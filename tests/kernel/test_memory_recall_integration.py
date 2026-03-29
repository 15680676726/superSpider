# -*- coding: utf-8 -*-
from __future__ import annotations

import base64

import pytest

from copaw.goals import GoalService
from copaw.kernel import KernelQueryExecutionService
from copaw.media import MediaAnalysisRequest, MediaService, MediaSourceSpec
from copaw.memory import (
    DerivedMemoryIndexService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
)
from copaw.memory.models import MemoryRecallHit, MemoryRecallResponse
from copaw.state import GoalRecord, SQLiteStateStore
from copaw.evidence import EvidenceLedger
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.repositories import (
    SqliteGoalRepository,
    SqliteKnowledgeChunkRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteMediaAnalysisRepository,
    SqliteStrategyMemoryRepository,
)


class _FakeMemoryRecallService:
    def recall(self, **kwargs):
        _ = kwargs
        return MemoryRecallResponse(
            query="evidence review",
            backend_used="hybrid-local",
            hits=[
                MemoryRecallHit(
                    entry_id="memory-index:knowledge_chunk:chunk-1",
                    kind="knowledge_chunk",
                    title="Outbound rule",
                    summary="Only approve outbound after evidence review.",
                    content_excerpt="Only approve outbound after evidence review.",
                    source_type="knowledge_chunk",
                    source_ref="chunk-1",
                    scope_type="industry",
                    scope_id="industry-1",
                    confidence=0.9,
                    quality_score=0.8,
                    score=1.0,
                )
            ],
        )


class _CapturingMemoryRecallService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def recall(self, **kwargs):
        self.calls.append(dict(kwargs))
        hits = []
        if kwargs.get("scope_type") == "work_context":
            hits = [
                MemoryRecallHit(
                    entry_id="memory-index:knowledge_chunk:chunk-2",
                    kind="knowledge_chunk",
                    title="Work context note",
                    summary="This note belongs to the shared work context.",
                    content_excerpt="This note belongs to the shared work context.",
                    source_type="knowledge_chunk",
                    source_ref="chunk-2",
                    scope_type="work_context",
                    scope_id="ctx-media-ops",
                    confidence=0.95,
                    quality_score=0.9,
                    score=1.0,
                )
            ]
        return MemoryRecallResponse(
            query=str(kwargs.get("query") or ""),
            backend_used="hybrid-local",
            hits=hits,
        )


def test_goal_service_compiler_uses_memory_recall_hits() -> None:
    store = SQLiteStateStore(":memory:")
    service = GoalService(
        repository=SqliteGoalRepository(store),
        memory_recall_service=_FakeMemoryRecallService(),
    )
    goal = GoalRecord(
        title="Plan outbound",
        summary="Prepare the outbound playbook.",
        status="active",
    )

    context = service._build_knowledge_context(
        goal=goal,
        context={
            "industry_instance_id": "industry-1",
            "industry_role_id": "execution-core",
            "steps": ["Check evidence", "Then send outbound"],
        },
    )

    assert context["memory_items"]
    assert "Outbound rule" in context["memory_items"][0]
    assert context["memory_refs"] == ["chunk-1"]


def test_query_execution_prompt_uses_memory_recall_hits() -> None:
    service = KernelQueryExecutionService(
        session_backend=object(),
        memory_recall_service=_FakeMemoryRecallService(),
    )

    lines = service._build_retrieved_knowledge_lines(
        msgs=["Please check evidence review before outbound approval"],
        owner_agent_id="copaw-agent-runner",
        industry_instance_id="industry-1",
        industry_role_id="execution-core",
        owner_scope="runtime",
    )

    assert any("Long-Term Memory" in line for line in lines)
    assert any("Outbound rule" in line for line in lines)


def test_query_execution_prompt_prefers_work_context_memory_recall_hits() -> None:
    recall_service = _CapturingMemoryRecallService()
    service = KernelQueryExecutionService(
        session_backend=object(),
        memory_recall_service=recall_service,
    )

    lines = service._build_retrieved_knowledge_lines(
        msgs=["Please check the work context note before outbound approval"],
        owner_agent_id="copaw-agent-runner",
        industry_instance_id="industry-1",
        industry_role_id="execution-core",
        owner_scope="runtime",
        task_id="task-1",
        work_context_id="ctx-media-ops",
    )

    assert recall_service.calls
    call = recall_service.calls[0]
    assert call["scope_type"] == "work_context"
    assert call["scope_id"] == "ctx-media-ops"
    assert call["include_related_scopes"] is False
    assert any("Work context note" in line for line in lines)


