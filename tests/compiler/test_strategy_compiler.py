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
        strategic_uncertainties=[
            {
                "uncertainty_id": "uncertainty-1",
                "statement": "Retention signal is still noisy.",
                "scope": "lane",
                "impact_level": "high",
                "current_confidence": 0.45,
                "evidence_for_refs": ["evidence-for-1"],
                "evidence_against_refs": ["evidence-against-1"],
                "review_by_cycle": "cycle-2",
                "escalate_when": ["confidence drop", "target miss"],
            }
        ],
        lane_budgets=[
            {
                "lane_id": "lane-retention",
                "budget_window": "next-3-cycles",
                "target_share": 0.6,
                "min_share": 0.4,
                "max_share": 0.75,
                "review_pressure": "protect-core-signal",
                "defer_reason": "wait for cleaner churn baseline",
                "force_include_reason": "current cycle is retention-critical",
            }
        ],
    )

    constraints = compiler.compile(strategy)

    assert constraints.north_star == "Grow retained revenue"
    assert constraints.lane_weights["lane-retention"] == 0.7
    assert constraints.planning_policy == ["prefer-followup-before-net-new"]
    assert "repeat-failure-needs-review" in constraints.review_rules
    assert constraints.paused_lane_ids == ["lane-experimental"]
    assert constraints.strategic_uncertainties[0].uncertainty_id == "uncertainty-1"
    assert constraints.lane_budgets[0].lane_id == "lane-retention"
    assert [rule.rule_id for rule in constraints.strategy_trigger_rules] == [
        "review-rule:0",
        "uncertainty:uncertainty-1:confidence-drop",
        "uncertainty:uncertainty-1:target-miss",
    ]
    assert constraints.strategy_trigger_rules[0].source_type == "review_rule"
    assert constraints.strategy_trigger_rules[1].decision_hint == "strategy_review_required"
    assert constraints.strategy_trigger_rules[2].decision_hint == "lane_reweight"


def test_strategy_compiler_returns_empty_constraints_without_strategy() -> None:
    compiler = StrategyPlanningCompiler()

    constraints = compiler.compile(None)

    assert constraints.mission == ""
    assert constraints.priority_order == []
    assert constraints.review_rules == []
    assert constraints.strategic_uncertainties == []
    assert constraints.lane_budgets == []
    assert constraints.strategy_trigger_rules == []
