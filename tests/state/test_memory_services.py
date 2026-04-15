# -*- coding: utf-8 -*-
from __future__ import annotations

import copaw.memory as memory_module
from copaw.memory import (
    DerivedMemoryIndexService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
    MemorySleepInferenceService,
    MemorySleepService,
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
    SqliteMemoryRelationViewRepository,
    SqliteMemorySleepRepository,
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
    relation_repo = SqliteMemoryRelationViewRepository(store)
    reflection_repo = SqliteMemoryReflectionRunRepository(store)
    derived = DerivedMemoryIndexService(
        fact_index_repository=fact_repo,
        entity_view_repository=entity_repo,
        opinion_view_repository=opinion_repo,
        relation_view_repository=relation_repo,
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
    )
    return store, knowledge, strategy, retain, recall, reflection, derived


def _build_memory_services_with_sleep(tmp_path):
    store, knowledge, strategy, retain, recall, reflection, derived = _build_memory_services(tmp_path)
    sleep = MemorySleepService(
        repository=SqliteMemorySleepRepository(store),
        knowledge_service=knowledge,
        strategy_memory_service=strategy,
        derived_index_service=derived,
        reflection_service=reflection,
        inference_service=MemorySleepInferenceService(),
    )
    knowledge.set_memory_sleep_service(sleep)
    strategy.set_memory_sleep_service(sleep)
    retain.set_memory_sleep_service(sleep)
    recall.set_memory_sleep_service(sleep)
    return store, knowledge, strategy, retain, recall, reflection, derived, sleep


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


def test_memory_reflection_and_relation_rebuild_preserve_industry_scope_identity(tmp_path) -> None:
    _store, knowledge, strategy, _retain, _recall, reflection, derived = _build_memory_services(tmp_path)

    knowledge.remember_fact(
        title="Industry outbound blocker",
        content="Outbound approval stays blocked until evidence review clears the queue.",
        scope_type="industry",
        scope_id="industry-full",
        source_ref="memory:industry-full:blocker",
        tags=["outbound", "industry"],
    )
    strategy.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-full:main-brain",
            scope_type="industry",
            scope_id="industry-full",
            owner_agent_id="main-brain",
            industry_instance_id="industry-full",
            title="Outbound evidence discipline",
            summary="Keep outbound execution blocked until evidence clears the action.",
            mission="Protect operator execution quality.",
            execution_constraints=["Only approve outbound after evidence review."],
            current_focuses=["Resolve outbound approval blockers with evidence."],
        ),
    )

    reflection.reflect(
        scope_type="industry",
        scope_id="industry-full",
        trigger_kind="test",
        create_learning_proposals=False,
    )

    industry_entities = derived.list_entity_views(
        scope_type="industry",
        scope_id="industry-full",
        industry_instance_id="industry-full",
        limit=None,
    )
    industry_opinions = derived.list_opinion_views(
        scope_type="industry",
        scope_id="industry-full",
        industry_instance_id="industry-full",
        limit=None,
    )
    relations = derived.rebuild_relation_views(
        scope_type="industry",
        scope_id="industry-full",
        industry_instance_id="industry-full",
    )

    assert industry_entities
    assert industry_opinions
    assert relations
    assert any(
        str(getattr(item, "relation_kind", "") or "").strip().lower() == "supports"
        for item in relations
    )


def test_memory_reflection_filters_internal_ids_and_low_signal_terms_from_entities_and_relations(tmp_path) -> None:
    _store, knowledge, _strategy, _retain, _recall, reflection, derived = _build_memory_services(tmp_path)

    knowledge.remember_fact(
        title="Outbound approval gate",
        content="Outbound approval must wait for finance evidence review before any message is sent.",
        scope_type="work_context",
        scope_id="ctx-memory-smoke",
        source_ref="fact:2",
        tags=["shared-memory"],
    )
    knowledge.remember_fact(
        title="Finance evidence gate",
        content="Finance queue owns the evidence review gate and only clears approval after evidence is verified.",
        scope_type="work_context",
        scope_id="ctx-memory-smoke",
        source_ref="fact:3",
        tags=["shared-memory"],
    )

    reflection.reflect(
        scope_type="work_context",
        scope_id="ctx-memory-smoke",
        trigger_kind="test",
        create_learning_proposals=False,
    )
    relations = derived.rebuild_relation_views(
        scope_type="work_context",
        scope_id="ctx-memory-smoke",
    )

    entity_keys = {
        item.entity_key
        for item in derived.list_entity_views(
            scope_type="work_context",
            scope_id="ctx-memory-smoke",
        )
    }
    assert {"approval", "finance"} <= entity_keys
    assert "ctx-memory-smoke" not in entity_keys
    assert "memory" not in entity_keys
    assert "fact" not in entity_keys
    assert "2" not in entity_keys
    assert "owns" not in entity_keys
    assert "sent" not in entity_keys

    noisy_relation_keys = {
        str(getattr(item, "metadata", {}).get("entity_key") or "").strip()
        for item in relations
    }
    assert "ctx-memory-smoke" not in noisy_relation_keys
    assert "memory" not in noisy_relation_keys
    assert "fact" not in noisy_relation_keys
    assert "2" not in noisy_relation_keys
    assert "owns" not in noisy_relation_keys
    assert all(" mentions 2" not in item.summary.lower() for item in relations)
    assert all(" mentions owns" not in item.summary.lower() for item in relations)
    assert all(":requirement:must" not in item.summary.lower() for item in relations)
    assert all(":requirement:only" not in item.summary.lower() for item in relations)
    assert any("requires finance review" in item.summary.lower() for item in relations)
    assert any("requires approval" in item.summary.lower() for item in relations)


