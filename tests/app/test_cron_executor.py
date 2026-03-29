# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from copaw.app.crons.executor import CronExecutor
from copaw.app.crons.models import CronJobSpec


class _FakeKernelDispatcher:
    def __init__(self) -> None:
        self.tasks = []

    def submit(self, task):
        self.tasks.append(task)
        return SimpleNamespace(phase="executing", task_id=task.id)

    async def execute_task(self, task_id: str):
        return SimpleNamespace(success=True, error=None, summary="ok")


def _agent_job(*, meta: dict[str, object] | None = None) -> CronJobSpec:
    return CronJobSpec.model_validate(
        {
            "id": "cron-job-1",
            "name": "Workflow host-aware cron",
            "enabled": True,
            "schedule": {
                "type": "cron",
                "cron": "0 9 * * 1",
                "timezone": "UTC",
            },
            "task_type": "agent",
            "request": {
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "continue workflow"}],
                    }
                ]
            },
            "dispatch": {
                "type": "channel",
                "channel": "console",
                "target": {"user_id": "workflow", "session_id": "workflow-run-1"},
                "mode": "final",
                "meta": {"summary": "resume scheduled step"},
            },
            "runtime": {
                "max_concurrency": 1,
                "timeout_seconds": 30,
                "misfire_grace_seconds": 30,
            },
            "meta": dict(meta or {}),
        }
    )


def test_cron_executor_prefers_stored_host_refs_over_session_fallback() -> None:
    dispatcher = _FakeKernelDispatcher()
    executor = CronExecutor(kernel_dispatcher=dispatcher)
    job = _agent_job(
        meta={
            "environment_id": "env:session:session:web:main",
            "session_mount_id": "session:web:main",
            "host_requirement": {"app_family": "browser_backoffice"},
        }
    )

    asyncio.run(executor.execute(job))

    assert len(dispatcher.tasks) == 1
    submitted = dispatcher.tasks[0]
    assert submitted.environment_ref == "env:session:session:web:main"
    assert submitted.payload["meta"]["session_mount_id"] == "session:web:main"
    assert submitted.payload["meta"]["host_requirement"] == {
        "app_family": "browser_backoffice"
    }


def test_cron_executor_falls_back_to_channel_session_when_no_host_ref_exists() -> None:
    dispatcher = _FakeKernelDispatcher()
    executor = CronExecutor(kernel_dispatcher=dispatcher)

    asyncio.run(executor.execute(_agent_job()))

    assert len(dispatcher.tasks) == 1
    submitted = dispatcher.tasks[0]
    assert submitted.environment_ref == "session:console:workflow-run-1"


def test_cron_executor_uses_scheduler_inputs_from_host_snapshot_before_session_fallback() -> None:
    dispatcher = _FakeKernelDispatcher()
    executor = CronExecutor(kernel_dispatcher=dispatcher)
    job = _agent_job(
        meta={
            "host_snapshot": {
                "environment_id": "env:host-snapshot",
                "session_mount_id": "session:host-snapshot",
                "scheduler_inputs": {
                    "environment_ref": "env:from-scheduler-inputs",
                    "session_mount_id": "session:from-scheduler-inputs",
                },
            },
        }
    )

    asyncio.run(executor.execute(job))

    assert len(dispatcher.tasks) == 1
    submitted = dispatcher.tasks[0]
    assert submitted.environment_ref == "env:from-scheduler-inputs"
    assert submitted.payload["meta"]["session_mount_id"] == "session:from-scheduler-inputs"
    assert submitted.payload["meta"]["host_snapshot"]["environment_id"] == "env:host-snapshot"


def test_cron_executor_prefers_scheduler_host_refs_over_stale_direct_meta_refs() -> None:
    dispatcher = _FakeKernelDispatcher()
    executor = CronExecutor(kernel_dispatcher=dispatcher)
    job = _agent_job(
        meta={
            "environment_ref": "env:stale-direct-meta",
            "environment_id": "env:stale-direct-meta",
            "session_mount_id": "session:stale-direct-meta",
            "host_snapshot": {
                "environment_id": "env:host-snapshot",
                "session_mount_id": "session:host-snapshot",
                "scheduler_inputs": {
                    "environment_ref": "env:fresh-scheduler-inputs",
                    "environment_id": "env:fresh-scheduler-inputs",
                    "session_mount_id": "session:fresh-scheduler-inputs",
                },
            },
        }
    )

    asyncio.run(executor.execute(job))

    assert len(dispatcher.tasks) == 1
    submitted = dispatcher.tasks[0]
    assert submitted.environment_ref == "env:fresh-scheduler-inputs"
    assert submitted.payload["meta"]["session_mount_id"] == "session:fresh-scheduler-inputs"
