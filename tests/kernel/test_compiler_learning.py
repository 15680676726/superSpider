# -*- coding: utf-8 -*-
"""Tests for the semantic compiler and learning engine."""
from __future__ import annotations

import sqlite3

import pytest

from copaw.compiler import CompilationUnit, CompiledTaskSpec, SemanticCompiler
from copaw.evidence import EvidenceLedger, EvidenceRecord
from copaw.industry import IndustryBootstrapInstallItem
from copaw.learning import (
    CapabilityAcquisitionProposal,
    GrowthEvent,
    InstallBindingPlan,
    LearningEngine,
    LearningService,
    OnboardingRun,
    Patch,
    PatchExecutor,
    Proposal,
)
from copaw.kernel.persistence import encode_kernel_task_metadata
from copaw.state import SQLiteStateStore, TaskRecord
from copaw.state.repositories import (
    SqliteAgentProfileOverrideRepository,
    SqliteCapabilityOverrideRepository,
    SqliteDecisionRequestRepository,
    SqliteGoalOverrideRepository,
    SqliteTaskRepository,
)


def _make_learning_engine(tmp_path) -> LearningEngine:
    return LearningEngine(database_path=tmp_path / "learning.sqlite3")


# ── Compiler tests ──────────────────────────────────────────────


class TestSemanticCompiler:
    def test_compile_goal_produces_one_spec(self):
        compiler = SemanticCompiler()
        unit = CompilationUnit(kind="goal", source_text="Build a new feature")
        specs = compiler.compile(unit)
        assert len(specs) == 1
        assert "goal" in specs[0].title.lower()
        assert specs[0].capability_ref == "system:dispatch_query"
        assert specs[0].risk_level == "guarded"
        assert specs[0].payload["request"]["input"][0]["content"][0]["type"] == "text"

    def test_compile_plan_produces_multiple_specs(self):
        compiler = SemanticCompiler()
        unit = CompilationUnit(
            kind="plan",
            source_text="Multi-step plan",
            context={"steps": ["step 1", "step 2", "step 3"]},
        )
        specs = compiler.compile(unit)
        assert len(specs) == 3
        assert all(spec.capability_ref == "system:dispatch_query" for spec in specs)

    def test_compile_role_produces_role_spec(self):
        compiler = SemanticCompiler()
        unit = CompilationUnit(kind="role", source_text="Senior developer")
        specs = compiler.compile(unit)
        assert len(specs) == 1
        assert specs[0].capability_ref == "system:apply_role"

    def test_compile_directive_produces_auto_risk(self):
        compiler = SemanticCompiler()
        unit = CompilationUnit(kind="directive", source_text="Run tests")
        specs = compiler.compile(unit)
        assert specs[0].capability_ref == "system:dispatch_query"
        assert specs[0].risk_level == "auto"

    def test_compile_goal_with_routine_id_produces_routine_replay_spec(self):
        compiler = SemanticCompiler()
        unit = CompilationUnit(
            kind="goal",
            source_text="Run the routine-backed operating slice",
            context={
                "goal_id": "goal-routine-1",
                "goal_title": "Routine goal",
                "goal_summary": "Execute the persisted routine and return the result.",
                "owner_agent_id": "ops-agent",
                "owner_scope": "industry-v1-test",
                "routine_id": "routine-123",
                "routine_name": "Stable routine",
                "routine_input_payload": {"window": "today"},
            },
        )
        specs = compiler.compile(unit)
        assert len(specs) == 1
        assert specs[0].capability_ref == "system:replay_routine"
        assert specs[0].environment_ref == "routine:routine-123"
        assert specs[0].payload["routine_id"] == "routine-123"
        assert specs[0].payload["input_payload"] == {"window": "today"}
        assert specs[0].payload["request_context"]["goal_title"] == "Routine goal"
        assert specs[0].payload["compiler"]["routine_id"] == "routine-123"
        assert specs[0].task_segment.segment_kind == "routine-replay"

    def test_compile_goal_with_fixed_sop_binding_produces_fixed_sop_binding_keys(self):
        compiler = SemanticCompiler()
        unit = CompilationUnit(
            kind="goal",
            source_text="Run the fixed SOP-backed operating slice",
            context={
                "goal_id": "goal-fixed-sop-1",
                "goal_title": "Fixed SOP goal",
                "goal_summary": "Execute the fixed SOP binding and return the result.",
                "owner_agent_id": "ops-agent",
                "owner_scope": "industry-v1-test",
                "fixed_sop_binding_id": "fixed-sop-binding-123",
                "fixed_sop_binding_name": "Governed fixed SOP",
                "fixed_sop_input_payload": {"window": "today"},
                "fixed_sop_source_type": "assignment",
                "fixed_sop_source_ref": "backlog-item-1",
            },
        )
        specs = compiler.compile(unit)

        assert len(specs) == 1
        assert specs[0].capability_ref == "system:run_fixed_sop"
        assert specs[0].payload["binding_id"] == "fixed-sop-binding-123"
        assert specs[0].payload["input_payload"] == {"window": "today"}
        assert (
            specs[0].payload["compiler"]["fixed_sop_binding_id"]
            == "fixed-sop-binding-123"
        )
        assert "sop_binding_id" not in specs[0].payload["compiler"]
        assert specs[0].task_segment.segment_kind == "sop-binding-trigger"

    def test_compilation_unit_ids_are_unique(self):
        ids = {CompilationUnit(kind="goal", source_text="Build a new feature").id for _ in range(32)}
        assert len(ids) == 32

    def test_compile_to_kernel_tasks(self):
        compiler = SemanticCompiler()
        unit = CompilationUnit(
            kind="goal",
            source_text="Test goal",
            context={
                "goal_id": "goal-1",
                "owner_agent_id": "ops-agent",
                "steps": ["Draft the operator brief"],
            },
        )
        tasks = compiler.compile_to_kernel_tasks(unit)
        assert len(tasks) == 1
        assert tasks[0].title.startswith("Goal step 1:")
        assert tasks[0].payload.get("source_unit_id") == unit.id
        assert tasks[0].capability_ref == "system:dispatch_query"
        assert tasks[0].payload["request"]["session_id"] == "goal-1"
        assert tasks[0].payload["compiler"]["goal_id"] == "goal-1"
        assert tasks[0].payload["compiler"]["owner_agent_id"] == "ops-agent"
        assert tasks[0].payload["task_seed"]["request_preview"].startswith("Goal title:")
        assert tasks[0].actor_owner_id == "ops-agent"
        assert tasks[0].task_segment["segment_kind"] == "goal-step"
        assert tasks[0].task_segment["index"] == 0
        assert tasks[0].resume_point["phase"] == "compiled"
        assert tasks[0].resume_point["cursor"] == tasks[0].task_segment["segment_id"]


