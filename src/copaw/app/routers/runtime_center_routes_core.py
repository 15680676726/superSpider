# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect

from .runtime_center_shared_core import *  # noqa: F401,F403
from ..runtime_center.models import RuntimeCenterAppStateView
from ..runtime_center.overview_cards import (
    build_runtime_capability_governance_projection,
)
from ..runtime_center.recovery_projection import project_latest_recovery_summary
from ..runtime_chat_stream_events import stream_runtime_chat_events

from agentscope.message import Msg
from agentscope_runtime.adapters.agentscope.stream import adapt_agentscope_message_stream
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentResponse,
    RunStatus,
    SequenceNumberGenerator,
)
from starlette.background import BackgroundTask

from ...kernel.main_brain_turn_result import MainBrainCommitState

_HUMAN_ASSIST_RESUME_MAX_ATTEMPTS = 2
_HUMAN_ASSIST_RESUME_RETRY_DELAY_SECONDS = 0.15


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


def _merge_runtime_decision_ids(*values: object) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        raw_items = value if isinstance(value, list) else [value]
        for item in raw_items:
            text = _first_non_empty_text(item)
            if text is None:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(text)
    return normalized


def _persist_runtime_center_main_brain_commit_resolution(
    *,
    request: Request,
    payload: GovernanceDecisionBatchRequest,
    action: str,
    result_payload: dict[str, object],
) -> None:
    session_backend = getattr(request.app.state, "session_backend", None)
    loader = getattr(session_backend, "load_session_snapshot", None)
    saver = getattr(session_backend, "save_session_snapshot", None)
    if not callable(loader) or not callable(saver):
        return
    session_id = _first_non_empty_text(payload.session_id, payload.control_thread_id)
    user_id = _first_non_empty_text(payload.agent_id, payload.user_id)
    if session_id is None or user_id is None:
        return
    snapshot = loader(
        session_id=session_id,
        user_id=user_id,
        allow_not_exist=True,
    )
    if not isinstance(snapshot, dict):
        return
    main_brain = _as_mapping(snapshot.get("main_brain"))
    commit_payload = _as_mapping(main_brain.get("phase2_commit"))
    if not commit_payload:
        return
    current_state = MainBrainCommitState.model_validate(commit_payload)
    results = result_payload.get("results")
    errors = result_payload.get("errors")
    if action == "approve" and not bool(result_payload.get("succeeded")):
        return
    if action == "reject" and not bool(result_payload.get("succeeded")):
        return
    first_result = _as_mapping(results[0]) if isinstance(results, list) and results else {}
    first_error = _as_mapping(errors[0]) if isinstance(errors, list) and errors else {}
    nested_payload = _as_mapping(current_state.payload)
    decision_ids = _merge_runtime_decision_ids(
        nested_payload.get("decision_ids"),
        nested_payload.get("decision_id"),
        payload.decision_ids,
    )
    if decision_ids:
        nested_payload["decision_ids"] = decision_ids
        if "decision_id" not in nested_payload and len(decision_ids) == 1:
            nested_payload["decision_id"] = decision_ids[0]
    record_id = _first_non_empty_text(
        first_result.get("record_id"),
        _as_mapping(first_result.get("output")).get("record_id"),
        current_state.record_id,
    )
    message = _first_non_empty_text(
        payload.resolution,
        first_result.get("summary"),
        first_error.get("error"),
    )
    updated_state = current_state.model_copy(
        update={
            "status": (
                "committed"
                if action == "approve" and payload.execute is not False
                else ("commit_deferred" if action == "approve" else "commit_failed")
            ),
            "reason": (
                "approved"
                if action == "approve" and payload.execute is False
                else ("governance_denied" if action == "reject" else None)
            ),
            "message": message,
            "record_id": record_id,
            "control_thread_id": _first_non_empty_text(
                payload.control_thread_id,
                current_state.control_thread_id,
                session_id,
            ),
            "session_id": _first_non_empty_text(
                payload.session_id,
                current_state.session_id,
                session_id,
            ),
            "work_context_id": _first_non_empty_text(
                payload.work_context_id,
                current_state.work_context_id,
            ),
            "payload": nested_payload or current_state.payload,
        },
    )
    main_brain["phase2_commit"] = updated_state.model_dump(mode="json")
    snapshot["main_brain"] = main_brain
    saver(
        session_id=session_id,
        user_id=user_id,
        payload=snapshot,
        source_ref="state:/main-brain-chat-session",
    )


