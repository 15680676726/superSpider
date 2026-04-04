# -*- coding: utf-8 -*-
"""Buddy-specific repositories for onboarding truth and transitional sessions."""
from __future__ import annotations

import json

from pydantic import Field

from .model_support import UpdatedRecord, _new_record_id
from .models_buddy import CompanionRelationship, GrowthTarget, HumanProfile
from .store import SQLiteStateStore


class BuddyOnboardingSessionRecord(UpdatedRecord):
    session_id: str = Field(default_factory=_new_record_id, min_length=1)
    profile_id: str = Field(..., min_length=1)
    status: str = Field(default="clarifying", min_length=1)
    question_count: int = Field(default=1, ge=1)
    tightened: bool = False
    next_question: str = ""
    transcript: list[str] = Field(default_factory=list)
    candidate_directions: list[str] = Field(default_factory=list)
    recommended_direction: str = ""
    selected_direction: str = ""


def _encode_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _decode_json_list(value: object | None) -> list[str]:
    if value in (None, ""):
        return []
    try:
        payload = json.loads(str(value))
    except Exception:
        return []
    if isinstance(payload, list):
        return [str(item).strip() for item in payload if str(item).strip()]
    return []


def _human_profile_from_row(row) -> HumanProfile | None:
    if row is None:
        return None
    payload = dict(row)
    payload["interests"] = _decode_json_list(payload.pop("interests_json", None))
    payload["strengths"] = _decode_json_list(payload.pop("strengths_json", None))
    payload["constraints"] = _decode_json_list(payload.pop("constraints_json", None))
    return HumanProfile.model_validate(payload)


def _growth_target_from_row(row) -> GrowthTarget | None:
    if row is None:
        return None
    return GrowthTarget.model_validate(dict(row))


def _relationship_from_row(row) -> CompanionRelationship | None:
    if row is None:
        return None
    payload = dict(row)
    payload["effective_reminders"] = _decode_json_list(
        payload.pop("effective_reminders_json", None),
    )
    payload["ineffective_reminders"] = _decode_json_list(
        payload.pop("ineffective_reminders_json", None),
    )
    payload["avoidance_patterns"] = _decode_json_list(
        payload.pop("avoidance_patterns_json", None),
    )
    return CompanionRelationship.model_validate(payload)


def _session_from_row(row) -> BuddyOnboardingSessionRecord | None:
    if row is None:
        return None
    payload = dict(row)
    payload["tightened"] = bool(payload.get("tightened", 0))
    payload["transcript"] = _decode_json_list(payload.pop("transcript_json", None))
    payload["candidate_directions"] = _decode_json_list(
        payload.pop("candidate_directions_json", None),
    )
    return BuddyOnboardingSessionRecord.model_validate(payload)


class SqliteHumanProfileRepository:
    def __init__(self, store: SQLiteStateStore) -> None:
        self._store = store
        self._store.initialize()

    def get_profile(self, profile_id: str) -> HumanProfile | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM human_profiles WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
        return _human_profile_from_row(row)

    def upsert_profile(self, profile: HumanProfile) -> HumanProfile:
        payload = profile.model_dump(mode="json")
        payload["interests_json"] = _encode_json(profile.interests)
        payload["strengths_json"] = _encode_json(profile.strengths)
        payload["constraints_json"] = _encode_json(profile.constraints)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO human_profiles (
                    profile_id, display_name, profession, current_stage,
                    interests_json, strengths_json, constraints_json, goal_intention,
                    created_at, updated_at
                ) VALUES (
                    :profile_id, :display_name, :profession, :current_stage,
                    :interests_json, :strengths_json, :constraints_json, :goal_intention,
                    :created_at, :updated_at
                )
                ON CONFLICT(profile_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    profession = excluded.profession,
                    current_stage = excluded.current_stage,
                    interests_json = excluded.interests_json,
                    strengths_json = excluded.strengths_json,
                    constraints_json = excluded.constraints_json,
                    goal_intention = excluded.goal_intention,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return profile


class SqliteGrowthTargetRepository:
    def __init__(self, store: SQLiteStateStore) -> None:
        self._store = store
        self._store.initialize()

    def get_active_target(self, profile_id: str) -> GrowthTarget | None:
        with self._store.connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM growth_targets
                WHERE profile_id = ?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (profile_id,),
            ).fetchone()
        return _growth_target_from_row(row)

    def upsert_target(self, target: GrowthTarget) -> GrowthTarget:
        payload = target.model_dump(mode="json")
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO growth_targets (
                    target_id, profile_id, primary_direction, final_goal,
                    why_it_matters, current_cycle_label, created_at, updated_at
                ) VALUES (
                    :target_id, :profile_id, :primary_direction, :final_goal,
                    :why_it_matters, :current_cycle_label, :created_at, :updated_at
                )
                ON CONFLICT(target_id) DO UPDATE SET
                    profile_id = excluded.profile_id,
                    primary_direction = excluded.primary_direction,
                    final_goal = excluded.final_goal,
                    why_it_matters = excluded.why_it_matters,
                    current_cycle_label = excluded.current_cycle_label,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return target


