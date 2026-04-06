# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from copaw.state import (
    CapabilityCandidateRecord,
    CapabilityDonorService,
    SQLiteStateStore,
    SkillLifecycleDecisionRecord,
    SkillTrialRecord,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_capability_evolution_records_accept_normalized_attribution_fields() -> None:
    candidate = CapabilityCandidateRecord(
        candidate_kind="skill",
        target_scope="seat",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/research-pack.zip",
        candidate_source_version="1.2.3",
        candidate_source_lineage="donor:research-pack",
        canonical_package_id="pkg:research-pack",
        source_aliases=[
            "registry://research-pack",
            "mirror://research-pack",
        ],
        equivalence_class="eq:research-pack",
        capability_overlap_score=0.82,
        replacement_relation="replace_existing",
    )
    trial = SkillTrialRecord(
        candidate_id=candidate.candidate_id,
        scope_ref="seat-1",
        donor_id="donor-1",
        package_id="package-1",
        source_profile_id="source-1",
        canonical_package_id="pkg:research-pack",
        candidate_source_lineage="donor:research-pack",
        equivalence_class="eq:research-pack",
        capability_overlap_score=0.82,
        replacement_relation="replace_existing",
    )
    decision = SkillLifecycleDecisionRecord(
        candidate_id=candidate.candidate_id,
        decision_kind="retire",
        donor_id="donor-1",
        package_id="package-1",
        source_profile_id="source-1",
        canonical_package_id="pkg:research-pack",
        candidate_source_lineage="donor:research-pack",
        equivalence_class="eq:research-pack",
        capability_overlap_score=0.82,
        replacement_relation="replace_existing",
        retirement_reason="Superseded by a curated donor.",
        retirement_scope="seat",
        retirement_evidence_refs=["evidence:retire-1"],
    )

    assert candidate.canonical_package_id == "pkg:research-pack"
    assert candidate.source_aliases == [
        "registry://research-pack",
        "mirror://research-pack",
    ]
    assert candidate.equivalence_class == "eq:research-pack"
    assert candidate.capability_overlap_score == 0.82
    assert candidate.replacement_relation == "replace_existing"
    assert trial.donor_id == "donor-1"
    assert trial.canonical_package_id == "pkg:research-pack"
    assert trial.equivalence_class == "eq:research-pack"
    assert decision.retirement_reason == "Superseded by a curated donor."
    assert decision.retirement_scope == "seat"
    assert decision.retirement_evidence_refs == ["evidence:retire-1"]


