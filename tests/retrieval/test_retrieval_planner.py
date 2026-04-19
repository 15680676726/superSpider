# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.retrieval.planner import build_retrieval_plan


def test_planner_keeps_frontdoor_mode_separate_from_retrieval_mode() -> None:
    plan = build_retrieval_plan(
        intent="repo-trace",
        requested_sources=["local_repo"],
        latest_required=False,
    )
    assert plan.mode_sequence == ["symbol", "exact", "semantic"]
    assert plan.source_sequence == ["local_repo"]


def test_planner_prefers_github_and_web_for_external_latest_queries() -> None:
    plan = build_retrieval_plan(
        intent="external-latest",
        requested_sources=[],
        latest_required=True,
    )
    assert plan.source_sequence == ["github", "web"]
    assert plan.mode_sequence == ["exact", "semantic"]
