from __future__ import annotations

from copaw.state.capability_donor_service import CapabilityDonorService
from copaw.state import SQLiteStateStore
from copaw.state.skill_candidate_service import CapabilityCandidateService
from copaw.state.skill_lifecycle_decision_service import (
    SkillLifecycleDecisionService,
)
from copaw.state.skill_trial_service import SkillTrialService


def test_skill_trial_service_creates_and_summarizes_trials(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    candidate_service = CapabilityCandidateService(state_store=state_store)
    trial_service = SkillTrialService(state_store=state_store)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="solution-lead",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/nextgen-outreach.zip",
        candidate_source_version="1.0.0",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="nextgen_outreach",
        summary="Governed remote skill candidate for outreach.",
    )

    created = trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        scope_type="seat",
        scope_ref="seat-primary",
        verdict="passed",
        summary="Primary seat trial completed without operator takeover.",
        task_ids=["task-1", "task-2"],
        evidence_refs=["ev-1"],
        success_count=2,
        failure_count=0,
        handoff_count=0,
        operator_intervention_count=0,
        latency_summary={"avg_seconds": 12.4},
        metadata={"target_agent_id": "industry-solution-lead-demo"},
    )

    listed = trial_service.list_trials(candidate_id=candidate.candidate_id)
    summary = trial_service.summarize_trials(candidate_id=candidate.candidate_id)

    assert created.candidate_id == candidate.candidate_id
    assert listed[0].trial_id == created.trial_id
    assert summary == {
        "candidate_id": candidate.candidate_id,
        "trial_count": 1,
        "success_count": 2,
        "failure_count": 0,
        "handoff_count": 0,
        "operator_intervention_count": 0,
        "verdicts": {"passed": 1},
        "scope_refs": ["seat-primary"],
    }


def test_skill_lifecycle_decision_service_records_candidate_decisions(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    candidate_service = CapabilityCandidateService(state_store=state_store)
    decision_service = SkillLifecycleDecisionService(state_store=state_store)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="solution-lead",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/nextgen-outreach.zip",
        candidate_source_version="1.0.0",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="nextgen_outreach",
        summary="Governed remote skill candidate for outreach.",
    )

    created = decision_service.create_decision(
        candidate_id=candidate.candidate_id,
        decision_kind="promote_to_role",
        from_stage="trial",
        to_stage="active",
        reason="Primary seat trial is stable enough for governed wider rollout.",
        evidence_refs=["ev-1", "ev-2"],
        replacement_target_ids=["skill:legacy_outreach"],
        protection_lifted=False,
        applied_by="prediction-service",
        metadata={"source_recommendation_id": "rec-1"},
    )

    listed = decision_service.list_decisions(candidate_id=candidate.candidate_id)

    assert created.candidate_id == candidate.candidate_id
    assert created.decision_kind == "promote_to_role"
    assert listed[0].decision_id == created.decision_id
    assert listed[0].replacement_target_ids == ["skill:legacy_outreach"]


