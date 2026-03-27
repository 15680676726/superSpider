from __future__ import annotations

from types import SimpleNamespace

from copaw.adapters.desktop import windows_mcp_server
from copaw.adapters.desktop.windows_host import WindowSelector, WindowsDesktopHost


class _FakeWin32GUI:
    def __init__(self) -> None:
        self.foreground = 101
        self.closed: list[int] = []
        self.show_calls: list[tuple[int, int]] = []
        self.windows = {
            101: {
                "title": "Notepad",
                "class_name": "Notepad",
                "visible": True,
                "enabled": True,
                "rect": (10, 20, 210, 120),
                "iconic": False,
            },
            202: {
                "title": "Calculator",
                "class_name": "CalcFrame",
                "visible": True,
                "enabled": True,
                "rect": (300, 100, 500, 300),
                "iconic": True,
            },
            303: {
                "title": "Popup",
                "class_name": "#32770",
                "visible": True,
                "enabled": True,
                "rect": (320, 120, 520, 280),
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

    def GetWindowRect(self, hwnd: int) -> tuple[int, int, int, int]:
        return tuple(self.windows[hwnd]["rect"])

    def GetForegroundWindow(self) -> int:
        return int(self.foreground)

    def IsIconic(self, hwnd: int) -> bool:
        return bool(self.windows[hwnd]["iconic"])

    def ShowWindow(self, hwnd: int, command: int) -> None:
        self.show_calls.append((hwnd, command))
        self.windows[hwnd]["iconic"] = False

    def SetForegroundWindow(self, hwnd: int) -> None:
        self.foreground = hwnd

    def PostMessage(self, hwnd: int, msg: int, wparam: int, lparam: int) -> None:
        _ = (msg, wparam, lparam)
        self.closed.append(hwnd)


class _FakeWin32Process:
    def GetWindowThreadProcessId(self, hwnd: int) -> tuple[int, int]:
        mapping = {101: 5001, 202: 6002, 303: 7003, 404: 5004}
        return 1, mapping[hwnd]


class _FakeWin32API:
    def __init__(self) -> None:
        self.cursor_positions: list[tuple[int, int]] = []
        self.mouse_events: list[tuple[int, int, int, int, int]] = []

    def SetCursorPos(self, coords: tuple[int, int]) -> None:
        self.cursor_positions.append(coords)

    def mouse_event(self, event: int, x: int, y: int, data: int, extra: int) -> None:
        self.mouse_events.append((event, x, y, data, extra))

    def VkKeyScan(self, token: str) -> int:
        if token == "!":
            return (1 << 8) | 49
        return -1


class _FakeUser32:
    def __init__(self, gui: _FakeWin32GUI | None = None) -> None:
        self._gui = gui
        self.calls: list[int] = []
        self.attach_calls: list[tuple[int, int, bool]] = []
        self.allow_calls: list[int] = []
        self.key_events: list[tuple[int, int, int, int]] = []
        self._attached = False

    def SendInput(self, count: int, _array, _size: int) -> int:
        self.calls.append(count)
        return count

    def AttachThreadInput(self, source_thread: int, target_thread: int, attach: bool) -> int:
        self.attach_calls.append((source_thread, target_thread, attach))
        self._attached = bool(attach)
        return 1

    def AllowSetForegroundWindow(self, process_id: int) -> int:
        self.allow_calls.append(process_id)
        return 1

    def BringWindowToTop(self, hwnd: int) -> int:
        if self._gui is not None:
            self._gui.foreground = hwnd
        return 1

    def SetActiveWindow(self, hwnd: int) -> int:
        if self._gui is not None:
            self._gui.foreground = hwnd
        return hwnd

    def SetFocus(self, hwnd: int) -> int:
        if self._gui is not None:
            self._gui.foreground = hwnd
        return hwnd

    def keybd_event(self, key: int, scan_code: int, flags: int, extra_info: int) -> None:
        self.key_events.append((key, scan_code, flags, extra_info))


class _FakeKernel32:
    def GetCurrentThreadId(self) -> int:
        return 77


class _AttachOnlyUser32(_FakeUser32):
    def BringWindowToTop(self, hwnd: int) -> int:
        _ = hwnd
        return 1

    def SetActiveWindow(self, hwnd: int) -> int:
        return hwnd

    def SetFocus(self, hwnd: int) -> int:
        return hwnd


class _ModalStealingUser32(_FakeUser32):
    def SendInput(self, count: int, _array, _size: int) -> int:
        result = super().SendInput(count, _array, _size)
        if self._gui is not None:
            self._gui.foreground = 303
        return result


def _build_host() -> tuple[WindowsDesktopHost, _FakeWin32GUI, _FakeWin32API, _FakeUser32]:
    gui = _FakeWin32GUI()
    api = _FakeWin32API()
    user32 = _FakeUser32(gui)
    host = WindowsDesktopHost(
        platform_name="win32",
        win32gui_module=gui,
        win32process_module=_FakeWin32Process(),
        win32api_module=api,
        win32con_module=SimpleNamespace(
            MOUSEEVENTF_LEFTDOWN=2,
            MOUSEEVENTF_LEFTUP=4,
            MOUSEEVENTF_RIGHTDOWN=8,
            MOUSEEVENTF_RIGHTUP=16,
            SW_RESTORE=9,
            SW_SHOW=5,
            WM_CLOSE=16,
            VK_MENU=18,
            VK_BACK=8,
            VK_CONTROL=17,
            VK_DELETE=46,
            VK_DOWN=40,
            VK_END=35,
            VK_ESCAPE=27,
            VK_HOME=36,
            VK_LEFT=37,
            VK_LWIN=91,
            VK_NEXT=34,
            VK_PRIOR=33,
            VK_RETURN=13,
            VK_RIGHT=39,
            VK_SHIFT=16,
            VK_SPACE=32,
            VK_TAB=9,
            VK_UP=38,
        ),
        user32=user32,
        kernel32=_FakeKernel32(),
    )
    return host, gui, api, user32


class _ForegroundAttachGUI(_FakeWin32GUI):
    def __init__(self, user32: _FakeUser32) -> None:
        super().__init__()
        self._user32 = user32
        self.foreground = 101

    def SetForegroundWindow(self, hwnd: int) -> None:
        if not self._user32._attached:
            raise RuntimeError((0, "SetForegroundWindow", "No error message is available"))
        self.foreground = hwnd


def test_list_windows_filters_matches_and_sorts_foreground_first() -> None:
    host, _gui, _api, _user32 = _build_host()

    result = host.list_windows(
        selector=WindowSelector(title_contains="a"),
        include_hidden=False,
        limit=10,
    )

    assert result["success"] is True
    assert result["count"] == 2
    assert result["windows"][0]["handle"] == 101
    assert result["windows"][1]["handle"] == 202


def test_click_relative_to_window_translates_coordinates_and_focuses() -> None:
    host, gui, api, _user32 = _build_host()

    result = host.click(
        x=5,
        y=10,
        selector=WindowSelector(title="Calculator"),
        relative_to_window=True,
    )

    assert result["success"] is True
    assert result["x"] == 305
    assert result["y"] == 110
    assert api.cursor_positions == [(305, 110)]
    assert gui.foreground == 202


def test_type_text_and_press_keys_dispatch_input_events() -> None:
    host, gui, _api, user32 = _build_host()

    typed = host.type_text(
        text="hi",
        selector=WindowSelector(title="Notepad"),
    )
    pressed = host.press_keys(keys="Ctrl+L", selector=WindowSelector(title="Notepad"))

    assert typed["success"] is True
    assert typed["char_count"] == 2
    assert pressed["success"] is True
    assert pressed["keys"] == ["Ctrl", "L"]
    assert gui.foreground == 101
    assert user32.calls == [4, 4]


def test_verify_window_focus_reports_actual_foreground_state() -> None:
    host, gui, _api, _user32 = _build_host()

    gui.foreground = 202
    verified = host.verify_window_focus(selector=WindowSelector(title="Calculator"))

    assert verified["success"] is True
    assert verified["window"]["handle"] == 202
    assert verified["is_foreground"] is True
    assert verified["foreground_window"]["handle"] == 202


def test_verify_window_focus_rejects_ambiguous_selector() -> None:
    host, gui, _api, _user32 = _build_host()
    gui.windows[404] = {
        "title": "Notepad",
        "class_name": "Notepad",
        "visible": True,
        "enabled": True,
        "rect": (30, 40, 230, 140),
        "iconic": False,
    }
    gui.foreground = 101

    try:
        host.verify_window_focus(selector=WindowSelector(title="Notepad"))
    except RuntimeError as exc:
        assert "ambiguous" in str(exc).lower()
    else:
        raise AssertionError("Expected ambiguous selector to be rejected")


def test_list_windows_skips_uninspectable_window_handles() -> None:
    host, gui, _api, _user32 = _build_host()
    gui.windows[505] = {
        "title": "Ghost Window",
        "class_name": "Ghost",
        "visible": True,
        "enabled": True,
        "rect": (0, 0, 50, 50),
        "iconic": False,
    }

    result = host.list_windows(selector=WindowSelector(), include_hidden=False, limit=10)

    assert result["success"] is True
    handles = [window["handle"] for window in result["windows"]]
    assert 505 not in handles
    assert result["count"] == 3


def test_type_text_fails_when_modal_steals_focus_during_input() -> None:
    gui = _FakeWin32GUI()
    api = _FakeWin32API()
    user32 = _ModalStealingUser32(gui)
    host = WindowsDesktopHost(
        platform_name="win32",
        win32gui_module=gui,
        win32process_module=_FakeWin32Process(),
        win32api_module=api,
        win32con_module=SimpleNamespace(
            MOUSEEVENTF_LEFTDOWN=2,
            MOUSEEVENTF_LEFTUP=4,
            MOUSEEVENTF_RIGHTDOWN=8,
            MOUSEEVENTF_RIGHTUP=16,
            SW_RESTORE=9,
            SW_SHOW=5,
            WM_CLOSE=16,
            VK_MENU=18,
            VK_BACK=8,
            VK_CONTROL=17,
            VK_DELETE=46,
            VK_DOWN=40,
            VK_END=35,
            VK_ESCAPE=27,
            VK_HOME=36,
            VK_LEFT=37,
            VK_LWIN=91,
            VK_NEXT=34,
            VK_PRIOR=33,
            VK_RETURN=13,
            VK_RIGHT=39,
            VK_SHIFT=16,
            VK_SPACE=32,
            VK_TAB=9,
            VK_UP=38,
        ),
        user32=user32,
        kernel32=_FakeKernel32(),
    )

    try:
        host.type_text(text="blocked", selector=WindowSelector(title="Notepad"))
    except RuntimeError as exc:
        assert "modal interruption" in str(exc).lower()
    else:
        raise AssertionError("Expected modal focus loss to raise an error")


def test_modal_interruption_error_exposes_structured_failure_details() -> None:
    original_host = windows_mcp_server._HOST
    gui = _FakeWin32GUI()
    api = _FakeWin32API()
    user32 = _ModalStealingUser32(gui)
    host = WindowsDesktopHost(
        platform_name="win32",
        win32gui_module=gui,
        win32process_module=_FakeWin32Process(),
        win32api_module=api,
        win32con_module=SimpleNamespace(
            MOUSEEVENTF_LEFTDOWN=2,
            MOUSEEVENTF_LEFTUP=4,
            MOUSEEVENTF_RIGHTDOWN=8,
            MOUSEEVENTF_RIGHTUP=16,
            SW_RESTORE=9,
            SW_SHOW=5,
            WM_CLOSE=16,
            VK_MENU=18,
            VK_BACK=8,
            VK_CONTROL=17,
            VK_DELETE=46,
            VK_DOWN=40,
            VK_END=35,
            VK_ESCAPE=27,
            VK_HOME=36,
            VK_LEFT=37,
            VK_LWIN=91,
            VK_NEXT=34,
            VK_PRIOR=33,
            VK_RETURN=13,
            VK_RIGHT=39,
            VK_SHIFT=16,
            VK_SPACE=32,
            VK_TAB=9,
            VK_UP=38,
        ),
        user32=user32,
        kernel32=_FakeKernel32(),
    )
    windows_mcp_server._HOST = host

    try:
        result = windows_mcp_server.type_text(text="blocked", title="Notepad")
    finally:
        windows_mcp_server._HOST = original_host

    assert result["success"] is False
    assert result["tool"] == "type_text"
    assert result["error_code"] == "modal_interruption"
    assert result["error_details"]["target_window"]["handle"] == 101
    assert result["error_details"]["foreground_window"]["handle"] == 303
    assert result["error_details"]["action_name"] == "type_text"


def test_write_document_file_creates_and_rereads_exact_content(tmp_path) -> None:
    host, _gui, _api, _user32 = _build_host()
    target = tmp_path / "desktop-note.txt"

    result = host.write_document_file(path=str(target), content="hello desktop")

    assert result["success"] is True
    assert result["created"] is True
    assert result["existed_before"] is False
    assert result["saved"] is True
    assert result["verification"]["reopened"] is True
    assert result["verification"]["post_write_reread_verified"] is True
    assert result["bytes_written"] == len("hello desktop".encode("utf-8"))
    assert result["verified_content"] == "hello desktop"
    assert target.read_text(encoding="utf-8") == "hello desktop"


def test_edit_document_file_reopens_and_verifies_updated_content(tmp_path) -> None:
    host, _gui, _api, _user32 = _build_host()
    target = tmp_path / "desktop-note.txt"
    target.write_text("hello old desktop", encoding="utf-8")

    result = host.edit_document_file(
        path=str(target),
        find_text="old",
        replace_text="new",
    )

    assert result["success"] is True
    assert result["replacements"] == 1
    assert result["created"] is False
    assert result["existed_before"] is True
    assert result["saved"] is True
    assert result["verification"]["reopened"] is True
    assert result["verification"]["post_write_reread_verified"] is True
    assert result["verified_content"] == "hello new desktop"
    assert target.read_text(encoding="utf-8") == "hello new desktop"


def test_wait_for_window_returns_match_without_sleeping() -> None:
    host, _gui, _api, _user32 = _build_host()

    result = host.wait_for_window(
        selector=WindowSelector(process_id=6002),
        timeout_seconds=0.1,
        poll_interval_seconds=0.01,
    )

    assert result["success"] is True
    assert result["window"]["handle"] == 202


def test_focus_window_uses_thread_attach_fallback_when_foreground_switch_is_blocked() -> None:
    user32 = _AttachOnlyUser32()
    gui = _ForegroundAttachGUI(user32)
    user32._gui = gui
    host = WindowsDesktopHost(
        platform_name="win32",
        win32gui_module=gui,
        win32process_module=_FakeWin32Process(),
        win32api_module=_FakeWin32API(),
        win32con_module=SimpleNamespace(
            MOUSEEVENTF_LEFTDOWN=2,
            MOUSEEVENTF_LEFTUP=4,
            MOUSEEVENTF_RIGHTDOWN=8,
            MOUSEEVENTF_RIGHTUP=16,
            SW_RESTORE=9,
            SW_SHOW=5,
            WM_CLOSE=16,
            VK_MENU=18,
            VK_BACK=8,
            VK_CONTROL=17,
            VK_DELETE=46,
            VK_DOWN=40,
            VK_END=35,
            VK_ESCAPE=27,
            VK_HOME=36,
            VK_LEFT=37,
            VK_LWIN=91,
            VK_NEXT=34,
            VK_PRIOR=33,
            VK_RETURN=13,
            VK_RIGHT=39,
            VK_SHIFT=16,
            VK_SPACE=32,
            VK_TAB=9,
            VK_UP=38,
        ),
        user32=user32,
        kernel32=_FakeKernel32(),
    )

    result = host.focus_window(selector=WindowSelector(title="Calculator"))

    assert result["success"] is True
    assert result["window"]["handle"] == 202
    assert gui.foreground == 202
    assert user32.attach_calls == [
        (77, 1, True),
        (77, 1, False),
    ]
