# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from typing import Any

from ..models_surface_learning import (
    SurfaceCapabilityTwinRecord,
    SurfacePlaybookRecord,
)
from ..store import SQLiteStateStore
from .base import BaseSurfaceCapabilityTwinRepository, BaseSurfacePlaybookRepository
from .sqlite_shared import _decode_json_list, _decode_json_mapping, _encode_json, _payload

_SURFACE_TWIN_COLUMNS = (
    "twin_id",
    "scope_level",
    "scope_id",
    "capability_name",
    "capability_kind",
    "surface_kind",
    "summary",
    "entry_conditions_json",
    "entry_regions_json",
    "required_state_signals_json",
    "probe_steps_json",
    "execution_steps_json",
    "result_signals_json",
    "failure_modes_json",
    "risk_level",
    "evidence_refs_json",
    "source_transition_refs_json",
    "source_discovery_refs_json",
    "version",
    "status",
    "metadata_json",
    "created_at",
    "updated_at",
)
_SURFACE_PLAYBOOK_COLUMNS = (
    "playbook_id",
    "twin_id",
    "scope_level",
    "scope_id",
    "summary",
    "capability_names_json",
    "recommended_steps_json",
    "probe_steps_json",
    "execution_steps_json",
    "success_signals_json",
    "blocker_signals_json",
    "evidence_refs_json",
    "version",
    "status",
    "metadata_json",
    "created_at",
    "updated_at",
)


def _surface_twin_from_row(row: sqlite3.Row | None) -> SurfaceCapabilityTwinRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["entry_conditions"] = _decode_json_list(payload.pop("entry_conditions_json", None)) or []
    payload["entry_regions"] = _decode_json_list(payload.pop("entry_regions_json", None)) or []
    payload["required_state_signals"] = (
        _decode_json_list(payload.pop("required_state_signals_json", None)) or []
    )
    payload["probe_steps"] = _decode_json_list(payload.pop("probe_steps_json", None)) or []
    payload["execution_steps"] = _decode_json_list(payload.pop("execution_steps_json", None)) or []
    payload["result_signals"] = _decode_json_list(payload.pop("result_signals_json", None)) or []
    payload["failure_modes"] = _decode_json_list(payload.pop("failure_modes_json", None)) or []
    payload["evidence_refs"] = _decode_json_list(payload.pop("evidence_refs_json", None)) or []
    payload["source_transition_refs"] = (
        _decode_json_list(payload.pop("source_transition_refs_json", None)) or []
    )
    payload["source_discovery_refs"] = (
        _decode_json_list(payload.pop("source_discovery_refs_json", None)) or []
    )
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return SurfaceCapabilityTwinRecord.model_validate(payload)


def _surface_playbook_from_row(row: sqlite3.Row | None) -> SurfacePlaybookRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["capability_names"] = _decode_json_list(payload.pop("capability_names_json", None)) or []
    payload["recommended_steps"] = (
        _decode_json_list(payload.pop("recommended_steps_json", None)) or []
    )
    payload["probe_steps"] = _decode_json_list(payload.pop("probe_steps_json", None)) or []
    payload["execution_steps"] = _decode_json_list(payload.pop("execution_steps_json", None)) or []
    payload["success_signals"] = _decode_json_list(payload.pop("success_signals_json", None)) or []
    payload["blocker_signals"] = _decode_json_list(payload.pop("blocker_signals_json", None)) or []
    payload["evidence_refs"] = _decode_json_list(payload.pop("evidence_refs_json", None)) or []
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return SurfacePlaybookRecord.model_validate(payload)


