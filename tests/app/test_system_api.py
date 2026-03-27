# -*- coding: utf-8 -*-
from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.system import router as system_router
from copaw.memory import MemoryBackendDescriptor
from copaw.providers.provider_manager import ModelSlotConfig
from copaw.state import SQLiteStateStore


class FakeProviderManager:
    def __init__(self) -> None:
        self._active = ModelSlotConfig(provider_id="openai", model="gpt-5")
        self._fallback = [ModelSlotConfig(provider_id="ollama", model="qwen")]

    def get_active_model(self):
        return self._active

    def get_provider(self, provider_id: str):
        if provider_id in {"openai", "ollama"}:
            return SimpleNamespace(id=provider_id)
        return None

    def get_fallback_slots(self):
        return list(self._fallback)


class FakeMemoryRecallService:
    def list_backends(self):
        return [
            MemoryBackendDescriptor(
                backend_id="hybrid-local",
                label="Hybrid Local",
                available=True,
                is_default=True,
            ),
            MemoryBackendDescriptor(
                backend_id="qmd",
                label="QMD Sidecar",
                available=True,
                metadata={
                    "install_mode": "path",
                    "query_mode": "search",
                    "embed_model": "hf:Qwen/Qwen3-Embedding-0.6B-GGUF/Qwen3-Embedding-0.6B-Q8_0.gguf",
                    "ready": True,
                    "dirty": False,
                    "runtime_problem": None,
                    "collection_path_matches": True,
                    "indexed_documents": 217,
                    "pending_embeddings": 0,
                    "daemon_enabled": True,
                    "daemon_state": "running",
                    "daemon_url": "http://127.0.0.1:8765",
                    "daemon_pid": 21648,
                },
            ),
        ]


class FakeMemoryManager:
    def runtime_health_payload(self) -> dict[str, object]:
        return {
            "vector_enabled": False,
            "vector_disable_reason_code": "missing_embedding_model_name",
            "vector_disable_reason": (
                "Vector search disabled. EMBEDDING_API_KEY is configured, "
                "but EMBEDDING_MODEL_NAME is missing and no provider "
                "default could be inferred."
            ),
            "embedding_model_name": "",
            "embedding_model_inferred": False,
            "embedding_base_url": "https://example.com/v1",
            "embedding_api_key_configured": True,
            "embedding_follow_active_provider": True,
            "fts_enabled": True,
            "memory_store_backend": "local",
        }


def build_app(tmp_path: Path) -> FastAPI:
    app = FastAPI()
    app.include_router(system_router)
    app.state.state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    app.state.state_store.initialize()
    app.state.evidence_ledger = object()
    app.state.capability_service = object()
    app.state.kernel_dispatcher = object()
    app.state.runtime_event_bus = object()
    app.state.governance_service = object()
    app.state.cron_manager = object()
    app.state.memory_recall_service = FakeMemoryRecallService()
    app.state.memory_manager = FakeMemoryManager()
    app.state.startup_recovery_summary = {"reason": "startup", "hydrated_tasks": 2}
    app.state.provider_manager = FakeProviderManager()
    return app


def _patch_workspace(monkeypatch, workspace_root: Path) -> None:
    monkeypatch.setattr("copaw.app.routers.workspace.WORKING_DIR", workspace_root)
    monkeypatch.setattr("copaw.app.routers.system.WORKING_DIR", workspace_root)


def test_system_overview_exposes_v3_routes(tmp_path: Path) -> None:
    app = build_app(tmp_path)
    client = TestClient(app)

    response = client.get("/system/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["backup"]["download_route"] == "/api/system/backup/download"
    assert payload["backup"]["restore_route"] == "/api/system/backup/restore"
    assert payload["providers"]["fallback_route"] == "/api/models/fallback"
    assert payload["runtime"]["governance_route"] == "/api/runtime-center/governance/status"
    assert payload["memory"]["backends_route"] == "/api/runtime-center/memory/backends"
    assert payload["memory"]["qmd"]["available"] is True
    assert payload["memory"]["qmd"]["metadata"]["query_mode"] == "search"


def test_system_overview_caches_workspace_stats(tmp_path: Path, monkeypatch) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "notes.txt").write_text("cached", encoding="utf-8")

    _patch_workspace(monkeypatch, workspace_root)
    app = build_app(tmp_path)
    client = TestClient(app)

    call_count = 0

    def _counting_dir_stats(root: Path) -> tuple[int, int]:
        nonlocal call_count
        call_count += 1
        return (1, 6)

    monkeypatch.setattr("copaw.app.routers.system._dir_stats", _counting_dir_stats)
    from copaw.app.routers import system as system_router_module

    system_router_module._workspace_stats_cache.clear()

    first = client.get("/system/overview")
    second = client.get("/system/overview")

    assert first.status_code == 200
    assert second.status_code == 200
    assert call_count == 1


