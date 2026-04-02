# -*- coding: utf-8 -*-
"""Browser companion runtime backed by environment/session metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models import EnvironmentMount, SessionMount
from ..repository import EnvironmentRepository, SessionMountRepository

_UNSET = object()
_READY_STATUSES = {"ready", "attached", "available", "healthy"}
_DEFAULT_COOPERATIVE_PATH = "cooperative-native-first"
_DEFAULT_SEMANTIC_PATH = "semantic-operator-second"
_DEFAULT_UI_FALLBACK = "ui-fallback-last"
_SHARED_OPERATOR_ABORT_STATE_KEY = "operator_abort_state"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_string(value: object) -> str | None:
    if value is _UNSET or value is None:
        return None
    text = str(value).strip()
    return text or None


def _infer_available(*, transport_ref: str | None, status: str | None) -> bool | None:
    if transport_ref:
        return True
    if status is None:
        return None
    return status.strip().lower() in _READY_STATUSES


def _resolve_execution_path(
    *,
    explicit: str | None,
    available: bool | None,
) -> str:
    if explicit:
        return explicit
    if available is True:
        return _DEFAULT_COOPERATIVE_PATH
    return _DEFAULT_SEMANTIC_PATH


def _resolve_shared_operator_abort_state(
    *,
    session_metadata: dict[str, Any],
    environment_metadata: dict[str, Any],
) -> dict[str, object]:
    raw = session_metadata.get(_SHARED_OPERATOR_ABORT_STATE_KEY)
    if not isinstance(raw, dict):
        raw = environment_metadata.get(_SHARED_OPERATOR_ABORT_STATE_KEY)
    if not isinstance(raw, dict):
        return {}
    channel = _normalize_string(raw.get("channel")) or _normalize_string(
        raw.get("operator_abort_channel"),
    )
    requested = bool(
        raw.get("requested")
        if "requested" in raw
        else raw.get("operator_abort_requested"),
    )
    requested_at = _normalize_string(raw.get("requested_at"))
    reason = (
        _normalize_string(raw.get("reason"))
        or _normalize_string(raw.get("abort_reason"))
        or channel
    )
    state: dict[str, object] = {}
    if channel is not None:
        state["channel"] = channel
    if requested:
        state["requested"] = True
    if reason is not None:
        state["reason"] = reason
    if requested_at is not None:
        state["requested_at"] = requested_at
    return state


def _abort_channels_match(
    *,
    guardrail_channel: object,
    shared_channel: object,
) -> bool:
    normalized_guardrail_channel = _normalize_string(guardrail_channel)
    normalized_shared_channel = _normalize_string(shared_channel)
    if normalized_guardrail_channel is None or normalized_shared_channel is None:
        return True
    return normalized_guardrail_channel == normalized_shared_channel


def _merge_execution_guardrails(
    *,
    guardrails: object,
    session_metadata: dict[str, Any],
    environment_metadata: dict[str, Any],
) -> dict[str, object]:
    merged = dict(guardrails) if isinstance(guardrails, dict) else {}
    shared_abort_state = _resolve_shared_operator_abort_state(
        session_metadata=session_metadata,
        environment_metadata=environment_metadata,
    )
    if not shared_abort_state.get("requested"):
        return merged
    if not _abort_channels_match(
        guardrail_channel=merged.get("operator_abort_channel"),
        shared_channel=shared_abort_state.get("channel"),
    ):
        return merged
    if shared_abort_state.get("channel") is not None and _normalize_string(
        merged.get("operator_abort_channel"),
    ) is None:
        merged["operator_abort_channel"] = shared_abort_state["channel"]
    merged["operator_abort_requested"] = True
    reason = _normalize_string(merged.get("abort_reason")) or _normalize_string(
        shared_abort_state.get("reason"),
    )
    if reason is not None:
        merged["abort_reason"] = reason
    if shared_abort_state.get("requested_at") is not None:
        merged.setdefault("operator_abort_requested_at", shared_abort_state["requested_at"])
    return merged


class BrowserCompanionRuntime:
    """Persists browser companion facts on EnvironmentMount/SessionMount metadata."""

    def __init__(
        self,
        *,
        environment_repository: EnvironmentRepository,
        session_repository: SessionMountRepository,
        runtime_event_bus: object | None = None,
    ) -> None:
        self._environment_repository = environment_repository
        self._session_repository = session_repository
        self._runtime_event_bus = runtime_event_bus

    def register_companion(
        self,
        *,
        environment_id: str | None = None,
        session_mount_id: str | None = None,
        transport_ref: object = _UNSET,
        status: object = _UNSET,
        available: bool | None = None,
        preferred_execution_path: object = _UNSET,
        ui_fallback_mode: object = _UNSET,
        adapter_gap_or_blocker: object = _UNSET,
        provider_session_ref: object = _UNSET,
        execution_guardrails: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        environment, session = self._resolve_mounts(
            environment_id=environment_id,
            session_mount_id=session_mount_id,
        )
        normalized_transport_ref = _normalize_string(transport_ref)
        normalized_status = _normalize_string(status)
        resolved_available = (
            available
            if available is not None
            else _infer_available(
                transport_ref=normalized_transport_ref,
                status=normalized_status,
            )
        )
        normalized_path = _resolve_execution_path(
            explicit=_normalize_string(preferred_execution_path),
            available=resolved_available,
        )
        normalized_fallback = (
            _normalize_string(ui_fallback_mode) or _DEFAULT_UI_FALLBACK
        )
        normalized_gap = _normalize_string(adapter_gap_or_blocker)
        normalized_provider_session_ref = _normalize_string(provider_session_ref)

        update_payload = {
            "browser_companion_transport_ref": normalized_transport_ref,
            "browser_companion_status": normalized_status,
            "browser_companion_available": resolved_available,
            "preferred_execution_path": normalized_path,
            "ui_fallback_mode": normalized_fallback,
            "adapter_gap_or_blocker": normalized_gap,
        }
        existing_guardrails = None
        if session is not None:
            existing_guardrails = session.metadata.get("browser_execution_guardrails")
        if not isinstance(existing_guardrails, dict) and environment is not None:
            existing_guardrails = environment.metadata.get("browser_execution_guardrails")
        if execution_guardrails is not None:
            update_payload["browser_execution_guardrails"] = dict(execution_guardrails)
        elif isinstance(existing_guardrails, dict):
            update_payload["browser_execution_guardrails"] = dict(existing_guardrails)
        if provider_session_ref is not _UNSET:
            update_payload["provider_session_ref"] = normalized_provider_session_ref

        if environment is not None:
            self._touch_environment(environment, metadata=update_payload)
        if session is not None:
            self._touch_session(session, metadata=update_payload)

        snapshot = self.snapshot(
            environment_id=environment.id if environment is not None else environment_id,
            session_mount_id=session.id if session is not None else session_mount_id,
        )
        self._publish_event(
            action="browser_companion_updated",
            payload={
                "environment_id": snapshot["environment_id"],
                "session_mount_id": snapshot["session_mount_id"],
                "preferred_execution_path": snapshot["preferred_execution_path"],
                "ui_fallback_mode": snapshot["ui_fallback_mode"],
                "adapter_gap_or_blocker": snapshot["adapter_gap_or_blocker"],
                "browser_companion": snapshot["browser_companion"],
            },
        )
        return snapshot

    def clear_companion(
        self,
        *,
        environment_id: str | None = None,
        session_mount_id: str | None = None,
        adapter_gap_or_blocker: str | None = None,
    ) -> dict[str, Any]:
        environment, session = self._resolve_mounts(
            environment_id=environment_id,
            session_mount_id=session_mount_id,
        )
        update_payload = {
            "browser_companion_transport_ref": None,
            "browser_companion_status": None,
            "browser_companion_available": False,
            "preferred_execution_path": _DEFAULT_SEMANTIC_PATH,
            "ui_fallback_mode": _DEFAULT_UI_FALLBACK,
            "adapter_gap_or_blocker": (
                _normalize_string(adapter_gap_or_blocker) or "Browser companion cleared."
            ),
            "provider_session_ref": None,
        }
        existing_guardrails = None
        if session is not None:
            existing_guardrails = session.metadata.get("browser_execution_guardrails")
        if not isinstance(existing_guardrails, dict) and environment is not None:
            existing_guardrails = environment.metadata.get("browser_execution_guardrails")
        if isinstance(existing_guardrails, dict):
            update_payload["browser_execution_guardrails"] = dict(existing_guardrails)
        if environment is not None:
            self._touch_environment(environment, metadata=update_payload)
        if session is not None:
            self._touch_session(session, metadata=update_payload)
        snapshot = self.snapshot(
            environment_id=environment.id if environment is not None else environment_id,
            session_mount_id=session.id if session is not None else session_mount_id,
        )
        self._publish_event(
            action="browser_companion_cleared",
            payload={
                "environment_id": snapshot["environment_id"],
                "session_mount_id": snapshot["session_mount_id"],
                "preferred_execution_path": snapshot["preferred_execution_path"],
                "ui_fallback_mode": snapshot["ui_fallback_mode"],
                "adapter_gap_or_blocker": snapshot["adapter_gap_or_blocker"],
                "browser_companion": snapshot["browser_companion"],
            },
        )
        return snapshot

    def snapshot(
        self,
        *,
        environment_id: str | None = None,
        session_mount_id: str | None = None,
    ) -> dict[str, Any]:
        environment, session = self._resolve_mounts(
            environment_id=environment_id,
            session_mount_id=session_mount_id,
            require_existing=False,
        )
        environment_metadata = dict(getattr(environment, "metadata", None) or {})
        session_metadata = dict(getattr(session, "metadata", None) or {})

        transport_ref = self._first_present(
            session_metadata,
            environment_metadata,
            "browser_companion_transport_ref",
        )
        status = self._first_present(
            session_metadata,
            environment_metadata,
            "browser_companion_status",
        )
        available = self._first_present(
            session_metadata,
            environment_metadata,
            "browser_companion_available",
        )
        if available is None:
            available = _infer_available(
                transport_ref=_normalize_string(transport_ref),
                status=_normalize_string(status),
            )
        preferred_execution_path = self._first_present(
            session_metadata,
            environment_metadata,
            "preferred_execution_path",
        )
        ui_fallback_mode = self._first_present(
            session_metadata,
            environment_metadata,
            "ui_fallback_mode",
        )
        adapter_gap_or_blocker = self._first_present(
            session_metadata,
            environment_metadata,
            "adapter_gap_or_blocker",
        )
        provider_session_ref = self._first_present(
            session_metadata,
            environment_metadata,
            "provider_session_ref",
        )
        execution_guardrails = self._first_present(
            session_metadata,
            environment_metadata,
            "browser_execution_guardrails",
        )
        work_context_id = self._first_present(
            session_metadata,
            environment_metadata,
            "work_context_id",
        )

        normalized_transport_ref = _normalize_string(transport_ref)
        normalized_status = _normalize_string(status)
        normalized_provider_session_ref = _normalize_string(provider_session_ref)
        normalized_work_context_id = _normalize_string(work_context_id)
        normalized_path = _resolve_execution_path(
            explicit=_normalize_string(preferred_execution_path),
            available=available if isinstance(available, bool) else None,
        )
        normalized_fallback = (
            _normalize_string(ui_fallback_mode) or _DEFAULT_UI_FALLBACK
        )

        return {
            "environment_id": environment.id if environment is not None else None,
            "session_mount_id": session.id if session is not None else None,
            "work_context_id": normalized_work_context_id,
            "preferred_execution_path": normalized_path,
            "ui_fallback_mode": normalized_fallback,
            "adapter_gap_or_blocker": _normalize_string(adapter_gap_or_blocker),
            "browser_companion": {
                "available": available if isinstance(available, bool) else None,
                "status": normalized_status,
                "transport_ref": normalized_transport_ref,
                "provider_session_ref": normalized_provider_session_ref,
                "work_context_id": normalized_work_context_id,
                "execution_guardrails": _merge_execution_guardrails(
                    guardrails=execution_guardrails,
                    session_metadata=session_metadata,
                    environment_metadata=environment_metadata,
                ),
            },
        }

    def _resolve_mounts(
        self,
        *,
        environment_id: str | None,
        session_mount_id: str | None,
        require_existing: bool = True,
    ) -> tuple[EnvironmentMount | None, SessionMount | None]:
        session = None
        if session_mount_id is not None:
            session = self._session_repository.get_session(session_mount_id)
            if session is None and require_existing:
                raise KeyError(f"Unknown session mount: {session_mount_id}")
        resolved_environment_id = (
            session.environment_id if session is not None else environment_id
        )
        environment = None
        if resolved_environment_id is not None:
            environment = self._environment_repository.get_environment(resolved_environment_id)
            if environment is None and require_existing:
                raise KeyError(f"Unknown environment mount: {resolved_environment_id}")
        if require_existing and environment is None and session is None:
            raise ValueError("environment_id or session_mount_id is required")
        return environment, session

    def _touch_environment(
        self,
        environment: EnvironmentMount,
        *,
        metadata: dict[str, object],
    ) -> None:
        self._environment_repository.touch_environment(
            env_id=environment.id,
            kind=environment.kind,
            display_name=environment.display_name,
            ref=environment.ref,
            status=environment.status,
            metadata=metadata,
            last_active_at=_utc_now(),
            evidence_delta=0,
        )

    def _touch_session(
        self,
        session: SessionMount,
        *,
        metadata: dict[str, object],
    ) -> None:
        self._session_repository.touch_session(
            session_mount_id=session.id,
            environment_id=session.environment_id,
            channel=session.channel,
            session_id=session.session_id,
            user_id=session.user_id,
            status=session.status,
            metadata=metadata,
            last_active_at=_utc_now(),
        )

    def _publish_event(
        self,
        *,
        action: str,
        payload: dict[str, object],
    ) -> None:
        if self._runtime_event_bus is None:
            return
        publisher = getattr(self._runtime_event_bus, "publish", None)
        if not callable(publisher):
            return
        publisher(
            topic="cooperative_adapter",
            action=action,
            payload=payload,
        )

    def _first_present(
        self,
        session_metadata: dict[str, object],
        environment_metadata: dict[str, object],
        key: str,
    ) -> object | None:
        session_value = session_metadata.get(key)
        if isinstance(session_value, str):
            session_value = session_value.strip() or None
        if session_value is not None:
            return session_value
        environment_value = environment_metadata.get(key)
        if isinstance(environment_value, str):
            environment_value = environment_value.strip() or None
        return environment_value
