# -*- coding: utf-8 -*-
from __future__ import annotations

from .shared import *  # noqa: F401,F403


def test_query_execution_service_surfaces_team_role_gap_notice_in_chat(
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    prediction_service = _FakePredictionService()
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
        prediction_service=prediction_service,
    )

    async def _run():
        payload = []
        async for item in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "下一步怎么做")],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                session_kind="industry-agent-chat",
            ),
            kernel_task_id="task-team-gap-notice",
        ):
            payload.append(item)
        return payload

    messages = asyncio.run(_run())

    assert len(messages) == 1
    msg, last = messages[0]
    assert last is True
    assert "视觉设计专员" in msg.get_text_content()
    assert "批准补位" in msg.get_text_content()
    assert "拒绝补位" in msg.get_text_content()
    assert prediction_service.lookup_calls == ["industry-v1-ops"]
    assert _FakeAgent.created == []


def test_query_execution_service_can_approve_team_role_gap_from_chat(
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    prediction_service = _FakePredictionService()
    dispatcher = _FakeDecisionDispatcher()
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
        kernel_dispatcher=dispatcher,
        agent_profile_service=_FakeAgentProfileService(),
        prediction_service=prediction_service,
    )

    async def _run():
        payload = []
        async for item in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "批准补位")],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                session_kind="industry-agent-chat",
            ),
            kernel_task_id="task-team-gap-approve",
        ):
            payload.append(item)
        return payload

    messages = asyncio.run(_run())

    assert len(messages) == 1
    msg, last = messages[0]
    assert last is True
    assert "已批准补位" in msg.get_text_content()
    assert "decision-team-gap-1" in msg.get_text_content()
    assert "task-team-gap-1" in msg.get_text_content()
    assert prediction_service.execute_calls == [
        ("case-team-gap-1", "rec-team-gap-1", "copaw-agent-runner"),
    ]
    assert dispatcher.approve_calls == [
        (
            "decision-team-gap-1",
            "操作方已在执行中枢聊天中批准补位“视觉设计专员”。",
            True,
        ),
    ]
    assert _FakeAgent.created == []


def test_query_execution_service_can_reject_team_role_gap_from_chat(
    monkeypatch,
) -> None:
    _FakeAgent.created.clear()
    prediction_service = _FakePredictionService(
        recommendation={
            "case_id": "case-team-gap-2",
            "recommendation_id": "rec-team-gap-2",
            "suggested_role_name": "数据分析专员",
            "summary": "当前团队缺少长期承接数据复盘的岗位。",
            "status": "waiting-confirm",
            "decision_request_id": "decision-team-gap-2",
            "workflow_title": "Reporting loop",
        }
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
        kernel_dispatcher=_FakeDecisionDispatcher(),
        agent_profile_service=_FakeAgentProfileService(),
        prediction_service=prediction_service,
    )

    async def _run():
        payload = []
        async for item in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "拒绝补位")],
            request=SimpleNamespace(
                session_id="industry-chat:industry-v1-ops:execution-core",
                user_id="default",
                channel="console",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
                session_kind="industry-agent-chat",
            ),
            kernel_task_id="task-team-gap-reject",
        ):
            payload.append(item)
        return payload

    messages = asyncio.run(_run())

    assert len(messages) == 1
    msg, last = messages[0]
    assert last is True
    assert "已拒绝补位" in msg.get_text_content()
    assert "数据分析专员" in msg.get_text_content()
    assert "decision-team-gap-2" in msg.get_text_content()
    assert prediction_service.reject_calls == [
        (
            "case-team-gap-2",
            "rec-team-gap-2",
            "copaw-agent-runner",
            "操作方已在执行中枢聊天中拒绝补位“数据分析专员”。",
        ),
    ]
    assert _FakeAgent.created == []


