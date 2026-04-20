# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

import pytest

from copaw.evidence import EvidenceLedger
from copaw.kernel import KernelTask, KernelTaskStore
from copaw.learning import LearningEngine, LearningService
from copaw.state import (
    AssignmentRecord,
    IndustryInstanceRecord,
    OperatingLaneRecord,
    SQLiteStateStore,
    StrategyMemoryRecord,
)
from copaw.state.repositories import (
    SqliteAssignmentRepository,
    SqliteDecisionRequestRepository,
    SqliteIndustryInstanceRepository,
    SqliteOperatingLaneRepository,
    SqliteStrategyMemoryRepository,
    SqliteSurfaceCapabilityTwinRepository,
    SqliteSurfacePlaybookRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)


LIVE_SURFACE_GRAPH_SOAK_SKIP_REASON = (
    "Set COPAW_RUN_SURFACE_GRAPH_SOAK=1 to run surface graph soak coverage "
    "(opt-in; not part of default regression coverage)."
)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _close_if_possible(value: object) -> None:
    closer = getattr(value, "close", None)
    if callable(closer):
        closer()


def _seed_surface_learning_context(
    *,
    industry_instance_repository: SqliteIndustryInstanceRepository,
    strategy_repository: SqliteStrategyMemoryRepository,
    operating_lane_repository: SqliteOperatingLaneRepository,
    assignment_repository: SqliteAssignmentRepository,
) -> None:
    industry_instance_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-surface-soak",
            label="Surface soak industry",
            summary="Surface graph soak verification industry.",
            owner_scope="industry-surface-soak-owner",
            status="running",
        ),
    )
    strategy_repository.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:surface-soak",
            scope_type="industry",
            scope_id="industry-surface-soak",
            industry_instance_id="industry-surface-soak",
            title="Surface soak strategy",
            mission="Publish approved work before low-value maintenance.",
            current_focuses=["publish listing", "refresh published state"],
            priority_order=["publish listing", "refresh inventory"],
            evidence_requirements=["published confirmation"],
            status="active",
        ),
    )
    operating_lane_repository.upsert_lane(
        OperatingLaneRecord(
            id="lane:surface-soak",
            industry_instance_id="industry-surface-soak",
            lane_key="publishing",
            title="Publishing lane",
            summary="Push approved work live with confirmation.",
            owner_agent_id="agent:surface-owner",
            metadata={"evidence_expectations": ["published confirmation"]},
        ),
    )
    assignment_repository.upsert_assignment(
        AssignmentRecord(
            id="assignment:scope-a",
            industry_instance_id="industry-surface-soak",
            lane_id="lane:surface-soak",
            owner_agent_id="agent:surface-owner",
            title="Publish listing A",
            summary="Publish the highest-priority listing in scope A.",
            metadata={"success_criteria": ["publish listing"]},
        ),
    )
    assignment_repository.upsert_assignment(
        AssignmentRecord(
            id="assignment:scope-b",
            industry_instance_id="industry-surface-soak",
            lane_id="lane:surface-soak",
            owner_agent_id="agent:surface-owner",
            title="Refresh listing B",
            summary="Refresh the published state in scope B.",
            metadata={"success_criteria": ["refresh inventory"]},
        ),
    )


