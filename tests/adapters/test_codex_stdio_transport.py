# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


def _load_stdio_transport_type():
    spec = importlib.util.find_spec("copaw.adapters.executors.codex_stdio_transport")
    assert spec is not None
    module = importlib.import_module("copaw.adapters.executors.codex_stdio_transport")
    transport_type = getattr(module, "CodexStdioTransport", None)
    assert transport_type is not None
    return transport_type


def _write_fake_stdio_server(path: Path) -> None:
    path.write_text(
        """
import json
import sys

for raw_line in sys.stdin:
    line = raw_line.strip()
    if not line:
        continue
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        sys.stdout.write(json.dumps({
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {"serverInfo": {"name": "fake-codex", "version": "1.0"}}
        }) + "\\n")
        sys.stdout.flush()
        continue
    if method == "notifications/initialized":
        continue
    if method == "thread/start":
        sys.stdout.write(json.dumps({
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {"thread": {"id": "thread-1"}}
        }) + "\\n")
        sys.stdout.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "turn/plan/updated",
            "params": {"threadId": "thread-1", "plan": [{"step": "do work"}]}
        }) + "\\n")
        sys.stdout.flush()
        continue
    if method == "turn/start":
        sys.stdout.write(json.dumps({
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {"turn": {"id": "turn-1"}}
        }) + "\\n")
        sys.stdout.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "turn/completed",
            "params": {"threadId": "thread-1", "turn": {"id": "turn-1", "status": "completed"}}
        }) + "\\n")
        sys.stdout.flush()
        continue
""".strip(),
        encoding="utf-8",
    )


def _write_fake_stdio_approval_server(path: Path) -> None:
    path.write_text(
        """
import json
import sys

turn_start_request_id = None
approval_request_id = "approval-request-1"

for raw_line in sys.stdin:
    line = raw_line.strip()
    if not line:
        continue
    message = json.loads(line)
    method = message.get("method")
    if method == "initialize":
        sys.stdout.write(json.dumps({
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {"serverInfo": {"name": "fake-codex", "version": "1.0"}}
        }) + "\\n")
        sys.stdout.flush()
        continue
    if method == "notifications/initialized":
        continue
    if method == "thread/start":
        sys.stdout.write(json.dumps({
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {"thread": {"id": "thread-1"}}
        }) + "\\n")
        sys.stdout.flush()
        continue
    if method == "turn/start":
        turn_start_request_id = message["id"]
        sys.stdout.write(json.dumps({
            "jsonrpc": "2.0",
            "id": approval_request_id,
            "method": "approval/request",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "requestId": "approval-1",
                "summary": "Approve guarded command execution"
            }
        }) + "\\n")
        sys.stdout.flush()
        continue
    if message.get("id") == approval_request_id:
        result = dict(message.get("result") or {})
        sys.stdout.write(json.dumps({
            "jsonrpc": "2.0",
            "id": turn_start_request_id,
            "result": {
                "turn": {"id": "turn-1"},
                "approvalDecision": result.get("decision", "unknown")
            }
        }) + "\\n")
        sys.stdout.flush()
        continue
""".strip(),
        encoding="utf-8",
    )


def test_stdio_transport_launches_managed_child_process_and_initializes_session(
    tmp_path,
) -> None:
    transport_type = _load_stdio_transport_type()
    script_path = tmp_path / "fake_codex_stdio_server.py"
    _write_fake_stdio_server(script_path)
    transport = transport_type(
        codex_command=(sys.executable, str(script_path)),
        request_timeout_seconds=2.0,
        startup_timeout_seconds=2.0,
    )

    try:
        thread_response = transport.request("thread/start", {"cwd": str(tmp_path)})
        turn_response = transport.request(
            "turn/start",
            {
                "threadId": "thread-1",
                "cwd": str(tmp_path),
                "input": [{"type": "text", "text": "Do work"}],
            },
        )
    finally:
        transport.close()

    assert thread_response["result"]["thread"]["id"] == "thread-1"
    assert turn_response["result"]["turn"]["id"] == "turn-1"


def test_stdio_transport_subscribes_and_closes_thread_events(tmp_path) -> None:
    transport_type = _load_stdio_transport_type()
    script_path = tmp_path / "fake_codex_stdio_server.py"
    _write_fake_stdio_server(script_path)
    transport = transport_type(
        codex_command=(sys.executable, str(script_path)),
        request_timeout_seconds=2.0,
        startup_timeout_seconds=2.0,
    )

    try:
        transport.request("thread/start", {"cwd": str(tmp_path)})
        transport.request(
            "turn/start",
            {
                "threadId": "thread-1",
                "cwd": str(tmp_path),
                "input": [{"type": "text", "text": "Do work"}],
            },
        )
        event_stream = transport.subscribe_events("thread-1")
        events = [next(event_stream), next(event_stream)]
    finally:
        transport.close()

    assert [event["method"] for event in events] == [
        "turn/plan/updated",
        "turn/completed",
    ]


