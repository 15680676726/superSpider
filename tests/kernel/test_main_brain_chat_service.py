# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from agentscope.message import Msg, TextBlock, ThinkingBlock

import copaw.kernel.main_brain_chat_service as main_brain_chat_service_module
from copaw.kernel.main_brain_chat_service import MainBrainChatService


class _FakeSessionBackend:
    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, str], dict] = {}
        self.save_calls: list[tuple[str, str, dict]] = []

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
        snapshot = dict(payload)
        self.snapshots[(session_id, user_id)] = snapshot
        self.save_calls.append((session_id, user_id, snapshot))


class _SnapshotInspectingModel:
    def __init__(self, backend: _FakeSessionBackend, *, session_id: str, user_id: str) -> None:
        self.backend = backend
        self.session_id = session_id
        self.user_id = user_id
        self.stream = True
        self.snapshot_during_call: dict | None = None

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)
        self.snapshot_during_call = self.backend.load_session_snapshot(
            session_id=self.session_id,
            user_id=self.user_id,
            allow_not_exist=True,
        )
        return SimpleNamespace(content="已收到，这轮先继续聊天。")


class _EmptyResponseModel:
    def __init__(self) -> None:
        self.stream = True
        self.calls: list[bool] = []

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)
        self.calls.append(bool(self.stream))
        return SimpleNamespace(content="")


class _StaticResponseModel:
    def __init__(self, text: str) -> None:
        self.text = text
        self.stream = True

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)
        return SimpleNamespace(content=self.text)


class _StreamingResponseModel:
    def __init__(self, *parts: str) -> None:
        self.parts = list(parts)
        self.stream = True

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)

        async def _stream():
            accumulated = ""
            for part in self.parts:
                accumulated += part
                yield SimpleNamespace(content=accumulated)

        return _stream()


class _StreamingThinkingResponseModel:
    def __init__(self) -> None:
        self.stream = True

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)

        async def _stream():
            yield SimpleNamespace(
                content=[
                    ThinkingBlock(type="thinking", thinking="先整理约束"),
                    TextBlock(type="text", text="先看目标"),
                ],
            )
            yield SimpleNamespace(
                content=[
                    ThinkingBlock(type="thinking", thinking="先整理约束，再确认下一步"),
                    TextBlock(type="text", text="先看目标，再给你下一步"),
                ],
            )

        return _stream()


class _CancelledResponseModel:
    def __init__(self) -> None:
        self.stream = True

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)
        raise asyncio.CancelledError()


class _FakeIndustryService:
    def __init__(self) -> None:
        self.writeback_calls: list[dict[str, object]] = []
        self.kickoff_calls: list[dict[str, object]] = []
        self.writeback_event = asyncio.Event()

    def get_instance_detail(self, instance_id: str) -> object:
        return SimpleNamespace(
            instance_id=instance_id,
            execution_core_identity={"agent_id": "copaw-agent-runner"},
        )

    async def apply_execution_chat_writeback(self, **kwargs):
        self.writeback_calls.append(kwargs)
        self.writeback_event.set()
        return {"applied": True}

    async def kickoff_execution_from_chat(self, **kwargs):
        self.kickoff_calls.append(kwargs)
        return {"activated": True}


async def _snapshot_texts(
    service: MainBrainChatService,
    snapshot: dict,
) -> list[str]:
    memory = service._load_memory(snapshot)  # pylint: disable=protected-access
    messages = await memory.get_memory(prepend_summary=False)
    return [message.get_text_content() for message in messages]


@pytest.mark.asyncio
async def test_main_brain_chat_service_keeps_incoming_turn_in_cache_until_reply_finishes():
    backend = _FakeSessionBackend()
    model = _SnapshotInspectingModel(
        backend,
        session_id="sess-chat",
        user_id="user-chat",
    )
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: model,
    )
    request = SimpleNamespace(
        session_id="sess-chat",
        user_id="user-chat",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )
    msgs = [Msg(name="user", role="user", content="先记住这条消息，再回复我。")]

    streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    assert streamed[0][0].get_text_content() == "已收到，这轮先继续聊天。"
    assert model.snapshot_during_call is not None
    assert await _snapshot_texts(service, model.snapshot_during_call) == []
    snapshot = backend.load_session_snapshot(
        session_id="sess-chat",
        user_id="user-chat",
        allow_not_exist=True,
    )
    assert await _snapshot_texts(service, snapshot) == [
        "先记住这条消息，再回复我。",
        "已收到，这轮先继续聊天。",
    ]
    assert len(backend.save_calls) == 1


