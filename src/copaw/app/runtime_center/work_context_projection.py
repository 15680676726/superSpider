# -*- coding: utf-8 -*-
"""Stable work-context projections for Runtime Center state queries."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...kernel.persistence import decode_kernel_task_metadata
from ...utils.runtime_routes import task_route, work_context_route
from .chat_thread_projection import extract_chat_thread_payload
from .projection_utils import first_non_empty
from .task_review_projection import (
    serialize_child_rollup,
)

RelatedAgentsLoader = Callable[[set[str]], list[dict[str, object]]]
TaskRouteBuilder = Callable[[str], str]
WorkContextRouteBuilder = Callable[[str], str]


class RuntimeCenterWorkContextProjector:
    """Project stable work-context payloads over canonical task/runtime state."""

    def __init__(
        self,
        *,
        task_repository: Any,
        task_runtime_repository: Any,
        work_context_repository: Any,
        related_agents_loader: RelatedAgentsLoader,
        task_route_builder: TaskRouteBuilder = task_route,
        work_context_route_builder: WorkContextRouteBuilder = work_context_route,
    ) -> None:
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._work_context_repository = work_context_repository
        self._related_agents_loader = related_agents_loader
        self._task_route_builder = task_route_builder
        self._work_context_route_builder = work_context_route_builder

    def serialize_work_context(
        self,
        work_context_id: str | None,
    ) -> dict[str, object] | None:
        if not isinstance(work_context_id, str) or not work_context_id.strip():
            return None
        repository = self._work_context_repository
        if repository is None:
            return {"id": work_context_id}
        record = repository.get_context(work_context_id)
        if record is None:
            return {"id": work_context_id}
        return {
            "id": record.id,
            "title": record.title,
            "context_type": record.context_type,
            "status": record.status,
            "context_key": record.context_key,
        }

    def list_work_contexts(self, limit: int | None = 5) -> list[dict[str, object]]:
        repository = self._work_context_repository
        if repository is None:
            return []
        contexts = repository.list_contexts(limit=limit)
        payload: list[dict[str, object]] = []
        for context in contexts:
            tasks = self._task_repository.list_tasks(work_context_id=context.id)
            tasks.sort(key=lambda item: item.updated_at, reverse=True)
            active_task_count = sum(
                1
                for task in tasks
                if str(getattr(task, "status", "") or "")
                not in {"completed", "failed", "cancelled"}
            )
            latest_task = tasks[0] if tasks else None
            payload.append(
                {
                    "id": context.id,
                    "title": context.title,
                    "kind": "work-context",
                    "status": context.status,
                    "owner_scope": context.owner_scope,
                    "summary": context.summary,
                    "updated_at": context.updated_at,
                    "route": self._work_context_route_builder(context.id),
                    "context_type": context.context_type,
                    "context_key": context.context_key,
                    "owner_agent_id": context.owner_agent_id,
                    "industry_instance_id": context.industry_instance_id,
                    "primary_thread_id": context.primary_thread_id,
                    "parent_work_context_id": context.parent_work_context_id,
                    "task_count": len(tasks),
                    "active_task_count": active_task_count,
                    "latest_task_id": getattr(latest_task, "id", None),
                    "latest_task_title": getattr(latest_task, "title", None),
                },
            )
        return payload

    def count_work_contexts(self) -> int:
        repository = self._work_context_repository
        if repository is None:
            return 0
        return len(repository.list_contexts())

    def get_work_context_detail(self, context_id: str) -> dict[str, object] | None:
        repository = self._work_context_repository
        if repository is None:
            return None
        record = repository.get_context(context_id)
        if record is None:
            return None
        tasks = self._task_repository.list_tasks(work_context_id=context_id)
        tasks.sort(key=lambda item: item.updated_at, reverse=True)
        task_runtimes = {
            str(getattr(task, "id", "") or ""): self._task_runtime_repository.get_runtime(
                task.id,
            )
            for task in tasks
            if str(getattr(task, "id", "") or "").strip()
        }
        owner_agent_ids = {
            self._resolved_owner_agent_id(
                task,
                task_runtimes.get(str(getattr(task, "id", "") or "").strip()),
            )
            for task in tasks
            if self._resolved_owner_agent_id(
                task,
                task_runtimes.get(str(getattr(task, "id", "") or "").strip()),
            )
        }
        related_agents = self._related_agents_loader(owner_agent_ids)
        related_agents_by_id = {
            str(agent.get("agent_id")).strip(): agent
            for agent in related_agents
            if isinstance(agent, dict) and str(agent.get("agent_id")).strip()
        }
        child_contexts = repository.list_contexts(parent_work_context_id=context_id)
        task_rollups = []
        for task in tasks[:20]:
            runtime = task_runtimes.get(str(getattr(task, "id", "") or "").strip())
            owner_agent_id = self._resolved_owner_agent_id(task, runtime)
            task_rollup = serialize_child_rollup(
                task,
                runtime,
                owner_agent=related_agents_by_id.get(
                    owner_agent_id,
                ),
                work_context=self.serialize_work_context(
                    getattr(task, "work_context_id", None),
                ),
            )
            if owner_agent_id is not None:
                task_rollup["owner_agent_id"] = owner_agent_id
            task_rollups.append(task_rollup)
        thread_ids = list(
            dict.fromkeys(
                item
                for item in (
                    record.primary_thread_id,
                    *[
                        first_non_empty(
                            extract_chat_thread_payload(
                                decode_kernel_task_metadata(
                                    getattr(task, "acceptance_criteria", None),
                                ),
                            ).get("control_thread_id"),
                        )
                        for task in tasks
                    ],
                )
                if isinstance(item, str) and item.strip()
            ),
        )
        terminal_task_count = sum(
            1
            for task in tasks
            if str(getattr(task, "status", "") or "")
            in {"completed", "failed", "cancelled"}
        )
        child_context_payloads = [
            self.serialize_work_context(child.id)
            for child in child_contexts
        ]
        return {
            "work_context": record.model_dump(mode="json"),
            "parent_work_context": self.serialize_work_context(record.parent_work_context_id),
            "child_contexts": [
                child_payload
                for child_payload in child_context_payloads
                if child_payload is not None
            ],
            "tasks": task_rollups,
            "agents": related_agents,
            "threads": thread_ids,
            "stats": {
                "task_count": len(tasks),
                "active_task_count": len(tasks) - terminal_task_count,
                "terminal_task_count": terminal_task_count,
                "owner_agent_count": len(owner_agent_ids),
                "child_context_count": len(child_contexts),
            },
            "route": self._work_context_route_builder(context_id),
        }

    def _resolved_owner_agent_id(
        self,
        task: Any,
        runtime: Any | None,
    ) -> str | None:
        for value in (
            getattr(runtime, "last_owner_agent_id", None) if runtime is not None else None,
            getattr(task, "owner_agent_id", None),
        ):
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if normalized:
                return normalized
        return None
