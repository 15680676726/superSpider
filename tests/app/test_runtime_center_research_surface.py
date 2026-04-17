# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.state import ResearchSessionRecord, ResearchSessionRoundRecord, SQLiteStateStore
from copaw.state.repositories import SqliteResearchSessionRepository


def _build_client(tmp_path) -> tuple[TestClient, SqliteResearchSessionRepository]:
    app = FastAPI()
    repository = SqliteResearchSessionRepository(SQLiteStateStore(tmp_path / "state.db"))
    app.state.research_session_repository = repository
    app.include_router(runtime_center_router)
    return TestClient(app), repository


def test_runtime_center_research_surface_exposes_structured_research_truth(tmp_path) -> None:
    client, repository = _build_client(tmp_path)
    session = repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-structured",
            provider="baidu-page",
            owner_agent_id="industry-researcher-demo",
            supervisor_agent_id="copaw-agent-runner",
            industry_instance_id="industry-demo",
            work_context_id="ctx-research-1",
            trigger_source="main-brain-followup",
            goal="补齐竞品定价和官网能力来源",
            status="running",
            round_count=2,
            stable_findings=["竞品官网已把基础套餐上调到每月 299 元。"],
            open_questions=["还缺官方定价页截图。"],
            final_report_id="report-research-1",
            metadata={
                "brief": {
                    "goal": "补齐竞品定价和官网能力来源",
                    "question": "飞书相关竞品最近的定价和能力变化是什么？",
                    "why_needed": "主脑要决定本周产品定位和跟进动作。",
                    "done_when": "至少拿到官网定价、核心能力和可信来源。",
                    "collection_mode_hint": "heavy",
                    "requested_sources": ["search", "web_page"],
                    "writeback_target": {
                        "scope_type": "work_context",
                        "scope_id": "ctx-research-1",
                    },
                },
                "conflicts": ["第三方博客和官网的价格口径不一致。"],
                "writeback_truth": {
                    "status": "written",
                    "scope_type": "work_context",
                    "scope_id": "ctx-research-1",
                    "report_id": "report-research-1",
                },
            },
        ),
    )
    repository.upsert_research_round(
        ResearchSessionRoundRecord(
            id="research-round-structured",
            session_id=session.id,
            round_index=2,
            question="继续核对官网和外部解读",
            response_summary="已拿到官网定价页和一篇第三方解读。",
            new_findings=["官网定价页显示基础套餐为每月 299 元。"],
            remaining_gaps=["还缺官网截图归档。"],
            selected_links=[
                {
                    "url": "https://example.com/pricing",
                    "title": "官网定价页",
                    "kind": "web",
                }
            ],
            metadata={
                "findings": [
                    {
                        "finding_id": "finding-pricing",
                        "finding_type": "pricing",
                        "summary": "官网定价页显示基础套餐为每月 299 元。",
                        "supporting_source_ids": ["source-pricing"],
                        "supporting_evidence_ids": ["evidence-pricing"],
                    }
                ],
                "collected_sources": [
                    {
                        "source_id": "source-pricing",
                        "source_kind": "web_page",
                        "collection_action": "read",
                        "source_ref": "https://example.com/pricing",
                        "normalized_ref": "https://example.com/pricing",
                        "title": "官网定价页",
                        "snippet": "基础套餐 299 元 / 月",
                        "evidence_id": "evidence-pricing",
                    }
                ],
                "gaps": ["还缺官网截图归档。"],
                "conflicts": ["第三方博客把旧价格写成了 199 元。"],
            },
        ),
    )

    response = client.get("/runtime-center/research")

    assert response.status_code == 200
    payload = response.json()
    assert payload["brief"] == {
        "goal": "补齐竞品定价和官网能力来源",
        "question": "飞书相关竞品最近的定价和能力变化是什么？",
        "why_needed": "主脑要决定本周产品定位和跟进动作。",
        "done_when": "至少拿到官网定价、核心能力和可信来源。",
        "collection_mode_hint": "heavy",
        "requested_sources": ["search", "web_page"],
        "writeback_target": {
            "scope_type": "work_context",
            "scope_id": "ctx-research-1",
        },
    }
    assert payload["findings"] == [
        {
            "finding_id": "finding-pricing",
            "finding_type": "pricing",
            "summary": "官网定价页显示基础套餐为每月 299 元。",
            "supporting_source_ids": ["source-pricing"],
            "supporting_evidence_ids": ["evidence-pricing"],
            "conflicts": [],
            "gaps": [],
        }
    ]
    assert payload["sources"] == [
        {
            "source_id": "source-pricing",
            "source_kind": "web_page",
            "collection_action": "read",
            "source_ref": "https://example.com/pricing",
            "normalized_ref": "https://example.com/pricing",
            "title": "官网定价页",
            "snippet": "基础套餐 299 元 / 月",
            "access_status": "",
            "evidence_id": "evidence-pricing",
            "artifact_id": None,
            "captured_at": None,
        }
    ]
    assert payload["gaps"] == ["还缺官网截图归档。"]
    assert payload["conflicts"] == ["第三方博客把旧价格写成了 199 元。"]
    assert payload["writeback_truth"] == {
        "status": "written",
        "scope_type": "work_context",
        "scope_id": "ctx-research-1",
        "report_id": "report-research-1",
    }