# ── Learning engine tests ───────────────────────────────────────


class TestLearningEngine:
    def test_create_and_list_proposal(self, tmp_path):
        engine = _make_learning_engine(tmp_path)
        proposal = engine.create_proposal(
            title="Add caching",
            description="Improve performance with caching layer",
        )
        assert proposal.status == "open"
        proposals = engine.list_proposals()
        assert len(proposals) == 1

    def test_accept_proposal(self, tmp_path):
        engine = _make_learning_engine(tmp_path)
        proposal = engine.create_proposal(title="Test", description="Test proposal")
        accepted = engine.accept_proposal(proposal.id)
        assert accepted.status == "accepted"

    def test_reject_proposal(self, tmp_path):
        engine = _make_learning_engine(tmp_path)
        proposal = engine.create_proposal(title="Test", description="Test proposal")
        rejected = engine.reject_proposal(proposal.id)
        assert rejected.status == "rejected"

    def test_create_and_apply_patch(self, tmp_path):
        engine = _make_learning_engine(tmp_path)
        patch = Patch(
            kind="capability_patch",
            title="Add new tool",
            description="Add file search capability",
            risk_level="auto",
        )
        engine.create_patch(patch=patch)
        applied = engine.apply_patch(patch.id)
        assert applied.status == "applied"
        assert applied.applied_at is not None

    def test_confirm_risk_patch_cannot_auto_apply(self, tmp_path):
        engine = _make_learning_engine(tmp_path)
        patch = Patch(
            kind="role_patch",
            title="Change role",
            description="Switch to admin",
            risk_level="confirm",
        )
        engine.create_patch(patch=patch)
        with pytest.raises(ValueError, match="must be approved"):
            engine.apply_patch(patch.id)

    def test_approve_then_apply_confirm_patch(self, tmp_path):
        engine = _make_learning_engine(tmp_path)
        patch = Patch(
            kind="role_patch",
            title="Change role",
            description="Switch to admin",
            risk_level="confirm",
        )
        engine.create_patch(patch=patch)
        engine.approve_patch(patch.id)
        applied = engine.apply_patch(patch.id)
        assert applied.status == "applied"

    def test_rollback_patch(self, tmp_path):
        engine = _make_learning_engine(tmp_path)
        patch = Patch(kind="plan_patch", title="Test", description="Test")
        engine.create_patch(patch=patch)
        engine.apply_patch(patch.id)
        rolled = engine.rollback_patch(patch.id)
        assert rolled.status == "rolled_back"

    def test_record_growth(self, tmp_path):
        engine = _make_learning_engine(tmp_path)
        event = GrowthEvent(
            agent_id="copaw-agent-runner",
            change_type="capability_added",
            description="Added file search tool",
        )
        engine.record_growth(event)
        history = engine.get_growth_history(agent_id="copaw-agent-runner")
        assert len(history) == 1
        assert history[0].change_type == "capability_added"

    def test_growth_history_limits(self, tmp_path):
        engine = _make_learning_engine(tmp_path)
        for i in range(10):
            engine.record_growth(
                GrowthEvent(
                    agent_id="test-agent",
                    change_type=f"change_{i}",
                    description=f"Change {i}",
                ),
            )
        limited = engine.get_growth_history(limit=5)
        assert len(limited) == 5

    def test_delete_learning_entities_cleans_audit_rows(self, tmp_path):
        engine = _make_learning_engine(tmp_path)
        proposal = engine.create_proposal(
            title="Delete proposal",
            description="Delete the proposal and its audit rows.",
        )
        patch = Patch(
            kind="plan_patch",
            proposal_id=proposal.id,
            title="Delete patch",
            description="Delete the patch and its audit rows.",
        )
        engine.create_patch(patch=patch)
        growth = GrowthEvent(
            agent_id="copaw-agent-runner",
            change_type="patch_applied",
            description="Delete the growth event and its audit rows.",
            source_patch_id=patch.id,
        )
        engine.record_growth(growth)

        assert engine.delete_growth_event(growth.id) is True
        assert engine.delete_patch(patch.id) is True
        assert engine.delete_proposal(proposal.id) is True
        assert engine.get_growth_history(limit=None) == []
        assert engine.list_patches() == []
        assert engine.list_proposals() == []

        with sqlite3.connect(engine.database_path) as conn:
            rows = conn.execute(
                """
                SELECT entity_type, entity_id
                FROM learning_audit_log
                WHERE entity_id IN (?, ?, ?)
                """,
                (proposal.id, patch.id, growth.id),
            ).fetchall()
        assert rows == []

    def test_acquisition_entities_round_trip_and_delete_clean_audit_rows(self, tmp_path):
        engine = _make_learning_engine(tmp_path)
        install_item = IndustryBootstrapInstallItem(
            install_kind="builtin-runtime",
            template_id="browser-local",
            client_key="browser-local-default",
            capability_ids=[],
            target_agent_ids=["industry-solution-lead-demo"],
            target_role_ids=["solution-lead"],
        )
        proposal = engine.save_acquisition_proposal(
            CapabilityAcquisitionProposal(
                proposal_key="industry-v1-demo:install:solution-lead:industry-solution-lead-demo:browser-local:browser-local-default",
                industry_instance_id="industry-v1-demo",
                owner_scope="industry-v1-demo",
                target_agent_id="industry-solution-lead-demo",
                target_role_id="solution-lead",
                acquisition_kind="install-capability",
                title="Install browser runtime",
                summary="Provision the governed browser runtime for the solution lead.",
                install_item=install_item,
                evidence_refs=["evidence:acq:1"],
            ),
            action="created",
        )
        plan = engine.save_install_binding_plan(
            InstallBindingPlan(
                proposal_id=proposal.id,
                industry_instance_id="industry-v1-demo",
                target_agent_id="industry-solution-lead-demo",
                target_role_id="solution-lead",
                install_item=install_item,
                binding_request={
                    "template_id": "n8n-scheduled-collector",
                    "binding_name": "Solution lane scheduled collector",
                    "owner_scope": "industry-v1-demo",
                    "owner_agent_id": "industry-solution-lead-demo",
                    "industry_instance_id": "industry-v1-demo",
                    "callback_mode": "workflow-callback",
                },
                evidence_refs=["evidence:plan:1"],
            ),
            action="created",
        )
        run = engine.save_onboarding_run(
            OnboardingRun(
                plan_id=plan.id,
                proposal_id=proposal.id,
                industry_instance_id="industry-v1-demo",
                target_agent_id="industry-solution-lead-demo",
                target_role_id="solution-lead",
                status="passed",
                summary="The onboarding checks passed.",
                checks=[
                    {
                        "key": "materialization",
                        "status": "pass",
                        "message": "Plan materialized.",
                    },
                ],
                evidence_refs=["evidence:onboarding:1"],
            ),
            action="created",
        )

        stored_proposal = engine.get_acquisition_proposal(proposal.id)
        assert stored_proposal.proposal_key == proposal.proposal_key
        stored_plan = engine.get_install_binding_plan(plan.id)
        assert stored_plan.proposal_id == proposal.id
        stored_run = engine.get_onboarding_run(run.id)
        assert stored_run.plan_id == plan.id
        assert [
            item.id
            for item in engine.list_acquisition_proposals(
                industry_instance_id="industry-v1-demo",
            )
        ] == [proposal.id]
        assert [
            item.id
            for item in engine.list_install_binding_plans(
                industry_instance_id="industry-v1-demo",
            )
        ] == [plan.id]
        assert [
            item.id
            for item in engine.list_onboarding_runs(
                industry_instance_id="industry-v1-demo",
            )
        ] == [run.id]

        assert engine.delete_onboarding_run(run.id) is True
        assert engine.delete_install_binding_plan(plan.id) is True
        assert engine.delete_acquisition_proposal(proposal.id) is True
        assert engine.list_onboarding_runs(limit=None) == []
        assert engine.list_install_binding_plans(limit=None) == []
        assert engine.list_acquisition_proposals(limit=None) == []

        with sqlite3.connect(engine.database_path) as conn:
            rows = conn.execute(
                """
                SELECT entity_type, entity_id
                FROM learning_audit_log
                WHERE entity_id IN (?, ?, ?)
                """,
                (proposal.id, plan.id, run.id),
            ).fetchall()
        assert rows == []


