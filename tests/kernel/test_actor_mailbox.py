# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from copaw.kernel import ActorMailboxService
from copaw.state import AgentRuntimeRecord, SQLiteStateStore
from copaw.state.repositories import (
    SqliteAgentCheckpointRepository,
    SqliteAgentMailboxRepository,
    SqliteAgentRuntimeRepository,
)


def _build_mailbox_service(tmp_path):
    state_store = SQLiteStateStore(tmp_path / "actor-mailbox-state.db")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    mailbox_repository = SqliteAgentMailboxRepository(state_store)
    checkpoint_repository = SqliteAgentCheckpointRepository(state_store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-1",
            actor_key="industry:test:agent-1",
            actor_fingerprint="fp-agent-1",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="idle",
            industry_instance_id="industry-test",
            industry_role_id="operator",
            display_name="Agent 1",
            role_name="Operator",
        ),
    )
    mailbox_service = ActorMailboxService(
        mailbox_repository=mailbox_repository,
        runtime_repository=runtime_repository,
        checkpoint_repository=checkpoint_repository,
    )
    return mailbox_service, checkpoint_repository, runtime_repository


def test_actor_mailbox_terminal_checkpoint_and_complete_are_idempotent(tmp_path) -> None:
    mailbox_service, checkpoint_repository, runtime_repository = _build_mailbox_service(
        tmp_path,
    )
    item = mailbox_service.enqueue_item(
        agent_id="agent-1",
        task_id="task-complete",
        title="Completed task",
        capability_ref="system:dispatch_query",
        conversation_thread_id="agent-chat:agent-1",
    )
    mailbox_service.start_item(
        item.id,
        worker_id="actor-worker-test",
        task_id="task-complete",
    )

    first = mailbox_service.create_checkpoint(
        agent_id="agent-1",
        mailbox_id=item.id,
        task_id="task-complete",
        checkpoint_kind="task-result",
        status="applied",
        phase="completed",
        conversation_thread_id="agent-chat:agent-1",
        resume_payload={"mailbox_id": item.id, "task_id": "task-complete", "phase": "completed"},
        summary="Completed task-complete",
    )
    mailbox_service.complete_item(
        item.id,
        result_summary="Completed task-complete",
        checkpoint_id=first.id if first is not None else None,
        task_id="task-complete",
    )

    second = mailbox_service.create_checkpoint(
        agent_id="agent-1",
        mailbox_id=item.id,
        task_id="task-complete",
        checkpoint_kind="task-result",
        status="applied",
        phase="completed",
        conversation_thread_id="agent-chat:agent-1",
        resume_payload={"mailbox_id": item.id, "task_id": "task-complete", "phase": "completed"},
        summary="Completed task-complete",
    )
    mailbox_service.complete_item(
        item.id,
        result_summary="Completed task-complete",
        checkpoint_id=second.id if second is not None else None,
        task_id="task-complete",
    )

    checkpoints = checkpoint_repository.list_checkpoints(agent_id="agent-1", limit=None)
    terminal = [checkpoint for checkpoint in checkpoints if checkpoint.checkpoint_kind == "task-result"]
    assert first is not None
    assert second is not None
    assert second.id == first.id
    assert len(terminal) == 1
    stored = mailbox_service.get_item(item.id)
    assert stored is not None
    assert stored.status == "completed"
    runtime = runtime_repository.get_runtime("agent-1")
    assert runtime is not None
    assert runtime.runtime_status == "idle"


def test_actor_mailbox_startup_recovery_resume_payload_keeps_continuity_fields(
    tmp_path,
) -> None:
    mailbox_service, checkpoint_repository, runtime_repository = _build_mailbox_service(
        tmp_path,
    )
    item = mailbox_service.enqueue_item(
        agent_id="agent-1",
        task_id="task-running",
        title="Recover running task",
        capability_ref="system:dispatch_query",
        conversation_thread_id="agent-chat:agent-1",
        work_context_id="work-context-1",
        source_agent_id="execution-core-agent",
        payload={
            "request_context": {
                "session_id": "industry-chat:industry-1:execution-core",
                "context_key": "control-thread:industry-1",
                "work_context_id": "work-context-1",
            },
            "meta": {
                "assignment_id": "assignment-shadow",
                "lane_id": "lane-shadow",
                "cycle_id": "cycle-shadow",
                "report_back_mode": "shadow-report",
                "environment_ref": "session:shadow",
            },
        },
        metadata={
            "assignment_id": "assignment-1",
            "lane_id": "lane-1",
            "cycle_id": "cycle-1",
            "report_back_mode": "agent-report",
            "parent_task_id": "task-parent",
            "environment_ref": "session:console:shared",
            "industry_instance_id": "industry-1",
            "industry_role_id": "ops-worker",
            "execution_source": "assignment",
        },
    )
    mailbox_service.claim_next("agent-1", worker_id="actor-worker-test")
    mailbox_service.start_item(
        item.id,
        worker_id="actor-worker-test",
        task_id="task-running",
    )

    summary = mailbox_service.recover_orphaned_items(
        task_reader=lambda _task_id: SimpleNamespace(phase="executing"),
    )

    assert summary["requeued"] == 1
    checkpoints = checkpoint_repository.list_checkpoints(mailbox_id=item.id, limit=None)
    assert len(checkpoints) == 1
    assert checkpoints[0].checkpoint_kind == "resume"
    assert checkpoints[0].resume_payload == {
        "mailbox_id": item.id,
        "task_id": "task-running",
        "phase": "queued",
        "agent_id": "agent-1",
        "source_agent_id": "execution-core-agent",
        "capability_ref": "system:dispatch_query",
        "work_context_id": "work-context-1",
        "conversation_thread_id": "agent-chat:agent-1",
        "session_id": "industry-chat:industry-1:execution-core",
        "control_thread_id": "control-thread:industry-1",
        "assignment_id": "assignment-1",
        "lane_id": "lane-1",
        "cycle_id": "cycle-1",
        "report_back_mode": "agent-report",
        "parent_task_id": "task-parent",
        "environment_ref": "session:console:shared",
        "industry_instance_id": "industry-1",
        "industry_role_id": "ops-worker",
        "execution_source": "assignment",
        "recovered_from_status": "running",
        "task_phase": "executing",
    }
    runtime = runtime_repository.get_runtime("agent-1")
    assert runtime is not None
    assert runtime.runtime_status == "queued"
