# -*- coding: utf-8 -*-
"""Pure Buddy domain-capability helpers."""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable

from ..state.models_buddy import BuddyEvolutionStage


@dataclass(slots=True)
class BuddyDomainTransitionPreview:
    suggestion_kind: str
    recommended_action: str
    selected_domain_key: str
    reason_summary: str
    current_domain: dict[str, object] | None = None
    archived_matches: list[dict[str, object]] | None = None


@dataclass(slots=True)
class BuddyDomainCapabilitySignals:
    has_active_instance: bool
    lane_count: int
    backlog_count: int
    cycle_count: int
    completed_cycle_count: int
    has_current_cycle: bool
    assignment_count: int
    active_assignment_count: int
    completed_assignment_count: int
    report_count: int
    completed_report_count: int
    evidence_count: int


@dataclass(slots=True)
class BuddyDomainCapabilityMetrics:
    strategy_score: int
    execution_score: int
    evidence_score: int
    stability_score: int
    capability_score: int
    evolution_stage: BuddyEvolutionStage
    knowledge_value: int
    skill_value: int
    completed_support_runs: int
    completed_assisted_closures: int
    evidence_count: int
    report_count: int


_CAPABILITY_STAGE_BANDS: tuple[tuple[int, BuddyEvolutionStage], ...] = (
    (80, "signature"),
    (60, "seasoned"),
    (40, "capable"),
    (20, "bonded"),
    (0, "seed"),
)
_POINT_STAGE_BANDS: tuple[tuple[int, BuddyEvolutionStage], ...] = (
    (200, "signature"),
    (100, "seasoned"),
    (40, "capable"),
    (20, "bonded"),
    (0, "seed"),
)
_EVOLUTION_STAGE_ORDER: tuple[BuddyEvolutionStage, ...] = (
    "seed",
    "bonded",
    "capable",
    "seasoned",
    "signature",
)

_DOMAIN_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "stocks",
        (
            "股票",
            "炒股",
            "证券",
            "基金",
            "投资",
            "交易",
            "quant",
            "trading",
            "trade",
            "stock",
            "stocks",
            "invest",
            "investing",
        ),
    ),
    (
        "writing",
        (
            "写作",
            "写文",
            "文章",
            "内容",
            "创作",
            "作者",
            "文稿",
            "writer",
            "writing",
            "content",
            "creator",
        ),
    ),
    (
        "fitness",
        (
            "健身",
            "运动",
            "锻炼",
            "健康",
            "减脂",
            "体能",
            "fitness",
            "health",
            "exercise",
            "training",
            "workout",
        ),
    ),
)

_BUDDY_SPECIALIST_BASE_ALLOWED_CAPABILITIES: tuple[str, ...] = (
    "system:dispatch_query",
    "tool:get_current_time",
    "tool:read_file",
    "tool:write_file",
    "tool:edit_file",
)

_BUDDY_SPECIALIST_ROLE_FAMILIES: dict[str, tuple[str, ...]] = {
    "growth-focus": ("planning", "coordination", "research", "data"),
    "proof-of-work": ("execution", "evidence", "browser", "workflow"),
}

_BUDDY_ROLE_BROWSER_HINTS: tuple[str, ...] = (
    "proof",
    "publish",
    "publishing",
    "platform",
    "content",
    "listing",
    "launch",
    "browser",
)

_BUDDY_ROLE_FAMILY_HINTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("research", "analysis", "market", "insight", "strategy", "plan"),
        ("planning", "coordination", "research", "data"),
    ),
    (
        ("publish", "publishing", "platform", "content", "listing", "copy", "launch"),
        ("execution", "evidence", "content", "browser", "workflow"),
    ),
    (
        ("ops", "operations", "execution", "execute", "delivery", "proof"),
        ("execution", "evidence", "workflow", "browser"),
    ),
)

