# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.app.runtime_bootstrap_query import build_runtime_query_services


def _repositories() -> SimpleNamespace:
    return SimpleNamespace(
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=object(),
        schedule_repository=object(),
        backlog_item_repository=object(),
        assignment_repository=object(),
        goal_repository=object(),
        work_context_repository=object(),
        decision_request_repository=object(),
        memory_fact_index_repository=object(),
        memory_entity_view_repository=object(),
        memory_opinion_view_repository=object(),
        memory_reflection_run_repository=object(),
        memory_sleep_repository=object(),
        knowledge_chunk_repository=object(),
        strategy_memory_repository=object(),
        agent_report_repository=object(),
        routine_repository=object(),
        routine_run_repository=object(),
        industry_instance_repository=object(),
    )


def test_build_runtime_query_services_attaches_executor_runtime_service() -> None:
    executor_runtime_service = object()

    bootstrap = build_runtime_query_services(
        repositories=_repositories(),
        evidence_ledger=object(),
        runtime_event_bus=object(),
        human_assist_task_service=object(),
        environment_service=object(),
        executor_runtime_service=executor_runtime_service,
    )

    assert bootstrap[0]._executor_runtime_service is executor_runtime_service
