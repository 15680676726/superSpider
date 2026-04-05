# -*- coding: utf-8 -*-
"""Cycle planner that compiles runtime facts into a formal cycle launch decision."""
from __future__ import annotations

import math
import re
from collections.abc import Sequence
from datetime import datetime, timezone

from ...state import AgentReportRecord, BacklogItemRecord, IndustryInstanceRecord, OperatingCycleRecord
from .models import (
    CyclePlanningDecision,
    PlanningLaneBudget,
    PlanningStrategyConstraints,
    StrategyTriggerRule,
    build_planning_shell_payload,
    project_task_subgraph_to_planning_focus,
)

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_-]{1,}")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _number(value: object | None) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _sort_timestamp(value: object | None) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    return 0.0


def _unique_strings(*values: object) -> list[str]:
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


def _tokenize(text: object | None) -> list[str]:
    raw = str(text or "").strip().lower()
    if not raw:
        return []
    return [token for token in _TOKEN_RE.findall(raw) if len(token) > 1]


def _lane_metadata_key(lane_id: str | None) -> str:
    return lane_id or "__no_lane__"


def _backlog_is_report_followup(item: BacklogItemRecord) -> bool:
    metadata = dict(item.metadata or {})
    if _string(metadata.get("source_report_id")) is not None:
        return True
    source_report_ids = metadata.get("source_report_ids")
    if isinstance(source_report_ids, Sequence) and not isinstance(source_report_ids, str):
        if any(_string(entry) is not None for entry in source_report_ids):
            return True
    return _string(metadata.get("synthesis_kind")) in {
        "followup-needed",
        "failed-report",
        "conflict",
    }


def _backlog_followup_overdue_score(item: BacklogItemRecord) -> float:
    if not _backlog_is_report_followup(item):
        return 0.0
    metadata = dict(item.metadata or {})
    return max(
        _number(metadata.get("followup_overdue_cycles")),
        _number(metadata.get("overdue_cycles")),
        _number(metadata.get("days_overdue")),
        1.0 if metadata.get("followup_due_now") else 0.0,
    )