def _build_surface_learning_stack(base_dir: Path) -> dict[str, object]:
    state_store = SQLiteStateStore(base_dir / "surface-soak-state.sqlite3")
    evidence_ledger = EvidenceLedger(base_dir / "surface-soak-evidence.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    industry_instance_repository = SqliteIndustryInstanceRepository(state_store)
    strategy_repository = SqliteStrategyMemoryRepository(state_store)
    operating_lane_repository = SqliteOperatingLaneRepository(state_store)
    assignment_repository = SqliteAssignmentRepository(state_store)
    twin_repository = SqliteSurfaceCapabilityTwinRepository(state_store)
    playbook_repository = SqliteSurfacePlaybookRepository(state_store)
    learning_service = LearningService(
        engine=LearningEngine(base_dir / "surface-soak-learning.sqlite3"),
        task_repository=task_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
    )
    learning_service.configure_surface_learning(
        surface_capability_twin_repository=twin_repository,
        surface_playbook_repository=playbook_repository,
        strategy_memory_repository=strategy_repository,
        operating_lane_repository=operating_lane_repository,
        assignment_repository=assignment_repository,
        scope_snapshot_service=None,
    )
    task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
        learning_service=learning_service,
    )
    return {
        "state_store": state_store,
        "evidence_ledger": evidence_ledger,
        "task_repository": task_repository,
        "learning_service": learning_service,
        "task_store": task_store,
        "industry_instance_repository": industry_instance_repository,
        "strategy_repository": strategy_repository,
        "operating_lane_repository": operating_lane_repository,
        "assignment_repository": assignment_repository,
        "twin_repository": twin_repository,
        "playbook_repository": playbook_repository,
    }


def _build_task(
    *,
    task_id: str,
    title: str,
    capability_ref: str,
    work_context_id: str,
    assignment_id: str,
) -> KernelTask:
    return KernelTask(
        id=task_id,
        title=title,
        capability_ref=capability_ref,
        owner_agent_id="agent:surface-owner",
        work_context_id=work_context_id,
        phase="executing",
        risk_level="auto",
        payload={
            "industry_instance_id": "industry-surface-soak",
            "lane_id": "lane:surface-soak",
            "assignment_id": assignment_id,
        },
    )


def _append_surface_evidence(
    *,
    task_store: KernelTaskStore,
    task: KernelTask,
    capability_name: str,
    round_index: int,
    kind: str = "surface-transition",
    surface_kind: str = "browser",
) -> None:
    record = task_store.append_evidence(
        task,
        action_summary=f"{capability_name} round {round_index}",
        result_summary=f"{capability_name} produced round {round_index}",
        kind=kind,
        metadata={
            "evidence_kind": kind,
            "surface_kind": surface_kind,
            "target_slot": capability_name,
            "transition": {
                "changed_nodes": [f"{capability_name}:changed:{round_index}"],
                "new_blockers": [],
                "resolved_blockers": [f"{capability_name}:resolved:{round_index}"],
                "result_summary": f"{capability_name} produced round {round_index}",
            },
        },
    )
    assert record is not None


