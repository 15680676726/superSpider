# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..graph_models import SurfaceGraphSnapshot
from ..owner import ProfessionSurfaceOperationCheckpoint

DesktopTargetKind = Literal["window", "input", "button"]
DesktopExecutionStatus = Literal["succeeded", "blocked", "failed"]


class DesktopTargetCandidate(BaseModel):
    target_kind: DesktopTargetKind
    action_selector: str = ""
    readback_key: str = ""
    scope_anchor: str = ""
    score: int = 0
    label: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class DesktopObservation(BaseModel):
    app_identity: str = ""
    window_title: str = ""
    slot_candidates: dict[str, list[DesktopTargetCandidate]] = Field(default_factory=dict)
    readback: dict[str, str] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    surface_graph: SurfaceGraphSnapshot | None = None


class DesktopExecutionStep(BaseModel):
    intent_kind: str
    target_slot: str
    payload: dict[str, str] = Field(default_factory=dict)
    success_assertion: dict[str, str] = Field(default_factory=dict)
    fallback_policy: str = ""


class DesktopExecutionResult(BaseModel):
    status: DesktopExecutionStatus
    intent_kind: str = ""
    target_slot: str = ""
    resolved_target: DesktopTargetCandidate | None = None
    before_observation: DesktopObservation | None = None
    after_observation: DesktopObservation | None = None
    before_graph: SurfaceGraphSnapshot | None = None
    after_graph: SurfaceGraphSnapshot | None = None
    readback: dict[str, str] = Field(default_factory=dict)
    verification_passed: bool = False
    blocker_kind: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class DesktopExecutionLoopResult(BaseModel):
    steps: list[DesktopExecutionResult] = Field(default_factory=list)
    final_observation: DesktopObservation | None = None
    stop_reason: str = ""
    operation_checkpoint: ProfessionSurfaceOperationCheckpoint | None = None


__all__ = [
    "DesktopExecutionLoopResult",
    "DesktopExecutionResult",
    "DesktopExecutionStatus",
    "DesktopExecutionStep",
    "DesktopObservation",
    "DesktopTargetCandidate",
    "DesktopTargetKind",
]
