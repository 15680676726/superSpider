# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from copaw.environments import EnvironmentRegistry, EnvironmentService
from copaw.environments.repository import EnvironmentRepository, SessionMountRepository
from copaw.state import SQLiteStateStore


def _build_environment_service(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4040,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)
    return service, env_repo, session_repo


def _acquire_browser_session(service: EnvironmentService):
    return service.acquire_session_lease(
        channel="browser",
        session_id="browser-seat-1",
        user_id="alice",
        owner="worker-4",
        ttl_seconds=60,
        metadata={
            "host_mode": "attach-existing-session",
            "lease_class": "exclusive-writer",
            "access_mode": "writer",
            "session_scope": "browser-user-session",
        },
    )


def test_register_browser_attach_transport_persists_transport_and_session_refs(
    tmp_path,
) -> None:
    service, env_repo, session_repo = _build_environment_service(tmp_path)
    lease = _acquire_browser_session(service)

    detail = service.register_browser_attach_transport(
        session_mount_id=lease.id,
        transport_ref="chrome-native-host:default",
        status="attached",
        browser_session_ref="chrome-session:alice-default",
        browser_scope_ref="chrome-profile:alice",
        reconnect_token="reconnect-token-1",
    )

    session = session_repo.get_session(lease.id)
    assert session is not None
    environment = env_repo.get_environment(session.environment_id)
    assert environment is not None

    assert session.metadata["browser_attach_transport_ref"] == "chrome-native-host:default"
    assert session.metadata["browser_attach_session_ref"] == "chrome-session:alice-default"
    assert session.metadata["browser_attach_scope_ref"] == "chrome-profile:alice"
    assert session.metadata["browser_attach_reconnect_token"] == "reconnect-token-1"
    assert detail["browser_attach"]["transport_ref"] == "chrome-native-host:default"
    assert detail["browser_attach"]["session_ref"] == "chrome-session:alice-default"


def test_clear_browser_attach_transport_keeps_mount_truth_and_marks_runtime_cleared(
    tmp_path,
) -> None:
    service, _, session_repo = _build_environment_service(tmp_path)
    lease = _acquire_browser_session(service)

    service.register_browser_attach_transport(
        session_mount_id=lease.id,
        transport_ref="chrome-native-host:default",
        status="attached",
        browser_session_ref="chrome-session:alice-default",
        browser_scope_ref="chrome-profile:alice",
        reconnect_token="reconnect-token-1",
    )

    detail = service.clear_browser_attach_transport(
        session_mount_id=lease.id,
        adapter_gap_or_blocker="browser attach cleared",
    )

    session = session_repo.get_session(lease.id)
    assert session is not None
    assert session.metadata["browser_attach_transport_ref"] is None
    assert detail["browser_attach"]["transport_ref"] is None
    assert detail["browser_attach"]["status"] is None
    assert detail["adapter_gap_or_blocker"] == "browser attach cleared"


def test_bridge_reconnect_without_transport_preserves_existing_attach_refs(
    tmp_path,
) -> None:
    service, env_repo, session_repo = _build_environment_service(tmp_path)
    lease = _acquire_browser_session(service)
    assert lease.lease_token is not None

    service.ack_bridge_session_work(
        lease.id,
        lease_token=lease.lease_token,
        work_id="bridge-work-attach-2",
        bridge_session_id="bridge-session-2",
        browser_attach_transport_ref="chrome-native-host:default",
        browser_attach_status="attached",
        browser_attach_session_ref="chrome-session:alice-default",
        browser_attach_scope_ref="chrome-profile:alice",
        browser_attach_reconnect_token="reconnect-token-1",
    )

    reconnected = service.reconnect_bridge_session_work(
        lease.id,
        lease_token=lease.lease_token,
        work_id="bridge-work-attach-2",
        browser_attach_status="reconnecting",
        browser_attach_reconnect_token="reconnect-token-2",
    )

    session = session_repo.get_session(lease.id)
    assert session is not None
    environment = env_repo.get_environment(lease.environment_id)
    assert environment is not None
    snapshot = service.browser_attach_snapshot(session_mount_id=lease.id)

    assert reconnected.metadata["bridge_work_status"] == "reconnecting"
    assert session.metadata["browser_attach_transport_ref"] == "chrome-native-host:default"
    assert session.metadata["browser_attach_session_ref"] == "chrome-session:alice-default"
    assert session.metadata["browser_attach_scope_ref"] == "chrome-profile:alice"
    assert session.metadata["browser_attach_reconnect_token"] == "reconnect-token-2"
    assert environment.metadata["browser_attach_transport_ref"] == "chrome-native-host:default"
    assert snapshot["browser_attach"]["transport_ref"] == "chrome-native-host:default"
    assert snapshot["browser_attach"]["status"] == "reconnecting"
    assert snapshot["browser_attach"]["session_ref"] == "chrome-session:alice-default"
    assert snapshot["browser_attach"]["scope_ref"] == "chrome-profile:alice"


