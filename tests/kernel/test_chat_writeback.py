# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.industry.chat_writeback import build_chat_writeback_plan
from copaw.kernel.query_execution_shared import (
    _build_chat_writeback_plan_from_model_decision,
)


class _FakeDecision:
    def __init__(self) -> None:
        self.approved_targets = ["backlog"]
        self.strategy = None
        self.goal = type(
            "GoalPayload",
            (),
            {
                "title": None,
                "summary": "月入10万且零亏损",
                "plan_steps": [],
            },
        )()
        self.schedule = None


def test_build_chat_writeback_plan_preserves_model_supplied_goal_fields() -> None:
    plan = build_chat_writeback_plan(
        "改成先做现场验证再做规模复制",
        approved_classifications=["backlog"],
        goal_title="现场验证主线",
        goal_summary="改成先做现场验证再做规模复制",
        goal_plan_steps=["先做现场验证", "再做规模复制"],
    )

    assert plan is not None
    assert plan.goal is not None
    assert plan.goal.title == "现场验证主线"
    assert plan.goal.summary == "改成先做现场验证再做规模复制"
    assert plan.goal.plan_steps == ["先做现场验证", "再做规模复制"]


def test_build_chat_writeback_plan_from_model_decision_structures_fuzzy_goal() -> None:
    plan = _build_chat_writeback_plan_from_model_decision(
        text="月入10万且零亏损",
        decision=_FakeDecision(),
    )

    assert plan is not None
    assert plan.goal is not None
    assert plan.goal.title == "月度收益目标校准"
    assert "目标结果：月入10万且零亏损" in plan.goal.summary
    assert "关键待校准参数：" in plan.goal.summary
    assert "可用本金/账户规模" in plan.goal.summary
    assert plan.goal.plan_steps
    assert "风险边界" in plan.goal.plan_steps[0] or "风险边界" in plan.goal.plan_steps[1]
