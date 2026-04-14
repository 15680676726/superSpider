# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.memory import (
    DerivedMemoryIndexService,
    KnowledgeGraphService,
    MemoryReflectionService,
)
from copaw.state import (
    AgentReportService,
    AssignmentService,
    BacklogService,
    IndustryInstanceRecord,
    OperatingCycleService,
    SQLiteStateStore,
    TaskRecord,
    TaskRuntimeRecord,
    WorkContextService,
)
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteAssignmentRepository,
    SqliteBacklogItemRepository,
    SqliteIndustryInstanceRepository,
    SqliteKnowledgeChunkRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteMemoryRelationViewRepository,
    SqliteOperatingCycleRepository,
    SqliteWorkContextRepository,
)


def _build_services(tmp_path):
    store = SQLiteStateStore(tmp_path / "execution-graph.sqlite3")
    SqliteIndustryInstanceRepository(store).upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-1",
            label="Industry 1",
            owner_scope="industry",
            status="active",
        ),
    )
    knowledge_repo = SqliteKnowledgeChunkRepository(store)
    fact_repo = SqliteMemoryFactIndexRepository(store)
    entity_repo = SqliteMemoryEntityViewRepository(store)
    opinion_repo = SqliteMemoryOpinionViewRepository(store)
    relation_repo = SqliteMemoryRelationViewRepository(store)
    reflection_repo = SqliteMemoryReflectionRunRepository(store)
    derived = DerivedMemoryIndexService(
        fact_index_repository=fact_repo,
        entity_view_repository=entity_repo,
        opinion_view_repository=opinion_repo,
        relation_view_repository=relation_repo,
        reflection_run_repository=reflection_repo,
    )
    reflection = MemoryReflectionService(
        derived_index_service=derived,
        entity_view_repository=entity_repo,
        opinion_view_repository=opinion_repo,
        reflection_run_repository=reflection_repo,
    )
    knowledge = StateKnowledgeService(
        repository=knowledge_repo,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    graph = KnowledgeGraphService(
        knowledge_service=knowledge,
        derived_index_service=derived,
        knowledge_writeback_service=None,
    )
    backlog_service = BacklogService(
        repository=SqliteBacklogItemRepository(store),
        graph_projection_service=graph,
    )
    cycle_service = OperatingCycleService(
        repository=SqliteOperatingCycleRepository(store),
        graph_projection_service=graph,
    )
    assignment_service = AssignmentService(
        repository=SqliteAssignmentRepository(store),
        graph_projection_service=graph,
    )
    report_service = AgentReportService(
        repository=SqliteAgentReportRepository(store),
        graph_projection_service=graph,
    )
    work_context_service = WorkContextService(
        repository=SqliteWorkContextRepository(store),
        graph_projection_service=graph,
    )
    return (
        derived,
        backlog_service,
        cycle_service,
        assignment_service,
        report_service,
        work_context_service,
    )


def test_state_services_project_execution_graph_chain_into_truth_first_memory(tmp_path) -> None:
    (
        derived,
        backlog_service,
        cycle_service,
        assignment_service,
        report_service,
        work_context_service,
    ) = _build_services(tmp_path)
    work_context = work_context_service.ensure_context(
        context_id="ctx-1",
        title="Weekend variance continuity",
        summary="Shared continuity for the variance thread.",
        context_type="analysis-thread",
        status="active",
        owner_agent_id="agent-a",
        industry_instance_id="industry-1",
        context_key="thread:weekend-variance",
    )
    cycle = cycle_service.start_cycle(
        industry_instance_id="industry-1",
        label="Daily",
        cycle_kind="daily",
        status="active",
        focus_lane_ids=[],
        backlog_item_ids=[],
        source_ref="cycle:seed",
    )
    backlog = backlog_service.record_chat_writeback(
        industry_instance_id="industry-1",
        lane_id=None,
        title="Weekend variance follow-up",
        summary="Investigate the latest weekend variance.",
        priority=4,
        source_ref="operator:weekend-variance",
    )
    selected = backlog_service.mark_item_selected(
        backlog,
        cycle_id=cycle.id,
    )
    assignment = assignment_service.ensure_assignments(
        industry_instance_id="industry-1",
        cycle_id=cycle.id,
        specs=[
            {
                "backlog_item_id": selected.id,
                "lane_id": None,
                "owner_agent_id": "agent-a",
                "owner_role_id": "role:agent-a",
                "title": "Investigate weekend variance",
                "summary": "Run the follow-up investigation.",
                "status": "running",
                "metadata": {"work_context_id": work_context.id},
            }
        ],
    )[0]
    materialized = backlog_service.mark_item_materialized(
        selected,
        cycle_id=cycle.id,
        goal_id=None,
        assignment_id=assignment.id,
    )
    task = TaskRecord(
        id="task-1",
        title="Investigate weekend variance",
        summary="Run the follow-up investigation.",
        task_type="system:dispatch_query",
        status="completed",
        industry_instance_id="industry-1",
        assignment_id=assignment.id,
        cycle_id=cycle.id,
        lane_id=None,
        owner_agent_id="agent-a",
        work_context_id=work_context.id,
    )
    runtime = TaskRuntimeRecord(
        task_id=task.id,
        runtime_status="terminated",
        current_phase="completed",
        last_result_summary="Weekend variance root cause was confirmed.",
    )

    report = report_service.record_task_terminal_report(
        task=task,
        runtime=runtime,
        assignment=assignment,
        evidence_ids=["evidence-1"],
        decision_ids=[],
        owner_role_id="role:agent-a",
    )

    assert report is not None

    industry_fact_ids = {
        entry.id
        for entry in derived.list_fact_entries(
            scope_type="industry",
            scope_id="industry-1",
            limit=None,
            include_inactive=True,
        )
    }
    work_context_fact_ids = {
        entry.id
        for entry in derived.list_fact_entries(
            scope_type="work_context",
            scope_id=work_context.id,
            limit=None,
            include_inactive=True,
        )
    }
    industry_relation_pairs = {
        (entry.source_node_id, entry.relation_kind, entry.target_node_id)
        for entry in derived.list_relation_views(
            scope_type="industry",
            scope_id="industry-1",
            limit=None,
            include_inactive=True,
        )
    }
    work_context_relation_pairs = {
        (entry.source_node_id, entry.relation_kind, entry.target_node_id)
        for entry in derived.list_relation_views(
            scope_type="work_context",
            scope_id=work_context.id,
            limit=None,
            include_inactive=True,
        )
    }

    assert {
        f"backlog:{materialized.id}",
        f"cycle:{cycle.id}",
        f"assignment:{assignment.id}",
    } <= industry_fact_ids
    assert {
        f"work-context:{work_context.id}",
        f"report:{report.id}",
    } <= work_context_fact_ids
    assert (
        f"backlog:{materialized.id}",
        "belongs_to",
        f"cycle:{cycle.id}",
    ) in industry_relation_pairs
    assert (
        f"backlog:{materialized.id}",
        "produces",
        f"assignment:{assignment.id}",
    ) in industry_relation_pairs
    assert (
        f"assignment:{assignment.id}",
        "belongs_to",
        f"cycle:{cycle.id}",
    ) in industry_relation_pairs
    assert (
        f"assignment:{assignment.id}",
        "belongs_to",
        f"work-context:{work_context.id}",
    ) in industry_relation_pairs
    assert (
        f"assignment:{assignment.id}",
        "produces",
        f"report:{report.id}",
    ) in work_context_relation_pairs
    assert (
        f"report:{report.id}",
        "belongs_to",
        f"work-context:{work_context.id}",
    ) in work_context_relation_pairs


def test_backlog_projection_invalidates_old_cycle_relation_when_item_moves(tmp_path) -> None:
    derived, backlog_service, cycle_service, _assignment_service, _report_service, _work_context_service = _build_services(
        tmp_path,
    )
    cycle_a = cycle_service.start_cycle(
        industry_instance_id="industry-1",
        label="Daily",
        cycle_kind="daily",
        status="active",
        focus_lane_ids=[],
        backlog_item_ids=[],
        source_ref="cycle:a",
    )
    cycle_b = cycle_service.start_cycle(
        industry_instance_id="industry-1",
        label="Daily",
        cycle_kind="event",
        status="planned",
        focus_lane_ids=[],
        backlog_item_ids=[],
        source_ref="cycle:b",
    )
    backlog = backlog_service.record_chat_writeback(
        industry_instance_id="industry-1",
        lane_id=None,
        title="Weekend variance follow-up",
        summary="Investigate the latest weekend variance.",
        priority=4,
        source_ref="operator:weekend-variance",
    )

    selected_a = backlog_service.mark_item_selected(
        backlog,
        cycle_id=cycle_a.id,
    )
    backlog_service.mark_item_selected(
        selected_a,
        cycle_id=cycle_b.id,
    )

    active_pairs = {
        (entry.source_node_id, entry.relation_kind, entry.target_node_id)
        for entry in derived.list_relation_views(
            scope_type="industry",
            scope_id="industry-1",
            limit=None,
        )
    }
    all_pairs = {
        (entry.source_node_id, entry.relation_kind, entry.target_node_id): entry
        for entry in derived.list_relation_views(
            scope_type="industry",
            scope_id="industry-1",
            limit=None,
            include_inactive=True,
        )
    }

    assert (
        f"backlog:{backlog.id}",
        "belongs_to",
        f"cycle:{cycle_b.id}",
    ) in active_pairs
    old_pair = (
        f"backlog:{backlog.id}",
        "belongs_to",
        f"cycle:{cycle_a.id}",
    )
    assert old_pair in all_pairs
    assert all_pairs[old_pair].metadata["status"] == "superseded"
