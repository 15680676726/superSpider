# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.runtime_center import Phase1StateQueryService
from copaw.app.routers.capabilities import router as capabilities_router
from copaw.app.routers.capability_market import router as capability_market_router
from copaw.app.routers.routines import router as routines_router
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.capabilities import CapabilityMount, CapabilityService
from copaw.capabilities.system_team_handlers import SystemTeamCapabilityFacade
from copaw.capabilities.remote_skill_contract import RemoteSkillCandidate
from copaw.evidence import EvidenceLedger
from copaw.goals import GoalService
from copaw.kernel import AgentProfileService, KernelDispatcher, KernelTask, KernelTaskStore
from copaw.routines import (
    RoutineDetail,
    RoutineDiagnosis,
    RoutineReplayRequest,
    RoutineReplayResponse,
    RoutineRunDetail,
    RoutineService,
)
from copaw.sop_kernel import FixedSopService
from copaw.state import AgentRuntimeRecord, GoalOverrideRecord, SQLiteStateStore
from copaw.state import ExecutionRoutineRecord, RoutineRunRecord
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteAgentProfileOverrideRepository,
    SqliteAgentRuntimeRepository,
    SqliteDecisionRequestRepository,
    SqliteFixedSopBindingRepository,
    SqliteFixedSopTemplateRepository,
    SqliteGoalOverrideRepository,
    SqliteGoalRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkflowRunRepository,
)


class StaticCapabilityRegistry:
    def __init__(self, *mounts: CapabilityMount) -> None:
        self._mounts = list(mounts)

    def list_capabilities(self) -> list[CapabilityMount]:
        return [mount.model_copy(deep=True) for mount in self._mounts]


class FakeTurnExecutor:
    def __init__(self) -> None:
        self.requests: list[tuple[object, dict[str, object]]] = []

    async def stream_request(self, request, **kwargs):
        self.requests.append((request, kwargs))
        yield {
            "object": "message",
            "status": "completed",
            "request": request,
        }


class FakeMCPClient:
    async def get_callable_function(
        self,
        tool_name: str,
        wrap_tool_result: bool = True,
        execution_timeout: float | None = None,
    ):
        async def _callable(**tool_args):
            return {
                "success": True,
                "summary": f"Ran {tool_name} with {tool_args}",
                "wrap_tool_result": wrap_tool_result,
                "execution_timeout": execution_timeout,
            }

        return _callable


class FakeMCPManager:
    async def get_client(self, client_key: str):
        if client_key == "browser":
            return FakeMCPClient()
        return None


class FakeMCPErrorClient:
    async def get_callable_function(
        self,
        tool_name: str,
        wrap_tool_result: bool = True,
        execution_timeout: float | None = None,
    ):
        _ = (tool_name, wrap_tool_result, execution_timeout)

        async def _callable(**tool_args):
            _ = tool_args
            return SimpleNamespace(
                content=[
                    {
                        "text": "Error executing tool focus_window: foreground switch blocked",
                    },
                ],
            )

        return _callable


class FakeMCPErrorManager:
    async def get_client(self, client_key: str):
        if client_key == "browser":
            return FakeMCPErrorClient()
        return None


class FakeAgentProfileService:
    def __init__(self, *, role_name: str, role_summary: str = "") -> None:
        self._role_name = role_name
        self._role_summary = role_summary

    def get_agent(self, agent_id: str):
        return type(
            "Profile",
            (),
            {
                "agent_id": agent_id,
                "name": agent_id,
                "role_name": self._role_name,
                "role_summary": self._role_summary,
            },
        )()


def _execute_capability_direct(
    capability_service: CapabilityService,
    dispatcher: KernelDispatcher,
    *,
    capability_id: str,
    payload: dict[str, object] | None = None,
    title: str | None = None,
    environment_ref: str | None = None,
    owner_agent_id: str = "copaw-operator",
) -> dict[str, object]:
    mount = capability_service.get_capability(capability_id)
    assert mount is not None
    task = KernelTask(
        title=title or mount.name,
        capability_ref=capability_id,
        environment_ref=environment_ref,
        owner_agent_id=owner_agent_id,
        risk_level=mount.risk_level,
        payload=dict(payload or {}),
    )
    admitted = dispatcher.submit(task)
    if admitted.phase != "executing":
        return admitted.model_dump(mode="json")
    return asyncio.run(dispatcher.execute_task(task.id)).model_dump(mode="json")


def test_capability_execute_runs_through_kernel_and_emits_evidence() -> None:
    app = FastAPI()
    app.include_router(capabilities_router)

    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(evidence_ledger=evidence_ledger)
    app.state.capability_service = capability_service
    dispatcher = KernelDispatcher(capability_service=capability_service)
    app.state.kernel_dispatcher = dispatcher

    payload = _execute_capability_direct(
        capability_service,
        dispatcher,
        capability_id="tool:get_current_time",
        payload={},
    )
    assert payload["success"] is True
    assert payload["phase"] == "completed"
    assert payload["summary"]
    assert payload["trace_id"].startswith("trace:")

    evidence = evidence_ledger.list_by_task(payload["task_id"])
    assert len(evidence) == 1
    assert evidence[0].capability_ref == "tool:get_current_time"
    assert evidence[0].risk_level == "auto"
    assert evidence[0].metadata["evidence_contract"] == ["call-record"]
    assert evidence[0].metadata["task_risk_level"] == "auto"
    assert evidence[0].metadata["trace_id"] == payload["trace_id"]


