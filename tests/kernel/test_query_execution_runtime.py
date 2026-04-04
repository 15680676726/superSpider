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
from copaw.memory.conversation_compaction_service import ConversationCompactionService
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
    assert entropy["runtime_entropy"]["tool_result_budget"] == entropy["budget"]["tool_result_budget"]
    assert entropy["sidecar_memory"]["status"] == "available"
    assert entropy["sidecar_memory"]["availability"] == "attached"
    assert entropy["degradation"] == {}


def test_query_execution_runtime_projects_compaction_visibility_into_entropy_contract() -> None:
    class _CompactionService:
        @staticmethod
        def build_visibility_payload(source: dict[str, object] | None = None) -> dict[str, object]:
            return ConversationCompactionService.build_visibility_payload(source)

        def runtime_health_payload(self) -> dict[str, object]:
            return {
                "compaction_state": {
                    "mode": "microcompact",
                    "summary": "Compacted 2 oversized tool results.",
                    "spill_count": 1,
                },
                "tool_result_budget": {
                    "message_budget": 2400,
                    "remaining_budget": 600,
                },
                "tool_use_summary": {
                    "summary": "2 tool results compacted into artifact previews.",
                    "artifact_refs": ["artifact://tool-result-1"],
                },
            }

    service = KernelQueryExecutionService(
        session_backend=object(),
        conversation_compaction_service=_CompactionService(),
    )

    entropy = service.get_query_runtime_entropy_contract()

    assert entropy["compaction_state"] == {
        "mode": "microcompact",
        "summary": "Compacted 2 oversized tool results.",
        "spill_count": 1,
    }
    assert entropy["tool_result_budget"] == {
        "message_budget": 2400,
        "remaining_budget": 600,
    }
    assert entropy["tool_use_summary"] == {
        "summary": "2 tool results compacted into artifact previews.",
        "artifact_refs": ["artifact://tool-result-1"],
    }


def test_query_execution_runtime_projects_compaction_visibility_when_available() -> None:
    class _FakeCompactionService:
        @staticmethod
        def build_visibility_payload(payload: dict[str, object] | None) -> dict[str, object]:
            return dict(payload or {})

        def runtime_visibility_payload(self) -> dict[str, object]:
            return {
                "compaction_state": {
                    "mode": "microcompact",
                    "summary": "Compacted 2 oversized tool results.",
                    "spill_count": 1,
                },
                "tool_result_budget": {
                    "message_budget": 2400,
                    "remaining_budget": 600,
                },
                "tool_use_summary": {
                    "summary": "2 tool results compacted into artifact previews.",
                    "artifact_refs": ["artifact://tool-result-1"],
                },
            }

    service = KernelQueryExecutionService(
        session_backend=object(),
        conversation_compaction_service=_FakeCompactionService(),
    )

    entropy = service.get_query_runtime_entropy_contract()

    assert entropy["compaction_state"] == {
        "mode": "microcompact",
        "summary": "Compacted 2 oversized tool results.",
        "spill_count": 1,
    }
    assert entropy["tool_result_budget"] == {
        "message_budget": 2400,
        "remaining_budget": 600,
    }
    assert entropy["tool_use_summary"] == {
        "summary": "2 tool results compacted into artifact previews.",
        "artifact_refs": ["artifact://tool-result-1"],
    }


def test_query_execution_runtime_exposes_bounded_donor_trial_carry_forward_contract() -> None:
    service = KernelQueryExecutionService(
        session_backend=object(),
        conversation_compaction_service=object(),
    )

    entropy = service.get_query_runtime_entropy_contract()

    assert entropy["runtime_entropy"]["donor_trial_budget"] == {
        "accepted_scalar_fields": [
            "candidate_id",
            "skill_candidate_id",
            "skill_trial_id",
            "skill_lifecycle_stage",
            "selected_scope",
            "selected_seat_ref",
        ],
        "accepted_list_fields": [
            "replacement_target_ids",
            "rollback_target_ids",
            "capability_ids",
        ],
        "max_list_items": 3,
        "acceptance": "bounded-runtime-metadata",
        "state_channel": "query_runtime_state",
        "summary_surface": "runtime-center",
        "spill_surface": "runtime-evidence",
    }
    assert entropy["runtime_entropy"]["donor_trial_carry_forward_status"] == "inactive"
    assert entropy["runtime_entropy"]["degraded_components"] == []
    assert entropy["donor_trial_carry_forward"] == {
        "status": "inactive",
        "summary": "No donor/trial metadata carry-forward is active.",
        "retained_metadata_keys": [],
        "truncated_metadata_keys": [],
        "artifact_refs": [],
    }


