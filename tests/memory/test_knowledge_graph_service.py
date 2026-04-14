# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.memory.knowledge_graph_models import (
    KnowledgeGraphNode,
    KnowledgeGraphPath,
    KnowledgeGraphRelation,
    KnowledgeGraphScope,
    KnowledgeGraphWritebackChange,
    TaskSubgraph,
)
from copaw.memory.knowledge_graph_service import KnowledgeGraphService
from copaw.state import AssignmentRecord, WorkContextRecord


def _sample_task_subgraph() -> TaskSubgraph:
    scope = KnowledgeGraphScope(
        scope_type="work_context",
        scope_id="ctx-approval",
        owner_agent_id="ops-agent",
        industry_instance_id="industry-ops",
    )
    return TaskSubgraph(
        scope=scope,
        query_text="clear outbound approval blocker",
        seed_refs=["task:task-approval-1", "work-context:ctx-approval"],
        focus_node_ids=["entity:outbound-approval", "capability:browser"],
        top_constraint_refs=["constraint:finance-signoff"],
        top_evidence_refs=["evidence:approval-1"],
        nodes=[
            KnowledgeGraphNode(
                node_id="entity:outbound-approval",
                node_type="entity",
                scope=scope,
                title="Outbound approval",
                entity_keys=["outbound-approval"],
            ),
            KnowledgeGraphNode(
                node_id="entity:finance-queue",
                node_type="entity",
                scope=scope,
                title="Finance queue",
                entity_keys=["finance-queue"],
            ),
            KnowledgeGraphNode(
                node_id="capability:browser",
                node_type="capability",
                scope=scope,
                title="Browser session",
                source_refs=["capability:browser"],
            ),
            KnowledgeGraphNode(
                node_id="environment:desktop",
                node_type="environment",
                scope=scope,
                title="Desktop session",
                source_refs=["environment:desktop:session-1"],
            ),
            KnowledgeGraphNode(
                node_id="failure:approval-gap",
                node_type="failure_pattern",
                scope=scope,
                title="Approval gap",
            ),
            KnowledgeGraphNode(
                node_id="recovery:refresh-proof",
                node_type="recovery_pattern",
                scope=scope,
                title="Refresh approval proof",
            ),
        ],
        relations=[
            KnowledgeGraphRelation(
                relation_id="rel:depends-approval",
                relation_type="depends_on",
                source_id="entity:outbound-approval",
                target_id="entity:finance-queue",
                scope=scope,
                source_refs=["memory:fact:approval-blocker"],
                evidence_refs=["evidence:approval-1"],
                metadata={"summary": "Outbound approval depends on finance queue sign-off"},
            ),
            KnowledgeGraphRelation(
                relation_id="rel:uses-browser",
                relation_type="uses",
                source_id="entity:outbound-approval",
                target_id="capability:browser",
                scope=scope,
                metadata={"summary": "Outbound approval flow uses the browser session"},
            ),
        ],
        dependency_paths=[
            KnowledgeGraphPath(
                path_type="dependency",
                summary="Finance sign-off is required before outbound approval can proceed.",
                node_ids=["entity:outbound-approval", "entity:finance-queue"],
                relation_ids=["rel:depends-approval"],
                relation_kinds=["depends_on"],
                source_refs=["memory:fact:approval-blocker"],
                evidence_refs=["evidence:approval-1"],
            ),
        ],
        blocker_paths=[
            KnowledgeGraphPath(
                path_type="blocker",
                summary="Do not advance while the finance queue still lacks approval proof.",
                node_ids=["entity:finance-queue"],
                relation_ids=["rel:depends-approval"],
                relation_kinds=["depends_on"],
            ),
        ],
        recovery_paths=[
            KnowledgeGraphPath(
                path_type="recovery",
                summary="Refresh approval proof and rerun outbound verification.",
                node_ids=["recovery:refresh-proof"],
                relation_ids=["rel:depends-approval"],
                relation_kinds=["depends_on"],
            ),
        ],
        contradiction_paths=[],
        support_paths=[],
        metadata={
            "top_entities": ["outbound-approval", "finance-queue"],
            "top_relations": ["Outbound approval depends on finance queue sign-off"],
            "top_relation_kinds": ["depends_on"],
        },
    )


class _StubSubgraphActivationService:
    def __init__(self, result: TaskSubgraph) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    def activate_for_query(self, **kwargs) -> TaskSubgraph:
        self.calls.append(kwargs)
        return self._result


