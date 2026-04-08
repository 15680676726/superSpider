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
import copaw.capabilities.execution as capability_execution_module
from copaw.capabilities import CapabilityMount, CapabilityService
from copaw.capabilities.system_team_handlers import SystemTeamCapabilityFacade
from copaw.capabilities.remote_skill_contract import RemoteSkillCandidate
from copaw.config.config import Config, ExternalCapabilityPackageConfig
from copaw.evidence import EvidenceLedger
from copaw.goals import GoalService
from copaw.kernel import (
    AgentProfileService,
    KernelDispatcher,
    KernelTask,
    KernelTaskStore,
    KernelToolBridge,
)
from copaw.routines import (
    RoutineDetail,
    RoutineDiagnosis,
    RoutineReplayRequest,
    RoutineReplayResponse,
    RoutineRunDetail,
    RoutineService,
)
from copaw.sop_kernel import FixedSopService
from copaw.state import (
    AgentRuntimeRecord,
    ExternalCapabilityRuntimeService,
    GoalOverrideRecord,
    SQLiteStateStore,
)
from copaw.state import ExecutionRoutineRecord, RoutineRunRecord
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteAgentProfileOverrideRepository,
    SqliteAgentRuntimeRepository,
    SqliteDecisionRequestRepository,
    SqliteExternalCapabilityRuntimeRepository,
    SqliteFixedSopBindingRepository,
    SqliteFixedSopTemplateRepository,
    SqliteGoalOverrideRepository,
    SqliteGoalRepository,
    SqliteRuntimeFrameRepository,
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
        if client_key in {"browser", "openspace"}:
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


class FakeMCPCancelledClient:
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
                        "text": "Query was cancelled before completion.",
                    },
                ],
            )

        return _callable


class FakeMCPCancelledManager:
    async def get_client(self, client_key: str):
        if client_key == "browser":
            return FakeMCPCancelledClient()
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


class RecordingSharedWriterEnvironmentService:
    def __init__(self, *, conflict_scope: str | None = None) -> None:
        self.acquire_calls: list[dict[str, object]] = []
        self.heartbeat_calls: list[dict[str, object]] = []
        self.release_calls: list[dict[str, object]] = []
        self._conflict_scope = conflict_scope
        self._lease = SimpleNamespace(
            id="lease:shared-writer:1",
            lease_token="lease-token-1",
        )

    def acquire_shared_writer_lease(
        self,
        *,
        writer_lock_scope: str,
        owner: str,
        ttl_seconds: int | None = None,
        metadata: dict[str, object] | None = None,
        handle: object | None = None,
    ):
        self.acquire_calls.append(
            {
                "writer_lock_scope": writer_lock_scope,
                "owner": owner,
                "ttl_seconds": ttl_seconds,
                "metadata": dict(metadata or {}),
                "handle": handle,
            },
        )
        if self._conflict_scope == writer_lock_scope:
            raise RuntimeError(
                f"Writer scope '{writer_lock_scope}' is already leased by other-worker",
            )
        return self._lease

    def heartbeat_shared_writer_lease(
        self,
        lease_id: str,
        *,
        lease_token: str,
        ttl_seconds: int | None = None,
        metadata: dict[str, object] | None = None,
        handle: object | None = None,
    ):
        self.heartbeat_calls.append(
            {
                "lease_id": lease_id,
                "lease_token": lease_token,
                "ttl_seconds": ttl_seconds,
                "metadata": dict(metadata or {}),
                "handle": handle,
            },
        )
        return self._lease

    def release_shared_writer_lease(
        self,
        *,
        lease_id: str,
        lease_token: str | None = None,
        reason: str | None = None,
        release_status: str = "released",
        validate_token: bool = True,
    ):
        self.release_calls.append(
            {
                "lease_id": lease_id,
                "lease_token": lease_token,
                "reason": reason,
                "release_status": release_status,
                "validate_token": validate_token,
            },
        )
        return self._lease


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


def _build_external_runtime_capability_service(
    tmp_path,
    *,
    config: Config,
) -> CapabilityService:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    runtime_repository = SqliteExternalCapabilityRuntimeRepository(state_store)
    external_runtime_service = ExternalCapabilityRuntimeService(
        repository=runtime_repository,
    )
    with patch(
        "copaw.capabilities.sources.external_packages.load_config",
        return_value=config,
    ):
        from copaw.capabilities.sources.external_packages import (
            list_external_package_capabilities,
        )

        mounts = list_external_package_capabilities()
    return CapabilityService(
        registry=StaticCapabilityRegistry(*mounts),
        state_store=state_store,
        external_runtime_service=external_runtime_service,
        load_config_fn=lambda: config,
        save_config_fn=lambda updated: None,
    )


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

    # Legacy goal dispatch system mounts are fully retired from the capability graph.
    assert capability_service.get_capability("system:dispatch_goal") is None
    assert capability_service.get_capability("system:dispatch_active_goals") is None


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

    reviewing = client.post(f"/runtime-center/governed/decisions/{decision_id}/review")
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


def test_runtime_center_kernel_task_list_reads_from_state_query_not_live_lifecycle(
    tmp_path,
) -> None:
    app = FastAPI()
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
    dispatcher = KernelDispatcher(task_store=task_store)
    app.state.kernel_dispatcher = dispatcher
    app.state.state_query_service = Phase1StateQueryService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        schedule_repository=schedule_repository,
        decision_request_repository=decision_request_repository,
    )

    task = KernelTask(
        title="Approve treasury transfer",
        capability_ref="tool:confirm_transfer",
        environment_ref="env:finance:payments",
        owner_agent_id="finance-agent",
        risk_level="confirm",
        payload={"decision_type": "query-tool-confirmation"},
    )
    admitted = dispatcher.submit(task)
    assert admitted.phase == "waiting-confirm"

    def _unexpected_list_tasks(*args, **kwargs):
        _ = (args, kwargs)
        raise AssertionError("kernel task route should read from state query service")

    dispatcher.lifecycle.list_tasks = _unexpected_list_tasks

    client = TestClient(app)
    response = client.get("/runtime-center/kernel/tasks?phase=waiting-confirm")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == task.id
    assert payload[0]["phase"] == "waiting-confirm"
    assert payload[0]["risk_level"] == "confirm"
    assert payload[0]["environment_ref"] == "env:finance:payments"
    assert payload[0]["payload"] == {"decision_type": "query-tool-confirmation"}


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
        content = """---
name: test-skill
description: Test skill content
package_ref: https://example.com/test-skill.zip
package_kind: hub-bundle
package_version: 2.0.0
---
Test skill content
"""
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
    mount = capability_service.get_capability("skill:test-skill")
    assert payload["success"] is True
    assert payload["phase"] == "completed"
    assert "description loaded" in payload["summary"].lower()
    assert payload["output"]["skill"]["name"] == "test-skill"
    assert payload["output"]["skill"]["source"] == "local"
    assert mount is not None
    assert mount.package_ref == "https://example.com/test-skill.zip"
    assert mount.package_kind == "hub-bundle"
    assert mount.package_version == "2.0.0"

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

    with patch(
        "copaw.capabilities.service.load_config",
        return_value=SimpleNamespace(
            mcp=SimpleNamespace(
                clients={
                    "browser": SimpleNamespace(
                        name="Browser MCP",
                        description="Run MCP browser tools.",
                        enabled=True,
                        transport="stdio",
                        url="",
                        headers={},
                        command="npx",
                        args=["-y", "@scope/browser@3.4.5"],
                        env={},
                        cwd="",
                        registry=SimpleNamespace(
                            install_kind="package",
                            package_identifier="@scope/browser",
                            package_registry_type="npm",
                            remote_url="",
                            version="3.4.5",
                        ),
                    ),
                },
            ),
        ),
    ):
        mount = capability_service.get_capability("mcp:browser")

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
    assert mount is not None
    assert mount.package_ref == "@scope/browser"
    assert mount.package_kind == "npm"
    assert mount.package_version == "3.4.5"

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


