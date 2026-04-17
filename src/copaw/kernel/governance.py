# -*- coding: utf-8 -*-
"""Governance services for emergency controls and batch runtime actions."""
from __future__ import annotations

import inspect
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..evidence import EvidenceLedger, EvidenceRecord
from ..state import GovernanceControlRecord
from ..state.repositories import BaseGovernanceControlRepository

logger = logging.getLogger(__name__)

_CONTROL_ID = "runtime"
_GOVERNANCE_TASK_ID = "governance:runtime"
_BLOCKED_SYSTEM_CAPABILITIES = frozenset(
    {
        "system:dispatch_query",
        "system:dispatch_command",
        "system:send_channel_text",
        "system:run_learning_strategy",
        "system:auto_apply_patches",
        "system:apply_patch",
    }
)
_RUNTIME_GOVERNANCE_BLOCKED_CAPABILITIES = frozenset(
    {
        "system:dispatch_query",
        "system:dispatch_command",
    }
)
_WRITEBACK_ONLY_REQUESTED_ACTIONS = frozenset(
    {
        "writeback_strategy",
        "writeback_backlog",
        "writeback_schedule",
    }
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _first_non_empty(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _mapping_value(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def _string_list(value: object | None) -> list[str]:
    raw_items = value if isinstance(value, (list, tuple, set)) else [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = _first_non_empty(item)
        if text is None:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return normalized


def _dict_list(value: object | None) -> list[dict[str, object]]:
    if not isinstance(value, (list, tuple, set)):
        return []
    payloads: list[dict[str, object]] = []
    for item in value:
        payload = _mapping_value(item)
        if payload:
            payloads.append(payload)
    return payloads


def _counted_entries(items: dict[str, int], key_name: str) -> list[dict[str, object]]:
    return [
        {key_name: key, "count": count}
        for key, count in sorted(items.items(), key=lambda entry: (-entry[1], entry[0]))
    ]


def _build_decision_provenance(
    decisions: list[object],
) -> dict[str, object]:
    if not decisions:
        return {
            "open_count": 0,
            "by_type": [],
            "by_risk_level": [],
            "by_requester": [],
        }
    by_type: dict[str, int] = {}
    by_risk_level: dict[str, int] = {}
    by_requester: dict[str, int] = {}
    for decision in decisions:
        decision_type = _first_non_empty(getattr(decision, "decision_type", None), "unknown")
        risk_level = _first_non_empty(getattr(decision, "risk_level", None), "unknown")
        requester = _first_non_empty(getattr(decision, "requested_by", None), "unknown")
        by_type[decision_type] = by_type.get(decision_type, 0) + 1
        by_risk_level[risk_level] = by_risk_level.get(risk_level, 0) + 1
        by_requester[requester] = by_requester.get(requester, 0) + 1
    return {
        "open_count": len(decisions),
        "by_type": _counted_entries(by_type, "decision_type"),
        "by_risk_level": _counted_entries(by_risk_level, "risk_level"),
        "by_requester": _counted_entries(by_requester, "requested_by"),
    }


def _staffing_confirmation_required(entry: object | None) -> bool:
    payload = _mapping_value(entry)
    if not payload:
        return False
    if bool(payload.get("requires_confirmation")):
        return True
    status = _first_non_empty(payload.get("status")) or "unknown"
    if status in {"approved", "rejected", "expired", "completed", "cancelled"}:
        return False
    return _first_non_empty(payload.get("decision_request_id")) is not None


def _resolve_chat_thread_id(payload: dict[str, object]) -> str | None:
    return _first_non_empty(
        payload.get("chat_thread_id"),
        payload.get("control_thread_id"),
        payload.get("session_id"),
    )


def _resolve_industry_instance_id_from_thread_id(thread_id: str | None) -> str | None:
    normalized = _first_non_empty(thread_id)
    if normalized is None:
        return None
    if not normalized.startswith("industry-chat:"):
        return None
    _, _, remainder = normalized.partition("industry-chat:")
    instance_id, separator, role_id = remainder.rpartition(":")
    if not instance_id or not separator or not role_id:
        return None
    return _first_non_empty(instance_id)


def _canonical_host_twin_summary(
    detail_payload: dict[str, object],
    host_twin: dict[str, object],
) -> dict[str, object]:
    from ..app.runtime_center.execution_runtime_projection import (
        build_host_twin_summary,
        derive_host_twin_continuity_state,
        host_twin_summary_ready,
    )

    existing_summary = _mapping_value(detail_payload.get("host_twin_summary"))
    derived_summary = build_host_twin_summary(
        host_twin,
        host_companion_session=_mapping_value(detail_payload.get("host_companion_session")),
    )
    if not derived_summary:
        return existing_summary
    if not existing_summary:
        return derived_summary
    existing_ready = host_twin_summary_ready(existing_summary)
    derived_ready = host_twin_summary_ready(derived_summary)
    if derived_ready and not existing_ready:
        preferred_summary = dict(derived_summary)
        fallback_summary = dict(existing_summary)
    elif existing_ready and not derived_ready:
        preferred_summary = dict(existing_summary)
        fallback_summary = dict(derived_summary)
    else:
        preferred_summary = dict(derived_summary)
        fallback_summary = dict(existing_summary)
    merged_summary = dict(fallback_summary)
    merged_summary.update(preferred_summary)
    merged_summary["continuity_state"] = _first_non_empty(
        preferred_summary.get("continuity_state"),
        fallback_summary.get("continuity_state"),
        derive_host_twin_continuity_state(merged_summary),
    )
    return merged_summary


def _resolve_candidate_environment_refs(
    *,
    payload: dict[str, object],
    task_environment_ref: object | None,
) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _append(value: object | None) -> None:
        text = _first_non_empty(value)
        if text is None:
            return
        lowered = text.lower()
        if lowered in seen:
            return
        seen.add(lowered)
        candidates.append(text)

    _append(task_environment_ref)
    _append(payload.get("environment_ref"))
    session_id = _first_non_empty(
        payload.get("session_id"),
        payload.get("control_thread_id"),
    )
    if session_id is not None:
        _append(session_id if session_id.startswith("session:") else None)
        _append(f"session:console:{session_id}")
    instance_id = _first_non_empty(
        payload.get("industry_instance_id"),
        _resolve_industry_instance_id_from_thread_id(
            _resolve_chat_thread_id(payload),
        ),
    )
    if instance_id is not None:
        _append(f"session:console:industry:{instance_id}")
    return candidates


def _batch_action_label(action: str) -> str:
    mapping = {
        "approve": "批准",
        "reject": "驳回",
        "apply": "应用",
        "rollback": "回滚",
    }
    return mapping.get(action, action)


class GovernanceStatus(BaseModel):
    control_id: str = Field(default=_CONTROL_ID)
    emergency_stop_active: bool = False
    emergency_reason: str | None = None
    emergency_actor: str | None = None
    paused_schedule_ids: list[str] = Field(default_factory=list)
    channel_shutdown_applied: bool = False
    blocked_capability_refs: list[str] = Field(default_factory=list)
    pending_decisions: int = 0
    proposed_patches: int = 0
    pending_patches: int = 0
    decision_provenance: dict[str, object] = Field(default_factory=dict)
    host_twin: dict[str, object] = Field(default_factory=dict)
    handoff: dict[str, object] = Field(default_factory=dict)
    staffing: dict[str, object] = Field(default_factory=dict)
    human_assist: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=_utc_now)


class GovernanceBatchResult(BaseModel):
    action: str
    requested: int
    succeeded: int
    failed: int
    actor: str
    results: list[dict[str, object]] = Field(default_factory=list)
    errors: list[dict[str, object]] = Field(default_factory=list)
    evidence_id: str | None = None


class GovernanceService:
    """Unified governance surface for runtime controls and operator batches."""

    def __init__(
        self,
        *,
        control_repository: BaseGovernanceControlRepository,
        decision_request_repository: Any | None = None,
        learning_service: Any | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        runtime_event_bus: Any | None = None,
        cron_manager: Any | None = None,
        channel_manager: Any | None = None,
        kernel_dispatcher: Any | None = None,
        environment_service: Any | None = None,
        human_assist_task_service: Any | None = None,
        industry_service: Any | None = None,
    ) -> None:
        self._control_repository = control_repository
        self._decision_request_repository = decision_request_repository
        self._learning_service = learning_service
        self._evidence_ledger = evidence_ledger
        self._runtime_event_bus = runtime_event_bus
        self._cron_manager = cron_manager
        self._channel_manager = channel_manager
        self._kernel_dispatcher = kernel_dispatcher
        self._environment_service = environment_service
        self._human_assist_task_service = human_assist_task_service
        self._industry_service = industry_service

    def set_runtime_managers(
        self,
        *,
        cron_manager: Any | None = None,
        channel_manager: Any | None = None,
    ) -> None:
        self._cron_manager = cron_manager
        self._channel_manager = channel_manager

    def set_kernel_dispatcher(self, dispatcher: Any | None) -> None:
        self._kernel_dispatcher = dispatcher

    def set_environment_service(self, environment_service: Any | None) -> None:
        self._environment_service = environment_service

    def set_human_assist_task_service(self, human_assist_task_service: Any | None) -> None:
        self._human_assist_task_service = human_assist_task_service

    def set_industry_service(self, industry_service: Any | None) -> None:
        self._industry_service = industry_service

    def get_control(self) -> GovernanceControlRecord:
        control = self._control_repository.get_control(_CONTROL_ID)
        if control is not None:
            return control
        control = GovernanceControlRecord(id=_CONTROL_ID)
        return self._control_repository.upsert_control(control)

    def get_status(self) -> GovernanceStatus:
        control = self.get_control()
        pending_decisions = 0
        open_decisions: list[object] = []
        if self._decision_request_repository is not None:
            try:
                open_decisions = [
                    decision
                    for decision in self._decision_request_repository.list_decision_requests()
                    if getattr(decision, "status", None) in {"open", "reviewing"}
                ]
                pending_decisions = len(open_decisions)
            except Exception:
                logger.exception("Failed to count pending decisions")
                open_decisions = []
        proposed_patches = 0
        pending_patches = 0
        if self._learning_service is not None:
            try:
                patches = list(self._learning_service.list_patches())
                proposed_patches = sum(
                    1
                    for patch in patches
                    if getattr(patch, "status", None) == "proposed"
                )
                pending_patches = sum(
                    1
                    for patch in patches
                    if getattr(patch, "status", None) in {"proposed", "approved"}
                )
            except Exception:
                logger.exception("Failed to summarize learning patches")
        blocked = []
        if control.emergency_stop_active:
            blocked = sorted(
                [*sorted(_BLOCKED_SYSTEM_CAPABILITIES), "skill:*", "mcp:*", "tool:*"]
            )
        host_twin, handoff = self._summarize_host_runtime_governance()
        staffing = self._summarize_staffing_governance()
        human_assist = self._summarize_human_assist_governance()
        return GovernanceStatus(
            control_id=control.id,
            emergency_stop_active=control.emergency_stop_active,
            emergency_reason=control.emergency_reason,
            emergency_actor=control.emergency_actor,
            paused_schedule_ids=list(control.paused_schedule_ids),
            channel_shutdown_applied=control.channel_shutdown_applied,
            blocked_capability_refs=blocked,
            pending_decisions=pending_decisions,
            proposed_patches=proposed_patches,
            pending_patches=pending_patches,
            decision_provenance=_build_decision_provenance(open_decisions),
            host_twin=host_twin,
            handoff=handoff,
            staffing=staffing,
            human_assist=human_assist,
            metadata=dict(control.metadata),
            updated_at=control.updated_at,
        )

    def admission_block_reason(self, task: Any) -> str | None:
        control = self.get_control()
        capability_ref = str(getattr(task, "capability_ref", "") or "")
        if control.emergency_stop_active and self._should_block_capability(capability_ref):
            reason = control.emergency_reason or "Emergency stop is active."
            return f"Emergency stop blocked capability '{capability_ref}'. {reason}"
        if capability_ref not in _RUNTIME_GOVERNANCE_BLOCKED_CAPABILITIES:
            return None
        if self._is_writeback_only_query_task(task):
            return None
        return self._runtime_governance_block_reason(task)

    def _runtime_governance_block_reason(self, task: Any) -> str | None:
        environment_reason = self._environment_handoff_block_reason(task)
        if environment_reason is not None:
            return environment_reason
        human_assist_reason = self._human_assist_block_reason(task)
        if human_assist_reason is not None:
            return human_assist_reason
        staffing_reason = self._staffing_block_reason(task)
        if staffing_reason is not None:
            return staffing_reason
        return None

    @staticmethod
    def _is_writeback_only_query_task(task: Any) -> bool:
        capability_ref = str(getattr(task, "capability_ref", "") or "").strip()
        if capability_ref != "system:dispatch_query":
            return False
        payload = _mapping_value(getattr(task, "payload", None))
        request_payload = _mapping_value(payload.get("request"))
        requested_actions = _string_list(
            request_payload.get("requested_actions"),
        )
        if not requested_actions:
            return False
        return all(action in _WRITEBACK_ONLY_REQUESTED_ACTIONS for action in requested_actions)

    def _environment_handoff_block_reason(self, task: Any) -> str | None:
        payload = _mapping_value(getattr(task, "payload", None))
        resolved = self._resolve_environment_handoff_candidate(
            payload=payload,
            task_environment_ref=getattr(task, "environment_ref", None),
        )
        if resolved is None:
            return None
        session_ref, detail_payload, host_twin, host_twin_summary = resolved
        if not self._host_twin_requires_handoff(host_twin, host_twin_summary):
            return None
        self._ensure_environment_handoff_human_assist_task(
            task=task,
            session_ref=session_ref,
            host_twin=host_twin,
        )
        owner_ref = _first_non_empty(
            host_twin_summary.get("handoff_owner_ref"),
            _mapping_value(host_twin.get("ownership")).get("handoff_owner_ref"),
            host_twin.get("handoff_owner_ref"),
        )
        owner_suffix = f" Owner: {owner_ref}." if owner_ref else ""
        return (
            f"Runtime handoff is active for environment '{session_ref}'. "
            f"Dispatch must wait for the human handoff to return.{owner_suffix}"
        )

    def _ensure_environment_handoff_human_assist_task(
        self,
        *,
        task: Any,
        session_ref: str,
        host_twin: dict[str, object],
    ) -> None:
        service = self._human_assist_task_service
        ensure_task = getattr(service, "ensure_host_handoff_task", None)
        if not callable(ensure_task):
            return
        payload = _mapping_value(getattr(task, "payload", None))
        chat_thread_id = _resolve_chat_thread_id(payload)
        if chat_thread_id is None:
            return
        legal_recovery = _mapping_value(host_twin.get("legal_recovery"))
        coordination = _mapping_value(host_twin.get("coordination"))
        ownership = _mapping_value(host_twin.get("ownership"))
        verification_anchor = _first_non_empty(
            legal_recovery.get("return_condition"),
            legal_recovery.get("checkpoint_ref"),
            legal_recovery.get("resume_kind"),
            ownership.get("handoff_owner_ref"),
            "human-return",
        )
        task_title = _first_non_empty(
            getattr(task, "title", None),
            payload.get("title"),
            "runtime work",
        ) or "runtime work"
        summary = _first_non_empty(
            coordination.get("summary"),
            legal_recovery.get("summary"),
            f"Runtime handoff is active for environment '{session_ref}'.",
        ) or f"Runtime handoff is active for environment '{session_ref}'."
        required_action = (
            f"请在宿主侧完成当前交接后，回到聊天里说明已完成，并包含“{verification_anchor}”。"
        )
        requested_surfaces = _string_list(
            [
                *_string_list(payload.get("requested_surfaces")),
                *_string_list(payload.get("seat_requested_surfaces")),
                *_string_list(payload.get("chat_writeback_requested_surfaces")),
            ],
        )
        continuation_context = {
            "industry_instance_id": _first_non_empty(payload.get("industry_instance_id")),
            "industry_role_id": _first_non_empty(payload.get("industry_role_id")),
            "industry_role_name": _first_non_empty(payload.get("industry_role_name")),
            "industry_label": _first_non_empty(payload.get("industry_label")),
            "owner_scope": _first_non_empty(payload.get("owner_scope")),
            "session_id": _first_non_empty(payload.get("session_id"), chat_thread_id),
            "control_thread_id": _first_non_empty(payload.get("control_thread_id"), chat_thread_id),
            "channel": _first_non_empty(payload.get("channel")),
            "environment_ref": _first_non_empty(payload.get("environment_ref"), session_ref),
            "work_context_id": _first_non_empty(payload.get("work_context_id")),
            "recommended_scheduler_action": _first_non_empty(
                payload.get("recommended_scheduler_action"),
                coordination.get("recommended_scheduler_action"),
            ),
            "requested_surfaces": requested_surfaces,
            "backlog_item_id": _first_non_empty(payload.get("backlog_item_id")),
            "source_report_id": _first_non_empty(payload.get("source_report_id")),
            "main_brain_runtime": {
                "work_context_id": _first_non_empty(payload.get("work_context_id")),
                "control_thread_id": _first_non_empty(
                    payload.get("control_thread_id"),
                    chat_thread_id,
                ),
                "environment_ref": _first_non_empty(payload.get("environment_ref"), session_ref),
                "environment_session_id": _first_non_empty(
                    payload.get("environment_session_id"),
                    session_ref,
                ),
                "environment_binding_kind": _first_non_empty(
                    payload.get("environment_binding_kind"),
                    "host-handoff",
                ),
                "environment_resume_ready": False,
                "recovery_mode": _first_non_empty(
                    payload.get("recovery_mode"),
                    legal_recovery.get("path"),
                    "handoff",
                ),
                "recovery_reason": _first_non_empty(
                    payload.get("recovery_reason"),
                    legal_recovery.get("summary"),
                    coordination.get("summary"),
                    "human-return",
                ),
                "resume_checkpoint_id": _first_non_empty(
                    legal_recovery.get("checkpoint_ref"),
                    verification_anchor,
                ),
                "recommended_scheduler_action": _first_non_empty(
                    payload.get("recommended_scheduler_action"),
                    coordination.get("recommended_scheduler_action"),
                ),
            },
        }
        try:
            ensure_task(
                chat_thread_id=chat_thread_id,
                profile_id=_first_non_empty(payload.get("buddy_profile_id")),
                title=f"Return host handoff for {task_title}",
                summary=summary,
                required_action=required_action,
                industry_instance_id=_first_non_empty(payload.get("industry_instance_id")),
                assignment_id=_first_non_empty(payload.get("assignment_id")),
                task_id=_first_non_empty(payload.get("task_id")),
                resume_checkpoint_ref=_first_non_empty(
                    legal_recovery.get("checkpoint_ref"),
                    verification_anchor,
                ),
                verification_anchor=verification_anchor,
                block_evidence_refs=[
                    session_ref,
                    _first_non_empty(legal_recovery.get("checkpoint_ref")),
                ],
                continuation_context=continuation_context,
            )
        except Exception:
            logger.exception("Failed to ensure host handoff human assist task")

    def _human_assist_block_reason(self, task: Any) -> str | None:
        service = self._human_assist_task_service
        if service is None:
            return None
        payload = _mapping_value(getattr(task, "payload", None))
        chat_thread_id = _resolve_chat_thread_id(payload)
        if chat_thread_id is None:
            return None
        list_tasks = getattr(service, "list_tasks", None)
        if not callable(list_tasks):
            return None
        try:
            tasks = list_tasks(chat_thread_id=chat_thread_id, limit=50)
        except TypeError:
            tasks = list_tasks(chat_thread_id=chat_thread_id)
        except Exception:
            logger.exception("Failed to inspect human assist governance")
            return None
        for task_record in tasks or []:
            payload_record = _mapping_value(task_record)
            status = _first_non_empty(payload_record.get("status")) or "unknown"
            if status in {"closed", "cancelled", "expired", "resume_queued"}:
                continue
            if self._maybe_close_stale_host_handoff_task(
                task_record=task_record,
                payload_record=payload_record,
            ):
                continue
            if status == "need_more_evidence":
                return (
                    f"Human assist evidence is still incomplete for chat thread '{chat_thread_id}'. "
                    "Dispatch must wait for more evidence."
                )
            return (
            f"Human assist handoff is still open for chat thread '{chat_thread_id}'. "
            f"Current status: {status}."
        )
        return None

    def _resolve_environment_handoff_candidate(
        self,
        *,
        payload: dict[str, object],
        task_environment_ref: object | None,
    ) -> tuple[str, dict[str, object], dict[str, object], dict[str, object]] | None:
        service = self._environment_service
        if service is None:
            return None
        candidate_session_refs = _resolve_candidate_environment_refs(
            payload=payload,
            task_environment_ref=task_environment_ref,
        )
        if not candidate_session_refs:
            return None
        getter = getattr(service, "get_session_detail", None)
        if not callable(getter):
            return None
        session_ref: str | None = None
        detail = None
        for candidate in candidate_session_refs:
            try:
                detail = getter(candidate, limit=20)
                if detail is None:
                    continue
                session_ref = candidate
                break
            except TypeError:
                try:
                    detail = getter(candidate)
                    if detail is None:
                        continue
                    session_ref = candidate
                    break
                except Exception:
                    continue
            except Exception:
                continue
        if detail is None or session_ref is None:
            return None
        detail_payload = _mapping_value(detail)
        host_twin = _mapping_value(detail_payload.get("host_twin"))
        host_twin_summary = _canonical_host_twin_summary(detail_payload, host_twin)
        return session_ref, detail_payload, host_twin, host_twin_summary

    def _maybe_close_stale_host_handoff_task(
        self,
        *,
        task_record: object,
        payload_record: dict[str, object],
    ) -> bool:
        service = self._human_assist_task_service
        if service is None:
            return False
        task_type = _first_non_empty(payload_record.get("task_type"))
        reason_code = _first_non_empty(payload_record.get("reason_code"))
        if task_type != "host-handoff-return" and reason_code != "host-handoff-active":
            return False
        submission_payload = _mapping_value(payload_record.get("submission_payload"))
        resolved = self._resolve_environment_handoff_candidate(
            payload=submission_payload,
            task_environment_ref=None,
        )
        if resolved is None:
            return False
        _session_ref, _detail_payload, host_twin, host_twin_summary = resolved
        if self._host_twin_requires_handoff(host_twin, host_twin_summary):
            return False
        task_id = _first_non_empty(payload_record.get("id"), payload_record.get("task_id"))
        closer = getattr(service, "mark_closed", None)
        if task_id is None or not callable(closer):
            return False
        try:
            closer(
                task_id,
                summary="运行时宿主交接已不再阻塞这条控制线程。",
                resume_payload={
                    "resumed": False,
                    "reason": "stale-host-handoff-cleared",
                },
            )
        except Exception:
            logger.exception("Failed to close stale host handoff human assist task")
            return False
        return True

    def _staffing_block_reason(self, task: Any) -> str | None:
        service = self._industry_service
        if service is None:
            return None
        payload = _mapping_value(getattr(task, "payload", None))
        instance_id = _first_non_empty(payload.get("industry_instance_id"))
        if instance_id is None:
            return None
        getter = getattr(service, "get_instance_detail", None)
        if not callable(getter):
            return None
        try:
            detail = getter(instance_id)
        except Exception:
            logger.exception("Failed to inspect staffing governance")
            return None
        staffing = _mapping_value(_mapping_value(detail).get("staffing"))
        active_gap = _mapping_value(staffing.get("active_gap"))
        pending_proposals = _dict_list(staffing.get("pending_proposals"))
        blocker = (
            active_gap
            if _staffing_confirmation_required(active_gap)
            else next(
                (
                    item
                    for item in pending_proposals
                    if _staffing_confirmation_required(item)
                ),
                None,
            )
        )
        if blocker is not None:
            role_name = _first_non_empty(
                blocker.get("target_role_name"),
                blocker.get("summary"),
            ) or instance_id
            return (
                f"Staffing confirmation is still required for industry '{instance_id}' "
                f"before dispatch can continue. Pending gap: {role_name}."
            )
        return None

    def _summarize_host_runtime_governance(self) -> tuple[dict[str, object], dict[str, object]]:
        from ..app.runtime_center.task_review_projection import host_twin_summary_ready

        host_twin_summary = {
            "blocking_session_count": 0,
            "blocking_families": [],
            "session_ids": [],
        }
        handoff_summary = {
            "active": False,
            "session_ids": [],
            "owner_refs": [],
            "blocking_families": [],
        }
        service = self._environment_service
        if service is None:
            return host_twin_summary, handoff_summary
        list_sessions = getattr(service, "list_sessions", None)
        detail_getter = getattr(service, "get_session_detail", None)
        if not callable(list_sessions) or not callable(detail_getter):
            return host_twin_summary, handoff_summary
        try:
            sessions = list_sessions(limit=200)
        except TypeError:
            sessions = list_sessions()
        except Exception:
            logger.exception("Failed to list runtime sessions for governance")
            return host_twin_summary, handoff_summary
        blocking_families: list[str] = []
        owner_refs: list[str] = []
        for session in sessions or []:
            session_payload = _mapping_value(session)
            session_id = _first_non_empty(
                session_payload.get("session_mount_id"),
                session_payload.get("id"),
            )
            if session_id is None:
                continue
            try:
                detail = detail_getter(session_id, limit=20)
            except TypeError:
                detail = detail_getter(session_id)
            except Exception:
                logger.exception("Failed to inspect runtime session '%s'", session_id)
                continue
            detail_payload = _mapping_value(detail)
            host_twin = _mapping_value(detail_payload.get("host_twin"))
            host_twin_summary_payload = _canonical_host_twin_summary(detail_payload, host_twin)
            if host_twin_summary_ready(host_twin_summary_payload):
                continue
            families = _string_list(host_twin.get("active_blocker_families"))
            if families:
                host_twin_summary["blocking_session_count"] = int(host_twin_summary["blocking_session_count"]) + 1
                host_twin_summary["session_ids"] = [*host_twin_summary["session_ids"], session_id]
                blocking_families.extend(families)
            if self._host_twin_requires_handoff(host_twin, host_twin_summary_payload):
                handoff_summary["active"] = True
                handoff_summary["session_ids"] = [*handoff_summary["session_ids"], session_id]
                owner_ref = _first_non_empty(
                    host_twin_summary_payload.get("handoff_owner_ref"),
                    _mapping_value(host_twin.get("ownership")).get("handoff_owner_ref"),
                    host_twin.get("handoff_owner_ref"),
                )
                if owner_ref is not None:
                    owner_refs.append(owner_ref)
                handoff_summary["blocking_families"] = [*handoff_summary["blocking_families"], *families]
        host_twin_summary["blocking_families"] = _string_list(blocking_families)
        host_twin_summary["session_ids"] = _string_list(host_twin_summary["session_ids"])
        handoff_summary["session_ids"] = _string_list(handoff_summary["session_ids"])
        handoff_summary["owner_refs"] = _string_list(owner_refs)
        handoff_summary["blocking_families"] = _string_list(handoff_summary["blocking_families"])
        return host_twin_summary, handoff_summary

    def _summarize_staffing_governance(self) -> dict[str, object]:
        summary = {
            "active_gap_count": 0,
            "pending_confirmation_count": 0,
            "instance_ids": [],
            "decision_request_ids": [],
        }
        service = self._industry_service
        if service is None:
            return summary
        list_instances = getattr(service, "list_instances", None)
        detail_getter = getattr(service, "get_instance_detail", None)
        if not callable(list_instances) or not callable(detail_getter):
            return summary
        try:
            instances = list_instances(status=None, limit=200)
        except TypeError:
            instances = list_instances(limit=200)
        except Exception:
            logger.exception("Failed to list industry instances for governance")
            return summary
        decision_ids: list[str] = []
        instance_ids: list[str] = []
        for instance in instances or []:
            instance_payload = _mapping_value(instance)
            instance_id = _first_non_empty(instance_payload.get("instance_id"), instance_payload.get("id"))
            if instance_id is None:
                continue
            try:
                detail = detail_getter(instance_id)
            except Exception:
                logger.exception("Failed to inspect industry instance '%s'", instance_id)
                continue
            staffing = _mapping_value(_mapping_value(detail).get("staffing"))
            active_gap = _mapping_value(staffing.get("active_gap"))
            pending_proposals = _dict_list(staffing.get("pending_proposals"))
            has_pending_confirmation = any(
                _staffing_confirmation_required(item) for item in pending_proposals
            )
            if active_gap:
                summary["active_gap_count"] = int(summary["active_gap_count"]) + 1
                instance_ids.append(instance_id)
                if _staffing_confirmation_required(active_gap) or has_pending_confirmation:
                    summary["pending_confirmation_count"] = int(summary["pending_confirmation_count"]) + 1
                decision_id = _first_non_empty(active_gap.get("decision_request_id"))
                if decision_id is not None:
                    decision_ids.append(decision_id)
            elif has_pending_confirmation:
                summary["pending_confirmation_count"] = int(summary["pending_confirmation_count"]) + 1
            for item in pending_proposals:
                decision_id = _first_non_empty(item.get("decision_request_id"))
                if decision_id is not None:
                    decision_ids.append(decision_id)
        summary["instance_ids"] = _string_list(instance_ids)
        summary["decision_request_ids"] = _string_list(decision_ids)
        return summary

    def _summarize_human_assist_governance(self) -> dict[str, object]:
        summary = {
            "open_count": 0,
            "blocked_count": 0,
            "need_more_evidence_count": 0,
            "task_ids": [],
            "chat_thread_ids": [],
        }
        service = self._human_assist_task_service
        if service is None:
            return summary
        list_tasks = getattr(service, "list_tasks", None)
        if not callable(list_tasks):
            return summary
        try:
            tasks = list_tasks(limit=200)
        except TypeError:
            tasks = list_tasks()
        except Exception:
            logger.exception("Failed to list human assist tasks for governance")
            return summary
        task_ids: list[str] = []
        chat_thread_ids: list[str] = []
        for task_record in tasks or []:
            payload = _mapping_value(task_record)
            status = _first_non_empty(payload.get("status")) or "unknown"
            if status in {"closed", "cancelled", "expired", "resume_queued"}:
                continue
            if self._maybe_close_stale_host_handoff_task(
                task_record=task_record,
                payload_record=payload,
            ):
                continue
            summary["open_count"] = int(summary["open_count"]) + 1
            if status in {"handoff_blocked", "blocked"}:
                summary["blocked_count"] = int(summary["blocked_count"]) + 1
            if status == "need_more_evidence":
                summary["need_more_evidence_count"] = int(summary["need_more_evidence_count"]) + 1
            task_id = _first_non_empty(payload.get("task_id"), payload.get("id"))
            if task_id is not None:
                task_ids.append(task_id)
            chat_thread_id = _first_non_empty(payload.get("chat_thread_id"))
            if chat_thread_id is not None:
                chat_thread_ids.append(chat_thread_id)
        summary["task_ids"] = _string_list(task_ids)
        summary["chat_thread_ids"] = _string_list(chat_thread_ids)
        return summary

    @staticmethod
    def _host_twin_requires_handoff(
        host_twin: dict[str, object],
        host_twin_summary: dict[str, object] | None = None,
    ) -> bool:
        from ..app.runtime_center.task_review_projection import host_twin_summary_ready

        if host_twin_summary_ready(host_twin_summary):
            return False
        continuity = _mapping_value(host_twin.get("continuity"))
        coordination = _mapping_value(host_twin.get("coordination"))
        legal_recovery = _mapping_value(host_twin.get("legal_recovery"))
        ownership = _mapping_value(host_twin.get("ownership"))
        recommended_action = _first_non_empty(
            _mapping_value(host_twin_summary).get("recommended_scheduler_action"),
            coordination.get("recommended_scheduler_action"),
            coordination.get("recommended_action"),
        )
        legal_path = _first_non_empty(
            _mapping_value(host_twin_summary).get("legal_recovery_mode"),
            legal_recovery.get("path"),
            legal_recovery.get("recovery_path"),
        )
        return bool(
            continuity.get("requires_human_return")
            or _mapping_value(host_twin_summary).get("handoff_owner_ref")
            or ownership.get("handoff_owner_ref")
            or recommended_action == "handoff"
            or legal_path == "handoff"
        )

    async def emergency_stop(
        self,
        *,
        actor: str,
        reason: str,
    ) -> GovernanceStatus:
        control = self.get_control()
        if not control.emergency_stop_active:
            control = control.model_copy(
                update={
                    "emergency_stop_active": True,
                    "emergency_reason": reason,
                    "emergency_actor": actor,
                    "metadata": {
                        **dict(control.metadata),
                        "stopped_at": _utc_now().isoformat(),
                    },
                }
            )
        control = await self._apply_emergency_runtime_state(control)
        persisted = self._control_repository.upsert_control(control)
        evidence_id = self._append_evidence(
            actor=actor,
            capability_ref="system:governance_emergency_stop",
            action_summary="运行时紧急停止",
            result_summary="运行时紧急停止已生效。",
            metadata={
                "reason": reason,
                "paused_schedule_ids": list(persisted.paused_schedule_ids),
                "channel_shutdown_applied": persisted.channel_shutdown_applied,
            },
        )
        self._publish_event(
            action="emergency-stop",
            payload={
                "actor": actor,
                "reason": reason,
                "paused_schedule_ids": list(persisted.paused_schedule_ids),
                "channel_shutdown_applied": persisted.channel_shutdown_applied,
                "evidence_id": evidence_id,
            },
        )
        return self.get_status()

    async def resume(
        self,
        *,
        actor: str,
        reason: str | None = None,
    ) -> GovernanceStatus:
        control = self.get_control()
        if control.emergency_stop_active:
            control = await self._restore_runtime_state(control)
        metadata = dict(control.metadata)
        metadata["last_resumed_at"] = _utc_now().isoformat()
        if reason:
            metadata["last_resume_reason"] = reason
        persisted = self._control_repository.upsert_control(
            control.model_copy(
                update={
                    "emergency_stop_active": False,
                    "emergency_reason": None,
                    "emergency_actor": actor,
                    "paused_schedule_ids": [],
                    "channel_shutdown_applied": False,
                    "metadata": metadata,
                }
            )
        )
        evidence_id = self._append_evidence(
            actor=actor,
            capability_ref="system:governance_resume",
            action_summary="运行治理恢复",
            result_summary="运行时操作已恢复。",
            metadata={
                "reason": reason,
                "evidence_control": persisted.model_dump(mode="json"),
            },
        )
        self._publish_event(
            action="resume",
            payload={
                "actor": actor,
                "reason": reason,
                "evidence_id": evidence_id,
            },
        )
        return self.get_status()

    async def reconcile_runtime_state(self) -> GovernanceStatus:
        control = self.get_control()
        if control.emergency_stop_active:
            control = await self._apply_emergency_runtime_state(control)
            self._control_repository.upsert_control(control)
        return self.get_status()

    async def batch_decisions(
        self,
        *,
        decision_ids: list[str],
        action: str,
        actor: str,
        resolution: str | None = None,
        execute: bool | None = None,
    ) -> GovernanceBatchResult:
        dispatcher = self._kernel_dispatcher
        if dispatcher is None:
            raise RuntimeError("Kernel dispatcher is not available")
        normalized_ids = [item.strip() for item in decision_ids if item and item.strip()]
        results: list[dict[str, object]] = []
        errors: list[dict[str, object]] = []
        for decision_id in normalized_ids:
            try:
                if action == "approve":
                    result = await dispatcher.approve_decision(
                        decision_id,
                        resolution=resolution or f"已由 {actor} 批准。",
                        execute=execute,
                    )
                elif action == "reject":
                    result = dispatcher.reject_decision(
                        decision_id,
                        resolution=resolution or f"已由 {actor} 驳回。",
                    )
                else:
                    raise ValueError(f"Unsupported decision batch action: {action}")
                results.append(result.model_dump(mode="json"))
            except Exception as exc:
                errors.append({"decision_id": decision_id, "error": str(exc)})
        evidence_id = self._append_evidence(
            actor=actor,
            capability_ref=f"system:batch_decision_{action}",
            action_summary=f"批量{_batch_action_label(action)}决策",
            result_summary=(
                f"共处理 {len(normalized_ids)} 条决策："
                f"{len(results)} 条成功，{len(errors)} 条失败。"
            ),
            metadata={
                "decision_ids": normalized_ids,
                "results": results,
                "errors": errors,
                "resolution": resolution,
                "execute": execute,
            },
        )
        self._publish_event(
            action=f"batch-decision-{action}",
            payload={
                "actor": actor,
                "requested": len(normalized_ids),
                "succeeded": len(results),
                "failed": len(errors),
                "evidence_id": evidence_id,
            },
        )
        return GovernanceBatchResult(
            action=f"decision:{action}",
            requested=len(normalized_ids),
            succeeded=len(results),
            failed=len(errors),
            actor=actor,
            results=results,
            errors=errors,
            evidence_id=evidence_id,
        )

    def batch_patches(
        self,
        *,
        patch_ids: list[str],
        action: str,
        actor: str,
    ) -> GovernanceBatchResult:
        service = self._learning_service
        if service is None:
            raise RuntimeError("Learning service is not available")
        normalized_ids = [item.strip() for item in patch_ids if item and item.strip()]
        results: list[dict[str, object]] = []
        errors: list[dict[str, object]] = []
        for patch_id in normalized_ids:
            try:
                if action == "approve":
                    patch = service.approve_patch(patch_id, approved_by=actor)
                elif action == "reject":
                    patch = service.reject_patch(patch_id, rejected_by=actor)
                elif action == "apply":
                    patch = service.apply_patch(patch_id, applied_by=actor)
                elif action == "rollback":
                    patch = service.rollback_patch(patch_id, rolled_back_by=actor)
                else:
                    raise ValueError(f"Unsupported patch batch action: {action}")
                results.append(patch.model_dump(mode="json"))
            except Exception as exc:
                errors.append({"patch_id": patch_id, "error": str(exc)})
        evidence_id = self._append_evidence(
            actor=actor,
            capability_ref=f"system:batch_patch_{action}",
            action_summary=f"批量{_batch_action_label(action)}补丁",
            result_summary=(
                f"共处理 {len(normalized_ids)} 个补丁："
                f"{len(results)} 个成功，{len(errors)} 个失败。"
            ),
            metadata={
                "patch_ids": normalized_ids,
                "results": results,
                "errors": errors,
            },
        )
        self._publish_event(
            action=f"batch-patch-{action}",
            payload={
                "actor": actor,
                "requested": len(normalized_ids),
                "succeeded": len(results),
                "failed": len(errors),
                "evidence_id": evidence_id,
            },
        )
        return GovernanceBatchResult(
            action=f"patch:{action}",
            requested=len(normalized_ids),
            succeeded=len(results),
            failed=len(errors),
            actor=actor,
            results=results,
            errors=errors,
            evidence_id=evidence_id,
        )

    async def _apply_emergency_runtime_state(
        self,
        control: GovernanceControlRecord,
    ) -> GovernanceControlRecord:
        paused_schedule_ids = list(control.paused_schedule_ids)
        if self._cron_manager is not None:
            try:
                jobs = await self._maybe_await(self._cron_manager.list_jobs())
            except Exception:
                logger.exception("Failed to list cron jobs during emergency stop")
                jobs = []
            seen = set(paused_schedule_ids)
            for job in jobs or []:
                job_id = str(getattr(job, "id", "") or "")
                enabled = bool(getattr(job, "enabled", False))
                if not job_id or not enabled:
                    continue
                try:
                    await self._maybe_await(self._cron_manager.pause_job(job_id))
                except Exception:
                    logger.exception("Failed to pause schedule %s during emergency stop", job_id)
                    continue
                if job_id not in seen:
                    paused_schedule_ids.append(job_id)
                    seen.add(job_id)
        channel_shutdown_applied = control.channel_shutdown_applied
        if self._channel_manager is not None and not channel_shutdown_applied:
            try:
                await self._maybe_await(self._channel_manager.stop_all())
                channel_shutdown_applied = True
            except Exception:
                logger.exception("Failed to stop channels during emergency stop")
        return control.model_copy(
            update={
                "paused_schedule_ids": paused_schedule_ids,
                "channel_shutdown_applied": channel_shutdown_applied,
            }
        )

    async def _restore_runtime_state(
        self,
        control: GovernanceControlRecord,
    ) -> GovernanceControlRecord:
        if self._channel_manager is not None and control.channel_shutdown_applied:
            try:
                await self._maybe_await(self._channel_manager.start_all())
            except Exception:
                logger.exception("Failed to restart channels during governance resume")
        if self._cron_manager is not None:
            for schedule_id in control.paused_schedule_ids:
                try:
                    await self._maybe_await(self._cron_manager.resume_job(schedule_id))
                except Exception:
                    logger.exception(
                        "Failed to resume schedule %s during governance resume",
                        schedule_id,
                    )
        return control

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _should_block_capability(capability_ref: str) -> bool:
        if not capability_ref:
            return False
        if capability_ref.startswith(("tool:", "skill:", "mcp:")):
            return True
        return capability_ref in _BLOCKED_SYSTEM_CAPABILITIES

    def _append_evidence(
        self,
        *,
        actor: str,
        capability_ref: str,
        action_summary: str,
        result_summary: str,
        metadata: dict[str, object] | None = None,
    ) -> str | None:
        if self._evidence_ledger is None:
            return None
        record = self._evidence_ledger.append(
            EvidenceRecord(
                task_id=_GOVERNANCE_TASK_ID,
                actor_ref=actor,
                environment_ref="config:runtime",
                capability_ref=capability_ref,
                risk_level="guarded",
                action_summary=action_summary,
                result_summary=result_summary,
                metadata=metadata or {},
            )
        )
        return record.id

    def _publish_event(self, *, action: str, payload: dict[str, object]) -> None:
        if self._runtime_event_bus is None:
            return
        try:
            self._runtime_event_bus.publish(topic="governance", action=action, payload=payload)
        except Exception:
            logger.exception("Failed to publish governance event")


__all__ = [
    "GovernanceBatchResult",
    "GovernanceService",
    "GovernanceStatus",
]
