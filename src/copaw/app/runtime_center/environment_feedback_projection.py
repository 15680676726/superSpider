# -*- coding: utf-8 -*-
"""Environment/runtime feedback projections for Runtime Center task detail."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...state.execution_feedback import collect_recent_execution_feedback
from .execution_runtime_projection import (
    attach_execution_runtime_projection,
    build_host_twin_summary,
    derive_host_twin_continuity_state,
)
from .projection_utils import (
    first_non_empty,
)


class RuntimeCenterEnvironmentFeedbackProjector:
    """Project execution feedback from task/runtime state and environment detail."""

    def __init__(
        self,
        *,
        task_repository: Any,
        task_runtime_repository: Any,
        evidence_ledger: Any | None = None,
        environment_service: object | None = None,
    ) -> None:
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._evidence_ledger = evidence_ledger
        self._environment_service = environment_service

    def collect_task_execution_feedback(
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
            return attach_execution_runtime_projection(feedback)
        merged_feedback = dict(runtime_feedback)
        merged_feedback.update(feedback)
        return attach_execution_runtime_projection(merged_feedback)

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
        existing_summary = feedback.get("host_twin_summary")
        if isinstance(existing_summary, dict):
            canonical_summary = dict(existing_summary)
            canonical_summary["continuity_state"] = first_non_empty(
                existing_summary.get("continuity_state"),
                derive_host_twin_continuity_state(canonical_summary),
            )
            feedback["host_twin_summary"] = canonical_summary
        elif isinstance(host_twin, dict):
            derived_summary = build_host_twin_summary(
                host_twin,
                host_companion_session=feedback.get("host_companion_session"),
            )
            if derived_summary is not None:
                feedback["host_twin_summary"] = derived_summary
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
