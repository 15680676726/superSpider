# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.runtime_center.state_query import RuntimeCenterStateQueryService
from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    SessionMountRepository,
)
from copaw.evidence import EvidenceLedger
from copaw.kernel import KernelDispatcher, KernelResult, TaskDelegationService
from copaw.kernel.delegation_service import DelegationError
from copaw.kernel.persistence import KernelTaskStore, decode_kernel_task_metadata
from copaw.state import GoalRecord, SQLiteStateStore, TaskRecord, TaskRuntimeRecord, WorkContextRecord
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteGoalRepository,
    SqliteKnowledgeChunkRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
)


class _FakeCapabilityService:
    async def execute_task(self, task):
        return {
            "success": True,
            "summary": f"Executed delegated task {task.id}",
        }


class _FakeIndustryService:
    def get_instance_detail(self, instance_id: str):
        if instance_id != "industry-1":
            return None
        return SimpleNamespace(
            team=SimpleNamespace(
                agents=[
                    {
                        "agent_id": "worker",
                        "role_id": "solution-lead",
                        "role_name": "Worker",
                    }
                ],
            ),
            agents=[
                {
                    "agent_id": "worker",
                    "industry_role_id": "solution-lead",
                    "role_name": "Worker",
                }
            ],
        )


def _seed_parent_task(
    task_repository: SqliteTaskRepository,
    task_runtime_repository: SqliteTaskRuntimeRepository,
    *,
    environment_ref: str = "session:console:execution-core-main",
    owner_agent_id: str = "execution-core-agent",
) -> None:
    task_repository.upsert_task(
        TaskRecord(
            id="task-parent",
            goal_id="goal-1",
            title="Parent task",
            summary="Delegate the work.",
            task_type="system:dispatch_query",
            status="running",
            owner_agent_id=owner_agent_id,
            work_context_id="work-context-parent",
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-parent",
            runtime_status="active",
            current_phase="executing",
            active_environment_id=environment_ref,
            last_owner_agent_id=owner_agent_id,
        ),
    )


def _build_task_store(
    *,
    task_repository: SqliteTaskRepository,
    task_runtime_repository: SqliteTaskRuntimeRepository,
    runtime_frame_repository: SqliteRuntimeFrameRepository,
    decision_repository: SqliteDecisionRequestRepository,
    evidence_ledger: EvidenceLedger,
) -> KernelTaskStore:
    return KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_repository,
        evidence_ledger=evidence_ledger,
    )


def _build_dispatcher(
    *,
    task_repository: SqliteTaskRepository,
    task_runtime_repository: SqliteTaskRuntimeRepository,
    runtime_frame_repository: SqliteRuntimeFrameRepository,
    decision_repository: SqliteDecisionRequestRepository,
    evidence_ledger: EvidenceLedger,
) -> KernelDispatcher:
    return KernelDispatcher(
        task_store=_build_task_store(
            task_repository=task_repository,
            task_runtime_repository=task_runtime_repository,
            runtime_frame_repository=runtime_frame_repository,
            decision_repository=decision_repository,
            evidence_ledger=evidence_ledger,
        ),
        capability_service=_FakeCapabilityService(),
    )


def _build_client(tmp_path, *, with_conflict: bool = False) -> TestClient:
    app = FastAPI()
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(store)
    schedule_repository = SqliteScheduleRepository(store)
    goal_repository = SqliteGoalRepository(store)
    decision_repository = SqliteDecisionRequestRepository(store)
    work_context_repository = SqliteWorkContextRepository(store)

    work_context_repository.upsert_context(
        WorkContextRecord(
            id="work-context-parent",
            title="Customer A thread",
            summary="Track the ongoing execution conversation.",
            context_type="customer-thread",
            status="active",
            context_key="control-thread:customer-a",
            owner_agent_id="execution-core-agent",
            owner_scope="runtime",
        ),
    )

    goal_repository.upsert_goal(
        GoalRecord(
            id="goal-1",
            title="Delegated execution",
            summary="Track parent-child task relationships.",
            status="active",
        ),
    )
    _seed_parent_task(task_repository, task_runtime_repository)

    if with_conflict:
        task_repository.upsert_task(
            TaskRecord(
                id="task-conflict",
                goal_id="goal-1",
                title="Conflicting task",
                summary="Occupies the same session.",
                task_type="system:dispatch_query",
                status="running",
                owner_agent_id="other-worker",
            ),
        )
        task_runtime_repository.upsert_runtime(
            TaskRuntimeRecord(
                task_id="task-conflict",
                runtime_status="active",
                current_phase="executing",
                active_environment_id="session:console:execution-core-main",
                last_owner_agent_id="other-worker",
            ),
        )

    dispatcher = _build_dispatcher(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_repository=decision_repository,
        evidence_ledger=evidence_ledger,
    )

    app.state.state_query_service = RuntimeCenterStateQueryService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        schedule_repository=schedule_repository,
        goal_repository=goal_repository,
        work_context_repository=work_context_repository,
        decision_request_repository=decision_repository,
        evidence_ledger=evidence_ledger,
    )
    app.state.delegation_service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=dispatcher,
        evidence_ledger=evidence_ledger,
        industry_service=_FakeIndustryService(),
    )
    app.include_router(runtime_center_router)
    return TestClient(app)


