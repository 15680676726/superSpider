# -*- coding: utf-8 -*-
"""Translate report synthesis pressure into a stable formal replan decision."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .models import ReportReplanDecision


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: object | None) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [
        text
        for item in value
        if (text := _string(item)) is not None
    ]


def _dict_list(value: object | None) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [
        dict(item)
        for item in value
        if isinstance(item, Mapping)
    ]


def _mapping(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _unique_strings(*values: object | None) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        for text in _string_list(value):
            if text in seen:
                continue
            seen.add(text)
            items.append(text)
    return items


def _append_unique(items: list[str], *values: object | None) -> list[str]:
    return _unique_strings(items, *values)


def _first_summary(entries: Sequence[Mapping[str, Any]], *, fallback: str) -> str:
    for entry in entries:
        if (summary := _string(entry.get("summary"))) is not None:
            return summary
    return fallback


def _strategy_context(
    synthesis: Mapping[str, Any],
    raw_decision: Mapping[str, Any],
) -> dict[str, Any]:
    context = _mapping(raw_decision.get("strategy_change_context"))
    context.update(_mapping(synthesis.get("strategy_change_context")))
    return context


def _decision_summary(decision_kind: str, rationale: str) -> str:
    prefix = {
        "follow_up_backlog": "Follow-up backlog required",
        "cycle_rebalance": "Cycle rebalance required",
        "lane_reweight": "Lane reweight required",
        "strategy_review_required": "Strategy review required",
    }.get(decision_kind, "Replan decision required")
    return f"{prefix}: {rationale}"


def _set_extra_fields(
    decision: ReportReplanDecision,
    *,
    decision_kind: str,
    trigger_family: str,
) -> ReportReplanDecision:
    updates: dict[str, Any] = {}
    model_fields = getattr(type(decision), "model_fields", {})
    for field_name, field_value in {
        "decision_kind": decision_kind,
        "trigger_family": trigger_family,
    }.items():
        if field_name in model_fields:
            updates[field_name] = field_value
        else:
            object.__setattr__(decision, field_name, field_value)
    if updates:
        decision = decision.model_copy(update=updates)
    return decision


def _build_strategy_change_payload(
    *,
    decision_kind: str,
    trigger_family: str,
    rationale: str,
    trigger_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "decision_kind": decision_kind,
        "trigger_family": trigger_family,
        "rationale": rationale,
        "trigger_evidence": trigger_evidence,
    }


class ReportReplanEngine:
    """Compile report synthesis output into a typed replan surface."""

    def compile(
        self,
        synthesis: Mapping[str, Any] | None,
    ) -> ReportReplanDecision:
        if not isinstance(synthesis, Mapping):
            return ReportReplanDecision()
        raw_decision = synthesis.get("replan_decision")
        decision: ReportReplanDecision
        if isinstance(raw_decision, Mapping):
            decision = ReportReplanDecision(
                decision_id=_string(raw_decision.get("decision_id")) or "report-synthesis:clear",
                status=(
                    "needs-replan"
                    if _string(raw_decision.get("status")) == "needs-replan"
                    else "clear"
                ),
                summary=(
                    _string(raw_decision.get("summary"))
                    or "No unresolved report synthesis pressure."
                ),
                reason_ids=_string_list(raw_decision.get("reason_ids")),
                source_report_ids=_string_list(raw_decision.get("source_report_ids")),
                topic_keys=_string_list(raw_decision.get("topic_keys")),
                directives=_dict_list(synthesis.get("replan_directives")),
                recommended_actions=_dict_list(synthesis.get("recommended_actions")),
                activation=(
                    dict(synthesis.get("activation"))
                    if isinstance(synthesis.get("activation"), Mapping)
                    else {}
                ),
            )
        elif synthesis.get("needs_replan"):
            decision = ReportReplanDecision(
                decision_id="report-synthesis:needs-replan",
                status="needs-replan",
                summary=(
                    _string(synthesis.get("summary"))
                    or "Report synthesis still requires main-brain review."
                ),
                directives=_dict_list(synthesis.get("replan_directives")),
                recommended_actions=_dict_list(synthesis.get("recommended_actions")),
                activation=(
                    dict(synthesis.get("activation"))
                    if isinstance(synthesis.get("activation"), Mapping)
                    else {}
                ),
            )
        else:
            return ReportReplanDecision()

        strategy_change = self._classify_strategy_change(
            synthesis=synthesis,
            raw_decision=_mapping(raw_decision),
            decision=decision,
        )
        if strategy_change is None:
            return decision
        activation = dict(decision.activation)
        activation["strategy_change"] = strategy_change
        summary = decision.summary
        if strategy_change["decision_kind"] != "follow_up_backlog":
            summary = _decision_summary(
                str(strategy_change["decision_kind"]),
                str(strategy_change["rationale"]),
            )
        decision = decision.model_copy(
            update={
                "summary": summary,
                "source_report_ids": _append_unique(
                    list(decision.source_report_ids),
                    *(
                        item.get("source_report_ids")
                        for item in strategy_change["trigger_evidence"]
                        if isinstance(item, Mapping)
                    ),
                ),
                "topic_keys": _append_unique(
                    list(decision.topic_keys),
                    [
                        _string(item.get("topic_key"))
                        or _string(item.get("objective_key"))
                        or _string(item.get("blocker_key"))
                        or _string(item.get("uncertainty_key"))
                        for item in strategy_change["trigger_evidence"]
                        if isinstance(item, Mapping)
                    ],
                ),
                "activation": activation,
            },
        )
        return _set_extra_fields(
            decision,
            decision_kind=str(strategy_change["decision_kind"]),
            trigger_family=str(strategy_change["trigger_family"]),
        )

    def _classify_strategy_change(
        self,
        *,
        synthesis: Mapping[str, Any],
        raw_decision: Mapping[str, Any],
        decision: ReportReplanDecision,
    ) -> dict[str, Any] | None:
        if decision.status != "needs-replan":
            return None
        context = _strategy_context(synthesis, raw_decision)
        contradictions = _dict_list(
            context.get("evidence_contradictions") or context.get("repeated_contradictions"),
        )
        if contradictions:
            return _build_strategy_change_payload(
                decision_kind="strategy_review_required",
                trigger_family="repeated_evidence_contradiction",
                rationale=_first_summary(
                    contradictions,
                    fallback="Repeated contradiction across synthesis, activation, and report evidence requires strategy review.",
                ),
                trigger_evidence=contradictions,
            )
        activation = _mapping(synthesis.get("activation"))
        contradiction_count = activation.get("contradiction_count")
        if isinstance(contradiction_count, int) and contradiction_count > 0:
            contradiction_sources = ["activation"]
            latest_findings = _dict_list(synthesis.get("latest_findings"))
            report_ids = _append_unique(
                list(decision.source_report_ids),
                [item.get("report_id") for item in latest_findings],
            )
            if report_ids:
                contradiction_sources.append("report")
            if any(not reason_id.startswith("activation:") for reason_id in decision.reason_ids):
                contradiction_sources.insert(0, "synthesis")
            if len(contradiction_sources) >= 2:
                rationale = (
                    _string_list(synthesis.get("replan_reasons"))[0]
                    if _string_list(synthesis.get("replan_reasons"))
                    else "Contradictory activation and report evidence requires strategy review."
                )
                return _build_strategy_change_payload(
                    decision_kind="strategy_review_required",
                    trigger_family="repeated_evidence_contradiction",
                    rationale=rationale,
                    trigger_evidence=[
                        {
                            "contradiction_count": contradiction_count,
                            "source_families": contradiction_sources,
                            "source_report_ids": report_ids,
                            "topic_keys": list(decision.topic_keys),
                            "summary": rationale,
                        },
                    ],
                )
        uncertainty_collapses = _dict_list(
            context.get("uncertainty_collapses") or context.get("confidence_collapses"),
        )
        if uncertainty_collapses:
            return _build_strategy_change_payload(
                decision_kind="strategy_review_required",
                trigger_family="confidence_collapse_tracked_uncertainty",
                rationale=_first_summary(
                    uncertainty_collapses,
                    fallback="Confidence collapsed on a tracked uncertainty and now requires strategy review.",
                ),
                trigger_evidence=uncertainty_collapses,
            )
        assignment_misses = _dict_list(
            context.get("assignment_misses") or context.get("repeated_assignment_misses"),
        )
        if assignment_misses:
            return _build_strategy_change_payload(
                decision_kind="lane_reweight",
                trigger_family="repeated_assignment_miss_same_lane_objective",
                rationale=_first_summary(
                    assignment_misses,
                    fallback="Repeated assignment misses against the same lane objective require lane reweight.",
                ),
                trigger_evidence=assignment_misses,
            )
        repeated_blockers = _dict_list(
            context.get("repeated_blockers") or context.get("blockers_across_cycles"),
        )
        if repeated_blockers:
            return _build_strategy_change_payload(
                decision_kind="cycle_rebalance",
                trigger_family="repeated_blocker_across_cycles",
                rationale=_first_summary(
                    repeated_blockers,
                    fallback="Repeated blocker pressure across cycles requires cycle rebalance.",
                ),
                trigger_evidence=repeated_blockers,
            )
        return _build_strategy_change_payload(
            decision_kind="follow_up_backlog",
            trigger_family="local_follow_up_pressure",
            rationale=decision.summary,
            trigger_evidence=[
                {
                    "reason_ids": list(decision.reason_ids),
                    "source_report_ids": list(decision.source_report_ids),
                    "topic_keys": list(decision.topic_keys),
                    "directive_ids": _unique_strings(
                        [item.get("directive_id") for item in decision.directives],
                    ),
                    "recommended_action_ids": _unique_strings(
                        [item.get("action_id") for item in decision.recommended_actions],
                    ),
                    "summary": decision.summary,
                },
            ],
        )
