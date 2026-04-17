# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urldefrag

from ..contracts import CollectedSource, ResearchAdapterResult, ResearchBrief, ResearchFinding


def _text(value: object) -> str:
    return str(value or "").strip()


def _normalized_ref(value: str) -> str:
    return urldefrag(value).url if value else ""


def collect_web_page(brief: ResearchBrief) -> ResearchAdapterResult:
    payload = brief.metadata.get("web_page")
    page = payload if isinstance(payload, Mapping) else {}
    source_ref = _text(page.get("url") or page.get("source_ref"))
    if not source_ref:
        return ResearchAdapterResult(
            adapter_kind="web_page",
            collection_action="read",
            status="partial",
            summary="Web page adapter is missing a page reference.",
            gaps=["web page reference missing from research brief metadata"],
        )

    summary = _text(page.get("summary") or page.get("snippet") or page.get("title"))
    source = CollectedSource(
        source_id="web-page-1",
        source_kind="web_page",
        collection_action="read",
        source_ref=source_ref,
        normalized_ref=_normalized_ref(source_ref),
        title=_text(page.get("title")),
        snippet=_text(page.get("snippet")),
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
