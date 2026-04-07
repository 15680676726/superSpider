# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import uuid
from types import SimpleNamespace

import pytest

import copaw.routines.service as routine_service_module
from copaw.evidence import EvidenceRecord
from copaw.capabilities.browser_runtime import BrowserRuntimeService
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


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


LIVE_ROUTINE_SMOKE_SKIP_REASON = (
    "Set COPAW_RUN_V6_LIVE_ROUTINE_SMOKE=1 to run V6 live routine smoke coverage "
    "(opt-in; not part of default regression coverage)."
)


def _build_live_routine_harness(tmp_path) -> SimpleNamespace:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    routine_repository = SqliteExecutionRoutineRepository(state_store)
    routine_run_repository = SqliteRoutineRunRepository(state_store)
    environment_repository = EnvironmentRepository(state_store)
    session_repository = SessionMountRepository(state_store)
    registry = EnvironmentRegistry(
        repository=environment_repository,
        session_repository=session_repository,
    )
    environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    environment_service.set_session_repository(session_repository)
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    browser_runtime = BrowserRuntimeService(state_store)
    service = RoutineService(
        routine_repository=routine_repository,
        routine_run_repository=routine_run_repository,
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
        browser_runtime_service=browser_runtime,
        state_store=state_store,
    )
    return SimpleNamespace(
        service=service,
        ledger=evidence_ledger,
        browser_runtime=browser_runtime,
    )


class _FakeBrowserRuntimeService:
    def __init__(self) -> None:
        self.start_calls = []
        self.stop_calls = []

    async def start_session(self, options):
        self.start_calls.append(options)
        return {"result": {"ok": True, "session_id": options.session_id}}

    async def stop_session(self, session_id: str):
        self.stop_calls.append(session_id)
        return {"ok": True}


def _build_stubbed_routine_harness(tmp_path) -> SimpleNamespace:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    routine_repository = SqliteExecutionRoutineRepository(state_store)
    routine_run_repository = SqliteRoutineRunRepository(state_store)
    environment_repository = EnvironmentRepository(state_store)
    session_repository = SessionMountRepository(state_store)
    registry = EnvironmentRegistry(
        repository=environment_repository,
        session_repository=session_repository,
    )
    environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    environment_service.set_session_repository(session_repository)
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    browser_runtime = _FakeBrowserRuntimeService()
    service = RoutineService(
        routine_repository=routine_repository,
        routine_run_repository=routine_run_repository,
        evidence_ledger=evidence_ledger,
        environment_service=environment_service,
        browser_runtime_service=browser_runtime,
        state_store=state_store,
    )
    return SimpleNamespace(
        service=service,
        ledger=evidence_ledger,
        browser_runtime=browser_runtime,
    )


def _browser_tool_response(payload: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(content=[{"text": json.dumps(payload)}])


def test_live_routine_smoke_skip_reasons_declare_opt_in_boundary() -> None:
    missing: list[str] = []
    for name, value in globals().items():
        if not name.startswith("test_live_") or not callable(value):
            continue
        marks = list(getattr(value, "pytestmark", []))
        skipif_marks = [mark for mark in marks if mark.name == "skipif"]
        if not skipif_marks:
            continue
        reason = str(skipif_marks[0].kwargs.get("reason", "")).lower()
        if "opt-in" not in reason or "not part of default regression coverage" not in reason:
            missing.append(name)
    assert not missing, f"Live routine smoke skip reasons must declare opt-in/default-regression boundary: {missing}"


@pytest.mark.asyncio
async def test_browser_routine_requires_post_action_verification(tmp_path, monkeypatch) -> None:
    harness = _build_stubbed_routine_harness(tmp_path)
    browser_calls: list[dict[str, object]] = []

    async def fake_browser_use(**kwargs):
        browser_calls.append(dict(kwargs))
        action = str(kwargs.get("action"))
        if action == "click":
            return _browser_tool_response({"ok": True, "message": "Clicked #submit"})
        if action == "evaluate":
            return _browser_tool_response(
                {"ok": True, "result": "https://example.com/login"},
            )
        return _browser_tool_response({"ok": True, "message": f"{action} ok"})

    monkeypatch.setattr(routine_service_module, "browser_use", fake_browser_use)
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="browser-post-action-verification",
            name="Browser Post Action Verification",
            action_contract=[
                {
                    "action": "click",
                    "page_id": "page-1",
                    "selector": "#submit",
                    "verification": {"url_contains": "/dashboard"},
                },
            ],
        ),
    )

    response = await harness.service.replay_routine(routine.id, RoutineReplayRequest())

    assert response.run.status == "failed"
    assert response.run.failure_class == "page-drift"
    assert any(call.get("action") == "evaluate" for call in browser_calls)
    records = harness.ledger.list_by_task(f"routine-run:{response.run.id}")
    assert len(records) == 1
    verification = dict(records[0].metadata.get("verification") or {})
    assert verification.get("verified") is False
    harness.ledger.close()


@pytest.mark.asyncio
async def test_browser_routine_open_requires_default_url_verification(tmp_path, monkeypatch) -> None:
    harness = _build_stubbed_routine_harness(tmp_path)
    browser_calls: list[dict[str, object]] = []

    async def fake_browser_use(**kwargs):
        browser_calls.append(dict(kwargs))
        action = str(kwargs.get("action"))
        if action == "open":
            return _browser_tool_response({"ok": True, "message": "Opened https://example.com/dashboard"})
        if action == "evaluate":
            return _browser_tool_response({"ok": True, "result": "https://example.com/login"})
        return _browser_tool_response({"ok": True, "message": f"{action} ok"})

    monkeypatch.setattr(routine_service_module, "browser_use", fake_browser_use)
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="browser-default-open-verification",
            name="Browser Default Open Verification",
            action_contract=[
                {
                    "action": "open",
                    "page_id": "page-1",
                    "url": "https://example.com/dashboard",
                },
            ],
        ),
    )

    response = await harness.service.replay_routine(routine.id, RoutineReplayRequest())

    assert response.run.status == "failed"
    assert response.run.failure_class == "page-drift"
    assert any(call.get("action") == "evaluate" for call in browser_calls)
    records = harness.ledger.list_by_task(f"routine-run:{response.run.id}")
    assert len(records) == 1
    verification = dict(records[0].metadata.get("verification") or {})
    assert verification.get("verified") is False
    assert any(check.get("kind") == "url" for check in list(verification.get("checks") or []))
    harness.ledger.close()