def test_skill_trial_and_lifecycle_services_persist_donor_attribution(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    donor_service = CapabilityDonorService(state_store=state_store)
    candidate_service = CapabilityCandidateService(
        state_store=state_store,
        donor_service=donor_service,
    )
    trial_service = SkillTrialService(state_store=state_store)
    decision_service = SkillLifecycleDecisionService(state_store=state_store)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="solution-lead",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/nextgen-outreach.zip",
        candidate_source_version="1.0.0",
        candidate_source_lineage="donor:nextgen-outreach",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="nextgen_outreach",
        summary="Governed remote skill candidate for outreach.",
        metadata={
            "source_aliases": ["https://mirror.example/skills/nextgen-outreach.zip"],
            "equivalence_class": "pkg:nextgen-outreach",
            "capability_overlap_score": 0.92,
            "replacement_relation": "replace_requested",
        },
    )

    trial = trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        donor_id=candidate.donor_id,
        package_id=candidate.package_id,
        source_profile_id=candidate.source_profile_id,
        canonical_package_id=candidate.canonical_package_id,
        candidate_source_lineage=candidate.candidate_source_lineage,
        source_aliases=candidate.source_aliases,
        equivalence_class=candidate.equivalence_class,
        capability_overlap_score=candidate.capability_overlap_score,
        replacement_relation=candidate.replacement_relation,
        scope_type="seat",
        scope_ref="seat-primary",
        verdict="passed",
        summary="Primary seat trial completed without operator takeover.",
    )
    decision = decision_service.create_decision(
        candidate_id=candidate.candidate_id,
        donor_id=candidate.donor_id,
        package_id=candidate.package_id,
        source_profile_id=candidate.source_profile_id,
        canonical_package_id=candidate.canonical_package_id,
        candidate_source_lineage=candidate.candidate_source_lineage,
        source_aliases=candidate.source_aliases,
        equivalence_class=candidate.equivalence_class,
        capability_overlap_score=candidate.capability_overlap_score,
        replacement_relation=candidate.replacement_relation,
        decision_kind="retire",
        from_stage="trial",
        to_stage="retired",
        reason="Primary seat trial drifted and should retire.",
        retirement_reason="drift",
        retirement_scope="seat",
        retirement_evidence_refs=["ev-retire"],
    )

    listed_trials = trial_service.list_trials(candidate_id=candidate.candidate_id)
    listed_decisions = decision_service.list_decisions(candidate_id=candidate.candidate_id)

    assert trial.trial_id == listed_trials[0].trial_id
    assert listed_trials[0].donor_id == candidate.donor_id
    assert listed_trials[0].package_id == candidate.package_id
    assert listed_trials[0].source_profile_id == candidate.source_profile_id
    assert listed_trials[0].canonical_package_id == candidate.canonical_package_id
    assert listed_trials[0].candidate_source_lineage == "donor:nextgen-outreach"
    assert "https://mirror.example/skills/nextgen-outreach.zip" in listed_trials[0].source_aliases
    assert "https://example.com/skills/nextgen-outreach.zip" in listed_trials[0].source_aliases
    assert listed_trials[0].equivalence_class == "pkg:nextgen-outreach"
    assert listed_trials[0].capability_overlap_score == 0.92
    assert listed_trials[0].replacement_relation == "replace_requested"

    assert decision.decision_id == listed_decisions[0].decision_id
    assert listed_decisions[0].donor_id == candidate.donor_id
    assert listed_decisions[0].package_id == candidate.package_id
    assert listed_decisions[0].source_profile_id == candidate.source_profile_id
    assert listed_decisions[0].canonical_package_id == candidate.canonical_package_id
    assert listed_decisions[0].candidate_source_lineage == "donor:nextgen-outreach"
    assert "https://mirror.example/skills/nextgen-outreach.zip" in listed_decisions[0].source_aliases
    assert "https://example.com/skills/nextgen-outreach.zip" in listed_decisions[0].source_aliases
    assert listed_decisions[0].equivalence_class == "pkg:nextgen-outreach"
    assert listed_decisions[0].capability_overlap_score == 0.92
    assert listed_decisions[0].replacement_relation == "replace_requested"
    assert listed_decisions[0].retirement_reason == "drift"
    assert listed_decisions[0].retirement_scope == "seat"
    assert listed_decisions[0].retirement_evidence_refs == ["ev-retire"]


def test_skill_trial_service_builds_candidate_verdict_summary_across_scopes(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    candidate_service = CapabilityCandidateService(state_store=state_store)
    trial_service = SkillTrialService(state_store=state_store)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="solution-lead",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/nextgen-outreach.zip",
        candidate_source_version="1.0.0",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="nextgen_outreach",
        summary="Governed remote skill candidate for outreach.",
    )

    trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        scope_type="seat",
        scope_ref="seat-primary",
        verdict="passed",
        success_count=3,
        failure_count=0,
        handoff_count=0,
        operator_intervention_count=0,
        summary="Primary seat trial completed cleanly.",
    )
    trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        scope_type="seat",
        scope_ref="seat-secondary",
        verdict="failed",
        success_count=0,
        failure_count=2,
        handoff_count=1,
        operator_intervention_count=1,
        summary="Secondary seat regressed and needed operator takeover.",
    )

    summary = trial_service.get_candidate_verdict_summary(candidate_id=candidate.candidate_id)

    assert summary["candidate_id"] == candidate.candidate_id
    assert summary["aggregate_verdict"] == "rollback_recommended"
    assert summary["trial_count"] == 2
    assert summary["operator_intervention_count"] == 1
    assert summary["scope_verdicts"] == {
        "seat-primary": "passed",
        "seat-secondary": "failed",
    }


