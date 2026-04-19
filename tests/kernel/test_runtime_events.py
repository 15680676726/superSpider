# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from copaw.app.runtime_center import (
    Phase1StateQueryService,
    RuntimeCenterStateQueryService,
)
from copaw.app.runtime_events import RuntimeEventBus
from copaw.evidence import EvidenceLedger, EvidenceRecord
from copaw.kernel import KernelTask, KernelTaskStore
from copaw.memory import ActivationResult, KnowledgeNeuron
from copaw.state import (
    DecisionRequestRecord,
    SQLiteStateStore,
    TaskRecord,
    TaskRuntimeRecord,
)
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


def test_kernel_task_store_append_evidence_preserves_explicit_kind(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    evidence_ledger = EvidenceLedger(tmp_path / "evidence.sqlite3")
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        evidence_ledger=evidence_ledger,
    )

    task = KernelTask(
        id="task-surface-transition-kind",
        title="Surface transition kind",
        capability_ref="tool:browser_use",
        owner_agent_id="ops-agent",
        risk_level="auto",
    )
    task_store.upsert(task)
    task_store.append_evidence(
        task,
        action_summary="record one surface transition",
        result_summary="typed into the current browser surface",
        kind="surface-transition",
        metadata={"evidence_kind": "surface-transition"},
    )

    records = evidence_ledger.list_by_task(task.id)

    assert len(records) == 1
    assert records[0].kind == "surface-transition"


def test_kernel_task_store_review_transition_emits_runtime_event(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    decision_repository = SqliteDecisionRequestRepository(state_store)
    evidence_ledger = EvidenceLedger()
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
    task_store = KernelTaskStore(
        task_repository=task_repository,
        decision_request_repository=decision_repository,
        task_runtime_repository=task_runtime_repository,
        evidence_ledger=evidence_ledger,
        runtime_event_bus=event_bus,
    )

    payload = task_store.mark_decision_reviewing("decision-1")

    assert payload is not None
    assert payload.status == "reviewing"
    events = event_bus.list_events(after_id=0, limit=10)
    assert any(event.event_name == "decision.reviewing" for event in events)


def test_state_query_decision_reads_do_not_expire_records(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    decision_repository = SqliteDecisionRequestRepository(state_store)
    task_repository.upsert_task(
        TaskRecord(
            id="task-expiring-1",
            title="Decision task",
            task_type="system:delete_capability",
        ),
    )
    decision_repository.upsert_decision_request(
        DecisionRequestRecord(
            id="decision-expiring-1",
            task_id="task-expiring-1",
            decision_type="kernel-confirmation",
            risk_level="confirm",
            summary="Read should not mutate me",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ),
    )
    event_bus = RuntimeEventBus()
    service = Phase1StateQueryService(
        task_repository=task_repository,
        task_runtime_repository=SqliteTaskRuntimeRepository(state_store),
        schedule_repository=SqliteScheduleRepository(state_store),
        decision_request_repository=decision_repository,
    )

    payload = service.get_decision_request("decision-expiring-1")

    assert payload is not None
    assert payload["status"] == "open"
    stored = decision_repository.get_decision_request("decision-expiring-1")
    assert stored is not None
    assert stored.status == "open"
    events = event_bus.list_events(after_id=0, limit=10)
    assert not any(event.event_name == "decision.expired" for event in events)


def test_runtime_center_activation_reads_do_not_write_decisions_evidence_or_events(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    decision_repository = SqliteDecisionRequestRepository(state_store)
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 4, 2, 8, 0, tzinfo=timezone.utc)
    task_repository.upsert_task(
        TaskRecord(
            id="task-activation-read-1",
            title="Activation read task",
            summary="Open activation path without writes.",
            task_type="system:dispatch_query",
            status="running",
            owner_agent_id="ops-agent",
            created_at=timestamp,
            updated_at=timestamp,
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-activation-read-1",
            runtime_status="active",
            current_phase="executing",
            risk_level="guarded",
            last_result_summary="Current activation query summary.",
            last_owner_agent_id="ops-agent",
            updated_at=timestamp,
        ),
    )
    decision_repository.upsert_decision_request(
        DecisionRequestRecord(
            id="decision-activation-read-1",
            task_id="task-activation-read-1",
            decision_type="guarded-browser-action",
            risk_level="guarded",
            summary="Approve guarded action",
        ),
    )
    evidence_ledger.append(
        EvidenceRecord(
            id="evidence-activation-read-1",
            task_id="task-activation-read-1",
            actor_ref="ops-agent",
            capability_ref="system:dispatch_query",
            risk_level="guarded",
            action_summary="seed evidence",
            result_summary="seed result",
            created_at=timestamp,
        ),
    )

    class _FakeMemoryActivationService:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def activate_for_query(self, **kwargs) -> ActivationResult:
            self.calls.append(kwargs)
            return ActivationResult(
                query=str(kwargs["query"]),
                scope_type="task",
                scope_id=str(kwargs["task_id"]),
                activated_neurons=[
                    KnowledgeNeuron(
                        neuron_id="neuron-1",
                        kind="fact",
                        scope_type="task",
                        scope_id=str(kwargs["task_id"]),
                        title="Activation fact",
                        source_refs=["memory://fact-1"],
                    ),
                ],
                support_refs=["memory://fact-1"],
                top_constraints=["keep reads pure"],
            )

    activation_service = _FakeMemoryActivationService()
    event_bus = RuntimeEventBus()
    service = RuntimeCenterStateQueryService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        schedule_repository=SqliteScheduleRepository(state_store),
        decision_request_repository=decision_repository,
        evidence_ledger=evidence_ledger,
        memory_activation_service=activation_service,
    )

    before_decisions = decision_repository.list_decision_requests(
        task_id="task-activation-read-1",
    )
    before_evidence_count = evidence_ledger.count_records()

    items = service.list_tasks(limit=10)
    detail = service.get_task_detail("task-activation-read-1")

    assert len(activation_service.calls) == 2
    assert activation_service.calls[0]["query"] == (
        "Activation read task | Current activation query summary. | "
        "Open activation path without writes."
    )
    task_item = next(item for item in items if item["id"] == "task-activation-read-1")
    assert task_item["activation"]["activated_count"] == 1
    assert detail is not None
    assert detail["activation"]["top_constraints"] == ["keep reads pure"]
    after_decisions = decision_repository.list_decision_requests(
        task_id="task-activation-read-1",
    )
    assert len(after_decisions) == len(before_decisions) == 1
    stored = decision_repository.get_decision_request("decision-activation-read-1")
    assert stored is not None
    assert stored.status == "open"
    assert evidence_ledger.count_records() == before_evidence_count == 1
    assert event_bus.list_events(after_id=0, limit=10) == []


@pytest.mark.asyncio
async def test_runtime_event_bus_close_drains_pending_notify_tasks() -> None:
    event_bus = RuntimeEventBus()
    waiter = asyncio.create_task(event_bus.wait_for_events(after_id=0, timeout=60.0))
    await asyncio.sleep(0)

    assert event_bus._waiters

    await event_bus.close()

    assert await asyncio.wait_for(waiter, timeout=0.2) == []
    assert not event_bus._waiters
