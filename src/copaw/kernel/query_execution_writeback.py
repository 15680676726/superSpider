# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any, Literal

from agentscope.message import Msg, TextBlock
from pydantic import BaseModel, Field

from ..industry.chat_writeback import ChatWritebackPlan, build_chat_writeback_plan_from_payload
from ..utils.cache import BoundedLRUCache
from .query_execution_intent_policy import (
    is_hypothetical_control_text as _is_hypothetical_control_text,
    looks_like_goal_setting_text as _looks_like_goal_setting_text,
)

logger = logging.getLogger(__name__)
_CHAT_WRITEBACK_MODEL_TARGETS = frozenset({"strategy", "backlog", "schedule"})
_CHAT_WRITEBACK_MODEL_INTENT_KINDS = frozenset(
    {"chat", "discussion", "status-query", "execute-task"},
)
_CHAT_WRITEBACK_MODEL_SURFACES = frozenset({"browser", "desktop", "auto"})
_CHAT_WRITEBACK_TEAM_ROLE_GAP_ACTIONS = frozenset({"approve", "reject"})
_CHAT_WRITEBACK_MODEL_CACHE_MAX = 128
_CHAT_WRITEBACK_MODEL_CACHE_LOCK = threading.Lock()
_CHAT_WRITEBACK_MODEL_CACHE = BoundedLRUCache[str, "_ChatWritebackModelDecision"](
    max_entries=_CHAT_WRITEBACK_MODEL_CACHE_MAX,
)
_CHAT_WRITEBACK_DECISION_MODEL_FACTORY = None
_CHAT_WRITEBACK_MODEL_TIMEOUT_SECONDS = 80.0
_CHAT_WRITEBACK_MODEL_PLANNER_PROMPT = """
You are the governed execution-core chat frontdoor for CoPaw.

For the latest operator message, return a structured decision with:
- intent_kind: chat | discussion | status-query | execute-task
- intent_confidence: 0..1
- intent_signals: short stable cues
- host_observation_requested: whether the operator is explicitly asking to inspect
  the current host/app/window/screen state now
- risky_actuation_requested: whether the operator is asking to perform a risky
  real-world browser/desktop actuation now
- risky_actuation_surface: browser | desktop | auto when risky_actuation_requested is true
- should_writeback: whether this turn should become durable operating truth
- approved_targets: strategy | backlog | schedule
- kickoff_allowed: whether execution should start or continue now
- explicit_execution_confirmation: whether the operator is explicitly approving
  the current risky workflow now
- team_role_gap_action: approve | reject only when the operator is explicitly
  deciding the current staffing-gap recommendation
- team_role_gap_notice: true when the operator is asking what to do next about
  a staffing gap or wants that gap surfaced in chat
""".strip()


class ChatWritebackDecisionModelUnavailableError(RuntimeError):
    """Raised when the writeback decision model cannot be used."""


class ChatWritebackDecisionModelTimeoutError(TimeoutError):
    """Raised when the writeback decision model times out."""


class _ChatWritebackStrategyPayload(BaseModel):
    operator_requirements: list[str] = Field(default_factory=list)
    priority_order: list[str] = Field(default_factory=list)
    execution_constraints: list[str] = Field(default_factory=list)
    switch_to_operator_guided: bool = False


class _ChatWritebackGoalPayload(BaseModel):
    title: str | None = None
    summary: str | None = None
    plan_steps: list[str] = Field(default_factory=list)


class _ChatWritebackSchedulePayload(BaseModel):
    title: str | None = None
    summary: str | None = None
    cron: str | None = None
    prompt: str | None = None


class _ChatWritebackModelDecision(BaseModel):
    intent_kind: Literal["chat", "discussion", "status-query", "execute-task"] = "chat"
    intent_confidence: float = 0.0
    intent_signals: list[str] = Field(default_factory=list)
    host_observation_requested: bool = False
    risky_actuation_requested: bool = False
    risky_actuation_surface: Literal["browser", "desktop", "auto"] | None = None
    should_writeback: bool = False
    approved_targets: list[Literal["strategy", "backlog", "schedule"]] = Field(
        default_factory=list,
    )
    kickoff_allowed: bool = False
    explicit_execution_confirmation: bool = False
    team_role_gap_action: Literal["approve", "reject"] | None = None
    team_role_gap_notice: bool = False
    confidence: float = 0.0
    blockers: list[str] = Field(default_factory=list)
    rationale: str | None = None
    strategy: _ChatWritebackStrategyPayload | None = None
    goal: _ChatWritebackGoalPayload | None = None
    schedule: _ChatWritebackSchedulePayload | None = None


