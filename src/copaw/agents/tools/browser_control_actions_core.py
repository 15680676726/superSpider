# -*- coding: utf-8 -*-
from __future__ import annotations

from .browser_control_shared import *  # noqa: F401,F403


def _get_page(page_id: str, session_id: str | None = None):
    """Return page for page_id or None if not found."""
    return _session_bucket("pages", session_id).get(page_id)


def _get_refs(page_id: str, session_id: str | None = None) -> dict[str, dict]:
    """Return refs map for page_id (ref -> {role, name?, nth?})."""
    return _session_bucket("refs", session_id, create=True).setdefault(page_id, {})


def _get_root(page, _page_id: str, frame_selector: str = ""):
    """Return page or frame for frame_selector (ref/selector)."""
    if not (frame_selector and frame_selector.strip()):
        return page
    return page.frame_locator(frame_selector.strip())


def _get_locator_by_ref(
    page,
    page_id: str,
    ref: str,
    frame_selector: str = "",
    session_id: str | None = None,
):
    """Resolve snapshot ref to locator; frame_selector for iframe."""
    refs = _get_refs(page_id, session_id)
    info = refs.get(ref)
    if not info:
        return None
    role = info.get("role", "generic")
    name = info.get("name")
    nth = info.get("nth", 0)
    root = _get_root(page, page_id, frame_selector)
    locator = root.get_by_role(role, name=name or None)
    if nth is not None and nth > 0:
        locator = locator.nth(nth)
    return locator


def _attach_page_listeners(page, page_id: str, session_id: str) -> None:
    """Attach console and request listeners for a page."""
    logs = _session_bucket("console_logs", session_id, create=True).setdefault(page_id, [])

    def on_console(msg):
        logs.append({"level": msg.type, "text": msg.text})

    page.on("console", on_console)
    requests_list = _session_bucket(
        "network_requests",
        session_id,
        create=True,
    ).setdefault(page_id, [])

    def on_request(req):
        requests_list.append(
            {
                "url": req.url,
                "method": req.method,
                "resourceType": getattr(req, "resource_type", None),
            },
        )

    def on_response(res):
        for r in requests_list:
            if r.get("url") == res.url and "status" not in r:
                r["status"] = res.status
                break

    page.on("request", on_request)
    page.on("response", on_response)
    dialogs = _session_bucket("pending_dialogs", session_id, create=True).setdefault(
        page_id,
        [],
    )

    def on_dialog(dialog):
        dialogs.append(dialog)

    page.on("dialog", on_dialog)
    choosers = _session_bucket(
        "pending_file_choosers",
        session_id,
        create=True,
    ).setdefault(page_id, [])

    def on_filechooser(chooser):
        choosers.append(chooser)

    page.on("filechooser", on_filechooser)


def _next_page_id(session_id: str | None = None) -> str:
    """Return a unique page_id (page_N).
    Uses monotonic counter so IDs are not reused after close."""
    session = _get_session_state(session_id, create=True)
    if not isinstance(session, dict):
        return "page_1"
    session["page_counter"] = int(session.get("page_counter", 0) or 0) + 1
    return f"page_{session['page_counter']}"


def _attach_context_listeners(context, session_id: str) -> None:
    """When the page opens a new tab (e.g. target=_blank, window.open),
    register it and set as current."""

    def on_page(page):
        session = _get_session_state(session_id, create=True)
        new_id = _next_page_id(session_id)
        _session_bucket("refs", session_id, create=True)[new_id] = {}
        _session_bucket("console_logs", session_id, create=True)[new_id] = []
        _session_bucket("network_requests", session_id, create=True)[new_id] = []
        _session_bucket("pending_dialogs", session_id, create=True)[new_id] = []
        _session_bucket("pending_file_choosers", session_id, create=True)[new_id] = []
        _attach_page_listeners(page, new_id, session_id)
        _session_bucket("pages", session_id, create=True)[new_id] = page
        if isinstance(session, dict):
            session["current_page_id"] = new_id
        _state["current_session_id"] = session_id
        logger.debug(
            "New tab opened by page, registered as page_id=%s in session=%s",
            new_id,
            session_id,
        )

    context.on("page", on_page)


