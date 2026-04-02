# -*- coding: utf-8 -*-
"""Cycle planner that compiles runtime facts into a formal cycle launch decision."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from ...state import AgentReportRecord, BacklogItemRecord, IndustryInstanceRecord, OperatingCycleRecord
from .models import CyclePlanningDecision, PlanningStrategyConstraints


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def _item_sort_key(
    item: BacklogItemRecord,
    lane_weights: dict[str, float],
) -> tuple[int, int, float, float]:
    return (
        1 if _backlog_is_report_followup(item) else 0,
        int(item.priority or 0),
        float(lane_weights.get(item.lane_id or "", 0.0)),
        _sort_timestamp(item.updated_at or item.created_at),
    )


def _budget_share(budget: object) -> float:
    current_share = getattr(budget, "current_share", None)
    if isinstance(current_share, (int, float)):
        return float(current_share)
    completed_cycles = int(getattr(budget, "completed_cycles", 0) or 0)
    consumed_cycles = int(getattr(budget, "consumed_cycles", 0) or 0)
    if completed_cycles > 0:
        return float(consumed_cycles) / float(completed_cycles)
    return 0.0


def _lane_budget_status(budget: object) -> tuple[str, str | None]:
    current_share = _budget_share(budget)
    min_share = float(getattr(budget, "min_share", 0.0) or 0.0)
    max_share = float(getattr(budget, "max_share", 1.0) or 1.0)
    target_share = float(getattr(budget, "target_share", 0.0) or 0.0)
    defer_reason = _string(getattr(budget, "defer_reason", None))
    force_include_reason = _string(getattr(budget, "force_include_reason", None))
    if current_share > max_share:
        if defer_reason is not None:
            return "deferred", defer_reason
        return "suppressed", "lane-budget-cap-exhausted"
    if current_share >= target_share and defer_reason is not None:
        return "deferred", defer_reason
    if current_share < min_share and force_include_reason is not None:
        return "force-included", force_include_reason
    return "eligible", None


class CyclePlanningCompiler:
    """Pure planner for whether the next operating cycle should start."""

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
    ) -> CyclePlanningDecision:
        constraints = strategy_constraints or PlanningStrategyConstraints()
        selection_limit = self._selection_limit(constraints)
        candidates, lane_budget_outcomes = self._candidate_backlog(
            open_backlog=open_backlog,
            constraints=constraints,
            force_scoped_backlog=force and force_scoped_backlog,
        )
        selected = list(candidates[:selection_limit])

        if force:
            should_start = bool(selected or pending_reports)
            return CyclePlanningDecision(
                should_start=should_start,
                reason="forced" if should_start else "forced-empty",
                cycle_kind=(
                    current_cycle.cycle_kind
                    if current_cycle is not None
                    else "daily"
                ),
                selected_backlog_item_ids=[item.id for item in selected],
                selected_lane_ids=_unique_strings(
                    [item.lane_id for item in selected if item.lane_id is not None],
                ),
                max_assignment_count=len(selected),
                summary=(
                    "Force-started cycle materialization from scoped backlog."
                    if should_start
                    else "Force requested a cycle launch but no materializable backlog or pending report remained."
                ),
                planning_policy=list(constraints.planning_policy or []),
                metadata={
                    "industry_instance_id": record.instance_id,
                    "pending_report_count": len(list(pending_reports)),
                    "open_backlog_count": len(list(open_backlog)),
                    "lane_budget_outcomes": lane_budget_outcomes,
                    "paused_lane_ids": list(constraints.paused_lane_ids or []),
                    "force_scoped_backlog": force_scoped_backlog,
                },
            )

        if current_cycle is not None and current_cycle.status not in {"completed", "cancelled"}:
            return CyclePlanningDecision(
                should_start=False,
                reason="cycle-inflight",
                cycle_kind=current_cycle.cycle_kind,
                max_assignment_count=0,
                summary="A formal cycle is already active, so planner launch is held.",
                planning_policy=list(constraints.planning_policy or []),
                metadata={"industry_instance_id": record.instance_id},
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

        summary = (
            f"Plan a daily cycle for {len(selected)} backlog item(s) across "
            f"{len(_unique_strings(item.lane_id for item in selected))} lane(s)."
            if should_start
            else "No materializable backlog items passed the formal cycle planner."
        )
        return CyclePlanningDecision(
            should_start=should_start,
            reason=reason,
            cycle_kind="daily",
            selected_backlog_item_ids=[item.id for item in selected],
            selected_lane_ids=_unique_strings(
                [item.lane_id for item in selected if item.lane_id is not None],
            ),
            max_assignment_count=len(selected),
            summary=summary,
            planning_policy=list(constraints.planning_policy or []),
            metadata={
                "industry_instance_id": record.instance_id,
                "pending_report_count": len(list(pending_reports)),
                "open_backlog_count": len(list(open_backlog)),
                "lane_budget_outcomes": lane_budget_outcomes,
                "paused_lane_ids": list(constraints.paused_lane_ids or []),
                "force_scoped_backlog": force_scoped_backlog,
            },
        )

    def _candidate_backlog(
        self,
        *,
        open_backlog: Sequence[BacklogItemRecord],
        constraints: PlanningStrategyConstraints,
        force_scoped_backlog: bool = False,
    ) -> tuple[list[BacklogItemRecord], list[dict[str, Any]]]:
        paused_lanes = {
            lane_id
            for lane_id in list(constraints.paused_lane_ids or [])
            if lane_id
        }
        lane_weights = dict(constraints.lane_weights or {})
        candidates = [
            item
            for item in open_backlog
            if item.lane_id is None or item.lane_id not in paused_lanes
        ]
        budget_by_lane = {
            getattr(budget, "lane_id", None): budget
            for budget in list(getattr(constraints, "lane_budgets", []) or [])
            if getattr(budget, "lane_id", None)
        }
        grouped: dict[str | None, list[BacklogItemRecord]] = {}
        for item in candidates:
            grouped.setdefault(item.lane_id, []).append(item)

        ordered: list[BacklogItemRecord] = []
        lane_budget_outcomes: list[dict[str, Any]] = []
        for lane_id, items in grouped.items():
            lane_items = sorted(
                items,
                key=lambda item: _item_sort_key(item, lane_weights),
                reverse=True,
            )
            budget = budget_by_lane.get(lane_id)
            if budget is None:
                ordered.extend(lane_items)
                continue
            status, reason = _lane_budget_status(budget)
            selected_items: list[BacklogItemRecord] = []
            if status == "force-included":
                selected_items = lane_items[:1]
                ordered.extend(selected_items)
                ordered.extend(lane_items[1:])
            elif status == "eligible":
                ordered.extend(lane_items)
            elif force_scoped_backlog and lane_items:
                status = "force-included"
                reason = reason or "force-scoped-backlog-override"
                selected_items = list(lane_items)
                ordered.extend(lane_items)
            lane_budget_outcomes.append(
                {
                    "lane_id": lane_id,
                    "status": status,
                    "reason": reason,
                    "budget_window": getattr(budget, "budget_window", ""),
                    "target_share": float(getattr(budget, "target_share", 0.0) or 0.0),
                    "min_share": float(getattr(budget, "min_share", 0.0) or 0.0),
                    "max_share": float(getattr(budget, "max_share", 1.0) or 1.0),
                    "current_share": _budget_share(budget),
                    "selected_item_ids": [item.id for item in selected_items],
                    "candidate_item_ids": [item.id for item in lane_items],
                    "review_pressure": _string(getattr(budget, "review_pressure", None)),
                },
            )
        ordered = sorted(
            ordered,
            key=lambda item: _item_sort_key(item, lane_weights),
            reverse=True,
        )
        return ordered, lane_budget_outcomes

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
