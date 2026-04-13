# -*- coding: utf-8 -*-
"""Buddy-first onboarding service built on top of existing main-brain truth."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import unicodedata
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ..app.crons.models import CronJobSpec
from ..industry import compile_industry_schedule_seeds
from .buddy_execution_carrier import (
    EXECUTION_CORE_ROLE_ID,
    build_buddy_domain_control_thread_id,
    build_buddy_domain_instance_id,
    build_buddy_execution_carrier_handoff,
)
from .buddy_onboarding_reasoner import (
    BuddyOnboardingBacklogSeed,
    BuddyCollaborationContract,
    BuddyOnboardingContractCompileResult,
    BuddyOnboardingReasoner,
    BuddyOnboardingReasonerUnavailableError,
    BuddyOnboardingReasonerTimeoutError,
)
from .buddy_domain_capability_growth import BuddyDomainCapabilityGrowthService
from .buddy_domain_capability import (
    buddy_specialist_allowed_capabilities,
    buddy_specialist_preferred_capability_families,
    derive_buddy_domain_key,
    preview_domain_transition,
)
from ..industry.identity import EXECUTION_CORE_AGENT_ID
from ..industry.models import (
    IndustryDraftPlan,
    IndustryDraftSchedule,
    IndustryProfile,
    IndustryRoleBlueprint,
    IndustryTeamBlueprint,
)
from ..state import (
    BuddyDomainCapabilityRecord,
    CompanionRelationship,
    GrowthTarget,
    HumanProfile,
    ScheduleRecord,
)
from ..state.main_brain_service import (
    AssignmentService,
    BacklogService,
    OperatingCycleService,
    OperatingLaneService,
)
from ..state.models import IndustryInstanceRecord
from ..state.repositories import (
    SqliteIndustryInstanceRepository,
    SqliteScheduleRepository,
)
from ..state.repositories_buddy import (
    BuddyOnboardingSessionRecord,
    SqliteBuddyDomainCapabilityRepository,
    SqliteBuddyOnboardingSessionRepository,
    SqliteCompanionRelationshipRepository,
    SqliteGrowthTargetRepository,
    SqliteHumanProfileRepository,
)

logger = logging.getLogger(__name__)


class BuddyIdentitySubmitResult(BaseModel):
    session_id: str
    profile: HumanProfile
    status: str = "contract-draft"


class BuddyContractCompileSubmitResult(BaseModel):
    session_id: str
    status: str = "contract-ready"
    service_intent: str = ""
    collaboration_role: str = "orchestrator"
    autonomy_level: str = "proactive"
    confirm_boundaries: list[str] = Field(default_factory=list)
    report_style: str = "result-first"
    collaboration_notes: str = ""
    candidate_directions: list[str] = Field(default_factory=list)
    recommended_direction: str = ""
    final_goal: str = ""
    why_it_matters: str = ""
    backlog_items: list[BuddyOnboardingBacklogSeed] = Field(default_factory=list)


class BuddyDirectionTransitionPreviewResult(BaseModel):
    session_id: str
    selected_direction: str
    selected_domain_key: str
    suggestion_kind: str
    recommended_action: str
    reason_summary: str
    current_domain: dict[str, object] | None = None
    archived_matches: list[dict[str, object]] = Field(default_factory=list)


class BuddyOnboardingOperationHandle(BaseModel):
    session_id: str
    profile_id: str
    operation_id: str
    operation_kind: str
    operation_status: str = "running"


@dataclass(slots=True)
class BuddyDirectionConfirmationResult:
    session: BuddyOnboardingSessionRecord
    growth_target: GrowthTarget
    relationship: CompanionRelationship
    domain_capability: BuddyDomainCapabilityRecord
    execution_carrier: dict[str, object] | None = None
    schedule_specs: list[dict[str, object]] | None = None


class BuddyActivationRepairTarget(BaseModel):
    session_id: str
    profile_id: str
    industry_instance_id: str
    activation_id: str | None = None


_DEFAULT_DIRECTION = "建立稳定、自主、长期向上的人生主方向"
_STOCKS_DIRECTION = "建立稳定、可验证的股票交易与投资成长路径"
_CREATOR_DIRECTION = "建立独立创作与内容事业的长期成长路径"
_DESIGN_DIRECTION = "建立高杠杆的设计与系统领导力成长路径"
_OPERATIONS_DIRECTION = "建立从执行型走向策略型的长期职业跃迁路径"
_HEALTH_DIRECTION = "建立自律、健康与自我掌控的人生重建路径"

_BUDDY_LANE_LABEL_MAP: dict[str, str] = {
    "growth-focus": "成长推进执行位",
    "proof-of-work": "成果验证执行位",
    "proof-work": "成果验证执行位",
    "browser-work": "浏览器执行位",
    "browser": "浏览器执行位",
    "research": "调研执行位",
    "planning": "规划执行位",
    "strategy": "策略执行位",
    "operations": "运营执行位",
    "ops": "运营执行位",
    "design": "设计执行位",
    "writing": "写作执行位",
    "publishing": "发布执行位",
    "content": "内容执行位",
    "analysis": "分析执行位",
    "trading": "交易执行位",
    "review": "复盘执行位",
}


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


def _normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return text.lower().strip()


def _new_buddy_operation_id() -> str:
    return str(uuid4())


def _normalize_buddy_lane_hint(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    if not normalized:
        return ""
    parts: list[str] = []
    current: list[str] = []
    for char in normalized:
        if char.isalnum():
            current.append(char)
            continue
        if current:
            parts.append("".join(current))
            current = []
    if current:
        parts.append("".join(current))
    return "-".join(part for part in parts if part).strip("-")


def _present_buddy_lane_label(role_id: str) -> str:
    normalized = _normalize_buddy_lane_hint(role_id)
    if not normalized:
        return "专项执行位"
    if normalized in _BUDDY_LANE_LABEL_MAP:
        return _BUDDY_LANE_LABEL_MAP[normalized]
    translated_parts = [
        _BUDDY_LANE_LABEL_MAP.get(part)
        for part in normalized.split("-")
        if part
    ]
    translated_parts = [part for part in translated_parts if part]
    if translated_parts:
        joined = "".join(translated_parts)
        if joined.endswith("执行位"):
            return joined
        return f"{joined}执行位"
    if all(part.isascii() for part in normalized.split("-") if part):
        return "专项执行位"
    return normalized


def _resolve_growth_plan_lane_hints(
    growth_plan: BuddyOnboardingContractCompileResult | None,
) -> list[str]:
    if growth_plan is None:
        return []
    lane_hints = [
        _normalize_buddy_lane_hint(item.lane_hint)
        for item in (growth_plan.backlog_items or [])
    ]
    return _unique([hint for hint in lane_hints if hint])


def _contains_any(source: str, tokens: tuple[str, ...]) -> bool:
    return any(token in source for token in tokens)


_STRONG_PULL_INTERACTION_MODES = ("strong-pull", "strong_pull")
_GROWTH_CHECKPOINT_INTERACTION_MODES = (
    "checkpoint",
    "runtime-outcome",
    "runtime_outcome",
    "human-assist-checkpoint",
    "human_assist_checkpoint",
    "human-assist-resume",
    "human_assist_resume",
    "closure",
)
_STRONG_PULL_MESSAGE_TOKENS = (
    "卡住",
    "卡住了",
    "拖延",
    "拖着",
    "逃避",
    "不想做",
    "不想动",
    "不想继续",
    "做不下去",
    "坚持不下去",
    "刷手机",
    "刷短视频",
    "stuck",
    "avoiding",
    "avoid this",
    "avoid it",
    "procrastinat",
    "don't want to do",
    "dont want to do",
    "don't want to",
    "dont want to",
    "can't start",
    "cannot start",
    "can't do it",
    "can’t do it",
    "stalled",
)


def _is_strong_pull_interaction(
    *,
    interaction_mode: str | None,
    normalized_message: str,
) -> bool:
    normalized_mode = _normalize_text(interaction_mode)
    if normalized_mode in _STRONG_PULL_INTERACTION_MODES:
        return True
    return _contains_any(normalized_message, _STRONG_PULL_MESSAGE_TOKENS)


def _is_growth_checkpoint_interaction(interaction_mode: str | None) -> bool:
    normalized_mode = _normalize_text(interaction_mode)
    if not normalized_mode:
        return False
    if normalized_mode in _GROWTH_CHECKPOINT_INTERACTION_MODES:
        return True
    return normalized_mode.startswith("checkpoint:")


def _build_buddy_industry_profile(
    *,
    profile: HumanProfile,
    growth_target: GrowthTarget,
) -> IndustryProfile:
    context_bits = _unique(
        [
            f"human_display_name={profile.display_name}",
            f"current_profession={profile.profession}",
            f"current_stage={profile.current_stage}",
            f"goal_intention={profile.goal_intention}",
        ]
    )
    return IndustryProfile(
        industry=growth_target.primary_direction,
        goals=[growth_target.final_goal],
        constraints=list(profile.constraints),
        notes=" | ".join(context_bits),
    )


class BuddyOnboardingService:
    MAX_QUESTIONS = 9
    TIGHTEN_AFTER = 5
    EXECUTION_CORE_ROLE_ID = EXECUTION_CORE_ROLE_ID

    def __init__(
        self,
        *,
        profile_repository: SqliteHumanProfileRepository,
        growth_target_repository: SqliteGrowthTargetRepository,
        relationship_repository: SqliteCompanionRelationshipRepository,
        domain_capability_repository: SqliteBuddyDomainCapabilityRepository | None = None,
        onboarding_session_repository: SqliteBuddyOnboardingSessionRepository,
        industry_instance_repository: SqliteIndustryInstanceRepository | None = None,
        operating_lane_service: OperatingLaneService | None = None,
        backlog_service: BacklogService | None = None,
        operating_cycle_service: OperatingCycleService | None = None,
        assignment_service: AssignmentService | None = None,
        schedule_repository: SqliteScheduleRepository | None = None,
        domain_capability_growth_service: BuddyDomainCapabilityGrowthService | None = None,
        onboarding_reasoner: BuddyOnboardingReasoner | None = None,
    ) -> None:
        self._profile_repository = profile_repository
        self._growth_target_repository = growth_target_repository
        self._relationship_repository = relationship_repository
        self._domain_capability_repository = domain_capability_repository
        self._onboarding_session_repository = onboarding_session_repository
        self._industry_instance_repository = industry_instance_repository
        self._operating_lane_service = operating_lane_service
        self._backlog_service = backlog_service
        self._operating_cycle_service = operating_cycle_service
        self._assignment_service = assignment_service
        self._schedule_repository = schedule_repository
        self._domain_capability_growth_service = domain_capability_growth_service
        self._onboarding_reasoner = onboarding_reasoner

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
        existing_profile = self._profile_repository.find_latest_profile_by_identity_signature(
            display_name=display_name,
            profession=profession,
            current_stage=current_stage,
        )
        return self._store_identity_submission(
            display_name=display_name,
            profession=profession,
            current_stage=current_stage,
            interests=interests,
            strengths=strengths,
            constraints=constraints,
            goal_intention=goal_intention,
            existing_profile=existing_profile,
        )

    def start_identity_operation(
        self,
        *,
        display_name: str,
        profession: str,
        current_stage: str,
        interests: list[str] | None = None,
        strengths: list[str] | None = None,
        constraints: list[str] | None = None,
        goal_intention: str,
    ) -> BuddyOnboardingOperationHandle:
        existing_profile = self._profile_repository.find_latest_profile_by_identity_signature(
            display_name=display_name,
            profession=profession,
            current_stage=current_stage,
        )
        profile = HumanProfile(
            display_name=display_name,
            profession=profession,
            current_stage=current_stage,
            interests=interests or [],
            strengths=strengths or [],
            constraints=constraints or [],
            goal_intention=goal_intention,
        )
        if existing_profile is not None:
            profile = profile.model_copy(
                update={
                    "profile_id": existing_profile.profile_id,
                    "created_at": existing_profile.created_at,
                    "updated_at": _utc_now(),
                },
            )
        profile = self._profile_repository.upsert_profile(profile)
        operation_id = _new_buddy_operation_id()
        session = self._build_contract_draft_session(
            profile=profile,
            existing_session=None,
            operation_id=operation_id,
            operation_kind="identity",
            operation_status="running",
            operation_error="",
        )
        session = self._onboarding_session_repository.upsert_session(session)
        return BuddyOnboardingOperationHandle(
            session_id=session.session_id,
            profile_id=profile.profile_id,
            operation_id=operation_id,
            operation_kind="identity",
        )

    def complete_identity_operation(
        self,
        *,
        session_id: str,
        profile_id: str,
        display_name: str,
        profession: str,
        current_stage: str,
        interests: list[str] | None = None,
        strengths: list[str] | None = None,
        constraints: list[str] | None = None,
        goal_intention: str,
    ) -> BuddyIdentitySubmitResult:
        existing_profile = self._profile_repository.get_profile(profile_id)
        if existing_profile is None:
            raise ValueError(f"未找到该档案：{profile_id}")
        existing_session = self._require_session(session_id)
        if existing_session.profile_id != profile_id:
            raise ValueError("伙伴建档会话与档案不匹配。")
        return self._store_identity_submission(
            display_name=display_name,
            profession=profession,
            current_stage=current_stage,
            interests=interests,
            strengths=strengths,
            constraints=constraints,
            goal_intention=goal_intention,
            existing_profile=existing_profile,
            existing_session=existing_session,
        )

    def submit_contract(
        self,
        *,
        session_id: str,
        service_intent: str,
        collaboration_role: str = "orchestrator",
        autonomy_level: str = "proactive",
        confirm_boundaries: list[str] | None = None,
        report_style: str = "result-first",
        collaboration_notes: str = "",
    ) -> BuddyContractCompileSubmitResult:
        session = self._require_session(session_id)
        profile = self._require_profile(session.profile_id)
        collaboration_contract = BuddyCollaborationContract(
            service_intent=service_intent,
            collaboration_role=collaboration_role,
            autonomy_level=autonomy_level,
            confirm_boundaries=confirm_boundaries or [],
            report_style=report_style,
            collaboration_notes=collaboration_notes,
        )
        try:
            compiled_contract = self._resolve_contract_compile(
                profile=profile,
                collaboration_contract=collaboration_contract,
            )
        except (
            BuddyOnboardingReasonerTimeoutError,
            TimeoutError,
            BuddyOnboardingReasonerUnavailableError,
        ):
            raise
        updated = self._onboarding_session_repository.upsert_session(
            session.model_copy(
                update={
                    "status": "contract-ready",
                    **self._clear_operation_state(),
                    "service_intent": collaboration_contract.service_intent,
                    "collaboration_role": collaboration_contract.collaboration_role,
                    "autonomy_level": collaboration_contract.autonomy_level,
                    "confirm_boundaries": list(collaboration_contract.confirm_boundaries),
                    "report_style": collaboration_contract.report_style,
                    "collaboration_notes": collaboration_contract.collaboration_notes,
                    "candidate_directions": list(compiled_contract.candidate_directions),
                    "recommended_direction": compiled_contract.recommended_direction,
                    **self._build_contract_compile_cache(compiled_contract),
                },
            ),
        )
        return BuddyContractCompileSubmitResult(
            session_id=updated.session_id,
            status=updated.status,
            service_intent=updated.service_intent,
            collaboration_role=updated.collaboration_role,
            autonomy_level=updated.autonomy_level,
            confirm_boundaries=list(updated.confirm_boundaries),
            report_style=updated.report_style,
            collaboration_notes=updated.collaboration_notes,
            candidate_directions=updated.candidate_directions,
            recommended_direction=updated.recommended_direction,
            final_goal=updated.draft_final_goal,
            why_it_matters=updated.draft_why_it_matters,
            backlog_items=[
                BuddyOnboardingBacklogSeed.model_validate(item)
                for item in list(updated.draft_backlog_items or [])
                if isinstance(item, dict)
            ],
        )

    def start_contract_compile(
        self,
        *,
        session_id: str,
    ) -> BuddyOnboardingOperationHandle:
        session = self._require_session(session_id)
        if session.operation_status == "running":
            raise ValueError("伙伴建档正在处理中，请稍后再试。")
        operation_id = _new_buddy_operation_id()
        updated = self._onboarding_session_repository.upsert_session(
            session.model_copy(
                update={
                    "operation_id": operation_id,
                    "operation_kind": "contract",
                    "operation_status": "running",
                    "operation_error": "",
                    "updated_at": _utc_now(),
                },
            ),
        )
        return BuddyOnboardingOperationHandle(
            session_id=updated.session_id,
            profile_id=updated.profile_id,
            operation_id=operation_id,
            operation_kind="contract",
        )

    def get_candidate_directions(self, *, session_id: str) -> BuddyContractCompileSubmitResult:
        session = self._require_session(session_id)
        return BuddyContractCompileSubmitResult(
            session_id=session.session_id,
            status=session.status,
            service_intent=session.service_intent,
            collaboration_role=session.collaboration_role,
            autonomy_level=session.autonomy_level,
            confirm_boundaries=list(session.confirm_boundaries),
            report_style=session.report_style,
            collaboration_notes=session.collaboration_notes,
            candidate_directions=session.candidate_directions,
            recommended_direction=session.recommended_direction,
            final_goal=session.draft_final_goal,
            why_it_matters=session.draft_why_it_matters,
            backlog_items=[
                BuddyOnboardingBacklogSeed.model_validate(item)
                for item in list(session.draft_backlog_items or [])
                if isinstance(item, dict)
            ],
        )

    def preview_primary_direction_transition(
        self,
        *,
        session_id: str,
        selected_direction: str,
    ) -> BuddyDirectionTransitionPreviewResult:
        session = self._require_session(session_id)
        profile = self._require_profile(session.profile_id)
        normalized = self._validate_selected_direction(
            session=session,
            selected_direction=selected_direction,
        )
        active_record = None
        archived_records: list[BuddyDomainCapabilityRecord] = []
        if self._domain_capability_repository is not None:
            active_record = self._domain_capability_repository.get_active_domain_capability(
                profile.profile_id,
            )
            archived_records = [
                record
                for record in self._domain_capability_repository.list_domain_capabilities(
                    profile.profile_id,
                )
                if record.status == "archived"
            ]
        preview = preview_domain_transition(
            selected_direction=normalized,
            active_record=active_record,
            archived_records=archived_records,
        )
        return BuddyDirectionTransitionPreviewResult(
            session_id=session.session_id,
            selected_direction=normalized,
            selected_domain_key=preview.selected_domain_key,
            suggestion_kind=preview.suggestion_kind,
            recommended_action=preview.recommended_action,
            reason_summary=preview.reason_summary,
            current_domain=preview.current_domain,
            archived_matches=preview.archived_matches or [],
        )

    def confirm_primary_direction(
        self,
        *,
        session_id: str,
        selected_direction: str,
        capability_action: str | None = None,
        target_domain_id: str | None = None,
    ) -> BuddyDirectionConfirmationResult:
        session = self._require_session(session_id)
        profile = self._require_profile(session.profile_id)
        normalized = self._validate_selected_direction(
            session=session,
            selected_direction=selected_direction,
        )
        preview = self.preview_primary_direction_transition(
            session_id=session_id,
            selected_direction=normalized,
        )
        compiled_contract = self._require_confirmable_contract_compile(
            session=session,
            selected_direction=normalized,
        )
        resolved_capability_action = str(
            capability_action or preview.recommended_action or "",
        ).strip()
        if resolved_capability_action not in {
            "keep-active",
            "restore-archived",
            "start-new",
        }:
            raise ValueError("请选择方向切换后的能力处理方式。")
        growth_target = self._growth_target_repository.upsert_target(
            GrowthTarget(
                profile_id=profile.profile_id,
                primary_direction=normalized,
                final_goal=compiled_contract.final_goal,
                why_it_matters=compiled_contract.why_it_matters,
                current_cycle_label="Cycle 1",
            ),
        )
        existing_relationship = self._relationship_repository.get_relationship(profile.profile_id)
        relationship = self._relationship_repository.upsert_relationship(
            (existing_relationship or CompanionRelationship(profile_id=profile.profile_id)).model_copy(
                update={
                    "profile_id": profile.profile_id,
                    "service_intent": session.service_intent,
                    "collaboration_role": session.collaboration_role,
                    "autonomy_level": session.autonomy_level,
                    "confirm_boundaries": list(session.confirm_boundaries),
                    "report_style": session.report_style,
                    "collaboration_notes": session.collaboration_notes,
                    "encouragement_style": "old-friend",
                    "effective_reminders": _unique(
                        list((existing_relationship.effective_reminders if existing_relationship else []) or [])
                        + ["先把任务缩成一个最小动作", "先把今天这一小步做完"]
                    )[:3],
                    "ineffective_reminders": _unique(
                        list((existing_relationship.ineffective_reminders if existing_relationship else []) or [])
                        + ["高压催促", "空泛说教"]
                    )[:3],
                    "avoidance_patterns": self._seed_avoidance_patterns(
                        profile=profile,
                        signals=[
                            session.service_intent,
                            session.collaboration_notes,
                            *list(session.confirm_boundaries or []),
                        ],
                        existing=existing_relationship.avoidance_patterns if existing_relationship else None,
                    )[:3],
                },
            ),
        )
        domain_capability = self._activate_domain_capability(
            profile=profile,
            selected_direction=normalized,
            capability_action=resolved_capability_action,
            target_domain_id=target_domain_id,
            preview=preview,
        )
        growth_target, domain_capability, execution_carrier, schedule_specs = self._ensure_growth_scaffold(
            profile=profile,
            growth_target=growth_target,
            domain_capability=domain_capability,
            capability_action=resolved_capability_action,
            growth_plan=compiled_contract,
        )
        if self._domain_capability_growth_service is not None:
            refreshed = self._domain_capability_growth_service.refresh_active_domain_capability(
                profile_id=profile.profile_id,
            )
            if refreshed is not None:
                domain_capability = refreshed
        updated_session = self._onboarding_session_repository.upsert_session(
            session.model_copy(
                update={
                    "status": "confirmed",
                    **self._clear_operation_state(),
                    "selected_direction": normalized,
                    "recommended_direction": session.recommended_direction or normalized,
                    **self._build_contract_compile_cache(compiled_contract),
                },
            ),
        )
        return BuddyDirectionConfirmationResult(
            session=updated_session,
            growth_target=growth_target,
            relationship=relationship,
            domain_capability=domain_capability,
            execution_carrier=execution_carrier,
            schedule_specs=schedule_specs,
        )

    def start_confirm_direction_operation(
        self,
        *,
        session_id: str,
    ) -> BuddyOnboardingOperationHandle:
        session = self._require_session(session_id)
        if session.operation_status == "running":
            raise ValueError("伙伴建档正在处理中，请稍后再试。")
        operation_id = _new_buddy_operation_id()
        updated = self._onboarding_session_repository.upsert_session(
            session.model_copy(
                update={
                    "operation_id": operation_id,
                    "operation_kind": "confirm",
                    "operation_status": "running",
                    "operation_error": "",
                    "updated_at": _utc_now(),
                },
            ),
        )
        return BuddyOnboardingOperationHandle(
            session_id=updated.session_id,
            profile_id=updated.profile_id,
            operation_id=operation_id,
            operation_kind="confirm",
        )

    def mark_operation_succeeded(
        self,
        *,
        session_id: str,
        operation_id: str,
        operation_kind: str,
    ) -> BuddyOnboardingSessionRecord:
        session = self._require_session(session_id)
        updated = session.model_copy(
            update={
                "operation_id": operation_id,
                "operation_kind": operation_kind,
                "operation_status": "succeeded",
                "operation_error": "",
                "updated_at": _utc_now(),
            },
        )
        return self._onboarding_session_repository.upsert_session(updated)

    def mark_operation_failed(
        self,
        *,
        session_id: str,
        operation_id: str,
        operation_kind: str,
        error_message: str,
    ) -> BuddyOnboardingSessionRecord:
        session = self._require_session(session_id)
        updated = session.model_copy(
            update={
                "operation_id": operation_id,
                "operation_kind": operation_kind,
                "operation_status": "failed",
                "operation_error": str(error_message or "").strip(),
                "updated_at": _utc_now(),
            },
        )
        return self._onboarding_session_repository.upsert_session(updated)

    def queue_activation(
        self,
        *,
        session_id: str,
    ) -> BuddyOnboardingSessionRecord:
        session = self._require_session(session_id)
        activation_id = _new_buddy_operation_id()
        updated = session.model_copy(
            update={
                "activation_id": activation_id,
                "activation_status": "queued",
                "activation_error": "",
                "activation_attempt_count": int(session.activation_attempt_count or 0) + 1,
                "updated_at": _utc_now(),
            },
        )
        return self._onboarding_session_repository.upsert_session(updated)

    def mark_activation_started(
        self,
        *,
        session_id: str,
        activation_id: str,
    ) -> BuddyOnboardingSessionRecord:
        session = self._require_session(session_id)
        if str(session.activation_id or "").strip() != str(activation_id or "").strip():
            return session
        updated = session.model_copy(
            update={
                "activation_status": "running",
                "activation_error": "",
                "updated_at": _utc_now(),
            },
        )
        return self._onboarding_session_repository.upsert_session(updated)

    def mark_activation_succeeded(
        self,
        *,
        session_id: str,
        activation_id: str,
    ) -> BuddyOnboardingSessionRecord:
        session = self._require_session(session_id)
        if str(session.activation_id or "").strip() != str(activation_id or "").strip():
            return session
        updated = session.model_copy(
            update={
                "activation_status": "succeeded",
                "activation_error": "",
                "updated_at": _utc_now(),
            },
        )
        return self._onboarding_session_repository.upsert_session(updated)

    def mark_activation_deferred(
        self,
        *,
        session_id: str,
        activation_id: str,
        error_message: str,
    ) -> BuddyOnboardingSessionRecord:
        session = self._require_session(session_id)
        if str(session.activation_id or "").strip() != str(activation_id or "").strip():
            return session
        updated = session.model_copy(
            update={
                "activation_status": "deferred",
                "activation_error": str(error_message or "").strip(),
                "updated_at": _utc_now(),
            },
        )
        return self._onboarding_session_repository.upsert_session(updated)

    def mark_activation_failed(
        self,
        *,
        session_id: str,
        activation_id: str,
        error_message: str,
    ) -> BuddyOnboardingSessionRecord:
        session = self._require_session(session_id)
        if str(session.activation_id or "").strip() != str(activation_id or "").strip():
            return session
        updated = session.model_copy(
            update={
                "activation_status": "failed",
                "activation_error": str(error_message or "").strip(),
                "updated_at": _utc_now(),
            },
        )
        return self._onboarding_session_repository.upsert_session(updated)

    def complete_activation_from_result(
        self,
        *,
        session_id: str,
        activation_id: str,
        result: Any,
    ) -> BuddyOnboardingSessionRecord:
        summary = dict(result) if isinstance(result, dict) else {}
        activated = bool(summary.get("activated"))
        started_assignment_ids = [
            str(item).strip()
            for item in list(summary.get("started_assignment_ids") or [])
            if str(item).strip()
        ]
        assignment_dispatches = [
            item
            for item in list(summary.get("assignment_dispatches") or [])
            if isinstance(item, dict)
        ]
        blocked_reason = str(summary.get("blocked_reason") or "").strip()
        if activated or started_assignment_ids or assignment_dispatches:
            return self.mark_activation_succeeded(
                session_id=session_id,
                activation_id=activation_id,
            )
        if blocked_reason:
            return self.mark_activation_deferred(
                session_id=session_id,
                activation_id=activation_id,
                error_message=blocked_reason,
            )
        return self.mark_activation_failed(
            session_id=session_id,
            activation_id=activation_id,
            error_message="伙伴激活未确认正式派工已成功启动。",
        )

    def repair_failed_activation(
        self,
        *,
        profile_id: str,
    ) -> BuddyActivationRepairTarget | None:
        if self._domain_capability_repository is None:
            return None
        session = self._onboarding_session_repository.get_latest_session_for_profile(profile_id)
        if session is None:
            return None
        if str(session.activation_status or "").strip().lower() != "failed":
            return None
        if int(session.activation_attempt_count or 0) >= 3:
            return None
        growth_target = self._growth_target_repository.get_active_target(profile_id)
        if growth_target is None:
            return None
        active_domain = self._domain_capability_repository.get_active_domain_capability(profile_id)
        instance_id = str(getattr(active_domain, "industry_instance_id", "") or "").strip()
        if not instance_id:
            return None
        return BuddyActivationRepairTarget(
            session_id=session.session_id,
            profile_id=profile_id,
            industry_instance_id=instance_id,
        )

    def requeue_failed_activation(
        self,
        *,
        session_id: str,
        activation_id: str | None = None,
    ) -> BuddyActivationRepairTarget | None:
        if self._domain_capability_repository is None:
            return None
        session = self._require_session(session_id)
        if activation_id and str(session.activation_id or "").strip() != str(activation_id).strip():
            return None
        if str(session.activation_status or "").strip().lower() != "failed":
            return None
        if int(session.activation_attempt_count or 0) >= 3:
            return None
        active_domain = self._domain_capability_repository.get_active_domain_capability(
            session.profile_id,
        )
        instance_id = str(getattr(active_domain, "industry_instance_id", "") or "").strip()
        if not instance_id:
            return None
        updated_session = self.queue_activation(session_id=session_id)
        return BuddyActivationRepairTarget(
            session_id=updated_session.session_id,
            profile_id=updated_session.profile_id,
            industry_instance_id=instance_id,
            activation_id=str(updated_session.activation_id or "").strip() or None,
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
        strong_pull = _is_strong_pull_interaction(
            interaction_mode=interaction_mode,
            normalized_message=_normalize_text(normalized_message),
        )
        growth_checkpoint = _is_growth_checkpoint_interaction(interaction_mode)
        if not growth_checkpoint and not strong_pull:
            return relationship
        updates: dict[str, object] = {
            "strong_pull_count": relationship.strong_pull_count + (1 if strong_pull else 0),
            "last_interaction_at": _utc_now().isoformat(),
        }
        if not growth_checkpoint:
            updated = relationship.model_copy(update=updates)
            return self._relationship_repository.upsert_relationship(updated)
        experience_delta = 8 if strong_pull else 5
        effective_reminders = list(relationship.effective_reminders)
        ineffective_reminders = list(relationship.ineffective_reminders)
        avoidance_patterns = list(relationship.avoidance_patterns)
        if strong_pull and "先把任务缩成一个最小动作" not in effective_reminders:
            effective_reminders.append("先把任务缩成一个最小动作")
        if any(token in normalized_message for token in ("拖延", "刷手机", "刷短视频", "分心", "逃避", "不想做")):
            avoidance_patterns = _unique([*avoidance_patterns, "拖延回避"])
        if any(token in normalized_message for token in ("别催", "太压", "有压力", "烦")):
            ineffective_reminders = _unique([*ineffective_reminders, "高压催促"])
        updates.update(
            {
                "effective_reminders": effective_reminders[:3],
                "ineffective_reminders": ineffective_reminders[:3],
                "avoidance_patterns": avoidance_patterns[:3],
                "communication_count": relationship.communication_count + 1,
                "pleasant_interaction_score": min(
                    100,
                    relationship.pleasant_interaction_score + pleasant_delta,
                ),
                "companion_experience": relationship.companion_experience + experience_delta,
            },
        )
        updated = relationship.model_copy(update=updates)
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
            raise ValueError("请先确认长期主方向，再给伙伴命名。")
        updated = self._relationship_repository.upsert_relationship(
            relationship.model_copy(update={"buddy_name": buddy_name.strip() or "伙伴"}),
        )
        self._onboarding_session_repository.upsert_session(
            session.model_copy(update={"status": "named"}),
        )
        return updated

    def repair_active_domain_schedules(self, *, profile_id: str) -> int:
        if (
            self._domain_capability_repository is None
            or self._industry_instance_repository is None
            or self._schedule_repository is None
        ):
            return 0
        profile = self._profile_repository.get_profile(profile_id)
        growth_target = self._growth_target_repository.get_active_target(profile_id)
        active_domain = self._domain_capability_repository.get_active_domain_capability(profile_id)
        instance_id = str(getattr(active_domain, "industry_instance_id", "") or "").strip()
        if profile is None or growth_target is None or active_domain is None or not instance_id:
            return 0
        instance = self._industry_instance_repository.get_instance(instance_id)
        if instance is None:
            return 0
        control_thread_id = str(getattr(active_domain, "control_thread_id", "") or "").strip()
        if not control_thread_id:
            control_thread_id = build_buddy_domain_control_thread_id(instance_id=instance_id)
        team_roles = self._resolve_initial_team_roles(
            profile=profile,
            instance_id=instance_id,
            existing_instance=instance,
            direction_text=growth_target.final_goal,
        )
        specs = self._ensure_durable_review_schedules(
            profile=profile,
            growth_target=growth_target,
            instance_id=instance_id,
            control_thread_id=control_thread_id,
            team_roles=team_roles,
        )
        return len(specs)

    def _require_session(self, session_id: str) -> BuddyOnboardingSessionRecord:
        session = self._onboarding_session_repository.get_session(session_id)
        if session is None:
            raise ValueError(f"未找到伙伴建档会话：{session_id}")
        return session

    def _require_profile(self, profile_id: str) -> HumanProfile:
        profile = self._profile_repository.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"未找到用户档案：{profile_id}")
        return profile

    def _require_session_by_profile(self, profile_id: str) -> BuddyOnboardingSessionRecord:
        session = self._onboarding_session_repository.get_latest_session_for_profile(profile_id)
        if session is None:
            raise ValueError(f"未找到该档案对应的伙伴建档会话：{profile_id}")
        return session

    def _derive_operating_mode(
        self,
        collaboration_contract: BuddyCollaborationContract,
    ) -> str:
        role = str(collaboration_contract.collaboration_role or "").strip().lower()
        autonomy = str(collaboration_contract.autonomy_level or "").strip().lower()
        if "guard" in autonomy or "confirm" in autonomy:
            return "guarded-collaboration"
        if role in {"operator", "assistant"}:
            return "operator-guided"
        return "collaboration-contract"

    def _build_delegation_policy(
        self,
        collaboration_contract: BuddyCollaborationContract,
    ) -> list[str]:
        return _unique(
            [
                "执行中枢负责方向、规划、监督与复盘，不直接吞掉叶子执行。",
                "具体执行应优先下放给由协作合同 backlog 生成的领域执行位。",
                f"协作角色：{collaboration_contract.collaboration_role or 'orchestrator'}。",
            ],
        )

    def _build_direct_execution_policy(
        self,
        collaboration_contract: BuddyCollaborationContract,
    ) -> list[str]:
        return _unique(
            [
                "主脑不能退化成浏览器、桌面或文档动作的叶子执行器。",
                "当执行能力缺失时，应先创建或恢复合适的领域执行位，而不是让中枢亲自下场。",
                f"主动级别：{collaboration_contract.autonomy_level or 'proactive'}。",
            ],
        )

    def _build_execution_core_identity_payload(
        self,
        *,
        profile: HumanProfile,
        growth_target: GrowthTarget,
        collaboration_contract: BuddyCollaborationContract,
    ) -> dict[str, object]:
        return {
            "profile_id": profile.profile_id,
            "primary_direction": growth_target.primary_direction,
            "final_goal": growth_target.final_goal,
            "operator_service_intent": collaboration_contract.service_intent,
            "collaboration_role": collaboration_contract.collaboration_role,
            "autonomy_level": collaboration_contract.autonomy_level,
            "report_style": collaboration_contract.report_style,
            "confirm_boundaries": list(collaboration_contract.confirm_boundaries or []),
            "operating_mode": self._derive_operating_mode(collaboration_contract),
            "delegation_policy": self._build_delegation_policy(collaboration_contract),
            "direct_execution_policy": self._build_direct_execution_policy(collaboration_contract),
        }

    def _build_contract_draft_session(
        self,
        *,
        profile: HumanProfile,
        existing_session: BuddyOnboardingSessionRecord | None,
        operation_id: str,
        operation_kind: str,
        operation_status: str,
        operation_error: str,
    ) -> BuddyOnboardingSessionRecord:
        session = BuddyOnboardingSessionRecord(
            profile_id=profile.profile_id,
            status="contract-draft",
            operation_id=operation_id,
            operation_kind=operation_kind,
            operation_status=operation_status,
            operation_error=operation_error,
            service_intent="",
            collaboration_role="orchestrator",
            autonomy_level="proactive",
            confirm_boundaries=[],
            report_style="result-first",
            collaboration_notes="",
            candidate_directions=[],
            recommended_direction="",
            selected_direction="",
            **self._build_contract_compile_cache(None),
        )
        if existing_session is None:
            return session
        return session.model_copy(
            update={
                "session_id": existing_session.session_id,
                "created_at": existing_session.created_at,
                "updated_at": _utc_now(),
            },
        )

    def _store_identity_submission(
        self,
        *,
        display_name: str,
        profession: str,
        current_stage: str,
        interests: list[str] | None = None,
        strengths: list[str] | None = None,
        constraints: list[str] | None = None,
        goal_intention: str,
        existing_profile: HumanProfile | None = None,
        existing_session: BuddyOnboardingSessionRecord | None = None,
    ) -> BuddyIdentitySubmitResult:
        profile = HumanProfile(
            display_name=display_name,
            profession=profession,
            current_stage=current_stage,
            interests=interests or [],
            strengths=strengths or [],
            constraints=constraints or [],
            goal_intention=goal_intention,
        )
        if existing_profile is not None:
            profile = profile.model_copy(
                update={
                    "profile_id": existing_profile.profile_id,
                    "created_at": existing_profile.created_at,
                    "updated_at": _utc_now(),
                },
            )
        profile = self._profile_repository.upsert_profile(profile)
        session = self._build_contract_draft_session(
            profile=profile,
            existing_session=existing_session,
            operation_id=str(getattr(existing_session, "operation_id", "") or "").strip(),
            operation_kind=str(getattr(existing_session, "operation_kind", "") or "").strip(),
            operation_status=str(getattr(existing_session, "operation_status", "") or "idle").strip()
            or "idle",
            operation_error=str(getattr(existing_session, "operation_error", "") or "").strip(),
        )
        session = self._onboarding_session_repository.upsert_session(session)
        return BuddyIdentitySubmitResult(
            session_id=session.session_id,
            profile=profile,
            status=session.status,
        )

    def _build_contract_compile_cache(
        self,
        growth_plan: BuddyOnboardingContractCompileResult | None,
    ) -> dict[str, object]:
        if growth_plan is None:
            return {
                "draft_direction": "",
                "draft_final_goal": "",
                "draft_why_it_matters": "",
                "draft_backlog_items": [],
            }
        return {
            "draft_direction": str(growth_plan.recommended_direction or "").strip(),
            "draft_final_goal": str(growth_plan.final_goal or "").strip(),
            "draft_why_it_matters": str(growth_plan.why_it_matters or "").strip(),
            "draft_backlog_items": [
                item.model_dump(mode="json")
                for item in growth_plan.backlog_items
                if item.title.strip() and item.summary.strip()
            ][:3],
        }

    def _build_contract_from_session(
        self,
        session: BuddyOnboardingSessionRecord,
    ) -> BuddyCollaborationContract:
        return BuddyCollaborationContract(
            service_intent=session.service_intent,
            collaboration_role=session.collaboration_role,
            autonomy_level=session.autonomy_level,
            confirm_boundaries=list(session.confirm_boundaries or []),
            report_style=session.report_style,
            collaboration_notes=session.collaboration_notes,
        )

    def _clear_operation_state(self) -> dict[str, object]:
        return {
            "operation_id": "",
            "operation_kind": "",
            "operation_status": "idle",
            "operation_error": "",
        }

    def _resolve_cached_contract_compile(
        self,
        *,
        session: BuddyOnboardingSessionRecord,
        selected_direction: str,
    ) -> BuddyOnboardingContractCompileResult | None:
        if str(session.draft_direction or "").strip() != selected_direction.strip():
            return None
        final_goal = str(session.draft_final_goal or "").strip()
        why_it_matters = str(session.draft_why_it_matters or "").strip()
        backlog_items = [
            BuddyOnboardingBacklogSeed.model_validate(item)
            for item in list(session.draft_backlog_items or [])
            if isinstance(item, dict)
        ]
        if not final_goal and not why_it_matters and not backlog_items:
            return None
        return BuddyOnboardingContractCompileResult(
            candidate_directions=[selected_direction.strip()],
            recommended_direction=selected_direction.strip(),
            final_goal=final_goal,
            why_it_matters=why_it_matters,
            backlog_items=backlog_items[:3],
        )

    def _require_confirmable_contract_compile(
        self,
        *,
        session: BuddyOnboardingSessionRecord,
        selected_direction: str,
    ) -> BuddyOnboardingContractCompileResult:
        normalized_direction = selected_direction.strip()
        candidate_directions = _unique(list(session.candidate_directions or []))
        if normalized_direction and candidate_directions and normalized_direction not in candidate_directions:
            raise ValueError("所选主方向必须来自当前这轮协作合同编译结果。")
        cached = self._resolve_cached_contract_compile(
            session=session,
            selected_direction=normalized_direction,
        )
        if cached is not None:
            return self._validate_contract_compile_result(cached)
        if str(session.draft_direction or "").strip():
            raise ValueError(
                "当前所选主方向需要重新编译协作合同后才能确认。",
            )
        raise ValueError("请先完成协作合同编译，再确认主方向。")

    def _resolve_contract_compile(
        self,
        *,
        profile: HumanProfile,
        collaboration_contract: BuddyCollaborationContract,
    ) -> BuddyOnboardingContractCompileResult:
        if self._onboarding_reasoner is None:
            raise BuddyOnboardingReasonerUnavailableError(
                "伙伴建档模型暂不可用。",
            )
        try:
            growth_plan = self._onboarding_reasoner.compile_contract(
                profile=profile,
                collaboration_contract=collaboration_contract,
            )
        except BuddyOnboardingReasonerTimeoutError:
            raise
        except TimeoutError:
            raise
        except BuddyOnboardingReasonerUnavailableError:
            raise
        except Exception:
            logger.warning("伙伴建档协作合同编译失败。", exc_info=True)
            raise BuddyOnboardingReasonerUnavailableError(
                "伙伴建档模型未返回有效结果。",
            ) from None
        return self._validate_contract_compile_result(growth_plan)

    def _validate_contract_compile_result(
        self,
        growth_plan: BuddyOnboardingContractCompileResult | None,
    ) -> BuddyOnboardingContractCompileResult:
        if growth_plan is None:
            raise BuddyOnboardingReasonerUnavailableError(
                "伙伴建档模型未返回有效结果。",
            )
        recommended_direction = str(growth_plan.recommended_direction or "").strip()
        final_goal = str(growth_plan.final_goal or "").strip()
        why_it_matters = str(growth_plan.why_it_matters or "").strip()
        backlog_items: list[BuddyOnboardingBacklogSeed] = []
        for index, item in enumerate(list(growth_plan.backlog_items or []), start=1):
            title = item.title.strip()
            summary = item.summary.strip()
            if not title or not summary:
                continue
            lane_hint = _normalize_buddy_lane_hint(item.lane_hint)
            if not lane_hint:
                raise BuddyOnboardingReasonerUnavailableError(
                    "伙伴建档模型未返回有效的职责车道。",
                )
            backlog_items.append(
                item.model_copy(
                    update={
                        "lane_hint": lane_hint,
                        "title": title,
                        "summary": summary,
                        "source_key": item.source_key.strip() or f"model-seed-{index}",
                    },
                )
            )
        backlog_items = backlog_items[:3]
        candidate_directions = _unique(
            [recommended_direction, *list(growth_plan.candidate_directions or [])],
        )
        if not recommended_direction or not final_goal or not why_it_matters or not backlog_items:
            raise BuddyOnboardingReasonerUnavailableError(
                "伙伴建档模型未返回有效结果。",
            )
        return growth_plan.model_copy(
            update={
                "candidate_directions": candidate_directions[:3],
                "recommended_direction": recommended_direction,
                "final_goal": final_goal,
                "why_it_matters": why_it_matters,
                "backlog_items": backlog_items,
            },
        )

    def _validate_selected_direction(
        self,
        *,
        session: BuddyOnboardingSessionRecord,
        selected_direction: str,
    ) -> str:
        normalized = selected_direction.strip()
        if not normalized:
            raise ValueError("请选择一个长期主方向。")
        return normalized

    def _activate_domain_capability(
        self,
        *,
        profile: HumanProfile,
        selected_direction: str,
        capability_action: str,
        target_domain_id: str | None,
        preview: BuddyDirectionTransitionPreviewResult,
    ) -> BuddyDomainCapabilityRecord:
        if self._domain_capability_repository is None:
            return BuddyDomainCapabilityRecord(
                profile_id=profile.profile_id,
                domain_key=preview.selected_domain_key,
                domain_label=self._present_domain_label(
                    preview.selected_domain_key,
                    selected_direction,
                ),
                status="active",
                last_activated_at=_utc_now().isoformat(),
            )

        if capability_action == "keep-active":
            active = self._domain_capability_repository.get_active_domain_capability(
                profile.profile_id,
            )
            if active is None:
                raise ValueError("当前没有可沿用的活跃领域能力。")
            updated = active.model_copy(
                update={
                    "domain_label": self._present_domain_label(
                        preview.selected_domain_key,
                        selected_direction,
                    ),
                    "status": "active",
                    "last_activated_at": _utc_now().isoformat(),
                },
            )
            return self._domain_capability_repository.upsert_domain_capability(updated)

        if capability_action == "restore-archived":
            resolved_target_domain_id = target_domain_id
            if not resolved_target_domain_id and len(preview.archived_matches) == 1:
                resolved_target_domain_id = str(preview.archived_matches[0]["domain_id"])
            if not resolved_target_domain_id:
                raise ValueError("请选择要恢复的历史领域能力。")
            archived = self._domain_capability_repository.get_domain_capability(
                resolved_target_domain_id,
            )
            if archived is None or archived.profile_id != profile.profile_id:
                raise ValueError("所选历史领域能力不属于当前档案。")
            self._domain_capability_repository.archive_active_domain_capabilities(
                profile.profile_id,
                except_domain_id=archived.domain_id,
            )
            restored = archived.model_copy(
                update={
                    "status": "active",
                    "domain_label": self._present_domain_label(
                        preview.selected_domain_key,
                        selected_direction,
                    ),
                    "last_activated_at": _utc_now().isoformat(),
                },
            )
            return self._domain_capability_repository.upsert_domain_capability(restored)

        self._domain_capability_repository.archive_active_domain_capabilities(
            profile.profile_id,
        )
        created = BuddyDomainCapabilityRecord(
            profile_id=profile.profile_id,
            domain_key=preview.selected_domain_key,
            domain_label=self._present_domain_label(
                preview.selected_domain_key,
                selected_direction,
            ),
            status="active",
            capability_score=0,
            evolution_stage="seed",
            last_activated_at=_utc_now().isoformat(),
        )
        return self._domain_capability_repository.upsert_domain_capability(created)

    def _present_domain_label(self, domain_key: str, selected_direction: str) -> str:
        normalized_direction = str(selected_direction or "").strip()
        if normalized_direction:
            return normalized_direction
        normalized_domain = str(domain_key or "").strip().replace("-", " ")
        return normalized_domain or "未分配领域"

    def _ensure_growth_scaffold(
        self,
        *,
        profile: HumanProfile,
        growth_target: GrowthTarget,
        domain_capability: BuddyDomainCapabilityRecord,
        capability_action: str,
        growth_plan: BuddyOnboardingContractCompileResult | None = None,
    ) -> tuple[
        GrowthTarget,
        BuddyDomainCapabilityRecord,
        dict[str, object] | None,
        list[dict[str, object]],
    ]:
        instance_id, control_thread_id = self._resolve_domain_carrier_binding(
            profile=profile,
            domain_capability=domain_capability,
            capability_action=capability_action,
        )
        bound_domain_capability = self._persist_domain_carrier_binding(
            domain_capability=domain_capability,
            instance_id=instance_id,
            control_thread_id=control_thread_id,
        )
        if (
            self._industry_instance_repository is None
            or self._operating_lane_service is None
            or self._backlog_service is None
            or self._operating_cycle_service is None
            or self._assignment_service is None
        ):
            return growth_target, bound_domain_capability, self._build_execution_carrier_handoff(
                profile=profile,
                instance_id=instance_id,
                control_thread_id=control_thread_id,
                label=profile.display_name,
                current_cycle_id=growth_target.current_cycle_label or "Cycle 1",
                team_generated=False,
            ), []
        existing_instance = self._industry_instance_repository.get_instance(instance_id)
        team_roles = self._resolve_initial_team_roles(
            profile=profile,
            instance_id=instance_id,
            existing_instance=existing_instance,
            direction_text=growth_target.final_goal,
            growth_plan=growth_plan,
        )
        instance = IndustryInstanceRecord(
            instance_id=instance_id,
            label=profile.display_name,
            summary=growth_target.final_goal,
            owner_scope=profile.profile_id,
            status="active",
            profile_payload=_build_buddy_industry_profile(
                profile=profile,
                growth_target=growth_target,
            ).model_dump(mode="json"),
            team_payload=IndustryTeamBlueprint(
                team_id=instance_id,
                label=profile.display_name,
                summary=growth_target.final_goal,
                agents=team_roles,
            ).model_dump(mode="json"),
            execution_core_identity_payload=self._build_execution_core_identity_payload(
                profile=profile,
                growth_target=growth_target,
                collaboration_contract=self._build_contract_from_session(
                    self._require_session_by_profile(profile.profile_id),
                ),
            ),
            agent_ids=[role.agent_id for role in team_roles],
            lifecycle_status="running",
            autonomy_status="coordinating",
            current_cycle_id=existing_instance.current_cycle_id if existing_instance is not None else None,
            next_cycle_due_at=existing_instance.next_cycle_due_at if existing_instance is not None else None,
            last_cycle_started_at=existing_instance.last_cycle_started_at if existing_instance is not None else None,
            created_at=existing_instance.created_at if existing_instance is not None else _utc_now(),
            updated_at=_utc_now(),
        )
        persisted_instance = self._industry_instance_repository.upsert_instance(instance)
        lanes = self._operating_lane_service.seed_from_roles(
            industry_instance_id=instance_id,
            roles=team_roles,
        )
        lanes_by_id = {
            str(getattr(lane, "id", "")).strip(): lane
            for lane in lanes
            if str(getattr(lane, "id", "")).strip()
        }
        def _lane_owner(lane_id: str | None, attr: str) -> str | None:
            lane = lanes_by_id.get(str(lane_id or "").strip())
            value = getattr(lane, attr, None) if lane is not None else None
            text = str(value or "").strip()
            return text or None
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
                growth_plan=growth_plan,
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
            summary=f"{profile.display_name} 的伙伴建档启动周期",
            metadata={"profile_id": profile.profile_id, "primary_direction": growth_target.primary_direction},
        )
        self._assignment_service.ensure_assignments(
            industry_instance_id=instance_id,
            cycle_id=cycle.id,
            specs=[
                {
                    "owner_agent_id": (
                        _lane_owner(item.lane_id, "owner_agent_id")
                        or EXECUTION_CORE_AGENT_ID
                    ),
                    "owner_role_id": (
                        _lane_owner(item.lane_id, "owner_role_id")
                        or EXECUTION_CORE_ROLE_ID
                    ),
                    "lane_id": item.lane_id,
                    "backlog_item_id": item.id,
                    "title": item.title,
                    "summary": item.summary,
                    "status": "queued" if index == 0 else "planned",
                    "metadata": {
                        "profile_id": profile.profile_id,
                        "primary_direction": growth_target.primary_direction,
                        "owner_agent_id": (
                            _lane_owner(item.lane_id, "owner_agent_id")
                            or EXECUTION_CORE_AGENT_ID
                        ),
                        "industry_role_id": (
                            _lane_owner(item.lane_id, "owner_role_id")
                            or EXECUTION_CORE_ROLE_ID
                        ),
                    },
                }
                for index, item in enumerate(backlog_items)
            ],
        )
        schedule_specs = self._ensure_durable_review_schedules(
            profile=profile,
            growth_target=growth_target,
            instance_id=instance_id,
            control_thread_id=control_thread_id,
            team_roles=team_roles,
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
        updated_target = self._growth_target_repository.upsert_target(
            growth_target.model_copy(update={"current_cycle_label": cycle.title}),
        )
        self._sync_domain_carrier_lifecycle(
            profile_id=profile.profile_id,
            active_domain_id=bound_domain_capability.domain_id,
            active_instance_id=instance_id,
        )
        return updated_target, bound_domain_capability, self._build_execution_carrier_handoff(
            profile=profile,
            instance_id=instance_id,
            control_thread_id=control_thread_id,
            label=persisted_instance.label,
            current_cycle_id=cycle.id,
            team_generated=True,
        ), schedule_specs

    def _ensure_durable_review_schedules(
        self,
        *,
        profile: HumanProfile,
        growth_target: GrowthTarget,
        instance_id: str,
        control_thread_id: str,
        team_roles: list[IndustryRoleBlueprint],
    ) -> list[dict[str, object]]:
        if self._schedule_repository is None:
            return []
        profile_payload = _build_buddy_industry_profile(
            profile=profile,
            growth_target=growth_target,
        )
        execution_core_role = IndustryRoleBlueprint(
            role_id=EXECUTION_CORE_ROLE_ID,
            agent_id=EXECUTION_CORE_AGENT_ID,
            actor_key=EXECUTION_CORE_AGENT_ID,
            name=f"{profile.display_name} Execution Core",
            role_name="Execution Core",
            role_summary="负责主脑长程复盘，并把下一步正式动作路由到正确执行位。",
            mission="审阅进度、积压、派工与证据，然后把下一步正式动作路由到正确执行位。",
            goal_kind=EXECUTION_CORE_ROLE_ID,
            agent_class="system",
            employment_mode="career",
            activation_mode="persistent",
            suspendable=False,
            reports_to=None,
            risk_level="guarded",
            allowed_capabilities=["system:dispatch_query"],
            preferred_capability_families=["planning", "coordination"],
            evidence_expectations=["execution-core review note"],
        )
        draft = IndustryDraftPlan(
            team=IndustryTeamBlueprint(
                team_id=instance_id,
                label=profile.display_name,
                summary=growth_target.final_goal,
                agents=[execution_core_role, *team_roles],
            ),
            goals=[],
            schedules=[
                IndustryDraftSchedule(
                    schedule_id=f"{instance_id}-main-brain-morning-review",
                    owner_agent_id=EXECUTION_CORE_AGENT_ID,
                    title=f"{profile.display_name} 超级伙伴晨间复盘",
                    summary="晨间检查报告、积压、派工、阻塞与下一步动作。",
                    cron="0 9 * * *",
                    timezone="Asia/Shanghai",
                    dispatch_mode="final",
                ),
                IndustryDraftSchedule(
                    schedule_id=f"{instance_id}-main-brain-evening-review",
                    owner_agent_id=EXECUTION_CORE_AGENT_ID,
                    title=f"{profile.display_name} 超级伙伴晚间复盘",
                    summary="晚间检查执行结果、未解决阻塞与明日路由安排。",
                    cron="0 19 * * *",
                    timezone="Asia/Shanghai",
                    dispatch_mode="final",
                ),
            ],
        )
        seeds = compile_industry_schedule_seeds(
            profile_payload,
            draft=draft,
            owner_scope=profile.profile_id,
        )
        normalized_specs: list[dict[str, object]] = []
        for seed in seeds:
            request_payload = {
                **dict(seed.request_payload),
                "buddy_profile_id": profile.profile_id,
            }
            if seed.dispatch_session_id != control_thread_id:
                request_payload.update(
                    {
                        "session_id": control_thread_id,
                        "control_thread_id": control_thread_id,
                    },
                )
                seed = seed.model_copy(
                    update={
                        "dispatch_session_id": control_thread_id,
                        "request_payload": request_payload,
                    },
                )
            else:
                seed = seed.model_copy(
                    update={
                        "request_payload": request_payload,
                    },
                )
            spec = self._build_schedule_spec(seed)
            self._upsert_schedule_record(spec)
            normalized_specs.append(spec)
        return normalized_specs

    def _build_schedule_spec(self, seed) -> dict[str, Any]:
        return {
            "id": seed.schedule_id,
            "name": seed.title,
            "enabled": True,
            "schedule": {
                "type": "cron",
                "cron": seed.cron,
                "timezone": seed.timezone,
            },
            "task_type": "agent",
            "request": dict(seed.request_payload),
            "dispatch": {
                "type": "channel",
                "channel": seed.dispatch_channel,
                "target": {
                    "user_id": seed.dispatch_user_id,
                    "session_id": seed.dispatch_session_id,
                },
                "mode": seed.dispatch_mode,
                "meta": {
                    "summary": seed.summary,
                    "owner_agent_id": seed.owner_agent_id,
                    **dict(seed.metadata),
                },
            },
            "runtime": {
                "max_concurrency": 1,
                "timeout_seconds": 180,
                "misfire_grace_seconds": 60,
            },
            "meta": {
                "summary": seed.summary,
                "owner_agent_id": seed.owner_agent_id,
                **dict(seed.metadata),
            },
        }

    def _upsert_schedule_record(self, spec: dict[str, object]) -> None:
        if self._schedule_repository is None:
            return
        job = CronJobSpec.model_validate(spec)
        existing = self._schedule_repository.get_schedule(job.id)
        preserved = existing or ScheduleRecord(
            id=job.id,
            title=job.name,
            cron=job.schedule.cron,
        )
        meta = dict(job.meta or {})
        trigger_target = str(meta.get("trigger_target") or "").strip() or preserved.trigger_target
        lane_id = str(meta.get("lane_id") or "").strip() or preserved.lane_id
        status = preserved.status
        if status == "deleted":
            status = "paused" if job.enabled is False else "scheduled"
        self._schedule_repository.upsert_schedule(
            ScheduleRecord(
                id=job.id,
                title=job.name,
                cron=job.schedule.cron,
                timezone=job.schedule.timezone,
                status=status,
                enabled=job.enabled,
                task_type=job.task_type,
                target_channel=job.dispatch.channel,
                target_user_id=job.dispatch.target.user_id,
                target_session_id=job.dispatch.target.session_id,
                last_run_at=preserved.last_run_at,
                next_run_at=preserved.next_run_at,
                last_error=preserved.last_error,
                source_ref="state:/cron-sole-repository",
                spec_payload=job.model_dump(mode="json"),
                schedule_kind=str(meta.get("schedule_kind") or preserved.schedule_kind or "cadence"),
                trigger_target=trigger_target,
                lane_id=lane_id,
                created_at=preserved.created_at,
                updated_at=_utc_now(),
            ),
        )

    def _resolve_domain_carrier_binding(
        self,
        *,
        profile: HumanProfile,
        domain_capability: BuddyDomainCapabilityRecord,
        capability_action: str,
    ) -> tuple[str, str]:
        instance_id = str(domain_capability.industry_instance_id or "").strip()
        control_thread_id = str(domain_capability.control_thread_id or "").strip()
        if not instance_id:
            if capability_action != "start-new":
                legacy_instance_id = f"buddy:{profile.profile_id}"
                has_legacy_instance = (
                    self._industry_instance_repository is not None
                    and self._industry_instance_repository.get_instance(legacy_instance_id)
                    is not None
                )
                if has_legacy_instance:
                    instance_id = legacy_instance_id
            if not instance_id:
                instance_id = build_buddy_domain_instance_id(
                    profile_id=profile.profile_id,
                    domain_id=domain_capability.domain_id,
                )
        if not control_thread_id:
            control_thread_id = build_buddy_domain_control_thread_id(
                instance_id=instance_id,
            )
        return instance_id, control_thread_id

    def _persist_domain_carrier_binding(
        self,
        *,
        domain_capability: BuddyDomainCapabilityRecord,
        instance_id: str,
        control_thread_id: str,
    ) -> BuddyDomainCapabilityRecord:
        if (
            domain_capability.industry_instance_id == instance_id
            and domain_capability.control_thread_id == control_thread_id
        ):
            return domain_capability
        updated = domain_capability.model_copy(
            update={
                "industry_instance_id": instance_id,
                "control_thread_id": control_thread_id,
            },
        )
        if self._domain_capability_repository is None:
            return updated
        return self._domain_capability_repository.upsert_domain_capability(updated)

    def _sync_domain_carrier_lifecycle(
        self,
        *,
        profile_id: str,
        active_domain_id: str,
        active_instance_id: str,
    ) -> None:
        if (
            self._domain_capability_repository is None
            or self._industry_instance_repository is None
        ):
            return
        now = _utc_now()
        for record in self._domain_capability_repository.list_domain_capabilities(profile_id):
            instance_id = str(record.industry_instance_id or "").strip()
            if not instance_id:
                continue
            instance = self._industry_instance_repository.get_instance(instance_id)
            if instance is None:
                continue
            if record.domain_id == active_domain_id and instance_id == active_instance_id:
                self._industry_instance_repository.upsert_instance(
                    instance.model_copy(
                        update={
                            "status": "active",
                            "lifecycle_status": "running",
                            "autonomy_status": "coordinating",
                            "updated_at": now,
                        },
                    ),
                )
                continue
            if record.status == "archived":
                self._industry_instance_repository.upsert_instance(
                    instance.model_copy(
                        update={
                            "status": "archived",
                            "lifecycle_status": "archived",
                            "autonomy_status": "archived",
                            "updated_at": now,
                        },
                    ),
                )

    def _build_execution_carrier_handoff(
        self,
        *,
        profile: HumanProfile,
        instance_id: str,
        control_thread_id: str,
        label: str,
        current_cycle_id: str,
        team_generated: bool,
    ) -> dict[str, object]:
        return build_buddy_execution_carrier_handoff(
            profile=profile,
            instance_id=instance_id,
            control_thread_id=control_thread_id,
            label=label,
            current_cycle_id=current_cycle_id,
            team_generated=team_generated,
        )

    def _resolve_initial_team_roles(
        self,
        *,
        profile: HumanProfile,
        instance_id: str,
        existing_instance: IndustryInstanceRecord | None,
        direction_text: str | None,
        growth_plan: BuddyOnboardingContractCompileResult | None = None,
    ) -> list[IndustryRoleBlueprint]:
        existing_agents = (
            list((existing_instance.team_payload or {}).get("agents") or [])
            if existing_instance is not None
            else []
        )
        restored_roles: list[IndustryRoleBlueprint] = []
        for item in existing_agents:
            try:
                restored_roles.append(IndustryRoleBlueprint.model_validate(item))
            except Exception:
                continue
        if restored_roles:
            return restored_roles
        label = profile.display_name.strip() or "伙伴"
        domain_key = derive_buddy_domain_key(direction_text or "")
        lane_hints = _resolve_growth_plan_lane_hints(growth_plan)
        if lane_hints:
            dynamic_roles: list[IndustryRoleBlueprint] = []
            for position, lane_hint in enumerate(lane_hints, start=1):
                role_id = lane_hint or f"specialist-{position}"
                lane_label = _present_buddy_lane_label(role_id)
                allowed_capabilities = buddy_specialist_allowed_capabilities(
                    domain_key=domain_key,
                    role_id=role_id,
                )
                preferred_families = buddy_specialist_preferred_capability_families(
                    domain_key=domain_key,
                    role_id=role_id,
                )
                lane_summary = (
                    f"负责“{label}”当前的{lane_label}，把方向拆成可执行进展、证据和下一步动作。"
                )
                dynamic_roles.append(
                    IndustryRoleBlueprint(
                        role_id=role_id,
                        agent_id=f"{instance_id}:{role_id}",
                        actor_key=f"{instance_id}:{role_id}",
                        name=f"{label} {lane_label}",
                        role_name=lane_label,
                        role_summary=lane_summary,
                        mission=lane_summary,
                        goal_kind=role_id,
                        agent_class="business",
                        employment_mode="career",
                        activation_mode="persistent",
                        suspendable=False,
                        reports_to=EXECUTION_CORE_ROLE_ID,
                        risk_level="guarded",
                        allowed_capabilities=allowed_capabilities,
                        preferred_capability_families=preferred_families,
                        evidence_expectations=[f"{lane_label}执行证据"],
                    ),
                )
            if dynamic_roles:
                return dynamic_roles
        raise BuddyOnboardingReasonerUnavailableError(
            "伙伴建档模型未返回有效的动态执行位车道。",
        )

    def _build_initial_backlog_specs(
        self,
        *,
        profile: HumanProfile,
        growth_target: GrowthTarget,
        lanes: list[object],
        growth_plan: BuddyOnboardingContractCompileResult | None = None,
    ) -> list[tuple[str | None, str, str, int, str]]:
        lane_ids = [getattr(lane, "id", None) for lane in lanes]
        primary_lane_id = lane_ids[0] if lane_ids else None
        proof_lane_id = lane_ids[1] if len(lane_ids) > 1 else primary_lane_id
        lane_id_by_role = {
            _normalize_buddy_lane_hint(getattr(lane, "owner_role_id", None)): getattr(lane, "id", None)
            for lane in lanes
            if _normalize_buddy_lane_hint(getattr(lane, "owner_role_id", None))
        }
        if growth_plan is not None and growth_plan.backlog_items:
            generated_specs: list[tuple[str | None, str, str, int, str]] = []
            for index, item in enumerate(growth_plan.backlog_items, start=1):
                normalized_lane_hint = _normalize_buddy_lane_hint(item.lane_hint)
                lane_id = lane_id_by_role.get(normalized_lane_hint)
                if lane_id is None:
                    raise BuddyOnboardingReasonerUnavailableError(
                        "伙伴建档模型返回的积压项没有匹配到对应执行位车道。",
                    )
                title = item.title.strip()
                summary = item.summary.strip()
                if not title or not summary:
                    continue
                source_key = item.source_key.strip() or f"model-seed-{index}"
                generated_specs.append(
                    (
                        lane_id,
                        title,
                        summary,
                        max(1, min(3, int(item.priority))),
                        f"profile:{profile.profile_id}:{source_key}",
                    ),
                )
            if generated_specs:
                return generated_specs
        raise BuddyOnboardingReasonerUnavailableError(
            "伙伴建档模型未返回有效的初始积压项。",
        )

    def _seed_avoidance_patterns(
        self,
        *,
        profile: HumanProfile,
        signals: list[str],
        existing: list[str] | None = None,
    ) -> list[str]:
        source = _normalize_text(" ".join([profile.goal_intention, *profile.constraints, *signals]))
        patterns = list(existing or [])
        if _contains_any(source, ("拖延", "分心", "刷", "逃避", "不想做")):
            patterns.append("拖延回避")
        if _contains_any(source, ("迷茫", "没方向", "不知道")):
            patterns.append("方向摇摆")
        if _contains_any(source, ("时间", "精力", "累", "疲惫")):
            patterns.append("精力透支")
        return _unique(patterns)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "BuddyContractCompileSubmitResult",
    "BuddyDirectionConfirmationResult",
    "BuddyDirectionTransitionPreviewResult",
    "BuddyIdentitySubmitResult",
    "BuddyOnboardingService",
]
