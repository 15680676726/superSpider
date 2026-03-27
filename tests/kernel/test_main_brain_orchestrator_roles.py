# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pytest
from agentscope.message import Msg
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from copaw.environments.models import SessionMount
from copaw.kernel.main_brain_intake import MainBrainIntakeContract
from copaw.kernel.main_brain_orchestrator import MainBrainOrchestrator


class _FakeQueryExecutionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield Msg(name="assistant", role="assistant", content="planned by orchestrator"), True


class _FakeEnvironmentService:
    def __init__(self, *, sessions: dict[str, SessionMount] | None = None) -> None:
        self._sessions = sessions or {}

    def get_session(self, session_mount_id: str) -> SessionMount | None:
        return self._sessions.get(session_mount_id)


@pytest.mark.asyncio
async def test_orchestrator_ingest_operator_turn_classifies_environment_bound_execution():
    intake_contract = MainBrainIntakeContract(
        message_text="Open the dashboard and continue the assigned work.",
        decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
        intent_kind="execute-task",
        writeback_requested=False,
        writeback_plan=None,
        should_kickoff=True,
    )

    async def _fake_resolver(**_kwargs):
        return intake_contract

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
    orchestrator = MainBrainOrchestrator(
        query_execution_service=_FakeQueryExecutionService(),
        intake_contract_resolver=_fake_resolver,
        environment_service=_FakeEnvironmentService(
            sessions={persisted_session.id: persisted_session},
        ),
    )
    request = AgentRequest(
        id="req-orchestrator-role-env",
        session_id="sess-orchestrator-role-env",
        user_id="user-orchestrator-role-env",
        channel="console",
        input=[],
    )
    request.environment_ref = "desktop:session-1"
    request.environment_session_id = persisted_session.id

    envelope = await orchestrator.ingest_operator_turn(
        msgs=[Msg(name="user", role="user", content="Continue the assigned desktop flow.")],
        request=request,
        kernel_task_id="kernel-task-env",
    )

    assert envelope.intent_kind == "orchestrate"
    assert envelope.execution_mode == "environment-bound"
    assert envelope.environment_ref == "desktop:session-1"
    assert envelope.recovery_mode == "resume-environment"
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert not hasattr(request, "_copaw_main_brain_execution_mode")
    assert runtime_context["execution_mode"] == "environment-bound"
    assert runtime_context["execution_intent"] == "orchestrate"
    assert runtime_context["source_intent_kind"] == "execute-task"
    assert runtime_context["environment_ref"] == "desktop:session-1"
    assert runtime_context["environment_kind"] == "desktop"
    assert runtime_context["environment_session_id"] == persisted_session.id
    assert runtime_context["environment_lease_token"] == "lease-persisted"
    assert runtime_context["environment_continuity_source"] == "session-lease"
    assert runtime_context["environment_resume_ready"] is True
    assert runtime_context["recovery_mode"] == "resume-environment"
    assert runtime_context["recovery_reason"] == "session-lease"
    assert runtime_context["resume_environment_session_id"] == persisted_session.id


@pytest.mark.asyncio
async def test_orchestrator_ingest_operator_turn_prefers_explicit_continuity_token():
    intake_contract = MainBrainIntakeContract(
        message_text="Continue the assigned desktop flow.",
        decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
        intent_kind="execute-task",
        writeback_requested=False,
        writeback_plan=None,
        should_kickoff=True,
    )

    async def _fake_resolver(**_kwargs):
        return intake_contract

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
    orchestrator = MainBrainOrchestrator(
        query_execution_service=_FakeQueryExecutionService(),
        intake_contract_resolver=_fake_resolver,
        environment_service=_FakeEnvironmentService(
            sessions={persisted_session.id: persisted_session},
        ),
    )
    request = AgentRequest(
        id="req-orchestrator-role-explicit-continuity",
        session_id="sess-orchestrator-role-explicit-continuity",
        user_id="user-orchestrator-role-explicit-continuity",
        channel="console",
        input=[],
    )
    request.environment_ref = "desktop:session-1"
    request.environment_session_id = persisted_session.id
    request.continuity_token = "continuity:desktop-session-1"

    await orchestrator.ingest_operator_turn(
        msgs=[Msg(name="user", role="user", content="Continue the assigned desktop flow.")],
        request=request,
        kernel_task_id="kernel-task-explicit-continuity",
    )

    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["environment_continuity_token"] == "continuity:desktop-session-1"
    assert runtime_context["environment_continuity_source"] == "session-lease"
    assert runtime_context["environment_resume_ready"] is True
    assert runtime_context["recovery_continuity_token"] == "continuity:desktop-session-1"
    assert runtime_context["recovery_mode"] == "resume-environment"
    assert runtime_context["recovery_reason"] == "session-lease"


