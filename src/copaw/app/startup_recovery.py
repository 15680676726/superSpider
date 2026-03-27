# -*- coding: utf-8 -*-
"""Startup recovery helpers for the runtime host."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..kernel.surface_routing import infer_requested_execution_surfaces


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StartupRecoverySummary(BaseModel):
    reason: str
    recovered_at: datetime = Field(default_factory=_utc_now)
    reaped_expired_leases: int = 0
    recovered_orphaned_leases: int = 0
    reaped_expired_actor_leases: int = 0
    recovered_orphaned_actor_leases: int = 0
    recovered_orphaned_mailbox_items: int = 0
    requeued_orphaned_mailbox_items: int = 0
    blocked_orphaned_mailbox_items: int = 0
    resolved_orphaned_mailbox_items: int = 0
    expired_decisions: int = 0
    pending_decisions: int = 0
    hydrated_waiting_confirm_tasks: int = 0
    recovered_legacy_chat_writebacks: int = 0
    cancelled_legacy_chat_writeback_tasks: int = 0
    active_schedules: int = 0
    notes: list[str] = Field(default_factory=list)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    return text or None


def _unique_strings(*values: object) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()

    def _append(value: object) -> None:
        text = _string(value)
        if text is None or text in seen:
            return
        seen.add(text)
        resolved.append(text)

    for value in values:
        if isinstance(value, (list, tuple, set)):
            for item in value:
                _append(item)
            continue
        _append(value)
    return resolved


def _detect_requested_surfaces(
    message_text: str | None,
    *,
    metadata: dict[str, Any] | None = None,
) -> list[str]:
    resolved_metadata = metadata if isinstance(metadata, dict) else {}
    return infer_requested_execution_surfaces(
        texts=[
            _string(message_text),
            _string(resolved_metadata.get("role_summary")),
            _string(resolved_metadata.get("industry_role_name")),
            _string(resolved_metadata.get("role_name")),
        ],
        capability_ids=_unique_strings(resolved_metadata.get("allowed_capabilities")),
        environment_texts=_unique_strings(
            resolved_metadata.get("environment_constraints"),
            resolved_metadata.get("role_summary"),
            resolved_metadata.get("industry_role_name"),
            resolved_metadata.get("role_name"),
        ),
        allow_hard_hints_without_text=True,
    )


def _runtime_has_terminal_signal(runtime: object | None) -> bool:
    if runtime is None:
        return False
    return any(
        _string(getattr(runtime, field_name, None)) is not None
        for field_name in ("last_evidence_id", "last_error_summary")
    )


def _recover_legacy_execution_core_chat_writebacks(
    *,
    summary: StartupRecoverySummary,
    backlog_item_repository: Any | None,
    assignment_repository: Any | None,
    goal_repository: Any | None,
    goal_override_repository: Any | None,
    task_repository: Any | None,
    task_runtime_repository: Any | None,
    kernel_dispatcher: Any | None,
) -> None:
    if (
        backlog_item_repository is None
        or assignment_repository is None
        or goal_repository is None
        or task_repository is None
        or task_runtime_repository is None
    ):
        return
    list_items = getattr(backlog_item_repository, "list_items", None)
    if not callable(list_items):
        return
    try:
        backlog_items = list_items(status="materialized", limit=None)
    except Exception as exc:  # pragma: no cover - guardrail
        summary.notes.append(f"legacy chat-writeback scan failed: {exc}")
        return
    for backlog_item in backlog_items or []:
        metadata = dict(getattr(backlog_item, "metadata", None) or {})
        source = _string(metadata.get("source")) or _string(getattr(backlog_item, "source_ref", None))
        if _string(getattr(backlog_item, "source_kind", None)) != "operator":
            continue
        if source != "chat-writeback" and not str(source or "").startswith("chat-writeback:"):
            continue
        assignment = None
        assignment_id = _string(getattr(backlog_item, "assignment_id", None))
        if assignment_id is not None:
            getter = getattr(assignment_repository, "get_assignment", None)
            if callable(getter):
                assignment = getter(assignment_id)
        resolved_role_id = (
            _string(getattr(assignment, "owner_role_id", None))
            or _string(metadata.get("industry_role_id"))
        )
        if resolved_role_id != "execution-core":
            continue
        if _unique_strings(metadata.get("chat_writeback_target_match_signals")):
            continue
        requested_surfaces = _unique_strings(
            metadata.get("chat_writeback_requested_surfaces"),
            _detect_requested_surfaces(
                _string(metadata.get("chat_writeback_instruction"))
                or _string(getattr(backlog_item, "summary", None))
                or _string(getattr(backlog_item, "title", None)),
                metadata=metadata,
            ),
        )
        if not requested_surfaces:
            continue
        if list(getattr(backlog_item, "evidence_ids", []) or []):
            continue
        if assignment is not None and list(getattr(assignment, "evidence_ids", []) or []):
            continue
        goal_id = (
            _string(getattr(backlog_item, "goal_id", None))
            or _string(getattr(assignment, "goal_id", None))
        )
        tasks = (
            list(task_repository.list_tasks(goal_id=goal_id))
            if goal_id is not None and callable(getattr(task_repository, "list_tasks", None))
            else []
        )
        runtimes_by_task_id = {
            task.id: task_runtime_repository.get_runtime(task.id)
            for task in tasks
        }
        if any(_runtime_has_terminal_signal(runtime) for runtime in runtimes_by_task_id.values()):
            continue
        recovery_reason = (
            "Recovered legacy execution-core chat-writeback routing gap during startup; "
            f"requested surfaces: {','.join(requested_surfaces)}."
        )
        gap_kind = "capability-gap" if requested_surfaces else "routing-pending"
        updated_metadata = dict(metadata)
        updated_metadata["chat_writeback_requested_surfaces"] = list(requested_surfaces)
        updated_metadata["chat_writeback_gap_kind"] = gap_kind
        updated_metadata["chat_writeback_classes"] = _unique_strings(
            metadata.get("chat_writeback_classes"),
            "routing-pending",
            gap_kind,
        )
        updated_metadata["chat_writeback_target_match_signals"] = _unique_strings(
            metadata.get("chat_writeback_target_match_signals"),
            "recovered legacy execution-core routing gap for requested execution surface: "
            + ",".join(requested_surfaces),
        )
        backlog_item_repository.upsert_item(
            backlog_item.model_copy(
                update={
                    "status": "open",
                    "cycle_id": None,
                    "assignment_id": None,
                    "goal_id": None,
                    "metadata": updated_metadata,
                    "updated_at": _utc_now(),
                },
            ),
        )
        if assignment is not None:
            assignment_repository.upsert_assignment(
                assignment.model_copy(
                    update={
                        "status": "cancelled",
                        "updated_at": _utc_now(),
                    },
                ),
            )
        if goal_id is not None:
            goal = goal_repository.get_goal(goal_id)
            if goal is not None and getattr(goal, "status", None) != "archived":
                goal_repository.upsert_goal(
                    goal.model_copy(update={"status": "archived", "updated_at": _utc_now()}),
                )
            if goal_override_repository is not None:
                override = goal_override_repository.get_override(goal_id)
                if override is not None and getattr(override, "status", None) != "archived":
                    goal_override_repository.upsert_override(
                        override.model_copy(
                            update={"status": "archived", "updated_at": _utc_now()},
                        ),
                    )
            for task in tasks:
                runtime = runtimes_by_task_id.get(task.id)
                task_phase = _string(getattr(runtime, "current_phase", None)) or _string(
                    getattr(task, "status", None),
                )
                if task_phase in {"completed", "failed", "cancelled"}:
                    continue
                cancelled = False
                if kernel_dispatcher is not None and callable(
                    getattr(kernel_dispatcher, "cancel_task", None),
                ):
                    try:
                        kernel_dispatcher.cancel_task(task.id, resolution=recovery_reason)
                        cancelled = True
                    except Exception as exc:  # pragma: no cover - guardrail
                        summary.notes.append(
                            f"legacy chat-writeback cancel_task failed for {task.id}: {exc}",
                        )
                if not cancelled:
                    task_repository.upsert_task(
                        task.model_copy(update={"status": "cancelled", "updated_at": _utc_now()}),
                    )
                    if runtime is not None:
                        task_runtime_repository.upsert_runtime(
                            runtime.model_copy(
                                update={
                                    "runtime_status": "terminated",
                                    "current_phase": "cancelled",
                                    "last_error_summary": recovery_reason,
                                    "updated_at": _utc_now(),
                                },
                            ),
                        )
                summary.cancelled_legacy_chat_writeback_tasks += 1
        summary.recovered_legacy_chat_writebacks += 1
        backlog_id = _string(getattr(backlog_item, "id", None)) or "unknown"
        summary.notes.append(
            f"recovered legacy execution-core chat-writeback gap: {backlog_id}",
        )


def run_startup_recovery(
    *,
    environment_service: Any | None,
    actor_mailbox_service: Any | None,
    decision_request_repository: Any | None,
    kernel_dispatcher: Any | None,
    kernel_task_store: Any | None,
    schedule_repository: Any | None,
    backlog_item_repository: Any | None = None,
    assignment_repository: Any | None = None,
    goal_repository: Any | None = None,
    goal_override_repository: Any | None = None,
    task_repository: Any | None = None,
    task_runtime_repository: Any | None = None,
    runtime_event_bus: Any | None = None,
    reason: str = "startup",
) -> StartupRecoverySummary:
    """Recover lease/decision state after host startup or restart."""
    summary = StartupRecoverySummary(reason=reason)

    if environment_service is not None:
        try:
            summary.reaped_expired_leases = int(
                environment_service.reap_expired_leases(),
            )
        except Exception as exc:  # pragma: no cover - guardrail
            summary.notes.append(f"reap_expired_leases failed: {exc}")
        try:
            summary.recovered_orphaned_leases = int(
                environment_service.recover_orphaned_leases(
                    allow_cross_process_recovery=True,
                ),
            )
        except Exception as exc:  # pragma: no cover - guardrail
            summary.notes.append(f"recover_orphaned_leases failed: {exc}")
        try:
            summary.reaped_expired_actor_leases = int(
                environment_service.reap_expired_actor_leases(),
            )
        except Exception as exc:  # pragma: no cover - guardrail
            summary.notes.append(f"reap_expired_actor_leases failed: {exc}")
        try:
            summary.recovered_orphaned_actor_leases = int(
                environment_service.recover_orphaned_actor_leases(),
            )
        except Exception as exc:  # pragma: no cover - guardrail
            summary.notes.append(f"recover_orphaned_actor_leases failed: {exc}")

    if decision_request_repository is not None:
        decisions = list(decision_request_repository.list_decision_requests())
        now = _utc_now()
        for decision in decisions:
            if getattr(decision, "status", None) not in {"open", "reviewing"}:
                continue
            expires_at = getattr(decision, "expires_at", None)
            if expires_at is not None and expires_at <= now:
                if kernel_dispatcher is not None:
                    try:
                        kernel_dispatcher.expire_decision(
                            decision.id,
                            resolution="Recovered expired decision during startup.",
                        )
                        summary.expired_decisions += 1
                        continue
                    except Exception as exc:  # pragma: no cover - guardrail
                        summary.notes.append(
                            f"expire_decision failed for {decision.id}: {exc}",
                        )
                if kernel_task_store is not None:
                    try:
                        expired = kernel_task_store.expire_decision_request(
                            decision.id,
                            resolution="Recovered expired decision during startup.",
                        )
                        if expired is not None:
                            summary.expired_decisions += 1
                            continue
                    except Exception as exc:  # pragma: no cover - guardrail
                        summary.notes.append(
                            f"expire_decision_request failed for {decision.id}: {exc}",
                        )
            summary.pending_decisions += 1
            if kernel_dispatcher is not None:
                try:
                    task = kernel_dispatcher.lifecycle.get_task(decision.task_id)
                except Exception as exc:  # pragma: no cover - guardrail
                    summary.notes.append(
                        f"hydrate waiting-confirm task failed for {decision.task_id}: {exc}",
                    )
                    continue
                if task is not None and getattr(task, "phase", None) == "waiting-confirm":
                    summary.hydrated_waiting_confirm_tasks += 1

    if actor_mailbox_service is not None:
        recover_items = getattr(actor_mailbox_service, "recover_orphaned_items", None)
        task_reader = None
        if kernel_dispatcher is not None:
            lifecycle = getattr(kernel_dispatcher, "lifecycle", None)
            task_reader = getattr(lifecycle, "get_task", None)
        if not callable(task_reader) and kernel_task_store is not None:
            task_reader = getattr(kernel_task_store, "get", None)
        if callable(recover_items):
            try:
                mailbox_summary = recover_items(task_reader=task_reader)
                summary.recovered_orphaned_mailbox_items = int(
                    mailbox_summary.get("total", 0),
                )
                summary.requeued_orphaned_mailbox_items = int(
                    mailbox_summary.get("requeued", 0),
                )
                summary.blocked_orphaned_mailbox_items = int(
                    mailbox_summary.get("blocked", 0),
                )
                summary.resolved_orphaned_mailbox_items = (
                    int(mailbox_summary.get("completed", 0))
                    + int(mailbox_summary.get("failed", 0))
                    + int(mailbox_summary.get("cancelled", 0))
                )
            except Exception as exc:  # pragma: no cover - guardrail
                summary.notes.append(f"recover_orphaned_mailbox_items failed: {exc}")

    _recover_legacy_execution_core_chat_writebacks(
        summary=summary,
        backlog_item_repository=backlog_item_repository,
        assignment_repository=assignment_repository,
        goal_repository=goal_repository,
        goal_override_repository=goal_override_repository,
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=kernel_dispatcher,
    )

    if schedule_repository is not None:
        try:
            schedules = list(schedule_repository.list_schedules())
            summary.active_schedules = sum(
                1
                for schedule in schedules
                if getattr(schedule, "status", None) != "deleted"
            )
        except Exception as exc:  # pragma: no cover - guardrail
            summary.notes.append(f"schedule scan failed: {exc}")

    if runtime_event_bus is not None:
        runtime_event_bus.publish(
            topic="system",
            action="recovery",
            payload=summary.model_dump(mode="json"),
        )
    return summary

__all__ = ["StartupRecoverySummary", "run_startup_recovery"]
