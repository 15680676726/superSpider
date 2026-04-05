# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from typing import Any

from ..models_external_runtime import ExternalCapabilityRuntimeInstanceRecord
from ..store import SQLiteStateStore
from .base import BaseExternalCapabilityRuntimeRepository
from .sqlite_shared import _decode_json_list, _decode_json_mapping, _encode_json, _payload


class SqliteExternalCapabilityRuntimeRepository(BaseExternalCapabilityRuntimeRepository):
    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_runtime(self, runtime_id: str) -> ExternalCapabilityRuntimeInstanceRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM external_capability_runtime_instances WHERE runtime_id = ?",
                (runtime_id,),
            ).fetchone()
        return _external_runtime_from_row(row)

    def list_runtimes(
        self,
        *,
        capability_id: str | None = None,
        runtime_kind: str | None = None,
        scope_kind: str | None = None,
        status: str | None = None,
        owner_agent_id: str | None = None,
        session_mount_id: str | None = None,
        work_context_id: str | None = None,
        environment_ref: str | None = None,
        limit: int | None = None,
    ) -> list[ExternalCapabilityRuntimeInstanceRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        for field_name, value in (
            ("capability_id", capability_id),
            ("runtime_kind", runtime_kind),
            ("scope_kind", scope_kind),
            ("status", status),
            ("owner_agent_id", owner_agent_id),
            ("session_mount_id", session_mount_id),
            ("work_context_id", work_context_id),
            ("environment_ref", environment_ref),
        ):
            if value is None:
                continue
            clauses.append(f"{field_name} = ?")
            params.append(value)
        query = "SELECT * FROM external_capability_runtime_instances"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, created_at DESC"
        if isinstance(limit, int) and limit > 0:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [
            item
            for item in (_external_runtime_from_row(row) for row in rows)
            if item is not None
        ]

    def upsert_runtime(
        self,
        runtime: ExternalCapabilityRuntimeInstanceRecord,
    ) -> ExternalCapabilityRuntimeInstanceRecord:
        payload = _payload(runtime)
        payload["artifact_refs_json"] = _encode_json(runtime.artifact_refs)
        payload["metadata_json"] = _encode_json(runtime.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO external_capability_runtime_instances (
                    runtime_id,
                    capability_id,
                    runtime_kind,
                    scope_kind,
                    work_context_id,
                    owner_agent_id,
                    environment_ref,
                    session_mount_id,
                    status,
                    command,
                    cwd,
                    process_id,
                    port,
                    health_url,
                    lease_owner_ref,
                    continuity_policy,
                    retention_policy,
                    last_started_at,
                    last_ready_at,
                    last_stopped_at,
                    last_exit_code,
                    last_error,
                    latest_start_evidence_id,
                    latest_healthcheck_evidence_id,
                    latest_stop_evidence_id,
                    latest_recovery_evidence_id,
                    artifact_refs_json,
                    replay_pointer,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :runtime_id,
                    :capability_id,
                    :runtime_kind,
                    :scope_kind,
                    :work_context_id,
                    :owner_agent_id,
                    :environment_ref,
                    :session_mount_id,
                    :status,
                    :command,
                    :cwd,
                    :process_id,
                    :port,
                    :health_url,
                    :lease_owner_ref,
                    :continuity_policy,
                    :retention_policy,
                    :last_started_at,
                    :last_ready_at,
                    :last_stopped_at,
                    :last_exit_code,
                    :last_error,
                    :latest_start_evidence_id,
                    :latest_healthcheck_evidence_id,
                    :latest_stop_evidence_id,
                    :latest_recovery_evidence_id,
                    :artifact_refs_json,
                    :replay_pointer,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(runtime_id) DO UPDATE SET
                    capability_id = excluded.capability_id,
                    runtime_kind = excluded.runtime_kind,
                    scope_kind = excluded.scope_kind,
                    work_context_id = excluded.work_context_id,
                    owner_agent_id = excluded.owner_agent_id,
                    environment_ref = excluded.environment_ref,
                    session_mount_id = excluded.session_mount_id,
                    status = excluded.status,
                    command = excluded.command,
                    cwd = excluded.cwd,
                    process_id = excluded.process_id,
                    port = excluded.port,
                    health_url = excluded.health_url,
                    lease_owner_ref = excluded.lease_owner_ref,
                    continuity_policy = excluded.continuity_policy,
                    retention_policy = excluded.retention_policy,
                    last_started_at = excluded.last_started_at,
                    last_ready_at = excluded.last_ready_at,
                    last_stopped_at = excluded.last_stopped_at,
                    last_exit_code = excluded.last_exit_code,
                    last_error = excluded.last_error,
                    latest_start_evidence_id = excluded.latest_start_evidence_id,
                    latest_healthcheck_evidence_id = excluded.latest_healthcheck_evidence_id,
                    latest_stop_evidence_id = excluded.latest_stop_evidence_id,
                    latest_recovery_evidence_id = excluded.latest_recovery_evidence_id,
                    artifact_refs_json = excluded.artifact_refs_json,
                    replay_pointer = excluded.replay_pointer,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return runtime

    def delete_runtime(self, runtime_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM external_capability_runtime_instances WHERE runtime_id = ?",
                (runtime_id,),
            )
        return cursor.rowcount > 0


def _external_runtime_from_row(
    row: sqlite3.Row | None,
) -> ExternalCapabilityRuntimeInstanceRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["artifact_refs"] = _decode_json_list(payload.pop("artifact_refs_json", None)) or []
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return ExternalCapabilityRuntimeInstanceRecord.model_validate(payload)
