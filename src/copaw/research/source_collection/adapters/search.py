# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urldefrag

from ..contracts import CollectedSource, ResearchAdapterResult, ResearchBrief, ResearchFinding


def _text(value: object) -> str:
    return str(value or "").strip()


def _normalized_ref(value: str) -> str:
    return urldefrag(value).url if value else ""


def collect_search(brief: ResearchBrief) -> ResearchAdapterResult:
    raw_hits = brief.metadata.get("search_hits")
    hits = raw_hits if isinstance(raw_hits, list) else []
    collected_sources: list[CollectedSource] = []

    for index, item in enumerate(hits, start=1):
        if not isinstance(item, Mapping):
            continue
        source_ref = _text(item.get("url") or item.get("source_ref"))
        if not source_ref:
            continue
        collected_sources.append(
            CollectedSource(
                source_id=f"search-hit-{index}",
                source_kind="search_hit",
                collection_action="discover",
                source_ref=source_ref,
                normalized_ref=_normalized_ref(source_ref),
                title=_text(item.get("title")),
                snippet=_text(item.get("snippet")),
                access_status="discovered",
                metadata={"rank": index},
            )
        )

    if not collected_sources:
        return ResearchAdapterResult(
            adapter_kind="search",
            collection_action="discover",
            status="partial",
            summary="Search adapter is missing discovered hits.",
            gaps=["search hits missing from research brief metadata"],
        )

    return ResearchAdapterResult(
        adapter_kind="search",
        collection_action="discover",
        status="succeeded",
        collected_sources=collected_sources,
        findings=[
            ResearchFinding(
                finding_id="search-discovery-1",
                finding_type="candidate-source-set",
                summary=f"Discovered {len(collected_sources)} candidate sources for the brief.",
                supporting_source_ids=[source.source_id for source in collected_sources],
            )
        ],
        summary=f"Discovered {len(collected_sources)} search hit(s).",
    )


__all__ = ["collect_search"]
