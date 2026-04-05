# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

KnowledgeGraphScopeType = Literal["global", "industry", "agent", "task", "work_context"]

WORLD_KNOWLEDGE_NODE_TYPES = (
    "entity",
    "event",
    "fact",
    "opinion",
    "evidence",
    "constraint",
)
EXECUTION_KNOWLEDGE_NODE_TYPES = (
    "strategy",
    "lane",
    "backlog",
    "cycle",
    "assignment",
    "report",
    "capability",
    "environment",
    "runtime_outcome",
    "failure_pattern",
    "recovery_pattern",
)
HUMAN_BOUNDARY_NODE_TYPES = (
    "instruction",
    "approval",
    "rejection",
    "discussion",
    "consensus",
    "preference",
)
COMPATIBILITY_NODE_TYPES = (
    "profile",
    "episode",
    "temporary",
    "inference",
)

KNOWLEDGE_GRAPH_NODE_TYPES = (
    *WORLD_KNOWLEDGE_NODE_TYPES,
    *EXECUTION_KNOWLEDGE_NODE_TYPES,
    *HUMAN_BOUNDARY_NODE_TYPES,
    *COMPATIBILITY_NODE_TYPES,
)
KNOWLEDGE_GRAPH_RELATION_TYPES = (
    "belongs_to",
    "part_of",
    "instance_of",
    "located_in",
    "depends_on",
    "affects",
    "causes",
    "blocks",
    "supports",
    "contradicts",
    "indicates",
    "suggests",
    "uses",
    "targets",
    "produces",
    "recovers_with",
    "follows",
    "updates",
    "replaces",
    "derived_from",
    "requested_by",
    "approved_by",
    "rejected_by",
    "constrained_by",
    "discussed_with",
    # Compatibility with existing derived-memory activation edges.
    "references",
    "mentions",
    "derives",
    "supersedes",
)

WORLD_NODE_KINDS = WORLD_KNOWLEDGE_NODE_TYPES
EXECUTION_NODE_KINDS = EXECUTION_KNOWLEDGE_NODE_TYPES
HUMAN_BOUNDARY_NODE_KINDS = HUMAN_BOUNDARY_NODE_TYPES
KNOWLEDGE_GRAPH_NODE_KINDS = KNOWLEDGE_GRAPH_NODE_TYPES

_NODE_TYPE_SET = set(KNOWLEDGE_GRAPH_NODE_TYPES)
_RELATION_TYPE_SET = set(KNOWLEDGE_GRAPH_RELATION_TYPES)
_STATUS_SET = {"active", "candidate", "superseded", "expired"}


def map_activation_kind_to_graph_node_type(kind: str) -> str:
    normalized = str(kind or "").strip()
    if normalized not in _NODE_TYPE_SET:
        raise ValueError(f"unsupported activation kind for graph projection: {normalized}")
    return normalized


def map_memory_relation_kind_to_graph_relation_type(kind: str) -> str:
    normalized = str(kind or "").strip()
    if normalized not in _RELATION_TYPE_SET:
        raise ValueError(f"unsupported relation kind for graph projection: {normalized}")
    return normalized
_ACTIVATION_NODE_TYPE_MAP = {
    "strategy": "strategy",
    "fact": "fact",
    "entity": "entity",
    "opinion": "opinion",
    "profile": "fact",
    "episode": "event",
}
_MEMORY_FACT_NODE_TYPE_MAP = {
    "fact": "fact",
    "preference": "preference",
    "episode": "event",
    "temporary": "fact",
    "inference": "opinion",
}
_COMPATIBILITY_RELATION_MAP = {
    "references": "indicates",
    "mentions": "indicates",
    "derives": "derived_from",
    "supersedes": "replaces",
}