def test_capability_execute_route_is_retired() -> None:
    app = FastAPI()
    app.include_router(capabilities_router)
    app.state.capability_service = CapabilityService()
    app.state.kernel_dispatcher = KernelDispatcher(
        capability_service=app.state.capability_service,
    )

    client = TestClient(app)
    response = client.post(
        "/capabilities/tool:get_current_time/execute",
        json={"payload": {}},
    )

    assert response.status_code == 405


def test_goal_dispatch_capabilities_are_hidden_from_public_capability_routes() -> None:
    app = FastAPI()
    app.include_router(capabilities_router)
    app.include_router(capability_market_router)

    capability_service = CapabilityService()
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = KernelDispatcher(
        capability_service=capability_service,
    )

    client = TestClient(app)

    listed = client.get("/capabilities")
    assert listed.status_code == 200
    capability_ids = {item["id"] for item in listed.json()}
    assert "system:dispatch_goal" not in capability_ids
    assert "system:dispatch_active_goals" not in capability_ids

    market_listed = client.get("/capability-market/capabilities")
    assert market_listed.status_code == 200
    market_capability_ids = {item["id"] for item in market_listed.json()}
    assert "system:dispatch_goal" not in market_capability_ids
    assert "system:dispatch_active_goals" not in market_capability_ids

    market_overview = client.get("/capability-market/overview")
    assert market_overview.status_code == 200
    market_overview_ids = {
        item["id"] for item in market_overview.json().get("installed", [])
    }
    assert "system:dispatch_goal" not in market_overview_ids
    assert "system:dispatch_active_goals" not in market_overview_ids

    hidden_detail = client.get("/capabilities/system:dispatch_goal")
    assert hidden_detail.status_code == 404

    # Internal leaf execution still needs the mount for workflow/prediction/goals paths.
    assert capability_service.get_capability("system:dispatch_goal") is not None
    assert capability_service.get_capability("system:dispatch_active_goals") is not None


def test_confirm_capability_requires_kernel_confirmation_then_executes() -> None:
    app = FastAPI()
    app.include_router(capabilities_router)
    app.include_router(runtime_center_router)

    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="tool:get_current_time",
                name="get_current_time",
                summary="Return the current time.",
                kind="local-tool",
                source_kind="tool",
                risk_level="confirm",
                environment_requirements=[],
                evidence_contract=["call-record"],
                role_access_policy=["all"],
                enabled=True,
            ),
        ),
        evidence_ledger=evidence_ledger,
    )
    dispatcher = KernelDispatcher(capability_service=capability_service)
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = dispatcher

    client = TestClient(app)
    admitted_payload = _execute_capability_direct(
        capability_service,
        dispatcher,
        capability_id="tool:get_current_time",
        payload={},
    )
    assert admitted_payload["phase"] == "waiting-confirm"
    assert admitted_payload["trace_id"].startswith("trace:")
    assert evidence_ledger.list_by_task(admitted_payload["task_id"]) == []

    confirmed = client.post(
        f"/runtime-center/kernel/tasks/{admitted_payload['task_id']}/confirm",
    )
    assert confirmed.status_code == 200
    confirmed_payload = confirmed.json()
    assert confirmed_payload["success"] is True
    assert confirmed_payload["phase"] == "completed"
    assert confirmed_payload["trace_id"] == admitted_payload["trace_id"]

    evidence = evidence_ledger.list_by_task(admitted_payload["task_id"])
    assert len(evidence) == 1
    assert evidence[0].capability_ref == "tool:get_current_time"
    assert evidence[0].risk_level == "confirm"
    assert evidence[0].metadata["mount_risk_level"] == "confirm"
    assert evidence[0].metadata["trace_id"] == admitted_payload["trace_id"]


