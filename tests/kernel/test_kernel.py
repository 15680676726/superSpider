# -*- coding: utf-8 -*-
"""Tests for the SRK kernel: lifecycle, dispatcher, and agent profiles."""
from __future__ import annotations

import asyncio

import pytest

from copaw.evidence import EvidenceLedger
from copaw.kernel import (
    AgentProfile,
    DEFAULT_AGENTS,
    KernelConfig,
    KernelDispatcher,
    KernelResult,
    KernelTask,
    KernelTaskStore,
    TaskLifecycleManager,
)
from copaw.learning import LearningEngine, LearningService
from copaw.state import SQLiteStateStore, TaskRecord, WorkContextService
from copaw.state.agent_experience_service import AgentExperienceMemoryService
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
)


def _build_dispatcher_with_decisions(
    tmp_path,
    *,
    capability_service=None,
    learning_service=None,
):
    store = SQLiteStateStore(tmp_path / "state.db")
    task_store = KernelTaskStore(
        task_repository=SqliteTaskRepository(store),
        task_runtime_repository=SqliteTaskRuntimeRepository(store),
        decision_request_repository=SqliteDecisionRequestRepository(store),
        evidence_ledger=EvidenceLedger(),
    )
    dispatcher = KernelDispatcher(
        task_store=task_store,
        capability_service=capability_service,
        learning_service=learning_service,
    )
    return dispatcher, task_store


