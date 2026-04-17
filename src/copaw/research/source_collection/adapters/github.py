# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urldefrag, urlparse

from ..contracts import CollectedSource, ResearchAdapterResult, ResearchBrief, ResearchFinding


def _text(value: object) -> str:
    return str(value or "").strip()


def _normalized_ref(value: str) -> str:
    return urldefrag(value).url if value else ""


def _github_metadata(source_ref: str) -> dict[str, str]:
    parsed = urlparse(source_ref)
    segments = [segment for segment in parsed.path.split("/") if segment]
    repository = "/".join(segments[:2]) if len(segments) >= 2 else ""
    target_kind = "repository"
    if len(segments) >= 3:
        segment = segments[2].lower()
        if segment == "issues":
            target_kind = "issue"
        elif segment in {"pull", "pulls"}:
            target_kind = "pull_request"
        elif segment == "commit":
            target_kind = "commit"
        elif segment == "blob":
            target_kind = "blob"
        elif segment == "tree":
            target_kind = "tree"
        elif segment == "discussions":
            target_kind = "discussion"
        else:
            target_kind = segment
    return {
        "repository": repository,
        "github_target_kind": target_kind,
    }


def collect_github(brief: ResearchBrief) -> ResearchAdapterResult:
    payload = brief.metadata.get("github")
    github_target = payload if isinstance(payload, Mapping) else {}
    source_ref = _text(github_target.get("url") or github_target.get("source_ref"))
    if not source_ref:
        return ResearchAdapterResult(
            adapter_kind="github",
            collection_action="interact",
            status="partial",
            summary="GitHub adapter is missing a repository target.",
            gaps=["github target missing from research brief metadata"],
        )

    summary = _text(
        github_target.get("summary")
        or github_target.get("snippet")
        or github_target.get("title")
    )
    source = CollectedSource(
        source_id="github-target-1",
        source_kind="github_target",
        collection_action="interact",
        source_ref=source_ref,
        normalized_ref=_normalized_ref(source_ref),
        title=_text(github_target.get("title")),
        snippet=_text(github_target.get("snippet")),
        access_status="interacted",
        metadata=_github_metadata(source_ref),
    )
    findings = [
        ResearchFinding(
            finding_id="github-target-summary-1",
            finding_type="github-context",
            summary=summary,
            supporting_source_ids=[source.source_id],
        )
    ]
    return ResearchAdapterResult(
        adapter_kind="github",
        collection_action="interact",
        status="succeeded",
        collected_sources=[source],
        findings=findings if summary else [],
        summary=summary or f"Interacted with GitHub target: {source.normalized_ref}",
    )


__all__ = ["collect_github"]
