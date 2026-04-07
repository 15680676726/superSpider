# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.compiler.planning import ReportReplanEngine


def _payload(decision: object) -> dict[str, object]:
    model_dump = getattr(decision, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json", exclude_none=True)
        if isinstance(payload, dict):
            return payload
    return {}


def _strategy_change(decision: object) -> dict[str, object]:
    activation = getattr(decision, "activation", {})
    if isinstance(activation, dict):
        strategy_change = activation.get("strategy_change")
        if isinstance(strategy_change, dict):
            return strategy_change
    return {}


def _top_level_strategy_change(decision: object) -> dict[str, object]:
    strategy_change = getattr(decision, "strategy_change", None)
    if isinstance(strategy_change, dict):
        return strategy_change
    payload = _payload(decision)
    nested = payload.get("strategy_change")
    return nested if isinstance(nested, dict) else {}


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
    assert decision.strategy_change_decision == "follow_up_backlog"
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
    assert decision.planning_shell == {
        "mode": "report-replan-shell",
        "scope": "report-replan",
        "plan_id": "report-synthesis:needs-replan:failed-report:1",
        "resume_key": "report:report-1",
        "fork_key": "decision:follow_up_backlog",
        "verify_reminder": "Verify synthesis pressure before mutating backlog, cycle, lane, or strategy truth.",
    }


def test_report_replan_engine_compiles_exception_absorption_replan_to_cycle_rebalance() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile_exception_absorption_replan(
        case_kind="repeated-blocker-same-scope",
        scope_ref="assignment:assignment-1",
        owner_agent_id="agent-ops",
        summary="Repeated blocker pressure is hitting the same execution scope.",
    )

    assert decision.status == "needs-replan"
    assert decision.strategy_change_decision == "cycle_rebalance"
    assert _trigger_family(decision) == "repeated_blocker_across_cycles"
    assert decision.planning_shell["fork_key"] == "decision:cycle_rebalance"


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
    assert decision.strategy_change_decision == "cycle_rebalance"
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
    assert decision.strategy_change_decision == "lane_reweight"
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
    assert decision.strategy_change_decision == "strategy_review_required"
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
    assert decision.strategy_change_decision == "strategy_review_required"
    assert _trigger_family(decision) == "repeated_evidence_contradiction"
    assert "strategy review" in decision.summary.lower()
    assert _strategy_change(decision)["trigger_evidence"][0]["source_families"] == [
        "synthesis",
        "activation",
        "report",
    ]


def test_report_replan_engine_promotes_trigger_consumption_into_formal_fields() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile(
        {
            "replan_decision": {
                "decision_id": "report-synthesis:needs-replan:compliance-signoff",
                "status": "needs-replan",
                "summary": "Repeated blocker requires main-brain judgment.",
                "reason_ids": ["blocker:compliance-signoff"],
                "source_report_ids": ["report-7", "report-8"],
                "topic_keys": ["compliance-signoff"],
                "trigger_context": {
                    "review_window": "weekly",
                    "source_scope": "industry-1",
                },
            },
            "strategy_change_context": {
                "trigger_rule_ids": [
                    "review-rule:0",
                    "uncertainty:uncertainty-1:confidence-drop",
                ],
                "trigger_context": {
                    "strategic_uncertainty_ids": ["uncertainty-1"],
                    "lane_budget_pressure": {"lane-ops": "protect-approval-path"},
                },
                "repeated_blockers": [
                    {
                        "blocker_key": "compliance-signoff",
                        "lane_id": "lane-ops",
                        "cycle_ids": ["cycle-4", "cycle-5"],
                        "source_report_ids": ["report-7", "report-8"],
                        "topic_key": "compliance-signoff",
                        "summary": "Compliance signoff blocker repeated across cycles.",
                    },
                ],
            },
        },
    )

    payload = _payload(decision)

    assert decision.strategy_change_decision == "cycle_rebalance"
    assert decision.trigger_rule_ids == [
        "review-rule:0",
        "uncertainty:uncertainty-1:confidence-drop",
    ]
    assert "trigger_context" in payload
    assert payload["trigger_context"]["review_window"] == "weekly"
    assert payload["trigger_context"]["source_scope"] == "industry-1"
    assert payload["trigger_context"]["strategic_uncertainty_ids"] == ["uncertainty-1"]
    assert payload["trigger_context"]["lane_budget_pressure"] == {
        "lane-ops": "protect-approval-path",
    }


def test_report_replan_engine_promotes_strategy_change_payload_into_top_level_surface() -> None:
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
                "trigger_rule_ids": ["review-rule:warehouse-approval"],
                "trigger_context": {
                    "review_window": "weekly",
                    "source_scope": "industry-1",
                },
            },
            "activation": {
                "contradiction_count": 2,
            },
            "strategy_change_context": {
                "trigger_rule_ids": ["activation-rule:contradiction-repeat"],
                "trigger_context": {
                    "strategic_uncertainty_ids": ["uncertainty-warehouse-approval"],
                },
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

    strategy_change = _top_level_strategy_change(decision)

    assert strategy_change == {
        "decision_kind": "strategy_review_required",
        "trigger_family": "repeated_evidence_contradiction",
        "trigger_rule_ids": [
            "review-rule:warehouse-approval",
            "activation-rule:contradiction-repeat",
        ],
        "trigger_context": {
            "review_window": "weekly",
            "source_scope": "industry-1",
            "strategic_uncertainty_ids": ["uncertainty-warehouse-approval"],
            "trigger_families": ["repeated_evidence_contradiction"],
        },
        "rationale": "Repeated contradiction spans synthesis, activation, and report evidence.",
        "trigger_evidence": [
            {
                "topic_key": "warehouse-approval",
                "source_families": ["synthesis", "activation", "report"],
                "repeat_count": 3,
                "source_report_ids": ["report-6"],
                "summary": "Repeated contradiction spans synthesis, activation, and report evidence.",
            },
        ],
    }
    assert strategy_change == _strategy_change(decision)
    assert decision.trigger_context == {
        "review_window": "weekly",
        "source_scope": "industry-1",
        "strategic_uncertainty_ids": ["uncertainty-warehouse-approval"],
        "trigger_families": ["repeated_evidence_contradiction"],
    }


def test_report_replan_engine_promotes_relation_activation_into_typed_fields() -> None:
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
                "top_relation_evidence": [
                    {
                        "relation_id": "relation-warehouse-approval",
                        "relation_kind": "contradicts",
                        "summary": "Warehouse approval evidence contradicts release readiness.",
                        "source_refs": ["chunk-warehouse-1"],
                        "source_node_id": "entity:warehouse-approval",
                        "target_node_id": "opinion:release-readiness",
                    },
                ],
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

    assert decision.affected_relation_ids == ["relation-warehouse-approval"]
    assert decision.affected_relation_kinds == ["contradicts"]
    assert decision.relation_source_refs == ["chunk-warehouse-1"]
    assert decision.strategy_change["affected_relation_ids"] == ["relation-warehouse-approval"]


def test_report_replan_engine_round_trips_top_level_strategy_change_fields() -> None:
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
                "trigger_rule_ids": ["review-rule:warehouse-approval"],
                "trigger_context": {
                    "review_window": "weekly",
                    "source_scope": "industry-1",
                },
            },
            "activation": {
                "contradiction_count": 2,
            },
            "strategy_change_context": {
                "trigger_rule_ids": ["activation-rule:contradiction-repeat"],
                "trigger_context": {
                    "strategic_uncertainty_ids": ["uncertainty-warehouse-approval"],
                },
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

    payload = _payload(decision)
    round_tripped = type(decision).model_validate(payload)

    assert getattr(round_tripped, "trigger_context", None) == {
        "review_window": "weekly",
        "source_scope": "industry-1",
        "strategic_uncertainty_ids": ["uncertainty-warehouse-approval"],
        "trigger_families": ["repeated_evidence_contradiction"],
    }
    assert _top_level_strategy_change(round_tripped) == {
        "decision_kind": "strategy_review_required",
        "trigger_family": "repeated_evidence_contradiction",
        "trigger_rule_ids": [
            "review-rule:warehouse-approval",
            "activation-rule:contradiction-repeat",
        ],
        "trigger_context": {
            "review_window": "weekly",
            "source_scope": "industry-1",
            "strategic_uncertainty_ids": ["uncertainty-warehouse-approval"],
            "trigger_families": ["repeated_evidence_contradiction"],
        },
        "rationale": "Repeated contradiction spans synthesis, activation, and report evidence.",
        "trigger_evidence": [
            {
                "topic_key": "warehouse-approval",
                "source_families": ["synthesis", "activation", "report"],
                "repeat_count": 3,
                "source_report_ids": ["report-6"],
                "summary": "Repeated contradiction spans synthesis, activation, and report evidence.",
            },
        ],
    }


def test_report_replan_engine_returns_clear_when_synthesis_is_missing() -> None:
    engine = ReportReplanEngine()

    decision = engine.compile(None)

    assert decision.status == "clear"
    assert decision.strategy_change_decision is None
    assert decision.reason_ids == []
    assert decision.directives == []
