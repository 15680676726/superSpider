# -*- coding: utf-8 -*-
"""Assignment-local planning shell that stays sidecar to formal truth ids."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...state import BacklogItemRecord, OperatingLaneRecord
from .models import (
    AssignmentPlanEnvelope,
    PlanningStrategyConstraints,
    build_planning_shell_payload,
    project_task_subgraph_to_planning_focus,
)


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


class _AssignmentPlanningInput(BaseModel):
    """Typed bridge from loose compiler context into assignment planning input."""

    model_config = ConfigDict(from_attributes=True)

    assignment_id: str
    backlog_item_id: str | None = None
    industry_instance_id: str = "compiler-context"
    lane_id: str | None = None
    cycle_id: str | None = None
    goal_title: str | None = None
    title: str | None = None
    goal_summary: str | None = None
    summary: str | None = None
    assignment_metadata: dict[str, Any] = Field(default_factory=dict)
    plan_steps: list[str] = Field(default_factory=list)
    plan_acceptance_criteria: list[str] = Field(default_factory=list)
    plan_dependencies: list[dict[str, Any]] = Field(default_factory=list)
    plan_resource_requirements: list[dict[str, Any]] = Field(default_factory=list)
    plan_capacity_requirements: list[dict[str, Any]] = Field(default_factory=list)
    plan_retry_policy: dict[str, Any] = Field(default_factory=dict)
    plan_local_replan_policy: dict[str, Any] = Field(default_factory=dict)
    report_back_mode: str | None = None
    lane_title: str | None = None
    owner_agent_id: str | None = None
    industry_role_id: str | None = None

    @classmethod
    def from_context(
        cls,
        context: Mapping[str, object],
    ) -> _AssignmentPlanningInput | None:
        assignment_id = _string(context.get("assignment_id"))
        if assignment_id is None:
            return None
        assignment_metadata = (
            dict(context.get("assignment_metadata"))
            if isinstance(context.get("assignment_metadata"), Mapping)
            else {}
        )
        return cls(
            assignment_id=assignment_id,
            backlog_item_id=_string(context.get("backlog_item_id")),
            industry_instance_id=_string(context.get("industry_instance_id")) or "compiler-context",
            lane_id=_string(context.get("lane_id")),
            cycle_id=_string(context.get("cycle_id")),
            goal_title=_string(context.get("goal_title")),
            title=_string(context.get("title")),
            goal_summary=_string(context.get("goal_summary")),
            summary=_string(context.get("summary")),
            assignment_metadata=assignment_metadata,
            plan_steps=_string_list(context.get("plan_steps")),
            plan_acceptance_criteria=_string_list(context.get("plan_acceptance_criteria")),
            plan_dependencies=_contract_entries(
                context.get("plan_dependencies"),
                string_key="label",
            ),
            plan_resource_requirements=_contract_entries(
                context.get("plan_resource_requirements"),
                string_key="resource_ref",
            ),
            plan_capacity_requirements=_contract_entries(
                context.get("plan_capacity_requirements"),
                string_key="capacity_ref",
            ),
            plan_retry_policy=_mapping(context.get("plan_retry_policy")),
            plan_local_replan_policy=_mapping(context.get("plan_local_replan_policy")),
            report_back_mode=_string(context.get("report_back_mode")),
            lane_title=_string(context.get("lane_title")),
            owner_agent_id=_string(context.get("owner_agent_id")),
            industry_role_id=_string(context.get("industry_role_id")),
        )

    def resolved_assignment_metadata(self) -> dict[str, Any]:
        metadata = dict(self.assignment_metadata)
        if "plan_steps" not in metadata and self.plan_steps:
            metadata["plan_steps"] = list(self.plan_steps)
        if "acceptance_criteria" not in metadata and self.plan_acceptance_criteria:
            metadata["acceptance_criteria"] = list(self.plan_acceptance_criteria)
        if "dependencies" not in metadata and self.plan_dependencies:
            metadata["dependencies"] = list(self.plan_dependencies)
        if "resource_requirements" not in metadata and self.plan_resource_requirements:
            metadata["resource_requirements"] = list(self.plan_resource_requirements)
        if "capacity_requirements" not in metadata and self.plan_capacity_requirements:
            metadata["capacity_requirements"] = list(self.plan_capacity_requirements)
        if "retry_policy" not in metadata and self.plan_retry_policy:
            metadata["retry_policy"] = dict(self.plan_retry_policy)
        if "local_replan_policy" not in metadata and self.plan_local_replan_policy:
            metadata["local_replan_policy"] = dict(self.plan_local_replan_policy)
        if "report_back_mode" not in metadata and self.report_back_mode is not None:
            metadata["report_back_mode"] = self.report_back_mode
        return metadata

    def backlog_item(self) -> BacklogItemRecord:
        return BacklogItemRecord(
            id=self.backlog_item_id or f"assignment:{self.assignment_id}",
            industry_instance_id=self.industry_instance_id,
            lane_id=self.lane_id,
            cycle_id=self.cycle_id,
            assignment_id=self.assignment_id,
            title=self.goal_title or self.title or "Assignment",
            summary=self.goal_summary or self.summary or "",
            metadata=self.resolved_assignment_metadata(),
        )

    def lane(self, *, industry_instance_id: str) -> OperatingLaneRecord | None:
        if (
            self.lane_id is None
            and self.owner_agent_id is None
            and self.industry_role_id is None
        ):
            return None
        return OperatingLaneRecord(
            id=self.lane_id or f"lane:{self.assignment_id}",
            industry_instance_id=industry_instance_id,
            lane_key=self.lane_id or "assignment",
            title=self.lane_title or "Assignment lane",
            owner_agent_id=self.owner_agent_id,
            owner_role_id=self.industry_role_id,
        )


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
        task_subgraph: object | None = None,
    ) -> AssignmentPlanEnvelope:
        constraints = PlanningStrategyConstraints.from_value(strategy_constraints)
        knowledge_subgraph = project_task_subgraph_to_planning_focus(task_subgraph)
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
        checkpoints.extend(
            {"kind": "capability-ready", "label": label}
            for label in list(knowledge_subgraph.get("capability_labels") or [])
        )
        checkpoints.extend(
            {"kind": "environment-ready", "label": label}
            for label in list(knowledge_subgraph.get("environment_labels") or [])
        )
        checkpoints.extend(
            {"kind": "failure-watch", "label": label}
            for label in list(knowledge_subgraph.get("failure_patterns") or [])
        )
        checkpoints.extend(
            {"kind": "dependency-path", "label": str(entry.get("summary"))}
            for entry in list(knowledge_subgraph.get("dependency_paths") or [])
            if _string(entry.get("summary")) is not None
        )
        checkpoints.extend(
            {"kind": "blocker-path", "label": str(entry.get("summary"))}
            for entry in list(knowledge_subgraph.get("blocker_paths") or [])
            if _string(entry.get("summary")) is not None
        )
        checkpoints.extend(
            {"kind": "recovery-path", "label": str(entry.get("summary"))}
            for entry in list(knowledge_subgraph.get("recovery_paths") or [])
            if _string(entry.get("summary")) is not None
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
        if knowledge_subgraph.get("constraint_refs"):
            acceptance_criteria = _string_list(
                acceptance_criteria,
                list(knowledge_subgraph.get("constraint_refs") or []),
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
        execution_ordering_hints = _string_list(
            [entry.get("summary") for entry in list(knowledge_subgraph.get("dependency_paths") or [])],
            [entry.get("summary") for entry in list(knowledge_subgraph.get("blocker_paths") or [])],
            [entry.get("summary") for entry in list(knowledge_subgraph.get("recovery_paths") or [])],
            [entry.get("summary") for entry in list(knowledge_subgraph.get("contradiction_paths") or [])],
        )
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
                "knowledge_subgraph": dict(knowledge_subgraph),
                "execution_ordering_hints": execution_ordering_hints,
            },
            planning_shell=build_planning_shell_payload(
                mode="assignment-planning-shell",
                scope="assignment",
                plan_id=f"assignment:{assignment_id}:plan",
                resume_key=f"assignment:{assignment_id}",
                fork_key=(
                    f"backlog:{backlog_item.id}"
                    if backlog_item.id
                    else "backlog:unresolved"
                ),
                verify_reminder=(
                    "Verify assignment output and supporting evidence before "
                    "reporting back or requesting local replan."
                ),
            ),
            metadata={
                "source_ref": backlog_item.source_ref,
                "source_kind": backlog_item.source_kind,
                "affected_relation_ids": list(knowledge_subgraph.get("relation_ids") or []),
                "affected_relation_kinds": list(
                    knowledge_subgraph.get("top_relation_kinds") or [],
                ),
                "relation_source_refs": list(
                    knowledge_subgraph.get("relation_source_refs") or [],
                ),
                "knowledge_focus_node_ids": list(
                    knowledge_subgraph.get("focus_node_ids") or [],
                ),
                "knowledge_seed_refs": list(knowledge_subgraph.get("seed_refs") or []),
            },
        )

    def plan_from_context(
        self,
        context: Mapping[str, object],
        *,
        strategy_constraints: PlanningStrategyConstraints | None = None,
    ) -> AssignmentPlanEnvelope | None:
        planning_input = _AssignmentPlanningInput.from_context(context)
        if planning_input is None:
            return None
        backlog_item = planning_input.backlog_item()
        lane = planning_input.lane(industry_instance_id=backlog_item.industry_instance_id)
        return self.plan(
            assignment_id=planning_input.assignment_id,
            cycle_id=planning_input.cycle_id,
            backlog_item=backlog_item,
            lane=lane,
            strategy_constraints=PlanningStrategyConstraints.from_value(strategy_constraints),
            task_subgraph=context.get("task_subgraph"),
        )
