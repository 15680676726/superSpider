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


LIVE_SEARCHING_SOAK_SKIP_REASON = (
    "Set COPAW_RUN_SEARCHING_SOAK=1 to run searching soak coverage "
    "(opt-in; not part of default regression coverage)."
)


class _UnusedHeavyResearchService:
    def start_session(self, **kwargs):
        raise AssertionError(f"heavy path should not run during searching soak: {kwargs}")


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_runtime_center_client(state_path: Path) -> tuple[TestClient, SqliteResearchSessionRepository]:
    app = FastAPI()
    repository = SqliteResearchSessionRepository(SQLiteStateStore(state_path))
    app.state.research_session_repository = repository
    app.include_router(runtime_center_router)
    return TestClient(app), repository


def test_searching_soak_skip_reason_declares_opt_in_boundary() -> None:
    reason = LIVE_SEARCHING_SOAK_SKIP_REASON.lower()
    assert "opt-in" in reason
    assert "not part of default regression coverage" in reason


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_SEARCHING_SOAK"),
    reason=LIVE_SEARCHING_SOAK_SKIP_REASON,
)
def test_searching_soak_repeats_queries_and_preserves_runtime_center_projection(tmp_path) -> None:
    query = "runtime center research surface reads which formal truth fields"
    first_facade = RetrievalFacade(workspace_root=_repo_root())
    second_facade = RetrievalFacade(workspace_root=_repo_root())

    first_run = first_facade.retrieve(
        question=query,
        goal="trace runtime center research payload",
        requested_sources=["local_repo"],
    )
    second_run = second_facade.retrieve(
        question=query,
        goal="trace runtime center research payload",
        requested_sources=["local_repo"],
    )

    assert first_run.selected_hits
    assert second_run.selected_hits
    assert first_run.selected_hits[0].ref == second_run.selected_hits[0].ref
    assert "runtime_center_payloads.py" in first_run.selected_hits[0].ref

    mixed_run = first_facade.retrieve(
        question="GitHub Copilot repository indexing official documentation",
        goal="compare official docs and repository context",
        requested_sources=["github", "search"],
        latest_required=True,
        metadata={"github": {"url": "https://github.com/openai/openai-python"}},
    )
    selected_source_kinds = {hit.source_kind for hit in mixed_run.selected_hits}
    assert "github" in selected_source_kinds
    assert "search" in selected_source_kinds

    state_path = tmp_path / "searching-soak-state.sqlite3"
    client_one, repository_one = _build_runtime_center_client(state_path)
    frontdoor = SourceCollectionFrontdoorService(
        heavy_research_service=_UnusedHeavyResearchService(),
        research_session_repository=repository_one,
    )
    frontdoor.run_source_collection_frontdoor(
        goal="trace the source collection frontdoor",
        question="run_source_collection_frontdoor",
        why_needed="preserve retrieval projection across refresh",
        done_when="runtime center still exposes retrieval hits after restart",
        trigger_source="agent-entry",
        owner_agent_id="writer-agent",
        work_context_id="ctx-searching-soak",
        collection_mode_hint="light",
        requested_sources=["local_repo"],
        writeback_target={"scope_type": "work_context", "scope_id": "ctx-searching-soak"},
        metadata={"entry_surface": "searching-soak"},
    )

    payload_one = client_one.get("/runtime-center/research").json()
    assert payload_one["retrieval"]["selected_hits"]

    client_two, _repository_two = _build_runtime_center_client(state_path)
    payload_two = client_two.get("/runtime-center/research").json()
    assert payload_two["retrieval"]["selected_hits"]
    assert payload_one["retrieval"]["selected_hits"][0]["ref"] == payload_two["retrieval"]["selected_hits"][0]["ref"]
    assert payload_one["retrieval"]["coverage"] == payload_two["retrieval"]["coverage"]
