# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

import pytest

from copaw.app.mcp.manager import MCPClientManager
from copaw.config.config import MCPClientConfig, MCPConfig


class _FakeClient:
    def __init__(self, name: str, *, fail_connect: bool = False) -> None:
        self.name = name
        self.fail_connect = fail_connect
        self.connect_calls = 0
        self.close_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1
        if self.fail_connect:
            raise RuntimeError("connect failed")

    async def close(self) -> None:
        self.close_calls += 1


@pytest.mark.asyncio
async def test_mcp_manager_tracks_runtime_policy_and_status(monkeypatch) -> None:
    manager = MCPClientManager()
    clients: dict[str, _FakeClient] = {}

    def _fake_build_client(cfg: MCPClientConfig) -> _FakeClient:
        client = _FakeClient(cfg.name)
        clients[cfg.name] = client
        return client

    monkeypatch.setattr(MCPClientManager, "_build_client", staticmethod(_fake_build_client))

    config = MCPConfig(
        clients={
            "stdio_worker": MCPClientConfig(
                name="stdio_worker",
                enabled=True,
                transport="stdio",
                command="npx",
                args=["-y", "@copaw/mcp-worker"],
                env={"API_TOKEN": "secret"},
            ),
            "remote_browser": MCPClientConfig(
                name="remote_browser",
                enabled=True,
                transport="streamable_http",
                url="https://mcp.example.com",
                headers={"Authorization": "Bearer token"},
            ),
            "disabled_sidecar": MCPClientConfig(
                name="disabled_sidecar",
                enabled=False,
                transport="stdio",
                command="python",
                args=["-m", "mcp_sidecar"],
            ),
        },
    )

    await manager.init_from_config(config, strict=False, timeout=12.0)

    records = {record.key: record for record in await manager.list_runtime_records()}
    assert records["stdio_worker"].status == "ready"
    assert records["stdio_worker"].auth_policy.mode == "env"
    assert records["stdio_worker"].session_policy.mode == "stdio-process"
    assert records["stdio_worker"].error_policy.init_mode == "warn"
    assert records["stdio_worker"].error_policy.connect_timeout_seconds == 12.0
    assert records["stdio_worker"].rebuild_info.command == "npx"
    assert records["stdio_worker"].rebuild_info.env == {"API_TOKEN": "secret"}
    assert records["remote_browser"].status == "ready"
    assert records["remote_browser"].auth_policy.mode == "headers"
    assert records["remote_browser"].session_policy.mode == "streamable-http"
    assert records["remote_browser"].rebuild_info.headers == {
        "Authorization": "Bearer token",
    }
    assert records["disabled_sidecar"].status == "disabled"
    assert clients["stdio_worker"].connect_calls == 1
    assert clients["remote_browser"].connect_calls == 1


@pytest.mark.asyncio
async def test_mcp_manager_marks_strict_init_failures_with_runtime_record(monkeypatch) -> None:
    manager = MCPClientManager()

    monkeypatch.setattr(
        MCPClientManager,
        "_build_client",
        staticmethod(lambda cfg: _FakeClient(cfg.name, fail_connect=True)),
    )

    config = MCPConfig(
        clients={
            "broken": MCPClientConfig(
                name="broken",
                enabled=True,
                transport="stdio",
                command="python",
                args=["-m", "broken"],
            ),
        },
    )

    with pytest.raises(RuntimeError, match="connect failed"):
        await manager.init_from_config(config, strict=True, timeout=5.0)

    record = await manager.get_runtime_record("broken")
    assert record is not None
    assert record.status == "failed"
    assert record.error_policy.init_mode == "strict"
    assert "connect failed" in (record.last_error or "")


@pytest.mark.asyncio
async def test_mcp_manager_replace_remove_and_close_update_runtime_states(monkeypatch) -> None:
    manager = MCPClientManager()
    clients: list[_FakeClient] = []

    def _fake_build_client(cfg: MCPClientConfig) -> _FakeClient:
        client = _FakeClient(cfg.name)
        clients.append(client)
        return client

    monkeypatch.setattr(MCPClientManager, "_build_client", staticmethod(_fake_build_client))

    base_cfg = MCPClientConfig(
        name="worker",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "worker"],
    )
    await manager.init_from_config(MCPConfig(clients={"worker": base_cfg}))
    await manager.replace_client("worker", base_cfg, timeout=3.0)

    replaced = await manager.get_runtime_record("worker")
    assert replaced is not None
    assert replaced.status == "ready"
    assert replaced.connected is True

    await manager.remove_client("worker")
    removed = await manager.get_runtime_record("worker")
    assert removed is not None
    assert removed.status == "removed"

    await manager.init_from_config(MCPConfig(clients={"worker": base_cfg}))
    await manager.close_all()
    closing = await manager.get_runtime_record("worker")
    assert closing is not None
    assert closing.status == "closing"
    assert all(client.close_calls >= 1 for client in clients if client.connect_calls >= 1)
