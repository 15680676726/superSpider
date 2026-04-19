# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

from copaw.app.runtime_bootstrap_domains import SourceCollectionFrontdoorService
from copaw.evidence import EvidenceLedger
from copaw.state import ResearchSessionRecord, SQLiteStateStore
from copaw.state.repositories import SqliteResearchSessionRepository


class _UnusedHeavyResearchService:
    def start_session(self, **kwargs):
        raise AssertionError(f"heavy path should not be used: {kwargs}")


class _StoredReport:
    def __init__(self, report_id: str, metadata: dict[str, object], evidence_ids: list[str]):
        self.id = report_id
        self.metadata = metadata
        self.evidence_ids = evidence_ids


class _FakeReportRepository:
    def __init__(self) -> None:
        self.reports: dict[str, _StoredReport] = {}

    def upsert_report(self, report):
        stored = _StoredReport(
            report_id=report.id,
            metadata=dict(report.metadata),
            evidence_ids=list(report.evidence_ids),
        )
        self.reports[stored.id] = stored
        return report


class _FakeKnowledgeService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def ingest_research_session(self, *, session, rounds):
        self.calls.append(
            {
                "session_id": session.id,
                "round_ids": [round_record.id for round_record in rounds],
            }
        )
        return {
            "work_context_chunk_ids": ["chunk-ctx-1"],
            "industry_document_id": "memory:industry:industry-1",
            "source_refs": ["https://example.com/pricing"],
        }


class _FakeKnowledgeWritebackService:
    def __init__(self) -> None:
        self.build_calls: list[dict[str, object]] = []
        self.applied_changes: list[object] = []

    def build_research_session_writeback(self, *, session, rounds):
        change = {
            "session_id": session.id,
            "round_ids": [round_record.id for round_record in rounds],
        }
        self.build_calls.append(change)
        return change

    def summarize_change(self, change):
        return {
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "node_ids": ["node-1"],
            "relation_ids": ["relation-1"],
        }

    def apply_change(self, change):
        self.applied_changes.append(change)
        return self.summarize_change(change)


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


def test_light_frontdoor_writes_dedicated_evidence_and_formal_writeback_truth(
    tmp_path,
) -> None:
    repository = SqliteResearchSessionRepository(SQLiteStateStore(tmp_path / "state.db"))
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.sqlite3")
    report_repository = _FakeReportRepository()
    knowledge_service = _FakeKnowledgeService()
    knowledge_writeback_service = _FakeKnowledgeWritebackService()
    service = SourceCollectionFrontdoorService(
        heavy_research_service=_UnusedHeavyResearchService(),
        research_session_repository=repository,
        report_repository=report_repository,
        evidence_ledger=evidence_ledger,
        knowledge_service=knowledge_service,
        knowledge_writeback_service=knowledge_writeback_service,
    )

    result = service.run_source_collection_frontdoor(
        goal="查官网定价",
        question="官网定价是多少",
        why_needed="主脑要做价格对比",
        done_when="拿到官网价格和来源",
        trigger_source="agent-entry",
        owner_agent_id="writer-agent",
        supervisor_agent_id="main-brain",
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
    evidence_records = evidence_ledger.list_by_task(result.session_id)

    assert stored_session is not None
    assert stored_round.evidence_ids
    assert len(evidence_records) == 1
    assert evidence_records[0].metadata["research_session_id"] == result.session_id
    assert stored_round.sources[0]["evidence_id"] == evidence_records[0].id
    assert stored_round.findings[0]["summary"] == "基础套餐 299 元 / 月"
    assert stored_session.writeback_truth == {
        "status": "written",
        "scope_type": "work_context",
        "scope_id": "ctx-1",
        "report_id": stored_session.final_report_id,
        "work_context_chunk_ids": ["chunk-ctx-1"],
        "industry_document_id": "memory:industry:industry-1",
        "node_ids": ["node-1"],
        "relation_ids": ["relation-1"],
    }
    assert stored_session.conflicts == []
    assert knowledge_service.calls == [
        {
            "session_id": result.session_id,
            "round_ids": [stored_round.id],
        }
    ]
    assert knowledge_writeback_service.build_calls == [
        {
            "session_id": result.session_id,
            "round_ids": [stored_round.id],
        }
    ]
    assert knowledge_writeback_service.applied_changes == knowledge_writeback_service.build_calls
    assert result.final_report_id == stored_session.final_report_id


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


def test_heavy_frontdoor_main_brain_followup_reuses_only_completed_session_without_keyword_marker(
    tmp_path,
) -> None:
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
            round_count=3,
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
        goal="Need one more decision-ready research clarification",
        question="List the most worth-reading materials first.",
        why_needed="Main brain is continuing the same research thread.",
        done_when="One more clarification is enough for the next decision.",
        trigger_source="main-brain-followup",
        owner_agent_id="industry-researcher-demo",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        collection_mode_hint="heavy",
        requested_sources=["search", "web_page"],
        metadata={"entry_surface": "test"},
    )

    assert heavy_service.start_calls == []
    assert heavy_service.resume_calls[0]["session_id"] == "research-session-existing"
    assert result.session_id == "research-session-existing"


