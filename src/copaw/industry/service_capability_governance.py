# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import IndustrySeatCapabilityLayers

_PROTECTED_FLAGS = {
    "pinned_by_operator",
    "required_by_role_blueprint",
    "protected_from_auto_replace",
    "protected_from_auto_retire",
}
_INSTALL_LIKE_PREFIXES = ("skill:", "project:", "adapter:", "runtime:")
_CAPABILITY_PREFIXES = (
    "skill:",
    "mcp:",
    "tool:",
    "project:",
    "runtime:",
    "adapter:",
)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="python")
        if isinstance(payload, dict):
            return dict(payload)
    return {}


def _string_list(*values: object) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        items = value if isinstance(value, (list, tuple, set)) else [value]
        for item in items:
            text = _string(item)
            if text is None:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            merged.append(text)
    return merged


def _capability_kind(capability_id: str) -> str:
    normalized = capability_id.strip().lower()
    for prefix in _CAPABILITY_PREFIXES:
        if normalized.startswith(prefix):
            return prefix[:-1]
    return "unknown"


def _is_install_like(capability_id: str) -> bool:
    normalized = capability_id.strip().lower()
    return any(normalized.startswith(prefix) for prefix in _INSTALL_LIKE_PREFIXES)


def _build_candidate_capability_ids(candidate: object) -> list[str]:
    metadata = _mapping(getattr(candidate, "metadata", None))
    capability_ids = _string_list(
        metadata.get("mount_id"),
        metadata.get("capability_id"),
        metadata.get("capability_ids"),
        getattr(candidate, "proposed_skill_name", None),
    )
    source_ref = _string(getattr(candidate, "candidate_source_ref", None))
    if source_ref is not None and any(
        source_ref.lower().startswith(prefix) for prefix in _CAPABILITY_PREFIXES
    ):
        capability_ids = _string_list(capability_ids, source_ref)
    return capability_ids


def _candidate_is_retired(candidate: object) -> bool:
    status = (_string(getattr(candidate, "status", None)) or "").lower()
    stage = (_string(getattr(candidate, "lifecycle_stage", None)) or "").lower()
    return status == "retired" or stage == "retired"


def _candidate_is_mount_ready(candidate: object) -> bool:
    stage = (_string(getattr(candidate, "lifecycle_stage", None)) or "").lower()
    status = (_string(getattr(candidate, "status", None)) or "").lower()
    return stage in {"baseline", "trial", "active"} or status in {"trial", "active"}


@dataclass(frozen=True, slots=True)
class CapabilityGovernanceSnapshot:
    layers_payload: dict[str, Any]
    governance_result: dict[str, Any]


