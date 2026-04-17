# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from copaw.app.crons.models import CronJobState
from copaw.app.startup_recovery import StartupRecoverySummary
from copaw.config.config import HeartbeatConfig
from copaw.kernel import GovernanceService, KernelTask
from copaw.industry import (
    IndustryDraftSchedule,
    IndustryPreviewRequest,
    normalize_industry_profile,
)
from copaw.industry.chat_writeback import build_chat_writeback_plan
from copaw.state import (
    AgentReportRecord,
    HumanAssistTaskService,
    ScheduleRecord,
    SQLiteStateStore,
    WorkflowTemplateRecord,
)
from copaw.state.repositories import (
    SqliteGovernanceControlRepository,
    SqliteHumanAssistTaskRepository,
)

from .industry_api_parts.shared import (
    FakeIndustryDraftGenerator,
    FakeTurnExecutor,
    _build_industry_app,
    bootstrap_schedule_by_role,
)
from .runtime_center_api_parts.shared import (
    FakeAgentProfileService,
    FakeCapabilityService,
    FakeCronManager,
    FakeEnvironmentService,
    FakeEvidenceQueryService,
    FakeGovernanceService,
    FakeIndustryService,
    FakeLearningService,
    FakeRoutineService,
    FakeStateQueryService,
    FakeStrategyMemoryService,
    build_runtime_center_app,
    make_job,
)
from .test_fixed_sop_kernel_api import _FakeEnvironmentService as _FakeFixedSopEnvironmentService
from .test_fixed_sop_kernel_api import _build_app as _build_fixed_sop_app
from .test_fixed_sop_kernel_api import _create_host_binding
from .test_runtime_human_assist_tasks_api import _FakeQueryExecutionService
from .test_workflow_templates_api import (
    FakeWorkflowEnvironmentService,
    _bootstrap_industry,
    _build_workflow_app,
    _desktop_host_preflight_detail,
    _grant_capability_to_agent,
    _industry_role_agent_id,
    _launch_workflow_via_service,
)


def _resolve_initial_materialization(
    app,
    *,
    instance_id: str,
    writeback: dict[str, object],
    backlog_id: str,
    actor: str,
    auto_dispatch_materialized_goals: bool = False,
) -> dict[str, object]:
    materialized_assignment_ids = [
        str(item)
        for item in list(writeback.get("materialized_assignment_ids") or [])
        if str(item)
    ]
    if materialized_assignment_ids:
        started_cycle_id = writeback.get("materialized_cycle_id")
        if not started_cycle_id:
            assignment_record = app.state.assignment_repository.get_assignment(
                materialized_assignment_ids[0],
            )
            started_cycle_id = assignment_record.cycle_id if assignment_record is not None else None
        return {
            "instance_id": instance_id,
            "started_cycle_id": started_cycle_id,
            "created_assignment_ids": materialized_assignment_ids,
            "created_task_ids": [],
            "created_report_ids": [],
            "processed_report_ids": [],
        }

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor=actor,
            force=True,
            backlog_item_ids=[backlog_id],
            auto_dispatch_materialized_goals=auto_dispatch_materialized_goals,
        ),
    )
    return cycle_result["processed_instances"][0]


def test_phase_next_runtime_center_overview_surfaces_main_brain_cockpit_card() -> None:
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.industry_service = FakeIndustryService()
    app.state.governance_service = FakeGovernanceService()
    app.state.routine_service = FakeRoutineService()
    app.state.strategy_memory_service = FakeStrategyMemoryService()

    client = TestClient(app)

    response = client.get("/runtime-center/surface")

    assert response.status_code == 200
    cards = {card["key"]: card for card in response.json()["cards"]}
    assert "main-brain" in cards
    main_brain = cards["main-brain"]
    assert main_brain["status"] == "state-service"
    assert main_brain["count"] == 1
    assert main_brain["entries"]
    entry = main_brain["entries"][0]
    assert entry["meta"]["lane_count"] == 2
    assert entry["meta"]["assignment_count"] == 2
    assert entry["meta"]["report_count"] == 1
    assert entry["meta"]["decision_count"] == 2
    assert entry["meta"]["patch_count"] == 3
    assert entry["meta"]["strategy_id"] == "strategy:industry:industry-v1-ops:copaw-agent-runner"


def test_phase_next_runtime_center_overview_surfaces_routine_degradation_contract() -> None:
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.industry_service = FakeIndustryService()
    app.state.governance_service = FakeGovernanceService()

    class _DegradedRoutineService(FakeRoutineService):
        def get_runtime_center_overview(self, *, limit: int = 5) -> dict[str, object]:
            payload = dict(super().get_runtime_center_overview(limit=limit))
            payload.update(
                {
                    "degraded": 1,
                    "last_fallback": "sidecar-memory-disabled",
                }
            )
            return payload

    app.state.routine_service = _DegradedRoutineService()
    app.state.strategy_memory_service = FakeStrategyMemoryService()

    client = TestClient(app)

    response = client.get("/runtime-center/surface")

    assert response.status_code == 200
    cards = {card["key"]: card for card in response.json()["cards"]}
    routines = cards["routines"]
    assert routines["meta"]["failure_source"] == "sidecar-memory"
    assert "仅依赖规范状态继续运行" in routines["meta"]["remediation_summary"]
    assert "compaction sidecar" in routines["meta"]["blocked_next_step"]


def test_phase_next_industry_long_run_smoke_keeps_followup_focus_and_replan_truth_contract(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["build a stable inspection loop"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]
    strategies = app.state.strategy_memory_service.list_strategies(
        industry_instance_id=instance_id,
        limit=5,
    )
    assert strategies
    assert isinstance(strategies[0].current_focuses, list)

    writeback = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text=(
                "Please publish the customer notice in the browser, "
                "keep the handoff governed, and report back."
            ),
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry-chat:{instance_id}:execution-core",
            channel="console",
            writeback_plan=build_chat_writeback_plan(
                "Please publish the customer notice in the browser, keep the handoff governed, and report back.",
                approved_classifications=["backlog"],
                goal_title="Browser publish handoff",
                goal_summary="Publish the customer notice with governed browser handoff.",
                goal_plan_steps=[
                    "Define the governed browser execution scope.",
                    "Require approval before any external action.",
                    "Write back the result and evidence.",
                ],
            ),
        ),
    )

    assert writeback is not None
    decision_id = writeback.get("decision_request_id")
    backlog_id = writeback["created_backlog_ids"][0]
    if decision_id:
        approved = client.post(
            f"/runtime-center/decisions/{decision_id}/approve",
            json={"resolution": "Approve the governed browser staffing seat.", "execute": True},
        )
        assert approved.status_code == 200

    first_cycle = _resolve_initial_materialization(
        app,
        instance_id=instance_id,
        writeback=writeback,
        backlog_id=backlog_id,
        actor="test:phase-next-smoke-cycle",
        auto_dispatch_materialized_goals=False,
    )
    assignment_id = first_cycle["created_assignment_ids"][0]
    cycle_id = first_cycle["started_cycle_id"]
    assert cycle_id is not None

    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment_id,
        owner_agent_id=writeback["target_owner_agent_id"],
        owner_role_id=writeback["target_industry_role_id"],
        headline="Browser publish handoff failed",
        summary="The browser publish attempt is still blocked by the unresolved platform handoff.",
        status="recorded",
        result="failed",
        findings=["The platform still requires a governed human handoff before publish can continue."],
        recommendation="Resume the staffed browser seat after the human handoff closes.",
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)

    second_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:phase-next-smoke-replan",
            force=True,
        ),
    )
    assert report.id in second_cycle["processed_instances"][0]["processed_report_ids"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.current_cycle is not None
    assert detail.current_cycle["synthesis"]["needs_replan"] is True
    assert "Browser publish handoff failed requires main-brain follow-up." in (
        detail.current_cycle["synthesis"]["replan_reasons"]
    )

    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("source_report_id") == report.id
    )
    assert followup_backlog["metadata"]["supervisor_owner_agent_id"] == "copaw-agent-runner"
    assert followup_backlog["metadata"]["supervisor_industry_role_id"] == "execution-core"

    resumed_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:phase-next-smoke-resume",
            force=True,
            backlog_item_ids=[followup_backlog["backlog_item_id"]],
            auto_dispatch_materialized_goals=False,
        ),
    )
    resumed_assignment_ids = resumed_cycle["processed_instances"][0]["created_assignment_ids"]
    resumed_assignment_id = resumed_assignment_ids[0] if resumed_assignment_ids else None

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    updated_strategies = app.state.strategy_memory_service.list_strategies(
        industry_instance_id=instance_id,
        limit=5,
    )
    assert updated_strategies
    assert isinstance(updated_strategies[0].current_focuses, list)
    assert runtime_payload["execution"]["current_focus_id"] != assignment_id
    assert runtime_payload["main_chain"]["current_focus_id"] != assignment_id
    assert runtime_payload["execution"]["current_focus_id"] in {
        None,
        resumed_assignment_id,
    }
    assert runtime_payload["main_chain"]["current_focus_id"] in {
        None,
        resumed_assignment_id,
    }
    replan_node = next(
        node for node in runtime_payload["main_chain"]["nodes"] if node["node_id"] == "replan"
    )
    assert replan_node["status"] in {"active", "idle"}
    if replan_node["status"] == "active":
        assert replan_node["metrics"]["replan_reason_count"] >= 1


