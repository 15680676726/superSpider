# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .contracts import RetrievalHit, RetrievalQuery, RetrievalRun
from .github.code_search import search_github_code
from .github.object_search import search_github_objects
from .local_repo.exact_search import search_local_repo_exact
from .local_repo.semantic_search import search_local_repo_semantic
from .local_repo.symbol_search import search_local_repo_symbols
from .planner import build_retrieval_plan
from .ranking import rank_retrieval_hits
from .run import select_retrieval_hits
from .utils import extract_first_url, normalize_ref, text
from .web.discover import discover_web_hits
from .web.read import read_web_page_hit


class RetrievalFacade:
    def __init__(self, *, workspace_root: Path) -> None:
        self._workspace_root = Path(workspace_root)

    def can_handle(self, source_kind: str) -> bool:
        return source_kind in {"local_repo", "github", "search", "web_page"}

    def retrieve(
        self,
        *,
        question: str,
        goal: str,
        requested_sources: list[str],
        latest_required: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> RetrievalRun:
        metadata_payload = dict(metadata or {})
        intent = self._classify_intent(
            requested_sources=requested_sources,
            latest_required=latest_required,
        )
        query = RetrievalQuery(
            question=question,
            goal=goal,
            intent=intent,
            requested_sources=list(requested_sources),
            workspace_root=str(self._workspace_root),
            constraints=metadata_payload,
            latest_required=latest_required,
        )
        plan = build_retrieval_plan(
            intent=intent,
            requested_sources=list(requested_sources),
            latest_required=latest_required,
        )
        hits = []
        for source_kind in plan.source_sequence:
            for mode in plan.mode_sequence:
                hits.extend(
                    self._run_stage(
                        source_kind=source_kind,
                        mode=mode,
                        question=question,
                        goal=goal,
                        metadata=metadata_payload,
                    )
                )
        ranked_hits = rank_retrieval_hits(hits)
        run = RetrievalRun(
            query=query,
            plan=plan,
            stages=[
                {
                    "source_sequence": list(plan.source_sequence),
                    "mode_sequence": list(plan.mode_sequence),
                }
            ],
            coverage_summary={
                source_kind: sum(1 for hit in ranked_hits if hit.source_kind == source_kind)
                for source_kind in plan.source_sequence
            },
            trace=[{"intent": intent}],
        )
        return select_retrieval_hits(
            run=run,
            ranked_hits=ranked_hits,
            top_k=plan.max_hits_per_stage,
        )

    def _classify_intent(
        self,
        *,
        requested_sources: list[str],
        latest_required: bool,
    ) -> str:
        if "local_repo" in requested_sources:
            return "repo-trace"
        if latest_required:
            return "external-latest"
        return "lookup"

    def _run_stage(
        self,
        *,
        source_kind: str,
        mode: str,
        question: str,
        goal: str,
        metadata: Mapping[str, Any],
    ):
        target = self._resolve_source_target(
            source_kind=source_kind,
            question=question,
            goal=goal,
            metadata=metadata,
        )
        if source_kind != "local_repo":
            if source_kind == "github":
                if mode == "exact":
                    return search_github_objects(query=target or question)
                if mode == "semantic":
                    return search_github_code(query=target or question)
                return []
            if source_kind == "search":
                if mode in {"exact", "semantic"}:
                    return discover_web_hits(query=target or question, source_kind="search")
                return []
            if source_kind == "web_page":
                metadata_hit = self._build_web_page_metadata_hit(metadata=metadata)
                if metadata_hit:
                    return metadata_hit
                if mode == "exact" and target:
                    return read_web_page_hit(source_ref=target, source_kind="web_page")
                return []
            return []
        if mode == "symbol":
            return search_local_repo_symbols(
                workspace_root=self._workspace_root,
                query=question,
            )
        if mode == "exact":
            return search_local_repo_exact(
                workspace_root=self._workspace_root,
                query=question,
            )
        if mode == "semantic":
            return search_local_repo_semantic(
                workspace_root=self._workspace_root,
                query=question,
            )
        return []

    def _resolve_source_target(
        self,
        *,
        source_kind: str,
        question: str,
        goal: str,
        metadata: Mapping[str, Any],
    ) -> str:
        if source_kind == "web_page":
            return self._resolve_web_page_target(question=question, goal=goal, metadata=metadata)
        if source_kind == "github":
            github_payload = metadata.get("github")
            if isinstance(github_payload, Mapping):
                direct = text(
                    github_payload.get("url")
                    or github_payload.get("source_ref")
                    or github_payload.get("repository")
                    or github_payload.get("repo")
                    or github_payload.get("target")
                )
                if direct:
                    return direct
        return extract_first_url(question, goal)

    def _resolve_web_page_target(
        self,
        *,
        question: str,
        goal: str,
        metadata: Mapping[str, Any],
    ) -> str:
        web_page_payload = metadata.get("web_page")
        if isinstance(web_page_payload, Mapping):
            direct = text(web_page_payload.get("url") or web_page_payload.get("source_ref"))
            if direct:
                return direct
        discovered_sources = metadata.get("discovered_sources")
        if isinstance(discovered_sources, list):
            for item in discovered_sources:
                if isinstance(item, Mapping):
                    direct = text(item.get("source_ref") or item.get("url"))
                    if direct:
                        return direct
        return extract_first_url(question, goal)

    def _build_web_page_metadata_hit(
        self,
        *,
        metadata: Mapping[str, Any],
    ) -> list[RetrievalHit]:
        web_page_payload = metadata.get("web_page")
        if not isinstance(web_page_payload, Mapping):
            return []
        source_ref = text(web_page_payload.get("url") or web_page_payload.get("source_ref"))
        if not source_ref:
            return []
        snippet = text(
            web_page_payload.get("summary")
            or web_page_payload.get("snippet")
            or web_page_payload.get("title")
        )
        if not snippet:
            return []
        return [
            RetrievalHit(
                source_kind="web_page",
                provider_kind="metadata",
                hit_kind="page",
                ref=source_ref,
                normalized_ref=normalize_ref(source_ref),
                title=text(web_page_payload.get("title")),
                snippet=snippet,
                score=0.92,
                relevance_score=0.92,
                answerability_score=0.88,
                freshness_score=0.0,
                credibility_score=0.85,
                structural_score=0.25,
                why_matched="web page metadata payload",
                metadata={"content_type": text(web_page_payload.get("content_type"))},
            )
        ]


__all__ = ["RetrievalFacade"]
