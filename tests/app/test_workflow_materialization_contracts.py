from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from .test_workflow_templates_api import (
    FakeWorkflowEnvironmentService,
    _bootstrap_industry,
    _browser_host_preflight_detail,
    _build_workflow_app,
    _launch_workflow_via_service,
)


def test_workflow_launch_materializes_leaf_goals_with_explicit_compatibility_class(
    tmp_path,
) -> None:
    detail = _browser_host_preflight_detail()
    environment_service = FakeWorkflowEnvironmentService(
        session_details={str(detail["session_mount_id"]): detail},
    )
    client = TestClient(_build_workflow_app(tmp_path, environment_service=environment_service))
    instance_id = _bootstrap_industry(client)

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
    service = client.app.state.workflow_template_service
    linked_goal_overrides = [
        override
        for override in service._goal_override_repository.list_overrides()
        if str((override.compiler_context or {}).get("workflow_run_id") or "") == run_id
    ]

    assert linked_goal_overrides
    for override in linked_goal_overrides:
        goal = service._goal_service.get_goal(override.goal_id)
        assert goal is not None
        assert goal.goal_class == "workflow-step-goal"
        assert (override.compiler_context or {}).get("materialization_path") == (
            "workflow-leaf-compatibility"
        )


def test_workflow_resume_fallback_recreates_leaf_goal_with_explicit_compatibility_class(
    tmp_path,
) -> None:
    detail = _browser_host_preflight_detail()
    environment_service = FakeWorkflowEnvironmentService(
        session_details={str(detail["session_mount_id"]): detail},
    )
    client = TestClient(_build_workflow_app(tmp_path, environment_service=environment_service))
    instance_id = _bootstrap_industry(client)

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
    run_detail = client.get(f"/workflow-runs/{run_id}")
    assert run_detail.status_code == 200
    goal_step = next(
        item for item in run_detail.json()["step_execution"] if item["kind"] == "goal"
    )

    service = client.app.state.workflow_template_service
    linked_goal_overrides = [
        override
        for override in service._goal_override_repository.list_overrides()
        if str((override.compiler_context or {}).get("workflow_run_id") or "") == run_id
        and str((override.compiler_context or {}).get("workflow_step_id") or "")
        == goal_step["step_id"]
    ]
    assert len(linked_goal_overrides) == 1
    original_override = linked_goal_overrides[0]
    service._goal_override_repository.delete_override(original_override.goal_id)

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

    resumed = asyncio.run(
        service.resume_run(
            run_id,
            actor="copaw-operator",
        ),
    )
    resumed_goal_detail = next(
        item for item in resumed.step_execution if item.step_id == goal_step["step_id"]
    )
    assert resumed_goal_detail.status in {"planned", "running", "completed", "draft"}

    recreated_overrides = [
        override
        for override in service._goal_override_repository.list_overrides()
        if str((override.compiler_context or {}).get("workflow_run_id") or "") == run_id
        and str((override.compiler_context or {}).get("workflow_step_id") or "")
        == goal_step["step_id"]
    ]
    assert len(recreated_overrides) == 1
    recreated_goal = service._goal_service.get_goal(recreated_overrides[0].goal_id)
    assert recreated_goal is not None
    assert recreated_goal.goal_class == "workflow-step-goal"
    assert (recreated_overrides[0].compiler_context or {}).get("materialization_path") == (
        "workflow-leaf-compatibility"
    )
