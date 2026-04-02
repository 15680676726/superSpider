# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.compiler.planning.strategy_compiler import StrategyPlanningCompiler
from copaw.state import StrategyMemoryRecord


def test_strategy_compiler_emits_lane_and_review_constraints() -> None:
    compiler = StrategyPlanningCompiler()
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Industry planning shell",
        north_star="Grow retained revenue",
        priority_order=["retain", "grow", "expand"],
        lane_weights={"lane-retention": 0.7, "lane-growth": 0.3},
        planning_policy=["prefer-followup-before-net-new"],
        review_rules=["repeat-failure-needs-review"],
        paused_lane_ids=["lane-experimental"],
    )

    constraints = compiler.compile(strategy)

    assert constraints.north_star == "Grow retained revenue"
    assert constraints.lane_weights["lane-retention"] == 0.7
    assert constraints.planning_policy == ["prefer-followup-before-net-new"]
    assert "repeat-failure-needs-review" in constraints.review_rules
    assert constraints.paused_lane_ids == ["lane-experimental"]


def test_strategy_compiler_returns_empty_constraints_without_strategy() -> None:
    compiler = StrategyPlanningCompiler()

    constraints = compiler.compile(None)

    assert constraints.mission == ""
    assert constraints.priority_order == []
    assert constraints.review_rules == []
