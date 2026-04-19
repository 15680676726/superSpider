# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
import pytest

import copaw.research.baidu_page_research_service as baidu_page_research_service_module
from copaw.environments.surface_execution.browser import (
    BrowserExecutionLoopResult,
    BrowserExecutionResult,
    BrowserObservation,
    BrowserTargetCandidate,
)
from copaw.environments.surface_execution.browser.resolver import resolve_browser_target
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
        page_probe_results: list[object] | None = None,
        deep_think_results: list[object] | None = None,
        input_readback_results: list[object] | None = None,
    ) -> None:
        self.evaluate_results = list(evaluate_results)
        self.snapshot_results = list(snapshot_results or [])
        self.page_probe_results = list(page_probe_results or [])
        self.deep_think_results = list(deep_think_results or [])
        self.input_readback_results = list(input_readback_results or [])
        self.calls: list[dict[str, object]] = []
        self.opened_pages: set[tuple[str, str]] = set()
        self.typed_text_by_page: dict[tuple[str, str], str] = {}
        self.toggle_enabled_by_selector: dict[str, bool] = {}

    def __call__(self, **payload):
        self.calls.append(dict(payload))
        action = payload["action"]
        if action == "start":
            return {"ok": True, "session_id": payload.get("session_id", "research-browser")}
        if action == "open":
            self.opened_pages.add(
                (
                    str(payload.get("session_id") or "").strip(),
                    str(payload.get("page_id") or "").strip(),
                )
            )
            return {"ok": True, "url": payload.get("url")}
        if action == "wait_for":
            return {"ok": True, "message": f"Waited {payload.get('wait_time')}s"}
        if action == "snapshot":
            if self.snapshot_results:
                result = self.snapshot_results.pop(0)
            else:
                page_key = (
                    str(payload.get("session_id") or "").strip(),
                    str(payload.get("page_id") or "").strip(),
                )
                if page_key not in self.opened_pages:
                    return {"ok": False, "error": f"Page '{page_key[1]}' not found"}
                result = {
                    "ok": True,
                    "snapshot": '- textbox "Chat input" [ref=e1]',
                    "refs": ["e1"],
                    "url": "https://chat.baidu.com/search",
                }
            return dict(result)
        if action == "type":
            page_key = (
                str(payload.get("session_id") or "").strip(),
                str(payload.get("page_id") or "").strip(),
            )
            self.typed_text_by_page[page_key] = str(payload.get("text") or "")
            return {"ok": True, "message": f"Typed into {payload.get('ref') or payload.get('selector')}"}
        if action == "click":
            selector = str(payload.get("selector") or "")
            if selector:
                self.toggle_enabled_by_selector[selector] = True
            return {"ok": True, "message": f"Clicked {payload.get('ref') or payload.get('selector')}"}
        if action == "press_key":
            return {"ok": True, "message": f"Pressed {payload.get('key')}"}
        if action == "evaluate":
            code = str(payload.get("code") or "")
            if "data-copaw-deep-think" in code or "深度思考" in code:
                if self.deep_think_results:
                    result = self.deep_think_results.pop(0)
                    selector = str(result.get("selector") or "")
                    if selector:
                        self.toggle_enabled_by_selector[selector] = bool(result.get("enabled"))
                else:
                    selector = "[data-copaw-deep-think='1']"
                    result = {
                        "available": selector in self.toggle_enabled_by_selector,
                        "enabled": self.toggle_enabled_by_selector.get(selector, False),
                        "selector": selector if selector in self.toggle_enabled_by_selector else "",
                        "label": "Deep Think" if selector in self.toggle_enabled_by_selector else "",
                    }
                return {"ok": True, "result": result}
            if "#chat-textarea" in code:
                if self.input_readback_results:
                    result = self.input_readback_results.pop(0)
                else:
                    page_key = (
                        str(payload.get("session_id") or "").strip(),
                        str(payload.get("page_id") or "").strip(),
                    )
                    observed = self.typed_text_by_page.get(page_key, "")
                    result = {
                        "text": observed,
                        "normalized_text": observed,
                    }
                return {"ok": True, "result": result}
            if "bodyText:" in code and "href:" in code and "title:" in code and "html:" not in code:
                if self.page_probe_results:
                    result = self.page_probe_results.pop(0)
                    if isinstance(result, dict):
                        normalized_body_text = str(result.get("bodyText") or result.get("body_text") or "")
                        if "?" in normalized_body_text and "href" in result:
                            result = {
                                **result,
                                "bodyText": "login required\nsign in to continue using baidu chat",
                            }
                else:
                    result = {
                        "bodyText": "",
                        "href": "https://chat.baidu.com/search",
                        "title": "Baidu Chat",
                    }
                return {"ok": True, "result": result}
            result = self.evaluate_results.pop(0)
            return {"ok": True, "result": result}
        raise AssertionError(f"Unexpected browser action: {action}")


