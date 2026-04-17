# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from weakref import WeakSet

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from copaw.agents.tools import browser_control as browser_control_module
from copaw.agents.tools import browser_control_actions_core
from copaw.agents.tools import browser_control_actions_extended
from copaw.agents.tools import browser_control_shared
from copaw.agents.tools.browser_control import (
    browser_use,
    list_browser_downloads,
    run_browser_use_json,
)
from copaw.agents.tools.evidence_runtime import bind_browser_evidence_sink
from copaw.app.runtime_events import RuntimeEventBus
from copaw.capabilities import browser_runtime as browser_runtime_module
from copaw.capabilities.browser_runtime import BrowserRuntimeService, BrowserSessionStartOptions
from copaw.environments import lease_service as lease_service_module
from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    SessionMountRepository,
)
from copaw.state import SQLiteStateStore


def _json_response(payload: dict[str, object]) -> ToolResponse:
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=json.dumps(payload, ensure_ascii=False, indent=2),
            ),
        ],
    )


def _response_payload(response: ToolResponse) -> dict[str, object]:
    return json.loads(response.content[0]["text"])


def _build_environment_service(tmp_path):
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(state_store)
    session_repo = SessionMountRepository(state_store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    environment_service.set_session_repository(session_repo)
    return environment_service, env_repo, session_repo


def test_browser_use_keeps_default_behavior_without_sink(monkeypatch) -> None:
    async def fake_open(url: str, page_id: str):
        return _json_response({"ok": True, "message": f"Opened {url}"})

    monkeypatch.setattr("copaw.agents.tools.browser_control._action_open", fake_open)

    response = asyncio.run(browser_use(action="open", url="https://example.com", page_id="page-1"))

    assert "Opened https://example.com" in response.content[0]["text"]


def test_browser_use_starts_visible_browser_by_default(monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def fake_start(
        *,
        headed: bool,
        session_id: str,
        profile_id: str,
        entry_url: str,
        persist_login_state: bool,
        storage_state_path: str,
        navigation_guard_json: str,
        action_timeout_seconds: float,
    ):
        seen.update(
            {
                "headed": headed,
                "session_id": session_id,
                "profile_id": profile_id,
                "navigation_guard_json": navigation_guard_json,
                "action_timeout_seconds": action_timeout_seconds,
            }
        )
        return _json_response({"ok": True, "message": "Browser session started (visible window)"})

    monkeypatch.setattr("copaw.agents.tools.browser_control._action_start", fake_start)

    response = asyncio.run(browser_use(action="start"))

    assert "visible window" in response.content[0]["text"]
    assert seen["headed"] is True
    assert seen["session_id"] == "default"
    assert seen["navigation_guard_json"] == ""
    assert seen["action_timeout_seconds"] == 0


def test_browser_use_emits_open_success_payload(monkeypatch) -> None:
    payloads: list[dict[str, object]] = []

    async def fake_open(url: str, page_id: str):
        return _json_response(
            {
                "ok": True,
                "message": f"Opened {url}",
                "page_id": page_id,
                "url": url,
            },
        )

    monkeypatch.setattr("copaw.agents.tools.browser_control._action_open", fake_open)

    async def run() -> None:
        with bind_browser_evidence_sink(payloads.append):
            await browser_use(action="open", url="https://example.com", page_id="page-1")

    asyncio.run(run())

    assert len(payloads) == 1
    assert payloads[0]["tool_name"] == "browser_use"
    assert payloads[0]["action"] == "open"
    assert payloads[0]["page_id"] == "page-1"
    assert payloads[0]["status"] == "success"
    assert payloads[0]["url"] == "https://example.com"
    assert payloads[0]["result_summary"] == "Opened https://example.com"
    assert payloads[0]["metadata"]["verification"]["verified"] is True
    assert payloads[0]["metadata"]["verification"]["kind"] == "navigation"
    assert payloads[0]["metadata"]["verification"]["observed_after"]["url"] == "https://example.com"


def test_browser_open_blocks_host_outside_navigation_guard_allowlist(monkeypatch) -> None:
    class _FakePage:
        def __init__(self) -> None:
            self.goto_calls: list[str] = []
            self.url = ""

        def on(self, *_args, **_kwargs) -> None:
            return None

        async def goto(self, url: str) -> None:
            self.goto_calls.append(url)
            self.url = url

    class _FakeContext:
        def __init__(self) -> None:
            self.page = _FakePage()
            self.new_page_calls = 0

        def on(self, *_args, **_kwargs) -> None:
            return None

        async def new_page(self):
            self.new_page_calls += 1
            return self.page

    browser_control_shared._state["sessions"] = {}
    browser_control_shared._state["current_session_id"] = None
    session = browser_control_shared._get_session_state("default", create=True)
    assert session is not None
    context = _FakeContext()
    session["context"] = context
    session["navigation_guard"] = {"allowed_hosts": ["example.com"]}

    async def fake_ensure_browser() -> bool:
        return True

    async def fake_ensure_browser_session(*_args, **_kwargs):
        return session

    monkeypatch.setattr(browser_control_actions_core, "_ensure_browser", fake_ensure_browser)
    monkeypatch.setattr(
        browser_control_actions_core,
        "_ensure_browser_session",
        fake_ensure_browser_session,
    )

    response = asyncio.run(
        browser_control_actions_core._action_open(
            "https://blocked.example.net",
            "page-1",
            "default",
        ),
    )

    payload = _response_payload(response)
    assert payload["ok"] is False
    assert payload["guardrail"]["kind"] == "navigation-guard"
    assert "not allowlisted" in payload["error"].lower()
    assert context.new_page_calls == 0


def test_browser_navigate_blocks_host_inside_navigation_guard_blocklist() -> None:
    class _FakePage:
        def __init__(self) -> None:
            self.goto_calls: list[str] = []
            self.url = "https://example.com"

        async def goto(self, url: str) -> None:
            self.goto_calls.append(url)
            self.url = url

    browser_control_shared._state["sessions"] = {}
    browser_control_shared._state["current_session_id"] = None
    session = browser_control_shared._get_session_state("default", create=True)
    assert session is not None
    page = _FakePage()
    session["pages"] = {"page-1": page}
    session["navigation_guard"] = {"blocked_hosts": ["internal.example.com"]}

    response = asyncio.run(
        browser_control_actions_core._action_navigate(
            "https://internal.example.com/dashboard",
            "page-1",
            "default",
        ),
    )

    payload = _response_payload(response)
    assert payload["ok"] is False
    assert payload["guardrail"]["kind"] == "navigation-guard"
    assert "blocked by browser navigation guard" in payload["error"].lower()
    assert page.goto_calls == []


def test_browser_open_does_not_clobber_persisted_session_storage_contract(
    tmp_path,
    monkeypatch,
) -> None:
    class _FakePage:
        def __init__(self) -> None:
            self.url = ""

        def on(self, *_args, **_kwargs) -> None:
            return None

        async def goto(self, url: str) -> None:
            self.url = url

    class _FakeContext:
        def __init__(self) -> None:
            self.page = _FakePage()
            self.storage_state_calls: list[str] = []
            self.closed = False

        def on(self, *_args, **_kwargs) -> None:
            return None

        async def new_page(self):
            return self.page

        async def storage_state(self, *, path: str):
            self.storage_state_calls.append(path)
            Path(path).write_text("{}", encoding="utf-8")

        async def close(self) -> None:
            self.closed = True

    storage_state_path = tmp_path / "browser-storage.json"
    fake_context = _FakeContext()

    async def fake_ensure_browser() -> bool:
        return True

    async def fake_create_browser_context(storage_state_path: str = ""):
        _ = storage_state_path
        return fake_context

    browser_control_shared._state["sessions"] = {}
    browser_control_shared._state["current_session_id"] = None
    monkeypatch.setattr(browser_control_actions_core, "_ensure_browser", fake_ensure_browser)
    monkeypatch.setattr(
        browser_control_actions_core,
        "_create_browser_context",
        fake_create_browser_context,
    )

    async def run() -> None:
        await browser_control_actions_core._ensure_browser_session(
            "persisted-session",
            persist_login_state=True,
            storage_state_path=str(storage_state_path),
        )
        await browser_control_actions_core._action_open(
            "https://example.com/runtime",
            "page-1",
            "persisted-session",
        )
        await browser_control_actions_core._close_session_context("persisted-session")

    asyncio.run(run())

    assert fake_context.storage_state_calls == [str(storage_state_path)]
    assert storage_state_path.exists() is True
    assert fake_context.closed is True


def test_browser_use_emits_navigation_guardrail_metadata_when_navigation_is_blocked(
    monkeypatch,
) -> None:
    payloads: list[dict[str, object]] = []

    browser_control_shared._state["sessions"] = {}
    browser_control_shared._state["current_session_id"] = None
    session = browser_control_shared._get_session_state("default", create=True)
    assert session is not None
    session["navigation_guard"] = {"allowed_hosts": ["example.com"]}

    async def fake_ensure_browser() -> bool:
        return True

    async def fake_ensure_browser_session(*_args, **_kwargs):
        return session

    monkeypatch.setattr(browser_control_actions_core, "_ensure_browser", fake_ensure_browser)
    monkeypatch.setattr(
        browser_control_actions_core,
        "_ensure_browser_session",
        fake_ensure_browser_session,
    )

    async def run() -> None:
        with bind_browser_evidence_sink(payloads.append):
            await browser_use(
                action="open",
                url="https://blocked.example.net",
                page_id="page-1",
                session_id="default",
            )

    asyncio.run(run())

    assert len(payloads) == 1
    assert payloads[0]["status"] == "error"
    assert payloads[0]["metadata"]["guardrail"]["kind"] == "navigation-guard"
    assert payloads[0]["metadata"]["guardrail"]["policy"] == "allowlist"


def test_browser_use_times_out_and_emits_timeout_guardrail(monkeypatch) -> None:
    payloads: list[dict[str, object]] = []

    browser_control_shared._state["sessions"] = {}
    browser_control_shared._state["current_session_id"] = None
    session = browser_control_shared._get_session_state("default", create=True)
    assert session is not None
    session["action_timeout_seconds"] = 0.01

    async def fake_open(url: str, page_id: str, session_id: str):
        await asyncio.sleep(0.05)
        return _json_response(
            {
                "ok": True,
                "message": f"Opened {url}",
                "page_id": page_id,
                "url": url,
            },
        )

    monkeypatch.setattr("copaw.agents.tools.browser_control._action_open", fake_open)

    async def run() -> ToolResponse:
        with bind_browser_evidence_sink(payloads.append):
            return await browser_use(
                action="open",
                url="https://example.com/slow",
                page_id="page-1",
                session_id="default",
            )

    response = asyncio.run(run())
    payload = _response_payload(response)

    assert payload["ok"] is False
    assert payload["guardrail"]["kind"] == "timeout"
    assert "timed out" in payload["error"].lower()
    assert len(payloads) == 1
    assert payloads[0]["status"] == "error"
    assert payloads[0]["metadata"]["guardrail"]["kind"] == "timeout"


def test_browser_use_emits_click_error_payload(monkeypatch) -> None:
    payloads: list[dict[str, object]] = []

    async def fake_click(*args, **kwargs):
        return _json_response(
            {
                "ok": False,
                "error": "Click failed: element missing",
            },
        )

    monkeypatch.setattr("copaw.agents.tools.browser_control._action_click", fake_click)
    monkeypatch.setattr(
        "copaw.agents.tools.browser_control._current_page_url",
        lambda page_id: "https://example.com/current",
    )

    async def run() -> None:
        with bind_browser_evidence_sink(payloads.append):
            await browser_use(action="click", page_id="page-2", selector="#submit")

    asyncio.run(run())

    assert len(payloads) == 1
    assert payloads[0]["action"] == "click"
    assert payloads[0]["status"] == "error"
    assert payloads[0]["url"] == "https://example.com/current"
    assert payloads[0]["metadata"]["selector"] == "#submit"
    assert payloads[0]["result_summary"] == "Click failed: element missing"


def test_click_wait_applies_after_click(monkeypatch) -> None:
    events: list[str] = []

    class _FakeLocator:
        @property
        def first(self):
            return self

        async def click(self, **kwargs):
            _ = kwargs
            events.append("click")

    class _FakePage:
        def locator(self, selector: str):
            _ = selector
            return _FakeLocator()

    async def fake_sleep(delay: float) -> None:
        events.append(f"sleep:{delay}")

    monkeypatch.setattr(
        browser_control_actions_core,
        "_get_page",
        lambda page_id, session_id="default": _FakePage(),
    )
    monkeypatch.setattr(
        browser_control_actions_core,
        "_get_root",
        lambda page, page_id, frame_selector="": page,
    )
    monkeypatch.setattr(
        browser_control_actions_core,
        "_touch_activity",
        lambda session_id="default": events.append("touch"),
    )
    monkeypatch.setattr(browser_control_actions_core.asyncio, "sleep", fake_sleep)

    response = asyncio.run(
        browser_control_actions_core._action_click(
            "page-1",
            "#open-workspace",
            wait=250,
            session_id="default",
        ),
    )

    payload = _response_payload(response)
    assert payload["ok"] is True
    assert events == ["click", "sleep:0.25", "touch"]


def test_browser_use_emits_screenshot_payload_with_async_sink(monkeypatch) -> None:
    payloads: list[dict[str, object]] = []

    async def fake_screenshot(*args, **kwargs):
        return _json_response(
            {
                "ok": True,
                "message": "Screenshot saved to shot.png",
                "path": "shot.png",
            },
        )

    async def sink(payload: dict[str, object]) -> None:
        payloads.append(payload)

    monkeypatch.setattr(
        "copaw.agents.tools.browser_control._action_screenshot",
        fake_screenshot,
    )
    monkeypatch.setattr(
        "copaw.agents.tools.browser_control._current_page_url",
        lambda page_id: "https://example.com/shot",
    )

    async def run() -> None:
        with bind_browser_evidence_sink(sink):
            await browser_use(
                action="screenshot",
                page_id="page-3",
                path="shot.png",
                full_page=True,
            )

    asyncio.run(run())

    assert len(payloads) == 1
    assert payloads[0]["action"] == "screenshot"
    assert payloads[0]["status"] == "success"
    assert payloads[0]["url"] == "https://example.com/shot"
    assert payloads[0]["metadata"]["path"] == "shot.png"
    assert payloads[0]["metadata"]["full_page"] is True


def test_browser_use_routes_snapshot_and_wait_for_extended_actions(monkeypatch) -> None:
    async def fake_snapshot(*args, **kwargs):
        return _json_response({"ok": True, "message": "Snapshot captured"})

    async def fake_wait_for(*args, **kwargs):
        return _json_response({"ok": True, "message": "Wait completed"})

    monkeypatch.setattr(browser_control_module, "_action_snapshot", fake_snapshot)
    monkeypatch.setattr(browser_control_module, "_action_wait_for", fake_wait_for)

    snapshot_response = asyncio.run(
        browser_use(action="snapshot", page_id="page-4", snapshot_filename="page.json"),
    )
    wait_response = asyncio.run(
        browser_use(action="wait_for", page_id="page-4", wait=1),
    )

    assert "Snapshot captured" in snapshot_response.content[0]["text"]
    assert "Wait completed" in wait_response.content[0]["text"]


def test_wait_for_passes_text_argument_via_keyword(monkeypatch) -> None:
    class _FakePage:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def wait_for_function(self, script: str, *, arg=None, timeout=None):
            self.calls.append(
                {
                    "script": script,
                    "arg": arg,
                    "timeout": timeout,
                },
            )

    page = _FakePage()
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_get_page",
        lambda page_id, session_id="default": page,
    )
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_touch_activity",
        lambda session_id="default": None,
    )

    response = asyncio.run(
        browser_control_actions_extended._action_wait_for(
            "page-1",
            wait_time=1.5,
            text="Uploaded: upload.txt",
            session_id="default",
        ),
    )

    payload = _response_payload(response)
    assert payload["ok"] is True
    assert payload["message"] == "Text appeared: Uploaded: upload.txt"
    assert page.calls == [
        {
            "script": "(text) => document.body && document.body.innerText.includes(text)",
            "arg": "Uploaded: upload.txt",
            "timeout": 1500,
        },
    ]


