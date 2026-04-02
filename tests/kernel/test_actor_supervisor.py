# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import time

import pytest

from copaw.kernel import ActorSupervisor
from copaw.state import AgentRuntimeRecord, SQLiteStateStore
from copaw.state.repositories import SqliteAgentRuntimeRepository


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


class _RecordingEventBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, object]]] = []

    def publish(self, *, topic: str, action: str, payload: dict[str, object]) -> None:
        self.events.append((topic, action, payload))


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
