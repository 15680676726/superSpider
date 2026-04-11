# -*- coding: utf-8 -*-
"""Refresh Buddy domain capability truth from canonical planning/runtime facts."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .buddy_domain_capability import (
    buddy_specialist_allowed_capabilities,
    buddy_specialist_preferred_capability_families,
    derive_buddy_domain_key,
    resolve_stage_transition,
)
from .buddy_execution_carrier import (
    EXECUTION_CORE_ROLE_ID,
    build_buddy_domain_control_thread_id,
)
from ..industry.identity import normalize_industry_role_id
from ..industry.identity import EXECUTION_CORE_AGENT_ID
from ..industry.models import IndustryRoleBlueprint, IndustryTeamBlueprint
from ..state import BuddyDomainCapabilityRecord
from ..state.repositories_buddy import SqliteBuddyDomainCapabilityRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _string(value: object | None) -> str | None:
    text = str(value or "").strip()
    return text or None


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
        return self._resolve_active_domain_capability(
            profile_id=profile_id,
            persist=True,
            repair_bindings=True,
        )

    def project_active_domain_capability(
        self,
        *,
        profile_id: str,
    ) -> BuddyDomainCapabilityRecord | None:
        return self._resolve_active_domain_capability(
            profile_id=profile_id,
            persist=False,
            repair_bindings=False,
        )

    def _resolve_active_domain_capability(
        self,
        *,
        profile_id: str,
        persist: bool,
        repair_bindings: bool,
    ) -> BuddyDomainCapabilityRecord | None:
        active = self._domain_capability_repository.get_active_domain_capability(profile_id)
        if active is None:
            return None
        active = self._backfill_legacy_binding(
            profile_id=profile_id,
            active=active,
            persist=persist,
        )
        if repair_bindings:
            self._repair_legacy_execution_binding(active=active)
        facts = self._collect_growth_facts(active=active)
        if facts is None:
            return active
        if persist and self._should_refresh_progress(active=active, facts=facts):
            facts["last_progress_at"] = _utc_now().isoformat()
        else:
            facts["last_progress_at"] = active.last_progress_at
        updated = active.model_copy(update=facts)
        if not persist:
            return updated
        return self._domain_capability_repository.upsert_domain_capability(updated)

    def _collect_growth_facts(
        self,
        *,
        active: BuddyDomainCapabilityRecord,
    ) -> dict[str, Any] | None:
        get_instance = getattr(self._industry_instance_repository, "get_instance", None)
        if not callable(get_instance):
            return None
        instance_id = str(active.industry_instance_id or "").strip()
        if not instance_id:
            return None
        if get_instance(instance_id) is None:
            return None
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
        return self._build_growth_facts(
            assignments=assignments,
            reports=reports,
            previous_stage=self._normalize_stage(active.evolution_stage),
        )

    def _build_growth_facts(
        self,
        *,
        assignments: list[object],
        reports: list[object],
        previous_stage: str,
    ) -> dict[str, Any]:
        reports_by_id = {
            str(getattr(report, "id", "") or "").strip(): report
            for report in reports
            if str(getattr(report, "id", "") or "").strip()
        }
        reports_by_assignment: dict[str, list[object]] = {}
        for report in reports:
            assignment_id = str(getattr(report, "assignment_id", "") or "").strip()
            if assignment_id:
                reports_by_assignment.setdefault(assignment_id, []).append(report)

        valid_closure_count = 0
        valid_cycle_ids: set[str] = set()
        valid_report_ids: set[str] = set()
        evidence_ids: set[str] = set()
        settled_assignments: list[object] = []
        for assignment in assignments:
            status = self._normalize_assignment_status(assignment)
            if status in {"completed", "failed", "cancelled"}:
                settled_assignments.append(assignment)
            if status != "completed":
                continue
            report = self._resolve_assignment_report(
                assignment=assignment,
                reports_by_id=reports_by_id,
                reports_by_assignment=reports_by_assignment,
            )
            if report is None or not self._is_completed_report(report):
                continue
            closure_evidence_ids = self._collect_evidence_ids(assignment, report)
            if not closure_evidence_ids:
                continue
            valid_closure_count += 1
            report_id = str(getattr(report, "id", "") or "").strip()
            if report_id:
                valid_report_ids.add(report_id)
            cycle_id = str(getattr(assignment, "cycle_id", "") or "").strip()
            if cycle_id:
                valid_cycle_ids.add(cycle_id)
            evidence_ids.update(closure_evidence_ids)

        recent_settled = settled_assignments[:30]
        settled_count = len(recent_settled)
        completed_count = sum(
            1 for assignment in recent_settled if self._normalize_assignment_status(assignment) == "completed"
        )
        failed_count = sum(
            1 for assignment in recent_settled if self._normalize_assignment_status(assignment) == "failed"
        )
        recent_completion_rate = completed_count / settled_count if settled_count else 0.0
        recent_execution_error_rate = failed_count / settled_count if settled_count else 0.0
        capability_points = valid_closure_count * 2
        distinct_settled_cycle_count = len(valid_cycle_ids)
        independent_outcome_count = len(valid_report_ids)
        evolution_stage = resolve_stage_transition(
            previous_stage=previous_stage if previous_stage in {"seed", "bonded", "capable", "seasoned", "signature"} else "seed",
            points=capability_points,
            settled_closure_count=valid_closure_count,
            independent_outcome_count=independent_outcome_count,
            recent_completion_rate=recent_completion_rate,
            recent_execution_error_rate=recent_execution_error_rate,
            distinct_settled_cycle_count=distinct_settled_cycle_count,
        )
        strategy_score = min(
            25,
            distinct_settled_cycle_count * 6
            + (3 if valid_closure_count > 0 else 0)
            + (2 if capability_points >= 40 else 0)
            + (2 if settled_count >= 10 and recent_completion_rate >= 0.85 else 0),
        )
        execution_score = min(35, valid_closure_count * 4 + min(15, completed_count))
        evidence_score = min(20, len(evidence_ids) * 2 + min(4, independent_outcome_count))
        stability_score = min(
            20,
            distinct_settled_cycle_count * 4
            + (4 if settled_count >= 10 and recent_completion_rate >= 0.85 else 0)
            + (4 if settled_count >= 10 and recent_execution_error_rate <= 0.03 else 0),
        )
        capability_score = min(
            100,
            strategy_score + execution_score + evidence_score + stability_score,
        )
        return {
            "strategy_score": strategy_score,
            "execution_score": execution_score,
            "evidence_score": evidence_score,
            "stability_score": stability_score,
            "capability_score": capability_score,
            "capability_points": capability_points,
            "settled_closure_count": valid_closure_count,
            "independent_outcome_count": independent_outcome_count,
            "recent_completion_rate": recent_completion_rate,
            "recent_execution_error_rate": recent_execution_error_rate,
            "distinct_settled_cycle_count": distinct_settled_cycle_count,
            "evolution_stage": evolution_stage,
            "knowledge_value": min(
                100,
                capability_points + distinct_settled_cycle_count * 10 + len(evidence_ids) * 2,
            ),
            "skill_value": min(100, capability_points + independent_outcome_count * 4),
            "completed_support_runs": valid_closure_count,
            "completed_assisted_closures": independent_outcome_count,
            "evidence_count": len(evidence_ids),
            "report_count": independent_outcome_count,
        }

    @staticmethod
    def _should_refresh_progress(
        *,
        active: BuddyDomainCapabilityRecord,
        facts: dict[str, Any],
    ) -> bool:
        return (
            int(active.capability_score or 0) != int(facts["capability_score"])
            or int(active.capability_points or 0) != int(facts["capability_points"])
            or int(active.settled_closure_count or 0) != int(facts["settled_closure_count"])
            or str(active.evolution_stage or "seed") != str(facts["evolution_stage"])
            or active.last_progress_at is None
        )

    @staticmethod
    def _resolve_assignment_report(
        *,
        assignment: object,
        reports_by_id: dict[str, object],
        reports_by_assignment: dict[str, list[object]],
    ) -> object | None:
        last_report_id = str(getattr(assignment, "last_report_id", "") or "").strip()
        if last_report_id and last_report_id in reports_by_id:
            return reports_by_id[last_report_id]
        assignment_id = str(getattr(assignment, "id", "") or "").strip()
        linked_reports = reports_by_assignment.get(assignment_id, [])
        return linked_reports[0] if linked_reports else None

    @staticmethod
    def _normalize_assignment_status(assignment: object) -> str:
        return str(getattr(assignment, "status", "") or "").strip().lower()

    @staticmethod
    def _is_completed_report(report: object) -> bool:
        result = str(getattr(report, "result", "") or "").strip().lower()
        status = str(getattr(report, "status", "") or "").strip().lower()
        return result in {"completed", "success"} or status == "completed"

    @staticmethod
    def _collect_evidence_ids(*records: object) -> set[str]:
        normalized_ids: set[str] = set()
        for record in records:
            for evidence_id in list(getattr(record, "evidence_ids", []) or []):
                normalized = str(evidence_id or "").strip()
                if normalized:
                    normalized_ids.add(normalized)
        return normalized_ids

    @staticmethod
    def _normalize_stage(stage: str | None) -> str:
        normalized = str(stage or "").strip()
        if normalized in {"seed", "bonded", "capable", "seasoned", "signature"}:
            return normalized
        return "seed"

    def _backfill_legacy_binding(
        self,
        *,
        profile_id: str,
        active: BuddyDomainCapabilityRecord,
        persist: bool = True,
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
        if not persist:
            return updated
        return self._domain_capability_repository.upsert_domain_capability(updated)

    def _repair_legacy_execution_binding(
        self,
        *,
        active: BuddyDomainCapabilityRecord,
    ) -> None:
        get_instance = getattr(self._industry_instance_repository, "get_instance", None)
        if not callable(get_instance):
            return
        instance_id = str(active.industry_instance_id or "").strip()
        if not instance_id.startswith("buddy:"):
            return
        record = get_instance(instance_id)
        if record is None:
            return
        roles = self._restore_or_build_buddy_roles(record=record)
        if not roles:
            return
        role_to_agent = {role.role_id: role.agent_id for role in roles}
        needs_team_repair = (
            not list((record.team_payload or {}).get("agents") or [])
            or set(record.agent_ids or []) != set(role_to_agent.values())
        )
        if needs_team_repair:
            self._industry_instance_repository.upsert_instance(
                record.model_copy(
                    update={
                        "team_payload": IndustryTeamBlueprint(
                            team_id=record.instance_id,
                            label=record.label,
                            summary=record.summary,
                            agents=roles,
                        ).model_dump(mode="json"),
                        "agent_ids": [role.agent_id for role in roles],
                        "updated_at": _utc_now(),
                    },
                ),
            )
        if self._operating_lane_service is not None:
            self._operating_lane_service.seed_from_roles(
                industry_instance_id=instance_id,
                roles=roles,
            )
        list_assignments = getattr(self._assignment_service, "list_assignments", None)
        assignment_repository = getattr(self._assignment_service, "_repository", None)
        if not callable(list_assignments) or assignment_repository is None:
            return
        assignments = list_assignments(industry_instance_id=instance_id, limit=None)
        lanes = []
        if self._operating_lane_service is not None:
            lanes = self._operating_lane_service.list_lanes(
                industry_instance_id=instance_id,
                limit=None,
            )
        lanes_by_id = {
            str(getattr(lane, "id", "") or "").strip(): lane
            for lane in lanes
            if str(getattr(lane, "id", "") or "").strip()
        }
        for assignment in assignments:
            metadata = dict(getattr(assignment, "metadata", None) or {})
            explicit_role_id = normalize_industry_role_id(
                _string(getattr(assignment, "owner_role_id", None))
                or _string(metadata.get("industry_role_id"))
            )
            if explicit_role_id not in role_to_agent:
                if explicit_role_id is not None:
                    continue
                lane = lanes_by_id.get(str(getattr(assignment, "lane_id", "") or "").strip())
                explicit_role_id = normalize_industry_role_id(
                    _string(getattr(lane, "owner_role_id", None))
                )
                if explicit_role_id not in role_to_agent:
                    continue
            desired_agent_id = role_to_agent[explicit_role_id]
            desired_role_id = explicit_role_id
            if (
                _string(getattr(assignment, "owner_agent_id", None)) == desired_agent_id
                and _string(getattr(assignment, "owner_role_id", None)) == desired_role_id
                and _string(metadata.get("owner_agent_id")) == desired_agent_id
                and _string(metadata.get("industry_role_id")) == desired_role_id
            ):
                continue
            metadata["owner_agent_id"] = desired_agent_id
            metadata["industry_role_id"] = desired_role_id
            assignment_repository.upsert_assignment(
                assignment.model_copy(
                    update={
                        "owner_agent_id": desired_agent_id,
                        "owner_role_id": desired_role_id,
                        "metadata": metadata,
                        "updated_at": _utc_now(),
                    },
                ),
            )

    def _restore_or_build_buddy_roles(
        self,
        *,
        record: object,
    ) -> list[IndustryRoleBlueprint]:
        payload = dict(getattr(record, "team_payload", None) or {})
        restored: list[IndustryRoleBlueprint] = []
        for item in list(payload.get("agents") or []):
            try:
                restored.append(IndustryRoleBlueprint.model_validate(item))
            except Exception:
                continue
        if restored:
            return restored
        instance_id = str(getattr(record, "instance_id", "") or "").strip()
        label = str(getattr(record, "label", "") or "").strip() or "Buddy"
        domain_key = derive_buddy_domain_key(
            _string(getattr(record, "summary", None)) or label,
        )
        restored_role_ids: list[str] = []
        normalized_prefix = f"{instance_id}:"
        for agent_id in list(getattr(record, "agent_ids", None) or []):
            normalized_agent_id = _string(agent_id)
            if normalized_agent_id is None or normalized_agent_id == EXECUTION_CORE_AGENT_ID:
                continue
            if normalized_agent_id.startswith(normalized_prefix):
                candidate_role_id = normalized_agent_id[len(normalized_prefix) :]
            else:
                candidate_role_id = normalized_agent_id.rsplit(":", 1)[-1]
            normalized_role_id = normalize_industry_role_id(candidate_role_id)
            if normalized_role_id is None or normalized_role_id == EXECUTION_CORE_ROLE_ID:
                continue
            if normalized_role_id not in restored_role_ids:
                restored_role_ids.append(normalized_role_id)
        if not restored_role_ids and self._operating_lane_service is not None:
            lanes = self._operating_lane_service.list_lanes(
                industry_instance_id=instance_id,
                limit=None,
            )
            for lane in lanes:
                normalized_role_id = normalize_industry_role_id(
                    _string(getattr(lane, "owner_role_id", None))
                )
                if normalized_role_id and normalized_role_id != EXECUTION_CORE_ROLE_ID:
                    if normalized_role_id not in restored_role_ids:
                        restored_role_ids.append(normalized_role_id)
        if not restored_role_ids and self._assignment_service is not None:
            assignments = self._assignment_service.list_assignments(
                industry_instance_id=instance_id,
                limit=None,
            )
            for assignment in assignments:
                metadata = dict(getattr(assignment, "metadata", None) or {})
                normalized_role_id = normalize_industry_role_id(
                    _string(getattr(assignment, "owner_role_id", None))
                    or _string(metadata.get("industry_role_id"))
                )
                if normalized_role_id and normalized_role_id != EXECUTION_CORE_ROLE_ID:
                    if normalized_role_id not in restored_role_ids:
                        restored_role_ids.append(normalized_role_id)
        if restored_role_ids:
            rebuilt_roles: list[IndustryRoleBlueprint] = []
            for role_id in restored_role_ids:
                parts = [part for part in role_id.replace("_", "-").split("-") if part]
                role_name = (
                    " ".join(part.capitalize() for part in parts)
                    if parts and all(part.isascii() for part in parts)
                    else role_id
                )
                role_summary = (
                    f"Own the {role_name} lane for {label}, keep it moving, and report structured evidence "
                    "back to the execution core."
                )
                rebuilt_roles.append(
                    IndustryRoleBlueprint(
                        role_id=role_id,
                        agent_id=f"{instance_id}:{role_id}",
                        actor_key=f"{instance_id}:{role_id}",
                        name=f"{label} {role_name}",
                        role_name=role_name,
                        role_summary=role_summary,
                        mission=role_summary,
                        goal_kind=role_id,
                        agent_class="business",
                        employment_mode="career",
                        activation_mode="persistent",
                        suspendable=False,
                        reports_to=EXECUTION_CORE_ROLE_ID,
                        risk_level="guarded",
                        allowed_capabilities=buddy_specialist_allowed_capabilities(
                            domain_key=domain_key,
                            role_id=role_id,
                        ),
                        preferred_capability_families=buddy_specialist_preferred_capability_families(
                            domain_key=domain_key,
                            role_id=role_id,
                        ),
                        evidence_expectations=[f"{role_id} evidence"],
                    ),
                )
            if rebuilt_roles:
                return rebuilt_roles
        return []

    @staticmethod
    def _list_records(service: object | None, method_name: str, **kwargs) -> list[object]:
        method = getattr(service, method_name, None)
        if not callable(method):
            return []
        result = method(**kwargs)
        return list(result or [])


__all__ = ["BuddyDomainCapabilityGrowthService"]