class _RawChatWritebackModelDecision(BaseModel):
    intent_kind: str | None = None
    intent_confidence: float = 0.0
    intent_signals: list[str] = Field(default_factory=list)
    host_observation_requested: bool = False
    risky_actuation_requested: bool = False
    risky_actuation_surface: str | None = None
    should_writeback: bool = False
    approved_targets: list[str] = Field(default_factory=list)
    kickoff_allowed: bool = False
    explicit_execution_confirmation: bool = False
    team_role_gap_action: str | None = None
    team_role_gap_notice: bool = False
    confidence: float = 0.0
    blockers: list[str] = Field(default_factory=list)
    rationale: str | None = None
    strategy: _ChatWritebackStrategyPayload | None = None
    goal: _ChatWritebackGoalPayload | None = None
    schedule: _ChatWritebackSchedulePayload | None = None


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
            continue
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return None


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _normalize_chat_writeback_literal(
    value: Any,
    *,
    allowed: frozenset[str],
) -> str | None:
    normalized = _first_non_empty(value)
    if normalized is None:
        return None
    lowered = normalized.strip().lower()
    return lowered if lowered in allowed else None


def _sanitize_chat_writeback_model_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    sanitized = dict(payload)
    intent_kind = _normalize_chat_writeback_literal(
        payload.get("intent_kind"),
        allowed=_CHAT_WRITEBACK_MODEL_INTENT_KINDS,
    )
    if intent_kind is not None:
        sanitized["intent_kind"] = intent_kind
    else:
        sanitized.pop("intent_kind", None)

    risky_surface = _normalize_chat_writeback_literal(
        payload.get("risky_actuation_surface"),
        allowed=_CHAT_WRITEBACK_MODEL_SURFACES,
    )
    sanitized["risky_actuation_surface"] = risky_surface

    team_role_gap_action = _normalize_chat_writeback_literal(
        payload.get("team_role_gap_action"),
        allowed=_CHAT_WRITEBACK_TEAM_ROLE_GAP_ACTIONS,
    )
    sanitized["team_role_gap_action"] = team_role_gap_action

    approved_targets: list[str] = []
    for item in _string_list(payload.get("approved_targets")):
        if item in _CHAT_WRITEBACK_MODEL_TARGETS and item not in approved_targets:
            approved_targets.append(item)
    sanitized["approved_targets"] = approved_targets

    sanitized["intent_signals"] = _string_list(payload.get("intent_signals"))
    sanitized["blockers"] = _string_list(payload.get("blockers"))
    return sanitized


def _request_requested_actions(request: Any) -> set[str]:
    values = getattr(request, "requested_actions", None)
    return {item for item in _string_list(values)}


def _request_has_requested_action(request: Any, *actions: str) -> bool:
    requested = _request_requested_actions(request)
    return any(action in requested for action in actions)


def _is_explicit_risky_execution_confirmation(
    *,
    text: str | None = None,
    request: Any | None = None,
) -> bool:
    if request is not None and _request_has_requested_action(
        request,
        "confirm_risky_actuation",
    ):
        return True
    normalized = _first_non_empty(text)
    if normalized is None:
        return False
    lowered = normalized.strip().lower()
    return any(
        phrase in lowered
        for phrase in (
            "confirm and continue",
            "confirm continue",
            "confirm execution",
            "go ahead and execute",
            "同意执行",
            "确认执行",
            "确认继续",
            "继续执行",
        )
    )


def _is_trading_goal_text(text: str) -> bool:
    lowered = text.casefold()
    return any(
        hint in lowered
        for hint in (
            "股票",
            "炒股",
            "a股",
            "港股",
            "美股",
            "基金",
            "期货",
            "btc",
            "比特币",
            "加密",
            "币圈",
            "回撤",
            "止损",
            "仓位",
            "零亏损",
            "零回撤",
            "月入",
            "收益",
        )
    )


def _structured_goal_title(text: str) -> str:
    if _is_trading_goal_text(text):
        return "月度收益目标校准"
    return "阶段目标校准"


def _structured_goal_gaps(text: str) -> list[str]:
    if _is_trading_goal_text(text):
        return [
            "可用本金/账户规模",
            "市场范围",
            "交易周期",
            "允许回撤",
            "仓位上限",
        ]
    return [
        "目标周期",
        "资源投入",
        "渠道边界",
        "验收指标",
        "风险边界",
    ]


