# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from copaw.kernel import KernelQueryExecutionService
from copaw.kernel import query_execution_runtime as query_execution_module


class _FakeIndustryService:
    def get_instance_detail(self, instance_id: str):
        assert instance_id == "industry-v1-demo"
        return {
            "staffing": {
                "researcher": {
                    "agent_id": "industry-researcher-demo",
                    "role_name": "Researcher",
                }
            }
        }


class _FakeSourceCollectionFrontdoor:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run_source_collection_frontdoor(self, **kwargs):
        self.calls.append(dict(kwargs))
        return SimpleNamespace(
            session_id="research-light-1",
            status="completed",
            route_mode="light",
            execution_agent_id=str(kwargs.get("owner_agent_id") or ""),
            findings=[
                {
                    "finding_id": "finding-1",
                    "summary": "官网定价页显示基础套餐已经更新。",
                }
            ],
            collected_sources=[
                {
                    "source_id": "source-1",
                    "source_kind": "web_page",
                    "source_ref": "https://example.com/pricing",
                }
            ],
            conflicts=[],
            gaps=[],
        )


def test_agent_entry_collect_sources_tool_routes_light_collection_through_unified_frontdoor() -> None:
    service = KernelQueryExecutionService(
        session_backend=object(),
        industry_service=_FakeIndustryService(),
    )
    frontdoor = _FakeSourceCollectionFrontdoor()
    service._source_collection_frontdoor = frontdoor
    request = SimpleNamespace(
        session_id="industry-chat-1",
        user_id="ops-writer-demo",
        agent_id="ops-writer-demo",
        channel="industry",
        owner_scope="industry-v1-demo-scope",
        industry_instance_id="industry-v1-demo",
        industry_role_id="writer",
        work_context_id="ctx-agent-entry-1",
        session_kind="industry-agent-chat",
        entry_source="agent-workbench",
    )

    tool_functions = service._build_system_tool_functions(
        request=request,
        owner_agent_id="ops-writer-demo",
        agent_profile=None,
        system_capability_ids={"system:dispatch_query"},
        kernel_task_id="task-agent-entry-1",
    )
    tools_by_name = {
        tool_fn.__name__: tool_fn
        for tool_fn in tool_functions
    }

    assert "collect_sources" in tools_by_name

    result = asyncio.run(
        tools_by_name["collect_sources"](
            question="查一下官网定价页最近有没有更新",
            requested_sources=["web_page"],
        )
    )
    payload = query_execution_module._structured_tool_payload(
        result,
        default_error="collect_sources test payload missing",
    )

    assert payload["success"] is True
    assert payload["route_mode"] == "light"
    assert payload["execution_agent_id"] == "ops-writer-demo"
    assert payload["session_id"] == "research-light-1"
    assert frontdoor.calls == [
        {
            "goal": "查一下官网定价页最近有没有更新",
            "question": "查一下官网定价页最近有没有更新",
            "why_needed": None,
            "done_when": None,
            "trigger_source": "agent-entry",
            "owner_agent_id": "ops-writer-demo",
            "preferred_researcher_agent_id": "industry-researcher-demo",
            "industry_instance_id": "industry-v1-demo",
            "work_context_id": "ctx-agent-entry-1",
            "assignment_id": None,
            "task_id": "task-agent-entry-1",
            "supervisor_agent_id": "ops-writer-demo",
            "collection_mode_hint": "auto",
            "requested_sources": ["web_page"],
            "writeback_target": {
                "scope_type": "work_context",
                "scope_id": "ctx-agent-entry-1",
            },
            "metadata": {
                "entry_surface": "query-execution-tools",
                "entry_source": "agent-workbench",
                "request_channel": "industry",
            },
        }
    ]
