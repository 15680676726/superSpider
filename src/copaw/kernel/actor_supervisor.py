# -*- coding: utf-8 -*-
"""Supervisor loop for resident actor workers."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from .actor_mailbox import ActorMailboxService
from .main_brain_exception_absorption import (
    AbsorptionAction,
    AbsorptionSummary,
    MainBrainExceptionAbsorptionService,
    resolve_absorption_continuity_context,
)
from .actor_worker import ActorWorker
from .runtime_outcome import normalize_runtime_summary, should_block_runtime_error
from ..state import AgentRuntimeRecord
from ..state.repositories import BaseAgentRuntimeRepository

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _consume_current_task_cancellation() -> int:
    current = asyncio.current_task()
    if current is None:
        return 0
    uncancel = getattr(current, "uncancel", None)
    if not callable(uncancel):
        return 0
    cleared = 0
    while current.cancelling():
        uncancel()
        cleared += 1
    return cleared


class ActorSupervisor:
    """One resident supervisor drives all actor workers from a shared loop."""

    def __init__(
        self,
        *,
        runtime_repository: BaseAgentRuntimeRepository,
        mailbox_service: ActorMailboxService,
        worker: ActorWorker,
        runtime_event_bus: object | None = None,
        exception_absorption_service: MainBrainExceptionAbsorptionService | None = None,
        human_assist_task_service: object | None = None,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._runtime_repository = runtime_repository
        self._mailbox_service = mailbox_service
        self._worker = worker
        self._runtime_event_bus = runtime_event_bus
        self._exception_absorption_service = exception_absorption_service
        self._human_assist_task_service = human_assist_task_service
        self._poll_interval_seconds = max(0.2, float(poll_interval_seconds))
        self._loop_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._agent_locks: dict[str, asyncio.Lock] = {}
        self._agent_tasks: dict[str, asyncio.Task[bool]] = {}
        self._last_absorption_summary: AbsorptionSummary | None = None
        self._last_absorption_action_fingerprint: str | None = None
        self._report_replan_engine: object | None = None

    async def start(self) -> None:
        if self._loop_task is not None and not self._loop_task.done():
            return
        self._stop_event = asyncio.Event()
        self._loop_task = asyncio.create_task(self._run_loop(), name="copaw-actor-supervisor")
        self._publish_runtime_event(topic="actor-supervisor", action="started", payload={})

    async def stop(self) -> None:
        self._stop_event.set()
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                _consume_current_task_cancellation()
                pass
        running_tasks = [
            task
            for task in self._agent_tasks.values()
            if not task.done()
        ]
        for task in running_tasks:
            task.cancel()
        if running_tasks:
            await asyncio.gather(*running_tasks, return_exceptions=True)
            _consume_current_task_cancellation()
        self._publish_runtime_event(topic="actor-supervisor", action="stopped", payload={})

    def mailbox_service(self) -> ActorMailboxService:
        return self._mailbox_service

    def configure_exception_absorption(
        self,
        *,
        exception_absorption_service: MainBrainExceptionAbsorptionService | None = None,
        human_assist_task_service: object | None = None,
        report_replan_engine: object | None = None,
    ) -> None:
        if exception_absorption_service is not None:
            self._exception_absorption_service = exception_absorption_service
        if human_assist_task_service is not None:
            self._human_assist_task_service = human_assist_task_service
        if report_replan_engine is not None:
            self._report_replan_engine = report_replan_engine

    def exception_absorption_service(self) -> MainBrainExceptionAbsorptionService | None:
        return self._exception_absorption_service

    @staticmethod
    def _task_status(task: asyncio.Task[Any] | None) -> str:
        if task is None:
            return "unavailable"
        if task.cancelled():
            return "cancelled"
        if task.done():
            return "completed"
        return "running"

    def snapshot(self) -> dict[str, object]:
        loop_status = self._task_status(self._loop_task)
        running = loop_status == "running"
        active_agent_run_count = sum(
            1
            for task in self._agent_tasks.values()
            if self._task_status(task) == "running"
        )
        blocked_runtime_count = 0
        recent_failure_count = 0
        last_failure_at: str | None = None
        last_failure_type: str | None = None
        for runtime in self._runtime_repository.list_runtimes(limit=None):
            if runtime.runtime_status == "blocked":
                blocked_runtime_count += 1
            metadata = dict(runtime.metadata or {})
            failure_at = metadata.get("supervisor_last_failure_at")
            if isinstance(failure_at, str) and failure_at:
                recent_failure_count += 1
                if last_failure_at is None or failure_at > last_failure_at:
                    last_failure_at = failure_at
                    failure_type = metadata.get("supervisor_last_failure_type")
                    last_failure_type = (
                        str(failure_type) if failure_type is not None else None
                    )
        absorption_summary = (
            self._last_absorption_summary
            or self._refresh_exception_absorption_summary(now=_utc_now())
        )

        status = "idle"
        if recent_failure_count > 0 or blocked_runtime_count > 0:
            status = "degraded"
        elif absorption_summary is not None and absorption_summary.case_count > 0:
            status = "degraded"
        elif running or active_agent_run_count > 0:
            status = "active"

        return {
            "available": True,
            "status": status,
            "running": running,
            "poll_interval_seconds": self._poll_interval_seconds,
            "loop_task_name": self._loop_task.get_name() if self._loop_task is not None else None,
            "loop_task_status": loop_status,
            "active_agent_run_count": active_agent_run_count,
            "blocked_runtime_count": blocked_runtime_count,
            "recent_failure_count": recent_failure_count,
            "last_failure_at": last_failure_at,
            "last_failure_type": last_failure_type,
            "absorption_case_count": (
                absorption_summary.case_count if absorption_summary is not None else 0
            ),
            "human_required_case_count": (
                absorption_summary.human_required_case_count
                if absorption_summary is not None
                else 0
            ),
            "absorption_case_counts": (
                dict(absorption_summary.case_counts)
                if absorption_summary is not None
                else {}
            ),
            "absorption_recovery_counts": (
                dict(absorption_summary.recovery_counts)
                if absorption_summary is not None
                else {}
            ),
            "absorption_summary": (
                absorption_summary.main_brain_summary
                if absorption_summary is not None
                else ""
            ),
        }

    async def run_agent_once(self, agent_id: str) -> bool:
        lock = self._agent_locks.setdefault(agent_id, asyncio.Lock())
        if lock.locked():
            return False
        async with lock:
            existing = self._agent_tasks.get(agent_id)
            if existing is not None and not existing.done():
                return False
            task = asyncio.create_task(
                self._worker.run_once(agent_id),
                name=f"copaw-actor:{agent_id}",
            )
            self._agent_tasks[agent_id] = task
            try:
                try:
                    return await task
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # pylint: disable=broad-except
                    self._record_agent_failure(agent_id, exc)
                    return False
            finally:
                if self._agent_tasks.get(agent_id) is task:
                    self._agent_tasks.pop(agent_id, None)

    async def run_poll_cycle(self) -> bool:
        agent_ids = [
            runtime.agent_id
            for runtime in self._runtime_repository.list_runtimes(limit=None)
            if runtime.desired_state == "active"
            and runtime.runtime_status != "retired"
            and (
                runtime.queue_depth > 0
                or runtime.runtime_status in {"queued", "claimed", "executing", "waiting", "running"}
            )
        ]
        if not agent_ids:
            self._evaluate_exception_absorption(now=_utc_now())
            return False
        results = await asyncio.gather(
            *(self.run_agent_once(agent_id) for agent_id in agent_ids),
        )
        self._evaluate_exception_absorption(now=_utc_now())
        return any(results)

    async def _run_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    ran_any = await self.run_poll_cycle()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # pylint: disable=broad-except
                    logger.exception("Actor supervisor poll cycle failed")
                    self._publish_runtime_event(
                        topic="actor-supervisor",
                        action="poll-failed",
                        payload={
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                        },
                    )
                    await asyncio.sleep(self._poll_interval_seconds)
                    continue
                if not ran_any:
                    await asyncio.sleep(self._poll_interval_seconds)
        except asyncio.CancelledError:
            raise

    def _record_agent_failure(self, agent_id: str, exc: Exception) -> None:
        logger.exception("Actor supervisor run failed for %s", agent_id)
        now = _utc_now()
        runtime = self._runtime_repository.get_runtime(agent_id)
        if runtime is None:
            runtime = AgentRuntimeRecord(
                agent_id=agent_id,
                actor_key=agent_id,
                actor_class="agent",
                desired_state="active",
                runtime_status="idle",
            )
        error_summary = normalize_runtime_summary(str(exc)) or type(exc).__name__
        metadata = dict(runtime.metadata or {})
        metadata["supervisor_last_failure_at"] = now.isoformat()
        metadata["supervisor_last_failure_type"] = type(exc).__name__
        runtime_status = runtime.runtime_status
        if runtime.desired_state == "retired":
            runtime_status = "retired"
        elif runtime.desired_state == "paused":
            runtime_status = "paused"
        elif should_block_runtime_error(error_summary):
            runtime_status = "blocked"
        elif runtime.queue_depth > 0:
            runtime_status = "queued"
        else:
            runtime_status = "idle"
        self._runtime_repository.upsert_runtime(
            runtime.model_copy(
                update={
                    "runtime_status": runtime_status,
                    "last_error_summary": error_summary,
                    "last_heartbeat_at": now,
                    "updated_at": now,
                    "metadata": metadata,
                },
            ),
        )
        self._publish_runtime_event(
            topic="actor-supervisor",
            action="agent-failed",
            payload={
                "agent_id": agent_id,
                "error": error_summary,
                "error_type": type(exc).__name__,
            },
        )
        self._evaluate_exception_absorption(now=now)

    def _absorption_inputs(self) -> tuple[list[object], list[object], list[object]]:
        list_items = getattr(self._mailbox_service, "list_items", None)
        mailbox_items = list(list_items(limit=None) if callable(list_items) else [])
        list_tasks = getattr(self._human_assist_task_service, "list_tasks", None)
        human_assist_tasks = list(list_tasks(limit=None) if callable(list_tasks) else [])
        runtimes = list(self._runtime_repository.list_runtimes(limit=None))
        return runtimes, mailbox_items, human_assist_tasks

    def _evaluate_exception_absorption(
        self,
        *,
        now: datetime,
    ) -> AbsorptionSummary | None:
        if self._exception_absorption_service is None:
            return None
        runtimes, mailbox_items, human_assist_tasks = self._absorption_inputs()
        summary = self._exception_absorption_service.scan(
            runtimes=runtimes,
            mailbox_items=mailbox_items,
            human_assist_tasks=human_assist_tasks,
            now=now,
        )
        self._last_absorption_summary = summary
        absorb = getattr(self._exception_absorption_service, "absorb", None)
        if not callable(absorb):
            self._last_absorption_action_fingerprint = None
            return summary
        action = absorb(
            runtimes=runtimes,
            mailbox_items=mailbox_items,
            human_assist_tasks=human_assist_tasks,
            now=now,
            report_replan_engine=self._report_replan_engine,
            human_assist_contract_builder=getattr(
                self._human_assist_task_service,
                "build_exception_absorption_contract",
                None,
            ),
        )
        if action is None:
            self._last_absorption_action_fingerprint = None
            return summary
        materialization = self._materialize_exception_absorption_action(
            action=action,
            runtimes=runtimes,
            mailbox_items=mailbox_items,
        )
        self._publish_exception_absorption_action(
            action=action,
            summary=summary,
            materialization=materialization,
        )
        return summary

    def _refresh_exception_absorption_summary(
        self,
        *,
        now: datetime,
    ) -> AbsorptionSummary | None:
        if self._exception_absorption_service is None:
            return None
        runtimes, mailbox_items, human_assist_tasks = self._absorption_inputs()
        summary = self._exception_absorption_service.scan(
            runtimes=runtimes,
            mailbox_items=mailbox_items,
            human_assist_tasks=human_assist_tasks,
            now=now,
        )
        self._last_absorption_summary = summary
        return summary

    @staticmethod
    def _action_fingerprint(
        action: AbsorptionAction,
        materialization: dict[str, object],
    ) -> str:
        return "|".join(
            [
                action.kind,
                action.case_kind,
                action.recovery_rung,
                action.owner_agent_id or "",
                action.scope_ref or "",
                action.replan_decision_kind or "",
                str(bool(materialization.get("materialized"))),
                str(materialization.get("human_task_id") or materialization.get("materialization_reason") or ""),
            ]
        )

    def _publish_exception_absorption_action(
        self,
        *,
        action: AbsorptionAction,
        summary: AbsorptionSummary,
        materialization: dict[str, object],
    ) -> None:
        fingerprint = self._action_fingerprint(action, materialization)
        if fingerprint == self._last_absorption_action_fingerprint:
            return
        self._last_absorption_action_fingerprint = fingerprint
        payload = {
            "action_kind": action.kind,
            "case_kind": action.case_kind,
            "recovery_rung": action.recovery_rung,
            "owner_agent_id": action.owner_agent_id,
            "scope_ref": action.scope_ref,
            "summary": action.summary,
            "human_required": action.human_required,
            "replan_decision_kind": action.replan_decision_kind,
            "replan_decision": dict(action.replan_decision),
            "human_action_summary": action.human_action_summary,
            "summary_text": summary.main_brain_summary,
            **materialization,
        }
        self._publish_runtime_event(
            topic="actor-supervisor",
            action="exception-absorption",
            payload=payload,
        )

    def _materialize_exception_absorption_action(
        self,
        *,
        action: AbsorptionAction,
        runtimes: list[object],
        mailbox_items: list[object],
    ) -> dict[str, object]:
        if action.kind != "human-assist":
            return {"materialized": False}
        service = self._human_assist_task_service
        ensure_task = getattr(service, "ensure_exception_absorption_task", None)
        if not callable(ensure_task):
            return {"materialized": False, "materialization_reason": "unsupported-service"}
        context = resolve_absorption_continuity_context(
            action,
            runtimes=runtimes,
            mailbox_items=mailbox_items,
        )
        if context.chat_thread_id is None:
            return {"materialized": False, "materialization_reason": "missing-chat-thread"}
        contract = dict(action.human_action_contract)
        acceptance_spec = contract.get("acceptance_spec") or {}
        hard_anchors = (
            list(acceptance_spec.get("hard_anchors") or [])
            if isinstance(acceptance_spec, dict)
            else []
        )
        verification_anchor = (
            contract.get("resume_checkpoint_ref")
            or (hard_anchors[0] if hard_anchors else None)
            or action.scope_ref
        )
        continuation_context = {
            **context.to_payload(),
            "owner_agent_id": action.owner_agent_id,
            "case_kind": action.case_kind,
            "recovery_rung": action.recovery_rung,
            "main_brain_runtime": {
                "control_thread_id": context.control_thread_id or context.chat_thread_id,
                "session_id": context.session_id or context.chat_thread_id,
                "work_context_id": context.work_context_id,
                "environment_ref": context.environment_ref,
                "recovery_mode": "exception-absorption",
                "recovery_reason": action.summary,
                "resume_checkpoint_id": verification_anchor,
            },
        }
        task = ensure_task(
            chat_thread_id=context.chat_thread_id,
            profile_id=context.profile_id,
            industry_instance_id=context.industry_instance_id,
            assignment_id=context.assignment_id,
            task_id=context.task_id,
            title=str(contract.get("title") or "补一个必要人类动作"),
            summary=str(contract.get("summary") or action.summary or ""),
            required_action=str(
                contract.get("required_action")
                or action.human_action_summary
                or action.summary
                or ""
            ),
            resume_checkpoint_ref=str(verification_anchor or action.scope_ref or "human-return"),
            verification_anchor=str(verification_anchor or action.scope_ref or "human-return"),
            block_evidence_refs=[item for item in [action.scope_ref, context.environment_ref] if item],
            continuation_context=continuation_context,
        )
        return {
            "materialized": True,
            "human_task_id": task.id,
            "human_task_status": task.status,
            "chat_thread_id": task.chat_thread_id,
        }

    def _publish_runtime_event(
        self,
        *,
        topic: str,
        action: str,
        payload: dict[str, object],
    ) -> None:
        if self._runtime_event_bus is None:
            return
        self._runtime_event_bus.publish(topic=topic, action=action, payload=payload)
