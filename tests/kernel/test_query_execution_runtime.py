# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from agentscope.message import Msg

from copaw.agents.react_agent import (
    _wrap_tool_function_for_toolkit,
    bind_reasoning_tool_choice_resolver,
    bind_tool_preflight,
)
from copaw.agents.tools.evidence_runtime import (
    bind_browser_evidence_sink,
    bind_file_evidence_sink,
    bind_shell_evidence_sink,
)
from copaw.agents.tools.file_io import read_file
from copaw.kernel import KernelTask
from copaw.kernel.main_brain_intake import MainBrainIntakeContract
from copaw.kernel.query_execution import KernelQueryExecutionService
from copaw.constant import MEMORY_COMPACT_KEEP_RECENT
from copaw.state import AgentRuntimeRecord, SQLiteStateStore
from copaw.state.repositories import SqliteAgentRuntimeRepository


async def _yield_once_with_runtime_bindings() -> None:
    with bind_reasoning_tool_choice_resolver(lambda: "required"):
        with bind_tool_preflight(lambda *_args, **_kwargs: None):
            with bind_shell_evidence_sink(lambda _payload: None):
                with bind_file_evidence_sink(lambda _payload: None):
                    with bind_browser_evidence_sink(lambda _payload: None):
                        yield


class _SnapshotSessionBackend:
    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, str], dict[str, object]] = {}

    def load_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        allow_not_exist: bool = True,
    ) -> dict[str, object] | None:
        _ = allow_not_exist
        snapshot = self.snapshots.get((session_id, user_id))
        return dict(snapshot) if snapshot is not None else None

    def save_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        payload: dict[str, object],
        source_ref: str,
    ) -> None:
        _ = source_ref
        self.snapshots[(session_id, user_id)] = dict(payload)


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


def test_execution_context_runtime_helpers_are_sourced_from_context_module() -> None:
    expected_module = "copaw.kernel.query_execution_context_runtime"
    helper_names = (
        "_merge_main_brain_runtime_contexts",
        "_resolve_request_main_brain_runtime_context",
        "_resolve_execution_task_context",
        "_resolve_execution_degradation_context",
    )
    for helper_name in helper_names:
        assert getattr(KernelQueryExecutionService, helper_name).__module__ == expected_module


def test_query_execution_runtime_drops_legacy_memory_manager_alias() -> None:
    assert not hasattr(KernelQueryExecutionService, "set_memory_manager")


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


def test_query_execution_runtime_marks_sidecar_memory_boundary_as_degraded_when_missing() -> None:
    service = KernelQueryExecutionService(
        session_backend=object(),
        conversation_compaction_service=None,
    )

    resolved = service._resolve_execution_task_context(  # pylint: disable=protected-access
        request=SimpleNamespace(),
        agent_id="ops-agent",
        kernel_task_id=None,
        conversation_thread_id="industry-chat:industry-v1-ops:execution-core",
    )

    degradation = resolved.get("degradation")
    assert isinstance(degradation, dict)
    sidecar_memory = degradation.get("sidecar_memory")
    assert isinstance(sidecar_memory, dict)
    assert sidecar_memory["failure_source"] == "sidecar-memory"
    assert "private compaction memory sidecar" in sidecar_memory["remediation_summary"]
    assert "Restore the compaction sidecar" in sidecar_memory["blocked_next_step"]
    runtime_entropy = resolved.get("runtime_entropy")
    assert isinstance(runtime_entropy, dict)
    assert runtime_entropy["status"] == "degraded"
    assert runtime_entropy["sidecar_memory_status"] == "degraded"
    assert runtime_entropy["carry_forward_contract"] == "canonical-state-only"
    assert runtime_entropy["failure_source"] == "sidecar-memory"
    entropy = resolved.get("query_runtime_entropy")
    assert isinstance(entropy, dict)
    assert entropy["status"] == "degraded"
    assert entropy["runtime_entropy"] == runtime_entropy
    assert entropy["sidecar_memory"]["status"] == "degraded"
    assert entropy["degradation"]["sidecar_memory"]["failure_source"] == "sidecar-memory"


