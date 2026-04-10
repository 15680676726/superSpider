# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from copaw.kernel.buddy_onboarding_reasoner import (
    _BUDDY_ONBOARDING_REASONER_PROMPT,
    BuddyCollaborationContract,
    BuddyOnboardingReasonerUnavailableError,
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
        self.calls: list[dict[str, object]] = []

    async def __call__(self, *, messages, structured_model=None):  # pragma: no cover - async adapter
        self.calls.append(
            {
                "messages": messages,
                "structured_model": structured_model,
            }
        )
        return _FakeChatResponse(metadata=self._metadata)


def _profile() -> HumanProfile:
    return HumanProfile(
        display_name="Kai",
        profession="Trader",
        current_stage="restart",
        interests=["stocks"],
        strengths=["review"],
        constraints=["capital"],
        goal_intention="Build a real stock trading path.",
    )


def _contract() -> BuddyCollaborationContract:
    return BuddyCollaborationContract(
        service_intent="Turn trading ambition into a disciplined weekly execution path.",
        collaboration_role="orchestrator",
        autonomy_level="guarded-proactive",
        confirm_boundaries=["external spend", "irreversible actions"],
        report_style="decision-first",
        collaboration_notes="Escalate when an action exceeds the agreed risk boundary.",
    )


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


def test_reasoner_prompt_declares_contract_compile_fields() -> None:
    assert '"recommended_direction"' in _BUDDY_ONBOARDING_REASONER_PROMPT
    assert '"candidate_directions"' in _BUDDY_ONBOARDING_REASONER_PROMPT
    assert '"final_goal"' in _BUDDY_ONBOARDING_REASONER_PROMPT
    assert '"why_it_matters"' in _BUDDY_ONBOARDING_REASONER_PROMPT
    assert '"backlog_items"' in _BUDDY_ONBOARDING_REASONER_PROMPT


def test_model_driven_reasoner_compiles_contract_and_normalizes_aliases() -> None:
    model = _FakeChatModel(
        metadata={
            "real_main_direction": "Build a disciplined stock trading path.",
            "final_goal": "Build a disciplined stock trading system with visible review evidence.",
            "reason": "Turn trading into a durable operating path instead of emotional reactions.",
            "backlog": [
                {
                    "lane_hint": "growth-focus",
                    "title": "Define the first-cycle risk boundary",
                    "summary": "Lock the market scope, risk cap, and stop-loss rule for the first cycle.",
                    "priority": 3,
                    "source_key": "trading-boundary",
                }
            ],
        }
    )
    reasoner = ModelDrivenBuddyOnboardingReasoner(
        provider_runtime=_StubProviderRuntime(),
        model_factory=lambda: model,
    )

    result = reasoner.compile_contract(
        profile=_profile(),
        collaboration_contract=_contract(),
    )

    assert result is not None
    assert result.recommended_direction == "Build a disciplined stock trading path."
    assert result.candidate_directions == ["Build a disciplined stock trading path."]
    assert result.final_goal
    assert result.why_it_matters
    assert result.backlog_items[0].lane_hint == "growth-focus"
    assert "collaboration_contract" in model.calls[0]["messages"][1]["content"]


def test_model_driven_reasoner_rejects_incomplete_contract_compile_payload() -> None:
    reasoner = ModelDrivenBuddyOnboardingReasoner(
        provider_runtime=_StubProviderRuntime(),
        model_factory=lambda: _FakeChatModel(
            metadata={
                "recommended_direction": "Build a disciplined stock trading path.",
                "final_goal": "",
                "why_it_matters": "",
                "backlog_items": [],
            }
        ),
    )

    with pytest.raises(BuddyOnboardingReasonerUnavailableError, match="有效结果"):
        reasoner.compile_contract(
            profile=_profile(),
            collaboration_contract=_contract(),
        )
