# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
import sys

import pytest

from copaw.adapters.desktop import build_windows_desktop_mcp_client_config
from copaw.app.mcp.manager import MCPClientManager
from copaw.app.mcp.runtime_contract import build_mcp_trial_contract
from copaw.config.config import MCPClientConfig, MCPConfig
from copaw.kernel import TaskDelegationService
from copaw.kernel.models import KernelTask


class _FakeClient:
    def __init__(
        self,
        name: str,
        *,
        fail_connect: bool = False,
        fail_close: bool = False,
    ) -> None:
        self.name = name
        self.fail_connect = fail_connect
        self.fail_close = fail_close
        self.connect_calls = 0
        self.close_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1
        if self.fail_connect:
            raise RuntimeError("connect failed")

    async def close(self) -> None:
        self.close_calls += 1
        if self.fail_close:
            raise RuntimeError("close failed")


class _RecordingMCPManager:
    def __init__(self) -> None:
        self.mount_calls: list[dict[str, object]] = []
        self.clear_calls: list[str] = []

    async def mount_scope_overlay(
        self,
        scope_ref: str,
        config,
        *,
        parent_scope_ref: str | None = None,
        additive: bool = True,
        timeout: float = 60.0,
    ) -> None:
        self.mount_calls.append(
            {
                "scope_ref": scope_ref,
                "parent_scope_ref": parent_scope_ref,
                "config": config,
                "additive": additive,
                "timeout": timeout,
            },
        )

    async def clear_scope_overlay(self, scope_ref: str) -> None:
        self.clear_calls.append(scope_ref)


def test_build_mcp_trial_contract_projects_local_scope_and_rollback_boundary() -> None:
    contract = build_mcp_trial_contract(
        baseline_ref="mcp:desktop_windows",
        challenger_ref="template:desktop-windows:desktop_windows",
        client_key="desktop_windows",
        target_agent_id="industry-solution-lead-demo",
        target_role_id="solution-lead",
        selected_scope="seat",
        selected_seat_ref="env-browser-primary",
        target_capability_ids=["mcp:desktop_windows"],
        rollback_target_ids=["mcp:desktop_windows"],
    )

    assert contract.contract_kind == "mcp"
    assert contract.target_capability_family == "mcp"
    assert contract.selected_scope == "seat"
    assert contract.selected_seat_ref == "env-browser-primary"
    assert contract.rollback.client_key == "desktop_windows"
    assert contract.rollback.rollback_target_ids == ["mcp:desktop_windows"]
    assert contract.rollback.fallback_action == "disable_mcp_client"


def _child_run_overlay_payload(
    scope_ref: str | None = None,
    *,
    seat_scope_ref: str | None = None,
    session_scope_ref: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "clients": {
            "scoped_worker": {
                "name": "scoped_worker",
                "enabled": True,
                "transport": "stdio",
                "command": "python",
                "args": ["-m", "scoped_worker"],
            },
        },
    }
    if scope_ref is not None:
        payload["scope_ref"] = scope_ref
    if seat_scope_ref is not None:
        payload["seat_scope_ref"] = seat_scope_ref
    if session_scope_ref is not None:
        payload["session_scope_ref"] = session_scope_ref
    return payload


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


@pytest.mark.asyncio
async def test_mcp_manager_replace_surfaces_old_client_close_failure(monkeypatch) -> None:
    manager = MCPClientManager()
    build_count = 0

    def _fake_build_client(cfg: MCPClientConfig) -> _FakeClient:
        nonlocal build_count
        build_count += 1
        if build_count == 1:
            return _FakeClient(cfg.name, fail_close=True)
        return _FakeClient(cfg.name)

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

    record = await manager.get_runtime_record("worker")
    assert record is not None
    assert record.status == "ready"
    assert record.connected is True
    assert record.last_error == "close failed"
    assert record.reload_state.last_outcome == "close_failed"
    assert record.reload_state.dirty is False
    assert record.reload_state.pending_reload is False