def test_execution_failure_contract_classifies_cancellation_separately() -> None:
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
        evidence_ledger=EvidenceLedger(),
        mcp_manager=FakeMCPCancelledManager(),
    )

    result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                title="Cancelled MCP call",
                capability_ref="mcp:browser",
                owner_agent_id="copaw-operator",
                payload={
                    "tool_name": "open_page",
                    "tool_args": {"url": "https://example.com"},
                },
            ),
        ),
    )

    assert result["success"] is False
    assert result["error_kind"] == "cancelled"
    assert result["error"] == "Query was cancelled before completion."


def test_execution_failure_contract_classifies_tool_error_as_failed() -> None:
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
        evidence_ledger=EvidenceLedger(),
        mcp_manager=FakeMCPErrorManager(),
    )

    result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                title="Errored MCP call",
                capability_ref="mcp:browser",
                owner_agent_id="copaw-operator",
                payload={
                    "tool_name": "focus_window",
                    "tool_args": {"process_id": 1},
                },
            ),
        ),
    )

    assert result["success"] is False
    assert result["error_kind"] == "failed"
    assert "Error executing tool focus_window" in result["error"]


def test_execution_result_contract_normalizes_missing_capability_failure() -> None:
    capability_service = CapabilityService(
        evidence_ledger=EvidenceLedger(),
    )

    result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                title="Missing capability",
                capability_ref="system:dispatch_goal",
                owner_agent_id="copaw-operator",
                environment_ref="session:console:test",
                payload={"goal_id": "goal-1"},
            ),
        ),
    )

    assert result["success"] is False
    assert result["capability_id"] == "system:dispatch_goal"
    assert result["environment_ref"] == "session:console:test"
    assert result["error_kind"] == "failed"
    assert result["summary"] == result["error"]
    assert "evidence_id" in result


def test_execution_failure_contract_classifies_shell_timeout_separately(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "copaw.agents.tools.shell._execute_subprocess_sync",
        lambda cmd, cwd, timeout: (
            -1,
            "",
            f"Command execution exceeded the timeout of {timeout} seconds.",
        ),
    )
    capability_service = CapabilityService(
        evidence_ledger=EvidenceLedger(),
    )

    result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                title="Timed out shell call",
                capability_ref="tool:execute_shell_command",
                owner_agent_id="copaw-operator",
                environment_ref="session:console:test",
                payload={
                    "command": "sleep 10",
                    "timeout": 5,
                    "cwd": str(tmp_path),
                },
            ),
        ),
    )

    assert result["success"] is False
    assert result["error_kind"] == "timeout"
    assert result["environment_ref"] == "session:console:test"


def test_execution_failure_contract_classifies_blocked_shell_separately(
    monkeypatch,
    tmp_path,
) -> None:
    calls: list[tuple[str, str, int]] = []

    def _fake_subprocess(cmd: str, cwd: str, timeout: int):
        calls.append((cmd, cwd, timeout))
        return (0, "should not run", "")

    monkeypatch.setattr(
        "copaw.agents.tools.shell._execute_subprocess_sync",
        _fake_subprocess,
    )
    capability_service = CapabilityService(
        evidence_ledger=EvidenceLedger(),
    )

    result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                title="Blocked shell call",
                capability_ref="tool:execute_shell_command",
                owner_agent_id="copaw-operator",
                environment_ref="session:console:test",
                payload={
                    "command": "git reset --hard HEAD",
                    "timeout": 5,
                    "cwd": str(tmp_path),
                },
            ),
        ),
    )

    assert calls == []
    assert result["success"] is False
    assert result["error_kind"] == "blocked"
    assert "blocked" in result["summary"].lower()
    assert "git reset --hard head" in result["summary"].lower()


def test_file_execution_builds_internal_execution_context(tmp_path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("hello world", encoding="utf-8")
    capability_service = CapabilityService(
        evidence_ledger=EvidenceLedger(),
    )

    result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                title="Read file",
                capability_ref="tool:read_file",
                owner_agent_id="copaw-operator",
                environment_ref="session:console:test",
                payload={"file_path": str(target)},
            ),
        ),
    )

    assert result["success"] is True
    assert result["capability_id"] == "tool:read_file"
    assert result["environment_ref"] == "session:console:test"
    assert result["action_mode"] == "read"


def test_mount_declared_action_mode_overrides_capability_id_fallback(
    tmp_path,
) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("hello world", encoding="utf-8")
    capability_service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="tool:read_file",
                name="read_file",
                summary="Read a file.",
                kind="local-tool",
                source_kind="tool",
                risk_level="auto",
                environment_requirements=["workspace", "file-view"],
                evidence_contract=["file-read"],
                role_access_policy=["all"],
                enabled=True,
                metadata={
                    "execution_policy": {
                        "action_mode": "write",
                        "evidence_owner": "execution-facade",
                    },
                },
            ),
        ),
        evidence_ledger=EvidenceLedger(),
    )

    result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                title="Read file with mount-declared policy",
                capability_ref="tool:read_file",
                owner_agent_id="copaw-operator",
                environment_ref="session:console:test",
                payload={"file_path": str(target)},
            ),
        ),
    )

    assert result["success"] is True
    assert result["action_mode"] == "write"


def test_mount_declared_action_mode_falls_back_when_metadata_missing(
    tmp_path,
) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("hello world", encoding="utf-8")
    capability_service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="tool:read_file",
                name="read_file",
                summary="Read a file.",
                kind="local-tool",
                source_kind="tool",
                risk_level="auto",
                environment_requirements=["workspace", "file-view"],
                evidence_contract=["file-read"],
                role_access_policy=["all"],
                enabled=True,
            ),
        ),
        evidence_ledger=EvidenceLedger(),
    )

    result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                title="Read file with fallback policy",
                capability_ref="tool:read_file",
                owner_agent_id="copaw-operator",
                environment_ref="session:console:test",
                payload={"file_path": str(target)},
            ),
        ),
    )

    assert result["success"] is True
    assert result["action_mode"] == "read"


