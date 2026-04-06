# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping

from .service_context import *  # noqa: F401,F403
from .service_capability_governance import (
    resolve_industry_capability_governance_service,
)
from .service_recommendation_search import *  # noqa: F401,F403
from .service_recommendation_pack import *  # noqa: F401,F403
from .main_brain_cognitive_surface import build_main_brain_cognitive_surface
from .models import IndustryMainBrainPlanningSurface, IndustrySeatCapabilityLayers
from ..compiler.planning import build_uncertainty_register_payload
from ..state.strategy_memory_service import resolve_strategy_payload


class _IndustryRuntimeViewsMixin:
    def _list_instance_schedules(
        self,
        instance_id: str,
        *,
        schedule_ids: list[str],
    ) -> list[dict[str, Any]]:
        if self._schedule_repository is None:
            return []
        resolved_ids = list(schedule_ids) or self._list_schedule_ids_for_instance(
            instance_id,
        )
        payload: list[dict[str, Any]] = []
        for schedule_id in resolved_ids:
            schedule = self._schedule_repository.get_schedule(schedule_id)
            if schedule is None or schedule.status == "deleted":
                continue
            spec_payload = (
                dict(schedule.spec_payload)
                if isinstance(schedule.spec_payload, dict)
                else {}
            )
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
        payload.sort(
            key=lambda item: _sort_timestamp(item.get("updated_at")),
            reverse=True,
        )
        return payload

    def _list_schedule_ids_for_instance(self, instance_id: str) -> list[str]:
        if self._schedule_repository is None:
            return []
        schedule_ids: list[str] = []
        for schedule in self._schedule_repository.list_schedules():
            if schedule.status == "deleted":
                continue
            spec_payload = (
                dict(schedule.spec_payload)
                if isinstance(schedule.spec_payload, dict)
                else {}
            )
            meta_mapping = (
                dict(spec_payload.get("meta"))
                if isinstance(spec_payload.get("meta"), dict)
                else {}
            )
            if _string(meta_mapping.get("industry_instance_id")) == instance_id:
                schedule_ids.append(schedule.id)
        return schedule_ids

    def _backlog_item_is_chat_writeback(
        self,
        item: dict[str, Any] | None,
    ) -> bool:
        if not isinstance(item, dict):
            return False
        source_ref = str(item.get("source_ref") or "")
        if source_ref.startswith("chat-writeback:"):
            return True
        metadata = _mapping(item.get("metadata"))
        if _string(metadata.get("source")) == "chat-writeback":
            return True
        return _string(item.get("source_kind")) == "operator"

    def _resolve_live_focus_payload(
        self,
        *,
        execution: IndustryExecutionSummary | None,
        assignments: list[dict[str, Any]],
        backlog: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        selected_assignment_id: str | None = None,
        selected_backlog_item_id: str | None = None,
    ) -> dict[str, Any]:
        focus_task = self._pick_execution_focus_task(tasks)
        if focus_task is None and execution is not None and execution.current_task_id:
            focus_task = next(
                (
                    item
                    for item in tasks
                    if _string(_mapping(item.get("task")).get("id"))
                    == _string(execution.current_task_id)
                ),
                None,
            )
        current_task_payload = (
            _mapping(focus_task.get("task")) if isinstance(focus_task, dict) else {}
        )
        current_task_id = _string(current_task_payload.get("id"))
        assignments_by_id = {
            _string(assignment.get("assignment_id")): assignment
            for assignment in assignments
            if _string(assignment.get("assignment_id"))
        }
        current_assignment_id = _string(current_task_payload.get("assignment_id"))
        current_assignment = (
            assignments_by_id.get(selected_assignment_id)
            if selected_assignment_id is not None
            else None
        )
        if (
            current_assignment is None
            and selected_backlog_item_id is not None
        ):
            current_assignment = next(
                (
                    item
                    for item in assignments
                    if _string(item.get("backlog_item_id")) == selected_backlog_item_id
                ),
                None,
            )
        if current_assignment is None:
            current_assignment = (
                assignments_by_id.get(current_assignment_id)
                if current_assignment_id is not None
                else None
            )
        if current_assignment is None and current_task_id is not None:
            current_assignment = next(
                (
                    item
                    for item in assignments
                    if _string(item.get("task_id")) == current_task_id
                ),
                None,
            )
        chat_writeback_items = [
            item
            for item in backlog
            if self._backlog_item_is_chat_writeback(item)
        ]
        latest_writeback = (
            max(
                chat_writeback_items,
                key=lambda item: _sort_timestamp(
                    item.get("updated_at") or item.get("created_at"),
                ),
            )
            if chat_writeback_items
            else None
        )
        if (
            current_assignment is None
            and current_task_id is None
            and selected_assignment_id is None
            and selected_backlog_item_id is None
            and isinstance(latest_writeback, dict)
        ):
            latest_writeback_assignment_id = _string(latest_writeback.get("assignment_id"))
            latest_writeback_backlog_id = _string(latest_writeback.get("backlog_item_id"))
            current_assignment = (
                assignments_by_id.get(latest_writeback_assignment_id)
                if latest_writeback_assignment_id is not None
                else None
            )
            if current_assignment is None and latest_writeback_backlog_id is not None:
                current_assignment = next(
                    (
                        item
                        for item in assignments
                        if _string(item.get("backlog_item_id")) == latest_writeback_backlog_id
                    ),
                    None,
                )
        if current_assignment is None and assignments:
            current_assignment = assignments[0]
        current_assignment_id = (
            _string(current_assignment.get("assignment_id"))
            if isinstance(current_assignment, dict)
            else None
        )
        live_backlog_items = [
            item
            for item in backlog
            if _string(item.get("status")) in {"open", "selected", "materialized"}
        ]
        open_backlog_items = [
            item
            for item in backlog
            if _string(item.get("status")) in {"open", "selected"}
        ]
        live_backlog_items = self._rank_materializable_backlog_items(live_backlog_items)
        open_backlog_items = self._rank_materializable_backlog_items(open_backlog_items)
        report_followup_backlog = next(
            (
                item
                for item in live_backlog_items
                if self._backlog_item_is_report_followup(item)
            ),
            None,
        )
        report_followup_backlog_id = (
            _string(report_followup_backlog.get("backlog_item_id"))
            if isinstance(report_followup_backlog, dict)
            else None
        )
        current_backlog = None
        if selected_backlog_item_id is not None:
            current_backlog = next(
                (
                    item
                    for item in backlog
                    if _string(item.get("backlog_item_id")) == selected_backlog_item_id
                ),
                None,
            )
        if (
            current_backlog is None
            and selected_assignment_id is not None
            and selected_assignment_id == current_assignment_id
            and isinstance(current_assignment, dict)
        ):
            current_backlog = next(
                (
                    item
                    for item in backlog
                    if _string(item.get("backlog_item_id"))
                    == _string(current_assignment.get("backlog_item_id"))
                ),
                None,
            )
        if current_backlog is None:
            current_backlog = (
                next(
                    (
                        item
                        for item in backlog
                        if _string(item.get("backlog_item_id"))
                        == (
                            _string(current_assignment.get("backlog_item_id"))
                            if isinstance(current_assignment, dict)
                            else None
                        )
                    ),
                    None,
                )
                if backlog
                else None
            )
        if current_backlog is None:
            current_backlog = latest_writeback or (
                open_backlog_items[0] if open_backlog_items else None
            )
        current_backlog_id = (
            _string(current_backlog.get("backlog_item_id"))
            if isinstance(current_backlog, dict)
            else None
        )
        if (
            selected_assignment_id is None
            and selected_backlog_item_id is None
            and isinstance(report_followup_backlog, dict)
            and _string(report_followup_backlog.get("backlog_item_id")) != current_backlog_id
        ):
            current_backlog = report_followup_backlog
            current_backlog_id = _string(current_backlog.get("backlog_item_id"))
        current_backlog_status = (
            _string(current_backlog.get("status"))
            if isinstance(current_backlog, dict)
            else None
        )
        current_backlog_is_report_followup = (
            isinstance(current_backlog, dict)
            and (
                self._backlog_item_is_report_followup(current_backlog)
                or _string(current_backlog.get("backlog_item_id")) == report_followup_backlog_id
            )
        )
        current_assignment_status = (
            _string(current_assignment.get("status"))
            if isinstance(current_assignment, dict)
            else None
        )
        assignment_backlog_attached = (
            isinstance(current_assignment, dict)
            and _string(current_assignment.get("backlog_item_id")) == current_backlog_id
            and current_assignment_status not in {"blocked", "cancelled", "completed", "failed"}
        )
        current_focus_title = (
            _string(execution.current_focus)
            if execution is not None
            else None
        )
        current_focus_id = (
            _string(execution.current_focus_id)
            if execution is not None
            else None
        )
        if (
            selected_assignment_id is None
            and selected_backlog_item_id is None
            and
            isinstance(current_backlog, dict)
            and current_backlog_status not in {"open", "selected"}
            and open_backlog_items
            and not assignment_backlog_attached
            and not current_backlog_is_report_followup
            and current_backlog_id != report_followup_backlog_id
        ):
            current_backlog = open_backlog_items[0]
            current_backlog_id = _string(current_backlog.get("backlog_item_id"))
        return {
            "current_assignment": current_assignment,
            "current_assignment_id": current_assignment_id,
            "current_backlog": current_backlog,
            "current_backlog_id": current_backlog_id,
            "current_focus_id": current_focus_id,
            "current_focus_title": current_focus_title,
        }

    def _resolve_cycle_synthesis_payload(
        self,
        cycle_entry: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(cycle_entry, dict):
            return {}
        payload = _mapping(cycle_entry.get("synthesis"))
        if payload:
            return payload
        return _mapping(_mapping(cycle_entry.get("metadata")).get("report_synthesis"))

    def _cycle_has_replan_payload(
        self,
        cycle_entry: dict[str, Any] | None,
    ) -> bool:
        synthesis = self._resolve_cycle_synthesis_payload(cycle_entry)
        replan = self._resolve_report_replan_payload(
            cycle_entry=cycle_entry,
            synthesis=synthesis,
        )
        if replan:
            status = _string(replan.get("status"))
            decision_kind = _string(replan.get("decision_kind"))
            if status == "needs-replan" or decision_kind not in {None, "", "clear"}:
                return True
            if any(
                (
                    list(replan.get("reason_ids") or []),
                    list(replan.get("directives") or []),
                    list(replan.get("recommended_actions") or []),
                )
            ):
                return True
        if not synthesis:
            return False
        return bool(
            synthesis.get("needs_replan")
            or list(synthesis.get("conflicts") or [])
            or list(synthesis.get("holes") or [])
            or list(synthesis.get("replan_reasons") or [])
            or list(synthesis.get("recommended_actions") or [])
        )

    def _resolve_replan_cycle_entry(
        self,
        *,
        current_cycle: dict[str, Any] | None,
        current_cycle_entry: dict[str, Any] | None,
        cycles: Sequence[dict[str, Any]],
    ) -> dict[str, Any] | None:
        current_surface = _mapping(_mapping(current_cycle).get("main_brain_cognitive_surface"))
        if current_surface:
            if not bool(current_surface.get("needs_replan")):
                if isinstance(current_cycle, dict):
                    return current_cycle
                if isinstance(current_cycle_entry, dict):
                    return current_cycle_entry
                return cycles[0] if cycles else None
            judgment_cycle_id = _string(
                _mapping(current_surface.get("judgment")).get("cycle_id"),
            )
            if judgment_cycle_id is not None:
                for candidate in (current_cycle, current_cycle_entry, *cycles):
                    if _string(_mapping(candidate).get("cycle_id")) == judgment_cycle_id:
                        return candidate
        if self._cycle_has_replan_payload(current_cycle):
            return current_cycle
        if self._cycle_has_replan_payload(current_cycle_entry):
            return current_cycle_entry
        for cycle in cycles:
            if self._cycle_has_replan_payload(cycle):
                return cycle
        if isinstance(current_cycle, dict):
            return current_cycle
        if isinstance(current_cycle_entry, dict):
            return current_cycle_entry
        return cycles[0] if cycles else None

    def _propagate_replan_activation_summary(
        self,
        *,
        current_cycle: dict[str, Any] | None,
        replan_cycle: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(current_cycle, dict):
            return current_cycle
        current_synthesis = self._resolve_cycle_synthesis_payload(current_cycle)
        if _mapping(current_synthesis.get("activation")):
            return current_cycle
        replan_synthesis = self._resolve_cycle_synthesis_payload(replan_cycle)
        replan_activation = _mapping(replan_synthesis.get("activation"))
        if not replan_activation:
            return current_cycle
        return {
            **current_cycle,
            "synthesis": {
                **current_synthesis,
                "activation": dict(replan_activation),
            },
        }

    def _resolve_formal_planning_payload(
        self,
        entry: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(entry, dict):
            return {}
        payload = _mapping(entry.get("formal_planning"))
        if payload:
            return payload
        return _mapping(_mapping(entry.get("metadata")).get("formal_planning"))

    def _mapping_list(self, value: object | None) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [dict(item) for item in value if isinstance(item, Mapping)]

    def _build_uncertainty_register_surface_payload(
        self,
        *,
        strategic_uncertainties: Sequence[dict[str, Any]],
        lane_budgets: Sequence[dict[str, Any]],
        strategy_trigger_rules: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        return build_uncertainty_register_payload(
            strategic_uncertainties=strategic_uncertainties,
            lane_budgets=lane_budgets,
            strategy_trigger_rules=strategy_trigger_rules,
            source="industry-runtime-read-model",
        )

    def _strategy_constraints_surface_payload(
        self,
        *,
        record: IndustryInstanceRecord,
        planning_sidecar: Mapping[str, Any],
    ) -> dict[str, Any]:
        compiled_constraints = self._planner_sidecar_payload(
            self._compile_strategy_constraints(record=record),
        )
        strategy_constraints = _mapping(planning_sidecar.get("strategy_constraints"))
        if not strategy_constraints:
            strategy_constraints = compiled_constraints
        strategy_payload = resolve_strategy_payload(
            service=self._strategy_memory_service,
            scope_type="industry",
            scope_id=record.instance_id,
            fallback_owner_agent_ids=(EXECUTION_CORE_AGENT_ID,),
        )
        raw_payload = dict(strategy_payload) if isinstance(strategy_payload, Mapping) else {}
        metadata = _mapping(raw_payload.get("metadata"))
        strategic_uncertainties = self._mapping_list(
            strategy_constraints.get("strategic_uncertainties"),
        ) or self._mapping_list(compiled_constraints.get("strategic_uncertainties")) or self._mapping_list(raw_payload.get("strategic_uncertainties")) or self._mapping_list(
            metadata.get("strategic_uncertainties"),
        )
        lane_budgets = self._mapping_list(strategy_constraints.get("lane_budgets")) or self._mapping_list(
            compiled_constraints.get("lane_budgets")
        ) or self._mapping_list(
            raw_payload.get("lane_budgets"),
        ) or self._mapping_list(metadata.get("lane_budgets"))
        payload = (
            dict(strategy_constraints)
            if strategy_constraints
            else dict(compiled_constraints)
        )
        if strategic_uncertainties:
            payload["strategic_uncertainties"] = strategic_uncertainties
        if lane_budgets:
            payload["lane_budgets"] = lane_budgets
        return payload

    def _strategy_trigger_rules_surface_payload(
        self,
        *,
        record: IndustryInstanceRecord,
        planning_sidecar: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        strategy_constraints = _mapping(planning_sidecar.get("strategy_constraints"))
        compiled_constraints = self._planner_sidecar_payload(
            self._compile_strategy_constraints(record=record),
        )
        strategy_payload = resolve_strategy_payload(
            service=self._strategy_memory_service,
            scope_type="industry",
            scope_id=record.instance_id,
            fallback_owner_agent_ids=(EXECUTION_CORE_AGENT_ID,),
        )
        raw_payload = dict(strategy_payload) if isinstance(strategy_payload, Mapping) else {}
        metadata = _mapping(raw_payload.get("metadata"))
        return self._mapping_list(
            strategy_constraints.get("strategy_trigger_rules"),
        ) or self._mapping_list(compiled_constraints.get("strategy_trigger_rules")) or self._mapping_list(
            raw_payload.get("strategy_trigger_rules"),
        ) or self._mapping_list(metadata.get("strategy_trigger_rules"))

    def _resolve_report_replan_payload(
        self,
        *,
        cycle_entry: dict[str, Any] | None,
        synthesis: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        planning_sidecar = self._resolve_formal_planning_payload(cycle_entry)
        replan_synthesis = (
            synthesis
            if isinstance(synthesis, Mapping)
            else self._resolve_cycle_synthesis_payload(cycle_entry)
        )
        compiled = self._planner_sidecar_payload(
            self._report_replan_engine.compile(replan_synthesis),
        )
        raw_decision = _mapping(_mapping(replan_synthesis).get("replan_decision"))
        sidecar_payload = _mapping(planning_sidecar.get("report_replan"))
        raw_trigger_context = dict(_mapping(raw_decision.get("trigger_context")))
        sidecar_trigger_context = dict(_mapping(sidecar_payload.get("trigger_context")))
        merged_activation = _mapping(compiled.get("activation"))
        sidecar_activation = _mapping(sidecar_payload.get("activation"))
        if sidecar_activation:
            merged_activation = {
                **merged_activation,
                **sidecar_activation,
                "strategy_change": {
                    **_mapping(merged_activation.get("strategy_change")),
                    **_mapping(sidecar_activation.get("strategy_change")),
                },
            }
        trigger_families = _unique_strings(
            compiled.get("trigger_families"),
            sidecar_payload.get("trigger_families"),
            raw_trigger_context.get("trigger_families"),
            sidecar_trigger_context.get("trigger_families"),
        )
        trigger_rule_ids = _unique_strings(
            compiled.get("trigger_rule_ids"),
            sidecar_payload.get("trigger_rule_ids"),
            raw_trigger_context.get("trigger_rule_ids"),
            sidecar_trigger_context.get("trigger_rule_ids"),
        )
        affected_lane_ids = _unique_strings(
            compiled.get("affected_lane_ids"),
            sidecar_payload.get("affected_lane_ids"),
            raw_trigger_context.get("affected_lane_ids"),
            sidecar_trigger_context.get("affected_lane_ids"),
        )
        affected_uncertainty_ids = _unique_strings(
            compiled.get("affected_uncertainty_ids"),
            sidecar_payload.get("affected_uncertainty_ids"),
            raw_trigger_context.get("affected_uncertainty_ids"),
            raw_trigger_context.get("strategic_uncertainty_ids"),
            sidecar_trigger_context.get("affected_uncertainty_ids"),
            sidecar_trigger_context.get("strategic_uncertainty_ids"),
        )
        trigger_context = {
            **raw_trigger_context,
            **sidecar_trigger_context,
        }
        if trigger_families:
            trigger_context["trigger_families"] = trigger_families
        if trigger_rule_ids:
            trigger_context["trigger_rule_ids"] = trigger_rule_ids
        if affected_lane_ids:
            trigger_context["affected_lane_ids"] = affected_lane_ids
        if affected_uncertainty_ids:
            trigger_context["affected_uncertainty_ids"] = affected_uncertainty_ids
            trigger_context["strategic_uncertainty_ids"] = affected_uncertainty_ids
        return {
            **compiled,
            **raw_decision,
            **sidecar_payload,
            "status": _string(sidecar_payload.get("status"))
            or _string(compiled.get("status"))
            or "clear",
            "decision_kind": (
                _string(sidecar_payload.get("decision_kind"))
                or _string(compiled.get("decision_kind"))
                or "clear"
            ),
            "decision_id": _string(sidecar_payload.get("decision_id"))
            or _string(compiled.get("decision_id"))
            or "report-synthesis:clear",
            "summary": _string(sidecar_payload.get("summary"))
            or _string(compiled.get("summary"))
            or "No unresolved report synthesis pressure.",
            "reason_ids": _unique_strings(
                compiled.get("reason_ids"),
                sidecar_payload.get("reason_ids"),
            ),
            "source_report_ids": _unique_strings(
                compiled.get("source_report_ids"),
                sidecar_payload.get("source_report_ids"),
            ),
            "topic_keys": _unique_strings(
                compiled.get("topic_keys"),
                sidecar_payload.get("topic_keys"),
            ),
            "trigger_families": trigger_families,
            "trigger_rule_ids": trigger_rule_ids,
            "affected_lane_ids": affected_lane_ids,
            "affected_uncertainty_ids": affected_uncertainty_ids,
            "trigger_context": trigger_context,
            "directives": self._mapping_list(
                sidecar_payload.get("directives") or _mapping(replan_synthesis).get("replan_directives"),
            )
            or self._mapping_list(compiled.get("directives")),
            "recommended_actions": self._mapping_list(
                sidecar_payload.get("recommended_actions")
                or _mapping(replan_synthesis).get("recommended_actions"),
            )
            or self._mapping_list(compiled.get("recommended_actions")),
            "activation": merged_activation,
        }

    def _resolve_latest_planning_cycle_entry(
        self,
        *,
        current_cycle: dict[str, Any] | None,
        cycles: Sequence[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if _mapping(self._resolve_formal_planning_payload(current_cycle)).get(
            "cycle_decision",
        ):
            return current_cycle
        for cycle in cycles:
            if _mapping(self._resolve_formal_planning_payload(cycle)).get(
                "cycle_decision",
            ):
                return cycle
        if isinstance(current_cycle, dict):
            return current_cycle
        return cycles[0] if cycles else None

    def _resolve_current_assignment_for_planning(
        self,
        *,
        current_cycle: dict[str, Any] | None,
        assignments: Sequence[dict[str, Any]],
        selected_assignment_id: str | None = None,
        selected_backlog_item_id: str | None = None,
    ) -> dict[str, Any] | None:
        if selected_assignment_id is not None:
            current_assignment = next(
                (
                    item
                    for item in assignments
                    if _string(item.get("assignment_id")) == selected_assignment_id
                ),
                None,
            )
            if isinstance(current_assignment, dict):
                return current_assignment
        if selected_backlog_item_id is not None:
            current_assignment = next(
                (
                    item
                    for item in assignments
                    if _string(item.get("backlog_item_id")) == selected_backlog_item_id
                ),
                None,
            )
            if isinstance(current_assignment, dict):
                return current_assignment
        for assignment_id in _unique_strings(_mapping(current_cycle).get("assignment_ids")):
            current_assignment = next(
                (
                    item
                    for item in assignments
                    if _string(item.get("assignment_id")) == assignment_id
                ),
                None,
            )
            if isinstance(current_assignment, dict):
                return current_assignment
        return assignments[0] if assignments else None

    def _build_fallback_cycle_planning_decision(
        self,
        *,
        cycle_entry: dict[str, Any] | None,
        assignments: Sequence[dict[str, Any]],
        strategy_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        cycle_payload = _mapping(cycle_entry)
        cycle_id = _string(cycle_payload.get("cycle_id"))
        selected_assignment_ids = _unique_strings(cycle_payload.get("assignment_ids"))
        if cycle_id is not None and not selected_assignment_ids:
            selected_assignment_ids = _unique_strings(
                [
                    item.get("assignment_id")
                    for item in assignments
                    if _string(item.get("cycle_id")) == cycle_id
                ],
            )
        selected_backlog_item_ids = _unique_strings(cycle_payload.get("backlog_item_ids"))
        selected_lane_ids = _unique_strings(
            cycle_payload.get("focus_lane_ids"),
            [
                item.get("lane_id")
                for item in assignments
                if cycle_id is None or _string(item.get("cycle_id")) == cycle_id
            ],
        )
        max_assignment_count = int(cycle_payload.get("max_assignment_count") or 0)
        if max_assignment_count <= 0:
            max_assignment_count = len(selected_assignment_ids) or len(
                selected_backlog_item_ids,
            )
        return {
            "should_start": bool(selected_assignment_ids or selected_backlog_item_ids),
            "reason": "cycle-record-fallback",
            "cycle_id": cycle_id,
            "cycle_kind": _string(cycle_payload.get("cycle_kind")) or "daily",
            "selected_backlog_item_ids": selected_backlog_item_ids,
            "selected_lane_ids": selected_lane_ids,
            "selected_assignment_ids": selected_assignment_ids,
            "max_assignment_count": max_assignment_count,
            "summary": (
                _string(cycle_payload.get("summary"))
                or "Formal cycle decision derived from the current cycle record."
            ),
            "planning_policy": _unique_strings(
                strategy_constraints.get("planning_policy"),
            ),
            "metadata": {
                "source": "cycle-record-fallback",
            },
        }

    def _build_main_brain_planning_surface(
        self,
        *,
        record: IndustryInstanceRecord,
        current_cycle: dict[str, Any] | None,
        cycles: list[dict[str, Any]],
        assignments: list[dict[str, Any]],
        selected_assignment_id: str | None = None,
        selected_backlog_item_id: str | None = None,
    ) -> IndustryMainBrainPlanningSurface:
        planning_cycle = self._resolve_latest_planning_cycle_entry(
            current_cycle=current_cycle,
            cycles=cycles,
        )
        planning_sidecar = self._resolve_formal_planning_payload(planning_cycle)
        strategy_constraints = self._strategy_constraints_surface_payload(
            record=record,
            planning_sidecar=planning_sidecar,
        )

        cycle_decision = _mapping(planning_sidecar.get("cycle_decision"))
        if cycle_decision:
            cycle_payload = _mapping(planning_cycle)
            selected_assignment_ids = _unique_strings(
                cycle_decision.get("selected_assignment_ids"),
                cycle_payload.get("assignment_ids"),
            )
            selected_backlog_item_ids = _unique_strings(
                cycle_decision.get("selected_backlog_item_ids"),
                cycle_payload.get("backlog_item_ids"),
            )
            cycle_decision = {
                **cycle_decision,
                "cycle_id": _string(cycle_decision.get("cycle_id"))
                or _string(cycle_payload.get("cycle_id")),
                "cycle_kind": _string(cycle_decision.get("cycle_kind"))
                or _string(cycle_payload.get("cycle_kind"))
                or "daily",
                "selected_lane_ids": _unique_strings(
                    cycle_decision.get("selected_lane_ids"),
                    cycle_payload.get("focus_lane_ids"),
                ),
                "selected_backlog_item_ids": selected_backlog_item_ids,
                "selected_assignment_ids": selected_assignment_ids,
                "max_assignment_count": int(
                    cycle_decision.get("max_assignment_count")
                    or len(selected_assignment_ids)
                    or len(selected_backlog_item_ids),
                ),
                "summary": (
                    _string(cycle_decision.get("summary"))
                    or _string(cycle_payload.get("summary"))
                    or "Formal cycle decision derived from persisted planning sidecars."
                ),
                "planning_policy": _unique_strings(
                    cycle_decision.get("planning_policy"),
                    strategy_constraints.get("planning_policy"),
                ),
            }
        else:
            cycle_decision = self._build_fallback_cycle_planning_decision(
                cycle_entry=planning_cycle,
                assignments=assignments,
                strategy_constraints=strategy_constraints,
            )

        current_assignment = self._resolve_current_assignment_for_planning(
            current_cycle=current_cycle,
            assignments=assignments,
            selected_assignment_id=selected_assignment_id,
            selected_backlog_item_id=selected_backlog_item_id,
        )
        assignment_sidecar = self._resolve_formal_planning_payload(current_assignment)
        focused_assignment_plan = _mapping(assignment_sidecar.get("assignment_plan"))

        replan_cycle = self._resolve_replan_cycle_entry(
            current_cycle=current_cycle,
            current_cycle_entry=current_cycle,
            cycles=cycles,
        )
        replan_synthesis = self._resolve_cycle_synthesis_payload(replan_cycle)
        replan = self._resolve_report_replan_payload(
            cycle_entry=replan_cycle,
            synthesis=replan_synthesis,
        )
        strategy_trigger_rules = self._strategy_trigger_rules_surface_payload(
            record=record,
            planning_sidecar=planning_sidecar,
        )
        uncertainty_register = self._build_uncertainty_register_surface_payload(
            strategic_uncertainties=self._mapping_list(
                strategy_constraints.get("strategic_uncertainties"),
            ),
            lane_budgets=self._mapping_list(strategy_constraints.get("lane_budgets")),
            strategy_trigger_rules=strategy_trigger_rules,
        )
        persisted_uncertainty_register = _mapping(replan.get("uncertainty_register"))
        if persisted_uncertainty_register:
            uncertainty_register = persisted_uncertainty_register
        if strategy_trigger_rules:
            replan = {
                **replan,
                "strategy_trigger_rules": strategy_trigger_rules,
            }
        if uncertainty_register:
            replan = {
                **replan,
                "uncertainty_register": uncertainty_register,
            }

        return IndustryMainBrainPlanningSurface(
            is_truth_store=False,
            source="industry-runtime-read-model",
            strategy_constraints=strategy_constraints,
            latest_cycle_decision=cycle_decision,
            focused_assignment_plan=focused_assignment_plan,
            replan=replan,
        )

    def _build_instance_main_chain(
        self,
        *,
        record: IndustryInstanceRecord,
        lanes: list[dict[str, Any]],
        backlog: list[dict[str, Any]],
        current_cycle: dict[str, Any] | None,
        cycles: list[dict[str, Any]],
        assignments: list[dict[str, Any]],
        agent_reports: list[dict[str, Any]],
        goals: list[dict[str, Any]],
        agents: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        execution: IndustryExecutionSummary | None,
        strategy_memory: StrategyMemoryRecord | None,
        selected_assignment_id: str | None = None,
        selected_backlog_item_id: str | None = None,
    ) -> IndustryMainChainGraph:
        focus_task = self._pick_execution_focus_task(tasks)
        if focus_task is None and execution is not None and execution.current_task_id:
            focus_task = next(
                (
                    item
                    for item in tasks
                    if _string(_mapping(item.get("task")).get("id"))
                    == _string(execution.current_task_id)
                ),
                None,
            )
        child_tasks = [
            item
            for item in tasks
            if _string(_mapping(item.get("task")).get("parent_task_id"))
        ]
        current_child_task = self._resolve_chain_child_task(
            child_tasks=child_tasks,
            execution=execution,
        )
        latest_evidence = (
            max(evidence, key=lambda item: _sort_timestamp(item.get("created_at")))
            if evidence
            else None
        )
        agents_by_id = {
            _string(agent.get("agent_id")): agent
            for agent in agents
            if _string(agent.get("agent_id"))
        }
        tasks_by_id = {
            _string(_mapping(item.get("task")).get("id")): item
            for item in tasks
            if _string(_mapping(item.get("task")).get("id"))
        }
        assignments_by_id = {
            _string(item.get("assignment_id")): item
            for item in assignments
            if _string(item.get("assignment_id"))
        }
        current_task_payload = (
            _mapping(focus_task.get("task")) if isinstance(focus_task, dict) else {}
        )
        current_task_id = _string(current_task_payload.get("id"))
        current_task_route = (
            _string(focus_task.get("route")) if isinstance(focus_task, dict) else None
        )
        current_child_payload = (
            _mapping(current_child_task.get("task"))
            if isinstance(current_child_task, dict)
            else {}
        )
        current_child_id = _string(current_child_payload.get("id"))
        current_child_route = (
            _string(current_child_task.get("route"))
            if isinstance(current_child_task, dict)
            else None
        )
        focus_payload = self._resolve_live_focus_payload(
            execution=execution,
            assignments=assignments,
            backlog=backlog,
            tasks=tasks,
            selected_assignment_id=selected_assignment_id,
            selected_backlog_item_id=selected_backlog_item_id,
        )
        current_assignment = focus_payload["current_assignment"]
        current_assignment_id = focus_payload["current_assignment_id"]
        current_assignment_meta = (
            _mapping(current_assignment.get("metadata"))
            if isinstance(current_assignment, dict)
            else {}
        )
        current_cycle_id = (
            _string(current_task_payload.get("cycle_id"))
            or (
                _string(current_assignment.get("cycle_id"))
                if isinstance(current_assignment, dict)
                else None
            )
            or (
                _string(current_cycle.get("cycle_id"))
                if isinstance(current_cycle, dict)
                else None
            )
        )
        current_cycle_entry = None
        if current_cycle_id is not None:
            current_cycle_entry = next(
                (
                    item
                    for item in cycles
                    if _string(item.get("cycle_id")) == current_cycle_id
                ),
                None,
            )
        if current_cycle_entry is None:
            current_cycle_entry = current_cycle or (cycles[0] if cycles else None)
        current_cycle_id = (
            _string(current_cycle_entry.get("cycle_id"))
            if isinstance(current_cycle_entry, dict)
            else None
        )
        replan_cycle_entry = self._resolve_replan_cycle_entry(
            current_cycle=current_cycle if isinstance(current_cycle, dict) else None,
            current_cycle_entry=(
                current_cycle_entry if isinstance(current_cycle_entry, dict) else None
            ),
            cycles=[item for item in cycles if isinstance(item, dict)],
        )
        replan_cycle_id = (
            _string(replan_cycle_entry.get("cycle_id"))
            if isinstance(replan_cycle_entry, dict)
            else current_cycle_id
        )
        current_lane_id = (
            _string(current_task_payload.get("lane_id"))
            or (
                _string(current_assignment.get("lane_id"))
                if isinstance(current_assignment, dict)
                else None
            )
            or (
                _string(_mapping(current_cycle_entry).get("focus_lane_ids")[0])
                if isinstance(_mapping(current_cycle_entry).get("focus_lane_ids"), list)
                and _mapping(current_cycle_entry).get("focus_lane_ids")
                else None
            )
        )
        lanes_by_id = {
            _string(lane.get("lane_id")): lane
            for lane in lanes
            if _string(lane.get("lane_id"))
        }
        current_lane = (
            lanes_by_id.get(current_lane_id)
            if current_lane_id is not None
            else None
        )
        if current_lane is None and lanes:
            current_lane = next(
                (
                    item
                    for item in lanes
                    if _string(item.get("status")) == "active"
                ),
                lanes[0],
            )
        current_lane_id = (
            _string(current_lane.get("lane_id")) if isinstance(current_lane, dict) else None
        )
        current_report = None
        if current_assignment_id is not None:
            current_report = next(
                (
                    item
                    for item in agent_reports
                    if _string(item.get("assignment_id")) == current_assignment_id
                ),
                None,
            )
        if current_report is None and current_cycle_id is not None:
            current_report = next(
                (
                    item
                    for item in agent_reports
                    if _string(item.get("cycle_id")) == current_cycle_id
                ),
                None,
            )
        if current_report is None and agent_reports:
            current_report = agent_reports[0]
        current_report_id = (
            _string(current_report.get("report_id"))
            if isinstance(current_report, dict)
            else None
        )
        open_backlog_items = [
            item
            for item in backlog
            if _string(item.get("status")) in {"open", "selected"}
        ]
        live_backlog_items = [
            item
            for item in backlog
            if _string(item.get("status")) in {"open", "selected", "materialized"}
        ]
        live_backlog_items = self._rank_materializable_backlog_items(live_backlog_items)
        if focus_task is None and isinstance(current_report, dict):
            report_task_id = _string(current_report.get("task_id"))
            report_assignment_id = _string(current_report.get("assignment_id"))
            report_cycle_id = _string(current_report.get("cycle_id"))
            report_task = (
                tasks_by_id.get(report_task_id)
                if report_task_id is not None
                else None
            )
            report_assignment = (
                assignments_by_id.get(report_assignment_id)
                if report_assignment_id is not None
                else None
            )
            report_cycle = (
                next(
                    (
                        item
                        for item in cycles
                        if _string(item.get("cycle_id")) == report_cycle_id
                    ),
                    None,
                )
                if report_cycle_id is not None
                else None
            )
            if isinstance(report_task, dict):
                focus_task = report_task
                current_task_payload = _mapping(report_task.get("task"))
                current_task_id = _string(current_task_payload.get("id"))
                current_task_route = _string(report_task.get("route"))
            if isinstance(report_assignment, dict):
                current_assignment = report_assignment
                current_assignment_id = _string(report_assignment.get("assignment_id"))
                current_assignment_meta = _mapping(report_assignment.get("metadata"))
            if isinstance(report_cycle, dict):
                current_cycle_entry = report_cycle
                current_cycle_id = _string(report_cycle.get("cycle_id"))
            if isinstance(current_assignment, dict):
                current_lane_id = (
                    _string(current_task_payload.get("lane_id"))
                    or _string(current_assignment.get("lane_id"))
                )
                current_lane = (
                    lanes_by_id.get(current_lane_id)
                    if current_lane_id is not None
                    else current_lane
                )
        current_sop_binding_id = (
            _string(current_task_payload.get("fixed_sop_binding_id"))
            or _string(
                _mapping(current_report).get("metadata", {}).get("fixed_sop_binding_id"),
            )
            or _string(current_assignment_meta.get("fixed_sop_binding_id"))
        )
        current_sop_binding_name = (
            _string(current_task_payload.get("fixed_sop_binding_name"))
            or _string(current_assignment_meta.get("fixed_sop_binding_name"))
        )
        current_routine_id = (
            _string(current_task_payload.get("routine_id"))
            or _string(_mapping(current_report).get("metadata", {}).get("routine_run_id"))
            or _string(current_assignment_meta.get("routine_id"))
        )
        current_routine_name = (
            _string(current_task_payload.get("routine_name"))
            or _string(current_assignment_meta.get("routine_name"))
        )
        current_execution_ref = current_sop_binding_id or current_routine_id
        current_execution_route = (
            f"/api/fixed-sops/bindings/{quote(current_sop_binding_id)}"
            if current_sop_binding_id is not None
            else (
                f"/api/routines/{quote(current_routine_id)}"
                if current_routine_id is not None
                else None
            )
        )
        current_execution_status = (
            _string(execution.status)
            if current_execution_ref is not None
            and execution is not None
            and _string(execution.status)
            else (
                _string(current_task_payload.get("status"))
                if current_execution_ref is not None
                else "idle"
            )
        ) or "idle"
        current_execution_name = current_sop_binding_name or current_routine_name
        current_execution_label = (
            "Fixed SOP" if current_sop_binding_id is not None else "Routine"
        )
        current_execution_truth_source = (
            "FixedSopBindingRecord + WorkflowRunRecord + EvidenceRecord"
            if current_sop_binding_id is not None
            else "ExecutionRoutineRecord + RoutineRunRecord"
        )
        current_execution_backflow_port = (
            "FixedSopService.run_binding()"
            if current_sop_binding_id is not None
            else "RoutineService.replay_routine()"
        )
        current_execution_summary = (
            current_execution_name
            or (
                "The current assignment is executing through a governed SOP binding."
                if current_sop_binding_id is not None
                else (
                    "The current assignment is executing through a formal routine replay."
                    if current_routine_id is not None
                    else "No formal routine or SOP binding is currently attached to the selected task."
                )
            )
        )
        current_execution_mode = (
            "sop-binding"
            if current_sop_binding_id is not None
            else ("routine" if current_routine_id is not None else "none")
        )
        latest_evidence_id = (
            _string(latest_evidence.get("id"))
            if isinstance(latest_evidence, dict)
            else None
        )
        evidence_route = (
            f"/api/runtime-center/evidence/{quote(latest_evidence_id)}"
            if latest_evidence_id is not None
            else None
        )
        strategy_route = (
            f"/api/runtime-center/strategy-memory?industry_instance_id={quote(record.instance_id)}"
            if record.instance_id
            else None
        )
        current_owner_agent_id = (
            _string(execution.current_owner_agent_id)
            if execution is not None and _string(execution.current_owner_agent_id)
            else (
                _string(current_assignment.get("owner_agent_id"))
                if isinstance(current_assignment, dict)
                else None
            )
            or (
                _string(current_lane.get("owner_agent_id"))
                if isinstance(current_lane, dict)
                else None
            )
        )
        current_owner_payload = (
            agents_by_id.get(current_owner_agent_id)
            if current_owner_agent_id is not None
            else None
        )
        current_owner = (
            _string(execution.current_owner)
            if execution is not None and _string(execution.current_owner)
            else (
                _string(current_owner_payload.get("role_name"))
                or _string(current_owner_payload.get("name"))
                if isinstance(current_owner_payload, dict)
                else None
            )
        )
        current_risk = (
            _string(execution.current_risk)
            if execution is not None and _string(execution.current_risk)
            else (
                _string(current_report.get("risk_level"))
                if isinstance(current_report, dict)
                else None
            )
        )
        loop_state = (
            _string(execution.status)
            if execution is not None and _string(execution.status)
            else _string(record.autonomy_status) or _string(record.status)
            or "idle"
        )
        open_backlog_count = sum(
            1 for item in backlog if _string(item.get("status")) in {"open", "selected"}
        )
        pending_report_count = sum(
            1 for item in agent_reports if not bool(item.get("processed"))
        )
        chat_writeback_items = [
            item
            for item in backlog
            if self._backlog_item_is_chat_writeback(item)
        ]
        latest_writeback = (
            max(
                chat_writeback_items,
                key=lambda item: _sort_timestamp(
                    item.get("updated_at") or item.get("created_at"),
                ),
            )
            if chat_writeback_items
            else None
        )
        latest_writeback_id = (
            _string(latest_writeback.get("backlog_item_id"))
            if isinstance(latest_writeback, dict)
            else None
        )
        latest_writeback_route = (
            _string(latest_writeback.get("route"))
            if isinstance(latest_writeback, dict)
            else None
        )
        current_backlog = focus_payload["current_backlog"]
        current_backlog_id = focus_payload["current_backlog_id"]
        current_focus_title = focus_payload["current_focus_title"]
        current_backlog_route = (
            _string(current_backlog.get("route"))
            if isinstance(current_backlog, dict)
            else None
        )
        current_cycle_synthesis = self._resolve_cycle_synthesis_payload(replan_cycle_entry)
        followup_backlog_items = [
            item
            for item in live_backlog_items
            if self._backlog_item_is_report_followup(item)
        ]
        followup_pressure_surfaces = _unique_strings(
            *[
                _mapping(item.get("metadata")).get("seat_requested_surfaces")
                for item in followup_backlog_items
            ],
            *[
                _mapping(item.get("metadata")).get("chat_writeback_requested_surfaces")
                for item in followup_backlog_items
            ],
        )
        followup_pressure_surfaces = [
            surface
            for surface in followup_pressure_surfaces
            if surface in {"browser", "desktop", "document", "file"}
        ]
        followup_control_thread_ids = _unique_strings(
            *[
                _mapping(item.get("metadata")).get("control_thread_id")
                for item in followup_backlog_items
            ],
            *[
                _mapping(item.get("metadata")).get("session_id")
                for item in followup_backlog_items
            ],
        )
        followup_environment_refs = _unique_strings(
            *[
                _mapping(item.get("metadata")).get("environment_ref")
                for item in followup_backlog_items
            ],
        )
        followup_scheduler_actions = _unique_strings(
            *[
                _mapping(item.get("metadata")).get("recommended_scheduler_action")
                for item in followup_backlog_items
            ],
        )
        pending_followup_confirmations = [
            item
            for item in followup_backlog_items
            if _string(_mapping(item.get("metadata")).get("decision_request_id")) is not None
            and _string(_mapping(item.get("metadata")).get("proposal_status"))
            in {"waiting-confirm", "reviewing", "submitted", "verifying", "need_more_evidence"}
        ]
        synthesis_conflicts = list(current_cycle_synthesis.get("conflicts") or [])
        synthesis_holes = list(current_cycle_synthesis.get("holes") or [])
        synthesis_replan_reasons = [
            _string(item)
            for item in list(current_cycle_synthesis.get("replan_reasons") or [])
            if _string(item) is not None
        ]
        replan_payload = self._resolve_report_replan_payload(
            cycle_entry=replan_cycle_entry,
            synthesis=current_cycle_synthesis,
        )
        replan_decision_kind = _string(replan_payload.get("decision_kind")) or "clear"
        replan_needed = bool(current_cycle_synthesis.get("needs_replan")) or bool(
            _string(replan_payload.get("status")) == "needs-replan"
            or replan_decision_kind != "clear"
            or synthesis_conflicts
            or synthesis_holes
            or synthesis_replan_reasons
            or followup_backlog_items
        )
        if synthesis_conflicts or synthesis_holes:
            replan_summary = (
                f"Conflicts={len(synthesis_conflicts)}, holes={len(synthesis_holes)}; "
                "main brain should compare reports and decide whether to dispatch a follow-up cycle."
            )
        elif followup_backlog_items:
            replan_summary = (
                f"{len(followup_backlog_items)} follow-up backlog item(s) remain open; "
                "keep replan active until continuity pressure is closed."
            )
        elif replan_decision_kind == "strategy_review_required":
            replan_summary = (
                _string(replan_payload.get("summary"))
                or "Escalate the current report pressure into an explicit strategy review."
            )
        elif replan_decision_kind == "cycle_rebalance":
            replan_summary = (
                _string(replan_payload.get("summary"))
                or "Rebalance the current operating cycle before dispatching more work."
            )
        elif replan_decision_kind == "lane_reweight":
            replan_summary = (
                _string(replan_payload.get("summary"))
                or "Reweight lane investment before selecting the next cycle work."
            )
        elif replan_needed:
            replan_summary = (
                _string(replan_payload.get("summary"))
                or "Main brain should review the latest cycle synthesis before dispatching more work."
            )
        else:
            replan_summary = "No explicit replan request is pending."
        recommended_replan_action = None
        if pending_followup_confirmations:
            recommended_replan_action = "close-staffing-or-human-handoff-before-dispatch"
        elif followup_pressure_surfaces:
            recommended_replan_action = (
                f"dispatch-governed-followup-on-{followup_pressure_surfaces[0]}-surface"
            )
        elif replan_decision_kind == "strategy_review_required":
            recommended_replan_action = "escalate-strategy-review"
        elif replan_decision_kind == "cycle_rebalance":
            recommended_replan_action = "rebalance-current-cycle"
        elif replan_decision_kind == "lane_reweight":
            recommended_replan_action = "reweight-next-cycle-lanes"
        elif replan_needed:
            recommended_replan_action = "review-reports-and-materialize-next-followup-cycle"
        nodes = [
            IndustryMainChainNode(
                node_id="carrier",
                label="Carrier",
                status=_string(record.status) or "active",
                truth_source="IndustryInstanceRecord",
                current_ref=record.instance_id,
                route=f"/api/runtime-center/industry/{quote(record.instance_id)}",
                summary=(
                    f"{len(lanes)} lanes, {open_backlog_count} open backlog item(s), "
                    f"{len(assignments)} assignment(s), {len(agent_reports)} report(s)."
                ),
                backflow_port="IndustryService.run_operating_cycle() / reconcile_instance_status()",
                metrics={
                    "lane_count": len(lanes),
                    "backlog_count": len(backlog),
                    "open_backlog_count": open_backlog_count,
                    "assignment_count": len(assignments),
                    "report_count": len(agent_reports),
                    "agent_count": len(agents),
                    "schedule_count": len(self._list_schedule_ids_for_instance(record.instance_id)),
                },
            ),
            IndustryMainChainNode(
                node_id="writeback",
                label="Writeback",
                status=(
                    _string(latest_writeback.get("status"))
                    if isinstance(latest_writeback, dict)
                    else "idle"
                ),
                truth_source="ChatWritebackPlan + BacklogItemRecord(source=chat-writeback)",
                current_ref=latest_writeback_id,
                route=latest_writeback_route,
                summary=(
                    _string(latest_writeback.get("title"))
                    or _string(latest_writeback.get("summary"))
                    if isinstance(latest_writeback, dict)
                    else "No formal chat writeback has been recorded yet."
                ),
                backflow_port="IndustryService.apply_execution_chat_writeback()",
                metrics={
                    "chat_writeback_count": len(chat_writeback_items),
                },
            ),
            IndustryMainChainNode(
                node_id="strategy",
                label="Strategy",
                status=(
                    _string(strategy_memory.status)
                    if strategy_memory is not None
                    else "idle"
                ),
                truth_source="StrategyMemoryRecord",
                current_ref=(
                    _string(strategy_memory.strategy_id)
                    if strategy_memory is not None
                    else None
                ),
                route=strategy_route,
                summary=(
                    (_string(strategy_memory.north_star) or _string(strategy_memory.summary))
                    if strategy_memory is not None
                    else "No active strategy memory is linked yet."
                ),
                backflow_port="StateStrategyMemoryService.resolve_strategy_payload()",
                metrics={
                    "focus_count": (
                        len(strategy_memory.current_focuses)
                        if strategy_memory is not None
                        else 0
                    ),
                    "priority_count": (
                        len(strategy_memory.priority_order)
                        if strategy_memory is not None
                        else 0
                    ),
                    "paused_lane_count": (
                        len(strategy_memory.paused_lane_ids)
                        if strategy_memory is not None
                        else 0
                    ),
                },
            ),
            IndustryMainChainNode(
                node_id="lane",
                label="Lane",
                status=(
                    _string(current_lane.get("status"))
                    if isinstance(current_lane, dict)
                    else "idle"
                ),
                truth_source="OperatingLaneRecord",
                current_ref=current_lane_id,
                route=(
                    _string(current_lane.get("route"))
                    if isinstance(current_lane, dict)
                    else None
                ),
                summary=(
                    _string(current_lane.get("title"))
                    or _string(current_lane.get("summary"))
                    if isinstance(current_lane, dict)
                    else "No operating lane is currently selected."
                ),
                backflow_port="OperatingLaneService.resolve_lane()",
                metrics={
                    "lane_count": len(lanes),
                    "lane_backlog_count": sum(
                        1
                        for item in backlog
                        if _string(item.get("lane_id")) == current_lane_id
                    ),
                },
            ),
            IndustryMainChainNode(
                node_id="backlog",
                label="Backlog",
                status=(
                    _string(current_backlog.get("status"))
                    if isinstance(current_backlog, dict)
                    else "idle"
                ),
                truth_source="BacklogItemRecord",
                current_ref=current_backlog_id,
                route=current_backlog_route,
                summary=(
                    _string(current_backlog.get("title"))
                    or _string(current_backlog.get("summary"))
                    if isinstance(current_backlog, dict)
                    else "No backlog item is currently selected."
                ),
                backflow_port="BacklogService.record_chat_writeback() / mark_item_materialized()",
                metrics={
                    "backlog_count": len(backlog),
                    "open_backlog_count": open_backlog_count,
                },
            ),
            IndustryMainChainNode(
                node_id="cycle",
                label="Cycle",
                status=(
                    _string(current_cycle_entry.get("status"))
                    if isinstance(current_cycle_entry, dict)
                    else "idle"
                ),
                truth_source="OperatingCycleRecord",
                current_ref=current_cycle_id,
                route=(
                    _string(current_cycle_entry.get("route"))
                    if isinstance(current_cycle_entry, dict)
                    else f"/api/runtime-center/industry/{quote(record.instance_id)}"
                ),
                summary=(
                    _string(current_cycle_entry.get("title"))
                    or _string(current_cycle_entry.get("summary"))
                    if isinstance(current_cycle_entry, dict)
                    else "No active operating cycle is currently selected."
                ),
                backflow_port="OperatingCycleService.reconcile_cycle()",
                metrics={
                    "cycle_count": len(cycles),
                    "pending_report_count": pending_report_count,
                    "open_backlog_count": open_backlog_count,
                },
            ),
            IndustryMainChainNode(
                node_id="assignment",
                label="Assignment",
                status=(
                    _string(current_assignment.get("status"))
                    if isinstance(current_assignment, dict)
                    else "idle"
                ),
                truth_source="AssignmentRecord",
                current_ref=current_assignment_id,
                route=(
                    _string(current_assignment.get("route"))
                    if isinstance(current_assignment, dict)
                    else None
                ),
                summary=(
                    _string(current_assignment.get("title"))
                    or _string(current_assignment.get("summary"))
                    if isinstance(current_assignment, dict)
                    else "No formal assignment is currently selected."
                ),
                backflow_port="AssignmentService.reconcile_assignments()",
                metrics={
                    "assignment_count": len(assignments),
                    "active_assignment_count": sum(
                        1 for item in assignments if _string(item.get("status")) == "active"
                    ),
                },
            ),
            IndustryMainChainNode(
                node_id="routine",
                label=current_execution_label,
                status=current_execution_status,
                truth_source=current_execution_truth_source,
                current_ref=current_execution_ref,
                route=current_execution_route,
                summary=current_execution_summary,
                backflow_port=current_execution_backflow_port,
                metrics={
                    "attached": 1 if current_execution_ref is not None else 0,
                    "execution_mode": current_execution_mode,
                    "task_type": _string(current_task_payload.get("task_type")),
                },
            ),
            IndustryMainChainNode(
                node_id="child-task",
                label="Child Task",
                status=self._derive_child_task_chain_status(child_tasks),
                truth_source="TaskRecord.parent_task_id + TaskRuntimeRecord",
                current_ref=current_child_id,
                route=current_child_route,
                summary=(
                    _string(current_child_payload.get("title"))
                    or (
                        f"{len(child_tasks)} delegated child task(s) linked to the parent chain."
                        if child_tasks
                        else "No delegated child task is currently attached."
                    )
                ),
                backflow_port="KernelDispatcher._reconcile_parent_after_child_terminal()",
                metrics=self._child_task_chain_metrics(child_tasks),
            ),
            IndustryMainChainNode(
                node_id="evidence",
                label="Evidence",
                status="active" if latest_evidence is not None else "idle",
                truth_source="EvidenceRecord",
                current_ref=latest_evidence_id,
                route=evidence_route,
                summary=self._evidence_summary(latest_evidence)
                or ("No evidence written yet." if not evidence else None),
                backflow_port="EvidenceLedger + Runtime Center evidence reads",
                metrics={"evidence_count": len(evidence)},
            ),
            IndustryMainChainNode(
                node_id="report",
                label="Report",
                status=(
                    _string(current_report.get("status"))
                    if isinstance(current_report, dict)
                    else "idle"
                ),
                truth_source="AgentReportRecord",
                current_ref=current_report_id,
                route=(
                    _string(current_report.get("route"))
                    if isinstance(current_report, dict)
                    else None
                ),
                summary=(
                    _string(current_report.get("headline"))
                    or _string(current_report.get("summary"))
                    if isinstance(current_report, dict)
                    else "No structured agent report has flowed back yet."
                ),
                backflow_port="AgentReportService.mark_processed() + BacklogService.mark_item_completed()",
                metrics={
                    "report_count": len(agent_reports),
                    "pending_report_count": pending_report_count,
                },
            ),
            IndustryMainChainNode(
                node_id="replan",
                label="Replan",
                status="active" if replan_needed else "idle",
                truth_source="OperatingCycle.synthesis + AgentReportRecord",
                current_ref=replan_cycle_id,
                route=(
                    _string(replan_cycle_entry.get("route"))
                    if isinstance(replan_cycle_entry, dict)
                    else f"/api/runtime-center/industry/{quote(record.instance_id)}"
                ),
                summary=replan_summary,
                backflow_port="IndustryService._process_pending_agent_reports() / run_operating_cycle()",
                metrics={
                    "conflict_count": len(synthesis_conflicts),
                    "hole_count": len(synthesis_holes),
                    "needs_replan": replan_needed,
                    "decision_kind": replan_decision_kind,
                    "replan_reason_count": len(synthesis_replan_reasons),
                    "replan_reasons": synthesis_replan_reasons,
                    "trigger_families": list(replan_payload.get("trigger_families") or []),
                    "trigger_rule_ids": list(replan_payload.get("trigger_rule_ids") or []),
                    "affected_lane_ids": list(replan_payload.get("affected_lane_ids") or []),
                    "affected_uncertainty_ids": list(
                        replan_payload.get("affected_uncertainty_ids") or []
                    ),
                    "followup_pressure_count": len(followup_backlog_items),
                    "pending_followup_confirmation_count": len(pending_followup_confirmations),
                    "followup_pressure_surfaces": followup_pressure_surfaces,
                    "followup_control_thread_ids": followup_control_thread_ids,
                    "followup_environment_refs": followup_environment_refs,
                    "followup_scheduler_actions": followup_scheduler_actions,
                    "recommended_action": recommended_replan_action,
                },
            ),
            IndustryMainChainNode(
                node_id="instance-reconcile",
                label="Instance Reconcile",
                status=_string(record.status) or "active",
                truth_source="IndustryService.reconcile_instance_status() over IndustryInstanceRecord + cycle/backlog/goal/report state",
                current_ref=record.instance_id,
                route=f"/api/runtime-center/industry/{quote(record.instance_id)}",
                summary=f"Team status is {_string(record.status) or 'active'}.",
                backflow_port="IndustryService._sync_strategy_memory_for_instance()",
                metrics={
                    "active_assignment_count": sum(
                        1 for assignment in assignments if _string(assignment.get("status")) == "active"
                    ),
                    "open_backlog_count": open_backlog_count,
                    "pending_report_count": pending_report_count,
                },
            ),
        ]
        return IndustryMainChainGraph(
            loop_state=loop_state or "idle",
            current_focus_id=(
                _string(focus_payload.get("current_focus_id"))
                or (
                    _string(execution.current_focus_id)
                    if execution is not None
                    else None
                )
            ),
            current_focus=current_focus_title,
            current_owner_agent_id=current_owner_agent_id,
            current_owner=current_owner,
            current_risk=current_risk,
            latest_evidence_summary=(
                self._evidence_summary(latest_evidence)
                or (
                    _string(execution.latest_evidence_summary)
                    if execution is not None
                    else None
                )
            ),
            nodes=nodes,
        )

    def _resolve_chain_child_task(
        self,
        *,
        child_tasks: list[dict[str, Any]],
        execution: IndustryExecutionSummary | None,
    ) -> dict[str, Any] | None:
        parent_task_id = _string(execution.current_task_id) if execution is not None else None
        if parent_task_id is not None:
            matched = next(
                (
                    task
                    for task in child_tasks
                    if _string(_mapping(task.get("task")).get("parent_task_id"))
                    == parent_task_id
                ),
                None,
            )
            if matched is not None:
                return matched
        return child_tasks[0] if child_tasks else None

    def _derive_child_task_chain_status(
        self,
        child_tasks: list[dict[str, Any]],
    ) -> str:
        if not child_tasks:
            return "idle"
        statuses = [
            str(self._derive_execution_task_state(task).get("status") or "")
            for task in child_tasks
        ]
        statuses = [status for status in statuses if status]
        if any(status in {"failed", "blocked", "idle-loop"} for status in statuses):
            return "blocked"
        if any(status in {"executing", "running", "active", "waiting-confirm"} for status in statuses):
            return "active"
        if statuses and all(status == "completed" for status in statuses):
            return "completed"
        return statuses[0] if statuses else "idle"

    def _child_task_chain_metrics(
        self,
        child_tasks: list[dict[str, Any]],
    ) -> dict[str, int]:
        metrics = {"total": len(child_tasks), "active": 0, "completed": 0, "blocked": 0}
        for task in child_tasks:
            status = str(self._derive_execution_task_state(task).get("status") or "")
            if status in {"executing", "running", "active", "waiting-confirm"}:
                metrics["active"] += 1
            elif status == "completed":
                metrics["completed"] += 1
            elif status:
                metrics["blocked"] += 1
        return metrics

    def _apply_execution_core_identity_to_agents(
        self,
        *,
        agents: list[dict[str, Any]],
        execution_core_identity: IndustryExecutionCoreIdentity | None,
        goals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if execution_core_identity is None:
            return agents
        for item in agents:
            agent_id = _string(item.get("agent_id"))
            if not is_execution_core_agent_id(agent_id):
                continue
            item["industry_instance_id"] = execution_core_identity.industry_instance_id
            item["industry_role_id"] = execution_core_identity.role_id
            item["identity_label"] = execution_core_identity.identity_label
            item["industry_label"] = execution_core_identity.industry_label
            item["industry_summary"] = execution_core_identity.industry_summary
            item["thinking_axes"] = list(execution_core_identity.thinking_axes)
            item["role_name"] = execution_core_identity.role_name
            item["role_summary"] = execution_core_identity.role_summary
            item["mission"] = execution_core_identity.mission
            item["environment_constraints"] = list(
                execution_core_identity.environment_constraints,
            )
            item["evidence_expectations"] = list(
                execution_core_identity.evidence_expectations,
            )
            item["allowed_capabilities"] = list(
                execution_core_identity.allowed_capabilities,
            )
            item["operating_mode"] = execution_core_identity.operating_mode
            item["delegation_policy"] = list(
                execution_core_identity.delegation_policy,
            )
            item["direct_execution_policy"] = list(
                execution_core_identity.direct_execution_policy,
            )
            return agents

        seed = self._get_agent_snapshot(EXECUTION_CORE_AGENT_ID) or {}
        item = dict(seed)
        item["agent_id"] = EXECUTION_CORE_AGENT_ID
        item["name"] = _string(item.get("name")) or _EXECUTION_CORE_NAME
        item["industry_instance_id"] = execution_core_identity.industry_instance_id
        item["industry_role_id"] = execution_core_identity.role_id
        item["identity_label"] = execution_core_identity.identity_label
        item["industry_label"] = execution_core_identity.industry_label
        item["industry_summary"] = execution_core_identity.industry_summary
        item["thinking_axes"] = list(execution_core_identity.thinking_axes)
        item["role_name"] = execution_core_identity.role_name
        item["role_summary"] = execution_core_identity.role_summary
        item["mission"] = execution_core_identity.mission
        item["environment_constraints"] = list(
            execution_core_identity.environment_constraints,
        )
        item["evidence_expectations"] = list(
            execution_core_identity.evidence_expectations,
        )
        item["allowed_capabilities"] = list(
            execution_core_identity.allowed_capabilities,
        )
        item["operating_mode"] = execution_core_identity.operating_mode
        item["delegation_policy"] = list(
            execution_core_identity.delegation_policy,
        )
        item["direct_execution_policy"] = list(
            execution_core_identity.direct_execution_policy,
        )
        item.setdefault("status", "running")
        item["route"] = f"/api/runtime-center/agents/{EXECUTION_CORE_AGENT_ID}"
        agents.append(item)
        agents.sort(
            key=lambda agent: _sort_timestamp(agent.get("updated_at")),
            reverse=True,
        )
        return agents

    def _resolve_execution_core_goal(
        self,
        goals: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        matches = [
            goal
            for goal in goals
            if is_execution_core_agent_id(_string(goal.get("owner_agent_id")))
            or is_execution_core_role_id(_string(goal.get("role_id")))
        ]
        if not matches:
            return None
        for status in ("active", "draft", "paused", "blocked"):
            for goal in matches:
                if _string(goal.get("status")) == status:
                    return goal
        return matches[0]

    def _enrich_agent_capability_governance_payload(
        self,
        agent: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(agent, dict):
            return agent
        agent_id = _string(agent.get("agent_id"))
        repository = getattr(self, "_agent_runtime_repository", None)
        runtime = (
            repository.get_runtime(agent_id)
            if agent_id is not None and repository is not None
            else None
        )
        if runtime is None:
            return agent
        metadata = _mapping(getattr(runtime, "metadata", None))
        capability_layers = IndustrySeatCapabilityLayers.from_metadata(
            metadata.get("capability_layers"),
        )
        if not capability_layers.merged_capability_ids():
            return agent
        layers_payload = capability_layers.to_metadata_payload()
        raw_session_overlay = _mapping(metadata.get("current_session_overlay"))
        overlay_capability_ids = _unique_strings(
            raw_session_overlay.get("capability_ids"),
            layers_payload.get("session_overlay_capability_ids"),
        )
        current_session_overlay = None
        if raw_session_overlay or overlay_capability_ids:
            current_session_overlay = {
                **raw_session_overlay,
                "overlay_scope": (
                    _string(raw_session_overlay.get("overlay_scope")) or "session"
                ),
                "overlay_mode": (
                    _string(raw_session_overlay.get("overlay_mode"))
                    or ("additive" if overlay_capability_ids else None)
                ),
                "session_id": _string(raw_session_overlay.get("session_id")),
                "capability_ids": overlay_capability_ids,
                "status": (
                    _string(raw_session_overlay.get("status"))
                    or ("active" if overlay_capability_ids else None)
                ),
            }
        current_capability_trial = _mapping(metadata.get("current_capability_trial"))
        governance_result = resolve_industry_capability_governance_service(
            self,
        ).build_runtime_governance_result(
            layers=capability_layers,
            current_capability_trial=current_capability_trial,
            target_role_id=(
                _string(getattr(runtime, "industry_role_id", None))
                or _string(agent.get("role_id"))
                or _string(agent.get("industry_role_id"))
            ),
            target_seat_ref=(
                _string(metadata.get("selected_seat_ref"))
                or _string(current_capability_trial.get("selected_seat_ref"))
            ),
            selected_scope=(
                _string(current_capability_trial.get("selected_scope")) or "seat"
            ),
            candidate_id=_string(current_capability_trial.get("candidate_id")),
        )
        return {
            **agent,
            "capability_governance": {
                "is_projection": True,
                "is_truth_store": False,
                "source": "agent_runtime.metadata.capability_layers",
                "layers": layers_payload,
                "counts": {
                    "role_prototype": len(
                        _unique_strings(layers_payload.get("role_prototype_capability_ids")),
                    ),
                    "seat_instance": len(
                        _unique_strings(layers_payload.get("seat_instance_capability_ids")),
                    ),
                    "cycle_delta": len(
                        _unique_strings(layers_payload.get("cycle_delta_capability_ids")),
                    ),
                    "session_overlay": len(
                        _unique_strings(layers_payload.get("session_overlay_capability_ids")),
                    ),
                    "effective": len(
                        _unique_strings(layers_payload.get("effective_capability_ids")),
                    ),
                },
                "current_session_overlay": current_session_overlay,
                "current_capability_trial": (
                    current_capability_trial if current_capability_trial else None
                ),
                "governance_result": governance_result,
                "lifecycle": {
                    "employment_mode": (
                        _string(getattr(runtime, "employment_mode", None))
                        or _string(agent.get("employment_mode"))
                    ),
                    "activation_mode": (
                        _string(getattr(runtime, "activation_mode", None))
                        or _string(agent.get("activation_mode"))
                    ),
                    "desired_state": _string(getattr(runtime, "desired_state", None)),
                    "runtime_status": _string(getattr(runtime, "runtime_status", None)),
                    "status": _string(agent.get("status")),
                },
            },
        }

    def _build_instance_execution_summary(
        self,
        *,
        record: IndustryInstanceRecord,
        goals: list[dict[str, Any]],
        agents: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> IndustryExecutionSummary:
        goals_by_id = {
            _string(goal.get("goal_id")): goal
            for goal in goals
            if _string(goal.get("goal_id"))
        }
        agents_by_id = {
            _string(agent.get("agent_id")): agent
            for agent in agents
            if _string(agent.get("agent_id"))
        }
        evidence_by_id = {
            _string(item.get("id")): item
            for item in evidence
            if _string(item.get("id"))
        }
        latest_evidence = (
            max(evidence, key=lambda item: _sort_timestamp(item.get("created_at")))
            if evidence
            else None
        )
        autonomy_status = _string(record.autonomy_status)
        waiting_confirm_goal = next(
            (
                goal
                for goal in goals
                if _string(goal.get("status")) in {"paused", "draft"}
            ),
            None,
        )
        waiting_confirm_agent = next(
            (
                agent
                for agent in agents
                if _string(agent.get("status")) == "waiting-confirm"
                or _string(agent.get("runtime_status")) == "waiting-confirm"
            ),
            None,
        )
        focus_task = self._pick_execution_focus_task(tasks)
        if focus_task is None:
            if autonomy_status == "learning":
                return IndustryExecutionSummary(
                    status="learning",
                    current_focus_id=None,
                    current_focus=None,
                    current_owner_agent_id=None,
                    current_owner=None,
                    current_risk=None,
                    evidence_count=len(evidence),
                    latest_evidence_summary=self._evidence_summary(latest_evidence),
                    next_step="系统正在补齐行业学习材料，完成后会自动转入执行阶段。",
                    updated_at=_parse_datetime(
                        (
                            latest_evidence.get("created_at")
                            if isinstance(latest_evidence, dict)
                            else None
                        )
                    ),
                )
            if autonomy_status == "coordinating":
                return IndustryExecutionSummary(
                    status="coordinating",
                    current_focus_id=None,
                    current_focus=None,
                    current_owner_agent_id=None,
                    current_owner=None,
                    current_risk=None,
                    evidence_count=len(evidence),
                    latest_evidence_summary=self._evidence_summary(latest_evidence),
                    next_step="主脑正在协调执行位与 backlog，命中条件后会自动继续执行。",
                    updated_at=_parse_datetime(
                        (
                            latest_evidence.get("created_at")
                            if isinstance(latest_evidence, dict)
                            else None
                        )
                    ),
                )
            if (
                autonomy_status == "waiting-confirm"
                or waiting_confirm_goal is not None
                or waiting_confirm_agent is not None
            ):
                fallback_owner_agent_id = (
                    _string(waiting_confirm_agent.get("agent_id"))
                    if isinstance(waiting_confirm_agent, dict)
                    else None
                )
                fallback_owner = (
                    agents_by_id.get(fallback_owner_agent_id)
                    if fallback_owner_agent_id is not None
                    else None
                )
                return IndustryExecutionSummary(
                    status="waiting-confirm",
                    current_focus_id=None,
                    current_focus=None,
                    current_owner_agent_id=fallback_owner_agent_id,
                    current_owner=(
                        _string(fallback_owner.get("role_name"))
                        or _string(fallback_owner.get("name"))
                        if isinstance(fallback_owner, dict)
                        else None
                    ),
                    current_risk=(
                        _string(fallback_owner.get("risk_level"))
                        if isinstance(fallback_owner, dict)
                        else None
                    ),
                    evidence_count=len(evidence),
                    latest_evidence_summary=self._evidence_summary(latest_evidence),
                    next_step="请先在主脑控制线程里确认是否启动这一阶段。",
                    blocked_reason="系统正在等待首轮启动确认。",
                    updated_at=_parse_datetime(
                        (
                            latest_evidence.get("created_at")
                            if isinstance(latest_evidence, dict)
                            else None
                        )
                    ),
                )
            return IndustryExecutionSummary(
                status="idle",
                current_focus_id=None,
                current_focus=None,
                current_owner_agent_id=None,
                current_owner=None,
                current_risk=None,
                evidence_count=len(evidence),
                latest_evidence_summary=self._evidence_summary(latest_evidence),
                next_step="当前没有可继续的执行链。",
                updated_at=_parse_datetime(
                    latest_evidence.get("created_at")
                    if isinstance(latest_evidence, dict)
                    else None
                ),
            )

        task_payload = _mapping(focus_task.get("task"))
        runtime_payload = _mapping(focus_task.get("runtime"))
        focus_state = self._derive_execution_task_state(focus_task)
        owner_agent_id = (
            _string(runtime_payload.get("last_owner_agent_id"))
            or _string(task_payload.get("owner_agent_id"))
        )
        owner_payload = agents_by_id.get(owner_agent_id) if owner_agent_id is not None else None
        latest_evidence_id = _string(focus_task.get("latest_evidence_id"))
        latest_task_evidence = (
            evidence_by_id.get(latest_evidence_id)
            if latest_evidence_id is not None
            else None
        ) or latest_evidence
        trigger = self._extract_execution_task_trigger(focus_task)
        updated_at = _parse_datetime(
            runtime_payload.get("updated_at")
            or task_payload.get("updated_at")
            or (
                latest_task_evidence.get("created_at")
                if isinstance(latest_task_evidence, dict)
                else None
            ),
        )
        focus_status = str(focus_state["status"])
        runtime_focus_id = _string(runtime_payload.get("current_focus_id"))
        runtime_focus = _string(runtime_payload.get("current_focus"))
        if focus_status == "idle" and autonomy_status in {"learning", "coordinating"}:
            next_step = (
                "系统正在补齐行业学习材料，完成后会自动转入执行阶段。"
                if autonomy_status == "learning"
                else "主脑正在协调执行位与 backlog，命中条件后会自动继续执行。"
            )
            return IndustryExecutionSummary(
                status=autonomy_status,
                current_focus_id=runtime_focus_id,
                current_focus=runtime_focus,
                current_owner_agent_id=owner_agent_id,
                current_owner=(
                    _string(owner_payload.get("role_name"))
                    or _string(owner_payload.get("name"))
                    if isinstance(owner_payload, dict)
                    else None
                ),
                current_risk=(
                    _string(runtime_payload.get("risk_level"))
                    or _string(task_payload.get("current_risk_level"))
                    or (
                        _string(owner_payload.get("risk_level"))
                        if isinstance(owner_payload, dict)
                        else None
                    )
                ),
                evidence_count=int(focus_task.get("evidence_count") or 0),
                latest_evidence_summary=self._evidence_summary(latest_task_evidence),
                next_step=next_step,
                current_task_id=_string(task_payload.get("id")),
                current_task_route=_string(focus_task.get("route")),
                current_stage=autonomy_status,
                trigger_source=trigger["source"],
                trigger_actor=trigger["actor"],
                trigger_reason=trigger["reason"],
                updated_at=updated_at,
            )
        return IndustryExecutionSummary(
            status=focus_status,
            current_focus_id=runtime_focus_id,
            current_focus=runtime_focus,
            current_owner_agent_id=owner_agent_id,
            current_owner=(
                _string(owner_payload.get("role_name"))
                or _string(owner_payload.get("name"))
                if isinstance(owner_payload, dict)
                else None
            ),
            current_risk=(
                _string(runtime_payload.get("risk_level"))
                or _string(task_payload.get("current_risk_level"))
                or (
                    _string(owner_payload.get("risk_level"))
                    if isinstance(owner_payload, dict)
                    else None
                )
            ),
            evidence_count=int(focus_task.get("evidence_count") or 0),
            latest_evidence_summary=self._evidence_summary(latest_task_evidence),
            next_step=self._execution_next_step(
                status=str(focus_state["status"]),
            ),
            current_task_id=_string(task_payload.get("id")),
            current_task_route=_string(focus_task.get("route")),
            current_stage=(
                _string(runtime_payload.get("current_phase"))
                or _string(task_payload.get("status"))
            ),
            trigger_source=trigger["source"],
            trigger_actor=trigger["actor"],
            trigger_reason=trigger["reason"],
            blocked_reason=(
                str(focus_state["blocked_reason"])
                if focus_state.get("blocked_reason") is not None
                else None
            ),
            stuck_reason=(
                str(focus_state["stuck_reason"])
                if focus_state.get("stuck_reason") is not None
                else None
            ),
            updated_at=updated_at,
        )

    def _build_instance_detail(

        self,

        record: IndustryInstanceRecord,

        *,
        assignment_id: str | None = None,
        backlog_item_id: str | None = None,

    ) -> IndustryInstanceDetail:

        profile = IndustryProfile.model_validate(

            record.profile_payload or {"industry": record.label},

        )

        team = self._materialize_team_blueprint(record)

        status = self._derive_instance_status(record)
        selected_assignment_id = _string(assignment_id)
        selected_backlog_item_id = _string(backlog_item_id)

        team = team.model_copy(

            update={

                "status": (

                    _string(record.autonomy_status)

                    or _string(record.lifecycle_status)

                    or status

                ),

                "autonomy_status": _string(record.autonomy_status),

                "lifecycle_status": _string(record.lifecycle_status),

            },

        )

        execution_core_identity = self._materialize_execution_core_identity(

            record,

            profile=profile,

            team=team,

        )

        strategy_memory = self._load_strategy_memory(

            record,

            profile=profile,

            team=team,

            execution_core_identity=execution_core_identity,

        )

        lane_records = self._list_operating_lanes(record.instance_id)

        current_cycle_record = self._current_operating_cycle_record(record.instance_id)

        cycle_records = self._list_operating_cycles(record.instance_id, limit=None)

        assignment_records = self._list_assignment_records(record.instance_id)

        agent_report_records = self._list_agent_report_records(

            record.instance_id,

            limit=None,

        )

        backlog_records = self._list_backlog_items(record.instance_id, limit=None)

        lanes = [

            {

                "lane_id": lane.id,

                "lane_key": lane.lane_key,

                "title": lane.title,

                "summary": lane.summary,

                "status": lane.status,

                "owner_agent_id": lane.owner_agent_id,

                "owner_role_id": lane.owner_role_id,

                "priority": lane.priority,

                "health_status": lane.health_status,

                "source_ref": lane.source_ref,

                "metadata": dict(lane.metadata or {}),

                "created_at": lane.created_at,

                "updated_at": lane.updated_at,

                "route": (

                    f"/api/runtime-center/agents/{quote(lane.owner_agent_id)}"

                    if lane.owner_agent_id

                    else None

                ),

            }

            for lane in sorted(

                lane_records,

                key=lambda item: (-int(item.priority), _sort_timestamp(item.updated_at)),

            )

        ]

        lane_route_by_id = {

            _string(item.get("lane_id")): _string(item.get("route"))

            for item in lanes

            if _string(item.get("lane_id"))

        }

        current_cycle_synthesis = self._resolve_report_synthesis_payload(

            cycle_record=current_cycle_record,

            agent_report_records=agent_report_records,

        )

        current_cycle = (

            {

                "cycle_id": current_cycle_record.id,

                "cycle_kind": current_cycle_record.cycle_kind,

                "title": current_cycle_record.title,

                "summary": current_cycle_record.summary,

                "status": current_cycle_record.status,

                "source_ref": current_cycle_record.source_ref,

                "started_at": current_cycle_record.started_at,

                "due_at": current_cycle_record.due_at,

                "completed_at": current_cycle_record.completed_at,

                "focus_lane_ids": list(current_cycle_record.focus_lane_ids or []),

                "backlog_item_ids": list(current_cycle_record.backlog_item_ids or []),

                "assignment_ids": list(current_cycle_record.assignment_ids or []),

                "report_ids": list(current_cycle_record.report_ids or []),

                "metadata": dict(current_cycle_record.metadata or {}),

                "synthesis": current_cycle_synthesis,

                "route": f"/api/runtime-center/industry/{quote(record.instance_id)}",

            }

            if current_cycle_record is not None

            else None

        )

        cycles = [

            {

                "cycle_id": cycle.id,

                "cycle_kind": cycle.cycle_kind,

                "title": cycle.title,

                "summary": cycle.summary,

                "status": cycle.status,

                "source_ref": cycle.source_ref,

                "started_at": cycle.started_at,

                "due_at": cycle.due_at,

                "completed_at": cycle.completed_at,

                "focus_lane_ids": list(cycle.focus_lane_ids or []),

                "backlog_item_ids": list(cycle.backlog_item_ids or []),

                "assignment_ids": list(cycle.assignment_ids or []),

                "report_ids": list(cycle.report_ids or []),

                "metadata": dict(cycle.metadata or {}),

                "synthesis": self._resolve_report_synthesis_payload(

                    cycle_record=cycle,

                    agent_report_records=agent_report_records,

                ),

                "is_current": current_cycle_record is not None and cycle.id == current_cycle_record.id,

                "route": f"/api/runtime-center/industry/{quote(record.instance_id)}",

            }

            for cycle in cycle_records

        ]

        current_cycle = self._propagate_replan_activation_summary(
            current_cycle=current_cycle,
            replan_cycle=self._resolve_replan_cycle_entry(
                current_cycle=current_cycle,
                current_cycle_entry=current_cycle,
                cycles=[item for item in cycles if isinstance(item, dict)],
            ),
        )

        assignments = [

            {

                "assignment_id": assignment.id,

                "cycle_id": assignment.cycle_id,

                "lane_id": assignment.lane_id,

                "backlog_item_id": assignment.backlog_item_id,

                "goal_id": assignment.goal_id,

                "task_id": assignment.task_id,

                "owner_agent_id": assignment.owner_agent_id,

                "owner_role_id": assignment.owner_role_id,

                "title": assignment.title,

                "summary": assignment.summary,

                "status": assignment.status,

                "report_back_mode": assignment.report_back_mode,

                "evidence_ids": list(assignment.evidence_ids or []),

                "last_report_id": assignment.last_report_id,

                "metadata": dict(assignment.metadata or {}),

                "created_at": assignment.created_at,

                "updated_at": assignment.updated_at,

                "selected": bool(selected_assignment_id and assignment.id == selected_assignment_id),

                "route": (
                    f"/api/runtime-center/industry/{quote(record.instance_id)}"
                    f"?assignment_id={quote(assignment.id)}"
                ),

            }

            for assignment in sorted(

                assignment_records,

                key=lambda item: _sort_timestamp(item.updated_at),

                reverse=True,

            )

        ]

        agent_reports = [

            {

                "report_id": report.id,

                "cycle_id": report.cycle_id,

                "assignment_id": report.assignment_id,

                "goal_id": report.goal_id,

                "task_id": report.task_id,

                "lane_id": report.lane_id,

                "owner_agent_id": report.owner_agent_id,

                "owner_role_id": report.owner_role_id,

                "report_kind": report.report_kind,

                "headline": report.headline,

                "summary": report.summary,

                "status": report.status,

                "result": report.result,

                "risk_level": report.risk_level,

                "evidence_ids": list(report.evidence_ids or []),

                "decision_ids": list(report.decision_ids or []),

                "processed": report.processed,

                "processed_at": report.processed_at,

                "metadata": dict(report.metadata or {}),

                "created_at": report.created_at,

                "updated_at": report.updated_at,

                "route": (

                    f"/api/runtime-center/tasks/{quote(report.task_id)}"

                    if report.task_id

                    else (

                        f"/api/goals/{quote(report.goal_id)}/detail"

                        if report.goal_id

                        else lane_route_by_id.get(report.lane_id)

                    )

                ),

            }

            for report in sorted(

                agent_report_records,

                key=lambda item: _sort_timestamp(item.updated_at),

                reverse=True,

            )

        ]

        backlog = [

            {

                "backlog_item_id": item.id,

                "lane_id": item.lane_id,

                "cycle_id": item.cycle_id,

                "assignment_id": item.assignment_id,

                "goal_id": item.goal_id,

                "title": item.title,

                "summary": item.summary,

                "status": item.status,

                "priority": item.priority,

                "source_kind": item.source_kind,

                "source_ref": item.source_ref,

                "evidence_ids": list(item.evidence_ids or []),

                "metadata": dict(item.metadata or {}),

                "created_at": item.created_at,

                "updated_at": item.updated_at,

                "selected": bool(selected_backlog_item_id and item.id == selected_backlog_item_id),

                "route": (
                    f"/api/runtime-center/industry/{quote(record.instance_id)}"
                    f"?backlog_item_id={quote(item.id)}"
                ),

            }

            for item in sorted(

                backlog_records,

                key=lambda candidate: (

                    0 if candidate.status in {"open", "selected"} else 1,

                    -int(candidate.priority),

                    _sort_timestamp(candidate.updated_at),

                ),

            )

        ]

        main_brain_cognitive_surface = build_main_brain_cognitive_surface(

            current_cycle=current_cycle,

            cycles=cycles,

            backlog=backlog,

            agent_reports=agent_reports,

        )

        if current_cycle is not None:

            current_cycle = {

                **current_cycle,

                "main_brain_cognitive_surface": main_brain_cognitive_surface,

            }

        judgment_cycle_id = _string(

            _mapping(main_brain_cognitive_surface.get("judgment")).get("cycle_id"),

        )

        cycles = [

            {

                **cycle,

                "main_brain_cognitive_surface": (

                    main_brain_cognitive_surface

                    if judgment_cycle_id is not None

                    and _string(cycle.get("cycle_id")) == judgment_cycle_id

                    else build_main_brain_cognitive_surface(

                        current_cycle=cycle,

                        cycles=[cycle],

                        backlog=backlog,

                        agent_reports=agent_reports,

                    )

                ),

            }

            for cycle in cycles

        ]
        main_brain_planning = self._build_main_brain_planning_surface(
            record=record,
            current_cycle=current_cycle,
            cycles=cycles,
            assignments=assignments,
            selected_assignment_id=selected_assignment_id,
            selected_backlog_item_id=selected_backlog_item_id,
        )
        main_brain_planning_payload = main_brain_planning.model_dump(mode="json")
        if current_cycle is not None:
            current_cycle = {
                **current_cycle,
                "main_brain_planning": main_brain_planning_payload,
            }

        goals: list[dict[str, Any]] = []

        tasks_by_id: dict[str, dict[str, Any]] = {}

        decisions_by_id: dict[str, dict[str, Any]] = {}

        evidence_by_id: dict[str, dict[str, Any]] = {}

        patches_by_id: dict[str, dict[str, Any]] = {}

        growth_by_id: dict[str, dict[str, Any]] = {}

        task_ids: set[str] = set()

        agent_ids = set(record.agent_ids or [])

        updated_candidates: list[datetime] = [

            candidate

            for candidate in (record.updated_at, record.created_at)

            if candidate is not None

        ]



        for goal_id in self._resolve_instance_goal_ids(record):

            goal = self._goal_service.get_goal(goal_id)

            if goal is None:

                continue

            override = self._goal_override_repository.get_override(goal.id)

            if not self._goal_belongs_to_instance(

                goal,

                record=record,

                override=override,

            ):

                continue

            goal_detail = self._goal_service.get_goal_detail(goal.id) or {}

            goal_context = self._resolve_goal_runtime_context(

                goal,

                override=override,

                record=record,

                team=team,

            )

            role = self._resolve_role_blueprint_by_agent(

                team,

                _string(goal_context.get("owner_agent_id")),

            ) or self._resolve_role_blueprint(

                team,

                _string(goal_context.get("industry_role_id")),

            )

            goal_entry = {

                "goal_id": goal.id,

                "kind": _string(goal_context.get("goal_kind")) or "industry",

                "title": goal.title,

                "summary": goal.summary,

                "status": goal.status,

                "priority": goal.priority,

                "owner_scope": goal.owner_scope,

                "industry_instance_id": _string(goal_context.get("industry_instance_id")) or goal.industry_instance_id,

                "lane_id": _string(goal_context.get("lane_id")) or goal.lane_id,

                "cycle_id": _string(goal_context.get("cycle_id")) or goal.cycle_id,

                "goal_class": goal.goal_class,

                "plan_steps": list(override.plan_steps or []) if override is not None else [],

                "owner_agent_id": _string(goal_context.get("owner_agent_id")),

                "role_id": role.role_id if role is not None else _string(goal_context.get("industry_role_id")),

                "role_name": (

                    role.role_name

                    if role is not None

                    else _string(goal_context.get("industry_role_name"))

                    or _string(goal_context.get("role_name"))

                ),

                "agent_class": role.agent_class if role is not None else _string(goal_context.get("agent_class")),

                "route": f"/api/goals/{goal.id}/detail",

            }

            updated_candidates.extend(

                candidate

                for candidate in (goal.updated_at, goal.created_at)

                if candidate is not None

            )

            goal_tasks = goal_detail.get("tasks")

            if isinstance(goal_tasks, list):

                goal_entry["task_count"] = len(goal_tasks)

                for item in goal_tasks:

                    if not isinstance(item, dict):

                        continue

                    task = item.get("task")

                    if not isinstance(task, dict):

                        continue

                    task_id = _string(task.get("id"))

                    if not task_id:

                        continue

                    task_ids.add(task_id)

                    task_payload = dict(item)

                    task_payload["route"] = f"/api/runtime-center/tasks/{task_id}"

                    tasks_by_id[task_id] = task_payload

            else:

                goal_entry["task_count"] = 0

            goal_decisions = goal_detail.get("decisions")

            if isinstance(goal_decisions, list):

                goal_entry["decision_count"] = len(goal_decisions)

                for item in goal_decisions:

                    if isinstance(item, dict) and _string(item.get("id")):

                        decisions_by_id[str(item["id"])] = dict(item)

            else:

                goal_entry["decision_count"] = 0

            goal_evidence = goal_detail.get("evidence")

            if isinstance(goal_evidence, list):

                goal_entry["evidence_count"] = len(goal_evidence)

                for item in goal_evidence:

                    if isinstance(item, dict) and _string(item.get("id")):

                        evidence_by_id[str(item["id"])] = dict(item)

            else:

                goal_entry["evidence_count"] = 0

            goal_patches = goal_detail.get("patches")

            if isinstance(goal_patches, list):

                for item in goal_patches:

                    if isinstance(item, dict) and _string(item.get("id")):

                        patches_by_id[str(item["id"])] = dict(item)

            goal_growth = goal_detail.get("growth")

            if isinstance(goal_growth, list):

                for item in goal_growth:

                    if isinstance(item, dict) and _string(item.get("id")):

                        growth_by_id[str(item["id"])] = dict(item)

            goal_agents = goal_detail.get("agents")

            if isinstance(goal_agents, list):

                for item in goal_agents:

                    if isinstance(item, dict):

                        agent_id = _string(item.get("agent_id"))

                        if agent_id:

                            agent_ids.add(agent_id)

            goals.append(goal_entry)



        additional_evidence_ids = {

            evidence_id

            for collection in (

                [item.get("evidence_ids") for item in assignments],

                [item.get("evidence_ids") for item in agent_reports],

                [item.get("evidence_ids") for item in backlog],

            )

            for value in collection

            if isinstance(value, list)

            for evidence_id in value

            if _string(evidence_id)

        }

        if self._evidence_ledger is not None:

            for evidence_id in additional_evidence_ids:

                normalized_id = _string(evidence_id)

                if normalized_id is None or normalized_id in evidence_by_id:

                    continue

                evidence_record = self._evidence_ledger.get_record(normalized_id)

                if evidence_record is None:

                    continue

                evidence_by_id[normalized_id] = {

                    "id": evidence_record.id,

                    "task_id": evidence_record.task_id,

                    "actor_ref": evidence_record.actor_ref,

                    "environment_ref": evidence_record.environment_ref,

                    "capability_ref": evidence_record.capability_ref,

                    "risk_level": evidence_record.risk_level,

                    "action_summary": evidence_record.action_summary,

                    "result_summary": evidence_record.result_summary,

                    "status": evidence_record.status,

                    "metadata": dict(evidence_record.metadata or {}),

                    "artifact_refs": list(evidence_record.artifact_refs or []),

                    "replay_refs": list(evidence_record.replay_refs or []),

                    "created_at": evidence_record.created_at,

                }



        schedules = self._list_instance_schedules(

            record.instance_id,

            schedule_ids=self._list_schedule_ids_for_instance(record.instance_id),

        )

        agents = self._list_instance_agents(agent_ids)
        agents = self._apply_execution_core_identity_to_agents(

            agents=agents,

            execution_core_identity=execution_core_identity,

            goals=goals,

        )
        agents = [
            self._enrich_agent_capability_governance_payload(agent)
            for agent in agents
        ]

        proposals = self._list_instance_proposals(

            goal_ids=set(self._resolve_instance_goal_ids(record)),

            task_ids=task_ids,

            agent_ids=agent_ids,

        )

        acquisition_proposals = self._list_instance_acquisition_proposals(

            record.instance_id,

        )

        install_binding_plans = self._list_instance_install_binding_plans(

            record.instance_id,

        )

        onboarding_runs = self._list_instance_onboarding_runs(record.instance_id)

        reports = self._build_reports(

            evidence=list(evidence_by_id.values()),

            proposals=proposals,

            patches=list(patches_by_id.values()),

            growth=list(growth_by_id.values()),

            decisions=list(decisions_by_id.values()),

        )

        staffing = self._build_instance_staffing(

            team=team,

            agents=agents,

            backlog=backlog,

            assignments=assignments,

            agent_reports=agent_reports,

        )

        execution = self._build_instance_execution_summary(

            record=record,

            goals=goals,

            agents=agents,

            tasks=list(tasks_by_id.values()),

            evidence=list(evidence_by_id.values()),

        )
        baseline_live_focus = self._resolve_live_focus_payload(
            execution=execution,
            assignments=assignments,
            backlog=backlog,
            tasks=list(tasks_by_id.values()),
            selected_assignment_id=None,
            selected_backlog_item_id=None,
        )
        live_focus = self._resolve_live_focus_payload(
            execution=execution,
            assignments=assignments,
            backlog=backlog,
            tasks=list(tasks_by_id.values()),
            selected_assignment_id=selected_assignment_id,
            selected_backlog_item_id=selected_backlog_item_id,
        )
        live_focus_id = _string(live_focus.get("current_focus_id"))
        live_focus_title = _string(live_focus.get("current_focus_title"))
        if execution is not None and (live_focus_id is not None or live_focus_title is not None):
            execution = execution.model_copy(
                update={
                    "current_focus_id": live_focus_id,
                    "current_focus": live_focus_title,
                },
            )

        focused_assignment = (
            next(
                (
                    item
                    for item in assignments
                    if _string(item.get("assignment_id")) == selected_assignment_id
                ),
                None,
            )
            if selected_assignment_id is not None
            else None
        )
        focused_backlog = (
            next(
                (
                    item
                    for item in backlog
                    if _string(item.get("backlog_item_id")) == selected_backlog_item_id
                ),
                None,
            )
            if selected_backlog_item_id is not None
            else None
        )
        focus_selection = None
        if isinstance(focused_assignment, dict):
            focus_selection = {
                "selection_kind": "assignment",
                "assignment_id": _string(focused_assignment.get("assignment_id")),
                "backlog_item_id": _string(focused_assignment.get("backlog_item_id")),
                "title": _string(focused_assignment.get("title")),
                "summary": _string(focused_assignment.get("summary")),
                "status": _string(focused_assignment.get("status")),
                "route": _string(focused_assignment.get("route")),
            }
        elif isinstance(focused_backlog, dict):
            focus_selection = {
                "selection_kind": "backlog",
                "assignment_id": _string(focused_backlog.get("assignment_id")),
                "backlog_item_id": _string(focused_backlog.get("backlog_item_id")),
                "title": _string(focused_backlog.get("title")),
                "summary": _string(focused_backlog.get("summary")),
                "status": _string(focused_backlog.get("status")),
                "route": _string(focused_backlog.get("route")),
            }
        selection_matches_live_focus = False
        if focus_selection is not None:
            selection_kind = _string(focus_selection.get("selection_kind"))
            if selection_kind == "assignment":
                selection_matches_live_focus = (
                    _string(focus_selection.get("assignment_id"))
                    == _string(baseline_live_focus.get("current_assignment_id"))
                )
            elif selection_kind == "backlog":
                selected_assignment_ref = _string(focus_selection.get("assignment_id"))
                selection_matches_live_focus = (
                    selected_assignment_ref is not None
                    and selected_assignment_ref
                    == _string(baseline_live_focus.get("current_assignment_id"))
                )
        main_chain = self._build_instance_main_chain(

            record=record,

            lanes=lanes,

            backlog=backlog,

            current_cycle=current_cycle,

            cycles=cycles,

            assignments=assignments,

            agent_reports=agent_reports,

            goals=goals,

            agents=agents,

            tasks=list(tasks_by_id.values()),

            evidence=list(evidence_by_id.values()),

            execution=execution,

            strategy_memory=strategy_memory,

            selected_assignment_id=selected_assignment_id,

            selected_backlog_item_id=selected_backlog_item_id,

        )

        updated_candidates.extend(

            candidate

            for candidate in (

                *(lane.updated_at for lane in lane_records),

                *(backlog_item.updated_at for backlog_item in backlog_records),

                *(cycle.updated_at for cycle in cycle_records),

                *(assignment.updated_at for assignment in assignment_records),

                *(report.updated_at for report in agent_report_records),

                *(_parse_datetime(schedule.get("updated_at")) for schedule in schedules),

                *(_parse_datetime(agent.get("updated_at")) for agent in agents),

            )

            if candidate is not None

        )

        media_service = getattr(self, "_media_service", None)

        media_analyses = (

            media_service.list_analyses(

                industry_instance_id=record.instance_id,

                limit=50,

            )

            if media_service is not None

            else []

        )

        return IndustryInstanceDetail(

            instance_id=record.instance_id,

            bootstrap_kind="industry-v1",

            label=record.label,

            summary=record.summary,

            owner_scope=record.owner_scope,

            profile=profile,

            team=team,

            execution_core_identity=execution_core_identity,

            strategy_memory=strategy_memory,

            status=status,

            autonomy_status=_string(record.autonomy_status),

            lifecycle_status=_string(record.lifecycle_status),

            updated_at=max(updated_candidates) if updated_candidates else None,

            stats={
                "agent_count": len(agents),

                "lane_count": len(lanes),

                "backlog_count": len(backlog),

                "open_backlog_count": sum(

                    1 for item in backlog if _string(item.get("status")) in {"open", "selected"}

                ),

                "cycle_count": len(cycles),

                "assignment_count": len(assignments),

                "agent_report_count": len(agent_reports),

                "task_count": len(tasks_by_id),

                "schedule_count": len(schedules),

                "decision_count": len(decisions_by_id),

                "evidence_count": len(evidence_by_id),

                "patch_count": len(patches_by_id),

                "growth_count": len(growth_by_id),

                "proposal_count": len(proposals),

                "acquisition_proposal_count": len(acquisition_proposals),

                "install_binding_plan_count": len(install_binding_plans),

                "onboarding_run_count": len(onboarding_runs),

            },

            routes={

                "detail": f"/api/industry/v1/instances/{record.instance_id}",

                "runtime_detail": f"/api/runtime-center/industry/{record.instance_id}",

                "runtime_center": "/api/runtime-center/surface",

                "strategy_memory": (

                    f"/api/runtime-center/strategy-memory?industry_instance_id={quote(record.instance_id)}"

                ),

                "goals": [goal["route"] for goal in goals if isinstance(goal.get("route"), str)],

                "agents": [agent["route"] for agent in agents if isinstance(agent.get("route"), str)],

                "schedules": [

                    schedule["route"]

                    for schedule in schedules

                    if isinstance(schedule.get("route"), str)

                ],

                "acquisition_proposals": [

                    item["route"]

                    for item in acquisition_proposals

                    if isinstance(item.get("route"), str)

                ],

                "install_binding_plans": [

                    item["route"]

                    for item in install_binding_plans

                    if isinstance(item.get("route"), str)

                ],

                "onboarding_runs": [

                    item["route"]

                    for item in onboarding_runs

                    if isinstance(item.get("route"), str)

                ],

            },

            goals=goals,

            agents=agents,

            schedules=schedules,

            lanes=lanes,

            backlog=backlog,

            staffing=staffing,

            current_cycle=current_cycle,

            cycles=cycles,

            assignments=assignments,

            agent_reports=agent_reports,

            tasks=sorted(

                tasks_by_id.values(),

                key=lambda item: _sort_timestamp(item.get("task", {}).get("updated_at")),

                reverse=True,

            ),

            decisions=sorted(

                decisions_by_id.values(),

                key=lambda item: _sort_timestamp(item.get("created_at")),

                reverse=True,

            ),

            evidence=sorted(

                evidence_by_id.values(),

                key=lambda item: _sort_timestamp(item.get("created_at")),

                reverse=True,

            ),

            patches=sorted(

                patches_by_id.values(),

                key=lambda item: _sort_timestamp(item.get("created_at")),

                reverse=True,

            ),

            growth=sorted(

                growth_by_id.values(),

                key=lambda item: _sort_timestamp(item.get("created_at")),

                reverse=True,

            ),

            proposals=proposals,

            acquisition_proposals=acquisition_proposals,

            install_binding_plans=install_binding_plans,

            onboarding_runs=onboarding_runs,

            execution=execution,

            main_chain=main_chain,
            main_brain_planning=main_brain_planning,

            focus_selection=focus_selection,

            reports=reports,

            media_analyses=media_analyses,

        )

    def _pick_execution_focus_task(
        self,
        tasks: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not tasks:
            return None
        live_tasks = [
            item
            for item in tasks
            if _string(_mapping(item.get("task")).get("status")) not in {"completed", "cancelled"}
        ]
        if not live_tasks:
            return None
        priorities = {
            "waiting-verification": 0,
            "waiting-confirm": 1,
            "waiting-resource": 2,
            "idle-loop": 3,
            "failed": 4,
            "executing": 5,
            "idle": 6,
        }
        ranked = sorted(
            live_tasks,
            key=lambda item: (
                priorities.get(
                    str(self._derive_execution_task_state(item)["status"]),
                    99,
                ),
                -_sort_timestamp(
                    _mapping(item.get("runtime")).get("updated_at")
                    or _mapping(item.get("task")).get("updated_at"),
                ).timestamp(),
            ),
        )
        return ranked[0] if ranked else None

    def _derive_execution_task_state(
        self,
        task_entry: dict[str, Any],
    ) -> dict[str, object]:
        task_payload = _mapping(task_entry.get("task"))
        runtime_payload = _mapping(task_entry.get("runtime"))
        runtime_status = _string(runtime_payload.get("runtime_status"))
        task_status = _string(task_payload.get("status")) or "created"
        status = runtime_status if task_status == "running" and runtime_status else task_status
        phase = _string(runtime_payload.get("current_phase")) or status or "created"
        detail_text = (
            _string(runtime_payload.get("last_error_summary"))
            or _string(runtime_payload.get("last_result_summary"))
            or _string(task_payload.get("summary"))
        )
        decision_count = int(task_entry.get("decision_count") or 0)
        verification_markers = (
            "验证码",
            "短信",
            "2fa",
            "two-factor",
            "二次验证",
            "设备确认",
            "滑块",
            "人机",
            "captcha",
            "verification",
            "verify",
        )
        resource_markers = (
            "缺少",
            "未找到",
            "不可用",
            "permission",
            "forbidden",
            "not available",
            "install",
            "api key",
            "登录",
            "cookie",
            "session",
            "resource",
            "文件",
        )
        if decision_count > 0 or status == "waiting-confirm" or phase == "waiting-confirm":
            if self._matches_execution_marker(detail_text, verification_markers):
                return {
                    "status": "waiting-verification",
                    "blocked_reason": detail_text or "Waiting for user-owned verification checkpoint.",
                    "stuck_reason": None,
                }
            return {
                "status": "waiting-confirm",
                "blocked_reason": detail_text or "Waiting for operator confirmation before continuing.",
                "stuck_reason": None,
            }
        if status in {"failed", "blocked", "cancelled"}:
            if self._matches_execution_marker(detail_text, verification_markers):
                return {
                    "status": "waiting-verification",
                    "blocked_reason": detail_text or "Waiting for user-owned verification checkpoint.",
                    "stuck_reason": None,
                }
            if self._matches_execution_marker(detail_text, resource_markers):
                return {
                    "status": "waiting-resource",
                    "blocked_reason": detail_text or "Waiting for an external resource or environment prerequisite.",
                    "stuck_reason": None,
                }
            return {
                "status": "failed",
                "blocked_reason": detail_text or "Execution failed or was blocked.",
                "stuck_reason": None,
            }
        if status in {"executing", "claimed", "running", "active", "queued", "created", "waiting"}:
            updated_at = _parse_datetime(
                runtime_payload.get("updated_at") or task_payload.get("updated_at"),
            )
            if (
                updated_at is not None
                and (datetime.now(timezone.utc) - updated_at).total_seconds() >= 180
            ):
                return {
                    "status": "idle-loop",
                    "blocked_reason": None,
                    "stuck_reason": "Task has not produced a new result or state transition for more than 3 minutes.",
                }
            return {
                "status": "executing",
                "blocked_reason": None,
                "stuck_reason": None,
            }
        return {
            "status": "idle",
            "blocked_reason": None,
            "stuck_reason": None,
        }

    def _extract_execution_task_trigger(
        self,
        task_entry: dict[str, Any],
    ) -> dict[str, str | None]:
        task_payload = _mapping(task_entry.get("task"))
        metadata = decode_kernel_task_metadata(task_payload.get("acceptance_criteria"))
        payload = _mapping(metadata.get("payload"))
        compiler = _mapping(payload.get("compiler"))
        task_seed = _mapping(payload.get("task_seed"))
        meta = _mapping(payload.get("meta"))
        return {
            "source": (
                _string(compiler.get("trigger_source"))
                or _string(task_seed.get("trigger_source"))
                or _string(meta.get("trigger_source"))
            ),
            "actor": (
                _string(compiler.get("trigger_actor"))
                or _string(task_seed.get("trigger_actor"))
                or _string(meta.get("trigger_actor"))
            ),
            "reason": (
                _string(compiler.get("trigger_reason"))
                or _string(task_seed.get("trigger_reason"))
                or _string(meta.get("trigger_reason"))
            ),
        }

    def _execution_next_step(
        self,
        *,
        status: str,
    ) -> str:
        if status == "waiting-verification":
            return "等待用户完成验证码、短信、设备确认或其他人工验证后继续。"
        if status == "waiting-confirm":
            return "等待人工确认通过后继续推进当前执行链。"
        if status == "waiting-resource":
            return "等待外部资源、登录态或环境前置条件补齐后继续。"
        if status == "idle-loop":
            return "当前长时间无进展，先检查是否在重复空转，再决定重试或改派。"
        if status == "failed":
            return "先处理失败原因，再决定重试、改派或终止。"
        if status == "executing":
            return "继续当前执行，并把关键动作和证据持续回写。"
        return "当前没有可继续的执行链。"
