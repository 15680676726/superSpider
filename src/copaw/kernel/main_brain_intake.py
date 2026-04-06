# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..app.channels.schema import DEFAULT_CHANNEL
from ..industry.identity import EXECUTION_CORE_ROLE_ID, is_execution_core_agent_id
from ..app.runtime_commands import get_last_user_text
from ..industry.chat_writeback import ChatWritebackPlan, build_chat_writeback_plan_from_payload
from .query_execution_shared import (
    _build_chat_writeback_plan_from_model_decision,
    _first_non_empty,
    _message_query_text,
    _resolve_chat_writeback_model_decision,
)

_WRITEBACK_ACTION_TO_CLASSIFICATION = {
    "writeback_strategy": "strategy",
    "writeback_backlog": "backlog",
    "writeback_schedule": "schedule",
}


@dataclass(slots=True)
class MainBrainIntakeContract:
    message_text: str
    decision: Any
    intent_kind: str
    writeback_requested: bool
    writeback_plan: ChatWritebackPlan | None
    should_kickoff: bool

    @property
    def should_route_to_orchestrate(self) -> bool:
        return self.writeback_requested or self.should_kickoff or self.intent_kind == "execute-task"

    @property
    def has_active_writeback_plan(self) -> bool:
        return bool(self.writeback_plan is not None and self.writeback_plan.active)


def read_attached_main_brain_intake_contract(
    *,
    request: Any,
) -> MainBrainIntakeContract | None:
    intake_contract = getattr(request, "_copaw_main_brain_intake_contract", None)
    if intake_contract is None:
        return None
    if intake_contract.writeback_requested and not intake_contract.has_active_writeback_plan:
        raise RuntimeError(
            "Structured chat writeback was explicitly requested but could not be materialized.",
        )
    return intake_contract


