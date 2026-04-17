# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.research.source_collection.adapters import (
    build_source_collection_adapters,
    collect_artifact,
    collect_github,
    collect_search,
    collect_web_page,
)
from copaw.research.source_collection.contracts import ResearchBrief


def _brief(*, metadata: dict | None = None) -> ResearchBrief:
    return ResearchBrief(
        owner_agent_id="industry-researcher-demo",
        supervisor_agent_id="main-brain",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        assignment_id="assignment-1",
        goal="Map the current evidence surface",
        question="Which external sources should be checked for the latest update?",
        why_needed="Keep the execution context grounded in fresh source material.",
        done_when="The next execution step has enough cited backing.",
        metadata=metadata or {},
    )


def test_build_source_collection_adapters_exposes_phase1_adapter_set() -> None:
    adapters = build_source_collection_adapters()

    assert set(adapters) == {"search", "web_page", "github", "artifact"}
    assert adapters["search"] is collect_search
    assert adapters["web_page"] is collect_web_page
    assert adapters["github"] is collect_github
    assert adapters["artifact"] is collect_artifact


def test_collect_search_normalizes_discovered_hits() -> None:
    result = collect_search(
        _brief(
            metadata={
                "search_hits": [
                    {
                        "title": "Official release note",
                        "url": "https://example.com/releases/v1?ref=feed#summary",
                        "snippet": "Lists the canonical Phase 1 changes.",
                    },
                    {
                        "title": "Community digest",
                        "url": "https://mirror.example.com/post",
                        "snippet": "Secondary source coverage.",
                    },
                ]
            }
        )
    )

    assert result.adapter_kind == "search"
    assert result.collection_action == "discover"
    assert result.status == "succeeded"
    assert [source.source_kind for source in result.collected_sources] == [
        "search_hit",
        "search_hit",
    ]
    assert result.collected_sources[0].normalized_ref == (
        "https://example.com/releases/v1?ref=feed"
    )
    assert result.findings[0].supporting_source_ids == ["search-hit-1", "search-hit-2"]


def test_collect_web_page_reads_single_page_snapshot() -> None:
    result = collect_web_page(
        _brief(
            metadata={
                "web_page": {
                    "url": "https://docs.example.com/runtime-center#overview",
                    "title": "Runtime Center",
                    "snippet": "Explains the current runtime-center read surface.",
                    "summary": "The page describes the research summary card and read API.",
                }
            }
        )
    )

    assert result.adapter_kind == "web_page"
    assert result.collection_action == "read"
    assert result.status == "succeeded"
    assert result.collected_sources[0].source_ref == "https://docs.example.com/runtime-center#overview"
    assert result.collected_sources[0].normalized_ref == "https://docs.example.com/runtime-center"
    assert result.findings[0].summary == (
        "The page describes the research summary card and read API."
    )


def test_collect_github_tracks_repository_context_and_interaction_target() -> None:
    result = collect_github(
        _brief(
            metadata={
                "github": {
                    "url": "https://github.com/example/project/issues/42",
                    "title": "Issue 42",
                    "snippet": "Tracks the adapter migration work.",
                    "summary": "The issue confirms the provider adapter cutover sequence.",
                }
            }
        )
    )

    assert result.adapter_kind == "github"
    assert result.collection_action == "interact"
    assert result.status == "succeeded"
    assert result.collected_sources[0].metadata["repository"] == "example/project"
    assert result.collected_sources[0].metadata["github_target_kind"] == "issue"
    assert result.findings[0].supporting_source_ids == ["github-target-1"]


def test_collect_artifact_captures_artifact_reference() -> None:
    result = collect_artifact(
        _brief(
            metadata={
                "artifact": {
                    "artifact_id": "artifact-77",
                    "path": "D:/word/copaw/reports/research-note.md",
                    "title": "Research Note",
                    "snippet": "Operator supplied scratch evidence.",
                    "summary": "The scratch note captures provisional evidence for the next round.",
                }
            }
        )
    )

    assert result.adapter_kind == "artifact"
    assert result.collection_action == "capture"
    assert result.status == "succeeded"
    assert result.collected_sources[0].artifact_id == "artifact-77"
    assert result.collected_sources[0].source_ref == "D:/word/copaw/reports/research-note.md"
    assert result.findings[0].summary == (
        "The scratch note captures provisional evidence for the next round."
    )