def test_mount_declared_writer_scope_source_acquires_and_releases_shared_writer_lease_for_direct_write(
    tmp_path,
) -> None:
    target = tmp_path / "notes.txt"

    class FakeEnvironmentService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []
            self._leases: dict[str, SimpleNamespace] = {}

        def acquire_shared_writer_lease(
            self,
            *,
            writer_lock_scope: str,
            owner: str,
            ttl_seconds: int | None = None,
            handle: object | None = None,
            metadata: dict[str, object] | None = None,
        ):
            self.calls.append(
                (
                    "acquire",
                    {
                        "writer_lock_scope": writer_lock_scope,
                        "owner": owner,
                        "ttl_seconds": ttl_seconds,
                        "handle": handle,
                        "metadata": dict(metadata or {}),
                    },
                ),
            )
            lease = SimpleNamespace(
                id="lease-1",
                lease_token="token-1",
                lease_status="leased",
                metadata=dict(metadata or {}),
            )
            self._leases[writer_lock_scope] = lease
            return lease

        def heartbeat_shared_writer_lease(
            self,
            lease_id: str,
            *,
            lease_token: str,
            ttl_seconds: int | None = None,
            handle: object | None = None,
            metadata: dict[str, object] | None = None,
        ):
            self.calls.append(
                (
                    "heartbeat",
                    {
                        "lease_id": lease_id,
                        "lease_token": lease_token,
                        "ttl_seconds": ttl_seconds,
                        "handle": handle,
                        "metadata": dict(metadata or {}),
                    },
                ),
            )
            return SimpleNamespace(
                id=lease_id,
                lease_token=lease_token,
                lease_status="leased",
                metadata=dict(metadata or {}),
            )

        def release_shared_writer_lease(
            self,
            *,
            lease_id: str,
            lease_token: str | None = None,
            reason: str | None = None,
            release_status: str = "released",
            validate_token: bool = True,
        ):
            self.calls.append(
                (
                    "release",
                    {
                        "lease_id": lease_id,
                        "lease_token": lease_token,
                        "reason": reason,
                        "release_status": release_status,
                        "validate_token": validate_token,
                    },
                ),
            )
            for lease in self._leases.values():
                if lease.id == lease_id:
                    lease.lease_status = release_status
                    return lease
            return None

        def get_shared_writer_lease(self, *, writer_lock_scope: str):
            return self._leases.get(writer_lock_scope)

    fake_environment_service = FakeEnvironmentService()
    capability_service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="tool:write_file",
                name="write_file",
                summary="Write a file.",
                kind="local-tool",
                source_kind="tool",
                risk_level="guarded",
                environment_requirements=["workspace", "file-view"],
                evidence_contract=["file-write"],
                role_access_policy=["all"],
                enabled=True,
                metadata={
                    "execution_policy": {
                        "action_mode": "write",
                        "evidence_owner": "execution-facade",
                        "writer_scope_source": "file_path",
                    },
                },
            ),
        ),
        evidence_ledger=EvidenceLedger(),
        environment_service=fake_environment_service,
    )

    async def _fake_write_executor(**kwargs):
        active_lease = fake_environment_service.get_shared_writer_lease(
            writer_lock_scope=f"file:{target.resolve()}",
        )
        assert active_lease is not None
        assert active_lease.lease_status == "leased"
        return {
            "success": True,
            "summary": f"wrote {kwargs['file_path']}",
        }

    with patch.dict(
        capability_execution_module._TOOL_EXECUTORS,
        {"tool:write_file": _fake_write_executor},
    ):
        result = asyncio.run(
            capability_service.execute_task(
                KernelTask(
                    title="Write file with writer lease",
                    capability_ref="tool:write_file",
                    owner_agent_id="copaw-operator",
                    environment_ref="session:console:test",
                    payload={
                        "file_path": str(target),
                        "content": "hello writer lease",
                    },
                ),
            ),
        )

    assert result["success"] is True
    assert fake_environment_service.calls[0][0] == "acquire"
    assert (
        fake_environment_service.calls[0][1]["writer_lock_scope"]
        == f"file:{target.resolve()}"
    )
    assert fake_environment_service.calls[-1][0] == "release"
    released = fake_environment_service.get_shared_writer_lease(
        writer_lock_scope=f"file:{target.resolve()}",
    )
    assert released is not None
    assert released.lease_status == "released"


def test_mount_declared_writer_scope_conflict_blocks_direct_write_before_executor_runs(
    tmp_path,
) -> None:
    target = tmp_path / "notes.txt"
    executor_calls: list[dict[str, object]] = []

    class FakeEnvironmentService:
        def acquire_shared_writer_lease(
            self,
            *,
            writer_lock_scope: str,
            owner: str,
            ttl_seconds: int | None = None,
            handle: object | None = None,
            metadata: dict[str, object] | None = None,
        ):
            _ = (owner, ttl_seconds, handle, metadata)
            raise RuntimeError(f"writer scope '{writer_lock_scope}' already leased by another actor")

        def heartbeat_shared_writer_lease(self, *args, **kwargs):
            raise AssertionError("heartbeat should not run when acquire already failed")

        def release_shared_writer_lease(self, *args, **kwargs):
            raise AssertionError("release should not run when acquire already failed")

    capability_service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="tool:write_file",
                name="write_file",
                summary="Write a file.",
                kind="local-tool",
                source_kind="tool",
                risk_level="guarded",
                environment_requirements=["workspace", "file-view"],
                evidence_contract=["file-write"],
                role_access_policy=["all"],
                enabled=True,
                metadata={
                    "execution_policy": {
                        "action_mode": "write",
                        "evidence_owner": "execution-facade",
                        "writer_scope_source": "file_path",
                    },
                },
            ),
        ),
        evidence_ledger=EvidenceLedger(),
        environment_service=FakeEnvironmentService(),
    )

    async def _fake_write_executor(**kwargs):
        executor_calls.append(dict(kwargs))
        return {"success": True, "summary": "should not run"}

    with patch.dict(
        capability_execution_module._TOOL_EXECUTORS,
        {"tool:write_file": _fake_write_executor},
    ):
        result = asyncio.run(
            capability_service.execute_task(
                KernelTask(
                    title="Blocked write file with writer lease conflict",
                    capability_ref="tool:write_file",
                    owner_agent_id="copaw-operator",
                    environment_ref="session:console:test",
                    payload={
                        "file_path": str(target),
                        "content": "blocked",
                    },
                ),
            ),
        )

    assert executor_calls == []
    assert result["success"] is False
    assert result["error_kind"] == "blocked"
    assert "writer scope" in result["summary"].lower()


