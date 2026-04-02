# -*- coding: utf-8 -*-
"""Formal planning compiler contracts for CoPaw's truth-first planning shell."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PlanningStrategyConstraints(BaseModel):
    """Strategy-derived constraints that shape cycle and assignment planning."""

    mission: str = ""
    north_star: str = ""
    priority_order: list[str] = Field(default_factory=list)
    lane_weights: dict[str, float] = Field(default_factory=dict)
    planning_policy: list[str] = Field(default_factory=list)
    review_rules: list[str] = Field(default_factory=list)
    paused_lane_ids: list[str] = Field(default_factory=list)
    current_focuses: list[str] = Field(default_factory=list)


class CyclePlanningDecision(BaseModel):
    """Planner output for whether and how to materialize the next operating cycle."""

    should_start: bool = False
    reason: str = "planner-no-open-backlog"
    cycle_kind: str = "daily"
    selected_backlog_item_ids: list[str] = Field(default_factory=list)
    selected_lane_ids: list[str] = Field(default_factory=list)
    max_assignment_count: int = 0
    summary: str = ""
    planning_policy: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssignmentPlanEnvelope(BaseModel):
    """Assignment-local planning shell that stays sidecar to formal truth ids."""

    assignment_id: str
    backlog_item_id: str | None = None
    lane_id: str | None = None
    cycle_id: str | None = None
    owner_agent_id: str | None = None
    owner_role_id: str | None = None
    report_back_mode: str = "summary"
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    sidecar_plan: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReportReplanDecision(BaseModel):
    """Structured replan output compiled from report synthesis pressure."""

    decision_id: str = "report-synthesis:clear"
    status: Literal["clear", "needs-replan"] = "clear"
    summary: str = "No unresolved report synthesis pressure."
    reason_ids: list[str] = Field(default_factory=list)
    source_report_ids: list[str] = Field(default_factory=list)
    topic_keys: list[str] = Field(default_factory=list)
    directives: list[dict[str, Any]] = Field(default_factory=list)
    recommended_actions: list[dict[str, Any]] = Field(default_factory=list)
    activation: dict[str, Any] = Field(default_factory=dict)