def test_stdio_transport_handles_sidecar_approval_server_requests(tmp_path) -> None:
    transport_type = _load_stdio_transport_type()
    script_path = tmp_path / "fake_codex_stdio_approval_server.py"
    _write_fake_stdio_approval_server(script_path)
    transport = transport_type(
        codex_command=(sys.executable, str(script_path)),
        request_timeout_seconds=2.0,
        startup_timeout_seconds=2.0,
    )
    approval_requests: list[dict[str, object]] = []

    try:
        transport.set_server_request_handler(
            lambda payload: approval_requests.append(dict(payload))
            or {"decision": "approved", "reason": "operator-approved"}
        )
        transport.request("thread/start", {"cwd": str(tmp_path)})
        turn_response = transport.request(
            "turn/start",
            {
                "threadId": "thread-1",
                "cwd": str(tmp_path),
                "input": [{"type": "text", "text": "Do guarded work"}],
            },
        )
    finally:
        transport.close()

    assert approval_requests
    assert approval_requests[0]["method"] == "approval/request"
    assert approval_requests[0]["params"]["requestId"] == "approval-1"
    assert turn_response["result"]["approvalDecision"] == "approved"


def test_stdio_transport_restart_reports_recovery_state(tmp_path) -> None:
    transport_type = _load_stdio_transport_type()
    script_path = tmp_path / "fake_codex_stdio_server.py"
    _write_fake_stdio_server(script_path)
    transport = transport_type(
        codex_command=(sys.executable, str(script_path)),
        request_timeout_seconds=2.0,
        startup_timeout_seconds=2.0,
    )

    try:
        transport.request("thread/start", {"cwd": str(tmp_path)})
        before_restart = transport.describe_sidecar()
        restart_status = transport.restart()
        after_restart = transport.describe_sidecar()
        transport.request("thread/start", {"cwd": str(tmp_path)})
        recovered = transport.describe_sidecar()
    finally:
        transport.close()

    assert before_restart["connected"] is True
    assert restart_status["restart_count"] == 1
    assert after_restart["connected"] is False
    assert recovered["connected"] is True


def test_stdio_transport_injects_writable_default_codex_home_for_managed_codex_launch(
    tmp_path,
    monkeypatch,
) -> None:
    module = importlib.import_module("copaw.adapters.executors.codex_stdio_transport")
    transport_type = getattr(module, "CodexStdioTransport")
    managed_root = tmp_path / "managed-sidecar"
    managed_root.mkdir(parents=True, exist_ok=True)
    codex_cmd = managed_root / "codex.cmd"
    codex_cmd.write_text("@ECHO off\n", encoding="utf-8")
    captured: dict[str, object] = {}

    class _DummyPipe:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

        def write(self, _text: str) -> None:
            return None

        def flush(self) -> None:
            return None

        def readline(self) -> str:
            return ""

    class _DummyProcess:
        def __init__(self, command, **kwargs) -> None:
            captured["command"] = list(command)
            captured["env"] = dict(kwargs.get("env") or {})
            self.stdin = _DummyPipe()
            self.stdout = _DummyPipe()
            self.pid = 321

        def poll(self):
            return None

        def terminate(self) -> None:
            return None

        def wait(self, timeout=None) -> int:
            return 0

        def kill(self) -> None:
            return None

    class _DummyThread:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def start(self) -> None:
            return None

    monkeypatch.setattr(module.subprocess, "Popen", _DummyProcess)
    monkeypatch.setattr(module.threading, "Thread", _DummyThread)
    user_home = tmp_path / "user-home"
    monkeypatch.setattr(module.Path, "home", lambda: user_home)

    transport = transport_type(
        codex_command=(str(codex_cmd), "app-server"),
        request_timeout_seconds=2.0,
        startup_timeout_seconds=2.0,
    )

    try:
        transport._ensure_connection()
    finally:
        transport.close()

    launch_env = dict(captured["env"])
    codex_home = Path(str(launch_env["CODEX_HOME"]))
    assert codex_home.exists()
    assert codex_home.is_dir()
    assert codex_home.parent == managed_root


