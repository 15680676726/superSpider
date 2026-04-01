# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.memory import (
    DerivedMemoryIndexService,
    MemoryActivationService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
)
from copaw.state import SQLiteStateStore, StrategyMemoryRecord
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.models_memory import MemoryRelationViewRecord
from copaw.state.repositories import (
    SqliteKnowledgeChunkRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteMemoryRelationViewRepository,
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
    app.state.memory_activation_service = MemoryActivationService(
        derived_index_service=derived,
        strategy_memory_service=strategy,
    )
    app.state.memory_relation_view_repository = relation_repo
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
    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    assert "/runtime-center/memory/backends" not in openapi_response.json()["paths"]

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


def _upsert_industry_strategy(client: TestClient, *, industry_instance_id: str = "industry-1") -> None:
    client.app.state.strategy_memory_service.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id=f"strategy:industry:{industry_instance_id}:main-brain",
            scope_type="industry",
            scope_id=industry_instance_id,
            owner_agent_id="main-brain",
            industry_instance_id=industry_instance_id,
            title="Outbound evidence discipline",
            summary="Keep outbound execution blocked until evidence clears the action.",
            mission="Protect operator execution quality.",
            execution_constraints=["Only approve outbound after evidence review."],
            current_focuses=["Resolve outbound approval blockers with evidence."],
        ),
    )


