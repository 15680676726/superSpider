from __future__ import annotations

from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest
from agentscope.message import Msg
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from copaw.evidence import EvidenceLedger
from copaw.kernel.executor_event_writeback_service import ExecutorEventWritebackService
from copaw.kernel.main_brain_intake import MainBrainIntakeContract
from copaw.kernel.main_brain_orchestrator import MainBrainOrchestrator
from copaw.kernel.turn_executor import KernelTurnExecutor
from copaw.state import AgentReportService, SQLiteStateStore
from copaw.state.executor_runtime_service import ExecutorRuntimeService
from copaw.state.external_runtime_service import ExternalCapabilityRuntimeService
from copaw.state.models_executor_runtime import (
    ExecutorProviderRecord,
    ModelInvocationPolicyRecord,
    RoleExecutorBindingRecord,
)
from copaw.state.repositories import SqliteExternalCapabilityRuntimeRepository


class _FakeQueryExecutionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield Msg(name="assistant", role="assistant", content="delegated"), True


class _FakeExecutorRuntimePort:
    def __init__(
        self,
        *,
        subscribed_events: list[object] | None = None,
        subscribe_error: Exception | None = None,
    ) -> None:
        self.start_calls: list[dict[str, object]] = []
        self.stop_calls: list[dict[str, object]] = []
        self._subscribed_events = list(subscribed_events or [])
        self._subscribe_error = subscribe_error
        self._server_request_handler = None
        self._restart_count = 0

    def start_assignment_turn(
        self,
        *,
        assignment_id: str,
        project_root: str,
        prompt: str,
        thread_id: str | None = None,
        model_ref: str | None = None,
        sidecar_launch_payload: dict[str, object] | None = None,
    ):
        payload = {
            "assignment_id": assignment_id,
            "project_root": project_root,
            "prompt": prompt,
            "thread_id": thread_id,
        }
        if model_ref is not None:
            payload["model_ref"] = model_ref
        if sidecar_launch_payload is not None:
            payload["sidecar_launch_payload"] = sidecar_launch_payload
        self.start_calls.append(payload)
        return SimpleNamespace(
            thread_id="thread-1",
            turn_id="turn-1",
            model_ref="gpt-5-codex",
            runtime_metadata={"source": "test-port"},
        )

    def steer_turn(self, *, thread_id: str, turn_id: str, prompt: str):
        return {
            "thread_id": thread_id,
            "turn_id": turn_id,
            "prompt": prompt,
        }

    def stop_turn(self, *, thread_id: str, turn_id: str | None = None):
        payload = {"thread_id": thread_id, "turn_id": turn_id}
        self.stop_calls.append(payload)
        return payload

    def subscribe_events(self, *, thread_id: str):
        _ = thread_id
        if self._subscribe_error is not None:
            raise self._subscribe_error
        return iter(self._subscribed_events)

    def normalize_event(self, payload: dict[str, object]):
        _ = payload
        return None

    def set_server_request_handler(self, handler) -> None:
        self._server_request_handler = handler

    def describe_sidecar(self) -> dict[str, object]:
        return {
            "transport_kind": "test-port",
            "connected": True,
            "restart_count": self._restart_count,
        }

    def restart_sidecar(self) -> dict[str, object]:
        self._restart_count += 1
        return {
            "transport_kind": "test-port",
            "connected": False,
            "restart_count": self._restart_count,
        }


def _build_executor_runtime_service(tmp_path: Path) -> ExecutorRuntimeService:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteExternalCapabilityRuntimeRepository(store)
    external_runtime_service = ExternalCapabilityRuntimeService(repository=repository)
    return ExecutorRuntimeService(external_runtime_service=external_runtime_service)


class _FakeAssignmentService:
    def __init__(self, assignment: SimpleNamespace) -> None:
        self._assignment = assignment
        self.attached_evidence_ids: list[str] = []

    def get_assignment(self, assignment_id: str):
        _ = assignment_id
        return self._assignment

    def attach_evidence_ids(self, assignment: str, *, evidence_ids: list[str]):
        _ = assignment
        self.attached_evidence_ids.extend(evidence_ids)
        return self._assignment


class _FakeReportRepository:
    def __init__(self) -> None:
        self.records = {}

    def get_report(self, report_id: str):
        return self.records.get(report_id)

    def upsert_report(self, report):
        self.records[report.id] = report
        return report