def test_phase_next_industry_long_run_smoke_keeps_handoff_human_assist_and_replan_on_one_control_thread_contract(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["keep the staffed handoff loop stable across resume"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]
    control_thread_id = f"industry-chat:{instance_id}:execution-core"
    environment_ref = f"session:console:industry:{instance_id}"
    work_context_id = "ctx-phase-next-handoff"

    writeback = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text=(
                "Please publish the customer notice in the browser, update the desktop tracker and "
                "document log, keep the handoff governed, and report back."
            ),
            owner_agent_id="copaw-agent-runner",
            session_id=control_thread_id,
            channel="console",
            writeback_plan=build_chat_writeback_plan(
                (
                    "Please publish the customer notice in the browser, update the desktop tracker "
                    "and document log, keep the handoff governed, and report back."
                ),
                approved_classifications=["backlog"],
                goal_title="Multi-surface publish handoff",
                goal_summary="Publish through browser/desktop/document with governed handoff.",
                goal_plan_steps=[
                    "Define the governed multi-surface execution scope.",
                    "Require approval before any external action.",
                    "Write back the result and evidence.",
                ],
            ),
        ),
    )

    assert writeback is not None
    decision_id = writeback.get("decision_request_id")
    backlog_id = writeback["created_backlog_ids"][0]
    if decision_id:
        approved = client.post(
            f"/runtime-center/decisions/{decision_id}/approve",
            json={"resolution": "Approve the governed staffing seat.", "execute": True},
        )
        assert approved.status_code == 200

    first_cycle = _resolve_initial_materialization(
        app,
        instance_id=instance_id,
        writeback=writeback,
        backlog_id=backlog_id,
        actor="test:phase-next-smoke-cycle",
        auto_dispatch_materialized_goals=False,
    )
    assignment_id = first_cycle["created_assignment_ids"][0]
    cycle_id = first_cycle["started_cycle_id"]
    assert cycle_id is not None

    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment_id,
        owner_agent_id=writeback["target_owner_agent_id"],
        owner_role_id=writeback["target_industry_role_id"],
        headline="Multi-surface handoff still blocked",
        summary="Browser, desktop, and document work are still blocked until host handoff returns.",
        status="recorded",
        result="failed",
        findings=["The host handoff checkpoint was not returned yet."],
        recommendation="Resume the staffed seat after the host handoff closes.",
        work_context_id=work_context_id,
        metadata={
            "chat_writeback_requested_surfaces": ["browser", "desktop", "document"],
            "seat_requested_surfaces": ["browser", "desktop", "document"],
            "control_thread_id": control_thread_id,
            "session_id": control_thread_id,
            "environment_ref": environment_ref,
            "recommended_scheduler_action": "handoff",
        },
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)

    second_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:phase-next-smoke-replan",
            force=True,
        ),
    )
    assert report.id in second_cycle["processed_instances"][0]["processed_report_ids"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("source_report_id") == report.id
    )

    human_assist_task_service = HumanAssistTaskService(
        repository=SqliteHumanAssistTaskRepository(app.state.state_store),
        evidence_ledger=app.state.evidence_ledger,
    )
    app.state.human_assist_task_service = human_assist_task_service
    set_human_assist = getattr(app.state.state_query_service, "set_human_assist_task_service", None)
    if callable(set_human_assist):
        set_human_assist(human_assist_task_service)
    app.state.turn_executor = FakeTurnExecutor()
    query_execution_service = _FakeQueryExecutionService()
    app.state.query_execution_service = query_execution_service

    class _MutableEnvironmentService:
        def __init__(self) -> None:
            self.ready = False

        def list_sessions(self, limit=200):
            del limit
            return [SimpleNamespace(session_mount_id=environment_ref)]

        def get_session_detail(self, session_id, limit=20):
            del limit
            assert session_id == environment_ref
            if self.ready:
                return {
                    "host_twin": {
                        "continuity": {"requires_human_return": False},
                        "coordination": {
                            "recommended_scheduler_action": "continue",
                            "candidate_seat_refs": ["env:seat-a", "env:seat-b"],
                            "selected_seat_ref": "env:seat-b",
                            "selected_session_mount_id": "session:seat-b",
                            "seat_selection_policy": "prefer-ready-seat",
                            "contention_forecast": {
                                "severity": "clear",
                                "reason": "canonical runtime switched to the alternate ready seat",
                            },
                        },
                        "legal_recovery": {
                            "path": "continue",
                            "checkpoint_ref": "checkpoint:phase-next-handoff",
                        },
                        "host_twin_summary": {
                            "seat_count": 2,
                            "candidate_seat_refs": ["env:seat-a", "env:seat-b"],
                            "selected_seat_ref": "env:seat-b",
                            "selected_session_mount_id": "session:seat-b",
                            "recommended_scheduler_action": "continue",
                            "legal_recovery_mode": "continue",
                            "blocked_surface_count": 0,
                        },
                    },
                }
            return {
                "host_twin": {
                    "continuity": {"requires_human_return": True},
                    "ownership": {"handoff_owner_ref": "host-owner"},
                    "coordination": {
                        "recommended_scheduler_action": "handoff",
                        "candidate_seat_refs": ["env:seat-a", "env:seat-b"],
                        "selected_seat_ref": "env:seat-a",
                        "selected_session_mount_id": "session:seat-a",
                        "seat_selection_policy": "prefer-ready-seat",
                        "contention_forecast": {
                            "severity": "blocked",
                            "reason": "shared writer scope is still owned by worker-2",
                        },
                    },
                    "legal_recovery": {
                        "path": "handoff",
                        "checkpoint_ref": "checkpoint:phase-next-handoff",
                    },
                    "host_twin_summary": {
                        "seat_count": 2,
                        "candidate_seat_refs": ["env:seat-a", "env:seat-b"],
                        "selected_seat_ref": "env:seat-a",
                        "selected_session_mount_id": "session:seat-a",
                        "recommended_scheduler_action": "handoff",
                        "legal_recovery_mode": "handoff",
                        "blocked_surface_count": 1,
                    },
                },
            }

    environment_service = _MutableEnvironmentService()
    governance = GovernanceService(
        control_repository=SqliteGovernanceControlRepository(
            SQLiteStateStore(tmp_path / "governance.sqlite3"),
        ),
        industry_service=app.state.industry_service,
        human_assist_task_service=human_assist_task_service,
        environment_service=environment_service,
    )

    task_payload = {
        "industry_instance_id": instance_id,
        "environment_ref": environment_ref,
        "control_thread_id": control_thread_id,
        "session_id": control_thread_id,
        "channel": "console",
        "work_context_id": work_context_id,
        "backlog_item_id": followup_backlog["backlog_item_id"],
        "source_report_id": report.id,
        "requested_surfaces": ["browser", "desktop", "document"],
        "recommended_scheduler_action": "handoff",
    }
    reason = governance.admission_block_reason(
        KernelTask(
            title="Resume staffed multi-surface follow-up",
            capability_ref="system:dispatch_command",
            payload=task_payload,
        ),
    )
    assert reason is not None
    assert "当前存在运行时交接" in reason
    assert "必须等待人工交接返回后才能继续分派" in reason
    blocked_host_detail = environment_service.get_session_detail(environment_ref)
    assert blocked_host_detail["host_twin"]["host_twin_summary"]["seat_count"] == 2
    assert sorted(
        blocked_host_detail["host_twin"]["host_twin_summary"]["candidate_seat_refs"],
    ) == ["env:seat-a", "env:seat-b"]
    assert (
        blocked_host_detail["host_twin"]["coordination"]["contention_forecast"]["severity"]
        == "blocked"
    )
    assert "worker-2" in str(
        blocked_host_detail["host_twin"]["coordination"]["contention_forecast"]["reason"],
    )

    current_task_response = client.get(
        "/runtime-center/human-assist-tasks/current",
        params={"chat_thread_id": control_thread_id},
    )
    assert current_task_response.status_code == 200
    current_task_payload = current_task_response.json()
    current_task = current_task_payload.get("task") or current_task_payload
    assert current_task["submission_payload"]["environment_ref"] == environment_ref
    assert current_task["submission_payload"]["work_context_id"] == work_context_id
    assert current_task["submission_payload"]["recommended_scheduler_action"] == "handoff"
    assert current_task["submission_payload"]["requested_surfaces"] == [
        "browser",
        "desktop",
        "document",
    ]
    assert current_task["submission_payload"]["main_brain_runtime"]["work_context_id"] == (
        work_context_id
    )
    assert current_task["submission_payload"]["main_brain_runtime"]["environment_ref"] == (
        environment_ref
    )
    assert (
        current_task["submission_payload"]["main_brain_runtime"]["resume_checkpoint_id"]
        == "checkpoint:phase-next-handoff"
    )

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-phase-next-human-assist",
            "session_id": control_thread_id,
            "thread_id": control_thread_id,
            "user_id": "host-user",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "Completed checkpoint:phase-next-handoff.",
                        },
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert query_execution_service.calls == [current_task["id"]]
    assert human_assist_task_service.get_task(current_task["id"]).status == "closed"

    closed_task_response = client.get(f"/runtime-center/human-assist-tasks/{current_task['id']}")
    assert closed_task_response.status_code == 200
    closed_task_payload = closed_task_response.json()
    closed_task = closed_task_payload.get("task") or closed_task_payload
    assert closed_task["submission_payload"]["environment_ref"] == environment_ref
    assert closed_task["submission_payload"]["work_context_id"] == work_context_id
    assert closed_task["submission_payload"]["control_thread_id"] == control_thread_id
    assert closed_task["submission_payload"]["recommended_scheduler_action"] == "handoff"
    assert closed_task["submission_payload"]["requested_surfaces"] == [
        "browser",
        "desktop",
        "document",
    ]
    assert closed_task["submission_payload"]["main_brain_runtime"]["work_context_id"] == (
        work_context_id
    )
    assert closed_task["submission_payload"]["main_brain_runtime"]["environment_ref"] == (
        environment_ref
    )
    assert (
        closed_task["submission_payload"]["main_brain_runtime"]["control_thread_id"]
        == control_thread_id
    )
    assert (
        closed_task["submission_payload"]["main_brain_runtime"]["recommended_scheduler_action"]
        == "handoff"
    )

    environment_service.ready = True
    cleared_reason = governance.admission_block_reason(
        KernelTask(
            title="Resume staffed multi-surface follow-up",
            capability_ref="system:dispatch_command",
            payload={
                **task_payload,
                "recommended_scheduler_action": "continue",
            },
        ),
    )
    assert cleared_reason is None
    resumed_host_detail = environment_service.get_session_detail(environment_ref)
    assert resumed_host_detail["host_twin"]["host_twin_summary"]["seat_count"] == 2
    assert sorted(
        resumed_host_detail["host_twin"]["host_twin_summary"]["candidate_seat_refs"],
    ) == ["env:seat-a", "env:seat-b"]
    assert resumed_host_detail["host_twin"]["host_twin_summary"]["selected_seat_ref"] == (
        "env:seat-b"
    )

    resumed_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:phase-next-smoke-resume-after-human-assist",
            force=True,
            backlog_item_ids=[followup_backlog["backlog_item_id"]],
            auto_dispatch_materialized_goals=False,
        ),
    )
    resumed_assignment_ids = resumed_cycle["processed_instances"][0]["created_assignment_ids"]
    resumed_assignment_id = resumed_assignment_ids[0] if resumed_assignment_ids else None

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    assert runtime_payload["execution"]["current_focus_id"] in {None, resumed_assignment_id}
    assert runtime_payload["main_chain"]["current_focus_id"] in {None, resumed_assignment_id}
    replan_node = next(
        node for node in runtime_payload["main_chain"]["nodes"] if node["node_id"] == "replan"
    )
    assert "browser" in replan_node["metrics"]["followup_pressure_surfaces"]
    assert "desktop" in replan_node["metrics"]["followup_pressure_surfaces"]
    assert "document" in replan_node["metrics"]["followup_pressure_surfaces"]


