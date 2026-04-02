# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from agentscope.message import Msg
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest, RunStatus

import copaw.kernel.main_brain_chat_service as main_brain_chat_service_module
import copaw.kernel.query_execution_shared as query_execution_shared_module
from copaw.app.runtime_host import RuntimeHost
from copaw.environments.models import SessionMount
from copaw.kernel import KernelResult, KernelTurnExecutor
from copaw.kernel.main_brain_chat_service import MainBrainChatService
from copaw.kernel.main_brain_intake import MainBrainIntakeContract
from copaw.kernel.main_brain_intent_shell import MainBrainIntentShell
from copaw.kernel.main_brain_orchestrator import MainBrainOrchestrator
from copaw.kernel.query_execution import KernelQueryExecutionService


class FakeQueryExecutionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.synced: dict[str, object] = {}
        self.recorded_usage: list[dict[str, object]] = []

    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield Msg(name="assistant", role="assistant", content="kernel done"), True

    def set_session_backend(self, session_backend) -> None:
        self.synced["session_backend"] = session_backend

    def set_conversation_compaction_service(
        self,
        conversation_compaction_service,
    ) -> None:
        self.synced["conversation_compaction_service"] = (
            conversation_compaction_service
        )

    def set_kernel_dispatcher(self, kernel_dispatcher) -> None:
        self.synced["kernel_dispatcher"] = kernel_dispatcher

    def resolve_request_owner_agent_id(self, *, request) -> str | None:
        return getattr(request, "agent_id", None) or None

    def record_turn_usage(self, *, request, kernel_task_id, usage) -> None:
        self.recorded_usage.append(
            {
                "request": request,
                "kernel_task_id": kernel_task_id,
                "usage": usage,
            },
        )


class FakeMainBrainChatService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.synced: dict[str, object] = {}

    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield Msg(name="assistant", role="assistant", content="chat done"), True

    def set_session_backend(self, session_backend) -> None:
        self.synced["session_backend"] = session_backend


class FakeMainBrainOrchestrator:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.synced: dict[str, object] = {}

    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield Msg(name="assistant", role="assistant", content="orchestrator done"), True

    def set_query_execution_service(self, query_execution_service) -> None:
        self.synced["query_execution_service"] = query_execution_service

    def set_session_backend(self, session_backend) -> None:
        self.synced["session_backend"] = session_backend


class FakeEnvironmentService:
    def __init__(self, *, sessions: dict[str, SessionMount] | None = None) -> None:
        self._sessions = sessions or {}

    def get_session(self, session_mount_id: str) -> SessionMount | None:
        return self._sessions.get(session_mount_id)


class FakeKernelDispatcher:
    def __init__(self) -> None:
        self.submitted = []
        self.completed = []
        self.failed = []
        self.cancelled = []

    def submit(self, task):
        self.submitted.append(task)
        return KernelResult(task_id=task.id, success=True, phase="executing")

    def complete_task(self, task_id: str, *, summary: str, metadata=None) -> None:
        self.completed.append((task_id, summary, metadata))

    def fail_task(self, task_id: str, *, error: str) -> None:
        self.failed.append((task_id, error))

    def cancel_task(self, task_id: str, *, resolution: str) -> None:
        self.cancelled.append((task_id, resolution))


class FailingQueryExecutionService(FakeQueryExecutionService):
    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        raise RuntimeError("Connection error.")
        yield


class CancelledQueryExecutionService(FakeQueryExecutionService):
    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        raise asyncio.CancelledError()
        yield


class _FakeIndustryServiceForAsyncIntake:
    def __init__(self) -> None:
        self.writeback_calls: list[dict[str, object]] = []
        self.kickoff_calls: list[dict[str, object]] = []
        self.writeback_event = asyncio.Event()
        self.kickoff_event = asyncio.Event()

    def get_instance_detail(self, instance_id: str):
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
        self.kickoff_event.set()
        return {"activated": True}


def _make_main_brain_intake_contract(
    *,
    message_text: str = "model",
    intent_kind: str = "chat",
    should_writeback: bool = False,
    kickoff_allowed: bool = False,
    explicit_execution_confirmation: bool = False,
    writeback_plan: object | None = None,
) -> MainBrainIntakeContract:
    return MainBrainIntakeContract(
        message_text=message_text,
        decision=SimpleNamespace(
            intent_kind=intent_kind,
            should_writeback=should_writeback,
            kickoff_allowed=kickoff_allowed,
            explicit_execution_confirmation=explicit_execution_confirmation,
        ),
        intent_kind=intent_kind,
        writeback_requested=should_writeback,
        writeback_plan=writeback_plan,
        should_kickoff=kickoff_allowed or explicit_execution_confirmation,
    )


def _async_intake_resolver(
    contract: MainBrainIntakeContract | None,
):
    async def _resolver(**_kwargs):
        return contract

    return _resolver


@pytest.mark.asyncio
async def test_kernel_turn_executor_delegates_query_execution_to_service():
    query_execution_service = FakeQueryExecutionService()
    kernel_dispatcher = FakeKernelDispatcher()
    executor = KernelTurnExecutor(
        session_backend=object(),
        kernel_dispatcher=kernel_dispatcher,
        query_execution_service=query_execution_service,
    )

    request = AgentRequest(
        id="req-1",
        session_id="sess-1",
        user_id="user-1",
        channel="console",
        input=[],
    )
    request.agent_id = "manager-1"
    msgs = [Msg(name="user", role="user", content="hello kernel")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][1] is True
    assert streamed[0][0].get_text_content() == "kernel done"
    assert len(query_execution_service.calls) == 1
    submitted = kernel_dispatcher.submitted[0]
    assert query_execution_service.calls[0]["kernel_task_id"] == submitted.id
    assert submitted.owner_agent_id == "manager-1"
    assert kernel_dispatcher.completed == [
        (submitted.id, "kernel done", {"source": "kernel-turn-executor"})
    ]


