# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pytest
from agentscope.message import Msg
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from copaw.kernel.main_brain_intake import MainBrainIntakeContract
from copaw.kernel.main_brain_orchestrator import MainBrainExecutionEnvelope, MainBrainOrchestrator


class _FakeQueryExecutionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield Msg(name="assistant", role="assistant", content="delegated through orchestrator"), True


@pytest.mark.asyncio
async def test_main_brain_orchestrator_executes_formal_turn_through_query_execution_service():
    query_execution_service = _FakeQueryExecutionService()
    orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
    )
    request = AgentRequest(
        id="req-orchestrator",
        session_id="sess-orchestrator",
        user_id="user-orchestrator",
        channel="console",
        input=[],
    )
    msgs = [Msg(name="user", role="user", content="把这个目标接过去并开始安排执行")]

    streamed = [
        item
        async for item in orchestrator.execute_stream(
            msgs=msgs,
            request=request,
            kernel_task_id="kernel-task-1",
        )
    ]

    assert len(streamed) == 1
    assert streamed[0][0].get_text_content() == "delegated through orchestrator"
    assert streamed[0][1] is True
    assert query_execution_service.calls[0]["msgs"] == msgs
    assert query_execution_service.calls[0]["request"] is request
    assert query_execution_service.calls[0]["kernel_task_id"] == "kernel-task-1"


@pytest.mark.asyncio
async def test_main_brain_orchestrator_attaches_intake_context_to_request():
    query_execution_service = _FakeQueryExecutionService()
    intake_contract = MainBrainIntakeContract(
        message_text="把这个目标接过去并开始安排执行",
        decision=SimpleNamespace(intent_kind="execute-task"),
        intent_kind="execute-task",
        writeback_requested=True,
        writeback_plan=SimpleNamespace(active=True),
        should_kickoff=True,
    )

    async def _fake_resolver(**_kwargs):
        return intake_contract

    orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_fake_resolver,
    )
    request = AgentRequest(
        id="req-orchestrator-context",
        session_id="sess-orchestrator-context",
        user_id="user-orchestrator-context",
        channel="console",
        input=[],
    )
    msgs = [Msg(name="user", role="user", content="把这个目标接过去并开始安排执行")]

    streamed = [
        item
        async for item in orchestrator.execute_stream(
            msgs=msgs,
            request=request,
            kernel_task_id="kernel-task-context",
        )
    ]

    assert len(streamed) == 1
    assert getattr(request, "_copaw_main_brain_intake_contract") is intake_contract
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["source_intent_kind"] == "execute-task"
    assert runtime_context["writeback_requested"] is True
    assert runtime_context["should_kickoff"] is True
    assert not hasattr(request, "_copaw_main_brain_intent_kind")
    assert not hasattr(request, "_copaw_main_brain_writeback_requested")
    assert not hasattr(request, "_copaw_main_brain_should_kickoff")
    assert getattr(request, "_copaw_kernel_task_id") == "kernel-task-context"


@pytest.mark.asyncio
async def test_main_brain_orchestrator_envelope_exposes_execution_kwargs():
    intake_contract = MainBrainIntakeContract(
        message_text="安排执行",
        decision=SimpleNamespace(intent_kind="execute-task"),
        intent_kind="execute-task",
        writeback_requested=False,
        writeback_plan=None,
        should_kickoff=True,
    )
    request = SimpleNamespace()
    msgs = [Msg(name="user", role="user", content="安排执行")]
    envelope = MainBrainExecutionEnvelope(
        msgs=msgs,
        request=request,
        kernel_task_id="kernel-task-envelope",
        transient_input_message_ids={"input-1"},
        intake_contract=intake_contract,
    )

    assert envelope.execution_kwargs == {
        "msgs": msgs,
        "request": request,
        "kernel_task_id": "kernel-task-envelope",
        "transient_input_message_ids": {"input-1"},
    }
    assert envelope.intake_contract is intake_contract


def test_main_brain_orchestrator_allows_query_execution_service_rebinding():
    original = _FakeQueryExecutionService()
    replacement = _FakeQueryExecutionService()
    orchestrator = MainBrainOrchestrator(query_execution_service=original)

    orchestrator.set_query_execution_service(replacement)

    assert orchestrator._query_execution_service is replacement  # pylint: disable=protected-access


@pytest.mark.asyncio
async def test_main_brain_orchestrator_passes_request_into_intake_resolver():
    query_execution_service = _FakeQueryExecutionService()
    captured: dict[str, object] = {}

    async def _fake_resolver(**kwargs):
        captured.update(kwargs)
        return None

    orchestrator = MainBrainOrchestrator(
        query_execution_service=query_execution_service,
        intake_contract_resolver=_fake_resolver,
    )
    request = AgentRequest(
        id="req-orchestrator-request-aware",
        session_id="sess-orchestrator-request-aware",
        user_id="user-orchestrator-request-aware",
        channel="console",
        input=[],
    )
    msgs = [Msg(name="user", role="user", content="把这条需求写回 backlog。")]

    streamed = [
        item
        async for item in orchestrator.execute_stream(
            msgs=msgs,
            request=request,
            kernel_task_id="kernel-task-request-aware",
        )
    ]

    assert len(streamed) == 1
    assert captured["request"] is request
    assert captured["msgs"] == msgs
