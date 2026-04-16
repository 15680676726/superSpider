# -*- coding: utf-8 -*-
"""Shared browser channel resolution helpers."""

from __future__ import annotations

from typing import Any, Mapping

_READY_STATUSES = {
    "attached",
    "available",
    "connected",
    "healthy",
    "ready",
    "reconnecting",
}


def _normalized(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _as_mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _extract_companion_snapshot(snapshot: object) -> dict[str, Any]:
    payload = _as_mapping(snapshot)
    companion = _as_mapping(payload.get("browser_companion"))
    if companion:
        return companion
    return payload


def _extract_attach_snapshot(snapshot: object) -> dict[str, Any]:
    payload = _as_mapping(snapshot)
    attach = _as_mapping(payload.get("browser_attach"))
    if attach:
        return attach
    return payload


def _ready_status(value: object) -> bool:
    normalized = _normalized(value)
    if normalized is None:
        return False
    return normalized.lower() in _READY_STATUSES


def _bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def resolve_browser_channel_policy(
    *,
    companion_snapshot: object = None,
    attach_snapshot: object = None,
    browser_mode: str | None = None,
    attach_required: bool | None = None,
) -> dict[str, Any]:
    normalized_mode = _normalized(browser_mode)
    effective_attach_required = bool(attach_required) or (
        normalized_mode == "attach-existing-session"
    )

    companion = _extract_companion_snapshot(companion_snapshot)
    attach = _extract_attach_snapshot(attach_snapshot)

    companion_transport_ref = _normalized(companion.get("transport_ref"))
    companion_provider_session_ref = _normalized(companion.get("provider_session_ref"))
    companion_status = _normalized(companion.get("status"))
    companion_available = _bool_or_none(companion.get("available"))
    companion_healthy = bool(
        (
            companion_available is True
            or companion_transport_ref is not None
            or companion_provider_session_ref is not None
        )
        and (
            companion_available is True
            or _ready_status(companion_status)
        )
    )

    attach_transport_ref = _normalized(attach.get("transport_ref"))
    attach_status = _normalized(attach.get("status"))
    attach_session_ref = _normalized(attach.get("session_ref"))
    attach_scope_ref = _normalized(attach.get("scope_ref"))
    attach_reconnect_token = _normalized(attach.get("reconnect_token"))
    attach_healthy = bool(
        attach_transport_ref is not None
        and (
            attach_status is None
            or _ready_status(attach_status)
        )
    )

    browser_mcp_healthy = companion_healthy and attach_healthy
    browser_mcp_status = (
        "healthy"
        if browser_mcp_healthy
        else "degraded"
        if companion_healthy or attach_healthy
        else "unavailable"
    )

    if effective_attach_required and not browser_mcp_healthy:
        return {
            "selected_channel": None,
            "selected_capability_id": None,
            "selection_status": "blocked",
            "selected_channel_health": "blocked",
            "selected_browser_mode": "attach-existing-session",
            "reason": (
                "Attach-required browser work cannot fall back to the managed built-in browser."
            ),
            "attach_required": True,
            "fail_closed": True,
            "built_in": {
                "capability_id": "tool:browser_use",
                "healthy": True,
                "status": "healthy",
            },
            "browser_mcp": {
                "capability_id": "system:browser_companion_runtime",
                "healthy": False,
                "status": browser_mcp_status,
                "transport_ref": companion_transport_ref,
                "provider_session_ref": companion_provider_session_ref,
                "attach_transport_ref": attach_transport_ref,
                "attach_status": attach_status,
                "attach_session_ref": attach_session_ref,
                "attach_scope_ref": attach_scope_ref,
                "attach_reconnect_token": attach_reconnect_token,
            },
        }

    if effective_attach_required and browser_mcp_healthy:
        return {
            "selected_channel": "browser-mcp",
            "selected_capability_id": "system:browser_companion_runtime",
            "selection_status": "ready",
            "selected_channel_health": "healthy",
            "selected_browser_mode": "attach-existing-session",
            "reason": "Browser MCP is healthy and selected for the attached browser seat.",
            "attach_required": effective_attach_required,
            "fail_closed": False,
            "built_in": {
                "capability_id": "tool:browser_use",
                "healthy": True,
                "status": "healthy",
            },
            "browser_mcp": {
                "capability_id": "system:browser_companion_runtime",
                "healthy": True,
                "status": "healthy",
                "transport_ref": companion_transport_ref,
                "provider_session_ref": companion_provider_session_ref,
                "attach_transport_ref": attach_transport_ref,
                "attach_status": attach_status,
                "attach_session_ref": attach_session_ref,
                "attach_scope_ref": attach_scope_ref,
                "attach_reconnect_token": attach_reconnect_token,
            },
        }

    return {
        "selected_channel": "built-in-browser",
        "selected_capability_id": "tool:browser_use",
        "selection_status": "ready",
        "selected_channel_health": "healthy",
        "selected_browser_mode": "managed-isolated",
        "reason": (
            "Built-in browser remains the default channel for general browser work; browser MCP is reserved for attached-session continuity."
        ),
        "attach_required": effective_attach_required,
        "fail_closed": False,
        "built_in": {
            "capability_id": "tool:browser_use",
            "healthy": True,
            "status": "healthy",
        },
        "browser_mcp": {
            "capability_id": "system:browser_companion_runtime",
            "healthy": browser_mcp_healthy,
            "status": browser_mcp_status,
            "transport_ref": companion_transport_ref,
            "provider_session_ref": companion_provider_session_ref,
            "attach_transport_ref": attach_transport_ref,
            "attach_status": attach_status,
            "attach_session_ref": attach_session_ref,
            "attach_scope_ref": attach_scope_ref,
            "attach_reconnect_token": attach_reconnect_token,
        },
    }
