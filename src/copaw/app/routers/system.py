# -*- coding: utf-8 -*-
"""System operations API for V3 delivery surfaces."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

from fastapi import APIRouter, File, Request, UploadFile

from ...capabilities.remote_skill_catalog import search_curated_skill_catalog
from ...constant import WORKING_DIR
from ...kernel import query_execution_writeback as query_execution_writeback_module
from ...utils.cache import TTLCache
from ..startup_environment_preflight import (
    build_environment_preflight_report,
    resolve_environment_preflight_paths,
)
from ..runtime_center.models import RuntimeCenterAppStateView
from ..runtime_recovery_report import resolve_current_recovery_report
from ..runtime_health_service import RuntimeHealthService
from .workspace import _dir_stats, download_workspace, upload_workspace

router = APIRouter(prefix="/system", tags=["system"])
_WORKSPACE_STATS_TTL_SECONDS = 5.0
_workspace_stats_cache = TTLCache[str, tuple[int, int]](
    ttl_seconds=_WORKSPACE_STATS_TTL_SECONDS,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _service_present(app_state: Any, name: str) -> bool:
    return getattr(app_state, name, None) is not None


def _workspace_stats(root: Path) -> tuple[int, int]:
    cache_key = str(root.resolve())
    cached = _workspace_stats_cache.get(cache_key)
    if cached is not None:
        return cached
    stats = _dir_stats(root)
    return _workspace_stats_cache.set(cache_key, stats)


def clear_workspace_stats_cache() -> None:
    _workspace_stats_cache.clear()


def _get_runtime_health_service(app_state: Any) -> RuntimeHealthService:
    service = getattr(app_state, "runtime_health_service", None)
    if isinstance(service, RuntimeHealthService):
        return service.bind_app_state(app_state)
    return RuntimeHealthService.from_app_state(app_state)


def _get_runtime_provider(app_state: Any) -> object:
    runtime_provider = getattr(app_state, "runtime_provider", None)
    if runtime_provider is not None:
        return runtime_provider
    raise RuntimeError("runtime_provider is not attached to app.state")


def _slot_ref(slot: object | None) -> tuple[str | None, str | None]:
    if slot is None:
        return (None, None)
    return (
        getattr(slot, "provider_id", None),
        getattr(slot, "model", None),
    )


def _slot_payload(slot: object | None) -> object:
    if slot is None:
        return None
    if hasattr(slot, "model_dump"):
        return slot.model_dump(mode="json")
    return slot


def _get_active_models_info(runtime_provider: object) -> object | None:
    getter = getattr(runtime_provider, "get_active_models_info", None)
    if not callable(getter):
        return None
    try:
        return getter()
    except Exception:
        return None


def _build_provider_resolution_check(runtime_provider: object) -> dict[str, object] | None:
    info = _get_active_models_info(runtime_provider)
    if info is None:
        return None
    active_slot = getattr(info, "active_llm", None)
    resolved_slot = getattr(info, "resolved_llm", None)
    fallback_applied = bool(getattr(info, "fallback_applied", False))
    resolution_reason = str(getattr(info, "resolution_reason", "") or "").strip()
    unavailable_candidates = list(getattr(info, "unavailable_candidates", []) or [])
    status = "pass" if resolved_slot is not None else "warn"
    summary = resolution_reason or (
        "Resolved a runnable provider/model slot."
        if resolved_slot is not None
        else "No available provider/model slot."
    )
    return {
        "name": "provider_resolution",
        "status": status,
        "summary": summary,
        "meta": {
            "active_model": _slot_payload(active_slot),
            "resolved_model": _slot_payload(resolved_slot),
            "fallback_applied": fallback_applied,
            "unavailable_candidates": unavailable_candidates,
        },
    }


def _probe_remote_skill_discovery(app_state: Any) -> object:
    probe = getattr(app_state, "remote_skill_discovery_probe", None)
    if callable(probe):
        return probe()
    return search_curated_skill_catalog("automation", limit=1)


def _build_remote_skill_discovery_check(app_state: Any) -> dict[str, object]:
    try:
        response = _probe_remote_skill_discovery(app_state)
        items = list(getattr(response, "items", []) or [])
        sources = list(getattr(response, "sources", []) or [])
        warnings = [
            str(item).strip()
            for item in list(getattr(response, "warnings", []) or [])
            if str(item).strip()
        ]
    except Exception as exc:
        return {
            "name": "remote_skill_discovery",
            "status": "warn",
            "summary": f"Curated remote skill discovery probe failed: {exc}",
            "meta": {
                "query": "automation",
                "item_count": 0,
                "source_count": 0,
                "warnings": [str(exc)],
            },
        }

    status = "pass" if items and not warnings else "warn"
    if items and not warnings:
        summary = f"Curated remote skill discovery returned {len(items)} result(s)."
    elif items:
        summary = "Curated remote skill discovery returned results with warnings."
    elif warnings:
        summary = warnings[0]
    else:
        summary = "Curated remote skill discovery returned no results."
    return {
        "name": "remote_skill_discovery",
        "status": status,
        "summary": summary,
        "meta": {
            "query": "automation",
            "item_count": len(items),
            "source_count": len(sources),
            "warnings": warnings,
        },
    }


def _probe_chat_decision_model(app_state: Any) -> object:
    probe = getattr(app_state, "chat_decision_model_probe", None)
    if callable(probe):
        return probe()
    query_execution_writeback_module.clear_chat_writeback_decision_cache()
    return query_execution_writeback_module.resolve_chat_writeback_model_decision_sync(
        text=(
            "Use the mounted browser capability right now. "
            "Open https://example.com and save a screenshot to C:\\temp\\probe.png."
        ),
    )


def _build_chat_decision_model_check(app_state: Any) -> dict[str, object]:
    try:
        decision = _probe_chat_decision_model(app_state)
    except (
        query_execution_writeback_module.ChatWritebackDecisionModelUnavailableError,
        query_execution_writeback_module.ChatWritebackDecisionModelTimeoutError,
    ) as exc:
        return {
            "name": "chat_decision_model",
            "status": "warn",
            "summary": f"Chat decision model is unavailable: {exc}",
            "meta": {
                "intent_kind": None,
                "kickoff_allowed": False,
            },
        }
    except Exception as exc:
        return {
            "name": "chat_decision_model",
            "status": "warn",
            "summary": f"Chat decision model probe failed: {exc}",
            "meta": {
                "intent_kind": None,
                "kickoff_allowed": False,
            },
        }

    intent_kind = getattr(decision, "intent_kind", None)
    kickoff_allowed = bool(getattr(decision, "kickoff_allowed", False))
    risky_actuation_requested = bool(
        getattr(decision, "risky_actuation_requested", False),
    )
    ready = intent_kind == "execute-task" and (kickoff_allowed or risky_actuation_requested)
    summary = (
        "Chat decision model is ready for governed execute-task routing."
        if ready
        else "Chat decision model did not resolve execute-task readiness."
    )
    return {
        "name": "chat_decision_model",
        "status": "pass" if ready else "warn",
        "summary": summary,
        "meta": {
            "intent_kind": intent_kind,
            "kickoff_allowed": kickoff_allowed,
            "risky_actuation_requested": risky_actuation_requested,
            "confidence": getattr(decision, "confidence", None),
        },
    }


def _resolve_state_db_path(app_state: Any) -> Path:
    state_store = getattr(app_state, "state_store", None)
    raw_path = getattr(state_store, "_path", None)
    if raw_path is not None:
        return Path(raw_path).expanduser().resolve()
    return resolve_environment_preflight_paths(working_dir=WORKING_DIR)[
        "state_db_path"
    ]


def _resolve_evidence_db_path(app_state: Any) -> Path:
    return resolve_environment_preflight_paths(
        working_dir=_resolve_working_dir(app_state),
    )["evidence_db_path"]


def _resolve_working_dir(app_state: Any) -> Path:
    state_store = getattr(app_state, "state_store", None)
    raw_path = getattr(state_store, "_path", None)
    if raw_path is not None:
        state_path = Path(raw_path).expanduser().resolve()
        state_dir = state_path.parent
        if state_dir.name == "state":
            return state_dir.parent
        return state_dir
    return WORKING_DIR


def _build_environment_preflight(app_state: Any) -> dict[str, object]:
    working_dir = _resolve_working_dir(app_state)
    paths = resolve_environment_preflight_paths(working_dir=working_dir)
    return build_environment_preflight_report(
        working_dir=working_dir,
        log_path=paths["log_path"],
        state_db_path=_resolve_state_db_path(app_state),
        evidence_db_path=_resolve_evidence_db_path(app_state),
        include_subprocess=True,
    )


@router.get("/overview", response_model=dict[str, object])
async def get_system_overview(request: Request) -> dict[str, object]:
    app_state = request.app.state
    runtime_state = RuntimeCenterAppStateView.from_object(app_state)
    runtime_provider = _get_runtime_provider(app_state)
    active_model = None
    get_active_model = getattr(runtime_provider, "get_active_model", None)
    if callable(get_active_model):
        active_model = get_active_model()
    fallback_slots = []
    get_fallback_slots = getattr(runtime_provider, "get_fallback_slots", None)
    if callable(get_fallback_slots):
        fallback_slots = [
            slot.model_dump(mode="json")
            for slot in (get_fallback_slots() or [])
        ]

    file_count, total_size = _workspace_stats(WORKING_DIR)
    state_db_path = _resolve_state_db_path(app_state)
    evidence_db_path = _resolve_evidence_db_path(app_state)
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
            "state_db_path": str(state_db_path),
            "evidence_db_path": str(evidence_db_path),
        },
        "providers": {
            "active_model": (
                active_model.model_dump(mode="json")
                if hasattr(active_model, "model_dump")
                else active_model
            ),
            "fallback_slots": fallback_slots,
            "fallback_route": "/api/providers/admin/fallback",
            "active_route": "/api/providers/admin/active",
        },
        "runtime": {
            "governance_route": "/api/runtime-center/governance/status",
            "recovery_route": "/api/runtime-center/recovery/latest",
            "events_route": "/api/runtime-center/events",
            "recovery_source": runtime_state.resolve_recovery_summary()[1],
        },
    }


@router.get("/self-check", response_model=dict[str, object])
async def run_system_self_check(request: Request) -> dict[str, object]:
    app_state = request.app.state
    runtime_health_service = _get_runtime_health_service(app_state)
    runtime_summary = await runtime_health_service.build_runtime_summary()
    runtime_provider = _get_runtime_provider(app_state)
    state_db_path = _resolve_state_db_path(app_state)
    evidence_db_path = _resolve_evidence_db_path(app_state)
    environment_preflight = _build_environment_preflight(app_state)

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
        "pass" if _service_present(app_state, "state_store") and state_db_path.exists() else "warn",
        "Unified state store is wired." if _service_present(app_state, "state_store") else "State store is not attached to app.state.",
        path=str(state_db_path),
        exists=state_db_path.exists(),
    )
    add_check(
        "evidence_ledger",
        "pass" if _service_present(app_state, "evidence_ledger") and evidence_db_path.exists() else "warn",
        "Evidence ledger is wired." if _service_present(app_state, "evidence_ledger") else "Evidence ledger is not attached to app.state.",
        path=str(evidence_db_path),
        exists=evidence_db_path.exists(),
    )
    for item in environment_preflight.get("checks", []):
        checks.append({
            "name": str(item.get("name") or "environment_preflight"),
            "status": str(item.get("status") or "warn"),
            "summary": str(item.get("summary") or ""),
            "meta": dict(item.get("meta") or {}),
        })
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
    provider_resolution_check = _build_provider_resolution_check(runtime_provider)
    if provider_resolution_check is not None:
        checks.append(provider_resolution_check)
    active_model = None
    get_active_model = getattr(runtime_provider, "get_active_model", None)
    if callable(get_active_model):
        active_model = get_active_model()
    provider_ok = False
    info = _get_active_models_info(runtime_provider)
    if info is not None:
        provider_ok = (
            active_model is not None
            and _slot_ref(active_model) == _slot_ref(getattr(info, "resolved_llm", None))
        )
    elif active_model is not None and getattr(active_model, "provider_id", None):
        get_provider = getattr(runtime_provider, "get_provider", None)
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

    checks.append(_build_remote_skill_discovery_check(app_state))

    fallback_slots = []
    get_fallback_slots = getattr(runtime_provider, "get_fallback_slots", None)
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
    checks.append(_build_chat_decision_model_check(app_state))

    recovery_summary, _ = resolve_current_recovery_report(app_state)
    add_check(
        "startup_recovery",
        "pass" if recovery_summary is not None else "warn",
        "Recovery summary is available." if recovery_summary is not None else "Recovery summary is missing.",
        recovery_summary=recovery_summary,
    )
    runtime_summary_status = str(runtime_summary.get("status") or "").strip().lower()
    add_check(
        "runtime_summary",
        (
            "pass"
            if runtime_summary_status in {"ready", "active", "idle"}
            else "warn"
            if runtime_summary_status == "degraded"
            else "warn"
        ),
        str(runtime_summary.get("summary") or "Runtime summary is unavailable."),
        runtime_status=runtime_summary_status or "unavailable",
    )

    statuses = {item["status"] for item in checks}
    overall_status = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    return {
        "generated_at": _utc_now_iso(),
        "overall_status": overall_status,
        "environment_preflight": environment_preflight,
        "runtime_summary": runtime_summary,
        "checks": checks,
    }


@router.get("/backup/download")
async def download_system_backup():
    return await download_workspace()


@router.post("/backup/restore", response_model=dict[str, object])
async def restore_system_backup(file: UploadFile = File(...)) -> dict[str, object]:
    return await upload_workspace(file)
