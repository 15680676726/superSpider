# -*- coding: utf-8 -*-
from __future__ import annotations

from ..contracts import RetrievalHit
from ..utils import normalize_ref, search_live_web, text
from .credibility import score_web_credibility
from .freshness import score_web_freshness


def discover_web_hits(*, query: str, limit: int = 5, source_kind: str = "search") -> list[RetrievalHit]:
    raw_hits = search_live_web(query, limit=limit)
    hits: list[RetrievalHit] = []
    for index, item in enumerate(raw_hits, start=1):
        source_ref = text(item.get("url") or item.get("source_ref"))
        if not source_ref:
            continue
        credibility = score_web_credibility(source_ref)
        freshness = score_web_freshness({})
        hits.append(
            RetrievalHit(
                source_kind=source_kind,
                provider_kind="discover",
                hit_kind="search-hit",
                ref=source_ref,
                normalized_ref=normalize_ref(source_ref),
                title=text(item.get("title")),
                snippet=text(item.get("snippet")),
                score=0.8,
                relevance_score=0.8,
                answerability_score=0.7,
                freshness_score=freshness,
                credibility_score=credibility,
                structural_score=0.2,
                why_matched=f"web discovery hit #{index}",
                metadata={"rank": index},
            )
        )
    return hits


__all__ = ["discover_web_hits"]
