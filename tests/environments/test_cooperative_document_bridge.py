# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    SessionMountRepository,
)
from copaw.state import SQLiteStateStore
from copaw.environments.cooperative.document_bridge import DocumentBridgeRuntime


def _bootstrap_session_mount(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    environment_repository = EnvironmentRepository(store)
    session_repository = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=environment_repository,
        session_repository=session_repository,
    )
    environment = registry.register(
        ref="session:console:doc-session",
        kind="session",
        metadata={
            "channel": "console",
            "session_id": "doc-session",
            "user_id": "user-1",
            "workspace_id": "workspace-main",
        },
    )
    assert environment is not None
    session = session_repository.get_session("session:console:doc-session")
    assert session is not None
    runtime = DocumentBridgeRuntime(
        environment_repository=environment_repository,
        session_repository=session_repository,
    )
    return runtime, environment_repository, session_repository, environment, session


def test_document_bridge_registers_bridge_metadata_on_session_and_environment(tmp_path) -> None:
    runtime, environment_repository, session_repository, environment, session = (
        _bootstrap_session_mount(tmp_path)
    )

    updated_session = runtime.register_bridge(
        session_mount_id=session.id,
        bridge_ref="document-bridge:office",
        status="ready",
        supported_families=["documents", "spreadsheets"],
    )

    assert updated_session is not None
    refreshed_session = session_repository.get_session(session.id)
    refreshed_environment = environment_repository.get_environment(environment.id)
    assert refreshed_session is not None
    assert refreshed_environment is not None
    assert refreshed_session.metadata["document_bridge_ref"] == "document-bridge:office"
    assert refreshed_session.metadata["document_bridge_status"] == "ready"
    assert refreshed_session.metadata["document_bridge_available"] is True
    assert refreshed_session.metadata["document_bridge_supported_families"] == [
        "documents",
        "spreadsheets",
    ]
    assert refreshed_session.metadata["preferred_execution_path"] == "cooperative-native-first"
    assert refreshed_session.metadata["ui_fallback_mode"] == "ui-fallback-last"
    assert refreshed_session.metadata["adapter_gap_or_blocker"] is None
    assert refreshed_environment.metadata["document_bridge_ref"] == "document-bridge:office"
    assert refreshed_environment.metadata["document_bridge_status"] == "ready"
    assert refreshed_environment.metadata["document_bridge_available"] is True
    assert refreshed_environment.metadata["document_bridge_supported_families"] == [
        "documents",
        "spreadsheets",
    ]
    assert refreshed_environment.metadata["preferred_execution_path"] == "cooperative-native-first"
    assert refreshed_environment.metadata["ui_fallback_mode"] == "ui-fallback-last"
    assert refreshed_environment.metadata["adapter_gap_or_blocker"] is None


def test_document_bridge_register_updates_supported_families_without_clobbering_existing_metadata(
    tmp_path,
) -> None:
    runtime, environment_repository, session_repository, environment, session = (
        _bootstrap_session_mount(tmp_path)
    )
    runtime.register_bridge(
        session_mount_id=session.id,
        bridge_ref="document-bridge:office",
        status="ready",
        supported_families=["documents"],
    )

    runtime.register_bridge(
        session_mount_id=session.id,
        bridge_ref="document-bridge:office",
        status="ready",
        supported_families=["spreadsheets", "documents", "spreadsheets"],
    )

    refreshed_session = session_repository.get_session(session.id)
    refreshed_environment = environment_repository.get_environment(environment.id)
    assert refreshed_session is not None
    assert refreshed_environment is not None
    assert refreshed_session.metadata["workspace_id"] == "workspace-main"
    assert refreshed_environment.metadata["workspace_id"] == "workspace-main"
    assert refreshed_session.metadata["document_bridge_ref"] == "document-bridge:office"
    assert refreshed_environment.metadata["document_bridge_ref"] == "document-bridge:office"
    assert refreshed_session.metadata["document_bridge_supported_families"] == [
        "documents",
        "spreadsheets",
    ]
    assert refreshed_environment.metadata["document_bridge_supported_families"] == [
        "documents",
        "spreadsheets",
    ]


def test_document_bridge_path_selection_prefers_cooperative_native_for_known_document_families(
    tmp_path,
) -> None:
    runtime, environment_repository, session_repository, environment, session = (
        _bootstrap_session_mount(tmp_path)
    )
    runtime.register_bridge(
        session_mount_id=session.id,
        bridge_ref="document-bridge:office",
        status="ready",
        supported_families=["documents", "spreadsheets"],
    )

    hints = runtime.snapshot(
        session_mount_id=session.id,
        document_family="xlsx",
    )

    refreshed_session = session_repository.get_session(session.id)
    refreshed_environment = environment_repository.get_environment(environment.id)
    assert hints["document_family"] == "spreadsheets"
    assert hints["preferred_execution_path"] == "cooperative-native-first"
    assert hints["ui_fallback_mode"] == "ui-fallback-last"
    assert hints["adapter_gap_or_blocker"] is None
    assert refreshed_session is not None
    assert refreshed_environment is not None
    assert refreshed_session.metadata["preferred_execution_path"] == "cooperative-native-first"
    assert refreshed_session.metadata["ui_fallback_mode"] == "ui-fallback-last"
    assert refreshed_session.metadata["adapter_gap_or_blocker"] is None
    assert refreshed_environment.metadata["preferred_execution_path"] == "cooperative-native-first"
    assert refreshed_environment.metadata["ui_fallback_mode"] == "ui-fallback-last"
    assert refreshed_environment.metadata["adapter_gap_or_blocker"] is None
