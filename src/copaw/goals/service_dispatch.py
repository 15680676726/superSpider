# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403


class _GoalServiceDispatchMixin:
    async def compile_goal_dispatch(
        self,
        goal_id: str,
        *,
        context: dict[str, object] | None = None,
        owner_agent_id: str | None = None,
        activate: bool = True,
    ) -> dict[str, object]:
        return await self._dispatch_goal(
            goal_id,
            context=context,
            owner_agent_id=owner_agent_id,
            execute=False,
            execute_background=False,
            activate=activate,
            schedule_background_execution=True,
        )

    async def dispatch_goal_execute_now(
        self,
        goal_id: str,
        *,
        context: dict[str, object] | None = None,
        owner_agent_id: str | None = None,
        activate: bool = True,
    ) -> dict[str, object]:
        return await self._dispatch_goal(
            goal_id,
            context=context,
            owner_agent_id=owner_agent_id,
            execute=True,
            execute_background=False,
            activate=activate,
            schedule_background_execution=True,
        )

    async def dispatch_goal_background(
        self,
        goal_id: str,
        *,
        context: dict[str, object] | None = None,
        owner_agent_id: str | None = None,
        activate: bool = True,
    ) -> dict[str, object]:
        return await self._dispatch_goal(
            goal_id,
            context=context,
            owner_agent_id=owner_agent_id,
            execute=True,
            execute_background=True,
            activate=activate,
            schedule_background_execution=True,
        )

    async def dispatch_goal_deferred_background(
        self,
        goal_id: str,
        *,
        context: dict[str, object] | None = None,
        owner_agent_id: str | None = None,
        activate: bool = True,
    ) -> dict[str, object]:
        return await self._dispatch_goal(
            goal_id,
            context=context,
            owner_agent_id=owner_agent_id,
            execute=True,
            execute_background=True,
            activate=activate,
            schedule_background_execution=False,
        )

    async def _dispatch_goal(
        self,
        goal_id: str,
        *,
        context: dict[str, object] | None = None,
        owner_agent_id: str | None = None,
        execute: bool = False,
        execute_background: bool = False,
        activate: bool = True,
        schedule_background_execution: bool = True,
    ) -> dict[str, object]:
        goal = self.get_goal(goal_id)
        if goal is None:
            raise KeyError(f"Goal '{goal_id}' not found")
        dispatcher = self._dispatcher
        if dispatcher is None:
            raise RuntimeError("Kernel dispatcher is not wired for goal dispatch")

        resolved_owner_agent_id = (
            owner_agent_id.strip()
            if isinstance(owner_agent_id, str) and owner_agent_id.strip()
            else None
        )
        trigger_context = self._resolve_dispatch_trigger_context(
            context=context,
            owner_agent_id=resolved_owner_agent_id,
        )
        if activate and goal.status != "active":
            goal = self._repository.upsert_goal(
                goal.model_copy(update={"status": "active", "updated_at": _utc_now()}),
            )

        compile_context = {
            **(context or {}),
            "goal_id": goal.id,
            **trigger_context,
        }
        if resolved_owner_agent_id is not None:
            compile_context["owner_agent_id"] = resolved_owner_agent_id
        unit, _compiled_specs, kernel_tasks = self._compile_goal_bundle(
            goal,
            context=compile_context,
        )
        self._persist_compiled_kernel_tasks(goal, unit=unit, kernel_tasks=kernel_tasks)

        background_task_ids: list[str] = []
        results: list[dict[str, object]] = []
        for task in kernel_tasks:
            if task.goal_id is None:
                task = task.model_copy(update={"goal_id": goal.id})
            execution_result: KernelResult | None = None
            admitted: KernelResult | None = None
            if execute and execute_background:
                background_task_ids.append(task.id)
            elif execute:
                admitted = dispatcher.submit(task)
                if admitted.phase == "executing":
                    try:
                        execution_result = await dispatcher.execute_task(task.id)
                    except Exception as exc:  # pragma: no cover - safeguard
                        logger.exception("Goal task execution failed: %s", task.id)
                        execution_result = dispatcher.fail_task(
                            task.id,
                            error=str(exc),
                        )
            results.append(
                {
                    "task_id": task.id,
                    "capability_ref": task.capability_ref,
                    "phase": (
                        execution_result.phase
                        if execution_result is not None
                        else admitted.phase
                        if admitted is not None
                        else "compiled"
                    ),
                    "summary": (
                        execution_result.summary
                        if execution_result is not None
                        else admitted.summary
                        if admitted is not None
                        else (
                            "Scheduled for background goal execution."
                            if execute and execute_background
                            else "Compiled goal task and left it pending dispatch."
                        )
                    ),
                    "decision_request_id": (
                        admitted.decision_request_id if admitted is not None else None
                    ),
                    "executed": execution_result is not None,
                    "scheduled_execution": (
                        execute_background
                        and execution_result is None
                        and admitted is None
                    ),
                },
            )

        if background_task_ids:
            self._record_background_goal_chain(
                goal_id=goal.id,
                unit_id=unit.id,
                task_ids=background_task_ids,
            )
        else:
            self._clear_background_goal_chain(goal.id)
        if background_task_ids and schedule_background_execution:
            self._schedule_background_goal_execution(
                goal_id=goal.id,
                task_ids=background_task_ids,
            )
        payload = {
            "goal": goal.model_dump(mode="json"),
            "compiled_tasks": [task.model_dump(mode="json") for task in kernel_tasks],
            "dispatch_results": results,
        }
        self._record_goal_dispatch_state(
            goal.id,
            trigger_context=trigger_context,
            results=results,
        )
        self._publish_runtime_event(
            topic="goal",
            action="dispatched",
            payload={
                "goal_id": goal.id,
                "compiled_task_count": len(kernel_tasks),
                "execute": execute,
                "execute_background": execute_background,
                "trigger_source": trigger_context["trigger_source"],
                "trigger_actor": trigger_context["trigger_actor"],
                "waiting_confirm_count": sum(
                    1 for item in results if item.get("phase") == "waiting-confirm"
                ),
            },
        )
        return payload

    def release_deferred_goal_dispatch(
        self,
        *,
        goal_id: str,
        dispatch_results: list[dict[str, object]] | None,
    ) -> None:
        task_ids = [
            str(item.get("task_id"))
            for item in list(dispatch_results or [])
            if item.get("scheduled_execution") is True and item.get("task_id")
        ]
        self._schedule_background_goal_execution(goal_id=goal_id, task_ids=task_ids)

    def _resolve_dispatch_trigger_context(
        self,
        *,
        context: dict[str, object] | None,
        owner_agent_id: str | None,
    ) -> dict[str, object]:
        resolved_context = dict(context or {})
        source = self._dispatch_trigger_source(resolved_context)
        actor = (
            str(
                resolved_context.get("trigger_actor")
                or resolved_context.get("actor")
                or owner_agent_id
                or "system",
            ).strip()
            or "system"
        )
        reason = (
            str(
                resolved_context.get("trigger_reason")
                or resolved_context.get("dispatch_reason")
                or resolved_context.get("reason")
                or "",
            ).strip()
            or None
        )
        return {
            "trigger_source": source,
            "trigger_actor": actor,
            "trigger_reason": reason,
            "dispatch_requested_at": _utc_now().isoformat(),
        }

    def _dispatch_trigger_source(self, context: dict[str, object] | None) -> str:
        resolved_context = dict(context or {})
        source = str(
            resolved_context.get("trigger_source")
            or resolved_context.get("dispatch_source")
            or resolved_context.get("source")
            or "manual:goal-dispatch",
        ).strip()
        return source or "manual:goal-dispatch"

    def _record_goal_dispatch_state(
        self,
        goal_id: str,
        *,
        trigger_context: dict[str, object],
        results: list[dict[str, object]],
    ) -> None:
        first_phase = next(
            (
                str(item.get("phase") or "").strip()
                for item in results
                if str(item.get("phase") or "").strip()
            ),
            "pending",
        )
        first_summary = next(
            (
                str(item.get("summary") or "").strip()
                for item in results
                if str(item.get("summary") or "").strip()
            ),
            "",
        )
        self._update_goal_compiler_context(
            goal_id,
            updater=lambda compiler_context: {
                **compiler_context,
                "dispatch_state": {
                    **_mapping(compiler_context.get("dispatch_state")),
                    "last_dispatch_at": _utc_now().isoformat(),
                    "last_trigger_source": trigger_context.get("trigger_source"),
                    "last_trigger_actor": trigger_context.get("trigger_actor"),
                    "last_trigger_reason": trigger_context.get("trigger_reason"),
                    "last_result_phase": first_phase,
                    "last_result_summary": first_summary or None,
                },
            },
            reason="Goal dispatch metadata",
        )

    def _update_goal_compiler_context(
        self,
        goal_id: str,
        *,
        updater,
        reason: str,
    ) -> None:
        if self._override_repository is None:
            return
        current = self._override_repository.get_override(goal_id)
        current_context = (
            dict(current.compiler_context)
            if current is not None and isinstance(current.compiler_context, dict)
            else {}
        )
        next_context = updater(current_context)
        if not isinstance(next_context, dict):
            next_context = current_context
        if current is not None:
            self._override_repository.upsert_override(
                current.model_copy(
                    update={
                        "compiler_context": next_context,
                        "reason": reason or current.reason,
                        "updated_at": _utc_now(),
                    },
                ),
            )
            return
        self._override_repository.upsert_override(
            GoalOverrideRecord(
                goal_id=goal_id,
                compiler_context=next_context,
                reason=reason,
            ),
        )

    def _background_chain_state(self, goal_id: str) -> dict[str, object]:
        if self._override_repository is None:
            return {}
        override = self._override_repository.get_override(goal_id)
        if override is None or not isinstance(override.compiler_context, dict):
            return {}
        return _mapping(override.compiler_context.get("background_chain"))

    def _record_background_goal_chain(
        self,
        goal_id: str,
        *,
        unit_id: str,
        task_ids: list[str],
    ) -> None:
        if self._override_repository is None:
            return
        resolved_task_ids = [
            task_id
            for task_id in dict.fromkeys(task_ids)
            if isinstance(task_id, str) and task_id.strip()
        ]
        if not resolved_task_ids or not unit_id:
            self._clear_background_goal_chain(goal_id)
            return
        now = _utc_now().isoformat()
        self._update_goal_compiler_context(
            goal_id,
            updater=lambda compiler_context: {
                **compiler_context,
                "background_chain": {
                    "unit_id": unit_id,
                    "task_ids": resolved_task_ids,
                    "auto_continue": True,
                    "updated_at": now,
                },
            },
            reason="Goal background execution chain",
        )

    def _clear_background_goal_chain(self, goal_id: str) -> None:
        if self._override_repository is None:
            return
        current = self._override_repository.get_override(goal_id)
        if current is None or not isinstance(current.compiler_context, dict):
            return
        if "background_chain" not in current.compiler_context:
            return
        next_context = dict(current.compiler_context)
        next_context.pop("background_chain", None)
        self._override_repository.upsert_override(
            current.model_copy(
                update={
                    "compiler_context": next_context,
                    "reason": "Goal background execution chain cleared",
                    "updated_at": _utc_now(),
                },
            ),
        )

    def _latest_background_chain_task_ids(
        self,
        goal_id: str,
        *,
        tasks: list[TaskRecord] | None = None,
    ) -> list[str]:
        chain_state = self._background_chain_state(goal_id)
        if chain_state.get("auto_continue") is not True:
            return []
        configured_task_ids = set(_string_list(chain_state.get("task_ids")))
        configured_unit_id = str(chain_state.get("unit_id") or "").strip()
        if not configured_task_ids or not configured_unit_id:
            return []
        latest = self._latest_persisted_compilation(goal_id, tasks=tasks)
        if latest is None:
            return []
        unit = latest.get("unit")
        if not isinstance(unit, CompilationUnit) or unit.id != configured_unit_id:
            return []
        specs = latest.get("specs")
        if not isinstance(specs, list):
            return []
        ordered_task_ids: list[str] = []
        for spec in specs:
            if not isinstance(spec, CompiledTaskSpec):
                continue
            task_id = str(spec.task_id or "").strip()
            if not task_id or task_id not in configured_task_ids:
                continue
            ordered_task_ids.append(task_id)
        return ordered_task_ids

    def _background_chain_has_staged_followups(
        self,
        *,
        ordered_task_ids: list[str],
        tasks_by_id: dict[str, TaskRecord],
        runtimes_by_task_id: dict[str, TaskRuntimeRecord],
    ) -> bool:
        has_progress = False
        has_staged_followups = False
        for task_id in ordered_task_ids:
            task = tasks_by_id.get(task_id)
            if task is None:
                continue
            runtime = runtimes_by_task_id.get(task_id)
            phase = str(getattr(runtime, "current_phase", "") or "").strip().lower()
            runtime_status = str(getattr(runtime, "runtime_status", "") or "").strip().lower()
            if (
                task.status == "created"
                and phase in {"", "compiled"}
                and runtime_status in {"", "cold"}
            ):
                has_staged_followups = True
                continue
            has_progress = True
        return has_progress and has_staged_followups

    def resume_background_goal_chain_for_task(self, task_id: str) -> None:
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return
        if normalized_task_id in self._background_goal_execution_active_task_ids:
            return
        if self._task_repository is None or self._dispatcher is None:
            return
        task = self._task_repository.get_task(normalized_task_id)
        if task is None or not task.goal_id:
            return
        runtime = (
            self._task_runtime_repository.get_runtime(normalized_task_id)
            if self._task_runtime_repository is not None
            else None
        )
        if self._goal_task_terminal_outcome(task=task, runtime=runtime) != "completed":
            return
        tasks = self._task_repository.list_tasks(goal_id=task.goal_id)
        ordered_task_ids = self._latest_background_chain_task_ids(
            task.goal_id,
            tasks=tasks,
        )
        if not ordered_task_ids or normalized_task_id not in ordered_task_ids:
            return
        current_index = ordered_task_ids.index(normalized_task_id)
        tasks_by_id = {item.id: item for item in tasks}
        task_ids = [task_id for task_id in ordered_task_ids if task_id in tasks_by_id]
        runtimes_by_task_id = (
            {
                runtime.task_id: runtime
                for runtime in self._task_runtime_repository.list_runtimes(task_ids=task_ids)
            }
            if self._task_runtime_repository is not None and task_ids
            else {}
        )
        remaining_task_ids: list[str] = []
        for index, ordered_task_id in enumerate(ordered_task_ids):
            ordered_task = tasks_by_id.get(ordered_task_id)
            if ordered_task is None:
                continue
            ordered_runtime = runtimes_by_task_id.get(ordered_task_id)
            outcome = self._goal_task_terminal_outcome(
                task=ordered_task,
                runtime=ordered_runtime,
            )
            if index <= current_index:
                if outcome != "completed":
                    return
                continue
            if outcome is not None:
                if outcome != "completed":
                    return
                continue
            phase = str(getattr(ordered_runtime, "current_phase", "") or "").strip().lower()
            runtime_status = str(
                getattr(ordered_runtime, "runtime_status", "") or "",
            ).strip().lower()
            if ordered_task.status != "created":
                return
            if phase not in {"", "compiled"} or runtime_status not in {"", "cold"}:
                return
            remaining_task_ids.append(ordered_task_id)
        if not remaining_task_ids:
            return
        self._schedule_background_goal_execution(
            goal_id=task.goal_id,
            task_ids=remaining_task_ids,
        )

    def reconcile_goal_status(
        self,
        goal_id: str,
        *,
        source: str = "task-state",
    ) -> GoalRecord | None:
        goal = self._repository.get_goal(goal_id)
        if goal is None or goal.status == "archived":
            return self.get_goal(goal_id) if goal is not None else None
        if self._task_repository is None:
            return self.get_goal(goal_id)
        tasks = self._task_repository.list_tasks(goal_id=goal_id)
        if not tasks:
            return self.get_goal(goal_id)
        tasks = self._effective_reconciliation_tasks(goal_id=goal_id, tasks=tasks)
        if not tasks:
            return self.get_goal(goal_id)

        task_ids = [task.id for task in tasks]
        runtimes = (
            {
                runtime.task_id: runtime
                for runtime in self._task_runtime_repository.list_runtimes(task_ids=task_ids)
            }
            if self._task_runtime_repository is not None and task_ids
            else {}
        )
        outcomes = [
            self._goal_task_terminal_outcome(task=task, runtime=runtimes.get(task.id))
            for task in tasks
        ]
        has_nonterminal = any(outcome is None for outcome in outcomes)
        next_status: str | None = None
        if has_nonterminal:
            if goal.status in {"completed", "blocked"}:
                next_status = "active"
        elif any(outcome in {"failed", "cancelled"} for outcome in outcomes):
            next_status = "blocked"
        elif outcomes and all(outcome == "completed" for outcome in outcomes):
            latest_compilation = self._latest_persisted_compilation(
                goal_id,
                tasks=tasks,
            )
            latest_specs = (
                list(latest_compilation.get("specs") or [])
                if isinstance(latest_compilation, dict)
                else []
            )
            latest_step_number = max(
                (
                    int(spec.payload.get("plan_step_number"))
                    for spec in latest_specs
                    if isinstance(spec.payload, dict)
                    and spec.payload.get("plan_step_number") is not None
                ),
                default=0,
            )
            latest_step_total = max(
                (
                    int(spec.payload.get("plan_step_total"))
                    for spec in latest_specs
                    if isinstance(spec.payload, dict)
                    and spec.payload.get("plan_step_total") is not None
                ),
                default=0,
            )
            if latest_step_total > 0 and latest_step_number < latest_step_total:
                next_status = "active"
            else:
                next_status = "completed"

        if next_status is None or next_status == goal.status:
            return self.get_goal(goal_id)

        persisted = self._repository.upsert_goal(
            goal.model_copy(update={"status": next_status, "updated_at": _utc_now()}),
        )
        self._publish_runtime_event(
            topic="goal",
            action="reconciled",
            payload={
                "goal_id": persisted.id,
                "source": source,
                "status": persisted.status,
                "previous_status": goal.status,
            },
        )
        self._notify_industry_goal_status_change(goal_id=goal_id)
        return self._apply_override(persisted)

    def _effective_reconciliation_tasks(
        self,
        *,
        goal_id: str,
        tasks: list[TaskRecord],
    ) -> list[TaskRecord]:
        latest = self._latest_persisted_compilation(goal_id, tasks=tasks)
        latest_unit_id = (
            latest["unit"].id
            if latest is not None and isinstance(latest.get("unit"), CompilationUnit)
            else None
        )
        if not latest_unit_id:
            return tasks

        effective: list[TaskRecord] = []
        for task in tasks:
            compiler_meta = _task_compiler_meta(task)
            if compiler_meta.get("source_kind") != "compiler":
                effective.append(task)
                continue
            if compiler_meta.get("unit_id") == latest_unit_id:
                effective.append(task)
        return effective

    def reconcile_goal_statuses(
        self,
        *,
        statuses: set[str] | None = None,
    ) -> list[GoalRecord]:
        reconciled: list[GoalRecord] = []
        for goal in self.list_goals():
            if statuses is not None and goal.status not in statuses:
                continue
            updated = self.reconcile_goal_status(goal.id)
            if updated is not None:
                reconciled.append(updated)
        return reconciled

    def _schedule_background_goal_execution(
        self,
        *,
        goal_id: str,
        task_ids: list[str],
    ) -> None:
        dispatcher = self._dispatcher
        if dispatcher is None or not task_ids:
            return

        managed_task_ids = tuple(
            task_id
            for task_id in dict.fromkeys(task_ids)
            if isinstance(task_id, str) and task_id.strip()
        )
        if not managed_task_ids:
            return

        async def _run() -> None:
            self._background_goal_execution_active_task_ids.update(managed_task_ids)
            try:
                for task_id in managed_task_ids:
                    try:
                        task = dispatcher.lifecycle.get_task(task_id)
                        if task is None:
                            logger.warning(
                                "Background goal task missing from kernel store: goal=%s task=%s",
                                goal_id,
                                task_id,
                            )
                            continue
                        if task.phase in {"completed", "failed", "cancelled"}:
                            continue
                        if task.phase == "waiting-confirm":
                            logger.info(
                                "Background goal task is waiting for confirmation; pausing goal chain: goal=%s task=%s",
                                goal_id,
                                task_id,
                            )
                            break
                        if task.phase != "executing":
                            admitted = dispatcher.submit(
                                task.model_copy(
                                    update={
                                        "phase": "pending",
                                        "updated_at": _utc_now(),
                                    },
                                ),
                            )
                            if admitted.phase == "waiting-confirm":
                                logger.info(
                                    "Background goal task entered confirmation gate; pausing goal chain: goal=%s task=%s",
                                    goal_id,
                                    task_id,
                                )
                                break
                            if admitted.phase != "executing":
                                logger.warning(
                                    "Background goal task was not admitted for execution: goal=%s task=%s phase=%s summary=%s",
                                    goal_id,
                                    task_id,
                                    admitted.phase,
                                    admitted.summary,
                                )
                                break
                            self._notify_industry_goal_status_change(goal_id=goal_id)
                        execution_result = await dispatcher.execute_task(task_id)
                        self._notify_industry_goal_status_change(goal_id=goal_id)
                        if execution_result.phase != "completed":
                            logger.warning(
                                "Background goal task did not complete cleanly; pausing remaining goal chain: goal=%s task=%s phase=%s summary=%s",
                                goal_id,
                                task_id,
                                execution_result.phase,
                                execution_result.summary,
                            )
                            break
                    except Exception as exc:  # pragma: no cover - safeguard
                        logger.exception(
                            "Background goal task execution failed: goal=%s task=%s",
                            goal_id,
                            task_id,
                        )
                        dispatcher.fail_task(task_id, error=str(exc))
            finally:
                for task_id in managed_task_ids:
                    self._background_goal_execution_active_task_ids.discard(task_id)

        asyncio.create_task(_run())
