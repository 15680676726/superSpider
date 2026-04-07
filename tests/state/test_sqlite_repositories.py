# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from copaw.state import (
    AgentReportService,
    AgentReportRecord,
    AgentProfileOverrideRecord,
    AgentRuntimeRecord,
    AssignmentRecord,
    BacklogItemRecord,
    CapabilityOverrideRecord,
    DecisionRequestRecord,
    ExecutionRoutineRecord,
    GoalRecord,
    GoalOverrideRecord,
    HumanAssistTaskRecord,
    IndustryInstanceRecord,
    KnowledgeChunkRecord,
    MediaAnalysisRecord,
    MemoryEntityViewRecord,
    MemoryFactIndexRecord,
    MemoryOpinionViewRecord,
    MemoryReflectionRunRecord,
    OperatingCycleRecord,
    OperatingLaneRecord,
    PredictionCaseRecord,
    PredictionRecommendationRecord,
    PredictionReviewRecord,
    RuntimeFrameRecord,
    RoutineRunRecord,
    SQLiteStateStore,
    ScheduleRecord,
    TaskRecord,
    TaskRuntimeRecord,
    WorkContextRecord,
)
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteAgentProfileOverrideRepository,
    SqliteAgentRuntimeRepository,
    SqliteAssignmentRepository,
    SqliteBacklogItemRepository,
    SqliteCapabilityOverrideRepository,
    SqliteDecisionRequestRepository,
    SqliteExecutionRoutineRepository,
    SqliteGoalRepository,
    SqliteGoalOverrideRepository,
    SqliteHumanAssistTaskRepository,
    SqliteIndustryInstanceRepository,
    SqliteKnowledgeChunkRepository,
    SqliteMediaAnalysisRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteOperatingCycleRepository,
    SqliteOperatingLaneRepository,
    SqlitePredictionCaseRepository,
    SqlitePredictionRecommendationRepository,
    SqlitePredictionReviewRepository,
    SqliteRuntimeFrameRepository,
    SqliteRoutineRunRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
)


