# -*- coding: utf-8 -*-
"""Startup recovery helpers for the runtime host."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..industry.models import IndustrySeatCapabilityLayers
from ..kernel.main_brain_exception_absorption import resolve_absorption_continuity_context
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
    absorption_case_count: int = 0
    absorption_human_required_case_count: int = 0
    absorption_case_counts: dict[str, int] = Field(default_factory=dict)
    absorption_recovery_counts: dict[str, int] = Field(default_factory=dict)
    absorption_summary: str = ""
    absorption_action_kind: str = ""
    absorption_action_summary: str = ""
    absorption_action_materialized: bool = False
    absorption_replan_decision_kind: str = ""
    absorption_human_task_id: str | None = None
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


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    return {}


def _first_non_empty(*values: object | None) -> str | None:
    for value in values:
        if (text := _string(value)) is not None:
            return text
    return None


def _record_absorption_action(
    *,
    summary: StartupRecoverySummary,
    action: object,
    materialization: dict[str, object],
) -> None:
    summary.absorption_action_kind = _string(getattr(action, "kind", None)) or ""
    summary.absorption_action_summary = (
        _string(getattr(action, "human_action_summary", None))
        or _string(getattr(action, "summary", None))
        or ""
    )
    summary.absorption_action_materialized = bool(materialization.get("materialized"))
    summary.absorption_replan_decision_kind = (
        _string(getattr(action, "replan_decision_kind", None)) or ""
    )
    summary.absorption_human_task_id = _string(materialization.get("human_task_id"))


def _materialize_exception_absorption_action(
    *,
    action: object,
    runtimes: list[object],
    mailbox_items: list[object],
    human_assist_task_service: object | None,
) -> dict[str, object]:
    if _string(getattr(action, "kind", None)) != "human-assist":
        return {"materialized": False}
    ensure_task = getattr(
        human_assist_task_service,
        "ensure_exception_absorption_task",
        None,
    )
    if not callable(ensure_task):
        return {"materialized": False, "materialization_reason": "unsupported-service"}
    context = resolve_absorption_continuity_context(
        action,
        runtimes=runtimes,
        mailbox_items=mailbox_items,
    )
    if context.chat_thread_id is None:
        return {"materialized": False, "materialization_reason": "missing-chat-thread"}
    contract = _mapping(getattr(action, "human_action_contract", None))
    acceptance_spec = _mapping(contract.get("acceptance_spec"))
    verification_anchor = _first_non_empty(
        contract.get("resume_checkpoint_ref"),
        (acceptance_spec.get("hard_anchors") or [None])[0]
        if isinstance(acceptance_spec.get("hard_anchors"), list)
        and acceptance_spec.get("hard_anchors")
        else None,
        getattr(action, "scope_ref", None),
        "human-return",
    ) or "human-return"
    task = ensure_task(
        chat_thread_id=context.chat_thread_id,
        profile_id=context.profile_id,
        industry_instance_id=context.industry_instance_id,
        assignment_id=context.assignment_id,
        task_id=context.task_id,
        title=_string(contract.get("title")) or "补一个必要人类动作",
        summary=(
            _string(contract.get("summary"))
            or _string(getattr(action, "summary", None))
            or ""
        ),
        required_action=(
            _string(contract.get("required_action"))
            or _string(getattr(action, "human_action_summary", None))
            or _string(getattr(action, "summary", None))
            or ""
        ),
        resume_checkpoint_ref=verification_anchor,
        verification_anchor=verification_anchor,
        block_evidence_refs=[item for item in [getattr(action, "scope_ref", None), context.environment_ref] if item],
        continuation_context={
            **context.to_payload(),
            "owner_agent_id": _string(getattr(action, "owner_agent_id", None)),
            "case_kind": _string(getattr(action, "case_kind", None)),
            "recovery_rung": _string(getattr(action, "recovery_rung", None)),
            "main_brain_runtime": {
                "control_thread_id": context.control_thread_id or context.chat_thread_id,
                "session_id": context.session_id or context.chat_thread_id,
                "work_context_id": context.work_context_id,
                "environment_ref": context.environment_ref,
                "recovery_mode": "exception-absorption",
                "recovery_reason": _string(getattr(action, "summary", None)),
                "resume_checkpoint_id": verification_anchor,
            },
        },
    )
    return {
        "materialized": True,
        "human_task_id": task.id,
        "human_task_status": task.status,
    }


def _detect_requested_surfaces(
    message_text: str | None,
    *,
    metadata: dict[str, Any] | None = None,
) -> list[str]:
    resolved_metadata = metadata if isinstance(metadata, dict) else {}
    capability_ids, capability_layers_declared, capability_layers_valid = (
        _resolve_runtime_capability_projection(resolved_metadata)
    )
    if capability_layers_declared and not capability_layers_valid:
        return []
    return infer_requested_execution_surfaces(
        texts=[
            _string(message_text),
            _string(resolved_metadata.get("role_summary")),
            _string(resolved_metadata.get("industry_role_name")),
            _string(resolved_metadata.get("role_name")),
        ],
        capability_ids=capability_ids,
        environment_texts=_unique_strings(
            resolved_metadata.get("environment_constraints"),
            resolved_metadata.get("role_summary"),
            resolved_metadata.get("industry_role_name"),
            resolved_metadata.get("role_name"),
        ),
        allow_hard_hints_without_text=True,
    )


def _resolve_runtime_capability_ids(metadata: dict[str, Any]) -> list[str]:
    return _resolve_runtime_capability_projection(metadata)[0]


def _resolve_runtime_capability_projection(
    metadata: dict[str, Any],
) -> tuple[list[str], bool, bool]:
    capability_layers = metadata.get("capability_layers")
    if "capability_layers" in metadata:
        if not isinstance(capability_layers, dict):
            return [], True, False
        for field_name in (
            "role_prototype_capability_ids",
            "seat_instance_capability_ids",
            "cycle_delta_capability_ids",
            "session_overlay_capability_ids",
            "effective_capability_ids",
        ):
            if field_name not in capability_layers:
                continue
            if not isinstance(capability_layers.get(field_name), (list, tuple, set)):
                return [], True, False
        try:
            merged = IndustrySeatCapabilityLayers.from_metadata(
                capability_layers,
            ).merged_capability_ids()
        except Exception:
            return [], True, False
        return merged, True, True
    return _unique_strings(metadata.get("allowed_capabilities")), False, True


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
    runtime_repository: Any | None = None,
    exception_absorption_service: Any | None = None,
    human_assist_task_service: Any | None = None,
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

    if exception_absorption_service is not None:
        resolved_runtime_repository = runtime_repository or getattr(
            actor_mailbox_service,
            "_runtime_repository",
            None,
        )
        list_runtimes = getattr(resolved_runtime_repository, "list_runtimes", None)
        list_items = getattr(actor_mailbox_service, "list_items", None)
        list_human_assist = getattr(human_assist_task_service, "list_tasks", None)
        try:
            runtimes = list(list_runtimes(limit=None) if callable(list_runtimes) else [])
            mailbox_items = list(list_items(limit=None) if callable(list_items) else [])
            human_assist_tasks = list(
                list_human_assist(limit=None) if callable(list_human_assist) else []
            )
            absorption_summary = exception_absorption_service.scan(
                runtimes=runtimes,
                mailbox_items=mailbox_items,
                human_assist_tasks=human_assist_tasks,
                now=_utc_now(),
            )
            summary.absorption_case_count = absorption_summary.case_count
            summary.absorption_human_required_case_count = (
                absorption_summary.human_required_case_count
            )
            summary.absorption_case_counts = dict(absorption_summary.case_counts)
            summary.absorption_recovery_counts = dict(absorption_summary.recovery_counts)
            summary.absorption_summary = absorption_summary.main_brain_summary
            absorb = getattr(exception_absorption_service, "absorb", None)
            if callable(absorb):
                absorption_action = absorb(
                    runtimes=runtimes,
                    mailbox_items=mailbox_items,
                    human_assist_tasks=human_assist_tasks,
                    now=_utc_now(),
                    human_assist_contract_builder=getattr(
                        human_assist_task_service,
                        "build_exception_absorption_contract",
                        None,
                    ),
                )
                if absorption_action is not None:
                    materialization = _materialize_exception_absorption_action(
                        action=absorption_action,
                        runtimes=runtimes,
                        mailbox_items=mailbox_items,
                        human_assist_task_service=human_assist_task_service,
                    )
                    _record_absorption_action(
                        summary=summary,
                        action=absorption_action,
                        materialization=materialization,
                    )
        except Exception as exc:  # pragma: no cover - guardrail
            summary.notes.append(f"exception absorption scan failed: {exc}")

    if runtime_event_bus is not None:
        runtime_event_bus.publish(
            topic="system",
            action="recovery",
            payload=summary.model_dump(mode="json"),
        )
    return summary

__all__ = ["StartupRecoverySummary", "run_startup_recovery"]