def test_query_execution_service_recognizes_desktop_mcp_as_actuation(
    monkeypatch,
) -> None:
    class _DesktopAgentProfileService:
        def get_agent(self, agent_id: str):
            if agent_id != "ops-specialist":
                return None
            return SimpleNamespace(
                agent_id="ops-specialist",
                actor_key="industry:ops:specialist",
                actor_fingerprint="fp-ops-specialist-v1",
                name="Ops Specialist",
                role_name="Operations specialist",
                role_summary="Executes specialist workflows.",
                mission="Use the mounted browser and desktop surfaces to complete delivery work.",
                environment_constraints=["browser allowed", "desktop allowed"],
                evidence_expectations=["execution evidence"],
                current_goal_id="goal-1",
                current_goal="Execute specialist workflow",
            )

        def list_agents(self):
            agent = self.get_agent("ops-specialist")
            return [agent] if agent is not None else []

    class _DesktopCapabilityService(_FakeCapabilityService):
        def list_accessible_capabilities(self, *, agent_id: str | None, enabled_only: bool = False):
            mounts = list(
                super().list_accessible_capabilities(
                    agent_id="ops-agent" if agent_id == "ops-specialist" else agent_id,
                    enabled_only=enabled_only,
                ),
            )
            mounts.append(
                CapabilityMount(
                    id="tool:desktop_screenshot",
                    name="desktop_screenshot",
                    summary="Capture the current desktop.",
                    kind="local-tool",
                    source_kind="tool",
                    risk_level="guarded",
                    environment_requirements=["desktop"],
                    evidence_contract=["desktop-screenshot"],
                    role_access_policy=["all"],
                    enabled=True,
                ),
            )
            mounts.append(
                CapabilityMount(
                    id="mcp:desktop_windows",
                    name="Windows Desktop",
                    summary="Local Windows desktop control adapter.",
                    kind="remote-mcp",
                    source_kind="mcp",
                    risk_level="guarded",
                    environment_requirements=["desktop"],
                    evidence_contract=["mcp-call"],
                    role_access_policy=["mcp-enabled"],
                    enabled=True,
                    metadata={"key": "desktop_windows"},
                ),
            )
            return mounts

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
    mcp_manager._clients["desktop_windows"] = SimpleNamespace(name="desktop_windows")
    service = KernelQueryExecutionService(
        session_backend=session_backend,
        mcp_manager=mcp_manager,
        capability_service=_DesktopCapabilityService(),
        agent_profile_service=_DesktopAgentProfileService(),
        industry_service=_FakeIndustryService(),
    )

    async def _run():
        async for _msg, _last in service.execute_stream(
            msgs=[SimpleNamespace(get_text_content=lambda: "open the desktop app and continue")],
            request=SimpleNamespace(
                session_id="goal-1",
                user_id="ops-specialist",
                agent_id="ops-specialist",
                channel="goal",
                industry_label="Ops Industry Team",
                owner_scope="industry-v1-ops-scope",
                session_kind="agent-chat",
            ),
            kernel_task_id="task-desktop-1",
        ):
            pass

    asyncio.run(_run())

    prompt_appendix = _FakeAgent.created[0].kwargs["prompt_appendix"]
    assert "Desktop actuation is mounted in this session" in prompt_appendix
    assert "Attempt mounted browser or desktop workflows before claiming the task is impossible" in prompt_appendix
    assert "Mounted browser/desktop actuation may be used for registration, login, dashboard operations" in prompt_appendix
    assert "Treat manual verification as a checkpoint to resume from" in prompt_appendix
    assert "Desktop access is observation-only via screenshots" not in prompt_appendix
    assert mcp_manager.requested_keys == ["browser", "desktop_windows"]


def test_query_execution_service_keeps_main_brain_risky_desktop_request_in_model_flow(
    monkeypatch,
    tmp_path,
) -> None:
    class _DesktopCapabilityService(_FakeCapabilityService):
        def list_accessible_capabilities(self, *, agent_id: str | None, enabled_only: bool = False):
            mounts = list(
                super().list_accessible_capabilities(
                    agent_id=agent_id,
                    enabled_only=enabled_only,
                ),
            )
            mounts.append(
                CapabilityMount(
                    id="mcp:desktop_windows",
                    name="Windows Desktop",
                    summary="Local Windows desktop control adapter.",
                    kind="remote-mcp",
                    source_kind="mcp",
                    risk_level="guarded",
                    environment_requirements=["desktop"],
                    evidence_contract=["mcp-call"],
                    role_access_policy=["mcp-enabled"],
                    enabled=True,
                    metadata={"key": "desktop_windows"},
                ),
            )
            return mounts

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

    (
        dispatcher,
        _task_repository,
        _decision_repository,
        _governance_control_repository,
    ) = _build_real_kernel_dispatcher(tmp_path)
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_DesktopCapabilityService(),
        kernel_dispatcher=dispatcher,
        agent_profile_service=_FakeAgentProfileService(),
    )
    request = SimpleNamespace(
        session_id="industry-chat:industry-v1-ops:execution-core",
        user_id="ops-agent",
        channel="console",
        entry_source="chat",
        industry_instance_id="industry-v1-ops",
        industry_role_id="execution-core",
        industry_label="Ops Industry Team",
        owner_scope="industry-v1-ops-scope",
        task_mode="team-orchestration",
        session_kind="industry-agent-chat",
    )

    async def _run():
        payload = []
        async for item in service.execute_stream(
            msgs=[
                SimpleNamespace(
                    get_text_content=lambda: "change the security settings in the desktop app",
                ),
            ],
            request=request,
            kernel_task_id="task-parent-desktop-1",
        ):
            payload.append(item)
        return payload

    messages = asyncio.run(_run())

    assert [item[0].id for item in messages] == ["msg-1", "msg-2"]
    assert messages[-1][1] is True
    assert _FakeAgent.created

    task_store = dispatcher.task_store
    assert task_store is not None
    waiting_tasks = task_store.list_tasks(
        phase="waiting-confirm",
        owner_agent_id="ops-agent",
        limit=10,
    )
    assert waiting_tasks == []


