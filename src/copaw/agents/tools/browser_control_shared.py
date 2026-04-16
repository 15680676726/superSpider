# -*- coding: utf-8 -*-
# flake8: noqa: E501
"""Browser automation tool using Playwright.

Single tool with action-based API matching browser MCP: start, stop, open,
navigate, navigate_back, screenshot, snapshot, click, type, eval, evaluate,
resize, console_messages, handle_dialog, file_upload, fill_form, install,
press_key, network_requests, run_code, drag, hover, select_option, tabs,
wait_for, pdf, close. Uses refs from snapshot for ref-based actions.
"""

import asyncio
from contextlib import suppress
import atexit
import inspect
import json
import logging
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ...config import (
    get_playwright_chromium_executable_path,
    get_system_default_browser,
    is_running_in_container,
)

from .browser_snapshot import build_role_snapshot_from_aria
from .evidence_runtime import BrowserEvidenceEvent, emit_browser_evidence

logger = logging.getLogger(__name__)

_BROWSER_EVIDENCE_ACTIONS = frozenset({
    "open",
    "navigate",
    "click",
    "fill_form",
    "file_upload",
    "tabs",
    "pdf",
    "screenshot",
    "take_screenshot",
})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _tool_response_text(response: ToolResponse) -> str:
    if not getattr(response, "content", None):
        return ""
    block = response.content[0]
    if isinstance(block, dict):
        return str(block.get("text", ""))
    return str(getattr(block, "text", ""))


def _parse_tool_response_json(response: ToolResponse) -> dict[str, Any]:
    text = _tool_response_text(response)
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "raw_text": text}
    return payload if isinstance(payload, dict) else {"ok": False, "raw_text": text}


def _path_exists(path: str | None) -> bool:
    text = str(path or "").strip()
    return bool(text) and Path(text).exists()


