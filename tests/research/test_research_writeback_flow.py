# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.memory import DerivedMemoryIndexService, MemoryReflectionService
from copaw.memory.knowledge_writeback_service import KnowledgeWritebackService
from copaw.state import ResearchSessionRecord, ResearchSessionRoundRecord, SQLiteStateStore
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.repositories import (
    SqliteKnowledgeChunkRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteMemoryRelationViewRepository,
)


def _build_research_writeback_services(tmp_path):
    store = SQLiteStateStore(tmp_path / "research-writeback.sqlite3")
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
        knowledge_repository=knowledge_repo,
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
    writeback = KnowledgeWritebackService(
        knowledge_service=knowledge,
        derived_index_service=derived,
        relation_view_repository=relation_repo,
        reflection_service=reflection,
    )
    return knowledge, writeback, derived


def _research_session() -> ResearchSessionRecord:
    return ResearchSessionRecord(
        id="research-session-1",
        provider="baidu-page",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        owner_agent_id="industry-researcher-demo",
        supervisor_agent_id="main-brain",
        trigger_source="user-direct",
        goal="Map the ecommerce onboarding operating model",
        stable_findings=[
            "Verified finding: start from reusable onboarding stages.",
        ],
        brief={
            "question": "What should the first operator playbook include?",
            "why_needed": "Need a reusable onboarding baseline.",
            "done_when": "We have a reusable first-pass operator playbook.",
        },
    )


def _research_round() -> ResearchSessionRoundRecord:
    return ResearchSessionRoundRecord(
        id="research-session-1:round:1",
        session_id="research-session-1",
        round_index=1,
        question="What are the key onboarding steps?",
        new_findings=[
            "Working finding: pricing alignment should happen before outbound launch.",
        ],
        evidence_ids=["evidence-1"],
        sources=[
            {
                "source_id": "source-1",
                "source_kind": "link",
                "collection_action": "read",
                "source_ref": "https://example.com/guide",
                "normalized_ref": "https://example.com/guide",
                "title": "Example onboarding guide",
                "snippet": "A reusable onboarding checklist.",
                "evidence_id": "evidence-1",
            },
        ],
    )


def test_state_knowledge_service_ingests_research_session_summary_with_sources(tmp_path) -> None:
    knowledge, _writeback, _derived = _build_research_writeback_services(tmp_path)

    result = knowledge.ingest_research_session(
        session=_research_session(),
        rounds=[_research_round()],
    )

    work_context_chunks = knowledge.list_chunks(
        document_id="memory:work_context:ctx-1",
        limit=None,
    )
    industry_chunks = knowledge.list_chunks(
        document_id="memory:industry:industry-1",
        limit=None,
    )

    assert result["work_context_chunk_ids"]
    assert result["industry_document_id"] == "memory:industry:industry-1"
    assert len(work_context_chunks) == 1
    assert "Verified finding" in work_context_chunks[0].content
    assert "Example onboarding guide" in work_context_chunks[0].content
    assert "https://example.com/guide" in work_context_chunks[0].content
    assert len(industry_chunks) == 1


def test_knowledge_writeback_service_projects_research_findings_and_sources(tmp_path) -> None:
    _knowledge, writeback, derived = _build_research_writeback_services(tmp_path)

    change = writeback.build_research_session_writeback(
        session=_research_session(),
        rounds=[_research_round()],
    )
    summary = writeback.summarize_change(change)
    writeback.apply_change(change)

    assert change.scope.scope_type == "work_context"
    assert change.scope.scope_id == "ctx-1"
    assert {"event", "fact", "opinion", "evidence"} <= set(summary["node_types"])
    assert {"belongs_to", "produces", "derived_from"} <= set(summary["relation_types"])

    fact_entries = derived.list_fact_entries(
        scope_type="work_context",
        scope_id="ctx-1",
        limit=None,
        include_inactive=True,
    )
    relation_views = derived.list_relation_views(
        scope_type="work_context",
        scope_id="ctx-1",
        limit=None,
        include_inactive=True,
    )

    assert any(
        entry.id == "research-session:research-session-1"
        and (entry.metadata or {}).get("knowledge_graph_node_type") == "event"
        for entry in fact_entries
    )
    assert any(
        entry.id.startswith("research-finding:research-session-1:")
        and (entry.metadata or {}).get("knowledge_graph_node_type") == "fact"
        for entry in fact_entries
    )
    assert any(view.relation_kind == "derived_from" for view in relation_views)
