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
from copaw.state import (
    IndustryMemoryProfileRecord,
    IndustryMemorySlotPreferenceRecord,
    MemoryContinuityDetailRecord,
    MemoryStructureProposalRecord,
    SQLiteStateStore,
    StrategyMemoryRecord,
)
from copaw.state.models_goals_tasks import AgentReportRecord
from copaw.state.models_memory import MemoryRelationViewRecord
from copaw.state.knowledge_service import StateKnowledgeService
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


def test_runtime_center_memory_sleep_routes_expose_profiles_overlays_and_structure_proposals(tmp_path) -> None:
    client = _build_client(tmp_path)

    industry_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "行业长期规则",
            "content": "行业当前要求所有外呼审批都必须先完成财务复核。",
            "scope_type": "industry",
            "scope_id": "industry-1",
            "source_ref": "memory:industry-1:1",
            "tags": ["approval", "finance"],
        },
    )
    assert industry_response.status_code == 200
    run_industry_response = client.post(
        "/runtime-center/memory/sleep/run",
        json={
            "scope_type": "industry",
            "scope_id": "industry-1",
            "trigger_kind": "manual",
        },
    )
    assert run_industry_response.status_code == 200

    work_context_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "工作上下文焦点",
            "content": "当前工作上下文正在收口财务复核和外呼审批之间的先后顺序。",
            "scope_type": "work_context",
            "scope_id": "ctx-structured-memory",
            "source_ref": "memory:ctx-structured-memory:1",
            "tags": ["approval", "finance"],
        },
    )
    assert work_context_response.status_code == 200
    client.app.state.memory_sleep_service.mark_scope_dirty(
        scope_type="work_context",
        scope_id="ctx-structured-memory",
        industry_instance_id="industry-1",
        reason="bind-industry",
        source_ref="memory:ctx-structured-memory:1",
    )
    run_work_context_response = client.post(
        "/runtime-center/memory/sleep/run",
        json={
            "scope_type": "work_context",
            "scope_id": "ctx-structured-memory",
            "trigger_kind": "manual",
        },
    )
    assert run_work_context_response.status_code == 200

    profiles_response = client.get(
        "/runtime-center/memory/sleep/industry-profiles",
        params={"industry_instance_id": "industry-1"},
    )
    overlays_response = client.get(
        "/runtime-center/memory/sleep/work-context-overlays",
        params={"work_context_id": "ctx-structured-memory"},
    )
    proposals_response = client.get(
        "/runtime-center/memory/sleep/structure-proposals",
        params={"scope_type": "work_context", "scope_id": "ctx-structured-memory"},
    )
    surface_response = client.get(
        "/runtime-center/memory/surface",
        params={"work_context_id": "ctx-structured-memory", "industry_instance_id": "industry-1"},
    )

    assert profiles_response.status_code == 200
    assert overlays_response.status_code == 200
    assert proposals_response.status_code == 200
    assert surface_response.status_code == 200
    assert profiles_response.json()[0]["industry_instance_id"] == "industry-1"
    assert overlays_response.json()[0]["work_context_id"] == "ctx-structured-memory"
    assert proposals_response.json()[0]["candidate_overlay_id"] == overlays_response.json()[0]["overlay_id"]
    sleep_payload = surface_response.json()["sleep"]
    assert sleep_payload["industry_profile"]["industry_instance_id"] == "industry-1"
    assert sleep_payload["work_context_overlay"]["work_context_id"] == "ctx-structured-memory"
    assert sleep_payload["structure_proposals"]


