# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.capabilities import CapabilityService
from copaw.evidence import EvidenceLedger
from copaw.kernel import ActorMailboxService, KernelDispatcher
from copaw.kernel.agent_profile_service import AgentProfileService
from copaw.kernel.persistence import KernelTaskStore
from copaw.state import (
    AgentLeaseRecord,
    AgentRuntimeRecord,
    AgentThreadBindingRecord,
    SQLiteStateStore,
)
from copaw.state.repositories import (
    SqliteAgentCheckpointRepository,
    SqliteDecisionRequestRepository,
    SqliteAgentLeaseRepository,
    SqliteAgentMailboxRepository,
    SqliteAgentProfileOverrideRepository,
    SqliteAgentRuntimeRepository,
    SqliteAgentThreadBindingRepository,
    SqliteRuntimeFrameRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


class FakeActorSupervisor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def run_agent_once(self, agent_id: str) -> bool:
        self.calls.append(agent_id)
        return True


def _build_actor_app(tmp_path):
    state_store = SQLiteStateStore(tmp_path / "actor-state.db")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    mailbox_repository = SqliteAgentMailboxRepository(state_store)
    checkpoint_repository = SqliteAgentCheckpointRepository(state_store)
    lease_repository = SqliteAgentLeaseRepository(state_store)
    thread_binding_repository = SqliteAgentThreadBindingRepository(state_store)
    override_repository = SqliteAgentProfileOverrideRepository(state_store)
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)

    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry-v1-ops:operator",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            display_name="Ops Agent",
            role_name="Operations",
        ),
    )
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-2",
            actor_key="industry-v1-ops:research",
            actor_fingerprint="fp-agent-2",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="research",
            display_name="Research Agent",
            role_name="Research",
        ),
    )

    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
        thread_binding_repository=thread_binding_repository,
    )
    supervisor = FakeActorSupervisor()

    item = mailbox_service.enqueue_item(
        agent_id="agent-1",
        task_id="task-1",
        source_agent_id="agent-2",
        title="Prepare operator brief",
        summary="Collect the latest operator backlog and summarize it.",
        capability_ref="system:dispatch_query",
        conversation_thread_id="agent-chat:agent-1",
        payload={"query": "Summarize the operator backlog."},
        metadata={"origin": "seed"},
    )
    mailbox_service.create_checkpoint(
        agent_id="agent-1",
        mailbox_id=item.id,
        task_id="task-1",
        checkpoint_kind="worker-step",
        status="ready",
        phase="queued",
        conversation_thread_id="agent-chat:agent-1",
        summary="Mailbox item seeded for actor runtime API tests.",
    )
    lease_repository.upsert_lease(
        AgentLeaseRecord(
            agent_id="agent-1",
            lease_kind="actor-runtime",
            resource_ref="actor-runtime:agent-1",
            owner="copaw-actor-worker",
            lease_token="lease-1",
        ),
    )
    thread_binding_repository.upsert_binding(
        AgentThreadBindingRecord(
            thread_id="agent-chat:agent-1",
            agent_id="agent-1",
            session_id="agent-chat:agent-1",
            channel="console",
            binding_kind="agent-primary",
            industry_instance_id="industry-v1-ops",
            industry_role_id="operator",
            owner_scope="ops",
            metadata={"agent_name": "Ops Agent", "role_name": "Operations"},
        ),
    )
    thread_binding_repository.upsert_binding(
        AgentThreadBindingRecord(
            thread_id="agent-chat:agent-2",
            agent_id="agent-2",
            session_id="agent-chat:agent-2",
            channel="console",
            binding_kind="agent-primary",
            industry_instance_id="industry-v1-ops",
            industry_role_id="research",
            owner_scope="ops",
            metadata={"agent_name": "Research Agent", "role_name": "Research"},
        ),
    )

    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(evidence_ledger=evidence_ledger)
    agent_profile_service = AgentProfileService(
        override_repository=override_repository,
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        agent_runtime_repository=runtime_repository,
        agent_mailbox_repository=mailbox_repository,
        agent_checkpoint_repository=checkpoint_repository,
        agent_lease_repository=lease_repository,
        agent_thread_binding_repository=thread_binding_repository,
        decision_request_repository=decision_request_repository,
        capability_service=capability_service,
    )
    capability_service.set_agent_profile_service(agent_profile_service)
    capability_service.set_agent_profile_override_repository(override_repository)
    capability_service.set_actor_mailbox_service(mailbox_service)
    capability_service.set_actor_supervisor(supervisor)
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
    app.state.agent_runtime_repository = runtime_repository
    app.state.agent_mailbox_repository = mailbox_repository
    app.state.agent_checkpoint_repository = checkpoint_repository
    app.state.agent_lease_repository = lease_repository
    app.state.agent_thread_binding_repository = thread_binding_repository
    app.state.agent_profile_override_repository = override_repository
    app.state.task_repository = task_repository
    app.state.task_runtime_repository = task_runtime_repository
    app.state.runtime_frame_repository = runtime_frame_repository
    app.state.decision_request_repository = decision_request_repository
    app.state.agent_profile_service = agent_profile_service
    app.state.actor_mailbox_service = mailbox_service
    app.state.actor_supervisor = supervisor
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = dispatcher
    return app, mailbox_service, supervisor, item


