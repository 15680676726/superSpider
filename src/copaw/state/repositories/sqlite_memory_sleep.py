# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sqlite3
from typing import Any

from pydantic import BaseModel

from ..models_memory import (
    IndustryMemoryProfileRecord,
    MemoryAliasMapRecord,
    MemoryConflictProposalRecord,
    MemoryMergeResultRecord,
    MemoryStructureProposalRecord,
    MemoryScopeDigestRecord,
    MemorySleepJobRecord,
    MemorySleepScopeStateRecord,
    MemorySoftRuleRecord,
    WorkContextMemoryOverlayRecord,
)
from ..store import SQLiteStateStore
from .base import BaseMemorySleepRepository
from .sqlite_shared import _decode_json_list, _decode_json_mapping, _encode_json, _payload

_SCOPE_STATE_COLUMNS = (
    "scope_key",
    "scope_type",
    "scope_id",
    "owner_agent_id",
    "industry_instance_id",
    "is_dirty",
    "dirty_reasons_json",
    "dirty_source_refs_json",
    "dirty_count",
    "first_dirtied_at",
    "last_dirtied_at",
    "last_sleep_job_id",
    "last_sleep_at",
    "metadata_json",
    "created_at",
    "updated_at",
)
_SLEEP_JOB_COLUMNS = (
    "job_id",
    "scope_type",
    "scope_id",
    "owner_agent_id",
    "industry_instance_id",
    "trigger_kind",
    "window_start",
    "window_end",
    "status",
    "input_refs_json",
    "output_refs_json",
    "model_ref",
    "started_at",
    "completed_at",
    "metadata_json",
    "created_at",
    "updated_at",
)
_DIGEST_COLUMNS = (
    "digest_id",
    "scope_type",
    "scope_id",
    "headline",
    "summary",
    "current_constraints_json",
    "current_focus_json",
    "top_entities_json",
    "top_relations_json",
    "evidence_refs_json",
    "source_job_id",
    "version",
    "status",
    "metadata_json",
    "created_at",
    "updated_at",
)
_ALIAS_COLUMNS = (
    "alias_id",
    "scope_type",
    "scope_id",
    "canonical_term",
    "aliases_json",
    "confidence",
    "evidence_refs_json",
    "source_job_id",
    "status",
    "metadata_json",
    "created_at",
    "updated_at",
)
_MERGE_COLUMNS = (
    "merge_id",
    "scope_type",
    "scope_id",
    "merged_title",
    "merged_summary",
    "merged_source_refs_json",
    "evidence_refs_json",
    "source_job_id",
    "status",
    "metadata_json",
    "created_at",
    "updated_at",
)
_SOFT_RULE_COLUMNS = (
    "rule_id",
    "scope_type",
    "scope_id",
    "rule_text",
    "rule_kind",
    "evidence_refs_json",
    "hit_count",
    "day_span",
    "conflict_count",
    "risk_level",
    "state",
    "source_job_id",
    "expires_at",
    "last_supported_at",
    "metadata_json",
    "created_at",
    "updated_at",
)
_CONFLICT_COLUMNS = (
    "proposal_id",
    "scope_type",
    "scope_id",
    "proposal_kind",
    "title",
    "summary",
    "conflicting_refs_json",
    "supporting_refs_json",
    "recommended_action",
    "risk_level",
    "status",
    "source_job_id",
    "metadata_json",
    "created_at",
    "updated_at",
)
_INDUSTRY_PROFILE_COLUMNS = (
    "profile_id",
    "industry_instance_id",
    "headline",
    "summary",
    "strategic_direction",
    "active_constraints_json",
    "active_focuses_json",
    "key_entities_json",
    "key_relations_json",
    "evidence_refs_json",
    "source_job_id",
    "source_digest_id",
    "version",
    "status",
    "metadata_json",
    "created_at",
    "updated_at",
)
_WORK_CONTEXT_OVERLAY_COLUMNS = (
    "overlay_id",
    "work_context_id",
    "industry_instance_id",
    "base_profile_id",
    "headline",
    "summary",
    "focus_summary",
    "active_constraints_json",
    "active_focuses_json",
    "active_entities_json",
    "active_relations_json",
    "evidence_refs_json",
    "source_job_id",
    "source_digest_id",
    "version",
    "status",
    "metadata_json",
    "created_at",
    "updated_at",
)
_STRUCTURE_PROPOSAL_COLUMNS = (
    "proposal_id",
    "scope_type",
    "scope_id",
    "industry_instance_id",
    "work_context_id",
    "proposal_kind",
    "title",
    "summary",
    "recommended_action",
    "candidate_profile_id",
    "candidate_overlay_id",
    "source_job_id",
    "evidence_refs_json",
    "risk_level",
    "status",
    "metadata_json",
    "created_at",
    "updated_at",
)


