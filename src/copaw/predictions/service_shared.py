# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha1
import json
import re
import sys
from typing import Any

from ..capabilities.remote_skill_contract import (
    RemoteSkillCandidate,
    build_remote_skill_preflight,
    resolve_candidate_capability_ids,
    search_allowlisted_remote_skill_candidates,
)
from ..evidence import EvidenceLedger
from ..industry.identity import EXECUTION_CORE_AGENT_ID
from ..industry.models import (
    IndustryDraftGoal,
    IndustryProfile,
    IndustryRoleBlueprint,
    IndustryTeamBlueprint,
)
from ..kernel import KernelTask
from ..state import (
    GoalRecord,
    PredictionCaseRecord,
    PredictionRecommendationRecord,
    PredictionReviewRecord,
    PredictionScenarioRecord,
    PredictionSignalRecord,
    TaskRecord,
    WorkflowRunRecord,
)
from ..state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteGoalRepository,
    SqliteIndustryInstanceRepository,
    SqlitePredictionCaseRepository,
    SqlitePredictionRecommendationRepository,
    SqlitePredictionReviewRepository,
    SqlitePredictionScenarioRepository,
    SqlitePredictionSignalRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkflowRunRepository,
)
from ..state.strategy_memory_service import resolve_strategy_payload
from .models import (
    PredictionCapabilityOptimizationItem,
    PredictionCapabilityOptimizationOverview,
    PredictionCapabilityOptimizationSummary,
    PredictionCaseDetail,
    PredictionCaseSummary,
    PredictionCreateRequest,
    PredictionRecommendationExecutionResponse,
    PredictionRecommendationView,
    PredictionReviewCreateRequest,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(*values: object) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                items.append(normalized)
            continue
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, str):
                continue
            normalized = entry.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                items.append(normalized)
    return items


def _safe_dict(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: object | None) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _window_from_days(days: int) -> str:
    if days <= 1:
        return "daily"
    if days <= 7:
        return "weekly"
    return "monthly"


_ACTIVE_TEAM_ROLE_GAP_STATUSES = frozenset(
    {"proposed", "queued", "throttled", "waiting-confirm"},
)
_ACTIVE_TEAM_ROLE_GAP_STATUS_PRIORITY = {
    "waiting-confirm": 0,
    "proposed": 1,
    "queued": 2,
    "throttled": 3,
}


def _metric_label(key: str) -> str:
    mapping = {
        "task_success_rate": "任务成功率",
        "manual_intervention_rate": "人工介入率",
        "exception_rate": "异常率",
        "patch_apply_rate": "补丁应用率",
        "rollback_rate": "回滚率",
        "active_task_load": "人均活跃任务负载",
        "prediction_hit_rate": "预测命中率",
        "recommendation_adoption_rate": "建议采纳率",
        "recommendation_execution_benefit": "建议执行收益",
    }
    normalized = key.strip()
    return mapping.get(normalized, normalized.replace("_", " "))


def _skill_capability_id(skill_name: str) -> str:
    return f"skill:{skill_name.strip()}"


def _ratio_strength(value: float, *, threshold: float, span: float) -> float:
    if span <= 0:
        return 0.0
    return max(0.0, min(1.0, round((value - threshold) / span, 3)))


def _route_prediction(case_id: str) -> str:
    return f"/api/predictions/{case_id}"


def _stable_prediction_fingerprint(payload: dict[str, Any]) -> str:
    try:
        normalized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    except TypeError:
        normalized = repr(sorted(payload.items(), key=lambda item: str(item[0])))
    return sha1(normalized.encode("utf-8")).hexdigest()[:16]


def _get_prediction_facade_attr(name: str, default: object) -> object:
    facade = sys.modules.get("copaw.predictions.service")
    if facade is None:
        return default
    return getattr(facade, name, default)


