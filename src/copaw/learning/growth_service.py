# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from .models import GrowthEvent
from .growth_runtime import LearningGrowthRuntimeService
from .runtime_core import LearningRuntimeCore


class LearningGrowthService:
    """Growth-facing learning operations."""

    def __init__(self, core: LearningRuntimeCore) -> None:
        self._core = core
        self._runtime = LearningGrowthRuntimeService(core)

    def list_growth(
        self,
        *,
        agent_id: str | None = None,
        goal_id: str | None = None,
        task_id: str | None = None,
        source_patch_id: str | None = None,
        source_evidence_id: str | None = None,
        category: str | None = None,
        created_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[GrowthEvent]:
        events = self._runtime.list_growth(
            agent_id=agent_id,
            goal_id=goal_id,
            task_id=task_id,
            source_patch_id=source_patch_id,
            source_evidence_id=source_evidence_id,
            created_since=created_since,
            limit=limit,
        )
        if category is None:
            return events
        return [event for event in events if event.change_type == category]

    def record_agent_outcome(self, **kwargs) -> GrowthEvent:
        return self._runtime.record_agent_outcome(**kwargs)

    def get_growth_event(self, event_id: str) -> GrowthEvent:
        return self._runtime.get_growth_event(event_id)

    def delete_growth_event(self, event_id: str) -> bool:
        return self._runtime.delete_growth_event(event_id)


__all__ = ["LearningGrowthService"]
