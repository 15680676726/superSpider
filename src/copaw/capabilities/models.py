# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


CapabilityKind = Literal[
    "local-tool",
    "remote-mcp",
    "skill-bundle",
    "project-package",
    "adapter",
    "runtime-component",
    "provider-admin",
    "system-op",
]

SourceKind = Literal["tool", "skill", "mcp", "project", "adapter", "runtime", "system"]


class CapabilityMount(BaseModel):
    """Phase 2 read model for the unified capability graph."""

    id: str
    name: str
    summary: str
    kind: CapabilityKind
    source_kind: SourceKind = "system"

    # --- risk contract ---
    risk_level: str
    risk_description: str = ""

    # --- environment contract ---
    environment_requirements: list[str] = Field(default_factory=list)
    environment_description: str = ""

    # --- evidence contract ---
    evidence_contract: list[str] = Field(default_factory=list)
    evidence_description: str = ""

    # --- access & policy ---
    role_access_policy: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # --- executor metadata ---
    executor_ref: str | None = None
    provider_ref: str | None = None
    timeout_policy: str | None = None
    package_ref: str | None = None
    package_kind: str | None = None
    package_version: str | None = None
    replay_support: bool = False
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilitySummary(BaseModel):
    total: int
    enabled: int
    by_kind: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)


