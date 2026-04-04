# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any, Iterable

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

    def summarize_candidates(self) -> dict[str, object]:
        items = self.list_candidates()
        by_kind: dict[str, int] = {}
        by_source_kind: dict[str, int] = {}
        for item in items:
            by_kind[item.candidate_kind] = by_kind.get(item.candidate_kind, 0) + 1
            by_source_kind[item.candidate_source_kind] = (
                by_source_kind.get(item.candidate_source_kind, 0) + 1
            )
        return {
            "total": len(items),
            "by_kind": by_kind,
            "by_source_kind": by_source_kind,
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
        metadata: dict[str, Any] | None = None,
    ) -> CapabilityCandidateRecord:
        record = CapabilityCandidateRecord(
            donor_id=None,
            package_id=None,
            source_profile_id=None,
            candidate_kind=_string(candidate_kind) or "skill",
            target_scope=_string(target_scope) or "seat",
            target_role_id=_string(target_role_id),
            target_seat_ref=_string(target_seat_ref),
            industry_instance_id=_string(industry_instance_id),
            candidate_source_kind=_string(candidate_source_kind) or "local_authored",
            candidate_source_ref=_string(candidate_source_ref),
            candidate_source_version=_string(candidate_source_version),
            candidate_source_lineage=_string(candidate_source_lineage),
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
            metadata=dict(metadata or {}),
        )
        record.lineage_root_id = _string(lineage_root_id) or record.candidate_id
        register_candidate_source = getattr(
            self._donor_service,
            "register_candidate_source",
            None,
        )
        if callable(register_candidate_source):
            donor_id, package_id, source_profile_id = register_candidate_source(record)
            record = record.model_copy(
                update={
                    "donor_id": donor_id,
                    "package_id": package_id,
                    "source_profile_id": source_profile_id,
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

    def _upsert_record(self, record: CapabilityCandidateRecord) -> None:
        with self._state_store.connection() as conn:
            conn.execute(
                """
                INSERT INTO capability_candidates (
                    candidate_id,
                    donor_id,
                    package_id,
                    source_profile_id,
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
