# -*- coding: utf-8 -*-
"""Cooperative host watcher runtime helpers."""
from __future__ import annotations

from typing import Any

from ...app.runtime_events import RuntimeEvent, RuntimeEventBus
from ..models import EnvironmentMount, SessionMount
from ..repository import EnvironmentRepository, SessionMountRepository

_UNSET = object()
_READY_STATUSES = {
    "active",
    "attached",
    "available",
    "connected",
    "healthy",
    "ready",
    "running",
}
_DOWNLOAD_TOPICS = {"download", "filesystem"}
_DOWNLOAD_ACTIONS = {"download-completed", "download-finished"}


class HostWatcherRuntime:
    """Repository-backed watcher runtime surface for cooperative adapters."""

    def __init__(
        self,
        *,
        session_repository: SessionMountRepository,
        environment_repository: EnvironmentRepository,
        runtime_event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self._session_repository = session_repository
        self._environment_repository = environment_repository
        self._runtime_event_bus = runtime_event_bus

    def register_watchers(
        self,
        session_mount_id: str,
        *,
        filesystem: dict[str, Any] | None = None,
        downloads: dict[str, Any] | None = None,
        notifications: dict[str, Any] | None = None,
        adapter_gap_or_blocker: str | None | object = _UNSET,
    ) -> dict[str, Any]:
        session = self._require_session(session_mount_id)
        environment = self._require_environment(session.environment_id)
        metadata: dict[str, Any] = {}
        if filesystem is not None:
            metadata.update(
                self._family_metadata(
                    status_key="filesystem_watcher_status",
                    available_key="filesystem_watcher_available",
                    config=filesystem,
                )
            )
        if downloads is not None:
            metadata.update(
                self._family_metadata(
                    status_key="download_watcher_status",
                    available_key="download_watcher_available",
                    config=downloads,
                    include_download_policy=True,
                )
            )
        if notifications is not None:
            metadata.update(
                self._family_metadata(
                    status_key="notification_watcher_status",
                    available_key="notification_watcher_available",
                    config=notifications,
                )
            )
        if adapter_gap_or_blocker is not _UNSET:
            metadata["adapter_gap_or_blocker"] = adapter_gap_or_blocker
        self._touch_mounts(session=session, environment=environment, metadata=metadata)
        return self.snapshot(session_mount_id)

    def snapshot(self, session_mount_id: str) -> dict[str, Any]:
        session = self._require_session(session_mount_id)
        environment = self._get_environment(session.environment_id)
        session_metadata = dict(session.metadata)
        environment_metadata = dict(environment.metadata) if environment is not None else {}

        filesystem_status = self._pick_string(
            session_metadata.get("filesystem_watcher_status"),
            environment_metadata.get("filesystem_watcher_status"),
        )
        filesystem_available = self._pick_bool(
            session_metadata.get("filesystem_watcher_available"),
            environment_metadata.get("filesystem_watcher_available"),
        )
        if filesystem_available is None:
            filesystem_available = self._availability_from_status(filesystem_status)

        download_status = self._pick_string(
            session_metadata.get("download_watcher_status"),
            environment_metadata.get("download_watcher_status"),
        )
        download_available = self._pick_bool(
            session_metadata.get("download_watcher_available"),
            environment_metadata.get("download_watcher_available"),
        )
        if download_available is None:
            download_available = self._availability_from_status(download_status)
        download_policy = self._pick_string(
            session_metadata.get("download_policy"),
            environment_metadata.get("download_policy"),
        )

        notification_status = self._pick_string(
            session_metadata.get("notification_watcher_status"),
            environment_metadata.get("notification_watcher_status"),
        )
        notification_available = self._pick_bool(
            session_metadata.get("notification_watcher_available"),
            environment_metadata.get("notification_watcher_available"),
        )
        if notification_available is None:
            notification_available = self._availability_from_status(notification_status)

        available_families: list[str] = []
        unavailable_families: list[str] = []
        for family_name, family_available in (
            ("filesystem-watcher", filesystem_available),
            ("download-watcher", download_available),
            ("notification-watcher", notification_available),
        ):
            if family_available is True:
                available_families.append(family_name)
            elif family_available is False:
                unavailable_families.append(family_name)

        latest_download_event = self._latest_download_event(session)
        return {
            "session_mount_id": session.id,
            "environment_id": session.environment_id,
            "watchers": {
                "filesystem": {
                    "status": filesystem_status,
                    "available": filesystem_available,
                },
                "downloads": {
                    "status": download_status,
                    "available": download_available,
                    "download_policy": download_policy,
                    "last_download_event": latest_download_event,
                },
                "notifications": {
                    "status": notification_status,
                    "available": notification_available,
                },
            },
            "available_families": available_families,
            "unavailable_families": unavailable_families,
            "adapter_gap_or_blocker": self._pick_string(
                session_metadata.get("adapter_gap_or_blocker"),
                environment_metadata.get("adapter_gap_or_blocker"),
            ),
        }

    def emit_download_completed(
        self,
        session_mount_id: str,
        *,
        download_ref: str,
        filename: str | None = None,
        file_path: str | None = None,
        status: str = "completed",
        payload: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        session = self._require_session(session_mount_id)
        event_payload = self._base_payload(session)
        event_payload.update(
            {
                "download_ref": download_ref,
                "status": status,
            }
        )
        if filename is not None:
            event_payload["filename"] = filename
        if file_path is not None:
            event_payload["file_path"] = file_path
        if payload:
            event_payload.update(payload)
        return self._publish(topic="download", action="download-completed", payload=event_payload)

    def emit_notification(
        self,
        session_mount_id: str,
        *,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        session = self._require_session(session_mount_id)
        event_payload = self._base_payload(session)
        if payload:
            event_payload.update(payload)
        return self._publish(topic="notification", action=action, payload=event_payload)

    def _family_metadata(
        self,
        *,
        status_key: str,
        available_key: str,
        config: dict[str, Any],
        include_download_policy: bool = False,
    ) -> dict[str, Any]:
        status = self._pick_string(config.get("status"))
        available = self._pick_bool(config.get("available"))
        metadata: dict[str, Any] = {}
        if status is not None:
            metadata[status_key] = status
            metadata[available_key] = (
                available
                if available is not None
                else self._availability_from_status(status)
            )
        elif available is not None:
            metadata[available_key] = available
        if include_download_policy and "download_policy" in config:
            metadata["download_policy"] = config.get("download_policy")
        return metadata

    def _touch_mounts(
        self,
        *,
        session: SessionMount,
        environment: EnvironmentMount,
        metadata: dict[str, Any],
    ) -> None:
        if not metadata:
            return
        self._session_repository.touch_session(
            session_mount_id=session.id,
            environment_id=session.environment_id,
            channel=session.channel,
            session_id=session.session_id,
            user_id=session.user_id,
            status=session.status,
            metadata=metadata,
        )
        self._environment_repository.touch_environment(
            env_id=environment.id,
            kind=environment.kind,
            display_name=environment.display_name,
            ref=environment.ref,
            status=environment.status,
            metadata=metadata,
            evidence_delta=0,
        )

    def _base_payload(self, session: SessionMount) -> dict[str, Any]:
        return {
            "session_mount_id": session.id,
            "environment_id": session.environment_id,
        }

    def _latest_download_event(
        self,
        session: SessionMount,
    ) -> dict[str, Any] | None:
        if self._runtime_event_bus is None:
            return None
        events = self._runtime_event_bus.list_events(limit=500)
        for event in reversed(events):
            if event.topic not in _DOWNLOAD_TOPICS or event.action not in _DOWNLOAD_ACTIONS:
                continue
            payload = dict(event.payload or {})
            if not self._matches_session(event, session):
                continue
            return {
                "event_name": event.event_name,
                "download_ref": self._pick_string(
                    payload.get("download_ref"),
                    payload.get("download_id"),
                ),
                "filename": self._pick_string(payload.get("filename")),
            }
        return None

    def _matches_session(self, event: RuntimeEvent, session: SessionMount) -> bool:
        payload = dict(event.payload or {})
        return (
            payload.get("session_mount_id") == session.id
            or payload.get("environment_id") == session.environment_id
        )

    def _publish(
        self,
        *,
        topic: str,
        action: str,
        payload: dict[str, Any],
    ) -> RuntimeEvent:
        if self._runtime_event_bus is None:
            raise RuntimeError("RuntimeEventBus is required to publish watcher events.")
        return self._runtime_event_bus.publish(topic=topic, action=action, payload=payload)

    def _require_session(self, session_mount_id: str) -> SessionMount:
        session = self._session_repository.get_session(session_mount_id)
        if session is None:
            raise ValueError(f"Unknown session mount: {session_mount_id}")
        return session

    def _get_environment(self, environment_id: str) -> EnvironmentMount | None:
        return self._environment_repository.get_environment(environment_id)

    def _require_environment(self, environment_id: str) -> EnvironmentMount:
        environment = self._get_environment(environment_id)
        if environment is None:
            raise ValueError(f"Unknown environment mount: {environment_id}")
        return environment

    @staticmethod
    def _pick_string(*values: object) -> str | None:
        for value in values:
            if isinstance(value, str):
                return value
        return None

    @staticmethod
    def _pick_bool(*values: object) -> bool | None:
        for value in values:
            if isinstance(value, bool):
                return value
        return None

    @staticmethod
    def _availability_from_status(status: str | None) -> bool | None:
        if status is None:
            return None
        normalized = status.strip().lower()
        if not normalized:
            return None
        if normalized in _READY_STATUSES:
            return True
        return False


CooperativeWatcherRuntimeService = HostWatcherRuntime

__all__ = ["HostWatcherRuntime", "CooperativeWatcherRuntimeService"]