def test_phase_next_same_thread_cognitive_closure_smoke_updates_visible_judgment_after_later_resolution(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["close the same-thread report loop with visible main-brain judgment"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]
    control_thread_id = f"industry-chat:{instance_id}:execution-core"
    environment_ref = f"session:console:industry:{instance_id}"
    base_time = datetime.now(timezone.utc)

    writeback = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text=(
                "Please publish the customer notice in the browser, keep the operator loop on "
                "the same control thread, and report back."
            ),
            owner_agent_id="copaw-agent-runner",
            session_id=control_thread_id,
            channel="console",
            writeback_plan=build_chat_writeback_plan(
                (
                    "Please publish the customer notice in the browser, keep the operator loop "
                    "on the same control thread, and report back."
                ),
                approved_classifications=["backlog"],
                goal_title="Same-thread publish handoff",
                goal_summary=(
                    "Publish the customer notice and keep the loop on the same control thread."
                ),
                goal_plan_steps=[
                    "Define the browser publish scope.",
                    "Report findings back to the same control thread.",
                    "Resolve any remaining blocker before closing the loop.",
                ],
            ),
        ),
    )

    assert writeback is not None
    decision_id = writeback.get("decision_request_id")
    if decision_id:
        approved = client.post(
            f"/runtime-center/decisions/{decision_id}/approve",
            json={"resolution": "Approve the governed browser seat.", "execute": True},
        )
        assert approved.status_code == 200

    backlog_id = writeback["created_backlog_ids"][0]
    first_cycle = _resolve_initial_materialization(
        app,
        instance_id=instance_id,
        writeback=writeback,
        backlog_id=backlog_id,
        actor="test:phase-next-cognitive-cycle-1",
        auto_dispatch_materialized_goals=False,
    )
    assignment_id = first_cycle["created_assignment_ids"][0]
    cycle_id = first_cycle["started_cycle_id"]
    assert cycle_id is not None
    common_metadata = {
        "control_thread_id": control_thread_id,
        "session_id": control_thread_id,
        "environment_ref": environment_ref,
        "claim_key": "same-thread-publish",
        "chat_writeback_requested_surfaces": ["browser"],
        "seat_requested_surfaces": ["browser"],
    }
    strategy = app.state.strategy_memory_service.get_active_strategy(
        scope_type="industry",
        scope_id=instance_id,
        owner_agent_id="copaw-agent-runner",
    )
    assert strategy is not None
    app.state.strategy_memory_service.upsert_strategy(
        strategy.model_copy(
            update={
                "strategic_uncertainties": [
                    {
                        "uncertainty_id": "uncertainty-same-thread-publish",
                        "statement": "Same-thread publish may still require governed browser follow-up.",
                        "scope": "strategy",
                        "impact_level": "high",
                        "current_confidence": 0.38,
                        "review_by_cycle": "cycle-weekly-1",
                        "escalate_when": ["repeated-blocker", "target-miss"],
                    }
                ],
                "lane_budgets": [
                    {
                        "lane_id": "lane-growth",
                        "budget_window": "next-2-cycles",
                        "target_share": 0.5,
                        "min_share": 0.35,
                        "max_share": 0.65,
                        "review_pressure": "high",
                        "force_include_reason": "Protect governed browser follow-up while the publish uncertainty is unresolved.",
                    }
                ],
            },
        ),
    )

    blocked_report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment_id,
        owner_agent_id="browser-ops-a",
        owner_role_id="temporary-browser-ops-worker",
        headline="Browser publish still blocked",
        summary="The browser publish is still blocked by a missing release note confirmation.",
        status="recorded",
        result="failed",
        findings=["The release note confirmation is still missing."],
        recommendation="Ask the main brain to reconcile the release note gap before retrying.",
        metadata=common_metadata,
        processed=False,
        updated_at=base_time,
    )
    ready_but_waiting_report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment_id,
        owner_agent_id="browser-ops-b",
        owner_role_id="temporary-browser-ops-worker",
        headline="Browser publish can continue after release note check",
        summary="The browser seat is ready once the release note check is confirmed on the control thread.",
        status="recorded",
        result="completed",
        findings=["The browser seat itself is ready."],
        needs_followup=True,
        followup_reason="Release note confirmation still needs main-brain follow-up.",
        recommendation="Confirm the release note check on the same control thread, then resume publish.",
        metadata=common_metadata,
        processed=False,
        updated_at=base_time + timedelta(microseconds=1),
    )
    app.state.agent_report_repository.upsert_report(blocked_report)
    app.state.agent_report_repository.upsert_report(ready_but_waiting_report)

    second_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:phase-next-cognitive-cycle-2",
            force=True,
        ),
    )
    assert set(second_cycle["processed_instances"][0]["processed_report_ids"]) == {
        blocked_report.id,
        ready_but_waiting_report.id,
    }

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    assert detail.current_cycle is not None
    synthesis = detail.current_cycle["synthesis"]
    assert synthesis["needs_replan"] is True
    assert "Reports disagree on same-thread-publish." in synthesis["replan_reasons"]
    assert any(
        reason.endswith("main-brain follow-up.")
        for reason in synthesis["replan_reasons"]
    )
    assert {entry["report_id"] for entry in synthesis["latest_findings"]} == {
        blocked_report.id,
        ready_but_waiting_report.id,
    }
    current_cycle_record = app.state.operating_cycle_repository.get_cycle(
        detail.current_cycle["cycle_id"],
    )
    assert current_cycle_record is not None
    cycle_formal_planning = (
        (current_cycle_record.metadata or {}).get("formal_planning") or {}
    )
    assert cycle_formal_planning["strategy_constraints"]["strategic_uncertainties"][0][
        "uncertainty_id"
    ] == "uncertainty-same-thread-publish"
    assert cycle_formal_planning["strategy_constraints"]["lane_budgets"][0]["lane_id"] == (
        "lane-growth"
    )
    assert cycle_formal_planning["report_replan"]["decision_kind"] == (
        "strategy_review_required"
    )
    assert cycle_formal_planning["report_replan"]["trigger_context"][
        "strategic_uncertainty_ids"
    ] == ["uncertainty-same-thread-publish"]
    uncertainty_register = cycle_formal_planning["report_replan"]["uncertainty_register"]
    assert uncertainty_register["is_truth_store"] is False
    assert uncertainty_register["source"] == "formal-planning-sidecar"
    assert uncertainty_register["durable_source"] == "strategy-memory"
    assert uncertainty_register["summary"]["uncertainty_count"] == 1
    assert uncertainty_register["summary"]["lane_budget_count"] == 1
    assert uncertainty_register["summary"]["trigger_rule_count"] >= 2
    assert uncertainty_register["summary"]["review_cycle_ids"] == ["cycle-weekly-1"]
    assert "repeated_blocker" in uncertainty_register["summary"]["trigger_families"]
    assert "target_miss" in uncertainty_register["summary"]["trigger_families"]
    assert uncertainty_register["items"] == [
        {
            "uncertainty_id": "uncertainty-same-thread-publish",
            "statement": "Same-thread publish may still require governed browser follow-up.",
            "scope": "strategy",
            "impact_level": "high",
            "current_confidence": 0.38,
            "review_by_cycle": "cycle-weekly-1",
            "escalate_when": ["repeated-blocker", "target-miss"],
            "trigger_rule_ids": [
                "uncertainty:uncertainty-same-thread-publish:repeated-blocker",
                "uncertainty:uncertainty-same-thread-publish:target-miss",
            ],
            "trigger_families": [
                "repeated_blocker",
                "target_miss",
            ],
        },
    ]
    current_assignment_record = app.state.assignment_repository.get_assignment(
        detail.current_cycle["assignment_ids"][0],
    )
    assert current_assignment_record is not None
    assignment_formal_planning = (
        (current_assignment_record.metadata or {}).get("formal_planning") or {}
    )
    assert assignment_formal_planning["strategy_constraints"]["lane_budgets"][0][
        "force_include_reason"
    ].startswith("Protect governed browser follow-up")
    assert assignment_formal_planning["cycle_decision"]["cycle_kind"] == (
        detail.current_cycle["cycle_kind"]
    )
    assert assignment_formal_planning["report_replan"]["decision_kind"] == (
        "strategy_review_required"
    )

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    planning_surface = runtime_payload["main_brain_planning"]
    assert planning_surface["strategy_constraints"]["strategic_uncertainties"][0][
        "uncertainty_id"
    ] == "uncertainty-same-thread-publish"
    assert planning_surface["strategy_constraints"]["lane_budgets"][0]["lane_id"] == (
        "lane-growth"
    )
    assert planning_surface["replan"]["decision_kind"] == "strategy_review_required"
    assert planning_surface["replan"]["trigger_context"]["strategic_uncertainty_ids"] == [
        "uncertainty-same-thread-publish"
    ]
    replan_node = next(
        node for node in runtime_payload["main_chain"]["nodes"] if node["node_id"] == "replan"
    )
    assert replan_node["status"] == "active"
    assert replan_node["metrics"]["needs_replan"] is True
    assert replan_node["metrics"]["conflict_count"] >= 1
    assert replan_node["metrics"]["hole_count"] >= 1
    assert control_thread_id in replan_node["metrics"]["followup_control_thread_ids"]
    assert environment_ref in replan_node["metrics"]["followup_environment_refs"]
    assert replan_node["metrics"]["recommended_action"] == (
        "dispatch-governed-followup-on-browser-surface"
    )

    snapshot = app.state.session_backend.load_session_snapshot(
        session_id=control_thread_id,
        user_id="copaw-agent-runner",
        allow_not_exist=True,
    )
    agent_state = snapshot.get("agent") if isinstance(snapshot, dict) else {}
    memory_state = agent_state.get("memory") if isinstance(agent_state, dict) else []
    if isinstance(memory_state, dict):
        control_thread_messages = list(memory_state.get("content") or [])
    else:
        control_thread_messages = list(memory_state or [])
    same_thread_reports = [
        item
        for item in control_thread_messages
        if isinstance(item, dict)
        and item.get("metadata", {}).get("control_thread_id") == control_thread_id
        and item.get("metadata", {}).get("message_kind") == "agent-report-writeback"
    ]
    assert {
        item["metadata"]["report_id"] for item in same_thread_reports
    } >= {
        blocked_report.id,
        ready_but_waiting_report.id,
    }

    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("source_report_id") == blocked_report.id
    )
    followup_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:phase-next-cognitive-cycle-3",
            force=True,
            backlog_item_ids=[followup_backlog["backlog_item_id"]],
            auto_dispatch_materialized_goals=False,
        ),
    )
    followup_assignment_ids = followup_cycle["processed_instances"][0]["created_assignment_ids"]
    detail_before_resolution = app.state.industry_service.get_instance_detail(instance_id)
    assert detail_before_resolution is not None
    assert detail_before_resolution.current_cycle is not None
    resolution_assignment_id = (
        followup_assignment_ids[0] if followup_assignment_ids else assignment_id
    )
    resolution_cycle_id = (
        followup_cycle["processed_instances"][0]["started_cycle_id"]
        or detail_before_resolution.current_cycle["cycle_id"]
    )

    resolved_report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=resolution_cycle_id,
        assignment_id=resolution_assignment_id,
        owner_agent_id="browser-ops-b",
        owner_role_id="temporary-browser-ops-worker",
        headline="Browser publish resolved on same thread",
        summary="The release note confirmation was resolved on the same control thread and publish completed.",
        status="recorded",
        result="completed",
        findings=[
            "The release note confirmation was recorded on the same control thread.",
            "Browser publish completed successfully.",
        ],
        recommendation="Close the follow-up and keep the same-thread confirmation pattern.",
        metadata=common_metadata,
        processed=False,
        updated_at=base_time + timedelta(minutes=1),
    )
    app.state.agent_report_repository.upsert_report(resolved_report)

    final_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:phase-next-cognitive-cycle-4",
            force=True,
        ),
    )
    assert resolved_report.id in final_cycle["processed_instances"][0]["processed_report_ids"]

    resolved_detail = app.state.industry_service.get_instance_detail(instance_id)
    assert resolved_detail is not None
    assert resolved_detail.current_cycle is not None
    resolved_synthesis = resolved_detail.current_cycle["synthesis"]
    assert resolved_synthesis["needs_replan"] is False
    assert resolved_synthesis["conflicts"] == []
    assert resolved_synthesis["holes"] == []
    assert resolved_synthesis["replan_reasons"] == []
    assert [entry["report_id"] for entry in resolved_synthesis["latest_findings"]] == [
        resolved_report.id,
    ]
    assert resolved_synthesis["latest_findings"][0]["headline"] == (
        "Browser publish resolved on same thread"
    )

    resolved_snapshot = app.state.session_backend.load_session_snapshot(
        session_id=control_thread_id,
        user_id="copaw-agent-runner",
        allow_not_exist=True,
    )
    resolved_agent_state = resolved_snapshot.get("agent") if isinstance(resolved_snapshot, dict) else {}
    resolved_memory_state = (
        resolved_agent_state.get("memory") if isinstance(resolved_agent_state, dict) else []
    )
    if isinstance(resolved_memory_state, dict):
        resolved_messages = list(resolved_memory_state.get("content") or [])
    else:
        resolved_messages = list(resolved_memory_state or [])
    resolved_same_thread_reports = [
        item
        for item in resolved_messages
        if isinstance(item, dict)
        and item.get("metadata", {}).get("control_thread_id") == control_thread_id
        and item.get("metadata", {}).get("message_kind") == "agent-report-writeback"
    ]
    assert {
        item["metadata"]["report_id"] for item in resolved_same_thread_reports
    } >= {
        blocked_report.id,
        ready_but_waiting_report.id,
        resolved_report.id,
    }

    resolved_runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    historical_replan_node = next(
        node
        for node in resolved_runtime_payload["main_chain"]["nodes"]
        if node["node_id"] == "replan"
    )
    assert historical_replan_node["status"] == "active"
    assert historical_replan_node["current_ref"] != resolved_detail.current_cycle["cycle_id"]
    assert historical_replan_node["metrics"]["needs_replan"] is True
    assert "Reports disagree on same-thread-publish." in (
        historical_replan_node["metrics"]["replan_reasons"]
    )


