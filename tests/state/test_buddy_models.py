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
