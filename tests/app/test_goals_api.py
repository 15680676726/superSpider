# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.goals import router as goals_router
from copaw.evidence import EvidenceLedger, EvidenceRecord
from copaw.capabilities import CapabilityService
from copaw.goals import GoalService
from copaw.kernel.persistence import decode_kernel_task_metadata
from copaw.kernel import AgentProfileService, KernelDispatcher, KernelTaskStore
from copaw.learning import LearningEngine, LearningService, PatchExecutor
from copaw.state import (
    DecisionRequestRecord,
    GoalOverrideRecord,
    IndustryInstanceRecord,
    RuntimeFrameRecord,
    SQLiteStateStore,
    TaskRecord,
    TaskRuntimeRecord,
    StrategyMemoryRecord,
)
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.strategy_memory_service import StateStrategyMemoryService
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteGoalOverrideRepository,
    SqliteGoalRepository,
    SqliteIndustryInstanceRepository,
    SqliteKnowledgeChunkRepository,
    SqliteRuntimeFrameRepository,
    SqliteStrategyMemoryRepository,
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


class SlowTurnExecutor:
    def __init__(self, *, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds

    async def stream_request(self, request, **kwargs):
        await asyncio.sleep(self.delay_seconds)
        yield {
            "object": "message",
            "status": "completed",
            "request": request,
            "kwargs": kwargs,
        }


def _build_goal_app(tmp_path, *, turn_executor=None) -> FastAPI:
    app = FastAPI()
    app.include_router(goals_router)

    state_store = SQLiteStateStore(tmp_path / "state.db")
    goal_repository = SqliteGoalRepository(state_store)
    goal_override_repository = SqliteGoalOverrideRepository(state_store)
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    knowledge_repository = SqliteKnowledgeChunkRepository(state_store)
    industry_instance_repository = SqliteIndustryInstanceRepository(state_store)
    strategy_memory_repository = SqliteStrategyMemoryRepository(state_store)
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    capability_service = CapabilityService(
        turn_executor=turn_executor or FakeTurnExecutor(),
    )
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
    knowledge_service = StateKnowledgeService(repository=knowledge_repository)
    strategy_memory_service = StateStrategyMemoryService(
        repository=strategy_memory_repository,
    )
    learning_service = LearningService(
        engine=LearningEngine(tmp_path / "learning.db"),
        patch_executor=PatchExecutor(goal_override_repository=goal_override_repository),
        decision_request_repository=decision_request_repository,
        task_repository=task_repository,
        evidence_ledger=evidence_ledger,
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
        strategy_memory_service=strategy_memory_service,
        knowledge_service=knowledge_service,
        industry_instance_repository=industry_instance_repository,
    )
    agent_profile_service = AgentProfileService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        capability_service=capability_service,
        goal_service=goal_service,
    )
    goal_service.set_agent_profile_service(agent_profile_service)
    app.state.goal_service = goal_service
    app.state.goal_override_repository = goal_override_repository
    app.state.task_repository = task_repository
    app.state.task_runtime_repository = task_runtime_repository
    app.state.runtime_frame_repository = runtime_frame_repository
    app.state.decision_request_repository = decision_request_repository
    app.state.evidence_ledger = evidence_ledger
    app.state.learning_service = learning_service
    app.state.knowledge_service = knowledge_service
    app.state.strategy_memory_service = strategy_memory_service
    app.state.industry_instance_repository = industry_instance_repository
    return app


