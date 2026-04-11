# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.capabilities import router as capabilities_router
from copaw.app.routers.goals import router as goals_router
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.runtime_center import (
    RuntimeCenterEvidenceQueryService,
    RuntimeCenterStateQueryService,
)
from copaw.app.startup_recovery import StartupRecoverySummary
from copaw.capabilities import CapabilityRegistry, CapabilityService
from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    SessionMountRepository,
)
from copaw.evidence import EvidenceLedger, EvidenceRecord
from copaw.goals import GoalService
from copaw.kernel import (
    AgentProfileService,
    KernelDispatcher,
    KernelQueryExecutionService,
    KernelResult,
    KernelTask,
    KernelTaskStore,
    KernelTurnExecutor,
)
from copaw.learning import LearningEngine, LearningService, PatchExecutor
from copaw.state import SQLiteStateStore
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteGoalOverrideRepository,
    SqliteGoalRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


class FakeTurnExecutor:
    async def stream_request(self, request, **kwargs):
        yield {
            "object": "message",
            "status": "completed",
            "request": request,
            "kwargs": kwargs,
        }


class ConfirmingCapabilityRegistry(CapabilityRegistry):
    def list_capabilities(self):
        mounts = super().list_capabilities()
        payload = []
        for mount in mounts:
            if mount.id == "tool:get_current_time":
                payload.append(mount.model_copy(update={"risk_level": "confirm"}))
                continue
            payload.append(mount)
        return payload


def _build_operator_app(tmp_path) -> FastAPI:
    app = FastAPI()
    app.include_router(goals_router)
    app.include_router(capabilities_router)
    app.include_router(runtime_center_router)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    goal_repository = SqliteGoalRepository(state_store)
    goal_override_repository = SqliteGoalOverrideRepository(state_store)
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    schedule_repository = SqliteScheduleRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    learning_service = LearningService(
        engine=LearningEngine(tmp_path / "learning.db"),
        patch_executor=PatchExecutor(goal_override_repository=goal_override_repository),
        decision_request_repository=decision_request_repository,
        task_repository=task_repository,
        evidence_ledger=evidence_ledger,
    )
    capability_service = CapabilityService(
        registry=ConfirmingCapabilityRegistry(),
        evidence_ledger=evidence_ledger,
        turn_executor=FakeTurnExecutor(),
        learning_service=learning_service,
    )
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    dispatcher = KernelDispatcher(
        task_store=task_store,
        capability_service=capability_service,
    )
    goal_service = GoalService(
        repository=goal_repository,
        override_repository=goal_override_repository,
        dispatcher=dispatcher,
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
    )
    capability_service.set_goal_service(goal_service)
    agent_profile_service = AgentProfileService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
        capability_service=capability_service,
        learning_service=learning_service,
        goal_service=goal_service,
    )
    goal_service.set_agent_profile_service(agent_profile_service)
    state_query_service = RuntimeCenterStateQueryService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        schedule_repository=schedule_repository,
        goal_repository=goal_repository,
        goal_service=goal_service,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
        agent_profile_service=agent_profile_service,
    )
    evidence_query_service = RuntimeCenterEvidenceQueryService(
        evidence_ledger=evidence_ledger,
    )

    app.state.goal_service = goal_service
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = dispatcher
    app.state.state_query_service = state_query_service
    app.state.evidence_query_service = evidence_query_service
    app.state.learning_service = learning_service
    app.state.agent_profile_service = agent_profile_service
    app.state.task_repository = task_repository
    app.state.task_runtime_repository = task_runtime_repository
    app.state.runtime_frame_repository = runtime_frame_repository
    app.state.goal_override_repository = goal_override_repository
    app.state.schedule_repository = schedule_repository
    app.state.decision_request_repository = decision_request_repository
    app.state.evidence_ledger = evidence_ledger
    return app


def _build_operator_environment_app(tmp_path) -> FastAPI:
    app = FastAPI()
    app.include_router(runtime_center_router)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    environment_repository = EnvironmentRepository(state_store)
    session_repository = SessionMountRepository(state_store)
    environment_service = EnvironmentService(
        registry=EnvironmentRegistry(
            repository=environment_repository,
            session_repository=session_repository,
            host_id="operator-host",
            process_id=501,
        ),
        lease_ttl_seconds=120,
    )
    environment_service.set_session_repository(session_repository)

    app.state.environment_service = environment_service
    app.state.startup_recovery_summary = StartupRecoverySummary(
        reason="startup",
        recovered_orphaned_leases=1,
        notes=[
            "Same-host cross-process recovery now only runs during explicit startup recovery.",
        ],
    )
    return app


