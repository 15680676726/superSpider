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
from copaw.kernel import (
    ActorMailboxService,
    ActorWorker,
    KernelDispatcher,
    KernelResult,
    TaskDelegationService,
)
from copaw.kernel.delegation_service import DelegationError
from copaw.kernel.persistence import decode_kernel_task_metadata
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
            active_environment_id="desktop-app:excel:weekly-report",
            last_owner_agent_id="execution-core-agent",
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
    environment_service.acquire_shared_writer_lease(
        writer_lock_scope="workbook:weekly-report",
        owner="other-worker",
        metadata={"environment_ref": "desktop-app:excel:weekly-report"},
    )
    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=dispatcher,
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


def test_delegation_service_execute_true_uses_supervisor_owned_completion_cleanup(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
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
    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
    )

    class _QueuedDispatcher:
        def submit(self, task):
            return SimpleNamespace(phase="executing", summary="Queued delegated task")

        async def execute_task(self, task_id: str):
            raise AssertionError("delegation service must not bypass the actor supervisor")

    class _CompletingSupervisor:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def run_agent_once(self, agent_id: str) -> bool:
            self.calls.append(agent_id)
            mailbox_item = mailbox_service.list_items(agent_id=agent_id, limit=1)[0]
            mailbox_service.start_item(
                mailbox_item.id,
                worker_id="copaw-actor-worker",
                task_id=mailbox_item.task_id,
            )
            checkpoint = mailbox_service.create_checkpoint(
                agent_id=agent_id,
                mailbox_id=mailbox_item.id,
                task_id=mailbox_item.task_id,
                checkpoint_kind="task-result",
                status="applied",
                phase="completed",
                conversation_thread_id=mailbox_item.conversation_thread_id,
                summary=f"Completed {mailbox_item.task_id}",
            )
            mailbox_service.complete_item(
                mailbox_item.id,
                result_summary=f"Completed {mailbox_item.task_id}",
                checkpoint_id=checkpoint.id if checkpoint is not None else None,
                task_id=mailbox_item.task_id,
            )
            return True

    supervisor = _CompletingSupervisor()
    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=_QueuedDispatcher(),
        evidence_ledger=evidence_ledger,
        actor_mailbox_service=mailbox_service,
        actor_supervisor=supervisor,
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

    assert supervisor.calls == ["worker"]
    assert result["dispatch_status"] == "completed"
    assert result["dispatch_result"]["phase"] == "completed"
    assert result["latest_result_summary"] == f"Completed {result['child_task_id']}"
    checkpoints = checkpoint_repository.list_checkpoints(agent_id="worker", limit=None)
    assert len(checkpoints) == 1
    assert checkpoints[0].phase == "completed"


def test_delegation_service_execute_true_keeps_mailbox_owned_by_worker_when_target_busy(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
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
            runtime_status="executing",
            industry_instance_id="industry-v1-ops",
            industry_role_id="solution-lead",
            display_name="Worker",
            role_name="Worker",
        ),
    )
    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
    )

    class _QueuedDispatcher:
        def submit(self, task):
            return SimpleNamespace(phase="executing", summary="Queued delegated task")

        async def execute_task(self, task_id: str):
            raise AssertionError("delegation service must not take over worker-owned runs")

    class _BusySupervisor:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def run_agent_once(self, agent_id: str) -> bool:
            self.calls.append(agent_id)
            return False

    supervisor = _BusySupervisor()
    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=_QueuedDispatcher(),
        evidence_ledger=evidence_ledger,
        actor_mailbox_service=mailbox_service,
        actor_supervisor=supervisor,
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

    assert supervisor.calls == ["worker"]
    assert result["dispatch_status"] == "queued"
    assert result["latest_result_summary"] == "Queued delegated task"
    mailbox_item = mailbox_repository.get_item(result["mailbox_id"])
    assert mailbox_item is not None
    assert mailbox_item.status == "queued"
    checkpoints = checkpoint_repository.list_checkpoints(agent_id="worker", limit=None)
    assert checkpoints == []


def test_delegation_service_records_dispatch_request_envelope_for_dispatch_query(
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
            work_context_id="work-context-parent",
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
    assert isinstance(metadata, dict)
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


def test_delegation_service_execute_true_marks_cancelled_child_mailbox_as_cancelled(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
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
    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
    )

    class _CancelledDispatcher:
        def submit(self, task):
            return SimpleNamespace(phase="executing", summary="Queued delegated task")

        async def execute_task(self, task_id: str):
            raise AssertionError("delegation service must not bypass the actor supervisor")

    class _CancellingSupervisor:
        async def run_agent_once(self, agent_id: str) -> bool:
            mailbox_item = mailbox_service.list_items(agent_id=agent_id, limit=1)[0]
            mailbox_service.start_item(
                mailbox_item.id,
                worker_id="copaw-actor-worker",
                task_id=mailbox_item.task_id,
            )
            checkpoint = mailbox_service.create_checkpoint(
                agent_id=agent_id,
                mailbox_id=mailbox_item.id,
                task_id=mailbox_item.task_id,
                checkpoint_kind="task-result",
                status="abandoned",
                phase="cancelled",
                conversation_thread_id=mailbox_item.conversation_thread_id,
                summary=f"Cancelled {mailbox_item.task_id}",
            )
            mailbox_service.cancel_item(
                mailbox_item.id,
                reason="Cancelled by delegated worker",
                checkpoint_id=checkpoint.id if checkpoint is not None else None,
                task_id=mailbox_item.task_id,
            )
            return True

    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=_CancelledDispatcher(),
        evidence_ledger=evidence_ledger,
        actor_mailbox_service=mailbox_service,
        actor_supervisor=_CancellingSupervisor(),
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

    assert result["mailbox_id"] is not None
    assert result["dispatch_status"] == "cancelled"
    mailbox_item = mailbox_repository.get_item(result["mailbox_id"])
    assert mailbox_item is not None
    assert mailbox_item.status == "cancelled"
    checkpoints = checkpoint_repository.list_checkpoints(agent_id="worker", limit=None)
    assert checkpoints[0].phase == "cancelled"
    assert checkpoints[0].status == "abandoned"


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
