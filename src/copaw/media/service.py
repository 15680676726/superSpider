# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import binascii
import html
import json
import mimetypes
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Iterable, Sequence
from xml.etree import ElementTree

from pydantic import BaseModel, Field

from ..constant import WORKING_DIR
from ..evidence import ArtifactRecord, EvidenceLedger, EvidenceRecord
from ..state import MediaAnalysisRecord, StrategyMemoryRecord
from ..state.repositories.base import BaseMediaAnalysisRepository
from ..state.strategy_memory_service import resolve_strategy_payload
from .models import (
    AnalysisMode,
    MediaAnalysisRequest,
    MediaAnalysisResponse,
    MediaAnalysisSummary,
    MediaCapabilityState,
    MediaIngestRequest,
    MediaIngestResponse,
    MediaResolveLinkRequest,
    MediaResolveLinkResponse,
    MediaSourceSpec,
)

_TRUE_VALUES = {"1", "true", "yes", "on"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".mkv", ".m4v"}
_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac"}
_DOCUMENT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".html",
    ".htm",
    ".xml",
    ".yml",
    ".yaml",
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".rtf",
}
_OFFICE_EXTENSIONS = {".docx", ".pptx", ".xlsx"}
_VIDEO_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "vimeo.com",
    "www.vimeo.com",
    "bilibili.com",
    "www.bilibili.com",
    "tiktok.com",
    "www.tiktok.com",
}
_AUDIO_DOMAINS = {
    "soundcloud.com",
    "www.soundcloud.com",
    "spotify.com",
    "www.spotify.com",
    "podcasts.apple.com",
    "music.163.com",
}
_TEXT_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+|\n{2,}")
_HTML_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(*parts: Iterable[object] | None) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for values in parts:
        for value in values or ():
            text = _string(value)
            if text is None:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            items.append(text)
    return items


def _truthy_env(name: str) -> bool:
    return str(os.environ.get(name, "") or "").strip().lower() in _TRUE_VALUES


def _media_storage_dir(*parts: str) -> Path:
    preferred_root = WORKING_DIR / "state" / "media"
    fallback_root = Path(tempfile.gettempdir()) / "copaw" / "state" / "media"
    for root in (preferred_root, fallback_root):
        target = root.joinpath(*parts)
        try:
            target.mkdir(parents=True, exist_ok=True)
            return target
        except OSError:
            continue
    target = fallback_root.joinpath(*parts)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _safe_name(value: str | None, *, fallback: str) -> str:
    raw = _string(value) or fallback
    safe = re.sub(r"[^\w.\-]+", "_", raw)
    return safe[:160] or fallback