def _admit_confirm_capability(
    app: FastAPI,
    *,
    capability_id: str,
    owner_agent_id: str = "copaw-operator",
) -> dict[str, object]:
    capability_service = app.state.capability_service
    dispatcher = app.state.kernel_dispatcher
    mount = capability_service.get_capability(capability_id)
    assert mount is not None
    task = KernelTask(
        title=f"Admit {capability_id}",
        capability_ref=capability_id,
        owner_agent_id=owner_agent_id,
        risk_level=mount.risk_level,
        payload={},
    )
    return dispatcher.submit(task).model_dump(mode="json")


def _create_goal(
    app: FastAPI,
    *,
    title: str,
    summary: str,
    status: str = "draft",
    priority: int = 0,
):
    return app.state.goal_service.create_goal(
        title=title,
        summary=summary,
        status=status,
        priority=priority,
    )


def _compile_goal(
    app: FastAPI,
    goal_id: str,
    *,
    context: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    return [
        spec.model_dump(mode="json")
        for spec in app.state.goal_service.compile_goal(
            goal_id,
            context=context or {},
        )
    ]


def test_operator_runtime_e2e_feedback_governance_and_runtime_center_contract(
    tmp_path,
) -> None:
    app = _build_operator_app(tmp_path)
    client = TestClient(app)

    created = _create_goal(
        app,
        title="Close operator loop",
        summary="Exercise goal compile, runtime center drill-down, and governance.",
        status="active",
        priority=3,
    )
    goal_id = created.id

    evidence = app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id="task-operator-gap",
            actor_ref="ops-agent",
            capability_ref="system:dispatch_query",
            risk_level="guarded",
            action_summary="Observed operator gap",
            result_summary="Need next-plan feedback and runtime-center deep links.",
        ),
    )
    patch_payload = app.state.learning_service.create_patch(
        kind="plan_patch",
        title="Close operator loop",
        description="Feed applied runtime feedback into the next compiled plan.",
        goal_id=goal_id,
        diff_summary=(
            f"goal_id={goal_id};"
            "plan_steps=Inspect operator backlog|Dispatch guarded action;"
            'compiler_context={"owner_agent_id":"ops-agent"}'
        ),
        evidence_refs=[evidence.id],
        source_evidence_id=evidence.id,
        risk_level="auto",
    )
    patch = patch_payload["patch"]
    applied_patch = app.state.learning_service.apply_patch(
        patch.id,
        applied_by="ops-agent",
    )
    growth = app.state.learning_service.list_growth(goal_id=goal_id, limit=10)
    assert growth

    compiled_payload = _compile_goal(
        app,
        goal_id,
        context={"owner_agent_id": "ops-agent"},
    )
    assert compiled_payload
    compiler_meta = compiled_payload[0]["payload"]["compiler"]
    assert compiler_meta["feedback_patch_ids"] == [applied_patch.id]
    assert compiler_meta["feedback_growth_ids"] == [growth[0].id]
    feedback_evidence_refs = list(compiler_meta["feedback_evidence_refs"])
    assert evidence.id in feedback_evidence_refs
    assert set(applied_patch.evidence_refs).issubset(set(feedback_evidence_refs))
    assert len(feedback_evidence_refs) == len(set(feedback_evidence_refs))

    dispatch_payload = asyncio.run(
        app.state.goal_service.dispatch_goal_execute_now(
            goal_id,
            context={"owner_agent_id": "ops-agent"},
            owner_agent_id="ops-agent",
            activate=True,
        )
    )
    assert dispatch_payload["dispatch_results"][0]["executed"] is True

    goal_detail = client.get(f"/goals/{goal_id}/detail")
    assert goal_detail.status_code == 200
    goal_detail_payload = goal_detail.json()
    assert goal_detail_payload["goal"]["id"] == goal_id
    assert any(item["id"] == applied_patch.id for item in goal_detail_payload["patches"])
    assert any(
        item["source_patch_id"] == applied_patch.id
        for item in goal_detail_payload["growth"]
    )
    assert goal_detail_payload["tasks"]
    goal_task_entry = goal_detail_payload["tasks"][0]
    assert goal_task_entry["task"]["id"]

    admitted_payload = _admit_confirm_capability(
        app,
        capability_id="tool:get_current_time",
    )
    assert admitted_payload["phase"] == "waiting-confirm"
    decision_id = admitted_payload["decision_request_id"]
    assert decision_id

    decision_detail = client.get(f"/runtime-center/decisions/{decision_id}")
    assert decision_detail.status_code == 200
    assert decision_detail.json()["status"] == "open"

    legacy_review = client.post(f"/runtime-center/decisions/{decision_id}/review")
    assert legacy_review.status_code == 404

    reviewing = client.post(f"/runtime-center/governed/decisions/{decision_id}/review")
    assert reviewing.status_code == 200
    assert reviewing.json()["status"] == "reviewing"

    approved = client.post(
        f"/runtime-center/decisions/{decision_id}/approve",
        json={"resolution": "Approved in operator flow.", "execute": True},
    )
    assert approved.status_code == 200
    approved_payload = approved.json()
    assert approved_payload["phase"] == "completed"
    assert approved_payload["decision_request_id"] == decision_id

    capability_task_detail = client.get(
        f"/runtime-center/tasks/{admitted_payload['task_id']}",
    )
    assert capability_task_detail.status_code == 200
    capability_task_payload = capability_task_detail.json()
    assert any(
        item["capability_ref"] == "tool:get_current_time"
        for item in capability_task_payload["evidence"]
    )

    overview = client.get("/runtime-center/surface")
    assert overview.status_code == 200
    cards = {card["key"]: card for card in overview.json()["cards"]}
    assert any(
        entry["id"] == goal_task_entry["task"]["id"]
        for entry in cards["tasks"]["entries"]
    )
    assert any(entry["id"] == applied_patch.id for entry in cards["patches"]["entries"])
    assert cards["growth"]["key"] == "growth"


