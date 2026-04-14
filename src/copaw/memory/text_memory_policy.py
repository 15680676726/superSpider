# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
import re

_LOW_VALUE_TAGS = frozenset(
    {
        "ack",
        "chat-noise",
        "chitchat",
        "filler",
        "small-talk",
        "typing",
    }
)
_HIGH_VALUE_TAGS = frozenset(
    {
        "constraint",
        "decision",
        "evidence",
        "follow-up",
        "media-analysis",
        "policy",
        "preference",
        "report",
        "report-outcome",
        "routine-run",
        "shared-memory",
    }
)
_LOW_VALUE_TEXTS = frozenset(
    {
        "ok",
        "ok thanks",
        "okay",
        "okay thanks",
        "thanks",
        "thank you",
        "收到",
        "好的",
    }
)
_TOKEN_RE = re.compile(r"[a-zA-Z0-9\u4e00-\u9fff]+")


@dataclass(frozen=True)
class TextMemoryWriteDecision:
    allow_formal_memory: bool
    scope_type: str
    scope_id: str
    reason: str


def resolve_formal_text_scope(
    *,
    industry_instance_id: str | None = None,
    work_context_id: str | None = None,
    scope_type: str | None = None,
    scope_id: str | None = None,
) -> tuple[str, str]:
    normalized_scope_type = str(scope_type or "").strip().lower()
    normalized_scope_id = str(scope_id or "").strip()
    if normalized_scope_type and normalized_scope_id:
        return normalized_scope_type, normalized_scope_id

    normalized_work_context_id = str(work_context_id or "").strip()
    if normalized_work_context_id:
        return "work_context", normalized_work_context_id

    normalized_industry_instance_id = str(industry_instance_id or "").strip()
    if normalized_industry_instance_id:
        return "industry", normalized_industry_instance_id

    return "global", "runtime"


def decide_formal_text_write(
    *,
    event_kind: str,
    title: str,
    content: str,
    tags: list[str] | None = None,
    industry_instance_id: str | None = None,
    work_context_id: str | None = None,
    scope_type: str | None = None,
    scope_id: str | None = None,
) -> TextMemoryWriteDecision:
    resolved_scope_type, resolved_scope_id = resolve_formal_text_scope(
        industry_instance_id=industry_instance_id,
        work_context_id=work_context_id,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    normalized_tags = {
        str(item or "").strip().lower()
        for item in (tags or [])
        if str(item or "").strip()
    }
    if event_kind == "chat_writeback" and _looks_like_low_value_chat(
        title=title,
        content=content,
        tags=normalized_tags,
    ):
        return TextMemoryWriteDecision(
            allow_formal_memory=False,
            scope_type=resolved_scope_type,
            scope_id=resolved_scope_id,
            reason="low-value-chat-noise",
        )
    return TextMemoryWriteDecision(
        allow_formal_memory=True,
        scope_type=resolved_scope_type,
        scope_id=resolved_scope_id,
        reason="formal-memory-allowed",
    )


def _looks_like_low_value_chat(
    *,
    title: str,
    content: str,
    tags: set[str],
) -> bool:
    if tags & _HIGH_VALUE_TAGS:
        return False
    if tags & _LOW_VALUE_TAGS:
        return True
    collapsed = " ".join(f"{title} {content}".split()).strip().lower()
    if collapsed in _LOW_VALUE_TEXTS:
        return True
    token_count = len(_TOKEN_RE.findall(collapsed))
    return token_count <= 4
