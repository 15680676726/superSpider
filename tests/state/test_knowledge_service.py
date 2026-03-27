# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.state import SQLiteStateStore
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.repositories import SqliteKnowledgeChunkRepository


def test_knowledge_service_imports_headings_and_retrieves_by_query(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteKnowledgeChunkRepository(store)
    service = StateKnowledgeService(repository=repository)

    result = service.import_document(
        title="Operations SOP",
        content=(
            "# Incident Triage\n"
            "Capture the trigger, scope, and current owner.\n\n"
            "# Rollback\n"
            "Use rollback criteria and evidence checkpoints before resuming."
        ),
        source_ref="workspace:OPS.md",
        role_bindings=["execution-core", "ops-agent"],
        tags=["ops", "incident"],
    )

    assert result["document_id"].startswith("knowledge-doc:")
    assert result["chunk_count"] == 2

    documents = service.list_documents(query="rollback")
    assert len(documents) == 1
    assert documents[0]["chunk_count"] == 2
    assert documents[0]["tags"] == ["ops", "incident"]

    retrieved = service.retrieve(query="rollback evidence", role="ops-agent", limit=2)
    assert len(retrieved) == 1
    assert retrieved[0].title == "Rollback"
    assert "evidence checkpoints" in retrieved[0].content


def test_knowledge_service_updates_and_deletes_chunk(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteKnowledgeChunkRepository(store)
    service = StateKnowledgeService(repository=repository)

    imported = service.import_document(
        title="Workspace notes",
        content="Draft the weekly signal summary and link evidence.",
        source_ref="workspace:NOTES.md",
        role_bindings=["execution-core"],
        tags=["weekly"],
    )
    chunk = imported["chunks"][0]

    updated = service.upsert_chunk(
        chunk_id=str(chunk["id"]),
        document_id=str(chunk["document_id"]),
        title="Workspace notes",
        content="Draft the weekly signal summary, link evidence, and list blockers.",
        source_ref="workspace:NOTES.md",
        chunk_index=int(chunk["chunk_index"]),
        role_bindings=["execution-core", "solution-lead"],
        tags=["weekly", "signals"],
    )
    assert "list blockers" in updated.content
    assert updated.role_bindings == ["execution-core", "solution-lead"]
    assert updated.tags == ["weekly", "signals"]

    assert service.delete_chunk(updated.id) is True
    assert service.get_chunk(updated.id) is None


def test_knowledge_service_persists_memory_by_scope_and_retrieves_it(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteKnowledgeChunkRepository(store)
    service = StateKnowledgeService(repository=repository)

    service.remember_fact(
        title="Execution core preference",
        content="The execution core should prefer weekly rollups over daily noise.",
        scope_type="agent",
        scope_id="execution-core-1",
        role_bindings=["execution-core"],
        tags=["ops"],
    )
    service.remember_fact(
        title="Industry memory",
        content="ACME only allows outbound action after evidence review.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["policy"],
    )
    service.remember_fact(
        title="Task memory",
        content="This task thread should stay isolated from other agent memories.",
        scope_type="task",
        scope_id="task-1",
        role_bindings=["execution-core"],
        tags=["task"],
    )
    service.remember_fact(
        title="Work context memory",
        content="Customer A prefers weekly async check-ins during onboarding.",
        scope_type="work_context",
        scope_id="ctx-customer-a",
        role_bindings=["execution-core"],
        tags=["customer"],
    )

    agent_memory = service.list_memory(
        agent_id="execution-core-1",
        query="weekly rollups",
        role="execution-core",
    )
    assert len(agent_memory) == 1
    assert agent_memory[0].document_id == "memory:agent:execution-core-1"

    industry_memory = service.retrieve_memory(
        query="evidence review",
        industry_instance_id="industry-1",
        role="execution-core",
    )
    assert len(industry_memory) == 1
    assert industry_memory[0].document_id == "memory:industry:industry-1"

    described = service.describe_memory_document(industry_memory[0].document_id)
    assert described == {
        "scope_type": "industry",
        "scope_id": "industry-1",
        "document_id": "memory:industry:industry-1",
    }

    task_memory = service.retrieve_memory(
        query="stay isolated",
        scope_type="task",
        scope_id="task-1",
        task_id="task-1",
        include_related_scopes=False,
        role="execution-core",
    )
    assert len(task_memory) == 1
    assert task_memory[0].document_id == "memory:task:task-1"

    work_context_memory = service.retrieve_memory(
        query="weekly async check-ins",
        scope_type="work_context",
        scope_id="ctx-customer-a",
        work_context_id="ctx-customer-a",
        include_related_scopes=False,
        role="execution-core",
    )
    assert len(work_context_memory) == 1
    assert work_context_memory[0].document_id == "memory:work_context:ctx-customer-a"
