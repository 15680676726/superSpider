# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

_SPACE_RE = re.compile(r"\s+")
_PRIORITY_RE = re.compile(
    r"(?:\u6539\u6210|\u6539\u4e3a|\u8c03\u6574\u4e3a|\u73b0\u5728|\u4ee5\u540e)?(?:\u5148\u505a|\u5148\u628a)(?P<first>.+?)(?:\uff0c|,|\u7136\u540e|\u518d\u505a|\u518d\u628a)(?P<second>.+)",
)
_PRIORITIZE_RE = re.compile(r"(?:\u4f18\u5148|\u5148\u505a|\u5148\u628a)(?P<item>[^\uff0c,\u3002\uff1b;]+)")
_PAUSE_RE = re.compile(r"(?:\u4e0d\u8981\u518d|\u4e0d\u8981|\u6682\u505c|\u5148\u522b)(?P<item>[^\uff0c,\u3002\uff1b;]+)")
_APPROVED_WRITEBACK_CLASSIFICATIONS = frozenset({"strategy", "backlog", "schedule"})


@dataclass(slots=True)
class StrategyWritebackPlan:
    operator_requirements: list[str] = field(default_factory=list)
    priority_order: list[str] = field(default_factory=list)
    execution_constraints: list[str] = field(default_factory=list)
    switch_to_operator_guided: bool = False


@dataclass(slots=True)
class GoalWritebackPlan:
    title: str
    summary: str
    plan_steps: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ScheduleWritebackPlan:
    title: str
    summary: str
    cron: str
    prompt: str


@dataclass(slots=True)
class ChatWritebackPlan:
    raw_text: str
    normalized_text: str
    fingerprint: str
    strategy: StrategyWritebackPlan
    goal: GoalWritebackPlan | None = None
    schedule: ScheduleWritebackPlan | None = None
    classifications: list[str] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return bool(self.classifications)

def _build_chat_writeback_plan(
    message_text: str | None,
    *,
    approved_classifications: list[str] | None = None,
    operator_requirements: list[str] | None = None,
    priority_order: list[str] | None = None,
    execution_constraints: list[str] | None = None,
    switch_to_operator_guided: bool | None = None,
    goal_title: str | None = None,
    goal_summary: str | None = None,
    goal_plan_steps: list[str] | None = None,
    schedule_title: str | None = None,
    schedule_summary: str | None = None,
    schedule_cron: str | None = None,
    schedule_prompt: str | None = None,
) -> ChatWritebackPlan | None:
    normalized_text = _normalize_text(message_text)
    if normalized_text is None or len(normalized_text) < 4:
        return None
    approved_targets = _normalize_approved_classifications(approved_classifications)
    if not approved_targets:
        return None

    resolved_priority_order = _normalize_text_list(priority_order)
    if not resolved_priority_order:
        resolved_priority_order = _extract_priority_order(normalized_text)
    resolved_execution_constraints = _normalize_text_list(execution_constraints)
    if not resolved_execution_constraints:
        resolved_execution_constraints = _extract_execution_constraints(normalized_text)
    resolved_operator_requirements = (
        _normalize_text_list(operator_requirements) or [normalized_text]
    )
    goal_requested = "backlog" in approved_targets
    schedule_requested = "schedule" in approved_targets

    strategy = StrategyWritebackPlan(
        operator_requirements=resolved_operator_requirements,
        priority_order=resolved_priority_order,
        execution_constraints=resolved_execution_constraints,
        switch_to_operator_guided=(
            bool(switch_to_operator_guided)
            if switch_to_operator_guided is not None
            else bool(resolved_priority_order or resolved_execution_constraints)
        ),
    )
    topic = _resolve_topic_label(normalized_text)
    goal = (
        _build_goal_plan(
            text=normalized_text,
            topic=topic,
            title=goal_title,
            summary=goal_summary,
            plan_steps=goal_plan_steps,
        )
        if goal_requested
        else None
    )
    schedule = (
        _build_schedule_plan(
            text=normalized_text,
            topic=topic,
            title=schedule_title,
            summary=schedule_summary,
            cron=schedule_cron,
            prompt=schedule_prompt,
        )
        if schedule_requested
        else None
    )

    classifications = list(approved_targets)
    fingerprint = hashlib.sha1(normalized_text.encode("utf-8")).hexdigest()[:12]
    return ChatWritebackPlan(
        raw_text=message_text or normalized_text,
        normalized_text=normalized_text,
        fingerprint=fingerprint,
        strategy=strategy,
        goal=goal,
        schedule=schedule,
        classifications=classifications,
    )


def build_chat_writeback_plan(
    message_text: str | None,
    *,
    approved_classifications: list[str] | None = None,
    operator_requirements: list[str] | None = None,
    priority_order: list[str] | None = None,
    execution_constraints: list[str] | None = None,
    switch_to_operator_guided: bool | None = None,
    goal_title: str | None = None,
    goal_summary: str | None = None,
    goal_plan_steps: list[str] | None = None,
    schedule_title: str | None = None,
    schedule_summary: str | None = None,
    schedule_cron: str | None = None,
    schedule_prompt: str | None = None,
) -> ChatWritebackPlan | None:
    return _build_chat_writeback_plan(
        message_text,
        approved_classifications=approved_classifications,
        operator_requirements=operator_requirements,
        priority_order=priority_order,
        execution_constraints=execution_constraints,
        switch_to_operator_guided=switch_to_operator_guided,
        goal_title=goal_title,
        goal_summary=goal_summary,
        goal_plan_steps=goal_plan_steps,
        schedule_title=schedule_title,
        schedule_summary=schedule_summary,
        schedule_cron=schedule_cron,
        schedule_prompt=schedule_prompt,
    )