class SqliteSurfaceCapabilityTwinRepository(BaseSurfaceCapabilityTwinRepository):
    """SQLite-backed repository for learned surface capability twins."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_twin(self, twin_id: str) -> SurfaceCapabilityTwinRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM surface_capability_twins WHERE twin_id = ?",
                (twin_id,),
            ).fetchone()
        return _surface_twin_from_row(row)

    def list_twins(
        self,
        *,
        scope_level: str | None = None,
        scope_id: str | None = None,
        capability_name: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[SurfaceCapabilityTwinRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        for field_name, value in (
            ("scope_level", scope_level),
            ("scope_id", scope_id),
            ("capability_name", capability_name),
            ("status", status),
        ):
            if value is None:
                continue
            clauses.append(f"{field_name} = ?")
            params.append(value)
        query = "SELECT * FROM surface_capability_twins"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = (
            f"{query} ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, "
            "version DESC, updated_at DESC, created_at DESC"
        )
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [record for record in (_surface_twin_from_row(row) for row in rows) if record is not None]

    def get_active_twins(
        self,
        *,
        scope_level: str,
        scope_id: str,
        limit: int | None = None,
    ) -> list[SurfaceCapabilityTwinRecord]:
        return self.list_twins(
            scope_level=scope_level,
            scope_id=scope_id,
            status="active",
            limit=limit,
        )

    def list_by_scope(
        self,
        *,
        scope_level: str,
        scope_id: str,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[SurfaceCapabilityTwinRecord]:
        return self.list_twins(
            scope_level=scope_level,
            scope_id=scope_id,
            status=status,
            limit=limit,
        )

    def upsert_twin(
        self,
        record: SurfaceCapabilityTwinRecord,
    ) -> SurfaceCapabilityTwinRecord:
        record = SurfaceCapabilityTwinRecord.model_validate(record.model_dump(mode="python"))
        payload = _payload(record)
        payload["entry_conditions_json"] = _encode_json(record.entry_conditions)
        payload["entry_regions_json"] = _encode_json(record.entry_regions)
        payload["required_state_signals_json"] = _encode_json(record.required_state_signals)
        payload["probe_steps_json"] = _encode_json(record.probe_steps)
        payload["execution_steps_json"] = _encode_json(record.execution_steps)
        payload["result_signals_json"] = _encode_json(record.result_signals)
        payload["failure_modes_json"] = _encode_json(record.failure_modes)
        payload["evidence_refs_json"] = _encode_json(record.evidence_refs)
        payload["source_transition_refs_json"] = _encode_json(record.source_transition_refs)
        payload["source_discovery_refs_json"] = _encode_json(record.source_discovery_refs)
        payload["metadata_json"] = _encode_json(record.metadata)
        with self._store.connection() as conn:
            if record.status == "active":
                conn.execute(
                    """
                    UPDATE surface_capability_twins
                    SET status = 'superseded',
                        updated_at = ?
                    WHERE scope_level = ?
                      AND scope_id = ?
                      AND capability_name = ?
                      AND twin_id != ?
                      AND status = 'active'
                    """,
                    (
                        payload["updated_at"],
                        record.scope_level,
                        record.scope_id,
                        record.capability_name,
                        record.twin_id,
                    ),
                )
            conn.execute(
                f"""
                INSERT INTO surface_capability_twins ({', '.join(_SURFACE_TWIN_COLUMNS)})
                VALUES ({', '.join(f':{column}' for column in _SURFACE_TWIN_COLUMNS)})
                ON CONFLICT(twin_id) DO UPDATE SET
                    scope_level = excluded.scope_level,
                    scope_id = excluded.scope_id,
                    capability_name = excluded.capability_name,
                    capability_kind = excluded.capability_kind,
                    surface_kind = excluded.surface_kind,
                    summary = excluded.summary,
                    entry_conditions_json = excluded.entry_conditions_json,
                    entry_regions_json = excluded.entry_regions_json,
                    required_state_signals_json = excluded.required_state_signals_json,
                    probe_steps_json = excluded.probe_steps_json,
                    execution_steps_json = excluded.execution_steps_json,
                    result_signals_json = excluded.result_signals_json,
                    failure_modes_json = excluded.failure_modes_json,
                    risk_level = excluded.risk_level,
                    evidence_refs_json = excluded.evidence_refs_json,
                    source_transition_refs_json = excluded.source_transition_refs_json,
                    source_discovery_refs_json = excluded.source_discovery_refs_json,
                    version = excluded.version,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
            row = conn.execute(
                "SELECT * FROM surface_capability_twins WHERE twin_id = ?",
                (record.twin_id,),
            ).fetchone()
        return _surface_twin_from_row(row) or record

    def upsert(
        self,
        record: SurfaceCapabilityTwinRecord,
    ) -> SurfaceCapabilityTwinRecord:
        return self.upsert_twin(record)