def _create_goal(
    app: FastAPI,
    *,
    title: str,
    summary: str,
    status: str = "draft",
    priority: int = 0,
    owner_scope: str | None = None,
    industry_instance_id: str | None = None,
):
    return app.state.goal_service.create_goal(
        title=title,
        summary=summary,
        status=status,
        priority=priority,
        owner_scope=owner_scope,
        industry_instance_id=industry_instance_id,
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


def test_goals_hidden_crud_compile_shell_is_removed_but_detail_survives(tmp_path) -> None:
    app = _build_goal_app(tmp_path)
    client = TestClient(app)

    goal = _create_goal(
        app,
        title="Make goals visible",
        summary="Expose goals in runtime center and agent workbench.",
        status="draft",
        priority=2,
    )
    goal_id = goal.id

    app.state.goal_service.update_goal(
        goal_id,
        status="active",
        priority=4,
    )

    compiled_payload = _compile_goal(
        app,
        goal_id,
        context={"source": "test", "owner_agent_id": "ops-agent"},
    )
    assert compiled_payload
    assert compiled_payload[0]["capability_ref"] == "system:dispatch_query"
    assert compiled_payload[0]["payload"]["request"]["channel"] == "goal"
    assert compiled_payload[0]["payload"]["request"]["user_id"] == "ops-agent"
    assert compiled_payload[0]["payload"]["dispatch_events"] is False

    detail = client.get(f"/goals/{goal_id}/detail")
    assert detail.status_code == 200
    assert detail.json()["goal"]["status"] == "active"

    assert client.get("/goals").status_code == 404
    assert client.post("/goals", json={"title": "Retired frontdoor"}).status_code == 404
    assert client.get(f"/goals/{goal_id}").status_code == 404
    assert client.patch(f"/goals/{goal_id}", json={"status": "active"}).status_code == 404
    assert client.delete(f"/goals/{goal_id}").status_code == 404
    assert client.post(
        f"/goals/{goal_id}/compile",
        json={"context": {"source": "test", "owner_agent_id": "ops-agent"}},
    ).status_code == 404
    assert client.post(
        f"/goals/{goal_id}/dispatch",
        json={"execute": True, "activate": True, "owner_agent_id": "ops-agent"},
    ).status_code == 404


def test_goal_service_list_respects_limit_query(tmp_path) -> None:
    app = _build_goal_app(tmp_path)

    for index in range(3):
        _create_goal(
            app,
            title=f"Goal {index}",
            summary="List limit test",
            status="active",
            priority=index,
        )

    listed = app.state.goal_service.list_goals(status="active", limit=2)
    assert len(listed) == 2


def test_goal_service_list_supports_industry_instance_filter(tmp_path) -> None:
    app = _build_goal_app(tmp_path)

    matched = _create_goal(
        app,
        title="Industry Goal A",
        summary="Matches the requested industry instance.",
        status="active",
        owner_scope="custom-owner-scope-a",
        industry_instance_id="industry-v1-alpha",
    )
    _create_goal(
        app,
        title="Industry Goal B",
        summary="Belongs to another industry instance.",
        status="active",
        owner_scope="industry-v1-alpha",
        industry_instance_id="industry-v1-beta",
    )

    payload = app.state.goal_service.list_goals(
        industry_instance_id="industry-v1-alpha",
        status="active",
    )
    assert [item.id for item in payload] == [matched.id]
    assert payload[0].industry_instance_id == "industry-v1-alpha"


def test_dispatch_active_goals_frontdoor_is_removed(tmp_path) -> None:
    app = _build_goal_app(tmp_path)
    client = TestClient(app)

    _create_goal(
        app,
        title="Active goal",
        summary="Should be dispatched.",
        status="active",
        priority=1,
    )
    _create_goal(
        app,
        title="Draft goal",
        summary="Should not be dispatched.",
        status="draft",
        priority=0,
    )

    dispatched = client.post(
        "/goals/automation/dispatch-active",
        json={"execute": True},
    )
    assert dispatched.status_code == 404


def test_dispatch_goal_preserves_override_owner_when_request_owner_is_missing(
    tmp_path,
) -> None:
    app = _build_goal_app(tmp_path)

    goal = _create_goal(
        app,
        title="Preserve compiler owner",
        summary="Keep the goal-specific owner when dispatch payload omits one.",
        status="active",
        priority=1,
    )
    goal_id = goal.id

    app.state.goal_override_repository.upsert_override(
        GoalOverrideRecord(
            goal_id=goal_id,
            compiler_context={"owner_agent_id": "ops-agent"},
        ),
    )

    payload = asyncio.run(
        app.state.goal_service.compile_goal_dispatch(
            goal_id,
            context={},
            owner_agent_id=None,
            activate=True,
        )
    )
    assert payload["compiled_tasks"][0]["owner_agent_id"] == "ops-agent"
    tasks = app.state.task_repository.list_tasks(goal_id=goal_id)
    assert tasks
    assert tasks[0].owner_agent_id == "ops-agent"
    assert payload["dispatch_results"][0]["executed"] is False
    assert payload["dispatch_results"][0]["phase"] == "compiled"
    task_runtime = app.state.task_runtime_repository.get_runtime(tasks[0].id)
    assert task_runtime is not None
    assert task_runtime.current_phase == "compiled"
    assert task_runtime.runtime_status == "cold"


def test_dispatch_goal_can_defer_background_execution_until_released(
    tmp_path,
) -> None:
    app = _build_goal_app(
        tmp_path,
        turn_executor=SlowTurnExecutor(delay_seconds=0.2),
    )
    goal = app.state.goal_service.create_goal(
        title="Deferred background goal",
        summary="Dispatch now and execute after the caller releases it.",
        status="active",
        priority=1,
    )

    async def _exercise() -> tuple[dict[str, object], list[str], list[str]]:
        payload = await app.state.goal_service.dispatch_goal_deferred_background(
            goal.id,
            context={"owner_agent_id": "ops-agent"},
            owner_agent_id="ops-agent",
            activate=True,
        )
        await asyncio.sleep(0.35)
        background_task_ids = [
            str(item["task_id"])
            for item in payload["dispatch_results"]
            if item.get("scheduled_execution") is True and item.get("task_id")
        ]
        statuses_before_release = [
            app.state.task_repository.get_task(task_id).status
            for task_id in background_task_ids
        ]
        app.state.goal_service.release_deferred_goal_dispatch(
            goal_id=goal.id,
            dispatch_results=payload["dispatch_results"],
        )
        statuses_after_release = list(statuses_before_release)
        for _ in range(30):
            statuses_after_release = [
                app.state.task_repository.get_task(task_id).status
                for task_id in background_task_ids
            ]
            if all(status == "completed" for status in statuses_after_release):
                break
            await asyncio.sleep(0.1)
        return payload, statuses_before_release, statuses_after_release

    payload, statuses_before_release, statuses_after_release = asyncio.run(_exercise())

    assert payload["dispatch_results"]
    assert all(item["scheduled_execution"] is True for item in payload["dispatch_results"])
    assert all(status == "created" for status in statuses_before_release)
    assert all(status == "completed" for status in statuses_after_release)


def test_goal_service_uses_explicit_leaf_dispatch_entrypoints(tmp_path) -> None:
    app = _build_goal_app(tmp_path)
    compile_signature = inspect.signature(app.state.goal_service.compile_goal_dispatch)
    execute_signature = inspect.signature(app.state.goal_service.dispatch_goal_execute_now)
    background_signature = inspect.signature(app.state.goal_service.dispatch_goal_background)
    deferred_signature = inspect.signature(
        app.state.goal_service.dispatch_goal_deferred_background,
    )

    assert hasattr(app.state.goal_service, "dispatch_goal") is False
    assert "background_task_ids_sink" not in compile_signature.parameters
    assert "schedule_background_execution" not in compile_signature.parameters
    assert "execute_background" not in compile_signature.parameters
    assert "execute" not in compile_signature.parameters
    assert "activate" in compile_signature.parameters
    assert "activate" in execute_signature.parameters
    assert "activate" in background_signature.parameters
    assert "activate" in deferred_signature.parameters
    assert hasattr(app.state.goal_service, "schedule_background_goal_execution") is False


def test_dispatch_goal_only_materializes_the_current_planned_step(
    tmp_path,
) -> None:
    app = _build_goal_app(tmp_path)
    goal = app.state.goal_service.create_goal(
        title="Stepwise planned goal",
        summary="Only the current planned step should materialize as a task.",
        status="active",
        priority=1,
    )
    app.state.goal_override_repository.upsert_override(
        GoalOverrideRecord(
            goal_id=goal.id,
            plan_steps=[
                "Prepare the first brief",
                "Pause for approval before continuing",
                "Publish the next follow-up",
            ],
            compiler_context={"owner_agent_id": "ops-agent"},
        ),
    )

    async def _exercise() -> dict[str, object]:
        return await app.state.goal_service.compile_goal_dispatch(
            goal.id,
            context={"owner_agent_id": "ops-agent"},
            owner_agent_id="ops-agent",
            activate=True,
        )

    payload = asyncio.run(_exercise())

    compiled_tasks = payload["compiled_tasks"]
    assert len(compiled_tasks) == 1
    assert compiled_tasks[0]["title"].startswith("Goal step 1:")
    assert "compiled_specs" not in payload
    assert "trigger" not in payload

    task_records = app.state.task_repository.list_tasks(goal_id=goal.id)
    assert len(task_records) == 1
    metadata = decode_kernel_task_metadata(task_records[0].acceptance_criteria)
    assert metadata is not None
    assert metadata["payload"]["compiler"]["plan_step_number"] == 1
    assert metadata["payload"]["compiler"]["plan_step_total"] == 3


def test_dispatch_goal_advances_to_the_next_planned_step_after_completion(
    tmp_path,
) -> None:
    app = _build_goal_app(tmp_path)
    goal = app.state.goal_service.create_goal(
        title="Advance planned step",
        summary="A completed step should unlock the next planned step instead of completing the whole goal.",
        status="active",
        priority=1,
    )
    app.state.goal_override_repository.upsert_override(
        GoalOverrideRecord(
            goal_id=goal.id,
            plan_steps=[
                "Prepare the brief",
                "Keep the staged follow-up pending",
                "Keep the staged close-out pending",
            ],
            compiler_context={"owner_agent_id": "ops-agent"},
        ),
    )

    async def _dispatch_first_step() -> str:
        await app.state.goal_service.compile_goal_dispatch(
            goal.id,
            context={"owner_agent_id": "ops-agent"},
            owner_agent_id="ops-agent",
            activate=True,
        )
        first_task = app.state.task_repository.list_tasks(goal_id=goal.id)[0]
        return first_task.id

    first_task_id = asyncio.run(_dispatch_first_step())

    first_task = app.state.task_repository.get_task(first_task_id)
    first_runtime = app.state.task_runtime_repository.get_runtime(first_task_id)
    assert first_task is not None
    assert first_runtime is not None
    app.state.task_repository.upsert_task(
        first_task.model_copy(update={"status": "completed"}),
    )
    app.state.task_runtime_repository.upsert_runtime(
        first_runtime.model_copy(
            update={"current_phase": "completed", "runtime_status": "terminated"},
        ),
    )
    app.state.goal_service.reconcile_goal_status(goal.id)

    updated_goal = app.state.goal_service.get_goal(goal.id)
    assert updated_goal is not None
    assert updated_goal.status == "active"

    payload = asyncio.run(
        app.state.goal_service.dispatch_goal_execute_now(
            goal.id,
            context={"owner_agent_id": "ops-agent"},
            owner_agent_id="ops-agent",
            activate=False,
        )
    )

    assert len(payload["dispatch_results"]) == 1
    task_records = app.state.task_repository.list_tasks(goal_id=goal.id)
    assert len(task_records) == 2
    second_task = max(task_records, key=lambda item: item.updated_at)
    metadata = decode_kernel_task_metadata(second_task.acceptance_criteria)
    assert metadata is not None
    assert metadata["payload"]["compiler"]["plan_step_number"] == 2
    assert metadata["payload"]["compiler"]["plan_step_total"] == 3


def test_goal_service_no_longer_exposes_dispatch_active_goals(tmp_path) -> None:
    app = _build_goal_app(tmp_path)
    assert hasattr(app.state.goal_service, "dispatch_active_goals") is False


def test_goal_detail_does_not_reconcile_goal_status(tmp_path) -> None:
    app = _build_goal_app(tmp_path)
    client = TestClient(app)

    goal = _create_goal(
        app,
        title="Keep goal detail read-only",
        summary="Detail reads should not mutate goal status.",
        status="active",
        priority=2,
    )
    goal_id = goal.id

    completed_task = TaskRecord(
        id="task-goal-detail-read-only",
        goal_id=goal_id,
        title="Completed task",
        summary="Already finished before the detail read.",
        task_type="goal-step",
        status="completed",
        owner_agent_id="copaw-agent-runner",
        current_risk_level="guarded",
    )
    app.state.task_repository.upsert_task(completed_task)
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id=completed_task.id,
            runtime_status="terminated",
            current_phase="completed",
            risk_level="guarded",
            last_owner_agent_id="copaw-agent-runner",
        ),
    )

    detail = client.get(f"/goals/{goal_id}/detail")
    assert detail.status_code == 200
    assert detail.json()["goal"]["status"] == "active"
    assert app.state.goal_service.get_goal(goal_id).status == "active"

    reconciled = app.state.goal_service.reconcile_goal_status(goal_id)
    assert reconciled is not None
    assert reconciled.status == "completed"
    assert app.state.goal_service.get_goal(goal_id).status == "completed"


