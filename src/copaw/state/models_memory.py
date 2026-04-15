# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ..memory.knowledge_graph_models import (
    KnowledgeGraphNode,
    KnowledgeGraphRelation,
    KnowledgeGraphScope,
    map_memory_fact_type_to_graph_node_type,
    map_memory_relation_kind_to_graph_relation_type,
)
from .model_support import (
    UpdatedRecord,
    _new_record_id,
    _normalize_datetime,
    _normalize_text_list,
)

MemoryScopeType = Literal["global", "industry", "agent", "task", "work_context"]
MemoryReflectionStatus = Literal["queued", "running", "completed", "failed"]
MemoryFactType = Literal["fact", "preference", "episode", "temporary", "inference"]
MemoryRelationKind = str
MemorySleepTriggerKind = Literal["scheduled", "idle", "manual"]
MemorySleepJobStatus = Literal["queued", "running", "completed", "failed", "skipped"]
MemorySleepArtifactStatus = Literal["active", "superseded"]
MemorySoftRuleState = Literal["candidate", "active", "promoted", "rejected", "expired"]
MemoryConflictProposalStatus = Literal["pending", "accepted", "rejected", "expired"]
MemoryOpinionStance = Literal[
    "supporting",
    "neutral",
    "caution",
    "requirement",
    "preference",
    "recommendation",
]


