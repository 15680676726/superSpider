# -*- coding: utf-8 -*-
"""Compile persisted strategy memory into formal planning constraints."""
from __future__ import annotations

from ...state import StrategyMemoryRecord
from .models import (
    PlanningLaneBudget,
    PlanningStrategicUncertainty,
    PlanningStrategyConstraints,
    StrategyTriggerRule,
)

_UNCERTAINTY_TRIGGER_FAMILY = {
    "repeated blocker": "repeated_blocker",
    "confidence drop": "confidence_collapse",
    "target miss": "target_miss",
}

_UNCERTAINTY_DECISION_HINT = {
    "repeated blocker": "strategy_review_required",
    "confidence drop": "strategy_review_required",
    "target miss": "lane_reweight",
}


def _compile_uncertainties(strategy: StrategyMemoryRecord) -> list[PlanningStrategicUncertainty]:
    return [
        PlanningStrategicUncertainty.model_validate(
            uncertainty.model_dump(mode="python"),
        )
        for uncertainty in list(strategy.strategic_uncertainties or [])
    ]


def _compile_lane_budgets(strategy: StrategyMemoryRecord) -> list[PlanningLaneBudget]:
    return [
        PlanningLaneBudget.model_validate(
            lane_budget.model_dump(mode="python"),
        )
        for lane_budget in list(strategy.lane_budgets or [])
    ]


def _compile_trigger_rules(strategy: StrategyMemoryRecord) -> list[StrategyTriggerRule]:
    rules: list[StrategyTriggerRule] = []
    for index, review_rule in enumerate(list(strategy.review_rules or [])):
        rules.append(
            StrategyTriggerRule(
                rule_id=f"review-rule:{index}",
                source_type="review_rule",
                trigger_family="review_rule",
                summary=review_rule,
            ),
        )
    for uncertainty in list(strategy.strategic_uncertainties or []):
        for escalate_when in list(uncertainty.escalate_when or []):
            normalized = str(escalate_when).strip().lower()
            if normalized not in _UNCERTAINTY_TRIGGER_FAMILY:
                continue
            rules.append(
                StrategyTriggerRule(
                    rule_id=(
                        f"uncertainty:{uncertainty.uncertainty_id}:"
                        f"{normalized.replace(' ', '-')}"
                    ),
                    source_type="uncertainty_escalation",
                    source_ref=uncertainty.uncertainty_id,
                    trigger_family=_UNCERTAINTY_TRIGGER_FAMILY[normalized],
                    summary=f"{uncertainty.statement} ({normalized})",
                    decision_hint=_UNCERTAINTY_DECISION_HINT[normalized],
                ),
            )
    return rules


class StrategyPlanningCompiler:
    """Pure compiler layer from strategy truth to planning constraints."""

    def compile(
        self,
        strategy: StrategyMemoryRecord | None,
    ) -> PlanningStrategyConstraints:
        if strategy is None:
            return PlanningStrategyConstraints()
        return PlanningStrategyConstraints(
            mission=strategy.mission,
            north_star=strategy.north_star,
            priority_order=list(strategy.priority_order or []),
            lane_weights={
                str(lane_id): float(weight)
                for lane_id, weight in dict(strategy.lane_weights or {}).items()
                if str(lane_id).strip()
            },
            planning_policy=list(strategy.planning_policy or []),
            review_rules=list(strategy.review_rules or []),
            paused_lane_ids=list(strategy.paused_lane_ids or []),
            current_focuses=list(strategy.current_focuses or []),
            strategic_uncertainties=_compile_uncertainties(strategy),
            lane_budgets=_compile_lane_budgets(strategy),
            strategy_trigger_rules=_compile_trigger_rules(strategy),
        )
