# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import json
from typing import Any

from .models import KernelResult, KernelTask


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _stable_payload_signature(payload: dict[str, object]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        return repr(sorted(payload.items(), key=lambda item: str(item[0])))


def resolve_mutation_risk(
    capability_service: Any,
    capability_id: str,
    *,
    fallback: str,
) -> str:
    mount = capability_service.get_capability(capability_id)
    return mount.risk_level if mount is not None else fallback


def find_inflight_governed_mutation_result(
    kernel_dispatcher: Any,
    *,
    capability_ref: str,
    owner_agent_id: str,
    payload: dict[str, object],
) -> KernelResult | None:
    task_store = getattr(kernel_dispatcher, "task_store", None)
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
                    summary="等价的运行时变更仍在等待确认。",
                    decision_request_id=decision_request_id,
                )
            return KernelResult(
                task_id=task.id,
                trace_id=getattr(task, "trace_id", None),
                success=True,
                phase="executing",
                summary="等价的运行时变更已经在执行中。",
                decision_request_id=decision_request_id,
            )
    return None


async def dispatch_governed_mutation_runtime(
    *,
    capability_service: Any,
    kernel_dispatcher: Any,
    capability_ref: str,
    title: str,
    payload: dict[str, object],
    environment_ref: str,
    fallback_risk: str = "guarded",
    risk_level_override: str | None = None,
) -> dict[str, object]:
    owner_agent_id = str(
        payload.get("owner_agent_id")
        or payload.get("actor")
        or "copaw-operator"
    )
    inflight = find_inflight_governed_mutation_result(
        kernel_dispatcher,
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
                capability_service,
                capability_ref,
                fallback=fallback_risk,
            )
        ),
        payload=payload,
    )
    admitted = kernel_dispatcher.submit(task)
    if admitted.phase != "executing":
        return admitted.model_dump(mode="json")
    executed = await _maybe_await(kernel_dispatcher.execute_task(task.id))
    return executed.model_dump(mode="json")