class _SplitReadbackBrowserRunner(_FakeBrowserRunner):
    def __init__(self) -> None:
        super().__init__(
            evaluate_results=[
                {
                    "html": "<main></main>",
                    "bodyText": "ordinary page without account prompt",
                    "href": "https://chat.baidu.com/search",
                    "title": "Baidu Chat",
                }
            ],
            snapshot_results=[
                {
                    "ok": True,
                    "snapshot": '- textbox "Ask anything" [ref=e1]',
                    "refs": ["e1"],
                    "url": "https://chat.baidu.com/search",
                },
                {
                    "ok": True,
                    "snapshot": '- textbox "Ask anything" [ref=e1]',
                    "refs": ["e1"],
                    "url": "https://chat.baidu.com/search",
                }
            ],
        )

    def __call__(self, **payload):
        if payload.get("action") == "snapshot" and not self.snapshot_results:
            return {
                "ok": True,
                "snapshot": '- textbox "Ask anything" [ref=e1]',
                "refs": ["e1"],
                "url": "https://chat.baidu.com/search",
            }
        if payload.get("action") == "evaluate":
            code = str(payload.get("code") or "")
            if "data-copaw-deep-think" in code:
                return {
                    "ok": True,
                    "result": {
                        "available": False,
                        "enabled": False,
                        "selector": "",
                        "label": "",
                    },
                }
            if "#chat-textarea" in code:
                page_key = (
                    str(payload.get("session_id") or "").strip(),
                    str(payload.get("page_id") or "").strip(),
                )
                observed = self.typed_text_by_page.get(page_key, "")
                return {
                    "ok": True,
                    "result": {
                        "text": observed,
                        "normalized_text": observed,
                    },
                }
        return super().__call__(**payload)


class _ScopedDeepThinkBrowserRunner(_FakeBrowserRunner):
    def __init__(self) -> None:
        super().__init__(evaluate_results=[])

    def __call__(self, **payload):
        if payload.get("action") == "evaluate":
            code = str(payload.get("code") or "")
            if "button, [role=\"button\"], label, span, div" in code:
                return {
                    "ok": True,
                    "result": {
                        "available": True,
                        "enabled": False,
                        "selector": "[data-copaw-deep-think='1']",
                        "label": (
                            "Baidu Chat page container Deep Think Ask anything "
                            "recent threads footer help center"
                        ),
                    },
                }
            if "#chat-textarea" in code and "aria-pressed" in code:
                return {
                    "ok": True,
                    "result": {
                        "available": True,
                        "enabled": True,
                        "selector": "[data-copaw-deep-think='1']",
                        "label": "Deep Think",
                    },
                }
            if "data-copaw-deep-think" in code and "aria-pressed" in code:
                return {
                    "ok": True,
                    "result": {
                        "available": True,
                        "enabled": True,
                        "selector": "[data-copaw-deep-think='1']",
                        "label": "Deep Think",
                    },
                }
        return super().__call__(**payload)


def _build_service(*, browser_runner: _FakeBrowserRunner) -> BaiduPageResearchService:
    return BaiduPageResearchService(
        research_session_repository=_FakeResearchRepository(),
        browser_action_runner=browser_runner,
        report_repository=_FakeReportRepository(),
    )