async def _create_browser_context(storage_state_path: str = ""):
    context_kwargs: dict[str, Any] = {}
    if storage_state_path and os.path.exists(storage_state_path):
        context_kwargs["storage_state"] = storage_state_path
    if _USE_SYNC_PLAYWRIGHT:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _get_executor(),
            lambda: _state["_sync_browser"].new_context(**context_kwargs),
        )
    return await _state["browser"].new_context(**context_kwargs)


async def _ensure_browser_session(
    session_id: str,
    *,
    profile_id: str | None = None,
    entry_url: str | None = None,
    persist_login_state: bool | None = None,
    storage_state_path: str | None = None,
    navigation_guard: dict[str, Any] | None = None,
    action_timeout_seconds: float | None = None,
) -> dict[str, Any] | None:
    if not await _ensure_browser():
        return None
    session = _get_session_state(session_id, create=True)
    if not isinstance(session, dict):
        return None
    if session.get("context") is None:
        context = await _create_browser_context(storage_state_path)
        _attach_context_listeners(context, session_id)
        session["context"] = context
    if profile_id:
        session["profile_id"] = profile_id
    session["browser_mode"] = "managed-isolated"
    if entry_url:
        session["entry_url"] = entry_url
    if navigation_guard is not None:
        session["navigation_guard"] = _normalize_navigation_guard(navigation_guard)
    if action_timeout_seconds is not None:
        session["action_timeout_seconds"] = _normalize_positive_timeout(action_timeout_seconds)
    if persist_login_state is not None:
        session["persist_login_state"] = bool(persist_login_state)
    if storage_state_path is not None:
        session["storage_state_path"] = storage_state_path or ""
    _state["current_session_id"] = session_id
    _touch_activity(session_id)
    return session