def test_collect_artifact_returns_partial_when_reference_missing() -> None:
    result = collect_artifact(_brief())

    assert result.adapter_kind == "artifact"
    assert result.collection_action == "capture"
    assert result.status == "partial"
    assert result.collected_sources == []
    assert result.gaps == ["artifact reference missing from research brief metadata"]


def test_collect_search_uses_live_search_when_metadata_missing(monkeypatch) -> None:
    from copaw.research.source_collection.adapters import search as search_module

    monkeypatch.setattr(
        search_module,
        "_search_live",
        lambda query, limit=5: [
            {
                "title": "Live result",
                "url": "https://example.com/live-result",
                "snippet": f"query={query}; limit={limit}",
            }
        ],
    )

    result = collect_search(_brief())

    assert result.status == "succeeded"
    assert result.collected_sources[0].source_ref == "https://example.com/live-result"
    assert "Discovered 1 search hit" in result.summary


def test_collect_search_falls_back_to_secondary_provider(monkeypatch) -> None:
    from copaw.research.source_collection.adapters import search as search_module

    monkeypatch.setattr(
        search_module,
        "_search_duckduckgo",
        lambda query, limit: (_ for _ in ()).throw(TimeoutError("ddg timed out")),
    )
    monkeypatch.setattr(
        search_module,
        "_search_bing",
        lambda query, limit: [
            {
                "title": "Fallback result",
                "url": "https://example.com/fallback",
                "snippet": f"{query}:{limit}",
            }
        ],
    )

    result = search_module.collect_search(_brief())

    assert result.status == "succeeded"
    assert result.collected_sources[0].source_ref == "https://example.com/fallback"


def test_collect_web_page_reads_live_page_from_direct_url(monkeypatch) -> None:
    from copaw.research.source_collection.adapters import web_page as web_page_module

    monkeypatch.setattr(
        web_page_module,
        "_read_live_page",
        lambda source_ref: {
            "url": source_ref,
            "title": "Live Runtime Center",
            "snippet": "Live snippet",
            "summary": "Live page summary",
        },
    )

    result = collect_web_page(
        _brief(
            metadata={},
        ).model_copy(
            update={
                "question": "https://docs.example.com/runtime-center",
            }
        )
    )

    assert result.status == "succeeded"
    assert result.collected_sources[0].normalized_ref == "https://docs.example.com/runtime-center"
    assert result.findings[0].summary == "Live page summary"


def test_collect_web_page_returns_blocked_when_live_read_fails(monkeypatch) -> None:
    from copaw.research.source_collection.adapters import web_page as web_page_module

    monkeypatch.setattr(
        web_page_module,
        "_read_live_page",
        lambda source_ref: (_ for _ in ()).throw(TimeoutError(source_ref)),
    )

    result = collect_web_page(
        _brief().model_copy(
            update={
                "question": "https://docs.example.com/runtime-center",
            }
        )
    )

    assert result.status == "blocked"
    assert result.gaps == ["web page provider could not read the requested page"]


def test_collect_github_resolves_live_repository_query(monkeypatch) -> None:
    from copaw.research.source_collection.adapters import github as github_module

    monkeypatch.setattr(
        github_module,
        "_search_github_live",
        lambda query, limit=1: [
            {
                "url": "https://github.com/example/project",
                "title": "example/project",
                "summary": f"Live repo for {query}",
                "metadata": {
                    "repository": "example/project",
                    "github_target_kind": "repository",
                },
            }
        ],
    )

    result = collect_github(
        _brief().model_copy(
            update={
                "question": "example project runtime center adapter",
            }
        )
    )

    assert result.status == "succeeded"
    assert result.collected_sources[0].metadata["repository"] == "example/project"
    assert result.findings[0].summary == "Live repo for example project runtime center adapter"


def test_collect_artifact_captures_live_local_file(tmp_path: Path) -> None:
    artifact_path = tmp_path / "research-note.md"
    artifact_path.write_text("# research\ncontent\n", encoding="utf-8")

    result = collect_artifact(
        _brief().model_copy(
            update={
                "question": str(artifact_path),
            }
        )
    )

    assert result.status == "succeeded"
    assert result.collected_sources[0].source_ref == str(artifact_path)
    assert result.collected_sources[0].metadata["storage_kind"] == "local-file"
