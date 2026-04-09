# -*- coding: utf-8 -*-
"""Buddy-first onboarding service built on top of existing main-brain truth."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import unicodedata
from typing import Any

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
    BuddyOnboardingGrowthPlan,
    BuddyOnboardingReasonedTurn,
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


class BuddyDirectionTransitionPreviewResult(BaseModel):
    session_id: str
    selected_direction: str
    selected_domain_key: str
    suggestion_kind: str
    recommended_action: str
    reason_summary: str
    current_domain: dict[str, object] | None = None
    archived_matches: list[dict[str, object]] = Field(default_factory=list)


@dataclass(slots=True)
class BuddyDirectionConfirmationResult:
    session: BuddyOnboardingSessionRecord
    growth_target: GrowthTarget
    relationship: CompanionRelationship
    domain_capability: BuddyDomainCapabilityRecord
    execution_carrier: dict[str, object] | None = None
    schedule_specs: list[dict[str, object]] | None = None


_DEFAULT_DIRECTION = "建立稳定、自主、长期向上的人生主方向"
_STOCKS_DIRECTION = "建立稳定、可验证的股票交易与投资成长路径"
_CREATOR_DIRECTION = "建立独立创作与内容事业的长期成长路径"
_DESIGN_DIRECTION = "建立高杠杆的设计与系统领导力成长路径"
_OPERATIONS_DIRECTION = "建立从执行型走向策略型的长期职业跃迁路径"
_HEALTH_DIRECTION = "建立自律、健康与自我掌控的人生重建路径"


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
        return "Specialist"
    parts = [part for part in normalized.split("-") if part]
    if all(part.isascii() for part in parts):
        return " ".join(part.capitalize() for part in parts)
    return normalized


def _resolve_growth_plan_lane_hints(
    growth_plan: BuddyOnboardingGrowthPlan | None,
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


def _build_buddy_question(
    *,
    profile: HumanProfile,
    question_count: int,
    tightened: bool = False,
    transcript: list[str] | None = None,
) -> str:
    source = " ".join(
        _normalize_text(item)
        for item in [
            profile.goal_intention,
            profile.profession,
            profile.current_stage,
            *(profile.interests or []),
            *(transcript or []),
        ]
        if str(item or "").strip()
    )
    if tightened:
        return (
            f"{profile.display_name}，如果现在只能先改变一件事，"
            "你最想摆脱的是什么，为什么必须是现在？"
        )
    if not _contains_any(
        source,
        (
            "stock",
            "stocks",
            "trading",
            "trade",
            "invest",
            "investing",
            "creator",
            "content",
            "writer",
            "writing",
            "design",
            "designer",
            "system",
            "systems",
            "operator",
            "operations",
            "fitness",
            "health",
            "股票",
            "炒股",
            "证券",
            "基金",
            "投资",
            "交易",
            "内容",
            "创作",
            "写作",
            "设计",
            "系统",
            "运营",
            "健康",
            "健身",
        ),
    ):
        return "先别泛化，直接告诉我：你最想在哪个具体领域做出结果？"
    if not _contains_any(
        source,
        (
            "自由",
            "income",
            "independent income",
            "financial freedom",
            "稳定收入",
            "赚钱",
            "结果",
            "proof",
            "作品",
            "回报",
            "收益",
            "财富自由",
        ),
    ):
        return "如果这条路走对了，你最想先看到的现实结果是什么？"
    if not _contains_any(
        source,
        (
            "stuck",
            "lost",
            "risk",
            "discipline",
            "拖延",
            "卡住",
            "没收入",
            "失业",
            "风险",
            "自律",
            "执行不下去",
        ),
    ):
        return "现在最卡你的现实问题是什么？说具体一点。"
    if question_count <= 2:
        return "如果接下来三个月只能先抓一条主线，你最愿意每天持续推进什么？"
    return "如果我现在就帮你收成一个长期方向，它应该叫什么？"


def _derive_candidate_directions(
    *,
    profile: HumanProfile,
    transcript: list[str],
) -> list[str]:
    segments = [
        profile.profession,
        profile.current_stage,
        profile.goal_intention,
        *profile.interests,
        *profile.strengths,
        *transcript,
    ]
    source = " ".join(
        _normalize_text(item)
        for item in segments
        if str(item or "").strip()
    )
    if not source:
        return [_DEFAULT_DIRECTION]

    direction_rules: list[tuple[str, tuple[str, ...], int]] = [
        (
            _STOCKS_DIRECTION,
            (
                "stock",
                "stocks",
                "trading",
                "trade",
                "invest",
                "investing",
                "quant",
                "portfolio",
                "股票",
                "炒股",
                "证券",
                "基金",
                "投资",
                "交易",
                "交易系统",
                "风险控制",
                "仓位",
            ),
            4,
        ),
        (
            _CREATOR_DIRECTION,
            (
                "content",
                "creator",
                "writing",
                "writer",
                "write",
                "story",
                "storytelling",
                "audience",
                "video",
                "creator economy",
                "personal brand",
                "brand",
                "ip",
                "内容",
                "创作",
                "写作",
                "作品",
                "表达",
                "自媒体",
                "影响力",
                "视频",
                "短视频",
                "镜头",
                "讲故事",
                "个人ip",
                "个人品牌",
                "内容作品",
                "创作者",
                "内容运营",
                "内容创作",
                "内容表达",
                "独立收入",
                "内容变现",
                "作品收入",
                "长期影响力",
            ),
            3,
        ),
        (
            _DESIGN_DIRECTION,
            (
                "design",
                "designer",
                "product",
                "systems",
                "ux",
                "ui",
                "service design",
                "设计",
                "产品",
                "系统",
                "体验",
                "策略",
                "品牌设计",
            ),
            3,
        ),
        (
            _OPERATIONS_DIRECTION,
            (
                "operator",
                "operations",
                "process",
                "execution",
                "program manager",
                "运营",
                "执行",
                "流程",
                "管理",
                "落地",
                "组织",
                "项目",
                "项目管理",
            ),
            2,
        ),
        (
            _HEALTH_DIRECTION,
            (
                "health",
                "discipline",
                "energy",
                "exercise",
                "fitness",
                "健康",
                "自律",
                "精力",
                "运动",
                "作息",
                "身体",
                "减肥",
            ),
            2,
        ),
    ]

    scores: dict[str, int] = {}
    for direction, tokens, weight in direction_rules:
        score = 0
        for token in tokens:
            if token in source:
                score += weight
        if score > 0:
            scores[direction] = score

    if _contains_any(
        source,
        (
            "stock",
            "stocks",
            "trading",
            "trade",
            "invest",
            "investing",
            "股票",
            "炒股",
            "证券",
            "基金",
            "投资",
            "交易",
            "财富自由",
            "financial freedom",
        ),
    ):
        scores[_STOCKS_DIRECTION] = scores.get(_STOCKS_DIRECTION, 0) + 3
    if (
        _contains_any(source, ("独立收入", "自主收入", "收入", "变现", "赚钱"))
        and _contains_any(source, ("content", "creator", "writing", "内容", "创作", "写作", "作品"))
    ):
        scores[_CREATOR_DIRECTION] = scores.get(_CREATOR_DIRECTION, 0) + 3
    if _contains_any(source, ("作品", "输出", "长期影响力", "内容运营", "内容创作")):
        scores[_CREATOR_DIRECTION] = scores.get(_CREATOR_DIRECTION, 0) + 2
    if _contains_any(source, ("职业转型", "跃迁", "职业升级")):
        scores[_OPERATIONS_DIRECTION] = scores.get(_OPERATIONS_DIRECTION, 0) + 2

    ordered = [
        direction
        for direction, _score in sorted(
            scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    ordered.append(_DEFAULT_DIRECTION)
    return _unique(ordered)[:3]


def _derive_final_goal(*, profile: HumanProfile, direction: str) -> str:
    if _STOCKS_DIRECTION in direction or derive_buddy_domain_key(direction) == "stocks":
        return f"帮助{profile.display_name}建立稳定、可验证、可持续的股票交易与投资成长路径"
    if _CREATOR_DIRECTION in direction:
        return f"帮助{profile.display_name}建立可持续的创作事业与独立成长轨道"
    if _DESIGN_DIRECTION in direction:
        return f"帮助{profile.display_name}成长为高杠杆的设计与系统领导者"
    if _OPERATIONS_DIRECTION in direction:
        return f"帮助{profile.display_name}从高执行消耗转向更稳定的策略型掌控"
    if _HEALTH_DIRECTION in direction:
        return f"帮助{profile.display_name}重建健康、自律且可持续的人生状态"
    return f"帮助{profile.display_name}建立真正属于自己的长期成长方向与自主掌控感"


def _derive_why_it_matters(*, profile: HumanProfile) -> str:
    if profile.goal_intention.strip():
        return profile.goal_intention.strip()
    return (
        f"因为{profile.display_name}需要一个足够稳定的主方向，"
        "让每一次当下努力都能慢慢积累成真正想要的人生。"
    )


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
        existing_profile = self._profile_repository.get_latest_profile()
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

        existing_session = self._onboarding_session_repository.get_latest_session_for_profile(
            profile.profile_id,
        )
        transcript = [profile.goal_intention]
        reasoned_turn = self._resolve_reasoned_turn(
            profile=profile,
            transcript=transcript,
            question_count=1,
            tightened=False,
        )
        session = BuddyOnboardingSessionRecord(
            profile_id=profile.profile_id,
            question_count=1,
            tightened=False,
            status="clarifying",
            next_question=(
                reasoned_turn.next_question.strip()
                if reasoned_turn is not None and reasoned_turn.next_question.strip()
                else _build_buddy_question(
                    profile=profile,
                    question_count=1,
                    transcript=transcript,
                )
            ),
            transcript=transcript,
            candidate_directions=(
                list(reasoned_turn.candidate_directions)
                if reasoned_turn is not None
                else []
            ),
            recommended_direction=(
                reasoned_turn.recommended_direction if reasoned_turn is not None else ""
            ),
            **self._build_reasoned_turn_cache(reasoned_turn),
        )
        if existing_session is not None:
            session = session.model_copy(
                update={
                    "session_id": existing_session.session_id,
                    "created_at": existing_session.created_at,
                    "updated_at": _utc_now(),
                },
            )
        session = self._onboarding_session_repository.upsert_session(session)
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
        candidate_directions = _derive_candidate_directions(
            profile=profile,
            transcript=merged_transcript,
        )
        recommended = candidate_directions[0] if candidate_directions else ""
        reasoned_turn = self._resolve_reasoned_turn(
            profile=profile,
            transcript=merged_transcript,
            question_count=question_count,
            tightened=tightened,
        )
        if reasoned_turn is not None:
            candidate_directions = list(reasoned_turn.candidate_directions) or candidate_directions
            recommended = reasoned_turn.recommended_direction or recommended
        finished = (
            question_count >= self.MAX_QUESTIONS
            or (
                reasoned_turn.finished
                if reasoned_turn is not None
                else self._should_finish_clarification(
                    question_count=question_count,
                    recommended_direction=recommended,
                    transcript=merged_transcript,
                )
            )
        )
        next_question = ""
        if not finished:
            next_question = (
                reasoned_turn.next_question.strip()
                if reasoned_turn is not None and reasoned_turn.next_question.strip()
                else _build_buddy_question(
                    profile=profile,
                    question_count=question_count,
                    tightened=tightened,
                    transcript=merged_transcript,
                )
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
                    **self._build_reasoned_turn_cache(reasoned_turn),
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
        growth_plan = self._resolve_cached_growth_plan(
            session=session,
            selected_direction=normalized,
        )
        if growth_plan is None:
            growth_plan = self._resolve_growth_plan(
                profile=profile,
                transcript=session.transcript,
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
            raise ValueError("capability_action is required")
        growth_target = self._growth_target_repository.upsert_target(
            GrowthTarget(
                profile_id=profile.profile_id,
                primary_direction=normalized,
                final_goal=(
                    growth_plan.final_goal
                    if growth_plan is not None and growth_plan.final_goal.strip()
                    else _derive_final_goal(profile=profile, direction=normalized)
                ),
                why_it_matters=(
                    growth_plan.why_it_matters
                    if growth_plan is not None and growth_plan.why_it_matters.strip()
                    else _derive_why_it_matters(profile=profile)
                ),
                current_cycle_label="Cycle 1",
            ),
        )
        existing_relationship = self._relationship_repository.get_relationship(profile.profile_id)
        relationship = self._relationship_repository.upsert_relationship(
            (existing_relationship or CompanionRelationship(profile_id=profile.profile_id)).model_copy(
                update={
                    "profile_id": profile.profile_id,
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
                        transcript=session.transcript,
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
            growth_plan=growth_plan,
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
                    "selected_direction": normalized,
                    "recommended_direction": session.recommended_direction or normalized,
                    **self._build_growth_plan_cache(
                        selected_direction=normalized,
                        growth_plan=growth_plan,
                    ),
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
            raise ValueError("primary direction must be confirmed before naming Buddy")
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
            raise ValueError(f"Buddy onboarding session '{session_id}' not found")
        return session

    def _require_profile(self, profile_id: str) -> HumanProfile:
        profile = self._profile_repository.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"Human profile '{profile_id}' not found")
        return profile

    def _build_reasoned_turn_cache(
        self,
        reasoned_turn: BuddyOnboardingReasonedTurn | None,
    ) -> dict[str, object]:
        if reasoned_turn is None:
            return {
                "draft_direction": "",
                "draft_final_goal": "",
                "draft_why_it_matters": "",
                "draft_backlog_items": [],
            }
        return {
            "draft_direction": str(reasoned_turn.recommended_direction or "").strip(),
            "draft_final_goal": str(reasoned_turn.final_goal or "").strip(),
            "draft_why_it_matters": str(reasoned_turn.why_it_matters or "").strip(),
            "draft_backlog_items": [
                item.model_dump(mode="json")
                for item in reasoned_turn.backlog_items
                if item.title.strip() and item.summary.strip()
            ][:3],
        }

    def _build_growth_plan_cache(
        self,
        *,
        selected_direction: str,
        growth_plan: BuddyOnboardingGrowthPlan | None,
    ) -> dict[str, object]:
        if growth_plan is None:
            return {
                "draft_direction": "",
                "draft_final_goal": "",
                "draft_why_it_matters": "",
                "draft_backlog_items": [],
            }
        return {
            "draft_direction": selected_direction.strip(),
            "draft_final_goal": str(growth_plan.final_goal or "").strip(),
            "draft_why_it_matters": str(growth_plan.why_it_matters or "").strip(),
            "draft_backlog_items": [
                item.model_dump(mode="json")
                for item in growth_plan.backlog_items
                if item.title.strip() and item.summary.strip()
            ][:3],
        }

    def _resolve_cached_growth_plan(
        self,
        *,
        session: BuddyOnboardingSessionRecord,
        selected_direction: str,
    ) -> BuddyOnboardingGrowthPlan | None:
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
        return BuddyOnboardingGrowthPlan(
            primary_direction=selected_direction.strip(),
            final_goal=final_goal,
            why_it_matters=why_it_matters,
            backlog_items=backlog_items[:3],
        )

    def _resolve_reasoned_turn(
        self,
        *,
        profile: HumanProfile,
        transcript: list[str],
        question_count: int,
        tightened: bool,
    ) -> BuddyOnboardingReasonedTurn | None:
        if self._onboarding_reasoner is None:
            return None
        try:
            return self._onboarding_reasoner.plan_turn(
                profile=profile,
                transcript=transcript,
                question_count=question_count,
                tightened=tightened,
            )
        except BuddyOnboardingReasonerTimeoutError:
            raise
        except TimeoutError:
            raise
        except BuddyOnboardingReasonerUnavailableError:
            raise
        except Exception:
            logger.warning("Buddy onboarding reasoned turn failed.", exc_info=True)
            raise BuddyOnboardingReasonerUnavailableError(
                "Buddy onboarding model failed to return a valid result.",
            ) from None

    def _resolve_growth_plan(
        self,
        *,
        profile: HumanProfile,
        transcript: list[str],
        selected_direction: str,
    ) -> BuddyOnboardingGrowthPlan | None:
        if self._onboarding_reasoner is None:
            return None
        try:
            return self._onboarding_reasoner.build_growth_plan(
                profile=profile,
                transcript=transcript,
                selected_direction=selected_direction,
            )
        except BuddyOnboardingReasonerTimeoutError:
            raise
        except TimeoutError:
            raise
        except BuddyOnboardingReasonerUnavailableError:
            raise
        except Exception:
            logger.warning("Buddy onboarding growth plan failed.", exc_info=True)
            raise BuddyOnboardingReasonerUnavailableError(
                "Buddy onboarding model failed to return a valid result.",
            ) from None

    def _validate_selected_direction(
        self,
        *,
        session: BuddyOnboardingSessionRecord,
        selected_direction: str,
    ) -> str:
        normalized = selected_direction.strip()
        if not normalized:
            raise ValueError("selected_direction is required")
        return normalized

    def _should_finish_clarification(
        self,
        *,
        question_count: int,
        recommended_direction: str,
        transcript: list[str],
    ) -> bool:
        if question_count < 2:
            return False
        normalized_direction = str(recommended_direction or "").strip()
        if not normalized_direction or normalized_direction == _DEFAULT_DIRECTION:
            return False
        source = " ".join(
            _normalize_text(item)
            for item in transcript
            if str(item or "").strip()
        )
        if _contains_any(
            source,
            (
                "stock",
                "stocks",
                "trading",
                "trade",
                "invest",
                "investing",
                "creator",
                "content",
                "writing",
                "design",
                "operator",
                "operations",
                "fitness",
                "health",
                "股票",
                "炒股",
                "投资",
                "交易",
                "内容",
                "创作",
                "写作",
                "设计",
                "运营",
                "健身",
                "健康",
            ),
        ):
            return True
        return question_count > self.TIGHTEN_AFTER

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
                raise ValueError("cannot keep-active without an active domain capability")
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
                raise ValueError("target_domain_id is required for restore-archived")
            archived = self._domain_capability_repository.get_domain_capability(
                resolved_target_domain_id,
            )
            if archived is None or archived.profile_id != profile.profile_id:
                raise ValueError("target_domain_id does not belong to the current profile")
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
        if domain_key == "stocks":
            return "股票"
        if domain_key == "writing":
            return "写作"
        if domain_key == "fitness":
            return "健身"
        return selected_direction.strip() or domain_key

    def _ensure_growth_scaffold(
        self,
        *,
        profile: HumanProfile,
        growth_target: GrowthTarget,
        domain_capability: BuddyDomainCapabilityRecord,
        capability_action: str,
        growth_plan: BuddyOnboardingGrowthPlan | None = None,
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
            execution_core_identity_payload={
                "profile_id": profile.profile_id,
                "primary_direction": growth_target.primary_direction,
                "final_goal": growth_target.final_goal,
            },
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
            summary=f"Buddy onboarding cycle for {profile.display_name}",
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
            role_summary="Runs durable main-brain reviews and routes the next governed move.",
            mission="Review progress, backlog, assignments, and evidence, then route the next governed move.",
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
                    title=f"{profile.display_name} Spider Mesh Morning Review",
                    summary="Morning main-brain review over reports, backlog, assignments, blockers, and next moves.",
                    cron="0 9 * * *",
                    timezone="Asia/Shanghai",
                    dispatch_mode="final",
                ),
                IndustryDraftSchedule(
                    schedule_id=f"{instance_id}-main-brain-evening-review",
                    owner_agent_id=EXECUTION_CORE_AGENT_ID,
                    title=f"{profile.display_name} Spider Mesh Evening Review",
                    summary="Evening main-brain review over execution results, unresolved blockers, and tomorrow routing.",
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
            if seed.dispatch_session_id != control_thread_id:
                seed = seed.model_copy(
                    update={
                        "dispatch_session_id": control_thread_id,
                        "request_payload": {
                            **dict(seed.request_payload),
                            "session_id": control_thread_id,
                            "control_thread_id": control_thread_id,
                        },
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
        growth_plan: BuddyOnboardingGrowthPlan | None = None,
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
        label = profile.display_name.strip() or "Buddy"
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
                    f"Owns the {lane_label} lane for {label} and turns it into concrete progress, "
                    "evidence, and next actions."
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
                        evidence_expectations=[f"{role_id} evidence"],
                    ),
                )
            if dynamic_roles:
                return dynamic_roles
        growth_allowed = buddy_specialist_allowed_capabilities(
            domain_key=domain_key,
            role_id="growth-focus",
        )
        proof_allowed = buddy_specialist_allowed_capabilities(
            domain_key=domain_key,
            role_id="proof-of-work",
        )
        growth_families = buddy_specialist_preferred_capability_families(
            domain_key=domain_key,
            role_id="growth-focus",
        )
        proof_families = buddy_specialist_preferred_capability_families(
            domain_key=domain_key,
            role_id="proof-of-work",
        )
        growth_summary = f"持续确保{label}没有偏离已经确认的长期主方向。"
        proof_summary = f"把{label}当前的主方向尽快变成看得见的证据、作品与推进势能。"
        if domain_key == "writing":
            growth_summary = f"持续确保{label}的写作主线、题材方向和更新节奏没有跑偏。"
            proof_summary = f"把{label}的写作主线尽快变成章节草稿、平台发布证据和作品积累。"
        elif domain_key == "stocks":
            growth_summary = f"持续确保{label}的交易主线、策略边界和复盘节奏没有跑偏。"
            proof_summary = f"把{label}的交易主线尽快变成可验证的观察、记录、复盘与结果证据。"
        return [
            IndustryRoleBlueprint(
                role_id="growth-focus",
                agent_id=f"{instance_id}:growth-focus",
                actor_key=f"{instance_id}:growth-focus",
                name=f"{label} Growth Focus",
                role_name="成长主线",
                role_summary=growth_summary,
                mission=growth_summary,
                goal_kind="growth-focus",
                agent_class="business",
                employment_mode="career",
                activation_mode="persistent",
                suspendable=False,
                reports_to=EXECUTION_CORE_ROLE_ID,
                risk_level="guarded",
                allowed_capabilities=growth_allowed,
                preferred_capability_families=growth_families,
                evidence_expectations=["growth-focus completion note"],
            ),
            IndustryRoleBlueprint(
                role_id="proof-of-work",
                agent_id=f"{instance_id}:proof-of-work",
                actor_key=f"{instance_id}:proof-of-work",
                name=f"{label} Proof Of Work",
                role_name="成果证明",
                role_summary=proof_summary,
                mission=proof_summary,
                goal_kind="proof-of-work",
                agent_class="business",
                employment_mode="career",
                activation_mode="persistent",
                suspendable=False,
                reports_to=EXECUTION_CORE_ROLE_ID,
                risk_level="guarded",
                allowed_capabilities=proof_allowed,
                preferred_capability_families=proof_families,
                evidence_expectations=["proof-of-work artifact"],
            ),
        ]

    def _build_initial_backlog_specs(
        self,
        *,
        profile: HumanProfile,
        growth_target: GrowthTarget,
        lanes: list[object],
        growth_plan: BuddyOnboardingGrowthPlan | None = None,
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
                    lane_id = proof_lane_id if normalized_lane_hint == "proof-of-work" else primary_lane_id
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
        return [
            (
                primary_lane_id,
                "先确认第一份可见证明",
                f"明确第一份什么样的证明，才能说明{profile.display_name}已经开始朝“{growth_target.primary_direction}”真实前进。",
                3,
                f"profile:{profile.profile_id}:proof-point",
            ),
            (
                proof_lane_id,
                "产出第一份可见成长成果",
                f"做出一份真正看得见的成果，让“{growth_target.final_goal}”开始从想象进入证据链。",
                2,
                f"profile:{profile.profile_id}:first-artifact",
            ),
            (
                primary_lane_id,
                "稳定每周推进节奏",
                f"建立一套{profile.display_name}现实可持续、不会很快透支的每周推进节奏。",
                1,
                f"profile:{profile.profile_id}:weekly-rhythm",
            ),
        ]

    def _seed_avoidance_patterns(
        self,
        *,
        profile: HumanProfile,
        transcript: list[str],
        existing: list[str] | None = None,
    ) -> list[str]:
        source = _normalize_text(" ".join([profile.goal_intention, *profile.constraints, *transcript]))
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
    "BuddyClarificationResult",
    "BuddyDirectionConfirmationResult",
    "BuddyDirectionTransitionPreviewResult",
    "BuddyIdentitySubmitResult",
    "BuddyOnboardingService",
]
