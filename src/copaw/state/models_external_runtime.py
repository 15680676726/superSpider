# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .model_support import UpdatedRecord, _new_record_id

ExternalCapabilityRuntimeKind = Literal["cli", "service"]
ExternalCapabilityRuntimeScopeKind = Literal["session", "work_context", "seat"]
ExternalCapabilityRuntimeStatus = Literal[
    "starting",
    "restarting",
    "ready",
    "degraded",
    "completed",
    "stopped",
    "failed",
    "orphaned",
]


class ExternalCapabilityRuntimeInstanceRecord(UpdatedRecord):
    runtime_id: str = Field(default_factory=_new_record_id, min_length=1)
    capability_id: str = Field(min_length=1)
    runtime_kind: ExternalCapabilityRuntimeKind
    scope_kind: ExternalCapabilityRuntimeScopeKind = "session"
    work_context_id: str | None = None
    owner_agent_id: str | None = None
    environment_ref: str | None = None
    session_mount_id: str | None = None
    status: ExternalCapabilityRuntimeStatus = "starting"
    command: str = ""
    cwd: str | None = None
    process_id: int | None = None
    port: int | None = None
    health_url: str | None = None
    lease_owner_ref: str | None = None
    continuity_policy: str = "scoped"
    retention_policy: str = "until-stop"
    last_started_at: datetime | None = None
    last_ready_at: datetime | None = None
    last_stopped_at: datetime | None = None
    last_exit_code: int | None = None
    last_error: str | None = None
    latest_start_evidence_id: str | None = None
    latest_healthcheck_evidence_id: str | None = None
    latest_stop_evidence_id: str | None = None
    latest_recovery_evidence_id: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    replay_pointer: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
