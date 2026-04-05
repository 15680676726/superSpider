# -*- coding: utf-8 -*-
from __future__ import annotations

from .shared import *  # noqa: F401,F403


def test_execution_feedback_prompt_lines_include_relation_path_guidance() -> None:
    from copaw.kernel.query_execution_confirmation import execution_feedback_prompt_lines

    lines = execution_feedback_prompt_lines(
        {
            "current_stage": "Resolve approval blocker",
            "dependency_paths": [
                "Refresh approval evidence before drafting the outbound package.",
            ],
            "blocker_paths": [
                "Do not publish while the approval contradiction remains unresolved.",
            ],
            "recovery_paths": [
                "If blocked, rerun approval refresh and verify the cache state.",
            ],
            "contradiction_paths": [
                "Current approval evidence contradicts immediate publish readiness.",
            ],
        },
    )

    prompt_appendix = "\n".join(lines)
    assert "Execution path guidance:" in prompt_appendix
    assert "Resolve these dependencies first:" in prompt_appendix
    assert "Refresh approval evidence before drafting the outbound package." in prompt_appendix
    assert "Known blockers that should stop forward motion:" in prompt_appendix
    assert "Do not publish while the approval contradiction remains unresolved." in prompt_appendix
    assert "Preferred recovery moves when blocked:" in prompt_appendix
    assert "If blocked, rerun approval refresh and verify the cache state." in prompt_appendix
    assert "Contradictions to resolve before claiming success:" in prompt_appendix
    assert "Current approval evidence contradicts immediate publish readiness." in prompt_appendix

def test_query_execution_service_manages_environment_lease_lifecycle(
    tmp_path,
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    session_repository = SessionMountRepository(state_store)
    environment_service = EnvironmentService(
        registry=EnvironmentRegistry(
            repository=EnvironmentRepository(state_store),
            session_repository=session_repository,
        ),
        lease_ttl_seconds=60,
    )
    environment_service.set_session_repository(session_repository)

    heartbeat_calls: list[str] = []
    release_calls: list[str] = []
    original_heartbeat = environment_service.heartbeat_session_lease
    original_release = environment_service.release_session_lease

    def _recording_heartbeat(*args, **kwargs):
        heartbeat_calls.append(args[0])
        return original_heartbeat(*args, **kwargs)

    def _recording_release(*args, **kwargs):
        release_calls.append(args[0])
        return original_release(*args, **kwargs)

    monkeypatch.setattr(environment_service, "heartbeat_session_lease", _recording_heartbeat)
    monkeypatch.setattr(environment_service, "release_session_lease", _recording_release)
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

    session_backend = _FakeSessionBackend()
    service = KernelQueryExecutionService(
        session_backend=session_backend,
        environment_service=environment_service,
    )

    async def _run():
        payload = []
        async for item in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "hello")],
            request=SimpleNamespace(
                session_id="sess-1",
                user_id="user-1",
                channel="console",
            ),
            kernel_task_id="chat:chat-lease-1",
        ):
            payload.append(item)
        return payload

    messages = asyncio.run(_run())

    assert len(messages) == 2
    assert session_backend.loaded == [("sess-1", "user-1")]
    assert session_backend.saved == [("sess-1", "user-1")]
    assert heartbeat_calls == ["session:console:sess-1", "session:console:sess-1"]
    assert release_calls == ["session:console:sess-1"]

    session_mount = environment_service.get_session("session:console:sess-1")
    assert session_mount is not None
    assert session_mount.lease_status == "released"
    assert session_mount.live_handle_ref is None
    assert session_mount.lease_owner == "copaw-agent-runner"


def test_query_execution_service_returns_busy_message_when_actor_runtime_is_already_leased(
    tmp_path,
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    state_store = SQLiteStateStore(tmp_path / "actor-busy-state.sqlite3")
    session_repository = SessionMountRepository(state_store)
    environment_service = EnvironmentService(
        registry=EnvironmentRegistry(
            repository=EnvironmentRepository(state_store),
            session_repository=session_repository,
        ),
        lease_ttl_seconds=60,
    )
    environment_service.set_session_repository(session_repository)
    agent_lease_repository = SqliteAgentLeaseRepository(state_store)
    environment_service.set_agent_lease_repository(agent_lease_repository)
    environment_service.acquire_actor_lease(
        agent_id="copaw-agent-runner",
        owner="copaw-actor-worker",
    )

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

    session_backend = _FakeSessionBackend()
    service = KernelQueryExecutionService(
        session_backend=session_backend,
        environment_service=environment_service,
    )

    async def _run():
        payload = []
        async for item in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "start execution")],
            request=SimpleNamespace(
                session_id="sess-busy",
                user_id="user-busy",
                channel="console",
            ),
            kernel_task_id="chat:actor-busy",
        ):
            payload.append(item)
        return payload

    messages = asyncio.run(_run())

    assert len(messages) == 1
    assert messages[0][1] is True
    assert "执行编排暂时不可用" in messages[0][0].get_text_content()
    assert session_backend.loaded == []
    assert session_backend.saved == []


