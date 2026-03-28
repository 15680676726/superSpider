# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib

from ..evidence import EvidenceRecord
from ..providers import ProviderManager
from .main_brain_intake import (
    build_industry_chat_action_kwargs,
    normalize_main_brain_runtime_context,
    resolve_execution_core_industry_instance_id,
    resolve_request_main_brain_intake_contract,
    resolve_request_main_brain_intake_contract_sync,
)
from .query_execution_shared import *  # noqa: F401,F403


def CoPawAgent(*args, **kwargs):
    module = importlib.import_module("copaw.kernel.query_execution")
    return module.CoPawAgent(*args, **kwargs)


def load_config(*args, **kwargs):
    module = importlib.import_module("copaw.kernel.query_execution")
    return module.load_config(*args, **kwargs)


def stream_printing_messages(*args, **kwargs):
    module = importlib.import_module("copaw.kernel.query_execution")
    return module.stream_printing_messages(*args, **kwargs)


_EXECUTION_CORE_ALLOWED_LOCAL_TOOL_CAPABILITY_IDS = {
    "tool:edit_file",
    "tool:execute_shell_command",
    "tool:get_current_time",
    "tool:read_file",
    "tool:write_file",
}


class _QueryExecutionRuntimeMixin:
    def __init__(
        self,
        *,
        session_backend: Any,
        memory_manager: MemoryManager | None = None,
        mcp_manager: Any | None = None,
        tool_bridge: Any | None = None,
        environment_service: Any | None = None,
        capability_service: Any | None = None,
        kernel_dispatcher: Any | None = None,
        agent_profile_service: Any | None = None,
        delegation_service: Any | None = None,
        industry_service: Any | None = None,
        strategy_memory_service: Any | None = None,
        prediction_service: Any | None = None,
        knowledge_service: Any | None = None,
        memory_recall_service: Any | None = None,
        actor_mailbox_service: Any | None = None,
        agent_runtime_repository: Any | None = None,
        governance_control_repository: Any | None = None,
        task_repository: Any | None = None,
        task_runtime_repository: Any | None = None,
        evidence_ledger: Any | None = None,
        provider_manager: Any | None = None,
        lease_heartbeat_interval_seconds: float = 15.0,
    ) -> None:
        self._session_backend = session_backend
        self._memory_manager = memory_manager
        self._mcp_manager = mcp_manager
        self._tool_bridge = tool_bridge
        self._environment_service = environment_service
        self._capability_service = capability_service
        self._kernel_dispatcher = kernel_dispatcher
        self._agent_profile_service = agent_profile_service
        self._delegation_service = delegation_service
        self._industry_service = industry_service
        self._strategy_memory_service = strategy_memory_service
        self._prediction_service = prediction_service
        self._knowledge_service = knowledge_service
        self._memory_recall_service = memory_recall_service
        self._actor_mailbox_service = actor_mailbox_service
        self._agent_runtime_repository = agent_runtime_repository
        self._governance_control_repository = governance_control_repository
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._evidence_ledger = evidence_ledger
        self._provider_manager = provider_manager
        self._lease_heartbeat_interval_seconds = max(
            0.01,
            float(lease_heartbeat_interval_seconds),
        )
        self._resident_agents: dict[str, _ResidentQueryAgent] = {}
        self._resident_agent_cache_lock = asyncio.Lock()
        self._interactive_actor_locks: dict[str, asyncio.Lock] = {}

    def resolve_request_owner_agent_id(self, *, request: Any) -> str:
        owner_agent_id, _profile = self._resolve_query_agent_profile(request=request)
        return owner_agent_id

    def set_session_backend(self, session_backend: Any) -> None:
        self._session_backend = session_backend

    def set_memory_manager(self, memory_manager: MemoryManager | None) -> None:
        self._memory_manager = memory_manager

    def set_mcp_manager(self, mcp_manager: Any | None) -> None:
        self._mcp_manager = mcp_manager

    def set_tool_bridge(self, tool_bridge: Any | None) -> None:
        self._tool_bridge = tool_bridge

    def set_environment_service(self, environment_service: Any | None) -> None:
        self._environment_service = environment_service

    def set_capability_service(self, capability_service: Any | None) -> None:
        self._capability_service = capability_service

    def set_kernel_dispatcher(self, kernel_dispatcher: Any | None) -> None:
        self._kernel_dispatcher = kernel_dispatcher

    def set_agent_profile_service(self, agent_profile_service: Any | None) -> None:
        self._agent_profile_service = agent_profile_service

    def set_delegation_service(self, delegation_service: Any | None) -> None:
        self._delegation_service = delegation_service

    def set_industry_service(self, industry_service: Any | None) -> None:
        self._industry_service = industry_service

    def set_strategy_memory_service(self, strategy_memory_service: Any | None) -> None:
        self._strategy_memory_service = strategy_memory_service

    def set_prediction_service(self, prediction_service: Any | None) -> None:
        self._prediction_service = prediction_service

    def set_knowledge_service(self, knowledge_service: Any | None) -> None:
        self._knowledge_service = knowledge_service

    def set_memory_recall_service(self, memory_recall_service: Any | None) -> None:
        self._memory_recall_service = memory_recall_service

    def set_actor_mailbox_service(self, actor_mailbox_service: Any | None) -> None:
        self._actor_mailbox_service = actor_mailbox_service

    def set_agent_runtime_repository(self, agent_runtime_repository: Any | None) -> None:
        self._agent_runtime_repository = agent_runtime_repository

    def set_governance_control_repository(
        self,
        governance_control_repository: Any | None,
    ) -> None:
        self._governance_control_repository = governance_control_repository

    def set_task_repository(self, task_repository: Any | None) -> None:
        self._task_repository = task_repository

    def set_task_runtime_repository(self, task_runtime_repository: Any | None) -> None:
        self._task_runtime_repository = task_runtime_repository

    def set_evidence_ledger(self, evidence_ledger: Any | None) -> None:
        self._evidence_ledger = evidence_ledger

    def _build_governance_control_record(
        self,
        *,
        existing_control: GovernanceControlRecord | None,
        metadata: dict[str, Any],
        updated_at: datetime,
    ) -> GovernanceControlRecord:
        if existing_control is None:
            return GovernanceControlRecord(
                id="runtime",
                metadata=metadata,
                updated_at=updated_at,
            )
        return GovernanceControlRecord(
            id=_first_non_empty(getattr(existing_control, "id", None), "runtime") or "runtime",
            emergency_stop_active=bool(
                getattr(existing_control, "emergency_stop_active", False),
            ),
            emergency_reason=getattr(existing_control, "emergency_reason", None),
            emergency_actor=getattr(existing_control, "emergency_actor", None),
            paused_schedule_ids=list(
                getattr(existing_control, "paused_schedule_ids", []) or [],
            ),
            channel_shutdown_applied=bool(
                getattr(existing_control, "channel_shutdown_applied", False),
            ),
            metadata=metadata,
            created_at=getattr(existing_control, "created_at", updated_at),
            updated_at=updated_at,
        )

    async def execute_stream(
        self,
        *,
        msgs: list[Any],
        request: Any,
        kernel_task_id: str | None = None,
        transient_input_message_ids: set[str] | None = None,
    ) -> AsyncIterator[tuple[Msg, bool]]:
        session_id = request.session_id
        user_id = request.user_id
        channel = getattr(request, "channel", DEFAULT_CHANNEL)
        logger.info(
            "Execute kernel query:\n%s",
            json.dumps(
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "channel": channel,
                    "msgs_len": len(msgs) if msgs else 0,
                    "msgs_str": str(msgs)[:300] + "...",
                    "kernel_task_id": kernel_task_id,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        owner_agent_id, agent_profile = self._resolve_query_agent_profile(
            request=request,
        )
        actor_lock = self._interactive_actor_locks.setdefault(
            owner_agent_id,
            asyncio.Lock(),
        )
        async with actor_lock:
            async for msg, last in self._execute_stream_locked(
                msgs=msgs,
                request=request,
                kernel_task_id=kernel_task_id,
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
                transient_input_message_ids=transient_input_message_ids,
            ):
                yield msg, last

    async def _execute_stream_locked(
        self,
        *,
        msgs: list[Any],
        request: Any,
        kernel_task_id: str | None,
        session_id: str,
        user_id: str,
        channel: str,
        owner_agent_id: str,
        agent_profile: Any | None,
        transient_input_message_ids: set[str] | None,
    ) -> AsyncIterator[tuple[Msg, bool]]:
        agent = None
        lease = None
        actor_lease = None
        session_state_loaded = False
        final_summary: str | None = None
        final_error: str | None = None
        stream_step_count = 0
        execution_context: dict[str, Any] = {}
        resident_key = self._resident_agent_cache_key(
            channel=channel,
            session_id=session_id,
            user_id=user_id,
            owner_agent_id=owner_agent_id,
        )

        try:
            env_context = build_env_context(
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                working_dir=str(WORKING_DIR),
            )
            execution_context = self._resolve_execution_task_context(
                request=request,
                agent_id=owner_agent_id,
                kernel_task_id=kernel_task_id,
                conversation_thread_id=session_id,
            )
            self._mark_actor_query_started(
                agent_id=owner_agent_id,
                task_id=kernel_task_id,
                session_id=session_id,
                user_id=user_id,
                conversation_thread_id=session_id,
                channel=channel,
                execution_context=execution_context,
            )
            try:
                actor_lease = self._acquire_actor_runtime_lease(
                    agent_id=owner_agent_id,
                    task_id=kernel_task_id,
                    conversation_thread_id=session_id,
                )
            except RuntimeError as exc:
                lowered = str(exc).lower()
                if "already leased by" in lowered:
                    busy_msg = Msg(
                        name="Spider Mesh",
                        role="assistant",
                        content=[
                            TextBlock(
                                type="text",
                                text=(
                                    "**执行编排暂时不可用（执行位正忙）**\n\n"
                                    "- 当前执行核正在处理其它任务，为避免环境/会话冲突，本轮无法进入执行编排。\n"
                                    "- 建议：等待当前执行完成后再重试；或在 AgentWorkbench / 运行面板里停止正在执行的任务后再发起。"
                                ),
                            )
                        ],
                    )
                    final_summary = _message_preview(busy_msg)
                    final_error = "actor_runtime_busy"
                    yield busy_msg, True
                    return
                raise
            self._assert_bound_chat_context(
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
            )
            (
                tool_capability_ids,
                skill_names,
                mcp_client_keys,
                system_capability_ids,
                desktop_actuation_available,
            ) = self._resolve_query_capability_context(owner_agent_id)
            (
                tool_capability_ids,
                skill_names,
                mcp_client_keys,
                system_capability_ids,
                desktop_actuation_available,
            ) = self._prune_execution_core_control_capability_context(
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
                tool_capability_ids=tool_capability_ids,
                skill_names=skill_names,
                mcp_client_keys=mcp_client_keys,
                system_capability_ids=system_capability_ids,
                desktop_actuation_available=desktop_actuation_available,
            )
            delegation_guard = self._resolve_delegation_first_guard(
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
                system_capability_ids=system_capability_ids,
            )
            team_role_gap_action_result = await self._handle_team_role_gap_chat_action(
                msgs=msgs,
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
            )
            if team_role_gap_action_result is not None:
                final_summary = _message_preview(team_role_gap_action_result)
                yield team_role_gap_action_result, True
                return
            team_role_gap_notice = self._build_team_role_gap_notice_message(
                msgs=msgs,
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
            )
            if team_role_gap_notice is not None:
                final_summary = _message_preview(team_role_gap_notice)
                yield team_role_gap_notice, True
                return
            chat_writeback_summary, industry_kickoff_summary = await self._apply_requested_main_brain_intake(
                msgs=msgs,
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
            )
            team_role_gap_summary = self._resolve_active_team_role_gap_summary(
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
            )
            mounted_capabilities = _merged_capability_ids(
                tool_capability_ids=tool_capability_ids,
                skill_names=skill_names,
                mcp_client_keys=mcp_client_keys,
                system_capability_ids=system_capability_ids,
            )
            prompt_appendix = self._build_profile_prompt_appendix(
                request=request,
                msgs=msgs,
                owner_agent_id=owner_agent_id,
                kernel_task_id=kernel_task_id,
                agent_profile=agent_profile,
                mounted_capabilities=mounted_capabilities,
                desktop_actuation_available=desktop_actuation_available,
                execution_context=execution_context,
                delegation_guard=delegation_guard,
                industry_kickoff_summary=industry_kickoff_summary,
                chat_writeback_summary=chat_writeback_summary,
                team_role_gap_summary=team_role_gap_summary,
            )
            system_tool_functions = self._build_system_tool_functions(
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
                system_capability_ids=system_capability_ids,
                kernel_task_id=kernel_task_id,
                delegation_guard=delegation_guard,
            )

            mcp_clients = []
            if self._mcp_manager is not None:
                if mcp_client_keys is None:
                    mcp_clients = await self._mcp_manager.get_clients()
                else:
                    for client_key in mcp_client_keys:
                        client = await self._mcp_manager.get_client(client_key)
                        if client is not None:
                            mcp_clients.append(client)

            config = load_config()
            resident_signature = self._resident_agent_signature(
                owner_agent_id=owner_agent_id,
                actor_key=_field_value(agent_profile, "actor_key"),
                actor_fingerprint=_field_value(agent_profile, "actor_fingerprint"),
                prompt_appendix=prompt_appendix,
                tool_capability_ids=tool_capability_ids,
                skill_names=skill_names,
                mcp_client_keys=mcp_client_keys,
                system_capability_ids=system_capability_ids,
            )
            resident = await self._get_or_create_resident_agent(
                cache_key=resident_key,
                signature=resident_signature,
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                owner_agent_id=owner_agent_id,
                create_agent=lambda: CoPawAgent(
                    env_context=env_context,
                    prompt_appendix=prompt_appendix,
                    mcp_clients=mcp_clients,
                    memory_manager=self._memory_manager,
                    max_iters=config.agents.running.max_iters,
                    max_input_length=config.agents.running.max_input_length,
                    allowed_tool_capability_ids=tool_capability_ids,
                    allowed_skill_names=skill_names,
                    extra_tool_functions=system_tool_functions,
                ),
            )
            agent = resident.agent
            session_state_loaded = True

            if self._environment_service is not None:
                try:
                    lease = self._environment_service.acquire_session_lease(
                        channel=channel,
                        session_id=session_id,
                        user_id=user_id,
                        owner=owner_agent_id,
                        handle={
                            "channel": channel,
                            "session_id": session_id,
                            "user_id": user_id,
                            "task_id": kernel_task_id,
                        },
                        metadata={
                            "channel": channel,
                            "session_id": session_id,
                            "user_id": user_id,
                            "conversation_thread_id": session_id,
                            "kernel_task_id": kernel_task_id,
                            "owner_agent_id": owner_agent_id,
                        },
                    )
                except Exception:
                    logger.exception("Environment session lease failed")

            self._record_query_checkpoint(
                agent_id=owner_agent_id,
                task_id=kernel_task_id,
                session_id=session_id,
                user_id=user_id,
                conversation_thread_id=session_id,
                channel=channel,
                phase="query-loaded",
                checkpoint_kind="resume",
                status="ready",
                summary="已加载交互查询轮次的会话状态",
                execution_context=execution_context,
                snapshot_payload={
                    "session_state_loaded": True,
                },
            )
            agent.rebuild_sys_prompt()

            heartbeat = self._build_query_lease_heartbeat(
                session_lease=lease,
                actor_lease=actor_lease,
            )
            tool_preflight = self._build_tool_preflight(
                delegation_guard=delegation_guard,
                msgs=msgs,
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
                kernel_task_id=kernel_task_id,
            )
            with bind_reasoning_tool_choice_resolver(
                lambda: (
                    "required"
                    if delegation_guard is not None and delegation_guard.locked
                    else None
                ),
            ):
                with bind_tool_preflight(tool_preflight):
                    with bind_shell_evidence_sink(self._make_shell_evidence_sink(kernel_task_id)):
                        with bind_file_evidence_sink(self._make_file_evidence_sink(kernel_task_id)):
                            with bind_browser_evidence_sink(
                                self._make_browser_evidence_sink(kernel_task_id),
                            ):
                                if heartbeat is None:
                                    async for msg, last in stream_printing_messages(
                                        agents=[agent],
                                        coroutine_task=agent(msgs),
                                    ):
                                        stream_step_count += 1
                                        final_summary = _message_preview(msg) or final_summary
                                        self._record_query_checkpoint(
                                            agent_id=owner_agent_id,
                                            task_id=kernel_task_id,
                                            session_id=session_id,
                                            user_id=user_id,
                                            conversation_thread_id=session_id,
                                            channel=channel,
                                            phase="query-streaming",
                                            checkpoint_kind="worker-step",
                                            status="ready",
                                            summary=final_summary or f"流式输出第 {stream_step_count} 条消息",
                                            execution_context=execution_context,
                                            stream_step_count=stream_step_count,
                                            snapshot_payload={
                                                "last_message_preview": final_summary,
                                                "last_message_is_terminal": last,
                                            },
                                        )
                                        yield msg, last
                                else:
                                    async with heartbeat:
                                        async for msg, last in stream_printing_messages(
                                            agents=[agent],
                                            coroutine_task=agent(msgs),
                                        ):
                                            stream_step_count += 1
                                            await heartbeat.pulse()
                                            final_summary = _message_preview(msg) or final_summary
                                            self._record_query_checkpoint(
                                                agent_id=owner_agent_id,
                                                task_id=kernel_task_id,
                                                session_id=session_id,
                                                user_id=user_id,
                                                conversation_thread_id=session_id,
                                                channel=channel,
                                                phase="query-streaming",
                                                checkpoint_kind="worker-step",
                                                status="ready",
                                                summary=final_summary or f"流式输出第 {stream_step_count} 条消息",
                                                execution_context=execution_context,
                                                stream_step_count=stream_step_count,
                                                snapshot_payload={
                                                    "last_message_preview": final_summary,
                                                    "last_message_is_terminal": last,
                                                },
                                            )
                                            yield msg, last
        except asyncio.CancelledError:
            final_error = "任务已取消。"
            if agent is not None:
                await agent.interrupt()
            self._resident_agents.pop(resident_key, None)
            raise
        except Exception as exc:
            final_error = str(exc)
            self._resident_agents.pop(resident_key, None)
            raise
        finally:
            if agent is not None and session_state_loaded:
                await self._prune_transient_messages(
                    agent=agent,
                    message_ids=transient_input_message_ids,
                )
                await self._session_backend.save_session_state(
                    session_id=session_id,
                    user_id=user_id,
                    agent=agent,
                )

            if lease is not None and self._environment_service is not None:
                self._environment_service.release_session_lease(
                    lease.id,
                    lease_token=lease.lease_token,
                    reason="query turn completed",
                )
            self._release_actor_runtime_lease(actor_lease)
            self._mark_actor_query_finished(
                agent_id=owner_agent_id,
                task_id=kernel_task_id,
                session_id=session_id,
                user_id=user_id,
                conversation_thread_id=session_id,
                channel=channel,
                summary=final_summary,
                error=final_error,
                execution_context=execution_context,
                stream_step_count=stream_step_count,
            )

    async def resume_query_tool_confirmation(
        self,
        *,
        decision_request_id: str,
    ) -> dict[str, Any]:
        match = self._load_query_tool_confirmation_context(
            decision_request_id=decision_request_id,
        )
        if match is None:
            return {
                "resumed": False,
                "reason": "decision_not_query_tool_confirmation",
            }

        request_context = match["request_context"]
        query_text = match["query_text"]
        owner_agent_id = match["owner_agent_id"]
        tool_name = _first_non_empty(match.get("tool_name"))
        workflow_label = _risky_tool_workflow_label(tool_name)
        surface_label = _risky_tool_surface_label(tool_name)
        request = _build_query_resume_request(
            request_context=request_context,
            owner_agent_id=owner_agent_id,
        )
        dispatcher = self._kernel_dispatcher
        kernel_task_id: str | None = None
        managed_by_kernel_dispatcher = False
        control_msg = Msg(
            name="runtime-center",
            role="user",
            content=(
                f"系统已批准，确认继续执行刚才被确认门拦住的{workflow_label}。"
                + (f" 原请求：{query_text}" if query_text else "")
                + " 请直接从当前会话继续执行，不要再次请求确认，也不要重新解释审批要求。"
            ),
            metadata={
                "decision_request_id": decision_request_id,
                "transient": True,
                "resume_kind": "query-tool-confirmation",
            },
        )
        final_summary: str | None = None
        stream_events = 0
        if dispatcher is not None:
            admitted = dispatcher.submit(
                KernelTask(
                    title=query_text or f"Resume approved query tool confirmation {decision_request_id}",
                    capability_ref="system:dispatch_query",
                    environment_ref=f"session:{request.channel}:{request.session_id}",
                    owner_agent_id=owner_agent_id,
                    risk_level="auto",
                    payload={
                        "request": request_context,
                        "request_context": dict(request_context),
                        "channel": request.channel,
                        "user_id": request.user_id,
                        "session_id": request.session_id,
                        "dispatch_events": False,
                        "resume_source_decision_id": decision_request_id,
                        "resume_kind": "query-tool-confirmation",
                        "query_preview": query_text,
                    },
                ),
            )
            kernel_task_id = _first_non_empty(getattr(admitted, "task_id", None))
            managed_by_kernel_dispatcher = getattr(admitted, "phase", None) == "executing"
            if kernel_task_id is None:
                return {
                    "resumed": False,
                    "reason": "resume_task_admission_missing_task_id",
                    "decision_request_id": decision_request_id,
                }
            if getattr(admitted, "phase", None) != "executing":
                return {
                    "resumed": False,
                    "reason": "resume_task_not_executing",
                    "decision_request_id": decision_request_id,
                    "task_id": kernel_task_id,
                    "phase": getattr(admitted, "phase", None),
                    "summary": getattr(admitted, "summary", None),
                }
        try:
            async for msg, _last in self.execute_stream(
                msgs=[control_msg],
                request=request,
                kernel_task_id=kernel_task_id,
                transient_input_message_ids={control_msg.id},
            ):
                stream_events += 1
                final_summary = _message_preview(msg) or final_summary
        except Exception:
            if managed_by_kernel_dispatcher and kernel_task_id is not None and dispatcher is not None:
                try:
                    dispatcher.fail_task(
                        kernel_task_id,
                        error=f"已批准的{surface_label}续跑失败。",
                    )
                except Exception:
                    logger.exception(
                        "Failed to record query-tool-confirmation resume failure for %s",
                        decision_request_id,
                    )
            raise
        if managed_by_kernel_dispatcher and kernel_task_id is not None and dispatcher is not None:
            try:
                dispatcher.complete_task(
                    kernel_task_id,
                    summary=final_summary or "Approved query tool confirmation resumed",
                    metadata={
                        "source": "query-tool-confirmation-resume",
                        "decision_request_id": decision_request_id,
                    },
                )
            except Exception:
                logger.exception(
                    "Failed to complete query-tool-confirmation resume task for %s",
                    decision_request_id,
                )
        return {
            "resumed": True,
            "decision_request_id": decision_request_id,
            "owner_agent_id": owner_agent_id,
            "session_id": request.session_id,
            "channel": getattr(request, "channel", DEFAULT_CHANNEL),
            "task_id": kernel_task_id,
            "stream_events": stream_events,
            "summary": final_summary or "query tool confirmation resumed",
        }

    async def _get_or_create_resident_agent(
        self,
        *,
        cache_key: str,
        signature: str,
        session_id: str,
        user_id: str,
        channel: str,
        owner_agent_id: str,
        create_agent,
    ) -> _ResidentQueryAgent:
        async with self._resident_agent_cache_lock:
            cached = self._resident_agents.get(cache_key)
            if cached is not None and cached.signature == signature:
                cached.agent.rebuild_sys_prompt()
                return cached
            agent = create_agent()
            await agent.register_mcp_clients()
            agent.set_console_output_enabled(enabled=False)
            try:
                await self._session_backend.load_session_state(
                    session_id=session_id,
                    user_id=user_id,
                    agent=agent,
                )
            except KeyError as exc:
                logger.warning(
                    "load_session_state skipped (state schema mismatch): %s; "
                    "will save fresh state on completion to recover file",
                    exc,
                )
            resident = _ResidentQueryAgent(
                cache_key=cache_key,
                signature=signature,
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                owner_agent_id=owner_agent_id,
                agent=agent,
            )
            self._resident_agents[cache_key] = resident
            return resident

    async def _prune_transient_messages(
        self,
        *,
        agent: Any,
        message_ids: set[str] | None,
    ) -> None:
        if not message_ids:
            return
        memory = getattr(agent, "memory", None)
        if memory is None:
            return
        delete = getattr(memory, "delete", None)
        if callable(delete):
            result = delete(list(message_ids))
            if asyncio.iscoroutine(result):
                await result
            return
        content = getattr(memory, "content", None)
        if isinstance(content, list):
            memory.content = [
                (msg, marks)
                for msg, marks in content
                if getattr(msg, "id", None) not in message_ids
            ]

    def _resident_agent_cache_key(
        self,
        *,
        channel: str,
        session_id: str,
        user_id: str,
        owner_agent_id: str,
    ) -> str:
        return f"{channel}:{session_id}:{user_id}:{owner_agent_id}"

    def _resident_agent_signature(
        self,
        *,
        owner_agent_id: str,
        actor_key: object | None,
        actor_fingerprint: object | None,
        prompt_appendix: str | None,
        tool_capability_ids: set[str] | None,
        skill_names: set[str] | None,
        mcp_client_keys: list[str] | None,
        system_capability_ids: set[str] | None,
    ) -> str:
        try:
            from copaw.agents.model_factory import build_runtime_model_fingerprint

            runtime_model_fingerprint = build_runtime_model_fingerprint()
        except Exception:
            runtime_model_fingerprint = ""
        payload = {
            "owner_agent_id": owner_agent_id,
            "actor_key": _first_non_empty(actor_key),
            "actor_fingerprint": _first_non_empty(actor_fingerprint),
            "prompt_appendix": prompt_appendix or "",
            "tool_capability_ids": sorted(tool_capability_ids or []),
            "skill_names": sorted(skill_names or []),
            "mcp_client_keys": sorted(mcp_client_keys) if isinstance(mcp_client_keys, list) else None,
            "system_capability_ids": sorted(system_capability_ids or []),
            "runtime_model_fingerprint": runtime_model_fingerprint,
        }
        return hashlib.sha1(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        ).hexdigest()

    def _make_shell_evidence_sink(self, kernel_task_id: str | None):
        if self._tool_bridge is None or kernel_task_id is None:
            return None
        return lambda payload: self._tool_bridge.record_shell_event(
            kernel_task_id,
            payload,
        )

    def _make_file_evidence_sink(self, kernel_task_id: str | None):
        if self._tool_bridge is None or kernel_task_id is None:
            return None
        return lambda payload: self._tool_bridge.record_file_event(
            kernel_task_id,
            payload,
        )

    def _make_browser_evidence_sink(self, kernel_task_id: str | None):
        if self._tool_bridge is None or kernel_task_id is None:
            return None
        return lambda payload: self._tool_bridge.record_browser_event(
            kernel_task_id,
            payload,
        )

    def _merge_main_brain_runtime_contexts(
        self,
        *values: Any,
    ) -> dict[str, Any] | None:
        merged: dict[str, Any] = {}
        for value in values:
            normalized = normalize_main_brain_runtime_context(value)
            if not normalized:
                continue
            for section in ("intent", "environment", "recovery"):
                payload = _mapping_value(normalized.get(section))
                if not payload:
                    continue
                existing = _mapping_value(merged.get(section))
                merged[section] = {
                    **existing,
                    **payload,
                }
        return merged or None

    def _resolve_request_main_brain_runtime_context(
        self,
        *,
        request: Any | None,
    ) -> dict[str, Any] | None:
        if request is None:
            return None
        return self._merge_main_brain_runtime_contexts(
            getattr(request, "_copaw_main_brain_runtime_context", None),
            getattr(request, "main_brain_runtime", None),
        )

    def _mark_actor_query_started(
        self,
        *,
        agent_id: str,
        task_id: str | None,
        session_id: str,
        user_id: str,
        conversation_thread_id: str | None,
        channel: str,
        execution_context: dict[str, Any] | None = None,
    ) -> None:
        runtime_repository = self._agent_runtime_repository
        runtime = runtime_repository.get_runtime(agent_id) if runtime_repository is not None else None
        now = _utc_now()
        checkpoint = self._record_query_checkpoint(
            agent_id=agent_id,
            task_id=task_id,
            session_id=session_id,
            user_id=user_id,
            conversation_thread_id=conversation_thread_id,
            channel=channel,
            phase="query-start",
            checkpoint_kind="worker-step",
            status="ready",
            summary="已开始交互查询轮次",
            execution_context=execution_context,
        )
        checkpoint_id = getattr(checkpoint, "id", None) if checkpoint is not None else None
        if runtime is None or runtime_repository is None:
            return
        main_brain_runtime = self._merge_main_brain_runtime_contexts(
            dict(runtime.metadata or {}).get("main_brain_runtime"),
            (execution_context or {}).get("main_brain_runtime"),
        )
        metadata = {
            **dict(runtime.metadata or {}),
            "last_query_channel": channel,
            "last_query_session_id": session_id,
            "last_query_user_id": user_id,
            "last_query_thread_id": conversation_thread_id,
            "last_resume_cursor": _first_non_empty(
                _mapping_value(
                    (execution_context or {}).get("resume_point"),
                ).get("cursor"),
            ),
            "last_task_segment_id": _first_non_empty(
                _mapping_value(
                    (execution_context or {}).get("task_segment"),
                ).get("segment_id"),
            ),
        }
        if main_brain_runtime is not None:
            metadata["main_brain_runtime"] = main_brain_runtime
        runtime_repository.upsert_runtime(
            runtime.model_copy(
                update={
                    "runtime_status": "running",
                    "current_task_id": task_id or runtime.current_task_id,
                    "last_started_at": now,
                    "last_heartbeat_at": now,
                    "last_error_summary": None,
                    "last_checkpoint_id": checkpoint_id or runtime.last_checkpoint_id,
                    "metadata": metadata,
                },
            ),
        )

    def _mark_actor_query_finished(
        self,
        *,
        agent_id: str,
        task_id: str | None,
        session_id: str,
        user_id: str,
        conversation_thread_id: str | None,
        channel: str,
        summary: str | None,
        error: str | None,
        execution_context: dict[str, Any] | None = None,
        stream_step_count: int = 0,
    ) -> None:
        runtime_repository = self._agent_runtime_repository
        runtime = runtime_repository.get_runtime(agent_id) if runtime_repository is not None else None
        now = _utc_now()
        resolved_error = normalize_runtime_summary(error)
        final_summary = normalize_runtime_summary(summary) or resolved_error or "交互查询已完成"
        checkpoint_phase, checkpoint_status = query_checkpoint_outcome(resolved_error)
        checkpoint = self._record_query_checkpoint(
            agent_id=agent_id,
            task_id=task_id,
            session_id=session_id,
            user_id=user_id,
            conversation_thread_id=conversation_thread_id,
            channel=channel,
            phase=checkpoint_phase,
            checkpoint_kind="task-result",
            status=checkpoint_status,
            summary=final_summary,
            execution_context=execution_context,
            stream_step_count=stream_step_count,
            snapshot_payload={
                "error": resolved_error,
                "final_summary": final_summary,
            },
        )
        checkpoint_id = getattr(checkpoint, "id", None) if checkpoint is not None else None
        if runtime is None or runtime_repository is None:
            return
        blocking_error = resolved_error if should_block_runtime_error(resolved_error) else None
        main_brain_runtime = self._merge_main_brain_runtime_contexts(
            dict(runtime.metadata or {}).get("main_brain_runtime"),
            (execution_context or {}).get("main_brain_runtime"),
        )
        metadata = {
            **dict(runtime.metadata or {}),
            "last_query_channel": channel,
            "last_query_session_id": session_id,
            "last_query_user_id": user_id,
            "last_query_thread_id": conversation_thread_id,
            "last_stream_step_count": stream_step_count,
            "last_query_outcome": (
                "failed"
                if blocking_error
                else "cancelled"
                if resolved_error
                else "completed"
            ),
        }
        if main_brain_runtime is not None:
            metadata["main_brain_runtime"] = main_brain_runtime
        runtime_repository.upsert_runtime(
            runtime.model_copy(
                update={
                    "runtime_status": (
                        "paused"
                        if runtime.desired_state == "paused"
                        else "blocked"
                        if blocking_error
                        else "idle"
                    ),
                    "current_task_id": None,
                    "last_heartbeat_at": now,
                    "last_stopped_at": now,
                    "last_result_summary": runtime.last_result_summary if resolved_error else final_summary,
                    "last_error_summary": resolved_error,
                    "last_checkpoint_id": checkpoint_id or runtime.last_checkpoint_id,
                    "metadata": metadata,
                },
            ),
        )

    def record_turn_usage(
        self,
        *,
        request: Any,
        kernel_task_id: str | None,
        usage: Any,
    ) -> None:
        usage_payload = _normalize_usage_payload(usage)
        if not usage_payload:
            return
        now = _utc_now()
        owner_agent_id = self.resolve_request_owner_agent_id(request=request)
        cost_estimate = _extract_usage_cost_estimate(usage_payload)
        model_context = self._resolve_query_model_usage_context(
            request=request,
            owner_agent_id=owner_agent_id,
        )
        self._record_agent_runtime_usage(
            owner_agent_id=owner_agent_id,
            usage_payload=usage_payload,
            cost_estimate=cost_estimate,
            model_context=model_context,
            recorded_at=now,
        )
        self._record_query_usage_evidence(
            request=request,
            kernel_task_id=kernel_task_id,
            owner_agent_id=owner_agent_id,
            usage_payload=usage_payload,
            cost_estimate=cost_estimate,
            model_context=model_context,
            recorded_at=now,
        )

    def _record_agent_runtime_usage(
        self,
        *,
        owner_agent_id: str | None,
        usage_payload: dict[str, Any],
        cost_estimate: float | None,
        model_context: dict[str, Any],
        recorded_at: datetime,
    ) -> None:
        if self._agent_runtime_repository is None or not owner_agent_id:
            return
        runtime = self._agent_runtime_repository.get_runtime(owner_agent_id)
        if runtime is None:
            return
        metadata = dict(runtime.metadata or {})
        metadata["last_query_usage"] = usage_payload
        metadata["last_query_usage_at"] = recorded_at.isoformat()
        if model_context:
            metadata["last_query_model_context"] = model_context
        if cost_estimate is not None:
            metadata["last_query_cost_estimate"] = cost_estimate
            metadata["query_cost_total_estimate"] = round(
                _usage_float(metadata.get("query_cost_total_estimate"), 0.0)
                + cost_estimate,
                12,
            )
        metadata["query_usage_totals"] = _merge_usage_totals(
            metadata.get("query_usage_totals"),
            usage_payload,
        )
        self._agent_runtime_repository.upsert_runtime(
            runtime.model_copy(
                update={
                    "metadata": metadata,
                    "updated_at": recorded_at,
                },
            ),
        )

    def _record_query_usage_evidence(
        self,
        *,
        request: Any,
        kernel_task_id: str | None,
        owner_agent_id: str | None,
        usage_payload: dict[str, Any],
        cost_estimate: float | None,
        model_context: dict[str, Any],
        recorded_at: datetime,
    ) -> None:
        if self._evidence_ledger is None or not kernel_task_id:
            return
        task_runtime = None
        if self._task_runtime_repository is not None:
            task_runtime = self._task_runtime_repository.get_runtime(kernel_task_id)
        risk_level = _first_non_empty(
            getattr(task_runtime, "risk_level", None),
            "auto",
        ) or "auto"
        owner_agent_id = (
            _first_non_empty(
                getattr(task_runtime, "last_owner_agent_id", None),
                owner_agent_id,
            )
            or owner_agent_id
        )
        record = self._evidence_ledger.append(
            EvidenceRecord(
                task_id=kernel_task_id,
                actor_ref=(
                    f"agent:{owner_agent_id}"
                    if owner_agent_id
                    else "agent:interactive-query"
                ),
                environment_ref=(
                    f"session:{_first_non_empty(getattr(request, 'channel', None), DEFAULT_CHANNEL)}:"
                    f"{_first_non_empty(getattr(request, 'session_id', None), 'unknown')}"
                ),
                capability_ref="system:dispatch_query",
                risk_level=risk_level,
                action_summary="Record interactive query token usage",
                result_summary=_summarize_usage_payload(
                    usage_payload,
                    cost_estimate=cost_estimate,
                ),
                created_at=recorded_at,
                metadata={
                    "usage_kind": "interactive-query",
                    "usage": usage_payload,
                    "cost_estimate": cost_estimate,
                    "owner_agent_id": owner_agent_id,
                    "channel": _first_non_empty(getattr(request, "channel", None), DEFAULT_CHANNEL),
                    "session_id": _first_non_empty(getattr(request, "session_id", None)),
                    "user_id": _first_non_empty(getattr(request, "user_id", None)),
                    "session_kind": _first_non_empty(getattr(request, "session_kind", None)),
                    "industry_instance_id": _first_non_empty(
                        getattr(request, "industry_instance_id", None),
                    ),
                    "industry_role_id": _first_non_empty(
                        getattr(request, "industry_role_id", None),
                    ),
                    "model_context": model_context,
                },
            ),
        )
        if task_runtime is None or self._task_runtime_repository is None:
            return
        self._task_runtime_repository.upsert_runtime(
            task_runtime.model_copy(
                update={
                    "last_evidence_id": record.id,
                    "updated_at": recorded_at,
                },
            ),
        )

    def _resolve_query_model_usage_context(
        self,
        *,
        request: Any,
        owner_agent_id: str | None,
    ) -> dict[str, Any]:
        del request, owner_agent_id
        try:
            manager = self._provider_manager or ProviderManager()
            slot, using_fallback, reason, unavailable = manager.resolve_model_slot()
        except Exception:
            return {}
        return {
            "provider_id": slot.provider_id,
            "model": slot.model,
            "slot_source": "fallback" if using_fallback else "active",
            "selection_reason": reason,
            "unavailable_slots": list(unavailable),
        }

    def _resolve_execution_task_context(
        self,
        *,
        request: Any | None = None,
        agent_id: str,
        kernel_task_id: str | None,
        conversation_thread_id: str | None,
    ) -> dict[str, Any]:
        context: dict[str, Any] = {}
        runtime_repository = self._agent_runtime_repository

        def _merge_main_brain_runtime(value: Any) -> None:
            merged = self._merge_main_brain_runtime_contexts(
                context.get("main_brain_runtime"),
                value,
            )
            if merged is not None:
                context["main_brain_runtime"] = merged

        if kernel_task_id and self._kernel_dispatcher is not None:
            task = self._kernel_dispatcher.lifecycle.get_task(kernel_task_id)
            if task is not None:
                if isinstance(task.task_segment, dict) and task.task_segment:
                    context["task_segment"] = dict(task.task_segment)
                if isinstance(task.resume_point, dict) and task.resume_point:
                    context["resume_point"] = dict(task.resume_point)
                if isinstance(task.actor_owner_id, str) and task.actor_owner_id:
                    context["actor_owner_id"] = task.actor_owner_id
                if isinstance(getattr(task, "work_context_id", None), str) and task.work_context_id:
                    context["work_context_id"] = task.work_context_id
                payload = task.payload if isinstance(task.payload, dict) else {}
                _merge_main_brain_runtime(payload.get("main_brain_runtime"))
                task_request_context = _mapping_value(payload.get("request_context"))
                if task_request_context:
                    _merge_main_brain_runtime(task_request_context.get("main_brain_runtime"))
                task_request = _mapping_value(payload.get("request"))
                if task_request:
                    _merge_main_brain_runtime(task_request.get("main_brain_runtime"))
        runtime = runtime_repository.get_runtime(agent_id) if runtime_repository is not None else None
        if runtime is not None:
            runtime_metadata = _mapping_value(getattr(runtime, "metadata", None))
            if runtime_metadata:
                _merge_main_brain_runtime(runtime_metadata.get("main_brain_runtime"))
        if self._actor_mailbox_service is not None:
            list_checkpoints = getattr(self._actor_mailbox_service, "list_checkpoints", None)
            if callable(list_checkpoints):
                checkpoints = list_checkpoints(
                    agent_id=agent_id,
                    task_id=kernel_task_id,
                    conversation_thread_id=conversation_thread_id,
                    limit=10,
                )
                if checkpoints:
                    latest_checkpoint = checkpoints[0]
                    context["resume_checkpoint"] = latest_checkpoint.model_dump(mode="json")
                    checkpoint_resume = _mapping_value(latest_checkpoint.resume_payload)
                    if checkpoint_resume:
                        context["resume_payload"] = checkpoint_resume
                        embedded_resume = _mapping_value(checkpoint_resume.get("resume_point"))
                        if embedded_resume and "resume_point" not in context:
                            context["resume_point"] = embedded_resume
                        _merge_main_brain_runtime(checkpoint_resume.get("main_brain_runtime"))
                    checkpoint_snapshot = _mapping_value(latest_checkpoint.snapshot_payload)
                    if checkpoint_snapshot:
                        context["resume_snapshot"] = checkpoint_snapshot
        _merge_main_brain_runtime(
            self._resolve_request_main_brain_runtime_context(request=request),
        )
        return context

    def _record_query_checkpoint(
        self,
        *,
        agent_id: str,
        task_id: str | None,
        session_id: str,
        user_id: str,
        conversation_thread_id: str | None,
        channel: str,
        phase: str,
        checkpoint_kind: str,
        status: str,
        summary: str,
        execution_context: dict[str, Any] | None = None,
        stream_step_count: int = 0,
        snapshot_payload: dict[str, object] | None = None,
    ) -> Any | None:
        if self._actor_mailbox_service is None:
            return None
        create_checkpoint = getattr(self._actor_mailbox_service, "create_checkpoint", None)
        if not callable(create_checkpoint):
            return None
        runtime = (
            self._agent_runtime_repository.get_runtime(agent_id)
            if self._agent_runtime_repository is not None
            else None
        )
        mailbox_id = getattr(runtime, "current_mailbox_id", None) if runtime is not None else None
        task_segment = _mapping_value((execution_context or {}).get("task_segment"))
        resume_point = _mapping_value((execution_context or {}).get("resume_point"))
        main_brain_runtime = self._merge_main_brain_runtime_contexts(
            (execution_context or {}).get("main_brain_runtime"),
        )
        checkpoint_payload = {
            "session_id": session_id,
            "user_id": user_id,
            "channel": channel,
            "kernel_task_id": task_id,
            "stream_step_count": stream_step_count,
            "task_segment": task_segment,
            "resume_point": {
                **resume_point,
                "phase": phase,
                "cursor": _first_non_empty(
                    resume_point.get("cursor"),
                    task_segment.get("segment_id"),
                    conversation_thread_id,
                ),
            },
        }
        if main_brain_runtime is not None:
            checkpoint_payload["main_brain_runtime"] = main_brain_runtime
        return create_checkpoint(
            agent_id=agent_id,
            mailbox_id=mailbox_id,
            task_id=task_id,
            work_context_id=_first_non_empty((execution_context or {}).get("work_context_id")),
            checkpoint_kind=checkpoint_kind,
            status=status,
            phase=phase,
            conversation_thread_id=conversation_thread_id,
            environment_ref=channel,
            summary=summary,
            snapshot_payload={
                "channel": channel,
                "conversation_thread_id": conversation_thread_id,
                **dict(snapshot_payload or {}),
            },
            resume_payload=checkpoint_payload,
        )

    def _acquire_actor_runtime_lease(
        self,
        *,
        agent_id: str,
        task_id: str | None,
        conversation_thread_id: str | None,
    ) -> Any | None:
        if self._environment_service is None:
            return None
        acquire = getattr(self._environment_service, "acquire_actor_lease", None)
        if not callable(acquire):
            return None
        try:
            return acquire(
                agent_id=agent_id,
                owner=_first_non_empty(conversation_thread_id, task_id, agent_id) or agent_id,
                ttl_seconds=180,
                metadata={
                    "task_id": task_id,
                    "thread_id": conversation_thread_id,
                    "lease_kind": "interactive-query",
                },
            )
        except RuntimeError as exc:
            message = str(exc).lower()
            if "not available" in message:
                return None
            logger.info(
                "Actor runtime lease acquisition blocked for '%s': %s",
                agent_id,
                exc,
            )
            raise
        except Exception:
            logger.exception("Actor runtime lease acquisition failed")
            return None

    def _heartbeat_actor_runtime_lease(self, lease: Any | None) -> None:
        if lease is None or self._environment_service is None:
            return
        heartbeat = getattr(self._environment_service, "heartbeat_actor_lease", None)
        if not callable(heartbeat):
            return
        try:
            heartbeat(lease.id, lease_token=lease.lease_token, ttl_seconds=180)
        except Exception:
            logger.exception("Actor runtime lease heartbeat failed")

    def _release_actor_runtime_lease(self, lease: Any | None) -> None:
        if lease is None or self._environment_service is None:
            return
        release = getattr(self._environment_service, "release_actor_lease", None)
        if not callable(release):
            return
        try:
            release(lease.id, lease_token=lease.lease_token, reason="interactive query completed")
        except Exception:
            logger.exception("Actor runtime lease release failed")

    def _build_query_lease_heartbeat(
        self,
        *,
        session_lease: Any | None,
        actor_lease: Any | None,
    ) -> LeaseHeartbeat | None:
        if session_lease is None and actor_lease is None:
            return None
        return LeaseHeartbeat(
            label="interactive-query",
            interval_seconds=self._lease_heartbeat_interval_seconds,
            heartbeat=lambda: self._heartbeat_query_leases(
                session_lease=session_lease,
                actor_lease=actor_lease,
            ),
        )

    def _heartbeat_query_leases(
        self,
        *,
        session_lease: Any | None,
        actor_lease: Any | None,
    ) -> None:
        if session_lease is not None and self._environment_service is not None:
            self._environment_service.heartbeat_session_lease(
                session_lease.id,
                lease_token=session_lease.lease_token or "",
            )
        self._heartbeat_actor_runtime_lease(actor_lease)


    def _resolve_query_agent_profile(
        self,
        *,
        request: Any,
    ) -> tuple[str, Any | None]:
        for agent_id in self._request_agent_candidates(request):
            if not agent_id:
                continue
            profile = self._get_agent_profile(agent_id)
            if profile is not None:
                return agent_id, profile
        fallback_profile = self._resolve_fallback_execution_core_profile(request=request)
        if fallback_profile is not None:
            return str(
                getattr(fallback_profile, "agent_id", EXECUTION_CORE_AGENT_ID),
            ), fallback_profile
        return EXECUTION_CORE_AGENT_ID, self._get_agent_profile(EXECUTION_CORE_AGENT_ID)

    def _request_agent_candidates(self, request: Any) -> list[str]:
        candidates: list[str] = []
        for value in (
            getattr(request, "agent_id", None),
            getattr(request, "target_agent_id", None),
            getattr(request, "user_id", None),
        ):
            normalized = _normalize_agent_candidate(value)
            if normalized and normalized not in candidates:
                candidates.append(normalized)

        industry_instance_id = _first_non_empty(
            getattr(request, "industry_instance_id", None),
        )
        industry_role_id = _first_non_empty(
            getattr(request, "industry_role_id", None),
        )
        if industry_instance_id:
            resolved_agent_id = self._resolve_industry_agent_id(
                industry_instance_id=industry_instance_id,
                industry_role_id=industry_role_id or EXECUTION_CORE_ROLE_ID,
            )
            if resolved_agent_id and resolved_agent_id not in candidates:
                candidates.append(resolved_agent_id)
        return candidates

    def _get_agent_profile(self, agent_id: str) -> Any | None:
        service = self._agent_profile_service
        if service is None:
            return None
        getter = getattr(service, "get_agent", None)
        if not callable(getter):
            return None
        return getter(agent_id)

    def _list_agent_profiles(self) -> list[Any]:
        service = self._agent_profile_service
        if service is None:
            return []
        lister = getattr(service, "list_agents", None)
        if not callable(lister):
            return []
        try:
            profiles = list(lister())
        except Exception:
            logger.exception("Failed to list agent profiles for query owner resolution")
            return []
        return profiles

    def _find_industry_agent_profile(
        self,
        *,
        industry_instance_id: str,
        industry_role_id: str,
    ) -> Any | None:
        normalized_role_id = normalize_industry_role_id(industry_role_id)
        if normalized_role_id is None:
            return None
        if is_execution_core_role_id(normalized_role_id):
            return self._get_agent_profile(EXECUTION_CORE_AGENT_ID)
        for profile in self._list_agent_profiles():
            if _first_non_empty(getattr(profile, "industry_instance_id", None)) != industry_instance_id:
                continue
            profile_role_id = normalize_industry_role_id(
                _first_non_empty(getattr(profile, "industry_role_id", None)),
            )
            if profile_role_id != normalized_role_id:
                continue
            return profile
        return None

    def _resolve_industry_agent_id(
        self,
        *,
        industry_instance_id: str,
        industry_role_id: str,
    ) -> str | None:
        profile = self._find_industry_agent_profile(
            industry_instance_id=industry_instance_id,
            industry_role_id=industry_role_id,
        )
        if profile is not None:
            return _normalize_agent_candidate(getattr(profile, "agent_id", None))
        instance = self._get_industry_instance(industry_instance_id)
        if instance is None:
            return None
        normalized_role_id = normalize_industry_role_id(industry_role_id)
        for collection_name in ("team", "agents"):
            items = _field_value(instance, collection_name)
            if collection_name == "team":
                items = _field_value(items, "agents")
            if not isinstance(items, list):
                continue
            for item in items:
                candidate_role_id = normalize_industry_role_id(
                    _field_value(item, "role_id", "industry_role_id"),
                )
                if candidate_role_id != normalized_role_id:
                    continue
                agent_id = _normalize_agent_candidate(
                    _field_value(item, "agent_id", "id"),
                )
                if agent_id:
                    return agent_id
        return None

    def _resolve_fallback_execution_core_profile(self, *, request: Any) -> Any | None:
        session_kind = _first_non_empty(getattr(request, "session_kind", None))
        channel = _first_non_empty(getattr(request, "channel", None))
        industry_instance_id = _first_non_empty(getattr(request, "industry_instance_id", None))
        if industry_instance_id:
            return self._get_agent_profile(EXECUTION_CORE_AGENT_ID)
        if session_kind not in {None, "industry-agent-chat"} and channel != DEFAULT_CHANNEL:
            return None
        return self._get_agent_profile(EXECUTION_CORE_AGENT_ID)

    def _resolve_query_capability_context(
        self,
        owner_agent_id: str,
    ) -> tuple[
        set[str] | None,
        set[str] | None,
        list[str] | None,
        set[str] | None,
        bool,
    ]:
        service = self._capability_service
        if service is None:
            return None, None, None, None, False
        lister = getattr(service, "list_accessible_capabilities", None)
        if not callable(lister):
            return None, None, None, None, False
        mounts = lister(agent_id=owner_agent_id, enabled_only=True)
        tool_capability_ids = {
            str(mount.id)
            for mount in mounts
            if getattr(mount, "source_kind", None) == "tool"
        }
        skill_names = {
            _capability_name_from_id(str(mount.id), prefix="skill:")
            for mount in mounts
            if getattr(mount, "source_kind", None) == "skill"
        }
        mcp_client_keys = sorted(
            _capability_name_from_id(str(mount.id), prefix="mcp:")
            for mount in mounts
            if getattr(mount, "source_kind", None) == "mcp"
        )
        system_capability_ids = {
            str(mount.id)
            for mount in mounts
            if getattr(mount, "source_kind", None) == "system"
        }
        desktop_actuation_available = any(
            _mount_supports_desktop_actuation(mount)
            for mount in mounts
        )
        return (
            tool_capability_ids,
            skill_names,
            mcp_client_keys,
            system_capability_ids,
            desktop_actuation_available,
        )

    def _prune_execution_core_control_capability_context(
        self,
        *,
        request: Any,
        owner_agent_id: str,
        agent_profile: Any | None,
        tool_capability_ids: set[str] | None,
        skill_names: set[str] | None,
        mcp_client_keys: list[str] | None,
        system_capability_ids: set[str] | None,
        desktop_actuation_available: bool,
    ) -> tuple[
        set[str] | None,
        set[str] | None,
        list[str] | None,
        set[str] | None,
        bool,
    ]:
        industry_instance_id = _first_non_empty(
            getattr(request, "industry_instance_id", None),
            getattr(agent_profile, "industry_instance_id", None)
            if agent_profile is not None
            else None,
        )
        industry_role_id = _first_non_empty(
            getattr(request, "industry_role_id", None),
            getattr(agent_profile, "industry_role_id", None)
            if agent_profile is not None
            else None,
        )
        if not industry_instance_id:
            return (
                tool_capability_ids,
                skill_names,
                mcp_client_keys,
                system_capability_ids,
                desktop_actuation_available,
            )
        if not (
            is_execution_core_agent_id(owner_agent_id)
            or industry_role_id == EXECUTION_CORE_ROLE_ID
        ):
            return (
                tool_capability_ids,
                skill_names,
                mcp_client_keys,
                system_capability_ids,
                desktop_actuation_available,
            )
        allowed_system_capability_ids = {
            "system:apply_role",
            "system:discover_capabilities",
            "system:dispatch_query",
            "system:delegate_task",
        }
        filtered_system_capability_ids = {
            capability_id
            for capability_id in (system_capability_ids or set())
            if capability_id in allowed_system_capability_ids
        }
        filtered_tool_capability_ids = {
            capability_id
            for capability_id in (tool_capability_ids or set())
            if capability_id in _EXECUTION_CORE_ALLOWED_LOCAL_TOOL_CAPABILITY_IDS
        }
        return (
            filtered_tool_capability_ids,
            set(),
            [],
            filtered_system_capability_ids,
            False,
        )

    def _resolve_delegation_first_guard(
        self,
        *,
        request: Any,
        owner_agent_id: str,
        agent_profile: Any | None,
        system_capability_ids: set[str] | None,
    ) -> _DelegationFirstGuard | None:
        if not system_capability_ids:
            return None
        if not (
            "system:dispatch_query" in system_capability_ids
            or "system:delegate_task" in system_capability_ids
        ):
            return None
        industry_instance_id = _first_non_empty(
            getattr(request, "industry_instance_id", None),
            getattr(agent_profile, "industry_instance_id", None)
            if agent_profile is not None
            else None,
        )
        industry_role_id = _first_non_empty(
            getattr(request, "industry_role_id", None),
            getattr(agent_profile, "industry_role_id", None)
            if agent_profile is not None
            else None,
        )
        if not industry_instance_id:
            return None
        if not (
            is_execution_core_agent_id(owner_agent_id)
            or industry_role_id == EXECUTION_CORE_ROLE_ID
        ):
            return None
        teammates = tuple(
            self._list_delegation_first_teammates(
                industry_instance_id=industry_instance_id,
                owner_agent_id=owner_agent_id,
            ),
        )
        if not teammates:
            return None
        return _DelegationFirstGuard(
            owner_agent_id=owner_agent_id,
            teammates=teammates,
        )

    async def _resolve_requested_main_brain_intake_contract(
        self,
        *,
        msgs: list[Any],
        request: Any,
    ):
        intake_contract = await resolve_request_main_brain_intake_contract(
            request=request,
            msgs=msgs,
        )
        if intake_contract is None:
            return None
        if intake_contract.writeback_requested and not intake_contract.has_active_writeback_plan:
            raise RuntimeError(
                "Structured chat writeback was explicitly requested but could not be materialized.",
            )
        return intake_contract

    def _resolve_requested_chat_writeback_plan(
        self,
        *,
        msgs: list[Any],
        request: Any,
    ) -> ChatWritebackPlan | None:
        intake_contract = resolve_request_main_brain_intake_contract_sync(
            request=request,
            msgs=msgs,
        )
        if intake_contract is not None and intake_contract.writeback_requested and not intake_contract.has_active_writeback_plan:
            raise RuntimeError(
                "Structured chat writeback was explicitly requested but could not be materialized.",
            )
        if intake_contract is None or not intake_contract.has_active_writeback_plan:
            return None
        return intake_contract.writeback_plan

    async def _apply_requested_main_brain_intake(
        self,
        *,
        msgs: list[Any],
        request: Any,
        owner_agent_id: str,
        agent_profile: Any | None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        industry_instance_id = resolve_execution_core_industry_instance_id(
            request=request,
            owner_agent_id=owner_agent_id,
            agent_profile=agent_profile,
        )
        if industry_instance_id is None:
            return None, None
        service = self._industry_service
        if service is None:
            return None, None
        intake_contract = await self._resolve_requested_main_brain_intake_contract(
            msgs=msgs,
            request=request,
        )
        if intake_contract is None:
            return None, None
        chat_writeback_summary = None
        if intake_contract.has_active_writeback_plan:
            applier = getattr(service, "apply_execution_chat_writeback", None)
            if callable(applier):
                try:
                    apply_kwargs = build_industry_chat_action_kwargs(
                        industry_instance_id=industry_instance_id,
                        message_text=intake_contract.message_text,
                        owner_agent_id=owner_agent_id,
                        request=request,
                    )
                    try:
                        result = applier(
                            **apply_kwargs,
                            writeback_plan=intake_contract.writeback_plan,
                        )
                    except TypeError as exc:
                        if "writeback_plan" not in str(exc):
                            raise
                        result = applier(**apply_kwargs)
                    if asyncio.iscoroutine(result):
                        result = await result
                    chat_writeback_summary = result if isinstance(result, dict) else None
                except Exception:
                    logger.exception(
                        "Failed to persist execution-core chat writeback for industry '%s'",
                        industry_instance_id,
                    )
        industry_kickoff_summary = None
        if intake_contract.should_kickoff:
            kickoff = getattr(service, "kickoff_execution_from_chat", None)
            if callable(kickoff):
                try:
                    result = kickoff(
                        **build_industry_chat_action_kwargs(
                            industry_instance_id=industry_instance_id,
                            message_text=intake_contract.message_text,
                            owner_agent_id=owner_agent_id,
                            request=request,
                        ),
                    )
                    if asyncio.iscoroutine(result):
                        result = await result
                    industry_kickoff_summary = result if isinstance(result, dict) else None
                except Exception:
                    logger.exception(
                        "Failed to kick off industry execution for '%s' from chat",
                        industry_instance_id,
                    )
        return chat_writeback_summary, industry_kickoff_summary

def _usage_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _usage_jsonable(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, (list, tuple, set)):
        return [_usage_jsonable(item) for item in value]
    mapped = _mapping_value(value)
    if mapped:
        return _usage_jsonable(mapped)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _usage_int(*values: Any) -> int | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = str(value).strip()
        if not text:
            continue
        try:
            return int(float(text))
        except ValueError:
            continue
    return None


def _usage_float(*values: Any) -> float | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            continue
        try:
            return float(text)
        except ValueError:
            continue
    return None


def _normalize_usage_payload(value: Any) -> dict[str, Any]:
    payload = _mapping_value(value)
    if not payload:
        return {}
    normalized = _usage_jsonable(payload)
    if not isinstance(normalized, dict):
        return {}
    prompt_tokens = _usage_int(
        normalized.get("prompt_tokens"),
        normalized.get("input_tokens"),
    )
    completion_tokens = _usage_int(
        normalized.get("completion_tokens"),
        normalized.get("output_tokens"),
    )
    total_tokens = _usage_int(normalized.get("total_tokens"))
    cached_tokens = _usage_int(
        normalized.get("cached_tokens"),
        normalized.get("cached_input_tokens"),
    )
    reasoning_tokens = _usage_int(normalized.get("reasoning_tokens"))
    if prompt_tokens is not None:
        normalized.setdefault("prompt_tokens", prompt_tokens)
    if completion_tokens is not None:
        normalized.setdefault("completion_tokens", completion_tokens)
    if total_tokens is None and (
        prompt_tokens is not None or completion_tokens is not None
    ):
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
    if total_tokens is not None:
        normalized["total_tokens"] = total_tokens
    if cached_tokens is not None:
        normalized["cached_tokens"] = cached_tokens
    if reasoning_tokens is not None:
        normalized["reasoning_tokens"] = reasoning_tokens
    cost_estimate = _extract_usage_cost_estimate(normalized)
    if cost_estimate is not None:
        normalized["cost_estimate"] = cost_estimate
    return normalized


def _extract_usage_cost_estimate(usage_payload: dict[str, Any]) -> float | None:
    return _usage_float(
        usage_payload.get("cost_estimate"),
        usage_payload.get("estimated_cost"),
        usage_payload.get("cost"),
        usage_payload.get("total_cost"),
    )


def _merge_usage_totals(
    existing: Any,
    usage_payload: dict[str, Any],
) -> dict[str, Any]:
    totals = _mapping_value(existing)
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cached_tokens",
        "reasoning_tokens",
    ):
        amount = _usage_int(usage_payload.get(key))
        if amount is None:
            continue
        totals[key] = _usage_int(totals.get(key), 0) + amount
    return totals


def _summarize_usage_payload(
    usage_payload: dict[str, Any],
    *,
    cost_estimate: float | None,
) -> str:
    parts: list[str] = []
    prompt_tokens = _usage_int(usage_payload.get("prompt_tokens"))
    completion_tokens = _usage_int(usage_payload.get("completion_tokens"))
    total_tokens = _usage_int(usage_payload.get("total_tokens"))
    cached_tokens = _usage_int(usage_payload.get("cached_tokens"))
    reasoning_tokens = _usage_int(usage_payload.get("reasoning_tokens"))
    if prompt_tokens is not None:
        parts.append(f"prompt={prompt_tokens}")
    if completion_tokens is not None:
        parts.append(f"completion={completion_tokens}")
    if total_tokens is not None:
        parts.append(f"total={total_tokens}")
    if cached_tokens is not None:
        parts.append(f"cached={cached_tokens}")
    if reasoning_tokens is not None:
        parts.append(f"reasoning={reasoning_tokens}")
    if cost_estimate is not None:
        parts.append(f"cost={cost_estimate:g}")
    if not parts:
        return "Recorded interactive query usage."
    return f"Recorded interactive query usage ({', '.join(parts)})."
