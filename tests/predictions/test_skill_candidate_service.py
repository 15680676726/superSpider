# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.capabilities.models import CapabilityMount
from copaw.state import SQLiteStateStore
from copaw.state.capability_donor_service import CapabilityDonorService
from copaw.state.capability_portfolio_service import CapabilityPortfolioService
from copaw.state.skill_lifecycle_decision_service import SkillLifecycleDecisionService
from copaw.state.skill_candidate_service import (
    CapabilityCandidateService,
)
from copaw.state.skill_trial_service import SkillTrialService


def _build_service(tmp_path: Path) -> CapabilityCandidateService:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    return CapabilityCandidateService(state_store=store)


def _build_portfolio_services(
    tmp_path: Path,
) -> tuple[
    CapabilityCandidateService,
    CapabilityDonorService,
    SkillTrialService,
    SkillLifecycleDecisionService,
    CapabilityPortfolioService,
]:
    store = SQLiteStateStore(tmp_path / "portfolio.sqlite3")
    donor_service = CapabilityDonorService(state_store=store)
    candidate_service = CapabilityCandidateService(
        state_store=store,
        donor_service=donor_service,
    )
    trial_service = SkillTrialService(state_store=store)
    decision_service = SkillLifecycleDecisionService(state_store=store)
    portfolio_service = CapabilityPortfolioService(
        donor_service=donor_service,
        candidate_service=candidate_service,
        skill_trial_service=trial_service,
        skill_lifecycle_decision_service=decision_service,
    )
    return (
        candidate_service,
        donor_service,
        trial_service,
        decision_service,
        portfolio_service,
    )


def test_capability_candidate_service_normalizes_external_and_local_sources(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    external = service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/research-pack.zip",
        candidate_source_version="1.2.3",
        ingestion_mode="auto-install",
        proposed_skill_name="research_pack",
        summary="Remote research pack candidate.",
    )
    local = service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="local_authored",
        candidate_source_ref=str(tmp_path / "skills" / "research_pack" / "SKILL.md"),
        candidate_source_version="draft-v1",
        ingestion_mode="local-authoring",
        proposed_skill_name="research_pack_local",
        summary="Local authoring candidate.",
    )

    assert external.candidate_id != local.candidate_id
    assert external.candidate_kind == "skill"
    assert external.candidate_source_kind == "external_remote"
    assert external.ingestion_mode == "auto-install"
    assert local.candidate_source_kind == "local_authored"
    assert local.ingestion_mode == "local-authoring"

    stored = service.list_candidates()
    assert [item.candidate_source_kind for item in stored] == [
        "local_authored",
        "external_remote",
    ]


def test_capability_candidate_service_baseline_import_reuses_existing_candidate(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    mount = CapabilityMount(
        id="skill:research",
        name="Research",
        summary="Research bundle",
        kind="skill-bundle",
        source_kind="skill",
        risk_level="guarded",
        enabled=True,
        package_ref="https://example.com/skills/research-pack.zip",
        package_kind="hub-bundle",
        package_version="1.2.3",
    )

    first = service.import_active_baseline_artifacts(
        mounts=[mount],
        target_role_id="researcher",
    )
    second = service.import_active_baseline_artifacts(
        mounts=[mount],
        target_role_id="researcher",
    )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].candidate_id == second[0].candidate_id
    assert first[0].status == "active"
    assert first[0].lifecycle_stage == "baseline"
    assert first[0].ingestion_mode == "baseline-import"
    assert len(service.list_candidates()) == 1


