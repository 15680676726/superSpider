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


def test_memory_retain_service_filters_low_value_chat_noise_from_formal_memory(tmp_path) -> None:
    _store, knowledge, _strategy, retain, _recall, _reflection, derived = _build_memory_services(tmp_path)

    result = retain.retain_chat_writeback(
        industry_instance_id="industry-1",
        title="Quick reply",
        content="ok thanks",
        source_ref="chat:thread-1:msg-1",
        tags=["chat-noise", "small-talk"],
    )

    assert result is None
    assert knowledge.list_chunks(document_id="memory:industry:industry-1", limit=None) == []
    assert derived.list_fact_entries(scope_type="industry", scope_id="industry-1", limit=None) == []


def test_memory_retain_service_routes_report_outcome_to_work_context_memory(tmp_path) -> None:
    _store, knowledge, _strategy, retain, _recall, _reflection, _derived = _build_memory_services(tmp_path)

    report = AgentReportRecord(
        id="report-ctx-1",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        owner_agent_id="worker-1",
        owner_role_id="researcher",
        headline="Follow-up completed",
        summary="The follow-up closed the blocker and confirmed the next check-in window.",
        status="recorded",
        result="completed",
        evidence_ids=["evidence-1"],
    )

    retain.retain_agent_report(report)

    work_context_chunks = knowledge.list_chunks(document_id="memory:work_context:ctx-1", limit=None)
    industry_chunks = knowledge.list_chunks(document_id="memory:industry:industry-1", limit=None)
    assert len(work_context_chunks) == 1
    assert industry_chunks == []
    assert "Result: completed" in work_context_chunks[0].content
    assert "closed the blocker" in work_context_chunks[0].content


def test_memory_retain_service_keeps_shared_writeback_in_industry_scope_without_work_context(tmp_path) -> None:
    _store, knowledge, _strategy, retain, _recall, _reflection, _derived = _build_memory_services(tmp_path)

    result = retain.retain_chat_writeback(
        industry_instance_id="industry-1",
        title="Shared operating note",
        content="Evidence review stays mandatory before outbound approval.",
        source_ref="report:industry-shared-1",
        tags=["report-outcome", "shared-memory"],
    )

    assert result == {
        "industry_instance_id": "industry-1",
        "work_context_id": None,
        "scope_type": "industry",
        "scope_id": "industry-1",
        "source_ref": "report:industry-shared-1",
    }
    industry_chunks = knowledge.list_chunks(document_id="memory:industry:industry-1", limit=None)
    work_context_chunks = knowledge.list_chunks(document_id="memory:work_context:industry-1", limit=None)
    assert len(industry_chunks) == 1
    assert work_context_chunks == []
    assert industry_chunks[0].document_id == "memory:industry:industry-1"


def test_memory_retain_service_compacts_duplicate_shared_writebacks_into_one_text_anchor(tmp_path) -> None:
    _store, knowledge, _strategy, retain, _recall, _reflection, _derived = _build_memory_services(tmp_path)

    retain.retain_chat_writeback(
        industry_instance_id="industry-1",
        title="Shared operating note",
        content="Evidence review stays mandatory before outbound approval.",
        source_ref="chat:thread-1:msg-1",
        tags=["shared-memory", "report-outcome"],
    )
    retain.retain_chat_writeback(
        industry_instance_id="industry-1",
        title="Shared operating note",
        content="Evidence review stays mandatory before outbound approval.",
        source_ref="chat:thread-1:msg-2",
        tags=["shared-memory", "report-outcome"],
    )

    industry_chunks = knowledge.list_chunks(document_id="memory:industry:industry-1", limit=None)
    assert len(industry_chunks) == 1
    assert industry_chunks[0].title == "Shared operating note"
    assert industry_chunks[0].content == "Evidence review stays mandatory before outbound approval."


def test_memory_retain_service_merges_repeated_report_findings_without_dropping_source_truth(tmp_path) -> None:
    _store, knowledge, _strategy, retain, _recall, _reflection, derived = _build_memory_services(tmp_path)

    report_one = AgentReportRecord(
        id="report-merge-1",
        industry_instance_id="industry-1",
        work_context_id="ctx-merge",
        owner_agent_id="worker-1",
        owner_role_id="researcher",
        headline="Weekly review completed",
        summary="Hold outbound until evidence is updated.",
        status="recorded",
        result="completed",
        evidence_ids=["evidence-1"],
    )
    report_two = AgentReportRecord(
        id="report-merge-2",
        industry_instance_id="industry-1",
        work_context_id="ctx-merge",
        owner_agent_id="worker-1",
        owner_role_id="researcher",
        headline="Weekly review completed",
        summary="Hold outbound until evidence review is fully updated.",
        status="recorded",
        result="completed",
        evidence_ids=["evidence-2"],
    )

    retain.retain_agent_report(report_one)
    retain.retain_agent_report(report_two)

    work_context_chunks = knowledge.list_chunks(document_id="memory:work_context:ctx-merge", limit=None)
    fact_entries = derived.list_fact_entries(source_type="agent_report", limit=None)
    assert len(work_context_chunks) == 1
    assert "evidence review is fully updated" in work_context_chunks[0].content
    assert {item.source_ref for item in fact_entries} == {"report-merge-1", "report-merge-2"}


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