class _FakeRuntimeProviderFacade:
    def __init__(self, *, contract: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self._contract = dict(contract or {})
        self._error = error

    def resolve_runtime_provider_contract(self) -> dict[str, object]:
        if self._error is not None:
            raise self._error
        return dict(self._contract)


def _resolved_runtime_contract() -> dict[str, object]:
    return {
        "provider_id": "openai",
        "provider_name": "OpenAI",
        "model": "gpt-5.2",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test-secret",
        "auth_mode": "api_key",
        "provenance": {
            "resolution_reason": "Using configured active model.",
            "fallback_applied": False,
            "unavailable_candidates": [],
        },
    }


def _make_contract(
    *,
    writeback_requested: bool = False,
    writeback_plan: object | None = None,
) -> MainBrainIntakeContract:
    return MainBrainIntakeContract(
        message_text="Implement the assignment in Codex.",
        decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
        intent_kind="execute-task",
        writeback_requested=writeback_requested,
        writeback_plan=writeback_plan,
        should_kickoff=True,
    )


@pytest.mark.asyncio
async def test_main_brain_orchestrator_starts_executor_runtime_for_assignment(
    tmp_path: Path,
) -> None:
    from copaw.app.runtime_bootstrap_execution import build_executor_runtime_coordination

    query_execution_service = _FakeQueryExecutionService()
    executor_runtime_service = _build_executor_runtime_service(tmp_path)
    executor_runtime_service.upsert_executor_provider(
        ExecutorProviderRecord(
            provider_id="codex-app-server",
            provider_kind="external-executor",
            runtime_family="codex",
            control_surface_kind="app_server",
            default_protocol_kind="app_server",
        )
    )
    executor_runtime_service.upsert_role_executor_binding(
        RoleExecutorBindingRecord(
            role_id="backend-engineer",
            executor_provider_id="codex-app-server",
            selection_mode="role-routed",
            execution_policy_id="default-model-policy",
        )
    )
    executor_runtime_service.upsert_model_invocation_policy(
        ModelInvocationPolicyRecord(
            policy_id="default-model-policy",
            ownership_mode="runtime_owned",
            default_model_ref="gpt-5-codex",
        )
    )
    executor_port = _FakeExecutorRuntimePort()
    assignment_service = SimpleNamespace(
        get_assignment=lambda assignment_id: SimpleNamespace(
            id=assignment_id,
            owner_role_id="backend-engineer",
            owner_agent_id="agent-1",
            title="Implement runtime seam",
            summary="Route assignment into executor runtime",
            metadata={"project_profile_id": "carrier-main"},
        )
    )
    _service, coordinator = build_executor_runtime_coordination(
        assignment_service=assignment_service,
        external_runtime_service=executor_runtime_service._external_runtime_service,
        project_root=str(tmp_path),
        executor_runtime_port=executor_port,
        default_executor_provider_id="codex-app-server",
        default_model_policy_id="default-model-policy",
    )
    coordinator.set_executor_runtime_service(executor_runtime_service)

    async def _resolver(**_kwargs):
        return _make_contract()

    orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_resolver,
        executor_runtime_coordinator=coordinator,
    )
    request = AgentRequest(
        id="req-executor-runtime",
        session_id="industry-chat:industry-1:execution-core",
        user_id="user-1",
        channel="console",
        input=[],
    )
    request.assignment_id = "assign-1"
    msgs = [
        Msg(
            name="user",
            role="user",
            content="Implement the assignment in Codex and then report back.",
        )
    ]

    streamed = [
        item
        async for item in orchestrator.execute_stream(
            msgs=msgs,
            request=request,
            kernel_task_id="kernel-task-runtime",
        )
    ]

    assert len(streamed) == 1
    assert query_execution_service.calls == []
    assert "executor runtime" in streamed[0][0].get_text_content().lower()
    assert executor_port.start_calls == [
        {
            "assignment_id": "assign-1",
            "project_root": str(tmp_path),
            "prompt": "Implement the assignment in Codex.",
            "thread_id": None,
            "model_ref": "gpt-5-codex",
        }
    ]
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["executor_runtime"]["assignment_id"] == "assign-1"
    assert runtime_context["executor_runtime"]["runtime_id"]
    assert runtime_context["executor_runtime"]["thread_id"] == "thread-1"
    assert runtime_context["executor_runtime"]["turn_id"] == "turn-1"
    assert runtime_context["executor_runtime"]["provider_id"] == "codex-app-server"
    assert runtime_context["executor_runtime"]["model_policy_id"] == "default-model-policy"
    runtimes = executor_runtime_service.list_runtimes(assignment_id="assign-1")
    assert len(runtimes) == 1
    assert runtimes[0].thread_id == "thread-1"
    assert runtimes[0].runtime_status == "ready"


