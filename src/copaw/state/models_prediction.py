# -*- coding: utf-8 -*-
"""Prediction case, scenario, signal, recommendation, and review records."""
from __future__ import annotations

from typing import Any

from pydantic import Field

from .model_support import UpdatedRecord, _new_record_id
from .models_core import (
    PredictionCaseKind,
    PredictionCaseStatus,
    PredictionRecommendationStatus,
    PredictionRecommendationType,
    PredictionReviewOutcome,
    PredictionScenarioKind,
    PredictionSignalDirection,
    PredictionSignalSourceKind,
    RiskLevel,
)


class PredictionCaseRecord(UpdatedRecord):
    """Formal persisted prediction case anchored in the unified state store."""

    case_id: str = Field(default_factory=_new_record_id, min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = ""
    case_kind: PredictionCaseKind = "manual"
    status: PredictionCaseStatus = "open"
    topic_type: str = Field(default="operations", min_length=1)
    owner_scope: str | None = None
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    workflow_run_id: str | None = None
    question: str = ""
    time_window_days: int = Field(default=7, ge=1, le=90)
    overall_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    primary_recommendation_id: str | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PredictionScenarioRecord(UpdatedRecord):
    """One structured scenario inside a prediction case."""

    scenario_id: str = Field(default_factory=_new_record_id, min_length=1)
    case_id: str = Field(..., min_length=1)
    scenario_kind: PredictionScenarioKind = "base"
    title: str = Field(..., min_length=1)
    summary: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    goal_delta: float = 0.0
    task_load_delta: float = 0.0
    risk_delta: float = 0.0
    resource_delta: float = 0.0
    externality_delta: float = 0.0
    assumptions: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    recommendation_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PredictionSignalRecord(UpdatedRecord):
    """Formal signal linked to a prediction case."""

    signal_id: str = Field(default_factory=_new_record_id, min_length=1)
    case_id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    summary: str = ""
    source_kind: PredictionSignalSourceKind = "metric"
    source_ref: str | None = None
    direction: PredictionSignalDirection = "neutral"
    strength: float = Field(default=0.0, ge=0.0, le=1.0)
    metric_key: str | None = None
    report_id: str | None = None
    evidence_id: str | None = None
    agent_id: str | None = None
    workflow_run_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class PredictionRecommendationRecord(UpdatedRecord):
    """Governable recommendation emitted by a prediction case."""

    recommendation_id: str = Field(default_factory=_new_record_id, min_length=1)
    case_id: str = Field(..., min_length=1)
    recommendation_type: PredictionRecommendationType = "plan_recommendation"
    title: str = Field(..., min_length=1)
    summary: str = ""
    priority: int = Field(default=0, ge=0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    risk_level: RiskLevel = "guarded"
    action_kind: str = Field(default="manual:review", min_length=1)
    executable: bool = False
    auto_eligible: bool = False
    auto_executed: bool = False
    status: PredictionRecommendationStatus = "proposed"
    target_agent_id: str | None = None
    target_goal_id: str | None = None
    target_schedule_id: str | None = None
    target_capability_ids: list[str] = Field(default_factory=list)
    decision_request_id: str | None = None
    execution_task_id: str | None = None
    execution_evidence_id: str | None = None
    outcome_summary: str | None = None
    action_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PredictionReviewRecord(UpdatedRecord):
    """Review/outcome snapshot for one prediction case or recommendation."""

    review_id: str = Field(default_factory=_new_record_id, min_length=1)
    case_id: str = Field(..., min_length=1)
    recommendation_id: str | None = None
    reviewer: str | None = None
    summary: str = ""
    outcome: PredictionReviewOutcome = "unknown"
    adopted: bool | None = None
    benefit_score: float | None = None
    actual_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "PredictionCaseRecord",
    "PredictionRecommendationRecord",
    "PredictionReviewRecord",
    "PredictionScenarioRecord",
    "PredictionSignalRecord",
]
