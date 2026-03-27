# -*- coding: utf-8 -*-
"""Semantic compiler layer — Layer 1 of the 7-layer architecture.

Compiles high-level semantic instructions (goals, plans, role prompts)
into concrete kernel tasks that can be dispatched through the SRK kernel.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


CompilableKind = Literal["goal", "plan", "role", "directive"]
TaskSegmentKind = Literal[
    "goal",
    "goal-step",
    "plan-step",
    "directive",
    "role-apply",
    "routine-replay",
    "sop-binding-trigger",
]
ResumeStrategy = Literal["resume-from-checkpoint", "restart-segment", "manual"]


def _next_compilation_unit_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"cu:{timestamp}-{uuid4().hex[:8]}"


class CompilationUnit(BaseModel):
    """A high-level semantic instruction to be compiled."""

    id: str = Field(default_factory=_next_compilation_unit_id)
    kind: CompilableKind
    source_text: str = Field(..., description="Natural language instruction")
    context: dict[str, object] = Field(default_factory=dict)
    actor_owner_id: str | None = None
    compiled_at: datetime | None = None


class CompiledTaskSegment(BaseModel):
    """Formal segment metadata for long-chain / resumable compilation."""

    segment_id: str = Field(..., min_length=1)
    segment_kind: TaskSegmentKind = "directive"
    index: int = Field(default=0, ge=0)
    total: int = Field(default=1, ge=1)
    actor_owner_id: str | None = None
    resume_strategy: ResumeStrategy = "resume-from-checkpoint"
    metadata: dict[str, object] = Field(default_factory=dict)


class ResumePoint(BaseModel):
    """Compiler-emitted starting checkpoint hint for runtime execution."""

    phase: str = Field(default="compiled", min_length=1)
    cursor: str | None = None
    checkpoint_kind: Literal["worker-step", "resume", "handoff", "task-result"] = (
        "resume"
    )
    owner_agent_id: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)


class CompiledTaskSpec(BaseModel):
    """Output of the compiler: a concrete task specification."""

    task_id: str | None = None
    title: str
    capability_ref: str | None = None
    environment_ref: str | None = None
    risk_level: str = "auto"
    payload: dict[str, object] = Field(default_factory=dict)
    source_unit_id: str | None = None
    actor_owner_id: str | None = None
    task_segment: CompiledTaskSegment | None = None
    resume_point: ResumePoint | None = None