class TestLearningStrategy:
    def test_strategy_cycle_generates_patch(self, tmp_path):
        engine = _make_learning_engine(tmp_path)
        evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
        state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
        decision_repo = SqliteDecisionRequestRepository(state_store)
        task_repo = SqliteTaskRepository(state_store)
        capability_override_repo = SqliteCapabilityOverrideRepository(state_store)
        service = LearningService(
            engine=engine,
            patch_executor=PatchExecutor(
                override_repository=capability_override_repo,
            ),
            decision_request_repository=decision_repo,
            task_repository=task_repo,
            evidence_ledger=evidence_ledger,
        )

        for idx in range(3):
            evidence_ledger.append(
                EvidenceRecord(
                    task_id=f"task-{idx}",
                    actor_ref="kernel",
                    capability_ref="tool:execute_shell_command",
                    risk_level="guarded",
                    action_summary="kernel task failed",
                    result_summary="error: test failure",
                    status="failed",
                ),
            )

        result = service.run_strategy_cycle(
            actor="tester",
            failure_threshold=2,
            confirm_threshold=5,
        )
        assert result["success"] is True
        assert result["proposals_created"] == 1
        assert result["patches_created"] == 1
        patch_id = result["patches"][0]["id"]

        patches = engine.list_patches()
        assert patches[0].status in {"applied", "approved", "proposed"}
        assert patches[0].task_id == "task-0"

        decisions = decision_repo.list_decision_requests(task_id=patch_id)
        assert decisions
        assert evidence_ledger.count_records() >= 4