@pytest.mark.asyncio
async def test_kernel_turn_executor_routes_chat_mode_to_main_brain_service():
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    kernel_dispatcher = FakeKernelDispatcher()
    executor = KernelTurnExecutor(
        session_backend=object(),
        kernel_dispatcher=kernel_dispatcher,
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-chat",
        session_id="sess-chat",
        user_id="user-chat",
        channel="console",
        input=[],
    )
    request.interaction_mode = "chat"
    msgs = [Msg(name="user", role="user", content="只聊天，不执行")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert streamed[0][1] is True
    assert len(main_brain_chat_service.calls) == 1
    assert query_execution_service.calls == []
    assert kernel_dispatcher.submitted == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_explicit_chat_mode_overrides_orchestrate_intake_hint(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-chat-explicit-wins",
        session_id="sess-chat-explicit-wins",
        user_id="user-chat-explicit-wins",
        channel="console",
        input=[],
    )
    request.interaction_mode = "chat"
    msgs = [Msg(name="user", role="user", content="这轮只聊天，不进入执行编排")]

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _async_intake_resolver(
            _make_main_brain_intake_contract(
                message_text="这轮只聊天，不进入执行编排",
                intent_kind="execute-task",
                kickoff_allowed=True,
            ),
        ),
    )

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert len(main_brain_chat_service.calls) == 1
    assert query_execution_service.calls == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_explicit_chat_mode_ignores_stale_cached_mode_metadata():
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-chat-stale-mode-cache",
        session_id="sess-chat-stale-mode-cache",
        user_id="user-chat-stale-mode-cache",
        channel="console",
        input=[],
    )
    request.interaction_mode = "chat"
    request._copaw_requested_interaction_mode = "auto"
    request._copaw_resolved_interaction_mode = "orchestrate"
    msgs = [Msg(name="user", role="user", content="这轮显式只聊天")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert len(main_brain_chat_service.calls) == 1
    assert query_execution_service.calls == []
    assert request._copaw_requested_interaction_mode == "chat"
    assert request._copaw_resolved_interaction_mode == "chat"


@pytest.mark.asyncio
async def test_kernel_turn_executor_explicit_orchestrate_mode_ignores_stale_cached_mode_metadata():
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    main_brain_orchestrator = FakeMainBrainOrchestrator()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
    )
    request = AgentRequest(
        id="req-orchestrate-stale-mode-cache",
        session_id="sess-orchestrate-stale-mode-cache",
        user_id="user-orchestrate-stale-mode-cache",
        channel="console",
        input=[],
    )
    request.interaction_mode = "orchestrate"
    request._copaw_requested_interaction_mode = "auto"
    request._copaw_resolved_interaction_mode = "chat"
    msgs = [Msg(name="user", role="user", content="这轮显式进入执行编排")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "orchestrator done"
    assert len(main_brain_orchestrator.calls) == 1
    assert main_brain_chat_service.calls == []
    assert query_execution_service.calls == []
    assert request._copaw_requested_interaction_mode == "orchestrate"
    assert request._copaw_resolved_interaction_mode == "orchestrate"


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_routes_questions_to_chat_service():
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    kernel_dispatcher = FakeKernelDispatcher()
    executor = KernelTurnExecutor(
        session_backend=object(),
        kernel_dispatcher=kernel_dispatcher,
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-chat",
        session_id="sess-auto-chat",
        user_id="user-auto-chat",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    msgs = [Msg(name="user", role="user", content="如果开始执行会怎么样？")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert streamed[0][1] is True
    assert len(main_brain_chat_service.calls) == 1
    assert query_execution_service.calls == []
    assert kernel_dispatcher.submitted == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_keeps_action_wording_in_chat_without_intake_result(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-orchestrate",
        session_id="sess-auto-orchestrate",
        user_id="user-auto-orchestrate",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    msgs = [Msg(name="user", role="user", content="生成一份测试报告")]

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _async_intake_resolver(None),
    )

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert streamed[0][1] is True
    assert query_execution_service.calls == []
    assert len(main_brain_chat_service.calls) == 1


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_does_not_guess_execution_from_action_wording(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-no-guess-action",
        session_id="sess-auto-no-guess-action",
        user_id="user-auto-no-guess-action",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    msgs = [Msg(name="user", role="user", content="生成一份测试报告")]

    async def _fake_intake_resolver(**_kwargs):
        return None

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _fake_intake_resolver,
        raising=False,
    )

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert len(main_brain_chat_service.calls) == 1
    assert query_execution_service.calls == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_does_not_guess_execution_from_plain_confirmation(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-no-guess-confirm",
        session_id="sess-auto-no-guess-confirm",
        user_id="user-auto-no-guess-confirm",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    msgs = [
        Msg(
            name="assistant",
            role="assistant",
            content="如果你确认，我下一条就进入执行编排。",
        ),
        Msg(name="user", role="user", content="好的"),
    ]

    async def _fake_intake_resolver(**_kwargs):
        return None

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _fake_intake_resolver,
        raising=False,
    )

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert len(main_brain_chat_service.calls) == 1
    assert query_execution_service.calls == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_routes_plain_chat_without_writeback_model_decision(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-natural-chat",
        session_id="sess-auto-natural-chat",
        user_id="user-auto-natural-chat",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    resolver_calls = 0

    async def _counting_resolver(**_kwargs):
        nonlocal resolver_calls
        resolver_calls += 1
        return _make_main_brain_intake_contract(
            intent_kind="execute-task",
            kickoff_allowed=True,
        )

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _counting_resolver,
    )
    msgs = [Msg(name="user", role="user", content="那你开始吧，直接推进下去")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert query_execution_service.calls == []
    assert len(main_brain_chat_service.calls) == 1
    assert resolver_calls == 0


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_keeps_goal_setting_text_in_chat_without_explicit_actions(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-goal-chat",
        session_id="sess-auto-goal-chat",
        user_id="user-auto-goal-chat",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    resolver_calls = 0

    async def _counting_resolver(**_kwargs):
        nonlocal resolver_calls
        resolver_calls += 1
        return _make_main_brain_intake_contract(
            intent_kind="execute-task",
            should_writeback=True,
            kickoff_allowed=True,
            writeback_plan=SimpleNamespace(active=True),
        )

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _counting_resolver,
    )
    msgs = [Msg(name="user", role="user", content="我要在3个月内把这个账号做到月营收10万")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert query_execution_service.calls == []
    assert len(main_brain_chat_service.calls) == 1
    assert resolver_calls == 0


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_routes_to_orchestrate_only_for_explicit_actions(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    main_brain_orchestrator = FakeMainBrainOrchestrator()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
    )
    request = AgentRequest(
        id="req-auto-explicit-actions",
        session_id="sess-auto-explicit-actions",
        user_id="user-auto-explicit-actions",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    request.requested_actions = ["writeback_backlog"]
    msgs = [Msg(name="user", role="user", content="Generate a report draft.")]
    resolver_calls = 0

    async def _counting_resolver(**_kwargs):
        nonlocal resolver_calls
        resolver_calls += 1
        return None

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _counting_resolver,
    )

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "orchestrator done"
    assert len(main_brain_orchestrator.calls) == 1
    assert main_brain_chat_service.calls == []
    assert query_execution_service.calls == []
    assert resolver_calls == 0


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_prefers_model_resolution_for_main_brain_request(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-model-orchestrate",
        session_id="sess-auto-model-orchestrate",
        user_id="user-auto-model-orchestrate",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    request.industry_instance_id = "industry-v1-demo"
    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _async_intake_resolver(
            _make_main_brain_intake_contract(
                intent_kind="execute-task",
                kickoff_allowed=True,
            ),
        ),
    )
    msgs = [Msg(name="user", role="user", content="这件事你接过去往前推，落到主线里")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "kernel done"
    assert len(query_execution_service.calls) == 1
    assert main_brain_chat_service.calls == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_prefers_model_chat_resolution_over_keyword_fallback(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-model-chat",
        session_id="sess-auto-model-chat",
        user_id="user-auto-model-chat",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    request.industry_instance_id = "industry-v1-demo"
    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _async_intake_resolver(
            _make_main_brain_intake_contract(
                intent_kind="chat",
            ),
        ),
    )
    msgs = [Msg(name="user", role="user", content="帮我看一下")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert query_execution_service.calls == []
    assert len(main_brain_chat_service.calls) == 1


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_keeps_plan_shell_queries_in_chat_on_control_thread(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-plan-shell",
        session_id="sess-auto-plan-shell",
        user_id="user-auto-plan-shell",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    request.industry_instance_id = "industry-v1-demo"
    request.industry_role_id = "execution-core"
    request.control_thread_id = "industry-chat:industry-v1-demo:execution-core"
    resolver_calls = 0

    async def _counting_resolver(**_kwargs):
        nonlocal resolver_calls
        resolver_calls += 1
        return _make_main_brain_intake_contract(
            intent_kind="execute-task",
            kickoff_allowed=True,
        )

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _counting_resolver,
    )
    monkeypatch.setattr(
        "copaw.kernel.turn_executor.detect_main_brain_intent_shell",
        lambda _text: MainBrainIntentShell(
            mode_hint="plan",
            trigger_source="keyword",
            matched_text="计划",
            confidence=0.95,
        ),
    )
    msgs = [Msg(name="user", role="user", content="先做个计划，再动手。")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert query_execution_service.calls == []
    assert len(main_brain_chat_service.calls) == 1
    assert resolver_calls == 0
    assert getattr(request, "_copaw_requested_mode_hint", None) == "plan"


@pytest.mark.asyncio
async def test_kernel_turn_executor_routes_orchestrate_mode_to_main_brain_orchestrator():
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    main_brain_orchestrator = FakeMainBrainOrchestrator()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
    )
    request = AgentRequest(
        id="req-orchestrator-direct",
        session_id="sess-orchestrator-direct",
        user_id="user-orchestrator-direct",
        channel="console",
        input=[],
    )
    request.interaction_mode = "orchestrate"

    streamed = [
        item
        async for item in executor.handle_query(
            msgs=[Msg(name="user", role="user", content="把本周运营安排落到执行链")],
            request=request,
        )
    ]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "orchestrator done"
    assert len(main_brain_orchestrator.calls) == 1
    assert query_execution_service.calls == []
    assert main_brain_chat_service.calls == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_routes_non_chat_turns_through_orchestrator_plan():
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()

    async def _fake_resolver(**_kwargs):
        return MainBrainIntakeContract(
            message_text="Continue the assigned desktop flow.",
            decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
            intent_kind="execute-task",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=True,
        )

    main_brain_orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_fake_resolver,
    )
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
    )
    request = AgentRequest(
        id="req-orchestrator-plan",
        session_id="sess-orchestrator-plan",
        user_id="user-orchestrator-plan",
        channel="console",
        input=[],
    )
    request.interaction_mode = "orchestrate"
    request.environment_ref = "desktop:session-1"

    streamed = [
        item
        async for item in executor.handle_query(
            msgs=[Msg(name="user", role="user", content="Continue the assigned desktop flow.")],
            request=request,
        )
    ]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "kernel done"
    assert len(query_execution_service.calls) == 1
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["execution_intent"] == "orchestrate"
    assert runtime_context["execution_mode"] == "environment-bound"
    assert main_brain_chat_service.calls == []


@pytest.mark.asyncio
async def test_main_brain_orchestrator_reuses_attached_intake_contract():
    query_execution_service = FakeQueryExecutionService()
    attached_contract = _make_main_brain_intake_contract(
        message_text="Continue the assigned desktop flow.",
        intent_kind="execute-task",
        kickoff_allowed=True,
    )

    async def _raising_resolver(**_kwargs):
        raise AssertionError("orchestrator should reuse attached intake contract")

    main_brain_orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_raising_resolver,
    )
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=FakeMainBrainChatService(),
        main_brain_orchestrator=main_brain_orchestrator,
    )
    request = AgentRequest(
        id="req-orchestrator-reuse-attached-intake",
        session_id="sess-orchestrator-reuse-attached-intake",
        user_id="user-orchestrator-reuse-attached-intake",
        channel="console",
        input=[],
    )
    request.interaction_mode = "orchestrate"
    request.environment_ref = "desktop:session-1"
    request._copaw_main_brain_intake_contract = attached_contract

    streamed = [
        item
        async for item in executor.handle_query(
            msgs=[Msg(name="user", role="user", content="Continue the assigned desktop flow.")],
            request=request,
        )
    ]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "kernel done"
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["source_intent_kind"] == "execute-task"


@pytest.mark.asyncio
async def test_kernel_turn_executor_syncs_environment_service_into_orchestrator_runtime_context():
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    persisted_session = SessionMount(
        id="session:console:desktop-session-1",
        environment_id="env:desktop:session-1",
        channel="console",
        session_id="desktop-session-1",
        lease_status="leased",
        lease_owner="ops-agent",
        lease_token="lease-persisted",
        live_handle_ref="live:desktop:session-1",
    )
    environment_service = FakeEnvironmentService(
        sessions={persisted_session.id: persisted_session},
    )

    async def _fake_resolver(**_kwargs):
        return MainBrainIntakeContract(
            message_text="Continue the assigned desktop flow.",
            decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
            intent_kind="execute-task",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=True,
        )

    main_brain_orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_fake_resolver,
    )
    executor = KernelTurnExecutor(
        session_backend=object(),
        environment_service=environment_service,
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
    )
    request = AgentRequest(
        id="req-orchestrator-plan-live-env",
        session_id="sess-orchestrator-plan-live-env",
        user_id="user-orchestrator-plan-live-env",
        channel="console",
        input=[],
    )
    request.interaction_mode = "orchestrate"
    request.environment_ref = "desktop:session-1"
    request.environment_session_id = persisted_session.id

    streamed = [
        item
        async for item in executor.handle_query(
            msgs=[Msg(name="user", role="user", content="Continue the assigned desktop flow.")],
            request=request,
        )
    ]

    assert len(streamed) == 1
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["environment_lease_token"] == "lease-persisted"
    assert runtime_context["environment_resume_ready"] is True
    assert runtime_context["recovery_mode"] == "resume-environment"


@pytest.mark.asyncio
async def test_main_brain_orchestrator_runtime_context_carries_cognitive_surface():
    class _CognitiveIndustryService:
        def get_instance_detail(self, instance_id: str) -> object:
            assert instance_id == "industry-v1-demo"
            return SimpleNamespace(
                instance_id=instance_id,
                current_cycle={
                    "synthesis": {
                        "latest_findings": [
                            {
                                "report_id": "report-weekend-1",
                                "headline": "Weekend variance review completed",
                                "summary": "Weekend variance still lacks a validated cause.",
                                "needs_followup": True,
                            },
                        ],
                        "conflicts": [
                            {
                                "kind": "result-mismatch",
                                "summary": "Reports disagree on assignment-shared.",
                                "report_ids": ["report-weekend-1", "report-weekend-2"],
                            },
                        ],
                        "holes": [
                            {
                                "kind": "followup-needed",
                                "summary": "Weekend variance still lacks a validated cause.",
                                "report_id": "report-weekend-1",
                            },
                        ],
                        "needs_replan": True,
                        "replan_reasons": [
                            "Reports disagree on assignment-shared.",
                            "Weekend variance still lacks a validated cause.",
                        ],
                    },
                },
            )

    query_execution_service = FakeQueryExecutionService()
    query_execution_service._industry_service = _CognitiveIndustryService()

    async def _fake_resolver(**_kwargs):
        return MainBrainIntakeContract(
            message_text="Continue the weekend variance closure.",
            decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
            intent_kind="execute-task",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=True,
        )

    main_brain_orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_fake_resolver,
    )
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=FakeMainBrainChatService(),
        main_brain_orchestrator=main_brain_orchestrator,
    )
    request = AgentRequest(
        id="req-orchestrator-cognitive-runtime",
        session_id="sess-orchestrator-cognitive-runtime",
        user_id="user-orchestrator-cognitive-runtime",
        channel="console",
        input=[],
    )
    request.interaction_mode = "orchestrate"
    request.industry_instance_id = "industry-v1-demo"

    streamed = [
        item
        async for item in executor.handle_query(
            msgs=[Msg(name="user", role="user", content="Continue the weekend variance closure.")],
            request=request,
        )
    ]

    assert len(streamed) == 1
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["cognitive"]["needs_replan"] is True
    assert runtime_context["cognitive"]["has_unresolved_conflicts"] is True
    assert runtime_context["cognitive"]["replan_reasons"] == [
        "Reports disagree on assignment-shared.",
        "Weekend variance still lacks a validated cause.",
    ]


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_routes_control_thread_execute_request_to_orchestrator(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    main_brain_orchestrator = FakeMainBrainOrchestrator()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
    )
    request = AgentRequest(
        id="req-auto-control-thread",
        session_id="sess-auto-control-thread",
        user_id="user-auto-control-thread",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    request.industry_instance_id = "industry-v1-demo"
    request.control_thread_id = "control-thread-1"
    msgs = [Msg(name="user", role="user", content="生成一份测试报告并推进下去")]

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _async_intake_resolver(
            _make_main_brain_intake_contract(
                message_text="生成一份测试报告并推进下去",
                intent_kind="execute-task",
                kickoff_allowed=True,
            ),
        ),
    )

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "orchestrator done"
    assert query_execution_service.calls == []
    assert len(main_brain_orchestrator.calls) == 1
    assert main_brain_chat_service.calls == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_routes_industry_execution_request_through_shared_intake(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-industry-shared-intake",
        session_id="sess-auto-industry-shared-intake",
        user_id="user-auto-industry-shared-intake",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    request.industry_instance_id = "industry-v1-demo"
    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _async_intake_resolver(
            _make_main_brain_intake_contract(
                message_text="把这件事接过去继续推进",
                intent_kind="execute-task",
                should_writeback=True,
                kickoff_allowed=True,
                writeback_plan=SimpleNamespace(active=True),
            ),
        ),
    )

    streamed = [
        item
        async for item in executor.handle_query(
            msgs=[Msg(name="user", role="user", content="把这件事接过去继续推进")],
            request=request,
        )
    ]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "kernel done"
    assert len(query_execution_service.calls) == 1
    assert main_brain_chat_service.calls == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_keeps_contextual_confirmation_in_chat_without_intake_result():
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-context-confirm",
        session_id="sess-auto-context-confirm",
        user_id="user-auto-context-confirm",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    msgs = [
        Msg(
            name="assistant",
            role="assistant",
            content="当前还没进入执行阶段。如果你确认，我下一条进入执行编排。",
        ),
        Msg(name="user", role="user", content="好的。"),
    ]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert query_execution_service.calls == []
    assert len(main_brain_chat_service.calls) == 1


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_keeps_plain_acknowledgement_in_chat_without_execution_context():
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-plain-ack",
        session_id="sess-auto-plain-ack",
        user_id="user-auto-plain-ack",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    msgs = [Msg(name="user", role="user", content="好的。")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert len(main_brain_chat_service.calls) == 1
    assert query_execution_service.calls == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_skips_intake_resolution_for_plain_ack_without_cognitive_pressure(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-ack-no-intake",
        session_id="sess-auto-ack-no-intake",
        user_id="user-auto-ack-no-intake",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    calls = 0

    async def _counting_resolver(**_kwargs):
        nonlocal calls
        calls += 1
        return _make_main_brain_intake_contract(
            intent_kind="execute-task",
            kickoff_allowed=True,
        )

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _counting_resolver,
    )
    msgs = [Msg(name="user", role="user", content="ok")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert len(main_brain_chat_service.calls) == 1
    assert query_execution_service.calls == []
    assert calls == 0


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_ignores_stale_cached_auto_orchestrate_for_new_plain_ack_turn():
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    main_brain_orchestrator = FakeMainBrainOrchestrator()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
    )
    request = AgentRequest(
        id="req-auto-stale-cache-ack",
        session_id="sess-auto-stale-cache-ack",
        user_id="user-auto-stale-cache-ack",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    request._copaw_requested_interaction_mode = "auto"
    request._copaw_resolved_interaction_mode = "orchestrate"
    request._copaw_interaction_mode_cache_key = "previous:execute-turn"
    msgs = [Msg(name="user", role="user", content="ok")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert len(main_brain_chat_service.calls) == 1
    assert len(main_brain_orchestrator.calls) == 0
    assert query_execution_service.calls == []
    assert request._copaw_requested_interaction_mode == "auto"
    assert request._copaw_resolved_interaction_mode == "chat"


@pytest.mark.asyncio
async def test_kernel_turn_executor_stream_request_reuses_auto_mode_resolution_for_same_turn(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-stream-cache-reuse",
        session_id="sess-stream-cache-reuse",
        user_id="user-stream-cache-reuse",
        channel="console",
        input=[
            {
                "role": "user",
                "content": [{"type": "text", "text": "Generate a report draft."}],
            },
        ],
    )
    request.interaction_mode = "auto"
    request.industry_instance_id = "industry-v1-demo"
    calls = 0

    async def _counting_resolver(**_kwargs):
        nonlocal calls
        calls += 1
        return _make_main_brain_intake_contract(intent_kind="chat")

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _counting_resolver,
    )

    message_events = []
    async for event in executor.stream_request(request):
        if getattr(event, "object", None) == "message":
            message_events.append(event)

    assert message_events
    assert message_events[-1].get_text_content() == "chat done"
    assert calls == 1
    assert len(main_brain_chat_service.calls) == 1
    assert query_execution_service.calls == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_routes_acknowledged_replan_to_orchestrator_when_cognitive_pressure_exists(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    main_brain_orchestrator = FakeMainBrainOrchestrator()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
    )
    request = AgentRequest(
        id="req-auto-cognitive-replan",
        session_id="sess-auto-cognitive-replan",
        user_id="user-auto-cognitive-replan",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    request._copaw_main_brain_runtime_context = {
        "cognitive": {
            "needs_replan": True,
            "conflicts": [
                {
                    "kind": "result-mismatch",
                    "summary": "Reports disagree on assignment-shared.",
                    "report_ids": ["report-weekend-1", "report-weekend-2"],
                },
            ],
            "holes": [],
            "replan_reasons": ["Reports disagree on assignment-shared."],
        },
    }
    msgs = [
        Msg(
            name="assistant",
            role="assistant",
            content="两个报告还没对齐，当前需要主脑直接重排并补缺口。",
        ),
        Msg(name="user", role="user", content="好的，按这个继续推进。"),
    ]

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _async_intake_resolver(None),
    )

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "orchestrator done"
    assert len(main_brain_orchestrator.calls) == 1
    assert main_brain_chat_service.calls == []
    assert query_execution_service.calls == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_keeps_short_inspection_request_in_chat_without_intake_result(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    kernel_dispatcher = FakeKernelDispatcher()
    executor = KernelTurnExecutor(
        session_backend=object(),
        kernel_dispatcher=kernel_dispatcher,
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-needs-human",
        session_id="sess-auto-needs-human",
        user_id="user-auto-needs-human",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    msgs = [Msg(name="user", role="user", content="帮我看一下")]
    calls = 0

    async def _counting_resolver(**_kwargs):
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _counting_resolver,
    )

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert streamed[0][1] is True
    assert query_execution_service.calls == []
    assert len(main_brain_chat_service.calls) == 1
    assert kernel_dispatcher.submitted == []
    assert calls == 0


@pytest.mark.asyncio
async def test_kernel_turn_executor_stream_request_attaches_resolved_interaction_mode_metadata(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )

    request = AgentRequest(
        id="req-stream-chat-meta",
        session_id="sess-stream-chat-meta",
        user_id="user-stream-chat-meta",
        channel="console",
        input=[
            {
                "role": "user",
                "content": [{"type": "text", "text": "这是什么？"}],
            },
        ],
    )
    request.interaction_mode = "auto"

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _async_intake_resolver(None),
    )

    found = False
    async for event in executor.stream_request(request):
        if getattr(event, "object", None) != "message":
            continue
        meta = getattr(event, "metadata", None)
        assert isinstance(meta, dict)
        assert meta.get("resolved_interaction_mode") == "chat"
        found = True
        break
    assert found is True

    request2 = AgentRequest(
        id="req-stream-orchestrate-meta",
        session_id="sess-stream-orchestrate-meta",
        user_id="user-stream-orchestrate-meta",
        channel="console",
        input=[
            {
                "role": "user",
                "content": [{"type": "text", "text": "生成一份测试报告"}],
            },
        ],
    )
    request2.interaction_mode = "auto"

    found2 = False
    async for event in executor.stream_request(request2):
        if getattr(event, "object", None) != "message":
            continue
        meta = getattr(event, "metadata", None)
        assert isinstance(meta, dict)
        assert meta.get("resolved_interaction_mode") == "chat"
        found2 = True
        break
    assert found2 is True

    request3 = AgentRequest(
        id="req-stream-control-thread-meta",
        session_id="sess-stream-control-thread-meta",
        user_id="user-stream-control-thread-meta",
        channel="console",
        input=[
            {
                "role": "user",
                "content": [{"type": "text", "text": "生成一份测试报告"}],
            },
        ],
    )
    request3.interaction_mode = "auto"
    request3.industry_instance_id = "industry-v1-demo"
    request3.control_thread_id = "control-thread-1"

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _async_intake_resolver(
            _make_main_brain_intake_contract(
                message_text="生成一份测试报告",
                intent_kind="execute-task",
                kickoff_allowed=True,
            ),
        ),
    )

    found3 = False
    async for event in executor.stream_request(request3):
        if getattr(event, "object", None) != "message":
            continue
        meta = getattr(event, "metadata", None)
        assert isinstance(meta, dict)
        assert meta.get("resolved_interaction_mode") == "orchestrate"
        found3 = True
        break
    assert found3 is True

def test_kernel_turn_executor_syncs_shared_query_execution_service_dependencies() -> None:
    session_backend = object()
    kernel_dispatcher = FakeKernelDispatcher()
    executor = KernelTurnExecutor(
        session_backend=session_backend,
        kernel_dispatcher=kernel_dispatcher,
    )
    query_execution_service = FakeQueryExecutionService()

    executor.set_query_execution_service(query_execution_service)

    assert executor._query_execution_service is query_execution_service
    assert query_execution_service.synced["session_backend"] is session_backend
    assert query_execution_service.synced["kernel_dispatcher"] is kernel_dispatcher


def test_kernel_turn_executor_syncs_conversation_compaction_service_without_legacy_memory_manager() -> None:
    conversation_compaction_service = object()
    query_execution_service = FakeQueryExecutionService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        conversation_compaction_service=conversation_compaction_service,
    )

    executor.set_query_execution_service(query_execution_service)

    assert (
        query_execution_service.synced["conversation_compaction_service"]
        is conversation_compaction_service
    )
    assert not hasattr(KernelTurnExecutor, "set_memory_manager")


