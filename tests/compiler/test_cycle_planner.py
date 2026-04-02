# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import UTC, datetime

from copaw.compiler.planning import CyclePlanningCompiler, PlanningStrategyConstraints
from copaw.state import AgentReportRecord, BacklogItemRecord, IndustryInstanceRecord, OperatingCycleRecord


def _backlog_item(
    item_id: str,
    *,
    lane_id: str | None,
    priority: int,
    metadata: dict[str, object] | None = None,
) -> BacklogItemRecord:
    return BacklogItemRecord(
        id=item_id,
        industry_instance_id="industry-1",
        lane_id=lane_id,
        title=f"Backlog {item_id}",
        summary=f"Summary for {item_id}",
        priority=priority,
        metadata=metadata or {},
    )


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


def test_cycle_planner_uses_lane_budgets_to_defer_and_force_include_lanes() -> None:
    planner = CyclePlanningCompiler()
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind",
        summary="Northwind execution shell",
        owner_scope="industry:northwind",
    )
    constraints = PlanningStrategyConstraints.model_validate(
        {
            "lane_weights": {"lane-growth": 0.9, "lane-ops": 0.4},
            "lane_budgets": [
                {
                    "lane_id": "lane-growth",
                    "budget_window": "next-3-cycles",
                    "target_share": 0.2,
                    "min_share": 0.0,
                    "max_share": 0.25,
                    "current_share": 0.5,
                    "defer_reason": "growth-lane-is-over-budget",
                },
                {
                    "lane_id": "lane-ops",
                    "budget_window": "next-3-cycles",
                    "target_share": 0.5,
                    "min_share": 0.4,
                    "max_share": 0.75,
                    "current_share": 0.1,
                    "force_include_reason": "ops-lane-needs-recovery-capacity",
                },
            ],
        },
    )

    decision = planner.plan(
        record=record,
        current_cycle=None,
        next_cycle_due_at=None,
        open_backlog=[
            _backlog_item("growth-1", lane_id="lane-growth", priority=4),
            _backlog_item("ops-1", lane_id="lane-ops", priority=1),
        ],
        pending_reports=[],
        force=False,
        strategy_constraints=constraints,
    )

    assert decision.should_start is True
    assert decision.selected_backlog_item_ids[0] == "ops-1"
    assert "growth-1" not in decision.selected_backlog_item_ids
    lane_outcomes = {
        item["lane_id"]: item["status"]
        for item in decision.metadata["lane_budget_outcomes"]
    }
    assert lane_outcomes["lane-growth"] == "deferred"
    assert lane_outcomes["lane-ops"] == "force-included"


def test_cycle_planner_can_suppress_a_lane_when_budget_cap_is_exhausted() -> None:
    planner = CyclePlanningCompiler()
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind",
        summary="Northwind execution shell",
        owner_scope="industry:northwind",
    )
    constraints = PlanningStrategyConstraints.model_validate(
        {
            "lane_budgets": [
                {
                    "lane_id": "lane-growth",
                    "budget_window": "next-3-cycles",
                    "target_share": 0.2,
                    "min_share": 0.0,
                    "max_share": 0.25,
                    "current_share": 0.9,
                }
            ],
        },
    )

    decision = planner.plan(
        record=record,
        current_cycle=None,
        next_cycle_due_at=None,
        open_backlog=[_backlog_item("growth-1", lane_id="lane-growth", priority=4)],
        pending_reports=[],
        force=False,
        strategy_constraints=constraints,
    )

    assert decision.should_start is False
    assert decision.reason == "planner-no-open-backlog"
    assert decision.metadata["lane_budget_outcomes"][0]["status"] == "suppressed"


def test_cycle_planner_force_scoped_backlog_overrides_lane_budget_deferral() -> None:
    planner = CyclePlanningCompiler()
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind",
        summary="Northwind execution shell",
        owner_scope="industry:northwind",
    )
    constraints = PlanningStrategyConstraints.model_validate(
        {
            "lane_budgets": [
                {
                    "lane_id": "lane-growth",
                    "budget_window": "next-3-cycles",
                    "target_share": 0.2,
                    "min_share": 0.0,
                    "max_share": 0.25,
                    "current_share": 0.9,
                    "defer_reason": "growth-lane-is-over-budget",
                }
            ],
        },
    )

    decision = planner.plan(
        record=record,
        current_cycle=None,
        next_cycle_due_at=None,
        open_backlog=[_backlog_item("growth-1", lane_id="lane-growth", priority=4)],
        pending_reports=[],
        force=True,
        force_scoped_backlog=True,
        strategy_constraints=constraints,
    )

    assert decision.should_start is True
    assert decision.reason == "forced"
    assert decision.selected_backlog_item_ids == ["growth-1"]
    assert decision.metadata["force_scoped_backlog"] is True
    assert decision.metadata["lane_budget_outcomes"][0]["status"] == "force-included"
