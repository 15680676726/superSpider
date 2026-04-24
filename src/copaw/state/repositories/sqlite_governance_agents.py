# -*- coding: utf-8 -*-
from __future__ import annotations

from .sqlite_shared import *  # noqa: F401,F403


class SqliteDecisionRequestRepository(BaseDecisionRequestRepository):
    """SQLite-backed decision request repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_decision_request(
        self,
        decision_id: str,
    ) -> DecisionRequestRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM decision_requests WHERE id = ?",
                (decision_id,),
            ).fetchone()
        return _model_from_row(DecisionRequestRecord, row)

    def list_decision_requests(
        self,
        *,
        task_id: str | None = None,
        status: str | None = None,
        task_ids: Sequence[str] | None = None,
        created_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[DecisionRequestRecord]:
        clauses: list[str] = []
        params: list[Any] = []

        if task_id is not None:
            clauses.append("task_id = ?")
            params.append(task_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if task_ids:
            placeholders = ", ".join("?" for _ in task_ids)
            clauses.append(f"task_id IN ({placeholders})")
            params.extend(task_ids)
        if created_since is not None:
            clauses.append("created_at >= ?")
            params.append(_encode_datetime_value(created_since))

        query = "SELECT * FROM decision_requests"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY created_at DESC"
        if limit is not None:
            query = f"{query} LIMIT ?"
            params.append(limit)

        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [DecisionRequestRecord.model_validate(dict(row)) for row in rows]

    def upsert_decision_request(
        self,
        decision: DecisionRequestRecord,
    ) -> DecisionRequestRecord:
        payload = _payload(decision)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO decision_requests (
                    id,
                    task_id,
                    decision_type,
                    risk_level,
                    summary,
                    status,
                    source_evidence_id,
                    source_patch_id,
                    requested_by,
                    resolution,
                    created_at,
                    resolved_at,
                    expires_at
                ) VALUES (
                    :id,
                    :task_id,
                    :decision_type,
                    :risk_level,
                    :summary,
                    :status,
                    :source_evidence_id,
                    :source_patch_id,
                    :requested_by,
                    :resolution,
                    :created_at,
                    :resolved_at,
                    :expires_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    task_id = excluded.task_id,
                    decision_type = excluded.decision_type,
                    risk_level = excluded.risk_level,
                    summary = excluded.summary,
                    status = excluded.status,
                    source_evidence_id = excluded.source_evidence_id,
                    source_patch_id = excluded.source_patch_id,
                    requested_by = excluded.requested_by,
                    resolution = excluded.resolution,
                    created_at = excluded.created_at,
                    resolved_at = excluded.resolved_at,
                    expires_at = excluded.expires_at
                """,
                payload,
            )
        return decision

    def delete_decision_request(self, decision_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM decision_requests WHERE id = ?",
                (decision_id,),
            )
        return cursor.rowcount > 0


