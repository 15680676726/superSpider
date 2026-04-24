# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers import runtime_center_actor_capabilities as runtime_center_actor_capabilities_module
from copaw.app.routers import runtime_center_dependencies as runtime_center_dependencies_module
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.capabilities import CapabilityService
from copaw.evidence import EvidenceLedger
from copaw.kernel import KernelDispatcher
from copaw.kernel.agent_profile_service import AgentProfileService
from copaw.kernel.persistence import KernelTaskStore
from copaw.state import (
    ExecutorRuntimeService,
    SQLiteStateStore,
)
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteAgentProfileOverrideRepository,
    SqliteRuntimeFrameRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


def test_runtime_center_dependencies_drop_legacy_actor_service_getters() -> None:
    assert not hasattr(runtime_center_dependencies_module, "_get_actor_mailbox_service")
    assert not hasattr(runtime_center_dependencies_module, "_get_actor_supervisor")
    assert not hasattr(runtime_center_dependencies_module, "_get_agent_checkpoint_repository")


def test_runtime_center_agent_capability_helpers_drop_require_actor_flag() -> None:
    assert "require_actor" not in inspect.signature(
        runtime_center_actor_capabilities_module._assign_agent_capabilities,
    ).parameters
    assert "require_actor" not in inspect.signature(
        runtime_center_actor_capabilities_module._submit_governed_capabilities,
    ).parameters


def test_runtime_center_actor_fixture_drops_legacy_actor_state(tmp_path) -> None:
    app, _item = _build_actor_app(tmp_path)

    assert not hasattr(app.state, "actor_mailbox_service")
    assert not hasattr(app.state, "actor_supervisor")
    assert not hasattr(app.state, "agent_runtime_repository")
    assert not hasattr(app.state, "agent_mailbox_repository")
    assert not hasattr(app.state, "agent_lease_repository")
    assert not hasattr(app.state, "agent_thread_binding_repository")


def _build_actor_app(tmp_path):
    state_store = SQLiteStateStore(tmp_path / "actor-state.db")
    override_repository = SqliteAgentProfileOverrideRepository(state_store)
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    executor_runtime_service = ExecutorRuntimeService(state_store=state_store)
    for assignment_id, role_id, agent_id, display_name, role_name in (
        ("assignment-operator", "operator", "agent-1", "Ops Agent", "Operations"),
        ("assignment-research", "research", "agent-2", "Research Agent", "Research"),
    ):
        runtime = executor_runtime_service.create_or_reuse_runtime(
            executor_id="codex",
            protocol_kind="app_server",
            scope_kind="assignment",
            assignment_id=assignment_id,
            role_id=role_id,
            thread_id=f"industry-chat:industry-v1-ops:{role_id}",
            metadata={
                "owner_agent_id": agent_id,
                "display_name": display_name,
                "role_name": role_name,
                "industry_instance_id": "industry-v1-ops",
                "industry_role_id": role_id,
                "desired_state": "active",
                "continuity": {
                    "control_thread_id": f"industry-chat:industry-v1-ops:{role_id}",
                    "session_id": f"industry-chat:industry-v1-ops:{role_id}",
                },
            },
        )
        executor_runtime_service.mark_runtime_ready(
            runtime.runtime_id,
            thread_id=f"industry-chat:industry-v1-ops:{role_id}",
            metadata={
                "owner_agent_id": agent_id,
                "display_name": display_name,
                "role_name": role_name,
                "industry_instance_id": "industry-v1-ops",
                "industry_role_id": role_id,
                "desired_state": "active",
                "continuity": {
                    "control_thread_id": f"industry-chat:industry-v1-ops:{role_id}",
                    "session_id": f"industry-chat:industry-v1-ops:{role_id}",
                },
            },
        )

    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(evidence_ledger=evidence_ledger)
    agent_profile_service = AgentProfileService(
        override_repository=override_repository,
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        executor_runtime_service=executor_runtime_service,
        decision_request_repository=decision_request_repository,
        capability_service=capability_service,
    )
    capability_service.set_agent_profile_service(agent_profile_service)
    capability_service.set_agent_profile_override_repository(override_repository)
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    dispatcher = KernelDispatcher(
        capability_service=capability_service,
        task_store=task_store,
    )

    app = FastAPI()
    app.include_router(runtime_center_router)
    app.state.executor_runtime_service = executor_runtime_service
    app.state.agent_profile_override_repository = override_repository
    app.state.task_repository = task_repository
    app.state.task_runtime_repository = task_runtime_repository
    app.state.runtime_frame_repository = runtime_frame_repository
    app.state.decision_request_repository = decision_request_repository
    app.state.agent_profile_service = agent_profile_service
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = dispatcher
    return app, SimpleNamespace(id="retired-actor-mailbox-item")


