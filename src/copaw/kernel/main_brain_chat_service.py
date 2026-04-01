# -*- coding: utf-8 -*-
"""Lightweight main-brain chat service for pure conversational turns."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from agentscope.message import Msg, TextBlock, ThinkingBlock
from reme.memory.file_based.reme_in_memory_memory import ReMeInMemoryMemory

from .main_brain_intake import (
    extract_main_brain_intake_text,
)
from .main_brain_orchestrator import build_main_brain_cognitive_surface
from .main_brain_commit_service import MainBrainCommitService
from .main_brain_result_committer import MainBrainResultCommitter
from .main_brain_scope_snapshot_service import MainBrainScopeSnapshotService
from .main_brain_turn_result import MainBrainCommitState, MainBrainTurnResult
from ..providers.provider_manager import ProviderManager
from .query_execution_shared import (
    _first_non_empty,
    _materialize_model_response,
    _response_to_text,
)

if TYPE_CHECKING:
    from ..industry import IndustryService
    from ..memory import MemoryRecallService
    from .agent_profile_service import AgentProfileService

logger = logging.getLogger(__name__)

_PURE_CHAT_MEMORY_MAX_ITEMS = 24
_PURE_CHAT_SESSION_CACHE_TTL_SECONDS = 20 * 60
_PURE_CHAT_PERSIST_INTERVAL_SECONDS = 45
_PURE_CHAT_PERSIST_TURNS = 2
_PURE_CHAT_HISTORY_MAX_MESSAGES = 8
_PURE_CHAT_HISTORY_MAX_CHARS = 4200
_PURE_CHAT_HISTORY_MESSAGE_CHAR_LIMIT = 960
_PURE_CHAT_MODEL_KWARGS: dict[str, object] = {
    "temperature": 0.15,
    "max_tokens": 520,
}
_PURE_CHAT_EMPTY_REPLY_FALLBACK = (
    "我这轮没有拿到有效回复。你可以直接重试；"
    "如果你是在补充目标、约束或执行条件，我会继续整理并自动推进。"
)

_PURE_CHAT_SYSTEM_PROMPT = """你是 Spider Mesh 主脑，当前处于主脑聊天前台。
你的职责：理解需求、澄清歧义、判断轻重缓急、解释团队现状、先拆执行前方案，并判断是否该由主脑继续自动推进后台编排。
硬约束：
1. 不要声称已经派工、已经执行、已经写回、已经调用工具，除非上下文里真的出现了这些结果。
2. 不要向用户暴露任何内部工具名、函数名或调度实现细节。
3. 先给结论，再给必要理由，再给下一步；没有必要就不要铺背景。
4. 默认短答，优先控制在 3 到 6 句；除非用户明确要细讲，否则不要长篇解释。
5. 先把需求整理成执行前方案：目标、约束、已知条件、关键缺口、建议下一步。
6. 如果需求已经足够清楚且不涉及必须的人类边界，不要反复追问“是否开始执行”；默认按主脑自动推进来回答。
7. 如果仍缺关键参数，只追问最少的一组缺口，优先问会改变执行方向或风险边界的问题。
8. 对“月入10万且零亏损”这类结果口号，要主动改写成结构化执行目标：周期、资源基线、风险边界、验收指标、首轮验证。
9. 可以结合团队成员分工说明谁更适合承接，但不要编造还没发生的派工结果。
10. 回复优先直接、清楚、少废话，禁止职业化空话和重复总结。"""


class _ApproxTokenizer:
    def encode(self, text: str) -> list[int]:
        # Pure chat only needs a coarse estimation for memory compaction.
        byte_len = len((text or "").encode("utf-8"))
        tokens = max(1, byte_len // 4)
        return [0] * tokens


class _ApproxTokenCounter:
    def __init__(self) -> None:
        self.tokenizer = _ApproxTokenizer()


_PURE_CHAT_TOKEN_COUNTER = _ApproxTokenCounter()


def _get_pure_chat_token_counter() -> object:
    return _PURE_CHAT_TOKEN_COUNTER


def _compact_memory_state(state: object) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    content = state.get("content")
    if isinstance(content, list) and len(content) > _PURE_CHAT_MEMORY_MAX_ITEMS:
        trimmed = dict(state)
        trimmed["content"] = content[-_PURE_CHAT_MEMORY_MAX_ITEMS :]
        return trimmed
    return dict(state)


def _clip_text(value: object, *, limit: int = 160) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def _safe_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    namespace = getattr(value, "__dict__", None)
    if isinstance(namespace, dict):
        return dict(namespace)
    return {}


def _merge_stream_text(current_text: str, new_text: str) -> str:
    normalized = str(new_text or "")
    if not normalized:
        return current_text
    if not current_text:
        return normalized
    if normalized.startswith(current_text):
        return normalized
    if normalized == current_text:
        return current_text
    return f"{current_text}{normalized}"


def _safe_response_attr(response: object, name: str) -> object | None:
    try:
        return getattr(response, name, None)
    except (AttributeError, KeyError):
        return None


def _build_assistant_message(
    *,
    text: str,
    thinking: str | None = None,
    message_id: str | None = None,
    usage: object | None = None,
) -> Msg:
    content_blocks: list[object] = []
    normalized_thinking = str(thinking or "").strip()
    normalized_text = str(text or "").strip()
    if normalized_thinking:
        content_blocks.append(
            ThinkingBlock(type="thinking", thinking=normalized_thinking),
        )
    if normalized_text or not content_blocks:
        content_blocks.append(TextBlock(type="text", text=normalized_text))
    message = Msg(
        name="Spider Mesh",
        role="assistant",
        content=content_blocks,
    )
    if message_id:
        try:
            message.id = message_id
        except Exception:
            logger.debug("Failed to pin main-brain assistant message id")
    if usage is not None:
        try:
            message.usage = usage
        except Exception:
            logger.debug("Failed to attach main-brain assistant usage")
    return message


def _response_to_text_and_thinking(response: object) -> tuple[str, str]:
    content = _safe_response_attr(response, "content")
    direct_thinking = _safe_response_attr(response, "reasoning_content")
    text_parts: list[str] = []
    thinking_parts: list[str] = []
    if isinstance(direct_thinking, str) and direct_thinking.strip():
        thinking_parts.append(direct_thinking.strip())
    if isinstance(content, str):
        return content.strip(), "\n".join(thinking_parts).strip()
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type")
                text = block.get("text")
                thinking = block.get("thinking")
            else:
                block_type = getattr(block, "type", None)
                text = getattr(block, "text", None)
                thinking = getattr(block, "thinking", None)
            if block_type == "thinking":
                if isinstance(thinking, str) and thinking.strip():
                    thinking_parts.append(thinking.strip())
                continue
            if isinstance(text, str) and text.strip():
                text_parts.append(text.strip())
    return "\n".join(text_parts).strip(), "\n".join(thinking_parts).strip()


def _message_role(message: object) -> str:
    role = getattr(message, "role", None)
    if isinstance(role, str) and role.strip():
        return role.strip().lower()
    return ""


def _message_text(message: object) -> str:
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


def _extract_assignment_summary(
    agent_id: str,
    *,
    assignments: list[dict[str, Any]],
) -> str:
    if not agent_id:
        return ""
    for item in assignments:
        if not isinstance(item, dict):
            continue
        owners = {
            str(item.get("owner_agent_id") or "").strip(),
            str(item.get("target_agent_id") or "").strip(),
            str(item.get("assignee_agent_id") or "").strip(),
            str(item.get("agent_id") or "").strip(),
        }
        if agent_id not in owners:
            continue
        title = _first_non_empty(
            item.get("title"),
            item.get("summary"),
            item.get("task_title"),
        )
        status = _first_non_empty(item.get("status"), item.get("lifecycle_status"))
        if title and status:
            return f"{_clip_text(title, limit=80)}（{status}）"
        if title:
            return _clip_text(title, limit=80)
    return ""


def _format_team_roster(
    *,
    detail: object | None,
    agent_profile_service: AgentProfileService | None,
    industry_instance_id: str | None,
    owner_agent_id: str | None,
) -> list[str]:
    team_agents = list(
        (_safe_mapping(getattr(detail, "team", None)).get("agents") or [])
        if detail is not None
        else []
    )
    assignments = list(
        (_safe_mapping(detail).get("assignments") or []) if detail is not None else []
    )
    lines: list[str] = []
    seen_agent_ids: set[str] = set()
    for raw in team_agents[:12]:
        if not isinstance(raw, dict):
            continue
        agent_id = str(raw.get("agent_id") or "").strip()
        if agent_id:
            seen_agent_ids.add(agent_id)
        display_name = _first_non_empty(raw.get("name"), raw.get("role_name"), agent_id) or "未命名成员"
        role_name = _first_non_empty(raw.get("role_name"), raw.get("goal_kind")) or "未标注职责"
        responsibility = _first_non_empty(raw.get("role_summary"), raw.get("mission")) or "未提供"
        capability_bits = []
        allowed = raw.get("allowed_capabilities")
        if isinstance(allowed, list):
            capability_bits.extend(str(item).strip() for item in allowed if str(item).strip())
        preferred = raw.get("preferred_capability_families")
        if isinstance(preferred, list):
            capability_bits.extend(str(item).strip() for item in preferred if str(item).strip())
        capability_summary = "、".join(capability_bits[:4]) or "按其角色职责执行"
        assignment_summary = _extract_assignment_summary(
            agent_id,
            assignments=assignments,
        ) or "当前无显式派工"
        reports_to = str(raw.get("reports_to") or "").strip()
        escalate = (
            "跨角色冲突/高风险/需要拍板时回到主脑"
            if reports_to
            else "关键判断不清楚时回到主脑"
        )
        lines.append(
            (
                f"- {display_name} [{agent_id or 'unknown'}] | {role_name} | "
                f"职责：{_clip_text(responsibility, limit=70)} | "
                f"能力范围：{_clip_text(capability_summary, limit=70)} | "
                f"当前派工：{_clip_text(assignment_summary, limit=50)} | "
                f"回报时机：{escalate}"
            )
        )
    if lines:
        return lines
    if agent_profile_service is None:
        return []
    agents = (
        agent_profile_service.list_agents(
            industry_instance_id=industry_instance_id,
            limit=8,
        )
        if industry_instance_id
        else []
    )
    if not agents and owner_agent_id:
        owner = agent_profile_service.get_agent(owner_agent_id)
        agents = [owner] if owner is not None else []
    for profile in agents[:8]:
        if profile is None:
            continue
        agent_id = str(getattr(profile, "agent_id", "") or "").strip()
        if agent_id and agent_id in seen_agent_ids:
            continue
        capability_summary = "、".join(
            str(item).strip()
            for item in list(getattr(profile, "capabilities", []) or [])[:4]
            if str(item).strip()
        ) or "按其角色职责执行"
        lines.append(
            (
                f"- {getattr(profile, 'name', agent_id) or agent_id} [{agent_id or 'unknown'}] | "
                f"{_first_non_empty(getattr(profile, 'role_name', None), '未标注职责')} | "
                f"职责：{_clip_text(getattr(profile, 'role_summary', ''), limit=70) or '未提供'} | "
                f"能力范围：{_clip_text(capability_summary, limit=70)} | "
                f"当前焦点：{_clip_text(_first_non_empty(getattr(profile, 'current_focus', None), getattr(profile, 'current_goal', '')), limit=50) or '当前无显式焦点'} | "
                "回报时机：跨角色冲突/高风险/需要主脑拍板时回到主脑"
            )
        )
    return lines


def _format_runtime_snapshot(detail: object | None) -> str:
    if detail is None:
        return "暂无行业运行摘要。"
    payload = _safe_mapping(detail)
    execution = _safe_mapping(payload.get("execution"))
    current_cycle = _safe_mapping(payload.get("current_cycle"))
    cycle_line = _first_non_empty(
        current_cycle.get("title"),
        current_cycle.get("summary"),
        execution.get("current_focus"),
        execution.get("current_goal"),
    ) or "暂无明确 cycle"
    lane_lines = [
        _clip_text(
            _first_non_empty(item.get("title"), item.get("label"), item.get("summary"))
            or "未命名 lane",
            limit=60,
        )
        for item in list(payload.get("lanes") or [])[:3]
        if isinstance(item, dict)
    ]
    backlog_lines = [
        _clip_text(
            _first_non_empty(item.get("title"), item.get("summary")) or "未命名 backlog",
            limit=60,
        )
        for item in list(payload.get("backlog") or [])[:4]
        if isinstance(item, dict)
    ]
    assignment_lines = [
        _clip_text(
            _first_non_empty(item.get("title"), item.get("summary"), item.get("task_title"))
            or "未命名派工",
            limit=60,
        )
        for item in list(payload.get("assignments") or [])[:4]
        if isinstance(item, dict)
    ]
    report_lines = [
        _clip_text(
            _first_non_empty(item.get("summary"), item.get("headline"), item.get("title"))
            or "未命名汇报",
            limit=60,
        )
        for item in list(payload.get("agent_reports") or [])[:3]
        if isinstance(item, dict)
    ]
    parts = [
        f"- 当前周期：{cycle_line}",
        f"- 关键 lane：{'；'.join(lane_lines) if lane_lines else '暂无'}",
        f"- 待处理 backlog：{'；'.join(backlog_lines) if backlog_lines else '暂无'}",
        f"- 当前派工：{'；'.join(assignment_lines) if assignment_lines else '暂无'}",
        f"- 最新汇报：{'；'.join(report_lines) if report_lines else '暂无'}",
    ]
    return "\n".join(parts)


def _format_strategy_summary(detail: object | None) -> str:
    if detail is None:
        return "暂无正式战略摘要。"
    strategy_payload = _safe_mapping(getattr(detail, "strategy_memory", None))
    if not strategy_payload:
        strategy_payload = _safe_mapping(_safe_mapping(detail).get("strategy_memory"))
    if not strategy_payload:
        return "暂无正式战略摘要。"
    parts = [
        _clip_text(
            _first_non_empty(
                strategy_payload.get("title"),
                strategy_payload.get("north_star"),
                strategy_payload.get("mission"),
            ),
            limit=120,
        ),
        _clip_text(strategy_payload.get("summary"), limit=160),
    ]
    normalized = [item for item in parts if item]
    return " | ".join(normalized) if normalized else "暂无正式战略摘要。"


def _format_staffing_summary(detail: object | None) -> str:
    if detail is None:
        return "No active staffing state."
    staffing = _safe_mapping(getattr(detail, "staffing", None))
    if not staffing:
        staffing = _safe_mapping(_safe_mapping(detail).get("staffing"))
    if not staffing:
        return "No active staffing state."
    lines: list[str] = []
    active_gap = _safe_mapping(staffing.get("active_gap"))
    if active_gap:
        role_name = _first_non_empty(
            active_gap.get("target_role_name"),
            active_gap.get("target_role_id"),
        ) or "unassigned seat"
        kind = _first_non_empty(active_gap.get("kind")) or "routing-pending"
        lines.append(f"- Active staffing gap: {role_name} ({kind})")
        reason = _first_non_empty(active_gap.get("reason"))
        if reason:
            lines.append(f"- Gap reason: {_clip_text(reason, limit=120)}")
        requested_surfaces = [
            str(item).strip()
            for item in list(active_gap.get("requested_surfaces") or [])[:4]
            if str(item).strip()
        ]
        if requested_surfaces:
            lines.append(f"- Requested surfaces: {', '.join(requested_surfaces)}")
        decision_request_id = _first_non_empty(active_gap.get("decision_request_id"))
        if decision_request_id:
            lines.append(f"- Open decision id: {decision_request_id}")
    pending_proposals = [
        _safe_mapping(item)
        for item in list(staffing.get("pending_proposals") or [])
        if _safe_mapping(item)
    ]
    if pending_proposals:
        preview = ", ".join(
            _first_non_empty(
                item.get("target_role_name"),
                item.get("target_role_id"),
                item.get("kind"),
            )
            or "proposal"
            for item in pending_proposals[:3]
        )
        lines.append(f"- Pending staffing proposals: {preview}")
    temporary_seats = [
        _safe_mapping(item)
        for item in list(staffing.get("temporary_seats") or [])
        if _safe_mapping(item)
    ]
    if temporary_seats:
        preview = ", ".join(
            (
                f"{_first_non_empty(item.get('role_name'), item.get('role_id')) or 'temporary seat'}"
                f" [{_first_non_empty(item.get('status')) or 'ready'}]"
            )
            for item in temporary_seats[:3]
        )
        lines.append(f"- Temporary seats: {preview}")
    researcher = _safe_mapping(staffing.get("researcher"))
    if researcher:
        researcher_name = _first_non_empty(
            researcher.get("role_name"),
            researcher.get("agent_id"),
        ) or "researcher"
        researcher_status = _first_non_empty(researcher.get("status")) or "ready"
        pending_signal_count = researcher.get("pending_signal_count")
        researcher_line = f"- Researcher: {researcher_name} | status={researcher_status}"
        if isinstance(pending_signal_count, int):
            researcher_line = f"{researcher_line} | pending signals: {pending_signal_count}"
        lines.append(researcher_line)
    return "\n".join(lines) if lines else "No active staffing state."


def _format_cognitive_closure(
    *,
    detail: object | None,
    request: Any,
) -> str:
    surface = build_main_brain_cognitive_surface(detail=detail, request=request)
    if not surface:
        return "暂无正式 cognitive closure 状态。"
    conflicts = list(surface.get("conflicts") or [])
    holes = list(surface.get("holes") or [])
    latest_findings = list(surface.get("latest_findings") or [])
    replan_reasons = [
        str(item).strip()
        for item in list(surface.get("replan_reasons") or [])[:3]
        if str(item).strip()
    ]
    lines = [
        f"- needs_replan={'yes' if surface.get('needs_replan') else 'no'}",
        f"- unresolved conflicts={len(conflicts)}",
        f"- unresolved holes={len(holes)}",
    ]
    for reason in replan_reasons:
        lines.append(f"- replan reason: {_clip_text(reason, limit=120)}")
    for finding in latest_findings[:2]:
        headline = _first_non_empty(
            finding.get("headline"),
            finding.get("summary"),
            finding.get("report_id"),
        ) or "finding"
        followup = " | needs_followup=yes" if finding.get("needs_followup") else ""
        lines.append(f"- latest finding: {_clip_text(headline, limit=120)}{followup}")
    for conflict in conflicts[:2]:
        summary = _first_non_empty(conflict.get("summary"), conflict.get("kind")) or "conflict"
        lines.append(f"- conflict: {_clip_text(summary, limit=120)}")
    for hole in holes[:2]:
        summary = _first_non_empty(hole.get("summary"), hole.get("kind")) or "gap"
        lines.append(f"- gap: {_clip_text(summary, limit=120)}")
    return "\n".join(lines)


def _format_memory_hits(hits: list[object]) -> str:
    lines: list[str] = []
    for raw in hits[:4]:
        payload = _safe_mapping(raw)
        summary = _first_non_empty(
            payload.get("summary"),
            payload.get("content_excerpt"),
            payload.get("title"),
        )
        if not summary:
            continue
        title = _first_non_empty(payload.get("title"), payload.get("kind")) or "记忆"
        lines.append(f"- {title}: {_clip_text(summary, limit=120)}")
    return "\n".join(lines) if lines else "暂无额外受控记忆命中。"


def _truth_first_entry_timestamp(entry: object) -> object | None:
    for field_name in ("source_updated_at", "updated_at", "created_at"):
        value = getattr(entry, field_name, None)
        if value is not None:
            return value
    return None


def _sort_truth_first_entries(entries: list[object]) -> list[object]:
    return sorted(
        list(entries),
        key=lambda item: (
            _truth_first_entry_timestamp(item) is not None,
            _truth_first_entry_timestamp(item) or "",
        ),
        reverse=True,
    )


def _format_truth_first_entry_lines(entries: list[object], *, limit: int) -> str:
    lines: list[str] = []
    for entry in entries[: max(1, limit)]:
        title = _first_non_empty(getattr(entry, "title", None), "memory fact") or "memory fact"
        summary = _first_non_empty(
            getattr(entry, "summary", None),
            getattr(entry, "content_excerpt", None),
            getattr(entry, "content_text", None),
        )
        if summary:
            lines.append(f"- {title}: {_clip_text(summary, limit=120)}")
        else:
            lines.append(f"- {title}")
    return "\n".join(lines) if lines else "- No truth-first memory facts available."


def _format_truth_first_profile(
    *,
    scope_type: str,
    scope_id: str,
    entries: list[object],
) -> str:
    if not entries:
        return "- No truth-first profile available."
    latest = entries[0]
    headline = _first_non_empty(getattr(latest, "title", None), scope_id) or scope_id
    current_context = _first_non_empty(
        getattr(latest, "summary", None),
        getattr(latest, "content_excerpt", None),
        getattr(latest, "content_text", None),
    ) or "No current operating context."
    return "\n".join(
        [
            f"- Scope: {scope_type}/{scope_id}",
            f"- Current focus: {headline}",
            f"- Current operating context: {_clip_text(current_context, limit=160)}",
        ],
    )


@dataclass
class _PureChatSessionCacheEntry:
    snapshot: dict[str, Any]
    memory: ReMeInMemoryMemory
    last_used_at: float
    last_persisted_at: float
    turns_since_persist: int
    prompt_context_signature: str | None = None
    prompt_context_body: str | None = None
    dirty: bool = False


class MainBrainChatService:
    """Run lightweight pure-chat turns for the main brain."""

    def __init__(
        self,
        *,
        session_backend: Any,
        industry_service: IndustryService | None = None,
        agent_profile_service: AgentProfileService | None = None,
        memory_recall_service: MemoryRecallService | None = None,
        model_factory: Callable[[], object] | None = None,
        scope_snapshot_service: MainBrainScopeSnapshotService | None = None,
        commit_service: MainBrainCommitService | None = None,
    ) -> None:
        self._session_backend = session_backend
        self._industry_service = industry_service
        self._agent_profile_service = agent_profile_service
        self._memory_recall_service = memory_recall_service
        self._model_factory = model_factory or ProviderManager.get_active_chat_model
        self._scope_snapshot_service = scope_snapshot_service or MainBrainScopeSnapshotService(
            stable_prefix_builder=self._build_stable_prompt_prefix,
            stable_prefix_signature_builder=self._build_prompt_context_signature,
            scope_snapshot_builder=self._build_scope_snapshot_body,
            scope_snapshot_signature_builder=self._build_scope_snapshot_signature,
            scope_key_resolver=self._resolve_scope_snapshot_key,
        )
        self._commit_service = commit_service or MainBrainCommitService(
            session_backend=session_backend,
            action_handlers={
                "writeback_operating_truth": MainBrainResultCommitter(
                    industry_service=industry_service,
                ).commit_action,
                "create_backlog_item": MainBrainResultCommitter(
                    industry_service=industry_service,
                ).commit_action,
                "orchestrate_execution": MainBrainResultCommitter(
                    industry_service=industry_service,
                ).commit_action,
                "resume_execution": MainBrainResultCommitter(
                    industry_service=industry_service,
                ).commit_action,
                "submit_human_assist": MainBrainResultCommitter(
                    industry_service=industry_service,
                ).commit_action,
            },
            dirty_marker=self.mark_scope_snapshot_dirty,
        )
        set_owner = getattr(self._scope_snapshot_service, "set_owner", None)
        if callable(set_owner):
            set_owner(self)
        self._session_cache: dict[tuple[str, str], _PureChatSessionCacheEntry] = {}
        self._background_tasks: set[asyncio.Task[Any]] = set()

    def set_session_backend(self, session_backend: Any) -> None:
        self._session_backend = session_backend

    def mark_scope_snapshot_dirty(
        self,
        *,
        work_context_id: str | None = None,
        industry_instance_id: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        self._scope_snapshot_service.mark_dirty(
            work_context_id=work_context_id,
            industry_instance_id=industry_instance_id,
            agent_id=agent_id,
        )

    def get_persisted_commit_state(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> MainBrainCommitState | None:
        return self._commit_service.get_persisted_commit_state(
            session_id=session_id,
            user_id=user_id,
        )

    def _read_commit_state_from_snapshot(
        self,
        snapshot: dict[str, Any],
    ) -> MainBrainCommitState | None:
        payload = _safe_mapping(_safe_mapping(snapshot.get("main_brain")).get("phase2_commit"))
        if not payload:
            return None
        return MainBrainCommitState.model_validate(payload)

    def _persist_interrupted_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        cache_entry: _PureChatSessionCacheEntry | None,
        snapshot: dict[str, Any],
        now: float,
    ) -> None:
        if cache_entry is not None:
            self._persist_cache_entry_if_needed(
                session_id=session_id,
                user_id=user_id,
                cache_entry=cache_entry,
                force=True,
                now=now,
            )
            return
        self._save_session_snapshot(
            session_id=session_id,
            user_id=user_id,
            snapshot=snapshot,
        )

    async def execute_stream(
        self,
        *,
        msgs: list[Any],
        request: Any,
    ) -> AsyncIterator[tuple[Msg, bool]]:
        query = extract_main_brain_intake_text(msgs)
        session_id = str(getattr(request, "session_id", "") or "").strip()
        user_id = str(getattr(request, "user_id", "") or "").strip()
        cache_key = (session_id, user_id) if session_id and user_id else None
        now = time.time()
        cache_entry: _PureChatSessionCacheEntry | None = None
        if cache_key is not None:
            cache_entry = self._session_cache.get(cache_key)
            if cache_entry is not None and now - cache_entry.last_used_at > _PURE_CHAT_SESSION_CACHE_TTL_SECONDS:
                self._persist_cache_entry_if_needed(
                    session_id=session_id,
                    user_id=user_id,
                    cache_entry=cache_entry,
                    force=True,
                    now=now,
                )
                cache_entry = None
                self._session_cache.pop(cache_key, None)

        if cache_entry is None:
            snapshot = self._load_session_snapshot(session_id=session_id, user_id=user_id)
            memory = self._load_memory(snapshot)
            if cache_key is not None:
                cache_entry = _PureChatSessionCacheEntry(
                    snapshot=snapshot,
                    memory=memory,
                    last_used_at=now,
                    last_persisted_at=0.0,
                    turns_since_persist=0,
                    dirty=False,
                )
                self._session_cache[cache_key] = cache_entry
        else:
            cache_entry.last_used_at = now
            snapshot = cache_entry.snapshot
            memory = cache_entry.memory

        persisted_commit_state = self._read_commit_state_from_snapshot(snapshot)
        if persisted_commit_state is not None:
            self._set_request_runtime_value(
                request,
                "_copaw_main_brain_commit_state",
                persisted_commit_state,
            )

        prior_messages = await memory.get_memory(prepend_summary=False)
        prompt_messages = self._build_prompt_messages(
            request=request,
            query=query,
            prior_messages=prior_messages,
            current_messages=msgs,
            cache_entry=cache_entry,
        )
        assistant_message_id = uuid.uuid4().hex
        assistant_message: Msg | None = None
        assistant_usage: object | None = None
        reply_already_streamed = False
        model_result = MainBrainTurnResult.from_reply_text("")
        try:
            if msgs:
                await memory.add(msgs, allow_duplicates=False)
                snapshot = self._snapshot_with_memory(
                    snapshot=snapshot,
                    memory=memory,
                )
                if cache_entry is not None:
                    cache_entry.snapshot = snapshot
                    cache_entry.memory = memory
                    cache_entry.last_used_at = now
                    cache_entry.dirty = True
        except Exception:
            logger.exception("Failed to persist incoming main-brain chat messages")
        try:
            model = self._resolve_model()
            response = await self._invoke_model_response(
                model=model,
                prompt_messages=prompt_messages,
                force_non_stream=False,
            )
            model_result = MainBrainTurnResult.normalize(response)
            text = ""
            thinking = ""
            if hasattr(response, "__aiter__"):
                accumulated_text = ""
                accumulated_thinking = ""
                pending_text: str | None = None
                pending_thinking: str | None = None
                pending_usage: object | None = None
                async for chunk in response:  # type: ignore[misc]
                    chunk_text, chunk_thinking = _response_to_text_and_thinking(chunk)
                    merged_text = _merge_stream_text(accumulated_text, chunk_text)
                    merged_thinking = _merge_stream_text(
                        accumulated_thinking,
                        chunk_thinking,
                    )
                    chunk_usage = getattr(chunk, "usage", None)
                    if (
                        (pending_text is not None or pending_thinking is not None)
                        and (
                            merged_text != accumulated_text
                            or merged_thinking != accumulated_thinking
                        )
                    ):
                        yield (
                            _build_assistant_message(
                                text=pending_text,
                                thinking=pending_thinking,
                                message_id=assistant_message_id,
                                usage=pending_usage,
                            ),
                            False,
                        )
                    if merged_text != accumulated_text or merged_thinking != accumulated_thinking:
                        accumulated_text = merged_text
                        accumulated_thinking = merged_thinking
                        pending_text = accumulated_text
                        pending_thinking = accumulated_thinking
                    if chunk_usage is not None:
                        pending_usage = chunk_usage
                if pending_text is not None or pending_thinking is not None:
                    text = pending_text
                    thinking = pending_thinking or ""
                    assistant_usage = pending_usage
                    assistant_message = _build_assistant_message(
                        text=text,
                        thinking=thinking,
                        message_id=assistant_message_id,
                        usage=assistant_usage,
                    )
                    yield assistant_message, True
                    reply_already_streamed = True
            else:
                text, thinking = _response_to_text_and_thinking(response)
                assistant_usage = getattr(response, "usage", None)
                if not text and model_result.reply_text:
                    text = model_result.reply_text
            if not text and not thinking:
                response = await self._call_model_response(
                    model=model,
                    prompt_messages=prompt_messages,
                    force_non_stream=True,
                )
                model_result = MainBrainTurnResult.normalize(response)
                text, thinking = _response_to_text_and_thinking(response)
                assistant_usage = getattr(response, "usage", None)
                if not text and model_result.reply_text:
                    text = model_result.reply_text
        except asyncio.CancelledError:
            self._persist_interrupted_snapshot(
                session_id=session_id,
                user_id=user_id,
                cache_entry=cache_entry,
                snapshot=snapshot,
                now=time.time(),
            )
            raise
        except Exception as exc:
            self._persist_interrupted_snapshot(
                session_id=session_id,
                user_id=user_id,
                cache_entry=cache_entry,
                snapshot=snapshot,
                now=time.time(),
            )
            detail = str(exc).strip()
            message = "主脑纯聊天调用失败，请检查当前激活模型或稍后重试。"
            if detail:
                message = f"{message}（{detail}）"
            raise RuntimeError(message) from exc
        if not text and not thinking:
            logger.warning(
                "Main-brain pure chat returned an empty response; using fallback text",
            )
            text = _PURE_CHAT_EMPTY_REPLY_FALLBACK
        model_result = MainBrainTurnResult.normalize(
            model_result,
            fallback_reply_text=text,
        )
        assistant_message = _build_assistant_message(
            text=text,
            thinking=thinking,
            message_id=assistant_message_id,
            usage=assistant_usage,
        )
        try:
            await memory.add(assistant_message, allow_duplicates=False)
            updated_snapshot = self._snapshot_with_memory(
                snapshot=snapshot,
                memory=memory,
            )

            if cache_entry is not None:
                cache_entry.snapshot = updated_snapshot
                cache_entry.memory = memory
                cache_entry.last_used_at = now
                cache_entry.dirty = True
            self._persist_cache_entry_if_needed(
                session_id=session_id,
                user_id=user_id,
                cache_entry=cache_entry,
                force=cache_entry is None,
                now=now,
            )
        except Exception:
            logger.exception("Failed to persist main-brain chat snapshot")
        commit_state = await self._commit_service.commit_turn_result_async(
            turn_result=model_result,
            request=request,
        )
        if cache_entry is not None and not (
            commit_state.status == "commit_deferred"
            and commit_state.reason == "no_commit_action"
        ):
            main_brain_payload = _safe_mapping(cache_entry.snapshot.get("main_brain"))
            main_brain_payload["phase2_commit"] = commit_state.model_dump(mode="json")
            cache_entry.snapshot["main_brain"] = main_brain_payload
            cache_entry.dirty = True
        self._set_request_runtime_value(
            request,
            "_copaw_main_brain_turn_result",
            model_result,
        )
        self._set_request_runtime_value(
            request,
            "_copaw_main_brain_commit_state",
            commit_state,
        )
        if not reply_already_streamed:
            yield assistant_message, True

    def _resolve_model(self) -> object:
        try:
            return self._model_factory()
        except Exception as exc:
            detail = str(exc).strip()
            message = "主脑纯聊天需要可用的激活聊天模型。请先在模型设置中确认配置。"
            if detail:
                message = f"{message}（{detail}）"
            raise RuntimeError(message) from exc

    def _load_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        if not session_id or not user_id:
            return {}
        loader = getattr(self._session_backend, "load_session_snapshot", None)
        if not callable(loader):
            return {}
        payload = loader(
            session_id=session_id,
            user_id=user_id,
            allow_not_exist=True,
        )
        return dict(payload) if isinstance(payload, dict) else {}

    def _save_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        snapshot: dict[str, Any],
    ) -> None:
        if not session_id or not user_id:
            return
        saver = getattr(self._session_backend, "save_session_snapshot", None)
        if not callable(saver):
            return
        saver(
            session_id=session_id,
            user_id=user_id,
            payload=dict(snapshot),
            source_ref="state:/main-brain-chat-session",
        )

    def _set_request_runtime_value(self, request: Any, name: str, value: Any) -> None:
        try:
            object.__setattr__(request, name, value)
            return
        except Exception:
            pass
        try:
            setattr(request, name, value)
        except Exception:
            logger.debug("Failed to set runtime request attribute '%s'", name)

    def _persist_cache_entry_if_needed(
        self,
        *,
        session_id: str,
        user_id: str,
        cache_entry: _PureChatSessionCacheEntry | None,
        force: bool,
        now: float,
    ) -> None:
        if cache_entry is None:
            return
        if not cache_entry.dirty:
            return
        if not force:
            cache_entry.turns_since_persist += 1
        due_to_turns = cache_entry.turns_since_persist >= _PURE_CHAT_PERSIST_TURNS
        due_to_interval = (
            cache_entry.last_persisted_at <= 0
            or now - cache_entry.last_persisted_at >= _PURE_CHAT_PERSIST_INTERVAL_SECONDS
        )
        if not force and not due_to_turns and not due_to_interval:
            return
        self._save_session_snapshot(
            session_id=session_id,
            user_id=user_id,
            snapshot=cache_entry.snapshot,
        )
        cache_entry.last_persisted_at = now
        cache_entry.turns_since_persist = 0
        cache_entry.dirty = False

    async def _invoke_model_response(
        self,
        *,
        model: object,
        prompt_messages: list[dict[str, str]],
        force_non_stream: bool,
    ) -> object:
        original_stream = getattr(model, "stream", None)
        stream_overridden = isinstance(original_stream, bool)
        if force_non_stream and stream_overridden:
            try:
                setattr(model, "stream", False)
            except Exception:
                stream_overridden = False
        try:
            try:
                response = await model(messages=prompt_messages, **_PURE_CHAT_MODEL_KWARGS)
            except TypeError:
                response = await model(messages=prompt_messages)
            return response
        finally:
            if force_non_stream and stream_overridden:
                try:
                    setattr(model, "stream", original_stream)
                except Exception:
                    logger.debug("Failed to restore pure-chat model stream flag")

    async def _call_model_response(
        self,
        *,
        model: object,
        prompt_messages: list[dict[str, str]],
        force_non_stream: bool,
    ) -> object:
        response = await self._invoke_model_response(
            model=model,
            prompt_messages=prompt_messages,
            force_non_stream=force_non_stream,
        )
        return await _materialize_model_response(response)

    def _snapshot_with_memory(
        self,
        *,
        snapshot: dict[str, Any],
        memory: ReMeInMemoryMemory,
    ) -> dict[str, Any]:
        compacted_state = _compact_memory_state(memory.state_dict())
        updated_snapshot = dict(snapshot)
        agent_payload = _safe_mapping(updated_snapshot.get("agent"))
        agent_payload["memory"] = compacted_state
        updated_snapshot["agent"] = agent_payload
        return updated_snapshot

    def _load_memory(self, snapshot: dict[str, Any]) -> ReMeInMemoryMemory:
        agent_payload = _safe_mapping(snapshot.get("agent"))
        memory_state = agent_payload.get("memory")
        if isinstance(memory_state, list):
            memory_state = {"content": memory_state}
        return self._memory_from_state(memory_state if isinstance(memory_state, dict) else None)

    def _memory_from_state(self, state: dict[str, Any] | None) -> ReMeInMemoryMemory:
        memory = ReMeInMemoryMemory(token_counter=_get_pure_chat_token_counter())
        if isinstance(state, dict) and state:
            try:
                memory.load_state_dict(state, strict=False)
            except Exception:
                logger.exception("Failed to load existing main-brain chat memory")
        return memory

    def _build_prompt_messages(
        self,
        *,
        request: Any,
        query: str | None,
        prior_messages: list[Any],
        current_messages: list[Any],
        cache_entry: _PureChatSessionCacheEntry | None = None,
    ) -> list[dict[str, str]]:
        _ = cache_entry
        detail = self._load_industry_detail(request)
        owner_agent_id = self._resolve_owner_agent_id(request, detail=detail)
        prompt_context = self._scope_snapshot_service.resolve_prompt_context(
            request=request,
            detail=detail,
            owner_agent_id=owner_agent_id,
        )
        lexical_recall = self._build_lexical_recall_context(
            request=request,
            query=query,
        )
        context_body = "\n\n".join(
            part
            for part in (
                prompt_context.stable_prefix,
                prompt_context.scope_snapshot,
                lexical_recall,
            )
            if part
        )
        history_messages = self._build_history_messages(
            prior_messages=prior_messages,
            current_messages=current_messages,
        )
        return [
            {"role": "system", "content": _PURE_CHAT_SYSTEM_PROMPT},
            {"role": "system", "content": context_body},
            *history_messages,
        ]

    def _build_stable_prompt_prefix(
        self,
        *,
        request: Any,
        detail: object | None,
        owner_agent_id: str | None,
    ) -> str:
        roster_lines = _format_team_roster(
            detail=detail,
            agent_profile_service=self._agent_profile_service,
            industry_instance_id=str(getattr(request, "industry_instance_id", "") or "").strip() or None,
            owner_agent_id=owner_agent_id,
        )
        context_sections = [
            f"## 主脑身份\n- 当前身份：Spider Mesh 主脑\n- 当前会话：{_clip_text(getattr(request, 'session_id', ''), limit=80) or '未命名会话'}",
            f"## 当前运行摘要\n{_format_runtime_snapshot(detail)}",
            f"## 主脑 cognitive closure\n{_format_cognitive_closure(detail=detail, request=request)}",
            f"## 正式战略摘要\n{_format_strategy_summary(detail)}",
            "## 团队职业成员 roster\n"
            + ("\n".join(roster_lines) if roster_lines else "- 当前没有可用 roster，请基于已知上下文谨慎回答"),
        ]
        context_sections.insert(3, f"## Staffing\n{_format_staffing_summary(detail)}")
        context_body = "\n\n".join(context_sections)
        return re.sub(
            r"## [^\n]*cognitive closure",
            "## 主脑 cognitive closure",
            context_body,
            count=1,
        )

    def _build_scope_snapshot_body(
        self,
        *,
        request: Any,
        detail: object | None,
        owner_agent_id: str | None,
    ) -> str:
        service = self._memory_recall_service
        if service is None:
            return "## Truth-First Memory Profile\n- No truth-first memory service available."
        scope_type, scope_id = self._resolve_truth_first_scope(request)
        derived_service = getattr(service, "_derived_index_service", None)
        if derived_service is not None and callable(getattr(derived_service, "list_fact_entries", None)):
            entries = _sort_truth_first_entries(
                list(
                    derived_service.list_fact_entries(
                        scope_type=scope_type,
                        scope_id=scope_id,
                        owner_agent_id=owner_agent_id,
                        industry_instance_id=str(
                            getattr(request, "industry_instance_id", "") or "",
                        ).strip()
                        or None,
                        limit=8,
                    )
                    or []
                ),
            )
        else:
            entries = []
        latest_entries = entries[:2]
        history_entries = entries[2:4]
        return "\n".join(
            [
                f"## Truth-First Memory Profile\n{_format_truth_first_profile(scope_type=scope_type, scope_id=scope_id, entries=entries)}",
                f"## Truth-First Memory Latest Facts\n{_format_truth_first_entry_lines(latest_entries, limit=2)}",
                f"## Truth-First Memory History\n{_format_truth_first_entry_lines(history_entries, limit=2)}",
            ],
        )

    def _build_scope_snapshot_signature(
        self,
        *,
        request: Any,
        detail: object | None,
        owner_agent_id: str | None,
    ) -> str:
        return self._build_prompt_context_signature(
            request=request,
            detail=detail,
            owner_agent_id=owner_agent_id,
        )

    def _resolve_scope_snapshot_key(
        self,
        *,
        request: Any,
        detail: object | None = None,
        owner_agent_id: str | None = None,
    ) -> str:
        _ = (detail, owner_agent_id)
        work_context_id = str(getattr(request, "work_context_id", "") or "").strip()
        if work_context_id:
            return work_context_id
        industry_instance_id = str(getattr(request, "industry_instance_id", "") or "").strip()
        if industry_instance_id:
            return f"industry:{industry_instance_id}"
        agent_id = str(getattr(request, "agent_id", "") or "").strip()
        if agent_id:
            return f"agent:{agent_id}"
        return "global:runtime"

    def _resolve_truth_first_scope(self, request: Any) -> tuple[str, str]:
        work_context_id = str(getattr(request, "work_context_id", "") or "").strip()
        industry_instance_id = str(getattr(request, "industry_instance_id", "") or "").strip()
        agent_id = str(getattr(request, "agent_id", "") or "").strip()
        if work_context_id:
            return ("work_context", work_context_id)
        if industry_instance_id:
            return ("industry", industry_instance_id)
        if agent_id:
            return ("agent", agent_id)
        return ("global", "runtime")

    def _build_prompt_context_signature(
        self,
        *,
        request: Any,
        detail: object | None,
        owner_agent_id: str | None,
    ) -> str:
        payload = _safe_mapping(detail)
        team_payload = _safe_mapping(payload.get("team"))
        signature_payload: dict[str, Any] = {
            "industry_instance_id": str(getattr(request, "industry_instance_id", "") or "").strip() or None,
            "work_context_id": str(getattr(request, "work_context_id", "") or "").strip() or None,
            "agent_id": str(getattr(request, "agent_id", "") or "").strip() or None,
            "owner_agent_id": owner_agent_id,
            "execution_core_identity": _safe_mapping(payload.get("execution_core_identity")),
            "execution": _safe_mapping(payload.get("execution")),
            "current_cycle": _safe_mapping(payload.get("current_cycle")),
            "strategy_memory": _safe_mapping(payload.get("strategy_memory")),
            "staffing": _safe_mapping(payload.get("staffing")),
            "team_agents": list(team_payload.get("agents") or [])[:12],
            "assignments": list(payload.get("assignments") or [])[:12],
            "backlog": list(payload.get("backlog") or [])[:8],
            "lanes": list(payload.get("lanes") or [])[:6],
            "agent_reports": list(payload.get("agent_reports") or [])[:6],
        }
        try:
            return json.dumps(
                signature_payload,
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
        except Exception:
            return repr(signature_payload)

    def _load_industry_detail(self, request: Any) -> object | None:
        service = self._industry_service
        if service is None:
            return None
        instance_id = str(getattr(request, "industry_instance_id", "") or "").strip()
        if not instance_id:
            return None
        getter = getattr(service, "get_instance_detail", None)
        if not callable(getter):
            return None
        try:
            return getter(instance_id)
        except Exception:
            logger.exception("Failed to load industry detail for pure chat")
            return None

    def _resolve_owner_agent_id(self, request: Any, *, detail: object | None) -> str | None:
        explicit = str(getattr(request, "agent_id", "") or "").strip()
        if explicit:
            return explicit
        identity = getattr(detail, "execution_core_identity", None) if detail is not None else None
        identity_payload = _safe_mapping(identity)
        resolved = str(identity_payload.get("agent_id") or "").strip()
        if resolved:
            return resolved
        return None

    def _recall_memory(self, *, request: Any, query: str | None) -> list[object]:
        service = self._memory_recall_service
        if service is None or not query:
            return []
        industry_instance_id = str(getattr(request, "industry_instance_id", "") or "").strip() or None
        work_context_id = str(getattr(request, "work_context_id", "") or "").strip() or None
        agent_id = str(getattr(request, "agent_id", "") or "").strip() or None
        scope_type: str | None = None
        scope_id: str | None = None
        if work_context_id:
            scope_type = "work_context"
            scope_id = work_context_id
        elif industry_instance_id:
            scope_type = "industry"
            scope_id = industry_instance_id
        elif agent_id:
            scope_type = "agent"
            scope_id = agent_id
        try:
            result = service.recall(
                query=query,
                scope_type=scope_type,
                scope_id=scope_id,
                work_context_id=work_context_id,
                agent_id=agent_id,
                industry_instance_id=industry_instance_id,
                include_related_scopes=True,
                limit=4,
            )
        except Exception:
            logger.exception("Failed to inject controlled recall into pure chat")
            return []
        hits = getattr(result, "hits", None)
        return list(hits or [])

    def _build_lexical_recall_context(
        self,
        *,
        request: Any,
        query: str | None,
    ) -> str:
        lexical_hits = self._recall_memory(request=request, query=query)
        return f"## Truth-First Lexical Recall\n{_format_memory_hits(lexical_hits)}"

    def _build_history_messages(
        self,
        *,
        prior_messages: list[Any],
        current_messages: list[Any],
    ) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for message in [*prior_messages, *current_messages]:
            role = _message_role(message)
            if role not in {"user", "assistant"}:
                continue
            text = _message_text(message)
            if not text:
                continue
            normalized.append(
                {
                    "role": role,
                    "content": _clip_text(
                        text,
                        limit=_PURE_CHAT_HISTORY_MESSAGE_CHAR_LIMIT,
                    ),
                },
            )
        if not normalized:
            return [{"role": "user", "content": "请先根据上面的上下文回答当前问题。"}]
        bounded_reversed: list[dict[str, str]] = []
        total_chars = 0
        for message in reversed(normalized):
            if len(bounded_reversed) >= _PURE_CHAT_HISTORY_MAX_MESSAGES:
                break
            content = str(message.get("content") or "")
            if not content:
                continue
            remaining = _PURE_CHAT_HISTORY_MAX_CHARS - total_chars
            if remaining <= 0:
                break
            if len(content) > remaining:
                if bounded_reversed:
                    break
                content = _clip_text(content, limit=max(80, remaining))
            bounded_reversed.append(
                {
                    "role": str(message.get("role") or "user"),
                    "content": content,
                },
            )
            total_chars += len(content)
        if not bounded_reversed:
            return [{"role": "user", "content": normalized[-1]["content"]}]
        return list(reversed(bounded_reversed))


__all__ = ["MainBrainChatService"]
