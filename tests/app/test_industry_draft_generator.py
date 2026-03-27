# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from copaw.industry import (
    IndustryDraftGenerator,
    IndustryPreviewRequest,
    normalize_industry_profile,
)


class _StreamingStructuredModel:
    def __init__(self, payload: dict):
        self._payload = payload

    async def __call__(self, **kwargs):
        async def _stream():
            yield SimpleNamespace(metadata=self._payload, content=[])

        return _stream()


class _MessageCaptureStructuredModel:
    def __init__(self, payload: dict):
        self._payload = payload
        self.last_messages = None

    async def __call__(self, **kwargs):
        self.last_messages = kwargs.get("messages")
        return SimpleNamespace(metadata=self._payload, content=[])


def test_industry_draft_generator_consumes_streamed_structured_response() -> None:
    payload = {
        "team": {
            "label": "Northwind Robotics AI Draft",
            "summary": "Editable AI-generated team draft.",
            "topology": "solo",
            "agents": [
                {
                    "role_id": "execution-core",
                    "name": "白泽执行中枢",
                    "role_name": "白泽执行中枢",
                    "role_summary": "Owns the operating brief.",
                    "mission": "Choose the next move.",
                    "goal_kind": "execution-core",
                    "agent_class": "business",
                    "activation_mode": "persistent",
                    "suspendable": False,
                    "risk_level": "guarded",
                },
                {
                    "role_id": "solution-lead",
                    "name": "Northwind Solution Lead",
                    "role_name": "Solution Lead",
                    "role_summary": "Shapes the operating design.",
                    "mission": "Turn the brief into a rollout-ready solution.",
                    "goal_kind": "solution",
                    "agent_class": "business",
                    "activation_mode": "persistent",
                    "suspendable": False,
                    "reports_to": "execution-core",
                    "risk_level": "guarded",
                },
            ],
        },
        "goals": [
            {
                "goal_id": "execution-core-goal",
                "kind": "execution-core",
                "owner_agent_id": "copaw-agent-runner",
                "title": "Operate Northwind Robotics",
                "summary": "Create the next operating brief.",
                "plan_steps": ["Review the brief", "Choose the next move"],
            },
            {
                "goal_id": "solution-goal",
                "kind": "solution",
                "owner_agent_id": "solution-lead",
                "title": "Shape the rollout",
                "summary": "Define the rollout path.",
                "plan_steps": ["Clarify the offer", "List dependencies"],
            },
        ],
        "schedules": [
            {
                "schedule_id": "execution-core-review",
                "owner_agent_id": "copaw-agent-runner",
                "title": "Northwind 白泽执行中枢复盘",
                "summary": "Recurring review for the team's execution core loop.",
                "cron": "0 9 * * *",
                "timezone": "UTC",
                "dispatch_mode": "stream",
            }
        ],
        "generation_summary": "AI streamed a draft response.",
    }
    generator = IndustryDraftGenerator(
        model_factory=lambda: _StreamingStructuredModel(payload),
    )
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Equipment",
            company_name="Northwind Robotics",
            product="factory monitoring copilots",
            goals=["launch two pilot deployments"],
        ),
    )

    draft = asyncio.run(
        generator.generate(
            profile=profile,
            owner_scope="industry-v1-northwind-robotics",
        ),
    )

    assert draft.team.label == "Northwind Robotics AI Draft"
    assert draft.team.topology == "solo"
    assert draft.generation_summary == "AI streamed a draft response."
    assert {role.role_id for role in draft.team.agents} == {
        "execution-core",
        "researcher",
        "solution-lead",
    }
    execution_core = next(
        role for role in draft.team.agents if role.role_id == "execution-core"
    )
    assert execution_core.agent_id == "copaw-agent-runner"
    assert execution_core.role_name == "Spider Mesh 执行中枢"
    assert execution_core.agent_class == "business"
    root_goal = next(goal for goal in draft.goals if goal.owner_agent_id == "copaw-agent-runner")
    assert root_goal.kind == "execution-core"
    assert any(goal.kind == "solution" for goal in draft.goals)
    assert draft.schedules[0].owner_agent_id == "copaw-agent-runner"
    assert draft.schedules[0].title == "Northwind Spider Mesh 执行中枢复盘"


def test_industry_draft_generator_includes_operator_planning_context() -> None:
    payload = {
        "team": {
            "label": "Northwind Robotics AI Draft",
            "summary": "Editable AI-generated team draft.",
            "topology": "solo",
            "agents": [
                {
                    "role_id": "execution-core",
                    "name": "白泽执行中枢",
                    "role_name": "白泽执行中枢",
                    "role_summary": "Owns the operating brief.",
                    "mission": "Choose the next move.",
                    "goal_kind": "execution-core",
                    "agent_class": "business",
                    "activation_mode": "persistent",
                    "suspendable": False,
                    "risk_level": "guarded",
                },
                {
                    "role_id": "solution-lead",
                    "name": "Northwind Solution Lead",
                    "role_name": "Solution Lead",
                    "role_summary": "Shapes the operating design.",
                    "mission": "Turn the brief into a rollout-ready solution.",
                    "goal_kind": "solution",
                    "agent_class": "business",
                    "activation_mode": "persistent",
                    "suspendable": False,
                    "reports_to": "execution-core",
                    "risk_level": "guarded",
                },
            ],
        },
        "goals": [
            {
                "goal_id": "execution-core-goal",
                "kind": "execution-core",
                "owner_agent_id": "copaw-agent-runner",
                "title": "Operate Northwind Robotics",
                "summary": "Create the next operating brief.",
                "plan_steps": ["Review the brief", "Choose the next move"],
            }
        ],
        "schedules": [],
        "generation_summary": "AI draft response.",
    }
    model = _MessageCaptureStructuredModel(payload)
    generator = IndustryDraftGenerator(model_factory=lambda: model)
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Equipment",
            company_name="Northwind Robotics",
            product="factory monitoring copilots",
            goals=["launch two pilot deployments"],
            experience_mode="operator-guided",
            experience_notes="先看近 7 天线索质量，再决定是否加大投放。",
            operator_requirements=["必须包含客服聊天闭环", "必须保留每周同行监控"],
        ),
    )

    asyncio.run(
        generator.generate(
            profile=profile,
            owner_scope="industry-v1-northwind-robotics",
        ),
    )

    assert model.last_messages is not None
    combined = "\n".join(str(item.get("content")) for item in model.last_messages)
    assert "Planning mode: operator-guided" in combined
    assert "客服聊天闭环" in combined
    assert "近 7 天线索质量" in combined