def test_runtime_center_delegate_task_route_is_retired(tmp_path) -> None:
    client = _build_client(tmp_path)

    delegated = client.post(
        "/runtime-center/tasks/task-parent/delegate",
        json={
            "title": "Worker follow-up",
            "owner_agent_id": "worker",
            "prompt_text": "Review the evidence and draft the next action.",
            "execute": True,
            "channel": "console",
            "industry_instance_id": "industry-1",
            "industry_role_id": "solution-lead",
        },
    )
    assert delegated.status_code == 404

    parent_detail = client.get("/runtime-center/tasks/task-parent")
    assert parent_detail.status_code == 200
    detail = parent_detail.json()
    assert detail["stats"]["child_task_count"] == 0
    assert detail["delegation"]["child_results"] == []


def test_runtime_center_delegate_task_route_stays_retired_even_when_conflicts_exist(tmp_path) -> None:
    client = _build_client(tmp_path, with_conflict=True)

    delegated = client.post(
        "/runtime-center/tasks/task-parent/delegate",
        json={
            "title": "Worker follow-up",
            "owner_agent_id": "worker",
            "prompt_text": "Use the shared session.",
        },
    )
    assert delegated.status_code == 404


def test_runtime_center_task_detail_marks_delegation_children_as_compatibility(
    tmp_path,
) -> None:
    client = _build_client(tmp_path)

    result = asyncio.run(
        client.app.state.delegation_service.delegate_task(
            "task-parent",
            title="Worker follow-up",
            owner_agent_id="execution-core-agent",
            target_agent_id="worker",
            prompt_text="Review the evidence and draft the next action.",
            execute=False,
            channel="console",
            industry_instance_id="industry-1",
            industry_role_id="solution-lead",
        ),
    )

    parent_detail = client.get("/runtime-center/tasks/task-parent")
    assert parent_detail.status_code == 200
    child_results = parent_detail.json()["delegation"]["child_results"]

    assert len(child_results) == 1
    assert child_results[0]["id"] == result["child_task_id"]
    assert child_results[0]["execution_source"] == "executor-runtime"
    assert child_results[0]["formal_surface"] is True


def test_delegation_service_execute_true_uses_direct_child_run_formal_path(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(store)
    decision_repository = SqliteDecisionRequestRepository(store)
    _seed_parent_task(task_repository, task_runtime_repository)

    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=_build_dispatcher(
            task_repository=task_repository,
            task_runtime_repository=task_runtime_repository,
            runtime_frame_repository=runtime_frame_repository,
            decision_repository=decision_repository,
            evidence_ledger=evidence_ledger,
        ),
        evidence_ledger=evidence_ledger,
    )

    result = asyncio.run(
        service.delegate_task(
            "task-parent",
            title="Worker follow-up",
            owner_agent_id="execution-core-agent",
            target_agent_id="worker",
            prompt_text="Review the evidence and draft the next action.",
            execute=True,
            channel="console",
        ),
    )

    assert result["mailbox_id"] is None
    assert result["dispatch_status"] == "completed"
    assert result["routes"]["mailbox"] is None
    assert result["latest_result_summary"]
    child_runtime = task_runtime_repository.get_runtime(result["child_task_id"])
    assert child_runtime is not None
    assert child_runtime.runtime_status in {"active", "terminated"}