def test_operator_runtime_e2e_rejection_visibility_in_runtime_center_contract(
    tmp_path,
) -> None:
    app = _build_operator_app(tmp_path)
    client = TestClient(app)

    admitted_payload = _admit_confirm_capability(
        app,
        capability_id="tool:get_current_time",
    )
    assert admitted_payload["phase"] == "waiting-confirm"
    decision_id = admitted_payload["decision_request_id"]
    task_id = admitted_payload["task_id"]

    reviewing = client.post(f"/runtime-center/governed/decisions/{decision_id}/review")
    assert reviewing.status_code == 200
    assert reviewing.json()["status"] == "reviewing"

    rejected = client.post(
        f"/runtime-center/decisions/{decision_id}/reject",
        json={"resolution": "Rejected in operator flow."},
    )
    assert rejected.status_code == 200
    rejected_payload = rejected.json()
    assert rejected_payload["success"] is False
    assert rejected_payload["phase"] == "cancelled"
    assert rejected_payload["decision_request_id"] == decision_id

    decision_detail = client.get(f"/runtime-center/decisions/{decision_id}")
    assert decision_detail.status_code == 200
    assert decision_detail.json()["status"] == "rejected"
    assert decision_detail.json()["resolution"] == "Rejected in operator flow."

    task_detail = client.get(f"/runtime-center/tasks/{task_id}")
    assert task_detail.status_code == 200
    task_payload = task_detail.json()
    assert task_payload["task"]["status"] == "cancelled"
    assert task_payload["runtime"]["current_phase"] == "cancelled"
    assert task_payload["review"]["blocked_reason"] == "runtime-error"
    assert task_payload["review"]["stuck_reason"] == "Rejected in operator flow."
    assert task_payload["review"]["headline"] == "Rejected in operator flow."
    assert any(item["status"] == "rejected" for item in task_payload["decisions"])
    assert any(
        item["result_summary"] == "Rejected in operator flow."
        for item in task_payload["evidence"]
    )

    decisions = client.get("/runtime-center/decisions")
    assert decisions.status_code == 200
    assert any(
        item["id"] == decision_id and item["status"] == "rejected"
        for item in decisions.json()
    )

    overview = client.get("/runtime-center/surface")
    assert overview.status_code == 200
    cards = {card["key"]: card for card in overview.json()["cards"]}
    assert any(
        entry["id"] == task_id and entry["status"] == "cancelled"
        for entry in cards["tasks"]["entries"]
    )
    assert any(
        entry["id"] == decision_id and entry["status"] == "rejected"
        for entry in cards["decisions"]["entries"]
    )


