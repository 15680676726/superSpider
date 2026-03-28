# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.app.runtime_events import RuntimeEventBus
from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    SessionMountRepository,
)
from copaw.environments.host_event_recovery_service import HostEventRecoveryService
from copaw.state import SQLiteStateStore


def _build_recovery_harness(
    tmp_path,
    *,
    host_id: str = "windows-host",
    process_id: int = 4040,
):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id=host_id,
        process_id=process_id,
    )
    environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    environment_service.set_session_repository(session_repo)
    event_bus = RuntimeEventBus(max_events=50)
    environment_service.set_runtime_event_bus(event_bus)
    recovery_service = HostEventRecoveryService(
        environment_service=environment_service,
        runtime_event_bus=event_bus,
    )
    return SimpleNamespace(
        environment_service=environment_service,
        recovery_service=recovery_service,
        event_bus=event_bus,
        env_repo=env_repo,
        session_repo=session_repo,
    )


def test_host_event_recovery_service_reobserves_actionable_download_events(tmp_path) -> None:
    harness = _build_recovery_harness(tmp_path)
    lease = harness.environment_service.acquire_session_lease(
        channel="desktop",
        session_id="seat-download",
        owner="worker-1",
        ttl_seconds=60,
        handle={"window": "excel-main"},
        metadata={
            "resume_kind": "resume-environment",
            "verification_channel": "runtime-center-self-check",
        },
    )
    before = harness.session_repo.get_session(lease.id)
    assert before is not None

    harness.event_bus.publish(
        topic="download",
        action="download-completed",
        payload={
            "session_mount_id": lease.id,
            "environment_id": lease.environment_id,
            "download_ref": "download-bucket:workspace-main",
            "status": "completed",
        },
    )

    result = harness.recovery_service.run_recovery_cycle()

    after = harness.session_repo.get_session(lease.id)
    assert after is not None
    assert result["executed"] == 1
    assert result["decisions"]["reobserve"] == 1
    assert after.last_active_at >= before.last_active_at
    assert after.metadata["host_recovery_state"]["last_handled_event_name"] == (
        "download.download-completed"
    )
    assert after.metadata["host_recovery_state"]["last_handled_decision"] == "reobserve"
    assert "runtime.recovery-reobserved" in [
        event.event_name for event in harness.event_bus.list_events(limit=10)
    ]


def test_host_event_recovery_service_marks_handoff_without_live_handle_mutation(
    tmp_path,
) -> None:
    harness = _build_recovery_harness(tmp_path)
    lease = harness.environment_service.acquire_session_lease(
        channel="desktop",
        session_id="seat-handoff",
        owner="worker-1",
        ttl_seconds=60,
        handle={"window": "excel-main"},
        metadata={
            "resume_kind": "resume-environment",
            "verification_channel": "runtime-center-self-check",
        },
    )

    harness.event_bus.publish(
        topic="desktop",
        action="uac-prompt",
        payload={
            "session_mount_id": lease.id,
            "environment_id": lease.environment_id,
            "prompt_kind": "uac",
            "window_title": "User Account Control",
        },
    )

    result = harness.recovery_service.run_recovery_cycle()

    session = harness.session_repo.get_session(lease.id)
    assert session is not None
    assert result["executed"] == 1
    assert result["decisions"]["handoff"] == 1
    assert session.lease_status == "leased"
    assert session.live_handle_ref is not None
    assert session.metadata["host_recovery_state"]["last_handled_decision"] == "handoff"
    assert "runtime.recovery-handoff" in [
        event.event_name for event in harness.event_bus.list_events(limit=10)
    ]


