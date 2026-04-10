# -*- coding: utf-8 -*-
"""SQLite-backed runtime session snapshots."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from agentscope.session import JSONSession


def _snapshot_messages(payload: dict[str, Any]) -> tuple[list[Any], dict[str, Any] | None]:
    agent_state = payload.get("agent")
    if not isinstance(agent_state, dict):
        return [], None
    memory_state = agent_state.get("memory")
    if isinstance(memory_state, list):
        return list(memory_state), None
    if isinstance(memory_state, dict):
        content = memory_state.get("content")
        if isinstance(content, list):
            return list(content), dict(memory_state)
    return [], dict(memory_state) if isinstance(memory_state, dict) else None


def _message_identity(item: Any) -> str:
    if isinstance(item, dict):
        message_id = str(item.get("id") or "").strip()
        if message_id:
            return f"id:{message_id}"
    return json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)


def _merge_snapshot_payloads(
    snapshots: list[dict[str, Any]],
    *,
    primary_user_id: str,
) -> dict[str, Any]:
    if not snapshots:
        return {}
    primary_snapshot = next(
        (
            snapshot
            for snapshot in snapshots
            if str(snapshot.get("user_id") or "").strip() == primary_user_id
        ),
        snapshots[-1],
    )
    merged: dict[str, Any] = dict(primary_snapshot.get("payload") or {})
    if not isinstance(merged, dict):
        merged = {}
    for snapshot in reversed(snapshots):
        payload = snapshot.get("payload")
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if key not in merged:
                merged[key] = value

    merged_messages: list[Any] = []
    seen_message_keys: set[str] = set()
    merged_memory_template: dict[str, Any] | None = None
    for snapshot in snapshots:
        payload = snapshot.get("payload")
        if not isinstance(payload, dict):
            continue
        messages, memory_template = _snapshot_messages(payload)
        if merged_memory_template is None and memory_template is not None:
            merged_memory_template = memory_template
        for message in messages:
            identity = _message_identity(message)
            if identity in seen_message_keys:
                continue
            seen_message_keys.add(identity)
            merged_messages.append(message)

    if merged_messages:
        agent_state = dict(merged.get("agent") or {})
        if not isinstance(agent_state, dict):
            agent_state = {}
        memory_state = agent_state.get("memory")
        if isinstance(memory_state, list):
            agent_state["memory"] = merged_messages
        else:
            normalized_memory = (
                dict(memory_state)
                if isinstance(memory_state, dict)
                else dict(merged_memory_template or {})
            )
            normalized_memory["content"] = merged_messages
            agent_state["memory"] = normalized_memory
        merged["agent"] = agent_state
    return merged


class SafeJSONSession(JSONSession):
    """Session backend that stores runtime state in SQLite only."""

    def __init__(
        self,
        database_path: str | Path | None = None,
        **kwargs,
    ):
        if database_path is None:
            raise ValueError(
                "SafeJSONSession requires database_path; legacy JSON-only "
                "session persistence has been retired.",
            )
        if "save_dir" in kwargs:
            raise TypeError("SafeJSONSession no longer accepts save_dir")
        if kwargs:
            unexpected = ", ".join(sorted(kwargs))
            raise TypeError(
                "SafeJSONSession got unexpected keyword arguments: "
                f"{unexpected}",
            )
        super().__init__(save_dir=str(Path(database_path).parent))
        self._database_path = str(database_path)
        self._initialize_state_store()

    @property
    def database_path(self) -> str | None:
        return self._database_path

    async def save_session_state(
        self,
        session_id: str,
        user_id: str = "",
        **state_modules_mapping,
    ) -> None:
        payload = {
            name: state_module.state_dict()
            for name, state_module in state_modules_mapping.items()
        }
        self._save_state_payload(
            session_id=session_id,
            user_id=user_id,
            payload=payload,
            source_ref="state:/session-snapshot",
        )

    async def load_session_state(
        self,
        session_id: str,
        user_id: str = "",
        allow_not_exist: bool = True,
        **state_modules_mapping,
    ) -> None:
        payload = self.load_session_snapshot(
            session_id=session_id,
            user_id=user_id,
            allow_not_exist=allow_not_exist,
        )
        if payload is None:
            return

        for name, state_module in state_modules_mapping.items():
            if name in payload:
                state_module.load_state_dict(payload[name])

    def load_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str = "",
        allow_not_exist: bool = True,
    ) -> dict[str, Any] | None:
        payload = self._load_state_payload(session_id=session_id, user_id=user_id)
        if payload is not None:
            return payload

        if allow_not_exist:
            return None
        raise ValueError(
            f"Failed to load session state for {session_id}: no state snapshot found.",
        )

    def list_session_snapshots(
        self,
        *,
        session_id: str,
    ) -> list[dict[str, Any]]:
        if self._database_path is None:
            return []
        self._initialize_state_store()
        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT user_id, source_ref, state_json, updated_at
                FROM session_state_snapshots
                WHERE session_id = ?
                ORDER BY updated_at ASC, user_id ASC
                """,
                (session_id,),
            ).fetchall()
        snapshots: list[dict[str, Any]] = []
        for user_id, source_ref, state_json, updated_at in rows:
            payload = json.loads(state_json)
            if not isinstance(payload, dict):
                continue
            snapshots.append(
                {
                    "session_id": session_id,
                    "user_id": str(user_id or ""),
                    "source_ref": str(source_ref or ""),
                    "updated_at": str(updated_at or ""),
                    "payload": payload,
                }
            )
        return snapshots

    def load_merged_session_snapshot(
        self,
        *,
        session_id: str,
        primary_user_id: str = "",
        allow_not_exist: bool = True,
    ) -> dict[str, Any] | None:
        snapshots = self.list_session_snapshots(session_id=session_id)
        if snapshots:
            return _merge_snapshot_payloads(
                snapshots,
                primary_user_id=primary_user_id,
            )
        if allow_not_exist:
            return None
        raise ValueError(
            f"Failed to load merged session state for {session_id}: no state snapshot found.",
        )

    def save_session_snapshot(
        self,
        *,
        session_id: str,
        payload: dict[str, Any],
        user_id: str = "",
        source_ref: str = "state:/session-snapshot",
    ) -> None:
        if not isinstance(payload, dict):
            raise TypeError("session snapshot payload must be a dict")
        self._save_state_payload(
            session_id=session_id,
            user_id=user_id,
            payload=payload,
            source_ref=source_ref,
        )

    def _initialize_state_store(self) -> None:
        database_dir = Path(self._database_path).parent
        database_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._database_path) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS session_state_snapshots (
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL DEFAULT '',
                    source_ref TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (session_id, user_id)
                );
                """,
            )

    def _save_state_payload(
        self,
        *,
        session_id: str,
        user_id: str,
        payload: dict[str, Any],
        source_ref: str,
    ) -> None:
        if self._database_path is None:
            return
        self._initialize_state_store()
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO session_state_snapshots (
                    session_id,
                    user_id,
                    source_ref,
                    state_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id, user_id) DO UPDATE SET
                    source_ref = excluded.source_ref,
                    state_json = excluded.state_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    session_id,
                    user_id,
                    source_ref,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                ),
            )

    def _load_state_payload(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        if self._database_path is None:
            return None
        self._initialize_state_store()
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT state_json
                FROM session_state_snapshots
                WHERE session_id = ? AND user_id = ?
                """,
                (session_id, user_id),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row[0])
        return payload if isinstance(payload, dict) else None


__all__ = ["SafeJSONSession"]
