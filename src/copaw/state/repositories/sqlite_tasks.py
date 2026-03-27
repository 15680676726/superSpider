# -*- coding: utf-8 -*-
from __future__ import annotations

from .sqlite_shared import *  # noqa: F401,F403


class SqliteGoalRepository(BaseGoalRepository):
    """SQLite-backed goal repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_goal(self, goal_id: str) -> GoalRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM goals WHERE id = ?",
                (goal_id,),
            ).fetchone()
        return _model_from_row(GoalRecord, row)

    def list_goals(
        self,
        *,
        status: str | None = None,
        owner_scope: str | None = None,
        industry_instance_id: str | None = None,
        goal_ids: Sequence[str] | None = None,
        activity_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[GoalRecord]:
        clauses: list[str] = []
        params: list[Any] = []

        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if owner_scope is not None:
            clauses.append("owner_scope = ?")
            params.append(owner_scope)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if goal_ids:
            placeholders = ", ".join("?" for _ in goal_ids)
            clauses.append(f"id IN ({placeholders})")
            params.extend(goal_ids)
        if activity_since is not None:
            encoded = _encode_datetime_value(activity_since)
            clauses.append("(created_at >= ? OR updated_at >= ?)")
            params.extend([encoded, encoded])

        query = "SELECT * FROM goals"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)

        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [GoalRecord.model_validate(dict(row)) for row in rows]

    def upsert_goal(self, goal: GoalRecord) -> GoalRecord:
        payload = _payload(goal)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO goals (
                    id,
                    title,
                    summary,
                    status,
                    priority,
                    owner_scope,
                    industry_instance_id,
                    lane_id,
                    cycle_id,
                    goal_class,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :title,
                    :summary,
                    :status,
                    :priority,
                    :owner_scope,
                    :industry_instance_id,
                    :lane_id,
                    :cycle_id,
                    :goal_class,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    summary = excluded.summary,
                    status = excluded.status,
                    priority = excluded.priority,
                    owner_scope = excluded.owner_scope,
                    industry_instance_id = excluded.industry_instance_id,
                    lane_id = excluded.lane_id,
                    cycle_id = excluded.cycle_id,
                    goal_class = excluded.goal_class,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return goal

    def delete_goal(self, goal_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        return cursor.rowcount > 0


class SqliteTaskRepository(BaseTaskRepository):
    """SQLite-backed task repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        return _model_from_row(TaskRecord, row)

    def list_tasks(
        self,
        *,
        goal_id: str | None = None,
        industry_instance_id: str | None = None,
        assignment_id: str | None = None,
        lane_id: str | None = None,
        cycle_id: str | None = None,
        status: str | None = None,
        owner_agent_id: str | None = None,
        parent_task_id: str | None = None,
        work_context_id: str | None = None,
        task_type: str | None = None,
        goal_ids: Sequence[str] | None = None,
        assignment_ids: Sequence[str] | None = None,
        task_ids: Sequence[str] | None = None,
        owner_agent_ids: Sequence[str] | None = None,
        acceptance_criteria_like: str | None = None,
        activity_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[TaskRecord]:
        clauses: list[str] = []
        params: list[Any] = []

        if goal_id is not None:
            clauses.append("goal_id = ?")
            params.append(goal_id)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if assignment_id is not None:
            clauses.append("assignment_id = ?")
            params.append(assignment_id)
        if lane_id is not None:
            clauses.append("lane_id = ?")
            params.append(lane_id)
        if cycle_id is not None:
            clauses.append("cycle_id = ?")
            params.append(cycle_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        if parent_task_id is not None:
            clauses.append("parent_task_id = ?")
            params.append(parent_task_id)
        if work_context_id is not None:
            clauses.append("work_context_id = ?")
            params.append(work_context_id)
        if task_type is not None:
            clauses.append("task_type = ?")
            params.append(task_type)
        if goal_ids:
            placeholders = ", ".join("?" for _ in goal_ids)
            clauses.append(f"goal_id IN ({placeholders})")
            params.extend(goal_ids)
        if assignment_ids:
            placeholders = ", ".join("?" for _ in assignment_ids)
            clauses.append(f"assignment_id IN ({placeholders})")
            params.extend(assignment_ids)
        if task_ids:
            placeholders = ", ".join("?" for _ in task_ids)
            clauses.append(f"id IN ({placeholders})")
            params.extend(task_ids)
        if owner_agent_ids:
            placeholders = ", ".join("?" for _ in owner_agent_ids)
            clauses.append(f"owner_agent_id IN ({placeholders})")
            params.extend(owner_agent_ids)
        if acceptance_criteria_like:
            clauses.append("acceptance_criteria LIKE ?")
            params.append(f"%{acceptance_criteria_like}%")
        if activity_since is not None:
            encoded = _encode_datetime_value(activity_since)
            clauses.append("(created_at >= ? OR updated_at >= ?)")
            params.extend([encoded, encoded])

        query = "SELECT * FROM tasks"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, created_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)

        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [TaskRecord.model_validate(dict(row)) for row in rows]

    def upsert_task(self, task: TaskRecord) -> TaskRecord:
        payload = _payload(task)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    id,
                    goal_id,
                    title,
                    summary,
                    task_type,
                    status,
                    priority,
                    owner_agent_id,
                    parent_task_id,
                    work_context_id,
                    seed_source,
                    constraints_summary,
                    acceptance_criteria,
                    current_risk_level,
                    industry_instance_id,
                    assignment_id,
                    lane_id,
                    cycle_id,
                    report_back_mode,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :goal_id,
                    :title,
                    :summary,
                    :task_type,
                    :status,
                    :priority,
                    :owner_agent_id,
                    :parent_task_id,
                    :work_context_id,
                    :seed_source,
                    :constraints_summary,
                    :acceptance_criteria,
                    :current_risk_level,
                    :industry_instance_id,
                    :assignment_id,
                    :lane_id,
                    :cycle_id,
                    :report_back_mode,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    goal_id = excluded.goal_id,
                    title = excluded.title,
                    summary = excluded.summary,
                    task_type = excluded.task_type,
                    status = excluded.status,
                    priority = excluded.priority,
                    owner_agent_id = excluded.owner_agent_id,
                    parent_task_id = excluded.parent_task_id,
                    work_context_id = excluded.work_context_id,
                    seed_source = excluded.seed_source,
                    constraints_summary = excluded.constraints_summary,
                    acceptance_criteria = excluded.acceptance_criteria,
                    current_risk_level = excluded.current_risk_level,
                    industry_instance_id = excluded.industry_instance_id,
                    assignment_id = excluded.assignment_id,
                    lane_id = excluded.lane_id,
                    cycle_id = excluded.cycle_id,
                    report_back_mode = excluded.report_back_mode,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return task

    def delete_task(self, task_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cursor.rowcount > 0


class SqliteTaskRuntimeRepository(BaseTaskRuntimeRepository):
    """SQLite-backed task runtime repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_runtime(self, task_id: str) -> TaskRuntimeRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM task_runtimes WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return _model_from_row(TaskRuntimeRecord, row)

    def list_runtimes(
        self,
        *,
        runtime_status: str | None = None,
        risk_level: str | None = None,
        task_ids: Sequence[str] | None = None,
        last_owner_agent_ids: Sequence[str] | None = None,
        updated_since: datetime | None = None,
    ) -> list[TaskRuntimeRecord]:
        clauses: list[str] = []
        params: list[Any] = []

        if runtime_status is not None:
            clauses.append("runtime_status = ?")
            params.append(runtime_status)
        if risk_level is not None:
            clauses.append("risk_level = ?")
            params.append(risk_level)
        if task_ids:
            placeholders = ", ".join("?" for _ in task_ids)
            clauses.append(f"task_id IN ({placeholders})")
            params.extend(task_ids)
        if last_owner_agent_ids:
            placeholders = ", ".join("?" for _ in last_owner_agent_ids)
            clauses.append(f"last_owner_agent_id IN ({placeholders})")
            params.extend(last_owner_agent_ids)
        if updated_since is not None:
            clauses.append("updated_at >= ?")
            params.append(_encode_datetime_value(updated_since))

        query = "SELECT * FROM task_runtimes"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC"

        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [TaskRuntimeRecord.model_validate(dict(row)) for row in rows]

    def upsert_runtime(self, runtime: TaskRuntimeRecord) -> TaskRuntimeRecord:
        payload = _payload(runtime)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO task_runtimes (
                    task_id,
                    runtime_status,
                    current_phase,
                    risk_level,
                    active_environment_id,
                    last_result_summary,
                    last_error_summary,
                    last_owner_agent_id,
                    last_evidence_id,
                    updated_at
                ) VALUES (
                    :task_id,
                    :runtime_status,
                    :current_phase,
                    :risk_level,
                    :active_environment_id,
                    :last_result_summary,
                    :last_error_summary,
                    :last_owner_agent_id,
                    :last_evidence_id,
                    :updated_at
                )
                ON CONFLICT(task_id) DO UPDATE SET
                    runtime_status = excluded.runtime_status,
                    current_phase = excluded.current_phase,
                    risk_level = excluded.risk_level,
                    active_environment_id = excluded.active_environment_id,
                    last_result_summary = excluded.last_result_summary,
                    last_error_summary = excluded.last_error_summary,
                    last_owner_agent_id = excluded.last_owner_agent_id,
                    last_evidence_id = excluded.last_evidence_id,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return runtime

    def delete_runtime(self, task_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM task_runtimes WHERE task_id = ?",
                (task_id,),
            )
        return cursor.rowcount > 0


class SqliteRuntimeFrameRepository(BaseRuntimeFrameRepository):
    """SQLite-backed runtime frame repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_frame(self, frame_id: str) -> RuntimeFrameRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM runtime_frames WHERE id = ?",
                (frame_id,),
            ).fetchone()
        return _model_from_row(RuntimeFrameRecord, row)

    def list_frames(
        self,
        task_id: str,
        *,
        limit: int | None = None,
    ) -> list[RuntimeFrameRecord]:
        query = (
            "SELECT * FROM runtime_frames WHERE task_id = ? "
            "ORDER BY created_at DESC"
        )
        params: list[Any] = [task_id]
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)

        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [RuntimeFrameRecord.model_validate(dict(row)) for row in rows]

    def append_frame(self, frame: RuntimeFrameRecord) -> RuntimeFrameRecord:
        payload = _payload(frame)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO runtime_frames (
                    id,
                    task_id,
                    goal_summary,
                    owner_agent_id,
                    current_phase,
                    current_risk_level,
                    environment_summary,
                    evidence_summary,
                    constraints_summary,
                    capabilities_summary,
                    pending_decisions_summary,
                    budget_summary,
                    created_at
                ) VALUES (
                    :id,
                    :task_id,
                    :goal_summary,
                    :owner_agent_id,
                    :current_phase,
                    :current_risk_level,
                    :environment_summary,
                    :evidence_summary,
                    :constraints_summary,
                    :capabilities_summary,
                    :pending_decisions_summary,
                    :budget_summary,
                    :created_at
                )
                """,
                payload,
            )
        return frame

    def delete_frame(self, frame_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM runtime_frames WHERE id = ?",
                (frame_id,),
            )
        return cursor.rowcount > 0


class SqliteScheduleRepository(BaseScheduleRepository):
    """SQLite-backed schedule projection repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_schedule(self, schedule_id: str) -> ScheduleRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM schedules WHERE id = ?",
                (schedule_id,),
            ).fetchone()
        return _schedule_from_row(row)

    def list_schedules(
        self,
        *,
        status: str | None = None,
        enabled: bool | None = None,
        limit: int | None = None,
    ) -> list[ScheduleRecord]:
        clauses: list[str] = []
        params: list[Any] = []

        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if enabled is not None:
            clauses.append("enabled = ?")
            params.append(int(enabled))

        query = "SELECT * FROM schedules"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)

        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_schedule_from_row(row) for row in rows]

    def upsert_schedule(self, schedule: ScheduleRecord) -> ScheduleRecord:
        payload = _payload(schedule)
        payload["enabled"] = int(schedule.enabled)
        payload["spec_payload_json"] = _encode_json(schedule.spec_payload)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO schedules (
                    id,
                    title,
                    cron,
                    timezone,
                    status,
                    enabled,
                    task_type,
                    target_channel,
                    target_user_id,
                    target_session_id,
                    last_run_at,
                    next_run_at,
                    last_error,
                    source_ref,
                    spec_payload_json,
                    schedule_kind,
                    trigger_target,
                    lane_id,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :title,
                    :cron,
                    :timezone,
                    :status,
                    :enabled,
                    :task_type,
                    :target_channel,
                    :target_user_id,
                    :target_session_id,
                    :last_run_at,
                    :next_run_at,
                    :last_error,
                    :source_ref,
                    :spec_payload_json,
                    :schedule_kind,
                    :trigger_target,
                    :lane_id,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    cron = excluded.cron,
                    timezone = excluded.timezone,
                    status = excluded.status,
                    enabled = excluded.enabled,
                    task_type = excluded.task_type,
                    target_channel = excluded.target_channel,
                    target_user_id = excluded.target_user_id,
                    target_session_id = excluded.target_session_id,
                    last_run_at = excluded.last_run_at,
                    next_run_at = excluded.next_run_at,
                    last_error = excluded.last_error,
                    source_ref = excluded.source_ref,
                    spec_payload_json = excluded.spec_payload_json,
                    schedule_kind = excluded.schedule_kind,
                    trigger_target = excluded.trigger_target,
                    lane_id = excluded.lane_id,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return schedule

    def delete_schedule(self, schedule_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM schedules WHERE id = ?",
                (schedule_id,),
            )
        return cursor.rowcount > 0


def _schedule_from_row(row: sqlite3.Row | None) -> ScheduleRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["enabled"] = bool(payload.get("enabled", 1))
    payload["spec_payload"] = _decode_json(payload.pop("spec_payload_json", "{}"))
    return ScheduleRecord.model_validate(payload)
