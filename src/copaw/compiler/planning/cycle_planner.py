# -*- coding: utf-8 -*-
"""Cycle planner that compiles runtime facts into a formal cycle launch decision."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

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
        strategy_constraints: PlanningStrategyConstraints | None = None,
    ) -> CyclePlanningDecision:
        constraints = strategy_constraints or PlanningStrategyConstraints()
        selection_limit = self._selection_limit(constraints)
        candidates = self._candidate_backlog(
            open_backlog=open_backlog,
            constraints=constraints,
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
                    "paused_lane_ids": list(constraints.paused_lane_ids or []),
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
                "paused_lane_ids": list(constraints.paused_lane_ids or []),
            },
        )

    def _candidate_backlog(
        self,
        *,
        open_backlog: Sequence[BacklogItemRecord],
        constraints: PlanningStrategyConstraints,
    ) -> list[BacklogItemRecord]:
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
        return sorted(
            candidates,
            key=lambda item: (
                1 if _backlog_is_report_followup(item) else 0,
                int(item.priority or 0),
                float(lane_weights.get(item.lane_id or "", 0.0)),
                _sort_timestamp(item.updated_at or item.created_at),
            ),
            reverse=True,
        )

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
