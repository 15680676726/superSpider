# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from time import perf_counter

from .service_context import *  # noqa: F401,F403
from .service_recommendation_search import *  # noqa: F401,F403
from .service_recommendation_pack import *  # noqa: F401,F403
from ..capabilities.lifecycle_assignment import (
    build_capability_lifecycle_assignment_payload,
)
from ..kernel.governed_mutation_dispatch import dispatch_governed_mutation_runtime

logger = logging.getLogger(__name__)


class _IndustryActivationMixin:
    def _build_capability_lifecycle_assignment_payload(
        self,
        *,
        agent_id: str,
        capability_ids: list[str],
        capability_assignment_mode: str,
        reason: str,
        actor: str,
    ) -> dict[str, object]:
        payload = build_capability_lifecycle_assignment_payload(
            agent_profile_service=self._agent_profile_service,
            target_agent_id=agent_id,
            capability_ids=capability_ids,
            capability_assignment_mode=capability_assignment_mode,
            reason=reason,
            actor=actor,
        )
        payload["governed_mutation"] = True
        return payload

    async def auto_close_capability_gap_for_instance(
        self,
        instance_id: str,
        recommendation: IndustryCapabilityRecommendation,
        *,
        target_agent_ids: list[str] | None = None,
        capability_ids: list[str] | None = None,
        capability_assignment_mode: Literal["replace", "merge"] = "merge",
        review_acknowledged: bool = False,
    ) -> IndustryBootstrapInstallResult:
        started_at = perf_counter()
        logger.info(
            "Industry auto-close capability gap start: instance=%s recommendation=%s install_kind=%s",
            instance_id,
            recommendation.recommendation_id,
            recommendation.install_kind,
        )
        detail = self.get_instance_detail(instance_id)
        if detail is None:
            raise KeyError(f"Industry instance '{instance_id}' not found")
        normalized_mode = (
            capability_assignment_mode
            if capability_assignment_mode in {"replace", "merge"}
            else "merge"
        )
        plan = _IndustryPlan(
            profile=detail.profile,
            owner_scope=detail.owner_scope,
            draft=self._build_draft_from_instance_detail(detail),
            goal_seeds=[],
            schedule_seeds=[],
            recommendation_pack=IndustryCapabilityRecommendationPack(
                summary="Runtime capability gap closure plan.",
                items=[recommendation],
            ),
            readiness_checks=[],
            media_analyses=[],
            media_analysis_ids=[],
            media_warnings=[],
        )
        resolved_target_agent_ids = _unique_strings(
            target_agent_ids,
            recommendation.target_agent_ids,
        )
        resolved_capability_ids = _unique_strings(
            capability_ids,
            recommendation.capability_ids,
        )
        install_item = IndustryBootstrapInstallItem(
            recommendation_id=recommendation.recommendation_id,
            install_kind=recommendation.install_kind,
            template_id=recommendation.template_id,
            install_option_key=recommendation.install_option_key,
            client_key=recommendation.default_client_key or None,
            bundle_url=recommendation.source_url or None,
            version=recommendation.version or None,
            source_kind=recommendation.source_kind,
            source_label=recommendation.source_label or None,
            review_acknowledged=review_acknowledged,
            enabled=bool(recommendation.default_enabled),
            required=False,
            capability_assignment_mode=normalized_mode,
            capability_ids=resolved_capability_ids,
            target_agent_ids=resolved_target_agent_ids,
            target_role_ids=list(recommendation.suggested_role_ids or []),
        )
        if recommendation.review_required or recommendation.risk_level != "auto":
            return IndustryBootstrapInstallResult(
                recommendation_id=recommendation.recommendation_id,
                install_kind=recommendation.install_kind,
                template_id=recommendation.template_id,
                install_option_key=recommendation.install_option_key,
                client_key=recommendation.default_client_key or "",
                capability_ids=resolved_capability_ids,
                source_kind=recommendation.source_kind,
                source_label=recommendation.source_label,
                source_url=recommendation.source_url,
                version=recommendation.version,
                status="skipped",
                detail=(
                    "Automatic gap closure only installs low-risk recommendations. "
                    "This recommendation still requires governed review."
                ),
                installed=False,
            )
        resolved_targets = self._resolve_install_targets(
            team=plan.draft.team,
            item=install_item,
            recommendation=recommendation,
        )
        if not resolved_targets:
            return IndustryBootstrapInstallResult(
                recommendation_id=recommendation.recommendation_id,
                install_kind=recommendation.install_kind,
                template_id=recommendation.template_id,
                install_option_key=recommendation.install_option_key,
                client_key=recommendation.default_client_key or "",
                capability_ids=resolved_capability_ids,
                source_kind=recommendation.source_kind,
                source_label=recommendation.source_label,
                source_url=recommendation.source_url,
                version=recommendation.version,
                status="skipped",
                detail=(
                    "Automatic gap closure requires a resolvable target seat or role."
                ),
                installed=False,
            )
        install_item.target_agent_ids = resolved_targets
        results = await self._execute_install_plan(
            plan=plan,
            install_plan=[install_item],
            governed_mode=True,
            governed_actor="industry-bootstrap",
            governed_risk_level_override="auto",
        )
        result = (
            results[0]
            if results
            else IndustryBootstrapInstallResult(
                recommendation_id=recommendation.recommendation_id,
                install_kind=recommendation.install_kind,
                template_id=recommendation.template_id,
                install_option_key=recommendation.install_option_key,
                client_key=recommendation.default_client_key or "",
                capability_ids=resolved_capability_ids,
                source_kind=recommendation.source_kind,
                source_label=recommendation.source_label,
                source_url=recommendation.source_url,
                version=recommendation.version,
                status="failed",
                detail="Automatic gap closure did not return an install result.",
                installed=False,
            )
        )
        logger.info(
            "Industry auto-close capability gap finish: instance=%s recommendation=%s elapsed=%.2fs status=%s detail=%s",
            instance_id,
            recommendation.recommendation_id,
            perf_counter() - started_at,
            result.status,
            result.detail,
        )
        return result

    async def _activate_plan(
        self,
        *,
        plan: _IndustryPlan,
        goal_priority: int,
        auto_activate: bool,
        auto_dispatch: bool,
        execute: bool,
        install_plan: list[IndustryBootstrapInstallItem],
        auto_start_learning: bool = False,
    ) -> IndustryBootstrapResponse:
        pending_chat_kickoff = (
            auto_start_learning and auto_activate and not auto_dispatch and not execute
        )
        initial_agent_status = (
            "waiting-confirm"
            if pending_chat_kickoff
            else "running" if auto_dispatch else "idle"
        )
        initial_goal_status = (
            "paused" if pending_chat_kickoff else "active" if auto_activate else "draft"
        )
        install_results = await self._execute_install_plan(
            plan=plan,
            install_plan=list(install_plan or []),
        )
        team_id = plan.draft.team.team_id
        existing = self._industry_instance_repository.get_instance(team_id)
        existing_strategy = (
            self._peek_strategy_memory(existing)
            if existing is not None
            else None
        )
        placeholder = self._build_instance_record(
            plan,
            existing=existing,
            status="active" if auto_activate else "draft",
            lifecycle_status="running" if auto_activate else "draft",
            autonomy_status="waiting-confirm" if pending_chat_kickoff else "coordinating" if auto_activate else "draft",
        )
        self._industry_instance_repository.upsert_instance(placeholder)
        lanes = (
            self._operating_lane_service.seed_from_roles(
                industry_instance_id=team_id,
                roles=plan.draft.team.agents,
                lane_weights=existing_strategy.lane_weights if existing_strategy is not None else None,
            )
            if self._operating_lane_service is not None
            else []
        )

        goal_ids: list[str] = []
        goal_by_agent_id: dict[str, tuple[str, str]] = {}
        goal_specs: list[dict[str, object]] = []
        for agent in plan.draft.team.agents:
            self._upsert_agent_profile(
                agent,
                instance_id=team_id,
                goal_id=None,
                goal_title=None,
                status=initial_agent_status,
            )

        for seed in plan.goal_seeds:
            lane = self._resolve_goal_lane(
                instance_id=team_id,
                role=seed.role,
                goal_kind=seed.kind,
                owner_agent_id=seed.owner_agent_id,
            )
            goal_ids.append(seed.goal_id)
            goal_by_agent_id.setdefault(seed.owner_agent_id, (seed.goal_id, seed.title))
            goal_specs.append(
                {
                    "goal_id": seed.goal_id,
                    "kind": seed.kind,
                    "goal_kind": seed.kind,
                    "owner_agent_id": seed.owner_agent_id,
                    "industry_role_id": seed.role.role_id,
                    "lane_id": lane.id if lane is not None else None,
                    "title": seed.title,
                    "summary": seed.summary,
                    "priority": goal_priority,
                    "goal_class": "bootstrap-goal",
                },
            )
            self._upsert_agent_profile(
                seed.role,
                instance_id=team_id,
                goal_id=seed.goal_id,
                goal_title=seed.title,
                status=initial_agent_status,
            )

        schedule_specs: list[dict[str, object]] = []
        schedule_enabled = False if pending_chat_kickoff else auto_dispatch or execute
        for seed in plan.schedule_seeds:
            lane = self._resolve_goal_lane(
                instance_id=team_id,
                role=self._resolve_role_blueprint(plan.draft.team, seed.metadata.get("industry_role_id")),
                goal_kind=_string(seed.metadata.get("goal_kind")),
                owner_agent_id=seed.owner_agent_id,
            )
            schedule_specs.append(
                {
                    "schedule_id": seed.schedule_id,
                    "title": seed.title,
                    "summary": seed.summary,
                    "lane_id": lane.id if lane is not None else None,
                    "schedule_kind": "cadence",
                    "trigger_target": _string(seed.metadata.get("goal_kind")) or "main-brain",
                    "spec_payload": self._build_schedule_spec(
                        seed,
                        enabled=schedule_enabled,
                    ),
                },
            )

        backlog_items = (
            self._backlog_service.seed_bootstrap_items_from_goal_specs(
                industry_instance_id=team_id,
                goal_specs=goal_specs,
                schedule_specs=schedule_specs,
            )
            if self._backlog_service is not None
            else []
        )
        planning_activation_result = self._resolve_planning_activation_result(
            record=placeholder,
            open_backlog=backlog_items,
            pending_reports=[],
        )
        planning_task_subgraph = self._resolve_planning_task_subgraph(
            record=placeholder,
            open_backlog=backlog_items,
            pending_reports=[],
            activation_result=planning_activation_result,
        )
        bootstrap_strategy_constraints = self._apply_activation_to_strategy_constraints(
            constraints=self._compile_strategy_constraints(record=placeholder),
            activation_result=planning_activation_result,
        )
        strategy_constraints_payload = self._strategy_constraints_sidecar_payload(
            record=placeholder,
            strategy_constraints=bootstrap_strategy_constraints,
        )
        bootstrap_cycle_decision_payload = {
            "reason": "bootstrap-seeded-cycle",
            "cycle_kind": "daily",
            "should_start": True,
            "summary": "Bootstrap operating cycle.",
            "selected_lane_ids": [lane.id for lane in lanes],
            "selected_backlog_item_ids": [
                item.id for item in backlog_items if item.goal_id is not None
            ],
            "metadata": {
                "bootstrap_kind": "industry-v1",
                "source_ref": "industry-bootstrap",
            },
        }
        bootstrap_cycle_planning_metadata = {
            "strategy_constraints": strategy_constraints_payload,
            "cycle_decision": bootstrap_cycle_decision_payload,
            "report_replan": {},
        }
        current_cycle = (
            self._operating_cycle_service.start_cycle(
                industry_instance_id=team_id,
                label=plan.draft.team.label or plan.profile.primary_label(),
                cycle_kind="daily",
                status=(
                    "waiting-confirm"
                    if pending_chat_kickoff
                    else "active" if auto_activate else "planned"
                ),
                focus_lane_ids=[lane.id for lane in lanes],
                backlog_item_ids=[
                    item.id
                    for item in backlog_items
                    if item.goal_id is not None
                ],
                source_ref="industry-bootstrap",
                summary="Bootstrap operating cycle.",
                metadata={"formal_planning": bootstrap_cycle_planning_metadata},
            )
            if self._operating_cycle_service is not None
            else None
        )
        assignment_specs: list[dict[str, object]] = []
        if current_cycle is not None:
            backlog_item_by_goal_id = {
                item.goal_id: item
                for item in backlog_items
                if item.goal_id is not None
            }
            for seed in plan.goal_seeds:
                lane = self._resolve_goal_lane(
                    instance_id=team_id,
                    role=seed.role,
                    goal_kind=seed.kind,
                    owner_agent_id=seed.owner_agent_id,
                )
                backlog_item = backlog_item_by_goal_id.get(seed.goal_id)
                assignment_plan = (
                    self._assignment_planner.plan(
                        assignment_id=self._stable_assignment_id(
                            cycle_id=current_cycle.id,
                            goal_id=seed.goal_id,
                            backlog_item_id=backlog_item.id if backlog_item is not None else None,
                            title=seed.title,
                        ),
                        cycle_id=current_cycle.id,
                        backlog_item=backlog_item,
                        lane=lane,
                        strategy_constraints=bootstrap_strategy_constraints,
                        task_subgraph=planning_task_subgraph,
                    )
                    if backlog_item is not None
                    else None
                )
                assignment_plan_payload = self._planner_sidecar_payload(assignment_plan)
                assignment_metadata = {
                    "bootstrap_kind": "industry-v1",
                    "kickoff_stage": _string(
                        seed.compiler_context.get("kickoff_stage"),
                    )
                    or "execution",
                    "goal_kind": seed.kind,
                    "industry_role_id": seed.role.role_id,
                    "owner_agent_id": seed.owner_agent_id,
                    "source_ref": f"goal:{seed.goal_id}",
                    "source_kind": "bootstrap-goal",
                }
                if assignment_plan is not None:
                    assignment_metadata.update(dict(assignment_plan.metadata or {}))
                    assignment_metadata["formal_planning"] = {
                        "strategy_constraints": dict(strategy_constraints_payload),
                        "cycle_decision": dict(bootstrap_cycle_decision_payload),
                        "report_replan": {},
                        "assignment_plan": assignment_plan_payload,
                    }
                assignment_specs.append(
                    {
                        "goal_id": seed.goal_id,
                        "lane_id": lane.id if lane is not None else None,
                        "owner_agent_id": (
                            assignment_plan.owner_agent_id
                            if assignment_plan is not None
                            else seed.owner_agent_id
                        ),
                        "owner_role_id": (
                            assignment_plan.owner_role_id
                            if assignment_plan is not None
                            else seed.role.role_id
                        ),
                        "title": seed.title,
                        "summary": seed.summary,
                        "goal_status": initial_goal_status,
                        "backlog_item_id": next(
                            (
                                item.id
                                for item in backlog_items
                                if item.goal_id == seed.goal_id
                            ),
                            None,
                        ),
                        "report_back_mode": (
                            assignment_plan.report_back_mode
                            if assignment_plan is not None
                            else "summary"
                        ),
                        "metadata": assignment_metadata,
                    },
                )
        assignments = (
            self._assignment_service.ensure_assignments(
                industry_instance_id=team_id,
                cycle_id=current_cycle.id,
                specs=assignment_specs,
            )
            if self._assignment_service is not None and current_cycle is not None
            else []
        )
        if current_cycle is not None and self._operating_cycle_service is not None:
            current_cycle = self._operating_cycle_service.update_cycle_links(
                current_cycle,
                assignment_ids=[assignment.id for assignment in assignments],
            )
        if self._backlog_service is not None and current_cycle is not None:
            assignment_map = {
                assignment.goal_id: assignment
                for assignment in assignments
                if assignment.goal_id
            }
            for item in backlog_items:
                if item.goal_id is None:
                    continue
                assignment = assignment_map.get(item.goal_id)
                self._backlog_service.mark_item_materialized(
                    item,
                    cycle_id=current_cycle.id,
                    goal_id=item.goal_id,
                    assignment_id=assignment.id if assignment is not None else None,
                )

        persisted_schedules = []
        for schedule_spec, seed in zip(schedule_specs, plan.schedule_seeds):
            await self._persist_schedule_spec(dict(schedule_spec["spec_payload"]))
            self._upsert_schedule_lane(
                schedule_id=seed.schedule_id,
                lane_id=_string(schedule_spec.get("lane_id")),
                schedule_kind=_string(schedule_spec.get("schedule_kind")) or "cadence",
                trigger_target=(
                    _string(schedule_spec.get("trigger_target")) or "main-brain"
                ),
            )
            if self._schedule_repository is None:
                continue
            schedule = self._schedule_repository.get_schedule(seed.schedule_id)
            if schedule is not None:
                persisted_schedules.append(schedule)

        for seed in plan.goal_seeds:
            lane = self._resolve_goal_lane(
                instance_id=team_id,
                role=seed.role,
                goal_kind=seed.kind,
                owner_agent_id=seed.owner_agent_id,
            )
            goal = self._goal_service.create_goal(
                goal_id=seed.goal_id,
                title=seed.title,
                summary=seed.summary,
                status=initial_goal_status,
                priority=goal_priority,
                owner_scope=plan.owner_scope,
                industry_instance_id=team_id,
                lane_id=lane.id if lane is not None else None,
                cycle_id=current_cycle.id if current_cycle is not None else None,
                goal_class="bootstrap-goal",
            )
            override = self._goal_override_repository.upsert_override(
                GoalOverrideRecord(
                    goal_id=seed.goal_id,
                    plan_steps=list(seed.plan_steps),
                    compiler_context={
                        "channel": "industry",
                        "bootstrap_kind": "industry-v1",
                        "industry_instance_id": team_id,
                        "lane_id": lane.id if lane is not None else None,
                        "report_back_mode": "summary",
                        **seed.compiler_context,
                    },
                    reason=f"Industry bootstrap for {plan.profile.primary_label()}",
                ),
            )
        if auto_dispatch:
            await self._dispatch_operating_cycle_assignments(
                instance_id=team_id,
                assignment_ids=[assignment.id for assignment in assignments],
                actor=EXECUTION_CORE_AGENT_ID,
                allow_waiting_confirm=True,
                include_execution_core=True,
                execute_background=execute,
            )

        for agent in plan.draft.team.agents:
            goal_link = goal_by_agent_id.get(agent.agent_id)
            if goal_link is not None:
                self._upsert_agent_profile(
                    agent,
                    instance_id=team_id,
                    goal_id=None,
                    goal_title=None,
                    status=initial_agent_status,
                )
            self._sync_actor_runtime_surface(
                agent=agent,
                instance_id=team_id,
                owner_scope=plan.owner_scope,
                goal_id=goal_link[0] if goal_link is not None else None,
                goal_title=goal_link[1] if goal_link is not None else None,
                status=initial_agent_status,
            )
        await self._finalize_install_assignments(
            plan=plan,
            install_plan=list(install_plan or []),
            install_results=install_results,
        )
        self._retire_stale_actors(
            instance_id=team_id,
            active_agent_ids={agent.agent_id for agent in plan.draft.team.agents},
        )
        self._archive_superseded_goals(
            owner_scope=plan.owner_scope,
            active_goal_ids=set(goal_ids),
        )

        final_record = self._build_instance_record(
            plan,
            existing=existing,
            status="active" if auto_activate else "draft",
            lifecycle_status="running" if auto_activate else "draft",
            autonomy_status="waiting-confirm" if pending_chat_kickoff else "coordinating" if auto_activate else "draft",
            current_cycle_id=current_cycle.id if current_cycle is not None else None,
            next_cycle_due_at=current_cycle.due_at if current_cycle is not None else None,
            last_cycle_started_at=current_cycle.started_at if current_cycle is not None else None,
        )
        final_record = self._industry_instance_repository.upsert_instance(final_record)
        if auto_activate:
            await self._retire_other_active_instances(active_instance_id=team_id)
        self._sync_strategy_memory(
            final_record,
            profile=plan.profile,
            team=plan.draft.team,
        )
        if auto_start_learning and pending_chat_kickoff:
            kickoff_result = await self.kickoff_execution_from_chat(
                industry_instance_id=team_id,
                message_text="开始学习",
                owner_agent_id=EXECUTION_CORE_AGENT_ID,
                execute_background=True,
                trigger_source="system:auto-learning-kickoff",
                trigger_reason_override=(
                    "Industry bootstrap automatically started the learning stage."
                ),
            )
            refreshed_record = self.reconcile_instance_status(team_id)
            if refreshed_record is not None:
                final_record = refreshed_record
            await self._maybe_auto_resume_execution_stage(team_id)
        adopted_media_analyses = list(plan.media_analyses or [])
        media_service = getattr(self, "_media_service", None)
        if media_service is not None and plan.media_analysis_ids:
            adopted_media_analyses = await media_service.adopt_analyses_for_industry(
                industry_instance_id=team_id,
                analysis_ids=plan.media_analysis_ids,
            )
        summary = self._build_instance_summary(final_record)
        schedule_summaries = [
            {
                "schedule_id": schedule.id,
                "title": schedule.title,
                "owner_agent_id": _string(schedule.spec_payload.get("meta", {}).get("owner_agent_id")),
                "industry_role_id": _string(
                    schedule.spec_payload.get("request", {}).get("industry_role_id")
                )
                or _string(schedule.spec_payload.get("meta", {}).get("industry_role_id")),
                "goal_kind": _string(schedule.spec_payload.get("meta", {}).get("goal_kind")),
                "cron": schedule.cron,
                "timezone": schedule.timezone,
                "enabled": bool(schedule.spec_payload.get("enabled")),
                "dispatch_mode": _string(schedule.spec_payload.get("dispatch_mode"))
                or _string(schedule.spec_payload.get("request", {}).get("dispatch_mode")),
                "spec_payload": dict(schedule.spec_payload),
                "routes": {
                    "runtime_detail": f"/api/runtime-center/schedules/{schedule.id}",
                },
            }
            for schedule in persisted_schedules
        ]
        return IndustryBootstrapResponse(
            profile=plan.profile,
            team=plan.draft.team,
            draft=plan.draft,
            recommendation_pack=plan.recommendation_pack,
            install_results=install_results,
            backlog=[item.model_dump(mode="json") for item in backlog_items],
            assignments=[assignment.model_dump(mode="json") for assignment in assignments],
            cycle=current_cycle.model_dump(mode="json") if current_cycle is not None else None,
            schedule_summaries=schedule_summaries,
            readiness_checks=plan.readiness_checks,
            media_analyses=adopted_media_analyses,
            routes={
                "runtime_center": "/api/runtime-center/surface",
                "instance": f"/api/industry/v1/instances/{team_id}",
                "runtime_detail": f"/api/runtime-center/industry/{team_id}",
                "agents": [
                    f"/api/runtime-center/agents/{agent.agent_id}"
                    for agent in plan.draft.team.agents
                ],
                "instance_summary": summary.model_dump(mode="json"),
            },
        )

    def _build_draft_from_instance_detail(
        self,
        detail: IndustryInstanceDetail,
    ) -> IndustryDraftPlan:
        team_agents = list(detail.team.agents)
        has_execution_core = any(
            normalize_industry_role_id(role.role_id) == EXECUTION_CORE_ROLE_ID
            for role in team_agents
        )
        execution_core_identity = detail.execution_core_identity
        if not has_execution_core and execution_core_identity is not None:
            team_agents.insert(
                0,
                IndustryRoleBlueprint(
                    role_id=EXECUTION_CORE_ROLE_ID,
                    agent_id=execution_core_identity.agent_id,
                    name=execution_core_identity.role_name,
                    role_name=execution_core_identity.role_name,
                    role_summary=execution_core_identity.role_summary,
                    mission=execution_core_identity.mission,
                    goal_kind=EXECUTION_CORE_ROLE_ID,
                    agent_class="system",
                    employment_mode="career",
                    activation_mode="persistent",
                    suspendable=False,
                    risk_level="guarded",
                    environment_constraints=list(
                        execution_core_identity.environment_constraints or [],
                    ),
                    allowed_capabilities=list(
                        execution_core_identity.allowed_capabilities or [],
                    ),
                    evidence_expectations=list(
                        execution_core_identity.evidence_expectations or [],
                    ),
                ),
            )

        goals: list[IndustryDraftGoal] = []
        for item in detail.goals:
            payload = dict(item) if isinstance(item, dict) else {}
            owner_agent_id = _string(payload.get("owner_agent_id"))
            kind = _string(payload.get("kind")) or _string(payload.get("goal_kind"))
            title = _string(payload.get("title"))
            if owner_agent_id is None or kind is None or title is None:
                continue
            goals.append(
                IndustryDraftGoal(
                    goal_id=_string(payload.get("goal_id")) or kind,
                    kind=kind,
                    owner_agent_id=owner_agent_id,
                    title=title,
                    summary=_string(payload.get("summary")) or "",
                    plan_steps=_unique_strings(payload.get("plan_steps")),
                ),
            )
        if not goals:
            fallback_goal_role = next(
                (
                    role
                    for role in team_agents
                    if role.employment_mode != "temporary"
                    and normalize_industry_role_id(role.role_id) != EXECUTION_CORE_ROLE_ID
                ),
                None,
            ) or next(
                (
                    role
                    for role in team_agents
                    if role.employment_mode != "temporary"
                ),
                None,
            ) or (team_agents[0] if team_agents else None)
            if fallback_goal_role is not None:
                goals.append(
                    self._build_default_goal_for_role(
                        detail.profile,
                        fallback_goal_role,
                    ),
                )

        schedules: list[IndustryDraftSchedule] = []
        for item in detail.schedules:
            payload = dict(item) if isinstance(item, dict) else {}
            schedule_id = _string(payload.get("schedule_id"))
            owner_agent_id = _string(payload.get("owner_agent_id"))
            title = _string(payload.get("title"))
            if schedule_id is None or owner_agent_id is None or title is None:
                continue
            schedules.append(
                IndustryDraftSchedule(
                    schedule_id=schedule_id,
                    owner_agent_id=owner_agent_id,
                    title=title,
                    summary=_string(payload.get("summary")) or "",
                    cron=_string(payload.get("cron")) or "0 9 * * *",
                    timezone=_string(payload.get("timezone")) or "UTC",
                    dispatch_channel=_string(payload.get("dispatch_channel")) or "console",
                    dispatch_mode=(
                        "final"
                        if _string(payload.get("dispatch_mode")) == "final"
                        else "stream"
                    ),
                ),
            )

        return IndustryDraftPlan(
            team=detail.team.model_copy(update={"agents": team_agents}),
            goals=goals,
            schedules=schedules,
        )

    async def build_acquisition_context_for_instance(
        self,
        instance_id: str,
    ) -> dict[str, Any] | None:
        record = self.reconcile_instance_status(instance_id)
        detail = self.get_instance_detail(instance_id)
        if record is None or detail is None:
            return None
        return {
            "record": record,
            "detail": detail,
            "profile": detail.profile,
            "team": detail.team,
            "owner_scope": detail.owner_scope,
            "draft": self._build_draft_from_instance_detail(detail),
            "goal_context_by_agent": self._build_instance_goal_context_by_agent(
                record=record,
            ),
        }

    async def execute_install_plan_for_instance(
        self,
        instance_id: str,
        install_plan: list[IndustryBootstrapInstallItem],
    ) -> list[IndustryBootstrapInstallResult]:
        detail = self.get_instance_detail(instance_id)
        if detail is None:
            raise KeyError(f"Industry instance '{instance_id}' not found")
        plan = _IndustryPlan(
            profile=detail.profile,
            owner_scope=detail.owner_scope,
            draft=self._build_draft_from_instance_detail(detail),
            goal_seeds=[],
            schedule_seeds=[],
            recommendation_pack=IndustryCapabilityRecommendationPack(
                summary="Learning acquisition materialization plan.",
                items=[],
            ),
            readiness_checks=[],
            media_analyses=[],
            media_analysis_ids=[],
            media_warnings=[],
        )
        return await self._execute_install_plan(
            plan=plan,
            install_plan=list(install_plan or []),
        )

    def _build_default_goal_for_role(
        self,
        profile: IndustryProfile,
        role: IndustryRoleBlueprint,
    ) -> IndustryDraftGoal:
        primary_label = profile.primary_label()
        return IndustryDraftGoal(
            goal_id=role.goal_kind or role.role_id,
            kind=role.goal_kind or role.role_id,
            owner_agent_id=role.agent_id,
            title=f"推进 {primary_label} 的 {role.role_name} 闭环",
            summary=_string(role.mission) or _string(role.role_summary) or "",
            plan_steps=[
                f"梳理“{role.role_name}”当前要补齐的执行缺口与验收口径。",
                f"启动首轮“{role.role_name}”动作，并沉淀可复核证据。",
                f"把“{role.role_name}”的结果、风险与下一步建议回写给执行中枢。",
            ],
        )

    def _default_team_update_flags(
        self,
        detail: IndustryInstanceDetail,
    ) -> dict[str, bool]:
        goal_active = any(
            str(item.get("status") or "").strip().lower() == "active"
            for item in detail.goals
            if isinstance(item, dict)
        )
        schedule_enabled = any(
            bool(item.get("enabled"))
            for item in detail.schedules
            if isinstance(item, dict)
        )
        execution_status = _string(
            getattr(detail.execution, "status", None) if detail.execution is not None else None,
        )
        waiting_for_manual_resume = execution_status == "waiting-confirm"
        auto_dispatch = bool(
            goal_active
            or schedule_enabled
            or execution_status in {"active", "running", "working", "blocked", "learning", "coordinating"}
        )
        return {
            "auto_activate": str(detail.status).strip().lower() != "draft",
            "auto_dispatch": auto_dispatch,
            "execute": auto_dispatch and not waiting_for_manual_resume,
        }

    def _build_install_template_recommendations(
        self,
        *,
        profile: IndustryProfile,
        target_roles: list[IndustryRoleBlueprint],
        goal_context_by_agent: dict[str, list[str]],
    ) -> list[IndustryCapabilityRecommendation]:
        discovery_service = self._get_capability_discovery_service()
        if discovery_service is None:
            return []
        builder = getattr(
            discovery_service,
            "build_install_template_recommendations",
            None,
        )
        if not callable(builder):
            return []
        return list(
            builder(
                profile=profile,
                target_roles=target_roles,
                goal_context_by_agent=goal_context_by_agent,
            ),
        )

    def _recommendation_target_roles(
        self,
        team: IndustryTeamBlueprint,
    ) -> list[IndustryRoleBlueprint]:
        target_roles = [
            role
            for role in team.agents
            if not is_execution_core_role_id(role.role_id)
        ]
        if not target_roles:
            target_roles = list(team.agents[:1])
        return target_roles

    def _list_installed_skill_specs(self) -> list[dict[str, str]]:
        if self._capability_service is None:
            return []
        lister = getattr(self._capability_service, "list_skill_specs", None)
        if not callable(lister):
            return []
        try:
            payload = lister()
        except Exception:
            return []
        installed: list[dict[str, str]] = []
        if not isinstance(payload, list):
            return installed
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = _string(item.get("name"))
            if not name:
                continue
            installed.append(
                {
                    "name": name,
                    "source": _string(item.get("source")) or "",
                },
            )
        return installed

    def _find_installed_skill_match(
        self,
        *,
        result: HubSkillResult,
        installed_skills: list[dict[str, str]],
    ) -> dict[str, str] | None:
        source_url = (_string(result.source_url) or "").rstrip("/").lower()
        result_name = (_string(result.name) or "").lower()
        slug_tail = (_string(result.slug) or "").split("/")[-1].strip().lower()
        result_key = _hub_result_key(result)
        for skill in installed_skills:
            source = (_string(skill.get("source")) or "").rstrip("/").lower()
            name = (_string(skill.get("name")) or "").lower()
            if source_url and source == source_url:
                return skill
            if result_name and name == result_name:
                return skill
            if slug_tail and name == slug_tail:
                return skill
            if result_key and source and result_key in source:
                return skill
        return None

    async def _build_hub_skill_recommendations(
        self,
        *,
        profile: IndustryProfile,
        target_roles: list[IndustryRoleBlueprint],
        goal_context_by_agent: dict[str, list[str]],
    ) -> tuple[list[IndustryCapabilityRecommendation], list[str]]:
        if not self._enable_hub_recommendations:
            return [], []
        discovery_service = self._get_capability_discovery_service()
        if discovery_service is None:
            return [], []
        builder = getattr(discovery_service, "build_hub_skill_recommendations", None)
        if not callable(builder):
            return [], []
        items, warnings = await builder(
            profile=profile,
            target_roles=target_roles,
            goal_context_by_agent=goal_context_by_agent,
        )
        return list(items), _unique_strings(warnings)

    async def _build_curated_skill_recommendations(
        self,
        *,
        profile: IndustryProfile,
        target_roles: list[IndustryRoleBlueprint],
        goal_context_by_agent: dict[str, list[str]],
    ) -> tuple[list[IndustryCapabilityRecommendation], list[str]]:
        if not self._enable_curated_skill_catalog:
            return [], []
        discovery_service = self._get_capability_discovery_service()
        if discovery_service is None:
            return [], []
        builder = getattr(
            discovery_service,
            "build_curated_skill_recommendations",
            None,
        )
        if not callable(builder):
            return [], []
        items, warnings = await builder(
            profile=profile,
            target_roles=target_roles,
            goal_context_by_agent=goal_context_by_agent,
        )
        return list(items), _unique_strings(warnings)

    async def _build_recommendation_pack(
        self,
        *,
        profile: IndustryProfile,
        draft: IndustryDraftPlan,
        include_install_templates: bool = True,
        include_remote_sources: bool = True,
        deferred_message: str | None = None,
    ) -> IndustryCapabilityRecommendationPack:
        goal_context_by_agent = _collect_goal_context_by_agent(draft)
        target_roles = self._recommendation_target_roles(draft.team)
        execution_core_roles = [
            role for role in draft.team.agents if is_execution_core_role_id(role.role_id)
        ]
        items = (
            self._build_install_template_recommendations(
                profile=profile,
                target_roles=target_roles,
                goal_context_by_agent=goal_context_by_agent,
            )
            if include_install_templates
            else []
        )
        curated_items: list[IndustryCapabilityRecommendation] = []
        curated_warnings: list[str] = []
        execution_core_curated_items: list[IndustryCapabilityRecommendation] = []
        execution_core_curated_warnings: list[str] = []
        if include_remote_sources:
            curated_items, curated_warnings = await self._build_curated_skill_recommendations(
                profile=profile,
                target_roles=target_roles,
                goal_context_by_agent=goal_context_by_agent,
            )
            if execution_core_roles:
                (
                    execution_core_curated_items,
                    execution_core_curated_warnings,
                ) = await self._build_curated_skill_recommendations(
                    profile=profile,
                    target_roles=execution_core_roles,
                    goal_context_by_agent=goal_context_by_agent,
                )
                non_core_item_keys = {
                    _recommendation_item_key(item)
                    for item in curated_items
                    if _recommendation_item_key(item)
                }
                if non_core_item_keys:
                    execution_core_curated_items = [
                        item
                        for item in execution_core_curated_items
                        if not (
                            "content" in set(_unique_strings(item.capability_families))
                            and _recommendation_item_key(item) in non_core_item_keys
                        )
                    ]
        items.extend(curated_items)
        items.extend(execution_core_curated_items)
        items = _standardize_recommendation_items(items, target_roles)
        sections = _build_recommendation_sections(items, draft.team.agents)
        warnings = _unique_strings(
            curated_warnings,
            execution_core_curated_warnings,
        )
        if deferred_message:
            warnings.append(deferred_message)
        elif not include_remote_sources:
            warnings.append(
                "预览阶段已跳过远程 SkillHub 技能检索；创建身份时会再解析远程技能建议与安装项。"
            )
        if not items and not deferred_message:
            warnings.append(
                "当前草案没有识别出需要在 bootstrap 前预装的安装建议。如需外部 skill、MCP 或运行时，请在角色职责或 allowed_capabilities 中明确声明。"
            )
        summary = (
            f"已为当前团队识别出 {len(items)} 条可复核的安装建议。"
            if items
            else "当前没有需要在 bootstrap 前预装的安装建议。"
        )
        if not items and deferred_message:
            summary = deferred_message
        return IndustryCapabilityRecommendationPack(
            summary=summary,
            items=items,
            warnings=warnings,
            sections=sections,
        )

    def _list_installed_mcp_client_keys(self) -> set[str]:
        if self._capability_service is None:
            return set()
        lister = getattr(self._capability_service, "list_mcp_client_infos", None)
        if not callable(lister):
            return set()
        try:
            payload = lister()
        except Exception:
            return set()
        installed: set[str] = set()
        if not isinstance(payload, list):
            return installed
        for item in payload:
            if not isinstance(item, dict):
                continue
            key = _string(item.get("key"))
            if key:
                installed.add(key)
        return installed

    def _list_installed_mcp_client_configs(self) -> dict[str, MCPClientConfig]:
        try:
            raw_clients = dict(load_config().mcp.clients or {})
        except Exception:
            return {}
        installed: dict[str, MCPClientConfig] = {}
        for key, value in raw_clients.items():
            normalized_key = _string(key)
            if not normalized_key:
                continue
            try:
                installed[normalized_key] = (
                    value
                    if isinstance(value, MCPClientConfig)
                    else MCPClientConfig.model_validate(value)
                )
            except Exception:
                continue
        return installed

    def _find_installed_registry_client_key(
        self,
        *,
        server_name: str,
        installed_clients: dict[str, MCPClientConfig],
    ) -> str | None:
        for client_key, client in installed_clients.items():
            registry = getattr(client, "registry", None)
            if registry is None:
                continue
            if _string(getattr(registry, "server_name", None)) == server_name:
                return client_key
        return None

    def _get_mcp_registry_catalog(self) -> McpRegistryCatalog:
        service = self._get_capability_discovery_service()
        getter = getattr(service, "_get_mcp_registry_catalog", None)
        if callable(getter):
            catalog = getter()
            if catalog is not None:
                return catalog
        return McpRegistryCatalog()

    def _resolve_install_targets(
        self,
        *,
        team: IndustryTeamBlueprint,
        item: IndustryBootstrapInstallItem,
        recommendation: IndustryCapabilityRecommendation | None,
    ) -> list[str]:
        explicit_target_agent_ids = _unique_strings(item.target_agent_ids)
        if explicit_target_agent_ids:
            return explicit_target_agent_ids
        target_role_ids = _unique_strings(
            item.target_role_ids,
            recommendation.suggested_role_ids if recommendation is not None else [],
        )
        if target_role_ids:
            return [
                agent.agent_id
                for agent in team.agents
                if agent.agent_id and agent.role_id in target_role_ids
            ]
        return _unique_strings(
            recommendation.target_agent_ids if recommendation is not None else [],
        )

    def _resolve_install_capabilities(
        self,
        *,
        item: IndustryBootstrapInstallItem,
        recommendation: IndustryCapabilityRecommendation | None,
        client_key: str,
        template: object | None = None,
    ) -> list[str]:
        explicit = _unique_strings(item.capability_ids)
        if explicit:
            return explicit
        if recommendation is not None:
            derived = _unique_strings(recommendation.capability_ids)
            if derived:
                return derived
        if template is not None:
            template_capability_ids = _install_template_capability_ids(template)
            if template_capability_ids:
                return template_capability_ids
        return [f"mcp:{client_key}"]

    def _resolve_hub_skill_capabilities(
        self,
        *,
        item: IndustryBootstrapInstallItem,
        recommendation: IndustryCapabilityRecommendation | None,
        installed_skill_name: str,
    ) -> list[str]:
        explicit = _unique_strings(item.capability_ids)
        if explicit:
            return explicit
        installed_capability = _skill_capability_id(installed_skill_name)
        return _unique_strings(
            recommendation.capability_ids if recommendation is not None else [],
            [installed_capability] if installed_capability else [],
        )

    def _resolve_system_executor(
        self,
        capability_id: str,
    ) -> Callable[..., Awaitable[dict[str, object]]] | None:
        resolver = getattr(self._capability_service, "resolve_executor", None)
        if not callable(resolver):
            return None
        executor = resolver(capability_id)
        if executor is None or not callable(executor):
            return None
        return executor

    async def _dispatch_industry_governed_mutation(
        self,
        *,
        capability_ref: str,
        title: str,
        payload: dict[str, object],
        environment_ref: str,
        fallback_risk: str = "guarded",
        risk_level_override: str | None = None,
    ) -> dict[str, object]:
        capability_service = self._capability_service
        dispatcher = self._get_industry_kernel_dispatcher()
        if capability_service is None:
            raise ValueError("Capability service is not available.")
        if dispatcher is None:
            raise ValueError("Kernel dispatcher is not available.")
        return await dispatch_governed_mutation_runtime(
            capability_service=capability_service,
            kernel_dispatcher=dispatcher,
            capability_ref=capability_ref,
            title=title,
            payload=payload,
            environment_ref=environment_ref,
            fallback_risk=fallback_risk,
            risk_level_override=risk_level_override,
        )

    async def _execute_install_plan(
        self,
        *,
        plan: _IndustryPlan,
        install_plan: list[IndustryBootstrapInstallItem],
        governed_mode: bool = False,
        governed_actor: str = "industry-bootstrap",
        governed_risk_level_override: str | None = None,
    ) -> list[IndustryBootstrapInstallResult]:
        if not install_plan:
            return []
        create_mcp_client = (
            None if governed_mode else self._resolve_system_executor("system:create_mcp_client")
        )
        update_mcp_client = (
            None if governed_mode else self._resolve_system_executor("system:update_mcp_client")
        )
        apply_capability_lifecycle = (
            None
            if governed_mode
            else self._resolve_system_executor("system:apply_capability_lifecycle")
        )
        set_capability_enabled = (
            None if governed_mode else self._resolve_system_executor("system:set_capability_enabled")
        )
        install_hub_skill = (
            None if governed_mode else self._resolve_system_executor("system:install_hub_skill")
        )
        requires_mcp_install = any(
            str(item.install_kind or "mcp-template") in {"mcp-template", "mcp-registry"}
            for item in install_plan
        )
        requires_hub_install = any(
            str(item.install_kind or "mcp-template") == "hub-skill"
            for item in install_plan
        )
        if requires_mcp_install and create_mcp_client is None:
            if not governed_mode:
                raise ValueError("Capability install executor is not available.")
        if requires_hub_install and install_hub_skill is None:
            if not governed_mode:
                raise ValueError("Skill hub install executor is not available.")
        if apply_capability_lifecycle is None:
            if not governed_mode:
                raise ValueError("Capability lifecycle executor is not available.")

        recommendation_by_id = {
            item.recommendation_id: item
            for item in plan.recommendation_pack.items
            if item.recommendation_id
        }
        installed_client_keys = (
            self._list_installed_mcp_client_keys()
            if requires_mcp_install
            else set()
        )
        installed_client_configs = (
            self._list_installed_mcp_client_configs()
            if requires_mcp_install
            else {}
        )
        installed_skills = (
            self._list_installed_skill_specs()
            if requires_hub_install
            else []
        )
        results: list[IndustryBootstrapInstallResult] = []
        environment_ref = f"industry:{plan.draft.team.team_id or plan.profile.slug}"

        async def execute_system_mutation(
            capability_ref: str,
            *,
            title: str,
            payload: dict[str, object],
            fallback_risk: str = "guarded",
        ) -> dict[str, object]:
            mutation_started_at = perf_counter()
            logger.info(
                "Industry install mutation start: capability=%s title=%s",
                capability_ref,
                title,
            )
            governed_owner_agent_id = next(
                (
                    role.agent_id
                    for role in plan.draft.team.agents
                    if is_execution_core_role_id(role.role_id) and _string(role.agent_id)
                ),
                EXECUTION_CORE_AGENT_ID,
            )
            normalized_payload = dict(payload)
            normalized_payload.setdefault("actor", governed_actor)
            normalized_payload.setdefault("owner_agent_id", governed_owner_agent_id)
            if capability_ref == "system:apply_capability_lifecycle":
                normalized_payload["governed_mutation"] = True
            if governed_mode:
                response = await self._dispatch_industry_governed_mutation(
                    capability_ref=capability_ref,
                    title=title,
                    payload=normalized_payload,
                    environment_ref=environment_ref,
                    fallback_risk=fallback_risk,
                    risk_level_override=governed_risk_level_override,
                )
                mutation_output = response.get("output")
                if isinstance(mutation_output, dict):
                    normalized_output = dict(mutation_output)
                    normalized_output.setdefault("success", bool(response.get("success")))
                    normalized_output.setdefault(
                        "summary",
                        _string(response.get("summary")) or _string(mutation_output.get("summary")) or "",
                    )
                    normalized_output.setdefault("task_id", _string(response.get("task_id")))
                    normalized_output.setdefault("trace_id", _string(response.get("trace_id")))
                    normalized_output.setdefault(
                        "decision_request_id",
                        _string(response.get("decision_request_id")),
                    )
                    logger.info(
                        "Industry install mutation finish: capability=%s title=%s elapsed=%.2fs success=%s",
                        capability_ref,
                        title,
                        perf_counter() - mutation_started_at,
                        bool(normalized_output.get("success")),
                    )
                    return normalized_output
                logger.info(
                    "Industry install mutation finish: capability=%s title=%s elapsed=%.2fs success=%s",
                    capability_ref,
                    title,
                    perf_counter() - mutation_started_at,
                    bool(response.get("success")),
                )
                return response
            executor = {
                "system:create_mcp_client": create_mcp_client,
                "system:update_mcp_client": update_mcp_client,
                "system:apply_capability_lifecycle": apply_capability_lifecycle,
                "system:set_capability_enabled": set_capability_enabled,
                "system:install_hub_skill": install_hub_skill,
            }.get(capability_ref)
            if executor is None:
                raise ValueError(f"Capability executor '{capability_ref}' is not available.")
            response = await executor(payload=normalized_payload)
            logger.info(
                "Industry install mutation finish: capability=%s title=%s elapsed=%.2fs success=%s",
                capability_ref,
                title,
                perf_counter() - mutation_started_at,
                bool(response.get("success")) if isinstance(response, dict) else None,
            )
            return response
        for item in install_plan:
            item_started_at = perf_counter()
            recommendation = (
                recommendation_by_id.get(item.recommendation_id)
                if item.recommendation_id
                else None
            )
            install_kind = str(
                item.install_kind
                or (
                    recommendation.install_kind
                    if recommendation is not None
                    else "mcp-template"
                ),
            )
            install_option_key = (
                _string(
                    item.install_option_key
                    or (
                        getattr(recommendation, "install_option_key", "")
                        if recommendation is not None
                        else ""
                    ),
                )
                or ""
            )
            template_spec = None
            if install_kind in {"mcp-template", "builtin-runtime"}:
                template_spec = get_install_template(
                    item.template_id,
                    capability_service=self._capability_service,
                    browser_runtime_service=self._get_browser_runtime_service(),
                    include_runtime=True,
                )
                if template_spec is None:
                    detail = f"Install template '{item.template_id}' not found."
                    if item.required:
                        raise ValueError(detail)
                    results.append(
                        IndustryBootstrapInstallResult(
                            recommendation_id=item.recommendation_id,
                            install_kind=install_kind,
                            template_id=item.template_id,
                            client_key=item.client_key or "",
                            capability_ids=list(item.capability_ids),
                            source_url=_string(item.bundle_url) or "",
                            version=_string(item.version) or "",
                            status="failed",
                            detail=detail,
                            installed=False,
                        ),
                    )
                    continue

            client_key = item.client_key or (
                recommendation.default_client_key if recommendation is not None else None
            )
            if install_kind == "mcp-registry" and not client_key:
                client_key = self._find_installed_registry_client_key(
                    server_name=item.template_id,
                    installed_clients=installed_client_configs,
                )
            if template_spec is not None:
                client_key = client_key or _install_template_default_ref(template_spec)
                capability_ids = self._resolve_install_capabilities(
                    item=item,
                    recommendation=recommendation,
                    client_key=client_key,
                    template=template_spec,
                )
            else:
                capability_ids = _unique_strings(item.capability_ids)

            target_agent_ids = self._resolve_install_targets(
                team=plan.draft.team,
                item=item,
                recommendation=recommendation,
            )
            status = "already-installed"
            detail = ""
            source_kind = str(
                item.source_kind
                or (
                    recommendation.source_kind
                    if recommendation is not None
                    else "mcp-registry" if install_kind == "mcp-registry" else "install-template"
                ),
            )
            source_label = str(
                item.source_label
                or (
                    recommendation.source_label
                    if recommendation is not None
                    else "Official MCP Registry" if install_kind == "mcp-registry" else ""
                )
                or ""
            )
            source_url = _string(item.bundle_url) or (
                _string(recommendation.source_url) if recommendation is not None else ""
            ) or ""
            version = _string(item.version) or (
                _string(recommendation.version) if recommendation is not None else ""
            ) or ""
            logger.info(
                "Industry install item start: install_kind=%s template=%s source=%s",
                install_kind,
                item.template_id,
                source_url,
            )
            if install_kind == "mcp-template":
                template = get_desktop_mcp_template(item.template_id)
                if template is None:
                    detail = f"Install template '{item.template_id}' not found."
                    if item.required:
                        raise ValueError(detail)
                    results.append(
                        IndustryBootstrapInstallResult(
                            recommendation_id=item.recommendation_id,
                            install_kind=install_kind,
                            template_id=item.template_id,
                            client_key=client_key,
                            capability_ids=capability_ids,
                            status="failed",
                            detail=detail,
                            installed=False,
                        ),
                    )
                    continue
                existing_client = installed_client_configs.get(client_key or "")
                status = "already-installed" if client_key in installed_client_keys else "installed"
                detail = f"MCP template '{item.template_id}' is already installed as '{client_key}'."
                if status == "installed":
                    client_payload = dict(template.client)
                    client_payload["enabled"] = item.enabled
                    response = await execute_system_mutation(
                        "system:create_mcp_client",
                        title=f"Install MCP template {item.template_id} as {client_key}",
                        payload={
                            "client_key": client_key,
                            "client": client_payload,
                            "actor": governed_actor,
                        },
                    )
                    if not bool(response.get("success")):
                        detail = str(
                            response.get("error")
                            or response.get("summary")
                            or f"Failed to install MCP template '{item.template_id}'."
                        )
                        if item.required:
                            raise ValueError(detail)
                        results.append(
                            IndustryBootstrapInstallResult(
                                recommendation_id=item.recommendation_id,
                                install_kind=install_kind,
                                template_id=item.template_id,
                                client_key=client_key,
                                capability_ids=capability_ids,
                                status="failed",
                                detail=detail,
                                installed=False,
                                routes={
                                    "market_template": (
                                        f"/api/capability-market/install-templates/{item.template_id}"
                                    ),
                                },
                            ),
                        )
                        continue
                    installed_client_keys.add(client_key)
                    if client_key:
                        installed_client_configs[client_key] = MCPClientConfig.model_validate(
                            client_payload,
                        )
                    detail = str(
                        response.get("summary")
                        or f"Installed MCP template '{item.template_id}' as '{client_key}'."
                    )
                elif (
                    item.enabled
                    and existing_client is not None
                    and not bool(existing_client.enabled)
                ):
                    if set_capability_enabled is None:
                        detail = "Capability enable executor is not available."
                        if item.required:
                            raise ValueError(detail)
                        results.append(
                            IndustryBootstrapInstallResult(
                                recommendation_id=item.recommendation_id,
                                install_kind=install_kind,
                                template_id=item.template_id,
                                client_key=client_key,
                                capability_ids=capability_ids,
                                status="failed",
                                detail=detail,
                                installed=False,
                            ),
                        )
                        continue
                    response = await execute_system_mutation(
                        "system:set_capability_enabled",
                        title=f"Enable MCP client {client_key}",
                        payload={
                            "capability_id": f"mcp:{client_key}",
                            "enabled": True,
                            "actor": governed_actor,
                        },
                    )
                    if not bool(response.get("success")):
                        detail = str(
                            response.get("error")
                            or response.get("summary")
                            or f"Failed to enable MCP client '{client_key}'."
                        )
                        if item.required:
                            raise ValueError(detail)
                        results.append(
                            IndustryBootstrapInstallResult(
                                recommendation_id=item.recommendation_id,
                                install_kind=install_kind,
                                template_id=item.template_id,
                                client_key=client_key,
                                capability_ids=capability_ids,
                                status="failed",
                                detail=detail,
                                installed=False,
                            ),
                        )
                        continue
                    status = "enabled-existing"
                    existing_client.enabled = True
                    detail = str(
                        response.get("summary")
                        or f"Enabled existing MCP client '{client_key}'."
                    )
            elif install_kind == "mcp-registry":
                if not install_option_key:
                    detail = "MCP registry install option is required."
                    if item.required:
                        raise ValueError(detail)
                    results.append(
                        IndustryBootstrapInstallResult(
                            recommendation_id=item.recommendation_id,
                            install_kind=install_kind,
                            template_id=item.template_id,
                            install_option_key=install_option_key,
                            client_key=client_key or "",
                            capability_ids=capability_ids,
                            source_kind=source_kind,
                            source_label=source_label,
                            source_url=source_url,
                            version=version,
                            status="failed",
                            detail=detail,
                            installed=False,
                        ),
                    )
                    continue
                existing_client_key = self._find_installed_registry_client_key(
                    server_name=item.template_id,
                    installed_clients=installed_client_configs,
                )
                if not item.client_key and existing_client_key:
                    client_key = existing_client_key
                existing_client = installed_client_configs.get(client_key or "")
                existing_registry = (
                    getattr(existing_client, "registry", None)
                    if existing_client is not None
                    else None
                )
                if existing_client is not None and (
                    existing_registry is None
                    or _string(getattr(existing_registry, "server_name", None)) != item.template_id
                ):
                    detail = (
                        f"Client key '{client_key}' is already used by a different MCP client."
                    )
                    if item.required:
                        raise ValueError(detail)
                    results.append(
                        IndustryBootstrapInstallResult(
                            recommendation_id=item.recommendation_id,
                            install_kind=install_kind,
                            template_id=item.template_id,
                            install_option_key=install_option_key,
                            client_key=client_key or "",
                            capability_ids=capability_ids,
                            source_kind=source_kind,
                            source_label=source_label,
                            source_url=source_url,
                            version=version,
                            status="failed",
                            detail=detail,
                            installed=False,
                        ),
                    )
                    continue
                catalog = self._get_mcp_registry_catalog()
                try:
                    materialized = catalog.materialize_install_plan(
                        item.template_id,
                        option_key=install_option_key,
                        input_values=(
                            dict(existing_registry.input_values or {})
                            if existing_registry is not None
                            else None
                        ),
                        client_key=client_key,
                        enabled=item.enabled,
                        existing_client=existing_client,
                    )
                except Exception as exc:
                    detail = str(exc).strip() or "Failed to materialize MCP registry install plan."
                    if item.required:
                        raise ValueError(detail)
                    results.append(
                        IndustryBootstrapInstallResult(
                            recommendation_id=item.recommendation_id,
                            install_kind=install_kind,
                            template_id=item.template_id,
                            install_option_key=install_option_key,
                            client_key=client_key or "",
                            capability_ids=capability_ids,
                            source_kind=source_kind,
                            source_label=source_label,
                            source_url=source_url,
                            version=version,
                            status="failed",
                            detail=detail,
                            installed=False,
                        ),
                    )
                    continue
                client_key = materialized.client_key
                capability_ids = [f"mcp:{client_key}"]
                source_label = source_label or "Official MCP Registry"
                version = _string(materialized.registry.version) or version
                if not source_url:
                    source_url = (
                        f"https://registry.modelcontextprotocol.io/v0/servers/"
                        f"{quote(item.template_id, safe='')}/versions/latest"
                    )
                requires_update = bool(
                    existing_registry is not None
                    and (
                        materialized.version_changed
                        or _string(getattr(existing_registry, "option_key", None))
                        != install_option_key
                    )
                )
                if existing_client is None:
                    response = await execute_system_mutation(
                        "system:create_mcp_client",
                        title=f"Install registry MCP {item.template_id} as {client_key}",
                        payload={
                            "client_key": client_key,
                            "client": materialized.client.model_dump(mode="json"),
                            "actor": governed_actor,
                        },
                    )
                    if not bool(response.get("success")):
                        detail = str(
                            response.get("error")
                            or response.get("summary")
                            or f"Failed to install MCP registry server '{item.template_id}'."
                        )
                        if item.required:
                            raise ValueError(detail)
                        results.append(
                            IndustryBootstrapInstallResult(
                                recommendation_id=item.recommendation_id,
                                install_kind=install_kind,
                                template_id=item.template_id,
                                install_option_key=install_option_key,
                                client_key=client_key,
                                capability_ids=capability_ids,
                                source_kind=source_kind,
                                source_label=source_label,
                                source_url=source_url,
                                version=version,
                                status="failed",
                                detail=detail,
                                installed=False,
                            ),
                        )
                        continue
                    installed_client_keys.add(client_key)
                    installed_client_configs[client_key] = materialized.client
                    status = "installed"
                    detail = str(
                        response.get("summary")
                        or materialized.summary
                        or f"Installed registry MCP '{client_key}'."
                    )
                elif requires_update:
                    if update_mcp_client is None:
                        detail = "MCP update executor is not available."
                        if item.required:
                            raise ValueError(detail)
                        results.append(
                            IndustryBootstrapInstallResult(
                                recommendation_id=item.recommendation_id,
                                install_kind=install_kind,
                                template_id=item.template_id,
                                install_option_key=install_option_key,
                                client_key=client_key,
                                capability_ids=capability_ids,
                                source_kind=source_kind,
                                source_label=source_label,
                                source_url=source_url,
                                version=version,
                                status="failed",
                                detail=detail,
                                installed=False,
                            ),
                        )
                        continue
                    response = await execute_system_mutation(
                        "system:update_mcp_client",
                        title=f"Update registry MCP {item.template_id} as {client_key}",
                        payload={
                            "client_key": client_key,
                            "client": materialized.client.model_dump(mode="json"),
                            "actor": governed_actor,
                        },
                    )
                    if not bool(response.get("success")):
                        detail = str(
                            response.get("error")
                            or response.get("summary")
                            or f"Failed to upgrade MCP registry server '{item.template_id}'."
                        )
                        if item.required:
                            raise ValueError(detail)
                        results.append(
                            IndustryBootstrapInstallResult(
                                recommendation_id=item.recommendation_id,
                                install_kind=install_kind,
                                template_id=item.template_id,
                                install_option_key=install_option_key,
                                client_key=client_key,
                                capability_ids=capability_ids,
                                source_kind=source_kind,
                                source_label=source_label,
                                source_url=source_url,
                                version=version,
                                status="failed",
                                detail=detail,
                                installed=False,
                            ),
                        )
                        continue
                    installed_client_configs[client_key] = materialized.client
                    status = "updated-existing"
                    detail = str(
                        response.get("summary")
                        or materialized.summary
                        or f"Upgraded registry MCP '{client_key}'."
                    )
                elif item.enabled and existing_client is not None and not bool(existing_client.enabled):
                    if set_capability_enabled is None:
                        detail = "Capability enable executor is not available."
                        if item.required:
                            raise ValueError(detail)
                        results.append(
                            IndustryBootstrapInstallResult(
                                recommendation_id=item.recommendation_id,
                                install_kind=install_kind,
                                template_id=item.template_id,
                                install_option_key=install_option_key,
                                client_key=client_key,
                                capability_ids=capability_ids,
                                source_kind=source_kind,
                                source_label=source_label,
                                source_url=source_url,
                                version=version,
                                status="failed",
                                detail=detail,
                                installed=False,
                            ),
                        )
                        continue
                    response = await execute_system_mutation(
                        "system:set_capability_enabled",
                        title=f"Enable registry MCP {client_key}",
                        payload={
                            "capability_id": f"mcp:{client_key}",
                            "enabled": True,
                            "actor": governed_actor,
                        },
                    )
                    if not bool(response.get("success")):
                        detail = str(
                            response.get("error")
                            or response.get("summary")
                            or f"Failed to enable MCP client '{client_key}'."
                        )
                        if item.required:
                            raise ValueError(detail)
                        results.append(
                            IndustryBootstrapInstallResult(
                                recommendation_id=item.recommendation_id,
                                install_kind=install_kind,
                                template_id=item.template_id,
                                install_option_key=install_option_key,
                                client_key=client_key,
                                capability_ids=capability_ids,
                                source_kind=source_kind,
                                source_label=source_label,
                                source_url=source_url,
                                version=version,
                                status="failed",
                                detail=detail,
                                installed=False,
                            ),
                        )
                        continue
                    status = "enabled-existing"
                    existing_client.enabled = True
                    detail = str(
                        response.get("summary")
                        or f"Enabled existing MCP client '{client_key}'."
                    )
                else:
                    status = "already-installed"
                    detail = (
                        f"MCP registry server '{item.template_id}' is already installed as '{client_key}'."
                    )
            elif install_kind == "builtin-runtime":
                browser_runtime_service = self._get_browser_runtime_service()
                if item.template_id == "browser-local":
                    if browser_runtime_service is None:
                        detail = "Browser runtime service is not available."
                        if item.required:
                            raise ValueError(detail)
                        results.append(
                            IndustryBootstrapInstallResult(
                                recommendation_id=item.recommendation_id,
                                install_kind=install_kind,
                                template_id=item.template_id,
                                client_key=client_key,
                                capability_ids=capability_ids,
                                status="failed",
                                detail=detail,
                                installed=False,
                            ),
                        )
                        continue
                    if (
                        item.enabled
                        and template_spec.default_capability_id
                        and not bool(template_spec.enabled)
                    ):
                        if set_capability_enabled is None:
                            detail = "Capability enable executor is not available."
                            if item.required:
                                raise ValueError(detail)
                            results.append(
                                IndustryBootstrapInstallResult(
                                    recommendation_id=item.recommendation_id,
                                    install_kind=install_kind,
                                    template_id=item.template_id,
                                    client_key=client_key,
                                    capability_ids=capability_ids,
                                    status="failed",
                                    detail=detail,
                                    installed=False,
                                ),
                            )
                            continue
                        response = await execute_system_mutation(
                            "system:set_capability_enabled",
                            title=f"Enable builtin runtime {template_spec.default_capability_id}",
                            payload={
                                "capability_id": template_spec.default_capability_id,
                                "enabled": True,
                                "actor": governed_actor,
                            },
                        )
                        if not bool(response.get("success")):
                            detail = str(
                                response.get("error")
                                or response.get("summary")
                                or f"Failed to enable capability '{template_spec.default_capability_id}'."
                            )
                            if item.required:
                                raise ValueError(detail)
                            results.append(
                                IndustryBootstrapInstallResult(
                                    recommendation_id=item.recommendation_id,
                                    install_kind=install_kind,
                                    template_id=item.template_id,
                                    client_key=client_key,
                                    capability_ids=capability_ids,
                                    status="failed",
                                    detail=detail,
                                    installed=False,
                                ),
                            )
                            continue
                        status = "enabled-existing"
                    existing_profile = browser_runtime_service.get_profile(client_key)
                    profile = browser_runtime_service.ensure_default_profile(
                        profile_id=client_key,
                        label=f"{plan.draft.team.label} 浏览器运行时",
                        metadata={"source_template_id": item.template_id},
                    )
                    if existing_profile is None:
                        status = "installed" if status == "already-installed" else status
                    detail = (
                        f"Browser runtime profile '{profile.profile_id}' is ready."
                        if status == "already-installed"
                        else f"Prepared browser runtime profile '{profile.profile_id}'."
                    )
                else:
                    detail = f"Unsupported builtin runtime template '{item.template_id}'."
                    if item.required:
                        raise ValueError(detail)
                    results.append(
                        IndustryBootstrapInstallResult(
                            recommendation_id=item.recommendation_id,
                            install_kind=install_kind,
                            template_id=item.template_id,
                            client_key=client_key,
                            capability_ids=capability_ids,
                            status="failed",
                            detail=detail,
                            installed=False,
                        ),
                    )
                    continue
            elif install_kind == "hub-skill":
                requires_review_ack = (
                    recommendation.review_required
                    if recommendation is not None
                    else source_kind == "skillhub-curated"
                )
                if (
                    requires_review_ack
                    and not bool(item.review_acknowledged)
                ):
                    detail = (
                        "该推荐技能在安装前需要操作方确认已阅读审查说明。"
                    )
                    if item.required:
                        raise ValueError(detail)
                    results.append(
                        IndustryBootstrapInstallResult(
                            recommendation_id=item.recommendation_id,
                            install_kind=install_kind,
                            template_id=item.template_id,
                            client_key=client_key or "",
                            capability_ids=capability_ids,
                            source_kind=source_kind,
                            source_label=source_label,
                            source_url=source_url,
                            version=version,
                            status="failed",
                            detail=detail,
                            installed=False,
                        ),
                    )
                    continue
                if not source_url:
                    detail = "远程技能来源地址不能为空。"
                    if item.required:
                        raise ValueError(detail)
                    results.append(
                        IndustryBootstrapInstallResult(
                            recommendation_id=item.recommendation_id,
                            install_kind=install_kind,
                            template_id=item.template_id,
                            client_key=client_key or "",
                            capability_ids=capability_ids,
                            source_kind=source_kind,
                            source_label=source_label,
                            source_url=source_url,
                            version=version,
                            status="failed",
                            detail=detail,
                            installed=False,
                        ),
                    )
                    continue
                existing_skill = self._find_installed_skill_match(
                    result=HubSkillResult(
                        slug=item.template_id,
                        name=recommendation.title if recommendation is not None else item.template_id,
                        description=recommendation.description if recommendation is not None else "",
                        version=version,
                        source_url=source_url,
                    ),
                    installed_skills=installed_skills,
                )
                installed_skill_name = (
                    _string(existing_skill.get("name"))
                    if existing_skill is not None
                    else ""
                ) or ""
                if existing_skill is not None:
                    status = "already-installed"
                    detail = (
                        f"Hub skill '{installed_skill_name}' is already installed."
                    )
                else:
                    response = await execute_system_mutation(
                        "system:install_hub_skill",
                        title=f"Install hub skill {item.template_id or source_url}",
                        payload={
                            "bundle_url": source_url,
                            "version": version,
                            "enable": item.enabled,
                            "overwrite": False,
                            "actor": governed_actor,
                        },
                    )
                    if not bool(response.get("success")):
                        detail = str(
                            response.get("error")
                            or response.get("summary")
                            or f"Failed to install hub skill from '{source_url}'."
                        )
                        if item.required:
                            raise ValueError(detail)
                        results.append(
                            IndustryBootstrapInstallResult(
                                recommendation_id=item.recommendation_id,
                                install_kind=install_kind,
                                template_id=item.template_id,
                                client_key=client_key or "",
                                capability_ids=capability_ids,
                                source_kind=source_kind,
                                source_label=source_label,
                                source_url=source_url,
                                version=version,
                                status="failed",
                                detail=detail,
                                installed=False,
                            ),
                        )
                        continue
                    installed_skill_name = (
                        _string(response.get("name"))
                        or client_key
                        or item.template_id
                    )
                    source_url = _string(response.get("source_url")) or source_url
                    installed_skills.append(
                        {
                            "name": installed_skill_name,
                            "source": source_url,
                        },
                    )
                    status = "installed"
                    detail = str(
                        response.get("summary")
                        or f"Installed hub skill '{installed_skill_name}'."
                    )
                client_key = installed_skill_name or client_key or item.template_id
                capability_ids = self._resolve_hub_skill_capabilities(
                    item=item,
                    recommendation=recommendation,
                    installed_skill_name=client_key,
                )
            else:
                detail = f"Unsupported install kind '{install_kind}'."
                if item.required:
                    raise ValueError(detail)
                results.append(
                    IndustryBootstrapInstallResult(
                        recommendation_id=item.recommendation_id,
                        install_kind=install_kind,
                        template_id=item.template_id,
                        client_key=client_key,
                        capability_ids=capability_ids,
                        source_kind=source_kind,
                        source_label=source_label,
                        source_url=source_url,
                        version=version,
                        status="failed",
                        detail=detail,
                        installed=False,
                    ),
                )
                continue

            assignment_results: list[IndustryBootstrapInstallAssignmentResult] = []
            for agent_id in target_agent_ids:
                lifecycle_payload = self._build_capability_lifecycle_assignment_payload(
                    agent_id=agent_id,
                    capability_ids=capability_ids,
                    capability_assignment_mode=item.capability_assignment_mode,
                    reason=f"Industry bootstrap install plan: {item.template_id}",
                    actor=governed_actor,
                )
                assignment_response = await execute_system_mutation(
                    "system:apply_capability_lifecycle",
                    title=f"Assign installed capabilities to {agent_id}",
                    payload=lifecycle_payload,
                )
                assignment_success = bool(assignment_response.get("success"))
                assignment_detail = str(
                    assignment_response.get("summary")
                    or assignment_response.get("error")
                    or (
                        f"Assigned {', '.join(capability_ids)} to '{agent_id}'."
                        if assignment_success
                        else f"Failed to assign capabilities to '{agent_id}'."
                    )
                )
                if not assignment_success and item.required:
                    raise ValueError(assignment_detail)
                assignment_results.append(
                    IndustryBootstrapInstallAssignmentResult(
                        agent_id=agent_id,
                        capability_ids=capability_ids,
                        status="assigned" if assignment_success else "failed",
                        detail=assignment_detail,
                        routes={
                            "agent": f"/api/runtime-center/agents/{agent_id}",
                        },
                    ),
                )

            results.append(
                IndustryBootstrapInstallResult(
                    recommendation_id=item.recommendation_id,
                    install_kind=install_kind,
                    template_id=item.template_id,
                    install_option_key=install_option_key,
                    client_key=client_key,
                    capability_ids=capability_ids,
                    source_kind=source_kind,
                    source_label=source_label,
                    source_url=source_url,
                    version=version,
                    status=status,
                    detail=detail,
                    installed=True,
                    assignment_results=assignment_results,
                    routes={
                        "market_template": (
                            f"/api/capability-market/install-templates/{item.template_id}"
                            if install_kind in {"mcp-template", "builtin-runtime"}
                            else ""
                        ),
                        "market_catalog": (
                            f"/api/capability-market/mcp/catalog/{quote(item.template_id, safe='')}"
                            if install_kind == "mcp-registry"
                            else ""
                        ),
                        "market_client": (
                            f"/api/capability-market/mcp/{client_key}"
                            if install_kind in {"mcp-template", "mcp-registry"}
                            else ""
                        ),
                        "market_skills": (
                            "/api/capability-market/skills"
                            if install_kind == "hub-skill"
                            else ""
                        ),
                    },
                ),
            )
            logger.info(
                "Industry install item finish: install_kind=%s template=%s elapsed=%.2fs status=%s",
                install_kind,
                item.template_id,
                perf_counter() - item_started_at,
                results[-1].status,
            )
        return results