def _list_lifecycle_kernel_tasks(app: FastAPI) -> list[object]:
    task_store = app.state.kernel_dispatcher.task_store
    return [
        task
        for task in task_store.list_tasks(limit=50)
        if getattr(task, "capability_ref", None) == "system:apply_capability_lifecycle"
    ]


def test_runtime_center_actor_routes_are_retired(tmp_path) -> None:
    app, _item = _build_actor_app(tmp_path)
    client = TestClient(app)

    assert client.get("/runtime-center/actors").status_code == 404
    assert client.get("/runtime-center/actors/agent-1").status_code == 404


def test_runtime_center_actor_mutation_routes_are_retired(tmp_path) -> None:
    app, item = _build_actor_app(tmp_path)
    client = TestClient(app)

    pause_response = client.post(
        "/runtime-center/actors/agent-1/pause",
        json={"reason": "manual hold"},
    )
    resume_response = client.post("/runtime-center/actors/agent-1/resume")
    retry_response = client.post(f"/runtime-center/actors/agent-1/retry/{item.id}")
    cancel_response = client.post(
        "/runtime-center/actors/agent-1/cancel",
        json={"task_id": "task-1"},
    )
    assign_capabilities_response = client.put(
        "/runtime-center/actors/agent-1/capabilities",
        json={
            "capabilities": ["tool:send_file_to_user"],
            "mode": "replace",
        },
    )
    govern_capabilities_response = client.post(
        "/runtime-center/actors/agent-1/capabilities/governed",
        json={
            "capabilities": ["tool:send_file_to_user"],
            "mode": "replace",
        },
    )

    assert pause_response.status_code == 404
    assert resume_response.status_code == 404
    assert retry_response.status_code == 404
    assert cancel_response.status_code == 404
    assert assign_capabilities_response.status_code == 404
    assert govern_capabilities_response.status_code == 404


