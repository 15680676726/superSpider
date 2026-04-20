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


def _nested_field(payload: Mapping[str, Any], *keys: str) -> object | None:
    for key in keys:
        if key in payload:
            return payload.get(key)
    result = payload.get("result")
    if isinstance(result, Mapping):
        for key in keys:
            if key in result:
                return result.get(key)
    return None


def build_thread_start_request(
    *,
    assignment_id: str,
    project_root: str,
) -> tuple[str, dict[str, Any]]:
    return (
        "thread/start",
        {
            "cwd": project_root,
            "metadata": {
                "assignment_id": assignment_id,
            },
        },
    )


def build_turn_start_request(
    *,
    thread_id: str,
    prompt: str,
    assignment_id: str,
    project_root: str,
) -> tuple[str, dict[str, Any]]:
    return (
        "turn/start",
        {
            "thread_id": thread_id,
            "prompt": prompt,
            "cwd": project_root,
            "metadata": {
                "assignment_id": assignment_id,
            },
        },
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
            "thread_id": thread_id,
            "turn_id": turn_id,
            "prompt": prompt,
        },
    )


def build_turn_stop_request(
    *,
    thread_id: str,
    turn_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    payload: dict[str, Any] = {"thread_id": thread_id}
    if _string(turn_id) is not None:
        payload["turn_id"] = turn_id
    return ("turn/stop", payload)


def extract_thread_id(payload: Mapping[str, Any]) -> str | None:
    return _string(_nested_field(payload, "thread_id", "threadId"))


def extract_turn_id(payload: Mapping[str, Any]) -> str | None:
    return _string(_nested_field(payload, "turn_id", "turnId"))


def extract_model_ref(payload: Mapping[str, Any]) -> str | None:
    return _string(_nested_field(payload, "model", "model_ref", "modelRef"))


def extract_runtime_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _dict(_nested_field(payload, "runtime_metadata", "runtimeMetadata"))


def normalize_codex_event(message: Mapping[str, Any]) -> ExecutorNormalizedEvent | None:
    method = _string(message.get("method"))
    params = _dict(message.get("params"))
    if method is None:
        return None
    if method == "turn/plan/updated":
        return ExecutorNormalizedEvent(
            event_type="plan_submitted",
            source_type="plan",
            payload=params,
            raw_method=method,
        )
    if method == "turn/completed":
        return ExecutorNormalizedEvent(
            event_type="task_completed",
            source_type="turn",
            payload=params,
            raw_method=method,
        )
    if method == "turn/failed":
        return ExecutorNormalizedEvent(
            event_type="task_failed",
            source_type="turn",
            payload=params,
            raw_method=method,
        )
    if method in {"item/completed", "item/started"}:
        item = _dict(params.get("item"))
        item_type = _string(item.get("type"))
        if item_type in {"commandExecution", "fileChange", "mcpToolCall", "webSearch"}:
            return ExecutorNormalizedEvent(
                event_type="evidence_emitted",
                source_type=item_type,
                payload=item,
                raw_method=method,
            )
    return None