def _json_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False, sort_keys=True)


def _decode_record(
    model_type: type[BaseModel],
    row: sqlite3.Row | None,
    *,
    list_fields: tuple[tuple[str, str], ...] = (),
    bool_fields: tuple[str, ...] = (),
) -> BaseModel | None:
    if row is None:
        return None
    payload = dict(row)
    for field_name, json_column in list_fields:
        payload[field_name] = _decode_json_list(payload.pop(json_column, None)) or []
    for field_name in bool_fields:
        payload[field_name] = bool(payload.get(field_name, 0))
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return model_type.model_validate(payload)


def _scope_state_from_row(row: sqlite3.Row | None) -> MemorySleepScopeStateRecord | None:
    record = _decode_record(
        MemorySleepScopeStateRecord,
        row,
        list_fields=(
            ("dirty_reasons", "dirty_reasons_json"),
            ("dirty_source_refs", "dirty_source_refs_json"),
        ),
        bool_fields=("is_dirty",),
    )
    return record if isinstance(record, MemorySleepScopeStateRecord) else None


def _sleep_job_from_row(row: sqlite3.Row | None) -> MemorySleepJobRecord | None:
    record = _decode_record(
        MemorySleepJobRecord,
        row,
        list_fields=(("input_refs", "input_refs_json"), ("output_refs", "output_refs_json")),
    )
    return record if isinstance(record, MemorySleepJobRecord) else None


def _digest_from_row(row: sqlite3.Row | None) -> MemoryScopeDigestRecord | None:
    record = _decode_record(
        MemoryScopeDigestRecord,
        row,
        list_fields=(
            ("current_constraints", "current_constraints_json"),
            ("current_focus", "current_focus_json"),
            ("top_entities", "top_entities_json"),
            ("top_relations", "top_relations_json"),
            ("evidence_refs", "evidence_refs_json"),
        ),
    )
    return record if isinstance(record, MemoryScopeDigestRecord) else None


def _alias_from_row(row: sqlite3.Row | None) -> MemoryAliasMapRecord | None:
    record = _decode_record(
        MemoryAliasMapRecord,
        row,
        list_fields=(("aliases", "aliases_json"), ("evidence_refs", "evidence_refs_json")),
    )
    return record if isinstance(record, MemoryAliasMapRecord) else None


def _merge_from_row(row: sqlite3.Row | None) -> MemoryMergeResultRecord | None:
    record = _decode_record(
        MemoryMergeResultRecord,
        row,
        list_fields=(
            ("merged_source_refs", "merged_source_refs_json"),
            ("evidence_refs", "evidence_refs_json"),
        ),
    )
    return record if isinstance(record, MemoryMergeResultRecord) else None


def _soft_rule_from_row(row: sqlite3.Row | None) -> MemorySoftRuleRecord | None:
    record = _decode_record(
        MemorySoftRuleRecord,
        row,
        list_fields=(("evidence_refs", "evidence_refs_json"),),
    )
    return record if isinstance(record, MemorySoftRuleRecord) else None


def _conflict_from_row(row: sqlite3.Row | None) -> MemoryConflictProposalRecord | None:
    record = _decode_record(
        MemoryConflictProposalRecord,
        row,
        list_fields=(
            ("conflicting_refs", "conflicting_refs_json"),
            ("supporting_refs", "supporting_refs_json"),
        ),
    )
    return record if isinstance(record, MemoryConflictProposalRecord) else None


