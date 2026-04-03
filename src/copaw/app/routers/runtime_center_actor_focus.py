# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import logging

from fastapi import Request

from .runtime_center_payloads import _runtime_non_empty_str

logger = logging.getLogger(__name__)

_ACTIVE_ACTOR_MAILBOX_STATUSES = frozenset(
    {"queued", "leased", "running", "blocked", "retry-wait"},
)
_ACTIVE_ACTOR_CHECKPOINT_STATUSES = frozenset({"ready"})


def _resolve_actor_focus_task_id(
    runtime: object,
    *,
    mailbox_items: list[object],
    checkpoints: list[object],
) -> str | None:
    current_task_id = _runtime_non_empty_str(getattr(runtime, "current_task_id", None))
    if current_task_id is not None:
        return current_task_id

    current_mailbox_id = _runtime_non_empty_str(getattr(runtime, "current_mailbox_id", None))
    for item in mailbox_items:
        status = _runtime_non_empty_str(getattr(item, "status", None))
        task_id = _runtime_non_empty_str(getattr(item, "task_id", None))
        item_id = _runtime_non_empty_str(getattr(item, "id", None))
        if (
            current_mailbox_id is not None
            and item_id == current_mailbox_id
            and status in _ACTIVE_ACTOR_MAILBOX_STATUSES
            and task_id is not None
        ):
            return task_id

    for item in mailbox_items:
        status = _runtime_non_empty_str(getattr(item, "status", None))
        task_id = _runtime_non_empty_str(getattr(item, "task_id", None))
        if status in _ACTIVE_ACTOR_MAILBOX_STATUSES and task_id is not None:
            return task_id

    current_checkpoint_id = _runtime_non_empty_str(getattr(runtime, "last_checkpoint_id", None))
    for checkpoint in checkpoints:
        status = _runtime_non_empty_str(getattr(checkpoint, "status", None))
        task_id = _runtime_non_empty_str(getattr(checkpoint, "task_id", None))
        checkpoint_id = _runtime_non_empty_str(getattr(checkpoint, "id", None))
        if (
            current_checkpoint_id is not None
            and checkpoint_id == current_checkpoint_id
            and status in _ACTIVE_ACTOR_CHECKPOINT_STATUSES
            and task_id is not None
        ):
            return task_id

    for checkpoint in checkpoints:
        status = _runtime_non_empty_str(getattr(checkpoint, "status", None))
        task_id = _runtime_non_empty_str(getattr(checkpoint, "task_id", None))
        if status in _ACTIVE_ACTOR_CHECKPOINT_STATUSES and task_id is not None:
            return task_id
    return None


async def _get_actor_focus_payload(
    request: Request,
    *,
    runtime: object,
    mailbox_items: list[object],
    checkpoints: list[object],
) -> dict[str, object] | None:
    task_id = _resolve_actor_focus_task_id(
        runtime,
        mailbox_items=mailbox_items,
        checkpoints=checkpoints,
    )
    if task_id is None:
        return None
    payload: dict[str, object] = {
        "task_id": task_id,
        "route": f"/api/runtime-center/tasks/{task_id}/review",
        "review": None,
    }
    state_query = getattr(request.app.state, "state_query_service", None)
    getter = getattr(state_query, "get_task_review", None)
    if not callable(getter):
        return payload
    try:
        result = getter(task_id)
        if inspect.isawaitable(result):
            result = await result
    except Exception:
        logger.exception("Failed to resolve actor focus review for '%s'", task_id)
        return payload
    if not isinstance(result, dict):
        return payload
    review = result.get("review")
    if isinstance(review, dict):
        payload["review"] = review
    route = _runtime_non_empty_str(result.get("route"))
    if route is not None:
        payload["route"] = route
    return payload


__all__ = [
    "_ACTIVE_ACTOR_CHECKPOINT_STATUSES",
    "_ACTIVE_ACTOR_MAILBOX_STATUSES",
    "_get_actor_focus_payload",
    "_resolve_actor_focus_task_id",
]
