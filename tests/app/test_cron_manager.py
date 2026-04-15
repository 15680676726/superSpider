# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from copaw.app.crons.manager import CronManager
from copaw.app.crons.models import (
    CronJobSpec,
    DispatchSpec,
    DispatchTarget,
    ScheduleSpec,
)

from tests.support_memory_repos import InMemoryJobRepository


def _make_job(job_id: str) -> CronJobSpec:
    return CronJobSpec(
        id=job_id,
        name=f"Job {job_id}",
        enabled=True,
        schedule=ScheduleSpec(cron="0 9 * * 1", timezone="UTC"),
        task_type="text",
        text="Ship weekly summary",
        dispatch=DispatchSpec(
            target=DispatchTarget(user_id="founder", session_id=f"cron:{job_id}"),
        ),
    )


def _next_fire_time(cron: str, *, now: datetime) -> datetime:
    manager = CronManager(
        repo=InMemoryJobRepository(),
        timezone="UTC",
    )
    trigger = manager._build_trigger(
        _make_job(f"job-{cron}").model_copy(
            update={"schedule": ScheduleSpec(cron=cron, timezone="UTC")},
        ),
    )
    next_fire = trigger.get_next_fire_time(None, now)
    assert next_fire is not None
    return next_fire


def test_cron_manager_create_replace_and_delete_job() -> None:
    async def run() -> None:
        manager = CronManager(
            repo=InMemoryJobRepository(),
            timezone="UTC",
        )

        job = _make_job("job-1")
        await manager.create_or_replace_job(job)

        listed = await manager.list_jobs()
        assert [item.id for item in listed] == ["job-1"]
        fetched = await manager.get_job("job-1")
        assert fetched is not None
        assert fetched.name == "Job job-1"

        replacement = job.model_copy(update={"name": "Job job-1 updated"})
        await manager.create_or_replace_job(replacement)
        fetched = await manager.get_job("job-1")
        assert fetched is not None
        assert fetched.name == "Job job-1 updated"

        deleted = await manager.delete_job("job-1")
        assert deleted is True
        assert await manager.get_job("job-1") is None
        assert await manager.list_jobs() == []

    asyncio.run(run())


def test_cron_manager_maps_numeric_weekday_to_standard_cron_semantics() -> None:
    next_fire = _next_fire_time(
        "0 9 * * 1",
        now=datetime(2026, 3, 22, 8, 0, tzinfo=timezone.utc),
    )
    assert next_fire == datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)


def test_cron_manager_treats_zero_and_seven_as_sunday() -> None:
    sunday_now = datetime(2026, 3, 22, 8, 0, tzinfo=timezone.utc)
    expected = datetime(2026, 3, 22, 9, 0, tzinfo=timezone.utc)

    assert _next_fire_time("0 9 * * 0", now=sunday_now) == expected
    assert _next_fire_time("0 9 * * 7", now=sunday_now) == expected


def test_cron_manager_accepts_full_standard_weekday_range() -> None:
    next_fire = _next_fire_time(
        "0 9 * * 1-7",
        now=datetime(2026, 3, 22, 8, 0, tzinfo=timezone.utc),
    )
    assert next_fire == datetime(2026, 3, 22, 9, 0, tzinfo=timezone.utc)


def test_cron_manager_reuses_inflight_heartbeat_run(monkeypatch) -> None:
    async def run() -> None:
        manager = CronManager(
            repo=InMemoryJobRepository(),
            timezone="UTC",
        )
        started = asyncio.Event()
        release = asyncio.Event()
        call_count = 0

        async def _fake_run_heartbeat_once(*, kernel_dispatcher=None, ignore_active_hours=False):
            nonlocal call_count
            _ = kernel_dispatcher
            _ = ignore_active_hours
            call_count += 1
            started.set()
            await release.wait()
            return {
                "status": "success",
                "task_id": "ktask:heartbeat",
                "query_path": "system:run_operating_cycle",
            }

        monkeypatch.setattr(
            "copaw.app.crons.manager.run_heartbeat_once",
            _fake_run_heartbeat_once,
        )

        first = asyncio.create_task(manager.run_heartbeat())
        await started.wait()

        second = asyncio.create_task(manager.run_heartbeat())
        await asyncio.sleep(0)
        assert call_count == 1

        release.set()
        first_result = await first
        second_result = await second

        assert call_count == 1
        assert first_result == second_result

        third_result = await manager.run_heartbeat()
        assert call_count == 2
        assert third_result["status"] == "success"

    asyncio.run(run())


def test_cron_manager_runs_memory_sleep_jobs_after_heartbeat(monkeypatch) -> None:
    async def run() -> None:
        sleep_calls: list[dict[str, object]] = []

        manager = CronManager(
            repo=InMemoryJobRepository(),
            timezone="UTC",
            memory_sleep_service=SimpleNamespace(
                run_due_sleep_jobs=lambda **kwargs: sleep_calls.append(dict(kwargs)) or [],
            ),
        )

        async def _fake_run_heartbeat_once(*, kernel_dispatcher=None, ignore_active_hours=False):
            _ = kernel_dispatcher
            _ = ignore_active_hours
            return {
                "status": "success",
                "task_id": "ktask:heartbeat",
                "query_path": "system:run_operating_cycle",
            }

        monkeypatch.setattr(
            "copaw.app.crons.manager.run_heartbeat_once",
            _fake_run_heartbeat_once,
        )

        result = await manager.run_heartbeat()

        assert result["status"] == "success"
        assert sleep_calls == [{"limit": None}]

    asyncio.run(run())


def test_cron_manager_reports_failed_memory_sleep_jobs(monkeypatch) -> None:
    async def run() -> None:
        manager = CronManager(
            repo=InMemoryJobRepository(),
            timezone="UTC",
            memory_sleep_service=SimpleNamespace(
                run_due_sleep_jobs=lambda **kwargs: [
                    SimpleNamespace(status="completed"),
                    SimpleNamespace(status="failed"),
                ],
            ),
        )

        async def _fake_run_heartbeat_once(*, kernel_dispatcher=None, ignore_active_hours=False):
            _ = kernel_dispatcher
            _ = ignore_active_hours
            return {
                "status": "success",
                "task_id": "ktask:heartbeat",
                "query_path": "system:run_operating_cycle",
            }

        monkeypatch.setattr(
            "copaw.app.crons.manager.run_heartbeat_once",
            _fake_run_heartbeat_once,
        )

        result = await manager.run_heartbeat()

        assert result["status"] == "success"
        assert result["memory_sleep_status"] == "failed"
        assert result["memory_sleep_job_count"] == 2
        assert result["memory_sleep_failed_count"] == 1

    asyncio.run(run())
