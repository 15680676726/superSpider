# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping
from uuid import uuid4

from .executor_runtime_port import ExecutorNormalizedEvent

ExecutorEventProjectionKind = Literal["plan", "evidence", "report", "generic"]


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _copy_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(payload or {})


def _first_text(*values: object | None) -> str | None:
    for value in values:
        text = _text(value)
        if text is not None:
            return text
    return None


def _string_list(value: object | None) -> list[str]:
    if isinstance(value, list):
        return [item for item in (_text(item) for item in value) if item is not None]
    text = _text(value)
    return [text] if text is not None else []


@dataclass(slots=True)
class ExecutorEventIngestContext:
    runtime_id: str
    executor_id: str
    assignment_id: str
    task_id: str | None = None
    industry_instance_id: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    owner_agent_id: str | None = None
    owner_role_id: str | None = None
    assignment_title: str | None = None
    assignment_summary: str | None = None
    risk_level: str = "auto"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutorEventRecordPayload:
    event_id: str
    runtime_id: str
    executor_id: str
    assignment_id: str
    task_id: str | None
    thread_id: str | None
    turn_id: str | None
    event_type: str
    source_type: str
    projection_kind: ExecutorEventProjectionKind
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    raw_method: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutorEventIngestResult:
    event_record: ExecutorEventRecordPayload
    evidence_payload: dict[str, Any] | None = None
    report_payload: dict[str, Any] | None = None


