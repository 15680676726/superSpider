# -*- coding: utf-8 -*-
"""Main-brain state services for lanes, backlog, cycles, assignments, and reports."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha1
from typing import Any, Mapping, Sequence

from .models import (
    AgentReportRecord,
    AssignmentRecord,
    BacklogItemRecord,
    GoalRecord,
    OperatingCycleRecord,
    OperatingLaneRecord,
    ScheduleRecord,
    TaskRecord,
    TaskRuntimeRecord,
)
from .repositories import (
    BaseAgentReportRepository,
    BaseAssignmentRepository,
    BaseBacklogItemRepository,
    BaseOperatingCycleRepository,
    BaseOperatingLaneRepository,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mapping(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _role_payload(role: object) -> dict[str, Any]:
    if hasattr(role, "model_dump"):
        return dict(role.model_dump(mode="json"))  # type: ignore[call-arg]
    return _mapping(role)


def _stable_id(prefix: str, *parts: object) -> str:
    normalized = "|".join(
        str(part).strip()
        for part in parts
        if str(part).strip()
    )
    digest = sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _lane_key_from_payload(payload: Mapping[str, Any]) -> str | None:
    for key in ("goal_kind", "role_id", "agent_id", "role_name", "name"):
        text = _string(payload.get(key))
        if text is not None:
            return text.lower().replace(" ", "-").replace("_", "-")
    return None


def _due_at_for_cycle(*, cycle_kind: str, now: datetime) -> datetime:
    if cycle_kind == "weekly":
        return now + timedelta(days=7)
    if cycle_kind == "event":
        return now + timedelta(hours=12)
    return now + timedelta(days=1)


_TERMINAL_TASK_RESULTS = {"completed", "failed", "cancelled"}


def _resolve_terminal_task_result(
    *,
    task: TaskRecord,
    runtime: TaskRuntimeRecord | None,
) -> str | None:
    task_status = _string(task.status)
    if task_status in _TERMINAL_TASK_RESULTS:
        return task_status
    if runtime is None:
        return None
    runtime_status = _string(runtime.runtime_status)
    runtime_phase = _string(runtime.current_phase)
    if runtime_status == "terminated" and runtime_phase in _TERMINAL_TASK_RESULTS:
        return runtime_phase
    if runtime_phase in _TERMINAL_TASK_RESULTS:
        return runtime_phase
    return None


class OperatingLaneService:
    def __init__(self, *, repository: BaseOperatingLaneRepository) -> None:
        self._repository = repository

    def get_lane(self, lane_id: str) -> OperatingLaneRecord | None:
        return self._repository.get_lane(lane_id)

    def list_lanes(
        self,
        *,
        industry_instance_id: str,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[OperatingLaneRecord]:
        return self._repository.list_lanes(
            industry_instance_id=industry_instance_id,
            status=status,
            limit=limit,
        )

    def seed_from_roles(
        self,
        *,
        industry_instance_id: str,
        roles: Sequence[object],
        lane_weights: Mapping[str, object] | None = None,
    ) -> list[OperatingLaneRecord]:
        existing = {
            lane.lane_key: lane
            for lane in self._repository.list_lanes(
                industry_instance_id=industry_instance_id,
                limit=None,
            )
        }
        active_lane_keys: set[str] = set()
        seeded: list[OperatingLaneRecord] = []
        total = max(1, len(roles))
        now = _utc_now()
        for index, role in enumerate(roles):
            payload = _role_payload(role)
            lane_key = _lane_key_from_payload(payload)
            if lane_key is None:
                continue
            active_lane_keys.add(lane_key)
            current = existing.get(lane_key)
            weight = None
            if lane_weights is not None:
                raw_weight = lane_weights.get(lane_key)
                if raw_weight is None and current is not None:
                    raw_weight = lane_weights.get(current.id)
                try:
                    weight = float(raw_weight) if raw_weight is not None else None
                except (TypeError, ValueError):
                    weight = None
            priority = (
                max(1, int(weight * 100))
                if isinstance(weight, float)
                else max(1, total - index)
            )
            seed = OperatingLaneRecord(
                id=(
                    current.id
                    if current is not None
                    else _stable_id("lane", industry_instance_id, lane_key)
                ),
                industry_instance_id=industry_instance_id,
                lane_key=lane_key,
                title=(
                    _string(payload.get("role_name"))
                    or _string(payload.get("name"))
                    or lane_key
                ),
                summary=(
                    _string(payload.get("mission"))
                    or _string(payload.get("role_summary"))
                    or ""
                ),
                status="active",
                owner_agent_id=_string(payload.get("agent_id")),
                owner_role_id=_string(payload.get("role_id")),
                priority=priority,
                health_status=current.health_status if current is not None else "healthy",
                source_ref=f"industry-role:{_string(payload.get('role_id')) or lane_key}",
                metadata={
                    "goal_kind": _string(payload.get("goal_kind")),
                    "role_name": _string(payload.get("role_name")) or _string(payload.get("name")),
                    "reports_to": _string(payload.get("reports_to")),
                    "evidence_expectations": list(payload.get("evidence_expectations") or []),
                },
                created_at=current.created_at if current is not None else now,
                updated_at=now,
            )
            seeded.append(self._repository.upsert_lane(seed))

        for lane in existing.values():
            if lane.lane_key in active_lane_keys or lane.status == "archived":
                continue
            self._repository.upsert_lane(
                lane.model_copy(update={"status": "archived", "updated_at": now}),
            )
        return seeded

    def resolve_lane(
        self,
        *,
        industry_instance_id: str,
        lane_key: str | None = None,
        role_id: str | None = None,
        goal_kind: str | None = None,
        owner_agent_id: str | None = None,
    ) -> OperatingLaneRecord | None:
        lanes = self._repository.list_lanes(
            industry_instance_id=industry_instance_id,
            limit=None,
        )
        aliases = {
            alias.lower().replace("_", "-").replace(" ", "-")
            for alias in (lane_key, role_id, goal_kind)
            if isinstance(alias, str) and alias.strip()
        }
        for lane in lanes:
            if lane.status == "archived":
                continue
            if lane.lane_key in aliases:
                return lane
            if owner_agent_id and lane.owner_agent_id == owner_agent_id:
                return lane
        return None


class BacklogService:
    def __init__(self, *, repository: BaseBacklogItemRepository) -> None:
        self._repository = repository

    def get_item(self, item_id: str) -> BacklogItemRecord | None:
        return self._repository.get_item(item_id)

    def list_items(
        self,
        *,
        industry_instance_id: str,
        lane_id: str | None = None,
        cycle_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[BacklogItemRecord]:
        return self._repository.list_items(
            industry_instance_id=industry_instance_id,
            lane_id=lane_id,
            cycle_id=cycle_id,
            status=status,
            limit=limit,
        )

    def list_open_items(
        self,
        *,
        industry_instance_id: str,
        limit: int | None = None,
    ) -> list[BacklogItemRecord]:
        items = self._repository.list_items(
            industry_instance_id=industry_instance_id,
            limit=limit,
        )
        return [
            item
            for item in items
            if item.status in {"open", "selected"}
        ]

    def seed_bootstrap_items(
        self,
        *,
        industry_instance_id: str,
        goals: Sequence[GoalRecord],
        schedules: Sequence[ScheduleRecord],
    ) -> list[BacklogItemRecord]:
        seeded: list[BacklogItemRecord] = []
        now = _utc_now()
        for goal in goals:
            stable_id = _stable_id("backlog-goal", industry_instance_id, goal.id)
            existing = self._repository.get_item(stable_id)
            item = BacklogItemRecord(
                id=stable_id,
                industry_instance_id=industry_instance_id,
                lane_id=goal.lane_id,
                cycle_id=goal.cycle_id,
                goal_id=goal.id,
                title=goal.title,
                summary=goal.summary,
                status="materialized",
                priority=goal.priority,
                source_kind="bootstrap-goal",
                source_ref=f"goal:{goal.id}",
                metadata={"goal_class": goal.goal_class},
                created_at=existing.created_at if existing is not None else now,
                updated_at=now,
            )
            seeded.append(self._repository.upsert_item(item))
        for schedule in schedules:
            stable_id = _stable_id("backlog-schedule", industry_instance_id, schedule.id)
            existing = self._repository.get_item(stable_id)
            item = BacklogItemRecord(
                id=stable_id,
                industry_instance_id=industry_instance_id,
                lane_id=schedule.lane_id,
                title=schedule.title,
                summary=schedule.spec_payload.get("meta", {}).get("summary") or schedule.source_ref or "",
                status="open",
                priority=2,
                source_kind="schedule",
                source_ref=f"schedule:{schedule.id}",
                metadata={
                    "schedule_id": schedule.id,
                    "schedule_kind": schedule.schedule_kind,
                    "trigger_target": schedule.trigger_target,
                    "spec_payload": dict(schedule.spec_payload),
                },
                created_at=existing.created_at if existing is not None else now,
                updated_at=now,
            )
            seeded.append(self._repository.upsert_item(item))
        return seeded

    def seed_bootstrap_items_from_goal_specs(
        self,
        *,
        industry_instance_id: str,
        goal_specs: Sequence[Mapping[str, object]],
        schedule_specs: Sequence[Mapping[str, object]],
    ) -> list[BacklogItemRecord]:
        seeded: list[BacklogItemRecord] = []
        now = _utc_now()
        for spec in goal_specs:
            goal_id = _string(spec.get("goal_id"))
            title = _string(spec.get("title"))
            if goal_id is None or title is None:
                continue
            stable_id = _stable_id("backlog-goal", industry_instance_id, goal_id)
            existing = self._repository.get_item(stable_id)
            metadata = dict(existing.metadata or {}) if existing is not None else {}
            metadata.update(
                {
                    "goal_kind": _string(spec.get("goal_kind")) or _string(spec.get("kind")),
                    "goal_class": _string(spec.get("goal_class")) or "bootstrap-goal",
                    "industry_role_id": _string(spec.get("industry_role_id")),
                    "owner_agent_id": _string(spec.get("owner_agent_id")),
                },
            )
            item = BacklogItemRecord(
                id=stable_id,
                industry_instance_id=industry_instance_id,
                lane_id=_string(spec.get("lane_id")),
                cycle_id=_string(spec.get("cycle_id")),
                goal_id=goal_id,
                title=title,
                summary=_string(spec.get("summary")) or "",
                status="materialized",
                priority=max(0, int(spec.get("priority") or 0)),
                source_kind="bootstrap-goal",
                source_ref=f"goal:{goal_id}",
                metadata=metadata,
                created_at=existing.created_at if existing is not None else now,
                updated_at=now,
            )
            seeded.append(self._repository.upsert_item(item))
        for schedule_spec in schedule_specs:
            schedule_id = _string(schedule_spec.get("schedule_id"))
            title = _string(schedule_spec.get("title"))
            spec_payload = _mapping(schedule_spec.get("spec_payload"))
            if schedule_id is None or title is None or not spec_payload:
                continue
            stable_id = _stable_id("backlog-schedule", industry_instance_id, schedule_id)
            existing = self._repository.get_item(stable_id)
            trigger_target = (
                _string(schedule_spec.get("trigger_target"))
                or _string(spec_payload.get("meta", {}).get("goal_kind"))
                or "main-brain"
            )
            schedule_kind = _string(schedule_spec.get("schedule_kind")) or "cadence"
            item = BacklogItemRecord(
                id=stable_id,
                industry_instance_id=industry_instance_id,
                lane_id=_string(schedule_spec.get("lane_id")),
                title=title,
                summary=(
                    _string(spec_payload.get("meta", {}).get("summary"))
                    or _string(schedule_spec.get("summary"))
                    or f"schedule:{schedule_id}"
                ),
                status="open",
                priority=2,
                source_kind="schedule",
                source_ref=f"schedule:{schedule_id}",
                metadata={
                    "schedule_id": schedule_id,
                    "schedule_kind": schedule_kind,
                    "trigger_target": trigger_target,
                    "spec_payload": spec_payload,
                },
                created_at=existing.created_at if existing is not None else now,
                updated_at=now,
            )
            seeded.append(self._repository.upsert_item(item))
        return seeded

    def record_generated_item(
        self,
        *,
        industry_instance_id: str,
        lane_id: str | None,
        title: str,
        summary: str,
        priority: int,
        source_kind: str,
        source_ref: str,
        metadata: Mapping[str, object] | None = None,
    ) -> BacklogItemRecord:
        stable_id = _stable_id(f"backlog-{source_kind}", industry_instance_id, source_ref)
        existing = self._repository.get_item(stable_id)
        existing_metadata = dict(existing.metadata or {}) if existing is not None else {}
        next_metadata = dict(existing_metadata)
        next_metadata.update(dict(metadata or {}))
        item = BacklogItemRecord(
            id=stable_id,
            industry_instance_id=industry_instance_id,
            lane_id=lane_id or (existing.lane_id if existing is not None else None),
            cycle_id=existing.cycle_id if existing is not None else None,
            assignment_id=existing.assignment_id if existing is not None else None,
            goal_id=existing.goal_id if existing is not None else None,
            title=title or (existing.title if existing is not None else ""),
            summary=summary or (existing.summary if existing is not None else ""),
            status=existing.status if existing is not None else "open",
            priority=max(0, priority),
            source_kind=source_kind,
            source_ref=source_ref,
            evidence_ids=list(existing.evidence_ids or []) if existing is not None else [],
            metadata=next_metadata,
            created_at=existing.created_at if existing is not None else _utc_now(),
            updated_at=_utc_now(),
        )
        return self._repository.upsert_item(item)

    def record_chat_writeback(
        self,
        *,
        industry_instance_id: str,
        lane_id: str | None,
        title: str,
        summary: str,
        priority: int,
        source_ref: str,
        metadata: Mapping[str, object] | None = None,
    ) -> BacklogItemRecord:
        return self.record_generated_item(
            industry_instance_id=industry_instance_id,
            lane_id=lane_id,
            title=title,
            summary=summary,
            priority=priority,
            source_kind="operator",
            source_ref=source_ref,
            metadata=metadata,
        )

    def ensure_schedule_items(
        self,
        *,
        industry_instance_id: str,
        schedules: Sequence[ScheduleRecord],
    ) -> list[BacklogItemRecord]:
        ensured: list[BacklogItemRecord] = []
        for schedule in schedules:
            if not schedule.enabled:
                continue
            stable_id = _stable_id("backlog-schedule", industry_instance_id, schedule.id)
            existing = self._repository.get_item(stable_id)
            if existing is not None and existing.status in {"open", "selected", "materialized"}:
                ensured.append(existing)
                continue
            item = BacklogItemRecord(
                id=stable_id,
                industry_instance_id=industry_instance_id,
                lane_id=schedule.lane_id,
                title=schedule.title,
                summary=schedule.spec_payload.get("meta", {}).get("summary") or schedule.source_ref or "",
                status="open",
                priority=2,
                source_kind="schedule",
                source_ref=f"schedule:{schedule.id}",
                metadata={
                    "schedule_id": schedule.id,
                    "schedule_kind": schedule.schedule_kind,
                    "trigger_target": schedule.trigger_target,
                    "spec_payload": dict(schedule.spec_payload),
                },
            )
            ensured.append(self._repository.upsert_item(item))
        return ensured

    def mark_item_selected(
        self,
        item: BacklogItemRecord,
        *,
        cycle_id: str,
    ) -> BacklogItemRecord:
        return self._repository.upsert_item(
            item.model_copy(
                update={
                    "cycle_id": cycle_id,
                    "status": "selected",
                    "updated_at": _utc_now(),
                },
            ),
        )

    def mark_item_materialized(
        self,
        item: BacklogItemRecord,
        *,
        cycle_id: str,
        goal_id: str | None,
        assignment_id: str | None,
    ) -> BacklogItemRecord:
        current = self._repository.get_item(item.id) or item
        return self._repository.upsert_item(
            current.model_copy(
                update={
                    "cycle_id": cycle_id,
                    "goal_id": goal_id or current.goal_id,
                    "assignment_id": assignment_id or current.assignment_id,
                    "status": "materialized",
                    "updated_at": _utc_now(),
                },
            ),
        )

    def mark_item_completed(self, item: BacklogItemRecord) -> BacklogItemRecord:
        return self._repository.upsert_item(
            item.model_copy(update={"status": "completed", "updated_at": _utc_now()}),
        )

    def attach_evidence_ids(
        self,
        item: BacklogItemRecord | str,
        *,
        evidence_ids: Sequence[str],
    ) -> BacklogItemRecord | None:
        current = (
            self._repository.get_item(item)
            if isinstance(item, str)
            else item
        )
        if current is None:
            return None
        merged_ids = list(
            dict.fromkeys(
                [
                    *list(current.evidence_ids or []),
                    *[
                        evidence_id
                        for evidence_id in evidence_ids
                        if _string(evidence_id) is not None
                    ],
                ],
            ),
        )
        if merged_ids == list(current.evidence_ids or []):
            return current
        return self._repository.upsert_item(
            current.model_copy(
                update={
                    "evidence_ids": merged_ids,
                    "updated_at": _utc_now(),
                },
            ),
        )


class OperatingCycleService:
    def __init__(self, *, repository: BaseOperatingCycleRepository) -> None:
        self._repository = repository

    def get_cycle(self, cycle_id: str) -> OperatingCycleRecord | None:
        return self._repository.get_cycle(cycle_id)

    def list_cycles(
        self,
        *,
        industry_instance_id: str,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[OperatingCycleRecord]:
        return self._repository.list_cycles(
            industry_instance_id=industry_instance_id,
            status=status,
            limit=limit,
        )

    def get_current_cycle(self, *, industry_instance_id: str) -> OperatingCycleRecord | None:
        cycles = self._repository.list_cycles(
            industry_instance_id=industry_instance_id,
            limit=10,
        )
        for cycle in cycles:
            if cycle.status not in {"completed", "cancelled"}:
                return cycle
        return cycles[0] if cycles else None

    def should_start_new_cycle(
        self,
        *,
        current_cycle: OperatingCycleRecord | None,
        next_cycle_due_at: datetime | None,
        open_backlog_count: int,
        pending_report_count: int,
        force: bool = False,
    ) -> tuple[bool, str]:
        if force:
            return (open_backlog_count > 0 or pending_report_count > 0, "forced")
        if current_cycle is not None and current_cycle.status not in {"completed", "cancelled"}:
            return (False, "cycle-inflight")
        if open_backlog_count > 0:
            return (True, "open-backlog")
        if next_cycle_due_at is not None and next_cycle_due_at <= _utc_now() and pending_report_count > 0:
            return (True, "due-with-pending-reports")
        return (False, "no-open-backlog")

    def start_cycle(
        self,
        *,
        industry_instance_id: str,
        label: str,
        cycle_kind: str,
        status: str,
        focus_lane_ids: Sequence[str],
        backlog_item_ids: Sequence[str],
        source_ref: str,
        summary: str | None = None,
        assignment_ids: Sequence[str] | None = None,
        metadata: Mapping[str, object] | None = None,
        now: datetime | None = None,
    ) -> OperatingCycleRecord:
        started_at = now or _utc_now()
        cycle = OperatingCycleRecord(
            id=_stable_id("cycle", industry_instance_id, cycle_kind, started_at.isoformat()),
            industry_instance_id=industry_instance_id,
            cycle_kind=cycle_kind,  # type: ignore[arg-type]
            title=f"{label} {cycle_kind} cycle",
            summary=summary or "Main-brain operating cycle.",
            status=status,  # type: ignore[arg-type]
            source_ref=source_ref,
            started_at=started_at,
            due_at=_due_at_for_cycle(cycle_kind=cycle_kind, now=started_at),
            focus_lane_ids=list(dict.fromkeys(focus_lane_ids)),
            backlog_item_ids=list(dict.fromkeys(backlog_item_ids)),
            assignment_ids=list(dict.fromkeys(assignment_ids or [])),
            report_ids=[],
            metadata=dict(metadata or {}),
            created_at=started_at,
            updated_at=started_at,
        )
        return self._repository.upsert_cycle(cycle)

    def reconcile_cycle(
        self,
        cycle: OperatingCycleRecord,
        *,
        assignment_statuses: Sequence[str],
        report_ids: Sequence[str],
    ) -> OperatingCycleRecord:
        next_status = cycle.status
        normalized_assignment_statuses = [status for status in assignment_statuses if status]
        if any(
            status in {"planned", "queued", "running", "waiting-report"}
            for status in normalized_assignment_statuses
        ):
            next_status = "active"
        elif any(status in {"failed", "cancelled"} for status in normalized_assignment_statuses):
            next_status = "review"
        elif normalized_assignment_statuses or report_ids:
            next_status = "completed"
        updated = cycle.model_copy(
            update={
                "status": next_status,
                "report_ids": list(dict.fromkeys(report_ids)),
                "completed_at": _utc_now() if next_status == "completed" else cycle.completed_at,
                "updated_at": _utc_now(),
            },
        )
        return self._repository.upsert_cycle(updated)

    def update_cycle_links(
        self,
        cycle: OperatingCycleRecord,
        *,
        assignment_ids: Sequence[str] | None = None,
        report_ids: Sequence[str] | None = None,
        backlog_item_ids: Sequence[str] | None = None,
        focus_lane_ids: Sequence[str] | None = None,
    ) -> OperatingCycleRecord:
        update: dict[str, Any] = {"updated_at": _utc_now()}
        if assignment_ids is not None:
            update["assignment_ids"] = list(dict.fromkeys(assignment_ids))
        if report_ids is not None:
            update["report_ids"] = list(dict.fromkeys(report_ids))
        if backlog_item_ids is not None:
            update["backlog_item_ids"] = list(dict.fromkeys(backlog_item_ids))
        if focus_lane_ids is not None:
            update["focus_lane_ids"] = list(dict.fromkeys(focus_lane_ids))
        return self._repository.upsert_cycle(cycle.model_copy(update=update))


class AssignmentService:
    def __init__(self, *, repository: BaseAssignmentRepository) -> None:
        self._repository = repository

    def get_assignment(self, assignment_id: str) -> AssignmentRecord | None:
        return self._repository.get_assignment(assignment_id)

    def list_assignments(
        self,
        *,
        industry_instance_id: str,
        cycle_id: str | None = None,
        goal_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[AssignmentRecord]:
        return self._repository.list_assignments(
            industry_instance_id=industry_instance_id,
            cycle_id=cycle_id,
            goal_id=goal_id,
            status=status,
            limit=limit,
        )

    def ensure_assignments(
        self,
        *,
        industry_instance_id: str,
        cycle_id: str,
        specs: Sequence[Mapping[str, object]],
    ) -> list[AssignmentRecord]:
        ensured: list[AssignmentRecord] = []
        now = _utc_now()
        for spec in specs:
            goal_id = _string(spec.get("goal_id"))
            backlog_item_id = _string(spec.get("backlog_item_id"))
            stable_id = _stable_id(
                "assignment",
                cycle_id,
                goal_id or backlog_item_id or _string(spec.get("title")) or now.isoformat(),
            )
            existing = self._repository.get_assignment(stable_id)
            goal_status = _string(spec.get("goal_status")) or "draft"
            assignment_status = _string(spec.get("status")) or "planned"
            if _string(spec.get("status")) is None:
                if goal_status == "active":
                    assignment_status = "queued"
                elif goal_status == "completed":
                    assignment_status = "waiting-report"
                elif goal_status == "blocked":
                    assignment_status = "failed"
            assignment = AssignmentRecord(
                id=stable_id,
                industry_instance_id=industry_instance_id,
                cycle_id=cycle_id,
                lane_id=_string(spec.get("lane_id")),
                backlog_item_id=backlog_item_id,
                goal_id=goal_id,
                task_id=_string(spec.get("task_id")),
                owner_agent_id=_string(spec.get("owner_agent_id")),
                owner_role_id=_string(spec.get("owner_role_id")),
                title=_string(spec.get("title")) or "Assignment",
                summary=_string(spec.get("summary")) or "",
                status=assignment_status,  # type: ignore[arg-type]
                report_back_mode=_string(spec.get("report_back_mode")) or "summary",
                evidence_ids=list(existing.evidence_ids) if existing is not None else [],
                last_report_id=existing.last_report_id if existing is not None else None,
                metadata=dict(spec.get("metadata") or {}),
                created_at=existing.created_at if existing is not None else now,
                updated_at=now,
            )
            ensured.append(self._repository.upsert_assignment(assignment))
        return ensured

    def attach_evidence_ids(
        self,
        assignment: AssignmentRecord | str,
        *,
        evidence_ids: Sequence[str],
    ) -> AssignmentRecord | None:
        current = (
            self._repository.get_assignment(assignment)
            if isinstance(assignment, str)
            else assignment
        )
        if current is None:
            return None
        merged_ids = list(
            dict.fromkeys(
                [
                    *list(current.evidence_ids or []),
                    *[
                        evidence_id
                        for evidence_id in evidence_ids
                        if _string(evidence_id) is not None
                    ],
                ],
            ),
        )
        if merged_ids == list(current.evidence_ids or []):
            return current
        return self._repository.upsert_assignment(
            current.model_copy(
                update={
                    "evidence_ids": merged_ids,
                    "updated_at": _utc_now(),
                },
            ),
        )

    def reconcile_assignments(
        self,
        *,
        industry_instance_id: str,
        cycle_id: str | None,
        goals_by_id: Mapping[str, GoalRecord],
        tasks_by_assignment_id: Mapping[str, Sequence[TaskRecord]],
        tasks_by_goal_id: Mapping[str, Sequence[TaskRecord]] | None = None,
        latest_reports_by_assignment_id: Mapping[str, AgentReportRecord],
    ) -> list[AssignmentRecord]:
        assignments = self._repository.list_assignments(
            industry_instance_id=industry_instance_id,
            cycle_id=cycle_id,
            limit=None,
        )
        reconciled: list[AssignmentRecord] = []
        tasks_by_goal_id = tasks_by_goal_id or {}
        for assignment in assignments:
            tasks = list(tasks_by_assignment_id.get(assignment.id, []))
            if not tasks and assignment.goal_id:
                tasks = list(tasks_by_goal_id.get(assignment.goal_id or "", []))
            latest_report = latest_reports_by_assignment_id.get(assignment.id)
            next_status = assignment.status
            task_id = assignment.task_id
            has_live_task = any(
                task.status in {"created", "queued", "running", "needs-confirm", "waiting", "blocked"}
                for task in tasks
            )
            if tasks:
                latest_task = max(
                    tasks,
                    key=lambda item: item.updated_at or item.created_at,
                )
                task_id = latest_task.id
                if latest_task.status in {"created", "queued"}:
                    next_status = "queued"
                elif latest_task.status == "running":
                    next_status = "running"
                elif latest_task.status == "completed":
                    next_status = "waiting-report"
                elif latest_task.status in {"failed", "cancelled"}:
                    next_status = "failed"
            if (
                latest_report is not None
                and latest_report.result in {"completed", "success"}
                and not has_live_task
            ):
                next_status = "completed"
            elif (
                latest_report is not None
                and latest_report.result in {"failed", "cancelled", "blocked"}
                and not has_live_task
            ):
                next_status = "failed"
            reconciled.append(
                self._repository.upsert_assignment(
                    assignment.model_copy(
                        update={
                            "task_id": task_id,
                            "status": next_status,
                            "evidence_ids": (
                                list(latest_report.evidence_ids or [])
                                if latest_report is not None
                                else assignment.evidence_ids
                            ),
                            "last_report_id": latest_report.id if latest_report is not None else assignment.last_report_id,
                            "updated_at": _utc_now(),
                        },
                    ),
                ),
            )
        return reconciled


class AgentReportService:
    def __init__(
        self,
        *,
        repository: BaseAgentReportRepository,
        memory_retain_service: object | None = None,
    ) -> None:
        self._repository = repository
        self._memory_retain_service = memory_retain_service

    def set_memory_retain_service(self, memory_retain_service: object | None) -> None:
        self._memory_retain_service = memory_retain_service

    def get_report(self, report_id: str) -> AgentReportRecord | None:
        return self._repository.get_report(report_id)

    def list_reports(
        self,
        *,
        industry_instance_id: str,
        cycle_id: str | None = None,
        assignment_id: str | None = None,
        processed: bool | None = None,
        limit: int | None = None,
    ) -> list[AgentReportRecord]:
        return self._repository.list_reports(
            industry_instance_id=industry_instance_id,
            cycle_id=cycle_id,
            assignment_id=assignment_id,
            processed=processed,
            limit=limit,
        )

    def latest_reports_by_assignment(
        self,
        *,
        industry_instance_id: str,
        cycle_id: str | None = None,
    ) -> dict[str, AgentReportRecord]:
        reports = self._repository.list_reports(
            industry_instance_id=industry_instance_id,
            cycle_id=cycle_id,
            limit=None,
        )
        latest: dict[str, AgentReportRecord] = {}
        for report in reports:
            if not report.assignment_id:
                continue
            current = latest.get(report.assignment_id)
            if current is None or (report.updated_at or report.created_at) >= (
                current.updated_at or current.created_at
            ):
                latest[report.assignment_id] = report
        return latest

    def record_task_terminal_report(
        self,
        *,
        task: TaskRecord,
        runtime: TaskRuntimeRecord | None,
        assignment: AssignmentRecord | None,
        evidence_ids: Sequence[str],
        decision_ids: Sequence[str],
        owner_role_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> AgentReportRecord | None:
        result = _resolve_terminal_task_result(task=task, runtime=runtime)
        if result is None:
            return None
        industry_instance_id = _string(task.industry_instance_id) or (
            assignment.industry_instance_id if assignment is not None else None
        )
        if industry_instance_id is None:
            return None
        stable_id = _stable_id("report", task.id, result)
        existing = self._repository.get_report(stable_id)
        result_summary = _string(runtime.last_result_summary if runtime is not None else None)
        error_summary = _string(runtime.last_error_summary if runtime is not None else None)
        summary = (
            result_summary
            or error_summary
            or task.summary
            or task.title
        )
        findings = [result_summary] if result_summary is not None else []
        uncertainties = [error_summary] if error_summary is not None else []
        needs_followup = (
            result in {"failed", "cancelled"}
            or error_summary is not None
            or bool(decision_ids)
        )
        followup_reason = error_summary
        report = AgentReportRecord(
            id=stable_id,
            industry_instance_id=industry_instance_id,
            cycle_id=_string(task.cycle_id) or (assignment.cycle_id if assignment is not None else None),
            assignment_id=_string(task.assignment_id) or (assignment.id if assignment is not None else None),
            goal_id=_string(task.goal_id) or (assignment.goal_id if assignment is not None else None),
            task_id=task.id,
            work_context_id=_string(task.work_context_id),
            lane_id=_string(task.lane_id) or (assignment.lane_id if assignment is not None else None),
            owner_agent_id=_string(task.owner_agent_id) or (assignment.owner_agent_id if assignment is not None else None),
            owner_role_id=owner_role_id or (assignment.owner_role_id if assignment is not None else None),
            report_kind="task-terminal",
            headline=f"{task.title} {result}",
            summary=summary or "",
            findings=findings,
            uncertainties=uncertainties,
            recommendation=None,
            needs_followup=needs_followup,
            followup_reason=followup_reason,
            result=result,
            risk_level=_string(runtime.risk_level if runtime is not None else None) or task.current_risk_level,
            evidence_ids=list(dict.fromkeys(evidence_ids)),
            decision_ids=list(dict.fromkeys(decision_ids)),
            processed=bool(existing.processed) if existing is not None else False,
            processed_at=existing.processed_at if existing is not None else None,
            metadata={
                "task_type": task.task_type,
                "report_back_mode": task.report_back_mode,
                "lane_id": task.lane_id,
                **dict(metadata or {}),
            },
            created_at=existing.created_at if existing is not None else _utc_now(),
            updated_at=_utc_now(),
            status=(
                existing.status
                if existing is not None and existing.processed
                else "recorded"
            ),
        )
        stored = self._repository.upsert_report(report)
        retain = getattr(self._memory_retain_service, "retain_agent_report", None)
        if callable(retain):
            try:
                retain(stored)
            except Exception:
                pass
        return stored

    def mark_processed(self, report: AgentReportRecord) -> AgentReportRecord:
        stored = self._repository.upsert_report(
            report.model_copy(
                update={
                    "processed": True,
                    "status": "processed",
                    "processed_at": _utc_now(),
                    "updated_at": _utc_now(),
                },
            ),
        )
        retain = getattr(self._memory_retain_service, "retain_agent_report", None)
        if callable(retain):
            try:
                retain(stored)
            except Exception:
                pass
        return stored
