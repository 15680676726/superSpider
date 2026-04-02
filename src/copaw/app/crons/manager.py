# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ...config import get_heartbeat_config

from ..console_push_store import append as push_store_append
from .executor import CronExecutor
from .heartbeat import parse_heartbeat_every, run_heartbeat_once
from .models import CronJobSpec, CronJobState
from .repo.base import BaseJobRepository

HEARTBEAT_JOB_ID = "_heartbeat"

logger = logging.getLogger(__name__)

_STANDARD_WEEKDAY_NAMES = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
_STANDARD_WEEKDAY_NAME_TO_VALUE = {
    name: index for index, name in enumerate(_STANDARD_WEEKDAY_NAMES)
}


@dataclass
class _Runtime:
    sem: asyncio.Semaphore


def _schedule_status_from_runtime(state: CronJobState) -> str | None:
    if state.last_status == "running":
        return "running"
    if state.last_status == "success":
        return "success"
    if state.last_status == "error":
        return "error"
    return None


def _parse_standard_weekday_value(text: str) -> int:
    token = text.strip().lower()
    if token.isdigit():
        value = int(token)
        if value < 0 or value > 7:
            raise ValueError(f"weekday value out of range: {text}")
        return 0 if value in {0, 7} else value
    value = _STANDARD_WEEKDAY_NAME_TO_VALUE.get(token[:3])
    if value is None:
        raise ValueError(f"unsupported weekday token: {text}")
    return value


def _expand_standard_weekday_range(start_text: str, end_text: str) -> list[int]:
    start_token = start_text.strip().lower()
    end_token = end_text.strip().lower()
    if start_token.isdigit() and end_token.isdigit():
        start = int(start_token)
        end = int(end_token)
        if start < 0 or start > 7 or end < 0 or end > 7:
            raise ValueError(
                f"weekday range must stay within 0-7: {start_text}-{end_text}",
            )
        if start > end:
            raise ValueError(
                f"weekday range start must not exceed end: {start_text}-{end_text}",
            )
        return [
            0 if raw_value in {0, 7} else raw_value
            for raw_value in range(start, end + 1)
        ]
    start = _parse_standard_weekday_value(start_token)
    end = _parse_standard_weekday_value(end_token)
    if start > end:
        raise ValueError(
            f"weekday range start must not exceed end: {start_text}-{end_text}",
        )
    return list(range(start, end + 1))


def _expand_standard_weekday_base(text: str) -> list[int]:
    token = text.strip().lower() or "*"
    if token == "*":
        return list(range(7))
    if "-" in token:
        start_text, end_text = token.split("-", 1)
        return _expand_standard_weekday_range(start_text, end_text)
    return [_parse_standard_weekday_value(token)]


def _expand_standard_weekday_token(text: str) -> list[int]:
    token = text.strip().lower()
    if "/" in token:
        base_text, step_text = token.split("/", 1)
        step = int(step_text)
        if step <= 0:
            raise ValueError(f"weekday step must be positive: {text}")
    else:
        base_text = token
        step = 1
    values = _expand_standard_weekday_base(base_text)
    return values[::step]


def _normalize_day_of_week_for_apscheduler(expression: str) -> str:
    normalized = expression.strip().lower()
    if not normalized or normalized == "*":
        return normalized or expression

    try:
        resolved_values: set[int] = set()
        for token in normalized.split(","):
            stripped = token.strip()
            if not stripped:
                raise ValueError("weekday token must not be empty")
            resolved_values.update(_expand_standard_weekday_token(stripped))
    except ValueError:
        # Preserve advanced APScheduler-native expressions like mon-sun.
        return normalized

    if len(resolved_values) == 7:
        return "*"
    return ",".join(
        _STANDARD_WEEKDAY_NAMES[value]
        for value in range(7)
        if value in resolved_values
    )


