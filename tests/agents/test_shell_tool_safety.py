# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import importlib.util


def _load_shell_safety_module():
    spec = importlib.util.find_spec("copaw.agents.tools.shell_safety")
    assert spec is not None, "shell_safety module missing"
    return importlib.import_module("copaw.agents.tools.shell_safety")


def test_validate_shell_command_allows_read_only_git_status() -> None:
    module = _load_shell_safety_module()
    decision = module.validate_shell_command("git status")

    assert decision.allowed is True
    assert decision.rule_id is None
    assert decision.reason is None


def test_validate_shell_command_blocks_git_reset_hard() -> None:
    module = _load_shell_safety_module()
    decision = module.validate_shell_command("git reset --hard HEAD")

    assert decision.allowed is False
    assert decision.rule_id == "destructive-git"
    assert "blocked" in (decision.reason or "").lower()


def test_validate_shell_command_blocks_recursive_powershell_delete() -> None:
    module = _load_shell_safety_module()
    decision = module.validate_shell_command(
        'Remove-Item -LiteralPath "." -Recurse -Force',
    )

    assert decision.allowed is False
    assert decision.rule_id == "recursive-delete"
    assert "blocked" in (decision.reason or "").lower()
