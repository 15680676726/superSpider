# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.discovery.models import DiscoveryHit
from copaw.state.donor_source_service import DonorSourceService
from copaw.state.store import SQLiteStateStore


def _build_service(tmp_path: Path) -> DonorSourceService:
    return DonorSourceService(state_store=SQLiteStateStore(tmp_path / "state.sqlite3"))


def test_donor_source_service_provides_default_regional_profiles(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)

    assert service.list_profile_names() == [
        "china-mainland",
        "global",
        "hybrid",
        "offline-private",
    ]

    global_profile = service.resolve_source_profile("global")
    china_profile = service.resolve_source_profile("china-mainland")
    hybrid_profile = service.resolve_source_profile("hybrid")
    offline_profile = service.resolve_source_profile("offline-private")

    assert [item.chain_role for item in global_profile.sources] == [
        "primary",
        "mirror",
        "fallback",
        "fallback",
    ]
    assert [item.chain_role for item in china_profile.sources] == [
        "primary",
        "mirror",
        "fallback",
        "fallback",
    ]
    assert [item.chain_role for item in hybrid_profile.sources] == [
        "primary",
        "mirror",
        "fallback",
        "fallback",
    ]
    assert [item.chain_role for item in offline_profile.sources] == [
        "primary",
        "fallback",
    ]
    assert global_profile.sources[0].source_id != china_profile.sources[0].source_id
    assert offline_profile.sources[-1].source_kind == "snapshot"


def test_donor_source_service_tracks_health_and_last_known_good_snapshot(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)
    profile = service.resolve_source_profile("global")
    primary_source = profile.sources[0]
    snapshot_hits = [
        DiscoveryHit(
            source_id=primary_source.source_id,
            source_kind=primary_source.source_kind,
            source_alias=primary_source.source_id,
            candidate_kind="skill",
            display_name="Research Pack",
            summary="Remote donor snapshot.",
            candidate_source_ref="https://example.com/research-pack",
            candidate_source_version="1.0.0",
            candidate_source_lineage="donor:research-pack",
            canonical_package_id="pkg:research-pack",
            capability_keys=("research", "search"),
        ),
    ]

    service.record_source_success(
        profile_name="global",
        source_id=primary_source.source_id,
        discovery_hits=snapshot_hits,
    )
    service.record_source_failure(
        profile_name="global",
        source_id=primary_source.source_id,
        error="timeout",
    )

    health = service.get_source_health(
        profile_name="global",
        source_id=primary_source.source_id,
    )
    snapshot = service.get_last_known_good_snapshot("global")

    assert health["last_status"] == "failed"
    assert health["success_count"] == 1
    assert health["failure_count"] == 1
    assert health["last_error"] == "timeout"
    assert snapshot is not None
    assert snapshot.source_id == primary_source.source_id
    assert [item.canonical_package_id for item in snapshot.discovery_hits] == [
        "pkg:research-pack",
    ]