def test_memory_reflection_supports_chinese_memory_entities_and_relation_summaries(tmp_path) -> None:
    _store, knowledge, _strategy, _retain, _recall, reflection, derived = _build_memory_services(tmp_path)

    knowledge.remember_fact(
        title="外呼审批规则",
        content="外呼审批必须先完成财务证据复核，确认后才能发送客户消息。",
        scope_type="work_context",
        scope_id="ctx-cn-memory",
        source_ref="fact:cn:1",
        tags=["共享记忆"],
    )
    knowledge.remember_fact(
        title="财务复核说明",
        content="财务证据复核完成后，外呼审批才能继续。",
        scope_type="work_context",
        scope_id="ctx-cn-memory",
        source_ref="fact:cn:2",
        tags=["共享记忆"],
    )

    reflection.reflect(
        scope_type="work_context",
        scope_id="ctx-cn-memory",
        trigger_kind="test",
        create_learning_proposals=False,
    )
    relations = derived.rebuild_relation_views(
        scope_type="work_context",
        scope_id="ctx-cn-memory",
    )

    entity_keys = {
        item.entity_key
        for item in derived.list_entity_views(
            scope_type="work_context",
            scope_id="ctx-cn-memory",
        )
    }
    assert "外呼审批" in entity_keys
    assert "财务证据复核" in entity_keys
    assert "共享记忆" not in entity_keys
    assert "cn" not in entity_keys
    support_summaries = [
        item.summary
        for item in relations
        if str(getattr(item, "relation_kind", "") or "").strip().lower() == "supports"
    ]
    assert any(summary == "外呼审批需要财务证据复核" for summary in support_summaries)
    assert all("客户消息" not in summary for summary in support_summaries)
    assert all("共享记忆" not in summary for summary in support_summaries)
    assert all("支持外呼审批" not in summary for summary in support_summaries)
    assert all("支持财务证据复核" not in summary for summary in support_summaries)


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


def test_memory_recall_prefers_sleep_digest_and_expands_alias_terms(tmp_path) -> None:
    _store, knowledge, _strategy, _retain, recall, _reflection, _derived, sleep = _build_memory_services_with_sleep(
        tmp_path,
    )

    knowledge.remember_fact(
        title="Finance evidence review",
        content="Outbound approval must wait for finance review.",
        scope_type="work_context",
        scope_id="ctx-sleep-read",
        source_ref="fact:ctx-sleep-read:1",
        tags=["approval"],
    )
    knowledge.remember_fact(
        title="Finance review checklist",
        content="The team also calls finance evidence review simply finance review.",
        scope_type="work_context",
        scope_id="ctx-sleep-read",
        source_ref="fact:ctx-sleep-read:2",
        tags=["approval"],
    )
    sleep.run_sleep(
        scope_type="work_context",
        scope_id="ctx-sleep-read",
        trigger_kind="manual",
    )

    recalled = recall.recall(
        query="finance review",
        scope_type="work_context",
        scope_id="ctx-sleep-read",
        limit=6,
    )

    assert recalled.hits
    assert recalled.hits[0].source_type == "memory_profile"
    assert any(hit.source_type == "memory_sleep_digest" for hit in recalled.hits)
    assert any(hit.source_type == "memory_soft_rule" for hit in recalled.hits)


def test_memory_recall_profile_uses_work_context_overlay_as_primary_read_layer(tmp_path) -> None:
    _store, knowledge, strategy, _retain, recall, _reflection, _derived, sleep = _build_memory_services_with_sleep(
        tmp_path,
    )

    strategy.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-overlay-1:main-brain",
            scope_type="industry",
            scope_id="industry-overlay-1",
            owner_agent_id="main-brain",
            industry_instance_id="industry-overlay-1",
            title="证据先行",
            summary="外呼审批必须先完成财务复核。",
            execution_constraints=["外呼审批必须先完成财务复核。"],
            current_focuses=["先完成财务复核，再处理审批。"],
        ),
    )
    knowledge.remember_fact(
        title="行业共享规则",
        content="财务复核是行业共享规则。",
        scope_type="industry",
        scope_id="industry-overlay-1",
        source_ref="fact:industry-overlay-1:1",
        tags=["approval", "finance"],
    )
    sleep.run_sleep(scope_type="industry", scope_id="industry-overlay-1", trigger_kind="manual")

    knowledge.remember_fact(
        title="当前工作焦点",
        content="当前工作上下文正在处理财务复核与外呼审批的先后顺序。",
        scope_type="work_context",
        scope_id="ctx-overlay-read",
        source_ref="fact:ctx-overlay-read:1",
        tags=["approval", "finance"],
    )
    sleep.mark_scope_dirty(
        scope_type="work_context",
        scope_id="ctx-overlay-read",
        industry_instance_id="industry-overlay-1",
        reason="bind-industry",
        source_ref="fact:ctx-overlay-read:1",
    )
    sleep.run_sleep(scope_type="work_context", scope_id="ctx-overlay-read", trigger_kind="manual")

    recalled = recall.recall(
        query="财务复核",
        scope_type="work_context",
        scope_id="ctx-overlay-read",
        limit=5,
    )

    assert recalled.hits
    profile_hit = recalled.hits[0]
    assert profile_hit.source_type == "memory_profile"
    assert "财务复核" in profile_hit.summary
    assert profile_hit.metadata["read_layer"] == "work_context_overlay"
    assert str(profile_hit.metadata["overlay_id"]).startswith("overlay:")


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
    )

    assert not hasattr(service, "close_sidecar_backends")
