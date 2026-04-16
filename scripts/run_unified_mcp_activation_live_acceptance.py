# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import logging
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import threading
import time
from types import ModuleType
from typing import Any
import warnings


def _ensure_repo_src_on_sys_path() -> None:
    repo_src = str(Path(__file__).resolve().parents[1] / "src")
    if repo_src not in sys.path:
        sys.path.insert(0, repo_src)


def _ensure_repo_src_in_environment() -> None:
    repo_src = str(Path(__file__).resolve().parents[1] / "src")
    current_pythonpath = [
        item
        for item in os.environ.get("PYTHONPATH", "").split(os.pathsep)
        if item
    ]
    if repo_src not in current_pythonpath:
        os.environ["PYTHONPATH"] = os.pathsep.join([repo_src, *current_pythonpath])


_ensure_repo_src_on_sys_path()
_ensure_repo_src_in_environment()


def _prepare_third_party_runtime_log_filters() -> None:
    logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)
    with contextlib.suppress(ImportError):
        from loguru import logger as loguru_logger

        loguru_logger.remove()
        loguru_logger.add(sys.stderr, level="WARNING")


def _prepare_runtime_noise_filters() -> None:
    # Keep the live acceptance output focused on our own failures instead of
    # known third-party startup noise.
    os.environ.setdefault("NUMEXPR_MAX_THREADS", "16")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "16")
    _prepare_third_party_runtime_log_filters()
    warning_rules = [
        "ignore:websockets.legacy is deprecated:DeprecationWarning:websockets.legacy",
        "ignore:websockets.server.WebSocketServerProtocol is deprecated:"
        "DeprecationWarning:uvicorn.protocols.websockets.websockets_impl",
    ]
    existing_warning_rules = [
        item
        for item in os.environ.get("PYTHONWARNINGS", "").split(",")
        if item
    ]
    os.environ["PYTHONWARNINGS"] = ",".join(
        warning_rules
        + [
            item
            for item in existing_warning_rules
            if item not in warning_rules
        ]
    )
    warnings.filterwarnings(
        "ignore",
        message=r"websockets\.legacy is deprecated.*",
        category=DeprecationWarning,
        module=r"websockets\.legacy(\..*)?$",
    )
    warnings.filterwarnings(
        "ignore",
        message=r"websockets\.server\.WebSocketServerProtocol is deprecated",
        category=DeprecationWarning,
        module=r"uvicorn\.protocols\.websockets\.websockets_impl$",
    )


_prepare_runtime_noise_filters()

import httpx
import uvicorn


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _copy_default_provider_secrets(secret_dir: Path) -> None:
    default_providers = Path.home() / ".copaw.secret" / "providers"
    if not default_providers.exists():
        return
    target = secret_dir / "providers"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(default_providers, target, dirs_exist_ok=True)


def _build_live_config():
    from copaw.adapters.desktop import build_windows_desktop_mcp_client_config
    from copaw.config.config import Config, MCPClientConfig, MCPConfig

    stateless_payload = build_windows_desktop_mcp_client_config(enabled=True)
    stateless_payload["name"] = "Windows Desktop Stateless"
    stateless_payload["env"] = {}

    auth_payload = build_windows_desktop_mcp_client_config(enabled=True)
    auth_payload["name"] = "Windows Desktop Auth"
    auth_payload["env"] = {
        "PYTHONIOENCODING": "utf-8",
        "COPAW_TEST_TOKEN": "present",
    }

    return Config(
        mcp=MCPConfig(
            clients={
                "desktop_windows_stateless": MCPClientConfig(**stateless_payload),
                "desktop_windows_auth": MCPClientConfig(**auth_payload),
            }
        )
    )


def _prepare_isolated_working_dir() -> tuple[Path, Path]:
    working_dir = Path(tempfile.mkdtemp(prefix="copaw-mcp-live-")).resolve()
    secret_dir = Path(f"{working_dir}.secret").resolve()
    os.environ["COPAW_WORKING_DIR"] = str(working_dir)
    os.environ["COPAW_SECRET_DIR"] = str(secret_dir)
    os.environ.setdefault("COPAW_LOG_LEVEL", "warning")
    _copy_default_provider_secrets(secret_dir)

    from copaw.config.utils import save_config

    save_config(_build_live_config(), working_dir / "config.json")
    return working_dir, secret_dir


def _reload_app_module() -> ModuleType:
    import copaw.app._app as app_module

    return importlib.reload(app_module)


