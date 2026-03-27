# -*- coding: utf-8 -*-
"""Kernel-native turn executor for query dispatch."""
from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from agentscope.message import Msg, TextBlock
from agentscope_runtime.adapters.agentscope.message import message_to_agentscope_msg
from agentscope_runtime.adapters.agentscope.stream import adapt_agentscope_message_stream
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    AgentResponse,
    Error,
    Event,
    RunStatus,
    SequenceNumberGenerator,
)
from agentscope_runtime.engine.schemas.exception import (
    AppBaseException,
    UnknownAgentException,
)

from ..agents.memory import MemoryManager
from ..app.channels.schema import DEFAULT_CHANNEL
from ..app.runtime_commands import (
    infer_turn_capability_and_risk,
    is_command,
    run_command_path,
)
from ..providers.model_diagnostics import normalize_runtime_exception
from .main_brain_intake import (
    extract_main_brain_intake_text,
    resolve_main_brain_intake_contract_sync,
)
from .main_brain_chat_service import MainBrainChatService
from .main_brain_orchestrator import MainBrainOrchestrator
from .query_error_dump import write_query_error_dump
from .models import KernelTask
from .query_execution import KernelQueryExecutionService
from .query_execution_shared import (
    _first_non_empty,
    _is_hypothetical_control_text,
    _looks_like_goal_setting_text,
)

logger = logging.getLogger(__name__)


def summarize_stream_message(msg: Any) -> str | None:
    if msg is None:
        return None
    if hasattr(msg, "get_text_content"):
        try:
            content = msg.get_text_content()
        except Exception:
            content = None
        if content:
            return str(content)[:240]
    for attr in ("text", "content"):
        value = getattr(msg, attr, None)
        if value:
            return str(value)[:240]
    return str(msg)[:240]


def _set_request_runtime_value(
    request: Any,
    name: str,
    value: Any,
) -> None:
    try:
        object.__setattr__(request, name, value)
        return
    except Exception:
        pass
    try:
        setattr(request, name, value)
    except Exception:
        logger.debug("Failed to set runtime request attribute '%s'", name)


def _extract_response_usage(response: AgentResponse) -> Any | None:
    for message in reversed(list(getattr(response, "output", []) or [])):
        usage = getattr(message, "usage", None)
        if usage is not None:
            return usage
    return None


def _resolve_interaction_mode(request: AgentRequest) -> str:
    value = getattr(request, "interaction_mode", None)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"auto", "chat", "orchestrate"}:
            return normalized
    return "orchestrate"


def _initial_turn_title(msgs: list[Any]) -> str:
    if msgs:
        try:
            content = msgs[0].get_text_content()
        except Exception:
            content = None
        if content:
            return content[:10]
    return "Media Message" if msgs else "New Chat"


