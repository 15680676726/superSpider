# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping

from ..compiler.planning import ReportReplanEngine
from ..capabilities.skill_evolution_service import SkillEvolutionService
from ..learning.skill_gap_detector import SkillGapDetector
from .service_shared import *  # noqa: F401,F403


def _mapping_dict(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_list(value: object | None) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _payload_dict(value: object | None) -> dict[str, Any]:
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


def _int_value(value: object | None) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = _string(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _merge_adapter_metadata(*payloads: object) -> dict[str, Any]:
    from ..capabilities.external_adapter_contracts import (
        merge_adapter_attribution_metadata,
    )

    return merge_adapter_attribution_metadata(*payloads)


class _PredictionServiceCoreMixin:
    def __init__(
        self,
        *,
        case_repository: SqlitePredictionCaseRepository,
        scenario_repository: SqlitePredictionScenarioRepository,
        signal_repository: SqlitePredictionSignalRepository,
        recommendation_repository: SqlitePredictionRecommendationRepository,
        review_repository: SqlitePredictionReviewRepository,
        evidence_ledger: EvidenceLedger,
        reporting_service: object | None = None,
        goal_repository: SqliteGoalRepository | None = None,
        task_repository: SqliteTaskRepository | None = None,
        task_runtime_repository: SqliteTaskRuntimeRepository | None = None,
        decision_request_repository: SqliteDecisionRequestRepository | None = None,
        industry_instance_repository: SqliteIndustryInstanceRepository | None = None,
        workflow_run_repository: SqliteWorkflowRunRepository | None = None,
        strategy_memory_service: object | None = None,
        capability_service: object | None = None,
        capability_candidate_service: object | None = None,
        capability_donor_service: object | None = None,
        capability_portfolio_service: object | None = None,
        skill_evolution_service: object | None = None,
        skill_gap_detector: object | None = None,
        skill_trial_service: object | None = None,
        skill_lifecycle_decision_service: object | None = None,
        agent_profile_service: object | None = None,
        kernel_dispatcher: object | None = None,
        enable_remote_hub_search: bool = True,
        enable_remote_curated_search: bool = True,
    ) -> None:
        self._case_repository = case_repository
        self._scenario_repository = scenario_repository
        self._signal_repository = signal_repository
        self._recommendation_repository = recommendation_repository
        self._review_repository = review_repository
        self._evidence_ledger = evidence_ledger
        self._reporting_service = reporting_service
        self._goal_repository = goal_repository
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._decision_request_repository = decision_request_repository
        self._industry_instance_repository = industry_instance_repository
        self._workflow_run_repository = workflow_run_repository
        self._strategy_memory_service = strategy_memory_service
        self._capability_service = capability_service
        self._capability_candidate_service = capability_candidate_service
        self._capability_donor_service = capability_donor_service
        self._capability_portfolio_service = capability_portfolio_service
        self._skill_evolution_service = (
            skill_evolution_service
            if skill_evolution_service is not None
            else SkillEvolutionService(
                candidate_service=capability_candidate_service,
            )
        )
        self._skill_gap_detector = (
            skill_gap_detector
            if skill_gap_detector is not None
            else SkillGapDetector()
        )
        self._skill_trial_service = skill_trial_service
        self._skill_lifecycle_decision_service = skill_lifecycle_decision_service
        self._agent_profile_service = agent_profile_service
        self._kernel_dispatcher = kernel_dispatcher
        self._enable_remote_hub_search = enable_remote_hub_search
        self._enable_remote_curated_search = enable_remote_curated_search
        self._purge_retired_goal_dispatch_recommendations()

    def list_cases(
        self,
        *,
        case_kind: str | None = None,
        status: str | None = None,
        industry_instance_id: str | None = None,
        owner_scope: str | None = None,
        limit: int | None = None,
    ) -> list[PredictionCaseSummary]:
        records = self._case_repository.list_cases(
            case_kind=case_kind,
            status=status,
            industry_instance_id=industry_instance_id,
            owner_scope=owner_scope,
            limit=limit,
        )
        return [self._summary(record) for record in records]

    def get_case(self, case_id: str) -> PredictionCaseRecord | None:
        return self._case_repository.get_case(case_id)

    def get_case_detail(self, case_id: str) -> PredictionCaseDetail:
        case = self._case_repository.get_case(case_id)
        if case is None:
            raise KeyError(f"Prediction case '{case_id}' not found")
        scenarios = self._scenario_repository.list_scenarios(case_id=case_id)
        signals = self._signal_repository.list_signals(case_id=case_id)
        recommendations = self._recommendation_repository.list_recommendations(case_id=case_id)
        reviews = self._review_repository.list_reviews(case_id=case_id)
        recommendation_views = [self._recommendation_view(item) for item in recommendations]
        pending_decisions = sum(
            1
            for item in recommendation_views
            if str(item.recommendation.get("status") or "") == "waiting-confirm"
        )
        latest_review = reviews[0] if reviews else None
        case_payload = case.model_dump(mode="json")
        case_metadata = _safe_dict(case_payload.get("metadata"))
        planning_snapshot = _mapping_dict(case_metadata.get("planning_snapshot"))
        if planning_snapshot:
            case_payload["planning"] = dict(planning_snapshot)
        planning_replan = _mapping_dict(planning_snapshot.get("replan"))
        return PredictionCaseDetail(
            case=case_payload,
            scenarios=[item.model_dump(mode="json") for item in scenarios],
            signals=[item.model_dump(mode="json") for item in signals],
            recommendations=recommendation_views,
            reviews=[item.model_dump(mode="json") for item in reviews],
            stats={
                "scenario_count": len(scenarios),
                "signal_count": len(signals),
                "recommendation_count": len(recommendations),
                "review_count": len(reviews),
                "pending_decision_count": pending_decisions,
                "latest_review_outcome": latest_review.outcome if latest_review is not None else None,
                "planning_overlap": bool(case_metadata.get("planning_overlap")),
                "planning_review_ref": _string(planning_snapshot.get("review_ref")),
                "planning_replan_status": _string(planning_replan.get("status")),
                "planning_replan_decision_kind": _string(
                    planning_replan.get("decision_kind"),
                ),
            },
            routes={
                "self": _route_prediction(case_id),
                "list": "/api/predictions",
                "reviews": f"/api/predictions/{case_id}/reviews",
            },
        )

    def create_case(
        self,
        payload: PredictionCreateRequest,
        *,
        case_kind: str = "manual",
    ) -> PredictionCaseDetail:
        title = payload.title or payload.question or "预测案例"
        case = PredictionCaseRecord(
            title=title[:160],
            summary=payload.summary or (payload.question or ""),
            case_kind=case_kind,  # type: ignore[arg-type]
            topic_type=payload.topic_type,
            owner_scope=_string(payload.owner_scope),
            owner_agent_id=_string(payload.owner_agent_id),
            industry_instance_id=_string(payload.industry_instance_id),
            workflow_run_id=_string(payload.workflow_run_id),
            question=payload.question or "",
            time_window_days=payload.time_window_days,
            metadata=dict(payload.metadata or {}),
        )
        facts = self._collect_facts(case)
        signals = self._build_signals(case, facts)
        recommendations = self._build_recommendations(case, facts, signals)
        scenarios = self._build_scenarios(case, facts, signals, recommendations)
        case = case.model_copy(
            update={
                "overall_confidence": self._case_confidence(signals, recommendations),
                "primary_recommendation_id": (
                    recommendations[0].recommendation_id if recommendations else None
                ),
                "input_payload": {
                    "scope_type": facts.scope_type,
                    "scope_id": facts.scope_id,
                    "strategy_id": _string((facts.strategy or {}).get("strategy_id")),
                    "strategy_summary": _string((facts.strategy or {}).get("summary")),
                    "strategy_priority_order": _string_list(
                        (facts.strategy or {}).get("priority_order"),
                    )[:5],
                    "report_route": facts.report.get("routes", {}).get("detail"),
                    "performance_route": facts.performance.get("routes", {}).get("report"),
                    "goal_ids": [goal.id for goal in facts.goals],
                    "workflow_run_ids": [run.run_id for run in facts.workflows],
                    "question": payload.question or "",
                },
                "metadata": {
                    **dict(payload.metadata or {}),
                    "signal_count": len(signals),
                    "recommendation_count": len(recommendations),
                    "generated_from": "prediction-service-v1",
                    "strategy_id": _string((facts.strategy or {}).get("strategy_id")),
                    "strategy_north_star": _string((facts.strategy or {}).get("north_star")),
                    "strategy_priority_count": len(
                        _string_list((facts.strategy or {}).get("priority_order")),
                    ),
                },
            },
        )
        self._case_repository.upsert_case(case)
        for item in signals:
            self._signal_repository.upsert_signal(item)
        for item in recommendations:
            self._recommendation_repository.upsert_recommendation(item)
        for item in scenarios:
            self._scenario_repository.upsert_scenario(item)
        return self.get_case_detail(case.case_id)

    def create_cycle_case(
        self,
        *,
        industry_instance_id: str,
        industry_label: str | None = None,
        owner_scope: str,
        owner_agent_id: str | None = None,
        actor: str = "system:operating-cycle",
        cycle_id: str | None = None,
        pending_report_ids: list[str] | None = None,
        open_backlog_ids: list[str] | None = None,
        open_backlog_source_refs: list[str] | None = None,
        goal_statuses: dict[str, str] | None = None,
        meeting_window: str | None = None,
        participant_inputs: list[dict[str, Any]] | None = None,
        assignment_summaries: list[dict[str, Any]] | None = None,
        lane_summaries: list[dict[str, Any]] | None = None,
        formal_planning_context: Mapping[str, Any] | None = None,
        report_synthesis: Mapping[str, Any] | None = None,
        force: bool = False,
    ) -> PredictionCaseDetail | None:
        normalized_instance_id = _string(industry_instance_id)
        normalized_owner_scope = _string(owner_scope)
        if normalized_instance_id is None or normalized_owner_scope is None:
            return None
        normalized_meeting_window = _string(meeting_window) or "cycle-review"
        local_review_date = datetime.now().astimezone().date().isoformat()
        planning_snapshot = self._build_cycle_case_planning_snapshot(
            industry_instance_id=normalized_instance_id,
            cycle_id=_string(cycle_id),
            meeting_window=normalized_meeting_window,
            review_date_local=local_review_date,
            pending_report_ids=pending_report_ids,
            open_backlog_ids=open_backlog_ids,
            participant_inputs=participant_inputs,
            assignment_summaries=assignment_summaries,
            lane_summaries=lane_summaries,
            formal_planning_context=formal_planning_context,
            report_synthesis=report_synthesis,
        )
        formal_review_ref = _string(planning_snapshot.get("review_ref"))
        replan_snapshot = _mapping_dict(planning_snapshot.get("replan"))
        if formal_review_ref is not None and bool(planning_snapshot.get("overlap_with_formal_review")):
            fingerprint_payload = {
                "industry_instance_id": normalized_instance_id,
                "cycle_id": _string(cycle_id),
                "planning_review_ref": formal_review_ref,
                "planning_review_window": _string(planning_snapshot.get("review_window")),
                "replan_decision_id": _string(replan_snapshot.get("decision_id")),
                "replan_reason_ids": _string_list(replan_snapshot.get("reason_ids"))[:12],
            }
        else:
            fingerprint_payload = {
                "industry_instance_id": normalized_instance_id,
                "cycle_id": _string(cycle_id),
                "meeting_window": normalized_meeting_window,
                "review_date_local": local_review_date,
                "pending_report_ids": _string_list(pending_report_ids)[:12],
                "open_backlog_ids": _string_list(open_backlog_ids)[:12],
                "open_backlog_source_refs": _string_list(open_backlog_source_refs)[:12],
                "assignment_ids": [
                    assignment_id
                    for assignment_id in (
                        _string(item.get("assignment_id"))
                        for item in list(participant_inputs or [])[:12]
                        if isinstance(item, dict)
                    )
                    if assignment_id is not None
                ],
                "goal_statuses": {
                    str(goal_id): str(status)
                    for goal_id, status in sorted((goal_statuses or {}).items())
                },
            }
        fingerprint = _stable_prediction_fingerprint(fingerprint_payload)
        if not force:
            recent_cases = self._case_repository.list_cases(
                case_kind="cycle",
                industry_instance_id=normalized_instance_id,
                limit=12,
            )
            for case in recent_cases:
                metadata = _safe_dict(case.metadata)
                if _string(metadata.get("cycle_fingerprint")) == fingerprint:
                    return self._persist_cycle_case_planning_snapshot(
                        case.case_id,
                        planning_snapshot,
                    )
        meeting_label = {
            "morning": "Morning Review",
            "evening": "Evening Review",
        }.get(normalized_meeting_window, "Review Meeting")
        meeting_trigger_mode = (
            "windowed-operating-cycle"
            if normalized_meeting_window in {"morning", "evening"}
            else "manual-review"
        )
        request = PredictionCreateRequest(
            title=(
                f"{_string(industry_label) or normalized_instance_id} "
                f"Spider Mesh {meeting_label}"
            ),
            question=(
                "Run the formal main-brain review meeting over the current cycle, "
                "pending reports, assignments, backlog, structured participant inputs, "
                "and strategy context, then surface the next governed moves."
            ),
            summary=(
                f"Main-brain {meeting_label.lower()} generated from current cycle facts "
                "and structured participant inputs."
            ),
            topic_type="operations",
            owner_scope=normalized_owner_scope,
            owner_agent_id=_string(owner_agent_id),
            industry_instance_id=normalized_instance_id,
            time_window_days=7,
            metadata={
                "trigger_source": "operating-cycle",
                "trigger_actor": actor,
                "cycle_id": _string(cycle_id),
                "cycle_fingerprint": fingerprint,
                "meeting_contract": "main-brain-window-review-v1",
                "meeting_kind": "main-brain-review",
                "meeting_mode": "structured-async",
                "meeting_trigger_mode": meeting_trigger_mode,
                "participant_mode": "structured-inputs",
                "meeting_window": normalized_meeting_window,
                "review_date_local": local_review_date,
                "pending_report_ids": _string_list(pending_report_ids),
                "open_backlog_ids": _string_list(open_backlog_ids),
                "open_backlog_source_refs": _string_list(open_backlog_source_refs),
                "goal_statuses": dict(goal_statuses or {}),
                "participant_inputs": list(participant_inputs or []),
                "assignment_summaries": list(assignment_summaries or []),
                "lane_summaries": list(lane_summaries or []),
                "planning_overlap": bool(planning_snapshot.get("overlap_with_formal_review")),
                "planning_snapshot": planning_snapshot,
            },
        )
        detail = self.create_case(request, case_kind="cycle")
        case_id = _string(_safe_dict(detail.case).get("case_id"))
        if case_id is None:
            return detail
        return self._persist_cycle_case_planning_snapshot(case_id, planning_snapshot)

    def _build_cycle_case_planning_snapshot(
        self,
        *,
        industry_instance_id: str,
        cycle_id: str | None,
        meeting_window: str,
        review_date_local: str,
        pending_report_ids: list[str] | None,
        open_backlog_ids: list[str] | None,
        participant_inputs: list[dict[str, Any]] | None,
        assignment_summaries: list[dict[str, Any]] | None,
        lane_summaries: list[dict[str, Any]] | None,
        formal_planning_context: Mapping[str, Any] | None,
        report_synthesis: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        planning_context = _mapping_dict(formal_planning_context)
        planning_metadata = _mapping_dict(planning_context.get("metadata"))
        strategy_constraints = _mapping_dict(planning_context.get("strategy_constraints"))
        cycle_decision = _mapping_dict(planning_context.get("cycle_decision"))
        if not cycle_decision:
            cycle_decision = {
                "summary": _string(planning_context.get("summary")),
                "planning_policy": _string_list(planning_context.get("planning_policy"))[:8],
                "selected_lane_ids": _string_list(planning_context.get("selected_lane_ids"))[:8],
                "selected_backlog_item_ids": _string_list(
                    planning_context.get("selected_backlog_item_ids"),
                )[:12],
            }
        overlap_with_formal_review = bool(planning_context) or bool(report_synthesis)
        review_ref = _string(planning_context.get("review_ref")) or (
            f"prediction-cycle-review:{industry_instance_id}:{cycle_id or meeting_window}:{review_date_local}"
        )
        pending_report_count = _int_value(planning_metadata.get("pending_report_count"))
        if pending_report_count is None:
            pending_report_count = len(_string_list(pending_report_ids))
        open_backlog_count = _int_value(planning_metadata.get("open_backlog_count"))
        if open_backlog_count is None:
            open_backlog_count = len(_string_list(open_backlog_ids))
        compiled_replan = ReportReplanEngine().compile(report_synthesis)
        synthesis_payload = _mapping_dict(report_synthesis)
        raw_replan = _mapping_dict(synthesis_payload.get("replan_decision"))
        persisted_replan = _mapping_dict(planning_context.get("report_replan"))
        trigger_context = {
            **_mapping_dict(raw_replan.get("trigger_context")),
            **_mapping_dict(persisted_replan.get("trigger_context")),
        }
        trigger_families = (
            _string_list(
                trigger_context.get("trigger_families"),
                persisted_replan.get("trigger_families"),
            )[:8]
            or _string_list(compiled_replan.trigger_families)[:8]
        )
        trigger_rule_ids = (
            _string_list(
                trigger_context.get("trigger_rule_ids"),
                persisted_replan.get("trigger_rule_ids"),
            )[:8]
            or _string_list(compiled_replan.trigger_rule_ids)[:8]
        )
        affected_lane_ids = (
            _string_list(
                trigger_context.get("affected_lane_ids"),
                persisted_replan.get("affected_lane_ids"),
            )[:8]
            or _string_list(compiled_replan.affected_lane_ids)[:8]
        )
        affected_uncertainty_ids = (
            _string_list(
                trigger_context.get("affected_uncertainty_ids"),
                trigger_context.get("strategic_uncertainty_ids"),
                persisted_replan.get("affected_uncertainty_ids"),
            )[:8]
            or _string_list(compiled_replan.affected_uncertainty_ids)[:8]
        )
        if trigger_families:
            trigger_context["trigger_families"] = trigger_families
        if trigger_rule_ids:
            trigger_context["trigger_rule_ids"] = trigger_rule_ids
        if affected_lane_ids:
            trigger_context["affected_lane_ids"] = affected_lane_ids
        if affected_uncertainty_ids:
            trigger_context["affected_uncertainty_ids"] = affected_uncertainty_ids
            trigger_context["strategic_uncertainty_ids"] = affected_uncertainty_ids
        replan_status = _string(persisted_replan.get("status")) or compiled_replan.status
        replan_decision_kind = (
            _string(persisted_replan.get("decision_kind"))
            or _string(raw_replan.get("decision_kind"))
            or compiled_replan.decision_kind
        )
        replan_decision_id = (
            _string(persisted_replan.get("decision_id"))
            or _string(raw_replan.get("decision_id"))
            or compiled_replan.decision_id
        )
        replan_summary = (
            _string(persisted_replan.get("summary"))
            or _string(raw_replan.get("summary"))
            or compiled_replan.summary
        )
        replan_reason_ids = _string_list(
            persisted_replan.get("reason_ids"),
            compiled_replan.reason_ids,
        )[:8]
        replan_source_report_ids = _string_list(
            persisted_replan.get("source_report_ids"),
            compiled_replan.source_report_ids,
        )[:8]
        replan_topic_keys = _string_list(
            persisted_replan.get("topic_keys"),
            compiled_replan.topic_keys,
        )[:8]
        replan_directives = _mapping_list(
            persisted_replan.get("directives") or synthesis_payload.get("replan_directives"),
        )[:8] or _mapping_list(compiled_replan.directives)[:8]
        replan_recommended_actions = _mapping_list(
            persisted_replan.get("recommended_actions") or synthesis_payload.get("recommended_actions"),
        )[:8] or _mapping_list(compiled_replan.recommended_actions)[:8]
        replan_activation = _mapping_dict(synthesis_payload.get("activation")) or dict(
            compiled_replan.activation
        )
        if _mapping_dict(persisted_replan.get("activation")):
            replan_activation = {
                **replan_activation,
                **_mapping_dict(persisted_replan.get("activation")),
            }
        return {
            "is_truth_store": False,
            "overlap_with_formal_review": overlap_with_formal_review,
            "source": (
                "formal-cycle-review-overlap"
                if overlap_with_formal_review
                else "prediction-cycle-review"
            ),
            "review_ref": review_ref,
            "review_window": _string(planning_context.get("review_window")) or meeting_window,
            "cycle_id": cycle_id,
            "meeting_window": meeting_window,
            "summary": _string(planning_context.get("summary")),
            "planning_policy": _string_list(planning_context.get("planning_policy"))[:8],
            "strategy_constraints": strategy_constraints,
            "cycle_decision": cycle_decision,
            "selected_lane_ids": _string_list(planning_context.get("selected_lane_ids"))[:8],
            "selected_backlog_item_ids": _string_list(
                planning_context.get("selected_backlog_item_ids"),
            )[:12],
            "participant_count": len(list(participant_inputs or [])),
            "assignment_count": len(list(assignment_summaries or [])),
            "lane_count": len(list(lane_summaries or [])),
            "pending_report_count": pending_report_count,
            "open_backlog_count": open_backlog_count,
            "replan": {
                "status": replan_status,
                "decision_kind": replan_decision_kind,
                "decision_id": replan_decision_id,
                "summary": replan_summary,
                "reason_ids": replan_reason_ids,
                "source_report_ids": replan_source_report_ids,
                "topic_keys": replan_topic_keys,
                "trigger_families": trigger_families,
                "trigger_rule_ids": trigger_rule_ids,
                "affected_lane_ids": affected_lane_ids,
                "affected_uncertainty_ids": affected_uncertainty_ids,
                "trigger_context": trigger_context,
                "directives": replan_directives,
                "recommended_actions": replan_recommended_actions,
                "activation": replan_activation,
                "directive_count": len(replan_directives),
                "recommended_action_count": len(replan_recommended_actions),
                "activation_keys": sorted(replan_activation.keys())[:8],
            },
        }

    def _persist_cycle_case_planning_snapshot(
        self,
        case_id: str,
        planning_snapshot: dict[str, Any],
    ) -> PredictionCaseDetail:
        case = self._case_repository.get_case(case_id)
        if case is None:
            raise KeyError(f"Prediction case '{case_id}' not found")
        metadata = _safe_dict(case.metadata)
        metadata["planning_overlap"] = bool(planning_snapshot.get("overlap_with_formal_review"))
        metadata["planning_snapshot"] = dict(planning_snapshot)
        input_payload = _safe_dict(case.input_payload)
        input_payload["planning"] = dict(planning_snapshot)
        updated = case.model_copy(
            update={
                "metadata": metadata,
                "input_payload": input_payload,
            },
        )
        self._case_repository.upsert_case(updated)
        return self.get_case_detail(case_id)

    async def execute_recommendation(
        self,
        case_id: str,
        recommendation_id: str,
        *,
        actor: str = "copaw-operator",
    ) -> PredictionRecommendationExecutionResponse:
        record = self._recommendation_repository.get_recommendation(recommendation_id)
        if record is None or record.case_id != case_id:
            raise KeyError(
                f"Prediction recommendation '{recommendation_id}' not found for case '{case_id}'",
            )
        record, _ = self._refresh_recommendation(record)
        if not record.executable:
            raise ValueError("Recommendation is review-only and cannot be executed")
        if self._kernel_dispatcher is None:
            raise RuntimeError("Kernel dispatcher is not available")
        task = KernelTask(
            title=record.title,
            capability_ref=record.action_kind,
            owner_agent_id=actor or record.target_agent_id or "copaw-operator",
            risk_level=record.risk_level,
            payload=dict(record.action_payload or {}),
        )
        admitted = self._kernel_dispatcher.submit(task)
        execution = admitted.model_dump(mode="json")
        updated = record.model_copy(
            update={
                "execution_task_id": task.id,
                "decision_request_id": admitted.decision_request_id or record.decision_request_id,
                "status": self._status_from_phase(execution.get("phase"), fallback=record.status),
                "outcome_summary": str(execution.get("summary") or record.outcome_summary or ""),
                "auto_executed": record.auto_executed or actor.startswith("copaw-auto"),
                "updated_at": _utc_now(),
            },
        )
        self._recommendation_repository.upsert_recommendation(updated)
        if admitted.phase == "executing":
            executed = await self._kernel_dispatcher.execute_task(task.id)
            execution = executed.model_dump(mode="json")
            execution_metadata = self._recommendation_execution_metadata(
                updated,
                execution=execution,
            )
            updated = updated.model_copy(
                update={
                    "decision_request_id": executed.decision_request_id or updated.decision_request_id,
                    "execution_evidence_id": executed.evidence_id,
                    "status": self._status_from_phase(execution.get("phase"), fallback=updated.status),
                    "outcome_summary": str(execution.get("summary") or updated.outcome_summary or ""),
                    "metadata": execution_metadata,
                    "updated_at": _utc_now(),
                },
            )
            self._recommendation_repository.upsert_recommendation(updated)
            self._record_executed_lifecycle_decision(
                record=updated,
                execution=execution,
                actor=actor,
            )
        detail = self.get_case_detail(case_id)
        return PredictionRecommendationExecutionResponse(
            execution=execution,
            decision=self._decision_payload(updated.decision_request_id),
            detail=detail,
        )

    def _record_executed_lifecycle_decision(
        self,
        *,
        record: PredictionRecommendationRecord,
        execution: dict[str, Any],
        actor: str,
    ) -> None:
        service = getattr(self, "_skill_lifecycle_decision_service", None)
        create_decision = getattr(service, "create_decision", None)
        list_decisions = getattr(service, "list_decisions", None)
        if not callable(create_decision):
            return
        if str(record.action_kind or "").strip() != "system:apply_capability_lifecycle":
            return
        if self._status_from_phase(execution.get("phase"), fallback=record.status) != "executed":
            return
        action_payload = _safe_dict(record.action_payload)
        metadata = _safe_dict(record.metadata)
        candidate_id = _string(action_payload.get("candidate_id")) or _string(metadata.get("candidate_id"))
        if candidate_id is None:
            return
        decision_kind = _string(action_payload.get("decision_kind"))
        stage_mapping = {
            "continue_trial": ("candidate", "trial"),
            "keep_seat_local": ("trial", "trial"),
            "replace_existing": ("candidate", "trial"),
            "promote_to_role": ("trial", "active"),
            "rollback": ("trial", "blocked"),
            "retire": ("active", "retired"),
        }
        if decision_kind not in stage_mapping:
            return
        source_recommendation_id = record.recommendation_id
        if callable(list_decisions):
            existing = list_decisions(candidate_id=candidate_id, limit=100)
            for item in existing:
                item_metadata = _safe_dict(getattr(item, "metadata", None))
                if (
                    getattr(item, "decision_kind", None) == decision_kind
                    and _string(item_metadata.get("source_recommendation_id")) == source_recommendation_id
                    and _string(item_metadata.get("execution_status")) == "executed"
                ):
                    return
        from_stage, to_stage = stage_mapping[decision_kind]
        create_decision(
            candidate_id=candidate_id,
            decision_kind=decision_kind,
            from_stage=from_stage,
            to_stage=to_stage,
            reason=_string(action_payload.get("reason")) or _string(metadata.get("optimization_stage")) or decision_kind,
            evidence_refs=_string_list(record.execution_evidence_id),
            replacement_target_ids=_string_list(
                action_payload.get("replacement_target_ids"),
                action_payload.get("rollback_target_ids"),
                metadata.get("replacement_target_ids"),
                metadata.get("rollback_target_ids"),
            ),
            protection_lifted=False,
            applied_by=_string(actor) or "prediction-service",
            metadata=_merge_adapter_metadata(
                metadata,
                {
                "source_recommendation_id": source_recommendation_id,
                "execution_status": "executed",
                "gap_kind": _string(metadata.get("gap_kind")),
                "trial_scope": _string(metadata.get("trial_scope")),
                "selected_seat_ref": _string(action_payload.get("selected_seat_ref"))
                or _string(metadata.get("selected_seat_ref"))
                or _string(metadata.get("source_trial_seat_ref")),
                },
            ),
        )

    def get_active_team_role_gap_recommendation(
        self,
        *,
        industry_instance_id: str,
    ) -> dict[str, Any] | None:
        normalized_instance_id = _string(industry_instance_id)
        if normalized_instance_id is None:
            return None
        case_records = self._case_repository.list_cases(
            industry_instance_id=normalized_instance_id,
            limit=60,
        )
        if not case_records:
            return None
        case_by_id = {record.case_id: record for record in case_records}
        recommendation_records = self._recommendation_repository.list_recommendations(
            case_ids=list(case_by_id),
            limit=240,
        )
        ranked: list[tuple[int, datetime, float, dict[str, Any]]] = []
        for record in recommendation_records:
            refreshed, _ = self._refresh_recommendation(record)
            if not refreshed.executable or refreshed.action_kind != "system:update_industry_team":
                continue
            if refreshed.status not in _ACTIVE_TEAM_ROLE_GAP_STATUSES:
                continue
            metadata = _safe_dict(refreshed.metadata)
            if str(metadata.get("gap_kind") or "").strip() != "team_role_gap":
                continue
            case = case_by_id.get(refreshed.case_id) or self._case_repository.get_case(
                refreshed.case_id,
            )
            if case is None:
                continue
            view = self._recommendation_view(refreshed)
            ranked.append(
                (
                    _ACTIVE_TEAM_ROLE_GAP_STATUS_PRIORITY.get(refreshed.status, 9),
                    refreshed.updated_at,
                    float(refreshed.confidence or 0.0),
                    {
                        "case_id": case.case_id,
                        "case_title": _string(case.title) or _string(case.question) or case.case_id,
                        "recommendation_id": refreshed.recommendation_id,
                        "title": refreshed.title,
                        "summary": refreshed.summary,
                        "status": refreshed.status,
                        "risk_level": refreshed.risk_level,
                        "decision_request_id": refreshed.decision_request_id,
                        "suggested_role_id": _string(metadata.get("suggested_role_id")),
                        "suggested_role_name": _string(metadata.get("suggested_role_name")),
                        "workflow_title": _string(metadata.get("workflow_title")),
                        "family_id": _string(metadata.get("family_id")),
                        "match_signals": _string_list(metadata.get("match_signals")),
                        "recommendation": view.recommendation,
                        "decision": view.decision,
                        "routes": dict(view.routes),
                    },
                ),
            )
        if not ranked:
            return None
        ranked.sort(
            key=lambda item: (
                item[0],
                -item[1].timestamp(),
                -item[2],
            ),
        )
        return ranked[0][3]

    def reject_recommendation(
        self,
        case_id: str,
        recommendation_id: str,
        *,
        actor: str = "copaw-operator",
        summary: str | None = None,
    ) -> PredictionCaseDetail:
        record = self._recommendation_repository.get_recommendation(recommendation_id)
        if record is None or record.case_id != case_id:
            raise KeyError(
                f"Prediction recommendation '{recommendation_id}' not found for case '{case_id}'",
            )
        record, _ = self._refresh_recommendation(record)
        if record.status in {"executed", "rejected", "failed"}:
            raise ValueError("Recommendation is already resolved")
        resolution = (
            _string(summary)
            or f"{actor or 'copaw-operator'} rejected recommendation '{recommendation_id}'"
        )
        decision_id = _string(record.decision_request_id)
        if (
            decision_id is not None
            and self._decision_request_repository is not None
            and self._kernel_dispatcher is not None
        ):
            decision = self._decision_request_repository.get_decision_request(decision_id)
            if decision is not None and decision.status in {"open", "reviewing"}:
                self._kernel_dispatcher.reject_decision(
                    decision_id,
                    resolution=resolution,
                )
                return self.get_case_detail(case_id)
        self._set_recommendation_status(record, "rejected", resolution)
        return self.get_case_detail(case_id)

    def add_review(
        self,
        case_id: str,
        payload: PredictionReviewCreateRequest,
    ) -> PredictionCaseDetail:
        case = self._case_repository.get_case(case_id)
        if case is None:
            raise KeyError(f"Prediction case '{case_id}' not found")
        if payload.recommendation_id:
            recommendation = self._recommendation_repository.get_recommendation(
                payload.recommendation_id,
            )
            if recommendation is None or recommendation.case_id != case_id:
                raise KeyError(
                    f"Prediction recommendation '{payload.recommendation_id}' not found for case '{case_id}'",
                )
        review = PredictionReviewRecord(
            case_id=case_id,
            recommendation_id=_string(payload.recommendation_id),
            reviewer=_string(payload.reviewer),
            summary=payload.summary,
            outcome=payload.outcome,
            adopted=payload.adopted,
            benefit_score=payload.benefit_score,
            actual_payload=dict(payload.actual_payload or {}),
            metadata=dict(payload.metadata or {}),
        )
        self._review_repository.upsert_review(review)
        updated_case = case.model_copy(
            update={
                "status": "closed" if payload.outcome != "unknown" else "reviewing",
                "updated_at": _utc_now(),
                "metadata": {
                    **dict(case.metadata or {}),
                    "latest_review_outcome": payload.outcome,
                    "latest_review_id": review.review_id,
                },
            },
        )
        self._case_repository.upsert_case(updated_case)
        return self.get_case_detail(case_id)

    def get_runtime_capability_optimization_overview(
        self,
        *,
        industry_instance_id: str | None = None,
        owner_scope: str | None = None,
        limit: int = 12,
        history_limit: int = 8,
        window_days: int = 14,
    ) -> PredictionCapabilityOptimizationOverview:
        since = _utc_now() - timedelta(days=max(1, window_days))
        case_records = self._case_repository.list_cases(
            industry_instance_id=industry_instance_id,
            owner_scope=owner_scope,
            limit=120,
        )
        case_by_id = {record.case_id: record for record in case_records}
        case_ids = list(case_by_id)
        if not case_ids:
            return PredictionCapabilityOptimizationOverview(
                routes={
                    "predictions": "/api/predictions",
                },
            )

        recommendation_records = self._recommendation_repository.list_recommendations(
            case_ids=case_ids,
            activity_since=since,
            limit=max(limit + history_limit + 48, 120),
        )
        items: list[PredictionCapabilityOptimizationItem] = []
        for record in recommendation_records:
            if not self._is_capability_optimization_recommendation(record):
                continue
            case = case_by_id.get(record.case_id) or self._case_repository.get_case(
                record.case_id,
            )
            if case is None:
                continue
            recommendation_view = self._recommendation_view(record)
            status_bucket = self._capability_optimization_status_bucket(
                str(
                    recommendation_view.recommendation.get("status")
                    or record.status
                    or "",
                ),
            )
            items.append(
                PredictionCapabilityOptimizationItem(
                    case=case.model_dump(mode="json"),
                    recommendation=recommendation_view,
                    status_bucket=status_bucket,  # type: ignore[arg-type]
                    routes={
                        "case": _route_prediction(case.case_id),
                        **recommendation_view.routes,
                    },
                ),
            )

        actionable = [item for item in items if item.status_bucket == "actionable"]
        history = [item for item in items if item.status_bucket == "history"]
        actionable.sort(key=self._capability_optimization_actionable_sort_key)
        history.sort(
            key=self._capability_optimization_history_sort_key,
            reverse=True,
        )

        summary = PredictionCapabilityOptimizationSummary(
            total_items=len(items),
            actionable_count=len(actionable),
            history_count=len(history),
            case_count=len(
                {
                    str(item.case.get("case_id") or "").strip()
                    for item in items
                    if str(item.case.get("case_id") or "").strip()
                },
            ),
            missing_capability_count=sum(
                1
                for item in items
                if self._capability_optimization_gap_kind(item)
                == "missing_capability"
            ),
            underperforming_capability_count=sum(
                1
                for item in items
                if self._capability_optimization_gap_kind(item)
                == "underperforming_capability"
            ),
            trial_count=sum(
                1
                for item in items
                if self._capability_optimization_stage(item) == "trial"
            ),
            rollout_count=sum(
                1
                for item in items
                if self._capability_optimization_stage(item) == "rollout"
            ),
            retire_count=sum(
                1
                for item in items
                if self._capability_optimization_stage(item) == "retire"
            ),
            waiting_confirm_count=sum(
                1
                for item in items
                if str(item.recommendation.recommendation.get("status") or "")
                == "waiting-confirm"
            ),
            manual_only_count=sum(
                1
                for item in items
                if str(item.recommendation.recommendation.get("status") or "")
                == "manual-only"
            ),
            executed_count=sum(
                1
                for item in items
                if str(item.recommendation.recommendation.get("status") or "")
                == "executed"
            ),
        )
        portfolio = self._build_governed_portfolio_summary()
        discovery = self._build_discovery_summary()
        return PredictionCapabilityOptimizationOverview(
            summary=summary,
            actionable=actionable[: max(1, limit)],
            history=history[: max(1, history_limit)],
            portfolio=portfolio,
            discovery=discovery,
            routes={
                "predictions": "/api/predictions",
            },
        )

    def _build_governed_portfolio_summary(self) -> dict[str, Any]:
        portfolio_service = getattr(self, "_capability_portfolio_service", None)
        getter = getattr(portfolio_service, "get_runtime_portfolio_summary", None)
        payload = getter() if callable(getter) else {}
        return _mapping_dict(payload)

    def _build_discovery_summary(self) -> dict[str, Any]:
        portfolio_service = getattr(self, "_capability_portfolio_service", None)
        getter = getattr(portfolio_service, "get_runtime_discovery_summary", None)
        payload = getter() if callable(getter) else {}
        return _mapping_dict(payload)
