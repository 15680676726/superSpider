# -*- coding: utf-8 -*-
"""Buddy-first onboarding service built on top of existing main-brain truth."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from ..state import CompanionRelationship, GrowthTarget, HumanProfile
from ..state.main_brain_service import (
    AssignmentService,
    BacklogService,
    OperatingCycleService,
    OperatingLaneService,
)
from ..state.models import IndustryInstanceRecord
from ..state.repositories_buddy import (
    BuddyOnboardingSessionRecord,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)
from ..state.repositories import SqliteIndustryInstanceRepository


class BuddyIdentitySubmitResult(BaseModel):
    session_id: str
    profile: HumanProfile
    question_count: int = Field(ge=1)
    next_question: str
    finished: bool = False


class BuddyClarificationResult(BaseModel):
    session_id: str
    question_count: int = Field(ge=1)
    tightened: bool = False
    finished: bool = False
    next_question: str = ""
    candidate_directions: list[str] = Field(default_factory=list)
    recommended_direction: str = ""


@dataclass(slots=True)
class BuddyDirectionConfirmationResult:
    session: BuddyOnboardingSessionRecord
    growth_target: GrowthTarget
    relationship: CompanionRelationship


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


class BuddyOnboardingService:
    MAX_QUESTIONS = 9
    TIGHTEN_AFTER = 5

    def __init__(
        self,
        *,
        profile_repository: SqliteHumanProfileRepository,
        growth_target_repository: SqliteGrowthTargetRepository,
        relationship_repository: SqliteCompanionRelationshipRepository,
        onboarding_session_repository: SqliteBuddyOnboardingSessionRepository,
        industry_instance_repository: SqliteIndustryInstanceRepository | None = None,
        operating_lane_service: OperatingLaneService | None = None,
        backlog_service: BacklogService | None = None,
        operating_cycle_service: OperatingCycleService | None = None,
        assignment_service: AssignmentService | None = None,
    ) -> None:
        self._profile_repository = profile_repository
        self._growth_target_repository = growth_target_repository
        self._relationship_repository = relationship_repository
        self._onboarding_session_repository = onboarding_session_repository
        self._industry_instance_repository = industry_instance_repository
        self._operating_lane_service = operating_lane_service
        self._backlog_service = backlog_service
        self._operating_cycle_service = operating_cycle_service
        self._assignment_service = assignment_service

    def submit_identity(
        self,
        *,
        display_name: str,
        profession: str,
        current_stage: str,
        interests: list[str] | None = None,
        strengths: list[str] | None = None,
        constraints: list[str] | None = None,
        goal_intention: str,
    ) -> BuddyIdentitySubmitResult:
        profile = self._profile_repository.upsert_profile(
            HumanProfile(
                display_name=display_name,
                profession=profession,
                current_stage=current_stage,
                interests=interests or [],
                strengths=strengths or [],
                constraints=constraints or [],
                goal_intention=goal_intention,
            ),
        )
        session = self._onboarding_session_repository.upsert_session(
            BuddyOnboardingSessionRecord(
                profile_id=profile.profile_id,
                question_count=1,
                next_question=self._build_question(profile=profile, question_count=1),
                transcript=[profile.goal_intention],
            ),
        )
        return BuddyIdentitySubmitResult(
            session_id=session.session_id,
            profile=profile,
            question_count=session.question_count,
            next_question=session.next_question,
            finished=False,
        )

    def answer_clarification_turn(
        self,
        *,
        session_id: str,
        answer: str,
        existing_question_count: int | None = None,
    ) -> BuddyClarificationResult:
        session = self._require_session(session_id)
        profile = self._require_profile(session.profile_id)
        merged_transcript = [*session.transcript, answer.strip()]
        question_count = min(
            self.MAX_QUESTIONS,
            max(existing_question_count or 0, session.question_count + 1),
        )
        tightened = question_count > self.TIGHTEN_AFTER
        candidate_directions = self._candidate_directions(
            profile=profile,
            transcript=merged_transcript,
        )
        recommended = candidate_directions[0] if candidate_directions else ""
        finished = question_count >= self.MAX_QUESTIONS
        next_question = "" if finished else self._build_question(
            profile=profile,
            question_count=question_count,
            tightened=tightened,
        )
        updated = self._onboarding_session_repository.upsert_session(
            session.model_copy(
                update={
                    "question_count": question_count,
                    "tightened": tightened,
                    "next_question": next_question,
                    "transcript": merged_transcript,
                    "candidate_directions": candidate_directions,
                    "recommended_direction": recommended,
                    "status": "direction-ready" if finished else "clarifying",
                },
            ),
        )
        return BuddyClarificationResult(
            session_id=updated.session_id,
            question_count=updated.question_count,
            tightened=updated.tightened,
            finished=finished,
            next_question=updated.next_question,
            candidate_directions=updated.candidate_directions,
            recommended_direction=updated.recommended_direction,
        )

    def get_candidate_directions(self, *, session_id: str) -> BuddyClarificationResult:
        session = self._require_session(session_id)
        return BuddyClarificationResult(
            session_id=session.session_id,
            question_count=session.question_count,
            tightened=session.tightened,
            finished=bool(session.candidate_directions),
            next_question=session.next_question,
            candidate_directions=session.candidate_directions,
            recommended_direction=session.recommended_direction,
        )

    def confirm_primary_direction(
        self,
        *,
        session_id: str,
        selected_direction: str,
    ) -> BuddyDirectionConfirmationResult:
        session = self._require_session(session_id)
        profile = self._require_profile(session.profile_id)
        normalized = selected_direction.strip()
        if not normalized:
            raise ValueError("selected_direction is required")
        if session.candidate_directions and normalized not in session.candidate_directions:
            raise ValueError("selected_direction must match one generated candidate")
        growth_target = self._growth_target_repository.upsert_target(
            GrowthTarget(
                profile_id=profile.profile_id,
                primary_direction=normalized,
                final_goal=self._final_goal(profile=profile, direction=normalized),
                why_it_matters=self._why_it_matters(profile=profile),
                current_cycle_label="Cycle 1",
            ),
        )
        existing_relationship = self._relationship_repository.get_relationship(profile.profile_id)
        relationship = self._relationship_repository.upsert_relationship(
            (existing_relationship or CompanionRelationship(profile_id=profile.profile_id)).model_copy(
                update={
                    "profile_id": profile.profile_id,
                    "encouragement_style": "old-friend",
                },
            ),
        )
        growth_target = self._ensure_growth_scaffold(
            profile=profile,
            growth_target=growth_target,
        )
        updated_session = self._onboarding_session_repository.upsert_session(
            session.model_copy(
                update={
                    "status": "confirmed",
                    "selected_direction": normalized,
                    "recommended_direction": session.recommended_direction or normalized,
                },
            ),
        )
        return BuddyDirectionConfirmationResult(
            session=updated_session,
            growth_target=growth_target,
            relationship=relationship,
        )

    def record_chat_interaction(
        self,
        *,
        profile_id: str,
        user_message: str,
        interaction_mode: str | None = None,
    ) -> CompanionRelationship | None:
        profile = self._profile_repository.get_profile(profile_id)
        if profile is None:
            return None
        relationship = self._relationship_repository.get_relationship(profile_id)
        if relationship is None:
            relationship = CompanionRelationship(profile_id=profile_id)
        normalized_message = str(user_message or "").strip()
        if not normalized_message:
            return relationship
        pleasant_delta = 6
        if len(normalized_message) >= 48:
            pleasant_delta += 4
        strong_pull = str(interaction_mode or "").strip().lower() == "strong-pull"
        experience_delta = 8 if strong_pull else 5
        updated = relationship.model_copy(
            update={
                "communication_count": relationship.communication_count + 1,
                "pleasant_interaction_score": min(
                    100,
                    relationship.pleasant_interaction_score + pleasant_delta,
                ),
                "companion_experience": relationship.companion_experience + experience_delta,
                "strong_pull_count": relationship.strong_pull_count + (1 if strong_pull else 0),
                "last_interaction_at": _utc_now().isoformat(),
            },
        )
        return self._relationship_repository.upsert_relationship(updated)

    def name_buddy(
        self,
        *,
        session_id: str,
        buddy_name: str,
    ) -> CompanionRelationship:
        session = self._require_session(session_id)
        relationship = self._relationship_repository.get_relationship(session.profile_id)
        if relationship is None:
            raise ValueError("primary direction must be confirmed before naming Buddy")
        updated = self._relationship_repository.upsert_relationship(
            relationship.model_copy(update={"buddy_name": buddy_name.strip() or "Buddy"}),
        )
        self._onboarding_session_repository.upsert_session(
            session.model_copy(update={"status": "named"}),
        )
        return updated

    def _require_session(self, session_id: str) -> BuddyOnboardingSessionRecord:
        session = self._onboarding_session_repository.get_session(session_id)
        if session is None:
            raise ValueError(f"Buddy onboarding session '{session_id}' not found")
        return session

    def _require_profile(self, profile_id: str) -> HumanProfile:
        profile = self._profile_repository.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"Human profile '{profile_id}' not found")
        return profile

    def _build_question(
        self,
        *,
        profile: HumanProfile,
        question_count: int,
        tightened: bool = False,
    ) -> str:
        if tightened:
            return (
                f"{profile.display_name}，如果现在只能先改变一件事，"
                "你最想摆脱的是什么，为什么必须是现在？"
            )
        prompts = [
            "先告诉我，你最想真正改变的人生部分是什么？",
            "如果接下来一年只允许有一个明显进步，你最希望是哪一块？",
            "什么样的长期方向，会让你觉得自己是在为真正想要的人生前进？",
            "你最不想继续重复的旧状态是什么？",
            "如果我现在只能陪你先抓住一个方向，你最不想放弃的东西是什么？",
        ]
        index = min(max(question_count - 1, 0), len(prompts) - 1)
        return prompts[index]

    def _candidate_directions(
        self,
        *,
        profile: HumanProfile,
        transcript: list[str],
    ) -> list[str]:
        source = " ".join(
            [
                profile.profession,
                profile.current_stage,
                profile.goal_intention,
                *profile.interests,
                *profile.strengths,
                *transcript,
            ],
        ).lower()
        directions: list[str] = []
        if any(token in source for token in ("content", "creator", "writing", "write", "audience")):
            directions.append("Build an independent creator-business growth path")
        if any(token in source for token in ("design", "designer", "product", "systems")):
            directions.append("Build a high-leverage design and systems leadership path")
        if any(token in source for token in ("operator", "operations", "process", "execution")):
            directions.append("Build a resilient operator-to-strategist career path")
        if any(token in source for token in ("health", "discipline", "energy", "exercise")):
            directions.append("Build a disciplined health-and-self-mastery growth path")
        directions.append("Build a stable self-directed growth path with increasing autonomy")
        unique = _unique(directions)
        return unique[:3]

    def _final_goal(self, *, profile: HumanProfile, direction: str) -> str:
        lowered = direction.lower()
        if "creator-business" in lowered:
            return f"Help {profile.display_name} build a durable creator-business and independent growth trajectory"
        if "design and systems" in lowered:
            return f"Help {profile.display_name} become a high-leverage builder of design and systems leadership"
        if "operator-to-strategist" in lowered:
            return f"Help {profile.display_name} transition from execution-heavy work into resilient strategic ownership"
        return f"Help {profile.display_name} build a stable long-term growth direction with real personal agency"

    def _why_it_matters(self, *, profile: HumanProfile) -> str:
        if profile.goal_intention.strip():
            return profile.goal_intention.strip()
        return f"{profile.display_name} wants a growth direction that is meaningful and sustainable."

    def _ensure_growth_scaffold(
        self,
        *,
        profile: HumanProfile,
        growth_target: GrowthTarget,
    ) -> GrowthTarget:
        if (
            self._industry_instance_repository is None
            or self._operating_lane_service is None
            or self._backlog_service is None
            or self._operating_cycle_service is None
            or self._assignment_service is None
        ):
            return growth_target
        instance_id = f"buddy:{profile.profile_id}"
        existing_instance = self._industry_instance_repository.get_instance(instance_id)
        instance = IndustryInstanceRecord(
            instance_id=instance_id,
            label=profile.display_name,
            summary=growth_target.final_goal,
            owner_scope=profile.profile_id,
            status="active",
            profile_payload={
                "profile_id": profile.profile_id,
                "display_name": profile.display_name,
                "profession": profile.profession,
                "current_stage": profile.current_stage,
                "goal_intention": profile.goal_intention,
                "interests": list(profile.interests),
                "strengths": list(profile.strengths),
                "constraints": list(profile.constraints),
            },
            execution_core_identity_payload={
                "profile_id": profile.profile_id,
                "primary_direction": growth_target.primary_direction,
                "final_goal": growth_target.final_goal,
            },
            goal_ids=list(existing_instance.goal_ids) if existing_instance is not None else [],
            agent_ids=list(existing_instance.agent_ids) if existing_instance is not None else [],
            schedule_ids=list(existing_instance.schedule_ids) if existing_instance is not None else [],
            lifecycle_status="running",
            autonomy_status="guided",
            current_cycle_id=existing_instance.current_cycle_id if existing_instance is not None else None,
            next_cycle_due_at=existing_instance.next_cycle_due_at if existing_instance is not None else None,
            last_cycle_started_at=existing_instance.last_cycle_started_at if existing_instance is not None else None,
            created_at=existing_instance.created_at if existing_instance is not None else _utc_now(),
            updated_at=_utc_now(),
        )
        persisted_instance = self._industry_instance_repository.upsert_instance(instance)
        lanes = self._operating_lane_service.seed_from_roles(
            industry_instance_id=instance_id,
            roles=self._build_lane_roles(profile=profile, growth_target=growth_target),
        )
        backlog_items = [
            self._backlog_service.record_generated_item(
                industry_instance_id=instance_id,
                lane_id=lane_id,
                title=title,
                summary=summary,
                priority=priority,
                source_kind="buddy-bootstrap",
                source_ref=source_ref,
                metadata={"profile_id": profile.profile_id, "primary_direction": growth_target.primary_direction},
            )
            for lane_id, title, summary, priority, source_ref in self._build_initial_backlog_specs(
                profile=profile,
                growth_target=growth_target,
                lanes=lanes,
            )
        ]
        focus_lane_ids = [lane.id for lane in lanes[:2]] or [lane.id for lane in lanes]
        cycle = self._operating_cycle_service.start_cycle(
            industry_instance_id=instance_id,
            label=profile.display_name,
            cycle_kind="daily",
            status="active",
            focus_lane_ids=focus_lane_ids,
            backlog_item_ids=[item.id for item in backlog_items],
            source_ref=f"buddy-onboarding:{profile.profile_id}",
            summary=f"Buddy onboarding cycle for {profile.display_name}",
            metadata={"profile_id": profile.profile_id, "primary_direction": growth_target.primary_direction},
        )
        assignments = self._assignment_service.ensure_assignments(
            industry_instance_id=instance_id,
            cycle_id=cycle.id,
            specs=[
                {
                    "lane_id": item.lane_id,
                    "backlog_item_id": item.id,
                    "title": item.title,
                    "summary": item.summary,
                    "status": "queued" if index == 0 else "planned",
                    "metadata": {
                        "profile_id": profile.profile_id,
                        "primary_direction": growth_target.primary_direction,
                    },
                }
                for index, item in enumerate(backlog_items)
            ],
        )
        self._industry_instance_repository.upsert_instance(
            persisted_instance.model_copy(
                update={
                    "current_cycle_id": cycle.id,
                    "last_cycle_started_at": cycle.started_at,
                    "next_cycle_due_at": cycle.due_at,
                    "updated_at": _utc_now(),
                },
            ),
        )
        return self._growth_target_repository.upsert_target(
            growth_target.model_copy(update={"current_cycle_label": cycle.title}),
        )

    def _build_lane_roles(
        self,
        *,
        profile: HumanProfile,
        growth_target: GrowthTarget,
    ) -> list[dict[str, str]]:
        del growth_target
        return [
            {
                "role_id": "growth-focus",
                "role_name": "Growth Focus",
                "goal_kind": "growth-focus",
                "mission": f"Keep {profile.display_name} aligned to the chosen long-term direction.",
            },
            {
                "role_id": "proof-of-work",
                "role_name": "Proof Of Work",
                "goal_kind": "proof-of-work",
                "mission": f"Turn {profile.display_name}'s current direction into visible proof and momentum.",
            },
        ]

    def _build_initial_backlog_specs(
        self,
        *,
        profile: HumanProfile,
        growth_target: GrowthTarget,
        lanes: list[object],
    ) -> list[tuple[str | None, str, str, int, str]]:
        lane_ids = [getattr(lane, "id", None) for lane in lanes]
        primary_lane_id = lane_ids[0] if lane_ids else None
        proof_lane_id = lane_ids[1] if len(lane_ids) > 1 else primary_lane_id
        return [
            (
                primary_lane_id,
                "Clarify the first concrete proof point",
                f"Define the first concrete proof that shows {profile.display_name} is moving toward {growth_target.primary_direction}.",
                3,
                f"profile:{profile.profile_id}:proof-point",
            ),
            (
                proof_lane_id,
                "Ship the first visible growth artifact",
                f"Create one visible artifact that starts moving '{growth_target.final_goal}' out of imagination and into evidence.",
                2,
                f"profile:{profile.profile_id}:first-artifact",
            ),
            (
                primary_lane_id,
                "Stabilize the weekly rhythm",
                f"Establish a weekly rhythm that {profile.display_name} can realistically sustain without burning out.",
                1,
                f"profile:{profile.profile_id}:weekly-rhythm",
            ),
        ]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "BuddyClarificationResult",
    "BuddyDirectionConfirmationResult",
    "BuddyIdentitySubmitResult",
    "BuddyOnboardingService",
]
