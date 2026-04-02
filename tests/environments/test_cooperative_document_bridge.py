# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

import pytest

from copaw.app.runtime_events import RuntimeEventBus
from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
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


def _build_environment_service(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    environment_repository = EnvironmentRepository(store)
    session_repository = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=environment_repository,
        session_repository=session_repository,
        host_id="windows-host",
        process_id=5252,
    )
    service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    service.set_session_repository(session_repository)
    event_bus = RuntimeEventBus(max_events=20)
    service.set_runtime_event_bus(event_bus)
    return service, environment_repository, session_repository, event_bus


def _acquire_document_session(service: EnvironmentService):
    return service.acquire_session_lease(
        channel="desktop",
        session_id="document-seat-1",
        user_id="alice",
        owner="worker-7",
        ttl_seconds=60,
        metadata={
            "host_mode": "local-managed",
            "lease_class": "exclusive-writer",
            "access_mode": "document-bridge",
            "session_scope": "desktop-user-session",
        },
    )


def _patch_document_abort_state(
    *,
    environment_repository,
    session_repository,
    session_mount_id: str,
    operator_abort_state: dict[str, object],
) -> None:
    session = session_repository.get_session(session_mount_id)
    assert session is not None
    environment = environment_repository.get_environment(session.environment_id)
    assert environment is not None
    session_repository.upsert_session(
        session.model_copy(
            update={
                "metadata": {
                    **session.metadata,
                    "operator_abort_state": dict(operator_abort_state),
                },
            },
        ),
    )
    environment_repository.upsert_environment(
        environment.model_copy(
            update={
                "metadata": {
                    **environment.metadata,
                    "operator_abort_state": dict(operator_abort_state),
                },
            },
        ),
    )


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


def test_document_bridge_registers_execution_guardrails_projection(tmp_path) -> None:
    service, environment_repository, session_repository, _event_bus = _build_environment_service(
        tmp_path,
    )
    lease = _acquire_document_session(service)

    detail = service.register_document_bridge(
        session_mount_id=lease.id,
        bridge_ref="document-bridge:office",
        status="ready",
        supported_families=["documents", "spreadsheets"],
        execution_guardrails={
            "operator_abort_channel": "global-esc",
            "host_exclusion_refs": ["window:copaw-overlay"],
            "frontmost_verification_required": True,
            "clipboard_roundtrip_required": True,
        },
    )

    session = session_repository.get_session(lease.id)
    assert session is not None
    environment = environment_repository.get_environment(session.environment_id)
    assert environment is not None
    expected_guardrails = {
        "operator_abort_channel": "global-esc",
        "host_exclusion_refs": ["window:copaw-overlay"],
        "frontmost_verification_required": True,
        "clipboard_roundtrip_required": True,
    }
    assert session.metadata["document_execution_guardrails"] == expected_guardrails
    assert environment.metadata["document_execution_guardrails"] == expected_guardrails
    assert detail["document_bridge"]["execution_guardrails"] == expected_guardrails


@pytest.mark.asyncio
async def test_document_action_blocks_when_operator_abort_guardrail_is_requested(
    tmp_path,
) -> None:
    service, _, _, _event_bus = _build_environment_service(tmp_path)
    lease = _acquire_document_session(service)
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

    class _Executor:
        async def __call__(self, **_kwargs):
            raise AssertionError("document executor should not run after operator abort")

    service.register_document_bridge_executor("document-bridge:office", _Executor())

    with pytest.raises(RuntimeError, match="operator abort"):
        await service.execute_document_action(
            session_mount_id=lease.id,
            action="write_document",
            document_family="documents",
            contract={},
        )


