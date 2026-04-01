# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


MainBrainActionKind = Literal["reply_only", "suggest_action", "commit_action"]
MainBrainActionType = Literal[
    "none",
    "orchestrate_execution",
    "writeback_operating_truth",
    "create_backlog_item",
    "resume_execution",
    "submit_human_assist",
]
MainBrainRiskHint = Literal["auto", "guarded", "confirm"]
MainBrainCommitStatus = Literal[
    "confirm_required",
    "committed",
    "commit_failed",
    "governance_denied",
    "commit_deferred",
]


class MainBrainActionEnvelope(BaseModel):
    version: str = "v1"
    kind: MainBrainActionKind = "reply_only"
    summary: str | None = None
    action_type: MainBrainActionType = "none"
    risk_hint: MainBrainRiskHint | None = None
    payload: dict[str, Any] | None = None


class MainBrainTurnResult(BaseModel):
    reply_text: str = ""
    action_envelope: MainBrainActionEnvelope = Field(
        default_factory=MainBrainActionEnvelope,
    )

    @classmethod
    def from_reply_text(cls, reply_text: str) -> "MainBrainTurnResult":
        return cls(reply_text=str(reply_text or "").strip())

    @classmethod
    def normalize(
        cls,
        value: object | None,
        *,
        fallback_reply_text: str = "",
    ) -> "MainBrainTurnResult":
        if isinstance(value, cls):
            if value.reply_text.strip():
                return value
            return value.model_copy(update={"reply_text": fallback_reply_text})
        if isinstance(value, dict):
            payload = dict(value)
            payload.setdefault("reply_text", fallback_reply_text)
            return cls.model_validate(payload)
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            payload = model_dump(mode="json")
            if isinstance(payload, dict):
                payload.setdefault("reply_text", fallback_reply_text)
                return cls.model_validate(payload)
        reply_text = getattr(value, "reply_text", None)
        action_envelope = getattr(value, "action_envelope", None)
        if reply_text is not None or action_envelope is not None:
            payload = {
                "reply_text": reply_text if reply_text is not None else fallback_reply_text,
                "action_envelope": action_envelope,
            }
            return cls.model_validate(payload)
        return cls.from_reply_text(fallback_reply_text)


class MainBrainCommitState(BaseModel):
    status: MainBrainCommitStatus
    action_type: MainBrainActionType = "none"
    risk_level: MainBrainRiskHint | None = None
    reason: str | None = None
    message: str | None = None
    summary: str | None = None
    commit_key: str | None = None
    control_thread_id: str | None = None
    session_id: str | None = None
    work_context_id: str | None = None
    record_id: str | None = None
    payload: dict[str, Any] | None = None
    recovery_options: list[str] = Field(default_factory=list)
    idempotent_replay: bool = False


__all__ = [
    "MainBrainActionEnvelope",
    "MainBrainCommitState",
    "MainBrainTurnResult",
]
