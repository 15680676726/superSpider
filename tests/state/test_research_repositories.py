# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.app.runtime_bootstrap_models import RuntimeManagerStack
from copaw.app.runtime_bootstrap_repositories import build_runtime_repositories
from copaw.app.runtime_state_bindings import build_runtime_state_bindings
from copaw.state import (
    ResearchSessionRecord,
    ResearchSessionRoundRecord,
    SQLiteStateStore,
)
from copaw.state.repositories import SqliteResearchSessionRepository


class _BootstrapStub:
    def __init__(self, repositories) -> None:
        self.repositories = repositories

    def __getattr__(self, name: str):
        value = SimpleNamespace(name=name)
        setattr(self, name, value)
        return value


def test_research_session_repository_round_trip(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteResearchSessionRepository(store)

    session = ResearchSessionRecord(
        id="research-session-1",
        provider="baidu-page",
        industry_instance_id="industry-1",
        work_context_id="work-context-1",
        owner_agent_id="industry-researcher-demo",
        supervisor_agent_id="main-brain",
        trigger_source="user-direct",
        goal="梳理紫微斗数核心术语和主流流派差异",
        status="queued",
        browser_session_id="browser-session-1",
        round_count=1,
        link_depth_count=2,
        download_count=1,
        stable_findings=["命宫决定主轴"],
        open_questions=["不同流派如何解释四化"],
        metadata={"provider_mode": "browser"},
    )

    saved = repository.upsert_research_session(session)
    assert saved.goal.startswith("梳理紫微斗数")

    stored = repository.get_research_session(session.id)
    assert stored is not None
    assert stored.owner_agent_id == "industry-researcher-demo"
    assert stored.stable_findings == ["命宫决定主轴"]
    assert stored.open_questions == ["不同流派如何解释四化"]

    listed = repository.list_research_sessions(
        owner_agent_id="industry-researcher-demo",
        trigger_source="user-direct",
    )
    assert [item.id for item in listed] == [session.id]


def test_research_round_repository_round_trip(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteResearchSessionRepository(store)
    repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-1",
            provider="baidu-page",
            owner_agent_id="industry-researcher-demo",
            trigger_source="user-direct",
            goal="梳理紫微斗数核心术语",
            status="running",
        ),
    )
    round_record = ResearchSessionRoundRecord(
        id="research-round-1",
        session_id="research-session-1",
        round_index=1,
        question="紫微斗数有哪些核心术语？",
        generated_prompt="请整理术语并附来源。",
        response_excerpt="命宫、身宫、主星是核心概念。",
        response_summary="先梳理宫位和主星。",
        raw_links=[{"url": "https://example.com/raw"}],
        selected_links=[{"url": "https://example.com/selected"}],
        downloaded_artifacts=[{"kind": "pdf", "artifact_id": "artifact-1"}],
        new_findings=["命宫与身宫是高频概念"],
        remaining_gaps=["不同派别的四化解释"],
        decision="continue",
        evidence_ids=["evidence-1"],
        metadata={"round_owner": "industry-researcher-demo"},
    )

    saved = repository.upsert_research_round(round_record)
    assert saved.round_index == 1

    stored = repository.get_research_round(round_record.id)
    assert stored is not None
    assert stored.response_summary == "先梳理宫位和主星。"
    assert stored.downloaded_artifacts == [{"kind": "pdf", "artifact_id": "artifact-1"}]

    listed = repository.list_research_rounds(session_id="research-session-1")
    assert [item.id for item in listed] == [round_record.id]


def test_build_runtime_repositories_exposes_research_session_repository(tmp_path) -> None:
    repositories = build_runtime_repositories(SQLiteStateStore(tmp_path / "state.db"))

    assert repositories.research_session_repository is not None


def test_build_runtime_state_bindings_binds_research_session_repository(tmp_path) -> None:
    repositories = build_runtime_repositories(SQLiteStateStore(tmp_path / "state.db"))
    bootstrap = _BootstrapStub(repositories)

    bindings = build_runtime_state_bindings(
        runtime_host=object(),
        bootstrap=bootstrap,
        manager_stack=RuntimeManagerStack(),
        startup_recovery_summary={"reason": "startup"},
    )

    assert (
        bindings["research_session_repository"]
        is repositories.research_session_repository
    )
