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


_CAPABILITY_STAGE_BANDS: tuple[tuple[int, BuddyEvolutionStage], ...] = (
    (80, "signature"),
    (60, "seasoned"),
    (40, "capable"),
    (20, "bonded"),
    (0, "seed"),
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
            "设计",
            "系统",
            "design",
            "designer",
            "system",
            "systems",
            "copy",
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


def _clamp_capability_score(score: int) -> int:
    return max(0, min(100, int(score)))


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


def derive_buddy_domain_key(direction: str) -> str:
    normalized = _normalize_domain_text(direction)
    for key, tokens in _DOMAIN_RULES:
        if any(token in normalized for token in tokens):
            return key
    collapsed = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "-", normalized)
    collapsed = collapsed.strip("-")
    return collapsed or "general"


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
    capability_score = getattr(record, "capability_score", None)
    evolution_stage = getattr(record, "evolution_stage", None)
    if not domain_id or not domain_key:
        return None
    return {
        "domain_id": str(domain_id),
        "domain_key": str(domain_key),
        "domain_label": str(domain_label or domain_key),
        "status": str(status or ""),
        "capability_score": int(capability_score or 0),
        "evolution_stage": str(evolution_stage or capability_stage_from_score(int(capability_score or 0))),
    }


def _normalize_domain_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower().strip()
    normalized = normalized.replace("赚", " 盈利 ")
    normalized = normalized.replace("變現", " 变现 ")
    return normalized


__all__ = [
    "BuddyDomainTransitionPreview",
    "capability_stage_from_score",
    "derive_buddy_domain_key",
    "preview_domain_transition",
    "progress_to_next_capability_stage",
]
