# -*- coding: utf-8 -*-
"""Task lifecycle manager for the SRK kernel."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from .models import KernelConfig, KernelResult, KernelTask
from .persistence import KernelTaskStore

logger = logging.getLogger(__name__)


class TaskLifecycleManager:
    """Manage kernel task transitions and persist them to state."""

    def __init__(
        self,
        *,
        config: KernelConfig | None = None,
        store: KernelTaskStore | None = None,
    ) -> None:
        self._config = config or KernelConfig()
        self._store = store
        self._tasks: dict[str, KernelTask] = {}
        self._terminal_results: dict[str, KernelResult] = {}

    def accept(self, task: KernelTask) -> KernelTask:
        task = task.model_copy(
            update={"phase": "risk-check", "updated_at": self._now()},
        )
        self._tasks[task.id] = task
        self._persist(task)
        logger.info("Kernel accepted task %s (risk=%s)", task.id, task.risk_level)
        return task

    def evaluate_risk(self, task_id: str) -> KernelTask:
        task = self._get_task(task_id)
        if task.phase != "risk-check":
            raise ValueError(
                f"Task {task_id} is in phase '{task.phase}', expected 'risk-check'",
            )

        auto_execute_levels = set(self._config.auto_execute_risk_levels)
        confirm_levels = set(self._config.confirm_risk_levels)
        should_auto_execute = (
            task.risk_level in auto_execute_levels
            and task.risk_level not in confirm_levels
        )

        if not should_auto_execute:
            task = task.model_copy(
                update={"phase": "waiting-confirm", "updated_at": self._now()},
            )
        else:
            task = task.model_copy(
                update={"phase": "executing", "updated_at": self._now()},
            )

        self._tasks[task_id] = task
        self._persist(task)
        logger.info("Kernel risk evaluation moved task %s to %s", task_id, task.phase)
        return task

    def confirm(self, task_id: str) -> KernelTask:
        task = self._get_task(task_id)
        if task.phase != "waiting-confirm":
            raise ValueError(
                f"Task {task_id} is in phase '{task.phase}', expected 'waiting-confirm'",
            )
        task = task.model_copy(
            update={"phase": "executing", "updated_at": self._now()},
        )
        self._tasks[task_id] = task
        self._persist(task)
        logger.info("Kernel confirmed task %s", task_id)
        return task

    def complete(
        self,
        task_id: str,
        *,
        summary: str = "",
        evidence_id: str | None = None,
    ) -> KernelResult:
        task = self._get_task(task_id)
        if task.phase in {"completed", "failed", "cancelled"}:
            return self._terminal_result(
                task,
                fallback_summary=summary,
                evidence_id=evidence_id,
            )
        if task.phase != "executing":
            raise ValueError(
                f"Task {task_id} is in phase '{task.phase}', expected 'executing'",
            )

        task = task.model_copy(
            update={"phase": "completed", "updated_at": self._now()},
        )
        self._tasks[task_id] = task
        self._persist(
            task,
            last_result_summary=summary,
            last_evidence_id=evidence_id,
        )
        logger.info("Kernel completed task %s", task_id)
        result = KernelResult(
            task_id=task_id,
            trace_id=task.trace_id,
            success=True,
            phase="completed",
            summary=summary,
            evidence_id=evidence_id,
        )
        self._terminal_results[task_id] = result
        return result

    def fail(self, task_id: str, *, error: str) -> KernelResult:
        task = self._get_task(task_id)
        if task.phase in {"completed", "failed", "cancelled"}:
            return self._terminal_result(
                task,
                fallback_error=error,
            )
        task = task.model_copy(
            update={"phase": "failed", "updated_at": self._now()},
        )
        self._tasks[task_id] = task
        self._persist(task, last_error_summary=error)
        logger.warning("Kernel failed task %s: %s", task_id, error)
        result = KernelResult(
            task_id=task_id,
            trace_id=task.trace_id,
            success=False,
            phase="failed",
            error=error,
        )
        self._terminal_results[task_id] = result
        return result

    def cancel(self, task_id: str, *, summary: str = "Task cancelled") -> KernelResult:
        task = self._get_task(task_id)
        if task.phase in {"completed", "failed", "cancelled"}:
            return self._terminal_result(
                task,
                fallback_summary=summary,
            )
        task = task.model_copy(
            update={"phase": "cancelled", "updated_at": self._now()},
        )
        self._tasks[task_id] = task
        self._persist(task, last_error_summary=summary)
        logger.info("Kernel cancelled task %s", task_id)
        result = KernelResult(
            task_id=task_id,
            trace_id=task.trace_id,
            success=False,
            phase="cancelled",
            summary=summary,
        )
        self._terminal_results[task_id] = result
        return result

    def heartbeat(self, task_id: str) -> KernelTask:
        task = self._get_task(task_id)
        if task.phase in {"completed", "failed", "cancelled"}:
            return task
        task = task.model_copy(
            update={"updated_at": self._now()},
        )
        self._tasks[task_id] = task
        self._persist(task)
        return task

    def get_task(self, task_id: str) -> KernelTask | None:
        task = self._tasks.get(task_id)
        if task is not None:
            return task
        if self._store is None:
            return None
        task = self._store.get(task_id)
        if task is not None:
            self._tasks[task.id] = task
        return task

    def list_tasks(self, *, phase: str | None = None) -> list[KernelTask]:
        if self._store is not None:
            for task in self._store.list_tasks(phase=phase):
                self._tasks[task.id] = task
        tasks = list(self._tasks.values())
        if phase:
            tasks = [task for task in tasks if task.phase == phase]
        return sorted(tasks, key=lambda item: item.updated_at, reverse=True)

    def _get_task(self, task_id: str) -> KernelTask:
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' not found in kernel")
        return task

    def _persist(
        self,
        task: KernelTask,
        *,
        last_result_summary: str | None = None,
        last_error_summary: str | None = None,
        last_evidence_id: str | None = None,
    ) -> None:
        if self._store is None:
            return
        self._store.upsert(
            task,
            last_result_summary=last_result_summary,
            last_error_summary=last_error_summary,
            last_evidence_id=last_evidence_id,
        )

    def _terminal_result(
        self,
        task: KernelTask,
        *,
        fallback_summary: str = "",
        fallback_error: str | None = None,
        evidence_id: str | None = None,
    ) -> KernelResult:
        cached = self._terminal_results.get(task.id)
        if cached is not None:
            return cached
        runtime_record = (
            self._store.get_runtime_record(task.id)
            if self._store is not None
            else None
        )
        summary = fallback_summary
        error = fallback_error
        resolved_evidence_id = evidence_id
        if runtime_record is not None:
            summary = runtime_record.last_result_summary or summary
            error = runtime_record.last_error_summary or error
            resolved_evidence_id = runtime_record.last_evidence_id or resolved_evidence_id
        result = KernelResult(
            task_id=task.id,
            trace_id=task.trace_id,
            success=task.phase == "completed",
            phase=task.phase,
            summary=summary if task.phase != "failed" else "",
            error=error if task.phase != "completed" else None,
            evidence_id=resolved_evidence_id,
        )
        self._terminal_results[task.id] = result
        return result

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
