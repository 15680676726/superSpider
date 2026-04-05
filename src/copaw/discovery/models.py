# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _unique_strings(values: Sequence[object | None]) -> tuple[str, ...]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        text = _string(value)
        if text is None:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return tuple(normalized)


def _normalize_float(value: object | None, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class DiscoverySourceSpec:
    source_id: str
    chain_role: str
    source_kind: str
    display_name: str | None = None
    endpoint: str | None = None
    trust_posture: str = "watchlist"
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "chain_role": self.chain_role,
            "source_kind": self.source_kind,
            "display_name": self.display_name,
            "endpoint": self.endpoint,
            "trust_posture": self.trust_posture,
            "priority": self.priority,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "DiscoverySourceSpec":
        return cls(
            source_id=_string(payload.get("source_id")) or "unknown-source",
            chain_role=_string(payload.get("chain_role")) or "primary",
            source_kind=_string(payload.get("source_kind")) or "catalog",
            display_name=_string(payload.get("display_name")),
            endpoint=_string(payload.get("endpoint")),
            trust_posture=_string(payload.get("trust_posture")) or "watchlist",
            priority=int(payload.get("priority") or 0),
            metadata=_normalize_metadata(payload.get("metadata")),
        )


@dataclass(frozen=True, slots=True)
class DiscoverySourceProfile:
    profile_name: str
    sources: tuple[DiscoverySourceSpec, ...]
    display_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DiscoveryActionRequest:
    action_id: str
    query: str
    source_profile: str = "global"
    discovery_mode: str = "gap"
    limit: int = 20
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DiscoveryHit:
    source_id: str
    source_kind: str
    source_alias: str | None = None
    candidate_kind: str = "skill"
    display_name: str | None = None
    summary: str = ""
    candidate_source_ref: str | None = None
    candidate_source_version: str | None = None
    candidate_source_lineage: str | None = None
    canonical_package_id: str | None = None
    equivalence_hint: str | None = None
    capability_keys: tuple[str, ...] = ()
    replacement_relation: str | None = None
    protocol_surface_kind: str | None = None
    transport_kind: str | None = None
    call_surface_ref: str | None = None
    formal_adapter_eligible: bool = False
    adapter_blockers: tuple[str, ...] = ()
    protocol_hints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "source_alias": self.source_alias,
            "candidate_kind": self.candidate_kind,
            "display_name": self.display_name,
            "summary": self.summary,
            "candidate_source_ref": self.candidate_source_ref,
            "candidate_source_version": self.candidate_source_version,
            "candidate_source_lineage": self.candidate_source_lineage,
            "canonical_package_id": self.canonical_package_id,
            "equivalence_hint": self.equivalence_hint,
            "capability_keys": list(self.capability_keys),
            "replacement_relation": self.replacement_relation,
            "protocol_surface_kind": self.protocol_surface_kind,
            "transport_kind": self.transport_kind,
            "call_surface_ref": self.call_surface_ref,
            "formal_adapter_eligible": self.formal_adapter_eligible,
            "adapter_blockers": list(self.adapter_blockers),
            "protocol_hints": dict(self.protocol_hints),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "DiscoveryHit":
        return cls(
            source_id=_string(payload.get("source_id")) or "unknown-source",
            source_kind=_string(payload.get("source_kind")) or "catalog",
            source_alias=_string(payload.get("source_alias")),
            candidate_kind=_string(payload.get("candidate_kind")) or "skill",
            display_name=_string(payload.get("display_name")),
            summary=str(payload.get("summary") or ""),
            candidate_source_ref=_string(payload.get("candidate_source_ref")),
            candidate_source_version=_string(payload.get("candidate_source_version")),
            candidate_source_lineage=_string(payload.get("candidate_source_lineage")),
            canonical_package_id=_string(payload.get("canonical_package_id")),
            equivalence_hint=_string(payload.get("equivalence_hint")),
            capability_keys=_unique_strings(payload.get("capability_keys") or []),
            replacement_relation=_string(payload.get("replacement_relation")),
            protocol_surface_kind=_string(payload.get("protocol_surface_kind")),
            transport_kind=_string(payload.get("transport_kind")),
            call_surface_ref=_string(payload.get("call_surface_ref")),
            formal_adapter_eligible=bool(payload.get("formal_adapter_eligible")),
            adapter_blockers=_unique_strings(payload.get("adapter_blockers") or []),
            protocol_hints=_normalize_metadata(payload.get("protocol_hints")),
            metadata=_normalize_metadata(payload.get("metadata")),
        )


@dataclass(frozen=True, slots=True)
class DiscoverySnapshot:
    profile_name: str
    source_id: str
    captured_at: datetime
    discovery_hits: tuple[DiscoveryHit, ...]


@dataclass(frozen=True, slots=True)
class DiscoverySourceAttempt:
    source_id: str
    chain_role: str
    status: str
    error: str | None = None


@dataclass(frozen=True, slots=True)
class DiscoverySourceChainResult:
    action_id: str
    source_profile: str
    status: str
    active_source_id: str | None = None
    discovery_hits: tuple[DiscoveryHit, ...] = ()
    attempts: tuple[DiscoverySourceAttempt, ...] = ()
    used_snapshot: bool = False
    error_summary: str | None = None

    @property
    def degraded(self) -> bool:
        return self.status != "ok"


@dataclass(frozen=True, slots=True)
class NormalizedDiscoveryHit:
    candidate_kind: str
    candidate_source_kind: str
    display_name: str | None
    summary: str
    candidate_source_ref: str | None
    candidate_source_version: str | None
    candidate_source_lineage: str | None
    canonical_package_id: str | None
    equivalence_class: str
    source_aliases: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    capability_keys: tuple[str, ...] = ()
    capability_overlap_score: float = 0.0
    replacement_relation: str | None = None
    protocol_surface_kind: str | None = None
    transport_kind: str | None = None
    call_surface_ref: str | None = None
    formal_adapter_eligible: bool = False
    adapter_blockers: tuple[str, ...] = ()
    protocol_hints: dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.5
    source_hit_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_candidate_metadata(self) -> dict[str, Any]:
        metadata = dict(self.metadata)
        metadata.update(
            {
                "canonical_package_id": self.canonical_package_id,
                "equivalence_class": self.equivalence_class,
                "source_aliases": list(self.source_aliases),
                "source_ids": list(self.source_ids),
                "capability_keys": list(self.capability_keys),
                "capability_overlap_score": self.capability_overlap_score,
                "replacement_relation": self.replacement_relation,
                "protocol_surface_kind": self.protocol_surface_kind,
                "transport_kind": self.transport_kind,
                "call_surface_ref": self.call_surface_ref,
                "formal_adapter_eligible": self.formal_adapter_eligible,
                "adapter_blockers": list(self.adapter_blockers),
                "protocol_hints": dict(self.protocol_hints),
                "confidence_score": self.confidence_score,
                "source_hit_count": self.source_hit_count,
            },
        )
        return metadata


@dataclass(frozen=True, slots=True)
class OpportunityRadarItem:
    item_id: str
    title: str
    summary: str = ""
    canonical_package_id: str | None = None
    source_ref: str | None = None
    ecosystem: str = "unknown"
    score: float = 0.0
    published_at: datetime = field(default_factory=_utc_now)
    capability_keys: tuple[str, ...] = ()
    query_hint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScoutBudget:
    max_queries: int = 3
    max_candidates: int = 8


@dataclass(frozen=True, slots=True)
class ScoutRequest:
    scout_id: str
    mode: str
    source_profile: str
    target_scope: str
    query: str | None = None
    queries: tuple[str, ...] = ()
    target_role_id: str | None = None
    target_seat_ref: str | None = None
    industry_instance_id: str | None = None
    budget: ScoutBudget = field(default_factory=ScoutBudget)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScoutRunResult:
    scout_id: str
    mode: str
    status: str
    attempted_queries: tuple[str, ...] = ()
    source_run_count: int = 0
    radar_item_count: int = 0
    imported_candidate_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def imported_candidate_count(self) -> int:
        return len(self.imported_candidate_ids)


__all__ = [
    "DiscoveryActionRequest",
    "DiscoveryHit",
    "DiscoverySnapshot",
    "DiscoverySourceAttempt",
    "DiscoverySourceChainResult",
    "DiscoverySourceProfile",
    "DiscoverySourceSpec",
    "NormalizedDiscoveryHit",
    "OpportunityRadarItem",
    "ScoutBudget",
    "ScoutRequest",
    "ScoutRunResult",
    "_normalize_float",
    "_string",
    "_unique_strings",
    "_utc_now",
]