def _structured_goal_summary(text: str) -> str:
    gaps = "、".join(_structured_goal_gaps(text))
    return f"目标结果：{text}\n关键待校准参数：{gaps}"


def _structured_goal_plan_steps(text: str) -> list[str]:
    if _is_trading_goal_text(text):
        return [
            "校准本金、市场范围、交易周期与风险边界。",
            "把结果口号改写成可执行目标：收益目标、允许回撤、仓位规则、停手条件。",
            "按校准后的目标拆分研究与执行动作，先跑小规模验证并回写证据。",
        ]
    return [
        "补齐目标的周期、资源、渠道与关键约束。",
        "把结果目标改写成阶段目标、验收指标与风险边界。",
        "启动首轮验证任务，并按证据决定是否继续放大执行。",
    ]
def _structure_chat_writeback_goal_if_needed(
    *,
    text: str,
    plan: ChatWritebackPlan | None,
) -> ChatWritebackPlan | None:
    if plan is None or plan.goal is None or not _looks_like_goal_setting_text(text):
        return plan
    goal = plan.goal
    if _first_non_empty(goal.summary) not in (None, text):
        return plan
    goal.title = _structured_goal_title(text)
    goal.summary = _structured_goal_summary(text)
    goal.plan_steps = _structured_goal_plan_steps(text)
    return plan