def test_phase_next_workflow_and_fixed_sop_share_handoff_host_truth(tmp_path) -> None:
    host_detail = _desktop_host_preflight_detail(
        environment_id="env-desktop-1",
        session_mount_id="session-desktop-1",
        handoff_state="active",
        handoff_reason="human handoff is still active",
        coordination_severity="blocked",
        coordination_reason="office writer ownership is contested",
        recommended_scheduler_action="handoff",
        host_blocker_family="human-handoff-return",
        host_blocker_response="handoff",
    )

    workflow_environment_service = FakeWorkflowEnvironmentService(
        session_details={str(host_detail["session_mount_id"]): host_detail},
    )
    workflow_client = TestClient(
        _build_workflow_app(tmp_path / "workflow", environment_service=workflow_environment_service),
    )
    instance_id = _bootstrap_industry(workflow_client)

    preview = workflow_client.post(
        "/workflow-templates/desktop-outreach-smoke/preview",
        json={
            "industry_instance_id": instance_id,
            "environment_id": host_detail["environment_id"],
            "session_mount_id": host_detail["session_mount_id"],
            "parameters": {
                "target_application": "Excel",
                "recipient_name": "Target contact",
                "message_text": "Prepare the weekly follow-up draft.",
            },
        },
    )
    assert preview.status_code == 200
    workflow_payload = preview.json()
    assert any(
        item["code"] == "host-twin-contention-forecast-blocked"
        for item in workflow_payload["launch_blockers"]
    )

    fixed_sop_client = TestClient(
        _build_fixed_sop_app(
            tmp_path / "fixed-sop",
            environment_service=_FakeFixedSopEnvironmentService(host_detail),
        ),
    )
    binding_id = _create_host_binding(fixed_sop_client)
    doctor = fixed_sop_client.post(f"/fixed-sops/bindings/{binding_id}/doctor")

    assert doctor.status_code == 200
    doctor_payload = doctor.json()
    assert doctor_payload["status"] == "blocked"
    assert doctor_payload["host_preflight"]["coordination"]["recommended_scheduler_action"] == (
        "handoff"
    )
    assert doctor_payload["host_preflight"]["legal_recovery"]["path"] == "handoff"


