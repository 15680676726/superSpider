from __future__ import annotations

from types import SimpleNamespace

from copaw.adapters.desktop import windows_mcp_server
from copaw.adapters.desktop.windows_host import WindowSelector, WindowsDesktopHost
from copaw.adapters.desktop.windows_uia import ControlSelector


class _FakeWin32GUI:
    def __init__(self) -> None:
        self.foreground = 101
        self.closed: list[int] = []
        self.windows = {
            101: {
                "title": "Dialog Host",
                "class_name": "#32770",
                "visible": True,
                "enabled": True,
                "rect": (10, 20, 210, 160),
                "iconic": False,
            },
        }

    def EnumWindows(self, callback, context) -> None:
        for hwnd in list(self.windows):
            callback(hwnd, context)

    def IsWindow(self, hwnd: int) -> bool:
        return hwnd in self.windows

    def IsWindowVisible(self, hwnd: int) -> bool:
        return bool(self.windows[hwnd]["visible"])

    def IsWindowEnabled(self, hwnd: int) -> bool:
        return bool(self.windows[hwnd]["enabled"])

    def GetWindowText(self, hwnd: int) -> str:
        return str(self.windows[hwnd]["title"])

    def GetClassName(self, hwnd: int) -> str:
        return str(self.windows[hwnd]["class_name"])

    def GetWindowRect(self, hwnd: int):
        return tuple(self.windows[hwnd]["rect"])

    def GetForegroundWindow(self) -> int:
        return int(self.foreground)

    def IsIconic(self, hwnd: int) -> bool:
        return bool(self.windows[hwnd]["iconic"])

    def ShowWindow(self, hwnd: int, _command: int) -> None:
        self.windows[hwnd]["iconic"] = False

    def SetForegroundWindow(self, hwnd: int) -> None:
        self.foreground = hwnd

    def PostMessage(self, hwnd: int, msg: int, wparam: int, lparam: int) -> None:
        _ = (msg, wparam, lparam)
        self.closed.append(hwnd)


class _FakeWin32Process:
    def GetWindowThreadProcessId(self, hwnd: int):
        return 1, {101: 5001}[hwnd]


class _FakeUser32:
    def __init__(self, gui: _FakeWin32GUI) -> None:
        self._gui = gui

    def SendInput(self, count: int, _array, _size: int) -> int:
        return count

    def AttachThreadInput(self, _source_thread: int, _target_thread: int, _attach: bool) -> int:
        return 1

    def AllowSetForegroundWindow(self, _process_id: int) -> int:
        return 1

    def BringWindowToTop(self, hwnd: int) -> int:
        self._gui.foreground = hwnd
        return 1

    def SetActiveWindow(self, hwnd: int) -> int:
        self._gui.foreground = hwnd
        return hwnd

    def SetFocus(self, hwnd: int) -> int:
        self._gui.foreground = hwnd
        return hwnd

    def keybd_event(self, _key: int, _scan_code: int, _flags: int, _extra_info: int) -> None:
        return None

    def GetAsyncKeyState(self, _key: int) -> int:
        return 0


class _FakeKernel32:
    def GetCurrentThreadId(self) -> int:
        return 77


class _FakeUIAAdapter:
    def __init__(self, gui: _FakeWin32GUI | None = None) -> None:
        self._gui = gui
        self.calls: list[tuple[str, dict[str, object]]] = []

    def list_controls(self, **kwargs):
        self.calls.append(("list_controls", dict(kwargs)))
        return [
            {
                "handle": 9001,
                "title": "Save",
                "automation_id": "1",
                "control_type": "Button",
            }
        ]

    def set_control_text(self, **kwargs):
        self.calls.append(("set_control_text", dict(kwargs)))
        return {
            "control": {
                "handle": 9002,
                "title": "File name:",
                "automation_id": "FileNameControlHost",
                "control_type": "Edit",
            },
            "text": kwargs["text"],
            "append": kwargs["append"],
        }

    def invoke_control(self, **kwargs):
        self.calls.append(("invoke_control", dict(kwargs)))
        selector = kwargs["selector"]
        window_handle = int(kwargs["window_handle"])
        title = getattr(selector, "title", None)
        if self._gui is not None and title == "关闭标签页":
            self._gui.windows[window_handle]["title"] = "Other Document - Notepad"
        if self._gui is not None and title == "关闭":
            self._gui.windows.pop(window_handle, None)
        return {
            "control": {
                "handle": 9001,
                "title": title or "Save",
                "automation_id": "1",
                "control_type": "Button",
            },
            "action": kwargs["action"],
        }

    def invoke_dialog_action(self, **kwargs):
        self.calls.append(("invoke_dialog_action", dict(kwargs)))
        return {
            "control": {
                "handle": 9001,
                "title": "Save",
                "automation_id": "1",
                "control_type": "Button",
            },
            "dialog_action": kwargs["action"],
        }


