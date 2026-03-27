# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.app.runtime_events import RuntimeEventBus
from copaw.environments.cooperative.watchers import HostWatcherRuntime
from copaw.environments.registry import EnvironmentRegistry
from copaw.environments.repository import EnvironmentRepository, SessionMountRepository
from copaw.environments.service import EnvironmentService
from copaw.state import SQLiteStateStore


def _build_runtime(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    environment_repository = EnvironmentRepository(store)
    session_repository = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=environment_repository,
        session_repository=session_repository,
        host_id="windows-host",
        process_id=4242,
    )
    environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    environment_service.set_session_repository(session_repository)
    runtime_event_bus = RuntimeEventBus(max_events=50)
    environment_service.set_runtime_event_bus(runtime_event_bus)
    lease = environment_service.acquire_session_lease(
        channel="desktop",
        session_id="seat-1",
        user_id="alice",
        owner="worker-3",
        ttl_seconds=60,
        metadata={
            "workspace_id": "workspace-main",
            "workspace_scope": "task:task-1",
        },
    )
    watchers = HostWatcherRuntime(
        session_repository=session_repository,
        environment_repository=environment_repository,
        runtime_event_bus=runtime_event_bus,
    )
    return (
        environment_repository,
        session_repository,
        environment_service,
        runtime_event_bus,
        lease,
        watchers,
    )


def test_register_watcher_families_persist_canonical_metadata(tmp_path):
    environment_repository, session_repository, _, _, lease, watchers = _build_runtime(
        tmp_path
    )

    snapshot = watchers.register_watchers(
        lease.id,
        filesystem={"status": "ready"},
        downloads={
            "status": "healthy",
            "download_policy": "download-bucket:workspace-main",
        },
        notifications={"status": "disabled"},
        adapter_gap_or_blocker="notifications blocked by host policy",
    )

    session = session_repository.get_session(lease.id)
    environment = environment_repository.get_environment(lease.environment_id)

    assert session is not None
    assert environment is not None
    assert session.metadata["filesystem_watcher_status"] == "ready"
    assert session.metadata["filesystem_watcher_available"] is True
    assert session.metadata["download_watcher_status"] == "healthy"
    assert session.metadata["download_watcher_available"] is True
    assert session.metadata["notification_watcher_status"] == "disabled"
    assert session.metadata["notification_watcher_available"] is False
    assert session.metadata["download_policy"] == "download-bucket:workspace-main"
    assert session.metadata["adapter_gap_or_blocker"] == (
        "notifications blocked by host policy"
    )
    assert environment.metadata["filesystem_watcher_status"] == "ready"
    assert environment.metadata["filesystem_watcher_available"] is True
    assert environment.metadata["download_watcher_status"] == "healthy"
    assert environment.metadata["download_watcher_available"] is True
    assert environment.metadata["notification_watcher_status"] == "disabled"
    assert environment.metadata["notification_watcher_available"] is False
    assert environment.metadata["download_policy"] == "download-bucket:workspace-main"
    assert environment.metadata["adapter_gap_or_blocker"] == (
        "notifications blocked by host policy"
    )
    assert snapshot["watchers"]["filesystem"] == {
        "status": "ready",
        "available": True,
    }
    assert snapshot["watchers"]["downloads"] == {
        "status": "healthy",
        "available": True,
        "download_policy": "download-bucket:workspace-main",
        "last_download_event": None,
    }
    assert snapshot["watchers"]["notifications"] == {
        "status": "disabled",
        "available": False,
    }
    assert snapshot["available_families"] == ["filesystem-watcher", "download-watcher"]
    assert snapshot["unavailable_families"] == ["notification-watcher"]
    assert snapshot["adapter_gap_or_blocker"] == "notifications blocked by host policy"


def test_download_completed_event_is_runtime_mechanism_not_truth_store(tmp_path):
    _, session_repository, environment_service, runtime_event_bus, lease, watchers = (
        _build_runtime(tmp_path)
    )
    watchers.register_watchers(
        lease.id,
        downloads={
            "status": "healthy",
            "download_policy": "download-bucket:workspace-main",
        },
    )
    before_metadata = dict(session_repository.get_session(lease.id).metadata)

    event = watchers.emit_download_completed(
        lease.id,
        download_ref="download:artifact-1",
        filename="report.csv",
        file_path="D:/downloads/report.csv",
    )

    assert event.event_name == "download.download-completed"
    assert event.payload["session_mount_id"] == lease.id
    assert event.payload["environment_id"] == lease.environment_id
    assert event.payload["download_ref"] == "download:artifact-1"
    assert event.payload["filename"] == "report.csv"
    assert runtime_event_bus.list_events()[-1].event_name == "download.download-completed"
    assert session_repository.get_session(lease.id).metadata == before_metadata

    detail = environment_service.get_environment_detail(lease.environment_id, limit=10)

    assert detail is not None
    assert detail["host_event_summary"]["family_counts"]["download-completed"] == 1
    assert detail["workspace_graph"]["download_status"]["latest_download_event"] == {
        "event_id": event.event_id,
        "event_name": "download.download-completed",
        "topic": "download",
        "action": "download-completed",
        "created_at": event.created_at.isoformat(),
        "severity": "low",
        "recommended_runtime_response": "re-observe",
    }


def test_snapshot_prefers_session_metadata_and_tracks_latest_download_event(tmp_path):
    environment_repository, _, _, _, lease, watchers = _build_runtime(tmp_path)
    watchers.register_watchers(
        lease.id,
        downloads={
            "status": "pending",
            "available": False,
        },
        adapter_gap_or_blocker="waiting for browser companion",
    )
    initial_snapshot = watchers.snapshot(lease.id)

    assert initial_snapshot["watchers"]["downloads"] == {
        "status": "pending",
        "available": False,
        "download_policy": None,
        "last_download_event": None,
    }
    assert initial_snapshot["adapter_gap_or_blocker"] == "waiting for browser companion"
    assert initial_snapshot["unavailable_families"] == ["download-watcher"]

    environment = environment_repository.get_environment(lease.environment_id)
    assert environment is not None
    environment_repository.touch_environment(
        env_id=environment.id,
        kind=environment.kind,
        display_name=environment.display_name,
        ref=environment.ref,
        metadata={
            "download_watcher_status": "disabled",
            "download_watcher_available": False,
            "download_policy": "download-bucket:stale",
            "adapter_gap_or_blocker": "stale environment fallback",
        },
        evidence_delta=0,
    )

    watchers.register_watchers(
        lease.id,
        downloads={
            "status": "healthy",
            "download_policy": "download-bucket:workspace-main",
        },
        adapter_gap_or_blocker=None,
    )
    watchers.emit_download_completed(
        lease.id,
        download_ref="download:artifact-2",
        filename="evidence.json",
    )
    updated_snapshot = watchers.snapshot(lease.id)

    assert updated_snapshot["watchers"]["downloads"]["status"] == "healthy"
    assert updated_snapshot["watchers"]["downloads"]["available"] is True
    assert (
        updated_snapshot["watchers"]["downloads"]["download_policy"]
        == "download-bucket:workspace-main"
    )
    assert updated_snapshot["watchers"]["downloads"]["last_download_event"] == {
        "event_name": "download.download-completed",
        "download_ref": "download:artifact-2",
        "filename": "evidence.json",
    }
    assert updated_snapshot["available_families"] == ["download-watcher"]
    assert updated_snapshot["unavailable_families"] == []
    assert updated_snapshot["adapter_gap_or_blocker"] is None
