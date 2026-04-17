# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .model_support import UpdatedRecord, _new_record_id, _normalize_text_list

ResearchSessionStatus = Literal[
    "queued",
    "running",
    "waiting-login",
    "deepening",
    "summarizing",
    "completed",
    "failed",
    "cancelled",
]

ResearchRoundDecision = Literal["continue", "stop", "login_required", "failed"]
_RESEARCH_METADATA_KEY = "__copaw_research"


def _normalize_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    return {}


def _normalize_mapping_list(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    normalized: list[dict[str, Any]] = []
    for item in items:
        mapping = _normalize_mapping(item)
        if mapping:
            normalized.append(mapping)
    return normalized


def _extract_research_metadata(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata = _normalize_mapping(payload.get("metadata"))
    reserved = _normalize_mapping(metadata.get(_RESEARCH_METADATA_KEY))
    public_metadata = dict(metadata)
    public_metadata.pop(_RESEARCH_METADATA_KEY, None)
    return public_metadata, reserved


class ResearchSessionRecord(UpdatedRecord):
    id: str = Field(default_factory=_new_record_id, min_length=1)
    provider: str = Field(default="baidu-page", min_length=1)
    industry_instance_id: str | None = None
    work_context_id: str | None = None
    owner_agent_id: str = Field(..., min_length=1)
    supervisor_agent_id: str | None = None
    trigger_source: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)
    status: ResearchSessionStatus = "queued"
    browser_session_id: str | None = None
    round_count: int = Field(default=0, ge=0)
    link_depth_count: int = Field(default=0, ge=0)
    download_count: int = Field(default=0, ge=0)
    stable_findings: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    brief: dict[str, Any] = Field(default_factory=dict)
    final_report_id: str | None = None
    failure_class: str | None = None
    failure_summary: str | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _hydrate_brief_from_metadata(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        metadata, reserved = _extract_research_metadata(payload)
        payload["metadata"] = metadata
        if payload.get("brief") is None:
            payload["brief"] = (
                reserved.get("brief")
                or metadata.get("research_brief")
                or metadata.get("brief")
                or {}
            )
        return payload

    @field_validator("stable_findings", "open_questions", mode="before")
    @classmethod
    def _normalize_text_fields(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    @field_validator("brief", mode="before")
    @classmethod
    def _normalize_brief(cls, value: object) -> dict[str, Any]:
        return _normalize_mapping(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def _normalize_metadata(cls, value: object) -> dict[str, Any]:
        return _normalize_mapping(value)


class ResearchSessionRoundRecord(UpdatedRecord):
    id: str = Field(default_factory=_new_record_id, min_length=1)
    session_id: str = Field(..., min_length=1)
    round_index: int = Field(..., ge=1)
    question: str = Field(..., min_length=1)
    generated_prompt: str | None = None
    response_excerpt: str | None = None
    response_summary: str | None = None
    raw_links: list[dict[str, Any]] = Field(default_factory=list)
    selected_links: list[dict[str, Any]] = Field(default_factory=list)
    downloaded_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    new_findings: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    remaining_gaps: list[str] = Field(default_factory=list)
    decision: ResearchRoundDecision = "continue"
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _hydrate_sources_from_metadata(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        metadata, reserved = _extract_research_metadata(payload)
        payload["metadata"] = metadata
        if payload.get("sources") is None:
            payload["sources"] = (
                reserved.get("sources")
                or metadata.get("collected_sources")
                or metadata.get("research_sources")
                or metadata.get("sources")
                or []
            )
        return payload

    @field_validator("new_findings", "remaining_gaps", "evidence_ids", mode="before")
    @classmethod
    def _normalize_text_list_fields(cls, value: object) -> list[str]:
        return _normalize_text_list(value)

    @field_validator(
        "raw_links",
        "selected_links",
        "downloaded_artifacts",
        "sources",
        mode="before",
    )
    @classmethod
    def _normalize_mapping_list_fields(cls, value: object) -> list[dict[str, Any]]:
        return _normalize_mapping_list(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def _normalize_metadata(cls, value: object) -> dict[str, Any]:
        return _normalize_mapping(value)


__all__ = [
    "ResearchRoundDecision",
    "ResearchSessionRecord",
    "ResearchSessionRoundRecord",
    "ResearchSessionStatus",
]
