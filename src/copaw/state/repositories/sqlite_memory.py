# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..models_memory import (
    MemoryEntityViewRecord,
    MemoryFactIndexRecord,
    MemoryOpinionViewRecord,
    MemoryReflectionRunRecord,
)
from ..store import SQLiteStateStore
from .base import (
    BaseMemoryEntityViewRepository,
    BaseMemoryFactIndexRepository,
    BaseMemoryOpinionViewRepository,
    BaseMemoryReflectionRunRepository,
)
from .sqlite_shared import _decode_json_list, _decode_json_mapping, _encode_json, _payload


class SqliteMemoryFactIndexRepository(BaseMemoryFactIndexRepository):
    """SQLite-backed repository for rebuildable memory fact index entries."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_entry(self, entry_id: str) -> MemoryFactIndexRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM memory_fact_index WHERE id = ?",
                (entry_id,),
            ).fetchone()
        return _memory_fact_index_from_row(row)

    def list_entries(
        self,
        *,
        source_type: str | None = None,
        source_ref: str | None = None,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryFactIndexRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if source_type is not None:
            clauses.append("source_type = ?")
            params.append(source_type)
        if source_ref is not None:
            clauses.append("source_ref = ?")
            params.append(source_ref)
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        query = "SELECT * FROM memory_fact_index"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, created_at DESC"
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            record
            for record in (_memory_fact_index_from_row(row) for row in rows)
            if record is not None
        ]

    def upsert_entry(self, record: MemoryFactIndexRecord) -> MemoryFactIndexRecord:
        payload = _payload(record)
        payload["entity_keys_json"] = json.dumps(
            record.entity_keys,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["opinion_keys_json"] = json.dumps(
            record.opinion_keys,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["tags_json"] = json.dumps(
            record.tags,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["role_bindings_json"] = json.dumps(
            record.role_bindings,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["evidence_refs_json"] = json.dumps(
            record.evidence_refs,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["metadata_json"] = _encode_json(record.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO memory_fact_index (
                    id,
                    source_type,
                    source_ref,
                    scope_type,
                    scope_id,
                    owner_agent_id,
                    owner_scope,
                    industry_instance_id,
                    title,
                    summary,
                    content_excerpt,
                    content_text,
                    entity_keys_json,
                    opinion_keys_json,
                    tags_json,
                    role_bindings_json,
                    evidence_refs_json,
                    confidence,
                    quality_score,
                    source_updated_at,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :source_type,
                    :source_ref,
                    :scope_type,
                    :scope_id,
                    :owner_agent_id,
                    :owner_scope,
                    :industry_instance_id,
                    :title,
                    :summary,
                    :content_excerpt,
                    :content_text,
                    :entity_keys_json,
                    :opinion_keys_json,
                    :tags_json,
                    :role_bindings_json,
                    :evidence_refs_json,
                    :confidence,
                    :quality_score,
                    :source_updated_at,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    source_type = excluded.source_type,
                    source_ref = excluded.source_ref,
                    scope_type = excluded.scope_type,
                    scope_id = excluded.scope_id,
                    owner_agent_id = excluded.owner_agent_id,
                    owner_scope = excluded.owner_scope,
                    industry_instance_id = excluded.industry_instance_id,
                    title = excluded.title,
                    summary = excluded.summary,
                    content_excerpt = excluded.content_excerpt,
                    content_text = excluded.content_text,
                    entity_keys_json = excluded.entity_keys_json,
                    opinion_keys_json = excluded.opinion_keys_json,
                    tags_json = excluded.tags_json,
                    role_bindings_json = excluded.role_bindings_json,
                    evidence_refs_json = excluded.evidence_refs_json,
                    confidence = excluded.confidence,
                    quality_score = excluded.quality_score,
                    source_updated_at = excluded.source_updated_at,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return record

    def delete_entry(self, entry_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM memory_fact_index WHERE id = ?",
                (entry_id,),
            )
        return cursor.rowcount > 0

    def delete_by_source(self, *, source_type: str, source_ref: str) -> int:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM memory_fact_index WHERE source_type = ? AND source_ref = ?",
                (source_type, source_ref),
            )
        return int(cursor.rowcount or 0)

    def clear(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> int:
        return _delete_with_optional_scope(
            store=self._store,
            table_name="memory_fact_index",
            scope_type=scope_type,
            scope_id=scope_id,
        )


class SqliteMemoryEntityViewRepository(BaseMemoryEntityViewRepository):
    """SQLite-backed repository for compiled entity memory views."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_view(self, entity_id: str) -> MemoryEntityViewRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM memory_entity_views WHERE entity_id = ?",
                (entity_id,),
            ).fetchone()
        return _memory_entity_view_from_row(row)

    def list_views(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        entity_key: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryEntityViewRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if entity_key is not None:
            clauses.append("entity_key = ?")
            params.append(entity_key)
        query = "SELECT * FROM memory_entity_views"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY confidence DESC, updated_at DESC, created_at DESC"
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            record
            for record in (_memory_entity_view_from_row(row) for row in rows)
            if record is not None
        ]

    def upsert_view(self, record: MemoryEntityViewRecord) -> MemoryEntityViewRecord:
        payload = _payload(record)
        payload["supporting_refs_json"] = json.dumps(
            record.supporting_refs,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["contradicting_refs_json"] = json.dumps(
            record.contradicting_refs,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["related_entities_json"] = json.dumps(
            record.related_entities,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["source_refs_json"] = json.dumps(
            record.source_refs,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["metadata_json"] = _encode_json(record.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO memory_entity_views (
                    entity_id,
                    entity_key,
                    scope_type,
                    scope_id,
                    owner_agent_id,
                    industry_instance_id,
                    display_name,
                    entity_type,
                    summary,
                    confidence,
                    supporting_refs_json,
                    contradicting_refs_json,
                    related_entities_json,
                    source_refs_json,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :entity_id,
                    :entity_key,
                    :scope_type,
                    :scope_id,
                    :owner_agent_id,
                    :industry_instance_id,
                    :display_name,
                    :entity_type,
                    :summary,
                    :confidence,
                    :supporting_refs_json,
                    :contradicting_refs_json,
                    :related_entities_json,
                    :source_refs_json,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(entity_id) DO UPDATE SET
                    entity_key = excluded.entity_key,
                    scope_type = excluded.scope_type,
                    scope_id = excluded.scope_id,
                    owner_agent_id = excluded.owner_agent_id,
                    industry_instance_id = excluded.industry_instance_id,
                    display_name = excluded.display_name,
                    entity_type = excluded.entity_type,
                    summary = excluded.summary,
                    confidence = excluded.confidence,
                    supporting_refs_json = excluded.supporting_refs_json,
                    contradicting_refs_json = excluded.contradicting_refs_json,
                    related_entities_json = excluded.related_entities_json,
                    source_refs_json = excluded.source_refs_json,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return record

    def delete_view(self, entity_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM memory_entity_views WHERE entity_id = ?",
                (entity_id,),
            )
        return cursor.rowcount > 0

    def clear(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> int:
        return _delete_with_optional_scope(
            store=self._store,
            table_name="memory_entity_views",
            scope_type=scope_type,
            scope_id=scope_id,
        )


class SqliteMemoryOpinionViewRepository(BaseMemoryOpinionViewRepository):
    """SQLite-backed repository for compiled opinion/confidence memory views."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_view(self, opinion_id: str) -> MemoryOpinionViewRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM memory_opinion_views WHERE opinion_id = ?",
                (opinion_id,),
            ).fetchone()
        return _memory_opinion_view_from_row(row)

    def list_views(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        subject_key: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryOpinionViewRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if subject_key is not None:
            clauses.append("subject_key = ?")
            params.append(subject_key)
        query = "SELECT * FROM memory_opinion_views"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY confidence DESC, updated_at DESC, created_at DESC"
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            record
            for record in (_memory_opinion_view_from_row(row) for row in rows)
            if record is not None
        ]

    def upsert_view(self, record: MemoryOpinionViewRecord) -> MemoryOpinionViewRecord:
        payload = _payload(record)
        payload["supporting_refs_json"] = json.dumps(
            record.supporting_refs,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["contradicting_refs_json"] = json.dumps(
            record.contradicting_refs,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["entity_keys_json"] = json.dumps(
            record.entity_keys,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["source_refs_json"] = json.dumps(
            record.source_refs,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["metadata_json"] = _encode_json(record.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO memory_opinion_views (
                    opinion_id,
                    subject_key,
                    scope_type,
                    scope_id,
                    owner_agent_id,
                    industry_instance_id,
                    opinion_key,
                    stance,
                    summary,
                    confidence,
                    supporting_refs_json,
                    contradicting_refs_json,
                    entity_keys_json,
                    source_refs_json,
                    last_reflected_at,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :opinion_id,
                    :subject_key,
                    :scope_type,
                    :scope_id,
                    :owner_agent_id,
                    :industry_instance_id,
                    :opinion_key,
                    :stance,
                    :summary,
                    :confidence,
                    :supporting_refs_json,
                    :contradicting_refs_json,
                    :entity_keys_json,
                    :source_refs_json,
                    :last_reflected_at,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(opinion_id) DO UPDATE SET
                    subject_key = excluded.subject_key,
                    scope_type = excluded.scope_type,
                    scope_id = excluded.scope_id,
                    owner_agent_id = excluded.owner_agent_id,
                    industry_instance_id = excluded.industry_instance_id,
                    opinion_key = excluded.opinion_key,
                    stance = excluded.stance,
                    summary = excluded.summary,
                    confidence = excluded.confidence,
                    supporting_refs_json = excluded.supporting_refs_json,
                    contradicting_refs_json = excluded.contradicting_refs_json,
                    entity_keys_json = excluded.entity_keys_json,
                    source_refs_json = excluded.source_refs_json,
                    last_reflected_at = excluded.last_reflected_at,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return record

    def delete_view(self, opinion_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM memory_opinion_views WHERE opinion_id = ?",
                (opinion_id,),
            )
        return cursor.rowcount > 0

    def clear(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> int:
        return _delete_with_optional_scope(
            store=self._store,
            table_name="memory_opinion_views",
            scope_type=scope_type,
            scope_id=scope_id,
        )


class SqliteMemoryReflectionRunRepository(BaseMemoryReflectionRunRepository):
    """SQLite-backed repository for memory reflection job records."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_run(self, run_id: str) -> MemoryReflectionRunRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM memory_reflection_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return _memory_reflection_run_from_row(row)

    def list_runs(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryReflectionRunRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        query = "SELECT * FROM memory_reflection_runs"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, created_at DESC"
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            record
            for record in (_memory_reflection_run_from_row(row) for row in rows)
            if record is not None
        ]

    def upsert_run(self, record: MemoryReflectionRunRecord) -> MemoryReflectionRunRecord:
        payload = _payload(record)
        payload["source_refs_json"] = json.dumps(
            record.source_refs,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["generated_entity_ids_json"] = json.dumps(
            record.generated_entity_ids,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["generated_opinion_ids_json"] = json.dumps(
            record.generated_opinion_ids,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["metadata_json"] = _encode_json(record.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO memory_reflection_runs (
                    run_id,
                    scope_type,
                    scope_id,
                    owner_agent_id,
                    industry_instance_id,
                    trigger_kind,
                    status,
                    summary,
                    source_refs_json,
                    generated_entity_ids_json,
                    generated_opinion_ids_json,
                    metadata_json,
                    started_at,
                    completed_at,
                    created_at,
                    updated_at
                ) VALUES (
                    :run_id,
                    :scope_type,
                    :scope_id,
                    :owner_agent_id,
                    :industry_instance_id,
                    :trigger_kind,
                    :status,
                    :summary,
                    :source_refs_json,
                    :generated_entity_ids_json,
                    :generated_opinion_ids_json,
                    :metadata_json,
                    :started_at,
                    :completed_at,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(run_id) DO UPDATE SET
                    scope_type = excluded.scope_type,
                    scope_id = excluded.scope_id,
                    owner_agent_id = excluded.owner_agent_id,
                    industry_instance_id = excluded.industry_instance_id,
                    trigger_kind = excluded.trigger_kind,
                    status = excluded.status,
                    summary = excluded.summary,
                    source_refs_json = excluded.source_refs_json,
                    generated_entity_ids_json = excluded.generated_entity_ids_json,
                    generated_opinion_ids_json = excluded.generated_opinion_ids_json,
                    metadata_json = excluded.metadata_json,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return record

    def delete_run(self, run_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM memory_reflection_runs WHERE run_id = ?",
                (run_id,),
            )
        return cursor.rowcount > 0


def _delete_with_optional_scope(
    *,
    store: SQLiteStateStore,
    table_name: str,
    scope_type: str | None = None,
    scope_id: str | None = None,
) -> int:
    clauses: list[str] = []
    params: list[Any] = []
    if scope_type is not None:
        clauses.append("scope_type = ?")
        params.append(scope_type)
    if scope_id is not None:
        clauses.append("scope_id = ?")
        params.append(scope_id)
    query = f"DELETE FROM {table_name}"
    if clauses:
        query = f"{query} WHERE {' AND '.join(clauses)}"
    with store.connection() as conn:
        cursor = conn.execute(query, params)
    return int(cursor.rowcount or 0)


def _memory_fact_index_from_row(
    row: sqlite3.Row | None,
) -> MemoryFactIndexRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["entity_keys"] = _decode_json_list(payload.pop("entity_keys_json", None)) or []
    payload["opinion_keys"] = _decode_json_list(payload.pop("opinion_keys_json", None)) or []
    payload["tags"] = _decode_json_list(payload.pop("tags_json", None)) or []
    payload["role_bindings"] = _decode_json_list(payload.pop("role_bindings_json", None)) or []
    payload["evidence_refs"] = _decode_json_list(payload.pop("evidence_refs_json", None)) or []
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return MemoryFactIndexRecord.model_validate(payload)


def _memory_entity_view_from_row(
    row: sqlite3.Row | None,
) -> MemoryEntityViewRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["supporting_refs"] = _decode_json_list(payload.pop("supporting_refs_json", None)) or []
    payload["contradicting_refs"] = _decode_json_list(
        payload.pop("contradicting_refs_json", None),
    ) or []
    payload["related_entities"] = _decode_json_list(
        payload.pop("related_entities_json", None),
    ) or []
    payload["source_refs"] = _decode_json_list(payload.pop("source_refs_json", None)) or []
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return MemoryEntityViewRecord.model_validate(payload)


def _memory_opinion_view_from_row(
    row: sqlite3.Row | None,
) -> MemoryOpinionViewRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["supporting_refs"] = _decode_json_list(payload.pop("supporting_refs_json", None)) or []
    payload["contradicting_refs"] = _decode_json_list(
        payload.pop("contradicting_refs_json", None),
    ) or []
    payload["entity_keys"] = _decode_json_list(payload.pop("entity_keys_json", None)) or []
    payload["source_refs"] = _decode_json_list(payload.pop("source_refs_json", None)) or []
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return MemoryOpinionViewRecord.model_validate(payload)


def _memory_reflection_run_from_row(
    row: sqlite3.Row | None,
) -> MemoryReflectionRunRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["source_refs"] = _decode_json_list(payload.pop("source_refs_json", None)) or []
    payload["generated_entity_ids"] = _decode_json_list(
        payload.pop("generated_entity_ids_json", None),
    ) or []
    payload["generated_opinion_ids"] = _decode_json_list(
        payload.pop("generated_opinion_ids_json", None),
    ) or []
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return MemoryReflectionRunRecord.model_validate(payload)
