# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    SessionMountRepository,
)
from copaw.kernel import ActorMailboxService, ActorWorker
from copaw.state.agent_experience_service import AgentExperienceMemoryService
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state import AgentRuntimeRecord, SQLiteStateStore
from copaw.state.repositories import (
    SqliteAgentCheckpointRepository,
    SqliteAgentLeaseRepository,
    SqliteAgentMailboxRepository,
    SqliteKnowledgeChunkRepository,
    SqliteAgentRuntimeRepository,
)


class _WaitingConfirmDispatcher:
    def submit(self, task):
        return SimpleNamespace(
            phase="waiting-confirm",
            summary="Awaiting operator confirmation.",
        )


class _SlowDispatcher:
    def __init__(self) -> None:
        self.submitted = []

    def submit(self, task):
        self.submitted.append(task.id)
        return SimpleNamespace(phase="executing")

    async def execute_task(self, task_id: str):
        await asyncio.sleep(0.05)
        return SimpleNamespace(
            phase="completed",
            summary=f"Completed {task_id}",
            model_dump=lambda mode="json": {
                "phase": "completed",
                "summary": f"Completed {task_id}",
            },
        )


class _CancelledDispatcher:
    def submit(self, task):
        return SimpleNamespace(phase="executing")

    async def execute_task(self, task_id: str):
        return SimpleNamespace(
            phase="cancelled",
            summary=f"Cancelled {task_id}",
            model_dump=lambda mode="json": {
                "phase": "cancelled",
                "summary": f"Cancelled {task_id}",
            },
        )


class _SubmitCancelledDispatcher:
    def submit(self, task):
        return SimpleNamespace(
            phase="cancelled",
            summary=f"Cancelled {task.id} before execution",
        )


class _InterruptibleDispatcher:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled: list[tuple[str, str]] = []

    def cancel_task(self, task_id: str, *, resolution: str):
        self.cancelled.append((task_id, resolution))

    async def execute_task(self, task_id: str):
        self.started.set()
        await asyncio.Event().wait()


def _build_mailbox_runtime(tmp_path):
    state_store = SQLiteStateStore(tmp_path / "actor-worker-state.db")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    mailbox_repository = SqliteAgentMailboxRepository(state_store)
    checkpoint_repository = SqliteAgentCheckpointRepository(state_store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry:test:agent-1",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="waiting",
            industry_instance_id="industry-test",
            industry_role_id="operator",
            display_name="Agent 1",
            role_name="Operator",
        ),
    )
    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
    )
    return mailbox_service, runtime_repository, checkpoint_repository, state_store


def test_actor_worker_blocks_waiting_confirm_mailbox_items(tmp_path) -> None:
    mailbox_service, runtime_repository, checkpoint_repository, _state_store = _build_mailbox_runtime(
        tmp_path,
    )
    item = mailbox_service.enqueue_item(
        agent_id="agent-1",
        title="Confirm outbound change",
        capability_ref="system:apply_role",
        payload={"payload": {"agent_id": "agent-1"}, "risk_level": "confirm"},
    )
    worker = ActorWorker(
        worker_id="actor-worker-test",
        mailbox_service=mailbox_service,
        kernel_dispatcher=_WaitingConfirmDispatcher(),
    )

    handled = asyncio.run(worker.run_once("agent-1"))

    assert handled is True
    stored = mailbox_service.get_item(item.id)
    assert stored is not None
    assert stored.status == "blocked"
    assert stored.error_summary == "Awaiting operator confirmation."
    runtime = runtime_repository.get_runtime("agent-1")
    assert runtime is not None
    assert runtime.runtime_status == "blocked"
    checkpoints = checkpoint_repository.list_checkpoints(agent_id="agent-1", limit=None)
    assert checkpoints[0].phase == "waiting-confirm"
    assert checkpoints[0].status == "ready"


