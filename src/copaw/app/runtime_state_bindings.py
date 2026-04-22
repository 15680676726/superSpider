# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .runtime_bootstrap_models import RuntimeBootstrap, RuntimeManagerStack
from .runtime_recovery_report import build_latest_recovery_report


def _materialize_automation_tasks(automation_tasks: list[Any] | None) -> Any:
    if automation_tasks is None:
        return []
    loop_snapshots = getattr(automation_tasks, "loop_snapshots", None)
    if callable(loop_snapshots):
        return automation_tasks
    return list(automation_tasks or [])


def build_runtime_state_bindings(
    *,
    runtime_host: object,
    bootstrap: RuntimeBootstrap,
    manager_stack: RuntimeManagerStack,
    startup_recovery_summary: object,
    automation_tasks: list[Any] | None = None,
) -> dict[str, object]:
    repositories = bootstrap.repositories
    latest_recovery_report = build_latest_recovery_report(
        startup_recovery_summary=startup_recovery_summary,
        automation_tasks=automation_tasks,
        automation_loop_runtime_repository=repositories.automation_loop_runtime_repository,
    )
    return {
        "runtime_host": runtime_host,
        "session_backend": bootstrap.session_backend,
        "conversation_compaction_service": bootstrap.conversation_compaction_service,
        "runtime_thread_history_reader": bootstrap.runtime_thread_history_reader,
        "channel_manager": manager_stack.channel_manager,
        "cron_manager": manager_stack.cron_manager,
        "job_repository": manager_stack.job_repository,
        "config_watcher": manager_stack.config_watcher,
        "mcp_manager": manager_stack.mcp_manager,
        "mcp_watcher": manager_stack.mcp_watcher,
        "runtime_provider": bootstrap.runtime_provider,
        "state_store": bootstrap.state_store,
        "task_repository": repositories.task_repository,
        "task_runtime_repository": repositories.task_runtime_repository,
        "runtime_frame_repository": repositories.runtime_frame_repository,
        "schedule_repository": repositories.schedule_repository,
        "goal_repository": repositories.goal_repository,
        "human_assist_task_repository": repositories.human_assist_task_repository,
        "work_context_repository": repositories.work_context_repository,
        "decision_request_repository": repositories.decision_request_repository,
        "governance_control_repository": repositories.governance_control_repository,
        "capability_override_repository": repositories.capability_override_repository,
        "agent_profile_override_repository": repositories.agent_profile_override_repository,
        "agent_runtime_repository": repositories.agent_runtime_repository,
        "agent_mailbox_repository": repositories.agent_mailbox_repository,
        "agent_checkpoint_repository": repositories.agent_checkpoint_repository,
        "agent_lease_repository": repositories.agent_lease_repository,
        "agent_thread_binding_repository": repositories.agent_thread_binding_repository,
        "industry_instance_repository": repositories.industry_instance_repository,
        "media_analysis_repository": repositories.media_analysis_repository,
        "operating_lane_repository": repositories.operating_lane_repository,
        "backlog_item_repository": repositories.backlog_item_repository,
        "operating_cycle_repository": repositories.operating_cycle_repository,
        "assignment_repository": repositories.assignment_repository,
        "agent_report_repository": repositories.agent_report_repository,
        "goal_override_repository": repositories.goal_override_repository,
        "strategy_memory_repository": repositories.strategy_memory_repository,
        "knowledge_chunk_repository": repositories.knowledge_chunk_repository,
        "memory_fact_index_repository": repositories.memory_fact_index_repository,
        "memory_entity_view_repository": repositories.memory_entity_view_repository,
        "memory_opinion_view_repository": repositories.memory_opinion_view_repository,
        "memory_relation_view_repository": repositories.memory_relation_view_repository,
        "memory_reflection_run_repository": repositories.memory_reflection_run_repository,
        "workflow_template_repository": repositories.workflow_template_repository,
        "workflow_preset_repository": repositories.workflow_preset_repository,
        "workflow_run_repository": repositories.workflow_run_repository,
        "fixed_sop_template_repository": repositories.fixed_sop_template_repository,
        "fixed_sop_binding_repository": repositories.fixed_sop_binding_repository,
        "routine_repository": repositories.routine_repository,
        "routine_run_repository": repositories.routine_run_repository,
        "prediction_case_repository": repositories.prediction_case_repository,
        "prediction_scenario_repository": repositories.prediction_scenario_repository,
        "prediction_signal_repository": repositories.prediction_signal_repository,
        "prediction_recommendation_repository": repositories.prediction_recommendation_repository,
        "prediction_review_repository": repositories.prediction_review_repository,
        "research_session_repository": repositories.research_session_repository,
        "evidence_ledger": bootstrap.evidence_ledger,
        "environment_registry": bootstrap.environment_registry,
        "environment_service": bootstrap.environment_service,
        "runtime_event_bus": bootstrap.runtime_event_bus,
        "runtime_health_service": bootstrap.runtime_health_service,
        "provider_admin_service": bootstrap.provider_admin_service,
        "buddy_onboarding_service": bootstrap.buddy_onboarding_service,
        "buddy_projection_service": bootstrap.buddy_projection_service,
        "startup_recovery_summary": startup_recovery_summary,
        "latest_recovery_report": latest_recovery_report,
        "session_mount_repository": repositories.session_mount_repository,
        "automation_loop_runtime_repository": repositories.automation_loop_runtime_repository,
        "external_runtime_repository": repositories.external_runtime_repository,
        "state_query_service": bootstrap.state_query_service,
        "evidence_query_service": bootstrap.evidence_query_service,
        "capability_candidate_service": bootstrap.capability_candidate_service,
        "capability_donor_service": bootstrap.capability_donor_service,
        "capability_portfolio_service": bootstrap.capability_portfolio_service,
        "skill_trial_service": bootstrap.skill_trial_service,
        "skill_lifecycle_decision_service": bootstrap.skill_lifecycle_decision_service,
        "human_assist_task_service": bootstrap.human_assist_task_service,
        "strategy_memory_service": bootstrap.strategy_memory_service,
        "work_context_service": bootstrap.work_context_service,
        "knowledge_service": bootstrap.knowledge_service,
        "media_service": bootstrap.media_service,
        "derived_memory_index_service": bootstrap.derived_memory_index_service,
        "memory_recall_service": bootstrap.memory_recall_service,
        "memory_reflection_service": bootstrap.memory_reflection_service,
        "memory_retain_service": bootstrap.memory_retain_service,
        "memory_sleep_service": bootstrap.memory_sleep_service,
        "memory_activation_service": bootstrap.memory_activation_service,
        "knowledge_graph_service": bootstrap.knowledge_graph_service,
        "agent_experience_service": bootstrap.agent_experience_service,
        "reporting_service": bootstrap.reporting_service,
        "operating_lane_service": bootstrap.operating_lane_service,
        "backlog_service": bootstrap.backlog_service,
        "operating_cycle_service": bootstrap.operating_cycle_service,
        "assignment_service": bootstrap.assignment_service,
        "agent_report_service": bootstrap.agent_report_service,
        "capability_service": bootstrap.capability_service,
        "agent_profile_service": bootstrap.agent_profile_service,
        "industry_service": bootstrap.industry_service,
        "workflow_template_service": bootstrap.workflow_template_service,
        "fixed_sop_service": bootstrap.fixed_sop_service,
        "routine_service": bootstrap.routine_service,
        "prediction_service": bootstrap.prediction_service,
        "goal_service": bootstrap.goal_service,
        "learning_service": bootstrap.learning_service,
        "governance_service": bootstrap.governance_service,
        "research_session_service": bootstrap.research_session_service,
        "kernel_dispatcher": bootstrap.kernel_dispatcher,
        "kernel_task_store": bootstrap.kernel_task_store,
        "kernel_tool_bridge": bootstrap.kernel_tool_bridge,
        "turn_executor": bootstrap.turn_executor,
        "main_brain_chat_service": bootstrap.main_brain_chat_service,
        "query_execution_service": bootstrap.query_execution_service,
        "external_runtime_service": bootstrap.external_runtime_service,
        "executor_runtime_service": bootstrap.executor_runtime_service,
        "executor_runtime_coordinator": bootstrap.executor_runtime_coordinator,
        "executor_runtime_port": bootstrap.executor_runtime_port,
        "sidecar_release_service": bootstrap.sidecar_release_service,
        "weixin_ilink_runtime_state": bootstrap.weixin_ilink_runtime_state,
        "automation_tasks": _materialize_automation_tasks(automation_tasks),
    }


def attach_runtime_state(
    app: FastAPI,
    *,
    runtime_host: object,
    bootstrap: RuntimeBootstrap,
    manager_stack: RuntimeManagerStack,
    startup_recovery_summary: object,
    automation_tasks: list[Any] | None = None,
) -> None:
    bindings = build_runtime_state_bindings(
        runtime_host=runtime_host,
        bootstrap=bootstrap,
        manager_stack=manager_stack,
        startup_recovery_summary=startup_recovery_summary,
        automation_tasks=automation_tasks,
    )
    for name, value in bindings.items():
        setattr(app.state, name, value)
