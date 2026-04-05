# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.memory.activation_models import ActivationRelationEvidence, ActivationResult, KnowledgeNeuron
from copaw.memory.activation_service import MemoryActivationService
from copaw.memory.subgraph_activation_service import SubgraphActivationService


def _fact_entry(
    entry_id: str,
    *,
    scope_type: str,
    scope_id: str,
    title: str,
    summary: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=entry_id,
        source_type="knowledge_chunk",
        source_ref=f"chunk:{entry_id}",
        scope_type=scope_type,
        scope_id=scope_id,
        title=title,
        summary=summary,
        content_excerpt=summary,
        entity_keys=["outbound"],
        opinion_keys=[],
        tags=[],
        evidence_refs=["evidence-1"],
        confidence=0.8,
        quality_score=0.7,
        source_updated_at=None,
        metadata={},
    )


def test_subgraph_activation_service_returns_task_subgraph_from_activation_result() -> None:
    activation_service = MemoryActivationService(
        derived_index_service=SimpleNamespace(
            list_fact_entries=lambda **_: [
                _fact_entry(
                    "fact-1",
                    scope_type="work_context",
                    scope_id="ctx-1",
                    title="Outbound review remains blocked",
                    summary="Evidence review is still pending.",
                ),
            ],
            list_entity_views=lambda **_: [],
            list_opinion_views=lambda **_: [],
            list_relation_views=lambda **_: [],
        ),
        strategy_memory_service=SimpleNamespace(),
    )
    service = SubgraphActivationService(memory_activation_service=activation_service)

    subgraph = service.activate_for_query(
        query="outbound review",
        work_context_id="ctx-1",
        seed_refs=["seed:outbound-review"],
        limit=4,
    )

    assert subgraph.scope.scope_type == "work_context"
    assert subgraph.scope.scope_id == "ctx-1"
    assert subgraph.seed_refs == ["seed:outbound-review"]
    assert [item.node_id for item in subgraph.nodes] == ["fact-1"]
    assert subgraph.top_evidence_refs == ["evidence-1"]


def test_subgraph_activation_service_preserves_activation_metadata_in_subgraph() -> None:
    class _StubActivationService:
        def activate_for_query(self, **kwargs: object) -> ActivationResult:
            assert kwargs["scope_type"] == "agent"
            assert kwargs["scope_id"] == "agent-1"
            return ActivationResult(
                query="agent constraint",
                scope_type="agent",
                scope_id="agent-1",
                activated_neurons=[
                    KnowledgeNeuron(
                        neuron_id="strategy-1",
                        kind="strategy",
                        scope_type="agent",
                        scope_id="agent-1",
                        title="Agent strategy",
                        summary="Keep the agent lane stable.",
                    ),
                    KnowledgeNeuron(
                        neuron_id="fact-1",
                        kind="fact",
                        scope_type="agent",
                        scope_id="agent-1",
                        title="Constraint fact",
                        summary="A constraint is active.",
                        evidence_refs=["evidence-1"],
                    ),
                ],
                contradictions=[
                    KnowledgeNeuron(
                        neuron_id="fact-contradiction",
                        kind="fact",
                        scope_type="agent",
                        scope_id="agent-1",
                        title="Contradiction fact",
                        summary="A contradiction remains open.",
                    ),
                ],
                strategy_refs=["strategy-1"],
                top_relation_kinds=["supports"],
                top_relation_evidence=[
                    ActivationRelationEvidence(
                        relation_id="relation-1",
                        relation_kind="supports",
                        source_node_id="fact-1",
                        target_node_id="strategy-1",
                        summary="Constraint fact supports the strategy.",
                        source_refs=["evidence-1"],
                    ),
                ],
                metadata={"seed_term_count": 2},
            )

    service = SubgraphActivationService(memory_activation_service=_StubActivationService())

    subgraph = service.activate_for_query(
        query="agent constraint",
        scope_type="agent",
        scope_id="agent-1",
        seed_refs=["seed:agent-1"],
    )

    assert subgraph.scope.scope_type == "agent"
    assert subgraph.scope.scope_id == "agent-1"
    assert subgraph.seed_refs == ["seed:agent-1"]
    assert subgraph.metadata["top_relation_kinds"] == ["supports"]
    assert subgraph.metadata["strategy_refs"] == ["strategy-1"]
    assert subgraph.metadata["contradiction_node_ids"] == ["fact-contradiction"]
