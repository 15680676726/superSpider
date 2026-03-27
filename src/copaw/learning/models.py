# -*- coding: utf-8 -*-
"""Learning & optimization layer — Layer 7 of the 7-layer architecture.

Models for proposals, patches, and growth tracking.
Based on AGENTS.md §11:
- Discover bottlenecks
- Generate proposals
- Produce patches
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from ..industry.models import IndustryBootstrapInstallItem, IndustryBootstrapInstallResult


PatchKind = Literal["profile_patch", "role_patch", "capability_patch", "plan_patch"]
PatchStatus = Literal["proposed", "approved", "applied", "rejected", "rolled_back"]
ProposalStatus = Literal["open", "accepted", "rejected", "deferred"]
AcquisitionKind = Literal["install-capability", "create-sop-binding"]
CapabilityAcquisitionProposalStatus = Literal[
    "open",
    "materialized",
    "applied",
    "blocked",
    "skipped",
    "rejected",
]
InstallBindingPlanStatus = Literal["pending", "applied", "blocked", "failed"]
OnboardingRunStatus = Literal["running", "passed", "failed"]


class Proposal(BaseModel):
    """A suggestion for system improvement."""

    id: str = Field(default_factory=lambda: f"proposal:{uuid4().hex[:12]}")
    title: str
    description: str
    source_agent_id: str = "copaw-agent-runner"
    goal_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    target_layer: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    status: ProposalStatus = "open"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class Patch(BaseModel):
    """A concrete change to apply to the system."""

    id: str = Field(default_factory=lambda: f"patch:{uuid4().hex[:12]}")
    kind: PatchKind
    proposal_id: str | None = None
    goal_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    title: str
    description: str
    diff_summary: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    source_evidence_id: str | None = None
    risk_level: str = "auto"
    status: PatchStatus = "proposed"
    applied_at: datetime | None = None
    applied_by: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class GrowthEvent(BaseModel):
    """A recorded change in an agent's capabilities or behavior."""

    id: str = Field(default_factory=lambda: f"growth:{uuid4().hex[:12]}")
    agent_id: str
    goal_id: str | None = None
    task_id: str | None = None
    change_type: str = Field(
        ...,
        description="e.g. 'capability_added', 'role_changed', 'patch_applied', 'performance_improved'",
    )
    description: str
    source_patch_id: str | None = None
    source_evidence_id: str | None = None
    risk_level: str = "auto"
    result: str = ""
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class CapabilityAcquisitionProposal(BaseModel):
    """A persisted proposal to acquire a missing install or SOP binding."""

    id: str = Field(default_factory=lambda: f"acq-proposal:{uuid4().hex[:12]}")
    proposal_key: str
    industry_instance_id: str
    owner_scope: str | None = None
    target_agent_id: str | None = None
    target_role_id: str | None = None
    acquisition_kind: AcquisitionKind
    title: str
    summary: str = ""
    risk_level: str = "guarded"
    status: CapabilityAcquisitionProposalStatus = "open"
    install_item: IndustryBootstrapInstallItem | None = None
    binding_request: dict[str, Any] | None = None
    decision_request_id: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejected_by: str | None = None
    rejected_at: datetime | None = None
    discovery_signals: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class InstallBindingPlan(BaseModel):
    """A materialized plan created from an acquisition proposal."""

    id: str = Field(default_factory=lambda: f"acq-plan:{uuid4().hex[:12]}")
    proposal_id: str
    industry_instance_id: str
    target_agent_id: str | None = None
    target_role_id: str | None = None
    risk_level: str = "guarded"
    status: InstallBindingPlanStatus = "pending"
    install_item: IndustryBootstrapInstallItem | None = None
    binding_request: dict[str, Any] | None = None
    install_result: IndustryBootstrapInstallResult | None = None
    binding_id: str | None = None
    doctor_status: str | None = None
    blocked_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    applied_at: datetime | None = None
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class OnboardingRun(BaseModel):
    """Verification run after a plan has been materialized."""

    id: str = Field(default_factory=lambda: f"onboarding:{uuid4().hex[:12]}")
    plan_id: str
    proposal_id: str
    industry_instance_id: str
    target_agent_id: str | None = None
    target_role_id: str | None = None
    status: OnboardingRunStatus = "running"
    summary: str = ""
    checks: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    completed_at: datetime | None = None
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