def test_host_event_recovery_service_recovers_human_return_ready_with_registered_restorer(
    tmp_path,
) -> None:
    original = _build_recovery_harness(
        tmp_path,
        host_id="windows-host",
        process_id=5151,
    )
    lease = original.environment_service.acquire_session_lease(
        channel="desktop",
        session_id="seat-return",
        owner="worker-1",
        ttl_seconds=60,
        handle={"window": "excel-main"},
        metadata={
            "resume_kind": "resume-environment",
            "verification_channel": "runtime-center-self-check",
        },
    )

    recovered = _build_recovery_harness(
        tmp_path,
        host_id="windows-host",
        process_id=5151,
    )
    recovered.environment_service.register_session_handle_restorer(
        "desktop",
        lambda context: {
            "handle": {"window": "excel-restored"},
            "descriptor": {"restored_by": "test-restorer"},
            "metadata": {"restore_source": context["channel"]},
        },
    )
    recovered.event_bus.publish(
        topic="host",
        action="human-return-ready",
        payload={
            "session_mount_id": lease.id,
            "environment_id": lease.environment_id,
            "checkpoint_ref": "checkpoint:captcha",
            "verification_channel": "runtime-center-self-check",
            "return_condition": "captcha-cleared",
            "handoff_owner_ref": "human-operator:alice",
        },
    )

    result = recovered.recovery_service.run_recovery_cycle()

    restored = recovered.session_repo.get_session(lease.id)
    assert restored is not None
    assert result["executed"] == 1
    assert result["decisions"]["recover"] == 1
    assert restored.lease_status == "leased"
    assert restored.live_handle_ref is not None
    assert restored.metadata["restore_source"] == "desktop"
    assert restored.metadata["lease_restore_status"] == "restored"
    assert restored.metadata["host_recovery_state"]["last_handled_decision"] == "recover"
    assert "session.restored" in [
        event.event_name for event in recovered.event_bus.list_events(limit=10)
    ]
    assert "runtime.recovery-restored" in [
        event.event_name for event in recovered.event_bus.list_events(limit=10)
    ]


def test_host_event_recovery_service_resumes_unlock_events_when_handle_is_still_live(
    tmp_path,
) -> None:
    harness = _build_recovery_harness(tmp_path)
    lease = harness.environment_service.acquire_session_lease(
        channel="desktop",
        session_id="seat-unlock",
        owner="worker-1",
        ttl_seconds=60,
        handle={"window": "excel-main"},
        metadata={
            "resume_kind": "resume-environment",
            "verification_channel": "runtime-center-self-check",
            "handoff_state": "active",
            "handoff_reason": "machine-locked",
            "handoff_owner_ref": "human-operator:alice",
        },
    )

    harness.event_bus.publish(
        topic="desktop",
        action="desktop-unlocked",
        payload={
            "session_mount_id": lease.id,
            "environment_id": lease.environment_id,
        },
    )

    result = harness.recovery_service.run_recovery_cycle()

    session = harness.session_repo.get_session(lease.id)
    assert session is not None
    assert result["executed"] == 1
    assert result["decisions"]["resume"] == 1
    assert session.live_handle_ref is not None
    assert session.metadata["host_recovery_state"]["last_handled_decision"] == "resume"
    assert session.metadata["handoff_owner_ref"] is None
    assert "runtime.recovery-resumed" in [
        event.event_name for event in harness.event_bus.list_events(limit=10)
    ]


def test_host_event_recovery_service_is_idempotent_for_same_event(tmp_path) -> None:
    harness = _build_recovery_harness(tmp_path)
    lease = harness.environment_service.acquire_session_lease(
        channel="desktop",
        session_id="seat-idempotent",
        owner="worker-1",
        ttl_seconds=60,
        handle={"window": "excel-main"},
        metadata={
            "resume_kind": "resume-environment",
            "verification_channel": "runtime-center-self-check",
        },
    )
    harness.event_bus.publish(
        topic="download",
        action="download-completed",
        payload={
            "session_mount_id": lease.id,
            "environment_id": lease.environment_id,
            "download_ref": "download-bucket:workspace-main",
            "status": "completed",
        },
    )

    first = harness.recovery_service.run_recovery_cycle()
    second = harness.recovery_service.run_recovery_cycle()

    assert first["executed"] == 1
    assert second["executed"] == 0
    assert second["skipped"] == 1
    recovery_events = [
        event.event_name
        for event in harness.event_bus.list_events(limit=20)
        if event.event_name == "runtime.recovery-reobserved"
    ]
    assert recovery_events == ["runtime.recovery-reobserved"]
