# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from agentscope.tool import ToolResponse

import copaw.kernel.main_brain_intake as main_brain_intake_module
import copaw.kernel.query_execution as query_execution_module
import copaw.kernel.query_execution_runtime as query_execution_runtime_module
import copaw.kernel.query_execution_shared as query_execution_shared_module
from copaw.capabilities import CapabilityMount
from copaw.environments import (
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    SessionMountRepository,
)
from copaw.kernel import ActorMailboxService, KernelDispatcher, KernelTask
from copaw.kernel.persistence import KernelTaskStore, decode_kernel_task_metadata
from copaw.kernel.query_execution import KernelQueryExecutionService
from copaw.state import AgentRuntimeRecord, SQLiteStateStore
from copaw.state.repositories import (
    SqliteAgentCheckpointRepository,
    SqliteAgentLeaseRepository,
    SqliteAgentMailboxRepository,
    SqliteAgentRuntimeRepository,
    SqliteDecisionRequestRepository,
    SqliteGovernanceControlRepository,
    SqliteRuntimeFrameRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


def _make_fake_chat_writeback_model_decision(
    *,
    intent_kind: str = "chat",
    intent_confidence: float = 0.0,
    intent_signals: list[str] | None = None,
    risky_actuation_requested: bool = False,
    risky_actuation_surface: str | None = None,
    should_writeback: bool = False,
    approved_targets: list[str] | None = None,
    kickoff_allowed: bool = False,
    explicit_execution_confirmation: bool = False,
    team_role_gap_action: str | None = None,
    team_role_gap_notice: bool = False,
    blockers: list[str] | None = None,
    operator_requirements: list[str] | None = None,
    priority_order: list[str] | None = None,
    execution_constraints: list[str] | None = None,
    switch_to_operator_guided: bool = False,
    goal_title: str | None = None,
    goal_summary: str | None = None,
    goal_plan_steps: list[str] | None = None,
    schedule_title: str | None = None,
    schedule_summary: str | None = None,
    schedule_cron: str | None = None,
    schedule_prompt: str | None = None,
):
    strategy = None
    if should_writeback:
        strategy = SimpleNamespace(
            operator_requirements=list(operator_requirements or []),
            priority_order=list(priority_order or []),
            execution_constraints=list(execution_constraints or []),
            switch_to_operator_guided=switch_to_operator_guided,
        )
    goal = None
    if goal_title is not None or goal_summary is not None or goal_plan_steps:
        goal = SimpleNamespace(
            title=goal_title,
            summary=goal_summary,
            plan_steps=list(goal_plan_steps or []),
        )
    schedule = None
    if (
        schedule_title is not None
        or schedule_summary is not None
        or schedule_cron is not None
        or schedule_prompt is not None
    ):
        schedule = SimpleNamespace(
            title=schedule_title,
            summary=schedule_summary,
            cron=schedule_cron,
            prompt=schedule_prompt,
        )
    return SimpleNamespace(
        intent_kind=intent_kind,
        intent_confidence=intent_confidence,
        intent_signals=list(intent_signals or []),
        risky_actuation_requested=risky_actuation_requested,
        risky_actuation_surface=risky_actuation_surface,
        should_writeback=should_writeback,
        approved_targets=list(approved_targets or []),
        kickoff_allowed=kickoff_allowed,
        explicit_execution_confirmation=explicit_execution_confirmation,
        team_role_gap_action=team_role_gap_action,
        team_role_gap_notice=team_role_gap_notice,
        confidence=1.0 if should_writeback else intent_confidence,
        blockers=list(blockers or []),
        rationale=None,
        strategy=strategy,
        goal=goal,
        schedule=schedule,
    )


def _fake_chat_writeback_model_decision(**kwargs):
    text = str(kwargs.get("text") or "")
    lowered = text.lower()
    if "你在干什么" in text:
        return _make_fake_chat_writeback_model_decision(
            intent_kind="status-query",
            intent_confidence=0.98,
            intent_signals=["status-hint", "question"],
            blockers=["status-query"],
        )
    if (
        "讨论" in text
        or "分析一下当前问题" in text
        or "解释" in text
        or "discuss" in lowered
        or "just want to discuss" in lowered
    ):
        return _make_fake_chat_writeback_model_decision(
            intent_kind="discussion",
            intent_confidence=0.92,
            intent_signals=["discussion-hint"],
            blockers=["discussion-turn"],
        )
    if "批准补位" in text:
        return _make_fake_chat_writeback_model_decision(
            intent_kind="chat",
            intent_confidence=0.97,
            intent_signals=["team-gap-action", "approve"],
            team_role_gap_action="approve",
        )
    if "拒绝补位" in text:
        return _make_fake_chat_writeback_model_decision(
            intent_kind="chat",
            intent_confidence=0.97,
            intent_signals=["team-gap-action", "reject"],
            team_role_gap_action="reject",
        )
    if "下一步怎么做" in text or "接下来怎么做" in text:
        return _make_fake_chat_writeback_model_decision(
            intent_kind="chat",
            intent_confidence=0.88,
            intent_signals=["team-gap-notice"],
            team_role_gap_notice=True,
            blockers=["discussion-turn"],
        )
    if "确认继续" in text:
        surface = "desktop" if "桌面" in text or "desktop" in lowered else "browser"
        return _make_fake_chat_writeback_model_decision(
            intent_kind="execute-task",
            intent_confidence=0.94,
            intent_signals=["risky-confirmation"],
            risky_actuation_requested=True,
            risky_actuation_surface=surface,
            explicit_execution_confirmation=True,
            kickoff_allowed=True,
        )
    if "publish from the desktop client" in lowered or (
        "security settings" in lowered and "desktop app" in lowered
    ):
        return _make_fake_chat_writeback_model_decision(
            intent_kind="execute-task",
            intent_confidence=0.95,
            intent_signals=["risky-actuation", "desktop"],
            risky_actuation_requested=True,
            risky_actuation_surface="desktop",
        )
    if (
        "publish the post and save the security settings" in lowered
        or "publish the product" in lowered
        or "publish a new product" in lowered
        or "上架新商品" in text
        or "登录京东商家后台并上架新商品" in text
    ):
        return _make_fake_chat_writeback_model_decision(
            intent_kind="execute-task",
            intent_confidence=0.95,
            intent_signals=["risky-actuation", "browser"],
            risky_actuation_requested=True,
            risky_actuation_surface="browser",
        )
    if (
        "帮我运营这个小红书账号" in text
        or "小红书经营一个私域账号" in text
        or "现在开始调研竞品并给出结论" in text
        or "开始执行默认计划" in text
    ):
        return _make_fake_chat_writeback_model_decision(
            intent_kind="execute-task",
            intent_confidence=0.95,
            intent_signals=["execution-request"],
            kickoff_allowed=True,
            blockers=["execution-request"],
        )
    if "must include" in lowered and "weekly" in lowered:
        kickoff_allowed = "confirm and continue" in lowered
        return _make_fake_chat_writeback_model_decision(
            intent_kind="execute-task" if kickoff_allowed else "chat",
            intent_confidence=0.95 if kickoff_allowed else 0.82,
            intent_signals=["durable-instruction", "cadence-change"],
            should_writeback=True,
            approved_targets=["backlog", "schedule"],
            kickoff_allowed=kickoff_allowed,
            explicit_execution_confirmation=kickoff_allowed,
            operator_requirements=[text],
            switch_to_operator_guided=True,
            goal_title="specialist follow-up loop",
            goal_summary=text,
            goal_plan_steps=[
                "Assign the specialist follow-up loop to the proper owner.",
                "Define the review checkpoint and required evidence.",
                "Keep the loop active until the operator changes it again.",
            ],
            schedule_title="specialist follow-up review cadence",
            schedule_summary=f"Review the specialist follow-up loop weekly: {text}",
            schedule_cron="0 9 * * 1",
            schedule_prompt=(
                "Review the specialist follow-up loop against the formal instruction: "
                f"{text}."
            ),
        )
    if "保留下来" in text:
        return _make_fake_chat_writeback_model_decision(
            intent_kind="chat",
            intent_confidence=0.84,
            intent_signals=["durable-default"],
            should_writeback=True,
            approved_targets=["backlog"],
            operator_requirements=[text],
            goal_title="团队默认做法",
            goal_summary=text,
            goal_plan_steps=[
                "Record the operating default as a governed work item.",
                "Propagate it to the owning role and execution lane.",
                "Review evidence before treating it as the new baseline.",
            ],
        )
    if "改成" in text or "改为" in text:
        return _make_fake_chat_writeback_model_decision(
            intent_kind="chat",
            intent_confidence=0.88,
            intent_signals=["priority-change"],
            should_writeback=True,
            approved_targets=["strategy", "backlog"],
            operator_requirements=[text],
            priority_order=["先做现场验证", "再做规模复制"],
            switch_to_operator_guided=True,
            goal_title="现场验证主线",
            goal_summary=text,
            goal_plan_steps=[
                "Reorder the main loop around on-site verification.",
                "Delay scale-up until verification is complete.",
                "Write back evidence before expanding the rollout.",
            ],
        )
    return _make_fake_chat_writeback_model_decision(
        intent_kind="chat",
        intent_confidence=0.36,
        blockers=["model-deny"],
    )


async def _fake_chat_writeback_model_decision_async(**kwargs):
    return _fake_chat_writeback_model_decision(**kwargs)


def _make_attached_main_brain_intake_contract(
    *,
    text: str,
    decision=None,
):
    effective_decision = decision or _fake_chat_writeback_model_decision(text=text)
    contract = main_brain_intake_module.materialize_main_brain_intake_contract(
        message_text=text,
        decision=effective_decision,
    )
    assert contract is not None
    return contract


@pytest.fixture(autouse=True)
def patch_chat_writeback_model_gate(monkeypatch):
    monkeypatch.setattr(
        query_execution_shared_module,
        "_resolve_chat_writeback_model_decision",
        _fake_chat_writeback_model_decision_async,
    )
    monkeypatch.setattr(
        main_brain_intake_module,
        "_resolve_chat_writeback_model_decision",
        _fake_chat_writeback_model_decision_async,
    )
    monkeypatch.setattr(
        query_execution_runtime_module,
        "_resolve_chat_writeback_model_decision",
        _fake_chat_writeback_model_decision_async,
    )


class _FakeMemory:
    def __init__(self) -> None:
        self.deleted_ids: list[list[str]] = []
        self.content: list[tuple[object, object]] = []

    def delete(self, message_ids: list[str]) -> None:
        self.deleted_ids.append(list(message_ids))


class _FakeAgent:
    created: list["_FakeAgent"] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.console_enabled = True
        self.registered = False
        self.rebuilt = False
        self.interrupted = False
        self.messages = None
        self.memory = _FakeMemory()
        self.__class__.created.append(self)

    async def register_mcp_clients(self) -> None:
        self.registered = True

    def set_console_output_enabled(self, *, enabled: bool) -> None:
        self.console_enabled = enabled

    def rebuild_sys_prompt(self) -> None:
        self.rebuilt = True

    async def interrupt(self) -> None:
        self.interrupted = True

    def __call__(self, msgs):
        self.messages = msgs
        return "fake-agent-task"


class _FakeSessionBackend:
    def __init__(self) -> None:
        self.loaded: list[tuple[str, str]] = []
        self.saved: list[tuple[str, str]] = []
        self.saved_agents: list[object] = []

    async def load_session_state(self, *, session_id: str, user_id: str, agent) -> None:
        _ = agent
        self.loaded.append((session_id, user_id))

    async def save_session_state(self, *, session_id: str, user_id: str, agent) -> None:
        self.saved.append((session_id, user_id))
        self.saved_agents.append(agent)


class _FakeMCPManager:
    def __init__(self) -> None:
        self.requested_keys: list[str] = []
        self.get_clients_calls = 0
        self._clients = {
            "browser": SimpleNamespace(name="browser"),
            "other": SimpleNamespace(name="other"),
        }

    async def get_clients(self):
        self.get_clients_calls += 1
        return list(self._clients.values())

    async def get_client(self, key: str):
        self.requested_keys.append(key)
        return self._clients.get(key)


class _FakeAgentProfileService:
    def _ops_profile(self):
        return SimpleNamespace(
            agent_id="ops-agent",
            actor_key="industry:ops:execution-core",
            actor_fingerprint="fp-ops-v1",
            name="Ops Agent",
            role_name="Operations lead",
            role_summary="Owns runtime closeout.",
            mission="Turn the industry brief into an executable operating loop.",
            environment_constraints=["workspace draft/edit allowed", "browser research allowed"],
            evidence_expectations=["operating brief", "next-action recommendation"],
            current_focus_kind="goal",
            current_focus_id="goal-1",
            current_focus="Launch runtime center",
            current_task_id="task-1",
            industry_instance_id="industry-v1-ops",
            industry_role_id="execution-core",
        )

    def get_agent(self, agent_id: str):
        if agent_id != "ops-agent":
            return None
        return self._ops_profile()

    def list_agents(self):
        return [self._ops_profile()]


class _FakeCapabilityService:
    def __init__(self) -> None:
        self.executions: list[tuple[str, dict[str, object] | None]] = []

    def list_accessible_capabilities(self, *, agent_id: str | None, enabled_only: bool = False):
        _ = enabled_only
        assert agent_id in {"ops-agent", "ops-researcher", "copaw-agent-runner"}
        return [
            CapabilityMount(
                id="tool:browser_use",
                name="browser_use",
                summary="Browser automation.",
                kind="local-tool",
                source_kind="tool",
                risk_level="guarded",
                environment_requirements=["browser", "network"],
                evidence_contract=["browser-action"],
                role_access_policy=["all"],
                enabled=True,
            ),
            CapabilityMount(
                id="tool:edit_file",
                name="edit_file",
                summary="Edit a local file.",
                kind="local-tool",
                source_kind="tool",
                risk_level="auto",
                environment_requirements=["workspace"],
                evidence_contract=["file-write"],
                role_access_policy=["all"],
                enabled=True,
            ),
            CapabilityMount(
                id="tool:execute_shell_command",
                name="execute_shell_command",
                summary="Run a local shell command.",
                kind="local-tool",
                source_kind="tool",
                risk_level="guarded",
                environment_requirements=["workspace", "shell"],
                evidence_contract=["shell-command"],
                role_access_policy=["all"],
                enabled=True,
            ),
            CapabilityMount(
                id="tool:get_current_time",
                name="get_current_time",
                summary="Return the current time.",
                kind="local-tool",
                source_kind="tool",
                risk_level="auto",
                environment_requirements=[],
                evidence_contract=["call-record"],
                role_access_policy=["all"],
                enabled=True,
            ),
            CapabilityMount(
                id="tool:read_file",
                name="read_file",
                summary="Read a local file.",
                kind="local-tool",
                source_kind="tool",
                risk_level="auto",
                environment_requirements=["workspace"],
                evidence_contract=["file-read"],
                role_access_policy=["all"],
                enabled=True,
            ),
            CapabilityMount(
                id="tool:write_file",
                name="write_file",
                summary="Write a local file.",
                kind="local-tool",
                source_kind="tool",
                risk_level="auto",
                environment_requirements=["workspace"],
                evidence_contract=["file-write"],
                role_access_policy=["all"],
                enabled=True,
            ),
            CapabilityMount(
                id="skill:test-skill",
                name="test-skill",
                summary="Test skill.",
                kind="skill-bundle",
                source_kind="skill",
                risk_level="auto",
                environment_requirements=[],
                evidence_contract=["call-record"],
                role_access_policy=["operator"],
                enabled=True,
            ),
            CapabilityMount(
                id="mcp:browser",
                name="browser",
                summary="Browser MCP.",
                kind="remote-mcp",
                source_kind="mcp",
                risk_level="auto",
                environment_requirements=[],
                evidence_contract=["call-record"],
                role_access_policy=["mcp-enabled"],
                enabled=True,
            ),
            CapabilityMount(
                id="system:dispatch_query",
                name="dispatch_query",
                summary="Dispatch a focused sub-query.",
                kind="system-op",
                source_kind="system",
                risk_level="guarded",
                environment_requirements=[],
                evidence_contract=["kernel-task"],
                role_access_policy=["execution-core"],
                enabled=True,
            ),
            CapabilityMount(
                id="system:delegate_task",
                name="delegate_task",
                summary="Delegate a child task.",
                kind="system-op",
                source_kind="system",
                risk_level="guarded",
                environment_requirements=[],
                evidence_contract=["kernel-task"],
                role_access_policy=["execution-core"],
                enabled=True,
            ),
            CapabilityMount(
                id="system:dispatch_goal",
                name="dispatch_goal",
                summary="Compile and dispatch a goal.",
                kind="system-op",
                source_kind="system",
                risk_level="guarded",
                environment_requirements=[],
                evidence_contract=["kernel-task"],
                role_access_policy=["execution-core"],
                enabled=True,
            ),
            CapabilityMount(
                id="system:apply_role",
                name="apply_role",
                summary="Apply a governed role or capability update.",
                kind="system-op",
                source_kind="system",
                risk_level="guarded",
                environment_requirements=["kernel", "profile"],
                evidence_contract=["agent-profile-update"],
                role_access_policy=["execution-core"],
                enabled=True,
            ),
            CapabilityMount(
                id="system:discover_capabilities",
                name="discover_capabilities",
                summary="Discover governed capability candidates.",
                kind="system-op",
                source_kind="system",
                risk_level="auto",
                environment_requirements=["capability-graph"],
                evidence_contract=["capability-discovery"],
                role_access_policy=["all"],
                enabled=True,
            ),
        ]

    def get_capability(self, capability_id: str):
        for mount in self.list_accessible_capabilities(agent_id="ops-agent", enabled_only=True):
            if mount.id == capability_id:
                return mount
        return None

    def resolve_executor(self, capability_id: str):
        async def _executor(*, payload=None, **kwargs):
            _ = kwargs
            self.executions.append(
                (
                    capability_id,
                    payload if isinstance(payload, dict) else None,
                ),
            )
            return {
                "success": True,
                "summary": f"Executed {capability_id}",
                "payload": payload if isinstance(payload, dict) else {},
            }

        return _executor


class _FakeIndustryService:
    def get_instance_detail(self, instance_id: str):
        assert instance_id == "industry-v1-ops"
        return SimpleNamespace(
            label="Ops Industry Team",
            summary="Evidence-driven operations modernization loop.",
            execution_core_identity={
                "binding_id": "industry-v1-ops:execution-core",
                "agent_id": "copaw-agent-runner",
                "role_id": "execution-core",
                "industry_instance_id": "industry-v1-ops",
                "identity_label": "Ops Industry Team / 白泽执行中枢",
                "industry_label": "Ops Industry Team",
                "industry_summary": "Evidence-driven operations modernization loop.",
                "role_name": "白泽执行中枢",
                "role_summary": "Operate as the execution brain for this ops team.",
                "mission": "Turn the ops brief into the next coordinated move.",
                "thinking_axes": [
                    "Industry focus: Operations consulting",
                    "Channel lens: LinkedIn, Email",
                    "Operating goals: Launch pipeline",
                ],
                "environment_constraints": [
                    "workspace draft/edit allowed",
                    "browser research allowed",
                ],
                "allowed_capabilities": [
                    "system:dispatch_query",
                    "system:apply_role",
                    "tool:browser_use",
                ],
                "evidence_expectations": [
                    "operating brief",
                    "next-action recommendation",
                ],
            },
            goals=[
                {
                    "goal_id": "goal-1",
                    "title": "Launch runtime center",
                    "status": "active",
                    "owner_agent_id": "copaw-agent-runner",
                    "role_id": "execution-core",
                },
            ],
            agents=[
                {
                    "agent_id": "ops-agent",
                    "role_id": "execution-core",
                    "role_name": "Operations lead",
                    "mission": "Own the next operating move.",
                    "allowed_capabilities": [
                        "system:dispatch_query",
                        "system:apply_role",
                        "tool:browser_use",
                    ],
                    "current_focus": "Launch runtime center",
                },
                {
                    "agent_id": "ops-researcher",
                    "role_id": "researcher",
                    "role_name": "Ops Researcher",
                    "mission": "Collect operator and market signals.",
                    "allowed_capabilities": [
                        "system:dispatch_query",
                        "tool:browser_use",
                    ],
                    "current_focus": "Gather operator research",
                },
            ],
            profile=SimpleNamespace(
                industry="Operations consulting",
                company_name="Ops Co",
                product="Ops Suite",
                target_customers=["COO leaders", "RevOps teams"],
                channels=["LinkedIn", "Email"],
                goals=["Launch pipeline"],
                constraints=["No shell access"],
            ),
        )


class _FallbackStrategyMemoryService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def get_active_strategy(
        self,
        *,
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None = None,
    ):
        self.calls.append((scope_type, scope_id, owner_agent_id))
        if owner_agent_id != "copaw-agent-runner":
            return None
        return {
            "strategy_id": "strategy:industry:industry-v1-ops:copaw-agent-runner",
            "north_star": "Build a predictable operator pipeline",
            "summary": "Route work through the execution core before direct action.",
            "mission": "Keep the runtime center reliable while delegating the next concrete move.",
            "priority_order": [
                "Keep the runtime center stable",
                "Delegate concrete execution before doing it directly",
            ],
            "execution_constraints": [
                "Collect evidence before mutating operator state",
            ],
            "evidence_requirements": [
                "runtime center checkpoint",
                "operator evidence bundle",
            ],
        }


class _MutableStrategyMemoryService(_FallbackStrategyMemoryService):
    def __init__(self) -> None:
        super().__init__()
        self.payload = {
            "strategy_id": "strategy:industry:industry-v1-ops:copaw-agent-runner",
            "north_star": "Build a predictable operator pipeline",
            "summary": "Route work through the execution core before direct action.",
            "mission": "Keep the runtime center reliable while delegating the next concrete move.",
            "priority_order": [
                "Keep the runtime center stable",
            ],
            "execution_constraints": [
                "Collect evidence before mutating operator state",
            ],
            "evidence_requirements": [
                "runtime center checkpoint",
            ],
            "metadata": {},
        }

    def get_active_strategy(
        self,
        *,
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None = None,
    ):
        self.calls.append((scope_type, scope_id, owner_agent_id))
        if owner_agent_id != "copaw-agent-runner":
            return None
        return dict(self.payload)

    def upsert_strategy(self, record):
        if isinstance(record, dict):
            self.payload = dict(record)
        else:
            self.payload = dict(record.model_dump(mode="json"))
        return dict(self.payload)


class _ChatWritebackIndustryService(_FakeIndustryService):
    def __init__(self, strategy_memory_service: _MutableStrategyMemoryService) -> None:
        self._strategy_memory_service = strategy_memory_service
        self.calls: list[tuple[str, str, str | None]] = []
        self.received_writeback_fingerprints: list[str | None] = []

    async def apply_execution_chat_writeback(
        self,
        *,
        industry_instance_id: str,
        message_text: str,
        owner_agent_id: str | None = None,
        session_id: str | None = None,
        channel: str | None = None,
        writeback_plan=None,
    ) -> dict[str, object]:
        _ = session_id, channel
        self.calls.append((industry_instance_id, message_text, owner_agent_id))
        self.received_writeback_fingerprints.append(
            getattr(writeback_plan, "fingerprint", None),
        )
        payload = dict(self._strategy_memory_service.payload)
        payload["priority_order"] = [
            "先做现场验证",
            "再做规模复制",
            *list(payload.get("priority_order") or []),
        ]
        payload["metadata"] = {
            **dict(payload.get("metadata") or {}),
            "operator_requirements": [message_text],
        }
        self._strategy_memory_service.upsert_strategy(payload)
        return {
            "applied": True,
            "strategy_updated": True,
            "created_schedule_titles": ["现场验证例行节奏"],
        }


class _KickoffIndustryService(_FakeIndustryService):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    async def kickoff_execution_from_chat(
        self,
        *,
        industry_instance_id: str,
        message_text: str,
        owner_agent_id: str | None = None,
        session_id: str | None = None,
        channel: str | None = None,
    ) -> dict[str, object]:
        _ = session_id, channel
        self.calls.append((industry_instance_id, message_text, owner_agent_id))
        return {
            "activated": True,
            "started_assignment_titles": ["default kickoff assignment"],
        }


class _KickoffAwareIndustryService(_FakeIndustryService):
    def __init__(self, strategy_memory_service: _MutableStrategyMemoryService) -> None:
        self._strategy_memory_service = strategy_memory_service
        self.call_order: list[str] = []
        self.writeback_calls: list[tuple[str, str, str | None]] = []
        self.kickoff_calls: list[tuple[str, str, str | None, list[str]]] = []
        self.received_writeback_fingerprints: list[str | None] = []

    async def apply_execution_chat_writeback(
        self,
        *,
        industry_instance_id: str,
        message_text: str,
        owner_agent_id: str | None = None,
        session_id: str | None = None,
        channel: str | None = None,
        writeback_plan=None,
    ) -> dict[str, object]:
        _ = session_id, channel
        self.call_order.append("writeback")
        self.writeback_calls.append((industry_instance_id, message_text, owner_agent_id))
        self.received_writeback_fingerprints.append(
            getattr(writeback_plan, "fingerprint", None),
        )
        payload = dict(self._strategy_memory_service.payload)
        payload["priority_order"] = [
            "verify on site first",
            "scale after verification",
            *list(payload.get("priority_order") or []),
        ]
        payload["metadata"] = {
            **dict(payload.get("metadata") or {}),
            "operator_requirements": [message_text],
        }
        self._strategy_memory_service.upsert_strategy(payload)
        return {
            "applied": True,
            "strategy_updated": True,
            "created_schedule_titles": ["follow-up cadence"],
        }

    async def kickoff_execution_from_chat(
        self,
        *,
        industry_instance_id: str,
        message_text: str,
        owner_agent_id: str | None = None,
        session_id: str | None = None,
        channel: str | None = None,
    ) -> dict[str, object]:
        _ = session_id, channel
        self.call_order.append("kickoff")
        self.kickoff_calls.append(
            (
                industry_instance_id,
                message_text,
                owner_agent_id,
                list(self._strategy_memory_service.payload.get("priority_order") or []),
            ),
        )
        return {
            "activated": True,
            "started_assignment_titles": ["default kickoff assignment"],
        }


class _FakePredictionService:
    def __init__(
        self,
        *,
        recommendation: dict[str, object] | None = None,
        execution_result: dict[str, object] | None = None,
    ) -> None:
        self.recommendation = dict(
            recommendation
            or {
                "case_id": "case-team-gap-1",
                "recommendation_id": "rec-team-gap-1",
                "suggested_role_name": "视觉设计专员",
                "summary": "当前团队缺少长期承接视觉资产生产的岗位。",
                "status": "proposed",
                "decision_request_id": None,
                "workflow_title": "Visual asset delivery",
            }
        )
        self.execution_result = dict(
            execution_result
            or {
                "execution": {
                    "phase": "waiting-confirm",
                    "summary": "补位建议已进入待批复。",
                    "decision_request_id": "decision-team-gap-1",
                },
                "decision": {
                    "id": "decision-team-gap-1",
                    "status": "open",
                },
            }
        )
        self.lookup_calls: list[str] = []
        self.execute_calls: list[tuple[str, str, str]] = []
        self.reject_calls: list[tuple[str, str, str, str | None]] = []

    def get_active_team_role_gap_recommendation(
        self,
        *,
        industry_instance_id: str,
    ) -> dict[str, object] | None:
        self.lookup_calls.append(industry_instance_id)
        return dict(self.recommendation)

    async def execute_recommendation(
        self,
        case_id: str,
        recommendation_id: str,
        *,
        actor: str = "copaw-operator",
    ) -> dict[str, object]:
        self.execute_calls.append((case_id, recommendation_id, actor))
        execution_payload = (
            self.execution_result.get("execution")
            if isinstance(self.execution_result.get("execution"), dict)
            else {}
        )
        decision_id = execution_payload.get("decision_request_id")
        if isinstance(decision_id, str) and decision_id.strip():
            self.recommendation["decision_request_id"] = decision_id
            self.recommendation["status"] = "waiting-confirm"
        return dict(self.execution_result)

    def reject_recommendation(
        self,
        case_id: str,
        recommendation_id: str,
        *,
        actor: str = "copaw-operator",
        summary: str | None = None,
    ) -> dict[str, object]:
        self.reject_calls.append((case_id, recommendation_id, actor, summary))
        self.recommendation["status"] = "rejected"
        return {"case_id": case_id, "recommendation_id": recommendation_id}


class _FakeDecisionDispatcher:
    def __init__(self) -> None:
        self.approve_calls: list[tuple[str, str | None, bool | None]] = []
        self.reject_calls: list[tuple[str, str | None]] = []
        self.lifecycle = SimpleNamespace(get_task=lambda task_id: None)

    async def approve_decision(
        self,
        decision_id: str,
        *,
        resolution: str | None = None,
        execute: bool | None = None,
    ) -> dict[str, object]:
        self.approve_calls.append((decision_id, resolution, execute))
        return {
            "decision_request_id": decision_id,
            "task_id": "task-team-gap-1",
            "summary": "补位已批准并进入正式团队主链。",
        }

    def reject_decision(
        self,
        decision_id: str,
        *,
        resolution: str | None = None,
    ) -> dict[str, object]:
        self.reject_calls.append((decision_id, resolution))
        return {
            "decision_request_id": decision_id,
            "summary": "补位已拒绝。",
        }


class _FakeKnowledgeService:
    def retrieve(self, *, query: str, role: str | None = None, limit: int = 5):
        _ = limit
        if "plan the next move" not in query:
            return []
        return [
            SimpleNamespace(
                id="knowledge-1",
                document_id="knowledge-doc:ops",
                title="Ops SOP",
                summary="Review evidence before acting.",
                source_ref="workspace:OPS.md",
            ),
        ]

    def retrieve_memory(
        self,
        *,
        query: str,
        role: str | None = None,
        scope_type: str | None = None,
        scope_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        industry_instance_id: str | None = None,
        global_scope_id: str | None = None,
        work_context_id: str | None = None,
        include_related_scopes: bool = True,
        limit: int = 5,
        **_: object,
    ):
        _ = (
            role,
            scope_type,
            scope_id,
            task_id,
            industry_instance_id,
            global_scope_id,
            work_context_id,
            include_related_scopes,
            limit,
        )
        if "plan the next move" not in query:
            return []
        if scope_type == "task" and scope_id == "task-123":
            return [
                SimpleNamespace(
                    id="memory-task-1",
                    document_id="memory:task:task-123",
                    title="Task thread rule",
                    summary="Only use this task thread's memory when continuing the task.",
                    source_ref=None,
                ),
            ]
        if agent_id != "ops-agent":
            return []
        return [
            SimpleNamespace(
                id="memory-1",
                document_id="memory:agent:ops-agent",
                title="Customer rule",
                summary="ACME requires execution-core review before outbound changes.",
                source_ref=None,
            ),
        ]


class _FakeKernelResult:
    def __init__(
        self,
        *,
        task_id: str,
        phase: str,
        success: bool,
        summary: str,
    ) -> None:
        self.task_id = task_id
        self.phase = phase
        self.success = success
        self.summary = summary

    def model_dump(self, mode: str = "json") -> dict[str, object]:
        _ = mode
        return {
            "task_id": self.task_id,
            "phase": self.phase,
            "success": self.success,
            "summary": self.summary,
        }


class _FakeKernelDispatcher:
    def __init__(self) -> None:
        self.submitted = []
        self.executed: list[str] = []

    def submit(self, task):
        self.submitted.append(task)
        return _FakeKernelResult(
            task_id=task.id,
            phase="executing",
            success=True,
            summary="Task admitted to the kernel and is ready for execution.",
        )

    async def execute_task(self, task_id: str):
        self.executed.append(task_id)
        return _FakeKernelResult(
            task_id=task_id,
            phase="completed",
            success=True,
            summary=f"Executed {task_id}",
        )


def _build_real_kernel_dispatcher(tmp_path):
    state_store = SQLiteStateStore(tmp_path / "query-preflight.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(state_store)
    decision_repository = SqliteDecisionRequestRepository(state_store)
    governance_control_repository = SqliteGovernanceControlRepository(state_store)
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_repository,
    )
    dispatcher = KernelDispatcher(task_store=task_store)
    return (
        dispatcher,
        task_repository,
        decision_repository,
        governance_control_repository,
    )


async def _fake_stream_printing_messages(*, agents, coroutine_task):
    _ = agents
    _ = coroutine_task
    yield SimpleNamespace(id="msg-1"), False
    yield SimpleNamespace(id="msg-2"), True


async def _slow_stream_printing_messages(*, agents, coroutine_task):
    _ = agents
    _ = coroutine_task
    await asyncio.sleep(0.05)
    yield SimpleNamespace(id="msg-slow"), True


__all__ = [name for name in globals() if not name.startswith("__")]