def test_runtime_center_research_surface_derives_minimum_truth_without_structured_metadata(
    tmp_path,
) -> None:
    client, repository = _build_client(tmp_path)
    session = repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-fallback",
            provider="baidu-page",
            owner_agent_id="industry-researcher-demo",
            work_context_id="ctx-research-2",
            trigger_source="user-direct",
            goal="梳理同类产品的核心能力差异",
            status="running",
            round_count=1,
            stable_findings=["找到 2 个官网能力对比点。"],
            open_questions=["还缺一条官方案例证据。"],
            final_report_id="report-research-2",
        ),
    )
    repository.upsert_research_round(
        ResearchSessionRoundRecord(
            id="research-round-fallback",
            session_id=session.id,
            round_index=1,
            question="先从官网能力页开始",
            response_summary="先拿到官网能力页。",
            new_findings=["官网能力页明确写了自动化编排能力。"],
            remaining_gaps=["还缺一条官方案例证据。"],
            selected_links=[
                {
                    "url": "https://example.com/capabilities",
                    "title": "官网能力页",
                    "kind": "web",
                }
            ],
        ),
    )

    response = client.get("/runtime-center/research")

    assert response.status_code == 200
    payload = response.json()
    assert payload["brief"] == {
        "goal": "梳理同类产品的核心能力差异",
        "question": "先从官网能力页开始",
        "why_needed": None,
        "done_when": None,
        "collection_mode_hint": None,
        "requested_sources": [],
        "writeback_target": {
            "scope_type": "work_context",
            "scope_id": "ctx-research-2",
        },
    }
    assert payload["findings"] == [
        {
            "finding_id": "research-session-fallback:finding:1",
            "finding_type": "finding",
            "summary": "官网能力页明确写了自动化编排能力。",
            "supporting_source_ids": [],
            "supporting_evidence_ids": [],
            "conflicts": [],
            "gaps": [],
        }
    ]
    assert payload["sources"] == [
        {
            "source_id": "research-session-fallback:source:1",
            "source_kind": "web",
            "collection_action": "read",
            "source_ref": "https://example.com/capabilities",
            "normalized_ref": "https://example.com/capabilities",
            "title": "官网能力页",
            "snippet": "",
            "access_status": "",
            "evidence_id": None,
            "artifact_id": None,
            "captured_at": None,
        }
    ]
    assert payload["gaps"] == ["还缺一条官方案例证据。"]
    assert payload["conflicts"] == []
    assert payload["writeback_truth"] == {
        "status": "pending",
        "scope_type": "work_context",
        "scope_id": "ctx-research-2",
        "report_id": "report-research-2",
    }


def test_runtime_center_research_surface_prefers_formal_brief_and_round_source_fields(
    tmp_path,
) -> None:
    client, repository = _build_client(tmp_path)
    session = repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-formal-fields",
            provider="source-collection",
            owner_agent_id="writer-agent",
            supervisor_agent_id="main-brain",
            work_context_id="ctx-formal-1",
            trigger_source="agent-entry",
            goal="查官网定价",
            status="completed",
            round_count=1,
            brief={
                "goal": "查官网定价",
                "question": "官网定价是多少",
                "why_needed": "主脑要做价格对比",
                "done_when": "拿到官网价格和来源",
                "collection_mode_hint": "light",
                "requested_sources": ["web_page"],
                "writeback_target": {
                    "scope_type": "work_context",
                    "scope_id": "ctx-formal-1",
                },
            },
        ),
    )
    repository.upsert_research_round(
        ResearchSessionRoundRecord(
            id="research-session-formal-fields:round:1",
            session_id=session.id,
            round_index=1,
            question="官网定价是多少",
            response_summary="官网定价页显示基础套餐 299 元 / 月。",
            new_findings=["官网定价页显示基础套餐 299 元 / 月。"],
            sources=[
                {
                    "source_id": "source-formal-1",
                    "source_kind": "web_page",
                    "collection_action": "read",
                    "source_ref": "https://example.com/pricing",
                    "normalized_ref": "https://example.com/pricing",
                    "title": "官网定价页",
                    "snippet": "基础套餐 299 元 / 月",
                }
            ],
        ),
    )

    response = client.get("/runtime-center/research")

    assert response.status_code == 200
    payload = response.json()
    assert payload["brief"] == {
        "goal": "查官网定价",
        "question": "官网定价是多少",
        "why_needed": "主脑要做价格对比",
        "done_when": "拿到官网价格和来源",
        "collection_mode_hint": "light",
        "requested_sources": ["web_page"],
        "writeback_target": {
            "scope_type": "work_context",
            "scope_id": "ctx-formal-1",
        },
    }
    assert payload["sources"] == [
        {
            "source_id": "source-formal-1",
            "source_kind": "web_page",
            "collection_action": "read",
            "source_ref": "https://example.com/pricing",
            "normalized_ref": "https://example.com/pricing",
            "title": "官网定价页",
            "snippet": "基础套餐 299 元 / 月",
            "access_status": "",
            "evidence_id": None,
            "artifact_id": None,
            "captured_at": None,
        }
    ]