def test_runtime_center_memory_surface_work_context_resolves_industry_profile_without_manual_scope_binding(
    tmp_path,
) -> None:
    client = _build_client(tmp_path)

    industry_id = "industry-surface-auto-bind"
    work_context_id = "ctx-surface-auto-bind"

    industry_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Industry outbound rule",
            "content": "Outbound approval must wait for finance review before any message is sent.",
            "scope_type": "industry",
            "scope_id": industry_id,
            "source_ref": f"memory:{industry_id}:1",
            "tags": ["approval", "finance"],
        },
    )
    assert industry_response.status_code == 200
    assert client.post(
        "/runtime-center/memory/sleep/run",
        json={"scope_type": "industry", "scope_id": industry_id, "trigger_kind": "manual"},
    ).status_code == 200

    work_context_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Work context blocker",
            "content": "Wait for finance review before outbound approval.",
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "source_ref": f"industry:{industry_id}",
            "tags": ["approval", "finance"],
        },
    )
    assert work_context_response.status_code == 200
    assert client.post(
        "/runtime-center/memory/sleep/run",
        json={"scope_type": "work_context", "scope_id": work_context_id, "trigger_kind": "manual"},
    ).status_code == 200

    surface_response = client.get(
        "/runtime-center/memory/surface",
        params={"work_context_id": work_context_id, "industry_instance_id": industry_id},
    )

    assert surface_response.status_code == 200
    sleep_payload = surface_response.json()["sleep"]
    assert sleep_payload["work_context_overlay"]["industry_instance_id"] == industry_id
    assert sleep_payload["industry_profile"]["industry_instance_id"] == industry_id


