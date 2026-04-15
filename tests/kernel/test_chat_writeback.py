# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace
import pytest

from copaw.industry.chat_writeback import build_chat_writeback_plan
from copaw.kernel import query_execution_writeback as writeback_module
from copaw.kernel.query_execution_shared import (
    _build_chat_writeback_plan_from_model_decision,
)


def test_chat_writeback_decision_cache_evicts_least_recently_used_entry() -> None:
    original_max = writeback_module._CHAT_WRITEBACK_MODEL_CACHE_MAX
    decision_a = writeback_module._ChatWritebackModelDecision(intent_kind="chat")
    decision_b = writeback_module._ChatWritebackModelDecision(intent_kind="discussion")
    decision_c = writeback_module._ChatWritebackModelDecision(intent_kind="status-query")

    writeback_module.clear_chat_writeback_decision_cache()
    writeback_module._CHAT_WRITEBACK_MODEL_CACHE_MAX = 2
    try:
        writeback_module._cache_chat_writeback_decision("a", decision_a)
        writeback_module._cache_chat_writeback_decision("b", decision_b)

        assert writeback_module._get_cached_chat_writeback_decision("a") == decision_a

        writeback_module._cache_chat_writeback_decision("c", decision_c)

        assert writeback_module._get_cached_chat_writeback_decision("a") == decision_a
        assert writeback_module._get_cached_chat_writeback_decision("b") is None
        assert writeback_module._get_cached_chat_writeback_decision("c") == decision_c
    finally:
        writeback_module._CHAT_WRITEBACK_MODEL_CACHE_MAX = original_max
        writeback_module.clear_chat_writeback_decision_cache()


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
class _FakeStructuredDecisionModel:
    stream = False

    async def __call__(self, *, messages, structured_model=None, **kwargs):
        _ = (messages, kwargs)
        assert structured_model is not None
        return SimpleNamespace(
            metadata=structured_model(
                intent_kind="execute-task",
                intent_confidence=0.97,
                intent_signals=["model-actionable"],
                should_writeback=True,
                approved_targets=["backlog"],
                kickoff_allowed=True,
                confidence=0.97,
                rationale="model-driven",
            ),
        )


class _FakeMalformedStructuredDecisionModel:
    stream = False

    async def __call__(self, *, messages, structured_model=None, **kwargs):
        _ = (messages, kwargs)
        assert structured_model is not None
        return SimpleNamespace(
            metadata=structured_model(
                intent_kind="execute-task",
                intent_confidence=0.93,
                intent_signals=["model-actionable"],
                should_writeback=True,
                approved_targets=["status-query"],
                kickoff_allowed=True,
                team_role_gap_action="",
                confidence=0.93,
                rationale="malformed-but-recoverable",
            ),
        )


class _FakeConservativeStructuredDecisionModel:
    stream = False

    async def __call__(self, *, messages, structured_model=None, **kwargs):
        _ = (messages, kwargs)
        assert structured_model is not None
        return SimpleNamespace(
            metadata=structured_model(
                intent_kind="chat",
                intent_confidence=0.92,
                intent_signals=["too-conservative"],
                should_writeback=False,
                approved_targets=[],
                kickoff_allowed=False,
                confidence=0.92,
                rationale="conservative-model",
            ),
        )


def test_actionable_content_creation_request_does_not_degrade_into_plain_chat(
    monkeypatch,
) -> None:
    writeback_module.clear_chat_writeback_decision_cache()
    monkeypatch.setattr(
        writeback_module,
        "_CHAT_WRITEBACK_DECISION_MODEL_FACTORY",
        lambda: _FakeStructuredDecisionModel(),
        raising=False,
    )

    decision = writeback_module.resolve_chat_writeback_model_decision_sync(
        text="现在去写一篇短篇小说，保存成实际文件，并完成后主动告诉我结果。",
    )

    assert decision is not None
    assert decision.intent_kind == "execute-task"
    assert decision.should_writeback is True
    assert "backlog" in decision.approved_targets
    assert decision.kickoff_allowed is True


def test_chat_writeback_decision_sanitizes_malformed_model_enum_values(
    monkeypatch,
) -> None:
    writeback_module.clear_chat_writeback_decision_cache()
    monkeypatch.setattr(
        writeback_module,
        "_CHAT_WRITEBACK_DECISION_MODEL_FACTORY",
        lambda: _FakeMalformedStructuredDecisionModel(),
        raising=False,
    )

    decision = writeback_module.resolve_chat_writeback_model_decision_sync(
        text="现在去写一篇短篇小说，保存成实际文件，并且完成后主动告诉我结果。",
    )

    assert decision is not None
    assert decision.intent_kind == "execute-task"
    assert decision.should_writeback is True
    assert decision.approved_targets == []
    assert decision.team_role_gap_action is None


