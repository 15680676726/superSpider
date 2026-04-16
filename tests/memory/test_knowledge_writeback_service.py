# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.memory import (
    DerivedMemoryIndexService,
    MemoryActivationService,
    MemoryReflectionService,
    MemorySleepInferenceService,
    MemorySleepService,
)
from copaw.memory.knowledge_writeback_service import KnowledgeWritebackService
from copaw.memory.knowledge_graph_models import (
    KnowledgeGraphNode,
    KnowledgeGraphRelation,
    KnowledgeGraphScope,
    KnowledgeGraphWritebackChange,
)
from copaw.state import (
    AgentReportRecord,
    AssignmentRecord,
    BacklogItemRecord,
    OperatingCycleRecord,
    SQLiteStateStore,
    WorkContextRecord,
)
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.repositories import (
    SqliteKnowledgeChunkRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteMemoryRelationViewRepository,
    SqliteMemorySleepRepository,
)


def _report(
    *,
    headline: str = "Warehouse approval review",
    result: str = "completed",
    findings: list[str] | None = None,
    uncertainties: list[str] | None = None,
    recommendation: str | None = None,
    evidence_ids: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> AgentReportRecord:
    return AgentReportRecord(
        industry_instance_id="industry-1",
        work_context_id="ctx-1",
        cycle_id="cycle-1",
        assignment_id="assignment-1",
        lane_id="lane-ops",
        owner_agent_id="agent-a",
        owner_role_id="role:agent-a",
        headline=headline,
        summary=f"{headline} summary",
        result=result,
        findings=list(findings or []),
        uncertainties=list(uncertainties or []),
        recommendation=recommendation,
        evidence_ids=list(evidence_ids or []),
        metadata=dict(metadata or {}),
    )


def _build_persistence_services(tmp_path):
    store = SQLiteStateStore(tmp_path / "knowledge-writeback.sqlite3")
    knowledge_repo = SqliteKnowledgeChunkRepository(store)
    fact_repo = SqliteMemoryFactIndexRepository(store)
    entity_repo = SqliteMemoryEntityViewRepository(store)
    opinion_repo = SqliteMemoryOpinionViewRepository(store)
    relation_repo = SqliteMemoryRelationViewRepository(store)
    reflection_repo = SqliteMemoryReflectionRunRepository(store)
    sleep_repo = SqliteMemorySleepRepository(store)
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
    sleep = MemorySleepService(
        repository=sleep_repo,
        knowledge_service=knowledge,
        strategy_memory_service=None,
        derived_index_service=derived,
        reflection_service=reflection,
        inference_service=MemorySleepInferenceService(),
    )
    knowledge.set_memory_sleep_service(sleep)
    activation = MemoryActivationService(
        derived_index_service=derived,
    )
    service = KnowledgeWritebackService(
        knowledge_service=knowledge,
        derived_index_service=derived,
        relation_view_repository=relation_repo,
        reflection_service=reflection,
    )
    return service, knowledge, derived, activation, sleep


def test_knowledge_writeback_service_builds_report_writeback_with_fact_opinion_evidence_and_relations() -> None:
    service = KnowledgeWritebackService()
    report = _report(
        findings=["Warehouse approval is verified."],
        recommendation="Keep the release paused until finance handoff clears.",
        evidence_ids=["evidence-1"],
        metadata={"verified_findings": True},
    )

    change = service.build_report_writeback(report=report)

    assert change.scope.scope_type == "work_context"
    assert change.scope.scope_id == "ctx-1"
    assert {"report", "event", "fact", "opinion", "evidence"} <= {
        item.node_type
        for item in change.upsert_nodes
    }
    assert {"produces", "derived_from"} <= {
        item.relation_type
        for item in change.upsert_relations
    }


def test_knowledge_writeback_service_downgrades_unverified_report_findings_to_opinion() -> None:
    service = KnowledgeWritebackService()
    report = _report(
        findings=["Weekend anomaly probably came from the staffing change."],
        metadata={"verified_findings": False},
    )

    change = service.build_report_writeback(report=report)
    finding_nodes = [
        item
        for item in change.upsert_nodes
        if item.node_id.startswith(f"report-finding:{report.id}:")
    ]

    assert finding_nodes
    assert {item.node_type for item in finding_nodes} == {"opinion"}


def test_knowledge_writeback_service_builds_failure_and_recovery_patterns_from_execution_outcome() -> None:
    service = KnowledgeWritebackService()

    change = service.build_execution_outcome_writeback(
        scope_type="task",
        scope_id="task-1",
        outcome_ref="runtime-1",
        outcome="failed",
        summary="Filesystem sync failed on permission error.",
        capability_ref="filesystem",
        evidence_refs=["evidence-1"],
        recovery_summary="Retry after refreshing the workspace lease.",
    )

    assert {"runtime_outcome", "failure_pattern", "recovery_pattern"} <= {
        item.node_type
        for item in change.upsert_nodes
    }
    assert {"indicates", "recovers_with"} <= {
        item.relation_type
        for item in change.upsert_relations
    }


def test_knowledge_writeback_service_keeps_human_boundary_writeback_out_of_fact_layer() -> None:
    service = KnowledgeWritebackService()

    change = service.build_human_boundary_writeback(
        scope_type="industry",
        scope_id="industry-1",
        boundary_kind="approval",
        summary="Operator approved the vendor outreach trial.",
        evidence_refs=["evidence-1"],
        source_refs=["decision:approval-1"],
    )

    assert [item.node_type for item in change.upsert_nodes] == ["approval"]
    assert all(item.node_type != "fact" for item in change.upsert_nodes)


def test_knowledge_writeback_service_persists_execution_outcome_into_truth_first_memory(
    tmp_path,
) -> None:
    service, knowledge, derived, activation, _sleep = _build_persistence_services(tmp_path)

    change = service.build_execution_outcome_writeback(
        scope_type="task",
        scope_id="task-1",
        outcome_ref="runtime-1",
        outcome="failed",
        summary="Filesystem sync failed on permission error.",
        capability_ref="filesystem",
        evidence_refs=["evidence-1"],
        recovery_summary="Retry after refreshing the workspace lease.",
    )

    service.apply_change(change)

    chunks = knowledge.list_memory(
        scope_type="task",
        scope_id="task-1",
        limit=None,
    )
    assert any(item.source_ref == "knowledge-graph-node:runtime-outcome:runtime-1" for item in chunks)

    fact_entries = derived.list_fact_entries(
        scope_type="task",
        scope_id="task-1",
        limit=None,
        include_inactive=True,
    )
    assert any(
        entry.id == "runtime-outcome:runtime-1"
        and (entry.metadata or {}).get("knowledge_graph_node_type") == "runtime_outcome"
        for entry in fact_entries
    )

    relation_views = derived.list_relation_views(
        scope_type="task",
        scope_id="task-1",
        limit=None,
        include_inactive=True,
    )
    assert {"indicates", "recovers_with"} <= {view.relation_kind for view in relation_views}

    activation_result = activation.activate_for_query(
        query="permission error workspace lease retry",
        scope_type="task",
        scope_id="task-1",
        include_strategy=False,
        include_reports=False,
        limit=10,
    )

    assert any(
        (neuron.metadata or {}).get("knowledge_graph_node_type") == "runtime_outcome"
        for neuron in activation_result.activated_neurons
    )
    assert "indicates" in activation_result.top_relation_kinds


def test_knowledge_writeback_service_applies_invalidation_to_future_activation(
    tmp_path,
) -> None:
    service, _knowledge, derived, activation, _sleep = _build_persistence_services(tmp_path)
    scope = KnowledgeGraphScope(scope_type="task", scope_id="task-2")

    initial = KnowledgeGraphWritebackChange(
        scope=scope,
        upsert_nodes=[
            KnowledgeGraphNode(
                node_id="fact-old",
                node_type="fact",
                scope=scope,
                title="Old blocker",
                summary="Old blocker summary",
                content_excerpt="old blocker content",
                entity_keys=["blocker"],
                evidence_refs=["evidence-old"],
            ),
        ],
        upsert_relations=[
            KnowledgeGraphRelation(
                relation_id="rel-old",
                relation_type="indicates",
                source_id="fact-old",
                target_id="fact-old-target",
                scope=scope,
                evidence_refs=["evidence-old"],
            ),
        ],
    )
    service.apply_change(initial)

    replacement = KnowledgeGraphWritebackChange(
        scope=scope,
        upsert_nodes=[
            KnowledgeGraphNode(
                node_id="fact-new",
                node_type="fact",
                scope=scope,
                title="New blocker",
                summary="New blocker summary",
                content_excerpt="new blocker content",
                entity_keys=["blocker"],
                evidence_refs=["evidence-new"],
            ),
        ],
        invalidate_node_ids=["fact-old"],
        invalidate_relation_ids=["rel-old"],
    )
    service.apply_change(replacement)

    active_entries = derived.list_fact_entries(
        scope_type="task",
        scope_id="task-2",
        limit=None,
    )
    assert [entry.id for entry in active_entries] == ["fact-new"]

    all_entries = derived.list_fact_entries(
        scope_type="task",
        scope_id="task-2",
        limit=None,
        include_inactive=True,
    )
    old_entry = next(entry for entry in all_entries if entry.id == "fact-old")
    assert old_entry.is_latest is False
    assert (old_entry.metadata or {}).get("knowledge_graph_status") == "superseded"

    active_relations = derived.list_relation_views(
        scope_type="task",
        scope_id="task-2",
        limit=None,
    )
    assert not any(view.relation_id == "rel-old" for view in active_relations)

    activation_result = activation.activate_for_query(
        query="new blocker content",
        scope_type="task",
        scope_id="task-2",
        include_strategy=False,
        include_reports=False,
        limit=10,
    )
    assert any(neuron.title == "New blocker" for neuron in activation_result.activated_neurons)
    assert all(neuron.title != "Old blocker" for neuron in activation_result.activated_neurons)


def test_knowledge_writeback_service_projects_execution_chain_nodes_and_edges() -> None:
    service = KnowledgeWritebackService()
    cycle = OperatingCycleRecord(
        id="cycle-1",
        industry_instance_id="industry-1",
        title="Daily operating cycle",
        summary="Drive the daily execution chain.",
        status="active",
        focus_lane_ids=["lane-ops"],
        backlog_item_ids=["backlog-1"],
        assignment_ids=["assignment-1"],
    )
    backlog = BacklogItemRecord(
        id="backlog-1",
        industry_instance_id="industry-1",
        lane_id="lane-ops",
        cycle_id=cycle.id,
        assignment_id="assignment-1",
        title="Weekend variance follow-up",
        summary="Investigate the latest weekend variance.",
        status="selected",
        priority=4,
        source_kind="operator",
        source_ref="operator:weekend-variance",
    )
    assignment = AssignmentRecord(
        id="assignment-1",
        industry_instance_id="industry-1",
        cycle_id=cycle.id,
        lane_id="lane-ops",
        backlog_item_id=backlog.id,
        owner_agent_id="agent-a",
        owner_role_id="role:agent-a",
        title="Investigate weekend variance",
        summary="Run the follow-up investigation.",
        status="running",
        metadata={"work_context_id": "ctx-1"},
    )
    work_context = WorkContextRecord(
        id="ctx-1",
        title="Weekend variance continuity",
        summary="Shared continuity for the variance thread.",
        context_type="analysis-thread",
        status="active",
        industry_instance_id="industry-1",
        owner_agent_id="agent-a",
        context_key="thread:weekend-variance",
    )
    report = _report(
        headline="Weekend variance resolved",
        result="completed",
        findings=["Weekend variance root cause was confirmed."],
        evidence_ids=["evidence-1"],
        metadata={"verified_findings": True},
    ).model_copy(
        update={
            "assignment_id": assignment.id,
            "owner_agent_id": assignment.owner_agent_id,
            "owner_role_id": assignment.owner_role_id,
            "work_context_id": work_context.id,
        },
    )

    change = service.merge_changes(
        service.build_cycle_writeback(cycle=cycle),
        service.build_backlog_writeback(item=backlog),
        service.build_assignment_writeback(assignment=assignment),
        service.build_work_context_writeback(context=work_context),
        service.build_report_writeback(report=report),
        service.build_execution_outcome_writeback(
            scope_type="task",
            scope_id="task-1",
            outcome_ref="runtime-1",
            outcome="failed",
            summary="Runtime hit a recoverable filesystem error.",
            work_context_id=work_context.id,
        ),
    )

    node_ids = {item.node_id for item in change.upsert_nodes}
    relation_pairs = {
        (item.source_id, item.relation_type, item.target_id)
        for item in change.upsert_relations
    }

    assert {
        f"cycle:{cycle.id}",
        f"backlog:{backlog.id}",
        f"assignment:{assignment.id}",
        f"work-context:{work_context.id}",
        f"report:{report.id}",
        "runtime-outcome:runtime-1",
    } <= node_ids
    assert (
        f"backlog:{backlog.id}",
        "belongs_to",
        f"cycle:{cycle.id}",
    ) in relation_pairs
    assert (
        f"backlog:{backlog.id}",
        "produces",
        f"assignment:{assignment.id}",
    ) in relation_pairs
    assert (
        f"assignment:{assignment.id}",
        "belongs_to",
        f"cycle:{cycle.id}",
    ) in relation_pairs
    assert (
        f"assignment:{assignment.id}",
        "belongs_to",
        f"work-context:{work_context.id}",
    ) in relation_pairs
    assert (
        f"assignment:{assignment.id}",
        "produces",
        f"report:{report.id}",
    ) in relation_pairs
    assert (
        f"report:{report.id}",
        "belongs_to",
        f"work-context:{work_context.id}",
    ) in relation_pairs
    assert (
        "runtime-outcome:runtime-1",
        "belongs_to",
        f"work-context:{work_context.id}",
    ) in relation_pairs


def test_knowledge_writeback_service_invalidates_stale_execution_relations_when_links_move() -> None:
    service = KnowledgeWritebackService()
    previous = AssignmentRecord(
        id="assignment-1",
        industry_instance_id="industry-1",
        cycle_id="cycle-1",
        lane_id="lane-ops",
        backlog_item_id="backlog-1",
        owner_agent_id="agent-a",
        title="Investigate weekend variance",
        summary="Old execution link",
        status="queued",
        metadata={"work_context_id": "ctx-1"},
    )
    current = previous.model_copy(
        update={
            "cycle_id": "cycle-2",
            "metadata": {"work_context_id": "ctx-2"},
            "status": "running",
        },
    )

    change = service.build_assignment_writeback(
        assignment=current,
        previous_assignment=previous,
    )

    relation_pairs = {
        (item.source_id, item.relation_type, item.target_id)
        for item in change.upsert_relations
    }

    assert (
        f"assignment:{current.id}",
        "belongs_to",
        "cycle:cycle-2",
    ) in relation_pairs
    assert (
        f"assignment:{current.id}",
        "belongs_to",
        "work-context:ctx-2",
    ) in relation_pairs
    assert len(change.invalidate_relation_ids) == 2


def test_knowledge_writeback_service_daytime_refreshes_work_context_overlay(tmp_path) -> None:
    service, _knowledge, _derived, _activation, sleep = _build_persistence_services(tmp_path)
    report = _report(
        headline="白天写回收口",
        findings=["当前需要先完成财务复核，再继续外呼审批。"],
        recommendation="先补齐财务证据，再继续外呼审批。",
        evidence_ids=["evidence-1"],
        metadata={"verified_findings": True},
    )

    change = service.build_report_writeback(report=report)
    service.apply_change(change)

    overlay = sleep.get_active_work_context_overlay("ctx-1")
    assert overlay is not None
    assert overlay.work_context_id == "ctx-1"
    assert "财务复核" in " ".join(
        [
            overlay.headline,
            overlay.summary,
            overlay.focus_summary,
            *overlay.active_focuses,
            *overlay.active_constraints,
        ],
    )
