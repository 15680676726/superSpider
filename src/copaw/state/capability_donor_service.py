# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Any

from .models_capability_evolution import (
    CapabilityCandidateRecord,
    CapabilityDonorRecord,
    CapabilityDonorTrustRecord,
    CapabilityPackageRecord,
    CapabilitySourceProfileRecord,
)
from .store import SQLiteStateStore


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_load_dict(value: object | None) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _json_load_list(value: object | None) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in (_string(entry) for entry in payload) if item is not None]


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _default_source_posture(source_kind: str) -> str:
    normalized = source_kind.strip().lower()
    if normalized == "external_catalog":
        return "trusted"
    if normalized == "local_authored":
        return "local"
    return "watchlist"


def _default_trust_status(*, source_posture: str, donor_status: str) -> str:
    if donor_status == "retired":
        return "retired"
    if source_posture == "trusted":
        return "trusted" if donor_status == "active" else "observing"
    if source_posture == "local":
        return "local"
    return "observing"


def _normalize_source_key(
    *,
    source_kind: str,
    source_ref: str | None,
    source_lineage: str | None,
) -> str:
    return ":".join(
        part
        for part in (
            source_kind.strip().lower(),
            _string(source_lineage) or _string(source_ref) or "unknown",
        )
        if part
    )


def _normalize_donor_key(candidate: CapabilityCandidateRecord) -> str:
    return ":".join(
        part
        for part in (
            candidate.candidate_kind.strip().lower(),
            candidate.candidate_source_kind.strip().lower(),
            _string(candidate.candidate_source_lineage)
            or _string(candidate.candidate_source_ref)
            or "unknown",
        )
        if part
    )


def _normalize_donor_status(candidate: CapabilityCandidateRecord) -> str:
    stage = str(candidate.lifecycle_stage or "").strip().lower()
    status = str(candidate.status or "").strip().lower()
    if stage in {"retired", "rollback"} or status == "retired":
        return "retired"
    if stage in {"baseline", "active"} or status == "active":
        return "active"
    if stage == "trial" or status == "trial":
        return "trial"
    return "candidate"


def _normalize_aliases(*values: object) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            items = list(value)
        else:
            items = [value]
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


def _normalize_source_aliases(candidate: CapabilityCandidateRecord) -> list[str]:
    return _normalize_aliases(
        getattr(candidate, "source_aliases", []),
        candidate.candidate_source_ref,
    )


def _normalize_canonical_package_id(candidate: CapabilityCandidateRecord) -> str:
    explicit = _string(getattr(candidate, "canonical_package_id", None))
    if explicit is not None:
        return explicit
    return "|".join(
        (
            candidate.candidate_kind.strip().lower(),
            candidate.candidate_source_kind.strip().lower(),
            _string(candidate.candidate_source_ref) or "unknown",
            _string(candidate.candidate_source_version) or "unversioned",
        ),
    )


def _normalize_equivalence_class(
    candidate: CapabilityCandidateRecord,
    *,
    canonical_package_id: str,
    donor_key: str,
) -> str:
    return (
        _string(getattr(candidate, "equivalence_class", None))
        or canonical_package_id
        or donor_key
    )


def _normalize_replacement_relation(candidate: CapabilityCandidateRecord) -> str | None:
    explicit = _string(getattr(candidate, "replacement_relation", None))
    if explicit is not None:
        return explicit
    if list(candidate.replacement_target_ids or []):
        return "replace_requested"
    return None


