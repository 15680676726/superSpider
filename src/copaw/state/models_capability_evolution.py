# -*- coding: utf-8 -*-
"""Formal capability-evolution state records."""
from __future__ import annotations

from typing import Any

from pydantic import Field

from .model_support import UpdatedRecord, _new_record_id


class CapabilityCandidateRecord(UpdatedRecord):
    """Top-level governed capability-evolution candidate truth."""

    candidate_id: str = Field(default_factory=_new_record_id, min_length=1)
    donor_id: str | None = None
    package_id: str | None = None
    source_profile_id: str | None = None
    canonical_package_id: str | None = None
    candidate_kind: str = Field(default="skill", min_length=1)
    industry_instance_id: str | None = None
    target_role_id: str | None = None
    target_seat_ref: str | None = None
    target_scope: str = Field(default="seat", min_length=1)
    status: str = Field(default="candidate", min_length=1)
    lifecycle_stage: str = Field(default="candidate", min_length=1)
    candidate_source_kind: str = Field(default="local_authored", min_length=1)
    candidate_source_ref: str | None = None
    candidate_source_version: str | None = None
    candidate_source_lineage: str | None = None
    source_aliases: list[str] = Field(default_factory=list)
    equivalence_class: str | None = None
    capability_overlap_score: float | None = None
    replacement_relation: str | None = None
    ingestion_mode: str = Field(default="manual", min_length=1)
    proposed_skill_name: str | None = None
    summary: str = ""
    replacement_target_ids: list[str] = Field(default_factory=list)
    rollback_target_ids: list[str] = Field(default_factory=list)
    required_capability_ids: list[str] = Field(default_factory=list)
    required_mcp_ids: list[str] = Field(default_factory=list)
    protection_flags: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    rollback_criteria: list[str] = Field(default_factory=list)
    source_task_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    version: str = Field(default="v1", min_length=1)
    lineage_root_id: str | None = None
    supersedes: list[str] = Field(default_factory=list)
    superseded_by: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillTrialRecord(UpdatedRecord):
    """Formal trial truth for a candidate on a specific runtime scope."""

    trial_id: str = Field(default_factory=_new_record_id, min_length=1)
    candidate_id: str = Field(..., min_length=1)
    donor_id: str | None = None
    package_id: str | None = None
    source_profile_id: str | None = None
    canonical_package_id: str | None = None
    candidate_source_lineage: str | None = None
    source_aliases: list[str] = Field(default_factory=list)
    equivalence_class: str | None = None
    capability_overlap_score: float | None = None
    replacement_relation: str | None = None
    scope_type: str = Field(default="seat", min_length=1)
    scope_ref: str = Field(..., min_length=1)
    verdict: str = Field(default="pending", min_length=1)
    summary: str = ""
    task_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    handoff_count: int = 0
    operator_intervention_count: int = 0
    latency_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillLifecycleDecisionRecord(UpdatedRecord):
    """Formal lifecycle decision log for capability-evolution governance."""

    decision_id: str = Field(default_factory=_new_record_id, min_length=1)
    candidate_id: str = Field(..., min_length=1)
    donor_id: str | None = None
    package_id: str | None = None
    source_profile_id: str | None = None
    canonical_package_id: str | None = None
    candidate_source_lineage: str | None = None
    source_aliases: list[str] = Field(default_factory=list)
    equivalence_class: str | None = None
    capability_overlap_score: float | None = None
    replacement_relation: str | None = None
    decision_kind: str = Field(default="continue_trial", min_length=1)
    from_stage: str | None = None
    to_stage: str | None = None
    reason: str = ""
    retirement_reason: str | None = None
    retirement_scope: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    retirement_evidence_refs: list[str] = Field(default_factory=list)
    replacement_target_ids: list[str] = Field(default_factory=list)
    protection_lifted: bool = False
    applied_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityDonorRecord(UpdatedRecord):
    """Formal donor truth backing external capability assimilation."""

    donor_id: str = Field(default_factory=_new_record_id, min_length=1)
    donor_kind: str = Field(default="skill", min_length=1)
    normalized_key: str = Field(..., min_length=1)
    canonical_package_id: str | None = None
    source_kind: str = Field(default="local_authored", min_length=1)
    primary_source_ref: str | None = None
    candidate_source_lineage: str | None = None
    source_aliases: list[str] = Field(default_factory=list)
    equivalence_class: str | None = None
    replacement_relation: str | None = None
    display_name: str | None = None
    status: str = Field(default="candidate", min_length=1)
    trust_status: str = Field(default="observing", min_length=1)
    package_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityPackageRecord(UpdatedRecord):
    """Formal package truth attached to a donor."""

    package_id: str = Field(default_factory=_new_record_id, min_length=1)
    donor_id: str = Field(..., min_length=1)
    source_profile_id: str | None = None
    canonical_package_id: str | None = None
    package_ref: str | None = None
    package_version: str | None = None
    source_aliases: list[str] = Field(default_factory=list)
    equivalence_class: str | None = None
    package_kind: str = Field(default="package", min_length=1)
    status: str = Field(default="available", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilitySourceProfileRecord(UpdatedRecord):
    """Governed source-chain/trust posture for a donor source."""

    source_profile_id: str = Field(default_factory=_new_record_id, min_length=1)
    source_kind: str = Field(default="local_authored", min_length=1)
    source_key: str = Field(..., min_length=1)
    source_lineage: str | None = None
    source_aliases: list[str] = Field(default_factory=list)
    display_name: str | None = None
    trust_posture: str = Field(default="watchlist", min_length=1)
    active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityDonorTrustRecord(UpdatedRecord):
    """Governance memory that tracks donor trust and lifecycle pressure."""

    donor_id: str = Field(..., min_length=1)
    source_profile_id: str | None = None
    last_candidate_id: str | None = None
    last_package_id: str | None = None
    last_canonical_package_id: str | None = None
    trust_status: str = Field(default="observing", min_length=1)
    trial_success_count: int = 0
    trial_failure_count: int = 0
    underperformance_count: int = 0
    rollback_count: int = 0
    replacement_pressure_count: int = 0
    retirement_count: int = 0
    last_trial_verdict: str | None = None
    last_decision_kind: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "CapabilityCandidateRecord",
    "CapabilityDonorRecord",
    "CapabilityDonorTrustRecord",
    "CapabilityPackageRecord",
    "CapabilitySourceProfileRecord",
    "SkillLifecycleDecisionRecord",
    "SkillTrialRecord",
]