def test_browser_use_emits_fill_form_success_payload(monkeypatch) -> None:
    payloads: list[dict[str, object]] = []

    async def fake_fill_form(*args, **kwargs):
        return _json_response(
            {
                "ok": True,
                "message": "Filled 1 field(s)",
                "verification": {
                    "verified": True,
                    "verified_fields": ["email"],
                },
            },
        )

    monkeypatch.setattr(
        browser_control_module,
        "_action_fill_form",
        fake_fill_form,
    )
    monkeypatch.setattr(
        "copaw.agents.tools.browser_control._current_page_url",
        lambda page_id: "https://example.com/form",
    )

    async def run() -> None:
        with bind_browser_evidence_sink(payloads.append):
            await browser_use(
                action="fill_form",
                page_id="page-form",
                fields_json=json.dumps([{"ref": "email", "value": "ops@example.com"}]),
            )

    asyncio.run(run())

    assert len(payloads) == 1
    assert payloads[0]["action"] == "fill_form"
    assert payloads[0]["status"] == "success"
    assert payloads[0]["url"] == "https://example.com/form"
    assert payloads[0]["metadata"]["verification"]["verified"] is True
    assert payloads[0]["metadata"]["verification"]["kind"] == "page-state"


def test_browser_use_emits_click_download_verification_payload(tmp_path, monkeypatch) -> None:
    payloads: list[dict[str, object]] = []
    download_path = tmp_path / "report.csv"
    download_path.write_text("id,name\n1,acceptance\n", encoding="utf-8")

    async def fake_click(*args, **kwargs):
        return _json_response(
            {
                "ok": True,
                "message": "Clicked #download-report",
            },
        )

    def _fake_session_bucket(key: str, session_id: str = "default", create: bool = False):
        _ = session_id, create
        if key == "downloads":
            return {
                "page-download": [
                    {
                        "status": "completed",
                        "verified": True,
                        "path": str(download_path),
                        "exists": True,
                        "suggested_filename": "report.csv",
                    },
                ],
            }
        return {}

    monkeypatch.setattr(browser_control_module, "_action_click", fake_click)
    monkeypatch.setattr(
        browser_control_module,
        "_current_page_url",
        lambda page_id: "https://example.com/export",
    )
    monkeypatch.setattr(
        browser_control_shared,
        "_session_bucket",
        _fake_session_bucket,
    )

    async def run() -> None:
        with bind_browser_evidence_sink(payloads.append):
            await browser_use(
                action="click",
                page_id="page-download",
                selector="#download-report",
                session_id="export-session",
            )

    asyncio.run(run())

    assert len(payloads) == 1
    assert payloads[0]["action"] == "click"
    assert payloads[0]["status"] == "success"
    assert payloads[0]["metadata"]["verification"]["verified"] is True
    assert payloads[0]["metadata"]["verification"]["kind"] == "download"
    assert payloads[0]["metadata"]["verification"]["channel"] == "playwright-download+filesystem"
    assert payloads[0]["metadata"]["verification"]["download"]["path"] == str(download_path)


