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


def _path_summary(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, dict):
        return _first_non_empty(value.get("summary"), value.get("label"))
    return _first_non_empty(getattr(value, "summary", None), getattr(value, "label", None))


def _path_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        summary = _path_summary(value)
        if summary is None or summary in seen:
            continue
        seen.add(summary)
        normalized.append(summary)
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
    capability_refs = _string_list(feedback.get("capability_refs"))
    environment_refs = _string_list(feedback.get("environment_refs"))
    risk_levels = _string_list(feedback.get("risk_levels"))
    execution_ordering_hints = _string_list(feedback.get("execution_ordering_hints"))
    dependency_paths = _path_list(feedback.get("dependency_paths"))
    blocker_paths = _path_list(feedback.get("blocker_paths"))
    recovery_paths = _path_list(feedback.get("recovery_paths"))
    contradiction_paths = _path_list(feedback.get("contradiction_paths"))
    if current_stage:
        lines.append("Current execution stage to continue from:")
        lines.append(f"- {current_stage}")
    if capability_refs or environment_refs or risk_levels:
        lines.append("Execution knowledge graph anchors:")
        if capability_refs:
            lines.append(f"- Capability refs: {', '.join(capability_refs[:4])}")
        if environment_refs:
            lines.append(f"- Environment refs: {', '.join(environment_refs[:4])}")
        if risk_levels:
            lines.append(f"- Risk levels seen: {', '.join(risk_levels[:4])}")
    if recent_failures:
        lines.append("Recent failures to avoid repeating:")
        lines.extend(f"- {item}" for item in recent_failures[:4])
    if effective_actions:
        lines.append("Recently effective moves to reuse:")
        lines.extend(f"- {item}" for item in effective_actions[:4])
    if avoid_repeats:
        lines.append("Do not repeat these patterns:")
        lines.extend(f"- {item}" for item in avoid_repeats[:4])
    if any(
        (
            execution_ordering_hints,
            dependency_paths,
            blocker_paths,
            recovery_paths,
            contradiction_paths,
        ),
    ):
        lines.append("Execution path guidance:")
        if execution_ordering_hints:
            lines.append("Top ordering hints:")
            lines.extend(f"- {item}" for item in execution_ordering_hints[:4])
        if dependency_paths:
            lines.append("Resolve these dependencies first:")
            lines.extend(f"- {item}" for item in dependency_paths[:4])
        if blocker_paths:
            lines.append("Known blockers that should stop forward motion:")
            lines.extend(f"- {item}" for item in blocker_paths[:4])
        if recovery_paths:
            lines.append("Preferred recovery moves when blocked:")
            lines.extend(f"- {item}" for item in recovery_paths[:4])
        if contradiction_paths:
            lines.append("Contradictions to resolve before claiming success:")
            lines.extend(f"- {item}" for item in contradiction_paths[:4])
    return lines


def query_confirmation_request_context(request: Any) -> dict[str, object]:
    payload: dict[str, object] = {}
    for field in (
        "session_id",
        "control_thread_id",
        "user_id",
        "channel",
        "environment_ref",
        "work_context_id",
        "agent_id",
        "entry_source",
        "coordinator_contract",
        "coordinator_entrypoint",
        "coordinator_id",
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
        "coordinator_contract",
        "coordinator_entrypoint",
        "coordinator_id",
    ):
        value = payload.get(field)
        if value not in (None, ""):
            setattr(request, field, value)
    environment_payload = (
        main_brain_runtime.get("environment")
        if isinstance(main_brain_runtime, dict)
        else None
    )
    work_context_id = _first_non_empty(
        payload.get("work_context_id"),
        main_brain_runtime.get("work_context_id")
        if isinstance(main_brain_runtime, dict)
        else None,
    )
    environment_ref = _first_non_empty(
        payload.get("environment_ref"),
        environment_payload.get("ref")
        if isinstance(environment_payload, dict)
        else None,
    )
    if work_context_id is not None:
        setattr(request, "work_context_id", work_context_id)
    if environment_ref is not None:
        setattr(request, "environment_ref", environment_ref)
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
