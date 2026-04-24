# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from types import SimpleNamespace

from copaw.evidence import EvidenceLedger
from copaw.kernel import KernelDispatcher, TaskDelegationService
from copaw.kernel.persistence import KernelTaskStore, decode_kernel_task_metadata
from copaw.state import SQLiteStateStore, TaskRecord, TaskRuntimeRecord
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteRuntimeFrameRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


class _FakeCapabilityService:
    async def execute_task(self, task):
        return {
            "success": True,
            "summary": f"Executed delegated task {task.id}",
        }


class _FakeIndustryService:
    def get_instance_detail(self, instance_id: str):
        if instance_id != "industry-1":
            return None
        return SimpleNamespace(
            team=SimpleNamespace(
                agents=[
                    {
                        "agent_id": "worker",
                        "role_id": "solution-lead",
                        "role_name": "Worker",
                    }
                ],
            ),
            agents=[
                {
                    "agent_id": "worker",
                    "industry_role_id": "solution-lead",
                    "role_name": "Worker",
                }
            ],
        )


def test_delegate_task_inherits_assignment_execution_envelope_without_mailbox_runtime(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.db")
    task_repository = SqliteTaskRepository(store)
    task_runtime_repository = SqliteTaskRuntimeRepository(store)
    runtime_frame_repository = SqliteRuntimeFrameRepository(store)
    decision_repository = SqliteDecisionRequestRepository(store)

    task_repository.upsert_task(
        TaskRecord(
            id="task-parent",
            goal_id="goal-1",
            assignment_id="assignment-1",
            lane_id="lane-ops",
            cycle_id="cycle-1",
            report_back_mode="summary",
            title="Parent assignment task",
            summary="Delegate the scoped work.",
            task_type="system:dispatch_query",
            status="running",
            owner_agent_id="execution-core-agent",
            industry_instance_id="industry-1",
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-parent",
            runtime_status="active",
            current_phase="executing",
            active_environment_id="session:console:execution-core-main",
            last_owner_agent_id="execution-core-agent",
        ),
    )

    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        runtime_frame_repository=runtime_frame_repository,
        decision_request_repository=decision_repository,
        evidence_ledger=evidence_ledger,
    )
    dispatcher = KernelDispatcher(
        task_store=task_store,
        capability_service=_FakeCapabilityService(),
    )
    service = TaskDelegationService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        kernel_dispatcher=dispatcher,
        evidence_ledger=evidence_ledger,
        industry_service=_FakeIndustryService(),
    )

    result = asyncio.run(
        service.delegate_task(
            "task-parent",
            title="Worker follow-up",
            owner_agent_id="execution-core-agent",
            target_agent_id="worker",
            prompt_text="Review the evidence and draft the next action.",
            execute=False,
            channel="console",
            industry_instance_id="industry-1",
            industry_role_id="solution-lead",
        ),
    )

    child_task = task_repository.get_task(result["child_task_id"])
    assert child_task is not None
    assert child_task.assignment_id == "assignment-1"
    metadata = decode_kernel_task_metadata(child_task.acceptance_criteria)
    assert metadata is not None
    payload_meta = metadata["payload"]["meta"]
    assert metadata["payload"]["assignment_id"] == "assignment-1"
    assert payload_meta["assignment_id"] == "assignment-1"
    assert payload_meta["execution_source"] == "executor-runtime"
    assert payload_meta["formal_surface"] is True
    assert "compatibility_mode" not in payload_meta

    assert result["mailbox_id"] is None