def test_query_execution_service_heartbeats_leases_during_silent_turn(
    tmp_path,
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    state_store = SQLiteStateStore(tmp_path / "heartbeat-state.sqlite3")
    session_repository = SessionMountRepository(state_store)
    environment_service = EnvironmentService(
        registry=EnvironmentRegistry(
            repository=EnvironmentRepository(state_store),
            session_repository=session_repository,
        ),
        lease_ttl_seconds=30,
    )
    environment_service.set_session_repository(session_repository)
    agent_lease_repository = SqliteAgentLeaseRepository(state_store)
    environment_service.set_agent_lease_repository(agent_lease_repository)

    session_heartbeats: list[str] = []
    actor_heartbeats: list[str] = []
    original_session_heartbeat = environment_service.heartbeat_session_lease
    original_actor_heartbeat = environment_service.heartbeat_actor_lease

    def _record_session_heartbeat(*args, **kwargs):
        session_heartbeats.append(args[0])
        return original_session_heartbeat(*args, **kwargs)

    def _record_actor_heartbeat(*args, **kwargs):
        actor_heartbeats.append(args[0])
        return original_actor_heartbeat(*args, **kwargs)

    monkeypatch.setattr(environment_service, "heartbeat_session_lease", _record_session_heartbeat)
    monkeypatch.setattr(environment_service, "heartbeat_actor_lease", _record_actor_heartbeat)
    monkeypatch.setattr(query_execution_module, "CoPawAgent", _FakeAgent)
    monkeypatch.setattr(
        query_execution_module,
        "stream_printing_messages",
        _slow_stream_printing_messages,
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

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        environment_service=environment_service,
        lease_heartbeat_interval_seconds=0.01,
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "slow heartbeat")],
            request=SimpleNamespace(
                session_id="sess-heartbeat",
                user_id="user-1",
                channel="console",
            ),
            kernel_task_id="chat:slow-heartbeat",
        ):
            pass

    asyncio.run(_run())

    assert session_heartbeats
    assert actor_heartbeats
    assert session_heartbeats[0] == "session:console:sess-heartbeat"
    assert actor_heartbeats[0] == "actor:copaw-agent-runner"


def test_query_execution_service_reuses_resident_agent_for_same_session(
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

    session_backend = _FakeSessionBackend()
    service = KernelQueryExecutionService(
        session_backend=session_backend,
    )

    async def _run_twice():
        for _ in range(2):
            async for _msg, _last in service.execute_stream(
                msgs=[SimpleNamespace(get_text_content=lambda: "hello")],
                request=SimpleNamespace(
                    session_id="resident-sess",
                    user_id="resident-user",
                    channel="console",
                ),
                kernel_task_id="chat:resident-sess",
            ):
                pass

    asyncio.run(_run_twice())

    assert len(_FakeAgent.created) == 1
    assert session_backend.loaded == [("resident-sess", "resident-user")]
    assert session_backend.saved == [
        ("resident-sess", "resident-user"),
        ("resident-sess", "resident-user"),
    ]


def test_query_execution_service_rebuilds_resident_agent_when_actor_identity_changes(
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

    class _MutableProfileService(_FakeAgentProfileService):
        def __init__(self) -> None:
            self.actor_fingerprint = "fp-ops-v1"

        def get_agent(self, agent_id: str):
            profile = super().get_agent(agent_id)
            if profile is None:
                return None
            profile.actor_fingerprint = self.actor_fingerprint
            return profile

    session_backend = _FakeSessionBackend()
    profile_service = _MutableProfileService()
    service = KernelQueryExecutionService(
        session_backend=session_backend,
        agent_profile_service=profile_service,
    )

    async def _run_twice():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "hello")],
            request=SimpleNamespace(
                session_id="resident-sess",
                user_id="ops-agent",
                channel="console",
            ),
            kernel_task_id="chat:resident-sess:1",
        ):
            pass
        profile_service.actor_fingerprint = "fp-ops-v2"
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "hello again")],
            request=SimpleNamespace(
                session_id="resident-sess",
                user_id="ops-agent",
                channel="console",
            ),
            kernel_task_id="chat:resident-sess:2",
        ):
            pass

    asyncio.run(_run_twice())

    assert len(_FakeAgent.created) == 2
    assert session_backend.loaded == [
        ("resident-sess", "ops-agent"),
        ("resident-sess", "ops-agent"),
    ]


