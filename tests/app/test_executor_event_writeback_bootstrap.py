# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.app.runtime_bootstrap_execution import build_executor_event_writeback_service


def test_build_executor_event_writeback_service_threads_dependencies() -> None:
    evidence_ledger = object()
    assignment_service = object()
    agent_report_service = object()
    runtime_event_bus = object()
    executor_runtime_service = object()

    service = build_executor_event_writeback_service(
        evidence_ledger=evidence_ledger,
        assignment_service=assignment_service,
        agent_report_service=agent_report_service,
        runtime_event_bus=runtime_event_bus,
        executor_runtime_service=executor_runtime_service,
    )

    assert service._evidence_ledger is evidence_ledger
    assert service._assignment_service is assignment_service
    assert service._agent_report_service is agent_report_service
    assert service._runtime_event_bus is runtime_event_bus
    assert service._executor_runtime_service is executor_runtime_service
