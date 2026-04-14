from __future__ import annotations

from copaw.learning import LearningEngine, LearningService, PatchExecutor
from copaw.state import SQLiteStateStore, WorkflowTemplateRecord
from copaw.state.repositories import SqliteWorkflowRunRepository, SqliteWorkflowTemplateRepository


def test_learning_service_applies_and_rolls_back_workflow_patch_against_template_truth(
    tmp_path,
) -> None:
    engine = LearningEngine(tmp_path / "learning.sqlite3")
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    workflow_template_repository = SqliteWorkflowTemplateRepository(state_store)
    workflow_run_repository = SqliteWorkflowRunRepository(state_store)
    workflow_template_repository.upsert_template(
        WorkflowTemplateRecord(
            template_id="workflow-template-1",
            title="Workflow Template",
            summary="Baseline summary",
            step_specs=[
                {
                    "id": "weekly-research-goal",
                    "kind": "goal",
                    "title": "Original title",
                    "summary": "Original summary",
                    "plan_steps": ["collect signal"],
                }
            ],
        )
    )
    service = LearningService(
        engine=engine,
        patch_executor=PatchExecutor(
            workflow_template_repository=workflow_template_repository,
            workflow_run_repository=workflow_run_repository,
        ),
    )

    payload = service.create_patch(
        kind="workflow_patch",
        title="Refine workflow template step",
        description="Apply workflow-native optimization",
        workflow_template_id="workflow-template-1",
        workflow_step_id="weekly-research-goal",
        patch_payload={
            "target_surface": "workflow_template",
            "step_updates": {
                "summary": "Updated summary",
                "plan_steps": ["collect signal", "write operator brief"],
            },
        },
    )
    patch = payload["patch"]
    assert patch is not None
    assert patch.status == "approved"

    applied = service.apply_patch(patch.id, applied_by="tester")
    assert applied.status == "applied"
    updated = workflow_template_repository.get_template("workflow-template-1")
    assert updated is not None
    assert updated.step_specs[0]["summary"] == "Updated summary"
    assert updated.step_specs[0]["plan_steps"] == [
        "collect signal",
        "write operator brief",
    ]

    rolled_back = service.rollback_patch(patch.id, rolled_back_by="tester")
    assert rolled_back.status == "rolled_back"
    restored = workflow_template_repository.get_template("workflow-template-1")
    assert restored is not None
    assert restored.step_specs[0]["summary"] == "Original summary"
    assert restored.step_specs[0]["plan_steps"] == ["collect signal"]
