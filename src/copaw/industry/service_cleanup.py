# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_context import *  # noqa: F401,F403
from .service_recommendation_search import *  # noqa: F401,F403
from .service_recommendation_pack import *  # noqa: F401,F403


class _IndustryCleanupMixin:
    def _evidence_summary(self, evidence: dict[str, Any] | None) -> str | None:
        if not isinstance(evidence, dict):
            return None
        return _string(evidence.get("result_summary")) or _string(evidence.get("action_summary"))

    def _matches_execution_marker(
        self,
        value: str | None,
        markers: tuple[str, ...],
    ) -> bool:
        text = (value or "").strip().casefold()
        if not text:
            return False
        return any(marker.casefold() in text for marker in markers)

    def _materialize_team_blueprint(
        self,
        record: IndustryInstanceRecord,
    ) -> IndustryTeamBlueprint:
        payload = dict(record.team_payload or {})
        if not payload:
            payload = {
                "team_id": record.instance_id,
                "label": record.label,
                "summary": record.summary,
                "agents": [],
            }
        try:
            team = IndustryTeamBlueprint.model_validate(payload)
        except Exception:
            team = IndustryTeamBlueprint(
                team_id=record.instance_id,
                label=record.label,
                summary=record.summary,
                agents=[],
            )
        agents = list(team.agents)
        existing_role_ids = {
            agent.role_id
            for agent in agents
            if isinstance(agent.role_id, str) and agent.role_id.strip()
        }
        for agent_id in record.agent_ids or []:
            snapshot = self._get_agent_snapshot(agent_id)
            if snapshot is None:
                continue
            role = self._build_role_blueprint_from_agent_snapshot(
                snapshot,
                fallback_agent_id=agent_id,
            )
            if role is None or role.role_id in existing_role_ids:
                continue
            existing_role_ids.add(role.role_id)
            agents.append(role)
        agents = [_normalize_role_blueprint(agent) for agent in agents]
        return IndustryTeamBlueprint(
            team_id=_string(team.team_id) or record.instance_id,
            label=_string(team.label) or record.label,
            summary=_string(team.summary) or record.summary,
            agents=agents,
        )

    def _build_role_blueprint_from_agent_snapshot(
        self,
        snapshot: dict[str, Any],
        *,
        fallback_agent_id: str,
    ) -> IndustryRoleBlueprint | None:
        agent_id = _string(snapshot.get("agent_id")) or fallback_agent_id
        role_id = normalize_industry_role_id(
            _string(snapshot.get("industry_role_id")) or _string(
                snapshot.get("role_id"),
            ),
        ) or (
            EXECUTION_CORE_ROLE_ID
            if is_execution_core_agent_id(agent_id)
            else None
        )
        if agent_id is None or role_id is None:
            return None
        agent_class = _string(snapshot.get("agent_class"))
        if agent_class not in {"system", "business"}:
            agent_class = (
                "business"
                if is_execution_core_role_id(role_id)
                else "system"
                if role_id == "researcher"
                else "business"
            )
        employment_mode = _string(snapshot.get("employment_mode"))
        if employment_mode not in {"career", "temporary"}:
            employment_mode = "career"
        activation_mode = _string(snapshot.get("activation_mode"))
        if activation_mode not in {"persistent", "on-demand"}:
            activation_mode = "persistent"
        risk_level = _string(snapshot.get("risk_level"))
        if risk_level not in {"auto", "guarded", "confirm"}:
            risk_level = "guarded"
        role_name = _string(snapshot.get("role_name")) or role_id.replace("-", " ").title()
        return _normalize_role_blueprint(
            IndustryRoleBlueprint(
            role_id=role_id,
            agent_id=agent_id,
            actor_key=_string(snapshot.get("actor_key")),
            actor_fingerprint=_string(snapshot.get("actor_fingerprint")),
            name=_string(snapshot.get("name")) or agent_id,
            role_name=role_name,
            role_summary=(
                _string(snapshot.get("role_summary"))
                or _string(snapshot.get("environment_summary"))
                or ""
            ),
            mission=_string(snapshot.get("mission")) or "",
            goal_kind=normalize_industry_role_id(
                _string(snapshot.get("goal_kind")) or role_id,
            )
            or role_id,
            agent_class=agent_class,
            employment_mode=employment_mode,
            activation_mode=activation_mode,
            suspendable=bool(snapshot.get("suspendable")),
            reports_to=_string(snapshot.get("reports_to")),
            risk_level=risk_level,
            environment_constraints=_unique_strings(
                snapshot.get("environment_constraints"),
                snapshot.get("environment_summary"),
            ),
            allowed_capabilities=_unique_strings(snapshot.get("capabilities")),
            preferred_capability_families=_unique_strings(
                snapshot.get("preferred_capability_families")
            ),
            evidence_expectations=_unique_strings(
                snapshot.get("evidence_expectations")
            ),
            ),
        )

    def _get_agent_snapshot(self, agent_id: str) -> dict[str, Any] | None:
        snapshot: dict[str, Any] | None = None
        getter = getattr(self._agent_profile_service, "get_agent", None)
        profile = getter(agent_id) if callable(getter) else None
        if profile is not None:
            snapshot = profile.model_dump(mode="json")
        else:
            override = self._agent_profile_override_repository.get_override(agent_id)
            if override is not None:
                snapshot = override.model_dump(mode="json")
        if snapshot is None:
            return None
        if self._agent_runtime_repository is not None:
            runtime = self._agent_runtime_repository.get_runtime(agent_id)
            if runtime is not None:
                snapshot.update(
                    {
                        "actor_key": runtime.actor_key,
                        "actor_fingerprint": runtime.actor_fingerprint,
                        "runtime_status": runtime.runtime_status,
                        "desired_state": runtime.desired_state,
                        "queue_depth": runtime.queue_depth,
                        "current_mailbox_id": runtime.current_mailbox_id,
                        "current_environment_id": runtime.current_environment_id,
                        "last_checkpoint_id": runtime.last_checkpoint_id,
                    },
                )
        if self._agent_thread_binding_repository is not None:
            bindings = self._agent_thread_binding_repository.list_bindings(
                agent_id=agent_id,
                active_only=False,
            )
            snapshot["thread_bindings"] = [
                binding.model_dump(mode="json")
                for binding in bindings
            ]
        return snapshot

    def _goal_compiler_context(
        self,
        override: GoalOverrideRecord | None,
    ) -> dict[str, Any]:
        if override is None or not isinstance(override.compiler_context, dict):
            return {}
        return dict(override.compiler_context)

    def _resolve_goal_lane_record(
        self,
        goal: GoalRecord,
        *,
        override: GoalOverrideRecord | None = None,
    ) -> OperatingLaneRecord | None:
        lane_id = _string(goal.lane_id)
        if lane_id is None:
            lane_id = _string(self._goal_compiler_context(override).get("lane_id"))
        if lane_id is None or self._operating_lane_service is None:
            return None
        return self._operating_lane_service.get_lane(lane_id)

    def _resolve_goal_runtime_context(
        self,
        goal: GoalRecord,
        *,
        override: GoalOverrideRecord | None = None,
        record: IndustryInstanceRecord | None = None,
        team: IndustryTeamBlueprint | None = None,
    ) -> dict[str, Any]:
        compiler_context = self._goal_compiler_context(override)
        industry_instance_id = _string(goal.industry_instance_id) or _string(
            compiler_context.get("industry_instance_id"),
        )
        resolved_record = record
        if (
            resolved_record is None
            and industry_instance_id is not None
            and self._industry_instance_repository is not None
        ):
            resolved_record = self._industry_instance_repository.get_instance(
                industry_instance_id,
            )
        resolved_team = (
            team
            if team is not None
            else self._materialize_team_blueprint(resolved_record)
            if resolved_record is not None
            else None
        )
        lane = self._resolve_goal_lane_record(goal, override=override)
        lane_id = _string(goal.lane_id) or (lane.id if lane is not None else None)
        owner_agent_id = _string(lane.owner_agent_id) if lane is not None else None
        if owner_agent_id is None:
            owner_agent_id = _string(compiler_context.get("owner_agent_id"))
        role_id = _string(lane.owner_role_id) if lane is not None else None
        if role_id is None:
            role_id = _string(compiler_context.get("industry_role_id"))
        goal_kind = _string(lane.lane_key) if lane is not None else None
        if goal_kind is None:
            goal_kind = _string(compiler_context.get("goal_kind"))
        role = None
        if resolved_team is not None:
            role = self._resolve_role_blueprint_by_agent(
                resolved_team,
                owner_agent_id,
            ) or self._resolve_role_blueprint(
                resolved_team,
                role_id,
            )
        industry_label = (
            _string(resolved_record.label) if resolved_record is not None else None
        ) or _string(compiler_context.get("industry_label"))
        industry_summary = (
            _string(resolved_record.summary) if resolved_record is not None else None
        ) or _string(compiler_context.get("industry_summary"))
        role_name = (
            role.role_name
            if role is not None
            else _string(compiler_context.get("industry_role_name"))
            or _string(compiler_context.get("role_name"))
        )
        environment_constraints = _unique_strings(
            list(role.environment_constraints) if role is not None else [],
            compiler_context.get("environment_constraints"),
        )
        evidence_expectations = _unique_strings(
            list(role.evidence_expectations) if role is not None else [],
            compiler_context.get("evidence_expectations"),
        )
        task_mode = _string(compiler_context.get("task_mode")) or infer_industry_task_mode(
            role_id=role.role_id if role is not None else role_id,
            goal_kind=goal_kind,
            source="goal",
        )
        kickoff_stage = _string(compiler_context.get("kickoff_stage"))
        if kickoff_stage not in {"learning", "execution"}:
            kickoff_stage = (
                "learning"
                if normalize_industry_role_id(
                    role.role_id if role is not None else role_id
                ) == "researcher"
                else "execution"
            )
        session_kind = _string(compiler_context.get("session_kind")) or (
            "industry-agent-chat"
            if industry_instance_id is not None and owner_agent_id is not None
            else None
        )
        resolved: dict[str, Any] = {}
        scalar_fields = {
            "owner_scope": _string(goal.owner_scope)
            or _string(compiler_context.get("owner_scope")),
            "industry_instance_id": industry_instance_id,
            "industry_label": industry_label,
            "industry_summary": industry_summary,
            "lane_id": lane_id,
            "cycle_id": _string(goal.cycle_id) or _string(compiler_context.get("cycle_id")),
            "assignment_id": _string(compiler_context.get("assignment_id")),
            "report_back_mode": _string(compiler_context.get("report_back_mode")),
            "bootstrap_kind": _string(compiler_context.get("bootstrap_kind")),
            "session_kind": session_kind,
            "task_mode": task_mode,
            "kickoff_stage": kickoff_stage,
            "owner_agent_id": owner_agent_id,
            "industry_role_id": role.role_id if role is not None else role_id,
            "industry_role_name": role_name,
            "role_name": role_name,
            "role_summary": (
                role.role_summary
                if role is not None
                else _string(compiler_context.get("role_summary"))
            ),
            "mission": (
                role.mission
                if role is not None
                else _string(compiler_context.get("mission"))
            ),
            "goal_kind": goal_kind,
            "agent_class": role.agent_class if role is not None else None,
        }
        for key, value in scalar_fields.items():
            normalized = _string(value) if isinstance(value, str) else value
            if normalized is None:
                continue
            resolved[key] = normalized
        if environment_constraints:
            resolved["environment_constraints"] = environment_constraints
        if evidence_expectations:
            resolved["evidence_expectations"] = evidence_expectations
        return resolved

    def _goal_belongs_to_instance(
        self,
        goal: GoalRecord,
        *,
        record: IndustryInstanceRecord,
        override: GoalOverrideRecord | None = None,
        team: IndustryTeamBlueprint | None = None,
    ) -> bool:
        return _string(
            self._resolve_goal_runtime_context(
                goal,
                override=override,
                record=record,
                team=team,
            ).get("industry_instance_id"),
        ) == _string(record.instance_id)

    def _resolve_goal_owner_agent_id(
        self,
        goal: GoalRecord,
        *,
        override: GoalOverrideRecord | None = None,
        record: IndustryInstanceRecord | None = None,
        team: IndustryTeamBlueprint | None = None,
    ) -> str | None:
        return _string(
            self._resolve_goal_runtime_context(
                goal,
                override=override,
                record=record,
                team=team,
            ).get("owner_agent_id"),
        )

    def _resolve_role_blueprint(
        self,
        team: IndustryTeamBlueprint,
        role_id: str | None,
    ) -> IndustryRoleBlueprint | None:
        normalized_role_id = normalize_industry_role_id(role_id)
        if normalized_role_id is None:
            return None
        for agent in team.agents:
            if normalize_industry_role_id(agent.role_id) == normalized_role_id:
                return agent
        return None

    def _resolve_role_blueprint_by_agent(
        self,
        team: IndustryTeamBlueprint,
        agent_id: str | None,
    ) -> IndustryRoleBlueprint | None:
        if agent_id is None:
            return None
        for agent in team.agents:
            if agent.agent_id == agent_id or (
                is_execution_core_agent_id(agent_id)
                and is_execution_core_agent_id(agent.agent_id)
            ):
                return agent
        return None

    def _list_instance_schedules(
        self,
        instance_id: str,
        *,
        schedule_ids: list[str],
    ) -> list[dict[str, Any]]:
        if self._schedule_repository is None:
            return []
        resolved_ids = list(schedule_ids) or self._list_schedule_ids_for_instance(instance_id)
        payload: list[dict[str, Any]] = []
        for schedule_id in resolved_ids:
            schedule = self._schedule_repository.get_schedule(schedule_id)
            if schedule is None or schedule.status == "deleted":
                continue
            spec_payload = dict(schedule.spec_payload or {})
            meta_mapping = (
                dict(spec_payload.get("meta"))
                if isinstance(spec_payload.get("meta"), dict)
                else {}
            )
            payload.append(
                {
                    "schedule_id": schedule.id,
                    "title": schedule.title,
                    "status": schedule.status,
                    "enabled": schedule.enabled,
                    "cron": schedule.cron,
                    "timezone": schedule.timezone,
                    "dispatch_channel": _string(spec_payload.get("channel")) or "console",
                    "dispatch_mode": _string(spec_payload.get("mode")) or "stream",
                    "owner_agent_id": _string(meta_mapping.get("owner_agent_id")),
                    "industry_role_id": _string(meta_mapping.get("industry_role_id")),
                    "summary": _string(meta_mapping.get("summary")),
                    "next_run_at": schedule.next_run_at,
                    "last_run_at": schedule.last_run_at,
                    "last_error": schedule.last_error,
                    "updated_at": schedule.updated_at,
                    "route": f"/api/runtime-center/schedules/{schedule.id}",
                },
            )
        payload.sort(key=lambda item: _sort_timestamp(item.get("updated_at")), reverse=True)
        return payload

    def _list_schedule_ids_for_instance(self, instance_id: str) -> list[str]:
        if self._schedule_repository is None:
            return []
        schedule_ids: list[str] = []
        for schedule in self._schedule_repository.list_schedules():
            if schedule.status == "deleted":
                continue
            spec_payload = dict(schedule.spec_payload or {})
            meta_mapping = (
                dict(spec_payload.get("meta"))
                if isinstance(spec_payload.get("meta"), dict)
                else {}
            )
            if _string(meta_mapping.get("industry_instance_id")) == instance_id:
                schedule_ids.append(schedule.id)
        return schedule_ids

    def _list_pending_chat_kickoff_goals(
        self,
        record: IndustryInstanceRecord,
        *,
        team: IndustryTeamBlueprint | None = None,
    ) -> list[tuple[Any, GoalOverrideRecord | None]]:
        pending: list[tuple[Any, GoalOverrideRecord | None]] = []
        seen_goal_ids: set[str] = set()
        for goal_id in self._resolve_instance_goal_ids(record):
            normalized_goal_id = _string(goal_id)
            if normalized_goal_id is None or normalized_goal_id in seen_goal_ids:
                continue
            seen_goal_ids.add(normalized_goal_id)
            goal = self._goal_service.get_goal(normalized_goal_id)
            if goal is None or goal.status not in {"paused", "draft"}:
                continue
            override = self._goal_override_repository.get_override(goal.id)
            if not self._goal_belongs_to_instance(
                goal,
                record=record,
                override=override,
                team=team,
            ):
                continue
            pending.append((goal, override))
        return pending

    def _list_active_goal_links_for_instance(
        self,
        record: IndustryInstanceRecord,
        *,
        team: IndustryTeamBlueprint | None = None,
    ) -> dict[str, tuple[str, str]]:
        goal_links: dict[str, tuple[str, str]] = {}
        seen_goal_ids: set[str] = set()
        for goal_id in self._resolve_instance_goal_ids(record):
            normalized_goal_id = _string(goal_id)
            if normalized_goal_id is None or normalized_goal_id in seen_goal_ids:
                continue
            seen_goal_ids.add(normalized_goal_id)
            goal = self._goal_service.get_goal(normalized_goal_id)
            if goal is None or goal.status not in {"active", "blocked"}:
                continue
            override = self._goal_override_repository.get_override(goal.id)
            if not self._goal_belongs_to_instance(
                goal,
                record=record,
                override=override,
                team=team,
            ):
                continue
            owner_agent_id = self._resolve_goal_owner_agent_id(
                goal,
                override=override,
                record=record,
                team=team,
            )
            if owner_agent_id is None or owner_agent_id in goal_links:
                continue
            goal_links[owner_agent_id] = (goal.id, goal.title)
        return goal_links

    def _list_pending_chat_kickoff_schedule_ids(
        self,
        *,
        instance_id: str,
        schedule_ids: list[str],
    ) -> list[str]:
        if self._schedule_repository is None:
            return []
        resolved_ids = list(schedule_ids) or self._list_schedule_ids_for_instance(instance_id)
        pending_ids: list[str] = []
        for schedule_id in resolved_ids:
            schedule = self._schedule_repository.get_schedule(schedule_id)
            if (
                schedule is None
                or schedule.status == "deleted"
                or bool(schedule.enabled)
            ):
                continue
            spec_payload = dict(schedule.spec_payload or {})
            meta_mapping = (
                dict(spec_payload.get("meta"))
                if isinstance(spec_payload.get("meta"), dict)
                else {}
            )
            if _string(meta_mapping.get("industry_instance_id")) != instance_id:
                continue
            pending_ids.append(schedule.id)
        return pending_ids

    async def _retire_other_active_instances(
        self,
        *,
        active_instance_id: str,
    ) -> None:
        normalized_active_instance_id = _string(active_instance_id)
        if normalized_active_instance_id is None:
            return
        for record in self._industry_instance_repository.list_instances(status="active"):
            if _string(record.instance_id) == normalized_active_instance_id:
                continue
            await self._retire_instance(
                record,
                superseded_by_instance_id=normalized_active_instance_id,
            )

    async def _retire_instance(
        self,
        record: IndustryInstanceRecord,
        *,
        superseded_by_instance_id: str,
    ) -> None:
        resolved_goal_ids = self._resolve_instance_goal_ids(record)
        await self._cancel_instance_tasks(
            goal_ids=resolved_goal_ids,
            reason=(
                f"Industry instance '{record.instance_id}' was superseded by "
                f"'{superseded_by_instance_id}'."
            ),
        )
        self._archive_instance_goals(goal_ids=resolved_goal_ids)
        await self._pause_instance_schedules(
            instance_id=record.instance_id,
            schedule_ids=list(record.schedule_ids or []),
        )
        self._retire_stale_actors(instance_id=record.instance_id, active_agent_ids=set())
        self._retire_instance_overrides(instance_id=record.instance_id)
        self._retire_instance_runtimes(
            instance_id=record.instance_id,
            reason=(
                f"Industry instance '{record.instance_id}' was superseded by "
                f"'{superseded_by_instance_id}'."
            ),
        )
        self._delete_instance_thread_bindings(record.instance_id)
        self._retire_strategy_memory(record)
        if record.status != "retired":
            self._industry_instance_repository.upsert_instance(
                record.model_copy(
                    update={
                        "status": "retired",
                        "updated_at": _utc_now(),
                    },
                ),
            )

    def _resolve_instance_goal_ids(self, record: IndustryInstanceRecord) -> list[str]:
        goal_ids = {
            goal_id.strip()
            for goal_id in (record.goal_ids or [])
            if isinstance(goal_id, str) and goal_id.strip()
        }
        owner_scope = _string(record.owner_scope)
        if owner_scope is None:
            return sorted(goal_ids)
        for goal in self._goal_service.list_goals(owner_scope=owner_scope):
            override = self._goal_override_repository.get_override(goal.id)
            if not self._goal_belongs_to_instance(
                goal,
                record=record,
                override=override,
            ):
                continue
            goal_ids.add(goal.id)
        return sorted(goal_ids)

    def _resolve_instance_agent_ids(self, record: IndustryInstanceRecord) -> list[str]:
        agent_ids = {
            agent_id.strip()
            for agent_id in (record.agent_ids or [])
            if isinstance(agent_id, str) and agent_id.strip()
        }
        normalized_instance_id = _string(record.instance_id)
        if normalized_instance_id is None:
            return sorted(agent_ids)
        for override in self._agent_profile_override_repository.list_overrides():
            if _string(override.industry_instance_id) != normalized_instance_id:
                continue
            agent_id = _string(override.agent_id)
            if agent_id is not None:
                agent_ids.add(agent_id)
        if self._agent_runtime_repository is not None:
            for runtime in self._agent_runtime_repository.list_runtimes(
                industry_instance_id=record.instance_id,
                limit=None,
            ):
                agent_id = _string(runtime.agent_id)
                if agent_id is not None:
                    agent_ids.add(agent_id)
        return sorted(agent_ids)

    def _resolve_instance_thread_ids(self, instance_id: str) -> list[str]:
        repository = self._agent_thread_binding_repository
        if repository is None:
            return []
        return [
            binding.thread_id
            for binding in repository.list_bindings(
                industry_instance_id=instance_id,
                active_only=False,
                limit=None,
            )
        ]

    def _resolve_instance_task_ids(
        self,
        *,
        goal_ids: list[str],
        agent_ids: list[str],
    ) -> list[str]:
        task_repository = getattr(self._goal_service, "_task_repository", None)
        if task_repository is None:
            return []
        task_ids: set[str] = set()
        normalized_goal_ids = [goal_id for goal_id in goal_ids if goal_id]
        normalized_agent_ids = [agent_id for agent_id in agent_ids if agent_id]
        if normalized_goal_ids:
            for task in task_repository.list_tasks(goal_ids=normalized_goal_ids):
                task_ids.add(task.id)
        non_execution_agent_ids = [
            agent_id
            for agent_id in normalized_agent_ids
            if not is_execution_core_agent_id(agent_id)
        ]
        if non_execution_agent_ids:
            for task in task_repository.list_tasks(owner_agent_ids=non_execution_agent_ids):
                task_ids.add(task.id)
        return sorted(task_ids)

    async def _cancel_instance_tasks(
        self,
        *,
        goal_ids: list[str],
        reason: str,
    ) -> None:
        task_repository = getattr(self._goal_service, "_task_repository", None)
        if task_repository is None:
            return
        runtime_repository = getattr(self._goal_service, "_task_runtime_repository", None)
        dispatcher = getattr(self._goal_service, "_dispatcher", None)
        normalized_goal_ids = [
            goal_id.strip()
            for goal_id in goal_ids
            if isinstance(goal_id, str) and goal_id.strip()
        ]
        if not normalized_goal_ids:
            return
        for task in task_repository.list_tasks(goal_ids=normalized_goal_ids):
            runtime = (
                runtime_repository.get_runtime(task.id)
                if runtime_repository is not None
                else None
            )
            task_phase = _string(getattr(runtime, "current_phase", None)) or _string(task.status)
            if task_phase in {"completed", "failed", "cancelled"}:
                continue
            if dispatcher is not None and callable(getattr(dispatcher, "cancel_task", None)):
                try:
                    dispatcher.cancel_task(task.id, resolution=reason)
                    continue
                except Exception:
                    logger.exception(
                        "Failed to cancel superseded industry task '%s'",
                        task.id,
                    )
            task_repository.upsert_task(
                task.model_copy(
                    update={
                        "status": "cancelled",
                        "updated_at": _utc_now(),
                    },
                ),
            )
            if runtime is not None and runtime_repository is not None:
                runtime_repository.upsert_runtime(
                    runtime.model_copy(
                        update={
                            "runtime_status": "terminated",
                            "current_phase": "cancelled",
                            "last_error_summary": reason,
                            "updated_at": _utc_now(),
                        },
                    ),
                )

    def _archive_instance_goals(self, *, goal_ids: list[str]) -> None:
        normalized_goal_ids = [
            goal_id.strip()
            for goal_id in goal_ids
            if isinstance(goal_id, str) and goal_id.strip()
        ]
        for goal_id in normalized_goal_ids:
            goal = self._goal_service.get_goal(goal_id)
            if goal is not None and goal.status != "archived":
                self._goal_service.update_goal(goal_id, status="archived")
            override = self._goal_override_repository.get_override(goal_id)
            if override is None or override.status == "archived":
                continue
            self._goal_override_repository.upsert_override(
                override.model_copy(
                    update={
                        "status": "archived",
                        "updated_at": _utc_now(),
                    },
                ),
            )

    def _delete_instance_goals(self, goal_ids: list[str]) -> int:
        deleted = 0
        for goal_id in {
            goal_id.strip()
            for goal_id in goal_ids
            if isinstance(goal_id, str) and goal_id.strip()
        }:
            if self._goal_service.delete_goal(goal_id):
                deleted += 1
        return deleted

    async def _pause_instance_schedules(
        self,
        *,
        instance_id: str,
        schedule_ids: list[str],
    ) -> None:
        if self._schedule_repository is None:
            return
        resolved_ids = list(schedule_ids) or self._list_schedule_ids_for_instance(instance_id)
        for schedule_id in resolved_ids:
            schedule = self._schedule_repository.get_schedule(schedule_id)
            if schedule is None or schedule.status == "deleted":
                continue
            spec_payload = dict(schedule.spec_payload or {})
            spec_payload["enabled"] = False
            pause_job = getattr(self._cron_manager, "pause_job", None)
            if callable(pause_job):
                try:
                    result = pause_job(schedule_id)
                    if inspect.isawaitable(result):
                        await result
                except Exception:
                    logger.exception(
                        "Failed to pause superseded industry schedule '%s'",
                        schedule_id,
                    )
            self._schedule_repository.upsert_schedule(
                schedule.model_copy(
                    update={
                        "status": "paused",
                        "enabled": False,
                        "spec_payload": spec_payload,
                        "updated_at": _utc_now(),
                    },
                ),
            )

    async def _resume_instance_schedules(
        self,
        *,
        instance_id: str,
        schedule_ids: list[str],
    ) -> list[str]:
        if self._schedule_repository is None:
            return []
        resolved_ids = list(schedule_ids) or self._list_schedule_ids_for_instance(instance_id)
        resumed_ids: list[str] = []
        for schedule_id in resolved_ids:
            schedule = self._schedule_repository.get_schedule(schedule_id)
            if schedule is None or schedule.status == "deleted":
                continue
            spec_payload = dict(schedule.spec_payload or {})
            spec_payload["enabled"] = True
            resume_job = getattr(self._cron_manager, "resume_job", None)
            if callable(resume_job):
                try:
                    result = resume_job(schedule_id)
                    if inspect.isawaitable(result):
                        await result
                except Exception:
                    logger.exception(
                        "Failed to resume waiting industry schedule '%s'",
                        schedule_id,
                    )
            self._schedule_repository.upsert_schedule(
                schedule.model_copy(
                    update={
                        "status": "scheduled",
                        "enabled": True,
                        "spec_payload": spec_payload,
                        "updated_at": _utc_now(),
                    },
                ),
            )
            resumed_ids.append(schedule_id)
        return resumed_ids

    async def _delete_instance_schedules(self, schedule_ids: list[str]) -> int:
        deleted = 0
        if self._schedule_repository is None:
            return deleted
        delete_job = getattr(self._cron_manager, "delete_job", None)
        for schedule_id in {
            schedule_id.strip()
            for schedule_id in schedule_ids
            if isinstance(schedule_id, str) and schedule_id.strip()
        }:
            if callable(delete_job):
                try:
                    result = delete_job(schedule_id)
                    if inspect.isawaitable(result):
                        await result
                except Exception:
                    logger.exception(
                        "Failed to stop deleted industry schedule '%s'",
                        schedule_id,
                    )
            if self._schedule_repository.delete_schedule(schedule_id):
                deleted += 1
        return deleted

    def _delete_instance_tasks(self, task_ids: list[str]) -> int:
        task_repository = getattr(self._goal_service, "_task_repository", None)
        if task_repository is None:
            return 0
        deleted = 0
        for task_id in {
            task_id.strip()
            for task_id in task_ids
            if isinstance(task_id, str) and task_id.strip()
        }:
            if task_repository.delete_task(task_id):
                deleted += 1
        return deleted

    def _delete_instance_task_runtimes(self, task_ids: list[str]) -> int:
        runtime_repository = getattr(self._goal_service, "_task_runtime_repository", None)
        if runtime_repository is None:
            return 0
        deleted = 0
        for task_id in {
            task_id.strip()
            for task_id in task_ids
            if isinstance(task_id, str) and task_id.strip()
        }:
            if runtime_repository.delete_runtime(task_id):
                deleted += 1
        return deleted

    def _delete_instance_runtime_frames(self, task_ids: list[str]) -> int:
        frame_repository = getattr(self._goal_service, "_runtime_frame_repository", None)
        if frame_repository is None:
            return 0
        deleted = 0
        for task_id in {
            task_id.strip()
            for task_id in task_ids
            if isinstance(task_id, str) and task_id.strip()
        }:
            for frame in frame_repository.list_frames(task_id, limit=None):
                if frame_repository.delete_frame(frame.id):
                    deleted += 1
        return deleted

    def _delete_instance_decisions(self, task_ids: list[str]) -> int:
        repository = getattr(self._goal_service, "_decision_request_repository", None)
        if repository is None:
            return 0
        deleted = 0
        normalized_task_ids = [
            task_id.strip()
            for task_id in task_ids
            if isinstance(task_id, str) and task_id.strip()
        ]
        if not normalized_task_ids:
            return deleted
        decision_ids: set[str] = set()
        for decision in repository.list_decision_requests(
            task_ids=normalized_task_ids,
            limit=None,
        ):
            decision_id = _string(getattr(decision, "id", None))
            if decision_id:
                decision_ids.add(decision_id)
        for task_id in normalized_task_ids:
            for decision in repository.list_decision_requests(
                task_id=task_id,
                limit=None,
            ):
                decision_id = _string(getattr(decision, "id", None))
                if decision_id:
                    decision_ids.add(decision_id)
        for decision_id in decision_ids:
            if repository.delete_decision_request(decision_id):
                deleted += 1
        return deleted

    def _collect_instance_evidence_ids(self, *, task_ids: list[str]) -> list[str]:
        if self._evidence_ledger is None:
            return []
        normalized_task_ids = _unique_strings(task_ids)
        if not normalized_task_ids:
            return []
        return [
            evidence_id
            for evidence_id in (
                _string(record.id)
                for record in self._evidence_ledger.list_records(
                    task_ids=normalized_task_ids,
                    limit=None,
                )
            )
            if evidence_id is not None
        ]

    def _plan_instance_learning_deletion(
        self,
        *,
        instance_id: str,
        goal_ids: list[str],
        task_ids: list[str],
        agent_ids: list[str],
        evidence_ids: list[str],
    ) -> _InstanceLearningDeletionPlan:
        normalized_instance_id = _string(instance_id)
        normalized_goal_ids = set(_unique_strings(goal_ids))
        normalized_task_ids = set(_unique_strings(task_ids))
        normalized_evidence_ids = set(_unique_strings(evidence_ids))
        normalized_agent_ids = {
            agent_id
            for agent_id in _unique_strings(agent_ids)
            if not is_execution_core_agent_id(agent_id)
        }

        proposal_ids: list[str] = []
        for proposal in self._call_learning_lister("list_proposals", limit=None):
            proposal_id = _string(getattr(proposal, "id", None))
            if proposal_id is None:
                continue
            if (
                _string(getattr(proposal, "goal_id", None)) in normalized_goal_ids
                or _string(getattr(proposal, "task_id", None)) in normalized_task_ids
                or _string(getattr(proposal, "agent_id", None)) in normalized_agent_ids
                or _sequence_intersects(
                    getattr(proposal, "evidence_refs", None),
                    normalized_evidence_ids,
                )
            ):
                proposal_ids.append(proposal_id)
        normalized_proposal_ids = set(proposal_ids)

        patch_ids: list[str] = []
        for patch in self._call_learning_lister("list_patches", limit=None):
            patch_id = _string(getattr(patch, "id", None))
            if patch_id is None:
                continue
            if (
                _string(getattr(patch, "proposal_id", None)) in normalized_proposal_ids
                or _string(getattr(patch, "goal_id", None)) in normalized_goal_ids
                or _string(getattr(patch, "task_id", None)) in normalized_task_ids
                or _string(getattr(patch, "agent_id", None)) in normalized_agent_ids
                or _string(getattr(patch, "source_evidence_id", None))
                in normalized_evidence_ids
                or _sequence_intersects(
                    getattr(patch, "evidence_refs", None),
                    normalized_evidence_ids,
                )
            ):
                patch_ids.append(patch_id)
        normalized_patch_ids = set(patch_ids)

        growth_ids: list[str] = []
        for event in self._call_learning_lister("list_growth", limit=None):
            event_id = _string(getattr(event, "id", None))
            if event_id is None:
                continue
            if (
                _string(getattr(event, "goal_id", None)) in normalized_goal_ids
                or _string(getattr(event, "task_id", None)) in normalized_task_ids
                or _string(getattr(event, "agent_id", None)) in normalized_agent_ids
                or _string(getattr(event, "source_patch_id", None))
                in normalized_patch_ids
                or _string(getattr(event, "source_evidence_id", None))
                in normalized_evidence_ids
            ):
                growth_ids.append(event_id)

        acquisition_proposal_ids: list[str] = []
        acquisition_evidence_ids: list[str] = []
        for proposal in self._call_learning_lister(
            "list_acquisition_proposals",
            limit=None,
        ):
            proposal_id = _string(getattr(proposal, "id", None))
            if proposal_id is None:
                continue
            if (
                _string(getattr(proposal, "industry_instance_id", None))
                == normalized_instance_id
                or _string(getattr(proposal, "target_agent_id", None)) in normalized_agent_ids
                or _sequence_intersects(
                    getattr(proposal, "evidence_refs", None),
                    normalized_evidence_ids,
                )
            ):
                acquisition_proposal_ids.append(proposal_id)
                acquisition_evidence_ids.extend(
                    _unique_strings(getattr(proposal, "evidence_refs", None)),
                )
        normalized_acquisition_proposal_ids = set(acquisition_proposal_ids)

        install_binding_plan_ids: list[str] = []
        for plan in self._call_learning_lister(
            "list_install_binding_plans",
            limit=None,
        ):
            plan_id = _string(getattr(plan, "id", None))
            if plan_id is None:
                continue
            if (
                _string(getattr(plan, "proposal_id", None))
                in normalized_acquisition_proposal_ids
                or _string(getattr(plan, "industry_instance_id", None))
                == normalized_instance_id
                or _string(getattr(plan, "target_agent_id", None)) in normalized_agent_ids
                or _sequence_intersects(
                    getattr(plan, "evidence_refs", None),
                    normalized_evidence_ids,
                )
            ):
                install_binding_plan_ids.append(plan_id)
                acquisition_evidence_ids.extend(
                    _unique_strings(getattr(plan, "evidence_refs", None)),
                )
        normalized_install_binding_plan_ids = set(install_binding_plan_ids)

        onboarding_run_ids: list[str] = []
        for run in self._call_learning_lister("list_onboarding_runs", limit=None):
            run_id = _string(getattr(run, "id", None))
            if run_id is None:
                continue
            if (
                _string(getattr(run, "proposal_id", None))
                in normalized_acquisition_proposal_ids
                or _string(getattr(run, "plan_id", None))
                in normalized_install_binding_plan_ids
                or _string(getattr(run, "industry_instance_id", None))
                == normalized_instance_id
                or _string(getattr(run, "target_agent_id", None)) in normalized_agent_ids
                or _sequence_intersects(
                    getattr(run, "evidence_refs", None),
                    normalized_evidence_ids,
                )
            ):
                onboarding_run_ids.append(run_id)
                acquisition_evidence_ids.extend(
                    _unique_strings(getattr(run, "evidence_refs", None)),
                )

        return _InstanceLearningDeletionPlan(
            proposal_ids=proposal_ids,
            patch_ids=patch_ids,
            growth_ids=growth_ids,
            acquisition_proposal_ids=acquisition_proposal_ids,
            install_binding_plan_ids=install_binding_plan_ids,
            onboarding_run_ids=onboarding_run_ids,
            evidence_ids=_unique_strings(acquisition_evidence_ids),
        )

    def _call_learning_lister(self, method_name: str, **kwargs: Any) -> list[Any]:
        lister = getattr(self._learning_service, method_name, None)
        if not callable(lister):
            return []
        try:
            items = lister(**kwargs)
        except TypeError:
            items = lister()
        return list(items or [])

    def _delete_instance_evidence_records(self, evidence_ids: list[str]) -> int:
        if self._evidence_ledger is None:
            return 0
        normalized_evidence_ids = _unique_strings(evidence_ids)
        if not normalized_evidence_ids:
            return 0
        return self._evidence_ledger.delete_records(evidence_ids=normalized_evidence_ids)

    def _delete_instance_learning_proposals(self, proposal_ids: list[str]) -> int:
        deleter = getattr(self._learning_service, "delete_proposal", None)
        if not callable(deleter):
            return 0
        deleted = 0
        for proposal_id in _unique_strings(proposal_ids):
            if deleter(proposal_id):
                deleted += 1
        return deleted

    def _delete_instance_learning_patches(self, patch_ids: list[str]) -> int:
        deleter = getattr(self._learning_service, "delete_patch", None)
        if not callable(deleter):
            return 0
        deleted = 0
        for patch_id in _unique_strings(patch_ids):
            if deleter(patch_id):
                deleted += 1
        return deleted

    def _delete_instance_learning_growth(self, growth_ids: list[str]) -> int:
        deleter = getattr(self._learning_service, "delete_growth_event", None)
        if not callable(deleter):
            return 0
        deleted = 0
        for growth_id in _unique_strings(growth_ids):
            if deleter(growth_id):
                deleted += 1
        return deleted

    def _delete_instance_acquisition_proposals(self, proposal_ids: list[str]) -> int:
        deleter = getattr(self._learning_service, "delete_acquisition_proposal", None)
        if not callable(deleter):
            return 0
        deleted = 0
        for proposal_id in _unique_strings(proposal_ids):
            if deleter(proposal_id):
                deleted += 1
        return deleted

    def _delete_instance_install_binding_plans(self, plan_ids: list[str]) -> int:
        deleter = getattr(self._learning_service, "delete_install_binding_plan", None)
        if not callable(deleter):
            return 0
        deleted = 0
        for plan_id in _unique_strings(plan_ids):
            if deleter(plan_id):
                deleted += 1
        return deleted

    def _delete_instance_onboarding_runs(self, run_ids: list[str]) -> int:
        deleter = getattr(self._learning_service, "delete_onboarding_run", None)
        if not callable(deleter):
            return 0
        deleted = 0
        for run_id in _unique_strings(run_ids):
            if deleter(run_id):
                deleted += 1
        return deleted

    def _retire_instance_overrides(self, *, instance_id: str) -> None:
        normalized_instance_id = _string(instance_id)
        if normalized_instance_id is None:
            return
        for override in self._agent_profile_override_repository.list_overrides():
            if _string(override.industry_instance_id) != normalized_instance_id:
                continue
            self._agent_profile_override_repository.delete_override(override.agent_id)

    def _retire_instance_runtimes(
        self,
        *,
        instance_id: str,
        reason: str,
    ) -> None:
        repository = self._agent_runtime_repository
        if repository is None:
            return
        retired_at = _utc_now()
        for runtime in repository.list_runtimes(
            industry_instance_id=instance_id,
            limit=None,
        ):
            repository.upsert_runtime(
                runtime.model_copy(
                    update={
                        "desired_state": "retired",
                        "runtime_status": "retired",
                        "queue_depth": 0,
                        "current_task_id": None,
                        "current_mailbox_id": None,
                        "last_stopped_at": retired_at,
                        "last_error_summary": reason,
                        "updated_at": retired_at,
                    },
                ),
            )

    def _delete_instance_agent_overrides(self, agent_ids: list[str]) -> int:
        deleted = 0
        for agent_id in {
            agent_id.strip()
            for agent_id in agent_ids
            if isinstance(agent_id, str)
            and agent_id.strip()
            and not is_execution_core_agent_id(agent_id)
        }:
            if self._agent_profile_override_repository.delete_override(agent_id):
                deleted += 1
        return deleted

    def _delete_instance_agent_runtimes(self, agent_ids: list[str]) -> int:
        repository = self._agent_runtime_repository
        if repository is None:
            return 0
        deleted = 0
        for agent_id in {
            agent_id.strip()
            for agent_id in agent_ids
            if isinstance(agent_id, str)
            and agent_id.strip()
            and not is_execution_core_agent_id(agent_id)
        }:
            if repository.delete_runtime(agent_id):
                deleted += 1
        return deleted

    def _delete_instance_mailbox_items(
        self,
        *,
        agent_ids: list[str],
        thread_ids: list[str],
    ) -> int:
        repository = self._agent_mailbox_repository
        if repository is None:
            return 0
        deleted_item_ids: set[str] = set()
        non_execution_agent_ids = [
            agent_id
            for agent_id in agent_ids
            if not is_execution_core_agent_id(agent_id)
        ]
        for agent_id in non_execution_agent_ids:
            for item in repository.list_items(agent_id=agent_id, limit=None):
                deleted_item_ids.add(item.id)
        for thread_id in thread_ids:
            for item in repository.list_items(
                conversation_thread_id=thread_id,
                limit=None,
            ):
                deleted_item_ids.add(item.id)
        deleted = 0
        for item_id in deleted_item_ids:
            if repository.delete_item(item_id):
                deleted += 1
        return deleted

    def _delete_instance_checkpoints(
        self,
        *,
        agent_ids: list[str],
        task_ids: list[str],
    ) -> int:
        repository = self._agent_checkpoint_repository
        if repository is None:
            return 0
        checkpoint_ids: set[str] = set()
        non_execution_agent_ids = [
            agent_id
            for agent_id in agent_ids
            if not is_execution_core_agent_id(agent_id)
        ]
        for agent_id in non_execution_agent_ids:
            for checkpoint in repository.list_checkpoints(agent_id=agent_id, limit=None):
                checkpoint_ids.add(checkpoint.id)
        for task_id in task_ids:
            for checkpoint in repository.list_checkpoints(task_id=task_id, limit=None):
                checkpoint_ids.add(checkpoint.id)
        deleted = 0
        for checkpoint_id in checkpoint_ids:
            if repository.delete_checkpoint(checkpoint_id):
                deleted += 1
        return deleted

    def _delete_instance_leases(self, agent_ids: list[str]) -> int:
        repository = self._agent_lease_repository
        if repository is None:
            return 0
        deleted = 0
        for agent_id in {
            agent_id.strip()
            for agent_id in agent_ids
            if isinstance(agent_id, str)
            and agent_id.strip()
            and not is_execution_core_agent_id(agent_id)
        }:
            for lease in repository.list_leases(agent_id=agent_id, limit=None):
                if repository.delete_lease(lease.id):
                    deleted += 1

        return deleted

    def _delete_instance_thread_bindings(self, instance_id: str) -> int:
        repository = self._agent_thread_binding_repository
        if repository is None:
            return 0
        deleted = 0
        for binding in repository.list_bindings(
            industry_instance_id=instance_id,
            active_only=False,
            limit=None,
        ):
            if repository.delete_binding(binding.thread_id):
                deleted += 1
        return deleted

    def _retire_strategy_memory(self, record: IndustryInstanceRecord) -> None:
        service = self._strategy_memory_service
        if service is None or not callable(getattr(service, "upsert_strategy", None)):
            return
        getter = getattr(service, "get_active_strategy", None)
        if not callable(getter):
            return
        strategy = getter(
            scope_type="industry",
            scope_id=record.instance_id,
            owner_agent_id=EXECUTION_CORE_AGENT_ID,
        )
        if strategy is None:
            return
        service.upsert_strategy(
            strategy.model_copy(
                update={
                    "status": "retired",
                    "active_goal_ids": [],
                    "active_goal_titles": [],
                    "updated_at": _utc_now(),
                },
            ),
        )

    def _delete_instance_strategy_records(self, instance_id: str) -> int:
        repository = self._strategy_memory_repository
        if repository is None:
            return 0
        deleted = 0
        for strategy in repository.list_strategies(
            industry_instance_id=instance_id,
            limit=None,
        ):
            if repository.delete_strategy(strategy.strategy_id):
                deleted += 1
        return deleted

    def _delete_instance_workflow_runs(self, instance_id: str) -> int:
        repository = self._workflow_run_repository
        if repository is None:
            return 0
        deleted = 0
        for run in repository.list_runs(industry_instance_id=instance_id):
            if repository.delete_run(run.run_id):
                deleted += 1
        return deleted

    def _delete_instance_prediction_cases(self, instance_id: str) -> int:
        case_repository = self._prediction_case_repository
        scenario_repository = self._prediction_scenario_repository
        signal_repository = self._prediction_signal_repository
        recommendation_repository = self._prediction_recommendation_repository
        review_repository = self._prediction_review_repository
        if any(
            repository is None
            for repository in (
                case_repository,
                scenario_repository,
                signal_repository,
                recommendation_repository,
                review_repository,
            )
        ):
            return 0
        deleted = 0
        for case in case_repository.list_cases(industry_instance_id=instance_id):
            scenario_repository.delete_for_case(case.case_id)
            signal_repository.delete_for_case(case.case_id)
            recommendation_repository.delete_for_case(case.case_id)
            for review in review_repository.list_reviews(case_id=case.case_id, limit=None):
                review_repository.delete_review(review.review_id)
            if case_repository.delete_case(case.case_id):
                deleted += 1
        return deleted

    def _list_instance_agents(self, agent_ids: set[str]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for agent_id in sorted(agent_ids):
            data = self._get_agent_snapshot(agent_id)
            if data is None:
                continue
            item = dict(data)
            item["route"] = f"/api/runtime-center/agents/{agent_id}"
            payload.append(item)
        payload.sort(key=lambda item: _sort_timestamp(item.get("updated_at")), reverse=True)
        return payload

    def _list_instance_proposals(
        self,
        *,
        goal_ids: set[str],
        task_ids: set[str],
        agent_ids: set[str],
    ) -> list[dict[str, Any]]:
        lister = getattr(self._learning_service, "list_proposals", None)
        if not callable(lister):
            return []
        proposals: list[dict[str, Any]] = []
        for proposal in list(lister()):
            proposal_goal_id = _string(getattr(proposal, "goal_id", None))
            proposal_task_id = _string(getattr(proposal, "task_id", None))
            proposal_agent_id = _string(getattr(proposal, "agent_id", None))
            if (
                proposal_goal_id in goal_ids
                or proposal_task_id in task_ids
                or proposal_agent_id in agent_ids
            ):
                proposals.append(proposal.model_dump(mode="json"))
        proposals.sort(key=lambda item: _sort_timestamp(item.get("created_at")), reverse=True)
        return proposals

    def _list_instance_acquisition_proposals(
        self,
        instance_id: str,
    ) -> list[dict[str, Any]]:
        lister = getattr(self._learning_service, "list_acquisition_proposals", None)
        if not callable(lister):
            return []
        proposals = [
            item.model_dump(mode="json")
            for item in list(
                lister(industry_instance_id=instance_id, limit=None),
            )
        ]
        for proposal in proposals:
            proposal_id = _string(proposal.get("id"))
            if proposal_id is None:
                continue
            proposal["route"] = f"/api/learning/acquisition/proposals/{proposal_id}"
        proposals.sort(key=lambda item: _sort_timestamp(item.get("updated_at")), reverse=True)
        return proposals

    def _list_instance_install_binding_plans(
        self,
        instance_id: str,
    ) -> list[dict[str, Any]]:
        lister = getattr(self._learning_service, "list_install_binding_plans", None)
        if not callable(lister):
            return []
        plans = [
            item.model_dump(mode="json")
            for item in list(
                lister(industry_instance_id=instance_id, limit=None),
            )
        ]
        for plan in plans:
            plan_id = _string(plan.get("id"))
            if plan_id is None:
                continue
            plan["route"] = f"/api/learning/acquisition/plans/{plan_id}"
        plans.sort(key=lambda item: _sort_timestamp(item.get("updated_at")), reverse=True)
        return plans

    def _list_instance_onboarding_runs(
        self,
        instance_id: str,
    ) -> list[dict[str, Any]]:
        lister = getattr(self._learning_service, "list_onboarding_runs", None)
        if not callable(lister):
            return []
        runs = [
            item.model_dump(mode="json")
            for item in list(
                lister(industry_instance_id=instance_id, limit=None),
            )
        ]
        for run in runs:
            run_id = _string(run.get("id"))
            if run_id is None:
                continue
            run["route"] = f"/api/learning/acquisition/onboarding-runs/{run_id}"
        runs.sort(key=lambda item: _sort_timestamp(item.get("updated_at")), reverse=True)
        return runs

    def _build_reports(
        self,
        *,
        evidence: list[dict[str, Any]],
        proposals: list[dict[str, Any]],
        patches: list[dict[str, Any]],
        growth: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
    ) -> dict[str, IndustryReportSnapshot]:
        now = _utc_now()
        return {
            "daily": self._build_report_snapshot(
                window="daily",
                since=now - timedelta(days=1),
                now=now,
                evidence=evidence,
                proposals=proposals,
                patches=patches,
                growth=growth,
                decisions=decisions,
            ),
            "weekly": self._build_report_snapshot(
                window="weekly",
                since=now - timedelta(days=7),
                now=now,
                evidence=evidence,
                proposals=proposals,
                patches=patches,
                growth=growth,
                decisions=decisions,
            ),
        }

    def _build_report_snapshot(
        self,
        *,
        window: str,
        since: datetime,
        now: datetime,
        evidence: list[dict[str, Any]],
        proposals: list[dict[str, Any]],
        patches: list[dict[str, Any]],
        growth: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
    ) -> IndustryReportSnapshot:
        report = IndustryReportSnapshot(
            window="daily" if window == "daily" else "weekly",
            since=since,
            until=now,
        )
        filtered_evidence = _filter_since(evidence, "created_at", since)
        filtered_proposals = _filter_since(proposals, "created_at", since)
        filtered_patches = _filter_since(patches, "created_at", since)
        filtered_growth = _filter_since(growth, "created_at", since)
        filtered_decisions = _filter_since(decisions, "created_at", since)
        report.evidence_count = len(filtered_evidence)
        report.proposal_count = len(filtered_proposals)
        report.patch_count = len(filtered_patches)
        report.applied_patch_count = sum(
            1 for patch in filtered_patches if _string(patch.get("status")) == "applied"
        )
        report.growth_count = len(filtered_growth)
        report.decision_count = len(filtered_decisions)
        report.recent_evidence = filtered_evidence[:5]
        report.highlights = [
            f"Evidence {report.evidence_count}",
            f"Proposals {report.proposal_count}",
            f"Patches {report.patch_count}",
            f"Applied patches {report.applied_patch_count}",
            f"Growth {report.growth_count}",
            f"Decisions {report.decision_count}",
        ]
        return report

    async def _upsert_schedule_seed(
        self,
        seed: IndustryScheduleSeed,
        *,
        enabled: bool = True,
    ) -> IndustryBootstrapScheduleResult:
        spec = self._build_schedule_spec(seed, enabled=enabled)
        await self._persist_schedule_spec(spec)
        schedule_record = (
            self._schedule_repository.get_schedule(seed.schedule_id)
            if self._schedule_repository is not None
            else None
        )
        schedule_payload = (
            schedule_record.model_dump(mode="json")
            if schedule_record is not None
            else {"id": seed.schedule_id, "title": seed.title, "cron": seed.cron}
        )
        return IndustryBootstrapScheduleResult(
            schedule_id=seed.schedule_id,
            schedule=schedule_payload,
            spec=spec,
            routes={
                "schedule": f"/api/runtime-center/schedules/{seed.schedule_id}",
                "runtime_detail": (
                    f"/api/runtime-center/industry/{seed.metadata.get('industry_instance_id')}"
                ),
            },
        )

    def _build_schedule_spec(
        self,
        seed: IndustryScheduleSeed,
        *,
        enabled: bool = True,
    ) -> dict[str, Any]:
        return {
            "id": seed.schedule_id,
            "name": seed.title,
            "enabled": enabled,
            "schedule": {"type": "cron", "cron": seed.cron, "timezone": seed.timezone},
            "task_type": "agent",
            "request": dict(seed.request_payload),
            "dispatch": {
                "type": "channel",
                "channel": seed.dispatch_channel,
                "target": {
                    "user_id": seed.dispatch_user_id,
                    "session_id": seed.dispatch_session_id,
                },
                "mode": seed.dispatch_mode,
                "meta": {
                    "summary": seed.summary,
                    "owner_agent_id": seed.owner_agent_id,
                    **dict(seed.metadata),
                },
            },
            "runtime": {
                "max_concurrency": 1,
                "timeout_seconds": 180,
                "misfire_grace_seconds": 60,
            },
            "meta": {
                "summary": seed.summary,
                "owner_agent_id": seed.owner_agent_id,
                **dict(seed.metadata),
            },
        }

    async def _persist_schedule_spec(self, spec: dict[str, Any]) -> None:
        if self._cron_manager is not None and callable(
            getattr(self._cron_manager, "create_or_replace_job", None),
        ):
            from ..app.crons.models import CronJobSpec

            await self._cron_manager.create_or_replace_job(CronJobSpec.model_validate(spec))
            return
        if self._schedule_writer is not None and callable(
            getattr(self._schedule_writer, "upsert_job", None),
        ):
            from ..app.crons.models import CronJobSpec

            result = self._schedule_writer.upsert_job(CronJobSpec.model_validate(spec))
            if inspect.isawaitable(result):
                await result

    def _archive_superseded_goals(
        self,
        *,
        owner_scope: str,
        active_goal_ids: set[str],
    ) -> None:
        normalized_goal_ids = {
            goal_id.strip()
            for goal_id in active_goal_ids
            if isinstance(goal_id, str) and goal_id.strip()
        }
        for goal in self._goal_service.list_goals(owner_scope=owner_scope):
            if goal.id in normalized_goal_ids:
                continue
            override = self._goal_override_repository.get_override(goal.id)
            compiler_context = dict(override.compiler_context or {}) if override is not None else {}
            if _string(compiler_context.get("bootstrap_kind")) != "industry-v1":
                continue
            if goal.status != "archived":
                self._goal_service.update_goal(goal.id, status="archived")
            if override is None or override.status == "archived":
                continue
            self._goal_override_repository.upsert_override(
                override.model_copy(
                    update={
                        "status": "archived",
                        "updated_at": _utc_now(),
                    },
                ),
            )

    def _prune_stale_agent_profiles(
        self,
        *,
        instance_id: str,
        active_agent_ids: set[str],
    ) -> None:
        self._retire_stale_actors(
            instance_id=instance_id,
            active_agent_ids=active_agent_ids,
        )
        normalized_active_agent_ids = {
            agent_id
            for agent_id in active_agent_ids
            if not is_execution_core_agent_id(agent_id)
        }
        for override in self._agent_profile_override_repository.list_overrides():
            if _string(override.industry_instance_id) != _string(instance_id):
                continue
            agent_id = _string(override.agent_id)
            if agent_id is None:
                continue
            if is_execution_core_agent_id(agent_id):
                self._agent_profile_override_repository.delete_override(agent_id)
                continue
            if agent_id in normalized_active_agent_ids:
                continue
            self._agent_profile_override_repository.delete_override(agent_id)

    def _upsert_agent_profile(
        self,
        agent: IndustryRoleBlueprint,
        *,
        instance_id: str,
        goal_id: str | None,
        goal_title: str | None,
        status: str,
    ) -> None:
        if is_execution_core_agent_id(agent.agent_id):
            existing = self._agent_profile_override_repository.get_override(agent.agent_id)
            if existing is not None and (
                _string(existing.industry_instance_id)
                or _string(existing.industry_role_id)
            ):
                self._agent_profile_override_repository.delete_override(agent.agent_id)
            return
        existing = self._agent_profile_override_repository.get_override(agent.agent_id)
        update = {
            "name": agent.name,
            "role_name": agent.role_name,
            "role_summary": agent.role_summary,
            "agent_class": agent.agent_class,
            "employment_mode": agent.employment_mode,
            "activation_mode": agent.activation_mode,
            "suspendable": agent.suspendable,
            "reports_to": agent.reports_to,
            "mission": agent.mission,
            "status": status,
            "risk_level": agent.risk_level,
            "current_focus_kind": None,
            "current_focus_id": None,
            "current_focus": None,
            "industry_instance_id": instance_id,
            "industry_role_id": agent.role_id,
            "environment_summary": "; ".join(agent.environment_constraints),
            "environment_constraints": list(agent.environment_constraints),
            "evidence_expectations": list(agent.evidence_expectations),
            "capabilities": list(agent.allowed_capabilities),
            "reason": "Industry V1 bootstrap",
        }
        if existing is None:
            override = AgentProfileOverrideRecord(
                agent_id=agent.agent_id,
                **update,
            )
        else:
            override = existing.model_copy(update=update)
        self._agent_profile_override_repository.upsert_override(override)

    def _normalize_industry_surfaces(self) -> None:
        for record in self._industry_instance_repository.list_instances():
            normalized_team = self._materialize_team_blueprint(record)
            normalized_payload = normalized_team.model_dump(mode="json")
            normalized_agent_ids = [agent.agent_id for agent in normalized_team.agents]
            normalized_profile = IndustryProfile.model_validate(
                record.profile_payload or {"industry": record.label},
            )
            normalized_execution_core_identity = self._build_execution_core_identity(
                instance_id=record.instance_id,
                profile=normalized_profile,
                team=normalized_team,
                industry_label=record.label,
                industry_summary=record.summary,
            ).model_dump(mode="json")
            update: dict[str, Any] = {}
            if normalized_payload != dict(record.team_payload or {}):
                update["team_payload"] = normalized_payload
            if normalized_agent_ids != list(record.agent_ids or []):
                update["agent_ids"] = normalized_agent_ids
            if normalized_execution_core_identity != dict(
                record.execution_core_identity_payload or {},
            ):
                update["execution_core_identity_payload"] = (
                    normalized_execution_core_identity
                )
            active_record = record
            if update:
                active_record = record.model_copy(
                    update={
                        **update,
                        "updated_at": _utc_now(),
                    },
                )
                self._industry_instance_repository.upsert_instance(active_record)
            if _string(active_record.status) == "retired":
                self._retire_stale_actors(
                    instance_id=active_record.instance_id,
                    active_agent_ids=set(),
                )
                self._retire_instance_overrides(instance_id=active_record.instance_id)
                self._retire_instance_runtimes(
                    instance_id=active_record.instance_id,
                    reason=f"Industry instance '{active_record.instance_id}' is retired.",
                )
                self._delete_instance_thread_bindings(active_record.instance_id)
                self._retire_strategy_memory(active_record)
                continue
            self._sync_strategy_memory(
                active_record,
                profile=normalized_profile,
                team=normalized_team,
                execution_core_identity=IndustryExecutionCoreIdentity.model_validate(
                    normalized_execution_core_identity,
                ),
            )
            for agent in normalized_team.agents:
                self._normalize_agent_override_surface(
                    instance_id=active_record.instance_id,
                    agent=agent,
                )
                override = self._agent_profile_override_repository.get_override(agent.agent_id)
                self._sync_actor_runtime_surface(
                    agent=agent,
                    instance_id=active_record.instance_id,
                    owner_scope=active_record.owner_scope,
                    goal_id=_string(override.current_focus_id) if override is not None else None,
                    goal_title=_string(override.current_focus) if override is not None else None,
                    status=_string(override.status) if override is not None else "idle",
                )
            self._retire_stale_actors(
                instance_id=active_record.instance_id,
                active_agent_ids={agent.agent_id for agent in normalized_team.agents},
            )
            self._normalize_schedule_surfaces(
                instance_id=active_record.instance_id,
                team=normalized_team,
            )

    def _normalize_agent_override_surface(
        self,
        *,
        instance_id: str,
        agent: IndustryRoleBlueprint,
    ) -> None:
        override = self._agent_profile_override_repository.get_override(agent.agent_id)
        if override is None:
            return
        if is_execution_core_agent_id(agent.agent_id):
            if _string(override.industry_instance_id) or _string(override.industry_role_id):
                self._agent_profile_override_repository.delete_override(agent.agent_id)
            return
        update = {
            "name": agent.name,
            "role_name": agent.role_name,
            "role_summary": agent.role_summary,
            "agent_class": agent.agent_class,
            "employment_mode": agent.employment_mode,
            "activation_mode": agent.activation_mode,
            "suspendable": agent.suspendable,
            "reports_to": agent.reports_to,
            "mission": agent.mission,
            "risk_level": agent.risk_level,
            "industry_instance_id": instance_id,
            "industry_role_id": agent.role_id,
            "environment_summary": "; ".join(agent.environment_constraints),
            "environment_constraints": list(agent.environment_constraints),
            "evidence_expectations": list(agent.evidence_expectations),
            "capabilities": list(agent.allowed_capabilities),
        }
        if all(getattr(override, key) == value for key, value in update.items()):
            return
        self._agent_profile_override_repository.upsert_override(
            override.model_copy(update=update),
        )

    def _normalize_schedule_surfaces(
        self,
        *,
        instance_id: str,
        team: IndustryTeamBlueprint,
    ) -> None:
        if self._schedule_repository is None:
            return
        execution_core_agent_ids = {
            agent.agent_id
            for agent in team.agents
            if is_execution_core_role_id(agent.role_id)
        }
        if not execution_core_agent_ids:
            return
        for schedule in self._schedule_repository.list_schedules():
            if schedule.status == "deleted":
                continue
            spec_payload = dict(schedule.spec_payload or {})
            meta_mapping = (
                dict(spec_payload.get("meta"))
                if isinstance(spec_payload.get("meta"), dict)
                else {}
            )
            if _string(meta_mapping.get("industry_instance_id")) != instance_id:
                continue
            owner_agent_id = _string(meta_mapping.get("owner_agent_id"))
            role_id = normalize_industry_role_id(_string(meta_mapping.get("industry_role_id")))
            if not is_execution_core_role_id(role_id) and owner_agent_id not in execution_core_agent_ids:
                continue
            normalized_title = _normalize_execution_core_schedule_title(schedule.title) or schedule.title
            normalized_summary = _normalize_execution_core_schedule_summary(
                meta_mapping.get("summary"),
            )
            dispatch_payload = (
                dict(spec_payload.get("dispatch"))
                if isinstance(spec_payload.get("dispatch"), dict)
                else {}
            )
            dispatch_meta = (
                dict(dispatch_payload.get("meta"))
                if isinstance(dispatch_payload.get("meta"), dict)
                else {}
            )
            normalized_owner_agent_id = EXECUTION_CORE_AGENT_ID
            changed = (
                normalized_title != schedule.title
                or normalized_summary != _string(meta_mapping.get("summary"))
                or _string(meta_mapping.get("owner_agent_id")) != normalized_owner_agent_id
                or _string(meta_mapping.get("industry_role_id")) != EXECUTION_CORE_ROLE_ID
            )
            if not changed and normalized_summary == _string(dispatch_meta.get("summary")):
                continue
            if normalized_summary:
                meta_mapping["summary"] = normalized_summary
                spec_payload["meta"] = meta_mapping
                dispatch_meta["summary"] = normalized_summary
                dispatch_payload["meta"] = dispatch_meta
                spec_payload["dispatch"] = dispatch_payload
            meta_mapping["owner_agent_id"] = normalized_owner_agent_id
            meta_mapping["industry_role_id"] = EXECUTION_CORE_ROLE_ID
            spec_payload["meta"] = meta_mapping
            dispatch_meta["owner_agent_id"] = normalized_owner_agent_id
            dispatch_meta["industry_role_id"] = EXECUTION_CORE_ROLE_ID
            spec_payload["dispatch"] = {
                **dispatch_payload,
                "meta": dispatch_meta,
            }
            self._schedule_repository.upsert_schedule(
                schedule.model_copy(
                    update={
                        "title": normalized_title,
                        "spec_payload": spec_payload,
                    },
                ),
            )