def test_sqlite_repositories_crud_round_trip(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    goal_repo = SqliteGoalRepository(store)
    task_repo = SqliteTaskRepository(store)
    runtime_repo = SqliteTaskRuntimeRepository(store)
    frame_repo = SqliteRuntimeFrameRepository(store)
    schedule_repo = SqliteScheduleRepository(store)
    decision_repo = SqliteDecisionRequestRepository(store)

    goal = GoalRecord(
        title="Phase 1 closeout",
        summary="Finalize legacy cleanup and unify the kernel handoff.",
        status="active",
        owner_scope="runtime-center",
    )
    goal_repo.upsert_goal(goal)

    stored_goal = goal_repo.get_goal(goal.id)
    assert stored_goal is not None
    assert stored_goal.status == "active"
    assert [item.id for item in goal_repo.list_goals(status="active")] == [goal.id]

    task = TaskRecord(
        goal_id="goal-bootstrap",
        title="Implement state package",
        summary="Build Phase 1 state foundation.",
        task_type="phase1-refactor",
        owner_agent_id="worker-1",
        current_risk_level="guarded",
    )
    task_repo.upsert_task(task)

    stored_task = task_repo.get_task(task.id)
    assert stored_task is not None
    assert stored_task.id == task.id
    assert stored_task.owner_agent_id == "worker-1"

    updated_task = stored_task.model_copy(
        update={
            "status": "running",
            "updated_at": stored_task.updated_at + timedelta(minutes=5),
        },
    )
    task_repo.upsert_task(updated_task)

    running_tasks = task_repo.list_tasks(status="running")
    assert [item.id for item in running_tasks] == [task.id]

    runtime = TaskRuntimeRecord(
        task_id=task.id,
        runtime_status="active",
        current_phase="bootstrap-store",
        risk_level="guarded",
        last_owner_agent_id="worker-1",
    )
    runtime_repo.upsert_runtime(runtime)

    stored_runtime = runtime_repo.get_runtime(task.id)
    assert stored_runtime is not None
    assert stored_runtime.current_phase == "bootstrap-store"

    newer_runtime = stored_runtime.model_copy(
        update={
            "current_phase": "repository-crud",
            "last_result_summary": "Task/runtime tables verified.",
            "updated_at": stored_runtime.updated_at + timedelta(minutes=10),
        },
    )
    runtime_repo.upsert_runtime(newer_runtime)

    runtimes = runtime_repo.list_runtimes(runtime_status="active")
    assert [item.task_id for item in runtimes] == [task.id]
    assert runtimes[0].current_phase == "repository-crud"

    first_frame = RuntimeFrameRecord(
        task_id=task.id,
        goal_summary="Phase 1 refactor",
        owner_agent_id="worker-1",
        current_phase="bootstrap-store",
        current_risk_level="guarded",
        environment_summary="temp sqlite db",
        evidence_summary="initial snapshot",
    )
    second_frame = RuntimeFrameRecord(
        task_id=task.id,
        goal_summary="Phase 1 refactor",
        owner_agent_id="worker-1",
        current_phase="repository-crud",
        current_risk_level="guarded",
        environment_summary="temp sqlite db",
        evidence_summary="post-runtime update",
        created_at=first_frame.created_at + timedelta(minutes=1),
    )
    frame_repo.append_frame(first_frame)
    frame_repo.append_frame(second_frame)

    latest_frame = frame_repo.get_frame(second_frame.id)
    assert latest_frame is not None
    assert latest_frame.evidence_summary == "post-runtime update"

    frames = frame_repo.list_frames(task.id)
    assert [item.id for item in frames] == [second_frame.id, first_frame.id]

    schedule = ScheduleRecord(
        id="job-1",
        title="Morning heartbeat",
        cron="0 9 * * 1",
        timezone="UTC",
        status="scheduled",
        enabled=True,
        task_type="text",
        target_channel="console",
        target_user_id="worker-1",
        target_session_id="cron:job-1",
        source_ref="legacy:/cron",
    )
    schedule_repo.upsert_schedule(schedule)

    stored_schedule = schedule_repo.get_schedule("job-1")
    assert stored_schedule is not None
    assert stored_schedule.cron == "0 9 * * 1"

    decision = DecisionRequestRecord(
        task_id=task.id,
        decision_type="guarded-action",
        risk_level="guarded",
        summary="Approve guarded file update",
        requested_by="worker-1",
    )
    decision_repo.upsert_decision_request(decision)

    decisions = decision_repo.list_decision_requests(task_id=task.id)
    assert [item.id for item in decisions] == [decision.id]

    assert task_repo.delete_task(task.id) is True
    assert task_repo.get_task(task.id) is None
    assert runtime_repo.get_runtime(task.id) is None
    assert frame_repo.list_frames(task.id) == []
    assert decision_repo.list_decision_requests(task_id=task.id) == []
    assert goal_repo.delete_goal(goal.id) is True
    assert goal_repo.get_goal(goal.id) is None


def test_sqlite_human_assist_task_repository_round_trip(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteHumanAssistTaskRepository(store)

    issued_at = datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc)
    record = HumanAssistTaskRecord(
        id="human-assist-1",
        industry_instance_id="industry-1",
        assignment_id="assignment-1",
        task_id="task-1",
        chat_thread_id="industry-chat:industry-1:execution-core",
        title="上传回执截图",
        summary="系统缺少宿主侧完成证明。",
        task_type="evidence-submit",
        reason_code="blocked-by-proof",
        reason_summary="需要宿主补充付款回执。",
        required_action="请在聊天里上传回执截图并回复已完成。",
        submission_mode="chat-message",
        acceptance_mode="evidence_verified",
        acceptance_spec={
            "version": "v1",
            "hard_anchors": ["receipt"],
            "result_anchors": ["uploaded"],
            "pass_rule": "all-required",
        },
        resume_checkpoint_ref="checkpoint:receipt-upload",
        status="issued",
        reward_preview={"协作值": 2, "同调经验": 1},
        block_evidence_refs=["evidence-block-1"],
        issued_at=issued_at,
        created_at=issued_at,
        updated_at=issued_at,
    )

    repository.upsert_task(record)

    stored = repository.get_task(record.id)
    assert stored is not None
    assert stored.chat_thread_id == "industry-chat:industry-1:execution-core"
    assert stored.acceptance_spec["result_anchors"] == ["uploaded"]
    assert stored.reward_preview["协作值"] == 2

    updated = stored.model_copy(
        update={
            "status": "submitted",
            "submission_text": "我已经上传回执了",
            "submission_evidence_refs": ["media-analysis-1"],
            "submission_payload": {
                "media_analysis_ids": ["media-analysis-1"],
                "anchors": ["receipt", "uploaded"],
            },
            "updated_at": issued_at + timedelta(minutes=3),
        },
    )
    repository.upsert_task(updated)

    listed = repository.list_tasks(
        chat_thread_id="industry-chat:industry-1:execution-core",
        status="submitted",
    )
    assert [item.id for item in listed] == [record.id]
    assert listed[0].submission_payload["anchors"] == ["receipt", "uploaded"]

    by_assignment = repository.list_tasks(assignment_id="assignment-1")
    assert [item.id for item in by_assignment] == [record.id]

    assert repository.delete_task(record.id) is True
    assert repository.get_task(record.id) is None


def test_sqlite_work_context_repository_round_trip(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    context_repo = SqliteWorkContextRepository(store)
    task_repo = SqliteTaskRepository(store)
    report_repo = SqliteAgentReportRepository(store)
    industry_repo = SqliteIndustryInstanceRepository(store)

    industry_repo.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-a",
            label="Industry A",
            summary="Work context test instance.",
            owner_scope="sales",
            status="active",
        ),
    )

    context = WorkContextRecord(
        id="ctx-customer-a",
        title="Customer A onboarding",
        summary="Track the ongoing onboarding thread.",
        context_type="customer-thread",
        status="active",
        context_key="control-thread:customer-a",
        owner_scope="sales",
        owner_agent_id="agent-sales-1",
        industry_instance_id="industry-a",
        primary_thread_id="agent-chat:agent-sales-1:customer-a",
        source_kind="control-thread",
        source_ref="customer-a",
    )
    context_repo.upsert_context(context)

    stored_context = context_repo.get_context(context.id)
    assert stored_context is not None
    assert stored_context.context_key == "control-thread:customer-a"
    assert context_repo.get_by_context_key("control-thread:customer-a") is not None

    task = TaskRecord(
        id="task-work-context",
        title="Prepare onboarding plan",
        task_type="system:dispatch_query",
        status="running",
        owner_agent_id="agent-sales-1",
        work_context_id=context.id,
    )
    task_repo.upsert_task(task)

    stored_task = task_repo.get_task(task.id)
    assert stored_task is not None
    assert stored_task.work_context_id == context.id
    assert [item.id for item in task_repo.list_tasks(work_context_id=context.id)] == [task.id]

    report = AgentReportRecord(
        id="report-work-context",
        industry_instance_id="industry-a",
        task_id=task.id,
        work_context_id=context.id,
        headline="Onboarding updated",
        summary="Captured the latest onboarding blockers.",
        owner_agent_id="agent-sales-1",
    )
    report_repo.upsert_report(report)

    stored_report = report_repo.get_report(report.id)
    assert stored_report is not None
    assert stored_report.work_context_id == context.id
    assert [item.id for item in report_repo.list_reports(work_context_id=context.id)] == [
        report.id
    ]


def test_sqlite_agent_report_repository_persists_cognitive_fields(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    industry_repo = SqliteIndustryInstanceRepository(store)
    report_repo = SqliteAgentReportRepository(store)
    industry_repo.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-cognitive",
            label="Cognitive Industry",
            owner_scope="industry",
        ),
    )

    report = AgentReportRecord(
        id="report-cognitive-1",
        industry_instance_id="industry-cognitive",
        owner_agent_id="agent-cognitive",
        owner_role_id="researcher",
        headline="Cognitive report ready",
        summary="Collected strong but incomplete evidence.",
        findings=["Traffic conversion dropped after onboarding step 2."],
        uncertainties=["No root-cause evidence for mobile users yet."],
        recommendation="Run a focused mobile onboarding audit.",
        needs_followup=True,
        followup_reason="Missing mobile funnel evidence for decision closure.",
    )
    report_repo.upsert_report(report)

    stored_report = report_repo.get_report(report.id)
    assert stored_report is not None
    assert stored_report.findings == ["Traffic conversion dropped after onboarding step 2."]
    assert stored_report.uncertainties == ["No root-cause evidence for mobile users yet."]
    assert stored_report.recommendation == "Run a focused mobile onboarding audit."
    assert stored_report.needs_followup is True
    assert (
        stored_report.followup_reason
        == "Missing mobile funnel evidence for decision closure."
    )

    listed_reports = report_repo.list_reports(industry_instance_id="industry-cognitive")
    assert [item.id for item in listed_reports] == [report.id]
    assert listed_reports[0].findings == stored_report.findings
    assert listed_reports[0].uncertainties == stored_report.uncertainties
    assert listed_reports[0].recommendation == stored_report.recommendation
    assert listed_reports[0].needs_followup is True
    assert listed_reports[0].followup_reason == stored_report.followup_reason


