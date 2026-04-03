# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..kernel.models import KernelTask


@dataclass(slots=True)
class CapabilityExecutionContext:
    task_id: str
    trace_id: str | None = None
    goal_id: str | None = None
    work_context_id: str | None = None
    owner_agent_id: str | None = None
    capability_ref: str | None = None
    environment_ref: str | None = None
    risk_level: str = "auto"
    action_mode: str | None = None
    concurrency_class: str | None = None
    preflight_policy: str | None = None
    evidence_mode: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def is_read_only(self) -> bool:
        return self.action_mode == "read"

    @classmethod
    def from_kernel_task(
        cls,
        task: "KernelTask",
        *,
        action_mode: str | None = None,
        concurrency_class: str | None = None,
        preflight_policy: str | None = None,
        evidence_mode: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> "CapabilityExecutionContext":
        return cls(
            task_id=task.id,
            trace_id=task.trace_id,
            goal_id=task.goal_id,
            work_context_id=task.work_context_id,
            owner_agent_id=task.owner_agent_id,
            capability_ref=task.capability_ref,
            environment_ref=task.environment_ref,
            risk_level=task.risk_level,
            action_mode=action_mode,
            concurrency_class=concurrency_class,
            preflight_policy=preflight_policy,
            evidence_mode=evidence_mode,
            payload=dict(payload or {}),
        )