def test_capability_can_be_approved_by_decision_id(tmp_path) -> None:
    app = FastAPI()
    app.include_router(capabilities_router)
    app.include_router(runtime_center_router)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    schedule_repository = SqliteScheduleRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    evidence_ledger = EvidenceLedger()
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    capability_service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="tool:get_current_time",
                name="get_current_time",
                summary="Return the current time.",
                kind="local-tool",
                source_kind="tool",
                risk_level="confirm",
                environment_requirements=[],
                evidence_contract=["call-record"],
                role_access_policy=["all"],
                enabled=True,
            ),
        ),
        evidence_ledger=evidence_ledger,
    )
    dispatcher = KernelDispatcher(
        task_store=task_store,
        capability_service=capability_service,
    )
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = dispatcher
    app.state.state_query_service = Phase1StateQueryService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        schedule_repository=schedule_repository,
        decision_request_repository=decision_request_repository,
    )

    client = TestClient(app)
    admitted_payload = _execute_capability_direct(
        capability_service,
        dispatcher,
        capability_id="tool:get_current_time",
        payload={},
    )
    assert admitted_payload["phase"] == "waiting-confirm"
    decision_id = admitted_payload["decision_request_id"]
    assert decision_id

    decision_detail = client.get(f"/runtime-center/decisions/{decision_id}")
    assert decision_detail.status_code == 200
    assert decision_detail.json()["status"] == "open"

    reviewing = client.post(f"/runtime-center/decisions/{decision_id}/review")
    assert reviewing.status_code == 200
    assert reviewing.json()["status"] == "reviewing"

    confirmed = client.post(
        f"/runtime-center/decisions/{decision_id}/approve",
        json={"resolution": "Approved via decision endpoint."},
    )
    assert confirmed.status_code == 200
    confirmed_payload = confirmed.json()
    assert confirmed_payload["success"] is True
    assert confirmed_payload["phase"] == "completed"
    assert confirmed_payload["decision_request_id"] == decision_id

    decision_detail = client.get(f"/runtime-center/decisions/{decision_id}")
    assert decision_detail.status_code == 200
    assert decision_detail.json()["status"] == "approved"
    assert decision_detail.json()["resolution"] == "Approved via decision endpoint."

    evidence = evidence_ledger.list_by_task(admitted_payload["task_id"])
    assert any(
        record.action_summary == "执行能力 tool:get_current_time"
        for record in evidence
    )


def test_capability_decision_can_be_rejected_by_decision_id(tmp_path) -> None:
    app = FastAPI()
    app.include_router(capabilities_router)
    app.include_router(runtime_center_router)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    schedule_repository = SqliteScheduleRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=EvidenceLedger(),
    )
    capability_service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="tool:get_current_time",
                name="get_current_time",
                summary="Return the current time.",
                kind="local-tool",
                source_kind="tool",
                risk_level="confirm",
                environment_requirements=[],
                evidence_contract=["call-record"],
                role_access_policy=["all"],
                enabled=True,
            ),
        ),
    )
    dispatcher = KernelDispatcher(
        task_store=task_store,
        capability_service=capability_service,
    )
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = dispatcher
    app.state.state_query_service = Phase1StateQueryService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        schedule_repository=schedule_repository,
        decision_request_repository=decision_request_repository,
    )

    client = TestClient(app)
    admitted_payload = _execute_capability_direct(
        capability_service,
        dispatcher,
        capability_id="tool:get_current_time",
        payload={},
    )
    decision_id = admitted_payload["decision_request_id"]
    rejected = client.post(
        f"/runtime-center/decisions/{decision_id}/reject",
        json={"resolution": "Rejected via decision endpoint."},
    )

    assert rejected.status_code == 200
    rejected_payload = rejected.json()
    assert rejected_payload["success"] is False
    assert rejected_payload["phase"] == "cancelled"
    assert rejected_payload["decision_request_id"] == decision_id

    decision_detail = client.get(f"/runtime-center/decisions/{decision_id}")
    assert decision_detail.status_code == 200
    assert decision_detail.json()["status"] == "rejected"
    assert decision_detail.json()["resolution"] == "Rejected via decision endpoint."


def test_query_tool_confirmation_task_confirm_routes_through_decision_resume(
    tmp_path,
) -> None:
    app = FastAPI()
    app.include_router(runtime_center_router)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=EvidenceLedger(),
    )
    dispatcher = KernelDispatcher(task_store=task_store)
    app.state.kernel_dispatcher = dispatcher
    app.state.decision_request_repository = decision_request_repository
    app.state.query_execution_service = SimpleNamespace(
        resume_query_tool_confirmation=lambda **_: None,
    )

    task = KernelTask(
        title="Browser action confirmation",
        risk_level="confirm",
        capability_ref=None,
        payload={
            "decision_type": "query-tool-confirmation",
            "decision_summary": "Confirm browser action before continuing.",
            "auto_complete_on_approval": True,
            "approval_completion_summary": "Browser action confirmation approved.",
        },
    )
    admitted = dispatcher.submit(task)
    assert admitted.phase == "waiting-confirm"
    assert admitted.decision_request_id is not None

    client = TestClient(app)
    response = client.post(f"/runtime-center/kernel/tasks/{task.id}/confirm")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["phase"] == "completed"
    assert payload["decision_request_id"] == admitted.decision_request_id
    assert payload["resume_scheduled"] is True
    assert payload["resume_kind"] == "query-tool-confirmation"

    decision = decision_request_repository.get_decision_request(
        admitted.decision_request_id
    )
    assert decision is not None
    assert decision.status == "approved"