def build_chat_writeback_plan_from_payload(
    message_text: str | None,
    *,
    approved_classifications: list[str] | None = None,
    operator_requirements: list[str] | None = None,
    priority_order: list[str] | None = None,
    execution_constraints: list[str] | None = None,
    switch_to_operator_guided: bool | None = None,
    goal_title: str | None = None,
    goal_summary: str | None = None,
    goal_plan_steps: list[str] | None = None,
    schedule_title: str | None = None,
    schedule_summary: str | None = None,
    schedule_cron: str | None = None,
    schedule_prompt: str | None = None,
) -> ChatWritebackPlan | None:
    return build_chat_writeback_plan(
        message_text,
        approved_classifications=approved_classifications,
        operator_requirements=operator_requirements,
        priority_order=priority_order,
        execution_constraints=execution_constraints,
        switch_to_operator_guided=switch_to_operator_guided,
        goal_title=goal_title,
        goal_summary=goal_summary,
        goal_plan_steps=goal_plan_steps,
        schedule_title=schedule_title,
        schedule_summary=schedule_summary,
        schedule_cron=schedule_cron,
        schedule_prompt=schedule_prompt,
    )


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = _SPACE_RE.sub(" ", str(value).strip())
    return text or None


def _normalize_approved_classifications(
    value: list[str] | None,
) -> list[str] | None:
    if value is None:
        return None
    normalized: list[str] = []
    for item in value:
        text = str(item or "").strip().lower()
        if text in _APPROVED_WRITEBACK_CLASSIFICATIONS and text not in normalized:
            normalized.append(text)
    if normalized and "strategy" not in normalized:
        normalized.insert(0, "strategy")
    return normalized


def _normalize_text_list(value: list[str] | None) -> list[str]:
    if not value:
        return []
    normalized: list[str] = []
    for item in value:
        text = _normalize_text(item)
        if text is not None:
            normalized.append(text)
    return normalized


def _extract_priority_order(text: str) -> list[str]:
    match = _PRIORITY_RE.search(text)
    if match is not None:
        first = _clean_clause(match.group("first"))
        second = _clean_clause(match.group("second"))
        priorities: list[str] = []
        if first is not None:
            priorities.append(f"\u5148\u505a{first}")
        if second is not None:
            priorities.append(f"\u518d\u505a{second}")
        return priorities
    match = _PRIORITIZE_RE.search(text)
    if match is None:
        return []
    item = _clean_clause(match.group("item"))
    return [f"\u4f18\u5148{item}"] if item is not None else []


def _extract_execution_constraints(text: str) -> list[str]:
    match = _PAUSE_RE.search(text)
    if match is None:
        return []
    item = _clean_clause(match.group("item"))
    if item is None:
        return []
    return [f"\u5f53\u524d\u5148\u4e0d\u8981{item}"]


def _clean_clause(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip(" \uff0c,\u3002\uff1b;:\uff1a")
    return cleaned or None


def _resolve_topic_label(text: str) -> str:
    clipped = text[:22].strip()
    if len(text) > 22:
        return f"{clipped}..."
    if clipped:
        return clipped
    return "new execution requirement"


def _build_goal_plan(
    *,
    text: str,
    topic: str,
    title: str | None,
    summary: str | None,
    plan_steps: list[str] | None,
) -> GoalWritebackPlan:
    resolved_title = _normalize_text(title)
    if resolved_title is None:
        resolved_title = topic
    resolved_title = resolved_title if len(resolved_title) <= 28 else resolved_title[:28]
    resolved_summary = _normalize_text(summary) or text
    resolved_plan_steps = _normalize_text_list(plan_steps) or [
        "Clarify the scope and acceptance criteria.",
        "Break the requirement into governed execution steps.",
        "Launch the first move and write back evidence and next step.",
    ]
    return GoalWritebackPlan(
        title=resolved_title,
        summary=resolved_summary,
        plan_steps=resolved_plan_steps,
    )


def _build_schedule_plan(
    *,
    text: str,
    topic: str,
    title: str | None,
    summary: str | None,
    cron: str | None,
    prompt: str | None,
) -> ScheduleWritebackPlan:
    resolved_title = _normalize_text(title) or f"{topic} cadence"
    resolved_summary = _normalize_text(summary) or (
        f"Persist the new operator instruction as a recurring cadence: {text}"
    )
    resolved_cron = _normalize_text(cron) or "0 9 * * *"
    resolved_prompt = _normalize_text(prompt) or (
        "Execute against the formally recorded long-term instruction: "
        f"{text}. Review the current goal, constraints, and evidence requirements before acting."
    )
    return ScheduleWritebackPlan(
        title=resolved_title,
        summary=resolved_summary,
        cron=resolved_cron,
        prompt=resolved_prompt,
    )
