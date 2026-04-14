from __future__ import annotations

from types import SimpleNamespace

from copaw.industry.models import IndustryExecutionSummary
from copaw.learning.models import GrowthEvent, Patch, Proposal
from copaw.state import AssignmentRecord, BacklogItemRecord, IndustryInstanceRecord, StrategyMemoryRecord

from tests.industry.test_runtime_views_split import (
    _FocusSelectionDetailRuntimeViewsHarness,
)


def test_instance_detail_exposes_single_optimization_closure_projection() -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _FocusSelectionDetailRuntimeViewsHarness(
        strategy,
        runtime_repository=None,
        assignments=[
            AssignmentRecord(
                id="assignment-1",
                industry_instance_id="industry-1",
                title="Assignment",
                summary="Assignment summary",
                status="running",
                owner_agent_id="agent-seat",
                owner_role_id="support-seat",
                task_id="task-1",
                backlog_item_id="backlog-1",
            )
        ],
        backlog_items=[
            BacklogItemRecord(
                id="backlog-1",
                industry_instance_id="industry-1",
                title="Backlog",
                summary="Backlog summary",
                status="materialized",
            )
        ],
        execution=IndustryExecutionSummary(status="executing"),
    )
    runtime_views._learning_service = SimpleNamespace(
        list_patches=lambda **kwargs: [
            Patch(
                id="patch-1",
                kind="workflow_patch",
                task_id="task-1",
                agent_id="agent-seat",
                title="Workflow patch",
                description="Tighten the workflow step",
                workflow_run_id="run-1",
                workflow_step_id="step-1",
                patch_payload={"target_surface": "workflow_run", "step_updates": {"summary": "Tightened"}},
                status="applied",
            )
        ],
        list_growth=lambda **kwargs: [
            GrowthEvent(
                id="growth-1",
                agent_id="agent-seat",
                task_id="task-1",
                change_type="patch_applied",
                description="Applied workflow patch",
                source_patch_id="patch-1",
            )
        ],
    )
    runtime_views._list_instance_proposals = lambda **kwargs: [
        Proposal(
            id="proposal-1",
            title="Improve workflow loop",
            description="Promote the follow-up into a workflow patch",
            task_id="task-1",
            agent_id="agent-seat",
            source_agent_id="copaw-main-brain",
        ).model_dump(mode="json")
    ]

    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind Robotics",
        owner_scope="industry:northwind",
        autonomy_status="active",
        lifecycle_status="running",
        agent_ids=["agent-seat"],
    )

    detail = runtime_views._build_instance_detail(
        record,
        assignment_id="assignment-1",
    ).model_dump(mode="json")

    closure = detail["optimization_closure"]
    assert closure["counts"] == {
        "proposals": 1,
        "patches": 1,
        "growth": 1,
        "decisions": 0,
    }
    assert len(closure["links"]) == 1
    link = closure["links"][0]
    assert link["task_id"] == "task-1"
    assert link["assignment_id"] == "assignment-1"
    assert link["proposal_ids"] == ["proposal-1"]
    assert link["patch_ids"] == ["patch-1"]
    assert link["growth_ids"] == ["growth-1"]
    assert link["workflow_run_ids"] == ["run-1"]
    assert link["workflow_step_ids"] == ["step-1"]
