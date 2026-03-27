# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .main_brain_intake import MainBrainIntakeContract


def _non_empty_str(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return None


def _resolve_request_environment_ref(request: Any) -> str | None:
    return (
        _non_empty_str(getattr(request, "environment_ref", None))
        or _non_empty_str(getattr(request, "active_environment_id", None))
        or _non_empty_str(getattr(request, "current_environment_id", None))
    )


@dataclass(slots=True)
class MainBrainExecutionPlan:
    intent_kind: str
    source_intent_kind: str | None
    execution_mode: str


class MainBrainExecutionPlanner:
    def plan(
        self,
        *,
        request: Any,
        intake_contract: MainBrainIntakeContract | None,
    ) -> MainBrainExecutionPlan:
        source_intent_kind = _non_empty_str(
            getattr(intake_contract, "intent_kind", None),
        )
        if intake_contract is None or not intake_contract.should_route_to_orchestrate:
            return MainBrainExecutionPlan(
                intent_kind="chat",
                source_intent_kind=source_intent_kind,
                execution_mode="chat",
            )
        execution_mode = (
            "environment-bound"
            if _resolve_request_environment_ref(request) is not None
            else "delegated"
        )
        return MainBrainExecutionPlan(
            intent_kind="orchestrate",
            source_intent_kind=source_intent_kind,
            execution_mode=execution_mode,
        )


__all__ = [
    "MainBrainExecutionPlan",
    "MainBrainExecutionPlanner",
]