@pytest.mark.asyncio
async def test_main_brain_orchestrator_prefers_binding_model_policy_id_over_execution_policy_id(
    tmp_path: Path,
) -> None:
    from copaw.app.runtime_bootstrap_execution import build_executor_runtime_coordination

    query_execution_service = _FakeQueryExecutionService()
    executor_runtime_service = _build_executor_runtime_service(tmp_path)
    executor_runtime_service.upsert_executor_provider(
        ExecutorProviderRecord(
            provider_id="codex-app-server",
            provider_kind="external-executor",
            runtime_family="codex",
            control_surface_kind="app_server",
            default_protocol_kind="app_server",
        )
    )
    executor_runtime_service.upsert_role_executor_binding(
        RoleExecutorBindingRecord(
            role_id="backend-engineer",
            executor_provider_id="codex-app-server",
            selection_mode="role-routed",
            execution_policy_id="open-default",
            model_policy_id="codex-default",
        )
    )
    executor_runtime_service.upsert_model_invocation_policy(
        ModelInvocationPolicyRecord(
            policy_id="codex-default",
            ownership_mode="runtime_owned",
            default_model_ref="gpt-5-codex",
        )
    )
    executor_port = _FakeExecutorRuntimePort()
    assignment_service = SimpleNamespace(
        get_assignment=lambda assignment_id: SimpleNamespace(
            id=assignment_id,
            owner_role_id="backend-engineer",
            owner_agent_id="agent-1",
            title="Implement runtime seam",
            summary="Route assignment into executor runtime",
            metadata={"project_profile_id": "carrier-main"},
        )
    )
    _service, coordinator = build_executor_runtime_coordination(
        assignment_service=assignment_service,
        external_runtime_service=executor_runtime_service._external_runtime_service,
        project_root=str(tmp_path),
        executor_runtime_port=executor_port,
        default_executor_provider_id="codex-app-server",
        default_model_policy_id="fallback-default-model-policy",
    )
    coordinator.set_executor_runtime_service(executor_runtime_service)

    async def _resolver(**_kwargs):
        return _make_contract()

    orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_resolver,
        executor_runtime_coordinator=coordinator,
    )
    request = AgentRequest(
        id="req-executor-runtime-model-policy",
        session_id="industry-chat:industry-1:execution-core",
        user_id="user-1",
        channel="console",
        input=[],
    )
    request.assignment_id = "assign-model-policy"
    msgs = [
        Msg(
            name="user",
            role="user",
            content="Implement the assignment in Codex and then report back.",
        )
    ]

    streamed = [
        item
        async for item in orchestrator.execute_stream(
            msgs=msgs,
            request=request,
            kernel_task_id="kernel-task-runtime-model-policy",
        )
    ]

    assert len(streamed) == 1
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["executor_runtime"]["model_policy_id"] == "codex-default"


@pytest.mark.asyncio
async def test_main_brain_orchestrator_forwards_system_model_and_sidecar_provider_payload(
    tmp_path: Path,
) -> None:
    from copaw.app.runtime_bootstrap_execution import build_executor_runtime_coordination

    query_execution_service = _FakeQueryExecutionService()
    executor_runtime_service = _build_executor_runtime_service(tmp_path)
    executor_runtime_service.upsert_executor_provider(
        ExecutorProviderRecord(
            provider_id="codex-app-server",
            provider_kind="external-executor",
            runtime_family="codex",
            control_surface_kind="app_server",
            default_protocol_kind="app_server",
        )
    )
    executor_runtime_service.upsert_role_executor_binding(
        RoleExecutorBindingRecord(
            role_id="backend-engineer",
            executor_provider_id="codex-app-server",
            selection_mode="role-routed",
            model_policy_id="codex-default",
        )
    )
    executor_runtime_service.upsert_model_invocation_policy(
        ModelInvocationPolicyRecord(
            policy_id="codex-default",
            ownership_mode="copaw_managed",
            default_model_ref="gpt-5-codex",
        )
    )
    executor_port = _FakeExecutorRuntimePort()
    assignment_service = SimpleNamespace(
        get_assignment=lambda assignment_id: SimpleNamespace(
            id=assignment_id,
            owner_role_id="backend-engineer",
            owner_agent_id="agent-1",
            title="Implement runtime seam",
            summary="Route assignment into executor runtime",
            metadata={"project_profile_id": "carrier-main"},
        )
    )
    _service, coordinator = build_executor_runtime_coordination(
        assignment_service=assignment_service,
        external_runtime_service=executor_runtime_service._external_runtime_service,
        project_root=str(tmp_path),
        executor_runtime_port=executor_port,
        default_executor_provider_id="codex-app-server",
        default_model_policy_id="codex-default",
    )
    coordinator.set_executor_runtime_service(executor_runtime_service)
    coordinator.set_provider_runtime_facade(
        _FakeRuntimeProviderFacade(contract=_resolved_runtime_contract()),
    )

    async def _resolver(**_kwargs):
        return _make_contract()

    orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_resolver,
        executor_runtime_coordinator=coordinator,
    )
    request = AgentRequest(
        id="req-executor-runtime-model-governance",
        session_id="industry-chat:industry-1:execution-core",
        user_id="user-1",
        channel="console",
        input=[],
    )
    request.assignment_id = "assign-1"
    msgs = [
        Msg(
            name="user",
            role="user",
            content="Implement the assignment in Codex and then report back.",
        )
    ]

    _ = [
        item
        async for item in orchestrator.execute_stream(
            msgs=msgs,
            request=request,
            kernel_task_id="kernel-task-runtime",
        )
    ]

    assert executor_port.start_calls[0]["model_ref"] == "gpt-5-codex"
    provider_payload = executor_port.start_calls[0]["sidecar_launch_payload"]
    assert provider_payload["provider_resolution_status"] == "resolved"
    assert provider_payload["env"]["COPAW_PROVIDER_MODEL"] == "gpt-5-codex"
    assert provider_payload["env"]["COPAW_PROVIDER_API_KEY"] == "sk-test-secret"


