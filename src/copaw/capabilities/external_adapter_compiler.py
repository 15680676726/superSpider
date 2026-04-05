# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .external_adapter_contracts import (
    CompiledAdapterAction,
    CompiledAdapterContract,
    ExternalProtocolSurface,
)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dict(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _normalize_action_id(
    item: Mapping[str, Any],
) -> str | None:
    for key in ("action_id", "name", "tool_name", "operation_id", "callable_name"):
        value = _string(item.get(key))
        if value is not None:
            return value
    return None


def _normalize_transport_action_ref(
    item: Mapping[str, Any],
    *,
    transport_kind: str,
    action_id: str,
) -> str:
    if transport_kind == "mcp":
        return _string(item.get("tool_name")) or action_id
    if transport_kind == "http":
        method = _string(item.get("method")) or "POST"
        path = _string(item.get("path")) or _string(item.get("operation_id")) or action_id
        return f"{method.upper()} {path}"
    if transport_kind == "sdk":
        return (
            _string(item.get("callable_ref"))
            or _string(item.get("callable_name"))
            or action_id
        )
    return action_id


def compile_external_adapter_contract(
    *,
    capability_id: str,
    surface: ExternalProtocolSurface,
) -> CompiledAdapterContract | None:
    if not surface.formal_adapter_eligible or surface.transport_kind is None:
        return None
    actions_payload = surface.hints.get("actions")
    if not isinstance(actions_payload, list) or not actions_payload:
        return None
    actions: list[CompiledAdapterAction] = []
    for item in actions_payload:
        if not isinstance(item, Mapping):
            continue
        action_id = _normalize_action_id(item)
        if action_id is None:
            continue
        actions.append(
            CompiledAdapterAction(
                action_id=action_id,
                summary=_string(item.get("summary")) or "",
                input_schema=_dict(item.get("input_schema")),
                output_schema=_dict(item.get("output_schema")),
                transport_action_ref=_normalize_transport_action_ref(
                    item,
                    transport_kind=surface.transport_kind,
                    action_id=action_id,
                ),
            ),
        )
    if not actions:
        return None
    return CompiledAdapterContract(
        compiled_adapter_id=capability_id,
        transport_kind=surface.transport_kind,
        call_surface_ref=surface.call_surface_ref or capability_id,
        actions=actions,
        promotion_blockers=list(surface.blockers),
    )


__all__ = ["compile_external_adapter_contract"]