def normalize_chat_writeback_targets(targets: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for item in _string_list(targets):
        target = item.strip().lower()
        if target in _CHAT_WRITEBACK_MODEL_TARGETS and target not in normalized:
            normalized.append(target)
    if normalized and "strategy" not in normalized:
        normalized.insert(0, "strategy")
    return normalized


def build_chat_writeback_plan_from_model_decision(
    *,
    text: str,
    decision: Any,
) -> ChatWritebackPlan | None:
    strategy = getattr(decision, "strategy", None)
    goal = getattr(decision, "goal", None)
    schedule = getattr(decision, "schedule", None)
    plan = build_chat_writeback_plan_from_payload(
        text,
        approved_classifications=list(getattr(decision, "approved_targets", []) or []),
        operator_requirements=(
            list(getattr(strategy, "operator_requirements", []) or [])
            if strategy is not None
            else None
        ),
        priority_order=(
            list(getattr(strategy, "priority_order", []) or [])
            if strategy is not None
            else None
        ),
        execution_constraints=(
            list(getattr(strategy, "execution_constraints", []) or [])
            if strategy is not None
            else None
        ),
        switch_to_operator_guided=(
            bool(getattr(strategy, "switch_to_operator_guided", False))
            if strategy is not None
            else None
        ),
        goal_title=_first_non_empty(getattr(goal, "title", None)) if goal is not None else None,
        goal_summary=_first_non_empty(getattr(goal, "summary", None)) if goal is not None else None,
        goal_plan_steps=list(getattr(goal, "plan_steps", []) or []) if goal is not None else None,
        schedule_title=_first_non_empty(getattr(schedule, "title", None)) if schedule is not None else None,
        schedule_summary=_first_non_empty(getattr(schedule, "summary", None)) if schedule is not None else None,
        schedule_cron=_first_non_empty(getattr(schedule, "cron", None)) if schedule is not None else None,
        schedule_prompt=_first_non_empty(getattr(schedule, "prompt", None)) if schedule is not None else None,
    )
    return _structure_chat_writeback_goal_if_needed(text=text, plan=plan)


def resolve_team_role_gap_action_request(
    *,
    text: str | None = None,
    request: Any | None = None,
) -> str | None:
    if request is not None:
        if _request_has_requested_action(request, "approve_team_role_gap"):
            return "approve"
        if _request_has_requested_action(request, "reject_team_role_gap"):
            return "reject"
    normalized = _first_non_empty(text)
    if normalized is None:
        return None
    lowered = normalized.strip().lower()
    if (
        _is_hypothetical_control_text(normalized)
        or "?" in normalized
        or "？" in normalized
        or lowered.startswith("if ")
        or lowered.startswith("如果")
        or lowered.startswith("假如")
        or lowered.startswith("假设")
    ):
        return None
    if any(phrase in lowered for phrase in ("approve the gap", "批准补位", "同意补位", "确认补位")):
        return "approve"
    if any(phrase in lowered for phrase in ("reject the gap", "拒绝补位", "不要补位")):
        return "reject"
    return None
def should_surface_team_role_gap_notice(
    *,
    text: str | None = None,
    request: Any | None = None,
) -> bool:
    if request is not None and _request_has_requested_action(request, "show_team_role_gap"):
        return True
    normalized = _first_non_empty(text)
    if normalized is None:
        return False
    lowered = normalized.strip().lower()
    return any(
        phrase in lowered
        for phrase in ("what should we do next", "what next", "下一步怎么做", "接下来怎么做")
    )


def should_trigger_industry_kickoff(
    *,
    text: str | None = None,
    request: Any | None = None,
) -> bool:
    _ = text
    return bool(request is not None and _request_has_requested_action(request, "kickoff_execution"))


def should_attempt_formal_chat_writeback(
    *,
    text: str | None = None,
    request: Any | None = None,
) -> bool:
    _ = text
    return bool(
        request is not None
        and _request_has_requested_action(
            request,
            "writeback_strategy",
            "writeback_backlog",
            "writeback_schedule",
        )
    )


def team_role_gap_notice_message(*, recommendation: dict[str, Any]) -> Msg:
    role_name = _first_non_empty(recommendation.get("suggested_role_name"), "该岗位")
    summary = _first_non_empty(recommendation.get("summary"), "当前团队存在可正式补位的岗位空缺。")
    decision_request_id = _first_non_empty(recommendation.get("decision_request_id"))
    status = _first_non_empty(recommendation.get("status"), "proposed")
    workflow_title = _first_non_empty(recommendation.get("workflow_title"))
    lines = [
        "**发现岗位空缺**",
        "",
        f"- 建议补位：{role_name}",
        f"- 原因：{summary}",
        f"- 当前状态：{status}",
    ]
    if workflow_title is not None:
        lines.append(f"- 来源工作流：{workflow_title}")
    if decision_request_id is not None:
        lines.append(f"- 当前决策单：`{decision_request_id}`")
    lines.append("- 直接在聊天里回复“批准补位”或“拒绝补位”。")
    return Msg(
        name="Spider Mesh",
        role="assistant",
        content=[TextBlock(type="text", text="\n".join(lines))],
    )


def team_role_gap_resolution_message(
    *,
    action: str,
    role_name: str | None,
    outcome_summary: str,
    decision_request_id: str | None,
    task_id: str | None = None,
) -> Msg:
    verb = "已批准" if action == "approve" else "已拒绝"
    label = role_name or "该岗位"
    lines = [
        f"**{verb}补位**",
        "",
        f"- 目标岗位：{label}",
        f"- 结果：{outcome_summary}",
    ]
    if decision_request_id is not None:
        lines.append(f"- 决策单：`{decision_request_id}`")
    if task_id is not None:
        lines.append(f"- 任务：`{task_id}`")
    return Msg(
        name="Spider Mesh",
        role="assistant",
        content=[TextBlock(type="text", text="\n".join(lines))],
    )


def _response_to_text(response: object) -> str:
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


def _response_to_payload(response: object) -> dict[str, Any]:
    metadata = getattr(response, "metadata", None)
    if isinstance(metadata, BaseModel):
        return metadata.model_dump(mode="json")
    if isinstance(metadata, dict):
        return metadata
    text = _response_to_text(response)
    if not text:
        raise ValueError("Chat writeback decision model returned an empty response.")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Chat writeback decision model returned a non-object payload.")
    return payload


async def _materialize_response(response: object) -> object:
    if not hasattr(response, "__aiter__"):
        return response
    last_item: object | None = None
    async for item in response:  # type: ignore[misc]
        last_item = item
    return last_item if last_item is not None else response


def _cache_chat_writeback_decision(
    text: str,
    decision: _ChatWritebackModelDecision,
) -> _ChatWritebackModelDecision:
    key = text.strip()
    with _CHAT_WRITEBACK_MODEL_CACHE_LOCK:
        if _CHAT_WRITEBACK_MODEL_CACHE._max_entries != _CHAT_WRITEBACK_MODEL_CACHE_MAX:
            _CHAT_WRITEBACK_MODEL_CACHE._max_entries = _CHAT_WRITEBACK_MODEL_CACHE_MAX
        _CHAT_WRITEBACK_MODEL_CACHE.set(key, decision)
    return decision


def _get_cached_chat_writeback_decision(
    text: str | None,
) -> _ChatWritebackModelDecision | None:
    normalized = _first_non_empty(text)
    if normalized is None:
        return None
    with _CHAT_WRITEBACK_MODEL_CACHE_LOCK:
        return _CHAT_WRITEBACK_MODEL_CACHE.get(normalized)


def clear_chat_writeback_decision_cache() -> None:
    with _CHAT_WRITEBACK_MODEL_CACHE_LOCK:
        _CHAT_WRITEBACK_MODEL_CACHE.clear()


def _resolve_chat_writeback_decision_model() -> object | None:
    factory = _CHAT_WRITEBACK_DECISION_MODEL_FACTORY
    if callable(factory):
        try:
            return factory()
        except Exception:
            logger.debug("Chat writeback decision model factory failed.", exc_info=True)
            return None
    try:
        from ..providers.runtime_provider_facade import build_compat_runtime_provider_facade

        runtime = build_compat_runtime_provider_facade()
        return runtime.get_active_chat_model()
    except Exception:
        logger.debug("Chat writeback decision model is unavailable.", exc_info=True)
        return None


async def _resolve_model_chat_writeback_decision(
    text: str,
) -> _ChatWritebackModelDecision | None:
    model = _resolve_chat_writeback_decision_model()
    if model is None:
        raise ChatWritebackDecisionModelUnavailableError(
            "Chat writeback decision model is unavailable.",
        )
    try:
        response = await asyncio.wait_for(
            model(
                messages=_decision_messages(text),
                structured_model=_RawChatWritebackModelDecision,
            ),
            timeout=_CHAT_WRITEBACK_MODEL_TIMEOUT_SECONDS,
        )
        response = await asyncio.wait_for(
            _materialize_response(response),
            timeout=_CHAT_WRITEBACK_MODEL_TIMEOUT_SECONDS,
        )
        payload = _sanitize_chat_writeback_model_payload(
            _response_to_payload(response),
        )
        return _ChatWritebackModelDecision.model_validate(payload)
    except TimeoutError:
        logger.warning("Chat writeback decision model timed out.", exc_info=True)
        raise ChatWritebackDecisionModelTimeoutError(
            "Chat writeback decision model timed out.",
        ) from None
    except Exception as exc:
        logger.debug("Chat writeback decision model failed.", exc_info=True)
        raise ChatWritebackDecisionModelUnavailableError(
            "Chat writeback decision model failed.",
        ) from exc


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _infer_risky_surface(text: str) -> str | None:
    lowered = text.casefold()
    if _contains_any(
        lowered,
        (
            "desktop",
            "desktop app",
            "desktop client",
            "local client",
            "windows app",
            "win32",
            "桌面",
            "本机",
            "客户端",
            "电脑",
            "微信",
            "企业微信",
            "钉钉",
            "飞书",
            "qq",
            "excel",
            "word",
            "powerpoint",
            "erp",
            "crm",
        ),
    ):
        return "desktop"
    if _contains_any(
        lowered,
        (
            "browser",
            "web",
            "site",
            "网页",
            "浏览器",
            "页面",
            "后台",
            "网站",
            "portal",
        ),
    ):
        return "browser"
    return None


def _looks_like_status_query(text: str) -> bool:
    lowered = text.casefold()
    return _contains_any(
        lowered,
        (
            "你在干什么",
            "在吗",
            "现在做到哪了",
            "现在在做什么",
            "进度",
            "状态",
            "status",
            "progress",
            "what are you doing",
            "where are you at",
        ),
    )


def _looks_like_discussion(text: str) -> bool:
    lowered = text.casefold()
    return _contains_any(
        lowered,
        (
            "讨论",
            "分析一下",
            "解释",
            "为什么",
            "怎么理解",
            "brainstorm",
            "discuss",
            "explain",
            "analyze",
        ),
    )


def _looks_like_host_observation_request(text: str) -> bool:
    lowered = text.casefold()
    return _contains_any(
        lowered,
        (
            "看看当前",
            "查看当前",
            "当前页面",
            "当前窗口",
            "当前屏幕",
            "前台窗口",
            "open windows",
            "current page",
            "current screen",
            "current window",
            "foreground window",
        ),
    )


def _looks_like_risky_actuation_request(text: str) -> bool:
    lowered = text.casefold()
    return _contains_any(
        lowered,
        (
            "publish",
            "post it",
            "submit order",
            "security settings",
            "account setting",
            "payment",
            "pay ",
            "transfer",
            "wire",
            "withdraw",
            "delete account",
            "发布",
            "上架",
            "发帖",
            "支付",
            "付款",
            "转账",
            "汇款",
            "提现",
            "提交审核",
            "保存安全设置",
            "删除账号",
        ),
    )


def _looks_like_schedule_change(text: str) -> bool:
    lowered = text.casefold()
    cadence = _contains_any(
        lowered,
        (
            "weekly",
            "daily",
            "every week",
            "every day",
            "每周",
            "每天",
            "每日",
            "定时",
            "周期",
            "cron",
        ),
    )
    return cadence and _contains_any(
        lowered,
        (
            "must include",
            "review",
            "follow up",
            "检查",
            "复盘",
            "跟进",
            "回顾",
            "汇报",
        ),
    )


def _looks_like_policy_writeback(text: str) -> bool:
    lowered = text.casefold()
    return _contains_any(
        lowered,
        (
            "以后",
            "默认",
            "保留",
            "记住",
            "必须",
            "优先",
            "改成",
            "改为",
            "不要再",
            "长期",
            "rule",
            "policy",
            "default",
        ),
    )


def _looks_like_execute_now(text: str) -> bool:
    lowered = text.casefold()
    return _contains_any(
        lowered,
        (
            "开始执行",
            "开始做",
            "继续做",
            "推进",
            "处理",
            "整理",
            "帮我",
            "现在就",
            "马上",
            "run",
            "execute",
            "start",
            "continue",
            "kickoff",
        ),
    )


def _schedule_payload_from_text(text: str) -> _ChatWritebackSchedulePayload:
    lowered = text.casefold()
    daily = _contains_any(lowered, ("daily", "every day", "每天", "每日"))
    return _ChatWritebackSchedulePayload(
        title="operator review cadence",
        summary=text,
        cron="0 9 * * *" if daily else "0 9 * * 1",
        prompt=f"Review and continue this governed instruction: {text}",
    )


def _goal_payload_from_text(text: str) -> _ChatWritebackGoalPayload:
    return _ChatWritebackGoalPayload(
        title=None,
        summary=text,
        plan_steps=[],
    )


def _strategy_payload_from_text(
    text: str,
    *,
    operator_guided: bool,
) -> _ChatWritebackStrategyPayload:
    return _ChatWritebackStrategyPayload(
        operator_requirements=[text],
        priority_order=[],
        execution_constraints=[],
        switch_to_operator_guided=operator_guided,
    )


def _heuristic_chat_writeback_model_decision(
    text: str,
) -> _ChatWritebackModelDecision:
    normalized = text.strip()
    if not normalized:
        return _ChatWritebackModelDecision()

    host_observation_requested = _looks_like_host_observation_request(normalized)
    team_role_gap_action = resolve_team_role_gap_action_request(text=normalized)
    team_role_gap_notice = (
        should_surface_team_role_gap_notice(text=normalized)
        if team_role_gap_action is None
        else False
    )
    explicit_execution_confirmation = _is_explicit_risky_execution_confirmation(text=normalized)
    risky_actuation_requested = explicit_execution_confirmation or _looks_like_risky_actuation_request(
        normalized,
    )
    risky_actuation_surface = _infer_risky_surface(normalized)
    schedule_change = _looks_like_schedule_change(normalized)
    policy_writeback = _looks_like_policy_writeback(normalized)
    goal_writeback = _looks_like_goal_setting_text(normalized)
    execute_now = _looks_like_execute_now(normalized)

    if team_role_gap_action is not None:
        return _ChatWritebackModelDecision(
            intent_kind="chat",
            intent_confidence=0.97,
            intent_signals=["team-gap-action", team_role_gap_action],
            team_role_gap_action=team_role_gap_action,
            confidence=0.97,
            rationale="heuristic-team-gap-action",
        )

    if team_role_gap_notice:
        return _ChatWritebackModelDecision(
            intent_kind="chat",
            intent_confidence=0.88,
            intent_signals=["team-gap-notice"],
            team_role_gap_notice=True,
            blockers=["team-gap-follow-up"],
            confidence=0.88,
            rationale="heuristic-team-gap-notice",
        )

    if _looks_like_status_query(normalized):
        return _ChatWritebackModelDecision(
            intent_kind="status-query",
            intent_confidence=0.98,
            intent_signals=["status-query"],
            blockers=["status-query"],
            confidence=0.98,
            rationale="heuristic-status-query",
        )

    if _looks_like_discussion(normalized) or _is_hypothetical_control_text(normalized):
        return _ChatWritebackModelDecision(
            intent_kind="discussion",
            intent_confidence=0.9,
            intent_signals=["discussion"],
            blockers=["discussion-turn"],
            confidence=0.9,
            rationale="heuristic-discussion",
        )

    should_writeback = schedule_change or policy_writeback or goal_writeback
    approved_targets: list[Literal["strategy", "backlog", "schedule"]] = []
    if schedule_change:
        approved_targets = ["backlog", "schedule"]
    elif policy_writeback:
        approved_targets = ["strategy", "backlog"]
    elif goal_writeback:
        approved_targets = ["backlog"]

    kickoff_allowed = bool(
        explicit_execution_confirmation
        or (
            not _is_hypothetical_control_text(normalized)
            and (execute_now or risky_actuation_requested or goal_writeback)
        ),
    )
    intent_kind: Literal["chat", "discussion", "status-query", "execute-task"] = (
        "execute-task" if kickoff_allowed or risky_actuation_requested else "chat"
    )

    confidence = 0.35
    intent_confidence = 0.35
    intent_signals = ["chat"]
    blockers: list[str] = []
    if risky_actuation_requested:
        confidence = 0.95
        intent_confidence = 0.95
        intent_signals = ["risky-actuation"]
    elif should_writeback:
        confidence = 0.86
        intent_confidence = 0.86
        intent_signals = ["durable-instruction"]
    elif host_observation_requested:
        confidence = 0.82
        intent_confidence = 0.82
        intent_signals = ["host-observation"]
    elif kickoff_allowed:
        confidence = 0.9
        intent_confidence = 0.9
        intent_signals = ["execution-request"]
    else:
        blockers = ["model-deny"]

    return _ChatWritebackModelDecision(
        intent_kind=intent_kind,
        intent_confidence=intent_confidence,
        intent_signals=intent_signals,
        host_observation_requested=host_observation_requested,
        risky_actuation_requested=risky_actuation_requested,
        risky_actuation_surface=(
            risky_actuation_surface
            if risky_actuation_surface is not None
            else ("auto" if risky_actuation_requested else None)
        ),
        should_writeback=should_writeback,
        approved_targets=approved_targets,
        kickoff_allowed=kickoff_allowed,
        explicit_execution_confirmation=explicit_execution_confirmation,
        confidence=confidence,
        blockers=blockers,
        rationale="heuristic-fallback",
        strategy=(
            _strategy_payload_from_text(
                normalized,
                operator_guided=(schedule_change or policy_writeback),
            )
            if should_writeback
            else None
        ),
        goal=(
            _goal_payload_from_text(normalized)
            if "backlog" in approved_targets
            else None
        ),
        schedule=(
            _schedule_payload_from_text(normalized)
            if "schedule" in approved_targets
            else None
        ),
    )


def _merge_model_decision_with_heuristic(
    model_decision: _ChatWritebackModelDecision,
    heuristic_decision: _ChatWritebackModelDecision,
) -> _ChatWritebackModelDecision:
    looks_empty = (
        model_decision.intent_kind == "chat"
        and not model_decision.should_writeback
        and not model_decision.kickoff_allowed
        and not model_decision.risky_actuation_requested
        and model_decision.team_role_gap_action is None
        and not model_decision.team_role_gap_notice
    )
    if looks_empty and heuristic_decision.confidence > model_decision.intent_confidence:
        return heuristic_decision

    payload = model_decision.model_dump(mode="json")
    if not payload.get("intent_signals") and heuristic_decision.intent_signals:
        payload["intent_signals"] = list(heuristic_decision.intent_signals)
    if not payload.get("approved_targets") and heuristic_decision.approved_targets:
        payload["approved_targets"] = list(heuristic_decision.approved_targets)
    if not payload.get("team_role_gap_action") and heuristic_decision.team_role_gap_action:
        payload["team_role_gap_action"] = heuristic_decision.team_role_gap_action
    if not payload.get("team_role_gap_notice") and heuristic_decision.team_role_gap_notice:
        payload["team_role_gap_notice"] = True
    if not payload.get("host_observation_requested") and heuristic_decision.host_observation_requested:
        payload["host_observation_requested"] = True
    if not payload.get("risky_actuation_requested") and heuristic_decision.risky_actuation_requested:
        payload["risky_actuation_requested"] = True
        payload["risky_actuation_surface"] = heuristic_decision.risky_actuation_surface
    if (
        not payload.get("should_writeback")
        and heuristic_decision.should_writeback
        and model_decision.confidence < 0.6
    ):
        payload["should_writeback"] = True
        payload["approved_targets"] = list(heuristic_decision.approved_targets)
        payload["strategy"] = (
            heuristic_decision.strategy.model_dump(mode="json")
            if heuristic_decision.strategy is not None
            else None
        )
        payload["goal"] = (
            heuristic_decision.goal.model_dump(mode="json")
            if heuristic_decision.goal is not None
            else None
        )
        payload["schedule"] = (
            heuristic_decision.schedule.model_dump(mode="json")
            if heuristic_decision.schedule is not None
            else None
        )
    if model_decision.intent_confidence <= 0 and heuristic_decision.intent_confidence > 0:
        payload["intent_confidence"] = heuristic_decision.intent_confidence
    if model_decision.confidence <= 0 and heuristic_decision.confidence > 0:
        payload["confidence"] = heuristic_decision.confidence
    return _ChatWritebackModelDecision.model_validate(payload)


def _decision_messages(text: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": _CHAT_WRITEBACK_MODEL_PLANNER_PROMPT,
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "latest_operator_message": text,
                },
                ensure_ascii=False,
            ),
        },
    ]


