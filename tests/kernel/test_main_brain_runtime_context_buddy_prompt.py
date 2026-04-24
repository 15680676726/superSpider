# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import copaw.kernel.query_execution as query_execution_module
import copaw.kernel.query_execution_prompt as query_execution_prompt_module
from copaw.kernel.query_execution import KernelQueryExecutionService
from copaw.state import SQLiteStateStore
from copaw.state.executor_runtime_service import ExecutorRuntimeService
from copaw.state.repositories import SqliteAgentCheckpointRepository

from .query_execution_environment_parts.shared import *  # noqa: F401,F403


class _FakeBuddyProjectionService:
    def build_chat_surface(self, *, profile_id: str | None = None):
        assert profile_id == "profile-buddy"
        contract = {
            "service_intent": "Turn creative ambition into a steady weekly publishing rhythm.",
            "collaboration_role": "orchestrator",
            "autonomy_level": "guarded-proactive",
            "report_style": "decision-first",
            "confirm_boundaries": ["external spend", "publishing under my real name"],
            "collaboration_notes": "Keep reports short and escalate blockers with one recommendation.",
        }
        return SimpleNamespace(
            profile=SimpleNamespace(
                profile_id="profile-buddy",
                display_name="Ava",
                profession="Independent creator",
                current_stage="rebuilding",
            ),
            growth_target=SimpleNamespace(
                primary_direction="Build an independent creative business with proof of work.",
                final_goal="Create a durable publishing rhythm that compounds into a real business.",
            ),
            relationship=SimpleNamespace(
                **contract,
                encouragement_style="old-friend",
                effective_reminders=["Shrink the task to one concrete move."],
                ineffective_reminders=["Do not use high-pressure pushing."],
                avoidance_patterns=["Doom-scrolling instead of shipping."],
            ),
            onboarding=SimpleNamespace(
                status="named",
                **contract,
            ),
            presentation=SimpleNamespace(
                buddy_name="Nova",
                current_goal_summary="Create a durable publishing rhythm that compounds into a real business.",
                current_task_summary="Draft the first public case study.",
                why_now_summary="Because this is the first proof that turns direction into reality.",
                single_next_action_summary="Open the draft and write the headline plus three proof points.",
                companion_strategy_summary=(
                    "Receive emotion first, then shrink the task to one concrete move; "
                    "avoid high-pressure pushing and pull attention back from doom-scrolling."
                ),
            ),
            growth=SimpleNamespace(
                intimacy=42,
                affinity=36,
                growth_level=3,
                evolution_stage="bonded",
            ),
        )


class _ContractAwareIndustryService(_FakeIndustryService):
    def get_instance_detail(self, instance_id: str):
        detail = super().get_instance_detail(instance_id)
        detail.execution_core_identity.update(
            {
                "operator_service_intent": "Turn creative ambition into a steady weekly publishing rhythm.",
                "collaboration_role": "orchestrator",
                "autonomy_level": "guarded-proactive",
                "report_style": "decision-first",
                "confirm_boundaries": [
                    "external spend",
                    "publishing under my real name",
                ],
                "collaboration_notes": "Keep reports short and escalate blockers with one recommendation.",
                "operating_mode": "guarded-collaboration",
                "delegation_policy": [
                    "Coordinate direction and delegate leaf execution to the right specialist lane.",
                ],
                "direct_execution_policy": [
                    "Do not let the execution core swallow browser or document leaf work.",
                ],
            },
        )
        return detail


def _seed_executor_runtime(
    state_store: SQLiteStateStore,
    *,
    agent_id: str,
    thread_id: str,
) -> ExecutorRuntimeService:
    service = ExecutorRuntimeService(state_store=state_store)
    runtime = service.create_or_reuse_runtime(
        executor_id="codex",
        protocol_kind="app_server",
        scope_kind="role",
        role_id=agent_id,
        thread_id=thread_id,
        metadata={
            "owner_agent_id": agent_id,
            "display_name": "Ops Agent",
            "role_name": "Operations lead",
            "industry_instance_id": "industry-v1-ops",
            "industry_role_id": "execution-core",
        },
        continuity_metadata={
            "control_thread_id": thread_id,
            "session_id": thread_id,
        },
    )
    service.mark_runtime_ready(
        runtime.runtime_id,
        thread_id=thread_id,
        metadata={"owner_agent_id": agent_id},
    )
    return service