def _build_host_with_uia():
    gui = _FakeWin32GUI()
    uia = _FakeUIAAdapter(gui)
    host = WindowsDesktopHost(
        platform_name="win32",
        win32gui_module=gui,
        win32process_module=_FakeWin32Process(),
        win32api_module=SimpleNamespace(),
        win32con_module=SimpleNamespace(
            SW_RESTORE=9,
            SW_SHOW=5,
            WM_CLOSE=16,
            VK_ESCAPE=27,
        ),
        user32=_FakeUser32(gui),
        kernel32=_FakeKernel32(),
        uia_adapter=uia,
    )
    return host, gui, uia


def test_list_controls_delegates_to_uia_layer_with_resolved_window() -> None:
    host, _gui, uia = _build_host_with_uia()

    result = host.list_controls(selector=WindowSelector(title="Dialog Host"))

    assert result["success"] is True
    assert result["count"] == 1
    assert result["controls"][0]["title"] == "Save"
    assert uia.calls[0][0] == "list_controls"
    assert uia.calls[0][1]["window_handle"] == 101


def test_set_control_text_focuses_window_and_returns_control_payload() -> None:
    host, gui, uia = _build_host_with_uia()

    result = host.set_control_text(
        selector=WindowSelector(title="Dialog Host"),
        control_selector=ControlSelector(automation_id="FileNameControlHost"),
        text=r"C:\tmp\artifact.txt",
    )

    assert result["success"] is True
    assert result["control"]["automation_id"] == "FileNameControlHost"
    assert gui.foreground == 101
    assert uia.calls[0][0] == "set_control_text"
    assert uia.calls[0][1]["text"] == r"C:\tmp\artifact.txt"


def test_invoke_dialog_action_uses_semantic_control_layer() -> None:
    host, _gui, uia = _build_host_with_uia()

    result = host.invoke_dialog_action(
        selector=WindowSelector(title="Dialog Host"),
        action="save",
    )

    assert result["success"] is True
    assert result["dialog_action"] == "save"
    assert result["control"]["title"] == "Save"
    assert uia.calls[0][0] == "invoke_dialog_action"


def test_windows_mcp_server_exposes_control_actions() -> None:
    original_host = windows_mcp_server._HOST
    host, _gui, _uia = _build_host_with_uia()
    windows_mcp_server._HOST = host
    try:
        listed = windows_mcp_server.list_controls(title="Dialog Host")
        edited = windows_mcp_server.set_control_text(
            title="Dialog Host",
            control_automation_id="FileNameControlHost",
            text=r"C:\tmp\artifact.txt",
        )
        invoked = windows_mcp_server.invoke_dialog_action(
            title="Dialog Host",
            dialog_action="save",
        )
    finally:
        windows_mcp_server._HOST = original_host

    assert listed["success"] is True
    assert listed["tool"] == "list_controls"
    assert edited["success"] is True
    assert edited["tool"] == "set_control_text"
    assert invoked["success"] is True
    assert invoked["tool"] == "invoke_dialog_action"


def test_close_window_prefers_semantic_tab_close_when_selector_clears() -> None:
    host, gui, uia = _build_host_with_uia()
    gui.windows[101]["title"] = "Document A - Notepad"

    result = host.close_window(selector=WindowSelector(title_contains="Document A"))

    assert result["success"] is True
    assert result["closed"] is True
    assert result["close_path"] == "semantic:关闭标签页"
    assert gui.closed == []
    assert uia.calls[0][0] == "invoke_control"
    assert gui.windows[101]["title"] == "Other Document - Notepad"


def test_close_window_falls_back_to_wm_close_when_semantic_close_is_unavailable() -> None:
    host, gui, uia = _build_host_with_uia()
    gui.windows[101]["title"] = "Dialog Host"

    def _invoke_control(**kwargs):
        uia.calls.append(("invoke_control", dict(kwargs)))
        raise RuntimeError("not available")

    uia.invoke_control = _invoke_control  # type: ignore[method-assign]
    original_post_message = gui.PostMessage

    def _post_message(hwnd: int, msg: int, wparam: int, lparam: int) -> None:
        original_post_message(hwnd, msg, wparam, lparam)
        gui.windows.pop(hwnd, None)

    gui.PostMessage = _post_message  # type: ignore[method-assign]

    result = host.close_window(selector=WindowSelector(title="Dialog Host"), timeout_seconds=0.01)

    assert result["success"] is True
    assert result["closed"] is True
    assert result["close_path"] == "wm_close"
    assert gui.closed == [101]