def test_query_execution_service_uses_agent_profile_and_capability_graph(
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

    session_backend = _FakeSessionBackend()
    mcp_manager = _FakeMCPManager()
    service = KernelQueryExecutionService(
        session_backend=session_backend,
        mcp_manager=mcp_manager,
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_FakeIndustryService(),
        knowledge_service=_FakeKnowledgeService(),
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "plan the next move")],
            request=SimpleNamespace(
                session_id="goal-1",
                user_id="ops-agent",
                channel="goal",
                industry_label="Ops Industry Team",
                owner_scope="industry-v1-ops-scope",
                session_kind="industry-agent-chat",
            ),
            kernel_task_id="task-1",
        ):
            pass

    asyncio.run(_run())

    assert len(_FakeAgent.created) == 1
    agent = _FakeAgent.created[0]
    assert agent.kwargs["allowed_tool_capability_ids"] == {
        "tool:edit_file",
        "tool:execute_shell_command",
        "tool:get_current_time",
        "tool:read_file",
        "tool:write_file",
    }
    assert agent.kwargs["allowed_skill_names"] == set()
    assert [client.name for client in agent.kwargs["mcp_clients"]] == []
    assert {
        tool_fn.__name__
        for tool_fn in agent.kwargs["extra_tool_functions"]
    } == {
        "discover_capabilities",
        "dispatch_query",
        "delegate_task",
        "apply_role",
    }
    assert "Role: 白泽执行中枢" in agent.kwargs["prompt_appendix"]
    assert "Mission: Turn the ops brief into the next coordinated move." in agent.kwargs[
        "prompt_appendix"
    ]
    assert "Industry team: Ops Industry Team" in agent.kwargs["prompt_appendix"]
    assert "Industry instance id: industry-v1-ops" in agent.kwargs["prompt_appendix"]
    assert "Industry role id: execution-core" in agent.kwargs["prompt_appendix"]
    assert "Owner scope: industry-v1-ops-scope" in agent.kwargs["prompt_appendix"]
    assert "Session kind: industry-agent-chat" in agent.kwargs["prompt_appendix"]
    assert "Current focus: Launch runtime center (goal-1)" in agent.kwargs["prompt_appendix"]
    assert "# Industry Brief" in agent.kwargs["prompt_appendix"]
    assert "# Team Roster" in agent.kwargs["prompt_appendix"]
    assert "# Delegation Policy" in agent.kwargs["prompt_appendix"]
    assert "# Team Operating Model" in agent.kwargs["prompt_appendix"]
    assert "Operating mode: team control core." in agent.kwargs["prompt_appendix"]
    assert "Prefer dispatching, delegating, supervising, and verifying" in agent.kwargs[
        "prompt_appendix"
    ]
    assert "Compare reports before deciding the next move." in agent.kwargs[
        "prompt_appendix"
    ]
    assert "Detect conflicts and holes before closing the loop." in agent.kwargs[
        "prompt_appendix"
    ]
    assert "Surface staffing/routing gaps explicitly" in agent.kwargs["prompt_appendix"]
    assert "Own final operator-facing synthesis before delegating more work." in agent.kwargs[
        "prompt_appendix"
    ]
    assert "Delegation-first policy is active for this turn" in agent.kwargs["prompt_appendix"]
    assert "ops-researcher" in agent.kwargs["prompt_appendix"]
    assert "allowed_capabilities=" in agent.kwargs["prompt_appendix"]
    assert "current_focus=Launch runtime center" in agent.kwargs["prompt_appendix"]
    assert "Target customers: COO leaders, RevOps teams" in agent.kwargs["prompt_appendix"]
    assert "Constraints: No shell access" in agent.kwargs["prompt_appendix"]
    assert "# Retrieved Knowledge" in agent.kwargs["prompt_appendix"]
    assert "Ops SOP: Review evidence before acting." in agent.kwargs["prompt_appendix"]
    assert "# Long-Term Memory" not in agent.kwargs["prompt_appendix"]
    assert (
        "Customer rule: ACME requires execution-core review before outbound changes."
        not in agent.kwargs["prompt_appendix"]
    )
    assert "# Execution Principles" in agent.kwargs["prompt_appendix"]
    assert "Learn first, then act" in agent.kwargs["prompt_appendix"]
    assert "# Role Capability Card" in agent.kwargs["prompt_appendix"]
    assert "Governance rights (2): apply_role, discover_capabilities" in agent.kwargs["prompt_appendix"]
    assert "Mounted capabilities: " in agent.kwargs["prompt_appendix"]
    assert "system:discover_capabilities" in agent.kwargs["prompt_appendix"]
    assert "system:dispatch_query" in agent.kwargs["prompt_appendix"]
    assert "system:dispatch_goal" not in agent.kwargs["prompt_appendix"]
    assert "system:apply_role" in agent.kwargs["prompt_appendix"]
    assert "Capability discovery is mounted" in agent.kwargs["prompt_appendix"]
    assert "Goal dispatch is mounted" not in agent.kwargs["prompt_appendix"]
    assert "Focused sub-query dispatch is mounted" in agent.kwargs["prompt_appendix"]
    assert "Governed role/capability assignment is mounted" in agent.kwargs["prompt_appendix"]
    assert "Do not describe this runtime as a generic sandbox" in agent.kwargs["prompt_appendix"]
    assert "The main-brain control thread cannot use direct tools." not in agent.kwargs[
        "prompt_appendix"
    ]
    assert mcp_manager.requested_keys == []
    assert mcp_manager.get_clients_calls == 0


