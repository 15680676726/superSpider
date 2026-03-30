# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.memory import (
    DerivedMemoryIndexService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
)
from copaw.state import SQLiteStateStore
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.repositories import (
    SqliteKnowledgeChunkRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteStrategyMemoryRepository,
)
from copaw.state.strategy_memory_service import StateStrategyMemoryService


def _build_client(tmp_path) -> TestClient:
    app = FastAPI()
    store = SQLiteStateStore(tmp_path / "state.db")
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
    strategy = StateStrategyMemoryService(
        repository=strategy_repo,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    app.state.knowledge_service = knowledge
    app.state.strategy_memory_service = strategy
    app.state.derived_memory_index_service = derived
    app.state.memory_recall_service = MemoryRecallService(
        derived_index_service=derived,
    )
    app.state.memory_reflection_service = reflection
    app.state.memory_retain_service = MemoryRetainService(
        knowledge_service=knowledge,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    app.include_router(runtime_center_router)
    return TestClient(app)


def test_runtime_center_memory_api_rebuild_recall_and_reflect(tmp_path) -> None:
    client = _build_client(tmp_path)

    remember_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Outbound approval rule",
            "content": "The team should only approve outbound messaging after evidence review.",
            "scope_type": "industry",
            "scope_id": "industry-1",
            "role_bindings": ["execution-core"],
            "tags": ["policy", "outbound"],
        },
    )
    assert remember_response.status_code == 200

    backends_response = client.get("/runtime-center/memory/backends")
    assert backends_response.status_code == 404

    rebuild_response = client.post(
        "/runtime-center/memory/rebuild",
        json={
            "scope_type": "industry",
            "scope_id": "industry-1",
            "include_reporting": False,
            "include_learning": False,
            "evidence_limit": 0,
        },
    )
    assert rebuild_response.status_code == 200
    assert rebuild_response.json()["fact_index_count"] >= 1

    recall_response = client.get(
        "/runtime-center/memory/recall",
        params={
            "query": "approve outbound after evidence review",
            "scope_type": "industry",
            "scope_id": "industry-1",
            "role": "execution-core",
            "limit": 5,
        },
    )
    assert recall_response.status_code == 200
    recall_payload = recall_response.json()
    assert recall_payload["hits"]
    assert recall_payload["hits"][0]["source_type"] == "memory_profile"
    assert any(item["source_type"] == "knowledge_chunk" for item in recall_payload["hits"])

    profiles_response = client.get(
        "/runtime-center/memory/profiles",
        params={"scope_type": "industry", "scope_id": "industry-1"},
    )
    assert profiles_response.status_code == 200
    profiles_payload = profiles_response.json()
    assert profiles_payload
    assert profiles_payload[0]["scope_type"] == "industry"
    assert profiles_payload[0]["scope_id"] == "industry-1"
    assert "dynamic_profile" in profiles_payload[0]

    profile_detail_response = client.get(
        "/runtime-center/memory/profiles/industry/industry-1",
    )
    assert profile_detail_response.status_code == 200
    profile_detail_payload = profile_detail_response.json()
    assert profile_detail_payload["scope_type"] == "industry"
    assert profile_detail_payload["scope_id"] == "industry-1"
    assert "current_operating_context" in profile_detail_payload

    episodes_response = client.get(
        "/runtime-center/memory/episodes",
        params={"scope_type": "industry", "scope_id": "industry-1"},
    )
    assert episodes_response.status_code == 200
    episodes_payload = episodes_response.json()
    assert episodes_payload
    assert episodes_payload[0]["scope_type"] == "industry"
    assert episodes_payload[0]["scope_id"] == "industry-1"
    assert episodes_payload[0]["entry_refs"]

    history_response = client.get(
        "/runtime-center/memory/history",
        params={"scope_type": "industry", "scope_id": "industry-1"},
    )
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload
    assert history_payload[0]["scope_type"] == "industry"
    assert history_payload[0]["scope_id"] == "industry-1"
    assert history_payload[0]["source_type"] == "knowledge_chunk"

    reflect_response = client.post(
        "/runtime-center/memory/reflect",
        json={
            "scope_type": "industry",
            "scope_id": "industry-1",
            "trigger_kind": "manual",
            "create_learning_proposals": False,
        },
    )
    assert reflect_response.status_code == 200
    reflect_payload = reflect_response.json()
    assert reflect_payload["entity_count"] >= 1
    assert reflect_payload["opinion_count"] >= 1

    entities_response = client.get(
        "/runtime-center/memory/entities",
        params={"scope_type": "industry", "scope_id": "industry-1"},
    )
    assert entities_response.status_code == 200
    assert entities_response.json()

    opinions_response = client.get(
        "/runtime-center/memory/opinions",
        params={"scope_type": "industry", "scope_id": "industry-1"},
    )
    assert opinions_response.status_code == 200
    assert opinions_response.json()

    runs_response = client.get(
        "/runtime-center/memory/reflections",
        params={"scope_type": "industry", "scope_id": "industry-1"},
    )
    assert runs_response.status_code == 200
    assert runs_response.json()


def test_runtime_center_memory_recall_accepts_work_context_selector(tmp_path) -> None:
    client = _build_client(tmp_path)

    industry_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Industry note",
            "content": "browser publish checklist browser publish checklist browser publish checklist",
            "scope_type": "industry",
            "scope_id": "industry-1",
            "role_bindings": ["execution-core"],
            "tags": ["browser", "industry"],
        },
    )
    assert industry_response.status_code == 200

    remember_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Control-thread note",
            "content": "Escalate browser publish only after the governed checklist is complete.",
            "scope_type": "work_context",
            "scope_id": "ctx-industry-control",
            "role_bindings": ["execution-core"],
            "tags": ["browser", "control-thread"],
        },
    )
    assert remember_response.status_code == 200

    recall_response = client.get(
        "/runtime-center/memory/recall",
        params={
            "query": "browser publish checklist",
            "work_context_id": "ctx-industry-control",
            "role": "execution-core",
            "limit": 5,
        },
    )
    assert recall_response.status_code == 200
    payload = recall_response.json()
    assert payload["hits"]
    assert payload["hits"][0]["scope_type"] == "work_context"
    assert payload["hits"][0]["scope_id"] == "ctx-industry-control"
    assert payload["hits"][0]["title"] == "Shared Memory Profile"
    assert any(item["title"] == "Control-thread note" for item in payload["hits"])
