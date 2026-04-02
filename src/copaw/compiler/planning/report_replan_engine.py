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


class ReportReplanEngine:
    """Compile report synthesis output into a typed replan surface."""

    def compile(
        self,
        synthesis: Mapping[str, Any] | None,
    ) -> ReportReplanDecision:
        if not isinstance(synthesis, Mapping):
            return ReportReplanDecision()
        raw_decision = synthesis.get("replan_decision")
        if isinstance(raw_decision, Mapping):
            return ReportReplanDecision(
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
        if synthesis.get("needs_replan"):
            return ReportReplanDecision(
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
        return ReportReplanDecision()
