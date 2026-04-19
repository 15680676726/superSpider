# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pytest
from agentscope.message import Msg

from copaw.kernel.main_brain_chat_service import MainBrainChatService


class _FakeSessionBackend:
    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, str], dict] = {}

    def load_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        allow_not_exist: bool = False,
    ) -> dict:
        _ = allow_not_exist
        return dict(self.snapshots.get((session_id, user_id), {}))

    def save_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        payload: dict,
        source_ref: str,
    ) -> None:
        _ = source_ref
        self.snapshots[(session_id, user_id)] = dict(payload)


class _ExplodingModel:
    stream = True

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)
        raise AssertionError("model should not be called for research trigger")


class _FakeResearchSessionService:
    def __init__(self, *, statuses: list[str] | None = None) -> None:
        self._statuses = list(statuses or ["completed"])
        self.frontdoor_calls: list[dict[str, object]] = []

    def start_session(self, **kwargs):
        _ = kwargs
        raise AssertionError("legacy research session methods should not be called")

    def run_session(self, session_id: str):
        _ = session_id
        raise AssertionError("legacy research session methods should not be called")

    def summarize_session(self, session_id: str):
        _ = session_id
        raise AssertionError("legacy research session methods should not be called")

    def run_source_collection_frontdoor(self, **kwargs):
        self.frontdoor_calls.append(dict(kwargs))
        status = self._statuses.pop(0) if self._statuses else "completed"
        return SimpleNamespace(
            session_id="research-session-1",
            status=status,
            stop_reason=("waiting-login" if status == "waiting-login" else "completed"),
            route_mode="heavy",
            execution_agent_id=str(kwargs.get("owner_agent_id") or ""),
        )


class _FakeIndustryService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_instance_detail(self, instance_id: str):
        self.calls.append(instance_id)
        return {
            "staffing": {
                "researcher": {
                    "agent_id": "industry-researcher-demo",
                    "role_name": "Researcher",
                }
            }
        }


@pytest.mark.asyncio
async def test_main_brain_user_direct_research_request_starts_formal_session() -> None:
    backend = _FakeSessionBackend()
    research_service = _FakeResearchSessionService()
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=_FakeIndustryService(),
        research_session_service=research_service,
        model_factory=lambda: _ExplodingModel(),
    )
    request = SimpleNamespace(
        session_id="sess-research-direct",
        user_id="user-research-direct",
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        agent_id="copaw-agent-runner",
        channel="console",
    )

    streamed = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="去查一下电商平台入门知识，整理后告诉我")],
            request=request,
        )
    ]

    assert streamed[-1][0].get_text_content() == "研究任务已经启动，我去查资料并整理成正式汇报。"
    assert research_service.frontdoor_calls == [
        {
            "goal": "去查一下电商平台入门知识，整理后告诉我",
            "trigger_source": "user-direct",
            "owner_agent_id": "industry-researcher-demo",
            "industry_instance_id": "industry-v1-demo",
            "work_context_id": None,
            "supervisor_agent_id": "copaw-agent-runner",
            "question": "去查一下电商平台入门知识，整理后告诉我",
            "why_needed": None,
            "done_when": None,
            "collection_mode_hint": "heavy",
            "requested_sources": [],
            "writeback_target": None,
            "metadata": {"entry_surface": "main-brain-chat"},
        }
    ]


@pytest.mark.asyncio
async def test_main_brain_followup_brief_uses_attached_trigger_source() -> None:
    backend = _FakeSessionBackend()
    research_service = _FakeResearchSessionService(statuses=["waiting-login"])
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=_FakeIndustryService(),
        research_session_service=research_service,
        model_factory=lambda: _ExplodingModel(),
    )
    request = SimpleNamespace(
        session_id="sess-research-followup",
        user_id="user-research-followup",
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        agent_id="copaw-agent-runner",
        channel="console",
        _copaw_research_brief={
            "goal": "补齐竞品定价资料和证据来源",
            "question": "继续补齐竞品定价资料和证据来源，并标注官网与第三方口径差异。",
            "trigger_source": "main-brain-followup",
            "why_needed": "当前 backlog 需要主脑基于正式证据决定下一步。",
            "done_when": "至少补齐官网定价页、核心能力页和一个第三方交叉来源。",
            "requested_sources": ["search", "web_page"],
            "collection_mode_hint": "heavy",
            "writeback_target": {
                "scope_type": "work_context",
                "scope_id": "ctx-followup-1",
            },
        },
        work_context_id="ctx-followup-1",
    )

    streamed = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="继续")],
            request=request,
        )
    ]

    assert streamed[-1][0].get_text_content() == (
        "研究任务卡在登录。请先完成百度登录，登录好后直接在这个聊天线程回复“继续”或“我登录好了”，"
        "我会沿同一个研究会话和浏览器窗口继续，不会新开线程。"
    )
    assert research_service.frontdoor_calls == [
        {
            "goal": "补齐竞品定价资料和证据来源",
            "trigger_source": "main-brain-followup",
            "owner_agent_id": "industry-researcher-demo",
            "industry_instance_id": "industry-v1-demo",
            "work_context_id": "ctx-followup-1",
            "supervisor_agent_id": "copaw-agent-runner",
            "question": "继续补齐竞品定价资料和证据来源，并标注官网与第三方口径差异。",
            "why_needed": "当前 backlog 需要主脑基于正式证据决定下一步。",
            "done_when": "至少补齐官网定价页、核心能力页和一个第三方交叉来源。",
            "collection_mode_hint": "heavy",
            "requested_sources": ["search", "web_page"],
            "writeback_target": {
                "scope_type": "work_context",
                "scope_id": "ctx-followup-1",
            },
            "metadata": {"entry_surface": "main-brain-chat"},
        }
    ]


