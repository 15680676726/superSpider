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
    app.state.runtime_provider = FakeProviderManager()
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

    system_router_module.clear_workspace_stats_cache()

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


def test_system_self_check_uses_runtime_root_for_preflight_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace_root = tmp_path / "runtime-root"
    workspace_root.mkdir()
    _patch_workspace(monkeypatch, workspace_root)

    app = build_app(tmp_path)
    app.state.state_store = SQLiteStateStore(
        workspace_root / "state" / "phase1.sqlite3"
    )
    app.state.state_store.initialize()
    client = TestClient(app)

    overview_response = client.get("/system/overview")
    self_check_response = client.get("/system/self-check")

    assert overview_response.status_code == 200
    assert self_check_response.status_code == 200

    overview = overview_response.json()
    self_check = self_check_response.json()
    assert overview["self_check"]["state_db_path"] == str(
        workspace_root / "state" / "phase1.sqlite3"
    )
    assert overview["self_check"]["evidence_db_path"] == str(
        workspace_root / "evidence" / "phase1.sqlite3"
    )

    preflight_by_name = {
        item["name"]: item for item in self_check["environment_preflight"]["checks"]
    }
    assert preflight_by_name["workspace_write_access"]["meta"]["path"] == str(
        workspace_root
    )
    assert preflight_by_name["log_path_write_access"]["meta"]["path"] == str(
        workspace_root / "copaw.log"
    )
    assert preflight_by_name["evidence_db_write_access"]["meta"]["path"] == str(
        workspace_root / "evidence" / "phase1.sqlite3"
    )


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
        absorption_action_kind="human-assist",
        absorption_action_summary="Need one governed confirmation to resume.",
        absorption_action_materialized=True,
        absorption_human_task_id="human-assist-1",
        notes=["Recovered canonical scheduler ownership after restart."],
    )
    app.state.automation_tasks = [
        FakeLoopTask(name="copaw-automation-host-recovery", done=False),
        FakeLoopTask(name="copaw-automation-operating-cycle", done=True),
    ]
    app.state.actor_supervisor = SimpleNamespace(
        snapshot=lambda: {
            "available": True,
            "status": "degraded",
            "running": True,
            "poll_interval_seconds": 1.25,
            "loop_task_name": "copaw-actor-supervisor",
            "active_agent_run_count": 1,
            "blocked_runtime_count": 1,
            "recent_failure_count": 1,
            "last_failure_at": "2026-04-02T10:00:00+00:00",
            "last_failure_type": "RuntimeError",
        }
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
    assert runtime_summary["startup_recovery"]["absorption_action_kind"] == (
        "human-assist"
    )
    assert runtime_summary["startup_recovery"]["absorption_action_summary"] == (
        "Need one governed confirmation to resume."
    )
    assert runtime_summary["startup_recovery"]["absorption_action_materialized"] is True
    assert runtime_summary["startup_recovery"]["absorption_human_task_id"] == (
        "human-assist-1"
    )
    assert runtime_summary["startup_recovery"]["notes"] == [
        "Recovered canonical scheduler ownership after restart."
    ]
    assert runtime_summary["status"] == "degraded"
    by_name = {item["name"]: item for item in payload["checks"]}
    assert by_name["startup_recovery"]["meta"]["recovery_summary"][
        "absorption_action_kind"
    ] == "human-assist"
    assert by_name["startup_recovery"]["meta"]["recovery_summary"][
        "absorption_action_summary"
    ] == "Need one governed confirmation to resume."
    assert by_name["startup_recovery"]["meta"]["recovery_summary"][
        "absorption_action_materialized"
    ] is True
    assert by_name["startup_recovery"]["meta"]["recovery_summary"][
        "absorption_human_task_id"
    ] == "human-assist-1"


def test_system_self_check_prefers_environment_runtime_recovery_report(
    tmp_path: Path,
) -> None:
    app = build_app(tmp_path)

    class FakeEnvironmentService:
        def get_latest_recovery_report(self):
            return {
                "reason": "runtime-recovery",
                "pending_decisions": 1,
                "active_schedules": 4,
                "latest_scope": "runtime",
            }

    app.state.environment_service = FakeEnvironmentService()
    app.state.latest_recovery_report = {
        "reason": "stale-startup-alias",
        "pending_decisions": 9,
    }
    client = TestClient(app)

    response = client.get("/system/self-check")

    assert response.status_code == 200
    payload = response.json()
    by_name = {item["name"]: item for item in payload["checks"]}
    assert by_name["startup_recovery"]["meta"]["recovery_summary"]["reason"] == (
        "runtime-recovery"
    )
    assert by_name["startup_recovery"]["meta"]["recovery_summary"]["latest_scope"] == (
        "runtime"
    )


def test_system_self_check_prefers_persisted_automation_loop_snapshots_when_live_tasks_are_absent(
    tmp_path: Path,
) -> None:
    app = build_app(tmp_path)
    app.state.state_query_service = SimpleNamespace(
        list_schedules=lambda: [],
    )
    app.state.startup_recovery_summary = StartupRecoverySummary(
        reason="Recovered leases after restart.",
        active_schedules=0,
    )
    app.state.automation_tasks = []
    app.state.automation_loop_runtime_repository = SimpleNamespace(
        list_loops=lambda limit=None: [
            SimpleNamespace(
                automation_task_id=(
                    "copaw-main-brain:operating-cycle:system:run_operating_cycle"
                ),
                task_name="operating-cycle",
                capability_ref="system:run_operating_cycle",
                owner_agent_id="copaw-main-brain",
                interval_seconds=180,
                coordinator_contract="automation-coordinator/v1",
                loop_phase="failed",
                health_status="degraded",
                last_gate_reason="active-industry",
                last_result_phase="failed",
                last_error_summary="planner timeout",
                submit_count=2,
                consecutive_failures=2,
            )
        ]
    )
    client = TestClient(app)

    response = client.get("/system/self-check")

    assert response.status_code == 200
    payload = response.json()
    runtime_summary = payload["runtime_summary"]
    assert runtime_summary["status"] == "degraded"
    assert runtime_summary["automation"]["status"] == "degraded"
    assert runtime_summary["automation"]["loop_count"] == 1
    assert runtime_summary["automation"]["loops"][0]["task_name"] == "operating-cycle"
    assert runtime_summary["automation"]["loops"][0]["health_status"] == "degraded"
    assert payload["overall_status"] == "warn"


def test_system_self_check_includes_environment_preflight_checks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = build_app(tmp_path)
    client = TestClient(app)
    monkeypatch.setattr(
        "copaw.app.routers.system.build_environment_preflight_report",
        lambda **_kwargs: {
            "overall_status": "warn",
            "fatal": False,
            "summary": "Subprocess probe is degraded.",
            "checks": [
                {
                    "name": "subprocess_spawn",
                    "status": "warn",
                    "summary": "Subprocess spawn is unavailable.",
                    "meta": {"command": "python -c pass"},
                },
            ],
        },
    )

    response = client.get("/system/self-check")

    assert response.status_code == 200
    payload = response.json()
    by_name = {item["name"]: item for item in payload["checks"]}
    assert by_name["subprocess_spawn"]["status"] == "warn"
    assert payload["environment_preflight"]["overall_status"] == "warn"


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