def test_agent_report_service_materializes_safe_cognitive_defaults(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    industry_repo = SqliteIndustryInstanceRepository(store)
    report_repo = SqliteAgentReportRepository(store)
    report_service = AgentReportService(repository=report_repo)
    industry_repo.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-cognitive",
            label="Cognitive Industry",
            owner_scope="industry",
        ),
    )

    task = TaskRecord(
        id="task-cognitive-defaults",
        title="Recover API credential chain",
        summary="Diagnose the latest credential failure and report back.",
        task_type="system:dispatch_query",
        status="failed",
        industry_instance_id="industry-cognitive",
        current_risk_level="guarded",
    )
    runtime = TaskRuntimeRecord(
        task_id=task.id,
        runtime_status="terminated",
        current_phase="failed",
        risk_level="guarded",
        last_result_summary="Observed repeated credential failures during runtime.",
        last_error_summary="Credential refresh is required before retry.",
    )

    report = report_service.record_task_terminal_report(
        task=task,
        runtime=runtime,
        assignment=None,
        evidence_ids=["evidence-cognitive-1"],
        decision_ids=["decision-cognitive-1"],
    )
    assert report is not None
    assert report.findings == [
        "Observed repeated credential failures during runtime.",
    ]
    assert report.uncertainties == ["Credential refresh is required before retry."]
    assert report.recommendation is None
    assert report.needs_followup is True
    assert report.followup_reason == "Credential refresh is required before retry."

    stored_report = report_repo.get_report(report.id)
    assert stored_report is not None
    assert stored_report.findings == report.findings
    assert stored_report.uncertainties == report.uncertainties
    assert stored_report.recommendation is None
    assert stored_report.needs_followup is True
    assert stored_report.followup_reason == report.followup_reason


def test_agent_report_service_prefers_task_status_for_terminality(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    industry_repo = SqliteIndustryInstanceRepository(store)
    report_repo = SqliteAgentReportRepository(store)
    report_service = AgentReportService(repository=report_repo)
    industry_repo.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-terminal",
            label="Terminal Industry",
            owner_scope="industry",
        ),
    )

    task = TaskRecord(
        id="task-terminal-source",
        title="Close onboarding issue",
        summary="Finalize the onboarding closure report.",
        task_type="system:dispatch_query",
        status="completed",
        industry_instance_id="industry-terminal",
    )
    runtime = TaskRuntimeRecord(
        task_id=task.id,
        runtime_status="active",
        current_phase="running",
        last_result_summary="Onboarding closure complete.",
    )

    report = report_service.record_task_terminal_report(
        task=task,
        runtime=runtime,
        assignment=None,
        evidence_ids=[],
        decision_ids=[],
    )

    assert report is not None
    assert report.result == "completed"
    assert report.headline == "Close onboarding issue completed"


def test_agent_report_service_does_not_carry_stale_semantic_fields(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    industry_repo = SqliteIndustryInstanceRepository(store)
    report_repo = SqliteAgentReportRepository(store)
    report_service = AgentReportService(repository=report_repo)
    industry_repo.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-stale",
            label="Stale Industry",
            owner_scope="industry",
        ),
    )

    task = TaskRecord(
        id="task-stale",
        title="Compile evidence pack",
        summary="Compile evidence and return final status.",
        task_type="system:dispatch_query",
        status="completed",
        industry_instance_id="industry-stale",
    )
    initial_runtime = TaskRuntimeRecord(
        task_id=task.id,
        runtime_status="terminated",
        current_phase="completed",
        last_result_summary="Initial run completed with one evidence pack.",
    )
    initial = report_service.record_task_terminal_report(
        task=task,
        runtime=initial_runtime,
        assignment=None,
        evidence_ids=[],
        decision_ids=[],
    )
    assert initial is not None
    stale_seed = initial.model_copy(
        update={
            "findings": ["stale finding"],
            "uncertainties": ["stale uncertainty"],
            "recommendation": "stale recommendation",
            "needs_followup": True,
            "followup_reason": "stale reason",
        },
    )
    report_repo.upsert_report(stale_seed)

    no_fact_runtime = TaskRuntimeRecord(
        task_id=task.id,
        runtime_status="terminated",
        current_phase="completed",
        last_result_summary=None,
        last_error_summary=None,
    )
    refreshed = report_service.record_task_terminal_report(
        task=task,
        runtime=no_fact_runtime,
        assignment=None,
        evidence_ids=[],
        decision_ids=[],
    )
    assert refreshed is not None
    assert refreshed.findings == []
    assert refreshed.uncertainties == []
    assert refreshed.recommendation is None
    assert refreshed.needs_followup is False
    assert refreshed.followup_reason is None