def test_actor_mailbox_projects_claim_and_execution_statuses(tmp_path) -> None:
    mailbox_service, runtime_repository, _checkpoint_repository, _state_store = _build_mailbox_runtime(
        tmp_path,
    )
    item = mailbox_service.enqueue_item(
        agent_id="agent-1",
        task_id="task-claim",
        title="Claim task",
        capability_ref="system:dispatch_query",
    )

    queued_runtime = runtime_repository.get_runtime("agent-1")
    assert queued_runtime is not None
    assert queued_runtime.runtime_status == "queued"

    claimed = mailbox_service.claim_next("agent-1", worker_id="actor-worker-test")
    assert claimed is not None
    assert claimed.id == item.id
    claimed_runtime = runtime_repository.get_runtime("agent-1")
    assert claimed_runtime is not None
    assert claimed_runtime.runtime_status == "claimed"

    mailbox_service.start_item(
        item.id,
        worker_id="actor-worker-test",
        task_id="task-claim",
    )
    executing_runtime = runtime_repository.get_runtime("agent-1")
    assert executing_runtime is not None
    assert executing_runtime.runtime_status == "executing"


def test_actor_worker_heartbeats_actor_lease_during_long_execution(tmp_path, monkeypatch) -> None:
    mailbox_service, _runtime_repository, _checkpoint_repository, state_store = _build_mailbox_runtime(
        tmp_path,
    )
    mailbox_service.enqueue_item(
        agent_id="agent-1",
        task_id="task-1",
        title="Long task",
        capability_ref="system:dispatch_query",
    )
    lease_repository = SqliteAgentLeaseRepository(state_store)
    environment_service = EnvironmentService(
        registry=EnvironmentRegistry(repository=EnvironmentRepository(state_store)),
        lease_ttl_seconds=30,
    )
    environment_service.set_agent_lease_repository(lease_repository)
    dispatcher = _SlowDispatcher()

    heartbeat_calls: list[str] = []
    original_heartbeat = environment_service.heartbeat_actor_lease

    def _record_heartbeat(*args, **kwargs):
        heartbeat_calls.append(args[0])
        return original_heartbeat(*args, **kwargs)

    monkeypatch.setattr(environment_service, "heartbeat_actor_lease", _record_heartbeat)

    worker = ActorWorker(
        worker_id="actor-worker-test",
        mailbox_service=mailbox_service,
        kernel_dispatcher=dispatcher,
        environment_service=environment_service,
        lease_ttl_seconds=30,
        lease_heartbeat_interval_seconds=0.01,
    )

    handled = asyncio.run(worker.run_once("agent-1"))

    assert handled is True
    assert heartbeat_calls
    lease = lease_repository.get_lease("actor:agent-1")
    assert lease is not None
    assert lease.lease_status == "released"


def test_actor_worker_releases_shared_writer_lease_when_run_is_cancelled(tmp_path) -> None:
    mailbox_service, _runtime_repository, _checkpoint_repository, state_store = _build_mailbox_runtime(
        tmp_path,
    )
    item = mailbox_service.enqueue_item(
        agent_id="agent-1",
        task_id="task-writer",
        title="Locked writer task",
        capability_ref="system:dispatch_query",
        payload={
            "payload": {
                "meta": {
                    "access_mode": "writer",
                    "lease_class": "exclusive-writer",
                    "writer_lock_scope": "workbook:weekly-report",
                },
            },
        },
        metadata={
            "access_mode": "writer",
            "lease_class": "exclusive-writer",
            "writer_lock_scope": "workbook:weekly-report",
        },
    )
    lease_repository = SqliteAgentLeaseRepository(state_store)
    env_repository = EnvironmentRepository(state_store)
    session_repository = SessionMountRepository(state_store)
    environment_service = EnvironmentService(
        registry=EnvironmentRegistry(
            repository=env_repository,
            session_repository=session_repository,
        ),
        lease_ttl_seconds=30,
    )
    environment_service.set_session_repository(session_repository)
    environment_service.set_agent_lease_repository(lease_repository)
    dispatcher = _InterruptibleDispatcher()
    worker = ActorWorker(
        worker_id="actor-worker-test",
        mailbox_service=mailbox_service,
        kernel_dispatcher=dispatcher,
        environment_service=environment_service,
        lease_ttl_seconds=30,
        lease_heartbeat_interval_seconds=0.01,
    )

    async def _run() -> bool:
        task = asyncio.create_task(worker.run_once("agent-1"))
        await dispatcher.started.wait()
        active_writer_lease = environment_service.get_shared_writer_lease(
            writer_lock_scope="workbook:weekly-report",
        )
        assert active_writer_lease is not None
        assert active_writer_lease.lease_status == "leased"
        task.cancel()
        return await task

    handled = asyncio.run(_run())

    assert handled is True
    stored = mailbox_service.get_item(item.id)
    assert stored is not None
    assert stored.status == "cancelled"
    writer_lease = environment_service.get_shared_writer_lease(
        writer_lock_scope="workbook:weekly-report",
    )
    assert writer_lease is not None
    assert writer_lease.lease_status == "released"