def test_goal_detail_endpoint_remains_read_only(tmp_path) -> None:
    app = _build_goal_app(tmp_path)
    client = TestClient(app)

    goal = _create_goal(
        app,
        title="Goal detail stays read-only",
        summary="The detail endpoint must not become a write surface.",
        status="active",
        priority=1,
    )
    goal_id = goal.id

    detail = client.get(f"/goals/{goal_id}/detail")
    assert detail.status_code == 200
    assert detail.json()["goal"]["id"] == goal_id

    assert client.post(f"/goals/{goal_id}/detail", json={"title": "forbidden"}).status_code == 405
    assert client.patch(f"/goals/{goal_id}/detail", json={"title": "forbidden"}).status_code == 405
    assert client.delete(f"/goals/{goal_id}/detail").status_code == 405


def test_goal_detail_links_tasks_agents_patches_and_growth(tmp_path) -> None:
    app = _build_goal_app(tmp_path)
    client = TestClient(app)

    goal = _create_goal(
        app,
        title="Make goal detail visible",
        summary="Link goal, tasks, evidence, decisions, patches, and growth.",
        status="active",
        priority=3,
    )
    goal_id = goal.id

    task = TaskRecord(
        id="task-goal-detail-1",
        goal_id=goal_id,
        title="Inspect runtime gap",
        summary="Collect the missing runtime center detail signals.",
        task_type="goal-step",
        status="running",
        owner_agent_id="copaw-agent-runner",
        current_risk_level="guarded",
    )
    app.state.task_repository.upsert_task(task)
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id=task.id,
            runtime_status="active",
            current_phase="executing",
            risk_level="guarded",
            active_environment_id="session:goal:goal-detail",
            last_result_summary="Collected current bindings.",
            last_owner_agent_id="copaw-agent-runner",
        ),
    )
    app.state.runtime_frame_repository.append_frame(
        RuntimeFrameRecord(
            task_id=task.id,
            goal_summary="Make goal detail visible",
            owner_agent_id="copaw-agent-runner",
            current_phase="executing",
            current_risk_level="guarded",
            environment_summary="session:goal:goal-detail",
            evidence_summary="Collected current bindings.",
        ),
    )
    app.state.decision_request_repository.upsert_decision_request(
        DecisionRequestRecord(
            task_id=task.id,
            decision_type="confirm-step",
            risk_level="guarded",
            summary="Review the next manual step.",
            requested_by="copaw-agent-runner",
        ),
    )

    evidence = app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id=task.id,
            actor_ref="copaw-agent-runner",
            capability_ref="system:dispatch_query",
            risk_level="guarded",
            action_summary="Dispatch goal step",
            result_summary="Collected current bindings.",
            environment_ref="session:goal:goal-detail",
        ),
    )
    patch_result = app.state.learning_service.create_patch(
        kind="plan_patch",
        title="Refine goal plan",
        description="Split the goal into explicit operator-visible steps.",
        diff_summary=(
            f"goal_id={goal_id};"
            "plan_steps=Inspect runtime gap|Publish goal detail"
        ),
        evidence_refs=[evidence.id],
        source_evidence_id=evidence.id,
        risk_level="auto",
    )
    patch = patch_result["patch"]
    assert patch.goal_id == goal_id
    assert patch.task_id == task.id
    assert patch.agent_id == "copaw-agent-runner"
    app.state.learning_service.apply_patch(
        patch.id,
        applied_by="copaw-agent-runner",
    )

    detail = client.get(f"/goals/{goal_id}/detail")
    assert detail.status_code == 200
    payload = detail.json()

    assert payload["goal"]["id"] == goal_id
    assert payload["override"]["goal_id"] == goal_id
    assert payload["override"]["plan_steps"] == [
        "Inspect runtime gap",
        "Publish goal detail",
    ]
    assert payload["compilation"]["specs"]
    assert payload["compilation"]["specs"][0]["capability_ref"] == "system:dispatch_query"
    task_entries = {item["task"]["id"]: item for item in payload["tasks"]}
    assert task.id in task_entries
    assert patch.id in task_entries
    assert task_entries[task.id]["runtime"]["runtime_status"] == "active"
    assert task_entries[task.id]["decision_count"] == 1
    assert task_entries[task.id]["evidence_count"] == 1
    assert payload["agents"][0]["agent_id"] == "copaw-agent-runner"
    assert any(item["task_id"] == task.id for item in payload["decisions"])
    assert any(item["task_id"] == patch.id for item in payload["decisions"])
    assert any(item["id"] == evidence.id for item in payload["evidence"])
    assert any(item["id"] == patch.id for item in payload["patches"])
    assert any(item["source_patch_id"] == patch.id for item in payload["growth"])


