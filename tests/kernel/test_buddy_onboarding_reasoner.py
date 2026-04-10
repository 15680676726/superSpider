# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.buddy_onboarding_reasoner import (
    _BUDDY_ONBOARDING_REASONER_PROMPT,
    ModelDrivenBuddyOnboardingReasoner,
)
from copaw.state import HumanProfile


class _StubProviderRuntime:
    def get_active_chat_model(self):  # pragma: no cover - construction stub only
        return object()


class _FakeChatResponse:
    def __init__(self, *, metadata: dict[str, object]) -> None:
        self.metadata = metadata
        self.content = ""


class _FakeChatModel:
    def __init__(self, *, metadata: dict[str, object]) -> None:
        self._metadata = metadata

    async def __call__(self, *, messages, structured_model=None):  # pragma: no cover - async adapter
        _ = (messages, structured_model)
        return _FakeChatResponse(metadata=self._metadata)


def test_model_driven_reasoner_defaults_to_live_safe_timeout() -> None:
    reasoner = ModelDrivenBuddyOnboardingReasoner(
        provider_runtime=_StubProviderRuntime(),
    )

    assert reasoner._reasoning_timeout_seconds == 45.0  # pylint: disable=protected-access


def test_model_driven_reasoner_keeps_explicit_timeout_override() -> None:
    reasoner = ModelDrivenBuddyOnboardingReasoner(
        provider_runtime=_StubProviderRuntime(),
        reasoning_timeout_seconds=22.0,
    )

    assert reasoner._reasoning_timeout_seconds == 22.0  # pylint: disable=protected-access


def test_reasoner_prompt_declares_exact_response_fields() -> None:
    assert '"recommended_direction"' in _BUDDY_ONBOARDING_REASONER_PROMPT
    assert '"candidate_directions"' in _BUDDY_ONBOARDING_REASONER_PROMPT
    assert '"next_question"' in _BUDDY_ONBOARDING_REASONER_PROMPT


def test_model_driven_reasoner_normalizes_real_main_direction_alias() -> None:
    reasoner = ModelDrivenBuddyOnboardingReasoner(
        provider_runtime=_StubProviderRuntime(),
        model_factory=lambda: _FakeChatModel(
            metadata={
                "finished": True,
                "next_question": "",
                "real_main_direction": "建立稳定的股票交易路径",
                "backlog_items": [],
            },
        ),
    )
    profile = HumanProfile(
        display_name="Kai",
        profession="Trader",
        current_stage="restart",
        interests=["stocks"],
        strengths=["review"],
        constraints=["capital"],
        goal_intention="Build a real stock trading path.",
    )

    result = reasoner.plan_turn(
        profile=profile,
        transcript=["Build a real stock trading path."],
        question_count=2,
        tightened=False,
    )

    assert result.recommended_direction == "建立稳定的股票交易路径"
    assert result.candidate_directions == ["建立稳定的股票交易路径"]
