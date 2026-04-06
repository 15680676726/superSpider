# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.state.capability_donor_service import CapabilityDonorService
from copaw.state.donor_trust_service import DonorTrustService
from copaw.state.skill_candidate_service import CapabilityCandidateService
from copaw.state.skill_lifecycle_decision_service import SkillLifecycleDecisionService
from copaw.state.skill_trial_service import SkillTrialService
from copaw.state.store import SQLiteStateStore


def test_donor_trust_service_refreshes_trial_and_retirement_pressure(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    donor_service = CapabilityDonorService(state_store=store)
    candidate_service = CapabilityCandidateService(
        state_store=store,
        donor_service=donor_service,
    )
    trial_service = SkillTrialService(state_store=store)
    decision_service = SkillLifecycleDecisionService(state_store=store)
    trust_service = DonorTrustService(
        donor_service=donor_service,
        skill_trial_service=trial_service,
        skill_lifecycle_decision_service=decision_service,
    )

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/research-pack.zip",
        candidate_source_version="1.0.0",
        candidate_source_lineage="donor:research-pack",
        ingestion_mode="discovery",
        proposed_skill_name="research_pack",
        summary="Research pack donor.",
        status="active",
        lifecycle_stage="active",
    )
    trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        donor_id=candidate.donor_id,
        package_id=candidate.package_id,
        source_profile_id=candidate.source_profile_id,
        scope_type="seat",
        scope_ref="seat-1",
        verdict="failed",
        success_count=1,
        failure_count=3,
    )
    decision_service.create_decision(
        candidate_id=candidate.candidate_id,
        donor_id=candidate.donor_id,
        package_id=candidate.package_id,
        source_profile_id=candidate.source_profile_id,
        decision_kind="retire",
        from_stage="active",
        to_stage="retired",
        reason="Repeated failures.",
    )

    refreshed = trust_service.refresh_trust_records()
    summary = trust_service.summarize_trust()

    assert len(refreshed) == 1
    assert refreshed[0].trial_failure_count == 3
    assert refreshed[0].retirement_count == 1
    assert refreshed[0].trust_status == "retired"
    assert summary["retired_count"] == 1


def test_donor_trust_service_marks_blocked_when_compatibility_is_blocked(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    donor_service = CapabilityDonorService(state_store=store)
    candidate_service = CapabilityCandidateService(
        state_store=store,
        donor_service=donor_service,
    )
    trial_service = SkillTrialService(state_store=store)
    trust_service = DonorTrustService(
        donor_service=donor_service,
        skill_trial_service=trial_service,
        skill_lifecycle_decision_service=SkillLifecycleDecisionService(state_store=store),
    )

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="adapter",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/adapters/openspace.zip",
        candidate_source_version="1.0.0",
        candidate_source_lineage="donor:openspace",
        ingestion_mode="discovery",
        proposed_skill_name="openspace_adapter",
        summary="OpenSpace adapter donor.",
    )
    trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        donor_id=candidate.donor_id,
        package_id=candidate.package_id,
        source_profile_id=candidate.source_profile_id,
        scope_type="seat",
        scope_ref="seat-1",
        verdict="failed",
        failure_count=1,
        compatibility_status="blocked_missing_provider_contract",
    )

    refreshed = trust_service.refresh_trust_records()

    assert len(refreshed) == 1
    assert refreshed[0].trust_status == "blocked"
    assert refreshed[0].metadata["last_compatibility_status"] == "blocked_missing_provider_contract"