def _normalize_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        value = [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def map_activation_kind_to_graph_node_type(kind: str) -> str:
    normalized = _ACTIVATION_NODE_TYPE_MAP.get(str(kind or "").strip(), str(kind or "").strip())
    if normalized not in _NODE_TYPE_SET:
        raise ValueError(f"unsupported activation kind for graph projection: {kind}")
    return normalized


def map_memory_fact_type_to_graph_node_type(memory_type: str) -> str:
    normalized = _MEMORY_FACT_NODE_TYPE_MAP.get(str(memory_type or "").strip(), "fact")
    if normalized not in _NODE_TYPE_SET:
        raise ValueError(f"unsupported memory fact type for graph projection: {memory_type}")
    return normalized


def map_memory_relation_kind_to_graph_relation_type(relation_kind: str) -> str:
    normalized = _COMPATIBILITY_RELATION_MAP.get(
        str(relation_kind or "").strip(),
        str(relation_kind or "").strip(),
    )
    if normalized not in _RELATION_TYPE_SET:
        raise ValueError(f"unsupported memory relation kind for graph projection: {relation_kind}")
    return normalized


class KnowledgeGraphScope(BaseModel):
    scope_type: KnowledgeGraphScopeType = "global"
    scope_id: str = "runtime"
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None


class KnowledgeGraphNode(BaseModel):
    node_id: str
    node_type: str
    scope: KnowledgeGraphScope
    title: str
    summary: str = ""
    content_excerpt: str = ""
    entity_keys: list[str] = Field(default_factory=list)
    opinion_keys: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    freshness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_content_alias(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        content = payload.pop("content", None)
        if content is not None and "content_excerpt" not in payload:
            payload["content_excerpt"] = content
        return payload

    @property
    def kind(self) -> str:
        return self.node_type

    @property
    def scope_type(self) -> str:
        return self.scope.scope_type

    @property
    def scope_id(self) -> str:
        return self.scope.scope_id

    @property
    def owner_agent_id(self) -> str | None:
        return self.scope.owner_agent_id

    @property
    def industry_instance_id(self) -> str | None:
        return self.scope.industry_instance_id

    @property
    def content(self) -> str:
        return self.content_excerpt

    @field_validator(
        "entity_keys",
        "opinion_keys",
        "tags",
        "source_refs",
        "evidence_refs",
        mode="before",
    )
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return _normalize_string_list(value)

    @field_validator("node_type")
    @classmethod
    def _validate_node_type(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if normalized not in _NODE_TYPE_SET:
            raise ValueError(f"unsupported knowledge graph node type: {normalized}")
        return normalized

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        normalized = str(value or "").strip() or "active"
        if normalized not in _STATUS_SET:
            raise ValueError(f"unsupported knowledge graph node status: {normalized}")
        return normalized


class KnowledgeGraphRelation(BaseModel):
    relation_type: str
    source_id: str
    target_id: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    scope: KnowledgeGraphScope
    relation_id: str = Field(default_factory=lambda: f"relation:{uuid4().hex}")
    source_refs: list[str] = Field(default_factory=list)
    status: str = "active"
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("relation_type")
    @classmethod
    def _validate_relation_type(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if normalized not in _RELATION_TYPE_SET:
            raise ValueError(f"unsupported knowledge graph relation type: {normalized}")
        return normalized

    @field_validator("source_refs", "evidence_refs", mode="before")
    @classmethod
    def _normalize_relation_lists(cls, value: object) -> list[str]:
        return _normalize_string_list(value)

    @field_validator("status")
    @classmethod
    def _validate_relation_status(cls, value: str) -> str:
        normalized = str(value or "").strip() or "active"
        if normalized not in _STATUS_SET:
            raise ValueError(f"unsupported knowledge graph relation status: {normalized}")
        return normalized

    @property
    def scope_type(self) -> str:
        return self.scope.scope_type

    @property
    def scope_id(self) -> str:
        return self.scope.scope_id


class TaskSubgraph(BaseModel):
    scope: KnowledgeGraphScope
    query_text: str = ""
    seed_refs: list[str] = Field(default_factory=list)
    nodes: list[KnowledgeGraphNode] = Field(default_factory=list)
    relations: list[KnowledgeGraphRelation] = Field(default_factory=list)
    focus_node_ids: list[str] = Field(default_factory=list)
    top_constraint_refs: list[str] = Field(default_factory=list)
    top_evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "seed_refs",
        "focus_node_ids",
        "top_constraint_refs",
        "top_evidence_refs",
        mode="before",
    )
    @classmethod
    def _normalize_subgraph_lists(cls, value: object) -> list[str]:
        return _normalize_string_list(value)


class KnowledgeGraphWritebackChange(BaseModel):
    scope: KnowledgeGraphScope
    upsert_nodes: list[KnowledgeGraphNode] = Field(default_factory=list)
    upsert_relations: list[KnowledgeGraphRelation] = Field(default_factory=list)
    invalidate_node_ids: list[str] = Field(default_factory=list)
    invalidate_relation_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("invalidate_node_ids", "invalidate_relation_ids", mode="before")
    @classmethod
    def _normalize_invalidated_lists(cls, value: object) -> list[str]:
        return _normalize_string_list(value)


KnowledgeGraphWriteback = KnowledgeGraphWritebackChange
