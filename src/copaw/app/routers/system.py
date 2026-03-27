# -*- coding: utf-8 -*-
"""System operations API for V3 delivery surfaces."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

from fastapi import APIRouter, File, Request, UploadFile

from ...constant import WORKING_DIR
from ...providers.provider_manager import ProviderManager
from ..runtime_health_service import RuntimeHealthService
from .workspace import _dir_stats, download_workspace, upload_workspace

router = APIRouter(prefix="/system", tags=["system"])

_STATE_DB_PATH = WORKING_DIR / "state" / "phase1.sqlite3"
_EVIDENCE_DB_PATH = WORKING_DIR / "evidence" / "phase1.sqlite3"
_WORKSPACE_STATS_TTL_SECONDS = 5.0
_workspace_stats_cache: dict[str, tuple[float, tuple[int, int]]] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _service_present(app_state: Any, name: str) -> bool:
    return getattr(app_state, name, None) is not None


def _list_memory_backends(app_state: Any) -> list[dict[str, Any]]:
    service = getattr(app_state, "memory_recall_service", None)
    lister = getattr(service, "list_backends", None)
    if not callable(lister):
        return []
    payload: list[dict[str, Any]] = []
    for item in lister() or []:
        model_dump = getattr(item, "model_dump", None)
        if callable(model_dump):
            payload.append(model_dump(mode="json"))
        elif isinstance(item, dict):
            payload.append(dict(item))
    return payload


def _workspace_stats(root: Path) -> tuple[int, int]:
    cache_key = str(root.resolve())
    now = time.monotonic()
    cached = _workspace_stats_cache.get(cache_key)
    if cached is not None:
        cached_at, stats = cached
        if now - cached_at <= _WORKSPACE_STATS_TTL_SECONDS:
            return stats
    stats = _dir_stats(root)
    _workspace_stats_cache[cache_key] = (now, stats)
    return stats


def _get_runtime_health_service(app_state: Any) -> RuntimeHealthService:
    service = getattr(app_state, "runtime_health_service", None)
    if isinstance(service, RuntimeHealthService):
        return service
    return RuntimeHealthService.from_app_state(app_state)


@router.get("/overview", response_model=dict[str, object])
async def get_system_overview(request: Request) -> dict[str, object]:
    app_state = request.app.state
    provider_manager = getattr(app_state, "provider_manager", None)
    if provider_manager is None:
        provider_manager = ProviderManager.get_instance()
    active_model = None
    get_active_model = getattr(provider_manager, "get_active_model", None)
    if callable(get_active_model):
        active_model = get_active_model()
    fallback_slots = []
    get_fallback_slots = getattr(provider_manager, "get_fallback_slots", None)
    if callable(get_fallback_slots):
        fallback_slots = [
            slot.model_dump(mode="json")
            for slot in (get_fallback_slots() or [])
        ]

    file_count, total_size = _workspace_stats(WORKING_DIR)
    startup_recovery = getattr(app_state, "startup_recovery_summary", None)
    memory_backends = _list_memory_backends(app_state)
    qmd_backend = next(
        (item for item in memory_backends if item.get("backend_id") == "qmd"),
        None,
    )
    return {
        "generated_at": _utc_now_iso(),
        "backup": {
            "root_path": str(WORKING_DIR),
            "download_route": "/api/system/backup/download",
            "restore_route": "/api/system/backup/restore",
            "workspace_download_route": "/api/workspace/download",
            "workspace_restore_route": "/api/workspace/upload",
            "file_count": file_count,
            "total_size": total_size,
        },
        "self_check": {
            "route": "/api/system/self-check",
            "state_db_path": str(_STATE_DB_PATH),
            "evidence_db_path": str(_EVIDENCE_DB_PATH),
        },
        "providers": {
            "active_model": (
                active_model.model_dump(mode="json")
                if hasattr(active_model, "model_dump")
                else active_model
            ),
            "fallback_slots": fallback_slots,
            "fallback_route": "/api/models/fallback",
            "active_route": "/api/models/active",
        },
        "runtime": {
            "governance_route": "/api/runtime-center/governance/status",
            "recovery_route": "/api/runtime-center/recovery/latest",
            "events_route": "/api/runtime-center/events",
            "startup_recovery": startup_recovery,
        },
        "memory": {
            "backends_route": "/api/runtime-center/memory/backends",
            "backends": memory_backends,
            "qmd": qmd_backend,
        },
    }


@router.get("/self-check", response_model=dict[str, object])
async def run_system_self_check(request: Request) -> dict[str, object]:
    app_state = request.app.state
    runtime_health_service = _get_runtime_health_service(app_state)
    provider_manager = getattr(app_state, "provider_manager", None)
    if provider_manager is None:
        provider_manager = ProviderManager.get_instance()

    checks: list[dict[str, object]] = []

    def add_check(name: str, status: str, summary: str, **meta: object) -> None:
        checks.append({
            "name": name,
            "status": status,
            "summary": summary,
            "meta": meta,
        })

    add_check(
        "working_dir",
        "pass" if WORKING_DIR.is_dir() else "fail",
        f"Working directory {'exists' if WORKING_DIR.is_dir() else 'is missing'}.",
        path=str(WORKING_DIR),
    )
    add_check(
        "state_store",
        "pass" if _service_present(app_state, "state_store") and _STATE_DB_PATH.exists() else "warn",
        "Unified state store is wired." if _service_present(app_state, "state_store") else "State store is not attached to app.state.",
        path=str(_STATE_DB_PATH),
        exists=_STATE_DB_PATH.exists(),
    )
    add_check(
        "evidence_ledger",
        "pass" if _service_present(app_state, "evidence_ledger") and _EVIDENCE_DB_PATH.exists() else "warn",
        "Evidence ledger is wired." if _service_present(app_state, "evidence_ledger") else "Evidence ledger is not attached to app.state.",
        path=str(_EVIDENCE_DB_PATH),
        exists=_EVIDENCE_DB_PATH.exists(),
    )
    for runtime_health_check in runtime_health_service.build_checks():
        meta = runtime_health_check.get("meta")
        checks.append({
            "name": str(runtime_health_check.get("name") or "runtime_health"),
            "status": str(runtime_health_check.get("status") or "warn"),
            "summary": str(runtime_health_check.get("summary") or ""),
            "meta": dict(meta) if isinstance(meta, dict) else {},
        })
    for service_name in (
        "capability_service",
        "kernel_dispatcher",
        "runtime_event_bus",
        "governance_service",
        "cron_manager",
    ):
        present = _service_present(app_state, service_name)
        add_check(
            service_name,
            "pass" if present else "warn",
            f"{service_name} {'is available' if present else 'is not available'}.",
        )

    memory_backends = _list_memory_backends(app_state)
    qmd_backend = next(
        (item for item in memory_backends if item.get("backend_id") == "qmd"),
        None,
    )
    qmd_available = bool(qmd_backend and qmd_backend.get("available"))
    qmd_ready = False
    qmd_metadata = dict(qmd_backend.get("metadata") or {}) if isinstance(qmd_backend, dict) else {}
    qmd_ready = bool(qmd_metadata.get("ready"))
    qmd_runtime_problem = str(qmd_metadata.get("runtime_problem") or "").strip()
    qmd_reason = (
        str(qmd_backend.get("reason") or "").strip()
        if isinstance(qmd_backend, dict)
        else ""
    )
    qmd_summary = "QMD sidecar is installed and reachable."
    qmd_status = "pass" if qmd_available and qmd_ready else "warn"
    if qmd_backend is None:
        qmd_status = "warn"
        qmd_summary = "Memory recall service does not expose a QMD backend descriptor."
    elif not qmd_available:
        qmd_summary = qmd_reason or "QMD sidecar is not installed or not reachable."
    elif not qmd_ready:
        qmd_summary = (
            qmd_reason
            or qmd_runtime_problem
            or "QMD sidecar is reachable but its runtime index is not ready."
        )
    add_check(
        "memory_qmd_sidecar",
        qmd_status,
        qmd_summary,
        backend=qmd_backend,
        install_mode=qmd_metadata.get("install_mode"),
        query_mode=qmd_metadata.get("query_mode"),
        embed_model=qmd_metadata.get("embed_model"),
        ready=qmd_metadata.get("ready"),
        dirty=qmd_metadata.get("dirty"),
        runtime_problem=qmd_metadata.get("runtime_problem"),
        collection_path_matches=qmd_metadata.get("collection_path_matches"),
        indexed_documents=qmd_metadata.get("indexed_documents"),
        pending_embeddings=qmd_metadata.get("pending_embeddings"),
        daemon_enabled=qmd_metadata.get("daemon_enabled"),
        daemon_state=qmd_metadata.get("daemon_state"),
        daemon_url=qmd_metadata.get("daemon_url"),
        daemon_pid=qmd_metadata.get("daemon_pid"),
    )

    active_model = None
    get_active_model = getattr(provider_manager, "get_active_model", None)
    if callable(get_active_model):
        active_model = get_active_model()
    provider_ok = False
    if active_model is not None and getattr(active_model, "provider_id", None):
        get_provider = getattr(provider_manager, "get_provider", None)
        if callable(get_provider):
            provider_ok = get_provider(active_model.provider_id) is not None
    add_check(
        "provider_active_model",
        "pass" if provider_ok else "warn",
        (
            f"Active provider '{active_model.provider_id}' is available."
            if provider_ok and active_model is not None
            else "Active provider/model is missing or unresolved."
        ),
        active_model=(
            active_model.model_dump(mode="json")
            if hasattr(active_model, "model_dump")
            else active_model
        ),
    )

    fallback_slots = []
    get_fallback_slots = getattr(provider_manager, "get_fallback_slots", None)
    if callable(get_fallback_slots):
        fallback_slots = get_fallback_slots() or []
    add_check(
        "provider_fallback",
        "pass" if fallback_slots else "warn",
        "Fallback chain is configured." if fallback_slots else "Fallback chain is empty.",
        count=len(fallback_slots),
        slots=[
            slot.model_dump(mode="json")
            if hasattr(slot, "model_dump")
            else slot
            for slot in fallback_slots
        ],
    )

    recovery_summary = getattr(app_state, "startup_recovery_summary", None)
    add_check(
        "startup_recovery",
        "pass" if recovery_summary is not None else "warn",
        "Startup recovery summary is available." if recovery_summary is not None else "Startup recovery summary is missing.",
        recovery_summary=recovery_summary,
    )

    statuses = {item["status"] for item in checks}
    overall_status = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    return {
        "generated_at": _utc_now_iso(),
        "overall_status": overall_status,
        "checks": checks,
    }


@router.get("/backup/download")
async def download_system_backup():
    return await download_workspace()


@router.post("/backup/restore", response_model=dict[str, object])
async def restore_system_backup(file: UploadFile = File(...)) -> dict[str, object]:
    return await upload_workspace(file)