def test_query_execution_runtime_projects_donor_trial_carry_forward_degradation() -> None:
    class _CompactionService:
        @staticmethod
        def build_visibility_payload(source: dict[str, object] | None = None) -> dict[str, object]:
            return ConversationCompactionService.build_visibility_payload(source)

        def runtime_visibility_payload(self) -> dict[str, object]:
            return {
                "donor_trial_carry_forward": {
                    "status": "degraded",
                    "summary": "Donor/trial metadata overflow compacted into runtime evidence.",
                    "retained_metadata_keys": [
                        "skill_candidate_id",
                        "skill_trial_id",
                        "selected_scope",
                    ],
                    "truncated_metadata_keys": [
                        "replacement_target_ids",
                        "capability_ids",
                        "ignored_field",
                    ],
                    "artifact_refs": [
                        "artifact://entropy-donor-1",
                        "artifact://entropy-donor-2",
                    ],
                    "ignored": "drop-me",
                },
            }

    service = KernelQueryExecutionService(
        session_backend=object(),
        conversation_compaction_service=_CompactionService(),
    )

    entropy = service.get_query_runtime_entropy_contract()

    assert entropy["status"] == "degraded"
    assert entropy["runtime_entropy"]["status"] == "degraded"
    assert entropy["runtime_entropy"]["donor_trial_carry_forward_status"] == "degraded"
    assert entropy["runtime_entropy"]["failure_source"] == "donor-trial-carry-forward"
    assert entropy["runtime_entropy"]["degraded_components"] == [
        "donor_trial_carry_forward",
    ]
    assert entropy["donor_trial_carry_forward"] == {
        "status": "degraded",
        "summary": "Donor/trial metadata overflow compacted into runtime evidence.",
        "retained_metadata_keys": [
            "skill_candidate_id",
            "skill_trial_id",
            "selected_scope",
        ],
        "truncated_metadata_keys": [
            "replacement_target_ids",
            "capability_ids",
        ],
        "artifact_refs": [
            "artifact://entropy-donor-1",
            "artifact://entropy-donor-2",
        ],
    }
    degradation = entropy["degradation"]["donor_trial_carry_forward"]
    assert degradation["failure_source"] == "donor-trial-carry-forward"
    assert "runtime evidence" in degradation["remediation_summary"]


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

    attribution = {
        "skill_candidate_id": "candidate-nextgen-outreach",
        "skill_trial_id": "trial-nextgen-seat-1",
        "skill_lifecycle_stage": "trial",
        "selected_scope": "seat",
        "replacement_target_ids": ["skill:legacy_outreach"],
    }

    shell_sink = service._make_shell_evidence_sink(  # pylint: disable=protected-access
        "ktask:query-tool",
        capability_trial_attribution=attribution,
    )
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

    file_sink = service._make_file_evidence_sink(  # pylint: disable=protected-access
        "ktask:query-tool",
        capability_trial_attribution=attribution,
    )
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

    browser_sink = service._make_browser_evidence_sink(  # pylint: disable=protected-access
        "ktask:query-tool",
        capability_trial_attribution=attribution,
    )
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
    assert shell_meta["skill_candidate_id"] == "candidate-nextgen-outreach"
    assert shell_meta["skill_trial_id"] == "trial-nextgen-seat-1"
    assert shell_meta["selected_scope"] == "seat"
    assert shell_meta["replacement_target_ids"] == ["skill:legacy_outreach"]

    file_meta = bridge.file_calls[0]["payload"]["metadata"]
    assert file_meta["tool_contract"] == "tool:write_file"
    assert file_meta["action_mode"] == "write"
    assert file_meta["read_only"] is False
    assert file_meta["concurrency_class"] == "serial-write"
    assert file_meta["preflight_policy"] == "inline"
    assert file_meta["skill_candidate_id"] == "candidate-nextgen-outreach"
    assert file_meta["skill_trial_id"] == "trial-nextgen-seat-1"
    assert file_meta["selected_scope"] == "seat"

    browser_meta = bridge.browser_calls[0]["payload"]["metadata"]
    assert browser_meta["tool_contract"] == "tool:browser_use"
    assert browser_meta["action_mode"] == "write"
    assert browser_meta["read_only"] is False
    assert browser_meta["concurrency_class"] == "serial-write"
    assert browser_meta["preflight_policy"] == "inline"
    assert browser_meta["skill_candidate_id"] == "candidate-nextgen-outreach"
    assert browser_meta["skill_trial_id"] == "trial-nextgen-seat-1"
    assert browser_meta["selected_scope"] == "seat"


