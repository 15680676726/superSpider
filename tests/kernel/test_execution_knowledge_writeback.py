# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.memory import DerivedMemoryIndexService, MemoryReflectionService
from copaw.kernel import KernelQueryExecutionService
from copaw.kernel.runtime_outcome import build_execution_knowledge_writeback
from copaw.state import AgentRuntimeRecord, SQLiteStateStore
from copaw.state.execution_feedback import collect_recent_execution_feedback
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.repositories import (
    SqliteAgentRuntimeRepository,
    SqliteKnowledgeChunkRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteMemoryRelationViewRepository,
)


def test_build_execution_knowledge_writeback_emits_failure_and_recovery_patterns() -> None:
    summary = build_execution_knowledge_writeback(
        scope_type="work_context",
        scope_id="ctx-1",
        outcome_ref="checkpoint-1",
        outcome="blocked",
        summary="Shell command blocked by safety policy.",
        capability_ref="tool:shell",
        environment_ref="workspace:repo",
        risk_level="guarded",
        failure_source="blocked",
        blocked_next_step="Review the pending decision request before retrying the turn.",
        evidence_refs=["evidence-1"],
        recovery_summary="Retry after operator approval.",
    )

    assert summary["scope_type"] == "work_context"
    assert summary["scope_id"] == "ctx-1"
    assert summary["outcome"] == "blocked"
    assert summary["capability_ref"] == "tool:shell"
    assert summary["environment_ref"] == "workspace:repo"
    assert summary["risk_level"] == "guarded"
    assert {"runtime_outcome", "failure_pattern", "recovery_pattern"} <= set(
        summary["node_types"],
    )
    assert {"indicates", "recovers_with"} <= set(summary["relation_types"])


def _build_knowledge_services(tmp_path):
    store = SQLiteStateStore(tmp_path / "query-knowledge.sqlite3")
    knowledge_repo = SqliteKnowledgeChunkRepository(store)
    fact_repo = SqliteMemoryFactIndexRepository(store)
    entity_repo = SqliteMemoryEntityViewRepository(store)
    opinion_repo = SqliteMemoryOpinionViewRepository(store)
    relation_repo = SqliteMemoryRelationViewRepository(store)
    reflection_repo = SqliteMemoryReflectionRunRepository(store)
    derived = DerivedMemoryIndexService(
        fact_index_repository=fact_repo,
        entity_view_repository=entity_repo,
        opinion_view_repository=opinion_repo,
        relation_view_repository=relation_repo,
        reflection_run_repository=reflection_repo,
    )
    reflection = MemoryReflectionService(
        derived_index_service=derived,
        entity_view_repository=entity_repo,
        opinion_view_repository=opinion_repo,
        reflection_run_repository=reflection_repo,
    )
    knowledge = StateKnowledgeService(
        repository=knowledge_repo,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    return knowledge, derived


def test_query_execution_runtime_persists_knowledge_writeback_to_agent_runtime(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "query-runtime.sqlite3")
    runtime_repository = SqliteAgentRuntimeRepository(store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="ops-agent",
            actor_key="industry:ops:execution-core",
            actor_fingerprint="fp-ops",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="executing",
            current_task_id="task-1",
            metadata={},
        ),
    )
    service = KernelQueryExecutionService(
        session_backend=object(),
        agent_runtime_repository=runtime_repository,
    )

    service._mark_actor_query_finished(  # pylint: disable=protected-access
        agent_id="ops-agent",
        task_id="task-1",
        session_id="industry-chat:ops",
        user_id="default",
        conversation_thread_id="industry-chat:ops",
        channel="console",
        summary="Shell command blocked by safety policy.",
        error="blocked by shell safety policy",
        execution_context={
            "work_context_id": "ctx-ops-1",
            "main_brain_runtime": {
                "risk_level": "guarded",
                "environment": {"ref": "workspace:repo"},
            },
        },
        stream_step_count=3,
    )

    runtime = runtime_repository.get_runtime("ops-agent")
    assert runtime is not None
    assert runtime.runtime_status == "blocked"
    knowledge = dict((runtime.metadata or {}).get("knowledge_writeback") or {})
    assert knowledge["scope_type"] == "work_context"
    assert knowledge["scope_id"] == "ctx-ops-1"
    assert knowledge["outcome"] == "blocked"
    assert knowledge["capability_ref"] == "system:dispatch_query"
    assert knowledge["environment_ref"] == "workspace:repo"
    assert {"runtime_outcome", "failure_pattern"} <= set(knowledge["node_types"])


