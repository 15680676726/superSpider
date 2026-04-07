# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import PredictionOptimizationCaseEvaluatorVerdict


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: object | None) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = _string(value)
    if text is None:
        return 0
    try:
        return int(text)
    except ValueError:
        return 0


class OptimizationEvaluator:
    """Small deterministic verdict wrapper over existing trial/decision truth."""

    def __init__(
        self,
        *,
        skill_trial_service: object | None = None,
        skill_lifecycle_decision_service: object | None = None,
    ) -> None:
        self._skill_trial_service = skill_trial_service
        self._skill_lifecycle_decision_service = skill_lifecycle_decision_service

    def evaluate_candidate(
        self,
        *,
        candidate_id: str | None,
    ) -> PredictionOptimizationCaseEvaluatorVerdict:
        normalized_candidate_id = _string(candidate_id)
        if normalized_candidate_id is None:
            return PredictionOptimizationCaseEvaluatorVerdict()
        summary_getter = getattr(
            self._skill_trial_service,
            "get_candidate_verdict_summary",
            None,
        )
        trial_summary = (
            _mapping(summary_getter(candidate_id=normalized_candidate_id))
            if callable(summary_getter)
            else {}
        )
        latest_decision_kind: str | None = None
        decision_lister = getattr(
            self._skill_lifecycle_decision_service,
            "list_decisions",
            None,
        )
        if callable(decision_lister):
            decisions = list(decision_lister(candidate_id=normalized_candidate_id, limit=1))
            if decisions:
                latest_decision_kind = _string(getattr(decisions[0], "decision_kind", None))
        return PredictionOptimizationCaseEvaluatorVerdict(
            aggregate_verdict=_string(trial_summary.get("aggregate_verdict")) or "no-trials",
            trial_count=_int(trial_summary.get("trial_count")),
            success_count=_int(trial_summary.get("success_count")),
            failure_count=_int(trial_summary.get("failure_count")),
            handoff_count=_int(trial_summary.get("handoff_count")),
            operator_intervention_count=_int(
                trial_summary.get("operator_intervention_count"),
            ),
            latest_decision_kind=latest_decision_kind,
        )


__all__ = ["OptimizationEvaluator"]
