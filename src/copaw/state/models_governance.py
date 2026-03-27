# -*- coding: utf-8 -*-
"""Governance and override records."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from .model_support import CreatedRecord, UpdatedRecord, _new_record_id
from .models_core import (
    DecisionRequestStatus,
    GoalStatus,
    RiskLevel,
    _TERMINAL_DECISION_STATUSES,
)


class DecisionRequestRecord(CreatedRecord):
    """Governance confirmation request."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    task_id: str = Field(..., min_length=1)
    decision_type: str = Field(..., min_length=1)
    risk_level: RiskLevel = "confirm"
    summary: str = Field(..., min_length=1)
    status: DecisionRequestStatus = "open"
    source_evidence_id: str | None = None
    source_patch_id: str | None = None
    requested_by: str | None = None
    resolution: str | None = None
    resolved_at: datetime | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _sync_resolution_state(self) -> "DecisionRequestRecord":
        if self.status in _TERMINAL_DECISION_STATUSES and self.resolved_at is None:
            self.resolved_at = self.created_at
        return self


class GovernanceControlRecord(UpdatedRecord):
    """Persisted runtime governance controls."""

    id: str = Field(default="runtime", min_length=1)
    emergency_stop_active: bool = False
    emergency_reason: str | None = None
    emergency_actor: str | None = None
    paused_schedule_ids: list[str] = Field(default_factory=list)
    channel_shutdown_applied: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityOverrideRecord(UpdatedRecord):
    """Persistent overrides applied to capability mounts."""

    capability_id: str = Field(..., min_length=1)
    enabled: bool | None = None
    forced_risk_level: RiskLevel | None = None
    reason: str | None = None
    source_patch_id: str | None = None


class AgentProfileOverrideRecord(UpdatedRecord):
    """Persistent overrides applied to visible agent profiles."""

    agent_id: str = Field(..., min_length=1)
    name: str | None = None
    role_name: str | None = None
    role_summary: str | None = None
    agent_class: Literal["system", "business"] | None = None
    employment_mode: Literal["career", "temporary"] | None = None
    activation_mode: Literal["persistent", "on-demand"] | None = None
    suspendable: bool | None = None
    reports_to: str | None = None
    mission: str | None = None
    status: str | None = None
    risk_level: RiskLevel | None = None
    current_goal_id: str | None = None
    current_goal: str | None = None
    current_task_id: str | None = None
    industry_instance_id: str | None = None
    industry_role_id: str | None = None
    environment_summary: str | None = None
    today_output_summary: str | None = None
    latest_evidence_summary: str | None = None
    environment_constraints: list[str] | None = None
    evidence_expectations: list[str] | None = None
    capabilities: list[str] | None = None
    reason: str | None = None
    source_patch_id: str | None = None


class GoalOverrideRecord(UpdatedRecord):
    """Persistent overrides applied to goal projections and plan views."""

    goal_id: str = Field(..., min_length=1)
    title: str | None = None
    summary: str | None = None
    status: GoalStatus | None = None
    priority: int | None = Field(default=None, ge=0)
    owner_scope: str | None = None
    plan_steps: list[str] | None = None
    compiler_context: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    source_patch_id: str | None = None


__all__ = [
    "AgentProfileOverrideRecord",
    "CapabilityOverrideRecord",
    "DecisionRequestRecord",
    "GoalOverrideRecord",
    "GovernanceControlRecord",
]
