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
