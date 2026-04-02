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


def _mapping_dict(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _decision_kind(value: object | None) -> str | None:
    text = _string(value)
    if text in {
        "follow_up_backlog",
        "cycle_rebalance",
        "lane_reweight",
        "strategy_review_required",
        "clear",
    }:
        return text
    return None


def _unique_strings(*values: object) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        for text in _string_list(value):
            if text in seen:
                continue
            seen.add(text)
            items.append(text)
    return items


def _infer_trigger_families(
    *,
    raw_decision: dict[str, Any],
    directives: list[dict[str, Any]],
    reason_ids: list[str],
    activation: dict[str, Any],
) -> list[str]:
    families = _unique_strings(
        raw_decision.get("trigger_families"),
        [_string(item.get("pressure_kind")) or "" for item in directives],
        activation.get("strategy_change", {}).get("trigger_families"),
    )
    contradiction_count = activation.get("contradiction_count")
    if isinstance(contradiction_count, int) and contradiction_count > 0:
        families.append("contradiction")
    if any(reason_id.startswith("uncertainty:") for reason_id in reason_ids):
        families.append("confidence-drop")
    if not families and reason_ids:
        families.append("followup-pressure")
    return _unique_strings(families)


def _infer_decision_kind(
    *,
    raw_decision: dict[str, Any],
    strategy_change: dict[str, Any],
    directives: list[dict[str, Any]],
    reason_ids: list[str],
    trigger_families: list[str],
    status: str,
) -> str:
    for candidate in (
        _decision_kind(raw_decision.get("decision_kind")),
        _decision_kind(strategy_change.get("decision_kind")),
    ):
        if candidate is not None:
            return candidate
    normalized_families = {family.strip().lower() for family in trigger_families if family}
    if "confidence-drop" in normalized_families or "repeated-blocker" in normalized_families:
        return "strategy_review_required"
    if "contradiction" in normalized_families or any(
        (_string(item.get("pressure_kind")) or "") == "recommendation-mismatch"
        for item in directives
    ):
        return "cycle_rebalance"
    if "target-miss" in normalized_families or any(
        reason_id.startswith("target-miss:")
        for reason_id in reason_ids
    ):
        return "lane_reweight"
    if status == "needs-replan":
        return "follow_up_backlog"
    return "clear"


class ReportReplanEngine:
    """Compile report synthesis output into a typed replan surface."""

    def compile(
        self,
        synthesis: Mapping[str, Any] | None,
    ) -> ReportReplanDecision:
        if not isinstance(synthesis, Mapping):
            return ReportReplanDecision()
        raw_decision = synthesis.get("replan_decision")
        directives = _dict_list(synthesis.get("replan_directives"))
        recommended_actions = _dict_list(synthesis.get("recommended_actions"))
        activation = _mapping_dict(synthesis.get("activation"))
        strategy_change = _mapping_dict(activation.get("strategy_change"))
        raw_decision_mapping = _mapping_dict(raw_decision)
        status = (
            "needs-replan"
            if _string(raw_decision_mapping.get("status")) == "needs-replan"
            or bool(synthesis.get("needs_replan"))
            else "clear"
        )
        reason_ids = _string_list(raw_decision_mapping.get("reason_ids"))
        source_report_ids = _string_list(raw_decision_mapping.get("source_report_ids"))
        topic_keys = _string_list(raw_decision_mapping.get("topic_keys"))
        trigger_families = _infer_trigger_families(
            raw_decision=raw_decision_mapping,
            directives=directives,
            reason_ids=reason_ids,
            activation=activation,
        )
        decision_kind = _infer_decision_kind(
            raw_decision=raw_decision_mapping,
            strategy_change=strategy_change,
            directives=directives,
            reason_ids=reason_ids,
            trigger_families=trigger_families,
            status=status,
        )
        trigger_rule_ids = _unique_strings(
            raw_decision_mapping.get("trigger_rule_ids"),
            strategy_change.get("trigger_rule_ids"),
        )
        affected_lane_ids = _unique_strings(
            raw_decision_mapping.get("affected_lane_ids"),
            strategy_change.get("affected_lane_ids"),
            [item.get("lane_id") for item in directives if _string(item.get("lane_id")) is not None],
        )
        affected_uncertainty_ids = _unique_strings(
            raw_decision_mapping.get("affected_uncertainty_ids"),
            strategy_change.get("affected_uncertainty_ids"),
            [reason_id for reason_id in reason_ids if reason_id.startswith("uncertainty:")],
        )
        activation["strategy_change"] = {
            "decision_kind": decision_kind,
            "trigger_families": trigger_families,
            "trigger_rule_ids": trigger_rule_ids,
            "affected_lane_ids": affected_lane_ids,
            "affected_uncertainty_ids": affected_uncertainty_ids,
        }
        if isinstance(raw_decision, Mapping):
            return ReportReplanDecision(
                decision_id=_string(raw_decision.get("decision_id")) or "report-synthesis:clear",
                status=status,
                decision_kind=decision_kind,
                summary=(
                    _string(raw_decision.get("summary"))
                    or "No unresolved report synthesis pressure."
                ),
                reason_ids=reason_ids,
                source_report_ids=source_report_ids,
                topic_keys=topic_keys,
                trigger_families=trigger_families,
                trigger_rule_ids=trigger_rule_ids,
                affected_lane_ids=affected_lane_ids,
                affected_uncertainty_ids=affected_uncertainty_ids,
                directives=directives,
                recommended_actions=recommended_actions,
                activation=activation,
                rationale={
                    "raw_decision": raw_decision_mapping,
                    "strategy_change": strategy_change,
                },
            )
        if synthesis.get("needs_replan"):
            return ReportReplanDecision(
                decision_id="report-synthesis:needs-replan",
                status="needs-replan",
                decision_kind=decision_kind,
                summary=(
                    _string(synthesis.get("summary"))
                    or "Report synthesis still requires main-brain review."
                ),
                trigger_families=trigger_families,
                trigger_rule_ids=trigger_rule_ids,
                affected_lane_ids=affected_lane_ids,
                affected_uncertainty_ids=affected_uncertainty_ids,
                directives=directives,
                recommended_actions=recommended_actions,
                activation=activation,
                rationale={"strategy_change": strategy_change},
            )
        return ReportReplanDecision()