def test_builtin_edit_file_acquires_shared_writer_lease_for_direct_write(
    tmp_path,
) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("old", encoding="utf-8")

    class FakeEnvironmentService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []
            self._leases: dict[str, SimpleNamespace] = {}

        def acquire_shared_writer_lease(
            self,
            *,
            writer_lock_scope: str,
            owner: str,
            ttl_seconds: int | None = None,
            handle: object | None = None,
            metadata: dict[str, object] | None = None,
        ):
            self.calls.append(
                (
                    "acquire",
                    {
                        "writer_lock_scope": writer_lock_scope,
                        "owner": owner,
                        "ttl_seconds": ttl_seconds,
                        "handle": handle,
                        "metadata": dict(metadata or {}),
                    },
                ),
            )
            lease = SimpleNamespace(
                id="lease-edit-1",
                lease_token="token-edit-1",
                lease_status="leased",
                metadata=dict(metadata or {}),
            )
            self._leases[writer_lock_scope] = lease
            return lease

        def heartbeat_shared_writer_lease(
            self,
            lease_id: str,
            *,
            lease_token: str,
            ttl_seconds: int | None = None,
            handle: object | None = None,
            metadata: dict[str, object] | None = None,
        ):
            self.calls.append(
                (
                    "heartbeat",
                    {
                        "lease_id": lease_id,
                        "lease_token": lease_token,
                        "ttl_seconds": ttl_seconds,
                        "handle": handle,
                        "metadata": dict(metadata or {}),
                    },
                ),
            )
            return SimpleNamespace(
                id=lease_id,
                lease_token=lease_token,
                lease_status="leased",
                metadata=dict(metadata or {}),
            )

        def release_shared_writer_lease(
            self,
            *,
            lease_id: str,
            lease_token: str | None = None,
            reason: str | None = None,
            release_status: str = "released",
            validate_token: bool = True,
        ):
            self.calls.append(
                (
                    "release",
                    {
                        "lease_id": lease_id,
                        "lease_token": lease_token,
                        "reason": reason,
                        "release_status": release_status,
                        "validate_token": validate_token,
                    },
                ),
            )
            for lease in self._leases.values():
                if lease.id == lease_id:
                    lease.lease_status = release_status
                    return lease
            return None

        def get_shared_writer_lease(self, *, writer_lock_scope: str):
            return self._leases.get(writer_lock_scope)

    fake_environment_service = FakeEnvironmentService()
    capability_service = CapabilityService(
        evidence_ledger=EvidenceLedger(),
        environment_service=fake_environment_service,
    )

    async def _fake_edit_executor(**kwargs):
        active_lease = fake_environment_service.get_shared_writer_lease(
            writer_lock_scope=f"file:{target.resolve()}",
        )
        assert active_lease is not None
        assert active_lease.lease_status == "leased"
        return {"success": True, "summary": f"edited {kwargs['file_path']}"}

    with patch.dict(
        capability_execution_module._TOOL_EXECUTORS,
        {"tool:edit_file": _fake_edit_executor},
    ):
        result = asyncio.run(
            capability_service.execute_task(
                KernelTask(
                    title="Edit file with builtin writer lease",
                    capability_ref="tool:edit_file",
                    owner_agent_id="copaw-operator",
                    environment_ref="session:console:test",
                    payload={
                        "file_path": str(target),
                        "old_text": "old",
                        "new_text": "new",
                    },
                ),
            ),
        )

    assert result["success"] is True
    assert fake_environment_service.calls[0][0] == "acquire"
    assert (
        fake_environment_service.calls[0][1]["writer_lock_scope"]
        == f"file:{target.resolve()}"
    )
    assert fake_environment_service.calls[-1][0] == "release"


def test_write_mount_without_resolved_writer_scope_blocks_direct_execution_fail_closed(
    tmp_path,
) -> None:
    target = tmp_path / "notes.txt"
    executor_calls: list[dict[str, object]] = []
    capability_service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="tool:write_file",
                name="write_file",
                summary="Write a file.",
                kind="local-tool",
                source_kind="tool",
                risk_level="guarded",
                environment_requirements=["workspace", "file-view"],
                evidence_contract=["file-write"],
                role_access_policy=["all"],
                enabled=True,
                metadata={
                    "execution_policy": {
                        "action_mode": "write",
                        "evidence_owner": "execution-facade",
                    },
                },
            ),
        ),
        evidence_ledger=EvidenceLedger(),
    )

    async def _fake_write_executor(**kwargs):
        executor_calls.append(dict(kwargs))
        return {"success": True, "summary": "should not run"}

    with patch.dict(
        capability_execution_module._TOOL_EXECUTORS,
        {"tool:write_file": _fake_write_executor},
    ):
        result = asyncio.run(
            capability_service.execute_task(
                KernelTask(
                    title="Blocked write file without writer scope",
                    capability_ref="tool:write_file",
                    owner_agent_id="copaw-operator",
                    environment_ref="session:console:test",
                    payload={
                        "file_path": str(target),
                        "content": "blocked",
                    },
                ),
            ),
        )

    assert executor_calls == []
    assert result["success"] is False
    assert result["error_kind"] == "blocked"
    assert "writer lock scope" in result["summary"].lower()


def test_write_mount_with_blank_declared_writer_scope_blocks_direct_execution_fail_closed(
    tmp_path,
) -> None:
    target = tmp_path / "notes.txt"
    executor_calls: list[dict[str, object]] = []
    capability_service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="tool:write_file",
                name="write_file",
                summary="Write a file.",
                kind="local-tool",
                source_kind="tool",
                risk_level="guarded",
                environment_requirements=["workspace", "file-view"],
                evidence_contract=["file-write"],
                role_access_policy=["all"],
                enabled=True,
                metadata={
                    "execution_policy": {
                        "action_mode": "write",
                        "evidence_owner": "execution-facade",
                        "writer_lock_scope": "   ",
                    },
                },
            ),
        ),
        evidence_ledger=EvidenceLedger(),
    )

    async def _fake_write_executor(**kwargs):
        executor_calls.append(dict(kwargs))
        return {"success": True, "summary": "should not run"}

    with patch.dict(
        capability_execution_module._TOOL_EXECUTORS,
        {"tool:write_file": _fake_write_executor},
    ):
        result = asyncio.run(
            capability_service.execute_task(
                KernelTask(
                    title="Blocked write file with blank writer scope",
                    capability_ref="tool:write_file",
                    owner_agent_id="copaw-operator",
                    environment_ref="session:console:test",
                    payload={
                        "file_path": str(target),
                        "content": "blocked",
                    },
                ),
            ),
        )

    assert executor_calls == []
    assert result["success"] is False
    assert result["error_kind"] == "blocked"
    assert "writer lock scope" in result["summary"].lower()