class SqliteGovernanceControlRepository(BaseGovernanceControlRepository):
    """SQLite-backed repository for runtime governance controls."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_control(self, control_id: str = "runtime") -> GovernanceControlRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM governance_controls WHERE id = ?",
                (control_id,),
            ).fetchone()
        return _governance_control_from_row(row)

    def upsert_control(
        self,
        control: GovernanceControlRecord,
    ) -> GovernanceControlRecord:
        payload = _payload(control)
        payload["emergency_stop_active"] = int(bool(payload.get("emergency_stop_active")))
        payload["channel_shutdown_applied"] = int(bool(payload.get("channel_shutdown_applied")))
        payload["paused_schedule_ids_json"] = json.dumps(
            control.paused_schedule_ids,
            ensure_ascii=False,
            sort_keys=True,
        )
        payload["metadata_json"] = json.dumps(
            control.metadata,
            ensure_ascii=False,
            sort_keys=True,
        )
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO governance_controls (
                    id,
                    emergency_stop_active,
                    emergency_reason,
                    emergency_actor,
                    paused_schedule_ids_json,
                    channel_shutdown_applied,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :emergency_stop_active,
                    :emergency_reason,
                    :emergency_actor,
                    :paused_schedule_ids_json,
                    :channel_shutdown_applied,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    emergency_stop_active = excluded.emergency_stop_active,
                    emergency_reason = excluded.emergency_reason,
                    emergency_actor = excluded.emergency_actor,
                    paused_schedule_ids_json = excluded.paused_schedule_ids_json,
                    channel_shutdown_applied = excluded.channel_shutdown_applied,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return control


class SqliteCapabilityOverrideRepository:
    """SQLite-backed repository for capability overrides."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_override(self, capability_id: str) -> CapabilityOverrideRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM capability_overrides WHERE capability_id = ?",
                (capability_id,),
            ).fetchone()
        return _model_from_row(CapabilityOverrideRecord, row)

    def list_overrides(self) -> list[CapabilityOverrideRecord]:
        with self._store.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM capability_overrides ORDER BY updated_at DESC",
            ).fetchall()
        return [CapabilityOverrideRecord.model_validate(dict(row)) for row in rows]

    def upsert_override(
        self,
        override: CapabilityOverrideRecord,
    ) -> CapabilityOverrideRecord:
        payload = _payload(override)
        enabled = payload.get("enabled")
        payload["enabled"] = None if enabled is None else int(bool(enabled))
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO capability_overrides (
                    capability_id,
                    enabled,
                    forced_risk_level,
                    reason,
                    source_patch_id,
                    created_at,
                    updated_at
                ) VALUES (
                    :capability_id,
                    :enabled,
                    :forced_risk_level,
                    :reason,
                    :source_patch_id,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(capability_id) DO UPDATE SET
                    enabled = excluded.enabled,
                    forced_risk_level = excluded.forced_risk_level,
                    reason = excluded.reason,
                    source_patch_id = excluded.source_patch_id,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return override

    def delete_override(self, capability_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM capability_overrides WHERE capability_id = ?",
                (capability_id,),
            )
        return cursor.rowcount > 0


class SqliteAgentProfileOverrideRepository:
    """SQLite-backed repository for agent profile overrides."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_override(self, agent_id: str) -> AgentProfileOverrideRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_profile_overrides WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
        return _agent_profile_override_from_row(row)

    def list_overrides(self) -> list[AgentProfileOverrideRecord]:
        with self._store.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_profile_overrides ORDER BY updated_at DESC",
            ).fetchall()
        return [
            override
            for override in (_agent_profile_override_from_row(row) for row in rows)
            if override is not None
        ]

    def upsert_override(
        self,
        override: AgentProfileOverrideRecord,
    ) -> AgentProfileOverrideRecord:
        payload = _payload(override)
        payload["suspendable"] = (
            None
            if override.suspendable is None
            else int(bool(override.suspendable))
        )
        payload["environment_constraints_json"] = json.dumps(
            override.environment_constraints,
            ensure_ascii=False,
            sort_keys=True,
        ) if override.environment_constraints is not None else None
        payload["evidence_expectations_json"] = json.dumps(
            override.evidence_expectations,
            ensure_ascii=False,
            sort_keys=True,
        ) if override.evidence_expectations is not None else None
        payload["capabilities_json"] = json.dumps(
            override.capabilities,
            ensure_ascii=False,
            sort_keys=True,
        ) if override.capabilities is not None else None
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_profile_overrides (
                    agent_id,
                    name,
                    role_name,
                    role_summary,
                    agent_class,
                    employment_mode,
                    activation_mode,
                    suspendable,
                    reports_to,
                    mission,
                    status,
                    risk_level,
                    current_focus_kind,
                    current_focus_id,
                    current_focus,
                    current_task_id,
                    industry_instance_id,
                    industry_role_id,
                    environment_summary,
                    today_output_summary,
                    latest_evidence_summary,
                    environment_constraints_json,
                    evidence_expectations_json,
                    capabilities_json,
                    reason,
                    source_patch_id,
                    created_at,
                    updated_at
                ) VALUES (
                    :agent_id,
                    :name,
                    :role_name,
                    :role_summary,
                    :agent_class,
                    :employment_mode,
                    :activation_mode,
                    :suspendable,
                    :reports_to,
                    :mission,
                    :status,
                    :risk_level,
                    :current_focus_kind,
                    :current_focus_id,
                    :current_focus,
                    :current_task_id,
                    :industry_instance_id,
                    :industry_role_id,
                    :environment_summary,
                    :today_output_summary,
                    :latest_evidence_summary,
                    :environment_constraints_json,
                    :evidence_expectations_json,
                    :capabilities_json,
                    :reason,
                    :source_patch_id,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(agent_id) DO UPDATE SET
                    name = excluded.name,
                    role_name = excluded.role_name,
                    role_summary = excluded.role_summary,
                    agent_class = excluded.agent_class,
                    employment_mode = excluded.employment_mode,
                    activation_mode = excluded.activation_mode,
                    suspendable = excluded.suspendable,
                    reports_to = excluded.reports_to,
                    mission = excluded.mission,
                    status = excluded.status,
                    risk_level = excluded.risk_level,
                    current_focus_kind = excluded.current_focus_kind,
                    current_focus_id = excluded.current_focus_id,
                    current_focus = excluded.current_focus,
                    current_task_id = excluded.current_task_id,
                    industry_instance_id = excluded.industry_instance_id,
                    industry_role_id = excluded.industry_role_id,
                    environment_summary = excluded.environment_summary,
                    today_output_summary = excluded.today_output_summary,
                    latest_evidence_summary = excluded.latest_evidence_summary,
                    environment_constraints_json = excluded.environment_constraints_json,
                    evidence_expectations_json = excluded.evidence_expectations_json,
                    capabilities_json = excluded.capabilities_json,
                    reason = excluded.reason,
                    source_patch_id = excluded.source_patch_id,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return override

    def delete_override(self, agent_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_profile_overrides WHERE agent_id = ?",
                (agent_id,),
            )
        return cursor.rowcount > 0


def _agent_profile_override_from_row(
    row: sqlite3.Row | None,
) -> AgentProfileOverrideRecord | None:
    if row is None:
        return None
    payload = dict(row)
    suspendable = payload.get("suspendable")
    payload["suspendable"] = None if suspendable is None else bool(suspendable)
    payload["environment_constraints"] = _decode_json_list(
        payload.pop("environment_constraints_json", None),
    )
    payload["evidence_expectations"] = _decode_json_list(
        payload.pop("evidence_expectations_json", None),
    )
    payload["capabilities"] = _decode_json_list(payload.pop("capabilities_json", None))
    allowed_keys = AgentProfileOverrideRecord.model_fields.keys()
    filtered_payload = {
        key: value for key, value in payload.items() if key in allowed_keys
    }
    return AgentProfileOverrideRecord.model_validate(filtered_payload)


class SqliteAgentCheckpointRepository(BaseAgentCheckpointRepository):
    """SQLite-backed repository for actor checkpoints."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_checkpoint(self, checkpoint_id: str) -> AgentCheckpointRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_checkpoints WHERE id = ?",
                (checkpoint_id,),
            ).fetchone()
        return _agent_checkpoint_from_row(row)

    def list_checkpoints(
        self,
        *,
        agent_id: str | None = None,
        mailbox_id: str | None = None,
        task_id: str | None = None,
        work_context_id: str | None = None,
        limit: int | None = None,
    ) -> list[AgentCheckpointRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if agent_id is not None:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        if mailbox_id is not None:
            clauses.append("mailbox_id = ?")
            params.append(mailbox_id)
        if task_id is not None:
            clauses.append("task_id = ?")
            params.append(task_id)
        if work_context_id is not None:
            clauses.append("work_context_id = ?")
            params.append(work_context_id)
        query = "SELECT * FROM agent_checkpoints"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC"
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            checkpoint
            for checkpoint in (_agent_checkpoint_from_row(row) for row in rows)
            if checkpoint is not None
        ]

    def upsert_checkpoint(
        self,
        checkpoint: AgentCheckpointRecord,
    ) -> AgentCheckpointRecord:
        payload = _payload(checkpoint)
        payload["snapshot_payload_json"] = _encode_json(checkpoint.snapshot_payload)
        payload["resume_payload_json"] = _encode_json(checkpoint.resume_payload)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_checkpoints (
                    id,
                    agent_id,
                    mailbox_id,
                    task_id,
                    work_context_id,
                    checkpoint_kind,
                    status,
                    phase,
                    cursor,
                    conversation_thread_id,
                    environment_ref,
                    snapshot_payload_json,
                    resume_payload_json,
                    summary,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :agent_id,
                    :mailbox_id,
                    :task_id,
                    :work_context_id,
                    :checkpoint_kind,
                    :status,
                    :phase,
                    :cursor,
                    :conversation_thread_id,
                    :environment_ref,
                    :snapshot_payload_json,
                    :resume_payload_json,
                    :summary,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    agent_id = excluded.agent_id,
                    mailbox_id = excluded.mailbox_id,
                    task_id = excluded.task_id,
                    work_context_id = excluded.work_context_id,
                    checkpoint_kind = excluded.checkpoint_kind,
                    status = excluded.status,
                    phase = excluded.phase,
                    cursor = excluded.cursor,
                    conversation_thread_id = excluded.conversation_thread_id,
                    environment_ref = excluded.environment_ref,
                    snapshot_payload_json = excluded.snapshot_payload_json,
                    resume_payload_json = excluded.resume_payload_json,
                    summary = excluded.summary,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return checkpoint

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_checkpoints WHERE id = ?",
                (checkpoint_id,),
            )
        return cursor.rowcount > 0


