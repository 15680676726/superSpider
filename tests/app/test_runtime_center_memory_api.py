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
    MemorySleepInferenceService,
    MemorySleepService,
)
from copaw.state import SQLiteStateStore, StrategyMemoryRecord
from copaw.state.models_goals_tasks import AgentReportRecord
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.models_memory import MemoryRelationViewRecord
from copaw.state.repositories import (
    SqliteKnowledgeChunkRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteMemoryRelationViewRepository,
    SqliteMemorySleepRepository,
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
    app.state.memory_sleep_service = MemorySleepService(
        repository=SqliteMemorySleepRepository(store),
        knowledge_service=knowledge,
        strategy_memory_service=strategy,
        derived_index_service=derived,
        reflection_service=reflection,
        inference_service=MemorySleepInferenceService(),
    )
    knowledge.set_memory_sleep_service(app.state.memory_sleep_service)
    strategy.set_memory_sleep_service(app.state.memory_sleep_service)
    app.state.memory_retain_service.set_memory_sleep_service(app.state.memory_sleep_service)
    app.state.memory_recall_service.set_memory_sleep_service(app.state.memory_sleep_service)
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


def test_runtime_center_memory_recall_route_uses_related_scope_fallback_chain(tmp_path) -> None:
    client = _build_client(tmp_path)

    context_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Control-thread note",
            "content": "This work context is focused on partner follow-up sequencing.",
            "scope_type": "work_context",
            "scope_id": "ctx-industry-control",
            "role_bindings": ["execution-core"],
            "tags": ["control-thread"],
        },
    )
    assert context_response.status_code == 200

    industry_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Industry fallback note",
            "content": "Only approve outbound after evidence review completes.",
            "scope_type": "industry",
            "scope_id": "industry-1",
            "role_bindings": ["execution-core"],
            "tags": ["policy"],
        },
    )
    assert industry_response.status_code == 200

    recall_response = client.get(
        "/runtime-center/memory/recall",
        params={
            "query": "approve outbound after evidence review",
            "work_context_id": "ctx-industry-control",
            "industry_instance_id": "industry-1",
            "role": "execution-core",
            "limit": 5,
        },
    )
    assert recall_response.status_code == 200
    payload = recall_response.json()
    assert payload["hits"]
    assert payload["hits"][0]["scope_type"] == "work_context"
    assert payload["hits"][0]["title"] == "Shared Memory Profile"
    assert any(
        item["scope_type"] == "industry" and item["title"] == "Industry fallback note"
        for item in payload["hits"]
    )


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
    assert payload["activated_count"] >= 1
    assert payload["top_constraints"] == ["Only approve outbound after evidence review."]
    assert "activated_neurons" not in payload


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


def test_runtime_center_memory_rebuild_route_also_rebuilds_relation_views(tmp_path) -> None:
    client = _build_client(tmp_path)

    remember_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Approval rule",
            "content": "Outbound approval must wait for finance evidence review.",
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "source_ref": "memory:ctx-1:approval-rule",
            "role_bindings": ["execution-core"],
            "tags": ["approval", "finance"],
        },
    )
    assert remember_response.status_code == 200

    reflect_response = client.post(
        "/runtime-center/memory/reflect",
        json={
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "trigger_kind": "manual",
            "create_learning_proposals": False,
        },
    )
    assert reflect_response.status_code == 200

    seeded_relations = client.app.state.derived_memory_index_service.rebuild_relation_views(
        scope_type="work_context",
        scope_id="ctx-1",
    )
    assert seeded_relations

    client.app.state.memory_relation_view_repository.clear(
        scope_type="work_context",
        scope_id="ctx-1",
    )
    assert (
        client.app.state.memory_relation_view_repository.list_views(
            scope_type="work_context",
            scope_id="ctx-1",
            limit=None,
        )
        == []
    )

    rebuild_response = client.post(
        "/runtime-center/memory/rebuild",
        json={
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "include_reporting": False,
            "include_learning": False,
            "evidence_limit": 0,
        },
    )

    assert rebuild_response.status_code == 200
    payload = rebuild_response.json()
    assert payload["fact_index_count"] >= 1
    assert payload["relation_view_count"] >= 1
    assert payload["metadata"]["relation_rebuilt"] is True

    relation_response = client.get(
        "/runtime-center/memory/relations",
        params={"work_context_id": "ctx-1"},
    )
    assert relation_response.status_code == 200
    relation_payload = relation_response.json()
    assert relation_payload
    assert any(item["relation_kind"] in {"mentions", "supports"} for item in relation_payload)


