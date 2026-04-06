# -*- coding: utf-8 -*-
"""Stable task-list projections for Runtime Center state queries."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...kernel.task_execution_projection import resolve_visible_execution_phase
from ...kernel.persistence import KernelTaskStore, decode_kernel_task_metadata
from ...utils.runtime_routes import task_route
from .projection_utils import first_non_empty
from .task_review_projection import trace_id_from_kernel_meta

WorkContextLoader = Callable[[str | None], dict[str, object] | None]
TaskRouteBuilder = Callable[[str], str]
ActivationSummaryBuilder = Callable[..., dict[str, object] | None]
TaskSubgraphSummaryBuilder = Callable[..., dict[str, object] | None]


def _work_context_context_key(work_context: dict[str, object] | None) -> str | None:
    if not isinstance(work_context, dict):
        return None
    return first_non_empty(work_context.get("context_key"))


class RuntimeCenterTaskListProjector:
    """Project stable task list payloads over canonical task/runtime state."""

    def __init__(
        self,
        *,
        task_repository: Any,
        task_runtime_repository: Any,
        work_context_loader: WorkContextLoader,
        activation_summary_builder: ActivationSummaryBuilder,
        task_subgraph_summary_builder: TaskSubgraphSummaryBuilder | None = None,
        task_route_builder: TaskRouteBuilder = task_route,
    ) -> None:
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._work_context_loader = work_context_loader
        self._activation_summary_builder = activation_summary_builder
        self._task_subgraph_summary_builder = task_subgraph_summary_builder
        self._task_route_builder = task_route_builder

    def list_tasks(self, limit: int | None = 5) -> list[dict[str, object]]:
        tasks = self._task_repository.list_tasks(limit=limit)
        tasks.sort(key=lambda item: item.updated_at, reverse=True)
        return [self._project_task(task) for task in tasks]

    def list_kernel_tasks(
        self,
        *,
        phase: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, object]]:
        task_store = KernelTaskStore(
            task_repository=self._task_repository,
            task_runtime_repository=self._task_runtime_repository,
        )
        return [
            task.model_dump(mode="json")
            for task in task_store.list_tasks(phase=phase, limit=limit)
        ]

    def _project_task(self, task: Any) -> dict[str, object]:
        runtime = self._task_runtime_repository.get_runtime(task.id)
        kernel_meta = decode_kernel_task_metadata(task.acceptance_criteria)
        child_task_count = len(self._task_repository.list_tasks(parent_task_id=task.id))
        work_context = self._work_context_loader(task.work_context_id)
        activation = self._activation_summary_builder(
            task=task,
            runtime=runtime,
            kernel_metadata=kernel_meta,
        )
        task_subgraph = None
        if self._task_subgraph_summary_builder is not None:
            task_subgraph = self._task_subgraph_summary_builder(
                kernel_metadata=kernel_meta,
            )
        visible_status = resolve_visible_execution_phase(
            runtime_phase=getattr(runtime, "current_phase", None) if runtime is not None else None,
            runtime_status=getattr(runtime, "runtime_status", None) if runtime is not None else None,
            task_status=getattr(task, "status", None),
        ) or task.status
        payload = {
            "id": task.id,
            "trace_id": trace_id_from_kernel_meta(task.id, kernel_meta),
            "title": task.title,
            "kind": task.task_type,
            "status": visible_status,
            "owner_agent_id": (
                runtime.last_owner_agent_id
                if runtime is not None and runtime.last_owner_agent_id
                else task.owner_agent_id
            ),
            "summary": (
                runtime.last_result_summary
                if runtime is not None and runtime.last_result_summary
                else task.summary
            ),
            "current_progress_summary": (
                runtime.last_result_summary
                if runtime is not None and runtime.last_result_summary
                else task.summary
            ),
            "updated_at": runtime.updated_at if runtime is not None else task.updated_at,
            "parent_task_id": task.parent_task_id,
            "work_context_id": task.work_context_id,
            "context_key": _work_context_context_key(work_context),
            "work_context": work_context,
            "child_task_count": child_task_count,
            "route": self._task_route_builder(task.id),
            "activation": activation,
        }
        if task_subgraph is not None:
            payload["task_subgraph"] = task_subgraph
        return payload
