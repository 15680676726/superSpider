from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from copaw.app.runtime_events import RuntimeEventBus
from copaw.evidence import EvidenceLedger
from copaw.kernel.executor_event_ingest_service import ExecutorEventIngestContext
from copaw.kernel.executor_event_writeback_service import ExecutorEventWritebackService
from copaw.kernel.executor_runtime_port import ExecutorNormalizedEvent
from copaw.state import SQLiteStateStore
from copaw.state.executor_runtime_service import ExecutorRuntimeService
from copaw.state.external_runtime_service import ExternalCapabilityRuntimeService
from copaw.state.models_goals_tasks import AgentReportRecord
from copaw.state.repositories import SqliteExternalCapabilityRuntimeRepository


def _context(**overrides: object) -> ExecutorEventIngestContext:
    base = {
        "runtime_id": "runtime-1",
        "executor_id": "codex",
        "assignment_id": "assignment-1",
        "task_id": "task-1",
        "industry_instance_id": "industry-1",
        "thread_id": "thread-1",
        "turn_id": "turn-1",
        "owner_agent_id": "agent-1",
        "owner_role_id": "role-1",
        "assignment_title": "Ship Task 5",
        "assignment_summary": "Implement executor event writeback",
        "risk_level": "guarded",
    }
    base.update(overrides)
    return ExecutorEventIngestContext(**base)


class _FakeAssignmentService:
    def __init__(self) -> None:
        self.attach_calls: list[tuple[str, list[str]]] = []

    def attach_evidence_ids(self, assignment: str, *, evidence_ids: list[str]):
        self.attach_calls.append((assignment, list(evidence_ids)))
        return None


class _FakeReportRepository:
    def __init__(self) -> None:
        self.records: dict[str, AgentReportRecord] = {}

    def get_report(self, report_id: str) -> AgentReportRecord | None:
        return self.records.get(report_id)

    def upsert_report(self, report: AgentReportRecord) -> AgentReportRecord:
        self.records[report.id] = report
        return report


@dataclass
class _RetainService:
    retained_ids: list[str]

    def retain_agent_report(self, report: AgentReportRecord) -> None:
        self.retained_ids.append(report.id)


class _FakeReportService:
    def __init__(self) -> None:
        self._repository = _FakeReportRepository()
        self._projected_ids: list[str] = []
        self._memory_retain_service = _RetainService([])

    def _project_report(
        self,
        report: AgentReportRecord,
        *,
        previous_report: AgentReportRecord | None = None,
    ) -> None:
        _ = previous_report
        self._projected_ids.append(report.id)


def _build_executor_runtime_service(tmp_path) -> ExecutorRuntimeService:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteExternalCapabilityRuntimeRepository(store)
    external_runtime_service = ExternalCapabilityRuntimeService(repository=repository)
    return ExecutorRuntimeService(
        external_runtime_service=external_runtime_service,
        state_store=store,
    )


def test_writeback_records_evidence_and_attaches_it_to_assignment() -> None:
    evidence_ledger = EvidenceLedger()
    assignment_service = _FakeAssignmentService()
    report_service = _FakeReportService()
    runtime_event_bus = RuntimeEventBus()
    service = ExecutorEventWritebackService(
        evidence_ledger=evidence_ledger,
        assignment_service=assignment_service,
        agent_report_service=report_service,
        runtime_event_bus=runtime_event_bus,
    )

    result = service.ingest_and_writeback(
        context=_context(),
        event=ExecutorNormalizedEvent(
            event_type="evidence_emitted",
            source_type="commandExecution",
            payload={
                "command": "pytest tests/kernel/test_executor_event_writeback_service.py -q",
                "exit_code": 0,
                "status": "completed",
            },
            raw_method="item/completed",
        ),
    )

    stored = evidence_ledger.list_by_task("task-1")
    assert len(stored) == 1
    assert stored[0].kind == "executor-command"
    assert result.evidence_record is not None
    assert result.evidence_record.id == stored[0].id
    assert assignment_service.attach_calls == [("assignment-1", [stored[0].id])]
    events = runtime_event_bus.list_events()
    assert events[-1].topic == "executor-runtime"
    assert events[-1].payload["evidence_id"] == stored[0].id
    assert result.report_record is None


