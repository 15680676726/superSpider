# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.adapters.executors.codex_app_server_adapter import CodexAppServerAdapter


class _FakeTransport:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, object]]] = []
        self.streams: dict[str, list[dict[str, object]]] = {}

    def request(self, method: str, params: dict[str, object] | None = None) -> dict[str, object]:
        payload = dict(params or {})
        self.requests.append((method, payload))
        if method == "thread/start":
            return {"thread_id": "thread-1"}
        if method == "turn/start":
            return {
                "turn_id": "turn-1",
                "model": "gpt-5-codex",
                "runtime_metadata": {"provider_id": "codex-app-server"},
            }
        if method == "turn/steer":
            return {"accepted": True}
        if method == "turn/stop":
            return {"accepted": True}
        raise AssertionError(f"Unexpected method: {method}")

    def subscribe_events(self, thread_id: str):
        for item in self.streams.get(thread_id, []):
            yield item


def test_codex_adapter_starts_thread_and_turn_for_assignment() -> None:
    transport = _FakeTransport()
    adapter = CodexAppServerAdapter(transport=transport)

    result = adapter.start_assignment_turn(
        assignment_id="assign-1",
        project_root="D:/agents/codex-project",
        prompt="Implement the task",
    )

    assert result.thread_id == "thread-1"
    assert result.turn_id == "turn-1"
    assert result.model_ref == "gpt-5-codex"
    assert transport.requests[0][0] == "thread/start"
    assert transport.requests[0][1]["cwd"] == "D:/agents/codex-project"
    assert transport.requests[0][1]["metadata"]["assignment_id"] == "assign-1"
    assert transport.requests[1][0] == "turn/start"
    assert transport.requests[1][1]["thread_id"] == "thread-1"
    assert transport.requests[1][1]["prompt"] == "Implement the task"


def test_codex_adapter_normalizes_plan_and_file_events() -> None:
    adapter = CodexAppServerAdapter(transport=_FakeTransport())

    plan_event = adapter.normalize_event(
        {"method": "turn/plan/updated", "params": {"plan": []}},
    )
    file_event = adapter.normalize_event(
        {"method": "item/completed", "params": {"item": {"type": "fileChange", "path": "a.py"}}},
    )
    mcp_event = adapter.normalize_event(
        {"method": "item/completed", "params": {"item": {"type": "mcpToolCall", "tool": "browser.open"}}},
    )
    completed_event = adapter.normalize_event(
        {"method": "turn/completed", "params": {"summary": "done"}},
    )
    failed_event = adapter.normalize_event(
        {"method": "turn/failed", "params": {"error": "boom"}},
    )

    assert plan_event.event_type == "plan_submitted"
    assert file_event.event_type == "evidence_emitted"
    assert file_event.source_type == "fileChange"
    assert mcp_event.source_type == "mcpToolCall"
    assert completed_event.event_type == "task_completed"
    assert failed_event.event_type == "task_failed"


def test_codex_adapter_subscribes_and_normalizes_stream_events() -> None:
    transport = _FakeTransport()
    transport.streams["thread-1"] = [
        {"method": "turn/plan/updated", "params": {"plan": [{"step": "Do work"}]}},
        {"method": "turn/completed", "params": {"summary": "done"}},
    ]
    adapter = CodexAppServerAdapter(transport=transport)

    events = list(adapter.subscribe_events(thread_id="thread-1"))

    assert [item.event_type for item in events] == ["plan_submitted", "task_completed"]


def test_codex_adapter_reuses_existing_thread_without_starting_new_one() -> None:
    transport = _FakeTransport()
    adapter = CodexAppServerAdapter(transport=transport)

    result = adapter.start_assignment_turn(
        assignment_id="assign-1",
        project_root="D:/agents/codex-project",
        prompt="Continue the task",
        thread_id="thread-existing",
    )

    assert result.thread_id == "thread-existing"
    assert transport.requests == [
        (
            "turn/start",
            {
                "thread_id": "thread-existing",
                "prompt": "Continue the task",
                "cwd": "D:/agents/codex-project",
                "metadata": {"assignment_id": "assign-1"},
            },
        ),
    ]


def test_codex_adapter_steers_and_stops_turn() -> None:
    transport = _FakeTransport()
    adapter = CodexAppServerAdapter(transport=transport)

    steer_response = adapter.steer_turn(
        thread_id="thread-1",
        turn_id="turn-1",
        prompt="Keep going",
    )
    stop_response = adapter.stop_turn(thread_id="thread-1", turn_id="turn-1")

    assert steer_response == {"accepted": True}
    assert stop_response == {"accepted": True}
    assert transport.requests == [
        (
            "turn/steer",
            {
                "thread_id": "thread-1",
                "turn_id": "turn-1",
                "prompt": "Keep going",
            },
        ),
        (
            "turn/stop",
            {
                "thread_id": "thread-1",
                "turn_id": "turn-1",
            },
        ),
    ]
