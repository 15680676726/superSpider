# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .models import EvidenceRecord


def serialize_evidence_record(record: EvidenceRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "kind": record.kind,
        "task_id": record.task_id,
        "actor_ref": record.actor_ref,
        "environment_ref": record.environment_ref,
        "capability_ref": record.capability_ref,
        "risk_level": record.risk_level,
        "action_summary": record.action_summary,
        "result_summary": record.result_summary,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "status": record.status,
        "input_digest": record.input_digest,
        "output_digest": record.output_digest,
        "metadata": dict(record.metadata),
        "artifact_count": len(record.artifacts),
        "replay_count": len(record.replay_pointers),
        "artifacts": [
            {
                "id": artifact.id,
                "artifact_type": artifact.artifact_type,
                "storage_uri": artifact.storage_uri,
                "summary": artifact.summary,
            }
            for artifact in record.artifacts
        ],
        "replay_pointers": [
            {
                "id": replay_pointer.id,
                "replay_type": replay_pointer.replay_type,
                "storage_uri": replay_pointer.storage_uri,
                "summary": replay_pointer.summary,
            }
            for replay_pointer in record.replay_pointers
        ],
    }


__all__ = ["serialize_evidence_record"]
