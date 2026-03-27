# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from .model_support import UpdatedRecord, _new_record_id, _normalize_text_list

MemoryScopeType = Literal["global", "industry", "agent", "task", "work_context"]
MemoryReflectionStatus = Literal["queued", "running", "completed", "failed"]
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
