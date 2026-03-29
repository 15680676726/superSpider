# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...evidence import EvidenceRecord
from ...kernel.persistence import decode_kernel_task_metadata
from ...utils.runtime_routes import task_route


def first_non_empty(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
            continue
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return None


def string_list_from_values(*values: object) -> list[str]:
    items: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                items.append(normalized)
            continue
        if isinstance(value, (list, tuple, set)):
            items.extend(string_list_from_values(*list(value)))
            continue
        normalized = str(value).strip()
        if normalized:
            items.append(normalized)
    return items


def dict_from_value(value: object) -> dict[str, object] | None:
    if isinstance(value, dict):
        return dict(value)
    return None


def runtime_metadata_from_runtime(runtime: Any | None) -> dict[str, object]:
    if runtime is None:
        return {}
    if isinstance(runtime, dict):
        metadata = runtime.get("metadata")
        runtime_metadata = runtime.get("runtime_metadata")
    else:
        metadata = getattr(runtime, "metadata", None)
        runtime_metadata = getattr(runtime, "runtime_metadata", None)
    if isinstance(metadata, dict):
        return dict(metadata)
    if isinstance(runtime_metadata, dict):
        return dict(runtime_metadata)
    return {}


def projection_section(
    *,
    feedback: dict[str, object],
    runtime_metadata: dict[str, object],
    key: str,
) -> dict[str, object] | None:
    direct = dict_from_value(feedback.get(key))
    if direct is not None:
        return direct
    return dict_from_value(runtime_metadata.get(key))


def dict_list_from_value(value: object) -> list[dict[str, object]]:
    if isinstance(value, dict):
        return [dict(value)]
    if isinstance(value, (list, tuple, set)):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


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
        embedded_summary.get("legal_recovery_mode")
        if embedded_summary is not None
        else None,
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


def host_twin_summary_ready(
    host_twin_summary: dict[str, object] | None,
) -> bool:
    if host_twin_summary is None:
        return False
    recommended_action = first_non_empty(
        host_twin_summary.get("recommended_scheduler_action"),
    )
    legal_recovery_mode = first_non_empty(
        host_twin_summary.get("legal_recovery_mode"),
    )
    try:
        blocked_surface_count = int(host_twin_summary.get("blocked_surface_count") or 0)
    except (TypeError, ValueError):
        blocked_surface_count = 0
    return bool(
        recommended_action
        and recommended_action not in {"recover", "handoff", "retry"}
        and legal_recovery_mode != "handoff"
        and blocked_surface_count == 0
    )


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
        blocker = first_non_empty(
            value.get("blocker_family"),
            value.get("mutability"),
        )
        if blocker:
            return blocker
    return first_non_empty(
        host_twin.get("blocker_family"),
        host_twin.get("blocker_summary"),
    )


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
    multi_seat_coordination = (
        dict_from_value(host_twin.get("multi_seat_coordination")) or {}
    )
    app_family_readiness = dict_from_value(host_twin.get("app_family_readiness")) or {}
    blocked_surfaces = dict_list_from_value(host_twin.get("blocked_surfaces"))
    active_app_family_keys = string_list_from_values(
        embedded_summary.get("active_app_family_keys"),
    )
    if not active_app_family_keys:
        active_app_family_keys = sorted(
            family_key
            for family_key, value in app_family_twins.items()
            if isinstance(value, dict) and value.get("active") is True
        )
    ready_app_family_keys = string_list_from_values(
        app_family_readiness.get("ready_family_keys"),
    )
    if not ready_app_family_keys:
        ready_app_family_keys = sorted(
            family_key
            for family_key, value in app_family_twins.items()
            if isinstance(value, dict)
            and value.get("active") is True
            and first_non_empty(value.get("contract_status")) not in {
                "blocked",
                "inactive",
            }
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
                or first_non_empty(value.get("contract_status")) in {
                    "blocked",
                    "inactive",
                }
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
    requires_human_return = bool(
        continuity.get("requires_human_return"),
    )
    if (
        continuity_status is not None
        and host_companion_status == "restorable"
        and (
            requires_human_return
            or legal_recovery_path == "handoff"
        )
    ):
        host_companion_status = continuity_status
    host_companion_source = first_non_empty(
        host_companion_session.get("continuity_source"),
    )
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
    return {
        "seat_owner_ref": first_non_empty(
            embedded_summary.get("seat_owner_ref"),
            coordination.get("seat_owner_ref"),
            ownership.get("seat_owner_ref"),
            ownership.get("seat_owner_agent_id"),
            host_twin.get("seat_owner_ref"),
            dict_from_value(host_twin.get("seat_owner")).get("owner_ref")
            if dict_from_value(host_twin.get("seat_owner")) is not None
            else None,
            dict_from_value(host_twin.get("seat_owner")).get("seat_owner_ref")
            if dict_from_value(host_twin.get("seat_owner")) is not None
            else None,
            dict_from_value(host_twin.get("seat_owner")).get("actor_ref")
            if dict_from_value(host_twin.get("seat_owner")) is not None
            else None,
            ownership.get("handoff_owner_ref"),
            coordination.get("handoff_owner_ref"),
        ),
        "handoff_owner_ref": first_non_empty(
            ownership.get("handoff_owner_ref"),
            coordination.get("handoff_owner_ref"),
            dict_from_value(host_twin.get("seat_owner")).get("actor_ref")
            if dict_from_value(host_twin.get("seat_owner")) is not None
            else None,
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
        "seat_selection_policy": seat_selection_policy,
        "recommended_scheduler_action": first_non_empty(
            embedded_summary.get("recommended_scheduler_action"),
            coordination.get("recommended_scheduler_action"),
            multi_seat_coordination.get("recommended_scheduler_action"),
        ),
        "contention_severity": first_non_empty(
            dict_from_value(coordination.get("contention_forecast")).get("severity")
            if dict_from_value(coordination.get("contention_forecast")) is not None
            else None,
            multi_seat_coordination.get("severity"),
        ),
        "contention_reason": first_non_empty(
            dict_from_value(coordination.get("contention_forecast")).get("reason")
            if dict_from_value(coordination.get("contention_forecast")) is not None
            else None,
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
            "seat_selection_policy": seat_selection_policy,
            "occupancy_state": first_non_empty(
                multi_seat_coordination.get("occupancy_state"),
            ),
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
                first_non_empty(
                    surface.get("surface_ref"),
                    surface.get("surface_kind"),
                )
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


def trace_id_from_metadata(task_id: str, metadata: dict[str, Any]) -> str:
    value = metadata.get("trace_id") if isinstance(metadata, dict) else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return f"trace:{task_id}"


def trace_id_from_kernel_meta(task_id: str, metadata: dict[str, Any] | None) -> str:
    if isinstance(metadata, dict):
        value = metadata.get("trace_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"trace:{task_id}"


def serialize_evidence_record(record: EvidenceRecord) -> dict[str, object]:
    metadata = dict(record.metadata or {})
    return {
        "id": record.id,
        "trace_id": trace_id_from_metadata(record.task_id, metadata),
        "task_id": record.task_id,
        "actor_ref": record.actor_ref,
        "risk_level": record.risk_level,
        "action_summary": record.action_summary,
        "result_summary": record.result_summary,
        "environment_ref": record.environment_ref,
        "capability_ref": record.capability_ref,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "status": record.status,
        "metadata": metadata,
        "artifact_refs": list(record.artifact_refs),
        "replay_refs": list(record.replay_refs),
    }


def serialize_kernel_meta(
    task_id: str,
    payload: dict[str, Any] | None,
) -> dict[str, object]:
    payload = payload or {}
    trigger = extract_task_trigger(payload)
    return {
        "trace_id": trace_id_from_kernel_meta(task_id, payload),
        "trigger": trigger,
        "raw": payload,
        "chat_thread": extract_chat_thread_payload(payload),
    }


def serialize_task_knowledge_context(payload: dict[str, Any] | None) -> dict[str, object]:
    payload = payload or {}
    runtime = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}
    return {
        "strategy_summary": first_non_empty(
            payload.get("strategy_summary"),
            runtime.get("strategy_summary") if isinstance(runtime, dict) else None,
        ),
        "strategy_items": string_list_from_values(
            payload.get("strategy_items"),
            runtime.get("strategy_items") if isinstance(runtime, dict) else None,
        ),
        "knowledge_refs": string_list_from_values(
            payload.get("knowledge_refs"),
            runtime.get("knowledge_refs") if isinstance(runtime, dict) else None,
        ),
        "knowledge_items": string_list_from_values(
            payload.get("knowledge_items"),
            runtime.get("knowledge_items") if isinstance(runtime, dict) else None,
        ),
        "knowledge_documents": string_list_from_values(
            payload.get("knowledge_documents"),
            runtime.get("knowledge_documents") if isinstance(runtime, dict) else None,
        ),
        "memory_refs": string_list_from_values(
            payload.get("memory_refs"),
            runtime.get("memory_refs") if isinstance(runtime, dict) else None,
        ),
        "memory_items": string_list_from_values(
            payload.get("memory_items"),
            runtime.get("memory_items") if isinstance(runtime, dict) else None,
        ),
        "memory_documents": string_list_from_values(
            payload.get("memory_documents"),
            runtime.get("memory_documents") if isinstance(runtime, dict) else None,
        ),
    }


def task_status_value(task: Any, runtime: Any | None) -> str:
    if runtime is not None and getattr(task, "status", None) == "running":
        runtime_status = getattr(runtime, "runtime_status", None)
        if runtime_status not in (None, ""):
            return str(runtime_status)
    task_status = getattr(task, "status", None)
    if task_status not in (None, ""):
        return str(task_status)
    return "unknown"


def task_phase_value(task: Any, runtime: Any | None) -> str:
    return str(
        getattr(runtime, "current_phase", None)
        or getattr(task, "status", None)
        or "unknown"
    )


def count_pending_decisions(decisions: list[Any]) -> int:
    return sum(
        1
        for decision in decisions
        if str(getattr(decision, "status", "") or "") in {"open", "reviewing"}
    )


def latest_evidence_record(evidence: list[EvidenceRecord]) -> EvidenceRecord | None:
    if not evidence:
        return None
    return max(
        evidence,
        key=lambda item: item.created_at.isoformat() if item.created_at else "",
    )


def _evidence_sort_key(record: EvidenceRecord) -> str:
    if record.created_at is not None:
        return record.created_at.isoformat()
    return ""


def _route_for_first_replay(record: EvidenceRecord) -> str | None:
    for replay in record.replay_pointers:
        replay_id = first_non_empty(getattr(replay, "id", None))
        if replay_id is not None:
            return f"/api/runtime-center/replays/{replay_id}"
    return None


def _route_for_first_artifact(record: EvidenceRecord) -> str | None:
    for artifact in record.artifacts:
        artifact_id = first_non_empty(getattr(artifact, "id", None))
        if artifact_id is not None:
            return f"/api/runtime-center/artifacts/{artifact_id}"
    return None


def _bool_from_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "verified", "passed", "success", "ready"}:
            return True
        if normalized in {"false", "0", "no", "failed", "blocked", "pending", "required"}:
            return False
    return None


def _canonicalize_verification_status(value: object) -> str | None:
    normalized = first_non_empty(value)
    if normalized is None:
        return None
    aliases = {
        "ok": "passed",
        "pass": "passed",
        "verified": "passed",
        "success": "passed",
        "complete": "completed",
        "unverified": "blocked",
    }
    return aliases.get(normalized.strip().lower(), normalized)


def _evidence_metadata_payloads(
    metadata: dict[str, object],
) -> tuple[
    dict[str, object] | None,
    dict[str, object] | None,
    dict[str, object] | None,
    dict[str, object] | None,
    dict[str, object] | None,
]:
    step_payload = dict_from_value(metadata.get("step"))
    verification_payload = (
        dict_from_value(metadata.get("verification"))
        or dict_from_value(metadata.get("verification_payload"))
    )
    closeout_payload = (
        dict_from_value(metadata.get("closeout"))
        or dict_from_value(metadata.get("acceptance_closeout"))
    )
    checkpoint_payload = (
        dict_from_value(metadata.get("checkpoint"))
        or (
            dict_from_value(closeout_payload.get("checkpoint"))
            if closeout_payload is not None
            else None
        )
        or (
            dict_from_value(verification_payload.get("checkpoint"))
            if verification_payload is not None
            else None
        )
    )
    verification_details = (
        dict_from_value(verification_payload.get("details"))
        if verification_payload is not None
        else None
    )
    return (
        step_payload,
        verification_payload,
        closeout_payload,
        checkpoint_payload,
        verification_details,
    )


def _normalized_evidence_closeout(
    record: EvidenceRecord,
) -> dict[str, str | None]:
    metadata = dict(record.metadata or {})
    (
        step_payload,
        verification_payload,
        closeout_payload,
        checkpoint_payload,
        verification_details,
    ) = _evidence_metadata_payloads(metadata)
    verification_status = _canonicalize_verification_status(
        first_non_empty(
            metadata.get("verification_status"),
            metadata.get("closeout_status"),
            verification_payload.get("verification_status")
            if verification_payload is not None
            else None,
            verification_payload.get("status") if verification_payload is not None else None,
            closeout_payload.get("verification_status") if closeout_payload is not None else None,
            closeout_payload.get("closeout_status") if closeout_payload is not None else None,
            checkpoint_payload.get("verification_status")
            if checkpoint_payload is not None
            else None,
            verification_details.get("verification_status")
            if verification_details is not None
            else None,
        ),
    )
    if verification_status is None:
        verified = _bool_from_value(
            verification_payload.get("verified") if verification_payload is not None else None,
        )
        if verified is True:
            verification_status = "passed"
        elif verified is False:
            verification_status = "blocked"
    verification_reason = first_non_empty(
        metadata.get("verification_reason"),
        metadata.get("blocked_reason"),
        metadata.get("closeout_reason"),
        verification_payload.get("verification_reason")
        if verification_payload is not None
        else None,
        verification_payload.get("summary") if verification_payload is not None else None,
        verification_payload.get("reason") if verification_payload is not None else None,
        verification_payload.get("message") if verification_payload is not None else None,
        verification_payload.get("error") if verification_payload is not None else None,
        verification_payload.get("failure_class")
        if verification_payload is not None
        else None,
        closeout_payload.get("verification_reason") if closeout_payload is not None else None,
        closeout_payload.get("closeout_reason") if closeout_payload is not None else None,
        closeout_payload.get("summary") if closeout_payload is not None else None,
        checkpoint_payload.get("verification_reason")
        if checkpoint_payload is not None
        else None,
        verification_details.get("verification_reason")
        if verification_details is not None
        else None,
        verification_details.get("summary") if verification_details is not None else None,
        verification_details.get("reason") if verification_details is not None else None,
    )
    step_id = first_non_empty(
        metadata.get("step_id"),
        metadata.get("step_index"),
        metadata.get("checkpoint_id"),
        step_payload.get("step_id") if step_payload is not None else None,
        step_payload.get("id") if step_payload is not None else None,
        step_payload.get("index") if step_payload is not None else None,
        checkpoint_payload.get("step_id") if checkpoint_payload is not None else None,
        checkpoint_payload.get("checkpoint_id") if checkpoint_payload is not None else None,
        checkpoint_payload.get("id") if checkpoint_payload is not None else None,
        closeout_payload.get("step_id") if closeout_payload is not None else None,
        closeout_payload.get("checkpoint_id") if closeout_payload is not None else None,
        verification_payload.get("step_id") if verification_payload is not None else None,
        verification_payload.get("checkpoint_id") if verification_payload is not None else None,
        verification_details.get("step_id") if verification_details is not None else None,
        verification_details.get("checkpoint_id") if verification_details is not None else None,
    )
    step_title = first_non_empty(
        metadata.get("step_title"),
        metadata.get("step_action"),
        metadata.get("checkpoint_title"),
        step_payload.get("step_title") if step_payload is not None else None,
        step_payload.get("title") if step_payload is not None else None,
        step_payload.get("action") if step_payload is not None else None,
        checkpoint_payload.get("step_title") if checkpoint_payload is not None else None,
        checkpoint_payload.get("checkpoint_title")
        if checkpoint_payload is not None
        else None,
        checkpoint_payload.get("title") if checkpoint_payload is not None else None,
        closeout_payload.get("step_title") if closeout_payload is not None else None,
        closeout_payload.get("checkpoint_title") if closeout_payload is not None else None,
        closeout_payload.get("title") if closeout_payload is not None else None,
        verification_payload.get("step_title") if verification_payload is not None else None,
        verification_payload.get("checkpoint_title")
        if verification_payload is not None
        else None,
        verification_payload.get("title") if verification_payload is not None else None,
        verification_details.get("step_title") if verification_details is not None else None,
        verification_details.get("checkpoint_title")
        if verification_details is not None
        else None,
        verification_details.get("title") if verification_details is not None else None,
        record.action_summary,
        record.result_summary,
    )
    return {
        "step_id": step_id,
        "step_title": step_title,
        "verification_status": verification_status,
        "verification_reason": verification_reason,
    }


def _evidence_step_payload(record: EvidenceRecord) -> dict[str, object]:
    normalized = _normalized_evidence_closeout(record)
    evidence_id = first_non_empty(record.id)
    return {
        "evidence_id": evidence_id,
        "evidence_route": (
            f"/api/runtime-center/evidence/{evidence_id}" if evidence_id is not None else None
        ),
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "step_id": normalized.get("step_id"),
        "step_title": normalized.get("step_title"),
        "action_summary": record.action_summary,
        "result_summary": record.result_summary,
        "status": record.status,
        "verification_status": normalized.get("verification_status"),
        "verification_reason": normalized.get("verification_reason"),
        "artifact_count": len(record.artifacts),
        "replay_count": len(record.replay_pointers),
        "artifact_route": _route_for_first_artifact(record),
        "replay_route": _route_for_first_replay(record),
    }


def summarize_evidence_status(
    task_id: str,
    evidence: list[EvidenceRecord],
) -> dict[str, object]:
    recent_steps = [
        _evidence_step_payload(record)
        for record in sorted(evidence, key=_evidence_sort_key, reverse=True)[:3]
    ]
    latest = recent_steps[0] if recent_steps else None
    latest_replayable_record = next(
        (
            record
            for record in sorted(evidence, key=_evidence_sort_key, reverse=True)
            if record.replay_pointers
        ),
        None,
    )
    latest_replayable = (
        _evidence_step_payload(latest_replayable_record)
        if latest_replayable_record is not None
        else None
    )
    verified_markers = {"passed", "verified", "success", "completed", "ready"}
    blocked_markers = {"blocked", "failed", "pending", "required", "waiting"}
    verified_count = 0
    blocked_count = 0
    replayable_count = 0
    artifact_backed_count = 0
    for record in evidence:
        verification_status = _normalized_evidence_closeout(record).get("verification_status")
        if verification_status is not None:
            key = verification_status.strip().lower()
            if key in verified_markers:
                verified_count += 1
            if key in blocked_markers:
                blocked_count += 1
        if record.replay_pointers:
            replayable_count += 1
        if record.artifacts:
            artifact_backed_count += 1
    return {
        "total_count": len(evidence),
        "replayable_count": replayable_count,
        "artifact_backed_count": artifact_backed_count,
        "verified_count": verified_count,
        "blocked_count": blocked_count,
        "latest_evidence_id": latest.get("evidence_id") if isinstance(latest, dict) else None,
        "latest_evidence_route": (
            latest.get("evidence_route") if isinstance(latest, dict) else None
        ),
        "latest_replayable_evidence_id": (
            latest_replayable.get("evidence_id")
            if isinstance(latest_replayable, dict)
            else None
        ),
        "latest_replayable_evidence_route": (
            latest_replayable.get("evidence_route")
            if isinstance(latest_replayable, dict)
            else None
        ),
        "latest_replayable_replay_route": (
            latest_replayable.get("replay_route")
            if isinstance(latest_replayable, dict)
            else None
        ),
        "task_evidence_route": f"/api/runtime-center/evidence?task_id={task_id}",
        "recent_steps": recent_steps,
    }


def serialize_child_rollup(
    task: Any,
    runtime: Any | None,
    *,
    owner_agent: dict[str, object] | None = None,
    work_context: dict[str, object] | None = None,
) -> dict[str, object]:
    owner_agent_name = (
        first_non_empty(owner_agent.get("name"), owner_agent.get("role_name"))
        if isinstance(owner_agent, dict)
        else None
    )
    return {
        "id": getattr(task, "id", None),
        "title": getattr(task, "title", None),
        "status": task_status_value(task, runtime),
        "phase": task_phase_value(task, runtime),
        "summary": first_non_empty(
            getattr(runtime, "last_result_summary", None) if runtime is not None else None,
            getattr(runtime, "last_error_summary", None) if runtime is not None else None,
            getattr(task, "summary", None),
        ),
        "owner_agent_id": getattr(task, "owner_agent_id", None),
        "owner_agent_name": owner_agent_name,
        "updated_at": (
            getattr(runtime, "updated_at", None) if runtime is not None else getattr(task, "updated_at", None)
        ),
        "context_key": (
            first_non_empty(work_context.get("context_key"))
            if isinstance(work_context, dict)
            else None
        ),
        "work_context": work_context,
        "route": task_route(getattr(task, "id", "")),
    }


def build_task_review_payload(
    *,
    task: Any,
    runtime: Any | None,
    decisions: list[Any],
    evidence: list[EvidenceRecord],
    execution_feedback: dict[str, object] | None,
    child_results: list[dict[str, object]],
    owner_agent: dict[str, object] | None,
    task_route: str,
) -> dict[str, object]:
    status = task_status_value(task, runtime)
    phase = task_phase_value(task, runtime)
    kernel_metadata = decode_kernel_task_metadata(getattr(task, "acceptance_criteria", None))
    objective = first_non_empty(getattr(task, "summary", None), getattr(task, "title", None)) or str(
        getattr(task, "title", "task"),
    )
    pending_decision_count = count_pending_decisions(decisions)
    latest_evidence = latest_evidence_record(evidence)
    latest_evidence_summary = (
        first_non_empty(
            getattr(latest_evidence, "result_summary", None),
            getattr(latest_evidence, "action_summary", None),
        )
        if latest_evidence is not None
        else None
    )
    latest_result_summary = first_non_empty(
        getattr(runtime, "last_result_summary", None) if runtime is not None else None,
        latest_evidence_summary,
        getattr(runtime, "last_error_summary", None) if runtime is not None else None,
        getattr(task, "summary", None),
    )
    child_task_count = len(child_results)
    child_terminal_count = sum(
        1
        for child in child_results
        if str(child.get("status") or "") in {"completed", "failed", "cancelled", "terminated"}
    )
    child_completion_rate = (
        round((child_terminal_count / child_task_count) * 100, 1)
        if child_task_count
        else 0.0
    )
    active_children = [
        child
        for child in child_results
        if str(child.get("status") or "") not in {"completed", "failed", "cancelled", "terminated"}
    ]
    failed_children = [
        child
        for child in child_results
        if str(child.get("status") or "") in {"failed", "cancelled", "blocked"}
    ]
    owner_agent_name = (
        first_non_empty(owner_agent.get("name"), owner_agent.get("role_name"))
        if isinstance(owner_agent, dict)
        else None
    )
    trigger = extract_task_trigger(kernel_metadata)
    feedback = execution_feedback or {}
    current_stage = first_non_empty(feedback.get("current_stage"), phase)
    recent_failures = string_list_from_values(feedback.get("recent_failures"))
    effective_actions = string_list_from_values(feedback.get("effective_actions"))
    avoid_repeats = string_list_from_values(feedback.get("avoid_repeats"))
    feedback_evidence_refs = string_list_from_values(feedback.get("evidence_refs"))
    runtime_metadata = runtime_metadata_from_runtime(runtime)
    workspace_graph = projection_section(
        feedback=feedback,
        runtime_metadata=runtime_metadata,
        key="workspace_graph",
    )
    cooperative_adapter_availability = projection_section(
        feedback=feedback,
        runtime_metadata=runtime_metadata,
        key="cooperative_adapter_availability",
    )
    host_contract = projection_section(
        feedback=feedback,
        runtime_metadata=runtime_metadata,
        key="host_contract",
    )
    recovery = projection_section(
        feedback=feedback,
        runtime_metadata=runtime_metadata,
        key="recovery",
    )
    host_event_summary = projection_section(
        feedback=feedback,
        runtime_metadata=runtime_metadata,
        key="host_event_summary",
    )
    seat_runtime = projection_section(
        feedback=feedback,
        runtime_metadata=runtime_metadata,
        key="seat_runtime",
    )
    browser_site_contract = projection_section(
        feedback=feedback,
        runtime_metadata=runtime_metadata,
        key="browser_site_contract",
    )
    desktop_app_contract = projection_section(
        feedback=feedback,
        runtime_metadata=runtime_metadata,
        key="desktop_app_contract",
    )
    host_companion_session = projection_section(
        feedback=feedback,
        runtime_metadata=runtime_metadata,
        key="host_companion_session",
    )
    host_twin = projection_section(
        feedback=feedback,
        runtime_metadata=runtime_metadata,
        key="host_twin",
    )
    host_twin_summary_payload = projection_section(
        feedback=feedback,
        runtime_metadata=runtime_metadata,
        key="host_twin_summary",
    ) or build_host_twin_summary(
        host_twin,
        host_companion_session=host_companion_session,
    )
    host_twin_blocker_family = host_twin_active_blocker_family(host_twin)
    host_twin_resume = host_twin_resume_kind(host_twin)
    host_twin_recovery_mode = host_twin_legal_recovery_mode(host_twin)
    host_twin_recovery_summary = host_twin_legal_recovery_summary(host_twin)
    host_twin_anchor = host_twin_trusted_anchor(host_twin)
    host_twin_writable_surface = host_twin_writable_surface_label(host_twin)
    host_twin_seat_owner = host_twin_seat_owner_ref(host_twin)
    host_twin_coordination = (
        dict_from_value(host_twin.get("coordination"))
        if host_twin is not None
        else None
    )
    coordination_contention = (
        dict_from_value(host_twin_coordination.get("contention_forecast"))
        if host_twin_coordination is not None
        else None
    )
    canonical_host_ready = host_twin_summary_ready(host_twin_summary_payload)
    host_twin_summary_recovery_mode = first_non_empty(
        host_twin_summary_payload.get("legal_recovery_mode")
        if host_twin_summary_payload is not None
        else None,
        host_twin_recovery_mode,
    )
    coordination_scheduler_action = first_non_empty(
        host_twin_summary_payload.get("recommended_scheduler_action")
        if host_twin_summary_payload is not None
        else None,
        host_twin_coordination.get("recommended_scheduler_action")
        if host_twin_coordination is not None
        else None,
    )
    coordination_selected_seat_ref = first_non_empty(
        host_twin_summary_payload.get("selected_seat_ref")
        if host_twin_summary_payload is not None
        else None,
        host_twin_coordination.get("selected_seat_ref")
        if host_twin_coordination is not None
        else None,
    )
    coordination_seat_policy = first_non_empty(
        host_twin_summary_payload.get("seat_selection_policy")
        if host_twin_summary_payload is not None
        else None,
        host_twin_coordination.get("seat_selection_policy")
        if host_twin_coordination is not None
        else None,
    )
    coordination_severity = first_non_empty(
        host_twin_summary_payload.get("contention_severity")
        if host_twin_summary_payload is not None
        else None,
        coordination_contention.get("severity")
        if coordination_contention is not None
        else None,
    )
    coordination_reason = (
        first_non_empty(
            host_twin_summary_payload.get("contention_reason")
            if host_twin_summary_payload is not None
            else None,
            coordination_contention.get("reason")
            if coordination_contention is not None
            else None,
        )
        if canonical_host_ready
        else first_non_empty(
            host_twin_blocker_family,
            coordination_contention.get("reason")
            if coordination_contention is not None
            else None,
            host_twin_summary_payload.get("contention_reason")
            if host_twin_summary_payload is not None
            else None,
        )
    )
    host_status = (
        first_non_empty(host_contract.get("status"), host_contract.get("state"))
        if host_contract is not None
        else None
    )
    host_blocker_reason = (
        first_non_empty(
            host_twin_blocker_family,
            host_contract.get("blocked_reason"),
            host_contract.get("blocker"),
            host_contract.get("status_reason"),
            host_contract.get("current_gap_or_blocker"),
        )
        if host_contract is not None
        else None
    )
    host_blocked_markers = {
        "blocked",
        "blocking",
        "degraded",
        "error",
        "failed",
        "unavailable",
        "contention",
        "handoff",
    }
    host_blocked = bool(host_blocker_reason) or (
        host_status is not None and host_status.strip().lower() in host_blocked_markers
    )
    recovery_status = (
        first_non_empty(recovery.get("status"), recovery.get("state"))
        if recovery is not None
        else None
    )
    recovery_mode = (
        first_non_empty(
            host_twin_recovery_mode,
            recovery.get("mode"),
            recovery.get("recovery_mode"),
            recovery.get("resume_kind"),
        )
        if recovery is not None
        else host_twin_recovery_mode
    )
    recovery_active_markers = {
        "pending",
        "required",
        "recovering",
        "failed",
        "blocked",
        "stalled",
    }
    recovery_active_mode_markers = {
        "resume-environment",
        "rebind-environment",
        "attach-environment",
        "resume-runtime",
        "resume-task",
    }
    recovery_terminal_markers = {"attached", "completed", "ready", "stable", "none"}
    recovery_active = False
    if recovery_status is not None:
        status_key = recovery_status.strip().lower()
        recovery_active = status_key in recovery_active_markers
    if recovery_mode is not None:
        mode_key = recovery_mode.strip().lower()
        if mode_key in recovery_active_mode_markers:
            status_key = recovery_status.strip().lower() if recovery_status is not None else ""
            if status_key not in recovery_terminal_markers:
                recovery_active = True
    if canonical_host_ready:
        recovery_active = False
        recovery_status = None
        recovery_mode = first_non_empty(host_twin_summary_recovery_mode, host_twin_resume)
    latest_host_event = (
        dict_from_value(host_event_summary.get("latest_event"))
        if host_event_summary is not None
        else None
    )
    host_event_name = (
        first_non_empty(
            host_event_summary.get("last_event"),
            host_event_summary.get("event"),
            host_event_summary.get("summary"),
            latest_host_event.get("event_name") if latest_host_event is not None else None,
            latest_host_event.get("action") if latest_host_event is not None else None,
        )
        if host_event_summary is not None
        else None
    )
    seat_runtime_status = (
        first_non_empty(seat_runtime.get("status"), seat_runtime.get("state"))
        if seat_runtime is not None
        else None
    )
    handoff_checkpoint = (
        dict_from_value(workspace_graph.get("handoff_checkpoint"))
        if workspace_graph is not None
        else None
    )
    handoff_state = first_non_empty(
        handoff_checkpoint.get("state") if handoff_checkpoint is not None else None,
        host_contract.get("handoff_state") if host_contract is not None else None,
    )
    handoff_reason = first_non_empty(
        handoff_checkpoint.get("reason") if handoff_checkpoint is not None else None,
        host_contract.get("handoff_reason") if host_contract is not None else None,
        host_blocker_reason,
    )
    handoff_owner_ref = first_non_empty(
        host_twin_summary_payload.get("handoff_owner_ref")
        if host_twin_summary_payload is not None
        else None,
        host_twin_seat_owner,
        handoff_checkpoint.get("owner_ref") if handoff_checkpoint is not None else None,
        host_contract.get("handoff_owner_ref") if host_contract is not None else None,
    )
    handoff_checkpoint_ref = first_non_empty(
        handoff_checkpoint.get("checkpoint_ref") if handoff_checkpoint is not None else None,
        host_twin.get("checkpoint_ref") if host_twin is not None else None,
        (
            dict_from_value(host_twin.get("legal_recovery")).get("checkpoint_ref")
            if host_twin is not None and dict_from_value(host_twin.get("legal_recovery")) is not None
            else None
        ),
    )
    handoff_return_condition = first_non_empty(
        handoff_checkpoint.get("return_condition") if handoff_checkpoint is not None else None,
        (
            dict_from_value(host_twin.get("legal_recovery")).get("return_condition")
            if host_twin is not None and dict_from_value(host_twin.get("legal_recovery")) is not None
            else None
        ),
        host_contract.get("return_condition") if host_contract is not None else None,
    )
    verification_channel = first_non_empty(
        handoff_checkpoint.get("verification_channel") if handoff_checkpoint is not None else None,
        (
            dict_from_value(host_twin.get("legal_recovery")).get("verification_channel")
            if host_twin is not None and dict_from_value(host_twin.get("legal_recovery")) is not None
            else None
        ),
        host_contract.get("verification_channel") if host_contract is not None else None,
        recovery.get("verification_channel") if recovery is not None else None,
    )
    if canonical_host_ready:
        handoff_state = None
        handoff_reason = None
        handoff_owner_ref = None
        host_blocker_reason = None
        host_blocked = False
        if not coordination_severity:
            coordination_severity = "clear"
    latest_evidence_closeout = (
        _normalized_evidence_closeout(latest_evidence)
        if latest_evidence is not None
        else {}
    )
    verification_status = first_non_empty(
        handoff_checkpoint.get("verification_status") if handoff_checkpoint is not None else None,
        browser_site_contract.get("verification_status") if browser_site_contract is not None else None,
        desktop_app_contract.get("verification_status") if desktop_app_contract is not None else None,
        latest_evidence_closeout.get("verification_status"),
    )
    verification_reason = first_non_empty(
        handoff_checkpoint.get("reason") if handoff_checkpoint is not None else None,
        host_twin_blocker_family,
        browser_site_contract.get("verification_reason") if browser_site_contract is not None else None,
        desktop_app_contract.get("verification_reason") if desktop_app_contract is not None else None,
        latest_evidence_closeout.get("verification_reason"),
        host_blocker_reason,
    )
    if (
        handoff_state is not None or recovery_active
    ) and (
        verification_status is None
        or verification_status.strip().lower() in {"passed", "verified", "success", "completed", "ready"}
    ):
        verification_status = "blocked"
    elif verification_status is None and verification_reason is not None:
        verification_status = "blocked"
    latest_anchor = first_non_empty(
        host_twin_anchor,
        browser_site_contract.get("last_verified_dom_anchor") if browser_site_contract is not None else None,
        browser_site_contract.get("verification_anchor") if browser_site_contract is not None else None,
        desktop_app_contract.get("window_anchor_summary") if desktop_app_contract is not None else None,
        desktop_app_contract.get("verification_anchor") if desktop_app_contract is not None else None,
    )
    continuity = {
        "handoff": {
            "state": handoff_state,
            "reason": handoff_reason,
            "owner_ref": handoff_owner_ref,
            "checkpoint_ref": handoff_checkpoint_ref,
            "return_condition": handoff_return_condition,
            "resume_kind": first_non_empty(
                handoff_checkpoint.get("resume_kind") if handoff_checkpoint is not None else None,
                host_twin_resume,
                recovery_mode,
            ),
        },
        "verification": {
            "status": verification_status,
            "reason": verification_reason,
            "channel": verification_channel,
            "latest_anchor": latest_anchor,
        },
    }
    evidence_status = summarize_evidence_status(getattr(task, "id", ""), evidence)
    execution_state, blocked_reason, stuck_reason = derive_review_execution_state(
        status=status,
        phase=phase,
        pending_decision_count=pending_decision_count,
        latest_result_summary=latest_result_summary,
        latest_evidence_summary=latest_evidence_summary,
        latest_error_summary=(
            getattr(runtime, "last_error_summary", None) if runtime is not None else None
        ),
        updated_at=(
            getattr(runtime, "updated_at", None)
            if runtime is not None
            else getattr(task, "updated_at", None)
        ),
    )

    if pending_decision_count:
        headline = f"任务当前被 {pending_decision_count} 条待确认事项挂起"
    elif status in {"failed", "blocked", "cancelled"}:
        headline = (
            first_non_empty(
                getattr(runtime, "last_error_summary", None) if runtime is not None else None,
                latest_result_summary,
            )
            or "任务执行受阻，需要处理失败或阻塞原因"
        )
    elif active_children:
        headline = f"主线仍在推进，尚有 {len(active_children)} 个子任务未收口"
    elif status in {"completed", "terminated"}:
        headline = latest_result_summary or "任务已完成，结果已回流控制线程"
    else:
        headline = latest_result_summary or "任务正在执行并持续回写结果"

    summary_lines = [
        f"任务目标：{objective}",
        f"当前状态：{status}",
        f"执行阶段：{phase}",
    ]
    if coordination_scheduler_action or coordination_severity:
        coordination_label = first_non_empty(
            coordination_scheduler_action,
            coordination_severity,
        )
        coordination_details = [
            value
            for value in (
                coordination_seat_policy,
                coordination_selected_seat_ref,
                coordination_reason,
            )
            if value
        ]
        if coordination_details:
            summary_lines.append(
                f"Coordination: {coordination_label} ({', '.join(coordination_details)})"
            )
        else:
            summary_lines.append(f"Coordination: {coordination_label}")
    if handoff_state:
        if handoff_reason:
            summary_lines.append(f"Handoff: {handoff_state} ({handoff_reason})")
        else:
            summary_lines.append(f"Handoff: {handoff_state}")
    if host_twin_summary_payload:
        host_companion_status = first_non_empty(
            host_twin_summary_payload.get("host_companion_status"),
        )
        host_companion_source = first_non_empty(
            host_twin_summary_payload.get("host_companion_source"),
        )
        if host_companion_status:
            host_companion_label = host_companion_status
            if host_companion_source:
                host_companion_label += f" via {host_companion_source}"
            summary_lines.append(f"Host companion: {host_companion_label}")
        ready_app_family_keys = string_list_from_values(
            host_twin_summary_payload.get("ready_app_family_keys"),
        )
        if ready_app_family_keys:
            summary_lines.append(
                f"App families ready: {', '.join(ready_app_family_keys)}"
            )
        active_family_keys = string_list_from_values(
            host_twin_summary_payload.get("active_app_family_keys"),
        )
        if active_family_keys:
            summary_lines.append(
                f"Host twin families: {', '.join(active_family_keys)}"
            )
        seat_count = first_non_empty(host_twin_summary_payload.get("seat_count"))
        multi_seat_coordination = dict_from_value(
            host_twin_summary_payload.get("multi_seat_coordination"),
        ) or {}
        if seat_count or multi_seat_coordination.get("selected_seat_ref"):
            seat_coordination_label = first_non_empty(
                multi_seat_coordination.get("selected_seat_ref"),
                host_twin_summary_payload.get("selected_seat_ref"),
            )
            if seat_count:
                summary_lines.append(
                    f"Seat coordination: {seat_count} seat(s)"
                    + (f" via {seat_coordination_label}" if seat_coordination_label else "")
                )
        host_twin_coordination_label = first_non_empty(
            host_twin_summary_payload.get("recommended_scheduler_action"),
            host_twin_summary_payload.get("contention_severity"),
        )
        if host_twin_coordination_label:
            summary_lines.append(
                f"Host twin coordination: {host_twin_coordination_label}"
            )
    if verification_status or verification_channel or latest_anchor:
        verification_label = first_non_empty(
            verification_status,
            verification_channel,
            latest_anchor,
        )
        if verification_reason:
            summary_lines.append(f"Verification: {verification_label} ({verification_reason})")
        else:
            summary_lines.append(f"Verification: {verification_label}")
    if current_stage and current_stage != phase:
        summary_lines.append(f"Continue from: {current_stage}")
    if host_blocker_reason:
        summary_lines.append(f"Host blocker: {host_blocker_reason}")
    elif host_blocked and host_status:
        summary_lines.append(f"Host status: {host_status}")
    if recovery_status or recovery_mode:
        if recovery_status and recovery_mode:
            summary_lines.append(f"Recovery: {recovery_status} ({recovery_mode})")
        elif recovery_status:
            summary_lines.append(f"Recovery: {recovery_status}")
        else:
            summary_lines.append(f"Recovery mode: {recovery_mode}")
    if seat_runtime_status:
        summary_lines.append(f"Seat runtime: {seat_runtime_status}")
    if host_event_name:
        summary_lines.append(f"Host events: {host_event_name}")
    if owner_agent_name:
        summary_lines.append(f"当前负责人：{owner_agent_name}")
    if latest_result_summary:
        summary_lines.append(f"最新结果：{latest_result_summary}")
    if child_task_count:
        summary_lines.append(
            f"子任务收口：{child_terminal_count}/{child_task_count}（{child_completion_rate}%）",
        )
    if pending_decision_count:
        summary_lines.append(f"待确认事项：{pending_decision_count} 条")
    if latest_evidence_summary and latest_evidence_summary != latest_result_summary:
        summary_lines.append(f"最新证据：{latest_evidence_summary}")

    next_actions: list[str] = []
    if coordination_scheduler_action and coordination_scheduler_action != "proceed":
        coordination_targets = [
            value
            for value in (
                coordination_seat_policy,
                coordination_selected_seat_ref,
                coordination_reason,
            )
            if value
        ]
        if coordination_targets:
            next_actions.append(
                "Follow host coordination action: "
                f"{coordination_scheduler_action} ({', '.join(coordination_targets)})"
            )
        else:
            next_actions.append(
                f"Follow host coordination action: {coordination_scheduler_action}"
            )
    if host_twin_writable_surface or host_twin_recovery_summary:
        recovery_target = (
            host_twin_recovery_summary
            or host_twin_recovery_mode
            or recovery_mode
            or recovery_status
            or "host recovery path"
        )
        surface_target = host_twin_writable_surface or "current writable surface"
        next_actions.append(
            f"Resume via {recovery_target} on writable surface: {surface_target}"
        )
    if handoff_state:
        handoff_label = first_non_empty(handoff_reason, handoff_return_condition, handoff_state)
        next_actions.append(f"Confirm handoff return condition: {handoff_label}")
    if verification_channel:
        verification_label = first_non_empty(
            verification_reason,
            verification_status,
            latest_anchor,
        ) or "pending"
        next_actions.append(f"Verify checkpoint via {verification_channel}: {verification_label}")
    if host_blocker_reason:
        next_actions.append(f"Resolve host blocker: {host_blocker_reason}")
    elif host_blocked and host_status:
        next_actions.append(f"Stabilize host contract state: {host_status}")
    if recovery_active:
        recovery_label = first_non_empty(recovery_mode, recovery_status) or "unknown"
        next_actions.append(f"Run recovery checkpoint: {recovery_label}")
    if pending_decision_count:
        next_actions.append("优先处理待确认事项，避免任务线程继续停在审批边界。")
    elif avoid_repeats:
        next_actions.append(f"Avoid repeating: {avoid_repeats[0]}")
    if failed_children:
        next_actions.append("检查失败或取消的子任务，决定重试、改派还是终止。")
    if active_children:
        next_actions.append("继续跟进未收口的子任务，并把阶段结果同步回控制线程。")
    if status in {"running", "active", "queued", "created", "waiting", "waiting-confirm"} and not pending_decision_count:
        next_actions.append("继续当前执行，并把关键动作和产出补齐到正式证据链。")
    if status in {"completed", "terminated"}:
        next_actions.append("基于已完成结果确认是否需要新一轮任务派发、复盘或归档。")
    if status in {"failed", "blocked", "cancelled"}:
        next_actions.append("围绕失败原因修正计划，再决定是否重新进入执行主链。")
    if not next_actions:
        next_actions.append("继续观察任务状态变化，并保持结果稳定回流控制线程。")

    risks: list[str] = []
    runtime_risk_level = (
        str(getattr(runtime, "risk_level", "") or "").strip()
        if runtime is not None
        else ""
    )
    if runtime_risk_level and runtime_risk_level != "auto":
        risks.append(f"当前任务风险级别为 {runtime_risk_level}，后续动作仍需按治理边界执行。")
    if coordination_severity and coordination_severity != "clear":
        coordination_label = first_non_empty(
            coordination_reason,
            coordination_scheduler_action,
        ) or "coordination blockers remain active"
        risks.append(
            f"Host coordination contention is {coordination_severity}: {coordination_label}."
        )
    if host_blocker_reason:
        risks.append(f"Host blocker detected: {host_blocker_reason}.")
    elif host_blocked and host_status:
        risks.append(f"Host contract status is {host_status}; execution continuity may be unstable.")
    if recovery_active:
        recovery_label = first_non_empty(recovery_status, recovery_mode) or "active"
        risks.append(f"Recovery is active ({recovery_label}); avoid blind continuation.")
    if handoff_state:
        handoff_label = first_non_empty(handoff_reason, handoff_state) or "active"
        risks.append(f"Handoff is active ({handoff_label}); do not resume without verification.")
    if pending_decision_count:
        risks.append("存在待确认事项，外部动作闭环仍未完全放行。")
    if failed_children:
        risks.append(f"有 {len(failed_children)} 个子任务未成功收口，主线结果可能不完整。")
    if not evidence:
        risks.append("尚无正式证据回写，后续复盘与审计可追溯性偏弱。")
    if not risks:
        risks.append("当前未发现额外治理阻塞，可继续按任务线程推进。")

    return {
        "headline": headline,
        "objective": objective,
        "status": status,
        "phase": phase,
        "execution_state": execution_state,
        "current_stage": current_stage,
        "recent_failures": recent_failures[:4],
        "effective_actions": effective_actions[:4],
        "avoid_repeats": avoid_repeats[:4],
        "feedback_evidence_refs": feedback_evidence_refs[:8],
        "execution_runtime": {
            "workspace": workspace_graph,
            "cooperative_adapter_availability": cooperative_adapter_availability,
            "host": host_contract,
            "recovery": recovery,
            "host_event_summary": host_event_summary,
            "seat_runtime": seat_runtime,
            "browser_site_contract": browser_site_contract,
            "desktop_app_contract": desktop_app_contract,
            "host_twin": host_twin,
            "host_twin_summary": host_twin_summary_payload,
        },
        "continuity": continuity,
        "evidence_status": evidence_status,
        "blocked_reason": blocked_reason,
        "stuck_reason": stuck_reason,
        "owner_agent_id": getattr(task, "owner_agent_id", None),
        "owner_agent_name": owner_agent_name,
        "trigger_source": trigger.get("source"),
        "trigger_actor": trigger.get("actor"),
        "trigger_reason": trigger.get("reason"),
        "latest_result_summary": latest_result_summary,
        "latest_evidence_summary": latest_evidence_summary,
        "pending_decision_count": pending_decision_count,
        "evidence_count": len(evidence),
        "child_task_count": child_task_count,
        "child_terminal_count": child_terminal_count,
        "child_completion_rate": child_completion_rate,
        "summary_lines": summary_lines[:7],
        "next_step": next_actions[0] if next_actions else None,
        "next_actions": next_actions[:4],
        "risks": risks[:4],
        "task_route": task_route,
        "review_route": f"{task_route}/review",
    }


def extract_task_trigger(metadata: dict[str, Any] | None) -> dict[str, str | None]:
    payload = metadata.get("payload") if isinstance(metadata, dict) else None
    compiler = payload.get("compiler") if isinstance(payload, dict) else None
    task_seed = payload.get("task_seed") if isinstance(payload, dict) else None
    meta = payload.get("meta") if isinstance(payload, dict) else None
    return {
        "source": first_non_empty(
            compiler.get("trigger_source") if isinstance(compiler, dict) else None,
            task_seed.get("trigger_source") if isinstance(task_seed, dict) else None,
            meta.get("trigger_source") if isinstance(meta, dict) else None,
        ),
        "actor": first_non_empty(
            compiler.get("trigger_actor") if isinstance(compiler, dict) else None,
            task_seed.get("trigger_actor") if isinstance(task_seed, dict) else None,
            meta.get("trigger_actor") if isinstance(meta, dict) else None,
        ),
        "reason": first_non_empty(
            compiler.get("trigger_reason") if isinstance(compiler, dict) else None,
            task_seed.get("trigger_reason") if isinstance(task_seed, dict) else None,
            meta.get("trigger_reason") if isinstance(meta, dict) else None,
        ),
    }


def derive_review_execution_state(
    *,
    status: str,
    phase: str,
    pending_decision_count: int,
    latest_result_summary: str | None,
    latest_evidence_summary: str | None,
    latest_error_summary: str | None,
    updated_at: datetime | None,
) -> tuple[str, str | None, str | None]:
    detail_text = first_non_empty(
        latest_error_summary,
        latest_result_summary,
        latest_evidence_summary,
    )
    verification_markers = (
        "验证码",
        "短信",
        "2fa",
        "two-factor",
        "二次验证",
        "设备确认",
        "人工确认",
        "登录校验",
    )
    resource_markers = (
        "缺少",
        "missing",
        "没有权限",
        "permission",
        "credential",
        "凭证",
        "token",
    )

    if pending_decision_count:
        return "awaiting-decision", "pending-decision", None
    if status in {"blocked", "waiting-confirm"}:
        if matches_checkpoint_text(detail_text, verification_markers):
            return "awaiting-verification", "verification-gate", detail_text
        if matches_checkpoint_text(detail_text, resource_markers):
            return "awaiting-input", "missing-resource", detail_text
        return "blocked", "runtime-blocked", detail_text
    if status in {"failed", "cancelled"}:
        if matches_checkpoint_text(detail_text, verification_markers):
            return "awaiting-verification", "verification-gate", detail_text
        if matches_checkpoint_text(detail_text, resource_markers):
            return "awaiting-input", "missing-resource", detail_text
        return "failed", "runtime-error", detail_text
    if status in {"completed", "terminated"}:
        return "completed", None, None
    if phase in {"queued", "created"}:
        return "queued", None, None
    if status in {"running", "active"}:
        age_seconds = seconds_since(updated_at)
        if age_seconds is not None and age_seconds >= 900 and not detail_text:
            return "stalled", None, "runtime stale without fresh result summary"
        return "executing", None, None
    return "unknown", None, None


def seconds_since(value: datetime | None) -> int | None:
    if value is None:
        return None
    current = datetime.now(timezone.utc)
    target = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return int((current - target).total_seconds())


def matches_checkpoint_text(value: str | None, markers: tuple[str, ...]) -> bool:
    if value is None:
        return False
    lowered = value.strip().lower()
    return any(marker.lower() in lowered for marker in markers)


def extract_chat_thread_payload(metadata: dict[str, Any] | None) -> dict[str, str | None]:
    raw_payload = metadata.get("payload") if isinstance(metadata, dict) else None
    request = raw_payload.get("request_context") if isinstance(raw_payload, dict) else None
    compiler = raw_payload.get("compiler") if isinstance(raw_payload, dict) else None
    meta = raw_payload.get("meta") if isinstance(raw_payload, dict) else None
    return {
        "control_thread_id": first_non_empty(
            request.get("control_thread_id") if isinstance(request, dict) else None,
            compiler.get("control_thread_id") if isinstance(compiler, dict) else None,
            meta.get("control_thread_id") if isinstance(meta, dict) else None,
        ),
        "thread_id": first_non_empty(
            request.get("thread_id") if isinstance(request, dict) else None,
            request.get("session_id") if isinstance(request, dict) else None,
        ),
        "session_id": first_non_empty(
            request.get("session_id") if isinstance(request, dict) else None,
        ),
        "task_title": first_non_empty(
            raw_payload.get("task_title") if isinstance(raw_payload, dict) else None,
            raw_payload.get("title") if isinstance(raw_payload, dict) else None,
        ),
        "industry_instance_id": first_non_empty(request.get("industry_instance_id") if isinstance(request, dict) else None),
        "industry_label": first_non_empty(request.get("industry_label") if isinstance(request, dict) else None),
        "owner_scope": first_non_empty(request.get("owner_scope") if isinstance(request, dict) else None),
        "thread_mode": first_non_empty(
            request.get("thread_mode") if isinstance(request, dict) else None,
            request.get("task_mode") if isinstance(request, dict) else None,
        ),
        "decision_type": first_non_empty(raw_payload.get("decision_type") if isinstance(raw_payload, dict) else None),
        "session_kind": first_non_empty(
            request.get("session_kind") if isinstance(request, dict) else None,
        ),
    }


__all__ = [
    "build_task_review_payload",
    "count_pending_decisions",
    "derive_review_execution_state",
    "extract_chat_thread_payload",
    "extract_task_trigger",
    "first_non_empty",
    "latest_evidence_record",
    "matches_checkpoint_text",
    "seconds_since",
    "serialize_child_rollup",
    "serialize_evidence_record",
    "serialize_kernel_meta",
    "serialize_task_knowledge_context",
    "string_list_from_values",
    "task_phase_value",
    "task_status_value",
    "trace_id_from_kernel_meta",
    "trace_id_from_metadata",
]
