# -*- coding: utf-8 -*-
"""Evidence-driven reporting and performance service for V2."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from ..evidence import EvidenceLedger, EvidenceRecord
from .models import (
    DecisionRequestRecord,
    GoalRecord,
    MetricRecord,
    ReportEvidenceDigest,
    ReportRecord,
    ReportScopeType,
    ReportTaskDigest,
    ReportWindow,
    TaskRecord,
    TaskRuntimeRecord,
)
from .repositories import (
    SqliteDecisionRequestRepository,
    SqliteGoalRepository,
    SqliteIndustryInstanceRepository,
    SqlitePredictionCaseRepository,
    SqlitePredictionRecommendationRepository,
    SqlitePredictionReviewRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)

_WINDOW_DAYS: dict[ReportWindow, int] = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
}
_TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _created_within(
    value: datetime | None,
    *,
    since: datetime,
    until: datetime,
) -> bool:
    normalized = _normalize_datetime(value)
    if normalized is None:
        return False
    return since <= normalized <= until


def _ratio_percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def _display_metric(value: float, unit: str) -> str:
    if unit == "percent":
        return f"{value:.1f}%"
    if unit == "count":
        return str(int(round(value)))
    return f"{value:.1f}"


def _report_id(
    *,
    window: ReportWindow,
    scope_type: ReportScopeType,
    scope_id: str | None,
    until: datetime,
) -> str:
    suffix = scope_id or "all"
    return f"report:{window}:{scope_type}:{suffix}:{until.date().isoformat()}"


def _unique_strings(values: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        if not value:
            continue
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        items.append(normalized)
    return items


def _normalize_text(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _timestamp_key(value: datetime | None) -> float:
    normalized = _normalize_datetime(value)
    return normalized.timestamp() if normalized is not None else 0.0


def _task_activity_at(
    task: TaskRecord,
    runtime: TaskRuntimeRecord | None,
) -> datetime | None:
    candidates = [
        value
        for value in (
            _normalize_datetime(task.updated_at),
            _normalize_datetime(task.created_at),
            _normalize_datetime(runtime.updated_at) if runtime is not None else None,
        )
        if value is not None
    ]
    return max(candidates) if candidates else None


def _window_label(window: ReportWindow) -> str:
    mapping: dict[ReportWindow, str] = {
        "daily": "日报",
        "weekly": "周报",
        "monthly": "月报",
    }
    return mapping.get(window, "报告")


@dataclass(slots=True)
class _ReportingScope:
    scope_type: ReportScopeType
    scope_id: str | None
    label: str
    goal_ids: set[str]
    agent_ids: set[str]


@dataclass(slots=True)
class _WindowDataset:
    window: ReportWindow
    scope_type: ReportScopeType
    scope_id: str | None
    scope_label: str
    since: datetime
    until: datetime
    goals: list[GoalRecord]
    tasks: list[TaskRecord]
    runtimes_by_task: dict[str, TaskRuntimeRecord]
    decisions: list[DecisionRequestRecord]
    evidence: list[EvidenceRecord]
    proposals: list[Any]
    patches: list[Any]
    growth: list[Any]
    agent_ids: list[str]
    active_task_count: int
    window_goal_ids: set[str]
    window_task_ids: set[str]


@dataclass(slots=True)
class _ScopeSnapshot:
    scope_type: ReportScopeType
    scope_id: str | None
    scope_label: str
    scope_agent_ids: set[str]
    tasks: list[TaskRecord]
    goals: list[GoalRecord]
    runtimes_by_task: dict[str, TaskRuntimeRecord]
    decisions: list[DecisionRequestRecord]
    proposals: list[Any]
    patches: list[Any]
    growth: list[Any]


@dataclass(slots=True)
class _PredictionSnapshot:
    case_count: int
    recommendation_count: int
    review_count: int
    auto_execution_count: int
    hit_rate: float
    adoption_rate: float
    average_benefit: float


class StateReportingService:
    """Build formal reports and performance metrics from unified state."""

    def __init__(
        self,
        *,
        task_repository: SqliteTaskRepository,
        task_runtime_repository: SqliteTaskRuntimeRepository,
        goal_repository: SqliteGoalRepository | None,
        decision_request_repository: SqliteDecisionRequestRepository,
        evidence_ledger: EvidenceLedger,
        learning_service: object | None = None,
        industry_instance_repository: SqliteIndustryInstanceRepository | None = None,
        agent_profile_service: object | None = None,
        prediction_case_repository: SqlitePredictionCaseRepository | None = None,
        prediction_recommendation_repository: SqlitePredictionRecommendationRepository | None = None,
        prediction_review_repository: SqlitePredictionReviewRepository | None = None,
    ) -> None:
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._goal_repository = goal_repository
        self._decision_request_repository = decision_request_repository
        self._evidence_ledger = evidence_ledger
        self._learning_service = learning_service
        self._industry_instance_repository = industry_instance_repository
        self._agent_profile_service = agent_profile_service
        self._prediction_case_repository = prediction_case_repository
        self._prediction_recommendation_repository = prediction_recommendation_repository
        self._prediction_review_repository = prediction_review_repository

    def list_reports(
        self,
        *,
        window: ReportWindow | None = None,
        scope_type: ReportScopeType = "global",
        scope_id: str | None = None,
    ) -> list[ReportRecord]:
        windows: list[ReportWindow] = [window] if window is not None else [
            "daily",
            "weekly",
            "monthly",
        ]
        until = _utc_now()
        snapshot_since = until - timedelta(days=max(_WINDOW_DAYS[item] for item in windows))
        snapshot = self._build_scope_snapshot(
            scope_type=scope_type,
            scope_id=scope_id,
            since=snapshot_since,
            until=until,
        )
        return [
            self._build_report(
                window=item,
                scope_type=scope_type,
                scope_id=scope_id,
                until=until,
                snapshot=snapshot,
            )
            for item in windows
        ]

    def get_report(
        self,
        *,
        window: ReportWindow = "weekly",
        scope_type: ReportScopeType = "global",
        scope_id: str | None = None,
    ) -> ReportRecord:
        until = _utc_now()
        since = until - timedelta(days=_WINDOW_DAYS[window])
        snapshot = self._build_scope_snapshot(
            scope_type=scope_type,
            scope_id=scope_id,
            since=since,
            until=until,
        )
        return self._build_report(
            window=window,
            scope_type=scope_type,
            scope_id=scope_id,
            until=until,
            snapshot=snapshot,
        )

    def _build_report(
        self,
        *,
        window: ReportWindow,
        scope_type: ReportScopeType,
        scope_id: str | None,
        until: datetime | None = None,
        snapshot: _ScopeSnapshot | None = None,
    ) -> ReportRecord:
        dataset = self._collect_window_dataset(
            window=window,
            scope_type=scope_type,
            scope_id=scope_id,
            until=until,
            snapshot=snapshot,
        )
        focus_items = self._build_focus_items(dataset)
        completed_tasks = self._build_completed_tasks(dataset)
        primary_evidence = self._build_primary_evidence(dataset)
        key_results = self._build_key_results(
            dataset,
            completed_task_ids={item.task_id for item in completed_tasks},
        )
        blockers = self._build_blockers(dataset)
        next_steps = self._build_next_steps(dataset)
        prediction = self._prediction_snapshot(dataset)
        metrics = self._build_metrics(dataset, prediction=prediction)
        window_label = _window_label(window)
        summary = (
            f"{dataset.scope_label}{window_label}覆盖 "
            f"{len(dataset.window_task_ids)} 个窗口内任务、{len(dataset.evidence)} 条证据、"
            f"{len(dataset.decisions)} 条决策请求，以及 {prediction.case_count} 个预测案例。"
        )
        highlights = [
            f"证据 {len(dataset.evidence)}",
            f"任务 {len(dataset.window_task_ids)}",
            f"补丁 {len(dataset.patches)}",
            f"已应用补丁 {sum(1 for patch in dataset.patches if getattr(patch, 'status', None) == 'applied')}",
            f"决策 {len(dataset.decisions)}",
        ]
        if prediction.case_count > 0:
            highlights.append(f"预测案例 {prediction.case_count}")
        if prediction.recommendation_count > 0:
            highlights.append(f"建议 {prediction.recommendation_count}")
        if prediction.review_count > 0:
            highlights.append(f"预测复盘 {prediction.review_count}")
        return ReportRecord(
            id=_report_id(
                window=window,
                scope_type=scope_type,
                scope_id=scope_id,
                until=dataset.until,
            ),
            title=self._report_title(dataset),
            summary=summary,
            window=window,
            scope_type=scope_type,
            scope_id=scope_id,
            since=dataset.since,
            until=dataset.until,
            highlights=highlights,
            metrics=metrics,
            task_status_counts=dict(
                Counter(task.status for task in dataset.tasks if task.id in dataset.window_task_ids),
            ),
            runtime_status_counts=dict(
                Counter(
                    runtime.runtime_status
                    for task_id, runtime in dataset.runtimes_by_task.items()
                    if task_id in dataset.window_task_ids
                ),
            ),
            goal_status_counts=dict(
                Counter(
                    goal.status
                    for goal in dataset.goals
                    if goal.id in dataset.window_goal_ids
                ),
            ),
            evidence_count=len(dataset.evidence),
            proposal_count=len(dataset.proposals),
            patch_count=len(dataset.patches),
            applied_patch_count=sum(
                1
                for patch in dataset.patches
                if getattr(patch, "status", None) == "applied"
            ),
            rollback_patch_count=sum(
                1
                for patch in dataset.patches
                if getattr(patch, "status", None) == "rolled_back"
            ),
            growth_count=len(dataset.growth),
            decision_count=len(dataset.decisions),
            prediction_count=prediction.case_count,
            recommendation_count=prediction.recommendation_count,
            review_count=prediction.review_count,
            auto_execution_count=prediction.auto_execution_count,
            task_count=len(dataset.window_task_ids),
            agent_count=len(dataset.agent_ids),
            focus_items=focus_items,
            completed_tasks=completed_tasks,
            key_results=key_results,
            primary_evidence=primary_evidence,
            blockers=blockers,
            next_steps=next_steps,
            evidence_ids=[record.id for record in dataset.evidence],
            task_ids=sorted(dataset.window_task_ids),
            goal_ids=sorted(dataset.window_goal_ids),
            agent_ids=list(dataset.agent_ids),
            routes={
                "detail": self._report_route(
                    window=window,
                    scope_type=scope_type,
                    scope_id=scope_id,
                ),
                "performance": self._performance_route(
                    window=window,
                    scope_type=scope_type,
                    scope_id=scope_id,
                ),
            },
        )

    def _build_focus_items(self, dataset: _WindowDataset) -> list[str]:
        window_goals = sorted(
            (goal for goal in dataset.goals if goal.id in dataset.window_goal_ids),
            key=lambda goal: _timestamp_key(goal.updated_at or goal.created_at),
            reverse=True,
        )
        focus_items = _unique_strings(goal.title for goal in window_goals)
        if focus_items:
            return focus_items[:3]
        active_tasks = sorted(
            (
                task
                for task in dataset.tasks
                if task.status not in _TERMINAL_TASK_STATUSES
            ),
            key=lambda task: _timestamp_key(
                _task_activity_at(task, dataset.runtimes_by_task.get(task.id)),
            ),
            reverse=True,
        )
        return _unique_strings(task.title for task in active_tasks)[:3]

    def _build_task_digest(
        self,
        task: TaskRecord,
        dataset: _WindowDataset,
    ) -> ReportTaskDigest:
        runtime = dataset.runtimes_by_task.get(task.id)
        return ReportTaskDigest(
            task_id=task.id,
            title=task.title,
            summary=task.summary or "",
            status=task.status,
            owner_agent_id=task.owner_agent_id,
            runtime_status=runtime.runtime_status if runtime is not None else None,
            current_phase=runtime.current_phase if runtime is not None else None,
            last_result_summary=runtime.last_result_summary if runtime is not None else None,
            last_error_summary=runtime.last_error_summary if runtime is not None else None,
            updated_at=_task_activity_at(task, runtime),
            route=f"/api/runtime-center/tasks/{task.id}",
        )

    def _build_completed_tasks(self, dataset: _WindowDataset) -> list[ReportTaskDigest]:
        completed_tasks = sorted(
            (
                task
                for task in dataset.tasks
                if task.id in dataset.window_task_ids and task.status == "completed"
            ),
            key=lambda task: _timestamp_key(
                _task_activity_at(task, dataset.runtimes_by_task.get(task.id)),
            ),
            reverse=True,
        )
        return [self._build_task_digest(task, dataset) for task in completed_tasks[:5]]

    def _build_primary_evidence(self, dataset: _WindowDataset) -> list[ReportEvidenceDigest]:
        recent_evidence = sorted(
            dataset.evidence,
            key=lambda record: _timestamp_key(record.created_at),
            reverse=True,
        )[:5]
        return [
            ReportEvidenceDigest(
                evidence_id=str(record.id or ""),
                task_id=record.task_id,
                action_summary=record.action_summary,
                result_summary=record.result_summary,
                risk_level=record.risk_level,
                capability_ref=record.capability_ref,
                created_at=record.created_at,
            )
            for record in recent_evidence
            if record.id
        ]

    def _build_key_results(
        self,
        dataset: _WindowDataset,
        *,
        completed_task_ids: set[str],
    ) -> list[str]:
        result_candidates: list[str | None] = []
        sorted_evidence = sorted(
            dataset.evidence,
            key=lambda record: _timestamp_key(record.created_at),
            reverse=True,
        )
        result_candidates.extend(
            record.result_summary
            for record in sorted_evidence
            if record.status != "failed"
            and (not completed_task_ids or record.task_id in completed_task_ids)
        )
        result_candidates.extend(
            _normalize_text(getattr(patch, "title", None))
            for patch in dataset.patches
            if getattr(patch, "status", None) == "applied"
        )
        result_candidates.extend(
            _normalize_text(getattr(event, "description", None))
            for event in dataset.growth
        )
        result_candidates.extend(
            task.title for task in dataset.tasks if task.id in completed_task_ids
        )
        return _unique_strings(result_candidates)[:5]

    def _build_blockers(self, dataset: _WindowDataset) -> list[str]:
        blockers: list[str | None] = []
        blocked_tasks = sorted(
            (
                task
                for task in dataset.tasks
                if task.id in dataset.window_task_ids
                and task.status in {"failed", "blocked", "needs-confirm"}
            ),
            key=lambda task: _timestamp_key(
                _task_activity_at(task, dataset.runtimes_by_task.get(task.id)),
            ),
            reverse=True,
        )
        for task in blocked_tasks:
            runtime = dataset.runtimes_by_task.get(task.id)
            reason = (
                _normalize_text(runtime.last_error_summary if runtime is not None else None)
                or _normalize_text(task.summary)
                or task.status
            )
            blockers.append(f"{task.title}: {reason}")
        blockers.extend(
            decision.summary
            for decision in dataset.decisions
            if decision.status not in {"approved", "rejected", "resolved", "cancelled"}
        )
        return _unique_strings(blockers)[:5]

    def _build_next_steps(self, dataset: _WindowDataset) -> list[str]:
        active_tasks = sorted(
            (
                task
                for task in dataset.tasks
                if task.status not in _TERMINAL_TASK_STATUSES
            ),
            key=lambda task: _timestamp_key(
                _task_activity_at(task, dataset.runtimes_by_task.get(task.id)),
            ),
            reverse=True,
        )
        next_steps = [
            f"{task.title}: {_normalize_text(task.summary) or task.status}"
            for task in active_tasks[:5]
        ]
        if not next_steps:
            next_steps = [
                decision.summary
                for decision in dataset.decisions
                if decision.status not in {"approved", "rejected", "resolved", "cancelled"}
            ]
        return _unique_strings(next_steps)[:5]

    def get_performance_overview(
        self,
        *,
        window: ReportWindow = "weekly",
        scope_type: ReportScopeType = "global",
        scope_id: str | None = None,
    ) -> dict[str, Any]:
        until = _utc_now()
        since = until - timedelta(days=_WINDOW_DAYS[window])
        snapshot = self._build_scope_snapshot(
            scope_type=scope_type,
            scope_id=scope_id,
            since=since,
            until=until,
        )
        dataset = self._collect_window_dataset(
            window=window,
            scope_type=scope_type,
            scope_id=scope_id,
            until=until,
            snapshot=snapshot,
        )
        prediction = self._prediction_snapshot(dataset)
        metrics = self._build_metrics(dataset, prediction=prediction)
        return {
            "window": window,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "scope_label": dataset.scope_label,
            "since": dataset.since,
            "until": dataset.until,
            "metrics": [metric.model_dump(mode="json") for metric in metrics],
            "task_status_counts": dict(
                Counter(task.status for task in dataset.tasks if task.id in dataset.window_task_ids),
            ),
            "runtime_status_counts": dict(
                Counter(
                    runtime.runtime_status
                    for task_id, runtime in dataset.runtimes_by_task.items()
                    if task_id in dataset.window_task_ids
                ),
            ),
            "goal_status_counts": dict(
                Counter(
                    goal.status
                    for goal in dataset.goals
                    if goal.id in dataset.window_goal_ids
                ),
            ),
            "prediction_stats": {
                "prediction_count": prediction.case_count,
                "recommendation_count": prediction.recommendation_count,
                "review_count": prediction.review_count,
                "auto_execution_count": prediction.auto_execution_count,
                "prediction_hit_rate": prediction.hit_rate,
                "recommendation_adoption_rate": prediction.adoption_rate,
                "recommendation_execution_benefit": prediction.average_benefit,
            },
            "agent_breakdown": self._build_agent_breakdown(dataset),
            "routes": {
                "report": self._report_route(
                    window=window,
                    scope_type=scope_type,
                    scope_id=scope_id,
                ),
            },
        }

    def _collect_window_dataset(
        self,
        *,
        window: ReportWindow,
        scope_type: ReportScopeType,
        scope_id: str | None,
        until: datetime | None = None,
        snapshot: _ScopeSnapshot | None = None,
    ) -> _WindowDataset:
        resolved_until = until or _utc_now()
        since = resolved_until - timedelta(days=_WINDOW_DAYS[window])
        resolved_snapshot = snapshot or self._build_scope_snapshot(
            scope_type=scope_type,
            scope_id=scope_id,
            since=since,
            until=resolved_until,
        )
        task_ids = {task.id for task in resolved_snapshot.tasks}
        decisions = [
            decision
            for decision in resolved_snapshot.decisions
            if decision.task_id in task_ids
            and _created_within(decision.created_at, since=since, until=resolved_until)
        ]
        evidence = self._evidence_ledger.list_records(
            since=since,
            until=resolved_until,
            task_ids=sorted(task_ids) if task_ids else None,
            actor_refs=(
                sorted(resolved_snapshot.scope_agent_ids)
                if scope_type == "agent" and not task_ids
                else None
            ),
        )
        proposals = [
            proposal
            for proposal in resolved_snapshot.proposals
            if _created_within(
                getattr(proposal, "created_at", None),
                since=since,
                until=resolved_until,
            )
        ]
        patches = [
            patch
            for patch in resolved_snapshot.patches
            if _created_within(
                getattr(patch, "created_at", None),
                since=since,
                until=resolved_until,
            )
        ]
        growth = [
            event
            for event in resolved_snapshot.growth
            if _created_within(
                getattr(event, "created_at", None),
                since=since,
                until=resolved_until,
            )
        ]
        event_task_ids = {
            str(item.task_id)
            for item in (*proposals, *patches, *growth)
            if getattr(item, "task_id", None)
        }
        event_task_ids.update(record.task_id for record in evidence if record.task_id)
        event_task_ids.update(decision.task_id for decision in decisions if decision.task_id)
        window_task_ids = {
            task.id
            for task in resolved_snapshot.tasks
            if _created_within(task.created_at, since=since, until=resolved_until)
            or _created_within(task.updated_at, since=since, until=resolved_until)
            or (
                task.id in resolved_snapshot.runtimes_by_task
                and _created_within(
                    resolved_snapshot.runtimes_by_task[task.id].updated_at,
                    since=since,
                    until=resolved_until,
                )
            )
            or task.id in event_task_ids
        }
        window_goal_ids = {
            goal.id
            for goal in resolved_snapshot.goals
            if _created_within(goal.created_at, since=since, until=resolved_until)
            or _created_within(goal.updated_at, since=since, until=resolved_until)
        }
        window_goal_ids.update(
            task.goal_id
            for task in resolved_snapshot.tasks
            if task.id in window_task_ids and task.goal_id
        )
        agent_ids = _unique_strings(
            [
                *(
                    resolved_snapshot.scope_agent_ids
                    if scope_type == "agent"
                    else []
                ),
                *(
                    task.owner_agent_id
                    for task in resolved_snapshot.tasks
                    if task.id in window_task_ids
                ),
                *(
                    resolved_snapshot.runtimes_by_task[task.id].last_owner_agent_id
                    for task in resolved_snapshot.tasks
                    if (
                        task.id in window_task_ids
                        and task.id in resolved_snapshot.runtimes_by_task
                    )
                ),
                *(record.actor_ref for record in evidence),
                *(getattr(item, "agent_id", None) for item in (*proposals, *patches, *growth)),
            ],
        )
        active_task_count = sum(
            1
            for task in resolved_snapshot.tasks
            if task.id in window_task_ids and task.status not in _TERMINAL_TASK_STATUSES
        )
        return _WindowDataset(
            window=window,
            scope_type=scope_type,
            scope_id=scope_id,
            scope_label=resolved_snapshot.scope_label,
            since=since,
            until=resolved_until,
            goals=resolved_snapshot.goals,
            tasks=resolved_snapshot.tasks,
            runtimes_by_task=resolved_snapshot.runtimes_by_task,
            decisions=decisions,
            evidence=evidence,
            proposals=proposals,
            patches=patches,
            growth=growth,
            agent_ids=agent_ids,
            active_task_count=active_task_count,
            window_goal_ids=window_goal_ids,
            window_task_ids=window_task_ids,
        )

    def _build_scope_snapshot(
        self,
        *,
        scope_type: ReportScopeType,
        scope_id: str | None,
        since: datetime,
        until: datetime,
    ) -> _ScopeSnapshot:
        scope = self._resolve_scope(
            scope_type=scope_type,
            scope_id=scope_id,
        )
        scope_tasks = self._list_scope_tasks(scope)
        scope_task_ids = {task.id for task in scope_tasks}
        tasks_by_id = {task.id: task for task in scope_tasks}

        recent_tasks = self._list_recent_tasks(scope=scope, since=since)
        tasks_by_id.update({task.id: task for task in recent_tasks})

        recent_runtimes = self._list_recent_runtimes(scope=scope, since=since)
        recent_runtime_task_ids = {runtime.task_id for runtime in recent_runtimes}

        recent_evidence = self._list_scope_evidence(
            scope=scope,
            scope_task_ids=scope_task_ids,
            since=since,
            until=until,
        )
        recent_evidence_task_ids = {
            record.task_id
            for record in recent_evidence
            if record.task_id
        }

        recent_decisions = self._list_scope_decisions(
            scope=scope,
            scope_task_ids=scope_task_ids,
            since=since,
        )
        recent_decision_task_ids = {
            decision.task_id
            for decision in recent_decisions
            if decision.task_id
        }

        proposal_candidates = self._list_learning_items(
            "list_proposals",
            created_since=since,
        )
        patch_candidates = self._list_learning_items(
            "list_patches",
            created_since=since,
        )
        growth_candidates = self._list_learning_items(
            "list_growth",
            created_since=since,
            limit=500,
        )

        task_ids = set(scope_task_ids if scope.scope_type != "global" else [])
        task_ids.update(tasks_by_id)
        task_ids.update(recent_runtime_task_ids)
        task_ids.update(recent_evidence_task_ids)
        task_ids.update(recent_decision_task_ids)
        if scope.scope_type == "global":
            task_ids.update(
                str(item.task_id)
                for item in (*proposal_candidates, *patch_candidates, *growth_candidates)
                if getattr(item, "task_id", None)
            )
        else:
            task_ids.update(
                str(item.task_id)
                for item in (*proposal_candidates, *patch_candidates, *growth_candidates)
                if getattr(item, "task_id", None) and str(item.task_id) in scope_task_ids
            )

        missing_task_ids = task_ids.difference(tasks_by_id)
        if missing_task_ids:
            tasks_by_id.update(
                {
                    task.id: task
                    for task in self._task_repository.list_tasks(
                        task_ids=sorted(missing_task_ids),
                    )
                },
            )

        runtimes_by_task = {runtime.task_id: runtime for runtime in recent_runtimes}
        if task_ids:
            missing_runtime_task_ids = task_ids.difference(runtimes_by_task)
            if missing_runtime_task_ids:
                runtimes_by_task.update(
                    {
                        runtime.task_id: runtime
                        for runtime in self._task_runtime_repository.list_runtimes(
                            task_ids=sorted(missing_runtime_task_ids),
                        )
                    },
                )

        tasks = [
            task
            for task in tasks_by_id.values()
            if self._task_matches_scope(task, scope=scope, runtimes=runtimes_by_task)
        ]
        task_ids = {task.id for task in tasks}
        goal_ids = {
            task.goal_id
            for task in tasks
            if task.goal_id
        }
        goal_ids.update(scope.goal_ids)

        goals_by_id = {
            goal.id: goal
            for goal in self._list_recent_goals(scope=scope, since=since)
        }
        missing_goal_ids = goal_ids.difference(goals_by_id)
        if missing_goal_ids and self._goal_repository is not None:
            goals_by_id.update(
                {
                    goal.id: goal
                    for goal in self._goal_repository.list_goals(
                        goal_ids=sorted(missing_goal_ids),
                    )
                },
            )
        goals = [
            goal
            for goal in goals_by_id.values()
            if goal.id in goal_ids
        ]
        goal_ids = {goal.id for goal in goals}
        decisions = [
            decision
            for decision in recent_decisions
            if decision.task_id in task_ids
        ]
        proposals = [
            proposal
            for proposal in proposal_candidates
            if (
                scope_type == "global"
                or self._learning_matches_scope(
                    proposal,
                    goal_ids=goal_ids,
                    task_ids=task_ids,
                    agent_ids=scope.agent_ids,
                )
            )
        ]
        patches = [
            patch
            for patch in patch_candidates
            if (
                scope_type == "global"
                or self._learning_matches_scope(
                    patch,
                    goal_ids=goal_ids,
                    task_ids=task_ids,
                    agent_ids=scope.agent_ids,
                )
            )
        ]
        growth = [
            event
            for event in growth_candidates
            if (
                scope_type == "global"
                or self._learning_matches_scope(
                    event,
                    goal_ids=goal_ids,
                    task_ids=task_ids,
                    agent_ids=scope.agent_ids,
                )
            )
        ]
        return _ScopeSnapshot(
            scope_type=scope_type,
            scope_id=scope_id,
            scope_label=scope.label,
            scope_agent_ids=set(scope.agent_ids),
            tasks=tasks,
            goals=goals,
            runtimes_by_task={
                task_id: runtimes_by_task[task_id]
                for task_id in task_ids
                if task_id in runtimes_by_task
            },
            decisions=decisions,
            proposals=proposals,
            patches=patches,
            growth=growth,
        )

    def _list_scope_tasks(self, scope: _ReportingScope) -> list[TaskRecord]:
        if scope.scope_type == "global":
            return []
        tasks_by_id: dict[str, TaskRecord] = {}
        if scope.goal_ids:
            tasks_by_id.update(
                {
                    task.id: task
                    for task in self._task_repository.list_tasks(
                        goal_ids=sorted(scope.goal_ids),
                    )
                },
            )
        if scope.agent_ids:
            tasks_by_id.update(
                {
                    task.id: task
                    for task in self._task_repository.list_tasks(
                        owner_agent_ids=sorted(scope.agent_ids),
                    )
                },
            )
            runtime_task_ids = {
                runtime.task_id
                for runtime in self._task_runtime_repository.list_runtimes(
                    last_owner_agent_ids=sorted(scope.agent_ids),
                )
            }
            missing_task_ids = runtime_task_ids.difference(tasks_by_id)
            if missing_task_ids:
                tasks_by_id.update(
                    {
                        task.id: task
                        for task in self._task_repository.list_tasks(
                            task_ids=sorted(missing_task_ids),
                        )
                    },
                )
        return list(tasks_by_id.values())

    def _list_recent_tasks(
        self,
        *,
        scope: _ReportingScope,
        since: datetime,
    ) -> list[TaskRecord]:
        if scope.scope_type == "global":
            return self._task_repository.list_tasks(activity_since=since)
        tasks_by_id: dict[str, TaskRecord] = {}
        if scope.goal_ids:
            tasks_by_id.update(
                {
                    task.id: task
                    for task in self._task_repository.list_tasks(
                        goal_ids=sorted(scope.goal_ids),
                        activity_since=since,
                    )
                },
            )
        if scope.agent_ids:
            tasks_by_id.update(
                {
                    task.id: task
                    for task in self._task_repository.list_tasks(
                        owner_agent_ids=sorted(scope.agent_ids),
                        activity_since=since,
                    )
                },
            )
        return list(tasks_by_id.values())

    def _list_recent_runtimes(
        self,
        *,
        scope: _ReportingScope,
        since: datetime,
    ) -> list[TaskRuntimeRecord]:
        if scope.scope_type == "global":
            return self._task_runtime_repository.list_runtimes(updated_since=since)
        if not scope.agent_ids:
            return []
        return self._task_runtime_repository.list_runtimes(
            last_owner_agent_ids=sorted(scope.agent_ids),
            updated_since=since,
        )

    def _list_recent_goals(
        self,
        *,
        scope: _ReportingScope,
        since: datetime,
    ) -> list[GoalRecord]:
        if self._goal_repository is None:
            return []
        if scope.scope_type == "global":
            return self._goal_repository.list_goals(activity_since=since)
        if not scope.goal_ids:
            return []
        return self._goal_repository.list_goals(
            goal_ids=sorted(scope.goal_ids),
            activity_since=since,
        )

    def _list_scope_evidence(
        self,
        *,
        scope: _ReportingScope,
        scope_task_ids: set[str],
        since: datetime,
        until: datetime,
    ) -> list[EvidenceRecord]:
        if scope.scope_type == "global":
            return self._evidence_ledger.list_records(since=since, until=until)
        if not scope_task_ids:
            return []
        return self._evidence_ledger.list_records(
            since=since,
            until=until,
            task_ids=sorted(scope_task_ids),
        )

    def _list_scope_decisions(
        self,
        *,
        scope: _ReportingScope,
        scope_task_ids: set[str],
        since: datetime,
    ) -> list[DecisionRequestRecord]:
        if scope.scope_type == "global":
            return self._decision_request_repository.list_decision_requests(
                created_since=since,
            )
        if not scope_task_ids:
            return []
        return self._decision_request_repository.list_decision_requests(
            task_ids=sorted(scope_task_ids),
            created_since=since,
        )

    def _build_metrics(
        self,
        dataset: _WindowDataset,
        *,
        prediction: _PredictionSnapshot | None = None,
    ) -> list[MetricRecord]:
        window_tasks = [
            task
            for task in dataset.tasks
            if task.id in dataset.window_task_ids
        ]
        terminal_tasks = [
            task
            for task in window_tasks
            if task.status in _TERMINAL_TASK_STATUSES
        ]
        completed_tasks = sum(1 for task in terminal_tasks if task.status == "completed")
        failed_tasks = sum(1 for task in terminal_tasks if task.status == "failed")
        tasks_with_decisions = {
            decision.task_id
            for decision in dataset.decisions
            if decision.task_id
        }
        failed_evidence = sum(
            1
            for record in dataset.evidence
            if record.status == "failed"
        )
        applied_patches = sum(
            1
            for patch in dataset.patches
            if getattr(patch, "status", None) == "applied"
        )
        rolled_back_patches = sum(
            1
            for patch in dataset.patches
            if getattr(patch, "status", None) == "rolled_back"
        )
        agent_count = max(1, len(dataset.agent_ids))
        metrics = [
            self._metric(
                key="task_success_rate",
                label="任务成功率",
                window=dataset.window,
                scope_type=dataset.scope_type,
                scope_id=dataset.scope_id,
                numerator=completed_tasks,
                denominator=len(terminal_tasks),
                formula="已完成任务数 / 已结束任务数",
                source_summary="统计窗口内的 TaskRecord.status。",
                unit="percent",
            ),
            self._metric(
                key="manual_intervention_rate",
                label="人工介入率",
                window=dataset.window,
                scope_type=dataset.scope_type,
                scope_id=dataset.scope_id,
                numerator=len(tasks_with_decisions),
                denominator=len(dataset.window_task_ids),
                formula="涉及决策的任务数 / 窗口内任务数",
                source_summary="统计窗口内的 DecisionRequestRecord.task_id。",
                unit="percent",
            ),
            self._metric(
                key="exception_rate",
                label="异常率",
                window=dataset.window,
                scope_type=dataset.scope_type,
                scope_id=dataset.scope_id,
                numerator=failed_evidence,
                denominator=len(dataset.evidence),
                formula="失败证据数 / 证据总数",
                source_summary="统计窗口内的 EvidenceRecord.status。",
                unit="percent",
            ),
            self._metric(
                key="patch_apply_rate",
                label="补丁应用率",
                window=dataset.window,
                scope_type=dataset.scope_type,
                scope_id=dataset.scope_id,
                numerator=applied_patches,
                denominator=len(dataset.patches),
                formula="已应用补丁数 / 新建补丁数",
                source_summary="统计窗口内的 Patch.status。",
                unit="percent",
            ),
            self._metric(
                key="rollback_rate",
                label="回滚率",
                window=dataset.window,
                scope_type=dataset.scope_type,
                scope_id=dataset.scope_id,
                numerator=rolled_back_patches,
                denominator=applied_patches,
                formula="已回滚补丁数 / 已应用补丁数",
                source_summary="统计窗口内的 Patch.status。",
                unit="percent",
            ),
            self._metric(
                key="active_task_load",
                label="人均活跃任务负载",
                window=dataset.window,
                scope_type=dataset.scope_type,
                scope_id=dataset.scope_id,
                numerator=dataset.active_task_count,
                denominator=agent_count,
                formula="窗口内活跃任务数 / 参与智能体数",
                source_summary="窗口内活跃任务总量除以参与智能体数量。",
                unit="ratio",
            ),
        ]
        if prediction is not None:
            metrics.extend(
                [
                    self._metric(
                        key="prediction_hit_rate",
                        label="预测命中率",
                        window=dataset.window,
                        scope_type=dataset.scope_type,
                        scope_id=dataset.scope_id,
                        numerator=int(round(prediction.hit_rate * 10)),
                        denominator=1000,
                        formula="(命中复盘数 + 部分命中复盘数) / 已复盘预测数",
                        source_summary="统计窗口内的 PredictionReviewRecord.outcome。",
                        unit="percent",
                    ).model_copy(update={"value": prediction.hit_rate, "display_value": _display_metric(prediction.hit_rate, "percent")}),
                    self._metric(
                        key="recommendation_adoption_rate",
                        label="建议采纳率",
                        window=dataset.window,
                        scope_type=dataset.scope_type,
                        scope_id=dataset.scope_id,
                        numerator=int(round(prediction.adoption_rate * 10)),
                        denominator=1000,
                        formula="已采纳复盘数 / 已复盘预测数",
                        source_summary="统计窗口内的 PredictionReviewRecord.adopted。",
                        unit="percent",
                    ).model_copy(update={"value": prediction.adoption_rate, "display_value": _display_metric(prediction.adoption_rate, "percent")}),
                    MetricRecord(
                        key="recommendation_execution_benefit",
                        label="建议执行收益",
                        window=dataset.window,
                        scope_type=dataset.scope_type,
                        scope_id=dataset.scope_id,
                        value=prediction.average_benefit,
                        unit="ratio",
                        display_value=_display_metric(prediction.average_benefit, "ratio"),
                        numerator=prediction.average_benefit,
                        denominator=1.0,
                        formula="平均值(复盘收益评分)",
                        source_summary="统计窗口内的 PredictionReviewRecord.benefit_score。",
                    ),
                ],
            )
        return metrics

    def _metric(
        self,
        *,
        key: str,
        label: str,
        window: ReportWindow,
        scope_type: ReportScopeType,
        scope_id: str | None,
        numerator: int,
        denominator: int,
        formula: str,
        source_summary: str,
        unit: str,
    ) -> MetricRecord:
        if unit == "percent":
            value = _ratio_percent(numerator, denominator)
        elif unit == "count":
            value = float(numerator)
        else:
            value = round(numerator / denominator, 2) if denominator > 0 else 0.0
        return MetricRecord(
            key=key,
            label=label,
            window=window,
            scope_type=scope_type,
            scope_id=scope_id,
            value=value,
            unit=unit,
            display_value=_display_metric(value, unit),
            numerator=float(numerator),
            denominator=float(denominator),
            formula=formula,
            source_summary=source_summary,
        )

    def _build_agent_breakdown(self, dataset: _WindowDataset) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for agent_id in dataset.agent_ids:
            related_tasks = [
                task
                for task in dataset.tasks
                if task.id in dataset.window_task_ids
                and (
                    task.owner_agent_id == agent_id
                    or dataset.runtimes_by_task.get(task.id, None) is not None
                    and dataset.runtimes_by_task[task.id].last_owner_agent_id == agent_id
                )
            ]
            related_task_ids = {task.id for task in related_tasks}
            terminal_tasks = [
                task
                for task in related_tasks
                if task.status in _TERMINAL_TASK_STATUSES
            ]
            completed = sum(1 for task in terminal_tasks if task.status == "completed")
            failed = sum(1 for task in terminal_tasks if task.status == "failed")
            evidence_count = sum(
                1
                for record in dataset.evidence
                if record.actor_ref == agent_id or record.task_id in related_task_ids
            )
            decision_count = sum(
                1
                for decision in dataset.decisions
                if decision.task_id in related_task_ids
            )
            patch_count = sum(
                1
                for patch in dataset.patches
                if getattr(patch, "agent_id", None) == agent_id
            )
            applied_patch_count = sum(
                1
                for patch in dataset.patches
                if getattr(patch, "agent_id", None) == agent_id
                and getattr(patch, "status", None) == "applied"
            )
            rollback_patch_count = sum(
                1
                for patch in dataset.patches
                if getattr(patch, "agent_id", None) == agent_id
                and getattr(patch, "status", None) == "rolled_back"
            )
            active_task_count = sum(
                1
                for task in related_tasks
                if task.status not in _TERMINAL_TASK_STATUSES
            )
            items.append(
                {
                    "agent_id": agent_id,
                    "name": self._agent_label(agent_id),
                    "task_count": len(related_tasks),
                    "window_task_count": len(related_tasks),
                    "active_task_count": active_task_count,
                    "completed_task_count": completed,
                    "failed_task_count": failed,
                    "success_rate": _ratio_percent(completed, len(terminal_tasks)),
                    "evidence_count": evidence_count,
                    "decision_count": decision_count,
                    "patch_count": patch_count,
                    "applied_patch_count": applied_patch_count,
                    "rollback_patch_count": rollback_patch_count,
                    "route": f"/api/runtime-center/agents/{agent_id}",
                },
            )
        items.sort(
            key=lambda item: (
                -int(item["active_task_count"]),
                -int(item["evidence_count"]),
                str(item["agent_id"]),
            ),
        )
        return items

    def _resolve_scope(
        self,
        *,
        scope_type: ReportScopeType,
        scope_id: str | None,
    ) -> _ReportingScope:
        if scope_type == "global":
            return _ReportingScope(
                scope_type=scope_type,
                scope_id=None,
                label="全局",
                goal_ids=set(),
                agent_ids=set(),
            )
        if scope_id is None:
            raise KeyError(f"{scope_type} scope requires scope_id")
        if scope_type == "agent":
            return _ReportingScope(
                scope_type=scope_type,
                scope_id=scope_id,
                label=f"智能体 {scope_id}",
                goal_ids=set(),
                agent_ids={scope_id},
            )
        if self._industry_instance_repository is None:
            raise KeyError("Industry instance repository is not available")
        instance = self._industry_instance_repository.get_instance(scope_id)
        if instance is None:
            raise KeyError(f"Industry instance '{scope_id}' not found")
        return _ReportingScope(
            scope_type=scope_type,
            scope_id=scope_id,
            label=instance.label,
            goal_ids=set(instance.goal_ids or []),
            agent_ids=set(instance.agent_ids or []),
        )

    def _task_matches_scope(
        self,
        task: TaskRecord,
        *,
        scope: _ReportingScope,
        runtimes: dict[str, TaskRuntimeRecord],
    ) -> bool:
        if scope.scope_type == "global":
            return True
        runtime = runtimes.get(task.id)
        owner_ids = {
            owner_id
            for owner_id in (
                task.owner_agent_id,
                runtime.last_owner_agent_id if runtime is not None else None,
            )
            if owner_id
        }
        if task.goal_id and task.goal_id in scope.goal_ids:
            return True
        return bool(scope.agent_ids.intersection(owner_ids))

    def _learning_matches_scope(
        self,
        item: Any,
        *,
        goal_ids: set[str],
        task_ids: set[str],
        agent_ids: set[str],
    ) -> bool:
        goal_id = getattr(item, "goal_id", None)
        task_id = getattr(item, "task_id", None)
        agent_id = getattr(item, "agent_id", None)
        if goal_id and goal_id in goal_ids:
            return True
        if task_id and task_id in task_ids:
            return True
        if agent_id and agent_id in agent_ids:
            return True
        return False

    def _list_learning_items(
        self,
        method_name: str,
        **kwargs,
    ) -> list[Any]:
        service = self._learning_service
        method = getattr(service, method_name, None)
        if not callable(method):
            return []
        result = method(**kwargs)
        return list(result) if isinstance(result, list) else list(result or [])

    def _prediction_snapshot(self, dataset: _WindowDataset) -> _PredictionSnapshot:
        if (
            self._prediction_case_repository is None
            or self._prediction_recommendation_repository is None
            or self._prediction_review_repository is None
        ):
            return _PredictionSnapshot(
                case_count=0,
                recommendation_count=0,
                review_count=0,
                auto_execution_count=0,
                hit_rate=0.0,
                adoption_rate=0.0,
                average_benefit=0.0,
            )
        case_filters: dict[str, Any] = {"activity_since": dataset.since}
        if dataset.scope_type == "industry":
            case_filters["industry_instance_id"] = dataset.scope_id
        elif dataset.scope_type == "agent":
            case_filters["owner_agent_id"] = dataset.scope_id
        cases = [
            case
            for case in self._prediction_case_repository.list_cases(**case_filters)
            if self._prediction_case_matches_scope(case, dataset=dataset)
            and (
                _created_within(case.created_at, since=dataset.since, until=dataset.until)
                or _created_within(case.updated_at, since=dataset.since, until=dataset.until)
            )
        ]
        case_ids = {case.case_id for case in cases}
        recommendations = (
            [
                recommendation
                for recommendation in self._prediction_recommendation_repository.list_recommendations(
                    case_ids=sorted(case_ids),
                    activity_since=dataset.since,
                )
                if (
                    _created_within(
                        recommendation.created_at,
                        since=dataset.since,
                        until=dataset.until,
                    )
                    or _created_within(
                        recommendation.updated_at,
                        since=dataset.since,
                        until=dataset.until,
                    )
                )
            ]
            if case_ids
            else []
        )
        reviews = (
            [
                review
                for review in self._prediction_review_repository.list_reviews(
                    case_ids=sorted(case_ids),
                    activity_since=dataset.since,
                )
                if (
                    _created_within(review.created_at, since=dataset.since, until=dataset.until)
                    or _created_within(review.updated_at, since=dataset.since, until=dataset.until)
                )
            ]
            if case_ids
            else []
        )
        known_reviews = [review for review in reviews if review.outcome != "unknown"]
        hit_count = sum(1 for review in known_reviews if review.outcome in {"hit", "partial"})
        adopted_count = sum(1 for review in reviews if review.adopted is True)
        benefit_values = [review.benefit_score for review in reviews if review.benefit_score is not None]
        return _PredictionSnapshot(
            case_count=len(cases),
            recommendation_count=len(recommendations),
            review_count=len(reviews),
            auto_execution_count=sum(
                1
                for recommendation in recommendations
                if recommendation.auto_executed and recommendation.status == "executed"
            ),
            hit_rate=_ratio_percent(hit_count, len(known_reviews)),
            adoption_rate=_ratio_percent(adopted_count, len(reviews)),
            average_benefit=(
                round(sum(benefit_values) / len(benefit_values), 2)
                if benefit_values
                else 0.0
            ),
        )

    def _prediction_case_matches_scope(
        self,
        case: Any,
        *,
        dataset: _WindowDataset,
    ) -> bool:
        if dataset.scope_type == "global":
            return True
        if dataset.scope_type == "industry":
            return getattr(case, "industry_instance_id", None) == dataset.scope_id
        return getattr(case, "owner_agent_id", None) == dataset.scope_id

    def _agent_label(self, agent_id: str) -> str:
        service = self._agent_profile_service
        getter = getattr(service, "get_agent", None)
        if callable(getter):
            agent = getter(agent_id)
            if agent is not None:
                name = getattr(agent, "name", None)
                if isinstance(name, str) and name.strip():
                    return name
        return agent_id

    def _report_title(self, dataset: _WindowDataset) -> str:
        return f"{dataset.scope_label}{_window_label(dataset.window)}"

    def _report_route(
        self,
        *,
        window: ReportWindow,
        scope_type: ReportScopeType,
        scope_id: str | None,
    ) -> str:
        route = f"/api/runtime-center/reports?window={window}&scope_type={scope_type}"
        if scope_id:
            route = f"{route}&scope_id={scope_id}"
        return route

    def _performance_route(
        self,
        *,
        window: ReportWindow,
        scope_type: ReportScopeType,
        scope_id: str | None,
    ) -> str:
        route = f"/api/runtime-center/performance?window={window}&scope_type={scope_type}"
        if scope_id:
            route = f"{route}&scope_id={scope_id}"
        return route