def test_skill_capability_execute_path(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(capabilities_router)

    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="skill:test-skill",
                name="test-skill",
                summary="Describe a test skill.",
                kind="skill-bundle",
                source_kind="skill",
                risk_level="auto",
                environment_requirements=[],
                evidence_contract=["call-record"],
                role_access_policy=["operator"],
                enabled=True,
            ),
        ),
        evidence_ledger=evidence_ledger,
    )
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = KernelDispatcher(capability_service=capability_service)

    class _Skill:
        name = "test-skill"
        source = "local"
        path = "/tmp/test-skill"
        content = "Test skill content"
        references = []
        scripts = []

    monkeypatch.setattr(
        "copaw.capabilities.skill_service.default_skill_service.list_all_skills",
        lambda: [_Skill()],
    )

    dispatcher = KernelDispatcher(capability_service=capability_service)
    app.state.kernel_dispatcher = dispatcher

    payload = _execute_capability_direct(
        capability_service,
        dispatcher,
        capability_id="skill:test-skill",
        payload={"action": "describe"},
    )
    assert payload["success"] is True
    assert payload["phase"] == "completed"
    assert "description loaded" in payload["summary"].lower()
    assert payload["output"]["skill"]["name"] == "test-skill"
    assert payload["output"]["skill"]["source"] == "local"

    evidence = evidence_ledger.list_by_task(payload["task_id"])
    assert len(evidence) == 1
    assert evidence[0].capability_ref == "skill:test-skill"


def test_mcp_capability_execute_path() -> None:
    app = FastAPI()
    app.include_router(capabilities_router)

    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="mcp:browser",
                name="browser",
                summary="Run MCP browser tools.",
                kind="remote-mcp",
                source_kind="mcp",
                risk_level="auto",
                environment_requirements=["mcp"],
                evidence_contract=["call-record"],
                role_access_policy=["operator"],
                enabled=True,
            ),
        ),
        evidence_ledger=evidence_ledger,
        mcp_manager=FakeMCPManager(),
    )
    app.state.capability_service = capability_service
    dispatcher = KernelDispatcher(capability_service=capability_service)
    app.state.kernel_dispatcher = dispatcher

    payload = _execute_capability_direct(
        capability_service,
        dispatcher,
        capability_id="mcp:browser",
        payload={"tool_name": "open_page", "tool_args": {"url": "https://example.com"}},
    )
    assert payload["success"] is True
    assert payload["phase"] == "completed"
    assert "open_page" in payload["summary"]
    assert payload["output"]["tool_name"] == "open_page"
    assert payload["output"]["client_key"] == "browser"
    assert payload["output"]["tool_output"]["wrap_tool_result"] is True

    evidence = evidence_ledger.list_by_task(payload["task_id"])
    assert len(evidence) == 1
    assert evidence[0].capability_ref == "mcp:browser"


def test_mcp_capability_execute_marks_tool_errors_as_failed() -> None:
    app = FastAPI()
    app.include_router(capabilities_router)

    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="mcp:browser",
                name="browser",
                summary="Run MCP browser tools.",
                kind="remote-mcp",
                source_kind="mcp",
                risk_level="auto",
                environment_requirements=["mcp"],
                evidence_contract=["call-record"],
                role_access_policy=["operator"],
                enabled=True,
            ),
        ),
        evidence_ledger=evidence_ledger,
        mcp_manager=FakeMCPErrorManager(),
    )
    app.state.capability_service = capability_service
    dispatcher = KernelDispatcher(capability_service=capability_service)
    app.state.kernel_dispatcher = dispatcher

    payload = _execute_capability_direct(
        capability_service,
        dispatcher,
        capability_id="mcp:browser",
        payload={"tool_name": "focus_window", "tool_args": {"process_id": 1}},
    )
    assert payload["success"] is False
    assert payload["phase"] == "failed"
    assert "Error executing tool focus_window" in payload["error"]
    assert payload["output"]["success"] is False
    assert payload["output"]["tool_output"]["success"] is False
    assert payload["output"]["tool_output"]["error"] == payload["error"]


def test_system_dispatch_query_executes_through_kernel_query_execution_service() -> None:
    app = FastAPI()
    app.include_router(capabilities_router)

    evidence_ledger = EvidenceLedger()
    turn_executor = FakeTurnExecutor()
    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
        turn_executor=turn_executor,
    )
    app.state.capability_service = capability_service
    dispatcher = KernelDispatcher(capability_service=capability_service)
    app.state.kernel_dispatcher = dispatcher

    payload = _execute_capability_direct(
        capability_service,
        dispatcher,
        capability_id="system:dispatch_query",
        payload={
            "request": {
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "hello kernel"}],
                    },
                ],
                "session_id": "goal-1",
                "user_id": "ops-agent",
                "channel": "goal",
            },
            "mode": "final",
            "dispatch_events": False,
        },
    )
    assert payload["success"] is True
    assert payload["phase"] == "completed"
    assert (
        payload["summary"]
        == "Dispatched query through the kernel-owned query execution service."
    )
    assert turn_executor.requests
    request_payload, kwargs = turn_executor.requests[0]
    assert request_payload["session_id"] == "goal-1"
    assert kwargs["skip_kernel_admission"] is True
    assert kwargs["kernel_task_id"] == payload["task_id"]

    evidence = evidence_ledger.list_by_task(payload["task_id"])
    assert len(evidence) == 1
    assert evidence[0].capability_ref == "system:dispatch_query"


