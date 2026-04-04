# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any

from .models_capability_evolution import SkillTrialRecord
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


def _float_value(value: object | None) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _string(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class SkillTrialService:
    def __init__(self, *, state_store: SQLiteStateStore) -> None:
        self._state_store = state_store
        self._state_store.initialize()

    def create_or_update_trial(
        self,
        *,
        candidate_id: str,
        donor_id: str | None = None,
        package_id: str | None = None,
        source_profile_id: str | None = None,
        canonical_package_id: str | None = None,
        candidate_source_lineage: str | None = None,
        source_aliases: list[str] | None = None,
        equivalence_class: str | None = None,
        capability_overlap_score: float | None = None,
        replacement_relation: str | None = None,
        scope_type: str,
        scope_ref: str,
        verdict: str = "pending",
        summary: str = "",
        task_ids: list[str] | None = None,
        evidence_refs: list[str] | None = None,
        success_count: int = 0,
        failure_count: int = 0,
        handoff_count: int = 0,
        operator_intervention_count: int = 0,
        latency_summary: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SkillTrialRecord:
        existing = self.get_trial(candidate_id=candidate_id, scope_type=scope_type, scope_ref=scope_ref)
        record = (
            existing.model_copy(
                update={
                    "donor_id": _string(donor_id) or existing.donor_id,
                    "package_id": _string(package_id) or existing.package_id,
                    "source_profile_id": _string(source_profile_id) or existing.source_profile_id,
                    "canonical_package_id": _string(canonical_package_id)
                    or existing.canonical_package_id,
                    "candidate_source_lineage": _string(candidate_source_lineage)
                    or existing.candidate_source_lineage,
                    "source_aliases": list(source_aliases or existing.source_aliases),
                    "equivalence_class": _string(equivalence_class) or existing.equivalence_class,
                    "capability_overlap_score": (
                        _float_value(capability_overlap_score)
                        if _float_value(capability_overlap_score) is not None
                        else existing.capability_overlap_score
                    ),
                    "replacement_relation": _string(replacement_relation)
                    or existing.replacement_relation,
                    "verdict": _string(verdict) or "pending",
                    "summary": str(summary or ""),
                    "task_ids": list(task_ids or []),
                    "evidence_refs": list(evidence_refs or []),
                    "success_count": max(0, int(success_count)),
                    "failure_count": max(0, int(failure_count)),
                    "handoff_count": max(0, int(handoff_count)),
                    "operator_intervention_count": max(0, int(operator_intervention_count)),
                    "latency_summary": dict(latency_summary or {}),
                    "metadata": dict(metadata or {}),
                },
            )
            if existing is not None
            else SkillTrialRecord(
                candidate_id=candidate_id,
                donor_id=_string(donor_id),
                package_id=_string(package_id),
                source_profile_id=_string(source_profile_id),
                canonical_package_id=_string(canonical_package_id),
                candidate_source_lineage=_string(candidate_source_lineage),
                source_aliases=list(source_aliases or []),
                equivalence_class=_string(equivalence_class),
                capability_overlap_score=_float_value(capability_overlap_score),
                replacement_relation=_string(replacement_relation),
                scope_type=_string(scope_type) or "seat",
                scope_ref=_string(scope_ref) or "unknown",
                verdict=_string(verdict) or "pending",
                summary=str(summary or ""),
                task_ids=list(task_ids or []),
                evidence_refs=list(evidence_refs or []),
                success_count=max(0, int(success_count)),
                failure_count=max(0, int(failure_count)),
                handoff_count=max(0, int(handoff_count)),
                operator_intervention_count=max(0, int(operator_intervention_count)),
                latency_summary=dict(latency_summary or {}),
                metadata=dict(metadata or {}),
            )
        )
        self._upsert_record(record)
        return record

    def get_trial(
        self,
        *,
        candidate_id: str,
        scope_type: str,
        scope_ref: str,
    ) -> SkillTrialRecord | None:
        with self._state_store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM skill_trials
                WHERE candidate_id = ?
                  AND scope_type = ?
                  AND scope_ref = ?
                ORDER BY updated_at DESC, trial_id DESC
                LIMIT 1
                """,
                (candidate_id, scope_type, scope_ref),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def list_trials(
        self,
        *,
        candidate_id: str | None = None,
        limit: int | None = None,
    ) -> list[SkillTrialRecord]:
        query = """
            SELECT *
            FROM skill_trials
        """
        clauses: list[str] = []
        params: list[object] = []
        if _string(candidate_id) is not None:
            clauses.append("candidate_id = ?")
            params.append(candidate_id)
        if clauses:
            query += "\nWHERE " + " AND ".join(clauses)
        query += "\nORDER BY updated_at DESC, trial_id DESC"
        if isinstance(limit, int) and limit > 0:
            query += "\nLIMIT ?"
            params.append(limit)
        with self._state_store.connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_record(row) for row in rows]

    def summarize_trials(self, *, candidate_id: str) -> dict[str, object]:
        items = self.list_trials(candidate_id=candidate_id)
        verdicts: dict[str, int] = {}
        scope_refs: list[str] = []
        for item in items:
            verdicts[item.verdict] = verdicts.get(item.verdict, 0) + 1
            if item.scope_ref not in scope_refs:
                scope_refs.append(item.scope_ref)
        return {
            "candidate_id": candidate_id,
            "trial_count": len(items),
            "success_count": sum(item.success_count for item in items),
            "failure_count": sum(item.failure_count for item in items),
            "handoff_count": sum(item.handoff_count for item in items),
            "operator_intervention_count": sum(
                item.operator_intervention_count for item in items
            ),
            "verdicts": verdicts,
            "scope_refs": scope_refs,
        }

    def get_candidate_verdict_summary(self, *, candidate_id: str) -> dict[str, object]:
        items = self.list_trials(candidate_id=candidate_id)
        scope_verdicts = {
            item.scope_ref: item.verdict
            for item in items
            if _string(item.scope_ref) is not None
        }
        aggregate_verdict = "no-trials"
        if items:
            if any(
                item.verdict == "failed" or item.failure_count > item.success_count
                for item in items
            ):
                aggregate_verdict = "rollback_recommended"
            elif any(item.operator_intervention_count > 0 or item.handoff_count > 0 for item in items):
                aggregate_verdict = "continue_trial"
            elif all(item.verdict == "passed" for item in items):
                aggregate_verdict = "passed"
            else:
                aggregate_verdict = "mixed"
        return {
            **self.summarize_trials(candidate_id=candidate_id),
            "aggregate_verdict": aggregate_verdict,
            "scope_verdicts": scope_verdicts,
        }

    def _upsert_record(self, record: SkillTrialRecord) -> None:
        with self._state_store.connection() as conn:
            conn.execute(
                """
                INSERT INTO skill_trials (
                    trial_id,
                    candidate_id,
                    donor_id,
                    package_id,
                    source_profile_id,
                    canonical_package_id,
                    candidate_source_lineage,
                    source_aliases_json,
                    equivalence_class,
                    capability_overlap_score,
                    replacement_relation,
                    scope_type,
                    scope_ref,
                    verdict,
                    summary,
                    task_ids_json,
                    evidence_refs_json,
                    success_count,
                    failure_count,
                    handoff_count,
                    operator_intervention_count,
                    latency_summary_json,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :trial_id,
                    :candidate_id,
                    :donor_id,
                    :package_id,
                    :source_profile_id,
                    :canonical_package_id,
                    :candidate_source_lineage,
                    :source_aliases_json,
                    :equivalence_class,
                    :capability_overlap_score,
                    :replacement_relation,
                    :scope_type,
                    :scope_ref,
                    :verdict,
                    :summary,
                    :task_ids_json,
                    :evidence_refs_json,
                    :success_count,
                    :failure_count,
                    :handoff_count,
                    :operator_intervention_count,
                    :latency_summary_json,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(trial_id) DO UPDATE SET
                    donor_id = excluded.donor_id,
                    package_id = excluded.package_id,
                    source_profile_id = excluded.source_profile_id,
                    canonical_package_id = excluded.canonical_package_id,
                    candidate_source_lineage = excluded.candidate_source_lineage,
                    source_aliases_json = excluded.source_aliases_json,
                    equivalence_class = excluded.equivalence_class,
                    capability_overlap_score = excluded.capability_overlap_score,
                    replacement_relation = excluded.replacement_relation,
                    verdict = excluded.verdict,
                    summary = excluded.summary,
                    task_ids_json = excluded.task_ids_json,
                    evidence_refs_json = excluded.evidence_refs_json,
                    success_count = excluded.success_count,
                    failure_count = excluded.failure_count,
                    handoff_count = excluded.handoff_count,
                    operator_intervention_count = excluded.operator_intervention_count,
                    latency_summary_json = excluded.latency_summary_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                {
                    "trial_id": record.trial_id,
                    "candidate_id": record.candidate_id,
                    "donor_id": record.donor_id,
                    "package_id": record.package_id,
                    "source_profile_id": record.source_profile_id,
                    "canonical_package_id": record.canonical_package_id,
                    "candidate_source_lineage": record.candidate_source_lineage,
                    "source_aliases_json": _json_dumps(record.source_aliases),
                    "equivalence_class": record.equivalence_class,
                    "capability_overlap_score": record.capability_overlap_score,
                    "replacement_relation": record.replacement_relation,
                    "scope_type": record.scope_type,
                    "scope_ref": record.scope_ref,
                    "verdict": record.verdict,
                    "summary": record.summary,
                    "task_ids_json": _json_dumps(record.task_ids),
                    "evidence_refs_json": _json_dumps(record.evidence_refs),
                    "success_count": record.success_count,
                    "failure_count": record.failure_count,
                    "handoff_count": record.handoff_count,
                    "operator_intervention_count": record.operator_intervention_count,
                    "latency_summary_json": _json_dumps(record.latency_summary),
                    "metadata_json": _json_dumps(record.metadata),
                    "created_at": record.created_at.isoformat(),
                    "updated_at": record.updated_at.isoformat(),
                },
            )

    def _row_to_record(self, row) -> SkillTrialRecord:
        return SkillTrialRecord(
            trial_id=row["trial_id"],
            candidate_id=row["candidate_id"],
            donor_id=row["donor_id"],
            package_id=row["package_id"],
            source_profile_id=row["source_profile_id"],
            canonical_package_id=row["canonical_package_id"],
            candidate_source_lineage=row["candidate_source_lineage"],
            source_aliases=_json_load_list(row["source_aliases_json"]),
            equivalence_class=row["equivalence_class"],
            capability_overlap_score=_float_value(row["capability_overlap_score"]),
            replacement_relation=row["replacement_relation"],
            scope_type=row["scope_type"],
            scope_ref=row["scope_ref"],
            verdict=row["verdict"],
            summary=row["summary"] or "",
            task_ids=_json_load_list(row["task_ids_json"]),
            evidence_refs=_json_load_list(row["evidence_refs_json"]),
            success_count=int(row["success_count"] or 0),
            failure_count=int(row["failure_count"] or 0),
            handoff_count=int(row["handoff_count"] or 0),
            operator_intervention_count=int(row["operator_intervention_count"] or 0),
            latency_summary=_json_load_dict(row["latency_summary_json"]),
            metadata=_json_load_dict(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
