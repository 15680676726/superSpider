# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PredictionCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = None
    question: str | None = None
    summary: str = ""
    topic_type: str = "operations"
    owner_scope: str | None = None
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    workflow_run_id: str | None = None
    time_window_days: int = Field(default=7, ge=1, le=90)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_prompt(self) -> "PredictionCreateRequest":
        if not (self.title or self.question):
            raise ValueError("title or question is required")
        return self


class PredictionRecommendationExecuteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    actor: str = "copaw-operator"


class PredictionReviewCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    recommendation_id: str | None = None
    reviewer: str | None = None
    summary: str = ""
    outcome: Literal["hit", "partial", "miss", "unknown"] = "unknown"
    adopted: bool | None = None
    benefit_score: float | None = None
    actual_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PredictionCaseSummary(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    case: dict[str, Any]
    scenario_count: int = 0
    signal_count: int = 0
    recommendation_count: int = 0
    review_count: int = 0
    latest_review_outcome: str | None = None
    pending_decision_count: int = 0
    routes: dict[str, str] = Field(default_factory=dict)


class PredictionRecommendationView(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    recommendation: dict[str, Any]
    decision: dict[str, Any] | None = None
    routes: dict[str, str] = Field(default_factory=dict)


class PredictionCaseDetail(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    case: dict[str, Any]
    scenarios: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[PredictionRecommendationView] = Field(default_factory=list)
    reviews: list[dict[str, Any]] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    routes: dict[str, Any] = Field(default_factory=dict)


class PredictionRecommendationExecutionResponse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    execution: dict[str, Any]
    decision: dict[str, Any] | None = None
    detail: PredictionCaseDetail


class PredictionRecommendationCoordinationResponse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    detail: PredictionCaseDetail
    summary: str = ""
    industry_instance_id: str | None = None
    backlog_item_id: str | None = None
    backlog_status: str | None = None
    reused_backlog: bool = False
    started_cycle_id: str | None = None
    coordination_reason: str | None = None
    chat_thread_id: str | None = None
    chat_route: str | None = None


class PredictionCapabilityOptimizationSummary(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    total_items: int = 0
    actionable_count: int = 0
    history_count: int = 0
    case_count: int = 0
    missing_capability_count: int = 0
    underperforming_capability_count: int = 0
    trial_count: int = 0
    rollout_count: int = 0
    retire_count: int = 0
    waiting_confirm_count: int = 0
    manual_only_count: int = 0
    executed_count: int = 0


class PredictionCapabilityOptimizationItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    case: dict[str, Any]
    recommendation: PredictionRecommendationView
    status_bucket: Literal["actionable", "history"] = "actionable"
    routes: dict[str, str] = Field(default_factory=dict)


class PredictionCapabilityPortfolioScopeSummary(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    scope_key: str = ""
    target_scope: str | None = None
    target_role_id: str | None = None
    target_seat_ref: str | None = None
    donor_count: int = 0
    candidate_count: int = 0
    active_candidate_count: int = 0
    trial_candidate_count: int = 0
    source_kind_count: dict[str, int] = Field(default_factory=dict)


class PredictionCapabilityPortfolioSummary(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    donor_count: int = 0
    active_donor_count: int = 0
    candidate_donor_count: int = 0
    trial_donor_count: int = 0
    trusted_source_count: int = 0
    watchlist_source_count: int = 0
    degraded_donor_count: int = 0
    replace_pressure_count: int = 0
    retire_pressure_count: int = 0
    over_budget_scope_count: int = 0
    fallback_only_candidate_count: int = 0
    over_budget_scopes: list[dict[str, Any]] = Field(default_factory=list)
    scope_breakdown: list[PredictionCapabilityPortfolioScopeSummary] = Field(
        default_factory=list,
    )
    planning_actions: list[dict[str, Any]] = Field(default_factory=list)
    routes: dict[str, str] = Field(default_factory=dict)


class PredictionCapabilityDiscoverySummary(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: str = "unavailable"
    summary: str = ""
    source_profile_count: int = 0
    active_source_count: int = 0
    trusted_source_count: int = 0
    watchlist_source_count: int = 0
    fallback_only_source_count: int = 0
    by_source_kind: dict[str, int] = Field(default_factory=dict)
    trust_posture_count: dict[str, int] = Field(default_factory=dict)
    degraded_components: list[dict[str, Any]] = Field(default_factory=list)
    routes: dict[str, str] = Field(default_factory=dict)


class PredictionCapabilityOptimizationOverview(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    summary: PredictionCapabilityOptimizationSummary = Field(
        default_factory=PredictionCapabilityOptimizationSummary,
    )
    actionable: list[PredictionCapabilityOptimizationItem] = Field(
        default_factory=list,
    )
    history: list[PredictionCapabilityOptimizationItem] = Field(
        default_factory=list,
    )
    portfolio: PredictionCapabilityPortfolioSummary = Field(
        default_factory=PredictionCapabilityPortfolioSummary,
    )
    discovery: PredictionCapabilityDiscoverySummary = Field(
        default_factory=PredictionCapabilityDiscoverySummary,
    )
    routes: dict[str, str] = Field(default_factory=dict)
