# -*- coding: utf-8 -*-
"""Goal, task, backlog, cycle, and assignment records."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from .model_support import (
    CreatedRecord,
    StateRecord,
    UpdatedRecord,
    _new_record_id,
    _normalize_text_list,
    _utc_now,
)
from .models_core import (
    AgentReportStatus,
    AssignmentStatus,
    BacklogItemStatus,
    GoalStatus,
    HumanAssistTaskAcceptanceMode,
    HumanAssistTaskStatus,
    OperatingCycleKind,
    OperatingCycleStatus,
    OperatingLaneStatus,
    RiskLevel,
    ScheduleStatus,
    TaskRuntimeStatus,
    TaskStatus,
)


class GoalRecord(UpdatedRecord):
    """Top-level goal record."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = ""
    status: GoalStatus = "draft"
    priority: int = Field(default=0, ge=0)
    owner_scope: str | None = None
    industry_instance_id: str | None = None
    lane_id: str | None = None
    cycle_id: str | None = None
    goal_class: str = "goal"


class TaskRecord(UpdatedRecord):
    """Schedulable task record."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    goal_id: str | None = None
    title: str = Field(..., min_length=1)
    summary: str = ""
    task_type: str = Field(..., min_length=1)
    status: TaskStatus = "created"
    priority: int = Field(default=0, ge=0)
    owner_agent_id: str | None = None
    parent_task_id: str | None = None
    work_context_id: str | None = None
    seed_source: str | None = None
    constraints_summary: str | None = None
    acceptance_criteria: str | None = None
    current_risk_level: RiskLevel = "auto"
    industry_instance_id: str | None = None
    assignment_id: str | None = None
    lane_id: str | None = None
    cycle_id: str | None = None
    report_back_mode: str = "summary"


def _normalize_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    return {}


class HumanAssistTaskRecord(UpdatedRecord):
    """Formal host-side task for blocked-by-proof or human-owned checkpoints."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    industry_instance_id: str | None = None
    assignment_id: str | None = None
    task_id: str | None = None
    chat_thread_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = ""
    task_type: str = Field(..., min_length=1)
    reason_code: str | None = None
    reason_summary: str = ""
    required_action: str = ""
    submission_mode: str = "chat-message"
    acceptance_mode: HumanAssistTaskAcceptanceMode = "anchor_verified"
    acceptance_spec: dict[str, Any] = Field(default_factory=dict)
    resume_checkpoint_ref: str | None = None
    status: HumanAssistTaskStatus = "created"
    reward_preview: dict[str, Any] = Field(default_factory=dict)
    reward_result: dict[str, Any] = Field(default_factory=dict)
    block_evidence_refs: list[str] = Field(default_factory=list)
    submission_evidence_refs: list[str] = Field(default_factory=list)
    verification_evidence_refs: list[str] = Field(default_factory=list)
    submission_text: str | None = None
    submission_payload: dict[str, Any] = Field(default_factory=dict)
    verification_payload: dict[str, Any] = Field(default_factory=dict)
    issued_at: datetime | None = None
    submitted_at: datetime | None = None
    verified_at: datetime | None = None
    closed_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator(
        "block_evidence_refs",
        "submission_evidence_refs",
        "verification_evidence_refs",
        mode="before",
    )
    @classmethod
    def _normalize_evidence_refs(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    @field_validator(
        "acceptance_spec",
        "reward_preview",
        "reward_result",
        "submission_payload",
        "verification_payload",
        mode="before",
    )
    @classmethod
    def _normalize_mapping_fields(cls, value: object) -> dict[str, Any]:
        return _normalize_mapping(value)


class TaskRuntimeRecord(StateRecord):
    """Runtime container for a task."""

    task_id: str = Field(..., min_length=1)
    runtime_status: TaskRuntimeStatus = "cold"
    current_phase: str = Field(default="created", min_length=1)
    risk_level: RiskLevel = "auto"
    active_environment_id: str | None = None
    last_result_summary: str | None = None
    last_error_summary: str | None = None
    last_owner_agent_id: str | None = None
    last_evidence_id: str | None = None
    updated_at: datetime = Field(default_factory=_utc_now)


class RuntimeFrameRecord(CreatedRecord):
    """Snapshot-style runtime frame."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    task_id: str = Field(..., min_length=1)
    goal_summary: str = ""
    owner_agent_id: str | None = None
    current_phase: str = Field(..., min_length=1)
    current_risk_level: RiskLevel = "auto"
    environment_summary: str = ""
    evidence_summary: str = ""
    constraints_summary: str | None = None
    capabilities_summary: str | None = None
    pending_decisions_summary: str | None = None
    budget_summary: str | None = None


class ScheduleRecord(UpdatedRecord):
    """Read-optimized schedule state shadow."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    title: str = Field(..., min_length=1)
    cron: str = Field(..., min_length=1)
    timezone: str = Field(default="UTC", min_length=1)
    status: ScheduleStatus = "scheduled"
    enabled: bool = True
    task_type: str = Field(default="agent", min_length=1)
    target_channel: str | None = None
    target_user_id: str | None = None
    target_session_id: str | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_error: str | None = None
    source_ref: str | None = None
    spec_payload: dict[str, Any] = Field(default_factory=dict)
    schedule_kind: str = "cadence"
    trigger_target: str | None = None
    lane_id: str | None = None


class OperatingLaneRecord(UpdatedRecord):
    """Long-lived operating lane owned by the main brain."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    industry_instance_id: str = Field(..., min_length=1)
    lane_key: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = ""
    status: OperatingLaneStatus = "active"
    owner_agent_id: str | None = None
    owner_role_id: str | None = None
    priority: int = Field(default=0, ge=0)
    health_status: str = "healthy"
    source_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BacklogItemRecord(UpdatedRecord):
    """Main-brain backlog entry waiting to be selected into a cycle."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    industry_instance_id: str = Field(..., min_length=1)
    lane_id: str | None = None
    cycle_id: str | None = None
    assignment_id: str | None = None
    goal_id: str | None = None
    title: str = Field(..., min_length=1)
    summary: str = ""
    status: BacklogItemStatus = "open"
    priority: int = Field(default=0, ge=0)
    source_kind: str = "operator"
    source_ref: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def _normalize_evidence_ids(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class OperatingCycleRecord(UpdatedRecord):
    """Formal daily/weekly/event cycle planned by the main brain."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    industry_instance_id: str = Field(..., min_length=1)
    cycle_kind: OperatingCycleKind = "daily"
    title: str = Field(..., min_length=1)
    summary: str = ""
    status: OperatingCycleStatus = "planned"
    source_ref: str | None = None
    started_at: datetime | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    focus_lane_ids: list[str] = Field(default_factory=list)
    backlog_item_ids: list[str] = Field(default_factory=list)
    goal_ids: list[str] = Field(default_factory=list)
    assignment_ids: list[str] = Field(default_factory=list)
    report_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "focus_lane_ids",
        "backlog_item_ids",
        "goal_ids",
        "assignment_ids",
        "report_ids",
        mode="before",
    )
    @classmethod
    def _normalize_cycle_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class AssignmentRecord(UpdatedRecord):
    """Formal work packet assigned to a career agent inside a cycle."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    industry_instance_id: str = Field(..., min_length=1)
    cycle_id: str | None = None
    lane_id: str | None = None
    backlog_item_id: str | None = None
    goal_id: str | None = None
    task_id: str | None = None
    owner_agent_id: str | None = None
    owner_role_id: str | None = None
    title: str = Field(..., min_length=1)
    summary: str = ""
    status: AssignmentStatus = "planned"
    report_back_mode: str = "summary"
    evidence_ids: list[str] = Field(default_factory=list)
    last_report_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def _normalize_assignment_evidence_ids(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class AgentReportRecord(UpdatedRecord):
    """Structured report flowing back from a career agent to the main brain."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    industry_instance_id: str = Field(..., min_length=1)
    cycle_id: str | None = None
    assignment_id: str | None = None
    goal_id: str | None = None
    task_id: str | None = None
    work_context_id: str | None = None
    lane_id: str | None = None
    owner_agent_id: str | None = None
    owner_role_id: str | None = None
    report_kind: str = "task-terminal"
    headline: str = Field(..., min_length=1)
    summary: str = ""
    findings: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    needs_followup: bool = False
    followup_reason: str | None = None
    status: AgentReportStatus = "recorded"
    result: str | None = None
    risk_level: RiskLevel = "auto"
    evidence_ids: list[str] = Field(default_factory=list)
    decision_ids: list[str] = Field(default_factory=list)
    processed: bool = False
    processed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "findings",
        "uncertainties",
        "evidence_ids",
        "decision_ids",
        mode="before",
    )
    @classmethod
    def _normalize_report_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


__all__ = [
    "AgentReportRecord",
    "AssignmentRecord",
    "BacklogItemRecord",
    "GoalRecord",
    "HumanAssistTaskRecord",
    "OperatingCycleRecord",
    "OperatingLaneRecord",
    "RuntimeFrameRecord",
    "ScheduleRecord",
    "TaskRecord",
    "TaskRuntimeRecord",
]