def test_browser_use_blocks_when_global_operator_abort_is_requested_for_bound_browser_session(
    tmp_path,
    monkeypatch,
) -> None:
    payloads: list[dict[str, object]] = []
    environment_service, _, _ = _build_environment_service(tmp_path)
    event_bus = RuntimeEventBus(max_events=20)
    environment_service.set_runtime_event_bus(event_bus)

    lease = environment_service.acquire_session_lease(
        channel="desktop",
        session_id="seat-browser-abort",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        metadata={
            "work_context_id": "ctx-browser-abort",
            "workspace_scope": "task:task-1",
        },
    )
    environment_service.register_browser_attach_transport(
        session_mount_id=lease.id,
        transport_ref="transport:cdp:local",
        status="attached",
        browser_session_ref="browser-session:web:abort",
        browser_scope_ref="site:jd:seller-center",
        reconnect_token="reconnect-abort",
    )
    environment_service._lease_service.set_shared_operator_abort_state(
        lease.id,
        channel="global-esc",
        reason="global-esc",
    )

    async def fake_open(*args, **kwargs):
        _ = args, kwargs
        raise AssertionError("browser action should not run after operator abort")

    monkeypatch.setattr("copaw.agents.tools.browser_control._action_open", fake_open)

    async def run() -> ToolResponse:
        with bind_browser_evidence_sink(payloads.append):
            return await browser_use(
                action="open",
                url="https://example.com/abort",
                page_id="page-abort",
                session_id="browser-session:web:abort",
            )

    response = asyncio.run(run())
    payload = _response_payload(response)

    assert payload["ok"] is False
    assert "operator abort" in str(payload["error"]).lower()
    assert len(payloads) == 1
    assert payloads[0]["status"] == "error"
    assert payloads[0]["metadata"]["guardrail"]["kind"] == "operator-abort"
    assert payloads[0]["metadata"]["guardrail"]["reason"] == "global-esc"
    assert payloads[0]["metadata"]["session_mount_id"] == lease.id

    blocked = [
        event
        for event in event_bus.list_events(limit=10)
        if event.event_name == "browser.guardrail-blocked"
    ]
    assert blocked
    assert blocked[-1].payload["guardrail_kind"] == "operator-abort"
    assert blocked[-1].payload["reason"] == "global-esc"


