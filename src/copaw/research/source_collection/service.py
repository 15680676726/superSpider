# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Callable, Mapping

from pydantic import BaseModel, Field

from .contracts import ResearchAdapterResult, ResearchBrief
from .routing import CollectionRouteDecision, route_collection_mode
from .synthesis import synthesize_collection_results

SourceCollectionAdapter = Callable[[ResearchBrief], ResearchAdapterResult]


class SourceCollectionRunResult(BaseModel):
    brief: ResearchBrief
    route: CollectionRouteDecision
    adapter_results: list[ResearchAdapterResult] = Field(default_factory=list)
    collected_sources: list = Field(default_factory=list)
    findings: list = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class SourceCollectionService:
    def __init__(
        self,
        *,
        adapters: Mapping[str, SourceCollectionAdapter] | None = None,
        preferred_researcher_agent_id: str | None = None,
    ) -> None:
        self._adapters = dict(adapters or {})
        self._preferred_researcher_agent_id = preferred_researcher_agent_id

    def collect(
        self,
        *,
        brief: ResearchBrief,
        owner_agent_id: str,
        requested_sources: list[str] | None = None,
    ) -> SourceCollectionRunResult:
        normalized_brief = self._normalize_brief(
            brief=brief,
            owner_agent_id=owner_agent_id,
        )
        normalized_sources = self._normalize_requested_sources(requested_sources)
        route = route_collection_mode(
            normalized_brief,
            requested_sources=normalized_sources,
            preferred_researcher_agent_id=self._preferred_researcher_agent_id,
        )

        adapter_results = [
            self._invoke_adapter(source_kind, normalized_brief)
            for source_kind in route.requested_sources
        ]
        synthesized = synthesize_collection_results(adapter_results)
        return SourceCollectionRunResult(
            brief=normalized_brief,
            route=route,
            adapter_results=synthesized.adapter_results,
            collected_sources=synthesized.collected_sources,
            findings=synthesized.findings,
            conflicts=synthesized.conflicts,
            gaps=synthesized.gaps,
        )

    def _normalize_brief(
        self,
        *,
        brief: ResearchBrief,
        owner_agent_id: str,
    ) -> ResearchBrief:
        normalized_question = " ".join(brief.question.split())
        normalized_goal = " ".join(brief.goal.split())
        normalized_why_needed = " ".join(brief.why_needed.split())
        normalized_done_when = " ".join(brief.done_when.split())
        return brief.model_copy(
            update={
                "owner_agent_id": owner_agent_id.strip() or brief.owner_agent_id,
                "goal": normalized_goal,
                "question": normalized_question,
                "why_needed": normalized_why_needed,
                "done_when": normalized_done_when,
            },
        )

    def _normalize_requested_sources(
        self,
        requested_sources: list[str] | None,
    ) -> list[str]:
        if not requested_sources:
            return []
        return [str(source or "").strip() for source in requested_sources]

    def _invoke_adapter(
        self,
        source_kind: str,
        brief: ResearchBrief,
    ) -> ResearchAdapterResult:
        adapter = self._adapters.get(source_kind)
        if adapter is None:
            raise KeyError(f"missing source collection adapter: {source_kind}")
        return adapter(brief)


__all__ = [
    "SourceCollectionAdapter",
    "SourceCollectionRunResult",
    "SourceCollectionService",
]