@pytest.mark.asyncio
async def test_main_brain_chat_service_throttles_snapshot_persistence_between_turns():
    backend = _FakeSessionBackend()
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: _StaticResponseModel("纯聊天回复"),
    )
    request = SimpleNamespace(
        session_id="sess-throttle",
        user_id="user-throttle",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )

    for turn in range(3):
        msgs = [Msg(name="user", role="user", content=f"第 {turn + 1} 轮消息")]
        streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]
        assert streamed[0][0].get_text_content() == "纯聊天回复"

        if turn == 0:
            assert len(backend.save_calls) == 1
        if turn == 1:
            assert len(backend.save_calls) == 1
        if turn == 2:
            assert len(backend.save_calls) == 2


@pytest.mark.asyncio
async def test_main_brain_chat_service_uses_fallback_text_for_empty_model_response():
    backend = _FakeSessionBackend()
    model = _EmptyResponseModel()
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: model,
    )
    request = SimpleNamespace(
        session_id="sess-empty",
        user_id="user-empty",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )
    msgs = [Msg(name="user", role="user", content="开始前先回我一句。")]

    streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    assert "没有拿到有效回复" in streamed[0][0].get_text_content()
    assert model.calls == [True, False]
    snapshot = backend.load_session_snapshot(
        session_id="sess-empty",
        user_id="user-empty",
        allow_not_exist=True,
    )
    texts = await _snapshot_texts(service, snapshot)
    assert texts[0] == "开始前先回我一句。"
    assert "没有拿到有效回复" in texts[-1]


@pytest.mark.asyncio
async def test_main_brain_chat_service_streams_incremental_chunks_before_completion():
    backend = _FakeSessionBackend()
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: _StreamingResponseModel("hello", " world"),
    )
    request = SimpleNamespace(
        session_id="sess-streaming",
        user_id="user-streaming",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )
    msgs = [Msg(name="user", role="user", content="stream to me")]

    streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    assert len(streamed) == 2
    assert streamed[0][1] is False
    assert streamed[1][1] is True
    assert streamed[0][0].id == streamed[1][0].id
    assert streamed[0][0].get_text_content() == "hello"
    assert streamed[1][0].get_text_content() == "hello world"
    snapshot = backend.load_session_snapshot(
        session_id="sess-streaming",
        user_id="user-streaming",
        allow_not_exist=True,
    )
    texts = await _snapshot_texts(service, snapshot)
    assert texts[-1] == "hello world"


@pytest.mark.asyncio
async def test_main_brain_chat_service_preserves_thinking_blocks_in_streamed_reply():
    backend = _FakeSessionBackend()
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: _StreamingThinkingResponseModel(),
    )
    request = SimpleNamespace(
        session_id="sess-thinking",
        user_id="user-thinking",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )
    msgs = [Msg(name="user", role="user", content="先想一下再答。")]

    streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    assert len(streamed) == 2
    final_message = streamed[-1][0]
    blocks = final_message.get_content_blocks()
    assert blocks[0]["type"] == "thinking"
    assert blocks[0]["thinking"] == "先整理约束，再确认下一步"
    assert blocks[1]["type"] == "text"
    assert blocks[1]["text"] == "先看目标，再给你下一步"