def test_system_discover_capabilities_executes_through_shared_discovery_service(
    tmp_path,
) -> None:
    app = FastAPI()
    app.include_router(capabilities_router)

    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
    )
    sop_state_store = SQLiteStateStore(tmp_path / "sop-discovery-state.db")
    fixed_sop_service = FixedSopService(
        template_repository=SqliteFixedSopTemplateRepository(sop_state_store),
        binding_repository=SqliteFixedSopBindingRepository(sop_state_store),
        workflow_run_repository=SqliteWorkflowRunRepository(sop_state_store),
        agent_report_repository=SqliteAgentReportRepository(sop_state_store),
        evidence_ledger=evidence_ledger,
    )
    capability_service.get_discovery_service().set_fixed_sop_service(
        fixed_sop_service,
    )
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = KernelDispatcher(capability_service=capability_service)

    with patch(
        "copaw.capabilities.capability_discovery.search_allowlisted_remote_skill_candidates",
        return_value=[
                RemoteSkillCandidate(
                    candidate_key="curated:crm-followup-pro",
                    source_kind="curated",
                    source_label="SkillHub",
                    title="CRM Followup Pro",
                description="Remote CRM follow-up automation skill.",
                bundle_url="https://skillhub.example.com/crm-followup-pro.zip",
                source_url="https://skillhub.example.com/crm-followup-pro.zip",
                slug="crm-followup-pro",
                version="1.0.0",
                install_name="crm_followup_pro",
                capability_ids=["skill:crm_followup_pro"],
                capability_tags=["skill", "crm"],
                review_required=False,
                search_query="writeback",
                ),
            ],
        ) as mock_remote_search:
            payload = _execute_capability_direct(
                capability_service,
                app.state.kernel_dispatcher,
                capability_id="system:discover_capabilities",
                payload={
                    "queries": ["writeback"],
                    "providers": ["remote"],
                },
            )

    assert payload["success"] is True
    assert payload["phase"] == "completed"
    assert payload["output"]["mode"] == "query"
    assert payload["output"]["queries"] == ["writeback"]
    assert payload["output"]["candidates"][0]["candidate_key"] == "curated:crm-followup-pro"
    assert mock_remote_search.call_count == 1
    _, remote_kwargs = mock_remote_search.call_args
    assert remote_kwargs["include_curated"] is True
    assert remote_kwargs["include_hub"] is False
    assert any(
        item["template_id"] == "fixed-sop-webhook-writeback"
        for item in payload["output"]["sop_templates"]
    )

    evidence = evidence_ledger.list_by_task(payload["task_id"])
    assert len(evidence) == 1
    assert evidence[0].capability_ref == "system:discover_capabilities"


def test_system_replay_routine_executes_through_routine_service() -> None:
    app = FastAPI()
    app.include_router(capabilities_router)

    class FakeRun:
        id = "routine-run-1"
        status = "completed"
        deterministic_result = "replay-complete"
        failure_class = None
        fallback_mode = None
        fallback_task_id = None
        output_summary = "Routine replay completed."
        evidence_ids = ["evidence-routine-1", "evidence-routine-2"]

    class FakeRoutineResponse:
        run = FakeRun()
        routes = {
            "run": "/api/routines/runs/routine-run-1",
            "routine": "/api/routines/routine-1",
        }

    class FakeRoutineService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        async def replay_routine(self, routine_id: str, payload) -> FakeRoutineResponse:
            self.calls.append((routine_id, payload))
            return FakeRoutineResponse()

    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(evidence_ledger=evidence_ledger)
    routine_service = FakeRoutineService()
    capability_service.set_routine_service(routine_service)
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = KernelDispatcher(capability_service=capability_service)

    payload = _execute_capability_direct(
        capability_service,
        app.state.kernel_dispatcher,
        capability_id="system:replay_routine",
        owner_agent_id="ops-agent",
        payload={
            "routine_id": "routine-1",
            "owner_scope": "industry-v1-test",
            "session_id": "goal-1",
            "request_context": {"goal_id": "goal-1"},
            "input_payload": {"window": "today"},
        },
    )
    assert payload["success"] is True
    assert payload["phase"] == "completed"
    assert payload["summary"] == "Routine replay completed."
    assert len(routine_service.calls) == 1
    routine_id, replay_payload = routine_service.calls[0]
    assert routine_id == "routine-1"
    assert replay_payload.owner_agent_id == "ops-agent"
    assert replay_payload.input_payload == {"window": "today"}

    evidence = evidence_ledger.list_by_task(payload["task_id"])
    assert len(evidence) == 1
    assert evidence[0].capability_ref == "system:replay_routine"
    assert evidence[0].metadata["routine_run_id"] == "routine-run-1"
    assert evidence[0].metadata["routine_evidence_ids"] == [
        "evidence-routine-1",
        "evidence-routine-2",
    ]