@pytest.mark.asyncio
async def test_main_brain_forwards_browser_session_override_into_frontdoor_metadata() -> None:
    backend = _FakeSessionBackend()
    research_service = _FakeResearchSessionService(statuses=["waiting-login"])
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=_FakeIndustryService(),
        research_session_service=research_service,
        model_factory=lambda: _ExplodingModel(),
    )
    request = SimpleNamespace(
        session_id="sess-research-browser-session",
        user_id="user-research-browser-session",
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        agent_id="copaw-agent-runner",
        channel="console",
        _copaw_research_brief={
            "goal": "继续行业研究",
            "question": "继续行业研究并补齐来源",
            "trigger_source": "main-brain-followup",
            "collection_mode_hint": "heavy",
            "browser_session": {
                "persist_login_state": True,
                "storage_state_path": "D:/tmp/main-brain-shared.json",
            },
        },
    )

    _ = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="继续")],
            request=request,
        )
    ]

    assert research_service.frontdoor_calls[0]["metadata"] == {
        "entry_surface": "main-brain-chat",
        "browser_session": {
            "persist_login_state": True,
            "storage_state_path": "D:/tmp/main-brain-shared.json",
        },
    }


@pytest.mark.asyncio
async def test_main_brain_waiting_login_prompt_persists_formal_continuation_and_reuses_same_research_session() -> None:
    backend = _FakeSessionBackend()
    research_service = _FakeResearchSessionService(statuses=["waiting-login", "completed"])
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=_FakeIndustryService(),
        research_session_service=research_service,
        model_factory=lambda: _ExplodingModel(),
    )
    first_request = SimpleNamespace(
        session_id="sess-research-login",
        user_id="user-research-login",
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        agent_id="copaw-agent-runner",
        channel="console",
        _copaw_research_brief={
            "goal": "补齐竞品定价资料和证据来源",
            "question": "继续补齐竞品定价资料和证据来源，并标注官网与第三方口径差异。",
            "trigger_source": "main-brain-followup",
            "why_needed": "当前 backlog 需要主脑基于正式证据决定下一步。",
            "done_when": "至少补齐官网定价页、核心能力页和一个第三方交叉来源。",
            "requested_sources": ["search", "web_page"],
            "collection_mode_hint": "heavy",
            "writeback_target": {
                "scope_type": "work_context",
                "scope_id": "ctx-followup-1",
            },
        },
        work_context_id="ctx-followup-1",
    )

    first_stream = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="继续")],
            request=first_request,
        )
    ]

    first_text = first_stream[-1][0].get_text_content()
    assert "登录好后直接在这个聊天线程回复“继续”或“我登录好了”" in first_text
    assert "同一个研究会话和浏览器窗口继续" in first_text
    persisted_snapshot = backend.snapshots[("sess-research-login", "copaw-agent-runner")]
    continuation = persisted_snapshot["main_brain"]["research_continuation"]
    assert continuation["status"] == "waiting-login"
    assert continuation["research_session_id"] == "research-session-1"
    assert continuation["chat_thread_id"] == "sess-research-login"

    second_request = SimpleNamespace(
        session_id="sess-research-login",
        user_id="user-research-login",
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        agent_id="copaw-agent-runner",
        channel="console",
        work_context_id="ctx-followup-1",
    )

    second_stream = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="我登录好了")],
            request=second_request,
        )
    ]

    second_text = second_stream[-1][0].get_text_content()
    assert "同一个研究会话和浏览器窗口继续" in second_text
    assert len(research_service.frontdoor_calls) == 2
    assert research_service.frontdoor_calls[1]["preferred_session_id"] == "research-session-1"
    assert research_service.frontdoor_calls[1]["trigger_source"] == "main-brain-followup"
