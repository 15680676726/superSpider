# -*- coding: utf-8 -*-
from __future__ import annotations

from .sqlite_shared import *  # noqa: F401,F403


class SqliteAutomationLoopRuntimeRepository(BaseAutomationLoopRuntimeRepository):
    """SQLite-backed repository for durable automation loop snapshots."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_loop(self, automation_task_id: str) -> AutomationLoopRuntimeRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM automation_loop_runtimes WHERE automation_task_id = ?",
                (automation_task_id,),
            ).fetchone()
        return _model_from_row(AutomationLoopRuntimeRecord, row)

    def list_loops(
        self,
        *,
        owner_agent_id: str | None = None,
        health_status: str | None = None,
        limit: int | None = None,
    ) -> list[AutomationLoopRuntimeRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        if health_status is not None:
            clauses.append("health_status = ?")
            params.append(health_status)
        query = "SELECT * FROM automation_loop_runtimes"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC"
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            record
            for record in (
                _model_from_row(AutomationLoopRuntimeRecord, row)
                for row in rows
            )
            if record is not None
        ]

    def upsert_loop(
        self,
        loop: AutomationLoopRuntimeRecord,
    ) -> AutomationLoopRuntimeRecord:
        payload = _payload(loop)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO automation_loop_runtimes (
                    automation_task_id,
                    task_name,
                    capability_ref,
                    owner_agent_id,
                    interval_seconds,
                    coordinator_contract,
                    loop_phase,
                    health_status,
                    last_gate_reason,
                    last_result_phase,
                    last_result_summary,
                    last_error_summary,
                    last_task_id,
                    last_evidence_id,
                    submit_count,
                    consecutive_failures,
                    created_at,
                    updated_at
                ) VALUES (
                    :automation_task_id,
                    :task_name,
                    :capability_ref,
                    :owner_agent_id,
                    :interval_seconds,
                    :coordinator_contract,
                    :loop_phase,
                    :health_status,
                    :last_gate_reason,
                    :last_result_phase,
                    :last_result_summary,
                    :last_error_summary,
                    :last_task_id,
                    :last_evidence_id,
                    :submit_count,
                    :consecutive_failures,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(automation_task_id) DO UPDATE SET
                    task_name = excluded.task_name,
                    capability_ref = excluded.capability_ref,
                    owner_agent_id = excluded.owner_agent_id,
                    interval_seconds = excluded.interval_seconds,
                    coordinator_contract = excluded.coordinator_contract,
                    loop_phase = excluded.loop_phase,
                    health_status = excluded.health_status,
                    last_gate_reason = excluded.last_gate_reason,
                    last_result_phase = excluded.last_result_phase,
                    last_result_summary = excluded.last_result_summary,
                    last_error_summary = excluded.last_error_summary,
                    last_task_id = excluded.last_task_id,
                    last_evidence_id = excluded.last_evidence_id,
                    submit_count = excluded.submit_count,
                    consecutive_failures = excluded.consecutive_failures,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return loop

    def delete_loop(self, automation_task_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM automation_loop_runtimes WHERE automation_task_id = ?",
                (automation_task_id,),
            )
        return cursor.rowcount > 0