def test_skill_gap_detector_builds_formal_drift_reentry_kinds() -> None:
    from copaw.learning.skill_gap_detector import SkillGapDetector

    detector = SkillGapDetector()

    replacement = detector.build_reentry_summary(
        trial_summary={
            "aggregate_verdict": "rollback_recommended",
            "operator_intervention_count": 1,
            "scope_verdicts": {
                "seat-primary": "passed",
                "seat-secondary": "failed",
            },
            "history": [
                {
                    "entry_kind": "decision",
                    "decision_kind": "rollback",
                    "replacement_target_ids": ["skill:legacy_outreach"],
                },
            ],
        },
        latest_decision_kind="rollback",
    )
    revision = detector.build_reentry_summary(
        trial_summary={
            "aggregate_verdict": "mixed",
            "operator_intervention_count": 1,
            "scope_verdicts": {
                "seat-primary": "passed",
                "session:followup-1": "passed",
            },
            "history": [
                {
                    "entry_kind": "trial",
                    "scope_type": "session",
                    "scope_ref": "followup-1",
                    "verdict": "passed",
                    "operator_intervention_count": 1,
                },
            ],
        },
        latest_decision_kind="continue_trial",
    )
    retirement = detector.build_reentry_summary(
        trial_summary={
            "aggregate_verdict": "passed",
            "operator_intervention_count": 0,
            "scope_verdicts": {
                "seat-primary": "passed",
            },
            "history": [
                {
                    "entry_kind": "decision",
                    "decision_kind": "retire",
                },
            ],
        },
        latest_decision_kind="retire",
    )

    assert replacement["reentry_kind"] == "replacement"
    assert replacement["replacement_pressure"] is True
    assert replacement["revision_pressure"] is False
    assert replacement["retirement_pressure"] is False
    assert "rollback" in replacement["reasons"]

    assert revision["reentry_kind"] == "revision"
    assert revision["revision_pressure"] is True
    assert revision["replacement_pressure"] is False
    assert revision["retirement_pressure"] is False
    assert "human-takeover" in revision["reasons"]

    assert retirement["reentry_kind"] == "retirement"
    assert retirement["retirement_pressure"] is True
    assert retirement["replacement_pressure"] is False
    assert retirement["revision_pressure"] is False


def test_skill_trial_service_preserves_adapter_attribution_metadata_across_updates(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    candidate_service = CapabilityCandidateService(state_store=state_store)
    trial_service = SkillTrialService(state_store=state_store)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="project",
        target_scope="seat",
        target_role_id="execution-core",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://github.com/example/donor-app",
        candidate_source_version="main",
        ingestion_mode="capability-market",
        proposed_skill_name="donor_app",
        summary="Governed external donor candidate.",
    )

    trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        scope_type="seat",
        scope_ref="seat-primary",
        verdict="pending",
        metadata={
            "protocol_surface_kind": "native_mcp",
            "transport_kind": "mcp",
            "compiled_adapter_id": "adapter:demo",
            "compiled_action_ids": ["execute_task"],
        },
    )
    updated = trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        scope_type="seat",
        scope_ref="seat-primary",
        verdict="passed",
        summary="Seat-local adapter trial completed.",
        metadata={
            "selected_adapter_action_id": "execute_task",
        },
    )

    assert updated.metadata["protocol_surface_kind"] == "native_mcp"
    assert updated.metadata["transport_kind"] == "mcp"
    assert updated.metadata["compiled_adapter_id"] == "adapter:demo"
    assert updated.metadata["compiled_action_ids"] == ["execute_task"]
    assert updated.metadata["selected_adapter_action_id"] == "execute_task"


def test_skill_trial_and_lifecycle_services_persist_formal_donor_execution_contract_statuses(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    candidate_service = CapabilityCandidateService(state_store=state_store)
    trial_service = SkillTrialService(state_store=state_store)
    decision_service = SkillLifecycleDecisionService(state_store=state_store)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="adapter",
        target_scope="seat",
        target_role_id="execution-core",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://github.com/example/donor-app",
        candidate_source_version="main",
        ingestion_mode="capability-market",
        proposed_skill_name="donor_app",
        summary="Governed external donor candidate.",
    )

    trial = trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        scope_type="seat",
        scope_ref="seat-primary",
        verdict="passed",
        summary="Seat-local adapter trial completed.",
        verified_stage="adapter_probe_passed",
        provider_resolution_status="resolved",
        compatibility_status="compatible_via_bridge",
    )
    decision = decision_service.create_decision(
        candidate_id=candidate.candidate_id,
        decision_kind="promote_to_role",
        from_stage="trial",
        to_stage="active",
        reason="Provider contract and bridge compatibility are verified.",
        verified_stage="primary_action_verified",
        provider_resolution_status="resolved",
        compatibility_status="compatible_native",
    )

    with state_store.connection() as conn:
        trial_row = conn.execute(
            """
            SELECT verified_stage, provider_resolution_status, compatibility_status
            FROM skill_trials
            WHERE trial_id = ?
            """,
            (trial.trial_id,),
        ).fetchone()
        decision_row = conn.execute(
            """
            SELECT verified_stage, provider_resolution_status, compatibility_status
            FROM skill_lifecycle_decisions
            WHERE decision_id = ?
            """,
            (decision.decision_id,),
        ).fetchone()

    reloaded_trial_service = SkillTrialService(
        state_store=SQLiteStateStore(tmp_path / "state.db"),
    )
    reloaded_decision_service = SkillLifecycleDecisionService(
        state_store=SQLiteStateStore(tmp_path / "state.db"),
    )
    reloaded_trial = reloaded_trial_service.get_trial(
        candidate_id=candidate.candidate_id,
        scope_type="seat",
        scope_ref="seat-primary",
    )
    reloaded_decisions = reloaded_decision_service.list_decisions(
        candidate_id=candidate.candidate_id,
    )

    assert trial_row is not None
    assert trial_row["verified_stage"] == "adapter_probe_passed"
    assert trial_row["provider_resolution_status"] == "resolved"
    assert trial_row["compatibility_status"] == "compatible_via_bridge"
    assert decision_row is not None
    assert decision_row["verified_stage"] == "primary_action_verified"
    assert decision_row["provider_resolution_status"] == "resolved"
    assert decision_row["compatibility_status"] == "compatible_native"
    assert reloaded_trial is not None
    assert reloaded_trial.verified_stage == "adapter_probe_passed"
    assert reloaded_trial.provider_resolution_status == "resolved"
    assert reloaded_trial.compatibility_status == "compatible_via_bridge"
    assert reloaded_decisions[0].decision_id == decision.decision_id
    assert reloaded_decisions[0].verified_stage == "primary_action_verified"
    assert reloaded_decisions[0].provider_resolution_status == "resolved"
    assert reloaded_decisions[0].compatibility_status == "compatible_native"