def test_surface_graph_soak_skip_reason_declares_opt_in_boundary() -> None:
    reason = LIVE_SURFACE_GRAPH_SOAK_SKIP_REASON.lower()
    assert "opt-in" in reason
    assert "not part of default regression coverage" in reason


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_SURFACE_GRAPH_SOAK"),
    reason=LIVE_SURFACE_GRAPH_SOAK_SKIP_REASON,
)
def test_surface_graph_soak_preserves_scope_isolation_and_restart_recovery(
    tmp_path,
) -> None:
    first_stack = _build_surface_learning_stack(tmp_path)
    _seed_surface_learning_context(
        industry_instance_repository=first_stack["industry_instance_repository"],
        strategy_repository=first_stack["strategy_repository"],
        operating_lane_repository=first_stack["operating_lane_repository"],
        assignment_repository=first_stack["assignment_repository"],
    )

    task_a = _build_task(
        task_id="task-surface-scope-a",
        title="Publish listing A",
        capability_ref="publish_listing",
        work_context_id="ctx-surface-a",
        assignment_id="assignment:scope-a",
    )
    task_b = _build_task(
        task_id="task-surface-scope-b",
        title="Refresh inventory B",
        capability_ref="refresh_inventory",
        work_context_id="ctx-surface-b",
        assignment_id="assignment:scope-b",
    )
    first_stack["task_store"].upsert(task_a)
    first_stack["task_store"].upsert(task_b)

    for round_index in range(1, 4):
        _append_surface_evidence(
            task_store=first_stack["task_store"],
            task=task_a,
            capability_name="publish_listing",
            round_index=round_index,
        )
        _append_surface_evidence(
            task_store=first_stack["task_store"],
            task=task_b,
            capability_name="refresh_inventory",
            round_index=round_index,
        )

    first_projection_a = first_stack["learning_service"].get_surface_learning_scope(
        scope_level="work_context",
        scope_id="ctx-surface-a",
        industry_instance_id="industry-surface-soak",
        lane_id="lane:surface-soak",
        assignment_id="assignment:scope-a",
        owner_agent_id="agent:surface-owner",
    )
    first_projection_b = first_stack["learning_service"].get_surface_learning_scope(
        scope_level="work_context",
        scope_id="ctx-surface-b",
        industry_instance_id="industry-surface-soak",
        lane_id="lane:surface-soak",
        assignment_id="assignment:scope-b",
        owner_agent_id="agent:surface-owner",
    )

    assert first_projection_a is not None
    assert first_projection_b is not None
    assert [item.capability_name for item in first_projection_a.active_twins] == [
        "publish_listing",
    ]
    assert [item.capability_name for item in first_projection_b.active_twins] == [
        "refresh_inventory",
    ]
    assert first_projection_a.reward_ranking[0].capability_name == "publish_listing"
    assert first_projection_b.reward_ranking[0].capability_name == "refresh_inventory"
    version_a_before_restart = int(first_projection_a.version or 0)
    version_b_before_restart = int(first_projection_b.version or 0)

    _close_if_possible(first_stack["evidence_ledger"])

    second_stack = _build_surface_learning_stack(tmp_path)
    second_projection_a = second_stack["learning_service"].get_surface_learning_scope(
        scope_level="work_context",
        scope_id="ctx-surface-a",
        industry_instance_id="industry-surface-soak",
        lane_id="lane:surface-soak",
        assignment_id="assignment:scope-a",
        owner_agent_id="agent:surface-owner",
    )
    second_projection_b = second_stack["learning_service"].get_surface_learning_scope(
        scope_level="work_context",
        scope_id="ctx-surface-b",
        industry_instance_id="industry-surface-soak",
        lane_id="lane:surface-soak",
        assignment_id="assignment:scope-b",
        owner_agent_id="agent:surface-owner",
    )

    assert second_projection_a is not None
    assert second_projection_b is not None
    assert int(second_projection_a.version or 0) == version_a_before_restart
    assert int(second_projection_b.version or 0) == version_b_before_restart

    second_stack["task_store"].upsert(task_a)
    _append_surface_evidence(
        task_store=second_stack["task_store"],
        task=task_a,
        capability_name="publish_listing",
        round_index=4,
    )

    third_projection_a = second_stack["learning_service"].get_surface_learning_scope(
        scope_level="work_context",
        scope_id="ctx-surface-a",
        industry_instance_id="industry-surface-soak",
        lane_id="lane:surface-soak",
        assignment_id="assignment:scope-a",
        owner_agent_id="agent:surface-owner",
    )
    third_projection_b = second_stack["learning_service"].get_surface_learning_scope(
        scope_level="work_context",
        scope_id="ctx-surface-b",
        industry_instance_id="industry-surface-soak",
        lane_id="lane:surface-soak",
        assignment_id="assignment:scope-b",
        owner_agent_id="agent:surface-owner",
    )

    assert third_projection_a is not None
    assert third_projection_b is not None
    assert int(third_projection_a.version or 0) > version_a_before_restart
    assert int(third_projection_b.version or 0) == version_b_before_restart
    assert [item.capability_name for item in third_projection_a.active_twins] == [
        "publish_listing",
    ]
    assert [item.capability_name for item in third_projection_b.active_twins] == [
        "refresh_inventory",
    ]
    assert any(
        reason.startswith("assignment+")
        or reason.startswith("strategy+")
        for reason in third_projection_a.reward_ranking[0].reasons
    )
    assert all(
        item.capability_name != "refresh_inventory"
        for item in third_projection_a.active_twins
    )
    assert all(
        item.capability_name != "publish_listing"
        for item in third_projection_b.active_twins
    )

    _close_if_possible(second_stack["evidence_ledger"])
