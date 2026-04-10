# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.kernel.buddy_domain_capability import (
    BuddyDomainCapabilitySignals,
    buddy_specialist_allowed_capabilities,
    buddy_specialist_preferred_capability_families,
    derive_capability_metrics,
    derive_buddy_domain_key,
    preview_domain_transition,
    progress_to_next_stage,
    resolve_stage_transition,
    stage_from_points,
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


def test_stage_from_points_uses_five_domain_bands() -> None:
    assert stage_from_points(0) == "seed"
    assert stage_from_points(19) == "seed"
    assert stage_from_points(20) == "bonded"
    assert stage_from_points(39) == "bonded"
    assert stage_from_points(40) == "capable"
    assert stage_from_points(99) == "capable"
    assert stage_from_points(100) == "seasoned"
    assert stage_from_points(199) == "seasoned"
    assert stage_from_points(200) == "signature"
    assert stage_from_points(500) == "signature"


def test_progress_to_next_stage_tracks_current_points_band() -> None:
    assert progress_to_next_stage(0) == 0
    assert progress_to_next_stage(10) == 50
    assert progress_to_next_stage(20) == 0
    assert progress_to_next_stage(70) == 50
    assert progress_to_next_stage(150) == 50
    assert progress_to_next_stage(200) == 100


def test_capable_stage_requires_at_least_one_real_closure() -> None:
    assert (
        resolve_stage_transition(
            previous_stage="bonded",
            points=40,
            settled_closure_count=0,
            independent_outcome_count=0,
            recent_completion_rate=0,
            recent_execution_error_rate=0,
            distinct_settled_cycle_count=0,
        )
        == "bonded"
    )
    assert (
        resolve_stage_transition(
            previous_stage="bonded",
            points=40,
            settled_closure_count=1,
            independent_outcome_count=0,
            recent_completion_rate=0,
            recent_execution_error_rate=0,
            distinct_settled_cycle_count=0,
        )
        == "capable"
    )


def test_seasoned_stage_requires_three_distinct_settled_cycles() -> None:
    assert (
        resolve_stage_transition(
            previous_stage="capable",
            points=100,
            settled_closure_count=20,
            independent_outcome_count=0,
            recent_completion_rate=0.9,
            recent_execution_error_rate=0.02,
            distinct_settled_cycle_count=2,
        )
        == "capable"
    )
    assert (
        resolve_stage_transition(
            previous_stage="capable",
            points=100,
            settled_closure_count=20,
            independent_outcome_count=0,
            recent_completion_rate=0.9,
            recent_execution_error_rate=0.02,
            distinct_settled_cycle_count=3,
        )
        == "seasoned"
    )


def test_signature_stage_requires_points_and_reliability_gates() -> None:
    assert (
        resolve_stage_transition(
            previous_stage="seasoned",
            points=200,
            settled_closure_count=100,
            independent_outcome_count=9,
            recent_completion_rate=0.95,
            recent_execution_error_rate=0.02,
            distinct_settled_cycle_count=5,
        )
        == "seasoned"
    )
    assert (
        resolve_stage_transition(
            previous_stage="seasoned",
            points=200,
            settled_closure_count=100,
            independent_outcome_count=10,
            recent_completion_rate=0.91,
            recent_execution_error_rate=0.02,
            distinct_settled_cycle_count=5,
        )
        == "seasoned"
    )
    assert (
        resolve_stage_transition(
            previous_stage="seasoned",
            points=200,
            settled_closure_count=100,
            independent_outcome_count=10,
            recent_completion_rate=0.95,
            recent_execution_error_rate=0.04,
            distinct_settled_cycle_count=5,
        )
        == "seasoned"
    )
    assert (
        resolve_stage_transition(
            previous_stage="seasoned",
            points=200,
            settled_closure_count=100,
            independent_outcome_count=10,
            recent_completion_rate=0.95,
            recent_execution_error_rate=0.03,
            distinct_settled_cycle_count=5,
        )
        == "signature"
    )


def test_demotion_can_only_drop_one_stage() -> None:
    assert (
        resolve_stage_transition(
            previous_stage="signature",
            points=10,
            settled_closure_count=0,
            independent_outcome_count=0,
            recent_completion_rate=0.1,
            recent_execution_error_rate=0.9,
            distinct_settled_cycle_count=0,
        )
        == "seasoned"
    )


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


