# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..media.models import MediaAnalysisSummary, MediaSourceSpec
from ..state import StrategyMemoryRecord


def _normalize_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_text_list(value: object) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _merge_text_lists(*values: object) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _normalize_text_list(value):
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return merged


def _normalize_recommendation_source_kind(value: object | None) -> str:
    text = _normalize_text(value)
    if text is None:
        return "install-template"
    if text == "github-curated":
        return "skillhub-curated"
    return text


IndustryTeamTopology = Literal["solo", "lead-plus-support", "pod", "full-team"]
IndustryPlanningMode = Literal["system-led", "operator-guided"]


def normalize_industry_team_topology(
    value: object | None,
) -> IndustryTeamTopology | None:
    text = _normalize_text(value)
    if text is None:
        return None
    normalized = text.lower().replace("_", "-").replace(" ", "-")
    alias_map = {
        "solo": "solo",
        "lead-plus-support": "lead-plus-support",
        "lead+support": "lead-plus-support",
        "lead-plus": "lead-plus-support",
        "pod": "pod",
        "full-team": "full-team",
        "full": "full-team",
    }
    return alias_map.get(normalized)


class IndustryPreviewRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    industry: str = Field(..., min_length=1)
    company_name: str | None = None
    sub_industry: str | None = None
    product: str | None = None
    business_model: str | None = None
    region: str | None = None
    target_customers: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    budget_summary: str | None = None
    notes: str | None = None
    owner_scope: str | None = None
    experience_mode: IndustryPlanningMode = "system-led"
    experience_notes: str | None = None
    operator_requirements: list[str] = Field(default_factory=list)
    media_inputs: list[MediaSourceSpec] = Field(default_factory=list)

    @field_validator(
        "target_customers",
        "channels",
        "goals",
        "constraints",
        "operator_requirements",
        mode="before",
    )
    @classmethod
    def _normalize_list_fields(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    def to_profile(self) -> "IndustryProfile":
        return IndustryProfile(
            industry=self.industry,
            company_name=self.company_name,
            sub_industry=self.sub_industry,
            product=self.product,
            business_model=self.business_model,
            region=self.region,
            target_customers=list(self.target_customers),
            channels=list(self.channels),
            goals=list(self.goals),
            constraints=list(self.constraints),
            budget_summary=self.budget_summary,
            notes=self.notes,
            experience_mode=self.experience_mode,
            experience_notes=self.experience_notes,
            operator_requirements=list(self.operator_requirements),
        )


class IndustryProfile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    schema_version: Literal["industry-profile-v1"] = "industry-profile-v1"
    industry: str = Field(..., min_length=1)
    company_name: str | None = None
    sub_industry: str | None = None
    product: str | None = None
    business_model: str | None = None
    region: str | None = None
    target_customers: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    budget_summary: str | None = None
    notes: str | None = None
    experience_mode: IndustryPlanningMode = "system-led"
    experience_notes: str | None = None
    operator_requirements: list[str] = Field(default_factory=list)

    @field_validator(
        "target_customers",
        "channels",
        "goals",
        "constraints",
        "operator_requirements",
        mode="before",
    )
    @classmethod
    def _normalize_list_fields(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    def primary_label(self) -> str:
        return self.company_name or self.product or self.sub_industry or self.industry


class IndustryRoleBlueprint(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    schema_version: Literal["industry-role-blueprint-v1"] = (
        "industry-role-blueprint-v1"
    )
    role_id: str
    agent_id: str
    actor_key: str | None = None
    actor_fingerprint: str | None = None
    name: str
    role_name: str
    role_summary: str
    mission: str
    goal_kind: str
    agent_class: Literal["system", "business"] = "business"
    employment_mode: Literal["career", "temporary"] = "career"
    activation_mode: Literal["persistent", "on-demand"] = "persistent"
    suspendable: bool = False
    reports_to: str | None = None
    risk_level: Literal["auto", "guarded", "confirm"] = "guarded"
    environment_constraints: list[str] = Field(default_factory=list)
    allowed_capabilities: list[str] = Field(default_factory=list)
    preferred_capability_families: list[str] = Field(default_factory=list)
    evidence_expectations: list[str] = Field(default_factory=list)

    @field_validator(
        "environment_constraints",
        "allowed_capabilities",
        "preferred_capability_families",
        "evidence_expectations",
        mode="before",
    )
    @classmethod
    def _normalize_role_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


IndustryAgentBlueprint = IndustryRoleBlueprint


class IndustryTeamBlueprint(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    schema_version: Literal["industry-team-blueprint-v1"] = (
        "industry-team-blueprint-v1"
    )
    team_id: str
    label: str
    summary: str
    topology: IndustryTeamTopology | None = None
    status: str | None = None
    autonomy_status: str | None = None
    lifecycle_status: str | None = None
    agents: list[IndustryRoleBlueprint] = Field(default_factory=list)

    @field_validator("topology", mode="before")
    @classmethod
    def _normalize_team_topology(
        cls,
        value: object | None,
    ) -> IndustryTeamTopology | None:
        return normalize_industry_team_topology(value)


class IndustryExecutionCoreIdentity(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    schema_version: Literal["industry-execution-core-identity-v1"] = (
        "industry-execution-core-identity-v1"
    )
    binding_id: str
    agent_id: str
    role_id: str
    industry_instance_id: str
    identity_label: str
    industry_label: str
    industry_summary: str = ""
    role_name: str
    role_summary: str = ""
    mission: str = ""
    thinking_axes: list[str] = Field(default_factory=list)
    environment_constraints: list[str] = Field(default_factory=list)
    allowed_capabilities: list[str] = Field(default_factory=list)
    operating_mode: str = "control-core"
    delegation_policy: list[str] = Field(default_factory=list)
    direct_execution_policy: list[str] = Field(default_factory=list)
    evidence_expectations: list[str] = Field(default_factory=list)

    @field_validator(
        "thinking_axes",
        "environment_constraints",
        "allowed_capabilities",
        "delegation_policy",
        "direct_execution_policy",
        "evidence_expectations",
        mode="before",
    )
    @classmethod
    def _normalize_identity_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class IndustrySeatCapabilityLayers(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    schema_version: Literal["industry-seat-capability-layers-v1"] = (
        "industry-seat-capability-layers-v1"
    )
    role_prototype_capability_ids: list[str] = Field(default_factory=list)
    seat_instance_capability_ids: list[str] = Field(default_factory=list)
    cycle_delta_capability_ids: list[str] = Field(default_factory=list)
    session_overlay_capability_ids: list[str] = Field(default_factory=list)
    effective_capability_ids: list[str] = Field(default_factory=list)

    @field_validator(
        "role_prototype_capability_ids",
        "seat_instance_capability_ids",
        "cycle_delta_capability_ids",
        "session_overlay_capability_ids",
        "effective_capability_ids",
        mode="before",
    )
    @classmethod
    def _normalize_capability_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    def merged_capability_ids(self) -> list[str]:
        if self.effective_capability_ids:
            return _merge_text_lists(self.effective_capability_ids)
        return _merge_text_lists(
            self.role_prototype_capability_ids,
            self.seat_instance_capability_ids,
            self.cycle_delta_capability_ids,
            self.session_overlay_capability_ids,
        )

    def to_metadata_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="python")
        payload["effective_capability_ids"] = self.merged_capability_ids()
        return payload

    @classmethod
    def from_metadata(
        cls,
        value: object | None,
    ) -> "IndustrySeatCapabilityLayers":
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls.model_validate(value)
        return cls()


def resolve_runtime_effective_capability_ids(
    metadata: object | None,
) -> list[str]:
    payload = metadata if isinstance(metadata, dict) else {}
    layers = IndustrySeatCapabilityLayers.from_metadata(payload.get("capability_layers"))
    effective_capability_ids = layers.merged_capability_ids()
    current_trial = payload.get("current_capability_trial")
    if not isinstance(current_trial, dict):
        return effective_capability_ids
    replacement_target_ids = set(
        _normalize_text_list(current_trial.get("replacement_target_ids")),
    )
    if not replacement_target_ids:
        return effective_capability_ids
    return [
        capability_id
        for capability_id in effective_capability_ids
        if capability_id not in replacement_target_ids
    ]


class IndustryDraftGoal(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    goal_id: str
    kind: str
    owner_agent_id: str
    title: str
    summary: str
    plan_steps: list[str] = Field(default_factory=list)

    @field_validator("plan_steps", mode="before")
    @classmethod
    def _normalize_plan_steps(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class IndustryDraftSchedule(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    schedule_id: str
    owner_agent_id: str
    title: str
    summary: str
    cron: str = Field(default="0 9 * * *")
    timezone: str = Field(default="UTC")
    dispatch_channel: str = Field(default="console")
    dispatch_mode: Literal["stream", "final"] = "stream"


class IndustryDraftPlan(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    schema_version: Literal["industry-draft-v1"] = "industry-draft-v1"
    team: IndustryTeamBlueprint
    goals: list[IndustryDraftGoal] = Field(default_factory=list)
    schedules: list[IndustryDraftSchedule] = Field(default_factory=list)
    generation_summary: str | None = None


class IndustryCapabilityRecommendation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    recommendation_id: str
    install_kind: Literal[
        "mcp-template",
        "mcp-registry",
        "builtin-runtime",
        "hub-skill",
    ] = (
        "mcp-template"
    )
    template_id: str
    install_option_key: str = ""
    title: str
    description: str = ""
    default_client_key: str = ""
    capability_ids: list[str] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    capability_families: list[str] = Field(default_factory=list)
    suggested_role_ids: list[str] = Field(default_factory=list)
    target_agent_ids: list[str] = Field(default_factory=list)
    default_enabled: bool = True
    installed: bool = False
    selected: bool = True
    required: bool = False
    risk_level: Literal["auto", "guarded", "confirm"] = "guarded"
    capability_budget_cost: int = Field(default=1, ge=0)
    source_kind: Literal[
        "install-template",
        "mcp-registry",
        "hub-search",
        "skillhub-curated",
    ] = (
        "install-template"
    )
    source_label: str = ""
    source_url: str = ""
    version: str = ""
    review_required: bool = False
    review_summary: str = ""
    review_notes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    discovery_queries: list[str] = Field(default_factory=list)
    match_signals: list[str] = Field(default_factory=list)
    governance_path: list[str] = Field(default_factory=list)
    recommendation_group: Literal[
        "system-baseline",
        "execution-core",
        "shared",
        "role-specific",
    ] = "role-specific"
    assignment_scope: Literal["system", "shared", "agent"] = "agent"
    shared_reuse: bool = False
    routes: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "capability_ids",
        "capability_tags",
        "capability_families",
        "suggested_role_ids",
        "target_agent_ids",
        "review_notes",
        "notes",
        "discovery_queries",
        "match_signals",
        "governance_path",
        mode="before",
    )
    @classmethod
    def _normalize_recommendation_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_recommendation_source_kind(
        cls,
        value: object | None,
    ) -> str:
        return _normalize_recommendation_source_kind(value)


class IndustryCapabilityRecommendationPack(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = ""
    items: list[IndustryCapabilityRecommendation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sections: list["IndustryCapabilityRecommendationSection"] = Field(
        default_factory=list,
    )

    @field_validator("warnings", mode="before")
    @classmethod
    def _normalize_pack_warnings(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class IndustryCapabilityRecommendationSection(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    section_id: str
    section_kind: Literal["system-baseline", "execution-core", "shared", "role"] = (
        "role"
    )
    title: str
    summary: str = ""
    role_id: str | None = None
    role_name: str | None = None
    target_agent_id: str | None = None
    items: list[IndustryCapabilityRecommendation] = Field(default_factory=list)


IndustryCapabilityRecommendationPack.model_rebuild()


class IndustryBootstrapInstallItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    recommendation_id: str | None = None
    install_kind: Literal[
        "mcp-template",
        "mcp-registry",
        "builtin-runtime",
        "hub-skill",
    ] = (
        "mcp-template"
    )
    template_id: str
    install_option_key: str = ""
    client_key: str | None = None
    bundle_url: str | None = None
    version: str | None = None
    source_kind: Literal[
        "install-template",
        "mcp-registry",
        "hub-search",
        "skillhub-curated",
    ] = (
        "install-template"
    )
    source_label: str | None = None
    review_acknowledged: bool = False
    enabled: bool = True
    required: bool = False
    capability_assignment_mode: Literal["replace", "merge"] = "merge"
    capability_ids: list[str] = Field(default_factory=list)
    target_agent_ids: list[str] = Field(default_factory=list)
    target_role_ids: list[str] = Field(default_factory=list)

    @field_validator(
        "capability_ids",
        "target_agent_ids",
        "target_role_ids",
        mode="before",
    )
    @classmethod
    def _normalize_install_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_install_source_kind(
        cls,
        value: object | None,
    ) -> str:
        return _normalize_recommendation_source_kind(value)


class IndustryBootstrapRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    profile: IndustryProfile
    draft: IndustryDraftPlan
    install_plan: list[IndustryBootstrapInstallItem] = Field(default_factory=list)
    owner_scope: str | None = None
    goal_priority: int = Field(default=3, ge=0)
    auto_activate: bool = True
    auto_dispatch: bool = False
    execute: bool = False
    media_inputs: list[MediaSourceSpec] = Field(default_factory=list)
    media_analysis_ids: list[str] = Field(default_factory=list)

    @field_validator("media_analysis_ids", mode="before")
    @classmethod
    def _normalize_media_analysis_ids(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class IndustryGoalSeed(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    schema_version: Literal["industry-goal-seed-v1"] = "industry-goal-seed-v1"
    goal_id: str
    kind: str
    owner_agent_id: str
    title: str
    summary: str
    plan_steps: list[str] = Field(default_factory=list)
    role: IndustryRoleBlueprint
    compiler_context: dict[str, Any] = Field(default_factory=dict)


class IndustryScheduleSeed(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    schema_version: Literal["industry-schedule-seed-v1"] = (
        "industry-schedule-seed-v1"
    )
    schedule_id: str
    title: str
    summary: str
    cron: str = Field(default="0 9 * * *")
    timezone: str = Field(default="UTC")
    owner_agent_id: str
    dispatch_channel: str = Field(default="console")
    dispatch_user_id: str
    dispatch_session_id: str
    dispatch_mode: Literal["stream", "final"] = "stream"
    request_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndustryBootstrapGoalResult(BaseModel):
    kind: str
    owner_agent_id: str
    goal: dict[str, Any]
    override: dict[str, Any]
    dispatch: dict[str, Any] | None = None
    routes: dict[str, str] = Field(default_factory=dict)


class IndustryBootstrapScheduleResult(BaseModel):
    schedule_id: str
    schedule: dict[str, Any]
    spec: dict[str, Any]
    routes: dict[str, str] = Field(default_factory=dict)


class IndustryBootstrapInstallAssignmentResult(BaseModel):
    agent_id: str
    capability_ids: list[str] = Field(default_factory=list)
    status: Literal["assigned", "failed", "skipped"] = "assigned"
    detail: str = ""
    routes: dict[str, str] = Field(default_factory=dict)

    @field_validator("capability_ids", mode="before")
    @classmethod
    def _normalize_assignment_capabilities(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class IndustryBootstrapInstallResult(BaseModel):
    recommendation_id: str | None = None
    install_kind: Literal[
        "mcp-template",
        "mcp-registry",
        "builtin-runtime",
        "hub-skill",
    ] = (
        "mcp-template"
    )
    template_id: str
    install_option_key: str = ""
    client_key: str
    capability_ids: list[str] = Field(default_factory=list)
    source_kind: Literal[
        "install-template",
        "mcp-registry",
        "hub-search",
        "skillhub-curated",
    ] = (
        "install-template"
    )
    source_label: str = ""
    source_url: str = ""
    version: str = ""
    status: Literal[
        "installed",
        "already-installed",
        "updated-existing",
        "enabled-existing",
        "failed",
        "skipped",
    ] = (
        "installed"
    )
    detail: str = ""
    installed: bool = False
    assignment_results: list[IndustryBootstrapInstallAssignmentResult] = Field(
        default_factory=list,
    )
    routes: dict[str, str] = Field(default_factory=dict)

    @field_validator("capability_ids", mode="before")
    @classmethod
    def _normalize_install_capabilities(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_install_result_source_kind(
        cls,
        value: object | None,
    ) -> str:
        return _normalize_recommendation_source_kind(value)


class IndustryReadinessCheck(BaseModel):
    key: str
    title: str
    status: Literal["ready", "warning", "missing"] = "ready"
    detail: str
    required: bool = True
    context: dict[str, Any] = Field(default_factory=dict)


class IndustryBootstrapResponse(BaseModel):
    profile: IndustryProfile
    team: IndustryTeamBlueprint
    recommendation_pack: IndustryCapabilityRecommendationPack = Field(
        default_factory=IndustryCapabilityRecommendationPack,
    )
    install_results: list[IndustryBootstrapInstallResult] = Field(default_factory=list)
    goals: list[IndustryBootstrapGoalResult] = Field(default_factory=list)
    schedules: list[IndustryBootstrapScheduleResult] = Field(default_factory=list)
    readiness_checks: list[IndustryReadinessCheck] = Field(default_factory=list)
    media_analyses: list[MediaAnalysisSummary] = Field(default_factory=list)
    routes: dict[str, Any] = Field(default_factory=dict)


class IndustryPreviewResponse(BaseModel):
    profile: IndustryProfile
    draft: IndustryDraftPlan
    recommendation_pack: IndustryCapabilityRecommendationPack = Field(
        default_factory=IndustryCapabilityRecommendationPack,
    )
    readiness_checks: list[IndustryReadinessCheck] = Field(default_factory=list)
    can_activate: bool = True
    media_analyses: list[MediaAnalysisSummary] = Field(default_factory=list)
    media_warnings: list[str] = Field(default_factory=list)

    @field_validator("media_warnings", mode="before")
    @classmethod
    def _normalize_media_warnings(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class IndustryReportSnapshot(BaseModel):
    window: Literal["daily", "weekly"]
    since: datetime
    until: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_count: int = 0
    proposal_count: int = 0
    patch_count: int = 0
    applied_patch_count: int = 0
    growth_count: int = 0
    decision_count: int = 0
    recent_evidence: list[dict[str, Any]] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class IndustryInstanceSummary(BaseModel):
    instance_id: str
    bootstrap_kind: Literal["industry-v1"] = "industry-v1"
    label: str
    summary: str
    owner_scope: str
    profile: IndustryProfile
    team: IndustryTeamBlueprint
    execution_core_identity: IndustryExecutionCoreIdentity | None = None
    strategy_memory: StrategyMemoryRecord | None = None
    status: str = "active"
    autonomy_status: str | None = None
    lifecycle_status: str | None = None
    updated_at: datetime | None = None
    stats: dict[str, int] = Field(default_factory=dict)
    routes: dict[str, Any] = Field(default_factory=dict)


class IndustryExecutionSummary(BaseModel):
    status: str = "idle"
    current_focus_id: str | None = None
    current_focus: str | None = None
    current_owner_agent_id: str | None = None
    current_owner: str | None = None
    current_risk: str | None = None
    evidence_count: int = 0
    latest_evidence_summary: str | None = None
    next_step: str | None = None
    current_task_id: str | None = None
    current_task_route: str | None = None
    current_stage: str | None = None
    trigger_source: str | None = None
    trigger_actor: str | None = None
    trigger_reason: str | None = None
    blocked_reason: str | None = None
    stuck_reason: str | None = None
    updated_at: datetime | None = None


class IndustryMainChainNode(BaseModel):
    node_id: str
    label: str
    status: str = "idle"
    truth_source: str
    current_ref: str | None = None
    route: str | None = None
    summary: str | None = None
    backflow_port: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class IndustryMainChainGraph(BaseModel):
    schema_version: Literal["industry-main-chain-v1"] = "industry-main-chain-v1"
    loop_state: str = "idle"
    current_focus_id: str | None = None
    current_focus: str | None = None
    current_owner_agent_id: str | None = None
    current_owner: str | None = None
    current_risk: str | None = None
    latest_evidence_summary: str | None = None
    nodes: list[IndustryMainChainNode] = Field(default_factory=list)


class IndustryDetailFocusSelection(BaseModel):
    selection_kind: Literal["assignment", "backlog"]
    assignment_id: str | None = None
    backlog_item_id: str | None = None
    title: str | None = None
    summary: str | None = None
    status: str | None = None
    route: str | None = None


class IndustryMainBrainPlanningSurface(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    is_truth_store: bool = False
    source: Literal["industry-runtime-read-model"] = "industry-runtime-read-model"
    strategy_constraints: dict[str, Any] = Field(default_factory=dict)
    latest_cycle_decision: dict[str, Any] = Field(default_factory=dict)
    focused_assignment_plan: dict[str, Any] = Field(default_factory=dict)
    replan: dict[str, Any] = Field(default_factory=dict)


class IndustryInstanceDetail(IndustryInstanceSummary):
    goals: list[dict[str, Any]] = Field(default_factory=list)
    agents: list[dict[str, Any]] = Field(default_factory=list)
    schedules: list[dict[str, Any]] = Field(default_factory=list)
    lanes: list[dict[str, Any]] = Field(default_factory=list)
    backlog: list[dict[str, Any]] = Field(default_factory=list)
    staffing: dict[str, Any] = Field(default_factory=dict)
    current_cycle: dict[str, Any] | None = None
    cycles: list[dict[str, Any]] = Field(default_factory=list)
    assignments: list[dict[str, Any]] = Field(default_factory=list)
    agent_reports: list[dict[str, Any]] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    patches: list[dict[str, Any]] = Field(default_factory=list)
    growth: list[dict[str, Any]] = Field(default_factory=list)
    proposals: list[dict[str, Any]] = Field(default_factory=list)
    acquisition_proposals: list[dict[str, Any]] = Field(default_factory=list)
    install_binding_plans: list[dict[str, Any]] = Field(default_factory=list)
    onboarding_runs: list[dict[str, Any]] = Field(default_factory=list)
    execution: IndustryExecutionSummary | None = None
    main_chain: IndustryMainChainGraph | None = None
    main_brain_planning: IndustryMainBrainPlanningSurface | None = None
    focus_selection: IndustryDetailFocusSelection | None = None
    reports: dict[str, IndustryReportSnapshot] = Field(default_factory=dict)
    media_analyses: list[MediaAnalysisSummary] = Field(default_factory=list)


def default_report_window(window: Literal["daily", "weekly"]) -> IndustryReportSnapshot:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=1 if window == "daily" else 7)
    return IndustryReportSnapshot(window=window, since=since, until=now)

