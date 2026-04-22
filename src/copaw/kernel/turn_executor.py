# -*- coding: utf-8 -*-
"""Kernel-native turn executor for query dispatch."""
from __future__ import annotations

import asyncio
import logging
import re
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

from ..app.channels.schema import DEFAULT_CHANNEL
from ..app.runtime_commands import (
    infer_turn_capability_and_risk,
    is_command,
    run_command_path,
)
from ..industry.identity import is_execution_core_role_id
from ..providers.model_diagnostics import normalize_runtime_exception
from .lease_heartbeat import LeaseHeartbeat
from .runtime_outcome import (
    build_execution_diagnostics,
    is_cancellation_runtime_error,
)
from .main_brain_intake import (
    extract_main_brain_intake_text,
    materialize_requested_actions_main_brain_intake_contract,
    normalize_main_brain_runtime_context,
    read_attached_main_brain_intake_contract,
    resolve_main_brain_intake_contract,
    resolve_request_main_brain_intake_contract,
)
from .main_brain_chat_service import MainBrainChatService
from .main_brain_orchestrator import (
    MainBrainOrchestrator,
    read_attached_main_brain_cognitive_surface,
)
from .main_brain_intent_shell import (
    MainBrainIntentShell,
    build_requested_main_brain_intent_shell,
    detect_main_brain_intent_shell,
)
from .query_error_dump import write_query_error_dump
from .models import KernelTask
from .query_execution import KernelQueryExecutionService
from .query_execution_shared import (
    _first_non_empty,
    _is_hypothetical_control_text,
)
from .query_execution_writeback import (
    ChatWritebackDecisionModelTimeoutError,
    ChatWritebackDecisionModelUnavailableError,
)
from .runtime_coordination import AssignmentExecutorRuntimeCoordinator
from ..memory.conversation_compaction_service import ConversationCompactionService

logger = logging.getLogger(__name__)


def _should_propagate_main_brain_intake_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            ChatWritebackDecisionModelTimeoutError,
            ChatWritebackDecisionModelUnavailableError,
        ),
    )

_COGNITIVE_ACKNOWLEDGEMENTS = frozenset(
    {
        "ok",
        "okay",
        "yes",
        "好",
        "好的",
        "可以",
        "确认",
        "同意",
    }
)
_COGNITIVE_FOLLOWUP_TOKENS = (
    "continue",
    "replan",
    "冲突",
    "处理",
    "推进",
    "拍板",
    "按这个",
    "继续",
    "补缺口",
    "解决",
    "缺口",
    "补上",
    "重排",
)
_COGNITIVE_PRESSURE_HINTS = (
    "conflict",
    "replan",
    "冲突",
    "缺口",
    "补缺口",
    "重排",
)
_SHORT_CHAT_INSPECTION_TOKENS = (
    "帮我看一下",
    "帮我看下",
    "看一下",
    "看下",
    "看看",
)
_DIRECT_AGENT_EXECUTION_TARGET_TOKENS = (
    "browser capability",
    "mounted browser",
    "browser",
    "screenshot",
    "desktop",
    "浏览器",
    "截图",
    "桌面",
)
_DIRECT_AGENT_EXECUTION_ACTION_TOKENS = (
    "use ",
    "open ",
    "navigate",
    "click",
    "type ",
    "fill ",
    "upload",
    "save ",
    "take a screenshot",
    "打开",
    "点击",
    "输入",
    "填写",
    "上传",
    "保存",
    "截图",
    "执行",
)
_DIRECT_AGENT_EXECUTION_ORDER_TOKENS = (
    "right now",
    "do not answer until",
    "don't answer until",
    "then report",
    "现在就",
    "立刻",
    "先别回复",
    "不要回答直到",
    "再汇报",
)
_DIRECT_AGENT_EXECUTION_RESOURCE_RE = re.compile(
    r"(https?://|file://|[a-z]:\\\\|\.png\b|\.jpg\b|\.jpeg\b|\.pdf\b)",
    re.IGNORECASE,
)


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


def _request_has_unresolved_cognitive_pressure(*, request: Any) -> bool:
    surface = read_attached_main_brain_cognitive_surface(request=request)
    if not surface:
        return False
    return bool(
        surface.get("needs_replan")
        or surface.get("has_unresolved_conflicts")
        or surface.get("has_unresolved_holes")
        or list(surface.get("replan_reasons") or [])
    )


