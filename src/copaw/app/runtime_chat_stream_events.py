# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import AsyncIterator

from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest, SequenceNumberGenerator

from .routers.runtime_center_shared import _encode_sse_event


def _safe_get(source: object | None, key: str) -> object | None:
    if isinstance(source, dict):
        return source.get(key)
    if source is None:
        return None
    return getattr(source, key, None)


def _first_non_empty(*values: object | None) -> object | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
        elif value is not None:
            return value
    return None


def _resolve_thread_info(request_payload: AgentRequest) -> tuple[str | None, str | None, str | None]:
    control_thread_id = _first_non_empty(
        getattr(request_payload, "control_thread_id", None),
        getattr(request_payload, "thread_id", None),
        getattr(request_payload, "session_id", None),
    )
    thread_id = _first_non_empty(
        control_thread_id,
        getattr(request_payload, "thread_id", None),
        getattr(request_payload, "session_id", None),
    )
    session_id = _first_non_empty(getattr(request_payload, "session_id", None))
    return control_thread_id, thread_id, session_id


def _summarize_intake_contract(contract: object | dict[str, object]) -> dict[str, object]:
    context: dict[str, object] = {}
    intent_kind = _safe_get(contract, "intent_kind")
    if intent_kind is not None:
        context["intent_kind"] = intent_kind
    writeback_requested = _safe_get(contract, "writeback_requested")
    if writeback_requested is not None:
        context["writeback_requested"] = writeback_requested
    should_kickoff = _safe_get(contract, "should_kickoff")
    if should_kickoff is not None:
        context["should_kickoff"] = should_kickoff
    decision = _safe_get(contract, "decision")
    if decision is not None:
        decision_id = _safe_get(decision, "id")
        if decision_id is not None:
            context["decision_id"] = decision_id
        decision_intent = _safe_get(decision, "intent_kind") or _safe_get(decision, "intention")
        if decision_intent is not None:
            context["decision_intent"] = decision_intent
        decision_risk_level = _safe_get(decision, "risk_level")
        if decision_risk_level is not None:
            context["decision_risk_level"] = decision_risk_level
    return context


