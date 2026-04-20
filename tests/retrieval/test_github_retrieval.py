# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.retrieval import RetrievalFacade


def test_facade_returns_github_hit_for_direct_issue_url() -> None:
    run = RetrievalFacade(workspace_root=Path(__file__).resolve().parents[2]).retrieve(
        question="https://github.com/example/project/issues/42",
        goal="inspect the upstream issue context",
        requested_sources=["github"],
    )

    assert run.selected_hits
    assert run.selected_hits[0].source_kind == "github"
    assert run.selected_hits[0].metadata["repository"] == "example/project"
    assert run.selected_hits[0].metadata["github_target_kind"] == "issue"