def test_delegation_service_blocks_shared_writer_scope_held_by_other_agent(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(store)
    decision_repository = SqliteDecisionRequestRepository(store)
    env_repository = EnvironmentRepository(store)
    session_repository = SessionMountRepository(store)
    environment_service = EnvironmentService(
        registry=EnvironmentRegistry(
            repository=env_repository,
            session_repository=session_repository,
        ),
        lease_ttl_seconds=120,
    )
    environment_service.set_session_repository(session_repository)
    _seed_parent_task(
        task_repository,
        task_runtime_repository,
        environment_ref="desktop-app:excel:weekly-report",
    )

    environment_service.acquire_shared_writer_lease(
        writer_lock_scope="workbook:weekly-report",
        owner="other-worker",
        metadata={"environment_ref": "desktop-app:excel:weekly-report"},
    )
    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=_build_dispatcher(
            task_repository=task_repository,
            task_runtime_repository=task_runtime_repository,
            runtime_frame_repository=runtime_frame_repository,
            decision_repository=decision_repository,
            evidence_ledger=evidence_ledger,
        ),
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
    )

    with pytest.raises(DelegationError) as exc_info:
        asyncio.run(
            service.delegate_task(
                "task-parent",
                title="Writer follow-up",
                owner_agent_id="execution-core-agent",
                target_agent_id="worker",
                prompt_text="Continue the Excel writer step.",
                execute=False,
                channel="console",
                access_mode="writer",
                lease_class="exclusive-writer",
                writer_lock_scope="workbook:weekly-report",
            ),
        )

    assert exc_info.value.code == "environment_conflict"
    assert "workbook:weekly-report" in str(exc_info.value)


def test_delegation_service_records_dispatch_request_envelope_for_dispatch_query(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(store)
    decision_repository = SqliteDecisionRequestRepository(store)
    _seed_parent_task(task_repository, task_runtime_repository)

    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=_build_dispatcher(
            task_repository=task_repository,
            task_runtime_repository=task_runtime_repository,
            runtime_frame_repository=runtime_frame_repository,
            decision_repository=decision_repository,
            evidence_ledger=evidence_ledger,
        ),
        evidence_ledger=evidence_ledger,
    )

    result = asyncio.run(
        service.delegate_task(
            "task-parent",
            title="Worker follow-up",
            owner_agent_id="execution-core-agent",
            target_agent_id="worker",
            prompt_text="Review the evidence and draft the next action.",
            execute=False,
            channel="console",
            session_id="industry-chat:industry-1:execution-core",
            user_id="worker",
            work_context_id="work-context-parent",
            context_key="control-thread:industry-1",
        ),
    )

    child_task = task_repository.get_task(result["child_task_id"])
    assert child_task is not None
    metadata = decode_kernel_task_metadata(child_task.acceptance_criteria)
    payload = metadata.get("payload")
    assert isinstance(payload, dict)
    dispatch_request = payload.get("dispatch_request")
    assert isinstance(dispatch_request, dict)
    assert dispatch_request["session_id"] == "industry-chat:industry-1:execution-core"
    assert dispatch_request["work_context_id"] == "work-context-parent"
    assert payload["request"] == dispatch_request
    request_context = payload.get("request_context")
    assert isinstance(request_context, dict)
    assert request_context["session_id"] == dispatch_request["session_id"]
    assert request_context["work_context_id"] == dispatch_request["work_context_id"]
    assert request_context["context_key"] == "control-thread:industry-1"
    assert request_context.get("request") is None


def test_delegation_service_execute_true_surfaces_cancelled_child_run_without_mailbox(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    _seed_parent_task(task_repository, task_runtime_repository)

    class _CancelledDispatcher:
        def submit(self, task):
            return SimpleNamespace(phase="executing", summary="Queued delegated task")

        async def execute_task(self, task_id: str):
            return KernelResult(
                task_id=task_id,
                trace_id="trace-direct-child-run",
                success=False,
                phase="cancelled",
                summary=f"Cancelled {task_id}",
            )

    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=_CancelledDispatcher(),
        evidence_ledger=evidence_ledger,
    )

    result = asyncio.run(
        service.delegate_task(
            "task-parent",
            title="Worker follow-up",
            owner_agent_id="execution-core-agent",
            target_agent_id="worker",
            prompt_text="Review the evidence and stop the task.",
            execute=True,
            channel="console",
        ),
    )

    assert result["mailbox_id"] is None
    assert result["dispatch_status"] == "cancelled"
    assert result["dispatch_result"]["phase"] == "cancelled"