def test_query_execution_service_keeps_main_brain_risky_browser_request_in_model_flow(
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

    (
        dispatcher,
        _task_repository,
        _decision_repository,
        _governance_control_repository,
    ) = _build_real_kernel_dispatcher(tmp_path)
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        kernel_dispatcher=dispatcher,
        agent_profile_service=_FakeAgentProfileService(),
    )
    request = SimpleNamespace(
        session_id="industry-chat:industry-v1-ops:execution-core",
        user_id="ops-agent",
        channel="console",
        entry_source="chat",
        industry_instance_id="industry-v1-ops",
        industry_role_id="execution-core",
        industry_label="Ops Industry Team",
        owner_scope="industry-v1-ops-scope",
        session_kind="industry-agent-chat",
    )

    async def _run():
        payload = []
        async for item in service.execute_stream(
            msgs=[
                SimpleNamespace(
                    get_text_content=lambda: "login to the JD seller dashboard and publish a new product",
                ),
            ],
            request=request,
            kernel_task_id="task-parent-early-1",
        ):
            payload.append(item)
        return payload

    messages = asyncio.run(_run())

    assert [item[0].id for item in messages] == ["msg-1", "msg-2"]
    assert messages[-1][1] is True
    assert _FakeAgent.created

    task_store = dispatcher.task_store
    assert task_store is not None
    waiting_tasks = task_store.list_tasks(
        phase="waiting-confirm",
        owner_agent_id="ops-agent",
        limit=10,
    )
    assert waiting_tasks == []


def test_query_execution_tool_preflight_requires_confirmation_for_risky_browser_workflow() -> None:
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
    )

    preflight = service._build_tool_preflight(
        delegation_guard=None,
        msgs=[SimpleNamespace(get_text_content=lambda: "登录京东商家后台并上架新商品")],
    )
    assert preflight is not None

    blocked = preflight(
        "browser_use",
        tuple(),
        {"action": "click", "selector": "#submit-transfer"},
    )
    assert isinstance(blocked, ToolResponse)
    payload = json.loads(query_execution_module._tool_response_text(blocked))
    assert payload["success"] is False
    assert payload["error_code"] == "user_confirmation_required"
    assert payload["confirmation_required"] is True
    assert payload["action"] == "click"

    assert preflight("browser_use", tuple(), {"action": "navigate"}) is None
    assert preflight("browser_use", tuple(), {"action": "fill_form"}) is None
    assert preflight("browser_use", tuple(), {"action": "file_upload"}) is None


def test_query_execution_tool_preflight_allows_risky_browser_workflow_after_confirmation() -> None:
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
    )

    preflight = service._build_tool_preflight(
        delegation_guard=None,
        msgs=[SimpleNamespace(get_text_content=lambda: "确认继续，登录京东商家后台并上架新商品")],
    )
    assert preflight is not None
    assert preflight(
        "browser_use",
        tuple(),
        {"action": "click", "selector": "#submit-transfer"},
    ) is None


