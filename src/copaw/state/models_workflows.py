# -*- coding: utf-8 -*-
"""Workflow, routine, and fixed SOP records."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from .model_support import UpdatedRecord, _new_record_id, _normalize_text_list, _utc_now


class WorkflowTemplateRecord(UpdatedRecord):
    """Formal persisted workflow template catalog object."""

    template_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = ""
    category: str = Field(default="operations", min_length=1)
    status: str = "active"
    version: str = Field(default="v1", min_length=1)
    industry_tags: list[str] = Field(default_factory=list)
    team_modes: list[str] = Field(default_factory=list)
    dependency_capability_ids: list[str] = Field(default_factory=list)
    suggested_role_ids: list[str] = Field(default_factory=list)
    owner_role_id: str | None = None
    parameter_schema: dict[str, Any] = Field(default_factory=dict)
    step_specs: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowPresetRecord(UpdatedRecord):
    """Formal persisted workflow template preset object."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    template_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    summary: str = ""
    owner_scope: str | None = None
    industry_scope: str | None = None
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunRecord(UpdatedRecord):
    """Formal persisted workflow run object materialized from a template."""

    run_id: str = Field(default_factory=_new_record_id, min_length=1)
    template_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = ""
    status: str = "draft"
    owner_scope: str | None = None
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    parameter_payload: dict[str, Any] = Field(default_factory=dict)
    preview_payload: dict[str, Any] = Field(default_factory=dict)
    task_ids: list[str] = Field(default_factory=list)
    decision_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionRoutineRecord(UpdatedRecord):
    """Formal persisted routine definition anchored in unified state."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    routine_key: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    summary: str = ""
    status: str = "active"
    owner_scope: str | None = None
    owner_agent_id: str | None = None
    source_capability_id: str | None = None
    trigger_kind: str = "manual"
    engine_kind: str = "browser"
    environment_kind: str = "browser"
    session_requirements: dict[str, Any] = Field(default_factory=dict)
    isolation_policy: dict[str, Any] = Field(default_factory=dict)
    lock_scope: list[dict[str, Any]] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[dict[str, Any]] = Field(default_factory=list)
    expected_observations: list[dict[str, Any]] = Field(default_factory=list)
    action_contract: list[dict[str, Any]] = Field(default_factory=list)
    success_signature: dict[str, Any] = Field(default_factory=dict)
    drift_signals: list[dict[str, Any]] = Field(default_factory=list)
    replay_policy: dict[str, Any] = Field(default_factory=dict)
    fallback_policy: dict[str, Any] = Field(default_factory=dict)
    risk_baseline: str = "guarded"
    evidence_expectations: list[str] = Field(default_factory=list)
    source_evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    last_verified_at: datetime | None = None
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class RoutineRunRecord(UpdatedRecord):
    """Formal persisted routine replay run."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    routine_id: str = Field(..., min_length=1)
    source_type: str = "manual"
    source_ref: str | None = None
    status: str = "running"
    input_payload: dict[str, Any] = Field(default_factory=dict)
    owner_agent_id: str | None = None
    owner_scope: str | None = None
    environment_id: str | None = None
    session_id: str | None = None
    lease_ref: str | None = None
    checkpoint_ref: str | None = None
    deterministic_result: str | None = None
    failure_class: str | None = None
    fallback_mode: str | None = None
    fallback_task_id: str | None = None
    decision_request_id: str | None = None
    output_summary: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=_utc_now)
    completed_at: datetime | None = None


class FixedSopTemplateRecord(UpdatedRecord):
    """Native fixed SOP template persisted inside unified state."""

    template_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    summary: str = ""
    description: str = ""
    status: str = "active"
    version: str = Field(default="v1", min_length=1)
    source_kind: str = "builtin"
    source_ref: str | None = None
    owner_role_id: str | None = None
    suggested_role_ids: list[str] = Field(default_factory=list)
    industry_tags: list[str] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    risk_baseline: str = "guarded"
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    writeback_contract: dict[str, Any] = Field(default_factory=dict)
    node_graph: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "suggested_role_ids",
        "industry_tags",
        "capability_tags",
        mode="before",
    )
    @classmethod
    def _normalize_fixed_sop_template_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class FixedSopBindingRecord(UpdatedRecord):
    """Installed native fixed SOP binding anchored to a runtime context."""

    binding_id: str = Field(default_factory=_new_record_id, min_length=1)
    template_id: str = Field(..., min_length=1)
    binding_name: str = Field(..., min_length=1)
    status: str = "draft"
    owner_scope: str | None = None
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    workflow_template_id: str | None = None
    trigger_mode: str = "manual"
    trigger_ref: str | None = None
    input_mapping: dict[str, Any] = Field(default_factory=dict)
    output_mapping: dict[str, Any] = Field(default_factory=dict)
    timeout_policy: dict[str, Any] = Field(default_factory=dict)
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    risk_baseline: str = "guarded"
    last_run_id: str | None = None
    last_verified_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "ExecutionRoutineRecord",
    "FixedSopBindingRecord",
    "FixedSopTemplateRecord",
    "RoutineRunRecord",
    "WorkflowPresetRecord",
    "WorkflowRunRecord",
    "WorkflowTemplateRecord",
]