def test_heavy_frontdoor_main_brain_followup_falls_back_to_latest_completed_session_when_ambiguous(
    tmp_path,
) -> None:
    repository = SqliteResearchSessionRepository(SQLiteStateStore(tmp_path / "state.db"))
    now = datetime.now(timezone.utc)
    repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-older",
            provider="baidu-page",
            industry_instance_id="industry-1",
            work_context_id="ctx-1",
            owner_agent_id="industry-researcher-demo",
            supervisor_agent_id="main-brain",
            trigger_source="user-direct",
            goal="Track chip sector news",
            status="completed",
            round_count=2,
            brief={
                "goal": "Track chip sector news",
                "question": "What moved the chip sector today?",
            },
            created_at=now.replace(minute=max(now.minute - 1, 0)),
            updated_at=now.replace(minute=max(now.minute - 1, 0)),
            completed_at=now.replace(minute=max(now.minute - 1, 0)),
        )
    )
    repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-latest",
            provider="baidu-page",
            industry_instance_id="industry-1",
            work_context_id="ctx-1",
            owner_agent_id="industry-researcher-demo",
            supervisor_agent_id="main-brain",
            trigger_source="user-direct",
            goal="Research Zi Wei Dou Shu basics",
            status="completed",
            round_count=3,
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
        goal="Need one more decision-ready research clarification",
        question="List the most worth-reading materials first.",
        why_needed="Main brain is continuing the same research thread.",
        done_when="One more clarification is enough for the next decision.",
        trigger_source="main-brain-followup",
        owner_agent_id="industry-researcher-demo",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        collection_mode_hint="heavy",
        requested_sources=["search", "web_page"],
        metadata={"entry_surface": "test"},
    )

    assert heavy_service.start_calls == []
    assert heavy_service.resume_calls[0]["session_id"] == "research-session-latest"
    assert result.session_id == "research-session-latest"


def test_heavy_frontdoor_forces_reuse_of_active_waiting_login_session_in_same_scope(
    tmp_path,
) -> None:
    repository = SqliteResearchSessionRepository(SQLiteStateStore(tmp_path / "state.db"))
    now = datetime.now(timezone.utc)
    repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-waiting-login",
            provider="baidu-page",
            industry_instance_id="industry-1",
            work_context_id="ctx-1",
            owner_agent_id="industry-researcher-demo",
            supervisor_agent_id="main-brain",
            trigger_source="main-brain-followup",
            goal="Track market close news for two stock symbols",
            status="waiting-login",
            round_count=1,
            brief={
                "goal": "Track market close news for two stock symbols",
                "question": "What moved the chip sector today?",
            },
            created_at=now,
            updated_at=now,
        )
    )
    heavy_service = _ReusableHeavyResearchService()
    service = SourceCollectionFrontdoorService(
        heavy_research_service=heavy_service,
        research_session_repository=repository,
    )

    result = service.run_source_collection_frontdoor(
        goal="Research Zi Wei Dou Shu basics",
        question="Explain the twelve palaces for a beginner.",
        why_needed="keep the same active browser thread instead of opening a new one",
        done_when="one more clarification is enough",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        collection_mode_hint="heavy",
        requested_sources=["search", "web_page"],
        metadata={"entry_surface": "test"},
    )

    assert heavy_service.start_calls == []
    assert heavy_service.resume_calls[0]["session_id"] == "research-session-waiting-login"
    assert result.session_id == "research-session-waiting-login"


def test_heavy_frontdoor_prefers_explicit_continuation_session_id_over_newer_waiting_login_session(
    tmp_path,
) -> None:
    repository = SqliteResearchSessionRepository(SQLiteStateStore(tmp_path / "state.db"))
    now = datetime.now(timezone.utc)
    repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-original",
            provider="baidu-page",
            industry_instance_id="industry-1",
            work_context_id="ctx-1",
            owner_agent_id="industry-researcher-demo",
            supervisor_agent_id="main-brain",
            trigger_source="main-brain-followup",
            goal="补齐竞品定价资料和证据来源",
            status="waiting-login",
            round_count=2,
            brief={
                "goal": "补齐竞品定价资料和证据来源",
                "question": "继续补齐竞品定价资料和证据来源，并标注官网与第三方口径差异。",
            },
            created_at=now.replace(minute=max(now.minute - 1, 0)),
            updated_at=now.replace(minute=max(now.minute - 1, 0)),
        )
    )
    repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-newer",
            provider="baidu-page",
            industry_instance_id="industry-1",
            work_context_id="ctx-1",
            owner_agent_id="industry-researcher-demo",
            supervisor_agent_id="main-brain",
            trigger_source="main-brain-followup",
            goal="另一条同 scope 的研究线程",
            status="waiting-login",
            round_count=1,
            brief={
                "goal": "另一条同 scope 的研究线程",
                "question": "这条不该抢走原来的恢复链。",
            },
            created_at=now,
            updated_at=now,
        )
    )
    heavy_service = _ReusableHeavyResearchService()
    service = SourceCollectionFrontdoorService(
        heavy_research_service=heavy_service,
        research_session_repository=repository,
    )

    result = service.run_source_collection_frontdoor(
        goal="补齐竞品定价资料和证据来源",
        question="我登录好了，继续原来的研究。",
        why_needed="登录后要继续原来的正式研究会话。",
        done_when="沿原线程补齐证据。",
        trigger_source="main-brain-followup",
        owner_agent_id="industry-researcher-demo",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        collection_mode_hint="heavy",
        requested_sources=["search", "web_page"],
        preferred_session_id="research-session-original",
        metadata={"entry_surface": "test"},
    )

    assert heavy_service.start_calls == []
    assert heavy_service.resume_calls[0]["session_id"] == "research-session-original"
    assert result.session_id == "research-session-original"
