# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.query_execution_intent_policy import (
    is_hypothetical_control_text,
    looks_like_goal_setting_text,
)
from copaw.kernel.query_execution_shared import (
    _is_hypothetical_control_text as shared_is_hypothetical_control_text,
    _looks_like_goal_setting_text as shared_looks_like_goal_setting_text,
)
from copaw.kernel.query_execution_writeback import (
    _is_hypothetical_control_text as writeback_is_hypothetical_control_text,
    _looks_like_goal_setting_text as writeback_looks_like_goal_setting_text,
)


def test_goal_setting_policy_stays_aligned_across_query_and_writeback() -> None:
    cases = {
        "我要把月营收做到 10 万": True,
        "交给你推进这个增长目标": True,
        "如果我说月入 10 万，你会怎么做？": False,
        "这个目标可行吗？": False,
        "先聊聊这个行业方向": False,
    }

    for text, expected in cases.items():
        assert looks_like_goal_setting_text(text) is expected
        assert shared_looks_like_goal_setting_text(text) is expected
        assert writeback_looks_like_goal_setting_text(text) is expected


def test_hypothetical_control_policy_stays_aligned_across_query_and_writeback() -> None:
    cases = {
        "如果我说帮我执行，你会怎么做": True,
        "what if I say execute this": True,
        "我要你现在执行": False,
        "继续推进这个任务": False,
    }

    for text, expected in cases.items():
        assert is_hypothetical_control_text(text) is expected
        assert shared_is_hypothetical_control_text(text) is expected
        assert writeback_is_hypothetical_control_text(text) is expected
