from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    from scripts.git_branch_guard import build_install_command
except ModuleNotFoundError:
    # Keep the script runnable both as an imported module and as
    # `python scripts/setup_git_hooks.py`.
    from git_branch_guard import build_install_command


HOOK_FILES = ("pre-commit", "pre-push")
WINDOWS_STALE_FILES = ("pre-commit.bat", "pre-push.bat", "pre-commit.cmd", "pre-push.cmd")


def build_windows_hook_script(python_executable: Path) -> str:
    shebang = python_executable.as_posix()
    return "\n".join(
        (
            f"#!{shebang}",
            "from __future__ import annotations",
            "",
            "import subprocess",
            "import sys",
            "from pathlib import Path",
            "",
            "REPO_ROOT = Path(__file__).resolve().parents[1]",
            "COMMAND = [",
            "    sys.executable,",
            "    str(REPO_ROOT / 'scripts' / 'git_branch_guard.py'),",
            "    '--repo',",
            "    str(REPO_ROOT),",
            "]",
            "raise SystemExit(subprocess.run(COMMAND, cwd=REPO_ROOT, check=False).returncode)",
            "",
        )
    )


def install_windows_hooks(repo_root: Path) -> None:
    hooks_root = repo_root / ".githooks"
    hooks_root.mkdir(parents=True, exist_ok=True)
    script_content = build_windows_hook_script(Path(sys.executable).resolve())
    for hook_name in HOOK_FILES:
        (hooks_root / hook_name).write_text(script_content, encoding="utf-8")
    for stale_name in WINDOWS_STALE_FILES:
        stale_path = hooks_root / stale_name
        if stale_path.exists():
            stale_path.unlink()


def ensure_hook_permissions(repo_root: Path) -> None:
    if sys.platform.startswith("win"):
        return
    hooks_root = repo_root / ".githooks" / "posix"
    for hook_name in HOOK_FILES:
        hook_path = hooks_root / hook_name
        if not hook_path.exists():
            continue
        hook_path.chmod(hook_path.stat().st_mode | 0o111)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if sys.platform.startswith("win"):
        install_windows_hooks(repo_root)
    subprocess.run(
        build_install_command(repo_root),
        check=True,
        text=True,
        encoding="utf-8",
    )
    ensure_hook_permissions(repo_root)
    print("Configured git hooks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