def test_runtime_center_actor_read_routes(tmp_path) -> None:
    app, _mailbox_service, _supervisor, item = _build_actor_app(tmp_path)
    client = TestClient(app)

    list_response = client.get("/runtime-center/actors")
    assert list_response.status_code == 200
    actors = list_response.json()
    assert len(actors) == 2
    assert actors[0]["routes"]["detail"].startswith("/api/runtime-center/actors/")

    detail_response = client.get("/runtime-center/actors/agent-1")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["runtime"]["agent_id"] == "agent-1"
    assert detail["capability_surface"]["default_mode"] == "governed"
    assert "system:dispatch_query" in detail["capability_surface"]["recommended_capabilities"]
    assert detail["stats"]["mailbox_count"] == 1
    assert detail["stats"]["checkpoint_count"] == 1
    assert detail["stats"]["lease_count"] == 1
    assert detail["stats"]["binding_count"] == 1
    assert detail["teammates"][0]["agent_id"] == "agent-2"
    assert detail["focus"]["task_id"] == "task-1"

    mailbox_response = client.get("/runtime-center/actors/agent-1/mailbox")
    assert mailbox_response.status_code == 200
    mailbox_payload = mailbox_response.json()
    assert mailbox_payload[0]["id"] == item.id
    assert mailbox_payload[0]["route"].endswith(item.id)

    mailbox_detail = client.get(f"/runtime-center/actors/agent-1/mailbox/{item.id}")
    assert mailbox_detail.status_code == 200
    assert mailbox_detail.json()["conversation_thread_id"] == "agent-chat:agent-1"

    checkpoints_response = client.get("/runtime-center/actors/agent-1/checkpoints")
    assert checkpoints_response.status_code == 200
    assert checkpoints_response.json()[0]["phase"] == "queued"

    leases_response = client.get("/runtime-center/actors/agent-1/leases")
    assert leases_response.status_code == 200
    assert leases_response.json()[0]["resource_ref"] == "actor-runtime:agent-1"

    teammates_response = client.get("/runtime-center/actors/agent-1/teammates")
    assert teammates_response.status_code == 200
    assert teammates_response.json()[0]["thread_bindings"][0]["thread_id"] == "agent-chat:agent-2"


def test_runtime_center_actor_focus_ignores_terminal_history(tmp_path) -> None:
    app, _mailbox_service, _supervisor, item = _build_actor_app(tmp_path)
    client = TestClient(app)

    mailbox_repository = app.state.agent_mailbox_repository
    checkpoint_repository = app.state.agent_checkpoint_repository
    runtime_repository = app.state.agent_runtime_repository

    mailbox_item = mailbox_repository.get_item(item.id)
    assert mailbox_item is not None
    mailbox_item.status = "completed"
    mailbox_item.completed_at = datetime.now(timezone.utc)
    mailbox_repository.upsert_item(mailbox_item)

    checkpoint = checkpoint_repository.list_checkpoints(agent_id="agent-1", limit=1)[0]
    checkpoint.status = "applied"
    checkpoint_repository.upsert_checkpoint(checkpoint)

    runtime = runtime_repository.get_runtime("agent-1")
    assert runtime is not None
    runtime.current_task_id = None
    runtime.current_mailbox_id = None
    runtime.last_checkpoint_id = checkpoint.id
    runtime.queue_depth = 0
    runtime_repository.upsert_runtime(runtime)

    detail_response = client.get("/runtime-center/actors/agent-1")
    assert detail_response.status_code == 200
    assert detail_response.json()["focus"] is None


