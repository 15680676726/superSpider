# -*- coding: utf-8 -*-
from __future__ import annotations


def task_route(task_id: str) -> str:
    return f"/api/runtime-center/tasks/{task_id}"


def goal_route(goal_id: str) -> str:
    return f"/api/runtime-center/goals/{goal_id}"


def agent_route(agent_id: str) -> str:
    return f"/api/runtime-center/agents/{agent_id}"


def decision_route(decision_id: str) -> str:
    return f"/api/runtime-center/decisions/{decision_id}"


def schedule_route(schedule_id: str) -> str:
    return f"/api/runtime-center/schedules/{schedule_id}"


def work_context_route(context_id: str) -> str:
    return f"/api/runtime-center/work-contexts/{context_id}"


__all__ = [
    "agent_route",
    "decision_route",
    "goal_route",
    "schedule_route",
    "task_route",
    "work_context_route",
]
