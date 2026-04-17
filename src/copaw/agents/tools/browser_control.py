# -*- coding: utf-8 -*-
from __future__ import annotations

import atexit
import asyncio
import sys
import threading
from typing import Any

from . import browser_control_actions_core as browser_control_actions_core_module
from .browser_control_shared import *  # noqa: F401,F403
from .browser_control_actions_core import *  # noqa: F401,F403
from .browser_control_actions_extended import *  # noqa: F401,F403
from ...environments.lease_service import (
    publish_browser_operator_abort_guardrail_block,
    resolve_operator_abort_binding_for_runtime_session,
)


_ORIGINAL_ATTACH_PAGE_LISTENERS = browser_control_actions_core_module._attach_page_listeners
_OPERATOR_ABORT_EXEMPT_ACTIONS = frozenset({"stop"})
_TIMEOUT_EXEMPT_ACTIONS = frozenset({"stop", "wait_for"})


def _attach_page_listeners_with_downloads(page, page_id: str, session_id: str) -> None:
    _ORIGINAL_ATTACH_PAGE_LISTENERS(page, page_id, session_id)
    _attach_download_listener(page, page_id, session_id)


if browser_control_actions_core_module._attach_page_listeners is not _attach_page_listeners_with_downloads:
    browser_control_actions_core_module._attach_page_listeners = _attach_page_listeners_with_downloads


_SYNC_BRIDGE_LOOP: asyncio.AbstractEventLoop | None = None
_SYNC_BRIDGE_THREAD: threading.Thread | None = None
_SYNC_BRIDGE_READY = threading.Event()
_SYNC_BRIDGE_LOCK = threading.Lock()


def _create_sync_bridge_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32" and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        policy = asyncio.get_event_loop_policy()
        if isinstance(policy, asyncio.WindowsSelectorEventLoopPolicy):
            return asyncio.WindowsProactorEventLoopPolicy().new_event_loop()
    return asyncio.new_event_loop()


def _run_sync_bridge_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    _SYNC_BRIDGE_READY.set()
    loop.run_forever()
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


def _get_sync_bridge_loop() -> asyncio.AbstractEventLoop:
    global _SYNC_BRIDGE_LOOP, _SYNC_BRIDGE_THREAD
    with _SYNC_BRIDGE_LOCK:
        if (
            _SYNC_BRIDGE_LOOP is not None
            and _SYNC_BRIDGE_THREAD is not None
            and _SYNC_BRIDGE_THREAD.is_alive()
            and not _SYNC_BRIDGE_LOOP.is_closed()
        ):
            return _SYNC_BRIDGE_LOOP
        _SYNC_BRIDGE_READY.clear()
        loop = _create_sync_bridge_loop()
        thread = threading.Thread(
            target=_run_sync_bridge_loop,
            args=(loop,),
            name="browser-use-json-loop",
            daemon=True,
        )
        _SYNC_BRIDGE_LOOP = loop
        _SYNC_BRIDGE_THREAD = thread
        thread.start()
    _SYNC_BRIDGE_READY.wait(timeout=5)
    return loop


def _run_browser_use_json_sync(coro: Any) -> ToolResponse:
    loop = _get_sync_bridge_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def _shutdown_sync_bridge_loop() -> None:
    global _SYNC_BRIDGE_LOOP, _SYNC_BRIDGE_THREAD
    with _SYNC_BRIDGE_LOCK:
        loop = _SYNC_BRIDGE_LOOP
        thread = _SYNC_BRIDGE_THREAD
        _SYNC_BRIDGE_LOOP = None
        _SYNC_BRIDGE_THREAD = None
    if loop is None or loop.is_closed():
        return
    if _is_browser_running():
        try:
            future = asyncio.run_coroutine_threadsafe(_action_stop(), loop)
            future.result(timeout=5)
        except Exception:
            pass
    loop.call_soon_threadsafe(loop.stop)
    if thread is not None and thread.is_alive():
        thread.join(timeout=1)


