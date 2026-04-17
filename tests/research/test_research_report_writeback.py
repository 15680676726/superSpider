# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from copaw.research import BaiduPageResearchService


@dataclass
class _StoredReport:
    id: str
    metadata: dict[str, object]


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


class _FakeReportRepository:
    def __init__(self) -> None:
        self.reports: dict[str, _StoredReport] = {}

    def upsert_report(self, report):
        stored = _StoredReport(id=report.id, metadata=dict(report.metadata))
        self.reports[stored.id] = stored
        return report

    def get_report(self, report_id: str):
        return self.reports.get(report_id)


class _FakeBrowserRunner:
    def __init__(self) -> None:
        self._html_queue = [
            """
            <main>
              <div class="answer">The framework includes selection, delivery, and review loops.</div>
              <a href="https://example.com/guide">Deep guide</a>
            </main>
            """,
            """
            <main>
              <div class="answer">
                Add audience segmentation, key metrics, and one common misunderstanding.
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


def test_completed_research_session_generates_researcher_report() -> None:
    report_repo = _FakeReportRepository()
    service = BaiduPageResearchService(
        research_session_repository=_FakeResearchRepository(),
        browser_action_runner=_FakeBrowserRunner(),
        report_repository=report_repo,
    )
    start_result = service.start_session(
        goal="Organize an ecommerce research scaffold",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )
    service.run_session(start_result.session.id)

    result = service.summarize_session(start_result.session.id)

    assert result.final_report_id is not None
    assert report_repo.get_report(result.final_report_id) is not None


def test_research_report_includes_question_excerpt_links_and_provider() -> None:
    report_repo = _FakeReportRepository()
    service = BaiduPageResearchService(
        research_session_repository=_FakeResearchRepository(),
        browser_action_runner=_FakeBrowserRunner(),
        report_repository=report_repo,
    )
    start_result = service.start_session(
        goal="Organize an ecommerce research scaffold",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )
    service.run_session(start_result.session.id)

    result = service.summarize_session(start_result.session.id)
    report = report_repo.get_report(result.final_report_id)

    assert report is not None
    assert report.metadata["provider"] == "baidu-page"
    assert report.metadata["citations"]
    assert report.metadata["question_excerpt"].startswith("Organize an ecommerce")
