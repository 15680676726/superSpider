# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.research.source_collection.contracts import ResearchBrief
from copaw.research.source_collection.routing import route_collection_mode


def _brief() -> ResearchBrief:
    return ResearchBrief(
        owner_agent_id="writer-agent",
        supervisor_agent_id="main-brain",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        goal="fill the current information gap",
        question="what source should be checked next?",
        why_needed="keep the task grounded in external evidence",
        done_when="enough evidence exists to continue",
    )


def test_route_collection_mode_marks_single_page_lookup_as_light() -> None:
    decision = route_collection_mode(_brief(), requested_sources=["web_page"])

    assert decision.mode == "light"
    assert decision.execution_agent_id == "writer-agent"


def test_route_collection_mode_marks_multi_source_comparison_as_heavy() -> None:
    decision = route_collection_mode(
        _brief(),
        requested_sources=["search", "github", "web_page"],
        preferred_researcher_agent_id="industry-researcher-demo",
    )

    assert decision.mode == "heavy"
    assert decision.execution_agent_id == "industry-researcher-demo"