@pytest.mark.asyncio
async def test_mcp_manager_failed_replace_keeps_steady_client_and_marks_dirty(
    monkeypatch,
) -> None:
    manager = MCPClientManager()
    build_count = 0
    steady_client: _FakeClient | None = None

    def _fake_build_client(cfg: MCPClientConfig) -> _FakeClient:
        nonlocal build_count, steady_client
        build_count += 1
        if build_count == 1:
            steady_client = _FakeClient(cfg.name)
            return steady_client
        return _FakeClient(cfg.name, fail_connect=True)

    monkeypatch.setattr(MCPClientManager, "_build_client", staticmethod(_fake_build_client))

    base_cfg = MCPClientConfig(
        name="worker",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "worker"],
    )
    next_cfg = MCPClientConfig(
        name="worker",
        enabled=True,
        transport="stdio",
        command="python3",
        args=["-m", "worker_v2"],
    )
    await manager.init_from_config(MCPConfig(clients={"worker": base_cfg}))

    with pytest.raises(RuntimeError, match="connect failed"):
        await manager.replace_client("worker", next_cfg, timeout=3.0)

    record = await manager.get_runtime_record("worker")
    assert record is not None
    assert record.status == "ready"
    assert record.connected is True
    assert record.last_error == "connect failed"
    assert record.rebuild_info.command == "python"
    assert record.reload_state.last_outcome == "connect_failed"
    assert record.reload_state.dirty is True
    assert record.reload_state.pending_reload is True
    assert record.reload_state.pending_spec is not None
    assert record.reload_state.pending_spec.command == "python3"
    assert await manager.get_client("worker") is steady_client


@pytest.mark.asyncio
async def test_mcp_manager_note_reload_pending_tracks_pending_spec(monkeypatch) -> None:
    manager = MCPClientManager()

    monkeypatch.setattr(
        MCPClientManager,
        "_build_client",
        staticmethod(lambda cfg: _FakeClient(cfg.name)),
    )

    base_cfg = MCPClientConfig(
        name="worker",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "worker"],
    )
    next_cfg = MCPClientConfig(
        name="worker",
        enabled=True,
        transport="stdio",
        command="python3",
        args=["-m", "worker_v2"],
    )
    await manager.init_from_config(MCPConfig(clients={"worker": base_cfg}))

    await manager.note_reload_pending("worker", next_cfg, reason="watcher-busy")

    record = await manager.get_runtime_record("worker")
    assert record is not None
    assert record.status == "ready"
    assert record.connected is True
    assert record.rebuild_info.command == "python"
    assert record.reload_state.last_outcome == "pending_reload"
    assert record.reload_state.pending_reload is True
    assert record.reload_state.dirty is True
    assert record.reload_state.pending_reason == "watcher-busy"
    assert record.reload_state.pending_spec is not None
    assert record.reload_state.pending_spec.command == "python3"


@pytest.mark.asyncio
async def test_mcp_manager_scoped_overlay_is_additive_and_local(monkeypatch) -> None:
    manager = MCPClientManager()

    monkeypatch.setattr(
        MCPClientManager,
        "_build_client",
        staticmethod(lambda cfg: _FakeClient(cfg.name)),
    )

    base_cfg = MCPClientConfig(
        name="worker",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "worker"],
    )
    overlay_cfg = MCPClientConfig(
        name="scoped_worker",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "scoped_worker"],
    )
    await manager.init_from_config(MCPConfig(clients={"worker": base_cfg}))

    await manager.mount_scope_overlay(
        "assignment:task-1",
        MCPConfig(clients={"scoped_worker": overlay_cfg}),
        additive=True,
        timeout=3.0,
    )

    global_clients = await manager.get_clients()
    scoped_clients = await manager.get_clients(scope_ref="assignment:task-1")

    assert [client.name for client in global_clients] == ["worker"]
    assert sorted(client.name for client in scoped_clients) == ["scoped_worker", "worker"]
    assert await manager.get_client("scoped_worker") is None
    assert await manager.get_client("scoped_worker", scope_ref="assignment:task-1") is not None

    overlay_record = await manager.get_runtime_record(
        "scoped_worker",
        scope_ref="assignment:task-1",
    )
    assert overlay_record is not None
    assert overlay_record.reload_state.overlay_scope == "assignment:task-1"
    assert overlay_record.reload_state.overlay_mode == "additive"


