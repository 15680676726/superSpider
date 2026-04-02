# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from inspect import isawaitable
from typing import Any

from .main_brain_environment_coordinator import MainBrainEnvironmentBinding
from .main_brain_execution_planner import MainBrainExecutionPlan
from .main_brain_intake import MainBrainIntakeContract
from .main_brain_recovery_coordinator import MainBrainRecoveryState

logger = logging.getLogger(__name__)

_ALLOWED_COMMIT_STATUSES = {
    "committed",
    "commit_deferred",
    "commit_failed",
    "governance_denied",
    "confirm_required",
}
_WRITEBACK_ACTION_TYPES = {
    "writeback_operating_truth",
    "create_backlog_item",
    "submit_human_assist",
}
_KICKOFF_ACTION_TYPES = {
    "orchestrate_execution",
    "resume_execution",
}


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
            continue
        if value is not None:
            return value
    return None


def _string(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    namespace = getattr(value, "__dict__", None)
    if isinstance(namespace, dict):
        return dict(namespace)
    return {}


def _resolve_downstream_record_id(result: Any) -> str | None:
    payload = _mapping(result)
    if not payload:
        return None
    record_id = payload.get("record_id")
    if isinstance(record_id, str) and record_id.strip():
        return record_id.strip()
    for key in (
        "created_backlog_ids",
        "created_goal_ids",
        "created_schedule_ids",
        "started_goal_ids",
        "resumed_schedule_ids",
    ):
        values = payload.get(key)
        if isinstance(values, list):
            for item in values:
                if isinstance(item, str) and item.strip():
                    return item.strip()
    for key in ("strategy_id", "decision_request_id", "resume_target_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_durable_failure_reason(action_type: str) -> str:
    if action_type in _KICKOFF_ACTION_TYPES:
        return "durable_kickoff_failed"
    return "durable_writeback_failed"


def _resolve_durable_failure_message(action_type: str) -> str:
    if action_type in _KICKOFF_ACTION_TYPES:
        return "kickoff pipeline did not confirm durable persistence"
    return "writeback pipeline did not confirm durable persistence"


def _resolve_success_markers(action_type: str) -> tuple[str, ...]:
    if action_type in _KICKOFF_ACTION_TYPES:
        return ("activated", "resumed")
    return ("applied", "deduplicated", "strategy_updated", "submitted")


def normalize_durable_commit_result(
    result: Any,
    *,
    action_type: str,
    commit_key: str,
    default_record_id: str | None,
    empty_reason: str,
) -> dict[str, Any]:
    payload = _mapping(result)
    explicit_status = _string(payload.get("status"))
    record_id = _resolve_downstream_record_id(payload) or default_record_id
    if explicit_status in _ALLOWED_COMMIT_STATUSES:
        normalized = dict(payload)
        normalized["status"] = explicit_status
        if record_id is not None:
            normalized["record_id"] = record_id
        normalized["commit_key"] = commit_key
        return normalized
    if not payload:
        return {
            "status": "commit_failed",
            "reason": empty_reason,
            "message": _resolve_durable_failure_message(action_type),
            "commit_key": commit_key,
        }
    success = _resolve_downstream_record_id(payload) is not None or any(
        bool(payload.get(key))
        for key in _resolve_success_markers(action_type)
    )
    if not success:
        normalized = dict(payload)
        normalized["status"] = "commit_failed"
        normalized["reason"] = _resolve_durable_failure_reason(action_type)
        normalized["message"] = _resolve_durable_failure_message(action_type)
        normalized["commit_key"] = commit_key
        return normalized
    normalized = dict(payload)
    normalized["status"] = "committed"
    if record_id is not None:
        normalized["record_id"] = record_id
    normalized["commit_key"] = commit_key
    return normalized


def update_request_runtime_context(
    request: Any,
    *,
    accepted_persistence: dict[str, Any] | None = None,
    commit_outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runtime_context = _mapping(getattr(request, "_copaw_main_brain_runtime_context", None))
    if accepted_persistence is not None:
        runtime_context["accepted_persistence"] = dict(accepted_persistence)
    if commit_outcome is not None:
        runtime_context["commit_outcome"] = dict(commit_outcome)
    set_request_runtime_value(
        request,
        "_copaw_main_brain_runtime_context",
        runtime_context,
    )
    return runtime_context


def build_accepted_persistence(
    *,
    request: Any,
    source: str,
    boundary: str,
) -> dict[str, Any]:
    session_id = _string(getattr(request, "session_id", None)) or None
    control_thread_id = _string(getattr(request, "control_thread_id", None)) or session_id
    return {
        "status": "accepted",
        "source": source,
        "boundary": boundary,
        "session_id": session_id,
        "control_thread_id": control_thread_id,
        "work_context_id": _string(getattr(request, "work_context_id", None)) or None,
    }


def set_request_runtime_value(request: Any, name: str, value: Any) -> None:
    try:
        object.__setattr__(request, name, value)
        return
    except Exception:
        pass
    try:
        setattr(request, name, value)
    except Exception:
        logger.debug("Failed to set runtime request attribute '%s'", name)


class MainBrainResultCommitter:
    def __init__(
        self,
        *,
        industry_service: Any | None = None,
    ) -> None:
        self._industry_service = industry_service

    def commit_request_runtime_context(
        self,
        *,
        request: Any,
        intake_contract: MainBrainIntakeContract | None,
        execution_plan: MainBrainExecutionPlan,
        environment_binding: MainBrainEnvironmentBinding,
        recovery_state: MainBrainRecoveryState,
        kernel_task_id: str | None,
    ) -> None:
        runtime_context = {
            "intake_contract": intake_contract,
            "source_intent_kind": execution_plan.source_intent_kind,
            "execution_intent": execution_plan.intent_kind,
            "execution_mode": execution_plan.execution_mode,
            "environment_ref": environment_binding.environment_ref,
            "environment_binding_kind": environment_binding.binding_kind,
            "environment_kind": environment_binding.environment_kind,
            "environment_session_id": environment_binding.environment_session_id,
            "environment_lease_token": environment_binding.environment_lease_token,
            "environment_continuity_token": environment_binding.continuity_token,
            "environment_continuity_source": environment_binding.continuity_source,
            "environment_live_session_bound": environment_binding.live_session_bound,
            "environment_resume_ready": environment_binding.resume_ready,
            "writeback_requested": bool(getattr(intake_contract, "writeback_requested", False)),
            "should_kickoff": bool(getattr(intake_contract, "should_kickoff", False)),
            "recovery_mode": recovery_state.recovery_mode,
            "recovery_reason": recovery_state.recovery_reason,
            "resume_checkpoint_id": recovery_state.resume_checkpoint_id,
            "resume_mailbox_id": recovery_state.resume_mailbox_id,
            "resume_kernel_task_id": recovery_state.resume_kernel_task_id,
            "resume_environment_session_id": recovery_state.resume_environment_session_id,
            "recovery_continuity_token": recovery_state.continuity_token,
            "kernel_task_id": kernel_task_id,
        }
        set_request_runtime_value(
            request,
            "_copaw_main_brain_runtime_context",
            runtime_context,
        )
        set_request_runtime_value(request, "_copaw_main_brain_intake_contract", intake_contract)
        if kernel_task_id is not None:
            set_request_runtime_value(request, "_copaw_kernel_task_id", kernel_task_id)

    async def commit_action(
        self,
        *,
        action_envelope: Any,
        request: Any,
        commit_key: str,
    ) -> dict[str, Any]:
        action_type = str(getattr(action_envelope, "action_type", "") or "").strip()
        payload = getattr(action_envelope, "payload", None)
        if not isinstance(payload, dict):
            payload = {}
        service = self._industry_service
        if service is None:
            return {
                "status": "commit_deferred",
                "reason": "no_industry_service",
                "commit_key": commit_key,
            }
        if action_type in {"writeback_operating_truth", "create_backlog_item"}:
            handler = getattr(service, "apply_execution_chat_writeback", None)
            if callable(handler):
                result = handler(
                    action_type=action_type,
                    payload=dict(payload),
                    request=request,
                    commit_key=commit_key,
                )
                if isawaitable(result):
                    result = await result
                return self._normalize_downstream_result(
                    result,
                    action_type=action_type,
                    commit_key=commit_key,
                    default_record_id=str(
                        payload.get("title") or payload.get("summary") or commit_key,
                    ),
                    empty_reason="writeback_handler_returned_no_result",
                )
        if action_type in {"orchestrate_execution", "resume_execution"}:
            handler = getattr(service, "kickoff_execution_from_chat", None)
            if callable(handler):
                result = handler(
                    action_type=action_type,
                    payload=dict(payload),
                    request=request,
                    commit_key=commit_key,
                )
                if isawaitable(result):
                    result = await result
                return self._normalize_downstream_result(
                    result,
                    action_type=action_type,
                    commit_key=commit_key,
                    default_record_id=str(
                        payload.get("goal_summary")
                        or payload.get("resume_target_id")
                        or commit_key,
                    ),
                    empty_reason="kickoff_handler_returned_no_result",
                )
        return {
            "status": "commit_deferred",
            "reason": "no_handler",
            "commit_key": commit_key,
        }

    @classmethod
    def _normalize_downstream_result(
        cls,
        result: Any,
        *,
        action_type: str,
        commit_key: str,
        default_record_id: str,
        empty_reason: str,
    ) -> dict[str, Any]:
        return normalize_durable_commit_result(
            result,
            action_type=action_type,
            commit_key=commit_key,
            default_record_id=default_record_id,
            empty_reason=empty_reason,
        )


__all__ = [
    "MainBrainResultCommitter",
    "build_accepted_persistence",
    "normalize_durable_commit_result",
    "set_request_runtime_value",
    "update_request_runtime_context",
]
