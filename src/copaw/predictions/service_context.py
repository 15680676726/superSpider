# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403


class _PredictionServiceContextMixin:
    def _summary(self, record: PredictionCaseRecord) -> PredictionCaseSummary:
        recommendations = [
            self._refresh_recommendation(item)[0]
            for item in self._recommendation_repository.list_recommendations(case_id=record.case_id)
        ]
        reviews = self._review_repository.list_reviews(case_id=record.case_id)
        latest_review = reviews[0] if reviews else None
        pending_decisions = sum(1 for item in recommendations if item.status == "waiting-confirm")
        return PredictionCaseSummary(
            case=record.model_dump(mode="json"),
            scenario_count=len(self._scenario_repository.list_scenarios(case_id=record.case_id)),
            signal_count=len(self._signal_repository.list_signals(case_id=record.case_id)),
            recommendation_count=len(recommendations),
            review_count=len(reviews),
            latest_review_outcome=latest_review.outcome if latest_review is not None else None,
            pending_decision_count=pending_decisions,
            routes={
                "detail": _route_prediction(record.case_id),
                "reviews": f"/api/predictions/{record.case_id}/reviews",
            },
        )

    def _collect_facts(self, case: PredictionCaseRecord) -> _FactPack:
        scope_type = "industry" if case.industry_instance_id else "global"
        scope_id = case.industry_instance_id
        performance = self._performance(scope_type=scope_type, scope_id=scope_id, days=case.time_window_days)
        report = self._report(scope_type=scope_type, scope_id=scope_id, days=case.time_window_days)
        goals = self._goals_for_scope(case=case, report=report)
        agents = self._agents_for_scope(case.industry_instance_id)
        tasks = self._tasks_for_scope(
            case=case,
            goals=goals,
            agents=agents,
        )
        workflows = self._workflows_for_scope(case=case)
        capabilities = self._capabilities()
        strategy = self._resolve_strategy_memory(case)
        return _FactPack(
            scope_type=scope_type,
            scope_id=scope_id,
            report=report,
            performance=performance,
            goals=goals,
            tasks=tasks,
            workflows=workflows,
            agents=agents,
            capabilities=capabilities,
            strategy=strategy,
        )

    def _performance(self, *, scope_type: str, scope_id: str | None, days: int) -> dict[str, Any]:
        getter = getattr(self._reporting_service, "get_performance_overview", None)
        if not callable(getter):
            return {"metrics": [], "agent_breakdown": [], "routes": {}}
        result = getter(window=_window_from_days(days), scope_type=scope_type, scope_id=scope_id)
        if hasattr(result, "model_dump"):
            return result.model_dump(mode="json")
        return _safe_dict(result)

    def _report(self, *, scope_type: str, scope_id: str | None, days: int) -> dict[str, Any]:
        getter = getattr(self._reporting_service, "get_report", None)
        if not callable(getter):
            return {"highlights": [], "goal_ids": [], "routes": {}}
        result = getter(window=_window_from_days(days), scope_type=scope_type, scope_id=scope_id)
        if hasattr(result, "model_dump"):
            return result.model_dump(mode="json")
        return _safe_dict(result)

    def _goals_for_scope(
        self,
        *,
        case: PredictionCaseRecord,
        report: dict[str, Any],
    ) -> list[GoalRecord]:
        if self._goal_repository is None:
            return []
        if case.industry_instance_id and self._industry_instance_repository is not None:
            instance = self._industry_instance_repository.get_instance(case.industry_instance_id)
            if instance is not None:
                return [
                    goal
                    for goal_id in instance.goal_ids
                    if (goal := self._goal_repository.get_goal(goal_id)) is not None
                ]
        report_goal_ids = _safe_list(report.get("goal_ids"))
        if report_goal_ids:
            return [
                goal
                for goal_id in report_goal_ids
                if (goal := self._goal_repository.get_goal(str(goal_id))) is not None
            ]
        return self._goal_repository.list_goals(owner_scope=case.owner_scope)

    def _workflows_for_scope(self, *, case: PredictionCaseRecord) -> list[WorkflowRunRecord]:
        repository = self._workflow_run_repository
        if repository is None:
            return []
        if case.workflow_run_id:
            run = repository.get_run(case.workflow_run_id)
            if run is None:
                return []
            related = repository.list_runs(industry_instance_id=run.industry_instance_id) if run.industry_instance_id else []
            runs = [run]
            runs.extend(item for item in related if item.run_id != run.run_id)
            return runs[:5]
        return repository.list_runs(industry_instance_id=case.industry_instance_id)[:5]

    def _tasks_for_scope(
        self,
        *,
        case: PredictionCaseRecord,
        goals: list[GoalRecord],
        agents: list[Any],
    ) -> list[TaskRecord]:
        repository = self._task_repository
        if repository is None:
            return []
        since = _utc_now() - timedelta(days=max(1, case.time_window_days))
        goal_ids = [goal.id for goal in goals if getattr(goal, "id", None)]
        agent_ids = [
            str(getattr(agent, "agent_id", "") or "")
            for agent in agents
            if str(getattr(agent, "agent_id", "") or "").strip()
        ]
        task_map: dict[str, TaskRecord] = {}
        if goal_ids:
            for task in repository.list_tasks(
                goal_ids=goal_ids,
                activity_since=since,
                limit=200,
            ):
                task_map[task.id] = task
        if agent_ids:
            for task in repository.list_tasks(
                owner_agent_ids=agent_ids,
                activity_since=since,
                limit=200,
            ):
                task_map[task.id] = task
        if case.owner_agent_id:
            for task in repository.list_tasks(
                owner_agent_id=case.owner_agent_id,
                activity_since=since,
                limit=50,
            ):
                task_map[task.id] = task
        tasks = list(task_map.values())
        tasks.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        return tasks

    def _agents_for_scope(self, industry_instance_id: str | None) -> list[Any]:
        getter = getattr(self._agent_profile_service, "list_agents", None)
        if not callable(getter):
            return []
        agents = list(getter(view="all", limit=50))
        if not industry_instance_id:
            return agents
        return [
            agent
            for agent in agents
            if str(getattr(agent, "industry_instance_id", "") or "") == industry_instance_id
        ] or agents

    def _capabilities(self) -> list[Any]:
        getter = getattr(self._capability_service, "list_capabilities", None)
        if not callable(getter):
            return []
        return list(getter())

    def _resolve_strategy_memory(self, case: PredictionCaseRecord) -> dict[str, Any] | None:
        if case.industry_instance_id:
            strategy = self._resolve_strategy_for_scope(
                scope_type="industry",
                scope_id=case.industry_instance_id,
                owner_agent_id=case.owner_agent_id,
            )
            if strategy is not None:
                return strategy
        owner_scope = _string(case.owner_scope)
        if owner_scope:
            strategy = self._resolve_strategy_for_scope(
                scope_type="global",
                scope_id=owner_scope,
                owner_agent_id=case.owner_agent_id,
            )
            if strategy is not None:
                return strategy
        return self._resolve_strategy_for_scope(
            scope_type="global",
            scope_id="global",
            owner_agent_id=case.owner_agent_id,
        )

    def _capability_telemetry(
        self,
        *,
        case: PredictionCaseRecord,
        facts: _FactPack,
    ) -> dict[tuple[str, str], dict[str, Any]]:
        task_ids = [task.id for task in facts.tasks]
        if not task_ids:
            return {}
        since = _utc_now() - timedelta(days=max(1, case.time_window_days))
        runtimes = (
            self._task_runtime_repository.list_runtimes(
                task_ids=task_ids,
                updated_since=since,
            )
            if self._task_runtime_repository is not None
            else []
        )
        runtime_by_task = {runtime.task_id: runtime for runtime in runtimes}
        decisions = (
            self._decision_request_repository.list_decision_requests(
                task_ids=task_ids,
                created_since=since,
                limit=500,
            )
            if self._decision_request_repository is not None
            else []
        )
        decisions_by_task: dict[str, list[Any]] = {}
        for decision in decisions:
            decisions_by_task.setdefault(decision.task_id, []).append(decision)
        evidence = self._evidence_ledger.list_records(
            since=since,
            task_ids=task_ids,
        )
        tasks_by_id = {task.id: task for task in facts.tasks}
        telemetry: dict[tuple[str, str], dict[str, Any]] = {}
        for record in evidence:
            capability_id = _string(getattr(record, "capability_ref", None))
            agent_id = _string(getattr(record, "actor_ref", None))
            task_id = _string(getattr(record, "task_id", None))
            if capability_id is None or agent_id is None or task_id is None:
                continue
            key = (agent_id, capability_id)
            payload = telemetry.setdefault(
                key,
                {
                    "agent_id": agent_id,
                    "capability_id": capability_id,
                    "task_ids": set(),
                    "evidence_ids": set(),
                    "evidence_count": 0,
                },
            )
            payload["task_ids"].add(task_id)
            if getattr(record, "id", None):
                payload["evidence_ids"].add(getattr(record, "id"))
            payload["evidence_count"] = int(payload.get("evidence_count") or 0) + 1

        blocked_statuses = {"failed", "cancelled", "blocked"}
        terminal_statuses = {"completed", "failed", "cancelled"}
        for payload in telemetry.values():
            group_task_ids = set(payload.get("task_ids") or set())
            group_tasks = [
                tasks_by_id[task_id]
                for task_id in group_task_ids
                if task_id in tasks_by_id
            ]
            terminal_tasks = [
                task for task in group_tasks if str(task.status).lower() in terminal_statuses
            ]
            failed_terminal_tasks = [
                task for task in terminal_tasks if str(task.status).lower() in {"failed", "cancelled"}
            ]
            task_decision_count = sum(
                len(decisions_by_task.get(task.id, [])) for task in group_tasks
            )
            task_manual_count = sum(
                1 for task in group_tasks if decisions_by_task.get(task.id)
            )
            related_workflow_ids: set[str] = set()
            blocked_workflow_ids: set[str] = set()
            capability_id = str(payload.get("capability_id") or "")
            agent_id = str(payload.get("agent_id") or "")
            for workflow in facts.workflows:
                preview = _safe_dict(workflow.preview_payload)
                dependency_items = [
                    _safe_dict(item) for item in _safe_list(preview.get("dependencies"))
                ]
                workflow_task_ids = {
                    str(item).strip()
                    for item in list(getattr(workflow, "task_ids", []) or [])
                    if str(item).strip()
                }
                related = bool(group_task_ids & workflow_task_ids)
                missing_ids = {
                    str(item).strip()
                    for item in _safe_list(preview.get("missing_capability_ids"))
                    if str(item).strip()
                }
                gap_ids = {
                    str(item).strip()
                    for item in _safe_list(preview.get("assignment_gap_capability_ids"))
                    if str(item).strip()
                }
                if capability_id in missing_ids or capability_id in gap_ids:
                    related = True
                for dependency in dependency_items:
                    dependency_capability_id = _string(dependency.get("capability_id"))
                    if dependency_capability_id != capability_id:
                        continue
                    target_agent_ids = {
                        str(item).strip()
                        for item in _safe_list(dependency.get("target_agent_ids"))
                        if str(item).strip()
                    }
                    if not target_agent_ids or agent_id in target_agent_ids:
                        related = True
                        break
                if not related:
                    continue
                related_workflow_ids.add(workflow.run_id)
                if (
                    str(workflow.status).lower() in blocked_statuses
                    or capability_id in missing_ids
                    or capability_id in gap_ids
                ):
                    blocked_workflow_ids.add(workflow.run_id)
            durations: list[float] = []
            for task in terminal_tasks:
                runtime = runtime_by_task.get(task.id)
                end_at = runtime.updated_at if runtime is not None else task.updated_at
                durations.append(
                    max(0.0, (end_at - task.created_at).total_seconds()),
                )
            payload.update(
                {
                    "task_count": len(group_tasks),
                    "terminal_task_count": len(terminal_tasks),
                    "failed_task_count": len(failed_terminal_tasks),
                    "failure_rate": round(
                        len(failed_terminal_tasks) / len(terminal_tasks),
                        3,
                    )
                    if terminal_tasks
                    else 0.0,
                    "decision_count": task_decision_count,
                    "manual_intervention_rate": round(
                        task_manual_count / len(group_tasks),
                        3,
                    )
                    if group_tasks
                    else 0.0,
                    "avg_duration_seconds": round(
                        sum(durations) / len(durations),
                        2,
                    )
                    if durations
                    else 0.0,
                    "related_workflow_count": len(related_workflow_ids),
                    "blocked_workflow_count": len(blocked_workflow_ids),
                    "workflow_blockage_rate": round(
                        len(blocked_workflow_ids) / len(related_workflow_ids),
                        3,
                    )
                    if related_workflow_ids
                    else 0.0,
                    "related_workflow_ids": sorted(related_workflow_ids),
                    "blocked_workflow_ids": sorted(blocked_workflow_ids),
                    "related_task_titles": [task.title for task in group_tasks[:4]],
                    "related_task_summaries": [task.summary for task in group_tasks[:4] if task.summary],
                },
            )
        return telemetry

    def _compile_remote_skill_queries(
        self,
        *,
        facts: _FactPack,
        target_agent_id: str | None,
        capability_id: str | None,
        workflow_titles: list[str] | None = None,
        task_titles: list[str] | None = None,
        task_summaries: list[str] | None = None,
    ) -> list[str]:
        discovery_service = self._get_capability_discovery_service()
        if discovery_service is None:
            return []
        build_queries = getattr(discovery_service, "build_prediction_queries", None)
        if not callable(build_queries):
            return []
        profile = self._get_agent_profile(target_agent_id)
        return _string_list(
            build_queries(
                role_name=_string(getattr(profile, "role_name", None)),
                role_summary=_string(getattr(profile, "role_summary", None)),
                mission=_string(getattr(profile, "mission", None)),
                capability_hint=self._capability_hint(capability_id),
                goal_titles=[goal.title for goal in facts.goals[:2]],
                workflow_titles=_string_list(workflow_titles),
                task_titles=_string_list(task_titles),
                task_summaries=_string_list(task_summaries),
            ),
        )

    def _remote_skill_candidates_for_queries(
        self,
        *,
        queries: list[str],
        current_capability_id: str | None = None,
    ) -> list[RemoteSkillCandidate]:
        if (
            not (self._enable_remote_curated_search or self._enable_remote_hub_search)
            or not queries
        ):
            return []
        discovery_service = self._get_capability_discovery_service()
        if discovery_service is None:
            return []
        search_candidates = getattr(
            discovery_service,
            "search_remote_skill_candidates_for_queries",
            None,
        )
        if not callable(search_candidates):
            return []
        return list(
            search_candidates(
                queries=_string_list(queries),
                current_capability_id=current_capability_id,
                include_curated=self._enable_remote_curated_search,
                include_hub=self._enable_remote_hub_search,
            ),
        )

    def _missing_remote_capability_findings(
        self,
        *,
        facts: _FactPack,
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        seen: set[tuple[str, str | None]] = set()
        for workflow in facts.workflows[:5]:
            preview = _safe_dict(workflow.preview_payload)
            missing_ids = {
                str(item).strip()
                for item in _safe_list(preview.get("missing_capability_ids"))
                if str(item).strip()
            }
            for dependency in [_safe_dict(item) for item in _safe_list(preview.get("dependencies"))]:
                capability_id = _string(dependency.get("capability_id"))
                if capability_id is None or capability_id not in missing_ids:
                    continue
                if capability_id.startswith(("mcp:", "tool:", "system:")):
                    continue
                if _safe_list(dependency.get("install_templates")):
                    continue
                target_agent_ids = _string_list(dependency.get("target_agent_ids"))
                target_agent_id = (
                    target_agent_ids[0]
                    if target_agent_ids
                    else self._default_target_agent_id(facts)
                )
                key = (capability_id, target_agent_id)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    {
                        "gap_kind": "missing_capability",
                        "capability_id": capability_id,
                        "target_agent_id": target_agent_id,
                        "workflow_run_id": workflow.run_id,
                        "workflow_title": workflow.title,
                        "task_titles": [],
                        "task_summaries": [],
                    },
                )
        return findings

    def _underperforming_remote_skill_findings(
        self,
        *,
        facts: _FactPack,
        telemetry: dict[tuple[str, str], dict[str, Any]],
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for payload in telemetry.values():
            capability_id = str(payload.get("capability_id") or "")
            if not capability_id.startswith("skill:"):
                continue
            failure_rate = float(payload.get("failure_rate") or 0.0)
            manual_rate = float(payload.get("manual_intervention_rate") or 0.0)
            blockage_rate = float(payload.get("workflow_blockage_rate") or 0.0)
            if (
                failure_rate < 0.34
                and manual_rate < 0.3
                and blockage_rate < 0.25
            ):
                continue
            findings.append(
                {
                    "gap_kind": "underperforming_capability",
                    "capability_id": capability_id,
                    "target_agent_id": str(payload.get("agent_id") or ""),
                    "workflow_run_ids": list(payload.get("related_workflow_ids") or []),
                    "workflow_titles": [
                        workflow.title
                        for workflow in facts.workflows
                        if workflow.run_id in set(payload.get("related_workflow_ids") or [])
                    ],
                    "task_titles": list(payload.get("related_task_titles") or []),
                    "task_summaries": list(payload.get("related_task_summaries") or []),
                    "stats": dict(payload),
                },
            )
        findings.sort(
            key=lambda item: (
                -float(_safe_dict(item.get("stats")).get("failure_rate") or 0.0),
                -float(_safe_dict(item.get("stats")).get("manual_intervention_rate") or 0.0),
                str(item.get("capability_id") or ""),
            ),
        )
        return findings[:3]

    def _trial_followup_findings(
        self,
        *,
        case: PredictionCaseRecord,
        facts: _FactPack,
        telemetry: dict[tuple[str, str], dict[str, Any]],
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        since = _utc_now() - timedelta(days=max(1, case.time_window_days))
        recent = self._recommendation_repository.list_recommendations(
            limit=100,
            activity_since=since,
        )
        seen_rollouts: set[tuple[str, str, str]] = set()
        for record in recent:
            if record.status != "executed":
                continue
            metadata = _safe_dict(record.metadata)
            if str(metadata.get("optimization_stage") or "") != "trial":
                continue
            if case.industry_instance_id and metadata.get("industry_instance_id") not in {
                case.industry_instance_id,
                None,
                "",
            }:
                continue
            preflight = _safe_dict(metadata.get("preflight"))
            trial_plan = _safe_dict(preflight.get("trial_plan"))
            old_capability_id = _string(metadata.get("replacement_capability_id"))
            if old_capability_id is None:
                replacement_ids = _string_list(
                    metadata.get("replacement_target_ids"),
                    metadata.get("replacement_capability_ids"),
                )
                old_capability_id = replacement_ids[0] if replacement_ids else None
            target_agent_id = record.target_agent_id or _string(metadata.get("target_agent_id"))
            if old_capability_id is None or target_agent_id is None:
                continue
            execution_output = _safe_dict(metadata.get("last_execution_output"))
            installed_capability_ids = _string_list(
                metadata.get("installed_capability_ids"),
                execution_output.get("installed_capability_ids"),
                metadata.get("requested_capability_ids"),
                record.action_payload.get("capability_ids") if isinstance(record.action_payload, dict) else None,
            )
            if not installed_capability_ids:
                resolved_candidate = _safe_dict(metadata.get("resolved_candidate"))
                install_name = _string(resolved_candidate.get("install_name"))
                if install_name:
                    installed_capability_ids = [_skill_capability_id(install_name)]
            if not installed_capability_ids:
                continue
            new_capability_id = installed_capability_ids[0]
            new_stats = telemetry.get((target_agent_id, new_capability_id), {})
            old_stats = telemetry.get((target_agent_id, old_capability_id), {})
            selected_seat_ref = (
                _string(metadata.get("selected_seat_ref"))
                or _string(trial_plan.get("target_seat_ref"))
            )
            trial_scope = (
                _string(metadata.get("trial_scope"))
                or _string(trial_plan.get("rollout_scope"))
                or "single-agent"
            )
            if not self._trial_improved(new_stats=new_stats, old_stats=old_stats):
                if self._trial_underperformed(new_stats=new_stats, old_stats=old_stats):
                    findings.append(
                        {
                            "gap_kind": "capability_rollback",
                            "optimization_stage": "rollback",
                            "lifecycle_stage": "blocked",
                            "candidate_lifecycle_stage": "deprecated",
                            "replacement_target_stage": "active",
                            "old_capability_id": old_capability_id,
                            "new_capability_id": new_capability_id,
                            "target_agent_id": target_agent_id,
                            "source_recommendation_id": record.recommendation_id,
                            "selected_seat_ref": selected_seat_ref,
                            "trial_scope": trial_scope,
                            "rollback_target_ids": [old_capability_id],
                            "stats": {
                                "new_stats": new_stats,
                                "old_stats": old_stats,
                            },
                        },
                    )
                continue
            rollout_agent_ids = [
                agent_id
                for agent_id in self._agents_using_capability(facts, old_capability_id)
                if agent_id != target_agent_id
            ]
            if not rollout_agent_ids:
                target_role_id = (
                    _string(metadata.get("target_role_id"))
                    or _string(trial_plan.get("target_role_id"))
                )
                team_blueprint = self._instance_team_blueprint(case.industry_instance_id)
                if team_blueprint is not None and target_role_id is not None:
                    rollout_agent_ids = [
                        agent.agent_id
                        for agent in team_blueprint.agents
                        if (
                            agent.agent_id != target_agent_id
                            and _string(getattr(agent, "role_id", None)) == target_role_id
                        )
                    ]
            if rollout_agent_ids:
                for rollout_agent_id in rollout_agent_ids[:2]:
                    dedupe_key = (rollout_agent_id, old_capability_id, new_capability_id)
                    if dedupe_key in seen_rollouts:
                        continue
                    seen_rollouts.add(dedupe_key)
                    findings.append(
                        {
                            "gap_kind": "capability_rollout",
                            "optimization_stage": "rollout",
                            "lifecycle_stage": "rollout",
                            "candidate_lifecycle_stage": "active",
                            "replacement_target_stage": "deprecated",
                            "old_capability_id": old_capability_id,
                            "new_capability_id": new_capability_id,
                            "target_agent_id": rollout_agent_id,
                            "source_recommendation_id": record.recommendation_id,
                            "selected_seat_ref": selected_seat_ref,
                            "trial_scope": trial_scope,
                            "replacement_target_ids": [old_capability_id],
                            "stats": {
                                "trial_agent_id": target_agent_id,
                                "new_stats": new_stats,
                                "old_stats": old_stats,
                            },
                        },
                    )
                continue
            if self._capability_exists(old_capability_id):
                findings.append(
                    {
                        "gap_kind": "capability_retirement",
                        "optimization_stage": "retire",
                        "lifecycle_stage": "retired",
                        "candidate_lifecycle_stage": "active",
                        "replacement_target_stage": "retired",
                        "old_capability_id": old_capability_id,
                        "new_capability_id": new_capability_id,
                        "target_agent_id": target_agent_id,
                        "source_recommendation_id": record.recommendation_id,
                        "selected_seat_ref": selected_seat_ref,
                        "trial_scope": trial_scope,
                        "replacement_target_ids": [old_capability_id],
                        "stats": {
                            "new_stats": new_stats,
                            "old_stats": old_stats,
                        },
                    },
                )
        return findings

    def _trial_improved(
        self,
        *,
        new_stats: dict[str, Any],
        old_stats: dict[str, Any],
    ) -> bool:
        if not new_stats:
            return False
        new_sample = max(
            int(new_stats.get("task_count") or 0),
            int(new_stats.get("evidence_count") or 0),
        )
        if new_sample <= 0:
            return False
        if not old_stats:
            return (
                float(new_stats.get("failure_rate") or 0.0) <= 0.2
                and float(new_stats.get("manual_intervention_rate") or 0.0) <= 0.2
            )
        new_failure = float(new_stats.get("failure_rate") or 0.0)
        old_failure = float(old_stats.get("failure_rate") or 0.0)
        new_manual = float(new_stats.get("manual_intervention_rate") or 0.0)
        old_manual = float(old_stats.get("manual_intervention_rate") or 0.0)
        new_blockage = float(new_stats.get("workflow_blockage_rate") or 0.0)
        old_blockage = float(old_stats.get("workflow_blockage_rate") or 0.0)
        return (
            new_failure <= old_failure
            and new_manual <= old_manual
            and new_blockage <= old_blockage
            and (
                old_failure - new_failure >= 0.1
                or old_manual - new_manual >= 0.1
                or old_blockage - new_blockage >= 0.1
            )
        )

    def _trial_underperformed(
        self,
        *,
        new_stats: dict[str, Any],
        old_stats: dict[str, Any],
    ) -> bool:
        if not new_stats:
            return False
        if not old_stats:
            return (
                float(new_stats.get("failure_rate") or 0.0) >= 0.34
                or float(new_stats.get("manual_intervention_rate") or 0.0) >= 0.3
                or float(new_stats.get("workflow_blockage_rate") or 0.0) >= 0.25
            )
        return (
            float(new_stats.get("failure_rate") or 0.0)
            > float(old_stats.get("failure_rate") or 0.0)
            or float(new_stats.get("manual_intervention_rate") or 0.0)
            > float(old_stats.get("manual_intervention_rate") or 0.0)
            or float(new_stats.get("workflow_blockage_rate") or 0.0)
            > float(old_stats.get("workflow_blockage_rate") or 0.0)
        )

    def _agents_using_capability(self, facts: _FactPack, capability_id: str) -> list[str]:
        users: list[str] = []
        candidate_agents = list(facts.agents)
        list_agents = getattr(self._agent_profile_service, "list_agents", None)
        if callable(list_agents):
            try:
                candidate_agents.extend(list_agents() or [])
            except Exception:
                pass
        override_repository = getattr(self._agent_profile_service, "_override_repository", None)
        if override_repository is not None:
            list_overrides = getattr(override_repository, "list_overrides", None)
            if callable(list_overrides):
                try:
                    candidate_agents.extend(list_overrides() or [])
                except Exception:
                    pass
        for agent in candidate_agents:
            agent_payload = _safe_dict(agent)
            agent_id = (
                _string(getattr(agent, "agent_id", None))
                or _string(agent_payload.get("agent_id"))
            )
            if agent_id is None:
                continue
            effective_capabilities = self._effective_capabilities_for_agent(agent_id)
            if capability_id in effective_capabilities and agent_id not in users:
                users.append(agent_id)
        return users

    def _effective_capabilities_for_agent(self, agent_id: str) -> list[str]:
        detail_getter = getattr(self._agent_profile_service, "get_agent_detail", None)
        if callable(detail_getter):
            try:
                detail = detail_getter(agent_id)
            except Exception:
                detail = None
            detail_payload = _safe_dict(detail)
            runtime_payload = _safe_dict(detail_payload.get("runtime"))
            metadata_payload = _safe_dict(runtime_payload.get("metadata"))
            capability_layers = _safe_dict(metadata_payload.get("capability_layers"))
            layered_capabilities: list[str] = []
            for capability_id in (
                _string_list(capability_layers.get("role_prototype_capability_ids"))
                + _string_list(capability_layers.get("seat_instance_capability_ids"))
                + _string_list(capability_layers.get("cycle_delta_capability_ids"))
                + _string_list(capability_layers.get("session_overlay_capability_ids"))
            ):
                if capability_id not in layered_capabilities:
                    layered_capabilities.append(capability_id)
            if layered_capabilities:
                return layered_capabilities
        getter = getattr(self._agent_profile_service, "get_capability_surface", None)
        if callable(getter):
            surface = getter(agent_id)
            if isinstance(surface, dict):
                resolved = _string_list(surface.get("effective_capabilities"))
                if resolved:
                    return resolved
        profile = self._get_agent_profile(agent_id)
        if profile is None:
            return []
        return _string_list(getattr(profile, "capabilities", None))

    def _get_agent_profile(self, agent_id: str | None) -> object | None:
        if agent_id is None:
            return None
        getter = getattr(self._agent_profile_service, "get_agent", None)
        if not callable(getter):
            return None
        return getter(agent_id)

    def _get_capability_discovery_service(self) -> object | None:
        service = self._capability_service
        if service is None:
            return None
        getter = getattr(service, "get_discovery_service", None)
        if not callable(getter):
            return None
        try:
            return getter()
        except Exception:
            return None

    def _default_target_agent_id(self, facts: _FactPack) -> str | None:
        for agent in facts.agents:
            agent_id = _string(getattr(agent, "agent_id", None))
            if agent_id and agent_id != EXECUTION_CORE_AGENT_ID:
                return agent_id
        hottest = self._hottest_agent(facts)
        return _string(hottest.get("agent_id")) if hottest else None

    def _team_gap_finding_key(
        self,
        workflow_run_id: str,
        step_payload: dict[str, Any],
    ) -> tuple[str, str]:
        step_key = _string(step_payload.get("step_id")) or _string(
            step_payload.get("title"),
        ) or workflow_run_id
        return workflow_run_id, step_key

    def _slugify_identifier(self, value: object | None, *, fallback: str) -> str:
        text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
        return text or fallback

    def _instance_team_blueprint(
        self,
        industry_instance_id: str | None,
    ) -> IndustryTeamBlueprint | None:
        if industry_instance_id is None or self._industry_instance_repository is None:
            return None
        record = self._industry_instance_repository.get_instance(industry_instance_id)
        if record is None:
            return None
        try:
            return IndustryTeamBlueprint.model_validate(
                record.team_payload or {"team_id": industry_instance_id, "agents": []},
            )
        except Exception:
            return IndustryTeamBlueprint(
                team_id=industry_instance_id,
                label=str(getattr(record, "label", "") or industry_instance_id),
                summary=str(getattr(record, "summary", "") or ""),
                agents=[],
            )

    def _instance_profile(
        self,
        industry_instance_id: str | None,
    ) -> IndustryProfile | None:
        if industry_instance_id is None or self._industry_instance_repository is None:
            return None
        record = self._industry_instance_repository.get_instance(industry_instance_id)
        if record is None:
            return None
        try:
            return IndustryProfile.model_validate(
                record.profile_payload or {"industry": record.label},
            )
        except Exception:
            return None

    def _family_score(self, family_id: str, values: list[str]) -> int:
        blob = " ".join(
            value.lower()
            for value in values
            if isinstance(value, str) and value.strip()
        )
        if not blob:
            return 0
        tokens = dict(_TEAM_GAP_FAMILY_RULES).get(family_id, ())
        return sum(2 if token.lower() in blob else 0 for token in tokens)

    def _infer_team_gap_family(self, values: list[str]) -> str | None:
        scores = {
            family_id: self._family_score(family_id, values)
            for family_id, _tokens in _TEAM_GAP_FAMILY_RULES
        }
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        if not ranked or ranked[0][1] <= 0:
            return None
        return ranked[0][0]

    def _team_covers_family(
        self,
        team: IndustryTeamBlueprint,
        family_id: str,
    ) -> bool:
        for role in team.agents:
            explicit = {
                str(item).strip().lower()
                for item in list(role.preferred_capability_families or [])
                if str(item).strip()
            }
            if family_id in explicit:
                return True
            values = [
                role.role_id,
                role.role_name,
                role.name,
                role.role_summary,
                role.mission,
                role.goal_kind,
                *list(role.allowed_capabilities or []),
            ]
            if self._infer_team_gap_family([item for item in values if isinstance(item, str)]) == family_id:
                return True
        return False

    def _build_team_gap_role(
        self,
        *,
        family_id: str,
        industry_instance_id: str,
        profile: IndustryProfile | None,
    ) -> IndustryRoleBlueprint | None:
        template = _TEAM_GAP_ROLE_TEMPLATES.get(family_id)
        if template is None:
            return None
        role_id = str(template["role_id"])
        instance_slug = self._slugify_identifier(
            industry_instance_id,
            fallback="industry",
        )
        label = (
            profile.primary_label()
            if profile is not None
            else industry_instance_id
        )
        return IndustryRoleBlueprint(
            role_id=role_id,
            agent_id=f"industry-{role_id}-{instance_slug}",
            name=f"{label} {template['role_name']}",
            role_name=str(template["role_name"]),
            role_summary=str(template["role_summary"]),
            mission=str(template["mission"]),
            goal_kind=str(template["goal_kind"]),
            agent_class=str(template["agent_class"]),  # type: ignore[arg-type]
            employment_mode="career",
            activation_mode="persistent",
            suspendable=False,
            reports_to=EXECUTION_CORE_AGENT_ID,
            risk_level="guarded",
            environment_constraints=[],
            allowed_capabilities=[],
            preferred_capability_families=list(
                template.get("preferred_capability_families") or [],
            ),
            evidence_expectations=list(template.get("evidence_expectations") or []),
        )

    def _build_team_gap_goal(
        self,
        *,
        role: IndustryRoleBlueprint,
        profile: IndustryProfile | None,
        workflow_title: str,
    ) -> IndustryDraftGoal:
        label = (
            profile.primary_label()
            if profile is not None
            else workflow_title
        )
        return IndustryDraftGoal(
            goal_id=role.goal_kind or role.role_id,
            kind=role.goal_kind or role.role_id,
            owner_agent_id=role.agent_id,
            title=f"推进 {label} 的{role.role_name}闭环",
            summary=f"补齐“{workflow_title}”暴露出来的{role.role_name}执行缺口。",
            plan_steps=[
                f"梳理“{workflow_title}”涉及的{role.role_name}职责范围与交付标准。",
                f"完成首轮“{role.role_name}”动作，并沉淀可复核证据。",
                "把结果、风险与下一步建议同步回执行中枢。",
            ],
        )

    def _team_role_gap_findings(
        self,
        *,
        case: PredictionCaseRecord,
        facts: _FactPack,
    ) -> dict[tuple[str, str], dict[str, Any]]:
        team = self._instance_team_blueprint(case.industry_instance_id)
        if team is None:
            return {}
        profile = self._instance_profile(case.industry_instance_id)
        covered_families = {
            family_id
            for family_id, _tokens in _TEAM_GAP_FAMILY_RULES
            if self._team_covers_family(team, family_id)
        }
        findings: dict[tuple[str, str], dict[str, Any]] = {}
        for workflow in facts.workflows[:4]:
            preview = _safe_dict(workflow.preview_payload)
            for step in [_safe_dict(item) for item in _safe_list(preview.get("steps"))]:
                execution_mode = str(step.get("execution_mode") or "").strip().lower()
                owner_role_id = str(step.get("owner_role_id") or "").strip().lower()
                owner_agent_id = _string(step.get("owner_agent_id"))
                if execution_mode != "leaf":
                    continue
                if owner_agent_id != EXECUTION_CORE_AGENT_ID and owner_role_id != "execution-core":
                    continue
                values = _string_list(
                    case.title,
                    case.question,
                    case.summary,
                    workflow.title,
                    workflow.summary,
                    step.get("step_id"),
                    step.get("title"),
                    step.get("summary"),
                    step.get("description"),
                    [goal.title for goal in facts.goals[:3]],
                    [goal.summary for goal in facts.goals[:3]],
                )
                family_id = self._infer_team_gap_family(values)
                if family_id is None or family_id in covered_families:
                    continue
                role = self._build_team_gap_role(
                    family_id=family_id,
                    industry_instance_id=case.industry_instance_id or "industry",
                    profile=profile,
                )
                if role is None:
                    continue
                finding_key = self._team_gap_finding_key(workflow.run_id, step)
                findings[finding_key] = {
                    "family_id": family_id,
                    "role": role,
                    "goal": self._build_team_gap_goal(
                        role=role,
                        profile=profile,
                        workflow_title=workflow.title,
                    ),
                    "workflow_run_id": workflow.run_id,
                    "workflow_title": workflow.title,
                    "step_id": _string(step.get("step_id")),
                    "signals": values[:6],
                }
                covered_families.add(family_id)
                if len(findings) >= 2:
                    return findings
        return findings

    def _capability_exists(self, capability_id: str | None) -> bool:
        if capability_id is None:
            return False
        getter = getattr(self._capability_service, "get_capability", None)
        return callable(getter) and getter(capability_id) is not None

    def _capability_hint(self, capability_id: str | None) -> str:
        if capability_id is None:
            return ""
        getter = getattr(self._capability_service, "get_capability", None)
        mount = getter(capability_id) if callable(getter) else None
        name = _string(getattr(mount, "name", None))
        if name:
            return name
        for prefix in ("skill:", "mcp:", "tool:", "system:"):
            if capability_id.startswith(prefix):
                return capability_id[len(prefix) :].replace("_", " ")
        return capability_id.replace("_", " ")

    def _compose_query(self, *parts: object) -> str:
        values = [
            str(part).strip()
            for part in parts
            if isinstance(part, str) and str(part).strip()
        ]
        if not values:
            return ""
        query = " ".join(values)
        return query[:180].strip()

    def _json_safe(self, value: object) -> object:
        if isinstance(value, dict):
            return {
                str(key): self._json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        if isinstance(value, set):
            return [self._json_safe(item) for item in sorted(value)]
        return value

    def _resolve_strategy_for_scope(
        self,
        *,
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None,
    ) -> dict[str, Any] | None:
        return resolve_strategy_payload(
            service=self._strategy_memory_service,
            scope_type=scope_type,
            scope_id=_string(scope_id),
            owner_agent_id=_string(owner_agent_id),
            fallback_owner_agent_ids=[EXECUTION_CORE_AGENT_ID, None],
        )