def _industry_profile_from_row(row: sqlite3.Row | None) -> IndustryMemoryProfileRecord | None:
    record = _decode_record(
        IndustryMemoryProfileRecord,
        row,
        list_fields=(
            ("active_constraints", "active_constraints_json"),
            ("active_focuses", "active_focuses_json"),
            ("key_entities", "key_entities_json"),
            ("key_relations", "key_relations_json"),
            ("evidence_refs", "evidence_refs_json"),
        ),
    )
    return record if isinstance(record, IndustryMemoryProfileRecord) else None


def _work_context_overlay_from_row(row: sqlite3.Row | None) -> WorkContextMemoryOverlayRecord | None:
    record = _decode_record(
        WorkContextMemoryOverlayRecord,
        row,
        list_fields=(
            ("active_constraints", "active_constraints_json"),
            ("active_focuses", "active_focuses_json"),
            ("active_entities", "active_entities_json"),
            ("active_relations", "active_relations_json"),
            ("evidence_refs", "evidence_refs_json"),
        ),
    )
    return record if isinstance(record, WorkContextMemoryOverlayRecord) else None


def _structure_proposal_from_row(row: sqlite3.Row | None) -> MemoryStructureProposalRecord | None:
    record = _decode_record(
        MemoryStructureProposalRecord,
        row,
        list_fields=(("evidence_refs", "evidence_refs_json"),),
    )
    return record if isinstance(record, MemoryStructureProposalRecord) else None