def test_system_run_fixed_sop_executes_through_fixed_sop_service() -> None:
    app = FastAPI()
    app.include_router(capabilities_router)

    class FakeFixedSopService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        async def run_binding(self, binding_id: str, payload) -> SimpleNamespace:
            self.calls.append((binding_id, payload))
            return SimpleNamespace(
                binding_id=binding_id,
                status="success",
                summary="Fixed SOP binding executed.",
                evidence_id="fixed-sop-evidence-1",
                workflow_run_id="workflow-run-1",
                routes={"detail": f"/api/fixed-sops/bindings/{binding_id}"},
            )

    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(evidence_ledger=evidence_ledger)
    fixed_sop_service = FakeFixedSopService()
    capability_service.set_fixed_sop_service(fixed_sop_service)
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = KernelDispatcher(capability_service=capability_service)

    payload = _execute_capability_direct(
        capability_service,
        app.state.kernel_dispatcher,
        capability_id="system:run_fixed_sop",
        owner_agent_id="ops-agent",
        payload={
            "binding_id": "sop-binding-1",
            "owner_scope": "industry-v1-test",
            "workflow_run_id": "workflow-run-1",
            "environment_id": "env-desktop-1",
            "session_mount_id": "session-desktop-1",
            "input_payload": {"window": "today"},
        },
    )
    assert payload["success"] is True
    assert payload["phase"] == "completed"
    assert payload["summary"] == "Fixed SOP binding executed."
    assert len(fixed_sop_service.calls) == 1
    binding_id, trigger_payload = fixed_sop_service.calls[0]
    assert binding_id == "sop-binding-1"
    assert trigger_payload.owner_agent_id == "ops-agent"
    assert trigger_payload.environment_id == "env-desktop-1"
    assert trigger_payload.session_mount_id == "session-desktop-1"
    assert trigger_payload.input_payload == {"window": "today"}

    evidence = evidence_ledger.list_by_task(payload["task_id"])
    assert len(evidence) == 1
    assert evidence[0].capability_ref == "system:run_fixed_sop"
    assert evidence[0].metadata["fixed_sop_binding_id"] == "sop-binding-1"
    assert evidence[0].metadata["workflow_run_id"] == "workflow-run-1"
    assert evidence[0].metadata["fixed_sop_evidence_id"] == "fixed-sop-evidence-1"


def test_system_run_host_recovery_executes_through_environment_service() -> None:
    app = FastAPI()
    app.include_router(capabilities_router)

    class FakeEnvironmentService:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def run_host_recovery_cycle(self, **kwargs) -> dict[str, object]:
            self.calls.append(dict(kwargs))
            return {
                "executed": 2,
                "decisions": {
                    "recover": 1,
                    "re-observe": 1,
                },
                "results": [
                    {"session_mount_id": "session-1", "decision": "recover"},
                    {"session_mount_id": "session-2", "decision": "re-observe"},
                ],
            }

    evidence_ledger = EvidenceLedger()
    environment_service = FakeEnvironmentService()
    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
    )
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = KernelDispatcher(capability_service=capability_service)

    payload = _execute_capability_direct(
        capability_service,
        app.state.kernel_dispatcher,
        capability_id="system:run_host_recovery",
        owner_agent_id="copaw-main-brain",
        payload={
            "actor": "system:automation",
            "source": "automation:host_recovery",
            "limit": 10,
            "allow_cross_process_recovery": True,
        },
    )

    assert payload["success"] is True
    assert payload["phase"] == "completed"
    assert payload["summary"] == "Host recovery processed 2 actionable event(s)."
    assert len(environment_service.calls) == 1
    assert environment_service.calls[0]["limit"] == 10
    assert environment_service.calls[0]["allow_cross_process_recovery"] is True

    evidence = evidence_ledger.list_by_task(payload["task_id"])
    assert len(evidence) == 1
    assert evidence[0].capability_ref == "system:run_host_recovery"
    assert evidence[0].metadata["host_recovery"]["executed"] == 2


