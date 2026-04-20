# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .model_support import UpdatedRecord, _new_record_id

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
