# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
from datetime import UTC, datetime

import pytest

from copaw.memory.activation_models import (
    ActivationRelationEvidence,
    ActivationResult,
    KnowledgeNeuron,
)
from copaw.state.models_memory import MemoryFactIndexRecord, MemoryRelationViewRecord


def _load_graph_models():
    try:
        return importlib.import_module("copaw.memory.knowledge_graph_models")
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in TDD red phase
        pytest.fail(f"knowledge graph models module missing: {exc}")


def test_knowledge_graph_vocab_covers_world_execution_and_human_boundary_nodes() -> None:
    graph_models = _load_graph_models()

    assert {
        "entity",
        "event",
        "fact",
        "opinion",
        "evidence",
        "constraint",
    } <= set(graph_models.WORLD_KNOWLEDGE_NODE_TYPES)
    assert {
        "strategy",
        "lane",
        "backlog",
        "cycle",
        "assignment",
        "report",
        "capability",
        "environment",
        "runtime_outcome",
    } <= set(graph_models.EXECUTION_KNOWLEDGE_NODE_TYPES)
    assert {
        "instruction",
        "approval",
        "rejection",
        "discussion",
        "consensus",
        "preference",
    } <= set(graph_models.HUMAN_BOUNDARY_NODE_TYPES)


def test_knowledge_graph_relation_contract_requires_scope_and_validity_fields() -> None:
    graph_models = _load_graph_models()
    scope = graph_models.KnowledgeGraphScope(
        scope_type="work_context",
        scope_id="ctx-1",
        owner_agent_id="agent-1",
        industry_instance_id="industry-1",
    )
    relation = graph_models.KnowledgeGraphRelation(
        relation_type="supports",
        source_id="fact-1",
        target_id="assignment-1",
        evidence_refs=["evidence-1"],
        confidence=0.9,
        scope=scope,
        valid_from=datetime(2026, 4, 5, tzinfo=UTC),
        valid_to=datetime(2026, 4, 6, tzinfo=UTC),
    )

    assert relation.relation_type == "supports"
    assert relation.source_id == "fact-1"
    assert relation.target_id == "assignment-1"
    assert relation.evidence_refs == ["evidence-1"]
    assert relation.scope.scope_type == "work_context"
    assert relation.valid_from == datetime(2026, 4, 5, tzinfo=UTC)
    assert relation.valid_to == datetime(2026, 4, 6, tzinfo=UTC)
    assert relation.status == "active"


def test_activation_result_projects_to_task_subgraph_using_unified_node_contract() -> None:
    result = ActivationResult(
        query="stabilize outbound assignment",
        scope_type="work_context",
        scope_id="ctx-1",
        seed_terms=["outbound", "assignment"],
        activated_neurons=[
            KnowledgeNeuron(
                neuron_id="strategy-1",
                kind="strategy",
                scope_type="work_context",
                scope_id="ctx-1",
                title="Outbound strategy",
                summary="Keep outbound flow stable.",
                source_refs=["strategy:1"],
            ),
            KnowledgeNeuron(
                neuron_id="fact-1",
                kind="fact",
                scope_type="work_context",
                scope_id="ctx-1",
                title="Evidence backlog exists",
                summary="Evidence review is pending.",
                evidence_refs=["evidence-1"],
            ),
            KnowledgeNeuron(
                neuron_id="entity-1",
                kind="entity",
                scope_type="work_context",
                scope_id="ctx-1",
                title="Outbound lane",
                summary="Primary execution lane.",
            ),
        ],
        top_relation_evidence=[
            ActivationRelationEvidence(
                relation_id="rel-1",
                relation_kind="supports",
                source_node_id="fact-1",
                target_node_id="strategy-1",
                summary="Evidence backlog supports the current strategy focus.",
                confidence=0.8,
                source_refs=["evidence-1"],
            )
        ],
        evidence_refs=["evidence-1"],
    )

    subgraph = result.to_task_subgraph()

    assert subgraph.scope.scope_type == "work_context"
    assert subgraph.scope.scope_id == "ctx-1"
    assert {node.node_id for node in subgraph.nodes} == {"strategy-1", "fact-1", "entity-1"}
    assert {node.node_type for node in subgraph.nodes} == {"strategy", "fact", "entity"}
    assert len(subgraph.relations) == 1
    assert subgraph.relations[0].relation_type == "supports"
    assert subgraph.relations[0].evidence_refs == ["evidence-1"]


def test_truth_first_memory_records_project_into_unified_graph_models() -> None:
    fact = MemoryFactIndexRecord(
        source_type="operator_note",
        source_ref="note:1",
        scope_type="work_context",
        scope_id="ctx-1",
        title="Operator preference",
        summary="Operator prefers outbound execution to stay evidence-first.",
        content_text="Evidence-first unless operator overrides.",
        memory_type="preference",
        evidence_refs=["evidence-1"],
        tags=["operator"],
    )
    relation_view = MemoryRelationViewRecord(
        source_node_id="fact-1",
        target_node_id="constraint-1",
        relation_kind="contradicts",
        scope_type="work_context",
        scope_id="ctx-1",
        summary="The stale path contradicts the active preference.",
        source_refs=["evidence-1"],
    )

    node = fact.as_knowledge_graph_node()
    relation = relation_view.as_knowledge_graph_relation()

    assert node.node_type == "preference"
    assert node.scope.scope_id == "ctx-1"
    assert node.evidence_refs == ["evidence-1"]
    assert relation.relation_type == "contradicts"
    assert relation.scope.scope_type == "work_context"
    assert relation.scope.scope_id == "ctx-1"


def test_knowledge_graph_writeback_change_tracks_upserts_and_invalidations() -> None:
    graph_models = _load_graph_models()
    scope = graph_models.KnowledgeGraphScope(scope_type="task", scope_id="task-1")
    node = graph_models.KnowledgeGraphNode(
        node_id="fact-1",
        node_type="fact",
        scope=scope,
        title="Fresh fact",
        summary="New fact written after execution.",
        evidence_refs=["evidence-1"],
    )
    relation = graph_models.KnowledgeGraphRelation(
        relation_type="derived_from",
        source_id="fact-1",
        target_id="report-1",
        evidence_refs=["evidence-1"],
        confidence=0.7,
        scope=scope,
    )

    change = graph_models.KnowledgeGraphWritebackChange(
        scope=scope,
        upsert_nodes=[node],
        upsert_relations=[relation],
        invalidate_node_ids=["fact-old"],
        invalidate_relation_ids=["rel-old"],
    )

    assert [item.node_id for item in change.upsert_nodes] == ["fact-1"]
    assert [item.relation_type for item in change.upsert_relations] == ["derived_from"]
    assert change.invalidate_node_ids == ["fact-old"]
    assert change.invalidate_relation_ids == ["rel-old"]
