# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from ..agents.skills_hub import HubSkillResult, search_hub_skills
from ..adapters.desktop import get_desktop_mcp_template
from ..capabilities.browser_runtime import BrowserRuntimeService
from ..capabilities.install_templates import get_install_template, list_install_templates
from ..capabilities.mcp_registry import McpRegistryCatalog
from ..capabilities.remote_skill_catalog import (
    CuratedSkillCatalogEntry,
    search_curated_skill_catalog,
)
from ..config import load_config
from ..config.config import MCPClientConfig
from ..evidence import EvidenceLedger
from ..goals import GoalService
from ..kernel.persistence import decode_kernel_task_metadata
from ..kernel.surface_routing import (
    BROWSER_DIRECT_TEXT_HINTS as _BROWSER_DIRECT_TEXT_HINTS,
    DESKTOP_DIRECT_TEXT_HINTS as _DESKTOP_DIRECT_TEXT_HINTS,
    FILE_DIRECT_TEXT_HINTS as _FILE_DIRECT_TEXT_HINTS,
    infer_requested_execution_surfaces,
    resolve_execution_surface_support,
)
from ..state import (
    AgentProfileOverrideRecord,
    AgentRuntimeRecord,
    AgentThreadBindingRecord,
    AgentReportRecord,
    GoalOverrideRecord,
    GoalRecord,
    IndustryInstanceRecord,
    AssignmentRecord,
    BacklogItemRecord,
    OperatingCycleRecord,
    OperatingLaneRecord,
    SQLiteStateStore,
    StrategyMemoryRecord,
    TaskRecord,
    TaskRuntimeRecord,
)
from ..state.main_brain_service import (
    AgentReportService,
    AssignmentService,
    BacklogService,
    OperatingCycleService,
    OperatingLaneService,
)
from ..state.strategy_memory_service import compact_strategy_payload
from ..state.repositories import (
    SqliteAgentCheckpointRepository,
    SqliteAgentLeaseRepository,
    SqliteAgentMailboxRepository,
    SqliteAgentProfileOverrideRepository,
    SqliteAgentReportRepository,
    SqliteAgentRuntimeRepository,
    SqliteAssignmentRepository,
    SqliteAgentThreadBindingRepository,
    SqliteBacklogItemRepository,
    SqliteGoalOverrideRepository,
    SqliteIndustryInstanceRepository,
    SqliteOperatingCycleRepository,
    SqliteOperatingLaneRepository,
    SqlitePredictionCaseRepository,
    SqlitePredictionRecommendationRepository,
    SqlitePredictionReviewRepository,
    SqlitePredictionScenarioRepository,
    SqlitePredictionSignalRepository,
    SqliteScheduleRepository,
    SqliteStrategyMemoryRepository,
    SqliteWorkflowRunRepository,
)
from .compiler import (
    canonicalize_industry_draft,
    build_goal_dispatch_context,
    compile_industry_goal_seeds,
    compile_industry_schedule_seeds,
    industry_slug,
    normalize_industry_profile,
)
from ..media import MediaAnalysisRequest
from ..media.models import MediaAnalysisSummary, MediaSourceSpec
from .chat_writeback import ChatWritebackPlan, build_chat_writeback_plan
from .draft_generator import IndustryDraftGenerator
from .prompting import build_industry_execution_prompt, infer_industry_task_mode
from .identity import (
    EXECUTION_CORE_AGENT_ID,
    EXECUTION_CORE_LEGACY_NAMES,
    EXECUTION_CORE_NAME,
    EXECUTION_CORE_ROLE_ID,
    is_execution_core_agent_id,
    is_execution_core_reference,
    is_execution_core_role_id,
    normalize_industry_role_id,
)
from .models import (
    IndustryBootstrapInstallAssignmentResult,
    IndustryBootstrapInstallItem,
    IndustryBootstrapInstallResult,
    IndustryBootstrapGoalResult,
    IndustryBootstrapRequest,
    IndustryBootstrapResponse,
    IndustryCapabilityRecommendation,
    IndustryCapabilityRecommendationPack,
    IndustryCapabilityRecommendationSection,
    IndustryDraftGoal,
    IndustryDraftPlan,
    IndustryDraftSchedule,
    IndustryBootstrapScheduleResult,
    IndustryExecutionCoreIdentity,
    IndustryMainChainGraph,
    IndustryMainChainNode,
    IndustryExecutionSummary,
    IndustryInstanceDetail,
    IndustryInstanceSummary,
    IndustryPreviewRequest,
    IndustryPreviewResponse,
    IndustryProfile,
    IndustryReadinessCheck,
    IndustryReportSnapshot,
    IndustryRoleBlueprint,
    IndustryScheduleSeed,
    IndustryTeamBlueprint,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IndustryServiceRuntimeBindings:
    operating_lane_repository: SqliteOperatingLaneRepository | None = None
    backlog_item_repository: SqliteBacklogItemRepository | None = None
    operating_cycle_repository: SqliteOperatingCycleRepository | None = None
    assignment_repository: SqliteAssignmentRepository | None = None
    agent_report_repository: SqliteAgentReportRepository | None = None
    agent_runtime_repository: SqliteAgentRuntimeRepository | None = None
    agent_thread_binding_repository: SqliteAgentThreadBindingRepository | None = None
    schedule_repository: SqliteScheduleRepository | None = None
    agent_mailbox_repository: SqliteAgentMailboxRepository | None = None
    agent_checkpoint_repository: SqliteAgentCheckpointRepository | None = None
    agent_lease_repository: SqliteAgentLeaseRepository | None = None
    strategy_memory_repository: SqliteStrategyMemoryRepository | None = None
    workflow_run_repository: SqliteWorkflowRunRepository | None = None
    prediction_case_repository: SqlitePredictionCaseRepository | None = None
    prediction_scenario_repository: SqlitePredictionScenarioRepository | None = None
    prediction_signal_repository: SqlitePredictionSignalRepository | None = None
    prediction_recommendation_repository: SqlitePredictionRecommendationRepository | None = None
    prediction_review_repository: SqlitePredictionReviewRepository | None = None
    operating_lane_service: OperatingLaneService | None = None
    backlog_service: BacklogService | None = None
    operating_cycle_service: OperatingCycleService | None = None
    assignment_service: AssignmentService | None = None
    agent_report_service: AgentReportService | None = None
    browser_runtime_service: BrowserRuntimeService | None = None


def build_industry_service_runtime_bindings(
    *,
    state_store: SQLiteStateStore | None = None,
    operating_lane_repository: SqliteOperatingLaneRepository | None = None,
    backlog_item_repository: SqliteBacklogItemRepository | None = None,
    operating_cycle_repository: SqliteOperatingCycleRepository | None = None,
    assignment_repository: SqliteAssignmentRepository | None = None,
    agent_report_repository: SqliteAgentReportRepository | None = None,
    agent_runtime_repository: SqliteAgentRuntimeRepository | None = None,
    agent_thread_binding_repository: SqliteAgentThreadBindingRepository | None = None,
    schedule_repository: SqliteScheduleRepository | None = None,
    agent_mailbox_repository: SqliteAgentMailboxRepository | None = None,
    agent_checkpoint_repository: SqliteAgentCheckpointRepository | None = None,
    agent_lease_repository: SqliteAgentLeaseRepository | None = None,
    strategy_memory_repository: SqliteStrategyMemoryRepository | None = None,
    workflow_run_repository: SqliteWorkflowRunRepository | None = None,
    prediction_case_repository: SqlitePredictionCaseRepository | None = None,
    prediction_scenario_repository: SqlitePredictionScenarioRepository | None = None,
    prediction_signal_repository: SqlitePredictionSignalRepository | None = None,
    prediction_recommendation_repository: SqlitePredictionRecommendationRepository | None = None,
    prediction_review_repository: SqlitePredictionReviewRepository | None = None,
    operating_lane_service: OperatingLaneService | None = None,
    backlog_service: BacklogService | None = None,
    operating_cycle_service: OperatingCycleService | None = None,
    assignment_service: AssignmentService | None = None,
    agent_report_service: AgentReportService | None = None,
    browser_runtime_service: BrowserRuntimeService | None = None,
    memory_retain_service: object | None = None,
) -> IndustryServiceRuntimeBindings:
    # `state_store` remains in the signature for compatibility with older
    # bootstrapping sites, but runtime bindings must now be assembled from
    # explicit repositories/services only. This keeps IndustryService on a
    # single injected access path instead of silently constructing parallel
    # repository graphs from the store.
    _ = state_store
    lane_repository = operating_lane_repository
    backlog_repository = backlog_item_repository
    cycle_repository = operating_cycle_repository
    assignment_repo = assignment_repository
    report_repository = agent_report_repository
    runtime_repository = agent_runtime_repository
    thread_binding_repository = agent_thread_binding_repository
    schedules = schedule_repository
    mailbox_repository = agent_mailbox_repository
    checkpoint_repository = agent_checkpoint_repository
    lease_repository = agent_lease_repository
    strategy_repository = strategy_memory_repository
    workflow_repository = workflow_run_repository
    case_repository = prediction_case_repository
    scenario_repository = prediction_scenario_repository
    signal_repository = prediction_signal_repository
    recommendation_repository = prediction_recommendation_repository
    review_repository = prediction_review_repository
    lane_service = operating_lane_service or (
        OperatingLaneService(repository=lane_repository)
        if lane_repository is not None
        else None
    )
    backlog_runtime_service = backlog_service or (
        BacklogService(repository=backlog_repository)
        if backlog_repository is not None
        else None
    )
    cycle_service = operating_cycle_service or (
        OperatingCycleService(repository=cycle_repository)
        if cycle_repository is not None
        else None
    )
    assignment_runtime_service = assignment_service or (
        AssignmentService(repository=assignment_repo)
        if assignment_repo is not None
        else None
    )
    report_service = agent_report_service or (
        AgentReportService(
            repository=report_repository,
            memory_retain_service=memory_retain_service,
        )
        if report_repository is not None
        else None
    )
    browser_service = browser_runtime_service
    return IndustryServiceRuntimeBindings(
        operating_lane_repository=lane_repository,
        backlog_item_repository=backlog_repository,
        operating_cycle_repository=cycle_repository,
        assignment_repository=assignment_repo,
        agent_report_repository=report_repository,
        agent_runtime_repository=runtime_repository,
        agent_thread_binding_repository=thread_binding_repository,
        schedule_repository=schedules,
        agent_mailbox_repository=mailbox_repository,
        agent_checkpoint_repository=checkpoint_repository,
        agent_lease_repository=lease_repository,
        strategy_memory_repository=strategy_repository,
        workflow_run_repository=workflow_repository,
        prediction_case_repository=case_repository,
        prediction_scenario_repository=scenario_repository,
        prediction_signal_repository=signal_repository,
        prediction_recommendation_repository=recommendation_repository,
        prediction_review_repository=review_repository,
        operating_lane_service=lane_service,
        backlog_service=backlog_runtime_service,
        operating_cycle_service=cycle_service,
        assignment_service=assignment_runtime_service,
        agent_report_service=report_service,
        browser_runtime_service=browser_service,
    )

_REMOTE_RECOMMENDATION_ROLE_LIMIT = 12
_REMOTE_RECOMMENDATION_MATCHES_PER_ROLE = 3
_HUB_RECOMMENDATION_MAX_ITEMS = 12
_CURATED_RECOMMENDATION_MAX_ITEMS = 10
_CURATED_RECOMMENDATION_MATCHES_PER_ROLE = 3
_HUB_RECOMMENDATION_MATCHES_PER_ROLE = 4
_STANDARD_RECOMMENDATION_MAX_TOTAL = 16
_ROLE_CAPABILITY_MAX_SELECTED_FAMILIES = 2
_ROLE_CAPABILITY_EXPANDED_FAMILY_LIMIT = 4
_ROLE_CAPABILITY_SECONDARY_MIN_SCORE = 12
_ROLE_CAPABILITY_SECONDARY_MIN_RATIO = 0.6
_ROLE_CAPABILITY_SECONDARY_MAX_GAP = 8
_RECOMMENDATION_GROUP_PRIORITY = {
    "system-baseline": 0,
    "execution-core": 1,
    "shared": 2,
    "role-specific": 3,
}
_RECOMMENDATION_FAMILY_BUDGETS = {
    "browser": 2,
    "desktop": 1,
    "workflow": 2,
    "research": 2,
    "content": 2,
    "crm": 2,
    "data": 2,
    "email": 1,
    "image": 1,
    "github": 1,
}
_REMOTE_DOMAIN_GUARDRAILS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "finance-trading",
        (
            "stock trading",
            "stock market",
            "stocks",
            "securities",
            "equity trading",
            "trading bot",
            "trading signal",
            "crypto",
            "cryptocurrency",
            "forex",
            "investment",
            "investing",
            "股票",
            "炒股",
            "证券",
            "基金",
            "期货",
            "外汇",
            "投资",
            "量化交易",
        ),
    ),
    (
        "medical",
        (
            "clinical",
            "patient",
            "medical diagnosis",
            "medical record",
            "pharmacy",
            "诊断",
            "患者",
            "病历",
            "处方",
            "医疗",
            "医药",
        ),
    ),
    (
        "legal",
        (
            "legal brief",
            "legal research",
            "contract review",
            "attorney",
            "law firm",
            "律师",
            "法务",
            "法律",
            "合同审查",
            "诉讼",
        ),
    ),
)
_GENERIC_BROWSER_REMOTE_TERMS = (
    "browser",
    "browser automation",
    "web automation",
    "web workflow",
    "login",
    "form",
    "dashboard",
    "browser use",
    "web page",
    "website",
    "网页",
    "浏览器",
    "表单",
    "登录",
)

