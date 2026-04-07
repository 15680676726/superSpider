# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import (
    PredictionOptimizationCaseBaseline,
    PredictionOptimizationCaseChallenger,
    PredictionOptimizationCaseDonorTrustImpact,
    PredictionOptimizationCaseLifecycleDecision,
    PredictionOptimizationCasePlanningImpact,
    PredictionOptimizationCaseProjection,
    PredictionOptimizationCaseTrialScope,
)
from .optimization_evaluator import OptimizationEvaluator

_WRITEBACK_TARGETS = [
    "planning_constraints",
    "donor_trust",
    "capability_portfolio_pressure",
    "future_discovery_pressure",
    "strategy_or_lane_reopen",
]


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
        if isinstance(payload, Mapping):
            return dict(payload)
    return {}


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(*values: object) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        if value is None:
            continue
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            text = _string(candidate)
            if text is None:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            items.append(text)
    return items


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


def _latest_decision(
    *,
    skill_lifecycle_decision_service: object | None,
    candidate_id: str | None,
) -> dict[str, Any]:
    normalized_candidate_id = _string(candidate_id)
    if normalized_candidate_id is None:
        return {}
    lister = getattr(skill_lifecycle_decision_service, "list_decisions", None)
    if not callable(lister):
        return {}
    decisions = list(lister(candidate_id=normalized_candidate_id, limit=1))
    if not decisions:
        return {}
    return _mapping(decisions[0])


def _portfolio_summary(
    capability_portfolio_service: object | None,
) -> dict[str, Any]:
    getter = getattr(capability_portfolio_service, "get_runtime_portfolio_summary", None)
    if callable(getter):
        return _mapping(getter())
    getter = getattr(capability_portfolio_service, "summarize_portfolio", None)
    if callable(getter):
        return _mapping(getter())
    return {}


