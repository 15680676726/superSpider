# -*- coding: utf-8 -*-
from __future__ import annotations

from urllib.parse import urlencode


def task_route(task_id: str) -> str:
    return f"/api/runtime-center/tasks/{task_id}"


def goal_route(goal_id: str) -> str:
    return f"/api/goals/{goal_id}/detail"


def agent_route(agent_id: str) -> str:
    return f"/api/runtime-center/agents/{agent_id}"


def decision_route(decision_id: str) -> str:
    return f"/api/runtime-center/decisions/{decision_id}"


def schedule_route(schedule_id: str) -> str:
    return f"/api/runtime-center/schedules/{schedule_id}"


def work_context_route(context_id: str) -> str:
    return f"/api/runtime-center/work-contexts/{context_id}"


def human_assist_task_route(task_id: str) -> str:
    return f"/api/runtime-center/human-assist-tasks/{task_id}"


def human_assist_task_list_route(
    *,
    chat_thread_id: str | None = None,
    industry_instance_id: str | None = None,
    assignment_id: str | None = None,
    task_id: str | None = None,
    status: str | None = None,
) -> str:
    params = {
        "chat_thread_id": chat_thread_id,
        "industry_instance_id": industry_instance_id,
        "assignment_id": assignment_id,
        "task_id": task_id,
        "status": status,
    }
    filtered = {
        key: value
        for key, value in params.items()
        if isinstance(value, str) and value.strip()
    }
    base = "/api/runtime-center/human-assist-tasks"
    if not filtered:
        return base
    return f"{base}?{urlencode(filtered)}"


def human_assist_task_current_route(*, chat_thread_id: str | None = None) -> str:
    base = "/api/runtime-center/human-assist-tasks/current"
    if not isinstance(chat_thread_id, str) or not chat_thread_id.strip():
        return base
    return f"{base}?{urlencode({'chat_thread_id': chat_thread_id})}"


__all__ = [
    "agent_route",
    "decision_route",
    "goal_route",
    "human_assist_task_current_route",
    "human_assist_task_list_route",
    "human_assist_task_route",
    "schedule_route",
    "task_route",
    "work_context_route",
]
