# -*- coding: utf-8 -*-
"""Read models for the Runtime Center operator surface."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from ..runtime_recovery_report import resolve_current_recovery_report


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


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    namespace = getattr(value, "__dict__", None)
    if isinstance(namespace, dict):
        return dict(namespace)
    return {}


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _runtime_task_name(task: object, *, fallback: str) -> str:
    getter = getattr(task, "get_name", None)
    if callable(getter):
        resolved = _string(getter())
        if resolved is not None:
            return resolved
    return _string(getattr(task, "name", None)) or fallback


def _runtime_task_done(task: object) -> bool:
    checker = getattr(task, "done", None)
    if callable(checker):
        try:
            return bool(checker())
        except Exception:
            return False
    return bool(getattr(task, "done", False))


def _runtime_task_cancelled(task: object) -> bool:
    checker = getattr(task, "cancelled", None)
    if callable(checker):
        try:
            return bool(checker())
        except Exception:
            return False
    return bool(getattr(task, "cancelled", False))


def _runtime_task_status(task: object) -> str:
    if _runtime_task_cancelled(task):
        return "cancelled"
    if _runtime_task_done(task):
        return "completed"
    return "running"


def _automation_task_route(task_id: str | None) -> str | None:
    normalized = _string(task_id)
    if normalized is None:
        return None
    return f"/api/runtime-center/tasks/{normalized}"


def _automation_evidence_route(evidence_id: str | None) -> str | None:
    normalized = _string(evidence_id)
    if normalized is None:
        return None
    return f"/api/runtime-center/evidence/{normalized}"


def _automation_report_route(
    *,
    industry_instance_id: str | None,
    report_id: str | None,
) -> str | None:
    normalized_instance = _string(industry_instance_id)
    normalized_report = _string(report_id)
    if normalized_instance is None or normalized_report is None:
        return None
    return (
        f"/api/runtime-center/industry/{quote(normalized_instance)}"
        f"?report_id={quote(normalized_report)}"
    )


def _normalize_recovery_payload(
    app_state: Any,
) -> tuple[dict[str, Any] | None, str]:
    summary, source = resolve_current_recovery_report(app_state)
    normalized = _mapping(summary)
    return (normalized or None), (source or "latest")


def _normalize_automation_overview_payload(
    *,
    automation_tasks: object | None,
    automation_loop_runtime_repository: object | None,
    agent_report_repository: object | None,
) -> list[dict[str, Any]]:
    getter = getattr(automation_tasks, "overview_snapshot", None)
    if callable(getter):
        payload = getter()
        if isinstance(payload, list):
            return [
                _enrich_automation_snapshot(
                    dict(item),
                    agent_report_repository=agent_report_repository,
                )
                for item in payload
                if isinstance(item, dict)
            ]

    snapshot_map: dict[str, dict[str, Any]] = {}
    list_loops = getattr(automation_loop_runtime_repository, "list_loops", None)
    if callable(list_loops):
        try:
            for loop in list_loops(limit=None):
                payload = _mapping(loop)
                if not payload:
                    continue
                task_name = _string(payload.get("task_name"))
                if task_name is not None:
                    snapshot_map[task_name] = payload
                automation_task_id = _string(payload.get("automation_task_id"))
                if automation_task_id is not None:
                    snapshot_map[automation_task_id] = payload
        except Exception:
            snapshot_map = {}
    loop_snapshots = getattr(automation_tasks, "loop_snapshots", None)
    if callable(loop_snapshots):
        try:
            raw = loop_snapshots()
        except Exception:
            raw = {}
        if isinstance(raw, Mapping):
            for key, value in raw.items():
                if not isinstance(value, Mapping):
                    continue
                payload = dict(value)
                task_name = _string(payload.get("task_name"))
                if task_name is not None:
                    snapshot_map[task_name] = payload
                key_text = _string(key)
                if key_text is not None:
                    snapshot_map[key_text] = payload

    try:
        tasks = list(automation_tasks or [])
    except Exception:
        tasks = []
    if not tasks:
        payloads: list[dict[str, Any]] = []
        seen_snapshot_ids: set[str] = set()
        for snapshot in snapshot_map.values():
            task_name = _string(snapshot.get("task_name"))
            if task_name is None:
                continue
            snapshot_id = _string(snapshot.get("automation_task_id")) or task_name
            if snapshot_id in seen_snapshot_ids:
                continue
            seen_snapshot_ids.add(snapshot_id)
            payloads.append(
                _enrich_automation_snapshot(
                    {
                        "name": task_name,
                        "status": _string(snapshot.get("health_status"))
                        or _string(snapshot.get("loop_phase"))
                        or "idle",
                        **snapshot,
                    },
                    agent_report_repository=agent_report_repository,
                )
            )
        return payloads

    payloads: list[dict[str, Any]] = []
    for index, task in enumerate(tasks, start=1):
        name = _runtime_task_name(
            task,
            fallback=f"automation-loop-{index}",
        )
        lookup_keys = [
            name,
            name.removeprefix("copaw-automation-"),
        ]
        snapshot: dict[str, Any] = {}
        for key in lookup_keys:
            if key in snapshot_map:
                snapshot = dict(snapshot_map[key])
                break
        status = _runtime_task_status(task)
        if status == "completed" and _string(snapshot.get("health_status")) == "degraded":
            status = "degraded"
        payloads.append(
            _enrich_automation_snapshot(
                {
                    "name": name,
                    "status": status,
                    **snapshot,
                },
                agent_report_repository=agent_report_repository,
            )
        )
    live_names = {_runtime_task_name(task, fallback="") for task in tasks}
    seen_snapshot_ids: set[str] = set()
    for snapshot in snapshot_map.values():
        task_name = _string(snapshot.get("task_name"))
        snapshot_id = _string(snapshot.get("automation_task_id")) or task_name
        if snapshot_id in seen_snapshot_ids:
            continue
        seen_snapshot_ids.add(snapshot_id)
        if task_name is None or f"copaw-automation-{task_name}" in live_names:
            continue
        payloads.append(
            _enrich_automation_snapshot(
                {
                    "name": task_name,
                    "status": _string(snapshot.get("health_status"))
                    or _string(snapshot.get("loop_phase"))
                    or "idle",
                    **snapshot,
                },
                agent_report_repository=agent_report_repository,
            )
        )
    return payloads


def _enrich_automation_snapshot(
    payload: dict[str, Any],
    *,
    agent_report_repository: object | None,
) -> dict[str, Any]:
    enriched = dict(payload)
    last_task_id = _string(enriched.get("last_task_id"))
    last_evidence_id = _string(enriched.get("last_evidence_id"))
    if last_task_id is not None:
        enriched["task_route"] = _automation_task_route(last_task_id)
    if last_evidence_id is not None:
        enriched["evidence_route"] = _automation_evidence_route(last_evidence_id)
    report_payload = _resolve_automation_report_anchor(
        agent_report_repository=agent_report_repository,
        task_id=last_task_id,
    )
    if report_payload:
        enriched.update(report_payload)
    return enriched


def _resolve_automation_report_anchor(
    *,
    agent_report_repository: object | None,
    task_id: str | None,
) -> dict[str, Any]:
    normalized_task_id = _string(task_id)
    if normalized_task_id is None or agent_report_repository is None:
        return {}
    list_reports = getattr(agent_report_repository, "list_reports", None)
    if not callable(list_reports):
        return {}
    try:
        reports = list_reports(task_id=normalized_task_id, limit=1)
    except Exception:
        return {}
    if not isinstance(reports, list) or not reports:
        return {}
    report_payload = _mapping(reports[0])
    if not report_payload:
        return {}
    report_id = _string(report_payload.get("id"))
    industry_instance_id = _string(report_payload.get("industry_instance_id"))
    if report_id is None:
        return {}
    return {
        "last_report_id": report_id,
        "report_route": _automation_report_route(
            industry_instance_id=industry_instance_id,
            report_id=report_id,
        ),
    }


def _normalize_supervisor_snapshot(
    actor_supervisor: object | None,
) -> dict[str, Any] | None:
    getter = getattr(actor_supervisor, "snapshot", None)
    if callable(getter):
        payload = getter()
        if isinstance(payload, dict):
            return dict(payload)
    return None


def _normalize_runtime_contract(target: object | None) -> dict[str, Any] | None:
    payload = _mapping(getattr(target, "runtime_contract", None))
    return payload or None


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
    top_opinions: list[str] = Field(default_factory=list)
    top_relations: list[str] = Field(default_factory=list)
    top_relation_kinds: list[str] = Field(default_factory=list)
    top_constraints: list[str] = Field(default_factory=list)
    top_next_actions: list[str] = Field(default_factory=list)
    support_refs: list[str] = Field(default_factory=list)
    top_evidence_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    strategy_refs: list[str] = Field(default_factory=list)


class RuntimeKnowledgeWritebackSummary(BaseModel):
    """Compact Runtime Center projection for recent execution knowledge writeback."""

    source: str
    outcome: str
    summary: str
    capability_ref: str | None = None
    environment_ref: str | None = None
    risk_level: str | None = None
    failure_source: str | None = None
    blocked_next_step: str | None = None
    recovery_summary: str | None = None
    node_types: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class RuntimeTaskSubgraphSummary(BaseModel):
    """Compact task-subgraph projection for Runtime Center task reads."""

    source: str = "task-subgraph"
    scope_type: str
    scope_id: str
    seed_refs: list[str] = Field(default_factory=list)
    focus_node_ids: list[str] = Field(default_factory=list)
    constraint_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    node_count: int = 0
    relation_count: int = 0
    node_types: list[str] = Field(default_factory=list)
    top_entities: list[str] = Field(default_factory=list)
    top_opinions: list[str] = Field(default_factory=list)
    top_relations: list[str] = Field(default_factory=list)
    top_relation_kinds: list[str] = Field(default_factory=list)
    capability_labels: list[str] = Field(default_factory=list)
    environment_labels: list[str] = Field(default_factory=list)
    failure_patterns: list[str] = Field(default_factory=list)
    recovery_patterns: list[str] = Field(default_factory=list)
    support_paths: list[str] = Field(default_factory=list)
    contradiction_paths: list[str] = Field(default_factory=list)
    dependency_paths: list[str] = Field(default_factory=list)
    blocker_paths: list[str] = Field(default_factory=list)
    recovery_paths: list[str] = Field(default_factory=list)


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
    capability_candidate_service: Any = None
    capability_donor_service: Any = None
    capability_portfolio_service: Any = None
    skill_trial_service: Any = None
    skill_lifecycle_decision_service: Any = None
    capability_service: Any = None
    learning_service: Any = None
    agent_profile_service: Any = None
    industry_service: Any = None
    prediction_service: Any = None
    governance_service: Any = None
    strategy_memory_service: Any = None
    routine_service: Any = None
    query_execution_service: Any = None
    buddy_projection_service: Any = None
    agent_report_repository: Any = None
    cron_manager: Any = None
    automation_overview: list[dict[str, Any]] = field(default_factory=list)
    actor_supervisor_overview: dict[str, Any] | None = None
    actor_worker_runtime_contract: dict[str, Any] | None = None
    actor_supervisor_runtime_contract: dict[str, Any] | None = None
    recovery_summary: dict[str, Any] | None = None
    recovery_source: str = "latest"

    @classmethod
    def from_object(cls, app_state: Any) -> "RuntimeCenterAppStateView":
        automation_tasks = getattr(app_state, "automation_tasks", None)
        automation_loop_runtime_repository = getattr(
            app_state,
            "automation_loop_runtime_repository",
            None,
        )
        actor_supervisor = getattr(app_state, "actor_supervisor", None)
        actor_worker = getattr(app_state, "actor_worker", None)
        recovery_summary, recovery_source = _normalize_recovery_payload(app_state)
        return cls(
            state_query_service=getattr(app_state, "state_query_service", None),
            evidence_query_service=getattr(app_state, "evidence_query_service", None),
            capability_candidate_service=getattr(
                app_state,
                "capability_candidate_service",
                None,
            ),
            capability_donor_service=getattr(
                app_state,
                "capability_donor_service",
                None,
            ),
            capability_portfolio_service=getattr(
                app_state,
                "capability_portfolio_service",
                None,
            ),
            skill_trial_service=getattr(app_state, "skill_trial_service", None),
            skill_lifecycle_decision_service=getattr(
                app_state,
                "skill_lifecycle_decision_service",
                None,
            ),
            capability_service=getattr(app_state, "capability_service", None),
            learning_service=getattr(app_state, "learning_service", None),
            agent_profile_service=getattr(app_state, "agent_profile_service", None),
            industry_service=getattr(app_state, "industry_service", None),
            prediction_service=getattr(app_state, "prediction_service", None),
            governance_service=getattr(app_state, "governance_service", None),
            strategy_memory_service=getattr(app_state, "strategy_memory_service", None),
            routine_service=getattr(app_state, "routine_service", None),
            query_execution_service=getattr(app_state, "query_execution_service", None),
            buddy_projection_service=getattr(app_state, "buddy_projection_service", None),
            agent_report_repository=getattr(app_state, "agent_report_repository", None),
            cron_manager=getattr(app_state, "cron_manager", None),
            automation_overview=_normalize_automation_overview_payload(
                automation_tasks=automation_tasks,
                automation_loop_runtime_repository=automation_loop_runtime_repository,
                agent_report_repository=getattr(app_state, "agent_report_repository", None),
            ),
            actor_supervisor_overview=_normalize_supervisor_snapshot(actor_supervisor),
            actor_worker_runtime_contract=_normalize_runtime_contract(actor_worker),
            actor_supervisor_runtime_contract=_normalize_runtime_contract(actor_supervisor),
            recovery_summary=recovery_summary,
            recovery_source=recovery_source,
        )

    def resolve_recovery_summary(self) -> tuple[dict[str, Any] | None, str]:
        if self.recovery_summary is None:
            return None, self.recovery_source
        return dict(self.recovery_summary), self.recovery_source

    def automation_overview_snapshot(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.automation_overview]

    def actor_supervisor_snapshot(self) -> dict[str, Any] | None:
        if self.actor_supervisor_overview is None:
            return None
        return dict(self.actor_supervisor_overview)


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


class RuntimeHumanCockpitCard(BaseModel):
    """Compact agent/main-brain card payload for the human cockpit surface."""

    id: str
    name: str
    role: str
    status: str
    progress: int = 0
    needs_attention: bool = False
    is_main_brain: bool = False


class RuntimeHumanCockpitSummaryField(BaseModel):
    """Human-readable summary field displayed in cockpit summary tabs."""

    label: str
    value: str
    hint: str | None = None


class RuntimeHumanCockpitReportBlock(BaseModel):
    """Structured morning/evening report block for the cockpit UI."""

    title: str
    items: list[str] = Field(default_factory=list)
    generated_at: str | None = None


class RuntimeHumanCockpitTrendPoint(BaseModel):
    """Lightweight trend item rendered by the cockpit stats tab."""

    label: str
    completed: int = 0
    completion_rate: int = 0
    quality: int = 0


class RuntimeHumanCockpitApproval(BaseModel):
    """Pending approval item shown in the main-brain approval tab."""

    id: str
    kind: Literal["decision", "patch"] = "decision"
    title: str
    reason: str
    recommendation: str
    risk: str
    initiator: str
    created_at: str


class RuntimeHumanCockpitStageSummary(BaseModel):
    """Main-brain stage summary tab payload."""

    title: str
    period_label: str | None = None
    summary: str
    bullets: list[str] = Field(default_factory=list)


class RuntimeHumanCockpitTraceLine(BaseModel):
    """One lightweight human-readable trace line for cockpit replay."""

    timestamp: str
    level: Literal["info", "warn", "error"] = "info"
    message: str
    route: str | None = None


class RuntimeHumanCockpitAgent(BaseModel):
    """Human-readable cockpit payload for one execution agent."""

    agent_id: str
    card: RuntimeHumanCockpitCard
    summary_fields: list[RuntimeHumanCockpitSummaryField] = Field(default_factory=list)
    morning_report: RuntimeHumanCockpitReportBlock | None = None
    evening_report: RuntimeHumanCockpitReportBlock | None = None
    trend: list[RuntimeHumanCockpitTrendPoint] = Field(default_factory=list)
    trace: list[RuntimeHumanCockpitTraceLine] = Field(default_factory=list)


class RuntimeHumanCockpitMainBrain(BaseModel):
    """Human-readable cockpit payload for the main brain panel."""

    card: RuntimeHumanCockpitCard = Field(default_factory=lambda: RuntimeHumanCockpitCard(
        id="main-brain",
        name="伙伴",
        role="主脑",
        status="idle",
    ))
    summary_fields: list[RuntimeHumanCockpitSummaryField] = Field(default_factory=list)
    morning_report: RuntimeHumanCockpitReportBlock | None = None
    evening_report: RuntimeHumanCockpitReportBlock | None = None
    trend: list[RuntimeHumanCockpitTrendPoint] = Field(default_factory=list)
    trace: list[RuntimeHumanCockpitTraceLine] = Field(default_factory=list)
    approvals: list[RuntimeHumanCockpitApproval] = Field(default_factory=list)
    stage_summary: RuntimeHumanCockpitStageSummary | None = None


class RuntimeHumanCockpitPayload(BaseModel):
    """Dedicated human-readable cockpit contract for the Runtime Center page."""

    main_brain: RuntimeHumanCockpitMainBrain = Field(default_factory=RuntimeHumanCockpitMainBrain)
    agents: list[RuntimeHumanCockpitAgent] = Field(default_factory=list)


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
    buddy_summary: dict[str, Any] | None = None
    evidence: RuntimeMainBrainSection = Field(default_factory=RuntimeMainBrainSection)
    decisions: RuntimeMainBrainSection = Field(default_factory=RuntimeMainBrainSection)
    patches: RuntimeMainBrainSection = Field(default_factory=RuntimeMainBrainSection)
    cockpit: RuntimeHumanCockpitPayload = Field(default_factory=RuntimeHumanCockpitPayload)
    signals: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
