# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any

_QUERY_CHECKPOINT_HISTORY_LIMIT = 20
_CHILD_REPORTBACK_HISTORY_LIMIT = 20


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if normalized:
            return normalized
    return None


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def _compact_mapping(value: Any) -> dict[str, Any]:
    payload = _mapping(value)
    return {
        key: item
        for key, item in payload.items()
        if item is not None and item != "" and item != []
    }


def _projection_identity(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def normalize_query_checkpoint_projection(value: Any) -> dict[str, Any]:
    payload = _mapping(value)
    if not payload:
        return {}
    projection = {
        "id": _first_non_empty(payload.get("id")),
        "agent_id": _first_non_empty(payload.get("agent_id")),
        "task_id": _first_non_empty(payload.get("task_id")),
        "work_context_id": _first_non_empty(payload.get("work_context_id")),
        "checkpoint_kind": _first_non_empty(payload.get("checkpoint_kind")),
        "status": _first_non_empty(payload.get("status")),
        "phase": _first_non_empty(payload.get("phase")),
        "cursor": _first_non_empty(payload.get("cursor")),
        "conversation_thread_id": _first_non_empty(payload.get("conversation_thread_id")),
        "environment_ref": _first_non_empty(payload.get("environment_ref")),
        "summary": _first_non_empty(payload.get("summary")),
        "updated_at": _first_non_empty(payload.get("updated_at")),
        "resume_payload": _compact_mapping(payload.get("resume_payload")),
        "snapshot_payload": _compact_mapping(payload.get("snapshot_payload")),
    }
    return {
        key: item
        for key, item in projection.items()
        if item is not None and item != "" and item != []
    }


def normalize_child_reportback_projection(value: Any) -> dict[str, Any]:
    payload = _mapping(value)
    if not payload:
        return {}
    projection = {
        "task_id": _first_non_empty(payload.get("task_id")),
        "parent_task_id": _first_non_empty(payload.get("parent_task_id")),
        "phase": _first_non_empty(payload.get("phase")),
        "report_back_mode": _first_non_empty(payload.get("report_back_mode")),
        "control_thread_id": _first_non_empty(payload.get("control_thread_id")),
        "session_id": _first_non_empty(payload.get("session_id")),
        "work_context_id": _first_non_empty(payload.get("work_context_id")),
        "status": _first_non_empty(payload.get("status")),
        "summary": _first_non_empty(payload.get("summary")),
        "updated_at": _first_non_empty(payload.get("updated_at")),
    }
    return {
        key: item
        for key, item in projection.items()
        if item is not None and item != "" and item != []
    }


def list_runtime_query_checkpoint_projections(*metadata_sources: Any) -> list[dict[str, Any]]:
    projections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for metadata in metadata_sources:
        payload = _mapping(metadata)
        candidates = [payload.get("last_query_checkpoint"), *(payload.get("query_checkpoint_history") or [])]
        for candidate in candidates:
            normalized = normalize_query_checkpoint_projection(candidate)
            if not normalized:
                continue
            identity = _projection_identity(normalized)
            if identity in seen:
                continue
            seen.add(identity)
            projections.append(normalized)
    projections.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return projections


def list_runtime_child_reportback_projections(*metadata_sources: Any) -> list[dict[str, Any]]:
    projections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for metadata in metadata_sources:
        payload = _mapping(metadata)
        for candidate in payload.get("query_child_reportbacks") or []:
            normalized = normalize_child_reportback_projection(candidate)
            if not normalized:
                continue
            identity = _projection_identity(normalized)
            if identity in seen:
                continue
            seen.add(identity)
            projections.append(normalized)
    projections.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return projections


def merge_runtime_metadata_with_query_checkpoint(
    metadata: Any,
    checkpoint_projection: Any,
) -> dict[str, Any]:
    payload = _mapping(metadata)
    normalized = normalize_query_checkpoint_projection(checkpoint_projection)
    if not normalized:
        return payload
    history = list_runtime_query_checkpoint_projections(payload)
    normalized_id = _first_non_empty(normalized.get("id"))
    history = [
        item
        for item in history
        if normalized_id is None or _first_non_empty(item.get("id")) != normalized_id
    ]
    history.insert(0, normalized)
    payload["last_query_checkpoint"] = dict(normalized)
    payload["query_checkpoint_history"] = history[:_QUERY_CHECKPOINT_HISTORY_LIMIT]
    if normalized_id is not None:
        payload["last_query_checkpoint_id"] = normalized_id
    return payload


def merge_runtime_metadata_with_child_reportback(
    metadata: Any,
    child_reportback_projection: Any,
) -> dict[str, Any]:
    payload = _mapping(metadata)
    normalized = normalize_child_reportback_projection(child_reportback_projection)
    if not normalized:
        return payload
    history = list_runtime_child_reportback_projections(payload)
    normalized_task_id = _first_non_empty(normalized.get("task_id"))
    normalized_parent_task_id = _first_non_empty(normalized.get("parent_task_id"))
    history = [
        item
        for item in history
        if not (
            normalized_task_id is not None
            and normalized_parent_task_id is not None
            and _first_non_empty(item.get("task_id")) == normalized_task_id
            and _first_non_empty(item.get("parent_task_id")) == normalized_parent_task_id
        )
    ]
    history.insert(0, normalized)
    payload["query_child_reportbacks"] = history[:_CHILD_REPORTBACK_HISTORY_LIMIT]
    return payload


__all__ = [
    "list_runtime_child_reportback_projections",
    "list_runtime_query_checkpoint_projections",
    "merge_runtime_metadata_with_child_reportback",
    "merge_runtime_metadata_with_query_checkpoint",
    "normalize_child_reportback_projection",
    "normalize_query_checkpoint_projection",
]
