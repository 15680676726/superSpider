# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from ..evidence import EvidenceLedger
from .models import ArtifactEntry, ObservationRecord, ReplayEntry


class ObservationCache:
    """Query-time observation cache derived from evidence."""

    def __init__(self, *, ledger: EvidenceLedger | None = None) -> None:
        self._ledger = ledger

    def list_recent(
        self,
        *,
        environment_ref: str | None,
        limit: int = 20,
    ) -> list[ObservationRecord]:
        if self._ledger is None or not environment_ref:
            return []
        records = self._ledger.list_by_environment_ref(
            environment_ref,
            limit=limit,
        )
        return [
            ObservationRecord(
                evidence_id=record.id or "",
                environment_ref=record.environment_ref,
                capability_ref=record.capability_ref,
                action_summary=record.action_summary,
                result_summary=record.result_summary,
                risk_level=record.risk_level,
                created_at=record.created_at,
            )
            for record in records
            if record.id
        ]

    def get_observation(self, observation_id: str) -> ObservationRecord | None:
        if self._ledger is None:
            return None
        record = self._ledger.get_record(observation_id)
        if record is None or not record.id:
            return None
        return ObservationRecord(
            evidence_id=record.id,
            environment_ref=record.environment_ref,
            capability_ref=record.capability_ref,
            action_summary=record.action_summary,
            result_summary=record.result_summary,
            risk_level=record.risk_level,
            created_at=record.created_at,
        )


class ActionReplayStore:
    """Replay pointers collected from evidence records."""

    def __init__(self, *, ledger: EvidenceLedger | None = None) -> None:
        self._ledger = ledger

    def list_replays(
        self,
        *,
        environment_ref: str | None,
        limit: int = 20,
    ) -> list[ReplayEntry]:
        if self._ledger is None or not environment_ref:
            return []
        replays = self._ledger.list_replay_pointers_by_environment_ref(
            environment_ref,
            limit=limit,
        )
        return [
            ReplayEntry(
                evidence_id=replay.evidence_id or "",
                replay_id=replay.id or "",
                replay_type=replay.replay_type,
                storage_uri=replay.storage_uri,
                summary=replay.summary,
                created_at=replay.created_at,
                metadata=dict(replay.metadata),
            )
            for replay in replays
        ]

    def get_replay(self, replay_id: str) -> ReplayEntry | None:
        if self._ledger is None:
            return None
        replay = self._ledger.get_replay_pointer(replay_id)
        if replay is None:
            return None
        return ReplayEntry(
            evidence_id=replay.evidence_id or "",
            replay_id=replay.id or "",
            replay_type=replay.replay_type,
            storage_uri=replay.storage_uri,
            summary=replay.summary,
            created_at=replay.created_at,
            metadata=dict(replay.metadata),
        )


class ArtifactStore:
    """Artifact pointers collected from evidence records."""

    def __init__(self, *, ledger: EvidenceLedger | None = None) -> None:
        self._ledger = ledger

    def list_artifacts(
        self,
        *,
        environment_ref: str | None,
        limit: int = 20,
    ) -> list[ArtifactEntry]:
        if self._ledger is None or not environment_ref:
            return []
        artifacts = self._ledger.list_artifact_records_by_environment_ref(
            environment_ref,
            limit=limit,
        )
        return [
            ArtifactEntry(
                evidence_id=artifact.evidence_id or "",
                artifact_id=artifact.id or "",
                artifact_type=artifact.artifact_type,
                storage_uri=artifact.storage_uri,
                summary=artifact.summary,
                created_at=artifact.created_at,
            )
            for artifact in artifacts
        ]

    def get_artifact(self, artifact_id: str) -> ArtifactEntry | None:
        if self._ledger is None:
            return None
        artifact = self._ledger.get_artifact_record(artifact_id)
        if artifact is None:
            return None
        return ArtifactEntry(
            evidence_id=artifact.evidence_id or "",
            artifact_id=artifact.id or "",
            artifact_type=artifact.artifact_type,
            storage_uri=artifact.storage_uri,
            summary=artifact.summary,
            created_at=artifact.created_at,
        )


__all__ = ["ObservationCache", "ActionReplayStore", "ArtifactStore"]