def test_derive_buddy_domain_key_uses_normalized_direction_text_instead_of_fixed_buckets() -> None:
    stock_key = derive_buddy_domain_key("Build a disciplined stock trading path with real risk control.")
    writing_key = derive_buddy_domain_key("Build a durable writing and publishing path with visible proof-of-work.")
    health_key = derive_buddy_domain_key("Build a repeatable health routine with visible weekly evidence.")

    assert stock_key == "build-a-disciplined-stock-trading-path-with-real-risk-control"
    assert writing_key == "build-a-durable-writing-and-publishing-path-with-visible-proof-of-work"
    assert health_key == "build-a-repeatable-health-routine-with-visible-weekly-evidence"
    assert stock_key != "stocks"
    assert writing_key != "writing"
    assert health_key != "fitness"


def test_derive_buddy_domain_key_does_not_fold_design_into_writing() -> None:
    writing_key = derive_buddy_domain_key("Build a durable writing income path.")
    design_key = derive_buddy_domain_key("Build a durable design systems and brand capability path.")

    assert writing_key != "writing"
    assert design_key != writing_key


def test_preview_domain_transition_prefers_same_domain_extension() -> None:
    stock_direction = "Build a disciplined stock trading path with real risk control."
    preview = preview_domain_transition(
        selected_direction=stock_direction,
        active_record=_record(
            domain_id="domain-stock",
            domain_key=derive_buddy_domain_key(stock_direction),
            domain_label="Stocks",
            status="active",
            capability_score=68,
            evolution_stage="seasoned",
        ),
        archived_records=[
            _record(
                domain_id="domain-writing",
                domain_key=derive_buddy_domain_key("Build a durable writing income path."),
                domain_label="Writing",
                status="archived",
                capability_score=35,
                evolution_stage="bonded",
            )
        ],
    )

    assert preview.suggestion_kind == "same-domain"
    assert preview.recommended_action == "keep-active"
    assert preview.selected_domain_key == derive_buddy_domain_key(stock_direction)
    assert preview.current_domain is not None
    assert preview.current_domain["domain_id"] == "domain-stock"
    assert preview.archived_matches == []


def test_preview_domain_transition_restores_matching_archived_domain() -> None:
    stock_direction = "Build a disciplined stock trading path with real risk control."
    writing_direction = "Build a durable writing and publishing path with visible proof-of-work."
    preview = preview_domain_transition(
        selected_direction=writing_direction,
        active_record=_record(
            domain_id="domain-stock",
            domain_key=derive_buddy_domain_key(stock_direction),
            domain_label="Stocks",
            status="active",
            capability_score=68,
            evolution_stage="seasoned",
        ),
        archived_records=[
            _record(
                domain_id="domain-writing",
                domain_key=derive_buddy_domain_key(writing_direction),
                domain_label="Writing",
                status="archived",
                capability_score=35,
                evolution_stage="bonded",
            )
        ],
    )

    assert preview.suggestion_kind == "switch-to-archived-domain"
    assert preview.recommended_action == "restore-archived"
    assert preview.selected_domain_key == derive_buddy_domain_key(writing_direction)
    assert preview.current_domain is not None
    assert preview.current_domain["domain_id"] == "domain-stock"
    assert preview.archived_matches is not None
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


def test_generic_domain_keys_do_not_fall_back_to_fixed_buckets() -> None:
    domain_key = derive_buddy_domain_key("跨境电商独立站运营与投放")

    assert domain_key not in {"general", "writing", "stocks", "fitness"}
    assert domain_key


def test_generic_proof_of_work_role_still_gets_browser_and_execution_families() -> None:
    domain_key = derive_buddy_domain_key("跨境电商独立站运营与投放")

    allowed = buddy_specialist_allowed_capabilities(
        domain_key=domain_key,
        role_id="proof-of-work",
    )
    families = buddy_specialist_preferred_capability_families(
        domain_key=domain_key,
        role_id="proof-of-work",
    )

    assert "tool:browser_use" in allowed
    assert "execution" in families
    assert "evidence" in families
    assert "browser" in families
