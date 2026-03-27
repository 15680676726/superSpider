# -*- coding: utf-8 -*-
"""Persistent learning engine for proposals, patches, and growth."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from ..constant import WORKING_DIR
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
from .storage import LearningStorageError, SqliteLearningStore

logger = logging.getLogger(__name__)

DEFAULT_LEARNING_DB_PATH = WORKING_DIR / "learning" / "phase1.sqlite3"


class LearningEngine:
    """Manage proposal, patch, and growth records in persistent storage."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self._store = SqliteLearningStore(database_path or DEFAULT_LEARNING_DB_PATH)

    @property
    def database_path(self) -> Path:
        return self._store.database_path

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
        """Create and persist a new improvement proposal."""
        proposal = Proposal(
            title=title,
            description=description,
            source_agent_id=source_agent_id,
            goal_id=goal_id,
            task_id=task_id,
            agent_id=agent_id,
            target_layer=target_layer,
            evidence_refs=evidence_refs or [],
        )
        self._store.save_proposal(proposal, action="created")
        logger.info("Learning proposal created: %s", proposal.id)
        return proposal

    def accept_proposal(self, proposal_id: str) -> Proposal:
        proposal = self._get_proposal(proposal_id)
        accepted = proposal.model_copy(update={"status": "accepted"})
        self._store.save_proposal(accepted, action="accepted")
        logger.info("Learning proposal accepted: %s", proposal_id)
        return accepted

    def reject_proposal(self, proposal_id: str) -> Proposal:
        proposal = self._get_proposal(proposal_id)
        rejected = proposal.model_copy(update={"status": "rejected"})
        self._store.save_proposal(rejected, action="rejected")
        logger.info("Learning proposal rejected: %s", proposal_id)
        return rejected

    def list_proposals(
        self,
        *,
        status: ProposalStatus | str | None = None,
        created_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Proposal]:
        return self._store.list_proposals(
            status=status,
            created_since=created_since,
            limit=limit,
        )

    def delete_proposal(self, proposal_id: str) -> bool:
        deleted = self._store.delete_proposal(proposal_id)
        if deleted:
            logger.info("Learning proposal deleted: %s", proposal_id)
        return deleted

    def create_patch(self, *, patch: Patch) -> Patch:
        """Persist a new patch proposal without applying it."""
        self._store.save_patch(patch, action="created")
        logger.info("Learning patch created: %s", patch.id)
        return patch

    def apply_patch(self, patch_id: str, *, applied_by: str = "system") -> Patch:
        """Mark a patch as applied after approval checks."""
        patch = self._get_patch(patch_id)
        if patch.risk_level == "confirm" and patch.status == "proposed":
            raise ValueError(
                f"Patch {patch_id} has risk_level=confirm and must be approved before applying.",
            )
        applied = patch.model_copy(
            update={
                "status": "applied",
                "applied_at": datetime.now(timezone.utc),
                "applied_by": applied_by,
            },
        )
        self._store.save_patch(applied, action="applied")
        logger.info("Learning patch applied: %s", patch_id)
        return applied

    def approve_patch(self, patch_id: str) -> Patch:
        patch = self._get_patch(patch_id)
        approved = patch.model_copy(update={"status": "approved"})
        self._store.save_patch(approved, action="approved")
        logger.info("Learning patch approved: %s", patch_id)
        return approved

    def reject_patch(self, patch_id: str) -> Patch:
        patch = self._get_patch(patch_id)
        rejected = patch.model_copy(update={"status": "rejected"})
        self._store.save_patch(rejected, action="rejected")
        logger.info("Learning patch rejected: %s", patch_id)
        return rejected

    def rollback_patch(self, patch_id: str) -> Patch:
        patch = self._get_patch(patch_id)
        rolled_back = patch.model_copy(update={"status": "rolled_back"})
        self._store.save_patch(rolled_back, action="rolled_back")
        logger.info("Learning patch rolled back: %s", patch_id)
        return rolled_back

    def list_patches(
        self,
        *,
        status: PatchStatus | str | None = None,
        created_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Patch]:
        return self._store.list_patches(
            status=status,
            created_since=created_since,
            limit=limit,
        )

    def delete_patch(self, patch_id: str) -> bool:
        deleted = self._store.delete_patch(patch_id)
        if deleted:
            logger.info("Learning patch deleted: %s", patch_id)
        return deleted

    def get_patch(self, patch_id: str) -> Patch:
        return self._get_patch(patch_id)

    def record_growth(self, event: GrowthEvent) -> GrowthEvent:
        """Persist a growth event derived from proposals or patches."""
        self._store.save_growth_event(event, action="recorded")
        logger.info("Learning growth event recorded: %s", event.id)
        return event

    def get_growth_history(
        self,
        *,
        agent_id: str | None = None,
        created_since: datetime | None = None,
        limit: int | None = 50,
    ) -> list[GrowthEvent]:
        return self._store.list_growth_events(
            agent_id=agent_id,
            created_since=created_since,
            limit=limit,
        )

    def delete_growth_event(self, event_id: str) -> bool:
        deleted = self._store.delete_growth_event(event_id)
        if deleted:
            logger.info("Learning growth event deleted: %s", event_id)
        return deleted

    def get_growth_event(self, event_id: str) -> GrowthEvent:
        event = self._store.get_growth_event(event_id)
        if event is None:
            raise KeyError(f"Growth event '{event_id}' not found")
        return event

    def save_acquisition_proposal(
        self,
        proposal: CapabilityAcquisitionProposal,
        *,
        action: str = "saved",
    ) -> CapabilityAcquisitionProposal:
        self._store.save_acquisition_proposal(proposal, action=action)
        logger.info("Capability acquisition proposal saved: %s", proposal.id)
        return proposal

    def get_acquisition_proposal(
        self,
        proposal_id: str,
    ) -> CapabilityAcquisitionProposal:
        proposal = self._store.get_acquisition_proposal(proposal_id)
        if proposal is None:
            raise KeyError(f"Capability acquisition proposal '{proposal_id}' not found")
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
        return self._store.list_acquisition_proposals(
            industry_instance_id=industry_instance_id,
            status=status,
            target_agent_id=target_agent_id,
            target_role_id=target_role_id,
            acquisition_kind=acquisition_kind,
            limit=limit,
        )

    def delete_acquisition_proposal(self, proposal_id: str) -> bool:
        deleted = self._store.delete_acquisition_proposal(proposal_id)
        if deleted:
            logger.info("Capability acquisition proposal deleted: %s", proposal_id)
        return deleted

    def save_install_binding_plan(
        self,
        plan: InstallBindingPlan,
        *,
        action: str = "saved",
    ) -> InstallBindingPlan:
        self._store.save_install_binding_plan(plan, action=action)
        logger.info("Install/binding plan saved: %s", plan.id)
        return plan

    def get_install_binding_plan(self, plan_id: str) -> InstallBindingPlan:
        plan = self._store.get_install_binding_plan(plan_id)
        if plan is None:
            raise KeyError(f"Install/binding plan '{plan_id}' not found")
        return plan

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
        return self._store.list_install_binding_plans(
            proposal_id=proposal_id,
            industry_instance_id=industry_instance_id,
            status=status,
            target_agent_id=target_agent_id,
            target_role_id=target_role_id,
            limit=limit,
        )

    def delete_install_binding_plan(self, plan_id: str) -> bool:
        deleted = self._store.delete_install_binding_plan(plan_id)
        if deleted:
            logger.info("Install/binding plan deleted: %s", plan_id)
        return deleted

    def save_onboarding_run(
        self,
        run: OnboardingRun,
        *,
        action: str = "saved",
    ) -> OnboardingRun:
        self._store.save_onboarding_run(run, action=action)
        logger.info("Onboarding run saved: %s", run.id)
        return run

    def get_onboarding_run(self, run_id: str) -> OnboardingRun:
        run = self._store.get_onboarding_run(run_id)
        if run is None:
            raise KeyError(f"Onboarding run '{run_id}' not found")
        return run

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
        return self._store.list_onboarding_runs(
            plan_id=plan_id,
            proposal_id=proposal_id,
            industry_instance_id=industry_instance_id,
            status=status,
            target_agent_id=target_agent_id,
            target_role_id=target_role_id,
            limit=limit,
        )

    def delete_onboarding_run(self, run_id: str) -> bool:
        deleted = self._store.delete_onboarding_run(run_id)
        if deleted:
            logger.info("Onboarding run deleted: %s", run_id)
        return deleted

    def _get_proposal(self, proposal_id: str) -> Proposal:
        proposal = self._store.get_proposal(proposal_id)
        if proposal is None:
            raise KeyError(f"Proposal '{proposal_id}' not found")
        return proposal

    def _get_patch(self, patch_id: str) -> Patch:
        patch = self._store.get_patch(patch_id)
        if patch is None:
            raise KeyError(f"Patch '{patch_id}' not found")
        return patch


__all__ = [
    "DEFAULT_LEARNING_DB_PATH",
    "LearningEngine",
    "LearningStorageError",
]
