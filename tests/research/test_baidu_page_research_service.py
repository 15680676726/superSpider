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

    def list_research_sessions(self):
        return list(self.sessions.values())

    def upsert_research_round(self, round_record):
        self.rounds.setdefault(round_record.session_id, [])
        bucket = self.rounds[round_record.session_id]
        for index, existing in enumerate(bucket):
            if existing.id == round_record.id:
                bucket[index] = round_record
                break
        else:
            bucket.append(round_record)
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
    def __init__(self, evaluate_results: list[str]) -> None:
        self.evaluate_results = list(evaluate_results)
        self.calls: list[dict[str, object]] = []

    def __call__(self, **payload):
        self.calls.append(dict(payload))
        action = payload["action"]
        if action == "start":
            return {"ok": True, "session_id": payload.get("session_id", "research-browser")}
        if action == "open":
            return {"ok": True, "url": payload.get("url")}
        if action == "evaluate":
            html = self.evaluate_results.pop(0)
            return {"ok": True, "result": html}
        raise AssertionError(f"Unexpected browser action: {action}")


def _build_service(*, browser_runner: _FakeBrowserRunner) -> BaiduPageResearchService:
    return BaiduPageResearchService(
        research_session_repository=_FakeResearchRepository(),
        browser_action_runner=browser_runner,
        report_repository=_FakeReportRepository(),
    )


def test_research_service_creates_session_and_first_round() -> None:
    service = _build_service(
        browser_runner=_FakeBrowserRunner(
            evaluate_results=["<main><div class='answer'>占位答案</div></main>"],
        ),
    )

    result = service.start_session(
        goal="梳理电商平台入门知识结构",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    assert result.session.status == "queued"
    assert result.session.goal == "梳理电商平台入门知识结构"
    assert len(result.rounds) == 1
    assert result.rounds[0].round_index == 1


def test_research_service_marks_waiting_login_when_baidu_not_logged_in() -> None:
    service = _build_service(
        browser_runner=_FakeBrowserRunner(
            evaluate_results=["<main><button>登录</button></main>"],
        ),
    )
    start_result = service.start_session(
        goal="梳理电商平台入门知识结构",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    result = service.run_session(start_result.session.id)

    assert result.session.status == "waiting-login"
    assert result.stop_reason == "waiting-login"


def test_research_service_stops_after_two_rounds_without_new_findings() -> None:
    repeated_html = """
    <main>
      <div class="answer">行业常见框架包括选品、流量、转化、复购。</div>
    </main>
    """
    service = _build_service(
        browser_runner=_FakeBrowserRunner(
            evaluate_results=[repeated_html, repeated_html, repeated_html],
        ),
    )
    start_result = service.start_session(
        goal="梳理电商平台入门知识结构",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    result = service.run_session(start_result.session.id)

    assert result.session.status == "completed"
    assert result.stop_reason == "no-new-findings"
    assert len(result.rounds) >= 3
