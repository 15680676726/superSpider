# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.kernel.query_execution_confirmation import (
    build_query_resume_request,
    query_confirmation_request_context,
)

from .query_execution_environment_parts.shared import *  # noqa: F401,F403


def _sample_main_brain_runtime_context() -> dict[str, object]:
    return {
        "source_intent_kind": "execute-task",
        "execution_intent": "orchestrate",
        "execution_mode": "environment-bound",
        "environment_ref": "desktop:session-1",
        "environment_binding_kind": "request-environment",
        "environment_kind": "desktop",
        "environment_session_id": "session:console:desktop-session-1",
        "environment_lease_token": "lease-ctx-1",
        "environment_continuity_token": "continuity:desktop-session-1",
        "environment_continuity_source": "session-lease",
        "environment_live_session_bound": True,
        "environment_resume_ready": True,
        "writeback_requested": True,
        "should_kickoff": True,
        "recovery_mode": "resume-environment",
        "recovery_reason": "session-lease",
        "resume_checkpoint_id": "checkpoint-main-brain-1",
        "resume_mailbox_id": "mailbox-main-brain-1",
        "resume_kernel_task_id": "kernel-main-brain-1",
        "resume_environment_session_id": "session:console:desktop-session-1",
        "recovery_continuity_token": "continuity:desktop-session-1",
        "kernel_task_id": "kernel-main-brain-1",
    }


def test_query_confirmation_resume_request_preserves_main_brain_runtime_context() -> None:
    runtime_context = _sample_main_brain_runtime_context()
    request_context = query_confirmation_request_context(
        SimpleNamespace(
            session_id="industry-chat:industry-v1-ops:execution-core",
            user_id="ops-user",
            agent_id="ops-agent",
            channel="console",
            industry_instance_id="industry-v1-ops",
            industry_role_id="execution-core",
            session_kind="industry-agent-chat",
            _copaw_main_brain_runtime_context=runtime_context,
        ),
    )

    assert request_context["main_brain_runtime"]["environment"]["ref"] == "desktop:session-1"
    assert request_context["main_brain_runtime"]["recovery"]["mode"] == "resume-environment"

    request = build_query_resume_request(
        request_context=request_context,
        owner_agent_id="ops-agent",
    )

    restored = getattr(request, "_copaw_main_brain_runtime_context")
    assert restored["intent"]["kind"] == "orchestrate"
    assert restored["environment"]["session_id"] == "session:console:desktop-session-1"
    assert restored["recovery"]["reason"] == "session-lease"


def test_query_execution_service_formally_consumes_main_brain_runtime_context_in_prompt_and_checkpoints(
    tmp_path,
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    monkeypatch.setattr(query_execution_module, "CoPawAgent", _FakeAgent)
    monkeypatch.setattr(
        query_execution_module,
        "stream_printing_messages",
        _fake_stream_printing_messages,
    )
    monkeypatch.setattr(
        query_execution_module,
        "load_config",
        lambda: SimpleNamespace(
            agents=SimpleNamespace(
                running=SimpleNamespace(max_iters=1, max_input_length=512),
            ),
        ),
    )

    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="ops-agent",
            actor_key="industry-v1-ops:execution-core",
            actor_fingerprint="fp-ops",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="execution-core",
            display_name="Ops Agent",
            role_name="Operations lead",
        ),
    )
    mailbox_repository = SqliteAgentMailboxRepository(state_store)
    checkpoint_repository = SqliteAgentCheckpointRepository(state_store)
    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
    )

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_FakeIndustryService(),
        actor_mailbox_service=mailbox_service,
        agent_runtime_repository=runtime_repository,
    )

    runtime_context = _sample_main_brain_runtime_context()

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "continue the bound desktop task")],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="ops-user",
                agent_id="ops-agent",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                session_kind="industry-agent-chat",
                _copaw_main_brain_runtime_context=runtime_context,
            ),
            kernel_task_id="kernel-main-brain-1",
        ):
            pass

    asyncio.run(_run())

    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "# Main Brain Runtime" in prompt_appendix
    assert "Execution route: execute-task -> orchestrate (environment-bound)" in prompt_appendix
    assert "Environment binding: desktop:session-1" in prompt_appendix
    assert "Recovery contract: resume-environment / session-lease" in prompt_appendix

    checkpoints = checkpoint_repository.list_checkpoints(agent_id="ops-agent", limit=None)
    assert checkpoints
    assert any(
        isinstance(checkpoint.resume_payload, dict)
        and checkpoint.resume_payload["main_brain_runtime"]["environment"]["ref"]
        == "desktop:session-1"
        and checkpoint.resume_payload["main_brain_runtime"]["recovery"]["mode"]
        == "resume-environment"
        for checkpoint in checkpoints
    )

    restored_context = service._resolve_execution_task_context(  # pylint: disable=protected-access
        agent_id="ops-agent",
        kernel_task_id="kernel-main-brain-1",
        conversation_thread_id="industry-chat:industry-v1-ops:execution-core",
    )
    assert restored_context["main_brain_runtime"]["environment"]["session_id"] == (
        "session:console:desktop-session-1"
    )
    assert restored_context["main_brain_runtime"]["recovery"]["reason"] == "session-lease"

    runtime = runtime_repository.get_runtime("ops-agent")
    assert runtime is not None
    assert runtime.metadata["main_brain_runtime"]["intent"]["mode"] == "environment-bound"
    assert runtime.metadata["main_brain_runtime"]["environment"]["ref"] == "desktop:session-1"