def test_compile_persists_state_backed_compiler_context_metadata(tmp_path) -> None:
    app = _build_goal_app(tmp_path)
    goal = _create_goal(
        app,
        title="Launch runtime center",
        summary="Promote the runtime center as operator cockpit.",
        status="active",
        priority=2,
    )
    goal_id = goal.id

    app.state.goal_override_repository.upsert_override(
        GoalOverrideRecord(
            goal_id=goal_id,
            plan_steps=["wire overview", "verify evidence"],
            compiler_context={
                "owner_agent_id": "ops-agent",
                "evidence_refs": ["evidence-1", "evidence-2"],
            },
        ),
    )

    payload = _compile_goal(app, goal_id)
    assert len(payload) == 1
    assert [item["task_id"] for item in payload] == [
        task.id for task in app.state.task_repository.list_tasks(goal_id=goal_id)
    ]

    task_records = app.state.task_repository.list_tasks(goal_id=goal_id)
    assert len(task_records) == 1
    runtime_records = [
        app.state.task_runtime_repository.get_runtime(task.id)
        for task in task_records
    ]
    assert all(runtime is not None for runtime in runtime_records)
    assert all(runtime.current_phase == "compiled" for runtime in runtime_records if runtime is not None)

    first_task = task_records[0]
    metadata = decode_kernel_task_metadata(first_task.acceptance_criteria)
    assert metadata is not None
    assert metadata["payload"]["compiler"]["evidence_refs"] == [
        "evidence-1",
        "evidence-2",
    ]
    assert metadata["payload"]["task_seed"]["evidence_refs"] == [
        "evidence-1",
        "evidence-2",
    ]
    assert metadata["payload"]["compiler"]["plan_step_number"] == 1
    assert metadata["payload"]["compiler"]["plan_step_total"] == 2
    assert first_task.seed_source.startswith("compiler:goal:")
    assert first_task.constraints_summary == (
        f"goal_id={goal_id}; plan_step=wire overview; channel=goal; "
        "evidence_refs=evidence-1,evidence-2"
    )


