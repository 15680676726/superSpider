# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from copaw.app.crons.executor import CronExecutor
from copaw.app.crons.models import CronJobSpec
from copaw.industry.compiler import (
    compile_industry_schedule_seeds,
    normalize_industry_profile,
)
from copaw.industry.models import (
    IndustryDraftGoal,
    IndustryDraftPlan,
    IndustryDraftSchedule,
    IndustryPreviewRequest,
    IndustryRoleBlueprint,
    IndustryTeamBlueprint,
)


class _FakeKernelDispatcher:
    def __init__(self) -> None:
        self.tasks: list[object] = []

    def submit(self, task):
        self.tasks.append(task)
        return SimpleNamespace(phase="executing", task_id=task.id)

    async def execute_task(self, task_id: str):
        return SimpleNamespace(success=True, error=None, summary=f"ok:{task_id}")


class _FakeResearchSessionService:
    def __init__(self) -> None:
        self.started: list[dict[str, object]] = []
        self.ran: list[str] = []
        self.summarized: list[str] = []

    def start_session(self, **kwargs):
        self.started.append(dict(kwargs))
        return SimpleNamespace(
            session=SimpleNamespace(id="research-session-1", status="queued"),
            stop_reason=None,
        )

    def run_session(self, session_id: str):
        self.ran.append(session_id)
        return SimpleNamespace(
            session=SimpleNamespace(id=session_id, status="completed"),
            stop_reason="completed",
        )

    def summarize_session(self, session_id: str):
        self.summarized.append(session_id)
        return SimpleNamespace(
            session=SimpleNamespace(id=session_id, status="completed"),
            stop_reason="completed",
        )


def _build_draft() -> tuple[object, IndustryDraftPlan]:
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["Keep researcher monitoring on a governed recurring loop."],
        )
    )
    execution_core = IndustryRoleBlueprint(
        role_id="execution-core",
        agent_id="copaw-agent-runner",
        name="Execution Core",
        role_name="Execution Core",
        role_summary="Owns the main operating loop.",
        mission="Route and supervise governed follow-up work.",
        goal_kind="execution-core",
        reports_to=None,
    )
    researcher = IndustryRoleBlueprint(
        role_id="researcher",
        agent_id="industry-researcher-northwind",
        name="Northwind Researcher",
        role_name="Researcher",
        role_summary="Runs explicit monitoring briefs.",
        mission="Track recurring market and platform signals.",
        goal_kind="researcher",
        agent_class="system",
        reports_to="copaw-agent-runner",
    )
    draft = IndustryDraftPlan(
        team=IndustryTeamBlueprint(
            team_id="industry-v1-northwind-robotics",
            label="Northwind Robotics Spider Mesh Team",
            summary="Durable operating team.",
            topology="lead-plus-support",
            agents=[execution_core, researcher],
        ),
        goals=[
            IndustryDraftGoal(
                goal_id="goal-researcher-monitoring",
                kind="researcher",
                owner_agent_id="industry-researcher-northwind",
                title="Research monitoring loop",
                summary="Keep an explicit monitoring brief on competitor, platform, and market changes.",
                plan_steps=[
                    "Run the explicit monitoring brief.",
                    "Capture evidence-backed findings.",
                    "Route governed follow-up back to the main brain.",
                ],
            )
        ],
        schedules=[
            IndustryDraftSchedule(
                schedule_id="researcher-monitoring-brief",
                owner_agent_id="industry-researcher-northwind",
                title="Northwind Monitoring Brief Review",
                summary=(
                    "Run the explicit researcher monitoring brief for competitor, platform, "
                    "and market changes, then report governed follow-up pressure."
                ),
                cron="0 10 * * 2",
                timezone="UTC",
                dispatch_mode="stream",
            )
        ],
    )
    return profile, draft


def _build_cron_job(seed) -> CronJobSpec:
    return CronJobSpec.model_validate(
        {
            "id": seed.schedule_id,
            "name": seed.title,
            "enabled": True,
            "schedule": {
                "type": "cron",
                "cron": seed.cron,
                "timezone": seed.timezone,
            },
            "task_type": "agent",
            "request": dict(seed.request_payload),
            "dispatch": {
                "type": "channel",
                "channel": seed.dispatch_channel,
                "target": {
                    "user_id": seed.dispatch_user_id,
                    "session_id": seed.dispatch_session_id,
                },
                "mode": seed.dispatch_mode,
                "meta": {
                    "summary": seed.summary,
                    "owner_agent_id": seed.owner_agent_id,
                    **dict(seed.metadata),
                },
            },
            "runtime": {
                "max_concurrency": 1,
                "timeout_seconds": 30,
                "misfire_grace_seconds": 30,
            },
            "meta": {
                "summary": seed.summary,
                "owner_agent_id": seed.owner_agent_id,
                **dict(seed.metadata),
            },
        }
    )


def test_compile_industry_schedule_seeds_marks_explicit_monitoring_brief_for_research_sessions() -> None:
    profile, draft = _build_draft()

    seeds = compile_industry_schedule_seeds(
        profile,
        draft=draft,
        owner_scope="industry-v1-northwind-robotics",
    )

    assert len(seeds) == 1
    seed = seeds[0]
    assert seed.metadata["research_provider"] == "baidu-page"
    assert seed.metadata["research_mode"] == "monitoring-brief"
    assert (
        seed.metadata["research_goal"]
        == "Run the explicit researcher monitoring brief for competitor, platform, and market changes, then report governed follow-up pressure."
    )
    assert seed.metadata["owner_agent_id"] == "industry-researcher-northwind"
    assert seed.metadata["supervisor_agent_id"] == "copaw-agent-runner"


def test_explicit_monitoring_brief_schedule_routes_to_research_session_service() -> None:
    profile, draft = _build_draft()
    seed = compile_industry_schedule_seeds(
        profile,
        draft=draft,
        owner_scope="industry-v1-northwind-robotics",
    )[0]
    dispatcher = _FakeKernelDispatcher()
    research_service = _FakeResearchSessionService()
    executor = CronExecutor(
        kernel_dispatcher=dispatcher,
        research_session_service=research_service,
    )

    asyncio.run(executor.execute(_build_cron_job(seed)))

    assert dispatcher.tasks == []
    assert research_service.started == [
        {
            "goal": (
                "Run the explicit researcher monitoring brief for competitor, platform, "
                "and market changes, then report governed follow-up pressure."
            ),
            "trigger_source": "monitoring",
            "owner_agent_id": "industry-researcher-northwind",
            "industry_instance_id": "industry-v1-northwind-robotics",
            "work_context_id": None,
            "supervisor_agent_id": "copaw-agent-runner",
            "metadata": {
                "schedule_id": "researcher-monitoring-brief",
                "schedule_name": "Northwind Monitoring Brief Review",
                "research_provider": "baidu-page",
                "research_mode": "monitoring-brief",
            },
        }
    ]
    assert research_service.ran == ["research-session-1"]
    assert research_service.summarized == ["research-session-1"]
