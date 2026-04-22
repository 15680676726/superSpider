# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

from .executor_event_ingest_service import ExecutorEventIngestContext
from .executor_event_writeback_service import ExecutorEventWritebackService
from .executor_runtime_port import ExecutorRuntimePort


DURABLE_RUNTIME_COORDINATOR_CONTRACT = "durable-runtime-coordinator/v1"
_EXECUTOR_RUNTIME_ENTRYPOINT = "executor-runtime"

logger = logging.getLogger(__name__)


def build_durable_runtime_coordination(
    *,
    entrypoint: str,
    coordinator_id: str | None,
    parent_id: str | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "coordinator_contract": DURABLE_RUNTIME_COORDINATOR_CONTRACT,
        "coordinator_entrypoint": entrypoint,
        "coordinator_id": str(coordinator_id or entrypoint).strip() or entrypoint,
    }
    if parent_id is not None:
        normalized_parent = str(parent_id).strip()
        if normalized_parent:
            payload["coordinator_parent_id"] = normalized_parent
    if isinstance(extras, dict):
        payload.update(extras)
    return payload


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _message_text(msg: object) -> str:
    getter = getattr(msg, "get_text_content", None)
    if callable(getter):
        try:
            content = getter()
        except Exception:
            content = None
        text = _text(content)
        if text is not None:
            return text
    for attr in ("content", "text"):
        text = _text(getattr(msg, attr, None))
        if text is not None:
            return text
    return ""


def _resolve_prompt(
    *,
    intake_contract: object | None,
    msgs: list[Any],
) -> str:
    contract_text = _text(getattr(intake_contract, "message_text", None))
    if contract_text is not None:
        return contract_text
    for msg in reversed(list(msgs or [])):
        text = _message_text(msg)
        if text:
            return text
    return ""


