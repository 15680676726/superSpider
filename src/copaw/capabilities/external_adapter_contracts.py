# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field

ProtocolSurfaceKind = Literal[
    "native_mcp",
    "api",
    "sdk",
    "cli_runtime",
    "unknown",
]
TransportKind = Literal["mcp", "http", "sdk"]


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(values: object | None) -> list[str]:
    if isinstance(values, str):
        items: Sequence[object] = [values]
    elif isinstance(values, Sequence):
        items = values
    else:
        items = []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _string(item)
        if text is None:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return normalized


class ExternalProtocolSurface(BaseModel):
    protocol_surface_kind: ProtocolSurfaceKind = "unknown"
    transport_kind: TransportKind | None = None
    call_surface_ref: str | None = None
    schema_ref: str | None = None
    formal_adapter_eligible: bool = False
    blockers: list[str] = Field(default_factory=list)
    hints: dict[str, Any] = Field(default_factory=dict)


class CompiledAdapterAction(BaseModel):
    action_id: str
    summary: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    transport_action_ref: str


class CompiledAdapterContract(BaseModel):
    compiled_adapter_id: str
    transport_kind: TransportKind
    call_surface_ref: str
    actions: list[CompiledAdapterAction] = Field(default_factory=list)
    promotion_blockers: list[str] = Field(default_factory=list)


def classify_external_protocol_surface(
    *,
    metadata: Mapping[str, Any] | None,
) -> ExternalProtocolSurface:
    payload = dict(metadata or {})
    mcp_server_ref = _string(payload.get("mcp_server_ref"))
    mcp_tools = payload.get("mcp_tools")
    if mcp_server_ref is not None and isinstance(mcp_tools, list) and mcp_tools:
        return ExternalProtocolSurface(
            protocol_surface_kind="native_mcp",
            transport_kind="mcp",
            call_surface_ref=mcp_server_ref,
            formal_adapter_eligible=True,
            hints={"actions": list(mcp_tools)},
        )

    api_base_url = _string(payload.get("api_base_url")) or _string(
        payload.get("openapi_url"),
    )
    api_actions = payload.get("api_actions") or payload.get("openapi_actions")
    if api_base_url is not None:
        blockers: list[str] = []
        eligible = isinstance(api_actions, list) and bool(api_actions)
        if not eligible:
            blockers.append("no-typed-action-surface")
        return ExternalProtocolSurface(
            protocol_surface_kind="api",
            transport_kind="http",
            call_surface_ref=api_base_url,
            schema_ref=_string(payload.get("openapi_url")),
            formal_adapter_eligible=eligible,
            blockers=blockers,
            hints={"actions": list(api_actions or [])},
        )

    sdk_entry_ref = _string(payload.get("sdk_entry_ref"))
    sdk_actions = payload.get("sdk_actions")
    if sdk_entry_ref is not None:
        blockers = []
        eligible = isinstance(sdk_actions, list) and bool(sdk_actions)
        if not eligible:
            blockers.append("no-typed-action-surface")
        return ExternalProtocolSurface(
            protocol_surface_kind="sdk",
            transport_kind="sdk",
            call_surface_ref=sdk_entry_ref,
            formal_adapter_eligible=eligible,
            blockers=blockers,
            hints={"actions": list(sdk_actions or [])},
        )

    if _string(payload.get("execute_command")) is not None:
        return ExternalProtocolSurface(
            protocol_surface_kind="cli_runtime",
            formal_adapter_eligible=False,
            blockers=["no-stable-callable-surface"],
        )

    return ExternalProtocolSurface(
        protocol_surface_kind="unknown",
        formal_adapter_eligible=False,
        blockers=["no-callable-surface-detected"],
    )


def protocol_surface_metadata(
    surface: ExternalProtocolSurface,
) -> dict[str, Any]:
    return {
        "protocol_surface_kind": surface.protocol_surface_kind,
        "transport_kind": surface.transport_kind,
        "call_surface_ref": surface.call_surface_ref,
        "schema_ref": surface.schema_ref,
        "formal_adapter_eligible": surface.formal_adapter_eligible,
        "adapter_blockers": _string_list(surface.blockers),
        "protocol_hints": dict(surface.hints),
    }


def protocol_surface_from_metadata(
    metadata: Mapping[str, Any] | None,
) -> ExternalProtocolSurface | None:
    payload = dict(metadata or {})
    protocol_surface_kind = _string(payload.get("protocol_surface_kind"))
    if protocol_surface_kind is None:
        return None
    transport_kind = _string(payload.get("transport_kind"))
    if transport_kind not in {"mcp", "http", "sdk"}:
        transport_kind = None
    return ExternalProtocolSurface(
        protocol_surface_kind=protocol_surface_kind,  # type: ignore[arg-type]
        transport_kind=transport_kind,  # type: ignore[arg-type]
        call_surface_ref=_string(payload.get("call_surface_ref")),
        schema_ref=_string(payload.get("schema_ref")),
        formal_adapter_eligible=bool(payload.get("formal_adapter_eligible")),
        blockers=_string_list(payload.get("adapter_blockers")),
        hints=dict(payload.get("protocol_hints") or {}),
    )


__all__ = [
    "CompiledAdapterAction",
    "CompiledAdapterContract",
    "ExternalProtocolSurface",
    "classify_external_protocol_surface",
    "protocol_surface_from_metadata",
    "protocol_surface_metadata",
]
