# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..evidence import EvidenceLedger, EvidenceRecord
from ..state.models_goals_tasks import AgentReportRecord
from .executor_event_ingest_service import (
    ExecutorEventIngestContext,
    ExecutorEventIngestResult,
    ExecutorEventIngestService,
    ExecutorEventRecordPayload,
)
from .executor_runtime_port import ExecutorNormalizedEvent


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _merge_ids(*groups: Sequence[str] | None) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for item in list(group or []):
            text = _text(item)
            if text is not None and text not in merged:
                merged.append(text)
    return merged


def _stable_executor_report_id(
    *,
    assignment_id: str | None,
    runtime_id: str,
    turn_id: str | None,
    event_type: str,
) -> str:
    stable_parts = [
        _text(assignment_id) or "assignment",
        _text(runtime_id) or "runtime",
        _text(turn_id) or event_type,
    ]
    return "executor-report:" + ":".join(stable_parts)


@dataclass(slots=True)
class ExecutorEventWritebackResult:
    ingest_result: ExecutorEventIngestResult
    evidence_record: EvidenceRecord | None = None
    report_record: AgentReportRecord | None = None

    @property
    def event_record(self) -> ExecutorEventRecordPayload:
        return self.ingest_result.event_record


class ExecutorEventWritebackService:
    def __init__(
        self,
        *,
        ingest_service: ExecutorEventIngestService | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        assignment_service: object | None = None,
        agent_report_service: object | None = None,
        runtime_event_bus: object | None = None,
    ) -> None:
        self._ingest_service = ingest_service or ExecutorEventIngestService()
        self._evidence_ledger = evidence_ledger
        self._assignment_service = assignment_service
        self._agent_report_service = agent_report_service
        self._runtime_event_bus = runtime_event_bus

    def ingest_and_writeback(
        self,
        *,
        context: ExecutorEventIngestContext,
        event: ExecutorNormalizedEvent,
    ) -> ExecutorEventWritebackResult:
        ingest_result = self._ingest_service.ingest_event(
            context=context,
            event=event,
        )
        evidence_record = self._record_evidence(
            payload=ingest_result.evidence_payload,
            assignment_id=context.assignment_id,
        )
        report_record = self._record_report(
            payload=ingest_result.report_payload,
            assignment_id=context.assignment_id,
            runtime_id=context.runtime_id,
            turn_id=ingest_result.event_record.turn_id,
            event_type=event.event_type,
            evidence_ids=[evidence_record.id] if evidence_record is not None else [],
        )
        result = ExecutorEventWritebackResult(
            ingest_result=ingest_result,
            evidence_record=evidence_record,
            report_record=report_record,
        )
        self._publish_runtime_event(
            action="executor-event",
            payload={
                "assignment_id": context.assignment_id,
                "runtime_id": context.runtime_id,
                "event_type": event.event_type,
                "source_type": event.source_type,
                "evidence_id": evidence_record.id if evidence_record is not None else None,
                "report_id": report_record.id if report_record is not None else None,
            },
        )
        return result

    def _record_evidence(
        self,
        *,
        payload: Mapping[str, Any] | None,
        assignment_id: str | None,
    ) -> EvidenceRecord | None:
        if payload is None or self._evidence_ledger is None:
            return None
        record = self._evidence_ledger.append(EvidenceRecord(**dict(payload)))
        attach = getattr(self._assignment_service, "attach_evidence_ids", None)
        if callable(attach) and _text(assignment_id) is not None:
            try:
                attach(assignment_id, evidence_ids=[record.id])
            except Exception:
                pass
        return record

    def _record_report(
        self,
        *,
        payload: Mapping[str, Any] | None,
        assignment_id: str | None,
        runtime_id: str,
        turn_id: str | None,
        event_type: str,
        evidence_ids: Sequence[str],
    ) -> AgentReportRecord | None:
        if payload is None:
            return None
        report_service = self._agent_report_service
        if report_service is None:
            return None
        report_payload = dict(payload)
        task_id = _text(report_payload.get("task_id"))
        ledger_evidence_ids: list[str] = []
        if self._evidence_ledger is not None and task_id is not None:
            try:
                ledger_evidence_ids = [
                    record.id for record in self._evidence_ledger.list_by_task(task_id)
                ]
            except Exception:
                ledger_evidence_ids = []
        report_payload["assignment_id"] = _text(report_payload.get("assignment_id")) or _text(assignment_id)
        report_payload["evidence_ids"] = _merge_ids(
            report_payload.get("evidence_ids") if isinstance(report_payload.get("evidence_ids"), list) else None,
            ledger_evidence_ids,
            evidence_ids,
        )
        report_payload.setdefault(
            "id",
            _stable_executor_report_id(
                assignment_id=_text(report_payload.get("assignment_id")),
                runtime_id=runtime_id,
                turn_id=turn_id,
                event_type=event_type,
            ),
        )
        report = AgentReportRecord(**report_payload)
        record_structured_report = getattr(report_service, "record_structured_report", None)
        if callable(record_structured_report):
            return record_structured_report(report)

        repository = getattr(report_service, "_repository", None)
        upsert_report = getattr(repository, "upsert_report", None)
        if not callable(upsert_report):
            return None
        previous_report = getattr(repository, "get_report", lambda _report_id: None)(report.id)
        stored = upsert_report(report)
        project_report = getattr(report_service, "_project_report", None)
        if callable(project_report):
            try:
                project_report(stored, previous_report=previous_report)
            except Exception:
                pass
        retain = getattr(getattr(report_service, "_memory_retain_service", None), "retain_agent_report", None)
        if callable(retain):
            try:
                retain(stored)
            except Exception:
                pass
        return stored

    def _publish_runtime_event(
        self,
        *,
        action: str,
        payload: Mapping[str, Any],
    ) -> None:
        publish = getattr(self._runtime_event_bus, "publish", None)
        if not callable(publish):
            return
        try:
            publish(
                topic="executor-runtime",
                action=action,
                payload=dict(payload),
            )
        except Exception:
            return


__all__ = [
    "ExecutorEventWritebackResult",
    "ExecutorEventWritebackService",
]
