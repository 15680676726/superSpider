# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DecisionApproveRequest(BaseModel):
    resolution: str | None = Field(default=None)
    execute: bool | None = Field(default=None)


class DecisionRejectRequest(BaseModel):
    resolution: str | None = Field(default=None)


class GoalCompileActionRequest(BaseModel):
    context: dict[str, object] = Field(default_factory=dict)


class PatchActionRequest(BaseModel):
    actor: str = Field(default="system")


class GovernanceEmergencyStopRequest(BaseModel):
    actor: str = Field(default="runtime-center")
    reason: str = Field(default="Operator emergency stop")


class GovernanceResumeRequest(BaseModel):
    actor: str = Field(default="runtime-center")
    reason: str | None = Field(default=None)


class GovernanceDecisionBatchRequest(BaseModel):
    decision_ids: list[str] = Field(min_length=1)
    actor: str = Field(default="runtime-center")
    resolution: str | None = Field(default=None)
    execute: bool | None = Field(default=None)
    control_thread_id: str | None = Field(default=None)
    session_id: str | None = Field(default=None)
    user_id: str | None = Field(default=None)
    agent_id: str | None = Field(default=None)
    work_context_id: str | None = Field(default=None)


class GovernancePatchBatchRequest(BaseModel):
    patch_ids: list[str] = Field(min_length=1)
    actor: str = Field(default="runtime-center")


class SessionForceReleaseRequest(BaseModel):
    reason: str = Field(default="forced release from runtime center")


class BridgeSessionWorkAckRequest(BaseModel):
    lease_token: str = Field(min_length=1)
    work_id: str = Field(min_length=1)
    bridge_session_id: str | None = Field(default=None)
    ttl_seconds: int | None = Field(default=None, ge=1)
    workspace_trusted: bool | None = Field(default=None)
    elevated_auth_state: str | None = Field(default=None)
    browser_attach_transport_ref: str | None = Field(default=None)
    browser_attach_status: str | None = Field(default=None)
    browser_attach_session_ref: str | None = Field(default=None)
    browser_attach_scope_ref: str | None = Field(default=None)
    browser_attach_reconnect_token: str | None = Field(default=None)
    preferred_execution_path: str | None = Field(default=None)
    ui_fallback_mode: str | None = Field(default=None)
    adapter_gap_or_blocker: str | None = Field(default=None)
    handle: dict[str, object] | None = Field(default=None)


class BridgeSessionWorkHeartbeatRequest(BaseModel):
    lease_token: str = Field(min_length=1)
    work_id: str = Field(min_length=1)
    ttl_seconds: int | None = Field(default=None, ge=1)
    handle: dict[str, object] | None = Field(default=None)


class BridgeSessionWorkReconnectRequest(BaseModel):
    lease_token: str = Field(min_length=1)
    work_id: str = Field(min_length=1)
    ttl_seconds: int | None = Field(default=None, ge=1)
    browser_attach_transport_ref: str | None = Field(default=None)
    browser_attach_status: str | None = Field(default=None)
    browser_attach_session_ref: str | None = Field(default=None)
    browser_attach_scope_ref: str | None = Field(default=None)
    browser_attach_reconnect_token: str | None = Field(default=None)
    preferred_execution_path: str | None = Field(default=None)
    ui_fallback_mode: str | None = Field(default=None)
    adapter_gap_or_blocker: str | None = Field(default=None)
    handle: dict[str, object] | None = Field(default=None)


class BridgeSessionWorkStopRequest(BaseModel):
    work_id: str = Field(min_length=1)
    force: bool = Field(default=False)
    lease_token: str | None = Field(default=None)
    reason: str | None = Field(default=None)


class BridgeSessionArchiveRequest(BaseModel):
    lease_token: str | None = Field(default=None)
    reason: str | None = Field(default=None)


class BridgeEnvironmentDeregisterRequest(BaseModel):
    reason: str | None = Field(default=None)


class SharedOperatorAbortRequest(BaseModel):
    channel: str | None = Field(default=None)
    reason: str | None = Field(default=None)


class SharedOperatorAbortClearRequest(BaseModel):
    channel: str | None = Field(default=None)
    reason: str | None = Field(default="operator abort cleared")


class KnowledgeImportRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_ref: str | None = None
    role_bindings: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class KnowledgeChunkUpsertRequest(BaseModel):
    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_ref: str | None = None
    chunk_index: int = Field(default=0, ge=0)
    role_bindings: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class KnowledgeMemoryUpsertRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] = "agent"
    scope_id: str = Field(min_length=1)
    source_ref: str | None = None
    role_bindings: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class MemoryRebuildRequest(BaseModel):
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = Field(default=None)
    scope_id: str | None = Field(default=None)
    include_reporting: bool = True
    include_learning: bool = True
    evidence_limit: int = Field(default=200, ge=0, le=2000)


class MemoryReflectRequest(BaseModel):
    scope_type: Literal["global", "industry", "agent", "task", "work_context"]
    scope_id: str = Field(min_length=1)
    owner_agent_id: str | None = Field(default=None)
    industry_instance_id: str | None = Field(default=None)
    trigger_kind: str = Field(default="manual", min_length=1)
    create_learning_proposals: bool = True


class TaskBatchActionRequest(BaseModel):
    task_ids: list[str] = Field(default_factory=list)
    action: Literal["cancel"] = "cancel"
    actor: str = Field(default="runtime-center", min_length=1)
    reason: str | None = Field(default=None)


class ActorPauseRequest(BaseModel):
    reason: str | None = Field(default=None)
    actor: str = Field(default="runtime-center")


class ActorCancelRequest(BaseModel):
    task_id: str | None = Field(default=None)
    actor: str = Field(default="runtime-center")


class AgentCapabilityAssignmentRequest(BaseModel):
    capabilities: list[str] = Field(default_factory=list)
    mode: Literal["replace", "merge"] = "replace"
    actor: str = Field(default="runtime-center")
    reason: str | None = Field(default=None)


class GovernedAgentCapabilityAssignmentRequest(BaseModel):
    capabilities: list[str] = Field(default_factory=list)
    mode: Literal["replace", "merge"] = "replace"
    actor: str = Field(default="copaw-governance")
    reason: str | None = Field(default=None)
    use_recommended: bool = Field(default=True)


__all__ = [name for name in globals() if not name.startswith("__")]
