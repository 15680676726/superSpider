# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from copaw.agents.react_agent import (
    bind_reasoning_tool_choice_resolver,
    bind_tool_preflight,
)
from copaw.agents.tools.evidence_runtime import (
    bind_browser_evidence_sink,
    bind_file_evidence_sink,
    bind_shell_evidence_sink,
)
from copaw.kernel import KernelTask
from copaw.kernel.query_execution import KernelQueryExecutionService
from copaw.state import AgentRuntimeRecord, SQLiteStateStore
from copaw.state.repositories import SqliteAgentRuntimeRepository


async def _yield_once_with_runtime_bindings() -> None:
    with bind_reasoning_tool_choice_resolver(lambda: "required"):
        with bind_tool_preflight(lambda *_args, **_kwargs: None):
            with bind_shell_evidence_sink(lambda _payload: None):
                with bind_file_evidence_sink(lambda _payload: None):
                    with bind_browser_evidence_sink(lambda _payload: None):
                        yield


def test_runtime_context_bindings_survive_cross_task_generator_close() -> None:
    async def _scenario() -> None:
        stream = _yield_once_with_runtime_bindings()
        await anext(stream)

        async def _close_in_another_task() -> None:
            await stream.aclose()

        await asyncio.create_task(_close_in_another_task())

    asyncio.run(_scenario())


def test_resident_runtime_helpers_are_sourced_from_resident_module() -> None:
    expected_module = "copaw.kernel.query_execution_resident_runtime"
    helper_names = (
        "_get_or_create_resident_agent",
        "_resident_agent_cache_key",
        "_resident_agent_signature",
        "_acquire_actor_runtime_lease",
        "_heartbeat_actor_runtime_lease",
        "_release_actor_runtime_lease",
        "_build_query_lease_heartbeat",
        "_heartbeat_query_leases",
    )
    for helper_name in helper_names:
        assert getattr(KernelQueryExecutionService, helper_name).__module__ == expected_module


def test_usage_runtime_helpers_are_sourced_from_usage_module() -> None:
    expected_module = "copaw.kernel.query_execution_usage_runtime"
    helper_names = (
        "record_turn_usage",
        "_record_agent_runtime_usage",
        "_record_query_usage_evidence",
        "_resolve_query_model_usage_context",
    )
    for helper_name in helper_names:
        assert getattr(KernelQueryExecutionService, helper_name).__module__ == expected_module


def test_query_execution_runtime_resolves_execution_context_from_task_runtime_and_request(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "query-runtime-state.db")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="ops-agent",
            actor_key="industry-v1-ops:execution-core",
            actor_fingerprint="fp-ops",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            metadata={
                "main_brain_runtime": {
                    "environment": {"ref": "desktop:runtime"},
                    "recovery": {"mode": "runtime-metadata"},
                },
            },
        ),
    )
    kernel_task = KernelTask(
        id="ktask:query-runtime",
        title="Continue the bound environment task",
        owner_agent_id="ops-agent",
        work_context_id="work-context-task",
        payload={
            "request_context": {
                "main_brain_runtime": {
                    "intent": {"mode": "environment-bound"},
                    "environment": {"session_id": "session:console:desktop-session-1"},
                },
            },
        },
    )
    dispatcher = SimpleNamespace(
        lifecycle=SimpleNamespace(get_task=lambda task_id: kernel_task if task_id == kernel_task.id else None),
    )
    service = KernelQueryExecutionService(
        session_backend=object(),
        kernel_dispatcher=dispatcher,
        agent_runtime_repository=runtime_repository,
    )

    resolved = service._resolve_execution_task_context(  # pylint: disable=protected-access
        request=SimpleNamespace(
            _copaw_main_brain_runtime_context={
                "environment": {"ref": "desktop:request"},
                "recovery": {"reason": "request-bound"},
            },
        ),
        agent_id="ops-agent",
        kernel_task_id=kernel_task.id,
        conversation_thread_id="industry-chat:industry-v1-ops:execution-core",
    )

    assert resolved["work_context_id"] == "work-context-task"
    assert resolved["main_brain_runtime"]["intent"]["mode"] == "environment-bound"
    assert (
        resolved["main_brain_runtime"]["environment"]["session_id"]
        == "session:console:desktop-session-1"
    )
    assert resolved["main_brain_runtime"]["environment"]["ref"] == "desktop:request"
    assert resolved["main_brain_runtime"]["recovery"]["mode"] == "runtime-metadata"
    assert resolved["main_brain_runtime"]["recovery"]["reason"] == "request-bound"