def test_query_execution_tool_preflight_allows_desktop_launch_by_default() -> None:
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
    )

    preflight = service._build_tool_preflight(
        delegation_guard=None,
        msgs=[SimpleNamespace(get_text_content=lambda: "打开企业微信并处理工单")],
    )
    assert preflight is not None

    assert (
        preflight(
            "desktop_actuation",
            tuple(),
            {"action": "launch_application", "executable": "C:/Program Files/WeChat/WeChat.exe"},
        )
        is None
    )
    assert preflight("desktop_actuation", tuple(), {"action": "type_text"}) is None
    assert preflight("desktop_actuation", tuple(), {"action": "click"}) is None


def test_query_execution_tool_preflight_requires_confirmation_for_contextual_browser_submit_click() -> None:
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
    )

    preflight = service._build_tool_preflight(
        delegation_guard=None,
        msgs=[SimpleNamespace(get_text_content=lambda: "继续网页操作")],
    )
    assert preflight is not None

    blocked = preflight(
        "browser_use",
        tuple(),
        {"action": "click", "selector": "#submit-transfer"},
    )
    assert isinstance(blocked, ToolResponse)
    payload = json.loads(query_execution_module._tool_response_text(blocked))
    assert payload["success"] is False
    assert payload["error_code"] == "user_confirmation_required"
    assert payload["confirmation_required"] is True
    assert payload["action"] == "click"

    assert preflight("browser_use", tuple(), {"action": "click", "selector": "#next-page"}) is None


def test_query_execution_tool_preflight_requires_confirmation_for_contextual_desktop_transfer() -> None:
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        agent_profile_service=_FakeAgentProfileService(),
    )

    preflight = service._build_tool_preflight(
        delegation_guard=None,
        msgs=[SimpleNamespace(get_text_content=lambda: "继续桌面操作")],
    )
    assert preflight is not None

    blocked = preflight(
        "desktop_actuation",
        tuple(),
        {"action": "type_text", "text": "向张三转账100元", "title_contains": "企业微信"},
    )
    assert isinstance(blocked, ToolResponse)
    payload = json.loads(query_execution_module._tool_response_text(blocked))
    assert payload["success"] is False
    assert payload["error_code"] == "user_confirmation_required"
    assert payload["confirmation_required"] is True
    assert payload["action"] == "type_text"

    assert (
        preflight(
            "desktop_actuation",
            tuple(),
            {"action": "press_keys", "keys": "Alt+F4", "title_contains": "企业微信"},
        )
        is None
    )


def test_query_execution_tool_preflight_keeps_contextual_browser_gates_separate(
    tmp_path,
) -> None:
    (
        dispatcher,
        _task_repository,
        _decision_repository,
        _governance_control_repository,
    ) = _build_real_kernel_dispatcher(tmp_path)
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        kernel_dispatcher=dispatcher,
        agent_profile_service=_FakeAgentProfileService(),
    )
    request = SimpleNamespace(
        session_id="agent-chat:ops-specialist",
        user_id="ops-specialist",
        agent_id="ops-specialist",
        channel="console",
        entry_source="chat",
        industry_instance_id="industry-v1-ops",
        industry_role_id="specialist",
        industry_label="Ops Industry Team",
        owner_scope="industry-v1-ops-scope",
        session_kind="agent-chat",
        task_mode="team-orchestration",
    )

    preflight = service._build_tool_preflight(
        delegation_guard=None,
        msgs=[SimpleNamespace(get_text_content=lambda: "继续网页操作")],
        request=request,
        owner_agent_id="ops-specialist",
        agent_profile=None,
        kernel_task_id="task-parent-contextual-click",
    )
    assert preflight is not None

    first = json.loads(
        query_execution_module._tool_response_text(
            preflight("browser_use", tuple(), {"action": "click", "selector": "#submit-transfer"})
        )
    )
    repeat = json.loads(
        query_execution_module._tool_response_text(
            preflight("browser_use", tuple(), {"action": "click", "selector": "#submit-transfer"})
        )
    )
    second = json.loads(
        query_execution_module._tool_response_text(
            preflight("browser_use", tuple(), {"action": "click", "selector": "#confirm-transfer"})
        )
    )

    assert repeat["decision_request_id"] == first["decision_request_id"]
    assert second["decision_request_id"] != first["decision_request_id"]
    assert second["task_id"] != first["task_id"]