def test_actor_worker_marks_cancelled_kernel_results_as_cancelled(tmp_path) -> None:
    mailbox_service, runtime_repository, checkpoint_repository, _state_store = _build_mailbox_runtime(
        tmp_path,
    )
    item = mailbox_service.enqueue_item(
        agent_id="agent-1",
        task_id="task-cancelled",
        title="Cancelled task",
        capability_ref="system:dispatch_query",
    )
    worker = ActorWorker(
        worker_id="actor-worker-test",
        mailbox_service=mailbox_service,
        kernel_dispatcher=_CancelledDispatcher(),
    )

    handled = asyncio.run(worker.run_once("agent-1"))

    assert handled is True
    stored = mailbox_service.get_item(item.id)
    assert stored is not None
    assert stored.status == "cancelled"
    runtime = runtime_repository.get_runtime("agent-1")
    assert runtime is not None
    assert runtime.runtime_status == "idle"
    assert runtime.last_error_summary is None
    checkpoints = checkpoint_repository.list_checkpoints(agent_id="agent-1", limit=None)
    assert checkpoints[0].phase == "cancelled"
    assert checkpoints[0].status == "abandoned"


def test_actor_worker_marks_submit_time_cancellations_as_cancelled(tmp_path) -> None:
    mailbox_service, runtime_repository, checkpoint_repository, _state_store = _build_mailbox_runtime(
        tmp_path,
    )
    item = mailbox_service.enqueue_item(
        agent_id="agent-1",
        title="Cancelled before execute",
        capability_ref="system:dispatch_query",
        payload={"payload": {"prompt_text": "skip"}, "risk_level": "guarded"},
    )
    worker = ActorWorker(
        worker_id="actor-worker-test",
        mailbox_service=mailbox_service,
        kernel_dispatcher=_SubmitCancelledDispatcher(),
    )

    handled = asyncio.run(worker.run_once("agent-1"))

    assert handled is True
    stored = mailbox_service.get_item(item.id)
    assert stored is not None
    assert stored.status == "cancelled"
    assert stored.error_summary is not None
    assert stored.error_summary.startswith("Cancelled ktask:")
    runtime = runtime_repository.get_runtime("agent-1")
    assert runtime is not None
    assert runtime.runtime_status == "idle"
    assert runtime.last_error_summary is None
    checkpoints = checkpoint_repository.list_checkpoints(agent_id="agent-1", limit=None)
    assert checkpoints[0].phase == "cancelled"
    assert checkpoints[0].status == "abandoned"


def test_actor_worker_writes_completed_agent_experience_to_long_term_memory(tmp_path) -> None:
    mailbox_service, runtime_repository, _checkpoint_repository, state_store = _build_mailbox_runtime(
        tmp_path,
    )
    item = mailbox_service.enqueue_item(
        agent_id="agent-1",
        task_id="task-completed",
        title="Draft the weekly analysis",
        capability_ref="system:dispatch_query",
        payload={
            "payload": {
                "industry_instance_id": "industry-test",
                "industry_role_id": "operator",
                "owner_scope": "industry-v1-test",
            },
        },
    )
    knowledge_service = StateKnowledgeService(
        repository=SqliteKnowledgeChunkRepository(state_store),
    )
    experience_service = AgentExperienceMemoryService(
        knowledge_service=knowledge_service,
    )
    worker = ActorWorker(
        worker_id="actor-worker-test",
        mailbox_service=mailbox_service,
        kernel_dispatcher=_SlowDispatcher(),
        agent_runtime_repository=runtime_repository,
        experience_memory_service=experience_service,
    )

    handled = asyncio.run(worker.run_once("agent-1"))

    assert handled is True
    memory = knowledge_service.retrieve_memory(
        query="weekly analysis",
        agent_id="agent-1",
        role="operator",
        limit=5,
    )
    assert len(memory) == 1
    assert "状态: completed" in memory[0].content
    assert item.id in memory[0].content
    assert memory[0].document_id == "memory:agent:agent-1"
    task_memory = knowledge_service.retrieve_memory(
        query="weekly analysis",
        scope_type="task",
        scope_id="task-completed",
        task_id="task-completed",
        include_related_scopes=False,
        role="operator",
        limit=5,
    )
    assert len(task_memory) == 1
    assert task_memory[0].document_id == "memory:task:task-completed"


