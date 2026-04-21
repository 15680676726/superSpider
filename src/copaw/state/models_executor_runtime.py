# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .model_support import CreatedRecord, UpdatedRecord, _new_record_id

ExecutorProtocolKind = Literal["app_server", "api", "sdk", "cli_runtime", "unknown"]
ExecutorRuntimeScopeKind = Literal["assignment", "role", "project", "session"]
ExecutorRuntimeStatus = Literal[
    "starting",
    "restarting",
    "ready",
    "degraded",
    "completed",
    "stopped",
    "failed",
    "orphaned",
]
ExecutorSelectionMode = Literal["single-runtime", "role-routed", "task-routed", "manual"]
ModelInvocationOwnershipMode = Literal["runtime_owned", "copaw_managed", "hybrid"]
ExecutorTurnStatus = Literal["queued", "running", "completed", "failed", "stopped"]


class RoleContractRecord(UpdatedRecord):
    role_id: str = Field(default_factory=_new_record_id, min_length=1)
    display_name: str = Field(min_length=1)
    summary: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    planning_contract: str = ""
    reporting_contract: str = ""
    escalation_rules: list[str] = Field(default_factory=list)
    default_skill_set: list[str] = Field(default_factory=list)
    default_project_profile: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectProfileRecord(UpdatedRecord):
    project_profile_id: str = Field(default_factory=_new_record_id, min_length=1)
    root_path: str = Field(min_length=1)
    agents_md_path: str | None = None
    role_md_path: str | None = None
    project_md_path: str | None = None
    skill_root: str | None = None
    runtime_root: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionPolicyRecord(UpdatedRecord):
    policy_id: str = Field(default_factory=_new_record_id, min_length=1)
    policy_name: str = Field(min_length=1)
    sandbox_mode: str = "use_default"
    approval_mode: str = "never"
    network_mode: str = "enabled"
    notes: str = ""
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutorProviderRecord(UpdatedRecord):
    provider_id: str = Field(default_factory=_new_record_id, min_length=1)
    provider_kind: str = Field(default="external-executor", min_length=1)
    runtime_family: str = Field(min_length=1)
    control_surface_kind: str = Field(min_length=1)
    install_source_kind: str | None = None
    source_ref: str | None = None
    default_protocol_kind: ExecutorProtocolKind = "unknown"
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoleExecutorBindingRecord(UpdatedRecord):
    binding_id: str = Field(default_factory=_new_record_id, min_length=1)
    role_id: str = Field(min_length=1)
    executor_provider_id: str = Field(min_length=1)
    selection_mode: ExecutorSelectionMode = "role-routed"
    project_profile_id: str | None = None
    execution_policy_id: str | None = None
    model_policy_id: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelInvocationPolicyRecord(UpdatedRecord):
    policy_id: str = Field(default_factory=_new_record_id, min_length=1)
    ownership_mode: ModelInvocationOwnershipMode = "runtime_owned"
    default_model_ref: str | None = None
    role_overrides: dict[str, str] = Field(default_factory=dict)
    task_overrides_allowed: bool = False
    cost_tracking_mode: str = "runtime-native"
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutorRuntimeInstanceRecord(UpdatedRecord):
    runtime_id: str = Field(default_factory=_new_record_id, min_length=1)
    executor_id: str = Field(min_length=1)
    protocol_kind: ExecutorProtocolKind = "unknown"
    scope_kind: ExecutorRuntimeScopeKind = "assignment"
    assignment_id: str | None = None
    role_id: str | None = None
    project_profile_id: str | None = None
    thread_id: str | None = None
    runtime_status: ExecutorRuntimeStatus = "starting"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutorThreadBindingRecord(UpdatedRecord):
    binding_id: str = Field(default_factory=_new_record_id, min_length=1)
    runtime_id: str = Field(min_length=1)
    role_id: str | None = None
    executor_provider_id: str = Field(min_length=1)
    project_profile_id: str | None = None
    assignment_id: str | None = None
    thread_id: str = Field(min_length=1)
    runtime_status: ExecutorRuntimeStatus = "starting"
    last_turn_id: str | None = None
    last_seen_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutorTurnRecord(UpdatedRecord):
    turn_record_id: str = Field(default_factory=_new_record_id, min_length=1)
    runtime_id: str = Field(min_length=1)
    thread_binding_id: str = Field(min_length=1)
    assignment_id: str | None = None
    thread_id: str | None = None
    turn_id: str = Field(min_length=1)
    turn_status: ExecutorTurnStatus = "queued"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutorEventRecord(CreatedRecord):
    event_id: str = Field(default_factory=_new_record_id, min_length=1)
    runtime_id: str = Field(min_length=1)
    turn_record_id: str | None = None
    assignment_id: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    event_type: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    raw_method: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
