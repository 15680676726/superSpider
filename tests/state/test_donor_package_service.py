# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.state.capability_donor_service import CapabilityDonorService
from copaw.state.donor_package_service import DonorPackageService
from copaw.state.skill_candidate_service import CapabilityCandidateService
from copaw.state.store import SQLiteStateStore


def test_donor_package_service_summarizes_package_kinds_by_donor(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    donor_service = CapabilityDonorService(state_store=store)
    candidate_service = CapabilityCandidateService(
        state_store=store,
        donor_service=donor_service,
    )
    package_service = DonorPackageService(donor_service=donor_service)

    first = candidate_service.normalize_candidate_source(
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
    )
    candidate_service.normalize_candidate_source(
        candidate_kind="mcp-bundle",
        target_scope="seat",
        target_role_id="researcher",
        target_seat_ref="seat-1",
        candidate_source_kind="external_catalog",
        candidate_source_ref="registry://browser-pack",
        candidate_source_version="2.0.0",
        candidate_source_lineage="donor:browser-pack",
        ingestion_mode="discovery",
        proposed_skill_name="browser_pack",
        summary="Browser pack donor.",
    )

    summary = package_service.summarize_packages()
    donor_packages = package_service.list_donor_packages(donor_id=first.donor_id)

    assert summary["package_count"] == 2
    assert summary["package_kind_count"] == {"mcp-bundle": 1, "skill": 1}
    assert len(donor_packages) == 1

