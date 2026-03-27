# -*- coding: utf-8 -*-
"""Environment mount object model.

An EnvironmentMount represents a persistent execution environment that
capabilities can operate within.  Current examples include:

- workspace (cwd / project directory)
- browser (URL / page session)
- session (channel + session_id)
- terminal (shell process)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


EnvironmentKind = Literal[
    "workspace",
    "browser",
    "session",
    "terminal",
    "desktop",
    "file-view",
    "channel-session",
    "observation-cache",
]
LeaseStatus = Literal["idle", "leased", "released", "expired"]


class EnvironmentMount(BaseModel):
    """Formal object representing a mounted execution environment."""

    id: str = Field(
        ...,
        description="Unique identifier, e.g. 'env:workspace:/path' or 'env:browser:https://...'",
    )
    kind: EnvironmentKind = Field(
        ...,
        description="Environment type: workspace, browser, session, terminal",
    )
    display_name: str = Field(
        ...,
        description="Human readable label for this environment",
    )
    ref: str = Field(
        ...,
        description="Original environment_ref value from evidence/bridge",
    )
    status: str = Field(
        default="active",
        description="Environment lifecycle status: active, idle, closed",
    )
    last_active_at: datetime | None = Field(
        default=None,
        description="When this environment was last active",
    )
    evidence_count: int = Field(
        default=0,
        description="Number of evidence records referencing this environment",
    )
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description="Additional context (session_id, channel, pid, etc.)",
    )
    lease_status: LeaseStatus | None = Field(
        default=None,
        description="Current lease lifecycle state for the live handle.",
    )
    lease_owner: str | None = Field(
        default=None,
        description="Current owner of the live lease.",
    )
    lease_token: str | None = Field(
        default=None,
        description="Opaque lease token for heartbeat/release validation.",
    )
    lease_acquired_at: datetime | None = Field(
        default=None,
        description="When the current lease was acquired.",
    )
    lease_expires_at: datetime | None = Field(
        default=None,
        description="When the current lease expires unless heartbeated.",
    )
    live_handle_ref: str | None = Field(
        default=None,
        description="Opaque ref to an in-memory live handle.",
    )


class EnvironmentSummary(BaseModel):
    """Aggregate statistics about mounted environments."""

    total: int = 0
    active: int = 0
    by_kind: dict[str, int] = Field(default_factory=dict)


class SessionMount(BaseModel):
    """Persistent session mount for long-lived conversations."""

    id: str = Field(
        ...,
        description="Stable session mount id, e.g. session:channel:session_id",
    )
    environment_id: str = Field(
        ...,
        description="EnvironmentMount id backing this session",
    )
    channel: str = Field(..., description="Channel identifier")
    session_id: str = Field(..., description="Session id within channel")
    user_id: str | None = Field(default=None, description="Optional user id")
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_active_at: datetime | None = Field(default=None)
    metadata: dict[str, object] = Field(default_factory=dict)
    lease_status: LeaseStatus | None = None
    lease_owner: str | None = None
    lease_token: str | None = None
    lease_acquired_at: datetime | None = None
    lease_expires_at: datetime | None = None
    live_handle_ref: str | None = None


class ObservationRecord(BaseModel):
    """Cached observation derived from evidence."""

    evidence_id: str
    environment_ref: str | None = None
    capability_ref: str | None = None
    action_summary: str
    result_summary: str
    risk_level: str
    created_at: datetime


class ReplayEntry(BaseModel):
    evidence_id: str
    replay_id: str
    replay_type: str
    storage_uri: str
    summary: str
    created_at: datetime
    metadata: dict[str, object] = Field(default_factory=dict)


class ArtifactEntry(BaseModel):
    evidence_id: str
    artifact_id: str
    artifact_type: str
    storage_uri: str
    summary: str
    created_at: datetime