_EXECUTION_CORE_NAME = EXECUTION_CORE_NAME
_EXECUTION_CORE_SUMMARY = (
    f"作为团队可见的{_EXECUTION_CORE_NAME}：负责理解目标、拆解计划、分派具体子任务给专业协作角色、监督执行并核验证据；发现缺岗位时负责补位、改派或发起治理提案，不亲自承担叶子执行。"
)
_EXECUTION_CORE_MISSION = (
    "将当前行业简报拆解为带明确执行位的子任务闭环，回收证据与状态；缺少合适协作角色时创建临时位或发起长期岗位提案，自己不直接执行叶子动作。"
)

_DESKTOP_SURFACE_HINTS: tuple[tuple[str, str], ...] = (
    ("窗口", "窗口"),
    ("键盘", "键盘"),
    ("鼠标", "鼠标"),
    ("window focus", "window focus"),
    ("keyboard", "keyboard"),
    ("mouse", "mouse"),
)

_DESKTOP_ACTION_HINTS: tuple[tuple[str, str], ...] = (
    ("点击", "点击"),
    ("输入", "输入"),
    ("打字", "打字"),
    ("快捷键", "快捷键"),
    ("热键", "热键"),
    ("切换", "切换"),
    ("发送", "发送"),
    ("click", "click"),
    ("type", "type"),
    ("typing", "typing"),
    ("keypress", "keypress"),
    ("focus", "focus"),
)


@dataclass(slots=True)
class _IndustryPlan:
    profile: IndustryProfile
    owner_scope: str
    draft: IndustryDraftPlan
    goal_seeds: list
    schedule_seeds: list
    recommendation_pack: IndustryCapabilityRecommendationPack
    readiness_checks: list[IndustryReadinessCheck]
    media_analyses: list[MediaAnalysisSummary]
    media_analysis_ids: list[str]
    media_warnings: list[str]


@dataclass(slots=True)
class _ActorMatchResult:
    role: IndustryRoleBlueprint
    match_kind: str
    semantic_drift: bool = False
    previous_fingerprint: str | None = None
    current_fingerprint: str | None = None


@dataclass(slots=True)
class _InstanceLearningDeletionPlan:
    proposal_ids: list[str]
    patch_ids: list[str]
    growth_ids: list[str]
    acquisition_proposal_ids: list[str]
    install_binding_plan_ids: list[str]
    onboarding_run_ids: list[str]
    evidence_ids: list[str]

__all__ = [name for name in globals() if not name.startswith("__")]
