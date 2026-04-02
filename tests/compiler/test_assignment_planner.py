# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.compiler.planning import AssignmentPlanningCompiler, PlanningStrategyConstraints
from copaw.state import BacklogItemRecord, OperatingLaneRecord


def test_assignment_planner_builds_checkpoints_acceptance_criteria_and_sidecar_plan() -> None:
    planner = AssignmentPlanningCompiler()
    backlog_item = BacklogItemRecord(
        id="backlog-1",
        industry_instance_id="industry-1",
        lane_id="lane-growth",
        title="Prepare launch follow-up",
        summary="Close the final evidence and return a governed update.",
        metadata={
            "plan_steps": ["Collect latest evidence", "Verify the outbound brief"],
            "evidence_expectations": ["artifact:launch-brief"],
            "report_back_mode": "summary",
        },
    )
    lane = OperatingLaneRecord(
        id="lane-growth",
        industry_instance_id="industry-1",
        lane_key="growth",
        title="Growth",
        owner_agent_id="agent-growth",
        owner_role_id="growth-lead",
    )

    envelope = planner.plan(
        assignment_id="assignment-1",
        cycle_id="cycle-1",
        backlog_item=backlog_item,
        lane=lane,
        strategy_constraints=PlanningStrategyConstraints(
            planning_policy=["prefer-evidence-before-external-move"],
        ),
    )

    assert envelope.assignment_id == "assignment-1"
    assert envelope.owner_agent_id == "agent-growth"
    assert envelope.owner_role_id == "growth-lead"
    assert envelope.report_back_mode == "summary"
    assert envelope.sidecar_plan["checklist"] == [
        "Collect latest evidence",
        "Verify the outbound brief",
    ]
    assert envelope.checkpoints[-1]["kind"] == "report-back"
    assert "artifact:launch-brief" in envelope.acceptance_criteria
    assert any(
        "Prepare launch follow-up" in item for item in envelope.acceptance_criteria
    )