def test_runtime_host_syncs_turn_executor_session_backend() -> None:
    host = RuntimeHost(session_backend=object())
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )

    host.sync_turn_executor(executor)

    assert query_execution_service.synced["session_backend"] is host.session_backend
    assert main_brain_chat_service.synced["session_backend"] is host.session_backend
    assert not hasattr(RuntimeHost, "memory_manager")
    assert not hasattr(RuntimeHost, "set_memory_manager")


@pytest.mark.asyncio
async def test_runtime_host_starts_conversation_compaction_service_without_memory_manager(
    monkeypatch,
) -> None:
    memory_manager_started: list[str] = []
    compaction_service_started: list[object] = []

    class FakeMemoryManager:
        def __init__(self, **_kwargs) -> None:
            memory_manager_started.append("created")

        async def start(self) -> None:
            memory_manager_started.append("started")

        async def close(self) -> None:
            memory_manager_started.append("closed")

    class FakeConversationCompactionService:
        def __init__(self, **_kwargs) -> None:
            compaction_service_started.append(self)

        async def start(self) -> None:
            compaction_service_started.append("started")

        async def close(self) -> None:
            compaction_service_started.append("closed")

    monkeypatch.setattr(
        "copaw.app.runtime_host.MemoryManager",
        FakeMemoryManager,
        raising=False,
    )
    monkeypatch.setattr(
        "copaw.app.runtime_host.ConversationCompactionService",
        FakeConversationCompactionService,
        raising=False,
    )

    host = RuntimeHost(session_backend=object())
    await host.start()
    await host.stop()

    assert memory_manager_started == []
    assert compaction_service_started[1:] == ["started", "closed"]