def test_phase_next_runtime_cockpit_preserves_evidence_decisions_patches_and_replays_across_reentry() -> None:
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.industry_service = FakeIndustryService()
    app.state.governance_service = FakeGovernanceService()
    app.state.routine_service = FakeRoutineService()
    app.state.strategy_memory_service = FakeStrategyMemoryService()
    app.state.environment_service = FakeEnvironmentService()

    client = TestClient(app)

    overview_before = client.get("/runtime-center/surface")
    assert overview_before.status_code == 200
    cards_before = {card["key"]: card for card in overview_before.json()["cards"]}
    assert cards_before["evidence"]["count"] == 1
    assert cards_before["decisions"]["count"] == 1
    assert cards_before["patches"]["count"] == 1
    assert cards_before["governance"]["count"] == 1

    task_before = client.get("/runtime-center/tasks/task-1")
    assert task_before.status_code == 200
    assert task_before.json()["evidence"][0]["id"] == "evidence-1"

    replays_before = client.get(
        "/runtime-center/replays",
        params={"environment_ref": "session:web:main"},
    )
    assert replays_before.status_code == 200
    assert replays_before.json()[0]["replay_id"] == "replay-1"

    force_release = client.post(
        "/runtime-center/sessions/session:web:main/lease/force-release",
        json={"reason": "phase-next recovery reentry"},
    )
    assert force_release.status_code == 200
    assert force_release.json()["lease_status"] == "released"

    session_after = client.get("/runtime-center/sessions/session:web:main")
    assert session_after.status_code == 200
    assert session_after.json()["lease_status"] == "released"

    replays_after = client.get(
        "/runtime-center/replays",
        params={"environment_ref": "session:web:main"},
    )
    assert replays_after.status_code == 200
    assert replays_after.json()[0]["replay_id"] == "replay-1"

    task_after = client.get("/runtime-center/tasks/task-1")
    assert task_after.status_code == 200
    assert task_after.json()["evidence"][0]["id"] == "evidence-1"

    overview_after = client.get("/runtime-center/surface")
    assert overview_after.status_code == 200
    cards_after = {card["key"]: card for card in overview_after.json()["cards"]}
    assert cards_after["evidence"]["count"] == 1
    assert cards_after["decisions"]["count"] == 1
    assert cards_after["patches"]["count"] == 1
    assert cards_after["governance"]["count"] == 1


def test_phase_next_host_switch_smoke_keeps_workflow_and_fixed_sop_on_canonical_selected_seat(
    tmp_path,
) -> None:
    host_detail = _desktop_host_preflight_detail(
        environment_id="env-desktop-1",
        session_mount_id="session-desktop-1",
        continuity_status="restorable",
        continuity_source="rebound-live-handle",
        coordination_reason="canonical runtime switched to the alternate ready seat",
        recommended_scheduler_action="continue",
    )
    host_detail["host_twin"]["coordination"].update(
        {
            "candidate_seat_refs": ["env-desktop-1", "env-desktop-2"],
            "selected_seat_ref": "env-desktop-2",
            "selected_session_mount_id": "session-desktop-2",
            "seat_selection_policy": "prefer-ready-seat",
        },
    )
    host_detail["host_twin"]["host_twin_summary"] = {
        **dict(host_detail["host_twin"].get("host_twin_summary") or {}),
        "seat_count": 2,
        "candidate_seat_refs": ["env-desktop-1", "env-desktop-2"],
        "selected_seat_ref": "env-desktop-2",
        "selected_session_mount_id": "session-desktop-2",
        "seat_selection_policy": "prefer-ready-seat",
    }

    workflow_environment_service = FakeWorkflowEnvironmentService(
        session_details={str(host_detail["session_mount_id"]): host_detail},
    )
    workflow_client = TestClient(
        _build_workflow_app(
            tmp_path / "workflow-switch",
            environment_service=workflow_environment_service,
        ),
    )
    instance_id = _bootstrap_industry(workflow_client)
    solution_lead_agent_id = _industry_role_agent_id(
        workflow_client,
        instance_id,
        "solution-lead",
    )
    _grant_capability_to_agent(
        workflow_client,
        agent_id=solution_lead_agent_id,
        capability_ids=["mcp:desktop_windows"],
    )
    launched = _launch_workflow_via_service(
        workflow_client,
        template_id="desktop-outreach-smoke",
        industry_instance_id=instance_id,
        environment_id="env-desktop-1",
        session_mount_id="session-desktop-1",
        parameters={
            "target_application": "Excel",
            "recipient_name": "Target contact",
            "message_text": "Prepare the switched-seat draft.",
        },
    )
    assert launched.diagnosis.host_snapshot["host_twin_summary"]["selected_seat_ref"] == (
        "env-desktop-2"
    )
    assert launched.diagnosis.host_snapshot["host_twin_summary"][
        "selected_session_mount_id"
    ] == "session-desktop-2"
    workflow_run = workflow_client.app.state.workflow_run_repository.get_run(
        launched.run["run_id"],
    )
    assert workflow_run is not None
    assert workflow_run.metadata["environment_id"] == "env-desktop-2"
    assert workflow_run.metadata["session_mount_id"] == "session-desktop-2"

    fixed_sop_client = TestClient(
        _build_fixed_sop_app(
            tmp_path / "fixed-sop-switch",
            environment_service=_FakeFixedSopEnvironmentService(host_detail),
        ),
    )
    binding_id = _create_host_binding(fixed_sop_client)
    fixed_sop_run = fixed_sop_client.post(
        f"/fixed-sops/bindings/{binding_id}/run",
        json={
            "environment_id": "env-desktop-1",
            "session_mount_id": "session-desktop-1",
        },
    )
    assert fixed_sop_run.status_code == 200
    fixed_sop_detail = fixed_sop_client.get(
        f"/fixed-sops/runs/{fixed_sop_run.json()['workflow_run_id']}",
    )
    assert fixed_sop_detail.status_code == 200
    assert fixed_sop_detail.json()["environment_id"] == "env-desktop-2"
    assert fixed_sop_detail.json()["session_mount_id"] == "session-desktop-2"


