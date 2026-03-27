# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.runtime_center.state_query import RuntimeCenterStateQueryService
from copaw.evidence import EvidenceLedger
from copaw.kernel import ActorMailboxService, ActorWorker, KernelDispatcher, TaskDelegationService
from copaw.kernel.persistence import KernelTaskStore
from copaw.state.agent_experience_service import AgentExperienceMemoryService
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state import (
    AgentRuntimeRecord,
    GoalRecord,
    SQLiteStateStore,
    TaskRecord,
    TaskRuntimeRecord,
    WorkContextRecord,
)
from copaw.state.repositories import (
    SqliteAgentCheckpointRepository,
    SqliteAgentMailboxRepository,
    SqliteAgentRuntimeRepository,
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
    task_repository.upsert_task(
        TaskRecord(
            id="task-parent",
            goal_id="goal-1",
            title="Execution core task",
            summary="Split the work.",
            task_type="system:dispatch_query",
            status="running",
            owner_agent_id="execution-core-agent",
            work_context_id="work-context-parent",
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-parent",
            runtime_status="active",
            current_phase="delegating",
            active_environment_id="session:console:execution-core-main",
            last_owner_agent_id="execution-core-agent",
        ),
    )

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

    kernel_task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_repository,
        evidence_ledger=evidence_ledger,
    )
    dispatcher = KernelDispatcher(
        task_store=kernel_task_store,
        capability_service=_FakeCapabilityService(),
    )

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


def test_delegation_service_execute_true_still_lands_mailbox(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(store)
    decision_repository = SqliteDecisionRequestRepository(store)
    runtime_repository = SqliteAgentRuntimeRepository(store)
    mailbox_repository = SqliteAgentMailboxRepository(store)
    checkpoint_repository = SqliteAgentCheckpointRepository(store)

    task_repository.upsert_task(
        TaskRecord(
            id="task-parent",
            goal_id="goal-1",
            title="Parent task",
            summary="Delegate the work.",
            task_type="system:dispatch_query",
            status="running",
            owner_agent_id="execution-core-agent",
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-parent",
            runtime_status="active",
            current_phase="executing",
            active_environment_id="session:console:execution-core-main",
            last_owner_agent_id="execution-core-agent",
        ),
    )
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="worker",
            actor_key="industry-v1-ops:worker",
            actor_fingerprint="fp-worker",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="solution-lead",
            display_name="Worker",
            role_name="Worker",
        ),
    )

    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_repository,
        evidence_ledger=evidence_ledger,
    )
    dispatcher = KernelDispatcher(
        task_store=task_store,
        capability_service=_FakeCapabilityService(),
    )
    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
    )
    knowledge_service = StateKnowledgeService(
        repository=SqliteKnowledgeChunkRepository(store),
    )
    experience_service = AgentExperienceMemoryService(
        knowledge_service=knowledge_service,
    )
    worker = ActorWorker(
        worker_id="test-actor-worker",
        mailbox_service=mailbox_service,
        kernel_dispatcher=dispatcher,
        agent_runtime_repository=runtime_repository,
        experience_memory_service=experience_service,
    )

    class _DirectSupervisor:
        async def run_agent_once(self, agent_id: str) -> bool:
            return await worker.run_once(agent_id)

    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=dispatcher,
        evidence_ledger=evidence_ledger,
        actor_mailbox_service=mailbox_service,
        actor_supervisor=_DirectSupervisor(),
        experience_memory_service=experience_service,
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

    assert result["mailbox_id"] is not None
    assert result["dispatch_status"] == "completed"
    assert result["latest_result_summary"]
    mailbox_item = mailbox_repository.get_item(result["mailbox_id"])
    assert mailbox_item is not None
    assert mailbox_item.status == "completed"
    assert mailbox_item.task_id == result["child_task_id"]
    memory = knowledge_service.retrieve_memory(
        query="Worker follow-up",
        agent_id="worker",
        role="solution-lead",
        limit=5,
    )
    assert len(memory) == 1
    assert "状态: completed" in memory[0].content
    assert result["child_task_id"] in memory[0].content
    task_memory = knowledge_service.retrieve_memory(
        query="Worker follow-up",
        scope_type="task",
        scope_id=result["child_task_id"],
        task_id=result["child_task_id"],
        include_related_scopes=False,
        role="solution-lead",
        limit=5,
    )
    assert len(task_memory) == 1
    assert task_memory[0].document_id == f"memory:task:{result['child_task_id']}"


def test_preview_delegation_ignores_cold_compiled_tasks_for_overload_and_conflicts(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(store)
    decision_repository = SqliteDecisionRequestRepository(store)

    task_repository.upsert_task(
        TaskRecord(
            id="task-parent",
            goal_id="goal-1",
            title="Parent task",
            summary="Delegate the work.",
            task_type="system:dispatch_query",
            status="running",
            owner_agent_id="execution-core-agent",
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-parent",
            runtime_status="active",
            current_phase="executing",
            active_environment_id="session:console:shared",
            last_owner_agent_id="execution-core-agent",
        ),
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
                status="created",
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

    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_repository,
        evidence_ledger=evidence_ledger,
    )
    dispatcher = KernelDispatcher(
        task_store=task_store,
        capability_service=_FakeCapabilityService(),
    )
    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=dispatcher,
        evidence_ledger=evidence_ledger,
        overload_threshold=1,
    )

    preview = service.preview_delegation(
        parent_task_id="task-parent",
        owner_agent_id="worker",
        environment_ref="session:console:shared",
    )

    assert preview["blocked"] is False
    assert preview["active_task_count"] == 0
    assert preview["conflict_count"] == 0
