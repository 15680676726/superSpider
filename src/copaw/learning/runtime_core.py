# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ..config import load_config  # noqa: F401
from ..evidence import EvidenceLedger, EvidenceRecord
from ..kernel.persistence import decode_kernel_task_metadata
from ..state import DecisionRequestRecord, TaskRecord
from ..state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteTaskRepository,
)
from .acquisition_runtime import LearningAcquisitionRuntimeService
from .engine import LearningEngine
from .executor import PatchExecutor
from .growth_runtime import LearningGrowthRuntimeService
from .models import (
    CapabilityAcquisitionProposal,
    GrowthEvent,
    InstallBindingPlan,
    OnboardingRun,
    Patch,
    PatchStatus,
    Proposal,
    ProposalStatus,
)
from .patch_runtime import LearningPatchRuntimeService
from .runtime_support import (
    _MAIN_BRAIN_ACTOR,
    _compiler_context_snapshot,
    _is_failure_record,
    _merge_string_lists,
    _patch_acceptance_criteria,
    _patch_constraints_summary,
    _utc_now,
)

logger = logging.getLogger(__name__)


class LearningRuntimeCore:
    """Internal learning runtime implementation."""

    def __init__(
        self,
        *,
        engine: LearningEngine | None = None,
        patch_executor: PatchExecutor | None = None,
        decision_request_repository: SqliteDecisionRequestRepository | None = None,
        task_repository: SqliteTaskRepository | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        runtime_event_bus: object | None = None,
    ) -> None:
        self._engine = engine or LearningEngine()
        self._patch_executor = patch_executor or PatchExecutor()
        self._decision_repo = decision_request_repository
        self._task_repo = task_repository
        self._evidence_ledger = evidence_ledger
        self._runtime_event_bus = runtime_event_bus
        self._industry_service: object | None = None
        self._capability_service: object | None = None
        self._fixed_sop_service: object | None = None
        self._agent_profile_service: object | None = None
        self._experience_memory_service: object | None = None
        self._patch_runtime = LearningPatchRuntimeService(self)
        self._growth_runtime = LearningGrowthRuntimeService(self)
        self._acquisition_runtime = LearningAcquisitionRuntimeService(self)

    @property
    def engine(self) -> LearningEngine:
        return self._engine

    def set_industry_service(self, industry_service: object | None) -> None:
        self._industry_service = industry_service

    def set_capability_service(self, capability_service: object | None) -> None:
        self._capability_service = capability_service

    def set_fixed_sop_service(self, fixed_sop_service: object | None) -> None:
        self._fixed_sop_service = fixed_sop_service

    def set_agent_profile_service(self, agent_profile_service: object | None) -> None:
        self._agent_profile_service = agent_profile_service

    def set_experience_memory_service(
        self,
        experience_memory_service: object | None,
    ) -> None:
        self._experience_memory_service = experience_memory_service

    def list_proposals(
        self,
        *,
        status: ProposalStatus | str | None = None,
        created_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Proposal]:
        return self._engine.list_proposals(
            status=status,
            created_since=created_since,
            limit=limit,
        )

    def delete_proposal(self, proposal_id: str) -> bool:
        deleted = self._engine.delete_proposal(proposal_id)
        if deleted:
            self._publish_runtime_event(
                topic="proposal",
                action="deleted",
                payload={"proposal_id": proposal_id},
            )
        return deleted

    def create_proposal(
        self,
        *,
        title: str,
        description: str,
        source_agent_id: str = "copaw-agent-runner",
        goal_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        target_layer: str = "",
        evidence_refs: list[str] | None = None,
    ) -> Proposal:
        resolved = self._resolve_learning_context(
            goal_id=goal_id,
            task_id=task_id,
            agent_id=agent_id,
            source_evidence_id=None,
            evidence_refs=evidence_refs or [],
        )
        proposal = self._engine.create_proposal(
            title=title,
            description=description,
            source_agent_id=source_agent_id,
            goal_id=resolved["goal_id"],
            task_id=resolved["task_id"],
            agent_id=resolved["agent_id"],
            target_layer=target_layer,
            evidence_refs=resolved["evidence_refs"],
        )
        self._publish_runtime_event(
            topic="proposal",
            action="created",
            payload={
                "proposal_id": proposal.id,
                "goal_id": proposal.goal_id,
                "task_id": proposal.task_id,
                "agent_id": proposal.agent_id,
                "status": proposal.status,
            },
        )
        return proposal

    def should_run_strategy_cycle(
        self,
        *,
        limit: int | None = None,
        failure_threshold: int = 2,
    ) -> tuple[bool, str]:
        if self._evidence_ledger is None:
            return (False, "evidence-ledger-unavailable")

        recent = self._collect_recent_evidence(limit=limit)
        if not recent:
            return (False, "no-recent-evidence")

        failure_groups = self._summarize_failures(recent)
        if not failure_groups:
            return (False, "no-failure-signals")

        existing_titles = {
            proposal.title
            for proposal in self._engine.list_proposals()
            if proposal.status in {"open", "accepted"}
        }
        for capability_ref, bucket in failure_groups.items():
            if int(bucket.get("count", 0) or 0) < failure_threshold:
                continue
            title = f"降低 {capability_ref} 的失败率"
            if title in existing_titles:
                continue
            return (True, "actionable-failure-pattern")
        return (False, "no-actionable-failure-pattern")

    def accept_proposal(self, proposal_id: str) -> Proposal:
        proposal = self._engine.accept_proposal(proposal_id)
        self._publish_runtime_event(
            topic="proposal",
            action="accepted",
            payload={"proposal_id": proposal.id, "status": proposal.status},
        )
        return proposal

    def reject_proposal(self, proposal_id: str) -> Proposal:
        proposal = self._engine.reject_proposal(proposal_id)
        self._publish_runtime_event(
            topic="proposal",
            action="rejected",
            payload={"proposal_id": proposal.id, "status": proposal.status},
        )
        return proposal

    def list_acquisition_proposals(
        self,
        *,
        industry_instance_id: str | None = None,
        status: str | None = None,
        target_agent_id: str | None = None,
        target_role_id: str | None = None,
        acquisition_kind: str | None = None,
        limit: int | None = None,
    ) -> list[CapabilityAcquisitionProposal]:
        return self._acquisition_runtime.list_acquisition_proposals(
            industry_instance_id=industry_instance_id,
            status=status,
            target_agent_id=target_agent_id,
            target_role_id=target_role_id,
            acquisition_kind=acquisition_kind,
            limit=limit,
        )

    def get_acquisition_proposal(
        self,
        proposal_id: str,
    ) -> CapabilityAcquisitionProposal:
        return self._acquisition_runtime.get_acquisition_proposal(proposal_id)

    def delete_acquisition_proposal(self, proposal_id: str) -> bool:
        return self._acquisition_runtime.delete_acquisition_proposal(proposal_id)

    async def approve_acquisition_proposal(
        self,
        proposal_id: str,
        *,
        approved_by: str = "system",
    ) -> dict[str, object]:
        return await self._acquisition_runtime.approve_acquisition_proposal(
            proposal_id,
            approved_by=approved_by,
        )

    def reject_acquisition_proposal(
        self,
        proposal_id: str,
        *,
        rejected_by: str = "system",
    ) -> dict[str, object]:
        return self._acquisition_runtime.reject_acquisition_proposal(
            proposal_id,
            rejected_by=rejected_by,
        )

    async def finalize_resolved_decision(
        self,
        decision_id: str,
        *,
        status: str,
        actor: str = "system",
        resolution: str | None = None,
    ) -> dict[str, object]:
        return await self._acquisition_runtime.finalize_resolved_decision(
            decision_id,
            status=status,
            actor=actor,
            resolution=resolution,
        )

    def list_install_binding_plans(
        self,
        *,
        proposal_id: str | None = None,
        industry_instance_id: str | None = None,
        status: str | None = None,
        target_agent_id: str | None = None,
        target_role_id: str | None = None,
        limit: int | None = None,
    ) -> list[InstallBindingPlan]:
        return self._acquisition_runtime.list_install_binding_plans(
            proposal_id=proposal_id,
            industry_instance_id=industry_instance_id,
            status=status,
            target_agent_id=target_agent_id,
            target_role_id=target_role_id,
            limit=limit,
        )

    def get_install_binding_plan(self, plan_id: str) -> InstallBindingPlan:
        return self._acquisition_runtime.get_install_binding_plan(plan_id)

    def delete_install_binding_plan(self, plan_id: str) -> bool:
        return self._acquisition_runtime.delete_install_binding_plan(plan_id)

    def list_onboarding_runs(
        self,
        *,
        plan_id: str | None = None,
        proposal_id: str | None = None,
        industry_instance_id: str | None = None,
        status: str | None = None,
        target_agent_id: str | None = None,
        target_role_id: str | None = None,
        limit: int | None = None,
    ) -> list[OnboardingRun]:
        return self._acquisition_runtime.list_onboarding_runs(
            plan_id=plan_id,
            proposal_id=proposal_id,
            industry_instance_id=industry_instance_id,
            status=status,
            target_agent_id=target_agent_id,
            target_role_id=target_role_id,
            limit=limit,
        )

    def get_onboarding_run(self, run_id: str) -> OnboardingRun:
        return self._acquisition_runtime.get_onboarding_run(run_id)

    def delete_onboarding_run(self, run_id: str) -> bool:
        return self._acquisition_runtime.delete_onboarding_run(run_id)

    def list_patches(
        self,
        *,
        status: PatchStatus | str | None = None,
        goal_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        evidence_id: str | None = None,
        created_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Patch]:
        return self._patch_runtime.list_patches(
            status=status,
            goal_id=goal_id,
            task_id=task_id,
            agent_id=agent_id,
            evidence_id=evidence_id,
            created_since=created_since,
            limit=limit,
        )

    def get_patch(self, patch_id: str) -> Patch:
        return self._patch_runtime.get_patch(patch_id)

    def delete_patch(self, patch_id: str) -> bool:
        return self._patch_runtime.delete_patch(patch_id)

    def create_patch(
        self,
        *,
        kind: str,
        title: str,
        description: str,
        goal_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        diff_summary: str = "",
        proposal_id: str | None = None,
        evidence_refs: list[str] | None = None,
        source_evidence_id: str | None = None,
        risk_level: str = "auto",
        auto_apply: bool = False,
    ) -> dict[str, object]:
        return self._patch_runtime.create_patch(
            kind=kind,
            title=title,
            description=description,
            goal_id=goal_id,
            task_id=task_id,
            agent_id=agent_id,
            diff_summary=diff_summary,
            proposal_id=proposal_id,
            evidence_refs=evidence_refs,
            source_evidence_id=source_evidence_id,
            risk_level=risk_level,
            auto_apply=auto_apply,
        )

    def approve_patch(self, patch_id: str, *, approved_by: str = "system") -> Patch:
        return self._patch_runtime.approve_patch(
            patch_id,
            approved_by=approved_by,
        )

    def reject_patch(self, patch_id: str, *, rejected_by: str = "system") -> Patch:
        return self._patch_runtime.reject_patch(
            patch_id,
            rejected_by=rejected_by,
        )

    def apply_patch(self, patch_id: str, *, applied_by: str = "system") -> Patch:
        return self._patch_runtime.apply_patch(
            patch_id,
            applied_by=applied_by,
        )

    def rollback_patch(self, patch_id: str, *, rolled_back_by: str = "system") -> Patch:
        return self._patch_runtime.rollback_patch(
            patch_id,
            rolled_back_by=rolled_back_by,
        )

    def auto_apply_low_risk_patches(
        self,
        *,
        limit: int | None = None,
        actor: str = _MAIN_BRAIN_ACTOR,
    ) -> dict[str, object]:
        return self._patch_runtime.auto_apply_low_risk_patches(
            limit=limit,
            actor=actor,
        )

    def run_strategy_cycle(
        self,
        *,
        actor: str = _MAIN_BRAIN_ACTOR,
        limit: int | None = None,
        auto_apply: bool = True,
        auto_rollback: bool = False,
        failure_threshold: int = 2,
        confirm_threshold: int = 6,
        max_proposals: int = 5,
    ) -> dict[str, object]:
        return self._patch_runtime.run_strategy_cycle(
            actor=actor,
            limit=limit,
            auto_apply=auto_apply,
            auto_rollback=auto_rollback,
            failure_threshold=failure_threshold,
            confirm_threshold=confirm_threshold,
            max_proposals=max_proposals,
        )

    def list_growth(
        self,
        *,
        agent_id: str | None = None,
        goal_id: str | None = None,
        task_id: str | None = None,
        source_patch_id: str | None = None,
        source_evidence_id: str | None = None,
        created_since: datetime | None = None,
        limit: int | None = 50,
    ) -> list[GrowthEvent]:
        return self._growth_runtime.list_growth(
            agent_id=agent_id,
            goal_id=goal_id,
            task_id=task_id,
            source_patch_id=source_patch_id,
            source_evidence_id=source_evidence_id,
            created_since=created_since,
            limit=limit,
        )

    def record_agent_outcome(
        self,
        *,
        agent_id: str | None,
        title: str,
        status: str,
        change_type: str,
        description: str | None = None,
        capability_ref: str | None = None,
        task_id: str | None = None,
        goal_id: str | None = None,
        source_evidence_id: str | None = None,
        risk_level: str = "auto",
        source_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        industry_role_id: str | None = None,
        role_name: str | None = None,
        owner_scope: str | None = None,
        error_summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GrowthEvent | None:
        return self._growth_runtime.record_agent_outcome(
            agent_id=agent_id,
            title=title,
            status=status,
            change_type=change_type,
            description=description,
            capability_ref=capability_ref,
            task_id=task_id,
            goal_id=goal_id,
            source_evidence_id=source_evidence_id,
            risk_level=risk_level,
            source_agent_id=source_agent_id,
            industry_instance_id=industry_instance_id,
            industry_role_id=industry_role_id,
            role_name=role_name,
            owner_scope=owner_scope,
            error_summary=error_summary,
            metadata=metadata,
        )

    def get_growth_event(self, event_id: str) -> GrowthEvent:
        return self._growth_runtime.get_growth_event(event_id)

    def delete_growth_event(self, event_id: str) -> bool:
        return self._growth_runtime.delete_growth_event(event_id)

    async def run_industry_acquisition_cycle(
        self,
        *,
        industry_instance_id: str,
        actor: str = _MAIN_BRAIN_ACTOR,
        rerun_existing: bool = False,
        max_install_recommendations_per_role: int = 4,
        max_sop_templates_per_role: int = 2,
    ) -> dict[str, object]:
        return await self._acquisition_runtime.run_industry_acquisition_cycle(
            industry_instance_id=industry_instance_id,
            actor=actor,
            rerun_existing=rerun_existing,
            max_install_recommendations_per_role=max_install_recommendations_per_role,
            max_sop_templates_per_role=max_sop_templates_per_role,
        )

    async def _run_capability_trial_check(
        self,
        *,
        capability_id: str,
        plan: InstallBindingPlan,
        proposal: CapabilityAcquisitionProposal,
    ) -> dict[str, object]:
        return await self._acquisition_runtime._run_capability_trial_check(
            capability_id=capability_id,
            plan=plan,
            proposal=proposal,
        )


    def _collect_recent_evidence(
        self,
        *,
        limit: int | None = None,
    ) -> list[EvidenceRecord]:
        if self._evidence_ledger is None:
            return []
        if limit is None:
            limit = 50
        recent = self._evidence_ledger.list_recent(limit=limit)
        # Normalize the recent window into oldest-first order so downstream
        # proposal/patch linkage picks a stable source evidence within that set.
        return list(reversed(recent))

    def _summarize_failures(
        self,
        records: list[EvidenceRecord],
    ) -> dict[str, dict[str, object]]:
        failures: dict[str, dict[str, object]] = {}
        for record in records:
            if not _is_failure_record(record):
                continue
            capability_ref = record.capability_ref or "unknown"
            bucket = failures.setdefault(
                capability_ref,
                {"count": 0, "evidence_ids": [], "samples": []},
            )
            bucket["count"] += 1
            if record.id:
                bucket["evidence_ids"].append(record.id)
            if len(bucket["samples"]) < 3:
                bucket["samples"].append(record.result_summary)
        return failures

    @staticmethod
    def _risk_from_failure_count(
        count: int,
        *,
        failure_threshold: int,
        confirm_threshold: int,
    ) -> str:
        if count >= confirm_threshold:
            return "confirm"
        if count >= failure_threshold + 1:
            return "guarded"
        return "auto"

    @staticmethod
    def _task_status_for_patch(patch: Patch) -> str:
        if patch.status == "applied":
            return "completed"
        if patch.status in {"rejected", "rolled_back"}:
            return "cancelled"
        if patch.risk_level == "confirm":
            return "needs-confirm"
        return "queued"

    def _ensure_main_brain_patch_adjudication(self, patch: Patch) -> Patch:
        if patch.risk_level == "confirm":
            return patch
        if patch.status != "proposed":
            return patch
        return self.approve_patch(
            patch.id,
            approved_by=_MAIN_BRAIN_ACTOR,
        )

    def _ensure_patch_decision(self, patch: Patch) -> DecisionRequestRecord | None:
        if patch.risk_level != "confirm" or self._decision_repo is None:
            return None
        self._ensure_patch_task(patch)
        open_requests = self._decision_repo.list_decision_requests(
            task_id=patch.id,
            status="open",
        )
        if open_requests:
            return open_requests[0]
        decision = DecisionRequestRecord(
            task_id=patch.id,
            decision_type="patch-approval",
            risk_level=patch.risk_level,
            summary=f"应用前需先批准补丁“{patch.title}”。",
            requested_by="learning-service",
            source_patch_id=patch.id,
        )
        self._decision_repo.upsert_decision_request(decision)
        return decision

    def _ensure_patch_task(self, patch: Patch) -> None:
        if self._task_repo is None:
            return
        existing = self._task_repo.get_task(patch.id)
        status = self._task_status_for_patch(patch)
        if existing is None:
            record = TaskRecord(
                id=patch.id,
                goal_id=patch.goal_id,
                title=patch.title,
                summary=patch.description,
                task_type="learning-patch",
                status=status,
                priority=0,
                owner_agent_id=patch.agent_id or patch.applied_by or "learning-service",
                parent_task_id=None,
                seed_source=f"learning:{patch.kind}",
                constraints_summary=_patch_constraints_summary(patch),
                acceptance_criteria=_patch_acceptance_criteria(patch),
                current_risk_level=patch.risk_level,
                created_at=patch.created_at,
                updated_at=_utc_now(),
            )
            self._task_repo.upsert_task(record)
            return
        if (
            existing.status == status
            and existing.goal_id == patch.goal_id
            and existing.owner_agent_id == (patch.agent_id or existing.owner_agent_id)
        ):
            return
        updated = existing.model_copy(
            update={
                "goal_id": patch.goal_id or existing.goal_id,
                "status": status,
                "owner_agent_id": patch.agent_id or existing.owner_agent_id,
                "seed_source": existing.seed_source or f"learning:{patch.kind}",
                "constraints_summary": (
                    existing.constraints_summary or _patch_constraints_summary(patch)
                ),
                "acceptance_criteria": _patch_acceptance_criteria(patch),
                "updated_at": _utc_now(),
            },
        )
        self._task_repo.upsert_task(updated)

    def _record_patch_decision_if_missing(
        self,
        patch: Patch,
        *,
        status: str,
        resolution: str,
        decision_type: str,
        requested_by: str,
    ) -> DecisionRequestRecord | None:
        if self._decision_repo is None:
            return None
        self._ensure_patch_task(patch)
        existing = self._decision_repo.list_decision_requests(task_id=patch.id)
        for decision in existing:
            if decision.status == status:
                return decision
        decision = DecisionRequestRecord(
            task_id=patch.id,
            decision_type=decision_type,
            risk_level=patch.risk_level,
            summary=f"{decision_type}：{patch.title}",
            status=status,
            source_patch_id=patch.id,
            requested_by=requested_by,
            resolution=resolution,
            resolved_at=_utc_now(),
        )
        return self._decision_repo.upsert_decision_request(decision)

    def _append_patch_evidence(
        self,
        patch: Patch,
        *,
        actor: str,
        action: str,
        result: str,
        status: str = "recorded",
        metadata: dict[str, object] | None = None,
    ) -> str | None:
        if self._evidence_ledger is None:
            return None
        payload = {
            "patch_id": patch.id,
            "proposal_id": patch.proposal_id,
            "risk_level": patch.risk_level,
        }
        if metadata:
            payload.update(metadata)
        record = self._evidence_ledger.append(
            EvidenceRecord(
                task_id=patch.id,
                actor_ref=actor,
                capability_ref=f"learning:{action}",
                risk_level=patch.risk_level,
                action_summary=action,
                result_summary=result,
                status=status,
                metadata=payload,
            ),
        )
        return record.id

    def _resolve_learning_context(
        self,
        *,
        goal_id: str | None,
        task_id: str | None,
        agent_id: str | None,
        source_evidence_id: str | None,
        evidence_refs: list[str],
    ) -> dict[str, str | None | list[str]]:
        resolved_goal_id = goal_id
        resolved_task_id = task_id
        resolved_agent_id = agent_id
        resolved_source_evidence_id = source_evidence_id
        resolved_evidence_refs = [ref for ref in evidence_refs if ref]

        evidence_record = None
        if self._evidence_ledger is not None:
            for evidence_id in [source_evidence_id, *evidence_refs]:
                if not evidence_id:
                    continue
                evidence_record = self._evidence_ledger.get_record(evidence_id)
                if evidence_record is not None:
                    break

        if evidence_record is not None and evidence_record.task_id and resolved_task_id is None:
            resolved_task_id = evidence_record.task_id
        if evidence_record is not None and evidence_record.id:
            if resolved_source_evidence_id is None:
                resolved_source_evidence_id = evidence_record.id
            if evidence_record.id not in resolved_evidence_refs:
                resolved_evidence_refs.insert(0, evidence_record.id)

        if self._task_repo is not None and resolved_task_id:
            task = self._task_repo.get_task(resolved_task_id)
            if task is not None:
                if resolved_goal_id is None and task.goal_id:
                    resolved_goal_id = task.goal_id
                if resolved_agent_id is None and task.owner_agent_id:
                    resolved_agent_id = task.owner_agent_id
        compiler_context = self._latest_compiler_context(
            goal_id=resolved_goal_id,
            task_id=resolved_task_id,
        )
        if compiler_context is not None:
            if resolved_goal_id is None:
                resolved_goal_id = compiler_context["goal_id"]
            if resolved_task_id is None:
                resolved_task_id = compiler_context["task_id"]
            if resolved_agent_id is None:
                resolved_agent_id = compiler_context["agent_id"]
            if not resolved_evidence_refs:
                resolved_evidence_refs = list(compiler_context["evidence_refs"])
            else:
                resolved_evidence_refs = _merge_string_lists(
                    resolved_evidence_refs,
                    compiler_context["evidence_refs"],
                )
            if resolved_source_evidence_id is None:
                resolved_source_evidence_id = compiler_context["source_evidence_id"]

        return {
            "goal_id": resolved_goal_id,
            "task_id": resolved_task_id,
            "agent_id": resolved_agent_id,
            "source_evidence_id": resolved_source_evidence_id,
            "evidence_refs": resolved_evidence_refs,
        }

    def _latest_compiler_context(
        self,
        *,
        goal_id: str | None,
        task_id: str | None,
    ) -> dict[str, str | list[str] | None] | None:
        if self._task_repo is None:
            return None

        anchor_task = self._task_repo.get_task(task_id) if task_id else None
        candidate_tasks: list[TaskRecord] = []
        if anchor_task is not None and anchor_task.goal_id:
            candidate_tasks = self._task_repo.list_tasks(goal_id=anchor_task.goal_id)
        elif goal_id is not None:
            candidate_tasks = self._task_repo.list_tasks(goal_id=goal_id)
        elif anchor_task is not None:
            candidate_tasks = [anchor_task]
        if not candidate_tasks:
            return None

        seed_candidates: list[dict[str, Any]] = []
        for task in candidate_tasks:
            snapshot = _compiler_context_snapshot(task)
            if snapshot is not None:
                seed_candidates.append(snapshot)
        if not seed_candidates:
            return None

        latest_unit_id = max(
            seed_candidates,
            key=lambda item: (item["compiled_at_key"], item["task"].updated_at.isoformat()),
        )["unit_id"]
        latest_unit_tasks = [
            item
            for item in seed_candidates
            if item["unit_id"] == latest_unit_id
        ]
        latest_unit_tasks.sort(
            key=lambda item: (
                item["step_order"],
                item["task"].updated_at.isoformat(),
                item["task"].id,
            ),
        )

        primary = latest_unit_tasks[0]
        evidence_refs = _merge_string_lists(
            *[item["evidence_refs"] for item in latest_unit_tasks],
        )
        return {
            "goal_id": primary["task"].goal_id,
            "task_id": primary["task"].id,
            "agent_id": primary["task"].owner_agent_id,
            "source_evidence_id": evidence_refs[0] if evidence_refs else None,
            "evidence_refs": evidence_refs,
        }

    def _resolve_patch_decision(
        self,
        patch_id: str,
        *,
        status: str,
        resolution: str,
    ) -> None:
        if self._decision_repo is None:
            return
        open_requests = self._decision_repo.list_decision_requests(
            task_id=patch_id,
            status="open",
        )
        for decision in open_requests:
            updated = decision.model_copy(
                update={
                    "status": status,
                    "resolution": resolution,
                    "resolved_at": _utc_now(),
                },
            )
            self._decision_repo.upsert_decision_request(updated)

    def set_runtime_event_bus(self, runtime_event_bus: object | None) -> None:
        self._runtime_event_bus = runtime_event_bus

    def _publish_runtime_event(
        self,
        *,
        topic: str,
        action: str,
        payload: dict[str, object],
    ) -> None:
        if self._runtime_event_bus is None:
            return
        self._runtime_event_bus.publish(
            topic=topic,
            action=action,
            payload=payload,
        )


__all__ = ["LearningRuntimeCore"]
