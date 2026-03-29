# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from copaw.industry import IndustryPreviewRequest, normalize_industry_profile
from copaw.industry.chat_writeback import build_chat_writeback_plan
from copaw.state import AgentReportRecord

from .industry_api_parts.shared import FakeIndustryDraftGenerator, _build_industry_app
from .runtime_center_api_parts.shared import (
    FakeAgentProfileService,
    FakeCapabilityService,
    FakeEnvironmentService,
    FakeEvidenceQueryService,
    FakeGovernanceService,
    FakeIndustryService,
    FakeLearningService,
    FakeRoutineService,
    FakeStateQueryService,
    FakeStrategyMemoryService,
    build_runtime_center_app,
)
from .test_fixed_sop_kernel_api import _FakeEnvironmentService as _FakeFixedSopEnvironmentService
from .test_fixed_sop_kernel_api import _build_app as _build_fixed_sop_app
from .test_fixed_sop_kernel_api import _create_host_binding
from .test_workflow_templates_api import (
    FakeWorkflowEnvironmentService,
    _bootstrap_industry,
    _build_workflow_app,
    _desktop_host_preflight_detail,
)


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

    response = client.get("/runtime-center/overview")

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


def test_phase_next_industry_long_run_smoke_keeps_followup_focus_and_replan_truth(
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
    decision_id = writeback["decision_request_id"]
    backlog_id = writeback["created_backlog_ids"][0]
    approved = client.post(
        f"/runtime-center/decisions/{decision_id}/approve",
        json={"resolution": "Approve the governed browser staffing seat.", "execute": True},
    )
    assert approved.status_code == 200

    first_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:phase-next-smoke-cycle",
            force=True,
            backlog_item_ids=[backlog_id],
            auto_dispatch_materialized_goals=False,
        ),
    )
    assignment_id = first_cycle["processed_instances"][0]["created_assignment_ids"][0]
    cycle_id = first_cycle["processed_instances"][0]["started_cycle_id"]

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
    assert runtime_payload["execution"]["current_focus_id"] != assignment_id
    assert runtime_payload["main_chain"]["current_focus_id"] != assignment_id
    assert runtime_payload["execution"]["current_focus_id"] in {
        followup_backlog["backlog_item_id"],
        resumed_assignment_id,
    }
    assert runtime_payload["main_chain"]["current_focus_id"] in {
        followup_backlog["backlog_item_id"],
        resumed_assignment_id,
    }
    replan_node = next(
        node for node in runtime_payload["main_chain"]["nodes"] if node["node_id"] == "replan"
    )
    assert replan_node["status"] in {"active", "idle"}
    if replan_node["status"] == "active":
        assert replan_node["metrics"]["replan_reason_count"] >= 1


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

    overview_before = client.get("/runtime-center/overview")
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

    overview_after = client.get("/runtime-center/overview")
    assert overview_after.status_code == 200
    cards_after = {card["key"]: card for card in overview_after.json()["cards"]}
    assert cards_after["evidence"]["count"] == 1
    assert cards_after["decisions"]["count"] == 1
    assert cards_after["patches"]["count"] == 1
    assert cards_after["governance"]["count"] == 1