def test_query_confirmation_policy_change_helper_removed() -> None:
    assert not hasattr(
        query_execution_shared_module,
        "_resolve_query_confirmation_policy_change_request",
    )


def test_team_role_gap_action_request_accepts_requested_actions_and_explicit_text() -> None:
    request = SimpleNamespace(requested_actions=["approve_team_role_gap"])
    assert (
        query_execution_shared_module._resolve_team_role_gap_action_request(
            text="just chat",
            request=request,
        )
        == "approve"
    )
    assert (
        query_execution_shared_module._resolve_team_role_gap_action_request(
            text="approve the gap",
        )
        == "approve"
    )
    assert (
        query_execution_shared_module._resolve_team_role_gap_action_request(
            text="reject the gap",
        )
        == "reject"
    )
    assert (
        query_execution_shared_module._resolve_team_role_gap_action_request(
            text="if we approve the gap, what happens next?",
        )
        is None
    )


def test_team_role_gap_notice_and_kickoff_helpers_only_honor_explicit_actions() -> None:
    assert query_execution_shared_module._should_surface_team_role_gap_notice(
        text="what should we do next",
    )
    assert not query_execution_shared_module._should_surface_team_role_gap_notice(
        text="explain the current plan first",
    )
    assert not query_execution_shared_module._should_trigger_industry_kickoff(
        text="start now and summarize the competitors",
    )
    assert query_execution_shared_module._should_trigger_industry_kickoff(
        request=SimpleNamespace(requested_actions=["kickoff_execution"]),
    )


