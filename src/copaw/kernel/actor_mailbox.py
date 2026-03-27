# -*- coding: utf-8 -*-
"""Actor mailbox service for resident multi-agent runtime."""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .runtime_outcome import normalize_runtime_summary, should_block_runtime_error
from ..state import AgentCheckpointRecord, AgentMailboxRecord, AgentRuntimeRecord
from ..state.repositories import (
    BaseAgentCheckpointRepository,
    BaseAgentMailboxRepository,
    BaseAgentRuntimeRepository,
    BaseAgentThreadBindingRepository,
)

_TERMINAL_MAILBOX_STATUSES = frozenset({"completed", "failed", "cancelled"})
_QUEUE_MAILBOX_STATUSES = frozenset({"queued", "leased", "running", "retry-wait", "blocked"})
_TERMINAL_KERNEL_PHASES = frozenset({"completed", "failed", "cancelled"})
_ACTIVE_ASSIGNMENT_STATUSES = frozenset({"planned", "queued", "running", "waiting-report"})

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ActorMailboxService:
    """Persisted inbox + runtime projection for actor-first execution."""

    def __init__(
        self,
        *,
        mailbox_repository: BaseAgentMailboxRepository,
        runtime_repository: BaseAgentRuntimeRepository,
        checkpoint_repository: BaseAgentCheckpointRepository | None = None,
        thread_binding_repository: BaseAgentThreadBindingRepository | None = None,
        kernel_dispatcher: object | None = None,
        runtime_event_bus: object | None = None,
    ) -> None:
        self._mailbox_repository = mailbox_repository
        self._runtime_repository = runtime_repository
        self._checkpoint_repository = checkpoint_repository
        self._thread_binding_repository = thread_binding_repository
        self._kernel_dispatcher = kernel_dispatcher
        self._runtime_event_bus = runtime_event_bus

    def list_items(
        self,
        *,
        agent_id: str | None = None,
        status: str | None = None,
        conversation_thread_id: str | None = None,
        work_context_id: str | None = None,
        limit: int | None = None,
    ) -> list[AgentMailboxRecord]:
        items = self._mailbox_repository.list_items(
            agent_id=agent_id,
            status=status,
            conversation_thread_id=conversation_thread_id,
            work_context_id=work_context_id,
            limit=limit,
        )
        items.sort(
            key=lambda item: (
                item.priority,
                item.retry_after_at or item.updated_at,
                item.updated_at,
            ),
            reverse=True,
        )
        return items

    def get_item(self, item_id: str) -> AgentMailboxRecord | None:
        return self._mailbox_repository.get_item(item_id)

    def get_checkpoint(self, checkpoint_id: str) -> AgentCheckpointRecord | None:
        if self._checkpoint_repository is None:
            return None
        return self._checkpoint_repository.get_checkpoint(checkpoint_id)

    def list_checkpoints(
        self,
        *,
        agent_id: str | None = None,
        mailbox_id: str | None = None,
        task_id: str | None = None,
        conversation_thread_id: str | None = None,
        work_context_id: str | None = None,
        limit: int | None = None,
    ) -> list[AgentCheckpointRecord]:
        if self._checkpoint_repository is None:
            return []
        checkpoints = self._checkpoint_repository.list_checkpoints(
            agent_id=agent_id,
            mailbox_id=mailbox_id,
            task_id=task_id,
            work_context_id=work_context_id,
            limit=None,
        )
        if conversation_thread_id:
            checkpoints = [
                checkpoint
                for checkpoint in checkpoints
                if checkpoint.conversation_thread_id == conversation_thread_id
            ]
        checkpoints.sort(key=lambda item: item.updated_at, reverse=True)
        if limit is not None and limit >= 0:
            return checkpoints[:limit]
        return checkpoints

    def enqueue_item(
        self,
        *,
        agent_id: str,
        title: str,
        summary: str = "",
        task_id: str | None = None,
        work_context_id: str | None = None,
        source_agent_id: str | None = None,
        parent_mailbox_id: str | None = None,
        envelope_type: str = "task",
        capability_ref: str | None = None,
        conversation_thread_id: str | None = None,
        payload: dict[str, object] | None = None,
        priority: int = 0,
        max_attempts: int = 3,
        metadata: dict[str, object] | None = None,
    ) -> AgentMailboxRecord:
        now = _utc_now()
        item = AgentMailboxRecord(
            agent_id=agent_id,
            task_id=task_id,
            work_context_id=_non_empty_str(
                work_context_id,
                (metadata or {}).get("work_context_id"),
            ),
            parent_mailbox_id=parent_mailbox_id,
            source_agent_id=source_agent_id,
            envelope_type=(envelope_type if envelope_type in {"query", "goal", "delegation", "control", "task"} else "task"),
            title=title.strip() or f"Actor task for {agent_id}",
            summary=summary.strip(),
            status="queued",
            priority=max(0, int(priority)),
            capability_ref=capability_ref,
            conversation_thread_id=conversation_thread_id,
            payload=dict(payload or {}),
            max_attempts=max(1, int(max_attempts)),
            metadata={**(metadata or {}), "enqueued_at": now.isoformat()},
        )
        stored = self._mailbox_repository.upsert_item(item)
        self._sync_runtime(agent_id, current_mailbox_id=None)
        self._publish_runtime_event(
            topic="actor-mailbox",
            action="queued",
            payload={
                "agent_id": agent_id,
                "mailbox_id": stored.id,
                "task_id": stored.task_id,
                "title": stored.title,
            },
        )
        return stored

    def claim_next(self, agent_id: str, *, worker_id: str) -> AgentMailboxRecord | None:
        now = _utc_now()
        items = self.list_items(agent_id=agent_id, limit=None)
        for item in items:
            if item.status == "retry-wait":
                retry_after = item.retry_after_at
                if retry_after is not None and retry_after > now:
                    continue
            if item.status not in {"queued", "retry-wait"}:
                continue
            claimed = item.model_copy(
                update={
                    "status": "leased",
                    "lease_owner": worker_id,
                    "lease_token": uuid4().hex,
                    "claimed_at": now,
                    "attempt_count": item.attempt_count + 1,
                    "updated_at": now,
                },
            )
            stored = self._mailbox_repository.upsert_item(claimed)
            self._sync_runtime(agent_id, current_mailbox_id=stored.id, error_summary="")
            return stored
        self._sync_runtime(agent_id, current_mailbox_id=None)
        return None

    def start_item(
        self,
        item_id: str,
        *,
        worker_id: str,
        task_id: str | None = None,
    ) -> AgentMailboxRecord:
        item = self._require_item(item_id)
        now = _utc_now()
        updated = item.model_copy(
            update={
                "status": "running",
                "lease_owner": worker_id,
                "started_at": now,
                "task_id": task_id or item.task_id,
                "updated_at": now,
            },
        )
        stored = self._mailbox_repository.upsert_item(updated)
        self._sync_runtime(
            stored.agent_id,
            current_mailbox_id=stored.id,
            current_task_id=stored.task_id,
            error_summary="",
            force_status="executing",
        )
        return stored

    def complete_item(
        self,
        item_id: str,
        *,
        result_summary: str,
        checkpoint_id: str | None = None,
        task_id: str | None = None,
    ) -> AgentMailboxRecord:
        item = self._require_item(item_id)
        now = _utc_now()
        updated = item.model_copy(
            update={
                "status": "completed",
                "result_summary": result_summary.strip() or item.result_summary,
                "task_id": task_id or item.task_id,
                "completed_at": now,
                "lease_owner": None,
                "lease_token": None,
                "updated_at": now,
            },
        )
        stored = self._mailbox_repository.upsert_item(updated)
        self._sync_runtime(
            stored.agent_id,
            current_mailbox_id=None,
            current_task_id=None,
            checkpoint_id=checkpoint_id,
            error_summary="",
            result_summary=stored.result_summary,
        )
        self._publish_runtime_event(
            topic="actor-mailbox",
            action="completed",
            payload={
                "agent_id": stored.agent_id,
                "mailbox_id": stored.id,
                "task_id": stored.task_id,
            },
        )
        return stored

    def fail_item(
        self,
        item_id: str,
        *,
        error_summary: str,
        retryable: bool = True,
        retry_delay_seconds: int = 60,
        task_id: str | None = None,
        checkpoint_id: str | None = None,
    ) -> AgentMailboxRecord:
        item = self._require_item(item_id)
        now = _utc_now()
        can_retry = retryable and item.attempt_count < item.max_attempts
        status = "retry-wait" if can_retry else "failed"
        updated = item.model_copy(
            update={
                "status": status,
                "task_id": task_id or item.task_id,
                "error_summary": error_summary.strip() or item.error_summary,
                "retry_after_at": (
                    now + timedelta(seconds=max(5, int(retry_delay_seconds)))
                    if can_retry
                    else None
                ),
                "lease_owner": None,
                "lease_token": None,
                "completed_at": None if can_retry else now,
                "updated_at": now,
            },
        )
        stored = self._mailbox_repository.upsert_item(updated)
        self._sync_runtime(
            stored.agent_id,
            current_mailbox_id=None,
            current_task_id=None,
            checkpoint_id=checkpoint_id,
            error_summary=stored.error_summary,
            force_status="queued" if can_retry else "blocked",
        )
        self._publish_runtime_event(
            topic="actor-mailbox",
            action="retry-wait" if can_retry else "failed",
            payload={
                "agent_id": stored.agent_id,
                "mailbox_id": stored.id,
                "task_id": stored.task_id,
                "error": stored.error_summary,
            },
        )
        return stored

    def retry_item(self, item_id: str) -> AgentMailboxRecord:
        item = self._require_item(item_id)
        now = _utc_now()
        updated = item.model_copy(
            update={
                "status": "queued",
                "retry_after_at": None,
                "lease_owner": None,
                "lease_token": None,
                "updated_at": now,
            },
        )
        stored = self._mailbox_repository.upsert_item(updated)
        self._sync_runtime(stored.agent_id, current_mailbox_id=None, error_summary="")
        return stored

    def recover_orphaned_items(
        self,
        *,
        now: datetime | None = None,
        task_reader: Callable[[str], object | None] | None = None,
    ) -> dict[str, int]:
        current = now or _utc_now()
        summary = {
            "total": 0,
            "requeued": 0,
            "blocked": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
        stale_items = [
            item
            for item in self._mailbox_repository.list_items(limit=None)
            if item.status in {"leased", "running"}
        ]
        for item in stale_items:
            summary["total"] += 1
            task = (
                task_reader(item.task_id)
                if callable(task_reader) and isinstance(item.task_id, str) and item.task_id.strip()
                else None
            )
            task_phase = _task_phase(task)
            recovery_summary = (
                f"Recovered mailbox item {item.id} from '{item.status}' during startup recovery."
            )
            snapshot_payload = {
                "mailbox": item.model_dump(mode="json"),
                "task_phase": task_phase,
            }
            resume_payload = {
                "mailbox_id": item.id,
                "task_id": item.task_id,
                "recovered_from_status": item.status,
                "task_phase": task_phase,
            }
            if task_phase == "completed":
                checkpoint = self.create_checkpoint(
                    agent_id=item.agent_id,
                    mailbox_id=item.id,
                    task_id=item.task_id,
                    checkpoint_kind="resume",
                    status="applied",
                    phase="startup-recovered-completed",
                    conversation_thread_id=item.conversation_thread_id,
                    snapshot_payload=snapshot_payload,
                    resume_payload=resume_payload,
                    summary=recovery_summary,
                )
                self.complete_item(
                    item.id,
                    result_summary=(
                        item.result_summary
                        or f"Recovered completed kernel task '{item.task_id}' during startup."
                    ),
                    checkpoint_id=checkpoint.id if checkpoint is not None else None,
                    task_id=item.task_id,
                )
                summary["completed"] += 1
                continue
            if task_phase == "failed":
                checkpoint = self.create_checkpoint(
                    agent_id=item.agent_id,
                    mailbox_id=item.id,
                    task_id=item.task_id,
                    checkpoint_kind="resume",
                    status="failed",
                    phase="startup-recovered-failed",
                    conversation_thread_id=item.conversation_thread_id,
                    snapshot_payload=snapshot_payload,
                    resume_payload=resume_payload,
                    summary=recovery_summary,
                )
                self.fail_item(
                    item.id,
                    error_summary=(
                        item.error_summary
                        or f"Recovered failed kernel task '{item.task_id}' during startup."
                    ),
                    retryable=False,
                    task_id=item.task_id,
                    checkpoint_id=checkpoint.id if checkpoint is not None else None,
                )
                summary["failed"] += 1
                continue
            if task_phase == "cancelled":
                checkpoint = self.create_checkpoint(
                    agent_id=item.agent_id,
                    mailbox_id=item.id,
                    task_id=item.task_id,
                    checkpoint_kind="resume",
                    status="abandoned",
                    phase="startup-recovered-cancelled",
                    conversation_thread_id=item.conversation_thread_id,
                    snapshot_payload=snapshot_payload,
                    resume_payload=resume_payload,
                    summary=recovery_summary,
                )
                self.cancel_item(
                    item.id,
                    reason=(
                        item.error_summary
                        or f"Recovered cancelled kernel task '{item.task_id}' during startup."
                    ),
                )
                if checkpoint is not None:
                    self._sync_runtime(
                        item.agent_id,
                        current_mailbox_id=None,
                        current_task_id=None,
                        checkpoint_id=checkpoint.id,
                    )
                summary["cancelled"] += 1
                continue
            if task_phase == "waiting-confirm":
                checkpoint = self.create_checkpoint(
                    agent_id=item.agent_id,
                    mailbox_id=item.id,
                    task_id=item.task_id,
                    checkpoint_kind="resume",
                    status="ready",
                    phase="startup-recovered-waiting-confirm",
                    conversation_thread_id=item.conversation_thread_id,
                    snapshot_payload=snapshot_payload,
                    resume_payload=resume_payload,
                    summary=recovery_summary,
                )
                self.block_item(
                    item.id,
                    reason=f"Recovered held kernel task '{item.task_id}' awaiting confirmation.",
                    task_id=item.task_id,
                    checkpoint_id=checkpoint.id if checkpoint is not None else None,
                )
                summary["blocked"] += 1
                continue

            metadata = dict(item.metadata)
            recovery_events = (
                list(metadata.get("recovery_events"))
                if isinstance(metadata.get("recovery_events"), list)
                else []
            )
            recovery_events.append(
                {
                    "at": current.isoformat(),
                    "kind": "startup-recovery",
                    "from_status": item.status,
                    "task_phase": task_phase,
                },
            )
            metadata["recovery_events"] = recovery_events[-10:]
            checkpoint = self.create_checkpoint(
                agent_id=item.agent_id,
                mailbox_id=item.id,
                task_id=item.task_id,
                checkpoint_kind="resume",
                status="ready",
                phase="startup-recovered",
                conversation_thread_id=item.conversation_thread_id,
                snapshot_payload=snapshot_payload,
                resume_payload=resume_payload,
                summary=recovery_summary,
            )
            updated = item.model_copy(
                update={
                    "status": "queued",
                    "lease_owner": None,
                    "lease_token": None,
                    "claimed_at": None,
                    "started_at": None,
                    "retry_after_at": None,
                    "metadata": metadata,
                    "updated_at": current,
                },
            )
            stored = self._mailbox_repository.upsert_item(updated)
            self._sync_runtime(
                stored.agent_id,
                current_mailbox_id=None,
                current_task_id=None,
                checkpoint_id=checkpoint.id if checkpoint is not None else None,
                force_status="queued",
            )
            self._publish_runtime_event(
                topic="actor-mailbox",
                action="recovered",
                payload={
                    "agent_id": stored.agent_id,
                    "mailbox_id": stored.id,
                    "task_id": stored.task_id,
                    "task_phase": task_phase,
                    "from_status": item.status,
                },
            )
            summary["requeued"] += 1
        return summary

    def cancel_item(
        self,
        item_id: str,
        *,
        reason: str | None = None,
        task_id: str | None = None,
        checkpoint_id: str | None = None,
    ) -> AgentMailboxRecord:
        item = self._require_item(item_id)
        now = _utc_now()
        updated = item.model_copy(
            update={
                "status": "cancelled",
                "task_id": task_id or item.task_id,
                "error_summary": reason or item.error_summary,
                "lease_owner": None,
                "lease_token": None,
                "completed_at": now,
                "updated_at": now,
            },
        )
        stored = self._mailbox_repository.upsert_item(updated)
        self._sync_runtime(
            stored.agent_id,
            current_mailbox_id=None,
            current_task_id=None,
            checkpoint_id=checkpoint_id,
            error_summary="",
        )
        self._publish_runtime_event(
            topic="actor-mailbox",
            action="cancelled",
            payload={
                "agent_id": stored.agent_id,
                "mailbox_id": stored.id,
                "task_id": stored.task_id,
                "reason": stored.error_summary,
            },
        )
        return stored

    def block_item(
        self,
        item_id: str,
        *,
        reason: str,
        task_id: str | None = None,
        checkpoint_id: str | None = None,
    ) -> AgentMailboxRecord:
        item = self._require_item(item_id)
        now = _utc_now()
        updated = item.model_copy(
            update={
                "status": "blocked",
                "task_id": task_id or item.task_id,
                "error_summary": reason.strip() or item.error_summary,
                "lease_owner": None,
                "lease_token": None,
                "updated_at": now,
            },
        )
        stored = self._mailbox_repository.upsert_item(updated)
        self._sync_runtime(
            stored.agent_id,
            current_mailbox_id=stored.id,
            current_task_id=stored.task_id,
            checkpoint_id=checkpoint_id,
            error_summary=stored.error_summary,
            force_status="blocked",
        )
        self._publish_runtime_event(
            topic="actor-mailbox",
            action="blocked",
            payload={
                "agent_id": stored.agent_id,
                "mailbox_id": stored.id,
                "task_id": stored.task_id,
                "error": stored.error_summary,
            },
        )
        return stored

    def pause_actor(self, agent_id: str, *, reason: str | None = None) -> AgentRuntimeRecord:
        runtime = self._require_runtime(agent_id)
        self._cancel_kernel_task(
            runtime.current_task_id,
            reason=reason or "paused by actor control",
        )
        metadata = dict(runtime.metadata)
        if reason:
            metadata["pause_reason"] = reason
        updated = runtime.model_copy(
            update={
                "desired_state": "paused",
                "runtime_status": "paused",
                "metadata": metadata,
                "updated_at": _utc_now(),
            },
        )
        return self._runtime_repository.upsert_runtime(updated)

    def resume_actor(self, agent_id: str) -> AgentRuntimeRecord:
        runtime = self._require_runtime(agent_id)
        metadata = dict(runtime.metadata)
        metadata.pop("pause_reason", None)
        updated = runtime.model_copy(
            update={
                "desired_state": "active",
                "runtime_status": (
                    "queued"
                    if self.pending_count(agent_id) > 0
                    else "assigned"
                    if self._runtime_has_active_assignment(runtime)
                    else "idle"
                ),
                "metadata": metadata,
                "updated_at": _utc_now(),
            },
        )
        return self._runtime_repository.upsert_runtime(updated)

    def cancel_actor_task(self, agent_id: str, *, task_id: str | None = None) -> dict[str, object]:
        cancelled: list[str] = []
        cancelled_kernel_task_ids: list[str] = []
        for item in self.list_items(agent_id=agent_id, limit=None):
            if task_id is not None and item.task_id != task_id:
                continue
            if item.status in _TERMINAL_MAILBOX_STATUSES:
                continue
            if self._cancel_kernel_task(
                item.task_id,
                reason="cancelled by actor control",
            ) and item.task_id:
                cancelled_kernel_task_ids.append(item.task_id)
            self.cancel_item(item.id, reason="cancelled by actor control")
            cancelled.append(item.id)
        if task_id is not None and task_id not in cancelled_kernel_task_ids:
            if self._cancel_kernel_task(task_id, reason="cancelled by actor control"):
                cancelled_kernel_task_ids.append(task_id)
        runtime = self._sync_runtime(agent_id, current_mailbox_id=None, current_task_id=None)
        return {
            "agent_id": agent_id,
            "cancelled_mailbox_ids": cancelled,
            "cancelled_kernel_task_ids": cancelled_kernel_task_ids,
            "runtime_status": runtime.runtime_status,
        }

    def list_teammates(
        self,
        *,
        agent_id: str,
        industry_instance_id: str | None = None,
    ) -> list[dict[str, object]]:
        runtime = self._runtime_repository.get_runtime(agent_id)
        resolved_instance_id = industry_instance_id or (
            runtime.industry_instance_id if runtime is not None else None
        )
        if not resolved_instance_id:
            return []
        teammates = self._runtime_repository.list_runtimes(
            industry_instance_id=resolved_instance_id,
            limit=None,
        )
        payload: list[dict[str, object]] = []
        for teammate in teammates:
            if teammate.agent_id == agent_id or teammate.desired_state == "retired":
                continue
            bindings = []
            if self._thread_binding_repository is not None:
                bindings = [
                    binding.model_dump(mode="json")
                    for binding in self._thread_binding_repository.list_bindings(
                        agent_id=teammate.agent_id,
                        active_only=True,
                    )
                ]
            payload.append(
                {
                    **teammate.model_dump(mode="json"),
                    "thread_bindings": bindings,
                },
            )
        payload.sort(key=lambda item: (item.get("queue_depth") or 0, item.get("role_name") or ""), reverse=True)
        return payload

    def create_checkpoint(
        self,
        *,
        agent_id: str,
        mailbox_id: str | None,
        task_id: str | None,
        checkpoint_kind: str,
        status: str,
        phase: str,
        conversation_thread_id: str | None = None,
        environment_ref: str | None = None,
        work_context_id: str | None = None,
        snapshot_payload: dict[str, object] | None = None,
        resume_payload: dict[str, object] | None = None,
        summary: str = "",
    ) -> AgentCheckpointRecord | None:
        if self._checkpoint_repository is None:
            return None
        resolved_work_context_id = _non_empty_str(work_context_id)
        if resolved_work_context_id is None and mailbox_id:
            mailbox_item = self._mailbox_repository.get_item(mailbox_id)
            if mailbox_item is not None:
                resolved_work_context_id = _non_empty_str(mailbox_item.work_context_id)
        checkpoint = AgentCheckpointRecord(
            agent_id=agent_id,
            mailbox_id=mailbox_id,
            task_id=task_id,
            work_context_id=resolved_work_context_id,
            checkpoint_kind=(
                checkpoint_kind
                if checkpoint_kind in {"worker-step", "resume", "handoff", "task-result"}
                else "worker-step"
            ),
            status=(status if status in {"ready", "applied", "abandoned", "failed"} else "ready"),
            phase=phase,
            conversation_thread_id=conversation_thread_id,
            environment_ref=environment_ref,
            snapshot_payload=dict(snapshot_payload or {}),
            resume_payload=dict(resume_payload or {}),
            summary=summary,
        )
        stored = self._checkpoint_repository.upsert_checkpoint(checkpoint)
        self._sync_runtime(
            agent_id,
            current_mailbox_id=mailbox_id,
            current_task_id=task_id,
            checkpoint_id=stored.id,
        )
        return stored

    def pending_count(self, agent_id: str) -> int:
        return sum(
            1
            for item in self._mailbox_repository.list_items(agent_id=agent_id, limit=None)
            if item.status in _QUEUE_MAILBOX_STATUSES
        )

    def _require_item(self, item_id: str) -> AgentMailboxRecord:
        item = self._mailbox_repository.get_item(item_id)
        if item is None:
            raise KeyError(f"Mailbox item '{item_id}' not found")
        return item

    def _require_runtime(self, agent_id: str) -> AgentRuntimeRecord:
        runtime = self._runtime_repository.get_runtime(agent_id)
        if runtime is None:
            raise KeyError(f"Actor runtime '{agent_id}' not found")
        return runtime

    def _cancel_kernel_task(self, task_id: str | None, *, reason: str) -> bool:
        if not isinstance(task_id, str) or not task_id.strip():
            return False
        dispatcher = self._kernel_dispatcher
        if dispatcher is None:
            return False
        lifecycle = getattr(dispatcher, "lifecycle", None)
        get_task = getattr(lifecycle, "get_task", None)
        task = get_task(task_id) if callable(get_task) else None
        if task is None or getattr(task, "phase", None) in _TERMINAL_KERNEL_PHASES:
            return False
        cancel_task = getattr(dispatcher, "cancel_task", None)
        if not callable(cancel_task):
            return False
        try:
            cancel_task(task_id, resolution=reason)
        except Exception:
            logger.exception("Failed to cancel kernel task from actor control: %s", task_id)
            return False
        return True

    def _sync_runtime(
        self,
        agent_id: str,
        *,
        current_mailbox_id: str | None,
        current_task_id: str | None = None,
        checkpoint_id: str | None = None,
        result_summary: str | None = None,
        error_summary: str | None = None,
        force_status: str | None = None,
    ) -> AgentRuntimeRecord:
        runtime = self._runtime_repository.get_runtime(agent_id)
        now = _utc_now()
        queue_depth = self.pending_count(agent_id)
        if runtime is None:
            runtime = AgentRuntimeRecord(
                agent_id=agent_id,
                actor_key=agent_id,
                runtime_status="idle",
                desired_state="active",
                activation_mode="persistent",
                persistent=True,
            )
        resolved_error_summary = normalize_runtime_summary(
            error_summary if error_summary is not None else runtime.last_error_summary,
        )
        resolved_result_summary = normalize_runtime_summary(
            result_summary if result_summary is not None else runtime.last_result_summary,
        )
        mailbox_runtime_status = self._resolve_mailbox_runtime_status(current_mailbox_id)
        runtime_status = runtime.runtime_status
        if runtime.desired_state == "retired":
            runtime_status = "retired"
        elif runtime.desired_state == "paused":
            runtime_status = "paused"
        elif force_status is not None:
            runtime_status = force_status
        elif mailbox_runtime_status is not None:
            runtime_status = mailbox_runtime_status
        elif should_block_runtime_error(resolved_error_summary) and runtime_status not in {
            "paused",
            "retired",
        }:
            runtime_status = "blocked"
        elif queue_depth > 0:
            runtime_status = "queued"
        elif self._runtime_has_active_assignment(runtime):
            runtime_status = "assigned"
        else:
            runtime_status = "idle"
        updated = runtime.model_copy(
            update={
                "queue_depth": queue_depth,
                "current_mailbox_id": current_mailbox_id,
                "current_task_id": current_task_id,
                "last_checkpoint_id": checkpoint_id or runtime.last_checkpoint_id,
                "last_result_summary": resolved_result_summary,
                "last_error_summary": resolved_error_summary,
                "last_heartbeat_at": now,
                "runtime_status": runtime_status,
                "updated_at": now,
            },
        )
        return self._runtime_repository.upsert_runtime(updated)

    def _runtime_has_active_assignment(self, runtime: AgentRuntimeRecord | None) -> bool:
        if runtime is None:
            return False
        metadata = dict(runtime.metadata or {})
        assignment_id = _non_empty_str(metadata.get("current_assignment_id"))
        assignment_status = _non_empty_str(metadata.get("current_assignment_status"))
        if assignment_id is None:
            return False
        return assignment_status in _ACTIVE_ASSIGNMENT_STATUSES or assignment_status is None

    def _resolve_mailbox_runtime_status(self, mailbox_id: str | None) -> str | None:
        if not isinstance(mailbox_id, str) or not mailbox_id.strip():
            return None
        item = self._mailbox_repository.get_item(mailbox_id)
        if item is None:
            return None
        if item.status == "blocked":
            return "blocked"
        if item.status == "running":
            return "executing"
        if item.status == "leased":
            return "claimed"
        if item.status in {"queued", "retry-wait"}:
            return "queued"
        return None

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


def _task_phase(task: object | None) -> str | None:
    if task is None:
        return None
    phase = getattr(task, "phase", None)
    if not isinstance(phase, str):
        return None
    resolved = phase.strip()
    return resolved or None


def _non_empty_str(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None