def test_routines_replay_route_is_retired() -> None:
    app = FastAPI()
    app.include_router(routines_router)

    verified_at = datetime(2026, 3, 18, 9, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 3, 18, 9, 5, tzinfo=timezone.utc)

    class FakeKernelGovernedRoutineService(RoutineService):
        def __init__(self) -> None:
            self.calls: list[tuple[str, RoutineReplayRequest | None]] = []
            self.routine = ExecutionRoutineRecord(
                id="routine-1",
                routine_key="kernel-governed-routine",
                name="Kernel Governed Routine",
                summary="Replay through the governed system capability.",
                owner_agent_id="ops-agent",
                owner_scope="industry-v1-test",
                engine_kind="browser",
                created_at=verified_at,
                updated_at=verified_at,
            )
            self.run = RoutineRunRecord(
                id="routine-run-1",
                routine_id="routine-1",
                source_type="manual",
                status="completed",
                owner_agent_id="ops-agent",
                owner_scope="industry-v1-test",
                session_id="browser-session-1",
                deterministic_result="replay-complete",
                output_summary="Kernel-governed routine replay completed.",
                evidence_ids=["evidence-routine-1"],
                started_at=verified_at,
                completed_at=completed_at,
                created_at=verified_at,
                updated_at=completed_at,
                metadata={"start_payload": {"status": "attached"}},
            )
            self.diagnosis = RoutineDiagnosis(
                routine_id="routine-1",
                last_run_id="routine-run-1",
                status="active",
                drift_status="stable",
                selector_health="healthy",
                session_health="healthy",
                lock_health="healthy",
                evidence_health="healthy",
                fallback_summary={"counts": {}, "last_fallback": None},
                recommended_actions=[],
                last_verified_at=verified_at.isoformat(),
            )

        def get_routine_detail(self, routine_id: str) -> RoutineDetail:
            if routine_id != self.routine.id:
                raise KeyError(f"Routine '{routine_id}' not found")
            return RoutineDetail(
                routine=self.routine,
                last_run=self.run,
                recent_runs=[self.run],
                diagnosis=self.diagnosis,
                routes={"replay": f"/api/routines/{self.routine.id}/replay"},
            )

        async def replay_routine(
            self,
            routine_id: str,
            payload: RoutineReplayRequest | None = None,
        ) -> RoutineReplayResponse:
            if routine_id != self.routine.id:
                raise KeyError(f"Routine '{routine_id}' not found")
            self.calls.append((routine_id, payload))
            return RoutineReplayResponse(
                run=self.run,
                diagnosis=self.diagnosis,
                routes={
                    "run": f"/api/routines/runs/{self.run.id}",
                    "routine": f"/api/routines/{self.routine.id}",
                    "diagnosis": f"/api/routines/{self.routine.id}/diagnosis",
                },
            )

        def get_run_detail(self, run_id: str) -> RoutineRunDetail:
            if run_id != self.run.id:
                raise KeyError(f"Routine run '{run_id}' not found")
            return RoutineRunDetail(
                run=self.run,
                routine=self.routine,
                routes={
                    "detail": f"/api/routines/runs/{self.run.id}",
                    "routine": f"/api/routines/{self.routine.id}",
                    "diagnosis": f"/api/routines/{self.routine.id}/diagnosis",
                },
            )

        def get_diagnosis(self, routine_id: str) -> RoutineDiagnosis:
            if routine_id != self.routine.id:
                raise KeyError(f"Routine '{routine_id}' not found")
            return self.diagnosis

    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(evidence_ledger=evidence_ledger)
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = KernelDispatcher(capability_service=capability_service)
    app.state.routine_service = FakeKernelGovernedRoutineService()

    client = TestClient(app)
    response = client.post(
        "/routines/routine-1/replay",
        json={
            "source_type": "manual",
            "owner_agent_id": "ops-agent",
            "owner_scope": "industry-v1-test",
            "session_id": "browser-session-1",
            "request_context": {"goal_id": "goal-1"},
        },
    )

    assert response.status_code == 404

    routine_service = app.state.routine_service
    assert len(routine_service.calls) == 0

    evidence = evidence_ledger.list_records(limit=None)
    assert evidence == []


def test_system_delegate_task_executes_through_delegation_service() -> None:
    app = FastAPI()
    app.include_router(capabilities_router)

    class FakeDelegationService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        async def delegate_task(self, parent_task_id: str, **kwargs):
            self.calls.append((parent_task_id, dict(kwargs)))
            return {
                "summary": "Delegation created.",
                "child_task": {"id": "child-task-1"},
            }

    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(evidence_ledger=evidence_ledger)
    delegation_service = FakeDelegationService()
    capability_service.set_delegation_service(delegation_service)
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = KernelDispatcher(capability_service=capability_service)

    payload = _execute_capability_direct(
        capability_service,
        app.state.kernel_dispatcher,
        capability_id="system:delegate_task",
        title="Delegate research",
        owner_agent_id="ops-agent",
        payload={
            "parent_task_id": "task-parent-1",
            "owner_agent_id": "ops-researcher",
            "prompt_text": "Review the latest operator handoff notes.",
            "industry_instance_id": "industry-v1-ops",
            "industry_role_id": "researcher",
        },
    )
    assert payload["success"] is True
    assert payload["phase"] == "completed"
    assert payload["summary"] == "Delegation created."
    assert len(delegation_service.calls) == 1
    parent_task_id, kwargs = delegation_service.calls[0]
    assert parent_task_id == "task-parent-1"
    assert kwargs["owner_agent_id"] == "ops-researcher"
    assert kwargs["industry_role_id"] == "researcher"


def test_execute_task_enforces_role_access_policy() -> None:
    service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="system:dispatch_goal",
                name="dispatch_goal",
                summary="Dispatch a goal.",
                kind="system-op",
                source_kind="system",
                risk_level="guarded",
                environment_requirements=[],
                evidence_contract=["kernel-task"],
                role_access_policy=["operator"],
                enabled=True,
            ),
        ),
        agent_profile_service=FakeAgentProfileService(role_name="guest"),
    )

    execution_result = asyncio.run(
        service.execute_task(
            KernelTask(
                id="task-role-denied",
                title="Dispatch goal",
                capability_ref="system:dispatch_goal",
                owner_agent_id="guest-agent",
                payload={},
            ),
        ),
    )
    assert execution_result["success"] is False
    assert "not authorized" in execution_result["error"]


