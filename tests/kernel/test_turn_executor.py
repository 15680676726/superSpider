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

    def submit(self, task):
        self.submitted.append(task)
        return KernelResult(task_id=task.id, success=True, phase="executing")

    def complete_task(self, task_id: str, *, summary: str, metadata=None) -> None:
        self.completed.append((task_id, summary, metadata))

    def fail_task(self, task_id: str, *, error: str) -> None:
        self.failed.append((task_id, error))


class FailingQueryExecutionService(FakeQueryExecutionService):
    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        raise RuntimeError("Connection error.")
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
async def test_kernel_turn_executor_auto_mode_routes_action_instructions_to_query_execution_service():
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

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "kernel done"
    assert streamed[0][1] is True
    assert query_execution_service.calls != []
    assert main_brain_chat_service.calls == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_recognizes_natural_execution_request():
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-natural-orchestrate",
        session_id="sess-auto-natural-orchestrate",
        user_id="user-auto-natural-orchestrate",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    msgs = [Msg(name="user", role="user", content="那你开始吧，直接推进下去")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "kernel done"
    assert query_execution_service.calls != []
    assert main_brain_chat_service.calls == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_routes_goal_setting_to_query_execution_service():
    query_execution_service = FakeQueryExecutionService()
    main_brain_chat_service = FakeMainBrainChatService()
    executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=main_brain_chat_service,
    )
    request = AgentRequest(
        id="req-auto-goal-orchestrate",
        session_id="sess-auto-goal-orchestrate",
        user_id="user-auto-goal-orchestrate",
        channel="console",
        input=[],
    )
    request.interaction_mode = "auto"
    msgs = [Msg(name="user", role="user", content="我要在3个月内把这个账号做到月营收10万")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "kernel done"
    assert query_execution_service.calls != []
    assert main_brain_chat_service.calls == []


@pytest.mark.asyncio
async def test_kernel_turn_executor_auto_mode_prefers_model_resolution_for_main_brain_request(
    monkeypatch,
):
    from copaw.kernel.main_brain_intake import MainBrainIntakeContract

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
        "copaw.kernel.turn_executor.resolve_main_brain_intake_contract_sync",
        lambda **_kwargs: MainBrainIntakeContract(
            message_text="model",
            decision=SimpleNamespace(
                intent_kind="execute-task",
                kickoff_allowed=True,
                explicit_execution_confirmation=False,
                should_writeback=False,
            ),
            intent_kind="execute-task",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=True,
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
    from copaw.kernel.main_brain_intake import MainBrainIntakeContract

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
        "copaw.kernel.turn_executor.resolve_main_brain_intake_contract_sync",
        lambda **_kwargs: MainBrainIntakeContract(
            message_text="model",
            decision=SimpleNamespace(
                intent_kind="chat",
                kickoff_allowed=False,
                explicit_execution_confirmation=False,
                should_writeback=False,
            ),
            intent_kind="chat",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=False,
        ),
    )
    msgs = [Msg(name="user", role="user", content="帮我看一下")]

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "chat done"
    assert query_execution_service.calls == []
    assert len(main_brain_chat_service.calls) == 1


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
async def test_kernel_turn_executor_auto_mode_routes_control_thread_execute_request_to_orchestrator(
    monkeypatch,
):
    from copaw.kernel.main_brain_intake import MainBrainIntakeContract

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
        "copaw.kernel.turn_executor.resolve_main_brain_intake_contract_sync",
        lambda **_kwargs: MainBrainIntakeContract(
            message_text="生成一份测试报告并推进下去",
            decision=SimpleNamespace(
                intent_kind="execute-task",
                kickoff_allowed=True,
                explicit_execution_confirmation=False,
                should_writeback=False,
            ),
            intent_kind="execute-task",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=True,
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
    from copaw.kernel.main_brain_intake import MainBrainIntakeContract

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
        "copaw.kernel.turn_executor.resolve_main_brain_intake_contract_sync",
        lambda **_kwargs: MainBrainIntakeContract(
            message_text="把这件事接过去继续推进",
            decision=SimpleNamespace(
                intent_kind="execute-task",
                should_writeback=True,
                kickoff_allowed=True,
                explicit_execution_confirmation=False,
            ),
            intent_kind="execute-task",
            writeback_requested=True,
            writeback_plan=SimpleNamespace(active=True),
            should_kickoff=True,
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
async def test_kernel_turn_executor_auto_mode_recognizes_contextual_execution_confirmation():
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
    assert streamed[0][0].get_text_content() == "kernel done"
    assert query_execution_service.calls != []
    assert main_brain_chat_service.calls == []


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
async def test_kernel_turn_executor_auto_mode_routes_short_inspection_request_to_query_execution_service():
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

    streamed = [item async for item in executor.handle_query(msgs=msgs, request=request)]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "kernel done"
    assert streamed[0][1] is True
    assert query_execution_service.calls != []
    assert main_brain_chat_service.calls == []
    assert kernel_dispatcher.submitted != []


@pytest.mark.asyncio
async def test_kernel_turn_executor_stream_request_attaches_resolved_interaction_mode_metadata(
    monkeypatch,
):
    from copaw.kernel.main_brain_intake import MainBrainIntakeContract

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
        assert meta.get("resolved_interaction_mode") == "orchestrate"
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
        "copaw.kernel.turn_executor.resolve_main_brain_intake_contract_sync",
        lambda **_kwargs: MainBrainIntakeContract(
            message_text="生成一份测试报告",
            decision=SimpleNamespace(
                intent_kind="execute-task",
                kickoff_allowed=True,
                explicit_execution_confirmation=False,
                should_writeback=False,
            ),
            intent_kind="execute-task",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=True,
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
    from copaw.kernel.main_brain_intake import MainBrainIntakeContract

    service = KernelQueryExecutionService(session_backend=object())

    monkeypatch.setattr(
        "copaw.kernel.query_execution_runtime._should_attempt_formal_chat_writeback",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        "copaw.kernel.query_execution_runtime.resolve_request_main_brain_intake_contract_sync",
        lambda **_kwargs: MainBrainIntakeContract(
            message_text="model",
            decision=SimpleNamespace(should_writeback=True),
            intent_kind="discussion",
            writeback_requested=True,
            writeback_plan=SimpleNamespace(active=True),
            should_kickoff=False,
        ),
    )

    plan = service._resolve_requested_chat_writeback_plan(  # pylint: disable=protected-access
        msgs=[Msg(name="user", role="user", content="先按这个方向长期推进")],
        request=SimpleNamespace(),
    )

    assert plan is not None
    assert plan.active is True


@pytest.mark.asyncio
async def test_query_execution_team_kickoff_uses_model_decision_even_without_text_gate(
    monkeypatch,
):
    industry_service = _FakeIndustryServiceForAsyncIntake()
    service = KernelQueryExecutionService(
        session_backend=object(),
        industry_service=industry_service,
    )

    monkeypatch.setattr(
        "copaw.kernel.query_execution_team.resolve_request_main_brain_intake_contract_sync",
        lambda **_kwargs: MainBrainIntakeContract(
            message_text="接过去往前推",
            decision=SimpleNamespace(
                kickoff_allowed=True,
                explicit_execution_confirmation=False,
            ),
            intent_kind="execute-task",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=True,
        ),
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

    assert result == {"activated": True}
    assert len(industry_service.kickoff_calls) == 1


@pytest.mark.asyncio
async def test_query_execution_team_kickoff_reuses_attached_intake_contract(
    monkeypatch,
):
    industry_service = _FakeIndustryServiceForAsyncIntake()
    service = KernelQueryExecutionService(
        session_backend=object(),
        industry_service=industry_service,
    )

    monkeypatch.setattr(
        "copaw.kernel.main_brain_intake.resolve_main_brain_intake_contract_sync",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("team kickoff should reuse the attached intake contract"),
        ),
    )
    monkeypatch.setattr(
        "copaw.kernel.query_execution_shared._resolve_chat_writeback_model_decision_sync",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("team kickoff should not re-run model decision when contract exists"),
        ),
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
    from copaw.kernel.main_brain_intake import MainBrainIntakeContract

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
        "copaw.kernel.turn_executor.resolve_main_brain_intake_contract_sync",
        lambda **_kwargs: MainBrainIntakeContract(
            message_text="把这个需求接过去，持续推进",
            decision=SimpleNamespace(
                intent_kind="execute-task",
                kickoff_allowed=True,
                explicit_execution_confirmation=False,
                should_writeback=True,
            ),
            intent_kind="execute-task",
            writeback_requested=True,
            writeback_plan=SimpleNamespace(active=True),
            should_kickoff=True,
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
    from copaw.kernel.main_brain_intake import materialize_main_brain_intake_contract

    industry_service = _FakeIndustryServiceForAsyncIntake()
    service = KernelQueryExecutionService(
        session_backend=object(),
        industry_service=industry_service,
    )
    request = SimpleNamespace(
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        session_id="sess-shared-intake",
        channel="console",
    )
    writeback_plan = SimpleNamespace(active=True, anchor="runtime-shared-contract")
    resolve_calls: list[str] = []
    sync_calls: list[str] = []

    async def _fake_resolve(*, request=None, msgs=None):
        _ = request
        text: str | None = None
        if text is None:
            assert msgs is not None
            text = msgs[-1].get_text_content()
        resolve_calls.append(text)
        contract = materialize_main_brain_intake_contract(
            message_text=text,
            decision=SimpleNamespace(
                intent_kind="execute-task",
                should_writeback=True,
                approved_targets=["backlog"],
                strategy=None,
                goal=None,
                schedule=None,
                kickoff_allowed=True,
                explicit_execution_confirmation=False,
            ),
        )
        assert contract is not None
        contract.writeback_plan = writeback_plan
        return contract

    monkeypatch.setattr(
        "copaw.kernel.query_execution_runtime.resolve_request_main_brain_intake_contract",
        _fake_resolve,
        raising=False,
    )
    monkeypatch.setattr(
        "copaw.kernel.query_execution_runtime.resolve_request_main_brain_intake_contract_sync",
        lambda **_kwargs: sync_calls.append("sync") or (_ for _ in ()).throw(
            AssertionError("sync intake resolver should not be used from runtime async code"),
        ),
    )

    chat_writeback_summary, industry_kickoff_summary = (
        await service._apply_requested_main_brain_intake(  # pylint: disable=protected-access
            msgs=[Msg(name="user", role="user", content="把这件事接过去，继续往前推")],
            request=request,
            owner_agent_id="copaw-agent-runner",
            agent_profile=None,
        )
    )

    assert resolve_calls == ["把这件事接过去，继续往前推"]
    assert sync_calls == []
    assert chat_writeback_summary == {"applied": True}
    assert industry_kickoff_summary == {"activated": True}
    assert len(industry_service.writeback_calls) == 1
    assert industry_service.writeback_calls[0]["writeback_plan"] is writeback_plan
    assert len(industry_service.kickoff_calls) == 1


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
