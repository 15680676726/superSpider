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
    def __init__(
        self,
        evaluate_results: list[object],
        *,
        snapshot_results: list[object] | None = None,
    ) -> None:
        self.evaluate_results = list(evaluate_results)
        self.snapshot_results = list(snapshot_results or [])
        self.calls: list[dict[str, object]] = []

    def __call__(self, **payload):
        self.calls.append(dict(payload))
        action = payload["action"]
        if action == "start":
            return {"ok": True, "session_id": payload.get("session_id", "research-browser")}
        if action == "open":
            return {"ok": True, "url": payload.get("url")}
        if action == "wait_for":
            return {"ok": True, "message": f"Waited {payload.get('wait_time')}s"}
        if action == "snapshot":
            if self.snapshot_results:
                result = self.snapshot_results.pop(0)
            else:
                result = {
                    "ok": True,
                    "snapshot": '- textbox "Chat input" [ref=e1]',
                    "refs": ["e1"],
                    "url": "https://chat.baidu.com/search",
                }
            return dict(result)
        if action == "type":
            return {"ok": True, "message": f"Typed into {payload.get('ref') or payload.get('selector')}"}
        if action == "evaluate":
            result = self.evaluate_results.pop(0)
            return {"ok": True, "result": result}
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


def test_research_service_completes_when_snapshot_only_contains_stable_answer_text() -> None:
    repeated_snapshot = {
        "html": "<main></main>",
        "bodyText": """
        开启新对话
        知识库
        对话历史
        The baseline execution loop remains stable across retries.
        内容由AI生成，仅供参考查看使用规则
        """,
    }
    service = _build_service(
        browser_runner=_FakeBrowserRunner(
            evaluate_results=[repeated_snapshot, repeated_snapshot, repeated_snapshot],
        ),
    )
    start_result = service.start_session(
        goal="梳理电商平台入门知识结构",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    result = service.run_session(start_result.session.id)

    assert result.session.status == "completed"
    assert result.stop_reason in {"followup-complete", "no-new-findings", "enough-findings"}
    assert len(result.rounds) >= 1


def test_research_service_starts_browser_with_persisted_login_state_by_default() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=["<main><button>login</button></main>"],
    )
    service = _build_service(browser_runner=browser_runner)
    start_result = service.start_session(
        goal="research browser continuity",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    service.run_session(start_result.session.id)

    start_call = next(call for call in browser_runner.calls if call["action"] == "start")
    assert start_call["persist_login_state"] is True
    assert str(start_call["storage_state_path"]).endswith(
        "state\\research_browser_storage\\industry-researcher-demo.json",
    )


def test_research_service_uses_explicit_login_state_override_from_metadata() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=["<main><button>login</button></main>"],
    )
    service = _build_service(browser_runner=browser_runner)
    start_result = service.start_session(
        goal="custom browser continuity",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
        metadata={
            "browser_session": {
                "persist_login_state": False,
                "storage_state_path": "D:/tmp/custom-research-storage.json",
            },
        },
    )

    service.run_session(start_result.session.id)

    start_call = next(call for call in browser_runner.calls if call["action"] == "start")
    assert start_call["persist_login_state"] is False
    assert start_call["storage_state_path"] == "D:/tmp/custom-research-storage.json"


def test_research_service_queries_baidu_with_round_question_and_extracts_body_text_answer() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=[
            {
                "html": "<main><a href='https://example.com/guide'>Guide</a></main>",
                "bodyText": """
                开启新对话
                知识库
                对话历史
                What is Zi Wei Dou Shu? Give 3 beginner points.
                全球搜检索32篇资料
                1.
                Guide - example.com

                Zi Wei Dou Shu is a traditional Chinese astrology system that maps stars across twelve palaces to interpret life patterns.
                Three beginner points:
                Learn the twelve palaces first.
                Study the main stars and four transformations.
                Use an accurate birth time.

                内容由AI生成，仅供参考查看使用规则
                """,
            },
            {
                "html": "<main><a href='https://example.com/guide-2'>Guide 2</a></main>",
                "bodyText": """
                Follow up
                Guide 2 - example.com

                Common misunderstanding:
                It is not fortune telling based on one single star.
                Useful source hints:
                Compare a basic twelve-palace primer.
                Cross-check star system references.
                Validate the birth time assumption.
                """,
            },
        ],
    )
    service = _build_service(browser_runner=browser_runner)
    start_result = service.start_session(
        goal="What is Zi Wei Dou Shu? Give 3 beginner points.",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    result = service.run_session(start_result.session.id)

    open_calls = [call for call in browser_runner.calls if call["action"] == "open"]
    type_calls = [call for call in browser_runner.calls if call["action"] == "type"]
    assert len(open_calls) == 1
    assert str(open_calls[0]["url"]) == "https://chat.baidu.com/search"
    assert len(type_calls) == 2
    assert type_calls[0]["page_id"] == type_calls[1]["page_id"]
    assert result.session.status == "completed"
    assert result.stop_reason in {"followup-complete", "completed"}
    assert len(result.rounds) == 2
    assert "traditional Chinese astrology system" in result.session.stable_findings[0]


def test_research_service_runs_followup_round_after_first_answer() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=[
            {
                "html": "<main><a href='https://example.com/source-1'>Source 1</a></main>",
                "bodyText": """
                开启新对话
                知识库
                对话历史
                What is Zi Wei Dou Shu? Give 3 beginner points.
                全球搜检索32篇资料
                1.
                Source 1 - example.com

                Zi Wei Dou Shu is a traditional Chinese astrology system used to read life patterns.
                内容由AI生成，仅供参考查看使用规则
                """,
            },
            {
                "html": "<main><a href='https://example.com/source-2'>Source 2</a></main>",
                "bodyText": """
                开启新对话
                知识库
                对话历史
                Follow up
                全球搜检索16篇资料
                1.
                Source 2 - example.com

                Three beginner points:
                Learn the twelve palaces.
                Study the main stars.
                Use an accurate birth time.
                内容由AI生成，仅供参考查看使用规则
                """,
            },
        ],
    )
    service = _build_service(browser_runner=browser_runner)
    start_result = service.start_session(
        goal="What is Zi Wei Dou Shu? Give 3 beginner points.",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    result = service.run_session(start_result.session.id)

    open_calls = [call for call in browser_runner.calls if call["action"] == "open"]
    type_calls = [call for call in browser_runner.calls if call["action"] == "type"]
    assert len(open_calls) == 1
    assert len(type_calls) == 2
    assert type_calls[0]["page_id"] == type_calls[1]["page_id"]
    assert result.stop_reason == "followup-complete"
    assert len(result.rounds) == 2
    second_round = result.rounds[-1]
    assert second_round.round_index == 2
    assert "follow up" in second_round.question.lower()
    assert any("Learn the twelve palaces" in item for item in result.session.stable_findings)
