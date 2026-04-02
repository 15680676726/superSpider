# -*- coding: utf-8 -*-
"""Compile persisted strategy memory into formal planning constraints."""
from __future__ import annotations

from ...state import LaneBudgetRecord, StrategicUncertaintyRecord, StrategyMemoryRecord
from .models import (
    PlanningLaneBudget,
    PlanningStrategicUncertainty,
    PlanningStrategyConstraints,
    StrategyTriggerRule,
)


def _signal_slug(value: str) -> str:
    return value.strip().lower().replace("_", "-").replace(" ", "-")


def _decision_kind_from_signal(value: str) -> str:
    normalized = _signal_slug(value)
    if any(token in normalized for token in ("target-miss", "lane-miss", "reweight")):
        return "lane_reweight"
    if any(token in normalized for token in ("contradiction", "conflict", "rebalance")):
        return "cycle_rebalance"
    if any(
        token in normalized
        for token in (
            "blocker",
            "repeat-failure",
            "confidence-drop",
            "strategy-review",
            "review",
        )
    ):
        return "strategy_review_required"
    return "follow_up_backlog"


def _compile_uncertainty(
    record: StrategicUncertaintyRecord,
) -> PlanningStrategicUncertainty:
    return PlanningStrategicUncertainty(
        uncertainty_id=record.uncertainty_id,
        statement=record.statement,
        scope=record.scope,
        impact_level=record.impact_level,
        current_confidence=record.current_confidence,
        evidence_for_refs=list(record.evidence_for_refs or []),
        evidence_against_refs=list(record.evidence_against_refs or []),
        review_by_cycle=record.review_by_cycle,
        escalate_when=list(record.escalate_when or []),
        lane_id=record.lane_id,
        metadata=dict(record.metadata or {}),
    )


def _compile_lane_budget(record: LaneBudgetRecord) -> PlanningLaneBudget:
    return PlanningLaneBudget(
        lane_id=record.lane_id,
        budget_window=record.budget_window,
        target_share=record.target_share,
        min_share=record.min_share,
        max_share=record.max_share,
        current_share=record.current_share,
        review_pressure=record.review_pressure,
        defer_reason=record.defer_reason,
        force_include_reason=record.force_include_reason,
        completed_cycles=record.completed_cycles,
        consumed_cycles=record.consumed_cycles,
        metadata=dict(record.metadata or {}),
    )


class StrategyPlanningCompiler:
    """Pure compiler layer from strategy truth to planning constraints."""

    def compile(
        self,
        strategy: StrategyMemoryRecord | None,
    ) -> PlanningStrategyConstraints:
        if strategy is None:
            return PlanningStrategyConstraints()
        strategic_uncertainties = [
            _compile_uncertainty(record)
            for record in list(strategy.strategic_uncertainties or [])
        ]
        lane_budgets = self._compile_lane_budgets(strategy)
        return PlanningStrategyConstraints(
            mission=strategy.mission,
            north_star=strategy.north_star,
            priority_order=list(strategy.priority_order or []),
            lane_weights={
                str(lane_id): float(weight)
                for lane_id, weight in dict(strategy.lane_weights or {}).items()
                if str(lane_id).strip()
            },
            strategic_uncertainties=strategic_uncertainties,
            lane_budgets=lane_budgets,
            strategy_trigger_rules=self._compile_trigger_rules(
                review_rules=list(strategy.review_rules or []),
                strategic_uncertainties=strategic_uncertainties,
            ),
            planning_policy=list(strategy.planning_policy or []),
            review_rules=list(strategy.review_rules or []),
            paused_lane_ids=list(strategy.paused_lane_ids or []),
            current_focuses=list(strategy.current_focuses or []),
        )

    def _compile_lane_budgets(
        self,
        strategy: StrategyMemoryRecord,
    ) -> list[PlanningLaneBudget]:
        explicit = [
            _compile_lane_budget(record)
            for record in list(strategy.lane_budgets or [])
            if record.lane_id
        ]
        if explicit:
            return explicit
        lane_weights = {
            str(lane_id): float(weight)
            for lane_id, weight in dict(strategy.lane_weights or {}).items()
            if str(lane_id).strip()
        }
        total_weight = sum(max(weight, 0.0) for weight in lane_weights.values()) or 1.0
        compiled: list[PlanningLaneBudget] = []
        for lane_id, weight in lane_weights.items():
            target_share = max(weight, 0.0) / total_weight
            min_share = max(0.0, round(target_share * 0.5, 4))
            max_share = min(1.0, round(max(target_share, target_share * 1.5), 4))
            compiled.append(
                PlanningLaneBudget(
                    lane_id=lane_id,
                    budget_window="next-3-cycles",
                    target_share=round(target_share, 4),
                    min_share=min_share,
                    max_share=max_share,
                    review_pressure="normal",
                ),
            )
        return compiled

    def _compile_trigger_rules(
        self,
        *,
        review_rules: list[str],
        strategic_uncertainties: list[PlanningStrategicUncertainty],
    ) -> list[StrategyTriggerRule]:
        rules: list[StrategyTriggerRule] = []
        for index, review_rule in enumerate(review_rules):
            summary = str(review_rule).strip()
            if not summary:
                continue
            rules.append(
                StrategyTriggerRule(
                    rule_id=f"review-rule:{index}",
                    source="review-rule",
                    decision_kind=_decision_kind_from_signal(summary),
                    summary=summary,
                    trigger_signals=[_signal_slug(summary)],
                ),
            )
        for uncertainty in strategic_uncertainties:
            for signal in list(uncertainty.escalate_when or []):
                slug = _signal_slug(signal)
                rules.append(
                    StrategyTriggerRule(
                        rule_id=f"uncertainty:{uncertainty.uncertainty_id}:{slug}",
                        source="uncertainty-register",
                        decision_kind=_decision_kind_from_signal(signal),
                        summary=f"{uncertainty.statement or uncertainty.uncertainty_id} -> {signal}",
                        trigger_signals=[slug],
                        uncertainty_ids=[uncertainty.uncertainty_id],
                        lane_ids=[uncertainty.lane_id] if uncertainty.lane_id else [],
                    ),
                )
        return rules
