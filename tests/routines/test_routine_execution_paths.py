# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import copaw.routines.service as routine_service_module
from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    SessionMountRepository,
)
from copaw.evidence import EvidenceLedger
from copaw.routines import RoutineCreateRequest, RoutineReplayRequest, RoutineService
from copaw.state import SQLiteStateStore
from copaw.state.repositories import (
    SqliteExecutionRoutineRepository,
    SqliteRoutineRunRepository,
)


class _FakeKernelDispatcher:
    def __init__(self) -> None:
        self.tasks = []

    def submit(self, task):
        self.tasks.append(task)
        return SimpleNamespace(task_id=f"ktask:{len(self.tasks)}")


def _build_routine_service(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    routine_repo = SqliteExecutionRoutineRepository(store)
    run_repo = SqliteRoutineRunRepository(store)
    env_repo = EnvironmentRepository(store)
    session_repo = SessionMountRepository(store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
    )
    environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    environment_service.set_session_repository(session_repo)
    ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    service = RoutineService(
        routine_repository=routine_repo,
        routine_run_repository=run_repo,
        evidence_ledger=ledger,
        environment_service=environment_service,
        kernel_dispatcher=_FakeKernelDispatcher(),
        state_store=store,
    )
    return SimpleNamespace(
        service=service,
        ledger=ledger,
        environment_service=environment_service,
    )


@pytest.mark.asyncio
async def test_routine_service_desktop_document_prefers_cooperative_native_before_win32(
    tmp_path,
    monkeypatch,
) -> None:
    harness = _build_routine_service(tmp_path)
    monkeypatch.setattr(routine_service_module.sys, "platform", "win32")

    execution_calls: list[dict[str, object]] = []
    original_acquire = harness.environment_service.acquire_session_lease

    def _acquire_and_register(*args, **kwargs):
        lease = original_acquire(*args, **kwargs)
        harness.environment_service.register_document_bridge(
            session_mount_id=lease.id,
            bridge_ref="document-bridge:office",
            status="ready",
            supported_families=["documents"],
        )
        return lease

    def _native_document_executor(**kwargs):
        execution_calls.append(kwargs)
        path = Path(str(kwargs["contract"]["path"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        content = str(kwargs["contract"]["content"])
        path.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "message": "native write ok",
            "path": str(path),
            "reopened": True,
            "verified_content": content,
        }

    class _FailHost:
        def __init__(self) -> None:
            pass

        def write_document_file(self, **_kwargs):
            raise AssertionError("win32 fallback should not run when cooperative-native is ready")

    monkeypatch.setattr(
        harness.environment_service,
        "acquire_session_lease",
        _acquire_and_register,
    )
    monkeypatch.setattr(routine_service_module, "WindowsDesktopHost", _FailHost)
    harness.environment_service.register_document_bridge_executor(
        "document-bridge:office",
        _native_document_executor,
    )

    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="desktop-native-doc",
            name="Desktop Native Document",
            engine_kind="desktop",
            environment_kind="desktop",
            action_contract=[
                {
                    "action": "write_document_file",
                    "path": str(tmp_path / "draft.docx"),
                    "content": "hello native bridge",
                },
            ],
        ),
    )

    response = await harness.service.replay_routine(
        routine.id,
        RoutineReplayRequest(session_id="desktop-native-doc-session"),
    )

    evidence = harness.ledger.list_by_task(f"routine-run:{response.run.id}")
    assert response.run.status == "completed"
    assert execution_calls
    assert evidence[0].metadata["result"]["execution_path"]["selected_path"] == (
        "cooperative-native"
    )
    assert evidence[0].metadata["result"]["execution_path"]["fallback_applied"] is False


@pytest.mark.asyncio
async def test_routine_service_windows_app_uses_semantic_operator_before_ui_fallback(
    tmp_path,
    monkeypatch,
) -> None:
    harness = _build_routine_service(tmp_path)
    monkeypatch.setattr(routine_service_module.sys, "platform", "win32")

    execution_calls: list[dict[str, object]] = []
    original_acquire = harness.environment_service.acquire_session_lease

    def _acquire_and_register(*args, **kwargs):
        lease = original_acquire(*args, **kwargs)
        harness.environment_service.register_windows_app_adapter(
            session_mount_id=lease.id,
            adapter_refs=["app-adapter:excel"],
            app_identity="excel",
            control_channel="accessibility-tree",
            adapter_gap_or_blocker="excel-native-bridge-missing",
        )
        return lease

    def _semantic_executor(**kwargs):
        execution_calls.append(kwargs)
        return {
            "success": True,
            "message": "semantic focus ok",
            "window": {"title": "Orders.xlsx"},
        }

    class _FailHost:
        def __init__(self) -> None:
            pass

        def focus_window(self, **_kwargs):
            raise AssertionError("ui fallback should not run when semantic operator is available")

    monkeypatch.setattr(
        harness.environment_service,
        "acquire_session_lease",
        _acquire_and_register,
    )
    monkeypatch.setattr(routine_service_module, "WindowsDesktopHost", _FailHost)
    harness.environment_service.register_semantic_surface_executor(
        "accessibility-tree",
        _semantic_executor,
    )

    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="desktop-semantic-app",
            name="Desktop Semantic App",
            engine_kind="desktop",
            environment_kind="desktop",
            action_contract=[
                {
                    "action": "focus_window",
                    "selector": {"title": "Orders.xlsx"},
                },
            ],
        ),
    )

    response = await harness.service.replay_routine(
        routine.id,
        RoutineReplayRequest(session_id="desktop-semantic-app-session"),
    )

    evidence = harness.ledger.list_by_task(f"routine-run:{response.run.id}")
    assert response.run.status == "completed"
    assert execution_calls
    assert evidence[0].metadata["result"]["execution_path"]["selected_path"] == (
        "semantic-operator"
    )
    assert evidence[0].metadata["result"]["execution_path"]["current_gap_or_blocker"] == (
        "excel-native-bridge-missing"
    )


