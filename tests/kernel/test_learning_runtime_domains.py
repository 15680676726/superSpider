# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.evidence import EvidenceLedger
from copaw.learning.engine import LearningEngine
from copaw.learning.acquisition_runtime import LearningAcquisitionRuntimeService
from copaw.learning.growth_runtime import LearningGrowthRuntimeService
from copaw.learning.models import (
    CapabilityAcquisitionProposal,
    GrowthEvent,
    InstallBindingPlan,
    OnboardingRun,
    Patch,
)
from copaw.learning.patch_runtime import LearningPatchRuntimeService
from copaw.learning.runtime_core import LearningRuntimeCore


def test_learning_patch_runtime_service_filters_patch_records(tmp_path) -> None:
    core = LearningRuntimeCore(
        engine=LearningEngine(database_path=tmp_path / "learning.sqlite3"),
        evidence_ledger=EvidenceLedger(tmp_path / "evidence.db"),
    )
    patch_runtime = LearningPatchRuntimeService(core)

    core.engine.create_patch(
        patch=Patch(
            kind="plan_patch",
            title="Patch A",
            description="For goal A",
            goal_id="goal-a",
            task_id="task-a",
            agent_id="agent-a",
            diff_summary="goal_id=goal-a;plan_steps=Inspect|Ship",
        ),
    )
    core.engine.create_patch(
        patch=Patch(
            kind="plan_patch",
            title="Patch B",
            description="For goal B",
            goal_id="goal-b",
            task_id="task-b",
            agent_id="agent-b",
            diff_summary="goal_id=goal-b;plan_steps=Inspect|Ship",
        ),
    )

    patches = patch_runtime.list_patches(goal_id="goal-a", agent_id="agent-a")

    assert [patch.title for patch in patches] == ["Patch A"]


def test_learning_acquisition_runtime_service_reads_saved_records(tmp_path) -> None:
    core = LearningRuntimeCore(
        engine=LearningEngine(database_path=tmp_path / "learning.sqlite3"),
        evidence_ledger=EvidenceLedger(tmp_path / "evidence.db"),
    )
    acquisition_runtime = LearningAcquisitionRuntimeService(core)

    proposal = core.engine.save_acquisition_proposal(
        CapabilityAcquisitionProposal(
            proposal_key="browser-local:agent-a",
            industry_instance_id="industry-a",
            target_agent_id="agent-a",
            target_role_id="role-a",
            acquisition_kind="install-capability",
            title="Acquire browser runtime",
        ),
    )
    plan = core.engine.save_install_binding_plan(
        InstallBindingPlan(
            proposal_id=proposal.id,
            industry_instance_id="industry-a",
            target_agent_id="agent-a",
            target_role_id="role-a",
            acquisition_kind="install-capability",
            title="Install browser runtime",
            status="applied",
        ),
    )
    run = core.engine.save_onboarding_run(
        OnboardingRun(
            proposal_id=proposal.id,
            plan_id=plan.id,
            industry_instance_id="industry-a",
            target_agent_id="agent-a",
            target_role_id="role-a",
            title="Browser onboarding",
            status="passed",
        ),
    )

    proposals = acquisition_runtime.list_acquisition_proposals(
        industry_instance_id="industry-a",
        limit=None,
    )
    plans = acquisition_runtime.list_install_binding_plans(
        industry_instance_id="industry-a",
        limit=None,
    )
    runs = acquisition_runtime.list_onboarding_runs(
        industry_instance_id="industry-a",
        limit=None,
    )

    assert [item.id for item in proposals] == [proposal.id]
    assert [item.id for item in plans] == [plan.id]
    assert [item.id for item in runs] == [run.id]


def test_learning_growth_runtime_service_filters_growth_records(tmp_path) -> None:
    core = LearningRuntimeCore(
        engine=LearningEngine(database_path=tmp_path / "learning.sqlite3"),
        evidence_ledger=EvidenceLedger(tmp_path / "evidence.db"),
    )
    growth_runtime = LearningGrowthRuntimeService(core)

    core.engine.record_growth(
        GrowthEvent(
            agent_id="agent-a",
            goal_id="goal-a",
            task_id="task-a",
            change_type="outcome",
            description="A",
            result="completed",
        ),
    )
    core.engine.record_growth(
        GrowthEvent(
            agent_id="agent-b",
            goal_id="goal-b",
            task_id="task-b",
            change_type="outcome",
            description="B",
            result="completed",
        ),
    )

    events = growth_runtime.list_growth(goal_id="goal-a", agent_id="agent-a")

    assert [event.description for event in events] == ["A"]


