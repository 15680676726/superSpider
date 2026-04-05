# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Iterable

from ..discovery.deduplication import normalize_discovery_hits
from ..discovery.models import DiscoveryHit, NormalizedDiscoveryHit
from .models_capability_evolution import CapabilityCandidateRecord
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


def _string_list(*values: object) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        items = value if isinstance(value, (list, tuple, set)) else [value]
        for item in items:
            text = _string(item)
            if text is None:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(text)
    return normalized


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


def _merge_metadata(
    current: dict[str, Any] | None,
    updates: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(current or {})
    merged.update(dict(updates or {}))
    return merged


def _mount_source_kind(mount: object) -> str:
    source_kind = _string(getattr(mount, "source_kind", None))
    if source_kind == "mcp":
        return "external_catalog"
    if source_kind == "skill":
        return "external_remote"
    return "external_catalog"


def _mount_candidate_kind(mount: object) -> str:
    source_kind = _string(getattr(mount, "source_kind", None))
    kind = _string(getattr(mount, "kind", None))
    if source_kind == "mcp" or kind == "remote-mcp":
        return "mcp-bundle"
    return "skill"


def _mount_protection_flags(mount: object) -> list[str]:
    metadata = getattr(mount, "metadata", None)
    if not isinstance(metadata, dict):
        return []
    return sorted(
        key
        for key, value in metadata.items()
        if bool(value) and key in {"protected_from_auto_replace", "required_by_role_blueprint"}
    )


class CapabilityCandidateService:
    def __init__(
        self,
        *,
        state_store: SQLiteStateStore,
        donor_service: object | None = None,
    ) -> None:
        self._state_store = state_store
        self._donor_service = donor_service
        self._state_store.initialize()

    def list_candidates(
        self,
        *,
        limit: int | None = None,
    ) -> list[CapabilityCandidateRecord]:
        with self._state_store.connection() as conn:
            query = """
                SELECT *
                FROM capability_candidates
                ORDER BY updated_at DESC, candidate_id DESC
            """
            params: tuple[object, ...] = ()
            if isinstance(limit, int) and limit > 0:
                query += "\nLIMIT ?"
                params = (limit,)
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_candidate(self, candidate_id: str) -> CapabilityCandidateRecord | None:
        candidate_id = _string(candidate_id)
        if candidate_id is None:
            return None
        with self._state_store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM capability_candidates
                WHERE candidate_id = ?
                LIMIT 1
                """,
                (candidate_id,),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def update_candidate_status(
        self,
        candidate_id: str,
        *,
        status: str | None = None,
        lifecycle_stage: str | None = None,
        metadata_updates: dict[str, Any] | None = None,
    ) -> CapabilityCandidateRecord | None:
        record = self.get_candidate(candidate_id)
        if record is None:
            return None
        updated = record.model_copy(
            update={
                "status": _string(status) or record.status,
                "lifecycle_stage": _string(lifecycle_stage) or record.lifecycle_stage,
                "metadata": _merge_metadata(record.metadata, metadata_updates or {}),
            },
        )
        self._upsert_record(updated)
        return updated

    def summarize_candidates(self) -> dict[str, object]:
        items = self.list_candidates()
        by_kind: dict[str, int] = {}
        by_source_kind: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for item in items:
            by_kind[item.candidate_kind] = by_kind.get(item.candidate_kind, 0) + 1
            by_source_kind[item.candidate_source_kind] = (
                by_source_kind.get(item.candidate_source_kind, 0) + 1
            )
            by_status[item.lifecycle_stage] = by_status.get(item.lifecycle_stage, 0) + 1
        return {
            "total": len(items),
            "by_kind": by_kind,
            "by_source_kind": by_source_kind,
            "by_status": by_status,
        }

    def normalize_candidate_source(
        self,
        *,
        candidate_kind: str,
        target_scope: str,
        target_role_id: str | None,
        target_seat_ref: str | None,
        candidate_source_kind: str,
        candidate_source_ref: str | None,
        candidate_source_version: str | None,
        candidate_source_lineage: str | None = None,
        ingestion_mode: str,
        proposed_skill_name: str | None = None,
        summary: str = "",
        industry_instance_id: str | None = None,
        status: str = "candidate",
        lifecycle_stage: str = "candidate",
        protection_flags: Iterable[str] | None = None,
        lineage_root_id: str | None = None,
        canonical_package_id: str | None = None,
        source_aliases: Iterable[str] | None = None,
        equivalence_class: str | None = None,
        capability_overlap_score: float | None = None,
        replacement_relation: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CapabilityCandidateRecord:
        metadata_payload = dict(metadata or {})
        record = CapabilityCandidateRecord(
            donor_id=None,
            package_id=None,
            source_profile_id=None,
            canonical_package_id=(
                _string(canonical_package_id)
                or _string(metadata_payload.get("canonical_package_id"))
            ),
            candidate_kind=_string(candidate_kind) or "skill",
            target_scope=_string(target_scope) or "seat",
            target_role_id=_string(target_role_id),
            target_seat_ref=_string(target_seat_ref),
            industry_instance_id=_string(industry_instance_id),
            candidate_source_kind=_string(candidate_source_kind) or "local_authored",
            candidate_source_ref=_string(candidate_source_ref),
            candidate_source_version=_string(candidate_source_version),
            candidate_source_lineage=_string(candidate_source_lineage),
            source_aliases=_string_list(
                list(source_aliases or []),
                metadata_payload.get("source_aliases"),
            ),
            equivalence_class=(
                _string(equivalence_class)
                or _string(metadata_payload.get("equivalence_class"))
            ),
            capability_overlap_score=(
                _float_value(capability_overlap_score)
                if _float_value(capability_overlap_score) is not None
                else _float_value(metadata_payload.get("capability_overlap_score"))
            ),
            replacement_relation=(
                _string(replacement_relation)
                or _string(metadata_payload.get("replacement_relation"))
            ),
            ingestion_mode=_string(ingestion_mode) or "manual",
            proposed_skill_name=_string(proposed_skill_name),
            summary=str(summary or ""),
            status=_string(status) or "candidate",
            lifecycle_stage=_string(lifecycle_stage) or "candidate",
            protection_flags=sorted(
                {
                    str(item).strip()
                    for item in list(protection_flags or [])
                    if str(item).strip()
                }
            ),
            metadata=metadata_payload,
        )
        record.lineage_root_id = _string(lineage_root_id) or record.candidate_id
        register_candidate_source = getattr(
            self._donor_service,
            "register_candidate_source",
            None,
        )
        if callable(register_candidate_source):
            donor_id, package_id, source_profile_id = register_candidate_source(record)
            donor = getattr(self._donor_service, "get_donor", lambda *_args: None)(donor_id)
            package = getattr(self._donor_service, "get_package", lambda *_args: None)(package_id)
            source_profile = getattr(
                self._donor_service,
                "get_source_profile",
                lambda *_args: None,
            )(source_profile_id)
            record = record.model_copy(
                update={
                    "donor_id": donor_id,
                    "package_id": package_id,
                    "source_profile_id": source_profile_id,
                    "canonical_package_id": (
                        _string(getattr(package, "canonical_package_id", None))
                        or _string(getattr(donor, "canonical_package_id", None))
                        or record.canonical_package_id
                    ),
                    "source_aliases": _string_list(
                        record.source_aliases,
                        getattr(package, "source_aliases", []),
                        getattr(donor, "source_aliases", []),
                        getattr(source_profile, "source_aliases", []),
                    ),
                    "equivalence_class": (
                        _string(getattr(package, "equivalence_class", None))
                        or _string(getattr(donor, "equivalence_class", None))
                        or record.equivalence_class
                    ),
                    "replacement_relation": (
                        _string(getattr(donor, "replacement_relation", None))
                        or record.replacement_relation
                    ),
                },
            )
        self._upsert_record(record)
        return record

    def import_active_baseline_artifacts(
        self,
        *,
        mounts: Iterable[object],
        target_role_id: str | None = None,
        target_scope: str = "seat",
        target_seat_ref: str | None = None,
        industry_instance_id: str | None = None,
    ) -> list[CapabilityCandidateRecord]:
        imported: list[CapabilityCandidateRecord] = []
        for mount in mounts:
            candidate_source_kind = _mount_source_kind(mount)
            candidate_source_ref = _string(
                getattr(mount, "package_ref", None),
            ) or _string(getattr(mount, "id", None))
            candidate_source_version = _string(
                getattr(mount, "package_version", None),
            )
            existing = self._find_existing_candidate(
                candidate_source_kind=candidate_source_kind,
                candidate_source_ref=candidate_source_ref,
                candidate_source_version=candidate_source_version,
                target_role_id=target_role_id,
                target_scope=target_scope,
                target_seat_ref=target_seat_ref,
            )
            if existing is not None:
                imported.append(existing)
                continue
            imported.append(
                self.normalize_candidate_source(
                    candidate_kind=_mount_candidate_kind(mount),
                    target_scope=target_scope,
                    target_role_id=target_role_id,
                    target_seat_ref=target_seat_ref,
                    candidate_source_kind=candidate_source_kind,
                    candidate_source_ref=candidate_source_ref,
                    candidate_source_version=candidate_source_version,
                    ingestion_mode="baseline-import",
                    proposed_skill_name=(
                        _string(getattr(mount, "name", None))
                        or _string(getattr(mount, "id", None))
                    ),
                    summary=str(getattr(mount, "summary", "") or ""),
                    industry_instance_id=industry_instance_id,
                    status="active",
                    lifecycle_stage="baseline",
                    protection_flags=_mount_protection_flags(mount),
                    metadata={
                        "mount_id": _string(getattr(mount, "id", None)),
                        "package_kind": _string(getattr(mount, "package_kind", None)),
                        "source_kind": _string(getattr(mount, "source_kind", None)),
                    },
                )
            )
        return imported

    def import_discovery_hits(
        self,
        *,
        discovery_hits: Iterable[DiscoveryHit],
        target_scope: str,
        target_role_id: str | None = None,
        target_seat_ref: str | None = None,
        industry_instance_id: str | None = None,
        ingestion_mode: str = "discovery",
        status: str = "candidate",
        lifecycle_stage: str = "candidate",
    ) -> list[CapabilityCandidateRecord]:
        normalized_hits = normalize_discovery_hits(discovery_hits)
        return self.import_normalized_discovery_hits(
            normalized_hits=normalized_hits,
            target_scope=target_scope,
            target_role_id=target_role_id,
            target_seat_ref=target_seat_ref,
            industry_instance_id=industry_instance_id,
            ingestion_mode=ingestion_mode,
            status=status,
            lifecycle_stage=lifecycle_stage,
        )

    def import_normalized_discovery_hits(
        self,
        *,
        normalized_hits: Iterable[NormalizedDiscoveryHit],
        target_scope: str,
        target_role_id: str | None = None,
        target_seat_ref: str | None = None,
        industry_instance_id: str | None = None,
        ingestion_mode: str = "discovery",
        status: str = "candidate",
        lifecycle_stage: str = "candidate",
    ) -> list[CapabilityCandidateRecord]:
        imported: list[CapabilityCandidateRecord] = []
        for hit in normalized_hits:
            candidate_source_ref = (
                _string(hit.candidate_source_ref)
                or _string(hit.canonical_package_id)
                or _string(hit.display_name)
            )
            existing = self._find_existing_candidate(
                candidate_source_kind=hit.candidate_source_kind,
                candidate_source_ref=candidate_source_ref,
                candidate_source_version=hit.candidate_source_version,
                target_role_id=target_role_id,
                target_scope=target_scope,
                target_seat_ref=target_seat_ref,
            )
            if existing is None and _string(hit.candidate_source_lineage) is not None:
                existing = self._find_existing_candidate_by_lineage(
                    candidate_source_kind=hit.candidate_source_kind,
                    candidate_source_lineage=hit.candidate_source_lineage,
                    target_role_id=target_role_id,
                    target_scope=target_scope,
                    target_seat_ref=target_seat_ref,
                )
            metadata = hit.to_candidate_metadata()
            if existing is not None:
                updated = existing.model_copy(
                    update={
                        "candidate_kind": hit.candidate_kind,
                        "industry_instance_id": _string(industry_instance_id)
                        or existing.industry_instance_id,
                        "target_role_id": _string(target_role_id)
                        or existing.target_role_id,
                        "target_seat_ref": _string(target_seat_ref)
                        or existing.target_seat_ref,
                        "target_scope": _string(target_scope) or existing.target_scope,
                        "status": _string(status) or existing.status,
                        "lifecycle_stage": _string(lifecycle_stage)
                        or existing.lifecycle_stage,
                        "candidate_source_kind": hit.candidate_source_kind,
                        "candidate_source_ref": candidate_source_ref,
                        "candidate_source_version": hit.candidate_source_version,
                        "candidate_source_lineage": hit.candidate_source_lineage,
                        "canonical_package_id": hit.canonical_package_id,
                        "source_aliases": _string_list(
                            existing.source_aliases,
                            hit.source_aliases,
                        ),
                        "equivalence_class": _string(hit.equivalence_class)
                        or existing.equivalence_class,
                        "capability_overlap_score": (
                            hit.capability_overlap_score
                            if hit.capability_overlap_score is not None
                            else existing.capability_overlap_score
                        ),
                        "replacement_relation": _string(hit.replacement_relation)
                        or existing.replacement_relation,
                        "ingestion_mode": _string(ingestion_mode) or existing.ingestion_mode,
                        "proposed_skill_name": _string(hit.display_name)
                        or existing.proposed_skill_name,
                        "summary": str(hit.summary or existing.summary or ""),
                        "metadata": _merge_metadata(existing.metadata, metadata),
                    },
                )
                self._upsert_record(updated)
                imported.append(updated)
                continue
            imported.append(
                self.normalize_candidate_source(
                    candidate_kind=hit.candidate_kind,
                    industry_instance_id=industry_instance_id,
                    target_scope=target_scope,
                    target_role_id=target_role_id,
                    target_seat_ref=target_seat_ref,
                    candidate_source_kind=hit.candidate_source_kind,
                    candidate_source_ref=candidate_source_ref,
                    candidate_source_version=hit.candidate_source_version,
                    candidate_source_lineage=hit.candidate_source_lineage,
                    ingestion_mode=ingestion_mode,
                    proposed_skill_name=hit.display_name,
                    summary=hit.summary,
                    status=status,
                    lifecycle_stage=lifecycle_stage,
                    canonical_package_id=hit.canonical_package_id,
                    source_aliases=hit.source_aliases,
                    equivalence_class=hit.equivalence_class,
                    capability_overlap_score=hit.capability_overlap_score,
                    replacement_relation=hit.replacement_relation,
                    metadata=metadata,
                )
            )
        return imported

    def _find_existing_candidate(
        self,
        *,
        candidate_source_kind: str,
        candidate_source_ref: str | None,
        candidate_source_version: str | None,
        target_role_id: str | None,
        target_scope: str,
        target_seat_ref: str | None,
    ) -> CapabilityCandidateRecord | None:
        with self._state_store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM capability_candidates
                WHERE candidate_source_kind = ?
                  AND COALESCE(candidate_source_ref, '') = COALESCE(?, '')
                  AND COALESCE(candidate_source_version, '') = COALESCE(?, '')
                  AND COALESCE(target_role_id, '') = COALESCE(?, '')
                  AND target_scope = ?
                  AND COALESCE(target_seat_ref, '') = COALESCE(?, '')
                ORDER BY updated_at DESC, candidate_id DESC
                LIMIT 1
                """,
                (
                    candidate_source_kind,
                    candidate_source_ref,
                    candidate_source_version,
                    target_role_id,
                    target_scope,
                    target_seat_ref,
                ),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def _find_existing_candidate_by_lineage(
        self,
        *,
        candidate_source_kind: str,
        candidate_source_lineage: str,
        target_role_id: str | None,
        target_scope: str,
        target_seat_ref: str | None,
    ) -> CapabilityCandidateRecord | None:
        with self._state_store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM capability_candidates
                WHERE candidate_source_kind = ?
                  AND candidate_source_lineage = ?
                  AND COALESCE(target_role_id, '') = COALESCE(?, '')
                  AND target_scope = ?
                  AND COALESCE(target_seat_ref, '') = COALESCE(?, '')
                ORDER BY updated_at DESC, candidate_id DESC
                LIMIT 1
                """,
                (
                    candidate_source_kind,
                    candidate_source_lineage,
                    target_role_id,
                    target_scope,
                    target_seat_ref,
                ),
            ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def _upsert_record(self, record: CapabilityCandidateRecord) -> None:
        with self._state_store.connection() as conn:
            conn.execute(
                """
                INSERT INTO capability_candidates (
                    candidate_id,
                    donor_id,
                    package_id,
                    source_profile_id,
                    canonical_package_id,
                    candidate_kind,
                    industry_instance_id,
                    target_role_id,
                    target_seat_ref,
                    target_scope,
                    status,
                    lifecycle_stage,
                    candidate_source_kind,
                    candidate_source_ref,
                    candidate_source_version,
                    candidate_source_lineage,
                    source_aliases_json,
                    equivalence_class,
                    capability_overlap_score,
                    replacement_relation,
                    ingestion_mode,
                    proposed_skill_name,
                    summary,
                    replacement_target_ids_json,
                    rollback_target_ids_json,
                    required_capability_ids_json,
                    required_mcp_ids_json,
                    protection_flags_json,
                    success_criteria_json,
                    rollback_criteria_json,
                    source_task_ids_json,
                    evidence_refs_json,
                    version,
                    lineage_root_id,
                    supersedes_json,
                    superseded_by_json,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :candidate_id,
                    :donor_id,
                    :package_id,
                    :source_profile_id,
                    :canonical_package_id,
                    :candidate_kind,
                    :industry_instance_id,
                    :target_role_id,
                    :target_seat_ref,
                    :target_scope,
                    :status,
                    :lifecycle_stage,
                    :candidate_source_kind,
                    :candidate_source_ref,
                    :candidate_source_version,
                    :candidate_source_lineage,
                    :source_aliases_json,
                    :equivalence_class,
                    :capability_overlap_score,
                    :replacement_relation,
                    :ingestion_mode,
                    :proposed_skill_name,
                    :summary,
                    :replacement_target_ids_json,
                    :rollback_target_ids_json,
                    :required_capability_ids_json,
                    :required_mcp_ids_json,
                    :protection_flags_json,
                    :success_criteria_json,
                    :rollback_criteria_json,
                    :source_task_ids_json,
                    :evidence_refs_json,
                    :version,
                    :lineage_root_id,
                    :supersedes_json,
                    :superseded_by_json,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(candidate_id) DO UPDATE SET
                    donor_id = excluded.donor_id,
                    package_id = excluded.package_id,
                    source_profile_id = excluded.source_profile_id,
                    canonical_package_id = excluded.canonical_package_id,
                    candidate_kind = excluded.candidate_kind,
                    industry_instance_id = excluded.industry_instance_id,
                    target_role_id = excluded.target_role_id,
                    target_seat_ref = excluded.target_seat_ref,
                    target_scope = excluded.target_scope,
                    status = excluded.status,
                    lifecycle_stage = excluded.lifecycle_stage,
                    candidate_source_kind = excluded.candidate_source_kind,
                    candidate_source_ref = excluded.candidate_source_ref,
                    candidate_source_version = excluded.candidate_source_version,
                    candidate_source_lineage = excluded.candidate_source_lineage,
                    source_aliases_json = excluded.source_aliases_json,
                    equivalence_class = excluded.equivalence_class,
                    capability_overlap_score = excluded.capability_overlap_score,
                    replacement_relation = excluded.replacement_relation,
                    ingestion_mode = excluded.ingestion_mode,
                    proposed_skill_name = excluded.proposed_skill_name,
                    summary = excluded.summary,
                    replacement_target_ids_json = excluded.replacement_target_ids_json,
                    rollback_target_ids_json = excluded.rollback_target_ids_json,
                    required_capability_ids_json = excluded.required_capability_ids_json,
                    required_mcp_ids_json = excluded.required_mcp_ids_json,
                    protection_flags_json = excluded.protection_flags_json,
                    success_criteria_json = excluded.success_criteria_json,
                    rollback_criteria_json = excluded.rollback_criteria_json,
                    source_task_ids_json = excluded.source_task_ids_json,
                    evidence_refs_json = excluded.evidence_refs_json,
                    version = excluded.version,
                    lineage_root_id = excluded.lineage_root_id,
                    supersedes_json = excluded.supersedes_json,
                    superseded_by_json = excluded.superseded_by_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                {
                    "candidate_id": record.candidate_id,
                    "donor_id": record.donor_id,
                    "package_id": record.package_id,
                    "source_profile_id": record.source_profile_id,
                    "canonical_package_id": record.canonical_package_id,
                    "candidate_kind": record.candidate_kind,
                    "industry_instance_id": record.industry_instance_id,
                    "target_role_id": record.target_role_id,
                    "target_seat_ref": record.target_seat_ref,
                    "target_scope": record.target_scope,
                    "status": record.status,
                    "lifecycle_stage": record.lifecycle_stage,
                    "candidate_source_kind": record.candidate_source_kind,
                    "candidate_source_ref": record.candidate_source_ref,
                    "candidate_source_version": record.candidate_source_version,
                    "candidate_source_lineage": record.candidate_source_lineage,
                    "source_aliases_json": _json_dumps(record.source_aliases),
                    "equivalence_class": record.equivalence_class,
                    "capability_overlap_score": record.capability_overlap_score,
                    "replacement_relation": record.replacement_relation,
                    "ingestion_mode": record.ingestion_mode,
                    "proposed_skill_name": record.proposed_skill_name,
                    "summary": record.summary,
                    "replacement_target_ids_json": _json_dumps(record.replacement_target_ids),
                    "rollback_target_ids_json": _json_dumps(record.rollback_target_ids),
                    "required_capability_ids_json": _json_dumps(record.required_capability_ids),
                    "required_mcp_ids_json": _json_dumps(record.required_mcp_ids),
                    "protection_flags_json": _json_dumps(record.protection_flags),
                    "success_criteria_json": _json_dumps(record.success_criteria),
                    "rollback_criteria_json": _json_dumps(record.rollback_criteria),
                    "source_task_ids_json": _json_dumps(record.source_task_ids),
                    "evidence_refs_json": _json_dumps(record.evidence_refs),
                    "version": record.version,
                    "lineage_root_id": record.lineage_root_id,
                    "supersedes_json": _json_dumps(record.supersedes),
                    "superseded_by_json": _json_dumps(record.superseded_by),
                    "metadata_json": _json_dumps(record.metadata),
                    "created_at": record.created_at.isoformat(),
                    "updated_at": record.updated_at.isoformat(),
                },
            )

    def _row_to_record(self, row) -> CapabilityCandidateRecord:
        return CapabilityCandidateRecord(
            candidate_id=row["candidate_id"],
            donor_id=row["donor_id"],
            package_id=row["package_id"],
            source_profile_id=row["source_profile_id"],
            canonical_package_id=row["canonical_package_id"],
            candidate_kind=row["candidate_kind"],
            industry_instance_id=row["industry_instance_id"],
            target_role_id=row["target_role_id"],
            target_seat_ref=row["target_seat_ref"],
            target_scope=row["target_scope"],
            status=row["status"],
            lifecycle_stage=row["lifecycle_stage"],
            candidate_source_kind=row["candidate_source_kind"],
            candidate_source_ref=row["candidate_source_ref"],
            candidate_source_version=row["candidate_source_version"],
            candidate_source_lineage=row["candidate_source_lineage"],
            source_aliases=_json_load_list(row["source_aliases_json"]),
            equivalence_class=row["equivalence_class"],
            capability_overlap_score=_float_value(row["capability_overlap_score"]),
            replacement_relation=row["replacement_relation"],
            ingestion_mode=row["ingestion_mode"],
            proposed_skill_name=row["proposed_skill_name"],
            summary=row["summary"] or "",
            replacement_target_ids=_json_load_list(row["replacement_target_ids_json"]),
            rollback_target_ids=_json_load_list(row["rollback_target_ids_json"]),
            required_capability_ids=_json_load_list(row["required_capability_ids_json"]),
            required_mcp_ids=_json_load_list(row["required_mcp_ids_json"]),
            protection_flags=_json_load_list(row["protection_flags_json"]),
            success_criteria=_json_load_list(row["success_criteria_json"]),
            rollback_criteria=_json_load_list(row["rollback_criteria_json"]),
            source_task_ids=_json_load_list(row["source_task_ids_json"]),
            evidence_refs=_json_load_list(row["evidence_refs_json"]),
            version=row["version"],
            lineage_root_id=row["lineage_root_id"],
            supersedes=_json_load_list(row["supersedes_json"]),
            superseded_by=_json_load_list(row["superseded_by_json"]),
            metadata=_json_load_dict(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
