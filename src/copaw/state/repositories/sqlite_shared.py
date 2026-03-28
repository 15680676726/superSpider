# -*- coding: utf-8 -*-
"""SQLite repository implementations for the state layer."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Sequence, TypeVar

from pydantic import BaseModel

from ..models import (
    AgentCheckpointRecord,
    AgentLeaseRecord,
    AgentMailboxRecord,
    AgentProfileOverrideRecord,
    AgentReportRecord,
    AssignmentRecord,
    AgentRuntimeRecord,
    AgentThreadBindingRecord,
    BacklogItemRecord,
    CapabilityOverrideRecord,
    DecisionRequestRecord,
    ExecutionRoutineRecord,
    FixedSopBindingRecord,
    FixedSopTemplateRecord,
    GovernanceControlRecord,
    GoalRecord,
    GoalOverrideRecord,
    HumanAssistTaskRecord,
    IndustryInstanceRecord,
    OperatingCycleRecord,
    OperatingLaneRecord,
    PredictionCaseRecord,
    PredictionRecommendationRecord,
    PredictionReviewRecord,
    PredictionScenarioRecord,
    PredictionSignalRecord,
    RuntimeFrameRecord,
    RoutineRunRecord,
    ScheduleRecord,
    StrategyMemoryRecord,
    TaskRecord,
    TaskRuntimeRecord,
    WorkflowPresetRecord,
    WorkflowRunRecord,
    WorkflowTemplateRecord,
)
from ..models_knowledge import KnowledgeChunkRecord
from ..models_work_context import WorkContextRecord
from ..store import SQLiteStateStore
from .base import (
    BaseAgentCheckpointRepository,
    BaseAgentLeaseRepository,
    BaseAgentMailboxRepository,
    BaseAgentReportRepository,
    BaseAgentRuntimeRepository,
    BaseAssignmentRepository,
    BaseAgentThreadBindingRepository,
    BaseBacklogItemRepository,
    BaseDecisionRequestRepository,
    BaseExecutionRoutineRepository,
    BaseFixedSopBindingRepository,
    BaseFixedSopTemplateRepository,
    BaseGovernanceControlRepository,
    BaseGoalRepository,
    BaseHumanAssistTaskRepository,
    BaseIndustryInstanceRepository,
    BaseKnowledgeChunkRepository,
    BaseOperatingCycleRepository,
    BaseOperatingLaneRepository,
    BasePredictionCaseRepository,
    BasePredictionRecommendationRepository,
    BasePredictionReviewRepository,
    BasePredictionScenarioRepository,
    BasePredictionSignalRepository,
    BaseRuntimeFrameRepository,
    BaseRoutineRunRepository,
    BaseScheduleRepository,
    BaseStrategyMemoryRepository,
    BaseTaskRepository,
    BaseTaskRuntimeRepository,
    BaseWorkContextRepository,
    BaseWorkflowPresetRepository,
    BaseWorkflowRunRepository,
    BaseWorkflowTemplateRepository,
)

_ModelT = TypeVar("_ModelT", bound=BaseModel)

_TASK_COLUMNS = (
    "id",
    "goal_id",
    "title",
    "summary",
    "task_type",
    "status",
    "priority",
    "owner_agent_id",
    "parent_task_id",
    "seed_source",
    "constraints_summary",
    "acceptance_criteria",
    "current_risk_level",
    "created_at",
    "updated_at",
)
_HUMAN_ASSIST_TASK_COLUMNS = (
    "id",
    "industry_instance_id",
    "assignment_id",
    "task_id",
    "chat_thread_id",
    "title",
    "summary",
    "task_type",
    "reason_code",
    "reason_summary",
    "required_action",
    "submission_mode",
    "acceptance_mode",
    "acceptance_spec_json",
    "resume_checkpoint_ref",
    "status",
    "reward_preview_json",
    "reward_result_json",
    "block_evidence_refs_json",
    "submission_evidence_refs_json",
    "verification_evidence_refs_json",
    "submission_text",
    "submission_payload_json",
    "verification_payload_json",
    "issued_at",
    "submitted_at",
    "verified_at",
    "closed_at",
    "expires_at",
    "created_at",
    "updated_at",
)
_TASK_RUNTIME_COLUMNS = (
    "task_id",
    "runtime_status",
    "current_phase",
    "risk_level",
    "active_environment_id",
    "last_result_summary",
    "last_error_summary",
    "last_owner_agent_id",
    "last_evidence_id",
    "updated_at",
)
_RUNTIME_FRAME_COLUMNS = (
    "id",
    "task_id",
    "goal_summary",
    "owner_agent_id",
    "current_phase",
    "current_risk_level",
    "environment_summary",
    "evidence_summary",
    "constraints_summary",
    "capabilities_summary",
    "pending_decisions_summary",
    "budget_summary",
    "created_at",
)
_SCHEDULE_COLUMNS = (
    "id",
    "title",
    "cron",
    "timezone",
    "status",
    "enabled",
    "task_type",
    "target_channel",
    "target_user_id",
    "target_session_id",
    "last_run_at",
    "next_run_at",
    "last_error",
    "source_ref",
    "spec_payload_json",
    "created_at",
    "updated_at",
)
_WORKFLOW_TEMPLATE_COLUMNS = (
    "template_id",
    "title",
    "summary",
    "category",
    "status",
    "version",
    "industry_tags_json",
    "team_modes_json",
    "dependency_capability_ids_json",
    "suggested_role_ids_json",
    "owner_role_id",
    "parameter_schema_json",
    "step_specs_json",
    "metadata_json",
    "created_at",
    "updated_at",
)
_WORKFLOW_RUN_COLUMNS = (
    "run_id",
    "template_id",
    "title",
    "summary",
    "status",
    "owner_scope",
    "owner_agent_id",
    "industry_instance_id",
    "parameter_payload_json",
    "preview_payload_json",
    "goal_ids_json",
    "schedule_ids_json",
    "task_ids_json",
    "decision_ids_json",
    "evidence_ids_json",
    "metadata_json",
    "created_at",
    "updated_at",
)
_EXECUTION_ROUTINE_COLUMNS = (
    "id",
    "routine_key",
    "name",
    "summary",
    "status",
    "owner_scope",
    "owner_agent_id",
    "source_capability_id",
    "trigger_kind",
    "engine_kind",
    "environment_kind",
    "session_requirements_json",
    "isolation_policy_json",
    "lock_scope_json",
    "input_schema_json",
    "preconditions_json",
    "expected_observations_json",
    "action_contract_json",
    "success_signature_json",
    "drift_signals_json",
    "replay_policy_json",
    "fallback_policy_json",
    "risk_baseline",
    "evidence_expectations_json",
    "source_evidence_ids_json",
    "metadata_json",
    "last_verified_at",
    "success_rate",
    "created_at",
    "updated_at",
)
_ROUTINE_RUN_COLUMNS = (
    "id",
    "routine_id",
    "source_type",
    "source_ref",
    "status",
    "input_payload_json",
    "owner_agent_id",
    "owner_scope",
    "environment_id",
    "session_id",
    "lease_ref",
    "checkpoint_ref",
    "deterministic_result",
    "failure_class",
    "fallback_mode",
    "fallback_task_id",
    "decision_request_id",
    "output_summary",
    "evidence_ids_json",
    "metadata_json",
    "started_at",
    "completed_at",
    "created_at",
    "updated_at",
)
_PREDICTION_CASE_COLUMNS = (
    "case_id",
    "title",
    "summary",
    "case_kind",
    "status",
    "topic_type",
    "owner_scope",
    "owner_agent_id",
    "industry_instance_id",
    "workflow_run_id",
    "question",
    "time_window_days",
    "overall_confidence",
    "primary_recommendation_id",
    "input_payload_json",
    "metadata_json",
    "created_at",
    "updated_at",
)
_PREDICTION_SCENARIO_COLUMNS = (
    "scenario_id",
    "case_id",
    "scenario_kind",
    "title",
    "summary",
    "confidence",
    "goal_delta",
    "task_load_delta",
    "risk_delta",
    "resource_delta",
    "externality_delta",
    "assumptions_json",
    "risk_factors_json",
    "recommendation_ids_json",
    "metadata_json",
    "created_at",
    "updated_at",
)
_PREDICTION_SIGNAL_COLUMNS = (
    "signal_id",
    "case_id",
    "label",
    "summary",
    "source_kind",
    "source_ref",
    "direction",
    "strength",
    "metric_key",
    "report_id",
    "evidence_id",
    "agent_id",
    "workflow_run_id",
    "payload_json",
    "created_at",
    "updated_at",
)
_PREDICTION_RECOMMENDATION_COLUMNS = (
    "recommendation_id",
    "case_id",
    "recommendation_type",
    "title",
    "summary",
    "priority",
    "confidence",
    "risk_level",
    "action_kind",
    "executable",
    "auto_eligible",
    "auto_executed",
    "status",
    "target_agent_id",
    "target_goal_id",
    "target_schedule_id",
    "target_capability_ids_json",
    "decision_request_id",
    "execution_task_id",
    "execution_evidence_id",
    "outcome_summary",
    "action_payload_json",
    "metadata_json",
    "created_at",
    "updated_at",
)
_PREDICTION_REVIEW_COLUMNS = (
    "review_id",
    "case_id",
    "recommendation_id",
    "reviewer",
    "summary",
    "outcome",
    "adopted",
    "benefit_score",
    "actual_payload_json",
    "metadata_json",
    "created_at",
    "updated_at",
)
_AUTOPILOT_CONFIG_COLUMNS = (
    "config_id",
    "enabled",
    "owner_agent_id",
    "scan_window",
    "max_cases_per_run",
    "min_signal_strength",
    "min_confidence",
    "cooldown_minutes",
    "daily_model_budget",
    "auto_execute_enabled",
    "auto_execute_risk_levels_json",
    "max_auto_executions_per_day",
    "metadata_json",
    "created_at",
    "updated_at",
)
_DECISION_REQUEST_COLUMNS = (
    "id",
    "task_id",
    "decision_type",
    "risk_level",
    "summary",
    "status",
    "source_evidence_id",
    "source_patch_id",
    "requested_by",
    "resolution",
    "created_at",
    "resolved_at",
    "expires_at",
)
_CAPABILITY_OVERRIDE_COLUMNS = (
    "capability_id",
    "enabled",
    "forced_risk_level",
    "reason",
    "source_patch_id",
    "created_at",
    "updated_at",
)
_AGENT_RUNTIME_COLUMNS = (
    "agent_id",
    "actor_key",
    "actor_fingerprint",
    "actor_class",
    "desired_state",
    "runtime_status",
    "employment_mode",
    "activation_mode",
    "persistent",
    "industry_instance_id",
    "industry_role_id",
    "display_name",
    "role_name",
    "current_task_id",
    "current_mailbox_id",
    "current_environment_id",
    "queue_depth",
    "last_started_at",
    "last_heartbeat_at",
    "last_stopped_at",
    "last_error_summary",
    "last_result_summary",
    "last_checkpoint_id",
    "metadata_json",
    "created_at",
    "updated_at",
)
_AGENT_MAILBOX_COLUMNS = (
    "id",
    "agent_id",
    "task_id",
    "parent_mailbox_id",
    "source_agent_id",
    "envelope_type",
    "title",
    "summary",
    "status",
    "priority",
    "capability_ref",
    "conversation_thread_id",
    "payload_json",
    "result_summary",
    "error_summary",
    "lease_owner",
    "lease_token",
    "claimed_at",
    "started_at",
    "completed_at",
    "retry_after_at",
    "attempt_count",
    "max_attempts",
    "metadata_json",
    "created_at",
    "updated_at",
)
_AGENT_CHECKPOINT_COLUMNS = (
    "id",
    "agent_id",
    "mailbox_id",
    "task_id",
    "checkpoint_kind",
    "status",
    "phase",
    "cursor",
    "conversation_thread_id",
    "environment_ref",
    "snapshot_payload_json",
    "resume_payload_json",
    "summary",
    "created_at",
    "updated_at",
)
_AGENT_LEASE_COLUMNS = (
    "id",
    "agent_id",
    "lease_kind",
    "resource_ref",
    "lease_status",
    "lease_token",
    "owner",
    "acquired_at",
    "expires_at",
    "heartbeat_at",
    "released_at",
    "metadata_json",
    "created_at",
    "updated_at",
)
_AGENT_THREAD_BINDING_COLUMNS = (
    "thread_id",
    "agent_id",
    "session_id",
    "channel",
    "binding_kind",
    "industry_instance_id",
    "industry_role_id",
    "owner_scope",
    "active",
    "alias_of_thread_id",
    "metadata_json",
    "created_at",
    "updated_at",
)
_INDUSTRY_INSTANCE_COLUMNS = (
    "instance_id",
    "bootstrap_kind",
    "label",
    "summary",
    "owner_scope",
    "status",
    "profile_payload_json",
    "team_payload_json",
    "execution_core_identity_payload_json",
    "goal_ids_json",
    "agent_ids_json",
    "schedule_ids_json",
    "lifecycle_status",
    "autonomy_status",
    "current_cycle_id",
    "next_cycle_due_at",
    "last_cycle_started_at",
    "created_at",
    "updated_at",
)
_OPERATING_LANE_COLUMNS = (
    "id",
    "industry_instance_id",
    "lane_key",
    "title",
    "summary",
    "status",
    "owner_agent_id",
    "owner_role_id",
    "priority",
    "health_status",
    "source_ref",
    "metadata_json",
    "created_at",
    "updated_at",
)
_BACKLOG_ITEM_COLUMNS = (
    "id",
    "industry_instance_id",
    "lane_id",
    "cycle_id",
    "assignment_id",
    "goal_id",
    "title",
    "summary",
    "status",
    "priority",
    "source_kind",
    "source_ref",
    "evidence_ids_json",
    "metadata_json",
    "created_at",
    "updated_at",
)
_OPERATING_CYCLE_COLUMNS = (
    "id",
    "industry_instance_id",
    "cycle_kind",
    "title",
    "summary",
    "status",
    "source_ref",
    "started_at",
    "due_at",
    "completed_at",
    "focus_lane_ids_json",
    "backlog_item_ids_json",
    "goal_ids_json",
    "assignment_ids_json",
    "report_ids_json",
    "metadata_json",
    "created_at",
    "updated_at",
)
_ASSIGNMENT_COLUMNS = (
    "id",
    "industry_instance_id",
    "cycle_id",
    "lane_id",
    "backlog_item_id",
    "goal_id",
    "task_id",
    "owner_agent_id",
    "owner_role_id",
    "title",
    "summary",
    "status",
    "report_back_mode",
    "evidence_ids_json",
    "last_report_id",
    "metadata_json",
    "created_at",
    "updated_at",
)
_AGENT_REPORT_COLUMNS = (
    "id",
    "industry_instance_id",
    "cycle_id",
    "assignment_id",
    "goal_id",
    "task_id",
    "lane_id",
    "owner_agent_id",
    "owner_role_id",
    "report_kind",
    "headline",
    "summary",
    "status",
    "result",
    "risk_level",
    "evidence_ids_json",
    "decision_ids_json",
    "processed",
    "processed_at",
    "metadata_json",
    "created_at",
    "updated_at",
)
_STRATEGY_MEMORY_COLUMNS = (
    "strategy_id",
    "scope_type",
    "scope_id",
    "owner_agent_id",
    "owner_scope",
    "industry_instance_id",
    "title",
    "summary",
    "mission",
    "north_star",
    "priority_order_json",
    "thinking_axes_json",
    "delegation_policy_json",
    "direct_execution_policy_json",
    "execution_constraints_json",
    "evidence_requirements_json",
    "active_goal_ids_json",
    "active_goal_titles_json",
    "teammate_contracts_json",
    "lane_weights_json",
    "planning_policy_json",
    "current_focuses_json",
    "paused_lane_ids_json",
    "review_rules_json",
    "source_ref",
    "status",
    "metadata_json",
    "created_at",
    "updated_at",
)
_KNOWLEDGE_CHUNK_COLUMNS = (
    "id",
    "document_id",
    "title",
    "content",
    "summary",
    "source_ref",
    "chunk_index",
    "role_bindings_json",
    "tags_json",
    "created_at",
    "updated_at",
)


def _model_from_row(model_type: type[_ModelT], row: sqlite3.Row | None) -> _ModelT | None:
    if row is None:
        return None
    return model_type.model_validate(dict(row))


def _payload(record: BaseModel) -> dict[str, Any]:
    return record.model_dump(mode="json")


def _encode_datetime_value(value: datetime) -> str:
    normalized = (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None or value.utcoffset() is None
        else value.astimezone(timezone.utc)
    )
    return normalized.isoformat().replace("+00:00", "Z")


def _encode_json(value: Any) -> str:
    from .sqlite_predictions import _encode_json as impl

    return impl(value)


def _decode_json(value: str) -> dict[str, Any]:
    from .sqlite_predictions import _decode_json as impl

    return impl(value)


def _decode_any_json(value: str | None) -> Any:
    from .sqlite_predictions import _decode_any_json as impl

    return impl(value)


def _governance_control_from_row(row: Any) -> GovernanceControlRecord | None:
    from .sqlite_industry import _governance_control_from_row as impl

    return impl(row)


def _industry_instance_from_row(row: Any) -> IndustryInstanceRecord | None:
    from .sqlite_industry import _industry_instance_from_row as impl

    return impl(row)


def _decode_json_mapping(value: str | None) -> dict[str, Any]:
    from .sqlite_predictions import _decode_json_mapping as impl

    return impl(value)


def _decode_json_list(value: str | None) -> list[str] | None:
    from .sqlite_predictions import _decode_json_list as impl

    return impl(value)


def _operating_lane_from_row(row: Any) -> OperatingLaneRecord | None:
    from .sqlite_industry import _operating_lane_from_row as impl

    return impl(row)


def _agent_runtime_from_row(row: Any) -> AgentRuntimeRecord | None:
    from .sqlite_governance_agents import _agent_runtime_from_row as impl

    return impl(row)


def _workflow_template_from_row(row: Any) -> WorkflowTemplateRecord | None:
    from .sqlite_predictions import _workflow_template_from_row as impl

    return impl(row)


def _workflow_run_from_row(row: Any) -> WorkflowRunRecord | None:
    from .sqlite_predictions import _workflow_run_from_row as impl

    return impl(row)


def _execution_routine_from_row(row: Any) -> ExecutionRoutineRecord | None:
    from .sqlite_predictions import _execution_routine_from_row as impl

    return impl(row)


def _routine_run_from_row(row: Any) -> RoutineRunRecord | None:
    from .sqlite_predictions import _routine_run_from_row as impl

    return impl(row)


def _workflow_preset_from_row(row: Any) -> WorkflowPresetRecord | None:
    from .sqlite_predictions import _workflow_preset_from_row as impl

    return impl(row)


def _fixed_sop_template_from_row(row: Any) -> FixedSopTemplateRecord | None:
    from .sqlite_predictions import _fixed_sop_template_from_row as impl

    return impl(row)


def _fixed_sop_binding_from_row(row: Any) -> FixedSopBindingRecord | None:
    from .sqlite_predictions import _fixed_sop_binding_from_row as impl

    return impl(row)

__all__ = [name for name in globals() if not name.startswith("__")]
