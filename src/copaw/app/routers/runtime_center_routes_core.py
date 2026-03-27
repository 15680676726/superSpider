# -*- coding: utf-8 -*-
from __future__ import annotations

from .runtime_center_shared_core import *  # noqa: F401,F403


def _merge_runtime_chat_requested_actions(
    request_payload: AgentRequest,
) -> AgentRequest:
    requested_actions = _normalize_requested_actions(
        getattr(request_payload, "requested_actions", None),
    )
    input_payload = getattr(request_payload, "input", None)
    if not isinstance(input_payload, list) or not input_payload:
        if requested_actions:
            request_payload.requested_actions = requested_actions
        return request_payload
    last_message = input_payload[-1]
    if not isinstance(last_message, dict):
        if requested_actions:
            request_payload.requested_actions = requested_actions
        return request_payload
    content = last_message.get("content")
    if not isinstance(content, list):
        if requested_actions:
            request_payload.requested_actions = requested_actions
        return request_payload
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        extracted_actions, stripped_text = _extract_leading_chat_action_hints(
            block.get("text"),
        )
        for action in extracted_actions:
            if action not in requested_actions:
                requested_actions.append(action)
        if stripped_text:
            block["text"] = stripped_text
        break
    if requested_actions:
        request_payload.requested_actions = requested_actions
    return request_payload


def _set_runtime_chat_interaction_mode(
    request_payload: AgentRequest,
    interaction_mode: str,
) -> AgentRequest:
    try:
        object.__setattr__(request_payload, "interaction_mode", interaction_mode)
        return request_payload
    except Exception:
        pass
    try:
        setattr(request_payload, "interaction_mode", interaction_mode)
    except Exception:
        pass
    return request_payload


def _resolve_runtime_chat_interaction_mode(
    request_payload: AgentRequest,
    *,
    default_mode: str,
) -> str:
    value = getattr(request_payload, "interaction_mode", None)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"auto", "chat", "orchestrate"}:
            return normalized
    return default_mode


