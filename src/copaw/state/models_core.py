# -*- coding: utf-8 -*-
"""Shared state model aliases and status literals."""
from __future__ import annotations

from typing import Literal

RiskLevel = Literal["auto", "guarded", "confirm"]
GoalStatus = Literal["draft", "active", "paused", "blocked", "completed", "archived"]
TaskStatus = Literal[
    "created",
    "queued",
    "running",
    "waiting",
    "blocked",
    "needs-confirm",
    "completed",
    "failed",
    "cancelled",
]
TaskRuntimeStatus = Literal[
    "cold",
    "hydrating",
    "active",
    "waiting-input",
    "waiting-env",
    "waiting-confirm",
    "blocked",
    "terminated",
]
ScheduleStatus = Literal[
    "scheduled",
    "paused",
    "running",
    "success",
    "error",
    "deleted",
]
OperatingLaneStatus = Literal["active", "paused", "archived"]
BacklogItemStatus = Literal[
    "open",
    "selected",
    "materialized",
    "completed",
    "deferred",
    "cancelled",
]
OperatingCycleKind = Literal["daily", "weekly", "event"]
OperatingCycleStatus = Literal[
    "planned",
    "waiting-confirm",
    "active",
    "review",
    "completed",
    "cancelled",
]
AssignmentStatus = Literal[
    "planned",
    "queued",
    "running",
    "waiting-report",
    "completed",
    "failed",
    "cancelled",
]
AgentReportStatus = Literal["recorded", "processed", "cancelled"]
DecisionRequestStatus = Literal[
    "open",
    "reviewing",
    "approved",
    "rejected",
    "expired",
]
PredictionCaseStatus = Literal["open", "reviewing", "closed", "failed"]
PredictionCaseKind = Literal["manual", "cycle"]
PredictionScenarioKind = Literal["best", "base", "worst"]
PredictionSignalDirection = Literal["positive", "negative", "neutral"]
PredictionSignalSourceKind = Literal[
    "metric",
    "report",
    "evidence",
    "workflow-run",
    "industry",
    "agent",
    "manual",
]
PredictionRecommendationType = Literal[
    "plan_recommendation",
    "role_recommendation",
    "capability_recommendation",
    "schedule_recommendation",
    "risk_recommendation",
]
PredictionRecommendationStatus = Literal[
    "proposed",
    "queued",
    "throttled",
    "waiting-confirm",
    "approved",
    "rejected",
    "executed",
    "manual-only",
    "failed",
]
PredictionReviewOutcome = Literal["hit", "partial", "miss", "unknown"]
AgentRuntimeStatus = Literal[
    "idle",
    "assigned",
    "queued",
    "claimed",
    "executing",
    "running",
    "waiting",
    "blocked",
    "paused",
    "retired",
    "degraded",
]
ActorDesiredState = Literal["active", "paused", "retired"]
AgentMailboxStatus = Literal[
    "queued",
    "leased",
    "running",
    "completed",
    "failed",
    "cancelled",
    "blocked",
    "retry-wait",
]
AgentCheckpointStatus = Literal["ready", "applied", "abandoned", "failed"]
AgentLeaseStatus = Literal["leased", "released", "expired"]
AgentThreadBindingKind = Literal[
    "agent-primary",
    "industry-role-alias",
    "agent-alias",
]
StrategyScopeType = Literal["global", "industry"]
StrategyMemoryStatus = Literal["active", "archived", "retired"]
ReportWindow = Literal["daily", "weekly", "monthly"]
ReportScopeType = Literal["global", "industry", "agent"]

_TERMINAL_DECISION_STATUSES = frozenset({"approved", "rejected", "expired"})


__all__ = [
    "ActorDesiredState",
    "AgentCheckpointStatus",
    "AgentLeaseStatus",
    "AgentMailboxStatus",
    "AgentReportStatus",
    "AgentRuntimeStatus",
    "AgentThreadBindingKind",
    "AssignmentStatus",
    "BacklogItemStatus",
    "DecisionRequestStatus",
    "GoalStatus",
    "OperatingCycleKind",
    "OperatingCycleStatus",
    "OperatingLaneStatus",
    "PredictionCaseKind",
    "PredictionCaseStatus",
    "PredictionRecommendationStatus",
    "PredictionRecommendationType",
    "PredictionReviewOutcome",
    "PredictionScenarioKind",
    "PredictionSignalDirection",
    "PredictionSignalSourceKind",
    "ReportScopeType",
    "ReportWindow",
    "RiskLevel",
    "ScheduleStatus",
    "StrategyMemoryStatus",
    "StrategyScopeType",
    "TaskRuntimeStatus",
    "TaskStatus",
    "_TERMINAL_DECISION_STATUSES",
]
