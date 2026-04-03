# -*- coding: utf-8 -*-
from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.system import router as system_router
from copaw.app.startup_recovery import StartupRecoverySummary
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


class FakeLoopTask:
    def __init__(
        self,
        *,
        name: str,
        done: bool = False,
        cancelled: bool = False,
    ) -> None:
        self._name = name
        self._done = done
        self._cancelled = cancelled

    def get_name(self) -> str:
        return self._name

    def done(self) -> bool:
        return self._done

    def cancelled(self) -> bool:
        return self._cancelled


class FakeRuntimeRepository:
    def list_runtimes(self, limit=None):
        assert limit is None
        return [
            SimpleNamespace(
                agent_id="agent-1",
                runtime_status="blocked",
                metadata={
                    "supervisor_last_failure_at": "2026-04-02T10:00:00+00:00",
                    "supervisor_last_failure_type": "RuntimeError",
                },
            ),
            SimpleNamespace(
                agent_id="agent-2",
                runtime_status="queued",
                metadata={},
            ),
        ]


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
    app.state.memory_manager = FakeMemoryManager()
    app.state.startup_recovery_summary = {"reason": "startup", "hydrated_tasks": 2}
    app.state.provider_manager = FakeProviderManager()
    return app


def _patch_workspace(monkeypatch, workspace_root: Path) -> None:
    monkeypatch.setattr("copaw.app.routers.workspace.WORKING_DIR", workspace_root)
    monkeypatch.setattr("copaw.app.routers.system.WORKING_DIR", workspace_root)


def test_system_overview_hides_memory_backend_surface(tmp_path: Path) -> None:
    app = build_app(tmp_path)
    client = TestClient(app)

    response = client.get("/system/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["backup"]["download_route"] == "/api/system/backup/download"
    assert payload["backup"]["restore_route"] == "/api/system/backup/restore"
    assert payload["providers"]["fallback_route"] == "/api/providers/admin/fallback"
    assert payload["providers"]["active_route"] == "/api/providers/admin/active"
    assert payload["runtime"]["governance_route"] == "/api/runtime-center/governance/status"
    assert "memory" not in payload


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
    assert "memory_qmd_sidecar" not in by_name
    assert "memory_embedding_config" not in by_name
    assert "memory_vector_ready" not in by_name


def test_system_self_check_hides_embedding_and_vector_runtime_noise(
    tmp_path: Path,
) -> None:
    app = build_app(tmp_path)
    client = TestClient(app)

    response = client.get("/system/self-check")

    assert response.status_code == 200
    payload = response.json()
    by_name = {item["name"]: item for item in payload["checks"]}
    assert "memory_embedding_config" not in by_name
    assert "memory_vector_ready" not in by_name
    assert "memory_qmd_sidecar" not in by_name


def test_system_self_check_hides_qmd_runtime_state(tmp_path: Path) -> None:
    app = build_app(tmp_path)
    client = TestClient(app)

    response = client.get("/system/self-check")

    assert response.status_code == 200
    payload = response.json()
    by_name = {item["name"]: item for item in payload["checks"]}
    assert "memory_qmd_sidecar" not in by_name


def test_system_self_check_exposes_runtime_summary_for_automation_and_recovery(
    tmp_path: Path,
) -> None:
    app = build_app(tmp_path)
    app.state.state_query_service = SimpleNamespace(
        list_schedules=lambda: [
            {"id": "sched-1", "status": "active"},
            {"id": "sched-2", "status": "paused"},
        ],
    )
    app.state.startup_recovery_summary = StartupRecoverySummary(
        reason="Recovered leases after restart.",
        expired_decisions=0,
        pending_decisions=1,
        active_schedules=2,
        notes=["Recovered canonical scheduler ownership after restart."],
    )
    app.state.automation_tasks = [
        FakeLoopTask(name="copaw-automation-host-recovery", done=False),
        FakeLoopTask(name="copaw-automation-operating-cycle", done=True),
    ]
    app.state.actor_supervisor = SimpleNamespace(
        _loop_task=FakeLoopTask(name="copaw-actor-supervisor", done=False),
        _poll_interval_seconds=1.25,
        _agent_tasks={
            "agent-1": FakeLoopTask(name="copaw-actor:agent-1", done=False),
            "agent-2": FakeLoopTask(name="copaw-actor:agent-2", done=True),
        },
        _runtime_repository=FakeRuntimeRepository(),
    )
    client = TestClient(app)

    response = client.get("/system/self-check")

    assert response.status_code == 200
    payload = response.json()
    runtime_summary = payload["runtime_summary"]
    assert runtime_summary["automation"]["loop_count"] == 2
    assert runtime_summary["automation"]["active_loop_count"] == 1
    assert runtime_summary["automation"]["loops"][0]["name"] == "copaw-automation-host-recovery"
    assert runtime_summary["automation"]["loops"][0]["status"] == "running"
    assert runtime_summary["automation"]["supervisor"]["status"] == "degraded"
    assert runtime_summary["automation"]["supervisor"]["running"] is True
    assert runtime_summary["automation"]["supervisor"]["poll_interval_seconds"] == 1.25
    assert runtime_summary["automation"]["supervisor"]["active_agent_run_count"] == 1
    assert runtime_summary["automation"]["supervisor"]["blocked_runtime_count"] == 1
    assert runtime_summary["automation"]["supervisor"]["recent_failure_count"] == 1
    assert runtime_summary["automation"]["supervisor"]["last_failure_type"] == "RuntimeError"
    assert runtime_summary["startup_recovery"]["available"] is True
    assert runtime_summary["startup_recovery"]["status"] == "ready"
    assert runtime_summary["startup_recovery"]["reason"] == "Recovered leases after restart."
    assert runtime_summary["startup_recovery"]["active_schedules"] == 2
    assert runtime_summary["startup_recovery"]["pending_decisions"] == 1
    assert runtime_summary["startup_recovery"]["notes"] == [
        "Recovered canonical scheduler ownership after restart."
    ]


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
