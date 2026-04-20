# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.state import ResearchSessionRecord, ResearchSessionRoundRecord, SQLiteStateStore
from copaw.state.repositories import SqliteResearchSessionRepository


def _build_client(tmp_path) -> tuple[TestClient, SqliteResearchSessionRepository]:
    app = FastAPI()
    repository = SqliteResearchSessionRepository(SQLiteStateStore(tmp_path / "state.db"))
    app.state.research_session_repository = repository
    app.include_router(runtime_center_router)
    return TestClient(app), repository


def test_runtime_center_research_surface_exposes_retrieval_summary_and_trace(tmp_path) -> None:
    client, repository = _build_client(tmp_path)
    session = repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-retrieval",
            provider="source-collection",
            owner_agent_id="writer-agent",
            work_context_id="ctx-retrieval-1",
            trigger_source="agent-entry",
            goal="trace source collection frontdoor",
            status="completed",
            round_count=1,
            brief={
                "goal": "trace source collection frontdoor",
                "question": "run_source_collection_frontdoor",
                "collection_mode_hint": "light",
                "requested_sources": ["local_repo"],
            },
            metadata={
                "retrieval": {
                    "query": {
                        "intent": "repo-trace",
                        "requested_sources": ["local_repo"],
                    },
                    "plan": {
                        "intent": "repo-trace",
                        "source_sequence": ["local_repo"],
                        "mode_sequence": ["symbol", "exact", "semantic"],
                    },
                    "coverage_summary": {"local_repo": 2},
                    "selected_hits": [
                        {
                            "source_kind": "local_repo",
                            "provider_kind": "symbol",
                            "hit_kind": "symbol",
                            "ref": "src/copaw/app/runtime_bootstrap_domains.py",
                            "normalized_ref": "src/copaw/app/runtime_bootstrap_domains.py",
                            "title": "run_source_collection_frontdoor",
                            "snippet": "run_source_collection_frontdoor(...)",
                            "why_matched": "matched requested frontdoor symbol",
                        }
                    ],
                    "dropped_hits": [
                        {
                            "source_kind": "local_repo",
                            "provider_kind": "exact",
                            "hit_kind": "file",
                            "ref": "src/copaw/kernel/query_execution_tools.py",
                            "title": "query_execution_tools.py",
                            "why_matched": "exact text match",
                        }
                    ],
                    "trace": [{"intent": "repo-trace"}],
                }
            },
        )
    )
    repository.upsert_research_round(
        ResearchSessionRoundRecord(
            id=f"{session.id}:round:1",
            session_id=session.id,
            round_index=1,
            question="run_source_collection_frontdoor",
            response_summary="frontdoor resolved",
            findings=[
                {
                    "finding_id": "finding-1",
                    "finding_type": "retrieval-hit",
                    "summary": "run_source_collection_frontdoor",
                }
            ],
            sources=[
                {
                    "source_id": "source-1",
                    "source_kind": "local_repo",
                    "collection_action": "read",
                    "source_ref": "src/copaw/app/runtime_bootstrap_domains.py",
                    "normalized_ref": "src/copaw/app/runtime_bootstrap_domains.py",
                    "title": "run_source_collection_frontdoor",
                }
            ],
            decision="stop",
            metadata={
                "retrieval": {
                    "query": {
                        "intent": "repo-trace",
                        "requested_sources": ["local_repo"],
                    },
                    "plan": {
                        "intent": "repo-trace",
                        "source_sequence": ["local_repo"],
                        "mode_sequence": ["symbol", "exact", "semantic"],
                    },
                    "coverage_summary": {"local_repo": 2},
                    "selected_hits": [
                        {
                            "source_kind": "local_repo",
                            "provider_kind": "symbol",
                            "hit_kind": "symbol",
                            "ref": "src/copaw/app/runtime_bootstrap_domains.py",
                            "normalized_ref": "src/copaw/app/runtime_bootstrap_domains.py",
                            "title": "run_source_collection_frontdoor",
                            "snippet": "run_source_collection_frontdoor(...)",
                            "why_matched": "matched requested frontdoor symbol",
                        }
                    ],
                    "dropped_hits": [
                        {
                            "source_kind": "local_repo",
                            "provider_kind": "exact",
                            "hit_kind": "file",
                            "ref": "src/copaw/kernel/query_execution_tools.py",
                            "title": "query_execution_tools.py",
                            "why_matched": "exact text match",
                        }
                    ],
                    "trace": [{"intent": "repo-trace"}],
                }
            },
        )
    )

    response = client.get("/runtime-center/research")

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval"] == {
        "intent": "repo-trace",
        "requested_sources": ["local_repo"],
        "mode_sequence": ["symbol", "exact", "semantic"],
        "coverage": {"local_repo": 2},
        "selected_hits": [
            {
                "source_kind": "local_repo",
                "provider_kind": "symbol",
                "hit_kind": "symbol",
                "ref": "src/copaw/app/runtime_bootstrap_domains.py",
                "normalized_ref": "src/copaw/app/runtime_bootstrap_domains.py",
                "title": "run_source_collection_frontdoor",
                "snippet": "run_source_collection_frontdoor(...)",
                "why_matched": "matched requested frontdoor symbol",
            }
        ],
        "dropped_hits": [
            {
                "source_kind": "local_repo",
                "provider_kind": "exact",
                "hit_kind": "file",
                "ref": "src/copaw/kernel/query_execution_tools.py",
                "title": "query_execution_tools.py",
                "why_matched": "exact text match",
            }
        ],
        "trace": [{"intent": "repo-trace"}],
    }
