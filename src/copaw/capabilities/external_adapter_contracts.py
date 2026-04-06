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
ADAPTER_ATTRIBUTION_SCALAR_FIELDS = (
    "protocol_surface_kind",
    "transport_kind",
    "compiled_adapter_id",
    "selected_adapter_action_id",
)
ADAPTER_ATTRIBUTION_LIST_FIELDS = (
    "compiled_action_ids",
    "adapter_blockers",
)


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


def _action_entries(value: object | None) -> list[dict[str, Any]]:
    items: Sequence[object]
    if isinstance(value, list):
        items = value
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray, Mapping),
    ):
        items = value
    else:
        items = []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, Mapping):
            normalized.append(dict(item))
    return normalized


def _mcp_surface_candidate(
    payload: Mapping[str, Any],
) -> ExternalProtocolSurface | None:
    mcp_server_ref = _string(payload.get("mcp_server_ref"))
    if mcp_server_ref is None:
        return None
    mcp_tools = _action_entries(payload.get("mcp_tools"))
    eligible = bool(mcp_tools)
    blockers: list[str] = []
    if not eligible:
        blockers.append("no-typed-action-surface")
    return ExternalProtocolSurface(
        protocol_surface_kind="native_mcp",
        transport_kind="mcp",
        call_surface_ref=mcp_server_ref,
        formal_adapter_eligible=eligible,
        blockers=blockers,
        hints={"actions": mcp_tools},
    )


def _api_surface_candidate(
    payload: Mapping[str, Any],
) -> ExternalProtocolSurface | None:
    api_base_url = _string(payload.get("api_base_url")) or _string(
        payload.get("openapi_url"),
    )
    if api_base_url is None:
        return None
    api_actions = _action_entries(payload.get("api_actions") or payload.get("openapi_actions"))
    blockers: list[str] = []
    eligible = bool(api_actions)
    if not eligible:
        blockers.append("no-typed-action-surface")
    return ExternalProtocolSurface(
        protocol_surface_kind="api",
        transport_kind="http",
        call_surface_ref=api_base_url,
        schema_ref=_string(payload.get("openapi_url")),
        formal_adapter_eligible=eligible,
        blockers=blockers,
        hints={"actions": api_actions},
    )


def _sdk_surface_candidate(
    payload: Mapping[str, Any],
) -> ExternalProtocolSurface | None:
    sdk_entry_ref = _string(payload.get("sdk_entry_ref"))
    if sdk_entry_ref is None:
        return None
    sdk_actions = _action_entries(payload.get("sdk_actions"))
    blockers: list[str] = []
    eligible = bool(sdk_actions)
    if not eligible:
        blockers.append("no-typed-action-surface")
    return ExternalProtocolSurface(
        protocol_surface_kind="sdk",
        transport_kind="sdk",
        call_surface_ref=sdk_entry_ref,
        formal_adapter_eligible=eligible,
        blockers=blockers,
        hints={"actions": sdk_actions},
    )


def classify_external_protocol_surface(
    *,
    metadata: Mapping[str, Any] | None,
) -> ExternalProtocolSurface:
    payload = dict(metadata or {})
    candidates = [
        _mcp_surface_candidate(payload),
        _api_surface_candidate(payload),
        _sdk_surface_candidate(payload),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.formal_adapter_eligible:
            return candidate
    for candidate in candidates:
        if candidate is not None:
            return candidate

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


def adapter_attribution_metadata(
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    normalized: dict[str, Any] = {}
    protocol_surface_kind = _string(payload.get("protocol_surface_kind"))
    if protocol_surface_kind in {"native_mcp", "api", "sdk", "cli_runtime", "unknown"}:
        normalized["protocol_surface_kind"] = protocol_surface_kind
    transport_kind = _string(payload.get("transport_kind"))
    if transport_kind in {"mcp", "http", "sdk"}:
        normalized["transport_kind"] = transport_kind
    compiled_adapter_id = _string(payload.get("compiled_adapter_id"))
    if compiled_adapter_id is not None:
        normalized["compiled_adapter_id"] = compiled_adapter_id
    selected_adapter_action_id = _string(payload.get("selected_adapter_action_id"))
    if selected_adapter_action_id is not None:
        normalized["selected_adapter_action_id"] = selected_adapter_action_id
    compiled_action_ids = _string_list(payload.get("compiled_action_ids"))
    if compiled_action_ids:
        normalized["compiled_action_ids"] = compiled_action_ids
    adapter_blockers = _string_list(
        payload.get("adapter_blockers") or payload.get("promotion_blockers"),
    )
    if adapter_blockers:
        normalized["adapter_blockers"] = adapter_blockers
    return normalized


def merge_adapter_attribution_metadata(
    *payloads: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        merged.update(dict(payload))
        merged.update(adapter_attribution_metadata(payload))
    return merged


__all__ = [
    "ADAPTER_ATTRIBUTION_LIST_FIELDS",
    "ADAPTER_ATTRIBUTION_SCALAR_FIELDS",
    "CompiledAdapterAction",
    "CompiledAdapterContract",
    "ExternalProtocolSurface",
    "adapter_attribution_metadata",
    "classify_external_protocol_surface",
    "merge_adapter_attribution_metadata",
    "protocol_surface_from_metadata",
    "protocol_surface_metadata",
]