@pytest.mark.asyncio
async def test_document_action_blocks_when_global_operator_abort_channel_matches(
    tmp_path,
) -> None:
    service, environment_repository, session_repository, _event_bus = _build_environment_service(
        tmp_path,
    )
    lease = _acquire_document_session(service)
    service.register_document_bridge(
        session_mount_id=lease.id,
        bridge_ref="document-bridge:office",
        status="ready",
        supported_families=["documents"],
        execution_guardrails={
            "operator_abort_channel": "global-esc",
        },
    )
    _patch_document_abort_state(
        environment_repository=environment_repository,
        session_repository=session_repository,
        session_mount_id=lease.id,
        operator_abort_state={
            "channel": "global-esc",
            "requested": True,
            "reason": "global-esc",
        },
    )

    class _Executor:
        async def __call__(self, **_kwargs):
            raise AssertionError("document executor should not run after global operator abort")

    service.register_document_bridge_executor("document-bridge:office", _Executor())

    with pytest.raises(RuntimeError, match="operator abort"):
        await service.execute_document_action(
            session_mount_id=lease.id,
            action="write_document",
            document_family="documents",
            contract={},
        )


@pytest.mark.asyncio
async def test_document_action_enforces_host_exclusion_before_execution(
    tmp_path,
) -> None:
    service, _, _, _event_bus = _build_environment_service(tmp_path)
    lease = _acquire_document_session(service)
    service.register_document_bridge(
        session_mount_id=lease.id,
        bridge_ref="document-bridge:office",
        status="ready",
        supported_families=["documents"],
    )

    class _Executor:
        async def guardrail_snapshot(self, **_kwargs):
            return {"frontmost_window_ref": "window:copaw-overlay"}

        async def __call__(self, **_kwargs):
            raise AssertionError("document executor should not run when host exclusion blocks")

    service.register_document_bridge_executor("document-bridge:office", _Executor())

    with pytest.raises(RuntimeError, match="Host exclusion guardrail blocked"):
        await service.execute_document_action(
            session_mount_id=lease.id,
            action="write_document",
            document_family="documents",
            contract={
                "guardrails": {
                    "excluded_surface_refs": ["window:copaw-overlay"],
                },
            },
        )


@pytest.mark.asyncio
async def test_document_action_runs_frontmost_and_clipboard_guardrails_before_execution(
    tmp_path,
) -> None:
    service, _, _, _event_bus = _build_environment_service(tmp_path)
    lease = _acquire_document_session(service)
    service.register_document_bridge(
        session_mount_id=lease.id,
        bridge_ref="document-bridge:office",
        status="ready",
        supported_families=["documents"],
        execution_guardrails={
            "frontmost_verification_required": True,
            "clipboard_roundtrip_required": True,
        },
    )

    call_order: list[str] = []

    class _Executor:
        async def verify_frontmost(self, **_kwargs):
            call_order.append("frontmost")
            return {"verified": True}

        async def verify_clipboard_roundtrip(self, **_kwargs):
            call_order.append("clipboard")
            return {"verified": True}

        async def __call__(self, **_kwargs):
            call_order.append("execute")
            return {"success": True, "message": "document ok"}

    service.register_document_bridge_executor("document-bridge:office", _Executor())

    result = await service.execute_document_action(
        session_mount_id=lease.id,
        action="write_document",
        document_family="documents",
        contract={},
    )

    assert result["success"] is True
    assert call_order == ["frontmost", "clipboard", "execute"]


def test_document_action_publishes_guardrail_block_event(tmp_path) -> None:
    service, _, _, event_bus = _build_environment_service(tmp_path)
    lease = _acquire_document_session(service)
    service.register_document_bridge(
        session_mount_id=lease.id,
        bridge_ref="document-bridge:office",
        status="ready",
        supported_families=["documents"],
        execution_guardrails={
            "operator_abort_requested": True,
            "abort_reason": "global-esc",
        },
    )

    def _executor(**_kwargs):
        return {"ok": True}

    service.register_document_bridge_executor("document-bridge:office", _executor)

    with pytest.raises(RuntimeError, match="operator abort"):
        asyncio.run(
            service.execute_document_action(
                session_mount_id=lease.id,
                action="write_document",
                document_family="documents",
                contract={},
            ),
        )

    blocked = [
        event
        for event in event_bus.list_events(limit=10)
        if event.event_name == "document.guardrail-blocked"
    ]
    assert blocked
    assert blocked[-1].payload["guardrail_kind"] == "operator-abort"
    assert blocked[-1].payload["reason"] == "global-esc"
