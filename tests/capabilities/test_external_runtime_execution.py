from __future__ import annotations


def test_append_args_uses_windows_safe_quoting_for_paths_with_spaces(
    monkeypatch,
) -> None:
    from copaw.capabilities.external_runtime_execution import _append_args
    from copaw.capabilities import external_runtime_execution as runtime_module

    monkeypatch.setattr(runtime_module.os, "name", "nt")

    command = _append_args(
        '"C:\\tooling\\black.exe"',
        ["C:\\Users\\test user\\bad format.py"],
    )

    assert command.startswith('"C:\\tooling\\black.exe" ')
    assert '"C:\\Users\\test user\\bad format.py"' in command
    assert "'C:\\Users\\test user\\bad format.py'" not in command