def test_query_execution_service_passes_typed_capability_layers_into_agent_and_prompt(
    tmp_path,
    monkeypatch,
) -> None:
    class _FakeAgentProfileServiceWithGovernance(_FakeAgentProfileService):
        def get_prompt_capability_projection(self, agent_id: str, *, item_limit: int = 4):
            _ = item_limit
            assert agent_id == "ops-agent"
            return {
                "agent_id": agent_id,
                "default_mode": "governed",
                "effective_count": 3,
                "pending_decision_count": 2,
                "drift_detected": True,
                "bucket_counts": {
                    "system_dispatch": 1,
                    "system_governance": 1,
                    "tools": 1,
                    "skills": 0,
                    "mcp": 0,
                    "other": 0,
                },
                "system_dispatch": [{"id": "system:dispatch_query", "label": "dispatch_query"}],
                "system_governance": [{"id": "system:apply_role", "label": "apply_role"}],
                "tools": [{"id": "tool:read_file", "label": "read_file"}],
                "skills": [],
                "mcp": [],
                "other": [],
                "risk_levels": {"auto": 1, "guarded": 2},
                "environment_requirements": ["workspace"],
                "evidence_contract": ["file-read"],
            }

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

    state_store = SQLiteStateStore(tmp_path / "query-runtime-capability-layers.sqlite3")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="ops-agent",
            actor_key="industry:ops:execution-core",
            actor_fingerprint="fp-ops-v1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            metadata={
                "capability_layers": {
                    "schema_version": "industry-seat-capability-layers-v1",
                    "role_prototype_capability_ids": [
                        "tool:read_file",
                        "system:dispatch_query",
                    ],
                    "seat_instance_capability_ids": ["tool:write_file"],
                    "cycle_delta_capability_ids": ["mcp:browser"],
                    "session_overlay_capability_ids": ["mcp:other"],
                },
            },
        ),
    )

    session_backend = _FakeSessionBackend()
    mcp_manager = _FakeMCPManager()
    service = KernelQueryExecutionService(
        session_backend=session_backend,
        mcp_manager=mcp_manager,
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileServiceWithGovernance(),
        industry_service=_FakeIndustryService(),
        knowledge_service=_FakeKnowledgeService(),
        agent_runtime_repository=runtime_repository,
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "plan the next move")],
            request=SimpleNamespace(
                session_id="goal-capability-layers",
                user_id="ops-agent",
                channel="goal",
                industry_label="Ops Industry Team",
                owner_scope="industry-v1-ops-scope",
                session_kind="industry-agent-chat",
            ),
            kernel_task_id="task-capability-layers",
        ):
            pass

    asyncio.run(_run())

    assert len(_FakeAgent.created) == 1
    agent = _FakeAgent.created[0]
    assert agent.kwargs["capability_layers"].role_prototype_capability_ids == [
        "tool:read_file",
        "system:dispatch_query",
    ]
    assert agent.kwargs["capability_layers"].seat_instance_capability_ids == [
        "tool:write_file",
    ]
    assert agent.kwargs["capability_layers"].cycle_delta_capability_ids == [
        "mcp:browser",
    ]
    assert agent.kwargs["capability_layers"].session_overlay_capability_ids == [
        "mcp:other",
    ]
    assert "Role prototype surfaces:" in agent.kwargs["prompt_appendix"]
    assert "Seat instance surfaces:" in agent.kwargs["prompt_appendix"]
    assert "Cycle delta surfaces:" in agent.kwargs["prompt_appendix"]
    assert "Session overlay surfaces:" in agent.kwargs["prompt_appendix"]
    assert "pending_governance=2" in agent.kwargs["prompt_appendix"]
    assert "drift=yes" in agent.kwargs["prompt_appendix"]


def test_query_execution_service_isolates_long_term_memory_for_task_threads(
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

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_FakeIndustryService(),
        knowledge_service=_FakeKnowledgeService(),
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "plan the next move")],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="ops-agent",
                channel="console",
                agent_id="ops-agent",
                session_kind="industry-control-thread",
                task_id="task-123",
                control_thread_id="industry-chat:industry-v1-ops:execution-core",
            ),
            kernel_task_id="task-123",
        ):
            pass

    asyncio.run(_run())

    assert len(_FakeAgent.created) == 1
    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "# Long-Term Memory" in prompt_appendix
    assert "Task thread rule: Only use this task thread's memory when continuing the task." in prompt_appendix
    assert "Customer rule: ACME requires execution-core review before outbound changes." not in prompt_appendix


def test_query_execution_service_injects_execution_core_industry_identity(
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

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=SimpleNamespace(
            get_agent=lambda agent_id: (
                SimpleNamespace(
                    agent_id="copaw-agent-runner",
                    name="白泽执行中枢",
                    role_name="团队执行中枢",
                    role_summary="Generic execution core profile.",
                    mission="Generic mission.",
                    current_focus_kind="goal",
                    current_focus="",
                    capabilities=["tool:browser_use", "system:dispatch_query"],
                )
                if agent_id == "copaw-agent-runner"
                else None
            ),
        ),
        industry_service=_FakeIndustryService(),
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "plan the next move")],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                industry_label="Ops Industry Team",
                session_kind="industry-agent-chat",
            ),
            kernel_task_id="task-identity",
        ):
            pass

    asyncio.run(_run())

    assert len(_FakeAgent.created) == 1
    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "Role: 白泽执行中枢" in prompt_appendix
    assert "Role summary: Operate as the execution brain for this ops team." in prompt_appendix
    assert "Mission: Turn the ops brief into the next coordinated move." in prompt_appendix
    assert "Current focus:" not in prompt_appendix
    assert "# Execution Core Identity" in prompt_appendix
    assert "# Team Operating Model" in prompt_appendix
    assert "Identity label: Ops Industry Team / 白泽执行中枢" in prompt_appendix
    assert "Thinking axis: Industry focus: Operations consulting" in prompt_appendix
    assert "Thinking axis: Channel lens: LinkedIn, Email" in prompt_appendix


