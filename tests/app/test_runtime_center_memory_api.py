# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.memory import (
    DerivedMemoryIndexService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
    QmdBackendConfig,
    QmdRecallBackend,
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


class _FakeQmdRunner:
    def __call__(self, args, **kwargs):
        return subprocess.CompletedProcess(
            args=list(args),
            returncode=0,
            stdout="[]",
            stderr="",
        )


def _build_qmd_backend(tmp_path) -> QmdRecallBackend:
    base_dir = tmp_path / "qmd-sidecar"
    return QmdRecallBackend(
        config=QmdBackendConfig(
            enabled=True,
            install_mode="path",
            binary_name="qmd",
            base_dir=base_dir,
            corpus_dir=base_dir / "corpus",
            manifest_path=base_dir / "manifest.json",
            xdg_cache_home=base_dir / "xdg-cache",
        ),
        runner=_FakeQmdRunner(),
        which=lambda _name: "qmd",
    )


def _build_client(tmp_path, *, qmd_backend: QmdRecallBackend | None = None) -> TestClient:
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
        sidecar_backends=[qmd_backend] if qmd_backend is not None else None,
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
        sidecar_backends=[qmd_backend] if qmd_backend is not None else None,
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
    assert backends_response.status_code == 200
    backends = backends_response.json()
    assert any(item["backend_id"] == "hybrid-local" for item in backends)

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
    assert recall_payload["hits"][0]["source_type"] == "knowledge_chunk"

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


def test_runtime_center_memory_backends_include_qmd_metadata(tmp_path) -> None:
    client = _build_client(tmp_path, qmd_backend=_build_qmd_backend(tmp_path))

    response = client.get("/runtime-center/memory/backends")
    assert response.status_code == 200
    payload = response.json()
    qmd = next(item for item in payload if item["backend_id"] == "qmd")
    assert qmd["available"] is True
    assert qmd["metadata"]["install_mode"] == "path"
    assert qmd["metadata"]["query_mode"] in {"query", "search", "vsearch"}
    assert "Qwen3-Embedding-0.6B" in qmd["metadata"]["embed_model"]
    assert qmd["metadata"]["ready"] is False
    assert "runtime_problem" in qmd["metadata"]
    assert qmd["metadata"]["daemon_state"] == "disabled"
