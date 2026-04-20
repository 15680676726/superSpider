# -*- coding: utf-8 -*-
"""Canonical execution-runtime projection helpers for Runtime Center read surfaces."""
from __future__ import annotations

from typing import Any

from .models import RuntimeKnowledgeWritebackSummary
from .projection_utils import (
    dict_from_value,
    dict_list_from_value,
    first_non_empty,
    string_list_from_values,
)

_EXECUTION_RUNTIME_SECTION_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("workspace", ("workspace", "workspace_graph")),
    (
        "cooperative_adapter_availability",
        ("cooperative_adapter_availability",),
    ),
    ("host", ("host", "host_contract")),
    ("recovery", ("recovery",)),
    ("host_event_summary", ("host_event_summary",)),
    ("seat_runtime", ("seat_runtime",)),
    ("browser_site_contract", ("browser_site_contract",)),
    ("desktop_app_contract", ("desktop_app_contract",)),
    ("host_companion_session", ("host_companion_session",)),
    ("host_twin", ("host_twin",)),
    ("host_twin_summary", ("host_twin_summary",)),
)


def resolve_canonical_host_identity(
    host_payload: dict[str, object] | None,
    *,
    metadata: dict[str, object] | None = None,
    fallback_environment_ref: str | None = None,
    fallback_environment_id: str | None = None,
    fallback_session_mount_id: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    host_payload = dict(host_payload or {})
    metadata = dict(metadata or {})
    scheduler_inputs = dict_from_value(host_payload.get("scheduler_inputs")) or {}
    host_twin_summary = dict_from_value(host_payload.get("host_twin_summary")) or {}
    coordination = dict_from_value(host_payload.get("coordination")) or {}

    canonical_environment_ref = first_non_empty(
        scheduler_inputs.get("environment_ref"),
        scheduler_inputs.get("environment_id"),
        host_twin_summary.get("selected_seat_ref"),
        coordination.get("selected_seat_ref"),
        host_payload.get("environment_ref"),
        host_payload.get("environment_id"),
        metadata.get("environment_ref"),
        metadata.get("environment_id"),
        fallback_environment_ref,
        fallback_environment_id,
    )
    canonical_environment_id = first_non_empty(
        scheduler_inputs.get("environment_id"),
        scheduler_inputs.get("environment_ref"),
        host_twin_summary.get("selected_seat_ref"),
        coordination.get("selected_seat_ref"),
        host_payload.get("environment_id"),
        host_payload.get("environment_ref"),
        metadata.get("environment_id"),
        metadata.get("environment_ref"),
        fallback_environment_id,
        fallback_environment_ref,
        canonical_environment_ref,
    )
    canonical_session_mount_id = first_non_empty(
        scheduler_inputs.get("session_mount_id"),
        host_twin_summary.get("selected_session_mount_id"),
        coordination.get("selected_session_mount_id"),
        host_payload.get("session_mount_id"),
        metadata.get("session_mount_id"),
        fallback_session_mount_id,
    )
    return (
        canonical_environment_ref,
        canonical_environment_id,
        canonical_session_mount_id,
    )


def extract_execution_runtime_sections(
    feedback: dict[str, object] | None,
) -> dict[str, dict[str, object] | None]:
    feedback = dict(feedback or {})
    prebuilt = dict_from_value(feedback.get("execution_runtime")) or {}
    sections: dict[str, dict[str, object] | None] = {}
    for canonical_key, aliases in _EXECUTION_RUNTIME_SECTION_ALIASES:
        section = dict_from_value(prebuilt.get(canonical_key))
        if section is None:
            for alias in aliases:
                section = dict_from_value(feedback.get(alias))
                if section is not None:
                    break
        sections[canonical_key] = section
    return sections


def attach_execution_runtime_projection(
    feedback: dict[str, object] | None,
) -> dict[str, object]:
    normalized = dict(feedback or {})
    normalized["execution_runtime"] = extract_execution_runtime_sections(normalized)
    return normalized


def summarize_execution_knowledge_writeback(
    payload: dict[str, object] | None,
) -> dict[str, object] | None:
    resolved = dict_from_value(payload)
    if resolved is None:
        return None
    summary = RuntimeKnowledgeWritebackSummary(
        source=first_non_empty(resolved.get("source")) or "execution-outcome",
        outcome=first_non_empty(resolved.get("outcome")) or "unknown",
        summary=first_non_empty(resolved.get("summary")) or "",
        capability_ref=first_non_empty(resolved.get("capability_ref")),
        environment_ref=first_non_empty(resolved.get("environment_ref")),
        risk_level=first_non_empty(resolved.get("risk_level")),
        failure_source=first_non_empty(resolved.get("failure_source")),
        blocked_next_step=first_non_empty(resolved.get("blocked_next_step")),
        recovery_summary=first_non_empty(resolved.get("recovery_summary")),
        node_types=string_list_from_values(resolved.get("node_types")),
        relation_types=string_list_from_values(resolved.get("relation_types")),
        evidence_refs=string_list_from_values(resolved.get("evidence_refs")),
    )
    if (
        not summary.summary
        and not summary.node_types
        and not summary.relation_types
        and not summary.failure_source
        and not summary.recovery_summary
    ):
        return None
    return summary.model_dump(mode="json")


def host_twin_seat_owner_ref(host_twin: dict[str, object] | None) -> str | None:
    if host_twin is None:
        return None
    seat_owner = dict_from_value(host_twin.get("seat_owner"))
    ownership = dict_from_value(host_twin.get("ownership"))
    coordination = dict_from_value(host_twin.get("coordination"))
    return first_non_empty(
        host_twin.get("seat_owner_ref"),
        ownership.get("handoff_owner_ref") if ownership is not None else None,
        ownership.get("seat_owner_ref") if ownership is not None else None,
        ownership.get("owner_ref") if ownership is not None else None,
        seat_owner.get("owner_ref") if seat_owner is not None else None,
        seat_owner.get("seat_owner_ref") if seat_owner is not None else None,
        seat_owner.get("actor_ref") if seat_owner is not None else None,
        coordination.get("handoff_owner_ref") if coordination is not None else None,
        coordination.get("seat_owner_ref") if coordination is not None else None,
    )


def host_twin_writable_surface_label(host_twin: dict[str, object] | None) -> str | None:
    if host_twin is None:
        return None
    surfaces = dict_list_from_value(host_twin.get("writable_surfaces"))
    first_surface = surfaces[0] if surfaces else None
    blocked_surfaces = dict_list_from_value(host_twin.get("blocked_surfaces"))
    first_blocked_surface = blocked_surfaces[0] if blocked_surfaces else None
    trusted_anchors = dict_list_from_value(host_twin.get("trusted_anchors"))
    first_anchor = trusted_anchors[0] if trusted_anchors else None
    app_family_twins = dict_from_value(host_twin.get("app_family_twins")) or {}
    active_family = next(
        (
            value
            for value in app_family_twins.values()
            if isinstance(value, dict) and value.get("active") is True
        ),
        None,
    )
    return first_non_empty(
        host_twin.get("writable_surface_summary"),
        first_surface.get("label") if first_surface is not None else None,
        first_surface.get("summary") if first_surface is not None else None,
        first_surface.get("surface_ref") if first_surface is not None else None,
        first_anchor.get("label") if first_anchor is not None else None,
        active_family.get("label") if active_family is not None else None,
        active_family.get("writer_lock_scope") if active_family is not None else None,
        active_family.get("family_scope_ref") if active_family is not None else None,
        active_family.get("surface_ref") if active_family is not None else None,
        first_blocked_surface.get("label") if first_blocked_surface is not None else None,
        first_blocked_surface.get("surface_ref") if first_blocked_surface is not None else None,
        first_anchor.get("anchor_ref") if first_anchor is not None else None,
    )


def host_twin_legal_recovery_mode(host_twin: dict[str, object] | None) -> str | None:
    if host_twin is None:
        return None
    embedded_summary = dict_from_value(host_twin.get("host_twin_summary"))
    recovery_path = dict_from_value(host_twin.get("legal_recovery_path"))
    legal_recovery = dict_from_value(host_twin.get("legal_recovery"))
    return first_non_empty(
        embedded_summary.get("legal_recovery_mode") if embedded_summary is not None else None,
        host_twin.get("legal_recovery_mode"),
        legal_recovery.get("mode") if legal_recovery is not None else None,
        legal_recovery.get("path") if legal_recovery is not None else None,
        legal_recovery.get("resume_kind") if legal_recovery is not None else None,
        recovery_path.get("mode") if recovery_path is not None else None,
        recovery_path.get("path") if recovery_path is not None else None,
        recovery_path.get("resume_kind") if recovery_path is not None else None,
    )


def host_twin_resume_kind(host_twin: dict[str, object] | None) -> str | None:
    if host_twin is None:
        return None
    recovery_path = dict_from_value(host_twin.get("legal_recovery_path"))
    legal_recovery = dict_from_value(host_twin.get("legal_recovery"))
    return first_non_empty(
        host_twin.get("resume_kind"),
        legal_recovery.get("resume_kind") if legal_recovery is not None else None,
        recovery_path.get("resume_kind") if recovery_path is not None else None,
    )


def host_twin_summary_ready(host_twin_summary: dict[str, object] | None) -> bool:
    if host_twin_summary is None:
        return False
    continuity_state = first_non_empty(host_twin_summary.get("continuity_state"))
    if continuity_state is not None:
        return continuity_state == "ready"
    recommended_action = first_non_empty(
        host_twin_summary.get("recommended_scheduler_action"),
    )
    legal_recovery_mode = first_non_empty(host_twin_summary.get("legal_recovery_mode"))
    host_companion_status = first_non_empty(host_twin_summary.get("host_companion_status"))
    try:
        blocked_surface_count = int(host_twin_summary.get("blocked_surface_count") or 0)
    except (TypeError, ValueError):
        blocked_surface_count = 0
    host_companion_ready = (
        host_companion_status in {"attached", "restorable", "same-host-other-process"}
        if host_companion_status is not None
        else True
    )
    return bool(
        recommended_action
        and recommended_action not in {"recover", "handoff", "retry"}
        and legal_recovery_mode != "handoff"
        and blocked_surface_count == 0
        and host_companion_ready
    )


def derive_host_twin_continuity_state(host_twin_summary: dict[str, object] | None) -> str:
    if host_twin_summary is None:
        return "blocked"
    recommended_action = first_non_empty(
        host_twin_summary.get("recommended_scheduler_action"),
    )
    legal_recovery_mode = first_non_empty(host_twin_summary.get("legal_recovery_mode"))
    host_companion_status = first_non_empty(host_twin_summary.get("host_companion_status"))
    contention_severity = first_non_empty(host_twin_summary.get("contention_severity"))
    try:
        blocked_surface_count = int(host_twin_summary.get("blocked_surface_count") or 0)
    except (TypeError, ValueError):
        blocked_surface_count = 0
    host_companion_ready = (
        host_companion_status in {"attached", "restorable", "same-host-other-process"}
        if host_companion_status is not None
        else True
    )
    if recommended_action in {"continue", "proceed", "ready", "clear"}:
        if host_companion_ready and legal_recovery_mode != "handoff" and blocked_surface_count == 0:
            return "ready"
    if (
        not host_companion_ready
        or legal_recovery_mode == "handoff"
        or blocked_surface_count > 0
        or recommended_action in {"recover", "handoff", "retry"}
    ):
        return "blocked"
    if (
        recommended_action is not None
        or contention_severity in {"guarded", "warn", "warning", "blocked"}
        or legal_recovery_mode is not None
    ):
        return "guarded"
    return "blocked"


def host_twin_legal_recovery_summary(host_twin: dict[str, object] | None) -> str | None:
    if host_twin is None:
        return None
    recovery_path = dict_from_value(host_twin.get("legal_recovery_path"))
    legal_recovery = dict_from_value(host_twin.get("legal_recovery"))
    return first_non_empty(
        host_twin.get("legal_recovery_summary"),
        legal_recovery.get("summary") if legal_recovery is not None else None,
        legal_recovery.get("label") if legal_recovery is not None else None,
        legal_recovery.get("resume_kind") if legal_recovery is not None else None,
        legal_recovery.get("mode") if legal_recovery is not None else None,
        legal_recovery.get("checkpoint_ref") if legal_recovery is not None else None,
        legal_recovery.get("path") if legal_recovery is not None else None,
        recovery_path.get("summary") if recovery_path is not None else None,
        recovery_path.get("label") if recovery_path is not None else None,
        recovery_path.get("resume_kind") if recovery_path is not None else None,
        recovery_path.get("mode") if recovery_path is not None else None,
        recovery_path.get("checkpoint_ref") if recovery_path is not None else None,
    )


def host_twin_trusted_anchor(host_twin: dict[str, object] | None) -> str | None:
    if host_twin is None:
        return None
    anchors = dict_list_from_value(host_twin.get("trusted_anchors"))
    first_anchor = anchors[0] if anchors else None
    return first_non_empty(
        host_twin.get("trusted_anchor"),
        host_twin.get("trusted_anchor_ref"),
        first_anchor.get("anchor_ref") if first_anchor is not None else None,
        first_anchor.get("anchor") if first_anchor is not None else None,
        first_anchor.get("label") if first_anchor is not None else None,
    )


def host_twin_active_blocker_family(host_twin: dict[str, object] | None) -> str | None:
    if host_twin is None:
        return None
    blocker_families = string_list_from_values(
        host_twin.get("active_blocker_families"),
        host_twin.get("active_blocker_family"),
    )
    if blocker_families:
        return blocker_families[0]
    blocked_surfaces = dict_list_from_value(host_twin.get("blocked_surfaces"))
    if blocked_surfaces:
        first_blocked_surface = blocked_surfaces[0]
        blocker = first_non_empty(
            first_blocked_surface.get("event_family"),
            first_blocked_surface.get("reason"),
        )
        if blocker:
            return blocker
    surface_mutability = dict_from_value(host_twin.get("surface_mutability")) or {}
    for value in surface_mutability.values():
        if not isinstance(value, dict):
            continue
        blocker = first_non_empty(value.get("blocker_family"), value.get("mutability"))
        if blocker:
            return blocker
    return first_non_empty(host_twin.get("blocker_family"), host_twin.get("blocker_summary"))


def serialize_executor_runtime_record(
    record: Any,
    *,
    route_prefix: str = "/api/runtime-center/external-runtimes",
) -> dict[str, object]:
    model_dump = getattr(record, "model_dump", None)
    payload = model_dump(mode="json") if callable(model_dump) else None
    if not isinstance(payload, dict):
        payload = {}
    runtime_id = first_non_empty(payload.get("runtime_id"))
    executor_id = first_non_empty(payload.get("executor_id"))
    protocol_kind = first_non_empty(payload.get("protocol_kind"))
    scope_kind = first_non_empty(payload.get("scope_kind"))
    status = first_non_empty(payload.get("runtime_status"), payload.get("status")) or "unknown"
    payload["status"] = status
    payload["runtime_status"] = status
    payload["kind"] = "executor-runtime"
    payload["title"] = executor_id or runtime_id or "executor-runtime"
    payload["summary"] = " / ".join(
        part for part in (protocol_kind, scope_kind, status) if part
    ) or "executor runtime"
    if runtime_id:
        payload["route"] = f"{route_prefix}/{runtime_id}"
    return payload


def build_host_twin_summary(
    host_twin: dict[str, object] | None,
    *,
    host_companion_session: dict[str, object] | None = None,
) -> dict[str, object] | None:
    if host_twin is None:
        return None
    embedded_summary = dict_from_value(host_twin.get("host_twin_summary")) or {}
    ownership = dict_from_value(host_twin.get("ownership")) or {}
    coordination = dict_from_value(host_twin.get("coordination")) or {}
    app_family_twins = dict_from_value(host_twin.get("app_family_twins")) or {}
    host_companion_session = (
        dict_from_value(host_companion_session)
        or dict_from_value(host_twin.get("host_companion_session"))
        or {}
    )
    continuity = dict_from_value(host_twin.get("continuity")) or {}
    legal_recovery = dict_from_value(host_twin.get("legal_recovery")) or {}
    multi_seat_coordination = dict_from_value(host_twin.get("multi_seat_coordination")) or {}
    app_family_readiness = dict_from_value(host_twin.get("app_family_readiness")) or {}
    blocked_surfaces = dict_list_from_value(host_twin.get("blocked_surfaces"))
    active_app_family_keys = string_list_from_values(embedded_summary.get("active_app_family_keys"))
    if not active_app_family_keys:
        active_app_family_keys = sorted(
            family_key
            for family_key, value in app_family_twins.items()
            if isinstance(value, dict) and value.get("active") is True
        )
    ready_app_family_keys = string_list_from_values(app_family_readiness.get("ready_family_keys"))
    if not ready_app_family_keys:
        ready_app_family_keys = sorted(
            family_key
            for family_key, value in app_family_twins.items()
            if isinstance(value, dict)
            and value.get("active") is True
            and first_non_empty(value.get("contract_status")) not in {"blocked", "inactive"}
        )
    blocked_app_family_keys = string_list_from_values(
        app_family_readiness.get("blocked_family_keys"),
    )
    if not blocked_app_family_keys:
        blocked_app_family_keys = sorted(
            family_key
            for family_key, value in app_family_twins.items()
            if isinstance(value, dict)
            and (
                value.get("active") is not True
                or first_non_empty(value.get("contract_status")) in {"blocked", "inactive"}
            )
        )
    candidate_seat_refs = string_list_from_values(
        multi_seat_coordination.get("candidate_seat_refs"),
        coordination.get("candidate_seat_refs"),
    )
    selected_seat_ref = first_non_empty(
        multi_seat_coordination.get("selected_seat_ref"),
        coordination.get("selected_seat_ref"),
    )
    selected_session_mount_id = first_non_empty(
        embedded_summary.get("selected_session_mount_id"),
        multi_seat_coordination.get("selected_session_mount_id"),
        coordination.get("selected_session_mount_id"),
        host_twin.get("session_mount_id"),
    )
    seat_selection_policy = first_non_empty(
        multi_seat_coordination.get("seat_selection_policy"),
        coordination.get("seat_selection_policy"),
    )
    seat_count_value = embedded_summary.get("seat_count")
    if not isinstance(seat_count_value, int):
        seat_count_value = multi_seat_coordination.get("seat_count")
    if not isinstance(seat_count_value, int):
        seat_count_value = len(candidate_seat_refs) or (1 if selected_seat_ref else 0)
    host_companion_status = first_non_empty(
        multi_seat_coordination.get("host_companion_status"),
        host_companion_session.get("continuity_status"),
    )
    continuity_status = first_non_empty(continuity.get("status"))
    legal_recovery_path = first_non_empty(
        legal_recovery.get("path"),
        legal_recovery.get("resume_kind"),
    )
    requires_human_return = bool(continuity.get("requires_human_return"))
    if continuity_status is not None and host_companion_status == "restorable" and (
        requires_human_return or legal_recovery_path == "handoff"
    ):
        host_companion_status = continuity_status
    host_companion_source = first_non_empty(host_companion_session.get("continuity_source"))
    host_companion_session_mount_id = first_non_empty(
        host_companion_session.get("session_mount_id"),
    )
    host_companion_environment_id = first_non_empty(
        host_companion_session.get("environment_id"),
    )
    host_companion_locality = dict_from_value(host_companion_session.get("locality")) or {}
    multi_seat_status = first_non_empty(multi_seat_coordination.get("status"))
    app_family_statuses = {
        family_key: {
            "active": bool(value.get("active")),
            "ready": family_key in set(ready_app_family_keys),
            "contract_status": first_non_empty(value.get("contract_status")),
            "surface_ref": first_non_empty(value.get("surface_ref")),
            "family_scope_ref": first_non_empty(value.get("family_scope_ref")),
            "writer_lock_scope": first_non_empty(value.get("writer_lock_scope")),
        }
        for family_key, value in app_family_twins.items()
        if isinstance(value, dict)
    }
    seat_owner = dict_from_value(host_twin.get("seat_owner"))
    contention_forecast = dict_from_value(coordination.get("contention_forecast"))
    summary = {
        "seat_owner_ref": first_non_empty(
            embedded_summary.get("seat_owner_ref"),
            coordination.get("seat_owner_ref"),
            ownership.get("seat_owner_ref"),
            ownership.get("seat_owner_agent_id"),
            host_twin.get("seat_owner_ref"),
            seat_owner.get("owner_ref") if seat_owner is not None else None,
            seat_owner.get("seat_owner_ref") if seat_owner is not None else None,
            seat_owner.get("actor_ref") if seat_owner is not None else None,
            ownership.get("handoff_owner_ref"),
            coordination.get("handoff_owner_ref"),
        ),
        "handoff_owner_ref": first_non_empty(
            ownership.get("handoff_owner_ref"),
            coordination.get("handoff_owner_ref"),
            seat_owner.get("actor_ref") if seat_owner is not None else None,
        ),
        "workspace_owner_ref": first_non_empty(
            coordination.get("workspace_owner_ref"),
            ownership.get("workspace_owner_ref"),
        ),
        "writer_owner_ref": first_non_empty(
            coordination.get("writer_owner_ref"),
            ownership.get("writer_owner_ref"),
            ownership.get("seat_owner_ref"),
        ),
        "selected_seat_ref": selected_seat_ref,
        "selected_session_mount_id": selected_session_mount_id,
        "seat_selection_policy": seat_selection_policy,
        "recommended_scheduler_action": first_non_empty(
            embedded_summary.get("recommended_scheduler_action"),
            coordination.get("recommended_scheduler_action"),
            multi_seat_coordination.get("recommended_scheduler_action"),
        ),
        "contention_severity": first_non_empty(
            contention_forecast.get("severity") if contention_forecast is not None else None,
            multi_seat_coordination.get("severity"),
        ),
        "contention_reason": first_non_empty(
            contention_forecast.get("reason") if contention_forecast is not None else None,
            multi_seat_coordination.get("reason"),
            host_twin_active_blocker_family(host_twin),
        ),
        "host_companion_status": host_companion_status,
        "host_companion_source": host_companion_source,
        "host_companion_session_mount_id": host_companion_session_mount_id,
        "host_companion_environment_id": host_companion_environment_id,
        "host_companion_locality": host_companion_locality,
        "seat_count": seat_count_value,
        "candidate_seat_refs": candidate_seat_refs,
        "multi_seat_coordination": {
            "seat_count": seat_count_value,
            "candidate_seat_refs": candidate_seat_refs,
            "selected_seat_ref": selected_seat_ref,
            "selected_session_mount_id": selected_session_mount_id,
            "seat_selection_policy": seat_selection_policy,
            "occupancy_state": first_non_empty(multi_seat_coordination.get("occupancy_state")),
            "status": multi_seat_status,
            "host_companion_status": host_companion_status,
            "active_surface_mix": string_list_from_values(
                multi_seat_coordination.get("active_surface_mix"),
            ),
        },
        "ready_app_family_keys": ready_app_family_keys,
        "ready_app_family_count": len(ready_app_family_keys),
        "blocked_app_family_keys": blocked_app_family_keys,
        "blocked_app_family_count": len(blocked_app_family_keys),
        "app_family_readiness": {
            "active_family_keys": active_app_family_keys,
            "active_family_count": len(active_app_family_keys),
            "ready_family_keys": ready_app_family_keys,
            "ready_family_count": len(ready_app_family_keys),
            "blocked_family_keys": blocked_app_family_keys,
            "blocked_family_count": len(blocked_app_family_keys),
            "family_statuses": app_family_statuses,
        },
        "active_app_family_keys": active_app_family_keys[:4],
        "active_app_family_count": len(active_app_family_keys),
        "blocked_surface_refs": string_list_from_values(
            embedded_summary.get("blocked_surface_refs"),
            [
                first_non_empty(surface.get("surface_ref"), surface.get("surface_kind"))
                for surface in blocked_surfaces[:4]
            ],
        )[:4],
        "blocked_surface_count": (
            embedded_summary.get("blocked_surface_count")
            if isinstance(embedded_summary.get("blocked_surface_count"), int)
            else len(blocked_surfaces)
        ),
        "active_blocker_families": string_list_from_values(
            host_twin.get("active_blocker_families"),
            host_twin.get("active_blocker_family"),
        )[:4],
        "legal_recovery_mode": host_twin_legal_recovery_mode(host_twin),
        "legal_recovery_summary": host_twin_legal_recovery_summary(host_twin),
        "writable_surface_label": host_twin_writable_surface_label(host_twin),
        "trusted_anchor_ref": host_twin_trusted_anchor(host_twin),
    }
    summary["continuity_state"] = first_non_empty(
        embedded_summary.get("continuity_state"),
        host_twin.get("continuity_state"),
        derive_host_twin_continuity_state(summary),
    )
    return summary


__all__ = [
    "attach_execution_runtime_projection",
    "build_host_twin_summary",
    "derive_host_twin_continuity_state",
    "extract_execution_runtime_sections",
    "host_twin_active_blocker_family",
    "host_twin_legal_recovery_mode",
    "host_twin_legal_recovery_summary",
    "host_twin_resume_kind",
    "host_twin_seat_owner_ref",
    "host_twin_summary_ready",
    "host_twin_trusted_anchor",
    "host_twin_writable_surface_label",
    "resolve_canonical_host_identity",
    "serialize_executor_runtime_record",
    "summarize_execution_knowledge_writeback",
]
