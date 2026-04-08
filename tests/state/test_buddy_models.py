# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3

from copaw.state import SQLiteStateStore


def test_buddy_models_round_trip_required_fields() -> None:
    from copaw.state import (
        BuddyDomainCapabilityRecord,
        BuddyGrowthProjection,
        BuddyPresentation,
        CompanionRelationship,
        GrowthTarget,
        HumanProfile,
    )

    profile = HumanProfile(
        profile_id="hp-1",
        display_name="Alex",
        profession="Designer",
        current_stage="transition",
        interests=["writing"],
        strengths=["systems thinking"],
        constraints=["time"],
        goal_intention="Build a long-term creative career",
    )
    target = GrowthTarget(
        target_id="gt-1",
        profile_id=profile.profile_id,
        primary_direction="Build an independent creative career",
        final_goal="Become a stable creator with recurring income",
        why_it_matters="Autonomy and long-term meaningful work",
    )
    relationship = CompanionRelationship(
        relationship_id="cr-1",
        profile_id=profile.profile_id,
        encouragement_style="old-friend",
        effective_reminders=["short pull-back"],
        ineffective_reminders=["hard pressure"],
        avoidance_patterns=["doom scrolling"],
    )
    presentation = BuddyPresentation(
        profile_id=profile.profile_id,
        buddy_name="Milo",
        lifecycle_state="named",
        presence_state="attentive",
        mood_state="warm",
        current_form="seed",
        rarity="common",
        current_goal_summary=target.final_goal,
        current_task_summary="Write the first portfolio draft",
        why_now_summary="This unlocks the first real sample of work",
    )
    growth = BuddyGrowthProjection(
        profile_id=profile.profile_id,
        intimacy=12,
        affinity=9,
        growth_level=2,
        companion_experience=35,
        knowledge_value=7,
        skill_value=5,
        pleasant_interaction_score=8,
        communication_count=14,
        completed_support_runs=3,
        completed_assisted_closures=1,
        evolution_stage="seed",
        progress_to_next_stage=42,
    )
    domain = BuddyDomainCapabilityRecord(
        domain_id="domain-1",
        profile_id=profile.profile_id,
        domain_key="writing",
        domain_label="写作",
        status="active",
        industry_instance_id="buddy:hp-1:domain-1",
        control_thread_id="industry-chat:buddy:hp-1:domain-1:execution-core",
        domain_scope_summary="Long-form writing plus adjacent creator products",
        domain_scope_tags=["writing", "ip"],
        strategy_score=18,
        execution_score=14,
        evidence_score=8,
        stability_score=6,
        capability_score=46,
        evolution_stage="capable",
    )

    assert profile.display_name == "Alex"
    assert target.primary_direction.startswith("Build")
    assert relationship.encouragement_style == "old-friend"
    assert presentation.buddy_name == "Milo"
    assert growth.evolution_stage == "seed"
    assert domain.domain_label == "写作"
    assert domain.evolution_stage == "capable"
    assert domain.industry_instance_id == "buddy:hp-1:domain-1"
    assert domain.control_thread_id == "industry-chat:buddy:hp-1:domain-1:execution-core"
    assert domain.domain_scope_tags == ["writing", "ip"]


def test_sqlite_state_store_creates_buddy_tables(tmp_path) -> None:
    database_path = tmp_path / "state.db"
    store = SQLiteStateStore(database_path)
    store.initialize()

    with sqlite3.connect(database_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    assert "human_profiles" in tables
    assert "growth_targets" in tables
    assert "companion_relationships" in tables
    assert "buddy_domain_capabilities" in tables


def test_buddy_models_accept_points_and_gate_metrics() -> None:
    from copaw.state import BuddyDomainCapabilityRecord, BuddyGrowthProjection

    record = BuddyDomainCapabilityRecord(
        profile_id="profile-1",
        domain_key="writing",
        domain_label="Writing",
        capability_points=40,
        settled_closure_count=20,
        independent_outcome_count=2,
        recent_completion_rate=0.95,
        recent_execution_error_rate=0.02,
        distinct_settled_cycle_count=3,
        demotion_cooldown_until="2026-04-09T00:00:00Z",
    )
    growth = BuddyGrowthProjection(
        profile_id="profile-1",
        capability_points=40,
        settled_closure_count=20,
        independent_outcome_count=2,
        recent_completion_rate=0.95,
        recent_execution_error_rate=0.02,
        distinct_settled_cycle_count=3,
    )

    assert record.capability_points == 40
    assert record.settled_closure_count == 20
    assert record.independent_outcome_count == 2
    assert record.recent_completion_rate == 0.95
    assert record.recent_execution_error_rate == 0.02
    assert record.distinct_settled_cycle_count == 3
    assert record.demotion_cooldown_until == "2026-04-09T00:00:00Z"
    assert growth.capability_points == 40
    assert growth.settled_closure_count == 20
