# -*- coding: utf-8 -*-
"""Strategy, metric, and reporting records."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_serializer, field_validator

from .model_support import CreatedRecord, UpdatedRecord, _new_record_id, _normalize_text_list, _utc_now
from .models_core import ReportScopeType, ReportWindow, StrategyMemoryStatus, StrategyScopeType


class StrategicUncertaintyRecord(BaseModel):
    """Typed strategic uncertainty that stays attached to strategy truth."""

    uncertainty_id: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1)
    scope: Literal["strategy", "lane", "cycle"] = "strategy"
    impact_level: Literal["low", "medium", "high"] = "medium"
    current_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_for_refs: list[str] = Field(default_factory=list)
    evidence_against_refs: list[str] = Field(default_factory=list)
    review_by_cycle: str | None = None
    escalate_when: list[Literal["repeated blocker", "confidence drop", "target miss"]] = Field(
        default_factory=list,
    )

    @field_validator(
        "evidence_for_refs",
        "evidence_against_refs",
        "escalate_when",
        mode="before",
    )
    @classmethod
    def _normalize_reference_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class LaneBudgetRecord(BaseModel):
    """Typed multi-cycle lane budget persisted on strategy truth."""

    lane_id: str = Field(..., min_length=1)
    budget_window: str = Field(..., min_length=1)
    target_share: float = Field(default=0.0, ge=0.0, le=1.0)
    min_share: float = Field(default=0.0, ge=0.0, le=1.0)
    max_share: float = Field(default=1.0, ge=0.0, le=1.0)
    review_pressure: str = ""
    defer_reason: str | None = None
    force_include_reason: str | None = None


class StrategyMemoryRecord(UpdatedRecord):
    """Formal persisted strategic memory for the execution core."""

    strategy_id: str = Field(default_factory=_new_record_id, min_length=1)
    scope_type: StrategyScopeType = "industry"
    scope_id: str = Field(..., min_length=1)
    owner_agent_id: str | None = None
    owner_scope: str | None = None
    industry_instance_id: str | None = None
    title: str = Field(..., min_length=1)
    summary: str = ""
    mission: str = ""
    north_star: str = ""
    priority_order: list[str] = Field(default_factory=list)
    thinking_axes: list[str] = Field(default_factory=list)
    delegation_policy: list[str] = Field(default_factory=list)
    direct_execution_policy: list[str] = Field(default_factory=list)
    execution_constraints: list[str] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    active_goal_ids: list[str] = Field(default_factory=list)
    active_goal_titles: list[str] = Field(default_factory=list)
    teammate_contracts: list[dict[str, Any]] = Field(default_factory=list)
    lane_weights: dict[str, float] = Field(default_factory=dict)
    planning_policy: list[str] = Field(default_factory=list)
    current_focuses: list[str] = Field(default_factory=list)
    paused_lane_ids: list[str] = Field(default_factory=list)
    strategic_uncertainties: list[StrategicUncertaintyRecord] = Field(default_factory=list)
    lane_budgets: list[LaneBudgetRecord] = Field(default_factory=list)
    review_rules: list[str] = Field(default_factory=list)
    source_ref: str | None = None
    status: StrategyMemoryStatus = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "priority_order",
        "thinking_axes",
        "delegation_policy",
        "direct_execution_policy",
        "execution_constraints",
        "evidence_requirements",
        "active_goal_ids",
        "active_goal_titles",
        "planning_policy",
        "current_focuses",
        "paused_lane_ids",
        "review_rules",
        mode="before",
    )
    @classmethod
    def _normalize_strategy_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    @field_validator("lane_weights", mode="before")
    @classmethod
    def _normalize_lane_weights(cls, value: object) -> dict[str, float]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, float] = {}
        for key, raw in value.items():
            lane_id = str(key or "").strip()
            if not lane_id:
                continue
            try:
                normalized[lane_id] = float(raw)
            except (TypeError, ValueError):
                continue
        return normalized

    @field_serializer("strategic_uncertainties", when_used="always")
    def _serialize_strategic_uncertainties(
        self,
        value: list[StrategicUncertaintyRecord] | list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            (
                item.model_dump(mode="python")
                if isinstance(item, StrategicUncertaintyRecord)
                else StrategicUncertaintyRecord.model_validate(item).model_dump(mode="python")
            )
            for item in list(value or [])
        ]

    @field_serializer("lane_budgets", when_used="always")
    def _serialize_lane_budgets(
        self,
        value: list[LaneBudgetRecord] | list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            (
                item.model_dump(mode="python")
                if isinstance(item, LaneBudgetRecord)
                else LaneBudgetRecord.model_validate(item).model_dump(mode="python")
            )
            for item in list(value or [])
        ]


class MetricRecord(CreatedRecord):
    """Formal evidence-driven metric snapshot."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    key: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    window: ReportWindow = "weekly"
    scope_type: ReportScopeType = "global"
    scope_id: str | None = None
    value: float = 0
    unit: str = Field(default="count", min_length=1)
    display_value: str = ""
    numerator: float | None = None
    denominator: float | None = None
    formula: str = ""
    source_summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReportTaskDigest(BaseModel):
    """Task digest embedded in a formal report window."""

    task_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = ""
    status: str = ""
    owner_agent_id: str | None = None
    runtime_status: str | None = None
    current_phase: str | None = None
    last_result_summary: str | None = None
    last_error_summary: str | None = None
    updated_at: datetime | None = None
    route: str | None = None


class ReportEvidenceDigest(BaseModel):
    """Evidence digest embedded in a formal report window."""

    evidence_id: str = Field(..., min_length=1)
    task_id: str | None = None
    action_summary: str = ""
    result_summary: str = ""
    risk_level: str = "auto"
    capability_ref: str | None = None
    created_at: datetime | None = None


class ReportRecord(CreatedRecord):
    """Formal evidence-driven report snapshot."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = ""
    window: ReportWindow = "weekly"
    scope_type: ReportScopeType = "global"
    scope_id: str | None = None
    status: str = "ready"
    since: datetime
    until: datetime = Field(default_factory=_utc_now)
    highlights: list[str] = Field(default_factory=list)
    metrics: list[MetricRecord] = Field(default_factory=list)
    task_status_counts: dict[str, int] = Field(default_factory=dict)
    runtime_status_counts: dict[str, int] = Field(default_factory=dict)
    goal_status_counts: dict[str, int] = Field(default_factory=dict)
    evidence_count: int = 0
    proposal_count: int = 0
    patch_count: int = 0
    applied_patch_count: int = 0
    rollback_patch_count: int = 0
    growth_count: int = 0
    decision_count: int = 0
    prediction_count: int = 0
    recommendation_count: int = 0
    review_count: int = 0
    auto_execution_count: int = 0
    task_count: int = 0
    agent_count: int = 0
    focus_items: list[str] = Field(default_factory=list)
    completed_tasks: list[ReportTaskDigest] = Field(default_factory=list)
    key_results: list[str] = Field(default_factory=list)
    primary_evidence: list[ReportEvidenceDigest] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    goal_ids: list[str] = Field(default_factory=list)
    agent_ids: list[str] = Field(default_factory=list)
    routes: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "LaneBudgetRecord",
    "MetricRecord",
    "ReportEvidenceDigest",
    "ReportRecord",
    "ReportTaskDigest",
    "StrategicUncertaintyRecord",
    "StrategyMemoryRecord",
]