def test_runtime_center_memory_activation_route_returns_activation_result(tmp_path) -> None:
    client = _build_client(tmp_path)
    _upsert_industry_strategy(client)

    remember_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Outbound approval blocked",
            "content": "Outbound approval is blocked until evidence review is complete.",
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "source_ref": "memory:ctx-1:approval",
            "role_bindings": ["execution-core"],
            "tags": ["outbound", "approval"],
        },
    )
    assert remember_response.status_code == 200

    response = client.get(
        "/runtime-center/memory/activation",
        params={
            "query": "outbound approval blocked",
            "work_context_id": "ctx-1",
            "industry_instance_id": "industry-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["activated_neurons"]
    assert payload["top_constraints"] == ["Only approve outbound after evidence review."]


def test_runtime_center_memory_activation_route_preserves_scope_priority(tmp_path) -> None:
    client = _build_client(tmp_path)

    industry_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Industry approval note",
            "content": "Industry scope tracks outbound approval review.",
            "scope_type": "industry",
            "scope_id": "industry-1",
            "source_ref": "memory:industry-1:approval",
            "role_bindings": ["execution-core"],
            "tags": ["industry"],
        },
    )
    assert industry_response.status_code == 200

    context_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Context approval blocker",
            "content": "This work context is blocked on outbound approval.",
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "source_ref": "memory:ctx-1:blocker",
            "role_bindings": ["execution-core"],
            "tags": ["work-context"],
        },
    )
    assert context_response.status_code == 200

    response = client.get(
        "/runtime-center/memory/activation",
        params={
            "query": "outbound approval blocked",
            "work_context_id": "ctx-1",
            "industry_instance_id": "industry-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope_type"] == "work_context"
    assert payload["scope_id"] == "ctx-1"


def test_runtime_center_memory_relations_route_lists_relation_views(tmp_path) -> None:
    client = _build_client(tmp_path)

    client.app.state.memory_relation_view_repository.upsert_view(
        MemoryRelationViewRecord(
            relation_id="rel:ctx-1:approval->finance",
            source_node_id="fact:approval",
            target_node_id="entity:finance-queue",
            relation_kind="supports",
            scope_type="work_context",
            scope_id="ctx-1",
            owner_agent_id="execution-core",
            industry_instance_id="industry-1",
            summary="Outbound approval supports finance queue review.",
            confidence=0.91,
            source_refs=["fact:approval"],
            metadata={"reason": "queue ownership"},
        ),
    )

    response = client.get(
        "/runtime-center/memory/relations",
        params={"scope_type": "work_context", "scope_id": "ctx-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert payload[0]["relation_id"] == "rel:ctx-1:approval->finance"
    assert payload[0]["relation_kind"] == "supports"
    assert payload[0]["metadata"] == {"reason": "queue ownership"}


def test_runtime_center_memory_relations_route_filters_by_relation_fields(tmp_path) -> None:
    client = _build_client(tmp_path)

    repository = client.app.state.memory_relation_view_repository
    repository.upsert_view(
        MemoryRelationViewRecord(
            relation_id="rel:ctx-1:approval->finance",
            source_node_id="fact:approval",
            target_node_id="entity:finance-queue",
            relation_kind="supports",
            scope_type="work_context",
            scope_id="ctx-1",
            summary="Approval supports finance queue review.",
            source_refs=["fact:approval"],
        ),
    )
    repository.upsert_view(
        MemoryRelationViewRecord(
            relation_id="rel:ctx-1:approval->legal",
            source_node_id="fact:approval",
            target_node_id="entity:legal-queue",
            relation_kind="mentions",
            scope_type="work_context",
            scope_id="ctx-1",
            summary="Approval mentions legal queue review.",
            source_refs=["fact:approval"],
        ),
    )

    response = client.get(
        "/runtime-center/memory/relations",
        params={
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "relation_kind": "supports",
            "target_node_id": "entity:finance-queue",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["relation_id"] == "rel:ctx-1:approval->finance"
    assert payload[0]["relation_kind"] == "supports"
    assert payload[0]["target_node_id"] == "entity:finance-queue"


def test_runtime_center_memory_relations_route_accepts_scope_selectors(tmp_path) -> None:
    client = _build_client(tmp_path)

    repository = client.app.state.memory_relation_view_repository
    repository.upsert_view(
        MemoryRelationViewRecord(
            relation_id="rel:ctx-1:approval->finance",
            source_node_id="fact:approval",
            target_node_id="entity:finance-queue",
            relation_kind="supports",
            scope_type="work_context",
            scope_id="ctx-1",
            summary="Approval supports finance queue review.",
            source_refs=["fact:approval"],
        ),
    )
    repository.upsert_view(
        MemoryRelationViewRecord(
            relation_id="rel:ctx-2:approval->legal",
            source_node_id="fact:approval",
            target_node_id="entity:legal-queue",
            relation_kind="supports",
            scope_type="work_context",
            scope_id="ctx-2",
            summary="Approval supports legal queue review.",
            source_refs=["fact:approval"],
        ),
    )

    response = client.get(
        "/runtime-center/memory/relations",
        params={"work_context_id": "ctx-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["relation_id"] == "rel:ctx-1:approval->finance"
    assert payload[0]["scope_type"] == "work_context"
    assert payload[0]["scope_id"] == "ctx-1"


def test_runtime_center_memory_relations_route_degrades_when_repository_missing(tmp_path) -> None:
    client = _build_client(tmp_path)

    client.app.state.memory_relation_view_repository = None
    client.app.state.derived_memory_index_service._relation_view_repository = None

    response = client.get(
        "/runtime-center/memory/relations",
        params={"scope_type": "work_context", "scope_id": "ctx-1"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_runtime_center_memory_profile_includes_activation_summary_when_requested(tmp_path) -> None:
    client = _build_client(tmp_path)
    _upsert_industry_strategy(client)

    remember_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Industry outbound blocker",
            "content": "Outbound approval stays blocked until the evidence pass completes.",
            "scope_type": "industry",
            "scope_id": "industry-1",
            "source_ref": "memory:industry-1:blocker",
            "role_bindings": ["execution-core"],
            "tags": ["outbound", "industry"],
        },
    )
    assert remember_response.status_code == 200

    response = client.get(
        "/runtime-center/memory/profiles/industry/industry-1",
        params={"include_activation": True, "query": "outbound approval blocked"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["activation"]["activated_neurons"]
    assert payload["activation"]["top_constraints"] == ["Only approve outbound after evidence review."]


def test_runtime_center_memory_episodes_can_include_activation_refs(tmp_path) -> None:
    client = _build_client(tmp_path)

    remember_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Control-thread blocker",
            "content": "Escalate outbound approval only after the evidence review is complete.",
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "source_ref": "work-context:ctx-1:approval",
            "role_bindings": ["execution-core"],
            "tags": ["outbound", "approval"],
        },
    )
    assert remember_response.status_code == 200

    response = client.get(
        "/runtime-center/memory/episodes",
        params={
            "work_context_id": "ctx-1",
            "include_activation": True,
            "query": "outbound approval blocked",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert payload[0]["activation"]["support_refs"]
