# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sqlite3

from copaw.state import SQLiteStateStore
from copaw.state.repositories_buddy import (
    BuddyOnboardingSessionRecord,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteHumanProfileRepository,
)


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


def test_companion_relationship_accepts_collaboration_contract_fields() -> None:
    from copaw.state import CompanionRelationship

    relationship = CompanionRelationship(
        relationship_id="cr-contract-1",
        profile_id="hp-contract-1",
        buddy_name="Milo",
        service_intent="turn long-term goals into steady weekly execution",
        collaboration_role="orchestrator",
        autonomy_level="proactive",
        confirm_boundaries=["external spend", "irreversible actions"],
        report_style="result-first",
        collaboration_notes="Prefer short status summaries and direct escalation.",
    )

    assert relationship.service_intent == "turn long-term goals into steady weekly execution"
    assert relationship.collaboration_role == "orchestrator"
    assert relationship.autonomy_level == "proactive"
    assert relationship.confirm_boundaries == ["external spend", "irreversible actions"]
    assert relationship.report_style == "result-first"
    assert relationship.collaboration_notes.startswith("Prefer short")


def test_buddy_onboarding_session_record_uses_contract_draft_fields() -> None:
    session = BuddyOnboardingSessionRecord(
        session_id="session-contract-1",
        profile_id="hp-contract-1",
        status="contract-draft",
        service_intent="build a reliable collaboration rhythm",
        collaboration_role="orchestrator",
        autonomy_level="proactive",
        confirm_boundaries=["money", "account changes"],
        report_style="result-first",
        collaboration_notes="Escalate blockers with one concrete next step.",
        candidate_directions=["writing", "productized consulting"],
        recommended_direction="writing",
        selected_direction="writing",
        draft_direction="writing",
        draft_final_goal="Publish consistently and convert to recurring revenue",
        draft_why_it_matters="This creates durable leverage.",
        draft_backlog_items=[{"title": "Draft weekly writing cadence"}],
    )

    payload = session.model_dump(mode="json")

    assert session.service_intent == "build a reliable collaboration rhythm"
    assert session.collaboration_role == "orchestrator"
    assert session.autonomy_level == "proactive"
    assert session.confirm_boundaries == ["money", "account changes"]
    assert session.report_style == "result-first"
    assert session.collaboration_notes.startswith("Escalate blockers")
    assert session.recommended_direction == "writing"
    assert session.draft_backlog_items == [{"title": "Draft weekly writing cadence"}]
    assert "question_count" not in payload
    assert "tightened" not in payload
    assert "next_question" not in payload
    assert "transcript" not in payload


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


def test_buddy_repositories_round_trip_contract_fields(tmp_path) -> None:
    from copaw.state import CompanionRelationship, HumanProfile

    database_path = tmp_path / "state.db"
    store = SQLiteStateStore(database_path)
    profile_repo = SqliteHumanProfileRepository(store)
    relationship_repo = SqliteCompanionRelationshipRepository(store)
    session_repo = SqliteBuddyOnboardingSessionRepository(store)

    profile_repo.upsert_profile(
        HumanProfile(
            profile_id="hp-contract-2",
            display_name="Alex",
            profession="Writer",
            current_stage="transition",
            interests=["writing"],
            strengths=["consistency"],
            constraints=["time"],
            goal_intention="Build a durable creative practice",
        )
    )

    relationship = CompanionRelationship(
        relationship_id="cr-contract-2",
        profile_id="hp-contract-2",
        buddy_name="Milo",
        service_intent="co-drive weekly execution with clear boundaries",
        collaboration_role="orchestrator",
        autonomy_level="proactive",
        confirm_boundaries=["payments", "publishing"],
        report_style="result-first",
        collaboration_notes="Lead with outcomes, then blockers.",
    )
    session = BuddyOnboardingSessionRecord(
        session_id="session-contract-2",
        profile_id="hp-contract-2",
        status="contract-draft",
        service_intent="co-drive weekly execution with clear boundaries",
        collaboration_role="orchestrator",
        autonomy_level="proactive",
        confirm_boundaries=["payments", "publishing"],
        report_style="result-first",
        collaboration_notes="Lead with outcomes, then blockers.",
        candidate_directions=["writing"],
        recommended_direction="writing",
        selected_direction="writing",
        activation_id="activation-1",
        activation_status="queued",
        activation_error="",
        activation_attempt_count=2,
        draft_direction="writing",
        draft_final_goal="Ship a weekly essay",
        draft_why_it_matters="Momentum compounds with visible output.",
        draft_backlog_items=[{"title": "Write outline"}],
    )

    relationship_repo.upsert_relationship(relationship)
    session_repo.upsert_session(session)

    stored_relationship = relationship_repo.get_relationship("hp-contract-2")
    stored_session = session_repo.get_latest_session_for_profile("hp-contract-2")

    assert stored_relationship is not None
    assert stored_relationship.service_intent == relationship.service_intent
    assert stored_relationship.confirm_boundaries == ["payments", "publishing"]
    assert stored_session is not None
    assert stored_session.service_intent == session.service_intent
    assert stored_session.confirm_boundaries == ["payments", "publishing"]
    assert stored_session.activation_id == "activation-1"
    assert stored_session.activation_status == "queued"
    assert stored_session.activation_error == ""
    assert stored_session.activation_attempt_count == 2
    assert stored_session.draft_backlog_items == [{"title": "Write outline"}]

    with sqlite3.connect(database_path) as conn:
        relationship_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(companion_relationships)").fetchall()
        }
        session_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(buddy_onboarding_sessions)").fetchall()
        }
        relationship_row = conn.execute(
            """
            SELECT service_intent, collaboration_role, autonomy_level,
                   confirm_boundaries_json, report_style, collaboration_notes
            FROM companion_relationships
            WHERE relationship_id = ?
            """,
            (relationship.relationship_id,),
        ).fetchone()
        session_row = conn.execute(
            """
            SELECT service_intent, collaboration_role, autonomy_level,
                   confirm_boundaries_json, report_style, collaboration_notes,
                   activation_id, activation_status, activation_error, activation_attempt_count
            FROM buddy_onboarding_sessions
            WHERE session_id = ?
            """,
            (session.session_id,),
        ).fetchone()

    assert "question_count" not in session_columns
    assert "tightened" not in session_columns
    assert "next_question" not in session_columns
    assert "transcript_json" not in session_columns
    assert "confirm_boundaries_json" in relationship_columns
    assert "confirm_boundaries_json" in session_columns
    assert relationship_row is not None
    assert relationship_row[0] == "co-drive weekly execution with clear boundaries"
    assert json.loads(relationship_row[3]) == ["payments", "publishing"]
    assert session_row is not None
    assert session_row[0] == "co-drive weekly execution with clear boundaries"
    assert json.loads(session_row[3]) == ["payments", "publishing"]
    assert session_row[6] == "activation-1"
    assert session_row[7] == "queued"
    assert session_row[8] == ""
    assert session_row[9] == 2


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