def test_stdio_transport_prefers_existing_user_codex_home_for_managed_codex_launch(
    tmp_path,
    monkeypatch,
) -> None:
    module = importlib.import_module("copaw.adapters.executors.codex_stdio_transport")
    transport_type = getattr(module, "CodexStdioTransport")
    managed_root = tmp_path / "managed-sidecar"
    managed_root.mkdir(parents=True, exist_ok=True)
    codex_cmd = managed_root / "codex.cmd"
    codex_cmd.write_text("@ECHO off\n", encoding="utf-8")
    user_home = tmp_path / "user-home"
    user_codex_home = user_home / ".codex"
    user_codex_home.mkdir(parents=True, exist_ok=True)
    captured: dict[str, object] = {}

    class _DummyPipe:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

        def write(self, _text: str) -> None:
            return None

        def flush(self) -> None:
            return None

        def readline(self) -> str:
            return ""

    class _DummyProcess:
        def __init__(self, command, **kwargs) -> None:
            captured["command"] = list(command)
            captured["env"] = dict(kwargs.get("env") or {})
            self.stdin = _DummyPipe()
            self.stdout = _DummyPipe()
            self.pid = 321

        def poll(self):
            return None

        def terminate(self) -> None:
            return None

        def wait(self, timeout=None) -> int:
            return 0

        def kill(self) -> None:
            return None

    class _DummyThread:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def start(self) -> None:
            return None

    monkeypatch.setattr(module.subprocess, "Popen", _DummyProcess)
    monkeypatch.setattr(module.threading, "Thread", _DummyThread)
    monkeypatch.setattr(module.Path, "home", lambda: user_home)

    transport = transport_type(
        codex_command=(str(codex_cmd), "app-server"),
        request_timeout_seconds=2.0,
        startup_timeout_seconds=2.0,
    )

    try:
        transport._ensure_connection()
    finally:
        transport.close()

    launch_env = dict(captured["env"])
    assert Path(str(launch_env["CODEX_HOME"])) == user_codex_home


def test_stdio_transport_falls_back_when_user_codex_sessions_are_not_writable(
    tmp_path,
    monkeypatch,
) -> None:
    module = importlib.import_module("copaw.adapters.executors.codex_stdio_transport")
    transport_type = getattr(module, "CodexStdioTransport")
    managed_root = tmp_path / "managed-sidecar"
    managed_root.mkdir(parents=True, exist_ok=True)
    codex_cmd = managed_root / "codex.cmd"
    codex_cmd.write_text("@ECHO off\n", encoding="utf-8")
    user_home = tmp_path / "user-home"
    user_codex_home = user_home / ".codex"
    user_codex_home.mkdir(parents=True, exist_ok=True)
    blocked_sessions_root = user_codex_home / "sessions"
    captured: dict[str, object] = {}

    class _DummyPipe:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

        def write(self, _text: str) -> None:
            return None

        def flush(self) -> None:
            return None

        def readline(self) -> str:
            return ""

    class _DummyProcess:
        def __init__(self, command, **kwargs) -> None:
            captured["command"] = list(command)
            captured["env"] = dict(kwargs.get("env") or {})
            self.stdin = _DummyPipe()
            self.stdout = _DummyPipe()
            self.pid = 321

        def poll(self):
            return None

        def terminate(self) -> None:
            return None

        def wait(self, timeout=None) -> int:
            return 0

        def kill(self) -> None:
            return None

    class _DummyThread:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def start(self) -> None:
            return None

    original_mkdir = module.Path.mkdir

    def _guarded_mkdir(path_obj, *args, **kwargs):
        if Path(path_obj) == blocked_sessions_root:
            raise PermissionError("sessions root is not writable")
        return original_mkdir(path_obj, *args, **kwargs)

    monkeypatch.setattr(module.subprocess, "Popen", _DummyProcess)
    monkeypatch.setattr(module.threading, "Thread", _DummyThread)
    monkeypatch.setattr(module.Path, "home", lambda: user_home)
    monkeypatch.setattr(module.Path, "mkdir", _guarded_mkdir)

    transport = transport_type(
        codex_command=(str(codex_cmd), "app-server"),
        request_timeout_seconds=2.0,
        startup_timeout_seconds=2.0,
    )

    try:
        transport._ensure_connection()
    finally:
        transport.close()

    launch_env = dict(captured["env"])
    codex_home = Path(str(launch_env["CODEX_HOME"]))
    assert codex_home != user_codex_home
    assert codex_home.parent == managed_root
