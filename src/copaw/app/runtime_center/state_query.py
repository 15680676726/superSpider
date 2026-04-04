# -*- coding: utf-8 -*-
"""State-backed read service for Runtime Center."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from ...evidence import EvidenceLedger
from ...industry.models import IndustrySeatCapabilityLayers
from ...kernel.decision_policy import (
    decision_chat_route,
    decision_chat_thread_id,
    decision_requires_human_confirmation,
)
from ...kernel.persistence import decode_kernel_task_metadata
from ...utils.runtime_routes import (
    agent_route,
    human_assist_task_current_route,
    human_assist_task_list_route,
    human_assist_task_route,
    schedule_route,
)
from ...state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteGoalRepository,
    SqliteRuntimeFrameRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
)
from .environment_feedback_projection import RuntimeCenterEnvironmentFeedbackProjector
from .goal_decision_projection import RuntimeCenterGoalDecisionProjector
from .task_detail_projection import RuntimeCenterTaskDetailProjector
from .task_list_projection import RuntimeCenterTaskListProjector
from .projection_utils import first_non_empty, string_list_from_values
from .work_context_projection import RuntimeCenterWorkContextProjector


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
        capability_candidate_service: object | None = None,
        capability_donor_service: object | None = None,
        capability_portfolio_service: object | None = None,
        skill_trial_service: object | None = None,
        skill_lifecycle_decision_service: object | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        learning_service: object | None = None,
        agent_profile_service: object | None = None,
        human_assist_task_service: object | None = None,
        environment_service: object | None = None,
        memory_activation_service: object | None = None,
    ) -> None:
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._runtime_frame_repository = runtime_frame_repository
        self._schedule_repository = schedule_repository
        self._goal_repository = goal_repository
        self._work_context_repository = work_context_repository
        self._goal_service = goal_service
        self._decision_request_repository = decision_request_repository
        self._capability_candidate_service = capability_candidate_service
        self._capability_donor_service = capability_donor_service
        self._capability_portfolio_service = capability_portfolio_service
        self._skill_trial_service = skill_trial_service
        self._skill_lifecycle_decision_service = skill_lifecycle_decision_service
        self._evidence_ledger = evidence_ledger
        self._learning_service = learning_service
        self._agent_profile_service = agent_profile_service
        self._human_assist_task_service = human_assist_task_service
        self._environment_service = environment_service
        self._memory_activation_service = memory_activation_service
        self._environment_feedback_projector = RuntimeCenterEnvironmentFeedbackProjector(
            task_repository=self._task_repository,
            task_runtime_repository=self._task_runtime_repository,
            evidence_ledger=self._evidence_ledger,
            environment_service=self._environment_service,
        )
        self._work_context_projector = RuntimeCenterWorkContextProjector(
            task_repository=self._task_repository,
            task_runtime_repository=self._task_runtime_repository,
            work_context_repository=self._work_context_repository,
            related_agents_loader=self._collect_related_agents,
        )
        self._goal_decision_projector = RuntimeCenterGoalDecisionProjector(
            goal_repository=self._goal_repository,
            goal_service=self._goal_service,
            decision_request_repository=self._decision_request_repository,
            task_repository=self._task_repository,
        )
        self._task_list_projector = RuntimeCenterTaskListProjector(
            task_repository=self._task_repository,
            task_runtime_repository=self._task_runtime_repository,
            work_context_loader=self._work_context_projector.serialize_work_context,
            activation_summary_builder=self._build_task_activation_summary,
        )
        self._task_detail_projector = RuntimeCenterTaskDetailProjector(
            task_repository=self._task_repository,
            task_runtime_repository=self._task_runtime_repository,
            runtime_frame_repository=self._runtime_frame_repository,
            decision_request_repository=self._decision_request_repository,
            evidence_ledger=self._evidence_ledger,
            goal_decision_projector=self._goal_decision_projector,
            environment_feedback_projector=self._environment_feedback_projector,
            work_context_projector=self._work_context_projector,
            related_patches_loader=self._collect_related_patches,
            related_growth_loader=self._collect_related_growth,
            related_agents_loader=self._collect_related_agents,
            memory_activation_service=self._memory_activation_service,
        )

    def list_tasks(self, limit: int | None = 5) -> list[dict[str, object]]:
        return self._task_list_projector.list_tasks(limit=limit)

    def list_kernel_tasks(
        self,
        *,
        phase: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, object]]:
        return self._task_list_projector.list_kernel_tasks(phase=phase, limit=limit)

    def get_task_detail(self, task_id: str) -> dict[str, object] | None:
        self._task_detail_projector.set_memory_activation_service(
            self._memory_activation_service,
        )
        return self._task_detail_projector.get_task_detail(task_id)

    def _build_task_activation_summary(
        self,
        *,
        task: object,
        runtime: object | None,
        kernel_metadata: dict[str, object] | None,
    ) -> dict[str, object] | None:
        self._task_detail_projector.set_memory_activation_service(
            self._memory_activation_service,
        )
        return self._task_detail_projector.build_task_activation_summary(
            task=task,
            runtime=runtime,
            kernel_metadata=kernel_metadata,
        )

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
        self._task_detail_projector.set_memory_activation_service(
            self._memory_activation_service,
        )
        return self._task_detail_projector.get_task_review(task_id)

    def list_capability_candidates(
        self,
        *,
        limit: int | None = 20,
    ) -> list[dict[str, object]]:
        service = getattr(self, "_capability_candidate_service", None)
        list_candidates = getattr(service, "list_candidates", None)
        if not callable(list_candidates):
            return []
        items = list_candidates(limit=limit)
        payload: list[dict[str, object]] = []
        for item in items:
            model_dump = getattr(item, "model_dump", None)
            serialized = model_dump(mode="json") if callable(model_dump) else None
            if isinstance(serialized, dict):
                payload.append(serialized)
        return payload

    def list_capability_trials(
        self,
        *,
        candidate_id: str | None = None,
        limit: int | None = 20,
    ) -> list[dict[str, object]]:
        service = getattr(self, "_skill_trial_service", None)
        lister = getattr(service, "list_trials", None)
        if not callable(lister):
            return []
        items = lister(candidate_id=candidate_id, limit=limit)
        payload: list[dict[str, object]] = []
        for item in items:
            model_dump = getattr(item, "model_dump", None)
            serialized = model_dump(mode="json") if callable(model_dump) else None
            if isinstance(serialized, dict):
                payload.append(serialized)
        return payload

    def list_capability_donors(
        self,
        *,
        limit: int | None = 20,
    ) -> list[dict[str, object]]:
        service = getattr(self, "_capability_donor_service", None)
        lister = getattr(service, "list_donors", None)
        if not callable(lister):
            return []
        items = lister(limit=limit)
        payload: list[dict[str, object]] = []
        for item in items:
            model_dump = getattr(item, "model_dump", None)
            serialized = model_dump(mode="json") if callable(model_dump) else None
            if isinstance(serialized, dict):
                payload.append(serialized)
        return payload

    def list_capability_source_profiles(
        self,
        *,
        limit: int | None = 20,
    ) -> list[dict[str, object]]:
        service = getattr(self, "_capability_donor_service", None)
        lister = getattr(service, "list_source_profiles", None)
        if not callable(lister):
            return []
        items = lister(limit=limit)
        payload: list[dict[str, object]] = []
        for item in items:
            model_dump = getattr(item, "model_dump", None)
            serialized = model_dump(mode="json") if callable(model_dump) else None
            if isinstance(serialized, dict):
                payload.append(serialized)
        return payload

    def get_capability_portfolio_summary(self) -> dict[str, object]:
        service = getattr(self, "_capability_portfolio_service", None)
        getter = getattr(service, "get_runtime_portfolio_summary", None)
        base_payload = getter() if callable(getter) else {}
        base = dict(base_payload) if isinstance(base_payload, Mapping) else {}

        governed_candidates, fallback_candidates = self._partition_capability_candidates()
        governed_donor_ids = {
            donor_id
            for donor_id in (
                self._string_value(item.get("donor_id")) for item in governed_candidates
            )
            if donor_id is not None
        }
        governed_source_profile_ids = {
            source_profile_id
            for source_profile_id in (
                self._string_value(item.get("source_profile_id"))
                for item in governed_candidates
            )
            if source_profile_id is not None
        }
        source_profiles = [
            item
            for item in self._service_payloads(
                getattr(self, "_capability_donor_service", None),
                "list_source_profiles",
            )
            if (
                self._string_value(item.get("source_profile_id"))
                in governed_source_profile_ids
            )
        ]
        trust_records = [
            item
            for item in self._service_payloads(
                getattr(self, "_capability_donor_service", None),
                "list_trust_records",
            )
            if self._string_value(item.get("donor_id")) in governed_donor_ids
        ]
        trials = self._service_payloads(
            getattr(self, "_skill_trial_service", None),
            "list_trials",
        )
        decisions = self._service_payloads(
            getattr(self, "_skill_lifecycle_decision_service", None),
            "list_decisions",
        )
        candidate_by_id = {
            candidate_id: item
            for item in governed_candidates
            if (candidate_id := self._string_value(item.get("candidate_id"))) is not None
        }

        active_donor_ids = {
            donor_id
            for item in governed_candidates
            if self._candidate_is_active(item)
            and (donor_id := self._string_value(item.get("donor_id"))) is not None
        }
        candidate_donor_ids = {
            donor_id
            for item in governed_candidates
            if not self._candidate_is_active(item)
            and not self._candidate_is_retired(item)
            and (donor_id := self._string_value(item.get("donor_id"))) is not None
        }
        trial_donor_ids = {
            donor_id
            for item in governed_candidates
            if self._candidate_is_trial(item)
            and (donor_id := self._string_value(item.get("donor_id"))) is not None
        }
        for item in trials:
            candidate = candidate_by_id.get(self._string_value(item.get("candidate_id")) or "")
            donor_id = self._string_value((candidate or {}).get("donor_id"))
            if donor_id is not None:
                trial_donor_ids.add(donor_id)

        replace_pressure_ids: set[str] = set()
        retire_pressure_ids: set[str] = set()
        for item in decisions:
            candidate = candidate_by_id.get(self._string_value(item.get("candidate_id")) or "")
            donor_id = self._string_value((candidate or {}).get("donor_id"))
            if donor_id is None:
                continue
            decision_kind = (self._string_value(item.get("decision_kind")) or "").lower()
            if decision_kind == "retire":
                retire_pressure_ids.add(donor_id)
            if decision_kind in {"replace_existing", "rollback"}:
                replace_pressure_ids.add(donor_id)

        degraded_donor_ids = set(replace_pressure_ids)
        for item in trust_records:
            donor_id = self._string_value(item.get("donor_id"))
            if donor_id is None:
                continue
            success_count = self._int_value(item.get("trial_success_count"))
            failure_count = self._int_value(item.get("trial_failure_count"))
            rollback_count = self._int_value(item.get("rollback_count"))
            retirement_count = self._int_value(item.get("retirement_count"))
            if (
                failure_count > success_count
                or rollback_count > 0
                or retirement_count > 0
            ):
                degraded_donor_ids.add(donor_id)

        density_budget = max(
            1,
            self._int_value(getattr(service, "_density_budget", None), default=3),
        )
        scope_breakdown, over_budget_scopes = self._build_capability_scope_breakdown(
            governed_candidates,
            density_budget=density_budget,
        )

        trusted_source_count = sum(
            1
            for item in source_profiles
            if (self._string_value(item.get("trust_posture")) or "").lower() == "trusted"
        )
        watchlist_source_count = sum(
            1
            for item in source_profiles
            if (self._string_value(item.get("trust_posture")) or "").lower() == "watchlist"
        )

        planning_actions: list[dict[str, object]] = []
        if len(candidate_donor_ids) > len(trial_donor_ids):
            planning_actions.append(
                {
                    "action": "run_scoped_trial",
                    "summary": "At least one governed donor still lacks a scoped trial.",
                },
            )
        if replace_pressure_ids:
            planning_actions.append(
                {
                    "action": "review_replacement_pressure",
                    "summary": "Some governed donors carry replacement or rollback pressure.",
                },
            )
        if retire_pressure_ids:
            planning_actions.append(
                {
                    "action": "review_retirement_pressure",
                    "summary": "A governed donor is pending retirement governance.",
                },
            )
        if over_budget_scopes:
            planning_actions.append(
                {
                    "action": "compact_over_budget_scope",
                    "summary": "One or more governed scopes exceeded donor density budget.",
                },
            )

        if not governed_candidates and not base:
            return {}

        return {
            "donor_count": len(governed_donor_ids),
            "active_donor_count": len(active_donor_ids),
            "candidate_donor_count": len(candidate_donor_ids),
            "trial_donor_count": len(trial_donor_ids),
            "trusted_source_count": trusted_source_count,
            "watchlist_source_count": watchlist_source_count,
            "degraded_donor_count": len(degraded_donor_ids),
            "replace_pressure_count": len(replace_pressure_ids),
            "retire_pressure_count": len(retire_pressure_ids),
            "over_budget_scope_count": len(over_budget_scopes),
            "over_budget_scopes": over_budget_scopes,
            "fallback_only_candidate_count": len(fallback_candidates),
            "scope_breakdown": scope_breakdown,
            "planning_actions": planning_actions,
            "routes": {
                "portfolio": "/api/runtime-center/capabilities/portfolio",
                "donors": "/api/runtime-center/capabilities/donors",
                "source_profiles": "/api/runtime-center/capabilities/source-profiles",
                "discovery": "/api/runtime-center/capabilities/discovery",
                "trials": "/api/runtime-center/capabilities/trials",
                "lifecycle_decisions": "/api/runtime-center/capabilities/lifecycle-decisions",
            },
        }

    def get_capability_discovery_summary(self) -> dict[str, object]:
        governed_candidates, fallback_candidates = self._partition_capability_candidates()
        governed_source_profile_ids = {
            source_profile_id
            for source_profile_id in (
                self._string_value(item.get("source_profile_id"))
                for item in governed_candidates
            )
            if source_profile_id is not None
        }
        fallback_source_profile_ids = {
            source_profile_id
            for source_profile_id in (
                self._string_value(item.get("source_profile_id"))
                for item in fallback_candidates
            )
            if source_profile_id is not None
        }
        source_profiles = self._service_payloads(
            getattr(self, "_capability_donor_service", None),
            "list_source_profiles",
        )
        governed_source_profiles = [
            item
            for item in source_profiles
            if (
                self._string_value(item.get("source_profile_id"))
                in governed_source_profile_ids
            )
        ]
        fallback_source_profiles = [
            item
            for item in source_profiles
            if (
                self._string_value(item.get("source_profile_id"))
                in fallback_source_profile_ids
            )
        ]
        if not governed_source_profiles and not fallback_source_profiles:
            return {}

        active_source_count = sum(
            1 for item in governed_source_profiles if bool(item.get("active", True))
        )
        trusted_source_count = sum(
            1
            for item in governed_source_profiles
            if (self._string_value(item.get("trust_posture")) or "").lower() == "trusted"
        )
        watchlist_source_count = sum(
            1
            for item in governed_source_profiles
            if (self._string_value(item.get("trust_posture")) or "").lower() == "watchlist"
        )
        by_source_kind = dict(
            sorted(
                Counter(
                    (self._string_value(item.get("source_kind")) or "unknown")
                    for item in governed_source_profiles
                ).items(),
            ),
        )
        trust_posture_count = dict(
            sorted(
                Counter(
                    (self._string_value(item.get("trust_posture")) or "unknown")
                    for item in governed_source_profiles
                ).items(),
            ),
        )
        degraded_components: list[dict[str, object]] = []
        status = "ready"
        if active_source_count <= 0:
            status = "degraded"
            degraded_components.append(
                {
                    "component": "source-availability",
                    "status": "degraded",
                    "summary": "No governed donor discovery source is currently active.",
                },
            )
        elif trusted_source_count <= 0 and watchlist_source_count > 0:
            status = "degraded"
            degraded_components.append(
                {
                    "component": "source-trust",
                    "status": "degraded",
                    "summary": "Discovery is currently relying on watchlist donor sources only.",
                },
            )
        summary = (
            "Governed donor discovery is running with trusted sources available."
            if status == "ready"
            else "Governed donor discovery is available, but current source posture is degraded."
        )
        return {
            "status": status,
            "summary": summary,
            "source_profile_count": len(governed_source_profiles),
            "active_source_count": active_source_count,
            "trusted_source_count": trusted_source_count,
            "watchlist_source_count": watchlist_source_count,
            "fallback_only_source_count": len(fallback_source_profiles),
            "by_source_kind": by_source_kind,
            "trust_posture_count": trust_posture_count,
            "degraded_components": degraded_components,
            "routes": {
                "portfolio": "/api/runtime-center/capabilities/portfolio",
                "source_profiles": "/api/runtime-center/capabilities/source-profiles",
                "discovery": "/api/runtime-center/capabilities/discovery",
            },
        }

    def list_capability_lifecycle_decisions(
        self,
        *,
        candidate_id: str | None = None,
        limit: int | None = 20,
    ) -> list[dict[str, object]]:
        service = getattr(self, "_skill_lifecycle_decision_service", None)
        lister = getattr(service, "list_decisions", None)
        if not callable(lister):
            return []
        items = lister(candidate_id=candidate_id, limit=limit)
        payload: list[dict[str, object]] = []
        for item in items:
            model_dump = getattr(item, "model_dump", None)
            serialized = model_dump(mode="json") if callable(model_dump) else None
            if isinstance(serialized, dict):
                payload.append(serialized)
        return payload

    def list_work_contexts(self, limit: int | None = 5) -> list[dict[str, object]]:
        return self._work_context_projector.list_work_contexts(limit=limit)

    def count_work_contexts(self) -> int:
        return self._work_context_projector.count_work_contexts()

    def get_work_context_detail(self, context_id: str) -> dict[str, object] | None:
        return self._work_context_projector.get_work_context_detail(context_id)

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
        return self._goal_decision_projector.list_goals(limit=limit)

    def get_goal_detail(self, goal_id: str) -> dict[str, object] | None:
        return self._goal_decision_projector.get_goal_detail(goal_id)

    def set_goal_service(self, goal_service: object | None) -> None:
        self._goal_service = goal_service
        self._goal_decision_projector.set_goal_service(goal_service)

    def set_learning_service(self, learning_service: object | None) -> None:
        self._learning_service = learning_service

    def set_agent_profile_service(self, agent_profile_service: object | None) -> None:
        self._agent_profile_service = agent_profile_service

    def set_human_assist_task_service(self, human_assist_task_service: object | None) -> None:
        self._human_assist_task_service = human_assist_task_service

    def list_decision_requests(self, limit: int | None = 5) -> list[dict[str, object]]:
        return self._goal_decision_projector.list_decision_requests(limit=limit)

    def get_decision_request(self, decision_id: str) -> dict[str, object] | None:
        return self._goal_decision_projector.get_decision_request(decision_id)

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
        detail_getter = getattr(service, "get_agent_detail", None)
        payload: list[dict[str, object]] = []
        for agent_id in sorted(agent_ids):
            agent_detail = detail_getter(agent_id) if callable(detail_getter) else None
            if agent_detail is not None:
                agent_payload = self._agent_payload_from_detail(agent_id, agent_detail)
            else:
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
                governance = self._project_agent_capability_governance(
                    agent_payload=agent_payload,
                    runtime_payload=None,
                )
                if governance is not None:
                    agent_payload["capability_governance"] = governance
            if not isinstance(agent_payload, dict):
                payload.append(
                    {
                        "agent_id": agent_id,
                        "name": agent_id,
                        "status": "unknown",
                        "route": agent_route(agent_id),
                    },
                )
                continue
            agent_payload["route"] = agent_route(agent_id)
            payload.append(agent_payload)
        return payload

    def _agent_payload_from_detail(
        self,
        agent_id: str,
        detail: object,
    ) -> dict[str, object]:
        detail_payload = self._mapping_payload(detail)
        agent_payload = self._mapping_payload(detail_payload.get("agent"))
        if not agent_payload:
            agent_payload = {"agent_id": agent_id, "name": agent_id}
        runtime_payload = self._mapping_payload(detail_payload.get("runtime"))
        governance = self._project_agent_capability_governance(
            agent_payload=agent_payload,
            runtime_payload=runtime_payload,
        )
        if governance is not None:
            agent_payload["capability_governance"] = governance
        return agent_payload

    def _project_agent_capability_governance(
        self,
        *,
        agent_payload: Mapping[str, object],
        runtime_payload: Mapping[str, object] | None,
    ) -> dict[str, object] | None:
        runtime_payload = runtime_payload or {}
        metadata = self._mapping_payload(runtime_payload.get("metadata"))
        capability_layers = IndustrySeatCapabilityLayers.from_metadata(
            metadata.get("capability_layers"),
        )
        if not capability_layers.merged_capability_ids():
            return None
        layers_payload = capability_layers.to_metadata_payload()
        overlay_payload = self._mapping_payload(metadata.get("current_session_overlay"))
        overlay_capability_ids = list(
            dict.fromkeys(
                string_list_from_values(
                    overlay_payload.get("capability_ids"),
                    layers_payload.get("session_overlay_capability_ids"),
                ),
            ),
        )
        current_session_overlay: dict[str, object] | None = None
        if overlay_payload or overlay_capability_ids:
            current_session_overlay = {
                **overlay_payload,
                "overlay_scope": first_non_empty(
                    overlay_payload.get("overlay_scope"),
                    "session",
                ),
                "overlay_mode": first_non_empty(
                    overlay_payload.get("overlay_mode"),
                    "additive" if overlay_capability_ids else None,
                ),
                "capability_ids": overlay_capability_ids,
                "status": first_non_empty(
                    overlay_payload.get("status"),
                    "active" if overlay_capability_ids else None,
                ),
            }
        return {
            "is_projection": True,
            "is_truth_store": False,
            "source": "agent_runtime.metadata.capability_layers",
            "layers": layers_payload,
            "counts": {
                "role_prototype": len(
                    string_list_from_values(
                        layers_payload.get("role_prototype_capability_ids"),
                    ),
                ),
                "seat_instance": len(
                    string_list_from_values(
                        layers_payload.get("seat_instance_capability_ids"),
                    ),
                ),
                "cycle_delta": len(
                    string_list_from_values(
                        layers_payload.get("cycle_delta_capability_ids"),
                    ),
                ),
                "session_overlay": len(
                    string_list_from_values(
                        layers_payload.get("session_overlay_capability_ids"),
                    ),
                ),
                "effective": len(
                    string_list_from_values(layers_payload.get("effective_capability_ids")),
                ),
            },
            "current_session_overlay": current_session_overlay,
            "lifecycle": {
                "employment_mode": first_non_empty(
                    runtime_payload.get("employment_mode"),
                    agent_payload.get("employment_mode"),
                ),
                "activation_mode": first_non_empty(
                    runtime_payload.get("activation_mode"),
                    agent_payload.get("activation_mode"),
                ),
                "desired_state": first_non_empty(runtime_payload.get("desired_state")),
                "runtime_status": first_non_empty(runtime_payload.get("runtime_status")),
                "status": first_non_empty(agent_payload.get("status")),
            },
        }

    def _mapping_payload(self, value: object) -> dict[str, object]:
        if isinstance(value, Mapping):
            return dict(value)
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            payload = model_dump(mode="json")
            if isinstance(payload, Mapping):
                return dict(payload)
        namespace = getattr(value, "__dict__", None)
        if isinstance(namespace, Mapping):
            return dict(namespace)
        return {}

    def _service_payloads(
        self,
        service: object | None,
        method_name: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        method = getattr(service, method_name, None)
        if not callable(method):
            return []
        kwargs = {"limit": limit} if limit is not None else {"limit": None}
        try:
            items = method(**kwargs)
        except TypeError:
            items = method()
        if not isinstance(items, list):
            return []
        payload: list[dict[str, Any]] = []
        for item in items:
            serialized = self._mapping_payload(item)
            if serialized:
                payload.append(dict(serialized))
        return payload

    def _partition_capability_candidates(
        self,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        payload = self._service_payloads(
            getattr(self, "_capability_candidate_service", None),
            "list_candidates",
        )
        governed: list[dict[str, Any]] = []
        fallback_only: list[dict[str, Any]] = []
        for item in payload:
            source_kind = (self._string_value(item.get("candidate_source_kind")) or "").lower()
            ingestion_mode = (self._string_value(item.get("ingestion_mode")) or "").lower()
            if source_kind == "local_authored" or ingestion_mode == "baseline-import":
                fallback_only.append(item)
                continue
            governed.append(item)
        return governed, fallback_only

    def _build_capability_scope_breakdown(
        self,
        candidates: list[dict[str, Any]],
        *,
        density_budget: int,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in candidates:
            if self._candidate_is_retired(item):
                continue
            target_scope = self._string_value(item.get("target_scope")) or "global"
            target_role_id = self._string_value(item.get("target_role_id")) or "*"
            target_seat_ref = self._string_value(item.get("target_seat_ref")) or "*"
            scope_key = f"{target_scope}:{target_role_id}:{target_seat_ref}"
            groups.setdefault(scope_key, []).append(item)
        breakdown: list[dict[str, object]] = []
        over_budget: list[dict[str, object]] = []
        for scope_key, items in sorted(groups.items()):
            donor_ids = {
                donor_id
                for donor_id in (
                    self._string_value(item.get("donor_id")) for item in items
                )
                if donor_id is not None
            }
            source_kind_count = dict(
                sorted(
                    Counter(
                        (self._string_value(item.get("candidate_source_kind")) or "unknown")
                        for item in items
                    ).items(),
                ),
            )
            first = items[0]
            entry = {
                "scope_key": scope_key,
                "target_scope": self._string_value(first.get("target_scope")) or "global",
                "target_role_id": self._string_value(first.get("target_role_id")),
                "target_seat_ref": self._string_value(first.get("target_seat_ref")),
                "donor_count": len(donor_ids),
                "candidate_count": len(items),
                "active_candidate_count": sum(1 for item in items if self._candidate_is_active(item)),
                "trial_candidate_count": sum(1 for item in items if self._candidate_is_trial(item)),
                "source_kind_count": source_kind_count,
            }
            breakdown.append(entry)
            if len(donor_ids) > density_budget:
                over_budget.append(
                    {
                        "scope_key": scope_key,
                        "count": len(donor_ids),
                    },
                )
        breakdown.sort(
            key=lambda item: (
                -self._int_value(item.get("donor_count")),
                str(item.get("scope_key") or ""),
            ),
        )
        return breakdown, over_budget

    def _candidate_is_active(self, payload: Mapping[str, Any]) -> bool:
        status = (self._string_value(payload.get("status")) or "").lower()
        stage = (self._string_value(payload.get("lifecycle_stage")) or "").lower()
        return status == "active" or stage == "active"

    def _candidate_is_trial(self, payload: Mapping[str, Any]) -> bool:
        status = (self._string_value(payload.get("status")) or "").lower()
        stage = (self._string_value(payload.get("lifecycle_stage")) or "").lower()
        return status == "trial" or stage == "trial"

    def _candidate_is_retired(self, payload: Mapping[str, Any]) -> bool:
        status = (self._string_value(payload.get("status")) or "").lower()
        stage = (self._string_value(payload.get("lifecycle_stage")) or "").lower()
        return status == "retired" or stage == "retired"

    def _string_value(self, value: object | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _int_value(self, value: object | None, *, default: int = 0) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = self._string_value(value)
        if text is None:
            return default
        try:
            return int(text)
        except ValueError:
            return default

Phase1StateQueryService = RuntimeCenterStateQueryService
RuntimeStateQueryService = RuntimeCenterStateQueryService
