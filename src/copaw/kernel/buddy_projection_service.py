# -*- coding: utf-8 -*-
"""Buddy presentation and growth derivation from formal runtime truth."""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field

from .buddy_domain_capability import (
    capability_stage_from_score,
    derive_buddy_domain_key,
    progress_to_next_stage,
    stage_from_points,
)
from .buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from .buddy_execution_carrier import build_buddy_execution_carrier_handoff
from .buddy_runtime_focus import resolve_active_human_assist_focus
from ..state import (
    BuddyDomainCapabilityRecord,
    BuddyGrowthProjection,
    BuddyPresentation,
    CompanionRelationship,
    GrowthTarget,
    HumanProfile,
)
from ..state.repositories_buddy import (
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)


class BuddySurfacePayload(BaseModel):
    profile: HumanProfile
    growth_target: GrowthTarget | None = None
    relationship: CompanionRelationship | None = None
    execution_carrier: dict[str, object] | None = None
    onboarding: "BuddyOnboardingProjection"
    presentation: BuddyPresentation
    growth: BuddyGrowthProjection


CurrentFocusResolver = Callable[[str], dict[str, str] | None]


class BuddyOnboardingProjection(BaseModel):
    session_id: str | None = None
    status: str = "unborn"
    operation_id: str = ""
    operation_kind: str = ""
    operation_status: str = "idle"
    operation_error: str = ""
    activation_status: str = "idle"
    activation_error: str = ""
    activation_attempt_count: int = 0
    candidate_directions: list[str] = Field(default_factory=list)
    recommended_direction: str = ""
    selected_direction: str = ""
    service_intent: str = ""
    collaboration_role: str = "orchestrator"
    autonomy_level: str = "proactive"
    confirm_boundaries: list[str] = Field(default_factory=list)
    report_style: str = "result-first"
    collaboration_notes: str = ""
    requires_direction_confirmation: bool = False
    requires_naming: bool = False
    completed: bool = False


