# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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


class ActivationInput(BaseModel):
    query_text: str
    work_context_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    industry_instance_id: str | None = None
    owner_agent_id: str | None = None
    capability_ref: str | None = None
    environment_ref: str | None = None
    risk_level: str | None = None
    current_phase: str | None = None
    include_strategy: bool = True
    include_reports: bool = True
    limit: int = 12


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
    top_constraints: list[str] = Field(default_factory=list)
    top_next_actions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