def _normalize_string_list(value: object) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    elif value is None:
        items = []
    else:
        items = [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _normalize_positive_timeout(value: object) -> float | None:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return None
    return timeout if timeout > 0 else None


def _normalize_navigation_guard(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, Any] = {}
    allowed_hosts = _normalize_string_list(raw.get("allowed_hosts"))
    blocked_hosts = _normalize_string_list(raw.get("blocked_hosts"))
    if allowed_hosts:
        normalized["allowed_hosts"] = allowed_hosts
    if blocked_hosts:
        normalized["blocked_hosts"] = blocked_hosts
    return normalized


def _host_matches_pattern(host: str, pattern: str) -> bool:
    normalized_host = str(host or "").strip().lower()
    normalized_pattern = str(pattern or "").strip().lower()
    if not normalized_host or not normalized_pattern:
        return False
    if normalized_pattern.startswith("*."):
        suffix = normalized_pattern[2:]
        return normalized_host == suffix or normalized_host.endswith(f".{suffix}")
    return normalized_host == normalized_pattern or normalized_host.endswith(
        f".{normalized_pattern}"
    )


def _navigation_guard_violation(
    url: str,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    session = _get_session_state(session_id)
    if not isinstance(session, dict):
        return None
    guard = _normalize_navigation_guard(session.get("navigation_guard"))
    if not guard:
        return None
    parsed = urlparse(str(url or "").strip())
    host = str(parsed.hostname or "").strip().lower()
    if not host:
        return None
    blocked_hosts = list(guard.get("blocked_hosts") or [])
    if any(_host_matches_pattern(host, pattern) for pattern in blocked_hosts):
        return {
            "error": (
                f"Blocked by browser navigation guard: host '{host}' is explicitly blocked."
            ),
            "guardrail": {
                "kind": "navigation-guard",
                "policy": "blocklist",
                "host": host,
                "blocked_hosts": blocked_hosts,
            },
        }
    allowed_hosts = list(guard.get("allowed_hosts") or [])
    if allowed_hosts and not any(
        _host_matches_pattern(host, pattern) for pattern in allowed_hosts
    ):
        return {
            "error": (
                f"Blocked by browser navigation guard: host '{host}' is not allowlisted for this browser session."
            ),
            "guardrail": {
                "kind": "navigation-guard",
                "policy": "allowlist",
                "host": host,
                "allowed_hosts": allowed_hosts,
            },
        }
    return None


def _session_action_timeout_seconds(session_id: str | None = None) -> float | None:
    session = _get_session_state(session_id)
    if not isinstance(session, dict):
        return None
    return _normalize_positive_timeout(session.get("action_timeout_seconds"))


def _normalized_download_record(record: dict[str, Any], *, page_id: str) -> dict[str, Any]:
    normalized = dict(record)
    normalized["page_id"] = str(normalized.get("page_id") or page_id)
    path = str(normalized.get("path") or "").strip()
    exists = bool(normalized.get("exists")) or _path_exists(path)
    status = str(normalized.get("status") or "").strip().lower() or (
        "completed" if exists else "observed"
    )
    normalized["path"] = path or None
    normalized["exists"] = exists
    normalized["status"] = status
    normalized["verified"] = bool(normalized.get("verified")) or (
        status == "completed" and exists
    )
    if "suggested_filename" in normalized:
        normalized["suggested_filename"] = str(normalized.get("suggested_filename") or "")
    return normalized


def _session_download_records(session_id: str | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for page_id, page_records in _session_bucket("downloads", session_id).items():
        if not isinstance(page_records, list):
            continue
        for item in page_records:
            if isinstance(item, dict):
                records.append(
                    _normalized_download_record(item, page_id=str(page_id)),
                )
    return records


def _latest_verified_download(
    page_id: str,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    page_records = _session_bucket("downloads", session_id).get(page_id, [])
    if isinstance(page_records, list):
        for item in reversed(page_records):
            if isinstance(item, dict):
                normalized = _normalized_download_record(item, page_id=page_id)
                if normalized.get("verified"):
                    return normalized
    for item in reversed(_session_download_records(session_id)):
        if item.get("verified"):
            return item
    return None


def _build_browser_verification(
    *,
    action: str,
    payload: dict[str, Any],
    page_id: str,
    url: str | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_metadata = dict(metadata or {})
    session_id = str(event_metadata.get("session_id") or "").strip() or None
    current_url = (
        payload.get("url")
        if isinstance(payload.get("url"), str) and str(payload.get("url")).strip()
        else _current_page_url(page_id, session_id)
        or url
    )
    raw_verification = payload.get("verification")
    if isinstance(raw_verification, dict) and raw_verification:
        verification = dict(raw_verification)
        verification.setdefault("verified", bool(raw_verification.get("verified")))
        verification.setdefault("status", "verified" if verification["verified"] else "unverified")
        verification.setdefault(
            "kind",
            "file-state" if action == "file_upload" else "page-state",
        )
        verification.setdefault("channel", "tool-response")
        observed_after = verification.get("observed_after")
        if not isinstance(observed_after, dict):
            observed_after = {}
        if current_url:
            observed_after.setdefault("url", current_url)
        verification["observed_after"] = observed_after
        return verification
    if action in {"open", "navigate"}:
        expected_url = (
            payload.get("url")
            if isinstance(payload.get("url"), str) and str(payload.get("url")).strip()
            else url
        )
        verified = bool(expected_url and current_url == expected_url)
        return {
            "verified": verified,
            "status": "verified" if verified else "unverified",
            "kind": "navigation",
            "channel": "page-url",
            "expected": {"url": expected_url},
            "observed_after": {"url": current_url} if current_url else {},
        }
    if action in {"screenshot", "take_screenshot", "pdf"}:
        artifact_path = str(payload.get("path") or event_metadata.get("path") or "").strip()
        exists = _path_exists(artifact_path)
        return {
            "verified": exists,
            "status": "verified" if exists else "unverified",
            "kind": "artifact",
            "channel": "filesystem",
            "artifact": {
                "path": artifact_path or None,
                "exists": exists,
            },
            "observed_after": {"url": current_url} if current_url else {},
        }
    if action == "click":
        download = _latest_verified_download(page_id, session_id)
        if download is not None:
            return {
                "verified": True,
                "status": "verified",
                "kind": "download",
                "channel": "playwright-download+filesystem",
                "download": download,
                "observed_after": {"url": current_url} if current_url else {},
            }
        return {
            "verified": False,
            "status": "unverified",
            "kind": "page-state",
            "channel": "follow-up-required",
            "reason": "click returned success without a verified page or file state anchor",
            "observed_after": {"url": current_url} if current_url else {},
        }
    return {
        "verified": False,
        "status": "unverified",
        "kind": "page-state",
        "channel": "follow-up-required",
        "reason": "action completed without an explicit verification anchor",
        "observed_after": {"url": current_url} if current_url else {},
    }


def _attach_download_listener(page, page_id: str, session_id: str) -> None:
    downloads = _session_bucket("downloads", session_id, create=True).setdefault(page_id, [])

    def _download_attr(download: Any, name: str) -> Any:
        value = getattr(download, name, None)
        return value() if callable(value) else value

    def _complete_download_record(record: dict[str, Any], path: str | None, error: str = "") -> None:
        resolved_path = str(path or "").strip()
        exists = _path_exists(resolved_path)
        if error:
            record["status"] = "failed"
            record["error"] = error
        else:
            record["status"] = "completed" if exists else "missing-file"
        record["path"] = resolved_path or None
        record["exists"] = exists
        record["verified"] = bool(record.get("verified")) or (
            record["status"] == "completed" and exists
        )
        record["completed_at"] = _utc_now().isoformat()
        _touch_activity(session_id)

    def on_download(download):
        record: dict[str, Any] = {
            "page_id": page_id,
            "status": "started",
            "url": getattr(download, "url", None),
            "suggested_filename": str(_download_attr(download, "suggested_filename") or ""),
            "observed_at": _utc_now().isoformat(),
            "verified": False,
        }
        downloads.append(record)
        _touch_activity(session_id)
        if _USE_SYNC_PLAYWRIGHT:
            try:
                _complete_download_record(record, download.path())
            except Exception as exc:
                _complete_download_record(record, None, str(exc))
            return

        async def _await_download() -> None:
            try:
                path = await download.path()
                _complete_download_record(record, path)
            except Exception as exc:
                _complete_download_record(record, None, str(exc))

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            record["status"] = "observed"
            return
        loop.create_task(_await_download())

    page.on("download", on_download)


def _compatible_browser_call_args(handler: Any, *args: Any) -> tuple[Any, ...]:
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):
        return args
    parameters = list(signature.parameters.values())
    if any(
        parameter.kind == inspect.Parameter.VAR_POSITIONAL
        for parameter in parameters
    ):
        return args
    positional_capacity = sum(
        1
        for parameter in parameters
        if parameter.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    )
    return args[:positional_capacity]


def _compatible_browser_call_kwargs(handler: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):
        return kwargs
    parameters = list(signature.parameters.values())
    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    ):
        return kwargs
    allowed = {
        name
        for name, parameter in signature.parameters.items()
        if parameter.kind
        in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    }
    return {
        key: value
        for key, value in kwargs.items()
        if key in allowed
    }


async def _invoke_browser_handler(handler: Any, *args: Any, **kwargs: Any) -> Any:
    result = handler(
        *_compatible_browser_call_args(handler, *args),
        **_compatible_browser_call_kwargs(handler, **kwargs),
    )
    if inspect.isawaitable(result):
        return await result
    return result


def _invoke_browser_helper(handler: Any, *args: Any, **kwargs: Any) -> Any:
    return handler(
        *_compatible_browser_call_args(handler, *args),
        **_compatible_browser_call_kwargs(handler, **kwargs),
    )


def _current_page_url(page_id: str, session_id: str | None = None) -> str | None:
    page = _session_bucket("pages", session_id).get(page_id)
    if page is None:
        return None
    try:
        value = getattr(page, "url", None)
    except Exception:
        return None
    return value if isinstance(value, str) and value else None


def get_browser_runtime_snapshot() -> dict[str, Any]:
    """Return a read-only snapshot of the current browser runtime surface."""
    default_kind, default_path = get_system_default_browser()
    current_session_id = _current_session_id()
    current_session = _get_session_state(current_session_id)
    page_ids = (
        sorted(str(page_id) for page_id in dict(current_session.get("pages") or {}).keys())
        if isinstance(current_session, dict)
        else []
    )
    sessions: list[dict[str, Any]] = []
    for session_id in _list_session_ids():
        session = _get_session_state(session_id)
        if not isinstance(session, dict):
            continue
        storage_state_path = str(session.get("storage_state_path") or "").strip()
        storage_state_available = _path_exists(storage_state_path)
        downloads = _session_download_records(session_id)
        completed_downloads = [
            item
            for item in downloads
            if item.get("status") == "completed" and item.get("verified")
        ]
        sessions.append(
            {
                "session_id": session_id,
                "profile_id": session.get("profile_id"),
                "browser_mode": str(session.get("browser_mode") or "managed-isolated"),
                "entry_url": session.get("entry_url"),
                "navigation_guard": _normalize_navigation_guard(
                    session.get("navigation_guard"),
                ),
                "action_timeout_seconds": _normalize_positive_timeout(
                    session.get("action_timeout_seconds"),
                ),
                "persist_login_state": bool(session.get("persist_login_state")),
                "storage_state_path": storage_state_path or None,
                "storage_state_available": storage_state_available,
                "save_reopen_verification": bool(
                    session.get("persist_login_state")
                    and (storage_state_available or storage_state_path)
                ),
                "current_page_id": session.get("current_page_id"),
                "page_count": len(dict(session.get("pages") or {})),
                "page_ids": sorted(
                    str(page_id)
                    for page_id in dict(session.get("pages") or {}).keys()
                ),
                "download_verification": True,
                "download_count": len(downloads),
                "completed_download_count": len(completed_downloads),
                "downloads": downloads[-3:],
                "created_at": session.get("created_at"),
                "last_activity_time": session.get("last_activity_time"),
            }
        )
    return {
        "running": _is_browser_running(),
        "headless": bool(_state.get("headless", False)),
        "current_session_id": current_session_id,
        "session_count": len(sessions),
        "sessions": sessions,
        "current_page_id": (
            current_session.get("current_page_id")
            if isinstance(current_session, dict)
            else None
        ),
        "page_count": len(page_ids),
        "page_ids": page_ids,
        "default_browser_kind": default_kind,
        "default_browser_path": default_path,
        "reload_mode": bool(_USE_SYNC_PLAYWRIGHT),
        "last_browser_error": _state.get("_last_browser_error"),
        "last_activity_time": _state.get("last_activity_time"),
    }


def get_browser_support_snapshot() -> dict[str, Any]:
    """Describe whether the local browser tool can be launched on this host."""
    playwright_ready = False
    playwright_error = ""
    try:
        if _USE_SYNC_PLAYWRIGHT:
            _ensure_playwright_sync()
        else:
            _ensure_playwright_async()
        playwright_ready = True
    except Exception as exc:  # pragma: no cover - exercised via router tests
        playwright_error = str(exc)
    runtime = get_browser_runtime_snapshot()
    return {
        **runtime,
        "playwright_ready": playwright_ready,
        "playwright_error": playwright_error,
        "container_mode": bool(is_running_in_container()),
    }


async def _emit_browser_action_evidence(
    *,
    action: str,
    page_id: str,
    response: ToolResponse,
    started_at: datetime,
    url: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    payload = _parse_tool_response_json(response)
    ok = bool(payload.get("ok"))
    result_summary = str(
        payload.get("message")
        or payload.get("error")
        or payload.get("raw_text")
        or f"Browser action {action} completed"
    )
    finished_at = _utc_now()
    duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
    event_metadata = dict(metadata or {})
    payload_guardrail = payload.get("guardrail")
    if isinstance(payload_guardrail, dict) and "guardrail" not in event_metadata:
        event_metadata["guardrail"] = dict(payload_guardrail)
    verification = _build_browser_verification(
        action=action,
        payload=payload,
        page_id=page_id,
        url=url,
        metadata=event_metadata,
    )
    event_metadata["verification"] = verification
    event_metadata["verification_status"] = verification.get("status")
    event_metadata["verification_kind"] = verification.get("kind")
    event_metadata["observe_act_verify"] = True
    await emit_browser_evidence(
        BrowserEvidenceEvent(
            action=action,
            page_id=page_id,
            status="success" if ok else "error",
            result_summary=result_summary,
            url=(payload.get("url") if isinstance(payload.get("url"), str) else url),
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            metadata=event_metadata,
        ),
    )

# Hybrid mode detection: Windows + Uvicorn reload mode requires sync Playwright
# to avoid NotImplementedError with asyncio.create_subprocess_exec.
# On other platforms or without reload, use async Playwright for better performance.
_USE_SYNC_PLAYWRIGHT = (
    sys.platform == "win32" and os.environ.get("COPAW_RELOAD_MODE") == "1"
)

if _USE_SYNC_PLAYWRIGHT:
    _executor: Optional[ThreadPoolExecutor] = None

    def _get_executor() -> ThreadPoolExecutor:
        global _executor
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="playwright",
            )
        return _executor

    async def _run_sync(func, *args, **kwargs):
        """Run a sync function in the thread pool and await the result."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _get_executor(),
            lambda: func(*args, **kwargs),
        )

else:

    async def _run_sync(func, *args, **kwargs):
        """Fallback: directly call async function (should not be used in async mode)."""
        return await func(*args, **kwargs)


# Process-global browser state (one browser process, multiple session contexts)
_state: dict[str, Any] = {
    "playwright": None,
    "browser": None,
    "context": None,
    "sessions": {},
    "headless": False,
    "current_session_id": None,
    "last_activity_time": 0.0,  # monotonic timestamp of last browser activity
    "_idle_task": None,  # background asyncio.Task for idle watchdog
    "_last_browser_error": None,  # message when launch failed (for user-facing error)
    "_sync_browser": None,  # sync browser handle for hybrid mode
    "_sync_context": None,  # sync context handle for hybrid mode
    "_sync_playwright": None,  # sync playwright handle for hybrid mode
}

# Stop the browser after this many seconds of inactivity (default 30 minutes).
_BROWSER_IDLE_TIMEOUT = 1800.0


def _normalize_session_id(session_id: str | None) -> str:
    normalized = str(session_id or "").strip()
    if normalized:
        return normalized
    current = str(_state.get("current_session_id") or "").strip()
    if current:
        return current
    return "default"


def _list_session_ids() -> list[str]:
    return [
        str(session_id)
        for session_id in dict(_state.get("sessions") or {}).keys()
        if str(session_id).strip()
    ]


def _initial_session_state(session_id: str) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "context": None,
        "pages": {},
        "refs": {},
        "refs_frame": {},
        "console_logs": {},
        "network_requests": {},
        "pending_dialogs": {},
        "pending_file_choosers": {},
        "downloads": {},
        "current_page_id": None,
        "page_counter": 0,
        "profile_id": None,
        "browser_mode": "managed-isolated",
        "entry_url": "",
        "navigation_guard": {},
        "action_timeout_seconds": None,
        "persist_login_state": False,
        "storage_state_path": "",
        "created_at": _utc_now().isoformat(),
        "last_activity_time": 0.0,
    }


def _get_session_state(
    session_id: str | None = None,
    *,
    create: bool = False,
) -> dict[str, Any] | None:
    normalized = _normalize_session_id(session_id)
    sessions = _state.setdefault("sessions", {})
    session = sessions.get(normalized)
    if session is None and create:
        session = _initial_session_state(normalized)
        sessions[normalized] = session
    return session if isinstance(session, dict) else None


def _touch_activity(session_id: str | None = None) -> None:
    """Record the current time as the last browser activity timestamp."""
    now = time.monotonic()
    _state["last_activity_time"] = now
    session = _get_session_state(session_id)
    if isinstance(session, dict):
        session["last_activity_time"] = now


def _current_session_id() -> str | None:
    current = str(_state.get("current_session_id") or "").strip()
    if current:
        return current
    session_ids = _list_session_ids()
    return session_ids[0] if session_ids else None


def _session_bucket(
    key: str,
    session_id: str | None = None,
    *,
    create: bool = False,
) -> dict[str, Any]:
    session = _get_session_state(session_id, create=create)
    if not isinstance(session, dict):
        return {}
    bucket = session.get(key)
    if not isinstance(bucket, dict):
        bucket = {}
        session[key] = bucket
    return bucket


def _current_page_id(session_id: str | None = None) -> str | None:
    session = _get_session_state(session_id)
    if not isinstance(session, dict):
        return None
    page_id = session.get("current_page_id")
    return str(page_id) if isinstance(page_id, str) and page_id else None


def _set_current_page_id(page_id: str | None, session_id: str | None = None) -> None:
    session = _get_session_state(session_id, create=True)
    if not isinstance(session, dict):
        return
    session["current_page_id"] = page_id


def attach_browser_session(session_id: str) -> dict[str, Any]:
    normalized = _normalize_session_id(session_id)
    session = _get_session_state(normalized)
    if not isinstance(session, dict) or session.get("context") is None:
        return {
            "ok": False,
            "error": f"Browser session '{normalized}' not found",
        }
    _state["current_session_id"] = normalized
    _touch_activity(normalized)
    return {
        "ok": True,
        "message": f"Attached browser session '{normalized}'",
        "session_id": normalized,
    }


def _is_browser_running() -> bool:
    """Check if browser is currently running (sync or async mode)."""
    if _USE_SYNC_PLAYWRIGHT:
        return _state.get("_sync_browser") is not None
    return _state.get("browser") is not None


def _reset_browser_state() -> None:
    """Reset all browser-related state variables."""
    # Clear sync/async specific state
    _state["playwright"] = None
    _state["browser"] = None
    _state["context"] = None
    _state["_sync_playwright"] = None
    _state["_sync_browser"] = None
    _state["_sync_context"] = None
    # Clear shared state
    _state["sessions"].clear()
    _state["current_session_id"] = None
    _state["last_activity_time"] = 0.0
    _state["headless"] = False


async def _await_cancelled_task(task) -> None:
    if task is None or task.done():
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


async def _idle_watchdog(idle_seconds: float = _BROWSER_IDLE_TIMEOUT) -> None:
    """Background task: stop the browser after it has been idle for *idle_seconds*.

    This reclaims Chrome renderer processes that accumulate when pages are
    opened during agent tasks but never explicitly closed.
    """
    try:
        while True:
            await asyncio.sleep(60)  # check every minute
            if not _is_browser_running():
                return
            idle = time.monotonic() - _state.get("last_activity_time", 0.0)
            if idle >= idle_seconds:
                logger.info(
                    "Browser idle for %.0fs (limit %.0fs), stopping to release resources",
                    idle,
                    idle_seconds,
                )
                await _action_stop()
                return
    except asyncio.CancelledError:
        pass


def _atexit_cleanup() -> None:
    """Best-effort browser cleanup registered with :func:`atexit`.

    Playwright child processes are cleaned up by the OS when the parent
    exits, but this gives Playwright a chance to flush any pending I/O and
    close Chrome gracefully before the process disappears.
    """
    if not _is_browser_running():
        return

    try:
        loop = asyncio.get_event_loop()
        if not loop.is_running() and not loop.is_closed():
            loop.run_until_complete(_action_stop())
    except Exception:
        pass


atexit.register(_atexit_cleanup)


def _tool_response(text: str) -> ToolResponse:
    """Wrap text for agentscope Toolkit (return ToolResponse)."""
    return ToolResponse(
        content=[TextBlock(type="text", text=text)],
    )


def _chromium_launch_args() -> list[str]:
    """Extra args for Chromium when running in container."""
    if is_running_in_container():
        return ["--no-sandbox", "--disable-dev-shm-usage"]
    return []


def _chromium_executable_path() -> str | None:
    """Chromium executable path when set (e.g. container); else None."""
    return get_playwright_chromium_executable_path()


def _use_webkit_fallback() -> bool:
    """True only on macOS when no system Chrome/Edge/Chromium found.
    Use WebKit (Safari) to avoid downloading Chromium. Windows has no system
    WebKit, so we never use webkit there.
    """
    return sys.platform == "darwin" and _chromium_executable_path() is None


def _ensure_playwright_async():
    """Import async_playwright; raise ImportError with hint if missing."""
    try:
        from playwright.async_api import async_playwright

        return async_playwright
    except ImportError as exc:
        raise ImportError(
            "Playwright not installed. Use the same Python that runs CoPaw (e.g. "
            "activate your venv or use 'uv run'): "
            f"'{sys.executable}' -m pip install playwright && "
            f"'{sys.executable}' -m playwright install",
        ) from exc


def _ensure_playwright_sync():
    """Import sync_playwright; raise ImportError with hint if missing."""
    try:
        from playwright.sync_api import sync_playwright

        return sync_playwright
    except ImportError as exc:
        raise ImportError(
            "Playwright not installed. Use the same Python that runs CoPaw (e.g. "
            "activate your venv or use 'uv run'): "
            f"'{sys.executable}' -m pip install playwright && "
            f"'{sys.executable}' -m playwright install",
        ) from exc


def _sync_browser_launch(headless: bool):
    """Launch browser using sync Playwright (for hybrid mode)."""
    sync_playwright = _ensure_playwright_sync()
    pw = sync_playwright().start()  # Start without context manager
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
        launch_kwargs = {"headless": headless}
        extra_args = _chromium_launch_args()
        if extra_args:
            launch_kwargs["args"] = extra_args
        launch_kwargs["executable_path"] = exe
        browser = pw.chromium.launch(**launch_kwargs)
    elif default_kind == "webkit" or sys.platform == "darwin":
        browser = pw.webkit.launch(headless=headless)
    else:
        launch_kwargs = {"headless": headless}
        extra_args = _chromium_launch_args()
        if extra_args:
            launch_kwargs["args"] = extra_args
        browser = pw.chromium.launch(**launch_kwargs)

    context = browser.new_context()
    _attach_context_listeners(context)
    return pw, browser, context


def _sync_browser_close():
    """Close browser using sync Playwright (for hybrid mode)."""
    if _state["_sync_browser"] is not None:
        try:
            _state["_sync_browser"].close()
        except Exception:
            pass
    if _state["_sync_playwright"] is not None:
        try:
            _state["_sync_playwright"].stop()
        except Exception:
            pass


def _parse_json_param(value: str, default: Any = None):
    """Parse optional JSON string param (e.g. fields, paths, values)."""
    if not value or not isinstance(value, str):
        return default
    value = value.strip()
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        if "," in value:
            return [x.strip() for x in value.split(",")]
        return default



__all__ = [name for name in globals() if not name.startswith("__")]
