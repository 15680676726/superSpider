# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RetrievalQuery(BaseModel):
    question: str
    goal: str
    intent: str
    requested_sources: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    workspace_root: str | None = None
    github_targets: list[str] = Field(default_factory=list)
    web_targets: list[str] = Field(default_factory=list)
    latest_required: bool = False


class RetrievalPlan(BaseModel):
    intent: str
    source_sequence: list[str] = Field(default_factory=list)
    mode_sequence: list[str] = Field(default_factory=list)
    allow_second_pass: bool = True
    max_hits_per_stage: int = 5
    budget: dict[str, Any] = Field(default_factory=dict)
    fallback_policy: str = "default"


class RetrievalHit(BaseModel):
    source_kind: str
    provider_kind: str
    hit_kind: str
    ref: str
    normalized_ref: str
    title: str = ""
    snippet: str = ""
    span: dict[str, int] | None = None
    score: float = 0.0
    relevance_score: float = 0.0
    answerability_score: float = 0.0
    freshness_score: float = 0.0
    credibility_score: float = 0.0
    structural_score: float = 0.0
    why_matched: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalRun(BaseModel):
    query: RetrievalQuery
    plan: RetrievalPlan
    stages: list[dict[str, Any]] = Field(default_factory=list)
    selected_hits: list[RetrievalHit] = Field(default_factory=list)
    dropped_hits: list[RetrievalHit] = Field(default_factory=list)
    coverage_summary: dict[str, Any] = Field(default_factory=dict)
    gaps: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)


__all__ = [
    "RetrievalHit",
    "RetrievalPlan",
    "RetrievalQuery",
    "RetrievalRun",
]
