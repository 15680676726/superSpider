# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


MediaSourceKind = Literal["link", "upload", "existing-artifact"]
MediaType = Literal["unknown", "article", "video", "audio", "document"]
AnalysisMode = Literal["standard", "video-lite", "video-deep"]
MediaEntryPoint = Literal[
    "industry-preview",
    "industry-bootstrap",
    "chat",
    "runtime-center",
]
MediaPurpose = Literal[
    "draft-enrichment",
    "chat-answer",
    "learn-and-writeback",
    "reference-only",
]


def _new_source_id() -> str:
    return f"media-src:{uuid4().hex}"


def _normalize_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_text_list(value: object) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = _normalize_text(item)
        if text is None or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


class MediaCapabilityState(BaseModel):
    video_deep_available: bool = False
    native_video_enabled: bool = False
    native_audio_enabled: bool = False
    local_asr_enabled: bool = False
    supported_video_modes: list[AnalysisMode] = Field(default_factory=lambda: ["video-lite"])


class MediaSourceSpec(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source_id: str = Field(default_factory=_new_source_id)
    source_kind: MediaSourceKind
    media_type: MediaType = "unknown"
    declared_media_type: MediaType | None = None
    detected_media_type: MediaType | None = None
    analysis_mode: AnalysisMode | None = None
    title: str | None = None
    url: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    artifact_id: str | None = None
    storage_uri: str | None = None
    upload_base64: str | None = None
    entry_point: MediaEntryPoint = "chat"
    purpose: MediaPurpose = "reference-only"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "title",
        "url",
        "filename",
        "mime_type",
        "artifact_id",
        "storage_uri",
        mode="before",
    )
    @classmethod
    def _normalize_optional_text(cls, value: object | None) -> str | None:
        return _normalize_text(value)


class MediaResolveLinkRequest(BaseModel):
    url: str = Field(..., min_length=1)
    entry_point: MediaEntryPoint = "chat"
    purpose: MediaPurpose = "reference-only"


class MediaResolveLinkResponse(BaseModel):
    url: str
    normalized_url: str
    detected_media_type: MediaType = "unknown"
    mime_type: str | None = None
    title: str | None = None
    filename: str | None = None
    size_bytes: int | None = None
    analysis_mode_options: list[AnalysisMode] = Field(default_factory=list)
    resolved_source: MediaSourceSpec
    warnings: list[str] = Field(default_factory=list)
    capabilities: MediaCapabilityState = Field(default_factory=MediaCapabilityState)

    @field_validator("warnings", mode="before")
    @classmethod
    def _normalize_warning_list(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class MediaIngestRequest(BaseModel):
    source: MediaSourceSpec


class MediaIngestResponse(BaseModel):
    source: MediaSourceSpec
    detected_media_type: MediaType = "unknown"
    analysis_mode_options: list[AnalysisMode] = Field(default_factory=list)
    asset_artifact_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    capabilities: MediaCapabilityState = Field(default_factory=MediaCapabilityState)

    @field_validator("asset_artifact_ids", "evidence_ids", "warnings", mode="before")
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class MediaAnalysisSummary(BaseModel):
    analysis_id: str
    industry_instance_id: str | None = None
    thread_id: str | None = None
    work_context_id: str | None = None
    entry_point: str
    purpose: str
    source_kind: str
    source_ref: str | None = None
    detected_media_type: MediaType | str = "unknown"
    analysis_mode: AnalysisMode | str = "standard"
    status: str = "queued"
    title: str = ""
    url: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    asset_artifact_ids: list[str] = Field(default_factory=list)
    derived_artifact_ids: list[str] = Field(default_factory=list)
    transcript_artifact_id: str | None = None
    knowledge_document_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    strategy_writeback_status: str | None = None
    backlog_writeback_status: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator(
        "key_points",
        "entities",
        "claims",
        "recommended_actions",
        "warnings",
        "asset_artifact_ids",
        "derived_artifact_ids",
        "knowledge_document_ids",
        "evidence_ids",
        mode="before",
    )
    @classmethod
    def _normalize_summary_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class MediaAnalysisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sources: list[MediaSourceSpec] = Field(default_factory=list)
    industry_instance_id: str | None = None
    thread_id: str | None = None
    work_context_id: str | None = None
    entry_point: MediaEntryPoint = "chat"
    purpose: MediaPurpose = "reference-only"
    writeback: bool = False


class MediaAnalysisResponse(BaseModel):
    analyses: list[MediaAnalysisSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    capabilities: MediaCapabilityState = Field(default_factory=MediaCapabilityState)

    @field_validator("warnings", mode="before")
    @classmethod
    def _normalize_response_warnings(cls, value: object) -> list[str]:
        return _normalize_text_list(value)