class _LiveServer:
    def __init__(self, app, *, host: str, port: int) -> None:
        self._app = app
        self._host = host
        self._port = port
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: uvicorn.Server | None = None
        self._thread_error: BaseException | None = None

    @property
    def port(self) -> int:
        return self._port

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            self._server = uvicorn.Server(
                uvicorn.Config(
                    self._app,
                    host=self._host,
                    port=self._port,
                    log_level="warning",
                    lifespan="on",
                    ws="wsproto",
                )
            )
            loop.run_until_complete(self._server.serve())
        except BaseException as exc:  # pragma: no cover - live-only
            self._thread_error = exc
            raise
        finally:
            loop.close()

    def start(self) -> None:
        self._thread.start()
        base_url = f"http://{self._host}:{self._port}"
        deadline = time.time() + 120.0
        last_error: Exception | None = None
        while time.time() < deadline:
            if self._thread_error is not None:
                raise RuntimeError(f"live server crashed during startup: {self._thread_error}")
            try:
                response = httpx.get(
                    f"{base_url}/api/capability-market/install-templates/document-office-bridge",
                    timeout=5.0,
                )
                if response.status_code == 200:
                    return
            except Exception as exc:
                last_error = exc
            time.sleep(0.5)
        raise RuntimeError(f"live server did not become ready in time: {last_error}")

    def run_coro(self, coro, *, timeout: float = 60.0):
        if self._loop is None:
            raise RuntimeError("live server event loop is not ready")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.should_exit = True
        self._thread.join(timeout=60.0)
        if self._thread.is_alive():
            raise RuntimeError("live server did not stop cleanly")


