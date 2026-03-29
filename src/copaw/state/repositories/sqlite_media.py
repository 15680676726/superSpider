# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any

from ..models import MediaAnalysisRecord
from ..store import SQLiteStateStore
from .base import BaseMediaAnalysisRepository
from .sqlite_shared import (
    _decode_any_json,
    _decode_json_list,
    _encode_json,
    _payload,
)


class SqliteMediaAnalysisRepository(BaseMediaAnalysisRepository):
    """SQLite-backed repository for persisted media analyses."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_analysis(self, analysis_id: str) -> MediaAnalysisRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM media_analyses WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
        return _media_analysis_from_row(row)

    def list_analyses(
        self,
        *,
        industry_instance_id: str | None = None,
        thread_id: str | None = None,
        work_context_id: str | None = None,
        entry_point: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[MediaAnalysisRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if thread_id is not None:
            clauses.append("thread_id = ?")
            params.append(thread_id)
        if work_context_id is not None:
            clauses.append("work_context_id = ?")
            params.append(work_context_id)
        if entry_point is not None:
            clauses.append("entry_point = ?")
            params.append(entry_point)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        query = "SELECT * FROM media_analyses"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            record
            for record in (_media_analysis_from_row(row) for row in rows)
            if record is not None
        ]

    def upsert_analysis(
        self,
        analysis: MediaAnalysisRecord,
    ) -> MediaAnalysisRecord:
        payload = _payload(analysis)
        for field_name in (
            "asset_artifact_ids",
            "derived_artifact_ids",
            "timeline_summary",
            "entities",
            "claims",
            "recommended_actions",
            "warnings",
            "knowledge_document_ids",
            "evidence_ids",
        ):
            payload[f"{field_name}_json"] = json.dumps(
                payload.pop(field_name),
                ensure_ascii=False,
                sort_keys=True,
            )
        payload["structured_summary_json"] = _encode_json(analysis.structured_summary)
        payload["metadata_json"] = _encode_json(analysis.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO media_analyses (
                    analysis_id,
                    industry_instance_id,
                    thread_id,
                    work_context_id,
                    entry_point,
                    purpose,
                    source_kind,
                    source_ref,
                    source_hash,
                    declared_media_type,
                    detected_media_type,
                    analysis_mode,
                    status,
                    title,
                    url,
                    filename,
                    mime_type,
                    size_bytes,
                    asset_artifact_ids_json,
                    derived_artifact_ids_json,
                    transcript_artifact_id,
                    structured_summary_json,
                    timeline_summary_json,
                    entities_json,
                    claims_json,
                    recommended_actions_json,
                    warnings_json,
                    knowledge_document_ids_json,
                    evidence_ids_json,
                    strategy_writeback_status,
                    backlog_writeback_status,
                    error_message,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :analysis_id,
                    :industry_instance_id,
                    :thread_id,
                    :work_context_id,
                    :entry_point,
                    :purpose,
                    :source_kind,
                    :source_ref,
                    :source_hash,
                    :declared_media_type,
                    :detected_media_type,
                    :analysis_mode,
                    :status,
                    :title,
                    :url,
                    :filename,
                    :mime_type,
                    :size_bytes,
                    :asset_artifact_ids_json,
                    :derived_artifact_ids_json,
                    :transcript_artifact_id,
                    :structured_summary_json,
                    :timeline_summary_json,
                    :entities_json,
                    :claims_json,
                    :recommended_actions_json,
                    :warnings_json,
                    :knowledge_document_ids_json,
                    :evidence_ids_json,
                    :strategy_writeback_status,
                    :backlog_writeback_status,
                    :error_message,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(analysis_id) DO UPDATE SET
                    industry_instance_id = excluded.industry_instance_id,
                    thread_id = excluded.thread_id,
                    work_context_id = excluded.work_context_id,
                    entry_point = excluded.entry_point,
                    purpose = excluded.purpose,
                    source_kind = excluded.source_kind,
                    source_ref = excluded.source_ref,
                    source_hash = excluded.source_hash,
                    declared_media_type = excluded.declared_media_type,
                    detected_media_type = excluded.detected_media_type,
                    analysis_mode = excluded.analysis_mode,
                    status = excluded.status,
                    title = excluded.title,
                    url = excluded.url,
                    filename = excluded.filename,
                    mime_type = excluded.mime_type,
                    size_bytes = excluded.size_bytes,
                    asset_artifact_ids_json = excluded.asset_artifact_ids_json,
                    derived_artifact_ids_json = excluded.derived_artifact_ids_json,
                    transcript_artifact_id = excluded.transcript_artifact_id,
                    structured_summary_json = excluded.structured_summary_json,
                    timeline_summary_json = excluded.timeline_summary_json,
                    entities_json = excluded.entities_json,
                    claims_json = excluded.claims_json,
                    recommended_actions_json = excluded.recommended_actions_json,
                    warnings_json = excluded.warnings_json,
                    knowledge_document_ids_json = excluded.knowledge_document_ids_json,
                    evidence_ids_json = excluded.evidence_ids_json,
                    strategy_writeback_status = excluded.strategy_writeback_status,
                    backlog_writeback_status = excluded.backlog_writeback_status,
                    error_message = excluded.error_message,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return analysis

    def delete_analysis(self, analysis_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM media_analyses WHERE analysis_id = ?",
                (analysis_id,),
            )
        return cursor.rowcount > 0


def _media_analysis_from_row(row: Any) -> MediaAnalysisRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["asset_artifact_ids"] = (
        _decode_json_list(payload.pop("asset_artifact_ids_json", None)) or []
    )
    payload["derived_artifact_ids"] = (
        _decode_json_list(payload.pop("derived_artifact_ids_json", None)) or []
    )
    payload["timeline_summary"] = (
        _decode_any_json(payload.pop("timeline_summary_json", None)) or []
    )
    payload["entities"] = _decode_json_list(payload.pop("entities_json", None)) or []
    payload["claims"] = _decode_json_list(payload.pop("claims_json", None)) or []
    payload["recommended_actions"] = (
        _decode_json_list(payload.pop("recommended_actions_json", None)) or []
    )
    payload["warnings"] = _decode_json_list(payload.pop("warnings_json", None)) or []
    payload["knowledge_document_ids"] = (
        _decode_json_list(payload.pop("knowledge_document_ids_json", None)) or []
    )
    payload["evidence_ids"] = (
        _decode_json_list(payload.pop("evidence_ids_json", None)) or []
    )
    payload["structured_summary"] = (
        _decode_any_json(payload.pop("structured_summary_json", None)) or {}
    )
    payload["metadata"] = _decode_any_json(payload.pop("metadata_json", None)) or {}
    return MediaAnalysisRecord.model_validate(payload)


__all__ = ["SqliteMediaAnalysisRepository", "_media_analysis_from_row"]
