# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping

from ..contracts import CollectedSource, ResearchAdapterResult, ResearchBrief, ResearchFinding


def _text(value: object) -> str:
    return str(value or "").strip()


def collect_artifact(brief: ResearchBrief) -> ResearchAdapterResult:
    payload = brief.metadata.get("artifact")
    artifact = payload if isinstance(payload, Mapping) else {}
    source_ref = _text(artifact.get("path") or artifact.get("source_ref"))
    if not source_ref:
        return ResearchAdapterResult(
            adapter_kind="artifact",
            collection_action="capture",
            status="partial",
            summary="Artifact adapter is missing an artifact reference.",
            gaps=["artifact reference missing from research brief metadata"],
        )

    summary = _text(artifact.get("summary") or artifact.get("snippet") or artifact.get("title"))
    source = CollectedSource(
        source_id="artifact-1",
        source_kind="artifact",
        collection_action="capture",
        source_ref=source_ref,
        normalized_ref=source_ref,
        title=_text(artifact.get("title")),
        snippet=_text(artifact.get("snippet")),
        access_status="captured",
        artifact_id=_text(artifact.get("artifact_id")) or None,
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