atexit.register(_shutdown_sync_bridge_loop)


def run_browser_use_json(**payload: Any) -> dict[str, Any]:
    async def _invoke() -> ToolResponse:
        return await browser_use(**payload)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        response = _run_browser_use_json_sync(_invoke())
        return _parse_tool_response_json(response)

    response = _run_browser_use_json_sync(_invoke())
    return _parse_tool_response_json(response)


def list_browser_downloads(
    *,
    session_id: str | None = None,
    page_id: str | None = None,
) -> list[dict[str, Any]]:
    downloads = _session_download_records(session_id)
    if page_id is None:
        return list(downloads)
    normalized_page_id = str(page_id).strip()
    return [
        item
        for item in downloads
        if str(item.get("page_id") or "").strip() == normalized_page_id
    ]


async def browser_use(  # pylint: disable=R0911,R0912
    action: str,
    url: str = "",
    page_id: str = "default",
    session_id: str = "",
    selector: str = "",
    text: str = "",
    code: str = "",
    path: str = "",
    wait: int = 0,
    full_page: bool = False,
    width: int = 0,
    height: int = 0,
    level: str = "info",
    filename: str = "",
    accept: bool = True,
    prompt_text: str = "",
    ref: str = "",
    element: str = "",
    paths_json: str = "",
    fields_json: str = "",
    key: str = "",
    submit: bool = False,
    slowly: bool = False,
    include_static: bool = False,
    screenshot_type: str = "png",
    snapshot_filename: str = "",
    double_click: bool = False,
    button: str = "left",
    modifiers_json: str = "",
    start_ref: str = "",
    end_ref: str = "",
    start_selector: str = "",
    end_selector: str = "",
    start_element: str = "",
    end_element: str = "",
    values_json: str = "",
    tab_action: str = "",
    index: int = -1,
    wait_time: float = 0,
    text_gone: str = "",
    frame_selector: str = "",
    headed: bool = True,
    profile_id: str = "",
    entry_url: str = "",
    persist_login_state: bool = False,
    storage_state_path: str = "",
    navigation_guard_json: str = "",
    action_timeout_seconds: float = 0,
) -> ToolResponse:
    """Control browser (Playwright). Default opens a visible browser window.
    Set headed=False with action=start to force background headless mode. Flow:
    start, open(url),
    snapshot to get refs, then click/type etc. with ref or selector. Use
    page_id for multiple tabs.

    Args:
        action (str):
            Required. Action type. Values: start, stop, open, navigate,
            navigate_back, snapshot, screenshot, click, type, eval, evaluate,
            resize, console_messages, network_requests, handle_dialog,
            file_upload, fill_form, install, press_key, run_code, drag, hover,
            select_option, tabs, wait_for, pdf, close.
        url (str):
            URL to open. Required for action=open or navigate.
        page_id (str):
            Page/tab identifier, default "default". Use different page_id for
            multiple tabs.
        selector (str):
            CSS selector to locate element for click/type/hover etc. Prefer
            ref when available.
        text (str):
            Text to type. Required for action=type.
        code (str):
            JavaScript code. Required for action=eval, evaluate, or run_code.
        path (str):
            File path for screenshot save or PDF export.
        wait (int):
            Milliseconds to wait after click. Used with action=click.
        full_page (bool):
            Whether to capture full page. Used with action=screenshot.
        width (int):
            Viewport width in pixels. Used with action=resize.
        height (int):
            Viewport height in pixels. Used with action=resize.
        level (str):
            Console log level filter, e.g. "info" or "error". Used with
            action=console_messages.
        filename (str):
            Filename for saving logs or screenshot. Used with
            console_messages, network_requests, screenshot.
        accept (bool):
            Whether to accept dialog (true) or dismiss (false). Used with
            action=handle_dialog.
        prompt_text (str):
            Input for prompt dialog. Used with action=handle_dialog when
            dialog is prompt.
        ref (str):
            Element ref from snapshot output; use for stable targeting. Prefer
            ref for click/type/hover/screenshot/evaluate/select_option.
        element (str):
            Element description for evaluate etc. Prefer ref when available.
        paths_json (str):
            JSON array string of file paths. Used with action=file_upload.
        fields_json (str):
            JSON object string of form field name to value. Used with
            action=fill_form.
        key (str):
            Key name, e.g. "Enter", "Control+a". Required for
            action=press_key.
        submit (bool):
            Whether to submit (press Enter) after typing. Used with
            action=type.
        slowly (bool):
            Whether to type character by character. Used with action=type.
        include_static (bool):
            Whether to include static resource requests. Used with
            action=network_requests.
        screenshot_type (str):
            Screenshot format, "png" or "jpeg". Used with action=screenshot.
        snapshot_filename (str):
            File path to save snapshot output. Used with action=snapshot.
        double_click (bool):
            Whether to double-click. Used with action=click.
        button (str):
            Mouse button: "left", "right", or "middle". Used with
            action=click.
        modifiers_json (str):
            JSON array of modifier keys, e.g. ["Shift","Control"]. Used with
            action=click.
        start_ref (str):
            Drag start element ref. Used with action=drag.
        end_ref (str):
            Drag end element ref. Used with action=drag.
        start_selector (str):
            Drag start CSS selector. Used with action=drag.
        end_selector (str):
            Drag end CSS selector. Used with action=drag.
        start_element (str):
            Drag start element description. Used with action=drag.
        end_element (str):
            Drag end element description. Used with action=drag.
        values_json (str):
            JSON of option value(s) for select. Used with
            action=select_option.
        tab_action (str):
            Tab action: list, new, close, or select. Required for
            action=tabs.
        index (int):
            Tab index for tabs select, zero-based. Used with action=tabs.
        wait_time (float):
            Seconds to wait. Used with action=wait_for.
        text_gone (str):
            Wait until this text disappears from page. Used with
            action=wait_for.
        frame_selector (str):
            iframe selector, e.g. "iframe#main". Set when operating inside
            that iframe in snapshot/click/type etc.
        headed (bool):
            When True with action=start, launch a visible browser window
            (non-headless). User can see the real browser. Default True.
    """
    action = (action or "").strip().lower()
    if not action:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "action required"},
                ensure_ascii=False,
                indent=2,
            ),
        )

    raw_session_id = str(session_id or "").strip()
    resolved_session_id = _normalize_session_id(raw_session_id)
    page_id = (page_id or "default").strip() or "default"
    current = _current_page_id(resolved_session_id)
    pages = _session_bucket("pages", resolved_session_id)
    if page_id == "default" and current and current in pages:
        page_id = current
    if action != "stop":
        _state["current_session_id"] = resolved_session_id

    should_emit_evidence = action in _BROWSER_EVIDENCE_ACTIONS
    started_at = _utc_now() if should_emit_evidence else None
    evidence_metadata = {
        "session_id": resolved_session_id,
        "ref": ref or None,
        "selector": selector or None,
        "path": (path or filename) or None,
        "fields_count": (
            len(_parse_json_param(fields_json, []))
            if action == "fill_form"
            else None
        ),
        "upload_paths": (
            _parse_json_param(paths_json, [])
            if action == "file_upload"
            else None
        ),
        "tab_action": tab_action if action == "tabs" else None,
        "tab_index": index if action == "tabs" else None,
        "full_page": full_page if action in {"screenshot", "take_screenshot"} else None,
        "button": button if action == "click" else None,
    }

    async def _with_evidence(response: ToolResponse) -> ToolResponse:
        if not should_emit_evidence or started_at is None:
            return response
        await _emit_browser_action_evidence(
            action=action,
            page_id=page_id,
            response=response,
            started_at=started_at,
            url=(
                url.strip()
                if url and action in {"open", "navigate"}
                else _invoke_browser_helper(
                    _current_page_url,
                    page_id,
                    resolved_session_id,
                )
            ),
            metadata=dict(evidence_metadata),
        )
        return response

    resolved_timeout_seconds = (
        _normalize_positive_timeout(action_timeout_seconds)
        or (
            None
            if action in _TIMEOUT_EXEMPT_ACTIONS
            else _session_action_timeout_seconds(resolved_session_id)
        )
    )

    async def _invoke_action(
        handler,
        *handler_args,
        emit_evidence: bool = False,
        **handler_kwargs,
    ) -> ToolResponse:
        try:
            if resolved_timeout_seconds is not None and action not in _TIMEOUT_EXEMPT_ACTIONS:
                response = await asyncio.wait_for(
                    _invoke_browser_handler(
                        handler,
                        *handler_args,
                        **handler_kwargs,
                    ),
                    timeout=resolved_timeout_seconds,
                )
            else:
                response = await _invoke_browser_handler(
                    handler,
                    *handler_args,
                    **handler_kwargs,
                )
        except asyncio.TimeoutError:
            response = _tool_response(
                json.dumps(
                    {
                        "ok": False,
                        "error": (
                            f"Browser action timed out after {resolved_timeout_seconds:.2f}s."
                        ),
                        "guardrail": {
                            "kind": "timeout",
                            "timeout_seconds": resolved_timeout_seconds,
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        if emit_evidence:
            return await _with_evidence(response)
        return response

    if action not in _OPERATOR_ABORT_EXEMPT_ACTIONS:
        abort_binding = resolve_operator_abort_binding_for_runtime_session(
            resolved_session_id,
        )
        if bool(abort_binding.get("requested")):
            reason = str(
                abort_binding.get("reason")
                or abort_binding.get("channel")
                or "operator abort",
            ).strip()
            evidence_metadata["guardrail"] = {
                "kind": "operator-abort",
                "reason": reason,
            }
            if abort_binding.get("session_mount_id") is not None:
                evidence_metadata["session_mount_id"] = abort_binding["session_mount_id"]
            if abort_binding.get("environment_id") is not None:
                evidence_metadata["environment_id"] = abort_binding["environment_id"]
            publish_browser_operator_abort_guardrail_block(
                resolved_session_id,
                action=action,
                reason=reason,
            )
            blocked_payload: dict[str, object] = {
                "ok": False,
                "error": "Browser action blocked: operator abort is pending.",
                "guardrail": dict(evidence_metadata["guardrail"]),
            }
            if abort_binding.get("session_mount_id") is not None:
                blocked_payload["session_mount_id"] = abort_binding["session_mount_id"]
            if abort_binding.get("environment_id") is not None:
                blocked_payload["environment_id"] = abort_binding["environment_id"]
            return await _with_evidence(
                _tool_response(
                    json.dumps(
                        blocked_payload,
                        ensure_ascii=False,
                        indent=2,
                    ),
                ),
            )

    try:
        if action == "start":
            return await _invoke_action(
                _action_start,
                headed=headed,
                session_id=resolved_session_id,
                profile_id=profile_id,
                entry_url=entry_url,
                persist_login_state=persist_login_state,
                storage_state_path=storage_state_path,
                navigation_guard_json=navigation_guard_json,
                action_timeout_seconds=action_timeout_seconds,
            )
        if action == "stop":
            return await _invoke_action(
                _action_stop,
                session_id=resolved_session_id if raw_session_id else None,
            )
        if action == "open":
            return await _invoke_action(
                _action_open,
                url,
                page_id,
                resolved_session_id,
                emit_evidence=True,
            )
        if action == "navigate":
            return await _invoke_action(
                _action_navigate,
                url,
                page_id,
                resolved_session_id,
                emit_evidence=True,
            )
        if action == "navigate_back":
            return await _invoke_action(
                _action_navigate_back,
                page_id,
                resolved_session_id,
            )
        if action in ("screenshot", "take_screenshot"):
            return await _invoke_action(
                _action_screenshot,
                page_id,
                path or filename,
                full_page,
                screenshot_type,
                ref,
                element,
                frame_selector,
                resolved_session_id,
                emit_evidence=True,
            )
        if action == "snapshot":
            return await _invoke_action(
                _action_snapshot,
                page_id,
                snapshot_filename or filename,
                frame_selector,
                resolved_session_id,
            )
        if action == "click":
            return await _invoke_action(
                _action_click,
                page_id,
                selector,
                ref,
                element,
                wait,
                double_click,
                button,
                modifiers_json,
                frame_selector,
                resolved_session_id,
                emit_evidence=True,
            )
        if action == "type":
            return await _invoke_action(
                _action_type,
                page_id,
                selector,
                ref,
                element,
                text,
                submit,
                slowly,
                frame_selector,
                resolved_session_id,
            )
        if action == "eval":
            return await _invoke_action(
                _action_eval,
                page_id,
                code,
                resolved_session_id,
            )
        if action == "evaluate":
            return await _invoke_action(
                _action_evaluate,
                page_id,
                code,
                ref,
                element,
                frame_selector,
                resolved_session_id,
            )
        if action == "resize":
            return await _invoke_action(
                _action_resize,
                page_id,
                width,
                height,
                resolved_session_id,
            )
        if action == "console_messages":
            return await _invoke_action(
                _action_console_messages,
                page_id,
                level,
                filename or path,
                resolved_session_id,
            )
        if action == "handle_dialog":
            return await _invoke_action(
                _action_handle_dialog,
                page_id,
                accept,
                prompt_text,
                resolved_session_id,
            )
        if action == "file_upload":
            return await _invoke_action(
                _action_file_upload,
                page_id,
                paths_json,
                resolved_session_id,
                emit_evidence=True,
            )
        if action == "fill_form":
            return await _invoke_action(
                _action_fill_form,
                page_id,
                fields_json,
                resolved_session_id,
                emit_evidence=True,
            )
        if action == "install":
            return await _invoke_action(_action_install)
        if action == "press_key":
            return await _invoke_action(
                _action_press_key,
                page_id,
                key,
                resolved_session_id,
            )
        if action == "network_requests":
            return await _invoke_action(
                _action_network_requests,
                page_id,
                include_static,
                filename or path,
                resolved_session_id,
            )
        if action == "run_code":
            return await _invoke_action(
                _action_run_code,
                page_id,
                code,
                resolved_session_id,
            )
        if action == "drag":
            return await _invoke_action(
                _action_drag,
                page_id,
                start_ref,
                end_ref,
                start_selector,
                end_selector,
                start_element,
                end_element,
                frame_selector,
                resolved_session_id,
            )
        if action == "hover":
            return await _invoke_action(
                _action_hover,
                page_id,
                ref,
                element,
                selector,
                frame_selector,
                resolved_session_id,
            )
        if action == "select_option":
            return await _invoke_action(
                _action_select_option,
                page_id,
                ref,
                element,
                values_json,
                frame_selector,
                resolved_session_id,
            )
        if action == "tabs":
            return await _invoke_action(
                _action_tabs,
                page_id,
                tab_action,
                index,
                resolved_session_id,
                emit_evidence=True,
            )
        if action == "wait_for":
            return await _invoke_action(
                _action_wait_for,
                page_id,
                wait_time,
                text,
                text_gone,
                resolved_session_id,
            )
        if action == "pdf":
            return await _invoke_action(
                _action_pdf,
                page_id,
                path,
                resolved_session_id,
                emit_evidence=True,
            )
        if action == "close":
            return await _invoke_action(
                _action_close,
                page_id,
                resolved_session_id,
            )
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Unknown action: {action}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        logger.error("Browser tool error: %s", e, exc_info=True)
        return _tool_response(
            json.dumps(
                {"ok": False, "error": str(e)},
                ensure_ascii=False,
                indent=2,
            ),
        )


