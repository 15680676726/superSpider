# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ..state import ResearchSessionRecord, ResearchSessionRoundRecord


@dataclass(slots=True)
class ResearchLink:
    url: str
    label: str = ""
    kind: str = "link"


@dataclass(slots=True)
class LoginStateResult:
    state: Literal["ready", "login-required", "unknown"]
    reason: str = ""


@dataclass(slots=True)
class BaiduPageContractResult:
    login_state: Literal["ready", "login-required", "unknown"] = "unknown"
    answer_text: str = ""
    links: list[ResearchLink] = field(default_factory=list)


@dataclass(slots=True)
class ResearchSessionRunResult:
    session: ResearchSessionRecord
    rounds: list[ResearchSessionRoundRecord] = field(default_factory=list)
    stop_reason: str | None = None
    deepened_links: list[dict[str, Any]] = field(default_factory=list)
    downloaded_artifacts: list[dict[str, Any]] = field(default_factory=list)
    final_report_id: str | None = None
    work_context_chunk_ids: list[str] = field(default_factory=list)
    industry_document_id: str | None = None


__all__ = [
    "BaiduPageContractResult",
    "LoginStateResult",
    "ResearchLink",
    "ResearchSessionRunResult",
]
