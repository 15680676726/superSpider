# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.discovery.deduplication import normalize_discovery_hits
from copaw.discovery.models import DiscoveryHit
from copaw.state.capability_donor_service import CapabilityDonorService
from copaw.state.capability_portfolio_service import CapabilityPortfolioService
from copaw.state.skill_candidate_service import CapabilityCandidateService
from copaw.state.skill_lifecycle_decision_service import SkillLifecycleDecisionService
from copaw.state.skill_trial_service import SkillTrialService
from copaw.state.store import SQLiteStateStore


def test_normalize_discovery_hits_merges_sources_and_overlap() -> None:
    normalized = normalize_discovery_hits(
        [
            DiscoveryHit(
                source_id="github",
                source_kind="catalog",
                source_alias="github",
                candidate_kind="skill",
                display_name="Research Pack",
                summary="GitHub package",
                candidate_source_ref="https://github.com/acme/research-pack",
                candidate_source_version="1.0.0",
                candidate_source_lineage="donor:research-pack",
                canonical_package_id="pkg:research-pack",
                capability_keys=("research", "search"),
            ),
            DiscoveryHit(
                source_id="mirror",
                source_kind="catalog",
                source_alias="gitee",
                candidate_kind="skill",
                display_name="Research Pack Mirror",
                summary="Mirror package",
                candidate_source_ref="https://gitee.com/acme/research-pack",
                candidate_source_version="1.0.0",
                candidate_source_lineage="donor:research-pack",
                canonical_package_id="pkg:research-pack",
                capability_keys=("research", "search"),
            ),
            DiscoveryHit(
                source_id="registry",
                source_kind="catalog",
                source_alias="registry",
                candidate_kind="skill",
                display_name="Browser Ops",
                summary="Original browser donor.",
                candidate_source_ref="registry://browser-ops",
                candidate_source_version="3.1.0",
                candidate_source_lineage="donor:browser-ops",
                canonical_package_id="pkg:browser-ops",
                capability_keys=("browser", "automation"),
            ),
            DiscoveryHit(
                source_id="registry",
                source_kind="catalog",
                source_alias="registry-alt",
                candidate_kind="skill",
                display_name="Web Automation",
                summary="Equivalent browser donor.",
                candidate_source_ref="registry://web-automation",
                candidate_source_version="3.1.0",
                candidate_source_lineage="donor:web-automation",
                canonical_package_id="pkg:web-automation",
                capability_keys=("browser", "automation"),
            ),
        ],
    )

    assert len(normalized) == 2
    research_cluster = next(
        item for item in normalized if item.canonical_package_id == "pkg:research-pack"
    )
    overlap_cluster = next(
        item
        for item in normalized
        if item.canonical_package_id in {"pkg:browser-ops", "pkg:web-automation"}
    )

    assert research_cluster.source_hit_count == 2
    assert set(research_cluster.source_aliases) == {"github", "gitee"}
    assert research_cluster.confidence_score > 0.5
    assert overlap_cluster.equivalence_class
    assert overlap_cluster.capability_overlap_score == 1.0


def test_candidate_import_deduplicates_before_fan_out_and_keeps_portfolio_counts_normalized(
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
    portfolio_service = CapabilityPortfolioService(
        donor_service=donor_service,
        candidate_service=candidate_service,
        skill_trial_service=trial_service,
        skill_lifecycle_decision_service=decision_service,
    )

    imported = candidate_service.import_discovery_hits(
        discovery_hits=[
            DiscoveryHit(
                source_id="github",
                source_kind="catalog",
                source_alias="github",
                candidate_kind="skill",
                display_name="Research Pack",
                summary="Primary hit.",
                candidate_source_ref="https://github.com/acme/research-pack",
                candidate_source_version="1.0.0",
                candidate_source_lineage="donor:research-pack",
                canonical_package_id="pkg:research-pack",
                capability_keys=("research", "search"),
            ),
            DiscoveryHit(
                source_id="mirror",
                source_kind="catalog",
                source_alias="gitee",
                candidate_kind="skill",
                display_name="Research Pack Mirror",
                summary="Mirror hit.",
                candidate_source_ref="https://gitee.com/acme/research-pack",
                candidate_source_version="1.0.0",
                candidate_source_lineage="donor:research-pack",
                canonical_package_id="pkg:research-pack",
                capability_keys=("research", "search"),
            ),
            DiscoveryHit(
                source_id="registry",
                source_kind="catalog",
                source_alias="registry",
                candidate_kind="skill",
                display_name="Browser Pilot",
                summary="Distinct donor.",
                candidate_source_ref="registry://browser-pilot",
                candidate_source_version="2.4.0",
                candidate_source_lineage="donor:browser-pilot",
                canonical_package_id="pkg:browser-pilot",
                capability_keys=("browser", "automation"),
            ),
        ],
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        industry_instance_id="industry-1",
        ingestion_mode="discovery-gap",
    )

    portfolio = portfolio_service.summarize_portfolio()
    candidates = candidate_service.list_candidates()

    assert len(imported) == 2
    assert len(candidates) == 2
    assert portfolio["donor_count"] == 2
    assert portfolio["candidate_donor_count"] == 2
    first_metadata = imported[0].metadata
    assert first_metadata["canonical_package_id"] in {
        "pkg:research-pack",
        "pkg:browser-pilot",
    }
    assert any(
        item.metadata.get("source_aliases") == ["github", "gitee"]
        for item in imported
    )


def test_normalize_discovery_hits_preserves_installable_project_source_ref() -> None:
    normalized = normalize_discovery_hits(
        [
            DiscoveryHit(
                source_id="github-repo",
                source_kind="github-repo",
                source_alias="github",
                candidate_kind="project",
                display_name="psf/black",
                summary="Python formatter donor.",
                candidate_source_ref="https://github.com/psf/black",
                candidate_source_version="main",
                candidate_source_lineage="donor:github:psf/black",
                canonical_package_id="pkg:github:psf/black",
                capability_keys=("formatting", "python"),
            ),
        ],
    )

    assert len(normalized) == 1
    assert normalized[0].candidate_kind == "project"
    assert normalized[0].candidate_source_ref == "https://github.com/psf/black"
    assert normalized[0].canonical_package_id == "pkg:github:psf/black"
    assert normalized[0].metadata["raw_source_refs"] == ["https://github.com/psf/black"]
