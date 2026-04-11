# -*- coding: utf-8 -*-
from __future__ import annotations

from .runtime_center_shared_ops import *  # noqa: F401,F403
from .runtime_center_mutation_helpers import (
    _runtime_operator_guard_key,
    _runtime_operator_reentry_guard,
)
from .runtime_center_request_models import (
    SharedOperatorAbortClearRequest,
    SharedOperatorAbortRequest,
)


@router.get("/conversations/{conversation_id}", response_model=RuntimeConversationPayload)
async def get_runtime_conversation(
    conversation_id: str,
    request: Request,
    response: Response,
    optional_meta: str | None = None,
) -> RuntimeConversationPayload:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    facade = _get_runtime_conversation_facade(request)
    requested_optional_meta = {
        item.strip()
        for item in str(optional_meta or "").split(",")
        if item.strip()
    }
    if "all" in requested_optional_meta:
        requested_optional_meta = {"main_brain_commit", "human_assist_task"}
    try:
        return await facade.get_conversation(
            conversation_id,
            optional_meta_keys=requested_optional_meta,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc)) from exc

@router.get("/heartbeat", response_model=dict[str, object])
async def get_runtime_heartbeat(
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    return _serialize_heartbeat_surface(request)


@router.put("/heartbeat", response_model=dict[str, object])
async def update_runtime_heartbeat(
    request: Request,
    response: Response,
    payload: HeartbeatConfig,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    result = await _dispatch_runtime_mutation(
        request,
        capability_ref="system:update_heartbeat_config",
        title="Update runtime heartbeat config",
        payload={
            "heartbeat": payload.model_dump(mode="json", by_alias=True),
            "actor": "copaw-operator",
        },
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {
                "updated": False,
                "result": result,
                "heartbeat": _serialize_heartbeat_surface(request),
            }
        raise HTTPException(400, detail=result.get("error") or "Heartbeat update failed")
    manager = _get_cron_manager(request)
    reschedule = getattr(manager, "reschedule_heartbeat", None)
    if callable(reschedule):
        await reschedule()
    detail = _serialize_heartbeat_surface(request)
    _maybe_publish_runtime_event(
        request,
        topic="heartbeat",
        action="updated",
        payload={
            "route": detail["route"],
            "status": detail["runtime"]["status"],
        },
    )
    return {
        "updated": True,
        "result": result,
        "heartbeat": detail,
    }


@router.post("/heartbeat/run", response_model=dict[str, object])
async def run_runtime_heartbeat(
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    manager = _get_cron_manager(request)
    runner = getattr(manager, "run_heartbeat", None)
    if not callable(runner):
        raise HTTPException(503, detail="Heartbeat runtime is not available")
    with _runtime_operator_reentry_guard(
        request,
        guard_key=_runtime_operator_guard_key("heartbeat", "run"),
        conflict_detail="Heartbeat run is already in progress",
    ):
        result = await runner()
    detail = _serialize_heartbeat_surface(request)
    status = str(result.get("status") or "unknown")
    _maybe_publish_runtime_event(
        request,
        topic="heartbeat",
        action=status,
        payload={
            "route": detail["route"],
            "status": detail["runtime"]["status"],
            "task_id": result.get("task_id"),
        },
    )
    return {
        "started": status == "success",
        "result": result,
        "heartbeat": detail,
    }


@router.get("/schedules", response_model=list[dict[str, object]])
async def list_schedules(
    request: Request,
    response: Response,
    limit: int = 20,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    schedules = await _call_runtime_query_method(
        state_query,
        "list_schedules",
        not_available_detail="Schedule queries are not available",
        limit=limit,
    )
    return schedules if isinstance(schedules, list) else []


@router.get("/schedules/{schedule_id}", response_model=dict[str, object])
async def get_schedule_detail(
    schedule_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    detail = await _call_runtime_query_method(
        state_query,
        "get_schedule_detail",
        not_available_detail="Schedule detail queries are not available",
        schedule_id=schedule_id,
    )
    if detail is None:
        raise HTTPException(404, detail=f"Schedule '{schedule_id}' not found")
    return detail if isinstance(detail, dict) else {"schedule": detail}


@router.post("/schedules", response_model=dict[str, object])
async def create_schedule(
    request: Request,
    response: Response,
    spec: CronJobSpec,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    manager = _get_cron_manager(request)
    existing = await manager.get_job(spec.id)
    if existing is not None:
        raise HTTPException(409, detail=f"Schedule '{spec.id}' already exists")
    result = await _dispatch_runtime_mutation(
        request,
        capability_ref="system:create_schedule",
        title=f"Create schedule '{spec.id}'",
        payload={
            "actor": "copaw-operator",
            "owner_agent_id": "copaw-operator",
            "job": spec.model_dump(mode="json"),
            "disable_main_brain_auto_adjudicate": True,
        },
        fallback_risk="confirm",
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {
                "created": False,
                "result": result,
                "schedule": spec.model_dump(mode="json"),
            }
        raise HTTPException(400, detail=result.get("error") or "Schedule creation failed")
    detail = await _get_schedule_surface(spec.id, request, response)
    return {"created": True, "result": result, "schedule": detail}


@router.put("/schedules/{schedule_id}", response_model=dict[str, object])
async def update_schedule(
    schedule_id: str,
    request: Request,
    response: Response,
    spec: CronJobSpec,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    if spec.id != schedule_id:
        raise HTTPException(400, detail="schedule_id mismatch")
    manager = _get_cron_manager(request)
    existing = await manager.get_job(schedule_id)
    if existing is None:
        raise HTTPException(404, detail=f"Schedule '{schedule_id}' not found")
    result = await _dispatch_runtime_mutation(
        request,
        capability_ref="system:update_schedule",
        title=f"Update schedule '{schedule_id}'",
        payload={
            "actor": "copaw-operator",
            "owner_agent_id": "copaw-operator",
            "schedule_id": schedule_id,
            "job": spec.model_dump(mode="json"),
            "disable_main_brain_auto_adjudicate": True,
        },
        fallback_risk="confirm",
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {
                "updated": False,
                "result": result,
                "schedule": await _get_schedule_surface(schedule_id, request, response),
            }
        raise HTTPException(400, detail=result.get("error") or "Schedule update failed")
    detail = await _get_schedule_surface(schedule_id, request, response)
    return {"updated": True, "result": result, "schedule": detail}


@router.delete("/schedules/{schedule_id}", response_model=dict[str, object])
async def delete_schedule(
    schedule_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    manager = _get_cron_manager(request)
    existing = await manager.get_job(schedule_id)
    if existing is None:
        raise HTTPException(404, detail=f"Schedule '{schedule_id}' not found")
    result = await _dispatch_runtime_mutation(
        request,
        capability_ref="system:delete_schedule",
        title=f"Delete schedule '{schedule_id}'",
        payload={
            "actor": "copaw-operator",
            "owner_agent_id": "copaw-operator",
            "schedule_id": schedule_id,
            "disable_main_brain_auto_adjudicate": True,
        },
        fallback_risk="confirm",
    )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {
                "deleted": False,
                "result": result,
                "schedule_id": schedule_id,
                "route": f"/api/runtime-center/schedules/{schedule_id}",
            }
        raise HTTPException(400, detail=result.get("error") or "Schedule deletion failed")
    return {
        "deleted": True,
        "result": result,
        "schedule_id": schedule_id,
        "route": f"/api/runtime-center/schedules/{schedule_id}",
    }


@router.post("/schedules/{schedule_id}/run", response_model=dict[str, object])
async def run_schedule(
    schedule_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    manager = _get_cron_manager(request)
    if await manager.get_job(schedule_id) is None:
        raise HTTPException(404, detail=f"Schedule '{schedule_id}' not found")
    with _runtime_operator_reentry_guard(
        request,
        guard_key=_runtime_operator_guard_key("schedule", schedule_id, "run"),
        conflict_detail=f"Schedule '{schedule_id}' run is already in progress",
    ):
        result = await _dispatch_runtime_mutation(
            request,
            capability_ref="system:run_schedule",
            title=f"Run schedule '{schedule_id}'",
            payload={
                "actor": "copaw-operator",
                "schedule_id": schedule_id,
            },
        )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {"started": False, "result": result}
        raise HTTPException(400, detail=result.get("error") or "Schedule run failed")
    detail = await _get_schedule_surface(schedule_id, request, response)
    return {"started": True, "result": result, "schedule": detail}


@router.post("/schedules/{schedule_id}/pause", response_model=dict[str, object])
async def pause_schedule(
    schedule_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    manager = _get_cron_manager(request)
    job = await manager.get_job(schedule_id)
    if job is None:
        raise HTTPException(404, detail=f"Schedule '{schedule_id}' not found")
    if getattr(job, "enabled", True) is False:
        detail = await _get_schedule_surface(schedule_id, request, response)
        return {
            "paused": False,
            "noop": True,
            "reason": f"Schedule '{schedule_id}' is already paused",
            "schedule": detail,
        }
    with _runtime_operator_reentry_guard(
        request,
        guard_key=_runtime_operator_guard_key("schedule", schedule_id, "pause"),
        conflict_detail=f"Schedule '{schedule_id}' pause is already in progress",
    ):
        result = await _dispatch_runtime_mutation(
            request,
            capability_ref="system:pause_schedule",
            title=f"Pause schedule '{schedule_id}'",
            payload={
                "actor": "copaw-operator",
                "schedule_id": schedule_id,
            },
        )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {"paused": False, "result": result}
        raise HTTPException(400, detail=result.get("error") or "Schedule pause failed")
    detail = await _get_schedule_surface(schedule_id, request, response)
    return {"paused": True, "result": result, "schedule": detail}


@router.post("/schedules/{schedule_id}/resume", response_model=dict[str, object])
async def resume_schedule(
    schedule_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    manager = _get_cron_manager(request)
    job = await manager.get_job(schedule_id)
    if job is None:
        raise HTTPException(404, detail=f"Schedule '{schedule_id}' not found")
    if getattr(job, "enabled", True) is True:
        detail = await _get_schedule_surface(schedule_id, request, response)
        return {
            "resumed": False,
            "noop": True,
            "reason": f"Schedule '{schedule_id}' is already active",
            "schedule": detail,
        }
    with _runtime_operator_reentry_guard(
        request,
        guard_key=_runtime_operator_guard_key("schedule", schedule_id, "resume"),
        conflict_detail=f"Schedule '{schedule_id}' resume is already in progress",
    ):
        result = await _dispatch_runtime_mutation(
            request,
            capability_ref="system:resume_schedule",
            title=f"Resume schedule '{schedule_id}'",
            payload={
                "actor": "copaw-operator",
                "schedule_id": schedule_id,
            },
        )
    if not result.get("success"):
        if result.get("phase") == "waiting-confirm":
            return {"resumed": False, "result": result}
        raise HTTPException(400, detail=result.get("error") or "Schedule resume failed")
    detail = await _get_schedule_surface(schedule_id, request, response)
    return {"resumed": True, "result": result, "schedule": detail}



@router.get("/evidence", response_model=list[dict[str, object]])
async def list_evidence(
    request: Request,
    response: Response,
    task_id: str | None = None,
    capability_ref: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    """List evidence records, optionally filtered by capability_ref."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    eq = getattr(request.app.state, "evidence_query_service", None)
    if eq is None:
        raise HTTPException(503, detail="Evidence query service is not available")
    normalized_task_id = task_id.strip() if isinstance(task_id, str) and task_id.strip() else None
    normalized_capability_ref = (
        capability_ref.strip()
        if isinstance(capability_ref, str) and capability_ref.strip()
        else None
    )
    if normalized_task_id:
        records = eq.list_by_task(normalized_task_id, limit=limit)
    elif normalized_capability_ref:
        records = eq.list_by_capability_ref(normalized_capability_ref, limit=limit)
    else:
        records = eq.list_recent_records(limit=limit)
    return [eq.serialize_record(r) for r in records]


@router.get("/evidence/stats", response_model=dict[str, object])
async def get_evidence_stats(
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return evidence count distribution by capability_ref."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    eq = getattr(request.app.state, "evidence_query_service", None)
    if eq is None:
        raise HTTPException(503, detail="Evidence query service is not available")
    total = eq.count_records()
    by_capability = eq.count_by_capability_ref()
    return {
        "total": total,
        "by_capability_ref": by_capability,
    }


@router.get("/evidence/{evidence_id}", response_model=dict[str, object])
async def get_evidence_detail(
    evidence_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return a single evidence record with full detail."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    eq = getattr(request.app.state, "evidence_query_service", None)
    if eq is None:
        raise HTTPException(503, detail="Evidence query service is not available")
    record = eq.get_record(evidence_id)
    if record is None:
        raise HTTPException(404, detail=f"Evidence '{evidence_id}' not found")
    return eq.serialize_record(record)


# ── Environment endpoints ──────────────────────────────────────────


def _runtime_surface_payload(
    value: object | None,
    *,
    not_serializable_detail: str,
) -> dict[str, object] | None:
    payload = _model_dump_or_dict(value)
    if payload is not None:
        return payload
    if value is None:
        return None
    raise HTTPException(500, detail=not_serializable_detail)


_RUNTIME_SURFACE_FORMAL_KEYS = {
    "recovery",
    "host_contract",
    "seat_runtime",
    "host_companion_session",
    "browser_site_contract",
    "desktop_app_contract",
    "cooperative_adapter_availability",
    "workspace_graph",
    "host_twin",
    "host_twin_summary",
    "host_event_summary",
    "host_events",
}
_RUNTIME_SURFACE_HEAVY_KEYS = {
    "sessions",
    "observations",
    "replays",
    "artifacts",
    "environment",
}


def _runtime_surface_has_formal_projection(payload: dict[str, object]) -> bool:
    return any(key in payload for key in _RUNTIME_SURFACE_FORMAL_KEYS)


def _runtime_surface_list_item_payload(
    payload: dict[str, object],
    *,
    detail_getter,
    not_serializable_detail: str,
) -> dict[str, object]:
    if _runtime_surface_has_formal_projection(payload):
        return payload
    if not callable(detail_getter):
        return payload
    item_id = payload.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        return payload
    detail_payload = _runtime_surface_payload(
        detail_getter(item_id),
        not_serializable_detail=not_serializable_detail,
    )
    if detail_payload is None:
        return payload
    summary_payload = dict(detail_payload)
    for key in _RUNTIME_SURFACE_HEAVY_KEYS:
        summary_payload.pop(key, None)
    return summary_payload


def _runtime_surface_payload_list(
    values: list[object],
    *,
    not_serializable_detail: str,
    detail_getter=None,
) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for value in values:
        payload = _runtime_surface_payload(
            value,
            not_serializable_detail=not_serializable_detail,
        )
        if payload is not None:
            payload = _runtime_surface_list_item_payload(
                payload,
                detail_getter=detail_getter,
                not_serializable_detail=not_serializable_detail,
            )
            payloads.append(payload)
    return payloads


@router.get("/environments", response_model=list[dict[str, object]])
async def list_environments(
    request: Request,
    response: Response,
    kind: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    """List active environments collected from evidence."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    mounts = service.list_environments(kind=kind, limit=limit)
    detail_getter = getattr(service, "get_environment_detail", None)
    return _runtime_surface_payload_list(
        list(mounts),
        not_serializable_detail="Environment payload is not serializable",
        detail_getter=detail_getter if callable(detail_getter) else None,
    )


@router.get("/environments/summary", response_model=dict[str, object])
async def get_environment_summary(
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return environment statistics by kind."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    summary = service.summarize()
    return summary.model_dump(mode="json")


@router.get("/environments/{env_id}", response_model=dict[str, object])
async def get_environment_detail(
    env_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return a single environment mount detail."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    detail_getter = getattr(service, "get_environment_detail", None)
    if callable(detail_getter):
        detail_payload = _runtime_surface_payload(
            detail_getter(env_id),
            not_serializable_detail="Environment detail payload is not serializable",
        )
        if detail_payload is not None:
            return detail_payload
    mount = service.get_environment(env_id)
    if mount is None:
        raise HTTPException(404, detail=f"Environment '{env_id}' not found")
    mount_payload = _runtime_surface_payload(
        mount,
        not_serializable_detail="Environment payload is not serializable",
    )
    if mount_payload is None:
        raise HTTPException(404, detail=f"Environment '{env_id}' not found")
    return mount_payload


@router.get("/sessions", response_model=list[dict[str, object]])
async def list_sessions(
    request: Request,
    response: Response,
    channel: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    """List active session mounts."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    sessions = service.list_sessions(
        channel=channel,
        user_id=user_id,
        status=status,
        limit=limit,
    )
    detail_getter = getattr(service, "get_session_detail", None)
    return _runtime_surface_payload_list(
        list(sessions),
        not_serializable_detail="Session payload is not serializable",
        detail_getter=detail_getter if callable(detail_getter) else None,
    )


@router.get("/sessions/{session_mount_id}", response_model=dict[str, object])
async def get_session_detail(
    session_mount_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return a single session mount detail."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    detail_getter = getattr(service, "get_session_detail", None)
    if callable(detail_getter):
        detail_payload = _runtime_surface_payload(
            detail_getter(session_mount_id),
            not_serializable_detail="Session detail payload is not serializable",
        )
        if detail_payload is not None:
            return detail_payload
    session = service.get_session(session_mount_id)
    if session is None:
        raise HTTPException(
            404,
            detail=f"Session '{session_mount_id}' not found",
        )
    session_payload = _runtime_surface_payload(
        session,
        not_serializable_detail="Session payload is not serializable",
    )
    if session_payload is None:
        raise HTTPException(
            404,
            detail=f"Session '{session_mount_id}' not found",
        )
    return session_payload


@router.post("/sessions/{session_mount_id}/lease/force-release", response_model=dict[str, object])
async def force_release_session_lease(
    session_mount_id: str,
    request: Request,
    response: Response,
    payload: SessionForceReleaseRequest | None = None,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    session = service.force_release_session_lease(
        session_mount_id,
        reason=(
            payload.reason
            if payload is not None
            else "forced release from runtime center"
        ),
    )
    if session is None:
        raise HTTPException(404, detail=f"Session '{session_mount_id}' not found")
    session_payload = _runtime_surface_payload(
        session,
        not_serializable_detail="Session payload is not serializable",
    )
    if session_payload is None:
        raise HTTPException(404, detail=f"Session '{session_mount_id}' not found")
    return session_payload


@router.post("/sessions/{session_mount_id}/operator-abort", response_model=dict[str, object])
async def request_shared_operator_abort(
    session_mount_id: str,
    request: Request,
    response: Response,
    payload: SharedOperatorAbortRequest,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    try:
        session = service.set_shared_operator_abort_state(
            session_mount_id=session_mount_id,
            channel=payload.channel,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    return _bridge_session_payload_or_404(session, session_mount_id)


@router.post(
    "/sessions/{session_mount_id}/operator-abort/clear",
    response_model=dict[str, object],
)
async def clear_shared_operator_abort(
    session_mount_id: str,
    request: Request,
    response: Response,
    payload: SharedOperatorAbortClearRequest | None = None,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    try:
        session = service.clear_shared_operator_abort_state(
            session_mount_id=session_mount_id,
            channel=payload.channel if payload is not None else None,
            reason=payload.reason if payload is not None else None,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    return _bridge_session_payload_or_404(session, session_mount_id)


def _bridge_service_method(service: object, method_name: str):
    method = getattr(service, method_name, None)
    if not callable(method):
        raise HTTPException(503, detail="Bridge lifecycle surface is not available")
    return method


def _bridge_session_payload_or_404(session: object | None, session_mount_id: str) -> dict[str, object]:
    session_payload = _runtime_surface_payload(
        session,
        not_serializable_detail="Session payload is not serializable",
    )
    if session_payload is None:
        raise HTTPException(404, detail=f"Session '{session_mount_id}' not found")
    return session_payload


def _bridge_environment_payload_or_404(environment: object | None, environment_id: str) -> dict[str, object]:
    environment_payload = _runtime_surface_payload(
        environment,
        not_serializable_detail="Environment payload is not serializable",
    )
    if environment_payload is None:
        raise HTTPException(404, detail=f"Environment '{environment_id}' not found")
    return environment_payload


@router.post("/sessions/{session_mount_id}/bridge/ack", response_model=dict[str, object])
async def ack_bridge_session_work(
    session_mount_id: str,
    request: Request,
    response: Response,
    payload: BridgeSessionWorkAckRequest,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    try:
        session = _bridge_service_method(service, "ack_bridge_session_work")(
            session_mount_id,
            lease_token=payload.lease_token,
            work_id=payload.work_id,
            bridge_session_id=payload.bridge_session_id,
            ttl_seconds=payload.ttl_seconds,
            handle=payload.handle,
            workspace_trusted=payload.workspace_trusted,
            elevated_auth_state=payload.elevated_auth_state,
            browser_attach_transport_ref=payload.browser_attach_transport_ref,
            browser_attach_status=payload.browser_attach_status,
            browser_attach_session_ref=payload.browser_attach_session_ref,
            browser_attach_scope_ref=payload.browser_attach_scope_ref,
            browser_attach_reconnect_token=payload.browser_attach_reconnect_token,
            preferred_execution_path=payload.preferred_execution_path,
            ui_fallback_mode=payload.ui_fallback_mode,
            adapter_gap_or_blocker=payload.adapter_gap_or_blocker,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    return _bridge_session_payload_or_404(session, session_mount_id)


@router.post("/sessions/{session_mount_id}/bridge/heartbeat", response_model=dict[str, object])
async def heartbeat_bridge_session_work(
    session_mount_id: str,
    request: Request,
    response: Response,
    payload: BridgeSessionWorkHeartbeatRequest,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    try:
        session = _bridge_service_method(service, "heartbeat_bridge_session_work")(
            session_mount_id,
            lease_token=payload.lease_token,
            work_id=payload.work_id,
            ttl_seconds=payload.ttl_seconds,
            handle=payload.handle,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    return _bridge_session_payload_or_404(session, session_mount_id)


@router.post("/sessions/{session_mount_id}/bridge/reconnect", response_model=dict[str, object])
async def reconnect_bridge_session_work(
    session_mount_id: str,
    request: Request,
    response: Response,
    payload: BridgeSessionWorkReconnectRequest,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    try:
        session = _bridge_service_method(service, "reconnect_bridge_session_work")(
            session_mount_id,
            lease_token=payload.lease_token,
            work_id=payload.work_id,
            ttl_seconds=payload.ttl_seconds,
            handle=payload.handle,
            browser_attach_transport_ref=payload.browser_attach_transport_ref,
            browser_attach_status=payload.browser_attach_status,
            browser_attach_session_ref=payload.browser_attach_session_ref,
            browser_attach_scope_ref=payload.browser_attach_scope_ref,
            browser_attach_reconnect_token=payload.browser_attach_reconnect_token,
            preferred_execution_path=payload.preferred_execution_path,
            ui_fallback_mode=payload.ui_fallback_mode,
            adapter_gap_or_blocker=payload.adapter_gap_or_blocker,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    return _bridge_session_payload_or_404(session, session_mount_id)


@router.post("/sessions/{session_mount_id}/bridge/stop", response_model=dict[str, object])
async def stop_bridge_session_work(
    session_mount_id: str,
    request: Request,
    response: Response,
    payload: BridgeSessionWorkStopRequest,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    try:
        session = _bridge_service_method(service, "stop_bridge_session_work")(
            session_mount_id,
            work_id=payload.work_id,
            force=payload.force,
            lease_token=payload.lease_token,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    return _bridge_session_payload_or_404(session, session_mount_id)


@router.post("/sessions/{session_mount_id}/bridge/archive", response_model=dict[str, object])
async def archive_bridge_session(
    session_mount_id: str,
    request: Request,
    response: Response,
    payload: BridgeSessionArchiveRequest | None = None,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    try:
        session = _bridge_service_method(service, "archive_bridge_session")(
            session_mount_id,
            lease_token=payload.lease_token if payload is not None else None,
            reason=payload.reason if payload is not None else None,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    return _bridge_session_payload_or_404(session, session_mount_id)


@router.post(
    "/environments/{environment_id}/bridge/deregister",
    response_model=dict[str, object],
)
async def deregister_bridge_environment(
    environment_id: str,
    request: Request,
    response: Response,
    payload: BridgeEnvironmentDeregisterRequest | None = None,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    try:
        environment = _bridge_service_method(service, "deregister_bridge_environment")(
            environment_id,
            reason=payload.reason if payload is not None else None,
        )
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc).strip("'")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    return _bridge_environment_payload_or_404(environment, environment_id)


@router.get("/observations", response_model=list[dict[str, object]])
async def list_observations(
    request: Request,
    response: Response,
    environment_ref: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    """List observation summaries derived from evidence."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    records = service.list_observations(
        environment_ref=environment_ref,
        limit=limit,
    )
    return [r.model_dump(mode="json") for r in records]


@router.get("/observations/{observation_id}", response_model=dict[str, object])
async def get_observation_detail(
    observation_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return a single observation record."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    record = service.get_observation(observation_id)
    if record is None:
        raise HTTPException(404, detail=f"Observation '{observation_id}' not found")
    return record.model_dump(mode="json")


@router.get("/replays", response_model=list[dict[str, object]])
async def list_replays(
    request: Request,
    response: Response,
    environment_ref: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    """List action replays derived from evidence."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    records = service.list_replays(
        environment_ref=environment_ref,
        limit=limit,
    )
    return [r.model_dump(mode="json") for r in records]


@router.get("/replays/{replay_id}", response_model=dict[str, object])
async def get_replay_detail(
    replay_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return a single replay pointer."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    record = service.get_replay(replay_id)
    if record is None:
        raise HTTPException(404, detail=f"Replay '{replay_id}' not found")
    return record.model_dump(mode="json")


@router.get("/artifacts", response_model=list[dict[str, object]])
async def list_artifacts(
    request: Request,
    response: Response,
    environment_ref: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    """List evidence artifacts derived from evidence."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    records = service.list_artifacts(
        environment_ref=environment_ref,
        limit=limit,
    )
    return [r.model_dump(mode="json") for r in records]


@router.get("/artifacts/{artifact_id}", response_model=dict[str, object])
async def get_artifact_detail(
    artifact_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    """Return a single artifact pointer."""
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_environment_service(request)
    record = service.get_artifact(artifact_id)
    if record is None:
        raise HTTPException(404, detail=f"Artifact '{artifact_id}' not found")
    return record.model_dump(mode="json")