def _looks_like_human_assist_submission(
    request_payload: AgentRequest,
    *,
    message_text: str | None,
    task: object | None = None,
) -> bool:
    if _string_list(getattr(request_payload, "media_analysis_ids", None)):
        return True
    requested_actions = _normalize_requested_actions(
        getattr(request_payload, "requested_actions", None),
    )
    if "submit_human_assist" in requested_actions:
        return True
    normalized_text = str(message_text or "").strip().lower()
    if not normalized_text:
        return False
    task_payload = _as_mapping(task)
    submission_mode = _first_non_empty_text(task_payload.get("submission_mode"))
    if submission_mode not in {None, "chat-message"}:
        return False
    acceptance_spec = _as_mapping(task_payload.get("acceptance_spec"))
    anchors = [
        *(
            anchor.lower()
            for anchor in _string_list(acceptance_spec.get("hard_anchors"))
        ),
        *(
            anchor.lower()
            for anchor in _string_list(acceptance_spec.get("result_anchors"))
        ),
    ]
    if any(anchor and anchor in normalized_text for anchor in anchors):
        return True
    completion_markers = (
        "i finished",
        "i'm done",
        "im done",
        "it is done",
        "uploaded",
        "submitted",
        "cleared",
        "已完成",
        "完成了",
        "搞定了",
        "搞定",
        "已上传",
        "上传了",
        "已提交",
        "提交了",
        "已清除",
        "清除了",
    )
    return any(marker in normalized_text for marker in completion_markers)


