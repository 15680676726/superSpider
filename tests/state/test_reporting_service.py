# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from copaw.evidence import EvidenceLedger, EvidenceRecord
from copaw.learning import LearningEngine, LearningService
from copaw.learning.models import GrowthEvent, Patch
from copaw.state import (
    DecisionRequestRecord,
    GoalRecord,
    SQLiteStateStore,
    TaskRecord,
    TaskRuntimeRecord,
)
from copaw.state.reporting_service import StateReportingService
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteGoalRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


def _build_service(tmp_path) -> StateReportingService:
    store = SQLiteStateStore(tmp_path / "state.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    goal_repository = SqliteGoalRepository(store)
    decision_repository = SqliteDecisionRequestRepository(store)
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    learning_service = LearningService(
        engine=LearningEngine(tmp_path / "learning.db"),
    )

    goal_repository.upsert_goal(
        GoalRecord(
            id="goal-1",
            title="Operate the team",
            summary="Keep the industry team moving.",
            status="active",
            owner_scope="industry",
        ),
    )
    task_repository.upsert_task(
        TaskRecord(
            id="task-1",
            goal_id="goal-1",
            title="Daily operating review",
            summary="Review daily operating evidence.",
            task_type="analysis",
            status="completed",
            owner_agent_id="ops-agent",
        ),
    )
    task_repository.upsert_task(
        TaskRecord(
            id="task-2",
            goal_id="goal-1",
            title="Investigate anomaly",
            summary="Follow the failed signal.",
            task_type="analysis",
            status="failed",
            owner_agent_id="research-agent",
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-1",
            runtime_status="terminated",
            current_phase="completed",
            last_owner_agent_id="ops-agent",
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-2",
            runtime_status="terminated",
            current_phase="failed",
            last_owner_agent_id="research-agent",
            last_error_summary="Signal validation failed.",
        ),
    )
    decision_repository.upsert_decision_request(
        DecisionRequestRecord(
            id="decision-1",
            task_id="task-2",
            decision_type="manual-review",
            summary="Confirm whether to rollback the signal change.",
            requested_by="execution-core",
            status="reviewing",
        ),
    )
    evidence_ledger.append(
        EvidenceRecord(
            task_id="task-1",
            actor_ref="ops-agent",
            risk_level="auto",
            action_summary="Summarized operating evidence",
            result_summary="Daily review completed.",
            capability_ref="reporting",
            status="recorded",
        ),
    )
    failed_evidence = evidence_ledger.append(
        EvidenceRecord(
            task_id="task-2",
            actor_ref="research-agent",
            risk_level="guarded",
            action_summary="Validated anomaly",
            result_summary="Validation failed and needs escalation.",
            capability_ref="research",
            status="failed",
        ),
    )
    learning_service.create_proposal(
        title="Strengthen anomaly SOP",
        description="Add an explicit rollback checklist.",
        agent_id="research-agent",
        goal_id="goal-1",
        task_id="task-2",
        evidence_refs=[failed_evidence.id],
    )
    learning_service.engine.create_patch(
        patch=Patch(
            id="patch-1",
            kind="plan_patch",
            goal_id="goal-1",
            task_id="task-2",
            agent_id="research-agent",
            title="Rollback checklist",
            description="Add rollback checkpoints to the anomaly SOP.",
            risk_level="guarded",
            status="applied",
            source_evidence_id=failed_evidence.id,
        ),
    )
    learning_service.engine.record_growth(
        GrowthEvent(
            id="growth-1",
            agent_id="research-agent",
            goal_id="goal-1",
            task_id="task-2",
            change_type="patch_applied",
            description="Applied anomaly rollback checklist.",
            source_patch_id="patch-1",
            source_evidence_id=failed_evidence.id,
            result="applied",
        ),
    )

    return StateReportingService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        goal_repository=goal_repository,
        decision_request_repository=decision_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
    )


