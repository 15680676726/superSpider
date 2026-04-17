# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from copaw.research import BaiduPageResearchService


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
                当前项目应先补齐商品库标签体系。
                行业通用做法是按选品、投放、转化、复购分层复盘。
                该回答暂无来源佐证。
              </div>
            </main>
            """,
        ]

    def __call__(self, **payload):
        if payload["action"] == "start":
            return {"ok": True, "session_id": payload.get("session_id", "research-browser")}
        if payload["action"] == "open":
            return {"ok": True, "url": payload.get("url")}
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
        goal="梳理电商平台入门知识结构",
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
        goal="梳理电商平台入门知识结构",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
        industry_instance_id="industry-1",
    )
    service.run_session(start_result.session.id)

    result = service.summarize_session(start_result.session.id)

    assert result.industry_document_id is not None
    assert "industry-1" in result.industry_document_id
    assert any(call["scope_type"] == "industry" for call in knowledge_service.calls)