def test_skill_trial_service_does_not_regress_formal_statuses_from_stale_metadata(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    candidate_service = CapabilityCandidateService(state_store=state_store)
    trial_service = SkillTrialService(state_store=state_store)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="adapter",
        target_scope="seat",
        target_role_id="execution-core",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://github.com/example/donor-app",
        candidate_source_version="main",
        ingestion_mode="capability-market",
        proposed_skill_name="donor_app",
        summary="Governed external donor candidate.",
    )

    trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        scope_type="seat",
        scope_ref="seat-primary",
        verdict="passed",
        verified_stage="adapter_probe_passed",
        provider_resolution_status="resolved",
        compatibility_status="compatible_native",
    )
    updated = trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        scope_type="seat",
        scope_ref="seat-primary",
        verdict="passed",
        summary="Unrelated metadata refresh.",
        metadata={
            "verified_stage": "unverified",
            "provider_resolution_status": "pending",
            "compatibility_status": "blocked_contract_violation",
        },
    )

    assert updated.verified_stage == "adapter_probe_passed"
    assert updated.provider_resolution_status == "resolved"
    assert updated.compatibility_status == "compatible_native"


def test_skill_lifecycle_decision_service_upserts_evaluator_verdict_decisions(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    candidate_service = CapabilityCandidateService(state_store=state_store)
    decision_service = SkillLifecycleDecisionService(state_store=state_store)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="solution-lead",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/nextgen-outreach.zip",
        candidate_source_version="1.0.0",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="nextgen_outreach",
        summary="Governed remote skill candidate for outreach.",
    )

    created = decision_service.upsert_evaluator_verdict_decision(
        candidate_id=candidate.candidate_id,
        aggregate_verdict="passed",
        source_recommendation_id="rec-trial-1",
        reason="Seat-local trial completed cleanly.",
        evidence_refs=["ev-trial-pass"],
        replacement_target_ids=["skill:legacy_outreach"],
        applied_by="prediction-service",
        metadata={"selected_seat_ref": "seat-primary"},
    )

    assert created.decision_kind == "continue_trial"
    assert created.from_stage == "candidate"
    assert created.to_stage == "trial"
    assert created.metadata["evaluator_verdict"] == "passed"
    assert created.metadata["verdict_source"] == "trial_evaluator"

    updated = decision_service.upsert_evaluator_verdict_decision(
        candidate_id=candidate.candidate_id,
        aggregate_verdict="rollback_recommended",
        source_recommendation_id="rec-trial-1",
        reason="Trial regressed and now requires rollback.",
        evidence_refs=["ev-trial-fail"],
        replacement_target_ids=["skill:legacy_outreach"],
        applied_by="prediction-service",
        metadata={"selected_seat_ref": "seat-primary"},
    )

    listed = decision_service.list_decisions(candidate_id=candidate.candidate_id)

    assert updated.decision_id == created.decision_id
    assert updated.decision_kind == "rollback"
    assert updated.from_stage == "trial"
    assert updated.to_stage == "blocked"
    assert updated.evidence_refs == ["ev-trial-fail"]
    assert updated.metadata["evaluator_verdict"] == "rollback_recommended"
    assert len(listed) == 1
