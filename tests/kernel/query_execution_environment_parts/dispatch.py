# -*- coding: utf-8 -*-
from __future__ import annotations

from .shared import *  # noqa: F401,F403


def test_query_execution_service_resolves_agent_from_request_agent_id_and_industry_context(
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
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "hello manager")],
            request=SimpleNamespace(
                session_id="industry-chat-1",
                user_id="default",
                agent_id="ops-agent",
                channel="console",
                industry_instance_id="industry-v1-ops",
                session_kind="industry-agent-chat",
            ),
            kernel_task_id="task-2",
        ):
            pass

    asyncio.run(_run())

    assert len(_FakeAgent.created) == 1
    agent = _FakeAgent.created[0]
    assert "Active agent id: ops-agent" in agent.kwargs["prompt_appendix"]
    assert agent.kwargs["allowed_tool_capability_ids"] == {
        "tool:edit_file",
        "tool:execute_shell_command",
        "tool:get_current_time",
        "tool:read_file",
        "tool:write_file",
    }
    assert {
        tool_fn.__name__
        for tool_fn in agent.kwargs["extra_tool_functions"]
    } == {
        "discover_capabilities",
        "dispatch_query",
        "delegate_task",
        "apply_role",
    }


def test_query_execution_service_system_dispatch_tools_execute_via_kernel_dispatcher() -> None:
    capability_service = _FakeCapabilityService()
    kernel_dispatcher = _FakeKernelDispatcher()
    agent_profile_service = _FakeAgentProfileService()
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=capability_service,
        kernel_dispatcher=kernel_dispatcher,
        agent_profile_service=agent_profile_service,
        industry_service=_FakeIndustryService(),
    )
    agent_profile = agent_profile_service.get_agent("ops-agent")
    request = SimpleNamespace(
        session_id="industry-chat-1",
        user_id="ops-agent",
        channel="industry",
        owner_scope="industry-v1-ops-scope",
        industry_instance_id="industry-v1-ops",
        industry_role_id="execution-core",
        session_kind="industry-agent-chat",
        entry_source="agent-workbench",
    )

    tool_functions = service._build_system_tool_functions(
        request=request,
        owner_agent_id="ops-agent",
        agent_profile=agent_profile,
        system_capability_ids={
            "system:apply_role",
            "system:discover_capabilities",
            "system:dispatch_query",
            "system:delegate_task",
        },
        kernel_task_id="task-1",
    )
    tools_by_name = {
        tool_fn.__name__: tool_fn
        for tool_fn in tool_functions
    }

    dispatch_query_result = asyncio.run(
        tools_by_name["dispatch_query"](
            "Investigate the latest pipeline blockers and report back.",
            target_role_id="researcher",
        ),
    )
    discover_capabilities_result = asyncio.run(
        tools_by_name["discover_capabilities"](
            query_text="crm follow-up automation",
            providers=["remote"],
        ),
    )
    apply_role_result = asyncio.run(
        tools_by_name["apply_role"](
            target_role_name="Ops Researcher",
            capabilities=["skill:test-skill", "mcp:browser"],
            capability_assignment_mode="merge",
        ),
    )
    delegate_task_result = asyncio.run(
        tools_by_name["delegate_task"](
            "Review the operator handoff notes and summarize blockers.",
            target_role_name="Ops Researcher",
        ),
    )

    assert isinstance(dispatch_query_result, ToolResponse)
    assert isinstance(discover_capabilities_result, ToolResponse)
    assert isinstance(apply_role_result, ToolResponse)
    assert isinstance(delegate_task_result, ToolResponse)

    dispatch_query_payload = query_execution_module._structured_tool_payload(
        dispatch_query_result,
        default_error="dispatch_query test payload missing",
    )
    discover_capabilities_payload = query_execution_module._structured_tool_payload(
        discover_capabilities_result,
        default_error="discover_capabilities test payload missing",
    )
    apply_role_payload = query_execution_module._structured_tool_payload(
        apply_role_result,
        default_error="apply_role test payload missing",
    )
    delegate_task_payload = query_execution_module._structured_tool_payload(
        delegate_task_result,
        default_error="delegate_task test payload missing",
    )

    assert dispatch_query_payload["success"] is True
    assert discover_capabilities_payload["success"] is True
    assert apply_role_payload["success"] is True
    assert "goal_count" not in apply_role_payload
    assert delegate_task_payload["success"] is True
    assert [task.capability_ref for task in kernel_dispatcher.submitted] == [
        "system:dispatch_query",
        "system:discover_capabilities",
        "system:apply_role",
        "system:delegate_task",
    ]
    assert len(kernel_dispatcher.executed) == 4
    dispatch_query_task = kernel_dispatcher.submitted[0]
    assert dispatch_query_task.owner_agent_id == "ops-agent"
    assert dispatch_query_task.payload["request"]["agent_id"] == "ops-researcher"
    assert dispatch_query_task.payload["request"]["industry_instance_id"] == "industry-v1-ops"
    assert dispatch_query_task.payload["request"]["industry_role_id"] == "researcher"
    assert dispatch_query_task.payload["mode"] == "final"
    discover_capabilities_task = kernel_dispatcher.submitted[1]
    assert discover_capabilities_task.payload["queries"] == ["crm follow-up automation"]
    assert discover_capabilities_task.payload["providers"] == ["remote"]
    apply_role_task = kernel_dispatcher.submitted[2]
    assert apply_role_task.payload["agent_id"] == "ops-researcher"
    assert apply_role_task.payload["capabilities"] == ["skill:test-skill", "mcp:browser"]
    assert apply_role_task.payload["capability_assignment_mode"] == "merge"
    delegate_task = kernel_dispatcher.submitted[3]
    assert delegate_task.payload["parent_task_id"] == "task-1"
    assert delegate_task.payload["owner_agent_id"] == "ops-researcher"