class ExecutorEventIngestService:
    _EVIDENCE_KIND_BY_SOURCE = {
        "commandExecution": "executor-command",
        "fileChange": "executor-file-change",
        "mcpToolCall": "executor-mcp-call",
        "webSearch": "executor-web-search",
    }

    def ingest_event(
        self,
        *,
        context: ExecutorEventIngestContext,
        event: ExecutorNormalizedEvent,
    ) -> ExecutorEventIngestResult:
        payload = _copy_payload(event.payload)
        projection_kind = self._resolve_projection_kind(event)
        event_record = ExecutorEventRecordPayload(
            event_id=f"executor-event-{uuid4().hex}",
            runtime_id=context.runtime_id,
            executor_id=context.executor_id,
            assignment_id=context.assignment_id,
            task_id=context.task_id,
            thread_id=_first_text(payload.get("thread_id"), context.thread_id),
            turn_id=_first_text(payload.get("turn_id"), context.turn_id),
            event_type=event.event_type,
            source_type=event.source_type,
            projection_kind=projection_kind,
            summary=self._build_event_summary(event=event, context=context, payload=payload),
            payload=payload,
            raw_method=event.raw_method,
            metadata={
                **dict(context.metadata),
                "industry_instance_id": context.industry_instance_id,
                "owner_agent_id": context.owner_agent_id,
                "owner_role_id": context.owner_role_id,
            },
        )
        evidence_payload = self._build_evidence_payload(
            context=context,
            event=event,
            payload=payload,
        )
        report_payload = self._build_report_payload(
            context=context,
            event=event,
            payload=payload,
        )
        return ExecutorEventIngestResult(
            event_record=event_record,
            evidence_payload=evidence_payload,
            report_payload=report_payload,
        )

    def _resolve_projection_kind(
        self,
        event: ExecutorNormalizedEvent,
    ) -> ExecutorEventProjectionKind:
        if event.event_type == "plan_submitted":
            return "plan"
        if event.event_type == "evidence_emitted" and event.source_type in self._EVIDENCE_KIND_BY_SOURCE:
            return "evidence"
        if event.event_type in {"task_completed", "task_failed"}:
            return "report"
        return "generic"

    def _build_event_summary(
        self,
        *,
        event: ExecutorNormalizedEvent,
        context: ExecutorEventIngestContext,
        payload: Mapping[str, Any],
    ) -> str:
        if event.event_type == "plan_submitted":
            summary = _first_text(
                payload.get("plan_summary"),
                payload.get("summary"),
                payload.get("message"),
            )
            if summary is not None:
                return summary
            step_count = len(_string_list(payload.get("steps")))
            if step_count:
                return f"Executor plan updated with {step_count} steps"
            return "Executor plan updated"
        if event.event_type == "evidence_emitted":
            action_summary, result_summary = self._build_evidence_summaries(
                source_type=event.source_type,
                payload=payload,
            )
            return _first_text(result_summary, action_summary) or "Executor emitted evidence"
        if event.event_type in {"task_completed", "task_failed"}:
            result = "completed" if event.event_type == "task_completed" else "failed"
            summary = _first_text(
                payload.get("summary"),
                payload.get("result_summary"),
                payload.get("error"),
                payload.get("message"),
                context.assignment_summary,
            )
            if summary is not None:
                return summary
            title = _text(context.assignment_title) or "Executor turn"
            return f"{title} {result}"
        return (
            _first_text(payload.get("message"), payload.get("summary"), payload.get("status"))
            or f"{event.event_type} ({event.source_type})"
        )

    def _build_evidence_payload(
        self,
        *,
        context: ExecutorEventIngestContext,
        event: ExecutorNormalizedEvent,
        payload: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        if event.event_type != "evidence_emitted":
            return None
        evidence_kind = self._EVIDENCE_KIND_BY_SOURCE.get(event.source_type)
        if evidence_kind is None or _text(context.task_id) is None:
            return None
        action_summary, result_summary = self._build_evidence_summaries(
            source_type=event.source_type,
            payload=payload,
        )
        return {
            "task_id": context.task_id,
            "actor_ref": f"executor:{context.executor_id}",
            "capability_ref": f"executor:{context.executor_id}",
            "environment_ref": None,
            "risk_level": context.risk_level,
            "kind": evidence_kind,
            "action_summary": action_summary,
            "result_summary": result_summary,
            "status": "recorded",
            "metadata": self._build_metadata(
                context=context,
                event=event,
                payload=payload,
            ),
        }

    def _build_report_payload(
        self,
        *,
        context: ExecutorEventIngestContext,
        event: ExecutorNormalizedEvent,
        payload: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        if event.event_type not in {"task_completed", "task_failed"}:
            return None
        industry_instance_id = _text(context.industry_instance_id)
        if industry_instance_id is None:
            return None
        completed = event.event_type == "task_completed"
        result = "completed" if completed else "failed"
        summary = _first_text(
            payload.get("summary"),
            payload.get("result_summary"),
            payload.get("error"),
            payload.get("message"),
            context.assignment_summary,
            context.assignment_title,
        ) or f"Executor turn {result}"
        title = _text(context.assignment_title) or "Executor turn"
        uncertainty = _first_text(payload.get("error"), payload.get("message"))
        return {
            "industry_instance_id": industry_instance_id,
            "assignment_id": _text(context.assignment_id),
            "task_id": _text(context.task_id),
            "owner_agent_id": _text(context.owner_agent_id),
            "owner_role_id": _text(context.owner_role_id),
            "report_kind": "executor-terminal",
            "headline": f"{title} {result}",
            "summary": summary,
            "findings": [summary] if completed else [],
            "uncertainties": [uncertainty] if not completed and uncertainty is not None else [],
            "recommendation": None,
            "needs_followup": not completed,
            "followup_reason": uncertainty if not completed else None,
            "status": "recorded",
            "result": result,
            "risk_level": context.risk_level,
            "evidence_ids": [],
            "decision_ids": [],
            "metadata": self._build_metadata(
                context=context,
                event=event,
                payload=payload,
            ),
        }

    def _build_evidence_summaries(
        self,
        *,
        source_type: str,
        payload: Mapping[str, Any],
    ) -> tuple[str, str]:
        if source_type == "commandExecution":
            command = _first_text(payload.get("command"), payload.get("command_text")) or "command"
            exit_code = _text(payload.get("exit_code"))
            status = _text(payload.get("status"))
            result = _first_text(
                payload.get("summary"),
                f"Command finished with exit code {exit_code}" if exit_code is not None else None,
                f"Command status: {status}" if status is not None else None,
                "Command finished",
            )
            return (f"Executed command: {command}", result or "Command finished")
        if source_type == "fileChange":
            path = _first_text(payload.get("path"), payload.get("file_path")) or "file"
            change_type = _text(payload.get("change_type"))
            result = _first_text(
                payload.get("summary"),
                f"File {change_type}" if change_type is not None else None,
                "File updated",
            )
            return (f"Updated file: {path}", result or "File updated")
        if source_type == "mcpToolCall":
            tool_name = _first_text(payload.get("tool_name"), payload.get("tool")) or "tool"
            server_name = _first_text(payload.get("server_name"), payload.get("server"))
            status = _text(payload.get("status"))
            result = _first_text(
                payload.get("summary"),
                server_name,
                status,
                "MCP tool call completed",
            )
            return (f"Called MCP tool: {tool_name}", result or "MCP tool call completed")
        if source_type == "webSearch":
            query = _first_text(payload.get("query"), payload.get("search_query")) or "search"
            result = _first_text(payload.get("summary"), payload.get("top_result"), "Search completed")
            return (f"Ran web search: {query}", result or "Search completed")
        return ("Executor emitted evidence", _first_text(payload.get("summary"), payload.get("message")) or "Evidence recorded")

    def _build_metadata(
        self,
        *,
        context: ExecutorEventIngestContext,
        event: ExecutorNormalizedEvent,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            **dict(context.metadata),
            "assignment_id": context.assignment_id,
            "executor_id": context.executor_id,
            "executor_runtime_id": context.runtime_id,
            "executor_thread_id": _first_text(payload.get("thread_id"), context.thread_id),
            "executor_turn_id": _first_text(payload.get("turn_id"), context.turn_id),
            "executor_event_type": event.event_type,
            "executor_source_type": event.source_type,
            "executor_raw_method": event.raw_method,
            "executor_payload": _copy_payload(payload),
            "industry_instance_id": context.industry_instance_id,
            "owner_agent_id": context.owner_agent_id,
            "owner_role_id": context.owner_role_id,
        }


__all__ = [
    "ExecutorEventIngestContext",
    "ExecutorEventIngestResult",
    "ExecutorEventIngestService",
    "ExecutorEventProjectionKind",
    "ExecutorEventRecordPayload",
]