@pytest.mark.asyncio
async def test_main_brain_orchestrator_blocks_executor_start_when_sidecar_provider_resolution_fails(
    tmp_path: Path,
) -> None:
    from copaw.app.runtime_bootstrap_execution import build_executor_runtime_coordination

    query_execution_service = _FakeQueryExecutionService()
    executor_runtime_service = _build_executor_runtime_service(tmp_path)
    executor_runtime_service.upsert_executor_provider(
        ExecutorProviderRecord(
            provider_id="codex-app-server",
            provider_kind="external-executor",
            runtime_family="codex",
            control_surface_kind="app_server",
            default_protocol_kind="app_server",
        )
    )
    executor_runtime_service.upsert_role_executor_binding(
        RoleExecutorBindingRecord(
            role_id="backend-engineer",
            executor_provider_id="codex-app-server",
            selection_mode="role-routed",
            model_policy_id="codex-default",
        )
    )
    executor_runtime_service.upsert_model_invocation_policy(
        ModelInvocationPolicyRecord(
            policy_id="codex-default",
            ownership_mode="copaw_managed",
            default_model_ref="gpt-5-codex",
        )
    )
    executor_port = _FakeExecutorRuntimePort()
    assignment_service = SimpleNamespace(
        get_assignment=lambda assignment_id: SimpleNamespace(
            id=assignment_id,
            owner_role_id="backend-engineer",
            owner_agent_id="agent-1",
            title="Implement runtime seam",
            summary="Route assignment into executor runtime",
            metadata={"project_profile_id": "carrier-main"},
        )
    )
    _service, coordinator = build_executor_runtime_coordination(
        assignment_service=assignment_service,
        external_runtime_service=executor_runtime_service._external_runtime_service,
        project_root=str(tmp_path),
        executor_runtime_port=executor_port,
        default_executor_provider_id="codex-app-server",
        default_model_policy_id="codex-default",
    )
    coordinator.set_executor_runtime_service(executor_runtime_service)
    coordinator.set_provider_runtime_facade(
        _FakeRuntimeProviderFacade(
            error=ValueError("No active or fallback model configured."),
        ),
    )

    async def _resolver(**_kwargs):
        return _make_contract()

    orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_resolver,
        executor_runtime_coordinator=coordinator,
    )
    request = AgentRequest(
        id="req-executor-runtime-provider-failure",
        session_id="industry-chat:industry-1:execution-core",
        user_id="user-1",
        channel="console",
        input=[],
    )
    request.assignment_id = "assign-1"
    msgs = [
        Msg(
            name="user",
            role="user",
            content="Implement the assignment in Codex and then report back.",
        )
    ]

    streamed = [
        item
        async for item in orchestrator.execute_stream(
            msgs=msgs,
            request=request,
            kernel_task_id="kernel-task-runtime",
        )
    ]

    assert executor_port.start_calls == []
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["executor_runtime"]["status"] == "failed"
    assert "No active or fallback model configured." in runtime_context["executor_runtime"]["error"]
    assert len(streamed) == 1


