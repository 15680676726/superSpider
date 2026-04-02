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


def test_browser_attach_runtime_requires_existing_mounts(tmp_path) -> None:
    service, _, _ = _build_environment_service(tmp_path)

    with pytest.raises(KeyError):
        service.register_browser_attach_transport(
            session_mount_id="missing",
            transport_ref="chrome-native-host:default",
        )


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