def _mapping(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_list(value: object | None) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [item for item in (_text(item) for item in value) if item is not None]
    item = _text(value)
    return [item] if item is not None else []


def _compact_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    compacted: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            nested = _compact_mapping(value)
            if nested:
                compacted[key] = nested
            continue
        if isinstance(value, list):
            if value:
                compacted[key] = value
            continue
        if value not in (None, ""):
            compacted[key] = value
    return compacted


def _resolve_assignment_id(request: Any) -> str | None:
    for field in (
        "assignment_id",
        "current_assignment_id",
        "target_assignment_id",
    ):
        value = _text(getattr(request, field, None))
        if value is not None:
            return value
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context", None)
    if isinstance(runtime_context, dict):
        return _text(runtime_context.get("assignment_id"))
    return None


@dataclass(slots=True)
class ExecutorRuntimeSelection:
    assignment_id: str
    role_id: str | None
    provider_id: str
    executor_id: str
    protocol_kind: str
    selection_mode: str
    task_id: str | None = None
    industry_instance_id: str | None = None
    owner_agent_id: str | None = None
    assignment_title: str | None = None
    assignment_summary: str | None = None
    report_back_mode: str | None = None
    risk_level: str | None = None
    project_profile_id: str | None = None
    model_policy_id: str | None = None
    model_ref: str | None = None


class AssignmentExecutorRuntimeCoordinator:
    """Optional seam from assignment truth into executor runtime selection/start."""

    def __init__(
        self,
        *,
        assignment_service: object | None = None,
        executor_runtime_service: object | None = None,
        executor_runtime_port: ExecutorRuntimePort | None = None,
        executor_event_writeback_service: ExecutorEventWritebackService | None = None,
        default_executor_provider_id: str | None = None,
        default_model_policy_id: str | None = None,
        project_root: str | None = None,
    ) -> None:
        self._assignment_service = assignment_service
        self._executor_runtime_service = executor_runtime_service
        self._executor_runtime_port = executor_runtime_port
        self._executor_event_writeback_service = executor_event_writeback_service
        self._default_executor_provider_id = _text(default_executor_provider_id)
        self._default_model_policy_id = _text(default_model_policy_id)
        self._project_root = _text(project_root)

    def set_assignment_service(self, assignment_service: object | None) -> None:
        self._assignment_service = assignment_service

    def set_executor_runtime_service(
        self,
        executor_runtime_service: object | None,
    ) -> None:
        self._executor_runtime_service = executor_runtime_service
        self._sync_writeback_runtime_service()

    def set_executor_runtime_port(
        self,
        executor_runtime_port: ExecutorRuntimePort | None,
    ) -> None:
        self._executor_runtime_port = executor_runtime_port

    def set_executor_event_writeback_service(
        self,
        executor_event_writeback_service: ExecutorEventWritebackService | None,
    ) -> None:
        self._executor_event_writeback_service = executor_event_writeback_service
        self._sync_writeback_runtime_service()

    def set_default_executor_provider_id(self, provider_id: str | None) -> None:
        self._default_executor_provider_id = _text(provider_id)

    def set_default_model_policy_id(self, policy_id: str | None) -> None:
        self._default_model_policy_id = _text(policy_id)

    def set_project_root(self, project_root: str | None) -> None:
        self._project_root = _text(project_root)

    def _sync_writeback_runtime_service(self) -> None:
        writeback_service = self._executor_event_writeback_service
        if writeback_service is None:
            return
        setter = getattr(writeback_service, "set_executor_runtime_service", None)
        if callable(setter):
            setter(self._executor_runtime_service)

    def coordinate_assignment_runtime(
        self,
        *,
        request: Any,
        msgs: list[Any],
        intake_contract: object | None,
    ) -> dict[str, Any] | None:
        assignment_id = _resolve_assignment_id(request)
        if assignment_id is None:
            return None
        selection = self._resolve_selection(assignment_id=assignment_id)
        if selection is None:
            return {
                "assignment_id": assignment_id,
                "status": "selection-unavailable",
            }
        runtime_service = self._executor_runtime_service
        if runtime_service is None:
            return {
                "assignment_id": assignment_id,
                "status": "runtime-service-unavailable",
                "provider_id": selection.provider_id,
                "executor_id": selection.executor_id,
            }
        create_or_reuse_runtime = getattr(runtime_service, "create_or_reuse_runtime", None)
        if not callable(create_or_reuse_runtime):
            return {
                "assignment_id": assignment_id,
                "status": "runtime-service-unavailable",
                "provider_id": selection.provider_id,
                "executor_id": selection.executor_id,
            }
        runtime = create_or_reuse_runtime(
            executor_id=selection.provider_id,
            protocol_kind=selection.protocol_kind,
            scope_kind="assignment",
            assignment_id=assignment_id,
            role_id=selection.role_id,
            project_profile_id=selection.project_profile_id,
            metadata={
                "selection_mode": selection.selection_mode,
                "model_policy_id": selection.model_policy_id,
                "model_ref": selection.model_ref,
            },
        )
        if self._executor_runtime_port is None:
            return self._build_payload(
                request=request,
                intake_contract=intake_contract,
                selection=selection,
                runtime=runtime,
                status="port-unavailable",
            )
        prompt = _resolve_prompt(intake_contract=intake_contract, msgs=msgs)
        project_root = self._project_root or "."
        try:
            started = self._executor_runtime_port.start_assignment_turn(
                assignment_id=assignment_id,
                project_root=project_root,
                prompt=prompt,
                thread_id=_text(getattr(runtime, "thread_id", None)),
            )
        except Exception as exc:
            logger.debug("Executor runtime start failed for assignment %s", assignment_id, exc_info=True)
            mark_runtime_stopped = getattr(runtime_service, "mark_runtime_stopped", None)
            if callable(mark_runtime_stopped):
                try:
                    runtime = mark_runtime_stopped(
                        getattr(runtime, "runtime_id"),
                        status="failed",
                        metadata={"start_error": str(exc)},
                    )
                except Exception:
                    logger.debug("Failed to mark executor runtime as failed", exc_info=True)
            return self._build_payload(
                request=request,
                intake_contract=intake_contract,
                selection=selection,
                runtime=runtime,
                status="start-failed",
                error=str(exc),
            )
        mark_runtime_ready = getattr(runtime_service, "mark_runtime_ready", None)
        if callable(mark_runtime_ready):
            runtime = mark_runtime_ready(
                getattr(runtime, "runtime_id"),
                thread_id=started.thread_id,
                metadata={
                    "turn_id": started.turn_id,
                    "runtime_metadata": dict(getattr(started, "runtime_metadata", {}) or {}),
                    "model_ref": _text(getattr(started, "model_ref", None)) or selection.model_ref,
                },
            )
        payload = self._build_payload(
            request=request,
            intake_contract=intake_contract,
            selection=selection,
            runtime=runtime,
            status="ready",
            thread_id=started.thread_id,
            turn_id=started.turn_id,
            runtime_metadata=dict(getattr(started, "runtime_metadata", {}) or {}),
            model_ref=_text(getattr(started, "model_ref", None)) or selection.model_ref,
        )
        self._start_event_writeback(payload=payload)
        return payload

    def _resolve_selection(self, *, assignment_id: str) -> ExecutorRuntimeSelection | None:
        assignment_service = self._assignment_service
        runtime_service = self._executor_runtime_service
        if assignment_service is None or runtime_service is None:
            return None
        get_assignment = getattr(assignment_service, "get_assignment", None)
        if not callable(get_assignment):
            return None
        assignment = get_assignment(assignment_id)
        if assignment is None:
            return None
        role_id = _text(getattr(assignment, "owner_role_id", None))
        binding = None
        if role_id is not None:
            resolve_binding = getattr(runtime_service, "resolve_role_executor_binding", None)
            if callable(resolve_binding):
                binding = resolve_binding(role_id)
        provider_id = _text(getattr(binding, "executor_provider_id", None)) or self._default_executor_provider_id
        if provider_id is None:
            return None
        resolve_provider = getattr(runtime_service, "resolve_executor_provider", None)
        if not callable(resolve_provider):
            return None
        provider = resolve_provider(provider_id)
        if provider is None:
            return None
        model_policy_id = _text(getattr(binding, "model_policy_id", None)) or self._default_model_policy_id
        model_ref = None
        if model_policy_id is not None:
            resolve_policy = getattr(runtime_service, "resolve_model_invocation_policy", None)
            if callable(resolve_policy):
                policy = resolve_policy(model_policy_id)
                model_ref = _text(getattr(policy, "default_model_ref", None))
        executor_id = (
            _text(getattr(provider, "provider_id", None))
            or _text(getattr(provider, "runtime_family", None))
            or provider_id
        )
        protocol_kind = (
            _text(getattr(provider, "default_protocol_kind", None))
            or _text(getattr(provider, "control_surface_kind", None))
            or "unknown"
        )
        project_profile_id = _text(getattr(assignment, "project_profile_id", None))
        metadata = getattr(assignment, "metadata", None)
        assignment_metadata = _mapping(metadata)
        if project_profile_id is None and assignment_metadata:
            project_profile_id = _text(assignment_metadata.get("project_profile_id"))
        task_id = _text(getattr(assignment, "task_id", None)) or _text(
            assignment_metadata.get("task_id")
        )
        industry_instance_id = _text(getattr(assignment, "industry_instance_id", None)) or _text(
            assignment_metadata.get("industry_instance_id")
        )
        owner_agent_id = _text(getattr(assignment, "owner_agent_id", None)) or _text(
            assignment_metadata.get("owner_agent_id")
        )
        assignment_title = _text(getattr(assignment, "title", None))
        assignment_summary = _text(getattr(assignment, "summary", None)) or _text(
            assignment_metadata.get("summary")
        )
        report_back_mode = (
            _text(getattr(assignment, "report_back_mode", None))
            or _text(assignment_metadata.get("report_back_mode"))
            or "summary"
        )
        risk_level = (
            _text(getattr(assignment, "risk_level", None))
            or _text(assignment_metadata.get("risk_level"))
            or _text(assignment_metadata.get("current_risk_level"))
        )
        return ExecutorRuntimeSelection(
            assignment_id=assignment_id,
            role_id=role_id,
            provider_id=provider_id,
            executor_id=executor_id,
            protocol_kind=protocol_kind,
            selection_mode=_text(getattr(binding, "selection_mode", None)) or "single-runtime",
            task_id=task_id,
            industry_instance_id=industry_instance_id,
            owner_agent_id=owner_agent_id,
            assignment_title=assignment_title,
            assignment_summary=assignment_summary,
            report_back_mode=report_back_mode,
            risk_level=risk_level,
            project_profile_id=project_profile_id,
            model_policy_id=model_policy_id,
            model_ref=model_ref,
        )

    def _build_payload(
        self,
        *,
        request: Any,
        intake_contract: object | None,
        selection: ExecutorRuntimeSelection,
        runtime: object,
        status: str,
        thread_id: str | None = None,
        turn_id: str | None = None,
        runtime_metadata: dict[str, Any] | None = None,
        model_ref: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        resolved_runtime_id = _text(getattr(runtime, "runtime_id", None))
        resolved_thread_id = thread_id or _text(getattr(runtime, "thread_id", None))
        resolved_model_ref = model_ref or selection.model_ref
        event_ingest_context = self._build_event_ingest_context(
            request=request,
            intake_contract=intake_contract,
            selection=selection,
            runtime_id=resolved_runtime_id,
            thread_id=resolved_thread_id,
            turn_id=turn_id,
            model_ref=resolved_model_ref,
        )
        payload = build_durable_runtime_coordination(
            entrypoint=_EXECUTOR_RUNTIME_ENTRYPOINT,
            coordinator_id=resolved_runtime_id or selection.assignment_id,
            parent_id=selection.assignment_id,
            extras={
                "status": status,
                "assignment_id": selection.assignment_id,
                "task_id": selection.task_id,
                "industry_instance_id": selection.industry_instance_id,
                "owner_agent_id": selection.owner_agent_id,
                "owner_role_id": selection.role_id,
                "report_back_mode": selection.report_back_mode,
                "risk_level": selection.risk_level or "auto",
                "executor_runtime": {
                    "assignment_id": selection.assignment_id,
                    "task_id": selection.task_id,
                    "industry_instance_id": selection.industry_instance_id,
                    "owner_agent_id": selection.owner_agent_id,
                    "owner_role_id": selection.role_id,
                    "assignment_title": selection.assignment_title,
                    "assignment_summary": selection.assignment_summary,
                    "report_back_mode": selection.report_back_mode,
                    "risk_level": selection.risk_level or "auto",
                    "runtime_id": resolved_runtime_id,
                    "runtime_status": _text(getattr(runtime, "runtime_status", None)),
                    "provider_id": selection.provider_id,
                    "executor_id": selection.executor_id,
                    "protocol_kind": selection.protocol_kind,
                    "selection_mode": selection.selection_mode,
                    "role_id": selection.role_id,
                    "project_profile_id": selection.project_profile_id,
                    "thread_id": resolved_thread_id,
                    "turn_id": turn_id,
                    "model_policy_id": selection.model_policy_id,
                    "model_ref": resolved_model_ref,
                    "runtime_metadata": dict(runtime_metadata or {}),
                    "event_ingest_context": event_ingest_context,
                    "error": error,
                },
            },
        )
        return payload

    def _build_event_ingest_context(
        self,
        *,
        request: Any,
        intake_contract: object | None,
        selection: ExecutorRuntimeSelection,
        runtime_id: str | None,
        thread_id: str | None,
        turn_id: str | None,
        model_ref: str | None,
    ) -> dict[str, Any]:
        writeback_plan = getattr(intake_contract, "writeback_plan", None)
        metadata = _compact_mapping(
            {
                "provider_id": selection.provider_id,
                "protocol_kind": selection.protocol_kind,
                "selection_mode": selection.selection_mode,
                "project_profile_id": selection.project_profile_id,
                "model_policy_id": selection.model_policy_id,
                "model_ref": model_ref,
                "control_thread_id": _text(getattr(request, "control_thread_id", None)),
                "session_id": _text(getattr(request, "session_id", None)),
                "work_context_id": _text(getattr(request, "work_context_id", None)),
                "kernel_task_id": _text(getattr(request, "_copaw_kernel_task_id", None)),
                "report_back_mode": selection.report_back_mode,
                "writeback_requested": bool(getattr(intake_contract, "writeback_requested", False)),
                "writeback_plan_active": bool(
                    writeback_plan is not None and getattr(writeback_plan, "active", False)
                ),
                "writeback_plan_classifications": _string_list(
                    getattr(writeback_plan, "classifications", None)
                ),
                "writeback_plan_fingerprint": _text(
                    getattr(writeback_plan, "fingerprint", None)
                ),
                "should_kickoff": bool(getattr(intake_contract, "should_kickoff", False)),
            }
        )
        return {
            "runtime_id": runtime_id,
            "executor_id": selection.executor_id,
            "assignment_id": selection.assignment_id,
            "task_id": selection.task_id,
            "industry_instance_id": selection.industry_instance_id,
            "thread_id": thread_id,
            "turn_id": turn_id,
            "owner_agent_id": selection.owner_agent_id,
            "owner_role_id": selection.role_id,
            "assignment_title": selection.assignment_title,
            "assignment_summary": selection.assignment_summary,
            "risk_level": selection.risk_level or "auto",
            "metadata": metadata,
        }

    def _start_event_writeback(self, *, payload: dict[str, Any]) -> None:
        executor_runtime_payload = _mapping(payload.get("executor_runtime"))
        if not executor_runtime_payload:
            return
        port = self._executor_runtime_port
        writeback_service = self._executor_event_writeback_service
        runtime_service = self._executor_runtime_service
        thread_id = _text(executor_runtime_payload.get("thread_id"))
        runtime_id = _text(executor_runtime_payload.get("runtime_id"))
        turn_id = _text(executor_runtime_payload.get("turn_id"))
        if (
            port is None
            or writeback_service is None
            or runtime_service is None
            or thread_id is None
            or runtime_id is None
        ):
            return
        context_payload = _mapping(executor_runtime_payload.get("event_ingest_context"))
        if not context_payload:
            return
        try:
            context = ExecutorEventIngestContext(**context_payload)
        except Exception:
            logger.debug("Executor runtime event writeback context is invalid", exc_info=True)
            return
        thread = threading.Thread(
            target=self._drain_executor_events,
            name=f"executor-runtime-drain:{runtime_id}",
            kwargs={
                "runtime_id": runtime_id,
                "thread_id": thread_id,
                "turn_id": turn_id,
                "context": context,
            },
            daemon=True,
        )
        thread.start()

    def _drain_executor_events(
        self,
        *,
        runtime_id: str,
        thread_id: str,
        turn_id: str | None,
        context: ExecutorEventIngestContext,
    ) -> None:
        port = self._executor_runtime_port
        writeback_service = self._executor_event_writeback_service
        runtime_service = self._executor_runtime_service
        if port is None or writeback_service is None or runtime_service is None:
            return
        try:
            for event in port.subscribe_events(thread_id=thread_id):
                event_turn_id = _text(event.payload.get("turn_id"))
                if turn_id is not None and event_turn_id not in {None, turn_id}:
                    continue
                result = writeback_service.ingest_and_writeback(
                    context=context,
                    event=event,
                )
                self._mark_runtime_progress(
                    runtime_id=runtime_id,
                    event_type=event.event_type,
                    evidence_id=_text(getattr(result.evidence_record, "id", None)),
                    report_id=_text(getattr(result.report_record, "id", None)),
                )
                if event.event_type == "task_completed":
                    self._mark_runtime_terminal(runtime_id=runtime_id, status="completed")
                    return
                if event.event_type == "task_failed":
                    self._mark_runtime_terminal(runtime_id=runtime_id, status="failed")
                    return
        except Exception as exc:
            logger.debug("Executor runtime event drain failed", exc_info=True)
            self._mark_runtime_terminal(
                runtime_id=runtime_id,
                status="failed",
                metadata={"event_drain_error": str(exc)},
            )

    def _mark_runtime_progress(
        self,
        *,
        runtime_id: str,
        event_type: str,
        evidence_id: str | None = None,
        report_id: str | None = None,
    ) -> None:
        runtime_service = self._executor_runtime_service
        mark_runtime_ready = getattr(runtime_service, "mark_runtime_ready", None)
        if not callable(mark_runtime_ready):
            return
        metadata = _compact_mapping(
            {
                "last_executor_event_type": event_type,
                "last_evidence_id": evidence_id,
                "last_report_id": report_id,
            }
        )
        try:
            mark_runtime_ready(runtime_id, metadata=metadata)
        except Exception:
            logger.debug("Failed to mark executor runtime progress", exc_info=True)

    def _mark_runtime_terminal(
        self,
        *,
        runtime_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        runtime_service = self._executor_runtime_service
        mark_runtime_stopped = getattr(runtime_service, "mark_runtime_stopped", None)
        if not callable(mark_runtime_stopped):
            return
        try:
            mark_runtime_stopped(runtime_id, status=status, metadata=metadata)
        except Exception:
            logger.debug("Failed to mark executor runtime terminal state", exc_info=True)


__all__ = [
    "AssignmentExecutorRuntimeCoordinator",
    "DURABLE_RUNTIME_COORDINATOR_CONTRACT",
    "ExecutorRuntimeSelection",
    "build_durable_runtime_coordination",
]
