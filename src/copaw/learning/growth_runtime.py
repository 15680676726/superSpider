# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import GrowthEvent
from .runtime_support import (
    _compact_metadata,
    _growth_matches,
    _normalize_optional_str,
)
from .runtime_support import LearningRuntimeDelegate


class LearningGrowthRuntimeService(LearningRuntimeDelegate):
    """Growth entrypoints extracted from the runtime core."""

    def list_growth(
        self,
        *,
        agent_id: str | None = None,
        goal_id: str | None = None,
        task_id: str | None = None,
        source_patch_id: str | None = None,
        source_evidence_id: str | None = None,
        created_since: datetime | None = None,
        limit: int | None = 50,
    ) -> list[GrowthEvent]:
        needs_extra_filter = any(
            value is not None
            for value in (goal_id, task_id, source_patch_id, source_evidence_id)
        )
        if limit is None:
            query_limit = None
        elif needs_extra_filter:
            query_limit = max(limit, 200)
        else:
            query_limit = limit
        events = self._engine.get_growth_history(
            agent_id=None if needs_extra_filter else agent_id,
            created_since=created_since,
            limit=query_limit,
        )
        filtered = [
            event
            for event in events
            if _growth_matches(
                event,
                agent_id=agent_id,
                goal_id=goal_id,
                task_id=task_id,
                source_patch_id=source_patch_id,
                source_evidence_id=source_evidence_id,
            )
            and (created_since is None or event.created_at >= created_since)
        ]
        if limit is None:
            return filtered
        return filtered[:limit]

    def record_agent_outcome(
        self,
        *,
        agent_id: str | None,
        title: str,
        status: str,
        change_type: str,
        description: str | None = None,
        capability_ref: str | None = None,
        task_id: str | None = None,
        goal_id: str | None = None,
        source_evidence_id: str | None = None,
        risk_level: str = "auto",
        source_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        industry_role_id: str | None = None,
        role_name: str | None = None,
        owner_scope: str | None = None,
        error_summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GrowthEvent | None:
        normalized_agent_id = _normalize_optional_str(agent_id)
        normalized_title = _normalize_optional_str(title)
        normalized_status = _normalize_optional_str(status)
        normalized_change_type = _normalize_optional_str(change_type)
        if (
            normalized_agent_id is None
            or normalized_title is None
            or normalized_status is None
            or normalized_change_type is None
        ):
            return None
        summary_text = (
            _normalize_optional_str(description)
            or _normalize_optional_str(error_summary)
            or normalized_title
        )
        event = self._engine.record_growth(
            GrowthEvent(
                agent_id=normalized_agent_id,
                goal_id=_normalize_optional_str(goal_id),
                task_id=_normalize_optional_str(task_id),
                change_type=normalized_change_type,
                description=summary_text,
                source_evidence_id=_normalize_optional_str(source_evidence_id),
                risk_level=_normalize_optional_str(risk_level) or "auto",
                result=normalized_status,
            ),
        )
        self._publish_runtime_event(
            topic="growth",
            action="recorded",
            payload={
                "event_id": event.id,
                "agent_id": event.agent_id,
                "goal_id": event.goal_id,
                "task_id": event.task_id,
                "change_type": event.change_type,
                "result": event.result,
            },
        )
        remember = (
            getattr(self._experience_memory_service, "remember_outcome", None)
            if self._experience_memory_service is not None
            else None
        )
        if callable(remember):
            remember(
                agent_id=normalized_agent_id,
                title=normalized_title,
                status=normalized_status,
                summary=summary_text,
                error_summary=_normalize_optional_str(error_summary),
                capability_ref=_normalize_optional_str(capability_ref),
                task_id=_normalize_optional_str(task_id),
                source_agent_id=_normalize_optional_str(source_agent_id),
                industry_instance_id=_normalize_optional_str(industry_instance_id),
                industry_role_id=_normalize_optional_str(industry_role_id),
                role_name=_normalize_optional_str(role_name),
                owner_scope=_normalize_optional_str(owner_scope),
                metadata=_compact_metadata(metadata),
            )
        return event

    def get_growth_event(self, event_id: str) -> GrowthEvent:
        return self._engine.get_growth_event(event_id)

    def delete_growth_event(self, event_id: str) -> bool:
        deleted = self._engine.delete_growth_event(event_id)
        if deleted:
            self._publish_runtime_event(
                topic="growth",
                action="deleted",
                payload={"event_id": event_id},
            )
        return deleted


__all__ = ["LearningGrowthRuntimeService"]
