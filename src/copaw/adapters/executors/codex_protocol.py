# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...kernel.executor_runtime_port import ExecutorNormalizedEvent


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dict(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _compact_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    compacted: dict[str, Any] = {}
    if not isinstance(value, Mapping):
        return compacted
    for key, item in value.items():
        if isinstance(item, Mapping):
            nested = _compact_mapping(item)
            if nested:
                compacted[key] = nested
            continue
        if isinstance(item, list):
            if item:
                compacted[key] = list(item)
            continue
        if item not in (None, ""):
            compacted[key] = item
    return compacted


def _copaw_contract_metadata(
    *,
    assignment_id: str,
    parent_runtime_id: str | None = None,
    continuity_metadata: dict[str, Any] | None = None,
    recovery_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    continuity = _compact_mapping(continuity_metadata)
    recovery = _compact_mapping(recovery_metadata)
    if _string(parent_runtime_id) is None and not continuity and not recovery:
        return {}
    contract = _compact_mapping(
        {
            "assignment_id": assignment_id,
            "parent_runtime_id": _string(parent_runtime_id),
            "continuity": continuity,
            "recovery": recovery,
        }
    )
    if not contract:
        return {}
    return {"metadata": {"copaw": contract}}


def _nested_lookup(
    payload: Mapping[str, Any],
    *paths: tuple[str, ...],
) -> object | None:
    for path in paths:
        current: object | None = payload
        for key in path:
            if not isinstance(current, Mapping) or key not in current:
                current = None
                break
            current = current.get(key)
        if current is not None:
            return current
    return None


def _text_input(prompt: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "text",
            "text": prompt,
            "text_elements": [],
        },
    ]


def _with_thread_context(
    *,
    payload: Mapping[str, Any],
    params: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = dict(payload)
    thread_id = _string(
        _nested_lookup(
            params,
            ("threadId",),
            ("thread_id",),
        ),
    )
    turn_id = _string(
        _nested_lookup(
            params,
            ("turnId",),
            ("turn_id",),
            ("turn", "id"),
            ("turn", "turnId"),
        ),
    )
    if thread_id is not None:
        normalized.setdefault("thread_id", thread_id)
    if turn_id is not None:
        normalized.setdefault("turn_id", turn_id)
    return normalized


def build_thread_start_request(
    *,
    assignment_id: str,
    project_root: str,
    model_ref: str | None = None,
    parent_runtime_id: str | None = None,
    continuity_metadata: dict[str, Any] | None = None,
    recovery_metadata: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    payload: dict[str, Any] = {
        "cwd": project_root,
    }
    resolved_model_ref = _string(model_ref)
    if resolved_model_ref is not None:
        payload["model"] = resolved_model_ref
    payload.update(
        _copaw_contract_metadata(
            assignment_id=assignment_id,
            parent_runtime_id=parent_runtime_id,
            continuity_metadata=continuity_metadata,
            recovery_metadata=recovery_metadata,
        )
    )
    return ("thread/start", payload)


def build_turn_start_request(
    *,
    thread_id: str,
    prompt: str,
    assignment_id: str,
    project_root: str,
    model_ref: str | None = None,
    parent_runtime_id: str | None = None,
    continuity_metadata: dict[str, Any] | None = None,
    recovery_metadata: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    payload: dict[str, Any] = {
        "threadId": thread_id,
        "input": _text_input(prompt),
        "cwd": project_root,
    }
    resolved_model_ref = _string(model_ref)
    if resolved_model_ref is not None:
        payload["model"] = resolved_model_ref
    payload.update(
        _copaw_contract_metadata(
            assignment_id=assignment_id,
            parent_runtime_id=parent_runtime_id,
            continuity_metadata=continuity_metadata,
            recovery_metadata=recovery_metadata,
        )
    )
    return (
        "turn/start",
        payload,
    )


def build_turn_steer_request(
    *,
    thread_id: str,
    turn_id: str,
    prompt: str,
) -> tuple[str, dict[str, Any]]:
    return (
        "turn/steer",
        {
            "threadId": thread_id,
            "expectedTurnId": turn_id,
            "input": _text_input(prompt),
        },
    )


def build_turn_stop_request(
    *,
    thread_id: str,
    turn_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    resolved_turn_id = _string(turn_id)
    if resolved_turn_id is None:
        raise ValueError("Codex App Server requires a turn id for turn/interrupt")
    return (
        "turn/interrupt",
        {
            "threadId": thread_id,
            "turnId": resolved_turn_id,
        },
    )


def extract_thread_id(payload: Mapping[str, Any]) -> str | None:
    return _string(
        _nested_lookup(
            payload,
            ("thread_id",),
            ("threadId",),
            ("result", "thread_id"),
            ("result", "threadId"),
            ("result", "thread", "id"),
            ("thread", "id"),
        ),
    )


def extract_turn_id(payload: Mapping[str, Any]) -> str | None:
    return _string(
        _nested_lookup(
            payload,
            ("turn_id",),
            ("turnId",),
            ("result", "turn_id"),
            ("result", "turnId"),
            ("result", "turn", "id"),
            ("turn", "id"),
        ),
    )


def extract_model_ref(payload: Mapping[str, Any]) -> str | None:
    return _string(
        _nested_lookup(
            payload,
            ("model",),
            ("model_ref",),
            ("modelRef",),
            ("result", "model"),
            ("result", "model_ref"),
            ("result", "modelRef"),
            ("result", "turn", "model"),
            ("turn", "model"),
        ),
    )


def extract_runtime_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _dict(
        _nested_lookup(
            payload,
            ("runtime_metadata",),
            ("runtimeMetadata",),
            ("result", "runtime_metadata"),
            ("result", "runtimeMetadata"),
        ),
    )


def normalize_codex_event(message: Mapping[str, Any]) -> ExecutorNormalizedEvent | None:
    method = _string(message.get("method"))
    params = _dict(message.get("params"))
    if method is None:
        return None
    if method == "turn/plan/updated":
        payload = _with_thread_context(payload=params, params=params)
        return ExecutorNormalizedEvent(
            event_type="plan_submitted",
            source_type="plan",
            payload=payload,
            raw_method=method,
        )
    if method == "turn/completed":
        turn = _dict(params.get("turn"))
        payload = _with_thread_context(payload=turn, params=params)
        status = _string(payload.get("status")) or "completed"
        payload["status"] = status
        event_type = "task_completed" if status == "completed" else "task_failed"
        return ExecutorNormalizedEvent(
            event_type=event_type,
            source_type="turn",
            payload=payload,
            raw_method=method,
        )
    if method == "turn/failed":
        payload = _with_thread_context(payload=params, params=params)
        return ExecutorNormalizedEvent(
            event_type="task_failed",
            source_type="turn",
            payload=payload,
            raw_method=method,
        )
    if method in {"item/completed", "item/started"}:
        item = _dict(params.get("item"))
        item_type = _string(item.get("type"))
        payload = _with_thread_context(payload=item, params=params)
        if item_type == "agentMessage":
            message_text = _string(payload.get("text")) or _string(payload.get("message"))
            if message_text is not None:
                payload.setdefault("message", message_text)
                payload.setdefault("summary", message_text)
            return ExecutorNormalizedEvent(
                event_type="message_emitted",
                source_type=item_type,
                payload=payload,
                raw_method=method,
            )
        if item_type in {"commandExecution", "fileChange", "mcpToolCall", "webSearch"}:
            return ExecutorNormalizedEvent(
                event_type="evidence_emitted",
                source_type=item_type,
                payload=payload,
                raw_method=method,
            )
    return None