class SqliteSurfacePlaybookRepository(BaseSurfacePlaybookRepository):
    """SQLite-backed repository for active per-scope surface playbooks."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_playbook(self, playbook_id: str) -> SurfacePlaybookRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM surface_playbooks WHERE playbook_id = ?",
                (playbook_id,),
            ).fetchone()
        return _surface_playbook_from_row(row)

    def get_active_playbook(
        self,
        *,
        scope_level: str,
        scope_id: str,
    ) -> SurfacePlaybookRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM surface_playbooks
                WHERE scope_level = ? AND scope_id = ? AND status = 'active'
                ORDER BY version DESC, updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (scope_level, scope_id),
            ).fetchone()
        return _surface_playbook_from_row(row)

    def list_playbooks(
        self,
        *,
        scope_level: str | None = None,
        scope_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[SurfacePlaybookRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        for field_name, value in (
            ("scope_level", scope_level),
            ("scope_id", scope_id),
            ("status", status),
        ):
            if value is None:
                continue
            clauses.append(f"{field_name} = ?")
            params.append(value)
        query = "SELECT * FROM surface_playbooks"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = (
            f"{query} ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, "
            "version DESC, updated_at DESC, created_at DESC"
        )
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [record for record in (_surface_playbook_from_row(row) for row in rows) if record is not None]

    def list_by_scope(
        self,
        *,
        scope_level: str,
        scope_id: str,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[SurfacePlaybookRecord]:
        return self.list_playbooks(
            scope_level=scope_level,
            scope_id=scope_id,
            status=status,
            limit=limit,
        )

    def upsert_playbook(
        self,
        record: SurfacePlaybookRecord,
    ) -> SurfacePlaybookRecord:
        record = SurfacePlaybookRecord.model_validate(record.model_dump(mode="python"))
        payload = _payload(record)
        payload["capability_names_json"] = _encode_json(record.capability_names)
        payload["recommended_steps_json"] = _encode_json(record.recommended_steps)
        payload["probe_steps_json"] = _encode_json(record.probe_steps)
        payload["execution_steps_json"] = _encode_json(record.execution_steps)
        payload["success_signals_json"] = _encode_json(record.success_signals)
        payload["blocker_signals_json"] = _encode_json(record.blocker_signals)
        payload["evidence_refs_json"] = _encode_json(record.evidence_refs)
        payload["metadata_json"] = _encode_json(record.metadata)
        with self._store.connection() as conn:
            if record.status == "active":
                conn.execute(
                    """
                    UPDATE surface_playbooks
                    SET status = 'superseded',
                        updated_at = ?
                    WHERE scope_level = ?
                      AND scope_id = ?
                      AND playbook_id != ?
                      AND status = 'active'
                    """,
                    (
                        payload["updated_at"],
                        record.scope_level,
                        record.scope_id,
                        record.playbook_id,
                    ),
                )
            conn.execute(
                f"""
                INSERT INTO surface_playbooks ({', '.join(_SURFACE_PLAYBOOK_COLUMNS)})
                VALUES ({', '.join(f':{column}' for column in _SURFACE_PLAYBOOK_COLUMNS)})
                ON CONFLICT(playbook_id) DO UPDATE SET
                    twin_id = excluded.twin_id,
                    scope_level = excluded.scope_level,
                    scope_id = excluded.scope_id,
                    summary = excluded.summary,
                    capability_names_json = excluded.capability_names_json,
                    recommended_steps_json = excluded.recommended_steps_json,
                    probe_steps_json = excluded.probe_steps_json,
                    execution_steps_json = excluded.execution_steps_json,
                    success_signals_json = excluded.success_signals_json,
                    blocker_signals_json = excluded.blocker_signals_json,
                    evidence_refs_json = excluded.evidence_refs_json,
                    version = excluded.version,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
            row = conn.execute(
                "SELECT * FROM surface_playbooks WHERE playbook_id = ?",
                (record.playbook_id,),
            ).fetchone()
        return _surface_playbook_from_row(row) or record

    def upsert(
        self,
        record: SurfacePlaybookRecord,
    ) -> SurfacePlaybookRecord:
        return self.upsert_playbook(record)


__all__ = [
    "SqliteSurfaceCapabilityTwinRepository",
    "SqliteSurfacePlaybookRepository",
]
