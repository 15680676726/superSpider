# -*- coding: utf-8 -*-
from __future__ import annotations

from .runtime_center_shared_core import *  # noqa: F401,F403

from agentscope.message import Msg
from agentscope_runtime.adapters.agentscope.stream import adapt_agentscope_message_stream
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentResponse,
    RunStatus,
    SequenceNumberGenerator,
)


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


def _first_non_empty_text(*values: object) -> str | None:
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if normalized:
            return normalized
    return None


def _as_mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    return {}


def _extract_runtime_chat_text(request_payload: AgentRequest) -> str | None:
    input_payload = getattr(request_payload, "input", None)
    if not isinstance(input_payload, list) or not input_payload:
        return None
    last_message = _as_mapping(input_payload[-1])
    if not last_message:
        return None
    content = last_message.get("content")
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for block in content:
        block_payload = _as_mapping(block)
        if block_payload.get("type") != "text":
            continue
        text = _first_non_empty_text(block_payload.get("text"))
        if text:
            parts.append(text)
    if not parts:
        return None
    return "\n".join(parts)


def _resolve_runtime_chat_thread_id(request_payload: AgentRequest) -> str | None:
    return _first_non_empty_text(
        getattr(request_payload, "thread_id", None),
        getattr(request_payload, "control_thread_id", None),
        getattr(request_payload, "session_id", None),
    )


def _string_list(value: object | None) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            normalized.append(text)
    return normalized


def _looks_like_human_assist_submission(
    request_payload: AgentRequest,
    *,
    message_text: str | None,
) -> bool:
    if _string_list(getattr(request_payload, "media_analysis_ids", None)):
        return True
    normalized = str(message_text or "").strip().lower()
    if not normalized:
        return False
    markers = (
        "我完成了",
        "已完成",
        "完成了",
        "完成这个任务",
        "done",
        "finished",
        "completed",
        "uploaded",
        "upload",
        "submitted",
        "submit",
    )
    return any(marker in normalized for marker in markers)


def _human_assist_task_is_submission_open(task: object) -> bool:
    status = str(getattr(task, "status", "") or "").strip().lower()
    return status in {"issued", "in_progress", "submitted", "rejected"}


def _format_human_assist_reward(reward_payload: object) -> str | None:
    if not isinstance(reward_payload, dict):
        return None
    parts: list[str] = []
    for key, value in reward_payload.items():
        if key == "granted" or value in (None, "", False):
            continue
        if isinstance(value, (int, float)):
            parts.append(f"{key} +{value}")
        else:
            parts.append(f"{key}: {value}")
    if not parts:
        return None
    return "，".join(parts)


def _build_human_assist_reply_text(result: object) -> str:
    task = getattr(result, "task", None)
    title = _first_non_empty_text(getattr(task, "title", None)) or "协作任务"
    outcome = str(getattr(result, "outcome", "") or "").strip().lower()
    message = _first_non_empty_text(getattr(result, "message", None))
    reward_text = _format_human_assist_reward(getattr(task, "reward_result", None))
    if outcome == "accepted":
        parts = [
            f"叮，{title} 验收通过。",
            "系统已记录你的提交，准备继续恢复执行。",
        ]
        if reward_text:
            parts.append(f"本次奖励：{reward_text}。")
        return "\n".join(parts)
    if outcome == "need_more_evidence":
        return "\n".join(
            [
                f"叮，{title} 已收到，但暂时还不能通过验收。",
                message or "还缺少可验证的完成证据。",
            ],
        )
    return "\n".join(
        [
            f"叮，{title} 未通过验收。",
            message or "当前提交没有满足验收条件。",
        ],
    )


def _human_assist_event_metadata(result: object) -> dict[str, object]:
    task = getattr(result, "task", None)
    model_dump = getattr(task, "model_dump", None)
    task_payload = model_dump(mode="json") if callable(model_dump) else None
    return {
        "outcome": getattr(result, "outcome", None),
        "resume_queued": bool(getattr(result, "resume_queued", False)),
        "human_assist_task": task_payload,
        "matched_hard_anchors": list(getattr(result, "matched_hard_anchors", []) or []),
        "matched_result_anchors": list(
            getattr(result, "matched_result_anchors", []) or [],
        ),
        "missing_hard_anchors": list(getattr(result, "missing_hard_anchors", []) or []),
        "missing_result_anchors": list(
            getattr(result, "missing_result_anchors", []) or [],
        ),
        "matched_negative_anchors": list(
            getattr(result, "matched_negative_anchors", []) or [],
        ),
    }


