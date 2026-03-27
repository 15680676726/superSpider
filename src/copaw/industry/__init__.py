# -*- coding: utf-8 -*-
from __future__ import annotations

from .compiler import (
    canonicalize_industry_draft,
    build_goal_dispatch_context,
    compile_industry_goal_seeds,
    compile_industry_schedule_seeds,
    industry_slug,
    normalize_industry_profile,
)
from .draft_generator import IndustryDraftGenerationError, IndustryDraftGenerator
from .models import (
    IndustryAgentBlueprint,
    IndustryBootstrapInstallAssignmentResult,
    IndustryBootstrapInstallItem,
    IndustryBootstrapInstallResult,
    IndustryBootstrapGoalResult,
    IndustryBootstrapRequest,
    IndustryBootstrapResponse,
    IndustryCapabilityRecommendation,
    IndustryCapabilityRecommendationPack,
    IndustryCapabilityRecommendationSection,
    IndustryExecutionCoreIdentity,
    IndustryDraftGoal,
    IndustryDraftPlan,
    IndustryDraftSchedule,
    IndustryBootstrapScheduleResult,
    IndustryGoalSeed,
    IndustryMainChainGraph,
    IndustryMainChainNode,
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
    normalize_industry_team_topology,
)

__all__ = [
    "IndustryAgentBlueprint",
    "IndustryBootstrapInstallAssignmentResult",
    "IndustryBootstrapInstallItem",
    "IndustryBootstrapInstallResult",
    "IndustryBootstrapGoalResult",
    "IndustryBootstrapRequest",
    "IndustryBootstrapResponse",
    "IndustryCapabilityRecommendation",
    "IndustryCapabilityRecommendationPack",
    "IndustryCapabilityRecommendationSection",
    "IndustryBootstrapService",
    "IndustryExecutionCoreIdentity",
    "IndustryDraftGenerationError",
    "IndustryDraftGenerator",
    "IndustryDraftGoal",
    "IndustryDraftPlan",
    "IndustryDraftSchedule",
    "IndustryBootstrapScheduleResult",
    "IndustryGoalSeed",
    "IndustryMainChainGraph",
    "IndustryMainChainNode",
    "IndustryInstanceDetail",
    "IndustryInstanceSummary",
    "IndustryPreviewRequest",
    "IndustryPreviewResponse",
    "IndustryProfile",
    "IndustryReadinessCheck",
    "IndustryReportSnapshot",
    "IndustryRoleBlueprint",
    "IndustryScheduleSeed",
    "IndustryService",
    "IndustryTeamBlueprint",
    "canonicalize_industry_draft",
    "build_goal_dispatch_context",
    "compile_industry_goal_seeds",
    "compile_industry_schedule_seeds",
    "industry_slug",
    "normalize_industry_profile",
    "normalize_industry_team_topology",
]


def __getattr__(name: str):
    if name in {"IndustryBootstrapService", "IndustryService"}:
        from .service import IndustryBootstrapService, IndustryService

        exports = {
            "IndustryBootstrapService": IndustryBootstrapService,
            "IndustryService": IndustryService,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