def test_formal_chat_writeback_helper_only_honors_explicit_actions() -> None:
    assert not query_execution_shared_module._should_attempt_formal_chat_writeback(
        text="from now on, keep this as the team's default operating rule",
    )
    assert not query_execution_shared_module._should_attempt_formal_chat_writeback(
        text="我要在3个月内把这个账号做到月营收10万",
    )
    assert query_execution_shared_module._should_attempt_formal_chat_writeback(
        request=SimpleNamespace(requested_actions=["writeback_backlog"]),
    )
    assert not query_execution_shared_module._should_attempt_formal_chat_writeback(
        text="explain the current plan first",
    )


def test_query_execution_runtime_writeback_plan_no_longer_depends_on_text_gate(
    monkeypatch,
) -> None:
    service = KernelQueryExecutionService(session_backend=object())
    request = SimpleNamespace(
        _copaw_main_brain_intake_contract=_make_main_brain_intake_contract(
            message_text="model",
            intent_kind="discussion",
            should_writeback=True,
            writeback_plan=SimpleNamespace(active=True),
        ),
    )

    monkeypatch.setattr(
        "copaw.kernel.query_execution_runtime._should_attempt_formal_chat_writeback",
        lambda **_kwargs: False,
    )
    plan = service._resolve_requested_chat_writeback_plan(  # pylint: disable=protected-access
        msgs=[Msg(name="user", role="user", content="先按这个方向长期推进")],
        request=request,
    )

    assert plan is not None
    assert plan.active is True


