# -*- coding: utf-8 -*-
"""Shared decision policy helpers for kernel governance."""
from __future__ import annotations

from urllib.parse import quote
from typing import Any

MAIN_BRAIN_DECISION_ACTOR = "copaw-main-brain"

_HUMAN_REQUIRED_DECISION_TYPES = frozenset({"query-tool-confirmation"})
_CHAT_THREAD_PREFIXES = ("industry-chat:", "agent-chat:")


def decision_requested_by(task: Any) -> str:
    payload = _mapping(getattr(task, "payload", None))
    explicit = _string(
        payload.get("decision_requested_by"),
        payload.get("requested_by"),
    )
    if explicit is not None:
        return explicit
    if task_requires_human_confirmation(task) or task_is_main_brain_auto_approvable(task):
        return MAIN_BRAIN_DECISION_ACTOR
    return _string(getattr(task, "owner_agent_id", None)) or MAIN_BRAIN_DECISION_ACTOR


def task_requires_human_confirmation(task: Any) -> bool:
    payload = _mapping(getattr(task, "payload", None))
    return decision_requires_human_confirmation(
        decision_type=payload.get("decision_type"),
        payload=payload,
    )


def decision_requires_human_confirmation(
    *,
    decision_type: object | None = None,
    payload: dict[str, object] | None = None,
) -> bool:
    normalized_payload = _mapping(payload)
    normalized_type = _normalized_token(
        decision_type,
        normalized_payload.get("decision_type"),
    )
    if normalized_type in _HUMAN_REQUIRED_DECISION_TYPES:
        return True
    return _truthy(
        normalized_payload.get("human_confirmation_required"),
        normalized_payload.get("require_human_confirmation"),
    )


def task_is_main_brain_auto_approvable(task: Any) -> bool:
    payload = _mapping(getattr(task, "payload", None))
    if decision_requires_human_confirmation(
        decision_type=payload.get("decision_type"),
        payload=payload,
    ):
        return False
    if _truthy(
        payload.get("disable_main_brain_auto_adjudicate"),
        payload.get("disable_main_brain_auto_approval"),
    ):
        return False
    if _truthy(
        payload.get("main_brain_auto_adjudicate"),
        payload.get("main_brain_auto_approve"),
    ):
        return True
    capability_ref = _string(getattr(task, "capability_ref", None))
    if capability_ref is None or not capability_ref.startswith("system:"):
        return False
    return True


def decision_chat_thread_id(*sources: object) -> str | None:
    candidates: list[dict[str, object]] = []
    for source in sources:
        mapping = _mapping(source)
        if mapping:
            candidates.append(mapping)
            request_context = _mapping(mapping.get("request_context"))
            if request_context:
                candidates.append(request_context)
            meta = _mapping(mapping.get("meta"))
            if meta:
                candidates.append(meta)
            request = _mapping(mapping.get("request"))
            if request:
                candidates.append(request)
    for candidate in candidates:
        for key in ("control_thread_id", "thread_id", "session_id"):
            value = _string(candidate.get(key))
            if value is None:
                continue
            if value.startswith(_CHAT_THREAD_PREFIXES):
                return value
    return None


def decision_chat_route(thread_id: str | None) -> str | None:
    normalized = _string(thread_id)
    if normalized is None:
        return None
    return f"/chat?threadId={quote(normalized, safe='')}"


def _mapping(value: object | None) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _string(*values: object | None) -> str | None:
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if normalized:
            return normalized
    return None


def _normalized_token(*values: object | None) -> str | None:
    value = _string(*values)
    if value is None:
        return None
    return value.lower()


def _truthy(*values: object | None) -> bool:
    for value in values:
        if isinstance(value, bool):
            if value:
                return True
            continue
        if isinstance(value, str) and value.strip().lower() in {"1", "true", "yes", "on"}:
            return True
    return False


__all__ = [
    "MAIN_BRAIN_DECISION_ACTOR",
    "decision_chat_route",
    "decision_chat_thread_id",
    "decision_requested_by",
    "decision_requires_human_confirmation",
    "task_is_main_brain_auto_approvable",
    "task_requires_human_confirmation",
]
