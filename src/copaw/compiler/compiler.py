# -*- coding: utf-8 -*-
"""Semantic compiler: compile high-level intents into kernel-native task specs."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from .models import (
    CompilableKind,
    CompilationUnit,
    CompiledTaskSegment,
    CompiledTaskSpec,
    ResumePoint,
)
from ..industry.identity import EXECUTION_CORE_ROLE_ID
from ..industry.prompting import (
    build_evidence_contract_lines,
    build_role_execution_contract_lines,
    build_task_mode_contract_lines,
    describe_industry_task_mode,
)
from ..kernel import KernelTask

logger = logging.getLogger(__name__)


class SemanticCompiler:
    """Compile natural language goals/plans into kernel task specs."""

    def compile(self, unit: CompilationUnit) -> list[CompiledTaskSpec]:
        unit = unit.model_copy(
            update={"compiled_at": unit.compiled_at or datetime.now(timezone.utc)},
        )
        compiler_fn = self._get_compiler(unit.kind)
        specs = [
            spec.model_copy(
                update={
                    "task_id": spec.task_id or self._compiled_task_id(unit, index),
                },
            )
            for index, spec in enumerate(compiler_fn(unit))
        ]
        logger.info(
            "Compiled %s '%s' into %d task spec(s)",
            unit.kind,
            unit.id,
            len(specs),
        )
        return specs

    def compile_to_kernel_tasks(
        self,
        unit: CompilationUnit,
        *,
        specs: list[CompiledTaskSpec] | None = None,
    ) -> list[KernelTask]:
        specs = specs or self.compile(unit)
        goal_id = unit.context.get("goal_id")
        owner_agent_id = unit.context.get("owner_agent_id")
        actor_owner_id = unit.context.get("actor_owner_id") or owner_agent_id
        parent_task_id = unit.context.get("parent_task_id")
        tasks: list[KernelTask] = []
        for index, spec in enumerate(specs):
            task_segment = (
                spec.task_segment.model_dump(mode="json")
                if spec.task_segment is not None
                else {}
            )
            resume_point = (
                spec.resume_point.model_dump(mode="json")
                if spec.resume_point is not None
                else {}
            )
            payload = dict(spec.payload)
            if task_segment:
                payload.setdefault("task_segment", task_segment)
            if resume_point:
                payload.setdefault("resume_point", resume_point)
            payload["source_unit_id"] = spec.source_unit_id
            tasks.append(
                KernelTask(
                    id=spec.task_id or self._compiled_task_id(unit, index),
                    title=spec.title,
                    capability_ref=spec.capability_ref,
                    environment_ref=spec.environment_ref,
                    risk_level=spec.risk_level,
                    payload=payload,
                    goal_id=str(goal_id) if goal_id else None,
                    parent_task_id=str(parent_task_id) if parent_task_id else None,
                    work_context_id=_string_context_value(
                        unit.context.get("work_context_id"),
                    ),
                    owner_agent_id=(
                        str(owner_agent_id)
                        if owner_agent_id
                        else "copaw-agent-runner"
                    ),
                    actor_owner_id=(
                        str(spec.actor_owner_id or actor_owner_id)
                        if (spec.actor_owner_id or actor_owner_id)
                        else None
                    ),
                    task_segment=task_segment,
                    resume_point=resume_point,
                ),
            )
        return tasks

    def _get_compiler(self, kind: CompilableKind):
        compilers = {
            "goal": self._compile_goal,
            "plan": self._compile_plan,
            "role": self._compile_role,
            "directive": self._compile_directive,
        }
        return compilers.get(kind, self._compile_directive)

    def _compile_goal(self, unit: CompilationUnit) -> list[CompiledTaskSpec]:
        title = unit.context.get("goal_title") or unit.source_text[:80]
        summary = unit.context.get("goal_summary") or unit.source_text
        sop_binding_spec = self._build_sop_binding_trigger_spec(
            unit,
            title=str(title),
            summary=str(summary),
        )
        if sop_binding_spec is not None:
            return [sop_binding_spec]
        routine_spec = self._build_routine_replay_spec(
            unit,
            title=str(title),
            summary=str(summary),
        )
        if routine_spec is not None:
            return [routine_spec]
        feedback_lines = _feedback_prompt_lines(unit.context)
        strategy_lines = _strategy_prompt_lines(unit.context)
        knowledge_lines = _knowledge_prompt_lines(unit.context)
        execution_path_lines = _execution_path_guidance_lines(unit.context)
        runtime_lines = _runtime_execution_prompt_lines(unit.context)
        steps = [
            str(step).strip()
            for step in (unit.context.get("steps") or [])
            if str(step).strip()
        ]
        if steps:
            requested_step_index = unit.context.get("current_step_index")
            current_step_index = (
                requested_step_index
                if isinstance(requested_step_index, int)
                else int(str(requested_step_index))
                if isinstance(requested_step_index, str)
                and str(requested_step_index).strip().isdigit()
                else 0
            )
            if current_step_index < 0:
                current_step_index = 0
            if current_step_index >= len(steps):
                return []
            step = steps[current_step_index]
            return [
                self._build_dispatch_query_spec(
                    unit,
                    title=f"Goal step {current_step_index + 1}: {step[:60]}",
                    prompt_text="\n".join(
                        part
                        for part in [
                            f"Goal title: {title}",
                            f"Goal summary: {summary}",
                            *runtime_lines,
                            *feedback_lines,
                            *strategy_lines,
                            *knowledge_lines,
                            *execution_path_lines,
                            f"Planned step {current_step_index + 1}/{len(steps)}: {step}",
                            "Execute only this planned step and report the result.",
                        ]
                        if part
                    ),
                    risk_level="guarded",
                    payload_extras={
                        "step_index": current_step_index,
                        "step_text": step,
                        "plan_step_number": current_step_index + 1,
                        "plan_step_total": len(steps),
                    },
                    segment_kind="goal-step",
                    segment_index=0,
                    segment_total=1,
                ),
            ]
        prompt_text = "\n".join(
            part
            for part in [
                f"Goal title: {title}",
                f"Goal summary: {summary}",
                *runtime_lines,
                *feedback_lines,
                *strategy_lines,
                *knowledge_lines,
                *execution_path_lines,
                "Produce the next concrete execution step for this goal and carry it out.",
            ]
            if part
        )
        return [
            self._build_dispatch_query_spec(
                unit,
                title=f"Execute goal: {str(title)[:80]}",
                prompt_text=prompt_text,
                risk_level="guarded",
                segment_kind="goal",
            ),
        ]

    def _compile_plan(self, unit: CompilationUnit) -> list[CompiledTaskSpec]:
        steps = unit.context.get("steps", [unit.source_text])
        sop_binding_spec = self._build_sop_binding_trigger_spec(
            unit,
            title=str(unit.context.get("goal_title") or unit.source_text[:80]),
            summary=str(unit.context.get("goal_summary") or unit.source_text),
        )
        if sop_binding_spec is not None:
            return [sop_binding_spec]
        routine_spec = self._build_routine_replay_spec(
            unit,
            title=str(unit.context.get("goal_title") or unit.source_text[:80]),
            summary=str(unit.context.get("goal_summary") or unit.source_text),
        )
        if routine_spec is not None:
            return [routine_spec]
        feedback_lines = _feedback_prompt_lines(unit.context)
        strategy_lines = _strategy_prompt_lines(unit.context)
        knowledge_lines = _knowledge_prompt_lines(unit.context)
        execution_path_lines = _execution_path_guidance_lines(unit.context)
        runtime_lines = _runtime_execution_prompt_lines(unit.context)
        return [
            self._build_dispatch_query_spec(
                unit,
                title=f"Plan step {i + 1}: {str(step)[:60]}",
                prompt_text=(
                    "\n".join(
                        part
                        for part in [
                            f"Plan step {i + 1}: {step}",
                            *runtime_lines,
                            *feedback_lines,
                            *strategy_lines,
                            *knowledge_lines,
                            *execution_path_lines,
                            "Focus only on this step, execute it, and report the result.",
                        ]
                        if part
                    )
                ),
                risk_level="auto",
                payload_extras={
                    "step_index": i,
                    "step_text": str(step),
                    "plan_step_number": i + 1,
                    "plan_step_total": len(steps),
                },
                segment_kind="plan-step",
                segment_index=i,
                segment_total=len(steps),
            )
            for i, step in enumerate(steps)
        ]

    def _compile_role(self, unit: CompilationUnit) -> list[CompiledTaskSpec]:
        actor_owner_id = self._actor_owner_id(unit)
        task_segment = self._build_task_segment(
            unit,
            segment_kind="role-apply",
            actor_owner_id=actor_owner_id,
        )
        resume_point = self._build_resume_point(
            unit,
            task_segment=task_segment,
            payload={"role_text": unit.source_text},
        )
        return [
            CompiledTaskSpec(
                title=f"Apply role: {unit.source_text[:60]}",
                capability_ref="system:apply_role",
                risk_level="guarded",
                payload={
                    "role_text": unit.source_text,
                    "agent_id": unit.context.get("target_agent_id")
                    or unit.context.get("owner_agent_id"),
                    "task_segment": task_segment.model_dump(mode="json"),
                    "resume_point": resume_point.model_dump(mode="json"),
                },
                source_unit_id=unit.id,
                actor_owner_id=actor_owner_id,
                task_segment=task_segment,
                resume_point=resume_point,
            ),
        ]

    def _compile_directive(self, unit: CompilationUnit) -> list[CompiledTaskSpec]:
        sop_binding_spec = self._build_sop_binding_trigger_spec(
            unit,
            title=str(unit.context.get("goal_title") or unit.source_text[:80]),
            summary=str(unit.context.get("goal_summary") or unit.source_text),
        )
        if sop_binding_spec is not None:
            return [sop_binding_spec]
        routine_spec = self._build_routine_replay_spec(
            unit,
            title=str(unit.context.get("goal_title") or unit.source_text[:80]),
            summary=str(unit.context.get("goal_summary") or unit.source_text),
        )
        if routine_spec is not None:
            return [routine_spec]
        feedback_lines = _feedback_prompt_lines(unit.context)
        strategy_lines = _strategy_prompt_lines(unit.context)
        knowledge_lines = _knowledge_prompt_lines(unit.context)
        execution_path_lines = _execution_path_guidance_lines(unit.context)
        runtime_lines = _runtime_execution_prompt_lines(unit.context)
        prompt_text = "\n".join(
            part
            for part in [
                unit.source_text,
                *runtime_lines,
                *feedback_lines,
                *strategy_lines,
                *knowledge_lines,
                *execution_path_lines,
            ]
            if part
        )
        return [
            self._build_dispatch_query_spec(
                unit,
                title=f"Directive: {unit.source_text[:80]}",
                prompt_text=prompt_text,
                risk_level="auto",
                payload_extras={"directive_text": unit.source_text},
                segment_kind="directive",
            ),
        ]

    def _build_dispatch_query_spec(
        self,
        unit: CompilationUnit,
        *,
        title: str,
        prompt_text: str,
        risk_level: str,
        payload_extras: dict[str, object] | None = None,
        segment_kind: str,
        segment_index: int = 0,
        segment_total: int = 1,
    ) -> CompiledTaskSpec:
        session_id = self._dispatch_session_id(unit)
        owner_agent_id = self._actor_owner_id(unit)
        channel = str(unit.context.get("channel") or unit.kind)
        trigger_source = unit.context.get("trigger_source")
        trigger_actor = unit.context.get("trigger_actor")
        trigger_reason = unit.context.get("trigger_reason")
        dispatch_requested_at = unit.context.get("dispatch_requested_at")
        request_context = _request_context_payload(
            unit.context,
            owner_agent_id=owner_agent_id,
        )
        task_segment = self._build_task_segment(
            unit,
            segment_kind=segment_kind,
            segment_index=segment_index,
            segment_total=segment_total,
            actor_owner_id=owner_agent_id,
            payload_extras=payload_extras,
        )
        resume_point = self._build_resume_point(
            unit,
            task_segment=task_segment,
            payload={
                "channel": channel,
                "session_id": session_id,
                "prompt_text": prompt_text[:280],
            },
        )
        assignment_plan_payload = self._assignment_plan_payload(unit)
        compiler_meta = {
            "source_kind": "compiler",
            "unit_kind": unit.kind,
            "unit_id": unit.id,
            "compiled_at": (
                unit.compiled_at.isoformat()
                if unit.compiled_at is not None
                else None
            ),
            "goal_id": unit.context.get("goal_id"),
            "goal_title": unit.context.get("goal_title"),
            "goal_summary": unit.context.get("goal_summary"),
            "owner_agent_id": owner_agent_id,
            "actor_owner_id": owner_agent_id,
            "trigger_source": trigger_source,
            "trigger_actor": trigger_actor,
            "trigger_reason": trigger_reason,
            "dispatch_requested_at": dispatch_requested_at,
            "request_context": dict(request_context),
            "step_index": payload_extras.get("step_index") if payload_extras else None,
            "step_text": payload_extras.get("step_text") if payload_extras else None,
            "plan_step_number": (
                payload_extras.get("plan_step_number")
                if payload_extras
                else None
            ),
            "plan_step_total": (
                payload_extras.get("plan_step_total")
                if payload_extras
                else None
            ),
            "prompt_text": prompt_text,
            "evidence_refs": list(unit.context.get("evidence_refs") or []),
            "feedback_summary": unit.context.get("feedback_summary"),
            "feedback_items": _string_context_list(unit.context.get("feedback_items")),
            "feedback_patch_ids": _string_context_list(unit.context.get("feedback_patch_ids")),
            "feedback_growth_ids": _string_context_list(unit.context.get("feedback_growth_ids")),
            "feedback_evidence_refs": _string_context_list(
                unit.context.get("feedback_evidence_refs"),
            ),
            "next_plan_hints": _string_context_list(unit.context.get("next_plan_hints")),
            "current_stage": unit.context.get("current_stage"),
            "recent_failures": _string_context_list(unit.context.get("recent_failures")),
            "effective_actions": _string_context_list(unit.context.get("effective_actions")),
            "avoid_repeats": _string_context_list(unit.context.get("avoid_repeats")),
            "strategy_id": unit.context.get("strategy_id"),
            "strategy_summary": unit.context.get("strategy_summary"),
            "strategy_items": _string_context_list(unit.context.get("strategy_items")),
            "strategy_mission": _string_context_value(unit.context.get("strategy_mission")),
            "strategy_north_star": _string_context_value(unit.context.get("strategy_north_star")),
            "strategy_priority_order": _string_context_list(
                unit.context.get("strategy_priority_order"),
            ),
            "strategy_strategic_uncertainties": _mapping_context_list(
                unit.context.get("strategy_strategic_uncertainties"),
            ),
            "strategy_lane_budgets": _mapping_context_list(
                unit.context.get("strategy_lane_budgets"),
            ),
            "strategy_trigger_rules": _mapping_context_list(
                unit.context.get("strategy_trigger_rules"),
            ),
            "strategy_planning_policy": _string_context_list(
                unit.context.get("strategy_planning_policy"),
            ),
            "strategy_review_rules": _string_context_list(
                unit.context.get("strategy_review_rules"),
            ),
            "strategy_current_focuses": _string_context_list(
                unit.context.get("strategy_current_focuses"),
            ),
            "knowledge_items": _string_context_list(unit.context.get("knowledge_items")),
            "knowledge_refs": _string_context_list(unit.context.get("knowledge_refs")),
            "knowledge_documents": _string_context_list(
                unit.context.get("knowledge_documents"),
            ),
            "memory_items": _string_context_list(unit.context.get("memory_items")),
            "memory_refs": _string_context_list(unit.context.get("memory_refs")),
            "memory_documents": _string_context_list(
                unit.context.get("memory_documents"),
            ),
            **_runtime_continuity_payload(unit.context),
            "task_segment": task_segment.model_dump(mode="json"),
            "resume_point": resume_point.model_dump(mode="json"),
        }
        if assignment_plan_payload:
            compiler_meta.update(assignment_plan_payload)
        request_payload = {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt_text}],
                },
            ],
            "session_id": session_id,
            "user_id": owner_agent_id,
            "channel": channel,
            **request_context,
        }
        payload = {
            "request": request_payload,
            "channel": channel,
            "user_id": owner_agent_id,
            "session_id": session_id,
            "mode": "final",
            "dispatch_events": False,
            "meta": {
                "source_kind": "compiler",
                "unit_kind": unit.kind,
                "unit_id": unit.id,
                "compiled_at": (
                    unit.compiled_at.isoformat()
                    if unit.compiled_at is not None
                    else None
                ),
                "goal_id": unit.context.get("goal_id"),
                "actor_owner_id": owner_agent_id,
                "trigger_source": trigger_source,
                "trigger_actor": trigger_actor,
                "trigger_reason": trigger_reason,
                "dispatch_requested_at": dispatch_requested_at,
                "request_context": dict(request_context),
                **_runtime_continuity_payload(unit.context),
            },
            "compiler": compiler_meta,
            "request_context": dict(request_context),
            "task_seed": {
                "title": title,
                "risk_level": risk_level,
                "environment_ref": f"session:{channel}:{session_id}",
                "request_preview": prompt_text[:280],
                "actor_owner_id": owner_agent_id,
                "trigger_source": trigger_source,
                "trigger_actor": trigger_actor,
                "trigger_reason": trigger_reason,
                "dispatch_requested_at": dispatch_requested_at,
                "request_context": dict(request_context),
                "task_segment": task_segment.model_dump(mode="json"),
                "resume_point": resume_point.model_dump(mode="json"),
                "evidence_refs": list(unit.context.get("evidence_refs") or []),
                "feedback_summary": unit.context.get("feedback_summary"),
                "feedback_patch_ids": _string_context_list(
                    unit.context.get("feedback_patch_ids"),
                ),
                "feedback_growth_ids": _string_context_list(
                    unit.context.get("feedback_growth_ids"),
                ),
                "next_plan_hints": _string_context_list(unit.context.get("next_plan_hints")),
                "current_stage": unit.context.get("current_stage"),
                "recent_failures": _string_context_list(unit.context.get("recent_failures")),
                "effective_actions": _string_context_list(unit.context.get("effective_actions")),
                "avoid_repeats": _string_context_list(unit.context.get("avoid_repeats")),
                "strategy_id": unit.context.get("strategy_id"),
                "strategy_summary": unit.context.get("strategy_summary"),
                "knowledge_refs": _string_context_list(unit.context.get("knowledge_refs")),
                "memory_refs": _string_context_list(unit.context.get("memory_refs")),
            },
            "task_segment": task_segment.model_dump(mode="json"),
            "resume_point": resume_point.model_dump(mode="json"),
        }
        if assignment_plan_payload:
            payload["task_seed"].update(self._assignment_plan_payload(unit))
        if payload_extras:
            payload.update(payload_extras)
        return CompiledTaskSpec(
            title=title,
            capability_ref="system:dispatch_query",
            environment_ref=f"session:{channel}:{session_id}",
            risk_level=risk_level,
            payload=payload,
            source_unit_id=unit.id,
            actor_owner_id=owner_agent_id,
            task_segment=task_segment,
            resume_point=resume_point,
        )

    def _build_routine_replay_spec(
        self,
        unit: CompilationUnit,
        *,
        title: str,
        summary: str,
    ) -> CompiledTaskSpec | None:
        routine_id = _string_context_value(unit.context.get("routine_id"))
        if routine_id is None:
            return None
        owner_agent_id = self._actor_owner_id(unit)
        session_id = (
            _string_context_value(unit.context.get("routine_session_id"))
            or _string_context_value(unit.context.get("session_id"))
            or self._dispatch_session_id(unit)
        )
        request_context = _request_context_payload(
            unit.context,
            owner_agent_id=owner_agent_id,
        )
        source_ref = _string_context_value(
            unit.context.get("routine_source_ref"),
            unit.context.get("backlog_item_id"),
            unit.context.get("goal_id"),
        )
        routine_input_payload = unit.context.get("routine_input_payload")
        if not isinstance(routine_input_payload, dict):
            routine_input_payload = {}
        routine_metadata = unit.context.get("routine_metadata")
        if not isinstance(routine_metadata, dict):
            routine_metadata = {}
        task_segment = self._build_task_segment(
            unit,
            segment_kind="routine-replay",
            actor_owner_id=owner_agent_id,
        )
        resume_point = self._build_resume_point(
            unit,
            task_segment=task_segment,
            payload={
                "routine_id": routine_id,
                "session_id": session_id,
            },
        )
        assignment_plan_payload = self._assignment_plan_payload(unit)
        compiler_meta = {
            "source_kind": "compiler",
            "unit_kind": unit.kind,
            "unit_id": unit.id,
            "compiled_at": (
                unit.compiled_at.isoformat()
                if unit.compiled_at is not None
                else None
            ),
            "goal_id": unit.context.get("goal_id"),
            "goal_title": unit.context.get("goal_title"),
            "goal_summary": unit.context.get("goal_summary"),
            "owner_agent_id": owner_agent_id,
            "actor_owner_id": owner_agent_id,
            "routine_id": routine_id,
            "request_context": dict(request_context),
            **_runtime_continuity_payload(unit.context),
            "task_segment": task_segment.model_dump(mode="json"),
            "resume_point": resume_point.model_dump(mode="json"),
        }
        if assignment_plan_payload:
            compiler_meta.update(assignment_plan_payload)
        payload = {
            "routine_id": routine_id,
            "source_type": _string_context_value(unit.context.get("routine_source_type")) or "goal-task",
            "source_ref": source_ref or unit.id,
            "owner_agent_id": owner_agent_id,
            "owner_scope": _string_context_value(unit.context.get("owner_scope")),
            "session_id": session_id,
            "request_context": {
                **dict(request_context),
                "goal_title": title,
                "goal_summary": summary,
                "routine_id": routine_id,
            },
            "input_payload": dict(routine_input_payload),
            "metadata": {
                **dict(routine_metadata),
                "source_kind": "compiler",
                "unit_kind": unit.kind,
                "unit_id": unit.id,
                "goal_id": unit.context.get("goal_id"),
            },
            "compiler": compiler_meta,
            "task_seed": {
                "title": title,
                "risk_level": _string_context_value(unit.context.get("routine_risk_level")) or "guarded",
                "environment_ref": f"routine:{routine_id}",
                "routine_id": routine_id,
                "request_context": dict(request_context),
                "task_segment": task_segment.model_dump(mode="json"),
                "resume_point": resume_point.model_dump(mode="json"),
            },
            "task_segment": task_segment.model_dump(mode="json"),
            "resume_point": resume_point.model_dump(mode="json"),
        }
        if assignment_plan_payload:
            payload["task_seed"].update(self._assignment_plan_payload(unit))
        return CompiledTaskSpec(
            title=f"Replay routine: {title[:60]}",
            capability_ref="system:replay_routine",
            environment_ref=f"routine:{routine_id}",
            risk_level=_string_context_value(unit.context.get("routine_risk_level")) or "guarded",
            payload=payload,
            source_unit_id=unit.id,
            actor_owner_id=owner_agent_id,
            task_segment=task_segment,
            resume_point=resume_point,
        )

    def _build_sop_binding_trigger_spec(
        self,
        unit: CompilationUnit,
        *,
        title: str,
        summary: str,
    ) -> CompiledTaskSpec | None:
        binding_id = _string_context_value(unit.context.get("fixed_sop_binding_id"))
        if binding_id is None:
            return None
        owner_agent_id = self._actor_owner_id(unit)
        workflow_run_id = _string_context_value(
            unit.context.get("fixed_sop_workflow_run_id"),
            unit.context.get("workflow_run_id"),
        )
        request_context = _request_context_payload(
            unit.context,
            owner_agent_id=owner_agent_id,
        )
        source_ref = _string_context_value(
            unit.context.get("fixed_sop_source_ref"),
            unit.context.get("backlog_item_id"),
            unit.context.get("goal_id"),
        )
        binding_input_payload = unit.context.get("fixed_sop_input_payload")
        if not isinstance(binding_input_payload, dict):
            binding_input_payload = {}
        binding_metadata = unit.context.get("fixed_sop_metadata")
        if not isinstance(binding_metadata, dict):
            binding_metadata = {}
        task_segment = self._build_task_segment(
            unit,
            segment_kind="sop-binding-trigger",
            actor_owner_id=owner_agent_id,
        )
        resume_point = self._build_resume_point(
            unit,
            task_segment=task_segment,
            payload={
                "binding_id": binding_id,
                "workflow_run_id": workflow_run_id,
            },
        )
        assignment_plan_payload = self._assignment_plan_payload(unit)
        compiler_meta = {
            "source_kind": "compiler",
            "unit_kind": unit.kind,
            "unit_id": unit.id,
            "compiled_at": (
                unit.compiled_at.isoformat()
                if unit.compiled_at is not None
                else None
            ),
            "goal_id": unit.context.get("goal_id"),
            "goal_title": unit.context.get("goal_title"),
            "goal_summary": unit.context.get("goal_summary"),
            "owner_agent_id": owner_agent_id,
            "actor_owner_id": owner_agent_id,
            "fixed_sop_binding_id": binding_id,
            "workflow_run_id": workflow_run_id,
            "request_context": dict(request_context),
            **_runtime_continuity_payload(unit.context),
            "task_segment": task_segment.model_dump(mode="json"),
            "resume_point": resume_point.model_dump(mode="json"),
        }
        if assignment_plan_payload:
            compiler_meta.update(assignment_plan_payload)
        payload = {
            "binding_id": binding_id,
            "source_type": (
                _string_context_value(unit.context.get("fixed_sop_source_type"))
                or "goal-task"
            ),
            "source_ref": source_ref or unit.id,
            "workflow_run_id": workflow_run_id,
            "owner_agent_id": owner_agent_id,
            "owner_scope": _string_context_value(unit.context.get("owner_scope")),
            "request_context": {
                **dict(request_context),
                "goal_title": title,
                "goal_summary": summary,
                "binding_id": binding_id,
            },
            "input_payload": dict(binding_input_payload),
            "metadata": {
                **dict(binding_metadata),
                "source_kind": "compiler",
                "unit_kind": unit.kind,
                "unit_id": unit.id,
                "goal_id": unit.context.get("goal_id"),
                "source_ref": source_ref or unit.id,
            },
            "compiler": compiler_meta,
            "task_seed": {
                "title": title,
                "risk_level": (
                    _string_context_value(unit.context.get("fixed_sop_risk_level"))
                    or "guarded"
                ),
                "environment_ref": f"sop-binding:{binding_id}",
                "binding_id": binding_id,
                "workflow_run_id": workflow_run_id,
                "request_context": dict(request_context),
                "task_segment": task_segment.model_dump(mode="json"),
                "resume_point": resume_point.model_dump(mode="json"),
            },
            "task_segment": task_segment.model_dump(mode="json"),
            "resume_point": resume_point.model_dump(mode="json"),
        }
        if assignment_plan_payload:
            payload["task_seed"].update(self._assignment_plan_payload(unit))
        return CompiledTaskSpec(
            title=f"Run fixed SOP binding: {title[:60]}",
            capability_ref="system:run_fixed_sop",
            environment_ref=f"sop-binding:{binding_id}",
            risk_level=(
                _string_context_value(unit.context.get("fixed_sop_risk_level"))
                or "guarded"
            ),
            payload=payload,
            source_unit_id=unit.id,
            actor_owner_id=owner_agent_id,
            task_segment=task_segment,
            resume_point=resume_point,
        )

    def _actor_owner_id(self, unit: CompilationUnit) -> str:
        return str(
            unit.actor_owner_id
            or unit.context.get("actor_owner_id")
            or unit.context.get("owner_agent_id")
            or "copaw-agent-runner",
        )

    def _build_task_segment(
        self,
        unit: CompilationUnit,
        *,
        segment_kind: str,
        actor_owner_id: str,
        segment_index: int = 0,
        segment_total: int = 1,
        payload_extras: dict[str, object] | None = None,
    ) -> CompiledTaskSegment:
        extras = dict(payload_extras or {})
        return CompiledTaskSegment(
            segment_id=f"{unit.id}:{segment_kind}:{segment_index + 1}",
            segment_kind=segment_kind,  # type: ignore[arg-type]
            index=segment_index,
            total=max(1, segment_total),
            actor_owner_id=actor_owner_id,
            resume_strategy="resume-from-checkpoint",
            metadata={
                "unit_id": unit.id,
                "unit_kind": unit.kind,
                "goal_id": unit.context.get("goal_id"),
                "step_text": extras.get("step_text"),
                "plan_step_number": extras.get("plan_step_number"),
                "plan_step_total": extras.get("plan_step_total"),
            },
        )

    def _build_resume_point(
        self,
        unit: CompilationUnit,
        *,
        task_segment: CompiledTaskSegment,
        payload: dict[str, object] | None = None,
    ) -> ResumePoint:
        return ResumePoint(
            phase="compiled",
            cursor=task_segment.segment_id,
            checkpoint_kind="resume",
            owner_agent_id=task_segment.actor_owner_id,
            payload={
                "unit_id": unit.id,
                "unit_kind": unit.kind,
                "segment_id": task_segment.segment_id,
                **dict(payload or {}),
            },
        )

    def _dispatch_session_id(self, unit: CompilationUnit) -> str:
        explicit_session_id = _string_context_value(unit.context.get("session_id"))
        if explicit_session_id:
            return explicit_session_id
        goal_id = unit.context.get("goal_id")
        if goal_id:
            return str(goal_id)
        return unit.id

    def _compiled_task_id(self, unit: CompilationUnit, index: int) -> str:
        return f"ctask:{unit.id}:{index + 1}"

    def _assignment_plan_payload(self, unit: CompilationUnit) -> dict[str, object]:
        envelope = unit.context.get("assignment_plan_envelope")
        if not isinstance(envelope, dict):
            return {}
        checkpoints = unit.context.get("assignment_plan_checkpoints")
        acceptance_criteria = unit.context.get("assignment_plan_acceptance_criteria")
        sidecar_plan = unit.context.get("assignment_sidecar_plan")
        resolved_sidecar_plan = (
            dict(sidecar_plan)
            if isinstance(sidecar_plan, dict)
            else dict(envelope.get("sidecar_plan"))
            if isinstance(envelope.get("sidecar_plan"), dict)
            else {}
        )
        payload = {
            "assignment_plan_envelope": dict(envelope),
            "assignment_plan_checkpoints": _checkpoint_context_list(
                checkpoints if isinstance(checkpoints, list) else envelope.get("checkpoints"),
            ),
            "assignment_plan_acceptance_criteria": _string_context_list(
                acceptance_criteria
                if isinstance(acceptance_criteria, list)
                else envelope.get("acceptance_criteria"),
            ),
            "assignment_sidecar_plan": resolved_sidecar_plan,
        }
        execution_path_guidance = _execution_path_guidance_payload(
            {"assignment_sidecar_plan": resolved_sidecar_plan},
        )
        if execution_path_guidance:
            payload["execution_path_guidance"] = execution_path_guidance
        return payload


def _string_context_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _merge_string_context_lists(*values: object) -> list[str]:
    merged: list[str] = []
    for value in values:
        if isinstance(value, str):
            merged.append(value)
            continue
        if isinstance(value, list):
            merged.extend(
                item
                for item in value
                if isinstance(item, str)
            )
    return _string_context_list(merged)


def _string_context_value(*values: object) -> str | None:
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if text:
            return text
    return None


def _checkpoint_context_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    checkpoints: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        checkpoints.append(dict(item))
    return checkpoints


def _mapping_context_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, dict):
            items.append(dict(item))
    return items


def _path_context_summary(value: object) -> str | None:
    if isinstance(value, dict):
        return _string_context_value(value.get("summary"), value.get("label"))
    return _string_context_value(getattr(value, "summary", None), getattr(value, "label", None))


def _path_context_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, object]] = []
    for entry in value:
        if isinstance(entry, dict):
            if _path_context_summary(entry) is None:
                continue
            items.append(dict(entry))
            continue
        summary = _path_context_summary(entry)
        if summary is None:
            continue
        items.append(
            {
                "summary": summary,
                "path_type": _string_context_value(getattr(entry, "path_type", None)),
                "relation_ids": _string_context_list(getattr(entry, "relation_ids", None)),
                "relation_kinds": _string_context_list(getattr(entry, "relation_kinds", None)),
                "source_refs": _string_context_list(getattr(entry, "source_refs", None)),
                "evidence_refs": _string_context_list(getattr(entry, "evidence_refs", None)),
            },
        )
    return items


def _execution_path_guidance_payload(context: dict[str, object]) -> dict[str, object]:
    sidecar_plan = context.get("assignment_sidecar_plan")
    if not isinstance(sidecar_plan, dict):
        return {}
    knowledge_subgraph = (
        dict(sidecar_plan.get("knowledge_subgraph"))
        if isinstance(sidecar_plan.get("knowledge_subgraph"), dict)
        else {}
    )
    dependency_paths = _path_context_list(knowledge_subgraph.get("dependency_paths"))
    blocker_paths = _path_context_list(knowledge_subgraph.get("blocker_paths"))
    recovery_paths = _path_context_list(knowledge_subgraph.get("recovery_paths"))
    contradiction_paths = _path_context_list(knowledge_subgraph.get("contradiction_paths"))
    execution_ordering_hints = _merge_string_context_lists(
        sidecar_plan.get("execution_ordering_hints"),
        [entry.get("summary") for entry in dependency_paths],
        [entry.get("summary") for entry in blocker_paths],
        [entry.get("summary") for entry in recovery_paths],
        [entry.get("summary") for entry in contradiction_paths],
    )
    if not any(
        (
            execution_ordering_hints,
            dependency_paths,
            blocker_paths,
            recovery_paths,
            contradiction_paths,
        ),
    ):
        return {}
    return {
        "execution_ordering_hints": execution_ordering_hints,
        "dependency_paths": dependency_paths,
        "blocker_paths": blocker_paths,
        "recovery_paths": recovery_paths,
        "contradiction_paths": contradiction_paths,
    }


def _execution_path_guidance_lines(context: dict[str, object]) -> list[str]:
    guidance = _execution_path_guidance_payload(context)
    if not guidance:
        return []
    lines = ["Execution path guidance for this assignment:"]
    ordering_hints = _string_context_list(guidance.get("execution_ordering_hints"))
    if ordering_hints:
        lines.extend(f"- {item}" for item in ordering_hints[:4])
    dependency_paths = _path_context_list(guidance.get("dependency_paths"))
    if dependency_paths:
        lines.append("Resolve these dependencies first:")
        lines.extend(
            f"- {summary}"
            for entry in dependency_paths[:3]
            if (summary := _path_context_summary(entry)) is not None
        )
    blocker_paths = _path_context_list(guidance.get("blocker_paths"))
    if blocker_paths:
        lines.append("Known blockers that should stop forward motion:")
        lines.extend(
            f"- {summary}"
            for entry in blocker_paths[:3]
            if (summary := _path_context_summary(entry)) is not None
        )
    recovery_paths = _path_context_list(guidance.get("recovery_paths"))
    if recovery_paths:
        lines.append("Preferred recovery moves when blocked:")
        lines.extend(
            f"- {summary}"
            for entry in recovery_paths[:3]
            if (summary := _path_context_summary(entry)) is not None
        )
    contradiction_paths = _path_context_list(guidance.get("contradiction_paths"))
    if contradiction_paths:
        lines.append("Contradictions to resolve before claiming success:")
        lines.extend(
            f"- {summary}"
            for entry in contradiction_paths[:3]
            if (summary := _path_context_summary(entry)) is not None
        )
    return lines


def _runtime_execution_prompt_lines(context: dict[str, object]) -> list[str]:
    industry_label = _string_context_value(context.get("industry_label"))
    role_name = _string_context_value(
        context.get("industry_role_name"),
        context.get("role_name"),
    )
    role_summary = _string_context_value(context.get("role_summary"))
    mission = _string_context_value(context.get("mission"))
    industry_role_id = _string_context_value(context.get("industry_role_id"))
    task_mode = _string_context_value(context.get("task_mode"))
    task_mode_label = describe_industry_task_mode(task_mode)
    environment_constraints = _string_context_list(
        context.get("environment_constraints"),
    )
    evidence_expectations = _string_context_list(
        context.get("evidence_expectations"),
    )
    if not any(
        [
            industry_label,
            role_name,
            role_summary,
            mission,
            environment_constraints,
            evidence_expectations,
            task_mode_label,
        ],
    ):
        return []
    lines = ["Runtime role framing for this execution:"]
    if industry_label:
        lines.append(f"- Industry team: {industry_label}")
    if role_name:
        lines.append(f"- Active role: {role_name}")
    if role_summary:
        lines.append(f"- Role summary: {role_summary}")
    if mission:
        lines.append(f"- Mission: {mission}")
    if task_mode_label:
        lines.append(f"- Task mode: {task_mode_label}")
    if environment_constraints:
        lines.append(
            "- Environment constraints: " + ", ".join(environment_constraints[:4])
        )
    if evidence_expectations:
        lines.append(
            "- Evidence expectations: " + ", ".join(evidence_expectations[:4])
        )
    is_execution_core_runtime = industry_role_id == EXECUTION_CORE_ROLE_ID
    role_contract_lines = build_role_execution_contract_lines(
        role_id=industry_role_id,
        is_execution_core_runtime=is_execution_core_runtime,
    )
    task_contract_lines = build_task_mode_contract_lines(task_mode)
    evidence_contract_lines = build_evidence_contract_lines(
        task_mode=task_mode,
        is_execution_core_runtime=is_execution_core_runtime,
    )
    if role_contract_lines:
        lines.append("- Role contract:")
        lines.extend(role_contract_lines)
    if task_contract_lines:
        lines.append("- Task mode contract:")
        lines.extend(task_contract_lines)
    if evidence_contract_lines:
        lines.append("- Evidence contract:")
        lines.extend(evidence_contract_lines)
    return lines


def _request_context_payload(
    context: dict[str, object],
    *,
    owner_agent_id: str,
) -> dict[str, object]:
    payload: dict[str, object] = {"agent_id": owner_agent_id}
    session_id = _string_context_value(context.get("session_id"))
    control_thread_id = _string_context_value(
        context.get("control_thread_id"),
        session_id,
    )
    thread_id = _string_context_value(
        context.get("thread_id"),
        control_thread_id,
        session_id,
    )
    for key in (
        "owner_scope",
        "industry_instance_id",
        "industry_role_id",
        "industry_label",
        "lane_id",
        "cycle_id",
        "assignment_id",
        "work_context_id",
        "report_back_mode",
        "session_kind",
        "task_mode",
        "session_id",
        "environment_ref",
    ):
        value = _string_context_value(context.get(key))
        if value is not None:
            payload[key] = value
    if control_thread_id is not None:
        payload["control_thread_id"] = control_thread_id
    if thread_id is not None:
        payload["thread_id"] = thread_id
    role_name = _string_context_value(
        context.get("industry_role_name"),
        context.get("role_name"),
    )
    if role_name is not None:
        payload["industry_role_name"] = role_name
    return payload


def _runtime_continuity_payload(context: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {}
    session_id = _string_context_value(context.get("session_id"))
    control_thread_id = _string_context_value(
        context.get("control_thread_id"),
        session_id,
    )
    thread_id = _string_context_value(
        context.get("thread_id"),
        control_thread_id,
        session_id,
    )
    for key in ("work_context_id", "environment_ref"):
        value = _string_context_value(context.get(key))
        if value is not None:
            payload[key] = value
    if session_id is not None:
        payload["session_id"] = session_id
    if control_thread_id is not None:
        payload["control_thread_id"] = control_thread_id
    if thread_id is not None:
        payload["thread_id"] = thread_id
    return payload


def _feedback_prompt_lines(context: dict[str, object]) -> list[str]:
    feedback_items = _string_context_list(context.get("feedback_items"))
    next_plan_hints = _string_context_list(context.get("next_plan_hints"))
    current_stage = _string_context_value(context.get("current_stage"))
    recent_failures = _string_context_list(context.get("recent_failures"))
    effective_actions = _string_context_list(context.get("effective_actions"))
    avoid_repeats = _string_context_list(context.get("avoid_repeats"))
    feedback_summary = context.get("feedback_summary")
    lines: list[str] = []
    if current_stage:
        lines.append("Current execution stage to continue from:")
        lines.append(f"- {current_stage}")
    if feedback_items or (
        isinstance(feedback_summary, str) and feedback_summary.strip()
    ):
        lines.append("Recent learning feedback to absorb before planning:")
        if feedback_items:
            lines.extend(f"- {item}" for item in feedback_items[:6])
        elif isinstance(feedback_summary, str):
            lines.append(f"- {feedback_summary.strip()}")
    if recent_failures:
        lines.append("Recent failures to avoid repeating:")
        lines.extend(f"- {item}" for item in recent_failures[:4])
    if effective_actions:
        lines.append("Recently effective moves to reuse:")
        lines.extend(f"- {item}" for item in effective_actions[:4])
    if avoid_repeats:
        lines.append("Do not repeat these patterns:")
        lines.extend(f"- {item}" for item in avoid_repeats[:4])
    if next_plan_hints:
        lines.append("Bias the next plan toward these validated directions:")
        lines.extend(f"- {item}" for item in next_plan_hints[:4])
    return lines


def _strategy_prompt_lines(context: dict[str, object]) -> list[str]:
    strategy_items = _string_context_list(context.get("strategy_items"))
    strategy_summary = context.get("strategy_summary")
    lines: list[str] = []
    if strategy_items or (
        isinstance(strategy_summary, str) and strategy_summary.strip()
    ):
        lines.append("Strategic directives that must frame this execution:")
        if strategy_items:
            lines.extend(f"- {item}" for item in strategy_items[:8])
        elif isinstance(strategy_summary, str):
            lines.append(f"- {strategy_summary.strip()}")
    return lines


def _knowledge_prompt_lines(context: dict[str, object]) -> list[str]:
    knowledge_items = _string_context_list(context.get("knowledge_items"))
    memory_items = _string_context_list(context.get("memory_items"))
    lines: list[str] = []
    if knowledge_items:
        lines.append("Relevant knowledge to use before acting:")
        lines.extend(f"- {item}" for item in knowledge_items[:5])
    if memory_items:
        if lines:
            lines.append("")
        lines.append("Long-term memory facts to preserve in this execution:")
        lines.extend(f"- {item}" for item in memory_items[:5])
    return lines
