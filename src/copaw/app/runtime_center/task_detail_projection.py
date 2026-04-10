# -*- coding: utf-8 -*-
"""Task-detail projector for Runtime Center state-backed reads."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from ...evidence import EvidenceLedger
from ...kernel.persistence import decode_kernel_task_metadata
from ...state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteRuntimeFrameRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)
from ...utils.runtime_routes import task_route
from .environment_feedback_projection import RuntimeCenterEnvironmentFeedbackProjector
from .goal_decision_projection import RuntimeCenterGoalDecisionProjector
from .models import RuntimeActivationSummary, RuntimeTaskSubgraphSummary
from .execution_runtime_projection import summarize_execution_knowledge_writeback
from .projection_utils import first_non_empty, string_list_from_values
from .task_review_projection import (
    build_task_review_payload,
    serialize_child_rollup,
    serialize_evidence_record,
    serialize_kernel_meta,
    serialize_task_knowledge_context,
    trace_id_from_kernel_meta,
)
from .work_context_projection import RuntimeCenterWorkContextProjector


class RuntimeCenterTaskDetailProjector:
    """Project detailed task/read-review payloads from canonical state."""

    def __init__(
        self,
        *,
        task_repository: SqliteTaskRepository,
        task_runtime_repository: SqliteTaskRuntimeRepository,
        runtime_frame_repository: SqliteRuntimeFrameRepository | None = None,
        decision_request_repository: SqliteDecisionRequestRepository,
        evidence_ledger: EvidenceLedger | None = None,
        goal_decision_projector: RuntimeCenterGoalDecisionProjector,
        environment_feedback_projector: RuntimeCenterEnvironmentFeedbackProjector,
        work_context_projector: RuntimeCenterWorkContextProjector,
        related_patches_loader: Callable[..., list[dict[str, object]]],
        related_growth_loader: Callable[..., list[dict[str, object]]],
        related_agents_loader: Callable[[set[str]], list[dict[str, object]]],
        memory_activation_service: object | None = None,
        knowledge_graph_service: object | None = None,
        task_route_builder: Callable[[str], str] = task_route,
    ) -> None:
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._runtime_frame_repository = runtime_frame_repository
        self._decision_request_repository = decision_request_repository
        self._evidence_ledger = evidence_ledger
        self._goal_decision_projector = goal_decision_projector
        self._environment_feedback_projector = environment_feedback_projector
        self._work_context_projector = work_context_projector
        self._related_patches_loader = related_patches_loader
        self._related_growth_loader = related_growth_loader
        self._related_agents_loader = related_agents_loader
        self._memory_activation_service = memory_activation_service
        self._knowledge_graph_service = knowledge_graph_service
        self._task_route_builder = task_route_builder

    def set_memory_activation_service(self, service: object | None) -> None:
        self._memory_activation_service = service

    def set_knowledge_graph_service(self, service: object | None) -> None:
        self._knowledge_graph_service = service

    def get_task_detail(self, task_id: str) -> dict[str, object] | None:
        task = self._task_repository.get_task(task_id)
        if task is None:
            return None

        runtime = self._task_runtime_repository.get_runtime(task_id)
        parent_task = (
            self._task_repository.get_task(task.parent_task_id)
            if task.parent_task_id
            else None
        )
        child_tasks = self._task_repository.list_tasks(parent_task_id=task_id)
        frames = (
            self._runtime_frame_repository.list_frames(task_id, limit=10)
            if self._runtime_frame_repository is not None
            else []
        )
        decisions = self._decision_request_repository.list_decision_requests(task_id=task_id)
        evidence = (
            self._evidence_ledger.list_by_task(task_id)
            if self._evidence_ledger is not None
            else []
        )
        agent_ids = {
            agent_id
            for agent_id in (
                task.owner_agent_id,
                runtime.last_owner_agent_id if runtime is not None else None,
            )
            if agent_id
        }
        agent_ids.update(
            child.owner_agent_id
            for child in child_tasks
            if child.owner_agent_id
        )
        evidence_ids = {
            record.id
            for record in evidence
            if record.id is not None
        }
        patches = self._related_patches_loader(
            goal_id=task.goal_id,
            task_id=task.id,
            agent_ids=agent_ids,
            evidence_ids=evidence_ids,
        )
        patch_ids = {
            patch["id"]
            for patch in patches
            if isinstance(patch.get("id"), str)
        }
        growth = self._related_growth_loader(
            goal_id=task.goal_id,
            task_id=task.id,
            agent_ids=agent_ids,
            evidence_ids=evidence_ids,
            patch_ids=patch_ids,
        )
        child_status_counts = Counter(child.status for child in child_tasks)
        child_terminal_count = sum(
            count
            for status, count in child_status_counts.items()
            if status in {"completed", "failed", "cancelled"}
        )
        kernel_metadata = decode_kernel_task_metadata(task.acceptance_criteria)
        related_agents = self._related_agents_loader(agent_ids)
        related_agents_by_id = {
            str(agent.get("agent_id")).strip(): agent
            for agent in related_agents
            if isinstance(agent, dict) and str(agent.get("agent_id")).strip()
        }
        child_result_rollups = [
            serialize_child_rollup(
                child,
                self._task_runtime_repository.get_runtime(child.id),
                owner_agent=related_agents_by_id.get(str(child.owner_agent_id or "").strip()),
                work_context=self._work_context_projector.serialize_work_context(
                    child.work_context_id,
                ),
            )
            for child in sorted(child_tasks, key=lambda item: item.updated_at, reverse=True)
        ]
        owner_agent_id = (
            runtime.last_owner_agent_id
            if runtime is not None and runtime.last_owner_agent_id
            else task.owner_agent_id
        )
        review_payload = build_task_review_payload(
            task=task,
            runtime=runtime,
            decisions=decisions,
            evidence=evidence,
            execution_feedback=self._environment_feedback_projector.collect_task_execution_feedback(
                task=task,
                runtime=runtime,
                child_tasks=child_tasks,
            ),
            child_results=child_result_rollups,
            owner_agent=related_agents_by_id.get(str(owner_agent_id or "").strip()),
            task_route=self._task_route_builder(task.id),
        )
        activation = self.build_task_activation_summary(
            task=task,
            runtime=runtime,
            kernel_metadata=kernel_metadata,
        )
        task_subgraph = self.build_task_subgraph_summary(
            kernel_metadata=kernel_metadata,
        )
        knowledge_writeback = summarize_execution_knowledge_writeback(
            related_agents_by_id.get(str(owner_agent_id or "").strip(), {}).get("latest_knowledge_writeback")
            if isinstance(related_agents_by_id.get(str(owner_agent_id or "").strip()), dict)
            else None,
        )
        payload = {
            "trace_id": trace_id_from_kernel_meta(task_id, kernel_metadata),
            "task": task.model_dump(mode="json"),
            "runtime": runtime.model_dump(mode="json") if runtime is not None else None,
            "goal": self._goal_decision_projector.resolve_goal(task.goal_id),
            "parent_task": (
                {
                    **parent_task.model_dump(mode="json"),
                    "route": self._task_route_builder(parent_task.id),
                }
                if parent_task is not None
                else None
            ),
            "child_tasks": child_result_rollups,
            "frames": [frame.model_dump(mode="json") for frame in frames],
            "decisions": [
                self._goal_decision_projector.serialize_decision_request(decision)
                for decision in decisions
            ],
            "evidence": [serialize_evidence_record(record) for record in evidence],
            "agents": related_agents,
            "work_context": self._work_context_projector.serialize_work_context(
                task.work_context_id,
            ),
            "kernel": serialize_kernel_meta(task_id, kernel_metadata),
            "knowledge": serialize_task_knowledge_context(kernel_metadata),
            "delegation": {
                "parent_task_id": task.parent_task_id,
                "is_child_task": task.parent_task_id is not None,
                "is_parent_task": bool(child_tasks),
                "child_task_status_counts": dict(child_status_counts),
                "child_terminal_count": child_terminal_count,
                "child_completion_rate": (
                    round((child_terminal_count / len(child_tasks)) * 100, 1)
                    if child_tasks
                    else 0.0
                ),
                "child_results": child_result_rollups[:10],
            },
            "patches": patches,
            "growth": growth,
            "review": review_payload,
            "activation": activation,
            "knowledge_writeback": knowledge_writeback,
            "stats": {
                "frame_count": len(frames),
                "decision_count": len(decisions),
                "evidence_count": len(evidence),
                "patch_count": len(patches),
                "growth_count": len(growth),
                "agent_count": len(agent_ids),
                "child_task_count": len(child_tasks),
            },
            "route": self._task_route_builder(task_id),
        }
        if task_subgraph is not None:
            payload["task_subgraph"] = task_subgraph
        return payload

    def get_task_review(self, task_id: str) -> dict[str, object] | None:
        detail = self.get_task_detail(task_id)
        if detail is None:
            return None
        review = detail.get("review")
        if not isinstance(review, dict):
            return None
        return {
            "task": detail.get("task"),
            "runtime": detail.get("runtime"),
            "review": review,
            "route": f"{self._task_route_builder(task_id)}/review",
        }

    def build_task_activation_summary(
        self,
        *,
        task: object,
        runtime: object | None,
        kernel_metadata: dict[str, object] | None,
    ) -> dict[str, object] | None:
        service = self._memory_activation_service
        activate_for_query = getattr(service, "activate_for_query", None)
        if not callable(activate_for_query):
            return {
                "status": "unavailable",
                "reason": "memory-activation-service-unwired",
            }
        task_id = first_non_empty(getattr(task, "id", None))
        if task_id is None:
            return None
        query = self._build_task_activation_query(task=task, runtime=runtime)
        if query is None:
            return None
        owner_agent_id = first_non_empty(
            getattr(runtime, "last_owner_agent_id", None) if runtime is not None else None,
            getattr(task, "owner_agent_id", None),
        )
        result = activate_for_query(
            query=query,
            task_id=task_id,
            work_context_id=first_non_empty(getattr(task, "work_context_id", None)),
            owner_agent_id=owner_agent_id,
            capability_ref=first_non_empty((kernel_metadata or {}).get("capability_ref")),
            risk_level=first_non_empty(
                getattr(runtime, "risk_level", None) if runtime is not None else None,
            ),
            current_phase=first_non_empty(
                getattr(runtime, "current_phase", None) if runtime is not None else None,
            ),
            include_strategy=True,
            include_reports=True,
            limit=6,
        )
        return self._serialize_activation_summary(result)

    def _build_task_activation_query(
        self,
        *,
        task: object,
        runtime: object | None,
    ) -> str | None:
        query_parts = string_list_from_values(
            getattr(task, "title", None),
            getattr(runtime, "last_result_summary", None) if runtime is not None else None,
            getattr(task, "summary", None),
        )
        if not query_parts:
            return None
        return " | ".join(dict.fromkeys(query_parts))

    def _serialize_activation_summary(self, result: object) -> dict[str, object] | None:
        model_dump = getattr(result, "model_dump", None)
        if not callable(model_dump):
            return None
        payload = model_dump(mode="json")
        if not isinstance(payload, dict):
            return None
        summary = RuntimeActivationSummary(
            scope_type=first_non_empty(payload.get("scope_type")) or "global",
            scope_id=first_non_empty(payload.get("scope_id")) or "runtime",
            activated_count=len(payload.get("activated_neurons") or []),
            contradiction_count=len(payload.get("contradictions") or []),
            top_entities=string_list_from_values(payload.get("top_entities")),
            top_opinions=string_list_from_values(payload.get("top_opinions")),
            top_relations=string_list_from_values(payload.get("top_relations")),
            top_relation_kinds=string_list_from_values(payload.get("top_relation_kinds")),
            top_constraints=string_list_from_values(payload.get("top_constraints")),
            top_next_actions=string_list_from_values(payload.get("top_next_actions")),
            support_refs=string_list_from_values(payload.get("support_refs")),
            top_evidence_refs=string_list_from_values(
                payload.get("top_evidence_refs"),
                payload.get("evidence_refs"),
                payload.get("support_refs"),
            ),
            evidence_refs=string_list_from_values(payload.get("evidence_refs")),
            strategy_refs=string_list_from_values(payload.get("strategy_refs")),
        )
        if (
            summary.activated_count <= 0
            and not summary.top_entities
            and not summary.top_opinions
            and not summary.top_relations
            and not summary.top_constraints
            and not summary.support_refs
        ):
            return None
        return summary.model_dump(mode="json")

    def build_task_subgraph_summary(
        self,
        *,
        kernel_metadata: dict[str, object] | None,
    ) -> dict[str, object] | None:
        service = self._knowledge_graph_service
        summarize = getattr(service, "summarize_kernel_task_subgraph", None)
        if not callable(summarize):
            return {
                "status": "unavailable",
                "reason": "knowledge-graph-service-unwired",
            }
        summary = summarize(kernel_metadata)
        if not isinstance(summary, dict) or not summary:
            return None
        return RuntimeTaskSubgraphSummary(**summary).model_dump(mode="json")


__all__ = ["RuntimeCenterTaskDetailProjector"]
