# -*- coding: utf-8 -*-
"""Real-user browser attach runtime metadata helpers."""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import EnvironmentMount, SessionMount
from .execution_path import (
    DEFAULT_PREFERRED_EXECUTION_PATH,
    DEFAULT_UI_FALLBACK_MODE,
)


class BrowserAttachRuntime:
    """Records real-user browser attach transport facts on canonical metadata."""

    def __init__(self, environment_service) -> None:
        self._service = environment_service

    def register_transport(
        self,
        *,
        session_mount_id: str,
        transport_ref: str | None,
        status: str | None = None,
        browser_session_ref: str | None = None,
        browser_scope_ref: str | None = None,
        reconnect_token: str | None = None,
        preferred_execution_path: str | None = None,
        ui_fallback_mode: str | None = None,
        adapter_gap_or_blocker: str | None = None,
    ) -> SessionMount:
        session = self._require_session(session_mount_id)
        environment = self._require_environment(session.environment_id)
        updates = {
            "browser_attach_transport_ref": self._normalized(transport_ref)
            or self._existing_string(
                session.metadata,
                environment.metadata,
                "browser_attach_transport_ref",
            ),
            # Keep legacy projection keys aligned until all read paths stop
            # consulting the pre-browser_attach continuity metadata.
            "attach_transport_ref": self._normalized(transport_ref)
            or self._existing_string(
                session.metadata,
                environment.metadata,
                "browser_attach_transport_ref",
            ),
            "browser_attach_status": self._normalized(status)
            or self._existing_string(
                session.metadata,
                environment.metadata,
                "browser_attach_status",
            ),
            "browser_attach_session_ref": self._normalized(browser_session_ref)
            or self._existing_string(
                session.metadata,
                environment.metadata,
                "browser_attach_session_ref",
            ),
            "attach_session_ref": self._normalized(browser_session_ref)
            or self._existing_string(
                session.metadata,
                environment.metadata,
                "browser_attach_session_ref",
            ),
            "browser_attach_scope_ref": self._normalized(browser_scope_ref)
            or self._existing_string(
                session.metadata,
                environment.metadata,
                "browser_attach_scope_ref",
            ),
            "attach_scope_ref": self._normalized(browser_scope_ref)
            or self._existing_string(
                session.metadata,
                environment.metadata,
                "browser_attach_scope_ref",
            ),
            "browser_attach_reconnect_token": self._normalized(reconnect_token)
            or self._existing_string(
                session.metadata,
                environment.metadata,
                "browser_attach_reconnect_token",
            ),
            "attach_reconnect_token": self._normalized(reconnect_token)
            or self._existing_string(
                session.metadata,
                environment.metadata,
                "browser_attach_reconnect_token",
            ),
            "preferred_execution_path": (
                self._normalized(preferred_execution_path)
                or self._existing_string(
                    session.metadata,
                    environment.metadata,
                    "preferred_execution_path",
                )
                or DEFAULT_PREFERRED_EXECUTION_PATH
            ),
            "ui_fallback_mode": (
                self._normalized(ui_fallback_mode)
                or self._existing_string(
                    session.metadata,
                    environment.metadata,
                    "ui_fallback_mode",
                )
                or DEFAULT_UI_FALLBACK_MODE
            ),
            "adapter_gap_or_blocker": self._normalized(adapter_gap_or_blocker),
        }
        return self._persist(session=session, environment=environment, updates=updates)

    def clear_transport(
        self,
        *,
        session_mount_id: str,
        adapter_gap_or_blocker: str | None = None,
        preferred_execution_path: str | None = None,
        ui_fallback_mode: str | None = None,
    ) -> SessionMount:
        session = self._require_session(session_mount_id)
        environment = self._require_environment(session.environment_id)
        updates = {
            "browser_attach_transport_ref": None,
            "attach_transport_ref": None,
            "browser_attach_status": None,
            "browser_attach_session_ref": None,
            "attach_session_ref": None,
            "browser_attach_scope_ref": None,
            "attach_scope_ref": None,
            "browser_attach_reconnect_token": None,
            "attach_reconnect_token": None,
            "preferred_execution_path": (
                self._normalized(preferred_execution_path)
                or self._existing_string(
                    session.metadata,
                    environment.metadata,
                    "preferred_execution_path",
                )
                or DEFAULT_PREFERRED_EXECUTION_PATH
            ),
            "ui_fallback_mode": (
                self._normalized(ui_fallback_mode)
                or self._existing_string(
                    session.metadata,
                    environment.metadata,
                    "ui_fallback_mode",
                )
                or DEFAULT_UI_FALLBACK_MODE
            ),
            "adapter_gap_or_blocker": self._normalized(adapter_gap_or_blocker),
        }
        return self._persist(session=session, environment=environment, updates=updates)

    def snapshot(
        self,
        *,
        session_mount_id: str | None = None,
        environment_id: str | None = None,
    ) -> dict[str, object]:
        session = self._resolve_session(
            session_mount_id=session_mount_id,
            environment_id=environment_id,
        )
        environment = self._require_environment(session.environment_id)
        session_metadata = dict(session.metadata)
        environment_metadata = dict(environment.metadata)
        return {
            "environment_id": environment.id,
            "session_mount_id": session.id,
            "preferred_execution_path": (
                self._existing_string(
                    session_metadata,
                    environment_metadata,
                    "preferred_execution_path",
                )
                or DEFAULT_PREFERRED_EXECUTION_PATH
            ),
            "ui_fallback_mode": (
                self._existing_string(
                    session_metadata,
                    environment_metadata,
                    "ui_fallback_mode",
                )
                or DEFAULT_UI_FALLBACK_MODE
            ),
            "adapter_gap_or_blocker": self._existing_string(
                session_metadata,
                environment_metadata,
                "adapter_gap_or_blocker",
            ),
            "browser_attach": {
                "transport_ref": self._existing_string(
                    session_metadata,
                    environment_metadata,
                    "browser_attach_transport_ref",
                ),
                "status": self._existing_string(
                    session_metadata,
                    environment_metadata,
                    "browser_attach_status",
                ),
                "session_ref": self._existing_string(
                    session_metadata,
                    environment_metadata,
                    "browser_attach_session_ref",
                ),
                "scope_ref": self._existing_string(
                    session_metadata,
                    environment_metadata,
                    "browser_attach_scope_ref",
                ),
                "reconnect_token": self._existing_string(
                    session_metadata,
                    environment_metadata,
                    "browser_attach_reconnect_token",
                ),
            },
        }

    def _persist(
        self,
        *,
        session: SessionMount,
        environment: EnvironmentMount,
        updates: dict[str, object],
    ) -> SessionMount:
        timestamp = datetime.now(timezone.utc)
        session_metadata = dict(session.metadata)
        session_metadata.update(updates)
        environment_metadata = dict(environment.metadata)
        environment_metadata.update(updates)

        updated_session = session.model_copy(
            update={
                "metadata": session_metadata,
                "last_active_at": timestamp,
            },
        )
        updated_environment = environment.model_copy(
            update={
                "metadata": environment_metadata,
                "last_active_at": timestamp,
            },
        )
        if self._service._session_repository is None:
            raise RuntimeError("BrowserAttachRuntime requires a session repository")
        self._service._session_repository.upsert_session(updated_session)
        self._service._registry.upsert(updated_environment)
        return updated_session

    def _require_session(self, session_mount_id: str) -> SessionMount:
        session = self._service.get_session(session_mount_id)
        if session is None:
            raise KeyError(f"Unknown session mount: {session_mount_id}")
        return session

    def _require_environment(self, environment_id: str) -> EnvironmentMount:
        environment = self._service.get_environment(environment_id)
        if environment is None:
            raise KeyError(f"Unknown environment mount: {environment_id}")
        return environment

    def _resolve_session(
        self,
        *,
        session_mount_id: str | None,
        environment_id: str | None,
    ) -> SessionMount:
        if session_mount_id is not None:
            return self._require_session(session_mount_id)
        if environment_id is not None:
            sessions = self._service.list_sessions(
                environment_id=environment_id,
                limit=1,
            )
            if sessions:
                return sessions[0]
            raise KeyError(f"Unknown environment mount: {environment_id}")
        raise KeyError("Unknown session mount: None")

    def _existing_string(
        self,
        session_metadata: dict[str, object],
        environment_metadata: dict[str, object],
        key: str,
    ) -> str | None:
        return self._normalized(session_metadata.get(key)) or self._normalized(
            environment_metadata.get(key),
        )

    def _normalized(self, value: object) -> str | None:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
        return None
