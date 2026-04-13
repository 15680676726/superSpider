# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from ..compiler import (
    AssignmentPlanningCompiler,
    CompilationUnit,
    CompiledTaskSegment,
    CompiledTaskSpec,
    PlanningStrategyConstraints,
    ResumePoint,
    SemanticCompiler,
)
from ..evidence import EvidenceLedger, EvidenceRecord
from ..industry.identity import EXECUTION_CORE_AGENT_ID, is_execution_core_role_id
from ..kernel import KernelDispatcher, KernelResult, KernelTask
from ..kernel.persistence import (
    decode_kernel_task_metadata,
    encode_kernel_task_metadata,
)
from ..learning import LearningService
from ..state import (
    GoalOverrideRecord,
    GoalRecord,
    RuntimeFrameRecord,
    TaskRecord,
    TaskRuntimeRecord,
)
from ..state.execution_feedback import collect_recent_execution_feedback
from ..state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteGoalOverrideRepository,
    SqliteGoalRepository,
    SqliteIndustryInstanceRepository,
    SqliteRuntimeFrameRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)
from ..state.strategy_memory_service import resolve_strategy_payload

logger = logging.getLogger(__name__)

_GOAL_TERMINAL_TASK_STATUSES = frozenset({"completed", "failed", "cancelled"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_payload_signature(payload: dict[str, object]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        return repr(sorted(payload.items(), key=lambda item: str(item[0])))




def _serialize_evidence_record(record: EvidenceRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "task_id": record.task_id,
        "actor_ref": record.actor_ref,
        "environment_ref": record.environment_ref,
        "capability_ref": record.capability_ref,
        "risk_level": record.risk_level,
        "action_summary": record.action_summary,
        "result_summary": record.result_summary,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "status": record.status,
        "metadata": dict(record.metadata),
        "artifact_count": len(record.artifacts),
        "replay_count": len(record.replay_pointers),
    }


def _parse_metadata(diff_summary: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for chunk in (diff_summary or "").split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            metadata[key] = value
    return metadata


def _first_non_empty(metadata: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if value:
            return value
    return None


def _compiler_task_summary(task: KernelTask) -> str:
    task_seed = _mapping(task.payload.get("task_seed"))
    request_preview = task_seed.get("request_preview")
    if isinstance(request_preview, str) and request_preview.strip():
        return request_preview.strip()[:280]

    compiler = _mapping(task.payload.get("compiler"))
    prompt_text = compiler.get("prompt_text")
    if isinstance(prompt_text, str) and prompt_text.strip():
        return prompt_text.strip()[:280]

    if task.environment_ref:
        return (
            f"Compiler seed for {task.capability_ref or 'system:dispatch_query'} "
            f"on {task.environment_ref}."
        )
    return f"Compiler seed for {task.capability_ref or 'system:dispatch_query'}."


def _compiler_seed_source(task: KernelTask) -> str:
    compiler = _mapping(task.payload.get("compiler"))
    unit_kind = str(compiler.get("unit_kind") or "task")
    unit_id = str(compiler.get("unit_id") or task.id)
    return f"compiler:{unit_kind}:{unit_id}"


def _compiler_constraints_summary(task: KernelTask) -> str | None:
    compiler = _mapping(task.payload.get("compiler"))
    request = _mapping(task.payload.get("request"))
    evidence_refs = [
        str(ref)
        for ref in (
            compiler.get("evidence_refs")
            if isinstance(compiler.get("evidence_refs"), list)
            else []
        )
        if isinstance(ref, str) and ref
    ]
    knowledge_refs = _string_list(
        compiler.get("knowledge_refs"),
        _mapping(task.payload.get("task_seed")).get("knowledge_refs"),
    )
    memory_refs = _string_list(
        compiler.get("memory_refs"),
        _mapping(task.payload.get("task_seed")).get("memory_refs"),
    )
    parts = [
        (
            f"goal_id={compiler.get('goal_id')}"
            if compiler.get("goal_id")
            else None
        ),
        (
            f"plan_step={compiler.get('step_text')}"
            if compiler.get("step_text")
            else None
        ),
        (
            f"channel={request.get('channel')}"
            if request.get("channel")
            else None
        ),
        (
            f"evidence_refs={','.join(evidence_refs)}"
            if evidence_refs
            else None
        ),
        (
            f"knowledge_refs={','.join(knowledge_refs)}"
            if knowledge_refs
            else None
        ),
        (
            f"memory_refs={','.join(memory_refs)}"
            if memory_refs
            else None
        ),
    ]
    values = [str(part) for part in parts if part]
    return "; ".join(values) if values else None


def _task_compiler_meta(task: TaskRecord) -> dict[str, object]:
    metadata = decode_kernel_task_metadata(task.acceptance_criteria)
    if metadata is None:
        return {}
    payload = metadata.get("payload")
    if not isinstance(payload, dict):
        return {}
    meta = _mapping(payload.get("meta"))
    compiler = _mapping(payload.get("compiler"))
    merged = {**meta, **compiler}
    if metadata.get("goal_id") and "goal_id" not in merged:
        merged["goal_id"] = metadata["goal_id"]
    if metadata.get("capability_ref") and "capability_ref" not in merged:
        merged["capability_ref"] = metadata["capability_ref"]
    if metadata.get("environment_ref") and "environment_ref" not in merged:
        merged["environment_ref"] = metadata["environment_ref"]
    return merged


def _task_compilation_snapshot(
    task: TaskRecord,
) -> dict[str, CompilationUnit | CompiledTaskSpec] | None:
    metadata = decode_kernel_task_metadata(task.acceptance_criteria)
    if metadata is None:
        return None
    payload = metadata.get("payload")
    if not isinstance(payload, dict):
        return None
    compiler = _task_compiler_meta(task)
    if compiler.get("source_kind") != "compiler":
        return None
    unit_id = compiler.get("unit_id")
    unit_kind = compiler.get("unit_kind")
    if not isinstance(unit_id, str) or not unit_id or not isinstance(unit_kind, str):
        return None

    compiled_at = _parse_datetime(
        compiler.get("compiled_at"),
    ) or task.updated_at
    request = _mapping(payload.get("request"))
    source_text = _first_non_empty(
        {
            "prompt_text": str(compiler.get("prompt_text") or ""),
            "goal_summary": str(compiler.get("goal_summary") or ""),
            "goal_title": str(compiler.get("goal_title") or ""),
        },
        "prompt_text",
        "goal_summary",
        "goal_title",
    ) or task.summary or task.title

    context: dict[str, object] = {}
    for key in (
        "goal_id",
        "goal_title",
        "goal_summary",
        "owner_agent_id",
        "actor_owner_id",
        "strategy_id",
        "strategy_summary",
        "strategy_mission",
        "strategy_north_star",
        "step_index",
        "step_text",
        "plan_step_number",
        "plan_step_total",
        "feedback_summary",
        "assignment_id",
        "backlog_item_id",
        "lane_id",
        "cycle_id",
        "report_back_mode",
        "assignment_plan_envelope",
        "assignment_plan_checkpoints",
        "assignment_plan_acceptance_criteria",
        "assignment_sidecar_plan",
    ):
        value = compiler.get(key)
        if value is not None:
            context[key] = value
    for key in (
        "strategy_items",
        "strategy_priority_order",
        "strategy_planning_policy",
        "strategy_review_rules",
        "strategy_current_focuses",
        "strategy_strategic_uncertainties",
        "strategy_lane_budgets",
    ):
        value = compiler.get(key)
        if isinstance(value, list) and value:
            context[key] = list(value)
    evidence_refs = _string_list(
        compiler.get("evidence_refs"),
        _mapping(payload.get("task_seed")).get("evidence_refs"),
    )
    if evidence_refs:
        context["evidence_refs"] = evidence_refs
    for key in (
        "feedback_items",
        "feedback_patch_ids",
        "feedback_growth_ids",
        "feedback_evidence_refs",
        "next_plan_hints",
        "knowledge_items",
        "knowledge_refs",
        "knowledge_documents",
        "memory_items",
        "memory_refs",
        "memory_documents",
    ):
        values = _string_list(
            compiler.get(key),
            _mapping(payload.get("task_seed")).get(key),
        )
        if values:
            context[key] = values
    request_context = _mapping(compiler.get("request_context"))
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
        "task_mode",
        "session_id",
        "environment_ref",
    ):
        value = request_context.get(key)
        if value is not None and key not in context:
            context[key] = value
    request_role_name = _string(request_context.get("industry_role_name"))
    if request_role_name is not None:
        context.setdefault("industry_role_name", request_role_name)
        context.setdefault("role_name", request_role_name)
    for key in ("session_id", "control_thread_id", "thread_id", "environment_ref"):
        value = _string(compiler.get(key))
        if value is not None:
            context[key] = value
    if not context.get("steps"):
        sidecar_plan = _mapping(compiler.get("assignment_sidecar_plan"))
        checklist = _string_list(sidecar_plan.get("checklist"))
        if checklist:
            context["steps"] = checklist
    channel = request.get("channel")
    if isinstance(channel, str) and channel:
        context["channel"] = channel
    task_segment_payload = _mapping(metadata.get("task_segment")) or _mapping(
        payload.get("task_segment"),
    )
    resume_point_payload = _mapping(metadata.get("resume_point")) or _mapping(
        payload.get("resume_point"),
    )

    spec = CompiledTaskSpec(
        task_id=task.id,
        title=task.title,
        capability_ref=(
            str(metadata.get("capability_ref"))
            if isinstance(metadata.get("capability_ref"), str)
            else task.task_type
        ),
        environment_ref=(
            str(metadata.get("environment_ref"))
            if isinstance(metadata.get("environment_ref"), str)
            else None
        ),
        risk_level=task.current_risk_level,
        payload=payload,
        source_unit_id=unit_id,
        actor_owner_id=next(
            (
                str(value).strip()
                for value in (
                    metadata.get("actor_owner_id"),
                    compiler.get("actor_owner_id"),
                    compiler.get("owner_agent_id"),
                )
                if isinstance(value, str) and str(value).strip()
            ),
            None,
        ),
        task_segment=(
            CompiledTaskSegment.model_validate(task_segment_payload)
            if task_segment_payload
            else None
        ),
        resume_point=(
            ResumePoint.model_validate(resume_point_payload)
            if resume_point_payload
            else None
        ),
    )
    unit = CompilationUnit(
        id=unit_id,
        kind=unit_kind,
        source_text=source_text,
        context=context,
        compiled_at=compiled_at,
    )
    return {"unit": unit, "spec": spec}


def _compiled_spec_sort_key(spec: CompiledTaskSpec) -> tuple[int, str]:
    payload = _mapping(spec.payload)
    step_number = payload.get("plan_step_number")
    step_index = payload.get("step_index")
    for value in (step_number, step_index):
        if isinstance(value, int):
            return value, spec.task_id or spec.title
        if isinstance(value, str) and value.isdigit():
            return int(value), spec.task_id or spec.title
    return 10_000, spec.task_id or spec.title


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(*values: object) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
    return result


def _merge_string_lists(*values: object) -> list[str]:
    return _string_list(*values)


def _dedupe_strings(values: list[str]) -> list[str]:
    return _string_list(values)


def _sort_datetime_value(*values: object) -> str:
    for value in values:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat()
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _knowledge_chunk_brief(chunk: object) -> str:
    title = str(getattr(chunk, "title", "") or "").strip()
    summary = str(getattr(chunk, "summary", "") or "").strip()
    source_ref = str(getattr(chunk, "source_ref", "") or "").strip()
    body = (
        summary
        or str(getattr(chunk, "content_excerpt", "") or "").strip()
        or str(getattr(chunk, "content", "") or "").strip()
    )
    body = body.replace("\n", " ").strip()
    if len(body) > 180:
        body = f"{body[:177].rstrip()}..."
    prefix = title or str(getattr(chunk, "document_id", "") or "").strip() or "Knowledge"
    if source_ref:
        return f"{prefix}: {body} [source: {source_ref}]"
    return f"{prefix}: {body}"


def _memory_chunk_ref(chunk: object) -> str | None:
    for field in ("source_ref", "id", "entry_id"):
        value = str(getattr(chunk, field, "") or "").strip()
        if value:
            return value
    return None


def _build_strategy_memory_items(payload: dict[str, object]) -> list[str]:
    items: list[str] = []
    north_star = payload.get("north_star")
    if isinstance(north_star, str) and north_star.strip():
        items.append(f"North star: {north_star.strip()}")
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        items.append(f"Strategy summary: {summary.strip()}")
    for label, key in (
        ("Priority", "priority_order"),
        ("Thinking axis", "thinking_axes"),
        ("Delegation rule", "delegation_policy"),
        ("Direct execution rule", "direct_execution_policy"),
        ("Execution constraint", "execution_constraints"),
        ("Evidence requirement", "evidence_requirements"),
        ("Current focus", "current_focuses"),
    ):
        values = _string_list(payload.get(key))
        items.extend(f"{label}: {value}" for value in values[:4])
    return items

__all__ = [name for name in globals() if not name.startswith("__")]
