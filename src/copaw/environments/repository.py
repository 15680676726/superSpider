# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..state import SQLiteStateStore
from .models import EnvironmentMount, SessionMount


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _encode_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _decode_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _encode_json(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _decode_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _row_to_mount(row) -> EnvironmentMount | None:
    if row is None:
        return None
    payload = {
        "id": row["id"],
        "kind": row["kind"],
        "display_name": row["display_name"],
        "ref": row["ref"],
        "status": row["status"],
        "last_active_at": row["last_active_at"],
        "evidence_count": int(row["evidence_count"] or 0),
        "metadata": _decode_json(row["metadata_json"]),
        "lease_status": row["lease_status"],
        "lease_owner": row["lease_owner"],
        "lease_token": row["lease_token"],
        "lease_acquired_at": _decode_datetime(row["lease_acquired_at"]),
        "lease_expires_at": _decode_datetime(row["lease_expires_at"]),
        "live_handle_ref": row["live_handle_ref"],
    }
    return EnvironmentMount.model_validate(payload)


def _row_to_session(row) -> SessionMount | None:
    if row is None:
        return None
    payload = {
        "id": row["id"],
        "environment_id": row["environment_id"],
        "channel": row["channel"],
        "session_id": row["session_id"],
        "user_id": row["user_id"],
        "status": row["status"],
        "created_at": _decode_datetime(row["created_at"]) or _utc_now(),
        "last_active_at": _decode_datetime(row["last_active_at"]),
        "metadata": _decode_json(row["metadata_json"]),
        "lease_status": row["lease_status"],
        "lease_owner": row["lease_owner"],
        "lease_token": row["lease_token"],
        "lease_acquired_at": _decode_datetime(row["lease_acquired_at"]),
        "lease_expires_at": _decode_datetime(row["lease_expires_at"]),
        "live_handle_ref": row["live_handle_ref"],
    }
    return SessionMount.model_validate(payload)


class EnvironmentRepository:
    """SQLite-backed repository for environment mounts."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_environment(self, env_id: str) -> EnvironmentMount | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM environment_mounts WHERE id = ?",
                (env_id,),
            ).fetchone()
        return _row_to_mount(row)

    def list_environments(
        self,
        *,
        kind: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[EnvironmentMount]:
        clauses: list[str] = []
        params: list[Any] = []
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        query = "SELECT * FROM environment_mounts"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY last_active_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        mounts: list[EnvironmentMount] = []
        for row in rows:
            mount = _row_to_mount(row)
            if mount is not None:
                mounts.append(mount)
        return mounts

    def upsert_environment(self, mount: EnvironmentMount) -> EnvironmentMount:
        payload = {
            "id": mount.id,
            "kind": mount.kind,
            "display_name": mount.display_name,
            "ref": mount.ref,
            "status": mount.status,
            "last_active_at": _encode_datetime(mount.last_active_at),
            "evidence_count": mount.evidence_count,
            "metadata_json": _encode_json(mount.metadata),
            "lease_status": mount.lease_status,
            "lease_owner": mount.lease_owner,
            "lease_token": mount.lease_token,
            "lease_acquired_at": _encode_datetime(mount.lease_acquired_at),
            "lease_expires_at": _encode_datetime(mount.lease_expires_at),
            "live_handle_ref": mount.live_handle_ref,
        }
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO environment_mounts (
                    id,
                    kind,
                    display_name,
                    ref,
                    status,
                    last_active_at,
                    evidence_count,
                    metadata_json,
                    lease_status,
                    lease_owner,
                    lease_token,
                    lease_acquired_at,
                    lease_expires_at,
                    live_handle_ref
                ) VALUES (
                    :id,
                    :kind,
                    :display_name,
                    :ref,
                    :status,
                    :last_active_at,
                    :evidence_count,
                    :metadata_json,
                    :lease_status,
                    :lease_owner,
                    :lease_token,
                    :lease_acquired_at,
                    :lease_expires_at,
                    :live_handle_ref
                )
                ON CONFLICT(id) DO UPDATE SET
                    kind = excluded.kind,
                    display_name = excluded.display_name,
                    ref = excluded.ref,
                    status = excluded.status,
                    last_active_at = excluded.last_active_at,
                    evidence_count = excluded.evidence_count,
                    metadata_json = excluded.metadata_json,
                    lease_status = excluded.lease_status,
                    lease_owner = excluded.lease_owner,
                    lease_token = excluded.lease_token,
                    lease_acquired_at = excluded.lease_acquired_at,
                    lease_expires_at = excluded.lease_expires_at,
                    live_handle_ref = excluded.live_handle_ref
                """,
                payload,
            )
        return mount

    def touch_environment(
        self,
        *,
        env_id: str,
        kind: str,
        display_name: str,
        ref: str,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
        last_active_at: datetime | None = None,
        evidence_delta: int = 1,
    ) -> EnvironmentMount:
        with self._store.connection() as conn:
            row = conn.execute(
                (
                    "SELECT evidence_count, metadata_json, last_active_at, status, "
                    "lease_status, lease_owner, lease_token, lease_acquired_at, "
                    "lease_expires_at, live_handle_ref "
                    "FROM environment_mounts WHERE id = ?"
                ),
                (env_id,),
            ).fetchone()
            existing_count = int(row["evidence_count"] or 0) if row else 0
            existing_meta = _decode_json(row["metadata_json"]) if row else {}
            existing_last_active = (
                _decode_datetime(row["last_active_at"]) if row else None
            )
            existing_status = row["status"] if row else None
            existing_lease_status = row["lease_status"] if row else None
            existing_lease_owner = row["lease_owner"] if row else None
            existing_lease_token = row["lease_token"] if row else None
            existing_lease_acquired_at = (
                _decode_datetime(row["lease_acquired_at"]) if row else None
            )
            existing_lease_expires_at = (
                _decode_datetime(row["lease_expires_at"]) if row else None
            )
            existing_live_handle_ref = row["live_handle_ref"] if row else None

            merged_meta = {**existing_meta, **(metadata or {})}
            effective_last_active = last_active_at or existing_last_active or _utc_now()
            effective_status = status or existing_status or "active"
            new_count = max(0, existing_count + evidence_delta)

            if row is None:
                conn.execute(
                    """
                    INSERT INTO environment_mounts (
                        id,
                        kind,
                        display_name,
                        ref,
                        status,
                        last_active_at,
                        evidence_count,
                        metadata_json,
                        lease_status,
                        lease_owner,
                        lease_token,
                        lease_acquired_at,
                        lease_expires_at,
                        live_handle_ref
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        env_id,
                        kind,
                        display_name,
                        ref,
                        effective_status,
                        _encode_datetime(effective_last_active),
                        new_count,
                        _encode_json(merged_meta),
                        existing_lease_status,
                        existing_lease_owner,
                        existing_lease_token,
                        _encode_datetime(existing_lease_acquired_at),
                        _encode_datetime(existing_lease_expires_at),
                        existing_live_handle_ref,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE environment_mounts
                    SET kind = ?,
                        display_name = ?,
                        ref = ?,
                        status = ?,
                        last_active_at = ?,
                        evidence_count = ?,
                        metadata_json = ?,
                        lease_status = ?,
                        lease_owner = ?,
                        lease_token = ?,
                        lease_acquired_at = ?,
                        lease_expires_at = ?,
                        live_handle_ref = ?
                    WHERE id = ?
                    """,
                    (
                        kind,
                        display_name,
                        ref,
                        effective_status,
                        _encode_datetime(effective_last_active),
                        new_count,
                        _encode_json(merged_meta),
                        existing_lease_status,
                        existing_lease_owner,
                        existing_lease_token,
                        _encode_datetime(existing_lease_acquired_at),
                        _encode_datetime(existing_lease_expires_at),
                        existing_live_handle_ref,
                        env_id,
                    ),
                )
        return self.get_environment(env_id) or EnvironmentMount(
            id=env_id,
            kind=kind,
            display_name=display_name,
            ref=ref,
            status=effective_status,
            last_active_at=effective_last_active,
            evidence_count=new_count,
            metadata=merged_meta,
            lease_status=existing_lease_status,
            lease_owner=existing_lease_owner,
            lease_token=existing_lease_token,
            lease_acquired_at=existing_lease_acquired_at,
            lease_expires_at=existing_lease_expires_at,
            live_handle_ref=existing_live_handle_ref,
        )

    def close_environment(self, env_id: str, *, status: str = "closed") -> EnvironmentMount | None:
        with self._store.connection() as conn:
            conn.execute(
                "UPDATE environment_mounts SET status = ? WHERE id = ?",
                (status, env_id),
            )
        return self.get_environment(env_id)