@pytest.mark.asyncio
async def test_main_brain_orchestrator_surfaces_sidecar_approval_and_allows_resolution(
    tmp_path: Path,
) -> None:
    from copaw.app.runtime_bootstrap_execution import build_executor_runtime_coordination

    query_execution_service = _FakeQueryExecutionService()
    executor_runtime_service = _build_executor_runtime_service(tmp_path)
    executor_runtime_service.upsert_executor_provider(
        ExecutorProviderRecord(
            provider_id="codex-app-server",
            provider_kind="external-executor",
            runtime_family="codex",
            control_surface_kind="app_server",
            default_protocol_kind="app_server",
        )
    )
    executor_runtime_service.upsert_role_executor_binding(
        RoleExecutorBindingRecord(
            role_id="backend-engineer",
            executor_provider_id="codex-app-server",
            selection_mode="role-routed",
            execution_policy_id="default-model-policy",
        )
    )
    executor_runtime_service.upsert_model_invocation_policy(
        ModelInvocationPolicyRecord(
            policy_id="default-model-policy",
            ownership_mode="runtime_owned",
            default_model_ref="gpt-5-codex",
        )
    )
    executor_port = _FakeExecutorRuntimePort()
    assignment = SimpleNamespace(
        id="assign-1",
        task_id="task-assign-1",
        industry_instance_id="industry-1",
        owner_role_id="backend-engineer",
        owner_agent_id="agent-1",
        report_back_mode="agent-report",
        title="Implement runtime seam",
        summary="Route assignment into executor runtime",
        metadata={"project_profile_id": "carrier-main", "risk_level": "confirm"},
    )
    assignment_service = _FakeAssignmentService(assignment)
    report_repository = _FakeReportRepository()
    report_service = AgentReportService(repository=report_repository)
    evidence_ledger = EvidenceLedger()
    _service, coordinator = build_executor_runtime_coordination(
        assignment_service=assignment_service,
        external_runtime_service=executor_runtime_service._external_runtime_service,
        project_root=str(tmp_path),
        executor_runtime_port=executor_port,
        default_executor_provider_id="codex-app-server",
        default_model_policy_id="default-model-policy",
    )
    coordinator.set_executor_runtime_service(executor_runtime_service)
    coordinator.set_executor_event_writeback_service(
        ExecutorEventWritebackService(
            evidence_ledger=evidence_ledger,
            assignment_service=assignment_service,
            agent_report_service=report_service,
            executor_runtime_service=executor_runtime_service,
        )
    )

    async def _resolver(**_kwargs):
        return _make_contract(writeback_requested=True)

    orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_resolver,
        executor_runtime_coordinator=coordinator,
    )
    request = AgentRequest(
        id="req-executor-runtime-approval",
        session_id="industry-chat:industry-1:execution-core",
        user_id="user-1",
        channel="console",
        input=[],
    )
    request.assignment_id = "assign-1"
    request.industry_instance_id = "industry-1"
    msgs = [Msg(name="user", role="user", content="Run the assignment.")]

    streamed = [
        item
        async for item in orchestrator.execute_stream(
            msgs=msgs,
            request=request,
            kernel_task_id="kernel-task-runtime",
        )
    ]

    assert len(streamed) == 1
    assert query_execution_service.calls == []

    approval_result: dict[str, object] = {}

    def _run_sidecar_request() -> None:
        approval_result["value"] = coordinator.handle_sidecar_request(
            {
                "jsonrpc": "2.0",
                "id": "approval-request-1",
                "method": "approval/request",
                "params": {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "requestId": "approval-1",
                    "summary": "Approve guarded command execution",
                },
            }
        )

    request_thread = threading.Thread(target=_run_sidecar_request, daemon=True)
    request_thread.start()

    pending: list[dict[str, object]] = []
    deadline = time.time() + 1.0
    while time.time() < deadline and not pending:
        pending = coordinator.list_pending_sidecar_approvals()
        time.sleep(0.01)

    assert len(pending) == 1
    assert pending[0]["request_id"] == "approval-1"
    assert pending[0]["status"] == "pending"
    assert pending[0]["risk_level"] == "confirm"

    response = coordinator.respond_to_sidecar_approval(
        "approval-1",
        decision="approved",
        reason="operator-approved",
    )
    request_thread.join(timeout=1.0)

    assert response["status"] == "approved"
    assert approval_result["value"]["decision"] == "approved"
    assert coordinator.list_pending_sidecar_approvals() == []
    evidence = evidence_ledger.list_by_task("task-assign-1")
    assert len(evidence) == 2
    assert [record.kind for record in evidence] == [
        "executor-approval",
        "executor-approval",
    ]
    runtimes = executor_runtime_service.list_runtimes(
        assignment_id="assign-1",
        formal_only=True,
    )
    assert len(runtimes) == 1
    assert runtimes[0].metadata["sidecar_control"]["approval"]["status"] == "approved"
    assert runtimes[0].metadata["sidecar_control"]["approval"]["request_id"] == "approval-1"