def test_runtime_center_memory_surface_route_returns_activation_and_relations(tmp_path) -> None:
    client = _build_client(tmp_path)
    _upsert_industry_strategy(client)

    remember_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Outbound blocker",
            "content": "Outbound approval is blocked until finance evidence review is complete.",
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "source_ref": "memory:ctx-1:blocker",
            "role_bindings": ["execution-core"],
            "tags": ["approval", "finance"],
        },
    )
    assert remember_response.status_code == 200
    run_response = client.post(
        "/runtime-center/memory/sleep/run",
        json={
            "scope_type": "work_context",
            "scope_id": "ctx-1",
            "trigger_kind": "manual",
        },
    )
    assert run_response.status_code == 200

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
        "/runtime-center/memory/surface",
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
    assert payload["query"] == "outbound approval blocked"
    assert payload["activation"]["activated_count"] >= 1
    assert payload["activation"]["top_constraints"] == ["Only approve outbound after evidence review."]
    assert "activated_neurons" not in payload["activation"]
    assert payload["sleep"]["digest"]["headline"]
    assert payload["sleep"]["soft_rules"]
    assert payload["relation_count"] == 1
    assert payload["relation_kind_counts"] == {"supports": 1}
    assert payload["relations"][0]["relation_id"] == "rel:ctx-1:approval->finance"


def test_runtime_center_memory_sleep_routes_expose_scopes_jobs_and_artifacts(tmp_path) -> None:
    client = _build_client(tmp_path)

    remember_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Finance evidence review",
            "content": "Outbound approval must wait for finance review.",
            "scope_type": "work_context",
            "scope_id": "ctx-sleep-api",
            "source_ref": "memory:ctx-sleep-api:1",
            "tags": ["approval"],
        },
    )
    assert remember_response.status_code == 200

    scopes_response = client.get(
        "/runtime-center/memory/sleep/scopes",
        params={"dirty_only": "true"},
    )
    assert scopes_response.status_code == 200
    assert any(item["scope_id"] == "ctx-sleep-api" for item in scopes_response.json())

    run_response = client.post(
        "/runtime-center/memory/sleep/run",
        json={
            "scope_type": "work_context",
            "scope_id": "ctx-sleep-api",
            "trigger_kind": "manual",
        },
    )
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "completed"

    jobs_response = client.get(
        "/runtime-center/memory/sleep/jobs",
        params={"scope_type": "work_context", "scope_id": "ctx-sleep-api"},
    )
    digests_response = client.get(
        "/runtime-center/memory/sleep/digests",
        params={"scope_type": "work_context", "scope_id": "ctx-sleep-api"},
    )
    rules_response = client.get(
        "/runtime-center/memory/sleep/rules",
        params={"scope_type": "work_context", "scope_id": "ctx-sleep-api"},
    )
    conflicts_response = client.get(
        "/runtime-center/memory/sleep/conflicts",
        params={"scope_type": "work_context", "scope_id": "ctx-sleep-api"},
    )

    assert jobs_response.status_code == 200
    assert digests_response.status_code == 200
    assert rules_response.status_code == 200
    assert conflicts_response.status_code == 200
    assert jobs_response.json()[0]["status"] == "completed"
    assert digests_response.json()[0]["status"] == "active"
    assert rules_response.json()


