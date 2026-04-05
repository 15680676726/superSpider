# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.discovery import provider_search as provider_search_module


def test_search_github_repository_donors_builds_normalized_hits(monkeypatch) -> None:
    monkeypatch.setattr(
        provider_search_module,
        "_github_api_json",
        lambda _query, limit=10, search_url=None: {
            "items": [
                {
                    "full_name": "acme/browser-pilot",
                    "html_url": "https://github.com/acme/browser-pilot",
                    "description": "Browser automation donor",
                    "topics": ["browser", "automation"],
                    "language": "Python",
                    "default_branch": "main",
                    "stargazers_count": 1200,
                    "updated_at": "2026-04-05T09:00:00Z",
                },
            ],
        },
    )
    hits = provider_search_module.search_github_repository_donors(
        "browser automation github",
        limit=5,
    )

    assert len(hits) == 1
    hit = hits[0]
    assert hit.source_kind == "github-repo"
    assert hit.display_name == "acme/browser-pilot"
    assert hit.candidate_source_ref == "https://github.com/acme/browser-pilot"
    assert hit.canonical_package_id == "pkg:github:acme/browser-pilot"
    assert hit.candidate_source_lineage == "donor:github:acme/browser-pilot"
    assert "browser" in hit.capability_keys
    assert "automation" in hit.capability_keys
    assert hit.metadata["materialization_strategy"] == "github-python-project"
    assert hit.metadata["install_transport_chain"] == [
        "git",
        "codeload-tar-gz",
        "github-archive-zip",
    ]


def test_search_github_repository_donors_keeps_open_source_project_candidates(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        provider_search_module,
        "_github_api_json",
        lambda _query, limit=10, search_url=None: {
            "items": [
                {
                    "full_name": "acme/broken-browser",
                    "html_url": "https://github.com/acme/broken-browser",
                    "description": "Not installable",
                    "topics": ["browser"],
                    "language": "Python",
                    "default_branch": "main",
                    "stargazers_count": 10,
                    "updated_at": "2026-04-05T09:00:00Z",
                },
                {
                    "full_name": "acme/browser-pilot",
                    "html_url": "https://github.com/acme/browser-pilot",
                    "description": "Installable browser donor",
                    "topics": ["browser", "automation"],
                    "language": "Python",
                    "default_branch": "main",
                    "stargazers_count": 1200,
                    "updated_at": "2026-04-05T09:00:00Z",
                },
            ],
        },
    )
    hits = provider_search_module.search_github_repository_donors(
        "browser automation github",
        limit=5,
    )

    assert [hit.display_name for hit in hits] == [
        "acme/broken-browser",
        "acme/browser-pilot",
    ]
    assert hits[0].metadata["install_supported"] is True


def test_search_github_repository_donors_supports_direct_repo_query(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        provider_search_module,
        "_github_api_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("search API should not run for direct repo query"),
        ),
    )
    hits = provider_search_module.search_github_repository_donors(
        "https://github.com/acme/browser-pilot",
        limit=5,
    )

    assert len(hits) == 1
    assert hits[0].display_name == "acme/browser-pilot"
    assert hits[0].candidate_source_ref == "https://github.com/acme/browser-pilot"
