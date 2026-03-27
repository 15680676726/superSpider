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

        normalized_transport_ref = _normalize_string(transport_ref)
        normalized_status = _normalize_string(status)
        normalized_provider_session_ref = _normalize_string(provider_session_ref)
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
            "preferred_execution_path": normalized_path,
            "ui_fallback_mode": normalized_fallback,
            "adapter_gap_or_blocker": _normalize_string(adapter_gap_or_blocker),
            "browser_companion": {
                "available": available if isinstance(available, bool) else None,
                "status": normalized_status,
                "transport_ref": normalized_transport_ref,
                "provider_session_ref": normalized_provider_session_ref,
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
