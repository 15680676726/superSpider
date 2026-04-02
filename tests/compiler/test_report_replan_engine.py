# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.compiler.planning import ReportReplanEngine


def _strategy_change(decision: object) -> dict[str, object]:
    activation = getattr(decision, "activation", {})
    if isinstance(activation, dict):
        strategy_change = activation.get("strategy_change")
        if isinstance(strategy_change, dict):
            return strategy_change
    return {}


def _decision_kind(decision: object) -> str | None:
    return getattr(decision, "decision_kind", None) or _strategy_change(decision).get("decision_kind")


def _trigger_family(decision: object) -> str | None:
    return getattr(decision, "trigger_family", None) or _strategy_change(decision).get("trigger_family")


def test_report_replan_engine_translates_synthesis_surface_into_follow_up_backlog_decision() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile(
        {
            "recommended_actions": [{"action_id": "follow-up:1"}],
            "replan_directives": [{"directive_id": "dir-1"}],
            "activation": {
                "top_constraints": ["Need validated weekend cause."],
                "top_entities": ["weekend-variance"],
                "top_opinions": ["staffing:caution:premature-change"],
            },
            "replan_decision": {
                "decision_id": "report-synthesis:needs-replan:failed-report:1",
                "status": "needs-replan",
                "summary": "1 unresolved report synthesis signal requires main-brain judgment.",
                "reason_ids": ["failed-report:1"],
                "source_report_ids": ["report-1"],
                "topic_keys": ["weekend-variance"],
            },
        },
    )

    assert decision.status == "needs-replan"
    assert _decision_kind(decision) == "follow_up_backlog"
    assert _trigger_family(decision) == "local_follow_up_pressure"
    assert decision.reason_ids == ["failed-report:1"]
    assert decision.source_report_ids == ["report-1"]
    assert decision.directives == [{"directive_id": "dir-1"}]
    assert decision.recommended_actions == [{"action_id": "follow-up:1"}]
    assert decision.activation["top_constraints"] == ["Need validated weekend cause."]
    assert decision.activation["top_entities"] == ["weekend-variance"]
    assert decision.activation["top_opinions"] == ["staffing:caution:premature-change"]
    assert _strategy_change(decision)["rationale"] == (
        "1 unresolved report synthesis signal requires main-brain judgment."
    )


def test_report_replan_engine_escalates_repeated_blocker_across_cycles_to_cycle_rebalance() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile(
        {
            "replan_reasons": ["Supplier approval blocker repeated across three cycles."],
            "replan_decision": {
                "decision_id": "report-synthesis:needs-replan:supplier-approval",
                "status": "needs-replan",
                "summary": "Repeated blocker requires main-brain judgment.",
                "reason_ids": ["blocker:supplier-approval"],
                "source_report_ids": ["report-1", "report-2"],
                "topic_keys": ["supplier-approval"],
            },
            "strategy_change_context": {
                "repeated_blockers": [
                    {
                        "blocker_key": "supplier-approval",
                        "lane_id": "lane-ops",
                        "cycle_ids": ["cycle-1", "cycle-2", "cycle-3"],
                        "source_report_ids": ["report-1", "report-2"],
                        "topic_key": "supplier-approval",
                        "summary": "Supplier approval blocker repeated across three cycles for lane-ops.",
                    },
                ],
            },
        },
    )

    assert decision.status == "needs-replan"
    assert _decision_kind(decision) == "cycle_rebalance"
    assert _trigger_family(decision) == "repeated_blocker_across_cycles"
    assert "cycle rebalance" in decision.summary.lower()
    assert _strategy_change(decision)["trigger_evidence"] == [
        {
            "blocker_key": "supplier-approval",
            "lane_id": "lane-ops",
            "cycle_ids": ["cycle-1", "cycle-2", "cycle-3"],
            "source_report_ids": ["report-1", "report-2"],
            "topic_key": "supplier-approval",
            "summary": "Supplier approval blocker repeated across three cycles for lane-ops.",
        },
    ]