def test_sqlite_agent_report_migration_adds_cognitive_fields_with_defaults(tmp_path) -> None:
    db_path = tmp_path / "legacy-state.db"
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE agent_reports (
                id TEXT PRIMARY KEY,
                industry_instance_id TEXT NOT NULL,
                cycle_id TEXT,
                assignment_id TEXT,
                goal_id TEXT,
                task_id TEXT,
                owner_agent_id TEXT,
                owner_role_id TEXT,
                report_kind TEXT NOT NULL DEFAULT 'task-terminal',
                headline TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'recorded',
                result TEXT,
                risk_level TEXT NOT NULL DEFAULT 'auto',
                evidence_ids_json TEXT NOT NULL DEFAULT '[]',
                decision_ids_json TEXT NOT NULL DEFAULT '[]',
                processed INTEGER NOT NULL DEFAULT 0,
                processed_at TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO agent_reports (
                id,
                industry_instance_id,
                headline,
                summary,
                status,
                result,
                risk_level,
                evidence_ids_json,
                decision_ids_json,
                processed,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-report-1",
                "industry-legacy",
                "Legacy report",
                "Legacy summary",
                "recorded",
                "completed",
                "auto",
                "[]",
                "[]",
                0,
                "{}",
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    store = SQLiteStateStore(db_path)
    report_repo = SqliteAgentReportRepository(store)
    with store.connection() as migrated_conn:
        column_names = {
            str(row["name"])
            for row in migrated_conn.execute("PRAGMA table_info(agent_reports)").fetchall()
        }
    assert {
        "findings_json",
        "uncertainties_json",
        "recommendation",
        "needs_followup",
        "followup_reason",
    }.issubset(column_names)

    stored = report_repo.get_report("legacy-report-1")
    assert stored is not None
    assert stored.findings == []
    assert stored.uncertainties == []
    assert stored.recommendation is None
    assert stored.needs_followup is False
    assert stored.followup_reason is None

def test_sqlite_repositories_support_activity_and_id_filters(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    goal_repo = SqliteGoalRepository(store)
    task_repo = SqliteTaskRepository(store)
    runtime_repo = SqliteTaskRuntimeRepository(store)
    decision_repo = SqliteDecisionRequestRepository(store)
    prediction_case_repo = SqlitePredictionCaseRepository(store)
    prediction_recommendation_repo = SqlitePredictionRecommendationRepository(store)
    prediction_review_repo = SqlitePredictionReviewRepository(store)

    old_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    recent_time = datetime(2026, 1, 10, tzinfo=timezone.utc)

    old_goal = GoalRecord(
        id="goal-old",
        title="Old goal",
        status="active",
        created_at=old_time,
        updated_at=old_time,
    )
    recent_goal = GoalRecord(
        id="goal-recent",
        title="Recent goal",
        status="active",
        created_at=recent_time,
        updated_at=recent_time,
    )
    goal_repo.upsert_goal(old_goal)
    goal_repo.upsert_goal(recent_goal)

    old_task = TaskRecord(
        id="task-old",
        goal_id=old_goal.id,
        title="Old task",
        task_type="analysis",
        owner_agent_id="agent-old",
        created_at=old_time,
        updated_at=old_time,
    )
    recent_task = TaskRecord(
        id="task-recent",
        goal_id=recent_goal.id,
        title="Recent task",
        task_type="system:apply_role",
        owner_agent_id="agent-recent",
        acceptance_criteria='{"agent_id": "agent-recent"}',
        created_at=recent_time,
        updated_at=recent_time,
    )
    child_task = TaskRecord(
        id="task-child",
        goal_id=recent_goal.id,
        parent_task_id=recent_task.id,
        title="Child task",
        task_type="analysis",
        owner_agent_id="child-agent",
        created_at=recent_time,
        updated_at=recent_time,
    )
    task_repo.upsert_task(old_task)
    task_repo.upsert_task(recent_task)
    task_repo.upsert_task(child_task)

    old_runtime = TaskRuntimeRecord(
        task_id=old_task.id,
        runtime_status="active",
        current_phase="old",
        last_owner_agent_id="agent-old",
        updated_at=old_time,
    )
    recent_runtime = TaskRuntimeRecord(
        task_id=recent_task.id,
        runtime_status="active",
        current_phase="recent",
        last_owner_agent_id="agent-recent",
        updated_at=recent_time,
    )
    runtime_repo.upsert_runtime(old_runtime)
    runtime_repo.upsert_runtime(recent_runtime)

    old_decision = DecisionRequestRecord(
        id="decision-old",
        task_id=old_task.id,
        decision_type="guarded-action",
        summary="Old decision",
        requested_by="agent-old",
        created_at=old_time,
    )
    recent_decision = DecisionRequestRecord(
        id="decision-recent",
        task_id=recent_task.id,
        decision_type="guarded-action",
        summary="Recent decision",
        requested_by="agent-recent",
        created_at=recent_time,
    )
    decision_repo.upsert_decision_request(old_decision)
    decision_repo.upsert_decision_request(recent_decision)

    old_case = PredictionCaseRecord(
        case_id="case-old",
        title="Old case",
        owner_scope="ops",
        owner_agent_id="agent-old",
        industry_instance_id="industry-old",
        created_at=old_time,
        updated_at=old_time,
    )
    recent_case = PredictionCaseRecord(
        case_id="case-recent",
        title="Recent case",
        owner_scope="ops",
        owner_agent_id="agent-recent",
        industry_instance_id="industry-recent",
        created_at=recent_time,
        updated_at=recent_time,
    )
    prediction_case_repo.upsert_case(old_case)
    prediction_case_repo.upsert_case(recent_case)

    old_recommendation = PredictionRecommendationRecord(
        recommendation_id="rec-old",
        case_id=old_case.case_id,
        title="Old recommendation",
        target_agent_id="agent-old",
        created_at=old_time,
        updated_at=old_time,
    )
    recent_recommendation = PredictionRecommendationRecord(
        recommendation_id="rec-recent",
        case_id=recent_case.case_id,
        title="Recent recommendation",
        target_agent_id="agent-recent",
        created_at=recent_time,
        updated_at=recent_time,
    )
    prediction_recommendation_repo.upsert_recommendation(old_recommendation)
    prediction_recommendation_repo.upsert_recommendation(recent_recommendation)

    old_review = PredictionReviewRecord(
        review_id="review-old",
        case_id=old_case.case_id,
        recommendation_id=old_recommendation.recommendation_id,
        created_at=old_time,
        updated_at=old_time,
    )
    recent_review = PredictionReviewRecord(
        review_id="review-recent",
        case_id=recent_case.case_id,
        recommendation_id=recent_recommendation.recommendation_id,
        created_at=recent_time,
        updated_at=recent_time,
    )
    prediction_review_repo.upsert_review(old_review)
    prediction_review_repo.upsert_review(recent_review)

    since = recent_time - timedelta(days=1)

    assert [goal.id for goal in goal_repo.list_goals(activity_since=since)] == [
        recent_goal.id,
    ]
    assert [goal.id for goal in goal_repo.list_goals(goal_ids=[old_goal.id])] == [
        old_goal.id,
    ]

    assert [task.id for task in task_repo.list_tasks(activity_since=since)] == [
        recent_task.id,
        child_task.id,
    ]
    assert [task.id for task in task_repo.list_tasks(task_ids=[old_task.id])] == [
        old_task.id,
    ]
    assert [
        task.id
        for task in task_repo.list_tasks(owner_agent_ids=["agent-recent"])
    ] == [recent_task.id]
    assert [
        task.id for task in task_repo.list_tasks(parent_task_id=recent_task.id)
    ] == [child_task.id]
    assert [
        task.id for task in task_repo.list_tasks(task_type="system:apply_role")
    ] == [recent_task.id]
    assert [
        task.id
        for task in task_repo.list_tasks(acceptance_criteria_like="agent-recent")
    ] == [recent_task.id]

    assert [
        runtime.task_id
        for runtime in runtime_repo.list_runtimes(updated_since=since)
    ] == [recent_runtime.task_id]
    assert [
        runtime.task_id
        for runtime in runtime_repo.list_runtimes(last_owner_agent_ids=["agent-old"])
    ] == [old_runtime.task_id]

    assert [
        decision.id
        for decision in decision_repo.list_decision_requests(created_since=since)
    ] == [recent_decision.id]
    assert [
        decision.id
        for decision in decision_repo.list_decision_requests(task_ids=[old_task.id])
    ] == [old_decision.id]

    assert [
        item.case_id
        for item in prediction_case_repo.list_cases(activity_since=since)
    ] == [recent_case.case_id]
    assert [
        item.case_id
        for item in prediction_case_repo.list_cases(owner_agent_id="agent-old")
    ] == [old_case.case_id]
    assert [
        item.case_id
        for item in prediction_case_repo.list_cases(case_ids=[recent_case.case_id])
    ] == [recent_case.case_id]

    assert [
        item.recommendation_id
        for item in prediction_recommendation_repo.list_recommendations(
            case_ids=[recent_case.case_id],
        )
    ] == [recent_recommendation.recommendation_id]
    assert [
        item.recommendation_id
        for item in prediction_recommendation_repo.list_recommendations(
            target_agent_id="agent-old",
        )
    ] == [old_recommendation.recommendation_id]
    assert [
        item.recommendation_id
        for item in prediction_recommendation_repo.list_recommendations(
            activity_since=since,
        )
    ] == [recent_recommendation.recommendation_id]

    assert [
        item.review_id
        for item in prediction_review_repo.list_reviews(case_ids=[recent_case.case_id])
    ] == [recent_review.review_id]
    assert [
        item.review_id
        for item in prediction_review_repo.list_reviews(
            recommendation_id=old_recommendation.recommendation_id,
        )
    ] == [old_review.review_id]
    assert [
        item.review_id
        for item in prediction_review_repo.list_reviews(activity_since=since)
    ] == [recent_review.review_id]


def test_sqlite_repositories_support_media_analysis_records(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    media_repo = SqliteMediaAnalysisRepository(store)

    created_at = datetime(2026, 3, 19, tzinfo=timezone.utc)
    first = MediaAnalysisRecord(
        analysis_id="media-analysis-1",
        industry_instance_id="industry-1",
        thread_id="industry-chat:industry-1:execution-core",
        work_context_id="ctx-industry-1",
        entry_point="chat",
        purpose="chat-answer",
        source_kind="link",
        source_ref="https://example.com/demo",
        source_hash="sha1-demo",
        declared_media_type="article",
        detected_media_type="article",
        analysis_mode="standard",
        status="completed",
        title="Demo market brief",
        url="https://example.com/demo",
        mime_type="text/html",
        asset_artifact_ids=["artifact-1"],
        derived_artifact_ids=["artifact-2"],
        transcript_artifact_id="artifact-transcript",
        structured_summary={
            "summary": "Demo material summary",
            "key_points": ["point-1", "point-2"],
        },
        timeline_summary=[{"at": "00:00", "note": "open"}],
        entities=["entity-1"],
        claims=["claim-1"],
        recommended_actions=["action-1"],
        warnings=["warning-1"],
        knowledge_document_ids=["knowledge-1"],
        evidence_ids=["evidence-1"],
        strategy_writeback_status="written",
        backlog_writeback_status="queued",
        metadata={"source_label": "demo"},
        created_at=created_at,
        updated_at=created_at,
    )
    second = MediaAnalysisRecord(
        analysis_id="media-analysis-2",
        industry_instance_id="industry-2",
        thread_id="industry-chat:industry-2:execution-core",
        entry_point="industry-preview",
        purpose="draft-enrichment",
        source_kind="upload",
        detected_media_type="document",
        analysis_mode="standard",
        status="failed",
        title="Draft attachment",
        filename="brief.pdf",
        error_message="parse failed",
        created_at=created_at + timedelta(minutes=1),
        updated_at=created_at + timedelta(minutes=1),
    )

    media_repo.upsert_analysis(first)
    media_repo.upsert_analysis(second)

    stored_first = media_repo.get_analysis(first.analysis_id)
    assert stored_first is not None
    assert stored_first.structured_summary["summary"] == "Demo material summary"
    assert stored_first.timeline_summary == [{"at": "00:00", "note": "open"}]
    assert stored_first.asset_artifact_ids == ["artifact-1"]
    assert stored_first.metadata == {"source_label": "demo"}
    assert stored_first.work_context_id == "ctx-industry-1"

    by_thread = media_repo.list_analyses(thread_id=first.thread_id)
    assert [item.analysis_id for item in by_thread] == [first.analysis_id]

    by_work_context = media_repo.list_analyses(work_context_id="ctx-industry-1")
    assert [item.analysis_id for item in by_work_context] == [first.analysis_id]

    by_entry = media_repo.list_analyses(entry_point="industry-preview")
    assert [item.analysis_id for item in by_entry] == [second.analysis_id]

    by_status = media_repo.list_analyses(status="completed")
    assert [item.analysis_id for item in by_status] == [first.analysis_id]

    updated_first = first.model_copy(
        update={
            "title": "Updated demo market brief",
            "warnings": ["warning-1", "warning-2"],
            "updated_at": created_at + timedelta(minutes=2),
        },
    )
    media_repo.upsert_analysis(updated_first)

    stored_updated = media_repo.get_analysis(first.analysis_id)
    assert stored_updated is not None
    assert stored_updated.title == "Updated demo market brief"
    assert stored_updated.warnings == ["warning-1", "warning-2"]

    limited = media_repo.list_analyses(limit=1)
    assert [item.analysis_id for item in limited] == [first.analysis_id]

    assert media_repo.delete_analysis(second.analysis_id) is True
    assert media_repo.get_analysis(second.analysis_id) is None


def test_sqlite_main_brain_repositories_round_trip(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    industry_repo = SqliteIndustryInstanceRepository(store)
    lane_repo = SqliteOperatingLaneRepository(store)
    backlog_repo = SqliteBacklogItemRepository(store)
    cycle_repo = SqliteOperatingCycleRepository(store)
    assignment_repo = SqliteAssignmentRepository(store)
    report_repo = SqliteAgentReportRepository(store)

    industry_repo.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-1",
            owner_scope="industry-1",
            label="Industry 1",
            summary="Main-brain repository round trip",
            status="active",
            profile_payload={"industry": "Test"},
            team_payload={"label": "Test"},
        ),
    )

    lane = OperatingLaneRecord(
        id="lane-growth",
        industry_instance_id="industry-1",
        lane_key="growth",
        title="Growth lane",
        summary="Own acquisition experiments",
        owner_agent_id="agent-growth",
        owner_role_id="researcher",
        priority=5,
    )
    lane_repo.upsert_lane(lane)

    backlog_item = BacklogItemRecord(
        id="backlog-growth-1",
        industry_instance_id="industry-1",
        lane_id=lane.id,
        title="Review new demand signal",
        summary="Check whether the new signal deserves a full cycle.",
        status="open",
        priority=4,
        source_kind="operator",
        source_ref="chat-writeback:signal-1",
    )
    backlog_repo.upsert_item(backlog_item)

    cycle = OperatingCycleRecord(
        id="cycle-1",
        industry_instance_id="industry-1",
        cycle_kind="daily",
        title="Daily operating cycle",
        status="active",
        focus_lane_ids=[lane.id],
        backlog_item_ids=[backlog_item.id],
    )
    cycle_repo.upsert_cycle(cycle)

    assignment = AssignmentRecord(
        id="assignment-1",
        industry_instance_id="industry-1",
        cycle_id=cycle.id,
        lane_id=lane.id,
        backlog_item_id=backlog_item.id,
        goal_id="goal-1",
        task_id="task-1",
        owner_agent_id="agent-growth",
        owner_role_id="researcher",
        title="Investigate the signal",
        summary="Collect evidence and report back.",
        status="running",
        report_back_mode="summary",
    )
    assignment_repo.upsert_assignment(assignment)

    report = AgentReportRecord(
        id="report-1",
        industry_instance_id="industry-1",
        cycle_id=cycle.id,
        assignment_id=assignment.id,
        goal_id="goal-1",
        task_id="task-1",
        lane_id=lane.id,
        owner_agent_id="agent-growth",
        owner_role_id="researcher",
        headline="Signal reviewed",
        summary="The signal is valid and should move forward.",
        status="recorded",
        result="completed",
        processed=False,
        evidence_ids=["evidence-1"],
        decision_ids=["decision-1"],
    )
    report_repo.upsert_report(report)

    stored_lane = lane_repo.get_lane(lane.id)
    assert stored_lane is not None
    assert stored_lane.owner_agent_id == "agent-growth"

    stored_backlog = backlog_repo.get_item(backlog_item.id)
    assert stored_backlog is not None
    assert stored_backlog.status == "open"

    stored_cycle = cycle_repo.get_cycle(cycle.id)
    assert stored_cycle is not None
    assert stored_cycle.focus_lane_ids == [lane.id]

    stored_assignment = assignment_repo.get_assignment(assignment.id)
    assert stored_assignment is not None
    assert stored_assignment.task_id == "task-1"

    stored_report = report_repo.get_report(report.id)
    assert stored_report is not None
    assert stored_report.lane_id == lane.id
    assert stored_report.evidence_ids == ["evidence-1"]
    assert stored_report.decision_ids == ["decision-1"]

    assert [item.id for item in lane_repo.list_lanes(industry_instance_id="industry-1")] == [lane.id]
    assert [item.id for item in backlog_repo.list_items(industry_instance_id="industry-1")] == [backlog_item.id]
    assert [item.id for item in cycle_repo.list_cycles(industry_instance_id="industry-1")] == [cycle.id]
    assert [item.id for item in assignment_repo.list_assignments(industry_instance_id="industry-1")] == [assignment.id]
    assert [item.id for item in report_repo.list_reports(industry_instance_id="industry-1")] == [report.id]

    assert report_repo.delete_report(report.id) is True
    assert assignment_repo.delete_assignment(assignment.id) is True
    assert cycle_repo.delete_cycle(cycle.id) is True
    assert backlog_repo.delete_item(backlog_item.id) is True
    assert lane_repo.delete_lane(lane.id) is True


def test_sqlite_repositories_support_routines_and_runs(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    routine_repo = SqliteExecutionRoutineRepository(store)
    run_repo = SqliteRoutineRunRepository(store)

    routine = ExecutionRoutineRecord(
        id="routine-1",
        routine_key="jd-login-capture",
        name="JD Login Capture",
        summary="Replay the fixed JD admin login path.",
        status="active",
        owner_scope="jd-ops",
        owner_agent_id="ops-agent",
        trigger_kind="manual",
        engine_kind="browser",
        environment_kind="browser",
        session_requirements={
            "profile_id": "profile-1",
            "entry_url": "https://example.com/login",
        },
        lock_scope=[{"scope_type": "browser-profile", "scope_value": "profile-1"}],
        action_contract=[
            {"action": "open", "page_id": "page-1", "url": "https://example.com/login"},
            {"action": "click", "page_id": "page-1", "selector": "#submit"},
        ],
        evidence_expectations=["open", "click"],
        source_evidence_ids=["evidence-1"],
        metadata={"fallback_request_context": {"channel": "console"}},
    )
    routine_repo.upsert_routine(routine)

    stored_routine = routine_repo.get_routine(routine.id)
    assert stored_routine is not None
    assert stored_routine.session_requirements["profile_id"] == "profile-1"
    assert stored_routine.action_contract[1]["action"] == "click"

    filtered_routines = routine_repo.list_routines(
        status="active",
        engine_kind="browser",
        owner_agent_id="ops-agent",
    )
    assert [item.id for item in filtered_routines] == [routine.id]

    completed_run = RoutineRunRecord(
        id="routine-run-1",
        routine_id=routine.id,
        source_type="manual",
        status="completed",
        owner_agent_id="ops-agent",
        owner_scope="jd-ops",
        environment_id="env:session:session:browser-local:session-1",
        session_id="session-1",
        lease_ref="session:browser-local:session-1",
        deterministic_result="replay-complete",
        output_summary="Routine replay completed",
        evidence_ids=["evidence-1"],
        metadata={"replay_request_context": {"channel": "console"}},
    )
    failed_run = RoutineRunRecord(
        id="routine-run-2",
        routine_id=routine.id,
        source_type="replay",
        status="failed",
        owner_agent_id="ops-agent",
        failure_class="page-drift",
        fallback_mode="hard-fail",
        output_summary="Selector drift detected",
        metadata={"missing_fallback_context": ["query_preview"]},
    )
    run_repo.upsert_run(completed_run)
    run_repo.upsert_run(failed_run)

    stored_run = run_repo.get_run(completed_run.id)
    assert stored_run is not None
    assert stored_run.deterministic_result == "replay-complete"

    failed_runs = run_repo.list_runs(
        routine_id=routine.id,
        failure_class="page-drift",
    )
    assert [item.id for item in failed_runs] == [failed_run.id]

    all_runs = run_repo.list_runs(routine_id=routine.id)
    assert [item.id for item in all_runs] == [failed_run.id, completed_run.id]

    assert run_repo.delete_run(completed_run.id) is True
    assert run_repo.get_run(completed_run.id) is None
    assert routine_repo.delete_routine(routine.id) is True
    assert routine_repo.get_routine(routine.id) is None


def test_sqlite_repositories_support_memory_vnext_tables(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    fact_repo = SqliteMemoryFactIndexRepository(store)
    entity_repo = SqliteMemoryEntityViewRepository(store)
    opinion_repo = SqliteMemoryOpinionViewRepository(store)
    reflection_repo = SqliteMemoryReflectionRunRepository(store)

    fact = MemoryFactIndexRecord(
        id="memory-index:knowledge_chunk:chunk-1",
        source_type="knowledge_chunk",
        source_ref="chunk-1",
        scope_type="industry",
        scope_id="industry-1",
        owner_agent_id="copaw-agent-runner",
        industry_instance_id="industry-1",
        title="Industry evidence policy",
        summary="Outbound action requires evidence review.",
        content_excerpt="Outbound action requires evidence review.",
        content_text="Outbound action requires evidence review before dispatch.",
        entity_keys=["industry-1", "evidence-review"],
        opinion_keys=["industry-1:requirement:requires"],
        tags=["memory", "policy"],
        role_bindings=["execution-core"],
        evidence_refs=["evidence-1"],
        confidence=0.88,
        quality_score=0.81,
    )
    fact_repo.upsert_entry(fact)
    stored_fact = fact_repo.get_entry(fact.id)
    assert stored_fact is not None
    assert stored_fact.entity_keys == ["industry-1", "evidence-review"]
    assert [item.id for item in fact_repo.list_entries(scope_type="industry", scope_id="industry-1")] == [fact.id]

    entity = MemoryEntityViewRecord(
        entity_id="memory-entity:industry:industry-1:evidence-review",
        entity_key="evidence-review",
        scope_type="industry",
        scope_id="industry-1",
        display_name="Evidence Review",
        summary="Evidence review gates outbound action.",
        confidence=0.84,
        supporting_refs=["chunk-1"],
        related_entities=["industry-1"],
        source_refs=["chunk-1"],
    )
    entity_repo.upsert_view(entity)
    stored_entity = entity_repo.get_view(entity.entity_id)
    assert stored_entity is not None
    assert stored_entity.display_name == "Evidence Review"

    opinion = MemoryOpinionViewRecord(
        opinion_id="memory-opinion:industry:industry-1:requirement",
        subject_key="industry-1",
        scope_type="industry",
        scope_id="industry-1",
        opinion_key="industry-1:requirement:requires",
        stance="requirement",
        summary="Industry requires evidence review before outbound action.",
        confidence=0.86,
        supporting_refs=["chunk-1"],
        entity_keys=["industry-1", "evidence-review"],
        source_refs=["chunk-1"],
    )
    opinion_repo.upsert_view(opinion)
    stored_opinion = opinion_repo.get_view(opinion.opinion_id)
    assert stored_opinion is not None
    assert stored_opinion.stance == "requirement"

    reflection_run = MemoryReflectionRunRecord(
        run_id="reflect-1",
        scope_type="industry",
        scope_id="industry-1",
        trigger_kind="manual",
        status="completed",
        summary="Compiled entity/opinion views.",
        source_refs=["chunk-1"],
        generated_entity_ids=[entity.entity_id],
        generated_opinion_ids=[opinion.opinion_id],
    )
    reflection_repo.upsert_run(reflection_run)
    stored_run = reflection_repo.get_run("reflect-1")
    assert stored_run is not None
    assert stored_run.generated_entity_ids == [entity.entity_id]
    assert stored_run.generated_opinion_ids == [opinion.opinion_id]


def test_sqlite_override_repositories_crud_round_trip(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    capability_repo = SqliteCapabilityOverrideRepository(store)
    agent_repo = SqliteAgentProfileOverrideRepository(store)
    agent_runtime_repo = SqliteAgentRuntimeRepository(store)
    goal_repo = SqliteGoalOverrideRepository(store)
    industry_repo = SqliteIndustryInstanceRepository(store)
    knowledge_repo = SqliteKnowledgeChunkRepository(store)

    capability_override = CapabilityOverrideRecord(
        capability_id="tool:execute_shell_command",
        enabled=False,
        forced_risk_level="confirm",
        reason="Temporarily elevate shell risk",
        source_patch_id="patch-capability",
    )
    capability_repo.upsert_override(capability_override)
    stored_capability = capability_repo.get_override("tool:execute_shell_command")
    assert stored_capability is not None
    assert stored_capability.enabled is False
    assert stored_capability.forced_risk_level == "confirm"
    assert [item.capability_id for item in capability_repo.list_overrides()] == [
        "tool:execute_shell_command",
    ]

    agent_override = AgentProfileOverrideRecord(
        agent_id="ops-agent",
        role_name="operations",
        role_summary="Owns runtime closeout.",
        agent_class="business",
        employment_mode="career",
        activation_mode="persistent",
        suspendable=True,
        reports_to="copaw-agent-runner",
        mission="Tighten the operating loop.",
        current_focus_kind="goal",
        current_focus_id="goal-1",
        current_focus="Launch runtime center",
        industry_instance_id="industry-v1-ops",
        industry_role_id="operations",
        environment_constraints=["workspace draft/edit allowed"],
        evidence_expectations=["closeout summary"],
        capabilities=["system:dispatch_query", "system:dispatch_goal"],
        source_patch_id="patch-agent",
    )
    agent_repo.upsert_override(agent_override)
    stored_agent = agent_repo.get_override("ops-agent")
    assert stored_agent is not None
    assert stored_agent.role_name == "operations"
    assert stored_agent.agent_class == "business"
    assert stored_agent.employment_mode == "career"
    assert stored_agent.suspendable is True
    assert stored_agent.current_focus_kind == "goal"
    assert stored_agent.current_focus_id == "goal-1"
    assert stored_agent.current_focus == "Launch runtime center"
    assert hasattr(stored_agent, "current_goal_id") is False
    assert hasattr(stored_agent, "current_goal") is False
    assert stored_agent.industry_instance_id == "industry-v1-ops"
    assert stored_agent.environment_constraints == ["workspace draft/edit allowed"]
    assert stored_agent.capabilities == [
        "system:dispatch_query",
        "system:dispatch_goal",
    ]
    assert [item.agent_id for item in agent_repo.list_overrides()] == ["ops-agent"]
    agent_runtime = AgentRuntimeRecord(
        agent_id="ops-agent",
        actor_key="industry:ops-agent",
        actor_fingerprint="fp-ops-agent",
        desired_state="active",
        runtime_status="idle",
        employment_mode="career",
        activation_mode="persistent",
        persistent=True,
        industry_instance_id="industry-v1-ops",
        industry_role_id="operations",
    )
    agent_runtime_repo.upsert_runtime(agent_runtime)
    stored_agent_runtime = agent_runtime_repo.get_runtime("ops-agent")
    assert stored_agent_runtime is not None
    assert stored_agent_runtime.employment_mode == "career"
    assert stored_agent_runtime.activation_mode == "persistent"
    assert stored_agent_runtime.persistent is True
    assert [item.agent_id for item in agent_runtime_repo.list_runtimes()] == ["ops-agent"]

    goal_override = GoalOverrideRecord(
        goal_id="goal-1",
        title="Launch runtime center",
        summary="Promote runtime center as the operator cockpit.",
        plan_steps=["wire overview", "verify evidence", "ship closeout"],
        compiler_context={"owner_agent_id": "ops-agent"},
        source_patch_id="patch-goal",
    )
    goal_repo.upsert_override(goal_override)
    stored_goal = goal_repo.get_override("goal-1")
    assert stored_goal is not None
    assert stored_goal.plan_steps == [
        "wire overview",
        "verify evidence",
        "ship closeout",
    ]
    assert stored_goal.compiler_context == {"owner_agent_id": "ops-agent"}
    assert [item.goal_id for item in goal_repo.list_overrides()] == ["goal-1"]

    industry_instance = IndustryInstanceRecord(
        instance_id="industry-v1-ops",
        label="Ops Industry Team",
        summary="Formal industry runtime team.",
        owner_scope="ops",
        status="active",
        profile_payload={"industry": "Operations"},
        team_payload={"team_id": "industry-v1-ops", "agents": []},
        draft_payload={
            "schema_version": "industry-draft-v1",
            "team": {"team_id": "industry-v1-ops", "agents": []},
            "goals": [
                {
                    "goal_id": "ops-closeout",
                    "kind": "operations",
                    "owner_agent_id": "ops-agent",
                    "title": "Close the runtime loop",
                    "summary": "Keep the operations lane closed with evidence.",
                    "plan_steps": ["review", "verify", "close"],
                },
            ],
            "schedules": [],
        },
        agent_ids=["ops-agent"],
    )
    industry_repo.upsert_instance(industry_instance)
    stored_instance = industry_repo.get_instance("industry-v1-ops")
    assert stored_instance is not None
    assert stored_instance.agent_ids == ["ops-agent"]
    assert stored_instance.draft_payload["goals"][0]["goal_id"] == "ops-closeout"
    assert [item.instance_id for item in industry_repo.list_instances()] == [
        "industry-v1-ops",
    ]

    assert capability_repo.delete_override("tool:execute_shell_command") is True
    assert capability_repo.get_override("tool:execute_shell_command") is None
    assert agent_repo.delete_override("ops-agent") is True
    assert agent_repo.get_override("ops-agent") is None
    assert goal_repo.delete_override("goal-1") is True
    assert goal_repo.get_override("goal-1") is None
    assert industry_repo.delete_instance("industry-v1-ops") is True
    assert industry_repo.get_instance("industry-v1-ops") is None

    knowledge_chunk = KnowledgeChunkRecord(
        document_id="knowledge-doc:ops",
        title="Runtime closeout checklist",
        content="Capture evidence, confirm decisions, and summarize risks.",
        summary="Capture evidence, confirm decisions, and summarize risks.",
        source_ref="workspace:CHECKLIST.md",
        chunk_index=0,
        role_bindings=["execution-core", "ops-agent"],
        tags=["runtime", "closeout"],
    )
    knowledge_repo.upsert_chunk(knowledge_chunk)
    stored_chunk = knowledge_repo.get_chunk(knowledge_chunk.id)
    assert stored_chunk is not None
    assert stored_chunk.document_id == "knowledge-doc:ops"
    assert stored_chunk.role_bindings == ["execution-core", "ops-agent"]
    assert stored_chunk.tags == ["runtime", "closeout"]
    assert [item.id for item in knowledge_repo.list_chunks()] == [knowledge_chunk.id]
    assert knowledge_repo.delete_chunk(knowledge_chunk.id) is True
    assert knowledge_repo.get_chunk(knowledge_chunk.id) is None


def test_agent_profile_override_repository_ignores_legacy_goal_columns(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteAgentProfileOverrideRepository(store)

    with store.connection() as conn:
        conn.execute(
            "ALTER TABLE agent_profile_overrides ADD COLUMN current_goal_id TEXT",
        )
        conn.execute(
            "ALTER TABLE agent_profile_overrides ADD COLUMN current_goal TEXT",
        )

    override = AgentProfileOverrideRecord(
        agent_id="legacy-agent",
        role_name="operations",
        role_summary="Legacy override row with retired goal columns.",
        current_focus_kind="goal",
        current_focus_id="goal-live",
        current_focus="Keep current focus projection only.",
    )
    repository.upsert_override(override)

    with store.connection() as conn:
        conn.execute(
            """
            UPDATE agent_profile_overrides
            SET current_goal_id = ?, current_goal = ?
            WHERE agent_id = ?
            """,
            ("goal-legacy", "Legacy goal summary", "legacy-agent"),
        )

    stored = repository.get_override("legacy-agent")
    assert stored is not None
    assert stored.agent_id == "legacy-agent"
    assert stored.current_focus_id == "goal-live"
    assert hasattr(stored, "current_goal_id") is False
    assert hasattr(stored, "current_goal") is False
    assert [item.agent_id for item in repository.list_overrides()] == ["legacy-agent"]