class CyclePlanningCompiler:
    """Pure planner for whether the next operating cycle should start."""

    @staticmethod
    def _planning_shell(record: IndustryInstanceRecord, cycle_kind: str) -> dict[str, str]:
        return build_planning_shell_payload(
            mode="cycle-planning-shell",
            scope="operating-cycle",
            plan_id=f"industry:{record.instance_id}:cycle-plan",
            resume_key=f"industry:{record.instance_id}:next-cycle",
            fork_key=f"cycle:{cycle_kind}",
            verify_reminder=(
                "Verify backlog selection and lane pressure before materializing assignments."
            ),
        )

    def plan(
        self,
        *,
        record: IndustryInstanceRecord,
        current_cycle: OperatingCycleRecord | None,
        next_cycle_due_at: datetime | None,
        open_backlog: Sequence[BacklogItemRecord],
        pending_reports: Sequence[AgentReportRecord],
        force: bool,
        force_scoped_backlog: bool = False,
        strategy_constraints: PlanningStrategyConstraints | None = None,
        task_subgraph: object | None = None,
    ) -> CyclePlanningDecision:
        constraints = self._merge_task_subgraph_into_constraints(
            constraints=PlanningStrategyConstraints.from_value(strategy_constraints),
            task_subgraph=task_subgraph,
        )
        selection_limit = self._selection_limit(constraints)
        lane_budgets = self._lane_budget_map(constraints)
        lane_budget_outcomes: dict[str, dict[str, object]] = {}

        if lane_budgets and not force:
            selected, lane_budget_outcomes = self._budget_constrained_backlog(
                open_backlog=open_backlog,
                constraints=constraints,
                selection_limit=selection_limit,
                lane_budgets=lane_budgets,
            )
        else:
            candidates = self._candidate_backlog(
                open_backlog=open_backlog,
                constraints=constraints,
            )
            selected = list(candidates[:selection_limit])
        cycle_kind, cycle_kind_reason = self._resolve_cycle_kind(
            constraints=constraints,
        )

        if force:
            should_start = bool(selected or pending_reports)
            relation_projection = self._relation_focus_projection(
                items=selected,
                constraints=constraints,
            )
            return CyclePlanningDecision(
                should_start=should_start,
                reason="forced" if should_start else "forced-empty",
                cycle_kind=(
                    current_cycle.cycle_kind
                    if current_cycle is not None
                    else cycle_kind
                ),
                selected_backlog_item_ids=[item.id for item in selected],
                selected_lane_ids=_unique_strings(
                    [item.lane_id for item in selected if item.lane_id is not None],
                ),
                max_assignment_count=len(selected),
                affected_relation_ids=relation_projection["relation_ids"],
                affected_relation_kinds=relation_projection["relation_kinds"],
                summary=(
                    "Force-started cycle materialization from scoped backlog."
                    if should_start
                    else "Force requested a cycle launch but no materializable backlog or pending report remained."
                ),
                planning_policy=list(constraints.planning_policy or []),
                planning_shell=self._planning_shell(
                    record,
                    current_cycle.cycle_kind if current_cycle is not None else cycle_kind,
                ),
                metadata=self._decision_metadata(
                    record=record,
                    open_backlog=open_backlog,
                    pending_reports=pending_reports,
                    constraints=constraints,
                    lane_budget_outcomes=lane_budget_outcomes,
                    lane_budget_mode="force-override" if lane_budgets else None,
                    force_scoped_backlog=force_scoped_backlog,
                    cycle_kind_reason=(
                        "forced-existing-cycle-kind"
                        if current_cycle is not None
                        else cycle_kind_reason
                    ),
                ),
            )

        if current_cycle is not None and current_cycle.status not in {"completed", "cancelled"}:
            return CyclePlanningDecision(
                should_start=False,
                reason="cycle-inflight",
                cycle_kind=current_cycle.cycle_kind,
                max_assignment_count=0,
                summary="A formal cycle is already active, so planner launch is held.",
                planning_policy=list(constraints.planning_policy or []),
                planning_shell=self._planning_shell(record, current_cycle.cycle_kind),
                metadata=self._decision_metadata(
                    record=record,
                    open_backlog=open_backlog,
                    pending_reports=pending_reports,
                    constraints=constraints,
                    lane_budget_outcomes=lane_budget_outcomes,
                    lane_budget_mode="constrained" if lane_budgets else None,
                    force_scoped_backlog=force_scoped_backlog,
                    cycle_kind_reason="cycle-inflight",
                ),
            )

        should_start = bool(selected)
        reason = "planned-open-backlog" if should_start else "planner-no-open-backlog"
        if (
            not should_start
            and next_cycle_due_at is not None
            and next_cycle_due_at <= _utc_now()
            and pending_reports
        ):
            reason = "pending-reports-without-materializable-backlog"
        relation_projection = self._relation_focus_projection(
            items=selected,
            constraints=constraints,
        )

        summary = (
            f"Plan a {cycle_kind} cycle for {len(selected)} backlog item(s) across "
            f"{len(_unique_strings(item.lane_id for item in selected))} lane(s)."
            if should_start
            else "No materializable backlog items passed the formal cycle planner."
        )
        return CyclePlanningDecision(
            should_start=should_start,
            reason=reason,
            cycle_kind=cycle_kind,
            selected_backlog_item_ids=[item.id for item in selected],
            selected_lane_ids=_unique_strings(
                [item.lane_id for item in selected if item.lane_id is not None],
            ),
            max_assignment_count=len(selected),
            affected_relation_ids=relation_projection["relation_ids"],
            affected_relation_kinds=relation_projection["relation_kinds"],
            summary=summary,
            planning_policy=list(constraints.planning_policy or []),
            planning_shell=self._planning_shell(record, cycle_kind),
            metadata=self._decision_metadata(
                record=record,
                open_backlog=open_backlog,
                pending_reports=pending_reports,
                constraints=constraints,
                lane_budget_outcomes=lane_budget_outcomes,
                lane_budget_mode="constrained" if lane_budgets else None,
                force_scoped_backlog=force_scoped_backlog,
                cycle_kind_reason=cycle_kind_reason,
            ),
        )

    def _candidate_backlog(
        self,
        *,
        open_backlog: Sequence[BacklogItemRecord],
        constraints: PlanningStrategyConstraints,
    ) -> list[BacklogItemRecord]:
        paused_lanes = self._paused_lanes(constraints)
        lane_weights = dict(constraints.lane_weights or {})
        candidates = [
            item
            for item in open_backlog
            if item.lane_id is None or item.lane_id not in paused_lanes
        ]
        return sorted(
            candidates,
            key=lambda item: self._item_sort_key(
                item=item,
                constraints=constraints,
                lane_weights=lane_weights,
            ),
            reverse=True,
        )

    def _decision_metadata(
        self,
        *,
        record: IndustryInstanceRecord,
        open_backlog: Sequence[BacklogItemRecord],
        pending_reports: Sequence[AgentReportRecord],
        constraints: PlanningStrategyConstraints,
        lane_budget_outcomes: dict[str, dict[str, object]],
        lane_budget_mode: str | None,
        force_scoped_backlog: bool,
        cycle_kind_reason: str | None,
    ) -> dict[str, object]:
        strategic_uncertainty_ids = [
            entry.uncertainty_id
            for entry in list(constraints.strategic_uncertainties or [])
            if entry.uncertainty_id
        ]
        trigger_families = [
            entry.trigger_family
            for entry in list(constraints.strategy_trigger_rules or [])
            if entry.trigger_family
        ]
        metadata: dict[str, object] = {
            "industry_instance_id": record.instance_id,
            "pending_report_count": len(list(pending_reports)),
            "open_backlog_count": len(list(open_backlog)),
            "paused_lane_ids": list(constraints.paused_lane_ids or []),
            "graph_focus_entities": list(constraints.graph_focus_entities or []),
            "graph_focus_opinions": list(constraints.graph_focus_opinions or []),
            "force_scoped_backlog": force_scoped_backlog,
            "strategic_uncertainty_ids": strategic_uncertainty_ids,
            "trigger_families": trigger_families,
            "force_scoped_backlog": force_scoped_backlog,
            "strategic_uncertainty_ids": strategic_uncertainty_ids,
            "trigger_families": trigger_families,
        }
        if cycle_kind_reason is not None:
            metadata["cycle_kind_reason"] = cycle_kind_reason
        if lane_budget_mode is not None:
            metadata["lane_budget_mode"] = lane_budget_mode
        if lane_budget_outcomes:
            metadata["lane_budget_outcomes"] = lane_budget_outcomes
        return metadata

    def _merge_task_subgraph_into_constraints(
        self,
        *,
        constraints: PlanningStrategyConstraints,
        task_subgraph: object | None,
    ) -> PlanningStrategyConstraints:
        projection = project_task_subgraph_to_planning_focus(task_subgraph)
        if not projection:
            return constraints
        relation_evidence = list(constraints.graph_relation_evidence or [])
        seen_relation_ids = {
            _string(entry.get("relation_id"))
            for entry in relation_evidence
            if isinstance(entry, dict)
        }
        for entry in list(projection.get("relation_evidence") or []):
            if not isinstance(entry, dict):
                continue
            relation_id = _string(entry.get("relation_id"))
            if relation_id is not None and relation_id in seen_relation_ids:
                continue
            if relation_id is not None:
                seen_relation_ids.add(relation_id)
            relation_evidence.append(dict(entry))
        for path_group in (
            "support_paths",
            "contradiction_paths",
            "dependency_paths",
            "blocker_paths",
            "recovery_paths",
        ):
            for entry in list(projection.get(path_group) or []):
                if not isinstance(entry, dict):
                    continue
                relation_id = _string((entry.get("relation_ids") or [None])[0])
                if relation_id is not None and relation_id in seen_relation_ids:
                    continue
                if relation_id is not None:
                    seen_relation_ids.add(relation_id)
                relation_evidence.append(
                    {
                        "relation_id": relation_id,
                        "relation_kind": _string((entry.get("relation_kinds") or [None])[0]),
                        "summary": _string(entry.get("summary")),
                        "source_refs": list(entry.get("source_refs") or []),
                        "source_node_id": _string((entry.get("node_ids") or [None])[0]),
                        "target_node_id": _string((entry.get("node_ids") or [None, None])[1]),
                        "path_type": _string(entry.get("path_type")),
                        "path_score": _number(entry.get("score")),
                    },
                )
        return constraints.model_copy(
            update={
                "current_focuses": _unique_strings(
                    constraints.current_focuses,
                    projection.get("constraint_refs"),
                ),
                "graph_focus_entities": _unique_strings(
                    constraints.graph_focus_entities,
                    projection.get("top_entities"),
                ),
                "graph_focus_opinions": _unique_strings(
                    constraints.graph_focus_opinions,
                    projection.get("top_opinions"),
                ),
                "graph_focus_relations": _unique_strings(
                    constraints.graph_focus_relations,
                    projection.get("top_relations"),
                ),
                "graph_relation_evidence": relation_evidence,
            },
        )

    def _resolve_cycle_kind(
        self,
        *,
        constraints: PlanningStrategyConstraints,
    ) -> tuple[str, str]:
        strategic_uncertainties = list(constraints.strategic_uncertainties or [])
        trigger_rules = list(constraints.strategy_trigger_rules or [])
        trigger_families = {
            rule.trigger_family
            for rule in trigger_rules
            if rule.trigger_family
        }
        if self._has_event_cycle_signal(
            strategic_uncertainties=strategic_uncertainties,
            trigger_families=trigger_families,
        ):
            if "confidence_collapse" in trigger_families:
                return ("event", "confidence-collapse")
            if "repeated_blocker" in trigger_families:
                return ("event", "repeated-blocker")
            return ("event", "high-impact-uncertainty")
        if self._has_weekly_cycle_signal(
            strategic_uncertainties=strategic_uncertainties,
            trigger_rules=trigger_rules,
        ):
            return ("weekly", "strategic-review-window")
        return ("daily", "default-daily")

    def _has_weekly_cycle_signal(
        self,
        *,
        strategic_uncertainties: Sequence[object],
        trigger_rules: Sequence[StrategyTriggerRule],
    ) -> bool:
        for entry in strategic_uncertainties:
            review_by_cycle = (_string(getattr(entry, "review_by_cycle", None)) or "").casefold()
            if "weekly" in review_by_cycle:
                return True
        for rule in trigger_rules:
            decision_hint = _string(rule.decision_hint)
            if decision_hint == "strategy_review_required":
                return True
        return False

    def _has_event_cycle_signal(
        self,
        *,
        strategic_uncertainties: Sequence[object],
        trigger_families: set[str],
    ) -> bool:
        if not trigger_families.intersection({"confidence_collapse", "repeated_blocker"}):
            return False
        for entry in strategic_uncertainties:
            impact_level = (_string(getattr(entry, "impact_level", None)) or "").casefold()
            current_confidence = _number(getattr(entry, "current_confidence", None))
            if impact_level == "high" and current_confidence <= 0.35:
                return True
        return False

    def _paused_lanes(self, constraints: PlanningStrategyConstraints) -> set[str]:
        return {
            lane_id
            for lane_id in list(constraints.paused_lane_ids or [])
            if lane_id
        }

    def _item_sort_key(
        self,
        *,
        item: BacklogItemRecord,
        constraints: PlanningStrategyConstraints,
        lane_weights: dict[str, float],
    ) -> tuple[object, ...]:
        return (
            _backlog_followup_overdue_score(item),
            1 if _backlog_is_report_followup(item) else 0,
            int(item.priority or 0),
            self._path_ordering_score(item=item, constraints=constraints),
            self._relation_focus_score(item=item, constraints=constraints),
            self._graph_focus_score(item=item, constraints=constraints),
            self._strategy_priority_score(item=item, constraints=constraints),
            float(lane_weights.get(item.lane_id or "", 0.0)),
            _sort_timestamp(item.updated_at or item.created_at),
        )

    def _lane_budget_map(
        self,
        constraints: PlanningStrategyConstraints,
    ) -> dict[str, dict[str, object]]:
        entries = list(constraints.lane_budgets or [])
        budgets: dict[str, dict[str, object]] = {}
        for entry in entries:
            lane_id = _string(entry.lane_id)
            if lane_id is None:
                continue
            budget_window = entry.budget_window
            current_share = self._budget_current_share(entry)
            completed_cycles = entry.completed_cycles_or_default()
            consumed_cycles = entry.consumed_cycles_or_default()
            underinvested_cycles = entry.underinvested_cycle_count()
            target_share = max(_number(entry.target_share), 0.0)
            min_share = max(_number(entry.min_share), 0.0)
            max_share = max(_number(entry.max_share), 0.0)
            target_cycle_count = 0
            if completed_cycles > 0 and target_share > 0.0:
                target_cycle_count = max(1, int(round(target_share * completed_cycles)))
            multi_cycle_gap = max(target_cycle_count - consumed_cycles, underinvested_cycles, 0)
            force_include_reason = _string(entry.force_include_reason)
            if force_include_reason is None and min_share > 0.0 and current_share < min_share:
                force_include_reason = "lane-below-min-share"
            if force_include_reason is None and self._is_multi_cycle_underinvested(
                budget=entry,
                current_share=current_share,
                target_share=target_share,
            ):
                force_include_reason = "multi-cycle-underinvestment"
            budgets[lane_id] = {
                "lane_id": lane_id,
                "budget_window": budget_window,
                "current_share": current_share,
                "target_share": target_share,
                "min_share": min_share,
                "max_share": max_share,
                "review_pressure": _string(entry.review_pressure) or "",
                "defer_reason": _string(entry.defer_reason),
                "force_include_reason": force_include_reason,
                "completed_cycles": completed_cycles,
                "consumed_cycles": consumed_cycles,
                "underinvested_cycles": underinvested_cycles,
                "target_cycle_count": target_cycle_count,
                "multi_cycle_gap": multi_cycle_gap,
            }
        return budgets

    def _budget_current_share(self, budget: PlanningLaneBudget) -> float:
        current_share = budget.current_share_or_default()
        if current_share > 0.0:
            return current_share
        completed_cycles = budget.completed_cycles_or_default()
        allocated_cycles = budget.consumed_cycles_or_default()
        if completed_cycles > 0 and allocated_cycles >= 0:
            return allocated_cycles / completed_cycles
        return 0.0

    def _budget_constrained_backlog(
        self,
        *,
        open_backlog: Sequence[BacklogItemRecord],
        constraints: PlanningStrategyConstraints,
        selection_limit: int,
        lane_budgets: dict[str, dict[str, object]],
    ) -> tuple[list[BacklogItemRecord], dict[str, dict[str, object]]]:
        paused_lanes = self._paused_lanes(constraints)
        lane_weights = dict(constraints.lane_weights or {})
        grouped: dict[str, list[BacklogItemRecord]] = {}
        paused: dict[str, list[BacklogItemRecord]] = {}

        for item in open_backlog:
            lane_key = _lane_metadata_key(item.lane_id)
            if item.lane_id is not None and item.lane_id in paused_lanes:
                paused.setdefault(lane_key, []).append(item)
                continue
            grouped.setdefault(lane_key, []).append(item)

        lane_outcomes: dict[str, dict[str, object]] = {}
        for lane_key, items in paused.items():
            lane_id = items[0].lane_id
            lane_outcomes[lane_key] = self._lane_outcome(
                lane_id=lane_id,
                budget=lane_budgets.get(lane_id or ""),
                items=items,
                outcome="suppressed",
                reason="paused-lane",
            )

        for items in grouped.values():
            items.sort(
                key=lambda item: self._item_sort_key(
                    item=item,
                    constraints=constraints,
                    lane_weights=lane_weights,
                ),
                reverse=True,
            )

        cohorts: dict[str, list[dict[str, object]]] = {
            "force-included": [],
            "selected": [],
            "deferred": [],
        }
        for lane_key, items in grouped.items():
            lane_id = items[0].lane_id
            budget = lane_budgets.get(lane_id or "")
            current_share = _number((budget or {}).get("current_share"))
            target_share = _number((budget or {}).get("target_share"))
            max_share = _number((budget or {}).get("max_share"))
            overdue_reason = self._lane_force_include_reason_for_items(items)
            force_reason = overdue_reason or _string((budget or {}).get("force_include_reason"))
            defer_reason = _string((budget or {}).get("defer_reason"))
            budget_for_lane = dict(budget or {})
            if force_reason is not None:
                budget_for_lane["force_include_reason"] = force_reason
            if budget is not None and force_reason is None and max_share > 0.0 and current_share >= max_share:
                lane_outcomes[lane_key] = self._lane_outcome(
                    lane_id=lane_id,
                    budget=budget_for_lane,
                    items=items,
                    outcome="suppressed",
                    reason=defer_reason or "lane-max-share-reached",
                )
                continue
            status = "selected"
            if force_reason is not None:
                status = "force-included"
            elif (
                budget is not None
                and defer_reason is not None
                and current_share >= target_share
                and overdue_reason is None
            ):
                status = "deferred"
            cohorts[status].append(
                {
                    "lane_id": lane_id,
                    "lane_key": lane_key,
                    "budget": budget_for_lane,
                    "items": list(items),
                    "available_items": list(items),
                    "selected_backlog_item_ids": [],
                },
            )

        selected: list[BacklogItemRecord] = []
        for status in ("force-included", "selected", "deferred"):
            while len(selected) < selection_limit:
                candidates = [
                    entry
                    for entry in cohorts[status]
                    if entry["items"]
                    and self._lane_can_accept_another_selection(
                        budget=entry["budget"] if isinstance(entry["budget"], dict) else None,
                        planned_assignment_count=len(list(entry["selected_backlog_item_ids"])),
                        selection_limit=selection_limit,
                    )
                ]
                if not candidates:
                    break
                entry = max(
                    candidates,
                    key=lambda candidate: self._lane_entry_rank(
                        entry=candidate,
                        constraints=constraints,
                        lane_weights=lane_weights,
                        selection_limit=selection_limit,
                    ),
                )
                items = list(entry["items"])
                if not items:
                    break
                item = items[0]
                selected.append(item)
                entry["items"] = items[1:]
                entry["selected_backlog_item_ids"] = [
                    *list(entry["selected_backlog_item_ids"]),
                    item.id,
                ]

        selected_by_lane: dict[str, list[str]] = {}
        for item in selected:
            selected_by_lane.setdefault(_lane_metadata_key(item.lane_id), []).append(item.id)

        for status, entries in cohorts.items():
            for entry in entries:
                lane_key = str(entry["lane_key"])
                lane_id = entry["lane_id"] if isinstance(entry["lane_id"], str) else None
                budget = entry["budget"] if isinstance(entry["budget"], dict) else None
                selected_ids = selected_by_lane.get(lane_key, [])
                if selected_ids:
                    outcome = "force-included" if status == "force-included" else "selected"
                    if status == "force-included":
                        reason = _string((budget or {}).get("force_include_reason"))
                    elif entry["items"] and not self._lane_can_accept_another_selection(
                        budget=budget,
                        planned_assignment_count=len(selected_ids),
                        selection_limit=selection_limit,
                    ):
                        reason = _string((budget or {}).get("defer_reason")) or "lane-budget-consumed"
                    else:
                        reason = None
                elif status == "deferred" or _string((budget or {}).get("defer_reason")) is not None:
                    outcome = "deferred"
                    reason = _string((budget or {}).get("defer_reason")) or "deferred-by-lane-budget"
                else:
                    outcome = "not-selected"
                    reason = "selection-limit-reached"
                lane_outcomes[lane_key] = self._lane_outcome(
                    lane_id=lane_id,
                    budget=budget,
                    items=list(entry["available_items"]),
                    outcome=outcome,
                    reason=reason,
                    selected_backlog_item_ids=selected_ids,
                    selection_limit=selection_limit,
                )
        return selected, lane_outcomes

    def _lane_entry_rank(
        self,
        *,
        entry: dict[str, object],
        constraints: PlanningStrategyConstraints,
        lane_weights: dict[str, float],
        selection_limit: int,
    ) -> tuple[object, ...]:
        items = list(entry.get("items") or [])
        lane_id = _string(entry.get("lane_id"))
        budget = entry.get("budget") if isinstance(entry.get("budget"), dict) else None
        current_planned = len(list(entry.get("selected_backlog_item_ids") or []))
        projected_share = self._projected_lane_share(
            budget=budget,
            planned_assignment_count=current_planned,
            selection_limit=selection_limit,
        )
        target_share = _number((budget or {}).get("target_share"))
        return (
            max(
                (_backlog_followup_overdue_score(item) for item in items[:1]),
                default=0.0,
            ),
            1 if items and any(_backlog_is_report_followup(item) for item in items[:1]) else 0,
            _number((budget or {}).get("multi_cycle_gap")),
            _number((budget or {}).get("underinvested_cycles")),
            max(target_share - projected_share, 0.0),
            self._review_pressure_score((budget or {}).get("review_pressure")),
            self._item_sort_key(
                item=items[0],
                constraints=constraints,
                lane_weights=lane_weights,
            )
            if items
            else (0, 0, 0, 0, 0, 0.0),
            float(lane_weights.get(lane_id or "", 0.0)),
        )

    def _lane_can_accept_another_selection(
        self,
        *,
        budget: dict[str, object] | None,
        planned_assignment_count: int,
        selection_limit: int,
    ) -> bool:
        if selection_limit <= 1:
            return True
        selection_cap = self._lane_selection_cap(
            budget=budget,
            selection_limit=selection_limit,
        )
        if selection_cap is not None and planned_assignment_count >= selection_cap:
            return False
        max_share = _number((budget or {}).get("max_share"))
        if max_share <= 0.0:
            return True
        projected_share = self._projected_lane_share(
            budget=budget,
            planned_assignment_count=planned_assignment_count + 1,
            selection_limit=selection_limit,
        )
        return projected_share <= max_share

    def _projected_lane_share(
        self,
        *,
        budget: dict[str, object] | None,
        planned_assignment_count: int,
        selection_limit: int,
    ) -> float:
        current_share = _number((budget or {}).get("current_share"))
        if selection_limit <= 0 or planned_assignment_count <= 0:
            return current_share
        planned_share = planned_assignment_count / max(selection_limit, 1)
        return max(current_share, planned_share)

    def _lane_selection_cap(
        self,
        *,
        budget: dict[str, object] | None,
        selection_limit: int,
    ) -> int | None:
        max_share = _number((budget or {}).get("max_share"))
        if max_share <= 0.0:
            return None
        current_share = _number((budget or {}).get("current_share"))
        remaining_headroom = max(max_share - current_share, 0.0)
        if remaining_headroom <= 0.0:
            return 0
        if selection_limit <= 1:
            return 1
        return max(1, math.ceil(remaining_headroom * selection_limit))

    def _lane_outcome(
        self,
        *,
        lane_id: str | None,
        budget: dict[str, object] | None,
        items: Sequence[BacklogItemRecord],
        outcome: str,
        reason: str | None,
        selected_backlog_item_ids: Sequence[str] | None = None,
        selection_limit: int | None = None,
    ) -> dict[str, object]:
        selected_ids = list(selected_backlog_item_ids or [])
        effective_selection_limit = selection_limit or 0
        selection_cap = self._lane_selection_cap(
            budget=budget,
            selection_limit=effective_selection_limit,
        )
        projected_share = self._projected_lane_share(
            budget=budget,
            planned_assignment_count=len(selected_ids),
            selection_limit=effective_selection_limit,
        )
        max_share = _number((budget or {}).get("max_share"))
        if selection_cap is None:
            remaining_headroom = max(max_share - projected_share, 0.0) if max_share > 0.0 else None
        else:
            remaining_slots = max(selection_cap - len(selected_ids), 0)
            remaining_headroom = remaining_slots / max(effective_selection_limit, 1)
        return {
            "lane_id": lane_id,
            "outcome": outcome,
            "reason": reason,
            "backlog_item_ids": [item.id for item in items],
            "selected_backlog_item_ids": selected_ids,
            "budget_window": (budget or {}).get("budget_window"),
            "current_share": _number((budget or {}).get("current_share")),
            "projected_share": projected_share,
            "planned_assignment_count": len(selected_ids),
            "target_share": _number((budget or {}).get("target_share")),
            "min_share": _number((budget or {}).get("min_share")),
            "max_share": _number((budget or {}).get("max_share")),
            "remaining_headroom": remaining_headroom,
            "completed_cycles": int(_number((budget or {}).get("completed_cycles"))),
            "consumed_cycles": int(_number((budget or {}).get("consumed_cycles"))),
            "underinvested_cycles": int(_number((budget or {}).get("underinvested_cycles"))),
            "target_cycle_count": int(_number((budget or {}).get("target_cycle_count"))),
            "multi_cycle_gap": int(_number((budget or {}).get("multi_cycle_gap"))),
            "review_pressure": (budget or {}).get("review_pressure"),
            "defer_reason": (budget or {}).get("defer_reason"),
            "force_include_reason": (budget or {}).get("force_include_reason"),
        }

    def _review_pressure_score(self, pressure: object | None) -> int:
        text = str(pressure or "").strip().lower()
        if any(token in text for token in ("critical", "urgent", "high", "catch")):
            return 3
        if any(token in text for token in ("steady", "normal", "medium")):
            return 2
        if any(token in text for token in ("throttle", "hold", "defer", "low")):
            return 1
        return 0

    def _graph_focus_score(
        self,
        *,
        item: BacklogItemRecord,
        constraints: PlanningStrategyConstraints,
    ) -> int:
        focus_tokens = set(
            _tokenize(
                " ".join(
                    _unique_strings(
                        constraints.current_focuses,
                        constraints.graph_focus_entities,
                        constraints.graph_focus_opinions,
                    ),
                ),
            ),
        )
        if not focus_tokens:
            return 0
        metadata = dict(item.metadata or {})
        item_tokens = set(
            _tokenize(
                " ".join(
                    [
                        item.id,
                        item.title,
                        item.summary,
                        *[str(value) for value in metadata.values() if value is not None],
                    ],
                ),
            ),
        )
        return len(item_tokens & focus_tokens)

    def _relation_focus_score(
        self,
        *,
        item: BacklogItemRecord,
        constraints: PlanningStrategyConstraints,
    ) -> int:
        return int(
            self._relation_matches_for_item(
                item=item,
                constraints=constraints,
            )["score"],
        )

    def _path_ordering_score(
        self,
        *,
        item: BacklogItemRecord,
        constraints: PlanningStrategyConstraints,
    ) -> int:
        item_tokens = self._item_tokens(item)
        if not item_tokens:
            return 0
        score = 0
        for entry in list(getattr(constraints, "graph_relation_evidence", []) or []):
            if not isinstance(entry, dict):
                continue
            path_type = _string(entry.get("path_type"))
            if path_type is None:
                continue
            path_tokens = set(
                _tokenize(
                    " ".join(
                        _unique_strings(
                            entry.get("summary"),
                            entry.get("relation_kind"),
                            entry.get("source_node_id"),
                            entry.get("target_node_id"),
                            entry.get("source_refs"),
                        ),
                    ),
                ),
            )
            overlap = item_tokens & path_tokens
            if not overlap:
                continue
            if path_type == "dependency":
                score += 12 + len(overlap)
                if item_tokens.intersection({"refresh", "verify", "evidence", "dependency"}):
                    score += 10
            elif path_type == "contradiction":
                score += 8 + len(overlap)
            elif path_type == "recovery":
                score += 6 + len(overlap)
            elif path_type == "support":
                score += 4 + len(overlap)
            elif path_type == "blocker":
                if item_tokens.intersection({"refresh", "verify", "resolve", "unblock", "clear"}):
                    score += 10 + len(overlap)
                elif item_tokens.intersection({"publish", "release", "launch", "ship", "deploy"}):
                    score -= 12
        return score

    def _relation_focus_projection(
        self,
        *,
        items: Sequence[BacklogItemRecord],
        constraints: PlanningStrategyConstraints,
    ) -> dict[str, list[str]]:
        relation_ids: list[str] = []
        relation_kinds: list[str] = []
        seen_relation_ids: set[str] = set()
        seen_relation_kinds: set[str] = set()
        for item in items:
            projection = self._relation_matches_for_item(
                item=item,
                constraints=constraints,
            )
            for relation_id in projection["relation_ids"]:
                if relation_id in seen_relation_ids:
                    continue
                seen_relation_ids.add(relation_id)
                relation_ids.append(relation_id)
            for relation_kind in projection["relation_kinds"]:
                if relation_kind in seen_relation_kinds:
                    continue
                seen_relation_kinds.add(relation_kind)
                relation_kinds.append(relation_kind)
        return {
            "relation_ids": relation_ids,
            "relation_kinds": relation_kinds,
        }

    def _relation_matches_for_item(
        self,
        *,
        item: BacklogItemRecord,
        constraints: PlanningStrategyConstraints,
    ) -> dict[str, object]:
        item_tokens = self._item_tokens(item)
        if not item_tokens:
            return {"score": 0, "relation_ids": [], "relation_kinds": []}
        focus_tokens = set(
            _tokenize(
                " ".join(
                    _unique_strings(
                        getattr(constraints, "graph_focus_relations", []),
                    ),
                ),
            ),
        )
        score = len(item_tokens & focus_tokens)
        relation_ids: list[str] = []
        relation_kinds: list[str] = []
        for entry in list(getattr(constraints, "graph_relation_evidence", []) or []):
            if not isinstance(entry, dict):
                continue
            relation_tokens = set(
                _tokenize(
                    " ".join(
                        _unique_strings(
                            entry.get("summary"),
                            entry.get("relation_kind"),
                            entry.get("source_node_id"),
                            entry.get("target_node_id"),
                            entry.get("source_refs"),
                        ),
                    ),
                ),
            )
            overlap = item_tokens & relation_tokens
            if not overlap:
                continue
            path_type = _string(entry.get("path_type"))
            path_score = _number(entry.get("path_score"))
            bonus = len(overlap)
            if path_type == "dependency":
                bonus += 8
            elif path_type == "contradiction":
                bonus += 3
            elif path_type == "support":
                bonus += 2
            elif path_type == "recovery":
                bonus += 2
            elif path_type == "blocker":
                if item_tokens.intersection({"resolve", "review", "refresh", "verify", "clarify", "unblock"}):
                    bonus += 5
                if item_tokens.intersection({"publish", "release", "launch", "ship", "deploy"}):
                    bonus -= 6
            score += bonus + int(path_score // 4)
            relation_id = _string(entry.get("relation_id"))
            if relation_id is not None and relation_id not in relation_ids:
                relation_ids.append(relation_id)
            relation_kind = _string(entry.get("relation_kind"))
            if relation_kind is not None and relation_kind not in relation_kinds:
                relation_kinds.append(relation_kind)
        return {
            "score": score,
            "relation_ids": relation_ids,
            "relation_kinds": relation_kinds,
        }

    def _item_tokens(self, item: BacklogItemRecord) -> set[str]:
        metadata = dict(item.metadata or {})
        return set(
            _tokenize(
                " ".join(
                    [
                        item.id,
                        item.title,
                        item.summary,
                        *[str(value) for value in metadata.values() if value is not None],
                    ],
                ),
            ),
        )

    def _strategy_priority_score(
        self,
        *,
        item: BacklogItemRecord,
        constraints: PlanningStrategyConstraints,
    ) -> int:
        priority_order = [_string(value) for value in list(constraints.priority_order or [])]
        priority_order = [value for value in priority_order if value is not None]
        if not priority_order:
            return 0
        metadata = dict(item.metadata or {})
        item_text = " ".join(
            [
                item.id,
                item.lane_id or "",
                item.title,
                item.summary,
                *[str(value) for value in metadata.values() if value is not None],
            ],
        ).casefold()
        item_tokens = set(_tokenize(item_text))
        best_score = 0
        total = len(priority_order)
        for index, entry in enumerate(priority_order):
            entry_text = entry.casefold()
            if not entry_text:
                continue
            entry_tokens = set(_tokenize(entry_text))
            if entry_text in item_text or (entry_tokens and item_tokens.intersection(entry_tokens)):
                best_score = max(best_score, total - index)
        return best_score

    def _is_multi_cycle_underinvested(
        self,
        *,
        budget: PlanningLaneBudget,
        current_share: float,
        target_share: float,
    ) -> bool:
        if current_share >= target_share:
            return False
        return budget.underinvested_cycle_count() >= 2

    def _lane_force_include_reason_for_items(
        self,
        items: Sequence[BacklogItemRecord],
    ) -> str | None:
        if any(_backlog_followup_overdue_score(item) > 0.0 for item in items):
            return "overdue-followup"
        return None

    def _selection_limit(
        self,
        constraints: PlanningStrategyConstraints,
    ) -> int:
        policies = {policy for policy in list(constraints.planning_policy or []) if policy}
        if {"single-assignment-cycle", "single-threaded-cycle"} & policies:
            return 1
        if {"narrow-focus", "limit-cycle-width"} & policies:
            return 2
        if {"allow-broad-cycle", "wide-cycle"} & policies:
            return 5
        return 3