def test_execute_task_batch_runs_parallel_reads_before_serial_write(
    monkeypatch,
) -> None:
    from copaw.capabilities.tool_execution_contracts import (
        TOOL_EXECUTION_CONTRACTS,
        ToolExecutionContract,
    )

    events: list[str] = []

    async def _read_time(**kwargs):
        _ = kwargs
        events.append("start:time")
        await asyncio.sleep(0.02)
        events.append("end:time")
        return {"success": True, "summary": "time"}

    async def _read_file(**kwargs):
        _ = kwargs
        events.append("start:file")
        await asyncio.sleep(0.02)
        events.append("end:file")
        return {"success": True, "summary": "file"}

    async def _write_file(**kwargs):
        _ = kwargs
        events.append("start:write")
        events.append("end:write")
        return {"success": True, "summary": "write"}

    monkeypatch.setitem(
        TOOL_EXECUTION_CONTRACTS,
        "tool:get_current_time",
        ToolExecutionContract(
            capability_id="tool:get_current_time",
            executor=_read_time,
            action_mode="read",
            concurrency_class="parallel-read",
            preflight_policy="inline",
            result_normalizer=lambda response: response,
        ),
    )
    monkeypatch.setitem(capability_execution_module._TOOL_EXECUTORS, "tool:get_current_time", _read_time)
    monkeypatch.setitem(
        TOOL_EXECUTION_CONTRACTS,
        "tool:read_file",
        ToolExecutionContract(
            capability_id="tool:read_file",
            executor=_read_file,
            action_mode="read",
            concurrency_class="parallel-read",
            preflight_policy="inline",
            result_normalizer=lambda response: response,
        ),
    )
    monkeypatch.setitem(capability_execution_module._TOOL_EXECUTORS, "tool:read_file", _read_file)
    monkeypatch.setitem(
        TOOL_EXECUTION_CONTRACTS,
        "tool:write_file",
        ToolExecutionContract(
            capability_id="tool:write_file",
            executor=_write_file,
            action_mode="write",
            concurrency_class="serial-write",
            preflight_policy="inline",
            result_normalizer=lambda response: response,
        ),
    )
    monkeypatch.setitem(capability_execution_module._TOOL_EXECUTORS, "tool:write_file", _write_file)

    capability_service = CapabilityService(
        evidence_ledger=EvidenceLedger(),
    )

    results = asyncio.run(
        capability_service.execute_task_batch(
            [
                KernelTask(
                    title="Read time",
                    capability_ref="tool:get_current_time",
                    owner_agent_id="copaw-operator",
                    environment_ref="session:console:test",
                    payload={},
                ),
                KernelTask(
                    title="Read file",
                    capability_ref="tool:read_file",
                    owner_agent_id="copaw-operator",
                    environment_ref="session:console:test",
                    payload={"file_path": "README.md"},
                ),
                KernelTask(
                    title="Write file",
                    capability_ref="tool:write_file",
                    owner_agent_id="copaw-operator",
                    environment_ref="session:console:test",
                    payload={"file_path": "README.md", "content": "updated"},
                ),
            ],
        ),
    )

    assert [result["success"] for result in results] == [True, True, True]
    assert events[:2] == ["start:time", "start:file"]
    assert events.index("start:write") > events.index("end:time")
    assert events.index("start:write") > events.index("end:file")
    assert events[-2:] == ["start:write", "end:write"]


