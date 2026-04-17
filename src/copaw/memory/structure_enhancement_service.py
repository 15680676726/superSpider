# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
import re
from typing import Any

from ..state import IndustryMemorySlotPreferenceRecord

_SLOT_TOKEN_RE = re.compile(r"[^a-z0-9]+")
_DEFAULT_COMMON_SLOTS = {
    "industry": ["goal", "constraints", "entities", "relations"],
    "work_context": ["current_goal", "stage", "blockers", "next_steps"],
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_slot_key(value: object | None) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    normalized = _SLOT_TOKEN_RE.sub("_", raw).strip("_")
    return normalized


def _slot_label(slot_key: str) -> str:
    return str(slot_key or "").replace("_", " ").strip().title()


def _dedupe(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_slot_key(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _preference_id(*, industry_instance_id: str, scope_level: str, scope_id: str, slot_key: str) -> str:
    return f"slot-pref:{industry_instance_id}:{scope_level}:{scope_id}:{slot_key}"


@dataclass(slots=True)
class StructureEnhancementResult:
    promoted_slots: list[str] = field(default_factory=list)
    demoted_slots: list[str] = field(default_factory=list)
    active_slots: list[str] = field(default_factory=list)
    persisted_preferences: list[IndustryMemorySlotPreferenceRecord] = field(default_factory=list)


class StructureEnhancementService:
    """Maintain stable industry memory slots over repeated rounds."""

    def __init__(
        self,
        *,
        repository,
        promotion_threshold: int = 2,
        common_slots: dict[str, list[str]] | None = None,
    ) -> None:
        self._repository = repository
        self._promotion_threshold = max(1, int(promotion_threshold or 1))
        self._common_slots = {
            key: _dedupe(list(values))
            for key, values in (common_slots or _DEFAULT_COMMON_SLOTS).items()
        }

    def build_slot_layout(
        self,
        *,
        industry_instance_id: str | None,
        scope_type: str,
        scope_id: str,
        candidate_slots: list[str] | None = None,
    ) -> dict[str, Any]:
        active_preferences = self._repository.list_slot_preferences(
            industry_instance_id=industry_instance_id,
            scope_level="industry" if industry_instance_id else scope_type,
            scope_id=industry_instance_id or scope_id,
            status="active",
            limit=None,
        )
        common_slots = list(self._common_slots.get(scope_type, []))
        dynamic_slots = [item.slot_key for item in active_preferences]
        if candidate_slots:
            dynamic_slots = _dedupe([*dynamic_slots, *candidate_slots])
        ordered_slots = _dedupe([*common_slots, *dynamic_slots])
        return {
            "common_slots": common_slots,
            "dynamic_slots": dynamic_slots,
            "ordered_slots": ordered_slots,
        }

    def evaluate_dynamic_slots(
        self,
        *,
        industry_instance_id: str | None,
        candidate_slots: list[str],
        existing_slots: list[str] | None = None,
        scope_level: str = "industry",
        scope_id: str | None = None,
        source_kind: str = "sleep",
    ) -> StructureEnhancementResult:
        normalized_industry = str(industry_instance_id or "").strip()
        if not normalized_industry:
            return StructureEnhancementResult()
        normalized_scope_id = str(scope_id or industry_instance_id or "").strip() or normalized_industry
        now = _utc_now()
        counts = Counter(_normalize_slot_key(item) for item in list(candidate_slots or []))
        counts.pop("", None)
        existing_records = self._repository.list_slot_preferences(
            industry_instance_id=normalized_industry,
            scope_level=scope_level,
            scope_id=normalized_scope_id,
            limit=None,
        )
        records_by_key = {item.slot_key: item for item in existing_records}
        result = StructureEnhancementResult()

        for slot_key, count in counts.items():
            existing = records_by_key.get(slot_key)
            if count < self._promotion_threshold and existing is None:
                continue
            record = (existing or IndustryMemorySlotPreferenceRecord(
                preference_id=_preference_id(
                    industry_instance_id=normalized_industry,
                    scope_level=scope_level,
                    scope_id=normalized_scope_id,
                    slot_key=slot_key,
                ),
                industry_instance_id=normalized_industry,
                slot_key=slot_key,
                slot_label=_slot_label(slot_key),
                scope_level=scope_level,
                scope_id=normalized_scope_id,
                source_kind=source_kind,
                status="active",
            )).model_copy(
                update={
                    "slot_label": _slot_label(slot_key),
                    "source_kind": source_kind,
                    "source_ref": f"{source_kind}:{normalized_scope_id}",
                    "observation_count": int(getattr(existing, "observation_count", 0) or 0) + count,
                    "promotion_count": int(getattr(existing, "promotion_count", 0) or 0)
                    + (1 if count >= self._promotion_threshold else 0),
                    "last_observed_at": now,
                    "last_promoted_at": now if count >= self._promotion_threshold else getattr(existing, "last_promoted_at", None),
                    "status": "active",
                    "updated_at": now,
                }
            )
            saved = self._repository.upsert_slot_preference(record)
            result.persisted_preferences.append(saved)
            if count >= self._promotion_threshold:
                result.promoted_slots.append(slot_key)

        stale_slot_keys = _dedupe([*(existing_slots or []), *records_by_key.keys()])
        for slot_key in stale_slot_keys:
            if slot_key in counts:
                continue
            existing = records_by_key.get(slot_key)
            if existing is None or existing.status != "active":
                continue
            saved = self._repository.upsert_slot_preference(
                existing.model_copy(
                    update={
                        "demotion_count": int(existing.demotion_count or 0) + 1,
                        "last_demoted_at": now,
                        "status": "inactive",
                        "updated_at": now,
                    }
                )
            )
            result.persisted_preferences.append(saved)
            result.demoted_slots.append(slot_key)

        result.promoted_slots = _dedupe(result.promoted_slots)
        result.demoted_slots = _dedupe(result.demoted_slots)
        layout = self.build_slot_layout(
            industry_instance_id=normalized_industry,
            scope_type="industry",
            scope_id=normalized_scope_id,
        )
        result.active_slots = list(layout["ordered_slots"])
        return result
