# -*- coding: utf-8 -*-
from __future__ import annotations

from .sqlite_shared import *  # noqa: F401,F403


class SqliteWorkflowTemplateRepository(BaseWorkflowTemplateRepository):
    """SQLite-backed workflow template repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_template(self, template_id: str) -> WorkflowTemplateRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()
        return _workflow_template_from_row(row)

    def list_templates(
        self,
        *,
        category: str | None = None,
        status: str | None = None,
    ) -> list[WorkflowTemplateRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        query = "SELECT * FROM workflow_templates"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, template_id ASC"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_workflow_template_from_row(row) for row in rows]

    def upsert_template(
        self,
        template: WorkflowTemplateRecord,
    ) -> WorkflowTemplateRecord:
        payload = _payload(template)
        payload["industry_tags_json"] = json.dumps(template.industry_tags or [])
        payload["team_modes_json"] = json.dumps(template.team_modes or [])
        payload["dependency_capability_ids_json"] = json.dumps(
            template.dependency_capability_ids or [],
        )
        payload["suggested_role_ids_json"] = json.dumps(template.suggested_role_ids or [])
        payload["parameter_schema_json"] = _encode_json(template.parameter_schema)
        payload["step_specs_json"] = json.dumps(template.step_specs or [])
        payload["metadata_json"] = _encode_json(template.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO workflow_templates (
                    template_id,
                    title,
                    summary,
                    category,
                    status,
                    version,
                    industry_tags_json,
                    team_modes_json,
                    dependency_capability_ids_json,
                    suggested_role_ids_json,
                    owner_role_id,
                    parameter_schema_json,
                    step_specs_json,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :template_id,
                    :title,
                    :summary,
                    :category,
                    :status,
                    :version,
                    :industry_tags_json,
                    :team_modes_json,
                    :dependency_capability_ids_json,
                    :suggested_role_ids_json,
                    :owner_role_id,
                    :parameter_schema_json,
                    :step_specs_json,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(template_id) DO UPDATE SET
                    title = excluded.title,
                    summary = excluded.summary,
                    category = excluded.category,
                    status = excluded.status,
                    version = excluded.version,
                    industry_tags_json = excluded.industry_tags_json,
                    team_modes_json = excluded.team_modes_json,
                    dependency_capability_ids_json = excluded.dependency_capability_ids_json,
                    suggested_role_ids_json = excluded.suggested_role_ids_json,
                    owner_role_id = excluded.owner_role_id,
                    parameter_schema_json = excluded.parameter_schema_json,
                    step_specs_json = excluded.step_specs_json,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return template

    def delete_template(self, template_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM workflow_templates WHERE template_id = ?",
                (template_id,),
            )
        return cursor.rowcount > 0


class SqliteFixedSopTemplateRepository(BaseFixedSopTemplateRepository):
    """SQLite-backed native fixed SOP template repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_template(self, template_id: str) -> FixedSopTemplateRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM fixed_sop_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()
        return _fixed_sop_template_from_row(row)

    def list_templates(
        self,
        *,
        status: str | None = None,
    ) -> list[FixedSopTemplateRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        query = "SELECT * FROM fixed_sop_templates"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, template_id ASC"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            template
            for template in (_fixed_sop_template_from_row(row) for row in rows)
            if template is not None
        ]

    def upsert_template(
        self,
        template: FixedSopTemplateRecord,
    ) -> FixedSopTemplateRecord:
        payload = _payload(template)
        payload["suggested_role_ids_json"] = json.dumps(template.suggested_role_ids or [])
        payload["industry_tags_json"] = json.dumps(template.industry_tags or [])
        payload["capability_tags_json"] = json.dumps(template.capability_tags or [])
        payload["input_schema_json"] = _encode_json(template.input_schema)
        payload["output_schema_json"] = _encode_json(template.output_schema)
        payload["writeback_contract_json"] = _encode_json(template.writeback_contract)
        payload["node_graph_json"] = json.dumps(template.node_graph or [])
        payload["metadata_json"] = _encode_json(template.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO fixed_sop_templates (
                    template_id,
                    name,
                    summary,
                    description,
                    status,
                    version,
                    source_kind,
                    source_ref,
                    owner_role_id,
                    suggested_role_ids_json,
                    industry_tags_json,
                    capability_tags_json,
                    risk_baseline,
                    input_schema_json,
                    output_schema_json,
                    writeback_contract_json,
                    node_graph_json,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :template_id,
                    :name,
                    :summary,
                    :description,
                    :status,
                    :version,
                    :source_kind,
                    :source_ref,
                    :owner_role_id,
                    :suggested_role_ids_json,
                    :industry_tags_json,
                    :capability_tags_json,
                    :risk_baseline,
                    :input_schema_json,
                    :output_schema_json,
                    :writeback_contract_json,
                    :node_graph_json,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(template_id) DO UPDATE SET
                    name = excluded.name,
                    summary = excluded.summary,
                    description = excluded.description,
                    status = excluded.status,
                    version = excluded.version,
                    source_kind = excluded.source_kind,
                    source_ref = excluded.source_ref,
                    owner_role_id = excluded.owner_role_id,
                    suggested_role_ids_json = excluded.suggested_role_ids_json,
                    industry_tags_json = excluded.industry_tags_json,
                    capability_tags_json = excluded.capability_tags_json,
                    risk_baseline = excluded.risk_baseline,
                    input_schema_json = excluded.input_schema_json,
                    output_schema_json = excluded.output_schema_json,
                    writeback_contract_json = excluded.writeback_contract_json,
                    node_graph_json = excluded.node_graph_json,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return template

    def delete_template(self, template_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM fixed_sop_templates WHERE template_id = ?",
                (template_id,),
            )
        return cursor.rowcount > 0


class SqliteFixedSopBindingRepository(BaseFixedSopBindingRepository):
    """SQLite-backed native fixed SOP binding repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_binding(self, binding_id: str) -> FixedSopBindingRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM fixed_sop_bindings WHERE binding_id = ?",
                (binding_id,),
            ).fetchone()
        return _fixed_sop_binding_from_row(row)

    def list_bindings(
        self,
        *,
        template_id: str | None = None,
        status: str | None = None,
        industry_instance_id: str | None = None,
        owner_agent_id: str | None = None,
        limit: int | None = None,
    ) -> list[FixedSopBindingRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if template_id is not None:
            clauses.append("template_id = ?")
            params.append(template_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        query = "SELECT * FROM fixed_sop_bindings"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, binding_id ASC"
        if limit is not None and limit >= 0:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            binding
            for binding in (_fixed_sop_binding_from_row(row) for row in rows)
            if binding is not None
        ]

    def upsert_binding(
        self,
        binding: FixedSopBindingRecord,
    ) -> FixedSopBindingRecord:
        payload = _payload(binding)
        payload["input_mapping_json"] = _encode_json(binding.input_mapping)
        payload["output_mapping_json"] = _encode_json(binding.output_mapping)
        payload["timeout_policy_json"] = _encode_json(binding.timeout_policy)
        payload["retry_policy_json"] = _encode_json(binding.retry_policy)
        payload["metadata_json"] = _encode_json(binding.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO fixed_sop_bindings (
                    binding_id,
                    template_id,
                    binding_name,
                    status,
                    owner_scope,
                    owner_agent_id,
                    industry_instance_id,
                    workflow_template_id,
                    trigger_mode,
                    trigger_ref,
                    input_mapping_json,
                    output_mapping_json,
                    timeout_policy_json,
                    retry_policy_json,
                    risk_baseline,
                    last_run_id,
                    last_verified_at,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :binding_id,
                    :template_id,
                    :binding_name,
                    :status,
                    :owner_scope,
                    :owner_agent_id,
                    :industry_instance_id,
                    :workflow_template_id,
                    :trigger_mode,
                    :trigger_ref,
                    :input_mapping_json,
                    :output_mapping_json,
                    :timeout_policy_json,
                    :retry_policy_json,
                    :risk_baseline,
                    :last_run_id,
                    :last_verified_at,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(binding_id) DO UPDATE SET
                    template_id = excluded.template_id,
                    binding_name = excluded.binding_name,
                    status = excluded.status,
                    owner_scope = excluded.owner_scope,
                    owner_agent_id = excluded.owner_agent_id,
                    industry_instance_id = excluded.industry_instance_id,
                    workflow_template_id = excluded.workflow_template_id,
                    trigger_mode = excluded.trigger_mode,
                    trigger_ref = excluded.trigger_ref,
                    input_mapping_json = excluded.input_mapping_json,
                    output_mapping_json = excluded.output_mapping_json,
                    timeout_policy_json = excluded.timeout_policy_json,
                    retry_policy_json = excluded.retry_policy_json,
                    risk_baseline = excluded.risk_baseline,
                    last_run_id = excluded.last_run_id,
                    last_verified_at = excluded.last_verified_at,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return binding

    def delete_binding(self, binding_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM fixed_sop_bindings WHERE binding_id = ?",
                (binding_id,),
            )
        return cursor.rowcount > 0


class SqliteWorkflowRunRepository(BaseWorkflowRunRepository):
    """SQLite-backed workflow run repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_run(self, run_id: str) -> WorkflowRunRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return _workflow_run_from_row(row)

    def list_runs(
        self,
        *,
        template_id: str | None = None,
        status: str | None = None,
        industry_instance_id: str | None = None,
    ) -> list[WorkflowRunRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if template_id is not None:
            clauses.append("template_id = ?")
            params.append(template_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        query = "SELECT * FROM workflow_runs"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, run_id DESC"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_workflow_run_from_row(row) for row in rows]

    def upsert_run(self, run: WorkflowRunRecord) -> WorkflowRunRecord:
        payload = _payload(run)
        payload["parameter_payload_json"] = _encode_json(run.parameter_payload)
        payload["preview_payload_json"] = _encode_json(run.preview_payload)
        payload["task_ids_json"] = json.dumps(run.task_ids or [])
        payload["decision_ids_json"] = json.dumps(run.decision_ids or [])
        payload["evidence_ids_json"] = json.dumps(run.evidence_ids or [])
        payload["metadata_json"] = _encode_json(run.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO workflow_runs (
                    run_id,
                    template_id,
                    title,
                    summary,
                    status,
                    owner_scope,
                    owner_agent_id,
                    industry_instance_id,
                    parameter_payload_json,
                    preview_payload_json,
                    task_ids_json,
                    decision_ids_json,
                    evidence_ids_json,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :run_id,
                    :template_id,
                    :title,
                    :summary,
                    :status,
                    :owner_scope,
                    :owner_agent_id,
                    :industry_instance_id,
                    :parameter_payload_json,
                    :preview_payload_json,
                    :task_ids_json,
                    :decision_ids_json,
                    :evidence_ids_json,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(run_id) DO UPDATE SET
                    template_id = excluded.template_id,
                    title = excluded.title,
                    summary = excluded.summary,
                    status = excluded.status,
                    owner_scope = excluded.owner_scope,
                    owner_agent_id = excluded.owner_agent_id,
                    industry_instance_id = excluded.industry_instance_id,
                    parameter_payload_json = excluded.parameter_payload_json,
                    preview_payload_json = excluded.preview_payload_json,
                    task_ids_json = excluded.task_ids_json,
                    decision_ids_json = excluded.decision_ids_json,
                    evidence_ids_json = excluded.evidence_ids_json,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return run

    def delete_run(self, run_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM workflow_runs WHERE run_id = ?",
                (run_id,),
            )
        return cursor.rowcount > 0


class SqliteExecutionRoutineRepository(BaseExecutionRoutineRepository):
    """SQLite-backed execution routine repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_routine(self, routine_id: str) -> ExecutionRoutineRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM execution_routines WHERE id = ?",
                (routine_id,),
            ).fetchone()
        return _execution_routine_from_row(row)

    def list_routines(
        self,
        *,
        status: str | None = None,
        owner_scope: str | None = None,
        owner_agent_id: str | None = None,
        engine_kind: str | None = None,
        trigger_kind: str | None = None,
        routine_ids: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[ExecutionRoutineRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if owner_scope is not None:
            clauses.append("owner_scope = ?")
            params.append(owner_scope)
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        if engine_kind is not None:
            clauses.append("engine_kind = ?")
            params.append(engine_kind)
        if trigger_kind is not None:
            clauses.append("trigger_kind = ?")
            params.append(trigger_kind)
        if routine_ids:
            placeholders = ", ".join("?" for _ in routine_ids)
            clauses.append(f"id IN ({placeholders})")
            params.extend(routine_ids)
        query = "SELECT * FROM execution_routines"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, id DESC"
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            routine
            for routine in (_execution_routine_from_row(row) for row in rows)
            if routine is not None
        ]

    def upsert_routine(
        self,
        routine: ExecutionRoutineRecord,
    ) -> ExecutionRoutineRecord:
        payload = _payload(routine)
        payload["session_requirements_json"] = _encode_json(routine.session_requirements)
        payload["isolation_policy_json"] = _encode_json(routine.isolation_policy)
        payload["lock_scope_json"] = json.dumps(routine.lock_scope or [])
        payload["input_schema_json"] = _encode_json(routine.input_schema)
        payload["preconditions_json"] = json.dumps(routine.preconditions or [])
        payload["expected_observations_json"] = json.dumps(
            routine.expected_observations or [],
        )
        payload["action_contract_json"] = json.dumps(routine.action_contract or [])
        payload["success_signature_json"] = _encode_json(routine.success_signature)
        payload["drift_signals_json"] = json.dumps(routine.drift_signals or [])
        payload["replay_policy_json"] = _encode_json(routine.replay_policy)
        payload["fallback_policy_json"] = _encode_json(routine.fallback_policy)
        payload["evidence_expectations_json"] = json.dumps(
            routine.evidence_expectations or [],
        )
        payload["source_evidence_ids_json"] = json.dumps(routine.source_evidence_ids or [])
        payload["metadata_json"] = _encode_json(routine.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO execution_routines (
                    id,
                    routine_key,
                    name,
                    summary,
                    status,
                    owner_scope,
                    owner_agent_id,
                    source_capability_id,
                    trigger_kind,
                    engine_kind,
                    environment_kind,
                    session_requirements_json,
                    isolation_policy_json,
                    lock_scope_json,
                    input_schema_json,
                    preconditions_json,
                    expected_observations_json,
                    action_contract_json,
                    success_signature_json,
                    drift_signals_json,
                    replay_policy_json,
                    fallback_policy_json,
                    risk_baseline,
                    evidence_expectations_json,
                    source_evidence_ids_json,
                    metadata_json,
                    last_verified_at,
                    success_rate,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :routine_key,
                    :name,
                    :summary,
                    :status,
                    :owner_scope,
                    :owner_agent_id,
                    :source_capability_id,
                    :trigger_kind,
                    :engine_kind,
                    :environment_kind,
                    :session_requirements_json,
                    :isolation_policy_json,
                    :lock_scope_json,
                    :input_schema_json,
                    :preconditions_json,
                    :expected_observations_json,
                    :action_contract_json,
                    :success_signature_json,
                    :drift_signals_json,
                    :replay_policy_json,
                    :fallback_policy_json,
                    :risk_baseline,
                    :evidence_expectations_json,
                    :source_evidence_ids_json,
                    :metadata_json,
                    :last_verified_at,
                    :success_rate,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    routine_key = excluded.routine_key,
                    name = excluded.name,
                    summary = excluded.summary,
                    status = excluded.status,
                    owner_scope = excluded.owner_scope,
                    owner_agent_id = excluded.owner_agent_id,
                    source_capability_id = excluded.source_capability_id,
                    trigger_kind = excluded.trigger_kind,
                    engine_kind = excluded.engine_kind,
                    environment_kind = excluded.environment_kind,
                    session_requirements_json = excluded.session_requirements_json,
                    isolation_policy_json = excluded.isolation_policy_json,
                    lock_scope_json = excluded.lock_scope_json,
                    input_schema_json = excluded.input_schema_json,
                    preconditions_json = excluded.preconditions_json,
                    expected_observations_json = excluded.expected_observations_json,
                    action_contract_json = excluded.action_contract_json,
                    success_signature_json = excluded.success_signature_json,
                    drift_signals_json = excluded.drift_signals_json,
                    replay_policy_json = excluded.replay_policy_json,
                    fallback_policy_json = excluded.fallback_policy_json,
                    risk_baseline = excluded.risk_baseline,
                    evidence_expectations_json = excluded.evidence_expectations_json,
                    source_evidence_ids_json = excluded.source_evidence_ids_json,
                    metadata_json = excluded.metadata_json,
                    last_verified_at = excluded.last_verified_at,
                    success_rate = excluded.success_rate,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return routine

    def delete_routine(self, routine_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM execution_routines WHERE id = ?",
                (routine_id,),
            )
        return cursor.rowcount > 0


class SqliteRoutineRunRepository(BaseRoutineRunRepository):
    """SQLite-backed routine run repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_run(self, run_id: str) -> RoutineRunRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM routine_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        return _routine_run_from_row(row)

    def list_runs(
        self,
        *,
        routine_id: str | None = None,
        status: str | None = None,
        source_type: str | None = None,
        owner_agent_id: str | None = None,
        failure_class: str | None = None,
        limit: int | None = None,
    ) -> list[RoutineRunRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if routine_id is not None:
            clauses.append("routine_id = ?")
            params.append(routine_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if source_type is not None:
            clauses.append("source_type = ?")
            params.append(source_type)
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        if failure_class is not None:
            clauses.append("failure_class = ?")
            params.append(failure_class)
        query = "SELECT * FROM routine_runs"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY started_at DESC, id DESC"
        if isinstance(limit, int) and limit >= 0:
            query = f"{query} LIMIT {int(limit)}"
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            run
            for run in (_routine_run_from_row(row) for row in rows)
            if run is not None
        ]

    def upsert_run(self, run: RoutineRunRecord) -> RoutineRunRecord:
        payload = _payload(run)
        payload["input_payload_json"] = _encode_json(run.input_payload)
        payload["evidence_ids_json"] = json.dumps(run.evidence_ids or [])
        payload["metadata_json"] = _encode_json(run.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO routine_runs (
                    id,
                    routine_id,
                    source_type,
                    source_ref,
                    status,
                    input_payload_json,
                    owner_agent_id,
                    owner_scope,
                    environment_id,
                    session_id,
                    lease_ref,
                    checkpoint_ref,
                    deterministic_result,
                    failure_class,
                    fallback_mode,
                    fallback_task_id,
                    decision_request_id,
                    output_summary,
                    evidence_ids_json,
                    metadata_json,
                    started_at,
                    completed_at,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :routine_id,
                    :source_type,
                    :source_ref,
                    :status,
                    :input_payload_json,
                    :owner_agent_id,
                    :owner_scope,
                    :environment_id,
                    :session_id,
                    :lease_ref,
                    :checkpoint_ref,
                    :deterministic_result,
                    :failure_class,
                    :fallback_mode,
                    :fallback_task_id,
                    :decision_request_id,
                    :output_summary,
                    :evidence_ids_json,
                    :metadata_json,
                    :started_at,
                    :completed_at,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    routine_id = excluded.routine_id,
                    source_type = excluded.source_type,
                    source_ref = excluded.source_ref,
                    status = excluded.status,
                    input_payload_json = excluded.input_payload_json,
                    owner_agent_id = excluded.owner_agent_id,
                    owner_scope = excluded.owner_scope,
                    environment_id = excluded.environment_id,
                    session_id = excluded.session_id,
                    lease_ref = excluded.lease_ref,
                    checkpoint_ref = excluded.checkpoint_ref,
                    deterministic_result = excluded.deterministic_result,
                    failure_class = excluded.failure_class,
                    fallback_mode = excluded.fallback_mode,
                    fallback_task_id = excluded.fallback_task_id,
                    decision_request_id = excluded.decision_request_id,
                    output_summary = excluded.output_summary,
                    evidence_ids_json = excluded.evidence_ids_json,
                    metadata_json = excluded.metadata_json,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return run

    def delete_run(self, run_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM routine_runs WHERE id = ?",
                (run_id,),
            )
        return cursor.rowcount > 0


class SqliteWorkflowPresetRepository(BaseWorkflowPresetRepository):
    """SQLite-backed workflow preset repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_preset(self, preset_id: str) -> WorkflowPresetRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_presets WHERE id = ?",
                (preset_id,),
            ).fetchone()
        return _workflow_preset_from_row(row)

    def list_presets(
        self,
        *,
        template_id: str,
        industry_scope: str | None = None,
        owner_scope: str | None = None,
    ) -> list[WorkflowPresetRecord]:
        clauses = ["template_id = ?"]
        params: list[Any] = [template_id]
        if industry_scope is not None:
            clauses.append("(industry_scope = ? OR industry_scope IS NULL OR industry_scope = '')")
            params.append(industry_scope)
        if owner_scope is not None:
            clauses.append("(owner_scope = ? OR owner_scope IS NULL OR owner_scope = '')")
            params.append(owner_scope)
        query = (
            "SELECT * FROM workflow_presets "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY updated_at DESC, name ASC"
        )
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_workflow_preset_from_row(row) for row in rows]

    def upsert_preset(self, preset: WorkflowPresetRecord) -> WorkflowPresetRecord:
        payload = _payload(preset)
        payload["parameter_overrides_json"] = _encode_json(preset.parameter_overrides)
        payload["metadata_json"] = _encode_json(preset.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO workflow_presets (
                    id,
                    template_id,
                    name,
                    summary,
                    owner_scope,
                    industry_scope,
                    parameter_overrides_json,
                    created_by,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :template_id,
                    :name,
                    :summary,
                    :owner_scope,
                    :industry_scope,
                    :parameter_overrides_json,
                    :created_by,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    template_id = excluded.template_id,
                    name = excluded.name,
                    summary = excluded.summary,
                    owner_scope = excluded.owner_scope,
                    industry_scope = excluded.industry_scope,
                    parameter_overrides_json = excluded.parameter_overrides_json,
                    created_by = excluded.created_by,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return preset

    def delete_preset(self, preset_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM workflow_presets WHERE id = ?",
                (preset_id,),
            )
        return cursor.rowcount > 0
