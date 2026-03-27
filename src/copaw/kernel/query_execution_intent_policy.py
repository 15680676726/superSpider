# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Any

_GOAL_METRIC_HINT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:万|亿|%|w|k|m|元|单|个|家|位|人|粉|用户|订单|营收|收入|利润|gmv|roi|mrr|arr)",
    re.IGNORECASE,
)
_GOAL_SETTING_HINTS = (
    "目标",
    "做到",
    "达到",
    "实现",
    "做成",
    "月入",
    "年入",
    "营收",
    "收入",
    "利润",
    "增长",
    "转化",
    "获客",
    "留存",
    "roi",
    "gmv",
    "mrr",
    "arr",
    "零亏损",
    "零回撤",
)
_GOAL_ENTRUSTMENT_HINTS = (
    "帮我把",
    "帮我做成",
    "帮我达成",
    "我要把",
    "我想把",
    "我需要把",
    "希望把",
    "目标是",
    "要做到",
    "想做到",
    "要实现",
    "想实现",
    "交给你推进",
)
_GOAL_METRIC_CONTEXT_HINTS = (
    "目标",
    "做到",
    "达到",
    "实现",
    "增长",
    "营收",
    "收入",
    "利润",
    "转化",
    "月",
    "年",
)
_HYPOTHETICAL_CONTROL_HINTS = (
    "what if",
    "if i say",
    "if we say",
    "would you",
    "如果",
    "假如",
    "假设",
    "要是",
    "可行吗",
    "能不能",
    "可以不可以",
)
_DISCUSSION_HINTS = (
    "怎么",
    "如何",
    "why",
    "what",
    "could we",
    "should we",
    "would it",
)


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
            continue
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return None


def is_hypothetical_control_text(text: str | None) -> bool:
    normalized = _first_non_empty(text)
    if normalized is None:
        return False
    lowered = normalized.casefold()
    if "?" in normalized or "？" in normalized:
        return True
    return any(marker in lowered for marker in _HYPOTHETICAL_CONTROL_HINTS)


def looks_like_goal_setting_text(text: str | None) -> bool:
    normalized = _first_non_empty(text)
    if normalized is None or is_hypothetical_control_text(normalized):
        return False
    lowered = normalized.casefold()
    if any(token in lowered for token in ("?", "？")):
        return False
    if any(token in lowered for token in _DISCUSSION_HINTS):
        return False
    if any(phrase in lowered for phrase in _GOAL_ENTRUSTMENT_HINTS):
        return True
    if any(phrase in lowered for phrase in _GOAL_SETTING_HINTS):
        return True
    return bool(_GOAL_METRIC_HINT_RE.search(lowered)) and any(
        phrase in lowered for phrase in _GOAL_METRIC_CONTEXT_HINTS
    )


__all__ = [
    "is_hypothetical_control_text",
    "looks_like_goal_setting_text",
]
