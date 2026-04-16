# -*- coding: utf-8 -*-
"""Typed MCP runtime contract for manager/lifecycle diagnostics."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from ...capabilities.activation_models import ActivationClass, ActivationState
from ...config.config import MCPClientConfig

MCPTransport = Literal["stdio", "streamable_http", "sse"]
MCPRuntimeStatus = Literal[
    "disabled",
    "connecting",
    "ready",
    "reloading",
    "failed",
    "removed",
    "closing",
]
MCPAuthMode = Literal["none", "headers", "env"]
MCPSessionMode = Literal["stdio-process", "streamable-http", "sse"]
MCPCacheScope = Literal["manager-client-registry", "manager-overlay-scope"]
MCPErrorMode = Literal["warn", "strict"]
MCPReloadOutcome = Literal[
    "steady",
    "pending_reload",
    "reloaded",
    "connect_failed",
    "close_failed",
    "removed",
    "overlay_mounted",
    "overlay_removed",
]
MCPOverlayMode = Literal["base", "additive", "replace"]
MCPTrialScope = Literal["agent", "seat", "session"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MCPRuntimeAuthPolicy(BaseModel):
    mode: MCPAuthMode = "none"
    keys: list[str] = Field(default_factory=list)


class MCPRuntimeSessionPolicy(BaseModel):
    mode: MCPSessionMode
    cache_scope: MCPCacheScope = "manager-client-registry"
    stateful: bool = True


class MCPRuntimeErrorPolicy(BaseModel):
    init_mode: MCPErrorMode = "warn"
    reload_mode: Literal["best-effort"] = "best-effort"
    connect_timeout_seconds: float = 60.0


class MCPClientRebuildSpec(BaseModel):
    name: str
    transport: MCPTransport
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None

    def as_client_attribute(self) -> dict[str, object]:
        """Keep the legacy client attribute shape until callers are migrated."""
        return self.model_dump(mode="python")


class MCPClientReloadState(BaseModel):
    dirty: bool = False
    pending_reload: bool = False
    in_flight: bool = False
    last_outcome: MCPReloadOutcome = "steady"
    pending_reason: str | None = None
    pending_spec: MCPClientRebuildSpec | None = None
    overlay_scope: str | None = None
    overlay_mode: MCPOverlayMode = "base"
    last_transition_at: datetime = Field(default_factory=_utc_now)


class MCPClientRuntimeRecord(BaseModel):
    key: str
    name: str
    transport: MCPTransport
    enabled: bool
    status: MCPRuntimeStatus
    summary: str
    auth_policy: MCPRuntimeAuthPolicy
    session_policy: MCPRuntimeSessionPolicy
    error_policy: MCPRuntimeErrorPolicy
    last_error: str | None = None
    last_transition_at: datetime = Field(default_factory=_utc_now)
    connected: bool = False
    rebuild_info: MCPClientRebuildSpec
    reload_state: MCPClientReloadState = Field(default_factory=MCPClientReloadState)


class MCPTrialRollbackContract(BaseModel):
    client_key: str
    rollback_target_ids: list[str] = Field(default_factory=list)
    fallback_action: Literal["disable_mcp_client"] = "disable_mcp_client"


class MCPTrialContract(BaseModel):
    contract_kind: Literal["mcp"] = "mcp"
    baseline_ref: str | None = None
    challenger_ref: str
    target_capability_family: Literal["mcp"] = "mcp"
    target_agent_id: str | None = None
    target_role_id: str | None = None
    selected_scope: MCPTrialScope = "agent"
    selected_seat_ref: str | None = None
    target_capability_ids: list[str] = Field(default_factory=list)
    rollback: MCPTrialRollbackContract


def build_mcp_rebuild_spec(
    client_config: MCPClientConfig,
) -> MCPClientRebuildSpec:
    return MCPClientRebuildSpec(
        name=client_config.name,
        transport=client_config.transport,
        url=client_config.url,
        headers=dict(client_config.headers),
        command=client_config.command,
        args=list(client_config.args),
        env=dict(client_config.env),
        cwd=client_config.cwd or None,
    )


def build_mcp_runtime_record(
    key: str,
    client_config: MCPClientConfig,
    *,
    status: MCPRuntimeStatus,
    init_mode: MCPErrorMode,
    connect_timeout_seconds: float,
    cache_scope: MCPCacheScope = "manager-client-registry",
    error: str | None = None,
    summary: str | None = None,
    connected: bool = False,
    reload_state: MCPClientReloadState | None = None,
) -> MCPClientRuntimeRecord:
    auth_keys: list[str] = []
    auth_mode: MCPAuthMode = "none"
    if client_config.headers:
        auth_mode = "headers"
        auth_keys = sorted(client_config.headers.keys())
    elif client_config.env:
        auth_mode = "env"
        auth_keys = sorted(client_config.env.keys())
    session_mode: MCPSessionMode = "stdio-process"
    if client_config.transport == "streamable_http":
        session_mode = "streamable-http"
    elif client_config.transport == "sse":
        session_mode = "sse"
    resolved_summary = summary or _default_summary(
        key=key,
        status=status,
        error=error,
    )
    return MCPClientRuntimeRecord(
        key=key,
        name=client_config.name,
        transport=client_config.transport,
        enabled=bool(client_config.enabled),
        status=status,
        summary=resolved_summary,
        auth_policy=MCPRuntimeAuthPolicy(mode=auth_mode, keys=auth_keys),
        session_policy=MCPRuntimeSessionPolicy(
            mode=session_mode,
            cache_scope=cache_scope,
        ),
        error_policy=MCPRuntimeErrorPolicy(
            init_mode=init_mode,
            connect_timeout_seconds=float(connect_timeout_seconds),
        ),
        last_error=error,
        connected=connected,
        rebuild_info=build_mcp_rebuild_spec(client_config),
        reload_state=reload_state or MCPClientReloadState(),
    )


def build_mcp_reload_state(
    *,
    dirty: bool = False,
    pending_reload: bool = False,
    in_flight: bool = False,
    last_outcome: MCPReloadOutcome = "steady",
    pending_reason: str | None = None,
    pending_client_config: MCPClientConfig | None = None,
    overlay_scope: str | None = None,
    overlay_mode: MCPOverlayMode = "base",
) -> MCPClientReloadState:
    pending_spec = (
        build_mcp_rebuild_spec(pending_client_config)
        if pending_client_config is not None
        else None
    )
    return MCPClientReloadState(
        dirty=dirty,
        pending_reload=pending_reload,
        in_flight=in_flight,
        last_outcome=last_outcome,
        pending_reason=pending_reason,
        pending_spec=pending_spec,
        overlay_scope=overlay_scope,
        overlay_mode=overlay_mode,
    )


def build_mcp_trial_contract(
    *,
    baseline_ref: str | None,
    challenger_ref: str,
    client_key: str,
    target_agent_id: str | None,
    target_role_id: str | None,
    selected_scope: str,
    selected_seat_ref: str | None,
    target_capability_ids: list[str] | None = None,
    rollback_target_ids: list[str] | None = None,
) -> MCPTrialContract:
    normalized_scope = str(selected_scope or "agent").strip().lower() or "agent"
    if normalized_scope not in {"agent", "seat", "session"}:
        normalized_scope = "agent"
    return MCPTrialContract(
        baseline_ref=str(baseline_ref).strip() or None if baseline_ref is not None else None,
        challenger_ref=str(challenger_ref).strip(),
        target_agent_id=str(target_agent_id).strip() or None
        if target_agent_id is not None
        else None,
        target_role_id=str(target_role_id).strip() or None
        if target_role_id is not None
        else None,
        selected_scope=normalized_scope,  # type: ignore[arg-type]
        selected_seat_ref=str(selected_seat_ref).strip() or None
        if selected_seat_ref is not None
        else None,
        target_capability_ids=[
            str(item).strip()
            for item in list(target_capability_ids or [])
            if str(item).strip()
        ],
        rollback=MCPTrialRollbackContract(
            client_key=str(client_key).strip(),
            rollback_target_ids=[
                str(item).strip()
                for item in list(rollback_target_ids or [])
                if str(item).strip()
            ],
        ),
    )


def infer_mcp_activation_class(
    record: MCPClientRuntimeRecord | None,
    *,
    requested_scope_ref: str | None = None,
) -> ActivationClass:
    if requested_scope_ref:
        return "workspace-bound"
    if record is not None and (
        record.reload_state.overlay_scope is not None
        or record.session_policy.cache_scope == "manager-overlay-scope"
    ):
        return "workspace-bound"
    if record is not None and record.auth_policy.mode != "none":
        return "auth-bound"
    return "stateless"


def build_mcp_activation_state(
    record: MCPClientRuntimeRecord | None,
    *,
    activation_class: ActivationClass,
    requested_scope_ref: str | None = None,
) -> ActivationState:
    runtime = (
        record.model_dump(mode="json")
        if record is not None
        else {
            "status": "missing",
            "connected": False,
        }
    )
    support = {
        "auth_mode": record.auth_policy.mode if record is not None else "none",
        "cache_scope": (
            record.session_policy.cache_scope
            if record is not None
            else "manager-client-registry"
        ),
        "overlay_scope": (
            record.reload_state.overlay_scope
            if record is not None
            else requested_scope_ref
        ),
        "overlay_mode": (
            record.reload_state.overlay_mode if record is not None else "base"
        ),
        "dirty": record.reload_state.dirty if record is not None else False,
        "pending_reload": (
            record.reload_state.pending_reload if record is not None else False
        ),
    }

    if record is None:
        if activation_class == "workspace-bound":
            return ActivationState(
                status="blocked",
                reason="scope_unbound",
                summary="Workspace-scoped MCP overlay is not mounted yet.",
                required_action="system-auto-heal",
                auto_heal_supported=True,
                retryable=True,
                scope_ref=requested_scope_ref,
                runtime=runtime,
                support=support,
            )
        return ActivationState(
            status="blocked",
            reason="runtime_unavailable",
            summary="MCP runtime client is not connected yet.",
            required_action="system-auto-heal",
            auto_heal_supported=True,
            retryable=True,
            scope_ref=requested_scope_ref,
            runtime=runtime,
            support=support,
        )

    if record.status == "disabled" or not record.enabled:
        return ActivationState(
            status="blocked",
            reason="policy_blocked",
            summary=f"MCP client '{record.key}' is disabled by policy.",
            retryable=False,
            scope_ref=requested_scope_ref,
            runtime=runtime,
            support=support,
        )

    runtime_reason = _runtime_reason_for_record(record, activation_class)
    if activation_class == "auth-bound" and runtime_reason == "token_expired":
        human_boundary = None
    else:
        human_boundary = _detect_human_boundary_reason(record.last_error)
    if human_boundary is not None:
        return ActivationState(
            status="waiting_human",
            reason=human_boundary,
            summary=_human_boundary_summary(human_boundary),
            required_action=_human_boundary_action(human_boundary),
            retryable=False,
            scope_ref=requested_scope_ref,
            runtime=runtime,
            support=support,
        )

    if activation_class == "workspace-bound":
        overlay_scope = record.reload_state.overlay_scope
        if requested_scope_ref and overlay_scope != requested_scope_ref:
            return ActivationState(
                status="blocked",
                reason="scope_unbound",
                summary="Workspace-scoped MCP overlay is not mounted yet.",
                required_action="system-auto-heal",
                auto_heal_supported=True,
                retryable=True,
                scope_ref=requested_scope_ref,
                runtime=runtime,
                support=support,
            )
        if record.reload_state.pending_reload or record.reload_state.dirty:
            return ActivationState(
                status="healing",
                reason="scope_unbound",
                summary="Workspace-scoped MCP overlay is being refreshed.",
                required_action="system-auto-heal",
                auto_heal_supported=True,
                retryable=True,
                scope_ref=requested_scope_ref or overlay_scope,
                runtime=runtime,
                support=support,
            )
        if record.status == "ready" and record.connected:
            return ActivationState(
                status="ready",
                summary="Workspace-scoped MCP overlay is ready.",
                retryable=True,
                scope_ref=requested_scope_ref or overlay_scope,
                runtime=runtime,
                support=support,
            )
        return ActivationState(
            status="blocked",
            reason="scope_unbound",
            summary="Workspace-scoped MCP overlay is not ready.",
            required_action="system-auto-heal",
            auto_heal_supported=True,
            retryable=True,
            scope_ref=requested_scope_ref or overlay_scope,
            runtime=runtime,
            support=support,
        )

    if record.status == "connecting":
        return ActivationState(
            status="activating",
            reason="runtime_unavailable",
            summary=f"MCP client '{record.key}' is connecting.",
            auto_heal_supported=True,
            retryable=True,
            scope_ref=requested_scope_ref,
            runtime=runtime,
            support=support,
        )

    if (
        record.status == "reloading"
        or record.reload_state.pending_reload
        or record.reload_state.dirty
    ):
        reason = runtime_reason
        return ActivationState(
            status="healing",
            reason=reason,
            summary=f"MCP client '{record.key}' is being refreshed.",
            required_action="system-auto-heal",
            auto_heal_supported=True,
            retryable=True,
            scope_ref=requested_scope_ref,
            runtime=runtime,
            support=support,
        )

    if record.status == "ready" and record.connected:
        return ActivationState(
            status="ready",
            summary=f"MCP client '{record.key}' is ready.",
            retryable=True,
            scope_ref=requested_scope_ref,
            runtime=runtime,
            support=support,
        )

    reason = runtime_reason
    return ActivationState(
        status="blocked",
        reason=reason,
        summary=f"MCP client '{record.key}' is not ready.",
        required_action="system-auto-heal" if reason != "policy_blocked" else None,
        auto_heal_supported=reason != "policy_blocked",
        retryable=reason != "policy_blocked",
        scope_ref=requested_scope_ref,
        runtime=runtime,
        support=support,
    )


def _runtime_reason_for_record(
    record: MCPClientRuntimeRecord,
    activation_class: ActivationClass,
) -> str:
    error_text = f"{record.last_error or ''} {record.reload_state.pending_reason or ''}".lower()
    if activation_class == "auth-bound" and _looks_like_token_expired(error_text):
        return "token_expired"
    if "unsupported host" in error_text:
        return "unsupported_host"
    if "invalid contract" in error_text:
        return "invalid_capability_contract"
    if "broken installation" in error_text:
        return "broken_installation"
    return "runtime_unavailable"


def _detect_human_boundary_reason(error: str | None) -> str | None:
    text = str(error or "").strip().lower()
    if not text:
        return None
    if "captcha" in text:
        return "captcha_required"
    if "2fa" in text or "two-factor" in text or "two factor" in text or "otp" in text:
        return "two_factor_required"
    if "confirm" in text or "approval" in text or "approve in app" in text:
        return "explicit_human_confirm_required"
    if "open host" in text or "open the app" in text:
        return "host_open_required"
    if "auth required" in text or "oauth" in text or "consent" in text or "login required" in text:
        return "human_auth_required"
    return None


def _looks_like_token_expired(error: str | None) -> bool:
    text = str(error or "").strip().lower()
    if not text:
        return False
    return any(
        token in text
        for token in (
            "token expired",
            "expired token",
            "refresh token",
            "unauthorized",
            "401",
        )
    )


def _human_boundary_summary(reason: str) -> str:
    if reason == "captcha_required":
        return "MCP runtime needs a captcha to continue."
    if reason == "two_factor_required":
        return "MCP runtime needs a 2FA confirmation to continue."
    if reason == "explicit_human_confirm_required":
        return "MCP runtime needs a human confirmation to continue."
    if reason == "host_open_required":
        return "The target host application must be opened first."
    return "MCP runtime needs a human authorization step to continue."


def _human_boundary_action(reason: str) -> str:
    if reason == "host_open_required":
        return "open-target-application"
    return "complete-human-auth"


def _default_summary(
    *,
    key: str,
    status: MCPRuntimeStatus,
    error: str | None,
) -> str:
    if status == "ready":
        return f"MCP client '{key}' is ready."
    if status == "disabled":
        return f"MCP client '{key}' is disabled."
    if status == "removed":
        return f"MCP client '{key}' has been removed."
    if status == "closing":
        return f"MCP client '{key}' is closing."
    if error:
        return f"MCP client '{key}' failed: {error}"
    return f"MCP client '{key}' status is {status}."


__all__ = [
    "MCPClientRebuildSpec",
    "MCPClientReloadState",
    "MCPClientRuntimeRecord",
    "MCPOverlayMode",
    "MCPReloadOutcome",
    "MCPRuntimeAuthPolicy",
    "MCPRuntimeErrorPolicy",
    "MCPRuntimeSessionPolicy",
    "MCPTrialContract",
    "MCPTrialRollbackContract",
    "MCPTrialScope",
    "build_mcp_activation_state",
    "build_mcp_trial_contract",
    "build_mcp_reload_state",
    "build_mcp_rebuild_spec",
    "build_mcp_runtime_record",
    "infer_mcp_activation_class",
    "MCPTransport",
]
