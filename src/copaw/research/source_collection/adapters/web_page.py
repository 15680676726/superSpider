# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping

from ..contracts import CollectedSource, ResearchAdapterResult, ResearchBrief, ResearchFinding
from ._shared import extract_first_url, guess_title_from_ref, normalize_ref, summarize_html_page, text


def _read_live_page(source_ref: str) -> dict[str, str]:
    payload = summarize_html_page(source_ref)
    return {
        "url": payload.get("url", source_ref),
        "title": payload.get("title", ""),
        "snippet": payload.get("snippet", ""),
        "summary": payload.get("summary", ""),
    }


def _resolve_page_ref(brief: ResearchBrief, page: Mapping[str, object]) -> str:
    explicit = text(page.get("url") or page.get("source_ref"))
    if explicit:
        return explicit
    metadata = brief.metadata if isinstance(brief.metadata, dict) else {}
    discovered_sources = metadata.get("discovered_sources")
    if isinstance(discovered_sources, list):
        for item in discovered_sources:
            if isinstance(item, Mapping):
                candidate = text(item.get("source_ref"))
                if candidate:
                    return candidate
    return extract_first_url(brief.question, brief.goal)


def collect_web_page(brief: ResearchBrief) -> ResearchAdapterResult:
    payload = brief.metadata.get("web_page")
    page = payload if isinstance(payload, Mapping) else {}
    source_ref = _resolve_page_ref(brief, page)
    if not source_ref:
        return ResearchAdapterResult(
            adapter_kind="web_page",
            collection_action="read",
            status="partial",
            summary="Web page adapter is missing a page reference.",
            gaps=["web page reference missing from research brief metadata"],
        )

    try:
        live_page = (
            {}
            if payload is not None
            else _read_live_page(source_ref)
        )
    except Exception as exc:
        return ResearchAdapterResult(
            adapter_kind="web_page",
            collection_action="read",
            status="blocked",
            summary=f"Web page adapter could not read the target page: {exc}",
            gaps=["web page provider could not read the requested page"],
        )
    summary = text(page.get("summary") or page.get("snippet") or page.get("title"))
    if not summary:
        summary = text(
            live_page.get("summary")
            or live_page.get("snippet")
            or live_page.get("title")
        )
    source = CollectedSource(
        source_id="web-page-1",
        source_kind="web_page",
        collection_action="read",
        source_ref=source_ref,
        normalized_ref=normalize_ref(source_ref),
        title=text(page.get("title") or live_page.get("title") or guess_title_from_ref(source_ref)),
        snippet=text(page.get("snippet") or live_page.get("snippet")),
        access_status="read",
    )
    findings = [
        ResearchFinding(
            finding_id="web-page-summary-1",
            finding_type="page-summary",
            summary=summary,
            supporting_source_ids=[source.source_id],
        )
    ]
    return ResearchAdapterResult(
        adapter_kind="web_page",
        collection_action="read",
        status="succeeded",
        collected_sources=[source],
        findings=findings if summary else [],
        summary=summary or f"Read web page: {source.title or source.normalized_ref}",
    )


__all__ = ["collect_web_page"]