async def _stream_human_assist_result(
    *,
    request_payload: AgentRequest,
    result: object,
):
    async def _message_stream():
        yield (
            Msg(
                name="assistant",
                role="assistant",
                content=_build_human_assist_reply_text(result),
                metadata=_human_assist_event_metadata(result),
            ),
            True,
        )

    seq_gen = SequenceNumberGenerator()
    response = AgentResponse(id=request_payload.id)
    response.session_id = getattr(request_payload, "session_id", None)
    yield _encode_sse_event(seq_gen.yield_with_sequence(response))
    yield _encode_sse_event(seq_gen.yield_with_sequence(response.in_progress()))

    async for event in adapt_agentscope_message_stream(source_stream=_message_stream()):
        if event.object == "message" and event.status == RunStatus.Completed:
            response.add_new_message(event)
        yield _encode_sse_event(seq_gen.yield_with_sequence(event))

    yield _encode_sse_event(seq_gen.yield_with_sequence(response.completed()))


async def _maybe_intercept_human_assist_chat_turn(
    *,
    request_payload: AgentRequest,
    request: Request,
) -> StreamingResponse | None:
    service = getattr(request.app.state, "human_assist_task_service", None)
    current_task_getter = getattr(service, "get_current_task", None)
    submit_and_verify = getattr(service, "submit_and_verify", None)
    if not callable(current_task_getter) or not callable(submit_and_verify):
        return None
    chat_thread_id = _resolve_runtime_chat_thread_id(request_payload)
    if chat_thread_id is None:
        return None
    current_task = current_task_getter(chat_thread_id=chat_thread_id)
    if current_task is None or not _human_assist_task_is_submission_open(current_task):
        return None
    message_text = _extract_runtime_chat_text(request_payload)
    if not _looks_like_human_assist_submission(
        request_payload,
        message_text=message_text,
    ):
        return None
    media_analysis_ids = _string_list(getattr(request_payload, "media_analysis_ids", None))
    submission_payload = {
        "chat_thread_id": chat_thread_id,
        "request_id": getattr(request_payload, "id", None),
        "media_analysis_ids": media_analysis_ids,
        "interaction_mode": getattr(request_payload, "interaction_mode", None),
    }
    result = submit_and_verify(
        current_task.id,
        submission_text=message_text,
        submission_evidence_refs=media_analysis_ids,
        submission_payload=submission_payload,
    )
    return StreamingResponse(
        _stream_human_assist_result(
            request_payload=request_payload,
            result=result,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


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
    intercepted = await _maybe_intercept_human_assist_chat_turn(
        request_payload=request_payload,
        request=request,
    )
    if intercepted is not None:
        return intercepted
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


@router.get("/human-assist-tasks", response_model=list[dict[str, object]])
async def list_human_assist_tasks(
    request: Request,
    response: Response,
    chat_thread_id: str | None = None,
    industry_instance_id: str | None = None,
    assignment_id: str | None = None,
    task_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    items = await _call_runtime_query_method(
        state_query,
        "list_human_assist_tasks",
        not_available_detail="Human assist task queries are not available",
        chat_thread_id=chat_thread_id,
        industry_instance_id=industry_instance_id,
        assignment_id=assignment_id,
        task_id=task_id,
        status=status,
        limit=limit,
    )
    return items if isinstance(items, list) else []


@router.get("/human-assist-tasks/current", response_model=dict[str, object])
async def get_current_human_assist_task(
    request: Request,
    response: Response,
    chat_thread_id: str,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    item = await _call_runtime_query_method(
        state_query,
        "get_current_human_assist_task",
        not_available_detail="Human assist current-task queries are not available",
        chat_thread_id=chat_thread_id,
    )
    if item is None:
        raise HTTPException(
            404,
            detail=f"Current human assist task for '{chat_thread_id}' was not found",
        )
    return item if isinstance(item, dict) else {"task": item}


@router.get("/human-assist-tasks/{task_id}", response_model=dict[str, object])
async def get_human_assist_task_detail(
    task_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    detail = await _call_runtime_query_method(
        state_query,
        "get_human_assist_task_detail",
        not_available_detail="Human assist task detail queries are not available",
        task_id=task_id,
    )
    if detail is None:
        raise HTTPException(404, detail=f"Human assist task '{task_id}' not found")
    return detail if isinstance(detail, dict) else {"task": detail}


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
