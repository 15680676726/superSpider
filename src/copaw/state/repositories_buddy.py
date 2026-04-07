# -*- coding: utf-8 -*-
"""Buddy-specific repositories for onboarding truth and transitional sessions."""
from __future__ import annotations

from datetime import datetime, timezone
import json

from pydantic import Field

from .model_support import UpdatedRecord, _new_record_id
from .models_buddy import (
    BuddyDomainCapabilityRecord,
    CompanionRelationship,
    GrowthTarget,
    HumanProfile,
)
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


def _domain_capability_from_row(row) -> BuddyDomainCapabilityRecord | None:
    if row is None:
        return None
    return BuddyDomainCapabilityRecord.model_validate(dict(row))


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

    def get_latest_profile(self) -> HumanProfile | None:
        with self._store.connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM human_profiles
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
            ).fetchone()
        return _human_profile_from_row(row)

    def count_profiles(self) -> int:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM human_profiles",
            ).fetchone()
        return int(row["count"] if row is not None else 0)

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
                    avoidance_patterns_json, communication_count,
                    pleasant_interaction_score, companion_experience,
                    strong_pull_count, last_interaction_at, created_at, updated_at
                ) VALUES (
                    :relationship_id, :profile_id, :buddy_name, :encouragement_style,
                    :effective_reminders_json, :ineffective_reminders_json,
                    :avoidance_patterns_json, :communication_count,
                    :pleasant_interaction_score, :companion_experience,
                    :strong_pull_count, :last_interaction_at, :created_at, :updated_at
                )
                ON CONFLICT(relationship_id) DO UPDATE SET
                    profile_id = excluded.profile_id,
                    buddy_name = excluded.buddy_name,
                    encouragement_style = excluded.encouragement_style,
                    effective_reminders_json = excluded.effective_reminders_json,
                    ineffective_reminders_json = excluded.ineffective_reminders_json,
                    avoidance_patterns_json = excluded.avoidance_patterns_json,
                    communication_count = excluded.communication_count,
                    pleasant_interaction_score = excluded.pleasant_interaction_score,
                    companion_experience = excluded.companion_experience,
                    strong_pull_count = excluded.strong_pull_count,
                    last_interaction_at = excluded.last_interaction_at,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return relationship


class SqliteBuddyDomainCapabilityRepository:
    def __init__(self, store: SQLiteStateStore) -> None:
        self._store = store
        self._store.initialize()

    def get_domain_capability(self, domain_id: str) -> BuddyDomainCapabilityRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM buddy_domain_capabilities WHERE domain_id = ?",
                (domain_id,),
            ).fetchone()
        return _domain_capability_from_row(row)

    def get_active_domain_capability(
        self,
        profile_id: str,
    ) -> BuddyDomainCapabilityRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM buddy_domain_capabilities
                WHERE profile_id = ? AND status = 'active'
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (profile_id,),
            ).fetchone()
        return _domain_capability_from_row(row)

    def list_domain_capabilities(
        self,
        profile_id: str,
        *,
        include_archived: bool = True,
    ) -> list[BuddyDomainCapabilityRecord]:
        query = """
            SELECT * FROM buddy_domain_capabilities
            WHERE profile_id = ?
        """
        params: list[object] = [profile_id]
        if not include_archived:
            query += " AND status = 'active'"
        query += """
            ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,
                     updated_at DESC,
                     created_at DESC
        """
        with self._store.connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [
            record
            for record in (_domain_capability_from_row(row) for row in rows)
            if record is not None
        ]

    def find_domain_capabilities_by_key(
        self,
        profile_id: str,
        domain_key: str,
    ) -> list[BuddyDomainCapabilityRecord]:
        with self._store.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM buddy_domain_capabilities
                WHERE profile_id = ? AND domain_key = ?
                ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,
                         updated_at DESC,
                         created_at DESC
                """,
                (profile_id, domain_key),
            ).fetchall()
        return [
            record
            for record in (_domain_capability_from_row(row) for row in rows)
            if record is not None
        ]

    def upsert_domain_capability(
        self,
        record: BuddyDomainCapabilityRecord,
    ) -> BuddyDomainCapabilityRecord:
        payload = record.model_dump(mode="json")
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO buddy_domain_capabilities (
                    domain_id, profile_id, domain_key, domain_label, status,
                    strategy_score, execution_score, evidence_score, stability_score,
                    capability_score, evolution_stage, knowledge_value, skill_value,
                    completed_support_runs, completed_assisted_closures,
                    evidence_count, report_count, last_activated_at, last_progress_at,
                    created_at, updated_at
                ) VALUES (
                    :domain_id, :profile_id, :domain_key, :domain_label, :status,
                    :strategy_score, :execution_score, :evidence_score, :stability_score,
                    :capability_score, :evolution_stage, :knowledge_value, :skill_value,
                    :completed_support_runs, :completed_assisted_closures,
                    :evidence_count, :report_count, :last_activated_at, :last_progress_at,
                    :created_at, :updated_at
                )
                ON CONFLICT(domain_id) DO UPDATE SET
                    profile_id = excluded.profile_id,
                    domain_key = excluded.domain_key,
                    domain_label = excluded.domain_label,
                    status = excluded.status,
                    strategy_score = excluded.strategy_score,
                    execution_score = excluded.execution_score,
                    evidence_score = excluded.evidence_score,
                    stability_score = excluded.stability_score,
                    capability_score = excluded.capability_score,
                    evolution_stage = excluded.evolution_stage,
                    knowledge_value = excluded.knowledge_value,
                    skill_value = excluded.skill_value,
                    completed_support_runs = excluded.completed_support_runs,
                    completed_assisted_closures = excluded.completed_assisted_closures,
                    evidence_count = excluded.evidence_count,
                    report_count = excluded.report_count,
                    last_activated_at = excluded.last_activated_at,
                    last_progress_at = excluded.last_progress_at,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return record

    def archive_active_domain_capabilities(
        self,
        profile_id: str,
        *,
        except_domain_id: str | None = None,
    ) -> None:
        now = _utc_now_iso()
        query = """
            UPDATE buddy_domain_capabilities
            SET status = 'archived', updated_at = ?
            WHERE profile_id = ? AND status = 'active'
        """
        params: list[object] = [now, profile_id]
        if except_domain_id:
            query += " AND domain_id != ?"
            params.append(except_domain_id)
        with self._store.connection() as conn:
            conn.execute(query, tuple(params))


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

    def get_latest_session_for_profile(
        self,
        profile_id: str,
    ) -> BuddyOnboardingSessionRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM buddy_onboarding_sessions
                WHERE profile_id = ?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (profile_id,),
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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "BuddyOnboardingSessionRecord",
    "SqliteBuddyDomainCapabilityRepository",
    "SqliteBuddyOnboardingSessionRepository",
    "SqliteCompanionRelationshipRepository",
    "SqliteGrowthTargetRepository",
    "SqliteHumanProfileRepository",
]
