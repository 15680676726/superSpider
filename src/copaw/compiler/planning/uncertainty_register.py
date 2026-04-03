# -*- coding: utf-8 -*-
"""Helpers for derived uncertainty register payloads."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="python")
        return payload if isinstance(payload, dict) else {}
    return {}


def _mapping_list(value: object | None) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    items: list[dict[str, Any]] = []
    for entry in value:
        payload = _mapping(entry)
        if payload:
            items.append(payload)
    return items


def _unique_strings(*values: object) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        if isinstance(value, str):
            candidates = [value]
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            candidates = list(value)
        else:
            candidates = []
        for candidate in candidates:
            text = _string(candidate)
            if text is None or text in seen:
                continue
            seen.add(text)
            items.append(text)
    return items


def _signal_slug(value: object | None) -> str:
    return str(value or "").strip().lower().replace("_", "-").replace(" ", "-")


def _trigger_family_from_signal(value: object | None) -> str:
    normalized = _signal_slug(value)
    if "target-miss" in normalized or "lane-miss" in normalized:
        return "target_miss"
    if "confidence-drop" in normalized or "confidence-collapse" in normalized:
        return "confidence_collapse"
    if "blocker" in normalized:
        return "repeated_blocker"
    return "review_rule"


def build_uncertainty_register_payload(
    *,
    strategic_uncertainties: Sequence[object],
    lane_budgets: Sequence[object],
    strategy_trigger_rules: Sequence[object],
    source: str,
) -> dict[str, Any]:
    uncertainty_items = _mapping_list(strategic_uncertainties)
    lane_budget_items = _mapping_list(lane_budgets)
    trigger_rule_items = _mapping_list(strategy_trigger_rules)
    known_rule_ids = {
        rule_id
        for rule_id in (_string(item.get("rule_id")) for item in trigger_rule_items)
        if rule_id is not None
    }
    for uncertainty in uncertainty_items:
        uncertainty_id = _string(uncertainty.get("uncertainty_id"))
        if uncertainty_id is None:
            continue
        for raw_signal in _unique_strings(uncertainty.get("escalate_when")):
            slug = _signal_slug(raw_signal)
            rule_id = f"uncertainty:{uncertainty_id}:{slug}"
            if rule_id in known_rule_ids:
                continue
            known_rule_ids.add(rule_id)
            trigger_rule_items.append(
                {
                    "rule_id": rule_id,
                    "source_type": "uncertainty_escalation",
                    "source_ref": uncertainty_id,
                    "trigger_family": _trigger_family_from_signal(raw_signal),
                    "uncertainty_ids": [uncertainty_id],
                },
            )
    if not uncertainty_items and not lane_budget_items and not trigger_rule_items:
        return {}

    trigger_rules_by_uncertainty: dict[str, list[dict[str, Any]]] = {}
    for rule in trigger_rule_items:
        matched_uncertainty_ids = _unique_strings(
            rule.get("source_ref"),
            rule.get("uncertainty_ids"),
        )
        for uncertainty_id in matched_uncertainty_ids:
            trigger_rules_by_uncertainty.setdefault(uncertainty_id, []).append(dict(rule))

    items: list[dict[str, Any]] = []
    for uncertainty in uncertainty_items:
        uncertainty_id = _string(uncertainty.get("uncertainty_id"))
        matched_rules = trigger_rules_by_uncertainty.get(uncertainty_id or "", [])
        items.append(
            {
                "uncertainty_id": uncertainty_id,
                "statement": _string(uncertainty.get("statement")) or "",
                "scope": _string(uncertainty.get("scope")) or "strategy",
                "impact_level": _string(uncertainty.get("impact_level")) or "medium",
                "current_confidence": float(uncertainty.get("current_confidence") or 0.0),
                "review_by_cycle": _string(uncertainty.get("review_by_cycle")),
                "escalate_when": _unique_strings(uncertainty.get("escalate_when")),
                "trigger_rule_ids": _unique_strings(
                    [rule.get("rule_id") for rule in matched_rules],
                ),
                "trigger_families": sorted(
                    _unique_strings([rule.get("trigger_family") for rule in matched_rules]),
                ),
            },
        )

    return {
        "is_truth_store": False,
        "source": source,
        "durable_source": "strategy-memory",
        "summary": {
            "uncertainty_count": len(uncertainty_items),
            "lane_budget_count": len(lane_budget_items),
            "trigger_rule_count": len(trigger_rule_items),
            "review_cycle_ids": sorted(
                _unique_strings([item.get("review_by_cycle") for item in uncertainty_items]),
            ),
            "trigger_families": sorted(
                _unique_strings([rule.get("trigger_family") for rule in trigger_rule_items]),
            ),
        },
        "items": items,
    }


__all__ = ["build_uncertainty_register_payload"]
