# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..evidence import EvidenceLedger
from ..state.repositories import SqliteDecisionRequestRepository, SqliteTaskRepository
from .acquisition_service import LearningAcquisitionService
from .engine import LearningEngine
from .executor import PatchExecutor
from .growth_service import LearningGrowthService
from .models import GrowthEvent, Patch, PatchStatus, Proposal, ProposalStatus
from .patch_service import LearningPatchService
from .proposal_service import LearningProposalService
from .runtime_bindings import LearningRuntimeBindings
from .runtime_core import LearningRuntimeCore


class LearningService:
    """Public learning facade with explicit internal domain services."""

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
        self._core = LearningRuntimeCore(
            engine=engine,
            patch_executor=patch_executor,
            decision_request_repository=decision_request_repository,
            task_repository=task_repository,
            evidence_ledger=evidence_ledger,
            runtime_event_bus=runtime_event_bus,
        )
        self._proposal_service = LearningProposalService(self._core)
        self._patch_service = LearningPatchService(self._core)
        self._growth_service = LearningGrowthService(self._core)
        self._acquisition_service = LearningAcquisitionService(self._core)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._core, name)

    @property
    def engine(self) -> LearningEngine:
        return self._core.engine

    def configure_bindings(self, bindings: LearningRuntimeBindings) -> None:
        self._core.set_industry_service(bindings.industry_service)
        self._core.set_capability_service(bindings.capability_service)
        self._core.set_kernel_dispatcher(bindings.kernel_dispatcher)
        self._core.set_fixed_sop_service(bindings.fixed_sop_service)
        self._core.set_agent_profile_service(bindings.agent_profile_service)
        self._core.set_experience_memory_service(bindings.experience_memory_service)

    def set_industry_service(self, industry_service: object | None) -> None:
        self._core.set_industry_service(industry_service)

    def set_capability_service(self, capability_service: object | None) -> None:
        self._core.set_capability_service(capability_service)

    def set_kernel_dispatcher(self, kernel_dispatcher: object | None) -> None:
        self._core.set_kernel_dispatcher(kernel_dispatcher)

    def set_fixed_sop_service(self, fixed_sop_service: object | None) -> None:
        self._core.set_fixed_sop_service(fixed_sop_service)

    def set_agent_profile_service(self, agent_profile_service: object | None) -> None:
        self._core.set_agent_profile_service(agent_profile_service)

    def set_experience_memory_service(
        self,
        experience_memory_service: object | None,
    ) -> None:
        self._core.set_experience_memory_service(experience_memory_service)

    def set_runtime_event_bus(self, runtime_event_bus: object | None) -> None:
        self._core.set_runtime_event_bus(runtime_event_bus)

    def list_proposals(
        self,
        *,
        status: ProposalStatus | str | None = None,
        created_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Proposal]:
        return self._proposal_service.list_proposals(
            status=status,
            created_since=created_since,
            limit=limit,
        )

    def delete_proposal(self, proposal_id: str) -> bool:
        return self._proposal_service.delete_proposal(proposal_id)

    def create_proposal(self, **kwargs) -> Proposal:
        return self._proposal_service.create_proposal(**kwargs)

    def accept_proposal(self, proposal_id: str) -> Proposal:
        return self._proposal_service.accept_proposal(proposal_id)

    def reject_proposal(self, proposal_id: str) -> Proposal:
        return self._proposal_service.reject_proposal(proposal_id)

    def should_run_strategy_cycle(
        self,
        *,
        limit: int | None = None,
        failure_threshold: int = 2,
    ) -> tuple[bool, str]:
        return self._patch_service.should_run_strategy_cycle(
            limit=limit,
            failure_threshold=failure_threshold,
        )

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
        return self._patch_service.list_patches(
            status=status,
            goal_id=goal_id,
            task_id=task_id,
            agent_id=agent_id,
            evidence_id=evidence_id,
            created_since=created_since,
            limit=limit,
        )

    def get_patch(self, patch_id: str) -> Patch:
        return self._patch_service.get_patch(patch_id)

    def delete_patch(self, patch_id: str) -> bool:
        return self._patch_service.delete_patch(patch_id)

    def create_patch(self, **kwargs) -> dict[str, object]:
        return self._patch_service.create_patch(**kwargs)

    def approve_patch(self, patch_id: str, *, approved_by: str = "system") -> Patch:
        return self._patch_service.approve_patch(patch_id, approved_by=approved_by)

    def reject_patch(self, patch_id: str, *, rejected_by: str = "system") -> Patch:
        return self._patch_service.reject_patch(patch_id, rejected_by=rejected_by)

    def apply_patch(self, patch_id: str, *, applied_by: str = "system") -> Patch:
        return self._patch_service.apply_patch(patch_id, applied_by=applied_by)

    def rollback_patch(
        self,
        patch_id: str,
        *,
        rolled_back_by: str = "system",
    ) -> Patch:
        return self._patch_service.rollback_patch(
            patch_id,
            rolled_back_by=rolled_back_by,
        )

    def auto_apply_low_risk_patches(
        self,
        *,
        limit: int | None = None,
        max_items: int = 20,
        actor: str = "system",
    ) -> dict[str, object]:
        return self._patch_service.auto_apply_low_risk_patches(
            limit=limit,
            max_items=max_items,
            actor=actor,
        )

    def run_strategy_cycle(self, **kwargs) -> dict[str, object]:
        return self._patch_service.run_strategy_cycle(**kwargs)

    def list_growth(
        self,
        *,
        agent_id: str | None = None,
        goal_id: str | None = None,
        task_id: str | None = None,
        source_patch_id: str | None = None,
        source_evidence_id: str | None = None,
        category: str | None = None,
        created_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[GrowthEvent]:
        return self._growth_service.list_growth(
            agent_id=agent_id,
            goal_id=goal_id,
            task_id=task_id,
            source_patch_id=source_patch_id,
            source_evidence_id=source_evidence_id,
            category=category,
            created_since=created_since,
            limit=limit,
        )

    def record_agent_outcome(self, **kwargs) -> GrowthEvent:
        return self._growth_service.record_agent_outcome(**kwargs)

    def get_growth_event(self, event_id: str) -> GrowthEvent:
        return self._growth_service.get_growth_event(event_id)

    def delete_growth_event(self, event_id: str) -> bool:
        return self._growth_service.delete_growth_event(event_id)

    def list_acquisition_proposals(self, **kwargs) -> list[object]:
        return self._acquisition_service.list_acquisition_proposals(**kwargs)

    def get_acquisition_proposal(self, proposal_id: str) -> object:
        return self._acquisition_service.get_acquisition_proposal(proposal_id)

    def delete_acquisition_proposal(self, proposal_id: str) -> bool:
        return self._acquisition_service.delete_acquisition_proposal(proposal_id)

    def ensure_acquisition_task(self, proposal: object) -> object:
        return self._acquisition_service.ensure_acquisition_task(proposal)

    async def approve_acquisition_proposal(
        self,
        proposal_id: str,
        *,
        approved_by: str = "system",
    ) -> dict[str, object]:
        return await self._acquisition_service.approve_acquisition_proposal(
            proposal_id,
            approved_by=approved_by,
        )

    def reject_acquisition_proposal(
        self,
        proposal_id: str,
        *,
        rejected_by: str = "system",
    ) -> dict[str, object]:
        return self._acquisition_service.reject_acquisition_proposal(
            proposal_id,
            rejected_by=rejected_by,
        )

    def list_install_binding_plans(self, **kwargs) -> list[object]:
        return self._acquisition_service.list_install_binding_plans(**kwargs)

    def get_install_binding_plan(self, plan_id: str) -> object:
        return self._acquisition_service.get_install_binding_plan(plan_id)

    def delete_install_binding_plan(self, plan_id: str) -> bool:
        return self._acquisition_service.delete_install_binding_plan(plan_id)

    def list_onboarding_runs(self, **kwargs) -> list[object]:
        return self._acquisition_service.list_onboarding_runs(**kwargs)

    def get_onboarding_run(self, run_id: str) -> object:
        return self._acquisition_service.get_onboarding_run(run_id)

    def delete_onboarding_run(self, run_id: str) -> bool:
        return self._acquisition_service.delete_onboarding_run(run_id)

    async def run_industry_acquisition_cycle(self, **kwargs) -> dict[str, object]:
        return await self._acquisition_service.run_industry_acquisition_cycle(**kwargs)


__all__ = ["LearningService"]
