from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ALLOWED_BRANCH = "main"


@dataclass(frozen=True)
class BranchCheckResult:
    allowed: bool
    exit_code: int
    message: str


def evaluate_branch(
    branch_name: str,
    *,
    allowed_branch: str = DEFAULT_ALLOWED_BRANCH,
) -> BranchCheckResult:
    normalized = branch_name.strip()
    if normalized == allowed_branch:
        return BranchCheckResult(allowed=True, exit_code=0, message="ok")
    if not normalized:
        return BranchCheckResult(
            allowed=False,
            exit_code=1,
            message=(
                f"Blocked: could not determine the current branch. "
                f"Expected '{allowed_branch}'."
            ),
        )
    return BranchCheckResult(
        allowed=False,
        exit_code=1,
        message=(
            f"Blocked: current branch '{normalized}' is not '{allowed_branch}'. "
            "Work on main unless explicit approval was given for this task."
        ),
    )

def resolve_hooks_path(platform_name: str | None = None) -> str:
    platform_value = sys.platform if platform_name is None else platform_name
    if platform_value.startswith("win"):
        return ".githooks"
    return ".githooks/posix"


def build_install_command(
    repo_root: Path,
    *,
    platform_name: str | None = None,
) -> tuple[str, ...]:
    return (
        "git",
        "-C",
        str(repo_root),
        "config",
        "core.hooksPath",
        resolve_hooks_path(platform_name),
    )


def resolve_current_branch(repo_root: Path) -> str:
    completed = subprocess.run(
        ("git", "-C", str(repo_root), "branch", "--show-current"),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Block commits and pushes outside the main branch.",
    )
    parser.add_argument(
        "--branch",
        help="Use an explicit branch name instead of reading git state.",
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Repository root used when reading git state.",
    )
    parser.add_argument(
        "--allowed-branch",
        default=DEFAULT_ALLOWED_BRANCH,
        help="Branch name that is allowed to proceed.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo).resolve()
    branch_name = args.branch
    if branch_name is None:
        try:
            branch_name = resolve_current_branch(repo_root)
        except subprocess.CalledProcessError as exc:
            print(
                "Blocked: failed to read the current git branch.",
                file=sys.stderr,
            )
            if exc.stderr:
                print(exc.stderr.strip(), file=sys.stderr)
            return 1

    result = evaluate_branch(
        branch_name,
        allowed_branch=args.allowed_branch,
    )
    if not result.allowed:
        print(result.message, file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