@pytest.mark.asyncio
async def test_main_brain_chat_service_persists_latest_user_turn_when_request_is_cancelled():
    backend = _FakeSessionBackend()
    service = MainBrainChatService(
        session_backend=backend,
        model_factory=lambda: _CancelledResponseModel(),
    )
    request = SimpleNamespace(
        session_id="sess-cancelled",
        user_id="user-cancelled",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )
    msgs = [Msg(name="user", role="user", content="这轮先记下来，我等会回来继续。")]

    with pytest.raises(asyncio.CancelledError):
        _ = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    snapshot = backend.load_session_snapshot(
        session_id="sess-cancelled",
        user_id="user-cancelled",
        allow_not_exist=True,
    )
    texts = await _snapshot_texts(service, snapshot)
    assert texts == ["这轮先记下来，我等会回来继续。"]
    assert len(backend.save_calls) == 1


def test_main_brain_chat_service_prompt_guides_structured_goal_and_auto_progression():
    service = MainBrainChatService(
        session_backend=_FakeSessionBackend(),
        model_factory=lambda: _StaticResponseModel("ok"),
    )
    request = SimpleNamespace(
        session_id="sess-prompt",
        user_id="user-prompt",
        industry_instance_id=None,
        work_context_id=None,
        agent_id=None,
    )

    prompt_messages = service._build_prompt_messages(  # pylint: disable=protected-access
        request=request,
        query="月入10万且零亏损",
        prior_messages=[],
        current_messages=[],
    )

    system_prompt = prompt_messages[0]["content"]
    assert "不要反复追问“是否开始执行”" in system_prompt
    assert "结构化执行目标" in system_prompt


def test_main_brain_chat_service_prompt_includes_staffing_gap_and_researcher_state():
    class _StaffingIndustryService:
        def get_instance_detail(self, instance_id: str) -> object:
            assert instance_id == "industry-v1-demo"
            return SimpleNamespace(
                instance_id=instance_id,
                label="Northwind Robotics",
                summary="Field operations control team",
                execution_core_identity={"agent_id": "copaw-agent-runner"},
                team=SimpleNamespace(
                    agents=[
                        {
                            "role_id": "execution-core",
                            "agent_id": "copaw-agent-runner",
                            "name": "Execution Core",
                            "role_name": "Execution Core",
                        },
                        {
                            "role_id": "researcher",
                            "agent_id": "industry-researcher-demo",
                            "name": "Researcher",
                            "role_name": "Researcher",
                        },
                    ],
                ),
                staffing={
                    "active_gap": {
                        "kind": "career-seat-proposal",
                        "target_role_name": "Platform Trader",
                        "reason": "Need a long-term browser execution seat",
                        "requested_surfaces": ["browser"],
                        "decision_request_id": "decision-seat-1",
                        "requires_confirmation": True,
                    },
                    "pending_proposals": [
                        {
                            "kind": "career-seat-proposal",
                            "target_role_name": "Platform Trader",
                            "decision_request_id": "decision-seat-1",
                            "status": "open",
                        },
                    ],
                    "temporary_seats": [
                        {
                            "role_name": "Desktop Clerk",
                            "status": "assigned",
                        },
                    ],
                    "researcher": {
                        "role_name": "Researcher",
                        "status": "waiting-review",
                        "pending_signal_count": 2,
                    },
                },
                assignments=[],
                backlog=[],
                lanes=[],
            )

    service = MainBrainChatService(
        session_backend=_FakeSessionBackend(),
        industry_service=_StaffingIndustryService(),
        model_factory=lambda: _StaticResponseModel("ok"),
    )
    request = SimpleNamespace(
        session_id="sess-staffing",
        user_id="user-staffing",
        industry_instance_id="industry-v1-demo",
        work_context_id=None,
        agent_id=None,
    )

    prompt_messages = service._build_prompt_messages(  # pylint: disable=protected-access
        request=request,
        query="把平台投放执行也纳入长期团队",
        prior_messages=[],
        current_messages=[],
    )

    context_prompt = prompt_messages[1]["content"]
    assert "Active staffing gap" in context_prompt
    assert "Platform Trader" in context_prompt
    assert "career-seat-proposal" in context_prompt
    assert "decision-seat-1" in context_prompt
    assert "Researcher" in context_prompt
    assert "pending signals: 2" in context_prompt


