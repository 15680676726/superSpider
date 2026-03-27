# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

from ....state import ScheduleRecord
from ....state.repositories import SqliteScheduleRepository
from ..models import CronJobSpec, JobsFile
from .base import BaseJobRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


_UNSET = object()


class StateBackedJobRepository(BaseJobRepository):
    """`BaseJobRepository` backed by `ScheduleRecord` shadow state.

    SQLite state is the sole runtime read/write surface. Legacy
    `jobs.json` no longer participates in bootstrap or steady-state
    reads.
    """

    def __init__(
        self,
        *,
        schedule_repository: SqliteScheduleRepository,
    ) -> None:
        self._schedule_repository = schedule_repository

    async def load(self) -> JobsFile:
        jobs = self._jobs_from_state()
        return JobsFile(version=1, jobs=jobs)

    async def save(self, jobs_file: JobsFile) -> None:
        existing = {
            record.id: record
            for record in self._schedule_repository.list_schedules()
            if record.status != "deleted"
        }
        incoming_ids = {job.id for job in jobs_file.jobs}

        for job in jobs_file.jobs:
            self._schedule_repository.upsert_schedule(
                self._job_to_schedule_record(
                    job,
                    existing=existing.get(job.id),
                ),
            )

        for schedule_id, schedule in existing.items():
            if schedule_id in incoming_ids:
                continue
            self._schedule_repository.upsert_schedule(
                schedule.model_copy(
                    update={
                        "status": "deleted",
                        "updated_at": _utc_now(),
                    },
                ),
            )

    async def list_jobs(self) -> list[CronJobSpec]:
        return self._jobs_from_state()

    async def get_job(self, job_id: str) -> CronJobSpec | None:
        schedule = self._schedule_repository.get_schedule(job_id)
        if schedule is not None and schedule.status != "deleted":
            return self._job_from_schedule_record(schedule)
        return None

    async def upsert_job(self, spec: CronJobSpec) -> None:
        jobs = self._jobs_from_state()
        for index, job in enumerate(jobs):
            if job.id == spec.id:
                jobs[index] = spec
                break
        else:
            jobs.append(spec)
        await self.save(JobsFile(version=1, jobs=jobs))

    async def delete_job(self, job_id: str) -> bool:
        schedule = self._schedule_repository.get_schedule(job_id)
        if schedule is None or schedule.status == "deleted":
            return False

        self._schedule_repository.upsert_schedule(
            schedule.model_copy(
                update={
                    "status": "deleted",
                    "updated_at": _utc_now(),
                },
            ),
        )
        return True

    async def update_runtime_state(
        self,
        job_id: str,
        *,
        status: str | None = None,
        enabled: bool | None = None,
        last_run_at: datetime | object = _UNSET,
        next_run_at: datetime | object = _UNSET,
        last_error: str | object = _UNSET,
    ) -> None:
        schedule = self._schedule_repository.get_schedule(job_id)
        if schedule is None or schedule.status == "deleted":
            return

        update: dict[str, object] = {"updated_at": _utc_now()}
        if status is not None:
            update["status"] = status
        if enabled is not None:
            update["enabled"] = enabled
        if last_run_at is not _UNSET:
            update["last_run_at"] = last_run_at
        if next_run_at is not _UNSET:
            update["next_run_at"] = next_run_at
        if last_error is not _UNSET:
            update["last_error"] = last_error

        self._schedule_repository.upsert_schedule(
            schedule.model_copy(update=update),
        )

    def _jobs_from_state(self) -> list[CronJobSpec]:
        jobs: list[CronJobSpec] = []
        for schedule in self._schedule_repository.list_schedules():
            if schedule.status == "deleted":
                continue
            job = self._job_from_schedule_record(schedule)
            if job is not None:
                jobs.append(job)
        return jobs

    def _job_from_schedule_record(
        self,
        schedule: ScheduleRecord,
    ) -> CronJobSpec | None:
        if not schedule.spec_payload:
            return None
        return CronJobSpec.model_validate(schedule.spec_payload)

    def _job_to_schedule_record(
        self,
        job: CronJobSpec,
        *,
        existing: ScheduleRecord | None,
    ) -> ScheduleRecord:
        now = _utc_now()
        preserved = existing or ScheduleRecord(
            id=job.id,
            title=job.name,
            cron=job.schedule.cron,
        )
        status = preserved.status
        if status == "deleted":
            status = "paused" if job.enabled is False else "scheduled"
        meta = (
            dict(job.meta)
            if isinstance(getattr(job, "meta", None), dict)
            else {}
        )

        return ScheduleRecord(
            id=job.id,
            title=job.name,
            cron=job.schedule.cron,
            timezone=job.schedule.timezone,
            status=status,
            enabled=job.enabled,
            task_type=job.task_type,
            target_channel=job.dispatch.channel,
            target_user_id=job.dispatch.target.user_id,
            target_session_id=job.dispatch.target.session_id,
            last_run_at=preserved.last_run_at,
            next_run_at=preserved.next_run_at,
            last_error=preserved.last_error,
            source_ref="state:/cron-sole-repository",
            spec_payload=job.model_dump(mode="json"),
            schedule_kind=str(meta.get("schedule_kind") or preserved.schedule_kind or "cadence"),
            trigger_target=(
                str(meta.get("trigger_target")).strip()
                if meta.get("trigger_target") is not None
                and str(meta.get("trigger_target")).strip()
                else preserved.trigger_target
            ),
            lane_id=(
                str(meta.get("lane_id")).strip()
                if meta.get("lane_id") is not None
                and str(meta.get("lane_id")).strip()
                else preserved.lane_id
            ),
            created_at=preserved.created_at,
            updated_at=now,
        )
