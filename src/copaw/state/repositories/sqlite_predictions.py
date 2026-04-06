# -*- coding: utf-8 -*-
from __future__ import annotations

from .sqlite_shared import *  # noqa: F401,F403


class SqlitePredictionCaseRepository(BasePredictionCaseRepository):
    """SQLite-backed prediction case repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_case(self, case_id: str) -> PredictionCaseRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM prediction_cases WHERE case_id = ?",
                (case_id,),
            ).fetchone()
        return _prediction_case_from_row(row)

    def list_cases(
        self,
        *,
        case_kind: str | None = None,
        status: str | None = None,
        industry_instance_id: str | None = None,
        owner_scope: str | None = None,
        owner_agent_id: str | None = None,
        case_ids: Sequence[str] | None = None,
        activity_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[PredictionCaseRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if case_kind is not None:
            clauses.append("case_kind = ?")
            params.append(case_kind)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if industry_instance_id is not None:
            clauses.append("industry_instance_id = ?")
            params.append(industry_instance_id)
        if owner_scope is not None:
            clauses.append("owner_scope = ?")
            params.append(owner_scope)
        if owner_agent_id is not None:
            clauses.append("owner_agent_id = ?")
            params.append(owner_agent_id)
        if case_ids:
            placeholders = ", ".join("?" for _ in case_ids)
            clauses.append(f"case_id IN ({placeholders})")
            params.extend(case_ids)
        if activity_since is not None:
            encoded = _encode_datetime_value(activity_since)
            clauses.append("(created_at >= ? OR updated_at >= ?)")
            params.extend([encoded, encoded])
        query = "SELECT * FROM prediction_cases"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, case_id DESC"
        if limit is not None and limit >= 0:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_prediction_case_from_row(row) for row in rows]

    def upsert_case(self, record: PredictionCaseRecord) -> PredictionCaseRecord:
        payload = _payload(record)
        payload["input_payload_json"] = _encode_json(record.input_payload)
        payload["metadata_json"] = _encode_json(record.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO prediction_cases (
                    case_id,
                    title,
                    summary,
                    case_kind,
                    status,
                    topic_type,
                    owner_scope,
                    owner_agent_id,
                    industry_instance_id,
                    workflow_run_id,
                    question,
                    time_window_days,
                    overall_confidence,
                    primary_recommendation_id,
                    input_payload_json,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :case_id,
                    :title,
                    :summary,
                    :case_kind,
                    :status,
                    :topic_type,
                    :owner_scope,
                    :owner_agent_id,
                    :industry_instance_id,
                    :workflow_run_id,
                    :question,
                    :time_window_days,
                    :overall_confidence,
                    :primary_recommendation_id,
                    :input_payload_json,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(case_id) DO UPDATE SET
                    title = excluded.title,
                    summary = excluded.summary,
                    case_kind = excluded.case_kind,
                    status = excluded.status,
                    topic_type = excluded.topic_type,
                    owner_scope = excluded.owner_scope,
                    owner_agent_id = excluded.owner_agent_id,
                    industry_instance_id = excluded.industry_instance_id,
                    workflow_run_id = excluded.workflow_run_id,
                    question = excluded.question,
                    time_window_days = excluded.time_window_days,
                    overall_confidence = excluded.overall_confidence,
                    primary_recommendation_id = excluded.primary_recommendation_id,
                    input_payload_json = excluded.input_payload_json,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return record

    def delete_case(self, case_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM prediction_cases WHERE case_id = ?",
                (case_id,),
            )
        return cursor.rowcount > 0


class SqlitePredictionScenarioRepository(BasePredictionScenarioRepository):
    """SQLite-backed prediction scenario repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_scenario(self, scenario_id: str) -> PredictionScenarioRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM prediction_scenarios WHERE scenario_id = ?",
                (scenario_id,),
            ).fetchone()
        return _prediction_scenario_from_row(row)

    def list_scenarios(self, *, case_id: str) -> list[PredictionScenarioRecord]:
        with self._store.connection() as conn:
            rows = conn.execute(
                (
                    "SELECT * FROM prediction_scenarios "
                    "WHERE case_id = ? "
                    "ORDER BY CASE scenario_kind "
                    "WHEN 'best' THEN 0 WHEN 'base' THEN 1 WHEN 'worst' THEN 2 ELSE 3 END, "
                    "updated_at DESC"
                ),
                (case_id,),
            ).fetchall()
        return [_prediction_scenario_from_row(row) for row in rows]

    def upsert_scenario(
        self,
        record: PredictionScenarioRecord,
    ) -> PredictionScenarioRecord:
        payload = _payload(record)
        payload["assumptions_json"] = json.dumps(record.assumptions or [])
        payload["risk_factors_json"] = json.dumps(record.risk_factors or [])
        payload["recommendation_ids_json"] = json.dumps(record.recommendation_ids or [])
        payload["metadata_json"] = _encode_json(record.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO prediction_scenarios (
                    scenario_id,
                    case_id,
                    scenario_kind,
                    title,
                    summary,
                    confidence,
                    goal_delta,
                    task_load_delta,
                    risk_delta,
                    resource_delta,
                    externality_delta,
                    assumptions_json,
                    risk_factors_json,
                    recommendation_ids_json,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :scenario_id,
                    :case_id,
                    :scenario_kind,
                    :title,
                    :summary,
                    :confidence,
                    :goal_delta,
                    :task_load_delta,
                    :risk_delta,
                    :resource_delta,
                    :externality_delta,
                    :assumptions_json,
                    :risk_factors_json,
                    :recommendation_ids_json,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(scenario_id) DO UPDATE SET
                    case_id = excluded.case_id,
                    scenario_kind = excluded.scenario_kind,
                    title = excluded.title,
                    summary = excluded.summary,
                    confidence = excluded.confidence,
                    goal_delta = excluded.goal_delta,
                    task_load_delta = excluded.task_load_delta,
                    risk_delta = excluded.risk_delta,
                    resource_delta = excluded.resource_delta,
                    externality_delta = excluded.externality_delta,
                    assumptions_json = excluded.assumptions_json,
                    risk_factors_json = excluded.risk_factors_json,
                    recommendation_ids_json = excluded.recommendation_ids_json,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return record

    def delete_scenario(self, scenario_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM prediction_scenarios WHERE scenario_id = ?",
                (scenario_id,),
            )
        return cursor.rowcount > 0

    def delete_for_case(self, case_id: str) -> int:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM prediction_scenarios WHERE case_id = ?",
                (case_id,),
            )
        return int(cursor.rowcount or 0)


class SqlitePredictionSignalRepository(BasePredictionSignalRepository):
    """SQLite-backed prediction signal repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_signal(self, signal_id: str) -> PredictionSignalRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM prediction_signals WHERE signal_id = ?",
                (signal_id,),
            ).fetchone()
        return _prediction_signal_from_row(row)

    def list_signals(self, *, case_id: str) -> list[PredictionSignalRecord]:
        with self._store.connection() as conn:
            rows = conn.execute(
                (
                    "SELECT * FROM prediction_signals "
                    "WHERE case_id = ? "
                    "ORDER BY strength DESC, updated_at DESC, signal_id ASC"
                ),
                (case_id,),
            ).fetchall()
        return [_prediction_signal_from_row(row) for row in rows]

    def upsert_signal(self, record: PredictionSignalRecord) -> PredictionSignalRecord:
        payload = _payload(record)
        payload["payload_json"] = _encode_json(record.payload)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO prediction_signals (
                    signal_id,
                    case_id,
                    label,
                    summary,
                    source_kind,
                    source_ref,
                    direction,
                    strength,
                    metric_key,
                    report_id,
                    evidence_id,
                    agent_id,
                    workflow_run_id,
                    payload_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :signal_id,
                    :case_id,
                    :label,
                    :summary,
                    :source_kind,
                    :source_ref,
                    :direction,
                    :strength,
                    :metric_key,
                    :report_id,
                    :evidence_id,
                    :agent_id,
                    :workflow_run_id,
                    :payload_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(signal_id) DO UPDATE SET
                    case_id = excluded.case_id,
                    label = excluded.label,
                    summary = excluded.summary,
                    source_kind = excluded.source_kind,
                    source_ref = excluded.source_ref,
                    direction = excluded.direction,
                    strength = excluded.strength,
                    metric_key = excluded.metric_key,
                    report_id = excluded.report_id,
                    evidence_id = excluded.evidence_id,
                    agent_id = excluded.agent_id,
                    workflow_run_id = excluded.workflow_run_id,
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return record

    def delete_signal(self, signal_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM prediction_signals WHERE signal_id = ?",
                (signal_id,),
            )
        return cursor.rowcount > 0

    def delete_for_case(self, case_id: str) -> int:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM prediction_signals WHERE case_id = ?",
                (case_id,),
            )
        return int(cursor.rowcount or 0)


class SqlitePredictionRecommendationRepository(BasePredictionRecommendationRepository):
    """SQLite-backed prediction recommendation repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_recommendation(
        self,
        recommendation_id: str,
    ) -> PredictionRecommendationRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM prediction_recommendations WHERE recommendation_id = ?",
                (recommendation_id,),
            ).fetchone()
        return _prediction_recommendation_from_row(row)

    def list_recommendations(
        self,
        *,
        case_id: str | None = None,
        case_ids: Sequence[str] | None = None,
        status: str | None = None,
        auto_eligible: bool | None = None,
        target_agent_id: str | None = None,
        activity_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[PredictionRecommendationRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if case_id is not None:
            clauses.append("case_id = ?")
            params.append(case_id)
        if case_ids:
            placeholders = ", ".join("?" for _ in case_ids)
            clauses.append(f"case_id IN ({placeholders})")
            params.extend(case_ids)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if auto_eligible is not None:
            clauses.append("auto_eligible = ?")
            params.append(1 if auto_eligible else 0)
        if target_agent_id is not None:
            clauses.append("target_agent_id = ?")
            params.append(target_agent_id)
        if activity_since is not None:
            encoded = _encode_datetime_value(activity_since)
            clauses.append("(created_at >= ? OR updated_at >= ?)")
            params.extend([encoded, encoded])
        query = "SELECT * FROM prediction_recommendations"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY priority DESC, updated_at DESC, recommendation_id ASC"
        if limit is not None and limit >= 0:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_prediction_recommendation_from_row(row) for row in rows]

    def upsert_recommendation(
        self,
        record: PredictionRecommendationRecord,
    ) -> PredictionRecommendationRecord:
        payload = _payload(record)
        payload["executable"] = 1 if record.executable else 0
        payload["auto_eligible"] = 1 if record.auto_eligible else 0
        payload["auto_executed"] = 1 if record.auto_executed else 0
        payload["target_capability_ids_json"] = json.dumps(record.target_capability_ids or [])
        payload["action_payload_json"] = _encode_json(record.action_payload)
        payload["metadata_json"] = _encode_json(record.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO prediction_recommendations (
                    recommendation_id,
                    case_id,
                    recommendation_type,
                    title,
                    summary,
                    priority,
                    confidence,
                    risk_level,
                    action_kind,
                    executable,
                    auto_eligible,
                    auto_executed,
                    status,
                    target_agent_id,
                    target_goal_id,
                    target_schedule_id,
                    target_capability_ids_json,
                    decision_request_id,
                    execution_task_id,
                    execution_evidence_id,
                    outcome_summary,
                    action_payload_json,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :recommendation_id,
                    :case_id,
                    :recommendation_type,
                    :title,
                    :summary,
                    :priority,
                    :confidence,
                    :risk_level,
                    :action_kind,
                    :executable,
                    :auto_eligible,
                    :auto_executed,
                    :status,
                    :target_agent_id,
                    :target_goal_id,
                    :target_schedule_id,
                    :target_capability_ids_json,
                    :decision_request_id,
                    :execution_task_id,
                    :execution_evidence_id,
                    :outcome_summary,
                    :action_payload_json,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(recommendation_id) DO UPDATE SET
                    case_id = excluded.case_id,
                    recommendation_type = excluded.recommendation_type,
                    title = excluded.title,
                    summary = excluded.summary,
                    priority = excluded.priority,
                    confidence = excluded.confidence,
                    risk_level = excluded.risk_level,
                    action_kind = excluded.action_kind,
                    executable = excluded.executable,
                    auto_eligible = excluded.auto_eligible,
                    auto_executed = excluded.auto_executed,
                    status = excluded.status,
                    target_agent_id = excluded.target_agent_id,
                    target_goal_id = excluded.target_goal_id,
                    target_schedule_id = excluded.target_schedule_id,
                    target_capability_ids_json = excluded.target_capability_ids_json,
                    decision_request_id = excluded.decision_request_id,
                    execution_task_id = excluded.execution_task_id,
                    execution_evidence_id = excluded.execution_evidence_id,
                    outcome_summary = excluded.outcome_summary,
                    action_payload_json = excluded.action_payload_json,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return record

    def delete_recommendation(self, recommendation_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM prediction_recommendations WHERE recommendation_id = ?",
                (recommendation_id,),
            )
        return cursor.rowcount > 0

    def delete_for_case(self, case_id: str) -> int:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM prediction_recommendations WHERE case_id = ?",
                (case_id,),
            )
        return int(cursor.rowcount or 0)


class SqlitePredictionReviewRepository(BasePredictionReviewRepository):
    """SQLite-backed prediction review repository."""

    def __init__(self, store: SQLiteStateStore):
        self._store = store
        self._store.initialize()

    def get_review(self, review_id: str) -> PredictionReviewRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM prediction_reviews WHERE review_id = ?",
                (review_id,),
            ).fetchone()
        return _prediction_review_from_row(row)

    def list_reviews(
        self,
        *,
        case_id: str | None = None,
        case_ids: Sequence[str] | None = None,
        recommendation_id: str | None = None,
        activity_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[PredictionReviewRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if case_id is not None:
            clauses.append("case_id = ?")
            params.append(case_id)
        if case_ids:
            placeholders = ", ".join("?" for _ in case_ids)
            clauses.append(f"case_id IN ({placeholders})")
            params.extend(case_ids)
        if recommendation_id is not None:
            clauses.append("recommendation_id = ?")
            params.append(recommendation_id)
        if activity_since is not None:
            encoded = _encode_datetime_value(activity_since)
            clauses.append("(created_at >= ? OR updated_at >= ?)")
            params.extend([encoded, encoded])
        query = "SELECT * FROM prediction_reviews"
        if clauses:
            query = f"{query} WHERE {' AND '.join(clauses)}"
        query = f"{query} ORDER BY updated_at DESC, review_id DESC"
        if limit is not None and limit >= 0:
            query = f"{query} LIMIT ?"
            params.append(limit)
        with self._store.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_prediction_review_from_row(row) for row in rows]

    def upsert_review(self, record: PredictionReviewRecord) -> PredictionReviewRecord:
        payload = _payload(record)
        payload["adopted"] = (
            None if record.adopted is None else (1 if record.adopted else 0)
        )
        payload["actual_payload_json"] = _encode_json(record.actual_payload)
        payload["metadata_json"] = _encode_json(record.metadata)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO prediction_reviews (
                    review_id,
                    case_id,
                    recommendation_id,
                    reviewer,
                    summary,
                    outcome,
                    adopted,
                    benefit_score,
                    actual_payload_json,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :review_id,
                    :case_id,
                    :recommendation_id,
                    :reviewer,
                    :summary,
                    :outcome,
                    :adopted,
                    :benefit_score,
                    :actual_payload_json,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(review_id) DO UPDATE SET
                    case_id = excluded.case_id,
                    recommendation_id = excluded.recommendation_id,
                    reviewer = excluded.reviewer,
                    summary = excluded.summary,
                    outcome = excluded.outcome,
                    adopted = excluded.adopted,
                    benefit_score = excluded.benefit_score,
                    actual_payload_json = excluded.actual_payload_json,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return record

    def delete_review(self, review_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM prediction_reviews WHERE review_id = ?",
                (review_id,),
            )
        return cursor.rowcount > 0


def _prediction_case_from_row(
    row: sqlite3.Row | None,
) -> PredictionCaseRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["input_payload"] = _decode_json(payload.pop("input_payload_json", "{}"))
    payload["metadata"] = _decode_json(payload.pop("metadata_json", "{}"))
    return PredictionCaseRecord.model_validate(payload)


def _prediction_scenario_from_row(
    row: sqlite3.Row | None,
) -> PredictionScenarioRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["assumptions"] = _decode_json_list(payload.pop("assumptions_json", "[]")) or []
    payload["risk_factors"] = _decode_json_list(payload.pop("risk_factors_json", "[]")) or []
    payload["recommendation_ids"] = (
        _decode_json_list(payload.pop("recommendation_ids_json", "[]")) or []
    )
    payload["metadata"] = _decode_json(payload.pop("metadata_json", "{}"))
    return PredictionScenarioRecord.model_validate(payload)


def _prediction_signal_from_row(
    row: sqlite3.Row | None,
) -> PredictionSignalRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["payload"] = _decode_json(payload.pop("payload_json", "{}"))
    return PredictionSignalRecord.model_validate(payload)


def _prediction_recommendation_from_row(
    row: sqlite3.Row | None,
) -> PredictionRecommendationRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["executable"] = bool(payload.get("executable", 0))
    payload["auto_eligible"] = bool(payload.get("auto_eligible", 0))
    payload["auto_executed"] = bool(payload.get("auto_executed", 0))
    payload["target_capability_ids"] = (
        _decode_json_list(payload.pop("target_capability_ids_json", "[]")) or []
    )
    payload["action_payload"] = _decode_json(payload.pop("action_payload_json", "{}"))
    payload["metadata"] = _decode_json(payload.pop("metadata_json", "{}"))
    return PredictionRecommendationRecord.model_validate(payload)


def _prediction_review_from_row(
    row: sqlite3.Row | None,
) -> PredictionReviewRecord | None:
    if row is None:
        return None
    payload = dict(row)
    adopted = payload.get("adopted")
    payload["adopted"] = None if adopted is None else bool(adopted)
    payload["actual_payload"] = _decode_json(payload.pop("actual_payload_json", "{}"))
    payload["metadata"] = _decode_json(payload.pop("metadata_json", "{}"))
    return PredictionReviewRecord.model_validate(payload)


def _workflow_template_from_row(
    row: sqlite3.Row | None,
) -> WorkflowTemplateRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["industry_tags"] = _decode_json_list(payload.pop("industry_tags_json", "[]")) or []
    payload["team_modes"] = _decode_json_list(payload.pop("team_modes_json", "[]")) or []
    payload["dependency_capability_ids"] = (
        _decode_json_list(payload.pop("dependency_capability_ids_json", "[]")) or []
    )
    payload["suggested_role_ids"] = (
        _decode_json_list(payload.pop("suggested_role_ids_json", "[]")) or []
    )
    payload["parameter_schema"] = _decode_json(payload.pop("parameter_schema_json", "{}"))
    payload["step_specs"] = _decode_any_json(payload.pop("step_specs_json", "[]"))
    if not isinstance(payload["step_specs"], list):
        payload["step_specs"] = []
    payload["metadata"] = _decode_json(payload.pop("metadata_json", "{}"))
    return WorkflowTemplateRecord.model_validate(payload)


def _workflow_run_from_row(row: sqlite3.Row | None) -> WorkflowRunRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["parameter_payload"] = _decode_json(payload.pop("parameter_payload_json", "{}"))
    payload["preview_payload"] = _decode_json(payload.pop("preview_payload_json", "{}"))
    payload["task_ids"] = _decode_json_list(payload.pop("task_ids_json", "[]")) or []
    payload["decision_ids"] = _decode_json_list(payload.pop("decision_ids_json", "[]")) or []
    payload["evidence_ids"] = _decode_json_list(payload.pop("evidence_ids_json", "[]")) or []
    payload["metadata"] = _decode_json(payload.pop("metadata_json", "{}"))
    return WorkflowRunRecord.model_validate(payload)


def _execution_routine_from_row(
    row: sqlite3.Row | None,
) -> ExecutionRoutineRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["session_requirements"] = _decode_json(
        payload.pop("session_requirements_json", "{}"),
    )
    payload["isolation_policy"] = _decode_json(
        payload.pop("isolation_policy_json", "{}"),
    )
    payload["lock_scope"] = _decode_any_json(payload.pop("lock_scope_json", "[]"))
    if not isinstance(payload["lock_scope"], list):
        payload["lock_scope"] = []
    payload["input_schema"] = _decode_json(payload.pop("input_schema_json", "{}"))
    payload["preconditions"] = _decode_any_json(payload.pop("preconditions_json", "[]"))
    if not isinstance(payload["preconditions"], list):
        payload["preconditions"] = []
    payload["expected_observations"] = _decode_any_json(
        payload.pop("expected_observations_json", "[]"),
    )
    if not isinstance(payload["expected_observations"], list):
        payload["expected_observations"] = []
    payload["action_contract"] = _decode_any_json(payload.pop("action_contract_json", "[]"))
    if not isinstance(payload["action_contract"], list):
        payload["action_contract"] = []
    payload["success_signature"] = _decode_json(
        payload.pop("success_signature_json", "{}"),
    )
    payload["drift_signals"] = _decode_any_json(payload.pop("drift_signals_json", "[]"))
    if not isinstance(payload["drift_signals"], list):
        payload["drift_signals"] = []
    payload["replay_policy"] = _decode_json(payload.pop("replay_policy_json", "{}"))
    payload["fallback_policy"] = _decode_json(payload.pop("fallback_policy_json", "{}"))
    payload["evidence_expectations"] = (
        _decode_json_list(payload.pop("evidence_expectations_json", "[]")) or []
    )
    payload["source_evidence_ids"] = (
        _decode_json_list(payload.pop("source_evidence_ids_json", "[]")) or []
    )
    payload["metadata"] = _decode_json(payload.pop("metadata_json", "{}"))
    return ExecutionRoutineRecord.model_validate(payload)


def _routine_run_from_row(row: sqlite3.Row | None) -> RoutineRunRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["input_payload"] = _decode_json(payload.pop("input_payload_json", "{}"))
    payload["evidence_ids"] = _decode_json_list(payload.pop("evidence_ids_json", "[]")) or []
    payload["metadata"] = _decode_json(payload.pop("metadata_json", "{}"))
    return RoutineRunRecord.model_validate(payload)


def _workflow_preset_from_row(
    row: sqlite3.Row | None,
) -> WorkflowPresetRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["parameter_overrides"] = _decode_json(
        payload.pop("parameter_overrides_json", "{}"),
    )
    payload["metadata"] = _decode_json(payload.pop("metadata_json", "{}"))
    return WorkflowPresetRecord.model_validate(payload)


def _fixed_sop_template_from_row(
    row: sqlite3.Row | None,
) -> FixedSopTemplateRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["suggested_role_ids"] = (
        _decode_json_list(payload.pop("suggested_role_ids_json", "[]")) or []
    )
    payload["industry_tags"] = (
        _decode_json_list(payload.pop("industry_tags_json", "[]")) or []
    )
    payload["capability_tags"] = (
        _decode_json_list(payload.pop("capability_tags_json", "[]")) or []
    )
    payload["input_schema"] = _decode_json(payload.pop("input_schema_json", "{}"))
    payload["output_schema"] = _decode_json(payload.pop("output_schema_json", "{}"))
    payload["writeback_contract"] = _decode_json(
        payload.pop("writeback_contract_json", "{}"),
    )
    payload["node_graph"] = _decode_any_json(payload.pop("node_graph_json", "[]"))
    if not isinstance(payload["node_graph"], list):
        payload["node_graph"] = []
    payload["metadata"] = _decode_json(payload.pop("metadata_json", "{}"))
    return FixedSopTemplateRecord.model_validate(payload)


def _fixed_sop_binding_from_row(
    row: sqlite3.Row | None,
) -> FixedSopBindingRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["input_mapping"] = _decode_json(payload.pop("input_mapping_json", "{}"))
    payload["output_mapping"] = _decode_json(
        payload.pop("output_mapping_json", "{}"),
    )
    payload["timeout_policy"] = _decode_json(
        payload.pop("timeout_policy_json", "{}"),
    )
    payload["retry_policy"] = _decode_json(payload.pop("retry_policy_json", "{}"))
    payload["metadata"] = _decode_json(payload.pop("metadata_json", "{}"))
    return FixedSopBindingRecord.model_validate(payload)


def _encode_json(value: Any) -> str:
    return json.dumps(value or {}, sort_keys=True)


def _decode_json(value: str) -> dict[str, Any]:
    payload = json.loads(value or "{}")
    return payload if isinstance(payload, dict) else {"value": payload}


def _decode_any_json(value: str | None) -> Any:
    if value in (None, ""):
        return None
    return json.loads(value)


def _decode_json_list(value: str | None) -> list[str] | None:
    if value in (None, ""):
        return None
    payload = json.loads(value)
    if not isinstance(payload, list):
        return None
    items = [str(item) for item in payload if item is not None]
    return items or []


def _decode_json_mapping(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    payload = json.loads(value)
    return payload if isinstance(payload, dict) else {}