class SqliteCompanionRelationshipRepository:
    def __init__(self, store: SQLiteStateStore) -> None:
        self._store = store
        self._store.initialize()

    def get_relationship(self, profile_id: str) -> CompanionRelationship | None:
        with self._store.connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM companion_relationships
                WHERE profile_id = ?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (profile_id,),
            ).fetchone()
        return _relationship_from_row(row)

    def upsert_relationship(
        self,
        relationship: CompanionRelationship,
    ) -> CompanionRelationship:
        payload = relationship.model_dump(mode="json")
        payload["effective_reminders_json"] = _encode_json(
            relationship.effective_reminders,
        )
        payload["ineffective_reminders_json"] = _encode_json(
            relationship.ineffective_reminders,
        )
        payload["avoidance_patterns_json"] = _encode_json(
            relationship.avoidance_patterns,
        )
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO companion_relationships (
                    relationship_id, profile_id, buddy_name, encouragement_style,
                    effective_reminders_json, ineffective_reminders_json,
                    avoidance_patterns_json, created_at, updated_at
                ) VALUES (
                    :relationship_id, :profile_id, :buddy_name, :encouragement_style,
                    :effective_reminders_json, :ineffective_reminders_json,
                    :avoidance_patterns_json, :created_at, :updated_at
                )
                ON CONFLICT(relationship_id) DO UPDATE SET
                    profile_id = excluded.profile_id,
                    buddy_name = excluded.buddy_name,
                    encouragement_style = excluded.encouragement_style,
                    effective_reminders_json = excluded.effective_reminders_json,
                    ineffective_reminders_json = excluded.ineffective_reminders_json,
                    avoidance_patterns_json = excluded.avoidance_patterns_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return relationship


class SqliteBuddyOnboardingSessionRepository:
    def __init__(self, store: SQLiteStateStore) -> None:
        self._store = store
        self._store.initialize()

    def get_session(self, session_id: str) -> BuddyOnboardingSessionRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM buddy_onboarding_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return _session_from_row(row)

    def upsert_session(
        self,
        session: BuddyOnboardingSessionRecord,
    ) -> BuddyOnboardingSessionRecord:
        payload = session.model_dump(mode="json")
        payload["tightened"] = 1 if session.tightened else 0
        payload["transcript_json"] = _encode_json(session.transcript)
        payload["candidate_directions_json"] = _encode_json(session.candidate_directions)
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO buddy_onboarding_sessions (
                    session_id, profile_id, status, question_count, tightened,
                    next_question, transcript_json, candidate_directions_json,
                    recommended_direction, selected_direction, created_at, updated_at
                ) VALUES (
                    :session_id, :profile_id, :status, :question_count, :tightened,
                    :next_question, :transcript_json, :candidate_directions_json,
                    :recommended_direction, :selected_direction, :created_at, :updated_at
                )
                ON CONFLICT(session_id) DO UPDATE SET
                    profile_id = excluded.profile_id,
                    status = excluded.status,
                    question_count = excluded.question_count,
                    tightened = excluded.tightened,
                    next_question = excluded.next_question,
                    transcript_json = excluded.transcript_json,
                    candidate_directions_json = excluded.candidate_directions_json,
                    recommended_direction = excluded.recommended_direction,
                    selected_direction = excluded.selected_direction,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return session


__all__ = [
    "BuddyOnboardingSessionRecord",
    "SqliteBuddyOnboardingSessionRepository",
    "SqliteCompanionRelationshipRepository",
    "SqliteGrowthTargetRepository",
    "SqliteHumanProfileRepository",
]
