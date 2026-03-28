# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from agentscope.message import Msg, TextBlock

from ..app.channels.schema import DEFAULT_CHANNEL
from ..industry.identity import EXECUTION_CORE_ROLE_ID
from ..industry.prompting import infer_industry_task_mode
from ..utils.runtime_action_links import build_decision_actions
from ..utils.runtime_routes import decision_route, task_route


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
            continue
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return None


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _normalize_main_brain_runtime_context(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    from .main_brain_intake import normalize_main_brain_runtime_context

    return normalize_main_brain_runtime_context(value)


def runtime_task_route(task_id: str) -> str:
    return task_route(task_id)


def runtime_decision_route(decision_id: str) -> str:
    return decision_route(decision_id)


def runtime_decision_actions(
    decision_id: str,
    *,
    status: str = "open",
) -> dict[str, str]:
    return build_decision_actions(decision_id, status=status)


def execution_feedback_prompt_lines(feedback: dict[str, Any]) -> list[str]:
    if not feedback:
        return []
    lines: list[str] = []
    current_stage = _first_non_empty(feedback.get("current_stage"))
    recent_failures = _string_list(feedback.get("recent_failures"))
    effective_actions = _string_list(feedback.get("effective_actions"))
    avoid_repeats = _string_list(feedback.get("avoid_repeats"))
    if current_stage:
        lines.append("Current execution stage to continue from:")
        lines.append(f"- {current_stage}")
    if recent_failures:
        lines.append("Recent failures to avoid repeating:")
        lines.extend(f"- {item}" for item in recent_failures[:4])
    if effective_actions:
        lines.append("Recently effective moves to reuse:")
        lines.extend(f"- {item}" for item in effective_actions[:4])
    if avoid_repeats:
        lines.append("Do not repeat these patterns:")
        lines.extend(f"- {item}" for item in avoid_repeats[:4])
    return lines


def query_confirmation_request_context(request: Any) -> dict[str, object]:
    payload: dict[str, object] = {}
    for field in (
        "session_id",
        "control_thread_id",
        "user_id",
        "channel",
        "agent_id",
        "entry_source",
        "owner_scope",
        "industry_instance_id",
        "industry_role_id",
        "industry_label",
        "session_kind",
        "task_mode",
    ):
        value = getattr(request, field, None)
        if value not in (None, ""):
            payload[field] = value
    if "task_mode" not in payload:
        industry_role_id = _first_non_empty(payload.get("industry_role_id"))
        if industry_role_id:
            payload["task_mode"] = infer_industry_task_mode(
                role_id=industry_role_id,
                goal_kind=(industry_role_id if industry_role_id == EXECUTION_CORE_ROLE_ID else None),
                source="goal",
            )
    main_brain_runtime = _normalize_main_brain_runtime_context(
        getattr(request, "_copaw_main_brain_runtime_context", None)
        or getattr(request, "main_brain_runtime", None),
    )
    if main_brain_runtime:
        payload["main_brain_runtime"] = main_brain_runtime
    return payload


def query_confirmation_required_message(
    *,
    decision_request_id: str | None,
    decision_summary: str | None,
) -> Msg:
    detail = (
        f"决策请求：`{decision_request_id}`。"
        if decision_request_id
        else "系统已创建决策请求。"
    )
    summary = decision_summary or "当前代操请求在执行前需要确认。"
    return Msg(
        name="Spider Mesh",
        role="assistant",
        content=[
            TextBlock(
                type="text",
                text=(
                    f"**需要确认**\n\n- {detail}\n- {summary}\n- 请先在主脑聊天里明确同意继续当前动作，"
                    "或在运行中心批准后，再继续执行。"
                ),
            ),
        ],
    )


def build_query_resume_request(
    *,
    request_context: dict[str, Any],
    owner_agent_id: str,
) -> Any:
    payload = dict(request_context)
    main_brain_runtime = _normalize_main_brain_runtime_context(
        payload.get("main_brain_runtime"),
    )
    session_id = _first_non_empty(payload.get("session_id")) or f"resume:{owner_agent_id}"
    user_id = _first_non_empty(payload.get("user_id"), owner_agent_id) or owner_agent_id
    channel = _first_non_empty(payload.get("channel"), DEFAULT_CHANNEL) or DEFAULT_CHANNEL
    request = type("QueryResumeRequest", (), {})()
    setattr(request, "id", f"query-resume:{owner_agent_id}:{session_id}")
    setattr(request, "session_id", session_id)
    setattr(request, "user_id", user_id)
    setattr(request, "channel", channel)
    setattr(request, "agent_id", _first_non_empty(payload.get("agent_id"), owner_agent_id))
    setattr(request, "entry_source", _first_non_empty(payload.get("entry_source"), "runtime-center"))
    setattr(request, "input", [])
    for field in (
        "owner_scope",
        "industry_instance_id",
        "industry_role_id",
        "industry_label",
        "industry_role_name",
        "session_kind",
        "task_mode",
        "target_agent_id",
    ):
        value = payload.get(field)
        if value not in (None, ""):
            setattr(request, field, value)
    if main_brain_runtime is not None:
        setattr(request, "main_brain_runtime", main_brain_runtime)
        setattr(request, "_copaw_main_brain_runtime_context", main_brain_runtime)
    return request


_runtime_task_route = runtime_task_route
_runtime_decision_route = runtime_decision_route
_runtime_decision_actions = runtime_decision_actions
_execution_feedback_prompt_lines = execution_feedback_prompt_lines
_query_confirmation_request_context = query_confirmation_request_context
_query_confirmation_required_message = query_confirmation_required_message
_build_query_resume_request = build_query_resume_request


__all__ = [
    "_build_query_resume_request",
    "_execution_feedback_prompt_lines",
    "_query_confirmation_request_context",
    "_query_confirmation_required_message",
    "_runtime_decision_actions",
    "_runtime_decision_route",
    "_runtime_task_route",
    "build_query_resume_request",
    "execution_feedback_prompt_lines",
    "query_confirmation_request_context",
    "query_confirmation_required_message",
    "runtime_decision_actions",
    "runtime_decision_route",
    "runtime_task_route",
]
