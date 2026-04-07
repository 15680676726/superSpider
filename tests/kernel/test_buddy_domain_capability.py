# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.kernel.buddy_domain_capability import (
    BuddyDomainCapabilitySignals,
    capability_stage_from_score,
    derive_capability_metrics,
    derive_buddy_domain_key,
    preview_domain_transition,
    progress_to_next_capability_stage,
)


def _record(
    *,
    domain_id: str,
    domain_key: str,
    domain_label: str,
    status: str,
    capability_score: int,
    evolution_stage: str,
):
    return SimpleNamespace(
        domain_id=domain_id,
        profile_id="profile-1",
        domain_key=domain_key,
        domain_label=domain_label,
        status=status,
        capability_score=capability_score,
        evolution_stage=evolution_stage,
    )


def test_capability_stage_from_score_uses_five_domain_bands() -> None:
    assert capability_stage_from_score(0) == "seed"
    assert capability_stage_from_score(19) == "seed"
    assert capability_stage_from_score(20) == "bonded"
    assert capability_stage_from_score(39) == "bonded"
    assert capability_stage_from_score(40) == "capable"
    assert capability_stage_from_score(59) == "capable"
    assert capability_stage_from_score(60) == "seasoned"
    assert capability_stage_from_score(79) == "seasoned"
    assert capability_stage_from_score(80) == "signature"
    assert capability_stage_from_score(100) == "signature"


def test_progress_to_next_capability_stage_tracks_current_band() -> None:
    assert progress_to_next_capability_stage(0) == 0
    assert progress_to_next_capability_stage(10) == 50
    assert progress_to_next_capability_stage(20) == 0
    assert progress_to_next_capability_stage(50) == 50
    assert progress_to_next_capability_stage(79) == 95
    assert progress_to_next_capability_stage(80) == 100


def test_derive_capability_metrics_caps_each_component_and_maps_stage() -> None:
    metrics = derive_capability_metrics(
        BuddyDomainCapabilitySignals(
            has_active_instance=True,
            lane_count=5,
            backlog_count=4,
            cycle_count=3,
            completed_cycle_count=2,
            has_current_cycle=True,
            assignment_count=6,
            active_assignment_count=3,
            completed_assignment_count=4,
            report_count=5,
            completed_report_count=3,
            evidence_count=7,
        )
    )

    assert metrics.strategy_score == 19
    assert metrics.execution_score == 26
    assert metrics.evidence_score == 20
    assert metrics.stability_score == 20
    assert metrics.capability_score == 85
    assert metrics.evolution_stage == "signature"


def test_derive_buddy_domain_key_normalizes_same_domain_variants() -> None:
    assert derive_buddy_domain_key("炒股赚 10 万") == derive_buddy_domain_key("股票赚 100 万")
    assert derive_buddy_domain_key("建立写作收入") == derive_buddy_domain_key("写作副业变现")
    assert derive_buddy_domain_key("炒股赚 10 万") != derive_buddy_domain_key("写作副业变现")


def test_preview_domain_transition_prefers_same_domain_extension() -> None:
    preview = preview_domain_transition(
        selected_direction="股票赚 100 万",
        active_record=_record(
            domain_id="domain-stock",
            domain_key=derive_buddy_domain_key("炒股赚 10 万"),
            domain_label="股票",
            status="active",
            capability_score=68,
            evolution_stage="seasoned",
        ),
        archived_records=[
            _record(
                domain_id="domain-writing",
                domain_key=derive_buddy_domain_key("写作副业变现"),
                domain_label="写作",
                status="archived",
                capability_score=35,
                evolution_stage="bonded",
            )
        ],
    )

    assert preview.suggestion_kind == "same-domain"
    assert preview.recommended_action == "keep-active"
    assert preview.selected_domain_key == derive_buddy_domain_key("股票赚 100 万")
    assert preview.current_domain is not None
    assert preview.current_domain["domain_id"] == "domain-stock"
    assert preview.archived_matches == []


def test_preview_domain_transition_restores_matching_archived_domain() -> None:
    preview = preview_domain_transition(
        selected_direction="写作副业变现",
        active_record=_record(
            domain_id="domain-stock",
            domain_key=derive_buddy_domain_key("炒股赚 10 万"),
            domain_label="股票",
            status="active",
            capability_score=68,
            evolution_stage="seasoned",
        ),
        archived_records=[
            _record(
                domain_id="domain-writing",
                domain_key=derive_buddy_domain_key("建立写作收入"),
                domain_label="写作",
                status="archived",
                capability_score=48,
                evolution_stage="capable",
            )
        ],
    )

    assert preview.suggestion_kind == "switch-to-archived-domain"
    assert preview.recommended_action == "restore-archived"
    assert preview.archived_matches[0]["domain_id"] == "domain-writing"


def test_preview_domain_transition_starts_new_domain_when_no_match_exists() -> None:
    preview = preview_domain_transition(
        selected_direction="健身习惯重建",
        active_record=_record(
            domain_id="domain-stock",
            domain_key=derive_buddy_domain_key("炒股赚 10 万"),
            domain_label="股票",
            status="active",
            capability_score=68,
            evolution_stage="seasoned",
        ),
        archived_records=[
            _record(
                domain_id="domain-writing",
                domain_key=derive_buddy_domain_key("建立写作收入"),
                domain_label="写作",
                status="archived",
                capability_score=48,
                evolution_stage="capable",
            )
        ],
    )

    assert preview.suggestion_kind == "start-new-domain"
    assert preview.recommended_action == "start-new"
    assert preview.archived_matches == []
