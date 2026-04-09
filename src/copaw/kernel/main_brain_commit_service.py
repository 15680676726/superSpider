# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import hashlib
import json
from inspect import isawaitable
from typing import Any, Awaitable, Callable

from .main_brain_result_committer import normalize_durable_commit_result
from .main_brain_turn_result import MainBrainCommitState, MainBrainTurnResult

_REQUIRED_PAYLOAD_FIELDS: dict[str, tuple[str, ...]] = {
    "orchestrate_execution": (
        "goal_summary",
        "requested_surfaces",
        "operator_intent_summary",
    ),
    "writeback_operating_truth": (
        "target_kind",
        "summary",
        "facts",
        "source_refs",
    ),
    "create_backlog_item": (
        "lane_hint",
        "title",
        "summary",
        "acceptance_hint",
        "source_refs",
    ),
    "resume_execution": (
        "resume_target_kind",
        "resume_target_id",
        "continuity_ref",
        "resume_reason",
    ),
    "submit_human_assist": (
        "task_type",
        "request_summary",
        "acceptance_anchors",
        "continuity_ref",
    ),
}


def _string(value: object | None) -> str:
    return str(value or "").strip()


def _mapping(value: object | None) -> dict[str, Any]:
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


def _string_list(value: object | None) -> list[str]:
    return [text for text in (str(item or "").strip() for item in list(value or [])) if text]


def _resolve_snapshot_user_id(request: Any) -> str:
    return _string(getattr(request, "agent_id", None)) or _string(
        getattr(request, "user_id", None),
    )


