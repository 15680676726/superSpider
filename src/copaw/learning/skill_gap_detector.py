# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _float_value(value: object | None) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _int_value(value: object | None) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


class SkillGapDetector:
    def detect_runtime_pressure(
        self,
        payload: Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        raw_payload = dict(payload or {})
        failure_rate = _float_value(raw_payload.get("failure_rate"))
        manual_rate = _float_value(raw_payload.get("manual_intervention_rate"))
        blockage_rate = _float_value(raw_payload.get("workflow_blockage_rate"))
        reasons: list[str] = []
        if failure_rate >= 0.34:
            reasons.append("failure-rate")
        if manual_rate >= 0.3:
            reasons.append("human-takeover")
        if blockage_rate >= 0.25:
            reasons.append("workflow-blockage")
        if not reasons:
            return None
        return {
            "status": "pressure",
            "reasons": reasons,
            "failure_rate": round(failure_rate, 3),
            "manual_intervention_rate": round(manual_rate, 3),
            "workflow_blockage_rate": round(blockage_rate, 3),
            "pressure_score": round(max(failure_rate, manual_rate, blockage_rate), 3),
        }

    def trial_improved(
        self,
        *,
        new_stats: Mapping[str, Any] | None,
        old_stats: Mapping[str, Any] | None,
    ) -> bool:
        new_payload = dict(new_stats or {})
        old_payload = dict(old_stats or {})
        new_sample = max(
            _int_value(new_payload.get("task_count")),
            _int_value(new_payload.get("evidence_count")),
        )
        if new_sample <= 0:
            return False
        if not old_payload:
            return (
                _float_value(new_payload.get("failure_rate")) <= 0.2
                and _float_value(new_payload.get("manual_intervention_rate")) <= 0.2
            )
        new_failure = _float_value(new_payload.get("failure_rate"))
        old_failure = _float_value(old_payload.get("failure_rate"))
        new_manual = _float_value(new_payload.get("manual_intervention_rate"))
        old_manual = _float_value(old_payload.get("manual_intervention_rate"))
        new_blockage = _float_value(new_payload.get("workflow_blockage_rate"))
        old_blockage = _float_value(old_payload.get("workflow_blockage_rate"))
        return (
            new_failure <= old_failure
            and new_manual <= old_manual
            and new_blockage <= old_blockage
            and (
                old_failure - new_failure >= 0.1
                or old_manual - new_manual >= 0.1
                or old_blockage - new_blockage >= 0.1
            )
        )

    def trial_underperformed(
        self,
        *,
        new_stats: Mapping[str, Any] | None,
        old_stats: Mapping[str, Any] | None,
    ) -> bool:
        new_payload = dict(new_stats or {})
        old_payload = dict(old_stats or {})
        if not new_payload:
            return False
        if not old_payload:
            return self.detect_runtime_pressure(new_payload) is not None
        return (
            _float_value(new_payload.get("failure_rate"))
            > _float_value(old_payload.get("failure_rate"))
            or _float_value(new_payload.get("manual_intervention_rate"))
            > _float_value(old_payload.get("manual_intervention_rate"))
            or _float_value(new_payload.get("workflow_blockage_rate"))
            > _float_value(old_payload.get("workflow_blockage_rate"))
        )

    def build_reentry_summary(
        self,
        *,
        trial_summary: Mapping[str, Any] | None,
        latest_decision_kind: str | None = None,
    ) -> dict[str, Any]:
        summary = dict(trial_summary or {})
        reasons: list[str] = []
        if str(summary.get("aggregate_verdict") or "").strip().lower() == "rollback_recommended":
            reasons.append("trial-regression")
        if _int_value(summary.get("operator_intervention_count")) > 0:
            reasons.append("human-takeover")
        history = list(summary.get("history") or []) if isinstance(summary.get("history"), list) else []
        decision_kind = str(latest_decision_kind or "").strip().lower()
        if decision_kind in {"rollback", "retire"}:
            reasons.append(decision_kind)
        replacement_target_ids: list[str] = []
        for item in history:
            if not isinstance(item, Mapping):
                continue
            for value in list(item.get("replacement_target_ids") or []):
                text = str(value).strip()
                if text and text not in replacement_target_ids:
                    replacement_target_ids.append(text)
        reentry_kind = "stable"
        replacement_pressure = False
        retirement_pressure = False
        revision_pressure = False
        if decision_kind == "retire":
            reentry_kind = "retirement"
            retirement_pressure = True
        elif decision_kind in {
            "rollback",
            "replace_existing",
            "promote_to_role",
            "replacement",
        }:
            reentry_kind = "replacement"
            replacement_pressure = True
        elif reasons:
            reentry_kind = "revision"
            revision_pressure = True
        if not reasons:
            return {
                "status": "stable",
                "reasons": [],
                "reentry_kind": reentry_kind,
                "replacement_pressure": replacement_pressure,
                "retirement_pressure": retirement_pressure,
                "revision_pressure": revision_pressure,
                "replacement_target_ids": replacement_target_ids,
            }
        return {
            "status": "pressure",
            "reasons": reasons,
            "reentry_kind": reentry_kind,
            "replacement_pressure": replacement_pressure,
            "retirement_pressure": retirement_pressure,
            "revision_pressure": revision_pressure,
            "replacement_target_ids": replacement_target_ids,
        }


__all__ = ["SkillGapDetector"]