class CapabilityDonorService:
    def __init__(self, *, state_store: SQLiteStateStore) -> None:
        self._state_store = state_store
        self._state_store.initialize()

    def register_candidate_source(
        self,
        candidate: CapabilityCandidateRecord,
    ) -> tuple[str | None, str | None, str | None]:
        source_profile = self._upsert_source_profile(candidate)
        donor = self._upsert_donor(candidate, source_profile=source_profile)
        package = self._upsert_package(
            candidate,
            donor=donor,
            source_profile=source_profile,
        )
        self._upsert_trust(
            candidate=candidate,
            donor=donor,
            package=package,
            source_profile=source_profile,
            donor_status=donor.status,
        )
        self._refresh_package_count(donor.donor_id)
        return donor.donor_id, package.package_id, source_profile.source_profile_id

    def list_donors(self, *, limit: int | None = None) -> list[CapabilityDonorRecord]:
        query = """
            SELECT *
            FROM capability_donors
            ORDER BY updated_at DESC, donor_id DESC
        """
        params: tuple[object, ...] = ()
        if isinstance(limit, int) and limit > 0:
            query += "\nLIMIT ?"
            params = (limit,)
        with self._state_store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_donor(row) for row in rows]

    def get_donor(self, donor_id: str | None) -> CapabilityDonorRecord | None:
        if _string(donor_id) is None:
            return None
        with self._state_store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM capability_donors
                WHERE donor_id = ?
                LIMIT 1
                """,
                (donor_id,),
            ).fetchone()
        return self._row_to_donor(row) if row is not None else None

    def list_packages(
        self,
        *,
        donor_id: str | None = None,
        limit: int | None = None,
    ) -> list[CapabilityPackageRecord]:
        query = """
            SELECT *
            FROM capability_packages
        """
        params: list[object] = []
        if _string(donor_id) is not None:
            query += "\nWHERE donor_id = ?"
            params.append(donor_id)
        query += "\nORDER BY updated_at DESC, package_id DESC"
        if isinstance(limit, int) and limit > 0:
            query += "\nLIMIT ?"
            params.append(limit)
        with self._state_store.connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_package(row) for row in rows]

    def get_package(self, package_id: str | None) -> CapabilityPackageRecord | None:
        if _string(package_id) is None:
            return None
        with self._state_store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM capability_packages
                WHERE package_id = ?
                LIMIT 1
                """,
                (package_id,),
            ).fetchone()
        return self._row_to_package(row) if row is not None else None

    def list_source_profiles(
        self,
        *,
        limit: int | None = None,
    ) -> list[CapabilitySourceProfileRecord]:
        query = """
            SELECT *
            FROM capability_source_profiles
            ORDER BY updated_at DESC, source_profile_id DESC
        """
        params: tuple[object, ...] = ()
        if isinstance(limit, int) and limit > 0:
            query += "\nLIMIT ?"
            params = (limit,)
        with self._state_store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_source_profile(row) for row in rows]

    def get_source_profile(
        self,
        source_profile_id: str | None,
    ) -> CapabilitySourceProfileRecord | None:
        if _string(source_profile_id) is None:
            return None
        with self._state_store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM capability_source_profiles
                WHERE source_profile_id = ?
                LIMIT 1
                """,
                (source_profile_id,),
            ).fetchone()
        return self._row_to_source_profile(row) if row is not None else None

    def list_trust_records(
        self,
        *,
        limit: int | None = None,
    ) -> list[CapabilityDonorTrustRecord]:
        query = """
            SELECT *
            FROM capability_donor_trust
            ORDER BY updated_at DESC, donor_id DESC
        """
        params: tuple[object, ...] = ()
        if isinstance(limit, int) and limit > 0:
            query += "\nLIMIT ?"
            params = (limit,)
        with self._state_store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_trust(row) for row in rows]

    def get_trust_record(self, donor_id: str | None) -> CapabilityDonorTrustRecord | None:
        if _string(donor_id) is None:
            return None
        with self._state_store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM capability_donor_trust
                WHERE donor_id = ?
                LIMIT 1
                """,
                (donor_id,),
            ).fetchone()
        return self._row_to_trust(row) if row is not None else None

    def upsert_trust_record(
        self,
        record: CapabilityDonorTrustRecord,
    ) -> CapabilityDonorTrustRecord:
        self._write_trust(record)
        return record

    def _upsert_source_profile(
        self,
        candidate: CapabilityCandidateRecord,
    ) -> CapabilitySourceProfileRecord:
        source_aliases = _normalize_source_aliases(candidate)
        source_key = _normalize_source_key(
            source_kind=candidate.candidate_source_kind,
            source_ref=candidate.candidate_source_ref,
            source_lineage=candidate.candidate_source_lineage,
        )
        source_kind = candidate.candidate_source_kind.strip().lower()
        trust_posture = _default_source_posture(source_kind)
        display_name = (
            _string(candidate.proposed_skill_name)
            or _string(candidate.candidate_source_ref)
            or source_key
        )
        with self._state_store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM capability_source_profiles
                WHERE source_kind = ?
                  AND source_key = ?
                ORDER BY updated_at DESC, source_profile_id DESC
                LIMIT 1
                """,
                (source_kind, source_key),
            ).fetchone()
        record = (
            self._row_to_source_profile(row)
            if row is not None
            else CapabilitySourceProfileRecord(
                source_kind=source_kind,
                source_key=source_key,
                source_lineage=candidate.candidate_source_lineage,
                source_aliases=source_aliases,
                display_name=display_name,
                trust_posture=trust_posture,
                active=True,
                metadata={
                    "source_ref": candidate.candidate_source_ref,
                    "source_lineage": candidate.candidate_source_lineage,
                },
            )
        )
        record = record.model_copy(
            update={
                "source_lineage": candidate.candidate_source_lineage,
                "source_aliases": _normalize_aliases(record.source_aliases, source_aliases),
                "display_name": display_name,
                "trust_posture": record.trust_posture or trust_posture,
                "active": True,
                "metadata": {
                    **dict(record.metadata or {}),
                    "source_ref": candidate.candidate_source_ref,
                    "source_lineage": candidate.candidate_source_lineage,
                },
            },
        )
        self._write_source_profile(record)
        return record

    def _upsert_donor(
        self,
        candidate: CapabilityCandidateRecord,
        *,
        source_profile: CapabilitySourceProfileRecord,
    ) -> CapabilityDonorRecord:
        normalized_key = _normalize_donor_key(candidate)
        donor_status = _normalize_donor_status(candidate)
        canonical_package_id = _normalize_canonical_package_id(candidate)
        source_aliases = _normalize_source_aliases(candidate)
        equivalence_class = _normalize_equivalence_class(
            candidate,
            canonical_package_id=canonical_package_id,
            donor_key=normalized_key,
        )
        replacement_relation = _normalize_replacement_relation(candidate)
        display_name = (
            _string(candidate.proposed_skill_name)
            or _string(candidate.candidate_source_ref)
            or normalized_key
        )
        with self._state_store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM capability_donors
                WHERE normalized_key = ?
                ORDER BY updated_at DESC, donor_id DESC
                LIMIT 1
                """,
                (normalized_key,),
            ).fetchone()
        record = (
            self._row_to_donor(row)
            if row is not None
            else CapabilityDonorRecord(
                donor_kind=candidate.candidate_kind,
                normalized_key=normalized_key,
                canonical_package_id=canonical_package_id,
                source_kind=candidate.candidate_source_kind,
                primary_source_ref=candidate.candidate_source_ref,
                candidate_source_lineage=candidate.candidate_source_lineage,
                source_aliases=source_aliases,
                equivalence_class=equivalence_class,
                replacement_relation=replacement_relation,
                display_name=display_name,
                status=donor_status,
                trust_status=_default_trust_status(
                    source_posture=source_profile.trust_posture,
                    donor_status=donor_status,
                ),
                metadata={
                    "source_profile_id": source_profile.source_profile_id,
                    "target_scope": candidate.target_scope,
                    "target_role_id": candidate.target_role_id,
                    "target_seat_ref": candidate.target_seat_ref,
                },
            )
        )
        existing_trust = str(record.trust_status or "").strip().lower()
        next_trust = _default_trust_status(
            source_posture=source_profile.trust_posture,
            donor_status=donor_status,
        )
        if existing_trust in {"degraded", "blocked"}:
            next_trust = existing_trust
        record = record.model_copy(
            update={
                "donor_kind": candidate.candidate_kind,
                "canonical_package_id": canonical_package_id,
                "source_kind": candidate.candidate_source_kind,
                "primary_source_ref": candidate.candidate_source_ref,
                "candidate_source_lineage": candidate.candidate_source_lineage,
                "source_aliases": _normalize_aliases(record.source_aliases, source_aliases),
                "equivalence_class": equivalence_class,
                "replacement_relation": replacement_relation,
                "display_name": display_name,
                "status": donor_status,
                "trust_status": next_trust,
                "metadata": {
                    **dict(record.metadata or {}),
                    "source_profile_id": source_profile.source_profile_id,
                    "target_scope": candidate.target_scope,
                    "target_role_id": candidate.target_role_id,
                    "target_seat_ref": candidate.target_seat_ref,
                },
            },
        )
        self._write_donor(record)
        return record

    def _upsert_package(
        self,
        candidate: CapabilityCandidateRecord,
        *,
        donor: CapabilityDonorRecord,
        source_profile: CapabilitySourceProfileRecord,
    ) -> CapabilityPackageRecord:
        canonical_package_id = _normalize_canonical_package_id(candidate)
        package_ref = _string(candidate.candidate_source_ref)
        package_version = _string(candidate.candidate_source_version)
        package_kind = candidate.candidate_kind
        source_aliases = _normalize_source_aliases(candidate)
        equivalence_class = _normalize_equivalence_class(
            candidate,
            canonical_package_id=canonical_package_id,
            donor_key=donor.normalized_key,
        )
        with self._state_store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM capability_packages
                WHERE donor_id = ?
                  AND COALESCE(package_ref, '') = COALESCE(?, '')
                  AND COALESCE(package_version, '') = COALESCE(?, '')
                ORDER BY updated_at DESC, package_id DESC
                LIMIT 1
                """,
                (donor.donor_id, package_ref, package_version),
            ).fetchone()
        record = (
            self._row_to_package(row)
            if row is not None
            else CapabilityPackageRecord(
                donor_id=donor.donor_id,
                source_profile_id=source_profile.source_profile_id,
                canonical_package_id=canonical_package_id,
                package_ref=package_ref,
                package_version=package_version,
                source_aliases=source_aliases,
                equivalence_class=equivalence_class,
                package_kind=package_kind,
                status="available" if donor.status != "retired" else "retired",
                metadata={
                    "candidate_kind": candidate.candidate_kind,
                    "ingestion_mode": candidate.ingestion_mode,
                },
            )
        )
        record = record.model_copy(
            update={
                "source_profile_id": source_profile.source_profile_id,
                "canonical_package_id": canonical_package_id,
                "package_ref": package_ref,
                "package_version": package_version,
                "source_aliases": _normalize_aliases(record.source_aliases, source_aliases),
                "equivalence_class": equivalence_class,
                "package_kind": package_kind,
                "status": "available" if donor.status != "retired" else "retired",
                "metadata": {
                    **dict(record.metadata or {}),
                    "candidate_kind": candidate.candidate_kind,
                    "ingestion_mode": candidate.ingestion_mode,
                    **{
                        key: value
                        for key, value in dict(candidate.metadata or {}).items()
                        if key
                        in {
                            "provider_injection_mode",
                            "execution_envelope",
                            "host_compatibility_requirements",
                        }
                    },
                },
            },
        )
        self._write_package(record)
        return record

    def _upsert_trust(
        self,
        *,
        candidate: CapabilityCandidateRecord,
        donor: CapabilityDonorRecord,
        package: CapabilityPackageRecord,
        source_profile: CapabilitySourceProfileRecord,
        donor_status: str,
    ) -> CapabilityDonorTrustRecord:
        with self._state_store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM capability_donor_trust
                WHERE donor_id = ?
                LIMIT 1
                """,
                (donor.donor_id,),
            ).fetchone()
        record = (
            self._row_to_trust(row)
            if row is not None
            else CapabilityDonorTrustRecord(
                donor_id=donor.donor_id,
                source_profile_id=source_profile.source_profile_id,
                last_candidate_id=candidate.candidate_id,
                last_package_id=package.package_id,
                last_canonical_package_id=package.canonical_package_id,
                trust_status=_default_trust_status(
                    source_posture=source_profile.trust_posture,
                    donor_status=donor_status,
                ),
                replacement_pressure_count=max(0, len(candidate.replacement_target_ids)),
                metadata={
                    "source_kind": source_profile.source_kind,
                    "source_key": source_profile.source_key,
                },
            )
        )
        if record.trust_status not in {"degraded", "blocked"}:
            record = record.model_copy(
                update={
                    "source_profile_id": source_profile.source_profile_id,
                    "last_candidate_id": candidate.candidate_id,
                    "last_package_id": package.package_id,
                    "last_canonical_package_id": package.canonical_package_id,
                    "trust_status": _default_trust_status(
                        source_posture=source_profile.trust_posture,
                        donor_status=donor_status,
                    ),
                    "replacement_pressure_count": max(
                        int(record.replacement_pressure_count or 0),
                        len(candidate.replacement_target_ids),
                    ),
                    "metadata": {
                        **dict(record.metadata or {}),
                        "source_kind": source_profile.source_kind,
                        "source_key": source_profile.source_key,
                    },
                },
            )
        self._write_trust(record)
        return record

    def _refresh_package_count(self, donor_id: str) -> None:
        with self._state_store.connection() as conn:
            count = int(
                conn.execute(
                    """
                    SELECT COUNT(1)
                    FROM capability_packages
                    WHERE donor_id = ?
                    """,
                    (donor_id,),
                ).fetchone()[0]
                or 0
            )
            conn.execute(
                """
                UPDATE capability_donors
                SET package_count = ?
                WHERE donor_id = ?
                """,
                (count, donor_id),
            )

    def _write_donor(self, record: CapabilityDonorRecord) -> None:
        with self._state_store.connection() as conn:
            conn.execute(
                """
                INSERT INTO capability_donors (
                    donor_id,
                    donor_kind,
                    normalized_key,
                    canonical_package_id,
                    source_kind,
                    primary_source_ref,
                    candidate_source_lineage,
                    source_aliases_json,
                    equivalence_class,
                    replacement_relation,
                    display_name,
                    status,
                    trust_status,
                    package_count,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :donor_id,
                    :donor_kind,
                    :normalized_key,
                    :canonical_package_id,
                    :source_kind,
                    :primary_source_ref,
                    :candidate_source_lineage,
                    :source_aliases_json,
                    :equivalence_class,
                    :replacement_relation,
                    :display_name,
                    :status,
                    :trust_status,
                    :package_count,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(donor_id) DO UPDATE SET
                    donor_kind = excluded.donor_kind,
                    normalized_key = excluded.normalized_key,
                    canonical_package_id = excluded.canonical_package_id,
                    source_kind = excluded.source_kind,
                    primary_source_ref = excluded.primary_source_ref,
                    candidate_source_lineage = excluded.candidate_source_lineage,
                    source_aliases_json = excluded.source_aliases_json,
                    equivalence_class = excluded.equivalence_class,
                    replacement_relation = excluded.replacement_relation,
                    display_name = excluded.display_name,
                    status = excluded.status,
                    trust_status = excluded.trust_status,
                    package_count = excluded.package_count,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                {
                    "donor_id": record.donor_id,
                    "donor_kind": record.donor_kind,
                    "normalized_key": record.normalized_key,
                    "canonical_package_id": record.canonical_package_id,
                    "source_kind": record.source_kind,
                    "primary_source_ref": record.primary_source_ref,
                    "candidate_source_lineage": record.candidate_source_lineage,
                    "source_aliases_json": _json_dumps(record.source_aliases),
                    "equivalence_class": record.equivalence_class,
                    "replacement_relation": record.replacement_relation,
                    "display_name": record.display_name,
                    "status": record.status,
                    "trust_status": record.trust_status,
                    "package_count": record.package_count,
                    "metadata_json": _json_dumps(record.metadata),
                    "created_at": record.created_at.isoformat(),
                    "updated_at": record.updated_at.isoformat(),
                },
            )

    def _write_package(self, record: CapabilityPackageRecord) -> None:
        with self._state_store.connection() as conn:
            conn.execute(
                """
                INSERT INTO capability_packages (
                    package_id,
                    donor_id,
                    source_profile_id,
                    canonical_package_id,
                    package_ref,
                    package_version,
                    source_aliases_json,
                    equivalence_class,
                    package_kind,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :package_id,
                    :donor_id,
                    :source_profile_id,
                    :canonical_package_id,
                    :package_ref,
                    :package_version,
                    :source_aliases_json,
                    :equivalence_class,
                    :package_kind,
                    :status,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(package_id) DO UPDATE SET
                    donor_id = excluded.donor_id,
                    source_profile_id = excluded.source_profile_id,
                    canonical_package_id = excluded.canonical_package_id,
                    package_ref = excluded.package_ref,
                    package_version = excluded.package_version,
                    source_aliases_json = excluded.source_aliases_json,
                    equivalence_class = excluded.equivalence_class,
                    package_kind = excluded.package_kind,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                {
                    "package_id": record.package_id,
                    "donor_id": record.donor_id,
                    "source_profile_id": record.source_profile_id,
                    "canonical_package_id": record.canonical_package_id,
                    "package_ref": record.package_ref,
                    "package_version": record.package_version,
                    "source_aliases_json": _json_dumps(record.source_aliases),
                    "equivalence_class": record.equivalence_class,
                    "package_kind": record.package_kind,
                    "status": record.status,
                    "metadata_json": _json_dumps(record.metadata),
                    "created_at": record.created_at.isoformat(),
                    "updated_at": record.updated_at.isoformat(),
                },
            )

    def _write_source_profile(self, record: CapabilitySourceProfileRecord) -> None:
        with self._state_store.connection() as conn:
            conn.execute(
                """
                INSERT INTO capability_source_profiles (
                    source_profile_id,
                    source_kind,
                    source_key,
                    source_lineage,
                    source_aliases_json,
                    display_name,
                    trust_posture,
                    active,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :source_profile_id,
                    :source_kind,
                    :source_key,
                    :source_lineage,
                    :source_aliases_json,
                    :display_name,
                    :trust_posture,
                    :active,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(source_profile_id) DO UPDATE SET
                    source_kind = excluded.source_kind,
                    source_key = excluded.source_key,
                    source_lineage = excluded.source_lineage,
                    source_aliases_json = excluded.source_aliases_json,
                    display_name = excluded.display_name,
                    trust_posture = excluded.trust_posture,
                    active = excluded.active,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                {
                    "source_profile_id": record.source_profile_id,
                    "source_kind": record.source_kind,
                    "source_key": record.source_key,
                    "source_lineage": record.source_lineage,
                    "source_aliases_json": _json_dumps(record.source_aliases),
                    "display_name": record.display_name,
                    "trust_posture": record.trust_posture,
                    "active": 1 if record.active else 0,
                    "metadata_json": _json_dumps(record.metadata),
                    "created_at": record.created_at.isoformat(),
                    "updated_at": record.updated_at.isoformat(),
                },
            )

    def _write_trust(self, record: CapabilityDonorTrustRecord) -> None:
        with self._state_store.connection() as conn:
            conn.execute(
                """
                INSERT INTO capability_donor_trust (
                    donor_id,
                    source_profile_id,
                    last_candidate_id,
                    last_package_id,
                    last_canonical_package_id,
                    trust_status,
                    trial_success_count,
                    trial_failure_count,
                    underperformance_count,
                    rollback_count,
                    replacement_pressure_count,
                    retirement_count,
                    last_trial_verdict,
                    last_decision_kind,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :donor_id,
                    :source_profile_id,
                    :last_candidate_id,
                    :last_package_id,
                    :last_canonical_package_id,
                    :trust_status,
                    :trial_success_count,
                    :trial_failure_count,
                    :underperformance_count,
                    :rollback_count,
                    :replacement_pressure_count,
                    :retirement_count,
                    :last_trial_verdict,
                    :last_decision_kind,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(donor_id) DO UPDATE SET
                    source_profile_id = excluded.source_profile_id,
                    last_candidate_id = excluded.last_candidate_id,
                    last_package_id = excluded.last_package_id,
                    last_canonical_package_id = excluded.last_canonical_package_id,
                    trust_status = excluded.trust_status,
                    trial_success_count = excluded.trial_success_count,
                    trial_failure_count = excluded.trial_failure_count,
                    underperformance_count = excluded.underperformance_count,
                    rollback_count = excluded.rollback_count,
                    replacement_pressure_count = excluded.replacement_pressure_count,
                    retirement_count = excluded.retirement_count,
                    last_trial_verdict = excluded.last_trial_verdict,
                    last_decision_kind = excluded.last_decision_kind,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                {
                    "donor_id": record.donor_id,
                    "source_profile_id": record.source_profile_id,
                    "last_candidate_id": record.last_candidate_id,
                    "last_package_id": record.last_package_id,
                    "last_canonical_package_id": record.last_canonical_package_id,
                    "trust_status": record.trust_status,
                    "trial_success_count": record.trial_success_count,
                    "trial_failure_count": record.trial_failure_count,
                    "underperformance_count": record.underperformance_count,
                    "rollback_count": record.rollback_count,
                    "replacement_pressure_count": record.replacement_pressure_count,
                    "retirement_count": record.retirement_count,
                    "last_trial_verdict": record.last_trial_verdict,
                    "last_decision_kind": record.last_decision_kind,
                    "metadata_json": _json_dumps(record.metadata),
                    "created_at": record.created_at.isoformat(),
                    "updated_at": record.updated_at.isoformat(),
                },
            )

    def _row_to_donor(self, row) -> CapabilityDonorRecord:
        return CapabilityDonorRecord(
            donor_id=row["donor_id"],
            donor_kind=row["donor_kind"],
            normalized_key=row["normalized_key"],
            canonical_package_id=row["canonical_package_id"],
            source_kind=row["source_kind"],
            primary_source_ref=row["primary_source_ref"],
            candidate_source_lineage=row["candidate_source_lineage"],
            source_aliases=_json_load_list(row["source_aliases_json"]),
            equivalence_class=row["equivalence_class"],
            replacement_relation=row["replacement_relation"],
            display_name=row["display_name"],
            status=row["status"],
            trust_status=row["trust_status"],
            package_count=int(row["package_count"] or 0),
            metadata=_json_load_dict(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_package(self, row) -> CapabilityPackageRecord:
        return CapabilityPackageRecord(
            package_id=row["package_id"],
            donor_id=row["donor_id"],
            source_profile_id=row["source_profile_id"],
            canonical_package_id=row["canonical_package_id"],
            package_ref=row["package_ref"],
            package_version=row["package_version"],
            source_aliases=_json_load_list(row["source_aliases_json"]),
            equivalence_class=row["equivalence_class"],
            package_kind=row["package_kind"],
            status=row["status"],
            metadata=_json_load_dict(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_source_profile(self, row) -> CapabilitySourceProfileRecord:
        return CapabilitySourceProfileRecord(
            source_profile_id=row["source_profile_id"],
            source_kind=row["source_kind"],
            source_key=row["source_key"],
            source_lineage=row["source_lineage"],
            source_aliases=_json_load_list(row["source_aliases_json"]),
            display_name=row["display_name"],
            trust_posture=row["trust_posture"],
            active=bool(row["active"]),
            metadata=_json_load_dict(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_trust(self, row) -> CapabilityDonorTrustRecord:
        return CapabilityDonorTrustRecord(
            donor_id=row["donor_id"],
            source_profile_id=row["source_profile_id"],
            last_candidate_id=row["last_candidate_id"],
            last_package_id=row["last_package_id"],
            last_canonical_package_id=row["last_canonical_package_id"],
            trust_status=row["trust_status"],
            trial_success_count=int(row["trial_success_count"] or 0),
            trial_failure_count=int(row["trial_failure_count"] or 0),
            underperformance_count=int(row["underperformance_count"] or 0),
            rollback_count=int(row["rollback_count"] or 0),
            replacement_pressure_count=int(row["replacement_pressure_count"] or 0),
            retirement_count=int(row["retirement_count"] or 0),
            last_trial_verdict=row["last_trial_verdict"],
            last_decision_kind=row["last_decision_kind"],
            metadata=_json_load_dict(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
