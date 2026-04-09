# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


MemoryBackendKind = Literal[
    "truth-first",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class MemoryScopeSelector:
    scope_type: str | None = None
    scope_id: str | None = None
    task_id: str | None = None
    work_context_id: str | None = None
    agent_id: str | None = None
    industry_instance_id: str | None = None
    global_scope_id: str | None = None
    include_related_scopes: bool = True


class MemoryBackendDescriptor(BaseModel):
    backend_id: str
    label: str
    available: bool = True
    is_default: bool = False
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRecallHit(BaseModel):
    entry_id: str
    kind: str
    title: str
    summary: str = ""
    content_excerpt: str = ""
    source_type: str
    source_ref: str
    source_route: str | None = None
    scope_type: str
    scope_id: str
    owner_agent_id: str | None = None
    owner_scope: str | None = None
    industry_instance_id: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    entity_keys: list[str] = Field(default_factory=list)
    opinion_keys: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    score: float = 0.0
    backend: str = "truth-first"
    source_updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRecallResponse(BaseModel):
    query: str
    backend_requested: str | None = None
    backend_used: str
    fallback_reason: str | None = None
    hits: list[MemoryRecallHit] = Field(default_factory=list)


class MemoryRebuildSummary(BaseModel):
    scope_type: str | None = None
    scope_id: str | None = None
    fact_index_count: int = 0
    source_counts: dict[str, int] = Field(default_factory=dict)
    reflection_triggered: bool = False
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryReflectionSummary(BaseModel):
    run_id: str
    scope_type: str
    scope_id: str
    status: str
    entity_count: int = 0
    opinion_count: int = 0
    proposal_ids: list[str] = Field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
