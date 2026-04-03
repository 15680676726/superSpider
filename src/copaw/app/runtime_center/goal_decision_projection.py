# -*- coding: utf-8 -*-
"""Goal and decision read projections for Runtime Center state queries."""
from __future__ import annotations

from typing import Any

from ...kernel.decision_policy import (
    decision_chat_route,
    decision_chat_thread_id,
    decision_requires_human_confirmation,
)
from ...kernel.persistence import decode_kernel_task_metadata
from ...utils.runtime_action_links import build_decision_actions
from ...utils.runtime_routes import decision_route, goal_route, task_route
from .task_review_projection import (
    extract_chat_thread_payload,
    trace_id_from_kernel_meta,
)


class RuntimeCenterGoalDecisionProjector:
    """Project stable goal and governance payloads for Runtime Center reads."""

    def __init__(
        self,
        *,
        goal_repository: Any | None,
        goal_service: object | None,
        decision_request_repository: Any,
        task_repository: Any,
    ) -> None:
        self._goal_repository = goal_repository
        self._goal_service = goal_service
        self._decision_request_repository = decision_request_repository
        self._task_repository = task_repository

    def set_goal_service(self, goal_service: object | None) -> None:
        self._goal_service = goal_service

    def list_goals(self, limit: int | None = 5) -> list[dict[str, object]]:
        goals = []
        if self._goal_service is not None:
            list_goals = getattr(self._goal_service, "list_goals", None)
            if callable(list_goals):
                try:
                    goals = list(list_goals(limit=limit))
                except TypeError:
                    goals = list(list_goals())
        elif self._goal_repository is not None:
            goals = self._goal_repository.list_goals(limit=limit)
        if not goals:
            return []
        goals.sort(
            key=lambda goal: (
                goal.status != "active",
                -goal.priority,
                goal.updated_at,
            ),
            reverse=False,
        )
        payload: list[dict[str, object]] = []
        for goal in goals:
            payload.append(
                {
                    "id": goal.id,
                    "title": goal.title,
                    "summary": goal.summary,
                    "status": goal.status,
                    "priority": goal.priority,
                    "owner_scope": goal.owner_scope,
                    "updated_at": goal.updated_at,
                    "route": goal_route(goal.id),
                },
            )
        return payload

    def get_goal_detail(self, goal_id: str) -> dict[str, object] | None:
        service = self._goal_service
        getter = getattr(service, "get_goal_detail", None)
        if callable(getter):
            return getter(goal_id)
        return None

    def resolve_goal(self, goal_id: str | None) -> dict[str, object] | None:
        if not goal_id:
            return None
        service = self._goal_service
        getter = getattr(service, "get_goal", None)
        goal = getter(goal_id) if callable(getter) else None
        if goal is None and self._goal_repository is not None:
            goal = self._goal_repository.get_goal(goal_id)
        if goal is None:
            return None
        return goal.model_dump(mode="json")

    def list_decision_requests(self, limit: int | None = 5) -> list[dict[str, object]]:
        decisions = self._decision_request_repository.list_decision_requests(limit=limit)
        return [self.serialize_decision_request(decision) for decision in decisions]

    def get_decision_request(self, decision_id: str) -> dict[str, object] | None:
        decision = self._decision_request_repository.get_decision_request(decision_id)
        if decision is None:
            return None
        return self.serialize_decision_request(decision)

    def serialize_decision_request(self, decision: Any) -> dict[str, object]:
        route = decision_route(decision.id)
        task = self._task_repository.get_task(decision.task_id)
        kernel_meta = (
            decode_kernel_task_metadata(task.acceptance_criteria)
            if task is not None
            else None
        )
        chat_context = extract_chat_thread_payload(kernel_meta)
        chat_thread_id = decision_chat_thread_id(chat_context)
        chat_route = decision_chat_route(chat_thread_id)
        requires_human_confirmation = decision_requires_human_confirmation(
            decision_type=getattr(decision, "decision_type", None),
            payload=chat_context,
        )
        actions: dict[str, str] = {}
        if decision.status == "open":
            actions = build_decision_actions(decision.id, status="open")
        elif decision.status == "reviewing":
            actions = build_decision_actions(decision.id, status="reviewing")
        return {
            "id": decision.id,
            "task_id": decision.task_id,
            "trace_id": trace_id_from_kernel_meta(decision.task_id, kernel_meta),
            "decision_type": decision.decision_type,
            "risk_level": decision.risk_level,
            "summary": decision.summary,
            "status": decision.status,
            "requested_by": decision.requested_by,
            "resolution": decision.resolution,
            "created_at": decision.created_at,
            "resolved_at": decision.resolved_at,
            "expires_at": getattr(decision, "expires_at", None),
            "route": route,
            "governance_route": route,
            "task_route": task_route(decision.task_id),
            "chat_thread_id": chat_thread_id,
            "chat_route": chat_route,
            "preferred_route": chat_route if requires_human_confirmation else route,
            "requires_human_confirmation": requires_human_confirmation,
            "actions": actions,
        }
