# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..state import MemoryFactIndexRecord


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_subject_key(entry: MemoryFactIndexRecord) -> str:
    metadata = dict(entry.metadata or {})
    explicit = str(metadata.get("subject_key") or "").strip()
    if explicit:
        return explicit
    if entry.entity_keys:
        return str(entry.entity_keys[0]).strip().lower()
    title = str(entry.title or "").strip().lower()
    return title or entry.id


def _memory_type(entry: MemoryFactIndexRecord) -> str:
    metadata = dict(entry.metadata or {})
    explicit = str(metadata.get("memory_type") or "").strip().lower()
    if explicit:
        return explicit
    if entry.source_type == "strategy_memory":
        return "fact"
    if entry.source_type == "report_snapshot":
        return "episode"
    if entry.source_type == "agent_report":
        return "fact" if entry.evidence_refs else "inference"
    if entry.source_type == "evidence":
        return "fact"
    return "fact"


def _memory_type_rank(entry: MemoryFactIndexRecord) -> int:
    return {
        "fact": 50,
        "preference": 40,
        "episode": 30,
        "temporary": 10,
        "inference": 0,
    }.get(_memory_type(entry), 20)


def _canonical_rank(entry: MemoryFactIndexRecord) -> int:
    metadata = dict(entry.metadata or {})
    status = str(metadata.get("status") or "").strip().lower()
    if entry.source_type == "strategy_memory" and status in {"", "active", "processed"}:
        return 30
    if entry.source_type == "evidence":
        return 24
    if entry.source_type in {"learning_patch", "learning_growth"}:
        return 18
    if entry.source_type in {"agent_report", "knowledge_chunk", "routine_run"}:
        return 12
    return 0


def _evidence_rank(entry: MemoryFactIndexRecord) -> int:
    if not entry.evidence_refs:
        return 0
    return min(len(entry.evidence_refs), 3) * 4


def _temporary_penalty(entry: MemoryFactIndexRecord) -> int:
    return -24 if _memory_type(entry) == "temporary" else 0


def _expired(entry: MemoryFactIndexRecord, *, now: datetime | None = None) -> bool:
    metadata = dict(entry.metadata or {})
    expires_at = _parse_timestamp(metadata.get("expires_at"))
    if expires_at is None:
        return False
    effective_now = now or _utc_now()
    return expires_at <= effective_now


def _precedence_tuple(
    entry: MemoryFactIndexRecord,
    *,
    now: datetime | None = None,
) -> tuple[int, int, int, float, float, datetime]:
    timestamp = entry.source_updated_at or entry.updated_at or entry.created_at or _utc_now()
    return (
        0 if _expired(entry, now=now) else 1,
        _canonical_rank(entry),
        _memory_type_rank(entry) + _evidence_rank(entry) + _temporary_penalty(entry),
        float(entry.confidence or 0.0),
        float(entry.quality_score or 0.0),
        timestamp,
    )


@dataclass(slots=True)
class MemoryEntryPartition:
    latest: list[MemoryFactIndexRecord]
    history: list[MemoryFactIndexRecord]


class MemoryPrecedenceService:
    """Resolve latest versus history using one shared truth-first rule set."""

    def partition_entries(
        self,
        entries: list[MemoryFactIndexRecord],
        *,
        now: datetime | None = None,
    ) -> MemoryEntryPartition:
        grouped: dict[tuple[str, str, str], list[MemoryFactIndexRecord]] = {}
        for entry in list(entries or []):
            key = (
                str(entry.scope_type or "").strip().lower(),
                str(entry.scope_id or "").strip(),
                _normalize_subject_key(entry),
            )
            grouped.setdefault(key, []).append(entry)

        latest: list[MemoryFactIndexRecord] = []
        history: list[MemoryFactIndexRecord] = []
        for group_entries in grouped.values():
            ordered = sorted(
                group_entries,
                key=lambda item: _precedence_tuple(item, now=now),
                reverse=True,
            )
            active_entries = [
                item
                for item in ordered
                if not _expired(item, now=now)
            ]
            if active_entries:
                latest.append(active_entries[0])
                history.extend(item for item in ordered if item.id != active_entries[0].id)
            else:
                history.extend(ordered)

        latest.sort(
            key=lambda item: _precedence_tuple(item, now=now),
            reverse=True,
        )
        history.sort(
            key=lambda item: _precedence_tuple(item, now=now),
            reverse=True,
        )
        return MemoryEntryPartition(latest=latest, history=history)


__all__ = [
    "MemoryEntryPartition",
    "MemoryPrecedenceService",
]