def test_patch_executor_applies_profile_role_and_plan_side_effects(tmp_path):
    engine = _make_learning_engine(tmp_path)
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    decision_repo = SqliteDecisionRequestRepository(state_store)
    task_repo = SqliteTaskRepository(state_store)
    capability_override_repo = SqliteCapabilityOverrideRepository(state_store)
    agent_override_repo = SqliteAgentProfileOverrideRepository(state_store)
    goal_override_repo = SqliteGoalOverrideRepository(state_store)
    service = LearningService(
        engine=engine,
        patch_executor=PatchExecutor(
            capability_override_repository=capability_override_repo,
            agent_profile_override_repository=agent_override_repo,
            goal_override_repository=goal_override_repo,
        ),
        decision_request_repository=decision_repo,
        task_repository=task_repo,
        evidence_ledger=evidence_ledger,
    )

    profile_payload = service.create_patch(
        kind="profile_patch",
        title="Refresh ops profile",
        description="Update operator profile projection",
        agent_id="ops-agent",
        diff_summary=(
            "agent_id=ops-agent;"
            "current_goal_id=goal-1;"
            "role_summary=Owns runtime closeout;"
            "current_goal=Launch runtime center;"
            "capabilities=system:dispatch_query|system:dispatch_goal"
        ),
    )
    profile_patch = profile_payload["patch"]
    assert profile_patch is not None
    assert profile_payload["decision_request"] is None
    assert profile_patch.status == "approved"
    profile_decisions = decision_repo.list_decision_requests(task_id=profile_patch.id)
    assert len(profile_decisions) == 1
    assert profile_decisions[0].status == "approved"
    assert profile_decisions[0].requested_by == "copaw-main-brain"
    service.apply_patch(profile_patch.id, applied_by="tester")
    profile_override = agent_override_repo.get_override("ops-agent")
    assert profile_override is not None
    assert profile_override.role_summary == "Owns runtime closeout"
    assert profile_override.current_goal_id == "goal-1"
    assert profile_override.current_goal == "Launch runtime center"
    assert profile_override.capabilities == [
        "system:dispatch_query",
        "system:dispatch_goal",
    ]

    role_payload = service.create_patch(
        kind="role_patch",
        title="Planner lead",
        description="Promote planner lead role",
        agent_id="ops-agent",
        diff_summary="agent_id=ops-agent",
        risk_level="confirm",
    )
    role_patch = role_payload["patch"]
    assert role_patch is not None
    assert role_payload["decision_request"] is not None
    assert role_patch.status == "proposed"
    service.approve_patch(role_patch.id, approved_by="reviewer")
    service.apply_patch(role_patch.id, applied_by="reviewer")
    role_override = agent_override_repo.get_override("ops-agent")
    assert role_override is not None
    assert role_override.role_name == "Planner lead"

    plan_payload = service.create_patch(
        kind="plan_patch",
        title="Refine goal plan",
        description="Refresh plan steps for launch",
        goal_id="goal-1",
        task_id="task-goal-1",
        agent_id="ops-agent",
        diff_summary=(
            "goal_id=goal-1;"
            "summary=Promote runtime center to the operator cockpit.;"
            'steps=["wire overview","verify evidence","ship closeout"];'
            'compiler_context={"owner_agent_id":"ops-agent","goal_id":"goal-1"}'
        ),
    )
    plan_patch = plan_payload["patch"]
    assert plan_patch is not None
    assert plan_payload["decision_request"] is None
    assert plan_patch.status == "approved"
    service.apply_patch(plan_patch.id, applied_by="tester")
    goal_override = goal_override_repo.get_override("goal-1")
    assert goal_override is not None
    assert goal_override.plan_steps == [
        "wire overview",
        "verify evidence",
        "ship closeout",
    ]
    assert goal_override.compiler_context == {
        "owner_agent_id": "ops-agent",
        "goal_id": "goal-1",
    }

    growth = service.list_growth(limit=10)
    assert growth
    assert growth[0].change_type == "patch_applied"
    assert growth[0].goal_id == "goal-1"
    assert growth[0].task_id == "task-goal-1"

    service.rollback_patch(plan_patch.id, rolled_back_by="tester")
    assert goal_override_repo.get_override("goal-1") is None