@pytest.mark.asyncio
async def test_main_brain_orchestrator_attaches_executor_runtime_event_writeback_context(
    tmp_path: Path,
) -> None:
    from copaw.app.runtime_bootstrap_execution import build_executor_runtime_coordination

    query_execution_service = _FakeQueryExecutionService()
    executor_runtime_service = _build_executor_runtime_service(tmp_path)
    executor_runtime_service.upsert_executor_provider(
        ExecutorProviderRecord(
            provider_id="codex-app-server",
            provider_kind="external-executor",
            runtime_family="codex",
            control_surface_kind="app_server",
            default_protocol_kind="app_server",
        )
    )
    executor_runtime_service.upsert_role_executor_binding(
        RoleExecutorBindingRecord(
            role_id="backend-engineer",
            executor_provider_id="codex-app-server",
            selection_mode="role-routed",
            execution_policy_id="default-model-policy",
        )
    )
    executor_runtime_service.upsert_model_invocation_policy(
        ModelInvocationPolicyRecord(
            policy_id="default-model-policy",
            ownership_mode="runtime_owned",
            default_model_ref="gpt-5-codex",
        )
    )
    executor_port = _FakeExecutorRuntimePort()
    assignment_service = SimpleNamespace(
        get_assignment=lambda assignment_id: SimpleNamespace(
            id=assignment_id,
            task_id="task-assign-1",
            industry_instance_id="industry-1",
            owner_role_id="backend-engineer",
            owner_agent_id="agent-1",
            report_back_mode="agent-report",
            title="Implement runtime seam",
            summary="Route assignment into executor runtime",
            metadata={
                "project_profile_id": "carrier-main",
                "risk_level": "guarded",
            },
        )
    )
    _service, coordinator = build_executor_runtime_coordination(
        assignment_service=assignment_service,
        external_runtime_service=executor_runtime_service._external_runtime_service,
        project_root=str(tmp_path),
        executor_runtime_port=executor_port,
        default_executor_provider_id="codex-app-server",
        default_model_policy_id="default-model-policy",
    )
    coordinator.set_executor_runtime_service(executor_runtime_service)

    writeback_plan = SimpleNamespace(
        active=True,
        classifications=["strategy", "backlog"],
        fingerprint="wb-plan-1",
    )

    async def _resolver(**_kwargs):
        return _make_contract(
            writeback_requested=True,
            writeback_plan=writeback_plan,
        )

    orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_resolver,
        executor_runtime_coordinator=coordinator,
    )
    request = AgentRequest(
        id="req-executor-runtime-writeback",
        session_id="industry-chat:industry-1:execution-core",
        user_id="user-1",
        channel="console",
        input=[],
    )
    request.assignment_id = "assign-1"
    request.industry_instance_id = "industry-1"
    request.control_thread_id = "control-thread-1"
    request.work_context_id = "ctx-1"
    msgs = [
        Msg(
            name="user",
            role="user",
            content="Implement the assignment in Codex and write back the result.",
        )
    ]

    streamed = [
        item
        async for item in orchestrator.execute_stream(
            msgs=msgs,
            request=request,
            kernel_task_id="kernel-task-runtime",
        )
    ]

    assert len(streamed) == 1
    assert query_execution_service.calls == []
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["assignment_id"] == "assign-1"
    assert runtime_context["task_id"] == "task-assign-1"
    assert runtime_context["industry_instance_id"] == "industry-1"
    assert runtime_context["owner_agent_id"] == "agent-1"
    assert runtime_context["owner_role_id"] == "backend-engineer"
    assert runtime_context["report_back_mode"] == "agent-report"

    executor_runtime = runtime_context["executor_runtime"]
    assert executor_runtime["assignment_title"] == "Implement runtime seam"
    assert executor_runtime["assignment_summary"] == "Route assignment into executor runtime"
    assert executor_runtime["risk_level"] == "guarded"
    event_ingest_context = executor_runtime["event_ingest_context"]
    assert event_ingest_context["runtime_id"] == executor_runtime["runtime_id"]
    assert event_ingest_context["executor_id"] == "codex-app-server"
    assert event_ingest_context["assignment_id"] == "assign-1"
    assert event_ingest_context["task_id"] == "task-assign-1"
    assert event_ingest_context["industry_instance_id"] == "industry-1"
    assert event_ingest_context["thread_id"] == "thread-1"
    assert event_ingest_context["turn_id"] == "turn-1"
    assert event_ingest_context["owner_agent_id"] == "agent-1"
    assert event_ingest_context["owner_role_id"] == "backend-engineer"
    assert event_ingest_context["assignment_title"] == "Implement runtime seam"
    assert event_ingest_context["assignment_summary"] == "Route assignment into executor runtime"
    assert event_ingest_context["risk_level"] == "guarded"
    assert event_ingest_context["metadata"]["control_thread_id"] == "control-thread-1"
    assert event_ingest_context["metadata"]["session_id"] == (
        "industry-chat:industry-1:execution-core"
    )
    assert event_ingest_context["metadata"]["work_context_id"] == "ctx-1"
    assert event_ingest_context["metadata"]["report_back_mode"] == "agent-report"
    assert event_ingest_context["metadata"]["writeback_requested"] is True
    assert event_ingest_context["metadata"]["writeback_plan_active"] is True
    assert event_ingest_context["metadata"]["writeback_plan_classifications"] == [
        "strategy",
        "backlog",
    ]
    assert event_ingest_context["metadata"]["writeback_plan_fingerprint"] == "wb-plan-1"


