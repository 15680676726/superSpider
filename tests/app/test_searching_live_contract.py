# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.runtime_bootstrap_domains import SourceCollectionFrontdoorService
from copaw.retrieval import RetrievalFacade
from copaw.state import SQLiteStateStore
from copaw.state.repositories import SqliteResearchSessionRepository


LIVE_SEARCHING_SMOKE_SKIP_REASON = (
    "Set COPAW_RUN_SEARCHING_LIVE_SMOKE=1 to run searching live smoke coverage "
    "(opt-in; not part of default regression coverage)."
)
_OFFICIAL_REPOSITORY_INDEXING_DOC = (
    "https://docs.github.com/en/copilot/concepts/context/repository-indexing"
)


class _UnusedHeavyResearchService:
    def start_session(self, **kwargs):
        raise AssertionError(f"heavy path should not run during searching live smoke: {kwargs}")


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_runtime_center_client(tmp_path: Path) -> tuple[TestClient, SqliteResearchSessionRepository]:
    app = FastAPI()
    repository = SqliteResearchSessionRepository(SQLiteStateStore(tmp_path / "state.sqlite3"))
    app.state.research_session_repository = repository
    app.include_router(runtime_center_router)
    return TestClient(app), repository


def test_searching_live_smoke_skip_reason_declares_opt_in_boundary() -> None:
    reason = LIVE_SEARCHING_SMOKE_SKIP_REASON.lower()
    assert "opt-in" in reason
    assert "not part of default regression coverage" in reason


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_SEARCHING_LIVE_SMOKE"),
    reason=LIVE_SEARCHING_SMOKE_SKIP_REASON,
)
def test_searching_live_smoke_local_repo_github_web_and_runtime_center(tmp_path) -> None:
    facade = RetrievalFacade(workspace_root=_repo_root())

    local_repo_trace = facade.retrieve(
        question="run_source_collection_frontdoor",
        goal="trace the source collection frontdoor",
        requested_sources=["local_repo"],
    )
    assert any("runtime_bootstrap_domains.py" in hit.ref for hit in local_repo_trace.selected_hits)

    local_repo_surface = facade.retrieve(
        question="runtime center research surface reads which formal truth fields",
        goal="trace runtime center research payload",
        requested_sources=["local_repo"],
    )
    assert any("runtime_center_payloads.py" in hit.ref for hit in local_repo_surface.selected_hits)

    github_repo = facade.retrieve(
        question="https://github.com/openai/openai-python",
        goal="inspect the official openai python repository target",
        requested_sources=["github"],
    )
    assert github_repo.selected_hits
    assert github_repo.selected_hits[0].metadata.get("github_target_kind") == "repository"

    github_pull = facade.retrieve(
        question="https://github.com/openai/openai-python/pull/1",
        goal="inspect a github pull request target",
        requested_sources=["github"],
    )
    assert github_pull.selected_hits
    assert github_pull.selected_hits[0].metadata.get("github_target_kind") == "pull_request"

    web_latest = facade.retrieve(
        question="GitHub Copilot repository indexing official documentation",
        goal="find the latest official repository indexing documentation",
        requested_sources=["search"],
        latest_required=True,
    )
    assert web_latest.selected_hits
    assert any(
        "docs.github.com" in (hit.normalized_ref or hit.ref)
        for hit in web_latest.selected_hits
    )

    web_page = facade.retrieve(
        question="read the canonical repository indexing document",
        goal="read the official repository indexing document",
        requested_sources=["web_page"],
        metadata={"web_page": {"url": _OFFICIAL_REPOSITORY_INDEXING_DOC}},
    )
    assert web_page.selected_hits
    assert "docs.github.com" in (web_page.selected_hits[0].normalized_ref or web_page.selected_hits[0].ref)
    assert web_page.selected_hits[0].snippet

    client, repository = _build_runtime_center_client(tmp_path)
    frontdoor = SourceCollectionFrontdoorService(
        heavy_research_service=_UnusedHeavyResearchService(),
        research_session_repository=repository,
    )
    frontdoor_result = frontdoor.run_source_collection_frontdoor(
        goal="trace the source collection frontdoor",
        question="run_source_collection_frontdoor",
        why_needed="confirm the real runtime bootstrap entry",
        done_when="the frontdoor source file is visible in runtime center",
        trigger_source="agent-entry",
        owner_agent_id="writer-agent",
        work_context_id="ctx-searching-live",
        collection_mode_hint="light",
        requested_sources=["local_repo"],
        writeback_target={"scope_type": "work_context", "scope_id": "ctx-searching-live"},
        metadata={"entry_surface": "searching-live-smoke"},
    )
    assert frontdoor_result.route_mode == "light"

    response = client.get("/runtime-center/research")
    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval"]["intent"] == "repo-trace"
    assert payload["retrieval"]["selected_hits"]
    assert any(
        "runtime_bootstrap_domains.py" in item.get("ref", "")
        for item in payload["retrieval"]["selected_hits"]
    )