def normalize_main_brain_runtime_context(
    value: Any,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if any(
        isinstance(value.get(key), dict)
        for key in ("intent", "environment", "recovery", "knowledge_graph")
    ):
        intent_payload = value.get("intent")
        environment_payload = value.get("environment")
        recovery_payload = value.get("recovery")
        knowledge_graph_payload = value.get("knowledge_graph")
        normalized = _compact_mapping(
            {
                "work_context_id": _first_non_empty(value.get("work_context_id")),
                "intent": {
                    "source_kind": _first_non_empty(
                        intent_payload.get("source_kind")
                        if isinstance(intent_payload, dict)
                        else None,
                        value.get("source_intent_kind"),
                    ),
                    "kind": _first_non_empty(
                        intent_payload.get("kind")
                        if isinstance(intent_payload, dict)
                        else None,
                        value.get("execution_intent"),
                    ),
                    "mode": _first_non_empty(
                        intent_payload.get("mode")
                        if isinstance(intent_payload, dict)
                        else None,
                        value.get("execution_mode"),
                    ),
                },
                "environment": {
                    "ref": _first_non_empty(
                        environment_payload.get("ref")
                        if isinstance(environment_payload, dict)
                        else None,
                        value.get("environment_ref"),
                    ),
                    "binding_kind": _first_non_empty(
                        environment_payload.get("binding_kind")
                        if isinstance(environment_payload, dict)
                        else None,
                        value.get("environment_binding_kind"),
                    ),
                    "kind": _first_non_empty(
                        environment_payload.get("kind")
                        if isinstance(environment_payload, dict)
                        else None,
                        value.get("environment_kind"),
                    ),
                    "session_id": _first_non_empty(
                        environment_payload.get("session_id")
                        if isinstance(environment_payload, dict)
                        else None,
                        value.get("environment_session_id"),
                    ),
                    "continuity_token": _first_non_empty(
                        environment_payload.get("continuity_token")
                        if isinstance(environment_payload, dict)
                        else None,
                        value.get("environment_continuity_token"),
                    ),
                    "continuity_source": _first_non_empty(
                        environment_payload.get("continuity_source")
                        if isinstance(environment_payload, dict)
                        else None,
                        value.get("environment_continuity_source"),
                    ),
                    "resume_ready": bool(
                        environment_payload.get("resume_ready")
                        if isinstance(environment_payload, dict)
                        else value.get("environment_resume_ready", False)
                    ),
                    "live_session_bound": bool(
                        environment_payload.get("live_session_bound")
                        if isinstance(environment_payload, dict)
                        else value.get("environment_live_session_bound", False)
                    ),
                    "surface_contracts": (
                        dict(environment_payload.get("surface_contracts"))
                        if isinstance(environment_payload, dict)
                        and isinstance(environment_payload.get("surface_contracts"), dict)
                        else {}
                    ),
                },
                "recovery": {
                    "mode": _first_non_empty(
                        recovery_payload.get("mode")
                        if isinstance(recovery_payload, dict)
                        else None,
                        value.get("recovery_mode"),
                    ),
                    "reason": _first_non_empty(
                        recovery_payload.get("reason")
                        if isinstance(recovery_payload, dict)
                        else None,
                        value.get("recovery_reason"),
                    ),
                    "checkpoint_id": _first_non_empty(
                        recovery_payload.get("checkpoint_id")
                        if isinstance(recovery_payload, dict)
                        else None,
                        value.get("resume_checkpoint_id"),
                    ),
                    "mailbox_id": _first_non_empty(
                        recovery_payload.get("mailbox_id")
                        if isinstance(recovery_payload, dict)
                        else None,
                        value.get("resume_mailbox_id"),
                    ),
                    "kernel_task_id": _first_non_empty(
                        recovery_payload.get("kernel_task_id")
                        if isinstance(recovery_payload, dict)
                        else None,
                        value.get("resume_kernel_task_id"),
                    ),
                },
                "knowledge_graph": _normalize_knowledge_graph_payload(
                    knowledge_graph_payload,
                ),
            },
        )
        return normalized or None
    normalized = _compact_mapping(
        {
            "work_context_id": _first_non_empty(value.get("work_context_id")),
            "intent": {
                "source_kind": _first_non_empty(value.get("source_intent_kind")),
                "kind": _first_non_empty(value.get("execution_intent")),
                "mode": _first_non_empty(value.get("execution_mode")),
            },
            "environment": {
                "ref": _first_non_empty(value.get("environment_ref")),
                "binding_kind": _first_non_empty(value.get("environment_binding_kind")),
                "kind": _first_non_empty(value.get("environment_kind")),
                "session_id": _first_non_empty(value.get("environment_session_id")),
                "continuity_token": _first_non_empty(value.get("environment_continuity_token")),
                "continuity_source": _first_non_empty(value.get("environment_continuity_source")),
                "resume_ready": bool(value.get("environment_resume_ready", False)),
                "live_session_bound": bool(value.get("environment_live_session_bound", False)),
                "surface_contracts": (
                    dict(value.get("surface_contracts"))
                    if isinstance(value.get("surface_contracts"), dict)
                    else {}
                ),
            },
            "recovery": {
                "mode": _first_non_empty(value.get("recovery_mode")),
                "reason": _first_non_empty(value.get("recovery_reason")),
                "checkpoint_id": _first_non_empty(value.get("resume_checkpoint_id")),
                "mailbox_id": _first_non_empty(value.get("resume_mailbox_id")),
                "kernel_task_id": _first_non_empty(value.get("resume_kernel_task_id")),
            },
            "knowledge_graph": _normalize_knowledge_graph_payload(
                value.get("knowledge_graph"),
            ),
        },
    )
    return normalized or None


def extract_main_brain_intake_text(msgs: list[Any]) -> str | None:
    latest_user_text = get_last_user_text(msgs)
    if latest_user_text:
        return latest_user_text
    return _message_query_text(msgs)


def materialize_main_brain_intake_contract(
    *,
    message_text: str,
    decision: Any | None,
) -> MainBrainIntakeContract | None:
    if not message_text or decision is None:
        return None
    intent_kind = str(getattr(decision, "intent_kind", "") or "").strip().lower()
    writeback_requested = bool(getattr(decision, "should_writeback", False))
    writeback_plan = None
    if writeback_requested:
        writeback_plan = _build_chat_writeback_plan_from_model_decision(
            text=message_text,
            decision=decision,
        )
    elif intent_kind == "execute-task":
        strategy = getattr(decision, "strategy", None)
        goal = getattr(decision, "goal", None)
        schedule = getattr(decision, "schedule", None)
        approved_targets = list(getattr(decision, "approved_targets", []) or []) or ["backlog"]
        writeback_plan = build_chat_writeback_plan_from_payload(
            message_text,
            approved_classifications=approved_targets,
            operator_requirements=(
                list(getattr(strategy, "operator_requirements", []) or [])
                if strategy is not None
                else None
            ),
            priority_order=(
                list(getattr(strategy, "priority_order", []) or []) if strategy is not None else None
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
            goal_title=_first_non_empty(getattr(goal, "title", None)),
            goal_summary=_first_non_empty(getattr(goal, "summary", None)),
            goal_plan_steps=list(getattr(goal, "plan_steps", []) or []) if goal is not None else None,
            schedule_title=_first_non_empty(getattr(schedule, "title", None)),
            schedule_summary=_first_non_empty(getattr(schedule, "summary", None)),
            schedule_cron=_first_non_empty(getattr(schedule, "cron", None)),
            schedule_prompt=_first_non_empty(getattr(schedule, "prompt", None)),
        )
    should_kickoff = bool(getattr(decision, "kickoff_allowed", False)) or bool(
        getattr(decision, "explicit_execution_confirmation", False),
    )
    return MainBrainIntakeContract(
        message_text=message_text,
        decision=decision,
        intent_kind=intent_kind,
        writeback_requested=writeback_requested,
        writeback_plan=writeback_plan,
        should_kickoff=should_kickoff,
    )


async def resolve_main_brain_intake_contract(
    *,
    text: str | None = None,
    msgs: list[Any] | None = None,
) -> MainBrainIntakeContract | None:
    message_text = _first_non_empty(text)
    if message_text is None and msgs is not None:
        message_text = extract_main_brain_intake_text(msgs)
    if message_text is None:
        return None
    decision = await _resolve_chat_writeback_model_decision(text=message_text)
    return materialize_main_brain_intake_contract(
        message_text=message_text,
        decision=decision,
    )


async def resolve_request_main_brain_intake_contract(
    *,
    request: Any,
    msgs: list[Any],
) -> MainBrainIntakeContract | None:
    attached = read_attached_main_brain_intake_contract(request=request)
    if attached is not None:
        return attached
    requested_actions = _normalize_requested_actions(getattr(request, "requested_actions", None))
    message_text = extract_main_brain_intake_text(msgs)
    if message_text is None:
        message_text = _first_non_empty(
            getattr(request, "text", None),
            getattr(request, "query", None),
            getattr(request, "message", None),
        )
    writeback_classifications = [
        classification
        for classification in (
            _WRITEBACK_ACTION_TO_CLASSIFICATION.get(action)
            for action in requested_actions
        )
        if classification is not None
    ]
    writeback_plan = build_chat_writeback_plan_from_payload(
        message_text,
        approved_classifications=writeback_classifications or None,
    )
    writeback_requested = bool(writeback_plan is not None and writeback_plan.active)
    should_kickoff = "kickoff_execution" in requested_actions
    if message_text is None and not should_kickoff:
        return None
    if not writeback_requested and not should_kickoff:
        return None
    return MainBrainIntakeContract(
        message_text=message_text or "",
        decision=None,
        intent_kind="execute-task" if should_kickoff else "chat",
        writeback_requested=writeback_requested,
        writeback_plan=writeback_plan,
        should_kickoff=should_kickoff,
    )


def resolve_execution_core_industry_instance_id(
    *,
    request: Any,
    owner_agent_id: str,
    agent_profile: Any | None,
) -> str | None:
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
    return industry_instance_id


def build_industry_chat_action_kwargs(
    *,
    industry_instance_id: str,
    message_text: str,
    owner_agent_id: str,
    request: Any,
) -> dict[str, Any]:
    return {
        "industry_instance_id": industry_instance_id,
        "message_text": message_text,
        "owner_agent_id": owner_agent_id,
        "session_id": _first_non_empty(getattr(request, "session_id", None)),
        "channel": _first_non_empty(getattr(request, "channel", None), DEFAULT_CHANNEL),
    }


def _compact_mapping(value: dict[str, Any]) -> dict[str, Any]:
    compacted: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, dict):
            nested = _compact_mapping(item)
            if nested:
                compacted[key] = nested
            continue
        if isinstance(item, bool):
            compacted[key] = item
            continue
        if item not in (None, ""):
            compacted[key] = item
    return compacted


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for raw in value:
        text = _first_non_empty(raw)
        if text is None or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def _normalize_requested_actions(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    actions: list[str] = []
    seen: set[str] = set()
    for raw in value:
        text = _first_non_empty(raw)
        if text is None:
            continue
        normalized = text.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        actions.append(normalized)
    return actions


def _normalize_knowledge_graph_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized = _compact_mapping(
        {
            "source": _first_non_empty(value.get("source")),
            "scope_type": _first_non_empty(value.get("scope_type")),
            "scope_id": _first_non_empty(value.get("scope_id")),
            "seed_refs": _string_list(value.get("seed_refs")),
            "focus_node_ids": _string_list(value.get("focus_node_ids")),
            "constraint_refs": _string_list(value.get("constraint_refs")),
            "evidence_refs": _string_list(value.get("evidence_refs")),
            "node_types": _string_list(value.get("node_types")),
            "top_entities": _string_list(value.get("top_entities")),
            "top_opinions": _string_list(value.get("top_opinions")),
            "top_relations": _string_list(value.get("top_relations")),
            "top_relation_kinds": _string_list(value.get("top_relation_kinds")),
            "capability_labels": _string_list(value.get("capability_labels")),
            "environment_labels": _string_list(value.get("environment_labels")),
            "failure_patterns": _string_list(value.get("failure_patterns")),
            "recovery_patterns": _string_list(value.get("recovery_patterns")),
            "support_paths": _string_list(value.get("support_paths")),
            "contradiction_paths": _string_list(value.get("contradiction_paths")),
            "dependency_paths": _string_list(value.get("dependency_paths")),
            "blocker_paths": _string_list(value.get("blocker_paths")),
            "recovery_paths": _string_list(value.get("recovery_paths")),
        },
    )
    for key in ("node_count", "relation_count"):
        raw = value.get(key)
        if isinstance(raw, int):
            normalized[key] = raw
    return normalized


__all__ = [
    "MainBrainIntakeContract",
    "build_industry_chat_action_kwargs",
    "extract_main_brain_intake_text",
    "materialize_main_brain_intake_contract",
    "read_attached_main_brain_intake_contract",
    "normalize_main_brain_runtime_context",
    "resolve_execution_core_industry_instance_id",
    "resolve_main_brain_intake_contract",
    "resolve_request_main_brain_intake_contract",
]