def test_retain_chat_writeback_creates_work_context_scoped_recall_hit(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "memory.sqlite3")
    store.initialize()
    knowledge_repo = SqliteKnowledgeChunkRepository(store)
    strategy_repo = SqliteStrategyMemoryRepository(store)
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
    retain = MemoryRetainService(
        knowledge_service=knowledge,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    recall = MemoryRecallService(derived_index_service=derived)

    result = retain.retain_chat_writeback(
        industry_instance_id="industry-1",
        work_context_id="ctx-media-ops",
        title="Media follow-up note",
        content="Prefer the shared work context when recalling media follow-up details.",
        source_ref="media-analysis:media-1",
        tags=["media-analysis", "follow-up"],
    )

    assert result["work_context_id"] == "ctx-media-ops"
    assert result["scope_type"] == "work_context"
    assert result["scope_id"] == "ctx-media-ops"

    hits = recall.recall(
        query="shared work context media follow-up details",
        work_context_id="ctx-media-ops",
        role="execution-core",
        include_related_scopes=False,
    ).hits

    assert hits
    assert hits[0].scope_type == "work_context"
    assert hits[0].scope_id == "ctx-media-ops"
    assert hits[0].source_ref == "media-analysis:media-1"
    assert hits[0].metadata["source_ref"] == "media-analysis:media-1"


def test_retain_chat_writeback_isolates_same_source_ref_across_work_contexts(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "memory.sqlite3")
    store.initialize()
    knowledge_repo = SqliteKnowledgeChunkRepository(store)
    strategy_repo = SqliteStrategyMemoryRepository(store)
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
    retain = MemoryRetainService(
        knowledge_service=knowledge,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    recall = MemoryRecallService(derived_index_service=derived)

    retain.retain_chat_writeback(
        industry_instance_id="industry-1",
        work_context_id="ctx-a",
        title="Follow-up A",
        content="Follow-up chain A stays in context A.",
        source_ref="media-analysis:shared-source",
        tags=["follow-up"],
    )
    retain.retain_chat_writeback(
        industry_instance_id="industry-1",
        work_context_id="ctx-b",
        title="Follow-up B",
        content="Follow-up chain B stays in context B.",
        source_ref="media-analysis:shared-source",
        tags=["follow-up"],
    )

    chunks_a = knowledge.list_chunks(document_id="memory:work_context:ctx-a", limit=None)
    chunks_b = knowledge.list_chunks(document_id="memory:work_context:ctx-b", limit=None)
    assert len(chunks_a) == 1
    assert len(chunks_b) == 1
    assert "context A" in chunks_a[0].content
    assert "context B" in chunks_b[0].content

    hits_a = recall.recall(
        query="follow-up chain context A",
        work_context_id="ctx-a",
        include_related_scopes=False,
        limit=3,
    ).hits
    hits_b = recall.recall(
        query="follow-up chain context B",
        work_context_id="ctx-b",
        include_related_scopes=False,
        limit=3,
    ).hits
    assert hits_a and hits_b
    assert hits_a[0].scope_type == "work_context"
    assert hits_a[0].scope_id == "ctx-a"
    assert hits_b[0].scope_type == "work_context"
    assert hits_b[0].scope_id == "ctx-b"


@pytest.mark.asyncio
async def test_media_analysis_followup_updates_existing_analysis_work_context(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    store.initialize()
    media_repository = SqliteMediaAnalysisRepository(store)
    service = MediaService(
        repository=media_repository,
        evidence_ledger=EvidenceLedger(tmp_path / "evidence.sqlite3"),
    )
    payload = base64.b64encode(
        b"Follow-up continuity notes for media analysis context binding."
    ).decode("ascii")
    source = MediaSourceSpec(
        source_id="media-src:shared",
        source_kind="upload",
        title="Shared media note",
        filename="shared.txt",
        mime_type="text/plain",
        upload_base64=payload,
    )

    first = await service.analyze(
        MediaAnalysisRequest(
            sources=[source],
            industry_instance_id="industry-1",
            thread_id="thread-initial",
            entry_point="chat",
            purpose="chat-answer",
            writeback=False,
        ),
    )
    assert first.analyses and first.analyses[0].work_context_id is None

    second = await service.analyze(
        MediaAnalysisRequest(
            sources=[source],
            industry_instance_id="industry-1",
            thread_id="thread-followup",
            work_context_id="ctx-followup-media",
            entry_point="chat",
            purpose="chat-answer",
            writeback=False,
        ),
    )
    assert second.analyses
    assert second.analyses[0].work_context_id == "ctx-followup-media"
    assert second.analyses[0].thread_id == "thread-followup"
