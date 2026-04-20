# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import uuid4

from pydantic import BaseModel, Field

from ...retrieval import RetrievalFacade, RetrievalRun
from .contracts import CollectedSource, ResearchAdapterResult, ResearchBrief, ResearchFinding
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
    retrieval_runs: list[RetrievalRun] = Field(default_factory=list)


class SourceCollectionService:
    def __init__(
        self,
        *,
        adapters: Mapping[str, SourceCollectionAdapter] | None = None,
        preferred_researcher_agent_id: str | None = None,
        retrieval_facade: RetrievalFacade | None = None,
    ) -> None:
        self._adapters = dict(adapters or {})
        self._preferred_researcher_agent_id = preferred_researcher_agent_id
        self._retrieval_facade = retrieval_facade

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

        retrieval_runs: list[RetrievalRun] = []
        adapter_results: list[ResearchAdapterResult] = []
        for source_kind in route.requested_sources:
            if self._retrieval_facade is not None and self._retrieval_facade.can_handle(source_kind):
                retrieval_run = self._retrieval_facade.retrieve(
                    question=normalized_brief.question,
                    goal=normalized_brief.goal,
                    requested_sources=[source_kind],
                    latest_required=False,
                    metadata=normalized_brief.metadata,
                )
                if retrieval_run.selected_hits:
                    retrieval_runs.append(retrieval_run)
                    adapter_results.append(
                        self._map_retrieval_run_to_adapter_result(
                            source_kind=source_kind,
                            retrieval_run=retrieval_run,
                        )
                    )
                    continue
            adapter_results.append(self._invoke_adapter(source_kind, normalized_brief))
        synthesized = synthesize_collection_results(adapter_results)
        return SourceCollectionRunResult(
            brief=normalized_brief,
            route=route,
            adapter_results=synthesized.adapter_results,
            collected_sources=synthesized.collected_sources,
            findings=synthesized.findings,
            conflicts=synthesized.conflicts,
            gaps=synthesized.gaps,
            retrieval_runs=retrieval_runs,
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

    def _map_retrieval_run_to_adapter_result(
        self,
        *,
        source_kind: str,
        retrieval_run: RetrievalRun,
    ) -> ResearchAdapterResult:
        collected_sources: list[CollectedSource] = []
        findings: list[ResearchFinding] = []
        for index, hit in enumerate(retrieval_run.selected_hits, start=1):
            source_id = f"{source_kind}:{uuid4().hex}:{index}"
            collected_sources.append(
                CollectedSource(
                    source_id=source_id,
                    source_kind=hit.source_kind,
                    collection_action="read",
                    source_ref=hit.ref,
                    normalized_ref=hit.normalized_ref,
                    title=hit.title,
                    snippet=hit.snippet,
                    metadata={
                        "provider_kind": hit.provider_kind,
                        "hit_kind": hit.hit_kind,
                        "why_matched": hit.why_matched,
                        "score": hit.score,
                        "relevance_score": hit.relevance_score,
                        "answerability_score": hit.answerability_score,
                        "credibility_score": hit.credibility_score,
                        "freshness_score": hit.freshness_score,
                        "structural_score": hit.structural_score,
                    },
                )
            )
            findings.append(
                ResearchFinding(
                    finding_id=f"{source_kind}:finding:{index}",
                    finding_type="retrieval-hit",
                    summary=hit.snippet or hit.title or hit.why_matched,
                    supporting_source_ids=[source_id],
                )
            )
        return ResearchAdapterResult(
            adapter_kind=source_kind,
            collection_action="read",
            status="succeeded" if collected_sources else "partial",
            collected_sources=collected_sources,
            findings=findings,
            metadata={
                "retrieval_plan": retrieval_run.plan.model_dump(mode="json"),
                "coverage_summary": dict(retrieval_run.coverage_summary),
                "trace": list(retrieval_run.trace),
            },
        )


__all__ = [
    "SourceCollectionAdapter",
    "SourceCollectionRunResult",
    "SourceCollectionService",
]