def test_capability_candidate_service_tracks_baseline_protection_and_lineage(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    mount = CapabilityMount(
        id="mcp:browser",
        name="Browser MCP",
        summary="Browser runtime",
        kind="remote-mcp",
        source_kind="mcp",
        risk_level="guarded",
        enabled=True,
        package_ref="registry://browser",
        package_kind="registry",
        package_version="2026.04.03",
        metadata={
            "required_by_role_blueprint": True,
            "protected_from_auto_replace": True,
        },
    )

    imported = service.import_active_baseline_artifacts(
        mounts=[mount],
        target_role_id="operator",
    )[0]

    assert imported.candidate_kind == "mcp-bundle"
    assert imported.protection_flags == [
        "protected_from_auto_replace",
        "required_by_role_blueprint",
    ]
    assert imported.lineage_root_id == imported.candidate_id
    assert imported.candidate_source_kind == "external_catalog"


def test_capability_candidate_service_materializes_donor_truth_and_portfolio_summary(
    tmp_path: Path,
) -> None:
    (
        candidate_service,
        donor_service,
        trial_service,
        decision_service,
        portfolio_service,
    ) = _build_portfolio_services(tmp_path)

    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/research-pack.zip",
        candidate_source_version="1.2.3",
        candidate_source_lineage="candidate:research-pack",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="research_pack",
        summary="Remote research pack candidate.",
    )
    baseline = candidate_service.normalize_candidate_source(
        candidate_kind="mcp-bundle",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="external_catalog",
        candidate_source_ref="registry://browser",
        candidate_source_version="2026.04.04",
        candidate_source_lineage="donor:browser-registry",
        ingestion_mode="baseline-import",
        proposed_skill_name="browser_registry",
        summary="Browser runtime baseline.",
        status="active",
        lifecycle_stage="baseline",
    )
    trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        scope_type="seat",
        scope_ref="seat-1",
        verdict="passed",
        success_count=2,
        summary="Remote donor passed scoped trial.",
    )
    decision_service.create_decision(
        candidate_id=baseline.candidate_id,
        decision_kind="retire",
        from_stage="active",
        to_stage="retired",
        reason="Registry donor is no longer aligned with the target seat.",
    )

    assert candidate.donor_id is not None
    assert candidate.package_id is not None
    assert candidate.source_profile_id is not None
    assert baseline.donor_id is not None
    assert baseline.donor_id != candidate.donor_id

    donors = donor_service.list_donors()
    source_profiles = donor_service.list_source_profiles()
    packages = donor_service.list_packages()
    trust_records = donor_service.list_trust_records()
    portfolio = portfolio_service.summarize_portfolio()

    assert len(donors) == 2
    assert len(source_profiles) == 2
    assert len(packages) == 2
    assert len(trust_records) == 2
    assert {item.trust_posture for item in source_profiles} == {
        "trusted",
        "watchlist",
    }
    donor_by_id = {item.donor_id: item for item in donors}
    package_by_id = {item.package_id: item for item in packages}
    source_profile_by_id = {
        item.source_profile_id: item
        for item in source_profiles
    }
    trust_by_donor_id = {item.donor_id: item for item in trust_records}

    assert donor_by_id[candidate.donor_id].source_kind == "external_remote"
    assert donor_by_id[baseline.donor_id].source_kind == "external_catalog"
    assert donor_by_id[candidate.donor_id].canonical_package_id is not None
    assert donor_by_id[baseline.donor_id].canonical_package_id is not None
    assert (
        donor_by_id[candidate.donor_id].canonical_package_id
        != donor_by_id[baseline.donor_id].canonical_package_id
    )
    assert donor_by_id[candidate.donor_id].candidate_source_lineage == "candidate:research-pack"
    assert donor_by_id[baseline.donor_id].candidate_source_lineage == "donor:browser-registry"
    assert source_profile_by_id[candidate.source_profile_id].source_lineage == "candidate:research-pack"
    assert source_profile_by_id[baseline.source_profile_id].source_lineage == "donor:browser-registry"
    assert (
        "https://example.com/skills/research-pack.zip"
        in donor_by_id[candidate.donor_id].source_aliases
    )
    assert "registry://browser" in donor_by_id[baseline.donor_id].source_aliases
    assert package_by_id[candidate.package_id].canonical_package_id == donor_by_id[candidate.donor_id].canonical_package_id
    assert package_by_id[baseline.package_id].canonical_package_id == donor_by_id[baseline.donor_id].canonical_package_id
    assert trust_by_donor_id[candidate.donor_id].last_candidate_id == candidate.candidate_id
    assert trust_by_donor_id[candidate.donor_id].last_package_id == candidate.package_id
    assert trust_by_donor_id[baseline.donor_id].last_candidate_id == baseline.candidate_id
    assert trust_by_donor_id[baseline.donor_id].last_package_id == baseline.package_id
    assert trust_by_donor_id[baseline.donor_id].last_canonical_package_id == package_by_id[baseline.package_id].canonical_package_id
    assert portfolio["donor_count"] == 2
    assert portfolio["active_donor_count"] == 1
    assert portfolio["candidate_donor_count"] == 1
    assert portfolio["trial_donor_count"] == 1
    assert portfolio["trusted_source_count"] == 1
    assert portfolio["watchlist_source_count"] == 1
    assert portfolio["retire_pressure_count"] == 1
    assert portfolio["degraded_donor_count"] == 0
    assert any(
        item["action"] == "review_retirement_pressure"
        for item in portfolio["planning_actions"]
    )


def test_capability_candidate_service_persists_candidate_attribution_fields(
    tmp_path: Path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.db")
    donor_service = CapabilityDonorService(state_store=state_store)
    candidate_service = CapabilityCandidateService(
        state_store=state_store,
        donor_service=donor_service,
    )

    created = candidate_service.normalize_candidate_source(
        candidate_kind="skill",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/skills/research-pack.zip",
        candidate_source_version="2.4.0",
        candidate_source_lineage="donor:research-pack",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="research_pack",
        summary="Research automation donor candidate.",
        metadata={
            "source_aliases": [
                "https://mirror.example/research-pack.zip",
            ],
            "equivalence_class": "pkg:research-pack",
            "capability_overlap_score": 0.88,
            "replacement_relation": "replace_requested",
        },
    )

    reloaded = candidate_service.list_candidates(limit=1)[0]

    assert created.donor_id is not None
    assert created.package_id is not None
    assert created.source_profile_id is not None
    assert reloaded.canonical_package_id is not None
    assert reloaded.canonical_package_id == created.canonical_package_id
    assert "https://mirror.example/research-pack.zip" in reloaded.source_aliases
    assert "https://example.com/skills/research-pack.zip" in reloaded.source_aliases
    assert reloaded.equivalence_class == "pkg:research-pack"
    assert reloaded.capability_overlap_score == 0.88
    assert reloaded.replacement_relation == "replace_requested"
