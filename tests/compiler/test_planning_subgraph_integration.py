# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.compiler.planning import (
    AssignmentPlanningCompiler,
    CyclePlanningCompiler,
    PlanningStrategyConstraints,
)
from copaw.memory.knowledge_graph_models import (
    KnowledgeGraphNode,
    KnowledgeGraphRelation,
    KnowledgeGraphScope,
    TaskSubgraph,
)
from copaw.state import BacklogItemRecord, IndustryInstanceRecord, OperatingLaneRecord


def _backlog_item(
    item_id: str,
    *,
    lane_id: str | None,
    priority: int,
    title: str,
    summary: str,
    metadata: dict[str, object] | None = None,
) -> BacklogItemRecord:
    return BacklogItemRecord(
        id=item_id,
        industry_instance_id="industry-1",
        lane_id=lane_id,
        title=title,
        summary=summary,
        priority=priority,
        metadata=metadata or {},
    )


def _task_subgraph() -> TaskSubgraph:
    scope = KnowledgeGraphScope(
        scope_type="industry",
        scope_id="industry-1",
        owner_agent_id="copaw-agent-runner",
        industry_instance_id="industry-1",
    )
    return TaskSubgraph(
        scope=scope,
        query_text="weekend variance approval review",
        seed_refs=["memory:weekend-variance-gap"],
        top_constraint_refs=["Do not publish until the approval contradiction is resolved."],
        top_evidence_refs=["memory:weekend-variance-gap"],
        nodes=[
            KnowledgeGraphNode(
                node_id="entity:weekend-variance",
                node_type="entity",
                scope=scope,
                title="Weekend inventory variance",
                summary="Variance evidence needs review before any staffing or publish move.",
                entity_keys=["weekend-variance", "inventory"],
            ),
            KnowledgeGraphNode(
                node_id="opinion:approval-caution",
                node_type="opinion",
                scope=scope,
                title="Approval contradiction caution",
                summary="Treat contradictory approval evidence as a hold signal.",
                opinion_keys=["approval:caution:contradiction"],
            ),
            KnowledgeGraphNode(
                node_id="capability:browser:partner-portal",
                node_type="capability",
                scope=scope,
                title="Partner portal browser capability",
                summary="Needed to inspect and update the governed partner portal.",
                source_refs=["capability:browser:partner-portal"],
            ),
            KnowledgeGraphNode(
                node_id="environment:browser-session",
                node_type="environment",
                scope=scope,
                title="Partner portal browser session",
                summary="Governed browser session for partner portal work.",
                source_refs=["environment:browser:partner-portal"],
            ),
            KnowledgeGraphNode(
                node_id="failure:stale-approval-cache",
                node_type="failure_pattern",
                scope=scope,
                title="Stale approval cache",
                summary="Stale approval cache can block a correct publish.",
                source_refs=["failure-pattern:stale-approval-cache"],
            ),
            KnowledgeGraphNode(
                node_id="recovery:refresh-approval-state",
                node_type="recovery_pattern",
                scope=scope,
                title="Refresh approval state before publish",
                summary="Refresh the approval state after reading the latest evidence.",
                source_refs=["recovery-pattern:refresh-approval-state"],
            ),
        ],
        relations=[
            KnowledgeGraphRelation(
                relation_id="relation-approval-1",
                relation_type="contradicts",
                source_id="entity:weekend-variance",
                target_id="opinion:approval-caution",
                scope=scope,
                source_refs=["memory:weekend-variance-gap"],
                evidence_refs=["memory:weekend-variance-gap"],
                metadata={
                    "summary": "Weekend variance contradicts publish readiness until approval evidence is refreshed.",
                },
            )
        ],
        metadata={
            "top_entities": ["weekend-variance", "inventory"],
            "top_opinions": ["approval:caution:contradiction"],
            "top_relations": ["weekend variance contradicts publish readiness"],
            "top_relation_kinds": ["contradicts"],
        },
    )


def test_cycle_planner_uses_task_subgraph_focus_without_hidden_recall() -> None:
    planner = CyclePlanningCompiler()
    subgraph = _task_subgraph()

    decision = planner.plan(
        record=IndustryInstanceRecord(
            instance_id="industry-1",
            label="Northwind",
            summary="Northwind execution shell",
            owner_scope="industry:northwind",
        ),
        current_cycle=None,
        next_cycle_due_at=None,
        open_backlog=[
            _backlog_item(
                "generic-publish-refresh",
                lane_id="lane-ops",
                priority=3,
                title="Refresh publish checklist",
                summary="Refresh the generic checklist before the next publish window.",
            ),
            _backlog_item(
                "approval-contradiction-review",
                lane_id="lane-ops",
                priority=3,
                title="Review weekend variance approval contradiction",
                summary="Resolve the approval contradiction before any partner portal publish move.",
            ),
        ],
        pending_reports=[],
        force=False,
        strategy_constraints=PlanningStrategyConstraints(),
        task_subgraph=subgraph,
    )

    assert decision.should_start is True
    assert decision.selected_backlog_item_ids[0] == "approval-contradiction-review"
    assert decision.affected_relation_ids == ["relation-approval-1"]
    assert decision.affected_relation_kinds == ["contradicts"]


def test_assignment_planner_projects_task_subgraph_into_execution_contract() -> None:
    planner = AssignmentPlanningCompiler()
    subgraph = _task_subgraph()
    backlog_item = BacklogItemRecord(
        id="backlog-1",
        industry_instance_id="industry-1",
        lane_id="lane-ops",
        title="Publish governed partner update",
        summary="Resolve the contradiction and publish the governed partner update.",
        metadata={
            "plan_steps": ["Review latest approval evidence", "Publish the governed update"],
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
        assignment_id="assignment-1",
        cycle_id="cycle-1",
        backlog_item=backlog_item,
        lane=lane,
        strategy_constraints=PlanningStrategyConstraints(),
        task_subgraph=subgraph,
    )

    knowledge = envelope.sidecar_plan["knowledge_subgraph"]

    assert knowledge["capability_refs"] == ["capability:browser:partner-portal"]
    assert knowledge["environment_refs"] == ["environment:browser:partner-portal"]
    assert knowledge["failure_patterns"] == ["Stale approval cache"]
    assert knowledge["recovery_patterns"] == ["Refresh approval state before publish"]
    assert knowledge["relation_ids"] == ["relation-approval-1"]
    assert any(
        checkpoint["kind"] == "capability-ready"
        and checkpoint["label"] == "Partner portal browser capability"
        for checkpoint in envelope.checkpoints
    )
    assert any(
        checkpoint["kind"] == "environment-ready"
        and checkpoint["label"] == "Partner portal browser session"
        for checkpoint in envelope.checkpoints
    )
    assert any(
        checkpoint["kind"] == "failure-watch"
        and checkpoint["label"] == "Stale approval cache"
        for checkpoint in envelope.checkpoints
    )
