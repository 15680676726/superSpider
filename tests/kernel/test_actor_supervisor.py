# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import time

import pytest

from copaw.evidence import EvidenceLedger
from copaw.kernel import AbsorptionAction, AbsorptionCase, AbsorptionSummary, ActorSupervisor
from copaw.state import AgentRuntimeRecord, SQLiteStateStore
from copaw.state.human_assist_task_service import HumanAssistTaskService
from copaw.state.repositories import SqliteAgentRuntimeRepository, SqliteHumanAssistTaskRepository


class _RecordingWorker:
    def __init__(self) -> None:
        self.starts: list[tuple[str, float]] = []
        self.finishes: list[tuple[str, float]] = []

    async def run_once(self, agent_id: str) -> bool:
        self.starts.append((agent_id, time.perf_counter()))
        await asyncio.sleep(0.05)
        self.finishes.append((agent_id, time.perf_counter()))
        return True


class _InterruptibleWorker:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled: list[str] = []

    async def run_once(self, agent_id: str) -> bool:
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.append(agent_id)
            raise


class _SelectiveFailingWorker:
    def __init__(self) -> None:
        self.started: list[str] = []

    async def run_once(self, agent_id: str) -> bool:
        self.started.append(agent_id)
        await asyncio.sleep(0)
        if agent_id == "agent-1":
            raise RuntimeError("worker crashed")
        return True


class _SelfCancellingAwaitable:
    def __init__(self) -> None:
        self.cancel_calls = 0

    def done(self) -> bool:
        return False

    def cancel(self) -> None:
        self.cancel_calls += 1

    def __await__(self):
        async def _inner():
            current = asyncio.current_task()
            if current is not None:
                current.cancel()
            await asyncio.sleep(0)

        return _inner().__await__()


class _RecordingEventBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, object]]] = []

    def publish(self, *, topic: str, action: str, payload: dict[str, object]) -> None:
        self.events.append((topic, action, payload))


class _RecordingAbsorptionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def scan(self, *, runtimes, mailbox_items, human_assist_tasks, now):
        self.calls.append(
            {
                "runtime_count": len(list(runtimes)),
                "mailbox_count": len(list(mailbox_items)),
                "human_assist_count": len(list(human_assist_tasks)),
                "now": now,
            }
        )
        return AbsorptionSummary(
            active_cases=[
                AbsorptionCase(
                    case_kind="writer-contention",
                    owner_agent_id="agent-1",
                    scope_ref="desktop:sheet-1",
                    recovery_rung="cleanup",
                )
            ],
            case_counts={"writer-contention": 1},
            recovery_counts={"cleanup": 1},
            human_required_case_count=0,
            main_brain_summary="Main brain is absorbing internal execution pressure.",
        )


class _AbsorbingService(_RecordingAbsorptionService):
    def __init__(self, action: AbsorptionAction | None) -> None:
        super().__init__()
        self.action = action
        self.absorb_calls: list[dict[str, object]] = []

    def absorb(self, *, runtimes, mailbox_items, human_assist_tasks, now, **kwargs):
        self.absorb_calls.append(
            {
                "runtime_count": len(list(runtimes)),
                "mailbox_count": len(list(mailbox_items)),
                "human_assist_count": len(list(human_assist_tasks)),
                "now": now,
                "kwargs": dict(kwargs),
            }
        )
        return self.action


def _build_runtime_repository(tmp_path) -> SqliteAgentRuntimeRepository:
    state_store = SQLiteStateStore(tmp_path / "actor-supervisor-state.db")
    repository = SqliteAgentRuntimeRepository(state_store)
    for agent_id in ("agent-1", "agent-2"):
        repository.upsert_runtime(
            AgentRuntimeRecord(
                agent_id=agent_id,
                actor_key=f"industry:test:{agent_id}",
                actor_fingerprint=f"fp-{agent_id}",
                actor_class="industry-dynamic",
                desired_state="active",
                runtime_status="waiting",
                queue_depth=1,
            ),
        )
    return repository


def _build_human_assist_service(tmp_path) -> HumanAssistTaskService:
    store = SQLiteStateStore(tmp_path / "actor-supervisor-human-assist.db")
    return HumanAssistTaskService(
        repository=SqliteHumanAssistTaskRepository(store),
        evidence_ledger=EvidenceLedger(database_path=tmp_path / "actor-supervisor-evidence.sqlite3"),
    )


