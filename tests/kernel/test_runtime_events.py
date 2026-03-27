# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.app.runtime_center import Phase1StateQueryService
from copaw.app.runtime_events import RuntimeEventBus
from copaw.evidence import EvidenceLedger
from copaw.kernel import KernelTask, KernelTaskStore
from copaw.state import DecisionRequestRecord, SQLiteStateStore, TaskRecord
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


def test_kernel_task_store_emits_task_decision_and_evidence_events(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    decision_repository = SqliteDecisionRequestRepository(state_store)
    evidence_ledger = EvidenceLedger()
    event_bus = RuntimeEventBus()
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        decision_request_repository=decision_repository,
        evidence_ledger=evidence_ledger,
        runtime_event_bus=event_bus,
    )

    task = KernelTask(
        id="task-1",
        title="Kernel event test",
        capability_ref="system:dispatch_goal",
        owner_agent_id="ops-agent",
        phase="waiting-confirm",
        risk_level="confirm",
    )
    task_store.upsert(task)
    task_store.ensure_decision_request(task)
    task_store.append_evidence(
        task,
        action_summary="kernel task completed",
        result_summary="done",
    )

    events = event_bus.list_events(after_id=0, limit=10)
    names = [event.event_name for event in events]
    assert "task.accepted" in names
    assert "decision.open" in names
    assert "evidence.recorded" in names


def test_state_query_review_transition_emits_runtime_event(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    decision_repository = SqliteDecisionRequestRepository(state_store)
    task_repository.upsert_task(
        TaskRecord(
            id="task-1",
            title="Decision task",
            task_type="system:delete_capability",
        ),
    )
    decision_repository.upsert_decision_request(
        DecisionRequestRecord(
            id="decision-1",
            task_id="task-1",
            decision_type="kernel-confirmation",
            risk_level="confirm",
            summary="Review me",
        ),
    )
    event_bus = RuntimeEventBus()
    service = Phase1StateQueryService(
        task_repository=task_repository,
        task_runtime_repository=SqliteTaskRuntimeRepository(state_store),
        schedule_repository=SqliteScheduleRepository(state_store),
        decision_request_repository=decision_repository,
        runtime_event_bus=event_bus,
    )

    payload = service.mark_decision_reviewing("decision-1")

    assert payload is not None
    assert payload["status"] == "reviewing"
    events = event_bus.list_events(after_id=0, limit=10)
    assert any(event.event_name == "decision.reviewing" for event in events)