class MainBrainCommitService:
    def __init__(
        self,
        *,
        session_backend: Any,
        risk_evaluator: Callable[[Any, Any], object] | None = None,
        environment_checker: Callable[[Any, Any], object] | None = None,
        governance_checker: Callable[[Any, Any], object] | None = None,
        action_handlers: dict[str, Callable[[Any, Any, str], object]] | None = None,
        dirty_marker: Callable[..., None] | None = None,
    ) -> None:
        self._session_backend = session_backend
        self._risk_evaluator = risk_evaluator
        self._environment_checker = environment_checker
        self._governance_checker = governance_checker
        self._action_handlers = dict(action_handlers or {})
        self._dirty_marker = dirty_marker

    def get_persisted_commit_state(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> MainBrainCommitState | None:
        snapshot = self._load_snapshot(session_id=session_id, user_id=user_id)
        payload = _mapping(_mapping(snapshot.get("main_brain")).get("phase2_commit"))
        if not payload:
            return None
        return MainBrainCommitState.model_validate(payload)

    def commit_turn_result(
        self,
        *,
        turn_result: MainBrainTurnResult,
        request: Any,
    ) -> MainBrainCommitState:
        return asyncio.run(
            self.commit_turn_result_async(turn_result=turn_result, request=request),
        )

    async def commit_turn_result_async(
        self,
        *,
        turn_result: MainBrainTurnResult,
        request: Any,
    ) -> MainBrainCommitState:
        normalized = MainBrainTurnResult.normalize(turn_result)
        envelope = normalized.action_envelope
        if envelope.kind != "commit_action":
            return self._decorate_state(
                request=request,
                state=MainBrainCommitState(
                    status="commit_deferred",
                    action_type=envelope.action_type,
                    reason="no_commit_action",
                    summary=envelope.summary,
                    payload=envelope.payload,
                ),
            )

        validation_error = self._validate_payload(envelope.action_type, envelope.payload)
        if validation_error is not None:
            return self._persist_state(
                request=request,
                state=MainBrainCommitState(
                    status="commit_failed",
                    action_type=envelope.action_type,
                    reason="payload_invalid",
                    message=validation_error,
                    summary=envelope.summary,
                    payload=envelope.payload,
                ),
            )

        commit_key = self._build_commit_key(envelope=envelope, request=request)
        persisted = self.get_persisted_commit_state(
            session_id=_string(getattr(request, "session_id", None)),
            user_id=_resolve_snapshot_user_id(request),
        )
        if (
            persisted is not None
            and persisted.commit_key == commit_key
            and persisted.status == "committed"
        ):
            return self._persist_state(
                request=request,
                state=persisted.model_copy(update={"idempotent_replay": True}),
            )

        risk_payload = await self._maybe_call(self._risk_evaluator, envelope, request)
        risk_level = _string(_mapping(risk_payload).get("risk_level")) or envelope.risk_hint
        if risk_level == "confirm":
            risk_level = "auto"

        environment_payload = await self._maybe_call(
            self._environment_checker,
            envelope,
            request,
        )
        environment_mapping = _mapping(environment_payload)
        if environment_mapping and not bool(environment_mapping.get("available", True)):
            return self._persist_state(
                request=request,
                state=MainBrainCommitState(
                    status="commit_failed",
                    action_type=envelope.action_type,
                    risk_level=risk_level or "auto",
                    reason=_string(environment_mapping.get("reason")) or "environment_unavailable",
                    message=_string(environment_mapping.get("message")),
                    summary=envelope.summary,
                    payload=envelope.payload,
                    commit_key=commit_key,
                    recovery_options=_string_list(environment_mapping.get("recovery_options")),
                ),
            )

        governance_payload = await self._maybe_call(
            self._governance_checker,
            envelope,
            request,
        )
        governance_mapping = _mapping(governance_payload)
        if governance_mapping and not bool(governance_mapping.get("allowed", True)):
            risk_level = "auto"

        handler = self._action_handlers.get(envelope.action_type)
        if handler is None:
            return self._persist_state(
                request=request,
                state=MainBrainCommitState(
                    status="commit_deferred",
                    action_type=envelope.action_type,
                    risk_level=risk_level or "auto",
                    reason="no_handler",
                    summary=envelope.summary,
                    payload=envelope.payload,
                    commit_key=commit_key,
                ),
            )
        handler_result = normalize_durable_commit_result(
            await self._maybe_call(handler, envelope, request, commit_key),
            action_type=envelope.action_type,
            commit_key=commit_key,
            default_record_id=None,
            empty_reason="commit_handler_returned_no_result",
        )
        status = _string(handler_result.get("status")) or "commit_failed"
        return self._persist_state(
            request=request,
            state=MainBrainCommitState(
                status=status,
                action_type=envelope.action_type,
                risk_level=risk_level or "auto",
                reason=_string(handler_result.get("reason")) or None,
                message=_string(handler_result.get("message")) or None,
                summary=envelope.summary,
                payload=envelope.payload,
                commit_key=commit_key,
                record_id=_string(handler_result.get("record_id")) or None,
                recovery_options=_string_list(handler_result.get("recovery_options")),
            ),
        )

    async def _maybe_call(self, func: Callable[..., object] | None, *args: object) -> object | None:
        if func is None:
            return None
        result = func(*args)
        if isawaitable(result):
            return await result  # type: ignore[no-any-return]
        return result

    def _validate_payload(self, action_type: str, payload: dict[str, Any] | None) -> str | None:
        payload_mapping = _mapping(payload)
        required = _REQUIRED_PAYLOAD_FIELDS.get(action_type, ())
        missing = [
            field
            for field in required
            if field not in payload_mapping
            or payload_mapping.get(field) is None
            or payload_mapping.get(field) == ""
            or payload_mapping.get(field) == []
            or payload_mapping.get(field) == {}
        ]
        if action_type == "orchestrate_execution":
            if not (
                _string(payload_mapping.get("continuity_ref"))
                or _string(payload_mapping.get("work_context_id"))
            ):
                missing.append("continuity_ref|work_context_id")
        if missing:
            return f"Missing required payload fields: {', '.join(sorted(set(missing)))}"
        return None

    def _build_commit_key(self, *, envelope: Any, request: Any) -> str:
        payload = {
            "control_thread_id": _string(getattr(request, "control_thread_id", None))
            or _string(getattr(request, "session_id", None)),
            "session_id": _string(getattr(request, "session_id", None)),
            "work_context_id": _string(getattr(request, "work_context_id", None))
            or _string(_mapping(getattr(envelope, "payload", None)).get("work_context_id")),
            "continuity_ref": _string(_mapping(getattr(envelope, "payload", None)).get("continuity_ref")),
            "action_type": _string(getattr(envelope, "action_type", None)),
            "payload": _mapping(getattr(envelope, "payload", None)),
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]

    def _persist_state(
        self,
        *,
        request: Any,
        state: MainBrainCommitState,
    ) -> MainBrainCommitState:
        session_id = _string(getattr(request, "session_id", None))
        user_id = _resolve_snapshot_user_id(request)
        control_thread_id = _string(getattr(request, "control_thread_id", None)) or session_id or None
        work_context_id = _string(getattr(request, "work_context_id", None)) or None
        normalized = self._decorate_state(
            request=request,
            state=state,
        )
        snapshot = self._load_snapshot(session_id=session_id, user_id=user_id)
        main_brain_payload = _mapping(snapshot.get("main_brain"))
        main_brain_payload["phase2_commit"] = normalized.model_dump(mode="json")
        snapshot["main_brain"] = main_brain_payload
        self._save_snapshot(session_id=session_id, user_id=user_id, snapshot=snapshot)
        if callable(self._dirty_marker) and not (
            normalized.status == "commit_deferred"
            and normalized.reason == "no_commit_action"
        ):
            self._dirty_marker(
                work_context_id=work_context_id,
                industry_instance_id=_string(getattr(request, "industry_instance_id", None)) or None,
                agent_id=_string(getattr(request, "agent_id", None)) or None,
            )
        return normalized

    def _decorate_state(
        self,
        *,
        request: Any,
        state: MainBrainCommitState,
    ) -> MainBrainCommitState:
        session_id = _string(getattr(request, "session_id", None))
        control_thread_id = _string(getattr(request, "control_thread_id", None)) or session_id or None
        work_context_id = _string(getattr(request, "work_context_id", None)) or None
        return state.model_copy(
            update={
                "control_thread_id": control_thread_id,
                "session_id": session_id or None,
                "work_context_id": work_context_id,
            },
        )

    def _load_snapshot(self, *, session_id: str, user_id: str) -> dict[str, Any]:
        if not session_id or not user_id:
            return {}
        merged_loader = getattr(self._session_backend, "load_merged_session_snapshot", None)
        if callable(merged_loader):
            payload = merged_loader(
                session_id=session_id,
                primary_user_id=user_id,
                allow_not_exist=True,
            )
            return dict(payload) if isinstance(payload, dict) else {}
        loader = getattr(self._session_backend, "load_session_snapshot", None)
        if not callable(loader):
            return {}
        payload = loader(session_id=session_id, user_id=user_id, allow_not_exist=True)
        return dict(payload) if isinstance(payload, dict) else {}

    def _save_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        snapshot: dict[str, Any],
    ) -> None:
        if not session_id or not user_id:
            return
        saver = getattr(self._session_backend, "save_session_snapshot", None)
        if not callable(saver):
            return
        saver(
            session_id=session_id,
            user_id=user_id,
            payload=dict(snapshot),
            source_ref="state:/main-brain-chat-session",
        )


__all__ = ["MainBrainCommitService"]