def _request_payload(request: AgentRequest) -> dict[str, Any]:
    model_dump = getattr(request, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
    else:
        payload = {
        "id": request.id,
        "session_id": request.session_id,
        "user_id": request.user_id,
        "channel": getattr(request, "channel", DEFAULT_CHANNEL),
        "input": request.input,
        }
    for field in (
        "agent_id",
        "agent_name",
        "entry_source",
        "interaction_mode",
        "industry_instance_id",
        "industry_label",
        "industry_role_id",
        "industry_role_name",
        "owner_scope",
        "session_kind",
        "target_agent_id",
        "control_thread_id",
        "task_id",
        "task_title",
        "requested_actions",
        "work_context_id",
        "context_key",
    ):
        value = getattr(request, field, None)
        if value not in (None, ""):
            payload[field] = value
    return payload


def _approval_required_message(
    *,
    query: str | None,
    decision_request_id: str | None,
) -> Msg:
    title = "命令待批准" if query and is_command(query) else "需要批准"
    detail = (
        f"决策请求：`{decision_request_id}`。"
        if decision_request_id
        else "系统已创建决策请求。"
    )
    return Msg(
        name="Spider Mesh",
        role="assistant",
        content=[
            TextBlock(
                type="text",
                text=(
                    f"**{title}**\n\n- {detail}\n- 请先在主脑聊天里明确同意继续当前动作，"
                    "或在运行中心批准后，再继续执行。"
                ),
            ),
        ],
    )


def _admission_blocked_message(*, summary: str | None) -> Msg:
    detail = summary or "运行准入已被治理控制阻断。"
    return Msg(
        name="Spider Mesh",
        role="assistant",
        content=[
            TextBlock(
                type="text",
                text=(
                    "**运行已暂停**\n\n"
                    f"- {detail}\n"
                    "- 请先在运行中心恢复运行时，再继续派发新工作。"
                ),
            ),
        ],
    )


def _needs_human_mode_choice_message(*, query: str | None) -> Msg:
    preview = (query or "").strip()
    if preview:
        preview = preview[:80]
    detail = f"- 你刚才说：{preview}" if preview else "- 你刚才的输入较短，我无法判断你的意图。"
    return Msg(
        name="Spider Mesh",
        role="assistant",
        content=[
            TextBlock(
                type="text",
                text=(
                    "**需要补一句你的意图**\n\n"
                    f"{detail}\n"
                    "- 如果你的意思是让我直接接手推进，我会按主脑编排继续处理\n"
                    "- 如果你只是想先讨论/澄清，请直接说明“先分析”“先讨论”之类的意图"
                ),
            ),
        ],
    )


def _looks_like_question(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if "?" in stripped or "？" in stripped:
        return True
    lowered = stripped.lower()
    for prefix in (
        "why",
        "how",
        "what",
        "can you",
        "could you",
        "would you",
        "should we",
        "怎么",
        "如何",
        "为什么",
        "是否",
        "能否",
        "可以吗",
        "行不行",
        "要不要",
        "如果",
        "会不会",
        "会怎样",
    ):
        if lowered.startswith(prefix) or prefix in lowered:
            return True
    return False


def _message_text(message: Any) -> str:
    getter = getattr(message, "get_text_content", None)
    if callable(getter):
        try:
            text = getter()
        except Exception:
            text = None
        if isinstance(text, str) and text.strip():
            return text.strip()
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    return ""


def _message_role(message: Any) -> str:
    role = getattr(message, "role", None)
    if isinstance(role, str) and role.strip():
        return role.strip().lower()
    return ""


def _latest_assistant_text(msgs: list[Any]) -> str:
    for message in reversed(list(msgs or [])[:-1]):
        if _message_role(message) != "assistant":
            continue
        text = _message_text(message)
        if text:
            return text
    return ""


def _looks_like_execution_confirmation(*, text: str, msgs: list[Any]) -> bool:
    normalized = str(text or "").strip().lower().strip("。.!！~～")
    if not normalized or _looks_like_question(normalized):
        return False
    confirmation_phrases = (
        "确认",
        "确认继续",
        "同意",
        "同意执行",
        "好的",
        "好",
        "行",
        "可以",
        "ok",
        "okay",
        "收到",
        "继续",
        "继续吧",
        "开始吧",
        "那你开始吧",
        "那就开始吧",
        "就这么办",
        "按这个来",
        "照这个来",
        "就按这个来",
        "推进吧",
        "去推进",
        "去做吧",
        "那就做吧",
        "开干",
        "开始干",
    )
    if normalized not in confirmation_phrases:
        return False
    assistant_text = _latest_assistant_text(msgs).lower()
    if not assistant_text:
        return False
    execution_cues = (
        "进入执行编排",
        "开始执行",
        "开始推进",
        "继续推进",
        "继续执行",
        "确认继续",
        "同意执行",
        "下一条进入执行编排",
        "如果你确认",
        "如果确认",
        "确认后",
        "要不要开始执行",
        "可以开始执行",
        "可以开始推进",
        "当前还没进入执行阶段",
        "进入执行阶段",
    )
    return any(cue in assistant_text for cue in execution_cues)


def _looks_like_explicit_execution_request(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized or _is_hypothetical_control_text(normalized):
        return False
    lowered = normalized.lower()
    action_prefixes = (
        "登录",
        "打开",
        "进入",
        "点击",
        "检查",
        "排查",
        "核对",
        "核查",
        "看看",
        "看下",
        "看一下",
        "整理",
        "生成",
        "创建",
        "删除",
        "修改",
        "提交",
        "发送",
        "导出",
        "下载",
        "上传",
        "安装",
        "运行",
        "执行",
        "启动",
        "抓取",
        "同步",
    )
    if any(lowered.startswith(prefix) for prefix in action_prefixes):
        return True
    direct_execution_phrases = (
        "开始执行",
        "现在执行",
        "马上执行",
        "进入执行编排",
        "执行编排",
        "那你开始吧",
        "你开始吧",
        "那就开始吧",
        "开始吧",
        "你来推进",
        "帮我推进",
        "继续推进",
        "开始推进",
        "推进下去",
        "帮我落地",
        "落地一下",
        "开始干",
        "开干",
        "那就做",
        "就去做",
        "去做吧",
        "你来做",
        "按这个做",
        "按这个推进",
        "照这个推进",
        "给我做计划",
        "帮我做计划",
    )
    if any(phrase in lowered for phrase in direct_execution_phrases):
        return True
    polite_action_tokens = ("帮我", "麻烦", "请", "替我", "给我", "你来")
    if any(token in lowered for token in polite_action_tokens) and any(
        token in lowered
        for token in (
            "登录",
            "打开",
            "进入",
            "点击",
            "整理",
            "生成",
            "创建",
            "删除",
            "修改",
            "提交",
            "发送",
            "导出",
            "下载",
            "上传",
            "安装",
            "运行",
            "执行",
            "启动",
            "检查",
            "排查",
            "核对",
            "核查",
            "看看",
            "看下",
            "看一下",
            "抓取",
            "同步",
            "推进",
            "落地",
            "开干",
        )
    ):
        return True
    return False


def _should_use_model_auto_mode_resolution(request: AgentRequest) -> bool:
    industry_instance_id = str(getattr(request, "industry_instance_id", "") or "").strip()
    if industry_instance_id:
        return True
    control_thread_id = str(getattr(request, "control_thread_id", "") or "").strip()
    if control_thread_id:
        return True
    session_kind = str(getattr(request, "session_kind", "") or "").strip().lower()
    if session_kind.startswith("industry"):
        return True
    owner_scope = str(getattr(request, "owner_scope", "") or "").strip().lower()
    return owner_scope.startswith("industry")


def _resolve_auto_chat_mode_from_model(
    *,
    request: AgentRequest,
    msgs: list[Any],
) -> str | None:
    if not _should_use_model_auto_mode_resolution(request):
        return None
    query = extract_main_brain_intake_text(msgs)
    if not query:
        return None
    if _is_hypothetical_control_text(query):
        return "chat"
    try:
        intake_contract = resolve_main_brain_intake_contract_sync(msgs=msgs)
    except Exception:
        logger.debug("Model-assisted auto mode resolution failed", exc_info=True)
        return None
    if intake_contract is None:
        return None
    if intake_contract.should_route_to_orchestrate:
        return "orchestrate"
    if intake_contract.intent_kind in {"discussion", "status-query", "chat"}:
        return "chat"
    return None


def _resolve_auto_chat_mode(*, query: str | None, request: AgentRequest, msgs: list[Any]) -> str:
    """Return the effective interaction mode for chat surface.

    Default to main-brain autonomy: normal target-setting and execution entrustment
    should enter orchestration unless the turn is clearly discussion-only.
    """
    requested_actions = getattr(request, "requested_actions", None)
    if isinstance(requested_actions, list):
        if any(str(item or "").strip() for item in requested_actions):
            return "orchestrate"

    text = str(extract_main_brain_intake_text(msgs) or query or "").strip()
    if not text:
        return "chat"

    lowered = text.lower()
    if any(token in lowered for token in ("只聊天", "先聊", "不要执行", "不执行", "别执行", "仅讨论")):
        return "chat"

    model_mode = _resolve_auto_chat_mode_from_model(
        request=request,
        msgs=msgs,
    )
    if model_mode is not None:
        return model_mode

    if _looks_like_execution_confirmation(text=text, msgs=msgs):
        return "orchestrate"

    if _looks_like_explicit_execution_request(text):
        return "orchestrate"

    if _looks_like_goal_setting_text(text):
        return "orchestrate"

    if _looks_like_question(text):
        return "chat"

    ambiguous_markers = ("处理一下", "看一下", "帮忙", "弄一下", "搞一下", "执行一下", "做一下")
    if any(token in lowered for token in ambiguous_markers) and len(text) <= 18:
        return "needs_human"

    return "chat"


def _resolve_effective_interaction_mode(
    *,
    request: AgentRequest,
    msgs: list[Any],
    query: str | None,
) -> str:
    interaction_mode = _resolve_interaction_mode(request)
    if interaction_mode != "auto":
        return interaction_mode
    return _resolve_auto_chat_mode(
        query=query,
        request=request,
        msgs=msgs,
    )


class KernelTurnExecutor:
    """Execute one conversational turn without falling back to runner logic."""

    def __init__(
        self,
        *,
        session_backend: Any,
        memory_manager: MemoryManager | None = None,
        mcp_manager: Any | None = None,
        kernel_dispatcher: Any | None = None,
        tool_bridge: Any | None = None,
        environment_service: Any | None = None,
        query_execution_service: KernelQueryExecutionService | None = None,
        main_brain_chat_service: MainBrainChatService | None = None,
        main_brain_orchestrator: MainBrainOrchestrator | None = None,
        restart_callback: Callable[[], Any] | None = None,
        in_type_converters: dict[str, Callable] | None = None,
        out_type_converters: dict[str, Callable] | None = None,
    ) -> None:
        self._session_backend = session_backend
        self._memory_manager = memory_manager
        self._mcp_manager = mcp_manager
        self._kernel_dispatcher = kernel_dispatcher
        self._tool_bridge = tool_bridge
        self._environment_service = environment_service
        self._query_execution_service = query_execution_service or KernelQueryExecutionService(
            session_backend=session_backend,
            memory_manager=memory_manager,
            mcp_manager=mcp_manager,
            tool_bridge=tool_bridge,
            environment_service=environment_service,
        )
        self._main_brain_chat_service = main_brain_chat_service or MainBrainChatService(
            session_backend=session_backend,
        )
        self._main_brain_orchestrator = main_brain_orchestrator or MainBrainOrchestrator(
            query_execution_service=self._query_execution_service,
            session_backend=session_backend,
            environment_service=environment_service,
        )
        self._sync_query_execution_service(
            session_backend=session_backend,
            memory_manager=memory_manager,
            mcp_manager=mcp_manager,
            tool_bridge=tool_bridge,
            environment_service=environment_service,
            kernel_dispatcher=kernel_dispatcher,
        )
        self._sync_main_brain_orchestrator(
            session_backend=session_backend,
            query_execution_service=self._query_execution_service,
            environment_service=environment_service,
        )
        self._restart_callback = restart_callback
        self._in_type_converters = in_type_converters
        self._out_type_converters = out_type_converters

    def set_session_backend(self, session_backend: Any) -> None:
        self._session_backend = session_backend
        self._maybe_call_query_execution_service("set_session_backend", session_backend)
        self._maybe_call_main_brain_chat_service("set_session_backend", session_backend)
        self._maybe_call_main_brain_orchestrator("set_session_backend", session_backend)

    def set_memory_manager(self, memory_manager: MemoryManager | None) -> None:
        self._memory_manager = memory_manager
        self._maybe_call_query_execution_service("set_memory_manager", memory_manager)

    def set_mcp_manager(self, mcp_manager: Any | None) -> None:
        self._mcp_manager = mcp_manager
        self._maybe_call_query_execution_service("set_mcp_manager", mcp_manager)

    def set_kernel_dispatcher(self, kernel_dispatcher: Any | None) -> None:
        self._kernel_dispatcher = kernel_dispatcher
        self._maybe_call_query_execution_service(
            "set_kernel_dispatcher",
            kernel_dispatcher,
        )

    def set_tool_bridge(self, tool_bridge: Any | None) -> None:
        self._tool_bridge = tool_bridge
        self._maybe_call_query_execution_service("set_tool_bridge", tool_bridge)

    def set_environment_service(self, environment_service: Any | None) -> None:
        self._environment_service = environment_service
        self._maybe_call_query_execution_service("set_environment_service", environment_service)
        self._maybe_call_main_brain_orchestrator("set_environment_service", environment_service)

    def set_query_execution_service(
        self,
        query_execution_service: KernelQueryExecutionService | None,
    ) -> None:
        if query_execution_service is None:
            query_execution_service = KernelQueryExecutionService(
                session_backend=self._session_backend,
                memory_manager=self._memory_manager,
                mcp_manager=self._mcp_manager,
                tool_bridge=self._tool_bridge,
                environment_service=self._environment_service,
            )
        self._query_execution_service = query_execution_service
        self._sync_query_execution_service(
            session_backend=self._session_backend,
            memory_manager=self._memory_manager,
            mcp_manager=self._mcp_manager,
            tool_bridge=self._tool_bridge,
            environment_service=self._environment_service,
            kernel_dispatcher=self._kernel_dispatcher,
        )
        self._sync_main_brain_orchestrator(
            session_backend=self._session_backend,
            query_execution_service=self._query_execution_service,
            environment_service=self._environment_service,
        )

    def set_main_brain_chat_service(
        self,
        main_brain_chat_service: MainBrainChatService | None,
    ) -> None:
        self._main_brain_chat_service = main_brain_chat_service or MainBrainChatService(
            session_backend=self._session_backend,
        )
        self._maybe_call_main_brain_chat_service(
            "set_session_backend",
            self._session_backend,
        )

    def set_main_brain_orchestrator(
        self,
        main_brain_orchestrator: MainBrainOrchestrator | None,
    ) -> None:
        self._main_brain_orchestrator = main_brain_orchestrator or MainBrainOrchestrator(
            query_execution_service=self._query_execution_service,
            session_backend=self._session_backend,
            environment_service=self._environment_service,
        )
        self._sync_main_brain_orchestrator(
            session_backend=self._session_backend,
            query_execution_service=self._query_execution_service,
            environment_service=self._environment_service,
        )

    def set_restart_callback(self, restart_callback: Callable[[], Any] | None) -> None:
        self._restart_callback = restart_callback

    def set_in_type_converters(
        self,
        converters: dict[str, Callable] | None,
    ) -> None:
        self._in_type_converters = converters

    def set_out_type_converters(
        self,
        converters: dict[str, Callable] | None,
    ) -> None:
        self._out_type_converters = converters

    def _sync_query_execution_service(
        self,
        *,
        session_backend: Any,
        memory_manager: MemoryManager | None,
        mcp_manager: Any | None,
        tool_bridge: Any | None,
        environment_service: Any | None,
        kernel_dispatcher: Any | None,
    ) -> None:
        self._maybe_call_query_execution_service("set_session_backend", session_backend)
        self._maybe_call_query_execution_service("set_memory_manager", memory_manager)
        self._maybe_call_query_execution_service("set_mcp_manager", mcp_manager)
        self._maybe_call_query_execution_service("set_tool_bridge", tool_bridge)
        self._maybe_call_query_execution_service(
            "set_environment_service",
            environment_service,
        )
        self._maybe_call_query_execution_service(
            "set_kernel_dispatcher",
            kernel_dispatcher,
        )

    def _sync_main_brain_orchestrator(
        self,
        *,
        session_backend: Any,
        query_execution_service: KernelQueryExecutionService | None,
        environment_service: Any | None,
    ) -> None:
        self._maybe_call_main_brain_orchestrator("set_session_backend", session_backend)
        self._maybe_call_main_brain_orchestrator(
            "set_query_execution_service",
            query_execution_service,
        )
        self._maybe_call_main_brain_orchestrator(
            "set_environment_service",
            environment_service,
        )

    def _maybe_call_query_execution_service(self, method_name: str, *args: Any) -> None:
        method = getattr(self._query_execution_service, method_name, None)
        if callable(method):
            method(*args)

    def _maybe_call_main_brain_chat_service(self, method_name: str, *args: Any) -> None:
        method = getattr(self._main_brain_chat_service, method_name, None)
        if callable(method):
            method(*args)

    def _maybe_call_main_brain_orchestrator(self, method_name: str, *args: Any) -> None:
        method = getattr(self._main_brain_orchestrator, method_name, None)
        if callable(method):
            method(*args)

    def _resolve_request_owner_agent_id(self, request: AgentRequest) -> str | None:
        resolver = getattr(
            self._query_execution_service,
            "resolve_request_owner_agent_id",
            None,
        )
        if callable(resolver):
            try:
                owner_agent_id = resolver(request=request)
            except TypeError:
                owner_agent_id = resolver(request)
            except Exception:
                logger.exception("Failed to resolve request owner agent id")
                return None
            if isinstance(owner_agent_id, str) and owner_agent_id.strip():
                return owner_agent_id.strip()
        return None

    async def handle_query(
        self,
        *,
        msgs: list[Any],
        request: AgentRequest,
        kernel_task_id: str | None = None,
        skip_kernel_admission: bool = False,
        transient_input_message_ids: set[str] | None = None,
    ) -> AsyncIterator[tuple[Msg, bool]]:
        query = extract_main_brain_intake_text(msgs)
        interaction_mode = _resolve_interaction_mode(request)
        effective_interaction_mode = _resolve_effective_interaction_mode(
            request=request,
            msgs=msgs,
            query=query,
        )
        _set_request_runtime_value(
            request,
            "_copaw_requested_interaction_mode",
            interaction_mode,
        )
        _set_request_runtime_value(
            request,
            "_copaw_resolved_interaction_mode",
            effective_interaction_mode,
        )
        if effective_interaction_mode == "orchestrate":
            _set_request_runtime_value(request, "interaction_mode", "orchestrate")
        elif effective_interaction_mode == "chat":
            _set_request_runtime_value(request, "interaction_mode", "chat")

        last_output_summary = None
        managed_by_kernel_dispatcher = False
        session_id = request.session_id
        user_id = request.user_id
        channel = getattr(request, "channel", DEFAULT_CHANNEL)
        owner_agent_id = self._resolve_request_owner_agent_id(request)
        try:
            if effective_interaction_mode == "needs_human":
                yield _needs_human_mode_choice_message(query=query), True
                return

            if effective_interaction_mode == "chat":
                async for msg, last in self._main_brain_chat_service.execute_stream(
                    msgs=msgs,
                    request=request,
                ):
                    last_output_summary = summarize_stream_message(msg)
                    yield msg, last
                return
            name = _initial_turn_title(msgs)
            if query and is_command(query):
                logger.info("Command path: %s", query.strip()[:50])
                if (
                    self._kernel_dispatcher is not None
                    and not skip_kernel_admission
                    and kernel_task_id is None
                ):
                    try:
                        capability_ref, risk_level = infer_turn_capability_and_risk(query)
                        admitted = self._submit_interactive_task(
                            request_id=getattr(request, "id", None),
                            session_id=session_id,
                            user_id=user_id,
                            channel=channel,
                            query_preview=(query or name),
                            capability_ref=capability_ref,
                            risk_level=risk_level,
                            owner_agent_id=owner_agent_id,
                            payload={
                                "request": _request_payload(request),
                                "channel": channel,
                                "user_id": user_id,
                                "session_id": session_id,
                                "dispatch_events": False,
                            },
                        )
                        kernel_task_id = admitted.task_id
                        _set_request_runtime_value(
                            request,
                            "_copaw_kernel_task_id",
                            kernel_task_id,
                        )
                        managed_by_kernel_dispatcher = admitted.phase == "executing"
                        if admitted.phase == "waiting-confirm":
                            yield (
                                _approval_required_message(
                                    query=query,
                                    decision_request_id=admitted.decision_request_id,
                                ),
                                True,
                            )
                            return
                        if admitted.phase != "executing":
                            yield (
                                _admission_blocked_message(
                                    summary=admitted.summary or admitted.error,
                                ),
                                True,
                            )
                            return
                    except Exception:
                        logger.exception("Kernel dispatcher failed to admit command task")

                async for msg, last in run_command_path(
                    request=request,
                    msgs=msgs,
                    session_backend=self._session_backend,
                    memory_manager=self._memory_manager,
                    restart_callback=self._restart_callback,
                ):
                    last_output_summary = summarize_stream_message(msg)
                    yield msg, last

                if managed_by_kernel_dispatcher and kernel_task_id is not None:
                    try:
                        self._kernel_dispatcher.complete_task(
                            kernel_task_id,
                            summary=last_output_summary or "Command completed",
                            metadata={"source": "kernel-turn-executor"},
                        )
                    except Exception:
                        logger.exception("Kernel dispatcher failed to complete command task")
                return

            if (
                self._kernel_dispatcher is not None
                and not skip_kernel_admission
                and kernel_task_id is None
            ):
                try:
                    admitted = self._submit_interactive_task(
                        request_id=getattr(request, "id", None),
                        session_id=session_id,
                        user_id=user_id,
                        channel=channel,
                        query_preview=(query or name),
                        owner_agent_id=owner_agent_id,
                        payload={
                            "request": _request_payload(request),
                            "channel": channel,
                            "user_id": user_id,
                            "session_id": session_id,
                            "dispatch_events": False,
                        },
                    )
                    kernel_task_id = admitted.task_id
                    _set_request_runtime_value(
                        request,
                        "_copaw_kernel_task_id",
                        kernel_task_id,
                    )
                    managed_by_kernel_dispatcher = admitted.phase == "executing"
                    if admitted.phase == "waiting-confirm":
                        yield (
                            _approval_required_message(
                                query=query,
                                decision_request_id=admitted.decision_request_id,
                            ),
                            True,
                        )
                        return
                    if admitted.phase != "executing":
                        yield (
                            _admission_blocked_message(
                                summary=admitted.summary or admitted.error,
                            ),
                            True,
                        )
                        return
                except Exception:
                    logger.exception("Kernel dispatcher failed to admit query")

            async for msg, last in self._main_brain_orchestrator.execute_stream(
                msgs=msgs,
                request=request,
                kernel_task_id=kernel_task_id,
                transient_input_message_ids=transient_input_message_ids,
            ):
                last_output_summary = summarize_stream_message(msg)
                yield msg, last

            if managed_by_kernel_dispatcher and kernel_task_id is not None:
                try:
                    self._kernel_dispatcher.complete_task(
                        kernel_task_id,
                        summary=last_output_summary or "Query completed",
                        metadata={"source": "kernel-turn-executor"},
                    )
                except Exception:
                    logger.exception("Kernel dispatcher failed to complete query")

        except asyncio.CancelledError as exc:
            logger.info("query_handler: %s cancelled!", session_id)
            if managed_by_kernel_dispatcher and kernel_task_id is not None:
                try:
                    self._kernel_dispatcher.fail_task(
                        kernel_task_id,
                        error="查询在完成前已被取消。",
                    )
                except Exception:
                    logger.exception("Kernel dispatcher failed to record cancellation")
            raise RuntimeError("任务已取消。") from exc
        except Exception as exc:
            exc = normalize_runtime_exception(exc)  # type: ignore[assignment]
            if managed_by_kernel_dispatcher and kernel_task_id is not None:
                try:
                    self._kernel_dispatcher.fail_task(
                        kernel_task_id,
                        error=str(exc),
                    )
                except Exception:
                    logger.exception("Kernel dispatcher failed to record failure")
            debug_dump_path = write_query_error_dump(
                request=request,
                exc=exc,
                locals_=locals(),
            )
            path_hint = f"\n(Details:  {debug_dump_path})" if debug_dump_path else ""
            logger.exception("Error in query handler: %s%s", exc, path_hint)
            if debug_dump_path:
                setattr(exc, "debug_dump_path", debug_dump_path)
                if hasattr(exc, "add_note"):
                    exc.add_note(f"(Details:  {debug_dump_path})")
                suffix = f"\n(Details:  {debug_dump_path})"
                exc.args = (
                    (f"{exc.args[0]}{suffix}" if exc.args else suffix.strip()),
                ) + exc.args[1:]
            raise

    def _submit_interactive_task(
        self,
        *,
        request_id: str | None,
        session_id: str,
        user_id: str,
        channel: str,
        query_preview: str | None,
        capability_ref: str = "system:dispatch_query",
        risk_level: str = "auto",
        owner_agent_id: str | None = None,
        payload: dict[str, object] | None = None,
    ):
        dispatcher = self._kernel_dispatcher
        if dispatcher is None:
            raise RuntimeError("Kernel dispatcher is not available")
        task_payload = {
            "session_id": session_id,
            "user_id": user_id,
            "channel": channel,
            "query_preview": query_preview,
        }
        if isinstance(payload, dict):
            task_payload.update(payload)
        task = KernelTask(
            id=_kernel_query_task_id(
                request_id=request_id,
                session_id=session_id,
                user_id=user_id,
                channel=channel,
            ),
            title=query_preview or f"Query from {user_id}@{channel}",
            capability_ref=capability_ref,
            environment_ref=f"session:{channel}:{session_id}",
            owner_agent_id=owner_agent_id or "copaw-agent-runner",
            risk_level=risk_level,
            payload=task_payload,
        )
        admitted = dispatcher.submit(task)
        logger.info(
            "Kernel admitted %s task %s (phase=%s)",
            capability_ref,
            task.id,
            admitted.phase,
        )
        return admitted

    async def stream_request(
        self,
        request: AgentRequest | dict[str, Any],
        *,
        kernel_task_id: str | None = None,
        skip_kernel_admission: bool = False,
        transient_input_message_ids: set[str] | None = None,
    ) -> AsyncIterator[Event]:
        if isinstance(request, dict):
            request = AgentRequest(**request)

        request.session_id = request.session_id or str(uuid.uuid4())
        request.user_id = request.user_id or request.session_id

        msgs = message_to_agentscope_msg(
            request.input,
            type_converters=self._in_type_converters,
        )
        if not isinstance(msgs, list):
            msgs = [msgs]

        requested_interaction_mode = _resolve_interaction_mode(request)
        resolved_interaction_mode = _resolve_effective_interaction_mode(
            request=request,
            msgs=msgs,
            query=extract_main_brain_intake_text(msgs),
        )
        _set_request_runtime_value(
            request,
            "_copaw_requested_interaction_mode",
            requested_interaction_mode,
        )
        _set_request_runtime_value(
            request,
            "_copaw_resolved_interaction_mode",
            resolved_interaction_mode,
        )

        seq_gen = SequenceNumberGenerator()
        response = AgentResponse(id=request.id)
        response.session_id = request.session_id
        yield seq_gen.yield_with_sequence(response)
        yield seq_gen.yield_with_sequence(response.in_progress())

        error = None
        resolved_mode_message_id = None
        try:
            async for event in adapt_agentscope_message_stream(
                source_stream=self.handle_query(
                    msgs=msgs,
                    request=request,
                    kernel_task_id=kernel_task_id,
                    skip_kernel_admission=skip_kernel_admission,
                    transient_input_message_ids=transient_input_message_ids,
                ),
                type_converters=self._out_type_converters,
            ):
                if getattr(event, "object", None) == "message":
                    message_id = getattr(event, "id", None)
                    if resolved_mode_message_id is None:
                        resolved_mode_message_id = str(message_id or "")
                    if message_id and str(message_id) == resolved_mode_message_id:
                        existing = getattr(event, "metadata", None)
                        meta: dict[str, Any]
                        if isinstance(existing, dict):
                            meta = {}
                            for key, value in existing.items():
                                if isinstance(key, str):
                                    meta[key] = value
                        else:
                            meta = {}
                        meta.setdefault(
                            "resolved_interaction_mode",
                            resolved_interaction_mode,
                        )
                        try:
                            event.metadata = meta
                        except Exception:
                            logger.debug(
                                "Failed to attach resolved interaction mode metadata to event",
                            )
                if event.status == RunStatus.Completed and event.object == "message":
                    response.add_new_message(event)
                yield seq_gen.yield_with_sequence(event)
        except Exception as exc:
            exc = normalize_runtime_exception(exc)  # type: ignore[assignment]
            if not isinstance(exc, AppBaseException):
                exc = UnknownAgentException(original_exception=exc)
            error_code = getattr(exc, "ui_title", exc.code)
            error = Error(code=error_code, message=exc.message)
            logger.error("%s: %s", error.model_dump(), traceback.format_exc())

        usage = _extract_response_usage(response)
        if usage is not None:
            response.usage = usage
            effective_kernel_task_id = getattr(
                request,
                "_copaw_kernel_task_id",
                kernel_task_id,
            )
            recorder = getattr(
                self._query_execution_service,
                "record_turn_usage",
                None,
            )
            interaction_mode = str(
                getattr(
                    request,
                    "_copaw_resolved_interaction_mode",
                    _resolve_interaction_mode(request),
                )
                or ""
            ).strip().lower()
            if interaction_mode != "chat" and callable(recorder):
                try:
                    recorder(
                        request=request,
                        kernel_task_id=effective_kernel_task_id,
                        usage=usage,
                    )
                except Exception:
                    logger.exception("Failed to persist interactive query usage")

        if error:
            yield seq_gen.yield_with_sequence(response.failed(error))
        else:
            yield seq_gen.yield_with_sequence(response.completed())


def _kernel_query_task_id(
    *,
    request_id: str | None,
    session_id: str,
    user_id: str,
    channel: str,
) -> str:
    safe_session_id = session_id.replace("/", "_")
    safe_request_id = (
        request_id.replace("/", "_")
        if isinstance(request_id, str) and request_id.strip()
        else uuid.uuid4().hex[:12]
    )
    return f"query:session:{channel}:{user_id}:{safe_session_id}:{safe_request_id}"


__all__ = ["KernelTurnExecutor", "summarize_stream_message"]
