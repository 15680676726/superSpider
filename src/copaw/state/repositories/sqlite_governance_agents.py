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


class SqliteAgentRuntimeRepository(BaseAgentRuntimeRepository):
    """SQLite-backed repository for actor runtime records."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_runtime(self, agent_id: str) -> AgentRuntimeRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_runtimes WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
        return _agent_runtime_from_row(row)

    def list_runtimes(
        self,
        *,
        runtime_status: str | None = None,
        desired_state: str | None = None,
        industry_instance_id: str | None = None,
        limit: int | None = None,
    ) -> list[AgentRuntimeRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if runtime_status is not None:
            clauses.append("runtime_status = ?")
            params.append(runtime_status)
        if desired_state is not None:
            clauses.append("desired_state = ?")
            params.append(desired_state)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        query = "SELECT * FROM agent_runtimes"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC"
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            runtime
            for runtime in (_agent_runtime_from_row(row) for row in rows)
            if runtime is not None
        ]

    def upsert_runtime(self, runtime: AgentRuntimeRecord) -> AgentRuntimeRecord:
        payload = _payload(runtime)
        payload["persistent"] = int(bool(runtime.persistent))
        payload["metadata_json"] = _encode_json(runtime.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_runtimes (
                    agent_id,
                    actor_key,
                    actor_fingerprint,
                    actor_class,
                    desired_state,
                    runtime_status,
                    employment_mode,
                    activation_mode,
                    persistent,
                    industry_instance_id,
                    industry_role_id,
                    display_name,
                    role_name,
                    current_task_id,
                    current_mailbox_id,
                    current_environment_id,
                    queue_depth,
                    last_started_at,
                    last_heartbeat_at,
                    last_stopped_at,
                    last_error_summary,
                    last_result_summary,
                    last_checkpoint_id,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :agent_id,
                    :actor_key,
                    :actor_fingerprint,
                    :actor_class,
                    :desired_state,
                    :runtime_status,
                    :employment_mode,
                    :activation_mode,
                    :persistent,
                    :industry_instance_id,
                    :industry_role_id,
                    :display_name,
                    :role_name,
                    :current_task_id,
                    :current_mailbox_id,
                    :current_environment_id,
                    :queue_depth,
                    :last_started_at,
                    :last_heartbeat_at,
                    :last_stopped_at,
                    :last_error_summary,
                    :last_result_summary,
                    :last_checkpoint_id,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(agent_id) DO UPDATE SET
                    actor_key = excluded.actor_key,
                    actor_fingerprint = excluded.actor_fingerprint,
                    actor_class = excluded.actor_class,
                    desired_state = excluded.desired_state,
                    runtime_status = excluded.runtime_status,
                    employment_mode = excluded.employment_mode,
                    activation_mode = excluded.activation_mode,
                    persistent = excluded.persistent,
                    industry_instance_id = excluded.industry_instance_id,
                    industry_role_id = excluded.industry_role_id,
                    display_name = excluded.display_name,
                    role_name = excluded.role_name,
                    current_task_id = excluded.current_task_id,
                    current_mailbox_id = excluded.current_mailbox_id,
                    current_environment_id = excluded.current_environment_id,
                    queue_depth = excluded.queue_depth,
                    last_started_at = excluded.last_started_at,
                    last_heartbeat_at = excluded.last_heartbeat_at,
                    last_stopped_at = excluded.last_stopped_at,
                    last_error_summary = excluded.last_error_summary,
                    last_result_summary = excluded.last_result_summary,
                    last_checkpoint_id = excluded.last_checkpoint_id,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return runtime

    def delete_runtime(self, agent_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_runtimes WHERE agent_id = ?",
                (agent_id,),
            )
        return cursor.rowcount > 0


def _agent_runtime_from_row(row: sqlite3.Row | None) -> AgentRuntimeRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["persistent"] = bool(payload.get("persistent", 1))
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return AgentRuntimeRecord.model_validate(payload)


class SqliteAgentMailboxRepository(BaseAgentMailboxRepository):
    """SQLite-backed repository for actor mailbox entries."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_item(self, item_id: str) -> AgentMailboxRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_mailbox WHERE id = ?",
                (item_id,),
            ).fetchone()
        return _agent_mailbox_from_row(row)

    def list_items(
        self,
        *,
        agent_id: str | None = None,
        status: str | None = None,
        conversation_thread_id: str | None = None,
        work_context_id: str | None = None,
        limit: int | None = None,
    ) -> list[AgentMailboxRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if agent_id is not None:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if conversation_thread_id is not None:
            clauses.append("conversation_thread_id = ?")
            params.append(conversation_thread_id)
        if work_context_id is not None:
            clauses.append("work_context_id = ?")
            params.append(work_context_id)
        query = "SELECT * FROM agent_mailbox"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = (
            f"{query} ORDER BY priority DESC, "
            "CASE status WHEN 'queued' THEN 0 WHEN 'retry-wait' THEN 1 ELSE 2 END, "
            "updated_at ASC"
        )
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            item
            for item in (_agent_mailbox_from_row(row) for row in rows)
            if item is not None
        ]

    def upsert_item(self, item: AgentMailboxRecord) -> AgentMailboxRecord:
        payload = _payload(item)
        payload["payload_json"] = _encode_json(item.payload)
        payload["metadata_json"] = _encode_json(item.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_mailbox (
                    id,
                    agent_id,
                    task_id,
                    work_context_id,
                    parent_mailbox_id,
                    source_agent_id,
                    envelope_type,
                    title,
                    summary,
                    status,
                    priority,
                    capability_ref,
                    conversation_thread_id,
                    payload_json,
                    result_summary,
                    error_summary,
                    lease_owner,
                    lease_token,
                    claimed_at,
                    started_at,
                    completed_at,
                    retry_after_at,
                    attempt_count,
                    max_attempts,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :agent_id,
                    :task_id,
                    :work_context_id,
                    :parent_mailbox_id,
                    :source_agent_id,
                    :envelope_type,
                    :title,
                    :summary,
                    :status,
                    :priority,
                    :capability_ref,
                    :conversation_thread_id,
                    :payload_json,
                    :result_summary,
                    :error_summary,
                    :lease_owner,
                    :lease_token,
                    :claimed_at,
                    :started_at,
                    :completed_at,
                    :retry_after_at,
                    :attempt_count,
                    :max_attempts,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    agent_id = excluded.agent_id,
                    task_id = excluded.task_id,
                    work_context_id = excluded.work_context_id,
                    parent_mailbox_id = excluded.parent_mailbox_id,
                    source_agent_id = excluded.source_agent_id,
                    envelope_type = excluded.envelope_type,
                    title = excluded.title,
                    summary = excluded.summary,
                    status = excluded.status,
                    priority = excluded.priority,
                    capability_ref = excluded.capability_ref,
                    conversation_thread_id = excluded.conversation_thread_id,
                    payload_json = excluded.payload_json,
                    result_summary = excluded.result_summary,
                    error_summary = excluded.error_summary,
                    lease_owner = excluded.lease_owner,
                    lease_token = excluded.lease_token,
                    claimed_at = excluded.claimed_at,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    retry_after_at = excluded.retry_after_at,
                    attempt_count = excluded.attempt_count,
                    max_attempts = excluded.max_attempts,
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
                "DELETE FROM agent_mailbox WHERE id = ?",
                (item_id,),
            )
        return cursor.rowcount > 0


def _agent_mailbox_from_row(row: sqlite3.Row | None) -> AgentMailboxRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["payload"] = _decode_json_mapping(payload.pop("payload_json", None))
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return AgentMailboxRecord.model_validate(payload)


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


class SqliteAgentLeaseRepository(BaseAgentLeaseRepository):
    """SQLite-backed repository for actor leases."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_lease(self, lease_id: str) -> AgentLeaseRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_leases WHERE id = ?",
                (lease_id,),
            ).fetchone()
        return _agent_lease_from_row(row)

    def list_leases(
        self,
        *,
        agent_id: str | None = None,
        lease_status: str | None = None,
        lease_kind: str | None = None,
        limit: int | None = None,
    ) -> list[AgentLeaseRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if agent_id is not None:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        if lease_status is not None:
            clauses.append("lease_status = ?")
            params.append(lease_status)
        if lease_kind is not None:
            clauses.append("lease_kind = ?")
            params.append(lease_kind)
        query = "SELECT * FROM agent_leases"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC"
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            lease
            for lease in (_agent_lease_from_row(row) for row in rows)
            if lease is not None
        ]

    def upsert_lease(self, lease: AgentLeaseRecord) -> AgentLeaseRecord:
        payload = _payload(lease)
        payload["metadata_json"] = _encode_json(lease.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_leases (
                    id,
                    agent_id,
                    lease_kind,
                    resource_ref,
                    lease_status,
                    lease_token,
                    owner,
                    acquired_at,
                    expires_at,
                    heartbeat_at,
                    released_at,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :agent_id,
                    :lease_kind,
                    :resource_ref,
                    :lease_status,
                    :lease_token,
                    :owner,
                    :acquired_at,
                    :expires_at,
                    :heartbeat_at,
                    :released_at,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    agent_id = excluded.agent_id,
                    lease_kind = excluded.lease_kind,
                    resource_ref = excluded.resource_ref,
                    lease_status = excluded.lease_status,
                    lease_token = excluded.lease_token,
                    owner = excluded.owner,
                    acquired_at = excluded.acquired_at,
                    expires_at = excluded.expires_at,
                    heartbeat_at = excluded.heartbeat_at,
                    released_at = excluded.released_at,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return lease

    def delete_lease(self, lease_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_leases WHERE id = ?",
                (lease_id,),
            )
        return cursor.rowcount > 0


def _agent_lease_from_row(row: sqlite3.Row | None) -> AgentLeaseRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return AgentLeaseRecord.model_validate(payload)


class SqliteAgentThreadBindingRepository(BaseAgentThreadBindingRepository):
    """SQLite-backed repository for actor thread bindings and aliases."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_binding(self, thread_id: str) -> AgentThreadBindingRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_thread_bindings WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
        return _agent_thread_binding_from_row(row)

    def list_bindings(
        self,
        *,
        agent_id: str | None = None,
        industry_instance_id: str | None = None,
        work_context_id: str | None = None,
        active_only: bool = False,
        limit: int | None = None,
    ) -> list[AgentThreadBindingRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if agent_id is not None:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if work_context_id is not None:
            clauses.append("work_context_id = ?")
            params.append(work_context_id)
        if active_only:
            clauses.append("active = 1")
        query = "SELECT * FROM agent_thread_bindings"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC"
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            binding
            for binding in (_agent_thread_binding_from_row(row) for row in rows)
            if binding is not None
        ]

    def upsert_binding(
        self,
        binding: AgentThreadBindingRecord,
    ) -> AgentThreadBindingRecord:
        payload = _payload(binding)
        payload["active"] = int(bool(binding.active))
        payload["metadata_json"] = _encode_json(binding.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_thread_bindings (
                    thread_id,
                    agent_id,
                    session_id,
                    channel,
                    binding_kind,
                    industry_instance_id,
                    industry_role_id,
                    work_context_id,
                    owner_scope,
                    active,
                    alias_of_thread_id,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :thread_id,
                    :agent_id,
                    :session_id,
                    :channel,
                    :binding_kind,
                    :industry_instance_id,
                    :industry_role_id,
                    :work_context_id,
                    :owner_scope,
                    :active,
                    :alias_of_thread_id,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(thread_id) DO UPDATE SET
                    agent_id = excluded.agent_id,
                    session_id = excluded.session_id,
                    channel = excluded.channel,
                    binding_kind = excluded.binding_kind,
                    industry_instance_id = excluded.industry_instance_id,
                    industry_role_id = excluded.industry_role_id,
                    work_context_id = excluded.work_context_id,
                    owner_scope = excluded.owner_scope,
                    active = excluded.active,
                    alias_of_thread_id = excluded.alias_of_thread_id,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return binding

    def delete_binding(self, thread_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_thread_bindings WHERE thread_id = ?",
                (thread_id,),
            )
        return cursor.rowcount > 0


def _agent_thread_binding_from_row(
    row: sqlite3.Row | None,
) -> AgentThreadBindingRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["active"] = bool(payload.get("active", 1))
    payload["metadata"] = _decode_json_mapping(payload.pop("metadata_json", None))
    return AgentThreadBindingRecord.model_validate(payload)


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