def test_query_execution_runtime_resolves_runtime_entropy_contract_when_sidecar_is_available() -> None:
    service = KernelQueryExecutionService(
        session_backend=object(),
        conversation_compaction_service=SimpleNamespace(),
    )

    resolved = service._resolve_execution_task_context(  # pylint: disable=protected-access
        request=SimpleNamespace(),
        agent_id="ops-agent",
        kernel_task_id=None,
        conversation_thread_id="industry-chat:industry-v1-ops:execution-core",
    )

    runtime_entropy = resolved.get("runtime_entropy")
    assert isinstance(runtime_entropy, dict)
    assert runtime_entropy["status"] == "available"
    assert runtime_entropy["sidecar_memory_status"] == "available"
    assert runtime_entropy["carry_forward_contract"] == "private-compaction-sidecar"
    assert runtime_entropy["max_input_length"] > 0
    entropy = resolved.get("query_runtime_entropy")
    assert isinstance(entropy, dict)
    assert entropy["status"] == "available"
    assert entropy["runtime_entropy"] == runtime_entropy
    assert entropy["sidecar_memory"]["status"] == "available"
    assert entropy["sidecar_memory"]["availability"] == "attached"
    assert entropy["degradation"] == {}


def test_query_execution_runtime_exposes_attached_entropy_budget_from_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = SimpleNamespace(
        max_input_length=4096,
        memory_compact_ratio=0.5,
        memory_compact_threshold=2048,
        memory_compact_reserve=512,
        enable_tool_result_compact=True,
        tool_result_compact_keep_n=7,
    )
    monkeypatch.setattr(
        "copaw.kernel.query_execution_runtime.load_config",
        lambda: SimpleNamespace(agents=SimpleNamespace(running=running)),
    )
    service = KernelQueryExecutionService(
        session_backend=object(),
        conversation_compaction_service=object(),
    )

    entropy = service.get_query_runtime_entropy_contract()

    assert entropy["status"] == "available"
    assert entropy["runtime_entropy"]["status"] == "available"
    assert entropy["runtime_entropy"]["carry_forward_contract"] == "private-compaction-sidecar"
    assert entropy["runtime_entropy"]["max_input_length"] == 4096
    assert entropy["budget"] == {
        "max_input_length": 4096,
        "memory_compact_ratio": 0.5,
        "memory_compact_threshold": 2048,
        "memory_compact_reserve": 512,
        "enable_tool_result_compact": True,
        "tool_result_compact_keep_n": 7,
        "keep_recent_messages": MEMORY_COMPACT_KEEP_RECENT,
        "tool_result_budget": {
            "enabled": True,
            "keep_recent_messages": MEMORY_COMPACT_KEEP_RECENT,
            "keep_recent_tool_results": 7,
            "state_channel": "query_runtime_state",
            "summary_surface": "runtime-center",
            "spill_surface": "runtime-center",
            "replay_surface": "runtime-conversation",
        },
    }
    assert entropy["sidecar_memory"]["status"] == "available"
    assert entropy["sidecar_memory"]["availability"] == "attached"
    assert entropy["degradation"] == {}


@pytest.mark.asyncio
async def test_query_execution_runtime_requires_durable_kickoff_proof_before_marking_committed() -> None:
    class _IndustryService:
        async def apply_execution_chat_writeback(self, **kwargs):
            _ = kwargs
            return {
                "applied": True,
                "strategy_updated": True,
                "created_goal_titles": ["Follow up on the latest operator request"],
            }

        async def kickoff_execution_from_chat(self, **kwargs):
            _ = kwargs
            return {
                "summary": "Kickoff tail completed but durable execution proof never arrived.",
            }

    service = KernelQueryExecutionService(
        session_backend=object(),
        industry_service=_IndustryService(),
    )
    request = SimpleNamespace(
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        session_id="industry-chat:industry-v1-demo:execution-core",
        control_thread_id="industry-chat:industry-v1-demo:execution-core",
        channel="console",
        work_context_id="work-context-1",
        _copaw_main_brain_intake_contract=MainBrainIntakeContract(
            message_text="Record this and continue execution.",
            decision=SimpleNamespace(
                intent_kind="execute-task",
                should_writeback=True,
                kickoff_allowed=True,
                explicit_execution_confirmation=False,
            ),
            intent_kind="execute-task",
            writeback_requested=True,
            writeback_plan=SimpleNamespace(active=True, fingerprint="plan-1"),
            should_kickoff=True,
        ),
    )

    chat_writeback_summary, industry_kickoff_summary = (
        await service._apply_requested_main_brain_intake(  # pylint: disable=protected-access
            msgs=[Msg(name="user", role="user", content="Record this and continue execution.")],
            request=request,
            owner_agent_id="execution-core-agent",
            agent_profile=None,
        )
    )

    assert chat_writeback_summary["status"] == "committed"
    assert industry_kickoff_summary["status"] == "commit_failed"
    assert industry_kickoff_summary["reason"] == "durable_kickoff_failed"

    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["accepted_persistence"]["status"] == "accepted"
    assert runtime_context["commit_outcome"]["status"] == "commit_failed"
    assert runtime_context["commit_outcome"]["reason"] == "durable_kickoff_failed"


