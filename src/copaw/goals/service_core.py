# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403


class _GoalServiceCoreMixin:
    def __init__(
        self,
        *,
        repository: SqliteGoalRepository,
        override_repository: SqliteGoalOverrideRepository | None = None,
        compiler: SemanticCompiler | None = None,
        dispatcher: KernelDispatcher | None = None,
        task_repository: SqliteTaskRepository | None = None,
        task_runtime_repository: SqliteTaskRuntimeRepository | None = None,
        runtime_frame_repository: SqliteRuntimeFrameRepository | None = None,
        decision_request_repository: SqliteDecisionRequestRepository | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        learning_service: LearningService | None = None,
        strategy_memory_service: object | None = None,
        knowledge_service: object | None = None,
        memory_recall_service: object | None = None,
        agent_profile_service: object | None = None,
        industry_instance_repository: SqliteIndustryInstanceRepository | None = None,
        runtime_event_bus: object | None = None,
    ) -> None:
        self._repository = repository
        self._override_repository = override_repository
        self._compiler = compiler or SemanticCompiler()
        self._dispatcher = dispatcher
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._runtime_frame_repository = runtime_frame_repository
        self._decision_request_repository = decision_request_repository
        self._evidence_ledger = evidence_ledger
        self._learning_service = learning_service
        self._strategy_memory_service = strategy_memory_service
        self._knowledge_service = knowledge_service
        self._memory_recall_service = memory_recall_service
        self._agent_profile_service = agent_profile_service
        self._industry_instance_repository = industry_instance_repository
        self._runtime_event_bus = runtime_event_bus
        self._industry_service: object | None = None
        self._background_goal_execution_active_task_ids: set[str] = set()
        if dispatcher is not None:
            setter = getattr(dispatcher, "set_goal_service", None)
            if callable(setter):
                setter(self)

    def list_goals(
        self,
        *,
        status: str | None = None,
        owner_scope: str | None = None,
        industry_instance_id: str | None = None,
        limit: int | None = None,
    ) -> list[GoalRecord]:
        goals = [
            self._apply_override(goal)
            for goal in self._repository.list_goals(
                industry_instance_id=industry_instance_id,
                limit=(
                    limit
                    if status is None and owner_scope is None
                    else None
                ),
            )
        ]
        if status is not None:
            goals = [goal for goal in goals if goal.status == status]
        if owner_scope is not None:
            goals = [goal for goal in goals if goal.owner_scope == owner_scope]
        if industry_instance_id is not None:
            goals = [
                goal
                for goal in goals
                if goal.industry_instance_id == industry_instance_id
            ]
        if limit is not None:
            goals = goals[:limit]
        return goals

    def get_goal(self, goal_id: str) -> GoalRecord | None:
        goal = self._repository.get_goal(goal_id)
        if goal is None:
            return None
        return self._apply_override(goal)

    def create_goal(
        self,
        *,
        title: str,
        summary: str = "",
        status: str = "draft",
        priority: int = 0,
        owner_scope: str | None = None,
        industry_instance_id: str | None = None,
        lane_id: str | None = None,
        cycle_id: str | None = None,
        goal_class: str = "goal",
    ) -> GoalRecord:
        goal = GoalRecord(
            title=title,
            summary=summary,
            status=status,
            priority=priority,
            owner_scope=owner_scope,
            industry_instance_id=industry_instance_id,
            lane_id=lane_id,
            cycle_id=cycle_id,
            goal_class=goal_class,
        )
        created = self._repository.upsert_goal(goal)
        self._publish_runtime_event(
            topic="goal",
            action="created",
            payload={
                "goal_id": created.id,
                "status": created.status,
                "priority": created.priority,
                "owner_scope": created.owner_scope,
            },
        )
        return created

    def update_goal(
        self,
        goal_id: str,
        *,
        title: str | None = None,
        summary: str | None = None,
        status: str | None = None,
        priority: int | None = None,
        owner_scope: str | None = None,
        industry_instance_id: str | None = None,
        lane_id: str | None = None,
        cycle_id: str | None = None,
        goal_class: str | None = None,
    ) -> GoalRecord:
        goal = self._repository.get_goal(goal_id)
        if goal is None:
            raise KeyError(f"Goal '{goal_id}' not found")
        updates: dict[str, Any] = {"updated_at": _utc_now()}
        if title is not None:
            updates["title"] = title
        if summary is not None:
            updates["summary"] = summary
        if status is not None:
            updates["status"] = status
        if priority is not None:
            updates["priority"] = priority
        if owner_scope is not None:
            updates["owner_scope"] = owner_scope
        if industry_instance_id is not None:
            updates["industry_instance_id"] = industry_instance_id
        if lane_id is not None:
            updates["lane_id"] = lane_id
        if cycle_id is not None:
            updates["cycle_id"] = cycle_id
        if goal_class is not None:
            updates["goal_class"] = goal_class
        updated = goal.model_copy(update=updates)
        persisted = self._repository.upsert_goal(updated)
        self._publish_runtime_event(
            topic="goal",
            action="updated",
            payload={
                "goal_id": persisted.id,
                "status": persisted.status,
                "priority": persisted.priority,
                "owner_scope": persisted.owner_scope,
            },
        )
        return persisted

    def delete_goal(self, goal_id: str) -> bool:
        if self._override_repository is not None:
            self._override_repository.delete_override(goal_id)
        deleted = self._repository.delete_goal(goal_id)
        if deleted:
            self._publish_runtime_event(
                topic="goal",
                action="deleted",
                payload={"goal_id": goal_id},
            )
        return deleted

    def compile_goal(
        self,
        goal_id: str,
        *,
        context: dict[str, object] | None = None,
    ) -> list[CompiledTaskSpec]:
        goal = self.get_goal(goal_id)
        if goal is None:
            raise KeyError(f"Goal '{goal_id}' not found")
        unit, compiled_specs, kernel_tasks = self._compile_goal_bundle(
            goal,
            context=context,
        )
        self._persist_compiled_kernel_tasks(goal, unit=unit, kernel_tasks=kernel_tasks)
        self._publish_runtime_event(
            topic="goal",
            action="compiled",
            payload={
                "goal_id": goal.id,
                "compiled_task_count": len(kernel_tasks),
                "unit_id": unit.id,
            },
        )
        return compiled_specs

    def set_agent_profile_service(self, agent_profile_service: object | None) -> None:
        self._agent_profile_service = agent_profile_service

    def set_knowledge_service(self, knowledge_service: object | None) -> None:
        self._knowledge_service = knowledge_service

    def set_memory_recall_service(self, memory_recall_service: object | None) -> None:
        self._memory_recall_service = memory_recall_service

    def set_strategy_memory_service(
        self,
        strategy_memory_service: object | None,
    ) -> None:
        self._strategy_memory_service = strategy_memory_service

    def set_industry_instance_repository(
        self,
        industry_instance_repository: SqliteIndustryInstanceRepository | None,
    ) -> None:
        self._industry_instance_repository = industry_instance_repository

    def set_runtime_event_bus(self, runtime_event_bus: object | None) -> None:
        self._runtime_event_bus = runtime_event_bus

    def set_industry_service(self, industry_service: object | None) -> None:
        self._industry_service = industry_service

    def _goal_compiler_context(
        self,
        override: GoalOverrideRecord | None,
    ) -> dict[str, object]:
        if override is None or not isinstance(override.compiler_context, dict):
            return {}
        return dict(override.compiler_context)

    def _resolve_goal_runtime_context(
        self,
        goal: GoalRecord,
        *,
        override: GoalOverrideRecord | None = None,
    ) -> dict[str, object]:
        resolved_context: dict[str, object] = self._goal_compiler_context(override)
        resolver = getattr(self._industry_service, "_resolve_goal_runtime_context", None)
        if callable(resolver):
            try:
                industry_context = resolver(goal, override=override)
            except TypeError:
                industry_context = resolver(goal)
            if isinstance(industry_context, dict):
                for key, value in industry_context.items():
                    if value is None:
                        continue
                    resolved_context[key] = value
        for key, value in {
            "owner_scope": goal.owner_scope,
            "industry_instance_id": goal.industry_instance_id,
            "lane_id": goal.lane_id,
            "cycle_id": goal.cycle_id,
        }.items():
            if value is None:
                continue
            resolved_context[key] = value
        return resolved_context

    def get_goal_detail(self, goal_id: str) -> dict[str, object] | None:
        self.reconcile_goal_status(goal_id, source="detail")
        goal = self.get_goal(goal_id)
        if goal is None:
            return None

        tasks = (
            self._task_repository.list_tasks(goal_id=goal.id)
            if self._task_repository is not None
            else []
        )
        override = (
            self._override_repository.get_override(goal.id)
            if self._override_repository is not None
            else None
        )
        compilation = self._latest_persisted_compilation(goal.id, tasks=tasks)
        if compilation is None:
            unit = self._build_compilation_unit(goal, context=None)
            compiled_specs = self._compiler.compile(unit)
        else:
            unit = compilation["unit"]
            compiled_specs = compilation["specs"]

        task_entries: list[dict[str, object]] = []
        decision_map: dict[str, dict[str, object]] = {}
        evidence_map: dict[str, dict[str, object]] = {}
        agent_ids: set[str] = set()
        task_ids = [task.id for task in tasks]
        runtime_map = (
            {
                runtime.task_id: runtime
                for runtime in self._task_runtime_repository.list_runtimes(task_ids=task_ids)
            }
            if self._task_runtime_repository is not None and task_ids
            else {}
        )
        task_decisions: dict[str, list[object]] = {}
        if self._decision_request_repository is not None and task_ids:
            for decision in self._decision_request_repository.list_decision_requests(
                task_ids=task_ids,
            ):
                task_decisions.setdefault(decision.task_id, []).append(decision)

        for task in sorted(tasks, key=lambda item: item.updated_at, reverse=True):
            runtime = runtime_map.get(task.id)
            frames = (
                self._runtime_frame_repository.list_frames(task.id, limit=3)
                if self._runtime_frame_repository is not None
                else []
            )
            decisions = task_decisions.get(task.id, [])
            evidence = (
                self._evidence_ledger.list_by_task(task.id)
                if self._evidence_ledger is not None
                else []
            )
            if task.owner_agent_id:
                agent_ids.add(task.owner_agent_id)
            if runtime is not None and runtime.last_owner_agent_id:
                agent_ids.add(runtime.last_owner_agent_id)

            task_entries.append(
                {
                    "task": task.model_dump(mode="json"),
                    "runtime": (
                        runtime.model_dump(mode="json")
                        if runtime is not None
                        else None
                    ),
                    "frames": [frame.model_dump(mode="json") for frame in frames],
                    "decision_count": len(decisions),
                    "evidence_count": len(evidence),
                    "latest_evidence_id": (
                        evidence[-1].id
                        if evidence and evidence[-1].id is not None
                        else runtime.last_evidence_id
                        if runtime is not None
                        else None
                    ),
                }
            )

            for decision in decisions:
                decision_map[decision.id] = decision.model_dump(mode="json")
            for record in evidence:
                if record.id is None:
                    continue
                evidence_map[record.id] = _serialize_evidence_record(record)

        evidence_ids = set(evidence_map.keys())
        patches = self._collect_related_patches(goal.id, evidence_ids=evidence_ids)
        patch_ids = {patch["id"] for patch in patches if isinstance(patch.get("id"), str)}
        growth = self._collect_related_growth(
            evidence_ids=evidence_ids,
            patch_ids=patch_ids,
            agent_ids=agent_ids,
        )
        agents = self._collect_related_agents(agent_ids)

        decisions = sorted(
            decision_map.values(),
            key=lambda item: item.get("created_at") or "",
            reverse=True,
        )
        evidence = sorted(
            evidence_map.values(),
            key=lambda item: item.get("created_at") or "",
            reverse=True,
        )
        industry_context = self._resolve_goal_runtime_context(
            goal,
            override=override,
        )
        industry_instance_id = _string(industry_context.get("industry_instance_id"))

        return {
            "goal": goal.model_dump(mode="json"),
            "override": (
                override.model_dump(mode="json")
                if override is not None
                else None
            ),
            "compilation": {
                "unit": unit.model_dump(mode="json"),
                "specs": [spec.model_dump(mode="json") for spec in compiled_specs],
            },
            "agents": agents,
            "tasks": task_entries,
            "decisions": decisions,
            "evidence": evidence,
            "patches": patches,
            "growth": growth,
            "stats": {
                "task_count": len(task_entries),
                "decision_count": len(decisions),
                "evidence_count": len(evidence),
                "patch_count": len(patches),
                "growth_count": len(growth),
                "agent_count": len(agents),
            },
            "industry": self._resolve_industry_payload(
                industry_context,
                industry_instance_id=industry_instance_id,
            ),
        }

    def _resolve_industry_payload(
        self,
        compiler_context: dict[str, object] | None,
        *,
        industry_instance_id: object,
    ) -> dict[str, object] | None:
        if not isinstance(industry_instance_id, str) or not industry_instance_id:
            return None
        role_id = None
        owner_agent_id = None
        if isinstance(compiler_context, dict):
            raw_role_id = compiler_context.get("industry_role_id")
            if isinstance(raw_role_id, str) and raw_role_id.strip():
                role_id = raw_role_id.strip()
            raw_owner_agent_id = compiler_context.get("owner_agent_id")
            if isinstance(raw_owner_agent_id, str) and raw_owner_agent_id.strip():
                owner_agent_id = raw_owner_agent_id.strip()
        route = f"/api/runtime-center/industry/{industry_instance_id}"
        if self._industry_instance_repository is None:
            return {
                "instance_id": industry_instance_id,
                "route": route,
                "role": {"role_id": role_id} if role_id else None,
                "execution_core_identity": (
                    {"role_id": "execution-core"}
                    if is_execution_core_role_id(role_id)
                    else None
                ),
            }
        record = self._industry_instance_repository.get_instance(industry_instance_id)
        if record is None:
            return {
                "instance_id": industry_instance_id,
                "route": route,
                "role": {"role_id": role_id} if role_id else None,
                "execution_core_identity": (
                    {"role_id": "execution-core"}
                    if is_execution_core_role_id(role_id)
                    else None
                ),
            }
        team_payload = dict(record.team_payload or {})
        execution_core_identity = dict(record.execution_core_identity_payload or {})
        role_payload: dict[str, object] | None = None
        agents = team_payload.get("agents")
        if isinstance(agents, list):
            for item in agents:
                if not isinstance(item, dict):
                    continue
                if role_id and item.get("role_id") == role_id:
                    role_payload = dict(item)
                    break
                if owner_agent_id and item.get("agent_id") == owner_agent_id:
                    role_payload = dict(item)
                    break
        if (
            role_payload is None
            and execution_core_identity
            and is_execution_core_role_id(role_id)
        ):
            role_payload = {
                "role_id": execution_core_identity.get("role_id"),
                "agent_id": execution_core_identity.get("agent_id"),
                "role_name": execution_core_identity.get("role_name"),
                "role_summary": execution_core_identity.get("role_summary"),
                "mission": execution_core_identity.get("mission"),
            }
        return {
            "instance_id": industry_instance_id,
            "label": record.label,
            "route": route,
            "profile": dict(record.profile_payload or {}),
            "team": team_payload,
            "role": role_payload or ({"role_id": role_id} if role_id else None),
            "execution_core_identity": execution_core_identity or None,
            "strategy_memory": self._resolve_strategy_memory_payload(
                industry_instance_id=industry_instance_id,
                owner_agent_id=owner_agent_id,
                role_id=role_id,
            ),
        }