def test_phase_next_document_host_switch_smoke_keeps_document_execution_on_canonical_host_truth(
    tmp_path,
) -> None:
    host_detail = _desktop_host_preflight_detail(
        environment_id="env-desktop-1",
        session_mount_id="session-desktop-1",
        continuity_status="restorable",
        continuity_source="rebound-live-handle",
        coordination_reason="canonical runtime switched to the alternate ready office seat",
        recommended_scheduler_action="continue",
    )
    host_detail["host_twin"]["coordination"].update(
        {
            "candidate_seat_refs": ["env-desktop-1", "env-desktop-2"],
            "selected_seat_ref": "env-desktop-2",
            "selected_session_mount_id": "session-desktop-2",
            "seat_selection_policy": "prefer-ready-seat",
        },
    )
    host_detail["host_twin"]["host_twin_summary"] = {
        **dict(host_detail["host_twin"].get("host_twin_summary") or {}),
        "seat_count": 2,
        "candidate_seat_refs": ["env-desktop-1", "env-desktop-2"],
        "selected_seat_ref": "env-desktop-2",
        "selected_session_mount_id": "session-desktop-2",
        "seat_selection_policy": "prefer-ready-seat",
        "active_app_family_keys": ["office_document"],
    }

    workflow_environment_service = FakeWorkflowEnvironmentService(
        session_details={str(host_detail["session_mount_id"]): host_detail},
    )
    workflow_client = TestClient(
        _build_workflow_app(
            tmp_path / "workflow-document-switch",
            environment_service=workflow_environment_service,
        ),
    )
    instance_id = _bootstrap_industry(workflow_client)
    solution_lead_agent_id = _industry_role_agent_id(
        workflow_client,
        instance_id,
        "solution-lead",
    )
    _grant_capability_to_agent(
        workflow_client,
        agent_id=solution_lead_agent_id,
        capability_ids=["mcp:desktop_windows"],
    )
    workflow_client.app.state.workflow_template_repository.upsert_template(
        WorkflowTemplateRecord(
            template_id="phase-next-document-host-switch",
            title="Phase Next Document Host Switch",
            summary="Keep document execution on canonical host truth after host switch.",
            category="desktop-ops",
            status="active",
            version="v1",
            owner_role_id="solution-lead",
            suggested_role_ids=["solution-lead"],
            dependency_capability_ids=["system:dispatch_query", "mcp:desktop_windows"],
            step_specs=[
                {
                    "id": "document-switch-leaf",
                    "kind": "goal",
                    "execution_mode": "leaf",
                    "owner_role_id": "solution-lead",
                    "title": "Update workbook on canonical host",
                    "summary": "Mutate the active office document after host switch.",
                    "required_capability_ids": [
                        "system:dispatch_query",
                        "mcp:desktop_windows",
                    ],
                    "environment_preflight": {
                        "surface_kind": "document",
                        "mutating": True,
                        "app_family": "office_document",
                    },
                },
            ],
        ),
    )

    launched = _launch_workflow_via_service(
        workflow_client,
        template_id="phase-next-document-host-switch",
        industry_instance_id=instance_id,
        environment_id="env-desktop-1",
        session_mount_id="session-desktop-1",
        parameters={
            "target_application": "Excel",
            "recipient_name": "Target contact",
            "message_text": "Prepare the switched-seat workbook draft.",
        },
    )
    assert launched.diagnosis.host_snapshot["host_twin_summary"]["selected_seat_ref"] == (
        "env-desktop-2"
    )
    assert launched.diagnosis.host_snapshot["host_twin_summary"][
        "selected_session_mount_id"
    ] == "session-desktop-2"
    assert launched.run["host_requirement"]["surface_kind"] == "document"
    assert launched.run["host_requirement"]["app_family"] == "office_document"
    workflow_run = workflow_client.app.state.workflow_run_repository.get_run(
        launched.run["run_id"],
    )
    assert workflow_run is not None
    assert workflow_run.metadata["environment_id"] == "env-desktop-2"
    assert workflow_run.metadata["session_mount_id"] == "session-desktop-2"

    fixed_sop_client = TestClient(
        _build_fixed_sop_app(
            tmp_path / "fixed-sop-document-switch",
            environment_service=_FakeFixedSopEnvironmentService(host_detail),
        ),
    )
    binding_response = fixed_sop_client.post(
        "/fixed-sops/bindings",
        json={
            "template_id": "fixed-sop-http-routine-bridge",
            "binding_name": "Document Host Switch SOP",
            "status": "active",
            "metadata": {
                "environment_id": "env-desktop-1",
                "session_mount_id": "session-desktop-1",
                "host_requirement": {
                    "surface_kind": "document",
                    "app_family": "office_document",
                    "mutating": True,
                },
            },
        },
    )
    assert binding_response.status_code == 201
    binding_id = binding_response.json()["binding"]["binding_id"]
    fixed_sop_run = fixed_sop_client.post(
        f"/fixed-sops/bindings/{binding_id}/run",
        json={
            "environment_id": "env-desktop-1",
            "session_mount_id": "session-desktop-1",
        },
    )
    assert fixed_sop_run.status_code == 200
    fixed_sop_detail = fixed_sop_client.get(
        f"/fixed-sops/runs/{fixed_sop_run.json()['workflow_run_id']}",
    )
    assert fixed_sop_detail.status_code == 200
    assert fixed_sop_detail.json()["environment_id"] == "env-desktop-2"
    assert fixed_sop_detail.json()["session_mount_id"] == "session-desktop-2"
    assert fixed_sop_detail.json()["host_requirement"]["surface_kind"] == "document"
    assert fixed_sop_detail.json()["host_requirement"]["app_family"] == "office_document"


def test_phase_next_researcher_schedule_followup_keeps_execution_core_continuity(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path / "industry-researcher-continuity")
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["keep researcher continuity on the same main-brain chain"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    researcher_agent_id = next(
        agent.agent_id for agent in draft.team.agents if agent.role_id == "researcher"
    )
    draft.schedules.append(
        IndustryDraftSchedule(
            schedule_id="phase-next-researcher-monitoring-explicit",
            owner_agent_id=researcher_agent_id,
            title=f"{profile.primary_label()} Monitoring Brief Review",
            summary="Run the explicit researcher monitoring brief and return governed follow-up pressure.",
            cron="0 10 * * 2",
            timezone="UTC",
            dispatch_mode="stream",
        )
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    instance_id = payload["team"]["team_id"]
    control_thread_id = f"industry-chat:{instance_id}:execution-core"
    environment_ref = f"session:console:industry:{instance_id}"

    researcher_schedule_id = bootstrap_schedule_by_role(payload, "researcher")["schedule_id"]
    schedule = app.state.schedule_repository.get_schedule(researcher_schedule_id)
    assert schedule is not None
    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    cycle_id = record.current_cycle_id
    assert cycle_id is not None

    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=None,
        owner_agent_id=schedule.spec_payload["meta"]["owner_agent_id"],
        owner_role_id="researcher",
        headline="Monitoring brief found escalation signal",
        summary="The explicit monitoring brief surfaced a governed follow-up for the main brain chain.",
        status="recorded",
        result="failed",
        findings=["Competitor monitoring surfaced a signal that needs execution-core routing."],
        recommendation="Route the next step back through the execution-core control thread.",
        processed=False,
        work_context_id="ctx-phase-next-researcher-followup",
        metadata=dict(schedule.spec_payload.get("meta") or {}),
    )
    app.state.agent_report_repository.upsert_report(report)

    second_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:phase-next-researcher-cycle-2",
            force=True,
        ),
    )
    assert report.id in second_cycle["processed_instances"][0]["processed_report_ids"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("source_report_id") == report.id
    )
    metadata = followup_backlog["metadata"]
    assert metadata["control_thread_id"] == control_thread_id
    assert metadata["session_id"] == control_thread_id
    assert metadata["environment_ref"] == environment_ref
    assert metadata["work_context_id"] == report.work_context_id
    assert metadata["owner_agent_id"] == "copaw-agent-runner"
    assert metadata["industry_role_id"] == "execution-core"
    assert metadata["recommended_scheduler_action"] == "continue"

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    assert runtime_payload["execution"]["current_focus_id"] is None
    assert runtime_payload["main_chain"]["current_focus_id"] is None
    replan_node = next(
        node for node in runtime_payload["main_chain"]["nodes"] if node["node_id"] == "replan"
    )
    assert control_thread_id in replan_node["metrics"]["followup_control_thread_ids"]
    assert environment_ref in replan_node["metrics"]["followup_environment_refs"]