def test_runtime_center_memory_sleep_governance_and_version_routes(tmp_path) -> None:
    client = _build_client(tmp_path)

    assert client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "行业规则 v1",
            "content": "行业要求所有外呼审批都必须先完成财务复核。",
            "scope_type": "industry",
            "scope_id": "industry-versioned",
            "source_ref": "memory:industry-versioned:1",
            "tags": ["approval", "finance"],
        },
    ).status_code == 200
    assert client.post(
        "/runtime-center/memory/sleep/run",
        json={"scope_type": "industry", "scope_id": "industry-versioned", "trigger_kind": "manual"},
    ).status_code == 200
    assert client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "行业规则 v2",
            "content": "行业当前要求先完成财务复核，再做外呼审批和证据归档。",
            "scope_type": "industry",
            "scope_id": "industry-versioned",
            "source_ref": "memory:industry-versioned:2",
            "tags": ["approval", "finance"],
        },
    ).status_code == 200
    assert client.post(
        "/runtime-center/memory/sleep/run",
        json={"scope_type": "industry", "scope_id": "industry-versioned", "trigger_kind": "manual"},
    ).status_code == 200

    assert client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "工作上下文 v1",
            "content": "当前工作上下文正在处理财务复核和外呼审批。",
            "scope_type": "work_context",
            "scope_id": "ctx-versioned-memory",
            "source_ref": "memory:ctx-versioned-memory:1",
            "tags": ["approval", "finance"],
        },
    ).status_code == 200
    client.app.state.memory_sleep_service.mark_scope_dirty(
        scope_type="work_context",
        scope_id="ctx-versioned-memory",
        industry_instance_id="industry-versioned",
        reason="bind-industry",
        source_ref="memory:ctx-versioned-memory:1",
    )
    assert client.post(
        "/runtime-center/memory/sleep/run",
        json={"scope_type": "work_context", "scope_id": "ctx-versioned-memory", "trigger_kind": "manual"},
    ).status_code == 200
    assert client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "工作上下文 v2",
            "content": "当前工作上下文要求先补齐财务证据，再继续外呼审批。",
            "scope_type": "work_context",
            "scope_id": "ctx-versioned-memory",
            "source_ref": "memory:ctx-versioned-memory:2",
            "tags": ["approval", "finance"],
        },
    ).status_code == 200
    client.app.state.memory_sleep_service.mark_scope_dirty(
        scope_type="work_context",
        scope_id="ctx-versioned-memory",
        industry_instance_id="industry-versioned",
        reason="update-work-context",
        source_ref="memory:ctx-versioned-memory:2",
    )
    assert client.post(
        "/runtime-center/memory/sleep/run",
        json={"scope_type": "work_context", "scope_id": "ctx-versioned-memory", "trigger_kind": "manual"},
    ).status_code == 200

    proposals_response = client.get(
        "/runtime-center/memory/sleep/structure-proposals",
        params={"scope_type": "work_context", "scope_id": "ctx-versioned-memory", "status": "pending"},
    )
    assert proposals_response.status_code == 200
    proposal_id = proposals_response.json()[0]["proposal_id"]

    reject_response = client.post(
        f"/runtime-center/memory/sleep/structure-proposals/{proposal_id}/reject",
        json={"actor": "tester", "note": "这次不接受结构改动。"},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"

    overlay_diff_response = client.get(
        "/runtime-center/memory/sleep/work-context-overlays/ctx-versioned-memory/diff",
        params={"from_version": 1, "to_version": 2},
    )
    assert overlay_diff_response.status_code == 200
    assert overlay_diff_response.json()["changes"]

    industry_diff_response = client.get(
        "/runtime-center/memory/sleep/industry-profiles/industry-versioned/diff",
        params={"from_version": 1, "to_version": 2},
    )
    assert industry_diff_response.status_code == 200
    assert industry_diff_response.json()["changes"]

    rollback_overlay_response = client.post(
        "/runtime-center/memory/sleep/work-context-overlays/ctx-versioned-memory/rollback",
        json={"version": 1, "actor": "tester"},
    )
    assert rollback_overlay_response.status_code == 200
    assert rollback_overlay_response.json()["status"] == "active"
    assert rollback_overlay_response.json()["version"] >= 3

    rollback_industry_response = client.post(
        "/runtime-center/memory/sleep/industry-profiles/industry-versioned/rollback",
        json={"version": 1, "actor": "tester"},
    )
    assert rollback_industry_response.status_code == 200
    assert rollback_industry_response.json()["status"] == "active"
    assert rollback_industry_response.json()["version"] >= 3

    rebuild_response = client.post(
        "/runtime-center/memory/sleep/rebuild",
        json={"scope_type": "work_context", "scope_id": "ctx-versioned-memory", "trigger_kind": "rebuild"},
    )
    assert rebuild_response.status_code == 200
    rebuild_payload = rebuild_response.json()
    assert rebuild_payload["sleep_job"]["status"] == "completed"
    assert rebuild_payload["sleep_job"]["trigger_kind"] == "manual"
    assert rebuild_payload["sleep_job"]["metadata"]["requested_trigger_kind"] == "rebuild"
    assert rebuild_payload["work_context_overlay"]["work_context_id"] == "ctx-versioned-memory"


def test_runtime_center_memory_surface_exposes_structure_truth_after_industry_proposal_apply(
    tmp_path,
) -> None:
    client = _build_client(tmp_path)
    repository = client.app.state.memory_sleep_service._repository

    first_profile = repository.upsert_industry_profile(
        IndustryMemoryProfileRecord(
            profile_id="industry-profile:industry-surface-apply:v1",
            industry_instance_id="industry-surface-apply",
            headline="Initial profile",
            summary="Original industry direction",
            strategic_direction="second direction",
            active_constraints=["second constraint", "first constraint"],
            active_focuses=["second direction", "first direction"],
            key_entities=["entity-a"],
            key_relations=["second relation", "first relation"],
            version=1,
            status="active",
            metadata={"source": "test"},
        )
    )
    repository.upsert_slot_preference(
        IndustryMemorySlotPreferenceRecord(
            preference_id="pref:industry-surface-apply:first-direction",
            industry_instance_id="industry-surface-apply",
            slot_key="first_direction",
            slot_label="First Direction",
            scope_level="industry",
            scope_id="industry-surface-apply",
            status="active",
            promotion_count=3,
        )
    )
    repository.upsert_continuity_detail(
        MemoryContinuityDetailRecord(
            detail_id="detail:industry:industry-surface-apply:guardrail",
            scope_type="industry",
            scope_id="industry-surface-apply",
            detail_key="guardrail",
            detail_text="Never drop the first-direction continuity guardrail.",
            source_kind="manual",
            status="active",
            pinned=True,
        )
    )
    proposal = repository.upsert_structure_proposal(
        MemoryStructureProposalRecord(
            proposal_id="structure:industry:industry-surface-apply:manual",
            scope_type="industry",
            scope_id="industry-surface-apply",
            industry_instance_id="industry-surface-apply",
            proposal_kind="read-order-optimization",
            title="Promote first direction",
            summary="Move first direction ahead of second direction.",
            recommended_action="Make first direction the primary industry focus.",
            candidate_profile_id=first_profile.profile_id,
            risk_level="medium",
            status="pending",
        )
    )

    apply_response = client.post(
        f"/runtime-center/memory/sleep/structure-proposals/{proposal.proposal_id}/apply",
        json={"actor": "tester"},
    )

    assert apply_response.status_code == 200
    assert apply_response.json()["status"] == "accepted"

    surface_response = client.get(
        "/runtime-center/memory/surface",
        params={"scope_type": "industry", "scope_id": "industry-surface-apply"},
    )

    assert surface_response.status_code == 200
    sleep_payload = surface_response.json()["sleep"]
    assert sleep_payload["industry_profile"]["profile_id"] != first_profile.profile_id
    assert sleep_payload["industry_profile"]["version"] == 2
    assert sleep_payload["industry_profile"]["active_focuses"][0] == "first direction"
    assert sleep_payload["industry_profile"]["metadata"]["last_applied_proposal_id"] == proposal.proposal_id
    assert sleep_payload["slot_preferences"][0]["slot_key"] == "first_direction"
    assert sleep_payload["continuity_details"][0]["detail_key"] == "guardrail"


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


def test_runtime_center_memory_pin_continuity_detail_enters_formal_memory_truth(tmp_path) -> None:
    client = _build_client(tmp_path)

    pin_response = client.post(
        "/runtime-center/memory/continuity-details/pin",
        json={
            "scope_type": "work_context",
            "scope_id": "ctx-pin-1",
            "industry_instance_id": "industry-pin-1",
            "work_context_id": "ctx-pin-1",
            "detail_key": "risk-boundary",
            "detail_text": "Do not average down after stop-loss.",
            "pinned_until_phase": "week-1",
        },
    )

    assert pin_response.status_code == 200
    payload = pin_response.json()
    assert payload["detail_key"] == "risk-boundary"
    assert payload["pinned"] is True
    assert payload["source_kind"] == "manual"

    surface_response = client.get(
        "/runtime-center/memory/surface",
        params={"scope_type": "work_context", "scope_id": "ctx-pin-1"},
    )

    assert surface_response.status_code == 200
    details = surface_response.json()["sleep"]["continuity_details"]
    assert details
    assert details[0]["detail_key"] == "risk-boundary"
    assert details[0]["pinned"] is True


def test_runtime_center_memory_sleep_keeps_core_continuity_ahead_of_new_noise(tmp_path) -> None:
    client = _build_client(tmp_path)

    industry_id = "industry-story-memory"
    work_context_id = "ctx-story-memory"
    client.app.state.strategy_memory_service.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id=f"strategy:industry:{industry_id}:main-brain",
            scope_type="industry",
            scope_id=industry_id,
            owner_agent_id="main-brain",
            industry_instance_id=industry_id,
            title="Story continuity baseline",
            summary="Protect story continuity before style chatter.",
            execution_constraints=[
                "Do not break the ring truth or the old pier timeline.",
            ],
            current_focuses=[
                "Keep the main continuity anchors stable.",
            ],
        )
    )
    assert client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Story continuity baseline",
            "content": "The industry baseline keeps ring truth, old pier timeline, and role identity stable.",
            "scope_type": "industry",
            "scope_id": industry_id,
            "source_ref": f"industry:{industry_id}",
            "tags": ["story", "continuity"],
        },
    ).status_code == 200
    assert client.post(
        "/runtime-center/memory/sleep/run",
        json={
            "scope_type": "industry",
            "scope_id": industry_id,
            "trigger_kind": "manual",
        },
    ).status_code == 200

    for item in (
        {
            "title": "Ring truth",
            "content": "Lin Xia must not learn the ring truth before chapter twelve.",
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "source_ref": f"memory:{work_context_id}:ring-truth",
            "tags": ["story", "continuity"],
        },
        {
            "title": "Old pier timeline",
            "content": "The old pier remains the agreed handoff scene after the storm.",
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "source_ref": f"memory:{work_context_id}:old-pier",
            "tags": ["story", "continuity"],
        },
    ):
        assert client.post("/runtime-center/knowledge/memory", json=item).status_code == 200

    client.app.state.memory_sleep_service.mark_scope_dirty(
        scope_type="work_context",
        scope_id=work_context_id,
        industry_instance_id=industry_id,
        reason="bind-industry",
        source_ref=f"industry:{industry_id}",
    )
    assert client.post(
        "/runtime-center/memory/continuity-details/pin",
        json={
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "industry_instance_id": industry_id,
            "work_context_id": work_context_id,
            "detail_key": "ring-truth",
            "detail_text": "The ring truth must remain stable until chapter twelve.",
            "pinned_until_phase": "chapter-12",
        },
    ).status_code == 200
    assert client.post(
        "/runtime-center/memory/sleep/run",
        json={
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "trigger_kind": "manual",
        },
    ).status_code == 200

    for index in range(1, 4):
        assert client.post(
            "/runtime-center/knowledge/memory",
            json={
                "title": f"noise-{index}",
                "content": f"Noise {index} is only a casual coffee, lunch, or palette chat.",
                "scope_type": "work_context",
                "scope_id": work_context_id,
                "source_ref": f"memory:{work_context_id}:noise-{index}",
                "tags": ["noise"],
            },
        ).status_code == 200
    assert client.post(
        "/runtime-center/memory/sleep/run",
        json={
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "trigger_kind": "manual",
        },
    ).status_code == 200

    surface_response = client.get(
        "/runtime-center/memory/surface",
        params={
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "query": "ring truth old pier continuity",
        },
    )
    recall_response = client.get(
        "/runtime-center/memory/recall",
        params={
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "query": "ring truth old pier continuity",
            "limit": 5,
        },
    )

    assert surface_response.status_code == 200
    assert recall_response.status_code == 200

    sleep_payload = surface_response.json()["sleep"]
    overlay = sleep_payload["work_context_overlay"]
    recall_payload = recall_response.json()
    top_hit = recall_payload["hits"][0]

    assert not str(overlay["headline"]).startswith("noise-")
    assert not str(overlay["summary"]).startswith("noise-")
    assert not str(overlay["focus_summary"]).startswith("noise-")
    assert "casual coffee" not in str(overlay["headline"]).lower()
    assert "casual coffee" not in str(overlay["summary"]).lower()
    assert "casual coffee" not in str(overlay["focus_summary"]).lower()
    assert any(
        anchor in " ".join(
            [
                str(overlay["headline"]),
                str(overlay["summary"]),
                str(overlay["focus_summary"]),
                *list(overlay.get("active_constraints") or []),
                *list(overlay.get("active_focuses") or []),
            ]
        ).lower()
        for anchor in ("ring truth", "old pier", "continuity")
    )
    assert sleep_payload["continuity_details"]
    assert sleep_payload["continuity_details"][0]["detail_key"] == "ring-truth"
    assert sleep_payload["continuity_details"][0]["pinned"] is True
    assert top_hit["source_type"] == "memory_profile"
    assert not str(top_hit["summary"]).startswith("noise-")
    assert "casual coffee" not in str(top_hit["summary"]).lower()
    assert "casual coffee" not in str(top_hit["content_excerpt"]).lower()
    assert any(
        anchor in str(top_hit["content_excerpt"]).lower()
        for anchor in ("ring truth", "old pier", "continuity")
    )