def test_query_execution_runtime_persists_knowledge_writeback_into_memory(tmp_path) -> None:
    knowledge_service, derived = _build_knowledge_services(tmp_path)
    store = SQLiteStateStore(tmp_path / "query-runtime.sqlite3")
    runtime_repository = SqliteAgentRuntimeRepository(store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="ops-agent",
            actor_key="industry:ops:execution-core",
            actor_fingerprint="fp-ops",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="executing",
            current_task_id="task-1",
            metadata={},
        ),
    )
    service = KernelQueryExecutionService(
        session_backend=object(),
        agent_runtime_repository=runtime_repository,
        knowledge_service=knowledge_service,
    )

    service._mark_actor_query_finished(  # pylint: disable=protected-access
        agent_id="ops-agent",
        task_id="task-1",
        session_id="industry-chat:ops",
        user_id="default",
        conversation_thread_id="industry-chat:ops",
        channel="console",
        summary="Shell command blocked by safety policy.",
        error="blocked by shell safety policy",
        execution_context={
            "work_context_id": "ctx-ops-1",
            "main_brain_runtime": {
                "risk_level": "guarded",
                "environment": {"ref": "workspace:repo"},
            },
        },
        stream_step_count=3,
    )

    fact_entries = derived.list_fact_entries(
        scope_type="work_context",
        scope_id="ctx-ops-1",
        limit=None,
    )
    assert any(
        entry.id.startswith("runtime-outcome:")
        and (entry.metadata or {}).get("knowledge_graph_node_type") == "runtime_outcome"
        for entry in fact_entries
    )
    relation_views = derived.list_relation_views(
        scope_type="work_context",
        scope_id="ctx-ops-1",
        limit=None,
    )
    assert any(view.relation_kind == "indicates" for view in relation_views)


def test_collect_recent_execution_feedback_exposes_execution_knowledge_anchors() -> None:
    feedback = collect_recent_execution_feedback(
        tasks=[
            SimpleNamespace(
                id="task-1",
                title="Prepare evidence brief",
                status="running",
                updated_at="2026-03-17T08:30:00+00:00",
            ),
            SimpleNamespace(
                id="task-2",
                title="Inspect feedback loop",
                status="running",
                updated_at="2026-03-17T09:15:00+00:00",
            ),
        ],
        task_runtime_repository=SimpleNamespace(
            get_runtime=lambda task_id: (
                SimpleNamespace(
                    task_id="task-2",
                    current_phase="verify-brief",
                    updated_at="2026-03-17T09:30:00+00:00",
                )
                if task_id == "task-2"
                else None
            ),
        ),
        evidence_ledger=SimpleNamespace(
            list_recent=lambda limit=80, **_: [
                SimpleNamespace(
                    id="evidence-fail-1",
                    task_id="task-2",
                    capability_ref="tool:browser_use",
                    environment_ref="browser:partner-portal",
                    risk_level="guarded",
                    action_summary="Retry storefront login",
                    result_summary="Login failed due to stale OTP.",
                    created_at="2026-03-17T09:29:00+00:00",
                ),
                SimpleNamespace(
                    id="evidence-ok-1",
                    task_id="task-1",
                    capability_ref="tool:read_file",
                    environment_ref="workspace:ops",
                    risk_level="auto",
                    action_summary="Review previous execution brief",
                    result_summary="Recovered the next owner and blocker summary.",
                    created_at="2026-03-17T09:10:00+00:00",
                ),
            ],
        ),
    )

    assert feedback["capability_refs"] == ["tool:browser_use", "tool:read_file"]
    assert feedback["environment_refs"] == ["browser:partner-portal", "workspace:ops"]
    assert feedback["risk_levels"] == ["guarded", "auto"]
    assert feedback["failure_patterns"] == feedback["recent_failures"]
    assert feedback["recovery_patterns"] == feedback["effective_actions"]
