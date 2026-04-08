# -*- coding: utf-8 -*-
"""MCP client manager for hot-reloadable client lifecycle management.

This module provides centralized management of MCP clients with support
for runtime updates without restarting the application.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Literal, TYPE_CHECKING

from agentscope.mcp import HttpStatefulClient, StdIOStatefulClient

from .runtime_contract import (
    MCPClientRuntimeRecord,
    MCPErrorMode,
    MCPOverlayMode,
    MCPRuntimeStatus,
    build_mcp_rebuild_spec,
    build_mcp_reload_state,
    build_mcp_runtime_record,
)

if TYPE_CHECKING:
    from ...config.config import MCPClientConfig, MCPConfig

logger = logging.getLogger(__name__)


def _consume_current_task_cancellation() -> int:
    current = asyncio.current_task()
    if current is None:
        return 0
    uncancel = getattr(current, "uncancel", None)
    if not callable(uncancel):
        return 0
    cleared = 0
    while current.cancelling():
        uncancel()
        cleared += 1
    return cleared


@dataclass
class _ScopedOverlayRegistry:
    mode: Literal["additive", "replace"] = "additive"
    clients: Dict[str, Any] = field(default_factory=dict)
    configs: Dict[str, "MCPClientConfig"] = field(default_factory=dict)
    parent_scope_ref: str | None = None


class MCPClientManager:
    """Manages MCP clients with hot-reload support.

    This manager handles the lifecycle of MCP clients, including:
    - Initial loading from config
    - Runtime replacement when config changes
    - Scoped additive overlays for child/runtime-local shells
    - Cleanup on shutdown

    Design pattern mirrors ChannelManager for consistency.
    """

    def __init__(self) -> None:
        """Initialize an empty MCP client manager."""
        self._clients: Dict[str, Any] = {}
        self._client_configs: Dict[str, MCPClientConfig] = {}
        self._runtime_records: Dict[tuple[str | None, str], MCPClientRuntimeRecord] = {}
        self._overlay_scopes: Dict[str, _ScopedOverlayRegistry] = {}
        self._lock = asyncio.Lock()
        self._close_timeout_seconds = 5.0

    async def init_from_config(
        self,
        config: "MCPConfig",
        *,
        strict: bool = False,
        timeout: float = 60.0,
    ) -> None:
        """Initialize clients from configuration."""
        logger.debug("Initializing MCP clients from config")
        for key, client_config in config.clients.items():
            await self._remember_config(key, client_config)
            if not client_config.enabled:
                logger.debug("MCP client '%s' is disabled, skipping", key)
                await self._set_runtime_record(
                    key,
                    client_config,
                    status="disabled",
                    init_mode="strict" if strict else "warn",
                    connect_timeout_seconds=timeout,
                )
                continue

            try:
                await self._add_client(
                    key,
                    client_config,
                    timeout=timeout,
                    init_mode="strict" if strict else "warn",
                )
                logger.debug("MCP client '%s' initialized successfully", key)
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                await self._set_runtime_record(
                    key,
                    client_config,
                    status="failed",
                    init_mode="strict" if strict else "warn",
                    connect_timeout_seconds=timeout,
                    error=str(exc),
                )
                logger.warning(
                    "Failed to initialize MCP client '%s': %s",
                    key,
                    exc,
                    exc_info=True,
                )
                if strict:
                    raise

    async def get_clients(self, *, scope_ref: str | None = None) -> List[Any]:
        """Get list of active MCP clients for the requested scope."""
        async with self._lock:
            return list(self._scoped_clients_locked(scope_ref).values())

    async def get_client(
        self,
        key: str,
        *,
        scope_ref: str | None = None,
    ) -> Any | None:
        """Return a single MCP client by key if available."""
        async with self._lock:
            return self._scoped_clients_locked(scope_ref).get(key)

    async def list_runtime_records(
        self,
        *,
        scope_ref: str | None = None,
    ) -> List[MCPClientRuntimeRecord]:
        """Return MCP runtime diagnostics in stable key order."""
        async with self._lock:
            keys = sorted(
                record_key
                for record_key in self._runtime_records
                if record_key[0] == scope_ref
            )
            return [
                self._runtime_records[record_key].model_copy(deep=True)
                for record_key in keys
            ]

    async def get_runtime_record(
        self,
        key: str,
        *,
        scope_ref: str | None = None,
    ) -> MCPClientRuntimeRecord | None:
        """Return runtime diagnostics for one client if available."""
        async with self._lock:
            record = self._runtime_records.get((scope_ref, key))
            return record.model_copy(deep=True) if record is not None else None

    async def replace_client(
        self,
        key: str,
        client_config: "MCPClientConfig",
        timeout: float = 60.0,
    ) -> None:
        """Replace or add a base client with new configuration."""
        async with self._lock:
            old_client = self._clients.get(key)
            old_config = self._client_configs.get(key)

        steady_config = old_config or client_config
        await self._set_runtime_record(
            key,
            steady_config,
            status="reloading",
            init_mode="warn",
            connect_timeout_seconds=timeout,
            connected=old_client is not None,
            summary=f"MCP client '{key}' is reloading.",
            dirty=old_client is not None,
            in_flight=True,
        )

        logger.debug("Connecting new MCP client: %s", key)
        new_client = self._build_client(client_config)

        try:
            await asyncio.wait_for(new_client.connect(), timeout=timeout)
        except asyncio.TimeoutError:
            await self._close_client_quietly(new_client)
            await self._record_failed_replace(
                key=key,
                steady_config=steady_config,
                pending_config=client_config,
                timeout=timeout,
                error=f"timeout after {timeout}s",
                has_steady_client=old_client is not None,
            )
            logger.warning(
                "Timeout connecting MCP client '%s' after %ss",
                key,
                timeout,
            )
            raise
        except Exception as exc:
            await self._close_client_quietly(new_client)
            await self._record_failed_replace(
                key=key,
                steady_config=steady_config,
                pending_config=client_config,
                timeout=timeout,
                error=str(exc),
                has_steady_client=old_client is not None,
            )
            logger.warning("Failed to connect MCP client '%s': %s", key, exc)
            raise

        async with self._lock:
            old_client = self._clients.get(key)
            self._clients[key] = new_client
            self._client_configs[key] = client_config
            self._runtime_records[(None, key)] = self._build_runtime_record(
                key,
                client_config,
                status="ready",
                init_mode="warn",
                connect_timeout_seconds=timeout,
                connected=True,
                last_outcome="reloaded",
            )

        close_error: str | None = None
        if old_client is not None:
            logger.debug("Closing old MCP client: %s", key)
            close_error = await self._close_client_with_timeout(old_client)
            if close_error is not None:  # pragma: no branch - exercised by tests
                logger.warning(
                    "Error closing old MCP client '%s': %s",
                    key,
                    close_error,
                )
        else:
            logger.debug("Added new MCP client: %s", key)

        if close_error:
            await self._set_runtime_record(
                key,
                client_config,
                status="ready",
                init_mode="warn",
                connect_timeout_seconds=timeout,
                error=close_error,
                summary=(
                    f"MCP client '{key}' swapped successfully, but closing the previous "
                    f"client failed: {close_error}"
                ),
                connected=True,
                last_outcome="close_failed",
            )

    async def note_reload_pending(
        self,
        key: str,
        client_config: "MCPClientConfig",
        *,
        reason: str = "reload-pending",
    ) -> None:
        """Mark a client as dirty/pending without mutating the steady client."""
        async with self._lock:
            current_client = self._clients.get(key)
            current_config = self._client_configs.get(key)
            current_record = self._runtime_records.get((None, key))

        steady_config = current_config or client_config
        status: MCPRuntimeStatus
        if current_client is not None:
            status = "ready"
        elif current_record is not None:
            status = current_record.status
        else:
            status = "failed"

        summary = (
            f"MCP client '{key}' keeps the current steady client while reload is pending."
            if current_client is not None
            else f"MCP client '{key}' has a pending reload."
        )
        await self._set_runtime_record(
            key,
            steady_config,
            status=status,
            init_mode="warn",
            connect_timeout_seconds=(
                current_record.error_policy.connect_timeout_seconds
                if current_record is not None
                else 60.0
            ),
            error=current_record.last_error if current_record is not None else None,
            summary=summary,
            connected=current_client is not None,
            dirty=True,
            pending_reload=True,
            pending_reason=reason,
            pending_client_config=client_config,
            last_outcome="pending_reload",
        )

    async def mount_scope_overlay(
        self,
        scope_ref: str,
        config: "MCPConfig",
        *,
        parent_scope_ref: str | None = None,
        additive: bool = True,
        timeout: float = 60.0,
    ) -> None:
        """Attach a scoped overlay without mutating the base registry."""
        overlay_mode: Literal["additive", "replace"] = (
            "additive" if additive else "replace"
        )
        connected_clients: Dict[str, Any] = {}
        connected_configs: Dict[str, MCPClientConfig] = {}
        init_mode: MCPErrorMode = "warn"

        for key, client_config in config.clients.items():
            if not client_config.enabled:
                continue
            await self._set_runtime_record(
                key,
                client_config,
                status="connecting",
                init_mode=init_mode,
                connect_timeout_seconds=timeout,
                connected=False,
                summary=(
                    f"MCP overlay client '{key}' is connecting for scope '{scope_ref}'."
                ),
                scope_ref=scope_ref,
                overlay_mode=overlay_mode,
                in_flight=True,
            )
            client = self._build_client(client_config)
            try:
                await asyncio.wait_for(client.connect(), timeout=timeout)
            except Exception as exc:
                await self._close_client_quietly(client)
                await self._close_client_map(connected_clients)
                await self._set_runtime_record(
                    key,
                    client_config,
                    status="failed",
                    init_mode=init_mode,
                    connect_timeout_seconds=timeout,
                    error=str(exc),
                    summary=(
                        f"MCP overlay client '{key}' failed for scope "
                        f"'{scope_ref}': {exc}"
                    ),
                    connected=False,
                    scope_ref=scope_ref,
                    overlay_mode=overlay_mode,
                    dirty=True,
                    last_outcome="connect_failed",
                )
                raise
            connected_clients[key] = client
            connected_configs[key] = client_config

        async with self._lock:
            previous_overlay = self._overlay_scopes.get(scope_ref)
            old_clients = (
                dict(previous_overlay.clients) if previous_overlay is not None else {}
            )
            old_configs = (
                dict(previous_overlay.configs) if previous_overlay is not None else {}
            )
            resolved_parent_scope_ref = self._resolve_parent_scope_ref(
                scope_ref=scope_ref,
                parent_scope_ref=parent_scope_ref,
                previous_overlay=previous_overlay,
            )
            self._overlay_scopes[scope_ref] = _ScopedOverlayRegistry(
                mode=overlay_mode,
                clients=connected_clients,
                configs=connected_configs,
                parent_scope_ref=resolved_parent_scope_ref,
            )
            for key, client_config in connected_configs.items():
                self._runtime_records[(scope_ref, key)] = self._build_runtime_record(
                    key,
                    client_config,
                    status="ready",
                    init_mode=init_mode,
                    connect_timeout_seconds=timeout,
                    connected=True,
                    scope_ref=scope_ref,
                    overlay_mode=overlay_mode,
                    last_outcome="overlay_mounted",
                )
            for key, old_config in old_configs.items():
                if key not in connected_configs:
                    self._runtime_records[(scope_ref, key)] = self._build_runtime_record(
                        key,
                        old_config,
                        status="removed",
                        init_mode=init_mode,
                        connect_timeout_seconds=timeout,
                        connected=False,
                        summary=(
                            f"MCP overlay client '{key}' has been removed from "
                            f"scope '{scope_ref}'."
                        ),
                        scope_ref=scope_ref,
                        overlay_mode=overlay_mode,
                        last_outcome="overlay_removed",
                    )

        await self._close_client_map(old_clients)

    async def clear_scope_overlay(self, scope_ref: str) -> None:
        """Drop a scoped overlay and close its clients."""
        async with self._lock:
            overlay = self._overlay_scopes.pop(scope_ref, None)
            if overlay is None:
                return
            clients = dict(overlay.clients)
            for key, client_config in overlay.configs.items():
                self._runtime_records[(scope_ref, key)] = self._build_runtime_record(
                    key,
                    client_config,
                    status="removed",
                    init_mode="warn",
                    connect_timeout_seconds=60.0,
                    connected=False,
                    summary=(
                        f"MCP overlay client '{key}' has been removed from "
                        f"scope '{scope_ref}'."
                    ),
                    scope_ref=scope_ref,
                    overlay_mode=overlay.mode,
                    last_outcome="overlay_removed",
                )
        await self._close_client_map(clients)

    async def remove_client(self, key: str) -> None:
        """Remove and close a base client."""
        async with self._lock:
            old_client = self._clients.pop(key, None)
            existing_record = self._runtime_records.get((None, key))
            existing_config = self._client_configs.pop(key, None)
            if existing_record is not None and existing_config is not None:
                self._runtime_records[(None, key)] = self._build_runtime_record(
                    key,
                    existing_config,
                    status="removed",
                    init_mode=existing_record.error_policy.init_mode,
                    connect_timeout_seconds=existing_record.error_policy.connect_timeout_seconds,
                    connected=False,
                    last_outcome="removed",
                )

        if old_client is not None:
            logger.debug("Removing MCP client: %s", key)
            close_error = await self._close_client_with_timeout(old_client)
            if close_error is not None:
                logger.warning("Error closing MCP client '%s': %s", key, close_error)

    async def close_all(self) -> None:
        """Close all base and overlay clients."""
        async with self._lock:
            base_clients_snapshot = list(self._clients.items())
            self._clients.clear()
            overlay_snapshot = {
                scope_ref: _ScopedOverlayRegistry(
                    mode=overlay.mode,
                    clients=dict(overlay.clients),
                    configs=dict(overlay.configs),
                    parent_scope_ref=overlay.parent_scope_ref,
                )
                for scope_ref, overlay in self._overlay_scopes.items()
            }
            self._overlay_scopes.clear()
            for key, record in list(self._runtime_records.items()):
                scope_ref, client_key = key
                if scope_ref is None:
                    client_config = self._client_configs.get(client_key)
                    overlay_mode: MCPOverlayMode = "base"
                else:
                    client_config = overlay_snapshot.get(scope_ref, _ScopedOverlayRegistry()).configs.get(
                        client_key
                    )
                    overlay_mode = overlay_snapshot.get(scope_ref, _ScopedOverlayRegistry()).mode
                if client_config is None:
                    continue
                self._runtime_records[key] = self._build_runtime_record(
                    client_key,
                    client_config,
                    status="closing",
                    init_mode=record.error_policy.init_mode,
                    connect_timeout_seconds=record.error_policy.connect_timeout_seconds,
                    connected=False,
                    summary=f"MCP client '{client_key}' is closing.",
                    scope_ref=scope_ref,
                    overlay_mode=overlay_mode,
                )

        logger.debug("Closing all MCP clients")
        for key, client in base_clients_snapshot:
            if client is None:
                continue
            close_error = await self._close_client_with_timeout(client)
            if close_error is not None:
                logger.warning("Error closing MCP client '%s': %s", key, close_error)

        for scope_ref, overlay in overlay_snapshot.items():
            await self._close_client_map(
                overlay.clients,
                label_prefix=f"{scope_ref}:",
            )

    async def _add_client(
        self,
        key: str,
        client_config: "MCPClientConfig",
        timeout: float = 60.0,
        init_mode: str = "warn",
    ) -> None:
        """Add a new client during initial setup."""
        resolved_init_mode: MCPErrorMode = "strict" if init_mode == "strict" else "warn"
        await self._set_runtime_record(
            key,
            client_config,
            status="connecting",
            init_mode=resolved_init_mode,
            connect_timeout_seconds=timeout,
            summary=f"MCP client '{key}' is connecting.",
            in_flight=True,
        )
        client = self._build_client(client_config)
        await asyncio.wait_for(client.connect(), timeout=timeout)

        async with self._lock:
            self._clients[key] = client
            self._client_configs[key] = client_config
            self._runtime_records[(None, key)] = self._build_runtime_record(
                key,
                client_config,
                status="ready",
                init_mode=resolved_init_mode,
                connect_timeout_seconds=timeout,
                connected=True,
            )

    @staticmethod
    def _build_client(client_config: "MCPClientConfig") -> Any:
        """Build MCP client instance by configured transport."""
        rebuild_info = build_mcp_rebuild_spec(
            client_config,
        ).as_client_attribute()

        if client_config.transport == "stdio":
            client = StdIOStatefulClient(
                name=client_config.name,
                command=client_config.command,
                args=client_config.args,
                env=client_config.env,
                cwd=client_config.cwd or None,
            )
            setattr(client, "_copaw_rebuild_info", rebuild_info)
            return client

        client = HttpStatefulClient(
            name=client_config.name,
            transport=client_config.transport,
            url=client_config.url,
            headers=client_config.headers or None,
        )
        setattr(client, "_copaw_rebuild_info", rebuild_info)
        return client

    async def _remember_config(
        self,
        key: str,
        client_config: "MCPClientConfig",
    ) -> None:
        async with self._lock:
            self._client_configs[key] = client_config

    async def _set_runtime_record(
        self,
        key: str,
        client_config: "MCPClientConfig",
        *,
        status: MCPRuntimeStatus,
        init_mode: MCPErrorMode,
        connect_timeout_seconds: float,
        error: str | None = None,
        summary: str | None = None,
        connected: bool = False,
        scope_ref: str | None = None,
        overlay_mode: MCPOverlayMode = "base",
        dirty: bool = False,
        pending_reload: bool = False,
        in_flight: bool = False,
        pending_reason: str | None = None,
        pending_client_config: MCPClientConfig | None = None,
        last_outcome: str = "steady",
    ) -> None:
        async with self._lock:
            self._runtime_records[(scope_ref, key)] = self._build_runtime_record(
                key,
                client_config,
                status=status,
                init_mode=init_mode,
                connect_timeout_seconds=connect_timeout_seconds,
                error=error,
                summary=summary,
                connected=connected,
                scope_ref=scope_ref,
                overlay_mode=overlay_mode,
                dirty=dirty,
                pending_reload=pending_reload,
                in_flight=in_flight,
                pending_reason=pending_reason,
                pending_client_config=pending_client_config,
                last_outcome=last_outcome,
            )

    async def _record_failed_replace(
        self,
        *,
        key: str,
        steady_config: "MCPClientConfig",
        pending_config: "MCPClientConfig",
        timeout: float,
        error: str,
        has_steady_client: bool,
    ) -> None:
        if has_steady_client:
            await self._set_runtime_record(
                key,
                steady_config,
                status="ready",
                init_mode="warn",
                connect_timeout_seconds=timeout,
                error=error,
                summary=(
                    f"MCP client '{key}' keeps the current steady client after "
                    f"reload failed: {error}"
                ),
                connected=True,
                dirty=True,
                pending_reload=True,
                pending_reason="replace-failed",
                pending_client_config=pending_config,
                last_outcome="connect_failed",
            )
            return

        await self._set_runtime_record(
            key,
            pending_config,
            status="failed",
            init_mode="warn",
            connect_timeout_seconds=timeout,
            error=error,
            connected=False,
            dirty=True,
            pending_reload=True,
            pending_reason="replace-failed",
            pending_client_config=pending_config,
            last_outcome="connect_failed",
        )

    def _build_runtime_record(
        self,
        key: str,
        client_config: "MCPClientConfig",
        *,
        status: MCPRuntimeStatus,
        init_mode: MCPErrorMode,
        connect_timeout_seconds: float,
        error: str | None = None,
        summary: str | None = None,
        connected: bool = False,
        scope_ref: str | None = None,
        overlay_mode: MCPOverlayMode = "base",
        dirty: bool = False,
        pending_reload: bool = False,
        in_flight: bool = False,
        pending_reason: str | None = None,
        pending_client_config: MCPClientConfig | None = None,
        last_outcome: str = "steady",
    ) -> MCPClientRuntimeRecord:
        cache_scope = (
            "manager-overlay-scope" if scope_ref is not None else "manager-client-registry"
        )
        return build_mcp_runtime_record(
            key,
            client_config,
            status=status,
            init_mode=init_mode,
            connect_timeout_seconds=connect_timeout_seconds,
            cache_scope=cache_scope,
            error=error,
            summary=summary,
            connected=connected,
            reload_state=build_mcp_reload_state(
                dirty=dirty,
                pending_reload=pending_reload,
                in_flight=in_flight,
                last_outcome=last_outcome,  # type: ignore[arg-type]
                pending_reason=pending_reason,
                pending_client_config=pending_client_config,
                overlay_scope=scope_ref,
                overlay_mode=overlay_mode,
            ),
        )

    def _scoped_clients_locked(self, scope_ref: str | None) -> Dict[str, Any]:
        return self._resolve_scoped_clients_locked(
            scope_ref=scope_ref,
            visited_scopes=set(),
        )

    def _resolve_scoped_clients_locked(
        self,
        *,
        scope_ref: str | None,
        visited_scopes: set[str],
    ) -> Dict[str, Any]:
        base_clients = {
            key: client
            for key, client in self._clients.items()
            if client is not None
        }
        if scope_ref is None:
            return dict(base_clients)

        overlay = self._overlay_scopes.get(scope_ref)
        if overlay is None:
            return dict(base_clients)

        scoped_clients = {
            key: client
            for key, client in overlay.clients.items()
            if client is not None
        }
        if overlay.mode == "replace":
            return scoped_clients

        parent_scope_ref = overlay.parent_scope_ref
        if (
            parent_scope_ref is not None
            and parent_scope_ref != scope_ref
            and parent_scope_ref not in visited_scopes
        ):
            merged = self._resolve_scoped_clients_locked(
                scope_ref=parent_scope_ref,
                visited_scopes={*visited_scopes, scope_ref},
            )
        else:
            merged = dict(base_clients)
        merged.update(scoped_clients)
        return merged

    @staticmethod
    def _resolve_parent_scope_ref(
        *,
        scope_ref: str,
        parent_scope_ref: str | None,
        previous_overlay: _ScopedOverlayRegistry | None,
    ) -> str | None:
        candidate = (
            parent_scope_ref
            if parent_scope_ref is not None
            else (
                previous_overlay.parent_scope_ref
                if previous_overlay is not None
                else None
            )
        )
        if candidate is None:
            return None
        normalized = str(candidate).strip()
        if not normalized or normalized == scope_ref:
            return None
        return normalized

    async def _close_client_quietly(self, client: Any | None) -> None:
        if client is None:
            return
        await self._close_client_with_timeout(client)

    @staticmethod
    def _resolve_close_operations(client: Any) -> list[Any]:
        operations: list[Any] = []
        context = getattr(client, "client", None)
        generator = getattr(context, "gen", None)
        frame = getattr(generator, "ag_frame", None)
        frame_locals = getattr(frame, "f_locals", None)
        if isinstance(frame_locals, dict):
            process = frame_locals.get("process")
            process_aclose = getattr(process, "aclose", None)
            if callable(process_aclose):
                operations.append(process_aclose)
        stack = getattr(client, "stack", None)
        stack_aclose = getattr(stack, "aclose", None)
        if callable(stack_aclose):
            operations.append(stack_aclose)
        close = getattr(client, "close", None)
        if callable(close) and not operations:
            operations.append(close)
        return operations

    async def _close_client_with_timeout(self, client: Any | None) -> str | None:
        if client is None:
            return None
        close_operations = self._resolve_close_operations(client)
        if not close_operations:
            return "close operation unavailable"
        close_timeout_seconds = max(0.01, float(self._close_timeout_seconds))
        close_errors: list[str] = []
        for close_operation in close_operations:
            try:
                async with asyncio.timeout(close_timeout_seconds):
                    await close_operation()
            except asyncio.TimeoutError:
                _consume_current_task_cancellation()
                close_errors.append(f"close timeout after {self._close_timeout_seconds}s")
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                _consume_current_task_cancellation()
                close_errors.append(str(exc) or "close cancelled")
        if hasattr(client, "is_connected"):
            try:
                setattr(client, "is_connected", False)
            except Exception:
                pass
        if not close_errors:
            return None
        return "; ".join(dict.fromkeys(close_errors))

    async def _close_client_map(
        self,
        clients: Dict[str, Any],
        *,
        label_prefix: str = "",
    ) -> None:
        for key, client in clients.items():
            if client is None:
                continue
            close_error = await self._close_client_with_timeout(client)
            if close_error is not None:
                logger.warning(
                    "Error closing MCP client '%s%s': %s",
                    label_prefix,
                    key,
                    close_error,
                )
