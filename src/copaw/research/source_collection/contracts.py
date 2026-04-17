# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CollectionAction = Literal["discover", "read", "interact", "capture"]
CollectionModeHint = Literal["light", "heavy", "auto"]
AdapterResultStatus = Literal["succeeded", "partial", "blocked", "failed"]
WritebackScopeType = Literal["work_context", "industry", "assignment", "task", "report"]


class ResearchWritebackTarget(BaseModel):
    scope_type: WritebackScopeType
    scope_id: str


class ResearchBrief(BaseModel):
    owner_agent_id: str
    supervisor_agent_id: str | None = None
    industry_instance_id: str | None = None
    work_context_id: str | None = None
    assignment_id: str | None = None
    task_id: str | None = None
    goal: str
    question: str
    why_needed: str
    done_when: str
    writeback_target: ResearchWritebackTarget | None = None
    urgency: str = "normal"
    collection_mode_hint: CollectionModeHint = "auto"
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollectedSource(BaseModel):
    source_id: str
    source_kind: str
    collection_action: CollectionAction
    source_ref: str
    normalized_ref: str = ""
    title: str = ""
    snippet: str = ""
    access_status: str = ""
    evidence_id: str | None = None
    artifact_id: str | None = None
    captured_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchFinding(BaseModel):
    finding_id: str
    finding_type: str
    summary: str
    supporting_source_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class ResearchAdapterResult(BaseModel):
    adapter_kind: str
    collection_action: CollectionAction
    status: AdapterResultStatus
    session_id: str | None = None
    round_id: str | None = None
    collected_sources: list[CollectedSource] = Field(default_factory=list)
    findings: list[ResearchFinding] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "AdapterResultStatus",
    "CollectedSource",
    "CollectionAction",
    "CollectionModeHint",
    "ResearchAdapterResult",
    "ResearchBrief",
    "ResearchFinding",
    "ResearchWritebackTarget",
    "WritebackScopeType",
]