def test_query_execution_service_keeps_execution_core_identity_for_task_chat_session(
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    strategy_memory_service = _FallbackStrategyMemoryService()
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

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=SimpleNamespace(
            get_agent=lambda agent_id: (
                SimpleNamespace(
                    agent_id="copaw-agent-runner",
                    name="Execution Core",
                    role_name="Execution Core",
                    role_summary="Generic execution core profile.",
                    mission="Generic mission.",
                    current_focus_kind="goal",
                    current_focus="Generic current goal",
                    capabilities=["tool:browser_use", "system:dispatch_query"],
                )
                if agent_id == "copaw-agent-runner"
                else None
            ),
        ),
        industry_service=_FakeIndustryService(),
        strategy_memory_service=strategy_memory_service,
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "plan the next move")],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                agent_id="copaw-agent-runner",
                channel="console",
                task_id="task-identity",
                session_kind="industry-control-thread",
                control_thread_id="industry-chat:industry-v1-ops:execution-core",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                industry_label="Ops Industry Team",
            ),
            kernel_task_id="task-identity",
        ):
            pass

    asyncio.run(_run())

    assert strategy_memory_service.calls == [
        ("industry", "industry-v1-ops", "copaw-agent-runner"),
    ]
    assert len(_FakeAgent.created) == 1
    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "Session kind: industry-control-thread" in prompt_appendix
    assert "Industry instance id: industry-v1-ops" in prompt_appendix
    assert "Industry role id: execution-core" in prompt_appendix
    assert "# Execution Core Identity" in prompt_appendix
    assert "# Strategy Memory" in prompt_appendix
    assert "Identity label: Ops Industry Team /" in prompt_appendix
    assert (
        "Mission: Keep the runtime center reliable while delegating the next concrete move."
        in prompt_appendix
    )


def test_query_execution_service_resolves_strategy_memory_via_shared_fallback(
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    strategy_memory_service = _FallbackStrategyMemoryService()
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

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_FakeIndustryService(),
        strategy_memory_service=strategy_memory_service,
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "plan the next move")],
            request=SimpleNamespace(
                session_id="industry-chat-1",
                user_id="default",
                agent_id="ops-agent",
                channel="console",
                industry_instance_id="industry-v1-ops",
                session_kind="industry-agent-chat",
            ),
            kernel_task_id="task-strategy",
        ):
            pass

    asyncio.run(_run())

    assert strategy_memory_service.calls == [
        ("industry", "industry-v1-ops", "ops-agent"),
        ("industry", "industry-v1-ops", "copaw-agent-runner"),
    ]
    assert len(_FakeAgent.created) == 1
    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert (
        "Mission: Keep the runtime center reliable while delegating the next concrete move."
        in prompt_appendix
    )
    assert "# Strategy Memory" in prompt_appendix
    assert "North star: Build a predictable operator pipeline" in prompt_appendix
    assert "Priority: Keep the runtime center stable" in prompt_appendix
    assert (
        "Execution constraint: Collect evidence before mutating operator state"
        in prompt_appendix
    )


def test_query_execution_service_applies_chat_writeback_before_prompt_build(
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    strategy_memory_service = _MutableStrategyMemoryService()
    industry_service = _ChatWritebackIndustryService(strategy_memory_service)
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

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=industry_service,
        strategy_memory_service=strategy_memory_service,
    )
    text = "改成先做现场验证再做规模复制"

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: text)],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                task_mode="team-orchestration",
                session_kind="industry-agent-chat",
                _copaw_main_brain_intake_contract=_make_attached_main_brain_intake_contract(
                    text=text,
                ),
            ),
            kernel_task_id="chat-writeback",
        ):
            pass

    asyncio.run(_run())

    assert industry_service.calls == [
        (
            "industry-v1-ops",
            "改成先做现场验证再做规模复制",
            "ops-agent",
        )
    ]
    assert industry_service.received_writeback_fingerprints
    assert industry_service.received_writeback_fingerprints[0]
    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "# Formal Writeback" in prompt_appendix
    assert "Must include: 改成先做现场验证再做规模复制" in prompt_appendix
    assert "Priority: 先做现场验证" in prompt_appendix
    assert "Priority: 再做规模复制" in prompt_appendix
    assert "Newly recorded goal: 现场验证主线" in prompt_appendix


def test_query_execution_service_applies_model_approved_writeback_when_rules_miss(
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    strategy_memory_service = _MutableStrategyMemoryService()
    industry_service = _ChatWritebackIndustryService(strategy_memory_service)
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
    async def _model_approved_writeback_async(**kwargs):
        return _make_fake_chat_writeback_model_decision(
            intent_kind="chat",
            intent_confidence=0.88,
            intent_signals=["durable-default"],
            should_writeback=True,
            approved_targets=["backlog"],
            operator_requirements=[str(kwargs.get("text") or "")],
            goal_title="团队默认做法",
            goal_summary=str(kwargs.get("text") or ""),
            goal_plan_steps=[
                "Record the default.",
                "Assign the owner.",
                "Review evidence before promoting it.",
            ],
        )

    def _model_approved_writeback_sync(**kwargs):
        return _make_fake_chat_writeback_model_decision(
            intent_kind="chat",
            intent_confidence=0.88,
            intent_signals=["durable-default"],
            should_writeback=True,
            approved_targets=["backlog"],
            operator_requirements=[str(kwargs.get("text") or "")],
            goal_title="团队默认做法",
            goal_summary=str(kwargs.get("text") or ""),
            goal_plan_steps=[
                "Record the default.",
                "Assign the owner.",
                "Review evidence before promoting it.",
            ],
        )

    monkeypatch.setattr(
        main_brain_intake_module,
        "_resolve_chat_writeback_model_decision",
        _model_approved_writeback_async,
    )

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=industry_service,
        strategy_memory_service=strategy_memory_service,
    )
    text = "persist this instruction as the team baseline default"

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[
                SimpleNamespace(
                    get_text_content=lambda: text,
                ),
            ],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                task_mode="team-orchestration",
                session_kind="industry-agent-chat",
                _copaw_main_brain_intake_contract=_make_attached_main_brain_intake_contract(
                    text=text,
                    decision=_model_approved_writeback_sync(text=text),
                ),
            ),
            kernel_task_id="chat-model-writeback",
        ):
            pass

    asyncio.run(_run())

    assert industry_service.calls == [
        (
            "industry-v1-ops",
            "persist this instruction as the team baseline default",
            "ops-agent",
        )
    ]
    assert industry_service.received_writeback_fingerprints
    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "# Formal Writeback" in prompt_appendix
    assert "Must include: persist this instruction as the team baseline default" in prompt_appendix