def build_optimization_case_projection(
    *,
    case: object,
    recommendation_view: object,
    capability_candidate_service: object | None = None,
    skill_trial_service: object | None = None,
    skill_lifecycle_decision_service: object | None = None,
    capability_donor_service: object | None = None,
    capability_portfolio_service: object | None = None,
) -> PredictionOptimizationCaseProjection:
    case_payload = _mapping(case)
    recommendation_view_payload = _mapping(recommendation_view)
    recommendation_payload = _mapping(recommendation_view_payload.get("recommendation"))
    routes = _mapping(recommendation_view_payload.get("routes"))
    metadata = _mapping(recommendation_payload.get("metadata"))
    action_payload = _mapping(recommendation_payload.get("action_payload"))

    candidate_id = _string(metadata.get("candidate_id")) or _string(action_payload.get("candidate_id"))
    candidate_getter = getattr(capability_candidate_service, "get_candidate", None)
    candidate_payload = (
        _mapping(candidate_getter(candidate_id))
        if callable(candidate_getter) and candidate_id is not None
        else {}
    )
    donor_id = (
        _string(candidate_payload.get("donor_id"))
        or _string(metadata.get("donor_id"))
        or _string(action_payload.get("donor_id"))
    )
    package_id = (
        _string(candidate_payload.get("package_id"))
        or _string(metadata.get("package_id"))
        or _string(action_payload.get("package_id"))
    )
    challenger_capability_ids = _string_list(
        candidate_payload.get("requested_capability_ids"),
        candidate_payload.get("capability_ids"),
        metadata.get("requested_capability_ids"),
        recommendation_payload.get("target_capability_ids"),
        action_payload.get("target_capability_ids"),
        action_payload.get("capability_ids"),
    )
    baseline_capability_ids = _string_list(
        metadata.get("rollback_target_ids"),
        metadata.get("replacement_target_ids"),
        action_payload.get("rollback_target_ids"),
        metadata.get("old_capability_id"),
        metadata.get("baseline_capability_ids"),
    )
    evaluator = OptimizationEvaluator(
        skill_trial_service=skill_trial_service,
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
    )
    evaluator_verdict = evaluator.evaluate_candidate(candidate_id=candidate_id)
    latest_decision = _latest_decision(
        skill_lifecycle_decision_service=skill_lifecycle_decision_service,
        candidate_id=candidate_id,
    )
    trust_payload = {}
    trust_getter = getattr(capability_donor_service, "get_trust_record", None)
    if callable(trust_getter) and donor_id is not None:
        trust_payload = _mapping(trust_getter(donor_id))
    compatibility_status = (
        _string(trust_payload.get("metadata", {}).get("last_compatibility_status"))
        if isinstance(trust_payload.get("metadata"), Mapping)
        else None
    ) or _string(latest_decision.get("compatibility_status")) or _string(
        candidate_payload.get("compatibility_status"),
    )
    scope_kind = (
        _string(metadata.get("selected_scope"))
        or _string(metadata.get("trial_scope"))
        or _string(action_payload.get("selected_scope"))
    )
    scope_ref = (
        _string(metadata.get("selected_seat_ref"))
        or _string(action_payload.get("selected_seat_ref"))
        or _string(recommendation_payload.get("target_agent_id"))
    )
    owner_agent_id = _string(recommendation_payload.get("target_agent_id")) or _string(
        case_payload.get("owner_agent_id"),
    )
    portfolio_summary = _portfolio_summary(capability_portfolio_service)
    raw_actions = list(portfolio_summary.get("planning_actions") or [])
    filtered_actions: list[dict[str, Any]] = []
    scope_key = None
    if scope_kind or scope_ref:
        scope_key = f"{scope_kind or 'unknown'}:*:{scope_ref or '*'}"
    for item in raw_actions:
        if not isinstance(item, Mapping):
            continue
        donor_ids = _string_list(item.get("donor_ids"))
        action_scope_key = _string(item.get("scope_key"))
        if donor_id and donor_id in donor_ids:
            filtered_actions.append(dict(item))
            continue
        if scope_key and action_scope_key and action_scope_key.endswith(scope_ref or ""):
            filtered_actions.append(dict(item))
    replace_pressure_count = _int(trust_payload.get("replacement_count")) or (
        1 if _string(latest_decision.get("decision_kind")) in {"replace_existing", "rollback"} else 0
    )
    retirement_count = _int(trust_payload.get("retirement_count")) or (
        1 if _string(latest_decision.get("decision_kind")) == "retire" else 0
    )
    rollback_count = _int(trust_payload.get("rollback_count")) or (
        1 if _string(latest_decision.get("decision_kind")) == "rollback" else 0
    )
    revision_pressure = evaluator_verdict.aggregate_verdict == "continue_trial"
    replacement_pressure = replace_pressure_count > 0
    retirement_pressure = retirement_count > 0
    issue_source = (
        _string(metadata.get("gap_kind"))
        or _string(case_payload.get("case_kind"))
        or _string(case_payload.get("topic_type"))
    )
    strategy_reopen_signals = _string_list(
        metadata.get("affected_lane_ids"),
        metadata.get("affected_uncertainty_ids"),
        _mapping(case_payload.get("metadata")).get("trigger_rule_ids"),
    )
    return PredictionOptimizationCaseProjection(
        issue_source=issue_source,
        discovery_case_id=_string(case_payload.get("case_id")),
        gap_kind=_string(metadata.get("gap_kind")),
        baseline=PredictionOptimizationCaseBaseline(
            candidate_id=_string(metadata.get("baseline_candidate_id")),
            capability_ids=baseline_capability_ids,
            summary=_string(metadata.get("baseline_summary"))
            or _string(metadata.get("old_capability_id"))
            or "",
        ),
        challenger=PredictionOptimizationCaseChallenger(
            candidate_id=candidate_id,
            donor_id=donor_id,
            package_id=package_id,
            capability_ids=challenger_capability_ids,
            summary=_string(recommendation_payload.get("title"))
            or _string(candidate_payload.get("summary"))
            or "",
        ),
        trial_scope=PredictionOptimizationCaseTrialScope(
            scope_kind=scope_kind,
            scope_ref=scope_ref,
            owner_agent_id=owner_agent_id,
        ),
        owner={
            "agent_id": owner_agent_id,
            "owner_scope": _string(case_payload.get("owner_scope")),
            "industry_instance_id": _string(case_payload.get("industry_instance_id")),
        },
        evaluator_verdict=evaluator_verdict,
        lifecycle_decision=PredictionOptimizationCaseLifecycleDecision(
            decision_kind=_string(latest_decision.get("decision_kind"))
            or evaluator_verdict.latest_decision_kind,
            from_stage=_string(latest_decision.get("from_stage")),
            to_stage=_string(latest_decision.get("to_stage")),
            reason=_string(latest_decision.get("reason")) or "",
            route=routes.get("decision") or "/api/runtime-center/capabilities/lifecycle-decisions",
        ),
        donor_trust_impact=PredictionOptimizationCaseDonorTrustImpact(
            donor_id=donor_id,
            trust_status=_string(trust_payload.get("trust_status"))
            or ("observing" if donor_id else None),
            replacement_pressure_count=replace_pressure_count,
            retirement_count=retirement_count,
            rollback_count=rollback_count,
            compatibility_status=compatibility_status,
        ),
        planning_impact=PredictionOptimizationCasePlanningImpact(
            planning_actions=filtered_actions,
            future_review_pressure=bool(
                replacement_pressure or retirement_pressure or revision_pressure
            ),
            replacement_pressure=replacement_pressure,
            retirement_pressure=retirement_pressure,
            revision_pressure=revision_pressure,
            strategy_reopen_signals=strategy_reopen_signals,
        ),
        rollback_route=routes.get("decision") or "/api/runtime-center/capabilities/lifecycle-decisions",
        writeback_targets=list(_WRITEBACK_TARGETS),
    )


__all__ = ["build_optimization_case_projection"]