def test_compile_goal_feeds_learning_patch_and_growth_back_into_compiler_context(
    tmp_path,
) -> None:
    app = _build_goal_app(tmp_path)
    goal = _create_goal(
        app,
        title="Close runtime loop",
        summary="Feed runtime learning back into the next compiler pass.",
        status="active",
        priority=2,
    )
    goal_id = goal.id

    feedback_task = TaskRecord(
        id="task-feedback-1",
        goal_id=goal_id,
        title="Inspect feedback loop",
        summary="Capture the latest execution state before recompiling.",
        task_type="goal-step",
        status="running",
        owner_agent_id="ops-agent",
        current_risk_level="guarded",
    )
    app.state.task_repository.upsert_task(feedback_task)
    app.state.task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id=feedback_task.id,
            runtime_status="active",
            current_phase="verify-brief",
            risk_level="guarded",
            last_owner_agent_id="ops-agent",
        ),
    )

    evidence = app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id="task-feedback-1",
            actor_ref="ops-agent",
            capability_ref="system:dispatch_query",
            risk_level="guarded",
            action_summary="Observed operator gap",
            result_summary="Need to surface growth feedback in compile.",
        ),
    )
    patch_payload = app.state.learning_service.create_patch(
        kind="plan_patch",
        title="Tighten next-plan feedback",
        description="Carry applied learning back into goal compilation.",
        goal_id=goal_id,
        diff_summary=(
            f"goal_id={goal_id};"
            "plan_steps=Inspect feedback loop|Compile next step with evidence; "
            'compiler_context={"owner_agent_id":"ops-agent"}'
        ),
        evidence_refs=[evidence.id],
        source_evidence_id=evidence.id,
        risk_level="auto",
    )
    patch = patch_payload["patch"]
    assert patch is not None
    applied_patch = app.state.learning_service.apply_patch(
        patch.id,
        applied_by="ops-agent",
    )
    growth = app.state.learning_service.list_growth(goal_id=goal_id, limit=10)
    assert growth

    failed_a = app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id=feedback_task.id,
            actor_ref="ops-agent",
            capability_ref="browser_use",
            risk_level="guarded",
            action_summary="Retry storefront login",
            result_summary="Failed due to captcha wall.",
            status="failed",
        ),
    )
    failed_b = app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id=feedback_task.id,
            actor_ref="ops-agent",
            capability_ref="browser_use",
            risk_level="guarded",
            action_summary="Retry storefront login",
            result_summary="Failed due to captcha wall again.",
            status="failed",
        ),
    )
    success = app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id=feedback_task.id,
            actor_ref="ops-agent",
            capability_ref="read_file",
            risk_level="auto",
            action_summary="Review previous execution brief",
            result_summary="Recovered the next owner and blocker summary.",
        ),
    )

    payload = _compile_goal(app, goal_id)
    assert payload

    first_spec = payload[0]
    compiler_meta = first_spec["payload"]["compiler"]
    task_seed = first_spec["payload"]["task_seed"]
    assert compiler_meta["feedback_patch_ids"] == [applied_patch.id]
    assert compiler_meta["feedback_growth_ids"] == [growth[0].id]
    assert evidence.id in compiler_meta["feedback_evidence_refs"]
    assert failed_a.id in compiler_meta["feedback_evidence_refs"]
    assert failed_b.id in compiler_meta["feedback_evidence_refs"]
    assert success.id in compiler_meta["feedback_evidence_refs"]
    assert task_seed["feedback_patch_ids"] == [applied_patch.id]
    assert task_seed["feedback_growth_ids"] == [growth[0].id]
    assert compiler_meta["current_stage"] == "Inspect feedback loop [verify-brief]"
    assert compiler_meta["recent_failures"]
    assert compiler_meta["effective_actions"]
    assert compiler_meta["avoid_repeats"]
    assert task_seed["current_stage"] == "Inspect feedback loop [verify-brief]"
    assert evidence.id in compiler_meta["evidence_refs"]
    assert failed_a.id in compiler_meta["evidence_refs"]
    assert success.id in compiler_meta["evidence_refs"]