def test_runtime_center_memory_surface_filters_internal_noise_from_entities_and_relation_summaries(tmp_path) -> None:
    client = _build_client(tmp_path)

    for item in (
        {
            "title": "Outbound approval gate",
            "content": "Outbound approval must wait for finance evidence review before any message is sent.",
            "scope_type": "work_context",
            "scope_id": "ctx-memory-smoke",
            "source_ref": "fact:2",
            "tags": ["shared-memory"],
        },
        {
            "title": "Finance evidence gate",
            "content": "Finance queue owns the evidence review gate and only clears approval after evidence is verified.",
            "scope_type": "work_context",
            "scope_id": "ctx-memory-smoke",
            "source_ref": "fact:3",
            "tags": ["shared-memory"],
        },
    ):
        remember_response = client.post("/runtime-center/knowledge/memory", json=item)
        assert remember_response.status_code == 200

    reflect_response = client.post(
        "/runtime-center/memory/reflect",
        json={
            "scope_type": "work_context",
            "scope_id": "ctx-memory-smoke",
            "trigger_kind": "manual",
            "create_learning_proposals": False,
        },
    )
    assert reflect_response.status_code == 200

    rebuild_response = client.post(
        "/runtime-center/memory/rebuild",
        json={
            "scope_type": "work_context",
            "scope_id": "ctx-memory-smoke",
            "include_reporting": False,
            "include_learning": False,
            "evidence_limit": 0,
        },
    )
    assert rebuild_response.status_code == 200

    entities_response = client.get(
        "/runtime-center/memory/entities",
        params={"scope_type": "work_context", "scope_id": "ctx-memory-smoke"},
    )
    relations_response = client.get(
        "/runtime-center/memory/relations",
        params={"scope_type": "work_context", "scope_id": "ctx-memory-smoke"},
    )
    surface_response = client.get(
        "/runtime-center/memory/surface",
        params={
            "scope_type": "work_context",
            "scope_id": "ctx-memory-smoke",
            "query": "finance evidence review outbound approval",
        },
    )

    assert entities_response.status_code == 200
    assert relations_response.status_code == 200
    assert surface_response.status_code == 200

    entity_payload = entities_response.json()
    entity_keys = {item["entity_key"] for item in entity_payload}
    entity_order = [item["entity_key"] for item in entity_payload]
    assert {"approval", "finance"} <= entity_keys
    assert "ctx-memory-smoke" not in entity_keys
    assert "memory" not in entity_keys
    assert "fact" not in entity_keys
    assert "2" not in entity_keys
    assert "owns" not in entity_keys
    assert set(entity_order[:3]) == {"approval", "finance", "outbound"}
    assert entity_order.index("approval") < entity_order.index("gate")
    assert entity_order.index("finance") < entity_order.index("review")

    relation_payload = relations_response.json()
    assert relation_payload
    assert all(":requirement:must" not in item["summary"].lower() for item in relation_payload)
    assert all(":requirement:only" not in item["summary"].lower() for item in relation_payload)
    assert all(" mentions 2" not in item["summary"].lower() for item in relation_payload)
    assert all(" mentions owns" not in item["summary"].lower() for item in relation_payload)
    support_summaries = [
        item["summary"].strip().lower()
        for item in relation_payload
        if str(item.get("relation_kind") or "").strip().lower() == "supports"
    ]
    assert len(support_summaries) == len(set(support_summaries))

    surface_payload = surface_response.json()
    assert surface_payload["relation_count"] >= 1
    assert surface_payload["relation_count"] < len(relation_payload)
    assert surface_payload["relation_count"] <= 6
    assert all(":requirement:must" not in item["summary"].lower() for item in surface_payload["relations"])
    assert all(":requirement:only" not in item["summary"].lower() for item in surface_payload["relations"])
    assert surface_payload["relations"][0]["relation_kind"] in {"supports", "contradicts", "depends_on"}
    assert "supports outbound requires" not in surface_payload["relations"][0]["summary"].lower()
    assert all(
        not item["summary"].lower().startswith("finance requires approval supports")
        for item in surface_payload["relations"]
    )


