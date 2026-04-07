# -*- coding: utf-8 -*-
"""Industry and media state records."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from .model_support import UpdatedRecord, _new_record_id, _normalize_text_list


class IndustryInstanceRecord(UpdatedRecord):
    """Formal persisted industry instance truth source."""

    instance_id: str = Field(..., min_length=1)
    bootstrap_kind: Literal["industry-v1"] = "industry-v1"
    label: str = Field(..., min_length=1)
    summary: str = ""
    owner_scope: str = Field(..., min_length=1)
    status: str = "draft"
    profile_payload: dict[str, Any] = Field(default_factory=dict)
    team_payload: dict[str, Any] = Field(default_factory=dict)
    draft_payload: dict[str, Any] = Field(default_factory=dict)
    execution_core_identity_payload: dict[str, Any] = Field(default_factory=dict)
    agent_ids: list[str] = Field(default_factory=list)
    lifecycle_status: str = "running"
    autonomy_status: str = "waiting-confirm"
    current_cycle_id: str | None = None
    next_cycle_due_at: datetime | None = None
    last_cycle_started_at: datetime | None = None


class MediaAnalysisRecord(UpdatedRecord):
    """Formal persisted media analysis anchored in unified state."""

    analysis_id: str = Field(default_factory=_new_record_id, min_length=1)
    industry_instance_id: str | None = None
    thread_id: str | None = None
    work_context_id: str | None = None
    entry_point: str = Field(default="chat", min_length=1)
    purpose: str = Field(default="reference-only", min_length=1)
    source_kind: str = Field(default="upload", min_length=1)
    source_ref: str | None = None
    source_hash: str | None = None
    declared_media_type: str | None = None
    detected_media_type: str = Field(default="unknown", min_length=1)
    analysis_mode: str = Field(default="standard", min_length=1)
    status: str = Field(default="queued", min_length=1)
    title: str = ""
    url: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    asset_artifact_ids: list[str] = Field(default_factory=list)
    derived_artifact_ids: list[str] = Field(default_factory=list)
    transcript_artifact_id: str | None = None
    structured_summary: dict[str, Any] = Field(default_factory=dict)
    timeline_summary: list[dict[str, Any]] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    knowledge_document_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    strategy_writeback_status: str | None = None
    backlog_writeback_status: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "asset_artifact_ids",
        "derived_artifact_ids",
        "entities",
        "claims",
        "recommended_actions",
        "warnings",
        "knowledge_document_ids",
        "evidence_ids",
        mode="before",
    )
    @classmethod
    def _normalize_media_list_fields(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


__all__ = [
    "IndustryInstanceRecord",
    "MediaAnalysisRecord",
]