def test_query_execution_runtime_writeback_plan_requires_attached_intake_contract() -> None:
    service = KernelQueryExecutionService(session_backend=object())

    plan = service._resolve_requested_chat_writeback_plan(  # pylint: disable=protected-access
        msgs=[Msg(name="user", role="user", content="先按这个方向长期推进")],
        request=SimpleNamespace(),
    )

    assert plan is None


@pytest.mark.asyncio
async def test_query_execution_team_kickoff_uses_attached_intake_contract_even_without_text_gate():
    industry_service = _FakeIndustryServiceForAsyncIntake()
    service = KernelQueryExecutionService(
        session_backend=object(),
        industry_service=industry_service,
    )
    request = SimpleNamespace(
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        session_id="sess-kickoff",
        channel="console",
        _copaw_main_brain_intake_contract=_make_main_brain_intake_contract(
            message_text="接过去往前推",
            intent_kind="execute-task",
            kickoff_allowed=True,
        ),
    )

    result = await service._apply_industry_chat_kickoff_intent(  # pylint: disable=protected-access
        msgs=[Msg(name="user", role="user", content="接过去往前推")],
        request=request,
        owner_agent_id="copaw-agent-runner",
        agent_profile=None,
    )

    assert result == {"activated": True}
    assert len(industry_service.kickoff_calls) == 1


