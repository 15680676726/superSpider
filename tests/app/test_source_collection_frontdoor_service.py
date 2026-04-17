# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

from copaw.app.runtime_bootstrap_domains import SourceCollectionFrontdoorService
from copaw.state import ResearchSessionRecord, SQLiteStateStore
from copaw.state.repositories import SqliteResearchSessionRepository


class _UnusedHeavyResearchService:
    def start_session(self, **kwargs):
        raise AssertionError(f"heavy path should not be used: {kwargs}")


def test_light_frontdoor_persists_formal_brief_and_round_sources(tmp_path) -> None:
    repository = SqliteResearchSessionRepository(SQLiteStateStore(tmp_path / "state.db"))
    service = SourceCollectionFrontdoorService(
        heavy_research_service=_UnusedHeavyResearchService(),
        research_session_repository=repository,
    )

    result = service.run_source_collection_frontdoor(
        goal="查官网定价",
        question="官网定价是多少",
        why_needed="主脑要做价格对比",
        done_when="拿到官网价格和来源",
        trigger_source="agent-entry",
        owner_agent_id="writer-agent",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        collection_mode_hint="light",
        requested_sources=["web_page"],
        writeback_target={"scope_type": "work_context", "scope_id": "ctx-1"},
        metadata={
            "entry_surface": "test",
            "web_page": {
                "url": "https://example.com/pricing",
                "title": "Pricing",
                "summary": "基础套餐 299 元 / 月",
            },
        },
    )

    stored_session = repository.get_research_session(result.session_id)
    stored_round = repository.list_research_rounds(session_id=result.session_id)[0]

    assert stored_session is not None
    assert stored_session.brief["question"] == "官网定价是多少"
    assert stored_session.brief["writeback_target"]["scope_id"] == "ctx-1"
    assert stored_round.sources[0]["source_ref"] == "https://example.com/pricing"


class _ReusableHeavyResearchService:
    def __init__(self) -> None:
        self.start_calls: list[dict[str, object]] = []
        self.resume_calls: list[dict[str, object]] = []

    def start_session(self, **kwargs):
        self.start_calls.append(dict(kwargs))
        raise AssertionError("frontdoor should reuse the latest matching session")

    def resume_session(self, **kwargs):
        self.resume_calls.append(dict(kwargs))
        return type(
            "ResumeResult",
            (),
            {"session_id": kwargs["session_id"]},
        )()

    def run_session(self, session_id: str):
        return type(
            "RunResult",
            (),
            {"session": type("Session", (), {"status": "completed", "id": session_id})()},
        )()

    def summarize_session(self, session_id: str):
        return {
            "stop_reason": "followup-complete",
            "final_report_id": f"report:{session_id}",
        }


def test_heavy_frontdoor_reuses_latest_matching_session_for_followup_question(tmp_path) -> None:
    repository = SqliteResearchSessionRepository(SQLiteStateStore(tmp_path / "state.db"))
    now = datetime.now(timezone.utc)
    repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-existing",
            provider="baidu-page",
            industry_instance_id="industry-1",
            work_context_id="ctx-1",
            owner_agent_id="industry-researcher-demo",
            supervisor_agent_id="main-brain",
            trigger_source="user-direct",
            goal="Research Zi Wei Dou Shu basics",
            status="completed",
            round_count=2,
            brief={
                "goal": "Research Zi Wei Dou Shu basics",
                "question": "What is Zi Wei Dou Shu?",
            },
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
    )
    heavy_service = _ReusableHeavyResearchService()
    service = SourceCollectionFrontdoorService(
        heavy_research_service=heavy_service,
        research_session_repository=repository,
    )

    result = service.run_source_collection_frontdoor(
        goal="Add one common misunderstanding",
        question="Add one common misunderstanding.",
        why_needed="keep the same research thread grounded",
        done_when="one more verified clarification is enough",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        collection_mode_hint="heavy",
        requested_sources=["search", "web_page"],
        metadata={"entry_surface": "test"},
    )

    assert heavy_service.start_calls == []
    assert heavy_service.resume_calls == [
        {
            "session_id": "research-session-existing",
            "question": "Add one common misunderstanding.",
            "metadata": {
                "entry_surface": "test",
                "brief": {
                    "goal": "Add one common misunderstanding",
                    "question": "Add one common misunderstanding.",
                    "why_needed": "keep the same research thread grounded",
                    "done_when": "one more verified clarification is enough",
                    "collection_mode_hint": "heavy",
                    "requested_sources": ["search", "web_page"],
                    "writeback_target": None,
                },
                "route": {
                    "mode": "heavy",
                    "requested_sources": ["search", "web_page"],
                    "execution_agent_id": "industry-researcher-demo",
                    "reason": "brief-requested-heavy",
                },
            },
        }
    ]
    assert result.session_id == "research-session-existing"
    assert result.status == "completed"


