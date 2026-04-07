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


def _verified_stage(value: object | None, default: str) -> str:
    from ..capabilities.external_adapter_contracts import normalize_verified_stage

    return normalize_verified_stage(value) or default


def _provider_resolution_status(value: object | None, default: str) -> str:
    from ..capabilities.external_adapter_contracts import (
        normalize_provider_resolution_status,
    )

    return normalize_provider_resolution_status(value) or default


def _compatibility_status(value: object | None, default: str) -> str:
    from ..capabilities.external_adapter_contracts import normalize_compatibility_status

    return normalize_compatibility_status(value) or default


def _merge_adapter_metadata(*payloads: object) -> dict[str, Any]:
    from ..capabilities.external_adapter_contracts import (
        merge_adapter_attribution_metadata,
    )

    return merge_adapter_attribution_metadata(*payloads)


class SkillLifecycleDecisionService:
    def __init__(self, *, state_store: SQLiteStateStore) -> None:
        self._state_store = state_store
        self._state_store.initialize()

    def create_decision(
        self,
        *,
        decision_id: str | None = None,
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
        decision_kind: str,
        from_stage: str | None = None,
        to_stage: str | None = None,
        reason: str = "",
        evidence_refs: list[str] | None = None,
        retirement_reason: str | None = None,
        retirement_scope: str | None = None,
        retirement_evidence_refs: list[str] | None = None,
        replacement_target_ids: list[str] | None = None,
        protection_lifted: bool = False,
        applied_by: str | None = None,
        verified_stage: str | None = None,
        provider_resolution_status: str | None = None,
        compatibility_status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SkillLifecycleDecisionRecord:
        metadata_payload = _merge_adapter_metadata(metadata or {})
        payload = {
            "candidate_id": candidate_id,
            "donor_id": _string(donor_id),
            "package_id": _string(package_id),
            "source_profile_id": _string(source_profile_id),
            "canonical_package_id": _string(canonical_package_id),
            "candidate_source_lineage": _string(candidate_source_lineage),
            "source_aliases": list(source_aliases or []),
            "equivalence_class": _string(equivalence_class),
            "capability_overlap_score": _float_value(capability_overlap_score),
            "replacement_relation": _string(replacement_relation),
            "decision_kind": _string(decision_kind) or "continue_trial",
            "from_stage": _string(from_stage),
            "to_stage": _string(to_stage),
            "reason": str(reason or ""),
            "retirement_reason": _string(retirement_reason),
            "retirement_scope": _string(retirement_scope),
            "evidence_refs": list(evidence_refs or []),
            "retirement_evidence_refs": list(retirement_evidence_refs or []),
            "replacement_target_ids": list(replacement_target_ids or []),
            "protection_lifted": bool(protection_lifted),
            "applied_by": _string(applied_by),
            "verified_stage": _verified_stage(
                verified_stage
                if verified_stage is not None
                else metadata_payload.get("verified_stage"),
                "unverified",
            ),
            "provider_resolution_status": _provider_resolution_status(
                provider_resolution_status
                if provider_resolution_status is not None
                else metadata_payload.get("provider_resolution_status"),
                "pending",
            ),
            "compatibility_status": _compatibility_status(
                compatibility_status
                if compatibility_status is not None
                else metadata_payload.get("compatibility_status"),
                "unknown",
            ),
            "metadata": metadata_payload,
        }
        normalized_decision_id = _string(decision_id)
        if normalized_decision_id is not None:
            payload["decision_id"] = normalized_decision_id
        record = SkillLifecycleDecisionRecord(**payload)
        self._upsert_record(record)
        return record

    def upsert_evaluator_verdict_decision(
        self,
        *,
        candidate_id: str,
        aggregate_verdict: str,
        source_recommendation_id: str | None = None,
        donor_id: str | None = None,
        package_id: str | None = None,
        source_profile_id: str | None = None,
        canonical_package_id: str | None = None,
        candidate_source_lineage: str | None = None,
        source_aliases: list[str] | None = None,
        equivalence_class: str | None = None,
        capability_overlap_score: float | None = None,
        replacement_relation: str | None = None,
        from_stage: str | None = None,
        reason: str = "",
        evidence_refs: list[str] | None = None,
        replacement_target_ids: list[str] | None = None,
        applied_by: str | None = None,
        verified_stage: str | None = None,
        provider_resolution_status: str | None = None,
        compatibility_status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SkillLifecycleDecisionRecord:
        normalized_verdict = _string(aggregate_verdict) or "no-trials"
        normalized_source_recommendation_id = _string(source_recommendation_id)
        existing: SkillLifecycleDecisionRecord | None = None
        if normalized_source_recommendation_id is not None:
            for item in self.list_decisions(candidate_id=candidate_id, limit=100):
                item_metadata = dict(item.metadata or {})
                if (
                    _string(item_metadata.get("verdict_source")) == "trial_evaluator"
                    and _string(item_metadata.get("source_recommendation_id"))
                    == normalized_source_recommendation_id
                ):
                    existing = item
                    break

        mapped_from_stage = _string(from_stage) or "candidate"
        mapped_decision_kind = "continue_trial"
        mapped_to_stage = "trial"
        if normalized_verdict == "rollback_recommended":
            mapped_decision_kind = "rollback"
            mapped_from_stage = "trial"
            mapped_to_stage = "blocked"
        elif mapped_from_stage not in {"candidate", "trial"}:
            mapped_from_stage = "trial"

        existing_metadata = dict(existing.metadata or {}) if existing is not None else {}
        metadata_payload = _merge_adapter_metadata(
            existing_metadata,
            metadata or {},
            {
                "source_recommendation_id": normalized_source_recommendation_id,
                "evaluator_verdict": normalized_verdict,
                "verdict_source": "trial_evaluator",
            },
        )
        return self.create_decision(
            decision_id=existing.decision_id if existing is not None else None,
            candidate_id=candidate_id,
            donor_id=_string(donor_id) or getattr(existing, "donor_id", None),
            package_id=_string(package_id) or getattr(existing, "package_id", None),
            source_profile_id=_string(source_profile_id)
            or getattr(existing, "source_profile_id", None),
            canonical_package_id=_string(canonical_package_id)
            or getattr(existing, "canonical_package_id", None),
            candidate_source_lineage=_string(candidate_source_lineage)
            or getattr(existing, "candidate_source_lineage", None),
            source_aliases=list(source_aliases or getattr(existing, "source_aliases", []) or []),
            equivalence_class=_string(equivalence_class)
            or getattr(existing, "equivalence_class", None),
            capability_overlap_score=(
                _float_value(capability_overlap_score)
                if _float_value(capability_overlap_score) is not None
                else getattr(existing, "capability_overlap_score", None)
            ),
            replacement_relation=_string(replacement_relation)
            or getattr(existing, "replacement_relation", None),
            decision_kind=mapped_decision_kind,
            from_stage=mapped_from_stage,
            to_stage=mapped_to_stage,
            reason=reason or getattr(existing, "reason", "") or normalized_verdict,
            evidence_refs=list(
                evidence_refs
                or getattr(existing, "evidence_refs", [])
                or []
            ),
            replacement_target_ids=list(
                replacement_target_ids
                or getattr(existing, "replacement_target_ids", [])
                or []
            ),
            applied_by=_string(applied_by) or getattr(existing, "applied_by", None),
            verified_stage=verified_stage or getattr(existing, "verified_stage", None),
            provider_resolution_status=provider_resolution_status
            or getattr(existing, "provider_resolution_status", None),
            compatibility_status=compatibility_status
            or getattr(existing, "compatibility_status", None),
            metadata=metadata_payload,
        )

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
                    donor_id,
                    package_id,
                    source_profile_id,
                    canonical_package_id,
                    candidate_source_lineage,
                    source_aliases_json,
                    equivalence_class,
                    capability_overlap_score,
                    replacement_relation,
                    decision_kind,
                    from_stage,
                    to_stage,
                    reason,
                    retirement_reason,
                    retirement_scope,
                    evidence_refs_json,
                    retirement_evidence_refs_json,
                    replacement_target_ids_json,
                    protection_lifted,
                    applied_by,
                    verified_stage,
                    provider_resolution_status,
                    compatibility_status,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :decision_id,
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
                    :decision_kind,
                    :from_stage,
                    :to_stage,
                    :reason,
                    :retirement_reason,
                    :retirement_scope,
                    :evidence_refs_json,
                    :retirement_evidence_refs_json,
                    :replacement_target_ids_json,
                    :protection_lifted,
                    :applied_by,
                    :verified_stage,
                    :provider_resolution_status,
                    :compatibility_status,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(decision_id) DO UPDATE SET
                    donor_id = excluded.donor_id,
                    package_id = excluded.package_id,
                    source_profile_id = excluded.source_profile_id,
                    canonical_package_id = excluded.canonical_package_id,
                    candidate_source_lineage = excluded.candidate_source_lineage,
                    source_aliases_json = excluded.source_aliases_json,
                    equivalence_class = excluded.equivalence_class,
                    capability_overlap_score = excluded.capability_overlap_score,
                    replacement_relation = excluded.replacement_relation,
                    decision_kind = excluded.decision_kind,
                    from_stage = excluded.from_stage,
                    to_stage = excluded.to_stage,
                    reason = excluded.reason,
                    retirement_reason = excluded.retirement_reason,
                    retirement_scope = excluded.retirement_scope,
                    evidence_refs_json = excluded.evidence_refs_json,
                    retirement_evidence_refs_json = excluded.retirement_evidence_refs_json,
                    replacement_target_ids_json = excluded.replacement_target_ids_json,
                    protection_lifted = excluded.protection_lifted,
                    applied_by = excluded.applied_by,
                    verified_stage = excluded.verified_stage,
                    provider_resolution_status = excluded.provider_resolution_status,
                    compatibility_status = excluded.compatibility_status,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                {
                    "decision_id": record.decision_id,
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
                    "decision_kind": record.decision_kind,
                    "from_stage": record.from_stage,
                    "to_stage": record.to_stage,
                    "reason": record.reason,
                    "retirement_reason": record.retirement_reason,
                    "retirement_scope": record.retirement_scope,
                    "evidence_refs_json": _json_dumps(record.evidence_refs),
                    "retirement_evidence_refs_json": _json_dumps(
                        record.retirement_evidence_refs,
                    ),
                    "replacement_target_ids_json": _json_dumps(record.replacement_target_ids),
                    "protection_lifted": 1 if record.protection_lifted else 0,
                    "applied_by": record.applied_by,
                    "verified_stage": record.verified_stage,
                    "provider_resolution_status": record.provider_resolution_status,
                    "compatibility_status": record.compatibility_status,
                    "metadata_json": _json_dumps(record.metadata),
                    "created_at": record.created_at.isoformat(),
                    "updated_at": record.updated_at.isoformat(),
                },
            )

    def _row_to_record(self, row) -> SkillLifecycleDecisionRecord:
        return SkillLifecycleDecisionRecord(
            decision_id=row["decision_id"],
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
            decision_kind=row["decision_kind"],
            from_stage=row["from_stage"],
            to_stage=row["to_stage"],
            reason=row["reason"] or "",
            retirement_reason=row["retirement_reason"],
            retirement_scope=row["retirement_scope"],
            evidence_refs=_json_load_list(row["evidence_refs_json"]),
            retirement_evidence_refs=_json_load_list(row["retirement_evidence_refs_json"]),
            replacement_target_ids=_json_load_list(row["replacement_target_ids_json"]),
            protection_lifted=bool(row["protection_lifted"]),
            applied_by=row["applied_by"],
            verified_stage=row["verified_stage"],
            provider_resolution_status=row["provider_resolution_status"],
            compatibility_status=row["compatibility_status"],
            metadata=_json_load_dict(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