def test_runtime_center_actor_capability_assignment_route_uses_agent_surface(tmp_path) -> None:
    app, _item = _build_actor_app(tmp_path)
    client = TestClient(app)

    response = client.put(
        "/runtime-center/agents/agent-1/capabilities",
        json={
            "capabilities": ["tool:send_file_to_user"],
            "mode": "replace",
            "reason": "actor runtime capability assignment",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated"] is True
    assert payload["agent"]["agent_id"] == "agent-1"
    assert "tool:send_file_to_user" in payload["agent"]["capabilities"]
    assert "system:dispatch_query" in payload["agent"]["capabilities"]
    assert payload["runtime"]["routes"] == {
        "agent_capabilities": "/api/runtime-center/agents/agent-1/capabilities",
    }
    assert payload["runtime"]["agent_capabilities_route"] == "/api/runtime-center/agents/agent-1/capabilities"

    override = app.state.agent_profile_override_repository.get_override("agent-1")
    assert override is not None
    assert override.name == "Ops Agent"
    assert override.role_name == "Operations"
    assert "tool:send_file_to_user" in (override.capabilities or [])
    assert "system:dispatch_query" in (override.capabilities or [])

    accessible = {
        mount.id
        for mount in app.state.capability_service.list_accessible_capabilities(
            agent_id="agent-1",
            enabled_only=True,
        )
    }
    assert "tool:send_file_to_user" in accessible
    assert "system:dispatch_query" in accessible
    lifecycle_tasks = _list_lifecycle_kernel_tasks(app)
    assert len(lifecycle_tasks) == 1
    assert lifecycle_tasks[0].payload["target_agent_id"] == "agent-1"
    assert app.state.task_repository.list_tasks(task_type="system:apply_role") == []


def test_runtime_center_agent_capability_assignment_uses_executor_runtime_when_actor_runtime_missing(
    tmp_path,
) -> None:
    app, _item = _build_actor_app(tmp_path)
    executor_runtime_service = ExecutorRuntimeService(
        state_store=SQLiteStateStore(tmp_path / "actor-capability-executor.db"),
    )
    runtime = executor_runtime_service.create_or_reuse_runtime(
        executor_id="codex",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assign-agent-1",
        role_id="operator",
        thread_id="industry-chat:industry-v1-ops:operator",
        metadata={"owner_agent_id": "agent-1"},
        continuity_metadata={
            "control_thread_id": "industry-chat:industry-v1-ops:operator",
        },
    )
    executor_runtime_service.mark_runtime_ready(
        runtime.runtime_id,
        thread_id="industry-chat:industry-v1-ops:operator",
        metadata={"owner_agent_id": "agent-1"},
    )
    app.state.executor_runtime_service = executor_runtime_service
    client = TestClient(app)

    response = client.put(
        "/runtime-center/agents/agent-1/capabilities",
        json={
            "capabilities": ["tool:send_file_to_user"],
            "mode": "replace",
            "reason": "executor runtime capability assignment",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated"] is True
    assert payload["runtime"]["kind"] == "executor-runtime"
    assert payload["runtime"]["runtime_id"] == runtime.runtime_id
    assert payload["runtime"]["status"] == "ready"
    assert payload["runtime"]["formal_surface"] is True
    assert payload["runtime"]["routes"] == {
        "agent_capabilities": "/api/runtime-center/agents/agent-1/capabilities",
    }
    assert payload["runtime"]["agent_capabilities_route"] == "/api/runtime-center/agents/agent-1/capabilities"


def test_runtime_center_actor_capability_surface_and_governed_assignment(tmp_path) -> None:
    app, _item = _build_actor_app(tmp_path)
    client = TestClient(app)

    surface_response = client.get("/runtime-center/agents/agent-1/capabilities")
    assert surface_response.status_code == 200
    surface = surface_response.json()
    assert surface["agent_id"] == "agent-1"
    assert surface["default_mode"] == "governed"
    assert "system:dispatch_query" in surface["baseline_capabilities"]
    assert surface["routes"]["governed_assign"] == "/api/runtime-center/agents/agent-1/capabilities/governed"
    assert "actor_detail" not in surface["routes"]

    govern_response = client.post(
        "/runtime-center/agents/agent-1/capabilities/governed",
        json={
            "capabilities": ["tool:send_file_to_user"],
            "mode": "replace",
            "reason": "submit governed capability change",
        },
    )
    assert govern_response.status_code == 200
    governed = govern_response.json()
    assert governed["submitted"] is True
    assert governed["updated"] is True
    assert governed["result"]["phase"] == "completed"
    decision = governed["decision"]
    assert decision is not None
    assert decision["status"] == "approved"
    assert decision["task_id"]
    assert decision["requested_by"] == "copaw-main-brain"

    refreshed_surface = client.get("/runtime-center/agents/agent-1/capabilities")
    assert refreshed_surface.status_code == 200
    refreshed_payload = refreshed_surface.json()
    assert refreshed_payload["pending_decisions"] == []
    assert "actor_detail" not in refreshed_payload["routes"]
    assert "tool:send_file_to_user" in refreshed_payload["effective_capabilities"]
    lifecycle_tasks = _list_lifecycle_kernel_tasks(app)
    assert len(lifecycle_tasks) == 1
    assert lifecycle_tasks[0].payload["target_agent_id"] == "agent-1"
    assert app.state.task_repository.list_tasks(task_type="system:apply_role") == []


def test_runtime_center_agent_capability_assignment_route_for_execution_core(tmp_path) -> None:
    app, _item = _build_actor_app(tmp_path)
    client = TestClient(app)

    response = client.put(
        "/runtime-center/agents/copaw-agent-runner/capabilities",
        json={
            "capabilities": ["tool:send_file_to_user"],
            "mode": "merge",
            "reason": "runtime center execution-core merge",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated"] is True
    assert payload["agent"]["agent_id"] == "copaw-agent-runner"
    assert "system:dispatch_query" in payload["agent"]["capabilities"]
    assert "system:dispatch_goal" not in payload["agent"]["capabilities"]
    assert "system:dispatch_active_goals" not in payload["agent"]["capabilities"]
    assert "system:discover_capabilities" in payload["agent"]["capabilities"]
    assert "tool:send_file_to_user" not in payload["agent"]["capabilities"]
    assert payload["runtime"] is None

    profile = app.state.agent_profile_service.get_agent("copaw-agent-runner")
    assert profile is not None
    assert "system:dispatch_goal" not in profile.capabilities
    assert "system:discover_capabilities" in profile.capabilities
    assert "tool:send_file_to_user" not in profile.capabilities
    lifecycle_tasks = _list_lifecycle_kernel_tasks(app)
    assert len(lifecycle_tasks) == 1
    assert lifecycle_tasks[0].payload["target_agent_id"] == "copaw-agent-runner"
    assert app.state.task_repository.list_tasks(task_type="system:apply_role") == []


def test_runtime_center_agent_governed_capability_assignment_route_for_execution_core(tmp_path) -> None:
    app, _item = _build_actor_app(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/runtime-center/agents/copaw-agent-runner/capabilities/governed",
        json={
            "capabilities": ["tool:send_file_to_user"],
            "mode": "merge",
            "reason": "govern execution core capability change",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["submitted"] is True
    assert payload["updated"] is True
    assert payload["result"]["phase"] == "completed"
    assert payload["decision"]["status"] == "approved"
    assert payload["decision"]["requested_by"] == "copaw-main-brain"
    assert payload["capability_surface"]["default_mode"] == "governed"
    lifecycle_tasks = _list_lifecycle_kernel_tasks(app)
    assert len(lifecycle_tasks) == 1
    assert lifecycle_tasks[0].payload["target_agent_id"] == "copaw-agent-runner"
    assert app.state.task_repository.list_tasks(task_type="system:apply_role") == []