def test_compile_goal_injects_knowledge_and_memory_context(tmp_path) -> None:
    app = _build_goal_app(tmp_path)

    app.state.knowledge_service.import_document(
        title="Ops SOP",
        content="Use evidence checkpoints before outbound execution.",
        role_bindings=["execution-core"],
        tags=["ops"],
    )
    app.state.knowledge_service.remember_fact(
        title="Customer rule",
        content="ACME requires the execution core to review risk before sending updates.",
        scope_type="agent",
        scope_id="ops-agent",
        role_bindings=["execution-core"],
    )

    goal = _create_goal(
        app,
        title="Prepare execution brief",
        summary="Review evidence checkpoints and draft the next update.",
        status="active",
        priority=1,
    )
    goal_id = goal.id
    app.state.goal_override_repository.upsert_override(
        GoalOverrideRecord(
            goal_id=goal_id,
            compiler_context={
                "owner_agent_id": "ops-agent",
                "industry_role_id": "execution-core",
            },
        ),
    )

    payload = _compile_goal(app, goal_id)[0]["payload"]["compiler"]
    assert payload["knowledge_refs"]
    assert payload["memory_refs"]


def test_compile_goal_propagates_runtime_request_context_and_role_brief(tmp_path) -> None:
    app = _build_goal_app(tmp_path)
    goal = _create_goal(
        app,
        title="Operate Acme account",
        summary="Prepare the next operating move.",
        status="active",
        priority=1,
    )
    goal_id = goal.id
    app.state.goal_override_repository.upsert_override(
        GoalOverrideRecord(
            goal_id=goal_id,
            compiler_context={
                "owner_agent_id": "ops-agent",
                "owner_scope": "industry-v1-acme",
                "industry_instance_id": "industry-v1-acme",
                "industry_role_id": "execution-core",
                "industry_label": "Acme Operations Cell",
                "industry_role_name": "白泽执行中枢",
                "session_kind": "industry-agent-chat",
                "task_mode": "team-orchestration",
                "role_summary": "Own the execution loop.",
                "mission": "Turn the brief into the next coordinated move.",
                "environment_constraints": ["workspace draft/edit only"],
                "evidence_expectations": ["execution brief", "evidence summary"],
            },
        ),
    )

    payload = _compile_goal(app, goal_id)[0]["payload"]
    assert payload["request"]["agent_id"] == "ops-agent"
    assert payload["request"]["industry_instance_id"] == "industry-v1-acme"
    assert payload["request"]["owner_scope"] == "industry-v1-acme"
    assert payload["request"]["session_kind"] == "industry-agent-chat"
    assert payload["request"]["task_mode"] == "team-orchestration"
    assert payload["request_context"]["industry_label"] == "Acme Operations Cell"
    assert payload["request_context"]["industry_role_name"] == "白泽执行中枢"
    assert payload["request_context"]["task_mode"] == "team-orchestration"
    assert payload["meta"]["request_context"]["owner_scope"] == "industry-v1-acme"
    assert payload["task_seed"]["request_context"]["industry_instance_id"] == "industry-v1-acme"
    assert payload["task_seed"]["request_context"]["task_mode"] == "team-orchestration"
    assert payload["compiler"]["request_context"]["session_kind"] == "industry-agent-chat"
    assert payload["compiler"]["request_context"]["task_mode"] == "team-orchestration"
    prompt_text = payload["compiler"]["prompt_text"]


