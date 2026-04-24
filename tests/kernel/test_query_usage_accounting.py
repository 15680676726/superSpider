# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from copaw.evidence import EvidenceLedger
from copaw.kernel.query_execution import KernelQueryExecutionService
from copaw.state import SQLiteStateStore, TaskRecord, TaskRuntimeRecord
from copaw.state.executor_runtime_service import ExecutorRuntimeService
from copaw.state.repositories import SqliteTaskRepository, SqliteTaskRuntimeRepository


def _build_executor_runtime_service(
    state_store: SQLiteStateStore,
    *,
    agent_id: str,
    task_id: str,
    session_id: str,
):
    executor_runtime_service = ExecutorRuntimeService(state_store=state_store)
    runtime = executor_runtime_service.create_or_reuse_runtime(
        executor_id="codex",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id=task_id,
        role_id=agent_id,
        thread_id=session_id,
        metadata={"owner_agent_id": agent_id},
        continuity_metadata={
            "control_thread_id": session_id,
            "session_id": session_id,
        },
    )
    executor_runtime_service.mark_runtime_ready(
        runtime.runtime_id,
        thread_id=session_id,
        metadata={"owner_agent_id": agent_id},
    )
    return executor_runtime_service, runtime


def _build_service(
    *,
    agent_id: str,
    task_id: str,
    task_runtime_repository: SqliteTaskRuntimeRepository,
    evidence_ledger: EvidenceLedger,
    executor_runtime_service: ExecutorRuntimeService,
    provider_manager: object | None,
) -> KernelQueryExecutionService:
    return KernelQueryExecutionService(
        session_backend=object(),
        agent_profile_service=SimpleNamespace(
            get_agent=lambda resolved_agent_id: (
                SimpleNamespace(agent_id=resolved_agent_id)
                if resolved_agent_id == agent_id
                else None
            ),
            list_agents=lambda: [SimpleNamespace(agent_id=agent_id)],
        ),
        task_runtime_repository=task_runtime_repository,
        evidence_ledger=evidence_ledger,
        provider_manager=provider_manager,
        executor_runtime_service=executor_runtime_service,
    )


def test_record_turn_usage_persists_executor_runtime_and_evidence(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    executor_runtime_service, runtime = _build_executor_runtime_service(
        state_store,
        agent_id="agent-1",
        task_id="task-1",
        session_id="sess-usage",
    )
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    task_repository.upsert_task(
        TaskRecord(
            id="task-1",
            title="Track query usage",
            task_type="system:dispatch_query",
            owner_agent_id="agent-1",
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-1",
            risk_level="guarded",
            last_owner_agent_id="agent-1",
        ),
    )

    service = _build_service(
        agent_id="agent-1",
        task_id="task-1",
        task_runtime_repository=task_runtime_repository,
        evidence_ledger=evidence_ledger,
        executor_runtime_service=executor_runtime_service,
        provider_manager=SimpleNamespace(
            resolve_model_slot=lambda: (
                SimpleNamespace(provider_id="openai", model="gpt-5"),
                False,
                "Using configured active model.",
                [],
            ),
        ),
    )
    request = AgentRequest(
        id="req-usage",
        session_id="sess-usage",
        user_id="user-usage",
        channel="console",
        input=[],
    )
    request.agent_id = "agent-1"
    request.capability_trial_attribution = {
        "candidate_id": "cand-browser-runtime",
        "skill_trial_id": "trial-browser-runtime-seat-primary",
        "skill_lifecycle_stage": "trial",
        "selected_scope": "seat",
        "selected_seat_ref": "seat-primary",
        "donor_id": "donor-browser-runtime",
        "package_id": "pkg-browser-runtime",
        "source_profile_id": "source-browser-runtime",
        "candidate_source_kind": "external_catalog",
        "resolution_kind": "reuse_existing_candidate",
        "replacement_target_ids": ["mcp:legacy_browser"],
        "rollback_target_ids": ["mcp:legacy_browser"],
    }

    service.record_turn_usage(
        request=request,
        kernel_task_id="task-1",
        usage={
            "input_tokens": 5,
            "output_tokens": 3,
            "cost_estimate": 0.12,
        },
    )

    updated_runtime = executor_runtime_service.get_runtime(runtime.runtime_id)
    assert updated_runtime is not None
    assert updated_runtime.metadata["last_query_usage"] == {
        "input_tokens": 5,
        "output_tokens": 3,
        "cost_estimate": 0.12,
        "prompt_tokens": 5,
        "completion_tokens": 3,
        "total_tokens": 8,
    }
    assert updated_runtime.metadata["query_usage_totals"] == {
        "prompt_tokens": 5,
        "completion_tokens": 3,
        "total_tokens": 8,
    }
    assert updated_runtime.metadata["query_cost_total_estimate"] == 0.12
    assert updated_runtime.metadata["last_query_model_context"] == {
        "provider_id": "openai",
        "model": "gpt-5",
        "slot_source": "active",
        "selection_reason": "Using configured active model.",
        "unavailable_slots": [],
    }

    task_runtime = task_runtime_repository.get_runtime("task-1")
    assert task_runtime is not None
    assert task_runtime.last_evidence_id
    evidence = evidence_ledger.get_record(task_runtime.last_evidence_id)
    assert evidence is not None
    assert evidence.task_id == "task-1"
    assert evidence.capability_ref == "system:dispatch_query"
    assert evidence.risk_level == "guarded"
    assert evidence.metadata["usage"]["total_tokens"] == 8
    assert evidence.metadata["cost_estimate"] == 0.12
    assert evidence.metadata["owner_agent_id"] == "agent-1"
    assert evidence.metadata["skill_candidate_id"] == "cand-browser-runtime"


def test_record_turn_usage_does_not_instantiate_provider_manager_fallback(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    executor_runtime_service, runtime = _build_executor_runtime_service(
        state_store,
        agent_id="agent-2",
        task_id="task-2",
        session_id="sess-no-provider",
    )
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    task_repository.upsert_task(
        TaskRecord(
            id="task-2",
            title="Track usage without provider fallback",
            task_type="system:dispatch_query",
            owner_agent_id="agent-2",
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-2",
            risk_level="auto",
            last_owner_agent_id="agent-2",
        ),
    )

    service = _build_service(
        agent_id="agent-2",
        task_id="task-2",
        task_runtime_repository=task_runtime_repository,
        evidence_ledger=evidence_ledger,
        executor_runtime_service=executor_runtime_service,
        provider_manager=None,
    )
    request = AgentRequest(
        id="req-no-provider",
        session_id="sess-no-provider",
        user_id="user-no-provider",
        channel="console",
        input=[],
    )
    request.agent_id = "agent-2"

    service.record_turn_usage(
        request=request,
        kernel_task_id="task-2",
        usage={"input_tokens": 2, "output_tokens": 1},
    )

    updated_runtime = executor_runtime_service.get_runtime(runtime.runtime_id)
    assert updated_runtime is not None
    assert updated_runtime.metadata["last_query_usage"]["total_tokens"] == 3
    assert "last_query_model_context" not in (updated_runtime.metadata or {})
