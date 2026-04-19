# -*- coding: utf-8 -*-
"""Kernel-owned query execution service."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections.abc import AsyncIterator
from typing import Any

from agentscope.message import Msg, TextBlock
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import ToolResponse

from ..agents.react_agent import (
    CoPawAgent,
    bind_reasoning_tool_choice_resolver,
    bind_tool_execution_delegate,
    bind_tool_preflight,
)
from ..agents.tools import (
    bind_browser_evidence_sink,
    bind_desktop_evidence_sink,
    bind_file_evidence_sink,
    bind_shell_evidence_sink,
)
from ..app.channels.schema import DEFAULT_CHANNEL
from ..app.runtime_agentscope import build_env_context
from ..config import load_config
from ..constant import WORKING_DIR
from ..industry.chat_writeback import (
    ChatWritebackPlan,
    build_chat_writeback_plan_from_payload,
)
from ..industry.identity import (
    EXECUTION_CORE_AGENT_ID,
    EXECUTION_CORE_ROLE_ID,
    is_execution_core_agent_id,
    is_execution_core_role_id,
    normalize_industry_role_id,
)
from ..industry.prompting import (
    build_evidence_contract_lines,
    build_role_execution_contract_lines,
    build_task_mode_contract_lines,
    build_team_operating_model_lines,
    describe_industry_task_mode,
    infer_industry_task_mode,
)
from ..state import GovernanceControlRecord
from ..state.execution_feedback import collect_recent_execution_feedback
from ..state.strategy_memory_service import resolve_strategy_payload
from ..utils.runtime_routes import decision_route as _runtime_decision_route
from ..utils.runtime_routes import task_route as _runtime_task_route
from .query_execution_intent_policy import (
    is_hypothetical_control_text as _is_hypothetical_control_text,
    looks_like_goal_setting_text as _looks_like_goal_setting_text,
)
from .query_execution_confirmation import (
    _build_query_resume_request,
    _execution_feedback_prompt_lines,
    _query_confirmation_request_context,
    _query_confirmation_required_message,
    _runtime_decision_actions,
)
from .query_execution_writeback import (
    _build_chat_writeback_plan_from_model_decision,
    _is_explicit_risky_execution_confirmation,
    _normalize_chat_writeback_targets,
    _resolve_chat_writeback_model_decision,
    _resolve_team_role_gap_action_request,
    _should_attempt_formal_chat_writeback,
    _should_surface_team_role_gap_notice,
    _should_trigger_industry_kickoff,
    _team_role_gap_notice_message,
    _team_role_gap_resolution_message,
)
from .lease_heartbeat import LeaseHeartbeat
from .models import KernelTask
from .runtime_outcome import (
    normalize_runtime_summary,
    query_checkpoint_outcome,
    should_block_runtime_error,
)
from .teammate_resolution import resolve_teammate_target

logger = logging.getLogger(__name__)

_RISKY_WORKFLOW_ACTION = "__risky_workflow__"
_HIGH_RISK_BROWSER_ACTIONS = frozenset()
_CONTEXTUAL_BROWSER_RISK_ACTIONS = frozenset(
    {
        "click",
        "fill_form",
        "guided_surface",
        "press_key",
        "select_option",
        "type",
    }
)
_HIGH_RISK_DESKTOP_ACTIONS = frozenset(
    {
        _RISKY_WORKFLOW_ACTION,
    }
)
_CONTEXTUAL_DESKTOP_RISK_ACTIONS = frozenset(
    {
        "click",
        "press_keys",
        "type_text",
    }
)
_RISKY_SEMANTIC_TOKENS = frozenset(
    {
        "transfer",
        "转账",
        "汇款",
        "打款",
        "remit",
        "wire",
        "withdraw",
        "withdrawal",
        "提现",
        "出金",
    }
)
_RISKY_SHORTCUT_TOKENS = frozenset()
_RISKY_BROWSER_CONTEXT_KEYS = (
    "button",
    "element",
    "fields_json",
    "key",
    "prompt_text",
    "ref",
    "selector",
    "text",
    "url",
    "values_json",
)
_RISKY_DESKTOP_CONTEXT_KEYS = (
    "button",
    "executable",
    "keys",
    "text",
    "title",
    "title_contains",
    "title_regex",
)
_RISKY_BROWSER_WORKFLOW_ACTION = _RISKY_WORKFLOW_ACTION
_RISKY_DESKTOP_WORKFLOW_ACTION = _RISKY_WORKFLOW_ACTION

_REQUESTED_CHAT_ACTIONS = frozenset(
    {
        "confirm_risky_actuation",
        "create_task",
        "inspect_host",
        "kickoff_execution",
        "show_team_role_gap",
        "approve_team_role_gap",
        "reject_team_role_gap",
        "submit_human_assist",
        "writeback_strategy",
        "writeback_backlog",
        "writeback_schedule",
    }
)
_CHAT_ACTION_ALIAS_MAP = {
    "confirm": "confirm_risky_actuation",
    "confirm_continue": "confirm_risky_actuation",
    "confirm_risky_actuation": "confirm_risky_actuation",
    "task": "create_task",
    "create_task": "create_task",
    "inspect": "inspect_host",
    "inspect_host": "inspect_host",
    "host": "inspect_host",
    "kickoff": "kickoff_execution",
    "kickoff_execution": "kickoff_execution",
    "gap": "show_team_role_gap",
    "show_gap": "show_team_role_gap",
    "show_team_role_gap": "show_team_role_gap",
    "approve_gap": "approve_team_role_gap",
    "gap_approve": "approve_team_role_gap",
    "approve_team_role_gap": "approve_team_role_gap",
    "reject_gap": "reject_team_role_gap",
    "gap_reject": "reject_team_role_gap",
    "reject_team_role_gap": "reject_team_role_gap",
    "writeback_strategy": "writeback_strategy",
    "writeback_backlog": "writeback_backlog",
    "writeback_schedule": "writeback_schedule",
}


@dataclass(slots=True)
class _ResidentQueryAgent:
    cache_key: str
    signature: str
    session_id: str
    user_id: str
    channel: str
    owner_agent_id: str
    agent: CoPawAgent


@dataclass(slots=True)
class _DelegationFirstGuard:
    owner_agent_id: str
    teammates: tuple[dict[str, str | None], ...]
    unlocked: bool = False
    delegation_receipts: list[dict[str, str | None]] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return bool(self.teammates)

    @property
    def locked(self) -> bool:
        return self.active and not self.unlocked

    def teammate_preview(self, limit: int = 5) -> list[dict[str, str | None]]:
        return [dict(item) for item in self.teammates[: max(1, limit)]]

    def teammate_summary(self, limit: int = 5) -> str:
        labels: list[str] = []
        for teammate in self.teammates[: max(1, limit)]:
            agent_id = _first_non_empty(teammate.get("agent_id")) or "unknown"
            role_name = _first_non_empty(
                teammate.get("role_name"),
                teammate.get("role_id"),
            )
            if role_name:
                labels.append(f"{agent_id} ({role_name})")
            else:
                labels.append(agent_id)
        if len(self.teammates) > limit:
            labels.append(f"... (+{len(self.teammates) - limit} more)")
        return ", ".join(labels)

    def mark_delegation(
        self,
        *,
        target_agent_id: str,
        target_role_id: str | None,
        target_role_name: str | None,
        capability_id: str,
    ) -> None:
        self.delegation_receipts.append(
            {
                "target_agent_id": target_agent_id,
                "target_role_id": target_role_id,
                "target_role_name": target_role_name,
                "capability_id": capability_id,
            },
        )
        self.unlocked = True

def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _normalize_agent_candidate(value: Any) -> str | None:
    text = _first_non_empty(value)
    if text in {None, "default", "anonymous"}:
        return None
    return text


def _field_value(value: Any, *names: str) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value.get(name)
        if hasattr(value, name):
            return getattr(value, name)
    return None


def _json_tool_response(payload: dict[str, Any]) -> ToolResponse:
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            ),
        ],
        metadata={"format": "json"},
    )


def _tool_response_text(response: ToolResponse) -> str:
    parts: list[str] = []
    for block in response.content:
        raw_block = block
        if isinstance(raw_block, dict):
            if raw_block.get("type") == "text" and raw_block.get("text"):
                parts.append(str(raw_block.get("text")))
            continue
        block_type = getattr(raw_block, "type", None)
        if block_type == "text":
            text = getattr(raw_block, "text", None)
            if text:
                parts.append(str(text))
    return "\n".join(parts).strip()


def _response_to_text(response: Any) -> str:
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
            else:
                text = getattr(block, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


async def _materialize_model_response(response: Any) -> Any:
    if not hasattr(response, "__aiter__"):
        return response
    last_item: Any | None = None
    async for item in response:  # type: ignore[misc]
        last_item = item
    return last_item if last_item is not None else response


def _structured_tool_payload(
    value: Any,
    *,
    default_error: str,
) -> dict[str, Any]:
    if isinstance(value, ToolResponse):
        text = _tool_response_text(value)
        if text:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                return parsed
            return {"success": False, "error": text}
        return {"success": False, "error": default_error}
    payload = _mapping_value(value)
    if payload:
        return payload
    return {
        "success": False,
        "error": default_error,
        "raw_type": type(value).__name__,
    }


def _enrich_delegate_task_payload(
    *,
    result: dict[str, Any],
    resolved_agent_id: str,
) -> None:
    result.setdefault("target_agent_id", resolved_agent_id)
    if result.get("dispatch_status") is None and isinstance(result.get("phase"), str):
        result["dispatch_status"] = result.get("phase")
    result.setdefault("child_task_id", None)
    result.setdefault("latest_result_summary", result.get("summary"))
    output = result.get("output")
    if not isinstance(output, dict):
        return
    if "error_code" in output and "error_code" not in result:
        result["error_code"] = output.get("error_code")
    target_agent = (
        output.get("target_agent")
        if isinstance(output.get("target_agent"), dict)
        else None
    )
    child_task = (
        output.get("child_task")
        if isinstance(output.get("child_task"), dict)
        else None
    )
    dispatch_result = (
        output.get("dispatch_result")
        if isinstance(output.get("dispatch_result"), dict)
        else None
    )
    result.setdefault(
        "target_agent_id",
        _first_non_empty(
            output.get("target_agent_id"),
            target_agent.get("agent_id") if target_agent else None,
            child_task.get("owner_agent_id") if child_task else None,
        ),
    )
    result.setdefault(
        "child_task_id",
        _first_non_empty(
            output.get("child_task_id"),
            child_task.get("id") if child_task else None,
        ),
    )
    result.setdefault(
        "dispatch_status",
        _first_non_empty(
            output.get("dispatch_status"),
            dispatch_result.get("phase") if dispatch_result else None,
        ),
    )
    result.setdefault(
        "latest_result_summary",
        _first_non_empty(
            output.get("latest_result_summary"),
            dispatch_result.get("summary") if dispatch_result else None,
        ),
    )


def _mapping_value(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = [value]
    normalized: list[str] = []
    for item in items:
        text = _first_non_empty(item)
        if text is not None:
            normalized.append(text)
    return normalized


def _clamp_unit_float(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numeric))


def _normalize_chat_intent_kind(value: Any) -> str:
    normalized = (_first_non_empty(value) or "chat").strip().lower()
    if normalized in {"chat", "discussion", "status-query", "execute-task"}:
        return normalized
    return "chat"


def _normalize_risky_actuation_surface(value: Any) -> str | None:
    normalized = _first_non_empty(value)
    if normalized is None:
        return None
    lowered = normalized.strip().lower()
    if lowered in {"browser", "desktop", "auto"}:
        return lowered
    return None


def _normalize_team_role_gap_action(value: Any) -> str | None:
    normalized = _first_non_empty(value)
    if normalized is None:
        return None
    lowered = normalized.strip().lower()
    if lowered in {"approve", "reject"}:
        return lowered
    return None


def _extract_message_text(msg: Any) -> str | None:
    if isinstance(msg, str):
        return msg.strip() or None

    get_text_content = getattr(msg, "get_text_content", None)
    if callable(get_text_content):
        try:
            text = get_text_content()
        except Exception:
            text = None
        normalized = _first_non_empty(text)
        if normalized is not None:
            return normalized

    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") != "text":
                    continue
                text = item.get("text")
            else:
                if getattr(item, "type", None) != "text":
                    continue
                text = getattr(item, "text", None)
            normalized = _first_non_empty(text)
            if normalized is not None:
                parts.append(normalized)
        if parts:
            return "\n".join(parts)
    return None


def _message_query_text(msgs: list[Any]) -> str | None:
    parts: list[str] = []
    for msg in msgs:
        text = _extract_message_text(msg)
        if text:
            parts.append(text)
    if not parts:
        return None
    return "\n".join(parts[-4:]).strip() or None


def _normalize_requested_action(value: Any) -> str | None:
    text = _first_non_empty(value)
    if text is None:
        return None
    normalized = text.strip().lower().replace("-", "_")
    if normalized.startswith("/"):
        normalized = normalized[1:]
    normalized = _CHAT_ACTION_ALIAS_MAP.get(normalized, normalized)
    if normalized in _REQUESTED_CHAT_ACTIONS:
        return normalized
    return None


def _normalize_requested_actions(value: Any) -> list[str]:
    normalized: list[str] = []
    for item in _string_list(value):
        action = _normalize_requested_action(item)
        if action is not None and action not in normalized:
            normalized.append(action)
    return normalized


def _request_requested_actions(request: Any) -> set[str]:
    return set(_normalize_requested_actions(getattr(request, "requested_actions", None)))


def _request_has_requested_action(request: Any, *actions: str) -> bool:
    requested = _request_requested_actions(request)
    if not requested:
        return False
    normalized_targets = {
        action
        for action in (
            _normalize_requested_action(item)
            for item in actions
        )
        if action is not None
    }
    return bool(requested & normalized_targets)


def _extract_leading_chat_action_hints(
    text: str | None,
) -> tuple[list[str], str | None]:
    normalized_text = _first_non_empty(text)
    if normalized_text is None:
        return [], None
    remaining = normalized_text.strip()
    actions: list[str] = []
    while remaining.startswith("/"):
        parts = remaining.split(maxsplit=1)
        command = parts[0]
        action = _normalize_requested_action(command)
        if action is None:
            break
        if action not in actions:
            actions.append(action)
        remaining = parts[1].strip() if len(parts) > 1 else ""
    return actions, remaining or None


def _normalize_browser_tool_action(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str:
    action = _first_non_empty(kwargs.get("action"))
    if action is None and args:
        action = _first_non_empty(args[0])
    return (action or "").strip().lower()


def _normalize_desktop_tool_action(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str:
    action = _first_non_empty(kwargs.get("action"), kwargs.get("tool"))
    if action is None and args:
        action = _first_non_empty(args[0])
    return (action or "").strip().lower()


def _iter_tool_context_fragments(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip().lower()
        return [text] if text else []
    if isinstance(value, dict):
        parts: list[str] = []
        for item in value.values():
            parts.extend(_iter_tool_context_fragments(item))
        return parts
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for item in value:
            parts.extend(_iter_tool_context_fragments(item))
        return parts
    return []


def _tool_context_fragments(
    kwargs: dict[str, Any],
    *,
    keys: tuple[str, ...],
) -> list[str]:
    fragments: list[str] = []
    for key in keys:
        if key not in kwargs:
            continue
        fragments.extend(_iter_tool_context_fragments(kwargs.get(key)))
    return fragments


def _matched_risky_semantic_tokens(fragments: list[str]) -> set[str]:
    matches: set[str] = set()
    for fragment in fragments:
        for token in _RISKY_SEMANTIC_TOKENS:
            if token in fragment:
                matches.add(token)
    return matches


def _matched_risky_shortcuts(fragments: list[str]) -> set[str]:
    matches: set[str] = set()
    for fragment in fragments:
        normalized = fragment.replace(" ", "")
        for token in _RISKY_SHORTCUT_TOKENS:
            if token in normalized:
                matches.add(token)
    return matches


def _risky_tool_context_signature(
    *,
    tool_name: str,
    action: str,
    fragments: list[str],
    matched_tokens: set[str],
) -> str:
    payload = {
        "tool_name": tool_name,
        "action": action,
        "matched_tokens": sorted(matched_tokens),
        "context": sorted(set(fragments)),
    }
    return hashlib.sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
    ).hexdigest()


def _risky_tool_confirmation_state(
    *,
    tool_name: str,
    action: str,
    kwargs: dict[str, Any],
) -> tuple[bool, str | None]:
    normalized_tool = (tool_name or "").strip().lower()
    normalized_action = (action or "").strip().lower()
    if normalized_tool == "browser_use":
        if normalized_action in _HIGH_RISK_BROWSER_ACTIONS:
            return True, None
        if normalized_action not in _CONTEXTUAL_BROWSER_RISK_ACTIONS:
            return False, None
        fragments = _tool_context_fragments(kwargs, keys=_RISKY_BROWSER_CONTEXT_KEYS)
        matched_tokens = _matched_risky_semantic_tokens(fragments)
        if normalized_action in {"type", "guided_surface"} and bool(kwargs.get("submit")):
            matched_tokens.add("submit")
            fragments.append("submit")
        if not matched_tokens:
            return False, None
        return True, _risky_tool_context_signature(
            tool_name=normalized_tool,
            action=normalized_action,
            fragments=fragments,
            matched_tokens=matched_tokens,
        )
    if normalized_tool == "desktop_actuation":
        if normalized_action in _HIGH_RISK_DESKTOP_ACTIONS:
            return True, None
        if normalized_action not in _CONTEXTUAL_DESKTOP_RISK_ACTIONS:
            return False, None
        fragments = _tool_context_fragments(kwargs, keys=_RISKY_DESKTOP_CONTEXT_KEYS)
        matched_tokens = _matched_risky_semantic_tokens(fragments)
        matched_tokens.update(_matched_risky_shortcuts(fragments))
        if not matched_tokens:
            return False, None
        return True, _risky_tool_context_signature(
            tool_name=normalized_tool,
            action=normalized_action,
            fragments=fragments,
            matched_tokens=matched_tokens,
        )
    return False, None


def _risky_workflow_action_for_tool(tool_name: str) -> str:
    normalized = (tool_name or "").strip().lower()
    if normalized == "desktop_actuation":
        return _RISKY_DESKTOP_WORKFLOW_ACTION
    return _RISKY_BROWSER_WORKFLOW_ACTION


def _risky_tool_surface_label(tool_name: str | None) -> str:
    normalized = (tool_name or "").strip().lower()
    if normalized == "browser_use":
        return "网页代操"
    if normalized == "desktop_actuation":
        return "桌面代操"
    return "代操"


def _risky_tool_workflow_label(tool_name: str | None) -> str:
    normalized = (tool_name or "").strip().lower()
    if normalized == "browser_use":
        return "网页流程"
    if normalized == "desktop_actuation":
        return "桌面流程"
    return "代操流程"


def _risky_tool_action_label(tool_name: str | None, action: str) -> str:
    normalized = (tool_name or "").strip().lower()
    if normalized == "desktop_actuation":
        return _desktop_action_label(action)
    return _browser_action_label(action)


def _browser_action_label(action: str) -> str:
    labels = {
        _RISKY_WORKFLOW_ACTION: "继续当前网页流程",
        "click": "点击页面控件",
        "drag": "拖拽页面元素",
        "eval": "执行页面脚本",
        "evaluate": "执行页面脚本",
        "file_upload": "上传文件",
        "fill_form": "填写表单",
        "handle_dialog": "处理页面弹窗",
        "press_key": "发送按键输入",
        "run_code": "执行页面代码",
        "select_option": "选择页面选项",
        "type": "输入页面文本",
    }
    return labels.get(action, action or "浏览器动作")


def _desktop_action_label(action: str) -> str:
    labels = {
        _RISKY_WORKFLOW_ACTION: "继续当前桌面流程",
        "click": "点击桌面控件",
        "close_window": "关闭桌面窗口",
        "focus_window": "聚焦桌面窗口",
        "launch_application": "启动桌面应用",
        "press_keys": "发送桌面按键",
        "type_text": "输入桌面文本",
        "wait_for_window": "等待桌面窗口",
    }
    return labels.get(action, action or "桌面动作")


def _matching_risky_tool_actions(*, tool_name: str, action: str) -> tuple[str, ...]:
    normalized = (action or "").strip().lower()
    if not normalized:
        return (_RISKY_WORKFLOW_ACTION,)
    if normalized == _RISKY_WORKFLOW_ACTION:
        if (tool_name or "").strip().lower() == "browser_use":
            return (_RISKY_WORKFLOW_ACTION, *sorted(_HIGH_RISK_BROWSER_ACTIONS))
        return (_RISKY_WORKFLOW_ACTION,)
    if (
        (tool_name or "").strip().lower() == "browser_use"
        and normalized in _HIGH_RISK_BROWSER_ACTIONS
    ):
        return (normalized, _RISKY_BROWSER_WORKFLOW_ACTION)
    return (normalized,)


def _query_task_payload_mapping(task: Any) -> dict[str, Any]:
    payload = getattr(task, "payload", None)
    return dict(payload) if isinstance(payload, dict) else {}


def _knowledge_line(chunk: Any) -> str:
    title = _first_non_empty(getattr(chunk, "title", None), getattr(chunk, "document_id", None))
    summary = _first_non_empty(
        getattr(chunk, "summary", None),
        getattr(chunk, "content_excerpt", None),
        getattr(chunk, "content", None),
    )
    source_ref = _first_non_empty(getattr(chunk, "source_ref", None))
    text = summary or ""
    if len(text) > 180:
        text = f"{text[:177].rstrip()}..."
    if source_ref:
        return f"- {title}: {text} [source: {source_ref}]"
    return f"- {title}: {text}"


def _merged_capability_ids(
    *,
    tool_capability_ids: set[str] | None,
    skill_names: set[str] | None,
    mcp_client_keys: list[str] | None,
    system_capability_ids: set[str] | None,
) -> list[str]:
    merged: set[str] = set(tool_capability_ids or set())
    merged.update(f"skill:{name}" for name in (skill_names or set()))
    merged.update(f"mcp:{key}" for key in (mcp_client_keys or []))
    merged.update(system_capability_ids or set())
    return sorted(item for item in merged if item)


def _prompt_capability_bucket(
    capability_id: str,
    *,
    source_kind: str,
) -> str:
    if source_kind == "system":
        if capability_id in {
            "system:dispatch_query",
            "system:delegate_task",
        }:
            return "system_dispatch"
        return "system_governance"
    if source_kind == "tool":
        return "tools"
    if source_kind == "skill":
        return "skills"
    if source_kind == "mcp":
        return "mcp"
    return "other"


def _prompt_capability_label(capability_id: str, *, name: str) -> str:
    normalized_name = _first_non_empty(name)
    if normalized_name is not None and normalized_name != capability_id:
        return normalized_name
    for prefix in ("tool:", "skill:", "mcp:", "system:"):
        if capability_id.startswith(prefix):
            return capability_id[len(prefix) :]
    return capability_id


def _prompt_capability_entry_label(value: Any) -> str:
    entry = _mapping_value(value)
    return _first_non_empty(entry.get("label"), entry.get("id")) or "unknown"


def _infer_capability_source_kind(capability_id: str) -> str:
    if capability_id.startswith("tool:"):
        return "tool"
    if capability_id.startswith("mcp:"):
        return "mcp"
    if capability_id.startswith("skill:"):
        return "skill"
    if capability_id.startswith("system:"):
        return "system"
    return "unknown"


def _mount_supports_desktop_actuation(mount: Any) -> bool:
    capability_id = str(getattr(mount, "id", "") or "").strip().lower()
    source_kind = str(getattr(mount, "source_kind", "") or "").strip().lower()
    if capability_id.startswith("tool:desktop_") and capability_id != "tool:desktop_screenshot":
        return True
    if source_kind != "mcp":
        return False
    fragments = [
        capability_id,
        str(getattr(mount, "name", "") or ""),
        str(getattr(mount, "summary", "") or ""),
        str(getattr(mount, "executor_ref", "") or ""),
    ]
    tags = getattr(mount, "tags", None)
    if isinstance(tags, list):
        fragments.extend(str(item) for item in tags if str(item).strip())
    metadata = getattr(mount, "metadata", None)
    if isinstance(metadata, dict):
        fragments.extend(
            str(value)
            for value in metadata.values()
            if isinstance(value, (str, int, float)) and str(value).strip()
        )
    haystack = " ".join(fragment.lower() for fragment in fragments if fragment)
    return any(
        token in haystack
        for token in ("desktop", "mouse", "keyboard", "click", "typing", "keypress")
    )


def _capability_name_from_id(capability_id: str, *, prefix: str) -> str:
    if capability_id.startswith(prefix):
        return capability_id[len(prefix) :]
    return capability_id


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _message_preview(msg: Msg) -> str | None:
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        preview = content.strip()
        return preview[:240] if preview else None
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_value = str(item.get("text") or "").strip()
                if text_value:
                    parts.append(text_value)
            elif hasattr(item, "type") and getattr(item, "type", None) == "text":
                # Handle TextBlock-like objects without isinstance check (Python 3.12+ TypedDict compat)
                text_value = str(getattr(item, "text", "") or "").strip()
                if text_value:
                    parts.append(text_value)
        if parts:
            return "\n".join(parts)[:240]
    preview = str(content or "").strip()
    return preview[:240] if preview else None


__all__ = [name for name in globals() if not name.startswith("__")]
