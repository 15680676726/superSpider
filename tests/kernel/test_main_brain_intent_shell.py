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


@pytest.mark.parametrize(
    "text",
    [
        '"plan" is just a label here',
        "what does review mean here?",
        "`/plan` is only an example command",
        "[/plan] is documentation, not an instruction",
        "\u8bf7\u628a\u201c\u5148\u505a\u4e2a\u8ba1\u5212\u201d\u8fd9\u53e5\u8bdd\u653e\u5230\u6807\u9898\u91cc",
        "\u8bf7\u628a\u5148\u505a\u4e2a\u8ba1\u5212\u8fd9\u51e0\u4e2a\u5b57\u653e\u5230\u6807\u9898\u91cc",
    ],
)
def test_main_brain_intent_shell_ignores_quoted_or_feature_discussion_language(
    text: str,
) -> None:
    result = detect_main_brain_intent_shell(text)

    assert result.mode_hint == "none"
    assert result.trigger_source == "none"
    assert result.confidence == 0.0
    assert result.matched_text == ""


def test_main_brain_intent_shell_still_detects_real_intent_when_text_also_mentions_a_path() -> None:
    result = detect_main_brain_intent_shell(
        "\u5148\u505a\u4e2a\u8ba1\u5212\uff0c\u7136\u540e\u770b src/app.py",
    )

    assert result.mode_hint == "plan"
    assert result.trigger_source == "keyword"
    assert result.confidence > 0.0
    assert result.matched_text


@pytest.mark.parametrize(
    ("text", "expected_mode", "expected_match", "min_confidence"),
    [
        ("\u5148\u505a\u4e2a\u8ba1\u5212\uff0c\u7136\u540e /review \u8fd9\u6b21\u6539\u52a8", "review", "/review", 0.98),
        ("review \u8fd9\u6b21\u6539\u52a8\uff0c\u6700\u540e /verify \u7ed3\u679c", "verify", "/verify", 0.98),
        ("review \u8fd9\u6b21\u6539\u52a8\uff0c\u540e\u9762\u5982\u679c\u9700\u8981\u518d\u505a\u4e2a\u8ba1\u5212", "review", "review ", 0.93),
        ("/review \u8fd9\u6b21\u6539\u52a8\uff0c\u7136\u540e /verify \u7ed3\u679c", "review", "/review", 0.98),
    ],
)
def test_main_brain_intent_shell_prioritizes_stronger_and_earlier_matches(
    text: str,
    expected_mode: str,
    expected_match: str,
    min_confidence: float,
) -> None:
    result = detect_main_brain_intent_shell(text)

    assert result.mode_hint == expected_mode
    assert result.trigger_source == "keyword"
    assert result.confidence >= min_confidence
    assert result.matched_text == expected_match
