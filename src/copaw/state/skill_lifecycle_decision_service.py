# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any

from .models_capability_evolution import SkillLifecycleDecisionRecord
from .store import SQLiteStateStore


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_load_list(value: object | None) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item).strip() for item in payload if str(item).strip()]


def _json_load_dict(value: object | None) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class SkillLifecycleDecisionService:
    def __init__(self, *, state_store: SQLiteStateStore) -> None:
        self._state_store = state_store
        self._state_store.initialize()

    def create_decision(
        self,
        *,
        candidate_id: str,
        decision_kind: str,
        from_stage: str | None = None,
        to_stage: str | None = None,
        reason: str = "",
        evidence_refs: list[str] | None = None,
        replacement_target_ids: list[str] | None = None,
        protection_lifted: bool = False,
        applied_by: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SkillLifecycleDecisionRecord:
        record = SkillLifecycleDecisionRecord(
            candidate_id=candidate_id,
            decision_kind=_string(decision_kind) or "continue_trial",
            from_stage=_string(from_stage),
            to_stage=_string(to_stage),
            reason=str(reason or ""),
            evidence_refs=list(evidence_refs or []),
            replacement_target_ids=list(replacement_target_ids or []),
            protection_lifted=bool(protection_lifted),
            applied_by=_string(applied_by),
            metadata=dict(metadata or {}),
        )
        self._upsert_record(record)
        return record

    def list_decisions(
        self,
        *,
        candidate_id: str | None = None,
        limit: int | None = None,
    ) -> list[SkillLifecycleDecisionRecord]:
        query = """
            SELECT *
            FROM skill_lifecycle_decisions
        """
        clauses: list[str] = []
        params: list[object] = []
        if _string(candidate_id) is not None:
            clauses.append("candidate_id = ?")
            params.append(candidate_id)
        if clauses:
            query += "\nWHERE " + " AND ".join(clauses)
        query += "\nORDER BY updated_at DESC, decision_id DESC"
        if isinstance(limit, int) and limit > 0:
            query += "\nLIMIT ?"
            params.append(limit)
        with self._state_store.connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _upsert_record(self, record: SkillLifecycleDecisionRecord) -> None:
        with self._state_store.connection() as conn:
            conn.execute(
                """
                INSERT INTO skill_lifecycle_decisions (
                    decision_id,
                    candidate_id,
                    decision_kind,
                    from_stage,
                    to_stage,
                    reason,
                    evidence_refs_json,
                    replacement_target_ids_json,
                    protection_lifted,
                    applied_by,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :decision_id,
                    :candidate_id,
                    :decision_kind,
                    :from_stage,
                    :to_stage,
                    :reason,
                    :evidence_refs_json,
                    :replacement_target_ids_json,
                    :protection_lifted,
                    :applied_by,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(decision_id) DO UPDATE SET
                    decision_kind = excluded.decision_kind,
                    from_stage = excluded.from_stage,
                    to_stage = excluded.to_stage,
                    reason = excluded.reason,
                    evidence_refs_json = excluded.evidence_refs_json,
                    replacement_target_ids_json = excluded.replacement_target_ids_json,
                    protection_lifted = excluded.protection_lifted,
                    applied_by = excluded.applied_by,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                {
                    "decision_id": record.decision_id,
                    "candidate_id": record.candidate_id,
                    "decision_kind": record.decision_kind,
                    "from_stage": record.from_stage,
                    "to_stage": record.to_stage,
                    "reason": record.reason,
                    "evidence_refs_json": _json_dumps(record.evidence_refs),
                    "replacement_target_ids_json": _json_dumps(record.replacement_target_ids),
                    "protection_lifted": 1 if record.protection_lifted else 0,
                    "applied_by": record.applied_by,
                    "metadata_json": _json_dumps(record.metadata),
                    "created_at": record.created_at.isoformat(),
                    "updated_at": record.updated_at.isoformat(),
                },
            )

    def _row_to_record(self, row) -> SkillLifecycleDecisionRecord:
        return SkillLifecycleDecisionRecord(
            decision_id=row["decision_id"],
            candidate_id=row["candidate_id"],
            decision_kind=row["decision_kind"],
            from_stage=row["from_stage"],
            to_stage=row["to_stage"],
            reason=row["reason"] or "",
            evidence_refs=_json_load_list(row["evidence_refs_json"]),
            replacement_target_ids=_json_load_list(row["replacement_target_ids_json"]),
            protection_lifted=bool(row["protection_lifted"]),
            applied_by=row["applied_by"],
            metadata=_json_load_dict(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
