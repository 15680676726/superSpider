# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.discovery.models import DiscoveryActionRequest, DiscoveryHit
from copaw.discovery.source_chain import execute_discovery_action
from copaw.state.donor_source_service import DonorSourceService
from copaw.state.store import SQLiteStateStore


def _build_service(tmp_path: Path) -> DonorSourceService:
    return DonorSourceService(state_store=SQLiteStateStore(tmp_path / "state.sqlite3"))


def test_source_chain_uses_one_active_source_after_retry(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)
    request = DiscoveryActionRequest(
        action_id="discover-browser",
        query="browser automation donor",
        source_profile="global",
        discovery_mode="gap",
    )
    profile = service.resolve_source_profile("global")
    calls: list[str] = []

    def executor(source, discovery_request):
        assert discovery_request.action_id == request.action_id
        calls.append(source.source_id)
        if source.source_id == profile.sources[0].source_id:
            raise RuntimeError("github timeout")
        return [
            DiscoveryHit(
                source_id=source.source_id,
                source_kind=source.source_kind,
                source_alias=source.source_id,
                candidate_kind="skill",
                display_name="Browser Pilot",
                summary="Mirror search result.",
                candidate_source_ref="https://mirror.example/browser-pilot",
                candidate_source_version="2.0.0",
                candidate_source_lineage="donor:browser-pilot",
                canonical_package_id="pkg:browser-pilot",
                capability_keys=("browser", "automation"),
            ),
        ]

    result = execute_discovery_action(
        request=request,
        source_service=service,
        executor=executor,
    )

    assert calls == [profile.sources[0].source_id, profile.sources[1].source_id]
    assert result.status == "ok"
    assert result.active_source_id == profile.sources[1].source_id
    assert result.used_snapshot is False
    assert [attempt.status for attempt in result.attempts] == [
        "failed",
        "succeeded",
    ]
    assert {item.source_id for item in result.discovery_hits} == {
        profile.sources[1].source_id,
    }


def test_source_chain_degrades_to_snapshot_without_runtime_failure(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)
    request = DiscoveryActionRequest(
        action_id="discover-research",
        query="research donor",
        source_profile="china-mainland",
        discovery_mode="periodic",
    )
    profile = service.resolve_source_profile("china-mainland")
    service.record_source_success(
        profile_name="china-mainland",
        source_id=profile.sources[1].source_id,
        discovery_hits=[
            DiscoveryHit(
                source_id=profile.sources[1].source_id,
                source_kind=profile.sources[1].source_kind,
                source_alias=profile.sources[1].source_id,
                candidate_kind="skill",
                display_name="Research Relay",
                summary="Cached donor.",
                candidate_source_ref="https://mirror.example/research-relay",
                candidate_source_version="1.4.0",
                candidate_source_lineage="donor:research-relay",
                canonical_package_id="pkg:research-relay",
                capability_keys=("research", "search"),
            ),
        ],
    )

    def executor(source, discovery_request):
        raise RuntimeError(f"{source.source_id} unavailable for {discovery_request.query}")

    result = execute_discovery_action(
        request=request,
        source_service=service,
        executor=executor,
    )

    assert result.status == "degraded"
    assert result.used_snapshot is True
    assert result.active_source_id == profile.sources[1].source_id
    assert result.error_summary is not None
    assert [attempt.status for attempt in result.attempts] == ["failed"] * len(profile.sources)
    assert [item.canonical_package_id for item in result.discovery_hits] == [
        "pkg:research-relay",
    ]


def test_source_chain_treats_empty_hits_as_empty_and_retries_next_source(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)
    request = DiscoveryActionRequest(
        action_id="discover-empty-then-hit",
        query="browser automation donor",
        source_profile="global",
        discovery_mode="gap",
    )
    profile = service.resolve_source_profile("global")
    calls: list[str] = []

    def executor(source, _discovery_request):
        calls.append(source.source_id)
        if source.source_id == profile.sources[0].source_id:
            return []
        return [
            DiscoveryHit(
                source_id=source.source_id,
                source_kind=source.source_kind,
                source_alias=source.source_id,
                candidate_kind="skill",
                display_name="Browser Pilot",
                summary="Mirror search result.",
                candidate_source_ref="https://github.com/acme/browser-pilot",
                candidate_source_version="2.0.0",
                candidate_source_lineage="donor:browser-pilot",
                canonical_package_id="pkg:browser-pilot",
                capability_keys=("browser", "automation"),
            ),
        ]

    result = execute_discovery_action(
        request=request,
        source_service=service,
        executor=executor,
    )

    health = service.get_source_health(
        profile_name="global",
        source_id=profile.sources[0].source_id,
    )

    assert calls == [profile.sources[0].source_id, profile.sources[1].source_id]
    assert [attempt.status for attempt in result.attempts] == ["empty", "succeeded"]
    assert result.active_source_id == profile.sources[1].source_id
    assert health["last_status"] == "empty"
    assert health["success_count"] == 0


def test_source_chain_offline_private_uses_cached_hits_without_remote_executor(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)
    global_profile = service.resolve_source_profile("global")
    service.record_source_success(
        profile_name="global",
        source_id=global_profile.sources[0].source_id,
        discovery_hits=[
            DiscoveryHit(
                source_id=global_profile.sources[0].source_id,
                source_kind=global_profile.sources[0].source_kind,
                source_alias=global_profile.sources[0].source_id,
                candidate_kind="project",
                display_name="Aider",
                summary="Cached GitHub donor.",
                candidate_source_ref="https://github.com/Aider-AI/aider",
                candidate_source_version="main",
                candidate_source_lineage="donor:github:aider-ai/aider",
                canonical_package_id="pkg:github:aider-ai/aider",
                capability_keys=("coding", "terminal"),
            ),
        ],
    )
    request = DiscoveryActionRequest(
        action_id="discover-offline-cache",
        query="aider coding",
        source_profile="offline-private",
        discovery_mode="gap",
        limit=5,
    )

    def executor(_source, _discovery_request):
        raise AssertionError("offline cache should not require remote executor")

    result = execute_discovery_action(
        request=request,
        source_service=service,
        executor=executor,
    )

    assert result.status == "ok"
    assert result.active_source_id == "offline-cache"
    assert result.used_snapshot is False
    assert [attempt.status for attempt in result.attempts] == ["succeeded"]
    assert [item.canonical_package_id for item in result.discovery_hits] == [
        "pkg:github:aider-ai/aider",
    ]