@pytest.mark.asyncio
async def test_mcp_manager_scoped_overlay_replace_hides_base_until_cleared(
    monkeypatch,
) -> None:
    manager = MCPClientManager()

    monkeypatch.setattr(
        MCPClientManager,
        "_build_client",
        staticmethod(lambda cfg: _FakeClient(cfg.name)),
    )

    base_cfg = MCPClientConfig(
        name="worker",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "worker"],
    )
    overlay_cfg = MCPClientConfig(
        name="scoped_worker",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "scoped_worker"],
    )
    await manager.init_from_config(MCPConfig(clients={"worker": base_cfg}))

    await manager.mount_scope_overlay(
        "assignment:task-2",
        MCPConfig(clients={"scoped_worker": overlay_cfg}),
        additive=False,
        timeout=3.0,
    )

    scoped_clients = await manager.get_clients(scope_ref="assignment:task-2")
    assert [client.name for client in scoped_clients] == ["scoped_worker"]

    overlay_record = await manager.get_runtime_record(
        "scoped_worker",
        scope_ref="assignment:task-2",
    )
    assert overlay_record is not None
    assert overlay_record.session_policy.cache_scope == "manager-overlay-scope"
    assert overlay_record.reload_state.overlay_scope == "assignment:task-2"
    assert overlay_record.reload_state.overlay_mode == "replace"
    assert overlay_record.reload_state.last_outcome == "overlay_mounted"

    await manager.clear_scope_overlay("assignment:task-2")

    cleared_clients = await manager.get_clients(scope_ref="assignment:task-2")
    assert [client.name for client in cleared_clients] == ["worker"]

    removed_record = await manager.get_runtime_record(
        "scoped_worker",
        scope_ref="assignment:task-2",
    )
    assert removed_record is not None
    assert removed_record.status == "removed"
    assert removed_record.reload_state.overlay_scope == "assignment:task-2"
    assert removed_record.reload_state.overlay_mode == "replace"
    assert removed_record.reload_state.last_outcome == "overlay_removed"


@pytest.mark.asyncio
async def test_mcp_manager_session_scope_inherits_selected_seat_overlay_without_cross_seat_leak(
    monkeypatch,
) -> None:
    manager = MCPClientManager()

    monkeypatch.setattr(
        MCPClientManager,
        "_build_client",
        staticmethod(lambda cfg: _FakeClient(cfg.name)),
    )

    base_cfg = MCPClientConfig(
        name="worker",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "worker"],
    )
    alpha_cfg = MCPClientConfig(
        name="alpha_browser",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "alpha_browser"],
    )
    beta_cfg = MCPClientConfig(
        name="beta_browser",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "beta_browser"],
    )
    session_cfg = MCPClientConfig(
        name="temp_browser",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "temp_browser"],
    )
    await manager.init_from_config(MCPConfig(clients={"worker": base_cfg}))
    await manager.mount_scope_overlay(
        "seat:alpha",
        MCPConfig(clients={"alpha_browser": alpha_cfg}),
        additive=True,
        timeout=3.0,
    )
    await manager.mount_scope_overlay(
        "seat:beta",
        MCPConfig(clients={"beta_browser": beta_cfg}),
        additive=True,
        timeout=3.0,
    )
    await manager.mount_scope_overlay(
        "session:alpha:1",
        MCPConfig(clients={"temp_browser": session_cfg}),
        parent_scope_ref="seat:alpha",
        additive=True,
        timeout=3.0,
    )

    alpha_session_clients = await manager.get_clients(scope_ref="session:alpha:1")
    beta_seat_clients = await manager.get_clients(scope_ref="seat:beta")

    assert sorted(client.name for client in alpha_session_clients) == [
        "alpha_browser",
        "temp_browser",
        "worker",
    ]
    assert sorted(client.name for client in beta_seat_clients) == [
        "beta_browser",
        "worker",
    ]
    assert await manager.get_client("alpha_browser", scope_ref="session:alpha:1") is not None
    assert await manager.get_client("beta_browser", scope_ref="session:alpha:1") is None
    assert await manager.get_client("temp_browser", scope_ref="seat:alpha") is None

    await manager.clear_scope_overlay("session:alpha:1")

    cleared_alpha_clients = await manager.get_clients(scope_ref="seat:alpha")
    assert sorted(client.name for client in cleared_alpha_clients) == [
        "alpha_browser",
        "worker",
    ]


