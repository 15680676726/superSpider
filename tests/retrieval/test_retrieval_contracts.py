# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.retrieval.contracts import RetrievalHit, RetrievalPlan, RetrievalQuery, RetrievalRun


def test_retrieval_hit_supports_unified_multi_source_shape() -> None:
    hit = RetrievalHit(
        source_kind="local_repo",
        provider_kind="symbol",
        hit_kind="symbol",
        ref="src/copaw/app/runtime_bootstrap_domains.py",
        normalized_ref="src/copaw/app/runtime_bootstrap_domains.py",
        title="run_source_collection_frontdoor",
        snippet="def run_source_collection_frontdoor(...):",
        score=0.9,
        relevance_score=0.9,
        answerability_score=0.8,
        freshness_score=0.0,
        credibility_score=1.0,
        structural_score=0.95,
        why_matched="matched requested frontdoor symbol",
    )
    assert hit.source_kind == "local_repo"
    assert hit.provider_kind == "symbol"


def test_retrieval_run_tracks_selected_and_dropped_hits() -> None:
    run = RetrievalRun(
        query=RetrievalQuery(question="q", goal="g", intent="repo-trace"),
        plan=RetrievalPlan(
            intent="repo-trace",
            source_sequence=["local_repo"],
            mode_sequence=["symbol", "exact", "semantic"],
        ),
        selected_hits=[],
        dropped_hits=[],
    )
    assert run.plan.intent == "repo-trace"
    assert run.selected_hits == []
    assert run.dropped_hits == []