@pytest.mark.asyncio
async def test_browser_routine_open_accepts_canonical_root_url_equivalence(tmp_path, monkeypatch) -> None:
    harness = _build_stubbed_routine_harness(tmp_path)

    async def fake_browser_use(**kwargs):
        action = str(kwargs.get("action"))
        if action == "open":
            return _browser_tool_response({"ok": True, "message": "Opened https://example.com"})
        if action == "evaluate":
            return _browser_tool_response({"ok": True, "result": "https://example.com/"})
        return _browser_tool_response({"ok": True, "message": f"{action} ok"})

    monkeypatch.setattr(routine_service_module, "browser_use", fake_browser_use)
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="browser-default-open-canonical-url",
            name="Browser Default Open Canonical URL",
            action_contract=[
                {
                    "action": "open",
                    "page_id": "page-1",
                    "url": "https://example.com",
                },
            ],
        ),
    )

    response = await harness.service.replay_routine(routine.id, RoutineReplayRequest())

    assert response.run.status == "completed"
    records = harness.ledger.list_by_task(f"routine-run:{response.run.id}")
    assert len(records) == 1
    verification = dict(records[0].metadata.get("verification") or {})
    assert verification.get("verified") is True
    checks = list(verification.get("checks") or [])
    assert checks[0]["normalized_current_url"] == "https://example.com"
    assert checks[0]["normalized_expected_equals"] == "https://example.com"
    harness.ledger.close()


@pytest.mark.asyncio
async def test_browser_routine_type_requires_default_value_verification(tmp_path, monkeypatch) -> None:
    harness = _build_stubbed_routine_harness(tmp_path)
    browser_calls: list[dict[str, object]] = []

    async def fake_browser_use(**kwargs):
        browser_calls.append(dict(kwargs))
        action = str(kwargs.get("action"))
        if action == "type":
            return _browser_tool_response({"ok": True, "message": "Typed into #name"})
        if action == "evaluate":
            return _browser_tool_response({"ok": True, "result": "unexpected draft"})
        return _browser_tool_response({"ok": True, "message": f"{action} ok"})

    monkeypatch.setattr(routine_service_module, "browser_use", fake_browser_use)
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="browser-default-type-verification",
            name="Browser Default Type Verification",
            action_contract=[
                {
                    "action": "type",
                    "page_id": "page-1",
                    "selector": "#name",
                    "text": "Carrier Runtime",
                },
            ],
        ),
    )

    response = await harness.service.replay_routine(routine.id, RoutineReplayRequest())

    assert response.run.status == "failed"
    assert response.run.failure_class == "page-drift"
    assert any(call.get("action") == "evaluate" for call in browser_calls)
    records = harness.ledger.list_by_task(f"routine-run:{response.run.id}")
    assert len(records) == 1
    verification = dict(records[0].metadata.get("verification") or {})
    assert verification.get("verified") is False
    assert any(check.get("kind") == "element_value" for check in list(verification.get("checks") or []))
    harness.ledger.close()


@pytest.mark.asyncio
async def test_browser_routine_records_verification_chain_and_evidence_anchors(
    tmp_path,
    monkeypatch,
) -> None:
    harness = _build_stubbed_routine_harness(tmp_path)
    browser_calls: list[dict[str, object]] = []

    async def fake_browser_use(**kwargs):
        browser_calls.append(dict(kwargs))
        action = str(kwargs.get("action"))
        if action == "fill_form":
            return _browser_tool_response(
                {
                    "ok": True,
                    "message": "Filled 2 field(s)",
                    "verification": {
                        "verified": True,
                        "verified_fields": ["name", "notes"],
                    },
                },
            )
        if action == "file_upload":
            return _browser_tool_response(
                {
                    "ok": True,
                    "message": "Uploaded 1 file(s)",
                    "verification": {
                        "verified": True,
                        "expected_files": ["upload.txt"],
                        "after_files": ["upload.txt"],
                    },
                },
            )
        if action == "click":
            return _browser_tool_response({"ok": True, "message": "Clicked #submit"})
        if action == "wait_for":
            return _browser_tool_response({"ok": True, "message": "Found submitted confirmation"})
        if action == "evaluate":
            return _browser_tool_response({"ok": True, "result": "https://example.com/form/submitted"})
        return _browser_tool_response({"ok": True, "message": f"{action} ok"})

    monkeypatch.setattr(routine_service_module, "browser_use", fake_browser_use)
    upload_path = tmp_path / "upload.txt"
    upload_path.write_text("routine upload", encoding="utf-8")
    screenshot_path = tmp_path / "browser-chain.png"
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="browser-verification-chain",
            name="Browser Verification Chain",
            action_contract=[
                {
                    "action": "fill_form",
                    "page_id": "page-1",
                    "fields": [
                        {"ref": "name", "value": "Carrier Runtime"},
                        {"ref": "notes", "value": "observe act verify"},
                    ],
                },
                {
                    "action": "click",
                    "page_id": "page-1",
                    "selector": "#submit",
                    "verification": {
                        "url_contains": "/submitted",
                        "text_present": "Submitted",
                    },
                },
                {
                    "action": "file_upload",
                    "page_id": "page-1",
                    "paths": [str(upload_path)],
                },
                {
                    "action": "screenshot",
                    "page_id": "page-1",
                    "path": str(screenshot_path),
                    "verification": {"file_exists": str(screenshot_path)},
                },
            ],
            evidence_expectations=["fill_form", "click", "file_upload", "screenshot"],
        ),
    )

    screenshot_path.write_text("fake screenshot", encoding="utf-8")
    response = await harness.service.replay_routine(routine.id, RoutineReplayRequest())

    assert response.run.status == "completed"
    verification_summary = dict(response.run.metadata.get("verification_summary") or {})
    assert verification_summary.get("chain_status") == "verified"
    assert verification_summary.get("verified_steps") == 4
    assert verification_summary.get("total_steps") == 4
    assert verification_summary.get("observed_steps") == 4
    anchors = list(verification_summary.get("evidence_anchors") or [])
    assert len(anchors) == 4
    assert [anchor.get("action") for anchor in anchors] == [
        "fill_form",
        "click",
        "file_upload",
        "screenshot",
    ]
    assert all(anchor.get("evidence_id") for anchor in anchors)
    assert anchors[-1].get("artifact_path") == str(screenshot_path)
    assert response.diagnosis.verification_status == "verified"
    assert response.diagnosis.verification_summary.get("total_steps") == 4
    assert any(call.get("action") == "evaluate" for call in browser_calls)
    records = harness.ledger.list_by_task(f"routine-run:{response.run.id}")
    assert len(records) == 4
    assert records[1].metadata["verification"]["verified"] is True
    harness.ledger.close()


