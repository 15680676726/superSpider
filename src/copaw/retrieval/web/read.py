# -*- coding: utf-8 -*-
from __future__ import annotations

from ..contracts import RetrievalHit
from ..utils import normalize_ref, summarize_html_page
from .credibility import score_web_credibility
from .freshness import score_web_freshness


def read_web_page_hit(*, source_ref: str, source_kind: str = "web_page") -> list[RetrievalHit]:
    payload = summarize_html_page(source_ref)
    credibility = score_web_credibility(source_ref)
    freshness = score_web_freshness(payload)
    return [
        RetrievalHit(
            source_kind=source_kind,
            provider_kind="read",
            hit_kind="page",
            ref=payload.get("url", source_ref),
            normalized_ref=normalize_ref(payload.get("url", source_ref)),
            title=str(payload.get("title") or ""),
            snippet=str(payload.get("summary") or payload.get("snippet") or ""),
            score=0.9,
            relevance_score=0.9,
            answerability_score=0.85,
            freshness_score=freshness,
            credibility_score=credibility,
            structural_score=0.3,
            why_matched="direct web page read",
            metadata={"content_type": payload.get("content_type", "")},
        )
    ]


__all__ = ["read_web_page_hit"]
