# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .model_support import (
    UpdatedRecord,
    _new_record_id,
    _normalize_datetime,
    _normalize_text_list,
)

MemoryScopeType = Literal["global", "industry", "agent", "task", "work_context"]
MemoryReflectionStatus = Literal["queued", "running", "completed", "failed"]
MemoryFactType = Literal["fact", "preference", "episode", "temporary", "inference"]
MemoryRelationKind = Literal[
    "updates",
    "supersedes",
    "derives",
    "references",
    "supports",
    "contradicts",
    "mentions",
]
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
