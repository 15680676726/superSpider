# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sqlite3
import threading
from collections import defaultdict
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from .artifacts import bind_evidence_links
from .models import ArtifactRecord, EvidenceRecord, ReplayPointer


class EvidenceLedger:
    def __init__(
        self,
        database_path: str | Path | None = None,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        if connection is not None and database_path is not None:
            raise ValueError(
                "Pass either database_path or connection, not both.",
            )

        sqlite_target = ":memory:"
        if connection is None and database_path is not None:
            sqlite_target = str(database_path)
            if sqlite_target != ":memory:":
                Path(sqlite_target).expanduser().parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

        self._owns_connection = connection is None
        self._connection = connection or sqlite3.connect(
            sqlite_target,
            check_same_thread=False,
        )
        self._lock = threading.RLock()
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._init_schema()

    def close(self) -> None:
        if self._owns_connection:
            with self._lock:
                self._connection.close()

    def __enter__(self) -> "EvidenceLedger":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def append(
        self,
        record: EvidenceRecord,
        *,
        artifacts: Sequence[ArtifactRecord] | None = None,
        replay_pointers: Sequence[ReplayPointer] | None = None,
    ) -> EvidenceRecord:
        persisted_record = record.materialize()
        linked_artifacts, linked_replays = bind_evidence_links(
            persisted_record.id,
            artifacts=record.artifacts if artifacts is None else artifacts,
            replay_pointers=(
                record.replay_pointers
                if replay_pointers is None
                else replay_pointers
            ),
        )
        persisted_record = replace(
            persisted_record,
            artifacts=linked_artifacts,
            replay_pointers=linked_replays,
        )

        with self._lock:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO evidence_records (
                        id,
                        kind,
                        task_id,
                        actor_ref,
                        environment_ref,
                        capability_ref,
                        risk_level,
                        action_summary,
                        result_summary,
                        created_at,
                        status,
                        input_digest,
                        output_digest,
                        metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        persisted_record.id,
                        persisted_record.kind,
                        persisted_record.task_id,
                        persisted_record.actor_ref,
                        persisted_record.environment_ref,
                        persisted_record.capability_ref,
                        persisted_record.risk_level,
                        persisted_record.action_summary,
                        persisted_record.result_summary,
                        _encode_datetime(persisted_record.created_at),
                        persisted_record.status,
                        persisted_record.input_digest,
                        persisted_record.output_digest,
                        _encode_json(persisted_record.metadata),
                    ),
                )
                self._connection.executemany(
                    """
                    INSERT INTO artifact_records (
                        id,
                        evidence_id,
                        artifact_type,
                        storage_uri,
                        summary,
                        created_at,
                        metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            artifact.id,
                            artifact.evidence_id,
                            artifact.artifact_type,
                            artifact.storage_uri,
                            artifact.summary,
                            _encode_datetime(artifact.created_at),
                            _encode_json(artifact.metadata),
                        )
                        for artifact in linked_artifacts
                    ],
                )
                self._connection.executemany(
                    """
                    INSERT INTO replay_pointers (
                        id,
                        evidence_id,
                        replay_type,
                        storage_uri,
                        summary,
                        created_at,
                        metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            replay_pointer.id,
                            replay_pointer.evidence_id,
                            replay_pointer.replay_type,
                            replay_pointer.storage_uri,
                            replay_pointer.summary,
                            _encode_datetime(replay_pointer.created_at),
                            _encode_json(replay_pointer.metadata),
                        )
                        for replay_pointer in linked_replays
                    ],
                )

        return persisted_record

    def list_by_task(self, task_id: str) -> list[EvidenceRecord]:
        with self._lock:
            evidence_rows = self._connection.execute(
                """
                SELECT *
                FROM evidence_records
                WHERE task_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (task_id,),
            ).fetchall()
        if not evidence_rows:
            return []

        evidence_ids = [row["id"] for row in evidence_rows]
        artifacts_by_evidence = self._load_artifacts(evidence_ids)
        replays_by_evidence = self._load_replays(evidence_ids)

        return [
            EvidenceRecord(
                id=row["id"],
                kind=_row_kind(row),
                task_id=row["task_id"],
                actor_ref=row["actor_ref"],
                environment_ref=row["environment_ref"],
                capability_ref=row["capability_ref"],
                risk_level=row["risk_level"],
                action_summary=row["action_summary"],
                result_summary=row["result_summary"],
                created_at=_decode_datetime(row["created_at"]),
                status=row["status"],
                input_digest=row["input_digest"],
                output_digest=row["output_digest"],
                metadata=_decode_json(row["metadata_json"]),
                artifacts=artifacts_by_evidence[row["id"]],
                replay_pointers=replays_by_evidence[row["id"]],
            )
            for row in evidence_rows
        ]

    def query_by_task(self, task_id: str) -> list[EvidenceRecord]:
        return self.list_by_task(task_id)

    def list_recent(self, *, limit: int = 5) -> list[EvidenceRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM evidence_records
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        evidence_ids = [row["id"] for row in rows]
        artifacts_by_evidence = self._load_artifacts(evidence_ids)
        replays_by_evidence = self._load_replays(evidence_ids)
        return [
            EvidenceRecord(
                id=row["id"],
                kind=_row_kind(row),
                task_id=row["task_id"],
                actor_ref=row["actor_ref"],
                environment_ref=row["environment_ref"],
                capability_ref=row["capability_ref"],
                risk_level=row["risk_level"],
                action_summary=row["action_summary"],
                result_summary=row["result_summary"],
                created_at=_decode_datetime(row["created_at"]),
                status=row["status"],
                input_digest=row["input_digest"],
                output_digest=row["output_digest"],
                metadata=_decode_json(row["metadata_json"]),
                artifacts=artifacts_by_evidence.get(row["id"], ()),
                replay_pointers=replays_by_evidence.get(row["id"], ()),
            )
            for row in rows
        ]

    def list_records(
        self,
        *,
        limit: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        task_ids: Sequence[str] | None = None,
        actor_refs: Sequence[str] | None = None,
        status: str | None = None,
    ) -> list[EvidenceRecord]:
        """List evidence records with optional filters."""

        clauses: list[str] = []
        params: list[Any] = []

        if since is not None:
            clauses.append("created_at >= ?")
            params.append(_encode_datetime(since))
        if until is not None:
            clauses.append("created_at <= ?")
            params.append(_encode_datetime(until))
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if task_ids:
            placeholders = ", ".join("?" for _ in task_ids)
            clauses.append(f"task_id IN ({placeholders})")
            params.extend(task_ids)
        if actor_refs:
            placeholders = ", ".join("?" for _ in actor_refs)
            clauses.append(f"actor_ref IN ({placeholders})")
            params.extend(actor_refs)

        query = "SELECT * FROM evidence_records"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY created_at DESC, rowid DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)

        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        evidence_ids = [row["id"] for row in rows]
        artifacts_by_evidence = self._load_artifacts(evidence_ids)
        replays_by_evidence = self._load_replays(evidence_ids)
        return [
            EvidenceRecord(
                id=row["id"],
                kind=_row_kind(row),
                task_id=row["task_id"],
                actor_ref=row["actor_ref"],
                environment_ref=row["environment_ref"],
                capability_ref=row["capability_ref"],
                risk_level=row["risk_level"],
                action_summary=row["action_summary"],
                result_summary=row["result_summary"],
                created_at=_decode_datetime(row["created_at"]),
                status=row["status"],
                input_digest=row["input_digest"],
                output_digest=row["output_digest"],
                metadata=_decode_json(row["metadata_json"]),
                artifacts=artifacts_by_evidence.get(row["id"], ()),
                replay_pointers=replays_by_evidence.get(row["id"], ()),
            )
            for row in rows
        ]

    def count_records(self) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS count FROM evidence_records",
            ).fetchone()
        return int(row["count"] if row is not None else 0)

    def get_record(self, evidence_id: str) -> EvidenceRecord | None:
        """Fetch a single evidence record by its ID."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM evidence_records WHERE id = ?",
                (evidence_id,),
            ).fetchone()
        if row is None:
            return None
        artifacts = self._load_artifacts([evidence_id])
        replays = self._load_replays([evidence_id])
        return EvidenceRecord(
            id=row["id"],
            kind=_row_kind(row),
            task_id=row["task_id"],
            actor_ref=row["actor_ref"],
            environment_ref=row["environment_ref"],
            capability_ref=row["capability_ref"],
            risk_level=row["risk_level"],
            action_summary=row["action_summary"],
            result_summary=row["result_summary"],
            created_at=_decode_datetime(row["created_at"]),
            status=row["status"],
            input_digest=row["input_digest"],
            output_digest=row["output_digest"],
            metadata=_decode_json(row["metadata_json"]),
            artifacts=artifacts.get(evidence_id, ()),
            replay_pointers=replays.get(evidence_id, ()),
        )

    def delete_record(self, evidence_id: str) -> bool:
        normalized_evidence_id = evidence_id.strip() if isinstance(evidence_id, str) else ""
        if not normalized_evidence_id:
            return False
        with self._lock:
            with self._connection:
                cursor = self._connection.execute(
                    "DELETE FROM evidence_records WHERE id = ?",
                    (normalized_evidence_id,),
                )
        return int(cursor.rowcount or 0) > 0

    def delete_records(
        self,
        *,
        evidence_ids: Sequence[str] | None = None,
        task_ids: Sequence[str] | None = None,
    ) -> int:
        normalized_evidence_ids = [
            evidence_id.strip()
            for evidence_id in evidence_ids or ()
            if isinstance(evidence_id, str) and evidence_id.strip()
        ]
        normalized_task_ids = [
            task_id.strip()
            for task_id in task_ids or ()
            if isinstance(task_id, str) and task_id.strip()
        ]
        if not normalized_evidence_ids and not normalized_task_ids:
            return 0

        clauses: list[str] = []
        params: list[Any] = []
        if normalized_evidence_ids:
            placeholders = ", ".join("?" for _ in normalized_evidence_ids)
            clauses.append(f"id IN ({placeholders})")
            params.extend(normalized_evidence_ids)
        if normalized_task_ids:
            placeholders = ", ".join("?" for _ in normalized_task_ids)
            clauses.append(f"task_id IN ({placeholders})")
            params.extend(normalized_task_ids)

        with self._lock:
            rows = self._connection.execute(
                f"SELECT id FROM evidence_records WHERE {' OR '.join(clauses)}",
                params,
            ).fetchall()
        resolved_ids = [row["id"] for row in rows]
        if not resolved_ids:
            return 0

        placeholders = ", ".join("?" for _ in resolved_ids)
        with self._lock:
            with self._connection:
                cursor = self._connection.execute(
                    f"DELETE FROM evidence_records WHERE id IN ({placeholders})",
                    resolved_ids,
                )
        return int(cursor.rowcount or 0)

    def get_artifact_record(self, artifact_id: str) -> ArtifactRecord | None:
        """Fetch a single artifact record by its ID."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM artifact_records WHERE id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            return None
        return ArtifactRecord(
            id=row["id"],
            evidence_id=row["evidence_id"],
            artifact_type=row["artifact_type"],
            storage_uri=row["storage_uri"],
            summary=row["summary"],
            created_at=_decode_datetime(row["created_at"]),
            metadata=_decode_json(row["metadata_json"]),
        )

    def list_artifact_records_by_environment_ref(
        self,
        environment_ref: str,
        *,
        limit: int = 20,
    ) -> list[ArtifactRecord]:
        """List artifact records linked to evidence for an environment."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT artifact_records.*
                FROM artifact_records
                INNER JOIN evidence_records
                    ON evidence_records.id = artifact_records.evidence_id
                WHERE evidence_records.environment_ref = ?
                ORDER BY artifact_records.created_at DESC, artifact_records.rowid DESC
                LIMIT ?
                """,
                (environment_ref, limit),
            ).fetchall()
        return [
            ArtifactRecord(
                id=row["id"],
                evidence_id=row["evidence_id"],
                artifact_type=row["artifact_type"],
                storage_uri=row["storage_uri"],
                summary=row["summary"],
                created_at=_decode_datetime(row["created_at"]),
                metadata=_decode_json(row["metadata_json"]),
            )
            for row in rows
        ]

    def get_replay_pointer(self, replay_id: str) -> ReplayPointer | None:
        """Fetch a single replay pointer by its ID."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM replay_pointers WHERE id = ?",
                (replay_id,),
            ).fetchone()
        if row is None:
            return None
        return ReplayPointer(
            id=row["id"],
            evidence_id=row["evidence_id"],
            replay_type=row["replay_type"],
            storage_uri=row["storage_uri"],
            summary=row["summary"],
            created_at=_decode_datetime(row["created_at"]),
            metadata=_decode_json(row["metadata_json"]),
        )

    def list_replay_pointers_by_environment_ref(
        self,
        environment_ref: str,
        *,
        limit: int = 20,
    ) -> list[ReplayPointer]:
        """List replay pointers linked to evidence for an environment."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT replay_pointers.*
                FROM replay_pointers
                INNER JOIN evidence_records
                    ON evidence_records.id = replay_pointers.evidence_id
                WHERE evidence_records.environment_ref = ?
                ORDER BY replay_pointers.created_at DESC, replay_pointers.rowid DESC
                LIMIT ?
                """,
                (environment_ref, limit),
            ).fetchall()
        return [
            ReplayPointer(
                id=row["id"],
                evidence_id=row["evidence_id"],
                replay_type=row["replay_type"],
                storage_uri=row["storage_uri"],
                summary=row["summary"],
                created_at=_decode_datetime(row["created_at"]),
                metadata=_decode_json(row["metadata_json"]),
            )
            for row in rows
        ]

    def list_by_capability_ref(
        self,
        capability_ref: str,
        *,
        limit: int = 20,
    ) -> list[EvidenceRecord]:
        """List evidence records filtered by capability_ref."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM evidence_records
                WHERE capability_ref = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (capability_ref, limit),
            ).fetchall()
        evidence_ids = [row["id"] for row in rows]
        artifacts_by_evidence = self._load_artifacts(evidence_ids)
        replays_by_evidence = self._load_replays(evidence_ids)
        return [
            EvidenceRecord(
                id=row["id"],
                kind=_row_kind(row),
                task_id=row["task_id"],
                actor_ref=row["actor_ref"],
                environment_ref=row["environment_ref"],
                capability_ref=row["capability_ref"],
                risk_level=row["risk_level"],
                action_summary=row["action_summary"],
                result_summary=row["result_summary"],
                created_at=_decode_datetime(row["created_at"]),
                status=row["status"],
                input_digest=row["input_digest"],
                output_digest=row["output_digest"],
                metadata=_decode_json(row["metadata_json"]),
                artifacts=artifacts_by_evidence.get(row["id"], ()),
                replay_pointers=replays_by_evidence.get(row["id"], ()),
            )
            for row in rows
        ]

    def list_by_environment_ref(
        self,
        environment_ref: str,
        *,
        limit: int = 20,
    ) -> list[EvidenceRecord]:
        """List evidence records filtered by environment_ref."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM evidence_records
                WHERE environment_ref = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (environment_ref, limit),
            ).fetchall()
        evidence_ids = [row["id"] for row in rows]
        artifacts_by_evidence = self._load_artifacts(evidence_ids)
        replays_by_evidence = self._load_replays(evidence_ids)
        return [
            EvidenceRecord(
                id=row["id"],
                kind=_row_kind(row),
                task_id=row["task_id"],
                actor_ref=row["actor_ref"],
                environment_ref=row["environment_ref"],
                capability_ref=row["capability_ref"],
                risk_level=row["risk_level"],
                action_summary=row["action_summary"],
                result_summary=row["result_summary"],
                created_at=_decode_datetime(row["created_at"]),
                status=row["status"],
                input_digest=row["input_digest"],
                output_digest=row["output_digest"],
                metadata=_decode_json(row["metadata_json"]),
                artifacts=artifacts_by_evidence.get(row["id"], ()),
                replay_pointers=replays_by_evidence.get(row["id"], ()),
            )
            for row in rows
        ]

    def count_by_capability_ref(self) -> dict[str, int]:
        """Return evidence count distribution by capability_ref."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT COALESCE(capability_ref, 'unknown') AS cap_ref,
                       COUNT(*) AS count
                FROM evidence_records
                GROUP BY cap_ref
                ORDER BY count DESC
                """,
            ).fetchall()
        return {row["cap_ref"]: int(row["count"]) for row in rows}

    def _init_schema(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS evidence_records (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL DEFAULT 'generic',
                    task_id TEXT NOT NULL,
                    actor_ref TEXT NOT NULL,
                    environment_ref TEXT,
                    capability_ref TEXT,
                    risk_level TEXT NOT NULL,
                    action_summary TEXT NOT NULL,
                    result_summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_digest TEXT,
                    output_digest TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_evidence_records_task_id
                ON evidence_records (task_id, created_at);

                CREATE INDEX IF NOT EXISTS idx_evidence_records_environment_ref
                ON evidence_records (environment_ref, created_at);

                CREATE TABLE IF NOT EXISTS artifact_records (
                    id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    storage_uri TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (evidence_id)
                        REFERENCES evidence_records (id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_artifact_records_evidence_id
                ON artifact_records (evidence_id, created_at);

                CREATE TABLE IF NOT EXISTS replay_pointers (
                    id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL,
                    replay_type TEXT NOT NULL,
                    storage_uri TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (evidence_id)
                        REFERENCES evidence_records (id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_replay_pointers_evidence_id
                ON replay_pointers (evidence_id, created_at);
                """,
            )
            self._ensure_column(
                "evidence_records",
                "kind",
                "TEXT NOT NULL DEFAULT 'generic'",
            )

    def _ensure_column(
        self,
        table_name: str,
        column_name: str,
        column_sql: str,
    ) -> None:
        existing_columns = {
            str(row["name"] or "")
            for row in self._connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in existing_columns:
            return
        self._connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}",
        )

    def _load_artifacts(
        self,
        evidence_ids: Sequence[str],
    ) -> dict[str, tuple[ArtifactRecord, ...]]:
        if not evidence_ids:
            return {}

        placeholders = ", ".join("?" for _ in evidence_ids)
        with self._lock:
            rows = self._connection.execute(
                f"""
                SELECT *
                FROM artifact_records
                WHERE evidence_id IN ({placeholders})
                ORDER BY created_at ASC, rowid ASC
                """,
                tuple(evidence_ids),
            ).fetchall()

        artifacts_by_evidence: dict[str, list[ArtifactRecord]] = defaultdict(list)
        for row in rows:
            artifacts_by_evidence[row["evidence_id"]].append(
                ArtifactRecord(
                    id=row["id"],
                    evidence_id=row["evidence_id"],
                    artifact_type=row["artifact_type"],
                    storage_uri=row["storage_uri"],
                    summary=row["summary"],
                    created_at=_decode_datetime(row["created_at"]),
                    metadata=_decode_json(row["metadata_json"]),
                ),
            )

        return {
            evidence_id: tuple(artifacts_by_evidence.get(evidence_id, []))
            for evidence_id in evidence_ids
        }

    def _load_replays(
        self,
        evidence_ids: Sequence[str],
    ) -> dict[str, tuple[ReplayPointer, ...]]:
        if not evidence_ids:
            return {}

        placeholders = ", ".join("?" for _ in evidence_ids)
        with self._lock:
            rows = self._connection.execute(
                f"""
                SELECT *
                FROM replay_pointers
                WHERE evidence_id IN ({placeholders})
                ORDER BY created_at ASC, rowid ASC
                """,
                tuple(evidence_ids),
            ).fetchall()

        replays_by_evidence: dict[str, list[ReplayPointer]] = defaultdict(list)
        for row in rows:
            replays_by_evidence[row["evidence_id"]].append(
                ReplayPointer(
                    id=row["id"],
                    evidence_id=row["evidence_id"],
                    replay_type=row["replay_type"],
                    storage_uri=row["storage_uri"],
                    summary=row["summary"],
                    created_at=_decode_datetime(row["created_at"]),
                    metadata=_decode_json(row["metadata_json"]),
                ),
            )

        return {
            evidence_id: tuple(replays_by_evidence.get(evidence_id, []))
            for evidence_id in evidence_ids
        }


def _encode_datetime(value) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _decode_datetime(value: str):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _encode_json(value: Any) -> str:
    return json.dumps(value or {}, sort_keys=True)


def _decode_json(value: str) -> dict[str, Any]:
    payload = json.loads(value or "{}")
    return payload if isinstance(payload, dict) else {"value": payload}


def _row_kind(row: sqlite3.Row) -> str:
    try:
        normalized = str(row["kind"] or "").strip()
    except Exception:
        normalized = ""
    return normalized or "generic"
