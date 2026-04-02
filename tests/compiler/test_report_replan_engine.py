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
                "summary": "1 unresolved report synthesis signal requires main-brain judgment.",
                "reason_ids": ["failed-report:1"],
                "source_report_ids": ["report-1"],
                "topic_keys": ["weekend-variance"],
            },
        },
    )

    assert decision.status == "needs-replan"
    assert decision.reason_ids == ["failed-report:1"]
    assert decision.source_report_ids == ["report-1"]
    assert decision.directives == [{"directive_id": "dir-1"}]
    assert decision.recommended_actions == [{"action_id": "follow-up:1"}]
    assert decision.activation["top_constraints"] == ["Need validated weekend cause."]


def test_report_replan_engine_returns_clear_when_synthesis_is_missing() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile(None)

    assert decision.status == "clear"
    assert decision.reason_ids == []
    assert decision.directives == []