def test_query_execution_tool_preflight_creates_runtime_center_decision_for_risky_browser_workflow(
    tmp_path,
) -> None:
    (
        dispatcher,
        task_repository,
        decision_repository,
        _governance_control_repository,
    ) = _build_real_kernel_dispatcher(tmp_path)
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        kernel_dispatcher=dispatcher,
        agent_profile_service=_FakeAgentProfileService(),
    )
    request = SimpleNamespace(
        session_id="agent-chat:ops-specialist",
        user_id="ops-specialist",
        agent_id="ops-specialist",
        channel="console",
        entry_source="chat",
        industry_instance_id="industry-v1-ops",
        industry_role_id="specialist",
        industry_label="Ops Industry Team",
        owner_scope="industry-v1-ops-scope",
        session_kind="agent-chat",
        task_mode="team-orchestration",
    )
    agent_profile = None
    preflight = service._build_tool_preflight(
        delegation_guard=None,
        msgs=[SimpleNamespace(get_text_content=lambda: "登录京东商家后台并上架新商品")],
        request=request,
        owner_agent_id="ops-specialist",
        agent_profile=agent_profile,
        kernel_task_id="task-parent-1",
    )

    assert preflight is not None
    blocked = preflight(
        "browser_use",
        tuple(),
        {"action": "click", "selector": "#submit-transfer"},
    )
    assert isinstance(blocked, ToolResponse)
    payload = json.loads(query_execution_module._tool_response_text(blocked))

    assert payload["success"] is False
    assert payload["error_code"] == "user_confirmation_required"
    assert payload["action"] == "click"
    assert payload["decision_request_id"]
    assert payload["decision_status"] == "open"
    assert payload["decision_route"] == (
        f"/api/runtime-center/decisions/{payload['decision_request_id']}"
    )
    assert payload["task_route"] == f"/api/runtime-center/tasks/{payload['task_id']}"
    assert payload["actions"] == {
        "review": f"/api/runtime-center/decisions/{payload['decision_request_id']}/review",
        "approve": f"/api/runtime-center/decisions/{payload['decision_request_id']}/approve",
        "reject": f"/api/runtime-center/decisions/{payload['decision_request_id']}/reject",
    }
    assert payload["decision_summary"]

    repeated = preflight(
        "browser_use",
        tuple(),
        {"action": "click", "selector": "#submit-transfer"},
    )
    repeated_payload = json.loads(query_execution_module._tool_response_text(repeated))
    assert repeated_payload["decision_request_id"] == payload["decision_request_id"]
    assert repeated_payload["task_id"] == payload["task_id"]

    next_turn_preflight = service._build_tool_preflight(
        delegation_guard=None,
        msgs=[SimpleNamespace(get_text_content=lambda: "登录京东商家后台并上架新商品")],
        request=request,
        owner_agent_id="ops-specialist",
        agent_profile=agent_profile,
        kernel_task_id="task-parent-2",
    )
    next_turn_blocked = next_turn_preflight(
        "browser_use",
        tuple(),
        {"action": "click", "selector": "#submit-transfer"},
    )
    next_turn_payload = json.loads(query_execution_module._tool_response_text(next_turn_blocked))
    assert next_turn_payload["decision_request_id"] == payload["decision_request_id"]
    assert next_turn_payload["task_id"] == payload["task_id"]

    decision = decision_repository.get_decision_request(payload["decision_request_id"])
    assert decision is not None
    assert decision.decision_type == "query-tool-confirmation"
    assert decision.summary == payload["decision_summary"]
    task_record = task_repository.get_task(payload["task_id"])
    assert task_record is not None
    kernel_meta = decode_kernel_task_metadata(task_record.acceptance_criteria)
    assert kernel_meta is not None
    assert kernel_meta["payload"]["tool_name"] == "browser_use"
    assert kernel_meta["payload"]["tool_action"] == "click"
    assert kernel_meta["payload"]["request_context"]["industry_instance_id"] == "industry-v1-ops"
    assert kernel_meta["payload"]["request_context"]["task_mode"] == "team-orchestration"
    approval = asyncio.run(
        dispatcher.approve_decision(
            payload["decision_request_id"],
            resolution="已批准继续网页代操。",
        ),
    )
    assert approval.success is True
    assert approval.phase == "completed"
    assert approval.decision_request_id == payload["decision_request_id"]

    approved_task = dispatcher.lifecycle.get_task(payload["task_id"])
    assert approved_task is not None
    assert approved_task.phase == "completed"

    approved_preflight = service._build_tool_preflight(
        delegation_guard=None,
        msgs=[SimpleNamespace(get_text_content=lambda: "登录京东商家后台并上架新商品")],
        request=request,
        owner_agent_id="ops-specialist",
        agent_profile=agent_profile,
        kernel_task_id="task-parent-3",
    )
    assert approved_preflight(
        "browser_use",
        tuple(),
        {"action": "click", "selector": "#submit-transfer"},
    ) is None