@pytest.mark.asyncio
async def test_orchestrator_ingest_operator_turn_attaches_environment_without_resume_claim_when_proof_missing():
    intake_contract = MainBrainIntakeContract(
        message_text="Continue the assigned desktop flow.",
        decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
        intent_kind="execute-task",
        writeback_requested=False,
        writeback_plan=None,
        should_kickoff=True,
    )

    async def _fake_resolver(**_kwargs):
        return intake_contract

    orchestrator = MainBrainOrchestrator(
        query_execution_service=_FakeQueryExecutionService(),
        intake_contract_resolver=_fake_resolver,
    )
    request = AgentRequest(
        id="req-orchestrator-role-attach-env",
        session_id="sess-orchestrator-role-attach-env",
        user_id="user-orchestrator-role-attach-env",
        channel="console",
        input=[],
    )
    request.environment_ref = "desktop:session-1"
    request.environment_session_id = "desktop-session-1"

    envelope = await orchestrator.ingest_operator_turn(
        msgs=[Msg(name="user", role="user", content="Continue the assigned desktop flow.")],
        request=request,
        kernel_task_id="kernel-task-attach-env",
    )

    assert envelope.execution_mode == "environment-bound"
    assert envelope.recovery_mode == "attach-environment"
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["environment_continuity_source"] == "environment-session"
    assert runtime_context["environment_resume_ready"] is False
    assert runtime_context["recovery_mode"] == "attach-environment"
    assert runtime_context["recovery_reason"] == "environment-session-without-continuity-proof"


@pytest.mark.asyncio
async def test_orchestrator_ingest_operator_turn_marks_rebind_when_resume_requested_without_proof():
    intake_contract = MainBrainIntakeContract(
        message_text="Continue the assigned desktop flow.",
        decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
        intent_kind="execute-task",
        writeback_requested=False,
        writeback_plan=None,
        should_kickoff=True,
    )

    async def _fake_resolver(**_kwargs):
        return intake_contract

    orchestrator = MainBrainOrchestrator(
        query_execution_service=_FakeQueryExecutionService(),
        intake_contract_resolver=_fake_resolver,
    )
    request = AgentRequest(
        id="req-orchestrator-role-rebind-env",
        session_id="sess-orchestrator-role-rebind-env",
        user_id="user-orchestrator-role-rebind-env",
        channel="console",
        input=[],
    )
    request.environment_ref = "desktop:session-1"
    request.environment_session_id = "desktop-session-1"
    request.resume_environment = True

    envelope = await orchestrator.ingest_operator_turn(
        msgs=[Msg(name="user", role="user", content="Continue the assigned desktop flow.")],
        request=request,
        kernel_task_id="kernel-task-rebind-env",
    )

    assert envelope.execution_mode == "environment-bound"
    assert envelope.recovery_mode == "rebind-environment"
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["recovery_mode"] == "rebind-environment"
    assert runtime_context["recovery_reason"] == "resume-request-without-continuity-proof"


@pytest.mark.asyncio
async def test_orchestrator_ingest_operator_turn_does_not_trust_request_lease_token_without_persisted_session():
    intake_contract = MainBrainIntakeContract(
        message_text="Continue the assigned desktop flow.",
        decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
        intent_kind="execute-task",
        writeback_requested=False,
        writeback_plan=None,
        should_kickoff=True,
    )

    async def _fake_resolver(**_kwargs):
        return intake_contract

    orchestrator = MainBrainOrchestrator(
        query_execution_service=_FakeQueryExecutionService(),
        intake_contract_resolver=_fake_resolver,
    )
    request = AgentRequest(
        id="req-orchestrator-role-forged-lease",
        session_id="sess-orchestrator-role-forged-lease",
        user_id="user-orchestrator-role-forged-lease",
        channel="console",
        input=[],
    )
    request.environment_ref = "desktop:session-1"
    request.environment_session_id = "session:console:desktop-session-1"
    request.environment_lease_token = "forged-request-lease"

    envelope = await orchestrator.ingest_operator_turn(
        msgs=[Msg(name="user", role="user", content="Continue the assigned desktop flow.")],
        request=request,
        kernel_task_id="kernel-task-forged-lease",
    )

    assert envelope.execution_mode == "environment-bound"
    assert envelope.recovery_mode == "attach-environment"
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["environment_lease_token"] is None
    assert runtime_context["environment_resume_ready"] is False
    assert runtime_context["recovery_mode"] == "attach-environment"
    assert runtime_context["recovery_reason"] == "environment-session-without-continuity-proof"


