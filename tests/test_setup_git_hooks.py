from __future__ import annotations

from pathlib import Path

from scripts.setup_git_hooks import build_windows_hook_script


def test_build_windows_hook_script_uses_absolute_python_shebang() -> None:
    script = build_windows_hook_script(Path("C:/Python312/python.exe"))

    lines = script.splitlines()
    assert lines[0] == "#!C:/Python312/python.exe"
    assert "git_branch_guard.py" in script
    assert "--repo" in script