def test_runtime_center_memory_surface_supports_chinese_memory_summaries(tmp_path) -> None:
    client = _build_client(tmp_path)

    for item in (
        {
            "title": "外呼审批规则",
            "content": "外呼审批必须先完成财务证据复核，确认后才能发送客户消息。",
            "scope_type": "work_context",
            "scope_id": "ctx-cn-memory",
            "source_ref": "fact:cn:1",
            "tags": ["共享记忆"],
        },
        {
            "title": "财务复核说明",
            "content": "财务证据复核完成后，外呼审批才能继续。",
            "scope_type": "work_context",
            "scope_id": "ctx-cn-memory",
            "source_ref": "fact:cn:2",
            "tags": ["共享记忆"],
        },
    ):
        remember_response = client.post("/runtime-center/knowledge/memory", json=item)
        assert remember_response.status_code == 200

    assert client.post(
        "/runtime-center/memory/reflect",
        json={
            "scope_type": "work_context",
            "scope_id": "ctx-cn-memory",
            "trigger_kind": "manual",
            "create_learning_proposals": False,
        },
    ).status_code == 200
    assert client.post(
        "/runtime-center/memory/rebuild",
        json={
            "scope_type": "work_context",
            "scope_id": "ctx-cn-memory",
            "include_reporting": False,
            "include_learning": False,
            "evidence_limit": 0,
        },
    ).status_code == 200

    entities_response = client.get(
        "/runtime-center/memory/entities",
        params={"scope_type": "work_context", "scope_id": "ctx-cn-memory"},
    )
    relations_response = client.get(
        "/runtime-center/memory/relations",
        params={"scope_type": "work_context", "scope_id": "ctx-cn-memory"},
    )
    surface_response = client.get(
        "/runtime-center/memory/surface",
        params={
            "scope_type": "work_context",
            "scope_id": "ctx-cn-memory",
            "query": "外呼审批 财务证据复核",
        },
    )

    assert entities_response.status_code == 200
    assert relations_response.status_code == 200
    assert surface_response.status_code == 200
    entity_payload = entities_response.json()
    entity_keys = {item["entity_key"] for item in entity_payload}
    entity_order = [item["entity_key"] for item in entity_payload]
    assert "外呼审批" in entity_keys
    assert "财务证据复核" in entity_keys
    assert "共享记忆" not in entity_keys
    assert "cn" not in entity_keys
    assert set(entity_order[:2]) == {"外呼审批", "财务证据复核"}
    assert entity_order[-1] == "财务复核说明"
    assert entity_order.index("外呼审批") < entity_order.index("客户消息")

    relation_payload = relations_response.json()
    support_summaries = [
        item["summary"]
        for item in relation_payload
        if str(item.get("relation_kind") or "").strip().lower() == "supports"
    ]
    assert len(support_summaries) == len(set(support_summaries))
    assert any(summary == "外呼审批需要财务证据复核" for summary in support_summaries)
    assert all("客户消息" not in summary for summary in support_summaries)
    assert all("共享记忆" not in summary for summary in support_summaries)
    assert all("支持外呼审批" not in summary for summary in support_summaries)
    assert all("支持财务证据复核" not in summary for summary in support_summaries)

    surface_payload = surface_response.json()
    assert surface_payload["relation_count"] >= 1
    assert any(item["summary"] == "外呼审批需要财务证据复核" for item in surface_payload["relations"])
    assert any("支持" in item["summary"] or "需要" in item["summary"] for item in surface_payload["relations"])


def test_runtime_center_memory_surface_exposes_industry_strategy_relations(tmp_path) -> None:
    client = _build_client(tmp_path)
    _upsert_industry_strategy(client, industry_instance_id="industry-full")

    remember_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Industry outbound blocker",
            "content": "Outbound approval stays blocked until evidence review clears the queue.",
            "scope_type": "industry",
            "scope_id": "industry-full",
            "source_ref": "memory:industry-full:blocker",
            "tags": ["outbound", "industry"],
        },
    )
    assert remember_response.status_code == 200

    reflect_response = client.post(
        "/runtime-center/memory/reflect",
        json={
            "scope_type": "industry",
            "scope_id": "industry-full",
            "trigger_kind": "manual",
            "create_learning_proposals": False,
        },
    )
    assert reflect_response.status_code == 200
    assert reflect_response.json()["opinion_count"] >= 1

    rebuild_response = client.post(
        "/runtime-center/memory/rebuild",
        json={
            "scope_type": "industry",
            "scope_id": "industry-full",
            "include_reporting": False,
            "include_learning": False,
            "evidence_limit": 0,
        },
    )
    assert rebuild_response.status_code == 200

    relations_response = client.get(
        "/runtime-center/memory/relations",
        params={"scope_type": "industry", "scope_id": "industry-full"},
    )
    surface_response = client.get(
        "/runtime-center/memory/surface",
        params={
            "scope_type": "industry",
            "scope_id": "industry-full",
            "query": "outbound approval blockers",
        },
    )

    assert relations_response.status_code == 200
    assert surface_response.status_code == 200

    relation_payload = relations_response.json()
    assert relation_payload
    assert any(
        str(item.get("relation_kind") or "").strip().lower() in {"supports", "contradicts"}
        for item in relation_payload
    )

    surface_payload = surface_response.json()
    assert surface_payload["relation_count"] >= 1
    assert surface_payload["relations"]
    assert any(
        str(item.get("relation_kind") or "").strip().lower() in {"supports", "contradicts"}
        for item in surface_payload["relations"]
    )


