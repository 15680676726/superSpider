# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403


class _GoalServiceCompilerMixin:
    def _goal_step_index_from_meta(self, value: object) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, int):
            return value
        text = str(value).strip()
        if not text:
            return None
        try:
            return int(float(text))
        except ValueError:
            return None

    def _goal_task_terminal_outcome(
        self,
        *,
        task: TaskRecord,
        runtime: TaskRuntimeRecord | None,
    ) -> str | None:
        phase = str(getattr(runtime, "current_phase", "") or "").strip().lower()
        if phase in _GOAL_TERMINAL_TASK_STATUSES:
            return phase
        status = str(getattr(task, "status", "") or "").strip().lower()
        if status in _GOAL_TERMINAL_TASK_STATUSES:
            return status
        return None

    def _notify_industry_goal_status_change(self, *, goal_id: str) -> None:
        if self._industry_service is None:
            return
        resolver = getattr(self._industry_service, "reconcile_instance_status_for_goal", None)
        if callable(resolver):
            resolver(goal_id)

    def _resolve_next_goal_step_index(
        self,
        goal: GoalRecord,
        *,
        total_steps: int,
    ) -> int:
        if total_steps <= 0 or self._task_repository is None:
            return 0
        tasks = self._task_repository.list_tasks(goal_id=goal.id)
        if not tasks:
            return 0
        runtimes_by_task_id = (
            {
                runtime.task_id: runtime
                for runtime in self._task_runtime_repository.list_runtimes(
                    task_ids=[task.id for task in tasks],
                )
            }
            if self._task_runtime_repository is not None
            else {}
        )
        latest_sort_key = ""
        latest_step_index: int | None = None
        latest_outcome: str | None = None
        for task in tasks:
            compiler_meta = _task_compiler_meta(task)
            if compiler_meta.get("source_kind") != "compiler":
                continue
            step_index = self._goal_step_index_from_meta(compiler_meta.get("step_index"))
            if step_index is None:
                step_number = self._goal_step_index_from_meta(
                    compiler_meta.get("plan_step_number"),
                )
                if step_number is not None:
                    step_index = max(0, step_number - 1)
            if step_index is None:
                continue
            compiled_at = _string(compiler_meta.get("compiled_at")) or ""
            sort_key = f"{compiled_at}|{task.updated_at.isoformat()}|{task.id}"
            if sort_key <= latest_sort_key:
                continue
            latest_sort_key = sort_key
            latest_step_index = step_index
            latest_outcome = self._goal_task_terminal_outcome(
                task=task,
                runtime=runtimes_by_task_id.get(task.id),
            )
        if latest_step_index is None:
            return 0
        if latest_outcome == "completed":
            return min(latest_step_index + 1, total_steps)
        return min(max(latest_step_index, 0), max(total_steps - 1, 0))

    def _compile_goal_bundle(
        self,
        goal: GoalRecord,
        *,
        context: dict[str, object] | None,
    ) -> tuple[CompilationUnit, list[CompiledTaskSpec], list[KernelTask]]:
        unit = self._build_compilation_unit(goal, context=context).model_copy(
            update={"compiled_at": _utc_now()},
        )
        compiled_specs = self._compiler.compile(unit)
        kernel_tasks = self._compiler.compile_to_kernel_tasks(unit, specs=compiled_specs)
        return unit, compiled_specs, kernel_tasks

    def _persist_compiled_kernel_tasks(
        self,
        goal: GoalRecord,
        *,
        unit: CompilationUnit,
        kernel_tasks: list[KernelTask],
    ) -> None:
        if self._task_repository is None:
            return
        self._cancel_superseded_compiler_tasks(goal.id, current_unit_id=unit.id)
        compiled_at = unit.compiled_at or _utc_now()
        unit_context = dict(unit.context or {})
        industry_instance_id = (
            _string(unit_context.get("industry_instance_id")) or goal.industry_instance_id
        )
        lane_id = _string(unit_context.get("lane_id")) or goal.lane_id
        cycle_id = _string(unit_context.get("cycle_id")) or goal.cycle_id
        assignment_id = _string(unit_context.get("assignment_id"))
        report_back_mode = (
            _string(unit_context.get("report_back_mode"))
            or _string(unit_context.get("task_mode"))
            or "summary"
        )
        for task in kernel_tasks:
            existing_task = self._task_repository.get_task(task.id)
            encoded_meta = encode_kernel_task_metadata(
                task,
                existing_acceptance_criteria=(
                    existing_task.acceptance_criteria
                    if existing_task is not None
                    else None
                ),
            )
            record = (
                existing_task.model_copy(
                    update={
                        "goal_id": task.goal_id or goal.id,
                        "title": task.title,
                        "summary": _compiler_task_summary(task),
                        "task_type": task.capability_ref or "system:dispatch_query",
                        "status": "created",
                        "priority": max(goal.priority, existing_task.priority),
                        "owner_agent_id": task.owner_agent_id,
                        "seed_source": _compiler_seed_source(task),
                        "constraints_summary": _compiler_constraints_summary(task),
                        "acceptance_criteria": encoded_meta,
                        "current_risk_level": task.risk_level,
                        "industry_instance_id": industry_instance_id,
                        "assignment_id": assignment_id,
                        "lane_id": lane_id,
                        "cycle_id": cycle_id,
                        "report_back_mode": report_back_mode,
                        "updated_at": compiled_at,
                    },
                )
                if existing_task is not None
                else TaskRecord(
                    id=task.id,
                    goal_id=task.goal_id or goal.id,
                    title=task.title,
                    summary=_compiler_task_summary(task),
                    task_type=task.capability_ref or "system:dispatch_query",
                    status="created",
                    priority=goal.priority,
                    owner_agent_id=task.owner_agent_id,
                    seed_source=_compiler_seed_source(task),
                    constraints_summary=_compiler_constraints_summary(task),
                    acceptance_criteria=encoded_meta,
                    current_risk_level=task.risk_level,
                    industry_instance_id=industry_instance_id,
                    assignment_id=assignment_id,
                    lane_id=lane_id,
                    cycle_id=cycle_id,
                    report_back_mode=report_back_mode,
                    created_at=compiled_at,
                    updated_at=compiled_at,
                )
            )
            self._task_repository.upsert_task(record)

            if self._task_runtime_repository is not None:
                existing_runtime = self._task_runtime_repository.get_runtime(task.id)
                runtime = (
                    existing_runtime.model_copy(
                        update={
                            "runtime_status": "cold",
                            "current_phase": "compiled",
                            "risk_level": task.risk_level,
                            "active_environment_id": task.environment_ref,
                            "last_result_summary": _compiler_task_summary(task),
                            "last_error_summary": None,
                            "last_owner_agent_id": task.owner_agent_id,
                            "updated_at": compiled_at,
                        },
                    )
                    if existing_runtime is not None
                    else TaskRuntimeRecord(
                        task_id=task.id,
                        runtime_status="cold",
                        current_phase="compiled",
                        risk_level=task.risk_level,
                        active_environment_id=task.environment_ref,
                        last_result_summary=_compiler_task_summary(task),
                        last_owner_agent_id=task.owner_agent_id,
                        updated_at=compiled_at,
                    )
                )
                self._task_runtime_repository.upsert_runtime(runtime)

            if self._runtime_frame_repository is not None:
                self._runtime_frame_repository.append_frame(
                    RuntimeFrameRecord(
                        task_id=task.id,
                        goal_summary=goal.title,
                        owner_agent_id=task.owner_agent_id,
                        current_phase="compiled",
                        current_risk_level=task.risk_level,
                        environment_summary=task.environment_ref or "compiler-seed",
                        evidence_summary=_compiler_task_summary(task),
                        constraints_summary=_compiler_constraints_summary(task),
                        capabilities_summary=task.capability_ref,
                        created_at=compiled_at,
                    ),
                )

    def _cancel_superseded_compiler_tasks(
        self,
        goal_id: str,
        *,
        current_unit_id: str,
    ) -> None:
        if self._task_repository is None:
            return
        for task in self._task_repository.list_tasks(goal_id=goal_id):
            if task.status not in {"created", "queued"}:
                continue
            compiler_meta = _task_compiler_meta(task)
            if not compiler_meta:
                continue
            if compiler_meta.get("unit_id") == current_unit_id:
                continue
            runtime = (
                self._task_runtime_repository.get_runtime(task.id)
                if self._task_runtime_repository is not None
                else None
            )
            if runtime is not None and runtime.current_phase != "compiled":
                continue
            self._task_repository.upsert_task(
                task.model_copy(
                    update={"status": "cancelled", "updated_at": _utc_now()},
                ),
            )
            if runtime is not None and self._task_runtime_repository is not None:
                self._task_runtime_repository.upsert_runtime(
                    runtime.model_copy(
                        update={
                            "runtime_status": "terminated",
                            "current_phase": "cancelled",
                            "last_error_summary": "Superseded by a newer compiler pass.",
                            "updated_at": _utc_now(),
                        },
                    ),
                )

    def _latest_persisted_compilation(
        self,
        goal_id: str,
        *,
        tasks: list[TaskRecord] | None = None,
    ) -> dict[str, object] | None:
        if self._task_repository is None:
            return None
        latest_unit: CompilationUnit | None = None
        latest_specs: list[CompiledTaskSpec] = []
        latest_unit_id: str | None = None
        latest_compiled_at: str | None = None
        candidate_tasks = (
            tasks
            if tasks is not None
            else self._task_repository.list_tasks(goal_id=goal_id)
        )
        for task in candidate_tasks:
            snapshot = _task_compilation_snapshot(task)
            if snapshot is None:
                continue
            unit = snapshot["unit"]
            spec = snapshot["spec"]
            compiled_at = (
                unit.compiled_at.isoformat()
                if unit.compiled_at is not None
                else None
            )
            if latest_unit_id is None or (compiled_at or "") > (latest_compiled_at or ""):
                latest_unit = unit
                latest_specs = [spec]
                latest_unit_id = unit.id
                latest_compiled_at = compiled_at
                continue
            if unit.id == latest_unit_id:
                latest_specs.append(spec)
        if latest_unit is None:
            return None
        latest_specs.sort(key=_compiled_spec_sort_key)
        if not latest_unit.context.get("steps"):
            step_texts = [
                str(spec.payload.get("step_text")).strip()
                for spec in latest_specs
                if isinstance(spec.payload.get("step_text"), str)
                and str(spec.payload.get("step_text")).strip()
            ]
            if step_texts:
                latest_unit = latest_unit.model_copy(
                    update={
                        "context": {
                            **latest_unit.context,
                            "steps": step_texts,
                        },
                    },
                )
        return {"unit": latest_unit, "specs": latest_specs}

    def _build_compilation_unit(
        self,
        goal: GoalRecord,
        *,
        context: dict[str, object] | None,
    ) -> CompilationUnit:
        goal_override = (
            self._override_repository.get_override(goal.id)
            if self._override_repository is not None
            else None
        )
        source_text = goal.summary or goal.title
        override_context = self._goal_compiler_context(goal_override)
        resolved_goal_context = self._resolve_goal_runtime_context(
            goal,
            override=goal_override,
        )
        merged_context: dict[str, object] = {
            "goal_id": goal.id,
            "goal_title": goal.title,
            "goal_summary": goal.summary,
            "goal_priority": goal.priority,
            "steps": (
                list(goal_override.plan_steps)
                if goal_override is not None and goal_override.plan_steps
                else None
            ),
            **override_context,
            **resolved_goal_context,
            **(context or {}),
        }
        steps = merged_context.get("steps")
        if isinstance(steps, list):
            normalized_steps = [
                str(step).strip()
                for step in steps
                if isinstance(step, str) and str(step).strip()
            ]
            merged_context["steps"] = normalized_steps
            if normalized_steps:
                merged_context["current_step_index"] = self._resolve_next_goal_step_index(
                    goal,
                    total_steps=len(normalized_steps),
                )
        learning_feedback = self._build_learning_feedback_context(goal.id)
        if learning_feedback:
            for key in (
                "feedback_summary",
                "feedback_items",
                "feedback_patch_ids",
                "feedback_growth_ids",
                "feedback_evidence_refs",
                "next_plan_hints",
                "current_stage",
                "recent_failures",
                "effective_actions",
                "avoid_repeats",
            ):
                if key in learning_feedback:
                    merged_context[key] = learning_feedback[key]
            merged_context["evidence_refs"] = _merge_string_lists(
                merged_context.get("evidence_refs"),
                learning_feedback["feedback_evidence_refs"],
            )
        knowledge_context = self._build_knowledge_context(
            goal=goal,
            context=merged_context,
        )
        if knowledge_context:
            for key in (
                "knowledge_items",
                "knowledge_refs",
                "knowledge_documents",
                "memory_items",
                "memory_refs",
                "memory_documents",
            ):
                merged_context[key] = _merge_string_lists(
                    merged_context.get(key),
                    knowledge_context.get(key),
                )
        strategy_context = self._build_strategy_context(context=merged_context)
        if strategy_context:
            merged_context.update(strategy_context)
        return CompilationUnit(
            kind="goal",
            source_text=source_text,
            context=merged_context,
        )

    def _build_strategy_context(
        self,
        *,
        context: dict[str, object],
    ) -> dict[str, object]:
        strategy_payload = self._resolve_strategy_memory_payload(
            industry_instance_id=(
                str(context.get("industry_instance_id")).strip()
                if isinstance(context.get("industry_instance_id"), str)
                and str(context.get("industry_instance_id")).strip()
                else None
            ),
            owner_agent_id=(
                str(context.get("owner_agent_id")).strip()
                if isinstance(context.get("owner_agent_id"), str)
                and str(context.get("owner_agent_id")).strip()
                else None
            ),
            role_id=(
                str(context.get("industry_role_id")).strip()
                if isinstance(context.get("industry_role_id"), str)
                and str(context.get("industry_role_id")).strip()
                else None
            ),
        )
        if not strategy_payload:
            return {}
        strategy_items = _build_strategy_memory_items(strategy_payload)
        if not strategy_items:
            return {}
        return {
            "strategy_id": strategy_payload.get("strategy_id"),
            "strategy_summary": strategy_payload.get("summary"),
            "strategy_items": strategy_items,
        }

    def _build_knowledge_context(
        self,
        *,
        goal: GoalRecord,
        context: dict[str, object],
    ) -> dict[str, object]:
        service = self._knowledge_service
        recall_service = getattr(self, "_memory_recall_service", None)
        if service is None:
            if recall_service is None:
                return {}

        query = "\n".join(
            part
            for part in (
                goal.title.strip(),
                goal.summary.strip(),
                "\n".join(_string_list(context.get("steps"))[:3]),
            )
            if part
        ).strip()
        if not query:
            return {}

        role = (
            str(context.get("industry_role_id")).strip()
            if isinstance(context.get("industry_role_id"), str)
            and str(context.get("industry_role_id")).strip()
            else None
        )
        owner_agent_id = (
            str(context.get("owner_agent_id")).strip()
            if isinstance(context.get("owner_agent_id"), str)
            and str(context.get("owner_agent_id")).strip()
            else None
        )
        industry_instance_id = (
            str(context.get("industry_instance_id")).strip()
            if isinstance(context.get("industry_instance_id"), str)
            and str(context.get("industry_instance_id")).strip()
            else None
        )
        owner_scope = (
            str(context.get("owner_scope")).strip()
            if isinstance(context.get("owner_scope"), str)
            and str(context.get("owner_scope")).strip()
            else None
        )
        current_task_id = (
            str(context.get("current_task_id")).strip()
            if isinstance(context.get("current_task_id"), str)
            and str(context.get("current_task_id")).strip()
            else (
                str(context.get("task_id")).strip()
                if isinstance(context.get("task_id"), str)
                and str(context.get("task_id")).strip()
                else None
            )
        )
        work_context_id = (
            str(context.get("work_context_id")).strip()
            if isinstance(context.get("work_context_id"), str)
            and str(context.get("work_context_id")).strip()
            else None
        )
        knowledge_retriever = getattr(service, "retrieve", None)
        memory_retriever = getattr(service, "retrieve_memory", None)
        knowledge_chunks = (
            knowledge_retriever(query=query, role=role, limit=5)
            if callable(knowledge_retriever)
            else []
        )
        recall = getattr(recall_service, "recall", None)
        if callable(recall):
            recall_response = recall(
                query=query,
                role=role,
                scope_type="work_context" if work_context_id else "task" if current_task_id else None,
                scope_id=work_context_id or current_task_id,
                task_id=current_task_id,
                work_context_id=work_context_id,
                agent_id=owner_agent_id,
                industry_instance_id=industry_instance_id,
                global_scope_id=owner_scope,
                include_related_scopes=not bool(work_context_id or current_task_id),
                limit=5,
            )
            memory_chunks = list(getattr(recall_response, "hits", []) or [])
        elif callable(memory_retriever):
            if work_context_id:
                memory_chunks = memory_retriever(
                    query=query,
                    role=role,
                    scope_type="work_context",
                    scope_id=work_context_id,
                    task_id=current_task_id,
                    work_context_id=work_context_id,
                    include_related_scopes=False,
                    limit=3,
                )
            elif current_task_id:
                memory_chunks = memory_retriever(
                    query=query,
                    role=role,
                    scope_type="task",
                    scope_id=current_task_id,
                    task_id=current_task_id,
                    work_context_id=work_context_id,
                    include_related_scopes=False,
                    limit=3,
                )
            else:
                memory_chunks = memory_retriever(
                    query=query,
                    role=role,
                    work_context_id=work_context_id,
                    agent_id=owner_agent_id,
                    industry_instance_id=industry_instance_id,
                    global_scope_id=owner_scope,
                    limit=3,
                )
        else:
            memory_chunks = []
        if not knowledge_chunks and not memory_chunks:
            return {}
        return {
            "knowledge_items": [_knowledge_chunk_brief(chunk) for chunk in knowledge_chunks],
            "knowledge_refs": [
                str(getattr(chunk, "id", "")).strip()
                for chunk in knowledge_chunks
                if str(getattr(chunk, "id", "")).strip()
            ],
            "knowledge_documents": [
                str(getattr(chunk, "document_id", "")).strip()
                for chunk in knowledge_chunks
                if str(getattr(chunk, "document_id", "")).strip()
            ],
            "memory_items": [_knowledge_chunk_brief(chunk) for chunk in memory_chunks],
            "memory_refs": [
                ref
                for chunk in memory_chunks
                if (ref := _memory_chunk_ref(chunk))
            ],
            "memory_documents": [
                str(getattr(chunk, "document_id", "")).strip()
                or f"{str(getattr(chunk, 'source_type', '')).strip()}:{str(getattr(chunk, 'source_ref', '')).strip()}"
                for chunk in memory_chunks
                if (
                    str(getattr(chunk, "document_id", "")).strip()
                    or str(getattr(chunk, "source_ref", "")).strip()
                )
            ],
        }

    def _resolve_strategy_memory_payload(
        self,
        *,
        industry_instance_id: str | None,
        owner_agent_id: str | None,
        role_id: str | None,
    ) -> dict[str, object] | None:
        _ = role_id
        return resolve_strategy_payload(
            service=self._strategy_memory_service,
            scope_type="industry",
            scope_id=industry_instance_id,
            owner_agent_id=owner_agent_id if owner_agent_id else None,
            fallback_owner_agent_ids=(
                [EXECUTION_CORE_AGENT_ID, None]
                if industry_instance_id
                else []
            ),
        )

    def _build_learning_feedback_context(self, goal_id: str) -> dict[str, object]:
        feedback_items: list[str] = []
        next_plan_hints: list[str] = []
        feedback_patch_ids: list[str] = []
        feedback_growth_ids: list[str] = []
        feedback_evidence_refs: list[str] = []

        if self._learning_service is not None:
            patches = [
                patch
                for patch in self._learning_service.list_patches(goal_id=goal_id)
                if getattr(patch, "status", None) in {"approved", "applied"}
            ]
            patches.sort(
                key=lambda item: _sort_datetime_value(
                    getattr(item, "applied_at", None),
                    getattr(item, "created_at", None),
                ),
                reverse=True,
            )

            growth = self._learning_service.list_growth(goal_id=goal_id, limit=20)
            growth.sort(
                key=lambda item: _sort_datetime_value(getattr(item, "created_at", None)),
                reverse=True,
            )

            for patch in patches[:5]:
                if patch.id:
                    feedback_patch_ids.append(patch.id)
                feedback_items.append(
                    f"Patch[{patch.status}/{patch.kind}] {patch.title}: {patch.description}",
                )
                next_plan_hints.append(
                    _first_non_empty(
                        {
                            "title": patch.title,
                            "description": patch.description,
                        },
                        "title",
                        "description",
                    )
                    or patch.id,
                )
                feedback_evidence_refs = _merge_string_lists(
                    feedback_evidence_refs,
                    [patch.source_evidence_id] if patch.source_evidence_id else [],
                    patch.evidence_refs,
                )

            for event in growth[:5]:
                if event.id:
                    feedback_growth_ids.append(event.id)
                feedback_items.append(
                    f"Growth[{event.change_type}/{event.result}] {event.description}",
                )
                next_plan_hints.append(event.description or event.change_type)
                feedback_evidence_refs = _merge_string_lists(
                    feedback_evidence_refs,
                    [event.source_evidence_id] if event.source_evidence_id else [],
                )

        execution_feedback = self._build_recent_execution_feedback(goal_id)
        current_stage = execution_feedback.get("current_stage")
        recent_failures = list(execution_feedback.get("recent_failures") or [])
        effective_actions = list(execution_feedback.get("effective_actions") or [])
        avoid_repeats = list(execution_feedback.get("avoid_repeats") or [])
        if isinstance(current_stage, str) and current_stage.strip():
            feedback_items.append(f"Current stage: {current_stage.strip()}")
        feedback_items.extend(
            f"Recent failure: {item}"
            for item in recent_failures[:3]
        )
        feedback_items.extend(
            f"Effective action: {item}"
            for item in effective_actions[:3]
        )
        feedback_items.extend(
            f"Do not repeat: {item}"
            for item in avoid_repeats[:3]
        )
        next_plan_hints = _merge_string_lists(next_plan_hints, effective_actions[:3])
        feedback_evidence_refs = _merge_string_lists(
            feedback_evidence_refs,
            execution_feedback.get("evidence_refs"),
        )

        feedback_items = _dedupe_strings(feedback_items)
        next_plan_hints = _dedupe_strings(next_plan_hints)
        if (
            not feedback_items
            and not feedback_patch_ids
            and not feedback_growth_ids
            and not feedback_evidence_refs
            and not current_stage
            and not recent_failures
            and not effective_actions
            and not avoid_repeats
        ):
            return {}
        return {
            "feedback_summary": " | ".join(feedback_items[:4]),
            "feedback_items": feedback_items[:8],
            "feedback_patch_ids": feedback_patch_ids,
            "feedback_growth_ids": feedback_growth_ids,
            "feedback_evidence_refs": feedback_evidence_refs,
            "next_plan_hints": next_plan_hints[:6],
            "current_stage": current_stage,
            "recent_failures": recent_failures[:4],
            "effective_actions": effective_actions[:4],
            "avoid_repeats": avoid_repeats[:4],
        }

    def _build_recent_execution_feedback(self, goal_id: str) -> dict[str, object]:
        task_repository = self._task_repository
        if task_repository is None:
            return {}
        tasks = [
            task
            for task in task_repository.list_tasks(goal_id=goal_id)
            if str(getattr(task, "task_type", "") or "") != "learning-patch"
        ]
        return collect_recent_execution_feedback(
            tasks=tasks,
            task_runtime_repository=self._task_runtime_repository,
            evidence_ledger=self._evidence_ledger,
        )

    def _apply_override(self, goal: GoalRecord) -> GoalRecord:
        if self._override_repository is None:
            return goal
        override = self._override_repository.get_override(goal.id)
        if override is None:
            return goal
        update: dict[str, Any] = {}
        for field in ("title", "summary", "status", "priority", "owner_scope"):
            value = getattr(override, field)
            if value is not None:
                update[field] = value
        if not update:
            return goal
        update["updated_at"] = max(goal.updated_at, override.updated_at or override.created_at)
        return goal.model_copy(update=update)

    def _collect_related_patches(
        self,
        goal_id: str,
        *,
        evidence_ids: set[str],
    ) -> list[dict[str, object]]:
        if self._learning_service is None:
            return []
        related: list[dict[str, object]] = []
        for patch in self._learning_service.list_patches():
            patch_evidence_refs = {
                str(ref)
                for ref in patch.evidence_refs
                if isinstance(ref, str) and ref
            }
            metadata = _parse_metadata(patch.diff_summary)
            patch_goal_id = patch.goal_id or _first_non_empty(
                metadata,
                "goal_id",
                "target_goal",
                "goal",
            )
            if patch_goal_id == goal_id:
                related.append(patch.model_dump(mode="json"))
                continue
            if patch.source_evidence_id and patch.source_evidence_id in evidence_ids:
                related.append(patch.model_dump(mode="json"))
                continue
            if patch_evidence_refs.intersection(evidence_ids):
                related.append(patch.model_dump(mode="json"))
        related.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return related

    def _collect_related_growth(
        self,
        *,
        evidence_ids: set[str],
        patch_ids: set[str],
        agent_ids: set[str],
    ) -> list[dict[str, object]]:
        if self._learning_service is None:
            return []
        related: list[dict[str, object]] = []
        for event in self._learning_service.list_growth(limit=200):
            if event.source_patch_id and event.source_patch_id in patch_ids:
                related.append(event.model_dump(mode="json"))
                continue
            if event.source_evidence_id and event.source_evidence_id in evidence_ids:
                related.append(event.model_dump(mode="json"))
                continue
            if event.agent_id in agent_ids:
                related.append(event.model_dump(mode="json"))
        related.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return related

    def _collect_related_agents(self, agent_ids: set[str]) -> list[dict[str, object]]:
        if not agent_ids:
            return []
        agents: list[dict[str, object]] = []
        service = self._agent_profile_service
        getter = getattr(service, "get_agent", None)
        for agent_id in sorted(agent_ids):
            agent_payload: dict[str, object]
            agent = getter(agent_id) if callable(getter) else None
            if agent is None:
                agent_payload = {
                    "agent_id": agent_id,
                    "name": agent_id,
                    "role_name": "",
                    "role_summary": "",
                    "status": "unknown",
                    "risk_level": "auto",
                    "current_goal_id": None,
                    "current_goal": "",
                    "current_task_id": None,
                    "environment_summary": "",
                    "today_output_summary": "",
                    "latest_evidence_summary": "",
                    "capabilities": [],
                    "updated_at": None,
                }
            else:
                model_dump = getattr(agent, "model_dump", None)
                agent_payload = (
                    model_dump(mode="json")
                    if callable(model_dump)
                    else dict(agent)
                    if isinstance(agent, dict)
                    else {"agent_id": agent_id, "name": agent_id}
                )
            agents.append(agent_payload)
        return agents

    def _publish_runtime_event(
        self,
        *,
        topic: str,
        action: str,
        payload: dict[str, object],
    ) -> None:
        if self._runtime_event_bus is None:
            return
        self._runtime_event_bus.publish(
            topic=topic,
            action=action,
            payload=payload,
        )