def test_capability_donor_service_roundtrips_normalized_donor_truth(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    donor_service = CapabilityDonorService(state_store=store)
    candidate = CapabilityCandidateRecord(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        status="candidate",
        lifecycle_stage="candidate",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/research-pack.zip",
        candidate_source_version="1.2.3",
        candidate_source_lineage="donor:research-pack",
        canonical_package_id="pkg:research-pack",
        source_aliases=[
            "registry://research-pack",
            "mirror://research-pack",
        ],
        equivalence_class="eq:research-pack",
        replacement_relation="replace_existing",
        proposed_skill_name="research_pack",
    )

    donor_id, package_id, source_profile_id = donor_service.register_candidate_source(
        candidate,
    )

    donor = donor_service.list_donors()[0]
    package = donor_service.list_packages()[0]
    source_profile = donor_service.list_source_profiles()[0]
    trust = donor_service.list_trust_records()[0]

    assert donor.donor_id == donor_id
    assert donor.canonical_package_id == "pkg:research-pack"
    assert donor.source_aliases == [
        "registry://research-pack",
        "mirror://research-pack",
        "https://example.com/skills/research-pack.zip",
    ]
    assert donor.equivalence_class == "eq:research-pack"
    assert donor.replacement_relation == "replace_existing"
    assert package.package_id == package_id
    assert package.canonical_package_id == "pkg:research-pack"
    assert package.equivalence_class == "eq:research-pack"
    assert source_profile.source_profile_id == source_profile_id
    assert source_profile.source_lineage == "donor:research-pack"
    assert source_profile.source_aliases == [
        "registry://research-pack",
        "mirror://research-pack",
        "https://example.com/skills/research-pack.zip",
    ]
    assert trust.last_candidate_id == candidate.candidate_id
    assert trust.last_package_id == package_id
    assert trust.last_canonical_package_id == "pkg:research-pack"


def test_capability_donor_service_persists_donor_execution_contract_snapshot_on_package(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    donor_service = CapabilityDonorService(state_store=store)
    candidate = CapabilityCandidateRecord(
        candidate_kind="adapter",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        status="candidate",
        lifecycle_stage="trial",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/adapters/openspace.zip",
        candidate_source_version="1.2.3",
        candidate_source_lineage="donor:openspace",
        canonical_package_id="pkg:openspace",
        proposed_skill_name="openspace_adapter",
        metadata={
            "provider_injection_mode": "environment",
            "execution_envelope": {
                "action_timeout_sec": 45,
                "probe_timeout_sec": 12,
            },
            "host_compatibility_requirements": {
                "required_provider_contract_kind": "cooperative_provider_runtime",
                "required_runtimes": ["python"],
            },
        },
    )

    _donor_id, package_id, _source_profile_id = donor_service.register_candidate_source(
        candidate,
    )

    package = next(item for item in donor_service.list_packages() if item.package_id == package_id)

    assert package.metadata["provider_injection_mode"] == "environment"
    assert package.metadata["execution_envelope"]["action_timeout_sec"] == 45
    assert (
        package.metadata["host_compatibility_requirements"][
            "required_provider_contract_kind"
        ]
        == "cooperative_provider_runtime"
    )


def test_state_store_accepts_new_candidate_trial_and_lifecycle_columns(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    store.initialize()
    now = _utc_now()

    with store.connection() as conn:
        conn.execute(
            """
            INSERT INTO capability_candidates (
                candidate_id,
                candidate_kind,
                target_scope,
                status,
                lifecycle_stage,
                candidate_source_kind,
                candidate_source_ref,
                candidate_source_version,
                candidate_source_lineage,
                canonical_package_id,
                source_aliases_json,
                equivalence_class,
                capability_overlap_score,
                replacement_relation,
                ingestion_mode,
                summary,
                replacement_target_ids_json,
                rollback_target_ids_json,
                required_capability_ids_json,
                required_mcp_ids_json,
                protection_flags_json,
                success_criteria_json,
                rollback_criteria_json,
                source_task_ids_json,
                evidence_refs_json,
                version,
                supersedes_json,
                superseded_by_json,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]', '[]', '[]', '[]', '[]', '[]', '[]', '[]', 'v1', '[]', '[]', '{}', ?, ?)
            """,
            (
                "candidate-1",
                "skill",
                "seat",
                "candidate",
                "trial",
                "external_remote",
                "https://example.com/skills/research-pack.zip",
                "1.2.3",
                "donor:research-pack",
                "pkg:research-pack",
                '["registry://research-pack","mirror://research-pack"]',
                "eq:research-pack",
                0.82,
                "replace_existing",
                "manual",
                "Candidate",
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO skill_trials (
                trial_id,
                candidate_id,
                donor_id,
                package_id,
                source_profile_id,
                canonical_package_id,
                candidate_source_lineage,
                equivalence_class,
                capability_overlap_score,
                replacement_relation,
                scope_type,
                scope_ref,
                verdict,
                summary,
                task_ids_json,
                evidence_refs_json,
                success_count,
                failure_count,
                handoff_count,
                operator_intervention_count,
                latency_summary_json,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]', ?, ?, ?, ?, '{}', '{}', ?, ?)
            """,
            (
                "trial-1",
                "candidate-1",
                "donor-1",
                "package-1",
                "source-1",
                "pkg:research-pack",
                "donor:research-pack",
                "eq:research-pack",
                0.82,
                "replace_existing",
                "seat",
                "seat-1",
                "passed",
                "Trial",
                2,
                0,
                0,
                0,
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO skill_lifecycle_decisions (
                decision_id,
                candidate_id,
                donor_id,
                package_id,
                source_profile_id,
                canonical_package_id,
                candidate_source_lineage,
                equivalence_class,
                capability_overlap_score,
                replacement_relation,
                decision_kind,
                from_stage,
                to_stage,
                reason,
                retirement_reason,
                retirement_scope,
                evidence_refs_json,
                retirement_evidence_refs_json,
                replacement_target_ids_json,
                protection_lifted,
                applied_by,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', '["evidence:retire-1"]', '[]', ?, ?, '{}', ?, ?)
            """,
            (
                "decision-1",
                "candidate-1",
                "donor-1",
                "package-1",
                "source-1",
                "pkg:research-pack",
                "donor:research-pack",
                "eq:research-pack",
                0.82,
                "replace_existing",
                "retire",
                "trial",
                "retired",
                "Retire candidate",
                "Superseded by curated donor",
                "seat",
                0,
                "main-brain",
                now,
                now,
            ),
        )
        candidate_row = conn.execute(
            """
            SELECT canonical_package_id, source_aliases_json, equivalence_class, capability_overlap_score, replacement_relation
            FROM capability_candidates
            WHERE candidate_id = 'candidate-1'
            """,
        ).fetchone()
        trial_row = conn.execute(
            """
            SELECT donor_id, package_id, source_profile_id, canonical_package_id, candidate_source_lineage, equivalence_class, capability_overlap_score, replacement_relation
            FROM skill_trials
            WHERE trial_id = 'trial-1'
            """,
        ).fetchone()
        decision_row = conn.execute(
            """
            SELECT donor_id, package_id, source_profile_id, canonical_package_id, candidate_source_lineage, equivalence_class, capability_overlap_score, replacement_relation, retirement_reason, retirement_scope, retirement_evidence_refs_json
            FROM skill_lifecycle_decisions
            WHERE decision_id = 'decision-1'
            """,
        ).fetchone()

    assert candidate_row["canonical_package_id"] == "pkg:research-pack"
    assert candidate_row["source_aliases_json"] == '["registry://research-pack","mirror://research-pack"]'
    assert candidate_row["equivalence_class"] == "eq:research-pack"
    assert candidate_row["capability_overlap_score"] == 0.82
    assert candidate_row["replacement_relation"] == "replace_existing"
    assert trial_row["donor_id"] == "donor-1"
    assert trial_row["canonical_package_id"] == "pkg:research-pack"
    assert trial_row["candidate_source_lineage"] == "donor:research-pack"
    assert decision_row["retirement_reason"] == "Superseded by curated donor"
    assert decision_row["retirement_scope"] == "seat"
    assert decision_row["retirement_evidence_refs_json"] == '["evidence:retire-1"]'
