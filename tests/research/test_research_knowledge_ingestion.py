# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
import json

from copaw.research import BaiduPageResearchService
from copaw.state import ResearchSessionRecord, ResearchSessionRoundRecord, SQLiteStateStore
from copaw.state.repositories import SqliteResearchSessionRepository


@dataclass
class _StoredChunk:
    id: str
    document_id: str


@dataclass
class _StoredContext:
    id: str


class _FakeResearchRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, object] = {}
        self.rounds: dict[str, list[object]] = {}

    def upsert_research_session(self, session):
        self.sessions[session.id] = session
        return session

    def get_research_session(self, session_id: str):
        return self.sessions.get(session_id)

    def upsert_research_round(self, round_record):
        self.rounds.setdefault(round_record.session_id, []).append(round_record)
        return round_record

    def list_research_rounds(self, session_id: str):
        return list(self.rounds.get(session_id, []))


class _FakeKnowledgeService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def remember_fact(self, **payload):
        self.calls.append(dict(payload))
        scope_type = str(payload["scope_type"])
        scope_id = str(payload["scope_id"])
        title = str(payload["title"])
        return _StoredChunk(
            id=f"chunk-{len(self.calls)}",
            document_id=f"memory:{scope_type}:{scope_id}:{title}",
        )


class _FakeWorkContextService:
    def ensure_context(self, **_payload):
        return _StoredContext(id="work-context-1")


class _FakeBrowserRunner:
    def __init__(self) -> None:
        self._html_queue = [
            """
            <main>
              <div class="answer">
                Start with a product taxonomy before launch work.
                A reusable framework groups work into selection, acquisition, conversion, and repeat purchase.
                The first answer still needs stronger source support.
              </div>
            </main>
            """,
            """
            <main>
              <div class="answer">
                Normalize the taxonomy and campaign goal semantics before optimizing conversion and retention.
              </div>
            </main>
            """,
            """
            <main>
              <div class="answer">
                Verify the taxonomy against acquisition, conversion, and repeat-purchase evidence before rollout.
              </div>
            </main>
            """,
        ]

    def __call__(self, **payload):
        if payload["action"] == "start":
            return {"ok": True, "session_id": payload.get("session_id", "research-browser")}
        if payload["action"] == "open":
            return {"ok": True, "url": payload.get("url")}
        if payload["action"] == "wait_for":
            return {"ok": True, "message": f"Waited {payload.get('wait_time')}s"}
        if payload["action"] == "snapshot":
            return {
                "ok": True,
                "snapshot": '- textbox "Chat input" [ref=e1]',
                "refs": ["e1"],
                "url": str(payload.get("page_id") or ""),
            }
        if payload["action"] == "type":
            return {"ok": True, "message": f"Typed into {payload.get('ref') or payload.get('selector')}"}
        if payload["action"] == "evaluate":
            return {"ok": True, "result": self._html_queue.pop(0)}
        raise AssertionError(payload["action"])


def test_research_result_routes_project_specific_findings_to_work_context_memory() -> None:
    knowledge_service = _FakeKnowledgeService()
    service = BaiduPageResearchService(
        research_session_repository=_FakeResearchRepository(),
        browser_action_runner=_FakeBrowserRunner(),
        knowledge_service=knowledge_service,
        work_context_service=_FakeWorkContextService(),
    )
    start_result = service.start_session(
        goal="Organize an ecommerce research scaffold",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )
    service.run_session(start_result.session.id)

    result = service.summarize_session(start_result.session.id)

    assert result.work_context_chunk_ids
    assert any(call["scope_type"] == "work_context" for call in knowledge_service.calls)


def test_research_result_routes_stable_reusable_findings_to_industry_knowledge() -> None:
    knowledge_service = _FakeKnowledgeService()
    service = BaiduPageResearchService(
        research_session_repository=_FakeResearchRepository(),
        browser_action_runner=_FakeBrowserRunner(),
        knowledge_service=knowledge_service,
        work_context_service=_FakeWorkContextService(),
    )
    start_result = service.start_session(
        goal="Organize an ecommerce research scaffold",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
        industry_instance_id="industry-1",
    )
    service.run_session(start_result.session.id)

    result = service.summarize_session(start_result.session.id)

    assert result.industry_document_id is not None
    assert "industry-1" in result.industry_document_id
    assert any(call["scope_type"] == "industry" for call in knowledge_service.calls)


