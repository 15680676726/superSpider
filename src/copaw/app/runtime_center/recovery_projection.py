# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    return text or None


def _int(value: object | None, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _summary_payload(summary: object | None) -> dict[str, object]:
    if summary is None:
        return {}
    model_dump = getattr(summary, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, Mapping):
            return dict(payload)
    if isinstance(summary, Mapping):
        return dict(summary)
    return {"summary": str(summary)}


def _build_recovery_detail(payload: Mapping[str, object]) -> dict[str, object]:
    return {
        "leases": {
            "reaped_expired_leases": _int(payload.get("reaped_expired_leases")),
            "recovered_orphaned_leases": _int(payload.get("recovered_orphaned_leases")),
            "reaped_expired_actor_leases": _int(payload.get("reaped_expired_actor_leases")),
            "recovered_orphaned_actor_leases": _int(
                payload.get("recovered_orphaned_actor_leases"),
            ),
        },
        "mailbox": {
            "recovered_orphaned_mailbox_items": _int(
                payload.get("recovered_orphaned_mailbox_items"),
            ),
            "requeued_orphaned_mailbox_items": _int(
                payload.get("requeued_orphaned_mailbox_items"),
            ),
            "blocked_orphaned_mailbox_items": _int(
                payload.get("blocked_orphaned_mailbox_items"),
            ),
            "resolved_orphaned_mailbox_items": _int(
                payload.get("resolved_orphaned_mailbox_items"),
            ),
        },
        "decisions": {
            "expired_decisions": _int(payload.get("expired_decisions")),
            "pending_decisions": _int(payload.get("pending_decisions")),
            "hydrated_waiting_confirm_tasks": _int(
                payload.get("hydrated_waiting_confirm_tasks"),
            ),
        },
        "automation": {
            "active_schedules": _int(payload.get("active_schedules")),
        },
    }


def project_latest_recovery_summary(
    summary: object | None,
    *,
    source: str,
) -> dict[str, object]:
    payload = _summary_payload(summary)
    payload["source"] = _string(source) or "unknown"
    payload["detail"] = _build_recovery_detail(payload)
    if "notes" in payload:
        payload["notes"] = list(payload.get("notes") or [])
    return payload