def _human_assist_task_is_submission_open(task: object) -> bool:
    status = str(getattr(task, "status", "") or "").strip().lower()
    return status in {
        "issued",
        "in_progress",
        "submitted",
        "need_more_evidence",
        "rejected",
    }


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
    task_status = str(getattr(task, "status", "") or "").strip().lower()
    verification_payload = _as_mapping(getattr(task, "verification_payload", None))
    resume_payload = _as_mapping(verification_payload.get("resume"))
    if outcome == "accepted":
        if task_status == "handoff_blocked":
            parts = [
                f"{title} 已通过。",
                _first_non_empty_text(
                    resume_payload.get("reason"),
                    "但系统暂时没接上后续流程。",
                )
                or "但系统暂时没接上后续流程。",
            ]
        elif task_status == "closed":
            parts = [
                f"{title} 已通过。",
                _first_non_empty_text(
                    resume_payload.get("summary"),
                    "系统已继续处理。",
                )
                or "系统已继续处理。",
            ]
        else:
            parts = [
                f"{title} 已通过。",
                "系统继续往下做。",
            ]
        if reward_text:
            parts.append(f"奖励：{reward_text}")
        return "\n".join(parts)
    if outcome == "need_more_evidence":
        return "\n".join(
            [
                f"{title} 还没过。",
                message or "还差证明材料。",
            ],
        )
    return "\n".join(
        [
            f"{title} 没通过。",
            message or "这次提交不符合要求。",
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


def _human_assist_resume_payload(result: object) -> dict[str, object]:
    return _as_mapping(result)


def _human_assist_resume_succeeded(result: object) -> bool:
    payload = _human_assist_resume_payload(result)
    if "resumed" in payload:
        return bool(payload.get("resumed"))
    return bool(result)


def _human_assist_resume_close_summary(result: object) -> str:
    del result
    return "系统已继续处理。"


def _human_assist_resume_block_reason(
    result: object | None = None,
    *,
    fallback: str = "系统暂时没接上后续流程。",
) -> str:
    del result
    return fallback


def _load_human_assist_task_snapshot(
    service: object,
    *,
    task_id: str,
    fallback_task: object,
) -> object:
    get_task = getattr(service, "get_task", None)
    if not callable(get_task):
        return fallback_task
    latest = get_task(task_id)
    if latest is None:
        return fallback_task
    return latest


def _invoke_human_assist_resume(
    app: object,
    *,
    task: object,
) -> object:
    query_execution_service = getattr(getattr(app, "state", None), "query_execution_service", None)
    resume = getattr(query_execution_service, "resume_human_assist_task", None)
    if not callable(resume):
        raise RuntimeError("human assist resume service is unavailable")
    return resume(task=task)


async def _finalize_human_assist_resume(
    *,
    app: object,
    service: object,
    task_id: str,
    task_snapshot: object,
    resume_result: object,
) -> None:
    mark_closed = getattr(service, "mark_closed", None)
    mark_handoff_blocked = getattr(service, "mark_handoff_blocked", None)
    latest_result = resume_result
    latest_payload = None
    for attempt in range(_HUMAN_ASSIST_RESUME_MAX_ATTEMPTS):
        try:
            latest_payload = (
                await latest_result if inspect.isawaitable(latest_result) else latest_result
            )
        except Exception:
            latest_payload = None
        else:
            if _human_assist_resume_succeeded(latest_payload):
                if callable(mark_closed):
                    mark_closed(
                        task_id,
                        summary=_human_assist_resume_close_summary(latest_payload),
                        resume_payload=_human_assist_resume_payload(latest_payload),
                    )
                return
        if attempt + 1 >= _HUMAN_ASSIST_RESUME_MAX_ATTEMPTS:
            break
        await asyncio.sleep(_HUMAN_ASSIST_RESUME_RETRY_DELAY_SECONDS)
        current_task = _load_human_assist_task_snapshot(
            service,
            task_id=task_id,
            fallback_task=task_snapshot,
        )
        try:
            latest_result = _invoke_human_assist_resume(
                app,
                task=current_task,
            )
        except Exception:
            latest_result = None
    if callable(mark_handoff_blocked):
        mark_handoff_blocked(
            task_id,
            reason=_human_assist_resume_block_reason(latest_payload),
            resume_payload=_human_assist_resume_payload(latest_payload),
        )


def _resume_human_assist_task(
    request: Request,
    *,
    task: object,
    service: object,
) -> tuple[object, bool, BackgroundTask | None]:
    task_id = _first_non_empty_text(getattr(task, "id", None))
    mark_resume_queued = getattr(service, "mark_resume_queued", None)
    mark_closed = getattr(service, "mark_closed", None)
    mark_handoff_blocked = getattr(service, "mark_handoff_blocked", None)
    if task_id is None:
        return task, False, None
    current_task = task
    latest_result = None
    for attempt in range(_HUMAN_ASSIST_RESUME_MAX_ATTEMPTS):
        try:
            latest_result = _invoke_human_assist_resume(
                request.app,
                task=current_task,
            )
        except Exception:
            latest_result = None
        else:
            if inspect.isawaitable(latest_result):
                queued_task = current_task
                if callable(mark_resume_queued):
                    queued_task = mark_resume_queued(task_id)
                return (
                    queued_task,
                    True,
                    BackgroundTask(
                        _finalize_human_assist_resume,
                        app=request.app,
                        service=service,
                        task_id=task_id,
                        task_snapshot=queued_task,
                        resume_result=latest_result,
                    ),
                )
            if _human_assist_resume_succeeded(latest_result):
                if callable(mark_closed):
                    return (
                        mark_closed(
                            task_id,
                            summary=_human_assist_resume_close_summary(latest_result),
                            resume_payload=_human_assist_resume_payload(latest_result),
                        ),
                        False,
                        None,
                    )
                return current_task, False, None
        if attempt + 1 >= _HUMAN_ASSIST_RESUME_MAX_ATTEMPTS:
            break
        current_task = _load_human_assist_task_snapshot(
            service,
            task_id=task_id,
            fallback_task=current_task,
        )
    if callable(mark_handoff_blocked):
        return (
            mark_handoff_blocked(
                task_id,
                reason=_human_assist_resume_block_reason(latest_result),
                resume_payload=_human_assist_resume_payload(latest_result),
            ),
            False,
            None,
        )
    return current_task, False, None


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
        task=current_task,
    ):
        return None
    media_analysis_ids = _string_list(getattr(request_payload, "media_analysis_ids", None))
    requested_actions = _normalize_requested_actions(
        getattr(request_payload, "requested_actions", None),
    )
    submission_payload = {
        "chat_thread_id": chat_thread_id,
        "request_id": getattr(request_payload, "id", None),
        "session_id": getattr(request_payload, "session_id", None),
        "control_thread_id": getattr(request_payload, "control_thread_id", None),
        "environment_ref": getattr(request_payload, "environment_ref", None),
        "work_context_id": getattr(request_payload, "work_context_id", None),
        "user_id": getattr(request_payload, "user_id", None),
        "channel": getattr(request_payload, "channel", None),
        "industry_instance_id": getattr(request_payload, "industry_instance_id", None),
        "industry_role_id": getattr(request_payload, "industry_role_id", None),
        "industry_role_name": getattr(request_payload, "industry_role_name", None),
        "industry_label": getattr(request_payload, "industry_label", None),
        "entry_source": getattr(request_payload, "entry_source", None),
        "owner_scope": getattr(request_payload, "owner_scope", None),
        "session_kind": getattr(request_payload, "session_kind", None),
        "main_brain_runtime": (
            getattr(request_payload, "_copaw_main_brain_runtime_context", None)
            or getattr(request_payload, "main_brain_runtime", None)
        ),
        "media_analysis_ids": media_analysis_ids,
        "requested_actions": requested_actions,
        "interaction_mode": getattr(request_payload, "interaction_mode", None),
    }
    result = submit_and_verify(
        current_task.id,
        submission_text=message_text,
        submission_evidence_refs=media_analysis_ids,
        submission_payload=submission_payload,
    )
    background_task = None
    if getattr(result, "outcome", None) == "accepted":
        updated_task, resume_queued, background_task = _resume_human_assist_task(
            request,
            task=getattr(result, "task", None),
            service=service,
        )
        result.task = updated_task
        result.resume_queued = resume_queued
    return StreamingResponse(
        _stream_human_assist_result(
            request_payload=request_payload,
            result=result,
        ),
        media_type="text/event-stream",
        background=background_task,
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def _runtime_center_list_query(
    *,
    request: Request,
    response: Response,
    query_methods: tuple[str, ...],
    not_available_detail: str,
    **query_kwargs: object,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    items = await _call_runtime_query_method(
        state_query,
        *query_methods,
        not_available_detail=not_available_detail,
        **query_kwargs,
    )
    return items if isinstance(items, list) else []


async def _runtime_center_detail_query(
    *,
    request: Request,
    response: Response,
    query_methods: tuple[str, ...],
    not_available_detail: str,
    not_found_detail: str,
    payload_key: str,
    **query_kwargs: object,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    state_query = _get_state_query_service(request)
    detail = await _call_runtime_query_method(
        state_query,
        *query_methods,
        not_available_detail=not_available_detail,
        **query_kwargs,
    )
    if detail is None:
        raise HTTPException(404, detail=not_found_detail)
    return detail if isinstance(detail, dict) else {payload_key: detail}


@router.get("/governance/status", response_model=dict[str, object])
async def get_governance_status(
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_governance_service(request)
    payload = service.get_status().model_dump(mode="json")
    payload["capability_governance"] = await build_runtime_capability_governance_projection(
        request.app.state,
    )
    return payload


@router.get("/capabilities/candidates", response_model=list[dict[str, object]])
async def list_runtime_center_capability_candidates(
    request: Request,
    response: Response,
    limit: int = 20,
) -> list[dict[str, object]]:
    return await _runtime_center_list_query(
        request=request,
        response=response,
        query_methods=("list_capability_candidates",),
        not_available_detail="Capability candidate view is not available.",
        limit=limit,
    )


@router.get("/capabilities/trials", response_model=list[dict[str, object]])
async def list_runtime_center_capability_trials(
    request: Request,
    response: Response,
    candidate_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    return await _runtime_center_list_query(
        request=request,
        response=response,
        query_methods=("list_capability_trials",),
        not_available_detail="Capability trial view is not available.",
        candidate_id=candidate_id,
        limit=limit,
    )


@router.get("/capabilities/lifecycle-decisions", response_model=list[dict[str, object]])
async def list_runtime_center_capability_lifecycle_decisions(
    request: Request,
    response: Response,
    candidate_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    return await _runtime_center_list_query(
        request=request,
        response=response,
        query_methods=("list_capability_lifecycle_decisions",),
        not_available_detail="Capability lifecycle decision view is not available.",
        candidate_id=candidate_id,
        limit=limit,
    )


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
    result_payload = result.model_dump(mode="json")
    _persist_runtime_center_main_brain_commit_resolution(
        request=request,
        payload=payload,
        action="approve",
        result_payload=result_payload,
    )
    return result_payload


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
    result_payload = result.model_dump(mode="json")
    _persist_runtime_center_main_brain_commit_resolution(
        request=request,
        payload=payload,
        action="reject",
        result_payload=result_payload,
    )
    return result_payload


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
    runtime_state = RuntimeCenterAppStateView.from_object(request.app.state)
    summary, source = runtime_state.resolve_recovery_summary()
    if summary is None:
        raise HTTPException(404, detail="Startup recovery summary is not available")
    return project_latest_recovery_summary(summary, source=source)


async def _stream_runtime_chat_events(
    *,
    turn_executor: object,
    request_payload: AgentRequest,
):
    async for encoded in stream_runtime_chat_events(
        turn_executor=turn_executor,
        request_payload=request_payload,
    ):
        yield encoded


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
    return await _runtime_center_list_query(
        request=request,
        response=response,
        query_methods=("list_human_assist_tasks",),
        not_available_detail="Human assist task queries are not available",
        chat_thread_id=chat_thread_id,
        industry_instance_id=industry_instance_id,
        assignment_id=assignment_id,
        task_id=task_id,
        status=status,
        limit=limit,
    )


@router.get("/human-assist-tasks/current", response_model=dict[str, object])
async def get_current_human_assist_task(
    request: Request,
    response: Response,
    chat_thread_id: str,
) -> dict[str, object]:
    return await _runtime_center_detail_query(
        request=request,
        response=response,
        query_methods=("get_current_human_assist_task",),
        not_available_detail="Human assist current-task queries are not available",
        not_found_detail=(
            f"Current human assist task for '{chat_thread_id}' was not found"
        ),
        payload_key="task",
        chat_thread_id=chat_thread_id,
    )


@router.get("/human-assist-tasks/{task_id}", response_model=dict[str, object])
async def get_human_assist_task_detail(
    task_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    return await _runtime_center_detail_query(
        request=request,
        response=response,
        query_methods=("get_human_assist_task_detail",),
        not_available_detail="Human assist task detail queries are not available",
        not_found_detail=f"Human assist task '{task_id}' not found",
        payload_key="task",
        task_id=task_id,
    )


@router.get("/tasks", response_model=list[dict[str, object]])
async def list_tasks(
    request: Request,
    response: Response,
    limit: int = 20,
) -> list[dict[str, object]]:
    return await _runtime_center_list_query(
        request=request,
        response=response,
        query_methods=("list_tasks", "get_tasks", "list_runtime_tasks"),
        not_available_detail="Task queries are not available",
        limit=limit,
    )


@router.get("/tasks/{task_id}", response_model=dict[str, object])
async def get_task_detail(
    task_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    return await _runtime_center_detail_query(
        request=request,
        response=response,
        query_methods=("get_task_detail", "get_task"),
        not_available_detail="Task detail queries are not available",
        not_found_detail=f"Task '{task_id}' not found",
        payload_key="task",
        task_id=task_id,
    )


@router.get("/tasks/{task_id}/review", response_model=dict[str, object])
async def get_task_review(
    task_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    return await _runtime_center_detail_query(
        request=request,
        response=response,
        query_methods=("get_task_review",),
        not_available_detail="Task review queries are not available",
        not_found_detail=f"Task '{task_id}' not found",
        payload_key="review",
        task_id=task_id,
    )


@router.get("/work-contexts", response_model=list[dict[str, object]])
async def list_work_contexts(
    request: Request,
    response: Response,
    limit: int = 20,
) -> list[dict[str, object]]:
    return await _runtime_center_list_query(
        request=request,
        response=response,
        query_methods=("list_work_contexts",),
        not_available_detail="Work context queries are not available",
        limit=limit,
    )


@router.get("/work-contexts/{context_id}", response_model=dict[str, object])
async def get_work_context_detail(
    context_id: str,
    request: Request,
    response: Response,
) -> dict[str, object]:
    return await _runtime_center_detail_query(
        request=request,
        response=response,
        query_methods=("get_work_context_detail",),
        not_available_detail="Work context detail queries are not available",
        not_found_detail=f"Work context '{context_id}' not found",
        payload_key="work_context",
        context_id=context_id,
    )
