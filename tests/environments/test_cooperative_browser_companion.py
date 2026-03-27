# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.app.runtime_events import RuntimeEventBus
from copaw.capabilities.browser_runtime import BrowserRuntimeService
from copaw.environments.cooperative.browser_companion import BrowserCompanionRuntime
from copaw.environments.registry import EnvironmentRegistry
from copaw.environments.repository import EnvironmentRepository, SessionMountRepository
from copaw.environments.service import EnvironmentService
from copaw.state import SQLiteStateStore


def _build_services(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    environment_service.set_session_repository(session_repo)
    event_bus = RuntimeEventBus(max_events=20)
    environment_service.set_runtime_event_bus(event_bus)

    environment = env_repo.touch_environment(
        env_id="env:browser:web:main",
        kind="browser",
        display_name="Primary browser seat",
        ref="browser:web:main",
        metadata={
            "provider_kind": "local-managed-browser",
        },
        evidence_delta=0,
    )
    session = session_repo.touch_session(
        session_mount_id="session:browser:web:main",
        environment_id=environment.id,
        channel="browser",
        session_id="web:main",
        user_id="alice",
        metadata={
            "provider_kind": "local-managed-browser",
        },
    )
    companion_runtime = BrowserCompanionRuntime(
        environment_repository=env_repo,
        session_repository=session_repo,
        runtime_event_bus=event_bus,
    )
    browser_runtime = BrowserRuntimeService(
        store,
        browser_companion_runtime=companion_runtime,
    )
    return (
        environment_service,
        env_repo,
        session_repo,
        event_bus,
        environment,
        session,
        companion_runtime,
        browser_runtime,
    )


def test_browser_companion_registration_persists_metadata_and_projection(tmp_path) -> None:
    (
        environment_service,
        env_repo,
        session_repo,
        event_bus,
        environment,
        session,
        companion_runtime,
        _browser_runtime,
    ) = _build_services(tmp_path)

    snapshot = companion_runtime.register_companion(
        environment_id=environment.id,
        session_mount_id=session.id,
        transport_ref="transport:browser-companion:localhost",
        status="attached",
        available=True,
        provider_session_ref="browser-session:web:main",
    )

    stored_environment = env_repo.get_environment(environment.id)
    stored_session = session_repo.get_session(session.id)
    assert stored_environment is not None
    assert stored_session is not None
    assert (
        stored_environment.metadata["browser_companion_transport_ref"]
        == "transport:browser-companion:localhost"
    )
    assert stored_environment.metadata["preferred_execution_path"] == "cooperative-native-first"
    assert stored_session.metadata["browser_companion_status"] == "attached"
    assert stored_session.metadata["browser_companion_available"] is True
    assert stored_session.metadata["provider_session_ref"] == "browser-session:web:main"

    detail = environment_service.get_session_detail(session.id, limit=5)
    assert detail is not None
    projection = detail["cooperative_adapter_availability"]
    assert projection["preferred_execution_path"] == "cooperative-native-first"
    assert projection["fallback_mode"] == "ui-fallback-last"
    assert projection["browser_companion"] == {
        "available": True,
        "status": "attached",
        "transport_ref": "transport:browser-companion:localhost",
        "provider_session_ref": "browser-session:web:main",
    }

    events = event_bus.list_events(limit=10)
    assert len(events) == 1
    assert events[0].topic == "cooperative_adapter"
    assert events[0].action == "browser_companion_updated"
    assert events[0].payload["environment_id"] == environment.id
    assert events[0].payload["session_mount_id"] == session.id
    assert snapshot["preferred_execution_path"] == "cooperative-native-first"


def test_browser_companion_unavailable_prefers_semantic_operator_before_ui_fallback(
    tmp_path,
) -> None:
    (
        environment_service,
        _env_repo,
        session_repo,
        _event_bus,
        environment,
        session,
        companion_runtime,
        _browser_runtime,
    ) = _build_services(tmp_path)

    companion_runtime.register_companion(
        environment_id=environment.id,
        session_mount_id=session.id,
        transport_ref="transport:browser-companion:localhost",
        status="attached",
        available=True,
    )

    snapshot = companion_runtime.register_companion(
        environment_id=environment.id,
        session_mount_id=session.id,
        transport_ref=None,
        status="blocked",
        available=False,
        adapter_gap_or_blocker="Browser companion is offline.",
    )

    stored_session = session_repo.get_session(session.id)
    assert stored_session is not None
    assert stored_session.metadata["browser_companion_available"] is False
    assert stored_session.metadata["preferred_execution_path"] == "semantic-operator-second"
    assert stored_session.metadata["ui_fallback_mode"] == "ui-fallback-last"
    assert stored_session.metadata["adapter_gap_or_blocker"] == "Browser companion is offline."

    detail = environment_service.get_session_detail(session.id, limit=5)
    assert detail is not None
    projection = detail["cooperative_adapter_availability"]
    assert projection["preferred_execution_path"] == "semantic-operator-second"
    assert projection["fallback_mode"] == "ui-fallback-last"
    assert projection["current_gap_or_blocker"] == "Browser companion is offline."
    assert projection["browser_companion"]["available"] is False
    assert projection["browser_companion"]["status"] == "blocked"
    assert projection["browser_companion"]["transport_ref"] is None
    assert snapshot["preferred_execution_path"] == "semantic-operator-second"


def test_browser_runtime_service_exposes_companion_snapshot_and_registration_helper(
    tmp_path,
) -> None:
    (
        _environment_service,
        _env_repo,
        _session_repo,
        _event_bus,
        environment,
        session,
        _companion_runtime,
        browser_runtime,
    ) = _build_services(tmp_path)

    result = browser_runtime.register_companion(
        environment_id=environment.id,
        session_mount_id=session.id,
        transport_ref="transport:browser-companion:localhost",
        status="ready",
        available=True,
    )

    assert result["browser_companion"]["available"] is True
    assert result["preferred_execution_path"] == "cooperative-native-first"

    snapshot = browser_runtime.runtime_snapshot(
        environment_id=environment.id,
        session_mount_id=session.id,
    )
    assert "profiles" in snapshot
    companion_snapshot = browser_runtime.companion_snapshot(
        environment_id=environment.id,
        session_mount_id=session.id,
    )
    assert snapshot["browser_companion"]["status"] == "ready"
    assert companion_snapshot["transport_ref"] == "transport:browser-companion:localhost"
