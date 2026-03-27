# -*- coding: utf-8 -*-
from __future__ import annotations

from .sqlite_shared import *  # noqa: F401,F403


class SqliteWorkContextRepository(BaseWorkContextRepository):
    """SQLite-backed repository for formal continuous work boundaries."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_context(self, context_id: str) -> WorkContextRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM work_contexts WHERE id = ?",
                (context_id,),
            ).fetchone()
        return _work_context_from_row(row)

    def get_by_context_key(self, context_key: str) -> WorkContextRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM work_contexts WHERE context_key = ?",
                (context_key,),
            ).fetchone()
        return _work_context_from_row(row)

    def list_contexts(
        self,
        *,
        context_type: str | None = None,
        status: str | None = None,
        context_key: str | None = None,
        owner_scope: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        primary_thread_id: str | None = None,
        parent_work_context_id: str | None = None,
        source_kind: str | None = None,
        source_ref: str | None = None,
        limit: int | None = None,
    ) -> list[WorkContextRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        for field_name, value in (
            ("context_type", context_type),
            ("status", status),
            ("context_key", context_key),
            ("owner_scope", owner_scope),
            ("owner_agent_id", owner_agent_id),
            ("industry_instance_id", industry_instance_id),
            ("primary_thread_id", primary_thread_id),
            ("parent_work_context_id", parent_work_context_id),
            ("source_kind", source_kind),
            ("source_ref", source_ref),
        ):
            if value is None:
                continue
            clauses.append(f"{field_name} = ?")
            params.append(value)
        query = "SELECT * FROM work_contexts"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, created_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            item
            for item in (_work_context_from_row(row) for row in rows)
            if item is not None
        ]

    def upsert_context(self, context: WorkContextRecord) -> WorkContextRecord:
        payload = _payload(context)
        payload["metadata_json"] = _encode_json(context.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO work_contexts (
                    id,
                    title,
                    summary,
                    context_type,
                    status,
                    context_key,
                    owner_scope,
                    owner_agent_id,
                    industry_instance_id,
                    primary_thread_id,
                    source_kind,
                    source_ref,
                    parent_work_context_id,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :title,
                    :summary,
                    :context_type,
                    :status,
                    :context_key,
                    :owner_scope,
                    :owner_agent_id,
                    :industry_instance_id,
                    :primary_thread_id,
                    :source_kind,
                    :source_ref,
                    :parent_work_context_id,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    summary = excluded.summary,
                    context_type = excluded.context_type,
                    status = excluded.status,
                    context_key = excluded.context_key,
                    owner_scope = excluded.owner_scope,
                    owner_agent_id = excluded.owner_agent_id,
                    industry_instance_id = excluded.industry_instance_id,
                    primary_thread_id = excluded.primary_thread_id,
                    source_kind = excluded.source_kind,
                    source_ref = excluded.source_ref,
                    parent_work_context_id = excluded.parent_work_context_id,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return context

    def delete_context(self, context_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute("DELETE FROM work_contexts WHERE id = ?", (context_id,))
        return cursor.rowcount > 0


def _work_context_from_row(row: sqlite3.Row | None) -> WorkContextRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return WorkContextRecord.model_validate(payload)
