# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

from .service_lifecycle import _IndustryLifecycleMixin


class IndustryViewService:
    """Read-model owner for industry runtime/status/detail surfaces."""

    def __init__(self, facade: object) -> None:
        self._facade = facade

    def list_instances(
        self,
        *,
        status: str | None = "active",
        limit: int | None = None,
    ):
        records = list(
            self._facade._industry_instance_repository.list_instances(
                status=None,
                limit=None,
            )
        )
        summaries = [
            summary
            for summary in (self._facade._build_instance_summary(record) for record in records)
            if status is None or summary.status == status
            if any(
                (summary.stats.get(key) or 0) > 0
                for key in (
                    "agent_count",
                    "lane_count",
                    "backlog_count",
                    "cycle_count",
                    "assignment_count",
                    "report_count",
                    "schedule_count",
                )
            )
        ]
        summaries.sort(
            key=lambda item: item.updated_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        if limit is not None:
            summaries = summaries[: max(0, limit)]
        return summaries

    def count_instances(self) -> int:
        return len(self.list_instances(status="active", limit=None))

    def get_instance_record(self, instance_id: str):
        return self._facade._industry_instance_repository.get_instance(instance_id)

    def get_instance_detail(
        self,
        instance_id: str,
        *,
        assignment_id: str | None = None,
        backlog_item_id: str | None = None,
    ):
        record = self._facade._industry_instance_repository.get_instance(instance_id)
        if record is None:
            return None
        if assignment_id is None and backlog_item_id is None:
            return self._facade._build_instance_detail(record)
        return self._facade._build_instance_detail(
            record,
            assignment_id=assignment_id,
            backlog_item_id=backlog_item_id,
        )

    def reconcile_instance_status(self, instance_id: str):
        record = self._facade._industry_instance_repository.get_instance(instance_id)
        if record is None:
            return None
        record = self._facade._reconcile_kickoff_autonomy_status(record)
        next_status = self._facade._derive_instance_status(record)
        if next_status == record.status:
            return record
        updated = record.model_copy(
            update={
                "status": next_status,
                "updated_at": datetime.now(timezone.utc),
            },
        )
        return self._facade._industry_instance_repository.upsert_instance(updated)

    def reconcile_instance_status_for_goal(self, goal_id: str) -> None:
        _IndustryLifecycleMixin.reconcile_instance_status_for_goal(
            self._facade,
            goal_id,
        )