@pytest.mark.asyncio
async def test_desktop_routine_supports_document_and_focus_actions(tmp_path, monkeypatch) -> None:
    harness = _build_stubbed_routine_harness(tmp_path)

    class FakeWindowsDesktopHost:
        def write_document_file(self, *, path: str, content: str, encoding: str = "utf-8", create_parent_dirs: bool = True):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding=encoding) as handle:
                handle.write(content)
            return {
                "success": True,
                "path": path,
                "verified_content": content,
                "encoding": encoding,
                "created": True,
                "reopened": True,
                "create_parent_dirs": create_parent_dirs,
            }

        def edit_document_file(self, *, path: str, find_text: str, replace_text: str, encoding: str = "utf-8"):
            with open(path, "r", encoding=encoding) as handle:
                current = handle.read()
            updated = current.replace(find_text, replace_text)
            with open(path, "w", encoding=encoding) as handle:
                handle.write(updated)
            return {
                "success": True,
                "path": path,
                "verified_content": updated,
                "encoding": encoding,
                "replacements": 1,
                "reopened": True,
            }

        def verify_window_focus(self, *, selector):
            return {
                "success": True,
                "is_foreground": True,
                "window": {
                    "title": getattr(selector, "title", None) or "Routine Focus Window",
                    "handle": getattr(selector, "handle", None) or 1001,
                },
                "foreground_window": {
                    "title": getattr(selector, "title", None) or "Routine Focus Window",
                    "handle": getattr(selector, "handle", None) or 1001,
                },
            }

    monkeypatch.setattr(routine_service_module.sys, "platform", "win32")
    monkeypatch.setattr(routine_service_module, "WindowsDesktopHost", FakeWindowsDesktopHost)
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="desktop-document-focus-support",
            name="Desktop Document Focus Support",
            engine_kind="desktop",
            environment_kind="desktop",
            action_contract=[
                {
                    "action": "write_document_file",
                    "path": str(tmp_path / "routine-smoke.txt"),
                    "content": "draft v1",
                },
                {
                    "action": "edit_document_file",
                    "path": str(tmp_path / "routine-smoke.txt"),
                    "find_text": "draft v1",
                    "replace_text": "draft v2",
                },
                {
                    "action": "verify_window_focus",
                    "selector": {"title": "Routine Focus Window"},
                },
            ],
        ),
    )

    response = await harness.service.replay_routine(routine.id, RoutineReplayRequest())

    assert response.run.status == "completed"
    assert response.run.deterministic_result == "desktop-replay-complete"
    records = harness.ledger.list_by_task(f"routine-run:{response.run.id}")
    assert [record.metadata.get("action") for record in records] == [
        "write_document_file",
        "edit_document_file",
        "verify_window_focus",
    ]
    assert records[-1].metadata["result"]["is_foreground"] is True
    harness.ledger.close()


@pytest.mark.asyncio
async def test_desktop_routine_write_document_requires_reread_verification(tmp_path, monkeypatch) -> None:
    harness = _build_stubbed_routine_harness(tmp_path)

    class FakeWindowsDesktopHost:
        def write_document_file(
            self,
            *,
            path: str,
            content: str,
            encoding: str = "utf-8",
            create_parent_dirs: bool = True,
        ):
            return {
                "success": True,
                "path": path,
                "verified_content": "mismatched content",
                "encoding": encoding,
                "created": True,
                "reopened": False,
                "create_parent_dirs": create_parent_dirs,
            }

    monkeypatch.setattr(routine_service_module.sys, "platform", "win32")
    monkeypatch.setattr(routine_service_module, "WindowsDesktopHost", FakeWindowsDesktopHost)
    target_path = tmp_path / "routine-smoke.txt"
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="desktop-document-reread-verification",
            name="Desktop Document Reread Verification",
            engine_kind="desktop",
            environment_kind="desktop",
            action_contract=[
                {
                    "action": "write_document_file",
                    "path": str(target_path),
                    "content": "draft v1",
                },
            ],
        ),
    )

    response = await harness.service.replay_routine(routine.id, RoutineReplayRequest())

    assert response.run.status == "failed"
    assert response.run.failure_class == "execution-error"
    records = harness.ledger.list_by_task(f"routine-run:{response.run.id}")
    assert records
    verifications = [dict(record.metadata.get("verification") or {}) for record in records]
    assert any(verification.get("verified") is False for verification in verifications)
    assert any(
        check.get("kind") == "document_reread"
        for verification in verifications
        for check in list(verification.get("checks") or [])
    )
    harness.ledger.close()


@pytest.mark.asyncio
async def test_desktop_routine_blocks_on_modal_interruption(tmp_path, monkeypatch) -> None:
    harness = _build_stubbed_routine_harness(tmp_path)

    class FakeWindowsDesktopHost:
        def type_text(self, *, text: str, selector=None, focus_target: bool = True):
            raise routine_service_module.DesktopAutomationError(
                "type_text lost focus after input; possible modal interruption or focus theft"
            )

    monkeypatch.setattr(routine_service_module.sys, "platform", "win32")
    monkeypatch.setattr(routine_service_module, "WindowsDesktopHost", FakeWindowsDesktopHost)
    routine = harness.service.create_routine(
        RoutineCreateRequest(
            routine_key="desktop-modal-interruption",
            name="Desktop Modal Interruption",
            engine_kind="desktop",
            environment_kind="desktop",
            action_contract=[
                {
                    "action": "type_text",
                    "selector": {"title": "Routine Focus Window"},
                    "text": "blocked",
                },
            ],
        ),
    )

    response = await harness.service.replay_routine(routine.id, RoutineReplayRequest())

    assert response.run.status == "blocked"
    assert response.run.failure_class == "modal-interruption"
    assert response.run.fallback_mode == "pause-for-confirm"
    verification_summary = dict(response.run.metadata.get("verification_summary") or {})
    assert verification_summary.get("chain_status") == "failed"
    assert verification_summary.get("failure_class") == "modal-interruption"
    assert "observe -> act -> verify" in " ".join(response.diagnosis.recommended_actions)
    harness.ledger.close()


