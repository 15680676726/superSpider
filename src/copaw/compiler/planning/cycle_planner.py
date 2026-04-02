# -*- coding: utf-8 -*-
"""Cycle planner that compiles runtime facts into a formal cycle launch decision."""
from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime, timezone

from ...state import AgentReportRecord, BacklogItemRecord, IndustryInstanceRecord, OperatingCycleRecord
from .models import CyclePlanningDecision, PlanningStrategyConstraints

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


def _read_field(value: object, field: str) -> object | None:
    if isinstance(value, dict):
        return value.get(field)
    return getattr(value, field, None)


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
                metadata=self._decision_metadata(
                    record=record,
                    open_backlog=open_backlog,
                    pending_reports=pending_reports,
                    constraints=constraints,
                    lane_budget_outcomes=lane_budget_outcomes,
                    lane_budget_mode="force-override" if lane_budgets else None,
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
                metadata=self._decision_metadata(
                    record=record,
                    open_backlog=open_backlog,
                    pending_reports=pending_reports,
                    constraints=constraints,
                    lane_budget_outcomes=lane_budget_outcomes,
                    lane_budget_mode="constrained" if lane_budgets else None,
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
            metadata=self._decision_metadata(
                record=record,
                open_backlog=open_backlog,
                pending_reports=pending_reports,
                constraints=constraints,
                lane_budget_outcomes=lane_budget_outcomes,
                lane_budget_mode="constrained" if lane_budgets else None,
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
    ) -> dict[str, object]:
        metadata: dict[str, object] = {
            "industry_instance_id": record.instance_id,
            "pending_report_count": len(list(pending_reports)),
            "open_backlog_count": len(list(open_backlog)),
            "paused_lane_ids": list(constraints.paused_lane_ids or []),
            "graph_focus_entities": list(constraints.graph_focus_entities or []),
            "graph_focus_opinions": list(constraints.graph_focus_opinions or []),
        }
        if lane_budget_mode is not None:
            metadata["lane_budget_mode"] = lane_budget_mode
        if lane_budget_outcomes:
            metadata["lane_budget_outcomes"] = lane_budget_outcomes
        return metadata

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
            1 if _backlog_is_report_followup(item) else 0,
            int(item.priority or 0),
            self._graph_focus_score(item=item, constraints=constraints),
            float(lane_weights.get(item.lane_id or "", 0.0)),
            _sort_timestamp(item.updated_at or item.created_at),
        )

    def _lane_budget_map(
        self,
        constraints: PlanningStrategyConstraints,
    ) -> dict[str, dict[str, object]]:
        entries = list(getattr(constraints, "lane_budgets", []) or [])
        budgets: dict[str, dict[str, object]] = {}
        for entry in entries:
            lane_id = _string(_read_field(entry, "lane_id"))
            if lane_id is None:
                continue
            budget_window = _read_field(entry, "budget_window")
            current_share = self._budget_current_share(budget_window)
            target_share = max(_number(_read_field(entry, "target_share")), 0.0)
            min_share = max(_number(_read_field(entry, "min_share")), 0.0)
            max_share = max(_number(_read_field(entry, "max_share")), 0.0)
            force_include_reason = _string(_read_field(entry, "force_include_reason"))
            if force_include_reason is None and min_share > 0.0 and current_share < min_share:
                force_include_reason = "lane-below-min-share"
            budgets[lane_id] = {
                "lane_id": lane_id,
                "budget_window": budget_window,
                "current_share": current_share,
                "target_share": target_share,
                "min_share": min_share,
                "max_share": max_share,
                "review_pressure": _string(_read_field(entry, "review_pressure")) or "",
                "defer_reason": _string(_read_field(entry, "defer_reason")),
                "force_include_reason": force_include_reason,
            }
        return budgets

    def _budget_current_share(self, budget_window: object | None) -> float:
        if isinstance(budget_window, (int, float)):
            return float(budget_window)
        current_share = _number(_read_field(budget_window or {}, "current_share"))
        if current_share > 0.0:
            return current_share
        completed_cycles = int(_number(_read_field(budget_window or {}, "completed_cycles")))
        allocated_cycles = int(
            _number(_read_field(budget_window or {}, "allocated_cycles"))
            or _number(_read_field(budget_window or {}, "selected_cycles"))
            or _number(_read_field(budget_window or {}, "consumed_cycles"))
        )
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
            force_reason = _string((budget or {}).get("force_include_reason"))
            defer_reason = _string((budget or {}).get("defer_reason"))
            if budget is not None and force_reason is None and max_share > 0.0 and current_share >= max_share:
                lane_outcomes[lane_key] = self._lane_outcome(
                    lane_id=lane_id,
                    budget=budget,
                    items=items,
                    outcome="suppressed",
                    reason=defer_reason or "lane-max-share-reached",
                )
                continue
            status = "selected"
            if force_reason is not None:
                status = "force-included"
            elif budget is not None and defer_reason is not None and current_share >= target_share:
                status = "deferred"
            cohorts[status].append(
                {
                    "lane_id": lane_id,
                    "lane_key": lane_key,
                    "budget": budget,
                    "items": list(items),
                    "available_items": list(items),
                    "rank": (
                        1 if any(_backlog_is_report_followup(item) for item in items) else 0,
                        max(target_share - current_share, 0.0),
                        self._review_pressure_score((budget or {}).get("review_pressure")),
                        float(lane_weights.get(lane_id or "", 0.0)),
                        self._item_sort_key(
                            item=items[0],
                            constraints=constraints,
                            lane_weights=lane_weights,
                        ),
                    ),
                },
            )

        selected: list[BacklogItemRecord] = []
        for status in ("force-included", "selected", "deferred"):
            queue = sorted(
                cohorts[status],
                key=lambda entry: entry["rank"],
                reverse=True,
            )
            while queue and len(selected) < selection_limit:
                progressed = False
                next_queue: list[dict[str, object]] = []
                for entry in queue:
                    items = list(entry["items"])
                    if not items or len(selected) >= selection_limit:
                        continue
                    selected.append(items[0])
                    entry["items"] = items[1:]
                    progressed = True
                    if entry["items"]:
                        next_queue.append(entry)
                if not progressed:
                    break
                queue = next_queue

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
                    reason = _string((budget or {}).get("force_include_reason"))
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
                )
        return selected, lane_outcomes

    def _lane_outcome(
        self,
        *,
        lane_id: str | None,
        budget: dict[str, object] | None,
        items: Sequence[BacklogItemRecord],
        outcome: str,
        reason: str | None,
        selected_backlog_item_ids: Sequence[str] | None = None,
    ) -> dict[str, object]:
        return {
            "lane_id": lane_id,
            "outcome": outcome,
            "reason": reason,
            "backlog_item_ids": [item.id for item in items],
            "selected_backlog_item_ids": list(selected_backlog_item_ids or []),
            "budget_window": (budget or {}).get("budget_window"),
            "target_share": _number((budget or {}).get("target_share")),
            "min_share": _number((budget or {}).get("min_share")),
            "max_share": _number((budget or {}).get("max_share")),
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
