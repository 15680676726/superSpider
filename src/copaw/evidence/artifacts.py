# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Iterable

from .models import ArtifactRecord, ReplayPointer


def bind_artifacts(
    evidence_id: str,
    artifacts: Iterable[ArtifactRecord],
) -> tuple[ArtifactRecord, ...]:
    return tuple(artifact.materialize(evidence_id=evidence_id) for artifact in artifacts)


def bind_replay_pointers(
    evidence_id: str,
    replay_pointers: Iterable[ReplayPointer],
) -> tuple[ReplayPointer, ...]:
    return tuple(
        replay_pointer.materialize(evidence_id=evidence_id)
        for replay_pointer in replay_pointers
    )


def bind_evidence_links(
    evidence_id: str,
    *,
    artifacts: Iterable[ArtifactRecord] = (),
    replay_pointers: Iterable[ReplayPointer] = (),
) -> tuple[tuple[ArtifactRecord, ...], tuple[ReplayPointer, ...]]:
    return (
        bind_artifacts(evidence_id, artifacts),
        bind_replay_pointers(evidence_id, replay_pointers),
    )