def test_learning_runtime_core_delegates_patch_queries_to_patch_runtime(
    monkeypatch,
    tmp_path,
) -> None:
    core = LearningRuntimeCore(
        engine=LearningEngine(database_path=tmp_path / "learning.sqlite3"),
        evidence_ledger=EvidenceLedger(tmp_path / "evidence.db"),
    )
    expected_patch = Patch(
        kind="plan_patch",
        title="Delegated patch",
        description="delegated",
        goal_id="goal-a",
        task_id="task-a",
        agent_id="agent-a",
        diff_summary="goal_id=goal-a",
    )
    seen: dict[str, object] = {}

    def _list_patches(**kwargs):
        seen["list_patches"] = kwargs
        return [expected_patch]

    def _strategy_cycle(**kwargs):
        seen["run_strategy_cycle"] = kwargs
        return {"ran": True}

    monkeypatch.setattr(core._patch_runtime, "list_patches", _list_patches)
    monkeypatch.setattr(
        core._patch_runtime,
        "run_strategy_cycle",
        _strategy_cycle,
    )

    patches = core.list_patches(goal_id="goal-a", agent_id="agent-a", limit=5)
    cycle = core.run_strategy_cycle(limit=7, auto_apply=False)

    assert patches == [expected_patch]
    assert seen["list_patches"] == {
        "status": None,
        "goal_id": "goal-a",
        "task_id": None,
        "agent_id": "agent-a",
        "evidence_id": None,
        "created_since": None,
        "limit": 5,
    }
    assert cycle == {"ran": True}
    assert seen["run_strategy_cycle"] == {
        "actor": "copaw-main-brain",
        "limit": 7,
        "auto_apply": False,
        "auto_rollback": False,
        "failure_threshold": 2,
        "confirm_threshold": 6,
        "max_proposals": 5,
    }


def test_learning_runtime_core_delegates_growth_entrypoints_to_growth_runtime(
    monkeypatch,
    tmp_path,
) -> None:
    core = LearningRuntimeCore(
        engine=LearningEngine(database_path=tmp_path / "learning.sqlite3"),
        evidence_ledger=EvidenceLedger(tmp_path / "evidence.db"),
    )
    expected_event = GrowthEvent(
        agent_id="agent-a",
        goal_id="goal-a",
        task_id="task-a",
        change_type="outcome",
        description="delegated",
        result="completed",
    )
    seen: dict[str, object] = {}

    def _list_growth(**kwargs):
        seen["list_growth"] = kwargs
        return [expected_event]

    def _record_agent_outcome(**kwargs):
        seen["record_agent_outcome"] = kwargs
        return expected_event

    def _get_growth_event(event_id: str):
        seen["get_growth_event"] = event_id
        return expected_event

    def _delete_growth_event(event_id: str):
        seen["delete_growth_event"] = event_id
        return True

    monkeypatch.setattr(core._growth_runtime, "list_growth", _list_growth)
    monkeypatch.setattr(
        core._growth_runtime,
        "record_agent_outcome",
        _record_agent_outcome,
    )
    monkeypatch.setattr(core._growth_runtime, "get_growth_event", _get_growth_event)
    monkeypatch.setattr(
        core._growth_runtime,
        "delete_growth_event",
        _delete_growth_event,
    )

    events = core.list_growth(goal_id="goal-a", agent_id="agent-a", limit=5)
    recorded = core.record_agent_outcome(
        agent_id="agent-a",
        title="Outcome",
        status="completed",
        change_type="outcome",
        description="delegated",
    )
    fetched = core.get_growth_event("event-a")
    deleted = core.delete_growth_event("event-a")

    assert events == [expected_event]
    assert seen["list_growth"] == {
        "agent_id": "agent-a",
        "goal_id": "goal-a",
        "task_id": None,
        "source_patch_id": None,
        "source_evidence_id": None,
        "created_since": None,
        "limit": 5,
    }
    assert recorded == expected_event
    assert seen["record_agent_outcome"] == {
        "agent_id": "agent-a",
        "title": "Outcome",
        "status": "completed",
        "change_type": "outcome",
        "description": "delegated",
        "capability_ref": None,
        "task_id": None,
        "goal_id": None,
        "source_evidence_id": None,
        "risk_level": "auto",
        "source_agent_id": None,
        "industry_instance_id": None,
        "industry_role_id": None,
        "role_name": None,
        "owner_scope": None,
        "error_summary": None,
        "metadata": None,
    }
    assert fetched == expected_event
    assert seen["get_growth_event"] == "event-a"
    assert deleted is True
    assert seen["delete_growth_event"] == "event-a"