def test_runtime_center_actor_control_routes(tmp_path) -> None:
    app, mailbox_service, supervisor, item = _build_actor_app(tmp_path)
    client = TestClient(app)

    pause_response = client.post(
        "/runtime-center/actors/agent-1/pause",
        json={"reason": "manual hold"},
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["paused"] is True
    assert pause_response.json()["runtime"]["desired_state"] == "paused"
    assert pause_response.json()["runtime"]["runtime_status"] == "paused"

    resume_response = client.post("/runtime-center/actors/agent-1/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["resumed"] is True
    assert resume_response.json()["runtime"]["desired_state"] == "active"
    assert resume_response.json()["runtime"]["runtime_status"] == "queued"
    assert supervisor.calls == ["agent-1"]

    mailbox_service.fail_item(
        item.id,
        error_summary="Need operator retry.",
        retryable=False,
        task_id="task-1",
    )
    retry_response = client.post(f"/runtime-center/actors/agent-1/retry/{item.id}")
    assert retry_response.status_code == 200
    assert retry_response.json()["retried"] is True
    assert retry_response.json()["mailbox"]["status"] == "queued"
    assert retry_response.json()["runtime"]["queue_depth"] == 1
    assert supervisor.calls == ["agent-1", "agent-1"]

    cancel_response = client.post(
        "/runtime-center/actors/agent-1/cancel",
        json={"task_id": "task-1"},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["cancelled"] is True
    assert cancel_response.json()["result"]["output"]["cancelled_mailbox_ids"] == [item.id]
    assert cancel_response.json()["runtime"]["queue_depth"] == 0


def test_runtime_center_actor_capability_assignment_route(tmp_path) -> None:
    app, _mailbox_service, _supervisor, _item = _build_actor_app(tmp_path)
    client = TestClient(app)

    response = client.put(
        "/runtime-center/actors/agent-1/capabilities",
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
    assert payload["runtime"]["routes"]["capabilities"] == "/api/runtime-center/actors/agent-1/capabilities"

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


def test_runtime_center_actor_capability_surface_and_governed_assignment(tmp_path) -> None:
    app, _mailbox_service, _supervisor, _item = _build_actor_app(tmp_path)
    client = TestClient(app)

    surface_response = client.get("/runtime-center/actors/agent-1/capabilities")
    assert surface_response.status_code == 200
    surface = surface_response.json()
    assert surface["agent_id"] == "agent-1"
    assert surface["default_mode"] == "governed"
    assert "system:dispatch_query" in surface["baseline_capabilities"]
    assert surface["routes"]["governed_assign"] == "/api/runtime-center/agents/agent-1/capabilities/governed"

    govern_response = client.post(
        "/runtime-center/actors/agent-1/capabilities/governed",
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

    refreshed_surface = client.get("/runtime-center/actors/agent-1/capabilities")
    assert refreshed_surface.status_code == 200
    refreshed_payload = refreshed_surface.json()
    assert refreshed_payload["pending_decisions"] == []
    assert "tool:send_file_to_user" in refreshed_payload["effective_capabilities"]


def test_runtime_center_agent_capability_assignment_route_for_execution_core(tmp_path) -> None:
    app, _mailbox_service, _supervisor, _item = _build_actor_app(tmp_path)
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


def test_runtime_center_agent_governed_capability_assignment_route_for_execution_core(tmp_path) -> None:
    app, _mailbox_service, _supervisor, _item = _build_actor_app(tmp_path)
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