def test_runtime_center_memory_sleep_rejects_weak_generated_titles_from_main_read_surface(tmp_path) -> None:
    client = _build_client(tmp_path)

    industry_id = "industry-weak-title-memory"
    work_context_id = "ctx-weak-title-memory"
    assert client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "Story continuity baseline",
            "content": "Keep ring truth and role identity stable across chapter transitions.",
            "scope_type": "industry",
            "scope_id": industry_id,
            "source_ref": f"industry:{industry_id}",
            "tags": ["story", "continuity"],
        },
    ).status_code == 200
    assert client.post(
        "/runtime-center/memory/sleep/run",
        json={
            "scope_type": "industry",
            "scope_id": industry_id,
            "trigger_kind": "manual",
        },
    ).status_code == 200
    assert client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "story core round 2",
            "content": "Role identity and ring truth remain the top continuity guardrails.",
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "source_ref": f"industry:{industry_id}",
            "tags": ["story", "continuity"],
        },
    ).status_code == 200
    assert client.post(
        "/runtime-center/memory/continuity-details/pin",
        json={
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "industry_instance_id": industry_id,
            "work_context_id": work_context_id,
            "detail_key": "role-identity",
            "detail_text": "Role identity and ring truth must remain stable.",
            "pinned_until_phase": "chapter-12",
        },
    ).status_code == 200
    assert client.post(
        "/runtime-center/memory/sleep/run",
        json={
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "trigger_kind": "manual",
        },
    ).status_code == 200

    surface_response = client.get(
        "/runtime-center/memory/surface",
        params={
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "query": "ring truth role identity continuity",
        },
    )
    recall_response = client.get(
        "/runtime-center/memory/recall",
        params={
            "scope_type": "work_context",
            "scope_id": work_context_id,
            "query": "ring truth role identity continuity",
            "limit": 5,
        },
    )

    assert surface_response.status_code == 200
    assert recall_response.status_code == 200

    overlay = surface_response.json()["sleep"]["work_context_overlay"]
    top_hit = recall_response.json()["hits"][0]

    assert str(overlay["headline"]).lower() != "story core round 2"
    assert str(overlay["focus_summary"]).lower() != "story core round 2"
    assert "ring truth" in " ".join(
        [
            str(overlay["headline"]),
            str(overlay["summary"]),
            str(overlay["focus_summary"]),
            *list(overlay.get("active_constraints") or []),
            *list(overlay.get("active_focuses") or []),
        ]
    ).lower()
    assert str(top_hit["summary"]).lower() != "story core round 2"
    assert "role identity" in str(top_hit["content_excerpt"]).lower()


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


