# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

import pytest

from copaw.app.runtime_session import SafeJSONSession


class _StateModule:
    def __init__(self, payload=None) -> None:
        self.payload = payload or {"memory": []}
        self.loaded = None

    def state_dict(self):
        return self.payload

    def load_state_dict(self, payload) -> None:
        self.loaded = payload


def test_safe_json_session_requires_database_path() -> None:
    with pytest.raises(ValueError, match="requires database_path"):
        SafeJSONSession()


def test_safe_json_session_persists_snapshot_in_sqlite_only(tmp_path) -> None:
    session = SafeJSONSession(database_path=tmp_path / "state.sqlite3")
    agent = _StateModule(
        {"memory": [{"role": "assistant", "content": "hello"}]},
    )

    asyncio.run(
        session.save_session_state(
            session_id="console:founder",
            user_id="founder",
            agent=agent,
        ),
    )

    payload = session.load_session_snapshot(
        session_id="console:founder",
        user_id="founder",
    )
    assert payload == {
        "agent": {"memory": [{"role": "assistant", "content": "hello"}]},
    }
    assert list(tmp_path.glob("**/*.json")) == []


def test_safe_json_session_load_remains_available(tmp_path) -> None:
    session = SafeJSONSession(database_path=tmp_path / "state.sqlite3")
    session._save_state_payload(
        session_id="console:founder",
        user_id="founder",
        payload={"agent": {"memory": [{"role": "assistant", "content": "loaded"}]}},
        source_ref="test",
    )
    agent = _StateModule()

    asyncio.run(
        session.load_session_state(
            session_id="console:founder",
            user_id="founder",
            agent=agent,
        ),
    )

    assert agent.loaded == {"memory": [{"role": "assistant", "content": "loaded"}]}


def test_safe_json_session_recreates_missing_snapshot_table_on_read(tmp_path) -> None:
    session = SafeJSONSession(database_path=tmp_path / "state.sqlite3")

    import sqlite3

    with sqlite3.connect(session.database_path) as connection:
        connection.execute("DROP TABLE session_state_snapshots")

    payload = session.load_merged_session_snapshot(
        session_id="console:founder",
        primary_user_id="founder",
    )

    assert payload is None
