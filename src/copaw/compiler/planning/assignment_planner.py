# -*- coding: utf-8 -*-
"""Assignment-local planning shell that stays sidecar to formal truth ids."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ...state import BacklogItemRecord, OperatingLaneRecord
from .models import AssignmentPlanEnvelope, PlanningStrategyConstraints


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(*values: object) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        if isinstance(value, str):
            candidates = [value]
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            candidates = list(value)
        else:
            candidates = []
        for candidate in candidates:
            text = _string(candidate)
            if text is None or text in seen:
                continue
            seen.add(text)
            items.append(text)
    return items


def _mapping(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _contract_entries(
    value: object | None,
    *,
    string_key: str,
) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        candidates = list(value)
    else:
        candidates = [value]
    entries: list[dict[str, Any]] = []
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            entries.append(dict(candidate))
            continue
        text = _string(candidate)
        if text is not None:
            entries.append({string_key: text})
    return entries


class AssignmentPlanningCompiler:
    """Compile a bounded assignment-local planning envelope."""

    def plan(
        self,
        *,
        assignment_id: str,
        cycle_id: str | None,
        backlog_item: BacklogItemRecord,
        lane: OperatingLaneRecord | None,
        strategy_constraints: PlanningStrategyConstraints | None = None,
    ) -> AssignmentPlanEnvelope:
        constraints = strategy_constraints or PlanningStrategyConstraints()
        metadata = dict(backlog_item.metadata or {})
        dependencies = _contract_entries(
            metadata.get("dependencies"),
            string_key="label",
        )
        resource_requirements = _contract_entries(
            metadata.get("resource_requirements"),
            string_key="resource_ref",
        )
        capacity_requirements = _contract_entries(
            metadata.get("capacity_requirements"),
            string_key="capacity_ref",
        )
        retry_policy = _mapping(metadata.get("retry_policy"))
        local_replan_policy = _mapping(metadata.get("local_replan_policy"))
        plan_steps = _string_list(metadata.get("plan_steps"))
        if not plan_steps:
            plan_steps = [
                f"Clarify the objective for {backlog_item.title}.",
                "Execute the governed move and capture evidence.",
            ]
        checkpoints = [
            {
                "kind": "dependency",
                "label": (
                    _string(entry.get("label"))
                    or _string(entry.get("dependency_id"))
                    or "dependency"
                ),
            }
            for entry in dependencies
        ] + [
            {"kind": "plan-step", "label": step}
            for step in plan_steps
        ]
        checkpoints.extend(
            {
                "kind": "resource-ready",
                "label": (
                    _string(entry.get("resource_ref"))
                    or _string(entry.get("label"))
                    or "resource"
                ),
            }
            for entry in resource_requirements
        )
        checkpoints.extend(
            {
                "kind": "capacity-ready",
                "label": (
                    _string(entry.get("capacity_ref"))
                    or _string(entry.get("label"))
                    or "capacity"
                ),
            }
            for entry in capacity_requirements
        )
        if not any("verify" in step.lower() for step in plan_steps):
            checkpoints.append(
                {"kind": "verify", "label": "Verify the result and supporting evidence."},
            )
        checkpoints.append(
            {"kind": "report-back", "label": "Report the result back to the main brain."},
        )
        acceptance_criteria = _string_list(
            metadata.get("acceptance_criteria"),
            metadata.get("evidence_expectations"),
            f"Complete the assigned backlog item: {backlog_item.title}.",
        )
        if _string(backlog_item.summary) is not None:
            acceptance_criteria = _string_list(
                acceptance_criteria,
                f"Outcome stays aligned with: {backlog_item.summary}",
            )
        if "prefer-evidence-before-external-move" in list(constraints.planning_policy or []):
            acceptance_criteria = _string_list(
                acceptance_criteria,
                "Evidence is captured before any external move is reported complete.",
            )
        owner_agent_id = _string(metadata.get("owner_agent_id")) or (
            lane.owner_agent_id if lane is not None else None
        )
        owner_role_id = _string(metadata.get("industry_role_id")) or (
            lane.owner_role_id if lane is not None else None
        )
        report_back_mode = _string(metadata.get("report_back_mode")) or "summary"
        return AssignmentPlanEnvelope(
            assignment_id=assignment_id,
            backlog_item_id=backlog_item.id,
            lane_id=backlog_item.lane_id,
            cycle_id=cycle_id,
            owner_agent_id=owner_agent_id,
            owner_role_id=owner_role_id,
            report_back_mode=report_back_mode,
            checkpoints=checkpoints,
            acceptance_criteria=acceptance_criteria,
            dependencies=dependencies,
            resource_requirements=resource_requirements,
            capacity_requirements=capacity_requirements,
            retry_policy=retry_policy,
            local_replan_policy=local_replan_policy,
            sidecar_plan={
                "checklist": list(plan_steps),
                "dependencies": dependencies,
                "resource_requirements": resource_requirements,
                "capacity_requirements": capacity_requirements,
                "retry_policy": retry_policy,
                "local_replan_policy": local_replan_policy,
                "planning_policy": list(constraints.planning_policy or []),
            },
            metadata={
                "source_ref": backlog_item.source_ref,
                "source_kind": backlog_item.source_kind,
            },
        )

    def plan_from_context(
        self,
        context: Mapping[str, object],
        *,
        strategy_constraints: PlanningStrategyConstraints | None = None,
    ) -> AssignmentPlanEnvelope | None:
        assignment_id = _string(context.get("assignment_id"))
        if assignment_id is None:
            return None
        assignment_metadata = (
            dict(context.get("assignment_metadata"))
            if isinstance(context.get("assignment_metadata"), dict)
            else {}
        )
        if "plan_steps" not in assignment_metadata and context.get("plan_steps") is not None:
            assignment_metadata["plan_steps"] = list(_string_list(context.get("plan_steps")))
        if (
            "acceptance_criteria" not in assignment_metadata
            and context.get("plan_acceptance_criteria") is not None
        ):
            assignment_metadata["acceptance_criteria"] = list(
                _string_list(context.get("plan_acceptance_criteria")),
            )
        if (
            "dependencies" not in assignment_metadata
            and context.get("plan_dependencies") is not None
        ):
            assignment_metadata["dependencies"] = _contract_entries(
                context.get("plan_dependencies"),
                string_key="label",
            )
        if (
            "resource_requirements" not in assignment_metadata
            and context.get("plan_resource_requirements") is not None
        ):
            assignment_metadata["resource_requirements"] = _contract_entries(
                context.get("plan_resource_requirements"),
                string_key="resource_ref",
            )
        if (
            "capacity_requirements" not in assignment_metadata
            and context.get("plan_capacity_requirements") is not None
        ):
            assignment_metadata["capacity_requirements"] = _contract_entries(
                context.get("plan_capacity_requirements"),
                string_key="capacity_ref",
            )
        if (
            "retry_policy" not in assignment_metadata
            and isinstance(context.get("plan_retry_policy"), Mapping)
        ):
            assignment_metadata["retry_policy"] = dict(context.get("plan_retry_policy"))
        if (
            "local_replan_policy" not in assignment_metadata
            and isinstance(context.get("plan_local_replan_policy"), Mapping)
        ):
            assignment_metadata["local_replan_policy"] = dict(
                context.get("plan_local_replan_policy"),
            )
        if (
            "report_back_mode" not in assignment_metadata
            and _string(context.get("report_back_mode")) is not None
        ):
            assignment_metadata["report_back_mode"] = _string(context.get("report_back_mode"))
        backlog_item = BacklogItemRecord(
            id=_string(context.get("backlog_item_id")) or f"assignment:{assignment_id}",
            industry_instance_id=_string(context.get("industry_instance_id")) or "compiler-context",
            lane_id=_string(context.get("lane_id")),
            cycle_id=_string(context.get("cycle_id")),
            assignment_id=assignment_id,
            title=(
                _string(context.get("goal_title"))
                or _string(context.get("title"))
                or "Assignment"
            ),
            summary=(
                _string(context.get("goal_summary"))
                or _string(context.get("summary"))
                or ""
            ),
            metadata=assignment_metadata,
        )
        lane_id = _string(context.get("lane_id"))
        lane = (
            OperatingLaneRecord(
                id=lane_id or f"lane:{assignment_id}",
                industry_instance_id=backlog_item.industry_instance_id,
                lane_key=lane_id or "assignment",
                title=_string(context.get("lane_title")) or "Assignment lane",
                owner_agent_id=_string(context.get("owner_agent_id")),
                owner_role_id=_string(context.get("industry_role_id")),
            )
            if lane_id is not None
            or _string(context.get("owner_agent_id")) is not None
            or _string(context.get("industry_role_id")) is not None
            else None
        )
        return self.plan(
            assignment_id=assignment_id,
            cycle_id=_string(context.get("cycle_id")),
            backlog_item=backlog_item,
            lane=lane,
            strategy_constraints=strategy_constraints,
        )
