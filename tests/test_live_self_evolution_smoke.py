# -*- coding: utf-8 -*-
from __future__ import annotations

import urllib.parse

from scripts.run_live_self_evolution_smoke import (
    _ensure_clean_browser_runtime_session,
    _load_learning_items_for_failed_chain,
    _load_self_check_by_name,
    _run_chat_turn,
)


def test_run_chat_turn_collects_child_task_evidence_for_same_request(monkeypatch) -> None:
    request_id = "req-live-fail"
    agent_id = "agent-browser"
    root_task_id = f"query:session:console:{agent_id}:thread:{request_id}"
    child_task_id = f"{root_task_id}:tool:tool-browser_use:child"

    before_tasks = [
        {
            "id": "older-task",
            "owner_agent_id": agent_id,
        }
    ]
    after_tasks = before_tasks + [
        {
            "id": root_task_id,
            "owner_agent_id": agent_id,
        },
        {
            "id": child_task_id,
            "owner_agent_id": agent_id,
        },
    ]

    list_calls: list[int] = []
    evidence_paths: list[str] = []

    def fake_list_tasks(base_url: str):
        list_calls.append(1)
        return before_tasks if len(list_calls) == 1 else after_tasks

    def fake_request_text(*, base_url: str, method: str, path: str, payload: object, timeout: float):
        assert method == "POST"
        assert path == "/api/runtime-center/chat/run"
        return 200, {"Content-Type": "text/event-stream"}, ""

    def fake_request_json(*, base_url: str, method: str, path: str, timeout: float):
        assert method == "GET"
        evidence_paths.append(path)
        if path == f"/api/runtime-center/evidence?task_id={urllib.parse.quote(root_task_id)}":
            return 200, {}, [{"id": "e-root", "task_id": root_task_id, "status": "succeeded"}]
        if path == f"/api/runtime-center/evidence?task_id={urllib.parse.quote(child_task_id)}":
            return 200, {}, [{"id": "e-child", "task_id": child_task_id, "status": "failed"}]
        raise AssertionError(f"Unexpected evidence path: {path}")

    monkeypatch.setattr(
        "scripts.run_live_self_evolution_smoke._list_tasks",
        fake_list_tasks,
    )
    monkeypatch.setattr(
        "scripts.run_live_self_evolution_smoke._request_text",
        fake_request_text,
    )
    monkeypatch.setattr(
        "scripts.run_live_self_evolution_smoke._request_json",
        fake_request_json,
    )

    result = _run_chat_turn(
        base_url="http://127.0.0.1:9000",
        instance_id="industry-demo",
        role_id="browser-onboarding-runner",
        agent_id=agent_id,
        request_id=request_id,
        prompt="trigger browser tool",
    )

    assert result["task_id"] == root_task_id
    assert evidence_paths == [
        f"/api/runtime-center/evidence?task_id={urllib.parse.quote(root_task_id)}",
        f"/api/runtime-center/evidence?task_id={urllib.parse.quote(child_task_id)}",
    ]
    assert [item["id"] for item in result["evidence"]] == ["e-root", "e-child"]
    assert any(str(item.get("status")) == "failed" for item in result["evidence"])