@pytest.mark.asyncio
async def test_query_execution_team_kickoff_requires_attached_intake_contract():
    industry_service = _FakeIndustryServiceForAsyncIntake()
    service = KernelQueryExecutionService(
        session_backend=object(),
        industry_service=industry_service,
    )

    result = await service._apply_industry_chat_kickoff_intent(  # pylint: disable=protected-access
        msgs=[Msg(name="user", role="user", content="接过去往前推")],
        request=SimpleNamespace(
            industry_instance_id="industry-v1-demo",
            industry_role_id="execution-core",
            session_id="sess-kickoff",
            channel="console",
        ),
        owner_agent_id="copaw-agent-runner",
        agent_profile=None,
    )

    assert result is None
    assert industry_service.kickoff_calls == []


@pytest.mark.asyncio
async def test_query_execution_team_kickoff_reuses_attached_intake_contract(
    monkeypatch,
):
    industry_service = _FakeIndustryServiceForAsyncIntake()
    service = KernelQueryExecutionService(
        session_backend=object(),
        industry_service=industry_service,
    )

    request = SimpleNamespace(
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        session_id="sess-kickoff",
        channel="console",
        _copaw_main_brain_intake_contract=MainBrainIntakeContract(
            message_text="接过去往前推",
            decision=SimpleNamespace(),
            intent_kind="execute-task",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=True,
        ),
    )

    result = await service._apply_industry_chat_kickoff_intent(  # pylint: disable=protected-access
        msgs=[Msg(name="user", role="user", content="接过去往前推")],
        request=request,
        owner_agent_id="copaw-agent-runner",
        agent_profile=None,
    )

    assert result == {"activated": True}
    assert len(industry_service.kickoff_calls) == 1
    assert industry_service.kickoff_calls[0]["message_text"] == "接过去往前推"


@pytest.mark.asyncio
async def test_kernel_turn_executor_control_thread_execute_request_no_longer_relies_on_chat_background_work(
    monkeypatch,
):
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    main_brain_orchestrator = FakeMainBrainOrchestrator()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
        main_brain_orchestrator=main_brain_orchestrator,
    )
    request = AgentRequest(
        id="req-control-thread-async",
        session_id="sess-control-thread-async",
        user_id="user-control-thread-async",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    request.industry_instance_id = "industry-v1-demo"
    request.industry_role_id = "execution-core"
    request.control_thread_id = "control-thread-1"

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.resolve_request_main_brain_intake_contract",
        _async_intake_resolver(
            _make_main_brain_intake_contract(
                message_text="把这个需求接过去，持续推进",
                intent_kind="execute-task",
                should_writeback=True,
                kickoff_allowed=True,
                writeback_plan=SimpleNamespace(active=True),
            ),
        ),
    )

    streamed = [
        item
        async for item in executor.handle_query(
            msgs=[Msg(name="user", role="user", content="把这个需求接过去，持续推进")],
            request=request,
        )
    ]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "orchestrator done"
    assert len(main_brain_orchestrator.calls) == 1
    assert main_brain_chat_service.calls == []
    assert query_execution_service.calls == []


@pytest.mark.asyncio
async def test_query_execution_runtime_reuses_shared_intake_contract_for_writeback_and_kickoff(
    monkeypatch,
):
    industry_service = _FakeIndustryServiceForAsyncIntake()
    service = KernelQueryExecutionService(
        session_backend=object(),
        industry_service=industry_service,
    )
    writeback_plan = SimpleNamespace(active=True, anchor="runtime-shared-contract")
    request = SimpleNamespace(
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        session_id="sess-shared-intake",
        channel="console",
        _copaw_main_brain_intake_contract=_make_main_brain_intake_contract(
            message_text="把这件事接过去，继续往前推",
            intent_kind="execute-task",
            should_writeback=True,
            kickoff_allowed=True,
            writeback_plan=writeback_plan,
        ),
    )
    monkeypatch.setattr(
        "copaw.kernel.main_brain_intake.resolve_request_main_brain_intake_contract",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("runtime async code should reuse attached intake contract"),
        ),
        raising=False,
    )

    chat_writeback_summary, industry_kickoff_summary = (
        await service._apply_requested_main_brain_intake(  # pylint: disable=protected-access
            msgs=[Msg(name="user", role="user", content="把这件事接过去，继续往前推")],
            request=request,
            owner_agent_id="copaw-agent-runner",
            agent_profile=None,
        )
    )

    assert chat_writeback_summary == {"applied": True}
    assert industry_kickoff_summary == {"activated": True}
    assert len(industry_service.writeback_calls) == 1
    assert industry_service.writeback_calls[0]["writeback_plan"] is writeback_plan
    assert len(industry_service.kickoff_calls) == 1


