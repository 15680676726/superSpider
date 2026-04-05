# -*- coding: utf-8 -*-
"""State-backed read service for Runtime Center."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from ...evidence import EvidenceLedger
from ...industry.models import IndustrySeatCapabilityLayers
from ...learning.skill_gap_detector import SkillGapDetector
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
from .execution_runtime_projection import summarize_execution_knowledge_writeback
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
        donor_source_service: object | None = None,
        capability_candidate_service: object | None = None,
        capability_donor_service: object | None = None,
        donor_package_service: object | None = None,
        donor_trust_service: object | None = None,
        capability_portfolio_service: object | None = None,
        donor_scout_service: object | None = None,
        skill_trial_service: object | None = None,
        skill_lifecycle_decision_service: object | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        learning_service: object | None = None,
        agent_profile_service: object | None = None,
        human_assist_task_service: object | None = None,
        environment_service: object | None = None,
        external_runtime_service: object | None = None,
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
        self._donor_source_service = donor_source_service
        self._capability_candidate_service = capability_candidate_service
        self._capability_donor_service = capability_donor_service
        self._donor_package_service = donor_package_service
        self._donor_trust_service = donor_trust_service
        self._capability_portfolio_service = capability_portfolio_service
        self._donor_scout_service = donor_scout_service
        self._skill_trial_service = skill_trial_service
        self._skill_lifecycle_decision_service = skill_lifecycle_decision_service
        self._evidence_ledger = evidence_ledger
        self._learning_service = learning_service
        self._agent_profile_service = agent_profile_service
        self._human_assist_task_service = human_assist_task_service
        self._environment_service = environment_service
        self._external_runtime_service = external_runtime_service
        self._memory_activation_service = memory_activation_service
        self._skill_gap_detector = SkillGapDetector()
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
            serialized = self._serialize_capability_candidate(item)
            if serialized:
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

    def list_external_runtimes(
        self,
        *,
        capability_id: str | None = None,
        status: str | None = None,
        scope_kind: str | None = None,
        limit: int | None = 20,
    ) -> list[dict[str, object]]:
        service = getattr(self, "_external_runtime_service", None)
        lister = getattr(service, "list_runtimes", None)
        if not callable(lister):
            return []
        items = lister(
            capability_id=capability_id,
            status=status,
            scope_kind=scope_kind,
            limit=limit,
        )
        payload: list[dict[str, object]] = []
        for item in items:
            model_dump = getattr(item, "model_dump", None)
            serialized = model_dump(mode="json") if callable(model_dump) else None
            if not isinstance(serialized, dict):
                continue
            runtime_id = str(serialized.get("runtime_id") or "").strip()
            if runtime_id:
                serialized["route"] = f"/api/runtime-center/external-runtimes/{runtime_id}"
            payload.append(serialized)
        return payload

    def get_external_runtime_detail(self, runtime_id: str) -> dict[str, object] | None:
        service = getattr(self, "_external_runtime_service", None)
        getter = getattr(service, "get_runtime", None)
        if not callable(getter):
            return None
        item = getter(runtime_id)
        if item is None:
            return None
        model_dump = getattr(item, "model_dump", None)
        payload = model_dump(mode="json") if callable(model_dump) else None
        if not isinstance(payload, dict):
            payload = {}
        return {
            "runtime": payload,
            "route": f"/api/runtime-center/external-runtimes/{runtime_id}",
        }

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

    def list_capability_packages(
        self,
        *,
        donor_id: str | None = None,
        limit: int | None = 20,
    ) -> list[dict[str, object]]:
        service = getattr(self, "_donor_package_service", None)
        lister = getattr(service, "list_packages", None)
        if not callable(lister):
            return []
        items = lister(donor_id=donor_id, limit=limit)
        payload: list[dict[str, object]] = []
        for item in items:
            model_dump = getattr(item, "model_dump", None)
            serialized = model_dump(mode="json") if callable(model_dump) else None
            if isinstance(serialized, dict):
                payload.append(serialized)
            elif isinstance(item, dict):
                payload.append(dict(item))
        return payload

    def list_capability_trust_records(
        self,
        *,
        limit: int | None = 20,
    ) -> list[dict[str, object]]:
        service = getattr(self, "_donor_trust_service", None)
        refresher = getattr(service, "refresh_trust_records", None)
        if callable(refresher):
            refresher()
        lister = getattr(service, "list_trust_records", None)
        if not callable(lister):
            return []
        items = lister(limit=limit)
        payload: list[dict[str, object]] = []
        for item in items:
            model_dump = getattr(item, "model_dump", None)
            serialized = model_dump(mode="json") if callable(model_dump) else None
            if isinstance(serialized, dict):
                payload.append(serialized)
            elif isinstance(item, dict):
                payload.append(dict(item))
        return payload

    def get_capability_portfolio_summary(self) -> dict[str, object]:
        service = getattr(self, "_capability_portfolio_service", None)
        getter = getattr(service, "get_runtime_portfolio_summary", None)
        payload = getter() if callable(getter) else {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def get_capability_discovery_summary(self) -> dict[str, object]:
        service = getattr(self, "_capability_portfolio_service", None)
        getter = getattr(service, "get_runtime_discovery_summary", None)
        payload = getter() if callable(getter) else {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def get_capability_scout_summary(self) -> dict[str, object]:
        service = getattr(self, "_donor_scout_service", None)
        getter = getattr(service, "get_latest_summary", None)
        payload = getter() if callable(getter) else {}
        return dict(payload) if isinstance(payload, Mapping) else {}

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

    def _serialize_capability_candidate(self, item: object) -> dict[str, object] | None:
        model_dump = getattr(item, "model_dump", None)
        serialized = model_dump(mode="json") if callable(model_dump) else None
        if not isinstance(serialized, dict):
            return None
        candidate_id = str(serialized.get("candidate_id") or "").strip()
        lifecycle_history = self._candidate_lifecycle_history(candidate_id)
        adapter_status = self._candidate_adapter_assimilation_status(
            candidate_id,
            candidate_payload=serialized,
        )
        return {
            **serialized,
            "supply_path": self._candidate_supply_path(serialized),
            "provenance": {
                "candidate_kind": serialized.get("candidate_kind"),
                "candidate_source_kind": serialized.get("candidate_source_kind"),
                "candidate_source_ref": serialized.get("candidate_source_ref"),
                "candidate_source_version": serialized.get("candidate_source_version"),
                "candidate_source_lineage": serialized.get("candidate_source_lineage"),
                "ingestion_mode": serialized.get("ingestion_mode"),
                "donor_id": serialized.get("donor_id"),
                "package_id": serialized.get("package_id"),
                "source_profile_id": serialized.get("source_profile_id"),
                "canonical_package_id": serialized.get("canonical_package_id"),
                "protection_flags": list(serialized.get("protection_flags") or []),
            },
            **adapter_status,
            "lifecycle_history": lifecycle_history,
            "drift_reentry": self._skill_gap_detector.build_reentry_summary(
                trial_summary=lifecycle_history,
                latest_decision_kind=str(lifecycle_history.get("latest_decision_kind") or ""),
            ),
        }

    def _candidate_supply_path(self, payload: Mapping[str, object]) -> str:
        metadata = self._mapping_payload(payload.get("metadata"))
        resolution_kind = first_non_empty(
            metadata.get("resolution_kind"),
            payload.get("resolution_kind"),
        )
        ingestion_mode = first_non_empty(payload.get("ingestion_mode")) or ""
        source_kind = first_non_empty(payload.get("candidate_source_kind")) or ""
        mapping = {
            "reuse_existing_candidate": "healthy-reuse",
            "adopt_registered_package": "registered-package",
            "adopt_external_donor": "external-donor",
            "author_local_fallback": "local-fallback",
        }
        if resolution_kind in mapping:
            return mapping[str(resolution_kind)]
        if ingestion_mode == "baseline-import":
            return "baseline-import"
        if source_kind == "local_authored":
            return "local-fallback"
        return "external-donor"

    def _candidate_lifecycle_history(self, candidate_id: str) -> dict[str, object]:
        if not candidate_id:
            return {
                "trial_count": 0,
                "decision_count": 0,
                "latest_trial_verdict": None,
                "latest_decision_kind": None,
            }
        trial_service = getattr(self, "_skill_trial_service", None)
        decision_service = getattr(self, "_skill_lifecycle_decision_service", None)
        list_trials = getattr(trial_service, "list_trials", None)
        list_decisions = getattr(decision_service, "list_decisions", None)
        verdict_summary = getattr(trial_service, "get_candidate_verdict_summary", None)
        trials = list_trials(candidate_id=candidate_id, limit=50) if callable(list_trials) else []
        decisions = (
            list_decisions(candidate_id=candidate_id, limit=50) if callable(list_decisions) else []
        )
        summary = (
            verdict_summary(candidate_id=candidate_id)
            if callable(verdict_summary)
            else {}
        )
        latest_trial_verdict = None
        if trials:
            latest_trial_verdict = getattr(trials[0], "verdict", None)
        latest_decision_kind = None
        if decisions:
            latest_decision_kind = getattr(decisions[0], "decision_kind", None)
        return {
            "trial_count": len(trials),
            "decision_count": len(decisions),
            "latest_trial_verdict": latest_trial_verdict,
            "latest_decision_kind": latest_decision_kind,
            "aggregate_verdict": (
                summary.get("aggregate_verdict")
                if isinstance(summary, Mapping)
                else None
            ),
            "operator_intervention_count": (
                summary.get("operator_intervention_count")
                if isinstance(summary, Mapping)
                else 0
            ),
            "scope_verdicts": (
                dict(summary.get("scope_verdicts"))
                if isinstance(summary, Mapping)
                and isinstance(summary.get("scope_verdicts"), Mapping)
                else {}
            ),
        }

    def _candidate_adapter_assimilation_status(
        self,
        candidate_id: str,
        *,
        candidate_payload: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        candidate_metadata = self._mapping_payload(
            self._mapping_payload(candidate_payload).get("metadata"),
        )
        trial_service = getattr(self, "_skill_trial_service", None)
        decision_service = getattr(self, "_skill_lifecycle_decision_service", None)
        list_trials = getattr(trial_service, "list_trials", None)
        list_decisions = getattr(decision_service, "list_decisions", None)
        trial_metadata = {}
        decision_metadata = {}
        if candidate_id:
            trials = (
                list_trials(candidate_id=candidate_id, limit=1)
                if callable(list_trials)
                else []
            )
            if trials:
                trial_metadata = self._mapping_payload(getattr(trials[0], "metadata", None))
            decisions = (
                list_decisions(candidate_id=candidate_id, limit=1)
                if callable(list_decisions)
                else []
            )
            if decisions:
                decision_metadata = self._mapping_payload(
                    getattr(decisions[0], "metadata", None),
                )

        merged: dict[str, object] = {}
        for payload in (candidate_metadata, trial_metadata, decision_metadata):
            if not payload:
                continue
            for key in (
                "protocol_surface_kind",
                "transport_kind",
                "compiled_adapter_id",
                "selected_adapter_action_id",
            ):
                value = first_non_empty(payload.get(key))
                if value is not None:
                    merged[key] = value
            compiled_action_ids = string_list_from_values(payload.get("compiled_action_ids"))
            if compiled_action_ids:
                merged["compiled_action_ids"] = compiled_action_ids
            promotion_blockers = string_list_from_values(
                payload.get("adapter_blockers"),
                payload.get("promotion_blockers"),
            )
            if promotion_blockers:
                merged["promotion_blockers"] = promotion_blockers
        merged.setdefault("compiled_action_ids", [])
        merged.setdefault("promotion_blockers", [])
        return merged

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
        knowledge_writeback = summarize_execution_knowledge_writeback(
            self._mapping_payload(runtime_payload.get("metadata")).get("knowledge_writeback"),
        )
        if knowledge_writeback is not None:
            agent_payload["latest_knowledge_writeback"] = knowledge_writeback
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

Phase1StateQueryService = RuntimeCenterStateQueryService
RuntimeStateQueryService = RuntimeCenterStateQueryService
