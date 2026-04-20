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
    task_route,
)
from ...state.repositories import (
    SqliteAgentReportRepository,
    SqliteAssignmentRepository,
    SqliteBacklogItemRepository,
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
from .task_review_projection import serialize_evidence_record
from .task_detail_projection import RuntimeCenterTaskDetailProjector
from .task_list_projection import RuntimeCenterTaskListProjector
from .projection_utils import first_non_empty, string_list_from_values
from .work_context_projection import RuntimeCenterWorkContextProjector


class RuntimeCenterReadModelUnavailableError(RuntimeError):
    """Raised when a Runtime Center read chain is missing a required service."""


class RuntimeCenterStateQueryService:
    """Read-only Runtime Center state queries."""

    def __init__(
        self,
        *,
        task_repository: SqliteTaskRepository,
        task_runtime_repository: SqliteTaskRuntimeRepository,
        runtime_frame_repository: SqliteRuntimeFrameRepository | None = None,
        schedule_repository: SqliteScheduleRepository,
        backlog_item_repository: SqliteBacklogItemRepository | None = None,
        assignment_repository: SqliteAssignmentRepository | None = None,
        agent_report_repository: SqliteAgentReportRepository | None = None,
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
        weixin_ilink_runtime_state: object | None = None,
        memory_activation_service: object | None = None,
        knowledge_graph_service: object | None = None,
    ) -> None:
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._runtime_frame_repository = runtime_frame_repository
        self._schedule_repository = schedule_repository
        self._backlog_item_repository = backlog_item_repository
        self._assignment_repository = assignment_repository
        self._agent_report_repository = agent_report_repository
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
        self._weixin_ilink_runtime_state = weixin_ilink_runtime_state
        self._memory_activation_service = memory_activation_service
        self._knowledge_graph_service = knowledge_graph_service
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
            task_subgraph_summary_builder=self._build_task_subgraph_summary,
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
            knowledge_graph_service=self._resolve_knowledge_graph_service(),
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
        self._task_detail_projector.set_knowledge_graph_service(
            self._resolve_knowledge_graph_service(),
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

    def _build_task_subgraph_summary(
        self,
        *,
        kernel_metadata: dict[str, object] | None,
    ) -> dict[str, object] | None:
        self._task_detail_projector.set_knowledge_graph_service(
            self._resolve_knowledge_graph_service(),
        )
        return self._task_detail_projector.build_task_subgraph_summary(
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
            raise RuntimeCenterReadModelUnavailableError(
                "Human assist task service is not wired into Runtime Center state queries.",
            )
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
        getter = getattr(service, "get_visible_current_task", None)
        if not callable(getter):
            getter = getattr(service, "get_current_task", None)
        if not callable(getter):
            raise RuntimeCenterReadModelUnavailableError(
                "Human assist current-task queries are not wired into Runtime Center state queries.",
            )
        task = getter(chat_thread_id=chat_thread_id)
        if task is None:
            return None
        return self._serialize_human_assist_task(task)

    def get_human_assist_task_detail(self, task_id: str) -> dict[str, object] | None:
        service = self._human_assist_task_service
        getter = getattr(service, "get_task", None)
        if not callable(getter):
            raise RuntimeCenterReadModelUnavailableError(
                "Human assist detail queries are not wired into Runtime Center state queries.",
            )
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
        self._task_detail_projector.set_knowledge_graph_service(
            self._resolve_knowledge_graph_service(),
        )
        return self._task_detail_projector.get_task_review(task_id)

    def set_knowledge_graph_service(self, service: object | None) -> None:
        self._knowledge_graph_service = service

    def _resolve_knowledge_graph_service(self) -> object | None:
        if self._knowledge_graph_service is not None:
            return self._knowledge_graph_service
        if self._memory_activation_service is None:
            return None
        try:
            from ...memory import KnowledgeGraphService

            return KnowledgeGraphService(
                memory_activation_service=self._memory_activation_service,
            )
        except Exception:
            return None

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
                payload.append(self._project_probe_projection(serialized))
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

    def list_channel_runtimes(self) -> list[dict[str, object]]:
        runtime_state = getattr(self, "_weixin_ilink_runtime_state", None)
        snapshot = getattr(runtime_state, "snapshot", None)
        if not callable(snapshot):
            return []
        payload = snapshot()
        if not isinstance(payload, dict):
            return []
        if str(payload.get("login_status") or "").strip() == "unconfigured":
            return []
        return [
            {
                "channel": "weixin_ilink",
                **payload,
                "route": "/api/runtime-center/channel-runtimes/weixin_ilink",
            },
        ]

    def get_channel_runtime_detail(self, channel: str) -> dict[str, object] | None:
        normalized = str(channel or "").strip().lower()
        if normalized != "weixin_ilink":
            return None
        runtime_state = getattr(self, "_weixin_ilink_runtime_state", None)
        snapshot = getattr(runtime_state, "snapshot", None)
        if not callable(snapshot):
            return None
        payload = snapshot()
        if not isinstance(payload, dict):
            return None
        return {
            "channel": "weixin_ilink",
            **payload,
            "route": "/api/runtime-center/channel-runtimes/weixin_ilink",
        }

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
                payload.append(self._project_probe_projection(serialized))
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
        lifecycle_replacement_target_ids = string_list_from_values(
            lifecycle_history.get("replacement_target_ids"),
        )
        target_scope_projection = {
            "target_scope": first_non_empty(serialized.get("target_scope")) or "seat",
            "target_role_id": first_non_empty(serialized.get("target_role_id")),
            "target_seat_ref": first_non_empty(serialized.get("target_seat_ref")),
        }
        target_agent_id = self._candidate_target_agent_id(serialized)
        if target_agent_id is not None:
            target_scope_projection["target_agent_id"] = target_agent_id
        baseline_projection = {
            "is_baseline_import": (
                first_non_empty(serialized.get("ingestion_mode")) == "baseline-import"
            ),
            "is_active": str(serialized.get("status") or "").strip().lower() == "active",
            "protection_flags": list(serialized.get("protection_flags") or []),
        }
        replacement_lineage = {
            "lineage_root_id": first_non_empty(
                serialized.get("lineage_root_id"),
                serialized.get("candidate_id"),
            ),
            "supersedes": list(serialized.get("supersedes") or []),
            "superseded_by": list(serialized.get("superseded_by") or []),
            "replacement_target_ids": (
                lifecycle_replacement_target_ids
                or list(serialized.get("replacement_target_ids") or [])
            ),
            "rollback_target_ids": list(serialized.get("rollback_target_ids") or []),
            "replacement_relation": first_non_empty(serialized.get("replacement_relation")),
        }
        active_pack_composition = self._candidate_active_pack_composition(serialized)
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
            "target_scope_projection": target_scope_projection,
            "baseline_projection": baseline_projection,
            "lifecycle_history": lifecycle_history,
            "replacement_lineage": replacement_lineage,
            "active_pack_composition": active_pack_composition,
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
                "history": [],
                "trial_scopes": [],
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
        history: list[dict[str, object]] = []
        for item in decisions:
            history.append(
                {
                    "entry_kind": "decision",
                    "updated_at": getattr(item, "updated_at", None),
                    "decision_kind": getattr(item, "decision_kind", None),
                    "from_stage": getattr(item, "from_stage", None),
                    "to_stage": getattr(item, "to_stage", None),
                    "replacement_target_ids": list(
                        getattr(item, "replacement_target_ids", None) or []
                    ),
                    "reason": getattr(item, "reason", None),
                },
            )
        trial_scopes: list[dict[str, object]] = []
        for item in trials:
            scope_type = first_non_empty(getattr(item, "scope_type", None)) or "seat"
            scope_ref = first_non_empty(getattr(item, "scope_ref", None))
            trial_payload = {
                "scope_key": f"{scope_type}:{scope_ref}" if scope_ref is not None else scope_type,
                "scope_type": scope_type,
                "scope_ref": scope_ref,
                "verdict": getattr(item, "verdict", None),
                "operator_intervention_count": getattr(
                    item,
                    "operator_intervention_count",
                    0,
                ),
                "success_count": getattr(item, "success_count", 0),
                "failure_count": getattr(item, "failure_count", 0),
            }
            trial_scopes.append(trial_payload)
            history.append(
                {
                    "entry_kind": "trial",
                    "updated_at": getattr(item, "updated_at", None),
                    "scope_type": scope_type,
                    "scope_ref": scope_ref,
                    "verdict": getattr(item, "verdict", None),
                    "operator_intervention_count": getattr(
                        item,
                        "operator_intervention_count",
                        0,
                    ),
                },
            )
        history.sort(
            key=lambda item: str(item.get("updated_at") or ""),
            reverse=True,
        )
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
            "replacement_target_ids": string_list_from_values(
                *[
                    getattr(item, "replacement_target_ids", None)
                    for item in decisions
                ],
            ),
            "history": history,
            "trial_scopes": trial_scopes,
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

    def _candidate_active_pack_composition(
        self,
        candidate_payload: Mapping[str, object],
    ) -> dict[str, object]:
        target_role_id = first_non_empty(candidate_payload.get("target_role_id"))
        target_agent_id = self._candidate_target_agent_id(candidate_payload)
        target_seat_ref = first_non_empty(candidate_payload.get("target_seat_ref"))
        target_scope = first_non_empty(candidate_payload.get("target_scope")) or "seat"
        role_prototype_capability_ids: list[str] = []
        seat_instance_capability_ids: list[str] = []
        cycle_delta_capability_ids: list[str] = []
        session_overlay_capability_ids: list[str] = []
        effective_capability_ids: list[str] = []
        service = getattr(self, "_agent_profile_service", None)
        detail_getter = getattr(service, "get_agent_detail", None)
        if callable(detail_getter) and target_agent_id is not None:
            try:
                detail = detail_getter(target_agent_id)
            except Exception:
                detail = None
            detail_payload = self._mapping_payload(detail)
            runtime_payload = self._mapping_payload(detail_payload.get("runtime"))
            metadata_payload = self._mapping_payload(runtime_payload.get("metadata"))
            layers = IndustrySeatCapabilityLayers.from_metadata(
                metadata_payload.get("capability_layers"),
            )
            role_prototype_capability_ids = list(layers.role_prototype_capability_ids)
            seat_instance_capability_ids = list(layers.seat_instance_capability_ids)
            cycle_delta_capability_ids = list(layers.cycle_delta_capability_ids)
            session_overlay_capability_ids = list(layers.session_overlay_capability_ids)
            effective_capability_ids = list(layers.merged_capability_ids())
        proposed_skill_name = first_non_empty(candidate_payload.get("proposed_skill_name"))
        candidate_capability_id = (
            f"mcp:{proposed_skill_name}"
            if first_non_empty(candidate_payload.get("candidate_kind")) == "mcp-bundle"
            and proposed_skill_name is not None
            else (
                f"skill:{proposed_skill_name}"
                if proposed_skill_name is not None
                else None
            )
        )
        payload = {
            "target_scope": target_scope,
            "target_role_id": target_role_id,
            "target_seat_ref": target_seat_ref,
            "role_prototype_capability_ids": role_prototype_capability_ids,
            "seat_instance_capability_ids": seat_instance_capability_ids,
            "cycle_delta_capability_ids": cycle_delta_capability_ids,
            "session_overlay_capability_ids": session_overlay_capability_ids,
            "effective_capability_ids": effective_capability_ids,
            "active_candidate_member": (
                candidate_capability_id in effective_capability_ids
                if candidate_capability_id is not None
                else False
            ),
        }
        if target_agent_id is not None:
            payload["target_agent_id"] = target_agent_id
        return payload

    def _candidate_target_agent_id(
        self,
        candidate_payload: Mapping[str, object],
    ) -> str | None:
        metadata = self._mapping_payload(candidate_payload.get("metadata"))
        return first_non_empty(
            candidate_payload.get("target_agent_id"),
            metadata.get("target_agent_id"),
            metadata.get("seat_target_agent_id"),
        )

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
        schedule_reconciliation = self._build_schedule_reconciliation(schedule)

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
            "reconciliation": schedule_reconciliation["reconciliation"],
            "backlog_items": schedule_reconciliation["backlog_items"],
            "assignments": schedule_reconciliation["assignments"],
            "reports": schedule_reconciliation["reports"],
            "evidence": schedule_reconciliation["evidence"],
            "route": route,
            "actions": actions,
        }

    def _build_schedule_reconciliation(self, schedule: object) -> dict[str, object]:
        schedule_id = first_non_empty(getattr(schedule, "id", None))
        empty_payload = {
            "reconciliation": {
                "backlog_item_ids": [],
                "assignment_ids": [],
                "task_ids": [],
                "report_ids": [],
                "evidence_ids": [],
            },
            "backlog_items": [],
            "assignments": [],
            "reports": [],
            "evidence": [],
        }
        if schedule_id is None:
            return empty_payload

        industry_instance_id = self._resolve_schedule_industry_instance_id(schedule)
        backlog_items = self._list_schedule_backlog_items(
            schedule_id=schedule_id,
            industry_instance_id=industry_instance_id,
        )
        backlog_item_ids = self._unique_ids(getattr(item, "id", None) for item in backlog_items)
        assignments = self._list_schedule_assignments(
            backlog_item_ids=backlog_item_ids,
            industry_instance_id=industry_instance_id,
        )
        assignment_ids = self._unique_ids(
            getattr(assignment, "id", None)
            for assignment in assignments
        )
        assignment_task_ids = self._unique_ids(
            getattr(assignment, "task_id", None)
            for assignment in assignments
        )
        direct_tasks = self._list_schedule_direct_tasks(
            schedule=schedule,
            schedule_id=schedule_id,
        )
        direct_task_ids = self._unique_ids(
            getattr(task, "id", None)
            for task in direct_tasks
        )
        task_ids = self._unique_ids([*assignment_task_ids, *direct_task_ids])
        reports = self._list_schedule_reports(
            assignment_ids=assignment_ids,
            task_ids=task_ids,
            industry_instance_id=industry_instance_id,
        )
        report_ids = self._unique_ids(getattr(report, "id", None) for report in reports)
        task_ids = self._unique_ids(
            [
                *task_ids,
                *[
                    getattr(report, "task_id", None)
                    for report in reports
                ],
            ],
        )
        evidence = self._list_schedule_evidence(
            task_ids=task_ids,
            assignments=assignments,
            reports=reports,
        )
        evidence_ids = self._unique_ids(
            getattr(record, "id", None)
            for record in evidence
        )
        return {
            "reconciliation": {
                "backlog_item_ids": backlog_item_ids,
                "assignment_ids": assignment_ids,
                "task_ids": task_ids,
                "report_ids": report_ids,
                "evidence_ids": evidence_ids,
            },
            "backlog_items": [item.model_dump(mode="json") for item in backlog_items],
            "assignments": [
                self._serialize_schedule_assignment(assignment)
                for assignment in assignments
            ],
            "reports": [
                self._serialize_schedule_report(report)
                for report in reports
            ],
            "evidence": [serialize_evidence_record(record) for record in evidence],
        }

    def _resolve_schedule_industry_instance_id(self, schedule: object) -> str | None:
        spec_payload = getattr(schedule, "spec_payload", {}) or {}
        payload = dict(spec_payload) if isinstance(spec_payload, Mapping) else {}
        meta = payload.get("meta")
        if isinstance(meta, Mapping):
            resolved = first_non_empty(
                meta.get("industry_instance_id"),
                meta.get("instance_id"),
            )
            if resolved is not None:
                return resolved
        source_ref = first_non_empty(getattr(schedule, "source_ref", None))
        if source_ref is not None and source_ref.startswith("industry:"):
            _, _, tail = source_ref.partition(":")
            return tail or None
        return None

    def _list_schedule_backlog_items(
        self,
        *,
        schedule_id: str,
        industry_instance_id: str | None,
    ) -> list[object]:
        repository = self._backlog_item_repository
        if repository is None:
            return []
        items = repository.list_items(
            industry_instance_id=industry_instance_id,
            limit=None,
        )
        expected_source_ref = f"schedule:{schedule_id}"
        return [
            item
            for item in items
            if first_non_empty(getattr(item, "source_ref", None)) == expected_source_ref
            or first_non_empty(
                getattr(item, "metadata", {}).get("schedule_id")
                if isinstance(getattr(item, "metadata", {}), Mapping)
                else None,
            )
            == schedule_id
        ]

    def _list_schedule_direct_tasks(
        self,
        *,
        schedule: object,
        schedule_id: str,
    ) -> list[object]:
        repository = self._task_repository
        if repository is None:
            return []
        anchor_terms = self._schedule_task_anchor_terms(
            schedule=schedule,
            schedule_id=schedule_id,
        )
        if not anchor_terms:
            return []
        candidates: dict[str, object] = {}
        for term in anchor_terms:
            for task in repository.list_tasks(
                acceptance_criteria_like=term,
                limit=None,
            ):
                task_id = first_non_empty(getattr(task, "id", None))
                if task_id is None:
                    continue
                if not self._task_matches_schedule(
                    task=task,
                    schedule=schedule,
                    schedule_id=schedule_id,
                ):
                    continue
                candidates[task_id] = task
        return list(candidates.values())

    def _schedule_task_anchor_terms(
        self,
        *,
        schedule: object,
        schedule_id: str,
    ) -> list[str]:
        spec_payload = getattr(schedule, "spec_payload", {}) or {}
        payload = dict(spec_payload) if isinstance(spec_payload, Mapping) else {}
        meta = dict(payload.get("meta")) if isinstance(payload.get("meta"), Mapping) else {}
        source_ref = first_non_empty(getattr(schedule, "source_ref", None))
        workflow_run_id = first_non_empty(meta.get("workflow_run_id"))
        workflow_step_id = first_non_empty(meta.get("workflow_step_id"))
        source_tail = source_ref.split(":", 1)[1].strip() if source_ref and ":" in source_ref else None
        return self._unique_ids(
            [
                schedule_id,
                workflow_run_id,
                workflow_step_id,
                source_tail,
            ],
        )

    def _task_matches_schedule(
        self,
        *,
        task: object,
        schedule: object,
        schedule_id: str,
    ) -> bool:
        metadata = decode_kernel_task_metadata(getattr(task, "acceptance_criteria", None)) or {}
        payload = dict(metadata.get("payload")) if isinstance(metadata.get("payload"), Mapping) else {}
        request = dict(payload.get("request")) if isinstance(payload.get("request"), Mapping) else {}
        request_meta = dict(request.get("meta")) if isinstance(request.get("meta"), Mapping) else {}
        dispatch = dict(payload.get("dispatch")) if isinstance(payload.get("dispatch"), Mapping) else {}
        dispatch_meta = dict(dispatch.get("meta")) if isinstance(dispatch.get("meta"), Mapping) else {}
        schedule_kind = first_non_empty(getattr(schedule, "schedule_kind", None))
        spec_payload = getattr(schedule, "spec_payload", {}) or {}
        schedule_payload = dict(spec_payload) if isinstance(spec_payload, Mapping) else {}
        schedule_meta = (
            dict(schedule_payload.get("meta"))
            if isinstance(schedule_payload.get("meta"), Mapping)
            else {}
        )
        source_ref = first_non_empty(getattr(schedule, "source_ref", None))
        workflow_run_id = first_non_empty(
            schedule_meta.get("workflow_run_id"),
            source_ref.split(":", 1)[1].strip() if source_ref and source_ref.startswith("workflow:") else None,
        )
        workflow_step_id = first_non_empty(schedule_meta.get("workflow_step_id"))

        if schedule_kind == "workflow" or workflow_run_id is not None or workflow_step_id is not None:
            return (
                first_non_empty(
                    request_meta.get("workflow_run_id"),
                    request.get("workflow_run_id"),
                    payload.get("workflow_run_id"),
                )
                == workflow_run_id
                and first_non_empty(
                    request_meta.get("workflow_step_id"),
                    request.get("workflow_step_id"),
                    payload.get("workflow_step_id"),
                )
                == workflow_step_id
            )

        return first_non_empty(
            payload.get("job_id"),
            payload.get("schedule_id"),
            dispatch_meta.get("schedule_id"),
            dispatch_meta.get("coordinator_id"),
            request_meta.get("schedule_id"),
            request_meta.get("coordinator_id"),
        ) == schedule_id

    def _list_schedule_assignments(
        self,
        *,
        backlog_item_ids: list[str],
        industry_instance_id: str | None,
    ) -> list[object]:
        repository = self._assignment_repository
        if repository is None or not backlog_item_ids:
            return []
        assignments = repository.list_assignments(
            industry_instance_id=industry_instance_id,
            limit=None,
        )
        backlog_item_id_set = set(backlog_item_ids)
        return [
            assignment
            for assignment in assignments
            if first_non_empty(getattr(assignment, "backlog_item_id", None))
            in backlog_item_id_set
        ]

    def _list_schedule_reports(
        self,
        *,
        assignment_ids: list[str],
        task_ids: list[str],
        industry_instance_id: str | None,
    ) -> list[object]:
        repository = self._agent_report_repository
        if repository is None or (not assignment_ids and not task_ids):
            return []
        reports = repository.list_reports(
            industry_instance_id=industry_instance_id,
            limit=None,
        )
        assignment_id_set = set(assignment_ids)
        task_id_set = set(task_ids)
        return [
            report
            for report in reports
            if first_non_empty(getattr(report, "assignment_id", None)) in assignment_id_set
            or first_non_empty(getattr(report, "task_id", None)) in task_id_set
        ]

    def _list_schedule_evidence(
        self,
        *,
        task_ids: list[str],
        assignments: list[object],
        reports: list[object],
    ) -> list[object]:
        if self._evidence_ledger is None:
            return []
        records = list(
            self._evidence_ledger.list_records(task_ids=task_ids)
            if task_ids
            else []
        )
        seen_ids = {
            evidence_id
            for evidence_id in self._unique_ids(getattr(record, "id", None) for record in records)
        }
        referenced_ids = self._unique_ids(
            [
                *[
                    evidence_id
                    for assignment in assignments
                    for evidence_id in list(getattr(assignment, "evidence_ids", []) or [])
                ],
                *[
                    evidence_id
                    for report in reports
                    for evidence_id in list(getattr(report, "evidence_ids", []) or [])
                ],
            ],
        )
        for evidence_id in referenced_ids:
            if evidence_id in seen_ids:
                continue
            record = self._evidence_ledger.get_record(evidence_id)
            if record is None:
                continue
            records.append(record)
            seen_ids.add(evidence_id)
        records.sort(
            key=lambda record: (
                getattr(record, "created_at", None) or datetime.min.replace(tzinfo=timezone.utc),
                first_non_empty(getattr(record, "id", None)) or "",
            ),
            reverse=True,
        )
        return records

    def _serialize_schedule_assignment(self, assignment: object) -> dict[str, object]:
        payload = (
            assignment.model_dump(mode="json")
            if hasattr(assignment, "model_dump")
            else dict(assignment)
            if isinstance(assignment, Mapping)
            else {}
        )
        task_id = first_non_empty(payload.get("task_id"))
        if task_id is not None:
            payload["task_route"] = task_route(task_id)
        return payload

    def _serialize_schedule_report(self, report: object) -> dict[str, object]:
        payload = (
            report.model_dump(mode="json")
            if hasattr(report, "model_dump")
            else dict(report)
            if isinstance(report, Mapping)
            else {}
        )
        task_id = first_non_empty(payload.get("task_id"))
        if task_id is not None:
            payload["task_route"] = task_route(task_id)
        return payload

    def _unique_ids(self, values: Any) -> list[str]:
        seen: set[str] = set()
        payload: list[str] = []
        for value in values:
            text = first_non_empty(value)
            if text is None or text in seen:
                continue
            seen.add(text)
            payload.append(text)
        return payload

    def list_goals(self, limit: int | None = 5) -> list[dict[str, object]]:
        return self._goal_decision_projector.list_goals(limit=limit)

    def get_goal_detail(self, goal_id: str) -> dict[str, object] | None:
        return self._goal_decision_projector.get_goal_detail(goal_id)

    def set_goal_service(self, goal_service: object | None) -> None:
        self._goal_service = goal_service
        self._goal_decision_projector.set_goal_service(goal_service)

    def set_learning_service(self, learning_service: object | None) -> None:
        self._learning_service = learning_service

    def get_surface_learning_scope(
        self,
        *,
        scope_type: str,
        scope_id: str,
        task_id: str | None = None,
        work_context_id: str | None = None,
        agent_id: str | None = None,
        industry_instance_id: str | None = None,
        owner_agent_id: str | None = None,
        limit: int = 3,
    ) -> dict[str, object] | None:
        getter = getattr(self._learning_service, "get_surface_learning_scope", None)
        if not callable(getter):
            raise RuntimeCenterReadModelUnavailableError(
                "Surface learning read chain is not wired into Runtime Center state queries.",
            )
        scope_level = {
            "work_context": "work_context",
            "industry": "industry_scope",
            "agent": "role_scope",
        }.get(str(scope_type or "").strip())
        normalized_scope_id = str(scope_id or "").strip()
        if scope_level is None or not normalized_scope_id:
            return None
        projection = getter(
            scope_level=scope_level,
            scope_id=normalized_scope_id,
            industry_instance_id=industry_instance_id,
            owner_agent_id=owner_agent_id or agent_id,
        )
        if projection is None:
            return None
        model_dump = getattr(projection, "model_dump", None)
        payload = (
            model_dump(mode="json")
            if callable(model_dump)
            else dict(projection)
            if isinstance(projection, dict)
            else None
        )
        if not isinstance(payload, dict):
            return None
        payload["scope_type"] = scope_type
        payload["scope_id"] = normalized_scope_id
        payload["live_graph"] = self._build_surface_live_graph_summary(
            scope_type=scope_type,
            scope_id=normalized_scope_id,
            task_id=task_id,
            work_context_id=work_context_id,
            agent_id=agent_id,
            industry_instance_id=industry_instance_id,
        )
        payload["latest_evidence"] = self._list_recent_surface_evidence(
            scope_type=scope_type,
            scope_id=normalized_scope_id,
            task_id=task_id,
            work_context_id=work_context_id,
            agent_id=agent_id,
            industry_instance_id=industry_instance_id,
            limit=limit,
        )
        return payload

    def set_agent_profile_service(self, agent_profile_service: object | None) -> None:
        self._agent_profile_service = agent_profile_service

    def set_human_assist_task_service(self, human_assist_task_service: object | None) -> None:
        self._human_assist_task_service = human_assist_task_service

    def list_decision_requests(self, limit: int | None = 5) -> list[dict[str, object]]:
        return self._goal_decision_projector.list_decision_requests(limit=limit)

    def get_decision_request(self, decision_id: str) -> dict[str, object] | None:
        return self._goal_decision_projector.get_decision_request(decision_id)

    def _build_surface_live_graph_summary(
        self,
        *,
        scope_type: str,
        scope_id: str,
        task_id: str | None,
        work_context_id: str | None,
        agent_id: str | None,
        industry_instance_id: str | None,
    ) -> dict[str, object]:
        if self._runtime_frame_repository is None:
            return {}
        tasks = self._task_repository.list_tasks(
            task_ids=[task_id] if task_id else None,
            work_context_id=scope_id if scope_type == "work_context" else work_context_id,
            owner_agent_id=scope_id if scope_type == "agent" else agent_id,
            industry_instance_id=(
                scope_id if scope_type == "industry" else industry_instance_id
            ),
            limit=12,
        )
        latest_frame = None
        for task in tasks:
            frames = self._runtime_frame_repository.list_frames(task.id, limit=1)
            if not frames:
                continue
            frame = frames[0]
            if latest_frame is None or frame.created_at > latest_frame.created_at:
                latest_frame = frame
        projection = (
            dict(getattr(latest_frame, "surface_projection", {}) or {})
            if latest_frame is not None
            else {}
        )
        if not projection:
            return {}
        return {
            "surface_kind": str(projection.get("surface_kind") or "").strip(),
            "confidence": float(projection.get("confidence") or 0.0),
            "region_count": len(projection.get("regions") or []),
            "control_count": len(projection.get("controls") or []),
            "result_count": len(projection.get("results") or []),
            "blocker_count": len(projection.get("blockers") or []),
            "entity_count": len(projection.get("entities") or []),
            "relation_count": len(projection.get("relations") or []),
        }

    def _list_recent_surface_evidence(
        self,
        *,
        scope_type: str,
        scope_id: str,
        task_id: str | None,
        work_context_id: str | None,
        agent_id: str | None,
        industry_instance_id: str | None,
        limit: int,
    ) -> list[dict[str, object]]:
        if self._evidence_ledger is None:
            return []
        matched: list[dict[str, object]] = []
        for record in self._evidence_ledger.list_recent(limit=max(20, limit * 20)):
            if str(getattr(record, "kind", "") or "").strip() not in {
                "surface-probe",
                "surface-discovery",
                "surface-transition",
            }:
                continue
            metadata = dict(getattr(record, "metadata", {}) or {})
            if task_id and str(getattr(record, "task_id", "") or "").strip() != task_id:
                continue
            if scope_type == "work_context":
                candidate_scope_id = str(
                    metadata.get("work_context_id") or work_context_id or "",
                ).strip()
                if candidate_scope_id != scope_id:
                    continue
            elif scope_type == "agent":
                candidate_scope_id = str(
                    metadata.get("trace_owner_agent_id") or agent_id or "",
                ).strip()
                if candidate_scope_id != scope_id:
                    continue
            elif scope_type == "industry":
                candidate_scope_id = str(
                    metadata.get("industry_instance_id") or industry_instance_id or "",
                ).strip()
                if candidate_scope_id != scope_id:
                    continue
            payload = serialize_evidence_record(record)
            matched.append(
                {
                    "id": payload.get("id"),
                    "kind": payload.get("kind"),
                    "action_summary": payload.get("action_summary"),
                    "result_summary": payload.get("result_summary"),
                    "created_at": payload.get("created_at"),
                    "task_id": payload.get("task_id"),
                }
            )
            if len(matched) >= limit:
                break
        return matched

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

    def _project_probe_projection(
        self,
        payload: Mapping[str, object] | None,
    ) -> dict[str, object]:
        serialized = dict(payload or {})
        metadata = self._mapping_payload(serialized.get("metadata"))
        probe_result = self._mapping_payload(metadata.get("probe_result"))
        selected_adapter_action_id = first_non_empty(
            serialized.get("selected_adapter_action_id"),
            metadata.get("selected_adapter_action_id"),
            probe_result.get("selected_adapter_action_id"),
        )
        if selected_adapter_action_id is not None:
            serialized["selected_adapter_action_id"] = selected_adapter_action_id
        probe_outcome = first_non_empty(
            serialized.get("probe_outcome"),
            probe_result.get("probe_outcome"),
        )
        if probe_outcome is not None:
            serialized["probe_outcome"] = probe_outcome
        probe_error_type = first_non_empty(
            serialized.get("probe_error_type"),
            probe_result.get("probe_error_type"),
        )
        if probe_error_type is not None:
            serialized["probe_error_type"] = probe_error_type
        probe_evidence_refs = string_list_from_values(
            serialized.get("probe_evidence_refs"),
            probe_result.get("probe_evidence_refs"),
            metadata.get("probe_evidence_refs"),
        )
        if probe_evidence_refs:
            serialized["probe_evidence_refs"] = probe_evidence_refs
        return serialized

Phase1StateQueryService = RuntimeCenterStateQueryService
RuntimeStateQueryService = RuntimeCenterStateQueryService
