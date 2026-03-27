# -*- coding: utf-8 -*-
"""Windows app cooperative adapter runtime metadata helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence

from ..models import EnvironmentMount, SessionMount
from .execution_path import (
    DEFAULT_PREFERRED_EXECUTION_PATH,
    DEFAULT_UI_FALLBACK_MODE,
)


class WindowsAppAdapterRuntime:
    """Records Windows app adapter availability into canonical environment metadata."""

    def __init__(self, environment_service) -> None:
        self._service = environment_service

    def register_adapter(
        self,
        *,
        session_mount_id: str,
        adapter_refs: str | Sequence[str],
        app_identity: str | None = None,
        control_channel: str | None = None,
        preferred_execution_path: str | None = None,
        ui_fallback_mode: str | None = None,
        adapter_gap_or_blocker: str | None = None,
    ) -> SessionMount:
        session = self._require_session(session_mount_id)
        environment = self._require_environment(session.environment_id)
        merged_refs = self._merge_refs(
            session.metadata.get("windows_app_adapter_refs"),
            session.metadata.get("app_adapter_refs"),
            environment.metadata.get("windows_app_adapter_refs"),
            environment.metadata.get("app_adapter_refs"),
            adapter_refs,
        )
        updates = {
            "windows_app_adapter_refs": merged_refs,
            "app_adapter_refs": merged_refs,
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
        if app_identity is not None:
            updates["app_identity"] = app_identity
        elif self._existing_string(session.metadata, environment.metadata, "app_identity"):
            updates["app_identity"] = self._existing_string(
                session.metadata,
                environment.metadata,
                "app_identity",
            )
        if control_channel is not None:
            updates["control_channel"] = control_channel
        elif self._existing_string(
            session.metadata,
            environment.metadata,
            "control_channel",
        ):
            updates["control_channel"] = self._existing_string(
                session.metadata,
                environment.metadata,
                "control_channel",
            )
        return self._persist(session=session, environment=environment, updates=updates)

    def clear_adapter(
        self,
        *,
        session_mount_id: str,
        adapter_refs: str | Sequence[str] | None = None,
        adapter_gap_or_blocker: str | None = None,
        preferred_execution_path: str | None = None,
        ui_fallback_mode: str | None = None,
    ) -> SessionMount:
        session = self._require_session(session_mount_id)
        environment = self._require_environment(session.environment_id)
        existing_refs = self._merge_refs(
            session.metadata.get("windows_app_adapter_refs"),
            session.metadata.get("app_adapter_refs"),
            environment.metadata.get("windows_app_adapter_refs"),
            environment.metadata.get("app_adapter_refs"),
        )
        refs_to_remove = set(self._normalize_refs(adapter_refs))
        remaining_refs = [
            ref for ref in existing_refs if not refs_to_remove or ref not in refs_to_remove
        ]
        updates = {
            "windows_app_adapter_refs": remaining_refs,
            "app_adapter_refs": remaining_refs,
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
        existing_identity = self._existing_string(
            session.metadata,
            environment.metadata,
            "app_identity",
        )
        if existing_identity is not None:
            updates["app_identity"] = existing_identity
        existing_channel = self._existing_string(
            session.metadata,
            environment.metadata,
            "control_channel",
        )
        if existing_channel is not None:
            updates["control_channel"] = existing_channel
        return self._persist(session=session, environment=environment, updates=updates)

    def snapshot(
        self,
        session_mount_id: str,
        *,
        limit: int = 20,
    ) -> dict[str, object] | None:
        return self._service.get_session_detail(session_mount_id, limit=limit)

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
            raise RuntimeError("WindowsAppAdapterRuntime requires a session repository")
        self._service._session_repository.upsert_session(updated_session)
        self._service._registry.upsert(updated_environment)
        return updated_session

    def _require_session(self, session_mount_id: str) -> SessionMount:
        session = self._service.get_session(session_mount_id)
        if session is None:
            raise LookupError(f"Session mount was not found: {session_mount_id}")
        return session

    def _require_environment(self, environment_id: str) -> EnvironmentMount:
        environment = self._service.get_environment(environment_id)
        if environment is None:
            raise LookupError(f"Environment mount was not found: {environment_id}")
        return environment

    def _merge_refs(self, *values: object) -> list[str]:
        refs: list[str] = []
        seen: set[str] = set()
        for ref in self._normalize_refs(values):
            if ref in seen:
                continue
            seen.add(ref)
            refs.append(ref)
        return refs

    def _normalize_refs(self, values: object) -> list[str]:
        if values is None:
            return []
        if isinstance(values, str):
            normalized = self._normalized(values)
            return [normalized] if normalized is not None else []
        if isinstance(values, tuple):
            items: Iterable[object] = values
        elif isinstance(values, list):
            items = values
        elif isinstance(values, Sequence):
            items = list(values)
        else:
            items = [values]
        refs: list[str] = []
        for item in items:
            if isinstance(item, (list, tuple, set)):
                refs.extend(self._normalize_refs(list(item)))
                continue
            normalized = self._normalized(item)
            if normalized is not None:
                refs.append(normalized)
        return refs

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
