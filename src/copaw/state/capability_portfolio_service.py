# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter
from typing import Any


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

    def _list_from_service(
        self,
        service: object | None,
        method_name: str,
    ) -> list[object]:
        method = getattr(service, method_name, None)
        if not callable(method):
            return []
        return list(method(limit=None))

    def _list_candidates(self) -> list[object]:
        return self._list_from_service(self._candidate_service, "list_candidates")

    def _list_donors(self) -> list[object]:
        return self._list_from_service(self._donor_service, "list_donors")

    def _list_packages(self) -> list[object]:
        return self._list_from_service(self._donor_service, "list_packages")

    def _list_source_profiles(self) -> list[object]:
        return self._list_from_service(self._donor_service, "list_source_profiles")

    def _list_trust_records(self) -> list[object]:
        return self._list_from_service(self._donor_service, "list_trust_records")

    def _list_trials(self) -> list[object]:
        return self._list_from_service(self._skill_trial_service, "list_trials")

    def _list_decisions(self) -> list[object]:
        return self._list_from_service(
            self._skill_lifecycle_decision_service,
            "list_decisions",
        )

    def _candidate_is_fallback_only(self, candidate: object) -> bool:
        source_kind = (_string(getattr(candidate, "candidate_source_kind", None)) or "").lower()
        ingestion_mode = (_string(getattr(candidate, "ingestion_mode", None)) or "").lower()
        return source_kind == "local_authored" or ingestion_mode == "baseline-import"

    def _partition_candidates(self) -> tuple[list[object], list[object]]:
        governed: list[object] = []
        fallback_only: list[object] = []
        for item in self._list_candidates():
            if self._candidate_is_fallback_only(item):
                fallback_only.append(item)
            else:
                governed.append(item)
        return governed, fallback_only

    def _candidate_is_active(self, candidate: object) -> bool:
        status = (_string(getattr(candidate, "status", None)) or "").lower()
        stage = (_string(getattr(candidate, "lifecycle_stage", None)) or "").lower()
        return status == "active" or stage == "active"

    def _candidate_is_trial(self, candidate: object) -> bool:
        status = (_string(getattr(candidate, "status", None)) or "").lower()
        stage = (_string(getattr(candidate, "lifecycle_stage", None)) or "").lower()
        return status == "trial" or stage == "trial"

    def _candidate_is_retired(self, candidate: object) -> bool:
        status = (_string(getattr(candidate, "status", None)) or "").lower()
        stage = (_string(getattr(candidate, "lifecycle_stage", None)) or "").lower()
        return status == "retired" or stage == "retired"

    def _build_scope_breakdown(
        self,
        candidates: list[object],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        groups: dict[str, list[object]] = {}
        for item in candidates:
            if self._candidate_is_retired(item):
                continue
            target_scope = _string(getattr(item, "target_scope", None)) or "global"
            target_role_id = _string(getattr(item, "target_role_id", None)) or "*"
            target_seat_ref = _string(getattr(item, "target_seat_ref", None)) or "*"
            scope_key = f"{target_scope}:{target_role_id}:{target_seat_ref}"
            groups.setdefault(scope_key, []).append(item)

        breakdown: list[dict[str, Any]] = []
        over_budget: list[dict[str, Any]] = []
        for scope_key, items in sorted(groups.items()):
            donor_ids = {
                donor_id
                for donor_id in (_string(getattr(item, "donor_id", None)) for item in items)
                if donor_id is not None
            }
            source_kind_count = dict(
                sorted(
                    Counter(
                        (_string(getattr(item, "candidate_source_kind", None)) or "unknown")
                        for item in items
                    ).items(),
                ),
            )
            first = items[0]
            summary = {
                "scope_key": scope_key,
                "target_scope": _string(getattr(first, "target_scope", None)) or "global",
                "target_role_id": _string(getattr(first, "target_role_id", None)),
                "target_seat_ref": _string(getattr(first, "target_seat_ref", None)),
                "donor_count": len(donor_ids),
                "candidate_count": len(items),
                "active_candidate_count": sum(
                    1 for item in items if self._candidate_is_active(item)
                ),
                "trial_candidate_count": sum(
                    1 for item in items if self._candidate_is_trial(item)
                ),
                "source_kind_count": source_kind_count,
            }
            breakdown.append(summary)
            if len(donor_ids) > self._density_budget:
                over_budget.append(
                    {
                        **summary,
                        "budget_limit": self._density_budget,
                        "count": len(donor_ids),
                    },
                )

        breakdown.sort(
            key=lambda item: (-_int(item.get("donor_count")), str(item.get("scope_key") or "")),
        )
        return breakdown, over_budget

    @staticmethod
    def _planning_actions_from_governance_actions(
        actions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "action": _string(item.get("action")) or "unknown",
                "summary": _string(item.get("summary")) or "",
            }
            for item in actions
            if _string(item.get("action"))
        ]

    @staticmethod
    def _action_route(action: str) -> str:
        if action == "run_scoped_trial":
            return "/api/runtime-center/capabilities/trials"
        if action in {"review_replacement_pressure", "review_retirement_pressure"}:
            return "/api/runtime-center/capabilities/lifecycle-decisions"
        return "/api/runtime-center/capabilities/portfolio"

    def _build_governance_actions(
        self,
        *,
        governed_candidates: list[object],
        candidate_donor_ids: set[str],
        trial_donor_ids: set[str],
        replace_pressure_ids: set[str],
        retire_pressure_ids: set[str],
        over_budget_scopes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        missing_trial_donor_ids = sorted(candidate_donor_ids - trial_donor_ids)
        if missing_trial_donor_ids:
            actions.append(
                {
                    "action": "run_scoped_trial",
                    "priority": "medium",
                    "summary": "At least one governed donor still lacks a scoped trial.",
                    "route": self._action_route("run_scoped_trial"),
                    "donor_ids": missing_trial_donor_ids,
                    "donor_count": len(missing_trial_donor_ids),
                },
            )
        if replace_pressure_ids:
            actions.append(
                {
                    "action": "review_replacement_pressure",
                    "priority": "high",
                    "summary": "Some governed donors carry replacement or rollback pressure.",
                    "route": self._action_route("review_replacement_pressure"),
                    "donor_ids": sorted(replace_pressure_ids),
                    "donor_count": len(replace_pressure_ids),
                },
            )
        if retire_pressure_ids:
            actions.append(
                {
                    "action": "review_retirement_pressure",
                    "priority": "high",
                    "summary": "A governed donor is pending retirement governance.",
                    "route": self._action_route("review_retirement_pressure"),
                    "donor_ids": sorted(retire_pressure_ids),
                    "donor_count": len(retire_pressure_ids),
                },
            )
        for scope in over_budget_scopes:
            actions.append(
                {
                    "action": "compact_over_budget_scope",
                    "priority": "high",
                    "summary": "One or more governed scopes exceeded donor density budget.",
                    "route": self._action_route("compact_over_budget_scope"),
                    "scope_key": _string(scope.get("scope_key")) or "unknown-scope",
                    "target_scope": _string(scope.get("target_scope")) or "global",
                    "target_role_id": _string(scope.get("target_role_id")),
                    "target_seat_ref": _string(scope.get("target_seat_ref")),
                    "budget_limit": _int(scope.get("budget_limit")) or self._density_budget,
                    "donor_count": _int(scope.get("donor_count")),
                    "candidate_count": _int(scope.get("candidate_count")),
                },
            )
        return actions

    def summarize_portfolio(self) -> dict[str, Any]:
        donors = self._list_donors()
        source_profiles = self._list_source_profiles()
        candidates = self._list_candidates()
        trials = self._list_trials()
        decisions = self._list_decisions()

        candidate_by_id = {
            candidate_id: item
            for item in candidates
            if (candidate_id := _string(getattr(item, "candidate_id", None))) is not None
        }
        active_donor_ids = {
            donor_id
            for item in candidates
            if self._candidate_is_active(item)
            and (donor_id := _string(getattr(item, "donor_id", None))) is not None
        }
        candidate_donor_ids = {
            donor_id
            for item in candidates
            if not self._candidate_is_active(item)
            and (donor_id := _string(getattr(item, "donor_id", None))) is not None
        }
        trial_donor_ids: set[str] = {
            donor_id
            for item in candidates
            if self._candidate_is_trial(item)
            and (donor_id := _string(getattr(item, "donor_id", None))) is not None
        }
        donor_success: Counter[str] = Counter()
        donor_failure: Counter[str] = Counter()
        for item in trials:
            candidate = candidate_by_id.get(_string(getattr(item, "candidate_id", None)) or "")
            donor_id = _string(getattr(candidate, "donor_id", None)) if candidate is not None else None
            if donor_id is None:
                continue
            trial_donor_ids.add(donor_id)
            donor_success[donor_id] += _int(getattr(item, "success_count", None))
            donor_failure[donor_id] += _int(getattr(item, "failure_count", None))

        donor_replace: set[str] = set()
        donor_retire: set[str] = set()
        for item in decisions:
            candidate = candidate_by_id.get(_string(getattr(item, "candidate_id", None)) or "")
            donor_id = _string(getattr(candidate, "donor_id", None)) if candidate is not None else None
            if donor_id is None:
                continue
            decision_kind = (_string(getattr(item, "decision_kind", None)) or "").lower()
            if decision_kind == "retire":
                donor_retire.add(donor_id)
            if decision_kind in {"replace_existing", "rollback"}:
                donor_replace.add(donor_id)

        degraded_donor_ids = {
            donor_id
            for donor_id in trial_donor_ids
            if donor_failure[donor_id] > donor_success[donor_id]
        }
        degraded_donor_ids.update(donor_replace)

        _scope_breakdown, over_budget_scopes = self._build_scope_breakdown(candidates)
        governance_actions = self._build_governance_actions(
            governed_candidates=candidates,
            candidate_donor_ids=candidate_donor_ids,
            trial_donor_ids=trial_donor_ids,
            replace_pressure_ids=donor_replace,
            retire_pressure_ids=donor_retire,
            over_budget_scopes=over_budget_scopes,
        )
        planning_actions = self._planning_actions_from_governance_actions(
            governance_actions,
        )

        return {
            "donor_count": len(donors),
            "active_donor_count": len(active_donor_ids),
            "candidate_donor_count": len(candidate_donor_ids),
            "trial_donor_count": len(trial_donor_ids),
            "trusted_source_count": sum(
                1
                for item in source_profiles
                if (_string(getattr(item, "trust_posture", None)) or "").lower() == "trusted"
            ),
            "watchlist_source_count": sum(
                1
                for item in source_profiles
                if (_string(getattr(item, "trust_posture", None)) or "").lower() == "watchlist"
            ),
            "degraded_donor_count": len(degraded_donor_ids),
            "replace_pressure_count": len(donor_replace),
            "retire_pressure_count": len(donor_retire),
            "over_budget_scope_count": len(over_budget_scopes),
            "over_budget_scopes": over_budget_scopes,
            "governance_actions": governance_actions,
            "planning_actions": planning_actions,
        }

    def get_runtime_portfolio_summary(self) -> dict[str, Any]:
        governed_candidates, fallback_candidates = self._partition_candidates()
        donors = self._list_donors()
        packages = self._list_packages()
        source_profiles = self._list_source_profiles()
        trust_records = self._list_trust_records()
        trials = self._list_trials()
        decisions = self._list_decisions()

        governed_donor_ids = {
            donor_id
            for donor_id in (_string(getattr(item, "donor_id", None)) for item in governed_candidates)
            if donor_id is not None
        }
        governed_source_profile_ids = {
            source_profile_id
            for source_profile_id in (
                _string(getattr(item, "source_profile_id", None))
                for item in governed_candidates
            )
            if source_profile_id is not None
        }
        governed_package_ids = {
            package_id
            for package_id in (_string(getattr(item, "package_id", None)) for item in governed_candidates)
            if package_id is not None
        }

        governed_source_profiles = [
            item
            for item in source_profiles
            if _string(getattr(item, "source_profile_id", None)) in governed_source_profile_ids
        ]
        governed_packages = [
            item
            for item in packages
            if _string(getattr(item, "package_id", None)) in governed_package_ids
        ]
        governed_trust_records = [
            item
            for item in trust_records
            if _string(getattr(item, "donor_id", None)) in governed_donor_ids
        ]

        candidate_by_id = {
            candidate_id: item
            for item in governed_candidates
            if (candidate_id := _string(getattr(item, "candidate_id", None))) is not None
        }
        active_donor_ids = {
            donor_id
            for item in governed_candidates
            if self._candidate_is_active(item)
            and (donor_id := _string(getattr(item, "donor_id", None))) is not None
        }
        candidate_donor_ids = {
            donor_id
            for item in governed_candidates
            if not self._candidate_is_active(item)
            and not self._candidate_is_retired(item)
            and (donor_id := _string(getattr(item, "donor_id", None))) is not None
        }
        trial_donor_ids = {
            donor_id
            for item in governed_candidates
            if self._candidate_is_trial(item)
            and (donor_id := _string(getattr(item, "donor_id", None))) is not None
        }

        donor_success: Counter[str] = Counter()
        donor_failure: Counter[str] = Counter()
        for item in trials:
            candidate = candidate_by_id.get(_string(getattr(item, "candidate_id", None)) or "")
            donor_id = _string(getattr(candidate, "donor_id", None)) if candidate is not None else None
            if donor_id is None:
                continue
            trial_donor_ids.add(donor_id)
            donor_success[donor_id] += _int(getattr(item, "success_count", None))
            donor_failure[donor_id] += _int(getattr(item, "failure_count", None))

        replace_pressure_ids: set[str] = set()
        retire_pressure_ids: set[str] = set()
        for item in decisions:
            candidate = candidate_by_id.get(_string(getattr(item, "candidate_id", None)) or "")
            donor_id = _string(getattr(candidate, "donor_id", None)) if candidate is not None else None
            if donor_id is None:
                continue
            decision_kind = (_string(getattr(item, "decision_kind", None)) or "").lower()
            if decision_kind == "retire":
                retire_pressure_ids.add(donor_id)
            if decision_kind in {"replace_existing", "rollback"}:
                replace_pressure_ids.add(donor_id)

        degraded_donor_ids = {
            donor_id
            for donor_id in trial_donor_ids
            if donor_failure[donor_id] > donor_success[donor_id]
        }
        degraded_donor_ids.update(replace_pressure_ids)
        for item in governed_trust_records:
            donor_id = _string(getattr(item, "donor_id", None))
            if donor_id is None:
                continue
            success_count = _int(getattr(item, "trial_success_count", None))
            failure_count = _int(getattr(item, "trial_failure_count", None))
            rollback_count = _int(getattr(item, "rollback_count", None))
            retirement_count = _int(getattr(item, "retirement_count", None))
            if failure_count > success_count or rollback_count > 0 or retirement_count > 0:
                degraded_donor_ids.add(donor_id)

        scope_breakdown, over_budget_scopes = self._build_scope_breakdown(governed_candidates)
        governance_actions = self._build_governance_actions(
            governed_candidates=governed_candidates,
            candidate_donor_ids=candidate_donor_ids,
            trial_donor_ids=trial_donor_ids,
            replace_pressure_ids=replace_pressure_ids,
            retire_pressure_ids=retire_pressure_ids,
            over_budget_scopes=over_budget_scopes,
        )
        planning_actions = self._planning_actions_from_governance_actions(
            governance_actions,
        )

        return {
            "donor_count": len(governed_donor_ids),
            "active_donor_count": len(active_donor_ids),
            "candidate_donor_count": len(candidate_donor_ids),
            "trial_donor_count": len(trial_donor_ids),
            "trusted_source_count": sum(
                1
                for item in governed_source_profiles
                if (_string(getattr(item, "trust_posture", None)) or "").lower() == "trusted"
            ),
            "watchlist_source_count": sum(
                1
                for item in governed_source_profiles
                if (_string(getattr(item, "trust_posture", None)) or "").lower() == "watchlist"
            ),
            "degraded_donor_count": len(degraded_donor_ids),
            "replace_pressure_count": len(replace_pressure_ids),
            "retire_pressure_count": len(retire_pressure_ids),
            "over_budget_scope_count": len(over_budget_scopes),
            "over_budget_scopes": over_budget_scopes,
            "fallback_only_candidate_count": len(fallback_candidates),
            "scope_breakdown": scope_breakdown,
            "governance_actions": governance_actions,
            "planning_actions": planning_actions,
            "package_kind_count": dict(
                sorted(
                    Counter(
                        (_string(getattr(item, "package_kind", None)) or "unknown")
                        for item in governed_packages
                    ).items(),
                ),
            ),
            "candidate_source_kind_count": dict(
                sorted(
                    Counter(
                        (_string(getattr(item, "candidate_source_kind", None)) or "unknown")
                        for item in governed_candidates
                    ).items(),
                ),
            ),
            "target_scope_count": dict(
                sorted(
                    Counter(
                        (_string(getattr(item, "target_scope", None)) or "global")
                        for item in governed_candidates
                    ).items(),
                ),
            ),
            "routes": {
                "portfolio": "/api/runtime-center/capabilities/portfolio",
                "donors": "/api/runtime-center/capabilities/donors",
                "source_profiles": "/api/runtime-center/capabilities/source-profiles",
                "discovery": "/api/runtime-center/capabilities/discovery",
                "trials": "/api/runtime-center/capabilities/trials",
                "lifecycle_decisions": "/api/runtime-center/capabilities/lifecycle-decisions",
            },
        }

    def get_runtime_discovery_summary(self) -> dict[str, Any]:
        governed_candidates, fallback_candidates = self._partition_candidates()
        source_profiles = self._list_source_profiles()
        governed_source_profile_ids = {
            source_profile_id
            for source_profile_id in (
                _string(getattr(item, "source_profile_id", None))
                for item in governed_candidates
            )
            if source_profile_id is not None
        }
        fallback_source_profile_ids = {
            source_profile_id
            for source_profile_id in (
                _string(getattr(item, "source_profile_id", None))
                for item in fallback_candidates
            )
            if source_profile_id is not None
        }
        governed_source_profiles = [
            item
            for item in source_profiles
            if _string(getattr(item, "source_profile_id", None)) in governed_source_profile_ids
        ]
        fallback_source_profiles = [
            item
            for item in source_profiles
            if _string(getattr(item, "source_profile_id", None)) in fallback_source_profile_ids
        ]
        if not governed_source_profiles and not fallback_source_profiles:
            return {}

        active_source_count = sum(
            1 for item in governed_source_profiles if bool(getattr(item, "active", True))
        )
        trusted_source_count = sum(
            1
            for item in governed_source_profiles
            if (_string(getattr(item, "trust_posture", None)) or "").lower() == "trusted"
        )
        watchlist_source_count = sum(
            1
            for item in governed_source_profiles
            if (_string(getattr(item, "trust_posture", None)) or "").lower() == "watchlist"
        )
        degraded_components: list[dict[str, Any]] = []
        status = "ready"
        if active_source_count <= 0:
            status = "degraded"
            degraded_components.append(
                {
                    "component": "source-availability",
                    "status": "degraded",
                    "summary": "No governed donor discovery source is currently active.",
                },
            )
        elif trusted_source_count <= 0 and watchlist_source_count > 0:
            status = "degraded"
            degraded_components.append(
                {
                    "component": "source-trust",
                    "status": "degraded",
                    "summary": "Discovery is currently relying on watchlist donor sources only.",
                },
            )

        return {
            "status": status,
            "summary": (
                "Governed donor discovery is running with trusted sources available."
                if status == "ready"
                else "Governed donor discovery is available, but current source posture is degraded."
            ),
            "source_profile_count": len(governed_source_profiles),
            "active_source_count": active_source_count,
            "trusted_source_count": trusted_source_count,
            "watchlist_source_count": watchlist_source_count,
            "fallback_only_source_count": len(fallback_source_profiles),
            "by_source_kind": dict(
                sorted(
                    Counter(
                        (_string(getattr(item, "source_kind", None)) or "unknown")
                        for item in governed_source_profiles
                    ).items(),
                ),
            ),
            "trust_posture_count": dict(
                sorted(
                    Counter(
                        (_string(getattr(item, "trust_posture", None)) or "unknown")
                        for item in governed_source_profiles
                    ).items(),
                ),
            ),
            "degraded_components": degraded_components,
            "routes": {
                "portfolio": "/api/runtime-center/capabilities/portfolio",
                "source_profiles": "/api/runtime-center/capabilities/source-profiles",
                "discovery": "/api/runtime-center/capabilities/discovery",
            },
        }