@router.get("/governance/status", response_model=dict[str, object])
async def get_governance_status(
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_governance_service(request)
    return service.get_status().model_dump(mode="json")


@router.get(
    "/governance/capability-optimizations",
    response_model=PredictionCapabilityOptimizationOverview,
)
async def get_governance_capability_optimizations(
    request: Request,
    response: Response,
    industry_instance_id: str | None = None,
    owner_scope: str | None = None,
    limit: int = 12,
    history_limit: int = 8,
    window_days: int = 14,
) -> PredictionCapabilityOptimizationOverview:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_prediction_service(request)
    return service.get_runtime_capability_optimization_overview(
        industry_instance_id=industry_instance_id,
        owner_scope=owner_scope,
        limit=limit,
        history_limit=history_limit,
        window_days=window_days,
    )


@router.post("/governance/emergency-stop", response_model=dict[str, object])
async def activate_emergency_stop(
    payload: GovernanceEmergencyStopRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_governance_service(request)
    status = await service.emergency_stop(actor=payload.actor, reason=payload.reason)
    return status.model_dump(mode="json")


@router.post("/governance/resume", response_model=dict[str, object])
async def resume_governed_runtime(
    payload: GovernanceResumeRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_governance_service(request)
    status = await service.resume(actor=payload.actor, reason=payload.reason)
    return status.model_dump(mode="json")


@router.post("/governance/decisions/approve", response_model=dict[str, object])
async def approve_decisions_batch(
    payload: GovernanceDecisionBatchRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_governance_service(request)
    result = await service.batch_decisions(
        decision_ids=payload.decision_ids,
        action="approve",
        actor=payload.actor,
        resolution=payload.resolution,
        execute=payload.execute,
    )
    return result.model_dump(mode="json")


@router.post("/governance/decisions/reject", response_model=dict[str, object])
async def reject_decisions_batch(
    payload: GovernanceDecisionBatchRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_governance_service(request)
    result = await service.batch_decisions(
        decision_ids=payload.decision_ids,
        action="reject",
        actor=payload.actor,
        resolution=payload.resolution,
        execute=payload.execute,
    )
    return result.model_dump(mode="json")


@router.post("/governance/patches/approve", response_model=dict[str, object])
async def approve_patches_batch(
    payload: GovernancePatchBatchRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_governance_service(request)
    return service.batch_patches(
        patch_ids=payload.patch_ids,
        action="approve",
        actor=payload.actor,
    ).model_dump(mode="json")


@router.post("/governance/patches/reject", response_model=dict[str, object])
async def reject_patches_batch(
    payload: GovernancePatchBatchRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_governance_service(request)
    return service.batch_patches(
        patch_ids=payload.patch_ids,
        action="reject",
        actor=payload.actor,
    ).model_dump(mode="json")


@router.post("/governance/patches/apply", response_model=dict[str, object])
async def apply_patches_batch(
    payload: GovernancePatchBatchRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_governance_service(request)
    return service.batch_patches(
        patch_ids=payload.patch_ids,
        action="apply",
        actor=payload.actor,
    ).model_dump(mode="json")


@router.post("/governance/patches/rollback", response_model=dict[str, object])
async def rollback_patches_batch(
    payload: GovernancePatchBatchRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_governance_service(request)
    return service.batch_patches(
        patch_ids=payload.patch_ids,
        action="rollback",
        actor=payload.actor,
    ).model_dump(mode="json")


@router.get("/recovery/latest", response_model=dict[str, object])
async def get_latest_recovery_report(
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    summary = getattr(request.app.state, "startup_recovery_summary", None)
    if summary is None:
        raise HTTPException(404, detail="Startup recovery summary is not available")
    model_dump = getattr(summary, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    if isinstance(summary, dict):
        return dict(summary)
    return {"summary": str(summary)}


async def _stream_runtime_chat_events(
    *,
    turn_executor: object,
    request_payload: AgentRequest,
):
    stream_request = getattr(turn_executor, "stream_request", None)
    if not callable(stream_request):
        raise RuntimeError("Kernel turn executor does not support streaming chat execution")
    async for event in stream_request(request_payload):
        yield _encode_sse_event(event)


async def _run_runtime_chat_turn(
    *,
    request_payload: AgentRequest,
    request: Request,
    default_mode: str,
) -> StreamingResponse:
    turn_executor = _get_turn_executor(request)
    request_payload = _merge_runtime_chat_requested_actions(request_payload)
    interaction_mode = _resolve_runtime_chat_interaction_mode(
        request_payload,
        default_mode=default_mode,
    )
    request_payload = _set_runtime_chat_interaction_mode(
        request_payload,
        interaction_mode,
    )
    request_payload, _, _ = await enrich_agent_request_with_media(
        request_payload,
        app_state=request.app.state,
    )
    request_payload = _set_runtime_chat_interaction_mode(
        request_payload,
        interaction_mode,
    )
    return StreamingResponse(
        _stream_runtime_chat_events(
            turn_executor=turn_executor,
            request_payload=request_payload,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/chat/run")
async def run_runtime_chat_turn(
    request_payload: AgentRequest,
    request: Request,
) -> StreamingResponse:
    return await _run_runtime_chat_turn(
        request_payload=request_payload,
        request=request,
        default_mode="auto",
    )


@router.get("/tasks", response_model=list[dict[str, object]])
async def list_tasks(
    request: Request,
    response: Response,
    limit: int = 20,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    tasks = await _call_runtime_query_method(
        state_query,
        "list_tasks",
        "get_tasks",
        "list_runtime_tasks",
        not_available_detail="Task queries are not available",
        limit=limit,
    )
    return tasks if isinstance(tasks, list) else []


@router.get("/tasks/{task_id}", response_model=dict[str, object])
async def get_task_detail(
    task_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    detail = await _call_runtime_query_method(
        state_query,
        "get_task_detail",
        "get_task",
        not_available_detail="Task detail queries are not available",
        task_id=task_id,
    )
    if detail is None:
        raise HTTPException(404, detail=f"Task '{task_id}' not found")
    return detail if isinstance(detail, dict) else {"task": detail}


@router.get("/tasks/{task_id}/review", response_model=dict[str, object])
async def get_task_review(
    task_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    detail = await _call_runtime_query_method(
        state_query,
        "get_task_review",
        not_available_detail="Task review queries are not available",
        task_id=task_id,
    )
    if detail is None:
        raise HTTPException(404, detail=f"Task '{task_id}' not found")
    return detail if isinstance(detail, dict) else {"review": detail}


@router.get("/work-contexts", response_model=list[dict[str, object]])
async def list_work_contexts(
    request: Request,
    response: Response,
    limit: int = 20,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    items = await _call_runtime_query_method(
        state_query,
        "list_work_contexts",
        not_available_detail="Work context queries are not available",
        limit=limit,
    )
    return items if isinstance(items, list) else []


@router.get("/work-contexts/{context_id}", response_model=dict[str, object])
async def get_work_context_detail(
    context_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    detail = await _call_runtime_query_method(
        state_query,
        "get_work_context_detail",
        not_available_detail="Work context detail queries are not available",
        context_id=context_id,
    )
    if detail is None:
        raise HTTPException(404, detail=f"Work context '{context_id}' not found")
    return detail if isinstance(detail, dict) else {"work_context": detail}


@router.get("/goals/{goal_id}", response_model=dict[str, object])
async def get_goal_detail(
    goal_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    detail = await _call_runtime_query_method(
        state_query,
        "get_goal_detail",
        not_available_detail="Goal detail queries are not available",
        goal_id=goal_id,
    )
    if detail is None:
        raise HTTPException(404, detail=f"Goal '{goal_id}' not found")
    return detail if isinstance(detail, dict) else {"goal": detail}