def _is_plain_acknowledgement(text: str) -> bool:
    normalized = str(text or "").strip().rstrip("。.!！?")
    return normalized.lower() in _COGNITIVE_ACKNOWLEDGEMENTS


def _looks_like_cognitive_followup(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    if _is_plain_acknowledgement(normalized):
        return True
    return any(token in normalized for token in _COGNITIVE_FOLLOWUP_TOKENS)


def _is_short_chat_inspection(text: str) -> bool:
    normalized = str(text or "").strip().lower().rstrip("。.!！?")
    if not normalized or len(normalized) > 12:
        return False
    return any(token in normalized for token in _SHORT_CHAT_INSPECTION_TOKENS)


def _looks_like_direct_industry_agent_execution_request(
    *,
    request: AgentRequest,
    text: str,
) -> bool:
    session_kind = str(getattr(request, "session_kind", "") or "").strip().lower()
    if session_kind != "industry-agent-chat":
        return False
    if is_execution_core_role_id(getattr(request, "industry_role_id", None)):
        return False
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    if _is_hypothetical_control_text(normalized):
        return False
    if "?" in normalized or "？" in normalized:
        return False
    has_target = any(
        token in normalized for token in _DIRECT_AGENT_EXECUTION_TARGET_TOKENS
    )
    if not has_target:
        return False
    has_action = any(
        token in normalized for token in _DIRECT_AGENT_EXECUTION_ACTION_TOKENS
    )
    if not has_action:
        return False
    has_order = any(
        token in normalized for token in _DIRECT_AGENT_EXECUTION_ORDER_TOKENS
    )
    has_resource = bool(_DIRECT_AGENT_EXECUTION_RESOURCE_RE.search(normalized))
    return has_order or has_resource


def _assistant_mentions_cognitive_pressure(msgs: list[Any]) -> bool:
    for message in reversed(msgs):
        role = str(getattr(message, "role", "") or "").strip().lower()
        if role != "assistant":
            continue
        text = ""
        getter = getattr(message, "get_text_content", None)
        if callable(getter):
            try:
                text = str(getter() or "")
            except Exception:
                text = ""
        if not text:
            text = str(getattr(message, "content", "") or "")
        normalized = text.strip().lower()
        if normalized and any(token in normalized for token in _COGNITIVE_PRESSURE_HINTS):
            return True
        return False
    return False


def _normalized_requested_actions(request: AgentRequest) -> tuple[str, ...]:
    requested_actions = getattr(request, "requested_actions", None)
    if not isinstance(requested_actions, list):
        return ()
    values = {
        str(item or "").strip().lower()
        for item in requested_actions
        if str(item or "").strip()
    }
    return tuple(sorted(values))


def _interaction_mode_cache_key(
    *,
    request: AgentRequest,
    msgs: list[Any],
    query: str | None,
) -> str:
    text = str(extract_main_brain_intake_text(msgs) or query or "").strip().lower()
    requested_actions = ",".join(_normalized_requested_actions(request))
    requested_mode_hint = str(
        getattr(request, "_copaw_requested_mode_hint", "") or "",
    ).strip().lower()
    has_cognitive_pressure = _request_has_unresolved_cognitive_pressure(
        request=request,
    )
    attached_intake_contract = read_attached_main_brain_intake_contract(request=request)
    has_continuity_contract = _request_has_active_confirmation_or_continuity(
        request=request,
    )
    return (
        f"text:{text}|actions:{requested_actions}|"
        f"mode_hint:{requested_mode_hint}|"
        f"pressure:{'1' if has_cognitive_pressure else '0'}|"
        f"attached:{'1' if attached_intake_contract is not None else '0'}|"
        f"continuity:{'1' if has_continuity_contract else '0'}"
    )


def _prepare_request_intent_shell(
    *,
    request: AgentRequest,
    msgs: list[Any],
    query: str | None,
) -> MainBrainIntentShell:
    requested_shell = build_requested_main_brain_intent_shell(
        getattr(request, "mode_hint", None),
    )
    resolved_shell = requested_shell
    if resolved_shell is None:
        text = str(extract_main_brain_intake_text(msgs) or query or "").strip()
        resolved_shell = detect_main_brain_intent_shell(text)
    _set_request_runtime_value(request, "_copaw_main_brain_intent_shell", resolved_shell)
    _set_request_runtime_value(
        request,
        "_copaw_requested_mode_hint",
        resolved_shell.mode_hint if resolved_shell.active else "",
    )
    _set_request_runtime_value(
        request,
        "_copaw_resolved_mode_hint",
        resolved_shell.mode_hint if resolved_shell.active else "",
    )
    return resolved_shell


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


def _request_has_active_confirmation_or_continuity(*, request: Any) -> bool:
    if _first_non_empty(
        getattr(request, "continuity_token", None),
        getattr(request, "decision_request_id", None),
        getattr(request, "pending_decision_request_id", None),
        getattr(request, "human_assist_task_id", None),
        getattr(request, "resume_checkpoint_id", None),
        getattr(request, "resume_mailbox_id", None),
        getattr(request, "resume_kernel_task_id", None),
    ):
        return True
    runtime_context = normalize_main_brain_runtime_context(
        getattr(request, "_copaw_main_brain_runtime_context", None),
    )
    if not runtime_context:
        return False
    recovery = runtime_context.get("recovery")
    if isinstance(recovery, dict) and _first_non_empty(
        recovery.get("mode"),
        recovery.get("checkpoint_id"),
        recovery.get("mailbox_id"),
        recovery.get("kernel_task_id"),
    ):
        return True
    environment = runtime_context.get("environment")
    if not isinstance(environment, dict):
        return False
    if bool(environment.get("resume_ready")):
        return True
    continuity_token = _first_non_empty(environment.get("continuity_token"))
    continuity_source = _first_non_empty(environment.get("continuity_source"))
    if continuity_token is None:
        return False
    return continuity_source in {
        "continuity-token",
        "session-lease",
        "session-live-handle",
    }


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


def _admission_blocked_message(
    *,
    phase: str | None,
    error: str | None = None,
    summary: str | None,
) -> Msg:
    diagnostics = build_execution_diagnostics(
        phase=phase,
        error=error,
        summary=summary,
        default_remediation_summary="运行准入已被治理控制阻断。",
    )
    detail = diagnostics["remediation_summary"] or "运行准入已被治理控制阻断。"
    blocked_next_step = diagnostics["blocked_next_step"]
    if blocked_next_step:
        detail = f"{detail}\nNext step: {blocked_next_step}"
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


async def _resolve_auto_chat_mode(
    *,
    query: str | None,
    request: AgentRequest,
    msgs: list[Any],
    intent_shell: MainBrainIntentShell | None = None,
) -> str:
    """Return the effective interaction mode for chat surface."""
    requested_actions = _normalized_requested_actions(request)
    if requested_actions:
        orchestrate_actions = {
            str(item or "").strip()
            for item in requested_actions
            if str(item or "").strip()
        }
        orchestrate_actions.discard("submit_human_assist")
        if orchestrate_actions:
            intake_contract = materialize_requested_actions_main_brain_intake_contract(
                request=request,
                msgs=msgs,
            )
            if intake_contract is not None:
                _set_request_runtime_value(
                    request,
                    "_copaw_main_brain_intake_contract",
                    intake_contract,
                )
            return "orchestrate"

    text = str(extract_main_brain_intake_text(msgs) or query or "").strip()
    if not text:
        return "chat"
    if _is_hypothetical_control_text(text):
        return "chat"
    if intent_shell is not None and intent_shell.mode_hint in {"plan", "review"}:
        return "chat"
    if intent_shell is not None and intent_shell.mode_hint in {"resume", "verify"}:
        if _request_has_active_confirmation_or_continuity(request=request):
            return "orchestrate"
        return "chat"
    has_cognitive_pressure = _request_has_unresolved_cognitive_pressure(request=request)
    has_buddy_runtime = bool(_first_non_empty(getattr(request, "buddy_profile_id", None)))
    if has_buddy_runtime and not _is_plain_acknowledgement(text) and not _is_short_chat_inspection(text):
        return "orchestrate"
    if not has_cognitive_pressure and _is_plain_acknowledgement(text):
        return "chat"
    if not has_cognitive_pressure and _is_short_chat_inspection(text):
        return "chat"
    if _looks_like_direct_industry_agent_execution_request(
        request=request,
        text=text,
    ):
        return "orchestrate"
    intake_contract = None
    if _first_non_empty(
        getattr(request, "industry_instance_id", None),
        getattr(request, "control_thread_id", None),
        getattr(request, "industry_role_id", None),
    ):
        try:
            intake_contract = await resolve_request_main_brain_intake_contract(
                request=request,
                msgs=msgs,
            )
        except Exception as exc:
            if _should_propagate_main_brain_intake_error(exc):
                raise
            logger.debug("Main-brain attached intake contract resolution failed", exc_info=True)
        if intake_contract is None:
            try:
                intake_contract = await resolve_main_brain_intake_contract(
                    text=text,
                    msgs=msgs,
                )
            except Exception as exc:
                if _should_propagate_main_brain_intake_error(exc):
                    raise
                logger.debug("Main-brain model intake contract resolution failed", exc_info=True)
    if intake_contract is not None:
        _set_request_runtime_value(
            request,
            "_copaw_main_brain_intake_contract",
            intake_contract,
        )
        if intake_contract.should_route_to_orchestrate:
            return "orchestrate"
    if _request_has_active_confirmation_or_continuity(request=request):
        return "orchestrate"
    if has_cognitive_pressure and (
        (
            _is_plain_acknowledgement(text)
            and _assistant_mentions_cognitive_pressure(msgs)
        )
        or _looks_like_cognitive_followup(text)
    ):
        return "orchestrate"
    return "chat"


async def _resolve_effective_interaction_mode(
    *,
    request: AgentRequest,
    msgs: list[Any],
    query: str | None,
    intent_shell: MainBrainIntentShell | None = None,
) -> str:
    interaction_mode = _resolve_interaction_mode(request)
    if interaction_mode != "auto":
        return interaction_mode
    return await _resolve_auto_chat_mode(
        query=query,
        request=request,
        msgs=msgs,
        intent_shell=intent_shell,
    )


async def _prepare_request_interaction_mode(
    *,
    request: AgentRequest,
    msgs: list[Any],
    query: str | None,
) -> tuple[str, str]:
    intent_shell = _prepare_request_intent_shell(
        request=request,
        msgs=msgs,
        query=query,
    )
    current_requested_interaction_mode = _resolve_interaction_mode(request)
    current_cache_key = _interaction_mode_cache_key(
        request=request,
        msgs=msgs,
        query=query,
    )
    requested_interaction_mode = str(
        getattr(request, "_copaw_requested_interaction_mode", "") or "",
    ).strip().lower()
    resolved_interaction_mode = str(
        getattr(request, "_copaw_resolved_interaction_mode", "") or "",
    ).strip().lower()
    cached_mode_key = str(
        getattr(request, "_copaw_interaction_mode_cache_key", "") or "",
    ).strip()
    if (
        requested_interaction_mode == current_requested_interaction_mode
        and requested_interaction_mode in {"auto", "chat", "orchestrate"}
        and resolved_interaction_mode in {"chat", "orchestrate"}
        and cached_mode_key == current_cache_key
    ):
        return requested_interaction_mode, resolved_interaction_mode
    if (
        requested_interaction_mode in {"auto", "chat", "orchestrate"}
        and resolved_interaction_mode in {"chat", "orchestrate"}
    ):
        requested_interaction_mode = ""
        resolved_interaction_mode = ""

    requested_interaction_mode = current_requested_interaction_mode
    resolved_interaction_mode = await _resolve_effective_interaction_mode(
        request=request,
        msgs=msgs,
        query=query,
        intent_shell=intent_shell,
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
    _set_request_runtime_value(
        request,
        "_copaw_interaction_mode_cache_key",
        current_cache_key,
    )
    if resolved_interaction_mode == "orchestrate":
        _set_request_runtime_value(request, "interaction_mode", "orchestrate")
    elif resolved_interaction_mode == "chat":
        _set_request_runtime_value(request, "interaction_mode", "chat")
    return requested_interaction_mode, resolved_interaction_mode


class KernelTurnExecutor:
    """Execute one conversational turn without falling back to runner logic."""

    def __init__(
        self,
        *,
        session_backend: Any,
        conversation_compaction_service: ConversationCompactionService | None = None,
        mcp_manager: Any | None = None,
        kernel_dispatcher: Any | None = None,
        tool_bridge: Any | None = None,
        environment_service: Any | None = None,
        query_execution_service: KernelQueryExecutionService | None = None,
        main_brain_chat_service: MainBrainChatService | None = None,
        main_brain_orchestrator: MainBrainOrchestrator | None = None,
        executor_runtime_coordinator: AssignmentExecutorRuntimeCoordinator | None = None,
        sidecar_release_service: Any | None = None,
        restart_callback: Callable[[], Any] | None = None,
        in_type_converters: dict[str, Callable] | None = None,
        out_type_converters: dict[str, Callable] | None = None,
    ) -> None:
        self._session_backend = session_backend
        self._conversation_compaction_service = conversation_compaction_service
        self._mcp_manager = mcp_manager
        self._kernel_dispatcher = kernel_dispatcher
        self._tool_bridge = tool_bridge
        self._environment_service = environment_service
        self._query_execution_service = query_execution_service or KernelQueryExecutionService(
            session_backend=session_backend,
            conversation_compaction_service=conversation_compaction_service,
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
            executor_runtime_coordinator=executor_runtime_coordinator,
        )
        self._executor_runtime_coordinator = executor_runtime_coordinator
        self._sync_query_execution_service(
            session_backend=session_backend,
            conversation_compaction_service=conversation_compaction_service,
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
        self._sidecar_release_service = sidecar_release_service
        self._in_type_converters = in_type_converters
        self._out_type_converters = out_type_converters

    def set_session_backend(self, session_backend: Any) -> None:
        self._session_backend = session_backend
        self._maybe_call_query_execution_service("set_session_backend", session_backend)
        self._maybe_call_main_brain_chat_service("set_session_backend", session_backend)
        self._maybe_call_main_brain_orchestrator("set_session_backend", session_backend)

    def set_conversation_compaction_service(
        self,
        conversation_compaction_service: ConversationCompactionService | None,
    ) -> None:
        self._conversation_compaction_service = conversation_compaction_service
        self._sync_query_execution_compaction_service(
            conversation_compaction_service,
        )

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
                conversation_compaction_service=self._conversation_compaction_service,
                mcp_manager=self._mcp_manager,
                tool_bridge=self._tool_bridge,
                environment_service=self._environment_service,
            )
        self._query_execution_service = query_execution_service
        self._sync_query_execution_service(
            session_backend=self._session_backend,
            conversation_compaction_service=self._conversation_compaction_service,
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
            executor_runtime_coordinator=self._executor_runtime_coordinator,
        )
        self._sync_main_brain_orchestrator(
            session_backend=self._session_backend,
            query_execution_service=self._query_execution_service,
            environment_service=self._environment_service,
        )

    def set_executor_runtime_coordinator(
        self,
        executor_runtime_coordinator: AssignmentExecutorRuntimeCoordinator | None,
    ) -> None:
        self._executor_runtime_coordinator = executor_runtime_coordinator
        self._maybe_call_main_brain_orchestrator(
            "set_executor_runtime_coordinator",
            executor_runtime_coordinator,
        )

    def set_restart_callback(self, restart_callback: Callable[[], Any] | None) -> None:
        self._restart_callback = restart_callback

    def set_sidecar_release_service(self, sidecar_release_service: Any | None) -> None:
        self._sidecar_release_service = sidecar_release_service

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
        conversation_compaction_service: ConversationCompactionService | None,
        mcp_manager: Any | None,
        tool_bridge: Any | None,
        environment_service: Any | None,
        kernel_dispatcher: Any | None,
    ) -> None:
        self._maybe_call_query_execution_service("set_session_backend", session_backend)
        self._sync_query_execution_compaction_service(
            conversation_compaction_service,
        )
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

    def _sync_query_execution_compaction_service(
        self,
        conversation_compaction_service: ConversationCompactionService | None,
    ) -> None:
        method = getattr(
            self._query_execution_service,
            "set_conversation_compaction_service",
            None,
        )
        if callable(method):
            method(conversation_compaction_service)

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
        self._maybe_call_main_brain_orchestrator(
            "set_executor_runtime_coordinator",
            self._executor_runtime_coordinator,
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

    def _admit_interactive_kernel_task(
        self,
        *,
        request: AgentRequest,
        kernel_task_id: str | None,
        skip_kernel_admission: bool,
        session_id: str,
        user_id: str,
        channel: str,
        query: str | None,
        name: str,
        owner_agent_id: str | None,
        capability_ref: str = "system:dispatch_query",
        risk_level: str = "auto",
        log_label: str,
    ) -> tuple[str | None, bool, tuple[Msg, bool] | None]:
        if (
            self._kernel_dispatcher is None
            or skip_kernel_admission
            or kernel_task_id is not None
        ):
            return kernel_task_id, False, None
        try:
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
                return kernel_task_id, managed_by_kernel_dispatcher, (
                    _approval_required_message(
                        query=query,
                        decision_request_id=admitted.decision_request_id,
                    ),
                    True,
                )
            if admitted.phase != "executing":
                return kernel_task_id, managed_by_kernel_dispatcher, (
                    _admission_blocked_message(
                        phase=admitted.phase,
                        error=admitted.error,
                        summary=admitted.summary,
                    ),
                    True,
                )
            return kernel_task_id, managed_by_kernel_dispatcher, None
        except Exception:
            logger.exception("Kernel dispatcher failed to admit %s", log_label)
            return kernel_task_id, False, None

    def _complete_managed_interactive_task(
        self,
        *,
        kernel_task_id: str | None,
        managed_by_kernel_dispatcher: bool,
        summary: str,
        log_label: str,
    ) -> None:
        if not managed_by_kernel_dispatcher or kernel_task_id is None:
            return
        try:
            self._kernel_dispatcher.complete_task(
                kernel_task_id,
                summary=summary,
                metadata={"source": "kernel-turn-executor"},
            )
        except Exception:
            logger.exception("Kernel dispatcher failed to complete %s", log_label)

    def _record_managed_interactive_terminal(
        self,
        *,
        kernel_task_id: str | None,
        managed_by_kernel_dispatcher: bool,
        error: str,
        cancellation_resolution: str = "查询在完成前已被取消。",
    ) -> None:
        if not managed_by_kernel_dispatcher or kernel_task_id is None:
            return
        try:
            if is_cancellation_runtime_error(error):
                cancel_task = getattr(self._kernel_dispatcher, "cancel_task", None)
                if callable(cancel_task):
                    cancel_task(
                        kernel_task_id,
                        resolution=cancellation_resolution,
                    )
                else:
                    self._kernel_dispatcher.fail_task(
                        kernel_task_id,
                        error=cancellation_resolution,
                    )
                return
            self._kernel_dispatcher.fail_task(
                kernel_task_id,
                error=error,
            )
        except Exception:
            logger.exception("Kernel dispatcher failed to record terminal outcome")

    def _build_managed_interactive_task_heartbeat(
        self,
        *,
        kernel_task_id: str | None,
        managed_by_kernel_dispatcher: bool,
    ) -> LeaseHeartbeat | None:
        if not managed_by_kernel_dispatcher or kernel_task_id is None:
            return None
        dispatcher = self._kernel_dispatcher
        heartbeat_task = getattr(dispatcher, "heartbeat_task", None)
        if not callable(heartbeat_task):
            return None
        timeout_seconds = getattr(
            getattr(dispatcher, "_config", None),
            "execution_timeout_seconds",
            None,
        )
        interval_seconds = 15.0
        if isinstance(timeout_seconds, (int, float)) and timeout_seconds > 0:
            interval_seconds = max(0.01, min(15.0, float(timeout_seconds) / 4.0))
        return LeaseHeartbeat(
            label=f"interactive-task:{kernel_task_id}",
            heartbeat=lambda: heartbeat_task(kernel_task_id),
            interval_seconds=interval_seconds,
        )

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
        _requested_interaction_mode, effective_interaction_mode = await _prepare_request_interaction_mode(
            request=request,
            msgs=msgs,
            query=query,
        )

        last_output_summary = None
        managed_by_kernel_dispatcher = False
        session_id = request.session_id
        user_id = request.user_id
        channel = getattr(request, "channel", DEFAULT_CHANNEL)
        owner_agent_id = self._resolve_request_owner_agent_id(request)
        try:
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
                capability_ref, risk_level = infer_turn_capability_and_risk(query)
                kernel_task_id, managed_by_kernel_dispatcher, terminal_message = (
                    self._admit_interactive_kernel_task(
                        request=request,
                        kernel_task_id=kernel_task_id,
                        skip_kernel_admission=skip_kernel_admission,
                        session_id=session_id,
                        user_id=user_id,
                        channel=channel,
                        query=query,
                        name=name,
                        owner_agent_id=owner_agent_id,
                        capability_ref=capability_ref,
                        risk_level=risk_level,
                        log_label="command task",
                    )
                )
                if terminal_message is not None:
                    yield terminal_message
                    return

                heartbeat = self._build_managed_interactive_task_heartbeat(
                    kernel_task_id=kernel_task_id,
                    managed_by_kernel_dispatcher=managed_by_kernel_dispatcher,
                )
                if heartbeat is None:
                    async for msg, last in run_command_path(
                        request=request,
                        msgs=msgs,
                        session_backend=self._session_backend,
                        conversation_compaction_service=self._conversation_compaction_service,
                        restart_callback=self._restart_callback,
                        executor_runtime_coordinator=self._executor_runtime_coordinator,
                        sidecar_release_service=self._sidecar_release_service,
                    ):
                        last_output_summary = summarize_stream_message(msg)
                        yield msg, last
                else:
                    async with heartbeat:
                        async for msg, last in run_command_path(
                            request=request,
                            msgs=msgs,
                            session_backend=self._session_backend,
                            conversation_compaction_service=self._conversation_compaction_service,
                            restart_callback=self._restart_callback,
                            executor_runtime_coordinator=self._executor_runtime_coordinator,
                            sidecar_release_service=self._sidecar_release_service,
                        ):
                            last_output_summary = summarize_stream_message(msg)
                            yield msg, last

                self._complete_managed_interactive_task(
                    kernel_task_id=kernel_task_id,
                    managed_by_kernel_dispatcher=managed_by_kernel_dispatcher,
                    summary=last_output_summary or "Command completed",
                    log_label="command task",
                )
                return

            kernel_task_id, managed_by_kernel_dispatcher, terminal_message = (
                self._admit_interactive_kernel_task(
                    request=request,
                    kernel_task_id=kernel_task_id,
                    skip_kernel_admission=skip_kernel_admission,
                    session_id=session_id,
                    user_id=user_id,
                    channel=channel,
                    query=query,
                    name=name,
                    owner_agent_id=owner_agent_id,
                    log_label="query",
                )
            )
            if terminal_message is not None:
                yield terminal_message
                return

            heartbeat = self._build_managed_interactive_task_heartbeat(
                kernel_task_id=kernel_task_id,
                managed_by_kernel_dispatcher=managed_by_kernel_dispatcher,
            )
            if heartbeat is None:
                async for msg, last in self._main_brain_orchestrator.execute_stream(
                    msgs=msgs,
                    request=request,
                    kernel_task_id=kernel_task_id,
                    transient_input_message_ids=transient_input_message_ids,
                ):
                    last_output_summary = summarize_stream_message(msg)
                    yield msg, last
            else:
                async with heartbeat:
                    async for msg, last in self._main_brain_orchestrator.execute_stream(
                        msgs=msgs,
                        request=request,
                        kernel_task_id=kernel_task_id,
                        transient_input_message_ids=transient_input_message_ids,
                    ):
                        last_output_summary = summarize_stream_message(msg)
                        yield msg, last

            self._complete_managed_interactive_task(
                kernel_task_id=kernel_task_id,
                managed_by_kernel_dispatcher=managed_by_kernel_dispatcher,
                summary=last_output_summary or "Query completed",
                log_label="query",
            )

        except asyncio.CancelledError as exc:
            logger.info("query_handler: %s cancelled!", session_id)
            self._record_managed_interactive_terminal(
                kernel_task_id=kernel_task_id,
                managed_by_kernel_dispatcher=managed_by_kernel_dispatcher,
                error="查询在完成前已被取消。",
            )
            raise RuntimeError("任务已取消。") from exc
        except Exception as exc:
            exc = normalize_runtime_exception(exc)  # type: ignore[assignment]
            self._record_managed_interactive_terminal(
                kernel_task_id=kernel_task_id,
                managed_by_kernel_dispatcher=managed_by_kernel_dispatcher,
                error=str(exc),
            )
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

        requested_interaction_mode, resolved_interaction_mode = await _prepare_request_interaction_mode(
            request=request,
            msgs=msgs,
            query=extract_main_brain_intake_text(msgs),
        )

        seq_gen = SequenceNumberGenerator()
        response = AgentResponse(id=request.id)
        response.session_id = request.session_id
        yield seq_gen.yield_with_sequence(response)
        yield seq_gen.yield_with_sequence(response.in_progress())

        error = None
        canceled = False
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
            if is_cancellation_runtime_error(getattr(exc, "message", str(exc))):
                canceled = True
                logger.info("stream_request: %s cancelled", request.session_id)
            else:
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
        elif canceled:
            yield seq_gen.yield_with_sequence(response.canceled())
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
