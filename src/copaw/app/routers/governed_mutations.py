# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from ...kernel.governed_mutation_dispatch import (
    dispatch_governed_mutation_runtime,
)


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


def translate_dispatcher_error(exc: Exception) -> None:
    if isinstance(exc, KeyError):
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(409, detail=str(exc)) from exc
    if isinstance(exc, RuntimeError):
        raise HTTPException(503, detail=str(exc)) from exc
    raise exc


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
    try:
        return await dispatch_governed_mutation_runtime(
            capability_service=service,
            kernel_dispatcher=dispatcher,
            capability_ref=capability_ref,
            title=title,
            payload=payload,
            environment_ref=environment_ref,
            fallback_risk=fallback_risk,
            risk_level_override=risk_level_override,
        )
    except Exception as exc:
        translate_dispatcher_error(exc)