def test_writeback_records_terminal_report_with_evidence_ids() -> None:
    evidence_ledger = EvidenceLedger()
    assignment_service = _FakeAssignmentService()
    report_service = _FakeReportService()
    runtime_event_bus = RuntimeEventBus()
    service = ExecutorEventWritebackService(
        evidence_ledger=evidence_ledger,
        assignment_service=assignment_service,
        agent_report_service=report_service,
        runtime_event_bus=runtime_event_bus,
    )

    evidence_result = service.ingest_and_writeback(
        context=_context(),
        event=ExecutorNormalizedEvent(
            event_type="evidence_emitted",
            source_type="fileChange",
            payload={
                "path": "src/copaw/kernel/runtime_coordination.py",
                "change_type": "modified",
                "summary": "Wired executor runtime coordination",
            },
            raw_method="item/completed",
        ),
    )
    terminal_result = service.ingest_and_writeback(
        context=_context(),
        event=ExecutorNormalizedEvent(
            event_type="task_completed",
            source_type="turn",
            payload={
                "summary": "Executor finished assignment successfully.",
            },
            raw_method="turn/completed",
        ),
    )

    assert evidence_result.evidence_record is not None
    assert terminal_result.report_record is not None
    report = terminal_result.report_record
    assert report.assignment_id == "assignment-1"
    assert report.result == "completed"
    assert evidence_result.evidence_record.id in report.evidence_ids
    assert report.id in report_service._projected_ids
    assert report.id in report_service._memory_retain_service.retained_ids
    events = runtime_event_bus.list_events()
    assert events[-1].payload["report_id"] == report.id
    assert report_service._repository.get_report(report.id) == report


def test_writeback_persists_executor_event_records_into_formal_runtime_truth(
    tmp_path,
) -> None:
    evidence_ledger = EvidenceLedger()
    assignment_service = _FakeAssignmentService()
    report_service = _FakeReportService()
    runtime_event_bus = RuntimeEventBus()
    executor_runtime_service = _build_executor_runtime_service(tmp_path)
    runtime = executor_runtime_service.create_or_reuse_runtime(
        executor_id="codex-app-server",
        protocol_kind="app_server",
        scope_kind="assignment",
        assignment_id="assignment-1",
        role_id="role-1",
    )
    executor_runtime_service.mark_runtime_ready(
        runtime.runtime_id,
        thread_id="thread-1",
        turn_id="turn-1",
    )
    service = ExecutorEventWritebackService(
        evidence_ledger=evidence_ledger,
        assignment_service=assignment_service,
        agent_report_service=report_service,
        runtime_event_bus=runtime_event_bus,
        executor_runtime_service=executor_runtime_service,
    )

    service.ingest_and_writeback(
        context=_context(runtime_id=runtime.runtime_id),
        event=ExecutorNormalizedEvent(
            event_type="evidence_emitted",
            source_type="fileChange",
            payload={
                "thread_id": "thread-1",
                "turn_id": "turn-1",
                "path": "src/copaw/kernel/runtime_coordination.py",
                "change_type": "modified",
                "summary": "Wired executor runtime coordination",
            },
            raw_method="item/completed",
        ),
    )
    service.ingest_and_writeback(
        context=_context(runtime_id=runtime.runtime_id),
        event=ExecutorNormalizedEvent(
            event_type="task_completed",
            source_type="turn",
            payload={
                "thread_id": "thread-1",
                "turn_id": "turn-1",
                "summary": "Executor finished assignment successfully.",
            },
            raw_method="turn/completed",
        ),
    )

    stored_events = executor_runtime_service.list_event_records(thread_id="thread-1")
    stored_turns = executor_runtime_service.list_turn_records(thread_id="thread-1")

    assert [item.event_type for item in stored_events] == [
        "task_completed",
        "evidence_emitted",
    ]
    assert stored_events[0].runtime_id == runtime.runtime_id
    assert stored_events[0].turn_id == "turn-1"
    assert stored_turns[0].turn_status == "completed"
    assert stored_turns[0].summary == "Executor finished assignment successfully."
