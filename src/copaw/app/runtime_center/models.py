# -*- coding: utf-8 -*-
"""Read models for the Runtime Center operator surface."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer


def _compact_payload(value: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, item in value.items():
        if item is None:
            continue
        if isinstance(item, str) and item == "":
            continue
        if isinstance(item, (list, dict)) and not item:
            continue
        compact[key] = item
    return compact


class RuntimeCenterSurfaceInfo(BaseModel):
    """Metadata describing the live Runtime Center operator surface."""

    version: Literal["runtime-center-v1"] = "runtime-center-v1"
    mode: Literal["operator-surface"] = "operator-surface"
    status: Literal["state-service", "degraded", "unavailable"] = "unavailable"
    read_only: bool = False
    source: str = Field(..., description="Current backing source summary")
    note: str = Field(
        default=(
            "Runtime Center is the operator surface backed by the "
            "shared state, evidence, goal, learning, and environment services."
        ),
    )
    services: list[str] = Field(
        default_factory=lambda: [
            "RuntimeCenterStateQueryService",
            "RuntimeCenterEvidenceQueryService",
            "RuntimeCenterQueryService",
        ],
    )


class RuntimeActivationSummary(BaseModel):
    """Conservative activation-layer projection for Runtime Center read payloads."""

    scope_type: str
    scope_id: str
    activated_count: int = 0
    contradiction_count: int = 0
    top_entities: list[str] = Field(default_factory=list)
    top_constraints: list[str] = Field(default_factory=list)
    top_next_actions: list[str] = Field(default_factory=list)
    support_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    strategy_refs: list[str] = Field(default_factory=list)


class RuntimeOverviewEntry(BaseModel):
    """One overview row rendered inside a runtime-center card."""

    id: str
    title: str
    kind: str
    status: str
    owner: str | None = None
    summary: str | None = None
    updated_at: datetime | None = None
    route: str | None = None
    actions: dict[str, str] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)


class RuntimeOverviewCard(BaseModel):
    """A compact frontend-friendly overview card."""

    key: str
    title: str
    source: str
    status: Literal["state-service", "degraded", "unavailable"]
    count: int = 0
    summary: str
    entries: list[RuntimeOverviewEntry] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class RuntimeOverviewResponse(BaseModel):
    """Top-level response for the runtime-center overview endpoint."""

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    surface: RuntimeCenterSurfaceInfo
    cards: list[RuntimeOverviewCard] = Field(default_factory=list)


class RuntimeCenterSurfaceResponse(BaseModel):
    """Canonical Runtime Center page payload."""

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    surface: RuntimeCenterSurfaceInfo
    cards: list[RuntimeOverviewCard] = Field(default_factory=list)
    main_brain: "RuntimeMainBrainResponse | None" = None


@dataclass(slots=True)
class RuntimeCenterAppStateView:
    """Typed facade over the app state attributes used by Runtime Center read models."""

    state_query_service: Any = None
    evidence_query_service: Any = None
    capability_service: Any = None
    learning_service: Any = None
    agent_profile_service: Any = None
    industry_service: Any = None
    prediction_service: Any = None
    governance_service: Any = None
    strategy_memory_service: Any = None
    routine_service: Any = None
    query_execution_service: Any = None
    cron_manager: Any = None
    automation_tasks: Any = None
    actor_supervisor: Any = None
    actor_worker: Any = None
    latest_recovery_report: Any = None
    startup_recovery_summary: Any = None

    @classmethod
    def from_object(cls, app_state: Any) -> "RuntimeCenterAppStateView":
        return cls(
            state_query_service=getattr(app_state, "state_query_service", None),
            evidence_query_service=getattr(app_state, "evidence_query_service", None),
            capability_service=getattr(app_state, "capability_service", None),
            learning_service=getattr(app_state, "learning_service", None),
            agent_profile_service=getattr(app_state, "agent_profile_service", None),
            industry_service=getattr(app_state, "industry_service", None),
            prediction_service=getattr(app_state, "prediction_service", None),
            governance_service=getattr(app_state, "governance_service", None),
            strategy_memory_service=getattr(app_state, "strategy_memory_service", None),
            routine_service=getattr(app_state, "routine_service", None),
            query_execution_service=getattr(app_state, "query_execution_service", None),
            cron_manager=getattr(app_state, "cron_manager", None),
            automation_tasks=getattr(app_state, "automation_tasks", None),
            actor_supervisor=getattr(app_state, "actor_supervisor", None),
            actor_worker=getattr(app_state, "actor_worker", None),
            latest_recovery_report=getattr(app_state, "latest_recovery_report", None),
            startup_recovery_summary=getattr(app_state, "startup_recovery_summary", None),
        )

    def resolve_recovery_summary(self) -> tuple[Any | None, str]:
        if self.latest_recovery_report is not None:
            return self.latest_recovery_report, "latest"
        if self.startup_recovery_summary is not None:
            return self.startup_recovery_summary, "startup"
        return None, "latest"

    def automation_overview_snapshot(self) -> list[dict[str, Any]]:
        getter = getattr(self.automation_tasks, "overview_snapshot", None)
        if callable(getter):
            payload = getter()
            if isinstance(payload, list):
                return [dict(item) for item in payload if isinstance(item, dict)]
        return []

    def actor_supervisor_snapshot(self) -> dict[str, Any] | None:
        getter = getattr(self.actor_supervisor, "snapshot", None)
        if callable(getter):
            payload = getter()
            if isinstance(payload, dict):
                return dict(payload)
        return None


class RuntimeMainBrainSection(BaseModel):
    """Compact section payload used by the dedicated main-brain cockpit."""

    count: int = 0
    summary: str | None = None
    route: str | None = None
    entries: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class RuntimePlanningShell(BaseModel):
    """Typed planning-shell sidecar payload exposed to Runtime Center readers."""

    model_config = ConfigDict(extra="allow")

    mode: str = ""
    scope: str = ""
    plan_id: str = ""
    resume_key: str = ""
    fork_key: str = ""
    verify_reminder: str = ""

    @model_serializer(mode="wrap")
    def serialize_model(self, handler) -> dict[str, Any]:
        return _compact_payload(handler(self))


class RuntimeMainBrainPlanningDecision(BaseModel):
    """Typed cycle-planning decision payload for the main-brain cockpit."""

    model_config = ConfigDict(extra="allow")

    cycle_id: str | None = None
    cycle_kind: str | None = None
    summary: str = ""
    selected_backlog_item_ids: list[str] = Field(default_factory=list)
    selected_assignment_ids: list[str] = Field(default_factory=list)
    selected_lane_ids: list[str] = Field(default_factory=list)
    planning_policy: list[str] = Field(default_factory=list)
    planning_shell: RuntimePlanningShell = Field(default_factory=RuntimePlanningShell)

    @model_serializer(mode="wrap")
    def serialize_model(self, handler) -> dict[str, Any]:
        return _compact_payload(handler(self))


class RuntimeMainBrainFocusedAssignmentPlan(BaseModel):
    """Typed focused assignment planning shell payload."""

    model_config = ConfigDict(extra="allow")

    assignment_id: str | None = None
    summary: str = ""
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    planning_shell: RuntimePlanningShell = Field(default_factory=RuntimePlanningShell)

    @model_serializer(mode="wrap")
    def serialize_model(self, handler) -> dict[str, Any]:
        return _compact_payload(handler(self))


class RuntimeMainBrainReplanPayload(BaseModel):
    """Typed report-replan shell payload."""

    model_config = ConfigDict(extra="allow")

    status: str = "clear"
    decision_kind: str | None = None
    summary: str = ""
    strategy_trigger_rules: list[dict[str, Any]] = Field(default_factory=list)
    uncertainty_register: dict[str, Any] = Field(default_factory=dict)
    directives: list[dict[str, Any]] = Field(default_factory=list)
    recommended_actions: list[dict[str, Any]] = Field(default_factory=list)
    planning_shell: RuntimePlanningShell = Field(default_factory=RuntimePlanningShell)

    @model_serializer(mode="wrap")
    def serialize_model(self, handler) -> dict[str, Any]:
        return _compact_payload(handler(self))


class RuntimeMainBrainPlanningPayload(BaseModel):
    """Typed planning surface lifted into the dedicated main-brain contract."""

    model_config = ConfigDict(extra="allow")

    is_truth_store: bool = False
    source: str = ""
    strategy_constraints: dict[str, Any] = Field(default_factory=dict)
    latest_cycle_decision: RuntimeMainBrainPlanningDecision = Field(
        default_factory=RuntimeMainBrainPlanningDecision,
    )
    focused_assignment_plan: RuntimeMainBrainFocusedAssignmentPlan = Field(
        default_factory=RuntimeMainBrainFocusedAssignmentPlan,
    )
    replan: RuntimeMainBrainReplanPayload = Field(
        default_factory=RuntimeMainBrainReplanPayload,
    )

    @model_serializer(mode="wrap")
    def serialize_model(self, handler) -> dict[str, Any]:
        return _compact_payload(handler(self))


class RuntimeQueryRuntimeEntropyPayload(BaseModel):
    """Typed query-runtime entropy contract exposed to governance/read surfaces."""

    model_config = ConfigDict(extra="allow")

    status: str = ""
    runtime_entropy: dict[str, Any] = Field(default_factory=dict)
    compaction_state: dict[str, Any] = Field(default_factory=dict)
    tool_result_budget: dict[str, Any] = Field(default_factory=dict)
    tool_use_summary: dict[str, Any] = Field(default_factory=dict)
    sidecar_memory: dict[str, Any] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def serialize_model(self, handler) -> dict[str, Any]:
        return _compact_payload(handler(self))


class RuntimeMainBrainGovernanceExplainPayload(BaseModel):
    """Typed diagnostics summary for main-brain governance."""

    model_config = ConfigDict(extra="allow")

    failure_source: str | None = None
    blocked_next_step: str | None = None
    remediation_summary: str | None = None
    decision_provenance: dict[str, Any] = Field(default_factory=dict)
    degraded_components: list[dict[str, Any]] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def serialize_model(self, handler) -> dict[str, Any]:
        return _compact_payload(handler(self))


class RuntimeMainBrainGovernancePayload(BaseModel):
    """Typed governance payload for the dedicated main-brain cockpit."""

    model_config = ConfigDict(extra="allow")

    status: str = "unavailable"
    summary: str = ""
    route: str = "/api/runtime-center/governance/status"
    pending_decisions: int = 0
    pending_patches: int = 0
    proposed_patches: int = 0
    decision_provenance: dict[str, Any] = Field(default_factory=dict)
    paused_schedule_count: int = 0
    emergency_stop_active: bool = False
    handoff_active: bool = False
    staffing_pending_count: int = 0
    human_assist_blocked_count: int = 0
    host_twin_summary: dict[str, Any] = Field(default_factory=dict)
    capability_governance: dict[str, Any] = Field(default_factory=dict)
    explain: RuntimeMainBrainGovernanceExplainPayload = Field(
        default_factory=RuntimeMainBrainGovernanceExplainPayload,
    )
    query_runtime_entropy: RuntimeQueryRuntimeEntropyPayload = Field(
        default_factory=RuntimeQueryRuntimeEntropyPayload,
    )
    sidecar_memory: dict[str, Any] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def serialize_model(self, handler) -> dict[str, Any]:
        payload = handler(self)
        compact = _compact_payload(payload)
        compact["query_runtime_entropy"] = payload.get("query_runtime_entropy", {})
        return compact


class RuntimeMainBrainResponse(BaseModel):
    """Dedicated main-brain cockpit payload for Runtime Center."""

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    surface: RuntimeCenterSurfaceInfo
    strategy: dict[str, Any] = Field(default_factory=dict)
    carrier: dict[str, Any] = Field(default_factory=dict)
    lanes: list[dict[str, Any]] = Field(default_factory=list)
    cycles: list[dict[str, Any]] = Field(default_factory=list)
    backlog: list[dict[str, Any]] = Field(default_factory=list)
    current_cycle: dict[str, Any] | None = None
    main_brain_planning: RuntimeMainBrainPlanningPayload = Field(
        default_factory=RuntimeMainBrainPlanningPayload,
    )
    assignments: list[dict[str, Any]] = Field(default_factory=list)
    reports: list[dict[str, Any]] = Field(default_factory=list)
    report_cognition: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)
    governance: RuntimeMainBrainGovernancePayload = Field(
        default_factory=RuntimeMainBrainGovernancePayload,
    )
    recovery: dict[str, Any] = Field(default_factory=dict)
    automation: dict[str, Any] = Field(default_factory=dict)
    evidence: RuntimeMainBrainSection = Field(default_factory=RuntimeMainBrainSection)
    decisions: RuntimeMainBrainSection = Field(default_factory=RuntimeMainBrainSection)
    patches: RuntimeMainBrainSection = Field(default_factory=RuntimeMainBrainSection)
    signals: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
