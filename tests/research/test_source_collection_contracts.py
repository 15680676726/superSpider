# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from pydantic import ValidationError

from copaw.research.source_collection.contracts import (
    CollectedSource,
    ResearchAdapterResult,
    ResearchBrief,
    ResearchFinding,
    ResearchWritebackTarget,
)


def test_research_brief_contract_round_trip() -> None:
    brief = ResearchBrief(
        owner_agent_id="writer-agent",
        supervisor_agent_id="main-brain",
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        assignment_id="assignment-1",
        goal="stabilize story continuity constraints",
        question="what world rules must stay fixed in the next chapter?",
        why_needed="avoid continuity drift",
        done_when="have 3-5 reusable continuity rules",
        writeback_target=ResearchWritebackTarget(
            scope_type="work_context",
            scope_id="ctx-1",
        ),
        collection_mode_hint="auto",
    )

    assert brief.owner_agent_id == "writer-agent"
    assert brief.collection_mode_hint == "auto"
    assert brief.work_context_id == "ctx-1"
    assert brief.writeback_target.scope_type == "work_context"


def test_collected_source_supports_open_taxonomy_and_collection_action() -> None:
    source = CollectedSource(
        source_id="source-1",
        source_kind="repo",
        collection_action="read",
        source_ref="https://github.com/example/project",
        normalized_ref="https://github.com/example/project",
        title="example/project",
        evidence_id="evidence-1",
    )

    assert source.source_id == "source-1"
    assert source.source_kind == "repo"
    assert source.collection_action == "read"
    assert source.source_ref == "https://github.com/example/project"
    assert source.evidence_id == "evidence-1"


def test_adapter_result_carries_findings_and_sources() -> None:
    finding = ResearchFinding(
        finding_id="finding-1",
        finding_type="continuity-rule",
        summary="Keep the twelve-house system fixed across drafts.",
        supporting_source_ids=["source-1"],
        supporting_evidence_ids=["evidence-1"],
    )
    result = ResearchAdapterResult(
        adapter_kind="github",
        collection_action="read",
        status="succeeded",
        session_id="session-1",
        round_id="round-1",
        collected_sources=[
            CollectedSource(
                source_id="source-1",
                source_kind="repo",
                collection_action="read",
                source_ref="https://github.com/example/project",
                title="example/project",
                evidence_id="evidence-1",
            ),
        ],
        findings=[finding],
    )

    assert result.adapter_kind == "github"
    assert result.findings[0].finding_type == "continuity-rule"
    assert result.collected_sources[0].source_kind == "repo"
    assert result.session_id == "session-1"


def test_collected_source_rejects_unknown_collection_action() -> None:
    with pytest.raises(ValidationError):
        CollectedSource(
            source_id="source-1",
            source_kind="repo",
            collection_action="crawl",
            source_ref="https://github.com/example/project",
        )
