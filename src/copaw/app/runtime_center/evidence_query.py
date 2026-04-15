# -*- coding: utf-8 -*-
"""Evidence-backed read service for Runtime Center."""
from __future__ import annotations

from typing import Any

from ...evidence import EvidenceLedger, EvidenceRecord, serialize_evidence_record


class RuntimeCenterEvidenceQueryService:
    """Read-only Runtime Center evidence queries."""

    def __init__(self, *, evidence_ledger: EvidenceLedger) -> None:
        self._evidence_ledger = evidence_ledger

    def list_recent_records(self, limit: int = 5):
        return self._evidence_ledger.list_recent(limit=limit)

    def count_records(self) -> int:
        return self._evidence_ledger.count_records()

    def get_record(self, evidence_id: str) -> EvidenceRecord | None:
        return self._evidence_ledger.get_record(evidence_id)

    def list_by_capability_ref(
        self,
        capability_ref: str,
        *,
        limit: int = 20,
    ) -> list[EvidenceRecord]:
        return self._evidence_ledger.list_by_capability_ref(
            capability_ref,
            limit=limit,
        )

    def list_by_task(
        self,
        task_id: str,
        *,
        limit: int | None = None,
    ) -> list[EvidenceRecord]:
        records = self._evidence_ledger.list_by_task(task_id)
        if limit is None:
            return records
        return records[-limit:]

    def count_by_capability_ref(self) -> dict[str, int]:
        return self._evidence_ledger.count_by_capability_ref()

    def serialize_record(self, record: EvidenceRecord) -> dict[str, Any]:
        """Serialize a single EvidenceRecord to JSON-friendly dict."""
        return serialize_evidence_record(record)
Phase1EvidenceQueryService = RuntimeCenterEvidenceQueryService
RuntimeEvidenceQueryService = RuntimeCenterEvidenceQueryService