def _agent_checkpoint_from_row(
    row: sqlite3.Row | None,
) -> AgentCheckpointRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["snapshot_payload"] = _decode_json_mapping(
        payload.pop("snapshot_payload_json", None),
    )
    payload["resume_payload"] = _decode_json_mapping(
        payload.pop("resume_payload_json", None),
    )
    return AgentCheckpointRecord.model_validate(payload)


class SqliteGoalOverrideRepository:
    """SQLite-backed repository for goal plan overrides."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_override(self, goal_id: str) -> GoalOverrideRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM goal_overrides WHERE goal_id = ?",
                (goal_id,),
            ).fetchone()
        return _goal_override_from_row(row)

    def list_overrides(self) -> list[GoalOverrideRecord]:
        with self._store.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM goal_overrides ORDER BY updated_at DESC",
            ).fetchall()
        return [
            override
            for override in (_goal_override_from_row(row) for row in rows)
            if override is not None
        ]

    def upsert_override(self, override: GoalOverrideRecord) -> GoalOverrideRecord:
        payload = _payload(override)
        payload["plan_steps_json"] = json.dumps(
            override.plan_steps,
            ensure_ascii=False,
            sort_keys=True,
        ) if override.plan_steps is not None else None
        payload["compiler_context_json"] = _encode_json(override.compiler_context)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO goal_overrides (
                    goal_id,
                    title,
                    summary,
                    status,
                    priority,
                    owner_scope,
                    plan_steps_json,
                    compiler_context_json,
                    reason,
                    source_patch_id,
                    created_at,
                    updated_at
                ) VALUES (
                    :goal_id,
                    :title,
                    :summary,
                    :status,
                    :priority,
                    :owner_scope,
                    :plan_steps_json,
                    :compiler_context_json,
                    :reason,
                    :source_patch_id,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(goal_id) DO UPDATE SET
                    title = excluded.title,
                    summary = excluded.summary,
                    status = excluded.status,
                    priority = excluded.priority,
                    owner_scope = excluded.owner_scope,
                    plan_steps_json = excluded.plan_steps_json,
                    compiler_context_json = excluded.compiler_context_json,
                    reason = excluded.reason,
                    source_patch_id = excluded.source_patch_id,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return override

    def delete_override(self, goal_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM goal_overrides WHERE goal_id = ?",
                (goal_id,),
            )
        return cursor.rowcount > 0


def _goal_override_from_row(row: sqlite3.Row | None) -> GoalOverrideRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["plan_steps"] = _decode_json_list(payload.pop("plan_steps_json", None))
    payload["compiler_context"] = _decode_json_mapping(
        payload.pop("compiler_context_json", None),
    )
    return GoalOverrideRecord.model_validate(payload)