def test_query_execution_service_runs_writeback_before_kickoff_when_both_apply(
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    strategy_memory_service = _MutableStrategyMemoryService()
    industry_service = _KickoffAwareIndustryService(strategy_memory_service)
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

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=industry_service,
        strategy_memory_service=strategy_memory_service,
    )
    text = "confirm and continue, must include a specialist follow-up loop and review it weekly"

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[
                SimpleNamespace(
                    get_text_content=lambda: text,
                ),
            ],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                task_mode="team-orchestration",
                session_kind="industry-agent-chat",
                _copaw_main_brain_intake_contract=_make_attached_main_brain_intake_contract(
                    text=text,
                ),
            ),
            kernel_task_id="chat-writeback-kickoff",
        ):
            pass

    asyncio.run(_run())

    assert industry_service.call_order == ["writeback", "kickoff"]
    assert industry_service.writeback_calls == [
        (
            "industry-v1-ops",
            "confirm and continue, must include a specialist follow-up loop and review it weekly",
            "ops-agent",
        ),
    ]
    assert industry_service.received_writeback_fingerprints
    assert industry_service.received_writeback_fingerprints[0]
    assert industry_service.kickoff_calls == [
        (
            "industry-v1-ops",
            "confirm and continue, must include a specialist follow-up loop and review it weekly",
            "ops-agent",
            [
                "verify on site first",
                "scale after verification",
                "Keep the runtime center stable",
            ],
        ),
    ]
    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "# Formal Writeback" in prompt_appendix
    assert "# Initial Kickoff" in prompt_appendix


def test_query_execution_service_does_not_kickoff_on_writeback_only_chat(
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    strategy_memory_service = _MutableStrategyMemoryService()
    industry_service = _KickoffAwareIndustryService(strategy_memory_service)
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

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=industry_service,
        strategy_memory_service=strategy_memory_service,
    )
    text = "must include a specialist follow-up loop and review it weekly"

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[
                SimpleNamespace(
                    get_text_content=lambda: text,
                ),
            ],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                task_mode="team-orchestration",
                session_kind="industry-agent-chat",
                _copaw_main_brain_intake_contract=_make_attached_main_brain_intake_contract(
                    text=text,
                ),
            ),
            kernel_task_id="chat-writeback-only",
        ):
            pass

    asyncio.run(_run())

    assert industry_service.call_order == ["writeback"]
    assert industry_service.received_writeback_fingerprints
    assert industry_service.received_writeback_fingerprints[0]
    assert industry_service.kickoff_calls == []
    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "# Formal Writeback" in prompt_appendix
    assert "# Initial Kickoff" not in prompt_appendix


def test_query_execution_service_keeps_discussion_cadence_in_control_without_writeback(
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    strategy_memory_service = _MutableStrategyMemoryService()
    industry_service = _KickoffAwareIndustryService(strategy_memory_service)
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

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=industry_service,
        strategy_memory_service=strategy_memory_service,
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[
                SimpleNamespace(
                    get_text_content=lambda: (
                        "Could we add a daily cadence? I just want to discuss it first."
                    ),
                ),
            ],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                task_mode="team-orchestration",
                session_kind="industry-agent-chat",
            ),
            kernel_task_id="chat-discussion-cadence",
        ):
            pass

    asyncio.run(_run())

    assert industry_service.call_order == []
    assert industry_service.received_writeback_fingerprints == []
    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "# Formal Writeback" not in prompt_appendix
    assert "# Initial Kickoff" not in prompt_appendix