def test_actor_worker_marks_interrupted_runs_as_cancelled(tmp_path) -> None:
    mailbox_service, runtime_repository, checkpoint_repository, _state_store = _build_mailbox_runtime(
        tmp_path,
    )
    item = mailbox_service.enqueue_item(
        agent_id="agent-1",
        task_id="task-running",
        title="Interruptible task",
        capability_ref="system:dispatch_query",
    )
    dispatcher = _InterruptibleDispatcher()
    worker = ActorWorker(
        worker_id="actor-worker-test",
        mailbox_service=mailbox_service,
        kernel_dispatcher=dispatcher,
    )

    async def _run_and_cancel() -> bool:
        task = asyncio.create_task(worker.run_once("agent-1"))
        await dispatcher.started.wait()
        task.cancel()
        return await task

    handled = asyncio.run(_run_and_cancel())

    assert handled is True
    assert dispatcher.cancelled == [("task-running", "cancelled by actor control")]
    stored = mailbox_service.get_item(item.id)
    assert stored is not None
    assert stored.status == "cancelled"
    runtime = runtime_repository.get_runtime("agent-1")
    assert runtime is not None
    assert runtime.runtime_status == "idle"
    checkpoints = checkpoint_repository.list_checkpoints(agent_id="agent-1", limit=None)
    assert checkpoints[0].phase == "cancelled"
    assert checkpoints[0].status == "abandoned"


def test_actor_mailbox_retry_clears_stale_blocked_error(tmp_path) -> None:
    mailbox_service, runtime_repository, _checkpoint_repository, _state_store = _build_mailbox_runtime(
        tmp_path,
    )
    item = mailbox_service.enqueue_item(
        agent_id="agent-1",
        task_id="task-retry",
        title="Retry task",
        capability_ref="system:dispatch_query",
    )

    mailbox_service.fail_item(
        item.id,
        error_summary="Need operator retry.",
        retryable=False,
        task_id="task-retry",
    )
    blocked_runtime = runtime_repository.get_runtime("agent-1")
    assert blocked_runtime is not None
    assert blocked_runtime.runtime_status == "blocked"

    retried = mailbox_service.retry_item(item.id)

    assert retried.status == "queued"
    runtime = runtime_repository.get_runtime("agent-1")
    assert runtime is not None
    assert runtime.runtime_status == "queued"
    assert runtime.last_error_summary is None


def test_actor_mailbox_cancel_actor_task_cancels_kernel_task(tmp_path) -> None:
    cancelled: list[tuple[str, str]] = []

    class _Lifecycle:
        @staticmethod
        def get_task(task_id: str):
            return SimpleNamespace(id=task_id, phase="executing")

    class _Dispatcher:
        lifecycle = _Lifecycle()

        @staticmethod
        def cancel_task(task_id: str, *, resolution: str):
            cancelled.append((task_id, resolution))

    mailbox_service, runtime_repository, checkpoint_repository, _state_store = _build_mailbox_runtime(
        tmp_path,
    )
    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_service._mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
        kernel_dispatcher=_Dispatcher(),
    )
    item = mailbox_service.enqueue_item(
        agent_id="agent-1",
        task_id="task-running",
        title="Running task",
        capability_ref="system:dispatch_query",
    )
    mailbox_service.start_item(
        item.id,
        worker_id="actor-worker-test",
        task_id="task-running",
    )

    result = mailbox_service.cancel_actor_task("agent-1", task_id="task-running")

    assert result["cancelled_kernel_task_ids"] == ["task-running"]
    assert cancelled == [("task-running", "cancelled by actor control")]