def _run_live_python_script(tmp_path, script: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _run_live_browser_case(
    tmp_path,
    *,
    routine_key: str,
    name: str,
    summary: str,
    session_id: str,
    action_contract: list[dict[str, object]],
    evidence_expectations: list[str],
    replay_count: int = 1,
) -> dict[str, object]:
    script = textwrap.dedent(
        f"""
        import asyncio
        import json
        from pathlib import Path

        from copaw.capabilities.browser_runtime import BrowserRuntimeService
        from copaw.environments import EnvironmentRegistry, EnvironmentRepository, EnvironmentService, SessionMountRepository
        from copaw.evidence import EvidenceLedger
        from copaw.routines import RoutineCreateRequest, RoutineReplayRequest, RoutineService
        from copaw.state import SQLiteStateStore
        from copaw.state.repositories import SqliteExecutionRoutineRepository, SqliteRoutineRunRepository

        ACTION_CONTRACT = json.loads({json.dumps(json.dumps(action_contract))})
        EVIDENCE_EXPECTATIONS = json.loads({json.dumps(json.dumps(evidence_expectations))})
        PAGE_IDS = [
            str(item.get("page_id"))
            for item in ACTION_CONTRACT
            if isinstance(item, dict) and str(item.get("page_id") or "").strip()
        ]

        async def main() -> None:
            root = Path({json.dumps(str(tmp_path))})
            state_store = SQLiteStateStore(root / "state.sqlite3")
            routine_repository = SqliteExecutionRoutineRepository(state_store)
            routine_run_repository = SqliteRoutineRunRepository(state_store)
            environment_repository = EnvironmentRepository(state_store)
            session_repository = SessionMountRepository(state_store)
            registry = EnvironmentRegistry(
                repository=environment_repository,
                session_repository=session_repository,
            )
            environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
            environment_service.set_session_repository(session_repository)
            evidence_ledger = EvidenceLedger(database_path=root / "evidence.sqlite3")
            browser_runtime = BrowserRuntimeService(state_store)
            session_id = {json.dumps(session_id)}
            screenshot_paths = [
                str(item.get("path"))
                for item in ACTION_CONTRACT
                if isinstance(item, dict)
                and str(item.get("action") or "").strip().lower() == "screenshot"
                and str(item.get("path") or "").strip()
            ]
            payload = {{"routine_id": None, "runs": [], "stop_payload": None}}
            try:
                service = RoutineService(
                    routine_repository=routine_repository,
                    routine_run_repository=routine_run_repository,
                    evidence_ledger=evidence_ledger,
                    environment_service=environment_service,
                    browser_runtime_service=browser_runtime,
                    state_store=state_store,
                )
                routine = service.create_routine(
                    RoutineCreateRequest(
                        routine_key={json.dumps(routine_key)},
                        name={json.dumps(name)},
                        summary={json.dumps(summary)},
                        session_requirements={{"headed": False}},
                        action_contract=ACTION_CONTRACT,
                        evidence_expectations=EVIDENCE_EXPECTATIONS,
                    ),
                )
                payload["routine_id"] = routine.id
                runs = []
                for attempt in range({replay_count}):
                    response = await service.replay_routine(
                        routine.id,
                        RoutineReplayRequest(
                            session_id=session_id,
                            request_context={{
                                "channel": "console",
                                "user_id": "live-routine-smoke",
                                "session_id": f"runtime-center-live-smoke-{{attempt + 1}}",
                                "query_preview": f"Run live browser routine smoke attempt {{attempt + 1}}",
                            }},
                        ),
                    )
                    records = evidence_ledger.list_by_task(f"routine-run:{{response.run.id}}")
                    session_lease = environment_service.get_session(response.run.lease_ref)
                    browser_session_lease = environment_service.get_resource_slot_lease(
                        scope_type="browser-session",
                        scope_value=session_id,
                    )
                    cleanup = {{
                        "session_lease_status": (
                            getattr(session_lease, "lease_status", None)
                            if session_lease is not None
                            else None
                        ),
                        "lease_release_reason": (
                            dict(getattr(session_lease, "metadata", {{}})).get("lease_release_reason")
                            if session_lease is not None
                            else None
                        ),
                        "resource_locks": {{
                            "browser_session": bool(
                                browser_session_lease is not None
                                and getattr(browser_session_lease, "lease_status", None) == "leased"
                            ),
                            "page_tabs": {{
                                page_id: bool(
                                    (lease := environment_service.get_resource_slot_lease(
                                        scope_type="page-tab",
                                        scope_value=page_id,
                                    )) is not None
                                    and getattr(lease, "lease_status", None) == "leased"
                                )
                                for page_id in PAGE_IDS
                            }},
                            "artifact_targets": {{
                                path: bool(
                                    (lease := environment_service.get_resource_slot_lease(
                                        scope_type="artifact-target",
                                        scope_value=path,
                                    )) is not None
                                    and getattr(lease, "lease_status", None) == "leased"
                                )
                                for path in screenshot_paths
                            }},
                        }},
                    }}
                    runs.append(
                        {{
                            "run_id": response.run.id,
                            "status": response.run.status,
                            "deterministic_result": response.run.deterministic_result,
                            "failure_class": response.run.failure_class,
                            "session_id": response.run.session_id,
                            "start_status": dict(response.run.metadata.get("start_payload") or {{}}).get("status"),
                            "start_payload": dict(response.run.metadata.get("start_payload") or {{}}),
                            "verification_summary": dict(response.run.metadata.get("verification_summary") or {{}}),
                            "evidence_ids": list(response.run.evidence_ids or []),
                            "actions": [record.metadata.get("action") for record in records],
                            "summaries": [record.result_summary for record in records],
                            "screenshot_exists": {{
                                path: Path(path).exists()
                                for path in screenshot_paths
                            }},
                            "cleanup": cleanup,
                        }}
                    )
                payload["runs"] = runs
            finally:
                payload["stop_payload"] = await browser_runtime.stop_session(session_id)
                evidence_ledger.close()
            print(json.dumps(payload))

        asyncio.run(main())
        """,
    )
    return _run_live_python_script(tmp_path, script)


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_V6_LIVE_ROUTINE_SMOKE"),
    reason=LIVE_ROUTINE_SMOKE_SKIP_REASON,
)
def test_live_browser_routine_fill_form_with_selectors_smoke(tmp_path) -> None:
    screenshot_path = tmp_path / "browser-routine-fill-form-selectors.png"
    html_path = tmp_path / "routine-fill-form-selectors.html"
    html_path.write_text(
        textwrap.dedent(
            """
            <!doctype html>
            <html lang="en">
              <head>
                <meta charset="utf-8" />
                <title>Fill Form Selector Smoke</title>
              </head>
              <body>
                <label for="name">Name</label>
                <input id="name" name="name" type="text" />
                <label for="notes">Notes</label>
                <textarea id="notes" name="notes"></textarea>
                <p id="status">Ready</p>
              </body>
            </html>
            """,
        ),
        encoding="utf-8",
    )
    payload = _run_live_browser_case(
        tmp_path,
        routine_key="live-browser-fill-form-selectors-smoke",
        name="Live Browser Fill Form Selectors Smoke",
        summary="Open a local page, fill fields by selector without snapshot refs, and capture a screenshot.",
        session_id="live-browser-fill-form-selectors",
        action_contract=[
            {"action": "open", "page_id": "page-1", "url": html_path.resolve().as_uri()},
            {
                "action": "fill_form",
                "page_id": "page-1",
                "fields": [
                    {"selector": "#name", "value": "Carrier Runtime"},
                    {"selector": "#notes", "value": "selector-fill-ok"},
                ],
            },
            {"action": "screenshot", "page_id": "page-1", "path": str(screenshot_path)},
        ],
        evidence_expectations=["open", "fill_form", "screenshot"],
    )
    run = payload["runs"][0]
    assert run["status"] == "completed"
    assert run["deterministic_result"] == "replay-complete"
    assert all(run["screenshot_exists"].values())
    assert run["actions"] == ["open", "fill_form", "screenshot"]
    verification_summary = dict(run["verification_summary"] or {})
    assert verification_summary.get("chain_status") == "verified"
    assert verification_summary.get("verified_steps") == 3


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_V6_LIVE_ROUTINE_SMOKE"),
    reason=LIVE_ROUTINE_SMOKE_SKIP_REASON,
)
def test_live_browser_routine_replay_round_trip(tmp_path) -> None:
    screenshot_path = tmp_path / "browser-routine-smoke.png"
    payload = _run_live_browser_case(
        tmp_path,
        routine_key="live-browser-routine-smoke",
        name="Live Browser Routine Smoke",
        summary="Open example.com and capture a screenshot through the V6 routine path.",
        session_id="live-browser-routine-smoke",
        action_contract=[
            {"action": "open", "page_id": "page-1", "url": "https://example.com"},
            {"action": "screenshot", "page_id": "page-1", "path": str(screenshot_path)},
        ],
        evidence_expectations=["open", "screenshot"],
    )
    run = payload["runs"][0]
    assert run["status"] == "completed"
    assert run["deterministic_result"] == "replay-complete"
    assert all(run["screenshot_exists"].values())
    assert run["actions"] == ["open", "screenshot"]
    assert run["summaries"][0] == "Opened https://example.com"
    assert str(run["summaries"][1]).startswith("Screenshot saved to ")


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_V6_LIVE_ROUTINE_SMOKE"),
    reason=LIVE_ROUTINE_SMOKE_SKIP_REASON,
)
def test_live_browser_routine_replay_clicks_example_anchor(tmp_path) -> None:
    screenshot_path = tmp_path / "browser-routine-click.png"
    payload = _run_live_browser_case(
        tmp_path,
        routine_key="live-browser-routine-click-smoke",
        name="Live Browser Routine Click Smoke",
        summary="Open example.com, click the only anchor, and capture a screenshot.",
        session_id="live-browser-routine-click",
        action_contract=[
            {"action": "open", "page_id": "page-1", "url": "https://example.com"},
            {"action": "click", "page_id": "page-1", "selector": "a", "wait": 1000},
            {"action": "screenshot", "page_id": "page-1", "path": str(screenshot_path)},
        ],
        evidence_expectations=["open", "click", "screenshot"],
    )
    run = payload["runs"][0]
    assert run["status"] == "completed"
    assert run["deterministic_result"] == "replay-complete"
    assert all(run["screenshot_exists"].values())
    assert run["actions"] == ["open", "click", "screenshot"]
    assert len(run["evidence_ids"]) == 3


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_V6_LIVE_ROUTINE_SMOKE"),
    reason=LIVE_ROUTINE_SMOKE_SKIP_REASON,
)
def test_live_browser_routine_replay_navigates_to_iana_reserved(tmp_path) -> None:
    screenshot_path = tmp_path / "browser-routine-iana.png"
    payload = _run_live_browser_case(
        tmp_path,
        routine_key="live-browser-routine-iana-smoke",
        name="Live Browser Routine IANA Smoke",
        summary="Open example.com, navigate to IANA reserved domains, and capture a screenshot.",
        session_id="live-browser-routine-iana",
        action_contract=[
            {"action": "open", "page_id": "page-1", "url": "https://example.com"},
            {
                "action": "navigate",
                "page_id": "page-1",
                "url": "https://www.iana.org/domains/reserved",
            },
            {"action": "screenshot", "page_id": "page-1", "path": str(screenshot_path)},
        ],
        evidence_expectations=["open", "navigate", "screenshot"],
    )
    run = payload["runs"][0]
    assert run["status"] == "completed"
    assert run["deterministic_result"] == "replay-complete"
    assert all(run["screenshot_exists"].values())
    assert run["actions"] == ["open", "navigate", "screenshot"]
    assert len(run["summaries"]) == 3


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_V6_LIVE_ROUTINE_SMOKE"),
    reason=LIVE_ROUTINE_SMOKE_SKIP_REASON,
)
def test_live_browser_routine_replay_reuses_same_session(tmp_path) -> None:
    screenshot_path = tmp_path / "browser-routine-reuse.png"
    payload = _run_live_browser_case(
        tmp_path,
        routine_key="live-browser-routine-reuse-smoke",
        name="Live Browser Routine Reuse Smoke",
        summary="Replay the same browser routine twice with one persisted session.",
        session_id="live-browser-routine-reuse",
        action_contract=[
            {"action": "open", "page_id": "page-1", "url": "https://example.com"},
            {"action": "navigate", "page_id": "page-1", "url": "https://example.net"},
            {"action": "screenshot", "page_id": "page-1", "path": str(screenshot_path)},
        ],
        evidence_expectations=["open", "navigate", "screenshot"],
        replay_count=2,
    )
    assert len(payload["runs"]) == 2
    first_run, second_run = payload["runs"]
    assert first_run["status"] == "completed"
    assert second_run["status"] == "completed"
    assert first_run["actions"] == ["open", "navigate", "screenshot"]
    assert second_run["actions"] == ["open", "navigate", "screenshot"]
    assert first_run["run_id"] != second_run["run_id"]
    assert set(first_run["evidence_ids"]).isdisjoint(set(second_run["evidence_ids"]))
    assert first_run["session_id"] == second_run["session_id"] == "live-browser-routine-reuse"
    assert first_run["start_status"] == "started"
    assert second_run["start_status"] == "attached"
    assert all(second_run["screenshot_exists"].values())


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_V6_LIVE_ROUTINE_SMOKE"),
    reason=LIVE_ROUTINE_SMOKE_SKIP_REASON,
)
def test_live_browser_routine_reconnect_cleanup_smoke(tmp_path) -> None:
    screenshot_path = tmp_path / "browser-routine-reconnect-cleanup.png"
    payload = _run_live_browser_case(
        tmp_path,
        routine_key="live-browser-routine-reconnect-cleanup-smoke",
        name="Live Browser Routine Reconnect Cleanup Smoke",
        summary="Replay the same browser routine twice and verify reconnect plus cleanup on the current host.",
        session_id="live-browser-routine-reconnect-cleanup",
        action_contract=[
            {"action": "open", "page_id": "page-1", "url": "https://example.com"},
            {"action": "screenshot", "page_id": "page-1", "path": str(screenshot_path)},
        ],
        evidence_expectations=["open", "screenshot"],
        replay_count=2,
    )
    first_run, second_run = payload["runs"]
    if (
        first_run["status"] == "failed"
        and not first_run["actions"]
        and first_run["start_status"] is None
    ):
        start_payload = dict(first_run.get("start_payload") or {})
        runtime_error = start_payload.get("error") or payload["stop_payload"].get("result", {}).get("message")
        pytest.skip(f"Browser live runtime is unavailable on this host: {runtime_error}")
    assert first_run["start_status"] == "started"
    assert second_run["start_status"] == "attached"
    assert first_run["cleanup"]["session_lease_status"] == "released"
    assert second_run["cleanup"]["session_lease_status"] == "released"
    assert first_run["cleanup"]["lease_release_reason"] == "routine browser replay completed"
    assert second_run["cleanup"]["lease_release_reason"] == "routine browser replay completed"
    assert not first_run["cleanup"]["resource_locks"]["browser_session"]
    assert not second_run["cleanup"]["resource_locks"]["browser_session"]
    assert not any(first_run["cleanup"]["resource_locks"]["page_tabs"].values())
    assert not any(second_run["cleanup"]["resource_locks"]["page_tabs"].values())
    assert not any(first_run["cleanup"]["resource_locks"]["artifact_targets"].values())
    assert not any(second_run["cleanup"]["resource_locks"]["artifact_targets"].values())
    assert payload["stop_payload"]["ok"] is True


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_V6_LIVE_ROUTINE_SMOKE"),
    reason=LIVE_ROUTINE_SMOKE_SKIP_REASON,
)
def test_live_desktop_routine_cross_surface_contention_smoke(tmp_path) -> None:
    script = textwrap.dedent(
        f"""
        import asyncio
        import json
        import sys
        from pathlib import Path

        from copaw.environments import EnvironmentRegistry, EnvironmentRepository, EnvironmentService, SessionMountRepository
        from copaw.evidence import EvidenceLedger
        from copaw.routines import RoutineCreateRequest, RoutineReplayRequest, RoutineService
        from copaw.state import SQLiteStateStore
        from copaw.state.repositories import SqliteExecutionRoutineRepository, SqliteRoutineRunRepository
        import copaw.routines.service as routine_service_module

        async def main() -> None:
            root = Path({json.dumps(str(tmp_path))})
            state_store = SQLiteStateStore(root / "state.sqlite3")
            routine_repository = SqliteExecutionRoutineRepository(state_store)
            routine_run_repository = SqliteRoutineRunRepository(state_store)
            environment_repository = EnvironmentRepository(state_store)
            session_repository = SessionMountRepository(state_store)
            registry = EnvironmentRegistry(
                repository=environment_repository,
                session_repository=session_repository,
            )
            environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
            environment_service.set_session_repository(session_repository)
            evidence_ledger = EvidenceLedger(database_path=root / "evidence.sqlite3")
            if sys.platform != "win32":
                raise SystemExit("Desktop live routine smoke requires a Windows host.")
            foreground = routine_service_module.WindowsDesktopHost().get_foreground_window()
            if not foreground.get("success") or not foreground.get("title"):
                raise SystemExit("Desktop live routine smoke requires a resolvable foreground window.")
            shared_scope = str(foreground["title"])
            held_lease = environment_service.acquire_resource_slot_lease(
                scope_type="page-tab",
                scope_value=shared_scope,
                owner="browser-owner",
            )
            try:
                service = RoutineService(
                    routine_repository=routine_repository,
                    routine_run_repository=routine_run_repository,
                    evidence_ledger=evidence_ledger,
                    environment_service=environment_service,
                    state_store=state_store,
                )
                routine = service.create_routine(
                    RoutineCreateRequest(
                        routine_key="live-desktop-surface-contention-smoke",
                        name="Live Desktop Surface Contention Smoke",
                        summary="Verify desktop routines fail closed when a browser-side page-tab lock already owns the same surface.",
                        engine_kind="desktop",
                        environment_kind="desktop",
                        action_contract=[
                            {{
                                "action": "verify_window_focus",
                                "selector": {{"title": shared_scope}},
                            }},
                        ],
                    ),
                )
                response = await service.replay_routine(
                    routine.id,
                    RoutineReplayRequest(session_id="live-desktop-contention-smoke"),
                )
                session = environment_service.get_session("session:desktop:live-desktop-contention-smoke")
                print(json.dumps({{
                    "status": response.run.status,
                    "failure_class": response.run.failure_class,
                    "lock_health": response.diagnosis.lock_health,
                    "resource_conflicts": list(response.run.metadata.get("resource_conflicts") or []),
                    "session_lease_status": getattr(session, "lease_status", None) if session is not None else None,
                    "held_lock_status": getattr(held_lease, "lease_status", None),
                }}))
            finally:
                environment_service.release_resource_slot_lease(
                    lease_id=held_lease.id,
                    lease_token=held_lease.lease_token,
                    reason="live desktop smoke cleanup",
                )
                evidence_ledger.close()

        asyncio.run(main())
        """,
    )
    payload = _run_live_python_script(tmp_path, script)
    assert payload["status"] == "failed"
    assert payload["failure_class"] == "lock-conflict"
    assert payload["lock_health"] == "contended"
    conflicts = list(payload["resource_conflicts"] or [])
    assert conflicts
    assert conflicts[0]["scope_type"] == "page-tab"
    assert payload["session_lease_status"] == "released"
    assert payload["held_lock_status"] == "leased"


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_V6_LIVE_ROUTINE_SMOKE"),
    reason=LIVE_ROUTINE_SMOKE_SKIP_REASON,
)
def test_live_browser_routine_verification_chain_with_upload_and_evidence_anchors(
    tmp_path,
) -> None:
    upload_path = tmp_path / "upload.txt"
    upload_path.write_text("upload payload for live routine smoke", encoding="utf-8")
    screenshot_path = tmp_path / "browser-routine-verification-chain.png"
    html_path = tmp_path / "routine-acceptance.html"
    html_path.write_text(
        textwrap.dedent(
            f"""
            <!doctype html>
            <html lang="en">
              <head>
                <meta charset="utf-8" />
                <title>Routine Acceptance</title>
              </head>
                <body>
                  <h1>Routine Acceptance Browser</h1>
                  <form id="acceptance-form">
                    <label for="name">Name</label>
                    <input id="name" name="name" type="text" />
                    <a
                      id="submit"
                      href="#submitted-anchor"
                    >
                      Submit
                    </a>
                  </form>
                  <label for="upload">Upload file</label>
                  <input
                    id="upload"
                    name="upload"
                    type="file"
                    onchange="document.getElementById('upload-status').textContent = this.files && this.files[0] ? 'Uploaded: ' + this.files[0].name : 'Waiting for upload';"
                  />
                  <p id="submitted-status">Waiting for submit</p>
                  <p id="submitted-anchor">Submit anchor target</p>
                  <p id="upload-status">Waiting for upload</p>
                </body>
            </html>
            """,
        ),
        encoding="utf-8",
    )
    payload = _run_live_browser_case(
        tmp_path,
        routine_key="live-browser-verification-chain-smoke",
        name="Live Browser Verification Chain Smoke",
        summary="Use a local page to exercise observe -> act -> verify with upload and screenshot evidence anchors.",
        session_id="live-browser-verification-chain",
        action_contract=[
            {"action": "open", "page_id": "page-1", "url": html_path.resolve().as_uri()},
            {"action": "type", "page_id": "page-1", "selector": "#name", "text": "Carrier Runtime"},
            {
                "action": "click",
                "page_id": "page-1",
                "selector": "#submit",
                "wait": 500,
                "verification": {"url_contains": "#submitted-anchor"},
            },
            {"action": "click", "page_id": "page-1", "selector": "#upload", "wait": 500},
            {
                "action": "file_upload",
                "page_id": "page-1",
                "paths": [str(upload_path)],
                "verification": {"text_present": "Uploaded: upload.txt"},
            },
            {
                "action": "screenshot",
                "page_id": "page-1",
                "path": str(screenshot_path),
                "verification": {"file_exists": str(screenshot_path)},
            },
        ],
        evidence_expectations=["open", "type", "click", "click", "file_upload", "screenshot"],
    )
    run = payload["runs"][0]
    assert run["status"] == "completed"
    assert run["deterministic_result"] == "replay-complete"
    assert run["actions"] == ["open", "type", "click", "click", "file_upload", "screenshot"]
    assert all(run["screenshot_exists"].values())
    verification_summary = dict(run["verification_summary"] or {})
    assert verification_summary.get("chain_status") == "verified"
    assert verification_summary.get("verified_steps") == 6
    assert verification_summary.get("observed_steps") == 6
    anchors = list(verification_summary.get("evidence_anchors") or [])
    assert len(anchors) == 6
    assert anchors[-1].get("artifact_path") == str(screenshot_path)
    assert anchors[-1].get("action") == "screenshot"


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_V6_LIVE_ROUTINE_SMOKE"),
    reason=LIVE_ROUTINE_SMOKE_SKIP_REASON,
)
def test_live_browser_routine_authenticated_continuation_cross_tab_save_reopen_smoke(
    tmp_path,
) -> None:
    screenshot_path = tmp_path / "browser-routine-authenticated-continuation.png"
    login_path = tmp_path / "routine-auth-login.html"
    workspace_path = tmp_path / "routine-auth-workspace.html"
    workspace_path.write_text(
        textwrap.dedent(
            """
            <!doctype html>
            <html lang="en">
              <head>
                <meta charset="utf-8" />
                <title>Routine Workspace</title>
                <script>
                  function hydrate() {
                    const authed = window.localStorage.getItem("routine-auth") === "ok";
                    const authStatus = document.getElementById("auth-status");
                    authStatus.textContent = authed
                      ? "Authenticated continuation ready"
                      : "Authentication missing";
                    const saved = window.localStorage.getItem("routine-draft") || "";
                    const note = document.getElementById("note");
                    note.value = saved;
                    const draftStatus = document.getElementById("draft-status");
                    draftStatus.textContent = saved
                      ? "Draft loaded: " + saved
                      : "Draft empty";
                  }
                  function saveDraft() {
                    const note = document.getElementById("note").value;
                    window.localStorage.setItem("routine-draft", note);
                    document.getElementById("draft-status").textContent = "Draft saved: " + note;
                  }
                  function markDownload() {
                    document.getElementById("download-status").textContent = "Download prepared: carrier-export.txt";
                  }
                  window.addEventListener("DOMContentLoaded", hydrate);
                </script>
              </head>
              <body>
                <h1>Routine Workspace</h1>
                <p id="auth-status">Loading auth state</p>
                <label for="note">Note</label>
                <textarea id="note" name="note"></textarea>
                <button id="save-note" type="button" onclick="saveDraft()">Save note</button>
                <a
                  id="download-link"
                  href="data:text/plain;charset=utf-8,carrier export"
                  download="carrier-export.txt"
                  onclick="markDownload()"
                >
                  Download export
                </a>
                <p id="draft-status">Draft empty</p>
                <p id="download-status">Download idle</p>
              </body>
            </html>
            """,
        ),
        encoding="utf-8",
    )
    login_path.write_text(
        textwrap.dedent(
            f"""
            <!doctype html>
            <html lang="en">
              <head>
                <meta charset="utf-8" />
                <title>Routine Login</title>
                <script>
                  function setAuthenticated() {{
                    window.localStorage.setItem("routine-auth", "ok");
                    document.getElementById("auth-state").textContent = "Authenticated";
                  }}
                </script>
              </head>
              <body>
                <h1>Routine Login</h1>
                <button id="login" type="button" onclick="setAuthenticated()">Authenticate</button>
                <a id="open-workspace" href="{workspace_path.resolve().as_uri()}" target="_blank">Open workspace</a>
                <p id="auth-state">Pending authentication</p>
              </body>
            </html>
            """,
        ),
        encoding="utf-8",
    )
    payload = _run_live_browser_case(
        tmp_path,
        routine_key="live-browser-authenticated-continuation-smoke",
        name="Live Browser Authenticated Continuation Smoke",
        summary="Exercise authenticated continuation, cross-tab reuse, save-and-reopen, and download initiation on a local HTML acceptance chain.",
        session_id="live-browser-authenticated-continuation",
        action_contract=[
            {"action": "open", "page_id": "page-1", "url": login_path.resolve().as_uri()},
            {
                "action": "click",
                "page_id": "page-1",
                "selector": "#login",
                "wait": 300,
                "verification": {"text_present": "Authenticated"},
            },
            {
                "action": "click",
                "page_id": "page-1",
                "selector": "#open-workspace",
                "wait": 800,
                "verification": {"tab_count": 2},
            },
            {
                "action": "tabs",
                "page_id": "page-1",
                "tab_action": "switch",
                "index": 1,
                "verification": {"text_present": "Authenticated continuation ready"},
            },
            {
                "action": "type",
                "page_id": "page-1",
                "selector": "#note",
                "text": "Carrier Runtime Draft",
            },
            {
                "action": "click",
                "page_id": "page-1",
                "selector": "#save-note",
                "wait": 300,
                "verification": {"text_present": "Draft saved: Carrier Runtime Draft"},
            },
            {
                "action": "navigate",
                "page_id": "page-1",
                "url": workspace_path.resolve().as_uri(),
                "verification": {"text_present": "Draft loaded: Carrier Runtime Draft"},
            },
            {
                "action": "click",
                "page_id": "page-1",
                "selector": "#download-link",
                "wait": 300,
                "verification": {"text_present": "Download prepared: carrier-export.txt"},
            },
            {
                "action": "screenshot",
                "page_id": "page-1",
                "path": str(screenshot_path),
                "verification": {"file_exists": str(screenshot_path)},
            },
        ],
        evidence_expectations=[
            "open",
            "click",
            "click",
            "tabs",
            "type",
            "click",
            "navigate",
            "click",
            "screenshot",
        ],
    )
    run = payload["runs"][0]
    assert run["status"] == "completed"
    assert run["deterministic_result"] == "replay-complete"
    assert run["actions"] == [
        "open",
        "click",
        "click",
        "tabs",
        "type",
        "click",
        "navigate",
        "click",
        "screenshot",
    ]
    assert all(run["screenshot_exists"].values())
    verification_summary = dict(run["verification_summary"] or {})
    assert verification_summary.get("chain_status") == "verified"
    assert verification_summary.get("verified_steps") == 9
    assert verification_summary.get("observed_steps") == 9
    assert verification_summary.get("total_steps") == 9
    anchors = list(verification_summary.get("evidence_anchors") or [])
    assert len(anchors) == 9
    assert anchors[3].get("action") == "tabs"
    assert anchors[-1].get("artifact_path") == str(screenshot_path)


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_V6_LIVE_ROUTINE_SMOKE"),
    reason=LIVE_ROUTINE_SMOKE_SKIP_REASON,
)
@pytest.mark.asyncio
async def test_live_desktop_routine_launch_edit_save_round_trip(tmp_path) -> None:
    if sys.platform != "win32":
        pytest.skip("Desktop live routine smoke requires a Windows host.")

    harness = _build_live_routine_harness(tmp_path)
    unique_name = f"live-desktop-routine-launch-note-{uuid.uuid4().hex[:8]}.txt"
    target_path = tmp_path / unique_name
    target_path.write_text("alpha", encoding="utf-8")
    selector = {"title_contains": target_path.name}
    try:
        routine = harness.service.create_routine(
            RoutineCreateRequest(
                routine_key="live-desktop-routine-launch-smoke",
                name="Live Desktop Routine Launch Smoke",
                summary="Launch Notepad on a unique file, click into the window, replace the content, save, and close through the V6 desktop routine path.",
                engine_kind="desktop",
                environment_kind="desktop",
                action_contract=[
                    {
                        "action": "launch_application",
                        "executable": "notepad.exe",
                        "args": [str(target_path)],
                    },
                    {
                        "action": "wait_for_window",
                        "selector": selector,
                        "timeout_seconds": 10.0,
                        "include_hidden": True,
                    },
                    {
                        "action": "click",
                        "selector": selector,
                        "relative_to_window": True,
                        "x": 120,
                        "y": 120,
                    },
                    {
                        "action": "press_keys",
                        "selector": selector,
                        "keys": "Ctrl+A",
                    },
                    {
                        "action": "type_text",
                        "selector": selector,
                        "text": "desktop runtime verified",
                    },
                    {
                        "action": "press_keys",
                        "selector": selector,
                        "keys": "Ctrl+S",
                    },
                    {
                        "action": "close_window",
                        "selector": selector,
                    },
                ],
            ),
        )

        response = await harness.service.replay_routine(
            routine.id,
            RoutineReplayRequest(),
        )

        assert response.run.status == "completed"
        assert response.run.deterministic_result == "desktop-replay-complete"
        for _ in range(10):
            if target_path.read_text(encoding="utf-8") == "desktop runtime verified":
                break
            await asyncio.sleep(0.5)
        assert target_path.read_text(encoding="utf-8") == "desktop runtime verified"
        verification_summary = dict(response.run.metadata.get("verification_summary") or {})
        assert verification_summary.get("chain_status") == "verified"
        assert verification_summary.get("verified_steps") == 7
        records = harness.ledger.list_by_task(f"routine-run:{response.run.id}")
        assert [record.metadata.get("action") for record in records] == [
            "launch_application",
            "wait_for_window",
            "click",
            "press_keys",
            "type_text",
            "press_keys",
            "close_window",
        ]
    finally:
        harness.ledger.close()


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_V6_LIVE_ROUTINE_SMOKE"),
    reason=LIVE_ROUTINE_SMOKE_SKIP_REASON,
)
@pytest.mark.asyncio
async def test_live_desktop_routine_replay_round_trip(tmp_path) -> None:
    if sys.platform != "win32":
        pytest.skip("Desktop live routine smoke requires a Windows host.")

    harness = _build_live_routine_harness(tmp_path)
    try:
        foreground = routine_service_module.WindowsDesktopHost().get_foreground_window()
        if not foreground.get("success") or not foreground.get("handle"):
            pytest.skip("Desktop live routine smoke requires a resolvable foreground window.")
        target_path = tmp_path / "live-desktop-routine-note.txt"
        routine = harness.service.create_routine(
            RoutineCreateRequest(
                routine_key="live-desktop-routine-smoke",
                name="Live Desktop Routine Smoke",
                summary="Create, edit, save, reopen, reread, and verify the focused window through the V6 desktop routine path.",
                engine_kind="desktop",
                environment_kind="desktop",
                action_contract=[
                    {
                        "action": "write_document_file",
                        "path": str(target_path),
                        "content": "desktop draft v1",
                    },
                    {
                        "action": "edit_document_file",
                        "path": str(target_path),
                        "find_text": "v1",
                        "replace_text": "v2",
                    },
                    {
                        "action": "verify_window_focus",
                        "selector": {"handle": foreground["handle"]},
                    },
                ],
            ),
        )

        response = await harness.service.replay_routine(
            routine.id,
            RoutineReplayRequest(),
        )

        assert response.run.status == "completed"
        assert response.run.deterministic_result == "desktop-replay-complete"
        verification_summary = dict(response.run.metadata.get("verification_summary") or {})
        assert verification_summary.get("chain_status") == "verified"
        assert verification_summary.get("verified_steps") == 3
        records = harness.ledger.list_by_task(f"routine-run:{response.run.id}")
        assert [record.metadata.get("action") for record in records] == [
            "write_document_file",
            "edit_document_file",
            "verify_window_focus",
        ]
        assert target_path.read_text(encoding="utf-8") == "desktop draft v2"
        assert dict(records[0].metadata.get("verification") or {}).get("verified") is True
        assert dict(records[1].metadata.get("verification") or {}).get("verified") is True
        assert dict(records[2].metadata.get("result") or {}).get("is_foreground") is True
    finally:
        harness.ledger.close()