class _FakeKnowledgeService:
    def __init__(self) -> None:
        self.calls = []

    def remember_fact(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs


class _CountingGoalService:
    def __init__(self) -> None:
        self.reconcile_calls: list[tuple[str, str]] = []
        self.resume_calls: list[str] = []

    def reconcile_goal_status(self, goal_id: str, *, source: str) -> None:
        self.reconcile_calls.append((goal_id, source))

    def resume_background_goal_chain_for_task(self, task_id: str) -> None:
        self.resume_calls.append(task_id)


# ── TaskLifecycleManager tests ──────────────────────────────────────


class TestTaskLifecycle:
    def test_accept_transitions_to_risk_check(self):
        lm = TaskLifecycleManager()
        task = KernelTask(title="Test task")
        result = lm.accept(task)
        assert result.phase == "risk-check"

    def test_evaluate_risk_auto_goes_to_executing(self):
        lm = TaskLifecycleManager()
        task = KernelTask(title="Auto task", risk_level="auto")
        lm.accept(task)
        result = lm.evaluate_risk(task.id)
        assert result.phase == "executing"

    def test_evaluate_risk_guarded_goes_to_executing(self):
        lm = TaskLifecycleManager()
        task = KernelTask(title="Guarded task", risk_level="guarded")
        lm.accept(task)
        result = lm.evaluate_risk(task.id)
        assert result.phase == "executing"

    def test_evaluate_risk_confirm_goes_to_waiting(self):
        lm = TaskLifecycleManager()
        task = KernelTask(title="Confirm task", risk_level="confirm")
        lm.accept(task)
        result = lm.evaluate_risk(task.id)
        assert result.phase == "waiting-confirm"

    def test_evaluate_risk_respects_auto_execute_risk_levels(self):
        lm = TaskLifecycleManager(
            config=KernelConfig(
                auto_execute_risk_levels=["auto"],
                confirm_risk_levels=["confirm"],
            )
        )
        task = KernelTask(title="Guarded task", risk_level="guarded")
        lm.accept(task)
        result = lm.evaluate_risk(task.id)
        assert result.phase == "waiting-confirm"

    def test_confirm_releases_for_execution(self):
        lm = TaskLifecycleManager()
        task = KernelTask(title="Confirm task", risk_level="confirm")
        lm.accept(task)
        lm.evaluate_risk(task.id)
        result = lm.confirm(task.id)
        assert result.phase == "executing"

    def test_complete_produces_success_result(self):
        lm = TaskLifecycleManager()
        task = KernelTask(title="Complete task")
        lm.accept(task)
        lm.evaluate_risk(task.id)
        result = lm.complete(task.id, summary="Done")
        assert result.success is True
        assert result.phase == "completed"
        assert result.summary == "Done"

    def test_fail_produces_error_result(self):
        lm = TaskLifecycleManager()
        task = KernelTask(title="Fail task")
        lm.accept(task)
        lm.evaluate_risk(task.id)
        result = lm.fail(task.id, error="boom")
        assert result.success is False
        assert result.phase == "failed"
        assert result.error == "boom"

    def test_cancel_produces_cancelled_result(self):
        lm = TaskLifecycleManager()
        task = KernelTask(title="Cancel task")
        lm.accept(task)
        result = lm.cancel(task.id)
        assert result.success is False
        assert result.phase == "cancelled"

    def test_list_tasks_filters_by_phase(self):
        lm = TaskLifecycleManager()
        t1 = KernelTask(title="Task 1")
        t2 = KernelTask(title="Task 2")
        lm.accept(t1)
        lm.accept(t2)
        lm.evaluate_risk(t1.id)  # now executing
        risk_check_tasks = lm.list_tasks(phase="risk-check")
        assert len(risk_check_tasks) == 1
        assert risk_check_tasks[0].id == t2.id

    def test_get_nonexistent_task_raises(self):
        lm = TaskLifecycleManager()
        with pytest.raises(KeyError):
            lm._get_task("nonexistent")

    def test_task_store_list_tasks_only_returns_kernel_records(self, tmp_path):
        store = SQLiteStateStore(tmp_path / "state.db")
        task_repo = SqliteTaskRepository(store)
        runtime_repo = SqliteTaskRuntimeRepository(store)
        task_store = KernelTaskStore(
            task_repository=task_repo,
            task_runtime_repository=runtime_repo,
        )

        task_repo.upsert_task(
            TaskRecord(
                id="external-task",
                title="External projection task",
                task_type="reporting",
                status="running",
            ),
        )

        task_store.upsert(
            KernelTask(
                id="kernel-active",
                title="Kernel active task",
                capability_ref="system:dispatch_query",
                phase="executing",
            ),
        )
        task_store.upsert(
            KernelTask(
                id="kernel-waiting",
                title="Kernel waiting task",
                capability_ref="system:dispatch_query",
                phase="waiting-confirm",
                risk_level="confirm",
            ),
        )

        listed = task_store.list_tasks()
        assert {task.id for task in listed} == {"kernel-active", "kernel-waiting"}

        waiting = task_store.list_tasks(phase="waiting-confirm")
        assert [task.id for task in waiting] == ["kernel-waiting"]

    def test_task_store_does_not_infer_work_context_from_thread_ids(self, tmp_path):
        store = SQLiteStateStore(tmp_path / "state.db")
        task_repo = SqliteTaskRepository(store)
        runtime_repo = SqliteTaskRuntimeRepository(store)
        work_context_repo = SqliteWorkContextRepository(store)
        task_store = KernelTaskStore(
            task_repository=task_repo,
            task_runtime_repository=runtime_repo,
            work_context_service=WorkContextService(repository=work_context_repo),
        )

        task_store.upsert(
            KernelTask(
                id="kernel-no-context-fallback",
                title="Kernel task without explicit work context",
                capability_ref="system:dispatch_query",
                payload={
                    "request": {
                        "session_id": "industry-chat:industry-v1-acme:execution-core",
                        "control_thread_id": "industry-chat:industry-v1-acme:execution-core",
                    },
                    "meta": {
                        "control_thread_id": "industry-chat:industry-v1-acme:execution-core",
                    },
                },
            ),
        )

        stored = task_store.get("kernel-no-context-fallback")
        assert stored is not None
        assert stored.work_context_id is None
        assert work_context_repo.list_contexts(limit=None) == []


# ── KernelDispatcher tests ──────────────────────────────────────────


class TestKernelDispatcher:
    def test_submit_auto_task_enters_executing(self):
        dispatcher = KernelDispatcher()
        task = KernelTask(title="Auto task", risk_level="auto")
        result = dispatcher.submit(task)
        assert result.success is True
        assert result.phase == "executing"
        assert result.trace_id == task.trace_id
        stored = dispatcher.lifecycle.get_task(task.id)
        assert stored is not None
        assert stored.phase == "executing"
        assert stored.trace_id == task.trace_id

    def test_submit_confirm_task_is_held(self):
        dispatcher = KernelDispatcher()
        task = KernelTask(title="Confirm task", risk_level="confirm")
        result = dispatcher.submit(task)
        assert result.success is False
        assert result.phase == "waiting-confirm"

    def test_submit_system_confirm_task_auto_adjudicates_to_main_brain(self, tmp_path):
        dispatcher, task_store = _build_dispatcher_with_decisions(tmp_path)
        task = KernelTask(
            title="Restart runtime",
            risk_level="confirm",
            capability_ref="system:dispatch_command",
        )

        result = dispatcher.submit(task)

        assert result.success is True
        assert result.phase == "executing"
        assert result.decision_request_id is not None

        decision = task_store.get_decision_request(result.decision_request_id)
        assert decision is not None
        assert decision.status == "approved"
        assert decision.requested_by == "copaw-main-brain"

    def test_confirm_and_execute_completes(self):
        class _FakeCapabilityService:
            async def execute_task(self, task):
                return {"success": True, "summary": f"executed {task.id}"}

        dispatcher = KernelDispatcher(capability_service=_FakeCapabilityService())
        task = KernelTask(title="Confirm then execute", risk_level="confirm")
        dispatcher.submit(task)
        result = asyncio.run(dispatcher.confirm_and_execute(task.id))
        assert result.success is True
        assert result.phase == "completed"

    def test_execution_core_task_records_growth_and_experience(self, tmp_path):
        class _FakeCapabilityService:
            async def execute_task(self, task):
                return {
                    "success": True,
                    "summary": f"Main-brain capability completed for {task.id}",
                }

        knowledge = _FakeKnowledgeService()
        learning_service = LearningService(
            engine=LearningEngine(tmp_path / "learning.sqlite3"),
            evidence_ledger=EvidenceLedger(),
        )
        learning_service.set_experience_memory_service(
            AgentExperienceMemoryService(knowledge_service=knowledge),
        )
        dispatcher, _task_store = _build_dispatcher_with_decisions(
            tmp_path,
            capability_service=_FakeCapabilityService(),
            learning_service=learning_service,
        )
        task = KernelTask(
            title="Run browser action",
            owner_agent_id="copaw-agent-runner",
            capability_ref="tool:browser_use",
            payload={
                "industry_instance_id": "industry-v1-acme",
                "industry_role_id": "execution-core",
                "owner_scope": "industry",
            },
        )

        dispatcher.submit(task)
        result = asyncio.run(dispatcher.execute_task(task.id))

        assert result.phase == "completed"
        growth = learning_service.list_growth(
            agent_id="copaw-agent-runner",
            task_id=task.id,
        )
        assert growth
        assert growth[0].task_id == task.id
        assert growth[0].change_type == "capability_completed"
        assert any(
            call["scope_type"] == "agent" and call["scope_id"] == "copaw-agent-runner"
            for call in knowledge.calls
        )

    def test_approve_decision_executes_task_by_decision_id(self, tmp_path):
        class _FakeCapabilityService:
            async def execute_task(self, task):
                return {"success": True, "summary": f"executed {task.id}"}

        dispatcher, task_store = _build_dispatcher_with_decisions(
            tmp_path,
            capability_service=_FakeCapabilityService(),
        )
        task = KernelTask(
            title="Decision approval task",
            risk_level="confirm",
            capability_ref="tool:get_current_time",
        )
        admitted = dispatcher.submit(task)

        assert admitted.decision_request_id is not None

        result = asyncio.run(dispatcher.approve_decision(admitted.decision_request_id))
        assert result.success is True
        assert result.phase == "completed"
        assert result.decision_request_id == admitted.decision_request_id
        assert result.trace_id == task.trace_id

        decision = task_store.get_decision_request(admitted.decision_request_id)
        assert decision is not None
        assert decision.status == "approved"

    def test_reject_decision_cancels_task_by_decision_id(self, tmp_path):
        dispatcher, task_store = _build_dispatcher_with_decisions(tmp_path)
        task = KernelTask(
            title="Decision rejection task",
            risk_level="confirm",
            capability_ref="tool:get_current_time",
        )
        admitted = dispatcher.submit(task)

        assert admitted.decision_request_id is not None

        result = dispatcher.reject_decision(
            admitted.decision_request_id,
            resolution="Rejected by operator.",
        )
        assert result.success is False
        assert result.phase == "cancelled"
        assert result.decision_request_id == admitted.decision_request_id
        assert result.trace_id == task.trace_id

        decision = task_store.get_decision_request(admitted.decision_request_id)
        assert decision is not None
        assert decision.status == "rejected"
        assert decision.resolution == "Rejected by operator."

    def test_parent_task_waits_for_child_tasks_before_completing(self, tmp_path):
        dispatcher, _task_store = _build_dispatcher_with_decisions(tmp_path)
        parent = KernelTask(
            id="parent-task",
            title="Parent task",
            capability_ref="system:dispatch_query",
        )
        child = KernelTask(
            id="child-task",
            parent_task_id=parent.id,
            title="Child task",
            capability_ref="system:dispatch_query",
        )
        dispatcher.submit(parent)
        dispatcher.submit(child)

        blocked = dispatcher.complete_task(parent.id, summary="parent done")
        assert blocked.phase == "executing"
        assert dispatcher.lifecycle.get_task(parent.id).phase == "executing"

        dispatcher.complete_task(child.id, summary="child done")
        assert dispatcher.lifecycle.get_task(parent.id).phase == "completed"

    def test_failed_child_task_fails_parent_task(self, tmp_path):
        dispatcher, _task_store = _build_dispatcher_with_decisions(tmp_path)
        parent = KernelTask(
            id="parent-task",
            title="Parent task",
            capability_ref="system:dispatch_query",
        )
        child = KernelTask(
            id="child-task",
            parent_task_id=parent.id,
            title="Child task",
            capability_ref="system:dispatch_query",
        )
        dispatcher.submit(parent)
        dispatcher.submit(child)

        dispatcher.fail_task(child.id, error="child failed")
        assert dispatcher.lifecycle.get_task(parent.id).phase == "failed"

    def test_fail_task_is_idempotent_for_terminal_task(self, tmp_path):
        dispatcher, task_store = _build_dispatcher_with_decisions(tmp_path)
        goal_service = _CountingGoalService()
        dispatcher.set_goal_service(goal_service)
        task = KernelTask(
            title="Idempotent fail task",
            capability_ref="system:dispatch_query",
            owner_agent_id="copaw-agent-runner",
            goal_id="goal-1",
        )
        admitted = dispatcher.submit(task)

        first = dispatcher.fail_task(admitted.task_id, error="first failure")
        second = dispatcher.fail_task(admitted.task_id, error="second failure")

        records = task_store._evidence_ledger.list_by_task(admitted.task_id)
        assert first.phase == "failed"
        assert second.phase == "failed"
        assert [record.result_summary for record in records] == ["first failure"]
        assert goal_service.reconcile_calls == [("goal-1", "task-terminal")]
        assert goal_service.resume_calls == [admitted.task_id]

    def test_cancel_task_is_idempotent_for_terminal_task(self, tmp_path):
        dispatcher, task_store = _build_dispatcher_with_decisions(tmp_path)
        goal_service = _CountingGoalService()
        dispatcher.set_goal_service(goal_service)
        task = KernelTask(
            title="Idempotent cancel task",
            capability_ref="system:dispatch_query",
            owner_agent_id="copaw-agent-runner",
            goal_id="goal-1",
        )
        admitted = dispatcher.submit(task)

        first = dispatcher.cancel_task(admitted.task_id, resolution="first cancel")
        second = dispatcher.cancel_task(admitted.task_id, resolution="second cancel")

        records = task_store._evidence_ledger.list_by_task(admitted.task_id)
        assert first.phase == "cancelled"
        assert second.phase == "cancelled"
        assert [record.result_summary for record in records] == ["first cancel"]
        assert goal_service.reconcile_calls == [("goal-1", "task-terminal")]
        assert goal_service.resume_calls == [admitted.task_id]


# ── Agent profile tests ─────────────────────────────────────────────


class TestAgentProfile:
    def test_default_agents_exist(self):
        assert len(DEFAULT_AGENTS) >= 3

    def test_default_agents_have_required_fields(self):
        for agent in DEFAULT_AGENTS:
            assert agent.agent_id
            assert agent.name
            assert agent.role_name
            assert agent.status

    def test_runner_agent_is_running(self):
        runner = next(
            (a for a in DEFAULT_AGENTS if a.agent_id == "copaw-agent-runner"),
            None,
        )
        assert runner is not None
        assert runner.status == "running"
        assert runner.role_name == "团队执行中枢"