def test_query_execution_service_delegation_first_guard_blocks_direct_work_until_claim() -> None:
    kernel_dispatcher = _FakeKernelDispatcher()
    capability_service = _FakeCapabilityService()
    agent_profile_service = _FakeAgentProfileService()
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=capability_service,
        kernel_dispatcher=kernel_dispatcher,
        agent_profile_service=agent_profile_service,
        industry_service=_FakeIndustryService(),
    )
    agent_profile = agent_profile_service.get_agent("ops-agent")
    request = SimpleNamespace(
        session_id="industry-chat-1",
        user_id="ops-agent",
        channel="industry",
        owner_scope="industry-v1-ops-scope",
        industry_instance_id="industry-v1-ops",
        industry_role_id="execution-core",
        session_kind="industry-agent-chat",
        entry_source="agent-workbench",
    )
    delegation_guard = service._resolve_delegation_first_guard(
        request=request,
        owner_agent_id="ops-agent",
        agent_profile=agent_profile,
        system_capability_ids={
            "system:dispatch_query",
            "system:delegate_task",
        },
    )

    assert delegation_guard is not None
    assert delegation_guard.locked is True
    assert delegation_guard.teammates[0]["agent_id"] == "ops-researcher"

    tool_functions = service._build_system_tool_functions(
        request=request,
        owner_agent_id="ops-agent",
        agent_profile=agent_profile,
        system_capability_ids={
            "system:dispatch_query",
            "system:delegate_task",
        },
        kernel_task_id="task-1",
        delegation_guard=delegation_guard,
    )
    tools_by_name = {
        tool_fn.__name__: tool_fn
        for tool_fn in tool_functions
    }

    blocked_result = asyncio.run(
        tools_by_name["delegate_task"](
            "Review the operator handoff notes and summarize blockers.",
        ),
    )
    blocked_payload = query_execution_module._structured_tool_payload(
        blocked_result,
        default_error="delegation guard payload missing",
    )
    assert blocked_payload["success"] is False
    assert blocked_payload["error_code"] == "delegation_target_required"
    assert "claim_direct_execution" not in tools_by_name

    self_target_result = asyncio.run(
        tools_by_name["dispatch_query"](
            "Summarize the current state.",
            target_agent_id="ops-agent",
        ),
    )
    self_target_payload = query_execution_module._structured_tool_payload(
        self_target_result,
        default_error="dispatch_query payload missing",
    )
    assert self_target_payload["success"] is False
    assert self_target_payload["error_code"] == "delegation_self_target_blocked"
    assert delegation_guard.locked is True

    preflight = service._build_tool_preflight(delegation_guard=delegation_guard)
    assert preflight("execute_shell_command") is None


