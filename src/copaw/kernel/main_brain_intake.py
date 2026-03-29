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


def read_attached_main_brain_runtime_context(
    *,
    request: Any,
) -> dict[str, Any] | None:
    return normalize_main_brain_runtime_context(
        getattr(request, "_copaw_main_brain_runtime_context", None),
    )


def normalize_main_brain_runtime_context(
    value: Any,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if any(isinstance(value.get(key), dict) for key in ("intent", "environment", "recovery")):
        intent_payload = value.get("intent")
        environment_payload = value.get("environment")
        recovery_payload = value.get("recovery")
        normalized = _compact_mapping(
            {
                "intent": {
                    "source_kind": _first_non_empty(
                        intent_payload.get("source_kind")
                        if isinstance(intent_payload, dict)
                        else None,
                    ),
                    "kind": _first_non_empty(
                        intent_payload.get("kind")
                        if isinstance(intent_payload, dict)
                        else None,
                    ),
                    "mode": _first_non_empty(
                        intent_payload.get("mode")
                        if isinstance(intent_payload, dict)
                        else None,
                    ),
                },
                "environment": {
                    "ref": _first_non_empty(
                        environment_payload.get("ref")
                        if isinstance(environment_payload, dict)
                        else None,
                    ),
                    "binding_kind": _first_non_empty(
                        environment_payload.get("binding_kind")
                        if isinstance(environment_payload, dict)
                        else None,
                    ),
                    "kind": _first_non_empty(
                        environment_payload.get("kind")
                        if isinstance(environment_payload, dict)
                        else None,
                    ),
                    "session_id": _first_non_empty(
                        environment_payload.get("session_id")
                        if isinstance(environment_payload, dict)
                        else None,
                    ),
                    "continuity_token": _first_non_empty(
                        environment_payload.get("continuity_token")
                        if isinstance(environment_payload, dict)
                        else None,
                    ),
                    "continuity_source": _first_non_empty(
                        environment_payload.get("continuity_source")
                        if isinstance(environment_payload, dict)
                        else None,
                    ),
                    "resume_ready": bool(
                        environment_payload.get("resume_ready")
                        if isinstance(environment_payload, dict)
                        else False
                    ),
                },
                "recovery": {
                    "mode": _first_non_empty(
                        recovery_payload.get("mode")
                        if isinstance(recovery_payload, dict)
                        else None,
                    ),
                    "reason": _first_non_empty(
                        recovery_payload.get("reason")
                        if isinstance(recovery_payload, dict)
                        else None,
                    ),
                    "checkpoint_id": _first_non_empty(
                        recovery_payload.get("checkpoint_id")
                        if isinstance(recovery_payload, dict)
                        else None,
                    ),
                    "mailbox_id": _first_non_empty(
                        recovery_payload.get("mailbox_id")
                        if isinstance(recovery_payload, dict)
                        else None,
                    ),
                    "kernel_task_id": _first_non_empty(
                        recovery_payload.get("kernel_task_id")
                        if isinstance(recovery_payload, dict)
                        else None,
                    ),
                },
            },
        )
        return normalized or None
    normalized = _compact_mapping(
        {
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
            },
            "recovery": {
                "mode": _first_non_empty(value.get("recovery_mode")),
                "reason": _first_non_empty(value.get("recovery_reason")),
                "checkpoint_id": _first_non_empty(value.get("resume_checkpoint_id")),
                "mailbox_id": _first_non_empty(value.get("resume_mailbox_id")),
                "kernel_task_id": _first_non_empty(value.get("resume_kernel_task_id")),
            },
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
    return await resolve_main_brain_intake_contract(msgs=msgs)


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


__all__ = [
    "MainBrainIntakeContract",
    "build_industry_chat_action_kwargs",
    "extract_main_brain_intake_text",
    "materialize_main_brain_intake_contract",
    "read_attached_main_brain_intake_contract",
    "read_attached_main_brain_runtime_context",
    "normalize_main_brain_runtime_context",
    "resolve_execution_core_industry_instance_id",
    "resolve_main_brain_intake_contract",
    "resolve_request_main_brain_intake_contract",
]
