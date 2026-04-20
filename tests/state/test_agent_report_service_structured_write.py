from __future__ import annotations

from copaw.state import AgentReportRecord, AgentReportService


class _FakeReportRepository:
    def __init__(self) -> None:
        self.records: dict[str, AgentReportRecord] = {}

    def get_report(self, report_id: str) -> AgentReportRecord | None:
        return self.records.get(report_id)

    def upsert_report(self, report: AgentReportRecord) -> AgentReportRecord:
        self.records[report.id] = report
        return report


class _RetainService:
    def __init__(self) -> None:
        self.retained_ids: list[str] = []

    def retain_agent_report(self, report: AgentReportRecord) -> None:
        self.retained_ids.append(report.id)


class _Projector:
    def __init__(self) -> None:
        self.projected_ids: list[str] = []

    def project_report(
        self,
        *,
        report: AgentReportRecord,
        previous_report: AgentReportRecord | None = None,
    ) -> None:
        _ = previous_report
        self.projected_ids.append(report.id)


def test_agent_report_service_record_structured_report_persists_and_projects() -> None:
    repository = _FakeReportRepository()
    retain_service = _RetainService()
    projector = _Projector()
    service = AgentReportService(
        repository=repository,
        memory_retain_service=retain_service,
        graph_projection_service=projector,
    )
    report = AgentReportRecord(
        id="executor-report:assignment-1:runtime-1:turn-1",
        industry_instance_id="industry-1",
        assignment_id="assignment-1",
        task_id="task-1",
        owner_agent_id="agent-1",
        owner_role_id="role-1",
        report_kind="executor-terminal",
        headline="Ship Task 5 completed",
        summary="Executor completed the task.",
        result="completed",
        evidence_ids=["evidence-1"],
    )

    stored = service.record_structured_report(report)

    assert stored == report
    assert repository.get_report(report.id) == report
    assert retain_service.retained_ids == [report.id]
    assert projector.projected_ids == [report.id]
