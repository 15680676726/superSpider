# -*- coding: utf-8 -*-
from __future__ import annotations

from ..environments.surface_execution.browser import (
    BrowserExecutionResult,
    BrowserExecutionStep,
    BrowserObservation,
)
from ..environments.surface_execution.browser.resolver import resolve_browser_target


class ResearchChatSurfaceLoopOwner:
    """Profession-layer owner for chat-page step planning."""

    def __init__(
        self,
        *,
        question: str,
        request_reasoning_toggle: bool = True,
    ) -> None:
        self._question = str(question or "").strip()
        self._request_reasoning_toggle = bool(request_reasoning_toggle)

    def plan_step(
        self,
        observation: BrowserObservation,
        history: list[BrowserExecutionResult],
    ) -> BrowserExecutionStep | None:
        if (
            str(observation.login_state or "").strip() == "login-required"
            or "login-required" in [str(item or "").strip() for item in observation.blockers]
        ):
            return None
        if self._request_reasoning_toggle:
            toggle_candidate = resolve_browser_target(
                observation,
                target_slot="reasoning_toggle",
            )
            toggle_completed = any(
                step.intent_kind == "click"
                and step.target_slot == "reasoning_toggle"
                and step.verification_passed
                for step in history
            )
            toggle_enabled = bool(toggle_candidate.metadata.get("enabled")) if toggle_candidate is not None else False
            if toggle_candidate is not None and not toggle_enabled and not toggle_completed:
                return BrowserExecutionStep(
                    intent_kind="click",
                    target_slot="reasoning_toggle",
                    payload={},
                    success_assertion={"toggle_enabled": "true"},
                )

        typed = any(
            step.intent_kind == "type"
            and step.target_slot == "primary_input"
            and step.verification_passed
            for step in history
        )
        if not typed:
            return BrowserExecutionStep(
                intent_kind="type",
                target_slot="primary_input",
                payload={"text": self._question},
                success_assertion={"normalized_text": self._question},
            )

        pressed = any(
            step.intent_kind == "press"
            and step.target_slot == "page"
            and step.status == "succeeded"
            for step in history
        )
        if not pressed:
            return BrowserExecutionStep(
                intent_kind="press",
                target_slot="page",
                payload={"key": "Enter"},
            )
        return None


__all__ = ["ResearchChatSurfaceLoopOwner"]