class IndustryCapabilityGovernanceService:
    def __init__(
        self,
        *,
        candidate_service: object | None = None,
        skill_trial_service: object | None = None,
        skill_lifecycle_decision_service: object | None = None,
        capability_portfolio_service: object | None = None,
        role_skill_budget: int = 4,
        seat_skill_budget: int = 3,
        mcp_budget: int = 2,
        overlap_budget: int = 0,
        overlap_score_threshold: float = 0.85,
    ) -> None:
        self._candidate_service = candidate_service
        self._skill_trial_service = skill_trial_service
        self._skill_lifecycle_decision_service = skill_lifecycle_decision_service
        self._capability_portfolio_service = capability_portfolio_service
        self._role_skill_budget = max(1, int(role_skill_budget))
        self._seat_skill_budget = max(1, int(seat_skill_budget))
        self._mcp_budget = max(1, int(mcp_budget))
        self._overlap_budget = max(0, int(overlap_budget))
        self._overlap_score_threshold = max(0.0, float(overlap_score_threshold))

    def _list_from_service(self, service: object | None, method_name: str) -> list[object]:
        method = getattr(service, method_name, None)
        if not callable(method):
            return []
        return list(method(limit=None))

    def _list_candidates(self) -> list[object]:
        return self._list_from_service(self._candidate_service, "list_candidates")

    def _list_trials(self) -> list[object]:
        return self._list_from_service(self._skill_trial_service, "list_trials")

    def _list_decisions(self) -> list[object]:
        return self._list_from_service(
            self._skill_lifecycle_decision_service,
            "list_decisions",
        )

    @staticmethod
    def _candidate_matches_scope(
        candidate: object,
        *,
        target_role_id: str | None,
        target_seat_ref: str | None,
        selected_scope: str,
    ) -> bool:
        candidate_scope = (_string(getattr(candidate, "target_scope", None)) or "global").lower()
        candidate_role_id = _string(getattr(candidate, "target_role_id", None))
        candidate_seat_ref = _string(getattr(candidate, "target_seat_ref", None))
        if candidate_role_id is not None and target_role_id is not None and candidate_role_id != target_role_id:
            return False
        if candidate_seat_ref is not None and target_seat_ref is not None and candidate_seat_ref != target_seat_ref:
            return False
        if target_seat_ref is not None and candidate_seat_ref is None and candidate_scope in {"seat", "session"}:
            return False
        if target_role_id is None and candidate_role_id is not None and target_seat_ref is None:
            return False
        if selected_scope == "session" and candidate_scope == "global":
            return True
        return True

    def _scope_candidates(
        self,
        *,
        target_role_id: str | None,
        target_seat_ref: str | None,
        selected_scope: str,
    ) -> list[object]:
        scoped: list[object] = []
        for candidate in self._list_candidates():
            if _candidate_is_retired(candidate):
                continue
            if not self._candidate_matches_scope(
                candidate,
                target_role_id=target_role_id,
                target_seat_ref=target_seat_ref,
                selected_scope=selected_scope,
            ):
                continue
            scoped.append(candidate)
        return scoped

    def resolve_replacement_pressure(
        self,
        *,
        replacement_target_ids: list[str] | None,
        target_role_id: str | None,
        target_seat_ref: str | None,
        selected_scope: str,
    ) -> dict[str, Any]:
        requested_replacement_target_ids = _string_list(replacement_target_ids)
        protected_by_capability: dict[str, dict[str, Any]] = {}
        for candidate in self._scope_candidates(
            target_role_id=target_role_id,
            target_seat_ref=target_seat_ref,
            selected_scope=selected_scope,
        ):
            protection_flags = sorted(
                {
                    flag
                    for flag in _string_list(getattr(candidate, "protection_flags", None))
                    if flag in _PROTECTED_FLAGS
                },
            )
            if not protection_flags:
                continue
            for capability_id in _build_candidate_capability_ids(candidate):
                protected_by_capability.setdefault(
                    capability_id,
                    {
                        "capability_id": capability_id,
                        "candidate_id": _string(getattr(candidate, "candidate_id", None)),
                        "protection_flags": protection_flags,
                        "ingestion_mode": _string(getattr(candidate, "ingestion_mode", None)),
                    },
                )
        blocked = [
            capability_id
            for capability_id in requested_replacement_target_ids
            if capability_id in protected_by_capability
        ]
        allowed = [
            capability_id
            for capability_id in requested_replacement_target_ids
            if capability_id not in protected_by_capability
        ]
        return {
            "requested_replacement_target_ids": requested_replacement_target_ids,
            "allowed_replacement_target_ids": allowed,
            "blocked_replacement_target_ids": blocked,
            "blocked_replacement_details": [
                protected_by_capability[capability_id]
                for capability_id in blocked
            ],
            "protected_baseline_capability_ids": blocked,
        }

    def _resolve_overlap_summary(
        self,
        *,
        scope_candidates: list[object],
    ) -> dict[str, Any]:
        grouped: dict[str, list[str]] = {}
        for candidate in scope_candidates:
            candidate_id = _string(getattr(candidate, "candidate_id", None))
            if candidate_id is None:
                continue
            keys = _string_list(
                getattr(candidate, "canonical_package_id", None),
                getattr(candidate, "equivalence_class", None),
                getattr(candidate, "donor_id", None),
            )
            for key in keys:
                grouped.setdefault(key, []).append(candidate_id)
        overlap_groups = [
            sorted(set(candidate_ids))
            for candidate_ids in grouped.values()
            if len(set(candidate_ids)) > 1
        ]
        overlap_candidate_ids = _string_list(*overlap_groups)
        scored_overlap_ids = [
            _string(getattr(candidate, "candidate_id", None))
            for candidate in scope_candidates
            if getattr(candidate, "capability_overlap_score", None) is not None
            and float(getattr(candidate, "capability_overlap_score", None) or 0.0)
            >= self._overlap_score_threshold
        ]
        overlap_candidate_ids = _string_list(overlap_candidate_ids, scored_overlap_ids)
        count = len(overlap_candidate_ids)
        return {
            "limit": self._overlap_budget,
            "count": count,
            "over_budget": count > self._overlap_budget,
            "candidate_ids": overlap_candidate_ids,
            "group_count": len(overlap_groups),
        }

    def _resolve_install_discipline(
        self,
        *,
        scope_candidates: list[object],
        candidate_id: str | None,
        selected_scope: str,
        requested_replacement_target_ids: list[str],
        trial_capability_ids: list[str],
    ) -> dict[str, Any]:
        selected_candidate = next(
            (
                candidate
                for candidate in scope_candidates
                if _string(getattr(candidate, "candidate_id", None)) == candidate_id
            ),
            None,
        )
        if selected_candidate is None and trial_capability_ids:
            selected_candidate = next(
                (
                    candidate
                    for candidate in scope_candidates
                    if bool(
                        set(_build_candidate_capability_ids(candidate))
                        & set(trial_capability_ids)
                    )
                ),
                None,
            )
        if selected_candidate is not None and _candidate_is_mount_ready(selected_candidate):
            preferred_action = "mount_existing_candidate"
            reason = "A governed candidate already exists and should be mounted into the selected scope."
        else:
            identity_keys = _string_list(
                getattr(selected_candidate, "canonical_package_id", None)
                if selected_candidate is not None
                else None,
                getattr(selected_candidate, "equivalence_class", None)
                if selected_candidate is not None
                else None,
                getattr(selected_candidate, "candidate_source_lineage", None)
                if selected_candidate is not None
                else None,
            )
            reusable = any(
                _candidate_is_mount_ready(candidate)
                and _string(getattr(candidate, "candidate_id", None)) != candidate_id
                and bool(
                    set(
                        _string_list(
                            getattr(candidate, "canonical_package_id", None),
                            getattr(candidate, "equivalence_class", None),
                            getattr(candidate, "candidate_source_lineage", None),
                        ),
                    )
                    & set(identity_keys)
                )
                for candidate in scope_candidates
            )
            if reusable:
                preferred_action = "reuse_existing_candidate"
                reason = "A healthy governed package already exists for the same normalized donor identity."
            elif requested_replacement_target_ids:
                preferred_action = "replace_existing_capability"
                reason = "Lifecycle apply should replace an existing capability instead of reinstalling a fresh donor."
            else:
                preferred_action = "fresh_install"
                reason = "No healthy governed package is available yet, so fresh install is the remaining path."
        return {
            "preferred_action": preferred_action,
            "selected_scope": selected_scope,
            "reason": reason,
            "fresh_install_required": preferred_action == "fresh_install",
        }

    def build_runtime_governance_result(
        self,
        *,
        layers: IndustrySeatCapabilityLayers,
        current_capability_trial: dict[str, Any] | None,
        target_role_id: str | None,
        target_seat_ref: str | None,
        selected_scope: str,
        candidate_id: str | None,
    ) -> dict[str, Any]:
        scope_candidates = self._scope_candidates(
            target_role_id=target_role_id,
            target_seat_ref=target_seat_ref,
            selected_scope=selected_scope,
        )
        replacement_pressure = self.resolve_replacement_pressure(
            replacement_target_ids=_mapping(current_capability_trial).get(
                "replacement_target_ids",
            ),
            target_role_id=target_role_id,
            target_seat_ref=target_seat_ref,
            selected_scope=selected_scope,
        )
        role_skill_capability_ids = [
            capability_id
            for capability_id in layers.role_prototype_capability_ids
            if _is_install_like(capability_id)
        ]
        seat_skill_capability_ids = [
            capability_id
            for capability_id in layers.seat_instance_capability_ids
            if _is_install_like(capability_id)
        ]
        mcp_capability_ids = [
            capability_id
            for capability_id in layers.merged_capability_ids()
            if _capability_kind(capability_id) == "mcp"
        ]
        overlap = self._resolve_overlap_summary(scope_candidates=scope_candidates)
        install_discipline = self._resolve_install_discipline(
            scope_candidates=scope_candidates,
            candidate_id=candidate_id,
            selected_scope=selected_scope,
            requested_replacement_target_ids=replacement_pressure[
                "requested_replacement_target_ids"
            ],
            trial_capability_ids=_string_list(
                _mapping(current_capability_trial).get("capability_ids"),
            ),
        )
        decisions = [
            decision
            for decision in self._list_decisions()
            if _string(getattr(decision, "candidate_id", None)) == candidate_id
        ]
        trials = [
            trial
            for trial in self._list_trials()
            if _string(getattr(trial, "candidate_id", None)) == candidate_id
        ]
        budgets = {
            "role_skill": {
                "limit": self._role_skill_budget,
                "count": len(role_skill_capability_ids),
                "over_budget": len(role_skill_capability_ids) > self._role_skill_budget,
                "capability_ids": role_skill_capability_ids,
            },
            "seat_skill": {
                "limit": self._seat_skill_budget,
                "count": len(seat_skill_capability_ids),
                "over_budget": len(seat_skill_capability_ids) > self._seat_skill_budget,
                "capability_ids": seat_skill_capability_ids,
            },
            "mcp": {
                "limit": self._mcp_budget,
                "count": len(mcp_capability_ids),
                "over_budget": len(mcp_capability_ids) > self._mcp_budget,
                "capability_ids": mcp_capability_ids,
            },
        }
        actions: list[dict[str, Any]] = []
        if budgets["role_skill"]["over_budget"]:
            actions.append(
                {
                    "action": "compact_role_skill_budget",
                    "priority": "high",
                    "budget_limit": self._role_skill_budget,
                    "count": budgets["role_skill"]["count"],
                },
            )
        if budgets["seat_skill"]["over_budget"]:
            actions.append(
                {
                    "action": "compact_seat_skill_budget",
                    "priority": "high",
                    "budget_limit": self._seat_skill_budget,
                    "count": budgets["seat_skill"]["count"],
                },
            )
        if budgets["mcp"]["over_budget"]:
            actions.append(
                {
                    "action": "compact_mcp_budget",
                    "priority": "high",
                    "budget_limit": self._mcp_budget,
                    "count": budgets["mcp"]["count"],
                },
            )
        if overlap["over_budget"]:
            actions.append(
                {
                    "action": "compact_overlap_budget",
                    "priority": "high",
                    "count": overlap["count"],
                    "candidate_ids": list(overlap["candidate_ids"]),
                },
            )
        if replacement_pressure["blocked_replacement_target_ids"]:
            actions.append(
                {
                    "action": "review_protected_replacement",
                    "priority": "high",
                    "capability_ids": list(
                        replacement_pressure["blocked_replacement_target_ids"],
                    ),
                },
            )
        return {
            "status": (
                "guarded"
                if actions or decisions or trials
                else "ready"
            ),
            "source": "runtime-capability-layers+normalized-candidate-truth",
            "budgets": budgets,
            "overlap": overlap,
            "replacement_pressure": replacement_pressure,
            "protection": {
                "protected_baseline_capability_ids": list(
                    replacement_pressure["protected_baseline_capability_ids"],
                ),
                "blocked_replacement_details": list(
                    replacement_pressure["blocked_replacement_details"],
                ),
            },
            "install_discipline": install_discipline,
            "trial_count": len(trials),
            "lifecycle_decision_count": len(decisions),
            "actions": actions,
        }

    def recompose_runtime_capability_layers(
        self,
        *,
        role_prototype_capability_ids: list[str] | None,
        seat_instance_capability_ids: list[str] | None,
        cycle_delta_capability_ids: list[str] | None,
        session_overlay_capability_ids: list[str] | None,
        current_capability_trial: dict[str, Any] | None,
        target_role_id: str | None,
        target_seat_ref: str | None,
        selected_scope: str | None = None,
        candidate_id: str | None = None,
    ) -> CapabilityGovernanceSnapshot:
        trial_payload = _mapping(current_capability_trial)
        resolved_scope = (
            _string(selected_scope)
            or _string(trial_payload.get("selected_scope"))
            or "seat"
        )
        role_capability_ids = _string_list(role_prototype_capability_ids)
        seat_capability_ids = _string_list(seat_instance_capability_ids)
        cycle_capability_ids = _string_list(cycle_delta_capability_ids)
        session_capability_ids = _string_list(session_overlay_capability_ids)
        trial_capability_ids = _string_list(trial_payload.get("capability_ids"))
        if resolved_scope == "session":
            session_capability_ids = _string_list(
                session_capability_ids,
                trial_capability_ids,
            )
        elif resolved_scope in {"seat", "agent"}:
            seat_capability_ids = _string_list(
                seat_capability_ids,
                trial_capability_ids,
            )
        replacement_pressure = self.resolve_replacement_pressure(
            replacement_target_ids=trial_payload.get("replacement_target_ids"),
            target_role_id=target_role_id,
            target_seat_ref=target_seat_ref,
            selected_scope=resolved_scope,
        )
        effective_capability_ids = [
            capability_id
            for capability_id in _string_list(
                role_capability_ids,
                seat_capability_ids,
                cycle_capability_ids,
                session_capability_ids,
            )
            if capability_id not in replacement_pressure["allowed_replacement_target_ids"]
        ]
        layers = IndustrySeatCapabilityLayers(
            role_prototype_capability_ids=role_capability_ids,
            seat_instance_capability_ids=seat_capability_ids,
            cycle_delta_capability_ids=cycle_capability_ids,
            session_overlay_capability_ids=session_capability_ids,
            effective_capability_ids=effective_capability_ids,
        )
        governance_result = self.build_runtime_governance_result(
            layers=layers,
            current_capability_trial=trial_payload,
            target_role_id=target_role_id,
            target_seat_ref=target_seat_ref,
            selected_scope=resolved_scope,
            candidate_id=_string(candidate_id) or _string(trial_payload.get("candidate_id")),
        )
        return CapabilityGovernanceSnapshot(
            layers_payload=layers.to_metadata_payload(),
            governance_result=governance_result,
        )


def resolve_industry_capability_governance_service(
    owner: object | None,
) -> IndustryCapabilityGovernanceService:
    prediction_service = getattr(owner, "_prediction_service", None)
    return IndustryCapabilityGovernanceService(
        candidate_service=(
            getattr(owner, "_capability_candidate_service", None)
            or getattr(prediction_service, "_capability_candidate_service", None)
        ),
        skill_trial_service=(
            getattr(owner, "_skill_trial_service", None)
            or getattr(prediction_service, "_skill_trial_service", None)
        ),
        skill_lifecycle_decision_service=(
            getattr(owner, "_skill_lifecycle_decision_service", None)
            or getattr(prediction_service, "_skill_lifecycle_decision_service", None)
        ),
        capability_portfolio_service=(
            getattr(owner, "_capability_portfolio_service", None)
            or getattr(prediction_service, "_capability_portfolio_service", None)
        ),
    )
