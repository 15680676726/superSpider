# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.compiler.planning import ReportReplanEngine


def test_report_replan_engine_translates_synthesis_surface_into_formal_decision() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile(
        {
            "recommended_actions": [{"action_id": "follow-up:1"}],
            "replan_directives": [{"directive_id": "dir-1"}],
            "activation": {"top_constraints": ["Need validated weekend cause."]},
            "replan_decision": {
                "decision_id": "report-synthesis:needs-replan:failed-report:1",
                "status": "needs-replan",
                "decision_kind": "follow_up_backlog",
                "summary": "1 unresolved report synthesis signal requires main-brain judgment.",
                "reason_ids": ["failed-report:1"],
                "source_report_ids": ["report-1"],
                "topic_keys": ["weekend-variance"],
            },
        },
    )

    assert decision.status == "needs-replan"
    assert decision.decision_kind == "follow_up_backlog"
    assert decision.reason_ids == ["failed-report:1"]
    assert decision.source_report_ids == ["report-1"]
    assert decision.directives == [{"directive_id": "dir-1"}]
    assert decision.recommended_actions == [{"action_id": "follow-up:1"}]
    assert decision.activation["top_constraints"] == ["Need validated weekend cause."]


def test_report_replan_engine_returns_clear_when_synthesis_is_missing() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile(None)

    assert decision.status == "clear"
    assert decision.decision_kind == "clear"
    assert decision.reason_ids == []
    assert decision.directives == []


def test_report_replan_engine_emits_lane_reweight_for_target_miss() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile(
        {
            "replan_decision": {
                "decision_id": "report-synthesis:needs-replan:lane-miss",
                "status": "needs-replan",
                "decision_kind": "lane_reweight",
                "trigger_families": ["target-miss"],
                "affected_lane_ids": ["lane-growth"],
                "summary": "Repeated lane miss should reweight growth lane.",
            }
        },
    )

    assert decision.status == "needs-replan"
    assert decision.decision_kind == "lane_reweight"
    assert decision.trigger_families == ["target-miss"]
    assert decision.affected_lane_ids == ["lane-growth"]


def test_report_replan_engine_escalates_to_strategy_review_for_confidence_collapse() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile(
        {
            "activation": {
                "strategy_change": {
                    "decision_kind": "strategy_review_required",
                    "trigger_families": ["confidence-drop"],
                    "affected_uncertainty_ids": ["uncertainty:weekend-variance"],
                }
            },
            "needs_replan": True,
            "replan_reasons": ["Weekend variance confidence collapsed."],
        },
    )

    assert decision.status == "needs-replan"
    assert decision.decision_kind == "strategy_review_required"
    assert decision.trigger_families == ["confidence-drop"]
    assert decision.affected_uncertainty_ids == ["uncertainty:weekend-variance"]