def test_query_execution_tool_preflight_approves_existing_risky_browser_confirmation_from_chat(
    tmp_path,
) -> None:
    (
        dispatcher,
        task_repository,
        decision_repository,
        _governance_control_repository,
    ) = _build_real_kernel_dispatcher(tmp_path)
    service = KernelQueryExecutionService(
        session_backend=_FakeSessionBackend(),
        capability_service=_FakeCapabilityService(),
        kernel_dispatcher=dispatcher,
        agent_profile_service=_FakeAgentProfileService(),
    )
    request = SimpleNamespace(
        session_id="agent-chat:ops-specialist",
        user_id="ops-specialist",
        agent_id="ops-specialist",
        channel="console",
        entry_source="chat",
        industry_instance_id="industry-v1-ops",
        industry_role_id="specialist",
        industry_label="Ops Industry Team",
        owner_scope="industry-v1-ops-scope",
        session_kind="agent-chat",
        task_mode="team-orchestration",
    )

    preflight = service._build_tool_preflight(
        delegation_guard=None,
        msgs=[SimpleNamespace(get_text_content=lambda: "登录京东商家后台并上架新商品")],
        request=request,
        owner_agent_id="ops-specialist",
        agent_profile=None,
        kernel_task_id="task-parent-chat-confirm-1",
    )
    blocked = preflight(
        "browser_use",
        tuple(),
        {"action": "click", "selector": "#submit-transfer"},
    )
    payload = json.loads(query_execution_module._tool_response_text(blocked))

    async def _approve_from_chat() -> None:
        next_turn_preflight = service._build_tool_preflight(
            delegation_guard=None,
            msgs=[SimpleNamespace(get_text_content=lambda: "确认继续")],
            request=request,
            owner_agent_id="ops-specialist",
            agent_profile=None,
            kernel_task_id="task-parent-chat-confirm-2",
        )
        assert next_turn_preflight is not None
        assert next_turn_preflight(
            "browser_use",
            tuple(),
            {"action": "click", "selector": "#submit-transfer"},
        ) is None
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(_approve_from_chat())

    decision = decision_repository.get_decision_request(payload["decision_request_id"])
    assert decision is not None
    assert decision.status == "approved"
    assert "主脑聊天" in (decision.resolution or "")
    approved_task = task_repository.get_task(payload["task_id"])
    assert approved_task is not None
    assert approved_task.status == "completed"


