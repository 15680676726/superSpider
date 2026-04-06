# -*- coding: utf-8 -*-
"""SRK Kernel object models.

The kernel is the single runtime core described in AGENTS.md §6.2:
- Scheduling
- Lifecycle management
- Risk admission
- Result submission
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


RiskLevel = Literal["auto", "guarded", "confirm"]
TaskPhase = Literal[
    "pending",
    "risk-check",
    "executing",
    "waiting-confirm",
    "completed",
    "failed",
    "cancelled",
]


class KernelTask(BaseModel):
    """A task dispatched through the unified kernel."""

    id: str = Field(default_factory=lambda: f"ktask:{uuid4().hex[:12]}")
    trace_id: str = Field(
        default_factory=lambda: f"trace:{uuid4().hex[:12]}",
        description="Correlation id shared across kernel, capability, and evidence stages.",
    )
    goal_id: str | None = Field(
        default=None,
        description="Optional goal record this task belongs to",
    )
    parent_task_id: str | None = Field(
        default=None,
        description="Optional parent task id when this task is delegated.",
    )
    work_context_id: str | None = Field(
        default=None,
        description="Formal continuous work boundary shared across related tasks.",
    )
    title: str = Field(..., description="Human readable task title")
    capability_ref: str | None = Field(
        default=None,
        description="Which capability to invoke, e.g. 'tool:execute_shell_command'",
    )
    environment_ref: str | None = Field(
        default=None,
        description="EnvironmentMount where this task runs",
    )
    owner_agent_id: str = Field(
        default="copaw-agent-runner",
        description="Agent owning this task",
    )
    actor_owner_id: str | None = Field(
        default=None,
        description="Stable actor owner for resumable execution.",
    )
    phase: TaskPhase = Field(default="pending")
    risk_level: RiskLevel = Field(default="auto")
    task_segment: dict[str, object] = Field(
        default_factory=dict,
        description="Compiler-emitted segment metadata.",
    )
    resume_point: dict[str, object] = Field(
        default_factory=dict,
        description="Latest resume cursor / checkpoint hint.",
    )
    payload: dict[str, object] = Field(
        default_factory=dict,
        description="Opaque parameters for the capability",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class KernelResult(BaseModel):
    """Result of a kernel task execution."""

    task_id: str
    trace_id: str | None = None
    success: bool
    phase: TaskPhase
    summary: str = ""
    evidence_id: str | None = None
    decision_request_id: str | None = None
    error: str | None = None
    output: dict[str, object] | None = None
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def ready_for_execution(self) -> bool:
        return self.phase == "executing"

    def requires_confirmation(self) -> bool:
        return self.phase == "waiting-confirm"


class KernelConfig(BaseModel):
    """Kernel risk strategy configuration.

    Follows AGENTS.md §9 risk model:
    - auto: low risk, execute immediately
    - guarded: medium risk, log + execute
    - confirm: high risk, hold for human approval
    """

    default_risk_level: RiskLevel = "auto"
    auto_execute_risk_levels: list[RiskLevel] = Field(
        default_factory=lambda: ["auto", "guarded"],
    )
    confirm_risk_levels: list[RiskLevel] = Field(
        default_factory=lambda: ["confirm"],
    )
    decision_expiry_hours: int | None = Field(
        default=72,
        description="Auto-expire confirmation decisions after this many hours.",
    )
    execution_timeout_seconds: float | None = Field(
        default=180.0,
        gt=0,
        description="Fail execution if a kernel capability call exceeds this timeout.",
    )
