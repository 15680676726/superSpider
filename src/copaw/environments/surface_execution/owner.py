# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field


class ProfessionSurfaceOperationPlan(BaseModel):
    intent_kind: str
    target_slot: str = ""
    payload: dict[str, str] = Field(default_factory=dict)
    success_assertion: dict[str, str] = Field(default_factory=dict)
    fallback_policy: str = ""


class ProfessionSurfaceOperationCheckpoint(BaseModel):
    formal_session_id: str
    surface_kind: str
    surface_thread_id: str
    step_index: int = 0
    last_status: str = ""
    last_blocker_kind: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProfessionSurfaceOperationOwner:
    def __init__(
        self,
        *,
        formal_session_id: str,
        surface_thread_id: str,
        planner: Callable[..., ProfessionSurfaceOperationPlan | None],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._formal_session_id = str(formal_session_id or "").strip()
        self._surface_thread_id = str(surface_thread_id or "").strip()
        self._planner = planner
        self._metadata = dict(metadata or {})

    def build_checkpoint(
        self,
        *,
        surface_kind: str,
        step_index: int,
        history: list[object],
    ) -> ProfessionSurfaceOperationCheckpoint:
        last_status = ""
        last_blocker_kind = ""
        if history:
            last_step = history[-1]
            last_status = str(getattr(last_step, "status", "") or "").strip()
            last_blocker_kind = str(getattr(last_step, "blocker_kind", "") or "").strip()
        return ProfessionSurfaceOperationCheckpoint(
            formal_session_id=self._formal_session_id,
            surface_kind=str(surface_kind or "").strip(),
            surface_thread_id=self._surface_thread_id,
            step_index=max(0, int(step_index)),
            last_status=last_status,
            last_blocker_kind=last_blocker_kind,
            metadata=dict(self._metadata),
        )

    def plan(
        self,
        *,
        observation: object,
        history: list[object],
        checkpoint: ProfessionSurfaceOperationCheckpoint,
    ) -> ProfessionSurfaceOperationPlan | None:
        return self._planner(
            observation=observation,
            history=list(history),
            checkpoint=checkpoint,
        )


__all__ = [
    "ProfessionSurfaceOperationCheckpoint",
    "ProfessionSurfaceOperationOwner",
    "ProfessionSurfaceOperationPlan",
]
