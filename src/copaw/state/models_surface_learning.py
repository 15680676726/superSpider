# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from .model_support import UpdatedRecord, _new_record_id, _normalize_text_list

SurfaceLearningScopeLevel = Literal[
    "site",
    "application",
    "document_family",
    "role_scope",
    "industry_scope",
    "work_context",
    "session",
]
SurfaceLearningStatus = Literal["active", "superseded", "inactive"]
SurfaceLearningRiskLevel = Literal["auto", "guarded", "confirm"]


class SurfaceCapabilityTwinRecord(UpdatedRecord):
    """Long-lived learned capability merged from surface observations and transitions."""

    twin_id: str = Field(default_factory=_new_record_id, min_length=1)
    scope_level: SurfaceLearningScopeLevel = "role_scope"
    scope_id: str = Field(..., min_length=1)
    capability_name: str = Field(..., min_length=1)
    capability_kind: str = Field(default="action", min_length=1)
    surface_kind: str = ""
    summary: str = ""
    entry_conditions: list[str] = Field(default_factory=list)
    entry_regions: list[str] = Field(default_factory=list)
    required_state_signals: list[str] = Field(default_factory=list)
    probe_steps: list[str] = Field(default_factory=list)
    execution_steps: list[str] = Field(default_factory=list)
    result_signals: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    risk_level: SurfaceLearningRiskLevel = "auto"
    evidence_refs: list[str] = Field(default_factory=list)
    source_transition_refs: list[str] = Field(default_factory=list)
    source_discovery_refs: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    status: SurfaceLearningStatus = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "entry_conditions",
        "entry_regions",
        "required_state_signals",
        "probe_steps",
        "execution_steps",
        "result_signals",
        "failure_modes",
        "evidence_refs",
        "source_transition_refs",
        "source_discovery_refs",
        mode="before",
    )
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


class SurfacePlaybookRecord(UpdatedRecord):
    """Fast executable projection compiled from the active capability twins for one scope."""

    playbook_id: str = Field(default_factory=_new_record_id, min_length=1)
    twin_id: str | None = None
    scope_level: SurfaceLearningScopeLevel = "role_scope"
    scope_id: str = Field(..., min_length=1)
    summary: str = ""
    capability_names: list[str] = Field(default_factory=list)
    recommended_steps: list[str] = Field(default_factory=list)
    probe_steps: list[str] = Field(default_factory=list)
    execution_steps: list[str] = Field(default_factory=list)
    success_signals: list[str] = Field(default_factory=list)
    blocker_signals: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    status: SurfaceLearningStatus = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "capability_names",
        "recommended_steps",
        "probe_steps",
        "execution_steps",
        "success_signals",
        "blocker_signals",
        "evidence_refs",
        mode="before",
    )
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return _normalize_text_list(value)


__all__ = [
    "SurfaceCapabilityTwinRecord",
    "SurfaceLearningRiskLevel",
    "SurfaceLearningScopeLevel",
    "SurfaceLearningStatus",
    "SurfacePlaybookRecord",
]
