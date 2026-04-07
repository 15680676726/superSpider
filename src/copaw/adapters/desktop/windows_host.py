# -*- coding: utf-8 -*-
"""Win32 desktop automation host for external MCP adapters.

This module intentionally keeps the desktop actuation boundary outside the core
kernel/runtime path. CoPaw mounts it through MCP, while the adapter owns the
host-specific mechanics.
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from .windows_uia import ControlSelector, UIAControlError, WindowsUIAAdapter

if sys.platform == "win32":
    import win32api
    import win32con
    import win32gui
    import win32process
else:  # pragma: no cover - exercised via platform guard
    win32api = None
    win32con = None
    win32gui = None
    win32process = None


class DesktopAutomationError(RuntimeError):
    """Raised when the desktop adapter cannot complete an action safely."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "desktop_automation_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class WindowSelector:
    """Stable selector for a top-level desktop window."""

    handle: int | None = None
    title: str | None = None
    title_contains: str | None = None
    title_regex: str | None = None
    process_id: int | None = None

    def is_empty(self) -> bool:
        return not any(
            (
                self.handle is not None,
                self.title,
                self.title_contains,
                self.title_regex,
                self.process_id is not None,
            ),
        )


ULONG_PTR = (
    ctypes.c_ulonglong
    if ctypes.sizeof(ctypes.c_void_p) == ctypes.sizeof(ctypes.c_ulonglong)
    else ctypes.c_ulong
)

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", _INPUTUNION)]


