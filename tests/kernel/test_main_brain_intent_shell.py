# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from copaw.kernel.main_brain_intent_shell import detect_main_brain_intent_shell


@pytest.mark.parametrize(
    ("text", "expected_mode"),
    [
        ("先做个计划，再动手。", "plan"),
        ("review 这次聊天升级改动。", "review"),
        ("resume 上一个线程，继续推进。", "resume"),
        ("verify 这个结果是不是已经达标。", "verify"),
    ],
)
def test_main_brain_intent_shell_detects_plan_review_resume_verify_hints(
    text: str,
    expected_mode: str,
) -> None:
    result = detect_main_brain_intent_shell(text)

    assert result.mode_hint == expected_mode
    assert result.trigger_source != "none"
    assert result.confidence > 0.0
    assert result.matched_text


@pytest.mark.parametrize(
    "text",
    [
        "我要在3个月内做到月营收10万。",
        "那你开始吧。",
        "请看 src/plan/review.ts 这个文件。",
        "review_plan = True",
    ],
)
def test_main_brain_intent_shell_ignores_goal_setting_start_language_and_codeish_context(
    text: str,
) -> None:
    result = detect_main_brain_intent_shell(text)

    assert result.mode_hint == "none"
    assert result.trigger_source == "none"
    assert result.confidence == 0.0
    assert result.matched_text == ""
