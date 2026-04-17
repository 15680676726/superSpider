# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.research import BaiduPageResearchService


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


class _FakeBrowserRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._html_queue = [
            """
            <main>
              <div class="answer">行业通用框架包括选品、投放与复盘。</div>
              <a href="https://example.com/guide">深挖指南</a>
              <a href="https://example.com/report.pdf">白皮书 PDF</a>
            </main>
            """,
            """
            <main>
              <div class="answer">行业通用框架补充了履约与客服协同。</div>
            </main>
            """,
        ]

    def __call__(self, **payload):
        self.calls.append(dict(payload))
        action = payload["action"]
        if action == "start":
            return {"ok": True, "session_id": payload.get("session_id", "research-browser")}
        if action == "open":
            return {"ok": True, "url": payload.get("url")}
        if action == "evaluate":
            return {"ok": True, "result": self._html_queue.pop(0)}
        raise AssertionError(f"Unexpected browser action: {action}")


def test_research_service_uses_browser_session_to_open_followup_link() -> None:
    browser_runner = _FakeBrowserRunner()
    service = BaiduPageResearchService(
        research_session_repository=_FakeResearchRepository(),
        browser_action_runner=browser_runner,
        browser_download_resolver=lambda **_: [],
    )
    start_result = service.start_session(
        goal="梳理电商平台入门知识结构",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    result = service.run_session(start_result.session.id)

    assert result.deepened_links[0]["url"] == "https://example.com/guide"
    assert sum(1 for item in browser_runner.calls if item["action"] == "open") >= 2


def test_research_service_records_downloaded_pdf_as_artifact() -> None:
    service = BaiduPageResearchService(
        research_session_repository=_FakeResearchRepository(),
        browser_action_runner=_FakeBrowserRunner(),
        browser_download_resolver=lambda **_: [
            {
                "page_id": "research-round-1",
                "path": "D:/tmp/report.pdf",
                "suggested_filename": "report.pdf",
                "status": "completed",
                "verified": True,
                "exists": True,
            },
        ],
    )
    start_result = service.start_session(
        goal="梳理电商平台入门知识结构",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    result = service.run_session(start_result.session.id)

    assert result.downloaded_artifacts
    assert result.downloaded_artifacts[0]["kind"] == "pdf"
    assert result.downloaded_artifacts[0]["path"].endswith("report.pdf")
