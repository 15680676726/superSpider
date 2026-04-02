# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


MainBrainIntentShellMode = Literal["none", "plan", "review", "resume", "verify"]

_VALID_MODE_HINTS = {"plan", "review", "resume", "verify"}
_WORD_CHAR_PATTERN = re.compile(r"[\w]", re.UNICODE)
_ASCII_PREFIX_PATTERN = re.compile(
    r"^\s*(?:please[, ]*|can you\s+|could you\s+|help me\s+|need you to\s+)?$",
    re.IGNORECASE,
)
_NON_ASCII_LITERAL_SUFFIXES = (
    "这句话",
    "这几个字",
    "这个词",
    "这个短语",
    "这句文案",
    "这个标题",
)
_OPEN_TO_CLOSE = {
    "`": "`",
    '"': '"',
    "'": "'",
    "“": "”",
    "‘": "’",
    "(": ")",
    "[": "]",
    "{": "}",
    "<": ">",
}
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


def _is_word_char(value: str | None) -> bool:
    if not value:
        return False
    return bool(_WORD_CHAR_PATTERN.search(value))


def _build_excluded_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    open_quote: str | None = None
    open_at = 0

    for index, ch in enumerate(text):
        if open_quote is not None:
            close_ch = _OPEN_TO_CLOSE[open_quote]
            if ch != close_ch:
                continue
            if open_quote == "'" and _is_word_char(text[index + 1 : index + 2]):
                continue
            ranges.append((open_at, index + 1))
            open_quote = None
            continue

        if ch == "'" and _is_word_char(text[index - 1 : index]):
            continue
        if ch == "<" and not re.match(r"[a-zA-Z/]", text[index + 1 : index + 2] or ""):
            continue
        if ch in _OPEN_TO_CLOSE:
            open_quote = ch
            open_at = index
    return ranges


def _is_in_excluded_range(index: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in ranges)


def _iter_matches(text: str, term: str) -> list[tuple[int, int]]:
    lowered_text = text.lower()
    lowered_term = term.lower()
    matches: list[tuple[int, int]] = []
    start = 0
    while True:
        found = lowered_text.find(lowered_term, start)
        if found < 0:
            return matches
        matches.append((found, found + len(term)))
        start = found + len(term)


def _ascii_prefix_allows_trigger(text: str, start: int) -> bool:
    return bool(_ASCII_PREFIX_PATTERN.match(text[:start]))


def _is_triggerable_match(
    text: str,
    term: str,
    *,
    start: int,
    end: int,
    excluded_ranges: list[tuple[int, int]],
) -> bool:
    if _is_in_excluded_range(start, excluded_ranges):
        return False

    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    after_next = text[end + 1] if end + 1 < len(text) else ""
    is_ascii_term = term.isascii()
    has_trailing_space = term.endswith(" ")

    if term.startswith("/"):
        if before and (_is_word_char(before) or before in "/\\-"):
            return False
        if after and after in "/\\-?":
            return False
        if after == "." and _is_word_char(after_next):
            return False
        return True

    if is_ascii_term:
        if before and _is_word_char(before):
            return False
        if not has_trailing_space and after and _is_word_char(after):
            return False
        if (before and before in "/\\-") or (after and after in "/\\-?"):
            return False
        if after == "." and _is_word_char(after_next):
            return False
        if not _ascii_prefix_allows_trigger(text, start):
            return False
    else:
        suffix = text[end:].lstrip()
        if any(suffix.startswith(marker) for marker in _NON_ASCII_LITERAL_SUFFIXES):
            return False

    return True


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
    excluded_ranges = _build_excluded_ranges(normalized)
    for mode_hint, terms in _SHELL_RULES:
        for term in terms:
            for start, end in _iter_matches(normalized, term):
                if not _is_triggerable_match(
                    normalized,
                    term,
                    start=start,
                    end=end,
                    excluded_ranges=excluded_ranges,
                ):
                    continue
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
