# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import copaw.kernel.query_execution as query_execution_module
import copaw.kernel.query_execution_prompt as query_execution_prompt_module
from copaw.kernel.query_execution import KernelQueryExecutionService
from copaw.state import (
    AgentRuntimeRecord,
    SQLiteStateStore,
)
from copaw.state.repositories import (
    SqliteAgentCheckpointRepository,
    SqliteAgentMailboxRepository,
    SqliteAgentRuntimeRepository,
)
from copaw.kernel import ActorMailboxService

from .query_execution_environment_parts.shared import *  # noqa: F401,F403


class _FakeBuddyProjectionService:
    def build_chat_surface(self, *, profile_id: str | None = None):
        assert profile_id == "profile-buddy"
        return SimpleNamespace(
            profile=SimpleNamespace(
                profile_id="profile-buddy",
                display_name="阿澄",
                profession="自由创作者",
                current_stage="重建期",
            ),
            growth_target=SimpleNamespace(
                primary_direction="建立独立创作与内容事业的长期成长路径",
                final_goal="帮助阿澄建立可持续的创作事业与独立成长轨道",
            ),
            relationship=SimpleNamespace(
                encouragement_style="old-friend",
                effective_reminders=["先把任务缩成一个最小动作"],
                ineffective_reminders=["高压催促"],
                avoidance_patterns=["刷短视频逃避"],
            ),
            presentation=SimpleNamespace(
                buddy_name="小澄",
                current_goal_summary="帮助阿澄建立可持续的创作事业与独立成长轨道",
                current_task_summary="写出第一篇真正能代表自己的案例文章",
                why_now_summary="因为这是把长期方向从想象拉进现实的第一份证据。",
                single_next_action_summary="现在先打开文档，写下这篇案例的标题和三条核心观点。",
                companion_strategy_summary="先接住情绪，再把任务缩成一个最小动作；避免高压催促；一旦出现刷短视频逃避，就立刻拉回一个最小动作。",
            ),
            growth=SimpleNamespace(
                intimacy=42,
                affinity=36,
                growth_level=3,
                evolution_stage="bonded",
            ),
        )


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
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="ops-agent",
            actor_key="industry-v1-ops:execution-core",
            actor_fingerprint="fp-ops",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="execution-core",
            display_name="Ops Agent",
            role_name="Operations lead",
        ),
    )
    mailbox_repository = SqliteAgentMailboxRepository(state_store)
    checkpoint_repository = SqliteAgentCheckpointRepository(state_store)
    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
    )

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_FakeIndustryService(),
        actor_mailbox_service=mailbox_service,
        agent_runtime_repository=runtime_repository,
        buddy_projection_service=_FakeBuddyProjectionService(),
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "继续帮我把这一步推进下去")],
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
    assert "# Buddy 对外人格" in prompt_appendix
    assert "伙伴名：小澄" in prompt_appendix
    assert "唯一下一步：现在先打开文档，写下这篇案例的标题和三条核心观点。" in prompt_appendix
    assert "避免高压催促" in prompt_appendix
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
        lambda: "北京时间 2026-04-09 周四 10:00",
        raising=False,
    )

    state_store = SQLiteStateStore(tmp_path / "state-time.sqlite3")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="ops-agent",
            actor_key="industry-v1-ops:execution-core",
            actor_fingerprint="fp-ops",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-v1-ops",
            industry_role_id="execution-core",
            display_name="Ops Agent",
            role_name="Operations lead",
        ),
    )
    mailbox_repository = SqliteAgentMailboxRepository(state_store)
    checkpoint_repository = SqliteAgentCheckpointRepository(state_store)
    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
    )

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_FakeIndustryService(),
        actor_mailbox_service=mailbox_service,
        agent_runtime_repository=runtime_repository,
        buddy_projection_service=_FakeBuddyProjectionService(),
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "今天是周几，接下来等到哪天？")],
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
    assert "北京时间 2026-04-09 周四 10:00" in prompt_appendix
    assert "do not guess" in prompt_appendix.lower()
