# -*- coding: utf-8 -*-
"""Formal strategy memory service for the execution core."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterable

from .models_reporting import StrategyMemoryRecord

if TYPE_CHECKING:
    from .repositories.base import BaseStrategyMemoryRepository

_MAX_STRATEGY_TITLE_LENGTH = 160
_MAX_STRATEGY_SUMMARY_LENGTH = 320
_MAX_STRATEGY_MISSION_LENGTH = 320
_MAX_STRATEGY_ITEM_LENGTH = 180
_MAX_STRATEGY_NOTE_LENGTH = 480
_MAX_PRIORITY_ITEMS = 12
_MAX_THINKING_AXIS_ITEMS = 10
_MAX_POLICY_ITEMS = 8
_MAX_CONSTRAINT_ITEMS = 12
_MAX_EVIDENCE_REQUIREMENT_ITEMS = 12
_MAX_CURRENT_FOCUS_ITEMS = 12
_MAX_TEAMMATE_CONTRACTS = 8
_MAX_TEAMMATE_CAPABILITIES = 12
_MAX_TEAMMATE_EVIDENCE_EXPECTATIONS = 6
_MAX_METADATA_LIST_ITEMS = 12
_MAX_METADATA_DICT_KEYS = 16
_MAX_CHAT_WRITEBACK_HISTORY = 10
_MAX_CHAT_WRITEBACK_CLASSIFICATIONS = 6


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_scope_type(scope_type: str) -> str:
    normalized = str(scope_type or "").strip().lower()
    if normalized not in {"global", "industry"}:
        raise ValueError("Strategy scope_type must be 'global' or 'industry'")
    return normalized


def _trim_text(value: object, *, max_length: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3].rstrip()}..."


def _compact_text_list(
    values: object,
    *,
    max_items: int,
    max_length: int = _MAX_STRATEGY_ITEM_LENGTH,
) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    compacted: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _trim_text(value, max_length=max_length)
        if text is None or text in seen:
            continue
        seen.add(text)
        compacted.append(text)
        if len(compacted) >= max_items:
            break
    return compacted


def _compact_chat_writeback_history(values: object) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    deduped: list[dict[str, Any]] = []
    seen_fingerprints: set[str] = set()
    for raw in reversed(values):
        if not isinstance(raw, dict):
            continue
        fingerprint = _trim_text(raw.get("fingerprint"), max_length=96)
        if fingerprint is None or fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)
        item: dict[str, Any] = {"fingerprint": fingerprint}
        instruction = _trim_text(raw.get("instruction"), max_length=240)
        if instruction is not None:
            item["instruction"] = instruction
        updated_at = _trim_text(raw.get("updated_at"), max_length=64)
        if updated_at is not None:
            item["updated_at"] = updated_at
        classifications = _compact_text_list(
            raw.get("classification"),
            max_items=_MAX_CHAT_WRITEBACK_CLASSIFICATIONS,
            max_length=96,
        )
        if classifications:
            item["classification"] = classifications
        deduped.append(item)
        if len(deduped) >= _MAX_CHAT_WRITEBACK_HISTORY:
            break
    deduped.reverse()
    return deduped


def _compact_teammate_contracts(values: object) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    compacted: list[dict[str, Any]] = []
    for raw in values:
        if not isinstance(raw, dict):
            continue
        item: dict[str, Any] = {}
        for key in (
            "agent_id",
            "role_id",
            "role_name",
            "role_summary",
            "mission",
            "employment_mode",
            "reports_to",
            "goal_kind",
            "risk_level",
        ):
            text = _trim_text(raw.get(key), max_length=_MAX_STRATEGY_ITEM_LENGTH)
            if text is not None:
                item[key] = text
        capabilities = _compact_text_list(
            raw.get("capabilities"),
            max_items=_MAX_TEAMMATE_CAPABILITIES,
            max_length=120,
        )
        if capabilities:
            item["capabilities"] = capabilities
        evidence_expectations = _compact_text_list(
            raw.get("evidence_expectations"),
            max_items=_MAX_TEAMMATE_EVIDENCE_EXPECTATIONS,
            max_length=_MAX_STRATEGY_ITEM_LENGTH,
        )
        if evidence_expectations:
            item["evidence_expectations"] = evidence_expectations
        if item:
            compacted.append(item)
        if len(compacted) >= _MAX_TEAMMATE_CONTRACTS:
            break
    return compacted


def _compact_jsonish_value(value: object, *, depth: int = 0) -> Any:
    if isinstance(value, dict):
        compacted: dict[str, Any] = {}
        for index, (key, nested_value) in enumerate(value.items()):
            if index >= _MAX_METADATA_DICT_KEYS:
                break
            compacted[str(key)] = _compact_jsonish_value(nested_value, depth=depth + 1)
        return compacted
    if isinstance(value, list):
        if depth >= 2:
            return _compact_text_list(
                value,
                max_items=_MAX_METADATA_LIST_ITEMS,
                max_length=180,
            )
        compacted_list = [_compact_jsonish_value(item, depth=depth + 1) for item in value[:_MAX_METADATA_LIST_ITEMS]]
        return [item for item in compacted_list if item not in (None, "", [], {})]
    if isinstance(value, tuple):
        return _compact_jsonish_value(list(value), depth=depth)
    if isinstance(value, set):
        return _compact_jsonish_value(list(value), depth=depth)
    if isinstance(value, str):
        return _trim_text(value, max_length=240)
    return value


def _compact_strategy_metadata(metadata: object) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    compacted: dict[str, Any] = {}
    for key, value in metadata.items():
        normalized_key = str(key).strip()
        if not normalized_key:
            continue
        if normalized_key == "chat_writeback_history":
            history = _compact_chat_writeback_history(value)
            if history:
                compacted[normalized_key] = history
            continue
        if normalized_key == "operator_requirements":
            compacted[normalized_key] = _compact_text_list(
                value,
                max_items=12,
                max_length=_MAX_STRATEGY_ITEM_LENGTH,
            )
            continue
        if normalized_key in {"target_customers", "channels"}:
            compacted[normalized_key] = _compact_text_list(
                value,
                max_items=8,
                max_length=120,
            )
            continue
        if normalized_key == "allowed_capabilities":
            compacted[normalized_key] = _compact_text_list(
                value,
                max_items=16,
                max_length=120,
            )
            continue
        if normalized_key in {"recent_failures", "effective_actions", "forbidden_repeats"}:
            compacted[normalized_key] = _compact_text_list(
                value,
                max_items=6,
                max_length=220,
            )
            continue
        if normalized_key == "experience_notes":
            text = _trim_text(value, max_length=_MAX_STRATEGY_NOTE_LENGTH)
            if text is not None:
                compacted[normalized_key] = text
            continue
        compacted_value = _compact_jsonish_value(value)
        if compacted_value not in (None, "", [], {}):
            compacted[normalized_key] = compacted_value
    return compacted


def compact_strategy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        **payload,
        "title": _trim_text(payload.get("title"), max_length=_MAX_STRATEGY_TITLE_LENGTH) or "Strategy Memory",
        "summary": _trim_text(payload.get("summary"), max_length=_MAX_STRATEGY_SUMMARY_LENGTH) or "",
        "mission": _trim_text(payload.get("mission"), max_length=_MAX_STRATEGY_MISSION_LENGTH) or "",
        "north_star": _trim_text(payload.get("north_star"), max_length=_MAX_STRATEGY_SUMMARY_LENGTH) or "",
        "priority_order": _compact_text_list(
            payload.get("priority_order"),
            max_items=_MAX_PRIORITY_ITEMS,
        ),
        "thinking_axes": _compact_text_list(
            payload.get("thinking_axes"),
            max_items=_MAX_THINKING_AXIS_ITEMS,
        ),
        "delegation_policy": _compact_text_list(
            payload.get("delegation_policy"),
            max_items=_MAX_POLICY_ITEMS,
        ),
        "direct_execution_policy": _compact_text_list(
            payload.get("direct_execution_policy"),
            max_items=_MAX_POLICY_ITEMS,
        ),
        "execution_constraints": _compact_text_list(
            payload.get("execution_constraints"),
            max_items=_MAX_CONSTRAINT_ITEMS,
        ),
        "evidence_requirements": _compact_text_list(
            payload.get("evidence_requirements"),
            max_items=_MAX_EVIDENCE_REQUIREMENT_ITEMS,
        ),
        "current_focuses": _compact_text_list(
            payload.get("current_focuses"),
            max_items=_MAX_CURRENT_FOCUS_ITEMS,
        ),
        "teammate_contracts": _compact_teammate_contracts(
            payload.get("teammate_contracts"),
        ),
        "metadata": _compact_strategy_metadata(payload.get("metadata")),
    }


def coerce_strategy_payload(strategy: object | None) -> dict[str, Any] | None:
    """Normalize strategy records/dicts into a plain JSON-like payload."""

    if strategy is None:
        return None
    if isinstance(strategy, dict):
        payload = dict(strategy)
    elif hasattr(strategy, "model_dump"):
        payload = dict(strategy.model_dump(mode="json"))
    else:
        payload = {}
    if not payload:
        return None
    return compact_strategy_payload(payload)


def resolve_strategy_payload(
    *,
    service: object | None,
    scope_type: str,
    scope_id: str | None,
    owner_agent_id: str | None = None,
    fallback_owner_agent_ids: Iterable[str | None] = (),
) -> dict[str, Any] | None:
    """Resolve a strategy payload through the formal state-layer strategy service.

    Planning/workflow/prediction entrypoints should call this helper rather than
    re-implementing owner fallback and payload coercion independently.
    """

    if service is None:
        return None
    normalized_scope_id = str(scope_id or "").strip()
    if not normalized_scope_id:
        return None
    getter = getattr(service, "get_active_strategy", None)
    if not callable(getter):
        return None

    owner_candidates: list[str | None] = []
    for candidate in [owner_agent_id, *list(fallback_owner_agent_ids)]:
        normalized_candidate = str(candidate).strip() if candidate else None
        if normalized_candidate:
            if normalized_candidate not in owner_candidates:
                owner_candidates.append(normalized_candidate)
            continue
        if None not in owner_candidates:
            owner_candidates.append(None)

    if not owner_candidates:
        owner_candidates = [None]

    for candidate in owner_candidates:
        strategy = getter(
            scope_type=_normalize_scope_type(scope_type),
            scope_id=normalized_scope_id,
            owner_agent_id=candidate,
        )
        payload = coerce_strategy_payload(strategy)
        if payload is not None:
            return payload
    return None


class StateStrategyMemoryService:
    """Manage formal strategy memory records in the unified state layer."""

    def __init__(
        self,
        *,
        repository: BaseStrategyMemoryRepository,
        derived_index_service: object | None = None,
        reflection_service: object | None = None,
    ) -> None:
        self._repository = repository
        self._derived_index_service = derived_index_service
        self._reflection_service = reflection_service

    def set_derived_index_service(self, derived_index_service: object | None) -> None:
        self._derived_index_service = derived_index_service

    def set_reflection_service(self, reflection_service: object | None) -> None:
        self._reflection_service = reflection_service

    def canonical_strategy_id(
        self,
        *,
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None = None,
    ) -> str:
        normalized_scope_type = _normalize_scope_type(scope_type)
        normalized_scope_id = str(scope_id).strip()
        normalized_owner = str(owner_agent_id or "").strip() or "shared"
        if not normalized_scope_id:
            raise ValueError("Strategy scope_id is required")
        return f"strategy:{normalized_scope_type}:{normalized_scope_id}:{normalized_owner}"

    def get_strategy(self, strategy_id: str) -> StrategyMemoryRecord | None:
        return self._repository.get_strategy(strategy_id)

    def get_active_strategy(
        self,
        *,
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None = None,
    ) -> StrategyMemoryRecord | None:
        records = self._repository.list_strategies(
            scope_type=_normalize_scope_type(scope_type),
            scope_id=str(scope_id).strip(),
            owner_agent_id=(str(owner_agent_id).strip() if owner_agent_id else None),
            status="active",
            limit=1,
        )
        return records[0] if records else None

    def list_strategies(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        status: str | None = None,
        limit: int | None = 50,
    ) -> list[StrategyMemoryRecord]:
        return self._repository.list_strategies(
            scope_type=_normalize_scope_type(scope_type) if scope_type else None,
            scope_id=(str(scope_id).strip() if scope_id else None),
            owner_agent_id=(str(owner_agent_id).strip() if owner_agent_id else None),
            industry_instance_id=(
                str(industry_instance_id).strip() if industry_instance_id else None
            ),
            status=(str(status).strip() if status else None),
            limit=limit,
        )

    def upsert_strategy(self, record: StrategyMemoryRecord) -> StrategyMemoryRecord:
        strategy_id = (
            str(record.strategy_id).strip()
            or self.canonical_strategy_id(
                scope_type=record.scope_type,
                scope_id=record.scope_id,
                owner_agent_id=record.owner_agent_id,
            )
        )
        existing = self._repository.get_strategy(strategy_id)
        compacted = StrategyMemoryRecord.model_validate(
            {
                **compact_strategy_payload(record.model_dump(mode="python")),
                "strategy_id": strategy_id,
                "scope_type": _normalize_scope_type(record.scope_type),
                "scope_id": str(record.scope_id).strip(),
                "owner_agent_id": (
                    str(record.owner_agent_id).strip()
                    if record.owner_agent_id
                    else None
                ),
                "created_at": existing.created_at if existing is not None else record.created_at,
                "updated_at": _utc_now(),
            },
        )
        stored = self._repository.upsert_strategy(compacted)
        indexer = getattr(self._derived_index_service, "upsert_strategy_memory", None)
        if callable(indexer):
            try:
                indexer(stored)
            except Exception:
                pass
        self._reflect_scope(stored)
        return stored

    def delete_strategy(self, strategy_id: str) -> bool:
        strategy = self._repository.get_strategy(strategy_id)
        deleted = self._repository.delete_strategy(strategy_id)
        if deleted:
            remover = getattr(self._derived_index_service, "delete_source", None)
            if callable(remover):
                try:
                    remover(source_type="strategy_memory", source_ref=strategy_id)
                except Exception:
                    pass
            if strategy is not None:
                self._reflect_scope(strategy)
        return deleted

    def _reflect_scope(self, strategy: StrategyMemoryRecord) -> None:
        reflector = getattr(self._reflection_service, "reflect", None)
        if not callable(reflector):
            return
        try:
            reflector(
                scope_type=_normalize_scope_type(strategy.scope_type),
                scope_id=str(strategy.scope_id).strip(),
                owner_agent_id=(
                    str(strategy.owner_agent_id).strip()
                    if strategy.owner_agent_id
                    else None
                ),
                industry_instance_id=(
                    str(strategy.industry_instance_id).strip()
                    if strategy.industry_instance_id
                    else None
                ),
                trigger_kind="strategy-upsert",
                create_learning_proposals=False,
            )
        except Exception:
            return