def test_operator_runtime_e2e_governed_patch_apply_writeback_contract(
    tmp_path,
) -> None:
    app = _build_operator_app(tmp_path)
    client = TestClient(app)

    created = _create_goal(
        app,
        title="Apply governed patch",
        summary="Lock the approval and writeback chain for runtime-center patch apply.",
        status="active",
        priority=2,
    )
    goal_id = created.id

    patch_result = app.state.learning_service.create_patch(
        kind="plan_patch",
        title="Governed patch apply",
        description="Use runtime-center governance to apply the patch.",
        goal_id=goal_id,
        diff_summary=f"goal_id={goal_id};plan_steps=Inspect governed flow|Write back result",
        risk_level="confirm",
    )
    patch_id = patch_result["patch"].id

    approve_patch = client.post(
        f"/runtime-center/learning/patches/{patch_id}/approve",
        json={"actor": "ops-reviewer"},
    )
    assert approve_patch.status_code == 200
    assert approve_patch.json()["status"] == "approved"

    apply_patch = client.post(
        f"/runtime-center/learning/patches/{patch_id}/apply",
        json={"actor": "ops-reviewer"},
    )
    assert apply_patch.status_code == 200
    apply_payload = apply_patch.json()
    assert apply_payload["applied"] is False
    assert apply_payload["result"]["phase"] == "waiting-confirm"
    decision_id = apply_payload["result"]["decision_request_id"]
    task_id = apply_payload["result"]["task_id"]
    assert decision_id
    assert task_id

    decision_detail = client.get(f"/runtime-center/decisions/{decision_id}")
    assert decision_detail.status_code == 200
    assert decision_detail.json()["status"] == "open"

    approved = client.post(
        f"/runtime-center/decisions/{decision_id}/approve",
        json={"resolution": "Apply the governed patch now.", "execute": True},
    )
    assert approved.status_code == 200
    assert approved.json()["phase"] == "completed"
    assert approved.json()["decision_request_id"] == decision_id

    goal_override = app.state.goal_override_repository.get_override(goal_id)
    assert goal_override is not None
    assert goal_override.plan_steps == [
        "Inspect governed flow",
        "Write back result",
    ]

    patch_detail = client.get(f"/runtime-center/learning/patches/{patch_id}")
    assert patch_detail.status_code == 200
    assert any(item["source_patch_id"] == patch_id for item in patch_detail.json()["growth"])

    task_detail = client.get(f"/runtime-center/tasks/{task_id}")
    assert task_detail.status_code == 200
    assert any(item["id"] == decision_id for item in task_detail.json()["decisions"])
    assert any(
        item["capability_ref"] == "system:apply_patch"
        for item in task_detail.json()["evidence"]
    )