async def resolve_chat_writeback_model_decision(
    *,
    text: str | None,
) -> _ChatWritebackModelDecision | None:
    normalized = _first_non_empty(text)
    if normalized is None:
        return None
    cached = _get_cached_chat_writeback_decision(normalized)
    if cached is not None:
        return cached

    heuristic = _heuristic_chat_writeback_model_decision(normalized)
    if (
        heuristic.intent_kind in {"status-query", "discussion"}
        or heuristic.team_role_gap_action is not None
        or heuristic.team_role_gap_notice
    ):
        return _cache_chat_writeback_decision(normalized, heuristic)

    model_decision = await _resolve_model_chat_writeback_decision(normalized)
    return _cache_chat_writeback_decision(
        normalized,
        _merge_model_decision_with_heuristic(model_decision, heuristic),
    )


def resolve_chat_writeback_model_decision_sync(
    *,
    text: str | None,
) -> _ChatWritebackModelDecision | None:
    normalized = _first_non_empty(text)
    if normalized is None:
        return None
    cached = _get_cached_chat_writeback_decision(normalized)
    if cached is not None:
        return cached
    return asyncio.run(
        resolve_chat_writeback_model_decision(text=normalized),
    )


_normalize_chat_writeback_targets = normalize_chat_writeback_targets
_build_chat_writeback_plan_from_model_decision = build_chat_writeback_plan_from_model_decision
_resolve_chat_writeback_model_decision = resolve_chat_writeback_model_decision
_resolve_chat_writeback_model_decision_sync = resolve_chat_writeback_model_decision_sync
_resolve_team_role_gap_action_request = resolve_team_role_gap_action_request
_should_surface_team_role_gap_notice = should_surface_team_role_gap_notice
_should_trigger_industry_kickoff = should_trigger_industry_kickoff
_should_attempt_formal_chat_writeback = should_attempt_formal_chat_writeback
_team_role_gap_notice_message = team_role_gap_notice_message
_team_role_gap_resolution_message = team_role_gap_resolution_message


__all__ = [
    "_build_chat_writeback_plan_from_model_decision",
    "_normalize_chat_writeback_targets",
    "_resolve_chat_writeback_model_decision",
    "_resolve_chat_writeback_model_decision_sync",
    "_resolve_team_role_gap_action_request",
    "_should_attempt_formal_chat_writeback",
    "_should_surface_team_role_gap_notice",
    "_should_trigger_industry_kickoff",
    "_team_role_gap_notice_message",
    "_team_role_gap_resolution_message",
    "build_chat_writeback_plan_from_model_decision",
    "normalize_chat_writeback_targets",
    "resolve_chat_writeback_model_decision",
    "resolve_chat_writeback_model_decision_sync",
    "resolve_team_role_gap_action_request",
    "should_attempt_formal_chat_writeback",
    "should_surface_team_role_gap_notice",
    "should_trigger_industry_kickoff",
    "team_role_gap_notice_message",
    "team_role_gap_resolution_message",
]