@pytest.mark.asyncio
async def test_orchestrator_ingest_operator_turn_uses_persisted_session_lease_for_resume():
    intake_contract = MainBrainIntakeContract(
        message_text="Continue the assigned desktop flow.",
        decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
        intent_kind="execute-task",
        writeback_requested=False,
        writeback_plan=None,
        should_kickoff=True,
    )

    async def _fake_resolver(**_kwargs):
        return intake_contract

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
    orchestrator = MainBrainOrchestrator(
        query_execution_service=_FakeQueryExecutionService(),
        intake_contract_resolver=_fake_resolver,
        environment_service=_FakeEnvironmentService(
            sessions={persisted_session.id: persisted_session},
        ),
    )
    request = AgentRequest(
        id="req-orchestrator-role-persisted-lease",
        session_id="sess-orchestrator-role-persisted-lease",
        user_id="user-orchestrator-role-persisted-lease",
        channel="console",
        input=[],
    )
    request.environment_ref = "desktop:session-1"
    request.environment_session_id = persisted_session.id

    envelope = await orchestrator.ingest_operator_turn(
        msgs=[Msg(name="user", role="user", content="Continue the assigned desktop flow.")],
        request=request,
        kernel_task_id="kernel-task-persisted-lease",
    )

    assert envelope.execution_mode == "environment-bound"
    assert envelope.recovery_mode == "resume-environment"
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["environment_session_id"] == persisted_session.id
    assert runtime_context["environment_lease_token"] == "lease-persisted"
    assert runtime_context["environment_resume_ready"] is True
    assert runtime_context["recovery_mode"] == "resume-environment"


@pytest.mark.asyncio
async def test_orchestrator_ingest_operator_turn_marks_missing_environment_binding_when_mode_requires_it():
    intake_contract = MainBrainIntakeContract(
        message_text="Continue the assigned desktop flow.",
        decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
        intent_kind="execute-task",
        writeback_requested=False,
        writeback_plan=None,
        should_kickoff=True,
    )

    async def _fake_resolver(**_kwargs):
        return intake_contract

    orchestrator = MainBrainOrchestrator(
        query_execution_service=_FakeQueryExecutionService(),
        intake_contract_resolver=_fake_resolver,
    )
    request = AgentRequest(
        id="req-orchestrator-role-env-missing",
        session_id="sess-orchestrator-role-env-missing",
        user_id="user-orchestrator-role-env-missing",
        channel="console",
        input=[],
    )

    request.environment_ref = None
    request.active_environment_id = None
    request.current_environment_id = None

    envelope = await orchestrator.ingest_operator_turn(
        msgs=[Msg(name="user", role="user", content="Continue the assigned desktop flow.")],
        request=request,
        kernel_task_id="kernel-task-env-missing",
    )

    assert envelope.execution_mode == "delegated"
    assert envelope.environment_ref is None
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["environment_binding_kind"] == "none"
    assert runtime_context["environment_kind"] == "none"


@pytest.mark.asyncio
async def test_orchestrator_ingest_operator_turn_keeps_discussion_as_chat():
    intake_contract = MainBrainIntakeContract(
        message_text="Let's discuss the weekly plan.",
        decision=SimpleNamespace(intent_kind="discussion", kickoff_allowed=False),
        intent_kind="discussion",
        writeback_requested=False,
        writeback_plan=None,
        should_kickoff=False,
    )

    async def _fake_resolver(**_kwargs):
        return intake_contract

    orchestrator = MainBrainOrchestrator(
        query_execution_service=_FakeQueryExecutionService(),
        intake_contract_resolver=_fake_resolver,
    )
    request = AgentRequest(
        id="req-orchestrator-role-direct",
        session_id="sess-orchestrator-role-direct",
        user_id="user-orchestrator-role-direct",
        channel="console",
        input=[],
    )

    envelope = await orchestrator.ingest_operator_turn(
        msgs=[Msg(name="user", role="user", content="Let's discuss the weekly plan.")],
        request=request,
    )

    assert envelope.intent_kind == "chat"
    assert envelope.execution_mode == "chat"
    assert envelope.environment_ref is None
    assert envelope.recovery_mode == "fresh"
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["execution_intent"] == "chat"
    assert runtime_context["execution_mode"] == "chat"