_DOMAIN_FAMILY_HINTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        (
            "writer",
            "writing",
            "creator",
            "content",
            "novel",
            "story",
            "publish",
            "writing",
            "鍐欎綔",
            "鍐呭",
            "鍒涗綔",
            "灏忚",
            "鍙戝竷",
            "骞冲彴",
        ),
        ("content", "browser", "workflow"),
    ),
    (
        (
            "stock",
            "stocks",
            "trade",
            "trading",
            "invest",
            "investing",
            "quant",
            "market",
            "research",
            "analysis",
            "data",
            "鑲＄エ",
            "鐐掕偂",
            "浜ゆ槗",
            "鎶曡祫",
            "琛屾儏",
            "鐮旂┒",
            "澶嶇洏",
        ),
        ("research", "data"),
    ),
    (
        (
            "fitness",
            "health",
            "habit",
            "routine",
            "workflow",
            "operations",
            "operate",
            "system",
            "杩愯惀",
            "绯荤粺",
            "娴佺▼",
            "鍋ュ悍",
            "鍋ヨ韩",
            "涔犳儻",
        ),
        ("workflow", "data"),
    ),
)


def _role_prefers_browser(role_id: str) -> bool:
    return any(token in role_id for token in _BUDDY_ROLE_BROWSER_HINTS)


def _infer_specialist_families(*, domain_key: str, role_id: str) -> list[str]:
    inferred = list(_BUDDY_SPECIALIST_ROLE_FAMILIES.get(role_id, ()))
    for tokens, families in _BUDDY_ROLE_FAMILY_HINTS:
        if any(token in role_id for token in tokens):
            inferred.extend(families)
    normalized_domain = _normalize_domain_text(domain_key)
    for tokens, families in _DOMAIN_FAMILY_HINTS:
        if any(token in normalized_domain for token in tokens):
            inferred.extend(families)
    if not inferred:
        if _role_prefers_browser(role_id):
            inferred.extend(("execution", "evidence", "browser"))
        else:
            inferred.extend(("planning", "coordination"))
    return list(dict.fromkeys(inferred))


def _clamp_capability_score(score: int) -> int:
    return max(0, min(100, int(score)))


def _normalize_points(points: int) -> int:
    return max(0, int(points))


def stage_from_points(points: int) -> BuddyEvolutionStage:
    normalized = _normalize_points(points)
    for minimum, stage in _POINT_STAGE_BANDS:
        if normalized >= minimum:
            return stage
    return "seed"


def can_promote_to_stage(
    stage: BuddyEvolutionStage,
    *,
    points: int,
    settled_closure_count: int,
    independent_outcome_count: int,
    recent_completion_rate: float,
    recent_execution_error_rate: float,
    distinct_settled_cycle_count: int,
) -> bool:
    normalized_points = _normalize_points(points)
    if stage == "seed":
        return normalized_points >= 0
    if stage == "bonded":
        return normalized_points >= 20
    if stage == "capable":
        return normalized_points >= 40 and int(settled_closure_count) >= 1
    if stage == "seasoned":
        return normalized_points >= 100 and int(distinct_settled_cycle_count) >= 3
    return (
        normalized_points >= 200
        and int(independent_outcome_count) >= 10
        and float(recent_completion_rate) >= 0.92
        and float(recent_execution_error_rate) <= 0.03
    )


def resolve_stage_transition(
    *,
    previous_stage: BuddyEvolutionStage,
    points: int,
    settled_closure_count: int,
    independent_outcome_count: int,
    recent_completion_rate: float,
    recent_execution_error_rate: float,
    distinct_settled_cycle_count: int,
) -> BuddyEvolutionStage:
    target_stage = "seed"
    highest_stage = stage_from_points(points)
    highest_rank = _EVOLUTION_STAGE_ORDER.index(highest_stage)
    for rank in range(highest_rank, -1, -1):
        candidate = _EVOLUTION_STAGE_ORDER[rank]
        if can_promote_to_stage(
            candidate,
            points=points,
            settled_closure_count=settled_closure_count,
            independent_outcome_count=independent_outcome_count,
            recent_completion_rate=recent_completion_rate,
            recent_execution_error_rate=recent_execution_error_rate,
            distinct_settled_cycle_count=distinct_settled_cycle_count,
        ):
            target_stage = candidate
            break
    previous_rank = _EVOLUTION_STAGE_ORDER.index(previous_stage)
    target_rank = _EVOLUTION_STAGE_ORDER.index(target_stage)
    if target_rank < previous_rank - 1:
        return _EVOLUTION_STAGE_ORDER[previous_rank - 1]
    return target_stage