@pytest.mark.asyncio
async def test_main_brain_orchestrator_drains_executor_events_into_evidence_and_reports(
    tmp_path: Path,
) -> None:
    from copaw.app.runtime_bootstrap_execution import build_executor_runtime_coordination

    query_execution_service = _FakeQueryExecutionService()
    executor_runtime_service = _build_executor_runtime_service(tmp_path)
    executor_runtime_service.upsert_executor_provider(
        ExecutorProviderRecord(
            provider_id="codex-app-server",
            provider_kind="external-executor",
            runtime_family="codex",
            control_surface_kind="app_server",
            default_protocol_kind="app_server",
        )
    )
    executor_runtime_service.upsert_role_executor_binding(
        RoleExecutorBindingRecord(
            role_id="backend-engineer",
            executor_provider_id="codex-app-server",
            selection_mode="role-routed",
            execution_policy_id="default-model-policy",
        )
    )
    executor_runtime_service.upsert_model_invocation_policy(
        ModelInvocationPolicyRecord(
            policy_id="default-model-policy",
            ownership_mode="runtime_owned",
            default_model_ref="gpt-5-codex",
        )
    )
    executor_port = _FakeExecutorRuntimePort(
        subscribed_events=[
            SimpleNamespace(
                event_type="evidence_emitted",
                source_type="commandExecution",
                payload={
                    "thread_id": "thread-1",
                    "turn_id": "turn-1",
                    "command": "pytest -q",
                    "exit_code": 0,
                    "status": "completed",
                },
                raw_method="item/completed",
            ),
            SimpleNamespace(
                event_type="task_completed",
                source_type="turn",
                payload={
                    "thread_id": "thread-1",
                    "turn_id": "turn-1",
                    "summary": "Executor finished assignment successfully.",
                },
                raw_method="turn/completed",
            ),
        ]
    )
    assignment = SimpleNamespace(
        id="assign-1",
        task_id="task-assign-1",
        industry_instance_id="industry-1",
        owner_role_id="backend-engineer",
        owner_agent_id="agent-1",
        report_back_mode="agent-report",
        title="Implement runtime seam",
        summary="Route assignment into executor runtime",
        metadata={"project_profile_id": "carrier-main", "risk_level": "guarded"},
    )
    assignment_service = _FakeAssignmentService(assignment)
    report_repository = _FakeReportRepository()
    report_service = AgentReportService(repository=report_repository)
    evidence_ledger = EvidenceLedger()
    _service, coordinator = build_executor_runtime_coordination(
        assignment_service=assignment_service,
        external_runtime_service=executor_runtime_service._external_runtime_service,
        project_root=str(tmp_path),
        executor_runtime_port=executor_port,
        default_executor_provider_id="codex-app-server",
        default_model_policy_id="default-model-policy",
    )
    coordinator.set_executor_runtime_service(executor_runtime_service)
    coordinator.set_executor_event_writeback_service(
        ExecutorEventWritebackService(
            evidence_ledger=evidence_ledger,
            assignment_service=assignment_service,
            agent_report_service=report_service,
        )
    )

    async def _resolver(**_kwargs):
        return _make_contract(writeback_requested=True)

    orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_resolver,
        executor_runtime_coordinator=coordinator,
    )
    request = AgentRequest(
        id="req-executor-runtime-drain",
        session_id="industry-chat:industry-1:execution-core",
        user_id="user-1",
        channel="console",
        input=[],
    )
    request.assignment_id = "assign-1"
    request.industry_instance_id = "industry-1"
    request.control_thread_id = "control-thread-1"
    request.work_context_id = "ctx-1"
    msgs = [Msg(name="user", role="user", content="Run the assignment.")]

    streamed = [
        item
        async for item in orchestrator.execute_stream(
            msgs=msgs,
            request=request,
            kernel_task_id="kernel-task-runtime",
        )
    ]

    assert len(streamed) == 1
    assert query_execution_service.calls == []
    deadline = time.time() + 1.0
    while time.time() < deadline and not report_repository.records:
        time.sleep(0.01)

    evidence = evidence_ledger.list_by_task("task-assign-1")
    assert len(evidence) == 1
    assert assignment_service.attached_evidence_ids == [evidence[0].id]
    assert len(report_repository.records) == 1
    report = next(iter(report_repository.records.values()))
    assert report.assignment_id == "assign-1"
    assert report.result == "completed"
    assert evidence[0].id in report.evidence_ids
    stored_events = executor_runtime_service.list_event_records(thread_id="thread-1")
    stored_turns = executor_runtime_service.list_turn_records(thread_id="thread-1")
    assert [item.event_type for item in stored_events] == [
        "task_completed",
        "evidence_emitted",
    ]
    assert stored_turns[0].turn_status == "completed"
    assert stored_turns[0].summary == "Executor finished assignment successfully."
    runtimes = executor_runtime_service.list_runtimes(assignment_id="assign-1", formal_only=True)
    while time.time() < deadline and (not runtimes or runtimes[0].runtime_status != "completed"):
        time.sleep(0.01)
        runtimes = executor_runtime_service.list_runtimes(
            assignment_id="assign-1",
            formal_only=True,
        )
    assert len(runtimes) == 1
    assert runtimes[0].runtime_status == "completed"


