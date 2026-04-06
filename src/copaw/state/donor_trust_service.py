# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models_capability_evolution import CapabilityDonorTrustRecord


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class DonorTrustService:
    def __init__(
        self,
        *,
        donor_service: object,
        skill_trial_service: object | None = None,
        skill_lifecycle_decision_service: object | None = None,
    ) -> None:
        self._donor_service = donor_service
        self._skill_trial_service = skill_trial_service
        self._skill_lifecycle_decision_service = skill_lifecycle_decision_service

    def list_trust_records(self, *, limit: int | None = None) -> list[CapabilityDonorTrustRecord]:
        lister = getattr(self._donor_service, "list_trust_records", None)
        if not callable(lister):
            return []
        return list(lister(limit=limit))

    def refresh_trust_records(self) -> list[CapabilityDonorTrustRecord]:
        trial_lister = getattr(self._skill_trial_service, "list_trials", None)
        decision_lister = getattr(self._skill_lifecycle_decision_service, "list_decisions", None)
        donors = getattr(self._donor_service, "list_donors", lambda limit=None: [])(limit=None)
        existing = {
            record.donor_id: record
            for record in self.list_trust_records(limit=None)
            if _string(record.donor_id) is not None
        }
        trial_totals: dict[str, dict[str, int | str | None]] = defaultdict(
            lambda: {
                "trial_success_count": 0,
                "trial_failure_count": 0,
                "underperformance_count": 0,
                "last_trial_verdict": None,
                "compatibility_block_count": 0,
                "compatibility_bridge_count": 0,
                "last_compatibility_status": None,
            }
        )
        if callable(trial_lister):
            for item in trial_lister(limit=None):
                donor_id = _string(getattr(item, "donor_id", None))
                if donor_id is None:
                    continue
                payload = trial_totals[donor_id]
                success_count = int(getattr(item, "success_count", None) or 0)
                failure_count = int(getattr(item, "failure_count", None) or 0)
                payload["trial_success_count"] = int(payload["trial_success_count"]) + success_count
                payload["trial_failure_count"] = int(payload["trial_failure_count"]) + failure_count
                if failure_count > success_count:
                    payload["underperformance_count"] = int(payload["underperformance_count"]) + 1
                payload["last_trial_verdict"] = _string(getattr(item, "verdict", None))
                compatibility_status = _string(getattr(item, "compatibility_status", None))
                if compatibility_status is not None:
                    if compatibility_status.startswith("blocked_"):
                        payload["compatibility_block_count"] = (
                            int(payload["compatibility_block_count"]) + 1
                        )
                    if compatibility_status == "compatible_via_bridge":
                        payload["compatibility_bridge_count"] = (
                            int(payload["compatibility_bridge_count"]) + 1
                        )
                    payload["last_compatibility_status"] = compatibility_status
        decision_totals: dict[str, dict[str, int | str | None]] = defaultdict(
            lambda: {
                "rollback_count": 0,
                "replacement_pressure_count": 0,
                "retirement_count": 0,
                "last_decision_kind": None,
                "compatibility_block_count": 0,
                "compatibility_bridge_count": 0,
                "last_compatibility_status": None,
            }
        )
        if callable(decision_lister):
            for item in decision_lister(limit=None):
                donor_id = _string(getattr(item, "donor_id", None))
                if donor_id is None:
                    continue
                payload = decision_totals[donor_id]
                decision_kind = (_string(getattr(item, "decision_kind", None)) or "").lower()
                if decision_kind == "rollback":
                    payload["rollback_count"] = int(payload["rollback_count"]) + 1
                if decision_kind in {"replace_existing", "rollback"}:
                    payload["replacement_pressure_count"] = (
                        int(payload["replacement_pressure_count"]) + 1
                    )
                if decision_kind == "retire":
                    payload["retirement_count"] = int(payload["retirement_count"]) + 1
                payload["last_decision_kind"] = decision_kind or None
                compatibility_status = _string(getattr(item, "compatibility_status", None))
                if compatibility_status is not None:
                    if compatibility_status.startswith("blocked_"):
                        payload["compatibility_block_count"] = (
                            int(payload["compatibility_block_count"]) + 1
                        )
                    if compatibility_status == "compatible_via_bridge":
                        payload["compatibility_bridge_count"] = (
                            int(payload["compatibility_bridge_count"]) + 1
                        )
                    payload["last_compatibility_status"] = compatibility_status

        updater = getattr(self._donor_service, "upsert_trust_record", None)
        refreshed: list[CapabilityDonorTrustRecord] = []
        for donor in donors:
            donor_id = _string(getattr(donor, "donor_id", None))
            if donor_id is None:
                continue
            current = existing.get(donor_id) or CapabilityDonorTrustRecord(donor_id=donor_id)
            trial_payload = trial_totals[donor_id]
            decision_payload = decision_totals[donor_id]
            trust_status = "observing"
            if int(decision_payload["retirement_count"]) > 0:
                trust_status = "retired"
            elif (
                int(trial_payload["compatibility_block_count"]) > 0
                or int(decision_payload["compatibility_block_count"]) > 0
            ):
                trust_status = "blocked"
            elif int(decision_payload["rollback_count"]) > 0 or int(trial_payload["underperformance_count"]) > 0:
                trust_status = "degraded"
            elif int(trial_payload["trial_success_count"]) > 0 and int(trial_payload["trial_failure_count"]) == 0:
                trust_status = "trusted"
            record = current.model_copy(
                update={
                    "source_profile_id": _string(getattr(donor, "metadata", {}).get("source_profile_id"))
                    or current.source_profile_id,
                    "last_candidate_id": current.last_candidate_id,
                    "last_package_id": current.last_package_id,
                    "last_canonical_package_id": _string(getattr(donor, "canonical_package_id", None))
                    or current.last_canonical_package_id,
                    "trust_status": trust_status,
                    "trial_success_count": int(trial_payload["trial_success_count"]),
                    "trial_failure_count": int(trial_payload["trial_failure_count"]),
                    "underperformance_count": int(trial_payload["underperformance_count"]),
                    "rollback_count": int(decision_payload["rollback_count"]),
                    "replacement_pressure_count": int(decision_payload["replacement_pressure_count"]),
                    "retirement_count": int(decision_payload["retirement_count"]),
                    "last_trial_verdict": _string(trial_payload["last_trial_verdict"]),
                    "last_decision_kind": _string(decision_payload["last_decision_kind"]),
                    "metadata": {
                        **dict(current.metadata or {}),
                        "last_compatibility_status": (
                            _string(decision_payload["last_compatibility_status"])
                            or _string(trial_payload["last_compatibility_status"])
                        ),
                        "compatibility_block_count": (
                            int(trial_payload["compatibility_block_count"])
                            + int(decision_payload["compatibility_block_count"])
                        ),
                        "compatibility_bridge_count": (
                            int(trial_payload["compatibility_bridge_count"])
                            + int(decision_payload["compatibility_bridge_count"])
                        ),
                    },
                }
            )
            if callable(updater):
                updater(record)
            refreshed.append(record)
        return refreshed

    def summarize_trust(self) -> dict[str, Any]:
        records = self.list_trust_records(limit=None)
        by_status: dict[str, int] = {}
        for item in records:
            trust_status = _string(getattr(item, "trust_status", None)) or "unknown"
            by_status[trust_status] = by_status.get(trust_status, 0) + 1
        return {
            "trust_record_count": len(records),
            "trusted_count": by_status.get("trusted", 0),
            "degraded_count": by_status.get("degraded", 0),
            "retired_count": by_status.get("retired", 0),
            "by_status": by_status,
        }


__all__ = ["DonorTrustService"]
