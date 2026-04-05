# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .knowledge_graph_models import (
    KnowledgeGraphPath,
    KnowledgeGraphNode,
    KnowledgeGraphRelation,
    KnowledgeGraphScope,
    TaskSubgraph,
    map_activation_kind_to_graph_node_type,
    map_memory_relation_kind_to_graph_relation_type,
)


ActivationNeuronKind = Literal["strategy", "fact", "entity", "opinion", "profile", "episode"]


class KnowledgeNeuron(BaseModel):
    neuron_id: str
    kind: ActivationNeuronKind
    scope_type: str
    scope_id: str
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    title: str
    summary: str = ""
    content_excerpt: str = ""
    entity_keys: list[str] = Field(default_factory=list)
    opinion_keys: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    quality_score: float = 0.0
    freshness_score: float = 0.0
    activation_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_graph_node(self) -> KnowledgeGraphNode:
        return KnowledgeGraphNode(
            node_id=self.neuron_id,
            node_type=map_activation_kind_to_graph_node_type(self.kind),
            scope=KnowledgeGraphScope(
                scope_type=self.scope_type,
                scope_id=self.scope_id,
                owner_agent_id=self.owner_agent_id,
                industry_instance_id=self.industry_instance_id,
            ),
            title=self.title,
            summary=self.summary,
            content_excerpt=self.content_excerpt,
            entity_keys=self.entity_keys,
            opinion_keys=self.opinion_keys,
            tags=self.tags,
            source_refs=self.source_refs,
            evidence_refs=self.evidence_refs,
            confidence=self.confidence,
            quality_score=self.quality_score,
            freshness_score=self.freshness_score,
            metadata={
                **self.metadata,
                "activation_kind": self.kind,
                "activation_score": self.activation_score,
            },
        )


class ActivationInput(BaseModel):
    query_text: str
    scope_type: str | None = None
    scope_id: str | None = None
    work_context_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    industry_instance_id: str | None = None
    global_scope_id: str | None = None
    strategy_id: str | None = None
    lane_id: str | None = None
    backlog_item_id: str | None = None
    cycle_id: str | None = None
    assignment_id: str | None = None
    report_id: str | None = None
    owner_agent_id: str | None = None
    capability_ref: str | None = None
    environment_ref: str | None = None
    risk_level: str | None = None
    current_phase: str | None = None
    seed_refs: list[str] = Field(default_factory=list)
    include_strategy: bool = True
    include_reports: bool = True
    limit: int = 12


class ActivationRelationEvidence(BaseModel):
    relation_id: str
    relation_kind: str = "references"
    summary: str = ""
    source_node_id: str | None = None
    target_node_id: str | None = None
    confidence: float = 0.0
    source_refs: list[str] = Field(default_factory=list)

    def to_graph_relation(
        self,
        *,
        scope_type: str,
        scope_id: str,
    ) -> KnowledgeGraphRelation:
        return KnowledgeGraphRelation(
            relation_id=self.relation_id,
            relation_type=map_memory_relation_kind_to_graph_relation_type(self.relation_kind),
            source_id=self.source_node_id or "unknown",
            target_id=self.target_node_id or "unknown",
            scope=KnowledgeGraphScope(scope_type=scope_type, scope_id=scope_id),
            confidence=self.confidence,
            source_refs=self.source_refs,
            evidence_refs=self.source_refs,
            metadata={"summary": self.summary},
        )


class ActivationResult(BaseModel):
    query: str
    scope_type: str
    scope_id: str
    seed_terms: list[str] = Field(default_factory=list)
    activated_neurons: list[KnowledgeNeuron] = Field(default_factory=list)
    contradictions: list[KnowledgeNeuron] = Field(default_factory=list)
    support_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    strategy_refs: list[str] = Field(default_factory=list)
    top_entities: list[str] = Field(default_factory=list)
    top_opinions: list[str] = Field(default_factory=list)
    top_relations: list[str] = Field(default_factory=list)
    top_relation_kinds: list[str] = Field(default_factory=list)
    top_relation_evidence: list[ActivationRelationEvidence] = Field(default_factory=list)
    support_paths: list[KnowledgeGraphPath] = Field(default_factory=list)
    contradiction_paths: list[KnowledgeGraphPath] = Field(default_factory=list)
    dependency_paths: list[KnowledgeGraphPath] = Field(default_factory=list)
    blocker_paths: list[KnowledgeGraphPath] = Field(default_factory=list)
    recovery_paths: list[KnowledgeGraphPath] = Field(default_factory=list)
    top_constraints: list[str] = Field(default_factory=list)
    top_next_actions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_task_subgraph(self, *, seed_refs: list[str] | None = None) -> TaskSubgraph:
        graph_nodes = [item.to_graph_node() for item in self.activated_neurons]
        graph_relations = [
            item.to_graph_relation(scope_type=self.scope_type, scope_id=self.scope_id)
            for item in self.top_relation_evidence
        ]
        return TaskSubgraph(
            query_text=self.query,
            scope=KnowledgeGraphScope(scope_type=self.scope_type, scope_id=self.scope_id),
            seed_refs=list(seed_refs or []),
            nodes=graph_nodes,
            relations=graph_relations,
            support_paths=list(self.support_paths or []),
            contradiction_paths=list(self.contradiction_paths or []),
            dependency_paths=list(self.dependency_paths or []),
            blocker_paths=list(self.blocker_paths or []),
            recovery_paths=list(self.recovery_paths or []),
            focus_node_ids=[item.node_id for item in graph_nodes[:5]],
            top_constraint_refs=list(self.top_constraints),
            top_evidence_refs=list(self.evidence_refs or self.support_refs),
            metadata=dict(self.metadata),
        )
