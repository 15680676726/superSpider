# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import pytest

from copaw.adapters.desktop.windows_host import WindowsDesktopHost, WindowSelector


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


LIVE_WINDOWS_HOST_SKIP_REASON = (
    "Set COPAW_RUN_LIVE_DESKTOP_HOST_SMOKE=1 to run native Windows desktop host smoke coverage."
)


def _write_script(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body), encoding="utf-8")


def _wait_for_dialog_window(
    host: WindowsDesktopHost,
    *,
    process_id: int,
    title: str,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    last_windows: list[dict[str, object]] = []
    while time.monotonic() < deadline:
        matches = list(
            host.list_windows(
                selector=WindowSelector(process_id=process_id, title=title),
                include_hidden=True,
                limit=10,
            ).get("windows")
            or []
        )
        last_windows = matches
        for match in matches:
            if str(match.get("class_name") or "") == "#32770":
                return match
        time.sleep(0.25)
    raise AssertionError(
        f"Timed out waiting for dialog {title!r}; last matches={last_windows!r}",
    )


@pytest.mark.skipif(
    sys.platform != "win32" or not _env_flag("COPAW_RUN_LIVE_DESKTOP_HOST_SMOKE"),
    reason=LIVE_WINDOWS_HOST_SKIP_REASON,
)
def test_live_windows_host_can_confirm_native_save_dialog() -> None:
    host = WindowsDesktopHost()
    base = Path(tempfile.mkdtemp(prefix="copaw-filedialog-"))
    script_path = base / "save_dialog_app.py"
    result_path = base / "save_result.txt"
    chosen_path = base / "chosen-by-dialog.txt"
    _write_script(
        script_path,
        f"""
        import tkinter as tk
        from tkinter import filedialog
        from pathlib import Path

        root = tk.Tk()
        root.withdraw()
        selected = filedialog.asksaveasfilename(
            initialdir={str(base)!r},
            initialfile='initial-name.txt',
            title='CoPaw Save Dialog Smoke',
        )
        Path({str(result_path)!r}).write_text(selected, encoding='utf-8')
        """,
    )
    proc = subprocess.Popen([sys.executable, str(script_path)])
    try:
        dialog = _wait_for_dialog_window(
            host,
            process_id=proc.pid,
            title="CoPaw Save Dialog Smoke",
        )
        selector = WindowSelector(handle=int(dialog["handle"]))
        host.focus_window(selector=selector)
        host.press_keys(keys="Ctrl+A", selector=selector)
        host.type_text(text=str(chosen_path), selector=selector)
        host.press_keys(keys="Enter", selector=selector)
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if result_path.exists():
                break
            time.sleep(0.25)
        assert result_path.exists()
        assert Path(result_path.read_text(encoding="utf-8")) == chosen_path
    finally:
        try:
            proc.wait(timeout=5.0)
        except Exception:
            proc.kill()


@pytest.mark.skipif(
    sys.platform != "win32" or not _env_flag("COPAW_RUN_LIVE_DESKTOP_HOST_SMOKE"),
    reason=LIVE_WINDOWS_HOST_SKIP_REASON,
)
def test_live_windows_host_can_dismiss_native_error_dialog() -> None:
    host = WindowsDesktopHost()
    base = Path(tempfile.mkdtemp(prefix="copaw-errordialog-"))
    script_path = base / "error_dialog_app.py"
    result_path = base / "error_result.txt"
    _write_script(
        script_path,
        f"""
        import tkinter as tk
        from tkinter import messagebox
        from pathlib import Path

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('CoPaw Error Smoke', 'desktop host should dismiss this error dialog')
        Path({str(result_path)!r}).write_text('dismissed', encoding='utf-8')
        """,
    )
    proc = subprocess.Popen([sys.executable, str(script_path)])
    try:
        dialog = _wait_for_dialog_window(
            host,
            process_id=proc.pid,
            title="CoPaw Error Smoke",
        )
        selector = WindowSelector(handle=int(dialog["handle"]))
        host.focus_window(selector=selector)
        host.press_keys(keys="Enter", selector=selector)
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if result_path.exists():
                break
            time.sleep(0.25)
        assert result_path.exists()
        assert result_path.read_text(encoding="utf-8") == "dismissed"
    finally:
        try:
            proc.wait(timeout=5.0)
        except Exception:
            proc.kill()
