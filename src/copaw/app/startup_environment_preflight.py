# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from ..state import ExecutorRuntimeService, SQLiteStateStore


class StartupEnvironmentPreflightError(RuntimeError):
    """Raised when the startup environment is not writable enough to boot."""


def resolve_environment_preflight_paths(*, working_dir: Path) -> dict[str, Path]:
    root = Path(working_dir).expanduser().resolve()
    return {
        "working_dir": root,
        "log_path": root / "copaw.log",
        "state_db_path": root / "state" / "phase1.sqlite3",
        "evidence_db_path": root / "evidence" / "phase1.sqlite3",
    }


def _probe_directory_write_access(path: Path) -> dict[str, object]:
    target = Path(path).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    probe_path = target / f".copaw-write-probe-{uuid.uuid4().hex}.tmp"
    probe_path.write_text("probe", encoding="utf-8")
    try:
        return {
            "status": "pass",
            "summary": "Workspace write access is available.",
            "meta": {"path": str(target)},
        }
    finally:
        if probe_path.exists():
            probe_path.unlink()


def _probe_log_path_write_access(path: Path) -> dict[str, object]:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists()
    with target.open("a", encoding="utf-8"):
        pass
    if not existed and target.exists() and target.stat().st_size == 0:
        target.unlink()
    return {
        "status": "pass",
        "summary": "Log file path is writable.",
        "meta": {"path": str(target)},
    }


def _probe_sqlite_write_access(path: Path) -> dict[str, object]:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    try:
        row = connection.execute("PRAGMA user_version").fetchone()
        current_user_version = int(row[0] if row else 0)
        connection.execute(f"PRAGMA user_version = {current_user_version}")
        connection.commit()
    finally:
        connection.close()
    return {
        "status": "pass",
        "summary": "SQLite write probe succeeded.",
        "meta": {"path": str(target)},
    }


def _probe_subprocess_spawn(timeout_seconds: float = 2.0) -> dict[str, object]:
    command = [sys.executable, "-c", "pass"]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=max(0.1, float(timeout_seconds)),
        check=False,
    )
    if completed.returncode == 0:
        return {
            "status": "pass",
            "summary": "Subprocess spawn is available.",
            "meta": {
                "command": " ".join(command),
                "timeout_seconds": timeout_seconds,
                "returncode": completed.returncode,
            },
        }
    return {
        "status": "warn",
        "summary": (
            "Subprocess spawn returned a non-zero exit code during doctor probe."
        ),
        "meta": {
            "command": " ".join(command),
            "timeout_seconds": timeout_seconds,
            "returncode": completed.returncode,
            "stderr": completed.stderr.strip(),
        },
    }


def _resolve_managed_sidecar_executable_path(state_db_path: Path) -> Path | None:
    target = Path(state_db_path).expanduser().resolve()
    try:
        service = ExecutorRuntimeService(state_store=SQLiteStateStore(target))
        install = service.get_active_sidecar_install(runtime_family="codex")
    except Exception:
        return None
    executable_path = getattr(install, "executable_path", None)
    if not executable_path:
        return None
    return Path(str(executable_path)).expanduser().resolve()


def _probe_managed_sidecar_executable(path: Path) -> dict[str, object]:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Managed sidecar executable not found: {target}")
    if not target.is_file():
        raise RuntimeError(f"Managed sidecar executable is not a file: {target}")
    return {
        "status": "pass",
        "summary": "Managed sidecar executable is available.",
        "meta": {"path": str(target)},
    }


def _run_check(
    *,
    name: str,
    fatal_on_fail: bool,
    probe,
) -> tuple[dict[str, object], bool]:
    try:
        payload = probe()
    except Exception as exc:  # pragma: no cover - exercised by tests via patching
        check = {
            "name": name,
            "status": "fail",
            "summary": str(exc),
            "meta": {"error_type": type(exc).__name__},
        }
    else:
        status = str(payload.get("status") or "pass").strip().lower() or "pass"
        check = {
            "name": name,
            "status": status,
            "summary": str(payload.get("summary") or "").strip(),
            "meta": dict(payload.get("meta") or {}),
        }
    return check, fatal_on_fail and check["status"] == "fail"


def build_environment_preflight_report(
    *,
    working_dir: Path,
    log_path: Path,
    state_db_path: Path,
    evidence_db_path: Path,
    include_subprocess: bool = False,
    managed_sidecar_executable_path: Path | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, object]] = []
    fatal = False
    resolved_sidecar_path = (
        Path(managed_sidecar_executable_path).expanduser().resolve()
        if managed_sidecar_executable_path is not None
        else _resolve_managed_sidecar_executable_path(state_db_path)
    )
    for name, probe, fatal_on_fail in (
        (
            "workspace_write_access",
            lambda: _probe_directory_write_access(working_dir),
            True,
        ),
        (
            "log_path_write_access",
            lambda: _probe_log_path_write_access(log_path),
            False,
        ),
        (
            "state_db_write_access",
            lambda: _probe_sqlite_write_access(state_db_path),
            True,
        ),
        (
            "evidence_db_write_access",
            lambda: _probe_sqlite_write_access(evidence_db_path),
            True,
        ),
    ):
        check, fatal_check = _run_check(
            name=name,
            fatal_on_fail=fatal_on_fail,
            probe=probe,
        )
        checks.append(check)
        fatal = fatal or fatal_check
    if resolved_sidecar_path is not None:
        check, fatal_check = _run_check(
            name="managed_sidecar_executable",
            fatal_on_fail=True,
            probe=lambda: _probe_managed_sidecar_executable(resolved_sidecar_path),
        )
        checks.append(check)
        fatal = fatal or fatal_check
    if include_subprocess:
        check, _ = _run_check(
            name="subprocess_spawn",
            fatal_on_fail=False,
            probe=lambda: _probe_subprocess_spawn(),
        )
        checks.append(check)
    statuses = {str(item["status"]) for item in checks}
    overall_status = (
        "fail"
        if "fail" in statuses
        else "warn"
        if "warn" in statuses
        else "pass"
    )
    summary = (
        "Startup environment preflight passed."
        if overall_status == "pass"
        else "Startup environment preflight found blocking issues."
        if fatal
        else "Startup environment preflight found degradations."
    )
    return {
        "overall_status": overall_status,
        "fatal": fatal,
        "summary": summary,
        "checks": checks,
    }


def assert_startup_environment_ready(
    *,
    working_dir: Path,
    log_path: Path,
    state_db_path: Path,
    evidence_db_path: Path,
) -> dict[str, Any]:
    report = build_environment_preflight_report(
        working_dir=working_dir,
        log_path=log_path,
        state_db_path=state_db_path,
        evidence_db_path=evidence_db_path,
        include_subprocess=False,
    )
    if not report["fatal"]:
        return report
    failed_checks = [
        f"{item['name']}: {item['summary']}"
        for item in report["checks"]
        if item.get("status") == "fail"
    ]
    raise StartupEnvironmentPreflightError(
        "Startup environment preflight failed: " + "; ".join(failed_checks),
    )


__all__ = [
    "StartupEnvironmentPreflightError",
    "assert_startup_environment_ready",
    "build_environment_preflight_report",
    "resolve_environment_preflight_paths",
]
