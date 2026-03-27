from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from copaw.app.crons.heartbeat import run_heartbeat_once
from copaw.app.runtime_lifecycle import (
    RuntimeRestartCoordinator,
    _should_run_operating_cycle,
    _should_run_learning_strategy,
    automation_interval_seconds,
    start_automation_tasks,
    stop_automation_tasks,
    submit_kernel_automation_task,
)


def test_automation_interval_seconds_uses_default_for_invalid_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COPAW_TEST_INTERVAL", "bad")

    value = automation_interval_seconds("COPAW_TEST_INTERVAL", 123)

    assert value == 123


def test_automation_interval_seconds_enforces_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COPAW_TEST_INTERVAL", "5")

    value = automation_interval_seconds("COPAW_TEST_INTERVAL", 123)

    assert value == 30


@pytest.mark.asyncio
async def test_start_automation_tasks_creates_named_tasks() -> None:
    tasks = start_automation_tasks(
        kernel_dispatcher=SimpleNamespace(),
        capability_service=SimpleNamespace(get_capability=lambda *_args, **_kwargs: None),
        logger=logging.getLogger(__name__),
    )

    assert {task.get_name() for task in tasks} == {
        "copaw-automation-operating-cycle",
        "copaw-automation-learning-strategy",
    }

    await stop_automation_tasks(tasks)

    assert all(task.done() for task in tasks)


@pytest.mark.asyncio
async def test_stop_automation_tasks_completes_during_shutdown_cancellation() -> None:
    gate = asyncio.Event()

    async def _loop() -> None:
        try:
            await gate.wait()
        except asyncio.CancelledError:
            raise

    managed = [asyncio.create_task(_loop(), name="managed-automation")]

    async def _shutdown() -> bool:
        await stop_automation_tasks(managed)
        return all(task.done() for task in managed)

    shutdown_task = asyncio.create_task(_shutdown(), name="shutdown-stop-automation")
    await asyncio.sleep(0)
    shutdown_task.cancel()

    assert await shutdown_task is True
    assert shutdown_task.cancelled() is False


@pytest.mark.asyncio
async def test_runtime_restart_coordinator_waits_for_existing_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = RuntimeRestartCoordinator(
        app=FastAPI(),
        agent_runtime_app=FastAPI(),
        bootstrap=SimpleNamespace(),
        runtime_host=object(),
        logger=logging.getLogger(__name__),
    )
    called = False
    gate = asyncio.Event()

    async def _unexpected_restart(*, restart_requester_task) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(coordinator, "_do_restart_services", _unexpected_restart)
    coordinator._restart_task = asyncio.create_task(gate.wait(), name="existing-restart")

    waiter = asyncio.create_task(coordinator.restart_services())
    await asyncio.sleep(0)

    assert called is False

    gate.set()
    await waiter


class _FakeAutomationTaskStore:
    def __init__(self, tasks) -> None:
        self._tasks = list(tasks)

    def list_tasks(self, *, phase=None, owner_agent_id=None, limit=200):
        _ = limit
        items = list(self._tasks)
        if phase is not None:
            items = [task for task in items if getattr(task, "phase", None) == phase]
        if owner_agent_id is not None:
            items = [
                task
                for task in items
                if getattr(task, "owner_agent_id", None) == owner_agent_id
            ]
        return items


class _FakeAutomationDispatcher:
    def __init__(self, task_store) -> None:
        self.task_store = task_store
        self.submitted = []

    def submit(self, task):
        self.submitted.append(task)
        return SimpleNamespace(phase="executing", summary="executing", task_id=task.id)

    async def execute_task(self, task_id):
        return SimpleNamespace(phase="completed", summary=f"completed {task_id}")


@pytest.mark.asyncio
async def test_submit_kernel_automation_task_skips_duplicate_inflight_payload() -> None:
    payload = {
        "actor": "copaw-main-brain",
        "auto_apply": True,
        "auto_rollback": False,
        "failure_threshold": 2,
        "confirm_threshold": 6,
        "max_proposals": 5,
    }
    existing_task = SimpleNamespace(
        phase="waiting-confirm",
        capability_ref="system:run_learning_strategy",
        owner_agent_id="copaw-main-brain",
        payload=payload,
    )
    dispatcher = _FakeAutomationDispatcher(_FakeAutomationTaskStore([existing_task]))

    result = await submit_kernel_automation_task(
        dispatcher,
        SimpleNamespace(get_capability=lambda *_args, **_kwargs: None),
        capability_ref="system:run_learning_strategy",
        title="Automation: learning-strategy",
        owner_agent_id="copaw-main-brain",
        payload=dict(payload),
    )

    assert getattr(result, "phase", None) == "skipped"
    assert dispatcher.submitted == []


def test_should_run_learning_strategy_uses_service_preflight() -> None:
    allowed, reason = _should_run_learning_strategy(
        SimpleNamespace(
            should_run_strategy_cycle=lambda **_kwargs: (
                False,
                "no-actionable-failure-pattern",
            ),
        ),
    )

    assert allowed is False
    assert reason == "no-actionable-failure-pattern"


def test_should_run_operating_cycle_uses_service_preflight() -> None:
    allowed, reason = _should_run_operating_cycle(
        SimpleNamespace(
            should_run_operating_cycle=lambda: (
                False,
                "open-backlog-drained",
            ),
        ),
    )

    assert allowed is False
    assert reason == "open-backlog-drained"


@pytest.mark.asyncio
async def test_run_heartbeat_once_dispatches_main_brain_supervision_pulse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[SimpleNamespace] = []

    class _Dispatcher:
        def submit(self, task):
            submitted.append(task)
            return SimpleNamespace(
                phase="executing",
                summary="executing",
                task_id=task.id,
            )

        async def execute_task(self, task_id):
            return SimpleNamespace(
                phase="completed",
                summary=f"completed {task_id}",
                result={"count": 2},
            )

    monkeypatch.setattr(
        "copaw.app.crons.heartbeat.get_heartbeat_config",
        lambda: SimpleNamespace(active_hours=None, target="main"),
    )

    payload = await run_heartbeat_once(
        kernel_dispatcher=_Dispatcher(),
        ignore_active_hours=True,
    )

    assert payload["status"] == "success"
    assert payload["query_path"] == "system:run_operating_cycle"
    assert payload["query_preview"] == "main-brain supervision pulse"
    assert payload["processed_instance_count"] == 2
    assert len(submitted) == 1
    assert submitted[0].capability_ref == "system:run_operating_cycle"
    assert submitted[0].owner_agent_id == "copaw-main-brain"
    assert submitted[0].payload["source"] == "heartbeat:supervision-pulse"
