# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if value is None:
        return {}
    namespace_dict = getattr(value, "__dict__", None)
    if isinstance(namespace_dict, dict):
        return dict(namespace_dict)
    return {}


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _clip_text(value: Any, *, limit: int) -> str:
    text = _first_non_empty(value) or ""
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1] + "…"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def build_buddy_persona_prompt(
    surface: Any,
    heading: str = "##",
) -> tuple[list[str], str]:
    profile = _as_mapping(getattr(surface, "profile", None))
    target = _as_mapping(getattr(surface, "growth_target", None))
    relationship = _as_mapping(getattr(surface, "relationship", None))
    presentation = _as_mapping(getattr(surface, "presentation", None))

    profile_id = _clip_text(
        _first_non_empty(profile.get("profile_id"), getattr(surface, "profile_id", None)),
        limit=96,
    ) or "unknown"

    buddy_name = _clip_text(
        _first_non_empty(presentation.get("buddy_name"), "你的伙伴"),
        limit=48,
    )
    display_name = _clip_text(_first_non_empty(profile.get("display_name")), limit=48)
    profession = _clip_text(_first_non_empty(profile.get("profession")), limit=48)
    current_stage = _clip_text(_first_non_empty(profile.get("current_stage")), limit=48)
    primary_direction = _clip_text(
        _first_non_empty(target.get("primary_direction")),
        limit=96,
    )
    final_goal = _clip_text(
        _first_non_empty(presentation.get("current_goal_summary")),
        limit=140,
    )
    current_task = _clip_text(
        _first_non_empty(presentation.get("current_task_summary")),
        limit=140,
    )
    why_now = _clip_text(
        _first_non_empty(presentation.get("why_now_summary")),
        limit=160,
    )
    next_action = _clip_text(
        _first_non_empty(presentation.get("single_next_action_summary")),
        limit=160,
    )
    strategy = _clip_text(
        _first_non_empty(presentation.get("companion_strategy_summary")),
        limit=200,
    )
    encouragement_style = _clip_text(
        _first_non_empty(relationship.get("encouragement_style")),
        limit=48,
    )
    service_intent = _clip_text(
        _first_non_empty(relationship.get("service_intent")),
        limit=180,
    )
    collaboration_role = _clip_text(
        _first_non_empty(relationship.get("collaboration_role")),
        limit=48,
    )
    autonomy_level = _clip_text(
        _first_non_empty(relationship.get("autonomy_level")),
        limit=48,
    )
    report_style = _clip_text(
        _first_non_empty(relationship.get("report_style")),
        limit=48,
    )
    collaboration_notes = _clip_text(
        _first_non_empty(relationship.get("collaboration_notes")),
        limit=180,
    )
    confirm_boundaries = _string_list(relationship.get("confirm_boundaries"))

    heading_text = _first_non_empty(heading, "##") or "##"
    lines = [
        f"{heading_text} 伙伴对外人格",
        f"- 伙伴名：{buddy_name}",
        "- 你现在以主脑显化出来的伙伴人格对外说话，但本质仍然是主脑。",
        f"- 你陪伴的人：{display_name or '未命名用户'} / {profession or '当前职业待补充'} / {current_stage or '当前阶段待补充'}",
        f"- 当前确认的长期主方向：{primary_direction or '先帮对方收口一个足够大的长期方向'}",
        "- 默认只给用户最终目标、当前任务、为什么现在做、唯一下一步和已完成进展；信息够就直接推进，不要停在陪聊。",
        "- 默认会主动推进当前任务，不只是陪聊。",
        f"- 最终目标：{final_goal or '先把长期目标收成一句真正对人有意义的话'}",
        f"- 当前任务：{current_task or '先把眼前这一小步收清楚'}",
        f"- 为什么现在做：{why_now or '因为现在这一步决定后续是不是还在真正前进'}",
        f"- 唯一下一步：{next_action or '先把当前任务缩成一个最小动作'}",
        f"- 伙伴策略：{strategy or '先直接推进当前任务，做完后主动同步结果和下一步，不要只陪聊'}",
    ]
    if encouragement_style:
        lines.append(f"- 当前鼓励风格代号：{encouragement_style}")
    if service_intent:
        lines.append(f"- 服务意图：{service_intent}")
    if collaboration_role:
        lines.append(f"- 协作角色：{collaboration_role}")
    if autonomy_level:
        lines.append(f"- 主动级别：{autonomy_level}")
    if report_style:
        lines.append(f"- 汇报风格：{report_style}")
    if confirm_boundaries:
        lines.append(f"- 这些事项必须先确认：{', '.join(confirm_boundaries[:4])}")
    if collaboration_notes:
        lines.append(f"- 协作备注：{collaboration_notes}")
    lines.extend(
        [
            "- 说话方式要像真正一起做事的伙伴，默认直接推进任务，做完主动汇报，不要客服腔。",
            "- 用户不追问，你也要在完成、卡住、需要关键输入时主动同步。",
            "- 不要暴露后台执行位抢前台，也不要把系统内部结构直接甩给用户。",
            "- 默认先把当前工作往前推进，再汇报结果和下一步。",
        ],
    )
    signature = "|".join(
        (
            f"buddy:{profile_id}",
            buddy_name,
            service_intent,
            collaboration_role,
            autonomy_level,
            report_style,
            ",".join(confirm_boundaries[:4]),
            final_goal,
            current_task,
            why_now,
            next_action,
            strategy,
        ),
    )
    return lines, signature
