# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.retrieval.contracts import RetrievalHit
from copaw.retrieval.ranking import rank_retrieval_hits


def test_ranking_prefers_higher_total_score() -> None:
    lower = RetrievalHit(
        source_kind="web",
        provider_kind="discover",
        hit_kind="result",
        ref="https://example.com/1",
        normalized_ref="https://example.com/1",
        score=0.4,
        relevance_score=0.4,
        answerability_score=0.4,
        freshness_score=0.3,
        credibility_score=0.3,
        structural_score=0.0,
        why_matched="lower",
    )
    higher = RetrievalHit(
        source_kind="local_repo",
        provider_kind="symbol",
        hit_kind="symbol",
        ref="src/copaw/app/runtime_bootstrap_domains.py",
        normalized_ref="src/copaw/app/runtime_bootstrap_domains.py",
        score=0.9,
        relevance_score=0.9,
        answerability_score=0.9,
        freshness_score=0.0,
        credibility_score=1.0,
        structural_score=0.9,
        why_matched="higher",
    )

    ranked = rank_retrieval_hits([lower, higher])

    assert ranked[0].ref == higher.ref


def test_ranking_preserves_existing_order_for_tied_scores() -> None:
    first = RetrievalHit(
        source_kind="github",
        provider_kind="object",
        hit_kind="issue",
        ref="https://github.com/example/repo/issues/1",
        normalized_ref="https://github.com/example/repo/issues/1",
        score=0.5,
        relevance_score=0.5,
        answerability_score=0.5,
        freshness_score=0.5,
        credibility_score=0.5,
        structural_score=0.0,
        why_matched="first",
    )
    second = RetrievalHit(
        source_kind="github",
        provider_kind="object",
        hit_kind="issue",
        ref="https://github.com/example/repo/issues/2",
        normalized_ref="https://github.com/example/repo/issues/2",
        score=0.5,
        relevance_score=0.5,
        answerability_score=0.5,
        freshness_score=0.5,
        credibility_score=0.5,
        structural_score=0.0,
        why_matched="second",
    )

    ranked = rank_retrieval_hits([first, second])

    assert [item.ref for item in ranked] == [first.ref, second.ref]
