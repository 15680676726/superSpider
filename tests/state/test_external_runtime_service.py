# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.state import SQLiteStateStore
from copaw.state.external_runtime_service import ExternalCapabilityRuntimeService
from copaw.state.repositories import SqliteExternalCapabilityRuntimeRepository


def _build_service(tmp_path) -> ExternalCapabilityRuntimeService:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteExternalCapabilityRuntimeRepository(store)
    return ExternalCapabilityRuntimeService(repository=repository)


def test_starting_same_service_in_same_scope_reuses_existing_instance(tmp_path) -> None:
    service = _build_service(tmp_path)

    first = service.create_or_reuse_service_runtime(
        capability_id="runtime:openspace",
        scope_kind="session",
        session_mount_id="session-1",
        owner_agent_id="copaw-agent-runner",
        command="openspace server",
    )
    second = service.create_or_reuse_service_runtime(
        capability_id="runtime:openspace",
        scope_kind="session",
        session_mount_id="session-1",
        owner_agent_id="copaw-agent-runner",
        command="openspace server",
    )

    assert second.runtime_id == first.runtime_id
    assert second.status == "starting"
    assert len(service.list_runtimes(capability_id="runtime:openspace")) == 1


def test_cli_run_creates_historical_execution_instance(tmp_path) -> None:
    service = _build_service(tmp_path)

    first = service.record_cli_run(
        capability_id="project:black",
        scope_kind="session",
        session_mount_id="session-1",
        owner_agent_id="copaw-agent-runner",
        command="black --version",
        success=True,
        exit_code=0,
    )
    second = service.record_cli_run(
        capability_id="project:black",
        scope_kind="session",
        session_mount_id="session-1",
        owner_agent_id="copaw-agent-runner",
        command="black broken.py",
        success=False,
        exit_code=1,
        last_error="formatting failed",
    )

    assert first.runtime_id != second.runtime_id
    assert first.runtime_kind == "cli"
    assert first.status == "completed"
    assert second.status == "failed"
    assert len(service.list_runtimes(capability_id="project:black")) == 2