def test_operator_runtime_e2e_governed_patch_rejection_evidence_contract(
    tmp_path,
) -> None:
    app = _build_operator_app(tmp_path)
    client = TestClient(app)

    created = _create_goal(
        app,
        title="Reject governed patch",
        summary="Lock rejection evidence for runtime-center patch governance.",
        status="active",
        priority=2,
    )
    goal_id = created.id

    patch_result = app.state.learning_service.create_patch(
        kind="plan_patch",
        title="Governed patch rejection",
        description="Use runtime-center governance to reject the patch apply.",
        goal_id=goal_id,
        diff_summary=f"goal_id={goal_id};plan_steps=Keep plan unchanged",
        risk_level="confirm",
    )
    patch_id = patch_result["patch"].id

    approve_patch = client.post(
        f"/runtime-center/learning/patches/{patch_id}/approve",
        json={"actor": "ops-reviewer"},
    )
    assert approve_patch.status_code == 200
    assert approve_patch.json()["status"] == "approved"

    apply_patch = client.post(
        f"/runtime-center/learning/patches/{patch_id}/apply",
        json={"actor": "ops-reviewer"},
    )
    assert apply_patch.status_code == 200
    apply_payload = apply_patch.json()
    decision_id = apply_payload["result"]["decision_request_id"]
    task_id = apply_payload["result"]["task_id"]
    assert decision_id
    assert task_id

    rejected = client.post(
        f"/runtime-center/decisions/{decision_id}/reject",
        json={"resolution": "Do not apply this patch yet."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["phase"] == "cancelled"
    assert rejected.json()["decision_request_id"] == decision_id

    assert app.state.goal_override_repository.get_override(goal_id) is None
    assert app.state.learning_service.get_patch(patch_id).status == "approved"

    decision_detail = client.get(f"/runtime-center/decisions/{decision_id}")
    assert decision_detail.status_code == 200
    assert decision_detail.json()["status"] == "rejected"
    assert decision_detail.json()["resolution"] == "Do not apply this patch yet."

    task_detail = client.get(f"/runtime-center/tasks/{task_id}")
    assert task_detail.status_code == 200
    assert any(item["status"] == "rejected" for item in task_detail.json()["decisions"])
    assert any(
        item["result_summary"] == "Do not apply this patch yet."
        for item in task_detail.json()["evidence"]
    )


def test_operator_manual_environment_e2e_force_release_and_recovery_report_contract(
    tmp_path,
) -> None:
    app = _build_operator_environment_app(tmp_path)
    lease = app.state.environment_service.acquire_session_lease(
        channel="console",
        session_id="sess-ops",
        user_id="founder",
        owner="ops-agent",
        ttl_seconds=60,
        handle={"browser": "tab-ops"},
        metadata={"chat_id": "chat-ops"},
    )
    client = TestClient(app)

    detail_before = client.get(f"/runtime-center/sessions/{lease.id}")
    assert detail_before.status_code == 200
    detail_before_payload = detail_before.json()
    assert detail_before_payload["lease_status"] == "leased"
    assert detail_before_payload["recovery"]["status"] == "attached"
    assert detail_before_payload["recovery"]["same_host"] is True
    assert detail_before_payload["recovery"]["same_process"] is True

    force_release = client.post(
        f"/runtime-center/sessions/{lease.id}/lease/force-release",
        json={"reason": "operator manual cleanup"},
    )
    assert force_release.status_code == 200
    force_release_payload = force_release.json()
    assert force_release_payload["lease_status"] == "released"
    assert (
        force_release_payload["metadata"]["lease_release_reason"]
        == "operator manual cleanup"
    )

    detail_after = client.get(f"/runtime-center/sessions/{lease.id}")
    assert detail_after.status_code == 200
    detail_after_payload = detail_after.json()
    assert detail_after_payload["lease_status"] == "released"
    assert detail_after_payload["live_handle"] is None

    recovery_latest = client.get("/runtime-center/recovery/latest")
    assert recovery_latest.status_code == 200
    recovery_payload = recovery_latest.json()
    assert recovery_payload["reason"] == "startup"
    assert recovery_payload["recovered_orphaned_leases"] == 1
    assert any("cross-process recovery" in note for note in recovery_payload["notes"])


def test_operator_runtime_chat_route_keeps_existing_sse_ingress(
    tmp_path,
) -> None:
    app = _build_operator_app(tmp_path)

    class _CapturingTurnExecutor:
        def __init__(self) -> None:
            self.requests: list[object] = []

        async def stream_request(self, request, **kwargs):
            _ = kwargs
            self.requests.append(request)
            yield {
                "object": "message",
                "status": "completed",
                "session_id": getattr(request, "session_id", None),
            }

    app.state.turn_executor = _CapturingTurnExecutor()
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-runtime-chat",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "Continue the operator loop."}],
                }
            ],
            "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(app.state.turn_executor.requests) == 1
    assert app.state.turn_executor.requests[0].session_id == (
        "industry-chat:industry-v1-ops:execution-core"
    )
    assert '"status": "completed"' in response.text


def test_operator_runtime_chat_route_surfaces_canonical_blocked_diagnostics(
    tmp_path,
) -> None:
    app = _build_operator_app(tmp_path)

    class _BlockedDispatcher:
        def submit(self, task):
            return SimpleNamespace(
                task_id=task.id,
                phase="blocked",
                summary="Runtime seat is still blocked by a host handoff.",
                error="Runtime seat is still blocked by a host handoff.",
                decision_request_id=None,
            )

    app.state.turn_executor = KernelTurnExecutor(
        session_backend=object(),
        kernel_dispatcher=_BlockedDispatcher(),
        query_execution_service=object(),
    )
    client = TestClient(app)

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-runtime-chat-blocked",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "interaction_mode": "orchestrate",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "Resume the blocked runtime."}],
                }
            ],
            "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "Runtime seat is still blocked by a host handoff." in response.text
    assert (
        "Next step: Resolve the current runtime blocker before retrying the turn."
        in response.text
    )


