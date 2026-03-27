# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

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
