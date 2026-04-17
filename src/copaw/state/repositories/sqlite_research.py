# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any

from .sqlite_shared import *  # noqa: F401,F403
from ..models_research import ResearchSessionRecord, ResearchSessionRoundRecord
from ..store import SQLiteStateStore
from .base import BaseResearchSessionRepository

_RESEARCH_METADATA_KEY = "__copaw_research"


def _decode_json_mapping_list(value: str | None) -> list[dict[str, Any]]:
    raw_text = str(value or "").strip()
    if not raw_text:
        return []
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [dict(item) for item in payload if isinstance(item, dict)]


def _encode_research_metadata(
    metadata: dict[str, Any] | None,
    *,
    brief: dict[str, Any] | None = None,
    sources: list[dict[str, Any]] | None = None,
) -> str:
    payload = dict(metadata or {})
    reserved: dict[str, Any] = {}
    if brief:
        reserved["brief"] = dict(brief)
    if sources:
        reserved["sources"] = [dict(item) for item in sources if isinstance(item, dict)]
    if reserved:
        payload[_RESEARCH_METADATA_KEY] = reserved
    else:
        payload.pop(_RESEARCH_METADATA_KEY, None)
    return _encode_json(payload)


def _research_session_from_row(row: sqlite3.Row | None) -> ResearchSessionRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["stable_findings"] = _decode_json_list(payload.pop("stable_findings_json", None)) or []
    payload["open_questions"] = _decode_json_list(payload.pop("open_questions_json", None)) or []
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return ResearchSessionRecord.model_validate(payload)


def _research_round_from_row(row: sqlite3.Row | None) -> ResearchSessionRoundRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["raw_links"] = _decode_json_mapping_list(payload.pop("raw_links_json", None))
    payload["selected_links"] = _decode_json_mapping_list(
        payload.pop("selected_links_json", None),
    )
    payload["downloaded_artifacts"] = _decode_json_mapping_list(
        payload.pop("downloaded_artifacts_json", None),
    )
    payload["new_findings"] = _decode_json_list(payload.pop("new_findings_json", None)) or []
    payload["remaining_gaps"] = _decode_json_list(payload.pop("remaining_gaps_json", None)) or []
    payload["evidence_ids"] = _decode_json_list(payload.pop("evidence_ids_json", None)) or []
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return ResearchSessionRoundRecord.model_validate(payload)