def test_research_service_creates_session_and_first_round() -> None:
    service = _build_service(
        browser_runner=_FakeBrowserRunner(
            page_probe_results=[
                {
                    "bodyText": "请登录后继续\n当前页面需要登录才能继续使用百度对话。",
                    "href": "https://chat.baidu.com/search",
                    "title": "Baidu Chat",
                }
            ],
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


def test_research_service_promotes_brief_metadata_into_formal_session_projection() -> None:
    repository = _FakeResearchRepository()
    service = BaiduPageResearchService(
        research_session_repository=repository,
        browser_action_runner=_FakeBrowserRunner(
            evaluate_results=["<main><div class='answer'>占位答案</div></main>"],
        ),
    )

    result = service.start_session(
        goal="梳理电商平台入门知识结构",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
        metadata={
            "brief": {
                "goal": "补齐竞品定价和能力差异",
                "question": "继续核对官网定价和核心能力页",
                "why_needed": "主脑要决定下一步策略。",
                "done_when": "至少拿到两条官方来源。",
                "requested_sources": ["search", "web_page"],
                "collection_mode_hint": "heavy",
            }
        },
    )

    stored_session = repository.get_research_session(result.session.id)

    assert stored_session is not None
    assert stored_session.brief["question"] == "继续核对官网定价和核心能力页"
    assert result.rounds[0].question == "继续核对官网定价和核心能力页"


def test_research_service_exposes_shared_adapter_result_for_latest_round() -> None:
    snapshot = {
        "html": "<main><a href='https://example.com/guide'>Guide</a></main>",
        "bodyText": (
            "Explain Zi Wei Dou Shu in one sentence.\n"
            "Zi Wei Dou Shu is a traditional Chinese astrology system.\n"
        ),
        "href": "https://chat.baidu.com/search",
        "title": "Baidu Chat",
    }
    service = _build_service(
        browser_runner=_FakeBrowserRunner(
            evaluate_results=[dict(snapshot) for _ in range(12)],
        ),
    )
    start_result = service.start_session(
        goal="Explain Zi Wei Dou Shu in one sentence.",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )
    service.run_session(start_result.session.id)

    adapter_result = service.collect_via_baidu_page(start_result.session.id)

    assert adapter_result.adapter_kind == "baidu_page"
    assert adapter_result.collection_action == "interact"
    assert adapter_result.status == "succeeded"
    assert adapter_result.findings[0].summary.startswith("Zi Wei Dou Shu is")
    assert adapter_result.collected_sources[0].source_ref == "https://example.com/guide"


def test_research_service_marks_waiting_login_when_baidu_not_logged_in() -> None:
    service = _build_service(
        browser_runner=_FakeBrowserRunner(
            page_probe_results=[
                {
                    "bodyText": "请登录后继续\n当前页面需要登录才能继续使用百度对话。",
                    "href": "https://chat.baidu.com/search",
                    "title": "Baidu Chat",
                }
            ],
            evaluate_results=["<main><button>登录</button></main>"],
        ),
    )
    start_result = service.start_session(
        goal="梳理电商平台入门知识结构",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    result = service.run_session(start_result.session.id)
    browser_runner = service._browser_action_runner
    type_calls = [call for call in browser_runner.calls if call["action"] == "type"]
    press_calls = [call for call in browser_runner.calls if call["action"] == "press_key"]

    assert result.session.status == "waiting-login"
    assert result.stop_reason == "waiting-login"
    assert type_calls == []
    assert press_calls == []


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
            {
                "html": "<main><a href='https://example.com/guide-3'>Guide 3</a></main>",
                "bodyText": """
                Continue researching
                Guide 3 - example.com

                The most important misconception is treating one star as the whole reading.
                Always cross-check the palace structure before drawing conclusions.
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
    assert result.stop_reason == "followup-complete"
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


def test_research_service_persists_provider_sources_into_round_projection() -> None:
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
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
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

                Learn the twelve palaces first.
                Study the main stars.
                内容由AI生成，仅供参考查看使用规则
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
        ],
    )
    repository = _FakeResearchRepository()
    service = BaiduPageResearchService(
        research_session_repository=repository,
        browser_action_runner=browser_runner,
        report_repository=_FakeReportRepository(),
    )
    start_result = service.start_session(
        goal="What is Zi Wei Dou Shu? Give 3 beginner points.",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    result = service.run_session(start_result.session.id)

    first_round = result.rounds[0]
    assert first_round.sources
    assert first_round.sources[0]["source_ref"] == "https://example.com/source-1"
    assert first_round.metadata["findings"][0]["summary"].startswith("Zi Wei Dou Shu is")


def test_research_service_exposes_provider_facing_round_collection_entry() -> None:
    service = _build_service(
        browser_runner=_FakeBrowserRunner(
            evaluate_results=[],
        ),
    )
    snapshot = {
        "html": "<main><a href='https://example.com/guide'>Guide</a></main>",
        "bodyText": """
        What is Zi Wei Dou Shu?
        Zi Wei Dou Shu is a traditional Chinese astrology system that maps stars across twelve palaces.
        """,
        "href": "https://chat.baidu.com/search",
        "title": "Baidu Chat",
    }

    result = service.collect_provider_round_result(
        snapshot=snapshot,
        current_url=BaiduPageResearchService.BAIDU_CHAT_URL,
    )

    assert result.login_state == "ready"
    assert result.adapter_result is not None
    assert result.adapter_result.collection_action == "interact"
    assert result.adapter_result.status == "succeeded"
    assert result.adapter_result.findings[0].summary.startswith("Zi Wei Dou Shu is")


def test_research_service_can_continue_initial_brief_beyond_two_rounds() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=[
            {
                "html": "<main><a href='https://example.com/source-1'>Source 1</a></main>",
                "bodyText": """
                What is Zi Wei Dou Shu?
                Zi Wei Dou Shu is a traditional Chinese astrology system.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main><a href='https://example.com/source-2'>Source 2</a></main>",
                "bodyText": """
                Follow up
                Learn the twelve palaces first.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main><a href='https://example.com/source-3'>Source 3</a></main>",
                "bodyText": """
                Continue researching
                Study the main stars and four transformations.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
        ],
    )
    service = _build_service(browser_runner=browser_runner)
    start_result = service.start_session(
        goal="What is Zi Wei Dou Shu?",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    result = service.run_session(start_result.session.id)

    assert result.session.status == "completed"
    assert len(result.rounds) >= 3
    assert result.stop_reason == "followup-complete"


def test_research_service_reuses_existing_chat_page_when_running_same_session_again() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=[
            {
                "html": "<main><a href='https://example.com/source-1'>Source 1</a></main>",
                "bodyText": """
                What is Zi Wei Dou Shu?
                Zi Wei Dou Shu is a traditional Chinese astrology system.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main><a href='https://example.com/source-2'>Source 2</a></main>",
                "bodyText": """
                Follow up
                Learn the twelve palaces first.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main><a href='https://example.com/source-3'>Source 3</a></main>",
                "bodyText": """
                Resume the same thread
                Study the main stars.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main><a href='https://example.com/source-4'>Source 4</a></main>",
                "bodyText": """
                Resume the same thread again
                Clarify the four transformations.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
        ],
        snapshot_results=[
            {"ok": False, "error": "Page 'missing' not found"},
        ],
    )
    service = _build_service(browser_runner=browser_runner)
    start_result = service.start_session(
        goal="What is Zi Wei Dou Shu?",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    service.run_session(start_result.session.id)
    service.run_session(start_result.session.id)

    open_calls = [call for call in browser_runner.calls if call["action"] == "open"]
    assert len(open_calls) == 1


def test_research_service_does_not_stop_resume_followup_on_repeated_old_answer() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=[
            {
                "html": "<main><a href='https://example.com/source-1'>Source 1</a></main>",
                "bodyText": """
                What is Zi Wei Dou Shu?
                Zi Wei Dou Shu is a traditional Chinese astrology system used to read life patterns.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main><a href='https://example.com/source-2'>Source 2</a></main>",
                "bodyText": """
                Follow up
                Learn the twelve palaces first.
                Study the main stars.
                Use an accurate birth time.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main><a href='https://example.com/source-3'>Source 3</a></main>",
                "bodyText": """
                Resume same thread
                Zi Wei Dou Shu is a traditional Chinese astrology system used to read life patterns.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main><a href='https://example.com/source-4'>Source 4</a></main>",
                "bodyText": """
                Continue same thread
                The four transformations are Hua Lu, Hua Quan, Hua Ke, and Hua Ji.
                They mark gain, authority, reputation, and obstruction in the chart.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
        ],
    )
    service = _build_service(browser_runner=browser_runner)
    start_result = service.start_session(
        goal="What is Zi Wei Dou Shu?",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    service.run_session(start_result.session.id)
    service.resume_session(
        session_id=start_result.session.id,
        question="Clarify the four transformations in Zi Wei Dou Shu.",
    )
    result = service.run_session(start_result.session.id)

    type_calls = [call for call in browser_runner.calls if call["action"] == "type"]
    assert result.stop_reason == "followup-complete"
    assert len(result.rounds) == 4
    assert len(type_calls) == 4
    assert "four transformations" in result.rounds[-1].question.lower()
    assert any("four transformations" in item.lower() for item in result.session.stable_findings)


def test_research_service_allows_later_resume_followups_after_total_round_count_grows() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=[
            {
                "html": "<main><a href='https://example.com/source-1'>Source 1</a></main>",
                "bodyText": """
                What is Zi Wei Dou Shu?
                Zi Wei Dou Shu is a traditional Chinese astrology system used to read life patterns.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main><a href='https://example.com/source-2'>Source 2</a></main>",
                "bodyText": """
                Follow up
                Learn the twelve palaces first.
                Study the main stars.
                Use an accurate birth time.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main><a href='https://example.com/source-3'>Source 3</a></main>",
                "bodyText": """
                Resume same thread
                Zi Wei Dou Shu is a traditional Chinese astrology system used to read life patterns.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main><a href='https://example.com/source-4'>Source 4</a></main>",
                "bodyText": """
                Continue same thread
                The four transformations are Hua Lu, Hua Quan, Hua Ke, and Hua Ji.
                They mark gain, authority, reputation, and obstruction in the chart.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main><a href='https://example.com/source-5'>Source 5</a></main>",
                "bodyText": """
                Retry
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main><a href='https://example.com/source-6'>Source 6</a></main>",
                "bodyText": """
                Continue same thread again
                Accurate birth time changes the rising palace and can shift key palace-star placements.
                Beginners should verify the legal birth certificate time and ask family for correction notes.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
        ],
    )
    service = _build_service(browser_runner=browser_runner)
    start_result = service.start_session(
        goal="What is Zi Wei Dou Shu?",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    service.run_session(start_result.session.id)
    service.resume_session(
        session_id=start_result.session.id,
        question="Clarify the four transformations in Zi Wei Dou Shu.",
    )
    service.run_session(start_result.session.id)
    service.resume_session(
        session_id=start_result.session.id,
        question="Explain why accurate birth time matters and how a beginner should verify it.",
    )
    result = service.run_session(start_result.session.id)

    assert result.stop_reason == "followup-complete"
    assert len(result.rounds) == 6
    assert "birth time" in result.rounds[-1].question.lower()
    assert any("accurate birth time" in item.lower() for item in result.session.stable_findings)


def test_submit_chat_question_enables_baidu_deep_think_and_returns_readback_metadata() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=[],
        deep_think_results=[
            {
                "available": True,
                "enabled": False,
                "selector": "[data-copaw-deep-think='1']",
                "label": "深度思考",
            },
            {
                "available": True,
                "enabled": True,
                "selector": "[data-copaw-deep-think='1']",
                "label": "深度思考",
            },
        ],
        input_readback_results=[
            {
                "text": "梳理紫微斗数核心术语和一个常见误解",
                "normalized_text": "梳理紫微斗数核心术语和一个常见误解",
            },
        ],
    )
    service = _build_service(browser_runner=browser_runner)
    service._ensure_chat_page(session_id="research-browser", page_id="chat-page")

    submission = service._submit_chat_question(
        session_id="research-browser",
        page_id="chat-page",
        question="梳理紫微斗数核心术语和一个常见误解",
    )

    click_calls = [call for call in browser_runner.calls if call["action"] == "click"]
    type_calls = [call for call in browser_runner.calls if call["action"] == "type"]
    press_key_calls = [call for call in browser_runner.calls if call["action"] == "press_key"]
    assert click_calls == [
        {
            "action": "click",
            "session_id": "research-browser",
            "page_id": "chat-page",
            "selector": "[data-copaw-deep-think='1']",
        }
    ]
    assert type_calls == [
        {
            "action": "type",
            "session_id": "research-browser",
            "page_id": "chat-page",
            "text": "梳理紫微斗数核心术语和一个常见误解",
            "submit": False,
            "ref": "e1",
            "selector": "",
        }
    ]
    assert press_key_calls == [
        {
            "action": "press_key",
            "session_id": "research-browser",
            "page_id": "chat-page",
            "key": "Enter",
        }
    ]
    assert submission["deep_think"] == {
        "requested": True,
        "available": True,
        "enabled_before": False,
        "enabled_after": True,
        "activated": True,
        "selector": "[data-copaw-deep-think='1']",
        "label": "深度思考",
    }
    assert submission["input_readback"] == {
        "matched": True,
        "observed_text": "梳理紫微斗数核心术语和一个常见误解",
        "normalized_text": "梳理紫微斗数核心术语和一个常见误解",
    }


def test_submit_chat_question_blocks_submit_when_input_readback_mismatches_question() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=[
            {
                "html": "<main></main>",
                "bodyText": "ordinary page without account prompt",
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            }
        ],
        deep_think_results=[
            {
                "available": False,
                "enabled": False,
                "selector": "",
                "label": "",
            },
        ],
        input_readback_results=[
            {
                "text": "????",
                "normalized_text": "????",
            },
        ],
    )
    service = _build_service(browser_runner=browser_runner)
    service._ensure_chat_page(session_id="research-browser", page_id="chat-page")

    with pytest.raises(RuntimeError, match="input readback"):
        service._submit_chat_question(
            session_id="research-browser",
            page_id="chat-page",
            question="梳理紫微斗数核心术语和一个常见误解",
        )

    press_key_calls = [call for call in browser_runner.calls if call["action"] == "press_key"]
    assert press_key_calls == []


def test_submit_chat_question_uses_split_action_and_readback_targets() -> None:
    browser_runner = _SplitReadbackBrowserRunner()
    service = _build_service(browser_runner=browser_runner)
    service._ensure_chat_page(session_id="research-browser", page_id="chat-page")

    submission = service._submit_chat_question(
        session_id="research-browser",
        page_id="chat-page",
        question="Clarify the key Zi Wei Dou Shu terms and one common misunderstanding.",
    )

    type_calls = [call for call in browser_runner.calls if call["action"] == "type"]
    assert type_calls == [
        {
            "action": "type",
            "session_id": "research-browser",
            "page_id": "chat-page",
            "text": "Clarify the key Zi Wei Dou Shu terms and one common misunderstanding.",
            "submit": False,
            "ref": "e1",
            "selector": "",
        }
    ]
    assert submission["input_readback"] == {
        "matched": True,
        "observed_text": "Clarify the key Zi Wei Dou Shu terms and one common misunderstanding.",
        "normalized_text": "Clarify the key Zi Wei Dou Shu terms and one common misunderstanding.",
    }


def test_submit_chat_question_runs_shared_step_loop_for_type_then_press() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=[],
        deep_think_results=[
            {
                "available": False,
                "enabled": False,
                "selector": "",
                "label": "",
            },
        ],
    )
    service = _build_service(browser_runner=browser_runner)
    service._ensure_chat_page(session_id="research-browser", page_id="chat-page")
    captured: dict[str, object] = {}
    question = "Clarify the key Zi Wei Dou Shu terms and one common misunderstanding."

    def _fake_run_step_loop(**kwargs):
        captured.update(kwargs)
        planner = kwargs["planner"]
        observation = BrowserObservation(
            page_url="https://chat.baidu.com/search",
            page_title="Baidu Chat",
            snapshot_text='- textbox "Ask anything" [ref=e1]',
        )
        first_step = planner(observation, [])
        assert first_step is not None
        assert first_step.intent_kind == "type"
        assert first_step.target_slot == "primary_input"
        assert first_step.payload["text"] == question
        second_step = planner(
            observation,
            [
                BrowserExecutionResult(
                    status="succeeded",
                    target_slot="primary_input",
                    intent_kind="type",
                    readback={
                        "observed_text": question,
                        "normalized_text": question,
                    },
                    verification_passed=True,
                )
            ],
        )
        assert second_step is not None
        assert second_step.intent_kind == "press"
        assert second_step.target_slot == "page"
        assert second_step.payload["key"] == "Enter"
        assert planner(
            observation,
            [
                BrowserExecutionResult(
                    status="succeeded",
                    target_slot="primary_input",
                    intent_kind="type",
                    verification_passed=True,
                ),
                BrowserExecutionResult(
                    status="succeeded",
                    target_slot="page",
                    intent_kind="press",
                    verification_passed=True,
                ),
            ],
        ) is None
        return BrowserExecutionLoopResult(
            steps=[
                BrowserExecutionResult(
                    status="succeeded",
                    target_slot="primary_input",
                    intent_kind="type",
                    readback={
                        "observed_text": question,
                        "normalized_text": question,
                    },
                    verification_passed=True,
                ),
                BrowserExecutionResult(
                    status="succeeded",
                    target_slot="page",
                    intent_kind="press",
                    verification_passed=True,
                ),
            ],
            final_observation=observation,
            stop_reason="planner-stop",
        )

    service._browser_surface_service.run_step_loop = _fake_run_step_loop

    submission = service._submit_chat_question(
        session_id="research-browser",
        page_id="chat-page",
        question=question,
    )

    assert captured["session_id"] == "research-browser"
    assert captured["page_id"] == "chat-page"
    assert captured["max_steps"] == 3
    assert getattr(captured["page_profile"], "profile_id", "") == "baidu-chat"
    assert submission["input_readback"] == {
        "matched": True,
        "observed_text": question,
        "normalized_text": question,
    }
    press_key_calls = [call for call in browser_runner.calls if call["action"] == "press_key"]
    assert press_key_calls == []


def test_submit_chat_question_shared_planner_clicks_toggle_before_type_when_needed() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=[],
        deep_think_results=[
            {
                "available": True,
                "enabled": False,
                "selector": "[data-copaw-deep-think='1']",
                "label": "深度思考",
            },
        ],
    )
    service = _build_service(browser_runner=browser_runner)
    service._ensure_chat_page(session_id="research-browser", page_id="chat-page")
    captured: dict[str, object] = {}
    question = "Clarify the key Zi Wei Dou Shu terms and one common misunderstanding."

    def _fake_run_step_loop(**kwargs):
        captured.update(kwargs)
        planner = kwargs["planner"]
        observation = BrowserObservation(
            page_url="https://chat.baidu.com/search",
            page_title="Baidu Chat",
            snapshot_text='- textbox "Ask anything" [ref=e1]',
            control_groups=[
                {
                    "group_kind": "reasoning_toggle_group",
                    "scope_anchor": "composer",
                    "candidates": [
                        BrowserTargetCandidate(
                            target_kind="toggle",
                            action_ref="",
                            action_selector="[data-copaw-deep-think='1']",
                            readback_selector="[data-copaw-deep-think='1']",
                            element_kind="button",
                            scope_anchor="composer",
                            score=10,
                            reason="deep-think toggle",
                            metadata={"enabled": False, "label": "深度思考", "target_slots": ["reasoning_toggle"]},
                        )
                    ],
                }
            ],
            slot_candidates={},
        )
        first_step = planner(observation, [])
        assert first_step is not None
        assert first_step.intent_kind == "click"
        assert first_step.target_slot == "reasoning_toggle"
        assert first_step.success_assertion == {"toggle_enabled": "true"}
        second_step = planner(
            observation,
            [
                BrowserExecutionResult(
                    status="succeeded",
                    target_slot="reasoning_toggle",
                    intent_kind="click",
                    readback={"toggle_enabled": "true", "observed_text": "深度思考"},
                    verification_passed=True,
                )
            ],
        )
        assert second_step is not None
        assert second_step.intent_kind == "type"
        assert second_step.target_slot == "primary_input"
        assert second_step.payload["text"] == question
        third_step = planner(
            observation,
            [
                BrowserExecutionResult(
                    status="succeeded",
                    target_slot="reasoning_toggle",
                    intent_kind="click",
                    readback={"toggle_enabled": "true", "observed_text": "深度思考"},
                    verification_passed=True,
                ),
                BrowserExecutionResult(
                    status="succeeded",
                    target_slot="primary_input",
                    intent_kind="type",
                    readback={
                        "observed_text": question,
                        "normalized_text": question,
                    },
                    verification_passed=True,
                ),
            ],
        )
        assert third_step is not None
        assert third_step.intent_kind == "press"
        assert third_step.target_slot == "page"
        return BrowserExecutionLoopResult(
            steps=[
                BrowserExecutionResult(
                    status="succeeded",
                    target_slot="reasoning_toggle",
                    intent_kind="click",
                    readback={"toggle_enabled": "true", "observed_text": "深度思考"},
                    verification_passed=True,
                ),
                BrowserExecutionResult(
                    status="succeeded",
                    target_slot="primary_input",
                    intent_kind="type",
                    readback={
                        "observed_text": question,
                        "normalized_text": question,
                    },
                    verification_passed=True,
                ),
                BrowserExecutionResult(
                    status="succeeded",
                    target_slot="page",
                    intent_kind="press",
                    verification_passed=True,
                ),
            ],
            final_observation=observation,
            stop_reason="planner-stop",
        )

    service._browser_surface_service.run_step_loop = _fake_run_step_loop

    submission = service._submit_chat_question(
        session_id="research-browser",
        page_id="chat-page",
        question=question,
    )

    assert captured["max_steps"] == 3
    assert submission["deep_think"]["requested"] is True
    assert submission["deep_think"]["enabled_after"] is True
    assert submission["input_readback"]["matched"] is True


def test_ensure_baidu_deep_think_enabled_uses_shared_execute_step_toggle_assertion() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=[],
        deep_think_results=[
            {
                "available": True,
                "enabled": False,
                "selector": "[data-copaw-deep-think='1']",
                "label": "深度思考",
            },
            {
                "available": True,
                "enabled": True,
                "selector": "[data-copaw-deep-think='1']",
                "label": "深度思考",
            },
        ],
    )
    service = _build_service(browser_runner=browser_runner)
    context = service._build_baidu_surface_context(
        session_id="research-browser",
        page_id="chat-page",
    )
    captured: dict[str, object] = {}
    original_execute_step = service._browser_surface_service.execute_step

    def _capture_execute_step(**kwargs):
        captured.update(kwargs)
        return original_execute_step(**kwargs)

    service._browser_surface_service.execute_step = _capture_execute_step

    payload = service._ensure_baidu_deep_think_enabled(
        session_id="research-browser",
        page_id="chat-page",
        surface_context=context,
    )

    assert captured["target_slot"] == "reasoning_toggle"
    assert captured["intent_kind"] == "click"
    assert captured["success_assertion"] == {"toggle_enabled": "true"}
    assert payload["enabled_after"] is True
    assert payload["activated"] is True


def test_build_baidu_surface_context_does_not_depend_on_private_input_selector() -> None:
    browser_runner = _SplitReadbackBrowserRunner()
    service = _build_service(browser_runner=browser_runner)
    service._ensure_chat_page(session_id="research-browser", page_id="chat-page")

    context = service._build_baidu_surface_context(
        session_id="research-browser",
        page_id="chat-page",
    )

    observation = context["observation"]
    candidate = resolve_browser_target(observation, target_slot="primary_input")

    assert candidate is not None
    assert candidate.action_ref == "e1"


def test_build_baidu_surface_context_uses_shared_service_capture_entry() -> None:
    browser_runner = _SplitReadbackBrowserRunner()
    service = _build_service(browser_runner=browser_runner)
    service._ensure_chat_page(session_id="research-browser", page_id="chat-page")
    captured: dict[str, object] = {}

    def _capture_page_context(**kwargs):
        captured.update(kwargs)
        return {
            "snapshot_text": '- textbox "Ask anything" [ref=e1]',
            "page_url": "https://chat.baidu.com/search",
            "page_title": "Baidu Chat",
            "dom_probe": {
                "inputs": [
                    {
                        "target_kind": "input",
                        "action_ref": "e1",
                        "readback_selector": "#chat-textarea",
                        "element_kind": "textarea",
                        "scope_anchor": "composer",
                        "score": 10,
                        "reason": "primary textarea",
                    }
                ]
            },
            "observation": BrowserObservation(
                page_url="https://chat.baidu.com/search",
                page_title="Baidu Chat",
                snapshot_text='- textbox "Ask anything" [ref=e1]',
                interactive_targets=[],
                primary_input_candidates=[],
                slot_candidates={},
                control_groups=[],
                readable_sections=[],
                blockers=[],
            ),
        }

    service._browser_surface_service.capture_page_context = _capture_page_context

    context = service._build_baidu_surface_context(
        session_id="research-browser",
        page_id="chat-page",
    )

    assert captured["session_id"] == "research-browser"
    assert captured["page_id"] == "chat-page"
    assert getattr(captured["page_profile"], "profile_id", "") == "baidu-chat"
    assert context["page_title"] == "Baidu Chat"


def test_baidu_service_no_longer_exposes_private_input_selector_helper() -> None:
    service = _build_service(browser_runner=_SplitReadbackBrowserRunner())

    assert not hasattr(service, "_select_chat_input_ref")


def test_build_baidu_surface_context_uses_shared_service_for_seed_input_resolution() -> None:
    browser_runner = _SplitReadbackBrowserRunner()
    service = _build_service(browser_runner=browser_runner)
    service._ensure_chat_page(session_id="research-browser", page_id="chat-page")
    assert not hasattr(baidu_page_research_service_module, "observe_browser_page")
    assert not hasattr(baidu_page_research_service_module, "resolve_browser_target")

    context = service._build_baidu_surface_context(
        session_id="research-browser",
        page_id="chat-page",
    )

    observation = context["observation"]
    candidate = resolve_browser_target(observation, target_slot="primary_input")

    assert candidate is not None
    assert candidate.action_ref == "e1"


def test_read_baidu_deep_think_state_scopes_to_local_control_group() -> None:
    service = _build_service(browser_runner=_ScopedDeepThinkBrowserRunner())

    payload = service._read_baidu_deep_think_state(
        session_id="research-browser",
        page_id="chat-page",
    )

    assert payload == {
        "available": True,
        "enabled": True,
        "selector": "[data-copaw-deep-think='1']",
        "label": "Deep Think",
    }


def test_read_baidu_deep_think_state_uses_shared_browser_readback_entry() -> None:
    browser_runner = _ScopedDeepThinkBrowserRunner()
    service = _build_service(browser_runner=browser_runner)
    captured: dict[str, object] = {}
    original_read_target_readback = service._browser_surface_service.read_target_readback

    def _capture_read_target_readback(**kwargs):
        captured.update(kwargs)
        return original_read_target_readback(**kwargs)

    service._browser_surface_service.read_target_readback = _capture_read_target_readback

    payload = service._read_baidu_deep_think_state(
        session_id="research-browser",
        page_id="chat-page",
    )

    assert captured["session_id"] == "research-browser"
    assert captured["page_id"] == "chat-page"
    assert isinstance(captured["target"], BrowserTargetCandidate)
    assert payload["enabled"] is True


def test_resolve_chat_input_target_uses_shared_browser_service_entry() -> None:
    browser_runner = _SplitReadbackBrowserRunner()
    service = _build_service(browser_runner=browser_runner)
    service._ensure_chat_page(session_id="research-browser", page_id="chat-page")
    context = service._build_baidu_surface_context(
        session_id="research-browser",
        page_id="chat-page",
    )
    assert not hasattr(baidu_page_research_service_module, "resolve_browser_target")

    payload = service._resolve_chat_input_target(
        session_id="research-browser",
        page_id="chat-page",
        surface_context=context,
    )

    assert payload["ref"] == "e1"
    assert payload["readback_selector"] == "#chat-textarea"


def test_read_chat_input_readback_uses_shared_browser_service_entry() -> None:
    browser_runner = _SplitReadbackBrowserRunner()
    service = _build_service(browser_runner=browser_runner)
    browser_runner.typed_text_by_page[("research-browser", "chat-page")] = (
        "Clarify the key Zi Wei Dou Shu terms and one common misunderstanding."
    )
    candidate = BrowserTargetCandidate(
        target_kind="input",
        action_ref="e1",
        action_selector="",
        readback_selector="#chat-textarea",
        element_kind="textarea",
        scope_anchor="composer",
        score=10,
        reason="primary composer textarea",
    )
    assert not hasattr(baidu_page_research_service_module, "read_browser_target_readback")

    payload = service._read_chat_input_readback(
        session_id="research-browser",
        page_id="chat-page",
        question="Clarify the key Zi Wei Dou Shu terms and one common misunderstanding.",
        target=candidate,
    )

    assert payload == {
        "matched": True,
        "observed_text": "Clarify the key Zi Wei Dou Shu terms and one common misunderstanding.",
        "normalized_text": "Clarify the key Zi Wei Dou Shu terms and one common misunderstanding.",
    }


def test_research_service_persists_chat_submission_and_response_readback_into_round_metadata() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=[
            {
                "html": "<main></main>",
                "bodyText": """
                What is Zi Wei Dou Shu?
                Zi Wei Dou Shu is a traditional Chinese astrology system used to interpret life patterns.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
            {
                "html": "<main></main>",
                "bodyText": """
                Follow up
                Beginners should learn the twelve palaces before reading any chart.
                Researchers should study the main stars and four transformations together.
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            },
        ],
        deep_think_results=[
            {
                "available": True,
                "enabled": False,
                "selector": "[data-copaw-deep-think='1']",
                "label": "深度思考",
            },
            {
                "available": True,
                "enabled": True,
                "selector": "[data-copaw-deep-think='1']",
                "label": "深度思考",
            },
            {
                "available": True,
                "enabled": True,
                "selector": "[data-copaw-deep-think='1']",
                "label": "深度思考",
            },
            {
                "available": True,
                "enabled": True,
                "selector": "[data-copaw-deep-think='1']",
                "label": "深度思考",
            },
        ],
        input_readback_results=[
            {
                "text": "What is Zi Wei Dou Shu?",
                "normalized_text": "What is Zi Wei Dou Shu?",
            },
            {
                "text": (
                    "Follow up on this research goal: What is Zi Wei Dou Shu?. Current answer: "
                    "Zi Wei Dou Shu is a traditional Chinese astrology system used to interpret life patterns. "
                    "Fill the most important missing details, the best sources to verify next, and one common misunderstanding."
                ),
                "normalized_text": (
                    "Follow up on this research goal: What is Zi Wei Dou Shu?. Current answer: "
                    "Zi Wei Dou Shu is a traditional Chinese astrology system used to interpret life patterns. "
                    "Fill the most important missing details, the best sources to verify next, and one common misunderstanding."
                ),
            },
        ],
    )
    service = _build_service(browser_runner=browser_runner)
    start_result = service.start_session(
        goal="What is Zi Wei Dou Shu?",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    result = service.run_session(start_result.session.id)

    first_round = result.rounds[0]
    second_round = result.rounds[1]
    assert first_round.metadata["deep_think"] == {
        "requested": True,
        "available": True,
        "enabled_before": False,
        "enabled_after": True,
        "activated": True,
        "selector": "[data-copaw-deep-think='1']",
        "label": "深度思考",
    }
    assert first_round.metadata["input_readback"]["matched"] is True
    assert first_round.metadata["response_readback"] == {
        "page_href": "https://chat.baidu.com/search",
        "page_title": "Baidu Chat",
        "login_state": "ready",
        "page_kind": "content-page",
        "blocker_hints": [],
        "answer_excerpt": "Zi Wei Dou Shu is a traditional Chinese astrology system used to interpret life patterns.",
        "link_count": 0,
    }
    assert second_round.metadata["deep_think"]["enabled_before"] is True
    assert second_round.metadata["input_readback"]["matched"] is True


def test_research_service_converts_input_readback_mismatch_into_waiting_login_when_page_requires_login() -> None:
    browser_runner = _FakeBrowserRunner(
        evaluate_results=[
            {
                "html": "<main><button>登录</button></main>",
                "bodyText": """
                登录
                请先登录百度账号后继续
                """,
                "href": "https://chat.baidu.com/search",
                "title": "Baidu Chat",
            }
        ],
        input_readback_results=[
            {
                "text": "????",
                "normalized_text": "????",
            }
        ],
    )
    service = _build_service(browser_runner=browser_runner)
    start_result = service.start_session(
        goal="梳理电商平台入门知识结构",
        trigger_source="user-direct",
        owner_agent_id="industry-researcher-demo",
    )

    result = service.run_session(start_result.session.id)

    assert result.session.status == "waiting-login"
    assert result.stop_reason == "waiting-login"
    assert result.rounds[-1].decision == "login_required"
    assert result.rounds[-1].metadata["input_readback"] == {
        "matched": False,
        "observed_text": "????",
        "normalized_text": "????",
    }
    assert result.rounds[-1].metadata["response_readback"] == {
        "page_href": "https://chat.baidu.com/search",
        "page_title": "Baidu Chat",
        "login_state": "login-required",
        "page_kind": "login-wall",
        "blocker_hints": ["login-required"],
        "answer_excerpt": "",
        "link_count": 0,
    }
