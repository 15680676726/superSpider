# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.compiler.planning.models import (
    AssignmentPlanEnvelope,
    CyclePlanningDecision,
    PlanningLaneBudget,
    PlanningStrategyConstraints,
    ReportReplanDecision,
)


def test_assignment_plan_envelope_keeps_formal_truth_ids() -> None:
    envelope = AssignmentPlanEnvelope(
        assignment_id="assignment-1",
        backlog_item_id="backlog-1",
        lane_id="lane-growth",
        cycle_id="cycle-daily-1",
        checkpoints=[{"kind": "verify", "label": "check result"}],
        acceptance_criteria=["result verified"],
        sidecar_plan={"checklist": ["step 1", "step 2"]},
    )

    assert envelope.assignment_id == "assignment-1"
    assert envelope.backlog_item_id == "backlog-1"
    assert envelope.sidecar_plan["checklist"] == ["step 1", "step 2"]


def test_cycle_planning_decision_keeps_selected_truth_refs() -> None:
    decision = CyclePlanningDecision(
        should_start=True,
        reason="planned-open-backlog",
        cycle_kind="daily",
        selected_backlog_item_ids=["backlog-1", "backlog-2"],
        selected_lane_ids=["lane-growth"],
        max_assignment_count=2,
        summary="Launch a daily cycle over the top weighted backlog items.",
    )

    assert decision.should_start is True
    assert decision.selected_backlog_item_ids == ["backlog-1", "backlog-2"]
    assert decision.max_assignment_count == 2


def test_strategy_constraints_and_replan_decision_default_to_sidecar_safe_empty_state() -> None:
    constraints = PlanningStrategyConstraints()
    replan = ReportReplanDecision()

    assert constraints.priority_order == []
    assert constraints.lane_weights == {}
    assert constraints.strategic_uncertainties == []
    assert constraints.lane_budgets == []
    assert constraints.strategy_trigger_rules == []
    assert replan.status == "clear"
    assert replan.strategy_change_decision is None
    assert replan.trigger_rule_ids == []
    assert replan.directives == []


def test_strategy_constraints_keep_typed_strategy_truth_and_trigger_contracts() -> None:
    constraints = PlanningStrategyConstraints(
        strategic_uncertainties=[
            {
                "uncertainty_id": "uncertainty-1",
                "statement": "Retention signal is still noisy.",
                "scope": "lane",
                "impact_level": "high",
                "current_confidence": 0.45,
                "evidence_for_refs": ["evidence-for-1"],
                "evidence_against_refs": ["evidence-against-1"],
                "review_by_cycle": "cycle-2",
                "escalate_when": ["confidence drop", "target miss"],
            }
        ],
        lane_budgets=[
            {
                "lane_id": "lane-retention",
                "budget_window": "next-3-cycles",
                "target_share": 0.6,
                "min_share": 0.4,
                "max_share": 0.75,
                "review_pressure": "protect-core-signal",
                "defer_reason": "wait for cleaner churn baseline",
                "force_include_reason": "current cycle is retention-critical",
            }
        ],
        strategy_trigger_rules=[
            {
                "rule_id": "uncertainty:uncertainty-1:confidence-drop",
                "source_type": "uncertainty_escalation",
                "source_ref": "uncertainty-1",
                "trigger_family": "confidence_collapse",
                "summary": "Review strategy when retention confidence drops again.",
                "decision_hint": "strategy_review_required",
            }
        ],
    )
    replan = ReportReplanDecision(
        strategy_change_decision="lane_reweight",
        trigger_rule_ids=["uncertainty:uncertainty-1:confidence-drop"],
    )

    assert constraints.strategic_uncertainties[0].uncertainty_id == "uncertainty-1"
    assert constraints.strategic_uncertainties[0].escalate_when == [
        "confidence drop",
        "target miss",
    ]
    assert constraints.lane_budgets[0].lane_id == "lane-retention"
    assert constraints.strategy_trigger_rules[0].trigger_family == "confidence_collapse"
    assert replan.strategy_change_decision == "lane_reweight"
    assert replan.trigger_rule_ids == ["uncertainty:uncertainty-1:confidence-drop"]


def test_lane_budget_reads_durable_underinvestment_debt_from_metadata() -> None:
    budget = PlanningLaneBudget(
        lane_id="lane-retention",
        budget_window="next-3-cycles",
        target_share=0.6,
        min_share=0.4,
        max_share=0.75,
        completed_cycles=3,
        consumed_cycles=1,
        metadata={
            "missed_target_cycles": 2,
            "consecutive_missed_cycles": 1,
        },
    )

    assert budget.underinvested_cycle_count() == 2


def test_strategy_constraints_from_context_coerces_attr_payloads_without_dict_round_trip() -> None:
    constraints = PlanningStrategyConstraints.from_context(
        {
            "strategy_constraints": SimpleNamespace(
                mission="Protect core retention quality.",
                north_star="Grow retained revenue",
                priority_order=["lane-retention"],
                lane_weights={"lane-retention": 0.7},
                planning_policy=["prefer-followup-before-net-new"],
                review_rules=["repeat-failure-needs-review"],
                paused_lane_ids=["lane-experimental"],
                current_focuses=["retention-diagnosis"],
                strategic_uncertainties=[
                    SimpleNamespace(
                        uncertainty_id="uncertainty-1",
                        statement="Retention signal is still noisy.",
                        scope="lane",
                        impact_level="high",
                        current_confidence=0.45,
                        review_by_cycle="cycle-2",
                        escalate_when=["confidence drop"],
                    ),
                ],
                lane_budgets=[
                    SimpleNamespace(
                        lane_id="lane-retention",
                        budget_window="next-3-cycles",
                        target_share=0.6,
                        min_share=0.4,
                        max_share=0.75,
                        review_pressure="protect-core-signal",
                        defer_reason="wait for cleaner churn baseline",
                    ),
                ],
                strategy_trigger_rules=[
                    SimpleNamespace(
                        rule_id="uncertainty:uncertainty-1:confidence-drop",
                        source_type="uncertainty_escalation",
                        source_ref="uncertainty-1",
                        trigger_family="confidence_collapse",
                        summary="Review strategy when retention confidence drops again.",
                        decision_hint="strategy_review_required",
                    ),
                ],
            ),
        },
    )

    assert constraints.mission == "Protect core retention quality."
    assert constraints.north_star == "Grow retained revenue"
    assert constraints.priority_order == ["lane-retention"]
    assert constraints.lane_weights == {"lane-retention": 0.7}
    assert constraints.strategic_uncertainties[0].uncertainty_id == "uncertainty-1"
    assert constraints.strategic_uncertainties[0].review_by_cycle == "cycle-2"
    assert constraints.lane_budgets[0].lane_id == "lane-retention"
    assert constraints.strategy_trigger_rules[0].trigger_family == "confidence_collapse"
