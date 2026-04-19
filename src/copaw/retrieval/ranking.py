# -*- coding: utf-8 -*-
from __future__ import annotations

from .contracts import RetrievalHit


def _ranking_key(hit: RetrievalHit) -> tuple[float, float, float, float, float, float]:
    return (
        float(hit.score),
        float(hit.relevance_score),
        float(hit.answerability_score),
        float(hit.freshness_score),
        float(hit.credibility_score),
        float(hit.structural_score),
    )


def rank_retrieval_hits(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    return sorted(list(hits), key=_ranking_key, reverse=True)


__all__ = ["rank_retrieval_hits"]
