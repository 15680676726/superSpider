# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..owner import ProfessionSurfaceOperationCheckpoint

DocumentExecutionStatus = Literal["succeeded", "blocked", "failed"]


class DocumentObservation(BaseModel):
    document_path: str = ""
    document_family: str = ""
    content_text: str = ""
    revision_token: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)


class DocumentExecutionStep(BaseModel):
    intent_kind: str
    payload: dict[str, str] = Field(default_factory=dict)
    success_assertion: dict[str, str] = Field(default_factory=dict)
    fallback_policy: str = ""


class DocumentExecutionResult(BaseModel):
    status: DocumentExecutionStatus
    intent_kind: str = ""
    before_observation: DocumentObservation | None = None
    after_observation: DocumentObservation | None = None
    readback: dict[str, str] = Field(default_factory=dict)
    verification_passed: bool = False
    blocker_kind: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class DocumentExecutionLoopResult(BaseModel):
    steps: list[DocumentExecutionResult] = Field(default_factory=list)
    final_observation: DocumentObservation | None = None
    stop_reason: str = ""
    operation_checkpoint: ProfessionSurfaceOperationCheckpoint | None = None


__all__ = [
    "DocumentExecutionLoopResult",
    "DocumentExecutionResult",
    "DocumentExecutionStatus",
    "DocumentExecutionStep",
    "DocumentObservation",
]