def _summarize_runtime_context(runtime_context: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(runtime_context, dict):
        return {}
    summary: dict[str, object] = {}
    for key in (
        "kernel_task_id",
        "execution_intent",
        "execution_mode",
        "environment_ref",
        "environment_session_id",
        "writeback_requested",
        "should_kickoff",
    ):
        value = runtime_context.get(key)
        if value is not None:
            summary[key] = value
    intake_contract = runtime_context.get("intake_contract")
    if intake_contract is not None:
        intake_summary = _summarize_intake_contract(intake_contract)
        if intake_summary:
            summary["intake_contract"] = intake_summary
    return summary


def _normalize_string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_string_list(value: object | None) -> list[str]:
    raw_items = value if isinstance(value, (list, tuple, set)) else [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = _normalize_string(item)
        if text is None:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return normalized


def _compact_payload(values: dict[str, object | None]) -> dict[str, object]:
    return {
        key: value
        for key, value in values.items()
        if value is not None and (not isinstance(value, str) or value.strip())
    }


def _normalize_commit_state_payload(commit_state: object | None) -> dict[str, object]:
    if commit_state is None:
        return {}
    payload = _safe_get(commit_state, "payload")
    if isinstance(payload, dict):
        return dict(payload)
    return {}


def _build_commit_payload(
    *,
    request_id: str | None,
    control_thread_id: str | None,
    thread_id: str | None,
    session_id: str | None,
    runtime_context_summary: dict[str, object],
    commit_state: object | None,
) -> dict[str, object]:
    commit_payload = _normalize_commit_state_payload(commit_state)
    decision_ids = _normalize_string_list(
        commit_payload.get("decision_ids"),
    )
    decision_id = _normalize_string(
        commit_payload.get("decision_id"),
    )
    if decision_id is None:
        intake_contract = runtime_context_summary.get("intake_contract")
        if isinstance(intake_contract, dict):
            decision_id = _normalize_string(intake_contract.get("decision_id"))
    if decision_id is not None and decision_id not in decision_ids:
        decision_ids.append(decision_id)
    return _compact_payload(
        {
            "request_id": request_id,
            "control_thread_id": _first_non_empty(
                _safe_get(commit_state, "control_thread_id"),
                control_thread_id,
            ),
            "thread_id": _first_non_empty(
                _safe_get(commit_state, "control_thread_id"),
                thread_id,
                control_thread_id,
            ),
            "session_id": _first_non_empty(
                _safe_get(commit_state, "session_id"),
                session_id,
            ),
            "work_context_id": _normalize_string(_safe_get(commit_state, "work_context_id")),
            "status": _normalize_string(_safe_get(commit_state, "status")),
            "action_type": _normalize_string(_safe_get(commit_state, "action_type")),
            "risk_level": _normalize_string(_safe_get(commit_state, "risk_level")),
            "summary": _normalize_string(_safe_get(commit_state, "summary")),
            "reason": _normalize_string(_safe_get(commit_state, "reason")),
            "message": _normalize_string(_safe_get(commit_state, "message")),
            "record_id": _normalize_string(
                _first_non_empty(
                    _safe_get(commit_state, "record_id"),
                    commit_payload.get("record_id"),
                )
            ),
            "commit_key": _normalize_string(_safe_get(commit_state, "commit_key")),
            "decision_id": decision_id,
            "decision_ids": decision_ids or None,
            "recovery_options": _normalize_string_list(
                _safe_get(commit_state, "recovery_options"),
            )
            or None,
            "kernel_task_id": runtime_context_summary.get("kernel_task_id"),
            "execution_intent": runtime_context_summary.get("execution_intent"),
            "execution_mode": runtime_context_summary.get("execution_mode"),
            "environment_ref": runtime_context_summary.get("environment_ref"),
            "environment_session_id": runtime_context_summary.get("environment_session_id"),
            "writeback_requested": runtime_context_summary.get("writeback_requested"),
            "should_kickoff": runtime_context_summary.get("should_kickoff"),
        }
    )


def _resolve_commit_terminal_event(commit_state: object | None) -> str | None:
    status = _normalize_string(_safe_get(commit_state, "status"))
    if status == "confirm_required":
        return "confirm_required"
    if status == "committed":
        return "committed"
    if status == "commit_deferred":
        return "commit_deferred"
    if status in {"commit_failed", "governance_denied"}:
        return "commit_failed"
    return None


def _should_skip_commit_sidecars(commit_state: object | None) -> bool:
    status = _normalize_string(_safe_get(commit_state, "status"))
    reason = _normalize_string(_safe_get(commit_state, "reason"))
    return status == "commit_deferred" and reason == "no_commit_action"


def _build_sidecar_event(
    event_name: str,
    *,
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "object": "runtime.sidecar",
        "event": event_name,
        "payload": payload,
    }


def _build_sidecar_events(
    *,
    request_payload: AgentRequest,
    runtime_context: dict[str, object] | None,
    control_thread_id: str | None,
    thread_id: str | None,
    session_id: str | None,
) -> list[dict[str, object]]:
    request_id = getattr(request_payload, "id", None)
    runtime_summary = _summarize_runtime_context(runtime_context)
    commit_state = getattr(request_payload, "_copaw_main_brain_commit_state", None)
    timing_profile = _safe_get(request_payload, "_copaw_main_brain_timing")
    sidecar_control_thread_id = _first_non_empty(
        _safe_get(commit_state, "control_thread_id"),
        control_thread_id,
        thread_id,
        session_id,
    )
    sidecar_thread_id = _first_non_empty(
        sidecar_control_thread_id,
        thread_id,
        control_thread_id,
        session_id,
    )
    sidecar_session_id = _first_non_empty(
        _safe_get(commit_state, "session_id"),
        session_id,
    )
    events: list[dict[str, object]] = []
    base_payload = _compact_payload(
        {
            "request_id": request_id,
            "control_thread_id": sidecar_control_thread_id,
            "thread_id": sidecar_thread_id,
            "session_id": sidecar_session_id,
            "kernel_task_id": runtime_summary.get("kernel_task_id"),
            "execution_intent": runtime_summary.get("execution_intent"),
            "execution_mode": runtime_summary.get("execution_mode"),
            "environment_ref": runtime_summary.get("environment_ref"),
            "environment_session_id": runtime_summary.get("environment_session_id"),
            "writeback_requested": runtime_summary.get("writeback_requested"),
            "should_kickoff": runtime_summary.get("should_kickoff"),
            "timing": timing_profile if isinstance(timing_profile, dict) and timing_profile else None,
        }
    )
    events.append(
        _build_sidecar_event(
            "turn_reply_done",
            payload=base_payload,
        )
    )
    if commit_state is None or _should_skip_commit_sidecars(commit_state):
        return events
    commit_payload = _build_commit_payload(
        request_id=request_id,
        control_thread_id=sidecar_control_thread_id,
        thread_id=sidecar_thread_id,
        session_id=sidecar_session_id,
        runtime_context_summary=runtime_summary,
        commit_state=commit_state,
    )
    events.append(
        _build_sidecar_event(
            "commit_started",
            payload=commit_payload,
        )
    )
    terminal_event = _resolve_commit_terminal_event(commit_state)
    if terminal_event is not None:
        events.append(
            _build_sidecar_event(
                terminal_event,
                payload=commit_payload,
            )
        )
    return events


def _extract_sequence_number(event: object) -> int | None:
    value = getattr(event, "sequence_number", None)
    if isinstance(value, int):
        return value
    if isinstance(event, dict):
        seq = event.get("sequence_number")
        if isinstance(seq, int):
            return seq
    return None


async def stream_runtime_chat_events(
    *,
    turn_executor: object,
    request_payload: AgentRequest,
) -> AsyncIterator[str]:
    stream_request = getattr(turn_executor, "stream_request", None)
    if not callable(stream_request):
        raise RuntimeError("Kernel turn executor does not support streaming chat execution")

    max_sequence = -1
    async for event in stream_request(request_payload):
        seq = _extract_sequence_number(event)
        if seq is not None:
            max_sequence = max(max_sequence, seq)
        yield _encode_sse_event(event)

    control_thread_id, thread_id, session_id = _resolve_thread_info(request_payload)
    start_sequence = max_sequence + 1 if max_sequence >= 0 else 0
    seq_gen = SequenceNumberGenerator(start=start_sequence)
    for sidecar_event in _build_sidecar_events(
        request_payload=request_payload,
        runtime_context=getattr(request_payload, "_copaw_main_brain_runtime_context", None),
        control_thread_id=control_thread_id,
        thread_id=thread_id,
        session_id=session_id,
    ):
        sidecar_event["sequence_number"] = seq_gen.next()
        yield _encode_sse_event(sidecar_event)
