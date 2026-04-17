# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, Field

from .contracts import CollectionModeHint, ResearchBrief

RouteMode = Literal["light", "heavy"]


class CollectionRouteDecision(BaseModel):
    mode: RouteMode
    requested_sources: list[str] = Field(default_factory=list)
    execution_agent_id: str
    reason: str = ""


_DIRECT_URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
_WINDOWS_PATH_PATTERN = re.compile(
    r"[A-Za-z]:[\\/][^\\/:*?\"<>|\r\n]+(?:[\\/][^\\/:*?\"<>|\r\n]+)+"
)
_GITHUB_REPO_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.-])([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?![A-Za-z0-9_.-])"
)


def _text(value: object | None) -> str:
    return str(value or "").strip()


def _infer_default_sources(brief: ResearchBrief) -> list[str]:
    metadata = brief.metadata if isinstance(brief.metadata, dict) else {}
    inferred: list[str] = []
    if metadata.get("artifact"):
        inferred.append("artifact")
    if metadata.get("github"):
        inferred.append("github")
    if metadata.get("web_page"):
        inferred.append("web_page")
    if metadata.get("search_hits"):
        inferred.append("search")
    if inferred:
        return list(dict.fromkeys(inferred))
    combined = " ".join(
        value
        for value in (
            _text(brief.question),
            _text(brief.goal),
            _text(brief.why_needed),
        )
        if value
    )
    if _WINDOWS_PATH_PATTERN.search(combined):
        return ["artifact"]
    for candidate in combined.split():
        if Path(candidate).exists():
            return ["artifact"]
    direct_url = _DIRECT_URL_PATTERN.search(combined)
    if direct_url is not None:
        lowered = direct_url.group(0).casefold()
        if "github.com/" in lowered:
            return ["github"]
        return ["web_page"]
    if _GITHUB_REPO_PATTERN.search(combined):
        return ["github"]
    return ["search"]


def route_collection_mode(
    brief: ResearchBrief,
    *,
    requested_sources: list[str],
    preferred_researcher_agent_id: str | None = None,
) -> CollectionRouteDecision:
    normalized_sources = [
        str(source or "").strip()
        for source in requested_sources
        if str(source or "").strip()
    ]
    unique_sources = list(dict.fromkeys(normalized_sources))
    if not unique_sources:
        unique_sources = _infer_default_sources(brief)
    hint: CollectionModeHint = brief.collection_mode_hint

    if hint == "heavy":
        mode: RouteMode = "heavy"
        reason = "brief-requested-heavy"
    elif hint == "light":
        mode = "light"
        reason = "brief-requested-light"
    elif len(unique_sources) > 1:
        mode = "heavy"
        reason = "multi-source-collection"
    else:
        mode = "light"
        reason = "single-source-collection"

    execution_agent_id = brief.owner_agent_id
    if mode == "heavy" and preferred_researcher_agent_id:
        execution_agent_id = preferred_researcher_agent_id

    return CollectionRouteDecision(
        mode=mode,
        requested_sources=unique_sources,
        execution_agent_id=execution_agent_id,
        reason=reason,
    )


__all__ = ["CollectionRouteDecision", "RouteMode", "route_collection_mode"]
