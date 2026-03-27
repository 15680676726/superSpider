# -*- coding: utf-8 -*-
from __future__ import annotations

from .acquisition_runtime import LearningAcquisitionRuntimeService
from .models import CapabilityAcquisitionProposal, InstallBindingPlan, OnboardingRun
from .runtime_core import LearningRuntimeCore
from ..state import TaskRecord


class LearningAcquisitionService:
    """Capability acquisition and onboarding operations."""

    def __init__(self, core: LearningRuntimeCore) -> None:
        self._core = core
        self._runtime = LearningAcquisitionRuntimeService(core)

    def list_acquisition_proposals(self, **kwargs) -> list[CapabilityAcquisitionProposal]:
        return self._runtime.list_acquisition_proposals(**kwargs)

    def get_acquisition_proposal(self, proposal_id: str) -> CapabilityAcquisitionProposal:
        return self._runtime.get_acquisition_proposal(proposal_id)

    def delete_acquisition_proposal(self, proposal_id: str) -> bool:
        return self._runtime.delete_acquisition_proposal(proposal_id)

    def ensure_acquisition_task(
        self,
        proposal: CapabilityAcquisitionProposal,
    ) -> TaskRecord:
        return self._runtime._ensure_acquisition_task(proposal)

    async def approve_acquisition_proposal(
        self,
        proposal_id: str,
        *,
        approved_by: str = "system",
    ) -> dict[str, object]:
        return await self._runtime.approve_acquisition_proposal(
            proposal_id,
            approved_by=approved_by,
        )

    def reject_acquisition_proposal(
        self,
        proposal_id: str,
        *,
        rejected_by: str = "system",
    ) -> dict[str, object]:
        return self._runtime.reject_acquisition_proposal(
            proposal_id,
            rejected_by=rejected_by,
        )

    def list_install_binding_plans(self, **kwargs) -> list[InstallBindingPlan]:
        return self._runtime.list_install_binding_plans(**kwargs)

    def get_install_binding_plan(self, plan_id: str) -> InstallBindingPlan:
        return self._runtime.get_install_binding_plan(plan_id)

    def delete_install_binding_plan(self, plan_id: str) -> bool:
        return self._runtime.delete_install_binding_plan(plan_id)

    def list_onboarding_runs(self, **kwargs) -> list[OnboardingRun]:
        return self._runtime.list_onboarding_runs(**kwargs)

    def get_onboarding_run(self, run_id: str) -> OnboardingRun:
        return self._runtime.get_onboarding_run(run_id)

    def delete_onboarding_run(self, run_id: str) -> bool:
        return self._runtime.delete_onboarding_run(run_id)

    async def run_industry_acquisition_cycle(self, **kwargs) -> dict[str, object]:
        return await self._runtime.run_industry_acquisition_cycle(**kwargs)


__all__ = ["LearningAcquisitionService"]