def test_reporting_service_builds_formal_report_and_metrics(tmp_path) -> None:
    service = _build_service(tmp_path)

    reports = service.list_reports()
    assert [report.window for report in reports] == ["daily", "weekly", "monthly"]

    weekly = service.get_report(window="weekly")
    assert weekly.task_count == 2
    assert weekly.evidence_count == 2
    assert weekly.proposal_count == 1
    assert weekly.patch_count == 1
    assert weekly.applied_patch_count == 1
    assert weekly.decision_count == 1
    assert "goal_count" not in weekly.model_dump(mode="json")
    assert weekly.agent_count == 2
    assert weekly.focus_items == ["Operate the team"]
    assert [item.task_id for item in weekly.completed_tasks] == ["task-1"]
    assert weekly.completed_tasks[0].route == "/api/runtime-center/tasks/task-1"
    assert weekly.primary_evidence[0].evidence_id
    assert any("Investigate anomaly" in item for item in weekly.blockers)
    assert weekly.next_steps == ["Confirm whether to rollback the signal change."]
    assert "Daily review completed." in weekly.key_results
    metric_map = {metric.key: metric for metric in weekly.metrics}
    assert metric_map["task_success_rate"].display_value == "50.0%"
    assert metric_map["manual_intervention_rate"].display_value == "50.0%"
    assert metric_map["exception_rate"].display_value == "50.0%"


def test_reporting_service_supports_agent_scoped_report_content(tmp_path) -> None:
    service = _build_service(tmp_path)

    report = service.get_report(window="weekly", scope_type="agent", scope_id="research-agent")

    assert report.scope_type == "agent"
    assert report.scope_id == "research-agent"
    assert report.agent_ids == ["research-agent"]
    assert report.task_ids == ["task-2"]
    assert report.completed_tasks == []
    assert any("Investigate anomaly" in item for item in report.blockers)
    assert report.next_steps == ["Confirm whether to rollback the signal change."]


def test_reporting_service_list_reports_reuses_scope_snapshot(tmp_path) -> None:
    service = _build_service(tmp_path)
    original = service._build_scope_snapshot
    calls: list[tuple[str, str | None]] = []

    def _wrapped_scope_snapshot(*, scope_type, scope_id, since, until):
        calls.append((scope_type, scope_id))
        return original(
            scope_type=scope_type,
            scope_id=scope_id,
            since=since,
            until=until,
        )

    service._build_scope_snapshot = _wrapped_scope_snapshot  # type: ignore[method-assign]

    reports = service.list_reports()

    assert [report.window for report in reports] == ["daily", "weekly", "monthly"]
    assert calls == [("global", None)]


def test_reporting_service_builds_agent_breakdown(tmp_path) -> None:
    service = _build_service(tmp_path)

    overview = service.get_performance_overview(window="weekly")
    assert overview["scope_type"] == "global"
    assert len(overview["metrics"]) == 9
    metric_keys = {item["key"] for item in overview["metrics"]}
    assert "prediction_hit_rate" in metric_keys
    assert "recommendation_adoption_rate" in metric_keys
    assert "recommendation_execution_benefit" in metric_keys
    assert len(overview["agent_breakdown"]) == 2
    agent_map = {item["agent_id"]: item for item in overview["agent_breakdown"]}
    assert agent_map["ops-agent"]["completed_task_count"] == 1
    assert agent_map["research-agent"]["failed_task_count"] == 1
    assert agent_map["research-agent"]["decision_count"] == 1


def test_reporting_service_ignores_stale_scope_objects_without_window_activity(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    goal_repository = SqliteGoalRepository(store)
    decision_repository = SqliteDecisionRequestRepository(store)
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    learning_service = LearningService(
        engine=LearningEngine(tmp_path / "learning.db"),
    )

    old_timestamp = datetime.now(timezone.utc) - timedelta(days=14)
    goal_repository.upsert_goal(
        GoalRecord(
            id="goal-stale",
            title="Old goal",
            status="active",
            created_at=old_timestamp,
            updated_at=old_timestamp,
        ),
    )
    task_repository.upsert_task(
        TaskRecord(
            id="task-stale",
            goal_id="goal-stale",
            title="Old task",
            task_type="analysis",
            status="waiting",
            owner_agent_id="stale-agent",
            created_at=old_timestamp,
            updated_at=old_timestamp,
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-stale",
            runtime_status="active",
            current_phase="waiting",
            last_owner_agent_id="stale-agent",
            updated_at=old_timestamp,
        ),
    )

    service = StateReportingService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        goal_repository=goal_repository,
        decision_request_repository=decision_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
    )

    daily = service.get_report(window="daily")
    assert daily.task_count == 0
    assert "goal_count" not in daily.model_dump(mode="json")
    assert daily.agent_count == 0
    assert daily.task_status_counts == {}
    assert daily.goal_status_counts == {}

    overview = service.get_performance_overview(window="daily")
    assert overview["task_status_counts"] == {}
    assert overview["goal_status_counts"] == {}
    assert overview["agent_breakdown"] == []
    metric_map = {metric["key"]: metric for metric in overview["metrics"]}
    assert metric_map["active_task_load"]["value"] == 0.0