def test_bridge_reconnect_blocker_only_updates_adapter_gap_without_dropping_attach_state(
    tmp_path,
) -> None:
    service, env_repo, session_repo = _build_environment_service(tmp_path)
    lease = _acquire_browser_session(service)
    assert lease.lease_token is not None

    service.ack_bridge_session_work(
        lease.id,
        lease_token=lease.lease_token,
        work_id="bridge-work-attach-3",
        bridge_session_id="bridge-session-3",
        browser_attach_transport_ref="chrome-native-host:default",
        browser_attach_status="attached",
        browser_attach_session_ref="chrome-session:alice-default",
        browser_attach_scope_ref="chrome-profile:alice",
        browser_attach_reconnect_token="reconnect-token-1",
    )

    reconnected = service.reconnect_bridge_session_work(
        lease.id,
        lease_token=lease.lease_token,
        work_id="bridge-work-attach-3",
        adapter_gap_or_blocker="browser attach blocked by policy",
    )

    session = session_repo.get_session(lease.id)
    assert session is not None
    environment = env_repo.get_environment(lease.environment_id)
    assert environment is not None
    snapshot = service.browser_attach_snapshot(session_mount_id=lease.id)

    assert reconnected.metadata["bridge_work_status"] == "reconnecting"
    assert session.metadata["browser_attach_transport_ref"] == "chrome-native-host:default"
    assert session.metadata["browser_attach_session_ref"] == "chrome-session:alice-default"
    assert session.metadata["browser_attach_scope_ref"] == "chrome-profile:alice"
    assert session.metadata["browser_attach_reconnect_token"] == "reconnect-token-1"
    assert session.metadata["adapter_gap_or_blocker"] == "browser attach blocked by policy"
    assert environment.metadata["adapter_gap_or_blocker"] == "browser attach blocked by policy"
    assert snapshot["adapter_gap_or_blocker"] == "browser attach blocked by policy"
    assert snapshot["browser_attach"]["transport_ref"] == "chrome-native-host:default"
    assert snapshot["browser_attach"]["status"] == "attached"


def test_browser_attach_runtime_requires_existing_mounts(tmp_path) -> None:
    service, _, _ = _build_environment_service(tmp_path)

    with pytest.raises(KeyError):
        service.register_browser_attach_transport(
            session_mount_id="missing",
            transport_ref="chrome-native-host:default",
        )


def test_browser_attach_snapshot_can_resolve_from_environment_id(tmp_path) -> None:
    service, _, _ = _build_environment_service(tmp_path)
    lease = _acquire_browser_session(service)

    service.register_browser_attach_transport(
        session_mount_id=lease.id,
        transport_ref="chrome-native-host:default",
        status="attached",
        browser_session_ref="chrome-session:alice-default",
        browser_scope_ref="chrome-profile:alice",
        reconnect_token="reconnect-token-1",
    )

    snapshot = service.browser_attach_snapshot(environment_id=lease.environment_id)

    assert snapshot["environment_id"] == lease.environment_id
    assert snapshot["session_mount_id"] == lease.id
    assert snapshot["browser_attach"]["transport_ref"] == "chrome-native-host:default"
    assert snapshot["browser_attach"]["session_ref"] == "chrome-session:alice-default"


