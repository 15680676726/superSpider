# -*- coding: utf-8 -*-
"""Read models for the Runtime Center operator surface."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class RuntimeCenterSurfaceInfo(BaseModel):
    """Metadata describing the live Runtime Center operator surface."""

    version: Literal["runtime-center-v1"] = "runtime-center-v1"
    mode: Literal["operator-surface"] = "operator-surface"
    status: Literal["state-service", "degraded", "unavailable"] = "unavailable"
    read_only: bool = False
    source: str = Field(..., description="Current backing source summary")
    note: str = Field(
        default=(
            "Runtime Center is the operator surface backed by the "
            "shared state, evidence, goal, learning, and environment services."
        ),
    )
    services: list[str] = Field(
        default_factory=lambda: [
            "RuntimeCenterStateQueryService",
            "RuntimeCenterEvidenceQueryService",
            "RuntimeCenterQueryService",
        ],
    )


class RuntimeOverviewEntry(BaseModel):
    """One overview row rendered inside a runtime-center card."""

    id: str
    title: str
    kind: str
    status: str
    owner: str | None = None
    summary: str | None = None
    updated_at: datetime | None = None
    route: str | None = None
    actions: dict[str, str] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)


class RuntimeOverviewCard(BaseModel):
    """A compact frontend-friendly overview card."""

    key: str
    title: str
    source: str
    status: Literal["state-service", "degraded", "unavailable"]
    count: int = 0
    summary: str
    entries: list[RuntimeOverviewEntry] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class RuntimeOverviewResponse(BaseModel):
    """Top-level response for the runtime-center overview endpoint."""

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    surface: RuntimeCenterSurfaceInfo
    cards: list[RuntimeOverviewCard] = Field(default_factory=list)


class RuntimeMainBrainSection(BaseModel):
    """Compact section payload used by the dedicated main-brain cockpit."""

    count: int = 0
    summary: str | None = None
    route: str | None = None
    entries: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class RuntimeMainBrainResponse(BaseModel):
    """Dedicated main-brain cockpit payload for Runtime Center."""

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    surface: RuntimeCenterSurfaceInfo
    strategy: dict[str, Any] = Field(default_factory=dict)
    carrier: dict[str, Any] = Field(default_factory=dict)
    lanes: list[dict[str, Any]] = Field(default_factory=list)
    cycles: list[dict[str, Any]] = Field(default_factory=list)
    backlog: list[dict[str, Any]] = Field(default_factory=list)
    current_cycle: dict[str, Any] | None = None
    assignments: list[dict[str, Any]] = Field(default_factory=list)
    reports: list[dict[str, Any]] = Field(default_factory=list)
    report_cognition: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)
    governance: dict[str, Any] = Field(default_factory=dict)
    recovery: dict[str, Any] = Field(default_factory=dict)
    automation: dict[str, Any] = Field(default_factory=dict)
    evidence: RuntimeMainBrainSection = Field(default_factory=RuntimeMainBrainSection)
    decisions: RuntimeMainBrainSection = Field(default_factory=RuntimeMainBrainSection)
    patches: RuntimeMainBrainSection = Field(default_factory=RuntimeMainBrainSection)
    signals: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