class BuddyProjectionService:
    def __init__(
        self,
        *,
        profile_repository: SqliteHumanProfileRepository,
        growth_target_repository: SqliteGrowthTargetRepository,
        relationship_repository: SqliteCompanionRelationshipRepository,
        onboarding_session_repository: SqliteBuddyOnboardingSessionRepository,
        domain_capability_repository: SqliteBuddyDomainCapabilityRepository | None = None,
        domain_capability_growth_service: BuddyDomainCapabilityGrowthService | None = None,
        human_assist_task_service: object | None = None,
        current_focus_resolver: CurrentFocusResolver | None = None,
    ) -> None:
        self._profile_repository = profile_repository
        self._growth_target_repository = growth_target_repository
        self._relationship_repository = relationship_repository
        self._onboarding_session_repository = onboarding_session_repository
        self._domain_capability_repository = domain_capability_repository
        self._domain_capability_growth_service = domain_capability_growth_service
        self._human_assist_task_service = human_assist_task_service
        self._current_focus_resolver = current_focus_resolver

    def build_optional_chat_surface(
        self,
        *,
        profile_id: str | None = None,
    ) -> BuddySurfacePayload | None:
        profile = self._resolve_profile(profile_id)
        if profile is None:
            return None
        target = self._growth_target_repository.get_active_target(profile.profile_id)
        relationship = self._relationship_repository.get_relationship(profile.profile_id)
        session = self._onboarding_session_repository.get_latest_session_for_profile(profile.profile_id)
        active_domain = self._resolve_active_domain_capability(profile.profile_id)
        execution_carrier = self._build_execution_carrier(
            profile=profile,
            growth_target=target,
            active_domain=active_domain,
        )
        onboarding = self._build_onboarding_projection(
            session=session,
            target=target,
            relationship=relationship,
            active_domain=active_domain,
        )
        current_focus = (
            self._current_focus_resolver(profile.profile_id)
            if callable(self._current_focus_resolver)
            else None
        ) or {}
        human_focus = resolve_active_human_assist_focus(
            profile.profile_id,
            self._human_assist_task_service,
        ) or {}
        current_task_summary = str(
            human_focus.get("current_task_summary")
            or current_focus.get("current_task_summary")
            or "",
        ).strip()
        why_now_summary = str(current_focus.get("why_now_summary") or "").strip()
        single_next_action_summary = str(
            human_focus.get("single_next_action_summary")
            or current_focus.get("single_next_action_summary")
            or "",
        ).strip()
        if not current_task_summary:
            current_task_summary = self._fallback_current_task_summary(profile.profile_id)
        if not why_now_summary:
            why_now_summary = self._fallback_why_now_summary(target)
        if not single_next_action_summary:
            single_next_action_summary = self._fallback_single_next_action_summary(
                profile_id=profile.profile_id,
                current_task_summary=current_task_summary,
            )
        buddy_name = (
            relationship.buddy_name.strip()
            if relationship is not None and relationship.buddy_name.strip()
            else "你的伙伴"
        )
        relationship_communication_count = (
            int(relationship.communication_count) if relationship is not None else 0
        )
        onboarding_signal_count = 0
        if session is not None:
            if any(
                str(getattr(session, field, "") or "").strip()
                for field in (
                    "service_intent",
                    "collaboration_role",
                    "autonomy_level",
                    "report_style",
                    "collaboration_notes",
                )
            ) or list(getattr(session, "confirm_boundaries", []) or []):
                onboarding_signal_count += 1
            if (
                str(getattr(session, "recommended_direction", "") or "").strip()
                or str(getattr(session, "selected_direction", "") or "").strip()
                or str(getattr(session, "draft_final_goal", "") or "").strip()
                or list(getattr(session, "draft_backlog_items", []) or [])
            ):
                onboarding_signal_count += 1
        if relationship is not None and str(getattr(relationship, "buddy_name", "") or "").strip():
            onboarding_signal_count += 1
        communication_count = max(relationship_communication_count, onboarding_signal_count)
        relationship_pleasant_score = (
            int(relationship.pleasant_interaction_score) if relationship is not None else 0
        )
        pleasant_interaction_score = min(
            100,
            relationship_pleasant_score + communication_count * 4,
        )
        intimacy = min(
            100,
            communication_count * 8 + (15 if relationship and relationship.buddy_name.strip() else 0),
        )
        affinity = min(100, intimacy // 2 + pleasant_interaction_score // 2)
        growth = self._build_growth_projection(
            profile=profile,
            target=target,
            relationship=relationship,
            active_domain=active_domain,
            intimacy=intimacy,
            affinity=affinity,
            pleasant_interaction_score=pleasant_interaction_score,
            communication_count=communication_count,
        )
        lifecycle_state = "named" if relationship and relationship.buddy_name.strip() else "born-unnamed"
        if intimacy >= 40:
            lifecycle_state = "bonded"
        presence_state = "focused" if current_task_summary else "attentive"
        mood_state = "determined" if current_task_summary else "warm"
        companion_strategy_summary = self._build_companion_strategy_summary(
            relationship=relationship,
        )
        presentation = BuddyPresentation(
            profile_id=profile.profile_id,
            buddy_name=buddy_name,
            lifecycle_state=lifecycle_state,
            presence_state=presence_state,
            mood_state=mood_state,
            current_form=growth.evolution_stage,
            rarity=self._rarity_for_stage(growth.evolution_stage),
            current_goal_summary=target.final_goal if target is not None else profile.goal_intention,
            current_task_summary=current_task_summary,
            why_now_summary=why_now_summary,
            single_next_action_summary=single_next_action_summary,
            companion_strategy_summary=companion_strategy_summary,
        )
        return BuddySurfacePayload(
            profile=profile,
            growth_target=target,
            relationship=relationship,
            execution_carrier=execution_carrier,
            onboarding=onboarding,
            presentation=presentation,
            growth=growth,
        )

    def build_chat_surface(self, *, profile_id: str | None = None) -> BuddySurfacePayload:
        surface = self.build_optional_chat_surface(profile_id=profile_id)
        if surface is None:
            raise ValueError("伙伴档案暂不可用。")
        return surface

    def build_cockpit_summary(self, *, profile_id: str | None = None) -> dict[str, Any]:
        surface = self.build_chat_surface(profile_id=profile_id)
        return {
            "buddy_name": surface.presentation.buddy_name,
            "lifecycle_state": surface.presentation.lifecycle_state,
            "presence_state": surface.presentation.presence_state,
            "mood_state": surface.presentation.mood_state,
            "evolution_stage": surface.growth.evolution_stage,
            "growth_level": surface.growth.growth_level,
            "capability_score": surface.growth.capability_score,
            "capability_points": surface.growth.capability_points,
            "domain_id": surface.growth.domain_id,
            "domain_key": surface.growth.domain_key,
            "domain_label": surface.growth.domain_label,
            "settled_closure_count": surface.growth.settled_closure_count,
            "strategy_score": surface.growth.strategy_score,
            "execution_score": surface.growth.execution_score,
            "evidence_score": surface.growth.evidence_score,
            "stability_score": surface.growth.stability_score,
            "intimacy": surface.growth.intimacy,
            "affinity": surface.growth.affinity,
            "current_goal_summary": surface.presentation.current_goal_summary,
            "current_task_summary": surface.presentation.current_task_summary,
            "why_now_summary": surface.presentation.why_now_summary,
            "single_next_action_summary": surface.presentation.single_next_action_summary,
            "companion_strategy_summary": surface.presentation.companion_strategy_summary,
        }

    def _resolve_profile(self, profile_id: str | None) -> HumanProfile | None:
        if profile_id:
            return self._profile_repository.get_profile(profile_id)
        if self._profile_repository.count_profiles() > 1:
            raise ValueError("当前存在多个伙伴档案，请明确指定 profile_id。")
        return self._profile_repository.get_latest_profile()

    def _resolve_active_domain_capability(
        self,
        profile_id: str,
    ) -> BuddyDomainCapabilityRecord | None:
        if self._domain_capability_growth_service is not None:
            refreshed = self._domain_capability_growth_service.refresh_active_domain_capability(
                profile_id=profile_id,
            )
            if refreshed is not None:
                return refreshed
        if self._domain_capability_repository is None:
            return None
        return self._domain_capability_repository.get_active_domain_capability(profile_id)

    def _build_growth_projection(
        self,
        *,
        profile: HumanProfile,
        target: GrowthTarget | None,
        relationship: CompanionRelationship | None,
        active_domain: BuddyDomainCapabilityRecord | None,
        intimacy: int,
        affinity: int,
        pleasant_interaction_score: int,
        communication_count: int,
    ) -> BuddyGrowthProjection:
        companion_experience = (
            int(relationship.companion_experience) if relationship is not None else 0
        )
        if active_domain is None:
            domain_key = derive_buddy_domain_key(target.primary_direction) if target is not None else ""
            domain_label = self._present_domain_label(
                domain_key=domain_key,
                selected_direction=target.primary_direction if target is not None else "",
            )
            capability_score = 0
            capability_points = 0
            strategy_score = 0
            execution_score = 0
            evidence_score = 0
            stability_score = 0
            settled_closure_count = 0
            independent_outcome_count = 0
            recent_completion_rate = 0.0
            recent_execution_error_rate = 0.0
            distinct_settled_cycle_count = 0
            knowledge_value = 0
            skill_value = 0
            completed_support_runs = 0
            completed_assisted_closures = 0
            evolution_stage = "seed"
            domain_id = ""
        else:
            domain_id = active_domain.domain_id
            domain_key = active_domain.domain_key
            domain_label = active_domain.domain_label
            capability_score = int(active_domain.capability_score)
            capability_points = int(active_domain.capability_points)
            strategy_score = int(active_domain.strategy_score)
            execution_score = int(active_domain.execution_score)
            evidence_score = int(active_domain.evidence_score)
            stability_score = int(active_domain.stability_score)
            settled_closure_count = int(active_domain.settled_closure_count)
            independent_outcome_count = int(active_domain.independent_outcome_count)
            recent_completion_rate = float(active_domain.recent_completion_rate)
            recent_execution_error_rate = float(active_domain.recent_execution_error_rate)
            distinct_settled_cycle_count = int(active_domain.distinct_settled_cycle_count)
            knowledge_value = int(active_domain.knowledge_value)
            skill_value = int(active_domain.skill_value)
            completed_support_runs = int(active_domain.completed_support_runs)
            completed_assisted_closures = int(active_domain.completed_assisted_closures)
            evolution_stage = str(
                active_domain.evolution_stage
                or stage_from_points(capability_points)
                or capability_stage_from_score(capability_score)
            )
        growth_level = max(1, 1 + capability_points // 20)
        return BuddyGrowthProjection(
            profile_id=profile.profile_id,
            domain_id=domain_id,
            domain_key=domain_key,
            domain_label=domain_label,
            intimacy=intimacy,
            affinity=affinity,
            growth_level=growth_level,
            companion_experience=companion_experience,
            capability_score=capability_score,
            capability_points=capability_points,
            strategy_score=strategy_score,
            execution_score=execution_score,
            evidence_score=evidence_score,
            stability_score=stability_score,
            settled_closure_count=settled_closure_count,
            independent_outcome_count=independent_outcome_count,
            recent_completion_rate=recent_completion_rate,
            recent_execution_error_rate=recent_execution_error_rate,
            distinct_settled_cycle_count=distinct_settled_cycle_count,
            knowledge_value=knowledge_value,
            skill_value=skill_value,
            pleasant_interaction_score=pleasant_interaction_score,
            communication_count=communication_count,
            completed_support_runs=completed_support_runs,
            completed_assisted_closures=completed_assisted_closures,
            evolution_stage=evolution_stage,
            progress_to_next_stage=progress_to_next_stage(capability_points),
        )

    def _build_onboarding_projection(
        self,
        *,
        session: Any | None,
        target: GrowthTarget | None,
        relationship: CompanionRelationship | None,
        active_domain: BuddyDomainCapabilityRecord | None,
    ) -> BuddyOnboardingProjection:
        buddy_name = (
            str(getattr(relationship, "buddy_name", "") or "").strip()
            if relationship is not None
            else ""
        )
        status = str(getattr(session, "status", "") or "").strip() or "unborn"
        operation_id = str(getattr(session, "operation_id", "") or "").strip()
        operation_kind = str(getattr(session, "operation_kind", "") or "").strip()
        operation_status = str(getattr(session, "operation_status", "") or "").strip() or "idle"
        operation_error = str(getattr(session, "operation_error", "") or "").strip()
        activation_status = str(getattr(session, "activation_status", "") or "").strip() or "idle"
        activation_error = str(getattr(session, "activation_error", "") or "").strip()
        activation_attempt_count = int(getattr(session, "activation_attempt_count", 0) or 0)
        candidate_directions = list(getattr(session, "candidate_directions", []) or [])
        recommended_direction = str(getattr(session, "recommended_direction", "") or "").strip()
        selected_direction = str(getattr(session, "selected_direction", "") or "").strip()
        contract_source = relationship if relationship is not None and target is not None else session
        service_intent = str(getattr(contract_source, "service_intent", "") or "").strip()
        collaboration_role = (
            str(getattr(contract_source, "collaboration_role", "") or "").strip() or "orchestrator"
        )
        autonomy_level = (
            str(getattr(contract_source, "autonomy_level", "") or "").strip() or "proactive"
        )
        confirm_boundaries = [
            str(item).strip()
            for item in list(getattr(contract_source, "confirm_boundaries", []) or [])
            if str(item).strip()
        ]
        report_style = (
            str(getattr(contract_source, "report_style", "") or "").strip() or "result-first"
        )
        collaboration_notes = str(
            getattr(contract_source, "collaboration_notes", "") or ""
        ).strip()
        carrier_ready = bool(
            active_domain is not None
            and str(getattr(active_domain, "industry_instance_id", "") or "").strip()
        )
        if target is not None and not selected_direction:
            selected_direction = target.primary_direction
        if target is not None and not recommended_direction:
            recommended_direction = selected_direction
        if target is not None and carrier_ready and status in {"unborn", "contract-draft", "contract-ready"}:
            status = "confirmed"
        if buddy_name and carrier_ready and status in {"confirmed", "contract-ready", "contract-draft", "unborn"}:
            status = "named"
        requires_direction_confirmation = not carrier_ready and (
            target is None and (status == "contract-ready" or bool(candidate_directions))
        )
        requires_naming = carrier_ready and target is not None and not buddy_name
        completed = carrier_ready and target is not None and bool(buddy_name)
        return BuddyOnboardingProjection(
            session_id=str(getattr(session, "session_id", "") or "").strip() or None,
            status=status,
            operation_id=operation_id,
            operation_kind=operation_kind,
            operation_status=operation_status,
            operation_error=operation_error,
            activation_status=activation_status,
            activation_error=activation_error,
            activation_attempt_count=activation_attempt_count,
            candidate_directions=candidate_directions,
            recommended_direction=recommended_direction,
            selected_direction=selected_direction,
            service_intent=service_intent,
            collaboration_role=collaboration_role,
            autonomy_level=autonomy_level,
            confirm_boundaries=confirm_boundaries,
            report_style=report_style,
            collaboration_notes=collaboration_notes,
            requires_direction_confirmation=requires_direction_confirmation,
            requires_naming=requires_naming,
            completed=completed,
        )

    def _build_execution_carrier(
        self,
        *,
        profile: HumanProfile,
        growth_target: GrowthTarget | None,
        active_domain: BuddyDomainCapabilityRecord | None,
    ) -> dict[str, object] | None:
        if growth_target is None or active_domain is None:
            return None
        instance_id = str(getattr(active_domain, "industry_instance_id", "") or "").strip()
        if not instance_id:
            return None
        control_thread_id = str(getattr(active_domain, "control_thread_id", "") or "").strip()
        return build_buddy_execution_carrier_handoff(
            profile=profile,
            instance_id=instance_id,
            control_thread_id=control_thread_id or None,
            label=profile.display_name,
            current_cycle_id=growth_target.current_cycle_label or "Cycle 1",
            team_generated=False,
        )

    def _fallback_current_task_summary(self, profile_id: str) -> str:
        human_focus = resolve_active_human_assist_focus(
            profile_id,
            self._human_assist_task_service,
        )
        if human_focus is not None:
            return str(human_focus.get("current_task_summary") or "").strip()
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
        return ""

    def _fallback_why_now_summary(self, target: GrowthTarget | None) -> str:
        del target
        return ""

    def _fallback_single_next_action_summary(
        self,
        *,
        profile_id: str,
        current_task_summary: str,
    ) -> str:
        task_summary = str(current_task_summary or "").strip()
        if task_summary:
            return f"现在先完成这一步：{task_summary}"
        fallback = self._fallback_current_task_summary(profile_id)
        if not fallback:
            return ""
        return f"现在先完成这一步：{fallback}"

    def _build_companion_strategy_summary(
        self,
        *,
        relationship: CompanionRelationship | None,
    ) -> str:
        if relationship is None:
            return (
                "先像老朋友一样接住情绪，再把任务收成一个最小动作；"
                "默认只围绕最终目标、当前任务、为什么现在做和唯一下一步展开。"
            )
        style = self._present_encouragement_style(relationship.encouragement_style)
        parts = [f"先按“{style}”的方式接住情绪，再把对话收成一个最小动作。"]
        effective = [str(item).strip() for item in relationship.effective_reminders[:2] if str(item).strip()]
        ineffective = [str(item).strip() for item in relationship.ineffective_reminders[:2] if str(item).strip()]
        avoidance = [str(item).strip() for item in relationship.avoidance_patterns[:2] if str(item).strip()]
        if effective:
            parts.append("优先提醒：" + "、".join(effective))
        if ineffective:
            parts.append("避免：" + "、".join(ineffective))
        if avoidance:
            parts.append("如果出现" + "、".join(avoidance) + "，就立刻把任务缩成一个最小动作。")
        elif relationship.strong_pull_count > 0:
            parts.append("一旦明显拖延，就直接发起一次短陪跑，把任务缩成一个最小动作。")
        return "".join(parts)

    def _present_encouragement_style(self, style: str | None) -> str:
        normalized = str(style or "").strip().lower()
        if normalized == "old-friend":
            return "老朋友式陪跑"
        if normalized == "steady-coach":
            return "稳住节奏的教练式提醒"
        if normalized == "gentle-push":
            return "温柔但坚定的推进"
        return "陪你一起往前走"

    def _present_domain_label(self, *, domain_key: str, selected_direction: str) -> str:
        normalized_direction = str(selected_direction or "").strip()
        if normalized_direction:
            return normalized_direction
        normalized_domain = str(domain_key or "").strip().replace("-", " ")
        return normalized_domain or "unscoped domain"

    def _rarity_for_stage(self, stage: str) -> str:
        mapping = {
            "seed": "common",
            "bonded": "uncommon",
            "capable": "rare",
            "seasoned": "epic",
            "signature": "signature",
        }
        return mapping.get(stage, "common")


__all__ = [
    "BuddyOnboardingProjection",
    "BuddyProjectionService",
    "BuddySurfacePayload",
]