class WindowsDesktopHost:
    """Thin Win32 host wrapper used by the desktop MCP adapter."""

    def __init__(
        self,
        *,
        platform_name: str | None = None,
        win32gui_module: Any | None = None,
        win32process_module: Any | None = None,
        win32api_module: Any | None = None,
        win32con_module: Any | None = None,
        user32: Any | None = None,
        kernel32: Any | None = None,
        subprocess_module: Any | None = None,
        time_module: Any | None = None,
        operator_abort_producer: Callable[..., object] | None = None,
        uia_adapter: WindowsUIAAdapter | None = None,
    ) -> None:
        self._platform_name = platform_name or sys.platform
        self._win32gui = win32gui_module or win32gui
        self._win32process = win32process_module or win32process
        self._win32api = win32api_module or win32api
        self._win32con = win32con_module or win32con
        self._user32 = user32 or (
            ctypes.windll.user32 if self._platform_name == "win32" else None
        )
        self._kernel32 = kernel32 or (
            ctypes.windll.kernel32 if self._platform_name == "win32" else None
        )
        self._subprocess = subprocess_module or subprocess
        self._time = time_module or time
        self._operator_abort_producer = operator_abort_producer
        self._uia = uia_adapter or WindowsUIAAdapter(platform_name=self._platform_name)

    def list_windows(
        self,
        *,
        selector: WindowSelector | None = None,
        include_hidden: bool = False,
        limit: int = 50,
    ) -> dict[str, object]:
        """List matching top-level windows and their bounds."""
        self._ensure_supported()
        selector = selector or WindowSelector()
        windows = self._matching_windows(
            selector=selector,
            include_hidden=include_hidden,
        )
        if limit > 0:
            windows = windows[:limit]
        return {
            "success": True,
            "windows": windows,
            "count": len(windows),
        }

    def get_foreground_window(self) -> dict[str, object]:
        """Return the current foreground window when available."""
        self._ensure_supported()
        handle = int(self._win32gui.GetForegroundWindow() or 0)
        if handle <= 0:
            raise DesktopAutomationError("No foreground window is available")
        window = self._window_info(handle)
        return {
            "success": True,
            **window,
            "window": window,
        }

    def poll_operator_abort_signal(
        self,
        *,
        session_mount_id: str | None = None,
        runtime_session_ref: str | None = None,
        channel: str = "global-esc",
        reason: str | None = None,
        **_kwargs,
    ) -> dict[str, object]:
        """Publish a canonical operator-abort request when the host ESC key is pressed."""
        self._ensure_supported()
        if not self._operator_abort_requested():
            return {
                "success": True,
                "abort_requested": False,
            }
        if session_mount_id is None and runtime_session_ref is None:
            raise DesktopAutomationError(
                "session_mount_id or runtime_session_ref is required to publish operator abort",
                code="operator_abort_binding_required",
            )
        if not callable(self._operator_abort_producer):
            raise DesktopAutomationError(
                "operator abort producer is not configured",
                code="operator_abort_producer_unavailable",
            )
        resolved_channel = str(channel or "").strip() or "global-esc"
        resolved_reason = str(reason or "").strip() or "esc hotkey"
        produced = self._operator_abort_producer(
            session_mount_id=session_mount_id,
            runtime_session_ref=runtime_session_ref,
            channel=resolved_channel,
            reason=resolved_reason,
        )
        payload: dict[str, object] = {
            "success": True,
            "abort_requested": True,
            "channel": resolved_channel,
            "reason": resolved_reason,
        }
        if runtime_session_ref is not None:
            payload["runtime_session_ref"] = runtime_session_ref
        if session_mount_id is not None:
            payload["session_mount_id"] = session_mount_id
        producer_session_mount_id = None
        producer_environment_id = None
        if isinstance(produced, dict):
            producer_session_mount_id = produced.get("session_mount_id")
            producer_environment_id = produced.get("environment_id")
        else:
            producer_session_mount_id = getattr(produced, "id", None)
            producer_environment_id = getattr(produced, "environment_id", None)
        if producer_session_mount_id is not None:
            payload["session_mount_id"] = producer_session_mount_id
        if producer_environment_id is not None:
            payload["environment_id"] = producer_environment_id
        return payload

    def prepare_execution_cleanup(self, **_kwargs) -> dict[str, object]:
        """Capture the current foreground window for best-effort restore."""
        self._ensure_supported()
        return {
            "foreground_window": self._window_reference(
                self._foreground_window_info(),
            ),
        }

    def restore_foreground(
        self,
        *,
        cleanup_state: dict[str, object] | None = None,
        **_kwargs,
    ) -> dict[str, object]:
        """Restore a previously captured foreground window when it still exists."""
        self._ensure_supported()
        state = cleanup_state if isinstance(cleanup_state, dict) else {}
        reference = state.get("foreground_window")
        handle = 0
        if isinstance(reference, dict):
            try:
                handle = int(reference.get("handle") or 0)
            except Exception:
                handle = 0
        if handle > 0 and bool(self._win32gui.IsWindow(handle)):
            if not self._is_foreground_window(handle):
                self._prepare_window_for_focus(handle)
                self._activate_window(handle)
        foreground_window = self._foreground_window_info()
        return {
            "success": True,
            "restored": bool(
                foreground_window is not None
                and int(foreground_window["handle"]) == int(handle)
                and handle > 0
            ),
            "foreground_window": self._window_reference(foreground_window),
        }

    def launch_application(
        self,
        *,
        executable: str,
        args: Sequence[str] | None = None,
        cwd: str | None = None,
    ) -> dict[str, object]:
        """Launch an application and return its process id."""
        self._ensure_supported()
        executable = (executable or "").strip()
        if not executable:
            raise DesktopAutomationError("executable is required")
        command = [executable, *(args or ())]
        proc = self._subprocess.Popen(
            command,
            cwd=cwd or None,
        )
        return {
            "success": True,
            "process_id": int(proc.pid),
            "command": command,
            "cwd": cwd or "",
        }

    def wait_for_window(
        self,
        *,
        selector: WindowSelector,
        timeout_seconds: float = 10.0,
        poll_interval_seconds: float = 0.25,
        include_hidden: bool = False,
    ) -> dict[str, object]:
        """Wait until a matching window appears."""
        self._ensure_supported()
        if selector.is_empty():
            raise DesktopAutomationError("A window selector is required")
        deadline = self._time.monotonic() + max(timeout_seconds, 0.0)
        while True:
            matches = self._matching_windows(
                selector=selector,
                include_hidden=include_hidden,
            )
            if matches:
                return {
                    "success": True,
                    "window": matches[0],
                    "matched_count": len(matches),
                }
            if self._time.monotonic() >= deadline:
                raise DesktopAutomationError(
                    f"Timed out waiting for window: {self._selector_description(selector)}",
                )
            self._time.sleep(max(poll_interval_seconds, 0.01))

    def focus_window(self, *, selector: WindowSelector) -> dict[str, object]:
        """Bring a matching window to the foreground."""
        self._ensure_supported()
        window = self._resolve_window(selector)
        handle = int(window["handle"])
        self._prepare_window_for_focus(handle)
        self._activate_window(handle)
        if not self._is_foreground_window(handle):
            raise DesktopAutomationError(
                f"Failed to bring window to foreground: {self._selector_description(selector)}",
            )
        return {
            "success": True,
            "window": self._window_info(handle),
        }

    def close_window(
        self,
        *,
        selector: WindowSelector,
        timeout_seconds: float = 2.0,
    ) -> dict[str, object]:
        """Request a graceful close for a top-level window and verify the selector clears."""
        self._ensure_supported()
        window = self._resolve_window(selector)
        handle = int(window["handle"])
        attempted_paths: list[str] = []
        try:
            self.focus_window(selector=selector)
        except Exception:
            pass
        for close_path in self._semantic_close_selectors():
            try:
                self._uia.invoke_control(
                    window_handle=handle,
                    selector=close_path,
                    action="invoke",
                )
            except Exception:
                continue
            attempted_paths.append(f"semantic:{close_path.title or close_path.title_contains or 'control'}")
            if self._wait_for_selector_clear(selector, timeout_seconds=timeout_seconds):
                return {
                    "success": True,
                    "window": window,
                    "closed": True,
                    "close_path": attempted_paths[-1],
                }
        try:
            self._send_key_chord(["Ctrl", "W"])
            attempted_paths.append("keys:Ctrl+W")
            if self._wait_for_selector_clear(selector, timeout_seconds=timeout_seconds):
                return {
                    "success": True,
                    "window": window,
                    "closed": True,
                    "close_path": attempted_paths[-1],
                }
        except Exception:
            pass
        for keys in (["Alt", "F4"],):
            try:
                self._send_key_chord(keys)
            except Exception:
                continue
            attempted_paths.append(f"keys:{'+'.join(keys)}")
            if self._wait_for_selector_clear(selector, timeout_seconds=timeout_seconds):
                return {
                    "success": True,
                    "window": window,
                    "closed": True,
                    "close_path": attempted_paths[-1],
                }
        self._win32gui.PostMessage(handle, self._win32con.WM_CLOSE, 0, 0)
        attempted_paths.append("wm_close")
        if self._wait_for_selector_clear(selector, timeout_seconds=timeout_seconds):
            return {
                "success": True,
                "window": window,
                "closed": True,
                "close_path": attempted_paths[-1],
            }
        raise DesktopAutomationError(
            f"Failed to close window: {self._selector_description(selector)}",
            code="window_close_failed",
            details={
                "selector": self._selector_payload(selector),
                "window": window,
                "attempted_paths": attempted_paths,
                "remaining_windows": self._matching_windows(selector=selector, include_hidden=True),
            },
        )

    def verify_window_focus(self, *, selector: WindowSelector) -> dict[str, object]:
        """Verify whether the selected window currently owns the foreground."""
        self._ensure_supported()
        window = self._resolve_window(selector)
        foreground_window = self._foreground_window_info()
        return {
            "success": True,
            "window": self._window_info(int(window["handle"])),
            "is_foreground": bool(
                foreground_window
                and int(foreground_window["handle"]) == int(window["handle"])
            ),
            "foreground_window": foreground_window,
        }

    def list_controls(
        self,
        *,
        selector: WindowSelector,
        control_selector: ControlSelector | None = None,
        include_descendants: bool = True,
        max_depth: int = 4,
        limit: int = 100,
    ) -> dict[str, object]:
        """List UIA controls inside a resolved top-level window."""
        self._ensure_supported()
        window = self._resolve_window(selector)
        try:
            controls = self._uia.list_controls(
                window_handle=int(window["handle"]),
                selector=control_selector,
                include_descendants=include_descendants,
                max_depth=max_depth,
                limit=limit,
            )
        except UIAControlError as exc:
            raise DesktopAutomationError(
                str(exc),
                code=exc.code,
                details=exc.details,
            ) from exc
        return {
            "success": True,
            "window": window,
            "controls": controls,
            "count": len(controls),
        }

    def set_control_text(
        self,
        *,
        selector: WindowSelector,
        control_selector: ControlSelector,
        text: str,
        append: bool = False,
        focus_target: bool = True,
    ) -> dict[str, object]:
        """Update a control semantically through UIA instead of raw coordinates."""
        self._ensure_supported()
        if control_selector.is_empty():
            raise DesktopAutomationError("A control selector is required", code="control_selector_required")
        window = self._resolve_window(selector)
        if focus_target:
            window = self.focus_window(selector=selector)["window"]
        try:
            result = self._uia.set_control_text(
                window_handle=int(window["handle"]),
                selector=control_selector,
                text=text,
                append=append,
            )
        except UIAControlError as exc:
            raise DesktopAutomationError(
                str(exc),
                code=exc.code,
                details=exc.details,
            ) from exc
        if focus_target:
            self._verify_action_foreground(
                handle=int(window["handle"]),
                selector=selector,
                action_name="set_control_text",
            )
            window = self._window_info(int(window["handle"]))
        return {
            "success": True,
            "window": window,
            **result,
        }

    def invoke_control(
        self,
        *,
        selector: WindowSelector,
        control_selector: ControlSelector,
        action: str = "invoke",
        focus_target: bool = True,
    ) -> dict[str, object]:
        """Invoke a control by semantic selector."""
        self._ensure_supported()
        if control_selector.is_empty():
            raise DesktopAutomationError("A control selector is required", code="control_selector_required")
        window = self._resolve_window(selector)
        if focus_target:
            window = self.focus_window(selector=selector)["window"]
        try:
            result = self._uia.invoke_control(
                window_handle=int(window["handle"]),
                selector=control_selector,
                action=action,
            )
        except UIAControlError as exc:
            raise DesktopAutomationError(
                str(exc),
                code=exc.code,
                details=exc.details,
            ) from exc
        return {
            "success": True,
            "window": window,
            **result,
        }

    def invoke_dialog_action(
        self,
        *,
        selector: WindowSelector,
        action: str,
        control_selector: ControlSelector | None = None,
        focus_target: bool = True,
    ) -> dict[str, object]:
        """Invoke a semantic dialog action such as confirm/cancel/save/replace."""
        self._ensure_supported()
        window = self._resolve_window(selector)
        if focus_target:
            window = self.focus_window(selector=selector)["window"]
        try:
            result = self._uia.invoke_dialog_action(
                window_handle=int(window["handle"]),
                action=action,
                selector=control_selector,
            )
        except UIAControlError as exc:
            raise DesktopAutomationError(
                str(exc),
                code=exc.code,
                details=exc.details,
            ) from exc
        return {
            "success": True,
            "window": window,
            **result,
        }

    def click(
        self,
        *,
        x: int | None = None,
        y: int | None = None,
        selector: WindowSelector | None = None,
        relative_to_window: bool = False,
        click_count: int = 1,
        button: str = "left",
        focus_target: bool = True,
    ) -> dict[str, object]:
        """Click a screen point or a point inside a resolved window."""
        self._ensure_supported()
        selector = selector or WindowSelector()
        window: dict[str, object] | None = None
        if not selector.is_empty():
            window = self._resolve_window(selector)
            if focus_target:
                self.focus_window(selector=selector)
        if x is None or y is None:
            if window is None:
                raise DesktopAutomationError(
                    "x/y are required unless a target window is provided",
                )
            rect = window["rect"]
            x = int((rect["left"] + rect["right"]) / 2)
            y = int((rect["top"] + rect["bottom"]) / 2)
        elif relative_to_window:
            if window is None:
                raise DesktopAutomationError(
                    "relative_to_window requires a target window selector",
                )
            rect = window["rect"]
            x = int(rect["left"]) + int(x)
            y = int(rect["top"]) + int(y)
        self._mouse_click(x=int(x), y=int(y), button=button, click_count=click_count)
        if window is not None and focus_target:
            self._verify_action_foreground(
                handle=int(window["handle"]),
                selector=selector,
                action_name="click",
            )
            window = self._window_info(int(window["handle"]))
        return {
            "success": True,
            "x": int(x),
            "y": int(y),
            "button": button,
            "click_count": int(click_count),
            "window": window,
        }

    def type_text(
        self,
        *,
        text: str,
        selector: WindowSelector | None = None,
        focus_target: bool = True,
    ) -> dict[str, object]:
        """Send unicode text to the foreground or selected window."""
        self._ensure_supported()
        selector = selector or WindowSelector()
        window: dict[str, object] | None = None
        if not selector.is_empty():
            if focus_target:
                focused = self.focus_window(selector=selector)
                window = focused["window"]
            else:
                window = self._resolve_window(selector)
        if not text:
            raise DesktopAutomationError("text is required")
        self._send_text(text)
        if window is not None and focus_target:
            self._verify_action_foreground(
                handle=int(window["handle"]),
                selector=selector,
                action_name="type_text",
            )
            window = self._window_info(int(window["handle"]))
        return {
            "success": True,
            "text": text,
            "char_count": len(text),
            "window": window,
        }

    def press_keys(
        self,
        *,
        keys: str | Sequence[str],
        selector: WindowSelector | None = None,
        focus_target: bool = True,
    ) -> dict[str, object]:
        """Press a key chord against the foreground or selected window."""
        self._ensure_supported()
        selector = selector or WindowSelector()
        window: dict[str, object] | None = None
        if not selector.is_empty():
            if focus_target:
                focused = self.focus_window(selector=selector)
                window = focused["window"]
            else:
                window = self._resolve_window(selector)
        tokens = self._normalize_key_tokens(keys)
        if not tokens:
            raise DesktopAutomationError("At least one key token is required")
        self._send_key_chord(tokens)
        if window is not None and focus_target:
            self._verify_action_foreground(
                handle=int(window["handle"]),
                selector=selector,
                action_name="press_keys",
            )
            window = self._window_info(int(window["handle"]))
        return {
            "success": True,
            "keys": tokens,
            "window": window,
        }

    def write_document_file(
        self,
        *,
        path: str,
        content: str,
        encoding: str = "utf-8",
        create_parent_dirs: bool = True,
    ) -> dict[str, object]:
        """Create or overwrite a text document and verify by rereading it."""
        self._ensure_supported()
        target = self._validate_document_path(path)
        existed_before = target.exists()
        if existed_before and not target.is_file():
            raise DesktopAutomationError(f"Document path is not a file: {target}")
        if create_parent_dirs:
            target.parent.mkdir(parents=True, exist_ok=True)
        return self._write_and_verify_document(
            target=target,
            content=content,
            encoding=encoding,
            existed_before=existed_before,
            replacements=0,
        )

    def edit_document_file(
        self,
        *,
        path: str,
        find_text: str,
        replace_text: str,
        encoding: str = "utf-8",
    ) -> dict[str, object]:
        """Edit a text document, save it, and verify by rereading exact content."""
        self._ensure_supported()
        target = self._validate_document_path(path)
        if not target.exists():
            raise DesktopAutomationError(f"Document does not exist: {target}")
        if not target.is_file():
            raise DesktopAutomationError(f"Document path is not a file: {target}")
        if not find_text:
            raise DesktopAutomationError("find_text is required")
        original_content = target.read_text(encoding=encoding)
        replacements = original_content.count(find_text)
        if replacements <= 0:
            raise DesktopAutomationError(
                f"Text '{find_text}' was not found in document: {target}",
            )
        updated_content = original_content.replace(find_text, replace_text)
        return self._write_and_verify_document(
            target=target,
            content=updated_content,
            encoding=encoding,
            existed_before=True,
            replacements=replacements,
        )

    def _ensure_supported(self) -> None:
        if self._platform_name != "win32":
            raise DesktopAutomationError(
                "desktop-windows adapter is only available on Windows hosts",
            )
        if not all(
            (
                self._win32gui is not None,
                self._win32process is not None,
                self._win32api is not None,
                self._win32con is not None,
                self._user32 is not None,
            ),
        ):
            raise DesktopAutomationError(
                "Win32 desktop dependencies are not available on this host",
            )

    def _prepare_window_for_focus(self, handle: int) -> None:
        if bool(self._win32gui.IsIconic(handle)):
            self._win32gui.ShowWindow(handle, self._win32con.SW_RESTORE)
        self._win32gui.ShowWindow(handle, self._win32con.SW_SHOW)

    def _wait_for_selector_clear(
        self,
        selector: WindowSelector,
        *,
        timeout_seconds: float,
    ) -> bool:
        deadline = self._time.monotonic() + max(timeout_seconds, 0.0)
        while True:
            matches = self._matching_windows(selector=selector, include_hidden=True)
            if not matches:
                return True
            if self._time.monotonic() >= deadline:
                return False
            self._time.sleep(0.05)

    def _semantic_close_selectors(self) -> tuple[ControlSelector, ...]:
        return (
            ControlSelector(title="\u5173\u95ed\u6807\u7b7e\u9875", control_type="Button", found_index=0),
            ControlSelector(title="Close tab", control_type="Button", found_index=0),
            ControlSelector(title="\u5173\u95ed", control_type="Button", found_index=0),
            ControlSelector(title="Close", control_type="Button", found_index=0),
        )

    def _activate_window(self, handle: int) -> None:
        self._try_focus_primitives(handle)
        if self._is_foreground_window(handle):
            return
        self._try_attach_thread_focus(handle)
        if self._is_foreground_window(handle):
            return
        self._try_alt_key_focus(handle)

    def _try_focus_primitives(self, handle: int) -> None:
        for action in (
            self._set_foreground_window,
            self._bring_window_to_top,
            self._set_active_window,
            self._set_focus,
            self._set_foreground_window,
        ):
            action(handle)
            if self._is_foreground_window(handle):
                return

    def _set_foreground_window(self, handle: int) -> None:
        try:
            self._win32gui.SetForegroundWindow(handle)
        except Exception:
            return

    def _bring_window_to_top(self, handle: int) -> None:
        bring = getattr(self._user32, "BringWindowToTop", None)
        if callable(bring):
            try:
                bring(handle)
            except Exception:
                pass

    def _set_active_window(self, handle: int) -> None:
        setter = getattr(self._user32, "SetActiveWindow", None)
        if callable(setter):
            try:
                setter(handle)
            except Exception:
                pass

    def _set_focus(self, handle: int) -> None:
        setter = getattr(self._user32, "SetFocus", None)
        if callable(setter):
            try:
                setter(handle)
            except Exception:
                pass

    def _try_attach_thread_focus(self, handle: int) -> None:
        attach = getattr(self._user32, "AttachThreadInput", None)
        current_thread_getter = getattr(self._kernel32, "GetCurrentThreadId", None)
        if not callable(attach) or not callable(current_thread_getter):
            return

        current_thread_id = int(current_thread_getter())
        foreground_handle = int(self._win32gui.GetForegroundWindow() or 0)
        target_thread_id = self._window_thread_id(handle)
        foreground_thread_id = (
            self._window_thread_id(foreground_handle)
            if foreground_handle > 0
            else 0
        )
        attached_pairs: list[tuple[int, int]] = []
        seen_target_threads: set[int] = set()

        for target_thread_id_candidate in (target_thread_id, foreground_thread_id):
            if (
                target_thread_id_candidate <= 0
                or target_thread_id_candidate == current_thread_id
                or target_thread_id_candidate in seen_target_threads
            ):
                continue
            try:
                attach(current_thread_id, target_thread_id_candidate, True)
                attached_pairs.append((current_thread_id, target_thread_id_candidate))
                seen_target_threads.add(target_thread_id_candidate)
            except Exception:
                continue

        try:
            allow = getattr(self._user32, "AllowSetForegroundWindow", None)
            if callable(allow):
                try:
                    allow(-1)
                except Exception:
                    pass
            self._try_focus_primitives(handle)
        finally:
            for source_thread_id, target_thread_id_candidate in reversed(attached_pairs):
                try:
                    attach(source_thread_id, target_thread_id_candidate, False)
                except Exception:
                    continue

    def _try_alt_key_focus(self, handle: int) -> None:
        keybd_event = getattr(self._user32, "keybd_event", None)
        if callable(keybd_event):
            try:
                keybd_event(self._win32con.VK_MENU, 0, 0, 0)
                keybd_event(self._win32con.VK_MENU, 0, KEYEVENTF_KEYUP, 0)
            except Exception:
                pass
        self._try_focus_primitives(handle)

    def _operator_abort_requested(self) -> bool:
        get_async_key_state = getattr(self._user32, "GetAsyncKeyState", None)
        if not callable(get_async_key_state):
            return False
        try:
            state = int(get_async_key_state(self._win32con.VK_ESCAPE))
        except Exception as exc:
            raise DesktopAutomationError(
                "Failed to read operator abort hotkey state",
                code="operator_abort_state_unavailable",
            ) from exc
        return bool(state & 0x8000)

    def _is_foreground_window(self, handle: int) -> bool:
        try:
            foreground = int(self._win32gui.GetForegroundWindow() or 0)
        except Exception:
            return False
        return foreground == int(handle)

    def _foreground_window_info(self) -> dict[str, object] | None:
        try:
            handle = int(self._win32gui.GetForegroundWindow() or 0)
        except Exception:
            return None
        if handle <= 0 or not bool(self._win32gui.IsWindow(handle)):
            return None
        return self._safe_window_info(handle)

    def _verify_action_foreground(
        self,
        *,
        handle: int,
        selector: WindowSelector,
        action_name: str,
    ) -> None:
        if self._is_foreground_window(handle):
            return
        foreground_window = self._foreground_window_info()
        foreground_desc = (
            f"{foreground_window['title']} ({foreground_window['handle']})"
            if foreground_window is not None
            else "none"
        )
        raise DesktopAutomationError(
            f"{action_name} lost focus after input; possible modal interruption or "
            f"window drift while targeting {self._selector_description(selector)}. "
            f"Current foreground: {foreground_desc}.",
            code=self._focus_loss_error_code(foreground_window),
            details={
                "action_name": action_name,
                "selector": self._selector_payload(selector),
                "target_window": self._window_reference(self._window_info(handle)),
                "foreground_window": self._window_reference(foreground_window),
                "interruption_kind": self._focus_loss_interruption_kind(
                    foreground_window,
                ),
            },
        )

    def _window_thread_id(self, handle: int) -> int:
        if handle <= 0:
            return 0
        try:
            thread_id, _process_id = self._win32process.GetWindowThreadProcessId(handle)
        except Exception:
            return 0
        return int(thread_id or 0)

    def _matching_windows(
        self,
        *,
        selector: WindowSelector,
        include_hidden: bool,
    ) -> list[dict[str, object]]:
        foreground = int(self._win32gui.GetForegroundWindow() or 0)
        windows: list[dict[str, object]] = []

        def _enum(hwnd: int, _ctx: object) -> None:
            if not bool(self._win32gui.IsWindow(hwnd)):
                return
            if not include_hidden and not bool(self._win32gui.IsWindowVisible(hwnd)):
                return
            info = self._safe_window_info(hwnd)
            if info is None:
                return
            if self._window_matches(info, selector):
                windows.append(info)

        self._win32gui.EnumWindows(_enum, None)
        windows.sort(
            key=lambda item: (
                0 if int(item["handle"]) == foreground else 1,
                0 if item["visible"] else 1,
                str(item["title"]).lower(),
                int(item["handle"]),
            ),
        )
        return windows

    def _resolve_window(self, selector: WindowSelector) -> dict[str, object]:
        if selector.is_empty():
            raise DesktopAutomationError("A window selector is required")
        matches = self._matching_windows(selector=selector, include_hidden=True)
        if not matches:
            raise DesktopAutomationError(
                f"No matching window found for {self._selector_description(selector)}",
                code="window_not_found",
                details={"selector": self._selector_payload(selector)},
            )
        if len(matches) > 1:
            raise DesktopAutomationError(
                f"Ambiguous window selector matched {len(matches)} windows for "
                f"{self._selector_description(selector)}",
                code="window_selector_ambiguous",
                details={
                    "selector": self._selector_payload(selector),
                    "matched_count": len(matches),
                    "matches": [self._window_reference(item) for item in matches[:5]],
                },
            )
        return matches[0]

    def _window_matches(
        self,
        info: dict[str, object],
        selector: WindowSelector,
    ) -> bool:
        if selector.handle is not None and int(info["handle"]) != int(selector.handle):
            return False
        title = str(info["title"] or "")
        if selector.title and title != selector.title:
            return False
        if selector.title_contains and selector.title_contains not in title:
            return False
        if selector.title_regex and not re.search(selector.title_regex, title):
            return False
        if (
            selector.process_id is not None
            and int(info["process_id"]) != int(selector.process_id)
        ):
            return False
        return True

    def _window_info(self, hwnd: int) -> dict[str, object]:
        left, top, right, bottom = self._win32gui.GetWindowRect(hwnd)
        _thread_id, process_id = self._win32process.GetWindowThreadProcessId(hwnd)
        return {
            "handle": int(hwnd),
            "title": self._win32gui.GetWindowText(hwnd),
            "class_name": self._win32gui.GetClassName(hwnd),
            "process_id": int(process_id),
            "visible": bool(self._win32gui.IsWindowVisible(hwnd)),
            "enabled": bool(self._win32gui.IsWindowEnabled(hwnd)),
            "rect": {
                "left": int(left),
                "top": int(top),
                "right": int(right),
                "bottom": int(bottom),
                "width": int(max(right - left, 0)),
                "height": int(max(bottom - top, 0)),
            },
        }

    def _safe_window_info(self, hwnd: int) -> dict[str, object] | None:
        try:
            return self._window_info(hwnd)
        except Exception:
            return None

    def _validate_document_path(self, path: str) -> Path:
        normalized = Path((path or "").strip())
        if not str(normalized):
            raise DesktopAutomationError("path is required")
        return normalized

    def _write_and_verify_document(
        self,
        *,
        target: Path,
        content: str,
        encoding: str,
        existed_before: bool,
        replacements: int,
    ) -> dict[str, object]:
        with target.open("w", encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        with target.open("r", encoding=encoding) as handle:
            verified_content = handle.read()
        if verified_content != content:
            raise DesktopAutomationError(
                f"Post-write reread mismatch for document: {target}",
                code="document_post_write_reread_mismatch",
                details={
                    "path": str(target),
                    "encoding": encoding,
                    "expected_char_count": len(content),
                    "actual_char_count": len(verified_content),
                },
            )
        bytes_written = len(content.encode(encoding))
        verified_bytes = len(verified_content.encode(encoding))
        return {
            "success": True,
            "path": str(target),
            "resolved_path": str(target.resolve()),
            "created": not existed_before,
            "existed_before": existed_before,
            "saved": True,
            "reopened": True,
            "verified_content": verified_content,
            "bytes_written": bytes_written,
            "char_count": len(content),
            "replacements": replacements,
            "encoding": encoding,
            "verification": {
                "saved": True,
                "reopened": True,
                "post_write_reread_verified": True,
                "expected_char_count": len(content),
                "verified_char_count": len(verified_content),
                "expected_bytes": bytes_written,
                "verified_bytes": verified_bytes,
            },
        }

    def _mouse_click(
        self,
        *,
        x: int,
        y: int,
        button: str,
        click_count: int,
    ) -> None:
        button_name = (button or "left").strip().lower()
        event_map = {
            "left": (
                self._win32con.MOUSEEVENTF_LEFTDOWN,
                self._win32con.MOUSEEVENTF_LEFTUP,
            ),
            "right": (
                self._win32con.MOUSEEVENTF_RIGHTDOWN,
                self._win32con.MOUSEEVENTF_RIGHTUP,
            ),
        }
        if button_name not in event_map:
            raise DesktopAutomationError(
                f"Unsupported mouse button '{button_name}'",
            )
        down_event, up_event = event_map[button_name]
        self._win32api.SetCursorPos((x, y))
        for _ in range(max(int(click_count), 1)):
            self._win32api.mouse_event(down_event, x, y, 0, 0)
            self._win32api.mouse_event(up_event, x, y, 0, 0)

    def _normalize_key_tokens(self, keys: str | Sequence[str]) -> list[str]:
        if isinstance(keys, str):
            text = keys.strip()
            if not text:
                return []
            if "+" in text:
                return [item.strip() for item in text.split("+") if item.strip()]
            return [text]
        tokens: list[str] = []
        for item in keys:
            normalized = str(item).strip()
            if normalized:
                tokens.append(normalized)
        return tokens

    def _send_text(self, text: str) -> None:
        inputs: list[INPUT] = []
        for char in text:
            code_point = ord(char)
            inputs.append(self._keyboard_input(scan=code_point, flags=KEYEVENTF_UNICODE))
            inputs.append(
                self._keyboard_input(
                    scan=code_point,
                    flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                ),
            )
        self._dispatch_inputs(inputs)

    def _send_key_chord(self, tokens: Sequence[str]) -> None:
        inputs: list[INPUT] = []
        pending_modifiers: list[int] = []
        for token in tokens:
            modifiers, virtual_key = self._vk_for_token(token)
            normalized = token.strip().upper()
            if normalized in {"CTRL", "SHIFT", "ALT", "WIN"} and not modifiers:
                pending_modifiers.append(virtual_key)
                continue
            chord_modifiers: list[int] = []
            for modifier in [*pending_modifiers, *modifiers]:
                if modifier not in chord_modifiers:
                    chord_modifiers.append(modifier)
            for modifier in chord_modifiers:
                inputs.append(self._keyboard_input(virtual_key=modifier))
            inputs.append(self._keyboard_input(virtual_key=virtual_key))
            inputs.append(
                self._keyboard_input(
                    virtual_key=virtual_key,
                    flags=KEYEVENTF_KEYUP,
                ),
            )
            for modifier in reversed(chord_modifiers):
                inputs.append(
                    self._keyboard_input(
                        virtual_key=modifier,
                        flags=KEYEVENTF_KEYUP,
                    ),
                )
            pending_modifiers = []
        for modifier in pending_modifiers:
            inputs.append(
                self._keyboard_input(virtual_key=modifier),
            )
            inputs.append(
                self._keyboard_input(
                    virtual_key=modifier,
                    flags=KEYEVENTF_KEYUP,
                ),
            )
        self._dispatch_inputs(inputs)

    def _vk_for_token(self, token: str) -> tuple[list[int], int]:
        normalized = token.strip()
        if not normalized:
            raise DesktopAutomationError("Key token cannot be empty")

        key_map = {
            "ALT": self._win32con.VK_MENU,
            "BACKSPACE": self._win32con.VK_BACK,
            "CTRL": self._win32con.VK_CONTROL,
            "DELETE": self._win32con.VK_DELETE,
            "DOWN": self._win32con.VK_DOWN,
            "END": self._win32con.VK_END,
            "ENTER": self._win32con.VK_RETURN,
            "ESC": self._win32con.VK_ESCAPE,
            "HOME": self._win32con.VK_HOME,
            "LEFT": self._win32con.VK_LEFT,
            "PGDN": self._win32con.VK_NEXT,
            "PGUP": self._win32con.VK_PRIOR,
            "RIGHT": self._win32con.VK_RIGHT,
            "SHIFT": self._win32con.VK_SHIFT,
            "SPACE": self._win32con.VK_SPACE,
            "TAB": self._win32con.VK_TAB,
            "UP": self._win32con.VK_UP,
            "WIN": self._win32con.VK_LWIN,
        }
        for function_key_index in range(1, 13):
            virtual_key = getattr(self._win32con, f"VK_F{function_key_index}", None)
            if virtual_key is not None:
                key_map[f"F{function_key_index}"] = int(virtual_key)
        upper = normalized.upper()
        if upper in key_map:
            return [], key_map[upper]
        if len(normalized) == 1 and normalized.isalnum():
            return [], ord(normalized.upper())
        vk_scan = int(self._win32api.VkKeyScan(normalized))
        if vk_scan == -1:
            raise DesktopAutomationError(
                f"Unsupported key token '{normalized}'",
            )
        virtual_key = vk_scan & 0xFF
        shift_state = (vk_scan >> 8) & 0xFF
        modifiers: list[int] = []
        if shift_state & 1:
            modifiers.append(self._win32con.VK_SHIFT)
        if shift_state & 2:
            modifiers.append(self._win32con.VK_CONTROL)
        if shift_state & 4:
            modifiers.append(self._win32con.VK_MENU)
        return modifiers, virtual_key

    def _dispatch_inputs(self, inputs: Sequence[INPUT]) -> None:
        if not inputs:
            return
        array_type = INPUT * len(inputs)
        input_array = array_type(*inputs)
        sent = int(self._user32.SendInput(len(inputs), input_array, ctypes.sizeof(INPUT)))
        if sent != len(inputs):
            raise DesktopAutomationError(
                f"SendInput dispatched {sent}/{len(inputs)} keyboard events",
            )

    def _keyboard_input(
        self,
        *,
        virtual_key: int = 0,
        scan: int = 0,
        flags: int = 0,
    ) -> INPUT:
        return INPUT(
            type=INPUT_KEYBOARD,
            union=_INPUTUNION(
                ki=KEYBDINPUT(
                    wVk=int(virtual_key),
                    wScan=int(scan),
                    dwFlags=int(flags),
                    time=0,
                    dwExtraInfo=0,
                ),
            ),
        )

    def _selector_description(self, selector: WindowSelector) -> str:
        fields = []
        if selector.handle is not None:
            fields.append(f"handle={selector.handle}")
        if selector.title:
            fields.append(f"title={selector.title!r}")
        if selector.title_contains:
            fields.append(f"title_contains={selector.title_contains!r}")
        if selector.title_regex:
            fields.append(f"title_regex={selector.title_regex!r}")
        if selector.process_id is not None:
            fields.append(f"process_id={selector.process_id}")
        return ", ".join(fields) or "<empty selector>"

    def _selector_payload(self, selector: WindowSelector) -> dict[str, object]:
        return {
            "handle": selector.handle,
            "title": selector.title,
            "title_contains": selector.title_contains,
            "title_regex": selector.title_regex,
            "process_id": selector.process_id,
        }

    def _window_reference(
        self,
        window: dict[str, object] | None,
    ) -> dict[str, object] | None:
        if window is None:
            return None
        return {
            "handle": window.get("handle"),
            "title": window.get("title"),
            "class_name": window.get("class_name"),
            "process_id": window.get("process_id"),
        }

    def _focus_loss_error_code(
        self,
        foreground_window: dict[str, object] | None,
    ) -> str:
        if self._is_modal_window(foreground_window):
            return "modal_interruption"
        return "focus_verification_failed"

    def _focus_loss_interruption_kind(
        self,
        foreground_window: dict[str, object] | None,
    ) -> str:
        if self._is_modal_window(foreground_window):
            return "modal_dialog"
        if foreground_window is None:
            return "no_foreground_window"
        return "window_drift"

    def _is_modal_window(self, window: dict[str, object] | None) -> bool:
        if window is None:
            return False
        class_name = str(window.get("class_name") or "")
        title = str(window.get("title") or "").lower()
        return class_name == "#32770" or "dialog" in title or "popup" in title
