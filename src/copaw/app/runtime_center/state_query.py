# -*- coding: utf-8 -*-
"""State-backed read service for Runtime Center."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from ...evidence import EvidenceLedger
from ...kernel.decision_policy import (
    decision_chat_route,
    decision_chat_thread_id,
    decision_requires_human_confirmation,
)
from ...kernel.persistence import decode_kernel_task_metadata
from ...utils.runtime_routes import (
    agent_route,
    decision_route,
    goal_route,
    human_assist_task_current_route,
    human_assist_task_list_route,
    human_assist_task_route,
    schedule_route,
    task_route,
    work_context_route,
)
from ...utils.runtime_action_links import build_decision_actions
from ...state.execution_feedback import collect_recent_execution_feedback
from ...state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteGoalRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
)
from .task_review_projection import (
    build_task_review_payload,
    build_host_twin_summary,
    extract_chat_thread_payload,
    first_non_empty,
    serialize_child_rollup,
    serialize_evidence_record,
    serialize_kernel_meta,
    serialize_task_knowledge_context,
    string_list_from_values,
    trace_id_from_kernel_meta,
)


def _work_context_context_key(work_context: dict[str, object] | None) -> str | None:
    if not isinstance(work_context, dict):
        return None
    return first_non_empty(work_context.get("context_key"))


class RuntimeCenterStateQueryService:
    """Read-only Runtime Center state queries."""

    def __init__(
        self,
        *,
        task_repository: SqliteTaskRepository,
        task_runtime_repository: SqliteTaskRuntimeRepository,
        runtime_frame_repository: SqliteRuntimeFrameRepository | None = None,
        schedule_repository: SqliteScheduleRepository,
        goal_repository: SqliteGoalRepository | None = None,
        work_context_repository: SqliteWorkContextRepository | None = None,
        goal_service: object | None = None,
        decision_request_repository: SqliteDecisionRequestRepository,
        evidence_ledger: EvidenceLedger | None = None,
        learning_service: object | None = None,
        agent_profile_service: object | None = None,
        human_assist_task_service: object | None = None,
        kernel_dispatcher: object | None = None,
        runtime_event_bus: object | None = None,
        environment_service: object | None = None,
    ) -> None:
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._runtime_frame_repository = runtime_frame_repository
        self._schedule_repository = schedule_repository
        self._goal_repository = goal_repository
        self._work_context_repository = work_context_repository
        self._goal_service = goal_service
        self._decision_request_repository = decision_request_repository
        self._evidence_ledger = evidence_ledger
        self._learning_service = learning_service
        self._agent_profile_service = agent_profile_service
        self._human_assist_task_service = human_assist_task_service
        self._kernel_dispatcher = kernel_dispatcher
        self._runtime_event_bus = runtime_event_bus
        self._environment_service = environment_service

    def list_tasks(self, limit: int | None = 5) -> list[dict[str, object]]:
        tasks = self._task_repository.list_tasks(limit=limit)
        tasks.sort(key=lambda item: item.updated_at, reverse=True)
        payload: list[dict[str, object]] = []
        for task in tasks:
            runtime = self._task_runtime_repository.get_runtime(task.id)
            kernel_meta = decode_kernel_task_metadata(task.acceptance_criteria)
            child_task_count = len(self._task_repository.list_tasks(parent_task_id=task.id))
            work_context = self._serialize_work_context(task.work_context_id)
            payload.append(
                {
                    "id": task.id,
                    "trace_id": trace_id_from_kernel_meta(task.id, kernel_meta),
                    "title": task.title,
                    "kind": task.task_type,
                    "status": (
                        runtime.runtime_status
                        if runtime is not None and task.status == "running"
                        else task.status
                    ),
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
                    "updated_at": (
                        runtime.updated_at if runtime is not None else task.updated_at
                    ),
                    "parent_task_id": task.parent_task_id,
                    "work_context_id": task.work_context_id,
                    "context_key": _work_context_context_key(work_context),
                    "work_context": work_context,
                    "child_task_count": child_task_count,
                    "route": task_route(task.id),
                },
            )
        return payload

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
        patches = self._collect_related_patches(
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
        growth = self._collect_related_growth(
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
        related_agents = self._collect_related_agents(agent_ids)
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
                work_context=self._serialize_work_context(child.work_context_id),
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
            execution_feedback=self._collect_task_execution_feedback(
                task=task,
                runtime=runtime,
                child_tasks=child_tasks,
            ),
            child_results=child_result_rollups,
            owner_agent=related_agents_by_id.get(str(owner_agent_id or "").strip()),
            task_route=task_route(task.id),
        )
        return {
            "trace_id": trace_id_from_kernel_meta(task_id, kernel_metadata),
            "task": task.model_dump(mode="json"),
            "runtime": runtime.model_dump(mode="json") if runtime is not None else None,
            "goal": self._resolve_goal(task.goal_id),
            "parent_task": (
                {
                    **parent_task.model_dump(mode="json"),
                    "route": task_route(parent_task.id),
                }
                if parent_task is not None
                else None
            ),
            "child_tasks": child_result_rollups,
            "frames": [frame.model_dump(mode="json") for frame in frames],
            "decisions": [self._serialize_decision_request(decision) for decision in decisions],
            "evidence": [serialize_evidence_record(record) for record in evidence],
            "agents": related_agents,
            "work_context": self._serialize_work_context(task.work_context_id),
            "kernel": serialize_kernel_meta(task_id, kernel_metadata),
            "knowledge": serialize_task_knowledge_context(
                kernel_metadata,
            ),
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
            "stats": {
                "frame_count": len(frames),
                "decision_count": len(decisions),
                "evidence_count": len(evidence),
                "patch_count": len(patches),
                "growth_count": len(growth),
                "agent_count": len(agent_ids),
                "child_task_count": len(child_tasks),
            },
            "route": task_route(task_id),
        }

    def list_human_assist_tasks(
        self,
        *,
        chat_thread_id: str | None = None,
        industry_instance_id: str | None = None,
        assignment_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
        limit: int | None = 20,
    ) -> list[dict[str, object]]:
        service = self._human_assist_task_service
        list_tasks = getattr(service, "list_tasks", None)
        if not callable(list_tasks):
            return []
        tasks = list_tasks(
            chat_thread_id=chat_thread_id,
            industry_instance_id=industry_instance_id,
            assignment_id=assignment_id,
            task_id=task_id,
            status=status,
            limit=limit,
        )
        return [self._serialize_human_assist_task(task) for task in tasks]

    def get_current_human_assist_task(
        self,
        *,
        chat_thread_id: str,
    ) -> dict[str, object] | None:
        service = self._human_assist_task_service
        getter = getattr(service, "get_current_task", None)
        if not callable(getter):
            return None
        task = getter(chat_thread_id=chat_thread_id)
        if task is None:
            return None
        return self._serialize_human_assist_task(task)

    def get_human_assist_task_detail(self, task_id: str) -> dict[str, object] | None:
        service = self._human_assist_task_service
        getter = getattr(service, "get_task", None)
        if not callable(getter):
            return None
        task = getter(task_id)
        if task is None:
            return None
        return {
            "task": self._serialize_human_assist_task(task),
            "routes": {
                "self": human_assist_task_route(task.id),
                "list": human_assist_task_list_route(
                    chat_thread_id=task.chat_thread_id,
                ),
                "current": human_assist_task_current_route(
                    chat_thread_id=task.chat_thread_id,
                ),
            },
        }

    def _serialize_work_context(
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

    def _serialize_human_assist_task(self, task: object) -> dict[str, object]:
        model_dump = getattr(task, "model_dump", None)
        payload = model_dump(mode="json") if callable(model_dump) else {}
        if not isinstance(payload, dict):
            payload = {}
        task_id = str(payload.get("id") or "").strip()
        chat_thread_id = str(payload.get("chat_thread_id") or "").strip() or None
        if task_id:
            payload["route"] = human_assist_task_route(task_id)
        payload["tasks_route"] = human_assist_task_list_route(
            chat_thread_id=chat_thread_id,
        )
        payload["current_route"] = human_assist_task_current_route(
            chat_thread_id=chat_thread_id,
        )
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
            "route": f"{task_route(task_id)}/review",
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
                    "route": work_context_route(context.id),
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
        owner_agent_ids = {
            str(getattr(task, "owner_agent_id", "") or "").strip()
            for task in tasks
            if str(getattr(task, "owner_agent_id", "") or "").strip()
        }
        related_agents = self._collect_related_agents(owner_agent_ids)
        related_agents_by_id = {
            str(agent.get("agent_id")).strip(): agent
            for agent in related_agents
            if isinstance(agent, dict) and str(agent.get("agent_id")).strip()
        }
        child_contexts = repository.list_contexts(parent_work_context_id=context_id)
        task_rollups = [
            serialize_child_rollup(
                task,
                self._task_runtime_repository.get_runtime(task.id),
                owner_agent=related_agents_by_id.get(
                    str(getattr(task, "owner_agent_id", "") or "").strip(),
                ),
                work_context=self._serialize_work_context(getattr(task, "work_context_id", None)),
            )
            for task in tasks[:20]
        ]
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
        return {
            "work_context": record.model_dump(mode="json"),
            "parent_work_context": self._serialize_work_context(record.parent_work_context_id),
            "child_contexts": [
                self._serialize_work_context(child.id)
                for child in child_contexts
                if self._serialize_work_context(child.id) is not None
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
            "route": work_context_route(context_id),
        }

    def _collect_task_execution_feedback(
        self,
        *,
        task: Any,
        runtime: Any | None,
        child_tasks: list[Any],
    ) -> dict[str, object]:
        related_tasks: list[Any]
        goal_id = first_non_empty(getattr(task, "goal_id", None))
        if goal_id:
            related_tasks = self._task_repository.list_tasks(goal_id=goal_id)
        else:
            related_tasks = [task, *child_tasks]
        related_tasks = [
            item
            for item in related_tasks
            if str(getattr(item, "task_type", "") or "") != "learning-patch"
        ]
        feedback = collect_recent_execution_feedback(
            tasks=related_tasks,
            task_runtime_repository=self._task_runtime_repository,
            evidence_ledger=self._evidence_ledger,
        )
        runtime_feedback = self._collect_environment_runtime_feedback(
            primary_runtime=runtime,
            related_tasks=related_tasks,
        )
        if not runtime_feedback:
            return feedback
        merged_feedback = dict(runtime_feedback)
        merged_feedback.update(feedback)
        return merged_feedback

    def _collect_environment_runtime_feedback(
        self,
        *,
        primary_runtime: Any | None,
        related_tasks: list[Any],
    ) -> dict[str, object]:
        if self._environment_service is None:
            return {}
        candidate_runtimes: list[Any] = []
        seen_task_ids: set[str] = set()
        if primary_runtime is not None:
            candidate_runtimes.append(primary_runtime)
            primary_task_id = first_non_empty(getattr(primary_runtime, "task_id", None))
            if primary_task_id is not None:
                seen_task_ids.add(primary_task_id)
        for related_task in related_tasks:
            related_task_id = first_non_empty(getattr(related_task, "id", None))
            if related_task_id is None or related_task_id in seen_task_ids:
                continue
            seen_task_ids.add(related_task_id)
            related_runtime = self._task_runtime_repository.get_runtime(related_task_id)
            if related_runtime is not None:
                candidate_runtimes.append(related_runtime)
        candidate_runtimes.sort(
            key=lambda item: self._runtime_updated_sort_key(getattr(item, "updated_at", None)),
            reverse=True,
        )
        for candidate_runtime in candidate_runtimes:
            active_environment_ref = first_non_empty(
                getattr(candidate_runtime, "active_environment_id", None),
            )
            if active_environment_ref is None:
                continue
            runtime_feedback = self._runtime_feedback_from_environment_ref(
                active_environment_ref,
            )
            if runtime_feedback:
                return runtime_feedback
        return {}

    def _runtime_feedback_from_environment_ref(
        self,
        environment_ref: str,
    ) -> dict[str, object]:
        service = self._environment_service
        if service is None:
            return {}
        detail_payload: dict[str, object] | None = None
        get_session_detail = getattr(service, "get_session_detail", None)
        get_environment_detail = getattr(service, "get_environment_detail", None)
        normalized_ref = environment_ref.strip()
        if normalized_ref.startswith("session:") and callable(get_session_detail):
            detail_payload = self._dict_payload(get_session_detail(normalized_ref))
        if detail_payload is None and normalized_ref.startswith("env:") and callable(
            get_environment_detail,
        ):
            detail_payload = self._dict_payload(get_environment_detail(normalized_ref))
        if detail_payload is None and callable(get_environment_detail):
            for candidate_environment_id in self._candidate_environment_ids(normalized_ref):
                detail_payload = self._dict_payload(
                    get_environment_detail(candidate_environment_id),
                )
                if detail_payload is not None:
                    break
        if detail_payload is None:
            return {}
        feedback: dict[str, object] = {}
        for key in (
            "workspace_graph",
            "cooperative_adapter_availability",
            "host_contract",
            "recovery",
            "host_event_summary",
            "seat_runtime",
            "host_companion_session",
            "browser_site_contract",
            "desktop_app_contract",
            "host_twin",
            "host_twin_summary",
        ):
            section = detail_payload.get(key)
            if isinstance(section, dict):
                feedback[key] = dict(section)
        host_twin = feedback.get("host_twin")
        if isinstance(host_twin, dict):
            summary = build_host_twin_summary(
                host_twin,
                host_companion_session=feedback.get("host_companion_session"),
            )
            if summary is not None:
                feedback["host_twin_summary"] = summary
        return feedback

    def _candidate_environment_ids(self, environment_ref: str) -> list[str]:
        normalized_ref = environment_ref.strip()
        if not normalized_ref:
            return []
        if normalized_ref.startswith("env:"):
            return [normalized_ref]
        candidates: list[str] = []
        for prefix in (
            "env:session:",
            "env:browser:",
            "env:workspace:",
            "env:terminal:",
            "env:desktop:",
            "env:file-view:",
            "env:channel-session:",
            "env:observation-cache:",
        ):
            candidates.append(f"{prefix}{normalized_ref}")
        return candidates

    def _dict_payload(self, value: object) -> dict[str, object] | None:
        if isinstance(value, dict):
            return dict(value)
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            payload = model_dump(mode="json")
            if isinstance(payload, dict):
                return payload
        return None

    def _runtime_updated_sort_key(self, value: object) -> str:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat()
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
        return ""

    def list_schedules(self, limit: int | None = 5) -> list[dict[str, object]]:
        schedules = self._schedule_repository.list_schedules(limit=limit)
        payload: list[dict[str, object]] = []
        for schedule in schedules:
            route = schedule_route(schedule.id)
            actions = {"run": f"{route}/run", "delete": route}
            if schedule.status == "paused" or schedule.enabled is False:
                actions["resume"] = f"{route}/resume"
            else:
                actions["pause"] = f"{route}/pause"
            payload.append(
                {
                    "id": schedule.id,
                    "title": schedule.title,
                    "status": schedule.status,
                    "owner": schedule.target_user_id,
                    "cron": schedule.cron,
                    "enabled": schedule.enabled,
                    "task_type": schedule.task_type,
                    "updated_at": schedule.updated_at,
                    "last_run_at": schedule.last_run_at,
                    "next_run_at": schedule.next_run_at,
                    "last_error": schedule.last_error,
                    "route": route,
                    "actions": actions,
                },
            )
        return payload

    def get_schedule_detail(self, schedule_id: str) -> dict[str, object] | None:
        schedule = self._schedule_repository.get_schedule(schedule_id)
        if schedule is None or schedule.status == "deleted":
            return None

        route = schedule_route(schedule.id)
        actions = {"run": f"{route}/run", "delete": route}
        if schedule.status == "paused" or schedule.enabled is False:
            actions["resume"] = f"{route}/resume"
        else:
            actions["pause"] = f"{route}/pause"

        return {
            "schedule": schedule.model_dump(mode="json"),
            "spec": dict(schedule.spec_payload or {}),
            "runtime": {
                "status": schedule.status,
                "enabled": schedule.enabled,
                "last_run_at": schedule.last_run_at,
                "next_run_at": schedule.next_run_at,
                "last_error": schedule.last_error,
            },
            "route": route,
            "actions": actions,
        }

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

    def set_goal_service(self, goal_service: object | None) -> None:
        self._goal_service = goal_service

    def set_learning_service(self, learning_service: object | None) -> None:
        self._learning_service = learning_service

    def set_agent_profile_service(self, agent_profile_service: object | None) -> None:
        self._agent_profile_service = agent_profile_service

    def set_human_assist_task_service(self, human_assist_task_service: object | None) -> None:
        self._human_assist_task_service = human_assist_task_service

    def list_decision_requests(self, limit: int | None = 5) -> list[dict[str, object]]:
        decisions = self._decision_request_repository.list_decision_requests(limit=limit)
        payload: list[dict[str, object]] = []
        for decision in decisions:
            decision = self._maybe_expire_decision(decision)
            payload.append(self._serialize_decision_request(decision))
        return payload

    def set_kernel_dispatcher(self, kernel_dispatcher: object | None) -> None:
        self._kernel_dispatcher = kernel_dispatcher

    def set_runtime_event_bus(self, runtime_event_bus: object | None) -> None:
        self._runtime_event_bus = runtime_event_bus

    def get_decision_request(self, decision_id: str) -> dict[str, object] | None:
        decision = self._decision_request_repository.get_decision_request(decision_id)
        if decision is None:
            return None
        decision = self._maybe_expire_decision(decision)
        return self._serialize_decision_request(decision)

    def mark_decision_reviewing(self, decision_id: str) -> dict[str, object] | None:
        decision = self._decision_request_repository.get_decision_request(decision_id)
        if decision is None:
            return None
        decision = self._maybe_expire_decision(decision)
        if decision.status == "open":
            updated = decision.model_copy(update={"status": "reviewing"})
            decision = self._decision_request_repository.upsert_decision_request(updated)
            self._publish_runtime_event(
                topic="decision",
                action="reviewing",
                payload={
                    "decision_id": decision.id,
                    "task_id": decision.task_id,
                    "status": decision.status,
                },
            )
        return self._serialize_decision_request(decision)

    def _serialize_decision_request(self, decision) -> dict[str, object]:
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

    def _maybe_expire_decision(self, decision):
        if decision.status not in {"open", "reviewing"}:
            return decision
        expires_at = getattr(decision, "expires_at", None)
        if expires_at is None:
            return decision
        now = datetime.now(timezone.utc)
        if expires_at > now:
            return decision
        resolution = "Decision expired before confirmation."
        if self._kernel_dispatcher is not None:
            try:
                expire_method = getattr(self._kernel_dispatcher, "expire_decision", None)
                if callable(expire_method):
                    expire_method(decision.id, resolution=resolution)
                    refreshed = self._decision_request_repository.get_decision_request(decision.id)
                    return refreshed or decision
            except Exception:
                pass
        updated = decision.model_copy(
            update={
                "status": "expired",
                "resolution": resolution,
                "resolved_at": now,
            },
        )
        persisted = self._decision_request_repository.upsert_decision_request(updated)
        self._publish_runtime_event(
            topic="decision",
            action="expired",
            payload={
                "decision_id": persisted.id,
                "task_id": persisted.task_id,
                "status": persisted.status,
            },
        )
        return persisted

    def _resolve_goal(self, goal_id: str | None) -> dict[str, object] | None:
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

    def _collect_related_patches(
        self,
        *,
        goal_id: str | None,
        task_id: str | None,
        agent_ids: set[str],
        evidence_ids: set[str],
    ) -> list[dict[str, object]]:
        service = self._learning_service
        lister = getattr(service, "list_patches", None)
        if not callable(lister):
            return []
        related: list[dict[str, object]] = []
        for patch in list(lister()):
            patch_goal_id = getattr(patch, "goal_id", None)
            patch_task_id = getattr(patch, "task_id", None)
            patch_agent_id = getattr(patch, "agent_id", None)
            source_evidence_id = getattr(patch, "source_evidence_id", None)
            evidence_refs = {
                ref
                for ref in getattr(patch, "evidence_refs", [])
                if isinstance(ref, str) and ref
            }
            if goal_id and patch_goal_id == goal_id:
                related.append(patch.model_dump(mode="json"))
                continue
            if task_id and patch_task_id == task_id:
                related.append(patch.model_dump(mode="json"))
                continue
            if patch_agent_id in agent_ids:
                related.append(patch.model_dump(mode="json"))
                continue
            if source_evidence_id and source_evidence_id in evidence_ids:
                related.append(patch.model_dump(mode="json"))
                continue
            if evidence_refs.intersection(evidence_ids):
                related.append(patch.model_dump(mode="json"))
        related.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return related

    def _collect_related_growth(
        self,
        *,
        goal_id: str | None,
        task_id: str | None,
        agent_ids: set[str],
        evidence_ids: set[str],
        patch_ids: set[str],
    ) -> list[dict[str, object]]:
        service = self._learning_service
        lister = getattr(service, "list_growth", None)
        if not callable(lister):
            return []
        related: list[dict[str, object]] = []
        for event in list(lister(limit=200)):
            if goal_id and getattr(event, "goal_id", None) == goal_id:
                related.append(event.model_dump(mode="json"))
                continue
            if task_id and getattr(event, "task_id", None) == task_id:
                related.append(event.model_dump(mode="json"))
                continue
            if event.agent_id in agent_ids:
                related.append(event.model_dump(mode="json"))
                continue
            if event.source_patch_id and event.source_patch_id in patch_ids:
                related.append(event.model_dump(mode="json"))
                continue
            if event.source_evidence_id and event.source_evidence_id in evidence_ids:
                related.append(event.model_dump(mode="json"))
        related.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return related

    def _collect_related_agents(self, agent_ids: set[str]) -> list[dict[str, object]]:
        if not agent_ids:
            return []
        service = self._agent_profile_service
        getter = getattr(service, "get_agent", None)
        payload: list[dict[str, object]] = []
        for agent_id in sorted(agent_ids):
            agent = getter(agent_id) if callable(getter) else None
            if agent is None:
                payload.append(
                    {
                        "agent_id": agent_id,
                        "name": agent_id,
                        "status": "unknown",
                        "route": agent_route(agent_id),
                    },
                )
                continue
            model_dump = getattr(agent, "model_dump", None)
            agent_payload = (
                model_dump(mode="json")
                if callable(model_dump)
                else dict(agent)
                if isinstance(agent, dict)
                else {"agent_id": agent_id, "name": agent_id}
            )
            agent_payload["route"] = agent_route(agent_id)
            payload.append(agent_payload)
        return payload

    def _publish_runtime_event(
        self,
        *,
        topic: str,
        action: str,
        payload: dict[str, object],
    ) -> None:
        if self._runtime_event_bus is None:
            return
        self._runtime_event_bus.publish(
            topic=topic,
            action=action,
            payload=payload,
        )


Phase1StateQueryService = RuntimeCenterStateQueryService
RuntimeStateQueryService = RuntimeCenterStateQueryService