def test_phase_next_long_run_harness_smoke_covers_runtime_chain_and_multi_surface_continuity_contract(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path / "industry-long-run")
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Field Operations",
            company_name="Northwind Robotics",
            product="inspection orchestration",
            goals=["keep the long-run staffed handoff loop stable across recovery"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]
    control_thread_id = f"industry-chat:{instance_id}:execution-core"
    environment_ref = f"session:console:industry:{instance_id}"
    work_context_id = "ctx-phase-next-long-run"

    app.state.startup_recovery_summary = StartupRecoverySummary(
        reason="Recovered the long-run runtime and scheduler state during startup.",
        expired_decisions=1,
        pending_decisions=1,
        active_schedules=1,
        notes=["Recovered the canonical host continuity checkpoint."],
    )
    app.state.schedule_repository.upsert_schedule(
        ScheduleRecord(
            id="sched-phase-next-long-run",
            title="Phase Next Long Run",
            cron="0 9 * * *",
            timezone="UTC",
            status="scheduled",
            enabled=True,
            task_type="agent",
            target_channel="console",
            target_user_id="runtime-center",
            target_session_id=control_thread_id,
            last_run_at=datetime(2026, 3, 30, 7, 30, tzinfo=timezone.utc),
            next_run_at=datetime(2026, 3, 30, 9, 0, tzinfo=timezone.utc),
            source_ref=f"industry:{instance_id}",
            trigger_target="operating-cycle",
        ),
    )
    app.state.cron_manager = FakeCronManager(
        [make_job("sched-phase-next-long-run")],
        states={
            "sched-phase-next-long-run": CronJobState(
                last_status="success",
                last_run_at=datetime(2026, 3, 30, 7, 30, tzinfo=timezone.utc),
                next_run_at=datetime(2026, 3, 30, 9, 0, tzinfo=timezone.utc),
            ),
        },
        heartbeat_state=CronJobState(
            last_status="success",
            last_run_at=datetime(2026, 3, 30, 8, 0, tzinfo=timezone.utc),
            next_run_at=datetime(2026, 3, 30, 14, 0, tzinfo=timezone.utc),
        ),
    )

    writeback = asyncio.run(
        app.state.industry_service.apply_execution_chat_writeback(
            industry_instance_id=instance_id,
            message_text=(
                "Please publish the customer notice in the browser, update the desktop tracker and "
                "document log, keep the handoff governed, and report back."
            ),
            owner_agent_id="copaw-agent-runner",
            session_id=control_thread_id,
            channel="console",
            writeback_plan=build_chat_writeback_plan(
                (
                    "Please publish the customer notice in the browser, update the desktop tracker "
                    "and document log, keep the handoff governed, and report back."
                ),
                approved_classifications=["backlog"],
                goal_title="Long-run multi-surface publish handoff",
                goal_summary="Publish through browser/desktop/document with governed handoff.",
                goal_plan_steps=[
                    "Define the governed multi-surface execution scope.",
                    "Require approval before any external action.",
                    "Write back the result and evidence.",
                ],
            ),
        ),
    )

    assert writeback is not None
    decision_id = writeback.get("decision_request_id")
    backlog_id = writeback["created_backlog_ids"][0]
    if decision_id:
        approved = client.post(
            f"/runtime-center/decisions/{decision_id}/approve",
            json={"resolution": "Approve the governed staffing seat.", "execute": True},
        )
        assert approved.status_code == 200

    first_cycle = _resolve_initial_materialization(
        app,
        instance_id=instance_id,
        writeback=writeback,
        backlog_id=backlog_id,
        actor="test:phase-next-long-run-cycle-1",
        auto_dispatch_materialized_goals=False,
    )
    assignment_id = first_cycle["created_assignment_ids"][0]
    cycle_id = first_cycle["started_cycle_id"]
    assert cycle_id is not None

    report = AgentReportRecord(
        industry_instance_id=instance_id,
        cycle_id=cycle_id,
        assignment_id=assignment_id,
        owner_agent_id=writeback["target_owner_agent_id"],
        owner_role_id=writeback["target_industry_role_id"],
        headline="Long-run multi-surface handoff still blocked",
        summary="Browser, desktop, and document work are still blocked until host handoff returns.",
        status="recorded",
        result="failed",
        findings=["The host handoff checkpoint was not returned yet."],
        recommendation="Resume the staffed seat after the host handoff closes.",
        work_context_id=work_context_id,
        metadata={
            "chat_writeback_requested_surfaces": ["browser", "desktop", "document"],
            "seat_requested_surfaces": ["browser", "desktop", "document"],
            "control_thread_id": control_thread_id,
            "session_id": control_thread_id,
            "environment_ref": environment_ref,
            "recommended_scheduler_action": "handoff",
        },
        processed=False,
    )
    app.state.agent_report_repository.upsert_report(report)

    second_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:phase-next-long-run-cycle-2",
            force=True,
        ),
    )
    assert report.id in second_cycle["processed_instances"][0]["processed_report_ids"]

    detail = app.state.industry_service.get_instance_detail(instance_id)
    assert detail is not None
    followup_backlog = next(
        item
        for item in detail.backlog
        if item["metadata"].get("source_report_id") == report.id
    )

    human_assist_task_service = HumanAssistTaskService(
        repository=SqliteHumanAssistTaskRepository(app.state.state_store),
        evidence_ledger=app.state.evidence_ledger,
    )
    app.state.human_assist_task_service = human_assist_task_service
    set_human_assist = getattr(app.state.state_query_service, "set_human_assist_task_service", None)
    if callable(set_human_assist):
        set_human_assist(human_assist_task_service)
    app.state.turn_executor = FakeTurnExecutor()
    query_execution_service = _FakeQueryExecutionService()
    app.state.query_execution_service = query_execution_service

    class _MutableEnvironmentService:
        def __init__(self) -> None:
            self.ready = False

        def list_sessions(self, limit=200):
            del limit
            return [SimpleNamespace(session_mount_id=environment_ref)]

        def get_session_detail(self, session_id, limit=20):
            del limit
            assert session_id == environment_ref
            if self.ready:
                return {
                    "host_twin": {
                        "continuity": {"requires_human_return": False},
                        "coordination": {
                            "recommended_scheduler_action": "continue",
                            "selected_seat_ref": "env:seat-b",
                            "selected_session_mount_id": "session:seat-b",
                        },
                        "legal_recovery": {
                            "path": "continue",
                            "checkpoint_ref": "checkpoint:phase-next-long-run",
                        },
                        "host_twin_summary": {
                            "recommended_scheduler_action": "continue",
                            "legal_recovery_mode": "continue",
                            "selected_seat_ref": "env:seat-b",
                            "selected_session_mount_id": "session:seat-b",
                            "blocked_surface_count": 0,
                            "active_app_family_keys": ["browser_backoffice", "office_document"],
                            "active_app_family_count": 2,
                        },
                    },
                }
            return {
                "host_twin": {
                    "continuity": {"requires_human_return": True},
                    "ownership": {"handoff_owner_ref": "host-owner"},
                    "coordination": {"recommended_scheduler_action": "handoff"},
                    "legal_recovery": {
                        "path": "handoff",
                        "checkpoint_ref": "checkpoint:phase-next-long-run",
                    },
                    "host_twin_summary": {
                        "recommended_scheduler_action": "handoff",
                        "legal_recovery_mode": "handoff",
                        "blocked_surface_count": 1,
                    },
                },
            }

    environment_service = _MutableEnvironmentService()
    governance = GovernanceService(
        control_repository=SqliteGovernanceControlRepository(
            SQLiteStateStore(tmp_path / "governance-long-run.sqlite3"),
        ),
        industry_service=app.state.industry_service,
        human_assist_task_service=human_assist_task_service,
        environment_service=environment_service,
    )

    task_payload = {
        "industry_instance_id": instance_id,
        "environment_ref": environment_ref,
        "control_thread_id": control_thread_id,
        "session_id": control_thread_id,
        "channel": "console",
        "work_context_id": work_context_id,
        "backlog_item_id": followup_backlog["backlog_item_id"],
        "source_report_id": report.id,
        "requested_surfaces": ["browser", "desktop", "document"],
        "recommended_scheduler_action": "handoff",
    }
    reason = governance.admission_block_reason(
        KernelTask(
            title="Resume staffed multi-surface follow-up",
            capability_ref="system:dispatch_command",
            payload=task_payload,
        ),
    )
    assert reason is not None
    assert "Runtime handoff is active" in reason

    current_task_response = client.get(
        "/runtime-center/human-assist-tasks/current",
        params={"chat_thread_id": control_thread_id},
    )
    assert current_task_response.status_code == 200
    current_task_payload = current_task_response.json()
    current_task = current_task_payload.get("task") or current_task_payload

    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-phase-next-long-run-human-assist",
            "session_id": control_thread_id,
            "thread_id": control_thread_id,
            "user_id": "host-user",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "Completed checkpoint:phase-next-long-run.",
                        },
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert query_execution_service.calls == [current_task["id"]]
    assert human_assist_task_service.get_task(current_task["id"]).status == "closed"

    closed_task_response = client.get(f"/runtime-center/human-assist-tasks/{current_task['id']}")
    assert closed_task_response.status_code == 200
    closed_task_payload = closed_task_response.json()
    closed_task = closed_task_payload.get("task") or closed_task_payload
    assert closed_task["submission_payload"]["environment_ref"] == environment_ref
    assert closed_task["submission_payload"]["work_context_id"] == work_context_id
    assert closed_task["submission_payload"]["control_thread_id"] == control_thread_id
    assert closed_task["submission_payload"]["recommended_scheduler_action"] == "handoff"
    assert (
        closed_task["submission_payload"]["main_brain_runtime"]["work_context_id"]
        == work_context_id
    )
    assert (
        closed_task["submission_payload"]["main_brain_runtime"]["environment_ref"]
        == environment_ref
    )
    assert (
        closed_task["submission_payload"]["main_brain_runtime"]["control_thread_id"]
        == control_thread_id
    )
    assert (
        closed_task["submission_payload"]["main_brain_runtime"]["recommended_scheduler_action"]
        == "handoff"
    )

    environment_service.ready = True
    cleared_reason = governance.admission_block_reason(
        KernelTask(
            title="Resume staffed multi-surface follow-up",
            capability_ref="system:dispatch_command",
            payload={**task_payload, "recommended_scheduler_action": "continue"},
        ),
    )
    assert cleared_reason is None

    third_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:phase-next-long-run-cycle-3",
            force=True,
            backlog_item_ids=[followup_backlog["backlog_item_id"]],
            auto_dispatch_materialized_goals=False,
        ),
    )
    resumed_assignment_ids = third_cycle["processed_instances"][0]["created_assignment_ids"]
    resumed_assignment_id = resumed_assignment_ids[0] if resumed_assignment_ids else None

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    assert runtime_payload["execution"]["current_focus_id"] in {None, resumed_assignment_id}
    assert runtime_payload["main_chain"]["current_focus_id"] in {None, resumed_assignment_id}

    with patch(
        "copaw.app.runtime_center.overview_cards.get_heartbeat_config",
        return_value=HeartbeatConfig(enabled=True, every="6h", target="main"),
        create=True,
    ):
        cockpit_response = client.get("/runtime-center/surface")

    assert cockpit_response.status_code == 200
    cockpit = cockpit_response.json()
    main_brain = cockpit["main_brain"]
    assert main_brain["governance"]["route"] == "/api/runtime-center/governance/status"
    assert main_brain["recovery"]["available"] is True
    assert main_brain["recovery"]["route"] == "/api/runtime-center/recovery/latest"
    assert main_brain["automation"]["schedule_count"] >= 1
    assert main_brain["automation"]["active_schedule_count"] >= 1
    assert main_brain["automation"]["heartbeat"]["status"] == "success"
    assert main_brain["assignments"]
    assert main_brain["reports"]
    assert main_brain["evidence"]["route"].startswith("/api/runtime-center/evidence")
    assert main_brain["decisions"]["route"].startswith("/api/runtime-center/decisions")
    control_chain_keys = [item["key"] for item in main_brain["meta"]["control_chain"]]
    assert "governance" in control_chain_keys
    assert "automation" in control_chain_keys
    assert "recovery" in control_chain_keys

    host_detail = _desktop_host_preflight_detail(
        environment_id="env-desktop-1",
        session_mount_id="session-desktop-1",
        continuity_status="restorable",
        continuity_source="rebound-live-handle",
        coordination_reason="canonical runtime switched to the alternate ready office seat",
        recommended_scheduler_action="continue",
    )
    host_detail["host_twin"]["coordination"].update(
        {
            "candidate_seat_refs": ["env-desktop-1", "env-desktop-2"],
            "selected_seat_ref": "env-desktop-2",
            "selected_session_mount_id": "session-desktop-2",
            "seat_selection_policy": "prefer-ready-seat",
        },
    )
    host_detail["host_twin"]["host_twin_summary"] = {
        **dict(host_detail["host_twin"].get("host_twin_summary") or {}),
        "seat_count": 2,
        "candidate_seat_refs": ["env-desktop-1", "env-desktop-2"],
        "selected_seat_ref": "env-desktop-2",
        "selected_session_mount_id": "session-desktop-2",
        "seat_selection_policy": "prefer-ready-seat",
        "active_app_family_keys": ["office_document"],
    }

    workflow_environment_service = FakeWorkflowEnvironmentService(
        session_details={str(host_detail["session_mount_id"]): host_detail},
    )
    workflow_client = TestClient(
        _build_workflow_app(
            tmp_path / "workflow-long-run-switch",
            environment_service=workflow_environment_service,
        ),
    )
    workflow_instance_id = _bootstrap_industry(workflow_client)
    solution_lead_agent_id = _industry_role_agent_id(
        workflow_client,
        workflow_instance_id,
        "solution-lead",
    )
    _grant_capability_to_agent(
        workflow_client,
        agent_id=solution_lead_agent_id,
        capability_ids=["mcp:desktop_windows"],
    )
    workflow_client.app.state.workflow_template_repository.upsert_template(
        WorkflowTemplateRecord(
            template_id="phase-next-long-run-document-switch",
            title="Phase Next Long Run Document Host Switch",
            summary="Keep document execution on canonical host truth after long-run host switch.",
            category="desktop-ops",
            status="active",
            version="v1",
            owner_role_id="solution-lead",
            suggested_role_ids=["solution-lead"],
            dependency_capability_ids=["system:dispatch_query", "mcp:desktop_windows"],
            step_specs=[
                {
                    "id": "document-switch-leaf",
                    "kind": "goal",
                    "execution_mode": "leaf",
                    "owner_role_id": "solution-lead",
                    "title": "Update workbook on canonical host",
                    "summary": "Mutate the active office document after host switch.",
                    "required_capability_ids": [
                        "system:dispatch_query",
                        "mcp:desktop_windows",
                    ],
                    "environment_preflight": {
                        "surface_kind": "document",
                        "mutating": True,
                        "app_family": "office_document",
                    },
                },
            ],
        ),
    )
    launched = _launch_workflow_via_service(
        workflow_client,
        template_id="phase-next-long-run-document-switch",
        industry_instance_id=workflow_instance_id,
        environment_id="env-desktop-1",
        session_mount_id="session-desktop-1",
        parameters={
            "target_application": "Excel",
            "recipient_name": "Target contact",
            "message_text": "Prepare the switched-seat workbook draft.",
        },
    )
    assert launched.diagnosis.host_snapshot["host_twin_summary"]["selected_seat_ref"] == (
        "env-desktop-2"
    )
    assert launched.diagnosis.host_snapshot["host_twin_summary"][
        "selected_session_mount_id"
    ] == "session-desktop-2"
    assert launched.run["host_requirement"]["surface_kind"] == "document"

    fixed_sop_client = TestClient(
        _build_fixed_sop_app(
            tmp_path / "fixed-sop-long-run-switch",
            environment_service=_FakeFixedSopEnvironmentService(host_detail),
        ),
    )
    binding_response = fixed_sop_client.post(
        "/fixed-sops/bindings",
        json={
            "template_id": "fixed-sop-http-routine-bridge",
            "binding_name": "Long Run Document Host Switch SOP",
            "status": "active",
            "metadata": {
                "environment_id": "env-desktop-1",
                "session_mount_id": "session-desktop-1",
                "host_requirement": {
                    "surface_kind": "document",
                    "app_family": "office_document",
                    "mutating": True,
                },
            },
        },
    )
    assert binding_response.status_code == 201
    binding_id = binding_response.json()["binding"]["binding_id"]
    fixed_sop_run = fixed_sop_client.post(
        f"/fixed-sops/bindings/{binding_id}/run",
        json={
            "environment_id": "env-desktop-1",
            "session_mount_id": "session-desktop-1",
        },
    )
    assert fixed_sop_run.status_code == 200
    fixed_sop_detail = fixed_sop_client.get(
        f"/fixed-sops/runs/{fixed_sop_run.json()['workflow_run_id']}",
    )
    assert fixed_sop_detail.status_code == 200
    assert fixed_sop_detail.json()["environment_id"] == "env-desktop-2"
    assert fixed_sop_detail.json()["session_mount_id"] == "session-desktop-2"
    assert fixed_sop_detail.json()["host_requirement"]["surface_kind"] == "document"