def test_actor_supervisor_runs_different_agents_in_parallel(tmp_path) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    worker = _RecordingWorker()
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=worker,  # type: ignore[arg-type]
        poll_interval_seconds=0.01,
    )

    ran_any = asyncio.run(supervisor.run_poll_cycle())

    assert ran_any is True
    assert len(worker.starts) == 2
    start_by_agent = {agent_id: started_at for agent_id, started_at in worker.starts}
    assert abs(start_by_agent["agent-1"] - start_by_agent["agent-2"]) < 0.03


def test_actor_supervisor_keeps_single_actor_serialized(tmp_path) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    worker = _RecordingWorker()
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=worker,  # type: ignore[arg-type]
        poll_interval_seconds=0.01,
    )

    async def _run():
        return await asyncio.gather(
            supervisor.run_agent_once("agent-1"),
            supervisor.run_agent_once("agent-1"),
        )

    results = asyncio.run(_run())

    assert results.count(True) == 1
    assert results.count(False) == 1
    assert len(worker.starts) == 1


def test_actor_supervisor_stop_cancels_inflight_agent_runs(tmp_path) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    worker = _InterruptibleWorker()
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=worker,  # type: ignore[arg-type]
        poll_interval_seconds=0.01,
    )

    async def _run():
        task = asyncio.create_task(supervisor.run_agent_once("agent-1"))
        await worker.started.wait()
        await supervisor.stop()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=0.2)

    asyncio.run(_run())

    assert worker.cancelled == ["agent-1"]


@pytest.mark.asyncio
async def test_actor_supervisor_stop_clears_shutdown_cancellation_residue(tmp_path) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=_RecordingWorker(),  # type: ignore[arg-type]
        poll_interval_seconds=0.01,
    )

    await supervisor.start()

    current = asyncio.current_task()
    assert current is not None
    assert current.cancelling() == 0

    try:
        await supervisor.stop()
        assert current.cancelling() == 0
    finally:
        uncancel = getattr(current, "uncancel", None)
        if callable(uncancel):
            while current.cancelling():
                uncancel()


@pytest.mark.asyncio
async def test_actor_supervisor_stop_clears_inflight_run_cancellation_residue(
    tmp_path,
) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    worker = _InterruptibleWorker()
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=worker,  # type: ignore[arg-type]
        poll_interval_seconds=0.01,
    )

    task = asyncio.create_task(supervisor.run_agent_once("agent-1"))
    await worker.started.wait()

    current = asyncio.current_task()
    assert current is not None
    assert current.cancelling() == 0

    try:
        await supervisor.stop()
        assert current.cancelling() == 0
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        uncancel = getattr(current, "uncancel", None)
        if callable(uncancel):
            while current.cancelling():
                uncancel()


@pytest.mark.asyncio
async def test_actor_supervisor_stop_clears_self_cancelled_loop_residue(tmp_path) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=_RecordingWorker(),  # type: ignore[arg-type]
        poll_interval_seconds=0.01,
    )
    supervisor._loop_task = _SelfCancellingAwaitable()  # type: ignore[assignment]

    current = asyncio.current_task()
    assert current is not None
    assert current.cancelling() == 0

    try:
        await supervisor.stop()
        assert current.cancelling() == 0
    finally:
        uncancel = getattr(current, "uncancel", None)
        if callable(uncancel):
            while current.cancelling():
                uncancel()


def test_actor_supervisor_isolates_agent_failure_without_aborting_parallel_poll(
    tmp_path,
) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    worker = _SelectiveFailingWorker()
    event_bus = _RecordingEventBus()
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=worker,  # type: ignore[arg-type]
        runtime_event_bus=event_bus,
        poll_interval_seconds=0.01,
    )

    ran_any = asyncio.run(supervisor.run_poll_cycle())

    assert ran_any is True
    assert set(worker.started) == {"agent-1", "agent-2"}
    failed_runtime = runtime_repository.get_runtime("agent-1")
    assert failed_runtime is not None
    assert failed_runtime.runtime_status == "blocked"
    assert failed_runtime.last_error_summary == "worker crashed"
    assert any(
        topic == "actor-supervisor"
        and action == "agent-failed"
        and payload["agent_id"] == "agent-1"
        for topic, action, payload in event_bus.events
    )


