# -*- coding: utf-8 -*-
from __future__ import annotations

from .sqlite_shared import *  # noqa: F401,F403


class SqliteIndustryInstanceRepository(BaseIndustryInstanceRepository):
    """SQLite-backed repository for formal industry instance records."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_instance(self, instance_id: str) -> IndustryInstanceRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM industry_instances WHERE instance_id = ?",
                (instance_id,),
            ).fetchone()
        return _industry_instance_from_row(row)

    def list_instances(
        self,
        *,
        owner_scope: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[IndustryInstanceRecord]:
        clauses: list[str] = []
        params: list[Any] = []

        if owner_scope is not None:
            clauses.append("owner_scope = ?")
            params.append(owner_scope)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)

        query = "SELECT * FROM industry_instances"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)

        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            instance
            for instance in (_industry_instance_from_row(row) for row in rows)
            if instance is not None
        ]

    def upsert_instance(
        self,
        instance: IndustryInstanceRecord,
    ) -> IndustryInstanceRecord:
        payload = _payload(instance)
        payload["profile_payload_json"] = _encode_json(instance.profile_payload)
        payload["team_payload_json"] = _encode_json(instance.team_payload)
        payload["execution_core_identity_payload_json"] = _encode_json(
            instance.execution_core_identity_payload,
        )
        payload["agent_ids_json"] = json.dumps(
            instance.agent_ids,
            ensure_ascii=False,
            sort_keys=True,
        )
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO industry_instances (
                    instance_id,
                    bootstrap_kind,
                    label,
                    summary,
                    owner_scope,
                    status,
                    profile_payload_json,
                    team_payload_json,
                    execution_core_identity_payload_json,
                    agent_ids_json,
                    lifecycle_status,
                    autonomy_status,
                    current_cycle_id,
                    next_cycle_due_at,
                    last_cycle_started_at,
                    created_at,
                    updated_at
                ) VALUES (
                    :instance_id,
                    :bootstrap_kind,
                    :label,
                    :summary,
                    :owner_scope,
                    :status,
                    :profile_payload_json,
                    :team_payload_json,
                    :execution_core_identity_payload_json,
                    :agent_ids_json,
                    :lifecycle_status,
                    :autonomy_status,
                    :current_cycle_id,
                    :next_cycle_due_at,
                    :last_cycle_started_at,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(instance_id) DO UPDATE SET
                    bootstrap_kind = excluded.bootstrap_kind,
                    label = excluded.label,
                    summary = excluded.summary,
                    owner_scope = excluded.owner_scope,
                    status = excluded.status,
                    profile_payload_json = excluded.profile_payload_json,
                    team_payload_json = excluded.team_payload_json,
                    execution_core_identity_payload_json = excluded.execution_core_identity_payload_json,
                    agent_ids_json = excluded.agent_ids_json,
                    lifecycle_status = excluded.lifecycle_status,
                    autonomy_status = excluded.autonomy_status,
                    current_cycle_id = excluded.current_cycle_id,
                    next_cycle_due_at = excluded.next_cycle_due_at,
                    last_cycle_started_at = excluded.last_cycle_started_at,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return instance

    def delete_instance(self, instance_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM industry_instances WHERE instance_id = ?",
                (instance_id,),
            )
        return cursor.rowcount > 0


class SqliteOperatingLaneRepository(BaseOperatingLaneRepository):
    """SQLite-backed repository for operating lanes."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_lane(self, lane_id: str) -> OperatingLaneRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM operating_lanes WHERE id = ?",
                (lane_id,),
            ).fetchone()
        return _operating_lane_from_row(row)

    def list_lanes(
        self,
        *,
        industry_instance_id: str | None = None,
        status: str | None = None,
        owner_agent_id: str | None = None,
        limit: int | None = None,
    ) -> list[OperatingLaneRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        query = "SELECT * FROM operating_lanes"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY priority DESC, updated_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            lane
            for lane in (_operating_lane_from_row(row) for row in rows)
            if lane is not None
        ]

    def upsert_lane(self, lane: OperatingLaneRecord) -> OperatingLaneRecord:
        payload = _payload(lane)
        payload["metadata_json"] = _encode_json(lane.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO operating_lanes (
                    id,
                    industry_instance_id,
                    lane_key,
                    title,
                    summary,
                    status,
                    owner_agent_id,
                    owner_role_id,
                    priority,
                    health_status,
                    source_ref,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :industry_instance_id,
                    :lane_key,
                    :title,
                    :summary,
                    :status,
                    :owner_agent_id,
                    :owner_role_id,
                    :priority,
                    :health_status,
                    :source_ref,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    industry_instance_id = excluded.industry_instance_id,
                    lane_key = excluded.lane_key,
                    title = excluded.title,
                    summary = excluded.summary,
                    status = excluded.status,
                    owner_agent_id = excluded.owner_agent_id,
                    owner_role_id = excluded.owner_role_id,
                    priority = excluded.priority,
                    health_status = excluded.health_status,
                    source_ref = excluded.source_ref,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return lane

    def delete_lane(self, lane_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM operating_lanes WHERE id = ?",
                (lane_id,),
            )
        return cursor.rowcount > 0


class SqliteBacklogItemRepository(BaseBacklogItemRepository):
    """SQLite-backed repository for main-brain backlog items."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_item(self, item_id: str) -> BacklogItemRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM backlog_items WHERE id = ?",
                (item_id,),
            ).fetchone()
        return _backlog_item_from_row(row)

    def list_items(
        self,
        *,
        industry_instance_id: str | None = None,
        lane_id: str | None = None,
        cycle_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[BacklogItemRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if lane_id is not None:
            clauses.append("lane_id = ?")
            params.append(lane_id)
        if cycle_id is not None:
            clauses.append("cycle_id = ?")
            params.append(cycle_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        query = "SELECT * FROM backlog_items"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY priority DESC, updated_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            item
            for item in (_backlog_item_from_row(row) for row in rows)
            if item is not None
        ]

    def upsert_item(self, item: BacklogItemRecord) -> BacklogItemRecord:
        payload = _payload(item)
        payload["evidence_ids_json"] = json.dumps(item.evidence_ids, sort_keys=True)
        payload["metadata_json"] = _encode_json(item.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO backlog_items (
                    id,
                    industry_instance_id,
                    lane_id,
                    cycle_id,
                    assignment_id,
                    goal_id,
                    title,
                    summary,
                    status,
                    priority,
                    source_kind,
                    source_ref,
                    evidence_ids_json,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :industry_instance_id,
                    :lane_id,
                    :cycle_id,
                    :assignment_id,
                    :goal_id,
                    :title,
                    :summary,
                    :status,
                    :priority,
                    :source_kind,
                    :source_ref,
                    :evidence_ids_json,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    industry_instance_id = excluded.industry_instance_id,
                    lane_id = excluded.lane_id,
                    cycle_id = excluded.cycle_id,
                    assignment_id = excluded.assignment_id,
                    goal_id = excluded.goal_id,
                    title = excluded.title,
                    summary = excluded.summary,
                    status = excluded.status,
                    priority = excluded.priority,
                    source_kind = excluded.source_kind,
                    source_ref = excluded.source_ref,
                    evidence_ids_json = excluded.evidence_ids_json,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return item

    def delete_item(self, item_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM backlog_items WHERE id = ?",
                (item_id,),
            )
        return cursor.rowcount > 0


class SqliteOperatingCycleRepository(BaseOperatingCycleRepository):
    """SQLite-backed repository for operating cycles."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_cycle(self, cycle_id: str) -> OperatingCycleRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM operating_cycles WHERE id = ?",
                (cycle_id,),
            ).fetchone()
        return _operating_cycle_from_row(row)

    def list_cycles(
        self,
        *,
        industry_instance_id: str | None = None,
        cycle_kind: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[OperatingCycleRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if cycle_kind is not None:
            clauses.append("cycle_kind = ?")
            params.append(cycle_kind)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        query = "SELECT * FROM operating_cycles"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, created_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            cycle
            for cycle in (_operating_cycle_from_row(row) for row in rows)
            if cycle is not None
        ]

    def upsert_cycle(self, cycle: OperatingCycleRecord) -> OperatingCycleRecord:
        payload = _payload(cycle)
        payload["focus_lane_ids_json"] = json.dumps(cycle.focus_lane_ids, sort_keys=True)
        payload["backlog_item_ids_json"] = json.dumps(
            cycle.backlog_item_ids,
            sort_keys=True,
        )
        payload["assignment_ids_json"] = json.dumps(
            cycle.assignment_ids,
            sort_keys=True,
        )
        payload["report_ids_json"] = json.dumps(cycle.report_ids, sort_keys=True)
        payload["metadata_json"] = _encode_json(cycle.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO operating_cycles (
                    id,
                    industry_instance_id,
                    cycle_kind,
                    title,
                    summary,
                    status,
                    source_ref,
                    started_at,
                    due_at,
                    completed_at,
                    focus_lane_ids_json,
                    backlog_item_ids_json,
                    assignment_ids_json,
                    report_ids_json,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :industry_instance_id,
                    :cycle_kind,
                    :title,
                    :summary,
                    :status,
                    :source_ref,
                    :started_at,
                    :due_at,
                    :completed_at,
                    :focus_lane_ids_json,
                    :backlog_item_ids_json,
                    :assignment_ids_json,
                    :report_ids_json,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    industry_instance_id = excluded.industry_instance_id,
                    cycle_kind = excluded.cycle_kind,
                    title = excluded.title,
                    summary = excluded.summary,
                    status = excluded.status,
                    source_ref = excluded.source_ref,
                    started_at = excluded.started_at,
                    due_at = excluded.due_at,
                    completed_at = excluded.completed_at,
                    focus_lane_ids_json = excluded.focus_lane_ids_json,
                    backlog_item_ids_json = excluded.backlog_item_ids_json,
                    assignment_ids_json = excluded.assignment_ids_json,
                    report_ids_json = excluded.report_ids_json,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return cycle

    def delete_cycle(self, cycle_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM operating_cycles WHERE id = ?",
                (cycle_id,),
            )
        return cursor.rowcount > 0


class SqliteAssignmentRepository(BaseAssignmentRepository):
    """SQLite-backed repository for assignment records."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_assignment(self, assignment_id: str) -> AssignmentRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM assignments WHERE id = ?",
                (assignment_id,),
            ).fetchone()
        return _assignment_from_row(row)

    def list_assignments(
        self,
        *,
        industry_instance_id: str | None = None,
        cycle_id: str | None = None,
        lane_id: str | None = None,
        goal_id: str | None = None,
        owner_agent_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[AssignmentRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if cycle_id is not None:
            clauses.append("cycle_id = ?")
            params.append(cycle_id)
        if lane_id is not None:
            clauses.append("lane_id = ?")
            params.append(lane_id)
        if goal_id is not None:
            clauses.append("goal_id = ?")
            params.append(goal_id)
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        query = "SELECT * FROM assignments"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, created_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            assignment
            for assignment in (_assignment_from_row(row) for row in rows)
            if assignment is not None
        ]

    def upsert_assignment(self, assignment: AssignmentRecord) -> AssignmentRecord:
        payload = _payload(assignment)
        payload["evidence_ids_json"] = json.dumps(assignment.evidence_ids, sort_keys=True)
        payload["metadata_json"] = _encode_json(assignment.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO assignments (
                    id,
                    industry_instance_id,
                    cycle_id,
                    lane_id,
                    backlog_item_id,
                    goal_id,
                    task_id,
                    owner_agent_id,
                    owner_role_id,
                    title,
                    summary,
                    status,
                    report_back_mode,
                    evidence_ids_json,
                    last_report_id,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :industry_instance_id,
                    :cycle_id,
                    :lane_id,
                    :backlog_item_id,
                    :goal_id,
                    :task_id,
                    :owner_agent_id,
                    :owner_role_id,
                    :title,
                    :summary,
                    :status,
                    :report_back_mode,
                    :evidence_ids_json,
                    :last_report_id,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    industry_instance_id = excluded.industry_instance_id,
                    cycle_id = excluded.cycle_id,
                    lane_id = excluded.lane_id,
                    backlog_item_id = excluded.backlog_item_id,
                    goal_id = excluded.goal_id,
                    task_id = excluded.task_id,
                    owner_agent_id = excluded.owner_agent_id,
                    owner_role_id = excluded.owner_role_id,
                    title = excluded.title,
                    summary = excluded.summary,
                    status = excluded.status,
                    report_back_mode = excluded.report_back_mode,
                    evidence_ids_json = excluded.evidence_ids_json,
                    last_report_id = excluded.last_report_id,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return assignment

    def delete_assignment(self, assignment_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM assignments WHERE id = ?",
                (assignment_id,),
            )
        return cursor.rowcount > 0


class SqliteAgentReportRepository(BaseAgentReportRepository):
    """SQLite-backed repository for structured agent reports."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_report(self, report_id: str) -> AgentReportRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_reports WHERE id = ?",
                (report_id,),
            ).fetchone()
        return _agent_report_from_row(row)

    def list_reports(
        self,
        *,
        industry_instance_id: str | None = None,
        cycle_id: str | None = None,
        assignment_id: str | None = None,
        task_id: str | None = None,
        work_context_id: str | None = None,
        owner_agent_id: str | None = None,
        status: str | None = None,
        processed: bool | None = None,
        limit: int | None = None,
    ) -> list[AgentReportRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if cycle_id is not None:
            clauses.append("cycle_id = ?")
            params.append(cycle_id)
        if assignment_id is not None:
            clauses.append("assignment_id = ?")
            params.append(assignment_id)
        if task_id is not None:
            clauses.append("task_id = ?")
            params.append(task_id)
        if work_context_id is not None:
            clauses.append("work_context_id = ?")
            params.append(work_context_id)
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if processed is not None:
            clauses.append("processed = ?")
            params.append(int(processed))
        query = "SELECT * FROM agent_reports"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, created_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            report
            for report in (_agent_report_from_row(row) for row in rows)
            if report is not None
        ]

    def upsert_report(self, report: AgentReportRecord) -> AgentReportRecord:
        payload = _payload(report)
        payload["findings_json"] = _encode_report_text_list(report.findings)
        payload["uncertainties_json"] = _encode_report_text_list(report.uncertainties)
        payload["needs_followup"] = int(report.needs_followup)
        payload["evidence_ids_json"] = json.dumps(report.evidence_ids, sort_keys=True)
        payload["decision_ids_json"] = json.dumps(report.decision_ids, sort_keys=True)
        payload["processed"] = int(report.processed)
        payload["metadata_json"] = _encode_json(report.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_reports (
                    id,
                    industry_instance_id,
                    cycle_id,
                    assignment_id,
                    goal_id,
                    task_id,
                    work_context_id,
                    lane_id,
                    owner_agent_id,
                    owner_role_id,
                    report_kind,
                    headline,
                    summary,
                    findings_json,
                    uncertainties_json,
                    recommendation,
                    needs_followup,
                    followup_reason,
                    status,
                    result,
                    risk_level,
                    evidence_ids_json,
                    decision_ids_json,
                    processed,
                    processed_at,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :industry_instance_id,
                    :cycle_id,
                    :assignment_id,
                    :goal_id,
                    :task_id,
                    :work_context_id,
                    :lane_id,
                    :owner_agent_id,
                    :owner_role_id,
                    :report_kind,
                    :headline,
                    :summary,
                    :findings_json,
                    :uncertainties_json,
                    :recommendation,
                    :needs_followup,
                    :followup_reason,
                    :status,
                    :result,
                    :risk_level,
                    :evidence_ids_json,
                    :decision_ids_json,
                    :processed,
                    :processed_at,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    industry_instance_id = excluded.industry_instance_id,
                    cycle_id = excluded.cycle_id,
                    assignment_id = excluded.assignment_id,
                    goal_id = excluded.goal_id,
                    task_id = excluded.task_id,
                    work_context_id = excluded.work_context_id,
                    lane_id = excluded.lane_id,
                    owner_agent_id = excluded.owner_agent_id,
                    owner_role_id = excluded.owner_role_id,
                    report_kind = excluded.report_kind,
                    headline = excluded.headline,
                    summary = excluded.summary,
                    findings_json = excluded.findings_json,
                    uncertainties_json = excluded.uncertainties_json,
                    recommendation = excluded.recommendation,
                    needs_followup = excluded.needs_followup,
                    followup_reason = excluded.followup_reason,
                    status = excluded.status,
                    result = excluded.result,
                    risk_level = excluded.risk_level,
                    evidence_ids_json = excluded.evidence_ids_json,
                    decision_ids_json = excluded.decision_ids_json,
                    processed = excluded.processed,
                    processed_at = excluded.processed_at,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return report

    def delete_report(self, report_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_reports WHERE id = ?",
                (report_id,),
            )
        return cursor.rowcount > 0


def _operating_lane_from_row(
    row: sqlite3.Row | None,
) -> OperatingLaneRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return OperatingLaneRecord.model_validate(payload)


def _backlog_item_from_row(
    row: sqlite3.Row | None,
) -> BacklogItemRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["evidence_ids"] = _decode_json_list(
        payload.pop("evidence_ids_json", None),
    ) or []
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return BacklogItemRecord.model_validate(payload)


def _operating_cycle_from_row(
    row: sqlite3.Row | None,
) -> OperatingCycleRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["focus_lane_ids"] = _decode_json_list(
        payload.pop("focus_lane_ids_json", None),
    ) or []
    payload["backlog_item_ids"] = _decode_json_list(
        payload.pop("backlog_item_ids_json", None),
    ) or []
    payload["assignment_ids"] = _decode_json_list(
        payload.pop("assignment_ids_json", None),
    ) or []
    payload["report_ids"] = _decode_json_list(payload.pop("report_ids_json", None)) or []
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return OperatingCycleRecord.model_validate(payload)


def _assignment_from_row(
    row: sqlite3.Row | None,
) -> AssignmentRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["evidence_ids"] = _decode_json_list(
        payload.pop("evidence_ids_json", None),
    ) or []
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return AssignmentRecord.model_validate(payload)


def _agent_report_from_row(
    row: sqlite3.Row | None,
) -> AgentReportRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["findings"] = _decode_report_text_list(payload.pop("findings_json", None))
    payload["uncertainties"] = _decode_report_text_list(
        payload.pop("uncertainties_json", None),
    )
    payload["needs_followup"] = bool(payload.get("needs_followup"))
    payload["evidence_ids"] = _decode_json_list(
        payload.pop("evidence_ids_json", None),
    ) or []
    payload["decision_ids"] = _decode_json_list(
        payload.pop("decision_ids_json", None),
    ) or []
    payload["processed"] = bool(payload.get("processed"))
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return AgentReportRecord.model_validate(payload)


def _encode_report_text_list(values: list[str]) -> str:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return _encode_json({"items": normalized})


def _decode_report_text_list(value: str | None) -> list[str]:
    payload = _decode_any_json(value)
    if isinstance(payload, list):
        source = payload
    elif isinstance(payload, dict):
        source = payload.get("items")
    else:
        source = None
    if not isinstance(source, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in source:
        text = str(raw).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return normalized


def _governance_control_from_row(
    row: sqlite3.Row | None,
) -> GovernanceControlRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["emergency_stop_active"] = bool(payload.get("emergency_stop_active"))
    payload["channel_shutdown_applied"] = bool(payload.get("channel_shutdown_applied"))
    payload["paused_schedule_ids"] = _decode_json_list(
        payload.pop("paused_schedule_ids_json", None),
    ) or []
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return GovernanceControlRecord.model_validate(payload)


def _industry_instance_from_row(
    row: sqlite3.Row | None,
) -> IndustryInstanceRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["profile_payload"] = _decode_json_mapping(
        payload.pop("profile_payload_json", None),
    )
    payload["team_payload"] = _decode_json_mapping(
        payload.pop("team_payload_json", None),
    )
    payload["execution_core_identity_payload"] = _decode_json_mapping(
        payload.pop("execution_core_identity_payload_json", None),
    )
    payload["agent_ids"] = _decode_json_list(payload.pop("agent_ids_json", None)) or []
    return IndustryInstanceRecord.model_validate(payload)