class SqliteMemorySleepRepository(BaseMemorySleepRepository):
    """SQLite-backed repository for B+ sleep-layer artifacts."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def _list(
        self,
        *,
        table: str,
        clauses: list[str],
        params: list[Any],
        order_by: str,
        limit: int | None,
        parser,
    ) -> list[Any]:
        query = f"SELECT * FROM {table}"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY {order_by}"
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [record for record in (parser(row) for row in rows) if record is not None]

    def _upsert(
        self,
        *,
        table: str,
        pk: str,
        columns: tuple[str, ...],
        record: BaseModel,
        extra_payload: dict[str, Any],
        before_write=None,
    ) -> BaseModel:
        payload = _payload(record)
        payload.update(extra_payload)
        names = ", ".join(columns)
        values = ", ".join(f":{column}" for column in columns)
        updates = ", ".join(f"{column} = excluded.{column}" for column in columns if column != pk)
        with self._store.connection() as conn:
            if callable(before_write):
                before_write(conn, payload, record)
            conn.execute(
                f"""
                INSERT INTO {table} ({names})
                VALUES ({values})
                ON CONFLICT({pk}) DO UPDATE SET
                    {updates}
                """,
                payload,
            )
        return record

    def get_scope_state(
        self,
        *,
        scope_type: str,
        scope_id: str,
    ) -> MemorySleepScopeStateRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM memory_sleep_scope_states WHERE scope_type = ? AND scope_id = ?",
                (scope_type, scope_id),
            ).fetchone()
        return _scope_state_from_row(row)

    def list_scope_states(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        dirty_only: bool = False,
        limit: int | None = None,
    ) -> list[MemorySleepScopeStateRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if dirty_only:
            clauses.append("is_dirty = 1")
        return self._list(
            table="memory_sleep_scope_states",
            clauses=clauses,
            params=params,
            order_by="is_dirty DESC, last_dirtied_at DESC, updated_at DESC, created_at DESC",
            limit=limit,
            parser=_scope_state_from_row,
        )

    def upsert_scope_state(
        self,
        record: MemorySleepScopeStateRecord,
    ) -> MemorySleepScopeStateRecord:
        record = MemorySleepScopeStateRecord.model_validate(record.model_dump(mode="python"))
        saved = self._upsert(
            table="memory_sleep_scope_states",
            pk="scope_key",
            columns=_SCOPE_STATE_COLUMNS,
            record=record,
            extra_payload={
                "is_dirty": 1 if record.is_dirty else 0,
                "dirty_reasons_json": _json_list(record.dirty_reasons),
                "dirty_source_refs_json": _json_list(record.dirty_source_refs),
                "metadata_json": _encode_json(record.metadata),
            },
        )
        return saved if isinstance(saved, MemorySleepScopeStateRecord) else record

    def get_sleep_job(self, job_id: str) -> MemorySleepJobRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM memory_sleep_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return _sleep_job_from_row(row)

    def list_sleep_jobs(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[MemorySleepJobRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        return self._list(
            table="memory_sleep_jobs",
            clauses=clauses,
            params=params,
            order_by="updated_at DESC, created_at DESC",
            limit=limit,
            parser=_sleep_job_from_row,
        )

    def upsert_sleep_job(self, record: MemorySleepJobRecord) -> MemorySleepJobRecord:
        record = MemorySleepJobRecord.model_validate(record.model_dump(mode="python"))
        saved = self._upsert(
            table="memory_sleep_jobs",
            pk="job_id",
            columns=_SLEEP_JOB_COLUMNS,
            record=record,
            extra_payload={
                "input_refs_json": _json_list(record.input_refs),
                "output_refs_json": _json_list(record.output_refs),
                "metadata_json": _encode_json(record.metadata),
            },
        )
        return saved if isinstance(saved, MemorySleepJobRecord) else record

    def get_active_digest(
        self,
        scope_type: str,
        scope_id: str,
    ) -> MemoryScopeDigestRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM memory_scope_digests
                WHERE scope_type = ? AND scope_id = ? AND status = 'active'
                ORDER BY version DESC, updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (scope_type, scope_id),
            ).fetchone()
        return _digest_from_row(row)

    def list_digests(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryScopeDigestRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        return self._list(
            table="memory_scope_digests",
            clauses=clauses,
            params=params,
            order_by="CASE status WHEN 'active' THEN 0 ELSE 1 END, version DESC, updated_at DESC, created_at DESC",
            limit=limit,
            parser=_digest_from_row,
        )

    def upsert_digest(self, record: MemoryScopeDigestRecord) -> MemoryScopeDigestRecord:
        record = MemoryScopeDigestRecord.model_validate(record.model_dump(mode="python"))

        def _supersede(conn: sqlite3.Connection, payload: dict[str, Any], current: BaseModel) -> None:
            if not isinstance(current, MemoryScopeDigestRecord) or current.status != "active":
                return
            conn.execute(
                """
                UPDATE memory_scope_digests
                SET status = 'superseded',
                    updated_at = ?
                WHERE scope_type = ?
                  AND scope_id = ?
                  AND digest_id != ?
                  AND status = 'active'
                """,
                (payload["updated_at"], current.scope_type, current.scope_id, current.digest_id),
            )

        saved = self._upsert(
            table="memory_scope_digests",
            pk="digest_id",
            columns=_DIGEST_COLUMNS,
            record=record,
            extra_payload={
                "current_constraints_json": _json_list(record.current_constraints),
                "current_focus_json": _json_list(record.current_focus),
                "top_entities_json": _json_list(record.top_entities),
                "top_relations_json": _json_list(record.top_relations),
                "evidence_refs_json": _json_list(record.evidence_refs),
                "metadata_json": _encode_json(record.metadata),
            },
            before_write=_supersede,
        )
        return saved if isinstance(saved, MemoryScopeDigestRecord) else record

    def list_alias_maps(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        canonical_term: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryAliasMapRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if canonical_term is not None:
            clauses.append("canonical_term = ?")
            params.append(canonical_term)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        return self._list(
            table="memory_alias_maps",
            clauses=clauses,
            params=params,
            order_by="CASE status WHEN 'active' THEN 0 ELSE 1 END, confidence DESC, updated_at DESC, created_at DESC",
            limit=limit,
            parser=_alias_from_row,
        )

    def upsert_alias_map(self, record: MemoryAliasMapRecord) -> MemoryAliasMapRecord:
        record = MemoryAliasMapRecord.model_validate(record.model_dump(mode="python"))
        saved = self._upsert(
            table="memory_alias_maps",
            pk="alias_id",
            columns=_ALIAS_COLUMNS,
            record=record,
            extra_payload={
                "aliases_json": _json_list(record.aliases),
                "evidence_refs_json": _json_list(record.evidence_refs),
                "metadata_json": _encode_json(record.metadata),
            },
        )
        return saved if isinstance(saved, MemoryAliasMapRecord) else record

    def list_merge_results(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryMergeResultRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        return self._list(
            table="memory_merge_results",
            clauses=clauses,
            params=params,
            order_by="CASE status WHEN 'active' THEN 0 ELSE 1 END, updated_at DESC, created_at DESC",
            limit=limit,
            parser=_merge_from_row,
        )

    def upsert_merge_result(self, record: MemoryMergeResultRecord) -> MemoryMergeResultRecord:
        record = MemoryMergeResultRecord.model_validate(record.model_dump(mode="python"))
        saved = self._upsert(
            table="memory_merge_results",
            pk="merge_id",
            columns=_MERGE_COLUMNS,
            record=record,
            extra_payload={
                "merged_source_refs_json": _json_list(record.merged_source_refs),
                "evidence_refs_json": _json_list(record.evidence_refs),
                "metadata_json": _encode_json(record.metadata),
            },
        )
        return saved if isinstance(saved, MemoryMergeResultRecord) else record

    def list_soft_rules(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        state: str | None = None,
        limit: int | None = None,
    ) -> list[MemorySoftRuleRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if state is not None:
            clauses.append("state = ?")
            params.append(state)
        return self._list(
            table="memory_soft_rules",
            clauses=clauses,
            params=params,
            order_by="CASE state WHEN 'active' THEN 0 WHEN 'promoted' THEN 1 ELSE 2 END, hit_count DESC, updated_at DESC, created_at DESC",
            limit=limit,
            parser=_soft_rule_from_row,
        )

    def upsert_soft_rule(self, record: MemorySoftRuleRecord) -> MemorySoftRuleRecord:
        record = MemorySoftRuleRecord.model_validate(record.model_dump(mode="python"))
        saved = self._upsert(
            table="memory_soft_rules",
            pk="rule_id",
            columns=_SOFT_RULE_COLUMNS,
            record=record,
            extra_payload={
                "evidence_refs_json": _json_list(record.evidence_refs),
                "metadata_json": _encode_json(record.metadata),
            },
        )
        return saved if isinstance(saved, MemorySoftRuleRecord) else record

    def list_conflict_proposals(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryConflictProposalRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        return self._list(
            table="memory_conflict_proposals",
            clauses=clauses,
            params=params,
            order_by="CASE status WHEN 'pending' THEN 0 ELSE 1 END, updated_at DESC, created_at DESC",
            limit=limit,
            parser=_conflict_from_row,
        )

    def upsert_conflict_proposal(
        self,
        record: MemoryConflictProposalRecord,
    ) -> MemoryConflictProposalRecord:
        record = MemoryConflictProposalRecord.model_validate(record.model_dump(mode="python"))
        saved = self._upsert(
            table="memory_conflict_proposals",
            pk="proposal_id",
            columns=_CONFLICT_COLUMNS,
            record=record,
            extra_payload={
                "conflicting_refs_json": _json_list(record.conflicting_refs),
                "supporting_refs_json": _json_list(record.supporting_refs),
                "metadata_json": _encode_json(record.metadata),
            },
        )
        return saved if isinstance(saved, MemoryConflictProposalRecord) else record

    def get_active_industry_profile(
        self,
        industry_instance_id: str,
    ) -> IndustryMemoryProfileRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM memory_industry_profiles
                WHERE industry_instance_id = ? AND status = 'active'
                ORDER BY version DESC, updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (industry_instance_id,),
            ).fetchone()
        return _industry_profile_from_row(row)

    def list_industry_profiles(
        self,
        *,
        industry_instance_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[IndustryMemoryProfileRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        return self._list(
            table="memory_industry_profiles",
            clauses=clauses,
            params=params,
            order_by="CASE status WHEN 'active' THEN 0 ELSE 1 END, version DESC, updated_at DESC, created_at DESC",
            limit=limit,
            parser=_industry_profile_from_row,
        )

    def upsert_industry_profile(
        self,
        record: IndustryMemoryProfileRecord,
    ) -> IndustryMemoryProfileRecord:
        record = IndustryMemoryProfileRecord.model_validate(record.model_dump(mode="python"))

        def _supersede(conn: sqlite3.Connection, payload: dict[str, Any], current: BaseModel) -> None:
            if not isinstance(current, IndustryMemoryProfileRecord) or current.status != "active":
                return
            conn.execute(
                """
                UPDATE memory_industry_profiles
                SET status = 'superseded',
                    updated_at = ?
                WHERE industry_instance_id = ?
                  AND profile_id != ?
                  AND status = 'active'
                """,
                (payload["updated_at"], current.industry_instance_id, current.profile_id),
            )

        saved = self._upsert(
            table="memory_industry_profiles",
            pk="profile_id",
            columns=_INDUSTRY_PROFILE_COLUMNS,
            record=record,
            extra_payload={
                "active_constraints_json": _json_list(record.active_constraints),
                "active_focuses_json": _json_list(record.active_focuses),
                "key_entities_json": _json_list(record.key_entities),
                "key_relations_json": _json_list(record.key_relations),
                "evidence_refs_json": _json_list(record.evidence_refs),
                "metadata_json": _encode_json(record.metadata),
            },
            before_write=_supersede,
        )
        return saved if isinstance(saved, IndustryMemoryProfileRecord) else record

    def get_active_work_context_overlay(
        self,
        work_context_id: str,
    ) -> WorkContextMemoryOverlayRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM memory_work_context_overlays
                WHERE work_context_id = ? AND status = 'active'
                ORDER BY version DESC, updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (work_context_id,),
            ).fetchone()
        return _work_context_overlay_from_row(row)

    def list_work_context_overlays(
        self,
        *,
        work_context_id: str | None = None,
        industry_instance_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[WorkContextMemoryOverlayRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if work_context_id is not None:
            clauses.append("work_context_id = ?")
            params.append(work_context_id)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        return self._list(
            table="memory_work_context_overlays",
            clauses=clauses,
            params=params,
            order_by="CASE status WHEN 'active' THEN 0 ELSE 1 END, version DESC, updated_at DESC, created_at DESC",
            limit=limit,
            parser=_work_context_overlay_from_row,
        )

    def upsert_work_context_overlay(
        self,
        record: WorkContextMemoryOverlayRecord,
    ) -> WorkContextMemoryOverlayRecord:
        record = WorkContextMemoryOverlayRecord.model_validate(record.model_dump(mode="python"))

        def _supersede(conn: sqlite3.Connection, payload: dict[str, Any], current: BaseModel) -> None:
            if not isinstance(current, WorkContextMemoryOverlayRecord) or current.status != "active":
                return
            conn.execute(
                """
                UPDATE memory_work_context_overlays
                SET status = 'superseded',
                    updated_at = ?
                WHERE work_context_id = ?
                  AND overlay_id != ?
                  AND status = 'active'
                """,
                (payload["updated_at"], current.work_context_id, current.overlay_id),
            )

        saved = self._upsert(
            table="memory_work_context_overlays",
            pk="overlay_id",
            columns=_WORK_CONTEXT_OVERLAY_COLUMNS,
            record=record,
            extra_payload={
                "active_constraints_json": _json_list(record.active_constraints),
                "active_focuses_json": _json_list(record.active_focuses),
                "active_entities_json": _json_list(record.active_entities),
                "active_relations_json": _json_list(record.active_relations),
                "evidence_refs_json": _json_list(record.evidence_refs),
                "metadata_json": _encode_json(record.metadata),
            },
            before_write=_supersede,
        )
        return saved if isinstance(saved, WorkContextMemoryOverlayRecord) else record

    def list_structure_proposals(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryStructureProposalRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if scope_type is not None:
            clauses.append("scope_type = ?")
            params.append(scope_type)
        if scope_id is not None:
            clauses.append("scope_id = ?")
            params.append(scope_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        return self._list(
            table="memory_structure_proposals",
            clauses=clauses,
            params=params,
            order_by="CASE status WHEN 'pending' THEN 0 ELSE 1 END, updated_at DESC, created_at DESC",
            limit=limit,
            parser=_structure_proposal_from_row,
        )

    def upsert_structure_proposal(
        self,
        record: MemoryStructureProposalRecord,
    ) -> MemoryStructureProposalRecord:
        record = MemoryStructureProposalRecord.model_validate(record.model_dump(mode="python"))
        saved = self._upsert(
            table="memory_structure_proposals",
            pk="proposal_id",
            columns=_STRUCTURE_PROPOSAL_COLUMNS,
            record=record,
            extra_payload={
                "evidence_refs_json": _json_list(record.evidence_refs),
                "metadata_json": _encode_json(record.metadata),
            },
        )
        return saved if isinstance(saved, MemoryStructureProposalRecord) else record