def test_runtime_center_memory_entities_filter_strategy_and_report_noise(tmp_path) -> None:
    client = _build_client(tmp_path)
    _upsert_industry_strategy(client, industry_instance_id="industry-noise")

    remember_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Industry outbound blocker",
            "content": "Keep outbound blocked until evidence review clears the execution lane.",
            "scope_type": "industry",
            "scope_id": "industry-noise",
            "source_ref": "memory:industry-noise:blocker",
            "tags": ["outbound", "industry"],
        },
    )
    assert remember_response.status_code == 200

    client.app.state.memory_retain_service.retain_agent_report(
        AgentReportRecord(
            id="report-noise-1",
            industry_instance_id="industry-noise",
            owner_agent_id="worker-1",
            owner_role_id="researcher",
            headline="Night review completed",
            summary="Night review recommends holding outbound until finance evidence is refreshed.",
            status="recorded",
            result="completed",
            evidence_ids=["evidence-1"],
        ),
    )

    assert client.post(
        "/runtime-center/memory/reflect",
        json={
            "scope_type": "industry",
            "scope_id": "industry-noise",
            "trigger_kind": "manual",
            "create_learning_proposals": False,
        },
    ).status_code == 200
    assert client.post(
        "/runtime-center/memory/rebuild",
        json={
            "scope_type": "industry",
            "scope_id": "industry-noise",
            "include_reporting": False,
            "include_learning": False,
            "evidence_limit": 0,
        },
    ).status_code == 200

    entities_response = client.get(
        "/runtime-center/memory/entities",
        params={"scope_type": "industry", "scope_id": "industry-noise"},
    )
    relations_response = client.get(
        "/runtime-center/memory/relations",
        params={"scope_type": "industry", "scope_id": "industry-noise"},
    )

    assert entities_response.status_code == 200
    assert relations_response.status_code == 200
    entity_keys = [item["entity_key"] for item in entities_response.json()]
    assert "outbound" in entity_keys
    assert entity_keys[0] == "outbound"
    assert "main-brain" not in entity_keys
    assert "resolve-outbound-approval-blockers-with-evidence" not in entity_keys
    assert "discipline" not in entity_keys
    assert "protect" not in entity_keys
    assert "operator" not in entity_keys
    assert "quality" not in entity_keys
    assert "refreshed" not in entity_keys
    assert "resolve" not in entity_keys
    assert "approve" not in entity_keys
    assert "blocker" not in entity_keys
    assert "blockers" not in entity_keys
    assert "keep" not in entity_keys
    assert "until" not in entity_keys
    assert "action" not in entity_keys
    assert "execution" not in entity_keys
    assert "researcher" not in entity_keys

    relation_summaries = [str(item["summary"]).lower() for item in relations_response.json()]
    assert all("mentions discipline" not in item for item in relation_summaries)
    assert all("mentions protect" not in item for item in relation_summaries)
    assert all("mentions operator" not in item for item in relation_summaries)
    assert all("mentions quality" not in item for item in relation_summaries)
    assert all("mentions refreshed" not in item for item in relation_summaries)
    assert all("mentions resolve" not in item for item in relation_summaries)
    assert all("mentions approve" not in item for item in relation_summaries)
    assert all("mentions blocker" not in item for item in relation_summaries)
    assert all("mentions blockers" not in item for item in relation_summaries)
    assert all("approve review" not in item for item in relation_summaries)


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
    assert payload["activation"]["activated_count"] >= 1
    assert payload["activation"]["top_constraints"] == ["Only approve outbound after evidence review."]
    assert "activated_neurons" not in payload["activation"]


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
    assert "activated_neurons" not in payload[0]["activation"]
