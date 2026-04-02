# -*- coding: utf-8 -*-
"""Formal planning compiler contracts for CoPaw's truth-first planning shell."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PlanningStrategicUncertainty(BaseModel):
    """Planning-side view of a tracked strategic uncertainty."""

    uncertainty_id: str
    statement: str = ""
    scope: Literal["strategy", "lane", "cycle"] = "strategy"
    impact_level: Literal["low", "medium", "high"] = "medium"
    current_confidence: float = 0.5
    evidence_for_refs: list[str] = Field(default_factory=list)
    evidence_against_refs: list[str] = Field(default_factory=list)
    review_by_cycle: str = ""
    escalate_when: list[str] = Field(default_factory=list)
    lane_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanningLaneBudget(BaseModel):
    """Typed lane-budget output compiled from strategy truth."""

    lane_id: str
    budget_window: str = "next-cycle"
    target_share: float = 0.0
    min_share: float = 0.0
    max_share: float = 1.0
    current_share: float | None = None
    review_pressure: str = ""
    defer_reason: str = ""
    force_include_reason: str = ""
    completed_cycles: int = 0
    consumed_cycles: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class StrategyTriggerRule(BaseModel):
    """Typed rule hint compiled from review rules and uncertainty escalation policy."""

    rule_id: str
    source: str = "review-rule"
    decision_kind: Literal[
        "follow_up_backlog",
        "cycle_rebalance",
        "lane_reweight",
        "strategy_review_required",
    ] = "follow_up_backlog"
    summary: str = ""
    trigger_signals: list[str] = Field(default_factory=list)
    uncertainty_ids: list[str] = Field(default_factory=list)
    lane_ids: list[str] = Field(default_factory=list)


class PlanningStrategyConstraints(BaseModel):
    """Strategy-derived constraints that shape cycle and assignment planning."""

    mission: str = ""
    north_star: str = ""
    priority_order: list[str] = Field(default_factory=list)
    lane_weights: dict[str, float] = Field(default_factory=dict)
    strategic_uncertainties: list[PlanningStrategicUncertainty] = Field(default_factory=list)
    lane_budgets: list[PlanningLaneBudget] = Field(default_factory=list)
    strategy_trigger_rules: list[StrategyTriggerRule] = Field(default_factory=list)
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
    decision_kind: Literal[
        "clear",
        "follow_up_backlog",
        "cycle_rebalance",
        "lane_reweight",
        "strategy_review_required",
    ] = "clear"
    summary: str = "No unresolved report synthesis pressure."
    reason_ids: list[str] = Field(default_factory=list)
    source_report_ids: list[str] = Field(default_factory=list)
    topic_keys: list[str] = Field(default_factory=list)
    trigger_families: list[str] = Field(default_factory=list)
    trigger_rule_ids: list[str] = Field(default_factory=list)
    affected_lane_ids: list[str] = Field(default_factory=list)
    affected_uncertainty_ids: list[str] = Field(default_factory=list)
    directives: list[dict[str, Any]] = Field(default_factory=list)
    recommended_actions: list[dict[str, Any]] = Field(default_factory=list)
    activation: dict[str, Any] = Field(default_factory=dict)
    rationale: dict[str, Any] = Field(default_factory=dict)
