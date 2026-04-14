# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from copaw.app.routers.workflow_templates import run_router as workflow_runs_router
from copaw.app.routers.workflow_templates import router as workflow_templates_router
from copaw.learning import LearningEngine, LearningService, PatchExecutor
from copaw.state.repositories import (
    SqliteWorkflowPresetRepository,
    SqliteWorkflowRunRepository,
    SqliteWorkflowTemplateRepository,
)
from copaw.workflows import WorkflowTemplateService
from tests.app.industry_api_parts.shared import _build_industry_app
from tests.app.test_workflow_templates_api import (
    FakeWorkflowEnvironmentService,
    _browser_host_preflight_detail,
    _launch_workflow_via_service,
)


def test_industry_workflow_learning_runtime_closure_runs_end_to_end(tmp_path) -> None:
    detail = _browser_host_preflight_detail()
    environment_service = FakeWorkflowEnvironmentService(
        session_details={str(detail["session_mount_id"]): detail},
    )
    app = _build_industry_app(tmp_path)
    workflow_template_repository = SqliteWorkflowTemplateRepository(app.state.state_store)
    workflow_preset_repository = SqliteWorkflowPresetRepository(app.state.state_store)
    workflow_run_repository = SqliteWorkflowRunRepository(app.state.state_store)
    workflow_template_service = WorkflowTemplateService(
        workflow_template_repository=workflow_template_repository,
        workflow_run_repository=workflow_run_repository,
        workflow_preset_repository=workflow_preset_repository,
        goal_service=app.state.goal_service,
        goal_override_repository=app.state.goal_override_repository,
        schedule_repository=app.state.schedule_repository,
        industry_instance_repository=app.state.industry_instance_repository,
        strategy_memory_service=app.state.strategy_memory_service,
        task_repository=app.state.task_repository,
        decision_request_repository=app.state.decision_request_repository,
        agent_profile_override_repository=app.state.agent_profile_override_repository,
        agent_profile_service=app.state.agent_profile_service,
        evidence_ledger=app.state.evidence_ledger,
        capability_service=app.state.capability_service,
        schedule_writer=app.state.industry_service._schedule_writer,
        environment_service=environment_service,
    )
    app.include_router(workflow_templates_router)
    app.include_router(workflow_runs_router)
    app.state.workflow_template_repository = workflow_template_repository
    app.state.workflow_preset_repository = workflow_preset_repository
    app.state.workflow_run_repository = workflow_run_repository
    app.state.workflow_template_service = workflow_template_service
    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Industrial Equipment",
            "company_name": "Northwind Robotics",
            "product": "factory monitoring copilots",
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()

    bootstrap = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": preview_payload["draft"],
            "auto_activate": True,
            "auto_dispatch": True,
            "execute": False,
        },
    )
    assert bootstrap.status_code == 200
    bootstrap_payload = bootstrap.json()
    instance_id = bootstrap_payload["team"]["team_id"]
    assignments = list(bootstrap_payload["assignments"] or [])
    assert assignments
    runtime_detail_after_bootstrap = client.get(f"/runtime-center/industry/{instance_id}")
    assert runtime_detail_after_bootstrap.status_code == 200
    seeded_assignment = next(
        item
        for item in runtime_detail_after_bootstrap.json()["assignments"]
        if item.get("task_id") and item.get("assignment_id")
    )
    task_id = str(seeded_assignment["task_id"])
    assignment_id = str(seeded_assignment["assignment_id"])
    owner_agent_id = str(seeded_assignment["owner_agent_id"])

    goals = client.app.state.goal_service.list_goals(
        industry_instance_id=instance_id,
        limit=None,
    )
    assert goals
    assert all(goal.goal_class == "compatibility-bootstrap-goal" for goal in goals)

    launched = _launch_workflow_via_service(
        client,
        template_id="industry-weekly-research-synthesis",
        industry_instance_id=instance_id,
        environment_id=str(detail["environment_id"]),
        session_mount_id=str(detail["session_mount_id"]),
        parameters={
            "focus_area": "channel conversion",
            "weekly_review_cron": "0 12 * * 2",
            "timezone": "UTC",
        },
    )
    run_id = launched.run["run_id"]
    workflow_service = client.app.state.workflow_template_service
    workflow_goal_overrides = [
        override
        for override in workflow_service._goal_override_repository.list_overrides()
        if str((override.compiler_context or {}).get("workflow_run_id") or "") == run_id
    ]
    assert workflow_goal_overrides
    for override in workflow_goal_overrides:
        goal = workflow_service._goal_service.get_goal(override.goal_id)
        assert goal is not None
        assert goal.goal_class == "workflow-step-goal"
        assert (override.compiler_context or {}).get("materialization_path") == (
            "workflow-leaf-compatibility"
        )

    run_detail = client.get(f"/workflow-runs/{run_id}")
    assert run_detail.status_code == 200
    goal_step = next(
        item for item in run_detail.json()["step_execution"] if item["kind"] == "goal"
    )
    original_override = next(
        override
        for override in workflow_goal_overrides
        if str((override.compiler_context or {}).get("workflow_step_id") or "")
        == goal_step["step_id"]
    )
    workflow_service._goal_override_repository.delete_override(original_override.goal_id)
    run_record = client.app.state.workflow_run_repository.get_run(run_id)
    assert run_record is not None
    metadata = dict(run_record.metadata or {})
    step_seed = []
    for item in list(metadata.get("step_execution_seed") or []):
        if not isinstance(item, dict):
            continue
        copied = dict(item)
        if copied.get("step_id") == goal_step["step_id"]:
            copied["linked_goal_ids"] = []
            copied["linked_task_ids"] = []
            copied["linked_decision_ids"] = []
            copied["linked_evidence_ids"] = []
        step_seed.append(copied)
    client.app.state.workflow_run_repository.upsert_run(
        run_record.model_copy(
            update={
                "metadata": {
                    **metadata,
                    "step_execution_seed": step_seed,
                },
            },
        ),
    )
    resumed = asyncio.run(workflow_service.resume_run(run_id, actor="copaw-operator"))
    resumed_goal_detail = next(
        item for item in resumed.step_execution if item.step_id == goal_step["step_id"]
    )
    assert resumed_goal_detail.status in {"planned", "running", "completed", "draft"}
    recreated_override = next(
        override
        for override in workflow_service._goal_override_repository.list_overrides()
        if str((override.compiler_context or {}).get("workflow_run_id") or "") == run_id
        and str((override.compiler_context or {}).get("workflow_step_id") or "")
        == goal_step["step_id"]
    )
    recreated_goal = workflow_service._goal_service.get_goal(recreated_override.goal_id)
    assert recreated_goal is not None
    assert recreated_goal.goal_class == "workflow-step-goal"

    learning_service = LearningService(
        engine=LearningEngine(tmp_path / "learning.sqlite3"),
        patch_executor=PatchExecutor(
            workflow_template_repository=workflow_template_repository,
            workflow_run_repository=workflow_run_repository,
        ),
        decision_request_repository=client.app.state.goal_service._decision_request_repository,
        task_repository=client.app.state.goal_service._task_repository,
        evidence_ledger=client.app.state.goal_service._evidence_ledger,
    )
    client.app.state.learning_service = learning_service
    client.app.state.industry_service._learning_service = learning_service

    proposal = learning_service.create_proposal(
        title="Promote workflow optimization into formal patch",
        description="Tighten the workflow loop after bootstrap dispatch.",
        task_id=task_id,
        agent_id=owner_agent_id,
    )
    patch_payload = learning_service.create_patch(
        kind="workflow_patch",
        title="Refine workflow template step",
        description="Tighten the workflow-native step summary and plan steps.",
        task_id=task_id,
        agent_id=owner_agent_id,
        workflow_template_id="industry-weekly-research-synthesis",
        workflow_run_id=run_id,
        workflow_step_id="weekly-research-goal",
        patch_payload={
            "target_surface": "workflow_template",
            "step_updates": {
                "summary": "Updated summary from full scenario test",
                "plan_steps": [
                    "collect signal",
                    "write operator brief",
                    "publish follow-up",
                ],
            },
        },
    )
    patch = patch_payload["patch"]
    assert patch is not None
    applied = learning_service.apply_patch(patch.id, applied_by="scenario-tester")
    assert applied.status == "applied"
    template = client.app.state.workflow_template_repository.get_template(
        "industry-weekly-research-synthesis",
    )
    assert template is not None
    target_step = next(
        item for item in template.step_specs if str(item.get("id") or "") == "weekly-research-goal"
    )
    assert target_step["summary"] == "Updated summary from full scenario test"

    detail_response = client.get(f"/runtime-center/industry/{instance_id}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    closure = detail_payload["optimization_closure"]
    assert closure["counts"]["proposals"] >= 1
    assert closure["counts"]["patches"] >= 1
    assert closure["counts"]["growth"] >= 1
    linked = next(
        item
        for item in closure["links"]
        if item["task_id"] == task_id and item["assignment_id"] == assignment_id
    )
    assert proposal.id in linked["proposal_ids"]
    assert patch.id in linked["patch_ids"]
    assert patch.workflow_run_id in linked["workflow_run_ids"]
    assert patch.workflow_step_id in linked["workflow_step_ids"]
    growth_ids = {
        event.id
        for event in learning_service.list_growth(task_id=task_id, limit=None)
        if event.source_patch_id == patch.id
    }
    assert growth_ids
    assert growth_ids.issubset(set(linked["growth_ids"]))

    rolled_back = learning_service.rollback_patch(patch.id, rolled_back_by="scenario-tester")
    assert rolled_back.status == "rolled_back"
    restored_template = client.app.state.workflow_template_repository.get_template(
        "industry-weekly-research-synthesis",
    )
    assert restored_template is not None
    restored_step = next(
        item
        for item in restored_template.step_specs
        if str(item.get("id") or "") == "weekly-research-goal"
    )
    assert restored_step["summary"] != "Updated summary from full scenario test"