def test_mount_declared_evidence_owner_can_prefer_execution_facade_over_tool_bridge(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "copaw.agents.tools.shell._execute_subprocess_sync",
        lambda cmd, cwd, timeout: (0, "hello world", ""),
    )
    state_store = SQLiteStateStore(tmp_path / "tool-bridge-policy-state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "tool-bridge-policy-evidence.db")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    tool_bridge = KernelToolBridge(task_store=task_store)
    capability_service = CapabilityService(
        registry=StaticCapabilityRegistry(
            CapabilityMount(
                id="tool:execute_shell_command",
                name="execute_shell_command",
                summary="Execute a shell command.",
                kind="local-tool",
                source_kind="tool",
                risk_level="guarded",
                environment_requirements=["workspace"],
                evidence_contract=["shell-command", "stdout", "stderr"],
                role_access_policy=["all"],
                enabled=True,
                metadata={
                    "execution_policy": {
                        "action_mode": "write",
                        "evidence_owner": "execution-facade",
                    },
                },
            ),
        ),
        evidence_ledger=evidence_ledger,
        tool_bridge=tool_bridge,
    )
    dispatcher = KernelDispatcher(
        task_store=task_store,
        capability_service=capability_service,
    )

    task = KernelTask(
        title="Shell command with mount-declared evidence owner",
        capability_ref="tool:execute_shell_command",
        owner_agent_id="copaw-operator",
        environment_ref="session:console:test",
        payload={"command": "echo hello", "cwd": str(tmp_path)},
    )
    admitted = dispatcher.submit(task)
    assert admitted.phase == "executing"

    payload = asyncio.run(
        capability_service.execute_task(task_store.get(admitted.task_id)),
    )

    assert payload["success"] is True
    assert payload["evidence_id"] is not None
    records = evidence_ledger.list_by_task(admitted.task_id)
    assert any(record.id == payload["evidence_id"] for record in records)


def test_shell_execution_writes_evidence_via_unified_contract(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "copaw.agents.tools.shell._execute_subprocess_sync",
        lambda cmd, cwd, timeout: (0, "hello world", ""),
    )
    monkeypatch.setattr("copaw.kernel.tool_bridge.WORKING_DIR", tmp_path)
    state_store = SQLiteStateStore(tmp_path / "tool-bridge-state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "tool-bridge-evidence.db")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    tool_bridge = KernelToolBridge(task_store=task_store)
    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
        tool_bridge=tool_bridge,
    )
    dispatcher = KernelDispatcher(
        task_store=task_store,
        capability_service=capability_service,
    )

    payload = _execute_capability_direct(
        capability_service,
        dispatcher,
        capability_id="tool:execute_shell_command",
        environment_ref="session:console:test",
        payload={"command": "echo hello", "cwd": str(tmp_path)},
    )

    assert payload["success"] is True
    records = evidence_ledger.list_by_task(payload["task_id"])
    assert any(
        record.capability_ref == "tool:execute_shell_command"
        and record.status == "succeeded"
        and record.metadata["status"] == "success"
        for record in records
    )


def test_blocked_shell_execution_preserves_contract_metadata_in_tool_bridge_evidence(
    monkeypatch,
    tmp_path,
) -> None:
    calls: list[tuple[str, str, int]] = []

    def _fake_subprocess(cmd: str, cwd: str, timeout: int):
        calls.append((cmd, cwd, timeout))
        return (0, "should not run", "")

    monkeypatch.setattr(
        "copaw.agents.tools.shell._execute_subprocess_sync",
        _fake_subprocess,
    )
    state_store = SQLiteStateStore(tmp_path / "tool-bridge-blocked-state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "tool-bridge-blocked-evidence.db")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
        tool_bridge=KernelToolBridge(task_store=task_store),
    )
    dispatcher = KernelDispatcher(
        task_store=task_store,
        capability_service=capability_service,
    )

    payload = _execute_capability_direct(
        capability_service,
        dispatcher,
        capability_id="tool:execute_shell_command",
        environment_ref="session:console:test",
        payload={
            "command": "git reset --hard HEAD",
            "timeout": 5,
            "cwd": str(tmp_path),
        },
    )

    assert calls == []
    assert payload["success"] is False
    assert payload["phase"] in {"blocked", "failed"}
    records = evidence_ledger.list_by_task(payload["task_id"])
    assert len(records) == 1
    record = records[0]
    assert record.status == "blocked"
    assert record.metadata["tool_contract"] == "tool:execute_shell_command"
    assert record.metadata["concurrency_class"] == "serial-write"
    assert record.metadata["preflight_policy"] == "shell-safety"
    assert record.metadata["outcome_kind"] == "blocked"
    assert record.metadata["read_only"] is False


def test_shell_execution_blocked_status_propagates_to_tool_bridge_evidence(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr("copaw.kernel.tool_bridge.WORKING_DIR", tmp_path)
    state_store = SQLiteStateStore(tmp_path / "tool-bridge-blocked-state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "tool-bridge-blocked-evidence.db")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    tool_bridge = KernelToolBridge(task_store=task_store)
    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
        tool_bridge=tool_bridge,
    )
    dispatcher = KernelDispatcher(
        task_store=task_store,
        capability_service=capability_service,
    )

    payload = _execute_capability_direct(
        capability_service,
        dispatcher,
        capability_id="tool:execute_shell_command",
        environment_ref="session:console:test",
        payload={"command": "git reset --hard HEAD", "cwd": str(tmp_path)},
    )

    assert payload["success"] is False
    records = evidence_ledger.list_by_task(payload["task_id"])
    assert any(
        record.capability_ref == "tool:execute_shell_command"
        and record.status == "blocked"
        and record.metadata["status"] == "blocked"
        for record in records
    )


def test_shell_execution_tool_bridge_evidence_carries_execution_contract_metadata(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "copaw.agents.tools.shell._execute_subprocess_sync",
        lambda cmd, cwd, timeout: (0, "hello world", ""),
    )
    monkeypatch.setattr("copaw.kernel.tool_bridge.WORKING_DIR", tmp_path)
    state_store = SQLiteStateStore(tmp_path / "tool-bridge-metadata-state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "tool-bridge-metadata-evidence.db")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    tool_bridge = KernelToolBridge(task_store=task_store)
    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
        tool_bridge=tool_bridge,
    )
    dispatcher = KernelDispatcher(
        task_store=task_store,
        capability_service=capability_service,
    )

    payload = _execute_capability_direct(
        capability_service,
        dispatcher,
        capability_id="tool:execute_shell_command",
        environment_ref="session:console:test",
        payload={"command": "Get-ChildItem", "cwd": str(tmp_path)},
    )

    assert payload["success"] is True
    records = evidence_ledger.list_by_task(payload["task_id"])
    record = next(
        record
        for record in records
        if record.capability_ref == "tool:execute_shell_command"
    )
    assert record.metadata["action_mode"] == "read"
    assert record.metadata["read_only"] is True
    assert record.metadata["concurrency_class"] == "parallel-read"
    assert record.metadata["preflight_policy"] == "shell-safety"
    assert record.metadata["tool_contract"] == "tool:execute_shell_command"


def test_browser_tool_execution_hydrates_session_id_from_main_brain_runtime_request_context(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    async def _fake_browser_use(
        action: str,
        session_id: str = "",
        page_id: str = "default",
        **kwargs,
    ):
        captured.update(
            {
                "action": action,
                "session_id": session_id,
                "page_id": page_id,
                "extra": dict(kwargs),
            },
        )
        return {
            "success": True,
            "summary": f"Browser action '{action}' ran on {session_id or 'missing-session'}",
        }

    monkeypatch.setitem(
        capability_execution_module._TOOL_EXECUTORS,
        "tool:browser_use",
        _fake_browser_use,
    )
    capability_service = CapabilityService(evidence_ledger=EvidenceLedger())
    dispatcher = KernelDispatcher(capability_service=capability_service)

    payload = _execute_capability_direct(
        capability_service,
        dispatcher,
        capability_id="tool:browser_use",
        owner_agent_id="ops-agent",
        environment_ref="desktop:runtime-session",
        payload={
            "action": "snapshot",
            "request_context": {
                "session_id": "industry-chat:industry-v1-ops:execution-core",
                "main_brain_runtime": {
                    "risk_level": "guarded",
                    "environment": {
                        "ref": "desktop:runtime-session",
                        "session_id": "session:console:desktop-runtime-session",
                        "live_session_bound": True,
                        "surface_contracts": {
                            "browser_site_contract_status": "verified-writer",
                        },
                    },
                },
            },
        },
    )

    assert payload["success"] is True
    assert captured["action"] == "snapshot"
    assert captured["session_id"] == "session:console:desktop-runtime-session"


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
    assert kwargs["skip_kernel_admission"] is False
    assert kwargs["kernel_task_id"] == payload["task_id"]

    evidence = evidence_ledger.list_by_task(payload["task_id"])
    assert len(evidence) == 1
    assert evidence[0].capability_ref == "system:dispatch_query"


def test_system_dispatch_query_propagates_turn_executor_failure_status() -> None:
    class _FailingTurnExecutor:
        def __init__(self) -> None:
            self.requests: list[tuple[object, dict[str, object]]] = []

        async def stream_request(self, request, **kwargs):
            self.requests.append((request, kwargs))
            yield {
                "object": "message",
                "status": "failed",
                "error": {"message": "query runtime failed"},
                "request": request,
            }

    evidence_ledger = EvidenceLedger()
    turn_executor = _FailingTurnExecutor()
    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
        turn_executor=turn_executor,
    )
    dispatcher = KernelDispatcher(capability_service=capability_service)

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
                "session_id": "goal-2",
                "user_id": "ops-agent",
                "channel": "goal",
            },
            "mode": "final",
            "dispatch_events": False,
        },
    )

    assert payload["success"] is False
    assert payload["phase"] == "failed"
    assert payload["error"] == "query runtime failed"


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
                id="system:apply_role",
                name="apply_role",
                summary="Apply a role.",
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
                title="Apply role",
                capability_ref="system:apply_role",
                owner_agent_id="guest-agent",
                payload={},
            ),
        ),
    )
    assert execution_result["success"] is False
    assert "not authorized" in execution_result["error"]


def test_system_dispatch_goal_capability_is_retired(
    tmp_path,
) -> None:
    capability_service = CapabilityService()

    execution_result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                id="task-system-dispatch-goal",
                title="Dispatch goal",
                capability_ref="system:dispatch_goal",
                owner_agent_id="copaw-scheduler",
                payload={
                    "goal_id": "goal-1",
                    "execute": False,
                    "context": {"source": "automation:dispatch_active_goals"},
                },
            ),
        ),
    )

    assert execution_result["success"] is False
    assert "not found" in execution_result["error"]


