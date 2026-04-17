# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.research.source_collection.contracts import (
    CollectedSource,
    ResearchAdapterResult,
    ResearchBrief,
    ResearchFinding,
)
from copaw.research.source_collection.service import SourceCollectionService


def _brief(*, mode_hint: str = "auto") -> ResearchBrief:
    return ResearchBrief(
        owner_agent_id="writer-agent",
        supervisor_agent_id="main-brain",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        goal="fill the current information gap",
        question="which source should be checked next?",
        why_needed="keep the task grounded in external evidence",
        done_when="enough evidence exists to continue",
        collection_mode_hint=mode_hint,
    )


def test_service_runs_light_collection_inline() -> None:
    calls: list[tuple[str, str, str]] = []

    def collect_web_page(brief: ResearchBrief) -> ResearchAdapterResult:
        calls.append(("web_page", brief.owner_agent_id, brief.question))
        return ResearchAdapterResult(
            adapter_kind="web_page",
            collection_action="read",
            status="succeeded",
            collected_sources=[
                CollectedSource(
                    source_id="source-1",
                    source_kind="web_page",
                    collection_action="read",
                    source_ref="https://example.com/page",
                    normalized_ref="https://example.com/page",
                    title="Example Page",
                ),
            ],
        )

    service = SourceCollectionService(
        adapters={"web_page": collect_web_page},
    )

    result = service.collect(
        brief=_brief(),
        owner_agent_id="writer-agent",
        requested_sources=["web_page"],
    )

    assert result.route.mode == "light"
    assert result.route.execution_agent_id == "writer-agent"
    assert calls == [
        ("web_page", "writer-agent", "which source should be checked next?")
    ]


def test_service_routes_heavy_collection_to_researcher() -> None:
    service = SourceCollectionService(
        adapters={
            "search": lambda brief: ResearchAdapterResult(
                adapter_kind="search",
                collection_action="discover",
                status="succeeded",
            ),
            "github": lambda brief: ResearchAdapterResult(
                adapter_kind="github",
                collection_action="read",
                status="succeeded",
            ),
        },
        preferred_researcher_agent_id="industry-researcher-demo",
    )

    result = service.collect(
        brief=_brief(),
        owner_agent_id="writer-agent",
        requested_sources=["search", "github"],
    )

    assert result.route.mode == "heavy"
    assert result.route.execution_agent_id == "industry-researcher-demo"


def test_service_returns_synthesized_unified_result() -> None:
    service = SourceCollectionService(
        adapters={
            "github": lambda brief: ResearchAdapterResult(
                adapter_kind="github",
                collection_action="read",
                status="succeeded",
                collected_sources=[
                    CollectedSource(
                        source_id="source-1",
                        source_kind="repo",
                        collection_action="read",
                        source_ref="https://github.com/example/project",
                        normalized_ref="https://github.com/example/project",
                        title="example/project",
                    ),
                ],
                findings=[
                    ResearchFinding(
                        finding_id="finding-1",
                        finding_type="constraint",
                        summary="Pin the project to the published API contract.",
                        supporting_source_ids=["source-1"],
                    ),
                ],
                conflicts=["Need maintainer confirmation."],
                gaps=["Still missing release note evidence."],
            ),
        },
    )

    result = service.collect(
        brief=_brief(),
        owner_agent_id="writer-agent",
        requested_sources=["github"],
    )

    assert len(result.adapter_results) == 1
    assert len(result.collected_sources) == 1
    assert result.findings[0].summary == "Pin the project to the published API contract."
    assert result.conflicts == ["Need maintainer confirmation."]
    assert result.gaps == ["Still missing release note evidence."]


def test_service_normalizes_requested_sources_before_invoking_adapters() -> None:
    calls: list[str] = []

    def collect_web_page(_brief: ResearchBrief) -> ResearchAdapterResult:
        calls.append("web_page")
        return ResearchAdapterResult(
            adapter_kind="web_page",
            collection_action="read",
            status="succeeded",
        )

    service = SourceCollectionService(adapters={"web_page": collect_web_page})

    result = service.collect(
        brief=_brief(),
        owner_agent_id="writer-agent",
        requested_sources=[" ", "web_page", "web_page"],
    )

    assert result.route.requested_sources == ["web_page"]
    assert calls == ["web_page"]


def test_service_infers_default_search_adapter_when_requested_sources_missing() -> None:
    calls: list[str] = []

    def collect_search(_brief: ResearchBrief) -> ResearchAdapterResult:
        calls.append("search")
        return ResearchAdapterResult(
            adapter_kind="search",
            collection_action="discover",
            status="succeeded",
        )

    service = SourceCollectionService(adapters={"search": collect_search})

    result = service.collect(
        brief=_brief(),
        owner_agent_id="writer-agent",
        requested_sources=[],
    )

    assert result.route.requested_sources == ["search"]
    assert calls == ["search"]