def test_query_execution_service_rejects_unbound_frontdoor_chat(monkeypatch) -> None:
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
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "hello")],
            request=SimpleNamespace(
                session_id="console-chat-1",
                user_id="default",
                channel="console",
                entry_source="chat",
            ),
            kernel_task_id="task-3",
        ):
            pass

    with pytest.raises(ValueError, match="尚未绑定真实的行业/智能体运行主体"):
        asyncio.run(_run())


def test_query_execution_service_records_resume_checkpoints_and_segment_context(
    monkeypatch,
    tmp_path,
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

    store = SQLiteStateStore(tmp_path / "state.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(store)
    runtime_repository = SqliteAgentRuntimeRepository(store)
    mailbox_repository = SqliteAgentMailboxRepository(store)
    checkpoint_repository = SqliteAgentCheckpointRepository(store)
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
    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
    )
    dispatcher = KernelDispatcher(
        task_store=KernelTaskStore(
            task_repository=task_repository,
            task_runtime_repository=task_runtime_repository,
            runtime_frame_repository=runtime_frame_repository,
        ),
    )
    dispatcher.submit(
        KernelTask(
            id="task-segmented",
            title="Segmented query task",
            capability_ref="system:dispatch_query",
            owner_agent_id="ops-agent",
            actor_owner_id="ops-agent",
            task_segment={
                "segment_id": "cu:test:goal-step:1",
                "segment_kind": "goal-step",
                "index": 0,
                "total": 3,
            },
            resume_point={
                "phase": "compiled",
                "cursor": "cu:test:goal-step:1",
            },
            payload={},
            risk_level="guarded",
        ),
    )

    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_FakeIndustryService(),
        kernel_dispatcher=dispatcher,
        actor_mailbox_service=mailbox_service,
        agent_runtime_repository=runtime_repository,
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
            kernel_task_id="task-segmented",
        ):
            pass

    asyncio.run(_run())

    checkpoints = checkpoint_repository.list_checkpoints(
        agent_id="ops-agent",
        limit=None,
    )
    phases = {checkpoint.phase for checkpoint in checkpoints}
    assert {"query-start", "query-loaded", "query-streaming", "query-complete"} <= phases

    runtime = runtime_repository.get_runtime("ops-agent")
    assert runtime is not None
    assert runtime.last_checkpoint_id is not None
    assert runtime.metadata["last_task_segment_id"] == "cu:test:goal-step:1"

    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "Execution segment: goal-step 1/3" in prompt_appendix
    assert "Resume phase: compiled" in prompt_appendix


def test_query_execution_cancellation_does_not_leave_runtime_blocked(tmp_path) -> None:
    _FakeAgent.created.clear()
    state_store = SQLiteStateStore(tmp_path / "cancel-state.sqlite3")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="ops-agent",
            actor_key="ops-agent",
            actor_class="agent",
            desired_state="active",
            runtime_status="idle",
        ),
    )

    async def _cancel_stream(*, agents, coroutine_task):
        _ = agents
        _ = coroutine_task
        raise asyncio.CancelledError()
        yield

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(query_execution_module, "CoPawAgent", _FakeAgent)
    monkeypatch.setattr(query_execution_module, "stream_printing_messages", _cancel_stream)
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
        agent_runtime_repository=runtime_repository,
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "cancel this turn")],
            request=SimpleNamespace(
                session_id="sess-cancel",
                user_id="ops-agent",
                channel="console",
            ),
            kernel_task_id="task-cancelled",
        ):
            pass

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_run())

    runtime = runtime_repository.get_runtime("ops-agent")
    assert runtime is not None
    assert runtime.runtime_status != "blocked"
    assert runtime.current_task_id is None
    assert runtime.last_error_summary

    monkeypatch.undo()
