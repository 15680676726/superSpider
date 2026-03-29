# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
from typing import Any

from fastapi import HTTPException, Request

from ...kernel import KernelTask


def get_capability_service(request: Request) -> Any:
    service = getattr(request.app.state, "capability_service", None)
    if service is None or not callable(getattr(service, "get_capability", None)):
        raise HTTPException(503, detail="Capability service is not available")
    return service


def get_kernel_dispatcher(request: Request) -> Any:
    dispatcher = getattr(request.app.state, "kernel_dispatcher", None)
    if dispatcher is None:
        raise HTTPException(503, detail="Kernel dispatcher is not available")
    return dispatcher


def resolve_mutation_risk(
    service: Any,
    capability_id: str,
    *,
    fallback: str,
) -> str:
    mount = service.get_capability(capability_id)
    return mount.risk_level if mount is not None else fallback


def translate_dispatcher_error(exc: Exception) -> None:
    if isinstance(exc, KeyError):
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(409, detail=str(exc)) from exc
    if isinstance(exc, RuntimeError):
        raise HTTPException(503, detail=str(exc)) from exc
    raise exc


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def dispatch_governed_mutation(
    request: Request,
    *,
    capability_ref: str,
    title: str,
    payload: dict[str, object],
    environment_ref: str,
    fallback_risk: str = "guarded",
    risk_level_override: str | None = None,
) -> dict[str, object]:
    service = get_capability_service(request)
    dispatcher = get_kernel_dispatcher(request)
    task = KernelTask(
        title=title,
        capability_ref=capability_ref,
        environment_ref=environment_ref,
        owner_agent_id=str(
            payload.get("owner_agent_id")
            or payload.get("actor")
            or "copaw-operator"
        ),
        risk_level=(
            risk_level_override.strip()
            if isinstance(risk_level_override, str) and risk_level_override.strip()
            else resolve_mutation_risk(
                service,
                capability_ref,
                fallback=fallback_risk,
            )
        ),
        payload=payload,
    )
    try:
        admitted = dispatcher.submit(task)
    except Exception as exc:
        translate_dispatcher_error(exc)
    if admitted.phase != "executing":
        return admitted.model_dump(mode="json")
    try:
        executed = await _maybe_await(dispatcher.execute_task(task.id))
    except Exception as exc:
        translate_dispatcher_error(exc)
    return executed.model_dump(mode="json")