class SessionMountRepository:
    """SQLite-backed repository for session mounts."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_session(self, session_mount_id: str) -> SessionMount | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM session_mounts WHERE id = ?",
                (session_mount_id,),
            ).fetchone()
        return _row_to_session(row)

    def upsert_session(self, session: SessionMount) -> SessionMount:
        payload = {
            "id": session.id,
            "environment_id": session.environment_id,
            "channel": session.channel,
            "session_id": session.session_id,
            "user_id": session.user_id,
            "status": session.status,
            "created_at": _encode_datetime(session.created_at),
            "last_active_at": _encode_datetime(session.last_active_at),
            "metadata_json": _encode_json(session.metadata),
            "lease_status": session.lease_status,
            "lease_owner": session.lease_owner,
            "lease_token": session.lease_token,
            "lease_acquired_at": _encode_datetime(session.lease_acquired_at),
            "lease_expires_at": _encode_datetime(session.lease_expires_at),
            "live_handle_ref": session.live_handle_ref,
        }
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO session_mounts (
                    id,
                    environment_id,
                    channel,
                    session_id,
                    user_id,
                    status,
                    created_at,
                    last_active_at,
                    metadata_json,
                    lease_status,
                    lease_owner,
                    lease_token,
                    lease_acquired_at,
                    lease_expires_at,
                    live_handle_ref
                ) VALUES (
                    :id,
                    :environment_id,
                    :channel,
                    :session_id,
                    :user_id,
                    :status,
                    :created_at,
                    :last_active_at,
                    :metadata_json,
                    :lease_status,
                    :lease_owner,
                    :lease_token,
                    :lease_acquired_at,
                    :lease_expires_at,
                    :live_handle_ref
                )
                ON CONFLICT(id) DO UPDATE SET
                    environment_id = excluded.environment_id,
                    channel = excluded.channel,
                    session_id = excluded.session_id,
                    user_id = excluded.user_id,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    last_active_at = excluded.last_active_at,
                    metadata_json = excluded.metadata_json,
                    lease_status = excluded.lease_status,
                    lease_owner = excluded.lease_owner,
                    lease_token = excluded.lease_token,
                    lease_acquired_at = excluded.lease_acquired_at,
                    lease_expires_at = excluded.lease_expires_at,
                    live_handle_ref = excluded.live_handle_ref
                """,
                payload,
            )
        return session

    def list_sessions(
        self,
        *,
        environment_id: str | None = None,
        channel: str | None = None,
        user_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[SessionMount]:
        clauses: list[str] = []
        params: list[Any] = []
        if environment_id is not None:
            clauses.append("environment_id = ?")
            params.append(environment_id)
        if channel is not None:
            clauses.append("channel = ?")
            params.append(channel)
        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        query = "SELECT * FROM session_mounts"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY last_active_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        sessions: list[SessionMount] = []
        for row in rows:
            session = _row_to_session(row)
            if session is not None:
                sessions.append(session)
        return sessions

    def touch_session(
        self,
        *,
        session_mount_id: str,
        environment_id: str,
        channel: str,
        session_id: str,
        user_id: str | None,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
        last_active_at: datetime | None = None,
    ) -> SessionMount:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM session_mounts WHERE id = ?",
                (session_mount_id,),
            ).fetchone()
            existing_meta = _decode_json(row["metadata_json"]) if row else {}
            merged_meta = {**existing_meta, **(metadata or {})}
            existing_created = _decode_datetime(row["created_at"]) if row else None
            existing_last_active = _decode_datetime(row["last_active_at"]) if row else None
            existing_lease_status = row["lease_status"] if row else None
            existing_lease_owner = row["lease_owner"] if row else None
            existing_lease_token = row["lease_token"] if row else None
            existing_lease_acquired_at = (
                _decode_datetime(row["lease_acquired_at"]) if row else None
            )
            existing_lease_expires_at = (
                _decode_datetime(row["lease_expires_at"]) if row else None
            )
            existing_live_handle_ref = row["live_handle_ref"] if row else None
            effective_last_active = (
                last_active_at or existing_last_active or _utc_now()
            )
            effective_status = status or (row["status"] if row else None) or "active"

            if row is None:
                conn.execute(
                    """
                    INSERT INTO session_mounts (
                        id,
                        environment_id,
                        channel,
                        session_id,
                        user_id,
                        status,
                        created_at,
                        last_active_at,
                        metadata_json,
                        lease_status,
                        lease_owner,
                        lease_token,
                        lease_acquired_at,
                        lease_expires_at,
                        live_handle_ref
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_mount_id,
                        environment_id,
                        channel,
                        session_id,
                        user_id,
                        effective_status,
                        _encode_datetime(existing_created or _utc_now()),
                        _encode_datetime(effective_last_active),
                        _encode_json(merged_meta),
                        existing_lease_status,
                        existing_lease_owner,
                        existing_lease_token,
                        _encode_datetime(existing_lease_acquired_at),
                        _encode_datetime(existing_lease_expires_at),
                        existing_live_handle_ref,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE session_mounts
                    SET environment_id = ?,
                        channel = ?,
                        session_id = ?,
                        user_id = ?,
                        status = ?,
                        created_at = ?,
                        last_active_at = ?,
                        metadata_json = ?,
                        lease_status = ?,
                        lease_owner = ?,
                        lease_token = ?,
                        lease_acquired_at = ?,
                        lease_expires_at = ?,
                        live_handle_ref = ?
                    WHERE id = ?
                    """,
                    (
                        environment_id,
                        channel,
                        session_id,
                        user_id,
                        effective_status,
                        _encode_datetime(existing_created or _utc_now()),
                        _encode_datetime(effective_last_active),
                        _encode_json(merged_meta),
                        existing_lease_status,
                        existing_lease_owner,
                        existing_lease_token,
                        _encode_datetime(existing_lease_acquired_at),
                        _encode_datetime(existing_lease_expires_at),
                        existing_live_handle_ref,
                        session_mount_id,
                    ),
                )
        return self.get_session(session_mount_id) or SessionMount(
            id=session_mount_id,
            environment_id=environment_id,
            channel=channel,
            session_id=session_id,
            user_id=user_id,
            status=status or "active",
            created_at=_utc_now(),
            last_active_at=last_active_at,
            metadata=metadata or {},
            lease_status=existing_lease_status,
            lease_owner=existing_lease_owner,
            lease_token=existing_lease_token,
            lease_acquired_at=existing_lease_acquired_at,
            lease_expires_at=existing_lease_expires_at,
            live_handle_ref=existing_live_handle_ref,
        )

    def close_session(self, session_mount_id: str, *, status: str = "closed") -> SessionMount | None:
        with self._store.connection() as conn:
            conn.execute(
                "UPDATE session_mounts SET status = ? WHERE id = ?",
                (status, session_mount_id),
            )
        return self.get_session(session_mount_id)


__all__ = ["EnvironmentRepository", "SessionMountRepository"]
