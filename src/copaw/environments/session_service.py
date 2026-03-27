# -*- coding: utf-8 -*-
"""Session-facing environment queries and lifecycle helpers."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .models import EnvironmentMount, EnvironmentSummary, SessionMount

if TYPE_CHECKING:
    from .service import EnvironmentService


class EnvironmentSessionService:
    """Facade collaborator for environment/session read operations."""

    def __init__(self, service: EnvironmentService) -> None:
        self._service = service

    def list_environments(
        self,
        *,
        kind: str | None = None,
        limit: int | None = None,
    ) -> list[EnvironmentMount]:
        self._refresh_runtime_leases()
        mounts = self._service._registry.collect()
        if kind:
            mounts = [mount for mount in mounts if mount.kind == kind]
        mounts.sort(
            key=lambda item: item.last_active_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        if limit is not None and limit >= 0:
            return mounts[:limit]
        return mounts

    def get_environment(self, env_id: str) -> EnvironmentMount | None:
        self._refresh_runtime_leases()
        return self._service._registry.get(env_id)

    def summarize(self) -> EnvironmentSummary:
        self._refresh_runtime_leases()
        mounts = self._service._registry.collect()
        by_kind = Counter(mount.kind for mount in mounts)
        active = sum(1 for mount in mounts if mount.status == "active")
        return EnvironmentSummary(
            total=len(mounts),
            active=active,
            by_kind=dict(sorted(by_kind.items())),
        )

    def register_environment(
        self,
        *,
        ref: str | None,
        kind: str | None = None,
        status: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> EnvironmentMount | None:
        return self._service._registry.register(
            ref=ref,
            kind=kind,
            status=status,
            metadata=metadata,
            evidence_delta=0,
        )

    def touch_environment(
        self,
        *,
        ref: str | None,
        kind: str | None = None,
        status: str | None = None,
        metadata: dict[str, object] | None = None,
        last_active_at: datetime | None = None,
        evidence_delta: int = 1,
    ) -> EnvironmentMount | None:
        return self._service._registry.touch(
            ref=ref,
            kind=kind,
            status=status,
            metadata=metadata,
            last_active_at=last_active_at,
            evidence_delta=evidence_delta,
        )

    def close_environment(
        self,
        env_id: str,
        *,
        status: str = "closed",
    ) -> EnvironmentMount | None:
        return self._service._registry.close(env_id, status=status)

    def list_sessions(
        self,
        *,
        environment_id: str | None = None,
        channel: str | None = None,
        user_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[SessionMount]:
        if self._service._session_repository is None:
            return []
        self._refresh_runtime_leases()
        return self._service._session_repository.list_sessions(
            environment_id=environment_id,
            channel=channel,
            user_id=user_id,
            status=status,
            limit=limit,
        )

    def get_session(self, session_mount_id: str) -> SessionMount | None:
        if self._service._session_repository is None:
            return None
        self._refresh_runtime_leases()
        return self._service._session_repository.get_session(session_mount_id)

    def close_session(
        self,
        session_mount_id: str,
        *,
        status: str = "closed",
    ) -> SessionMount | None:
        if self._service._session_repository is None:
            return None
        self._service._lease_service.release_session_lease(
            session_mount_id,
            reason=f"session closed as {status}",
            release_status="released",
            validate_token=False,
        )
        return self._service._session_repository.close_session(
            session_mount_id,
            status=status,
        )

    def _refresh_runtime_leases(self) -> None:
        self._service._lease_service.recover_orphaned_leases()
        self._service._lease_service.reap_expired_leases()