def test_system_dispatch_goal_manual_execution_is_retired(
    tmp_path,
) -> None:
    capability_service = CapabilityService()

    execution_result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                id="task-system-dispatch-goal-manual",
                title="Dispatch goal",
                capability_ref="system:dispatch_goal",
                owner_agent_id="copaw-operator",
                payload={
                    "goal_id": "goal-1",
                    "execute": False,
                },
            ),
        ),
    )

    assert execution_result["success"] is False
    assert "not found" in execution_result["error"]


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
                schedule_summaries=[{"schedule_id": "schedule-1"}],
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


def test_supported_service_donor_rejects_raw_shell_payload(tmp_path) -> None:
    config = Config(
        external_capability_packages={
            "runtime:flask": ExternalCapabilityPackageConfig(
                capability_id="runtime:flask",
                name="flask",
                summary="Flask runtime component",
                kind="runtime-component",
                source_kind="runtime",
                source_url="https://github.com/pallets/flask",
                package_ref="git+https://github.com/pallets/flask.git",
                package_kind="git-repo",
                enabled=True,
                execute_command="python -m flask run",
                healthcheck_command="python -m flask --version",
                runtime_kind="service",
                supported_actions=[
                    "describe",
                    "start",
                    "healthcheck",
                    "stop",
                    "restart",
                ],
                scope_policy="session",
                ready_probe_kind="command",
                ready_probe_config={"command": "python -m flask --version"},
                stop_strategy="terminate",
                startup_entry_ref="module:flask",
                environment_requirements=["process", "network"],
                evidence_contract=["shell-command", "runtime-event"],
            ),
        },
    )
    capability_service = _build_external_runtime_capability_service(
        tmp_path,
        config=config,
    )

    result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                id="task-runtime-flask-start",
                title="Start flask",
                capability_ref="runtime:flask",
                owner_agent_id="copaw-agent-runner",
                payload={
                    "action": "start",
                    "session_mount_id": "session-1",
                    "command": "python -m flask run --weird-shell-override",
                },
            ),
        ),
    )

    assert result["success"] is False
    assert "typed runtime action" in str(result["error"])


def test_service_healthcheck_requires_runtime_id(tmp_path) -> None:
    config = Config(
        external_capability_packages={
            "runtime:flask": ExternalCapabilityPackageConfig(
                capability_id="runtime:flask",
                name="flask",
                summary="Flask runtime component",
                kind="runtime-component",
                source_kind="runtime",
                source_url="https://github.com/pallets/flask",
                package_ref="git+https://github.com/pallets/flask.git",
                package_kind="git-repo",
                enabled=True,
                execute_command="python -m flask run",
                healthcheck_command="python -m flask --version",
                runtime_kind="service",
                supported_actions=[
                    "describe",
                    "start",
                    "healthcheck",
                    "stop",
                    "restart",
                ],
                scope_policy="session",
                ready_probe_kind="command",
                ready_probe_config={"command": "python -m flask --version"},
                stop_strategy="terminate",
                startup_entry_ref="module:flask",
                environment_requirements=["process", "network"],
                evidence_contract=["shell-command", "runtime-event"],
            ),
        },
    )
    capability_service = _build_external_runtime_capability_service(
        tmp_path,
        config=config,
    )

    result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                id="task-runtime-flask-health",
                title="Healthcheck flask",
                capability_ref="runtime:flask",
                owner_agent_id="copaw-agent-runner",
                payload={"action": "healthcheck"},
            ),
        ),
    )

    assert result["success"] is False
    assert "runtime_id" in str(result["error"])


def test_service_healthcheck_marks_missing_process_orphaned(tmp_path, monkeypatch) -> None:
    config = Config(
        external_capability_packages={
            "runtime:openspace": ExternalCapabilityPackageConfig(
                capability_id="runtime:openspace",
                name="openspace",
                summary="OpenSpace runtime component",
                kind="runtime-component",
                source_kind="runtime",
                source_url="https://github.com/HKUDS/OpenSpace",
                package_ref="git+https://github.com/HKUDS/OpenSpace.git",
                package_kind="git-repo",
                enabled=True,
                execute_command="openspace",
                healthcheck_command="openspace --help",
                runtime_kind="service",
                supported_actions=[
                    "describe",
                    "start",
                    "healthcheck",
                    "stop",
                    "restart",
                ],
                scope_policy="session",
                ready_probe_kind="http",
                ready_probe_config={"url": "http://127.0.0.1:8080/health"},
                stop_strategy="terminate",
                startup_entry_ref="script:openspace",
                environment_requirements=["process", "network"],
                evidence_contract=["shell-command", "runtime-event"],
            ),
        },
    )
    capability_service = _build_external_runtime_capability_service(
        tmp_path,
        config=config,
    )
    runtime_service = capability_service._external_runtime_service
    runtime = runtime_service.create_or_reuse_service_runtime(
        capability_id="runtime:openspace",
        scope_kind="session",
        session_mount_id="session-1",
        owner_agent_id="copaw-agent-runner",
        command="openspace",
    )
    runtime_service.update_runtime(runtime.runtime_id, process_id=4242)
    monkeypatch.setattr(
        "copaw.capabilities.external_runtime_execution._process_exists",
        lambda pid: False,
    )

    result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                id="task-runtime-openspace-health",
                title="Healthcheck openspace",
                capability_ref="runtime:openspace",
                owner_agent_id="copaw-agent-runner",
                payload={
                    "action": "healthcheck",
                    "runtime_id": runtime.runtime_id,
                },
            ),
        ),
    )

    updated = runtime_service.get_runtime(runtime.runtime_id)
    assert result["success"] is False
    assert result["output"]["status"] == "orphaned"
    assert updated is not None
    assert updated.status == "orphaned"


def test_service_start_preserves_orphaned_when_process_exits_before_ready(
    tmp_path,
    monkeypatch,
) -> None:
    config = Config(
        external_capability_packages={
            "runtime:openspace": ExternalCapabilityPackageConfig(
                capability_id="runtime:openspace",
                name="openspace",
                summary="OpenSpace runtime component",
                kind="runtime-component",
                source_kind="runtime",
                source_url="https://github.com/HKUDS/OpenSpace",
                package_ref="git+https://github.com/HKUDS/OpenSpace.git",
                package_kind="git-repo",
                enabled=True,
                execute_command="openspace",
                healthcheck_command="openspace --help",
                runtime_kind="service",
                supported_actions=[
                    "describe",
                    "start",
                    "healthcheck",
                    "stop",
                    "restart",
                ],
                scope_policy="session",
                ready_probe_kind="http",
                ready_probe_config={"url": "http://127.0.0.1:8080/health"},
                stop_strategy="terminate",
                startup_entry_ref="script:openspace",
                environment_requirements=["process", "network"],
                evidence_contract=["shell-command", "runtime-event"],
            ),
        },
    )
    capability_service = _build_external_runtime_capability_service(
        tmp_path,
        config=config,
    )
    runtime_service = capability_service._external_runtime_service
    monkeypatch.setattr(
        "copaw.capabilities.external_runtime_execution._spawn_process",
        lambda command: (4242, None),
    )
    monkeypatch.setattr(
        "copaw.capabilities.external_runtime_execution._process_exists",
        lambda pid: False,
    )

    result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                id="task-runtime-openspace-start",
                title="Start openspace",
                capability_ref="runtime:openspace",
                owner_agent_id="copaw-agent-runner",
                payload={
                    "action": "start",
                    "session_mount_id": "session-1",
                },
            ),
        ),
    )

    runtime_id = result["output"]["runtime_id"]
    updated = runtime_service.get_runtime(runtime_id)
    assert result["success"] is False
    assert result["output"]["status"] == "orphaned"
    assert updated is not None
    assert updated.status == "orphaned"


