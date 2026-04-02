# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.app.runtime_events import RuntimeEventBus
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
        process_id=4242,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repo)
    service.set_runtime_event_bus(RuntimeEventBus(max_events=20))
    return service


def _acquire_desktop_session(service: EnvironmentService):
    return service.acquire_session_lease(
        channel="desktop",
        session_id="seat-operator-abort",
        user_id="u1",
        owner="worker-bridge",
        ttl_seconds=60,
        handle={"process_id": 4242},
    )


def test_windows_app_projection_keeps_explicit_local_abort_after_shared_clear(tmp_path):
    service = _build_environment_service(tmp_path)
    lease = _acquire_desktop_session(service)

    service.register_windows_app_adapter(
        session_mount_id=lease.id,
        adapter_refs=["app-adapter:excel"],
        app_identity="excel",
        control_channel="accessibility-tree",
        execution_guardrails={
            "operator_abort_channel": "global-esc",
            "operator_abort_requested": True,
        },
    )
    service.set_shared_operator_abort_state(
        session_mount_id=lease.id,
        channel="global-esc",
        reason="esc hotkey",
    )
    service.clear_shared_operator_abort_state(
        session_mount_id=lease.id,
        channel="global-esc",
        reason="resume",
    )

    detail = service.get_session_detail(lease.id, limit=20)
    assert detail is not None
    assert (
        detail["cooperative_adapter_availability"]["windows_app_adapters"][
            "execution_guardrails"
        ]["operator_abort_requested"]
        is True
    )
    assert (
        detail["desktop_app_contract"]["execution_guardrails"][
            "operator_abort_requested"
        ]
        is True
    )


def test_document_bridge_projection_keeps_explicit_local_abort_after_shared_clear(
    tmp_path,
):
    service = _build_environment_service(tmp_path)
    lease = _acquire_desktop_session(service)

    service.register_document_bridge(
        session_mount_id=lease.id,
        bridge_ref="document-bridge:office",
        status="ready",
        supported_families=["documents"],
        execution_guardrails={
            "operator_abort_channel": "global-esc",
            "operator_abort_requested": True,
        },
    )
    service.set_shared_operator_abort_state(
        session_mount_id=lease.id,
        channel="global-esc",
        reason="esc hotkey",
    )
    service.clear_shared_operator_abort_state(
        session_mount_id=lease.id,
        channel="global-esc",
        reason="resume",
    )

    detail = service.get_session_detail(lease.id, limit=20)
    assert detail is not None
    assert (
        detail["cooperative_adapter_availability"]["document_bridge"][
            "execution_guardrails"
        ]["operator_abort_requested"]
        is True
    )

