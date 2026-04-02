# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.compiler.planning.models import (
    AssignmentPlanEnvelope,
    CyclePlanningDecision,
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
    assert replan.status == "clear"
    assert replan.directives == []