@pytest.mark.asyncio
async def test_main_brain_chat_service_never_schedules_background_intake_for_control_thread():
    backend = _FakeSessionBackend()
    industry_service = _FakeIndustryService()
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=industry_service,
        model_factory=lambda: _StaticResponseModel("我先接住这件事，后台继续推进。"),
    )
    request = SimpleNamespace(
        session_id="sess-intake",
        user_id="user-intake",
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        work_context_id=None,
        agent_id=None,
        channel="console",
    )

    msgs = [Msg(name="user", role="user", content="把这个需求接过去，往前推进")]

    streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    assert streamed[0][0].get_text_content() == "我先接住这件事，后台继续推进。"
    await asyncio.sleep(0)
    assert industry_service.writeback_calls == []
    assert industry_service.kickoff_calls == []
    assert service._background_tasks == set()  # pylint: disable=protected-access


@pytest.mark.asyncio
async def test_main_brain_chat_service_never_applies_shared_intake_contract_after_reply():
    backend = _FakeSessionBackend()
    industry_service = _FakeIndustryService()
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=industry_service,
        model_factory=lambda: _StaticResponseModel("我先接住，后台继续推进。"),
    )
    request = SimpleNamespace(
        session_id="sess-intake-contract",
        user_id="user-intake-contract",
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        work_context_id=None,
        agent_id=None,
        channel="console",
    )

    msgs = [Msg(name="user", role="user", content="把这件事接过去，继续往前推")]

    streamed = [item async for item in service.execute_stream(msgs=msgs, request=request)]

    assert streamed[0][0].get_text_content() == "我先接住，后台继续推进。"
    await asyncio.sleep(0)
    assert industry_service.writeback_calls == []
    assert industry_service.kickoff_calls == []


@pytest.mark.asyncio
async def test_main_brain_chat_service_explicit_chat_mode_does_not_schedule_background_intake():
    backend = _FakeSessionBackend()
    industry_service = _FakeIndustryService()
    service = MainBrainChatService(
        session_backend=backend,
        industry_service=industry_service,
        model_factory=lambda: _StaticResponseModel("只聊这轮，不进入执行。"),
    )
    request = SimpleNamespace(
        session_id="sess-chat-only",
        user_id="user-chat-only",
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        work_context_id=None,
        agent_id=None,
        channel="console",
        interaction_mode="chat",
    )

    streamed = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content="这轮只聊天，不要落单也不要开跑")],
            request=request,
        )
    ]

    await asyncio.sleep(0)

    assert streamed[0][0].get_text_content() == "只聊这轮，不进入执行。"
    assert industry_service.writeback_calls == []
    assert industry_service.kickoff_calls == []
    assert service._background_tasks == set()  # pylint: disable=protected-access


def test_main_brain_intake_extracts_latest_user_text_as_canonical_input():
    from copaw.kernel.main_brain_intake import extract_main_brain_intake_text

    msgs = [
        Msg(name="assistant", role="assistant", content="先确认一下现状。"),
        Msg(name="user", role="user", content="旧的目标先别动。"),
        Msg(name="assistant", role="assistant", content="收到。"),
        Msg(name="user", role="user", content="把新的增长目标接过去继续推进。"),
    ]

    assert extract_main_brain_intake_text(msgs) == "把新的增长目标接过去继续推进。"


def test_main_brain_intake_materializes_execute_task_contract_from_model_decision():
    from copaw.kernel.main_brain_intake import materialize_main_brain_intake_contract

    contract = materialize_main_brain_intake_contract(
        message_text="把新的增长目标接过去继续推进。",
        decision=SimpleNamespace(
            intent_kind="execute-task",
            should_writeback=False,
            approved_targets=[],
            strategy=None,
            goal=None,
            schedule=None,
            kickoff_allowed=True,
            explicit_execution_confirmation=False,
        ),
    )

    assert contract is not None
    assert contract.message_text == "把新的增长目标接过去继续推进。"
    assert contract.intent_kind == "execute-task"
    assert contract.writeback_requested is False
    assert contract.has_active_writeback_plan is True
    assert contract.should_kickoff is True
    assert contract.should_route_to_orchestrate is True
