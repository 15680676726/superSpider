# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.kernel.query_execution_confirmation import (
    build_query_resume_request,
    query_confirmation_request_context,
)
from copaw.state.executor_runtime_service import ExecutorRuntimeService
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
        "knowledge_graph": {
            "scope_type": "work_context",
            "scope_id": "ctx-approval",
            "node_count": 4,
            "relation_count": 2,
            "top_entities": ["outbound-approval", "finance-queue"],
            "top_relations": ["Outbound approval depends on finance sign-off"],
            "environment_labels": ["Desktop session"],
            "dependency_paths": [
                "Resolve the finance sign-off dependency before continuing.",
            ],
            "blocker_paths": [
                "Do not continue if approval proof is still missing.",
            ],
            "recovery_paths": [
                "Refresh approval proof and rerun verification.",
            ],
        },
    }


def _seed_executor_runtime(
    state_store: SQLiteStateStore,
    *,
    agent_id: str,
    thread_id: str,
) -> ExecutorRuntimeService:
    service = ExecutorRuntimeService(state_store=state_store)
    runtime = service.create_or_reuse_runtime(
        executor_id="codex",
        protocol_kind="app_server",
        scope_kind="role",
        role_id=agent_id,
        thread_id=thread_id,
        metadata={
            "owner_agent_id": agent_id,
            "display_name": "Ops Agent",
            "role_name": "Operations lead",
            "industry_instance_id": "industry-v1-ops",
            "industry_role_id": "execution-core",
        },
        continuity_metadata={
            "control_thread_id": thread_id,
            "session_id": thread_id,
        },
    )
    service.mark_runtime_ready(
        runtime.runtime_id,
        thread_id=thread_id,
        metadata={"owner_agent_id": agent_id},
    )
    return service


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
    executor_runtime_service = _seed_executor_runtime(
        state_store,
        agent_id="ops-agent",
        thread_id="industry-chat:industry-v1-ops:execution-core",
    )
    checkpoint_repository = SqliteAgentCheckpointRepository(state_store)

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_FakeIndustryService(),
        agent_checkpoint_repository=checkpoint_repository,
        executor_runtime_service=executor_runtime_service,
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
    assert "Knowledge graph focus: outbound-approval; finance-queue" in prompt_appendix
    assert "Knowledge graph dependencies:" in prompt_appendix
    assert "Resolve the finance sign-off dependency before continuing." in prompt_appendix

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
    assert restored_context["main_brain_runtime"]["knowledge_graph"]["scope_id"] == "ctx-approval"

    runtime = next(
        iter(executor_runtime_service.list_runtimes(role_id="ops-agent")),
        None,
    )
    assert runtime is not None
    assert runtime.metadata["main_brain_runtime"]["intent"]["mode"] == "environment-bound"
    assert runtime.metadata["main_brain_runtime"]["environment"]["ref"] == "desktop:session-1"
    assert runtime.metadata["main_brain_runtime"]["knowledge_graph"]["top_relations"] == [
        "Outbound approval depends on finance sign-off",
    ]


def test_query_execution_service_restores_main_brain_runtime_context_from_executor_checkpoint_projection_without_checkpoint_repo(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    executor_runtime_service = _seed_executor_runtime(
        state_store,
        agent_id="ops-agent",
        thread_id="industry-chat:industry-v1-ops:execution-core",
    )
    runtime = next(
        iter(executor_runtime_service.list_runtimes(role_id="ops-agent")),
        None,
    )
    assert runtime is not None
    executor_runtime_service.upsert_runtime(
        runtime.model_copy(
            update={
                "metadata": {
                    **dict(runtime.metadata or {}),
                    "main_brain_runtime": {
                        "environment": {
                            "ref": "desktop:session-1",
                            "session_id": "session:console:desktop-session-1",
                        },
                        "recovery": {
                            "mode": "resume-environment",
                            "reason": "session-lease",
                        },
                        "knowledge_graph": {
                            "scope_id": "ctx-approval",
                        },
                    },
                    "last_query_checkpoint_id": "checkpoint-runtime-projection",
                    "last_query_checkpoint": {
                        "id": "checkpoint-runtime-projection",
                        "task_id": "kernel-main-brain-1",
                        "conversation_thread_id": "industry-chat:industry-v1-ops:execution-core",
                        "checkpoint_kind": "task-result",
                        "status": "applied",
                        "phase": "query-complete",
                        "summary": "Projection restored",
                        "resume_payload": {
                            "main_brain_runtime": {
                                "environment": {
                                    "ref": "desktop:session-1",
                                    "session_id": "session:console:desktop-session-1",
                                },
                                "recovery": {
                                    "mode": "resume-environment",
                                    "reason": "session-lease",
                                },
                                "knowledge_graph": {
                                    "scope_id": "ctx-approval",
                                },
                            },
                        },
                        "snapshot_payload": {
                            "restored": True,
                        },
                    },
                },
            },
        )
    )

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_FakeIndustryService(),
        executor_runtime_service=executor_runtime_service,
    )

    restored_context = service._resolve_execution_task_context(  # pylint: disable=protected-access
        agent_id="ops-agent",
        kernel_task_id="kernel-main-brain-1",
        conversation_thread_id="industry-chat:industry-v1-ops:execution-core",
    )

    assert restored_context["resume_checkpoint"]["id"] == "checkpoint-runtime-projection"
    assert restored_context["resume_payload"]["main_brain_runtime"]["environment"]["ref"] == (
        "desktop:session-1"
    )
    assert restored_context["resume_snapshot"]["restored"] is True
    assert restored_context["main_brain_runtime"]["recovery"]["reason"] == "session-lease"