class _StubWritebackService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def build_assignment_writeback(self, **kwargs) -> KnowledgeGraphWritebackChange:
        self.calls.append(("assignment", kwargs))
        scope = KnowledgeGraphScope(scope_type="industry", scope_id="industry-ops")
        return KnowledgeGraphWritebackChange(
            scope=scope,
            upsert_nodes=[
                KnowledgeGraphNode(
                    node_id="assignment:assignment-1",
                    node_type="assignment",
                    scope=scope,
                    title="Assignment 1",
                ),
            ],
        )

    def build_work_context_writeback(self, **kwargs) -> KnowledgeGraphWritebackChange:
        self.calls.append(("work_context", kwargs))
        scope = KnowledgeGraphScope(scope_type="work_context", scope_id="ctx-approval")
        return KnowledgeGraphWritebackChange(
            scope=scope,
            upsert_nodes=[
                KnowledgeGraphNode(
                    node_id="work-context:ctx-approval",
                    node_type="work_context",
                    scope=scope,
                    title="Approval context",
                ),
            ],
        )

    def apply_change(self, change: KnowledgeGraphWritebackChange) -> dict[str, object]:
        return {
            "scope_type": change.scope.scope_type,
            "scope_id": change.scope.scope_id,
            "node_ids": [item.node_id for item in change.upsert_nodes],
        }

    def summarize_change(self, change: KnowledgeGraphWritebackChange) -> dict[str, object]:
        return {
            "scope_type": change.scope.scope_type,
            "scope_id": change.scope.scope_id,
            "node_ids": [item.node_id for item in change.upsert_nodes],
        }


def test_knowledge_graph_service_builds_request_subgraph_and_summary() -> None:
    subgraph = _sample_task_subgraph()
    activation_service = _StubSubgraphActivationService(subgraph)
    service = KnowledgeGraphService(
        subgraph_activation_service=activation_service,
    )
    request = SimpleNamespace(
        task_id="task-approval-1",
        work_context_id="ctx-approval",
        industry_instance_id="industry-ops",
        agent_id="ops-agent",
    )
    intake_contract = SimpleNamespace(message_text="Clear outbound approval blocker")

    result = service.activate_request_task_subgraph(
        request=request,
        intake_contract=intake_contract,
        current_phase="main-brain-intake",
        limit=6,
    )

    assert result is subgraph
    assert activation_service.calls[0]["task_id"] == "task-approval-1"
    assert activation_service.calls[0]["work_context_id"] == "ctx-approval"
    assert activation_service.calls[0]["industry_instance_id"] == "industry-ops"
    assert activation_service.calls[0]["owner_agent_id"] == "ops-agent"
    summary = service.summarize_task_subgraph(result)
    assert summary["scope_type"] == "work_context"
    assert summary["scope_id"] == "ctx-approval"
    assert summary["node_count"] == 6
    assert summary["relation_count"] == 2
    assert summary["top_entities"] == ["outbound-approval", "finance-queue"]
    assert summary["capability_labels"] == ["Browser session"]
    assert summary["environment_labels"] == ["Desktop session"]
    assert summary["dependency_paths"] == [
        "Finance sign-off is required before outbound approval can proceed.",
    ]
    assert summary["recovery_paths"] == [
        "Refresh approval proof and rerun outbound verification.",
    ]


def test_knowledge_graph_service_exposes_execution_projection_helpers() -> None:
    stub = _StubWritebackService()
    service = KnowledgeGraphService(
        knowledge_writeback_service=stub,
    )
    assignment = AssignmentRecord(
        id="assignment-1",
        industry_instance_id="industry-ops",
        cycle_id="cycle-1",
        lane_id="lane-ops",
        owner_agent_id="ops-agent",
        title="Resolve approval blocker",
        summary="Investigate the current blocker.",
        status="queued",
    )
    work_context = WorkContextRecord(
        id="ctx-approval",
        title="Approval continuity",
        summary="Shared approval work context.",
        industry_instance_id="industry-ops",
    )

    assignment_summary = service.project_assignment(assignment=assignment)
    work_context_summary = service.project_work_context(context=work_context)

    assert stub.calls[0][0] == "assignment"
    assert stub.calls[0][1]["assignment"] is assignment
    assert assignment_summary == {
        "scope_type": "industry",
        "scope_id": "industry-ops",
        "node_ids": ["assignment:assignment-1"],
    }
    assert stub.calls[1][0] == "work_context"
    assert stub.calls[1][1]["context"] is work_context
    assert work_context_summary == {
        "scope_type": "work_context",
        "scope_id": "ctx-approval",
        "node_ids": ["work-context:ctx-approval"],
    }
