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
            return {
                "result": {
                    "thread": {"id": "thread-1"},
                    "model": "gpt-5-codex",
                },
            }
        if method == "turn/start":
            return {
                "result": {
                    "turn": {"id": "turn-1"},
                    "runtimeMetadata": {"provider_id": "codex-app-server"},
                },
            }
        if method == "turn/steer":
            return {"accepted": True}
        if method == "turn/interrupt":
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
    assert transport.requests[1][0] == "turn/start"
    assert transport.requests[1][1]["threadId"] == "thread-1"
    assert transport.requests[1][1]["cwd"] == "D:/agents/codex-project"
    assert transport.requests[1][1]["input"] == [
        {
            "type": "text",
            "text": "Implement the task",
            "text_elements": [],
        },
    ]


def test_codex_adapter_normalizes_plan_and_file_events() -> None:
    adapter = CodexAppServerAdapter(transport=_FakeTransport())

    plan_event = adapter.normalize_event(
        {
            "method": "turn/plan/updated",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "plan": [],
            },
        },
    )
    file_event = adapter.normalize_event(
        {
            "method": "item/completed",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "item": {"type": "fileChange", "path": "a.py"},
            },
        },
    )
    mcp_event = adapter.normalize_event(
        {
            "method": "item/completed",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "item": {"type": "mcpToolCall", "tool": "browser.open"},
            },
        },
    )
    agent_message_event = adapter.normalize_event(
        {
            "method": "item/completed",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "item": {"type": "agentMessage", "text": "COPAW_APP_SERVER_SMOKE"},
            },
        },
    )
    completed_event = adapter.normalize_event(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed"},
            },
        },
    )
    failed_event = adapter.normalize_event(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-1",
                "turn": {"id": "turn-2", "status": "failed", "error": "boom"},
            },
        },
    )

    assert plan_event.event_type == "plan_submitted"
    assert plan_event.payload["thread_id"] == "thread-1"
    assert plan_event.payload["turn_id"] == "turn-1"
    assert file_event.event_type == "evidence_emitted"
    assert file_event.source_type == "fileChange"
    assert file_event.payload["thread_id"] == "thread-1"
    assert file_event.payload["turn_id"] == "turn-1"
    assert mcp_event.source_type == "mcpToolCall"
    assert agent_message_event.event_type == "message_emitted"
    assert agent_message_event.source_type == "agentMessage"
    assert agent_message_event.payload["message"] == "COPAW_APP_SERVER_SMOKE"
    assert completed_event.event_type == "task_completed"
    assert completed_event.payload["thread_id"] == "thread-1"
    assert completed_event.payload["turn_id"] == "turn-1"
    assert failed_event.event_type == "task_failed"
    assert failed_event.payload["error"] == "boom"


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
                "threadId": "thread-existing",
                "input": [
                    {
                        "type": "text",
                        "text": "Continue the task",
                        "text_elements": [],
                    },
                ],
                "cwd": "D:/agents/codex-project",
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
                "threadId": "thread-1",
                "expectedTurnId": "turn-1",
                "input": [
                    {
                        "type": "text",
                        "text": "Keep going",
                        "text_elements": [],
                    },
                ],
            },
        ),
        (
            "turn/interrupt",
            {
                "threadId": "thread-1",
                "turnId": "turn-1",
            },
        ),
    ]
