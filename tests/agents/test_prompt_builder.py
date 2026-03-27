# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from copaw.agents.prompt import DEFAULT_SYS_PROMPT, PromptBuilder


def test_prompt_builder_uses_builtin_core_prompt_without_workspace_files(
    tmp_path,
    caplog,
) -> None:
    caplog.set_level(logging.WARNING)

    prompt = PromptBuilder(tmp_path).build()

    assert prompt == DEFAULT_SYS_PROMPT
    assert "Spider Mesh" in prompt
    assert not caplog.records


def test_prompt_builder_ignores_workspace_prompt_files(
    tmp_path,
) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "---\nsummary: test\n---\n覆盖规则A",
        encoding="utf-8",
    )
    (tmp_path / "PROFILE.md").write_text(
        "偏好：默认中文，少废话。",
        encoding="utf-8",
    )

    prompt = PromptBuilder(tmp_path).build()

    assert prompt == DEFAULT_SYS_PROMPT
    assert "# AGENTS.md" not in prompt
    assert "覆盖规则A" not in prompt
    assert "# PROFILE.md" not in prompt
    assert "偏好：默认中文，少废话。" not in prompt