def test_runtime_center_memory_profile_detail_uses_sleep_overlay_read_layer(tmp_path) -> None:
    client = _build_client(tmp_path)

    industry_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "行业总规则",
            "content": "行业要求所有外呼审批都必须先完成财务复核。",
            "scope_type": "industry",
            "scope_id": "industry-1",
            "source_ref": "memory:industry-1:profile",
            "tags": ["approval", "finance"],
        },
    )
    assert industry_response.status_code == 200
    run_industry_response = client.post(
        "/runtime-center/memory/sleep/run",
        json={
            "scope_type": "industry",
            "scope_id": "industry-1",
            "trigger_kind": "manual",
        },
    )
    assert run_industry_response.status_code == 200

    work_context_response = client.post(
        "/runtime-center/knowledge/memory",
        json={
            "title": "工作上下文焦点",
            "content": "当前工作上下文正在收口财务复核和外呼审批的先后顺序。",
            "scope_type": "work_context",
            "scope_id": "ctx-profile-overlay",
            "source_ref": "memory:ctx-profile-overlay:1",
            "tags": ["approval", "finance"],
        },
    )
    assert work_context_response.status_code == 200
    client.app.state.memory_sleep_service.mark_scope_dirty(
        scope_type="work_context",
        scope_id="ctx-profile-overlay",
        industry_instance_id="industry-1",
        reason="bind-industry",
        source_ref="memory:ctx-profile-overlay:1",
    )
    run_work_context_response = client.post(
        "/runtime-center/memory/sleep/run",
        json={
            "scope_type": "work_context",
            "scope_id": "ctx-profile-overlay",
            "trigger_kind": "manual",
        },
    )
    assert run_work_context_response.status_code == 200

    response = client.get(
        "/runtime-center/memory/profiles/work_context/ctx-profile-overlay",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope_type"] == "work_context"
    assert payload["scope_id"] == "ctx-profile-overlay"
    assert payload["read_layer"] == "work_context_overlay"
    assert str(payload["overlay_id"]).startswith("overlay:")
    assert str(payload["industry_profile_id"]).startswith("industry-profile:")
    assert any("财务复核" in item for item in payload["static_profile"])
    assert any("工作上下文" in item for item in payload["dynamic_profile"])
    assert isinstance(payload["current_operating_context"], list)
    assert payload["current_operating_context"]


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