def test_service_start_waits_until_runtime_is_ready(
    tmp_path,
    monkeypatch,
) -> None:
    config = Config(
        external_capability_packages={
            "runtime:openspace": ExternalCapabilityPackageConfig(
                capability_id="runtime:openspace",
                name="openspace",
                summary="OpenSpace runtime component",
                kind="runtime-component",
                source_kind="runtime",
                source_url="https://github.com/HKUDS/OpenSpace",
                package_ref="git+https://github.com/HKUDS/OpenSpace.git",
                package_kind="git-repo",
                enabled=True,
                execute_command="openspace-dashboard --port 7788",
                healthcheck_command="openspace-dashboard --help",
                runtime_kind="service",
                supported_actions=[
                    "describe",
                    "start",
                    "healthcheck",
                    "stop",
                    "restart",
                ],
                scope_policy="session",
                ready_probe_kind="http",
                ready_probe_config={
                    "url": "http://127.0.0.1:7788/health",
                    "predicted_default_port": 7788,
                    "predicted_health_path": "/health",
                    "startup_timeout_sec": 0.05,
                    "probe_interval_sec": 0.0,
                },
                stop_strategy="terminate",
                startup_entry_ref="script:openspace-dashboard",
                environment_requirements=["process", "network"],
                evidence_contract=["shell-command", "runtime-event"],
            ),
        },
    )
    capability_service = _build_external_runtime_capability_service(
        tmp_path,
        config=config,
    )
    runtime_service = capability_service._external_runtime_service
    attempts = {"count": 0}

    monkeypatch.setattr(
        "copaw.capabilities.external_runtime_execution._spawn_process",
        lambda command: (4242, None),
    )
    monkeypatch.setattr(
        "copaw.capabilities.external_runtime_execution._process_exists",
        lambda pid: True,
    )

    def _fake_http_check(url: str, timeout: float) -> tuple[bool, str]:
        _ = (url, timeout)
        attempts["count"] += 1
        if attempts["count"] < 2:
            return False, "Connection refused"
        return True, "HTTP readiness probe succeeded (200)"

    monkeypatch.setattr(
        "copaw.capabilities.external_runtime_execution._http_check",
        _fake_http_check,
    )

    result = asyncio.run(
        capability_service.execute_task(
            KernelTask(
                id="task-runtime-openspace-start-ready",
                title="Start openspace dashboard",
                capability_ref="runtime:openspace",
                owner_agent_id="copaw-agent-runner",
                payload={
                    "action": "start",
                    "session_mount_id": "session-1",
                },
            ),
        ),
    )

    runtime_id = result["output"]["runtime_id"]
    updated = runtime_service.get_runtime(runtime_id)
    assert result["success"] is True
    assert attempts["count"] >= 2
    assert updated is not None
    assert updated.status == "ready"


def test_adapter_capability_executes_compiled_action_through_mcp_transport() -> None:
    config = Config(
        external_capability_packages={
            "adapter:openspace": ExternalCapabilityPackageConfig(
                capability_id="adapter:openspace",
                name="openspace",
                summary="OpenSpace adapter",
                kind="adapter",
                source_kind="adapter",
                source_url="https://github.com/HKUDS/OpenSpace",
                package_ref="git+https://github.com/HKUDS/OpenSpace.git",
                package_kind="git-repo",
                enabled=True,
                execution_mode="shell",
                runtime_kind=None,
                supported_actions=[],
                scope_policy="seat",
                ready_probe_kind="none",
                stop_strategy="terminate",
                startup_entry_ref="script:openspace-mcp",
                intake_protocol_kind="native_mcp",
                call_surface_ref="mcp:openspace",
                adapter_contract={
                    "compiled_adapter_id": "adapter:openspace",
                    "transport_kind": "mcp",
                    "call_surface_ref": "mcp:openspace",
                    "actions": [
                        {
                            "action_id": "execute_task",
                            "transport_action_ref": "execute_task",
                            "input_schema": {"type": "object"},
                            "output_schema": {},
                        },
                    ],
                },
            ),
        },
    )

    with (
        patch("copaw.capabilities.service.load_config", return_value=config),
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config", return_value=config),
        patch(
            "copaw.capabilities.sources.external_packages.load_config",
            return_value=config,
        ),
    ):
        service = CapabilityService(mcp_manager=FakeMCPManager())
        result = asyncio.run(
            service.execute_task(
                KernelTask(
                    id="task-external-adapter",
                    title="Execute adapter action",
                    capability_ref="adapter:openspace",
                    owner_agent_id="copaw-operator",
                    payload={"action": "execute_task", "task": "hello"},
                ),
            ),
    )

    assert result["success"] is True
    assert result["capability_id"] == "adapter:openspace"
    assert result["output"]["adapter_action"] == "execute_task"
    assert result["output"]["transport_kind"] == "mcp"


def test_runtime_only_capability_rejects_business_adapter_action() -> None:
    config = Config(
        external_capability_packages={
            "runtime:flask": ExternalCapabilityPackageConfig(
                capability_id="runtime:flask",
                name="flask",
                summary="Flask runtime component",
                kind="runtime-component",
                source_kind="runtime",
                source_url="https://github.com/pallets/flask",
                package_ref="git+https://github.com/pallets/flask.git",
                package_kind="git-repo",
                enabled=True,
                execution_mode="shell",
                execute_command='python -m flask --version',
                healthcheck_command='python -m flask --version',
                runtime_kind="service",
                supported_actions=["describe", "start", "healthcheck", "stop", "restart"],
                scope_policy="session",
                ready_probe_kind="command",
                stop_strategy="terminate",
                startup_entry_ref="module:flask",
            ),
        },
    )

    with (
        patch("copaw.capabilities.service.load_config", return_value=config),
        patch("copaw.capabilities.service.save_config"),
        patch("copaw.capabilities.sources.mcp.load_config", return_value=config),
        patch(
            "copaw.capabilities.sources.external_packages.load_config",
            return_value=config,
        ),
    ):
        service = CapabilityService()
        result = asyncio.run(
            service.execute_task(
                KernelTask(
                    id="task-runtime-only",
                    title="Execute unsupported adapter action",
                    capability_ref="runtime:flask",
                    owner_agent_id="copaw-operator",
                    payload={"action": "execute_task"},
                ),
            ),
        )

    assert result["success"] is False
    assert "formal adapter" in result["summary"].lower()