def test_operator_runtime_overview_surfaces_sidecar_memory_degradation(
    tmp_path,
) -> None:
    app = _build_operator_app(tmp_path)
    app.state.governance_service = SimpleNamespace(
        get_status=lambda: SimpleNamespace(
            control_id="runtime",
            emergency_stop_active=False,
            emergency_reason=None,
            emergency_actor=None,
            pending_decisions=0,
            pending_patches=0,
            paused_schedule_ids=[],
            channel_shutdown_applied=False,
            handoff={},
            staffing={},
            human_assist={},
            host_twin={},
            host_companion_session={},
            host_twin_summary={},
            updated_at=None,
        )
    )
    query_execution_service = KernelQueryExecutionService(
        session_backend=object(),
        conversation_compaction_service=None,
    )
    expected_entropy = query_execution_service._resolve_execution_task_context(  # pylint: disable=protected-access
        request=SimpleNamespace(),
        agent_id="ops-agent",
        kernel_task_id=None,
        conversation_thread_id="industry-chat:industry-v1-ops:execution-core",
    )["query_runtime_entropy"]
    app.state.query_execution_service = SimpleNamespace(
        get_query_runtime_entropy_contract=lambda: expected_entropy,
    )
    client = TestClient(app)

    response = client.get("/runtime-center/surface")

    assert response.status_code == 200
    cards = {card["key"]: card for card in response.json()["cards"]}
    governance = cards["governance"]
    entry = governance["entries"][0]
    entropy = governance["meta"]["query_runtime_entropy"]
    assert entropy == expected_entropy
    assert entry["meta"]["query_runtime_entropy"] == expected_entropy
    assert entropy["budget"]["tool_result_budget"]["state_channel"] == "query_runtime_state"
    assert entropy["budget"]["tool_result_budget"]["summary_surface"] == "runtime-center"
    assert entropy["budget"]["tool_result_budget"]["spill_surface"] == "runtime-center"
    assert entropy["budget"]["tool_result_budget"]["replay_surface"] == "runtime-conversation"
    assert entry["meta"]["query_runtime_entropy"]["runtime_entropy"]["tool_result_budget"] == (
        entropy["budget"]["tool_result_budget"]
    )
    sidecar_memory = governance["meta"]["sidecar_memory"]
    assert sidecar_memory == expected_entropy["sidecar_memory"]
    assert entry["meta"]["sidecar_memory"] == expected_entropy["sidecar_memory"]
    assert sidecar_memory["failure_source"] == "sidecar-memory"
    assert "canonical state only" in sidecar_memory["summary"]
    assert "Restore the compaction sidecar" in sidecar_memory["blocked_next_step"]
    assert governance["summary"] == expected_entropy["sidecar_memory"]["summary"]


def test_operator_runtime_overview_falls_back_to_runtime_contract_sidecar_diagnostics(
    tmp_path,
) -> None:
    app = _build_operator_app(tmp_path)
    app.state.governance_service = SimpleNamespace(
        get_status=lambda: SimpleNamespace(
            control_id="runtime",
            emergency_stop_active=False,
            emergency_reason=None,
            emergency_actor=None,
            pending_decisions=0,
            pending_patches=0,
            paused_schedule_ids=[],
            channel_shutdown_applied=False,
            handoff={},
            staffing={},
            human_assist={},
            host_twin={},
            host_companion_session={},
            host_twin_summary={},
            updated_at=None,
        )
    )
    degraded_sidecar_memory = {
        "status": "degraded",
        "failure_source": "runtime-contract-sidecar",
        "blocked_next_step": "Restore the runtime-contract sidecar before scheduling the next turn.",
        "summary": "Runtime contract fallback is degraded and canonical state is the only safe carry-forward path.",
    }
    app.state.actor_worker = SimpleNamespace(
        runtime_contract={"sidecar_memory": degraded_sidecar_memory},
    )
    client = TestClient(app)

    response = client.get("/runtime-center/surface")

    assert response.status_code == 200
    cards = {card["key"]: card for card in response.json()["cards"]}
    governance = cards["governance"]
    entry = governance["entries"][0]
    assert entry["status"] == "blocked"
    assert governance["meta"]["query_runtime_entropy"] == {}
    assert governance["meta"]["sidecar_memory"] == degraded_sidecar_memory
    assert entry["meta"]["sidecar_memory"] == degraded_sidecar_memory
    assert governance["meta"]["failure_source"] == "runtime-contract-sidecar"
    assert governance["meta"]["blocked_next_step"] == (
        "Restore the runtime-contract sidecar before scheduling the next turn."
    )
    assert entry["meta"]["failure_source"] == "runtime-contract-sidecar"
    assert entry["meta"]["blocked_next_step"] == (
        "Restore the runtime-contract sidecar before scheduling the next turn."
    )
    assert governance["summary"] == (
        "Runtime contract fallback is degraded and canonical state is the only safe carry-forward path."
    )