def test_query_execution_service_limits_strategy_memory_surface_in_prompt(
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    strategy_memory_service = _MutableStrategyMemoryService()
    strategy_memory_service.payload.update(
        {
            "priority_order": ["PRIORITY-01", "PRIORITY-02", "PRIORITY-03", "PRIORITY-04", "PRIORITY-05"],
            "delegation_policy": ["DELEGATE-01", "DELEGATE-02", "DELEGATE-03", "DELEGATE-04"],
            "direct_execution_policy": ["DIRECT-01", "DIRECT-02", "DIRECT-03"],
            "execution_constraints": [
                "CONSTRAINT-01",
                "CONSTRAINT-02",
                "CONSTRAINT-03",
                "CONSTRAINT-04",
                "CONSTRAINT-05",
            ],
            "evidence_requirements": [
                "EVIDENCE-01",
                "EVIDENCE-02",
                "EVIDENCE-03",
                "EVIDENCE-04",
                "EVIDENCE-05",
                "EVIDENCE-06",
                "EVIDENCE-07",
            ],
            "active_goal_titles": ["GOAL-01", "GOAL-02", "GOAL-03", "GOAL-04", "GOAL-05"],
            "metadata": {
                "experience_mode": "operator-guided",
                "experience_notes": "PLAYBOOK-01",
                "operator_requirements": [
                    "REQUIREMENT-01",
                    "REQUIREMENT-02",
                    "REQUIREMENT-03",
                    "REQUIREMENT-04",
                    "REQUIREMENT-05",
                ],
            },
        },
    )
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

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_FakeIndustryService(),
        strategy_memory_service=strategy_memory_service,
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "plan the next move")],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                agent_id="copaw-agent-runner",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                session_kind="industry-agent-chat",
            ),
            kernel_task_id="task-strategy-limits",
        ):
            pass

    asyncio.run(_run())

    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "- Task mode: team orchestration" in prompt_appendix
    assert "# Role Contract" in prompt_appendix
    assert "# Task Mode" in prompt_appendix
    assert "# Evidence Contract" in prompt_appendix
    assert "Operator playbook: PLAYBOOK-01" in prompt_appendix
    assert "Expected evidence: EVIDENCE-01, EVIDENCE-02, EVIDENCE-03, EVIDENCE-04, EVIDENCE-05, EVIDENCE-06" in prompt_appendix
    for marker in ("REQUIREMENT-01", "REQUIREMENT-02", "REQUIREMENT-03", "REQUIREMENT-04"):
        assert f"Must include: {marker}" in prompt_appendix
    for marker in ("GOAL-01", "GOAL-02", "GOAL-03", "GOAL-04"):
        assert f"Active goal: {marker}" in prompt_appendix
    for marker in ("PRIORITY-01", "PRIORITY-02", "PRIORITY-03", "PRIORITY-04"):
        assert f"Priority: {marker}" in prompt_appendix
    for marker in ("DELEGATE-01", "DELEGATE-02", "DELEGATE-03"):
        assert f"Delegation rule: {marker}" in prompt_appendix
    for marker in ("DIRECT-01", "DIRECT-02"):
        assert f"Direct execution rule: {marker}" in prompt_appendix
    for marker in ("CONSTRAINT-01", "CONSTRAINT-02", "CONSTRAINT-03", "CONSTRAINT-04"):
        assert f"Execution constraint: {marker}" in prompt_appendix
    for marker in (
        "REQUIREMENT-05",
        "GOAL-05",
        "PRIORITY-05",
        "DELEGATE-04",
        "DIRECT-03",
        "CONSTRAINT-05",
        "EVIDENCE-07",
    ):
        assert marker not in prompt_appendix


def test_query_execution_service_injects_recent_execution_feedback_into_prompt(
    monkeypatch,
) -> None:
    class _FeedbackTaskRepository:
        def __init__(self) -> None:
            self._tasks = [
                SimpleNamespace(
                    id="task-1",
                    goal_id="goal-1",
                    title="Prepare evidence brief",
                    status="running",
                    task_type="dispatch-query",
                    updated_at="2026-03-17T08:30:00+00:00",
                ),
                SimpleNamespace(
                    id="task-2",
                    goal_id="goal-1",
                    title="Inspect feedback loop",
                    status="running",
                    task_type="dispatch-query",
                    updated_at="2026-03-17T09:15:00+00:00",
                ),
            ]

        def get_task(self, task_id: str):
            for task in self._tasks:
                if task.id == task_id:
                    return task
            return None

        def list_tasks(
            self,
            *,
            goal_id: str | None = None,
            parent_task_id: str | None = None,
            limit: int | None = None,
            **_: object,
        ):
            items = list(self._tasks)
            if goal_id is not None:
                items = [task for task in items if getattr(task, "goal_id", None) == goal_id]
            if parent_task_id is not None:
                items = [
                    task for task in items if getattr(task, "parent_task_id", None) == parent_task_id
                ]
            if isinstance(limit, int):
                items = items[:limit]
            return items

    class _FeedbackTaskRuntimeRepository:
        def get_runtime(self, task_id: str):
            if task_id != "task-2":
                return None
            return SimpleNamespace(
                task_id="task-2",
                current_phase="verify-brief",
                updated_at="2026-03-17T09:30:00+00:00",
            )

    class _FeedbackEvidenceLedger:
        def list_recent(self, *, limit: int = 80):
            _ = limit
            return [
                SimpleNamespace(
                    id="evidence-fail-1",
                    task_id="task-2",
                    capability_ref="browser_use",
                    environment_ref="browser:storefront",
                    risk_level="guarded",
                    action_summary="Retry storefront login",
                    result_summary="Login failed due to stale OTP.",
                    created_at="2026-03-17T09:29:00+00:00",
                ),
                SimpleNamespace(
                    id="evidence-fail-2",
                    task_id="task-2",
                    capability_ref="browser_use",
                    environment_ref="browser:storefront",
                    risk_level="guarded",
                    action_summary="Retry storefront login",
                    result_summary="Login failed again due to stale OTP.",
                    created_at="2026-03-17T09:28:00+00:00",
                ),
                SimpleNamespace(
                    id="evidence-ok-1",
                    task_id="task-1",
                    capability_ref="read_file",
                    environment_ref="workspace:ops",
                    risk_level="auto",
                    action_summary="Review previous execution brief",
                    result_summary="Recovered the next owner and blocker summary.",
                    created_at="2026-03-17T09:10:00+00:00",
                ),
            ]

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

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_FakeIndustryService(),
        task_repository=_FeedbackTaskRepository(),
        task_runtime_repository=_FeedbackTaskRuntimeRepository(),
        evidence_ledger=_FeedbackEvidenceLedger(),
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "plan the next move")],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                session_kind="industry-agent-chat",
            ),
            kernel_task_id="task-execution-feedback",
        ):
            pass

    asyncio.run(_run())

    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "# Execution Feedback" in prompt_appendix
    assert "Current execution stage to continue from:" in prompt_appendix
    assert "Inspect feedback loop [verify-brief]" in prompt_appendix
    assert "Execution knowledge graph anchors:" in prompt_appendix
    assert "Capability refs: browser_use, read_file" in prompt_appendix
    assert "Environment refs: browser:storefront, workspace:ops" in prompt_appendix
    assert "Risk levels seen: guarded, auto" in prompt_appendix
    assert "Recent failures to avoid repeating:" in prompt_appendix
    assert "Retry storefront login" in prompt_appendix
    assert "Recently effective moves to reuse:" in prompt_appendix
    assert "Review previous execution brief" in prompt_appendix
    assert "Do not repeat these patterns:" in prompt_appendix
    assert "failed 2 times" in prompt_appendix


