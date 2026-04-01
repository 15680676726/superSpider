# -*- coding: utf-8 -*-
"""Typed MCP runtime contract for manager/lifecycle diagnostics."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

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
MCPCacheScope = Literal["manager-client-registry"]
MCPErrorMode = Literal["warn", "strict"]


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
    error: str | None = None,
    summary: str | None = None,
    connected: bool = False,
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
        session_policy=MCPRuntimeSessionPolicy(mode=session_mode),
        error_policy=MCPRuntimeErrorPolicy(
            init_mode=init_mode,
            connect_timeout_seconds=float(connect_timeout_seconds),
        ),
        last_error=error,
        connected=connected,
        rebuild_info=build_mcp_rebuild_spec(client_config),
    )


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
    "MCPClientRuntimeRecord",
    "MCPRuntimeAuthPolicy",
    "MCPRuntimeErrorPolicy",
    "MCPRuntimeSessionPolicy",
    "MCPTransport",
    "build_mcp_rebuild_spec",
    "build_mcp_runtime_record",
]
