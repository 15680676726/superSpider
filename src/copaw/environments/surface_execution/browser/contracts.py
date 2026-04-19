# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..graph_models import SurfaceGraphSnapshot
from ..owner import ProfessionSurfaceOperationCheckpoint

BrowserTargetKind = Literal["input", "button", "toggle", "link", "menu", "tab", "upload"]
BrowserElementKind = Literal["textarea", "input", "contenteditable", "button", "generic"]
BrowserExecutionStatus = Literal["succeeded", "blocked", "failed"]


class BrowserTargetCandidate(BaseModel):
    target_kind: BrowserTargetKind
    action_ref: str = ""
    action_selector: str = ""
    readback_selector: str = ""
    element_kind: BrowserElementKind = "generic"
    scope_anchor: str = ""
    score: int = 0
    reason: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class BrowserPageSummary(BaseModel):
    page_kind: str = ""
    headline: str = ""
    primary_text: str = ""
    action_hints: list[str] = Field(default_factory=list)
    blocker_hints: list[str] = Field(default_factory=list)


class BrowserObservation(BaseModel):
    page_url: str = ""
    page_title: str = ""
    snapshot_text: str = ""
    interactive_targets: list[BrowserTargetCandidate] = Field(default_factory=list)
    primary_input_candidates: list[BrowserTargetCandidate] = Field(default_factory=list)
    slot_candidates: dict[str, list[BrowserTargetCandidate]] = Field(default_factory=dict)
    control_groups: list[dict[str, object]] = Field(default_factory=list)
    readable_sections: list[dict[str, object]] = Field(default_factory=list)
    login_state: str = ""
    blockers: list[str] = Field(default_factory=list)
    page_summary: BrowserPageSummary = Field(default_factory=BrowserPageSummary)
    surface_graph: SurfaceGraphSnapshot | None = None


class BrowserExecutionStep(BaseModel):
    intent_kind: str
    target_slot: str
    payload: dict[str, str] = Field(default_factory=dict)
    success_assertion: dict[str, str] = Field(default_factory=dict)
    fallback_policy: str = ""


class BrowserExecutionResult(BaseModel):
    status: BrowserExecutionStatus
    intent_kind: str = ""
    target_slot: str = ""
    resolved_target: BrowserTargetCandidate | None = None
    before_observation: BrowserObservation | None = None
    after_observation: BrowserObservation | None = None
    before_graph: SurfaceGraphSnapshot | None = None
    after_graph: SurfaceGraphSnapshot | None = None
    readback: dict[str, str] = Field(default_factory=dict)
    verification_passed: bool = False
    blocker_kind: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class BrowserExecutionLoopResult(BaseModel):
    steps: list[BrowserExecutionResult] = Field(default_factory=list)
    final_observation: BrowserObservation | None = None
    stop_reason: str = ""
    operation_checkpoint: ProfessionSurfaceOperationCheckpoint | None = None


__all__ = [
    "BrowserElementKind",
    "BrowserExecutionLoopResult",
    "BrowserExecutionResult",
    "BrowserExecutionStatus",
    "BrowserExecutionStep",
    "BrowserObservation",
    "BrowserPageSummary",
    "BrowserTargetCandidate",
    "BrowserTargetKind",
]
