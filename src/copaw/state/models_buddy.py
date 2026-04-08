# -*- coding: utf-8 -*-
"""Human-facing Buddy truth and projection models."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from .model_support import UpdatedRecord, _new_record_id, _normalize_text_list

BuddyLifecycleState = Literal[
    "unborn",
    "born-unnamed",
    "named",
    "bonded",
    "evolving",
]
BuddyPresenceState = Literal[
    "idle",
    "attentive",
    "focused",
    "supporting",
    "pulling-back",
    "celebrating",
    "resting",
]
BuddyMoodState = Literal[
    "calm",
    "warm",
    "concerned",
    "playful",
    "proud",
    "determined",
]
BuddyEvolutionStage = Literal[
    "seed",
    "bonded",
    "capable",
    "seasoned",
    "signature",
]
BuddyRarity = Literal["common", "uncommon", "rare", "epic", "signature"]
BuddyDomainCapabilityStatus = Literal["active", "archived"]


class HumanProfile(UpdatedRecord):
    """Canonical human identity/profile truth for Buddy onboarding."""

    profile_id: str = Field(default_factory=_new_record_id, min_length=1)
    display_name: str = Field(..., min_length=1)
    profession: str = Field(..., min_length=1)
    current_stage: str = Field(..., min_length=1)
    interests: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    goal_intention: str = Field(..., min_length=1)

    @field_validator("interests", "strengths", "constraints", mode="before")
    @classmethod
    def _normalize_list_fields(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class GrowthTarget(UpdatedRecord):
    """Confirmed human-facing growth target truth."""

    target_id: str = Field(default_factory=_new_record_id, min_length=1)
    profile_id: str = Field(..., min_length=1)
    primary_direction: str = Field(..., min_length=1)
    final_goal: str = Field(..., min_length=1)
    why_it_matters: str = Field(..., min_length=1)
    current_cycle_label: str = ""


class CompanionRelationship(UpdatedRecord):
    """Stable Buddy relationship preferences and learned support patterns."""

    relationship_id: str = Field(default_factory=_new_record_id, min_length=1)
    profile_id: str = Field(..., min_length=1)
    buddy_name: str = ""
    encouragement_style: str = Field(default="old-friend", min_length=1)
    effective_reminders: list[str] = Field(default_factory=list)
    ineffective_reminders: list[str] = Field(default_factory=list)
    avoidance_patterns: list[str] = Field(default_factory=list)
    communication_count: int = Field(default=0, ge=0)
    pleasant_interaction_score: int = Field(default=0, ge=0)
    companion_experience: int = Field(default=0, ge=0)
    strong_pull_count: int = Field(default=0, ge=0)
    last_interaction_at: str | None = None

    @field_validator(
        "effective_reminders",
        "ineffective_reminders",
        "avoidance_patterns",
        mode="before",
    )
    @classmethod
    def _normalize_list_fields(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class BuddyDomainCapabilityRecord(UpdatedRecord):
    """Persisted Buddy capability progress for one domain/direction."""

    domain_id: str = Field(default_factory=_new_record_id, min_length=1)
    profile_id: str = Field(..., min_length=1)
    domain_key: str = Field(..., min_length=1)
    domain_label: str = Field(..., min_length=1)
    status: BuddyDomainCapabilityStatus = "active"
    industry_instance_id: str = ""
    control_thread_id: str = ""
    domain_scope_summary: str = ""
    domain_scope_tags: list[str] = Field(default_factory=list)
    strategy_score: int = Field(default=0, ge=0, le=25)
    execution_score: int = Field(default=0, ge=0, le=35)
    evidence_score: int = Field(default=0, ge=0, le=20)
    stability_score: int = Field(default=0, ge=0, le=20)
    capability_score: int = Field(default=0, ge=0, le=100)
    capability_points: int = Field(default=0, ge=0)
    settled_closure_count: int = Field(default=0, ge=0)
    independent_outcome_count: int = Field(default=0, ge=0)
    recent_completion_rate: float = Field(default=0, ge=0, le=1)
    recent_execution_error_rate: float = Field(default=0, ge=0, le=1)
    distinct_settled_cycle_count: int = Field(default=0, ge=0)
    demotion_cooldown_until: str | None = None
    evolution_stage: BuddyEvolutionStage = "seed"
    knowledge_value: int = Field(default=0, ge=0)
    skill_value: int = Field(default=0, ge=0)
    completed_support_runs: int = Field(default=0, ge=0)
    completed_assisted_closures: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    report_count: int = Field(default=0, ge=0)
    last_activated_at: str | None = None
    last_progress_at: str | None = None

    @field_validator("domain_scope_tags", mode="before")
    @classmethod
    def _normalize_domain_scope_tags(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class BuddyPresentation(UpdatedRecord):
    """Derived Buddy presentation payload for chat/cockpit surfaces."""

    profile_id: str = Field(..., min_length=1)
    buddy_name: str = Field(..., min_length=1)
    lifecycle_state: BuddyLifecycleState = "born-unnamed"
    presence_state: BuddyPresenceState = "idle"
    mood_state: BuddyMoodState = "calm"
    current_form: BuddyEvolutionStage = "seed"
    rarity: BuddyRarity = "common"
    current_goal_summary: str = ""
    current_task_summary: str = ""
    why_now_summary: str = ""
    single_next_action_summary: str = ""
    companion_strategy_summary: str = ""


class BuddyGrowthProjection(UpdatedRecord):
    """Derived game-like Buddy growth surface."""

    profile_id: str = Field(..., min_length=1)
    domain_id: str = ""
    domain_key: str = ""
    domain_label: str = ""
    intimacy: int = Field(default=0, ge=0)
    affinity: int = Field(default=0, ge=0)
    growth_level: int = Field(default=1, ge=1)
    companion_experience: int = Field(default=0, ge=0)
    capability_score: int = Field(default=0, ge=0, le=100)
    capability_points: int = Field(default=0, ge=0)
    strategy_score: int = Field(default=0, ge=0)
    execution_score: int = Field(default=0, ge=0)
    evidence_score: int = Field(default=0, ge=0)
    stability_score: int = Field(default=0, ge=0)
    settled_closure_count: int = Field(default=0, ge=0)
    independent_outcome_count: int = Field(default=0, ge=0)
    recent_completion_rate: float = Field(default=0, ge=0, le=1)
    recent_execution_error_rate: float = Field(default=0, ge=0, le=1)
    distinct_settled_cycle_count: int = Field(default=0, ge=0)
    knowledge_value: int = Field(default=0, ge=0)
    skill_value: int = Field(default=0, ge=0)
    pleasant_interaction_score: int = Field(default=0, ge=0)
    communication_count: int = Field(default=0, ge=0)
    completed_support_runs: int = Field(default=0, ge=0)
    completed_assisted_closures: int = Field(default=0, ge=0)
    evolution_stage: BuddyEvolutionStage = "seed"
    progress_to_next_stage: int = Field(default=0, ge=0, le=100)


__all__ = [
    "BuddyDomainCapabilityRecord",
    "BuddyDomainCapabilityStatus",
    "BuddyEvolutionStage",
    "BuddyGrowthProjection",
    "BuddyLifecycleState",
    "BuddyMoodState",
    "BuddyPresentation",
    "BuddyPresenceState",
    "BuddyRarity",
    "CompanionRelationship",
    "GrowthTarget",
    "HumanProfile",
]