def test_browser_use_does_not_treat_unrelated_default_desktop_session_as_browser_abort_binding(
    tmp_path,
    monkeypatch,
) -> None:
    payloads: list[dict[str, object]] = []
    environment_service, _, _ = _build_environment_service(tmp_path)
    monkeypatch.setattr(
        lease_service_module,
        "_ACTIVE_LEASE_SERVICES",
        WeakSet([environment_service._lease_service]),
    )

    lease = environment_service.acquire_session_lease(
        channel="desktop",
        session_id="default",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        metadata={
            "work_context_id": "ctx-browser-default-collision",
            "workspace_scope": "task:task-1",
        },
    )
    environment_service._lease_service.set_shared_operator_abort_state(
        lease.id,
        channel="global-esc",
        reason="global-esc",
    )

    async def fake_open(*args, **kwargs):
        _ = args, kwargs
        return _json_response({"ok": True, "page_id": "default"})

    monkeypatch.setattr("copaw.agents.tools.browser_control._action_open", fake_open)

    async def run() -> ToolResponse:
        with bind_browser_evidence_sink(payloads.append):
            return await browser_use(
                action="open",
                url="https://example.com/default",
                page_id="default",
                session_id="default",
            )

    response = asyncio.run(run())
    payload = _response_payload(response)

    assert payload["ok"] is True
    assert not any(
        item.get("metadata", {}).get("guardrail", {}).get("kind") == "operator-abort"
        for item in payloads
    )


