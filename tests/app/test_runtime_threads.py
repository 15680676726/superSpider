# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from agentscope_runtime.engine.schemas.agent_schemas import Message

from copaw.app.runtime_threads import (
    RuntimeThreadSpec,
    SessionRuntimeThreadHistoryReader,
)


def _make_thread(thread_id: str) -> RuntimeThreadSpec:
    timestamp = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
    return RuntimeThreadSpec(
        id=thread_id,
        name="Founder sync",
        session_id=f"console:{thread_id}",
        user_id="founder",
        channel="console",
        created_at=timestamp,
        updated_at=timestamp,
    )


class _FakeMemory:
    def __init__(self) -> None:
        self._payload = None

    def load_state_dict(self, payload) -> None:
        self._payload = payload

    async def get_memory(self):
        return self._payload


def _stub_messages(_payload):
    return [
        Message.model_validate(
            {
                "id": "msg-1",
                "role": "assistant",
                "content": [{"type": "text", "text": "hello from history"}],
            },
        ),
    ]


def test_runtime_thread_history_reader_uses_session_snapshot_loader(monkeypatch) -> None:
    monkeypatch.setattr("copaw.app.runtime_threads.InMemoryMemory", _FakeMemory)
    monkeypatch.setattr("copaw.app.runtime_threads.agentscope_msg_to_message", _stub_messages)

    class _Backend:
        def load_session_snapshot(self, *, session_id: str, user_id: str, allow_not_exist: bool):
            assert session_id == "console:chat-1"
            assert user_id == "founder"
            assert allow_not_exist is True
            return {"agent": {"memory": {"content": [{"role": "assistant", "content": "seed"}]}}}

    reader = SessionRuntimeThreadHistoryReader(session_backend=_Backend())
    history = asyncio.run(reader.get_thread_history(_make_thread("chat-1")))

    assert history.messages[0].content[0].text == "hello from history"


def test_runtime_thread_history_reader_does_not_fall_back_to_legacy_path(tmp_path) -> None:
    payload = {"agent": {"memory": {"content": [{"role": "assistant", "content": "legacy"}]}}}
    path = tmp_path / "founder_console--chat-2.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    class _Backend:
        def get_save_path(self, *, session_id: str, user_id: str) -> str:
            assert session_id == "console:chat-2"
            assert user_id == "founder"
            return str(path)

    reader = SessionRuntimeThreadHistoryReader(session_backend=_Backend())
    history = asyncio.run(reader.get_thread_history(_make_thread("chat-2")))

    assert history.messages == []


def test_runtime_thread_history_reader_merges_session_snapshots_across_user_ids(
    monkeypatch,
) -> None:
    monkeypatch.setattr("copaw.app.runtime_threads.InMemoryMemory", _FakeMemory)

    def _payload_messages(payload):
        items = []
        if isinstance(payload, dict):
            items = list(payload.get("content") or [])
        return [Message.model_validate(item) for item in items]

    monkeypatch.setattr(
        "copaw.app.runtime_threads.agentscope_msg_to_message",
        _payload_messages,
    )

    class _Backend:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, bool]] = []

        def load_merged_session_snapshot(
            self,
            *,
            session_id: str,
            primary_user_id: str,
            allow_not_exist: bool,
        ):
            self.calls.append((session_id, primary_user_id, allow_not_exist))
            return {
                "agent": {
                    "memory": {
                        "content": [
                            {
                                "id": "msg-user-1",
                                "role": "user",
                                "content": [{"type": "text", "text": "帮我继续推进"}],
                            },
                            {
                                "id": "msg-report-1",
                                "role": "assistant",
                                "content": [{"type": "text", "text": "我刚完成一项任务"}],
                            },
                        ],
                    },
                },
            }

    backend = _Backend()
    reader = SessionRuntimeThreadHistoryReader(session_backend=backend)

    history = asyncio.run(reader.get_thread_history(_make_thread("chat-merged")))

    assert backend.calls == [("console:chat-merged", "founder", True)]
    assert [message.id for message in history.messages] == [
        "msg-user-1",
        "msg-report-1",
    ]


def test_runtime_thread_history_reader_normalizes_legacy_merged_snapshot_messages(
    monkeypatch,
) -> None:
    def _payload_messages(payload):
        items = []
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = list(payload.get("content") or [])
        messages: list[Message] = []
        for item in items:
            if hasattr(item, "to_dict"):
                item = item.to_dict()
            if isinstance(item, list) and item:
                item = item[0]
            if not isinstance(item, dict):
                continue
            text_blocks = item.get("content") or []
            first_text = ""
            if isinstance(text_blocks, list):
                for block in text_blocks:
                    if isinstance(block, dict) and block.get("type") == "text":
                        first_text = str(block.get("text") or "")
                        break
            messages.append(
                Message.model_validate(
                    {
                        "id": item.get("id"),
                        "role": item.get("role") or "assistant",
                        "content": [{"type": "text", "text": first_text}],
                    },
                ),
            )
        return messages

    monkeypatch.setattr(
        "copaw.app.runtime_threads.agentscope_msg_to_message",
        _payload_messages,
    )

    class _Backend:
        def load_merged_session_snapshot(
            self,
            *,
            session_id: str,
            primary_user_id: str,
            allow_not_exist: bool,
        ):
            assert session_id == "console:chat-legacy-merged"
            assert primary_user_id == "founder"
            assert allow_not_exist is True
            return {
                "agent": {
                    "memory": [
                        {
                            "id": "legacy-report-1",
                            "role": "assistant",
                            "content": [{"type": "text", "text": "legacy report"}],
                        },
                        [
                            {
                                "id": "user-msg-1",
                                "name": "user",
                                "role": "user",
                                "content": [{"type": "text", "text": "继续"}],
                            },
                            [],
                        ],
                    ],
                },
            }

    reader = SessionRuntimeThreadHistoryReader(session_backend=_Backend())

    history = asyncio.run(reader.get_thread_history(_make_thread("chat-legacy-merged")))

    assert [message.id for message in history.messages] == [
        "legacy-report-1",
        "user-msg-1",
    ]