def test_browser_attach_runtime_replaces_stale_legacy_attach_transport_projection(
    tmp_path,
) -> None:
    service, env_repo, session_repo = _build_environment_service(tmp_path)
    lease = _acquire_browser_session(service)

    session = session_repo.get_session(lease.id)
    assert session is not None
    session.metadata["attach_transport_ref"] = "legacy:stale"
    session_repo.upsert_session(session)

    environment = env_repo.get_environment(lease.environment_id)
    assert environment is not None
    environment.metadata["attach_transport_ref"] = "legacy:stale"
    env_repo.upsert_environment(environment)

    service.register_browser_attach_transport(
        session_mount_id=lease.id,
        transport_ref="chrome-native-host:default",
        status="attached",
        browser_session_ref="chrome-session:alice-default",
        browser_scope_ref="chrome-profile:alice",
        reconnect_token="reconnect-token-1",
    )

    detail = service.get_session_detail(lease.id)
    assert detail is not None
    assert detail["browser_site_contract"]["attach_transport_ref"] == "chrome-native-host:default"
    assert detail["browser_site_contract"]["attach_session_ref"] == "chrome-session:alice-default"
    assert detail["browser_site_contract"]["attach_scope_ref"] == "chrome-profile:alice"
    assert detail["browser_site_contract"]["attach_reconnect_token"] == "reconnect-token-1"

    service.clear_browser_attach_transport(session_mount_id=lease.id)

    cleared = service.get_session_detail(lease.id)
    assert cleared is not None
    assert cleared["browser_site_contract"]["attach_transport_ref"] is None
    assert cleared["browser_site_contract"]["attach_session_ref"] is None
    assert cleared["browser_site_contract"]["attach_scope_ref"] is None
    assert cleared["browser_site_contract"]["attach_reconnect_token"] is None


def test_bridge_lifecycle_can_drive_browser_attach_transport_on_same_mount_truth(
    tmp_path,
) -> None:
    service, env_repo, session_repo = _build_environment_service(tmp_path)
    lease = _acquire_browser_session(service)
    assert lease.lease_token is not None

    acknowledged = service.ack_bridge_session_work(
        lease.id,
        lease_token=lease.lease_token,
        work_id="bridge-work-attach-1",
        bridge_session_id="bridge-session-1",
        browser_attach_transport_ref="chrome-native-host:default",
        browser_attach_status="attached",
        browser_attach_session_ref="chrome-session:alice-default",
        browser_attach_scope_ref="chrome-profile:alice",
        browser_attach_reconnect_token="reconnect-token-1",
    )
    reconnected = service.reconnect_bridge_session_work(
        lease.id,
        lease_token=lease.lease_token,
        work_id="bridge-work-attach-1",
        browser_attach_transport_ref="chrome-native-host:reconnected",
        browser_attach_status="reconnecting",
        browser_attach_session_ref="chrome-session:alice-default",
        browser_attach_scope_ref="chrome-profile:alice",
        browser_attach_reconnect_token="reconnect-token-2",
    )

    session = session_repo.get_session(lease.id)
    assert session is not None
    environment = env_repo.get_environment(lease.environment_id)
    assert environment is not None
    snapshot = service.browser_attach_snapshot(session_mount_id=lease.id)

    assert len(service.list_sessions(environment_id=lease.environment_id, limit=10)) == 1
    assert acknowledged.metadata["bridge_work_status"] == "acknowledged"
    assert reconnected.metadata["bridge_work_status"] == "reconnecting"
    assert session.metadata["browser_attach_transport_ref"] == "chrome-native-host:reconnected"
    assert session.metadata["browser_attach_reconnect_token"] == "reconnect-token-2"
    assert environment.metadata["browser_attach_transport_ref"] == "chrome-native-host:reconnected"
    assert snapshot["browser_attach"]["transport_ref"] == "chrome-native-host:reconnected"
    assert snapshot["browser_attach"]["status"] == "reconnecting"
    assert snapshot["browser_attach"]["reconnect_token"] == "reconnect-token-2"


