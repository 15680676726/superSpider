# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


MainBrainIntentShellMode = Literal["none", "plan", "review", "resume", "verify"]

_VALID_MODE_HINTS = {"plan", "review", "resume", "verify"}
_CODEISH_PATTERN = re.compile(
    r"([\\/].+\.(?:ts|tsx|js|jsx|py|md|json|ya?ml)\b)"
    r"|(\b[\w.-]+\.(?:ts|tsx|js|jsx|py|md|json|ya?ml)\b)"
    r"|(\b[a-zA-Z_][\w]*\s*=)",
    re.IGNORECASE,
)
_SHELL_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "plan",
        (
            "先做个计划",
            "先做个规划",
            "先规划一下",
            "做个计划",
            "计划一下",
            "给我一个计划",
            "plan ",
            "/plan",
            "ultraplan",
        ),
    ),
    (
        "review",
        (
            "review ",
            "/review",
            "评审一下",
            "审查一下",
            "复盘一下",
            "检查这次改动",
        ),
    ),
    (
        "resume",
        (
            "resume ",
            "/resume",
            "恢复上一个线程",
            "继续上一个线程",
            "继续上个线程",
            "接着上一个线程",
        ),
    ),
    (
        "verify",
        (
            "verify ",
            "/verify",
            "验证一下",
            "核验一下",
            "确认这个结果",
            "检查这个结果",
        ),
    ),
)


@dataclass(slots=True)
class MainBrainIntentShell:
    mode_hint: MainBrainIntentShellMode = "none"
    trigger_source: str = "none"
    matched_text: str = ""
    confidence: float = 0.0

    @property
    def active(self) -> bool:
        return self.mode_hint != "none"

    def to_payload(self) -> dict[str, object] | None:
        if not self.active:
            return None
        label = str(self.mode_hint).upper()
        summary_map = {
            "plan": "Use a compact planning shell for this reply.",
            "review": "Use a compact review shell for this reply.",
            "resume": "Use a compact continuity shell for this reply.",
            "verify": "Use a compact verification shell for this reply.",
        }
        hint_map = {
            "plan": "Goal, constraints, affected scope/files, checklist, acceptance criteria, verification steps.",
            "review": "Conclusion, findings, severity, risk, evidence gaps, next step.",
            "resume": "Current state, continuity anchors, blockers, next action.",
            "verify": "Check target, evidence, pass/fail, unresolved risk, next step.",
        }
        return {
            "mode_hint": self.mode_hint,
            "label": label,
            "summary": summary_map.get(self.mode_hint),
            "hint": hint_map.get(self.mode_hint),
            "trigger_source": self.trigger_source,
            "matched_text": self.matched_text,
            "confidence": self.confidence,
        }


def normalize_main_brain_mode_hint(value: object | None) -> MainBrainIntentShellMode:
    text = str(value or "").strip().lower()
    if text in _VALID_MODE_HINTS:
        return text  # type: ignore[return-value]
    return "none"


def read_attached_main_brain_intent_shell(*, request: object) -> MainBrainIntentShell | None:
    attached = getattr(request, "_copaw_main_brain_intent_shell", None)
    if isinstance(attached, MainBrainIntentShell):
        return attached
    if isinstance(attached, dict):
        return MainBrainIntentShell(
            mode_hint=normalize_main_brain_mode_hint(attached.get("mode_hint")),
            trigger_source=str(attached.get("trigger_source") or "none"),
            matched_text=str(attached.get("matched_text") or ""),
            confidence=float(attached.get("confidence") or 0.0),
        )
    mode_hint = normalize_main_brain_mode_hint(getattr(attached, "mode_hint", None))
    if mode_hint == "none":
        return None
    return MainBrainIntentShell(
        mode_hint=mode_hint,
        trigger_source=str(getattr(attached, "trigger_source", None) or "attached"),
        matched_text=str(getattr(attached, "matched_text", None) or ""),
        confidence=float(getattr(attached, "confidence", None) or 1.0),
    )


def build_requested_main_brain_intent_shell(mode_hint: object | None) -> MainBrainIntentShell | None:
    normalized = normalize_main_brain_mode_hint(mode_hint)
    if normalized == "none":
        return None
    return MainBrainIntentShell(
        mode_hint=normalized,
        trigger_source="request",
        matched_text=str(mode_hint or normalized),
        confidence=1.0,
    )


def detect_main_brain_intent_shell(text: str | None) -> MainBrainIntentShell:
    normalized = str(text or "").strip()
    if not normalized:
        return MainBrainIntentShell()
    lowered = normalized.lower()
    if _CODEISH_PATTERN.search(normalized):
        return MainBrainIntentShell()
    for mode_hint, terms in _SHELL_RULES:
        for term in terms:
            if term.lower() in lowered:
                confidence = 0.98 if term.startswith("/") or term.isascii() else 0.88
                return MainBrainIntentShell(
                    mode_hint=mode_hint,  # type: ignore[arg-type]
                    trigger_source="keyword",
                    matched_text=term,
                    confidence=confidence,
                )
    return MainBrainIntentShell()


__all__ = [
    "MainBrainIntentShell",
    "MainBrainIntentShellMode",
    "build_requested_main_brain_intent_shell",
    "detect_main_brain_intent_shell",
    "normalize_main_brain_mode_hint",
    "read_attached_main_brain_intent_shell",
]
