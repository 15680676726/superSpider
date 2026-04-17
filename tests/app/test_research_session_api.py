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


def test_runtime_center_research_api_returns_latest_session_and_round(tmp_path) -> None:
    client, repository = _build_client(tmp_path)
    session = repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-1",
            provider="baidu-page",
            owner_agent_id="industry-researcher-demo",
            trigger_source="user-direct",
            goal="梳理电商平台入门知识结构",
            status="running",
            round_count=2,
        ),
    )
    repository.upsert_research_round(
        ResearchSessionRoundRecord(
            id="research-round-1",
            session_id=session.id,
            round_index=1,
            question="先看电商基础框架",
            response_summary="第一轮总结",
        ),
    )
    repository.upsert_research_round(
        ResearchSessionRoundRecord(
            id="research-round-2",
            session_id=session.id,
            round_index=2,
            question="继续对比竞品资料",
            response_summary="第二轮总结",
        ),
    )

    response = client.get("/runtime-center/research")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["id"] == "research-session-1"
    assert payload["session"]["goal"] == "梳理电商平台入门知识结构"
    assert payload["latest_round"]["id"] == "research-round-2"
    assert payload["latest_round"]["response_summary"] == "第二轮总结"


def test_runtime_center_research_api_uses_latest_round_status_when_summary_missing(
    tmp_path,
) -> None:
    client, repository = _build_client(tmp_path)
    session = repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-login",
            provider="baidu-page",
            owner_agent_id="industry-researcher-demo",
            trigger_source="user-direct",
            goal="Follow the latest login requirement",
            status="running",
            round_count=1,
        ),
    )
    repository.upsert_research_round(
        ResearchSessionRoundRecord(
            id="research-round-login",
            session_id=session.id,
            round_index=1,
            question="Does the page require login?",
            decision="login_required",
        ),
    )

    response = client.get("/runtime-center/research")

    assert response.status_code == 200
    payload = response.json()
    assert payload["latest_round"]["status"] == "login_required"
    assert payload["latest_status"] == "login_required"
    assert payload["session"]["latest_status"] == "login_required"


def test_runtime_center_research_api_returns_empty_surface_without_sessions(tmp_path) -> None:
    client, _repository = _build_client(tmp_path)

    response = client.get("/runtime-center/research")

    assert response.status_code == 200
    assert response.json()["session"] is None
    assert response.json()["latest_round"] is None
