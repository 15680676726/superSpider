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
    thread_id = getattr(request_payload, "thread_id", None) or control_thread_id
    session_id = getattr(request_payload, "session_id", None)
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
    commit_outcome = runtime_context.get("commit_outcome")
    if isinstance(commit_outcome, dict) and commit_outcome:
        summarized_commit_outcome: dict[str, object] = {}
        for key in ("status", "code", "message"):
            value = commit_outcome.get(key)
            if value is not None:
                summarized_commit_outcome[key] = value
        if summarized_commit_outcome:
            summary["commit_outcome"] = summarized_commit_outcome
    accepted_persistence = runtime_context.get("accepted_persistence")
    if isinstance(accepted_persistence, dict) and accepted_persistence:
        summarized_accepted: dict[str, object] = {}
        for key in ("status", "checkpoint_id", "session_state_saved", "message"):
            value = accepted_persistence.get(key)
            if value is not None:
                summarized_accepted[key] = value
        if summarized_accepted:
            summary["accepted_persistence"] = summarized_accepted
    intake_contract = runtime_context.get("intake_contract")
    if intake_contract is not None:
        intake_summary = _summarize_intake_contract(intake_contract)
        if intake_summary:
            summary["intake_contract"] = intake_summary
    return summary


def _should_emit_confirm_required(context_summary: dict[str, object]) -> bool:
    intake = context_summary.get("intake_contract")
    if not isinstance(intake, dict):
        return False
    return not bool(intake.get("should_kickoff"))


def _build_sidecar_event(
    event_name: str,
    *,
    request_id: str | None,
    control_thread_id: str | None,
    thread_id: str | None,
    session_id: str | None,
    runtime_context_summary: dict[str, object],
    extra_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {"request_id": request_id, "runtime_context": runtime_context_summary}
    if extra_payload:
        payload["details"] = extra_payload
    return {
        "sidecar_event": event_name,
        "control_thread_id": control_thread_id,
        "thread_id": thread_id,
        "session_id": session_id,
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
    events: list[dict[str, object]] = []
    events.append(
        _build_sidecar_event(
            "turn_reply_done",
            request_id=request_id,
            control_thread_id=control_thread_id,
            thread_id=thread_id,
            session_id=session_id,
            runtime_context_summary=runtime_summary,
            extra_payload={"phase": "reply"},
        )
    )
    if runtime_context is None:
        return events
    events.append(
        _build_sidecar_event(
            "commit_started",
            request_id=request_id,
            control_thread_id=control_thread_id,
            thread_id=thread_id,
            session_id=session_id,
            runtime_context_summary=runtime_summary,
            extra_payload={"phase": "commit_started"},
        )
    )
    commit_outcome = runtime_summary.get("commit_outcome")
    if isinstance(commit_outcome, dict) and str(commit_outcome.get("status") or "").strip().lower() == "failed":
        events.append(
            _build_sidecar_event(
                "commit_failed",
                request_id=request_id,
                control_thread_id=control_thread_id,
                thread_id=thread_id,
                session_id=session_id,
                runtime_context_summary=runtime_summary,
                extra_payload={
                    "phase": "commit_failed",
                    "code": _first_non_empty(commit_outcome.get("code"), "RUNTIME_COMMIT_FAILED"),
                    "message": _first_non_empty(
                        commit_outcome.get("message"),
                        "Runtime commit failed before durable writeback completed.",
                    ),
                },
            )
        )
        return events
    if _should_emit_confirm_required(runtime_summary):
        events.append(
            _build_sidecar_event(
                "confirm_required",
                request_id=request_id,
                control_thread_id=control_thread_id,
                thread_id=thread_id,
                session_id=session_id,
                runtime_context_summary=runtime_summary,
                extra_payload={"phase": "confirm_required"},
            )
        )
    events.append(
        _build_sidecar_event(
            "committed",
            request_id=request_id,
            control_thread_id=control_thread_id,
            thread_id=thread_id,
            session_id=session_id,
            runtime_context_summary=runtime_summary,
            extra_payload={"phase": "committed"},
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

    control_thread_id, thread_id, session_id = _resolve_thread_info(request_payload)
    accepted_event = _build_sidecar_event(
        "accepted",
        request_id=getattr(request_payload, "id", None),
        control_thread_id=control_thread_id,
        thread_id=thread_id,
        session_id=session_id,
        runtime_context_summary={},
        extra_payload={"phase": "accepted"},
    )
    yield _encode_sse_event(accepted_event)

    max_sequence = -1
    try:
        async for event in stream_request(request_payload):
            seq = _extract_sequence_number(event)
            if seq is not None:
                max_sequence = max(max_sequence, seq)
            yield _encode_sse_event(event)
    except Exception as error:
        runtime_context = getattr(request_payload, "_copaw_main_brain_runtime_context", None)
        runtime_summary = _summarize_runtime_context(runtime_context)
        seq_gen = SequenceNumberGenerator(start=max_sequence + 1 if max_sequence >= 0 else 0)
        error_message = str(error).strip() or "Runtime chat stream failed."
        yield _encode_sse_event(
            {
                "object": "response",
                "status": "failed",
                "error": {
                    "code": "AGENT_UNKNOWN_ERROR",
                    "message": error_message,
                },
                "sequence_number": seq_gen.next(),
            }
        )
        failed_sidecar = _build_sidecar_event(
            "commit_failed",
            request_id=getattr(request_payload, "id", None),
            control_thread_id=control_thread_id,
            thread_id=thread_id,
            session_id=session_id,
            runtime_context_summary=runtime_summary,
            extra_payload={
                "phase": "commit_failed",
                "code": "AGENT_UNKNOWN_ERROR",
                "message": error_message,
            },
        )
        failed_sidecar["sequence_number"] = seq_gen.next()
        yield _encode_sse_event(failed_sidecar)
        return

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
