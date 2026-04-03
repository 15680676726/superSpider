# -*- coding: utf-8 -*-
"""Formal planning compiler contracts for CoPaw's truth-first planning shell."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field


TPlanningModel = TypeVar("TPlanningModel", bound=BaseModel)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="python")
        return payload if isinstance(payload, dict) else {}
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _context_override(
    context: Mapping[str, object],
    key: str,
    default: object,
) -> object:
    if key in context and context.get(key) is not None:
        return context.get(key)
    return default


def _string_list(value: object | None) -> list[str]:
    if isinstance(value, str):
        values: Sequence[object] = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        values = value
    else:
        return []
    items: list[str] = []
    seen: set[str] = set()
    for candidate in values:
        text = _string(candidate)
        if text is None or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def _coerce_model(model: type[TPlanningModel], value: object | None) -> TPlanningModel | None:
    if value is None:
        return None
    if isinstance(value, model):
        return value
    payload = _mapping(value)
    if payload:
        return model.model_validate(payload)
    try:
        return model.model_validate(value, from_attributes=True)
    except Exception:
        return None


def _coerce_model_list(model: type[TPlanningModel], value: object | None) -> list[TPlanningModel]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        candidates = list(value)
    elif value is None:
        return []
    else:
        candidates = [value]
    items: list[TPlanningModel] = []
    for candidate in candidates:
        parsed = _coerce_model(model, candidate)
        if parsed is not None:
            items.append(parsed)
    return items


def _coerce_lane_weights(value: object | None) -> dict[str, float]:
    payload = _mapping(value)
    weights: dict[str, float] = {}
    for raw_lane_id, raw_weight in payload.items():
        lane_id = _string(raw_lane_id)
        if lane_id is None:
            continue
        try:
            weights[lane_id] = float(raw_weight)
        except (TypeError, ValueError):
            continue
    return weights


StrategyChangeDecision = Literal[
    "follow_up_backlog",
    "cycle_rebalance",
    "lane_reweight",
    "strategy_review_required",
]


class PlanningStrategicUncertainty(BaseModel):
    """Planning-side view of a tracked strategic uncertainty."""

    model_config = ConfigDict(from_attributes=True)

    uncertainty_id: str = Field(..., min_length=1)
    statement: str = ""
    scope: Literal["strategy", "lane", "cycle"] = "strategy"
    impact_level: Literal["low", "medium", "high"] = "medium"
    current_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_for_refs: list[str] = Field(default_factory=list)
    evidence_against_refs: list[str] = Field(default_factory=list)
    review_by_cycle: str | None = None
    escalate_when: list[str] = Field(default_factory=list)
    lane_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanningLaneBudget(BaseModel):
    """Typed multi-cycle lane budget constraint compiled from strategy truth."""

    model_config = ConfigDict(from_attributes=True)

    lane_id: str = Field(..., min_length=1)
    budget_window: str | dict[str, Any] = Field(default="next-cycle")
    target_share: float = Field(default=0.0, ge=0.0, le=1.0)
    min_share: float = Field(default=0.0, ge=0.0, le=1.0)
    max_share: float = Field(default=1.0, ge=0.0, le=1.0)
    current_share: float | None = Field(default=None, ge=0.0, le=1.0)
    review_pressure: str = ""
    defer_reason: str | None = None
    force_include_reason: str | None = None
    completed_cycles: int = Field(default=0, ge=0)
    consumed_cycles: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def _budget_window_mapping(self) -> dict[str, Any]:
        return _mapping(self.budget_window)

    def current_share_or_default(self) -> float:
        if self.current_share is not None:
            return float(self.current_share)
        payload = self._budget_window_mapping()
        if payload:
            raw = payload.get("current_share")
            if raw is not None:
                try:
                    return float(raw)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    def completed_cycles_or_default(self) -> int:
        payload = self._budget_window_mapping()
        raw = payload.get("completed_cycles") if payload else None
        if raw is None:
            raw = self.completed_cycles
        try:
            return max(int(raw), 0)
        except (TypeError, ValueError):
            return 0

    def consumed_cycles_or_default(self) -> int:
        payload = self._budget_window_mapping()
        raw = (
            payload.get("allocated_cycles")
            or payload.get("selected_cycles")
            or payload.get("consumed_cycles")
        ) if payload else None
        if raw is None:
            raw = self.consumed_cycles
        try:
            return max(int(raw), 0)
        except (TypeError, ValueError):
            return 0

    def underinvested_cycle_count(self) -> int:
        payload = self._budget_window_mapping()
        for key in ("consecutive_missed_cycles", "missed_target_cycles", "underinvested_cycles"):
            raw = payload.get(key) if payload else None
            try:
                count = int(raw)
            except (TypeError, ValueError):
                count = 0
            if count > 0:
                return count
        return 0


class StrategyTriggerRule(BaseModel):
    """Compiled strategy-change trigger hint derived from strategy truth."""

    model_config = ConfigDict(from_attributes=True)

    rule_id: str = Field(..., min_length=1)
    source_type: Literal["review_rule", "uncertainty_escalation"] = "review_rule"
    source_ref: str | None = None
    trigger_family: str = "review_rule"
    summary: str = ""
    decision_hint: StrategyChangeDecision | None = None
    source: str = "review-rule"
    decision_kind: StrategyChangeDecision | None = None
    trigger_signals: list[str] = Field(default_factory=list)
    uncertainty_ids: list[str] = Field(default_factory=list)
    lane_ids: list[str] = Field(default_factory=list)


class PlanningStrategyConstraints(BaseModel):
    """Strategy-derived constraints that shape cycle and assignment planning."""

    model_config = ConfigDict(from_attributes=True)

    mission: str = ""
    north_star: str = ""
    priority_order: list[str] = Field(default_factory=list)
    lane_weights: dict[str, float] = Field(default_factory=dict)
    planning_policy: list[str] = Field(default_factory=list)
    review_rules: list[str] = Field(default_factory=list)
    paused_lane_ids: list[str] = Field(default_factory=list)
    current_focuses: list[str] = Field(default_factory=list)
    strategic_uncertainties: list[PlanningStrategicUncertainty] = Field(default_factory=list)
    lane_budgets: list[PlanningLaneBudget] = Field(default_factory=list)
    strategy_trigger_rules: list[StrategyTriggerRule] = Field(default_factory=list)
    graph_focus_entities: list[str] = Field(default_factory=list)
    graph_focus_opinions: list[str] = Field(default_factory=list)
    graph_focus_relations: list[str] = Field(default_factory=list)
    graph_relation_evidence: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_value(cls, value: object | None) -> PlanningStrategyConstraints:
        if isinstance(value, cls):
            return value
        if value is None:
            return cls()
        payload = _mapping(value)
        if payload:
            return cls.model_validate(payload)
        try:
            return cls.model_validate(value, from_attributes=True)
        except Exception:
            return cls()

    @classmethod
    def from_context(cls, context: Mapping[str, object] | None) -> PlanningStrategyConstraints:
        if not isinstance(context, Mapping):
            return cls()
        base = cls.from_value(context.get("strategy_constraints"))
        return cls(
            mission=_string(_context_override(context, "strategy_mission", base.mission)) or "",
            north_star=_string(_context_override(context, "strategy_north_star", base.north_star))
            or "",
            priority_order=_string_list(
                _context_override(context, "strategy_priority_order", base.priority_order),
            ),
            lane_weights=_coerce_lane_weights(
                _context_override(context, "strategy_lane_weights", base.lane_weights),
            ),
            planning_policy=_string_list(
                _context_override(context, "strategy_planning_policy", base.planning_policy),
            ),
            review_rules=_string_list(
                _context_override(context, "strategy_review_rules", base.review_rules),
            ),
            paused_lane_ids=_string_list(
                _context_override(context, "strategy_paused_lane_ids", base.paused_lane_ids),
            ),
            current_focuses=_string_list(
                _context_override(context, "strategy_current_focuses", base.current_focuses),
            ),
            strategic_uncertainties=_coerce_model_list(
                PlanningStrategicUncertainty,
                _context_override(
                    context,
                    "strategy_strategic_uncertainties",
                    base.strategic_uncertainties,
                ),
            ),
            lane_budgets=_coerce_model_list(
                PlanningLaneBudget,
                _context_override(context, "strategy_lane_budgets", base.lane_budgets),
            ),
            strategy_trigger_rules=_coerce_model_list(
                StrategyTriggerRule,
                _context_override(context, "strategy_trigger_rules", base.strategy_trigger_rules),
            ),
            graph_focus_entities=_string_list(
                _context_override(
                    context,
                    "strategy_graph_focus_entities",
                    base.graph_focus_entities,
                ),
            ),
            graph_focus_opinions=_string_list(
                _context_override(
                    context,
                    "strategy_graph_focus_opinions",
                    base.graph_focus_opinions,
                ),
            ),
        )

    def is_empty(self) -> bool:
        return not any(
            (
                self.mission,
                self.north_star,
                self.priority_order,
                self.lane_weights,
                self.planning_policy,
                self.review_rules,
                self.paused_lane_ids,
                self.current_focuses,
                self.strategic_uncertainties,
                self.lane_budgets,
                self.strategy_trigger_rules,
                self.graph_focus_entities,
                self.graph_focus_opinions,
            ),
        )

    def sidecar_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        return payload if isinstance(payload, dict) else {}


class CyclePlanningDecision(BaseModel):
    """Planner output for whether and how to materialize the next operating cycle."""

    model_config = ConfigDict(from_attributes=True)

    should_start: bool = False
    reason: str = "planner-no-open-backlog"
    cycle_kind: str = "daily"
    selected_backlog_item_ids: list[str] = Field(default_factory=list)
    selected_lane_ids: list[str] = Field(default_factory=list)
    max_assignment_count: int = 0
    summary: str = ""
    planning_policy: list[str] = Field(default_factory=list)
    affected_relation_ids: list[str] = Field(default_factory=list)
    affected_relation_kinds: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssignmentPlanEnvelope(BaseModel):
    """Assignment-local planning shell that stays sidecar to formal truth ids."""

    model_config = ConfigDict(from_attributes=True)

    assignment_id: str
    backlog_item_id: str | None = None
    lane_id: str | None = None
    cycle_id: str | None = None
    owner_agent_id: str | None = None
    owner_role_id: str | None = None
    report_back_mode: str = "summary"
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    resource_requirements: list[dict[str, Any]] = Field(default_factory=list)
    capacity_requirements: list[dict[str, Any]] = Field(default_factory=list)
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    local_replan_policy: dict[str, Any] = Field(default_factory=dict)
    sidecar_plan: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def context_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        if not isinstance(payload, dict):
            payload = {}
        return {
            "assignment_plan_envelope": payload,
            "assignment_plan_checkpoints": list(payload.get("checkpoints") or []),
            "assignment_plan_acceptance_criteria": list(
                payload.get("acceptance_criteria") or [],
            ),
            "assignment_sidecar_plan": dict(payload.get("sidecar_plan") or {}),
            "report_back_mode": self.report_back_mode,
        }


class ReportReplanDecision(BaseModel):
    """Structured replan output compiled from report synthesis pressure."""

    model_config = ConfigDict(from_attributes=True)

    decision_id: str = "report-synthesis:clear"
    status: Literal["clear", "needs-replan"] = "clear"
    decision_kind: Literal[
        "clear",
        "follow_up_backlog",
        "cycle_rebalance",
        "lane_reweight",
        "strategy_review_required",
    ] | None = None
    summary: str = "No unresolved report synthesis pressure."
    reason_ids: list[str] = Field(default_factory=list)
    source_report_ids: list[str] = Field(default_factory=list)
    topic_keys: list[str] = Field(default_factory=list)
    strategy_change_decision: StrategyChangeDecision | None = None
    trigger_family: str | None = None
    trigger_families: list[str] = Field(default_factory=list)
    trigger_rule_ids: list[str] = Field(default_factory=list)
    trigger_context: dict[str, Any] = Field(default_factory=dict)
    affected_lane_ids: list[str] = Field(default_factory=list)
    affected_uncertainty_ids: list[str] = Field(default_factory=list)
    affected_relation_ids: list[str] = Field(default_factory=list)
    affected_relation_kinds: list[str] = Field(default_factory=list)
    relation_source_refs: list[str] = Field(default_factory=list)
    directives: list[dict[str, Any]] = Field(default_factory=list)
    recommended_actions: list[dict[str, Any]] = Field(default_factory=list)
    activation: dict[str, Any] = Field(default_factory=dict)
    rationale: dict[str, Any] = Field(default_factory=dict)
    strategy_change: dict[str, Any] = Field(default_factory=dict)
