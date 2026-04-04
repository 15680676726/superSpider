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
    portfolio = portfolio_service.summarize_portfolio()

    assert len(donors) == 2
    assert len(source_profiles) == 2
    assert len(packages) == 2
    assert {item.trust_posture for item in source_profiles} == {
        "trusted",
        "watchlist",
    }
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
