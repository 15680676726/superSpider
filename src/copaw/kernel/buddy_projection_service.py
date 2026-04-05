# -*- coding: utf-8 -*-
"""Buddy presentation and growth derivation from formal runtime truth."""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field

from ..state import BuddyGrowthProjection, BuddyPresentation, CompanionRelationship, GrowthTarget, HumanProfile
from ..state.repositories_buddy import (
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)


class BuddySurfacePayload(BaseModel):
    profile: HumanProfile
    growth_target: GrowthTarget | None = None
    relationship: CompanionRelationship | None = None
    presentation: BuddyPresentation
    growth: BuddyGrowthProjection


CurrentFocusResolver = Callable[[str], dict[str, str] | None]


class BuddyProjectionService:
    def __init__(
        self,
        *,
        profile_repository: SqliteHumanProfileRepository,
        growth_target_repository: SqliteGrowthTargetRepository,
        relationship_repository: SqliteCompanionRelationshipRepository,
        onboarding_session_repository: SqliteBuddyOnboardingSessionRepository,
        human_assist_task_service: object | None = None,
        current_focus_resolver: CurrentFocusResolver | None = None,
    ) -> None:
        self._profile_repository = profile_repository
        self._growth_target_repository = growth_target_repository
        self._relationship_repository = relationship_repository
        self._onboarding_session_repository = onboarding_session_repository
        self._human_assist_task_service = human_assist_task_service
        self._current_focus_resolver = current_focus_resolver

    def build_chat_surface(self, *, profile_id: str | None = None) -> BuddySurfacePayload:
        profile = self._resolve_profile(profile_id)
        if profile is None:
            raise ValueError("Buddy profile is not available")
        target = self._growth_target_repository.get_active_target(profile.profile_id)
        relationship = self._relationship_repository.get_relationship(profile.profile_id)
        session = self._onboarding_session_repository.get_latest_session_for_profile(profile.profile_id)
        current_focus = (
            self._current_focus_resolver(profile.profile_id)
            if callable(self._current_focus_resolver)
            else None
        ) or {}
        current_task_summary = str(current_focus.get("current_task_summary") or "").strip()
        why_now_summary = str(current_focus.get("why_now_summary") or "").strip()
        if not current_task_summary:
            current_task_summary = self._fallback_current_task_summary(profile.profile_id)
        if not why_now_summary:
            why_now_summary = self._fallback_why_now_summary(target)
        buddy_name = (
            relationship.buddy_name.strip()
            if relationship is not None and relationship.buddy_name.strip()
            else "你的伙伴"
        )
        onboarding_turn_count = len(session.transcript) if session is not None else 0
        relationship_communication_count = (
            int(relationship.communication_count) if relationship is not None else 0
        )
        communication_count = onboarding_turn_count + relationship_communication_count
        completed_support_runs = self._completed_support_runs(profile.profile_id)
        completed_assisted_closures = self._completed_assisted_closures(profile.profile_id)
        knowledge_value = max(0, len(profile.interests) * 10 + len(profile.strengths) * 12 + (10 if target else 0))
        skill_value = max(0, completed_support_runs * 15 + completed_assisted_closures * 10)
        relationship_pleasant_score = (
            int(relationship.pleasant_interaction_score) if relationship is not None else 0
        )
        pleasant_interaction_score = min(
            100,
            relationship_pleasant_score + communication_count * 4 + completed_support_runs * 4,
        )
        intimacy = min(100, communication_count * 8 + (15 if relationship and relationship.buddy_name.strip() else 0))
        affinity = min(100, intimacy // 2 + pleasant_interaction_score // 2)
        relationship_experience = (
            int(relationship.companion_experience) if relationship is not None else 0
        )
        companion_experience = relationship_experience + (
            onboarding_turn_count * 5
            + completed_support_runs * 10
            + completed_assisted_closures * 8
            + len(profile.strengths) * 3
        )
        growth_level = max(1, 1 + companion_experience // 40)
        evolution_stage, rarity, progress_to_next_stage = self._resolve_evolution(
            experience=companion_experience,
        )
        lifecycle_state = "named" if relationship and relationship.buddy_name.strip() else "born-unnamed"
        if growth_level >= 3:
            lifecycle_state = "bonded"
        presence_state = "focused" if current_task_summary else "attentive"
        mood_state = "determined" if current_task_summary else "warm"
        presentation = BuddyPresentation(
            profile_id=profile.profile_id,
            buddy_name=buddy_name,
            lifecycle_state=lifecycle_state,
            presence_state=presence_state,
            mood_state=mood_state,
            current_form=evolution_stage,
            rarity=rarity,
            current_goal_summary=target.final_goal if target is not None else profile.goal_intention,
            current_task_summary=current_task_summary,
            why_now_summary=why_now_summary,
        )
        growth = BuddyGrowthProjection(
            profile_id=profile.profile_id,
            intimacy=intimacy,
            affinity=affinity,
            growth_level=growth_level,
            companion_experience=companion_experience,
            knowledge_value=knowledge_value,
            skill_value=skill_value,
            pleasant_interaction_score=pleasant_interaction_score,
            communication_count=communication_count,
            completed_support_runs=completed_support_runs,
            completed_assisted_closures=completed_assisted_closures,
            evolution_stage=evolution_stage,
            progress_to_next_stage=progress_to_next_stage,
        )
        return BuddySurfacePayload(
            profile=profile,
            growth_target=target,
            relationship=relationship,
            presentation=presentation,
            growth=growth,
        )

    def build_cockpit_summary(self, *, profile_id: str | None = None) -> dict[str, Any]:
        surface = self.build_chat_surface(profile_id=profile_id)
        return {
            "buddy_name": surface.presentation.buddy_name,
            "lifecycle_state": surface.presentation.lifecycle_state,
            "presence_state": surface.presentation.presence_state,
            "mood_state": surface.presentation.mood_state,
            "evolution_stage": surface.growth.evolution_stage,
            "growth_level": surface.growth.growth_level,
            "intimacy": surface.growth.intimacy,
            "affinity": surface.growth.affinity,
            "current_goal_summary": surface.presentation.current_goal_summary,
            "current_task_summary": surface.presentation.current_task_summary,
            "why_now_summary": surface.presentation.why_now_summary,
        }

    def _resolve_profile(self, profile_id: str | None) -> HumanProfile | None:
        if profile_id:
            return self._profile_repository.get_profile(profile_id)
        if self._profile_repository.count_profiles() > 1:
            raise ValueError("Buddy surface requires explicit profile_id when multiple profiles exist")
        return self._profile_repository.get_latest_profile()

    def _fallback_current_task_summary(self, profile_id: str) -> str:
        service = self._human_assist_task_service
        getter = getattr(service, "list_tasks", None)
        if callable(getter):
            try:
                tasks = getter(limit=20, profile_id=profile_id)
            except TypeError:
                tasks = getter(limit=20)
            for task in tasks:
                task_profile_id = getattr(task, "profile_id", None)
                if task_profile_id != profile_id:
                    continue
                status = str(getattr(task, "status", "")).strip().lower()
                if status in {"closed", "cancelled", "expired"}:
                    continue
                return str(
                    getattr(task, "required_action", None)
                    or getattr(task, "summary", None)
                    or getattr(task, "title", None)
                    or ""
                ).strip()
        return "先把眼前这一步做完，我们再一起看下一步。"

    def _fallback_why_now_summary(self, target: GrowthTarget | None) -> str:
        if target is not None and target.why_it_matters.strip():
            return target.why_it_matters.strip()
        return "因为只有先推进当前这一步，你最终想去的地方才不会继续停在原地。"

    def _completed_support_runs(self, profile_id: str) -> int:
        service = self._human_assist_task_service
        getter = getattr(service, "list_tasks", None)
        if not callable(getter):
            return 0
        count = 0
        try:
            tasks = getter(limit=100, profile_id=profile_id)
        except TypeError:
            tasks = getter(limit=100)
        for task in tasks:
            task_profile_id = getattr(task, "profile_id", None)
            if task_profile_id != profile_id:
                continue
            status = str(getattr(task, "status", "")).strip().lower()
            if status in {"resume_queued", "closed"}:
                count += 1
        return count

    def _completed_assisted_closures(self, profile_id: str) -> int:
        service = self._human_assist_task_service
        getter = getattr(service, "list_tasks", None)
        if not callable(getter):
            return 0
        count = 0
        try:
            tasks = getter(limit=100, profile_id=profile_id)
        except TypeError:
            tasks = getter(limit=100)
        for task in tasks:
            task_profile_id = getattr(task, "profile_id", None)
            if task_profile_id != profile_id:
                continue
            status = str(getattr(task, "status", "")).strip().lower()
            if status == "closed":
                count += 1
        return count

    def _resolve_evolution(self, *, experience: int) -> tuple[str, str, int]:
        thresholds = [
            (0, "seed", "common", 40),
            (40, "bonded", "uncommon", 80),
            (80, "capable", "rare", 140),
            (140, "seasoned", "epic", 220),
            (220, "signature", "signature", None),
        ]
        current_stage = "seed"
        current_rarity = "common"
        next_threshold = 40
        for threshold, stage, rarity, next_value in thresholds:
            if experience >= threshold:
                current_stage = stage
                current_rarity = rarity
                next_threshold = next_value
        if next_threshold is None:
            return current_stage, current_rarity, 100
        previous_threshold = 0
        for threshold, stage, _rarity, _next_value in thresholds:
            if stage == current_stage:
                previous_threshold = threshold
                break
        span = max(1, next_threshold - previous_threshold)
        progress = min(100, max(0, ((experience - previous_threshold) * 100) // span))
        return current_stage, current_rarity, progress


__all__ = ["BuddyProjectionService", "BuddySurfacePayload"]