async def _persist_session_storage(session: dict[str, Any]) -> None:
    context = session.get("context")
    storage_state_path = str(session.get("storage_state_path") or "").strip()
    if context is None or not session.get("persist_login_state") or not storage_state_path:
        return
    directory = os.path.dirname(storage_state_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if _USE_SYNC_PLAYWRIGHT:
        await _run_sync(context.storage_state, path=storage_state_path)
    else:
        await context.storage_state(path=storage_state_path)


async def _close_session_context(session_id: str) -> bool:
    session = _get_session_state(session_id)
    if not isinstance(session, dict):
        return False
    context = session.get("context")
    if context is None:
        _state.setdefault("sessions", {}).pop(session_id, None)
        if _state.get("current_session_id") == session_id:
            _state["current_session_id"] = _current_session_id()
        return False
    await _persist_session_storage(session)
    if _USE_SYNC_PLAYWRIGHT:
        await _run_sync(context.close)
    else:
        await context.close()
    _state.setdefault("sessions", {}).pop(session_id, None)
    if _state.get("current_session_id") == session_id:
        _state["current_session_id"] = _current_session_id()
    return True


async def _ensure_browser() -> bool:  # pylint: disable=too-many-branches
    """Start browser if not running. Return True if ready, False on failure."""
    # Check browser state based on mode
    if _USE_SYNC_PLAYWRIGHT:
        if _state["_sync_browser"] is not None:
            _touch_activity()
            return True
    else:
        if _state["browser"] is not None:
            _touch_activity()
            return True

    try:
        if _USE_SYNC_PLAYWRIGHT:
            # Hybrid mode: use sync Playwright in thread pool
            loop = asyncio.get_event_loop()
            pw, browser, context = await loop.run_in_executor(
                _get_executor(),
                lambda: _sync_browser_launch(_state["headless"]),
            )
            _state["_sync_playwright"] = pw
            _state["_sync_browser"] = browser
            _state["_sync_context"] = context
            try:
                context.close()
            except Exception:
                pass
            _state["_sync_context"] = None
        else:
            # Standard mode: use async Playwright
            async_playwright = _ensure_playwright_async()
            pw = await async_playwright().start()
            # Prefer OS default browser when available (e.g. user's default Chrome/Safari).
            use_default = not is_running_in_container() and os.environ.get(
                "COPAW_BROWSER_USE_DEFAULT",
                "1",
            ).strip().lower() in ("1", "true", "yes")
            default_kind, default_path = (
                get_system_default_browser() if use_default else (None, None)
            )
            exe: Optional[str] = None
            if default_kind == "chromium" and default_path:
                exe = default_path
            elif default_kind != "webkit":
                exe = _chromium_executable_path()
            if exe:
                # System Chrome/Edge/Chromium (default or discovered)
                launch_kwargs: dict[str, Any] = {
                    "headless": _state["headless"],
                }
                extra_args = _chromium_launch_args()
                if extra_args:
                    launch_kwargs["args"] = extra_args
                launch_kwargs["executable_path"] = exe
                pw_browser = await pw.chromium.launch(**launch_kwargs)
            elif default_kind == "webkit" or sys.platform == "darwin":
                # macOS: default Safari or no Chromium → use WebKit (Safari)
                pw_browser = await pw.webkit.launch(
                    headless=_state["headless"],
                )
            else:
                # Windows/Linux without system Chromium → Playwright's Chromium
                launch_kwargs = {"headless": _state["headless"]}
                extra_args = _chromium_launch_args()
                if extra_args:
                    launch_kwargs["args"] = extra_args
                pw_browser = await pw.chromium.launch(**launch_kwargs)
            _state["playwright"] = pw
            _state["browser"] = pw_browser
            _state["context"] = None
        _state["_last_browser_error"] = None
        _touch_activity()
        _start_idle_watchdog()
        return True
    except Exception as e:
        _state["_last_browser_error"] = str(e)
        return False


def _start_idle_watchdog() -> None:
    """Cancel any existing idle watchdog and start a fresh one."""
    old_task = _state.get("_idle_task")
    if old_task and not old_task.done():
        old_task.cancel()
    _state["_idle_task"] = asyncio.ensure_future(_idle_watchdog())


def _cancel_idle_watchdog() -> None:
    """Cancel the idle watchdog, if running."""
    task = _state.get("_idle_task")
    if task and not task.done():
        task.cancel()
    _state["_idle_task"] = None


# pylint: disable=R0912,R0915
async def _action_start(
    headed: bool = True,
    session_id: str = "default",
    profile_id: str = "",
    entry_url: str = "",
    persist_login_state: bool = False,
    storage_state_path: str = "",
    navigation_guard_json: str = "",
    action_timeout_seconds: float = 0,
) -> ToolResponse:
    # Check browser state based on mode
    if _USE_SYNC_PLAYWRIGHT:
        browser_exists = _state["_sync_browser"] is not None
        current_headless = not _state.get("_sync_headless", True)
    else:
        browser_exists = _state["browser"] is not None
        current_headless = _state["headless"]

    # Keep the current browser mode stable within a live session.
    if browser_exists:
        requested_headless = not headed
        if requested_headless != _state["headless"] and _list_session_ids():
            return _tool_response(
                json.dumps(
                    {
                        "ok": False,
                        "error": (
                            "Browser is already running in a different headed mode. "
                            "Stop active browser sessions before switching mode."
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
    # Default to a visible local browser unless headless mode is explicitly requested.
    _state["headless"] = not headed
    navigation_guard = _normalize_navigation_guard(
        _parse_json_param(navigation_guard_json, {}),
    )

    try:
        if not await _ensure_browser_session(
            session_id,
            profile_id=profile_id,
            entry_url=entry_url,
            persist_login_state=persist_login_state,
            storage_state_path=storage_state_path,
            navigation_guard=navigation_guard,
            action_timeout_seconds=action_timeout_seconds,
        ):
            raise RuntimeError(_state.get("_last_browser_error") or "Browser start failed")
        _state["_sync_headless"] = not headed
        if entry_url.strip():
            current_session = _get_session_state(session_id)
            if isinstance(current_session, dict) and not dict(current_session.get("pages") or {}):
                opened = await _action_open(entry_url, "default", session_id)
                payload = _parse_tool_response_json(opened)
                if not payload.get("ok"):
                    return opened
        _touch_activity(session_id)
        _start_idle_watchdog()
        msg = (
            "Browser session started (visible window)"
            if not _state["headless"]
            else "Browser session started"
        )
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": msg,
                    "session_id": session_id,
                    "profile_id": profile_id or None,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Browser start failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_stop(session_id: str | None = None) -> ToolResponse:
    _cancel_idle_watchdog()

    # Check browser state based on mode
    if not _is_browser_running():
        return _tool_response(
            json.dumps(
                {"ok": True, "message": "Browser not running"},
                ensure_ascii=False,
                indent=2,
            ),
        )

    reset_runtime = False
    try:
        target_session_id = str(session_id or "").strip() or None
        if target_session_id is not None:
            await _close_session_context(target_session_id)
        else:
            for active_session_id in list(_list_session_ids()):
                await _close_session_context(active_session_id)
        if _list_session_ids():
            _start_idle_watchdog()
            return _tool_response(
                json.dumps(
                    {
                        "ok": True,
                        "message": "Browser session stopped",
                        "session_id": target_session_id,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        if _USE_SYNC_PLAYWRIGHT:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                _get_executor(),
                _sync_browser_close,
            )
        else:
            if _state["browser"] is not None:
                await _state["browser"].close()
            if _state["playwright"] is not None:
                await _state["playwright"].stop()
        reset_runtime = True
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Browser stop failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    finally:
        if reset_runtime:
            try:
                _reset_browser_state()
            except Exception:
                pass

    return _tool_response(
        json.dumps(
            {"ok": True, "message": "Browser stopped"},
            ensure_ascii=False,
            indent=2,
        ),
    )


async def _action_open(url: str, page_id: str, session_id: str) -> ToolResponse:
    url = (url or "").strip()
    if not url:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "url required for open"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    guardrail_violation = _navigation_guard_violation(url, session_id)
    if guardrail_violation is not None:
        return _tool_response(
            json.dumps(
                {
                    "ok": False,
                    "error": guardrail_violation["error"],
                    "guardrail": guardrail_violation["guardrail"],
                    "url": url,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    if not await _ensure_browser():
        err = _state.get("_last_browser_error") or "Browser not started"
        return _tool_response(
            json.dumps(
                {"ok": False, "error": err},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        session = await _ensure_browser_session(session_id)
        if not isinstance(session, dict) or session.get("context") is None:
            raise RuntimeError(_state.get("_last_browser_error") or "Browser not started")
        if _USE_SYNC_PLAYWRIGHT:
            loop = asyncio.get_event_loop()
            page = await loop.run_in_executor(
                _get_executor(),
                lambda: session["context"].new_page(),
            )
        else:
            page = await session["context"].new_page()

        _session_bucket("refs", session_id, create=True)[page_id] = {}
        _session_bucket("console_logs", session_id, create=True)[page_id] = []
        _session_bucket("network_requests", session_id, create=True)[page_id] = []
        _session_bucket("pending_dialogs", session_id, create=True)[page_id] = []
        _session_bucket("pending_file_choosers", session_id, create=True)[page_id] = []
        _attach_page_listeners(page, page_id, session_id)

        if _USE_SYNC_PLAYWRIGHT:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                _get_executor(),
                lambda: page.goto(url),
            )
        else:
            await page.goto(url)

        _session_bucket("pages", session_id, create=True)[page_id] = page
        _set_current_page_id(page_id, session_id)
        _state["current_session_id"] = session_id
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Opened {url}",
                    "page_id": page_id,
                    "url": url,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Open failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_navigate(url: str, page_id: str, session_id: str) -> ToolResponse:
    url = (url or "").strip()
    if not url:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "url required for navigate"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    guardrail_violation = _navigation_guard_violation(url, session_id)
    if guardrail_violation is not None:
        return _tool_response(
            json.dumps(
                {
                    "ok": False,
                    "error": guardrail_violation["error"],
                    "guardrail": guardrail_violation["guardrail"],
                    "url": url,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                _get_executor(),
                lambda: page.goto(url),
            )
        else:
            await page.goto(url)
        _set_current_page_id(page_id, session_id)
        _state["current_session_id"] = session_id
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Navigated to {url}",
                    "url": page.url,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Navigate failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_screenshot(
    page_id: str,
    path: str,
    full_page: bool,
    screenshot_type: str = "png",
    ref: str = "",
    element: str = "",  # pylint: disable=unused-argument
    frame_selector: str = "",
    session_id: str = "default",
) -> ToolResponse:
    path = (path or "").strip()
    if not path:
        ext = "jpeg" if screenshot_type == "jpeg" else "png"
        path = f"page-{int(time.time())}.{ext}"
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if ref and ref.strip():
            locator = _get_locator_by_ref(
                page,
                page_id,
                ref.strip(),
                frame_selector,
                session_id,
            )
            if locator is None:
                return _tool_response(
                    json.dumps(
                        {"ok": False, "error": f"Unknown ref: {ref}"},
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            if _USE_SYNC_PLAYWRIGHT:
                await _run_sync(
                    locator.screenshot,
                    path=path,
                    type=screenshot_type
                    if screenshot_type == "jpeg"
                    else "png",
                )
            else:
                await locator.screenshot(
                    path=path,
                    type=screenshot_type
                    if screenshot_type == "jpeg"
                    else "png",
                )
        else:
            if frame_selector and frame_selector.strip():
                root = _get_root(page, page_id, frame_selector)
                locator = root.locator("body").first
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(
                        locator.screenshot,
                        path=path,
                        type=screenshot_type
                        if screenshot_type == "jpeg"
                        else "png",
                    )
                else:
                    await locator.screenshot(
                        path=path,
                        type=screenshot_type
                        if screenshot_type == "jpeg"
                        else "png",
                    )
            else:
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(
                        page.screenshot,
                        path=path,
                        full_page=full_page,
                        type=screenshot_type
                        if screenshot_type == "jpeg"
                        else "png",
                    )
                else:
                    await page.screenshot(
                        path=path,
                        full_page=full_page,
                        type=screenshot_type
                        if screenshot_type == "jpeg"
                        else "png",
                    )
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Screenshot saved to {path}",
                    "path": path,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Screenshot failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_click(  # pylint: disable=too-many-branches
    page_id: str,
    selector: str,
    ref: str = "",
    element: str = "",  # pylint: disable=unused-argument
    wait: int = 0,
    double_click: bool = False,
    button: str = "left",
    modifiers_json: str = "",
    frame_selector: str = "",
    session_id: str = "default",
) -> ToolResponse:
    ref = (ref or "").strip()
    selector = (selector or "").strip()
    if not ref and not selector:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "selector or ref required for click"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        mods = _parse_json_param(modifiers_json, [])
        if not isinstance(mods, list):
            mods = []
        kwargs = {
            "button": button
            if button in ("left", "right", "middle")
            else "left",
        }
        if mods:
            kwargs["modifiers"] = [
                m
                for m in mods
                if m in ("Alt", "Control", "ControlOrMeta", "Meta", "Shift")
            ]

        if _USE_SYNC_PLAYWRIGHT:
            loop = asyncio.get_event_loop()
            if ref:
                locator = _get_locator_by_ref(
                    page,
                    page_id,
                    ref,
                    frame_selector,
                    session_id,
                )
                if locator is None:
                    return _tool_response(
                        json.dumps(
                            {"ok": False, "error": f"Unknown ref: {ref}"},
                            ensure_ascii=False,
                            indent=2,
                        ),
                    )
                if double_click:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.dblclick(**kwargs),
                    )
                else:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.click(**kwargs),
                    )
            else:
                root = _get_root(page, page_id, frame_selector)
                locator = root.locator(selector).first
                if double_click:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.dblclick(**kwargs),
                    )
                else:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.click(**kwargs),
                    )
        else:
            # Standard async mode
            if ref:
                locator = _get_locator_by_ref(
                    page,
                    page_id,
                    ref,
                    frame_selector,
                    session_id,
                )
                if locator is None:
                    return _tool_response(
                        json.dumps(
                            {"ok": False, "error": f"Unknown ref: {ref}"},
                            ensure_ascii=False,
                            indent=2,
                        ),
                    )
                if double_click:
                    await locator.dblclick(**kwargs)
                else:
                    await locator.click(**kwargs)
            else:
                root = _get_root(page, page_id, frame_selector)
                locator = root.locator(selector).first
                if double_click:
                    await locator.dblclick(**kwargs)
                else:
                    await locator.click(**kwargs)

        if wait > 0:
            await asyncio.sleep(wait / 1000.0)
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Clicked {ref or selector}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Click failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_type(
    page_id: str,
    selector: str,
    ref: str = "",
    element: str = "",  # pylint: disable=unused-argument
    text: str = "",
    submit: bool = False,
    slowly: bool = False,
    frame_selector: str = "",
    session_id: str = "default",
) -> ToolResponse:
    ref = (ref or "").strip()
    selector = (selector or "").strip()
    if not ref and not selector:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "selector or ref required for type"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if ref:
            locator = _get_locator_by_ref(
                page,
                page_id,
                ref,
                frame_selector,
                session_id,
            )
            if locator is None:
                return _tool_response(
                    json.dumps(
                        {"ok": False, "error": f"Unknown ref: {ref}"},
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            if _USE_SYNC_PLAYWRIGHT:
                loop = asyncio.get_event_loop()
                if slowly:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.press_sequentially(text or ""),
                    )
                else:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.fill(text or ""),
                    )
                if submit:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: locator.press("Enter"),
                    )
            else:
                if slowly:
                    await locator.press_sequentially(text or "")
                else:
                    await locator.fill(text or "")
                if submit:
                    await locator.press("Enter")
        else:
            root = _get_root(page, page_id, frame_selector)
            loc = root.locator(selector).first
            if _USE_SYNC_PLAYWRIGHT:
                loop = asyncio.get_event_loop()
                if slowly:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: loc.press_sequentially(text or ""),
                    )
                else:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: loc.fill(text or ""),
                    )
                if submit:
                    await loop.run_in_executor(
                        _get_executor(),
                        lambda: loc.press("Enter"),
                    )
            else:
                if slowly:
                    await loc.press_sequentially(text or "")
                else:
                    await loc.fill(text or "")
                if submit:
                    await loc.press("Enter")
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Typed into {ref or selector}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Type failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_eval(
    page_id: str,
    code: str,
    session_id: str = "default",
) -> ToolResponse:
    code = (code or "").strip()
    if not code:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "code required for eval"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if code.strip().startswith("(") or code.strip().startswith("function"):
            if _USE_SYNC_PLAYWRIGHT:
                result = await _run_sync(page.evaluate, code)
            else:
                result = await page.evaluate(code)
        else:
            if _USE_SYNC_PLAYWRIGHT:
                result = await _run_sync(
                    page.evaluate,
                    f"() => {{ return ({code}); }}",
                )
            else:
                result = await page.evaluate(f"() => {{ return ({code}); }}")
        _touch_activity(session_id)
        try:
            out = json.dumps(
                {"ok": True, "result": result},
                ensure_ascii=False,
                indent=2,
            )
        except TypeError:
            out = json.dumps(
                {"ok": True, "result": str(result)},
                ensure_ascii=False,
                indent=2,
            )
        return _tool_response(out)
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Eval failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_pdf(
    page_id: str,
    path: str,
    session_id: str = "default",
) -> ToolResponse:
    path = (path or "page.pdf").strip() or "page.pdf"
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(page.pdf, path=path)
        else:
            await page.pdf(path=path)
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"PDF saved to {path}", "path": path},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"PDF failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_close(page_id: str, session_id: str = "default") -> ToolResponse:
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(page.close)
        else:
            await page.close()
        _session_bucket("pages", session_id).pop(page_id, None)
        for key in (
            "refs",
            "refs_frame",
            "console_logs",
            "network_requests",
            "pending_dialogs",
            "pending_file_choosers",
        ):
            _session_bucket(key, session_id).pop(page_id, None)
        if _current_page_id(session_id) == page_id:
            remaining = list(_session_bucket("pages", session_id).keys())
            _set_current_page_id(remaining[0] if remaining else None, session_id)
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Closed page '{page_id}'"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Close failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )



__all__ = [name for name in globals() if not name.startswith("__")]