def test_learning_service_apply_patch_auto_adjudicates_legacy_low_risk_patch(tmp_path):
    engine = _make_learning_engine(tmp_path)
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    decision_repo = SqliteDecisionRequestRepository(state_store)
    task_repo = SqliteTaskRepository(state_store)
    goal_override_repo = SqliteGoalOverrideRepository(state_store)
    service = LearningService(
        engine=engine,
        patch_executor=PatchExecutor(goal_override_repository=goal_override_repo),
        decision_request_repository=decision_repo,
        task_repository=task_repo,
    )

    legacy_patch = Patch(
        kind="plan_patch",
        title="Legacy guarded patch",
        description="Make sure old proposed low-risk patches still follow main-brain adjudication.",
        goal_id="goal-legacy",
        diff_summary="goal_id=goal-legacy;plan_steps=Inspect|Apply",
        risk_level="guarded",
    )
    engine.create_patch(patch=legacy_patch)

    applied = service.apply_patch(legacy_patch.id, applied_by="runtime-operator")

    assert applied.status == "applied"
    decisions = decision_repo.list_decision_requests(task_id=legacy_patch.id)
    assert len(decisions) == 1
    assert decisions[0].status == "approved"
    assert decisions[0].requested_by == "copaw-main-brain"
    goal_override = goal_override_repo.get_override("goal-legacy")
    assert goal_override is not None
    assert goal_override.plan_steps == ["Inspect", "Apply"]