def test_goal_detail_exposes_execution_core_identity_from_industry_instance(tmp_path) -> None:
    app = _build_goal_app(tmp_path)
    client = TestClient(app)

    app.state.industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-v1-acme",
            label="Acme Operations Cell",
            summary="Execution shell for Acme operations.",
            owner_scope="industry-v1-acme",
            status="active",
            profile_payload={"industry": "Operations"},
            team_payload={
                "team_id": "industry-v1-acme",
                "label": "Acme Operations Cell",
                "summary": "Execution shell for Acme operations.",
                "agents": [
                    {
                        "role_id": "execution-core",
                        "agent_id": "copaw-agent-runner",
                        "name": "白泽执行中枢",
                        "role_name": "白泽执行中枢",
                    },
                ],
            },
            execution_core_identity_payload={
                "binding_id": "industry-v1-acme:execution-core",
                "agent_id": "copaw-agent-runner",
                "role_id": "execution-core",
                "industry_instance_id": "industry-v1-acme",
                "identity_label": "Acme Operations Cell / 白泽执行中枢",
                "industry_label": "Acme Operations Cell",
                "industry_summary": "Execution shell for Acme operations.",
                "role_name": "白泽执行中枢",
                "role_summary": "Operate as Acme's execution brain.",
                "mission": "Turn Acme operational goals into coordinated actions.",
                "thinking_axes": [
                    "Industry focus: Operations",
                    "Operating goals: Stabilize delivery",
                ],
                "environment_constraints": ["workspace draft/edit allowed"],
                "allowed_capabilities": ["system:dispatch_query"],
                "evidence_expectations": ["operating brief"],
            },
            goal_ids=[],
            agent_ids=["copaw-agent-runner"],
            schedule_ids=[],
        ),
    )

    goal = _create_goal(
        app,
        title="Operate Acme account",
        summary="Prepare the next operating move.",
        status="active",
        priority=1,
    )
    goal_id = goal.id
    app.state.goal_override_repository.upsert_override(
        GoalOverrideRecord(
            goal_id=goal_id,
            compiler_context={
                "owner_agent_id": "copaw-agent-runner",
                "industry_instance_id": "industry-v1-acme",
                "industry_role_id": "execution-core",
            },
        ),
    )

    detail = client.get(f"/goals/{goal_id}/detail")

    assert detail.status_code == 200
    payload = detail.json()
    assert payload["industry"]["instance_id"] == "industry-v1-acme"
    assert payload["industry"]["execution_core_identity"]["agent_id"] == "copaw-agent-runner"
    assert payload["industry"]["execution_core_identity"]["identity_label"] == (
        "Acme Operations Cell / 白泽执行中枢"
    )


