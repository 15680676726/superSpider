# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.goals import GoalService
from copaw.kernel import KernelQueryExecutionService
from copaw.memory.models import MemoryRecallHit, MemoryRecallResponse
from copaw.state import GoalRecord, SQLiteStateStore
from copaw.state.repositories import SqliteGoalRepository


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
