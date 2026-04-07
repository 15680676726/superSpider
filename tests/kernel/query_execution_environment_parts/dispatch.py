# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel import ActorWorker

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


def test_query_execution_service_discover_capabilities_preserves_mcp_registry_provider() -> None:
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
        system_capability_ids={"system:discover_capabilities"},
        kernel_task_id="task-1",
    )
    tools_by_name = {
        tool_fn.__name__: tool_fn
        for tool_fn in tool_functions
    }

    discover_capabilities_result = asyncio.run(
        tools_by_name["discover_capabilities"](
            query_text="browser automation",
            providers=["remote", "mcp-registry"],
        ),
    )

    assert isinstance(discover_capabilities_result, ToolResponse)
    discover_capabilities_payload = query_execution_module._structured_tool_payload(
        discover_capabilities_result,
        default_error="discover_capabilities test payload missing",
    )
    assert discover_capabilities_payload["success"] is True
    discover_capabilities_task = kernel_dispatcher.submitted[0]
    assert discover_capabilities_task.payload["providers"] == [
        "remote",
        "mcp-registry",
    ]


def test_query_execution_service_query_turn_binds_builtin_tool_delegate_into_runtime_stream(
    monkeypatch,
) -> None:
    from copaw.agents.react_agent import _wrap_tool_function_for_toolkit
    from copaw.agents.tools import get_current_time

    _FakeAgent.created.clear()

    class _FrontdoorCapabilityService(_FakeCapabilityService):
        def __init__(self) -> None:
            super().__init__()
            self.tasks: list[KernelTask] = []

        async def execute_task(self, task: KernelTask) -> dict[str, object]:
            self.tasks.append(task)
            return {
                "success": True,
                "summary": "delegated-runtime-frontdoor",
            }

    class _FrontdoorDispatcher:
        def __init__(self, capability_service, parent_task: KernelTask) -> None:
            self.capability_service = capability_service
            self.parent_task = parent_task
            self.submitted: list[KernelTask] = []
            self.lifecycle = SimpleNamespace(
                get_task=lambda task_id: (
                    self.parent_task
                    if task_id == self.parent_task.id
                    else next(
                        (task for task in self.submitted if task.id == task_id),
                        None,
                    )
                ),
            )

        def submit(self, task: KernelTask):
            self.submitted.append(task)
            return SimpleNamespace(
                task_id=task.id,
                phase="executing",
                summary="admitted",
                error=None,
                decision_request_id=None,
            )

        async def execute_task(self, task_id: str):
            task = next(task for task in self.submitted if task.id == task_id)
            return await self.capability_service.execute_task(task)

    class _FrontdoorAgent(_FakeAgent):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            self.tool_response = None

        def __call__(self, msgs):
            self.messages = msgs
            wrapped = _wrap_tool_function_for_toolkit(get_current_time)

            async def _run():
                self.tool_response = await wrapped()
                return "fake-agent-task"

            return _run()

    async def _stream_and_wait_for_agent_tool(*, agents, coroutine_task):
        _ = agents
        await coroutine_task
        yield SimpleNamespace(id="msg-1"), True

    monkeypatch.setattr(query_execution_module, "CoPawAgent", _FrontdoorAgent)
    monkeypatch.setattr(
        query_execution_module,
        "stream_printing_messages",
        _stream_and_wait_for_agent_tool,
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

    capability_service = _FrontdoorCapabilityService()
    kernel_task = KernelTask(
        id="task-query-frontdoor",
        title="query turn frontdoor task",
        owner_agent_id="ops-agent",
        work_context_id="work-context-frontdoor",
        payload={
            "request_context": {
                "main_brain_runtime": {
                    "environment": {"ref": "desktop:query-frontdoor"},
                },
            },
        },
    )
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=capability_service,
        agent_profile_service=_FakeAgentProfileService(),
        kernel_dispatcher=_FrontdoorDispatcher(capability_service, kernel_task),
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "what time is it")],
            request=SimpleNamespace(
                session_id="industry-chat-1",
                user_id="default",
                agent_id="ops-agent",
                channel="console",
                industry_instance_id="industry-v1-ops",
                session_kind="industry-agent-chat",
            ),
            kernel_task_id=kernel_task.id,
        ):
            pass

    asyncio.run(_run())

    assert len(_FakeAgent.created) == 1
    agent = _FakeAgent.created[0]
    assert agent.tool_response.content[0]["text"] == "delegated-runtime-frontdoor"
    [submitted] = capability_service.tasks
    assert submitted.parent_task_id == "task-query-frontdoor"
    assert submitted.id.startswith("task-query-frontdoor:tool:tool-get_current_time:")
    assert submitted.capability_ref == "tool:get_current_time"
    assert submitted.owner_agent_id == "ops-agent"
    assert submitted.work_context_id == "work-context-frontdoor"
    assert submitted.environment_ref == "desktop:query-frontdoor"
    assert submitted.payload == {
        "request_context": {
            "work_context_id": "work-context-frontdoor",
            "main_brain_runtime": {
                "environment": {
                    "ref": "desktop:query-frontdoor",
                    "resume_ready": False,
                    "live_session_bound": False,
                },
            },
        },
    }


