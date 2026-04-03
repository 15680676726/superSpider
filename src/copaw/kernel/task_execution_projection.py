# -*- coding: utf-8 -*-
"""Shared task execution projection helpers without introducing new vocabulary."""
from __future__ import annotations

from typing import Any

_VISIBLE_EXECUTION_PHASES = frozenset(
    {
        "queued",
        "claimed",
        "executing",
        "waiting-confirm",
        "completed",
        "failed",
        "cancelled",
    },
)

_MAILBOX_STATUS_TO_PHASE = {
    "queued": "queued",
    "retry-wait": "queued",
    "leased": "claimed",
    "running": "executing",
    "blocked": "waiting-confirm",
    "completed": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
}

_TASK_STATUS_TO_PHASE = {
    "created": "queued",
    "queued": "queued",
    "running": "executing",
    "waiting": "waiting-confirm",
    "blocked": "waiting-confirm",
    "needs-confirm": "waiting-confirm",
    "completed": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
}

_RUNTIME_PHASE_TO_VISIBLE_PHASE = {
    "pending": "queued",
    "risk-check": "queued",
    "queued": "queued",
    "claimed": "claimed",
    "executing": "executing",
    "waiting-confirm": "waiting-confirm",
    "blocked": "waiting-confirm",
    "completed": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
}

_RUNTIME_STATUS_TO_PHASE = {
    "cold": None,
    "hydrating": "queued",
    "active": "executing",
    "waiting-input": "waiting-confirm",
    "waiting-env": "waiting-confirm",
    "waiting-confirm": "waiting-confirm",
    "blocked": "waiting-confirm",
    "terminated": None,
}


def _non_empty_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _first_text(*values: object | None) -> str | None:
    for value in values:
        resolved = _non_empty_text(value)
        if resolved is not None:
            return resolved
    return None


def resolve_visible_execution_phase(
    *,
    runtime_phase: str | None = None,
    runtime_status: str | None = None,
    mailbox_status: str | None = None,
    task_status: str | None = None,
    admitted_phase: str | None = None,
) -> str | None:
    normalized_runtime_status = _non_empty_text(runtime_status) or ""
    for candidate in (
        _RUNTIME_PHASE_TO_VISIBLE_PHASE.get(_non_empty_text(runtime_phase) or ""),
        _MAILBOX_STATUS_TO_PHASE.get(_non_empty_text(mailbox_status) or ""),
        _RUNTIME_STATUS_TO_PHASE.get(_non_empty_text(runtime_status) or ""),
        _RUNTIME_PHASE_TO_VISIBLE_PHASE.get(_non_empty_text(admitted_phase) or ""),
    ):
        if candidate in _VISIBLE_EXECUTION_PHASES:
            return candidate
    if normalized_runtime_status in {"cold", "terminated"}:
        return None
    for candidate in (
        _TASK_STATUS_TO_PHASE.get(_non_empty_text(task_status) or ""),
    ):
        if candidate in _VISIBLE_EXECUTION_PHASES:
            return candidate
    return None


def is_visible_execution_inflight(phase: str | None) -> bool:
    return _non_empty_text(phase) in {
        "queued",
        "claimed",
        "executing",
        "waiting-confirm",
    }


def is_visible_execution_terminal(phase: str | None) -> bool:
    return _non_empty_text(phase) in {"completed", "failed", "cancelled"}


def build_child_run_resume_payload(
    *,
    mailbox_item: object,
    task_id: str | None,
    phase: str,
    extra_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    metadata = _mapping(getattr(mailbox_item, "metadata", None))
    payload = _mapping(getattr(mailbox_item, "payload", None))
    nested_payload = _mapping(payload.get("payload"))
    payload_meta = _mapping(payload.get("meta")) or _mapping(nested_payload.get("meta"))
    request_context = (
        _mapping(payload.get("request_context"))
        or _mapping(nested_payload.get("request_context"))
        or _mapping(payload.get("dispatch_request"))
        or _mapping(nested_payload.get("dispatch_request"))
        or _mapping(payload.get("request"))
        or _mapping(nested_payload.get("request"))
    )
    result: dict[str, object] = {
        "mailbox_id": str(getattr(mailbox_item, "id", "") or ""),
        "task_id": task_id,
        "phase": phase,
        "agent_id": str(getattr(mailbox_item, "agent_id", "") or ""),
    }
    optional_fields = {
        "source_agent_id": _first_text(getattr(mailbox_item, "source_agent_id", None)),
        "capability_ref": _first_text(getattr(mailbox_item, "capability_ref", None)),
        "work_context_id": _first_text(
            getattr(mailbox_item, "work_context_id", None),
            metadata.get("work_context_id"),
            request_context.get("work_context_id"),
        ),
        "conversation_thread_id": _first_text(
            getattr(mailbox_item, "conversation_thread_id", None),
            metadata.get("conversation_thread_id"),
        ),
        "session_id": _first_text(
            metadata.get("session_id"),
            request_context.get("session_id"),
        ),
        "control_thread_id": _first_text(
            metadata.get("control_thread_id"),
            request_context.get("control_thread_id"),
            request_context.get("context_key"),
        ),
        "assignment_id": _first_text(
            metadata.get("assignment_id"),
            payload.get("assignment_id"),
            nested_payload.get("assignment_id"),
            payload_meta.get("assignment_id"),
        ),
        "lane_id": _first_text(
            metadata.get("lane_id"),
            payload.get("lane_id"),
            nested_payload.get("lane_id"),
            payload_meta.get("lane_id"),
        ),
        "cycle_id": _first_text(
            metadata.get("cycle_id"),
            payload.get("cycle_id"),
            nested_payload.get("cycle_id"),
            payload_meta.get("cycle_id"),
        ),
        "report_back_mode": _first_text(
            metadata.get("report_back_mode"),
            payload.get("report_back_mode"),
            nested_payload.get("report_back_mode"),
            payload_meta.get("report_back_mode"),
        ),
        "parent_task_id": _first_text(metadata.get("parent_task_id")),
        "environment_ref": _first_text(
            metadata.get("environment_ref"),
            payload.get("environment_ref"),
            nested_payload.get("environment_ref"),
            payload_meta.get("environment_ref"),
        ),
        "industry_instance_id": _first_text(metadata.get("industry_instance_id")),
        "industry_role_id": _first_text(metadata.get("industry_role_id")),
        "execution_source": _first_text(metadata.get("execution_source")),
        "access_mode": _first_text(metadata.get("access_mode")),
        "lease_class": _first_text(metadata.get("lease_class")),
        "writer_lock_scope": _first_text(metadata.get("writer_lock_scope")),
    }
    result.update(
        {
            key: value
            for key, value in optional_fields.items()
            if value is not None
        },
    )
    if isinstance(extra_payload, dict):
        result.update(
            {
                key: value
                for key, value in extra_payload.items()
                if value is not None
            },
        )
    return result