def _truncate(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "..."


def _decode_bytes(data: bytes, *, default: str = "utf-8") -> str:
    for encoding in (default, "utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode(default, errors="ignore")


def _decode_base64_media_bytes(value: str) -> tuple[bytes, str | None]:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Upload base64 payload is empty")
    mime_type: str | None = None
    if raw.startswith("data:") and ";base64," in raw:
        header, encoded = raw.split(",", 1)
        mime_type = _string(header[5:].split(";", 1)[0])
    else:
        encoded = raw
    padding = len(encoded) % 4
    if padding:
        encoded = encoded + ("=" * (4 - padding))
    try:
        return base64.b64decode(encoded, validate=False), mime_type
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid upload base64 payload") from exc


def _url_filename(url: str | None) -> str | None:
    parsed = urllib.parse.urlparse(url or "")
    filename = Path(parsed.path).name
    return _string(filename)


def _summary_from_digest(digest: "_MediaDigest") -> dict[str, Any]:
    return {
        "summary": digest.summary,
        "key_points": list(digest.key_points),
        "entities": list(digest.entities),
        "claims": list(digest.claims),
        "recommended_actions": list(digest.recommended_actions),
    }


class _MediaDigest(BaseModel):
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class _MediaWritebackDecision(BaseModel):
    should_writeback: bool = False
    backlog_title: str | None = None
    backlog_summary: str | None = None
    strategy_focuses: list[str] = Field(default_factory=list)


class MediaService:
    def __init__(
        self,
        *,
        repository: BaseMediaAnalysisRepository,
        evidence_ledger: EvidenceLedger,
        knowledge_service: object | None = None,
        strategy_memory_service: object | None = None,
        backlog_service: object | None = None,
        operating_lane_service: object | None = None,
        industry_instance_repository: object | None = None,
        memory_retain_service: object | None = None,
    ) -> None:
        self._repository = repository
        self._evidence_ledger = evidence_ledger
        self._knowledge_service = knowledge_service
        self._strategy_memory_service = strategy_memory_service
        self._backlog_service = backlog_service
        self._operating_lane_service = operating_lane_service
        self._industry_instance_repository = industry_instance_repository
        self._memory_retain_service = memory_retain_service

    def capabilities(self) -> MediaCapabilityState:
        native_video_enabled = _truthy_env("COPAW_MEDIA_ENABLE_NATIVE_VIDEO")
        native_audio_enabled = _truthy_env("COPAW_MEDIA_ENABLE_NATIVE_AUDIO")
        local_asr_enabled = _truthy_env("COPAW_MEDIA_ENABLE_LOCAL_ASR")
        return MediaCapabilityState(
            video_deep_available=False,
            native_video_enabled=native_video_enabled,
            native_audio_enabled=native_audio_enabled,
            local_asr_enabled=local_asr_enabled,
            supported_video_modes=["video-lite"],
        )

    def resolve_link(self, request: MediaResolveLinkRequest) -> MediaResolveLinkResponse:
        normalized_url = self._normalize_url(request.url)
        preview = self._fetch_link_preview(normalized_url)
        detected_media_type = self._detect_media_type(
            filename=_string(preview.get("filename")),
            mime_type=_string(preview.get("mime_type")),
            url=_string(preview.get("final_url")) or normalized_url,
            html_text=_string(preview.get("html_text")),
        )
        capabilities = self.capabilities()
        source = MediaSourceSpec(
            source_kind="link",
            media_type=detected_media_type,
            declared_media_type="unknown",
            detected_media_type=detected_media_type,
            analysis_mode="video-lite" if detected_media_type == "video" else "standard",
            title=_string(preview.get("title")),
            url=_string(preview.get("final_url")) or normalized_url,
            filename=_string(preview.get("filename")),
            mime_type=_string(preview.get("mime_type")),
            size_bytes=preview.get("size_bytes"),
            entry_point=request.entry_point,
            purpose=request.purpose,
            metadata={
                "preview_text": _string(preview.get("preview_text")),
                "final_url": _string(preview.get("final_url")) or normalized_url,
            },
        )
        warnings = _string_list(
            self._source_warnings(source, capabilities=capabilities),
            [preview.get("warning")] if preview.get("warning") else [],
        )
        return MediaResolveLinkResponse(
            url=request.url,
            normalized_url=normalized_url,
            detected_media_type=detected_media_type,
            mime_type=source.mime_type,
            title=source.title,
            filename=source.filename,
            size_bytes=source.size_bytes,
            analysis_mode_options=self._analysis_modes(
                source.detected_media_type,
                capabilities=capabilities,
            ),
            resolved_source=source,
            warnings=warnings,
            capabilities=capabilities,
        )

    def ingest(
        self,
        request: MediaIngestRequest,
        *,
        file_bytes: bytes | None = None,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> MediaIngestResponse:
        source = request.source
        capabilities = self.capabilities()
        if source.source_kind == "link":
            resolved = self.resolve_link(
                MediaResolveLinkRequest(
                    url=source.url or "",
                    entry_point=source.entry_point,
                    purpose=source.purpose,
                ),
            )
            return MediaIngestResponse(
                source=resolved.resolved_source,
                detected_media_type=resolved.detected_media_type,
                analysis_mode_options=resolved.analysis_mode_options,
                warnings=resolved.warnings,
                capabilities=capabilities,
            )

        if file_bytes is None and source.upload_base64:
            decoded_bytes, decoded_mime = _decode_base64_media_bytes(source.upload_base64)
            return self.ingest(
                MediaIngestRequest(
                    source=source.model_copy(update={"upload_base64": None})
                ),
                file_bytes=decoded_bytes,
                filename=source.filename,
                mime_type=_string(source.mime_type) or decoded_mime,
            )

        if file_bytes is None and source.storage_uri:
            detected_filename = _string(source.filename) or Path(source.storage_uri).name
            detected_mime = (
                _string(source.mime_type)
                or mimetypes.guess_type(detected_filename or "upload.bin")[0]
            )
            detected_media_type = self._detect_media_type(
                filename=detected_filename,
                mime_type=detected_mime,
            )
            resolved_source = source.model_copy(
                update={
                    "filename": detected_filename,
                    "mime_type": detected_mime,
                    "detected_media_type": detected_media_type,
                    "media_type": detected_media_type,
                    "analysis_mode": (
                        "video-lite" if detected_media_type == "video" else "standard"
                    ),
                }
            )
            return MediaIngestResponse(
                source=resolved_source,
                detected_media_type=detected_media_type,
                analysis_mode_options=self._analysis_modes(
                    detected_media_type,
                    capabilities=capabilities,
                ),
                asset_artifact_ids=[resolved_source.artifact_id]
                if resolved_source.artifact_id
                else [],
                warnings=self._source_warnings(
                    resolved_source,
                    capabilities=capabilities,
                ),
                capabilities=capabilities,
            )

        if file_bytes is None:
            raise ValueError("Upload ingest requires file bytes")

        detected_filename = _string(filename) or source.filename or "upload.bin"
        detected_mime = (
            _string(mime_type)
            or source.mime_type
            or mimetypes.guess_type(detected_filename)[0]
        )
        detected_media_type = self._detect_media_type(
            filename=detected_filename,
            mime_type=detected_mime,
        )
        storage_dir = _media_storage_dir(
            "sources",
            _safe_name(source.source_id, fallback="source"),
        )
        storage_path = storage_dir / _safe_name(
            detected_filename,
            fallback="upload.bin",
        )
        storage_path.write_bytes(file_bytes)
        file_sha1 = sha1(file_bytes).hexdigest()
        evidence = self._append_evidence(
            task_id=f"media-ingest:{source.source_id}",
            action_summary=f"Ingested media upload {detected_filename}",
            result_summary=f"Stored upload as {detected_media_type}",
            metadata={"source_id": source.source_id, "media_type": detected_media_type},
            artifacts=[
                ArtifactRecord(
                    artifact_type="media-source",
                    storage_uri=str(storage_path),
                    summary=f"Uploaded source file {detected_filename}",
                    metadata={"file_sha1": file_sha1, "mime_type": detected_mime},
                )
            ],
        )
        artifact_id = evidence.artifacts[0].id if evidence.artifacts else None
        resolved_source = source.model_copy(
            update={
                "filename": detected_filename,
                "mime_type": detected_mime,
                "size_bytes": len(file_bytes),
                "storage_uri": str(storage_path),
                "artifact_id": artifact_id,
                "media_type": detected_media_type,
                "detected_media_type": detected_media_type,
                "analysis_mode": (
                    "video-lite" if detected_media_type == "video" else "standard"
                ),
                "metadata": {**dict(source.metadata or {}), "file_sha1": file_sha1},
            }
        )
        return MediaIngestResponse(
            source=resolved_source,
            detected_media_type=detected_media_type,
            analysis_mode_options=self._analysis_modes(
                detected_media_type,
                capabilities=capabilities,
            ),
            asset_artifact_ids=[artifact_id] if artifact_id else [],
            evidence_ids=[evidence.id],
            warnings=self._source_warnings(
                resolved_source,
                capabilities=capabilities,
            ),
            capabilities=capabilities,
        )

    async def analyze(self, request: MediaAnalysisRequest) -> MediaAnalysisResponse:
        capabilities = self.capabilities()
        analyses: list[MediaAnalysisSummary] = []
        warnings: list[str] = []
        for source in request.sources:
            try:
                summary, item_warnings = await self._analyze_one(
                    source=source,
                    industry_instance_id=request.industry_instance_id,
                    thread_id=request.thread_id,
                    work_context_id=request.work_context_id,
                    entry_point=request.entry_point,
                    purpose=request.purpose,
                    writeback=request.writeback,
                    capabilities=capabilities,
                )
                analyses.append(summary)
                warnings.extend(item_warnings)
            except Exception as exc:
                analyses.append(
                    MediaAnalysisSummary(
                        analysis_id=f"media-error:{source.source_id}",
                        industry_instance_id=request.industry_instance_id,
                        thread_id=request.thread_id,
                        work_context_id=request.work_context_id,
                        entry_point=request.entry_point,
                        purpose=request.purpose,
                        source_kind=source.source_kind,
                        source_ref=source.url or source.storage_uri or source.artifact_id,
                        detected_media_type=source.detected_media_type or source.media_type,
                        analysis_mode=source.analysis_mode or "standard",
                        status="failed",
                        title=source.title or source.filename or source.url or source.source_id,
                        url=source.url,
                        filename=source.filename,
                        mime_type=source.mime_type,
                        size_bytes=source.size_bytes,
                        warnings=[str(exc)],
                        error_message=str(exc),
                    )
                )
                warnings.append(str(exc))
        return MediaAnalysisResponse(
            analyses=analyses,
            warnings=_string_list(warnings),
            capabilities=capabilities,
        )

    def get_analysis(self, analysis_id: str) -> MediaAnalysisSummary | None:
        record = self._repository.get_analysis(analysis_id)
        return None if record is None else self._summary_from_record(record)

    def list_analyses(
        self,
        *,
        industry_instance_id: str | None = None,
        thread_id: str | None = None,
        work_context_id: str | None = None,
        entry_point: str | None = None,
        status: str | None = None,
        limit: int | None = 50,
    ) -> list[MediaAnalysisSummary]:
        return [
            self._summary_from_record(record)
            for record in self._repository.list_analyses(
                industry_instance_id=industry_instance_id,
                thread_id=thread_id,
                work_context_id=work_context_id,
                entry_point=entry_point,
                status=status,
                limit=limit,
            )
        ]

    def build_prompt_context(
        self,
        analysis_ids: Sequence[str],
        *,
        limit_chars: int = 10000,
    ) -> str:
        blocks = [
            "Attached analyzed materials are available below.",
            "Use them as canonical reference context for this turn.",
        ]
        used = sum(len(item) for item in blocks)
        for index, analysis_id in enumerate(analysis_ids, start=1):
            record = self._repository.get_analysis(str(analysis_id).strip())
            if record is None or record.status != "completed":
                continue
            summary = _string(record.structured_summary.get("summary")) or ""
            key_points = _string_list(record.structured_summary.get("key_points"))
            block = "\n".join(
                [
                    f"[Material {index}] {record.title or record.filename or record.url or record.analysis_id}",
                    f"Type: {record.detected_media_type}; Mode: {record.analysis_mode}",
                    f"Summary: {summary}",
                    *[f"- {item}" for item in key_points[:6]],
                ]
            )
            if used + len(block) > limit_chars:
                break
            blocks.extend(["", block])
            used += len(block)
        return "\n".join(blocks).strip()

    async def adopt_analyses_for_industry(
        self,
        *,
        industry_instance_id: str,
        analysis_ids: Sequence[str],
        thread_id: str | None = None,
        work_context_id: str | None = None,
    ) -> list[MediaAnalysisSummary]:
        adopted: list[MediaAnalysisSummary] = []
        for analysis_id in analysis_ids:
            record = self._repository.get_analysis(str(analysis_id).strip())
            if record is None or record.status != "completed":
                continue
            updated = record.model_copy(
                update={
                    "industry_instance_id": industry_instance_id,
                    "thread_id": thread_id or record.thread_id,
                    "work_context_id": work_context_id or record.work_context_id,
                    "updated_at": _utc_now(),
                }
            )
            updated = await self._apply_industry_writeback(
                updated,
                industry_instance_id=industry_instance_id,
            )
            self._repository.upsert_analysis(updated)
            adopted.append(self._summary_from_record(updated))
        return adopted

    async def _analyze_one(
        self,
        *,
        source: MediaSourceSpec,
        industry_instance_id: str | None,
        thread_id: str | None,
        work_context_id: str | None,
        entry_point: str,
        purpose: str,
        writeback: bool,
        capabilities: MediaCapabilityState,
    ) -> tuple[MediaAnalysisSummary, list[str]]:
        ingested = self.ingest(MediaIngestRequest(source=source))
        prepared = ingested.source.model_copy(
            update={"entry_point": entry_point, "purpose": purpose}
        )
        warnings = _string_list(
            ingested.warnings,
            self._source_warnings(prepared, capabilities=capabilities),
        )
        if prepared.analysis_mode == "video-deep":
            prepared = prepared.model_copy(update={"analysis_mode": "video-lite"})
            warnings.append("Deep video analysis is not available; falling back to video-lite.")

        source_ref = (
            _string(prepared.url)
            or _string(prepared.artifact_id)
            or _string(prepared.storage_uri)
        )
        source_hash = _string((prepared.metadata or {}).get("file_sha1"))
        existing_match: MediaAnalysisRecord | None = None
        for existing in self._repository.list_analyses(limit=None):
            if existing.analysis_mode != prepared.analysis_mode:
                continue
            if (
                work_context_id
                and existing.work_context_id
                and existing.work_context_id != work_context_id
            ):
                continue
            if source_hash and existing.source_hash == source_hash:
                existing_match = existing
                break
            if source_ref and existing.source_ref == source_ref:
                existing_match = existing
                break
        if existing_match is not None:
            updates: dict[str, Any] = {}
            rebind_industry = False
            if industry_instance_id and existing_match.industry_instance_id != industry_instance_id:
                updates["industry_instance_id"] = industry_instance_id
                rebind_industry = True
            if thread_id and existing_match.thread_id != thread_id:
                updates["thread_id"] = thread_id
            if work_context_id and existing_match.work_context_id != work_context_id:
                updates["work_context_id"] = work_context_id
            if updates:
                existing_match = existing_match.model_copy(
                    update={
                        **updates,
                        "updated_at": _utc_now(),
                    },
                )
            if rebind_industry:
                existing_match = await self._apply_industry_writeback(
                    existing_match,
                    industry_instance_id=industry_instance_id,
                )
            if updates or rebind_industry:
                self._repository.upsert_analysis(existing_match)
            return self._summary_from_record(existing_match), warnings

        extracted_text, extracted_title = self._extract_text(prepared)
        digest = self._build_digest(
            source=prepared,
            extracted_text=extracted_text,
            title=extracted_title or prepared.title,
        )
        structured_summary = _summary_from_digest(digest)
        timeline_summary = self._timeline_summary(
            extracted_text=extracted_text,
            detected_media_type=prepared.detected_media_type or "unknown",
        )
        analysis_id = f"media-analysis:{prepared.source_id}"
        derived_artifacts = self._write_analysis_artifacts(
            analysis_id=analysis_id,
            source=prepared,
            digest=digest,
            extracted_text=extracted_text,
        )
        evidence = self._append_evidence(
            task_id=f"media-analyze:{prepared.source_id}",
            action_summary=f"Analyzed media source {prepared.title or prepared.filename or prepared.url or prepared.source_id}",
            result_summary=digest.summary or "Media analysis completed",
            metadata={
                "analysis_id": analysis_id,
                "source_id": prepared.source_id,
                "detected_media_type": prepared.detected_media_type,
                "analysis_mode": prepared.analysis_mode,
            },
            artifacts=derived_artifacts,
        )
        derived_artifact_ids = [
            artifact.id
            for artifact in evidence.artifacts
            if artifact.artifact_type == "media-derived"
        ]
        transcript_artifact_id = next(
            (
                artifact.id
                for artifact in evidence.artifacts
                if artifact.metadata.get("derived_kind") == "transcript"
            ),
            None,
        )
        record = MediaAnalysisRecord(
            analysis_id=analysis_id,
            industry_instance_id=industry_instance_id,
            thread_id=thread_id,
            work_context_id=work_context_id,
            entry_point=entry_point,
            purpose=purpose,
            source_kind=prepared.source_kind,
            source_ref=source_ref,
            source_hash=source_hash,
            declared_media_type=prepared.declared_media_type,
            detected_media_type=prepared.detected_media_type or prepared.media_type,
            analysis_mode=prepared.analysis_mode or "standard",
            status="completed",
            title=prepared.title or extracted_title or prepared.filename or prepared.url or prepared.source_id,
            url=prepared.url,
            filename=prepared.filename,
            mime_type=prepared.mime_type,
            size_bytes=prepared.size_bytes,
            asset_artifact_ids=_string_list(
                ingested.asset_artifact_ids,
                [prepared.artifact_id] if prepared.artifact_id else [],
            ),
            derived_artifact_ids=derived_artifact_ids,
            transcript_artifact_id=transcript_artifact_id,
            structured_summary=structured_summary,
            timeline_summary=timeline_summary,
            entities=list(digest.entities),
            claims=list(digest.claims),
            recommended_actions=list(digest.recommended_actions),
            warnings=warnings,
            evidence_ids=_string_list(ingested.evidence_ids, [evidence.id]),
            metadata={
                "source_id": prepared.source_id,
                "storage_uri": prepared.storage_uri,
                "preview_text": _string((prepared.metadata or {}).get("preview_text")),
            },
        )
        record = record.model_copy(
            update={
                "knowledge_document_ids": self._write_knowledge(
                    record,
                    extracted_text=extracted_text,
                ),
            }
        )
        if writeback and industry_instance_id:
            record = await self._apply_industry_writeback(
                record,
                industry_instance_id=industry_instance_id,
            )
        else:
            record = record.model_copy(
                update={
                    "strategy_writeback_status": record.strategy_writeback_status or "pending",
                    "backlog_writeback_status": record.backlog_writeback_status or "pending",
                }
            )
        self._repository.upsert_analysis(record)
        return self._summary_from_record(record), warnings

    def _extract_text(self, source: MediaSourceSpec) -> tuple[str, str | None]:
        preview_text = _string((source.metadata or {}).get("preview_text"))
        if source.source_kind == "link":
            preview = self._fetch_link_preview(source.url or "")
            title = _string(preview.get("title")) or source.title
            if source.detected_media_type == "article":
                text = _string(preview.get("html_text")) or preview_text or ""
                return text, title
            return preview_text or _string(preview.get("html_text")) or "", title

        storage_uri = _string(source.storage_uri)
        if not storage_uri:
            return preview_text or "", source.title
        path = Path(storage_uri)
        if not path.exists():
            return preview_text or "", source.title

        suffix = path.suffix.lower()
        if suffix in {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".xml", ".yml", ".yaml"}:
            text = _decode_bytes(path.read_bytes())
            return text, source.title or path.stem
        if suffix in {".html", ".htm"}:
            return self._html_text(_decode_bytes(path.read_bytes())), source.title or path.stem
        if suffix == ".rtf":
            text = _decode_bytes(path.read_bytes())
            text = re.sub(r"\\[a-z]+\d* ?", " ", text)
            text = text.replace("{", " ").replace("}", " ")
            return " ".join(text.split()), source.title or path.stem
        if suffix == ".pdf":
            return self._extract_pdf_text(path), source.title or path.stem
        if suffix in _OFFICE_EXTENSIONS:
            return self._extract_office_text(path), source.title or path.stem
        return preview_text or "", source.title or path.stem

    def _build_digest(
        self,
        *,
        source: MediaSourceSpec,
        extracted_text: str,
        title: str | None,
    ) -> _MediaDigest:
        effective_title = (
            _string(title)
            or _string(source.title)
            or _string(source.filename)
            or _string(source.url)
            or source.source_id
        )
        fragments = self._split_fragments(extracted_text)
        if not fragments:
            fragments = self._split_fragments(
                _string((source.metadata or {}).get("preview_text")) or ""
            )
        if not fragments:
            fragments = self._split_fragments(
                " ".join(
                    part
                    for part in (
                        effective_title,
                        _string(source.filename),
                        _string(source.url),
                    )
                    if part
                )
            )
        summary = _truncate(" ".join(fragments[:2]) or effective_title, 480)
        key_points = fragments[:5]
        entities = _string_list(
            [effective_title],
            [Path(source.filename).stem] if source.filename else [],
            [urllib.parse.urlparse(source.url or "").netloc] if source.url else [],
        )[:6]
        claims = key_points[:3]
        recommended_actions = self._fallback_actions(
            source=source,
            summary=summary,
            key_points=key_points,
        )
        return _MediaDigest(
            summary=summary,
            key_points=key_points,
            entities=entities,
            claims=claims,
            recommended_actions=recommended_actions,
        )

    def _write_knowledge(
        self,
        record: MediaAnalysisRecord,
        *,
        extracted_text: str,
    ) -> list[str]:
        service = self._knowledge_service
        importer = getattr(service, "import_document", None)
        if not callable(importer):
            return []

        title = record.title or record.filename or record.url or record.analysis_id
        summary = _string(record.structured_summary.get("summary")) or ""
        key_points = _string_list(record.structured_summary.get("key_points"))
        recommended_actions = _string_list(record.recommended_actions)
        excerpt = _truncate(extracted_text, 8000) if extracted_text else ""
        content_parts = [
            f"# {title}",
            "",
            "## Summary",
            summary or "No structured summary was extracted.",
        ]
        if key_points:
            content_parts.extend(["", "## Key Points", *[f"- {item}" for item in key_points]])
        if recommended_actions:
            content_parts.extend(
                ["", "## Recommended Actions", *[f"- {item}" for item in recommended_actions]]
            )
        if excerpt:
            content_parts.extend(["", "## Excerpt", excerpt])
        content = "\n".join(content_parts).strip()
        if not content:
            return []
        try:
            imported = importer(
                title=title,
                content=content,
                source_ref=f"media-analysis:{record.analysis_id}",
                tags=_string_list(
                    ["media-analysis", record.detected_media_type, record.analysis_mode]
                ),
            )
        except Exception:
            return []
        document_id = _string(imported.get("document_id")) if isinstance(imported, dict) else None
        return [document_id] if document_id else []

    def _write_analysis_artifacts(
        self,
        *,
        analysis_id: str,
        source: MediaSourceSpec,
        digest: _MediaDigest,
        extracted_text: str,
    ) -> list[ArtifactRecord]:
        analysis_dir = _media_storage_dir(
            "analyses",
            _safe_name(analysis_id, fallback="analysis"),
        )

        json_path = analysis_dir / "analysis.json"
        json_path.write_text(
            json.dumps(
                {
                    "analysis_id": analysis_id,
                    "source": source.model_dump(mode="json"),
                    "digest": digest.model_dump(mode="json"),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        md_lines = [
            f"# {source.title or source.filename or source.url or analysis_id}",
            "",
            f"- Type: {source.detected_media_type or source.media_type}",
            f"- Mode: {source.analysis_mode or 'standard'}",
            "",
            "## Summary",
            digest.summary or "No summary generated.",
        ]
        if digest.key_points:
            md_lines.extend(["", "## Key Points", *[f"- {item}" for item in digest.key_points]])
        if digest.recommended_actions:
            md_lines.extend(
                ["", "## Recommended Actions", *[f"- {item}" for item in digest.recommended_actions]]
            )
        md_path = analysis_dir / "analysis.md"
        md_path.write_text("\n".join(md_lines).strip(), encoding="utf-8")

        artifacts = [
            ArtifactRecord(
                artifact_type="media-derived",
                storage_uri=str(json_path),
                summary="Structured media analysis payload",
                metadata={"derived_kind": "analysis-json"},
            ),
            ArtifactRecord(
                artifact_type="media-derived",
                storage_uri=str(md_path),
                summary="Human-readable media analysis summary",
                metadata={"derived_kind": "analysis-markdown"},
            ),
        ]

        if extracted_text.strip():
            transcript_path = analysis_dir / "extracted.txt"
            transcript_path.write_text(extracted_text, encoding="utf-8")
            artifacts.append(
                ArtifactRecord(
                    artifact_type="media-derived",
                    storage_uri=str(transcript_path),
                    summary="Extracted source text",
                    metadata={"derived_kind": "transcript"},
                )
            )
        return artifacts

    async def _apply_industry_writeback(
        self,
        record: MediaAnalysisRecord,
        *,
        industry_instance_id: str,
    ) -> MediaAnalysisRecord:
        decision = self._writeback_decision(record)
        strategy_status = "skipped"
        backlog_status = "skipped"
        source_ref = f"media-analysis:{record.analysis_id}"
        instance_record = None
        getter = getattr(self._industry_instance_repository, "get_instance", None)
        if callable(getter):
            instance_record = getter(industry_instance_id)

        if decision.should_writeback and self._backlog_service is not None:
            try:
                self._backlog_service.record_generated_item(
                    industry_instance_id=industry_instance_id,
                    lane_id=self._primary_lane_id(industry_instance_id),
                    title=decision.backlog_title or f"Review material: {record.title}",
                    summary=decision.backlog_summary or "",
                    priority=2,
                    source_kind="media-analysis",
                    source_ref=source_ref,
                    metadata={
                        "analysis_id": record.analysis_id,
                        "detected_media_type": record.detected_media_type,
                        "analysis_mode": record.analysis_mode,
                        "knowledge_document_ids": list(record.knowledge_document_ids or []),
                        "evidence_ids": list(record.evidence_ids or []),
                    },
                )
                backlog_status = "written"
            except Exception:
                backlog_status = "failed"
        elif decision.should_writeback:
            backlog_status = "unavailable"

        if decision.should_writeback and self._strategy_memory_service is not None:
            try:
                execution_core_identity = (
                    dict(getattr(instance_record, "execution_core_identity_payload", None) or {})
                    if instance_record is not None
                    else {}
                )
                active_strategy_payload = resolve_strategy_payload(
                    service=self._strategy_memory_service,
                    scope_type="industry",
                    scope_id=industry_instance_id,
                    owner_agent_id=_string(execution_core_identity.get("agent_id")),
                    fallback_owner_agent_ids=[None],
                )
                strategy_title = (
                    _string(getattr(instance_record, "label", None))
                    or f"Industry {industry_instance_id}"
                )
                active_strategy = (
                    StrategyMemoryRecord.model_validate(
                        {
                            **dict(active_strategy_payload or {}),
                            "scope_type": "industry",
                            "scope_id": industry_instance_id,
                            "industry_instance_id": industry_instance_id,
                            "owner_scope": _string(
                                getattr(instance_record, "owner_scope", None),
                            )
                            or _string((active_strategy_payload or {}).get("owner_scope")),
                            "title": _string((active_strategy_payload or {}).get("title"))
                            or strategy_title,
                        }
                    )
                    if active_strategy_payload is not None
                    else None
                )
                if active_strategy is None:
                    active_strategy = StrategyMemoryRecord(
                        scope_type="industry",
                        scope_id=industry_instance_id,
                        industry_instance_id=industry_instance_id,
                        owner_scope=_string(getattr(instance_record, "owner_scope", None)),
                        title=strategy_title,
                        summary=decision.backlog_summary or "",
                        source_ref=source_ref,
                    )
                updated_strategy = active_strategy.model_copy(
                    update={
                        "industry_instance_id": industry_instance_id,
                        "source_ref": source_ref,
                        "summary": (
                            _string(active_strategy.summary)
                            or decision.backlog_summary
                            or _string(record.structured_summary.get("summary"))
                            or ""
                        ),
                        "current_focuses": _string_list(
                            active_strategy.current_focuses,
                            decision.strategy_focuses,
                        )[:12],
                        "metadata": {
                            **dict(active_strategy.metadata or {}),
                            "media_analysis_ids": _string_list(
                                (active_strategy.metadata or {}).get("media_analysis_ids"),
                                [record.analysis_id],
                            ),
                        },
                    }
                )
                self._strategy_memory_service.upsert_strategy(updated_strategy)
                strategy_status = "written"
            except Exception:
                strategy_status = "failed"
        elif decision.should_writeback:
            strategy_status = "unavailable"

        retain = getattr(self._memory_retain_service, "retain_chat_writeback", None)
        if callable(retain):
            try:
                retain(
                    industry_instance_id=industry_instance_id,
                    work_context_id=record.work_context_id,
                    title=record.title or record.analysis_id,
                    content=self.build_prompt_context([record.analysis_id], limit_chars=4000),
                    source_ref=source_ref,
                    tags=["media-analysis", record.detected_media_type],
                )
            except Exception:
                pass

        return record.model_copy(
            update={
                "industry_instance_id": industry_instance_id,
                "strategy_writeback_status": strategy_status,
                "backlog_writeback_status": backlog_status,
                "updated_at": _utc_now(),
            }
        )

    def _writeback_decision(self, record: MediaAnalysisRecord) -> _MediaWritebackDecision:
        summary = _string(record.structured_summary.get("summary")) or ""
        key_points = _string_list(record.structured_summary.get("key_points"))
        recommended_actions = _string_list(record.recommended_actions)
        should_writeback = bool(
            record.industry_instance_id
            and (
                record.purpose in {"draft-enrichment", "learn-and-writeback"}
                or key_points
                or recommended_actions
            )
        )
        backlog_title = (
            recommended_actions[0]
            if recommended_actions
            else f"Review material: {record.title or record.filename or record.analysis_id}"
        )
        backlog_summary = _truncate(
            " ".join(part for part in (summary, " ".join(key_points[:3])) if part),
            360,
        )
        strategy_focuses = _string_list(key_points[:3], recommended_actions[:2])
        return _MediaWritebackDecision(
            should_writeback=should_writeback,
            backlog_title=_truncate(backlog_title, 120),
            backlog_summary=backlog_summary or summary,
            strategy_focuses=strategy_focuses,
        )

    def _append_evidence(
        self,
        *,
        task_id: str,
        action_summary: str,
        result_summary: str,
        metadata: dict[str, Any] | None = None,
        artifacts: Sequence[ArtifactRecord] | None = None,
    ) -> EvidenceRecord:
        return self._evidence_ledger.append(
            EvidenceRecord(
                task_id=task_id,
                actor_ref="media-service",
                risk_level="auto",
                action_summary=action_summary,
                result_summary=result_summary,
                metadata=dict(metadata or {}),
                artifacts=tuple(artifacts or ()),
            )
        )

    def _primary_lane_id(self, industry_instance_id: str) -> str | None:
        service = self._operating_lane_service
        lister = getattr(service, "list_lanes", None)
        if not callable(lister):
            return None
        try:
            lanes = list(
                lister(
                    industry_instance_id=industry_instance_id,
                    status="active",
                    limit=None,
                )
            )
        except Exception:
            return None
        if not lanes:
            return None
        lanes.sort(
            key=lambda item: (
                int(getattr(item, "priority", 0) or 0),
                getattr(item, "updated_at", None)
                or getattr(item, "created_at", None)
                or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )
        return _string(getattr(lanes[0], "id", None))

    def _detect_media_type(
        self,
        *,
        filename: str | None,
        mime_type: str | None,
        url: str | None = None,
        html_text: str | None = None,
    ) -> str:
        suffix = Path(filename or _url_filename(url or "") or "").suffix.lower()
        parsed = urllib.parse.urlparse(url or "")
        host = parsed.netloc.lower()
        mime_lower = (mime_type or "").lower()

        if host in _VIDEO_DOMAINS or suffix in _VIDEO_EXTENSIONS or mime_lower.startswith("video/"):
            return "video"
        if host in _AUDIO_DOMAINS or suffix in _AUDIO_EXTENSIONS or mime_lower.startswith("audio/"):
            return "audio"
        if suffix in _DOCUMENT_EXTENSIONS:
            return "document" if suffix not in {".html", ".htm"} else "article"
        if mime_lower in {"text/html", "application/xhtml+xml"}:
            blob = (html_text or "").lower()
            if any(marker in blob for marker in ("og:video", "videoobject", "<video")):
                return "video"
            if any(marker in blob for marker in ("og:audio", "audioobject", "<audio")):
                return "audio"
            return "article"
        if mime_lower.startswith("text/"):
            return "article"
        if "pdf" in mime_lower or "officedocument" in mime_lower or "msword" in mime_lower:
            return "document"
        return "unknown"

    def _fetch_link_preview(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "CoPawMedia/1.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                final_url = response.geturl()
                mime_type = _string(response.headers.get_content_type()) or _string(
                    response.headers.get("Content-Type")
                )
                size_raw = _string(response.headers.get("Content-Length"))
                try:
                    size_bytes = int(size_raw) if size_raw is not None else None
                except ValueError:
                    size_bytes = None
                disposition = _string(response.headers.get("Content-Disposition")) or ""
                filename = self._content_disposition_filename(disposition) or _url_filename(final_url)
                raw = response.read(65536)
                charset = response.headers.get_content_charset() or "utf-8"
                decoded = _decode_bytes(raw, default=charset)
                html_text = None
                preview_text = None
                title = None
                if mime_type in {"text/html", "application/xhtml+xml"} or "<html" in decoded.lower():
                    html_text = self._html_text(decoded)
                    preview_text = _truncate(html_text, 2000) if html_text else None
                    title = self._html_title(decoded)
                elif decoded.strip():
                    preview_text = _truncate(decoded, 2000)
                return {
                    "final_url": final_url,
                    "mime_type": mime_type,
                    "size_bytes": size_bytes,
                    "filename": filename,
                    "title": title,
                    "preview_text": preview_text,
                    "html_text": html_text,
                }
        except urllib.error.HTTPError as exc:
            return {
                "final_url": url,
                "filename": _url_filename(url),
                "warning": f"Could not preview link ({exc.code}).",
            }
        except urllib.error.URLError as exc:
            return {
                "final_url": url,
                "filename": _url_filename(url),
                "warning": f"Could not preview link ({exc.reason}).",
            }

    def _extract_office_text(self, path: Path) -> str:
        texts: list[str] = []
        try:
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if not name.endswith(".xml"):
                        continue
                    if path.suffix.lower() == ".docx" and not name.startswith("word/"):
                        continue
                    if path.suffix.lower() == ".pptx" and not name.startswith("ppt/"):
                        continue
                    if path.suffix.lower() == ".xlsx" and not name.startswith("xl/"):
                        continue
                    try:
                        root = ElementTree.fromstring(archive.read(name))
                    except Exception:
                        continue
                    for node in root.iter():
                        text = _string(node.text)
                        if text is not None:
                            texts.append(text)
        except Exception:
            return ""
        return _truncate(" ".join(texts), 30000)

    def _extract_pdf_text(self, path: Path) -> str:
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            return _truncate(
                "\n".join(page.extract_text() or "" for page in reader.pages),
                30000,
            )
        except Exception:
            pass
        try:
            from PyPDF2 import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            return _truncate(
                "\n".join(page.extract_text() or "" for page in reader.pages),
                30000,
            )
        except Exception:
            return ""

    def _normalize_url(self, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("Media URL is required")
        parsed = urllib.parse.urlparse(text)
        if not parsed.scheme:
            text = f"https://{text}"
            parsed = urllib.parse.urlparse(text)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only http/https media URLs are supported")
        return text

    def _analysis_modes(
        self,
        media_type: str | None,
        *,
        capabilities: MediaCapabilityState,
    ) -> list[AnalysisMode]:
        if media_type == "video":
            return list(capabilities.supported_video_modes or ["video-lite"])
        return ["standard"]

    def _source_warnings(
        self,
        source: MediaSourceSpec,
        *,
        capabilities: MediaCapabilityState,
    ) -> list[str]:
        detected_type = source.detected_media_type or source.media_type or "unknown"
        warnings: list[str] = []
        if detected_type == "video":
            warnings.append("Current runtime only supports video-lite analysis.")
        if detected_type == "audio" and not (
            capabilities.native_audio_enabled or capabilities.local_asr_enabled
        ):
            warnings.append(
                "Audio transcript is not available in the current runtime; analysis may rely on metadata only."
            )
        if source.source_kind == "link" and detected_type == "unknown":
            warnings.append("The link type could not be determined confidently.")
        return warnings

    def _fallback_actions(
        self,
        *,
        source: MediaSourceSpec,
        summary: str,
        key_points: list[str],
    ) -> list[str]:
        actions: list[str] = []
        if source.purpose in {"draft-enrichment", "learn-and-writeback"}:
            actions.append("Write the material takeaways back into the industry strategy and backlog.")
        if source.purpose == "chat-answer":
            actions.append("Use the analyzed material as supporting context for the current reply.")
        if (source.detected_media_type or source.media_type) in {"video", "audio"}:
            actions.append("Validate any execution-critical spoken details with transcript or manual review.")
        if key_points:
            actions.append(f"Review and operationalize: {_truncate(key_points[0], 120)}")
        elif summary:
            actions.append(f"Review and operationalize: {_truncate(summary, 120)}")
        return _string_list(actions)[:4]

    def _html_title(self, content: str) -> str | None:
        match = _HTML_TITLE_RE.search(content or "")
        if not match:
            return None
        return _string(html.unescape(match.group(1)))

    def _html_text(self, content: str) -> str:
        cleaned = _SCRIPT_STYLE_RE.sub(" ", content or "")
        cleaned = _HTML_TAG_RE.sub(" ", cleaned)
        cleaned = html.unescape(cleaned)
        return _truncate(" ".join(cleaned.split()), 30000)

    def _summary_from_record(self, record: MediaAnalysisRecord) -> MediaAnalysisSummary:
        return MediaAnalysisSummary(
            analysis_id=record.analysis_id,
            industry_instance_id=record.industry_instance_id,
            thread_id=record.thread_id,
            work_context_id=record.work_context_id,
            entry_point=record.entry_point,
            purpose=record.purpose,
            source_kind=record.source_kind,
            source_ref=record.source_ref,
            detected_media_type=record.detected_media_type,
            analysis_mode=record.analysis_mode,
            status=record.status,
            title=record.title,
            url=record.url,
            filename=record.filename,
            mime_type=record.mime_type,
            size_bytes=record.size_bytes,
            summary=_string(record.structured_summary.get("summary")) or "",
            key_points=_string_list(record.structured_summary.get("key_points")),
            entities=list(record.entities or []),
            claims=list(record.claims or []),
            recommended_actions=list(record.recommended_actions or []),
            warnings=list(record.warnings or []),
            asset_artifact_ids=list(record.asset_artifact_ids or []),
            derived_artifact_ids=list(record.derived_artifact_ids or []),
            transcript_artifact_id=record.transcript_artifact_id,
            knowledge_document_ids=list(record.knowledge_document_ids or []),
            evidence_ids=list(record.evidence_ids or []),
            strategy_writeback_status=record.strategy_writeback_status,
            backlog_writeback_status=record.backlog_writeback_status,
            error_message=record.error_message,
            metadata=dict(record.metadata or {}),
            created_at=record.created_at.isoformat() if record.created_at else None,
            updated_at=record.updated_at.isoformat() if record.updated_at else None,
        )

    def _timeline_summary(
        self,
        *,
        extracted_text: str,
        detected_media_type: str,
    ) -> list[dict[str, Any]]:
        if detected_media_type != "video":
            return []
        fragments = self._split_fragments(extracted_text)
        timeline: list[dict[str, Any]] = []
        for index, fragment in enumerate(fragments[:5], start=1):
            timeline.append({"index": index, "label": f"Segment {index}", "summary": fragment})
        return timeline

    def _split_fragments(self, text: str) -> list[str]:
        if not text.strip():
            return []
        raw_items = _TEXT_SPLIT_RE.split(text)
        fragments = [
            _truncate(item.strip(), 240)
            for item in raw_items
            if len(item.strip()) >= 12
        ]
        return _string_list(fragments)

    def _content_disposition_filename(self, disposition: str) -> str | None:
        if not disposition:
            return None
        for pattern in (
            r"filename\\*=UTF-8''([^;]+)",
            r'filename="([^"]+)"',
            r"filename=([^;]+)",
        ):
            match = re.search(pattern, disposition, flags=re.IGNORECASE)
            if not match:
                continue
            value = urllib.parse.unquote(match.group(1).strip())
            return _string(value.strip('"'))
        return None


__all__ = ["MediaService"]
