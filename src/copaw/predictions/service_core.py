# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403


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
        return PredictionCaseDetail(
            case=case.model_dump(mode="json"),
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
        force: bool = False,
    ) -> PredictionCaseDetail | None:
        normalized_instance_id = _string(industry_instance_id)
        normalized_owner_scope = _string(owner_scope)
        if normalized_instance_id is None or normalized_owner_scope is None:
            return None
        normalized_meeting_window = _string(meeting_window) or "cycle-review"
        local_review_date = datetime.now().astimezone().date().isoformat()
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
                    return self.get_case_detail(case.case_id)
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
            },
        )
        return self.create_case(request, case_kind="cycle")

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
        detail = self.get_case_detail(case_id)
        return PredictionRecommendationExecutionResponse(
            execution=execution,
            decision=self._decision_payload(updated.decision_request_id),
            detail=detail,
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
        return PredictionCapabilityOptimizationOverview(
            summary=summary,
            actionable=actionable[: max(1, limit)],
            history=history[: max(1, history_limit)],
            routes={
                "predictions": "/api/predictions",
            },
        )