def test_query_execution_service_does_not_use_request_goal_id_as_focus_truth_for_feedback(
    monkeypatch,
) -> None:
    class _LegacyGoalOnlyAgentProfileService:
        def get_agent(self, agent_id: str):
            if agent_id != "ops-agent":
                return None
            return SimpleNamespace(
                agent_id="ops-agent",
                actor_key="industry:ops:execution-core",
                actor_fingerprint="fp-ops-v1",
                name="Ops Agent",
                role_name="Operations lead",
                role_summary="Owns runtime closeout.",
                mission="Turn the industry brief into an executable operating loop.",
                current_focus_kind=None,
                current_focus_id=None,
                current_focus="",
                current_task_id=None,
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
            )

        def list_agents(self):
            return [self.get_agent("ops-agent")]

    class _FeedbackTaskRepository:
        def __init__(self) -> None:
            self._tasks = [
                SimpleNamespace(
                    id="task-legacy-1",
                    goal_id="goal-legacy-only",
                    title="Inspect legacy goal feedback",
                    status="running",
                    task_type="dispatch-query",
                    updated_at="2026-03-17T09:15:00+00:00",
                ),
            ]

        def get_task(self, task_id: str):
            for task in self._tasks:
                if task.id == task_id:
                    return task
            return None

        def list_tasks(
            self,
            *,
            goal_id: str | None = None,
            parent_task_id: str | None = None,
            limit: int | None = None,
            **_: object,
        ):
            items = list(self._tasks)
            if goal_id is not None:
                items = [task for task in items if getattr(task, "goal_id", None) == goal_id]
            if parent_task_id is not None:
                items = [
                    task for task in items if getattr(task, "parent_task_id", None) == parent_task_id
                ]
            if isinstance(limit, int):
                items = items[:limit]
            return items

    class _FeedbackTaskRuntimeRepository:
        def get_runtime(self, task_id: str):
            if task_id != "task-legacy-1":
                return None
            return SimpleNamespace(
                task_id="task-legacy-1",
                current_phase="legacy-goal-phase",
                updated_at="2026-03-17T09:30:00+00:00",
            )

    class _FeedbackEvidenceLedger:
        def list_recent(self, *, limit: int = 80):
            _ = limit
            return [
                SimpleNamespace(
                    id="evidence-legacy-1",
                    task_id="task-legacy-1",
                    capability_ref="read_file",
                    action_summary="Review legacy goal brief",
                    result_summary="Recovered a stale goal-linked summary.",
                    created_at="2026-03-17T09:10:00+00:00",
                ),
            ]

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

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_LegacyGoalOnlyAgentProfileService(),
        industry_service=_FakeIndustryService(),
        task_repository=_FeedbackTaskRepository(),
        task_runtime_repository=_FeedbackTaskRuntimeRepository(),
        evidence_ledger=_FeedbackEvidenceLedger(),
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "plan the next move")],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                session_kind="industry-agent-chat",
                goal_id="goal-legacy-only",
            ),
            kernel_task_id="task-legacy-goal-feedback",
        ):
            pass

    asyncio.run(_run())

    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "Current focus:" not in prompt_appendix
    assert "# Execution Feedback" not in prompt_appendix
    assert "Inspect legacy goal feedback" not in prompt_appendix


def test_query_execution_service_kicks_off_pending_industry_execution_from_chat(
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    industry_service = _KickoffIndustryService()
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

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=industry_service,
    )
    text = "开始执行默认计划"

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: text)],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                session_kind="industry-agent-chat",
                _copaw_main_brain_intake_contract=_make_attached_main_brain_intake_contract(
                    text=text,
                ),
            ),
            kernel_task_id="chat-kickoff",
        ):
            pass

    asyncio.run(_run())

    assert industry_service.calls == [
        (
            "industry-v1-ops",
            "开始执行默认计划",
            "ops-agent",
        )
    ]
    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "# Initial Kickoff" in prompt_appendix
    assert "Started default goal: 默认首轮验证" in prompt_appendix
    assert "Resumed recurring loop: 默认巡检计划" in prompt_appendix


