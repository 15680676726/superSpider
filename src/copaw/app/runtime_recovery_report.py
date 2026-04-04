# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _mapping(value: object | None) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    namespace = getattr(value, "__dict__", None)
    if isinstance(namespace, dict):
        return dict(namespace)
    return {}


def _list_automation_loop_payloads(
    *,
    automation_tasks: object | None = None,
    automation_loop_runtime_repository: object | None = None,
) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    if automation_loop_runtime_repository is not None:
        list_loops = getattr(automation_loop_runtime_repository, "list_loops", None)
        if callable(list_loops):
            try:
                for item in list_loops(limit=None):
                    payload = _mapping(item)
                    if payload:
                        payloads.append(payload)
            except Exception:
                payloads = []
    if payloads:
        return payloads
    loop_snapshots = getattr(automation_tasks, "loop_snapshots", None)
    if callable(loop_snapshots):
        try:
            raw = loop_snapshots()
        except Exception:
            raw = {}
        if isinstance(raw, dict):
            for payload in raw.values():
                normalized = _mapping(payload)
                if normalized:
                    payloads.append(normalized)
    return payloads


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _latest_report_from_environment_service(
    environment_service: object | None,
) -> dict[str, object] | None:
    getter = getattr(environment_service, "get_latest_recovery_report", None)
    if not callable(getter):
        return None
    try:
        payload = getter()
    except Exception:
        return None
    normalized = _mapping(payload)
    return normalized or None


def build_latest_recovery_report(
    *,
    startup_recovery_summary: object,
    automation_tasks: object | None = None,
    automation_loop_runtime_repository: object | None = None,
) -> dict[str, object]:
    payload = _mapping(startup_recovery_summary)
    loops = _list_automation_loop_payloads(
        automation_tasks=automation_tasks,
        automation_loop_runtime_repository=automation_loop_runtime_repository,
    )
    degraded_loop_count = sum(
        1
        for loop in loops
        if str(loop.get("health_status") or "").strip().lower() == "degraded"
        or str(loop.get("loop_phase") or "").strip().lower() in {"failed", "degraded"}
    )
    payload["source"] = "startup"
    payload["automation_loops"] = loops
    payload["automation_loop_count"] = len(loops)
    payload["degraded_loop_count"] = degraded_loop_count
    return payload


def build_runtime_host_recovery_report(
    *,
    host_recovery: object,
    actor: str | None = None,
    source: str | None = None,
    session_mount_id: str | None = None,
) -> dict[str, object]:
    payload = _mapping(host_recovery)
    executed = int(payload.get("executed") or 0)
    skipped = int(payload.get("skipped") or 0)
    failed = int(payload.get("failed") or 0)
    planned = int(payload.get("planned") or 0)
    decisions = _mapping(payload.get("decisions"))
    report = {
        "reason": "runtime-recovery",
        "source": "runtime",
        "latest_scope": "runtime",
        "producer": "host-recovery",
        "recovered_at": _utc_now_iso(),
        "executed": executed,
        "skipped": skipped,
        "failed": failed,
        "planned": planned,
        "last_seen_event_id": payload.get("last_seen_event_id"),
        "decisions": decisions,
        "actions": list(payload.get("actions") or []),
        "pending_decisions": 0,
        "hydrated_waiting_confirm_tasks": 0,
        "active_schedules": 0,
        "notes": [
            f"Host recovery processed {executed} actionable event(s).",
        ],
    }
    if actor:
        report["actor"] = actor
    if source:
        report["trigger_source"] = source
    if session_mount_id:
        report["session_mount_id"] = session_mount_id
    return report


def resolve_current_recovery_report(
    app_state: object,
) -> tuple[object | None, str | None]:
    environment_service = getattr(app_state, "environment_service", None)
    latest_from_environment = _latest_report_from_environment_service(environment_service)
    if latest_from_environment is not None:
        return latest_from_environment, "latest"
    latest_from_state = getattr(app_state, "latest_recovery_report", None)
    if latest_from_state is not None:
        return latest_from_state, "latest"
    startup_summary = getattr(app_state, "startup_recovery_summary", None)
    if startup_summary is not None:
        return startup_summary, "startup"
    return None, None