def test_heavy_frontdoor_prefers_matching_session_over_newer_unrelated_scope_session(
    tmp_path,
) -> None:
    repository = SqliteResearchSessionRepository(SQLiteStateStore(tmp_path / "state.db"))
    now = datetime.now(timezone.utc)
    repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-unrelated",
            provider="baidu-page",
            industry_instance_id="industry-1",
            work_context_id="ctx-1",
            owner_agent_id="industry-researcher-demo",
            supervisor_agent_id="main-brain",
            trigger_source="user-direct",
            goal="Track market close news for two stock symbols",
            status="completed",
            round_count=2,
            brief={
                "goal": "Track market close news for two stock symbols",
                "question": "What moved the chip sector today?",
            },
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
    )
    repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-pricing",
            provider="baidu-page",
            industry_instance_id="industry-1",
            work_context_id="ctx-1",
            owner_agent_id="industry-researcher-demo",
            supervisor_agent_id="main-brain",
            trigger_source="user-direct",
            goal="补齐竞品定价资料和证据来源",
            status="completed",
            round_count=2,
            brief={
                "goal": "补齐竞品定价资料和证据来源",
                "question": "官网和第三方价格口径分别是什么？",
            },
            created_at=now,
            updated_at=now.replace(second=max(now.second - 1, 0)),
            completed_at=now.replace(second=max(now.second - 1, 0)),
        )
    )
    heavy_service = _ReusableHeavyResearchService()
    service = SourceCollectionFrontdoorService(
        heavy_research_service=heavy_service,
        research_session_repository=repository,
    )

    result = service.run_source_collection_frontdoor(
        goal="补齐竞品定价资料和证据来源",
        question="继续补齐竞品定价资料和证据来源，并标注官网与第三方口径差异。",
        why_needed="当前 backlog 需要主脑基于正式证据决定下一步。",
        done_when="至少补齐官网定价页、核心能力页和一个第三方交叉来源。",
        trigger_source="main-brain-followup",
        owner_agent_id="industry-researcher-demo",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        collection_mode_hint="heavy",
        requested_sources=["search", "web_page"],
        metadata={"entry_surface": "test"},
    )

    assert heavy_service.start_calls == []
    assert heavy_service.resume_calls[0]["session_id"] == "research-session-pricing"
    assert result.session_id == "research-session-pricing"


def test_heavy_frontdoor_reuses_matching_session_for_strong_overlap_followup_without_marker(
    tmp_path,
) -> None:
    repository = SqliteResearchSessionRepository(SQLiteStateStore(tmp_path / "state.db"))
    now = datetime.now(timezone.utc)
    repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-ziwei",
            provider="baidu-page",
            industry_instance_id="industry-1",
            work_context_id="ctx-1",
            owner_agent_id="industry-researcher-demo",
            supervisor_agent_id="main-brain",
            trigger_source="user-direct",
            goal="Explain Zi Wei Dou Shu in one sentence.",
            status="completed",
            round_count=4,
            brief={
                "goal": "Explain Zi Wei Dou Shu in one sentence.",
                "question": "Clarify the four transformations in Zi Wei Dou Shu.",
            },
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
    )
    heavy_service = _ReusableHeavyResearchService()
    service = SourceCollectionFrontdoorService(
        heavy_research_service=heavy_service,
        research_session_repository=repository,
    )

    result = service.run_source_collection_frontdoor(
        goal="Explain Zi Wei Dou Shu in one sentence.",
        question="Now explain why accurate birth time matters and how a beginner should verify it.",
        why_needed="Keep the same research thread and continue the deeper clarification.",
        done_when="The birth-time dependency is clarified with practical verification steps.",
        trigger_source="main-brain-followup",
        owner_agent_id="industry-researcher-demo",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        collection_mode_hint="heavy",
        requested_sources=["search", "web_page"],
        metadata={"entry_surface": "test"},
    )

    assert heavy_service.start_calls == []
    assert heavy_service.resume_calls[0]["session_id"] == "research-session-ziwei"
    assert result.session_id == "research-session-ziwei"
