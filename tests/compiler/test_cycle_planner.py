# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from copaw.compiler.planning import CyclePlanningCompiler, PlanningStrategyConstraints
from copaw.state import AgentReportRecord, BacklogItemRecord, IndustryInstanceRecord, OperatingCycleRecord


def _backlog_item(
    item_id: str,
    *,
    lane_id: str | None,
    priority: int,
    title: str | None = None,
    summary: str | None = None,
    metadata: dict[str, object] | None = None,
) -> BacklogItemRecord:
    return BacklogItemRecord(
        id=item_id,
        industry_instance_id="industry-1",
        lane_id=lane_id,
        title=title or f"Backlog {item_id}",
        summary=summary or f"Summary for {item_id}",
        priority=priority,
        metadata=metadata or {},
    )


def _constraints(**overrides: object) -> SimpleNamespace:
    payload: dict[str, object] = {
        "mission": "",
        "north_star": "",
        "priority_order": [],
        "lane_weights": {},
        "planning_policy": [],
        "review_rules": [],
        "paused_lane_ids": [],
        "current_focuses": [],
        "graph_focus_entities": [],
        "graph_focus_opinions": [],
        "lane_budgets": [],
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _lane_budget(
    lane_id: str,
    *,
    current_share: float,
    target_share: float,
    min_share: float,
    max_share: float,
    review_pressure: str,
    defer_reason: str | None = None,
    force_include_reason: str | None = None,
    completed_cycles: int = 2,
) -> dict[str, object]:
    return {
        "lane_id": lane_id,
        "budget_window": {
            "completed_cycles": completed_cycles,
            "current_share": current_share,
        },
        "target_share": target_share,
        "min_share": min_share,
        "max_share": max_share,
        "review_pressure": review_pressure,
        "defer_reason": defer_reason,
        "force_include_reason": force_include_reason,
    }


def test_cycle_planner_prefers_followup_pressure_and_skips_paused_lanes() -> None:
    planner = CyclePlanningCompiler()
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind",
        summary="Northwind execution shell",
        owner_scope="industry:northwind",
    )
    constraints = PlanningStrategyConstraints(
        lane_weights={"lane-growth": 0.9, "lane-ops": 0.2, "lane-paused": 1.0},
        paused_lane_ids=["lane-paused"],
        planning_policy=["prefer-followup-before-net-new"],
    )

    decision = planner.plan(
        record=record,
        current_cycle=None,
        next_cycle_due_at=None,
        open_backlog=[
            _backlog_item("paused", lane_id="lane-paused", priority=10),
            _backlog_item(
                "followup",
                lane_id="lane-ops",
                priority=3,
                metadata={"synthesis_kind": "followup-needed", "source_report_id": "report-1"},
            ),
            _backlog_item("growth-1", lane_id="lane-growth", priority=2),
            _backlog_item("growth-2", lane_id="lane-growth", priority=1),
        ],
        pending_reports=[
            AgentReportRecord(
                id="report-1",
                industry_instance_id="industry-1",
                headline="Follow-up still needed",
                owner_agent_id="agent-1",
            ),
        ],
        force=False,
        strategy_constraints=constraints,
    )

    assert decision.should_start is True
    assert decision.reason == "planned-open-backlog"
    assert decision.selected_backlog_item_ids == ["followup", "growth-1", "growth-2"]
    assert decision.selected_lane_ids == ["lane-ops", "lane-growth"]


def test_cycle_planner_holds_when_cycle_is_already_inflight() -> None:
    planner = CyclePlanningCompiler()
    current_cycle = OperatingCycleRecord(
        id="cycle-1",
        industry_instance_id="industry-1",
        cycle_kind="daily",
        title="Northwind daily cycle",
        status="active",
    )

    decision = planner.plan(
        record=IndustryInstanceRecord(
            instance_id="industry-1",
            label="Northwind",
            summary="Northwind execution shell",
            owner_scope="industry:northwind",
        ),
        current_cycle=current_cycle,
        next_cycle_due_at=datetime(2026, 4, 2, tzinfo=UTC),
        open_backlog=[_backlog_item("growth-1", lane_id="lane-growth", priority=2)],
        pending_reports=[],
        force=False,
        strategy_constraints=PlanningStrategyConstraints(),
    )

    assert decision.should_start is False
    assert decision.reason == "cycle-inflight"
    assert decision.selected_backlog_item_ids == []


