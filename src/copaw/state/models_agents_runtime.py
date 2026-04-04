# -*- coding: utf-8 -*-
"""Persisted actor runtime carrier records."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .model_support import UpdatedRecord, _new_record_id, _utc_now
from .models_core import (
    ActorDesiredState,
    AgentCheckpointStatus,
    AgentLeaseStatus,
    AgentMailboxStatus,
    AgentRuntimeStatus,
    AgentThreadBindingKind,
)


class AgentRuntimeRecord(UpdatedRecord):
    """Formal persisted actor runtime container for a visible agent."""

    agent_id: str = Field(..., min_length=1)
    actor_key: str = Field(..., min_length=1)
    actor_fingerprint: str | None = None
    actor_class: Literal["system", "industry-dynamic", "agent"] = "agent"
    desired_state: ActorDesiredState = "active"
    runtime_status: AgentRuntimeStatus = "idle"
    employment_mode: Literal["career", "temporary"] = "career"
    activation_mode: Literal["persistent", "on-demand"] = "persistent"
    persistent: bool = True
    industry_instance_id: str | None = None
    industry_role_id: str | None = None
    display_name: str | None = None
    role_name: str | None = None
    current_task_id: str | None = None
    current_mailbox_id: str | None = None
    current_environment_id: str | None = None
    queue_depth: int = Field(default=0, ge=0)
    last_started_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_stopped_at: datetime | None = None
    last_error_summary: str | None = None
    last_result_summary: str | None = None
    last_checkpoint_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentMailboxRecord(UpdatedRecord):
    """Formal persisted mailbox/inbox entry for actor-driven execution."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    agent_id: str = Field(..., min_length=1)
    task_id: str | None = None
    work_context_id: str | None = None
    parent_mailbox_id: str | None = None
    source_agent_id: str | None = None
    envelope_type: Literal["query", "goal", "delegation", "control", "task"] = "task"
    title: str = Field(..., min_length=1)
    summary: str = ""
    status: AgentMailboxStatus = "queued"
    priority: int = Field(default=0, ge=0)
    capability_ref: str | None = None
    conversation_thread_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result_summary: str | None = None
    error_summary: str | None = None
    lease_owner: str | None = None
    lease_token: str | None = None
    claimed_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_after_at: datetime | None = None
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentCheckpointRecord(UpdatedRecord):
    """Formal persisted checkpoint for resumable actor execution."""

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


class AgentLeaseRecord(UpdatedRecord):
    """Formal persisted actor lease separate from session mounts."""

    id: str = Field(default_factory=_new_record_id, min_length=1)
    agent_id: str = Field(..., min_length=1)
    lease_kind: Literal["actor-runtime", "environment", "thread"] = "actor-runtime"
    resource_ref: str = Field(..., min_length=1)
    lease_status: AgentLeaseStatus = "leased"
    lease_token: str | None = None
    owner: str | None = None
    acquired_at: datetime = Field(default_factory=_utc_now)
    expires_at: datetime | None = None
    heartbeat_at: datetime | None = None
    released_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentThreadBindingRecord(UpdatedRecord):
    """Formal persisted actor-first thread binding and legacy alias mapping."""

    thread_id: str = Field(..., min_length=1)
    agent_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    channel: str = Field(default="console", min_length=1)
    binding_kind: AgentThreadBindingKind = "agent-primary"
    industry_instance_id: str | None = None
    industry_role_id: str | None = None
    work_context_id: str | None = None
    owner_scope: str | None = None
    active: bool = True
    alias_of_thread_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutomationLoopRuntimeRecord(UpdatedRecord):
    """Formal persisted runtime snapshot for a durable automation loop."""

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
    last_error_summary: str | None = None
    submit_count: int = Field(default=0, ge=0)
    consecutive_failures: int = Field(default=0, ge=0)


__all__ = [
    "AgentCheckpointRecord",
    "AgentLeaseRecord",
    "AgentMailboxRecord",
    "AgentRuntimeRecord",
    "AgentThreadBindingRecord",
    "AutomationLoopRuntimeRecord",
]