def test_actor_supervisor_run_loop_survives_poll_cycle_exception(tmp_path) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    event_bus = _RecordingEventBus()
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=_RecordingWorker(),  # type: ignore[arg-type]
        runtime_event_bus=event_bus,
        poll_interval_seconds=0.01,
    )
    calls = 0

    async def _flaky_poll_cycle() -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("poll exploded")
        supervisor._stop_event.set()
        return True

    supervisor.run_poll_cycle = _flaky_poll_cycle  # type: ignore[method-assign]

    async def _run() -> None:
        await supervisor.start()
        await asyncio.wait_for(supervisor._loop_task, timeout=0.7)
        await supervisor.stop()

    asyncio.run(_run())

    assert calls >= 2
    assert any(
        topic == "actor-supervisor"
        and action == "poll-failed"
        and payload["error"] == "poll exploded"
        for topic, action, payload in event_bus.events
    )


def test_actor_supervisor_exposes_public_snapshot_for_runtime_center(tmp_path) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry:test:agent-1",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="blocked",
            metadata={
                "supervisor_last_failure_at": "2026-04-04T00:00:00+00:00",
                "supervisor_last_failure_type": "RuntimeError",
            },
        )
    )
    worker = _RecordingWorker()
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=worker,  # type: ignore[arg-type]
        poll_interval_seconds=1.25,
    )

    async def _run() -> dict[str, object]:
        loop_task = asyncio.create_task(asyncio.sleep(0.2), name="copaw-actor-supervisor")
        agent_task = asyncio.create_task(asyncio.sleep(0.2), name="copaw-actor:agent-1")
        supervisor._loop_task = loop_task
        supervisor._agent_tasks["agent-1"] = agent_task
        try:
            await asyncio.sleep(0)
            return supervisor.snapshot()
        finally:
            loop_task.cancel()
            agent_task.cancel()
            await asyncio.gather(loop_task, agent_task, return_exceptions=True)
            supervisor._agent_tasks.clear()
            supervisor._loop_task = None

    snapshot = asyncio.run(_run())

    assert snapshot["available"] is True
    assert snapshot["status"] == "degraded"
    assert snapshot["running"] is True
    assert snapshot["poll_interval_seconds"] == 1.25
    assert snapshot["active_agent_run_count"] == 1
    assert snapshot["blocked_runtime_count"] == 1
    assert snapshot["recent_failure_count"] == 1
    assert snapshot["last_failure_type"] == "RuntimeError"


def test_actor_supervisor_snapshot_includes_absorption_counts(tmp_path) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    absorption_service = _RecordingAbsorptionService()
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=_RecordingWorker(),  # type: ignore[arg-type]
        exception_absorption_service=absorption_service,  # type: ignore[arg-type]
        poll_interval_seconds=0.1,
    )

    snapshot = supervisor.snapshot()

    assert snapshot["absorption_case_count"] == 1
    assert snapshot["human_required_case_count"] == 0
    assert snapshot["absorption_case_counts"] == {"writer-contention": 1}
    assert snapshot["absorption_recovery_counts"] == {"cleanup": 1}
    assert snapshot["absorption_summary"] == (
        "Main brain is absorbing internal execution pressure."
    )
    assert len(absorption_service.calls) == 1


def test_actor_supervisor_run_poll_cycle_refreshes_absorption_summary(tmp_path) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    absorption_service = _RecordingAbsorptionService()
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=_RecordingWorker(),  # type: ignore[arg-type]
        exception_absorption_service=absorption_service,  # type: ignore[arg-type]
        poll_interval_seconds=0.01,
    )

    ran_any = asyncio.run(supervisor.run_poll_cycle())

    assert ran_any is True
    assert len(absorption_service.calls) == 1


def test_actor_supervisor_failure_path_refreshes_absorption_summary(tmp_path) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    absorption_service = _RecordingAbsorptionService()
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=_SelectiveFailingWorker(),  # type: ignore[arg-type]
        exception_absorption_service=absorption_service,  # type: ignore[arg-type]
        poll_interval_seconds=0.01,
    )

    asyncio.run(supervisor.run_agent_once("agent-1"))

    assert len(absorption_service.calls) == 1