def test_research_repository_round_trips_session_brief_and_round_sources(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteResearchSessionRepository(store)

    session = ResearchSessionRecord(
        id="research-session-1",
        provider="baidu-page",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        owner_agent_id="industry-researcher-demo",
        supervisor_agent_id="main-brain",
        trigger_source="user-direct",
        goal="Map the ecommerce onboarding operating model",
        stable_findings=["Stable finding"],
        brief={
            "question": "What should the first operator playbook include?",
            "why_needed": "Need a reusable onboarding baseline.",
            "done_when": "We have the first reusable research summary.",
            "writeback_target": {
                "scope_type": "work_context",
                "scope_id": "ctx-1",
            },
        },
        metadata={"operator_note": "keep-this"},
    )
    round_record = ResearchSessionRoundRecord(
        id="research-session-1:round:1",
        session_id=session.id,
        round_index=1,
        question="What are the key onboarding steps?",
        new_findings=["Round-specific finding"],
        sources=[
            {
                "source_id": "source-1",
                "source_kind": "link",
                "collection_action": "read",
                "source_ref": "https://example.com/guide",
                "normalized_ref": "https://example.com/guide",
                "title": "Example onboarding guide",
                "snippet": "A reusable operating checklist.",
                "metadata": {"evidence_id": "evidence-1"},
            },
        ],
        metadata={"adapter_kind": "baidu-page"},
    )

    repository.upsert_research_session(session)
    repository.upsert_research_round(round_record)

    restored_session = repository.get_research_session(session.id)
    restored_rounds = repository.list_research_rounds(session_id=session.id)

    assert restored_session is not None
    assert restored_session.brief["question"] == session.brief["question"]
    assert restored_session.metadata["operator_note"] == "keep-this"
    assert len(restored_rounds) == 1
    assert restored_rounds[0].sources[0]["source_ref"] == "https://example.com/guide"
    assert restored_rounds[0].sources[0]["metadata"]["evidence_id"] == "evidence-1"
    assert restored_rounds[0].metadata["adapter_kind"] == "baidu-page"


def test_research_repository_hydrates_legacy_metadata_brief_and_collected_sources(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteResearchSessionRepository(store)

    session = ResearchSessionRecord(
        id="research-session-legacy-meta",
        provider="baidu-page",
        owner_agent_id="industry-researcher-demo",
        supervisor_agent_id="main-brain",
        trigger_source="user-direct",
        goal="Map the ecommerce onboarding operating model",
        metadata={
            "brief": {
                "question": "What should the first operator playbook include?",
                "why_needed": "Need a reusable onboarding baseline.",
                "done_when": "We have the first reusable research summary.",
            }
        },
    )
    round_record = ResearchSessionRoundRecord(
        id="research-session-legacy-meta:round:1",
        session_id=session.id,
        round_index=1,
        question="What are the key onboarding steps?",
        metadata={
            "collected_sources": [
                {
                    "source_id": "source-legacy-1",
                    "source_kind": "link",
                    "collection_action": "read",
                    "source_ref": "https://example.com/guide",
                    "normalized_ref": "https://example.com/guide",
                    "title": "Example onboarding guide",
                }
            ]
        },
    )

    repository.upsert_research_session(session)
    repository.upsert_research_round(round_record)

    restored_session = repository.get_research_session(session.id)
    restored_round = repository.list_research_rounds(session_id=session.id)[0]

    assert restored_session is not None
    assert restored_session.brief["question"] == "What should the first operator playbook include?"
    assert restored_round.sources[0]["source_ref"] == "https://example.com/guide"


def test_research_repository_persists_formal_projection_columns_for_source_collection_truth(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteResearchSessionRepository(store)

    session = ResearchSessionRecord(
        id="research-session-formal-columns",
        provider="source-collection",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        owner_agent_id="writer-agent",
        supervisor_agent_id="main-brain",
        trigger_source="agent-entry",
        goal="查官网定价",
        status="completed",
        stable_findings=["官网定价页显示基础套餐 299 元 / 月。"],
        open_questions=["还缺官网截图归档。"],
        brief={
            "goal": "查官网定价",
            "question": "官网定价是多少",
            "why_needed": "主脑要做价格对比",
            "done_when": "拿到官网价格和来源",
            "collection_mode_hint": "light",
            "requested_sources": ["web_page"],
        },
        conflicts=["第三方博客把旧价格写成了 199 元。"],
        writeback_truth={
            "status": "written",
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "report_id": "report-1",
        },
    )
    round_record = ResearchSessionRoundRecord(
        id="research-session-formal-columns:round:1",
        session_id=session.id,
        round_index=1,
        question="官网定价是多少",
        response_summary="官网定价页显示基础套餐 299 元 / 月。",
        new_findings=["官网定价页显示基础套餐 299 元 / 月。"],
        sources=[
            {
                "source_id": "source-1",
                "source_kind": "web_page",
                "collection_action": "read",
                "source_ref": "https://example.com/pricing",
                "normalized_ref": "https://example.com/pricing",
                "title": "官网定价页",
                "snippet": "基础套餐 299 元 / 月",
                "evidence_id": "evidence-1",
            },
        ],
        findings=[
            {
                "finding_id": "finding-1",
                "finding_type": "pricing",
                "summary": "官网定价页显示基础套餐 299 元 / 月。",
                "supporting_source_ids": ["source-1"],
                "supporting_evidence_ids": ["evidence-1"],
            }
        ],
        conflicts=["第三方博客把旧价格写成了 199 元。"],
        gaps=["还缺官网截图归档。"],
        writeback_truth={
            "status": "written",
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "report_id": "report-1",
        },
    )

    repository.upsert_research_session(session)
    repository.upsert_research_round(round_record)

    with store.connection() as conn:
        session_row = conn.execute(
            """
            SELECT brief_json, conflicts_json, writeback_truth_json
            FROM research_sessions
            WHERE id = ?
            """,
            (session.id,),
        ).fetchone()
        round_row = conn.execute(
            """
            SELECT sources_json, findings_json, conflicts_json, gaps_json, writeback_truth_json
            FROM research_session_rounds
            WHERE id = ?
            """,
            (round_record.id,),
        ).fetchone()

    assert session_row is not None
    assert session_row["brief_json"] is not None
    assert json.loads(session_row["brief_json"])["question"] == "官网定价是多少"
    assert json.loads(session_row["conflicts_json"]) == ["第三方博客把旧价格写成了 199 元。"]
    assert json.loads(session_row["writeback_truth_json"])["status"] == "written"

    assert round_row is not None
    assert json.loads(round_row["sources_json"])[0]["source_ref"] == "https://example.com/pricing"
    assert json.loads(round_row["findings_json"])[0]["summary"] == "官网定价页显示基础套餐 299 元 / 月。"
    assert json.loads(round_row["conflicts_json"]) == ["第三方博客把旧价格写成了 199 元。"]
    assert json.loads(round_row["gaps_json"]) == ["还缺官网截图归档。"]
    assert json.loads(round_row["writeback_truth_json"])["report_id"] == "report-1"
