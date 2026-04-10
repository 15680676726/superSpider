# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect
import sys
import threading
from contextlib import contextmanager

from fastapi import HTTPException, Request

from ..runtime_center.state_query import RuntimeCenterReadModelUnavailableError
from .governed_mutations import dispatch_governed_mutation, translate_dispatcher_error


async def _call_runtime_query_method(
    target: object,
    *method_names: str,
    not_available_detail: str,
    **kwargs,
):
    for method_name in method_names:
        method = getattr(target, method_name, None)
        if not callable(method):
            continue
        try:
            result = method(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            return result
        except RuntimeCenterReadModelUnavailableError as exc:
            raise HTTPException(503, detail=not_available_detail) from exc
    raise HTTPException(503, detail=not_available_detail)


def _raise_dispatcher_error(exc: Exception) -> None:
    translate_dispatcher_error(exc)


def _get_runtime_center_facade_attr(name: str, default: object) -> object:
    facade = sys.modules.get("copaw.app.routers.runtime_center")
    if facade is None:
        return default
    return getattr(facade, name, default)


def _runtime_operator_guard_key(*parts: str) -> str:
    return ":".join(part.strip() for part in parts if isinstance(part, str) and part.strip())


def _get_runtime_operator_frontdoor_guard_state(request: Request) -> dict[str, object]:
    state = getattr(request.app.state, "runtime_center_operator_frontdoor_guard", None)
    if not isinstance(state, dict):
        state = {}
        setattr(request.app.state, "runtime_center_operator_frontdoor_guard", state)
    lock = state.get("lock")
    if not callable(getattr(lock, "acquire", None)) or not callable(getattr(lock, "release", None)):
        lock = threading.Lock()
        state["lock"] = lock
    inflight = state.get("inflight")
    if isinstance(inflight, set):
        return state
    if isinstance(inflight, (list, tuple, frozenset)):
        state["inflight"] = {str(item) for item in inflight}
    else:
        state["inflight"] = set()
    return state


@contextmanager
def _runtime_operator_reentry_guard(
    request: Request,
    *,
    guard_key: str,
    conflict_detail: str,
):
    state = _get_runtime_operator_frontdoor_guard_state(request)
    lock = state["lock"]
    inflight = state["inflight"]
    with lock:
        if guard_key in inflight:
            raise HTTPException(409, detail=conflict_detail)
        inflight.add(guard_key)
    try:
        yield
    finally:
        with lock:
            inflight.discard(guard_key)


async def _dispatch_runtime_mutation(
    request: Request,
    *,
    capability_ref: str,
    title: str,
    payload: dict[str, object],
    fallback_risk: str = "guarded",
    risk_level_override: str | None = None,
) -> dict[str, object]:
    return await dispatch_governed_mutation(
        request,
        capability_ref=capability_ref,
        title=title,
        payload=payload,
        environment_ref="config:runtime",
        fallback_risk=fallback_risk,
        risk_level_override=risk_level_override,
    )


__all__ = [name for name in globals() if not name.startswith("__")]
