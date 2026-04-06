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
    knowledge_graph: dict[str, Any] | None = None


class MainBrainExecutionPlanner:
    def __init__(
        self,
        *,
        knowledge_graph_service: object | None = None,
    ) -> None:
        self._knowledge_graph_service = knowledge_graph_service

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
            knowledge_graph=self._build_knowledge_graph_summary(
                request=request,
                intake_contract=intake_contract,
            ),
        )

    def _build_knowledge_graph_summary(
        self,
        *,
        request: Any,
        intake_contract: MainBrainIntakeContract | None,
    ) -> dict[str, Any] | None:
        service = self._knowledge_graph_service
        activate = getattr(service, "activate_request_task_subgraph", None)
        summarize = getattr(service, "summarize_task_subgraph", None)
        if not callable(activate) or not callable(summarize):
            return None
        try:
            task_subgraph = activate(
                request=request,
                intake_contract=intake_contract,
                current_phase="main-brain-intake",
            )
        except Exception:
            return None
        if task_subgraph is None:
            return None
        try:
            summary = summarize(task_subgraph)
        except Exception:
            return None
        return dict(summary) if isinstance(summary, dict) and summary else None


__all__ = [
    "MainBrainExecutionPlan",
    "MainBrainExecutionPlanner",
]
