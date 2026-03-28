# -*- coding: utf-8 -*-
"""SQLite-backed state store for the Phase 1 state foundation."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

STATE_SCHEMA_VERSION = 21

_SCHEMA = """
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    owner_scope TEXT,
    industry_instance_id TEXT,
    lane_id TEXT,
    cycle_id TEXT,
    goal_class TEXT NOT NULL DEFAULT 'goal',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_goals_updated_at
    ON goals(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_goals_created_at
    ON goals(created_at DESC);

CREATE TABLE IF NOT EXISTS work_contexts (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    context_type TEXT NOT NULL DEFAULT 'generic',
    status TEXT NOT NULL DEFAULT 'active',
    context_key TEXT,
    owner_scope TEXT,
    owner_agent_id TEXT,
    industry_instance_id TEXT,
    primary_thread_id TEXT,
    source_kind TEXT,
    source_ref TEXT,
    parent_work_context_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_work_contexts_context_key
    ON work_contexts(context_key);
CREATE INDEX IF NOT EXISTS idx_work_contexts_type_status
    ON work_contexts(context_type, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_work_contexts_owner
    ON work_contexts(owner_agent_id, owner_scope, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_work_contexts_industry
    ON work_contexts(industry_instance_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_work_contexts_thread
    ON work_contexts(primary_thread_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    goal_id TEXT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    owner_agent_id TEXT,
    parent_task_id TEXT,
    work_context_id TEXT,
    seed_source TEXT,
    constraints_summary TEXT,
    acceptance_criteria TEXT,
    current_risk_level TEXT NOT NULL DEFAULT 'auto',
    industry_instance_id TEXT,
    assignment_id TEXT,
    lane_id TEXT,
    cycle_id TEXT,
    report_back_mode TEXT NOT NULL DEFAULT 'summary',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_goal_id ON tasks(goal_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_owner_agent_id ON tasks(owner_agent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_parent_task_id ON tasks(parent_task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_work_context_id ON tasks(work_context_id);
CREATE INDEX IF NOT EXISTS idx_tasks_task_type ON tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);

CREATE TABLE IF NOT EXISTS human_assist_tasks (
    id TEXT PRIMARY KEY,
    industry_instance_id TEXT,
    assignment_id TEXT,
    task_id TEXT,
    chat_thread_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    task_type TEXT NOT NULL,
    reason_code TEXT,
    reason_summary TEXT NOT NULL DEFAULT '',
    required_action TEXT NOT NULL DEFAULT '',
    submission_mode TEXT NOT NULL DEFAULT 'chat-message',
    acceptance_mode TEXT NOT NULL DEFAULT 'anchor_verified',
    acceptance_spec_json TEXT NOT NULL DEFAULT '{}',
    resume_checkpoint_ref TEXT,
    status TEXT NOT NULL DEFAULT 'created',
    reward_preview_json TEXT NOT NULL DEFAULT '{}',
    reward_result_json TEXT NOT NULL DEFAULT '{}',
    block_evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    submission_evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    verification_evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    submission_text TEXT,
    submission_payload_json TEXT NOT NULL DEFAULT '{}',
    verification_payload_json TEXT NOT NULL DEFAULT '{}',
    issued_at TEXT,
    submitted_at TEXT,
    verified_at TEXT,
    closed_at TEXT,
    expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_human_assist_tasks_thread_updated
    ON human_assist_tasks(chat_thread_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_human_assist_tasks_status
    ON human_assist_tasks(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_human_assist_tasks_assignment
    ON human_assist_tasks(assignment_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_human_assist_tasks_task
    ON human_assist_tasks(task_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS task_runtimes (
    task_id TEXT PRIMARY KEY,
    runtime_status TEXT NOT NULL,
    current_phase TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    active_environment_id TEXT,
    last_result_summary TEXT,
    last_error_summary TEXT,
    last_owner_agent_id TEXT,
    last_evidence_id TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_task_runtimes_status
    ON task_runtimes(runtime_status);
CREATE INDEX IF NOT EXISTS idx_task_runtimes_updated_at
    ON task_runtimes(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_task_runtimes_owner_updated_at
    ON task_runtimes(last_owner_agent_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS runtime_frames (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    goal_summary TEXT NOT NULL DEFAULT '',
    owner_agent_id TEXT,
    current_phase TEXT NOT NULL,
    current_risk_level TEXT NOT NULL DEFAULT 'auto',
    environment_summary TEXT NOT NULL DEFAULT '',
    evidence_summary TEXT NOT NULL DEFAULT '',
    constraints_summary TEXT,
    capabilities_summary TEXT,
    pending_decisions_summary TEXT,
    budget_summary TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_runtime_frames_task_created_at
    ON runtime_frames(task_id, created_at DESC);

CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    cron TEXT NOT NULL,
    timezone TEXT NOT NULL,
    status TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    task_type TEXT NOT NULL,
    target_channel TEXT,
    target_user_id TEXT,
    target_session_id TEXT,
    last_run_at TEXT,
    next_run_at TEXT,
    last_error TEXT,
    source_ref TEXT,
    spec_payload_json TEXT NOT NULL DEFAULT '{}',
    schedule_kind TEXT NOT NULL DEFAULT 'cadence',
    trigger_target TEXT,
    lane_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_schedules_status
    ON schedules(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_schedules_lane
    ON schedules(lane_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS workflow_templates (
    template_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    version TEXT NOT NULL,
    industry_tags_json TEXT NOT NULL DEFAULT '[]',
    team_modes_json TEXT NOT NULL DEFAULT '[]',
    dependency_capability_ids_json TEXT NOT NULL DEFAULT '[]',
    suggested_role_ids_json TEXT NOT NULL DEFAULT '[]',
    owner_role_id TEXT,
    parameter_schema_json TEXT NOT NULL DEFAULT '{}',
    step_specs_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workflow_templates_category
    ON workflow_templates(category, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS fixed_sop_templates (
    template_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    version TEXT NOT NULL DEFAULT 'v1',
    source_kind TEXT NOT NULL DEFAULT 'builtin',
    source_ref TEXT,
    owner_role_id TEXT,
    suggested_role_ids_json TEXT NOT NULL DEFAULT '[]',
    industry_tags_json TEXT NOT NULL DEFAULT '[]',
    capability_tags_json TEXT NOT NULL DEFAULT '[]',
    risk_baseline TEXT NOT NULL DEFAULT 'guarded',
    input_schema_json TEXT NOT NULL DEFAULT '{}',
    output_schema_json TEXT NOT NULL DEFAULT '{}',
    writeback_contract_json TEXT NOT NULL DEFAULT '{}',
    node_graph_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fixed_sop_templates_status
    ON fixed_sop_templates(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_fixed_sop_templates_owner_role
    ON fixed_sop_templates(owner_role_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS fixed_sop_bindings (
    binding_id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    binding_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    owner_scope TEXT,
    owner_agent_id TEXT,
    industry_instance_id TEXT,
    workflow_template_id TEXT,
    trigger_mode TEXT NOT NULL DEFAULT 'manual',
    trigger_ref TEXT,
    input_mapping_json TEXT NOT NULL DEFAULT '{}',
    output_mapping_json TEXT NOT NULL DEFAULT '{}',
    timeout_policy_json TEXT NOT NULL DEFAULT '{}',
    retry_policy_json TEXT NOT NULL DEFAULT '{}',
    risk_baseline TEXT NOT NULL DEFAULT 'guarded',
    last_run_id TEXT,
    last_verified_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(template_id) REFERENCES fixed_sop_templates(template_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fixed_sop_bindings_template
    ON fixed_sop_bindings(template_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_fixed_sop_bindings_instance
    ON fixed_sop_bindings(industry_instance_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_fixed_sop_bindings_owner
    ON fixed_sop_bindings(owner_agent_id, owner_scope, updated_at DESC);

CREATE TABLE IF NOT EXISTS workflow_presets (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    name TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    owner_scope TEXT,
    industry_scope TEXT,
    parameter_overrides_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workflow_presets_template
    ON workflow_presets(template_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_presets_scope
    ON workflow_presets(template_id, industry_scope, owner_scope, updated_at DESC);

CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    owner_scope TEXT,
    owner_agent_id TEXT,
    industry_instance_id TEXT,
    parameter_payload_json TEXT NOT NULL DEFAULT '{}',
    preview_payload_json TEXT NOT NULL DEFAULT '{}',
    goal_ids_json TEXT NOT NULL DEFAULT '[]',
    schedule_ids_json TEXT NOT NULL DEFAULT '[]',
    task_ids_json TEXT NOT NULL DEFAULT '[]',
    decision_ids_json TEXT NOT NULL DEFAULT '[]',
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_template
    ON workflow_runs(template_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_instance
    ON workflow_runs(industry_instance_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS execution_routines (
    id TEXT PRIMARY KEY,
    routine_key TEXT NOT NULL,
    name TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    owner_scope TEXT,
    owner_agent_id TEXT,
    source_capability_id TEXT,
    trigger_kind TEXT NOT NULL DEFAULT 'manual',
    engine_kind TEXT NOT NULL DEFAULT 'browser',
    environment_kind TEXT NOT NULL DEFAULT 'browser',
    session_requirements_json TEXT NOT NULL DEFAULT '{}',
    isolation_policy_json TEXT NOT NULL DEFAULT '{}',
    lock_scope_json TEXT NOT NULL DEFAULT '[]',
    input_schema_json TEXT NOT NULL DEFAULT '{}',
    preconditions_json TEXT NOT NULL DEFAULT '[]',
    expected_observations_json TEXT NOT NULL DEFAULT '[]',
    action_contract_json TEXT NOT NULL DEFAULT '[]',
    success_signature_json TEXT NOT NULL DEFAULT '{}',
    drift_signals_json TEXT NOT NULL DEFAULT '[]',
    replay_policy_json TEXT NOT NULL DEFAULT '{}',
    fallback_policy_json TEXT NOT NULL DEFAULT '{}',
    risk_baseline TEXT NOT NULL DEFAULT 'guarded',
    evidence_expectations_json TEXT NOT NULL DEFAULT '[]',
    source_evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    last_verified_at TEXT,
    success_rate REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_execution_routines_status
    ON execution_routines(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_routines_engine
    ON execution_routines(engine_kind, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_routines_owner
    ON execution_routines(owner_agent_id, owner_scope, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_routines_key
    ON execution_routines(routine_key, updated_at DESC);

CREATE TABLE IF NOT EXISTS routine_runs (
    id TEXT PRIMARY KEY,
    routine_id TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'manual',
    source_ref TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    input_payload_json TEXT NOT NULL DEFAULT '{}',
    owner_agent_id TEXT,
    owner_scope TEXT,
    environment_id TEXT,
    session_id TEXT,
    lease_ref TEXT,
    checkpoint_ref TEXT,
    deterministic_result TEXT,
    failure_class TEXT,
    fallback_mode TEXT,
    fallback_task_id TEXT,
    decision_request_id TEXT,
    output_summary TEXT,
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(routine_id) REFERENCES execution_routines(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_routine_runs_routine
    ON routine_runs(routine_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_routine_runs_status
    ON routine_runs(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_routine_runs_owner
    ON routine_runs(owner_agent_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_routine_runs_failure
    ON routine_runs(failure_class, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_routine_runs_started_at
    ON routine_runs(started_at DESC);

CREATE TABLE IF NOT EXISTS prediction_cases (
    case_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    case_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    topic_type TEXT NOT NULL,
    owner_scope TEXT,
    owner_agent_id TEXT,
    industry_instance_id TEXT,
    workflow_run_id TEXT,
    question TEXT NOT NULL DEFAULT '',
    time_window_days INTEGER NOT NULL DEFAULT 7,
    overall_confidence REAL NOT NULL DEFAULT 0.5,
    primary_recommendation_id TEXT,
    input_payload_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prediction_cases_kind
    ON prediction_cases(case_kind, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_cases_scope
    ON prediction_cases(industry_instance_id, owner_scope, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_cases_owner_agent
    ON prediction_cases(owner_agent_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_cases_created_at
    ON prediction_cases(created_at DESC);

CREATE TABLE IF NOT EXISTS prediction_scenarios (
    scenario_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    scenario_kind TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.5,
    goal_delta REAL NOT NULL DEFAULT 0,
    task_load_delta REAL NOT NULL DEFAULT 0,
    risk_delta REAL NOT NULL DEFAULT 0,
    resource_delta REAL NOT NULL DEFAULT 0,
    externality_delta REAL NOT NULL DEFAULT 0,
    assumptions_json TEXT NOT NULL DEFAULT '[]',
    risk_factors_json TEXT NOT NULL DEFAULT '[]',
    recommendation_ids_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES prediction_cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_prediction_scenarios_case
    ON prediction_scenarios(case_id, scenario_kind, updated_at DESC);

CREATE TABLE IF NOT EXISTS prediction_signals (
    signal_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    label TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    source_kind TEXT NOT NULL,
    source_ref TEXT,
    direction TEXT NOT NULL,
    strength REAL NOT NULL DEFAULT 0,
    metric_key TEXT,
    report_id TEXT,
    evidence_id TEXT,
    agent_id TEXT,
    workflow_run_id TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES prediction_cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_prediction_signals_case
    ON prediction_signals(case_id, strength DESC, updated_at DESC);

CREATE TABLE IF NOT EXISTS prediction_recommendations (
    recommendation_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    recommendation_type TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0.5,
    risk_level TEXT NOT NULL DEFAULT 'guarded',
    action_kind TEXT NOT NULL,
    executable INTEGER NOT NULL DEFAULT 0,
    auto_eligible INTEGER NOT NULL DEFAULT 0,
    auto_executed INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    target_agent_id TEXT,
    target_goal_id TEXT,
    target_schedule_id TEXT,
    target_capability_ids_json TEXT NOT NULL DEFAULT '[]',
    decision_request_id TEXT,
    execution_task_id TEXT,
    execution_evidence_id TEXT,
    outcome_summary TEXT,
    action_payload_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES prediction_cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_prediction_recommendations_case
    ON prediction_recommendations(case_id, priority DESC, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_recommendations_status
    ON prediction_recommendations(status, auto_eligible, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_recommendations_target_agent
    ON prediction_recommendations(target_agent_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_recommendations_created_at
    ON prediction_recommendations(created_at DESC);

CREATE TABLE IF NOT EXISTS prediction_reviews (
    review_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    recommendation_id TEXT,
    reviewer TEXT,
    summary TEXT NOT NULL DEFAULT '',
    outcome TEXT NOT NULL,
    adopted INTEGER,
    benefit_score REAL,
    actual_payload_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES prediction_cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_prediction_reviews_case
    ON prediction_reviews(case_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_reviews_updated_at
    ON prediction_reviews(updated_at DESC);

CREATE TABLE IF NOT EXISTS decision_requests (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL,
    source_evidence_id TEXT,
    source_patch_id TEXT,
    requested_by TEXT,
    resolution TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    expires_at TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_decision_requests_task_id
    ON decision_requests(task_id);
CREATE INDEX IF NOT EXISTS idx_decision_requests_created_at
    ON decision_requests(created_at DESC);

CREATE TABLE IF NOT EXISTS governance_controls (
    id TEXT PRIMARY KEY,
    emergency_stop_active INTEGER NOT NULL DEFAULT 0,
    emergency_reason TEXT,
    emergency_actor TEXT,
    paused_schedule_ids_json TEXT NOT NULL DEFAULT '[]',
    channel_shutdown_applied INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS environment_mounts (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    display_name TEXT NOT NULL,
    ref TEXT NOT NULL,
    status TEXT NOT NULL,
    last_active_at TEXT,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    lease_status TEXT,
    lease_owner TEXT,
    lease_token TEXT,
    lease_acquired_at TEXT,
    lease_expires_at TEXT,
    live_handle_ref TEXT
);

CREATE INDEX IF NOT EXISTS idx_environment_mounts_kind
    ON environment_mounts(kind);
CREATE INDEX IF NOT EXISTS idx_environment_mounts_status
    ON environment_mounts(status);
CREATE INDEX IF NOT EXISTS idx_environment_mounts_last_active
    ON environment_mounts(last_active_at DESC);

CREATE TABLE IF NOT EXISTS session_mounts (
    id TEXT PRIMARY KEY,
    environment_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    session_id TEXT NOT NULL,
    user_id TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_active_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    lease_status TEXT,
    lease_owner TEXT,
    lease_token TEXT,
    lease_acquired_at TEXT,
    lease_expires_at TEXT,
    live_handle_ref TEXT
);

CREATE INDEX IF NOT EXISTS idx_session_mounts_channel
    ON session_mounts(channel);
CREATE INDEX IF NOT EXISTS idx_session_mounts_user_id
    ON session_mounts(user_id);
CREATE INDEX IF NOT EXISTS idx_session_mounts_last_active
    ON session_mounts(last_active_at DESC);

CREATE TABLE IF NOT EXISTS capability_overrides (
    capability_id TEXT PRIMARY KEY,
    enabled INTEGER,
    forced_risk_level TEXT,
    reason TEXT,
    source_patch_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_capability_overrides_updated_at
    ON capability_overrides(updated_at DESC);

CREATE TABLE IF NOT EXISTS agent_profile_overrides (
    agent_id TEXT PRIMARY KEY,
    name TEXT,
    role_name TEXT,
    role_summary TEXT,
    agent_class TEXT,
    employment_mode TEXT,
    activation_mode TEXT,
    suspendable INTEGER,
    reports_to TEXT,
    mission TEXT,
    status TEXT,
    risk_level TEXT,
    current_goal_id TEXT,
    current_goal TEXT,
    current_task_id TEXT,
    industry_instance_id TEXT,
    industry_role_id TEXT,
    environment_summary TEXT,
    today_output_summary TEXT,
    latest_evidence_summary TEXT,
    environment_constraints_json TEXT,
    evidence_expectations_json TEXT,
    capabilities_json TEXT,
    reason TEXT,
    source_patch_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_profile_overrides_updated_at
    ON agent_profile_overrides(updated_at DESC);

CREATE TABLE IF NOT EXISTS agent_runtimes (
    agent_id TEXT PRIMARY KEY,
    actor_key TEXT NOT NULL,
    actor_fingerprint TEXT,
    actor_class TEXT NOT NULL,
    desired_state TEXT NOT NULL,
    runtime_status TEXT NOT NULL,
    employment_mode TEXT NOT NULL DEFAULT 'career',
    activation_mode TEXT NOT NULL,
    persistent INTEGER NOT NULL DEFAULT 1,
    industry_instance_id TEXT,
    industry_role_id TEXT,
    display_name TEXT,
    role_name TEXT,
    current_task_id TEXT,
    current_mailbox_id TEXT,
    current_environment_id TEXT,
    queue_depth INTEGER NOT NULL DEFAULT 0,
    last_started_at TEXT,
    last_heartbeat_at TEXT,
    last_stopped_at TEXT,
    last_error_summary TEXT,
    last_result_summary TEXT,
    last_checkpoint_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_runtimes_instance
    ON agent_runtimes(industry_instance_id, industry_role_id);
CREATE INDEX IF NOT EXISTS idx_agent_runtimes_status
    ON agent_runtimes(runtime_status, updated_at DESC);

CREATE TABLE IF NOT EXISTS agent_mailbox (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task_id TEXT,
    work_context_id TEXT,
    parent_mailbox_id TEXT,
    source_agent_id TEXT,
    envelope_type TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    capability_ref TEXT,
    conversation_thread_id TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    result_summary TEXT,
    error_summary TEXT,
    lease_owner TEXT,
    lease_token TEXT,
    claimed_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    retry_after_at TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_mailbox_agent_status
    ON agent_mailbox(agent_id, status, priority DESC, updated_at ASC);
CREATE INDEX IF NOT EXISTS idx_agent_mailbox_thread
    ON agent_mailbox(conversation_thread_id);
CREATE INDEX IF NOT EXISTS idx_agent_mailbox_work_context
    ON agent_mailbox(work_context_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS agent_checkpoints (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    mailbox_id TEXT,
    task_id TEXT,
    work_context_id TEXT,
    checkpoint_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT '',
    cursor TEXT,
    conversation_thread_id TEXT,
    environment_ref TEXT,
    snapshot_payload_json TEXT NOT NULL DEFAULT '{}',
    resume_payload_json TEXT NOT NULL DEFAULT '{}',
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_checkpoints_agent
    ON agent_checkpoints(agent_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_checkpoints_mailbox
    ON agent_checkpoints(mailbox_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_checkpoints_work_context
    ON agent_checkpoints(work_context_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS agent_leases (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    lease_kind TEXT NOT NULL,
    resource_ref TEXT NOT NULL,
    lease_status TEXT NOT NULL,
    lease_token TEXT,
    owner TEXT,
    acquired_at TEXT NOT NULL,
    expires_at TEXT,
    heartbeat_at TEXT,
    released_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_leases_agent_status
    ON agent_leases(agent_id, lease_status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_leases_resource
    ON agent_leases(resource_ref, lease_status);

CREATE TABLE IF NOT EXISTS agent_thread_bindings (
    thread_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    binding_kind TEXT NOT NULL,
    industry_instance_id TEXT,
    industry_role_id TEXT,
    work_context_id TEXT,
    owner_scope TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    alias_of_thread_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_thread_bindings_agent
    ON agent_thread_bindings(agent_id, active, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_thread_bindings_alias
    ON agent_thread_bindings(alias_of_thread_id);
CREATE INDEX IF NOT EXISTS idx_agent_thread_bindings_work_context
    ON agent_thread_bindings(work_context_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS goal_overrides (
    goal_id TEXT PRIMARY KEY,
    title TEXT,
    summary TEXT,
    status TEXT,
    priority INTEGER,
    owner_scope TEXT,
    plan_steps_json TEXT,
    compiler_context_json TEXT NOT NULL DEFAULT '{}',
    reason TEXT,
    source_patch_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_goal_overrides_updated_at
    ON goal_overrides(updated_at DESC);

CREATE TABLE IF NOT EXISTS industry_instances (
    instance_id TEXT PRIMARY KEY,
    bootstrap_kind TEXT NOT NULL,
    label TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    owner_scope TEXT NOT NULL,
    status TEXT NOT NULL,
    profile_payload_json TEXT NOT NULL DEFAULT '{}',
    team_payload_json TEXT NOT NULL DEFAULT '{}',
    execution_core_identity_payload_json TEXT NOT NULL DEFAULT '{}',
    goal_ids_json TEXT NOT NULL DEFAULT '[]',
    agent_ids_json TEXT NOT NULL DEFAULT '[]',
    schedule_ids_json TEXT NOT NULL DEFAULT '[]',
    lifecycle_status TEXT NOT NULL DEFAULT 'running',
    autonomy_status TEXT NOT NULL DEFAULT 'waiting-confirm',
    current_cycle_id TEXT,
    next_cycle_due_at TEXT,
    last_cycle_started_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_industry_instances_owner_scope
    ON industry_instances(owner_scope);
CREATE INDEX IF NOT EXISTS idx_industry_instances_updated_at
    ON industry_instances(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_industry_instances_current_cycle
    ON industry_instances(current_cycle_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS media_analyses (
    analysis_id TEXT PRIMARY KEY,
    industry_instance_id TEXT,
    thread_id TEXT,
    entry_point TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT 'reference-only',
    source_kind TEXT NOT NULL,
    source_ref TEXT,
    source_hash TEXT,
    declared_media_type TEXT,
    detected_media_type TEXT NOT NULL DEFAULT 'unknown',
    analysis_mode TEXT NOT NULL DEFAULT 'standard',
    status TEXT NOT NULL DEFAULT 'queued',
    title TEXT NOT NULL DEFAULT '',
    url TEXT,
    filename TEXT,
    mime_type TEXT,
    size_bytes INTEGER,
    asset_artifact_ids_json TEXT NOT NULL DEFAULT '[]',
    derived_artifact_ids_json TEXT NOT NULL DEFAULT '[]',
    transcript_artifact_id TEXT,
    structured_summary_json TEXT NOT NULL DEFAULT '{}',
    timeline_summary_json TEXT NOT NULL DEFAULT '[]',
    entities_json TEXT NOT NULL DEFAULT '[]',
    claims_json TEXT NOT NULL DEFAULT '[]',
    recommended_actions_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    knowledge_document_ids_json TEXT NOT NULL DEFAULT '[]',
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    strategy_writeback_status TEXT,
    backlog_writeback_status TEXT,
    error_message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_media_analyses_instance
    ON media_analyses(industry_instance_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_media_analyses_thread
    ON media_analyses(thread_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_media_analyses_entry
    ON media_analyses(entry_point, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_media_analyses_status
    ON media_analyses(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS operating_lanes (
    id TEXT PRIMARY KEY,
    industry_instance_id TEXT NOT NULL,
    lane_key TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    owner_agent_id TEXT,
    owner_role_id TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    health_status TEXT NOT NULL DEFAULT 'healthy',
    source_ref TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(industry_instance_id) REFERENCES industry_instances(instance_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_operating_lanes_instance
    ON operating_lanes(industry_instance_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_operating_lanes_status
    ON operating_lanes(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_operating_lanes_owner
    ON operating_lanes(owner_agent_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS backlog_items (
    id TEXT PRIMARY KEY,
    industry_instance_id TEXT NOT NULL,
    lane_id TEXT,
    cycle_id TEXT,
    assignment_id TEXT,
    goal_id TEXT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    priority INTEGER NOT NULL DEFAULT 0,
    source_kind TEXT NOT NULL DEFAULT 'operator',
    source_ref TEXT,
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(industry_instance_id) REFERENCES industry_instances(instance_id) ON DELETE CASCADE,
    FOREIGN KEY(lane_id) REFERENCES operating_lanes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_backlog_items_instance
    ON backlog_items(industry_instance_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_backlog_items_status
    ON backlog_items(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_backlog_items_cycle
    ON backlog_items(cycle_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_backlog_items_lane
    ON backlog_items(lane_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS operating_cycles (
    id TEXT PRIMARY KEY,
    industry_instance_id TEXT NOT NULL,
    cycle_kind TEXT NOT NULL DEFAULT 'daily',
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'planned',
    source_ref TEXT,
    started_at TEXT,
    due_at TEXT,
    completed_at TEXT,
    focus_lane_ids_json TEXT NOT NULL DEFAULT '[]',
    backlog_item_ids_json TEXT NOT NULL DEFAULT '[]',
    goal_ids_json TEXT NOT NULL DEFAULT '[]',
    assignment_ids_json TEXT NOT NULL DEFAULT '[]',
    report_ids_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(industry_instance_id) REFERENCES industry_instances(instance_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_operating_cycles_instance
    ON operating_cycles(industry_instance_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_operating_cycles_status
    ON operating_cycles(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_operating_cycles_due
    ON operating_cycles(due_at, updated_at DESC);

CREATE TABLE IF NOT EXISTS assignments (
    id TEXT PRIMARY KEY,
    industry_instance_id TEXT NOT NULL,
    cycle_id TEXT,
    lane_id TEXT,
    backlog_item_id TEXT,
    goal_id TEXT,
    task_id TEXT,
    owner_agent_id TEXT,
    owner_role_id TEXT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'planned',
    report_back_mode TEXT NOT NULL DEFAULT 'summary',
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    last_report_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(industry_instance_id) REFERENCES industry_instances(instance_id) ON DELETE CASCADE,
    FOREIGN KEY(cycle_id) REFERENCES operating_cycles(id) ON DELETE SET NULL,
    FOREIGN KEY(lane_id) REFERENCES operating_lanes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_assignments_instance
    ON assignments(industry_instance_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_assignments_cycle
    ON assignments(cycle_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_assignments_goal
    ON assignments(goal_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_assignments_status
    ON assignments(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_assignments_owner
    ON assignments(owner_agent_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS agent_reports (
    id TEXT PRIMARY KEY,
    industry_instance_id TEXT NOT NULL,
    cycle_id TEXT,
    assignment_id TEXT,
    goal_id TEXT,
    task_id TEXT,
    work_context_id TEXT,
    lane_id TEXT,
    owner_agent_id TEXT,
    owner_role_id TEXT,
    report_kind TEXT NOT NULL DEFAULT 'task-terminal',
    headline TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    findings_json TEXT NOT NULL DEFAULT '[]',
    uncertainties_json TEXT NOT NULL DEFAULT '[]',
    recommendation TEXT,
    needs_followup INTEGER NOT NULL DEFAULT 0,
    followup_reason TEXT,
    status TEXT NOT NULL DEFAULT 'recorded',
    result TEXT,
    risk_level TEXT NOT NULL DEFAULT 'auto',
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    decision_ids_json TEXT NOT NULL DEFAULT '[]',
    processed INTEGER NOT NULL DEFAULT 0,
    processed_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(industry_instance_id) REFERENCES industry_instances(instance_id) ON DELETE CASCADE,
    FOREIGN KEY(cycle_id) REFERENCES operating_cycles(id) ON DELETE SET NULL,
    FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_reports_instance
    ON agent_reports(industry_instance_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_reports_cycle
    ON agent_reports(cycle_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_reports_assignment
    ON agent_reports(assignment_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_reports_task
    ON agent_reports(task_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_reports_processed
    ON agent_reports(processed, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_reports_work_context
    ON agent_reports(work_context_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS strategy_memories (
    strategy_id TEXT PRIMARY KEY,
    scope_type TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    owner_agent_id TEXT,
    owner_scope TEXT,
    industry_instance_id TEXT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    mission TEXT NOT NULL DEFAULT '',
    north_star TEXT NOT NULL DEFAULT '',
    priority_order_json TEXT NOT NULL DEFAULT '[]',
    thinking_axes_json TEXT NOT NULL DEFAULT '[]',
    delegation_policy_json TEXT NOT NULL DEFAULT '[]',
    direct_execution_policy_json TEXT NOT NULL DEFAULT '[]',
    execution_constraints_json TEXT NOT NULL DEFAULT '[]',
    evidence_requirements_json TEXT NOT NULL DEFAULT '[]',
    active_goal_ids_json TEXT NOT NULL DEFAULT '[]',
    active_goal_titles_json TEXT NOT NULL DEFAULT '[]',
    teammate_contracts_json TEXT NOT NULL DEFAULT '[]',
    lane_weights_json TEXT NOT NULL DEFAULT '{}',
    planning_policy_json TEXT NOT NULL DEFAULT '[]',
    current_focuses_json TEXT NOT NULL DEFAULT '[]',
    paused_lane_ids_json TEXT NOT NULL DEFAULT '[]',
    review_rules_json TEXT NOT NULL DEFAULT '[]',
    source_ref TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_strategy_memories_scope
    ON strategy_memories(scope_type, scope_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_memories_owner
    ON strategy_memories(owner_agent_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_memories_status
    ON strategy_memories(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    source_ref TEXT,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    role_bindings_json TEXT NOT NULL DEFAULT '[]',
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document_id
    ON knowledge_chunks(document_id, chunk_index ASC);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_updated_at
    ON knowledge_chunks(updated_at DESC);

CREATE TABLE IF NOT EXISTS memory_fact_index (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    scope_type TEXT NOT NULL DEFAULT 'global',
    scope_id TEXT NOT NULL,
    owner_agent_id TEXT,
    owner_scope TEXT,
    industry_instance_id TEXT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    content_excerpt TEXT NOT NULL DEFAULT '',
    content_text TEXT NOT NULL DEFAULT '',
    entity_keys_json TEXT NOT NULL DEFAULT '[]',
    opinion_keys_json TEXT NOT NULL DEFAULT '[]',
    tags_json TEXT NOT NULL DEFAULT '[]',
    role_bindings_json TEXT NOT NULL DEFAULT '[]',
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0.5,
    quality_score REAL NOT NULL DEFAULT 0.5,
    source_updated_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_fact_index_source
    ON memory_fact_index(source_type, source_ref);
CREATE INDEX IF NOT EXISTS idx_memory_fact_index_scope
    ON memory_fact_index(scope_type, scope_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_fact_index_owner
    ON memory_fact_index(owner_agent_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_fact_index_industry
    ON memory_fact_index(industry_instance_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS memory_entity_views (
    entity_id TEXT PRIMARY KEY,
    entity_key TEXT NOT NULL,
    scope_type TEXT NOT NULL DEFAULT 'global',
    scope_id TEXT NOT NULL,
    owner_agent_id TEXT,
    industry_instance_id TEXT,
    display_name TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'concept',
    summary TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.5,
    supporting_refs_json TEXT NOT NULL DEFAULT '[]',
    contradicting_refs_json TEXT NOT NULL DEFAULT '[]',
    related_entities_json TEXT NOT NULL DEFAULT '[]',
    source_refs_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_entity_views_scope
    ON memory_entity_views(scope_type, scope_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_entity_views_key
    ON memory_entity_views(entity_key, updated_at DESC);

CREATE TABLE IF NOT EXISTS memory_opinion_views (
    opinion_id TEXT PRIMARY KEY,
    subject_key TEXT NOT NULL,
    scope_type TEXT NOT NULL DEFAULT 'global',
    scope_id TEXT NOT NULL,
    owner_agent_id TEXT,
    industry_instance_id TEXT,
    opinion_key TEXT NOT NULL,
    stance TEXT NOT NULL DEFAULT 'neutral',
    summary TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.5,
    supporting_refs_json TEXT NOT NULL DEFAULT '[]',
    contradicting_refs_json TEXT NOT NULL DEFAULT '[]',
    entity_keys_json TEXT NOT NULL DEFAULT '[]',
    source_refs_json TEXT NOT NULL DEFAULT '[]',
    last_reflected_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_opinion_views_scope
    ON memory_opinion_views(scope_type, scope_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_opinion_views_subject
    ON memory_opinion_views(subject_key, updated_at DESC);

CREATE TABLE IF NOT EXISTS memory_reflection_runs (
    run_id TEXT PRIMARY KEY,
    scope_type TEXT NOT NULL DEFAULT 'global',
    scope_id TEXT NOT NULL,
    owner_agent_id TEXT,
    industry_instance_id TEXT,
    trigger_kind TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'queued',
    summary TEXT NOT NULL DEFAULT '',
    source_refs_json TEXT NOT NULL DEFAULT '[]',
    generated_entity_ids_json TEXT NOT NULL DEFAULT '[]',
    generated_opinion_ids_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_reflection_runs_scope
    ON memory_reflection_runs(scope_type, scope_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_reflection_runs_status
    ON memory_reflection_runs(status, updated_at DESC);
"""

_ADDITIVE_SCHEMA_COLUMNS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "schedules",
        (
            ("spec_payload_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("schedule_kind", "TEXT NOT NULL DEFAULT 'cadence'"),
            ("trigger_target", "TEXT"),
            ("lane_id", "TEXT"),
        ),
    ),
    ("decision_requests", (("expires_at", "TEXT"),)),
    (
        "environment_mounts",
        (
            ("lease_status", "TEXT"),
            ("lease_owner", "TEXT"),
            ("lease_token", "TEXT"),
            ("lease_acquired_at", "TEXT"),
            ("lease_expires_at", "TEXT"),
            ("live_handle_ref", "TEXT"),
        ),
    ),
    (
        "session_mounts",
        (
            ("lease_status", "TEXT"),
            ("lease_owner", "TEXT"),
            ("lease_token", "TEXT"),
            ("lease_acquired_at", "TEXT"),
            ("lease_expires_at", "TEXT"),
            ("live_handle_ref", "TEXT"),
        ),
    ),
    (
        "agent_profile_overrides",
        (
            ("agent_class", "TEXT"),
            ("employment_mode", "TEXT"),
            ("activation_mode", "TEXT"),
            ("suspendable", "INTEGER"),
            ("reports_to", "TEXT"),
            ("mission", "TEXT"),
            ("current_goal_id", "TEXT"),
            ("industry_instance_id", "TEXT"),
            ("industry_role_id", "TEXT"),
            ("environment_constraints_json", "TEXT"),
            ("evidence_expectations_json", "TEXT"),
            ("capabilities_json", "TEXT"),
        ),
    ),
    (
        "agent_runtimes",
        (
            ("employment_mode", "TEXT NOT NULL DEFAULT 'career'"),
        ),
    ),
    (
        "goal_overrides",
        (
            ("plan_steps_json", "TEXT"),
            ("compiler_context_json", "TEXT NOT NULL DEFAULT '{}'"),
        ),
    ),
    (
        "industry_instances",
        (
            ("execution_core_identity_payload_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("lifecycle_status", "TEXT NOT NULL DEFAULT 'running'"),
            ("autonomy_status", "TEXT NOT NULL DEFAULT 'waiting-confirm'"),
            ("current_cycle_id", "TEXT"),
            ("next_cycle_due_at", "TEXT"),
            ("last_cycle_started_at", "TEXT"),
        ),
    ),
    (
        "media_analyses",
        (
            ("purpose", "TEXT NOT NULL DEFAULT 'reference-only'"),
            ("source_hash", "TEXT"),
            ("declared_media_type", "TEXT"),
            ("url", "TEXT"),
            ("filename", "TEXT"),
            ("mime_type", "TEXT"),
            ("size_bytes", "INTEGER"),
            ("asset_artifact_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("derived_artifact_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("transcript_artifact_id", "TEXT"),
            ("structured_summary_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("timeline_summary_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("entities_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("claims_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("recommended_actions_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("warnings_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("knowledge_document_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("evidence_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("strategy_writeback_status", "TEXT"),
            ("backlog_writeback_status", "TEXT"),
            ("error_message", "TEXT"),
            ("metadata_json", "TEXT NOT NULL DEFAULT '{}'"),
        ),
    ),
    (
        "tasks",
        (
            ("work_context_id", "TEXT"),
        ),
    ),
    (
        "agent_mailbox",
        (
            ("work_context_id", "TEXT"),
        ),
    ),
    (
        "agent_checkpoints",
        (
            ("work_context_id", "TEXT"),
        ),
    ),
    (
        "agent_thread_bindings",
        (
            ("work_context_id", "TEXT"),
        ),
    ),
    (
        "agent_reports",
        (
            ("lane_id", "TEXT"),
            ("work_context_id", "TEXT"),
            ("findings_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("uncertainties_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("recommendation", "TEXT"),
            ("needs_followup", "INTEGER NOT NULL DEFAULT 0"),
            ("followup_reason", "TEXT"),
        ),
    ),
    (
        "goals",
        (
            ("industry_instance_id", "TEXT"),
            ("lane_id", "TEXT"),
            ("cycle_id", "TEXT"),
            ("goal_class", "TEXT NOT NULL DEFAULT 'goal'"),
        ),
    ),
    (
        "tasks",
        (
            ("industry_instance_id", "TEXT"),
            ("assignment_id", "TEXT"),
            ("lane_id", "TEXT"),
            ("cycle_id", "TEXT"),
            ("report_back_mode", "TEXT NOT NULL DEFAULT 'summary'"),
        ),
    ),
    (
        "strategy_memories",
        (
            ("priority_order_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("thinking_axes_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("delegation_policy_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("direct_execution_policy_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("execution_constraints_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("evidence_requirements_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("active_goal_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("active_goal_titles_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("teammate_contracts_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("lane_weights_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("planning_policy_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("current_focuses_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("paused_lane_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("review_rules_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("metadata_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("scope_type", "TEXT NOT NULL DEFAULT 'industry'"),
            ("scope_id", "TEXT"),
            ("owner_agent_id", "TEXT"),
            ("owner_scope", "TEXT"),
            ("industry_instance_id", "TEXT"),
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("summary", "TEXT NOT NULL DEFAULT ''"),
            ("mission", "TEXT NOT NULL DEFAULT ''"),
            ("north_star", "TEXT NOT NULL DEFAULT ''"),
            ("source_ref", "TEXT"),
            ("status", "TEXT NOT NULL DEFAULT 'active'"),
            ("created_at", "TEXT"),
            ("updated_at", "TEXT"),
        ),
    ),
    (
        "knowledge_chunks",
        (
            ("role_bindings_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("tags_json", "TEXT NOT NULL DEFAULT '[]'"),
        ),
    ),
)


class SQLiteStateStore:
    """Small SQLite store abstraction for state repositories."""

    def __init__(self, path: Path | str):
        if isinstance(path, str):
            path = Path(path)
        self._path = path.expanduser()

    @property
    def path(self) -> Path:
        return self._path

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            existing_tables = _list_table_names(conn)
            if existing_tables:
                _ensure_additive_schema_columns(
                    conn,
                    existing_tables=existing_tables,
                )
            conn.executescript(_SCHEMA)
            _ensure_additive_schema_columns(conn)
            conn.execute(f"PRAGMA user_version = {STATE_SCHEMA_VERSION}")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _ensure_column(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name in columns:
        return
    conn.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}",
    )


def _list_table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'",
    ).fetchall()
    return {str(row["name"]) for row in rows if row["name"]}


def _ensure_additive_schema_columns(
    conn: sqlite3.Connection,
    *,
    existing_tables: set[str] | None = None,
) -> None:
    table_names = existing_tables if existing_tables is not None else _list_table_names(conn)
    for table_name, columns in _ADDITIVE_SCHEMA_COLUMNS:
        if table_name not in table_names:
            continue
        for column_name, column_sql in columns:
            _ensure_column(
                conn,
                table_name=table_name,
                column_name=column_name,
                column_sql=column_sql,
            )
