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