def test_bridge_stop_clears_browser_attach_continuity_before_reconnect(tmp_path) -> None:
    service, env_repo, session_repo = _build_environment_service(tmp_path)
    lease = _acquire_browser_session(service)
    assert lease.lease_token is not None

    service.ack_bridge_session_work(
        lease.id,
        lease_token=lease.lease_token,
        work_id="bridge-work-attach-stop",
        bridge_session_id="bridge-session-stop",
        browser_attach_transport_ref="chrome-native-host:default",
        browser_attach_status="attached",
        browser_attach_session_ref="chrome-session:alice-default",
        browser_attach_scope_ref="chrome-profile:alice",
        browser_attach_reconnect_token="reconnect-token-1",
    )

    stopped = service.stop_bridge_session_work(
        lease.id,
        work_id="bridge-work-attach-stop",
        force=True,
        reason="bridge supervisor stop",
    )
    reconnected = service.reconnect_bridge_session_work(
        lease.id,
        lease_token=lease.lease_token,
        work_id="bridge-work-attach-stop",
        browser_attach_status="reconnecting",
    )

    session = session_repo.get_session(lease.id)
    assert session is not None
    environment = env_repo.get_environment(lease.environment_id)
    assert environment is not None
    snapshot = service.browser_attach_snapshot(session_mount_id=lease.id)

    assert stopped.metadata["bridge_work_status"] == "stopped"
    assert reconnected.metadata["bridge_work_status"] == "reconnecting"
    assert session.metadata["browser_attach_transport_ref"] is None
    assert session.metadata["browser_attach_session_ref"] is None
    assert session.metadata["browser_attach_scope_ref"] is None
    assert session.metadata["browser_attach_reconnect_token"] is None
    assert environment.metadata["browser_attach_transport_ref"] is None
    assert environment.metadata["browser_attach_session_ref"] is None
    assert environment.metadata["browser_attach_scope_ref"] is None
    assert environment.metadata["browser_attach_reconnect_token"] is None
    assert snapshot["browser_attach"] == {
        "transport_ref": None,
        "status": "reconnecting",
        "session_ref": None,
        "scope_ref": None,
        "reconnect_token": None,
    }


def test_release_browser_attach_transport_clears_session_and_environment_truth(
    tmp_path,
) -> None:
    service, env_repo, session_repo = _build_environment_service(tmp_path)
    lease = _acquire_browser_session(service)

    service.register_browser_attach_transport(
        session_mount_id=lease.id,
        transport_ref="chrome-native-host:default",
        status="attached",
        browser_session_ref="chrome-session:alice-default",
        browser_scope_ref="chrome-profile:alice",
        reconnect_token="reconnect-token-1",
    )

    released = service.release_session_lease(
        lease.id,
        lease_token=lease.lease_token,
        reason="runtime stop",
    )

    session = session_repo.get_session(lease.id)
    assert session is not None
    environment = env_repo.get_environment(lease.environment_id)
    assert environment is not None
    snapshot = service.browser_attach_snapshot(session_mount_id=lease.id)

    assert released is not None
    assert released.lease_status == "released"
    assert session.metadata["browser_attach_transport_ref"] is None
    assert session.metadata["browser_attach_session_ref"] is None
    assert session.metadata["browser_attach_scope_ref"] is None
    assert session.metadata["browser_attach_reconnect_token"] is None
    assert environment.metadata["browser_attach_transport_ref"] is None
    assert environment.metadata["browser_attach_session_ref"] is None
    assert environment.metadata["browser_attach_scope_ref"] is None
    assert environment.metadata["browser_attach_reconnect_token"] is None
    assert snapshot["browser_attach"] == {
        "transport_ref": None,
        "status": None,
        "session_ref": None,
        "scope_ref": None,
        "reconnect_token": None,
    }


def test_browser_channel_resolver_defaults_to_built_in_when_attach_path_is_unavailable(
    tmp_path,
) -> None:
    service, _, _ = _build_environment_service(tmp_path)
    lease = _acquire_browser_session(service)

    resolution = service.resolve_browser_channel(session_mount_id=lease.id)

    assert resolution["selected_channel"] == "built-in-browser"
    assert resolution["selected_capability_id"] == "tool:browser_use"
    assert resolution["selection_status"] == "ready"
    assert resolution["selected_channel_health"] == "healthy"
    assert resolution["attach_required"] is False
    assert resolution["fail_closed"] is False
    assert resolution["browser_mcp"]["healthy"] is False


