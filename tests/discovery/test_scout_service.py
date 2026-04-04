# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.discovery.models import (
    DiscoveryHit,
    OpportunityRadarItem,
    ScoutBudget,
    ScoutRequest,
)
from copaw.discovery.opportunity_radar import OpportunityRadarService
from copaw.discovery.scout_service import DonorScoutService
from copaw.state.capability_donor_service import CapabilityDonorService
from copaw.state.donor_source_service import DonorSourceService
from copaw.state.skill_candidate_service import CapabilityCandidateService
from copaw.state.store import SQLiteStateStore


def test_scout_service_runs_bounded_opportunity_mode_and_imports_candidates(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    donor_source_service = DonorSourceService(state_store=store)
    donor_service = CapabilityDonorService(state_store=store)
    candidate_service = CapabilityCandidateService(
        state_store=store,
        donor_service=donor_service,
    )
    radar_service = OpportunityRadarService(
        feeds={
            "weekly": lambda: [
                OpportunityRadarItem(
                    item_id="item-1",
                    title="Browser donor",
                    summary="Browser donor trend.",
                    canonical_package_id="pkg:browser-pilot",
                    source_ref="https://github.com/acme/browser-pilot",
                    ecosystem="github",
                    score=0.9,
                    capability_keys=("browser", "automation"),
                    query_hint="browser automation donor",
                ),
                OpportunityRadarItem(
                    item_id="item-2",
                    title="Research donor",
                    summary="Research donor trend.",
                    canonical_package_id="pkg:research-relay",
                    source_ref="https://github.com/acme/research-relay",
                    ecosystem="github",
                    score=0.8,
                    capability_keys=("research", "search"),
                    query_hint="research automation donor",
                ),
            ],
        }
    )
    calls: list[str] = []

    def executor(source, request):
        calls.append(f"{source.source_id}:{request.query}")
        if "browser" in request.query:
            return [
                DiscoveryHit(
                    source_id=source.source_id,
                    source_kind=source.source_kind,
                    source_alias=source.source_id,
                    candidate_kind="skill",
                    display_name="Browser Pilot",
                    summary="Browser scout hit.",
                    candidate_source_ref="https://github.com/acme/browser-pilot",
                    candidate_source_version="2.0.0",
                    candidate_source_lineage="donor:browser-pilot",
                    canonical_package_id="pkg:browser-pilot",
                    capability_keys=("browser", "automation"),
                ),
            ]
        return [
            DiscoveryHit(
                source_id=source.source_id,
                source_kind=source.source_kind,
                source_alias=source.source_id,
                candidate_kind="skill",
                display_name="Research Relay",
                summary="Research scout hit.",
                candidate_source_ref="https://github.com/acme/research-relay",
                candidate_source_version="1.4.0",
                candidate_source_lineage="donor:research-relay",
                canonical_package_id="pkg:research-relay",
                capability_keys=("research", "search"),
            ),
        ]

    service = DonorScoutService(
        source_service=donor_source_service,
        candidate_service=candidate_service,
        opportunity_radar_service=radar_service,
        discovery_executor=executor,
    )

    result = service.run_scout(
        request=ScoutRequest(
            scout_id="scout-1",
            mode="opportunity",
            source_profile="global",
            target_scope="seat",
            target_role_id="researcher",
            target_seat_ref="seat-1",
            industry_instance_id="industry-1",
            budget=ScoutBudget(max_queries=1, max_candidates=2),
        )
    )

    assert result.mode == "opportunity"
    assert result.radar_item_count == 1
    assert result.imported_candidate_count == 1
    assert len(candidate_service.list_candidates()) == 1
    assert len(calls) == 1
    assert service.get_latest_summary()["status"] == "ready"