def test_query_execution_service_query_turn_falls_back_to_builtin_when_delegate_fails(
    monkeypatch,
) -> None:
    from copaw.agents.react_agent import _wrap_tool_function_for_toolkit

    _FakeAgent.created.clear()

    async def get_current_time() -> dict[str, object]:
        return {
            "success": True,
            "summary": "builtin-fallback-sentinel",
        }

    class _FailingFrontdoorCapabilityService(_FakeCapabilityService):
        def __init__(self) -> None:
            super().__init__()
            self.tasks: list[KernelTask] = []

        async def execute_task(self, task: KernelTask) -> dict[str, object]:
            self.tasks.append(task)
            raise RuntimeError("delegate-offline")

    class _FailingFrontdoorDispatcher:
        def __init__(self, capability_service, parent_task: KernelTask) -> None:
            self.capability_service = capability_service
            self.parent_task = parent_task
            self.submitted: list[KernelTask] = []
            self.lifecycle = SimpleNamespace(
                get_task=lambda task_id: (
                    self.parent_task
                    if task_id == self.parent_task.id
                    else next(
                        (task for task in self.submitted if task.id == task_id),
                        None,
                    )
                ),
            )

        def submit(self, task: KernelTask):
            self.submitted.append(task)
            return SimpleNamespace(
                task_id=task.id,
                phase="executing",
                summary="admitted",
                error=None,
                decision_request_id=None,
            )

        async def execute_task(self, task_id: str):
            task = next(task for task in self.submitted if task.id == task_id)
            return await self.capability_service.execute_task(task)

    class _FrontdoorAgent(_FakeAgent):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            self.tool_response = None

        def __call__(self, msgs):
            self.messages = msgs
            wrapped = _wrap_tool_function_for_toolkit(get_current_time)

            async def _run():
                self.tool_response = await wrapped()
                return "fake-agent-task"

            return _run()

    async def _stream_and_wait_for_agent_tool(*, agents, coroutine_task):
        _ = agents
        await coroutine_task
        yield SimpleNamespace(id="msg-1"), True

    monkeypatch.setattr(query_execution_module, "CoPawAgent", _FrontdoorAgent)
    monkeypatch.setattr(
        query_execution_module,
        "stream_printing_messages",
        _stream_and_wait_for_agent_tool,
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

    capability_service = _FailingFrontdoorCapabilityService()
    kernel_task = KernelTask(
        id="task-query-frontdoor-fallback",
        title="query turn frontdoor fallback task",
        owner_agent_id="ops-agent",
    )
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=capability_service,
        agent_profile_service=_FakeAgentProfileService(),
        kernel_dispatcher=_FailingFrontdoorDispatcher(capability_service, kernel_task),
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "what time is it")],
            request=SimpleNamespace(
                session_id="industry-chat-1",
                user_id="default",
                agent_id="ops-agent",
                channel="console",
                industry_instance_id="industry-v1-ops",
                session_kind="industry-agent-chat",
            ),
            kernel_task_id=kernel_task.id,
        ):
            pass

    asyncio.run(_run())

    assert len(_FakeAgent.created) == 1
    agent = _FakeAgent.created[0]
    assert capability_service.tasks
    assert agent.tool_response.content
    assert "builtin-fallback-sentinel" not in agent.tool_response.content[0]["text"]
    assert "delegate-offline" in agent.tool_response.content[0]["text"]


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


