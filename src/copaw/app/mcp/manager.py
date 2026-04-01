# -*- coding: utf-8 -*-
"""MCP client manager for hot-reloadable client lifecycle management.

This module provides centralized management of MCP clients with support
for runtime updates without restarting the application.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, TYPE_CHECKING

from agentscope.mcp import HttpStatefulClient, StdIOStatefulClient

from .runtime_contract import (
    MCPClientRuntimeRecord,
    MCPErrorMode,
    MCPRuntimeStatus,
    build_mcp_rebuild_spec,
    build_mcp_runtime_record,
)

if TYPE_CHECKING:
    from ...config.config import MCPClientConfig, MCPConfig

logger = logging.getLogger(__name__)


class MCPClientManager:
    """Manages MCP clients with hot-reload support.

    This manager handles the lifecycle of MCP clients, including:
    - Initial loading from config
    - Runtime replacement when config changes
    - Cleanup on shutdown

    Design pattern mirrors ChannelManager for consistency.
    """

    def __init__(self) -> None:
        """Initialize an empty MCP client manager."""
        self._clients: Dict[str, Any] = {}
        self._runtime_records: Dict[str, MCPClientRuntimeRecord] = {}
        self._lock = asyncio.Lock()

    async def init_from_config(
        self,
        config: "MCPConfig",
        *,
        strict: bool = False,
        timeout: float = 60.0,
    ) -> None:
        """Initialize clients from configuration.

        Args:
            config: MCP configuration containing client definitions
        """
        logger.debug("Initializing MCP clients from config")
        for key, client_config in config.clients.items():
            if not client_config.enabled:
                logger.debug(f"MCP client '{key}' is disabled, skipping")
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
                logger.debug(f"MCP client '{key}' initialized successfully")
            except BaseException as e:
                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                    raise
                await self._set_runtime_record(
                    key,
                    client_config,
                    status="failed",
                    init_mode="strict" if strict else "warn",
                    connect_timeout_seconds=timeout,
                    error=str(e),
                )
                logger.warning(
                    f"Failed to initialize MCP client '{key}': {e}",
                    exc_info=True,
                )
                if strict:
                    raise

    async def get_clients(self) -> List[Any]:
        """Get list of all active MCP clients.

        This method is called by the runner on each query to get
        the latest set of clients.

        Returns:
            List of connected MCP client instances
        """
        async with self._lock:
            return [
                client
                for client in self._clients.values()
                if client is not None
            ]

    async def get_client(self, key: str) -> Any | None:
        """Return a single MCP client by key if available."""
        async with self._lock:
            return self._clients.get(key)

    async def list_runtime_records(self) -> List[MCPClientRuntimeRecord]:
        """Return MCP runtime diagnostics in stable key order."""
        async with self._lock:
            return [
                self._runtime_records[key].model_copy(deep=True)
                for key in sorted(self._runtime_records.keys())
            ]

    async def get_runtime_record(
        self,
        key: str,
    ) -> MCPClientRuntimeRecord | None:
        """Return runtime diagnostics for one client if available."""
        async with self._lock:
            record = self._runtime_records.get(key)
            return record.model_copy(deep=True) if record is not None else None

    async def replace_client(
        self,
        key: str,
        client_config: "MCPClientConfig",
        timeout: float = 60.0,
    ) -> None:
        """Replace or add a client with new configuration.

        Flow: connect new (outside lock) → swap + close old (inside lock).
        This ensures minimal lock holding time.

        Args:
            key: Client identifier (from config)
            client_config: New client configuration
            timeout: Connection timeout in seconds (default 60s)
        """
        await self._set_runtime_record(
            key,
            client_config,
            status="reloading",
            init_mode="warn",
            connect_timeout_seconds=timeout,
            summary=f"MCP client '{key}' is reloading.",
        )
        # 1. Create and connect new client outside lock (may be slow)
        logger.debug(f"Connecting new MCP client: {key}")
        new_client = self._build_client(client_config)

        try:
            # Add timeout to prevent indefinite blocking
            await asyncio.wait_for(new_client.connect(), timeout=timeout)
        except asyncio.TimeoutError:
            await self._set_runtime_record(
                key,
                client_config,
                status="failed",
                init_mode="warn",
                connect_timeout_seconds=timeout,
                error=f"timeout after {timeout}s",
            )
            logger.warning(
                f"Timeout connecting MCP client '{key}' after {timeout}s",
            )
            try:
                await new_client.close()
            except Exception:
                pass
            raise
        except Exception as e:
            await self._set_runtime_record(
                key,
                client_config,
                status="failed",
                init_mode="warn",
                connect_timeout_seconds=timeout,
                error=str(e),
            )
            logger.warning(f"Failed to connect MCP client '{key}': {e}")
            try:
                await new_client.close()
            except Exception:
                pass
            raise

        # 2. Swap and close old client inside lock
        async with self._lock:
            old_client = self._clients.get(key)
            self._clients[key] = new_client

            if old_client is not None:
                logger.debug(f"Closing old MCP client: {key}")
                try:
                    await old_client.close()
                except Exception as e:
                    logger.warning(
                        f"Error closing old MCP client '{key}': {e}",
                    )
            else:
                logger.debug(f"Added new MCP client: {key}")
        await self._set_runtime_record(
            key,
            client_config,
            status="ready",
            init_mode="warn",
            connect_timeout_seconds=timeout,
            connected=True,
        )

    async def remove_client(self, key: str) -> None:
        """Remove and close a client.

        Args:
            key: Client identifier to remove
        """
        async with self._lock:
            old_client = self._clients.pop(key, None)
            existing_record = self._runtime_records.get(key)
            if existing_record is not None:
                self._runtime_records[key] = existing_record.model_copy(
                    update={
                        "status": "removed",
                        "summary": f"MCP client '{key}' has been removed.",
                        "connected": False,
                    },
                )

        if old_client is not None:
            logger.debug(f"Removing MCP client: {key}")
            try:
                await old_client.close()
            except Exception as e:
                logger.warning(f"Error closing MCP client '{key}': {e}")

    async def close_all(self) -> None:
        """Close all MCP clients.

        Called during application shutdown.
        """
        async with self._lock:
            clients_snapshot = list(self._clients.items())
            self._clients.clear()
            for key, record in list(self._runtime_records.items()):
                self._runtime_records[key] = record.model_copy(
                    update={
                        "status": "closing",
                        "summary": f"MCP client '{key}' is closing.",
                        "connected": False,
                    },
                )

        logger.debug("Closing all MCP clients")
        for key, client in clients_snapshot:
            if client is not None:
                try:
                    await client.close()
                except Exception as e:
                    logger.warning(f"Error closing MCP client '{key}': {e}")

    async def _add_client(
        self,
        key: str,
        client_config: "MCPClientConfig",
        timeout: float = 60.0,
        init_mode: str = "warn",
    ) -> None:
        """Add a new client (used during initial setup).

        Args:
            key: Client identifier
            client_config: Client configuration
            timeout: Connection timeout in seconds (default 60s)
        """
        await self._set_runtime_record(
            key,
            client_config,
            status="connecting",
            init_mode="strict" if init_mode == "strict" else "warn",
            connect_timeout_seconds=timeout,
            summary=f"MCP client '{key}' is connecting.",
        )
        client = self._build_client(client_config)

        # Add timeout to prevent indefinite blocking
        await asyncio.wait_for(client.connect(), timeout=timeout)

        async with self._lock:
            self._clients[key] = client
            self._runtime_records[key] = build_mcp_runtime_record(
                key,
                client_config,
                status="ready",
                init_mode="strict" if init_mode == "strict" else "warn",
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
    ) -> None:
        async with self._lock:
            self._runtime_records[key] = build_mcp_runtime_record(
                key,
                client_config,
                status=status,  # type: ignore[arg-type]
                init_mode=init_mode,  # type: ignore[arg-type]
                connect_timeout_seconds=connect_timeout_seconds,
                error=error,
                summary=summary,
                connected=connected,
            )