def _request_json(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.request(method, path, json=json_body)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise AssertionError(f"{path} did not return a JSON object")
    return payload


def _run_host_attached_round(client: httpx.Client) -> dict[str, Any]:
    document_doctor = _request_json(
        client,
        "GET",
        "/api/capability-market/install-templates/document-office-bridge/doctor",
    )
    document_activate = _request_json(
        client,
        "POST",
        "/api/capability-market/install-templates/document-office-bridge/activate",
        json_body={
            "config": {
                "session_id": "live-doc-1",
                "document_family": "documents",
            }
        },
    )
    host_watchers_example = _request_json(
        client,
        "POST",
        "/api/capability-market/install-templates/host-watchers/example-run",
        json_body={
            "config": {
                "session_id": "live-watch-1",
                "watcher_family": "downloads",
            }
        },
    )
    windows_apps_example = _request_json(
        client,
        "POST",
        "/api/capability-market/install-templates/windows-app-adapters/example-run",
        json_body={
            "config": {
                "session_id": "live-win-1",
                "adapter_ref": "app-adapter:excel",
            }
        },
    )
    browser_activate = _request_json(
        client,
        "POST",
        "/api/capability-market/install-templates/browser-companion/activate",
        json_body={
            "config": {
                "session_id": "live-browser-1",
            }
        },
    )

    _assert(document_activate["status"] == "ready", "document bridge activate failed")
    _assert(
        host_watchers_example["activation"]["status"] == "ready",
        "host watchers activation did not become ready",
    )
    _assert(
        windows_apps_example["activation"]["status"] == "ready",
        "windows app adapters activation did not become ready",
    )
    _assert(browser_activate["status"] == "ready", "browser companion activate failed")

    return {
        "document_doctor": document_doctor,
        "document_activate": document_activate,
        "host_watchers_example": host_watchers_example,
        "windows_app_adapters_example": windows_apps_example,
        "browser_companion_activate": browser_activate,
    }


def _inject_failed_runtime_state(
    server: _LiveServer,
    app_module: ModuleType,
    client_key: str,
    *,
    reason: str,
) -> None:
    async def _inject() -> None:
        manager = app_module.app.state.mcp_manager
        config = await manager.get_client_config(client_key)
        if config is None:
            raise RuntimeError(f"missing live MCP client config for {client_key}")
        async with manager._lock:  # noqa: SLF001 - live fault injection only
            detached_client = manager._clients.pop(client_key, None)  # noqa: SLF001
            if detached_client is not None:
                leaked_clients = getattr(
                    app_module.app.state,
                    "_mcp_activation_fault_clients",
                    None,
                )
                if not isinstance(leaked_clients, list):
                    leaked_clients = []
                    setattr(
                        app_module.app.state,
                        "_mcp_activation_fault_clients",
                        leaked_clients,
                    )
                leaked_clients.append(detached_client)
        await manager._set_runtime_record(  # noqa: SLF001
            client_key,
            config,
            status="failed",
            init_mode="warn",
            connect_timeout_seconds=60.0,
            error=reason,
            summary=f"Injected live fault for {client_key}: {reason}",
            connected=False,
            last_outcome="connect_failed",
        )

    server.run_coro(_inject())


def _run_mcp_execution_round(
    client: httpx.Client,
    server: _LiveServer,
    app_module: ModuleType,
) -> dict[str, Any]:
    _inject_failed_runtime_state(
        server,
        app_module,
        "desktop_windows_stateless",
        reason="runtime unavailable during live acceptance",
    )
    stateless = _request_json(
        client,
        "POST",
        "/api/runtime-center/external-runtimes/actions",
        json_body={
            "capability_id": "mcp:desktop_windows_stateless",
            "action": "run",
            "tool_name": "get_foreground_window",
            "tool_args": {},
        },
    )
    _assert(stateless["success"] is True, "stateless MCP execution failed")
    _assert(
        stateless["output"]["activation"]["operations"] == ["reconnect-runtime-client"],
        "stateless MCP activation did not reconnect through the shared plane",
    )

    _inject_failed_runtime_state(
        server,
        app_module,
        "desktop_windows_auth",
        reason="OAuth token expired in live acceptance",
    )
    auth_bound = _request_json(
        client,
        "POST",
        "/api/runtime-center/external-runtimes/actions",
        json_body={
            "capability_id": "mcp:desktop_windows_auth",
            "action": "run",
            "tool_name": "get_foreground_window",
            "tool_args": {},
        },
    )
    _assert(auth_bound["success"] is True, "auth-bound MCP execution failed")
    _assert(
        auth_bound["output"]["activation"]["operations"] == ["refresh-auth-runtime"],
        "auth-bound MCP activation did not refresh through the shared plane",
    )

    workspace = _request_json(
        client,
        "POST",
        "/api/runtime-center/external-runtimes/actions",
        json_body={
            "capability_id": "mcp:desktop_windows_stateless",
            "action": "run",
            "tool_name": "get_foreground_window",
            "tool_args": {},
            "scope_ref": "assignment:live-workspace-1",
            "mcp_scope_overlay": {
                "scope_ref": "assignment:live-workspace-1",
                "parent_scope_ref": "seat:live-primary",
                "overlay_mode": "additive",
                "clients": {
                    "desktop_windows_stateless": _build_live_config()
                    .mcp.clients["desktop_windows_stateless"]
                    .model_dump(mode="json")
                },
            },
        },
    )
    _assert(workspace["success"] is True, "workspace-bound MCP execution failed")
    _assert(
        workspace["output"]["activation"]["operations"] == ["mount-scope-overlay"],
        "workspace-bound MCP activation did not mount a scope overlay",
    )

    return {
        "stateless": stateless,
        "auth_bound": auth_bound,
        "workspace_bound": workspace,
    }


def _run_live_round(
    client: httpx.Client,
    server: _LiveServer,
    app_module: ModuleType,
) -> dict[str, Any]:
    capabilities = client.get("/api/capability-market/capabilities")
    capabilities.raise_for_status()
    capability_ids = {item["id"] for item in capabilities.json()}
    _assert(
        "mcp:desktop_windows_stateless" in capability_ids,
        "stateless live MCP capability was not registered",
    )
    _assert(
        "mcp:desktop_windows_auth" in capability_ids,
        "auth-bound live MCP capability was not registered",
    )

    return {
        "self_check": _request_json(client, "GET", "/api/system/self-check"),
        "host_attached": _run_host_attached_round(client),
        "mcp_execution": _run_mcp_execution_round(client, server, app_module),
    }


def _compare_restart_persistence(result: dict[str, Any]) -> None:
    round_1_host = result["round_1"]["host_attached"]
    round_2_host = result["round_2_after_restart"]["host_attached"]
    _assert(
        round_1_host["document_activate"]["runtime"]["session_mount_id"]
        == round_2_host["document_activate"]["runtime"]["session_mount_id"],
        "document bridge session mount did not persist across restart",
    )
    _assert(
        round_1_host["host_watchers_example"]["activation"]["runtime"]["session_mount_id"]
        == round_2_host["host_watchers_example"]["activation"]["runtime"]["session_mount_id"],
        "host watchers session mount did not persist across restart",
    )
    _assert(
        round_1_host["windows_app_adapters_example"]["activation"]["runtime"]["session_mount_id"]
        == round_2_host["windows_app_adapters_example"]["activation"]["runtime"]["session_mount_id"],
        "windows app adapter session mount did not persist across restart",
    )
    _assert(
        round_1_host["browser_companion_activate"]["runtime"]["session_mount_id"]
        == round_2_host["browser_companion_activate"]["runtime"]["session_mount_id"],
        "browser companion session mount did not persist across restart",
    )


def _run_server_round(app_module: ModuleType) -> dict[str, Any]:
    server = _LiveServer(app_module.app, host="127.0.0.1", port=_find_free_port())
    server.start()
    client = httpx.Client(
        base_url=f"http://127.0.0.1:{server.port}",
        timeout=120.0,
    )
    try:
        return _run_live_round(client, server, app_module)
    finally:
        client.close()
        server.stop()


def main() -> None:
    working_dir, secret_dir = _prepare_isolated_working_dir()
    result: dict[str, Any] = {
        "working_dir": str(working_dir),
        "secret_dir": str(secret_dir),
    }

    app_module = _reload_app_module()
    result["round_1"] = _run_server_round(app_module)

    app_module = _reload_app_module()
    result["round_2_after_restart"] = _run_server_round(app_module)

    _compare_restart_persistence(result)
    result_path = working_dir / "unified_mcp_activation_live_acceptance.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"live acceptance result: {result_path}")


if __name__ == "__main__":
    main()