def test_cycle_planner_force_can_override_inflight_cycle_for_scoped_backlog() -> None:
    planner = CyclePlanningCompiler()
    current_cycle = OperatingCycleRecord(
        id="cycle-1",
        industry_instance_id="industry-1",
        cycle_kind="daily",
        title="Northwind daily cycle",
        status="active",
    )

    decision = planner.plan(
        record=IndustryInstanceRecord(
            instance_id="industry-1",
            label="Northwind",
            summary="Northwind execution shell",
            owner_scope="industry:northwind",
        ),
        current_cycle=current_cycle,
        next_cycle_due_at=datetime(2026, 4, 2, tzinfo=UTC),
        open_backlog=[_backlog_item("growth-1", lane_id="lane-growth", priority=2)],
        pending_reports=[],
        force=True,
        strategy_constraints=PlanningStrategyConstraints(),
    )

    assert decision.should_start is True
    assert decision.reason == "forced"
    assert decision.selected_backlog_item_ids == ["growth-1"]


def test_cycle_planner_force_keeps_high_priority_operator_item_ahead_of_lower_priority_schedule_items() -> None:
    planner = CyclePlanningCompiler()
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind",
        summary="Northwind execution shell",
        owner_scope="industry:northwind",
    )
    constraints = PlanningStrategyConstraints(
        lane_weights={"lane-exec": 0.9, "lane-solution": 0.2},
    )

    decision = planner.plan(
        record=record,
        current_cycle=None,
        next_cycle_due_at=None,
        open_backlog=[
            _backlog_item(
                "operator-sop",
                lane_id="lane-solution",
                priority=5,
                metadata={"fixed_sop_binding_id": "binding-1"},
            ),
            _backlog_item(
                "exec-schedule-1",
                lane_id="lane-exec",
                priority=2,
                metadata={"source_kind_hint": "schedule"},
            ),
            _backlog_item(
                "exec-schedule-2",
                lane_id="lane-exec",
                priority=2,
                metadata={"source_kind_hint": "schedule"},
            ),
        ],
        pending_reports=[],
        force=True,
        strategy_constraints=constraints,
    )

    assert decision.should_start is True
    assert decision.selected_backlog_item_ids[0] == "operator-sop"


def test_cycle_planner_uses_graph_focus_to_break_near_ties() -> None:
    planner = CyclePlanningCompiler()
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind",
        summary="Northwind execution shell",
        owner_scope="industry:northwind",
    )

    decision = planner.plan(
        record=record,
        current_cycle=None,
        next_cycle_due_at=None,
        open_backlog=[
            _backlog_item(
                "schedule-refresh",
                lane_id="lane-growth",
                priority=3,
                title="Refresh publishing schedule",
                summary="Adjust the weekly publishing schedule for the next cycle.",
            ),
            _backlog_item(
                "inventory-variance-review",
                lane_id="lane-growth",
                priority=3,
                title="Review weekend inventory variance",
                summary="Check whether staffing changes should wait until the variance is explained.",
            ),
        ],
        pending_reports=[],
        force=False,
        strategy_constraints=PlanningStrategyConstraints(
            graph_focus_entities=["inventory", "weekend"],
            graph_focus_opinions=["staffing:caution:premature-change"],
        ),
    )

    assert decision.should_start is True
    assert decision.selected_backlog_item_ids[0] == "inventory-variance-review"