def test_attach_download_listener_accepts_property_filename(tmp_path, monkeypatch) -> None:
    download_path = tmp_path / "listener-report.csv"
    download_path.write_text("id,name\n1,listener\n", encoding="utf-8")
    buckets: dict[str, dict[str, object]] = {}

    class _FakePage:
        def __init__(self) -> None:
            self.handlers: dict[str, object] = {}

        def on(self, event: str, handler) -> None:
            self.handlers[event] = handler

    class _FakeDownload:
        url = "https://example.com/listener-report.csv"
        suggested_filename = "listener-report.csv"

        async def path(self):
            return str(download_path)

    def _fake_session_bucket(key: str, session_id: str = "default", create: bool = False):
        _ = session_id, create
        return buckets.setdefault(key, {})

    async def run() -> None:
        page = _FakePage()
        monkeypatch.setattr(
            browser_control_shared,
            "_session_bucket",
            _fake_session_bucket,
        )
        monkeypatch.setattr(
            browser_control_shared,
            "_touch_activity",
            lambda session_id="default": None,
        )
        browser_control_shared._attach_download_listener(page, "page-1", "default")
        handler = page.handlers["download"]
        handler(_FakeDownload())
        await asyncio.sleep(0)

    asyncio.run(run())

    downloads = buckets["downloads"]["page-1"]
    assert len(downloads) == 1
    assert downloads[0]["suggested_filename"] == "listener-report.csv"
    assert downloads[0]["status"] == "completed"
    assert downloads[0]["exists"] is True


def test_list_browser_downloads_reads_verified_records_from_shared_bucket() -> None:
    browser_control_shared._state["sessions"] = {}
    browser_control_shared._state["current_session_id"] = None
    session = browser_control_shared._get_session_state("research-session", create=True)
    assert session is not None
    session["downloads"] = {
        "page-1": [
            {
                "page_id": "page-1",
                "path": "D:/tmp/report.pdf",
                "suggested_filename": "report.pdf",
                "status": "completed",
                "verified": True,
                "exists": True,
            },
        ],
        "page-2": [
            {
                "page_id": "page-2",
                "path": "D:/tmp/ignore.txt",
                "suggested_filename": "ignore.txt",
                "status": "completed",
                "verified": True,
                "exists": True,
            },
        ],
    }

    downloads = list_browser_downloads(session_id="research-session", page_id="page-1")

    assert [item["page_id"] for item in downloads] == ["page-1"]
    assert downloads[0]["suggested_filename"] == "report.pdf"


def test_run_browser_use_json_returns_parsed_payload(monkeypatch) -> None:
    async def fake_browser_use(**_payload):
        return _json_response({"ok": True, "page_id": "page-1"})

    monkeypatch.setattr(browser_control_module, "browser_use", fake_browser_use)

    payload = run_browser_use_json(action="snapshot", page_id="page-1")

    assert payload == {"ok": True, "page_id": "page-1"}


def test_fill_form_fails_when_requested_ref_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_get_page",
        lambda page_id, session_id="default": object(),
    )
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_get_refs",
        lambda page_id, session_id="default": {},
    )
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_session_bucket",
        lambda key, session_id="default", create=False: {},
    )

    response = asyncio.run(
        browser_control_actions_extended._action_fill_form(
            "page-form",
            json.dumps([{"ref": "missing-ref", "value": "ops@example.com"}]),
            "default",
        ),
    )

    payload = _response_payload(response)
    assert payload["ok"] is False
    assert "missing-ref" in payload["error"]


def test_fill_form_supports_selector_fields_without_snapshot_refs(monkeypatch) -> None:
    class _FakeLocator:
        def __init__(self) -> None:
            self.value = ""

        @property
        def first(self):
            return self

        async def fill(self, value: str) -> None:
            self.value = value

        async def input_value(self) -> str:
            return self.value

    class _FakePage:
        def __init__(self) -> None:
            self.locators = {
                "#name": _FakeLocator(),
                "#notes": _FakeLocator(),
            }

        def locator(self, selector: str):
            return self.locators[selector]

    page = _FakePage()
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_get_page",
        lambda page_id, session_id="default": page,
    )
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_get_refs",
        lambda page_id, session_id="default": {},
    )
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_get_root",
        lambda page_obj, page_id, frame_selector="": page_obj,
    )
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_session_bucket",
        lambda key, session_id="default", create=False: {},
    )
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_touch_activity",
        lambda session_id="default": None,
    )

    response = asyncio.run(
        browser_control_actions_extended._action_fill_form(
            "page-form",
            json.dumps(
                [
                    {"selector": "#name", "value": "Carrier Runtime"},
                    {"selector": "#notes", "value": "fill-form-ok"},
                ]
            ),
            "default",
        ),
    )

    payload = _response_payload(response)
    assert payload["ok"] is True
    assert payload["verification"]["verified"] is True
    assert payload["verification"]["verified_fields"] == ["#name", "#notes"]


