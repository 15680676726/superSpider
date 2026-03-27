# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime:
    if value is None:
        return utc_now()

    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def make_record_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_type: str
    storage_uri: str
    summary: str
    id: str | None = None
    evidence_id: str | None = None
    created_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def materialize(self, *, evidence_id: str | None = None) -> "ArtifactRecord":
        return replace(
            self,
            id=self.id or make_record_id("artifact"),
            evidence_id=evidence_id if evidence_id is not None else self.evidence_id,
            created_at=ensure_utc(self.created_at),
        )


@dataclass(frozen=True)
class ReplayPointer:
    replay_type: str
    storage_uri: str
    summary: str
    id: str | None = None
    evidence_id: str | None = None
    created_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def materialize(self, *, evidence_id: str | None = None) -> "ReplayPointer":
        return replace(
            self,
            id=self.id or make_record_id("replay"),
            evidence_id=evidence_id if evidence_id is not None else self.evidence_id,
            created_at=ensure_utc(self.created_at),
        )


@dataclass(frozen=True)
class EvidenceRecord:
    task_id: str
    actor_ref: str
    risk_level: str
    action_summary: str
    result_summary: str
    id: str | None = None
    environment_ref: str | None = None
    capability_ref: str | None = None
    created_at: datetime | None = None
    status: str = "recorded"
    input_digest: str | None = None
    output_digest: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    artifacts: tuple[ArtifactRecord, ...] = field(default_factory=tuple)
    replay_pointers: tuple[ReplayPointer, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", dict(self.metadata or {}))
        object.__setattr__(self, "artifacts", tuple(self.artifacts or ()))
        object.__setattr__(
            self,
            "replay_pointers",
            tuple(self.replay_pointers or ()),
        )

    def materialize(self) -> "EvidenceRecord":
        return replace(
            self,
            id=self.id or make_record_id("evidence"),
            created_at=ensure_utc(self.created_at),
        )

    @property
    def artifact_refs(self) -> tuple[str, ...]:
        return tuple(artifact.storage_uri for artifact in self.artifacts)

    @property
    def replay_refs(self) -> tuple[str, ...]:
        return tuple(pointer.storage_uri for pointer in self.replay_pointers)