class MemoryFactIndexRecord(UpdatedRecord):
    """Rebuildable memory index entry derived from canonical state/evidence."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    source_type: str = Field(..., min_length=1)
    source_ref: str = Field(..., min_length=1)
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    owner_agent_id: str | None = None
    owner_scope: str | None = None
    industry_instance_id: str | None = None
    title: str = Field(..., min_length=1)
    summary: str = ""
    content_excerpt: str = ""
    content_text: str = ""
    entity_keys: list[str] = Field(default_factory=list)
    opinion_keys: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    role_bindings: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.5, ge=0.0, le=1.0)
    memory_type: MemoryFactType = "fact"
    relation_kind: MemoryRelationKind = "references"
    supersedes_entry_id: str | None = None
    is_latest: bool = True
    valid_from: datetime | None = None
    expires_at: datetime | None = None
    confidence_tier: str = Field(default="standard", min_length=1)
    source_updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "entity_keys",
        "opinion_keys",
        "tags",
        "role_bindings",
        "evidence_refs",
        mode="before",
    )
    @classmethod
    def _normalize_index_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    @field_validator("valid_from", mode="after")
    @classmethod
    def _normalize_valid_from(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _normalize_datetime(value)

    @model_validator(mode="after")
    def _default_valid_from(self) -> "MemoryFactIndexRecord":
        if self.valid_from is None:
            self.valid_from = self.created_at
        return self

    def as_knowledge_graph_node(self) -> KnowledgeGraphNode:
        node_type = self.metadata.get("knowledge_graph_node_type") or map_memory_fact_type_to_graph_node_type(
            self.memory_type
        )
        return KnowledgeGraphNode(
            node_id=self.id,
            node_type=str(node_type),
            scope=KnowledgeGraphScope(
                scope_type=self.scope_type,
                scope_id=self.scope_id,
                owner_agent_id=self.owner_agent_id,
                industry_instance_id=self.industry_instance_id,
            ),
            title=self.title,
            summary=self.summary,
            content=self.content_text or self.content_excerpt,
            entity_keys=self.entity_keys,
            opinion_keys=self.opinion_keys,
            tags=[self.memory_type, *self.tags],
            source_refs=[self.source_ref],
            evidence_refs=self.evidence_refs,
            confidence=self.confidence,
            quality_score=self.quality_score,
            status="active" if self.is_latest else "superseded",
            metadata={
                **self.metadata,
                "memory_type": self.memory_type,
                "relation_kind": self.relation_kind,
                "owner_scope": self.owner_scope,
                "role_bindings": list(self.role_bindings),
                "supersedes_entry_id": self.supersedes_entry_id,
                "source_updated_at": self.source_updated_at.isoformat()
                if self.source_updated_at is not None
                else None,
                "valid_from": self.valid_from.isoformat() if self.valid_from is not None else None,
                "expires_at": self.expires_at.isoformat() if self.expires_at is not None else None,
            },
        )


class MemoryProfileViewRecord(UpdatedRecord):
    """Compiled profile-first memory view derived from canonical truth."""

    profile_id: str = Field(default_factory=_new_record_id, min_length=1)
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    static_profile: str = ""
    dynamic_profile: str = ""
    active_preferences: list[str] = Field(default_factory=list)
    active_constraints: list[str] = Field(default_factory=list)
    current_focus_summary: str = ""
    current_operating_context: str = ""
    source_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "active_preferences",
        "active_constraints",
        "source_refs",
        mode="before",
    )
    @classmethod
    def _normalize_profile_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class MemoryEpisodeViewRecord(UpdatedRecord):
    """Summarized continuous execution stretch derived from canonical truth."""

    episode_id: str = Field(default_factory=_new_record_id, min_length=1)
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    headline: str = Field(..., min_length=1)
    summary: str = ""
    source_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    work_context_id: str | None = None
    control_thread_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "source_refs",
        "evidence_refs",
        mode="before",
    )
    @classmethod
    def _normalize_episode_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    @field_validator("ended_at", mode="after")
    @classmethod
    def _normalize_ended_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _normalize_datetime(value)


class MemoryEntityViewRecord(UpdatedRecord):
    """Compiled entity summary derived from memory fact index entries."""

    entity_id: str = Field(default_factory=_new_record_id, min_length=1)
    entity_key: str = Field(..., min_length=1)
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    display_name: str = Field(..., min_length=1)
    entity_type: str = Field(default="concept", min_length=1)
    summary: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    supporting_refs: list[str] = Field(default_factory=list)
    contradicting_refs: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "supporting_refs",
        "contradicting_refs",
        "related_entities",
        "source_refs",
        mode="before",
    )
    @classmethod
    def _normalize_entity_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class MemoryRelationViewRecord(UpdatedRecord):
    """Derived relation edge persisted for activation/read-model queries."""

    relation_id: str = Field(default_factory=_new_record_id, min_length=1)
    source_node_id: str = Field(..., min_length=1)
    target_node_id: str = Field(..., min_length=1)
    relation_kind: MemoryRelationKind = "references"
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    summary: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_refs", mode="before")
    @classmethod
    def _normalize_relation_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    def as_knowledge_graph_relation(self) -> KnowledgeGraphRelation:
        return KnowledgeGraphRelation(
            relation_id=self.relation_id,
            relation_type=map_memory_relation_kind_to_graph_relation_type(self.relation_kind),
            source_id=self.source_node_id,
            target_id=self.target_node_id,
            scope=KnowledgeGraphScope(
                scope_type=self.scope_type,
                scope_id=self.scope_id,
                owner_agent_id=self.owner_agent_id,
                industry_instance_id=self.industry_instance_id,
            ),
            confidence=self.confidence,
            source_refs=self.source_refs,
            evidence_refs=self.source_refs,
            metadata={
                **self.metadata,
                "summary": self.summary,
                "memory_relation_kind": self.relation_kind,
            },
        )


class MemoryOpinionViewRecord(UpdatedRecord):
    """Compiled opinion/confidence summary derived from memory fact index entries."""

    opinion_id: str = Field(default_factory=_new_record_id, min_length=1)
    subject_key: str = Field(..., min_length=1)
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    opinion_key: str = Field(..., min_length=1)
    stance: MemoryOpinionStance = "neutral"
    summary: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    supporting_refs: list[str] = Field(default_factory=list)
    contradicting_refs: list[str] = Field(default_factory=list)
    entity_keys: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    last_reflected_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "supporting_refs",
        "contradicting_refs",
        "entity_keys",
        "source_refs",
        mode="before",
    )
    @classmethod
    def _normalize_opinion_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class MemoryReflectionRunRecord(UpdatedRecord):
    """Recorded memory reflection job over a scoped set of fact index entries."""

    run_id: str = Field(default_factory=_new_record_id, min_length=1)
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    trigger_kind: str = Field(default="manual", min_length=1)
    status: MemoryReflectionStatus = "queued"
    summary: str = ""
    source_refs: list[str] = Field(default_factory=list)
    generated_entity_ids: list[str] = Field(default_factory=list)
    generated_opinion_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator(
        "source_refs",
        "generated_entity_ids",
        "generated_opinion_ids",
        mode="before",
    )
    @classmethod
    def _normalize_reflection_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class MemorySleepScopeStateRecord(UpdatedRecord):
    """Persistent dirty-state and latest sleep-run state for one formal scope."""

    scope_key: str = Field(default="", min_length=1)
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    is_dirty: bool = False
    dirty_reasons: list[str] = Field(default_factory=list)
    dirty_source_refs: list[str] = Field(default_factory=list)
    dirty_count: int = Field(default=0, ge=0)
    first_dirtied_at: datetime | None = None
    last_dirtied_at: datetime | None = None
    last_sleep_job_id: str | None = None
    last_sleep_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("dirty_reasons", "dirty_source_refs", mode="before")
    @classmethod
    def _normalize_dirty_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    @field_validator(
        "first_dirtied_at",
        "last_dirtied_at",
        "last_sleep_at",
        mode="after",
    )
    @classmethod
    def _normalize_optional_datetimes(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _normalize_datetime(value)

    @model_validator(mode="after")
    def _default_scope_key(self) -> "MemorySleepScopeStateRecord":
        if not self.scope_key:
            self.scope_key = f"{self.scope_type}:{self.scope_id}"
        return self


class MemorySleepJobRecord(UpdatedRecord):
    """One formal sleep-layer run over a dirty scope."""

    job_id: str = Field(default_factory=_new_record_id, min_length=1)
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    owner_agent_id: str | None = None
    industry_instance_id: str | None = None
    trigger_kind: MemorySleepTriggerKind = "manual"
    window_start: datetime | None = None
    window_end: datetime | None = None
    status: MemorySleepJobStatus = "queued"
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    model_ref: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("input_refs", "output_refs", mode="before")
    @classmethod
    def _normalize_job_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    @field_validator(
        "window_start",
        "window_end",
        "started_at",
        "completed_at",
        mode="after",
    )
    @classmethod
    def _normalize_job_datetimes(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _normalize_datetime(value)


class MemoryScopeDigestRecord(UpdatedRecord):
    """Next-day high-level digest over one formal memory scope."""

    digest_id: str = Field(default_factory=_new_record_id, min_length=1)
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    headline: str = Field(..., min_length=1)
    summary: str = ""
    current_constraints: list[str] = Field(default_factory=list)
    current_focus: list[str] = Field(default_factory=list)
    top_entities: list[str] = Field(default_factory=list)
    top_relations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_job_id: str | None = None
    version: int = Field(default=1, ge=1)
    status: MemorySleepArtifactStatus = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "current_constraints",
        "current_focus",
        "top_entities",
        "top_relations",
        "evidence_refs",
        mode="before",
    )
    @classmethod
    def _normalize_digest_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class MemoryAliasMapRecord(UpdatedRecord):
    """Canonical term plus sleep-derived aliases for one scope."""

    alias_id: str = Field(default_factory=_new_record_id, min_length=1)
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    canonical_term: str = Field(..., min_length=1)
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)
    source_job_id: str | None = None
    status: MemorySleepArtifactStatus = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("aliases", "evidence_refs", mode="before")
    @classmethod
    def _normalize_alias_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class MemoryMergeResultRecord(UpdatedRecord):
    """Sleep-derived merged topic over multiple truth-backed sources."""

    merge_id: str = Field(default_factory=_new_record_id, min_length=1)
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    merged_title: str = Field(..., min_length=1)
    merged_summary: str = ""
    merged_source_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_job_id: str | None = None
    status: MemorySleepArtifactStatus = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("merged_source_refs", "evidence_refs", mode="before")
    @classmethod
    def _normalize_merge_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class MemorySoftRuleRecord(UpdatedRecord):
    """Sleep-derived soft rule that may auto-apply on the read path."""

    rule_id: str = Field(default_factory=_new_record_id, min_length=1)
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    rule_text: str = Field(..., min_length=1)
    rule_kind: str = Field(default="general", min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    hit_count: int = Field(default=0, ge=0)
    day_span: int = Field(default=0, ge=0)
    conflict_count: int = Field(default=0, ge=0)
    risk_level: str = Field(default="low", min_length=1)
    state: MemorySoftRuleState = "candidate"
    source_job_id: str | None = None
    expires_at: datetime | None = None
    last_supported_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _normalize_rule_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    @field_validator("expires_at", "last_supported_at", mode="after")
    @classmethod
    def _normalize_rule_datetimes(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _normalize_datetime(value)


class MemoryConflictProposalRecord(UpdatedRecord):
    """High-risk sleep conclusion that must stay proposal-only."""

    proposal_id: str = Field(default_factory=_new_record_id, min_length=1)
    scope_type: MemoryScopeType = "global"
    scope_id: str = Field(default="runtime", min_length=1)
    proposal_kind: str = Field(default="conflict", min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = ""
    conflicting_refs: list[str] = Field(default_factory=list)
    supporting_refs: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    risk_level: str = Field(default="high", min_length=1)
    status: MemoryConflictProposalStatus = "pending"
    source_job_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("conflicting_refs", "supporting_refs", mode="before")
    @classmethod
    def _normalize_proposal_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)