def test_runtime_center_research_surface_prefers_formal_findings_conflicts_gaps_and_writeback_fields(
    tmp_path,
) -> None:
    client, repository = _build_client(tmp_path)
    session = repository.upsert_research_session(
        ResearchSessionRecord(
            id="research-session-formal-projections",
            provider="source-collection",
            owner_agent_id="writer-agent",
            supervisor_agent_id="main-brain",
            work_context_id="ctx-formal-2",
            trigger_source="agent-entry",
            goal="查官网定价",
            status="completed",
            round_count=1,
            stable_findings=["旧 fallback finding"],
            open_questions=["旧 fallback gap"],
            brief={
                "goal": "查官网定价",
                "question": "官网定价是多少",
                "why_needed": "主脑要做价格对比",
                "done_when": "拿到官网价格和来源",
                "collection_mode_hint": "light",
                "requested_sources": ["web_page"],
                "writeback_target": {
                    "scope_type": "work_context",
                    "scope_id": "ctx-formal-2",
                },
            },
            conflicts=["formal session conflict"],
            writeback_truth={
                "status": "written",
                "scope_type": "work_context",
                "scope_id": "ctx-formal-2",
                "report_id": "report-formal-2",
            },
            metadata={
                "conflicts": ["legacy metadata conflict"],
                "writeback_truth": {
                    "status": "pending",
                    "scope_type": "industry",
                    "scope_id": "industry-legacy",
                    "report_id": "report-legacy",
                },
            },
        ),
    )
    repository.upsert_research_round(
        ResearchSessionRoundRecord(
            id="research-session-formal-projections:round:1",
            session_id=session.id,
            round_index=1,
            question="官网定价是多少",
            response_summary="官网定价页显示基础套餐 299 元 / 月。",
            new_findings=["旧 fallback round finding"],
            remaining_gaps=["旧 fallback round gap"],
            findings=[
                {
                    "finding_id": "finding-formal-1",
                    "finding_type": "pricing",
                    "summary": "官网定价页显示基础套餐 299 元 / 月。",
                    "supporting_source_ids": ["source-formal-2"],
                    "supporting_evidence_ids": ["evidence-formal-2"],
                }
            ],
            conflicts=["formal round conflict"],
            gaps=["formal round gap"],
            writeback_truth={
                "status": "written",
                "scope_type": "work_context",
                "scope_id": "ctx-formal-2",
                "report_id": "report-formal-2",
            },
            sources=[
                {
                    "source_id": "source-formal-2",
                    "source_kind": "web_page",
                    "collection_action": "read",
                    "source_ref": "https://example.com/pricing",
                    "normalized_ref": "https://example.com/pricing",
                    "title": "官网定价页",
                    "snippet": "基础套餐 299 元 / 月",
                    "evidence_id": "evidence-formal-2",
                }
            ],
            metadata={
                "findings": [
                    {
                        "finding_id": "finding-legacy-1",
                        "finding_type": "legacy",
                        "summary": "legacy metadata finding",
                    }
                ],
                "conflicts": ["legacy round metadata conflict"],
                "gaps": ["legacy round metadata gap"],
                "writeback_truth": {
                    "status": "pending",
                    "scope_type": "industry",
                    "scope_id": "industry-legacy",
                    "report_id": "report-legacy",
                },
            },
        ),
    )

    response = client.get("/runtime-center/research")

    assert response.status_code == 200
    payload = response.json()
    assert payload["findings"] == [
        {
            "finding_id": "finding-formal-1",
            "finding_type": "pricing",
            "summary": "官网定价页显示基础套餐 299 元 / 月。",
            "supporting_source_ids": ["source-formal-2"],
            "supporting_evidence_ids": ["evidence-formal-2"],
            "conflicts": [],
            "gaps": [],
        }
    ]
    assert payload["gaps"] == ["formal round gap"]
    assert payload["conflicts"] == ["formal round conflict"]
    assert payload["writeback_truth"] == {
        "status": "written",
        "scope_type": "work_context",
        "scope_id": "ctx-formal-2",
        "report_id": "report-formal-2",
    }