_TEAM_GAP_FAMILY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "image",
        (
            "visual",
            "design",
            "creative",
            "image",
            "images",
            "photo",
            "asset",
            "assets",
            "banner",
            "poster",
            "thumbnail",
            "图片",
            "图像",
            "视觉",
            "设计",
            "美工",
            "素材",
            "海报",
            "封面",
            "主图",
            "详情图",
        ),
    ),
    (
        "content",
        (
            "content",
            "copy",
            "writing",
            "script",
            "article",
            "文案",
            "内容",
            "脚本",
            "写作",
            "稿件",
        ),
    ),
    (
        "research",
        (
            "research",
            "analysis",
            "monitor",
            "insight",
            "benchmark",
            "trend",
            "competitor",
            "调研",
            "研究",
            "分析",
            "监控",
            "竞品",
            "情报",
            "趋势",
        ),
    ),
    (
        "data",
        (
            "data",
            "report",
            "analytics",
            "dashboard",
            "excel",
            "sheet",
            "数据",
            "报表",
            "分析",
            "看板",
            "表格",
        ),
    ),
    (
        "crm",
        (
            "customer",
            "crm",
            "service",
            "support",
            "follow-up",
            "follow up",
            "lead",
            "客户",
            "客服",
            "跟进",
            "线索",
            "售后",
        ),
    ),
    (
        "workflow",
        (
            "workflow",
            "process",
            "automation",
            "sop",
            "runbook",
            "planning",
            "流程",
            "自动化",
            "编排",
            "规划",
            "方案",
        ),
    ),
)

_TEAM_GAP_ROLE_TEMPLATES: dict[str, dict[str, Any]] = {
    "image": {
        "role_id": "visual-design",
        "role_name": "视觉设计专员",
        "role_summary": "负责图片、视觉素材、创意包装与出图交付。",
        "mission": "补齐当前执行链里的视觉与素材产出缺口，并把结果沉淀为可复用资产。",
        "goal_kind": "visual-design",
        "preferred_capability_families": ["image", "content"],
        "evidence_expectations": ["设计简报", "素材交付", "版本证明"],
        "agent_class": "business",
    },
    "content": {
        "role_id": "content-ops",
        "role_name": "内容策划专员",
        "role_summary": "负责内容策划、文案产出与内容发布前准备。",
        "mission": "把当前经营要求转成可上线、可复盘的内容资产。",
        "goal_kind": "content-ops",
        "preferred_capability_families": ["content"],
        "evidence_expectations": ["内容提纲", "文案版本", "发布建议"],
        "agent_class": "business",
    },
    "research": {
        "role_id": "researcher",
        "role_name": "行业研究员",
        "role_summary": "负责收集行业、竞品、用户与环境信号。",
        "mission": "持续为执行中枢提供高信号研究结论与监测结果。",
        "goal_kind": "researcher",
        "preferred_capability_families": ["research", "data"],
        "evidence_expectations": ["研究摘要", "监测信号", "结论简报"],
        "agent_class": "system",
    },
    "data": {
        "role_id": "data-analyst",
        "role_name": "数据分析专员",
        "role_summary": "负责指标拆解、报表复盘与异常定位。",
        "mission": "把运行结果转成可执行的数据诊断与优化建议。",
        "goal_kind": "data-analyst",
        "preferred_capability_families": ["data"],
        "evidence_expectations": ["数据报表", "异常定位", "复盘建议"],
        "agent_class": "business",
    },
    "crm": {
        "role_id": "customer-success",
        "role_name": "客户协同专员",
        "role_summary": "负责客户响应、线索跟进与服务闭环。",
        "mission": "补齐当前经营链里的客户协同与反馈跟进缺口。",
        "goal_kind": "customer-success",
        "preferred_capability_families": ["crm", "content"],
        "evidence_expectations": ["客户记录", "跟进摘要", "问题闭环"],
        "agent_class": "business",
    },
    "workflow": {
        "role_id": "workflow-specialist",
        "role_name": "流程执行专员",
        "role_summary": "负责把规划拆成可执行 SOP、流程节点与协同动作。",
        "mission": "让当前执行链从抽象规划落到稳定流程与标准动作。",
        "goal_kind": "workflow-specialist",
        "preferred_capability_families": ["workflow"],
        "evidence_expectations": ["流程方案", "执行清单", "节点复盘"],
        "agent_class": "business",
    },
}


@dataclass(slots=True)
class _FactPack:
    scope_type: str
    scope_id: str | None
    report: dict[str, Any]
    performance: dict[str, Any]
    goals: list[GoalRecord]
    tasks: list[TaskRecord]
    workflows: list[WorkflowRunRecord]
    agents: list[Any]
    capabilities: list[Any]
    strategy: dict[str, Any] | None

__all__ = [name for name in globals() if not name.startswith("__")]
