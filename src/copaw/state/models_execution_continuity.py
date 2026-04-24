# -*- coding: utf-8 -*-
"""Persisted execution continuity records that survive actor-runtime retirement."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .model_support import UpdatedRecord, _new_record_id
from .models_core import AgentCheckpointStatus


class AgentCheckpointRecord(UpdatedRecord):
    """Persisted checkpoint for resumable query/executor continuity."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    agent_id: str = Field(..., min_length=1)
    mailbox_id: str | None = None
    task_id: str | None = None
    work_context_id: str | None = None
    checkpoint_kind: Literal["worker-step", "resume", "handoff", "task-result"] = (
        "worker-step"
    )
    status: AgentCheckpointStatus = "ready"
    phase: str = Field(default="", min_length=0)
    cursor: str | None = None
    conversation_thread_id: str | None = None
    environment_ref: str | None = None
    snapshot_payload: dict[str, Any] = Field(default_factory=dict)
    resume_payload: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


class AutomationLoopRuntimeRecord(UpdatedRecord):
    """Persisted runtime snapshot for a durable automation loop."""

    automation_task_id: str = Field(..., min_length=1)
    task_name: str = Field(..., min_length=1)
    capability_ref: str = Field(..., min_length=1)
    owner_agent_id: str = Field(..., min_length=1)
    interval_seconds: int = Field(default=30, ge=0)
    coordinator_contract: str = Field(default="automation-coordinator/v1", min_length=1)
    loop_phase: str = Field(default="idle", min_length=1)
    health_status: str = Field(default="idle", min_length=1)
    last_gate_reason: str | None = None
    last_result_phase: str | None = None
    last_result_summary: str | None = None
    last_error_summary: str | None = None
    last_task_id: str | None = None
    last_evidence_id: str | None = None
    submit_count: int = Field(default=0, ge=0)
    consecutive_failures: int = Field(default=0, ge=0)


__all__ = [
    "AgentCheckpointRecord",
    "AutomationLoopRuntimeRecord",
]
