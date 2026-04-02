# -*- coding: utf-8 -*-
"""Lease, recovery, and live-handle coordination for environments."""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import uuid4
from weakref import WeakSet

from ..state import AgentLeaseRecord
from .models import SessionMount

if TYPE_CHECKING:
    from .service import EnvironmentService

_ACTIVE_LEASE_SERVICES: WeakSet = WeakSet()


class EnvironmentLeaseService:
    """Focused collaborator for session/resource/actor leases."""

    def __init__(self, service: EnvironmentService) -> None:
        self._service = service
        self._session_handle_restorers: dict[str, object] = {}
        _ACTIVE_LEASE_SERVICES.add(self)

    def register_session_handle_restorer(
        self,
        channel: str,
        restorer: object | None,
    ) -> None:
        key = (channel or "").strip()
        if not key:
            return
        if restorer is None:
            self._session_handle_restorers.pop(key, None)
            return
        self._session_handle_restorers[key] = restorer

    def acquire_session_lease(
        self,
        *,
        channel: str,
        session_id: str,
        user_id: str | None = None,
        owner: str,
        ttl_seconds: int | None = None,
        handle: object | None = None,
        metadata: dict[str, object] | None = None,
    ) -> SessionMount:
        return self._acquire_leased_session(
            channel=channel,
            session_id=session_id,
            user_id=user_id,
            owner=owner,
            ttl_seconds=ttl_seconds,
            handle=handle,
            metadata=metadata,
            ref=f"session:{channel}:{session_id}",
            conflict_label=f"Session '{_session_mount_id(channel=channel, session_id=session_id)}'",
            event_topic="session",
            event_payload={
                "channel": channel,
                "session_id": session_id,
            },
        )

    def heartbeat_session_lease(
        self,
        session_mount_id: str,
        *,
        lease_token: str,
        ttl_seconds: int | None = None,
        handle: object | None = None,
        metadata: dict[str, object] | None = None,
    ) -> SessionMount:
        session_repository = self._service._session_repository
        if session_repository is None:
            raise RuntimeError("Session repository is not available")

        now = _utc_now()
        session = session_repository.get_session(session_mount_id)
        if session is None:
            raise KeyError(f"Session '{session_mount_id}' not found")
        if session.lease_token and session.lease_token != lease_token:
            raise ValueError(f"Lease token mismatch for session '{session_mount_id}'")

        expires_at = now + timedelta(
            seconds=ttl_seconds or self._service._lease_ttl_seconds,
        )
        live_handle_ref = session.live_handle_ref
        descriptor = self.build_live_handle_descriptor(
            channel=session.channel,
            session_id=session.session_id,
            user_id=session.user_id,
            owner=session.lease_owner,
            handle=handle,
            metadata=session.metadata,
        )
        if handle is not None or not self._service._registry.has_live_handle(
            session.environment_id,
        ):
            live_handle_ref = self._service._registry.attach_live_handle(
                session.environment_id,
                handle=handle
                or {
                    "session_mount_id": session_mount_id,
                    "owner": session.lease_owner,
                },
                owner=session.lease_owner,
                lease_token=lease_token,
                handle_ref=live_handle_ref,
                descriptor=descriptor,
                seen_at=now,
            )
        else:
            self._service._registry.touch_live_handle(
                session.environment_id,
                lease_token=lease_token,
                seen_at=now,
                descriptor=descriptor,
            )

        merged_metadata = {**session.metadata, **(metadata or {})}
        merged_metadata["lease_runtime"] = self.build_lease_runtime_metadata(
            owner=session.lease_owner,
            status="leased",
            descriptor=descriptor,
            token=lease_token,
            seen_at=now,
            expires_at=expires_at,
        )
        updated = session.model_copy(
            update={
                "last_active_at": now,
                "metadata": merged_metadata,
                "lease_status": "leased",
                "lease_expires_at": expires_at,
                "live_handle_ref": live_handle_ref,
            },
        )
        session_repository.upsert_session(updated)
        self._sync_environment_lease(
            updated.environment_id,
            owner=updated.lease_owner,
            lease_token=lease_token,
            lease_status="leased",
            live_handle_ref=live_handle_ref,
            last_active_at=now,
            expires_at=expires_at,
        )
        self._publish_runtime_event(
            topic="session",
            action="heartbeat",
            payload={
                "session_mount_id": updated.id,
                "environment_id": updated.environment_id,
                "lease_status": updated.lease_status,
                "live_handle_ref": updated.live_handle_ref,
            },
        )
        return updated

    def release_session_lease(
        self,
        session_mount_id: str,
        *,
        lease_token: str | None = None,
        reason: str | None = None,
        release_status: str = "released",
        validate_token: bool = True,
    ) -> SessionMount | None:
        session_repository = self._service._session_repository
        if session_repository is None:
            return None

        now = _utc_now()
        session = session_repository.get_session(session_mount_id)
        if session is None:
            return None
        if (
            validate_token
            and session.lease_token
            and lease_token is not None
            and session.lease_token != lease_token
        ):
            raise ValueError(f"Lease token mismatch for session '{session_mount_id}'")

        self._service._registry.detach_live_handle(session.environment_id)
        metadata = dict(session.metadata)
        if reason:
            metadata["lease_release_reason"] = reason
        metadata["lease_runtime"] = self.build_lease_runtime_metadata(
            owner=None,
            status=release_status,
            descriptor=self.lease_runtime_descriptor(metadata),
            token=None,
            seen_at=now,
            expires_at=now,
        )
        updated = session.model_copy(
            update={
                "last_active_at": now,
                "metadata": metadata,
                "lease_status": release_status,
                "lease_token": None,
                "lease_expires_at": now,
                "live_handle_ref": None,
            },
        )
        session_repository.upsert_session(updated)
        self._sync_environment_lease(
            session.environment_id,
            owner=None,
            lease_token=None,
            lease_status=release_status,
            live_handle_ref=None,
            last_active_at=now,
            expires_at=now,
        )
        self._publish_runtime_event(
            topic="session",
            action=release_status,
            payload={
                "session_mount_id": updated.id,
                "environment_id": updated.environment_id,
                "lease_status": updated.lease_status,
                "reason": reason,
            },
        )
        return updated

    def force_release_session_lease(
        self,
        session_mount_id: str,
        *,
        reason: str = "forced release",
    ) -> SessionMount | None:
        return self.release_session_lease(
            session_mount_id,
            lease_token=None,
            reason=reason,
            release_status="released",
            validate_token=False,
        )

    def set_shared_operator_abort_state(
        self,
        session_mount_id: str,
        *,
        channel: str | None = None,
        reason: str | None = None,
    ) -> SessionMount:
        now = _utc_now()
        abort_state = {
            "requested": True,
            "requested_at": now.isoformat(),
            **(
                {"channel": str(channel).strip()}
                if isinstance(channel, str) and channel.strip()
                else {}
            ),
            **(
                {"reason": str(reason).strip()}
                if isinstance(reason, str) and reason.strip()
                else {}
            ),
        }
        updated = self._update_shared_session_environment_metadata(
            session_mount_id,
            metadata_patch={"operator_abort_state": abort_state},
        )
        self._publish_runtime_event(
            topic="session",
            action="operator-abort-requested",
            payload={
                "session_mount_id": updated.id,
                "environment_id": updated.environment_id,
                "operator_abort_state": abort_state,
            },
        )
        return updated

    def clear_shared_operator_abort_state(
        self,
        session_mount_id: str,
        *,
        channel: str | None = None,
        reason: str | None = None,
    ) -> SessionMount:
        session_repository = self._service._session_repository
        if session_repository is None:
            raise RuntimeError("Session repository is not available")
        existing = session_repository.get_session(session_mount_id)
        if existing is None:
            raise KeyError(f"Session '{session_mount_id}' not found")
        existing_state = _mapping(dict(existing.metadata).get("operator_abort_state"))
        now = _utc_now()
        resolved_channel = (
            str(channel).strip()
            if isinstance(channel, str) and channel.strip()
            else None
        ) or (
            str(existing_state.get("channel")).strip()
            if isinstance(existing_state.get("channel"), str)
            and str(existing_state.get("channel")).strip()
            else None
        )
        abort_state = {
            "requested": False,
            "requested_at": now.isoformat(),
            **({"channel": resolved_channel} if resolved_channel is not None else {}),
            "reason": (
                str(reason).strip()
                if isinstance(reason, str) and reason.strip()
                else "operator abort cleared"
            ),
        }
        updated = self._update_shared_session_environment_metadata(
            session_mount_id,
            metadata_patch={"operator_abort_state": abort_state},
        )
        self._publish_runtime_event(
            topic="session",
            action="operator-abort-cleared",
            payload={
                "session_mount_id": updated.id,
                "environment_id": updated.environment_id,
                "operator_abort_state": abort_state,
            },
        )
        return updated

    def ack_bridge_session_work(
        self,
        session_mount_id: str,
        *,
        lease_token: str,
        work_id: str,
        bridge_session_id: str | None = None,
        ttl_seconds: int | None = None,
        handle: object | None = None,
        workspace_trusted: bool | None = None,
        elevated_auth_state: str | None = None,
    ) -> SessionMount:
        now = _utc_now()
        return self._update_bridge_session_work(
            session_mount_id,
            lease_token=lease_token,
            ttl_seconds=ttl_seconds,
            handle=handle,
            bridge_updates={
                "bridge_work_id": str(work_id).strip(),
                "bridge_work_status": "acknowledged",
                "bridge_session_id": (
                    str(bridge_session_id).strip()
                    if isinstance(bridge_session_id, str) and bridge_session_id.strip()
                    else None
                ),
                "bridge_acknowledged_at": now.isoformat(),
                "workspace_trusted": workspace_trusted,
                "elevated_auth_state": (
                    str(elevated_auth_state).strip()
                    if isinstance(elevated_auth_state, str) and elevated_auth_state.strip()
                    else None
                ),
            },
            event_action="bridge-work-acknowledged",
        )

    def heartbeat_bridge_session_work(
        self,
        session_mount_id: str,
        *,
        lease_token: str,
        work_id: str,
        ttl_seconds: int | None = None,
        handle: object | None = None,
    ) -> SessionMount:
        now = _utc_now()
        return self._update_bridge_session_work(
            session_mount_id,
            lease_token=lease_token,
            ttl_seconds=ttl_seconds,
            handle=handle,
            bridge_updates={
                "bridge_work_id": str(work_id).strip(),
                "bridge_work_status": "running",
                "bridge_heartbeat_at": now.isoformat(),
            },
            event_action="bridge-work-heartbeat",
        )

    def reconnect_bridge_session_work(
        self,
        session_mount_id: str,
        *,
        lease_token: str,
        work_id: str,
        ttl_seconds: int | None = None,
        handle: object | None = None,
    ) -> SessionMount:
        now = _utc_now()
        return self._update_bridge_session_work(
            session_mount_id,
            lease_token=lease_token,
            ttl_seconds=ttl_seconds,
            handle=handle,
            bridge_updates={
                "bridge_work_id": str(work_id).strip(),
                "bridge_work_status": "reconnecting",
                "bridge_reconnected_at": now.isoformat(),
                "bridge_heartbeat_at": now.isoformat(),
            },
            event_action="bridge-work-reconnecting",
        )

    def stop_bridge_session_work(
        self,
        session_mount_id: str,
        *,
        work_id: str,
        force: bool = False,
        lease_token: str | None = None,
        reason: str | None = None,
    ) -> SessionMount:
        session_repository = self._service._session_repository
        if session_repository is None:
            raise RuntimeError("Session repository is not available")
        now = _utc_now()
        session = session_repository.get_session(session_mount_id)
        if session is None:
            raise KeyError(f"Session '{session_mount_id}' not found")
        if (
            lease_token is not None
            and session.lease_token
            and session.lease_token != lease_token
        ):
            raise ValueError(f"Lease token mismatch for session '{session_mount_id}'")
        metadata = {
            **dict(session.metadata),
            "bridge_work_id": str(work_id).strip(),
            "bridge_work_status": "stopped",
            "bridge_stopped_at": now.isoformat(),
            "bridge_stop_mode": "force" if force else "graceful",
        }
        if reason:
            metadata["bridge_stop_reason"] = reason
        updated = session.model_copy(
            update={
                "last_active_at": now,
                "metadata": metadata,
            },
        )
        session_repository.upsert_session(updated)
        self._publish_runtime_event(
            topic="session",
            action="bridge-work-stopped",
            payload={
                "session_mount_id": updated.id,
                "environment_id": updated.environment_id,
                "bridge_work_id": updated.metadata.get("bridge_work_id"),
                "bridge_work_status": updated.metadata.get("bridge_work_status"),
                "force": force,
                "reason": reason,
            },
        )
        return updated

    def archive_bridge_session(
        self,
        session_mount_id: str,
        *,
        lease_token: str | None = None,
        reason: str | None = None,
    ) -> SessionMount | None:
        session_repository = self._service._session_repository
        if session_repository is None:
            return None
        now = _utc_now()
        released = self.release_session_lease(
            session_mount_id,
            lease_token=lease_token,
            reason=reason or "bridge session archived",
            release_status="released",
            validate_token=lease_token is not None,
        )
        current = released or session_repository.get_session(session_mount_id)
        if current is None:
            return None
        metadata = {
            **dict(current.metadata),
            "bridge_work_status": "archived",
            "bridge_archived_at": now.isoformat(),
        }
        if reason:
            metadata["bridge_archive_reason"] = reason
        updated = current.model_copy(
            update={
                "status": "archived",
                "last_active_at": now,
                "metadata": metadata,
            },
        )
        session_repository.upsert_session(updated)
        self._publish_runtime_event(
            topic="session",
            action="bridge-session-archived",
            payload={
                "session_mount_id": updated.id,
                "environment_id": updated.environment_id,
                "bridge_work_status": "archived",
                "reason": reason,
            },
        )
        return updated

    def deregister_bridge_environment(
        self,
        environment_id: str,
        *,
        reason: str | None = None,
    ):
        session_repository = self._service._session_repository
        mount = self._service._registry.get(environment_id)
        if mount is None:
            return None
        now = _utc_now()
        if session_repository is not None:
            sessions = session_repository.list_sessions(environment_id=environment_id, limit=None)
            for session in sessions:
                released = self.release_session_lease(
                    session.id,
                    lease_token=session.lease_token,
                    reason=reason or "bridge environment deregistered",
                    release_status="released",
                    validate_token=False,
                )
                current = released or session_repository.get_session(session.id)
                if current is None:
                    continue
                metadata = {
                    **dict(current.metadata),
                    "bridge_work_status": "deregistered",
                    "bridge_deregistered_at": now.isoformat(),
                }
                if reason:
                    metadata["bridge_deregister_reason"] = reason
                session_repository.upsert_session(
                    current.model_copy(
                        update={
                            "status": "deregistered",
                            "last_active_at": now,
                            "metadata": metadata,
                        },
                    ),
                )
        self._service._registry.detach_live_handle(environment_id)
        updated_mount = mount.model_copy(
            update={
                "status": "deregistered",
                "last_active_at": now,
                "metadata": {
                    **dict(mount.metadata),
                    "bridge_environment_status": "deregistered",
                    "bridge_deregistered_at": now.isoformat(),
                    **(
                        {"bridge_deregister_reason": reason}
                        if isinstance(reason, str) and reason.strip()
                        else {}
                    ),
                },
                "lease_status": "released",
                "lease_owner": None,
                "lease_token": None,
                "lease_expires_at": now,
                "live_handle_ref": None,
            },
        )
        self._service._registry.upsert(updated_mount)
        self._publish_runtime_event(
            topic="session",
            action="bridge-environment-deregistered",
            payload={
                "environment_id": environment_id,
                "reason": reason,
            },
        )
        return updated_mount

    def acquire_resource_slot_lease(
        self,
        *,
        scope_type: str,
        scope_value: str,
        owner: str,
        ttl_seconds: int | None = None,
        handle: object | None = None,
        metadata: dict[str, object] | None = None,
    ) -> SessionMount:
        normalized_scope_type = str(scope_type or "").strip()
        normalized_scope_value = str(scope_value or "").strip()
        if not normalized_scope_type or not normalized_scope_value:
            raise ValueError("scope_type and scope_value are required")
        channel = f"resource-slot:{normalized_scope_type}"
        return self._acquire_leased_session(
            channel=channel,
            session_id=normalized_scope_value,
            user_id=None,
            owner=owner,
            ttl_seconds=ttl_seconds,
            handle=handle,
            metadata={
                "scope_type": normalized_scope_type,
                "scope_value": normalized_scope_value,
                "environment_ref": (
                    f"resource-slot:{normalized_scope_type}:{normalized_scope_value}"
                ),
                **(metadata or {}),
            },
            ref=f"resource-slot:{normalized_scope_type}:{normalized_scope_value}",
            conflict_label=(
                f"Resource slot '{normalized_scope_type}:{normalized_scope_value}'"
            ),
            event_topic="resource-slot",
            event_payload={
                "scope_type": normalized_scope_type,
                "scope_value": normalized_scope_value,
            },
        )

    def acquire_shared_writer_lease(
        self,
        *,
        writer_lock_scope: str,
        owner: str,
        ttl_seconds: int | None = None,
        handle: object | None = None,
        metadata: dict[str, object] | None = None,
    ) -> SessionMount:
        normalized_scope = str(writer_lock_scope or "").strip()
        if not normalized_scope:
            raise ValueError("writer_lock_scope is required")
        metadata_mapping = _mapping(metadata)
        merged_metadata = {
            "access_mode": "writer",
            "lease_class": "exclusive-writer",
            "writer_lock_scope": normalized_scope,
            "environment_ref": (
                metadata_mapping.get("environment_ref")
                or f"resource-slot:shared-writer:{normalized_scope}"
            ),
            **metadata_mapping,
        }
        return self.acquire_resource_slot_lease(
            scope_type="shared-writer",
            scope_value=normalized_scope,
            owner=owner,
            ttl_seconds=ttl_seconds,
            handle=handle,
            metadata=merged_metadata,
        )

    def heartbeat_resource_slot_lease(
        self,
        lease_id: str,
        *,
        lease_token: str,
        ttl_seconds: int | None = None,
        handle: object | None = None,
        metadata: dict[str, object] | None = None,
    ) -> SessionMount:
        return self.heartbeat_session_lease(
            lease_id,
            lease_token=lease_token,
            ttl_seconds=ttl_seconds,
            handle=handle,
            metadata=metadata,
        )

    def heartbeat_shared_writer_lease(
        self,
        lease_id: str,
        *,
        lease_token: str,
        ttl_seconds: int | None = None,
        handle: object | None = None,
        metadata: dict[str, object] | None = None,
    ) -> SessionMount:
        return self.heartbeat_resource_slot_lease(
            lease_id,
            lease_token=lease_token,
            ttl_seconds=ttl_seconds,
            handle=handle,
            metadata={
                "access_mode": "writer",
                "lease_class": "exclusive-writer",
                **_mapping(metadata),
            },
        )

    def release_resource_slot_lease(
        self,
        *,
        lease_id: str,
        lease_token: str | None = None,
        reason: str | None = None,
        release_status: str = "released",
        validate_token: bool = True,
    ) -> SessionMount | None:
        return self.release_session_lease(
            lease_id,
            lease_token=lease_token,
            reason=reason,
            release_status=release_status,
            validate_token=validate_token,
        )

    def release_shared_writer_lease(
        self,
        *,
        lease_id: str,
        lease_token: str | None = None,
        reason: str | None = None,
        release_status: str = "released",
        validate_token: bool = True,
    ) -> SessionMount | None:
        return self.release_resource_slot_lease(
            lease_id=lease_id,
            lease_token=lease_token,
            reason=reason,
            release_status=release_status,
            validate_token=validate_token,
        )

    def list_resource_slot_leases(
        self,
        *,
        scope_type: str | None = None,
        limit: int | None = None,
    ) -> list[SessionMount]:
        session_repository = self._service._session_repository
        if session_repository is None:
            return []
        if scope_type is not None:
            return session_repository.list_sessions(
                channel=f"resource-slot:{scope_type}",
                limit=limit,
            )
        sessions = session_repository.list_sessions(limit=None)
        resource_sessions = [
            session
            for session in sessions
            if str(session.channel or "").startswith("resource-slot:")
        ]
        if isinstance(limit, int) and limit >= 0:
            return resource_sessions[:limit]
        return resource_sessions

    def get_resource_slot_lease(
        self,
        *,
        scope_type: str,
        scope_value: str,
    ) -> SessionMount | None:
        session_repository = self._service._session_repository
        if session_repository is None:
            return None
        return session_repository.get_session(
            _session_mount_id(
                channel=f"resource-slot:{scope_type}",
                session_id=scope_value,
            ),
        )

    def list_shared_writer_leases(
        self,
        *,
        limit: int | None = None,
    ) -> list[SessionMount]:
        return self.list_resource_slot_leases(scope_type="shared-writer", limit=limit)

    def get_shared_writer_lease(
        self,
        *,
        writer_lock_scope: str,
    ) -> SessionMount | None:
        normalized_scope = str(writer_lock_scope or "").strip()
        if not normalized_scope:
            return None
        return self.get_resource_slot_lease(
            scope_type="shared-writer",
            scope_value=normalized_scope,
        )

    def reap_expired_leases(
        self,
        *,
        now: datetime | None = None,
    ) -> int:
        session_repository = self._service._session_repository
        if session_repository is None:
            return 0
        current = now or _utc_now()
        sessions = session_repository.list_sessions(limit=None)
        expired = [
            session
            for session in sessions
            if session.lease_status == "leased"
            and _lease_expired(session.lease_expires_at, now=current)
        ]
        for session in expired:
            self.release_session_lease(
                session.id,
                lease_token=session.lease_token,
                reason="lease expired",
                release_status="expired",
                validate_token=False,
            )
        return len(expired)

    def recover_orphaned_leases(
        self,
        *,
        now: datetime | None = None,
        allow_cross_process_recovery: bool = False,
    ) -> int:
        """Release leased sessions whose live handles were lost after recovery/restart."""
        session_repository = self._service._session_repository
        if session_repository is None:
            return 0
        current = now or _utc_now()
        sessions = session_repository.list_sessions(limit=None)
        orphaned = [
            session
            for session in sessions
            if session.lease_status == "leased"
            and self.session_should_be_recovered_locally(
                session,
                allow_cross_process_recovery=allow_cross_process_recovery,
            )
            and (
                not session.live_handle_ref
                or not self._service._registry.has_live_handle(
                    session.environment_id,
                    lease_token=session.lease_token,
                )
            )
        ]
        recovered = 0
        for session in orphaned:
            restored = self._try_restore_session_live_handle(session, now=current)
            if restored is not None:
                recovered += 1
                continue
            self.release_session_lease(
                session.id,
                lease_token=session.lease_token,
                reason="live handle unavailable during runtime recovery",
                release_status="expired",
                validate_token=False,
            )
            recovered += 1
        return recovered

    def _update_bridge_session_work(
        self,
        session_mount_id: str,
        *,
        lease_token: str,
        bridge_updates: dict[str, object],
        ttl_seconds: int | None,
        handle: object | None,
        event_action: str,
    ) -> SessionMount:
        session_repository = self._service._session_repository
        if session_repository is None:
            raise RuntimeError("Session repository is not available")
        session = session_repository.get_session(session_mount_id)
        if session is None:
            raise KeyError(f"Session '{session_mount_id}' not found")
        metadata_patch = {
            key: value
            for key, value in bridge_updates.items()
            if value is not None
        }
        updated = self.heartbeat_session_lease(
            session_mount_id,
            lease_token=lease_token,
            ttl_seconds=ttl_seconds,
            handle=handle,
            metadata=metadata_patch,
        )
        self._publish_runtime_event(
            topic="session",
            action=event_action,
            payload={
                "session_mount_id": updated.id,
                "environment_id": updated.environment_id,
                "bridge_work_id": updated.metadata.get("bridge_work_id"),
                "bridge_work_status": updated.metadata.get("bridge_work_status"),
            },
        )
        return updated

    def _update_shared_session_environment_metadata(
        self,
        session_mount_id: str,
        *,
        metadata_patch: dict[str, object],
    ) -> SessionMount:
        session_repository = self._service._session_repository
        if session_repository is None:
            raise RuntimeError("Session repository is not available")
        session = session_repository.get_session(session_mount_id)
        if session is None:
            raise KeyError(f"Session '{session_mount_id}' not found")
        mount = self._service._registry.get(session.environment_id)
        if mount is None:
            raise KeyError(f"Environment '{session.environment_id}' not found")
        now = _utc_now()
        updated_session = session.model_copy(
            update={
                "last_active_at": now,
                "metadata": {
                    **dict(session.metadata),
                    **metadata_patch,
                },
            },
        )
        updated_mount = mount.model_copy(
            update={
                "last_active_at": now,
                "metadata": {
                    **dict(mount.metadata),
                    **metadata_patch,
                },
            },
        )
        session_repository.upsert_session(updated_session)
        self._service._registry.upsert(updated_mount)
        return updated_session

    def acquire_actor_lease(
        self,
        *,
        agent_id: str,
        owner: str,
        ttl_seconds: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AgentLeaseRecord:
        actor_repository = self._service._agent_lease_repository
        if actor_repository is None:
            raise RuntimeError("Actor lease repository is not available")
        now = _utc_now()
        expires_at = now + timedelta(
            seconds=ttl_seconds or self._service._lease_ttl_seconds,
        )
        lease_id = f"actor:{agent_id}"
        existing = actor_repository.get_lease(lease_id)
        if (
            existing is not None
            and existing.lease_status == "leased"
            and not _lease_expired(existing.expires_at, now=now)
            and existing.owner
            and existing.owner != owner
        ):
            raise RuntimeError(
                f"Actor '{agent_id}' is already leased by '{existing.owner}'",
            )
        payload = {
            "agent_id": agent_id,
            "lease_kind": "actor-runtime",
            "resource_ref": f"actor:{agent_id}",
            "lease_status": "leased",
            "lease_token": existing.lease_token if existing is not None else uuid4().hex,
            "owner": owner,
            "acquired_at": existing.acquired_at if existing is not None else now,
            "expires_at": expires_at,
            "heartbeat_at": now,
            "released_at": None,
            "metadata": {
                **(existing.metadata if existing is not None else {}),
                **(metadata or {}),
            },
            "updated_at": now,
        }
        lease = (
            existing.model_copy(update=payload)
            if existing is not None
            else AgentLeaseRecord(id=lease_id, **payload)
        )
        return actor_repository.upsert_lease(lease)

    def heartbeat_actor_lease(
        self,
        lease_id: str,
        *,
        lease_token: str | None,
        ttl_seconds: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AgentLeaseRecord:
        actor_repository = self._service._agent_lease_repository
        if actor_repository is None:
            raise RuntimeError("Actor lease repository is not available")
        existing = actor_repository.get_lease(lease_id)
        if existing is None:
            raise KeyError(f"Actor lease '{lease_id}' not found")
        if existing.lease_token and lease_token and existing.lease_token != lease_token:
            raise ValueError(f"Lease token mismatch for actor lease '{lease_id}'")
        now = _utc_now()
        updated = existing.model_copy(
            update={
                "lease_status": "leased",
                "expires_at": now
                + timedelta(seconds=ttl_seconds or self._service._lease_ttl_seconds),
                "heartbeat_at": now,
                "metadata": {**existing.metadata, **(metadata or {})},
                "updated_at": now,
            },
        )
        return actor_repository.upsert_lease(updated)

    def release_actor_lease(
        self,
        lease_id: str,
        *,
        lease_token: str | None = None,
        reason: str | None = None,
    ) -> AgentLeaseRecord | None:
        actor_repository = self._service._agent_lease_repository
        if actor_repository is None:
            return None
        existing = actor_repository.get_lease(lease_id)
        if existing is None:
            return None
        if existing.lease_token and lease_token and existing.lease_token != lease_token:
            raise ValueError(f"Lease token mismatch for actor lease '{lease_id}'")
        now = _utc_now()
        metadata = dict(existing.metadata)
        if reason:
            metadata["release_reason"] = reason
        updated = existing.model_copy(
            update={
                "lease_status": "released",
                "released_at": now,
                "heartbeat_at": now,
                "expires_at": now,
                "metadata": metadata,
                "updated_at": now,
            },
        )
        return actor_repository.upsert_lease(updated)

    def reap_expired_actor_leases(
        self,
        *,
        now: datetime | None = None,
    ) -> int:
        actor_repository = self._service._agent_lease_repository
        if actor_repository is None:
            return 0
        current = now or _utc_now()
        leases = actor_repository.list_leases(limit=None)
        expired = [
            lease
            for lease in leases
            if lease.lease_status == "leased"
            and _lease_expired(lease.expires_at, now=current)
        ]
        for lease in expired:
            metadata = dict(lease.metadata)
            metadata["release_reason"] = "actor lease expired"
            actor_repository.upsert_lease(
                lease.model_copy(
                    update={
                        "lease_status": "expired",
                        "released_at": current,
                        "heartbeat_at": current,
                        "expires_at": current,
                        "metadata": metadata,
                        "updated_at": current,
                    },
                ),
            )
        return len(expired)

    def recover_orphaned_actor_leases(
        self,
        *,
        now: datetime | None = None,
    ) -> int:
        actor_repository = self._service._agent_lease_repository
        if actor_repository is None:
            return 0
        current = now or _utc_now()
        leases = actor_repository.list_leases(limit=None)
        orphaned = [
            lease
            for lease in leases
            if lease.lease_status == "leased"
            and not _lease_expired(lease.expires_at, now=current)
        ]
        for lease in orphaned:
            metadata = dict(lease.metadata)
            metadata["release_reason"] = "actor lease orphaned during runtime recovery"
            actor_repository.upsert_lease(
                lease.model_copy(
                    update={
                        "lease_status": "expired",
                        "released_at": current,
                        "heartbeat_at": current,
                        "expires_at": current,
                        "metadata": metadata,
                        "updated_at": current,
                    },
                ),
            )
        return len(orphaned)

    def session_should_be_recovered_locally(
        self,
        session: SessionMount,
        *,
        allow_cross_process_recovery: bool = False,
    ) -> bool:
        locality = self.session_recovery_locality(session)
        if locality["same_process"]:
            return True
        if locality["same_host"] and allow_cross_process_recovery:
            return True
        if not locality["host_known"] and allow_cross_process_recovery:
            return True
        return False

    def session_recovery_locality(self, session: SessionMount) -> dict[str, object]:
        lease_runtime = self.lease_runtime_mapping(session.metadata)
        lease_host_id = str(
            lease_runtime.get("host_id")
            or session.metadata.get("lease_host_id")
            or "",
        ).strip() or None
        lease_process_id = self.normalize_process_id(
            lease_runtime.get("process_id") or session.metadata.get("lease_process_id"),
        )
        current_host_id = self._service._registry.host_id
        current_process_id = self.normalize_process_id(
            self._service._registry.process_id,
        )
        same_host = bool(lease_host_id) and lease_host_id == current_host_id
        same_process = (
            same_host
            and lease_process_id is not None
            and lease_process_id == current_process_id
        )
        return {
            "lease_host_id": lease_host_id,
            "lease_process_id": lease_process_id,
            "current_host_id": current_host_id,
            "current_process_id": current_process_id,
            "host_known": lease_host_id is not None,
            "process_known": lease_process_id is not None,
            "same_host": same_host,
            "same_process": same_process,
        }

    def lease_runtime_mapping(self, metadata: dict[str, object]) -> dict[str, object]:
        lease_runtime = metadata.get("lease_runtime")
        return dict(lease_runtime) if isinstance(lease_runtime, dict) else {}

    def lease_runtime_descriptor(self, metadata: dict[str, object]) -> dict[str, object]:
        lease_runtime = self.lease_runtime_mapping(metadata)
        descriptor = lease_runtime.get("descriptor")
        return dict(descriptor) if isinstance(descriptor, dict) else {}

    def build_live_handle_descriptor(
        self,
        *,
        channel: str,
        session_id: str,
        user_id: str | None,
        owner: str | None,
        handle: object | None,
        metadata: dict[str, object],
    ) -> dict[str, object]:
        descriptor = {
            "kind": "session",
            "channel": channel,
            "session_id": session_id,
            "user_id": user_id,
            "owner": owner,
        }
        if isinstance(handle, dict):
            for key in ("browser", "page_id", "workspace", "cwd", "task_id"):
                value = handle.get(key)
                if value is not None:
                    descriptor[key] = value
        for key in (
            "chat_id",
            "kernel_task_id",
            "work_context_id",
            "workspace_id",
            "workspace_scope",
            "attach_transport_ref",
            "provider_session_ref",
            "browser_companion_transport_ref",
        ):
            value = metadata.get(key)
            if value is not None:
                descriptor[key] = value
        return descriptor

    def build_lease_runtime_metadata(
        self,
        *,
        owner: str | None,
        status: str,
        descriptor: dict[str, object],
        token: str | None,
        seen_at: datetime,
        expires_at: datetime | None,
    ) -> dict[str, object]:
        return {
            "host_id": self._service._registry.host_id,
            "process_id": self._service._registry.process_id,
            "owner": owner,
            "status": status,
            "token": token,
            "descriptor": dict(descriptor),
            "seen_at": seen_at.isoformat(),
            "expires_at": (
                expires_at.isoformat() if expires_at is not None else None
            ),
        }

    def normalize_process_id(self, value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                return int(raw)
            except ValueError:
                return None
        return None

    def _acquire_leased_session(
        self,
        *,
        channel: str,
        session_id: str,
        user_id: str | None,
        owner: str,
        ttl_seconds: int | None,
        handle: object | None,
        metadata: dict[str, object] | None,
        ref: str,
        conflict_label: str,
        event_topic: str,
        event_payload: dict[str, object],
    ) -> SessionMount:
        session_repository = self._service._session_repository
        if session_repository is None:
            raise RuntimeError("Session repository is not available")

        normalized_channel = str(channel or "").strip()
        normalized_session_id = str(session_id or "").strip()
        normalized_owner = str(owner or "").strip()
        if not normalized_channel or not normalized_session_id or not normalized_owner:
            raise ValueError("channel, session_id, and owner are required")

        now = _utc_now()
        expires_at = now + timedelta(
            seconds=ttl_seconds or self._service._lease_ttl_seconds,
        )
        lease_token = uuid4().hex
        session_mount_id = _session_mount_id(
            channel=normalized_channel,
            session_id=normalized_session_id,
        )
        session_metadata = {
            "channel": normalized_channel,
            "session_id": normalized_session_id,
            **(metadata or {}),
        }
        if user_id is not None:
            session_metadata.setdefault("user_id", user_id)

        existing = session_repository.get_session(session_mount_id)
        if (
            existing is not None
            and existing.lease_status == "leased"
            and not _lease_expired(existing.lease_expires_at, now=now)
            and existing.lease_owner
            and existing.lease_owner != normalized_owner
        ):
            raise RuntimeError(
                f"{conflict_label} is already leased by '{existing.lease_owner}'",
            )

        mount = self._service._registry.register(
            ref=ref,
            kind="session",
            status="active",
            metadata=session_metadata,
        )
        if mount is None:
            raise RuntimeError(f"Environment '{ref}' could not be registered")

        descriptor = self.build_live_handle_descriptor(
            channel=normalized_channel,
            session_id=normalized_session_id,
            user_id=user_id,
            owner=normalized_owner,
            handle=handle,
            metadata=session_metadata,
        )
        live_handle_ref = self._service._registry.attach_live_handle(
            mount.id,
            handle=handle
            or {
                "session_mount_id": session_mount_id,
                "owner": normalized_owner,
            },
            owner=normalized_owner,
            lease_token=lease_token,
            handle_ref=existing.live_handle_ref if existing is not None else None,
            descriptor=descriptor,
            seen_at=now,
        )

        lease_runtime = self.build_lease_runtime_metadata(
            owner=normalized_owner,
            status="leased",
            descriptor=descriptor,
            token=lease_token,
            seen_at=now,
            expires_at=expires_at,
        )
        persisted_metadata = {
            **(existing.metadata if existing is not None else {}),
            **session_metadata,
            "lease_runtime": lease_runtime,
        }
        session = SessionMount(
            id=session_mount_id,
            environment_id=mount.id,
            channel=normalized_channel,
            session_id=normalized_session_id,
            user_id=user_id,
            status=existing.status if existing is not None else "active",
            created_at=existing.created_at if existing is not None else now,
            last_active_at=now,
            metadata=persisted_metadata,
            lease_status="leased",
            lease_owner=normalized_owner,
            lease_token=lease_token,
            lease_acquired_at=now,
            lease_expires_at=expires_at,
            live_handle_ref=live_handle_ref,
        )
        session_repository.upsert_session(session)
        self._sync_environment_lease(
            mount.id,
            owner=normalized_owner,
            lease_token=lease_token,
            lease_status="leased",
            live_handle_ref=live_handle_ref,
            last_active_at=now,
            expires_at=expires_at,
        )
        self._publish_runtime_event(
            topic=event_topic,
            action="leased",
            payload={
                "session_mount_id": session.id,
                "environment_id": session.environment_id,
                "lease_status": session.lease_status,
                "live_handle_ref": session.live_handle_ref,
                **event_payload,
            },
        )
        return session

    def _try_restore_session_live_handle(
        self,
        session: SessionMount,
        *,
        now: datetime,
    ) -> SessionMount | None:
        session_repository = self._service._session_repository
        if session_repository is None:
            return None
        restorer = self._session_handle_restorers.get(session.channel)
        if not callable(restorer):
            return None
        descriptor = self.lease_runtime_descriptor(session.metadata)
        context = {
            "channel": session.channel,
            "session_id": session.session_id,
            "user_id": session.user_id,
            "owner": session.lease_owner,
            "environment_id": session.environment_id,
            "session_mount_id": session.id,
            "lease_token": session.lease_token,
            "descriptor": descriptor,
            "metadata": dict(session.metadata),
        }
        try:
            restored = restorer(context)
        except Exception:
            return None
        if inspect.isawaitable(restored):
            return None
        handle, descriptor_update, metadata_update = self._normalize_restored_handle(
            restored,
        )
        if handle is None:
            return None
        merged_descriptor = {**descriptor, **descriptor_update}
        live_handle_ref = self._service._registry.attach_live_handle(
            session.environment_id,
            handle=handle,
            owner=session.lease_owner,
            lease_token=session.lease_token,
            handle_ref=session.live_handle_ref,
            descriptor=merged_descriptor,
            seen_at=now,
        )
        metadata = {**session.metadata, **metadata_update}
        metadata["lease_runtime"] = self.build_lease_runtime_metadata(
            owner=session.lease_owner,
            status="restored",
            descriptor=merged_descriptor,
            token=session.lease_token,
            seen_at=now,
            expires_at=session.lease_expires_at,
        )
        metadata["lease_restored_at"] = now.isoformat()
        metadata["lease_restore_status"] = "restored"
        updated = session.model_copy(
            update={
                "last_active_at": now,
                "metadata": metadata,
                "lease_status": "leased",
                "live_handle_ref": live_handle_ref,
            },
        )
        session_repository.upsert_session(updated)
        self._sync_environment_lease(
            updated.environment_id,
            owner=updated.lease_owner,
            lease_token=updated.lease_token,
            lease_status="leased",
            live_handle_ref=live_handle_ref,
            last_active_at=now,
            expires_at=updated.lease_expires_at,
        )
        self._publish_runtime_event(
            topic="session",
            action="restored",
            payload={
                "session_mount_id": updated.id,
                "environment_id": updated.environment_id,
                "lease_status": updated.lease_status,
                "live_handle_ref": updated.live_handle_ref,
            },
        )
        return updated

    def _normalize_restored_handle(
        self,
        restored: object,
    ) -> tuple[object | None, dict[str, object], dict[str, object]]:
        if restored is None:
            return None, {}, {}
        if isinstance(restored, dict) and any(
            key in restored for key in ("handle", "descriptor", "metadata")
        ):
            handle = restored.get("handle")
            descriptor = (
                dict(restored.get("descriptor"))
                if isinstance(restored.get("descriptor"), dict)
                else {}
            )
            metadata = (
                dict(restored.get("metadata"))
                if isinstance(restored.get("metadata"), dict)
                else {}
            )
            return handle, descriptor, metadata
        return restored, {}, {}

    def _publish_runtime_event(
        self,
        *,
        topic: str,
        action: str,
        payload: dict[str, object],
    ) -> None:
        if self._service._runtime_event_bus is None:
            return
        self._service._runtime_event_bus.publish(
            topic=topic,
            action=action,
            payload=payload,
        )

    def _sync_environment_lease(
        self,
        env_id: str,
        *,
        owner: str | None,
        lease_token: str | None,
        lease_status: str,
        live_handle_ref: str | None,
        last_active_at: datetime,
        expires_at: datetime | None,
    ) -> None:
        mount = self._service._registry.get(env_id)
        if mount is None:
            return
        live_handle = self._service._registry.get_live_handle_info(env_id) or {}
        existing_lease_runtime = self.lease_runtime_mapping(mount.metadata)
        lease_runtime = {
            "host_id": live_handle.get("host_id")
            or existing_lease_runtime.get("host_id"),
            "process_id": live_handle.get("process_id")
            or existing_lease_runtime.get("process_id"),
            "owner": owner,
            "status": lease_status,
            "token": lease_token,
            "descriptor": live_handle.get("descriptor")
            or self.lease_runtime_descriptor(mount.metadata),
            "seen_at": last_active_at.isoformat(),
            "expires_at": (
                expires_at.isoformat() if expires_at is not None else None
            ),
        }
        updated = mount.model_copy(
            update={
                "last_active_at": last_active_at,
                "metadata": {
                    **mount.metadata,
                    "lease_runtime": lease_runtime,
                },
                "lease_status": lease_status,
                "lease_owner": owner,
                "lease_token": lease_token,
                "lease_acquired_at": (
                    mount.lease_acquired_at
                    if lease_status == "leased" and mount.lease_acquired_at is not None
                    else (last_active_at if lease_status == "leased" else None)
                ),
                "lease_expires_at": expires_at,
                "live_handle_ref": live_handle_ref,
            },
        )
        self._service._registry.upsert(updated)


def _session_mount_id(*, channel: str, session_id: str) -> str:
    return f"session:{channel}:{session_id}"


def resolve_operator_abort_binding_for_runtime_session(
    runtime_session_ref: str,
) -> dict[str, object]:
    resolved = _resolve_operator_abort_binding_record(runtime_session_ref)
    if resolved is None:
        return {}
    _, binding = resolved
    return dict(binding)


def publish_browser_operator_abort_guardrail_block(
    runtime_session_ref: str,
    *,
    action: str,
    reason: str | None = None,
) -> None:
    resolved = _resolve_operator_abort_binding_record(runtime_session_ref)
    if resolved is None:
        return
    service, binding = resolved
    if not binding.get("requested"):
        return
    resolved_reason = _normalize_string(reason, binding.get("reason"), binding.get("channel"))
    service._publish_runtime_event(
        topic="browser",
        action="guardrail-blocked",
        payload={
            "session_mount_id": binding.get("session_mount_id"),
            "environment_id": binding.get("environment_id"),
            "runtime_session_ref": _normalize_string(runtime_session_ref),
            "action": _normalize_string(action),
            "guardrail_kind": "operator-abort",
            "reason": resolved_reason,
        },
    )


def _resolve_operator_abort_binding_record(
    runtime_session_ref: str,
):
    normalized_ref = _normalize_string(runtime_session_ref)
    if normalized_ref is None:
        return None
    best_requested = None
    best_fallback = None
    for service in list(_ACTIVE_LEASE_SERVICES):
        binding = _resolve_operator_abort_binding_for_service(
            service,
            runtime_session_ref=normalized_ref,
        )
        if not binding:
            continue
        match_rank = int(binding.get("_match_rank") or 0)
        if binding.get("requested"):
            if (
                best_requested is None
                or match_rank > int(best_requested[1].get("_match_rank") or 0)
            ):
                best_requested = (service, binding)
            continue
        if (
            best_fallback is None
            or match_rank > int(best_fallback[1].get("_match_rank") or 0)
        ):
            best_fallback = (service, binding)
    resolved = best_requested or best_fallback
    if resolved is None:
        return None
    service, binding = resolved
    return service, {
        key: value
        for key, value in binding.items()
        if key != "_match_rank"
    }


def _resolve_operator_abort_binding_for_service(
    service: EnvironmentLeaseService,
    *,
    runtime_session_ref: str,
) -> dict[str, object]:
    session_repository = service._service._session_repository
    if session_repository is None:
        return {}
    best_requested: dict[str, object] | None = None
    best_requested_rank = 0
    best_fallback: dict[str, object] | None = None
    best_fallback_rank = 0
    for session in session_repository.list_sessions(limit=None):
        match_rank = _session_runtime_ref_match_rank(
            session,
            runtime_session_ref=runtime_session_ref,
        )
        if match_rank is None:
            continue
        environment = service._service._registry.get(session.environment_id)
        state = _shared_operator_abort_state(
            session_metadata=_mapping(session.metadata),
            environment_metadata=_mapping(
                environment.metadata if environment is not None else None,
            ),
        )
        binding: dict[str, object] = {
            "session_mount_id": session.id,
            "environment_id": session.environment_id,
            "runtime_session_ref": runtime_session_ref,
            "_match_rank": match_rank,
            **state,
        }
        if binding.get("requested"):
            if match_rank > best_requested_rank:
                best_requested = binding
                best_requested_rank = match_rank
            continue
        if match_rank > best_fallback_rank:
            best_fallback = binding
            best_fallback_rank = match_rank
    return best_requested or best_fallback or {}


def _session_runtime_ref_match_rank(
    session: SessionMount,
    *,
    runtime_session_ref: str,
) -> int | None:
    ranked_aliases = (
        (_normalize_string(session.metadata.get("provider_session_ref")), 4),
        (_normalize_string(session.metadata.get("browser_attach_session_ref")), 4),
        (_normalize_string(session.metadata.get("browser_session_ref")), 4),
        (_normalize_string(session.metadata.get("session_ref")), 4),
        (_normalize_string(session.id), 3),
        (_normalize_string(session.live_handle_ref), 2),
        (_normalize_string(session.session_id), 1),
    )
    best_rank: int | None = None
    for alias, rank in ranked_aliases:
        if alias != runtime_session_ref:
            continue
        if best_rank is None or rank > best_rank:
            best_rank = rank
    return best_rank


def _shared_operator_abort_state(
    *,
    session_metadata: dict[str, object],
    environment_metadata: dict[str, object],
) -> dict[str, object]:
    raw = session_metadata.get("operator_abort_state")
    if not isinstance(raw, dict):
        raw = environment_metadata.get("operator_abort_state")
    if not isinstance(raw, dict):
        return {}
    channel = _normalize_string(raw.get("channel"), raw.get("operator_abort_channel"))
    reason = _normalize_string(raw.get("reason"), raw.get("abort_reason"), channel)
    requested_at = _normalize_string(raw.get("requested_at"))
    requested = bool(
        raw.get("requested")
        if "requested" in raw
        else raw.get("operator_abort_requested"),
    )
    state: dict[str, object] = {}
    if requested:
        state["requested"] = True
    if channel is not None:
        state["channel"] = channel
    if reason is not None:
        state["reason"] = reason
    if requested_at is not None:
        state["requested_at"] = requested_at
    return state


def _mapping(value: object | None) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _normalize_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None


def _lease_expired(expires_at: datetime | None, *, now: datetime) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
