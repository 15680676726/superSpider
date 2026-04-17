from __future__ import annotations

from pathlib import Path

from scripts.git_branch_guard import (
    build_install_command,
    evaluate_branch,
    resolve_hooks_path,
)


def test_evaluate_branch_allows_main() -> None:
    result = evaluate_branch("main")

    assert result.allowed is True
    assert result.exit_code == 0
    assert result.message == "ok"


def test_evaluate_branch_rejects_non_main() -> None:
    result = evaluate_branch("feature/runtime-tail")

    assert result.allowed is False
    assert result.exit_code == 1
    assert "main" in result.message


def test_build_install_command_targets_versioned_hooks_path() -> None:
    repo_root = Path("D:/word/copaw")
    command = build_install_command(repo_root, platform_name="win32")

    assert command == (
        "git",
        "-C",
        str(repo_root),
        "config",
        "core.hooksPath",
        ".githooks",
    )


def test_resolve_hooks_path_uses_windows_hooks_on_win32() -> None:
    assert resolve_hooks_path("win32") == ".githooks"


def test_resolve_hooks_path_uses_posix_hooks_elsewhere() -> None:
    assert resolve_hooks_path("linux") == ".githooks/posix"