def test_system_dispatch_goal_preserves_goal_owner_when_payload_owner_is_missing(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    goal_repository = SqliteGoalRepository(state_store)
    goal_override_repository = SqliteGoalOverrideRepository(state_store)
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)

    capability_service = CapabilityService()
    dispatcher = KernelDispatcher(capability_service=capability_service)
    goal_service = GoalService(
        repository=goal_repository,
        override_repository=goal_override_repository,
        dispatcher=dispatcher,
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
    )
    capability_service.set_goal_service(goal_service)

    goal = goal_service.create_goal(
        title="Dispatch seeded goal",
        summary="Preserve the compiler owner through system dispatch.",
        status="active",
    )
    goal_override_repository.upsert_override(
        GoalOverrideRecord(
            goal_id=goal.id,
            compiler_context={"owner_agent_id": "copaw-agent-runner"},
        ),
    )

    execution_result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                id="task-system-dispatch-goal",
                title="Dispatch goal",
                capability_ref="system:dispatch_goal",
                owner_agent_id="copaw-scheduler",
                payload={
                    "goal_id": goal.id,
                    "execute": False,
                    "context": {"source": "automation:dispatch_active_goals"},
                },
            ),
        ),
    )

    assert execution_result["success"] is True
    assert task_repository.list_tasks(goal_id=goal.id)[0].owner_agent_id == "copaw-agent-runner"


def test_system_apply_role_persists_agent_profile_override(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    agent_override_repository = SqliteAgentProfileOverrideRepository(state_store)
    service = CapabilityService(
        agent_profile_override_repository=agent_override_repository,
    )

    execution = asyncio.run(
        service.execute_task(
            KernelTask(
                id="task-apply-role",
                title="Apply role",
                capability_ref="system:apply_role",
                owner_agent_id="ops-agent",
                payload={
                    "role_text": "Operations lead\nOwns runtime closeout.",
                    "agent_id": "ops-agent",
                },
            ),
        ),
    )

    assert execution["success"] is True
    override = agent_override_repository.get_override("ops-agent")
    assert override is not None
    assert override.role_name == "Operations lead"
    assert "Owns runtime closeout." in (override.role_summary or "")


def test_system_apply_role_persists_capability_allowlist_and_preserves_role_baseline(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    agent_override_repository = SqliteAgentProfileOverrideRepository(state_store)
    agent_runtime_repository = SqliteAgentRuntimeRepository(state_store)
    agent_runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="ops-agent",
            actor_key="industry-v1-ops:operator",
            actor_fingerprint="fp-ops-agent",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent",
            role_name="Operator",
        ),
    )
    agent_profile_service = AgentProfileService(
        override_repository=agent_override_repository,
        agent_runtime_repository=agent_runtime_repository,
    )
    service = CapabilityService(
        agent_profile_override_repository=agent_override_repository,
        agent_profile_service=agent_profile_service,
    )

    execution = asyncio.run(
        service.execute_task(
            KernelTask(
                id="task-apply-role-capabilities",
                title="Assign capabilities",
                capability_ref="system:apply_role",
                owner_agent_id="runtime-center",
                payload={
                    "agent_id": "ops-agent",
                    "capabilities": ["tool:send_file_to_user"],
                    "reason": "runtime-center capability assignment",
                },
            ),
        ),
    )

    assert execution["success"] is True
    override = agent_override_repository.get_override("ops-agent")
    assert override is not None
    assert "tool:send_file_to_user" in (override.capabilities or [])
    assert "system:dispatch_query" in (override.capabilities or [])
    assert "tool:browser_use" in (override.capabilities or [])

    accessible = {
        mount.id
        for mount in service.list_accessible_capabilities(
            agent_id="ops-agent",
            enabled_only=True,
        )
    }
    assert "tool:send_file_to_user" in accessible
    assert "system:dispatch_query" in accessible


def test_update_industry_team_add_role_response_drops_goal_count() -> None:
    class FakeIndustryService:
        def get_instance_detail(self, instance_id: str):
            return SimpleNamespace(team=SimpleNamespace(agents=[]), instance_id=instance_id)

        async def add_role_to_instance_team(self, instance_id: str, **kwargs):
            _ = kwargs
            return SimpleNamespace(
                team=SimpleNamespace(agents=[{"agent_id": "agent-1"}]),
                goals=[{"goal_id": "goal-1"}],
                schedules=[{"schedule_id": "schedule-1"}],
            )

    facade = SystemTeamCapabilityFacade(
        get_capability_fn=lambda capability_id: None,
        resolve_agent_profile_fn=lambda agent_id: None,
        industry_service=FakeIndustryService(),
    )

    result = asyncio.run(
        facade.handle_update_industry_team(
            {
                "instance_id": "industry-v1-ops",
                "operation": "add-role",
                "role": {
                    "schema_version": "industry-role-blueprint-v1",
                    "role_id": "ops-support",
                    "agent_id": "agent-1",
                    "name": "Ops Support",
                    "role_name": "Ops Support",
                    "role_summary": "Handles support follow-up.",
                    "mission": "Close the support loop.",
                    "goal_kind": "ops-support",
                    "agent_class": "business",
                    "employment_mode": "career",
                    "activation_mode": "persistent",
                    "suspendable": False,
                    "risk_level": "guarded",
                    "environment_constraints": [],
                    "allowed_capabilities": ["system:dispatch_query"],
                    "evidence_expectations": ["support summary"],
                },
            },
        ),
    )

    assert result["success"] is True
    assert result["team_size"] == 1
    assert result["schedule_count"] == 1
    assert "goal_count" not in result