def test_delegation_service_execute_true_preserves_direct_child_run_output_and_evidence(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    _seed_parent_task(task_repository, task_runtime_repository)

    class _QueuedDispatcher:
        def submit(self, task):
            return SimpleNamespace(phase="executing", summary="Queued delegated task")

        async def execute_task(self, task_id: str):
            return KernelResult(
                task_id=task_id,
                trace_id="trace-child",
                success=True,
                phase="completed",
                summary=f"Completed {task_id}",
                evidence_id="evidence-child-1",
                output={
                    "artifact_path": "D:/word/copaw/out.md",
                    "artifact_kind": "file",
                },
            )

    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=_QueuedDispatcher(),
        evidence_ledger=evidence_ledger,
    )

    result = asyncio.run(
        service.delegate_task(
            "task-parent",
            title="Worker follow-up",
            owner_agent_id="execution-core-agent",
            target_agent_id="worker",
            prompt_text="Create the file and report back.",
            execute=True,
            channel="console",
        ),
    )

    assert result["dispatch_status"] == "completed"
    assert result["dispatch_result"]["phase"] == "completed"
    assert result["dispatch_result"]["evidence_id"] == "evidence-child-1"
    assert result["dispatch_result"]["output"] == {
        "artifact_path": "D:/word/copaw/out.md",
        "artifact_kind": "file",
    }
    assert result["mailbox_id"] is None


def test_preview_delegation_ignores_cold_compiled_tasks_for_overload_and_conflicts(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(store)
    decision_repository = SqliteDecisionRequestRepository(store)
    _seed_parent_task(
        task_repository,
        task_runtime_repository,
        environment_ref="session:console:shared",
    )

    for task_id, owner_agent_id in (
        ("compiled-cold-worker", "worker"),
        ("compiled-cold-other", "other-worker"),
    ):
        task_repository.upsert_task(
            TaskRecord(
                id=task_id,
                goal_id="goal-1",
                title=f"Compiled step for {owner_agent_id}",
                summary="Compiled but not started.",
                task_type="system:dispatch_query",
                status="queued",
                owner_agent_id=owner_agent_id,
            ),
        )
        task_runtime_repository.upsert_runtime(
            TaskRuntimeRecord(
                task_id=task_id,
                runtime_status="cold",
                current_phase="compiled",
                active_environment_id="session:console:shared",
                last_owner_agent_id=owner_agent_id,
            ),
        )

    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=_build_dispatcher(
            task_repository=task_repository,
            task_runtime_repository=task_runtime_repository,
            runtime_frame_repository=runtime_frame_repository,
            decision_repository=decision_repository,
            evidence_ledger=evidence_ledger,
        ),
        evidence_ledger=evidence_ledger,
    )

    governance = service.preview_delegation(
        parent_task_id="task-parent",
        owner_agent_id="worker",
        environment_ref="session:console:shared",
    )

    assert governance["blocked"] is False
    assert governance["conflict_count"] == 0
    assert governance["overloaded"] is False


def test_delegation_service_can_opt_out_of_parent_environment_inheritance(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(store)
    decision_repository = SqliteDecisionRequestRepository(store)
    _seed_parent_task(
        task_repository,
        task_runtime_repository,
        environment_ref="desktop-app:excel:weekly-report",
    )

    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=_build_dispatcher(
            task_repository=task_repository,
            task_runtime_repository=task_runtime_repository,
            runtime_frame_repository=runtime_frame_repository,
            decision_repository=decision_repository,
            evidence_ledger=evidence_ledger,
        ),
        evidence_ledger=evidence_ledger,
    )

    result = asyncio.run(
        service.delegate_task(
            "task-parent",
            title="Worker follow-up",
            owner_agent_id="execution-core-agent",
            target_agent_id="worker",
            prompt_text="Use a fresh runtime.",
            execute=False,
            channel="console",
            inherit_environment_ref=False,
        ),
    )

    child_task = task_repository.get_task(result["child_task_id"])
    assert child_task is not None
    metadata = decode_kernel_task_metadata(child_task.acceptance_criteria)
    request_context = (metadata.get("payload") or {}).get("request_context") or {}
    assert request_context.get("environment_ref") is None
