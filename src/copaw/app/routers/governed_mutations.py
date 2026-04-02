# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import json
from typing import Any

from fastapi import HTTPException, Request

from ...kernel import KernelResult, KernelTask


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


def _stable_payload_signature(payload: dict[str, object]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        return repr(sorted(payload.items(), key=lambda item: str(item[0])))


def _find_inflight_mutation_result(
    dispatcher: Any,
    *,
    capability_ref: str,
    owner_agent_id: str,
    payload: dict[str, object],
) -> KernelResult | None:
    task_store = getattr(dispatcher, "task_store", None)
    if task_store is None or not callable(getattr(task_store, "list_tasks", None)):
        return None
    payload_signature = _stable_payload_signature(payload)
    for phase in ("executing", "waiting-confirm", "risk-check"):
        tasks = task_store.list_tasks(
            phase=phase,
            owner_agent_id=owner_agent_id,
        )
        for task in tasks:
            if getattr(task, "capability_ref", None) != capability_ref:
                continue
            task_payload = task.payload if isinstance(task.payload, dict) else {}
            if _stable_payload_signature(task_payload) != payload_signature:
                continue
            decision_request_id = None
            if callable(getattr(task_store, "list_decision_requests", None)):
                for decision in task_store.list_decision_requests(task_id=task.id):
                    if getattr(decision, "status", None) in {"open", "reviewing"}:
                        decision_request_id = getattr(decision, "id", None)
                        break
            if phase == "waiting-confirm":
                return KernelResult(
                    task_id=task.id,
                    trace_id=getattr(task, "trace_id", None),
                    success=False,
                    phase="waiting-confirm",
                    summary="Equivalent runtime mutation already awaits confirmation.",
                    decision_request_id=decision_request_id,
                )
            return KernelResult(
                task_id=task.id,
                trace_id=getattr(task, "trace_id", None),
                success=True,
                phase="executing",
                summary="Equivalent runtime mutation already in progress.",
                decision_request_id=decision_request_id,
            )
    return None


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
    owner_agent_id = str(
        payload.get("owner_agent_id")
        or payload.get("actor")
        or "copaw-operator"
    )
    inflight = _find_inflight_mutation_result(
        dispatcher,
        capability_ref=capability_ref,
        owner_agent_id=owner_agent_id,
        payload=payload,
    )
    if inflight is not None:
        return inflight.model_dump(mode="json")
    task = KernelTask(
        title=title,
        capability_ref=capability_ref,
        environment_ref=environment_ref,
        owner_agent_id=owner_agent_id,
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