def test_system_self_check_reports_provider_fallback(tmp_path: Path) -> None:
    app = build_app(tmp_path)
    client = TestClient(app)

    response = client.get("/system/self-check")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_status"] in {"pass", "warn"}
    by_name = {item["name"]: item for item in payload["checks"]}
    assert by_name["provider_active_model"]["status"] == "pass"
    assert by_name["provider_fallback"]["status"] == "pass"
    assert by_name["provider_fallback"]["meta"]["count"] == 1
    assert by_name["memory_qmd_sidecar"]["status"] == "pass"
    assert by_name["memory_qmd_sidecar"]["meta"]["query_mode"] == "search"
    assert "Qwen3-Embedding-0.6B" in by_name["memory_qmd_sidecar"]["meta"]["embed_model"]
    assert by_name["memory_qmd_sidecar"]["meta"]["daemon_state"] == "running"
    assert by_name["memory_qmd_sidecar"]["meta"]["indexed_documents"] == 217


def test_system_self_check_surfaces_embedding_model_gap(tmp_path: Path) -> None:
    app = build_app(tmp_path)
    client = TestClient(app)

    response = client.get("/system/self-check")

    assert response.status_code == 200
    payload = response.json()
    by_name = {item["name"]: item for item in payload["checks"]}
    assert "memory_embedding_config" in by_name
    assert by_name["memory_embedding_config"]["status"] == "warn"
    assert (
        by_name["memory_embedding_config"]["meta"]["vector_disable_reason_code"]
        == "missing_embedding_model_name"
    )
    assert "EMBEDDING_MODEL_NAME" in by_name["memory_embedding_config"]["summary"]
    assert by_name["memory_vector_ready"]["status"] == "warn"
    assert by_name["memory_vector_ready"]["meta"]["vector_enabled"] is False


def test_system_self_check_warns_when_qmd_runtime_not_ready(tmp_path: Path) -> None:
    app = build_app(tmp_path)

    class _UnreadyMemoryRecallService:
        def list_backends(self):
            return [
                MemoryBackendDescriptor(
                    backend_id="qmd",
                    label="QMD Sidecar",
                    available=True,
                    reason="QMD indexed document count is behind manifest entries (0 < 217).",
                    metadata={
                        "install_mode": "path",
                        "query_mode": "query",
                        "embed_model": "hf:Qwen/Qwen3-Embedding-0.6B-GGUF/Qwen3-Embedding-0.6B-Q8_0.gguf",
                        "ready": False,
                        "dirty": False,
                        "runtime_problem": "QMD indexed document count is behind manifest entries (0 < 217).",
                        "collection_path_matches": False,
                        "indexed_documents": 0,
                        "pending_embeddings": 217,
                        "daemon_enabled": True,
                        "daemon_state": "failed",
                        "daemon_url": "http://127.0.0.1:8765",
                        "daemon_pid": None,
                    },
                ),
            ]

    app.state.memory_recall_service = _UnreadyMemoryRecallService()
    client = TestClient(app)

    response = client.get("/system/self-check")

    assert response.status_code == 200
    payload = response.json()
    by_name = {item["name"]: item for item in payload["checks"]}
    assert by_name["memory_qmd_sidecar"]["status"] == "warn"
    assert "behind manifest entries" in by_name["memory_qmd_sidecar"]["summary"]
    assert by_name["memory_qmd_sidecar"]["meta"]["ready"] is False
    assert by_name["memory_qmd_sidecar"]["meta"]["pending_embeddings"] == 217
    assert by_name["memory_qmd_sidecar"]["meta"]["daemon_state"] == "failed"


def test_system_backup_download_streams_workspace_archive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "notes.txt").write_text("backup me", encoding="utf-8")

    _patch_workspace(monkeypatch, workspace_root)
    app = build_app(tmp_path)
    client = TestClient(app)

    response = client.get("/system/backup/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment; filename=" in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "notes.txt" in archive.namelist()
        assert archive.read("notes.txt").decode("utf-8") == "backup me"


def test_system_backup_restore_merges_uploaded_archive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "keep.txt").write_text("keep", encoding="utf-8")

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("restored.txt", "restored")
        archive.writestr("nested/inside.txt", "nested value")

    _patch_workspace(monkeypatch, workspace_root)
    app = build_app(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/system/backup/restore",
        files={
            "file": ("backup.zip", archive_buffer.getvalue(), "application/zip"),
        },
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert (workspace_root / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert (workspace_root / "restored.txt").read_text(encoding="utf-8") == "restored"
    assert (workspace_root / "nested" / "inside.txt").read_text(
        encoding="utf-8",
    ) == "nested value"