def test_query_execution_runtime_bounds_trial_attribution_list_carry_forward() -> None:
    class _ToolBridge:
        def __init__(self) -> None:
            self.shell_calls: list[dict[str, object]] = []

        def record_shell_event(self, task_id: str, payload: dict[str, object]) -> None:
            self.shell_calls.append({"task_id": task_id, "payload": payload})

    bridge = _ToolBridge()
    service = KernelQueryExecutionService(
        session_backend=object(),
        tool_bridge=bridge,
    )

    shell_sink = service._make_shell_evidence_sink(  # pylint: disable=protected-access
        "ktask:query-tool",
        capability_trial_attribution={
            "skill_candidate_id": "candidate-nextgen-outreach",
            "skill_trial_id": "trial-nextgen-seat-1",
            "skill_lifecycle_stage": "trial",
            "selected_scope": "seat",
            "replacement_target_ids": [
                "skill:legacy-outreach-1",
                "skill:legacy-outreach-2",
                "skill:legacy-outreach-3",
                "skill:legacy-outreach-4",
            ],
            "rollback_target_ids": [
                "skill:rollback-1",
                "skill:rollback-2",
                "skill:rollback-3",
                "skill:rollback-4",
            ],
            "capability_ids": [
                "tool:execute_shell_command",
                "tool:write_file",
                "tool:browser_use",
                "tool:ignored-overflow",
            ],
            "ignored_key": "drop-me",
        },
    )
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

    metadata = bridge.shell_calls[0]["payload"]["metadata"]
    assert metadata["replacement_target_ids"] == [
        "skill:legacy-outreach-1",
        "skill:legacy-outreach-2",
        "skill:legacy-outreach-3",
    ]
    assert metadata["rollback_target_ids"] == [
        "skill:rollback-1",
        "skill:rollback-2",
        "skill:rollback-3",
    ]
    assert metadata["capability_ids"] == [
        "tool:execute_shell_command",
        "tool:write_file",
        "tool:browser_use",
    ]
    assert "ignored_key" not in metadata


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


def test_query_execution_runtime_filters_capabilities_by_effective_seat_layers(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "query-runtime-seat-capability-layers.db")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-support",
            actor_key="industry-1:support-specialist",
            actor_fingerprint="fingerprint-support",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            metadata={
                "capability_layers": {
                    "schema_version": "industry-seat-capability-layers-v1",
                    "role_prototype_capability_ids": ["tool:read_file"],
                    "seat_instance_capability_ids": ["skill:crm-seat-playbook"],
                    "cycle_delta_capability_ids": ["mcp:campaign-dashboard"],
                    "session_overlay_capability_ids": ["mcp:browser-temp"],
                    "effective_capability_ids": [
                        "tool:read_file",
                        "skill:crm-seat-playbook",
                        "mcp:campaign-dashboard",
                        "mcp:browser-temp",
                    ],
                },
            },
        ),
    )

    def _mount(capability_id: str, source_kind: str) -> SimpleNamespace:
        return SimpleNamespace(id=capability_id, source_kind=source_kind)

    capability_service = SimpleNamespace(
        list_accessible_capabilities=lambda *, agent_id, enabled_only=True: [
            _mount("tool:read_file", "tool"),
            _mount("tool:write_file", "tool"),
            _mount("skill:crm-seat-playbook", "skill"),
            _mount("skill:generic-overlap", "skill"),
            _mount("mcp:campaign-dashboard", "mcp"),
            _mount("mcp:browser-temp", "mcp"),
            _mount("mcp:desktop_windows", "mcp"),
        ],
    )
    service = KernelQueryExecutionService(
        session_backend=object(),
        capability_service=capability_service,
        agent_runtime_repository=runtime_repository,
    )

    (
        tool_capability_ids,
        skill_names,
        mcp_client_keys,
        system_capability_ids,
        desktop_actuation_available,
        capability_layers,
    ) = service._resolve_query_capability_context("agent-support")  # pylint: disable=protected-access

    assert tool_capability_ids == {"tool:read_file"}
    assert skill_names == {"crm-seat-playbook"}
    assert mcp_client_keys == ["browser-temp", "campaign-dashboard"]
    assert system_capability_ids == set()
    assert desktop_actuation_available is False
    assert capability_layers is not None
    assert capability_layers.role_prototype_capability_ids == ["tool:read_file"]
    assert capability_layers.seat_instance_capability_ids == ["skill:crm-seat-playbook"]
    assert capability_layers.cycle_delta_capability_ids == ["mcp:campaign-dashboard"]
    assert capability_layers.session_overlay_capability_ids == ["mcp:browser-temp"]
