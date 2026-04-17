# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

from ..contracts import CollectedSource, ResearchAdapterResult, ResearchBrief, ResearchFinding
from ._shared import extract_first_url, extract_first_windows_path, guess_title_from_ref, text


def _resolve_artifact_ref(brief: ResearchBrief, artifact: Mapping[str, object]) -> str:
    explicit = text(artifact.get("path") or artifact.get("source_ref"))
    if explicit:
        return explicit
    local_path = extract_first_windows_path(brief.question, brief.goal)
    if local_path:
        return local_path
    return extract_first_url(brief.question, brief.goal)


def _artifact_metadata(source_ref: str) -> dict[str, object]:
    parsed = urlparse(source_ref)
    if parsed.scheme in {"http", "https"}:
        return {"storage_kind": "remote-url"}
    path = Path(source_ref)
    if path.exists():
        stat = path.stat()
        return {
            "storage_kind": "local-file",
            "size_bytes": stat.st_size,
        }
    return {"storage_kind": "local-reference"}


def collect_artifact(brief: ResearchBrief) -> ResearchAdapterResult:
    payload = brief.metadata.get("artifact")
    artifact = payload if isinstance(payload, Mapping) else {}
    source_ref = _resolve_artifact_ref(brief, artifact)
    if not source_ref:
        return ResearchAdapterResult(
            adapter_kind="artifact",
            collection_action="capture",
            status="partial",
            summary="Artifact adapter is missing an artifact reference.",
            gaps=["artifact reference missing from research brief metadata"],
        )

    metadata = _artifact_metadata(source_ref)
    summary = text(artifact.get("summary") or artifact.get("snippet") or artifact.get("title"))
    if not summary:
        storage_kind = text(metadata.get("storage_kind"))
        if storage_kind == "local-file":
            summary = f"Captured local artifact: {Path(source_ref).name}"
        elif storage_kind == "remote-url":
            summary = f"Captured remote artifact reference: {source_ref}"
    source = CollectedSource(
        source_id="artifact-1",
        source_kind="artifact",
        collection_action="capture",
        source_ref=source_ref,
        normalized_ref=source_ref,
        title=text(artifact.get("title") or guess_title_from_ref(source_ref)),
        snippet=text(artifact.get("snippet")),
        access_status="captured",
        artifact_id=text(artifact.get("artifact_id")) or None,
        metadata=metadata,
    )
    findings = [
        ResearchFinding(
            finding_id="artifact-summary-1",
            finding_type="artifact-summary",
            summary=summary,
            supporting_source_ids=[source.source_id],
        )
    ]
    return ResearchAdapterResult(
        adapter_kind="artifact",
        collection_action="capture",
        status="succeeded",
        collected_sources=[source],
        findings=findings if summary else [],
        summary=summary or f"Captured artifact source: {source.source_ref}",
    )


__all__ = ["collect_artifact"]