class CronManager:
    def __init__(
        self,
        *,
        repo: BaseJobRepository,
        timezone: str = "UTC",
        kernel_dispatcher: Any | None = None,
    ):
        self._repo = repo
        self._scheduler = AsyncIOScheduler(timezone=timezone)
        self._executor = CronExecutor(
            kernel_dispatcher=kernel_dispatcher,
        )
        self._kernel_dispatcher = kernel_dispatcher

        self._lock = asyncio.Lock()
        self._heartbeat_run_lock = asyncio.Lock()
        self._states: Dict[str, CronJobState] = {}
        self._rt: Dict[str, _Runtime] = {}
        self._heartbeat_state = CronJobState()
        self._heartbeat_run_task: asyncio.Task | None = None
        self._started = False

    def set_kernel_dispatcher(self, kernel_dispatcher) -> None:
        """Attach the SRK kernel dispatcher for cron execution."""
        self._kernel_dispatcher = kernel_dispatcher
        self._executor.set_kernel_dispatcher(kernel_dispatcher)

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return
            jobs_file = await self._repo.load()

            self._scheduler.start()
            for job in jobs_file.jobs:
                await self._register_or_update(job)

            # Heartbeat: one interval job when enabled in config
            hb = get_heartbeat_config()
            if getattr(hb, "enabled", True):
                interval_seconds = parse_heartbeat_every(hb.every)
                self._scheduler.add_job(
                    self._heartbeat_callback,
                    trigger=IntervalTrigger(seconds=interval_seconds),
                    id=HEARTBEAT_JOB_ID,
                    replace_existing=True,
                )
            self._heartbeat_state = self._heartbeat_state.model_copy(
                update={"next_run_at": self._heartbeat_next_run_at()},
            )

            self._started = True

    async def stop(self) -> None:
        async with self._lock:
            if not self._started:
                return
            self._scheduler.shutdown(wait=False)
            self._started = False

    # ----- read/state -----

    async def list_jobs(self) -> list[CronJobSpec]:
        return await self._repo.list_jobs()

    async def get_job(self, job_id: str) -> Optional[CronJobSpec]:
        return await self._repo.get_job(job_id)

    def get_state(self, job_id: str) -> CronJobState:
        return self._states.get(job_id, CronJobState())

    def get_heartbeat_state(self) -> CronJobState:
        return self._heartbeat_state.model_copy(
            update={"next_run_at": self._heartbeat_next_run_at()},
        )

    # ----- write/control -----

    async def create_or_replace_job(self, spec: CronJobSpec) -> None:
        async with self._lock:
            await self._repo.upsert_job(spec)
            if self._started:
                await self._register_or_update(spec)

    async def delete_job(self, job_id: str) -> bool:
        async with self._lock:
            if self._started and self._scheduler.get_job(job_id):
                self._scheduler.remove_job(job_id)
            self._states.pop(job_id, None)
            self._rt.pop(job_id, None)
            deleted = await self._repo.delete_job(job_id)
            return deleted

    async def pause_job(self, job_id: str) -> None:
        async with self._lock:
            self._scheduler.pause_job(job_id)
            await self._persist_repo_state(
                job_id,
                self._states.get(job_id, CronJobState()),
                enabled=False,
                status="paused",
            )

    async def resume_job(self, job_id: str) -> None:
        async with self._lock:
            self._scheduler.resume_job(job_id)
            await self._persist_repo_state(
                job_id,
                self._states.get(job_id, CronJobState()),
                enabled=True,
                status="scheduled",
            )

    async def reschedule_heartbeat(self) -> None:
        """Reload heartbeat config and update or remove the heartbeat job."""
        async with self._lock:
            if not self._started:
                return
            hb = get_heartbeat_config()
            if self._scheduler.get_job(HEARTBEAT_JOB_ID):
                self._scheduler.remove_job(HEARTBEAT_JOB_ID)
            if getattr(hb, "enabled", True):
                interval_seconds = parse_heartbeat_every(hb.every)
                self._scheduler.add_job(
                    self._heartbeat_callback,
                    trigger=IntervalTrigger(seconds=interval_seconds),
                    id=HEARTBEAT_JOB_ID,
                    replace_existing=True,
                )
                logger.info(
                    "heartbeat rescheduled: every=%s (interval=%ss)",
                    hb.every,
                    interval_seconds,
                )
            else:
                logger.info("heartbeat disabled, job removed")
            self._heartbeat_state = self._heartbeat_state.model_copy(
                update={"next_run_at": self._heartbeat_next_run_at()},
            )

    async def run_heartbeat(self, *, ignore_active_hours: bool = True) -> dict[str, Any]:
        """Run heartbeat immediately and return the structured result."""
        return await self._run_heartbeat(ignore_active_hours=ignore_active_hours)

    async def run_job(self, job_id: str) -> None:
        """Trigger a job to run in the background (fire-and-forget).

        Raises KeyError if the job does not exist.
        The actual execution happens asynchronously; errors are logged
        and reflected in the job state but NOT propagated to the caller.
        """
        job = await self._repo.get_job(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        logger.info(
            "cron run_job (async): job_id=%s channel=%s task_type=%s "
            "target_user_id=%s target_session_id=%s",
            job_id,
            job.dispatch.channel,
            job.task_type,
            (job.dispatch.target.user_id or "")[:40],
            (job.dispatch.target.session_id or "")[:40],
        )
        task = asyncio.create_task(
            self._execute_once(job),
            name=f"cron-run-{job_id}",
        )
        task.add_done_callback(lambda t: self._task_done_cb(t, job))

    # ----- callbacks -----

    def _task_done_cb(self, task: asyncio.Task, job: CronJobSpec) -> None:
        """Suppress and log exceptions from fire-and-forget tasks.

        On failure, push an error message to the console push store so
        the frontend can display it.
        """
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "cron background task %s failed: %s",
                task.get_name(),
                repr(exc),
            )
            # Push error to the console for the frontend to display
            session_id = job.dispatch.target.session_id
            if session_id:
                error_text = f"❌ Cron job [{job.name}] failed: {exc}"
                asyncio.ensure_future(
                    push_store_append(session_id, error_text),
                )

    # ----- internal -----

    async def _register_or_update(self, spec: CronJobSpec) -> None:
        # per-job concurrency semaphore
        self._rt[spec.id] = _Runtime(
            sem=asyncio.Semaphore(spec.runtime.max_concurrency),
        )

        trigger = self._build_trigger(spec)

        # replace existing
        if self._scheduler.get_job(spec.id):
            self._scheduler.remove_job(spec.id)

        self._scheduler.add_job(
            self._scheduled_callback,
            trigger=trigger,
            id=spec.id,
            args=[spec.id],
            misfire_grace_time=spec.runtime.misfire_grace_seconds,
            replace_existing=True,
        )

        if not spec.enabled:
            self._scheduler.pause_job(spec.id)

        # update next_run
        aps_job = self._scheduler.get_job(spec.id)
        st = self._states.get(spec.id, CronJobState())
        st.next_run_at = aps_job.next_run_time if aps_job else None
        self._states[spec.id] = st
        await self._persist_repo_state(
            spec.id,
            st,
            enabled=spec.enabled,
            status="paused" if not spec.enabled else "scheduled",
        )

    def _build_trigger(self, spec: CronJobSpec) -> CronTrigger:
        # enforce 5 fields (no seconds)
        parts = [p for p in spec.schedule.cron.split() if p]
        if len(parts) != 5:
            raise ValueError(
                f"cron must have 5 fields, got {len(parts)}:"
                f" {spec.schedule.cron}",
            )

        minute, hour, day, month, day_of_week = parts
        return CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=_normalize_day_of_week_for_apscheduler(day_of_week),
            timezone=spec.schedule.timezone,
        )

    async def _scheduled_callback(self, job_id: str) -> None:
        job = await self._repo.get_job(job_id)
        if not job:
            return

        await self._execute_once(job)

        # refresh next_run
        aps_job = self._scheduler.get_job(job_id)
        st = self._states.get(job_id, CronJobState())
        st.next_run_at = aps_job.next_run_time if aps_job else None
        self._states[job_id] = st
        await self._persist_repo_state(job_id, st)

    async def _heartbeat_callback(self) -> None:
        """Run one heartbeat (HEARTBEAT.md as query, optional dispatch)."""
        result = await self._run_heartbeat(ignore_active_hours=False)
        if result.get("status") == "error":
            logger.warning("heartbeat run failed: %s", result.get("reason"))

    async def _execute_once(self, job: CronJobSpec) -> None:
        rt = self._rt.get(job.id)
        if not rt:
            rt = _Runtime(sem=asyncio.Semaphore(job.runtime.max_concurrency))
            self._rt[job.id] = rt

        async with rt.sem:
            st = self._states.get(job.id, CronJobState())
            st.last_status = "running"
            self._states[job.id] = st
            await self._persist_repo_state(
                job.id,
                st,
                enabled=job.enabled,
                status="running",
            )

            try:
                await self._executor.execute(job)
                st.last_status = "success"
                st.last_error = None
                logger.info(
                    "cron _execute_once: job_id=%s status=success",
                    job.id,
                )
            except Exception as e:  # pylint: disable=broad-except
                st.last_status = "error"
                st.last_error = repr(e)
                logger.warning(
                    "cron _execute_once: job_id=%s status=error error=%s",
                    job.id,
                    repr(e),
                )
                raise
            finally:
                st.last_run_at = datetime.utcnow()
                self._states[job.id] = st
                await self._persist_repo_state(job.id, st, enabled=job.enabled)

    async def _persist_repo_state(
        self,
        job_id: str,
        state: CronJobState,
        *,
        enabled: bool | None = None,
        status: str | None = None,
    ) -> None:
        updater = getattr(self._repo, "update_runtime_state", None)
        if not callable(updater):
            return
        await updater(
            job_id,
            status=status or _schedule_status_from_runtime(state),
            enabled=enabled,
            last_run_at=state.last_run_at,
            next_run_at=self._next_run_at(job_id),
            last_error=state.last_error,
        )

    def _next_run_at(self, job_id: str):
        job = self._scheduler.get_job(job_id)
        return job.next_run_time if job is not None else None

    def _heartbeat_next_run_at(self) -> Optional[datetime]:
        job = self._scheduler.get_job(HEARTBEAT_JOB_ID)
        return job.next_run_time if job is not None else None

    async def _run_heartbeat(self, *, ignore_active_hours: bool) -> dict[str, Any]:
        async with self._heartbeat_run_lock:
            task = self._heartbeat_run_task
            if task is None or task.done():
                task = asyncio.create_task(
                    self._execute_heartbeat_run(ignore_active_hours=ignore_active_hours),
                    name="cron-heartbeat-run",
                )
                self._heartbeat_run_task = task
        try:
            return await task
        finally:
            if task.done():
                async with self._heartbeat_run_lock:
                    if self._heartbeat_run_task is task:
                        self._heartbeat_run_task = None

    async def _execute_heartbeat_run(self, *, ignore_active_hours: bool) -> dict[str, Any]:
        self._heartbeat_state = self._heartbeat_state.model_copy(
            update={
                "last_status": "running",
                "last_error": None,
                "next_run_at": self._heartbeat_next_run_at(),
            },
        )
        try:
            result = await run_heartbeat_once(
                kernel_dispatcher=self._kernel_dispatcher,
                ignore_active_hours=ignore_active_hours,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("heartbeat run failed")
            result = {
                "status": "error",
                "reason": str(exc),
            }

        finished_at = datetime.now(timezone.utc)
        status = str(result.get("status") or "success")
        normalized_status = (
            status if status in {"success", "error", "running", "skipped"} else "error"
        )
        last_error = None
        if normalized_status in {"error", "skipped"}:
            detail = result.get("reason") or result.get("error")
            last_error = str(detail) if detail else None
        self._heartbeat_state = self._heartbeat_state.model_copy(
            update={
                "last_run_at": finished_at,
                "last_status": normalized_status,
                "last_error": last_error,
                "next_run_at": self._heartbeat_next_run_at(),
            },
        )
        return result