def test_chat_writeback_decision_prefers_model_for_actionable_creation_request(
    monkeypatch,
) -> None:
    writeback_module.clear_chat_writeback_decision_cache()
    monkeypatch.setattr(
        writeback_module,
        "_CHAT_WRITEBACK_DECISION_MODEL_FACTORY",
        lambda: _FakeStructuredDecisionModel(),
        raising=False,
    )

    decision = asyncio.run(
        writeback_module.resolve_chat_writeback_model_decision(
            text="现在去写一篇短篇小说，保存成实际文件，并完成后主动告诉我结果。",
        ),
    )

    assert decision is not None
    assert decision.intent_kind == "execute-task"
    assert decision.should_writeback is True
    assert decision.kickoff_allowed is True
    assert decision.intent_signals == ["model-actionable"]


def test_actionable_request_raises_when_chat_writeback_model_is_unavailable(
    monkeypatch,
) -> None:
    writeback_module.clear_chat_writeback_decision_cache()
    monkeypatch.setattr(
        writeback_module,
        "_CHAT_WRITEBACK_DECISION_MODEL_FACTORY",
        lambda: None,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="unavailable"):
        asyncio.run(
            writeback_module.resolve_chat_writeback_model_decision(
                text="现在去写一篇短篇小说，保存成实际文件，完成后主动告诉我结果。",
            ),
        )


class _SlowStructuredDecisionModel:
    stream = False

    async def __call__(self, *, messages, structured_model=None, **kwargs):
        _ = (messages, structured_model, kwargs)
        await asyncio.sleep(0.05)
        return SimpleNamespace(metadata={})


def test_chat_writeback_model_timeout_default_is_300_seconds() -> None:
    assert writeback_module._CHAT_WRITEBACK_MODEL_TIMEOUT_SECONDS == 300.0


def test_direct_browser_execution_request_falls_back_to_heuristic_when_model_is_conservative(
    monkeypatch,
) -> None:
    writeback_module.clear_chat_writeback_decision_cache()
    monkeypatch.setattr(
        writeback_module,
        "_CHAT_WRITEBACK_DECISION_MODEL_FACTORY",
        lambda: _FakeConservativeStructuredDecisionModel(),
        raising=False,
    )

    decision = asyncio.run(
        writeback_module.resolve_chat_writeback_model_decision(
            text=(
                "Use the mounted browser capability right now. "
                "Open https://example.com and save a screenshot to C:\\temp\\probe.png."
            ),
        ),
    )

    assert decision is not None
    assert decision.intent_kind == "execute-task"
    assert decision.kickoff_allowed is True
    assert "direct-execution-request" in decision.intent_signals
    assert decision.risky_actuation_surface == "browser"


def test_actionable_request_raises_when_chat_writeback_model_times_out(
    monkeypatch,
) -> None:
    writeback_module.clear_chat_writeback_decision_cache()
    monkeypatch.setattr(
        writeback_module,
        "_CHAT_WRITEBACK_DECISION_MODEL_FACTORY",
        lambda: _SlowStructuredDecisionModel(),
        raising=False,
    )
    monkeypatch.setattr(
        writeback_module,
        "_CHAT_WRITEBACK_MODEL_TIMEOUT_SECONDS",
        0.01,
        raising=False,
    )

    with pytest.raises(TimeoutError, match="timed out"):
        asyncio.run(
            writeback_module.resolve_chat_writeback_model_decision(
                text="现在去写一篇短篇小说，保存成实际文件，完成后主动告诉我结果。",
            ),
        )


def test_direct_browser_execution_request_falls_back_to_heuristic_when_model_times_out(
    monkeypatch,
) -> None:
    writeback_module.clear_chat_writeback_decision_cache()
    monkeypatch.setattr(
        writeback_module,
        "_CHAT_WRITEBACK_DECISION_MODEL_FACTORY",
        lambda: _SlowStructuredDecisionModel(),
        raising=False,
    )
    monkeypatch.setattr(
        writeback_module,
        "_CHAT_WRITEBACK_MODEL_TIMEOUT_SECONDS",
        0.01,
        raising=False,
    )

    decision = asyncio.run(
        writeback_module.resolve_chat_writeback_model_decision(
            text=(
                "Use the mounted browser capability right now. "
                "Open https://example.com and save a screenshot to C:\\temp\\probe.png."
            ),
        ),
    )

    assert decision is not None
    assert decision.intent_kind == "execute-task"
    assert decision.kickoff_allowed is True
    assert "direct-execution-request" in decision.intent_signals
    assert decision.risky_actuation_surface == "browser"