@pytest.mark.asyncio
async def test_query_execution_runtime_persists_accepted_boundary_and_commit_outcome_for_replay() -> None:
    class _IndustryService:
        async def apply_execution_chat_writeback(self, **kwargs):
            _ = kwargs
            return {
                "applied": True,
                "strategy_updated": True,
                "created_goal_titles": ["Follow up on the latest operator request"],
            }

        async def kickoff_execution_from_chat(self, **kwargs):
            _ = kwargs
            return {
                "summary": "Kickoff tail completed but durable execution proof never arrived.",
            }

    session_backend = _SnapshotSessionBackend()
    service = KernelQueryExecutionService(
        session_backend=session_backend,
        industry_service=_IndustryService(),
    )
    request = SimpleNamespace(
        industry_instance_id="industry-v1-demo",
        industry_role_id="execution-core",
        session_id="industry-chat:industry-v1-demo:execution-core",
        control_thread_id="industry-chat:industry-v1-demo:execution-core",
        channel="console",
        work_context_id="work-context-1",
        user_id="ops-user",
        _copaw_main_brain_intake_contract=MainBrainIntakeContract(
            message_text="Record this and continue execution.",
            decision=SimpleNamespace(
                intent_kind="execute-task",
                should_writeback=True,
                kickoff_allowed=True,
                explicit_execution_confirmation=False,
            ),
            intent_kind="execute-task",
            writeback_requested=True,
            writeback_plan=SimpleNamespace(active=True, fingerprint="plan-1"),
            should_kickoff=True,
        ),
    )

    await service._apply_requested_main_brain_intake(  # pylint: disable=protected-access
        msgs=[Msg(name="user", role="user", content="Record this and continue execution.")],
        request=request,
        owner_agent_id="execution-core-agent",
        agent_profile=None,
    )

    snapshot = session_backend.snapshots[(request.session_id, request.user_id)]
    query_runtime_state = snapshot.get("query_runtime_state")
    assert isinstance(query_runtime_state, dict)
    assert query_runtime_state["accepted_persistence"]["status"] == "accepted"
    assert query_runtime_state["accepted_persistence"]["boundary"] == "execution_runtime_intake"
    assert query_runtime_state["commit_outcome"]["status"] == "commit_failed"
    assert query_runtime_state["commit_outcome"]["reason"] == "durable_kickoff_failed"


@pytest.mark.asyncio
async def test_wrapped_builtin_tool_applies_unified_tool_contract_validation() -> None:
    wrapped = _wrap_tool_function_for_toolkit(read_file)

    response = await wrapped(file_path="   ")

    assert "Missing required tool field(s): file_path" in response.content[0]["text"]


def test_query_execution_runtime_evidence_sinks_attach_tool_contract_metadata() -> None:
    class _ToolBridge:
        def __init__(self) -> None:
            self.shell_calls: list[dict[str, object]] = []
            self.file_calls: list[dict[str, object]] = []
            self.browser_calls: list[dict[str, object]] = []

        def record_shell_event(self, task_id: str, payload: dict[str, object]) -> None:
            self.shell_calls.append({"task_id": task_id, "payload": payload})

        def record_file_event(self, task_id: str, payload: dict[str, object]) -> None:
            self.file_calls.append({"task_id": task_id, "payload": payload})

        def record_browser_event(self, task_id: str, payload: dict[str, object]) -> None:
            self.browser_calls.append({"task_id": task_id, "payload": payload})

    bridge = _ToolBridge()
    service = KernelQueryExecutionService(
        session_backend=object(),
        tool_bridge=bridge,
    )

    shell_sink = service._make_shell_evidence_sink("ktask:query-tool")  # pylint: disable=protected-access
    assert shell_sink is not None
    shell_sink(
        {
            "tool_name": "execute_shell_command",
            "command": "git status",
            "cwd": "D:/word/copaw",
            "timeout_seconds": 60,
            "status": "success",
            "returncode": 0,
            "stdout": "ok",
            "stderr": "",
            "metadata": {},
        },
    )

    file_sink = service._make_file_evidence_sink("ktask:query-tool")  # pylint: disable=protected-access
    assert file_sink is not None
    file_sink(
        {
            "tool_name": "write_file",
            "action": "write",
            "file_path": "notes.txt",
            "resolved_path": "D:/word/copaw/notes.txt",
            "status": "success",
            "result_summary": "done",
            "metadata": {},
        },
    )

    browser_sink = service._make_browser_evidence_sink("ktask:query-tool")  # pylint: disable=protected-access
    assert browser_sink is not None
    browser_sink(
        {
            "tool_name": "browser_use",
            "action": "click",
            "page_id": "page-1",
            "status": "success",
            "result_summary": "clicked",
            "metadata": {},
        },
    )

    shell_meta = bridge.shell_calls[0]["payload"]["metadata"]
    assert shell_meta["tool_contract"] == "tool:execute_shell_command"
    assert shell_meta["action_mode"] == "read"
    assert shell_meta["read_only"] is True
    assert shell_meta["concurrency_class"] == "parallel-read"
    assert shell_meta["preflight_policy"] == "shell-safety"

    file_meta = bridge.file_calls[0]["payload"]["metadata"]
    assert file_meta["tool_contract"] == "tool:write_file"
    assert file_meta["action_mode"] == "write"
    assert file_meta["read_only"] is False
    assert file_meta["concurrency_class"] == "serial-write"
    assert file_meta["preflight_policy"] == "inline"

    browser_meta = bridge.browser_calls[0]["payload"]["metadata"]
    assert browser_meta["tool_contract"] == "tool:browser_use"
    assert browser_meta["action_mode"] == "write"
    assert browser_meta["read_only"] is False
    assert browser_meta["concurrency_class"] == "serial-write"
    assert browser_meta["preflight_policy"] == "inline"


