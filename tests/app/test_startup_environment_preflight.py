from __future__ import annotations

from pathlib import Path

import pytest

from copaw.app import startup_environment_preflight as preflight_module
from copaw.state import SQLiteStateStore
from copaw.state import models_executor_runtime as executor_models
from copaw.state.executor_runtime_service import ExecutorRuntimeService
from copaw.app.startup_environment_preflight import (
    StartupEnvironmentPreflightError,
    assert_startup_environment_ready,
    build_environment_preflight_report,
)


def test_build_environment_preflight_report_includes_subprocess_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        preflight_module,
        "_probe_subprocess_spawn",
        lambda timeout_seconds=2.0: {
            "status": "pass",
            "summary": "Subprocess spawn is available.",
            "meta": {"command": "python -c pass", "timeout_seconds": timeout_seconds},
        },
    )

    report = build_environment_preflight_report(
        working_dir=tmp_path,
        log_path=tmp_path / "copaw.log",
        state_db_path=tmp_path / "state.sqlite3",
        evidence_db_path=tmp_path / "evidence.sqlite3",
        include_subprocess=True,
    )

    by_name = {item["name"]: item for item in report["checks"]}
    assert report["overall_status"] == "pass"
    assert report["fatal"] is False
    assert by_name["subprocess_spawn"]["status"] == "pass"


def test_build_environment_preflight_report_marks_sqlite_failure_fatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_probe = preflight_module._probe_sqlite_write_access

    def _failing_probe(path: Path) -> dict[str, object]:
        if path.name == "state.sqlite3":
            raise PermissionError("readonly database")
        return original_probe(path)

    monkeypatch.setattr(
        preflight_module,
        "_probe_sqlite_write_access",
        _failing_probe,
    )

    report = build_environment_preflight_report(
        working_dir=tmp_path,
        log_path=tmp_path / "copaw.log",
        state_db_path=tmp_path / "state.sqlite3",
        evidence_db_path=tmp_path / "evidence.sqlite3",
        include_subprocess=False,
    )

    by_name = {item["name"]: item for item in report["checks"]}
    assert report["fatal"] is True
    assert report["overall_status"] == "fail"
    assert by_name["state_db_write_access"]["status"] == "fail"
    assert "readonly database" in by_name["state_db_write_access"]["summary"]


def test_assert_startup_environment_ready_raises_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        preflight_module,
        "build_environment_preflight_report",
        lambda **_kwargs: {
            "overall_status": "fail",
            "fatal": True,
            "summary": "Startup environment preflight failed.",
            "checks": [
                {
                    "name": "state_db_write_access",
                    "status": "fail",
                    "summary": "readonly database",
                    "meta": {"path": str(tmp_path / "state.sqlite3")},
                },
            ],
        },
    )

    with pytest.raises(StartupEnvironmentPreflightError) as excinfo:
        assert_startup_environment_ready(
            working_dir=tmp_path,
            log_path=tmp_path / "copaw.log",
            state_db_path=tmp_path / "state.sqlite3",
            evidence_db_path=tmp_path / "evidence.sqlite3",
        )

    assert "state_db_write_access" in str(excinfo.value)
    assert "readonly database" in str(excinfo.value)


def test_build_environment_preflight_report_includes_managed_sidecar_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sidecar_path = tmp_path / "runtime" / "codex" / "codex.exe"
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(
        preflight_module,
        "_probe_managed_sidecar_executable",
        lambda path: {
            "status": "pass",
            "summary": "Managed sidecar executable is available.",
            "meta": {"path": str(path)},
        },
        raising=False,
    )

    report = build_environment_preflight_report(
        working_dir=tmp_path,
        log_path=tmp_path / "copaw.log",
        state_db_path=tmp_path / "state.sqlite3",
        evidence_db_path=tmp_path / "evidence.sqlite3",
        include_subprocess=False,
        managed_sidecar_executable_path=sidecar_path,
    )

    by_name = {item["name"]: item for item in report["checks"]}
    assert by_name["managed_sidecar_executable"]["status"] == "pass"
    assert by_name["managed_sidecar_executable"]["meta"]["path"] == str(sidecar_path)


def test_build_environment_preflight_report_fails_closed_on_incompatible_sidecar_version(
    tmp_path: Path,
) -> None:
    sidecar_path = tmp_path / "runtime" / "codex" / "codex.exe"
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text("stub", encoding="utf-8")
    state_db_path = tmp_path / "state.sqlite3"
    service = ExecutorRuntimeService(state_store=SQLiteStateStore(state_db_path))
    service.upsert_sidecar_install(
        executor_models.ExecutorSidecarInstallRecord(
            install_id="codex-stable-0.9.0",
            runtime_family="codex",
            channel="stable",
            version="0.9.0",
            install_root=str(sidecar_path.parent),
            executable_path=str(sidecar_path),
            install_status="ready",
            metadata={"protocol_features": []},
        )
    )
    service.upsert_sidecar_compatibility_policy(
        executor_models.ExecutorSidecarCompatibilityPolicyRecord(
            policy_id="codex-stable-policy",
            runtime_family="codex",
            channel="stable",
            supported_version_range=">=0.10,<0.11",
            required_copaw_version_range=">=1.0",
            status="active",
            metadata={"fail_closed": True},
        )
    )

    report = build_environment_preflight_report(
        working_dir=tmp_path,
        log_path=tmp_path / "copaw.log",
        state_db_path=state_db_path,
        evidence_db_path=tmp_path / "evidence.sqlite3",
        include_subprocess=False,
        managed_sidecar_executable_path=sidecar_path,
    )

    by_name = {item["name"]: item for item in report["checks"]}
    assert report["fatal"] is True
    assert report["overall_status"] == "fail"
    assert by_name["managed_sidecar_compatibility"]["status"] == "fail"
    assert "0.9.0" in by_name["managed_sidecar_compatibility"]["summary"]
