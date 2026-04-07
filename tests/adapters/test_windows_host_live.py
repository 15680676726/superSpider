# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import pytest

from copaw.adapters.desktop.windows_host import WindowsDesktopHost, WindowSelector
from copaw.adapters.desktop.windows_uia import ControlSelector


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
    class_name: str | None = None,
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
            if class_name is None or str(match.get("class_name") or "") == class_name:
                return match
        time.sleep(0.25)
    raise AssertionError(
        f"Timed out waiting for dialog {title!r}; last matches={last_windows!r}",
    )


def _wait_for_result_file(path: Path, *, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.25)
    raise AssertionError(f"Timed out waiting for result file: {path}")


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
            class_name="#32770",
        )
        selector = WindowSelector(handle=int(dialog["handle"]))
        controls = host.list_controls(selector=selector)
        assert controls["count"] > 0
        host.set_control_text(
            selector=selector,
            control_selector=ControlSelector(control_type="Edit", title_contains="\u6587\u4ef6\u540d"),
            text=str(chosen_path),
        )
        host.invoke_dialog_action(selector=selector, action="save")
        _wait_for_result_file(result_path)
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
            class_name="#32770",
        )
        selector = WindowSelector(handle=int(dialog["handle"]))
        host.invoke_dialog_action(selector=selector, action="ok")
        _wait_for_result_file(result_path)
        assert result_path.read_text(encoding="utf-8") == "dismissed"
    finally:
        try:
            proc.wait(timeout=5.0)
        except Exception:
            proc.kill()


def _write_semantic_dialog_script(path: Path, result_path: Path) -> None:
    _write_script(
        path,
        f"""
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing

        $utf8 = New-Object System.Text.UTF8Encoding($false)
        $form = New-Object System.Windows.Forms.Form
        $form.Text = 'CoPaw Semantic Control Smoke'
        $form.Width = 360
        $form.Height = 220
        $form.StartPosition = 'CenterScreen'

        $textBox = New-Object System.Windows.Forms.TextBox
        $textBox.Width = 220
        $textBox.Left = 20
        $textBox.Top = 20
        $form.Controls.Add($textBox)

        $writeResult = {{
            param([string]$action)
            $payload = @{{ action = $action; text = $textBox.Text }} | ConvertTo-Json -Compress
            [System.IO.File]::WriteAllText({str(result_path)!r}, $payload, $utf8)
            $form.Close()
        }}

        $ok = New-Object System.Windows.Forms.Button
        $ok.Text = 'OK'
        $ok.Left = 20
        $ok.Top = 60
        $ok.Add_Click({{ & $writeResult 'confirm' }})
        $form.Controls.Add($ok)

        $cancel = New-Object System.Windows.Forms.Button
        $cancel.Text = 'Cancel'
        $cancel.Left = 120
        $cancel.Top = 60
        $cancel.Add_Click({{ & $writeResult 'cancel' }})
        $form.Controls.Add($cancel)

        $replace = New-Object System.Windows.Forms.Button
        $replace.Text = 'Replace'
        $replace.Left = 220
        $replace.Top = 60
        $replace.Add_Click({{ & $writeResult 'replace' }})
        $form.Controls.Add($replace)

        [System.Windows.Forms.Application]::Run($form)
        """,
    )


def _launch_semantic_dialog(base: Path) -> tuple[subprocess.Popen[bytes], Path]:
    script_path = base / "semantic_dialog_app.ps1"
    result_path = base / "semantic_dialog_result.json"
    _write_semantic_dialog_script(script_path, result_path)
    return (
        subprocess.Popen(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
        ),
        result_path,
    )


@pytest.mark.skipif(
    sys.platform != "win32" or not _env_flag("COPAW_RUN_LIVE_DESKTOP_HOST_SMOKE"),
    reason=LIVE_WINDOWS_HOST_SKIP_REASON,
)
def test_live_windows_host_can_set_control_text_and_confirm_dialog() -> None:
    host = WindowsDesktopHost()
    base = Path(tempfile.mkdtemp(prefix="copaw-semantic-confirm-"))
    proc, result_path = _launch_semantic_dialog(base)
    try:
        dialog = _wait_for_dialog_window(
            host,
            process_id=proc.pid,
            title="CoPaw Semantic Control Smoke",
        )
        selector = WindowSelector(handle=int(dialog["handle"]))
        host.set_control_text(
            selector=selector,
            control_selector=ControlSelector(control_type="Edit", found_index=0),
            text="semantic confirm payload",
        )
        host.invoke_dialog_action(selector=selector, action="confirm")
        _wait_for_result_file(result_path)
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        assert payload == {
            "action": "confirm",
            "text": "semantic confirm payload",
        }
    finally:
        try:
            proc.wait(timeout=5.0)
        except Exception:
            proc.kill()


@pytest.mark.skipif(
    sys.platform != "win32" or not _env_flag("COPAW_RUN_LIVE_DESKTOP_HOST_SMOKE"),
    reason=LIVE_WINDOWS_HOST_SKIP_REASON,
)
def test_live_windows_host_can_cancel_dialog_semantically() -> None:
    host = WindowsDesktopHost()
    base = Path(tempfile.mkdtemp(prefix="copaw-semantic-cancel-"))
    proc, result_path = _launch_semantic_dialog(base)
    try:
        dialog = _wait_for_dialog_window(
            host,
            process_id=proc.pid,
            title="CoPaw Semantic Control Smoke",
        )
        selector = WindowSelector(handle=int(dialog["handle"]))
        host.invoke_dialog_action(selector=selector, action="cancel")
        _wait_for_result_file(result_path)
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        assert payload["action"] == "cancel"
    finally:
        try:
            proc.wait(timeout=5.0)
        except Exception:
            proc.kill()


@pytest.mark.skipif(
    sys.platform != "win32" or not _env_flag("COPAW_RUN_LIVE_DESKTOP_HOST_SMOKE"),
    reason=LIVE_WINDOWS_HOST_SKIP_REASON,
)
def test_live_windows_host_can_trigger_replace_button_semantically() -> None:
    host = WindowsDesktopHost()
    base = Path(tempfile.mkdtemp(prefix="copaw-semantic-replace-"))
    proc, result_path = _launch_semantic_dialog(base)
    try:
        dialog = _wait_for_dialog_window(
            host,
            process_id=proc.pid,
            title="CoPaw Semantic Control Smoke",
        )
        selector = WindowSelector(handle=int(dialog["handle"]))
        host.invoke_dialog_action(selector=selector, action="replace")
        _wait_for_result_file(result_path)
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        assert payload["action"] == "replace"
    finally:
        try:
            proc.wait(timeout=5.0)
        except Exception:
            proc.kill()
