# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any

from .retrieval_budget import surface_snapshot_limit

logger = logging.getLogger(__name__)

_COMPACTION_VISIBILITY_KEYS = (
    "compaction_state",
    "tool_result_budget",
    "tool_use_summary",
    "donor_trial_carry_forward",
)


def _mapping_value(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _truth_first_entry_timestamp(entry: object) -> object | None:
    for field_name in ("source_updated_at", "updated_at", "created_at"):
        value = getattr(entry, field_name, None)
        if value is not None:
            return value
    return None


def _sort_truth_first_entries(entries: list[object]) -> list[object]:
    return sorted(
        list(entries),
        key=lambda item: (
            _truth_first_entry_timestamp(item) is not None,
            _truth_first_entry_timestamp(item) or "",
        ),
        reverse=True,
    )


def _normalize_runtime_compaction_visibility(payload: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(payload or {})
    normalized: dict[str, Any] = {}
    for key in _COMPACTION_VISIBILITY_KEYS:
        value = _mapping_value(source.get(key))
        if value:
            normalized[key] = value
    return normalized


class MemorySurfaceService:
    """Read-only facade over shared truth-first recall and private compaction memory."""

    def __init__(
        self,
        *,
        memory_recall_service: Any | None = None,
        memory_sleep_service: Any | None = None,
        conversation_compaction_service: Any | None = None,
    ) -> None:
        self._memory_recall_service = memory_recall_service
        self._memory_sleep_service = memory_sleep_service
        self._conversation_compaction_service = conversation_compaction_service

    def set_memory_recall_service(self, memory_recall_service: Any | None) -> None:
        self._memory_recall_service = memory_recall_service

    def set_memory_sleep_service(self, memory_sleep_service: Any | None) -> None:
        self._memory_sleep_service = memory_sleep_service

    def set_conversation_compaction_service(
        self,
        conversation_compaction_service: Any | None,
    ) -> None:
        self._conversation_compaction_service = conversation_compaction_service

    def has_truth_first_surface(self) -> bool:
        return self._memory_recall_service is not None

    def has_private_memory_surface(self) -> bool:
        return self._conversation_compaction_service is not None

    def resolve_truth_first_scope_snapshot(
        self,
        *,
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        limit: int = 8,
    ) -> dict[str, list[object]]:
        service = self._memory_recall_service
        derived_service = getattr(service, "_derived_index_service", None)
        list_fact_entries = getattr(derived_service, "list_fact_entries", None)
        if not callable(list_fact_entries):
            return {
                "entries": [],
                "latest_entries": [],
                "history_entries": [],
                "sleep": self.resolve_sleep_overlay(scope_type=scope_type, scope_id=scope_id),
            }
        bounded_limit = surface_snapshot_limit(limit)
        try:
            entries = _sort_truth_first_entries(
                list(
                    list_fact_entries(
                        scope_type=scope_type,
                        scope_id=scope_id,
                        owner_agent_id=owner_agent_id,
                        industry_instance_id=industry_instance_id,
                        limit=bounded_limit,
                    )
                    or []
                ),
            )
        except Exception:
            logger.debug("Memory surface truth-first snapshot resolve failed", exc_info=True)
            entries = []
        return {
            "entries": entries,
            "latest_entries": entries[:2],
            "history_entries": entries[2:4],
            "sleep": self.resolve_sleep_overlay(scope_type=scope_type, scope_id=scope_id),
        }

    def resolve_sleep_overlay(self, *, scope_type: str, scope_id: str) -> dict[str, Any]:
        service = self._memory_sleep_service
        resolver = getattr(service, "resolve_scope_overlay", None)
        if not callable(resolver):
            return {}
        try:
            payload = resolver(scope_type=scope_type, scope_id=scope_id)
        except Exception:
            logger.debug("Memory surface sleep overlay resolve failed", exc_info=True)
            return {}
        return dict(payload or {}) if isinstance(payload, dict) else {}

    def resolve_runtime_compaction_visibility_payload(self) -> dict[str, Any]:
        conversation_compaction_service = self._conversation_compaction_service
        if conversation_compaction_service is None:
            return {}
        visibility_source: dict[str, Any] = {}
        for getter_name in ("runtime_visibility_payload", "runtime_health_payload"):
            getter = getattr(conversation_compaction_service, getter_name, None)
            if not callable(getter):
                continue
            try:
                payload = getter()
            except Exception:
                logger.debug("Memory surface compaction visibility getter failed", exc_info=True)
                continue
            payload_mapping = _mapping_value(payload)
            if payload_mapping:
                visibility_source.update(payload_mapping)
        builder = getattr(conversation_compaction_service, "build_visibility_payload", None)
        if callable(builder):
            try:
                payload = builder(visibility_source or None)
            except TypeError:
                payload = builder()
            except Exception:
                logger.debug("Memory surface compaction visibility builder failed", exc_info=True)
            else:
                payload_mapping = _mapping_value(payload)
                if payload_mapping:
                    return _normalize_runtime_compaction_visibility(payload_mapping)
        return _normalize_runtime_compaction_visibility(visibility_source)
