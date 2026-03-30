# -*- coding: utf-8 -*-
from __future__ import annotations

import copaw.memory as memory_module
from copaw.memory import (
    DerivedMemoryIndexService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
)
from copaw.state import AgentReportRecord, SQLiteStateStore, StrategyMemoryRecord
from copaw.state.work_context_service import WorkContextService
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteKnowledgeChunkRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteStrategyMemoryRepository,
    SqliteWorkContextRepository,
)
from copaw.state.strategy_memory_service import StateStrategyMemoryService


def _build_memory_services(tmp_path, *, sidecar_backends=None):
    store = SQLiteStateStore(tmp_path / "state.db")
    knowledge_repo = SqliteKnowledgeChunkRepository(store)
    strategy_repo = SqliteStrategyMemoryRepository(store)
    agent_report_repo = SqliteAgentReportRepository(store)
    fact_repo = SqliteMemoryFactIndexRepository(store)
    entity_repo = SqliteMemoryEntityViewRepository(store)
    opinion_repo = SqliteMemoryOpinionViewRepository(store)
    reflection_repo = SqliteMemoryReflectionRunRepository(store)
    derived = DerivedMemoryIndexService(
        fact_index_repository=fact_repo,
        entity_view_repository=entity_repo,
        opinion_view_repository=opinion_repo,
        reflection_run_repository=reflection_repo,
        knowledge_repository=knowledge_repo,
        strategy_repository=strategy_repo,
        agent_report_repository=agent_report_repo,
        sidecar_backends=list(sidecar_backends or []),
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
    strategy = StateStrategyMemoryService(
        repository=strategy_repo,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    retain = MemoryRetainService(
        knowledge_service=knowledge,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    recall = MemoryRecallService(
        derived_index_service=derived,
        sidecar_backends=list(sidecar_backends or []),
    )
    return store, knowledge, strategy, retain, recall, reflection, derived


def test_memory_vnext_rebuild_recall_and_reflect(tmp_path) -> None:
    _store, knowledge, strategy, _retain, recall, reflection, derived = _build_memory_services(tmp_path)

    knowledge.remember_fact(
        title="Outbound policy",
        content="The team should only send outbound messages after evidence review.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["policy", "outbound"],
    )
    strategy.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-1:copaw-agent-runner",
            scope_type="industry",
            scope_id="industry-1",
            owner_agent_id="copaw-agent-runner",
            industry_instance_id="industry-1",
            title="Industry memory strategy",
            summary="Operate with evidence-first outbound discipline.",
            north_star="Protect quality before throughput.",
            evidence_requirements=["Evidence review before outbound action"],
        ),
    )

    rebuild = derived.rebuild_all(
        scope_type="industry",
        scope_id="industry-1",
        include_reporting=False,
        include_learning=False,
        evidence_limit=0,
    )
    assert rebuild.fact_index_count >= 2
    assert rebuild.source_counts["knowledge_chunk"] >= 1
    assert rebuild.source_counts["strategy_memory"] >= 1

    reflected = reflection.reflect(
        scope_type="industry",
        scope_id="industry-1",
        trigger_kind="test",
        create_learning_proposals=False,
    )
    assert reflected.entity_count >= 1
    assert reflected.opinion_count >= 1

    recalled = recall.recall(
        query="evidence review before outbound",
        scope_type="industry",
        scope_id="industry-1",
        role="execution-core",
        limit=5,
    )
    assert recalled.backend_used == "truth-first"
    assert recalled.hits
    assert any(hit.source_type == "knowledge_chunk" for hit in recalled.hits)

    entities = derived.list_entity_views(scope_type="industry", scope_id="industry-1")
    opinions = derived.list_opinion_views(scope_type="industry", scope_id="industry-1")
    assert entities
    assert opinions


def test_memory_retain_service_turns_agent_report_into_canonical_memory(tmp_path) -> None:
    _store, knowledge, _strategy, retain, _recall, _reflection, derived = _build_memory_services(tmp_path)

    report = AgentReportRecord(
        id="report-1",
        industry_instance_id="industry-1",
        owner_agent_id="worker-1",
        owner_role_id="researcher",
        headline="Weekly review completed",
        summary="Weekly review recommends holding outbound until evidence is updated.",
        status="recorded",
        result="completed",
        evidence_ids=["evidence-1"],
    )
    retain.retain_agent_report(report)

    memory_records = knowledge.list_memory(
        industry_instance_id="industry-1",
        query="holding outbound until evidence is updated",
        limit=10,
    )
    assert any(item.title == "Weekly review completed" for item in memory_records)

    fact_entries = derived.list_fact_entries(
        source_type="agent_report",
        source_ref="report-1",
        limit=None,
    )
    assert len(fact_entries) == 1
    assert fact_entries[0].industry_instance_id == "industry-1"


def test_memory_package_does_not_export_qmd_runtime_symbols() -> None:
    assert not hasattr(memory_module, "QmdBackendConfig")
    assert not hasattr(memory_module, "QmdRecallBackend")


def test_memory_recall_prefers_work_context_hits_over_related_scopes(tmp_path) -> None:
    _store, knowledge, _strategy, _retain, recall, _reflection, _derived = _build_memory_services(tmp_path)

    knowledge.remember_fact(
        title="Continuity anchor",
        content="Use this anchor for follow-up reporting and replan continuity.",
        scope_type="work_context",
        scope_id="ctx-followup",
        role_bindings=["execution-core"],
        tags=["follow-up", "continuity"],
    )
    knowledge.remember_fact(
        title="Continuity anchor",
        content="Use this anchor for follow-up reporting and replan continuity.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["follow-up", "continuity"],
    )

    recalled = recall.recall(
        query="follow-up reporting replan continuity anchor",
        work_context_id="ctx-followup",
        industry_instance_id="industry-1",
        role="execution-core",
        include_related_scopes=True,
        limit=5,
    )

    assert recalled.hits
    assert recalled.hits[0].scope_type == "work_context"
    assert recalled.hits[0].scope_id == "ctx-followup"
    assert recalled.hits[0].source_ref


def test_work_context_service_deep_merges_metadata_payloads(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    store.initialize()
    service = WorkContextService(
        repository=SqliteWorkContextRepository(store),
    )
    created = service.ensure_context(
        context_id="ctx-1",
        title="Context 1",
        metadata={
            "continuity": {
                "thread_id": "thread-1",
                "scheduler": {
                    "action": "resume",
                },
            },
        },
    )
    updated = service.ensure_context(
        context_id=created.id,
        title="Context 1",
        metadata={
            "continuity": {
                "scheduler": {
                    "approved": True,
                },
            },
            "notes": {
                "owner": "execution-core",
            },
        },
    )

    assert updated.metadata["continuity"]["thread_id"] == "thread-1"
    assert updated.metadata["continuity"]["scheduler"]["action"] == "resume"
    assert updated.metadata["continuity"]["scheduler"]["approved"] is True
    assert updated.metadata["notes"]["owner"] == "execution-core"


def test_memory_recall_service_exposes_no_sidecar_shutdown_surface() -> None:
    service = MemoryRecallService(
        derived_index_service=object(),
        sidecar_backends=[],
    )

    assert not hasattr(service, "close_sidecar_backends")
