# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.state import SQLiteStateStore
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.repositories import SqliteKnowledgeChunkRepository


def _build_client(tmp_path) -> TestClient:
    app = FastAPI()
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteKnowledgeChunkRepository(store)
    app.state.knowledge_service = StateKnowledgeService(repository=repository)
    app.include_router(runtime_center_router)
    return TestClient(app)


def test_runtime_center_knowledge_import_list_and_retrieve(tmp_path) -> None:
    client = _build_client(tmp_path)

    response = client.post(
        "/runtime-center/knowledge/import",
        json={
            "title": "Signal handbook",
            "content": "# Daily\nCapture the signal.\n\n# Weekly\nSummarize trend shifts.",
            "source_ref": "workspace:SIGNALS.md",
            "role_bindings": ["execution-core"],
            "tags": ["signals", "reports"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["chunk_count"] == 2
    chunk_id = payload["chunks"][0]["id"]
    document_id = payload["document_id"]

    list_response = client.get("/runtime-center/knowledge", params={"document_id": document_id})
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 2
    assert listed[0]["document_id"] == document_id

    retrieve_response = client.get(
        "/runtime-center/knowledge/retrieve",
        params={"query": "trend", "role": "execution-core"},
    )
    assert retrieve_response.status_code == 200
    retrieved = retrieve_response.json()
    assert len(retrieved) == 1
    assert retrieved[0]["title"] == "Weekly"

    detail_response = client.get(f"/runtime-center/knowledge/{chunk_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == chunk_id


def test_runtime_center_knowledge_update_and_delete(tmp_path) -> None:
    client = _build_client(tmp_path)

    imported = client.post(
        "/runtime-center/knowledge/import",
        json={
            "title": "Ops note",
            "content": "Track blockers and evidence.",
        },
    ).json()
    chunk = imported["chunks"][0]

    update_response = client.put(
        f"/runtime-center/knowledge/{chunk['id']}",
        json={
            "document_id": chunk["document_id"],
            "title": chunk["title"],
            "content": "Track blockers, evidence, and rollback checkpoints.",
            "source_ref": chunk["source_ref"],
            "chunk_index": chunk["chunk_index"],
            "role_bindings": ["ops-agent"],
            "tags": ["ops", "rollback"],
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert "rollback checkpoints" in updated["content"]
    assert updated["role_bindings"] == ["ops-agent"]

    documents_response = client.get("/runtime-center/knowledge/documents")
    assert documents_response.status_code == 200
    documents = documents_response.json()
    assert documents[0]["document_id"] == chunk["document_id"]

    delete_response = client.delete(f"/runtime-center/knowledge/{chunk['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    missing_response = client.get(f"/runtime-center/knowledge/{chunk['id']}")
    assert missing_response.status_code == 404


def test_runtime_center_memory_api_supports_write_and_scope_filtering(tmp_path) -> None:
    client = _build_client(tmp_path)

    remembered = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Execution core fact",
            "content": "The customer only approves outbound contact after review.",
            "scope_type": "industry",
            "scope_id": "industry-1",
            "role_bindings": ["execution-core"],
            "tags": ["customer", "policy"],
        },
    )
    assert remembered.status_code == 200
    payload = remembered.json()
    assert payload["document_id"] == "memory:industry:industry-1"
    assert payload["scope_type"] == "industry"
    assert payload["scope_id"] == "industry-1"

    listed = client.get(
        "/runtime-center/knowledge/memory",
        params={
            "industry_instance_id": "industry-1",
            "query": "outbound contact",
            "role": "execution-core",
        },
    )
    assert listed.status_code == 200
    records = listed.json()
    assert len(records) == 1
    assert records[0]["title"] == "Execution core fact"