@pytest.mark.asyncio
async def test_routine_service_windows_app_falls_back_to_ui_host_as_last_resort(
    tmp_path,
    monkeypatch,
) -> None:
    harness = _build_routine_service(tmp_path)
    monkeypatch.setattr(routine_service_module.sys, "platform", "win32")

    host_calls: list[dict[str, object]] = []

    class _Host:
        def __init__(self) -> None:
            pass

        def focus_window(self, **kwargs):
            host_calls.append(kwargs)
            return {
                "success": True,
                "message": "focused by host",
                "window": {"title": "Orders.xlsx"},
            }

    monkeypatch.setattr(routine_service_module, "WindowsDesktopHost", _Host)

    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="desktop-ui-fallback",
            name="Desktop UI Fallback",
            engine_kind="desktop",
            environment_kind="desktop",
            action_contract=[
                {
                    "action": "focus_window",
                    "selector": {"title": "Orders.xlsx"},
                },
            ],
        ),
    )

    response = await harness.service.replay_routine(
        routine.id,
        RoutineReplayRequest(session_id="desktop-ui-fallback-session"),
    )

    evidence = harness.ledger.list_by_task(f"routine-run:{response.run.id}")
    assert response.run.status == "completed"
    assert host_calls
    assert evidence[0].metadata["result"]["execution_path"]["selected_path"] == "ui-fallback"
    assert evidence[0].metadata["result"]["execution_path"]["attempted_paths"] == [
        "cooperative-native",
        "semantic-operator",
        "ui-fallback",
    ]


@pytest.mark.asyncio
async def test_routine_service_desktop_environment_execution_failure_is_not_hidden_by_ui_fallback(
    tmp_path,
    monkeypatch,
) -> None:
    harness = _build_routine_service(tmp_path)
    monkeypatch.setattr(routine_service_module.sys, "platform", "win32")

    original_acquire = harness.environment_service.acquire_session_lease

    def _acquire_and_register(*args, **kwargs):
        lease = original_acquire(*args, **kwargs)
        harness.environment_service.register_document_bridge(
            session_mount_id=lease.id,
            bridge_ref="document-bridge:office",
            status="ready",
            supported_families=["documents"],
        )
        return lease

    def _failing_native_document_executor(**_kwargs):
        raise RuntimeError("native bridge exploded")

    class _FailHost:
        def __init__(self) -> None:
            pass

        def write_document_file(self, **_kwargs):
            raise AssertionError("ui fallback must not hide environment execution failure")

    monkeypatch.setattr(
        harness.environment_service,
        "acquire_session_lease",
        _acquire_and_register,
    )
    monkeypatch.setattr(routine_service_module, "WindowsDesktopHost", _FailHost)
    harness.environment_service.register_document_bridge_executor(
        "document-bridge:office",
        _failing_native_document_executor,
    )

    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="desktop-native-doc-failure",
            name="Desktop Native Document Failure",
            engine_kind="desktop",
            environment_kind="desktop",
            action_contract=[
                {
                    "action": "write_document_file",
                    "path": str(tmp_path / "draft.docx"),
                    "content": "hello native bridge",
                },
            ],
        ),
    )

    response = await harness.service.replay_routine(
        routine.id,
        RoutineReplayRequest(session_id="desktop-native-doc-failure-session"),
    )

    assert response.run.status == "failed"
    assert response.run.failure_class == "execution-error"
    assert response.run.output_summary == "native bridge exploded"
    assert response.run.metadata["execution_path"]["selected_path"] == "cooperative-native"
    assert response.run.metadata["execution_path"]["fallback_applied"] is False
