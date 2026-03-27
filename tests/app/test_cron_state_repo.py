# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json

from copaw.app.crons.models import (
    CronJobSpec,
    DispatchSpec,
    DispatchTarget,
    ScheduleSpec,
)
from copaw.app.crons.repo import StateBackedJobRepository
from copaw.state import SQLiteStateStore
from copaw.state.repositories import SqliteScheduleRepository


def make_job(job_id: str, *, text: str = "Ship weekly summary") -> CronJobSpec:
    return CronJobSpec(
        id=job_id,
        name=f"Job {job_id}",
        enabled=True,
        schedule=ScheduleSpec(cron="0 9 * * 1", timezone="UTC"),
        task_type="text",
        text=text,
        dispatch=DispatchSpec(
            target=DispatchTarget(user_id="founder", session_id=f"cron:{job_id}"),
        ),
    )


def _write_legacy_jobs(path, jobs: list[CronJobSpec]) -> None:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "jobs": [job.model_dump(mode="json") for job in jobs],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _build_repo(tmp_path) -> tuple[StateBackedJobRepository, SqliteScheduleRepository]:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    schedule_repository = SqliteScheduleRepository(state_store)
    repo = StateBackedJobRepository(
        schedule_repository=schedule_repository,
    )
    return repo, schedule_repository


def test_state_backed_job_repo_ignores_legacy_json_and_reads_only_state(
    tmp_path,
) -> None:
    jobs_path = tmp_path / "jobs.json"
    _write_legacy_jobs(jobs_path, [make_job("job-legacy")])
    legacy_snapshot = jobs_path.read_text(encoding="utf-8")

    repo, schedule_repo = _build_repo(tmp_path)

    assert asyncio.run(repo.list_jobs()) == []

    asyncio.run(repo.upsert_job(make_job("job-state", text="State job")))
    loaded = asyncio.run(repo.list_jobs())

    assert [job.id for job in loaded] == ["job-state"]
    stored = schedule_repo.get_schedule("job-state")
    assert stored is not None
    assert stored.spec_payload["name"] == "Job job-state"
    assert jobs_path.read_text(encoding="utf-8") == legacy_snapshot


def test_state_backed_job_repo_delete_stays_off_legacy_json(tmp_path) -> None:
    jobs_path = tmp_path / "jobs.json"
    _write_legacy_jobs(jobs_path, [make_job("job-legacy")])
    legacy_snapshot = jobs_path.read_text(encoding="utf-8")

    repo, schedule_repo = _build_repo(tmp_path)
    asyncio.run(repo.upsert_job(make_job("job-delete")))

    deleted = asyncio.run(repo.delete_job("job-delete"))

    assert deleted is True
    assert asyncio.run(repo.list_jobs()) == []
    deleted_schedule = schedule_repo.get_schedule("job-delete")
    assert deleted_schedule is not None
    assert deleted_schedule.status == "deleted"
    assert jobs_path.read_text(encoding="utf-8") == legacy_snapshot


def test_state_backed_job_repo_keeps_state_only_deletion_after_restart(
    tmp_path,
) -> None:
    repo, _ = _build_repo(tmp_path)
    asyncio.run(repo.upsert_job(make_job("job-delete")))
    asyncio.run(repo.delete_job("job-delete"))

    restarted_repo, _ = _build_repo(tmp_path)

    assert asyncio.run(restarted_repo.list_jobs()) == []
