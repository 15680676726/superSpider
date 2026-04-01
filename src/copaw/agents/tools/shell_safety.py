# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShellSafetyDecision:
    allowed: bool
    reason: str | None = None
    rule_id: str | None = None


_DESTRUCTIVE_GIT_MARKERS = (
    "git reset --hard",
    "git checkout --",
    "git clean -fd",
    "git clean -df",
)

_GIT_INTERNAL_PATH_MARKERS = (
    ".git/",
    ".git\\",
    ".git ",
    " hooks/",
    " hooks\\",
    " refs/",
    " refs\\",
)


def validate_shell_command(command: str) -> ShellSafetyDecision:
    normalized = (command or "").strip().casefold()
    if not normalized:
        return ShellSafetyDecision(True)

    if any(marker in normalized for marker in _DESTRUCTIVE_GIT_MARKERS):
        return ShellSafetyDecision(
            allowed=False,
            reason="Blocked by shell safety policy: destructive git command.",
            rule_id="destructive-git",
        )

    if "remove-item" in normalized and "-recurse" in normalized:
        return ShellSafetyDecision(
            allowed=False,
            reason="Blocked by shell safety policy: recursive delete command.",
            rule_id="recursive-delete",
        )

    if normalized.startswith("del ") and "/s" in normalized:
        return ShellSafetyDecision(
            allowed=False,
            reason="Blocked by shell safety policy: recursive delete command.",
            rule_id="recursive-delete",
        )

    if normalized.startswith("rmdir ") and "/s" in normalized:
        return ShellSafetyDecision(
            allowed=False,
            reason="Blocked by shell safety policy: recursive delete command.",
            rule_id="recursive-delete",
        )

    if any(marker in normalized for marker in _GIT_INTERNAL_PATH_MARKERS) and any(
        keyword in normalized
        for keyword in ("remove-item", "del ", "rmdir ", "rm ", "erase ", "move-item")
    ):
        return ShellSafetyDecision(
            allowed=False,
            reason="Blocked by shell safety policy: destructive access to git internals.",
            rule_id="git-internals",
        )

    return ShellSafetyDecision(True)


__all__ = ["ShellSafetyDecision", "validate_shell_command"]