def progress_to_next_stage(points: int) -> int:
    normalized = _normalize_points(points)
    if normalized >= 200:
        return 100
    thresholds = (0, 20, 40, 100, 200)
    lower_bound = thresholds[0]
    upper_bound = thresholds[1]
    for current, next_threshold in zip(thresholds, thresholds[1:]):
        if normalized < next_threshold:
            lower_bound = current
            upper_bound = next_threshold
            break
    span = max(1, upper_bound - lower_bound)
    return min(100, max(0, ((normalized - lower_bound) * 100) // span))


def capability_stage_from_score(score: int) -> BuddyEvolutionStage:
    normalized = _clamp_capability_score(score)
    for minimum, stage in _CAPABILITY_STAGE_BANDS:
        if normalized >= minimum:
            return stage
    return "seed"


def progress_to_next_capability_stage(score: int) -> int:
    normalized = _clamp_capability_score(score)
    if normalized >= 80:
        return 100
    lower_bound = 0
    upper_bound = 20
    for minimum, _stage in reversed(_CAPABILITY_STAGE_BANDS):
        if normalized >= minimum:
            lower_bound = minimum
            upper_bound = minimum + 20
    span = max(1, upper_bound - lower_bound)
    return min(100, max(0, ((normalized - lower_bound) * 100) // span))


def derive_capability_metrics(
    signals: BuddyDomainCapabilitySignals,
) -> BuddyDomainCapabilityMetrics:
    strategy_score = _clamp_metric(
        (3 if signals.has_active_instance else 0)
        + (3 if signals.lane_count > 0 else 0)
        + (2 if signals.backlog_count > 0 else 0)
        + (4 if signals.has_current_cycle else 0)
        + (3 if signals.assignment_count > 0 else 0)
        + (1 if signals.lane_count >= 2 else 0)
        + (1 if signals.backlog_count >= 3 else 0)
        + (1 if signals.assignment_count >= 3 else 0)
        + (1 if signals.cycle_count >= 2 else 0),
        ceiling=25,
    )
    execution_score = _clamp_metric(
        min(18, max(0, signals.completed_assignment_count) * 6)
        + min(8, max(0, signals.completed_report_count) * 4),
        ceiling=35,
    )
    evidence_score = _clamp_metric(
        min(12, max(0, signals.evidence_count) * 4)
        + min(8, max(0, signals.report_count) * 2),
        ceiling=20,
    )
    stability_score = _clamp_metric(
        (6 if signals.completed_cycle_count > 0 else 0)
        + min(6, max(0, signals.completed_cycle_count - 1) * 3)
        + (4 if signals.completed_assignment_count >= 2 else 0)
        + (4 if signals.completed_report_count >= 2 else 0)
        + (4 if signals.evidence_count >= 3 else 0),
        ceiling=20,
    )
    capability_score = _clamp_capability_score(
        strategy_score + execution_score + evidence_score + stability_score,
    )
    return BuddyDomainCapabilityMetrics(
        strategy_score=strategy_score,
        execution_score=execution_score,
        evidence_score=evidence_score,
        stability_score=stability_score,
        capability_score=capability_score,
        evolution_stage=capability_stage_from_score(capability_score),
        knowledge_value=min(
            100,
            strategy_score * 4 + evidence_score * 2 + stability_score,
        ),
        skill_value=min(100, execution_score * 3 + stability_score * 2),
        completed_support_runs=max(0, signals.completed_assignment_count),
        completed_assisted_closures=max(0, signals.completed_report_count),
        evidence_count=max(0, signals.evidence_count),
        report_count=max(0, signals.report_count),
    )


def derive_buddy_domain_key(direction: str) -> str:
    normalized = _normalize_domain_text(direction)
    for key, tokens in _DOMAIN_RULES:
        if any(token in normalized for token in tokens):
            return key
    collapsed = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "-", normalized)
    collapsed = collapsed.strip("-")
    return collapsed or "general"


def buddy_specialist_allowed_capabilities(*, domain_key: str, role_id: str) -> list[str]:
    del domain_key
    capabilities = list(_BUDDY_SPECIALIST_BASE_ALLOWED_CAPABILITIES)
    normalized_role_id = role_id.strip().lower()
    if (
        normalized_role_id == "proof-of-work"
        or _role_prefers_browser(normalized_role_id)
    ):
        capabilities.append("tool:browser_use")
    return list(dict.fromkeys(capabilities))


def buddy_specialist_preferred_capability_families(
    *,
    domain_key: str,
    role_id: str,
) -> list[str]:
    normalized_role_id = role_id.strip().lower()
    return _infer_specialist_families(
        domain_key=domain_key.strip().lower(),
        role_id=normalized_role_id,
    )


def preview_domain_transition(
    *,
    selected_direction: str,
    active_record: object | None,
    archived_records: Iterable[object] | None,
) -> BuddyDomainTransitionPreview:
    selected_domain_key = derive_buddy_domain_key(selected_direction)
    current_domain = _serialize_domain_record(active_record)
    archived_matches = [
        serialized
        for serialized in (
            _serialize_domain_record(record) for record in (archived_records or [])
        )
        if serialized is not None and serialized["domain_key"] == selected_domain_key
    ]

    if current_domain is not None and current_domain["domain_key"] == selected_domain_key:
        return BuddyDomainTransitionPreview(
            suggestion_kind="same-domain",
            recommended_action="keep-active",
            selected_domain_key=selected_domain_key,
            reason_summary="新目标看起来仍属于当前领域，可以继承现有能力积累。",
            current_domain=current_domain,
            archived_matches=[],
        )
    if archived_matches:
        return BuddyDomainTransitionPreview(
            suggestion_kind="switch-to-archived-domain",
            recommended_action="restore-archived",
            selected_domain_key=selected_domain_key,
            reason_summary="检测到历史领域能力档案，建议恢复旧积累而不是从零开始。",
            current_domain=current_domain,
            archived_matches=archived_matches,
        )
    return BuddyDomainTransitionPreview(
        suggestion_kind="start-new-domain",
        recommended_action="start-new",
        selected_domain_key=selected_domain_key,
        reason_summary="当前没有可继承的同领域能力档案，建议以新领域重新开始。",
        current_domain=current_domain,
        archived_matches=[],
    )


def _serialize_domain_record(record: object | None) -> dict[str, object] | None:
    if record is None:
        return None
    domain_id = getattr(record, "domain_id", None)
    domain_key = getattr(record, "domain_key", None)
    domain_label = getattr(record, "domain_label", None)
    status = getattr(record, "status", None)
    capability_points = getattr(record, "capability_points", None)
    capability_score = getattr(record, "capability_score", None)
    evolution_stage = getattr(record, "evolution_stage", None)
    if not domain_id or not domain_key:
        return None
    return {
        "domain_id": str(domain_id),
        "domain_key": str(domain_key),
        "domain_label": str(domain_label or domain_key),
        "status": str(status or ""),
        "capability_points": int(capability_points or 0),
        "capability_score": int(capability_score or 0),
        "evolution_stage": str(
            evolution_stage
            or stage_from_points(int(capability_points or 0))
            or capability_stage_from_score(int(capability_score or 0))
        ),
    }


def _normalize_domain_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower().strip()
    normalized = normalized.replace("赚", " 盈利 ")
    normalized = normalized.replace("變現", " 变现 ")
    return normalized


def _clamp_metric(value: int, *, ceiling: int) -> int:
    return max(0, min(ceiling, int(value)))


__all__ = [
    "BuddyDomainCapabilityMetrics",
    "BuddyDomainCapabilitySignals",
    "BuddyDomainTransitionPreview",
    "can_promote_to_stage",
    "capability_stage_from_score",
    "derive_capability_metrics",
    "derive_buddy_domain_key",
    "preview_domain_transition",
    "progress_to_next_capability_stage",
    "progress_to_next_stage",
    "resolve_stage_transition",
    "stage_from_points",
]
