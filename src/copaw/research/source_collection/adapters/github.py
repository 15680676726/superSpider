# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlparse

from ....discovery.provider_search import search_github_repository_donors
from ..contracts import CollectedSource, ResearchAdapterResult, ResearchBrief, ResearchFinding
from ._shared import extract_first_url, normalize_ref, summarize_html_page, text


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


def _search_github_live(query: str, limit: int = 1) -> list[dict[str, object]]:
    hits = search_github_repository_donors(query, limit=limit)
    results: list[dict[str, object]] = []
    for hit in hits:
        source_ref = text(getattr(hit, "candidate_source_ref", None))
        if not source_ref:
            continue
        metadata = dict(getattr(hit, "metadata", {}) or {})
        metadata.setdefault("repository", text(getattr(hit, "display_name", None)))
        metadata.setdefault("github_target_kind", "repository")
        results.append(
            {
                "url": source_ref,
                "title": text(getattr(hit, "display_name", None)),
                "summary": text(getattr(hit, "summary", None)),
                "metadata": metadata,
            }
        )
    return results


def _resolve_live_github_target(brief: ResearchBrief) -> dict[str, object]:
    direct_url = extract_first_url(brief.question, brief.goal)
    try:
        if direct_url and "github.com/" in direct_url.casefold():
            page = summarize_html_page(direct_url)
            return {
                "url": direct_url,
                "title": text(page.get("title")),
                "summary": text(page.get("summary") or page.get("snippet")),
                "metadata": _github_metadata(direct_url),
            }
        live_hits = _search_github_live(brief.question, limit=1)
        return live_hits[0] if live_hits else {}
    except Exception:
        return {}


def collect_github(brief: ResearchBrief) -> ResearchAdapterResult:
    payload = brief.metadata.get("github")
    live_target = _resolve_live_github_target(brief) if payload is None else {}
    github_target = payload if isinstance(payload, Mapping) else live_target
    source_ref = text(github_target.get("url") or github_target.get("source_ref"))
    if not source_ref:
        return ResearchAdapterResult(
            adapter_kind="github",
            collection_action="interact",
            status="partial",
            summary="GitHub adapter is missing a repository target.",
            gaps=["github target missing from research brief metadata"],
        )

    summary = text(
        github_target.get("summary")
        or github_target.get("snippet")
        or github_target.get("title")
    )
    source = CollectedSource(
        source_id="github-target-1",
        source_kind="github_target",
        collection_action="interact",
        source_ref=source_ref,
        normalized_ref=normalize_ref(source_ref),
        title=text(github_target.get("title")),
        snippet=text(github_target.get("snippet")),
        access_status="interacted",
        metadata={
            **_github_metadata(source_ref),
            **(
                dict(github_target.get("metadata") or {})
                if isinstance(github_target.get("metadata"), Mapping)
                else {}
            ),
        },
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