@pytest.mark.asyncio
async def test_mcp_manager_failed_overlay_mount_preserves_previous_scope_clients(
    monkeypatch,
) -> None:
    manager = MCPClientManager()
    build_calls = 0

    def _fake_build_client(cfg: MCPClientConfig) -> _FakeClient:
        nonlocal build_calls
        build_calls += 1
        if build_calls == 3:
            return _FakeClient(cfg.name, fail_connect=True)
        return _FakeClient(cfg.name)

    monkeypatch.setattr(MCPClientManager, "_build_client", staticmethod(_fake_build_client))

    base_cfg = MCPClientConfig(
        name="worker",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "worker"],
    )
    first_overlay_cfg = MCPClientConfig(
        name="scoped_worker_v1",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "scoped_worker_v1"],
    )
    failing_overlay_cfg = MCPClientConfig(
        name="scoped_worker_v2",
        enabled=True,
        transport="stdio",
        command="python",
        args=["-m", "scoped_worker_v2"],
    )
    await manager.init_from_config(MCPConfig(clients={"worker": base_cfg}))
    await manager.mount_scope_overlay(
        "assignment:task-3",
        MCPConfig(clients={"scoped_worker_v1": first_overlay_cfg}),
        additive=True,
        timeout=3.0,
    )

    with pytest.raises(RuntimeError, match="connect failed"):
        await manager.mount_scope_overlay(
            "assignment:task-3",
            MCPConfig(clients={"scoped_worker_v2": failing_overlay_cfg}),
            additive=True,
            timeout=3.0,
        )

    scoped_clients = await manager.get_clients(scope_ref="assignment:task-3")
    assert sorted(client.name for client in scoped_clients) == ["scoped_worker_v1", "worker"]
    assert await manager.get_client("scoped_worker_v1", scope_ref="assignment:task-3") is not None
    assert await manager.get_client("scoped_worker_v2", scope_ref="assignment:task-3") is None

    previous_record = await manager.get_runtime_record(
        "scoped_worker_v1",
        scope_ref="assignment:task-3",
    )
    failed_record = await manager.get_runtime_record(
        "scoped_worker_v2",
        scope_ref="assignment:task-3",
    )
    assert previous_record is not None
    assert previous_record.status == "ready"
    assert previous_record.reload_state.last_outcome == "overlay_mounted"
    assert failed_record is not None
    assert failed_record.status == "failed"
    assert failed_record.reload_state.overlay_scope == "assignment:task-3"
    assert failed_record.reload_state.overlay_mode == "additive"
    assert failed_record.reload_state.last_outcome == "connect_failed"