def test_tabs_select_rejects_unknown_target(monkeypatch) -> None:
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_session_bucket",
        lambda key, session_id="default", create=False: {},
    )
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_touch_activity",
        lambda session_id="default": None,
    )

    response = asyncio.run(
        browser_control_actions_extended._action_tabs(
            "page-404",
            "select",
            -1,
            "default",
        ),
    )

    payload = _response_payload(response)
    assert payload["ok"] is False
    assert "page-404" in payload["error"]


def test_tabs_list_counts_unique_underlying_pages(monkeypatch) -> None:
    login_page = object()
    workspace_page = object()
    buckets = {
        "pages": {
            "page-1": login_page,
            "page-shadow": login_page,
            "page-2": workspace_page,
        }
    }

    monkeypatch.setattr(
        browser_control_actions_extended,
        "_session_bucket",
        lambda key, session_id="default", create=False: buckets.setdefault(key, {}),
    )

    response = asyncio.run(
        browser_control_actions_extended._action_tabs(
            "page-1",
            "list",
            -1,
            "default",
        ),
    )

    payload = _response_payload(response)
    assert payload["ok"] is True
    assert payload["count"] == 2
    assert payload["tabs"] == ["page-1", "page-2"]


def test_tabs_switch_rebinds_requested_page_id(monkeypatch) -> None:
    login_page = object()
    workspace_page = object()
    buckets = {
        "pages": {
            "page-1": login_page,
            "page-shadow": login_page,
            "page-2": workspace_page,
        }
    }
    current_page_ids: list[tuple[str | None, str | None]] = []

    monkeypatch.setattr(
        browser_control_actions_extended,
        "_session_bucket",
        lambda key, session_id="default", create=False: buckets.setdefault(key, {}),
    )
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_set_current_page_id",
        lambda page_id, session_id="default": current_page_ids.append((page_id, session_id)),
    )
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_touch_activity",
        lambda session_id="default": None,
    )

    response = asyncio.run(
        browser_control_actions_extended._action_tabs(
            "page-1",
            "switch",
            1,
            "default",
        ),
    )

    payload = _response_payload(response)
    assert payload["ok"] is True
    assert payload["page_id"] == "page-1"
    assert payload["selected_page_id"] == "page-2"
    assert payload["verification"]["current_page_id"] == "page-1"
    assert payload["verification"]["selected_page_id"] == "page-2"
    assert buckets["pages"]["page-1"] is workspace_page
    assert current_page_ids == [("page-1", "default")]


def test_file_upload_fails_when_page_state_does_not_change(monkeypatch) -> None:
    class _FakePage:
        def __init__(self) -> None:
            self._counts = [0, 0]

        async def evaluate(self, code: str):
            _ = code
            return self._counts.pop(0)

    class _FakeChooser:
        def __init__(self) -> None:
            self.received_paths: list[str] = []

        async def set_files(self, paths):
            self.received_paths = list(paths)

    chooser = _FakeChooser()
    page = _FakePage()

    def _fake_session_bucket(key: str, session_id: str = "default", create: bool = False):
        _ = session_id, create
        if key == "pending_file_choosers":
            return {"page-upload": [chooser]}
        return {}

    monkeypatch.setattr(
        browser_control_actions_extended,
        "_get_page",
        lambda page_id, session_id="default": page,
    )
    monkeypatch.setattr(
        browser_control_actions_extended,
        "_session_bucket",
        _fake_session_bucket,
    )

    response = asyncio.run(
        browser_control_actions_extended._action_file_upload(
            "page-upload",
            json.dumps(["D:/word/copaw/tests/fixtures/report.pdf"]),
            "default",
        ),
    )

    payload = _response_payload(response)
    assert payload["ok"] is False
    assert chooser.received_paths == ["D:/word/copaw/tests/fixtures/report.pdf"]
    assert "verification" in payload["error"].lower()


def test_browser_runtime_attach_reports_continuity_contract(tmp_path, monkeypatch) -> None:
    service = BrowserRuntimeService(SQLiteStateStore(tmp_path / "state.sqlite3"))
    service.ensure_default_profile(
        profile_id="browser-local-default",
        persist_login_state=True,
    )
    storage_state_path = tmp_path / "browser-local-default.json"
    storage_state_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        browser_runtime_module,
        "_profile_storage_state_path",
        lambda profile_id: str(storage_state_path),
    )
    snapshots = iter(
        [
            {
                "sessions": [
                    {
                        "session_id": "default",
                    },
                ],
            },
            {
                "running": True,
                "current_session_id": "default",
                "session_count": 1,
                "sessions": [
                    {
                        "session_id": "default",
                        "persist_login_state": True,
                        "storage_state_path": str(storage_state_path),
                        "storage_state_available": True,
                        "page_count": 2,
                        "page_ids": ["default", "page_2"],
                        "download_verification": True,
                        "download_count": 1,
                        "completed_download_count": 1,
                        "downloads": [
                            {
                                "status": "completed",
                                "verified": True,
                                "path": str(tmp_path / "report.csv"),
                                "suggested_filename": "report.csv",
                            },
                        ],
                    },
                ],
            },
        ],
    )
    monkeypatch.setattr(
        browser_runtime_module,
        "get_browser_runtime_snapshot",
        lambda: next(snapshots),
    )
    monkeypatch.setattr(
        browser_runtime_module,
        "attach_browser_session",
        lambda session_id: {"ok": True, "session_id": session_id},
    )

    result = asyncio.run(
        service.start_session(
            BrowserSessionStartOptions(
                session_id="default",
                reuse_running_session=True,
            ),
        ),
    )

    assert result["status"] == "attached"
    assert result["continuity"]["browser_mode"] == "managed-isolated"
    assert result["continuity"]["resume_kind"] == "attach-running-session"
    assert result["continuity"]["authenticated_continuation"] is True
    assert result["continuity"]["cross_tab_continuation"] is True
    assert result["continuity"]["download_verification"] is True
    assert result["continuity"]["save_reopen_verification"] is True
    assert result["continuity"]["verification"]["download"]["verified"] is True
    assert result["continuity"]["verification"]["save_reopen"]["verified"] is True