def test_actor_supervisor_materializes_exception_absorption_human_assist_with_continuity_anchor(
    tmp_path,
) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    runtime = runtime_repository.get_runtime("agent-1")
    assert runtime is not None
    runtime_repository.upsert_runtime(
        runtime.model_copy(
            update={
                "metadata": {
                    **dict(runtime.metadata or {}),
                    "chat_thread_id": "thread-1",
                    "control_thread_id": "thread-1",
                    "industry_instance_id": "industry-1",
                    "assignment_id": "assignment-1",
                    "work_context_id": "work-1",
                    "environment_ref": "desktop:sheet-1",
                }
            }
        )
    )
    human_assist_service = _build_human_assist_service(tmp_path)
    event_bus = _RecordingEventBus()
    absorption_service = _AbsorbingService(
        AbsorptionAction(
            kind="human-assist",
            case_kind="waiting-confirm-orphan",
            recovery_rung="human-assist",
            owner_agent_id="agent-1",
            scope_ref="checkpoint:confirm",
            summary="Need one governed confirmation to resume.",
            human_required=True,
            human_action_summary="请补一个必要确认。",
            human_action_contract={
                "title": "补一个必要确认",
                "summary": "Need one governed confirmation to resume.",
                "required_action": "请在聊天里补一个必要确认，并包含“checkpoint:confirm”。",
                "resume_checkpoint_ref": "checkpoint:confirm",
                "acceptance_spec": {"version": "v1", "hard_anchors": ["checkpoint:confirm"]},
            },
        )
    )
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=_RecordingWorker(),  # type: ignore[arg-type]
        runtime_event_bus=event_bus,
        exception_absorption_service=absorption_service,  # type: ignore[arg-type]
        human_assist_task_service=human_assist_service,
        poll_interval_seconds=0.01,
    )

    asyncio.run(supervisor.run_poll_cycle())

    tasks = human_assist_service.list_tasks(chat_thread_id="thread-1", limit=20)
    assert len(tasks) == 1
    task = tasks[0]
    assert task.task_type == "exception-absorption-human-step"
    assert task.reason_code == "main-brain-exception-absorption"
    assert task.status == "issued"
    assert task.resume_checkpoint_ref == "checkpoint:confirm"
    assert any(
        topic == "actor-supervisor"
        and action == "exception-absorption"
        and payload.get("action_kind") == "human-assist"
        and payload.get("materialized") is True
        and payload.get("human_task_id") == task.id
        for topic, action, payload in event_bus.events
    )


def test_actor_supervisor_does_not_materialize_exception_absorption_human_assist_without_chat_thread(
    tmp_path,
) -> None:
    runtime_repository = _build_runtime_repository(tmp_path)
    human_assist_service = _build_human_assist_service(tmp_path)
    event_bus = _RecordingEventBus()
    absorption_service = _AbsorbingService(
        AbsorptionAction(
            kind="human-assist",
            case_kind="waiting-confirm-orphan",
            recovery_rung="human-assist",
            owner_agent_id="agent-1",
            scope_ref="checkpoint:confirm",
            summary="Need one governed confirmation to resume.",
            human_required=True,
            human_action_summary="请补一个必要确认。",
            human_action_contract={
                "title": "补一个必要确认",
                "summary": "Need one governed confirmation to resume.",
                "required_action": "请在聊天里补一个必要确认，并包含“checkpoint:confirm”。",
                "resume_checkpoint_ref": "checkpoint:confirm",
                "acceptance_spec": {"version": "v1", "hard_anchors": ["checkpoint:confirm"]},
            },
        )
    )
    supervisor = ActorSupervisor(
        runtime_repository=runtime_repository,
        mailbox_service=None,  # type: ignore[arg-type]
        worker=_RecordingWorker(),  # type: ignore[arg-type]
        runtime_event_bus=event_bus,
        exception_absorption_service=absorption_service,  # type: ignore[arg-type]
        human_assist_task_service=human_assist_service,
        poll_interval_seconds=0.01,
    )

    asyncio.run(supervisor.run_poll_cycle())

    assert human_assist_service.list_tasks(limit=20) == []
    assert any(
        topic == "actor-supervisor"
        and action == "exception-absorption"
        and payload.get("action_kind") == "human-assist"
        and payload.get("materialized") is False
        and payload.get("materialization_reason") == "missing-chat-thread"
        for topic, action, payload in event_bus.events
    )