@pytest.mark.asyncio
async def test_query_execution_runtime_requested_main_brain_intake_requires_attached_contract(
    monkeypatch,
):
    industry_service = _FakeIndustryServiceForAsyncIntake()
    service = KernelQueryExecutionService(
        session_backend=object(),
        industry_service=industry_service,
    )

    monkeypatch.setattr(
        "copaw.kernel.main_brain_intake.resolve_request_main_brain_intake_contract",
        _async_intake_resolver(
            _make_main_brain_intake_contract(
                message_text="fallback",
                intent_kind="execute-task",
                should_writeback=True,
                kickoff_allowed=True,
                writeback_plan=SimpleNamespace(active=True),
            ),
        ),
        raising=False,
    )

    chat_writeback_summary, industry_kickoff_summary = (
        await service._apply_requested_main_brain_intake(  # pylint: disable=protected-access
            msgs=[Msg(name="user", role="user", content="把这件事接过去，继续往前推")],
            request=SimpleNamespace(
                industry_instance_id="industry-v1-demo",
                industry_role_id="execution-core",
                session_id="sess-shared-intake",
                channel="console",
            ),
            owner_agent_id="copaw-agent-runner",
            agent_profile=None,
        )
    )

    assert chat_writeback_summary is None
    assert industry_kickoff_summary is None
    assert industry_service.writeback_calls == []
    assert industry_service.kickoff_calls == []


def test_tool_preflight_allows_host_observation_without_explicit_request() -> None:
    service = KernelQueryExecutionService(session_backend=object())
    preflight = service._build_tool_preflight(
        delegation_guard=None,
        msgs=[Msg(name="user", role="user", content="what are you doing right now?")],
    )

    assert callable(preflight)
    assert preflight("get_foreground_window") is None


def test_tool_preflight_keeps_host_observation_open_when_requested_action_present() -> None:
    service = KernelQueryExecutionService(session_backend=object())
    preflight = service._build_tool_preflight(
        delegation_guard=None,
        msgs=[Msg(name="user", role="user", content="what is the active window?")],
        request=SimpleNamespace(requested_actions=["inspect_host"]),
    )

    assert callable(preflight)
    assert preflight("desktop_screenshot") is None


@pytest.mark.asyncio
async def test_kernel_turn_executor_stream_request_localizes_model_upstream_error():
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=FailingQueryExecutionService(),
    )
    request = AgentRequest(
        id="req-connection",
        session_id="sess-connection",
        user_id="user-connection",
        channel="console",
        input=[],
    )

    events = [event async for event in executor.stream_request(request)]

    final_response = events[-1]
    assert final_response.status == RunStatus.Failed
    assert final_response.error is not None
    assert final_response.error.code == "模型连接失败"
    assert "模型上游连接异常" in final_response.error.message
@pytest.mark.asyncio
async def test_kernel_turn_executor_stream_request_marks_cancellation_as_canceled():
    kernel_dispatcher = FakeKernelDispatcher()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=CancelledQueryExecutionService(),
        kernel_dispatcher=kernel_dispatcher,
    )
    request = AgentRequest(
        id="req-cancelled",
        session_id="sess-cancelled",
        user_id="user-cancelled",
        channel="console",
        input=[],
    )

    events = [event async for event in executor.stream_request(request)]

    final_response = events[-1]
    assert final_response.status == RunStatus.Canceled
    assert kernel_dispatcher.failed == []
    assert len(kernel_dispatcher.cancelled) == 1
    assert kernel_dispatcher.cancelled[0][1] == "查询在完成前已被取消。"


@pytest.mark.asyncio
async def test_kernel_turn_executor_persists_response_usage(monkeypatch):
    query_execution_service = FakeQueryExecutionService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
    )
    request = AgentRequest(
        id="req-usage",
        session_id="sess-usage",
        user_id="user-usage",
        channel="console",
        input=[],
    )

    async def _fake_adapt_agentscope_message_stream(**_kwargs):
        yield SimpleNamespace(
            status=RunStatus.Completed,
            object="message",
            usage={
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            },
        )

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.adapt_agentscope_message_stream",
        _fake_adapt_agentscope_message_stream,
    )

    events = [event async for event in executor.stream_request(request)]

    assert events[-1].usage == {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }
    assert query_execution_service.recorded_usage == [
        {
            "request": request,
            "kernel_task_id": None,
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            },
        },
    ]


@pytest.mark.asyncio
async def test_kernel_turn_executor_skips_usage_persistence_for_chat_mode(monkeypatch):
    query_execution_service = FakeQueryExecutionService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=FakeMainBrainChatService(),
    )
    request = AgentRequest(
        id="req-chat-usage",
        session_id="sess-chat-usage",
        user_id="user-chat-usage",
        channel="console",
        input=[],
    )
    request.interaction_mode = "chat"

    async def _fake_adapt_agentscope_message_stream(**_kwargs):
        yield SimpleNamespace(
            status=RunStatus.Completed,
            object="message",
            usage={
                "prompt_tokens": 5,
                "completion_tokens": 3,
                "total_tokens": 8,
            },
        )

    monkeypatch.setattr(
        "copaw.kernel.turn_executor.adapt_agentscope_message_stream",
        _fake_adapt_agentscope_message_stream,
    )

    events = [event async for event in executor.stream_request(request)]

    assert events[-1].usage == {
        "prompt_tokens": 5,
        "completion_tokens": 3,
        "total_tokens": 8,
    }
    assert query_execution_service.recorded_usage == []