def test_cycle_planner_lane_budgets_constrain_selection_across_cycles_with_lane_metadata() -> None:
    planner = CyclePlanningCompiler()
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind",
        summary="Northwind execution shell",
        owner_scope="industry:northwind",
    )
    open_backlog = [
        _backlog_item("growth-1", lane_id="lane-growth", priority=4),
        _backlog_item("retention-1", lane_id="lane-retention", priority=2),
        _backlog_item(
            "ops-followup-1",
            lane_id="lane-ops",
            priority=3,
            metadata={"source_report_id": "report-7", "synthesis_kind": "followup-needed"},
        ),
    ]

    cycle_one = planner.plan(
        record=record,
        current_cycle=None,
        next_cycle_due_at=None,
        open_backlog=open_backlog,
        pending_reports=[],
        force=False,
        strategy_constraints=_constraints(
            lane_weights={"lane-growth": 0.95, "lane-retention": 0.1, "lane-ops": 0.8},
            planning_policy=["single-assignment-cycle"],
            lane_budgets=[
                _lane_budget(
                    "lane-growth",
                    current_share=1.0,
                    target_share=0.4,
                    min_share=0.2,
                    max_share=0.6,
                    review_pressure="throttle",
                    defer_reason="lane-max-share-reached",
                ),
                _lane_budget(
                    "lane-retention",
                    current_share=0.0,
                    target_share=0.4,
                    min_share=0.3,
                    max_share=0.7,
                    review_pressure="catch-up",
                    force_include_reason="lane-below-min-share",
                ),
                _lane_budget(
                    "lane-ops",
                    current_share=0.5,
                    target_share=0.3,
                    min_share=0.2,
                    max_share=0.7,
                    review_pressure="steady",
                    defer_reason="hold-until-next-cycle-budget-window",
                ),
            ],
        ),
    )

    assert cycle_one.should_start is True
    assert cycle_one.selected_backlog_item_ids == ["retention-1"]
    lane_outcomes = cycle_one.metadata["lane_budget_outcomes"]
    assert lane_outcomes["lane-growth"]["outcome"] == "suppressed"
    assert lane_outcomes["lane-growth"]["reason"] == "lane-max-share-reached"
    assert lane_outcomes["lane-retention"]["outcome"] == "force-included"
    assert lane_outcomes["lane-retention"]["reason"] == "lane-below-min-share"
    assert lane_outcomes["lane-ops"]["outcome"] == "deferred"
    assert lane_outcomes["lane-ops"]["reason"] == "hold-until-next-cycle-budget-window"

    cycle_two = planner.plan(
        record=record,
        current_cycle=None,
        next_cycle_due_at=None,
        open_backlog=open_backlog,
        pending_reports=[],
        force=False,
        strategy_constraints=_constraints(
            lane_weights={"lane-growth": 0.95, "lane-retention": 0.1, "lane-ops": 0.8},
            planning_policy=["single-assignment-cycle"],
            lane_budgets=[
                _lane_budget(
                    "lane-growth",
                    current_share=0.2,
                    target_share=0.4,
                    min_share=0.2,
                    max_share=0.6,
                    review_pressure="catch-up",
                ),
                _lane_budget(
                    "lane-retention",
                    current_share=0.5,
                    target_share=0.4,
                    min_share=0.3,
                    max_share=0.7,
                    review_pressure="steady",
                ),
                _lane_budget(
                    "lane-ops",
                    current_share=0.5,
                    target_share=0.3,
                    min_share=0.2,
                    max_share=0.7,
                    review_pressure="steady",
                    defer_reason="hold-until-next-cycle-budget-window",
                ),
            ],
        ),
    )

    assert cycle_two.should_start is True
    assert cycle_two.selected_backlog_item_ids == ["growth-1"]
    assert cycle_two.metadata["lane_budget_outcomes"]["lane-growth"]["outcome"] == "selected"


def test_cycle_planner_force_path_bypasses_lane_budget_suppression_for_scoped_backlog() -> None:
    planner = CyclePlanningCompiler()
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind",
        summary="Northwind execution shell",
        owner_scope="industry:northwind",
    )

    decision = planner.plan(
        record=record,
        current_cycle=None,
        next_cycle_due_at=None,
        open_backlog=[
            _backlog_item("growth-1", lane_id="lane-growth", priority=4),
            _backlog_item("growth-2", lane_id="lane-growth", priority=3),
        ],
        pending_reports=[],
        force=True,
        strategy_constraints=_constraints(
            lane_weights={"lane-growth": 1.0},
            lane_budgets=[
                _lane_budget(
                    "lane-growth",
                    current_share=1.0,
                    target_share=0.2,
                    min_share=0.0,
                    max_share=0.3,
                    review_pressure="throttle",
                    defer_reason="lane-max-share-reached",
                ),
            ],
        ),
    )

    assert decision.should_start is True
    assert decision.reason == "forced"
    assert decision.selected_backlog_item_ids == ["growth-1", "growth-2"]