@pytest.mark.asyncio
async def test_child_run_direct_delegation_mounts_and_clears_scoped_overlay_on_failure() -> None:
    mcp_manager = _RecordingMCPManager()

    class _FailingDispatcher:
        def __init__(self) -> None:
            self._capability_service = SimpleNamespace(_mcp_manager=mcp_manager)

        async def execute_task(self, task_id: str):
            raise RuntimeError(f"boom:{task_id}")

    service = TaskDelegationService(
        task_repository=SimpleNamespace(),
        task_runtime_repository=SimpleNamespace(),
        kernel_dispatcher=_FailingDispatcher(),
    )
    child_task = KernelTask(
        title="Child run with scoped MCP",
        capability_ref="system:dispatch_query",
        owner_agent_id="agent-1",
        payload={
            "meta": {
                "mcp_scope_overlay": _child_run_overlay_payload(
                    "assignment:delegated-child-run",
                ),
            },
        },
    )

    with pytest.raises(RuntimeError, match="boom:"):
        await service._execute_delegated_child_task(
            child_task,
            mailbox_item=None,
        )

    assert [call["scope_ref"] for call in mcp_manager.mount_calls] == [
        "assignment:delegated-child-run",
    ]
    assert mcp_manager.mount_calls[0]["additive"] is True
    mounted_config = mcp_manager.mount_calls[0]["config"]
    assert mounted_config.clients["scoped_worker"].command == "python"
    assert mcp_manager.clear_calls == ["assignment:delegated-child-run"]


@pytest.mark.asyncio
async def test_child_run_direct_delegation_mounts_session_overlay_under_selected_seat_scope() -> None:
    mcp_manager = _RecordingMCPManager()

    class _SuccessfulDispatcher:
        def __init__(self) -> None:
            self._capability_service = SimpleNamespace(_mcp_manager=mcp_manager)

        async def execute_task(self, task_id: str):
            return SimpleNamespace(phase="completed", summary=f"ok:{task_id}")

    service = TaskDelegationService(
        task_repository=SimpleNamespace(),
        task_runtime_repository=SimpleNamespace(),
        kernel_dispatcher=_SuccessfulDispatcher(),
    )
    child_task = KernelTask(
        title="Child run with seat-session scoped MCP",
        capability_ref="system:dispatch_query",
        owner_agent_id="agent-1",
        payload={
            "meta": {
                "mcp_scope_overlay": _child_run_overlay_payload(
                    seat_scope_ref="seat:agent-1",
                    session_scope_ref="session:agent-1:delegated-child-run",
                ),
            },
        },
    )

    result = await service._execute_delegated_child_task(
        child_task,
        mailbox_item=None,
    )

    assert result.phase == "completed"
    assert [call["scope_ref"] for call in mcp_manager.mount_calls] == [
        "session:agent-1:delegated-child-run",
    ]
    assert [call["parent_scope_ref"] for call in mcp_manager.mount_calls] == [
        "seat:agent-1",
    ]
    assert mcp_manager.clear_calls == ["session:agent-1:delegated-child-run"]


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows desktop MCP host")
async def test_windows_desktop_template_connects_and_calls_real_tool() -> None:
    manager = MCPClientManager()
    config = MCPConfig(
        clients={
            "desktop_windows": MCPClientConfig(
                **build_windows_desktop_mcp_client_config(enabled=True),
            ),
        },
    )

    try:
        await manager.init_from_config(config, strict=False, timeout=20.0)
        record = await manager.get_runtime_record("desktop_windows")
        assert record is not None
        assert record.status == "ready"
        assert record.connected is True

        client = await manager.get_client("desktop_windows")
        assert client is not None

        callable_fn = await client.get_callable_function(
            "get_foreground_window",
            wrap_tool_result=True,
            execution_timeout=15.0,
        )
        response = await callable_fn()
        content = getattr(response, "content", None)
        assert isinstance(content, list)
        assert content
        payload = json.loads(str(content[0].get("text") or "{}"))
        assert payload["tool"] == "get_foreground_window"
        assert payload["success"] is True
        assert payload["handle"]
    finally:
        await manager.close_all()