@pytest.mark.asyncio
async def test_query_execution_runtime_builds_capability_frontdoor_delegate_for_builtin_tools() -> None:
    class _CapabilityService:
        def __init__(self) -> None:
            self.calls: list[KernelTask] = []

        async def execute_task(self, task: KernelTask) -> dict[str, object]:
            self.calls.append(task)
            return {
                "success": True,
                "summary": "delegated-via-capability-frontdoor",
            }

    capability_service = _CapabilityService()
    service = KernelQueryExecutionService(
        session_backend=object(),
        capability_service=capability_service,
    )

    delegate = service._build_query_tool_execution_delegate(  # pylint: disable=protected-access
        owner_agent_id="ops-agent",
        kernel_task_id="ktask:query-frontdoor",
        execution_context={
            "work_context_id": "work-context-1",
            "main_brain_runtime": {
                "environment": {
                    "ref": "desktop:runtime",
                },
            },
        },
    )

    assert delegate is not None
    result = await delegate(
        "tool:execute_shell_command",
        {"command": "git status"},
    )

    assert result["summary"] == "delegated-via-capability-frontdoor"
    [submitted] = capability_service.calls
    assert submitted.id == "ktask:query-frontdoor"
    assert submitted.capability_ref == "tool:execute_shell_command"
    assert submitted.owner_agent_id == "ops-agent"
    assert submitted.work_context_id == "work-context-1"
    assert submitted.environment_ref == "desktop:runtime"
    assert submitted.payload == {"command": "git status"}


@pytest.mark.asyncio
async def test_query_execution_runtime_delegate_and_wrapped_builtin_tool_form_end_to_end_frontdoor_path() -> None:
    from copaw.agents.react_agent import _wrap_tool_function_for_toolkit, bind_tool_execution_delegate
    from copaw.agents.tools import get_current_time

    class _CapabilityService:
        def __init__(self) -> None:
            self.calls: list[KernelTask] = []

        async def execute_task(self, task: KernelTask) -> dict[str, object]:
            self.calls.append(task)
            return {
                "success": True,
                "summary": "delegated-e2e",
            }

    capability_service = _CapabilityService()
    service = KernelQueryExecutionService(
        session_backend=object(),
        capability_service=capability_service,
    )
    delegate = service._build_query_tool_execution_delegate(  # pylint: disable=protected-access
        owner_agent_id="ops-agent",
        kernel_task_id="ktask:query-e2e-frontdoor",
        execution_context={
            "work_context_id": "work-context-e2e",
            "main_brain_runtime": {
                "environment": {
                    "ref": "desktop:e2e",
                },
            },
        },
    )
    wrapped = _wrap_tool_function_for_toolkit(get_current_time)

    with bind_tool_execution_delegate(delegate):
        response = await wrapped()

    assert response.content[0]["text"] == "delegated-e2e"
    [submitted] = capability_service.calls
    assert submitted.id == "ktask:query-e2e-frontdoor"
    assert submitted.capability_ref == "tool:get_current_time"
    assert submitted.owner_agent_id == "ops-agent"
    assert submitted.work_context_id == "work-context-e2e"
    assert submitted.environment_ref == "desktop:e2e"
    assert submitted.payload == {}
