# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .contracts import CollectionModeHint, ResearchBrief

RouteMode = Literal["light", "heavy"]


class CollectionRouteDecision(BaseModel):
    mode: RouteMode
    requested_sources: list[str] = Field(default_factory=list)
    execution_agent_id: str
    reason: str = ""


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