def test_query_execution_service_delegation_first_guard_unlocks_after_child_terminal_report(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "delegation-guard.sqlite3")
    mailbox_repository = SqliteAgentMailboxRepository(state_store)
    checkpoint_repository = SqliteAgentCheckpointRepository(state_store)
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
    )
    kernel_dispatcher = _FakeKernelDispatcher()
    capability_service = _FakeCapabilityService()
    agent_profile_service = _FakeAgentProfileService()
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=capability_service,
        kernel_dispatcher=kernel_dispatcher,
        agent_profile_service=agent_profile_service,
        industry_service=_FakeIndustryService(),
        actor_mailbox_service=mailbox_service,
        agent_runtime_repository=runtime_repository,
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
    parent_task_id = "task-parent-1"
    child_task_id = "task-child-1"
    mailbox_item = mailbox_service.enqueue_item(
        agent_id="ops-researcher",
        task_id=child_task_id,
        work_context_id="work-context-1",
        source_agent_id="ops-agent",
        envelope_type="delegation",
        title="delegated child task",
        summary="research the blocker and report back",
        capability_ref="system:dispatch_query",
        conversation_thread_id="agent-chat:ops-researcher",
        payload={
            "request": {
                "session_id": request.session_id,
                "control_thread_id": request.session_id,
            },
            "report_back_mode": "summary",
        },
        metadata={
            "parent_task_id": parent_task_id,
            "report_back_mode": "summary",
            "session_id": request.session_id,
            "control_thread_id": request.session_id,
            "work_context_id": "work-context-1",
        },
    )
    mailbox_service.create_checkpoint(
        agent_id="ops-researcher",
        mailbox_id=mailbox_item.id,
        task_id=child_task_id,
        work_context_id="work-context-1",
        checkpoint_kind="task-result",
        status="applied",
        phase="completed",
        conversation_thread_id="agent-chat:ops-researcher",
        summary="child task finished and reported back",
        resume_payload={
            "task_id": child_task_id,
            "phase": "completed",
            "parent_task_id": parent_task_id,
            "report_back_mode": "summary",
            "session_id": request.session_id,
            "control_thread_id": request.session_id,
            "work_context_id": "work-context-1",
        },
    )

    delegation_guard = service._resolve_delegation_first_guard(
        request=request,
        owner_agent_id="ops-agent",
        agent_profile=agent_profile,
        system_capability_ids={
            "system:dispatch_query",
            "system:delegate_task",
        },
        kernel_task_id=parent_task_id,
        conversation_thread_id=request.session_id,
    )

    assert delegation_guard is not None
    assert delegation_guard.locked is False

    assert service._build_delegation_policy_lines(
        delegation_guard=delegation_guard,
    ) == []


def test_query_execution_service_delegation_first_guard_unlocks_after_real_worker_terminal_report(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "delegation-guard-worker.sqlite3")
    mailbox_repository = SqliteAgentMailboxRepository(state_store)
    checkpoint_repository = SqliteAgentCheckpointRepository(state_store)
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
    )

    class _ChildCompleteDispatcher:
        async def execute_task(self, task_id: str):
            return SimpleNamespace(
                phase="completed",
                summary=f"Completed {task_id}",
                model_dump=lambda mode="json": {
                    "phase": "completed",
                    "summary": f"Completed {task_id}",
                },
            )

    worker = ActorWorker(
        worker_id="actor-worker-test",
        mailbox_service=mailbox_service,
        kernel_dispatcher=_ChildCompleteDispatcher(),
    )
    capability_service = _FakeCapabilityService()
    agent_profile_service = _FakeAgentProfileService()
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=capability_service,
        kernel_dispatcher=_FakeKernelDispatcher(),
        agent_profile_service=agent_profile_service,
        industry_service=_FakeIndustryService(),
        actor_mailbox_service=mailbox_service,
        agent_runtime_repository=runtime_repository,
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
    parent_task_id = "task-parent-real-worker"
    child_task_id = "task-child-real-worker"
    mailbox_service.enqueue_item(
        agent_id="ops-researcher",
        task_id=child_task_id,
        work_context_id="work-context-1",
        source_agent_id="ops-agent",
        envelope_type="delegation",
        title="delegated child task",
        summary="research the blocker and report back",
        capability_ref="system:dispatch_query",
        conversation_thread_id="agent-chat:ops-researcher",
        payload={
            "request_context": {
                "session_id": request.session_id,
                "context_key": request.session_id,
                "work_context_id": "work-context-1",
            },
        },
        metadata={
            "parent_task_id": parent_task_id,
            "assignment_id": "assignment-1",
            "report_back_mode": "summary",
            "session_id": request.session_id,
            "control_thread_id": request.session_id,
            "work_context_id": "work-context-1",
            "industry_instance_id": "industry-v1-ops",
            "industry_role_id": "researcher",
        },
    )

    handled = asyncio.run(worker.run_once("ops-researcher"))

    assert handled is True
    checkpoints = checkpoint_repository.list_checkpoints(agent_id="ops-researcher", limit=None)
    terminal_checkpoint = next(
        checkpoint
        for checkpoint in checkpoints
        if checkpoint.checkpoint_kind == "task-result"
    )
    assert terminal_checkpoint.resume_payload["parent_task_id"] == parent_task_id
    assert terminal_checkpoint.resume_payload["report_back_mode"] == "summary"
    assert terminal_checkpoint.resume_payload["control_thread_id"] == request.session_id
    assert terminal_checkpoint.resume_payload["assignment_id"] == "assignment-1"

    delegation_guard = service._resolve_delegation_first_guard(
        request=request,
        owner_agent_id="ops-agent",
        agent_profile=agent_profile,
        system_capability_ids={
            "system:dispatch_query",
            "system:delegate_task",
        },
        kernel_task_id=parent_task_id,
        conversation_thread_id=request.session_id,
    )

    assert delegation_guard is not None
    assert delegation_guard.locked is False
    assert service._build_delegation_policy_lines(
        delegation_guard=delegation_guard,
    ) == []


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
