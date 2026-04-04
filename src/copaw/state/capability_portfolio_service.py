# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter
from typing import Any


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class CapabilityPortfolioService:
    def __init__(
        self,
        *,
        donor_service: object,
        candidate_service: object,
        skill_trial_service: object,
        skill_lifecycle_decision_service: object,
        density_budget: int = 3,
    ) -> None:
        self._donor_service = donor_service
        self._candidate_service = candidate_service
        self._skill_trial_service = skill_trial_service
        self._skill_lifecycle_decision_service = skill_lifecycle_decision_service
        self._density_budget = max(1, int(density_budget))

    def summarize_portfolio(self) -> dict[str, Any]:
        donors = list(getattr(self._donor_service, "list_donors")())
        source_profiles = list(getattr(self._donor_service, "list_source_profiles")())
        candidates = list(getattr(self._candidate_service, "list_candidates")(limit=None))
        trials = list(getattr(self._skill_trial_service, "list_trials")(limit=None))
        decisions = list(
            getattr(self._skill_lifecycle_decision_service, "list_decisions")(limit=None),
        )
        candidate_by_id = {
            _string(getattr(item, "candidate_id", None)): item
            for item in candidates
            if _string(getattr(item, "candidate_id", None))
        }
        trial_donor_ids: set[str] = set()
        donor_success: Counter[str] = Counter()
        donor_failure: Counter[str] = Counter()
        for item in trials:
            candidate = candidate_by_id.get(_string(getattr(item, "candidate_id", None)))
            donor_id = _string(getattr(candidate, "donor_id", None))
            if donor_id is None:
                continue
            trial_donor_ids.add(donor_id)
            donor_success[donor_id] += int(getattr(item, "success_count", 0) or 0)
            donor_failure[donor_id] += int(getattr(item, "failure_count", 0) or 0)
        donor_retire: Counter[str] = Counter()
        donor_replace: Counter[str] = Counter()
        for item in decisions:
            candidate = candidate_by_id.get(_string(getattr(item, "candidate_id", None)))
            donor_id = _string(getattr(candidate, "donor_id", None))
            if donor_id is None:
                continue
            decision_kind = _string(getattr(item, "decision_kind", None)) or ""
            if decision_kind == "retire":
                donor_retire[donor_id] += 1
            if decision_kind in {"replace_existing", "rollback"}:
                donor_replace[donor_id] += 1
        candidate_donor_ids = {
            _string(getattr(item, "donor_id", None))
            for item in candidates
            if (
                _string(getattr(item, "donor_id", None)) is not None
                and str(getattr(item, "status", "") or "").strip().lower() != "active"
            )
        }
        active_donor_ids = {
            _string(getattr(item, "donor_id", None))
            for item in candidates
            if (
                _string(getattr(item, "donor_id", None)) is not None
                and str(getattr(item, "status", "") or "").strip().lower() == "active"
            )
        }
        trusted_source_count = sum(
            1
            for item in source_profiles
            if str(getattr(item, "trust_posture", "") or "").strip().lower() == "trusted"
        )
        watchlist_source_count = sum(
            1
            for item in source_profiles
            if str(getattr(item, "trust_posture", "") or "").strip().lower() == "watchlist"
        )
        degraded_donor_ids = {
            donor_id
            for donor_id in trial_donor_ids
            if donor_failure[donor_id] > donor_success[donor_id]
        }
        degraded_donor_ids.update(donor_replace)
        scope_counter: Counter[str] = Counter()
        for item in candidates:
            if str(getattr(item, "status", "") or "").strip().lower() == "retired":
                continue
            target_scope = _string(getattr(item, "target_scope", None)) or "global"
            target_role_id = _string(getattr(item, "target_role_id", None)) or "*"
            target_seat_ref = _string(getattr(item, "target_seat_ref", None)) or "*"
            scope_counter[f"{target_scope}:{target_role_id}:{target_seat_ref}"] += 1
        over_budget_scopes = [
            {"scope_key": key, "count": count}
            for key, count in scope_counter.items()
            if count > self._density_budget
        ]
        planning_actions: list[dict[str, Any]] = []
        if len(candidate_donor_ids) > len(trial_donor_ids):
            planning_actions.append(
                {
                    "action": "run_scoped_trial",
                    "summary": "At least one candidate donor still lacks a scoped trial.",
                },
            )
        if donor_replace:
            planning_actions.append(
                {
                    "action": "review_replacement_pressure",
                    "summary": "Some donors have replacement or rollback pressure.",
                },
            )
        if donor_retire:
            planning_actions.append(
                {
                    "action": "review_retirement_pressure",
                    "summary": "A donor is pending retirement governance.",
                },
            )
        if over_budget_scopes:
            planning_actions.append(
                {
                    "action": "compact_over_budget_scope",
                    "summary": "One or more scopes exceeded donor density budget.",
                },
            )
        return {
            "donor_count": len(donors),
            "active_donor_count": len(active_donor_ids),
            "candidate_donor_count": len(candidate_donor_ids),
            "trial_donor_count": len(trial_donor_ids),
            "trusted_source_count": trusted_source_count,
            "watchlist_source_count": watchlist_source_count,
            "degraded_donor_count": len(degraded_donor_ids),
            "replace_pressure_count": len(donor_replace),
            "retire_pressure_count": len(donor_retire),
            "over_budget_scope_count": len(over_budget_scopes),
            "over_budget_scopes": over_budget_scopes,
            "planning_actions": planning_actions,
        }

    def get_runtime_portfolio_summary(self) -> dict[str, Any]:
        return self.summarize_portfolio()
