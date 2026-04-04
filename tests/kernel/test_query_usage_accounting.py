# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from copaw.evidence import EvidenceLedger
from copaw.kernel.query_execution import KernelQueryExecutionService
from copaw.state import (
    AgentRuntimeRecord,
    SQLiteStateStore,
    TaskRecord,
    TaskRuntimeRecord,
)
from copaw.state.repositories import (
    SqliteAgentRuntimeRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


def test_record_turn_usage_persists_runtime_and_evidence(tmp_path, monkeypatch) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    agent_runtime_repository = SqliteAgentRuntimeRepository(state_store)
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    agent_runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="agent-1",
        ),
    )
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
    service = KernelQueryExecutionService(
        session_backend=object(),
        agent_profile_service=SimpleNamespace(
            get_agent=lambda agent_id: (
                SimpleNamespace(agent_id=agent_id)
                if agent_id == "agent-1"
                else None
            ),
            list_agents=lambda: [SimpleNamespace(agent_id="agent-1")],
        ),
        agent_runtime_repository=agent_runtime_repository,
        task_runtime_repository=task_runtime_repository,
        evidence_ledger=evidence_ledger,
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

    runtime = agent_runtime_repository.get_runtime("agent-1")
    assert runtime is not None
    assert runtime.metadata["last_query_usage"] == {
        "input_tokens": 5,
        "output_tokens": 3,
        "cost_estimate": 0.12,
        "prompt_tokens": 5,
        "completion_tokens": 3,
        "total_tokens": 8,
    }
    assert runtime.metadata["query_usage_totals"] == {
        "prompt_tokens": 5,
        "completion_tokens": 3,
        "total_tokens": 8,
    }
    assert runtime.metadata["query_cost_total_estimate"] == 0.12
    assert runtime.metadata["last_query_model_context"] == {
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
    assert evidence.metadata["usage"] == {
        "input_tokens": 5,
        "output_tokens": 3,
        "cost_estimate": 0.12,
        "prompt_tokens": 5,
        "completion_tokens": 3,
        "total_tokens": 8,
    }
    assert evidence.metadata["cost_estimate"] == 0.12
    assert evidence.metadata["owner_agent_id"] == "agent-1"
    assert evidence.metadata["skill_candidate_id"] == "cand-browser-runtime"
    assert evidence.metadata["skill_trial_id"] == "trial-browser-runtime-seat-primary"
    assert evidence.metadata["skill_lifecycle_stage"] == "trial"
    assert evidence.metadata["selected_scope"] == "seat"
    assert evidence.metadata["selected_seat_ref"] == "seat-primary"
    assert evidence.metadata["donor_id"] == "donor-browser-runtime"
    assert evidence.metadata["package_id"] == "pkg-browser-runtime"
    assert evidence.metadata["source_profile_id"] == "source-browser-runtime"
    assert evidence.metadata["candidate_source_kind"] == "external_catalog"
    assert evidence.metadata["resolution_kind"] == "reuse_existing_candidate"
    assert evidence.metadata["replacement_target_ids"] == ["mcp:legacy_browser"]
    assert evidence.metadata["rollback_target_ids"] == ["mcp:legacy_browser"]


def test_record_turn_usage_does_not_instantiate_provider_manager_fallback(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    agent_runtime_repository = SqliteAgentRuntimeRepository(state_store)
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    agent_runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-2",
            actor_key="agent-2",
        ),
    )
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

    service = KernelQueryExecutionService(
        session_backend=object(),
        agent_profile_service=SimpleNamespace(
            get_agent=lambda agent_id: (
                SimpleNamespace(agent_id=agent_id)
                if agent_id == "agent-2"
                else None
            ),
            list_agents=lambda: [SimpleNamespace(agent_id="agent-2")],
        ),
        agent_runtime_repository=agent_runtime_repository,
        task_runtime_repository=task_runtime_repository,
        evidence_ledger=evidence_ledger,
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
        usage={
            "input_tokens": 2,
            "output_tokens": 1,
        },
    )

    runtime = agent_runtime_repository.get_runtime("agent-2")
    assert runtime is not None
    assert "last_query_model_context" not in (runtime.metadata or {})