def test_browser_runtime_attach_does_not_fake_save_reopen_verification(tmp_path, monkeypatch) -> None:
    service = BrowserRuntimeService(SQLiteStateStore(tmp_path / "state.sqlite3"))
    service.ensure_default_profile(
        profile_id="browser-local-default",
        persist_login_state=True,
    )
    monkeypatch.setattr(
        browser_runtime_module,
        "_profile_storage_state_path",
        lambda profile_id: str(tmp_path / "missing-storage-state.json"),
    )
    snapshots = iter(
        [
            {
                "sessions": [
                    {
                        "session_id": "default",
                    },
                ],
            },
            {
                "running": True,
                "current_session_id": "default",
                "session_count": 1,
                "sessions": [
                    {
                        "session_id": "default",
                        "persist_login_state": True,
                        "page_count": 1,
                        "page_ids": ["default"],
                    },
                ],
            },
        ],
    )
    monkeypatch.setattr(
        browser_runtime_module,
        "get_browser_runtime_snapshot",
        lambda: next(snapshots),
    )
    monkeypatch.setattr(
        browser_runtime_module,
        "attach_browser_session",
        lambda session_id: {"ok": True, "session_id": session_id},
    )

    result = asyncio.run(
        service.start_session(
            BrowserSessionStartOptions(
                session_id="default",
                reuse_running_session=True,
            ),
        ),
    )

    assert result["status"] == "attached"
    assert result["continuity"]["save_reopen_verification"] is False
    assert result["continuity"]["verification"]["save_reopen"]["verified"] is False


def test_browser_runtime_start_session_passes_profile_navigation_guard_to_browser_start(
    tmp_path,
    monkeypatch,
) -> None:
    service = BrowserRuntimeService(SQLiteStateStore(tmp_path / "state.sqlite3"))
    service.ensure_default_profile(
        profile_id="browser-local-default",
        persist_login_state=True,
        metadata={
            "navigation_guard": {
                "allowed_hosts": ["example.com"],
                "blocked_hosts": ["internal.example.com"],
            },
            "action_timeout_seconds": 15.0,
        },
    )

    seen: dict[str, object] = {}

    async def fake_browser_use(**kwargs):
        seen.update(kwargs)
        return _json_response({"ok": True, "message": "Browser session started"})

    monkeypatch.setattr(browser_runtime_module, "browser_use", fake_browser_use)
    monkeypatch.setattr(
        browser_runtime_module,
        "get_browser_runtime_snapshot",
        lambda: {"running": True, "sessions": []},
    )

    result = asyncio.run(
        service.start_session(
            BrowserSessionStartOptions(
                session_id="default",
                reuse_running_session=False,
            ),
        ),
    )

    assert result["status"] == "started"
    assert json.loads(str(seen["navigation_guard_json"])) == {
        "allowed_hosts": ["example.com"],
        "blocked_hosts": ["internal.example.com"],
    }
    assert seen["action_timeout_seconds"] == 15.0