def test_ensure_clean_browser_runtime_session_stops_existing_sessions_and_starts_headed(
    monkeypatch,
) -> None:
    calls: list[tuple[str, str, object | None]] = []

    def fake_request_json(
        *,
        base_url: str,
        method: str,
        path: str,
        payload: object | None = None,
        timeout: float,
    ):
        calls.append((method, path, payload))
        if method == "GET" and path == "/api/capability-market/install-templates/browser-local/sessions":
            return 200, {}, {"sessions": [{"session_id": "existing-a"}, {"session_id": "existing-b"}]}
        if method == "POST" and path == "/api/capability-market/install-templates/browser-local/sessions/existing-a/stop":
            return 200, {}, {"result": {"ok": True}}
        if method == "POST" and path == "/api/capability-market/install-templates/browser-local/sessions/existing-b/stop":
            return 200, {}, {"result": {"ok": True}}
        if method == "POST" and path == "/api/capability-market/install-templates/browser-local/sessions/start":
            return 200, {}, {"result": {"ok": True}, "status": "started"}
        raise AssertionError(f"Unexpected request: {method} {path}")

    monkeypatch.setattr(
        "scripts.run_live_self_evolution_smoke._request_json",
        fake_request_json,
    )

    payload = _ensure_clean_browser_runtime_session(
        base_url="http://127.0.0.1:9000",
        session_id="live-self-evolution-browser",
        entry_url="https://www.baidu.com",
        allowed_hosts=["www.baidu.com", "baidu.com"],
    )

    assert payload["status"] == "started"
    assert calls == [
        ("GET", "/api/capability-market/install-templates/browser-local/sessions", None),
        (
            "POST",
            "/api/capability-market/install-templates/browser-local/sessions/existing-a/stop",
            None,
        ),
        (
            "POST",
            "/api/capability-market/install-templates/browser-local/sessions/existing-b/stop",
            None,
        ),
        (
            "POST",
            "/api/capability-market/install-templates/browser-local/sessions/start",
            {
                "session_id": "live-self-evolution-browser",
                "headed": True,
                "entry_url": "https://www.baidu.com",
                "reuse_running_session": False,
                "allowed_hosts": ["www.baidu.com", "baidu.com"],
            },
        ),
    ]


def test_load_self_check_by_name_reads_system_self_check(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request_json(*, base_url: str, method: str, path: str, timeout: float):
        _ = base_url, timeout
        calls.append((method, path))
        assert method == "GET"
        assert path == "/api/system/self-check"
        return 200, {}, {
            "checks": [
                {
                    "name": "chat_decision_model",
                    "status": "pass",
                    "summary": "decision model ready",
                },
                {
                    "name": "provider_active_model",
                    "status": "pass",
                    "summary": "active model ready",
                },
            ],
        }

    monkeypatch.setattr(
        "scripts.run_live_self_evolution_smoke._request_json",
        fake_request_json,
    )

    payload = _load_self_check_by_name("http://127.0.0.1:9000")

    assert calls == [("GET", "/api/system/self-check")]
    assert payload["chat_decision_model"]["status"] == "pass"
    assert payload["provider_active_model"]["summary"] == "active model ready"


def test_load_learning_items_for_failed_chain_falls_back_to_failed_child_task(
    monkeypatch,
) -> None:
    root_task_id = "query:root-fail"
    child_task_id = "query:root-fail:tool:tool-browser_use:child-fail"
    calls: list[str] = []

    def fake_request_json(*, base_url: str, method: str, path: str, timeout: float):
        _ = base_url, timeout
        assert method == "GET"
        calls.append(path)
        if path == f"/api/runtime-center/learning/patches?task_id={urllib.parse.quote(root_task_id)}":
            return 200, {}, []
        if path == f"/api/runtime-center/learning/patches?task_id={urllib.parse.quote(child_task_id)}":
            return 200, {}, [{"id": "patch:child", "task_id": child_task_id}]
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(
        "scripts.run_live_self_evolution_smoke._request_json",
        fake_request_json,
    )

    anchor_task_id, items = _load_learning_items_for_failed_chain(
        base_url="http://127.0.0.1:9000",
        endpoint="patches",
        failed_turns=[{"task_id": root_task_id}],
        failed_browser_evidence=[{"task_id": child_task_id}],
    )

    assert calls == [
        f"/api/runtime-center/learning/patches?task_id={urllib.parse.quote(root_task_id)}",
        f"/api/runtime-center/learning/patches?task_id={urllib.parse.quote(child_task_id)}",
    ]
    assert anchor_task_id == child_task_id
    assert items == [{"id": "patch:child", "task_id": child_task_id}]
