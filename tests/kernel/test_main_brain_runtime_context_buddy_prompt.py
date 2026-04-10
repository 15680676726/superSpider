# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import copaw.kernel.query_execution as query_execution_module
import copaw.kernel.query_execution_prompt as query_execution_prompt_module
from copaw.kernel import ActorMailboxService
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
        industry_service=_ContractAwareIndustryService(),
        actor_mailbox_service=mailbox_service,
        agent_runtime_repository=runtime_repository,
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
        "# Buddy",
        "Buddy name: Nova",
        "Service intent: Turn creative ambition into a steady weekly publishing rhythm.",
        "Collaboration role: orchestrator",
        "Autonomy level: guarded-proactive",
        "Report style: decision-first",
        "Confirm before: external spend, publishing under my real name",
        "Collaboration notes: Keep reports short and escalate blockers with one recommendation.",
        "# Execution Core Identity",
        "Operating mode: guarded-collaboration",
        "Delegation rule: Coordinate direction and delegate leaf execution to the right specialist lane.",
        "Direct execution rule: Do not let the execution core swallow browser or document leaf work.",
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
        industry_service=_ContractAwareIndustryService(),
        actor_mailbox_service=mailbox_service,
        agent_runtime_repository=runtime_repository,
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
