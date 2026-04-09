# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.compiler.planning import AssignmentPlanningCompiler, PlanningStrategyConstraints
from copaw.industry.identity import EXECUTION_CORE_AGENT_ID, EXECUTION_CORE_ROLE_ID
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


def test_assignment_planner_carries_dependency_resource_and_retry_contract() -> None:
    planner = AssignmentPlanningCompiler()
    backlog_item = BacklogItemRecord(
        id="backlog-2",
        industry_instance_id="industry-1",
        lane_id="lane-ops",
        title="Publish governed partner update",
        summary="Wait for validation inputs before outbound action.",
        metadata={
            "plan_steps": ["Prepare outbound draft"],
            "dependencies": [
                {
                    "dependency_id": "dep-validate-brief",
                    "label": "Validation brief signed off",
                    "required_before": "Prepare outbound draft",
                }
            ],
            "resource_requirements": [
                {
                    "resource_ref": "browser:partner-portal",
                    "mode": "exclusive",
                }
            ],
            "capacity_requirements": [
                {
                    "capacity_ref": "seat:writer",
                    "minimum_units": 1,
                    "reason": "Need one exclusive writer seat before outbound publish.",
                }
            ],
            "retry_policy": {
                "max_attempts": 2,
                "escalate_after": 1,
                "escalation_mode": "supervisor-review",
            },
            "local_replan_policy": {
                "replan_after_blocked": 1,
                "replan_after_evidence_gap": 1,
                "replan_mode": "bounded-assignment-replan",
            },
        },
    )
    lane = OperatingLaneRecord(
        id="lane-ops",
        industry_instance_id="industry-1",
        lane_key="ops",
        title="Ops",
        owner_agent_id="ops-agent",
        owner_role_id="ops-lead",
    )

    envelope = planner.plan(
        assignment_id="assignment-2",
        cycle_id="cycle-2",
        backlog_item=backlog_item,
        lane=lane,
    )

    assert envelope.dependencies == [
        {
            "dependency_id": "dep-validate-brief",
            "label": "Validation brief signed off",
            "required_before": "Prepare outbound draft",
        }
    ]
    assert envelope.resource_requirements == [
        {
            "resource_ref": "browser:partner-portal",
            "mode": "exclusive",
        }
    ]
    assert envelope.capacity_requirements == [
        {
            "capacity_ref": "seat:writer",
            "minimum_units": 1,
            "reason": "Need one exclusive writer seat before outbound publish.",
        }
    ]
    assert envelope.retry_policy == {
        "max_attempts": 2,
        "escalate_after": 1,
        "escalation_mode": "supervisor-review",
    }
    assert envelope.local_replan_policy == {
        "replan_after_blocked": 1,
        "replan_after_evidence_gap": 1,
        "replan_mode": "bounded-assignment-replan",
    }
    assert envelope.checkpoints[0]["kind"] == "dependency"
    assert envelope.checkpoints[0]["label"] == "Validation brief signed off"
    assert any(
        checkpoint["kind"] == "resource-ready"
        and checkpoint["label"] == "browser:partner-portal"
        for checkpoint in envelope.checkpoints
    )
    assert any(
        checkpoint["kind"] == "capacity-ready"
        and checkpoint["label"] == "seat:writer"
        for checkpoint in envelope.checkpoints
    )
    assert envelope.sidecar_plan["dependencies"] == envelope.dependencies
    assert envelope.sidecar_plan["resource_requirements"] == envelope.resource_requirements
    assert envelope.sidecar_plan["capacity_requirements"] == envelope.capacity_requirements
    assert envelope.sidecar_plan["retry_policy"] == envelope.retry_policy
    assert envelope.sidecar_plan["local_replan_policy"] == envelope.local_replan_policy


def test_assignment_planner_defaults_lane_less_backlog_to_execution_core() -> None:
    planner = AssignmentPlanningCompiler()
    backlog_item = BacklogItemRecord(
        id="backlog-followup-1",
        industry_instance_id="industry-1",
        lane_id=None,
        title="Review strategy follow-up",
        summary="Materialize a main-brain follow-up without a dedicated lane owner.",
        metadata={},
    )

    envelope = planner.plan(
        assignment_id="assignment-followup-1",
        cycle_id="cycle-followup-1",
        backlog_item=backlog_item,
        lane=None,
    )

    assert envelope.owner_agent_id == EXECUTION_CORE_AGENT_ID
    assert envelope.owner_role_id == EXECUTION_CORE_ROLE_ID
