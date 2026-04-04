# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from copaw.capabilities.models import CapabilityMount
from copaw.state import SQLiteStateStore
from copaw.state.skill_candidate_service import (
    CapabilityCandidateService,
)


def _build_service(tmp_path: Path) -> CapabilityCandidateService:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    return CapabilityCandidateService(state_store=store)


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