class SqliteResearchSessionRepository(BaseResearchSessionRepository):
    """SQLite-backed repository for research sessions and rounds."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_research_session(self, session_id: str) -> ResearchSessionRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM research_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return _research_session_from_row(row)

    def list_research_sessions(
        self,
        *,
        provider: str | None = None,
        owner_agent_id: str | None = None,
        supervisor_agent_id: str | None = None,
        trigger_source: str | None = None,
        industry_instance_id: str | None = None,
        work_context_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[ResearchSessionRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        for field_name, value in (
            ("provider", provider),
            ("owner_agent_id", owner_agent_id),
            ("supervisor_agent_id", supervisor_agent_id),
            ("trigger_source", trigger_source),
            ("industry_instance_id", industry_instance_id),
            ("work_context_id", work_context_id),
            ("status", status),
        ):
            if value is None:
                continue
            clauses.append(f"{field_name} = ?")
            params.append(value)
        query = "SELECT * FROM research_sessions"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, created_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            session
            for session in (_research_session_from_row(row) for row in rows)
            if session is not None
        ]

    def upsert_research_session(
        self,
        session: ResearchSessionRecord,
    ) -> ResearchSessionRecord:
        payload = _payload(session)
        payload["stable_findings_json"] = _encode_json(session.stable_findings)
        payload["open_questions_json"] = _encode_json(session.open_questions)
        payload["metadata_json"] = _encode_research_metadata(
            session.metadata,
            brief=session.brief,
        )
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO research_sessions (
                    id,
                    provider,
                    industry_instance_id,
                    work_context_id,
                    owner_agent_id,
                    supervisor_agent_id,
                    trigger_source,
                    goal,
                    status,
                    browser_session_id,
                    round_count,
                    link_depth_count,
                    download_count,
                    stable_findings_json,
                    open_questions_json,
                    final_report_id,
                    failure_class,
                    failure_summary,
                    completed_at,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :provider,
                    :industry_instance_id,
                    :work_context_id,
                    :owner_agent_id,
                    :supervisor_agent_id,
                    :trigger_source,
                    :goal,
                    :status,
                    :browser_session_id,
                    :round_count,
                    :link_depth_count,
                    :download_count,
                    :stable_findings_json,
                    :open_questions_json,
                    :final_report_id,
                    :failure_class,
                    :failure_summary,
                    :completed_at,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    provider = excluded.provider,
                    industry_instance_id = excluded.industry_instance_id,
                    work_context_id = excluded.work_context_id,
                    owner_agent_id = excluded.owner_agent_id,
                    supervisor_agent_id = excluded.supervisor_agent_id,
                    trigger_source = excluded.trigger_source,
                    goal = excluded.goal,
                    status = excluded.status,
                    browser_session_id = excluded.browser_session_id,
                    round_count = excluded.round_count,
                    link_depth_count = excluded.link_depth_count,
                    download_count = excluded.download_count,
                    stable_findings_json = excluded.stable_findings_json,
                    open_questions_json = excluded.open_questions_json,
                    final_report_id = excluded.final_report_id,
                    failure_class = excluded.failure_class,
                    failure_summary = excluded.failure_summary,
                    completed_at = excluded.completed_at,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return session

    def delete_research_session(self, session_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM research_sessions WHERE id = ?",
                (session_id,),
            )
        return cursor.rowcount > 0

    def get_research_round(self, round_id: str) -> ResearchSessionRoundRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM research_session_rounds WHERE id = ?",
                (round_id,),
            ).fetchone()
        return _research_round_from_row(row)

    def list_research_rounds(
        self,
        *,
        session_id: str,
        decision: str | None = None,
        limit: int | None = None,
    ) -> list[ResearchSessionRoundRecord]:
        clauses = ["session_id = ?"]
        params: list[Any] = [session_id]
        if decision is not None:
            clauses.append("decision = ?")
            params.append(decision)
        query = (
            "SELECT * FROM research_session_rounds "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY round_index ASC, created_at ASC"
        )
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            round_record
            for round_record in (_research_round_from_row(row) for row in rows)
            if round_record is not None
        ]

    def upsert_research_round(
        self,
        round_record: ResearchSessionRoundRecord,
    ) -> ResearchSessionRoundRecord:
        payload = _payload(round_record)
        payload["raw_links_json"] = _encode_json(round_record.raw_links)
        payload["selected_links_json"] = _encode_json(round_record.selected_links)
        payload["downloaded_artifacts_json"] = _encode_json(round_record.downloaded_artifacts)
        payload["new_findings_json"] = _encode_json(round_record.new_findings)
        payload["remaining_gaps_json"] = _encode_json(round_record.remaining_gaps)
        payload["evidence_ids_json"] = _encode_json(round_record.evidence_ids)
        payload["metadata_json"] = _encode_research_metadata(
            round_record.metadata,
            sources=round_record.sources,
        )
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO research_session_rounds (
                    id,
                    session_id,
                    round_index,
                    question,
                    generated_prompt,
                    response_excerpt,
                    response_summary,
                    raw_links_json,
                    selected_links_json,
                    downloaded_artifacts_json,
                    new_findings_json,
                    remaining_gaps_json,
                    decision,
                    evidence_ids_json,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :session_id,
                    :round_index,
                    :question,
                    :generated_prompt,
                    :response_excerpt,
                    :response_summary,
                    :raw_links_json,
                    :selected_links_json,
                    :downloaded_artifacts_json,
                    :new_findings_json,
                    :remaining_gaps_json,
                    :decision,
                    :evidence_ids_json,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    session_id = excluded.session_id,
                    round_index = excluded.round_index,
                    question = excluded.question,
                    generated_prompt = excluded.generated_prompt,
                    response_excerpt = excluded.response_excerpt,
                    response_summary = excluded.response_summary,
                    raw_links_json = excluded.raw_links_json,
                    selected_links_json = excluded.selected_links_json,
                    downloaded_artifacts_json = excluded.downloaded_artifacts_json,
                    new_findings_json = excluded.new_findings_json,
                    remaining_gaps_json = excluded.remaining_gaps_json,
                    decision = excluded.decision,
                    evidence_ids_json = excluded.evidence_ids_json,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return round_record

    def delete_research_round(self, round_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM research_session_rounds WHERE id = ?",
                (round_id,),
            )
        return cursor.rowcount > 0


__all__ = ["SqliteResearchSessionRepository"]
