# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.compiler.planning.models import (
    AssignmentPlanEnvelope,
    CyclePlanningDecision,
    PlanningLaneBudget,
    PlanningStrategyConstraints,
    PlanningStrategicUncertainty,
    ReportReplanDecision,
    StrategyTriggerRule,
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
    assert replan.decision_kind == "clear"
    assert replan.directives == []


def test_strategy_constraints_keep_uncertainties_budgets_and_trigger_rules() -> None:
    constraints = PlanningStrategyConstraints(
        strategic_uncertainties=[
            PlanningStrategicUncertainty(
                uncertainty_id="uncertainty:weekend-variance",
                statement="Weekend variance cause remains uncertain.",
                scope="lane",
                impact_level="high",
                current_confidence=0.35,
                review_by_cycle="next-cycle",
                escalate_when=["confidence-drop", "target-miss"],
            )
        ],
        lane_budgets=[
            PlanningLaneBudget(
                lane_id="lane-growth",
                budget_window="next-3-cycles",
                target_share=0.5,
                min_share=0.25,
                max_share=0.75,
                review_pressure="medium",
                force_include_reason="growth-lane-underfunded",
            )
        ],
        strategy_trigger_rules=[
            StrategyTriggerRule(
                rule_id="uncertainty:weekend-variance:confidence-drop",
                source="uncertainty-register",
                decision_kind="strategy_review_required",
                summary="Escalate when confidence drops on weekend variance.",
                trigger_signals=["confidence-drop"],
                uncertainty_ids=["uncertainty:weekend-variance"],
            )
        ],
    )

    assert constraints.strategic_uncertainties[0].uncertainty_id == (
        "uncertainty:weekend-variance"
    )
    assert constraints.lane_budgets[0].lane_id == "lane-growth"
    assert constraints.strategy_trigger_rules[0].decision_kind == (
        "strategy_review_required"
    )