@pytest.mark.asyncio
async def test_main_brain_orchestrator_persists_sidecar_recovery_failure_when_event_stream_crashes(
    tmp_path: Path,
) -> None:
    from copaw.app.runtime_bootstrap_execution import build_executor_runtime_coordination

    query_execution_service = _FakeQueryExecutionService()
    executor_runtime_service = _build_executor_runtime_service(tmp_path)
    executor_runtime_service.upsert_executor_provider(
        ExecutorProviderRecord(
            provider_id="codex-app-server",
            provider_kind="external-executor",
            runtime_family="codex",
            control_surface_kind="app_server",
            default_protocol_kind="app_server",
        )
    )
    executor_runtime_service.upsert_role_executor_binding(
        RoleExecutorBindingRecord(
            role_id="backend-engineer",
            executor_provider_id="codex-app-server",
            selection_mode="role-routed",
            execution_policy_id="default-model-policy",
        )
    )
    executor_runtime_service.upsert_model_invocation_policy(
        ModelInvocationPolicyRecord(
            policy_id="default-model-policy",
            ownership_mode="runtime_owned",
            default_model_ref="gpt-5-codex",
        )
    )
    executor_port = _FakeExecutorRuntimePort(
        subscribe_error=RuntimeError("sidecar crashed during event stream"),
    )
    assignment = SimpleNamespace(
        id="assign-1",
        task_id="task-assign-1",
        industry_instance_id="industry-1",
        owner_role_id="backend-engineer",
        owner_agent_id="agent-1",
        report_back_mode="agent-report",
        title="Implement runtime seam",
        summary="Route assignment into executor runtime",
        metadata={"project_profile_id": "carrier-main", "risk_level": "guarded"},
    )
    assignment_service = _FakeAssignmentService(assignment)
    report_repository = _FakeReportRepository()
    report_service = AgentReportService(repository=report_repository)
    evidence_ledger = EvidenceLedger()
    _service, coordinator = build_executor_runtime_coordination(
        assignment_service=assignment_service,
        external_runtime_service=executor_runtime_service._external_runtime_service,
        project_root=str(tmp_path),
        executor_runtime_port=executor_port,
        default_executor_provider_id="codex-app-server",
        default_model_policy_id="default-model-policy",
    )
    coordinator.set_executor_runtime_service(executor_runtime_service)
    coordinator.set_executor_event_writeback_service(
        ExecutorEventWritebackService(
            evidence_ledger=evidence_ledger,
            assignment_service=assignment_service,
            agent_report_service=report_service,
            executor_runtime_service=executor_runtime_service,
        )
    )

    async def _resolver(**_kwargs):
        return _make_contract(writeback_requested=True)

    orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_resolver,
        executor_runtime_coordinator=coordinator,
    )
    request = AgentRequest(
        id="req-executor-runtime-recovery",
        session_id="industry-chat:industry-1:execution-core",
        user_id="user-1",
        channel="console",
        input=[],
    )
    request.assignment_id = "assign-1"
    request.industry_instance_id = "industry-1"
    msgs = [Msg(name="user", role="user", content="Run the assignment.")]

    streamed = [
        item
        async for item in orchestrator.execute_stream(
            msgs=msgs,
            request=request,
            kernel_task_id="kernel-task-runtime",
        )
    ]

    assert len(streamed) == 1
    assert query_execution_service.calls == []

    deadline = time.time() + 1.0
    runtimes = executor_runtime_service.list_runtimes(
        assignment_id="assign-1",
        formal_only=True,
    )
    while time.time() < deadline and (
        not runtimes or runtimes[0].runtime_status != "failed"
    ):
        time.sleep(0.01)
        runtimes = executor_runtime_service.list_runtimes(
            assignment_id="assign-1",
            formal_only=True,
        )

    assert len(runtimes) == 1
    assert runtimes[0].runtime_status == "failed"
    assert "sidecar crashed during event stream" in runtimes[0].metadata["event_drain_error"]


def test_kernel_turn_executor_threads_executor_runtime_coordinator_into_orchestrator() -> None:
    query_execution_service = _FakeQueryExecutionService()
    coordinator = object()

    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        executor_runtime_coordinator=coordinator,
    )

    assert executor._main_brain_orchestrator._executor_runtime_coordinator is coordinator


def test_build_executor_runtime_coordination_creates_service_and_coordinator(
    tmp_path: Path,
) -> None:
    from copaw.app.runtime_bootstrap_execution import build_executor_runtime_coordination

    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteExternalCapabilityRuntimeRepository(store)
    external_runtime_service = ExternalCapabilityRuntimeService(repository=repository)

    service, coordinator = build_executor_runtime_coordination(
        assignment_service=SimpleNamespace(get_assignment=lambda _assignment_id: None),
        external_runtime_service=external_runtime_service,
        project_root=str(tmp_path),
    )

    assert service is not None
    assert coordinator is not None