def test_report_replan_engine_escalates_repeated_assignment_miss_to_lane_reweight() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile(
        {
            "replan_decision": {
                "decision_id": "report-synthesis:needs-replan:lane-growth",
                "status": "needs-replan",
                "summary": "Repeated lane miss requires main-brain judgment.",
                "reason_ids": ["assignment-miss:lane-growth:conversion"],
                "source_report_ids": ["report-3", "report-4"],
                "topic_keys": ["conversion"],
            },
            "strategy_change_context": {
                "assignment_misses": [
                    {
                        "lane_id": "lane-growth",
                        "objective_key": "conversion",
                        "missed_assignment_ids": ["assignment-1", "assignment-2"],
                        "source_report_ids": ["report-3", "report-4"],
                        "summary": "Two assignments missed the same lane-growth conversion objective.",
                    },
                ],
            },
        },
    )

    assert decision.status == "needs-replan"
    assert _decision_kind(decision) == "lane_reweight"
    assert _trigger_family(decision) == "repeated_assignment_miss_same_lane_objective"
    assert "lane reweight" in decision.summary.lower()
    assert "conversion" in decision.topic_keys


def test_report_replan_engine_escalates_confidence_collapse_to_strategy_review() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile(
        {
            "replan_decision": {
                "decision_id": "report-synthesis:needs-replan:weekend-variance",
                "status": "needs-replan",
                "summary": "Confidence collapse requires main-brain judgment.",
                "reason_ids": ["uncertainty:weekend-variance"],
                "source_report_ids": ["report-5"],
                "topic_keys": ["weekend-variance"],
            },
            "strategy_change_context": {
                "uncertainty_collapses": [
                    {
                        "uncertainty_key": "weekend-cause",
                        "topic_key": "weekend-variance",
                        "previous_confidence": 0.74,
                        "current_confidence": 0.21,
                        "source_report_ids": ["report-5"],
                        "summary": "Confidence on the tracked weekend-cause uncertainty collapsed from 0.74 to 0.21.",
                    },
                ],
            },
        },
    )

    assert decision.status == "needs-replan"
    assert _decision_kind(decision) == "strategy_review_required"
    assert _trigger_family(decision) == "confidence_collapse_tracked_uncertainty"
    assert "strategy review" in decision.summary.lower()
    assert _strategy_change(decision)["trigger_evidence"][0]["current_confidence"] == 0.21


def test_report_replan_engine_escalates_repeated_contradictions_to_strategy_review() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile(
        {
            "replan_decision": {
                "decision_id": "report-synthesis:needs-replan:warehouse-approval",
                "status": "needs-replan",
                "summary": "Repeated contradiction requires main-brain judgment.",
                "reason_ids": ["activation:contradictions", "failed-report:report-6"],
                "source_report_ids": ["report-6"],
                "topic_keys": ["warehouse-approval"],
            },
            "activation": {
                "contradiction_count": 2,
                "top_constraints": ["Approval status still conflicts with recent execution evidence."],
            },
            "strategy_change_context": {
                "evidence_contradictions": [
                    {
                        "topic_key": "warehouse-approval",
                        "source_families": ["synthesis", "activation", "report"],
                        "repeat_count": 3,
                        "source_report_ids": ["report-6"],
                        "summary": "Repeated contradiction spans synthesis, activation, and report evidence.",
                    },
                ],
            },
        },
    )

    assert decision.status == "needs-replan"
    assert _decision_kind(decision) == "strategy_review_required"
    assert _trigger_family(decision) == "repeated_evidence_contradiction"
    assert "strategy review" in decision.summary.lower()
    assert _strategy_change(decision)["trigger_evidence"][0]["source_families"] == [
        "synthesis",
        "activation",
        "report",
    ]


def test_report_replan_engine_returns_clear_when_synthesis_is_missing() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile(None)

    assert decision.status == "clear"
    assert _decision_kind(decision) is None
    assert decision.reason_ids == []
    assert decision.directives == []