def test_query_execution_service_appends_buddy_persona_prompt_when_bound_profile_exists(
    tmp_path,
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    monkeypatch.setattr(query_execution_module, "CoPawAgent", _FakeAgent)
    monkeypatch.setattr(
        query_execution_module,
        "stream_printing_messages",
        _fake_stream_printing_messages,
    )
    monkeypatch.setattr(
        query_execution_module,
        "load_config",
        lambda: SimpleNamespace(
            agents=SimpleNamespace(
                running=SimpleNamespace(max_iters=1, max_input_length=512),
            ),
        ),
    )

    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    executor_runtime_service = _seed_executor_runtime(
        state_store,
        agent_id="ops-agent",
        thread_id="industry-chat:industry-v1-ops:execution-core",
    )
    checkpoint_repository = SqliteAgentCheckpointRepository(state_store)

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_ContractAwareIndustryService(),
        agent_checkpoint_repository=checkpoint_repository,
        executor_runtime_service=executor_runtime_service,
        buddy_projection_service=_FakeBuddyProjectionService(),
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "Help me push this step forward.")],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="ops-user",
                agent_id="ops-agent",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                session_kind="industry-agent-chat",
                buddy_profile_id="profile-buddy",
            ),
            kernel_task_id="kernel-main-brain-1",
        ):
            pass

    asyncio.run(_run())

    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    expected_lines = [
        "# 伙伴对外人格",
        "伙伴名：Nova",
        "服务意图：Turn creative ambition into a steady weekly publishing rhythm.",
        "协作角色：orchestrator",
        "主动级别：guarded-proactive",
        "汇报风格：decision-first",
        "这些事项必须先确认：external spend, publishing under my real name",
        "协作备注：Keep reports short and escalate blockers with one recommendation.",
        "# Execution Core Identity",
        "运行模式：guarded-collaboration",
        "派工规则：Coordinate direction and delegate leaf execution to the right specialist lane.",
        "直接执行规则：Do not let the execution core swallow browser or document leaf work.",
    ]
    for line in expected_lines:
        assert line in prompt_appendix


def test_query_execution_service_appends_current_time_grounding_for_buddy_runtime(
    tmp_path,
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    monkeypatch.setattr(query_execution_module, "CoPawAgent", _FakeAgent)
    monkeypatch.setattr(
        query_execution_module,
        "stream_printing_messages",
        _fake_stream_printing_messages,
    )
    monkeypatch.setattr(
        query_execution_module,
        "load_config",
        lambda: SimpleNamespace(
            agents=SimpleNamespace(
                running=SimpleNamespace(max_iters=1, max_input_length=512),
            ),
        ),
    )
    monkeypatch.setattr(
        query_execution_prompt_module,
        "_current_prompt_time_snapshot",
        lambda: "Beijing time 2026-04-09 Thu 10:00",
        raising=False,
    )

    state_store = SQLiteStateStore(tmp_path / "state-time.sqlite3")
    executor_runtime_service = _seed_executor_runtime(
        state_store,
        agent_id="ops-agent",
        thread_id="industry-chat:industry-v1-ops:execution-core",
    )
    checkpoint_repository = SqliteAgentCheckpointRepository(state_store)

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_ContractAwareIndustryService(),
        agent_checkpoint_repository=checkpoint_repository,
        executor_runtime_service=executor_runtime_service,
        buddy_projection_service=_FakeBuddyProjectionService(),
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "What day is it today?")],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="ops-user",
                agent_id="ops-agent",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                session_kind="industry-agent-chat",
                buddy_profile_id="profile-buddy",
            ),
            kernel_task_id="kernel-main-brain-time-1",
        ):
            pass

    asyncio.run(_run())

    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "Current Time" in prompt_appendix
    assert "Beijing time 2026-04-09 Thu 10:00" in prompt_appendix
    assert "do not guess" in prompt_appendix.lower()