def test_compile_goal_injects_strategy_memory_context(tmp_path) -> None:
    app = _build_goal_app(tmp_path)

    app.state.industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-v1-acme",
            label="Acme Operations Cell",
            summary="Execution shell for Acme operations.",
            owner_scope="industry-v1-acme",
            status="active",
            profile_payload={"industry": "Operations"},
            team_payload={
                "team_id": "industry-v1-acme",
                "label": "Acme Operations Cell",
                "summary": "Execution shell for Acme operations.",
                "agents": [
                    {
                        "role_id": "execution-core",
                        "agent_id": "copaw-agent-runner",
                        "name": "白泽执行中枢",
                        "role_name": "白泽执行中枢",
                    },
                ],
            },
            execution_core_identity_payload={
                "binding_id": "industry-v1-acme:execution-core",
                "agent_id": "copaw-agent-runner",
                "role_id": "execution-core",
                "industry_instance_id": "industry-v1-acme",
                "identity_label": "Acme Operations Cell / 白泽执行中枢",
                "industry_label": "Acme Operations Cell",
                "industry_summary": "Execution shell for Acme operations.",
                "role_name": "白泽执行中枢",
                "role_summary": "Operate as Acme's execution brain.",
                "mission": "Turn Acme operational goals into coordinated actions.",
                "thinking_axes": ["经营目标", "风险"],
                "environment_constraints": ["workspace draft/edit allowed"],
                "allowed_capabilities": ["system:dispatch_query"],
                "evidence_expectations": ["operating brief"],
            },
            goal_ids=[],
            agent_ids=["copaw-agent-runner"],
            schedule_ids=[],
        ),
    )
    app.state.strategy_memory_service.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-v1-acme:copaw-agent-runner",
            scope_type="industry",
            scope_id="industry-v1-acme",
            owner_agent_id="copaw-agent-runner",
            owner_scope="industry-v1-acme",
            industry_instance_id="industry-v1-acme",
            title="Acme 战略记忆",
            summary="先稳住经营主线，再推进执行闭环。",
            mission="统筹执行、分派专业角色、核验证据。",
            north_star="稳定交付并持续增长",
            priority_order=["稳住交付", "推进增长"],
            delegation_policy=["优先分派给专业角色"],
            direct_execution_policy=[
                "主脑不直接使用浏览器、桌面、文件编辑等叶子执行能力。",
                "没有合适执行位时，先补位、改派或请求确认，不让主脑兜底变成执行员。",
            ],
            execution_constraints=["高风险动作必须确认"],
            evidence_requirements=["每次外部动作保留证据"],
            active_goal_titles=["Operate Acme account"],
            teammate_contracts=[],
        ),
    )

    goal = _create_goal(
        app,
        title="Operate Acme account",
        summary="Prepare the next operating move.",
        status="active",
        priority=1,
    )
    goal_id = goal.id
    app.state.goal_override_repository.upsert_override(
        GoalOverrideRecord(
            goal_id=goal_id,
            compiler_context={
                "owner_agent_id": "copaw-agent-runner",
                "industry_instance_id": "industry-v1-acme",
                "industry_role_id": "execution-core",
            },
        ),
    )

    compiler_payload = _compile_goal(app, goal_id)[0]["payload"]["compiler"]
    assert compiler_payload["strategy_id"] == "strategy:industry:industry-v1-acme:copaw-agent-runner"
    assert compiler_payload["strategy_items"]
    assert any("North star: 稳定交付并持续增长" in item for item in compiler_payload["strategy_items"])


def test_goal_detail_exposes_strategy_memory_from_industry_instance(tmp_path) -> None:
    app = _build_goal_app(tmp_path)
    client = TestClient(app)

    app.state.industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-v1-acme",
            label="Acme Operations Cell",
            summary="Execution shell for Acme operations.",
            owner_scope="industry-v1-acme",
            status="active",
            profile_payload={"industry": "Operations"},
            team_payload={"team_id": "industry-v1-acme", "label": "Acme Operations Cell", "summary": "Execution shell for Acme operations.", "agents": []},
            execution_core_identity_payload={
                "binding_id": "industry-v1-acme:execution-core",
                "agent_id": "copaw-agent-runner",
                "role_id": "execution-core",
                "industry_instance_id": "industry-v1-acme",
                "identity_label": "Acme Operations Cell / 白泽执行中枢",
                "industry_label": "Acme Operations Cell",
                "role_name": "白泽执行中枢",
            },
            goal_ids=[],
            agent_ids=["copaw-agent-runner"],
            schedule_ids=[],
        ),
    )
    app.state.strategy_memory_service.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-v1-acme:copaw-agent-runner",
            scope_type="industry",
            scope_id="industry-v1-acme",
            owner_agent_id="copaw-agent-runner",
            owner_scope="industry-v1-acme",
            industry_instance_id="industry-v1-acme",
            title="Acme 战略记忆",
            summary="先稳住经营主线，再推进执行闭环。",
            mission="统筹执行、分派专业角色、核验证据。",
            north_star="稳定交付并持续增长",
            priority_order=["稳住交付"],
            delegation_policy=["优先分派给专业角色"],
            direct_execution_policy=[
                "主脑不直接使用浏览器、桌面、文件编辑等叶子执行能力。",
                "没有合适执行位时，先补位、改派或请求确认，不让主脑兜底变成执行员。",
            ],
            execution_constraints=["高风险动作必须确认"],
            evidence_requirements=["每次外部动作保留证据"],
            teammate_contracts=[],
        ),
    )

    goal = _create_goal(
        app,
        title="Operate Acme account",
        summary="Prepare the next operating move.",
        status="active",
        priority=1,
    )
    goal_id = goal.id
    app.state.goal_override_repository.upsert_override(
        GoalOverrideRecord(
            goal_id=goal_id,
            compiler_context={
                "owner_agent_id": "copaw-agent-runner",
                "industry_instance_id": "industry-v1-acme",
                "industry_role_id": "execution-core",
            },
        ),
    )

    detail = client.get(f"/goals/{goal_id}/detail")

    assert detail.status_code == 200
    payload = detail.json()
    assert payload["industry"]["strategy_memory"]["strategy_id"] == (
        "strategy:industry:industry-v1-acme:copaw-agent-runner"
    )
    assert payload["industry"]["strategy_memory"]["north_star"] == "稳定交付并持续增长"