def test_browser_runtime_companion_snapshot_preserves_mount_truth_continuity_refs(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(state_store)
    session_repo = SessionMountRepository(state_store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    environment_service.set_session_repository(session_repo)

    lease = environment_service.acquire_session_lease(
        channel="desktop",
        session_id="seat-browser-companion",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={"page_id": "page:jd:seller-center:home"},
        metadata={
            "work_context_id": "ctx-browser-companion",
            "workspace_scope": "task:task-1",
        },
    )
    environment_service.register_browser_companion(
        session_mount_id=lease.id,
        transport_ref="transport:cdp:local",
        status="attached",
        available=True,
        provider_session_ref="browser-session:web:main",
    )

    browser_runtime = BrowserRuntimeService(
        SQLiteStateStore(tmp_path / "browser.sqlite3"),
        browser_companion_runtime=environment_service._require_browser_companion_runtime(),
    )

    snapshot = browser_runtime.companion_snapshot(session_mount_id=lease.id)

    assert snapshot["transport_ref"] == "transport:cdp:local"
    assert snapshot["provider_session_ref"] == "browser-session:web:main"
    assert snapshot["environment_id"] == lease.environment_id
    assert snapshot["session_mount_id"] == lease.id
    assert snapshot["work_context_id"] == "ctx-browser-companion"


def test_browser_runtime_service_exposes_browser_attach_snapshot_and_registration_helper(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(state_store)
    session_repo = SessionMountRepository(state_store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    environment_service.set_session_repository(session_repo)

    lease = environment_service.acquire_session_lease(
        channel="desktop",
        session_id="seat-browser-attach-runtime",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={"page_id": "page:jd:seller-center:home"},
        metadata={
            "work_context_id": "ctx-browser-attach-runtime",
            "workspace_scope": "task:task-1",
        },
    )

    browser_runtime = BrowserRuntimeService(
        SQLiteStateStore(tmp_path / "browser.sqlite3"),
        browser_companion_runtime=environment_service._require_browser_companion_runtime(),
        browser_attach_runtime=environment_service._require_browser_attach_runtime(),
    )

    result = browser_runtime.register_attach_transport(
        session_mount_id=lease.id,
        transport_ref="transport:cdp:local",
        status="attached",
        browser_session_ref="browser-session:web:main",
        browser_scope_ref="site:jd:seller-center",
        reconnect_token="reconnect-token-1",
    )

    assert result["browser_attach"]["transport_ref"] == "transport:cdp:local"
    assert result["browser_attach"]["session_ref"] == "browser-session:web:main"
    assert result["browser_attach"]["scope_ref"] == "site:jd:seller-center"
    assert result["browser_attach"]["reconnect_token"] == "reconnect-token-1"

    snapshot = browser_runtime.runtime_snapshot(
        environment_id=lease.environment_id,
        session_mount_id=lease.id,
    )

    assert snapshot["browser_attach"]["transport_ref"] == "transport:cdp:local"
    assert snapshot["browser_attach"]["session_ref"] == "browser-session:web:main"


def test_browser_runtime_service_resolves_attach_snapshot_from_environment_id(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    env_repo = EnvironmentRepository(state_store)
    session_repo = SessionMountRepository(state_store)
    registry = EnvironmentRegistry(
        repository=env_repo,
        session_repository=session_repo,
        host_id="windows-host",
        process_id=4242,
    )
    environment_service = EnvironmentService(registry=registry, lease_ttl_seconds=120)
    environment_service.set_session_repository(session_repo)

    lease = environment_service.acquire_session_lease(
        channel="desktop",
        session_id="seat-browser-attach-runtime-env-id",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={"page_id": "page:jd:seller-center:home"},
        metadata={
            "work_context_id": "ctx-browser-attach-runtime-env-id",
            "workspace_scope": "task:task-1",
        },
    )

    environment_service.register_browser_attach_transport(
        session_mount_id=lease.id,
        transport_ref="transport:cdp:local",
        status="attached",
        browser_session_ref="browser-session:web:main",
        browser_scope_ref="site:jd:seller-center",
        reconnect_token="reconnect-token-1",
    )

    browser_runtime = BrowserRuntimeService(
        SQLiteStateStore(tmp_path / "browser.sqlite3"),
        browser_attach_runtime=environment_service._require_browser_attach_runtime(),
    )

    snapshot = browser_runtime.attach_snapshot(environment_id=lease.environment_id)

    assert snapshot["environment_id"] == lease.environment_id
    assert snapshot["session_mount_id"] == lease.id
    assert snapshot["transport_ref"] == "transport:cdp:local"
    assert snapshot["session_ref"] == "browser-session:web:main"


def test_browser_runtime_start_session_rebinds_existing_browser_mount_truth_after_restart(
    tmp_path,
    monkeypatch,
) -> None:
    environment_service, _, session_repo = _build_environment_service(tmp_path)
    lease = environment_service.acquire_session_lease(
        channel="browser",
        session_id="restart-browser-session",
        user_id="alice",
        owner="worker-1",
        ttl_seconds=60,
        handle={"page_id": "page:browser:before-restart"},
        metadata={
            "host_mode": "attach-existing-session",
            "lease_class": "exclusive-writer",
            "access_mode": "writer",
            "session_scope": "browser-user-session",
        },
    )
    assert lease.lease_token is not None

    environment_service.release_session_lease(
        lease.id,
        lease_token=lease.lease_token,
        reason="simulate service restart",
        release_status="expired",
        validate_token=False,
    )
    blocked = environment_service.get_session_detail(lease.id, limit=5) or {}
    assert blocked["host_twin_summary"]["host_companion_status"] == "detached"

    browser_runtime = BrowserRuntimeService(SQLiteStateStore(tmp_path / "browser.sqlite3"))
    setattr(browser_runtime, "_environment_service", environment_service)

    async def fake_browser_use(**kwargs):
        return _json_response({"ok": True, "message": "started"})

    monkeypatch.setattr(browser_runtime_module, "browser_use", fake_browser_use)
    monkeypatch.setattr(
        browser_runtime_module,
        "get_browser_runtime_snapshot",
        lambda: {
            "running": True,
            "current_session_id": "restart-browser-session",
            "session_count": 1,
            "sessions": [
                {
                    "session_id": "restart-browser-session",
                    "page_count": 1,
                    "page_ids": ["restart-browser-session"],
                },
            ],
        },
    )

    result = asyncio.run(
        browser_runtime.start_session(
            BrowserSessionStartOptions(
                session_id="restart-browser-session",
                reuse_running_session=False,
                session_mount_id=lease.id,
            ),
        ),
    )

    resumed = environment_service.get_session_detail(lease.id, limit=5) or {}
    persisted_session = session_repo.get_session(lease.id)

    assert result["status"] == "started"
    assert persisted_session is not None
    assert persisted_session.lease_status == "leased"
    assert persisted_session.live_handle_ref is not None
    assert resumed["host_twin_summary"]["host_companion_status"] == "attached"