def test_query_execution_service_resumes_approved_query_tool_confirmation(
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

    (
        dispatcher,
        task_repository,
        _decision_repository,
        _governance_control_repository,
    ) = _build_real_kernel_dispatcher(tmp_path)
    session_backend = _FakeSessionBackend()
    service = KernelQueryExecutionService(
        session_backend=session_backend,
        capability_service=_FakeCapabilityService(),
        kernel_dispatcher=dispatcher,
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_FakeIndustryService(),
    )
    request = SimpleNamespace(
        session_id="agent-chat-1",
        user_id="ops-specialist",
        agent_id="ops-specialist",
        channel="industry",
        industry_instance_id="industry-v1-ops",
        industry_role_id="specialist",
        industry_label="Ops Industry Team",
        owner_scope="industry-v1-ops-scope",
        session_kind="agent-chat",
        task_mode="team-orchestration",
    )
    agent_profile = None
    preflight = service._build_tool_preflight(
        delegation_guard=None,
        msgs=[SimpleNamespace(get_text_content=lambda: "登录京东商家后台并上架新商品")],
        request=request,
        owner_agent_id="ops-specialist",
        agent_profile=agent_profile,
        kernel_task_id="task-parent-1",
    )

    blocked = preflight(
        "browser_use",
        tuple(),
        {"action": "click", "selector": "#submit-transfer"},
    )
    payload = json.loads(query_execution_module._tool_response_text(blocked))
    asyncio.run(
        dispatcher.approve_decision(
            payload["decision_request_id"],
            resolution="已批准继续网页代操",
        ),
    )

    resumed = asyncio.run(
        service.resume_query_tool_confirmation(
            decision_request_id=payload["decision_request_id"],
        ),
    )

    assert resumed["resumed"] is True
    assert resumed["stream_events"] == 2
    assert resumed["task_id"]
    resumed_task = dispatcher.lifecycle.get_task(resumed["task_id"])
    assert resumed_task is not None
    assert resumed_task.phase == "completed"
    resume_task_record = task_repository.get_task(resumed["task_id"])
    assert resume_task_record is not None
    kernel_meta = decode_kernel_task_metadata(resume_task_record.acceptance_criteria)
    assert kernel_meta is not None
    assert kernel_meta["payload"]["resume_kind"] == "query-tool-confirmation"
    assert kernel_meta["payload"]["resume_source_decision_id"] == payload["decision_request_id"]
    assert kernel_meta["payload"]["request_context"]["task_mode"] == "team-orchestration"
    assert session_backend.saved == [("agent-chat-1", "ops-specialist")]
    saved_agent = session_backend.saved_agents[-1]
    assert saved_agent.memory.deleted_ids
    assert len(saved_agent.memory.deleted_ids[0]) == 1


def test_query_execution_service_resumes_human_assist_with_seeded_work_context_and_environment(
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

    (
        dispatcher,
        task_repository,
        _decision_repository,
        _governance_control_repository,
    ) = _build_real_kernel_dispatcher(tmp_path)
    session_backend = _FakeSessionBackend()
    service = KernelQueryExecutionService(
        session_backend=session_backend,
        capability_service=_FakeCapabilityService(),
        kernel_dispatcher=dispatcher,
        agent_profile_service=_FakeAgentProfileService(),
        industry_service=_FakeIndustryService(),
    )

    resumed = asyncio.run(
        service.resume_human_assist_task(
            task=SimpleNamespace(
                id="human-assist:host-handoff-1",
                industry_instance_id="industry-v1-ops",
                assignment_id="assignment-1",
                task_id="task-host-handoff-1",
                chat_thread_id="industry-chat:industry-v1-ops:execution-core",
                title="Return host handoff",
                required_action="Return after checkpoint:host-handoff-1 is complete.",
                submission_text="Completed checkpoint:host-handoff-1.",
                submission_evidence_refs=["media-analysis-1"],
                resume_checkpoint_ref="checkpoint:host-handoff-1",
                submission_payload={
                    "industry_instance_id": "industry-v1-ops",
                    "session_id": "industry-chat:industry-v1-ops:execution-core",
                    "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
                    "channel": "console",
                    "environment_ref": "session:console:industry:industry-v1-ops",
                    "work_context_id": "ctx-host-handoff-1",
                    "main_brain_runtime": {
                        "work_context_id": "ctx-host-handoff-1",
                        "environment_ref": "session:console:industry:industry-v1-ops",
                        "environment_session_id": "session:console:industry:industry-v1-ops",
                        "environment_binding_kind": "host-handoff",
                        "environment_resume_ready": False,
                        "recovery_mode": "handoff",
                        "recovery_reason": "human-return",
                        "resume_checkpoint_id": "checkpoint:host-handoff-1",
                    },
                },
            ),
        ),
    )

    assert resumed["resumed"] is True
    assert resumed["task_id"]

    resumed_task = dispatcher.lifecycle.get_task(resumed["task_id"])
    assert resumed_task is not None
    assert resumed_task.work_context_id == "ctx-host-handoff-1"
    assert resumed_task.environment_ref == "session:console:industry:industry-v1-ops"

    resume_task_record = task_repository.get_task(resumed["task_id"])
    assert resume_task_record is not None
    assert resume_task_record.work_context_id == "ctx-host-handoff-1"
    kernel_meta = decode_kernel_task_metadata(resume_task_record.acceptance_criteria)
    assert kernel_meta is not None
    assert kernel_meta["payload"]["resume_kind"] == "human-assist"
    assert kernel_meta["payload"]["request_context"]["work_context_id"] == "ctx-host-handoff-1"
    assert (
        kernel_meta["payload"]["request_context"]["main_brain_runtime"]["environment"]["ref"]
        == "session:console:industry:industry-v1-ops"
    )
    assert (
        kernel_meta["payload"]["request_context"]["main_brain_runtime"]["recovery"][
            "checkpoint_id"
        ]
        == "checkpoint:host-handoff-1"
    )