def test_browser_channel_resolver_ignores_workspace_mount_without_browser_session(
    tmp_path,
) -> None:
    service, _, _ = _build_environment_service(tmp_path)
    workspace = service.touch_environment(
        ref=r"C:\Users\21492\.copaw",
        kind="workspace",
        status="active",
        metadata={"workspace_scope": "project:copaw"},
    )

    assert workspace is not None

    resolution = service.resolve_browser_channel(environment_id=workspace.id)

    assert resolution["selected_channel"] == "built-in-browser"
    assert resolution["selection_status"] == "ready"
    assert resolution["fail_closed"] is False
    assert resolution["browser_mcp"]["healthy"] is False


def test_browser_channel_resolver_prefers_browser_mcp_when_companion_and_attach_are_healthy(
    tmp_path,
) -> None:
    service, _, _ = _build_environment_service(tmp_path)
    lease = _acquire_browser_session(service)

    service.register_browser_companion(
        session_mount_id=lease.id,
        transport_ref="transport:browser-companion:localhost",
        status="attached",
        available=True,
        provider_session_ref="browser-session:web:main",
    )
    service.register_browser_attach_transport(
        session_mount_id=lease.id,
        transport_ref="transport:browser-companion:localhost",
        status="attached",
        browser_session_ref="browser-session:web:main",
        browser_scope_ref="chrome-profile:alice",
        reconnect_token="reconnect-token-1",
    )

    resolution = service.resolve_browser_channel(
        session_mount_id=lease.id,
        browser_mode="attach-existing-session",
    )

    assert resolution["selected_channel"] == "browser-mcp"
    assert resolution["selected_capability_id"] == "system:browser_companion_runtime"
    assert resolution["selection_status"] == "ready"
    assert resolution["selected_channel_health"] == "healthy"
    assert resolution["attach_required"] is True
    assert resolution["fail_closed"] is False
    assert resolution["browser_mcp"]["healthy"] is True
    assert resolution["browser_mcp"]["attach_transport_ref"] == (
        "transport:browser-companion:localhost"
    )


def test_browser_channel_resolver_keeps_built_in_default_for_general_browser_work(
    tmp_path,
) -> None:
    service, _, _ = _build_environment_service(tmp_path)
    lease = _acquire_browser_session(service)

    service.register_browser_companion(
        session_mount_id=lease.id,
        transport_ref="transport:browser-companion:localhost",
        status="attached",
        available=True,
        provider_session_ref="browser-session:web:main",
    )
    service.register_browser_attach_transport(
        session_mount_id=lease.id,
        transport_ref="transport:browser-companion:localhost",
        status="attached",
        browser_session_ref="browser-session:web:main",
        browser_scope_ref="chrome-profile:alice",
        reconnect_token="reconnect-token-1",
    )

    resolution = service.resolve_browser_channel(session_mount_id=lease.id)

    assert resolution["selected_channel"] == "built-in-browser"
    assert resolution["selected_capability_id"] == "tool:browser_use"
    assert resolution["selection_status"] == "ready"
    assert resolution["selected_channel_health"] == "healthy"
    assert resolution["attach_required"] is False
    assert resolution["fail_closed"] is False
    assert resolution["browser_mcp"]["healthy"] is True


def test_browser_channel_resolver_fails_closed_when_attach_is_required_but_not_available(
    tmp_path,
) -> None:
    service, _, _ = _build_environment_service(tmp_path)
    lease = _acquire_browser_session(service)

    resolution = service.resolve_browser_channel(
        session_mount_id=lease.id,
        browser_mode="attach-existing-session",
    )

    assert resolution["selected_channel"] is None
    assert resolution["selection_status"] == "blocked"
    assert resolution["selected_channel_health"] == "blocked"
    assert resolution["attach_required"] is True
    assert resolution["fail_closed"] is True
    assert "attach" in str(resolution["reason"]).lower()
