# -*- coding: utf-8 -*-
"""Refresh Buddy domain capability truth from canonical planning/runtime signals."""
from __future__ import annotations

from datetime import datetime, timezone

from .buddy_domain_capability import (
    BuddyDomainCapabilitySignals,
    derive_capability_metrics,
)
from .buddy_execution_carrier import build_buddy_domain_control_thread_id
from ..state import BuddyDomainCapabilityRecord
from ..state.repositories_buddy import SqliteBuddyDomainCapabilityRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BuddyDomainCapabilityGrowthService:
    def __init__(
        self,
        *,
        domain_capability_repository: SqliteBuddyDomainCapabilityRepository,
        industry_instance_repository: object | None = None,
        operating_lane_service: object | None = None,
        backlog_service: object | None = None,
        operating_cycle_service: object | None = None,
        assignment_service: object | None = None,
        agent_report_service: object | None = None,
    ) -> None:
        self._domain_capability_repository = domain_capability_repository
        self._industry_instance_repository = industry_instance_repository
        self._operating_lane_service = operating_lane_service
        self._backlog_service = backlog_service
        self._operating_cycle_service = operating_cycle_service
        self._assignment_service = assignment_service
        self._agent_report_service = agent_report_service

    def refresh_active_domain_capability(
        self,
        *,
        profile_id: str,
    ) -> BuddyDomainCapabilityRecord | None:
        active = self._domain_capability_repository.get_active_domain_capability(profile_id)
        if active is None:
            return None
        active = self._backfill_legacy_binding(profile_id=profile_id, active=active)
        signals = self._collect_signals(active=active)
        if signals is None:
            return active
        metrics = derive_capability_metrics(signals)
        previous_score = int(active.capability_score or 0)
        next_progress_at = active.last_progress_at
        if metrics.capability_score != previous_score or next_progress_at is None:
            next_progress_at = _utc_now().isoformat()
        updated = active.model_copy(
            update={
                "strategy_score": metrics.strategy_score,
                "execution_score": metrics.execution_score,
                "evidence_score": metrics.evidence_score,
                "stability_score": metrics.stability_score,
                "capability_score": metrics.capability_score,
                "evolution_stage": metrics.evolution_stage,
                "knowledge_value": metrics.knowledge_value,
                "skill_value": metrics.skill_value,
                "completed_support_runs": metrics.completed_support_runs,
                "completed_assisted_closures": metrics.completed_assisted_closures,
                "evidence_count": metrics.evidence_count,
                "report_count": metrics.report_count,
                "last_progress_at": next_progress_at,
            }
        )
        return self._domain_capability_repository.upsert_domain_capability(updated)

    def _collect_signals(
        self,
        *,
        active: BuddyDomainCapabilityRecord,
    ) -> BuddyDomainCapabilitySignals | None:
        get_instance = getattr(self._industry_instance_repository, "get_instance", None)
        if not callable(get_instance):
            return None
        instance_id = str(active.industry_instance_id or "").strip()
        if not instance_id:
            return None
        instance = get_instance(instance_id)
        if instance is None:
            return None
        lanes = self._list_records(
            self._operating_lane_service,
            "list_lanes",
            industry_instance_id=instance_id,
            status="active",
            limit=None,
        )
        backlog_items = self._list_records(
            self._backlog_service,
            "list_items",
            industry_instance_id=instance_id,
            limit=None,
        )
        cycles = self._list_records(
            self._operating_cycle_service,
            "list_cycles",
            industry_instance_id=instance_id,
            limit=None,
        )
        assignments = self._list_records(
            self._assignment_service,
            "list_assignments",
            industry_instance_id=instance_id,
            limit=None,
        )
        reports = self._list_records(
            self._agent_report_service,
            "list_reports",
            industry_instance_id=instance_id,
            limit=None,
        )
        active_assignment_count = sum(
            1
            for assignment in assignments
            if str(getattr(assignment, "status", "") or "") in {"queued", "running", "waiting-report"}
        )
        completed_assignment_count = sum(
            1
            for assignment in assignments
            if str(getattr(assignment, "status", "") or "") == "completed"
        )
        completed_report_count = sum(
            1
            for report in reports
            if str(getattr(report, "result", "") or "").lower() in {"completed", "success"}
            or str(getattr(report, "status", "") or "").lower() == "completed"
        )
        completed_cycle_count = sum(
            1
            for cycle in cycles
            if str(getattr(cycle, "status", "") or "") == "completed"
        )
        evidence_ids: set[str] = set()
        for collection in (backlog_items, assignments, reports):
            for record in collection:
                for evidence_id in list(getattr(record, "evidence_ids", []) or []):
                    normalized = str(evidence_id or "").strip()
                    if normalized:
                        evidence_ids.add(normalized)
        return BuddyDomainCapabilitySignals(
            has_active_instance=str(getattr(instance, "status", "") or "") == "active",
            lane_count=len(lanes),
            backlog_count=len(backlog_items),
            cycle_count=len(cycles),
            completed_cycle_count=completed_cycle_count,
            has_current_cycle=bool(getattr(instance, "current_cycle_id", None)),
            assignment_count=len(assignments),
            active_assignment_count=active_assignment_count,
            completed_assignment_count=completed_assignment_count,
            report_count=len(reports),
            completed_report_count=completed_report_count,
            evidence_count=len(evidence_ids),
        )

    def _backfill_legacy_binding(
        self,
        *,
        profile_id: str,
        active: BuddyDomainCapabilityRecord,
    ) -> BuddyDomainCapabilityRecord:
        if str(active.industry_instance_id or "").strip():
            return active
        get_instance = getattr(self._industry_instance_repository, "get_instance", None)
        if not callable(get_instance):
            return active
        legacy_instance_id = f"buddy:{profile_id}"
        if get_instance(legacy_instance_id) is None:
            return active
        updated = active.model_copy(
            update={
                "industry_instance_id": legacy_instance_id,
                "control_thread_id": str(active.control_thread_id or "").strip()
                or build_buddy_domain_control_thread_id(instance_id=legacy_instance_id),
            },
        )
        return self._domain_capability_repository.upsert_domain_capability(updated)

    @staticmethod
    def _list_records(service: object | None, method_name: str, **kwargs) -> list[object]:
        method = getattr(service, method_name, None)
        if not callable(method):
            return []
        result = method(**kwargs)
        return list(result or [])


__all__ = ["BuddyDomainCapabilityGrowthService"]