def test_learning_service_links_to_persisted_compiler_context(tmp_path):
    engine = _make_learning_engine(tmp_path)
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repo = SqliteTaskRepository(state_store)
    service = LearningService(
        engine=engine,
        task_repository=task_repo,
        evidence_ledger=evidence_ledger,
    )

    compiler = SemanticCompiler()
    unit = CompilationUnit(
        kind="goal",
        source_text="Launch runtime center",
        context={
            "goal_id": "goal-1",
            "goal_title": "Launch runtime center",
            "goal_summary": "Close the operator surface gaps.",
            "owner_agent_id": "ops-agent",
            "steps": ["wire overview", "verify evidence"],
            "evidence_refs": ["evidence-1", "evidence-2"],
        },
    )
    specs = compiler.compile(unit)
    tasks = compiler.compile_to_kernel_tasks(unit, specs=specs)
    for task in tasks:
        task_repo.upsert_task(
            TaskRecord(
                id=task.id,
                goal_id=task.goal_id,
                title=task.title,
                summary=task.title,
                task_type=task.capability_ref or "system:dispatch_query",
                status="created",
                owner_agent_id=task.owner_agent_id,
                seed_source="compiler:test",
                acceptance_criteria=encode_kernel_task_metadata(task),
                current_risk_level=task.risk_level,
            ),
        )

    proposal = service.create_proposal(
        title="Tighten next-plan feedback",
        description="Promote compiler seed evidence into learning.",
        goal_id="goal-1",
    )
    assert proposal.goal_id == "goal-1"
    assert proposal.task_id == tasks[0].id
    assert proposal.agent_id == "ops-agent"
    assert proposal.evidence_refs == ["evidence-1", "evidence-2"]

    patch_payload = service.create_patch(
        kind="plan_patch",
        title="Refine runtime-center plan",
        description="Carry compiler seeds into learning patches.",
        goal_id="goal-1",
        diff_summary="goal_id=goal-1;steps=wire overview|verify evidence",
    )
    patch = patch_payload["patch"]
    assert patch.goal_id == "goal-1"
    assert patch.task_id == tasks[0].id
    assert patch.agent_id == "ops-agent"
    assert patch.source_evidence_id == "evidence-1"
    assert patch.evidence_refs == ["evidence-1", "evidence-2"]


# ── Kernel adapter tests ───────────────────────────────────────
