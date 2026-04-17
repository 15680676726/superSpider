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
    def __init__(self, *, final_status: str = "completed") -> None:
        self.final_status = final_status
        self.started: list[dict[str, object]] = []
        self.ran: list[str] = []
        self.summarized: list[str] = []

    def start_session(self, **kwargs):
        self.started.append(dict(kwargs))
        return SimpleNamespace(
            session=SimpleNamespace(id="research-session-1", status="queued"),
            stop_reason=None,
        )

    def run_session(self, session_id: str):
        self.ran.append(session_id)
        return SimpleNamespace(
            session=SimpleNamespace(id=session_id, status=self.final_status),
            stop_reason=("waiting-login" if self.final_status == "waiting-login" else "completed"),
        )

    def summarize_session(self, session_id: str):
        self.summarized.append(session_id)
        return SimpleNamespace(
            session=SimpleNamespace(id=session_id, status=self.final_status),
            stop_reason=None,
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
    assert research_service.started == [
        {
            "goal": "去查一下电商平台入门知识，整理后告诉我",
            "trigger_source": "user-direct",
            "owner_agent_id": "industry-researcher-demo",
            "industry_instance_id": "industry-v1-demo",
            "work_context_id": None,
            "supervisor_agent_id": "copaw-agent-runner",
            "metadata": {"entry_surface": "main-brain-chat"},
        }
    ]
    assert research_service.ran == ["research-session-1"]
    assert research_service.summarized == ["research-session-1"]


@pytest.mark.asyncio
async def test_main_brain_followup_brief_uses_attached_trigger_source() -> None:
    backend = _FakeSessionBackend()
    research_service = _FakeResearchSessionService(final_status="waiting-login")
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
            "trigger_source": "main-brain-followup",
        },
    )

    streamed = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="继续")],
            request=request,
        )
    ]

    assert streamed[-1][0].get_text_content() == "研究任务已建立，但百度还没登录。你先登录百度，我再继续。"
    assert research_service.started == [
        {
            "goal": "补齐竞品定价资料和证据来源",
            "trigger_source": "main-brain-followup",
            "owner_agent_id": "industry-researcher-demo",
            "industry_instance_id": "industry-v1-demo",
            "work_context_id": None,
            "supervisor_agent_id": "copaw-agent-runner",
            "metadata": {"entry_surface": "main-brain-chat"},
        }
    ]
    assert research_service.ran == ["research-session-1"]
    assert research_service.summarized == ["research-session-1"]
