# -*- coding: utf-8 -*-
"""Environment query facade."""
from __future__ import annotations

from typing import Any

from ..state import AgentLeaseRecord
from .artifact_service import EnvironmentArtifactService
from .cooperative import (
    BrowserCompanionRuntime,
    DocumentBridgeRuntime,
    ExecutionPathResolution,
    HostWatcherRuntime,
    WindowsAppAdapterRuntime,
    resolve_preferred_execution_path,
)
from .health_service import EnvironmentHealthService
from .host_event_recovery_service import HostEventRecoveryService
from .lease_service import EnvironmentLeaseService
from .models import EnvironmentMount, EnvironmentSummary, SessionMount
from .observations import ActionReplayStore, ArtifactStore, ObservationCache
from .registry import EnvironmentRegistry
from .replay_service import EnvironmentReplayService
from .repository import SessionMountRepository
from .session_service import EnvironmentSessionService
from .surface_control_service import SurfaceControlService


class EnvironmentService:
    """Stable outward-facing facade for the environment domain."""

    def __init__(
        self,
        *,
        registry: EnvironmentRegistry | None = None,
        lease_ttl_seconds: int = 900,
    ) -> None:
        self._registry = registry or EnvironmentRegistry()
        self._session_repository: SessionMountRepository | None = None
        self._observation_cache: ObservationCache | None = None
        self._action_replay: ActionReplayStore | None = None
        self._artifact_store: ArtifactStore | None = None
        self._lease_ttl_seconds = max(30, lease_ttl_seconds)
        self._runtime_event_bus = None
        self._agent_lease_repository = None
        self._kernel_dispatcher = None
        self._browser_companion_runtime: BrowserCompanionRuntime | None = None
        self._document_bridge_runtime: DocumentBridgeRuntime | None = None
        self._host_watcher_runtime: HostWatcherRuntime | None = None
        self._windows_app_adapter_runtime: WindowsAppAdapterRuntime | None = None

        self._session_service = EnvironmentSessionService(self)
        self._lease_service = EnvironmentLeaseService(self)
        self._replay_service = EnvironmentReplayService(self)
        self._artifact_service = EnvironmentArtifactService(self)
        self._health_service = EnvironmentHealthService(self)
        self._host_event_recovery_service = HostEventRecoveryService(
            environment_service=self,
        )
        self._surface_control_service = SurfaceControlService(self)
        self._rebind_cooperative_runtimes()

    def set_session_repository(
        self,
        session_repository: SessionMountRepository | None,
    ) -> None:
        self._session_repository = session_repository
        self._rebind_cooperative_runtimes()

    def set_observation_cache(
        self,
        observation_cache: ObservationCache | None,
    ) -> None:
        self._observation_cache = observation_cache

    def set_action_replay(
        self,
        action_replay: ActionReplayStore | None,
    ) -> None:
        self._action_replay = action_replay

    def set_artifact_store(
        self,
        artifact_store: ArtifactStore | None,
    ) -> None:
        self._artifact_store = artifact_store

    def set_runtime_event_bus(self, runtime_event_bus) -> None:
        self._runtime_event_bus = runtime_event_bus
        self._host_event_recovery_service = HostEventRecoveryService(
            environment_service=self,
            runtime_event_bus=runtime_event_bus,
        )
        self._rebind_cooperative_runtimes()

    def set_agent_lease_repository(self, agent_lease_repository) -> None:
        self._agent_lease_repository = agent_lease_repository

    def set_kernel_dispatcher(self, kernel_dispatcher) -> None:
        self._kernel_dispatcher = kernel_dispatcher

    def register_session_handle_restorer(
        self,
        channel: str,
        restorer: object | None,
    ) -> None:
        self._lease_service.register_session_handle_restorer(channel, restorer)

    def register_replay_executor(
        self,
        replay_type: str,
        executor: object | None,
    ) -> None:
        self._replay_service.register_replay_executor(replay_type, executor)

    def register_document_bridge_executor(
        self,
        bridge_ref: str,
        executor: object | None,
    ) -> None:
        self._surface_control_service.register_document_bridge_executor(
            bridge_ref,
            executor,
        )

    def register_windows_app_executor(
        self,
        app_identity: str,
        executor: object | None,
    ) -> None:
        self._surface_control_service.register_windows_app_executor(
            app_identity,
            executor,
        )

    def register_semantic_surface_executor(
        self,
        control_channel: str,
        executor: object | None,
    ) -> None:
        self._surface_control_service.register_semantic_surface_executor(
            control_channel,
            executor,
        )

    def list_environments(
        self,
        *,
        kind: str | None = None,
        limit: int | None = None,
    ) -> list[EnvironmentMount]:
        return self._session_service.list_environments(kind=kind, limit=limit)

    def get_environment(self, env_id: str) -> EnvironmentMount | None:
        return self._session_service.get_environment(env_id)

    def summarize(self) -> EnvironmentSummary:
        return self._session_service.summarize()

    def register_environment(
        self,
        *,
        ref: str | None,
        kind: str | None = None,
        status: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> EnvironmentMount | None:
        return self._session_service.register_environment(
            ref=ref,
            kind=kind,
            status=status,
            metadata=metadata,
        )

    def touch_environment(
        self,
        *,
        ref: str | None,
        kind: str | None = None,
        status: str | None = None,
        metadata: dict[str, object] | None = None,
        last_active_at=None,
        evidence_delta: int = 1,
    ) -> EnvironmentMount | None:
        return self._session_service.touch_environment(
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
        return self._session_service.close_environment(env_id, status=status)

    def list_sessions(
        self,
        *,
        environment_id: str | None = None,
        channel: str | None = None,
        user_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[SessionMount]:
        return self._session_service.list_sessions(
            environment_id=environment_id,
            channel=channel,
            user_id=user_id,
            status=status,
            limit=limit,
        )

    def get_session(self, session_mount_id: str) -> SessionMount | None:
        return self._session_service.get_session(session_mount_id)

    def close_session(
        self,
        session_mount_id: str,
        *,
        status: str = "closed",
    ) -> SessionMount | None:
        return self._session_service.close_session(session_mount_id, status=status)

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
        return self._lease_service.acquire_session_lease(
            channel=channel,
            session_id=session_id,
            user_id=user_id,
            owner=owner,
            ttl_seconds=ttl_seconds,
            handle=handle,
            metadata=metadata,
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
        return self._lease_service.heartbeat_session_lease(
            session_mount_id,
            lease_token=lease_token,
            ttl_seconds=ttl_seconds,
            handle=handle,
            metadata=metadata,
        )

    def release_session_lease(
        self,
        session_mount_id: str,
        *,
        lease_token: str | None = None,
        reason: str | None = None,
        release_status: str = "released",
        validate_token: bool = True,
    ) -> SessionMount | None:
        return self._lease_service.release_session_lease(
            session_mount_id,
            lease_token=lease_token,
            reason=reason,
            release_status=release_status,
            validate_token=validate_token,
        )

    def force_release_session_lease(
        self,
        session_mount_id: str,
        *,
        reason: str = "forced release",
    ) -> SessionMount | None:
        return self._lease_service.force_release_session_lease(
            session_mount_id,
            reason=reason,
        )

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
        return self._lease_service.acquire_resource_slot_lease(
            scope_type=scope_type,
            scope_value=scope_value,
            owner=owner,
            ttl_seconds=ttl_seconds,
            handle=handle,
            metadata=metadata,
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
        return self._lease_service.heartbeat_resource_slot_lease(
            lease_id,
            lease_token=lease_token,
            ttl_seconds=ttl_seconds,
            handle=handle,
            metadata=metadata,
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
        return self._lease_service.release_resource_slot_lease(
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
        return self._lease_service.list_resource_slot_leases(
            scope_type=scope_type,
            limit=limit,
        )

    def get_resource_slot_lease(
        self,
        *,
        scope_type: str,
        scope_value: str,
    ) -> SessionMount | None:
        return self._lease_service.get_resource_slot_lease(
            scope_type=scope_type,
            scope_value=scope_value,
        )

    def reap_expired_leases(
        self,
        *,
        now=None,
    ) -> int:
        return self._lease_service.reap_expired_leases(now=now)

    def recover_orphaned_leases(
        self,
        *,
        now=None,
        allow_cross_process_recovery: bool = False,
    ) -> int:
        return self._lease_service.recover_orphaned_leases(
            now=now,
            allow_cross_process_recovery=allow_cross_process_recovery,
        )

    def acquire_actor_lease(
        self,
        *,
        agent_id: str,
        owner: str,
        ttl_seconds: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AgentLeaseRecord:
        return self._lease_service.acquire_actor_lease(
            agent_id=agent_id,
            owner=owner,
            ttl_seconds=ttl_seconds,
            metadata=metadata,
        )

    def heartbeat_actor_lease(
        self,
        lease_id: str,
        *,
        lease_token: str | None,
        ttl_seconds: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AgentLeaseRecord:
        return self._lease_service.heartbeat_actor_lease(
            lease_id,
            lease_token=lease_token,
            ttl_seconds=ttl_seconds,
            metadata=metadata,
        )

    def release_actor_lease(
        self,
        lease_id: str,
        *,
        lease_token: str | None = None,
        reason: str | None = None,
    ) -> AgentLeaseRecord | None:
        return self._lease_service.release_actor_lease(
            lease_id,
            lease_token=lease_token,
            reason=reason,
        )

    def reap_expired_actor_leases(
        self,
        *,
        now=None,
    ) -> int:
        return self._lease_service.reap_expired_actor_leases(now=now)

    def recover_orphaned_actor_leases(
        self,
        *,
        now=None,
    ) -> int:
        return self._lease_service.recover_orphaned_actor_leases(now=now)

    def list_observations(
        self,
        *,
        environment_ref: str | None,
        limit: int = 20,
    ):
        return self._replay_service.list_observations(
            environment_ref=environment_ref,
            limit=limit,
        )

    def get_observation(self, observation_id: str):
        return self._replay_service.get_observation(observation_id)

    def list_replays(
        self,
        *,
        environment_ref: str | None,
        limit: int = 20,
    ):
        return self._replay_service.list_replays(
            environment_ref=environment_ref,
            limit=limit,
        )

    def get_replay(self, replay_id: str):
        return self._replay_service.get_replay(replay_id)

    async def execute_replay(
        self,
        replay_id: str,
        *,
        actor: str = "runtime-center",
    ) -> dict[str, object]:
        return await self._replay_service.execute_replay(replay_id, actor=actor)

    def list_artifacts(
        self,
        *,
        environment_ref: str | None,
        limit: int = 20,
    ):
        return self._artifact_service.list_artifacts(
            environment_ref=environment_ref,
            limit=limit,
        )

    def get_artifact(self, artifact_id: str):
        return self._artifact_service.get_artifact(artifact_id)

    def get_environment_detail(
        self,
        env_id: str,
        *,
        limit: int = 20,
    ) -> dict[str, object] | None:
        return self._health_service.get_environment_detail(env_id, limit=limit)

    def get_session_detail(
        self,
        session_mount_id: str,
        *,
        limit: int = 20,
    ) -> dict[str, object] | None:
        return self._health_service.get_session_detail(
            session_mount_id,
            limit=limit,
        )

    def should_run_host_recovery(
        self,
        *,
        limit: int = 20,
        allow_cross_process_recovery: bool = False,
    ) -> tuple[bool, str]:
        plan = self._host_event_recovery_service.plan_recovery(
            limit=limit,
            allow_cross_process_recovery=allow_cross_process_recovery,
        )
        planned = int(plan.get("planned") or 0)
        if planned > 0:
            return (True, "actionable-host-events")
        skipped = int(plan.get("skipped") or 0)
        if skipped > 0:
            skipped_events = plan.get("skipped_events") or []
            if any(
                isinstance(item, dict)
                and item.get("reason") == "cross-process-recovery-disabled"
                for item in skipped_events
            ):
                return (False, "cross-process-recovery-disabled")
            return (False, "host-events-already-handled")
        return (False, "no-actionable-host-events")

    def run_host_recovery_cycle(
        self,
        *,
        limit: int = 20,
        allow_cross_process_recovery: bool = False,
    ) -> dict[str, Any]:
        return self._host_event_recovery_service.run_recovery_cycle(
            limit=limit,
            allow_cross_process_recovery=allow_cross_process_recovery,
        )

    def register_browser_companion(self, **kwargs) -> dict[str, Any]:
        runtime = self._require_browser_companion_runtime()
        return runtime.register_companion(**kwargs)

    def clear_browser_companion(self, **kwargs) -> dict[str, Any]:
        runtime = self._require_browser_companion_runtime()
        return runtime.clear_companion(**kwargs)

    def browser_companion_snapshot(self, **kwargs) -> dict[str, Any]:
        runtime = self._require_browser_companion_runtime()
        return runtime.snapshot(**kwargs)

    def register_document_bridge(
        self,
        *,
        session_mount_id: str,
        bridge_ref: str,
        status: str | None = None,
        supported_families=None,
        available: bool | None = None,
    ) -> dict[str, Any]:
        runtime = self._require_document_bridge_runtime()
        runtime.register_bridge(
            session_mount_id=session_mount_id,
            bridge_ref=bridge_ref,
            status=status,
            supported_families=supported_families,
            available=available,
        )
        return self.document_bridge_snapshot(session_mount_id=session_mount_id)

    def clear_document_bridge(
        self,
        *,
        session_mount_id: str,
        document_family: str | None = None,
    ) -> dict[str, Any]:
        runtime = self._require_document_bridge_runtime()
        runtime.clear_bridge(session_mount_id=session_mount_id)
        return self.document_bridge_snapshot(
            session_mount_id=session_mount_id,
            document_family=document_family,
        )

    def document_bridge_snapshot(
        self,
        *,
        session_mount_id: str,
        document_family: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        projection = self._cooperative_projection_for_session(
            session_mount_id,
            limit=limit,
        )
        snapshot = {
            "environment_id": projection.get("environment_id"),
            "session_mount_id": projection.get("session_mount_id"),
            "preferred_execution_path": projection.get("preferred_execution_path"),
            "ui_fallback_mode": projection.get("fallback_mode"),
            "adapter_gap_or_blocker": projection.get("current_gap_or_blocker"),
            "document_bridge": dict(projection.get("document_bridge") or {}),
        }
        if document_family is not None:
            runtime = self._require_document_bridge_runtime()
            hints = runtime.snapshot(
                session_mount_id=session_mount_id,
                document_family=document_family,
            )
            snapshot.update(
                {
                    "document_family": hints.get("document_family"),
                    "preferred_execution_path": hints.get("preferred_execution_path"),
                    "ui_fallback_mode": hints.get("ui_fallback_mode"),
                    "adapter_gap_or_blocker": hints.get("adapter_gap_or_blocker"),
                }
            )
        return snapshot

    def register_host_watchers(
        self,
        session_mount_id: str,
        *,
        filesystem: dict[str, Any] | None = None,
        downloads: dict[str, Any] | None = None,
        notifications: dict[str, Any] | None = None,
        adapter_gap_or_blocker: str | None = None,
    ) -> dict[str, Any]:
        runtime = self._require_host_watcher_runtime()
        return runtime.register_watchers(
            session_mount_id,
            filesystem=filesystem,
            downloads=downloads,
            notifications=notifications,
            adapter_gap_or_blocker=adapter_gap_or_blocker,
        )

    def emit_download_completed(
        self,
        session_mount_id: str,
        *,
        download_ref: str,
        filename: str | None = None,
        file_path: str | None = None,
        status: str = "completed",
        payload: dict[str, Any] | None = None,
    ):
        runtime = self._require_host_watcher_runtime()
        return runtime.emit_download_completed(
            session_mount_id,
            download_ref=download_ref,
            filename=filename,
            file_path=file_path,
            status=status,
            payload=payload,
        )

    def emit_notification(
        self,
        session_mount_id: str,
        *,
        action: str,
        payload: dict[str, Any] | None = None,
    ):
        runtime = self._require_host_watcher_runtime()
        return runtime.emit_notification(
            session_mount_id,
            action=action,
            payload=payload,
        )

    def host_watchers_snapshot(
        self,
        session_mount_id: str,
    ) -> dict[str, Any]:
        runtime = self._require_host_watcher_runtime()
        return runtime.snapshot(session_mount_id)

    def register_windows_app_adapter(
        self,
        *,
        session_mount_id: str,
        adapter_refs,
        app_identity: str | None = None,
        control_channel: str | None = None,
        preferred_execution_path: str | None = None,
        ui_fallback_mode: str | None = None,
        adapter_gap_or_blocker: str | None = None,
    ) -> dict[str, Any]:
        runtime = self._require_windows_app_adapter_runtime()
        runtime.register_adapter(
            session_mount_id=session_mount_id,
            adapter_refs=adapter_refs,
            app_identity=app_identity,
            control_channel=control_channel,
            preferred_execution_path=preferred_execution_path,
            ui_fallback_mode=ui_fallback_mode,
            adapter_gap_or_blocker=adapter_gap_or_blocker,
        )
        return self.windows_app_adapter_snapshot(session_mount_id=session_mount_id)

    def clear_windows_app_adapter(
        self,
        *,
        session_mount_id: str,
        adapter_refs=None,
        adapter_gap_or_blocker: str | None = None,
        preferred_execution_path: str | None = None,
        ui_fallback_mode: str | None = None,
    ) -> dict[str, Any]:
        runtime = self._require_windows_app_adapter_runtime()
        runtime.clear_adapter(
            session_mount_id=session_mount_id,
            adapter_refs=adapter_refs,
            adapter_gap_or_blocker=adapter_gap_or_blocker,
            preferred_execution_path=preferred_execution_path,
            ui_fallback_mode=ui_fallback_mode,
        )
        return self.windows_app_adapter_snapshot(session_mount_id=session_mount_id)

    def windows_app_adapter_snapshot(
        self,
        *,
        session_mount_id: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        projection = self._cooperative_projection_for_session(
            session_mount_id,
            limit=limit,
        )
        return {
            "environment_id": projection.get("environment_id"),
            "session_mount_id": projection.get("session_mount_id"),
            "preferred_execution_path": projection.get("preferred_execution_path"),
            "ui_fallback_mode": projection.get("fallback_mode"),
            "adapter_gap_or_blocker": projection.get("current_gap_or_blocker"),
            "windows_app_adapters": dict(
                projection.get("windows_app_adapters") or {},
            ),
        }

    def resolve_execution_path(
        self,
        **kwargs,
    ) -> ExecutionPathResolution:
        return resolve_preferred_execution_path(**kwargs)

    async def execute_document_action(
        self,
        *,
        session_mount_id: str,
        action: str,
        contract: dict[str, Any],
        host_executor: object | None = None,
        document_family: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        return await self._surface_control_service.execute_document_action(
            session_mount_id=session_mount_id,
            action=action,
            contract=contract,
            host_executor=host_executor,
            document_family=document_family,
            limit=limit,
        )

    async def execute_windows_app_action(
        self,
        *,
        session_mount_id: str,
        action: str,
        contract: dict[str, Any],
        host_executor: object | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        return await self._surface_control_service.execute_windows_app_action(
            session_mount_id=session_mount_id,
            action=action,
            contract=contract,
            host_executor=host_executor,
            limit=limit,
        )

    def _cooperative_projection_for_session(
        self,
        session_mount_id: str,
        *,
        limit: int = 20,
    ) -> dict[str, Any]:
        detail = self.get_session_detail(session_mount_id, limit=limit)
        if detail is None:
            raise LookupError(f"Session mount was not found: {session_mount_id}")
        projection = detail.get("cooperative_adapter_availability")
        if not isinstance(projection, dict):
            raise RuntimeError(
                "EnvironmentService session detail is missing the cooperative adapter projection.",
            )
        return projection

    def _rebind_cooperative_runtimes(self) -> None:
        environment_repository = getattr(self._registry, "_repository", None)
        if environment_repository is None or self._session_repository is None:
            self._browser_companion_runtime = None
            self._document_bridge_runtime = None
            self._host_watcher_runtime = None
            self._windows_app_adapter_runtime = None
            return
        self._browser_companion_runtime = BrowserCompanionRuntime(
            environment_repository=environment_repository,
            session_repository=self._session_repository,
            runtime_event_bus=self._runtime_event_bus,
        )
        self._document_bridge_runtime = DocumentBridgeRuntime(
            environment_repository=environment_repository,
            session_repository=self._session_repository,
        )
        self._host_watcher_runtime = HostWatcherRuntime(
            session_repository=self._session_repository,
            environment_repository=environment_repository,
            runtime_event_bus=self._runtime_event_bus,
        )
        self._windows_app_adapter_runtime = WindowsAppAdapterRuntime(self)

    def _require_browser_companion_runtime(self) -> BrowserCompanionRuntime:
        self._rebind_cooperative_runtimes()
        if self._browser_companion_runtime is None:
            raise RuntimeError(
                "BrowserCompanionRuntime requires EnvironmentRegistry.repository and SessionMountRepository.",
            )
        return self._browser_companion_runtime

    def _require_document_bridge_runtime(self) -> DocumentBridgeRuntime:
        self._rebind_cooperative_runtimes()
        if self._document_bridge_runtime is None:
            raise RuntimeError(
                "DocumentBridgeRuntime requires EnvironmentRegistry.repository and SessionMountRepository.",
            )
        return self._document_bridge_runtime

    def _require_host_watcher_runtime(self) -> HostWatcherRuntime:
        self._rebind_cooperative_runtimes()
        if self._host_watcher_runtime is None:
            raise RuntimeError(
                "HostWatcherRuntime requires EnvironmentRegistry.repository and SessionMountRepository.",
            )
        return self._host_watcher_runtime

    def _require_windows_app_adapter_runtime(self) -> WindowsAppAdapterRuntime:
        self._rebind_cooperative_runtimes()
        if self._windows_app_adapter_runtime is None:
            raise RuntimeError(
                "WindowsAppAdapterRuntime requires EnvironmentRegistry.repository and SessionMountRepository.",
            )
        return self._windows_app_adapter_runtime
