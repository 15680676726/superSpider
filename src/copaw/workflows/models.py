# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkflowTemplateInstallTemplateRef(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    template_id: str
    name: str
    installed: bool = False
    default_client_key: str | None = None
    capability_tags: list[str] = Field(default_factory=list)
    routes: dict[str, str] = Field(default_factory=dict)


class WorkflowTemplateStepPreview(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    step_id: str
    title: str
    summary: str = ""
    kind: Literal["goal", "schedule"] = "goal"
    execution_mode: Literal["control", "leaf"] = "leaf"
    owner_role_id: str | None = None
    owner_role_candidates: list[str] = Field(default_factory=list)
    owner_agent_id: str | None = None
    required_capability_ids: list[str] = Field(default_factory=list)
    missing_capability_ids: list[str] = Field(default_factory=list)
    assignment_gap_capability_ids: list[str] = Field(default_factory=list)
    budget_cost: int = 0
    payload_preview: dict[str, Any] = Field(default_factory=dict)


class WorkflowTemplateDependencyStatus(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    capability_id: str
    installed: bool = False
    enabled: bool | None = None
    available: bool = False
    required_by_steps: list[str] = Field(default_factory=list)
    target_agent_ids: list[str] = Field(default_factory=list)
    install_templates: list[WorkflowTemplateInstallTemplateRef] = Field(default_factory=list)


class WorkflowTemplateAgentBudgetStatus(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    agent_id: str
    role_id: str | None = None
    agent_class: str | None = None
    agent_present: bool = True
    baseline_capability_ids: list[str] = Field(default_factory=list)
    effective_capability_ids: list[str] = Field(default_factory=list)
    required_capability_ids: list[str] = Field(default_factory=list)
    planned_capability_ids: list[str] = Field(default_factory=list)
    current_extra_count: int = 0
    planned_extra_count: int = 0
    extra_limit: int | None = None
    over_limit_by: int = 0
    within_limit: bool = True
    blocking: bool = False


class WorkflowTemplateLaunchBlocker(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str
    message: str
    agent_id: str | None = None
    capability_ids: list[str] = Field(default_factory=list)
    step_ids: list[str] = Field(default_factory=list)


class WorkflowTemplatePreview(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    template_id: str
    title: str
    summary: str = ""
    owner_scope: str | None = None
    industry_instance_id: str | None = None
    strategy_memory: dict[str, Any] | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    steps: list[WorkflowTemplateStepPreview] = Field(default_factory=list)
    dependencies: list[WorkflowTemplateDependencyStatus] = Field(default_factory=list)
    missing_capability_ids: list[str] = Field(default_factory=list)
    assignment_gap_capability_ids: list[str] = Field(default_factory=list)
    capability_budget_by_agent: dict[str, int] = Field(default_factory=dict)
    budget_status_by_agent: list[WorkflowTemplateAgentBudgetStatus] = Field(default_factory=list)
    host_requirements: list[dict[str, Any]] = Field(default_factory=list)
    launch_blockers: list[WorkflowTemplateLaunchBlocker] = Field(default_factory=list)
    can_launch: bool = True
    materialized_objects: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class WorkflowLaunchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    owner_scope: str | None = None
    industry_instance_id: str | None = None
    owner_agent_id: str | None = None
    environment_id: str | None = None
    session_mount_id: str | None = None
    preset_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    activate: bool = True
    execute: bool = False


class WorkflowPreviewRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    owner_scope: str | None = None
    industry_instance_id: str | None = None
    owner_agent_id: str | None = None
    environment_id: str | None = None
    session_mount_id: str | None = None
    preset_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class WorkflowPresetCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    summary: str = ""
    owner_scope: str | None = None
    industry_scope: str | None = None
    created_by: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunCancelRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    actor: str = "copaw-operator"
    reason: str | None = None


class WorkflowRunResumeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    actor: str = "copaw-operator"
    execute: bool | None = None


class WorkflowRunDiagnosis(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: str = "planned"
    summary: str = ""
    can_resume: bool = False
    blocking_codes: list[str] = Field(default_factory=list)
    missing_capability_ids: list[str] = Field(default_factory=list)
    assignment_gap_capability_ids: list[str] = Field(default_factory=list)
    open_decision_count: int = 0
    task_count: int = 0
    completed_task_count: int = 0
    evidence_count: int = 0
    goal_statuses: dict[str, int] = Field(default_factory=dict)
    schedule_statuses: dict[str, int] = Field(default_factory=dict)
    host_snapshot: dict[str, Any] = Field(default_factory=dict)
    routes: dict[str, str] = Field(default_factory=dict)


class WorkflowStepExecutionRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    step_id: str
    title: str
    kind: Literal["goal", "schedule"] = "goal"
    execution_mode: Literal["control", "leaf"] = "leaf"
    status: str = "planned"
    owner_role_id: str | None = None
    owner_role_candidates: list[str] = Field(default_factory=list)
    owner_agent_id: str | None = None
    linked_goal_ids: list[str] = Field(default_factory=list, exclude=True)
    linked_schedule_ids: list[str] = Field(default_factory=list, exclude=True)
    linked_task_ids: list[str] = Field(default_factory=list)
    linked_decision_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    blocked_reason_code: str | None = None
    blocked_reason_message: str | None = None
    summary: str = ""
    last_event_at: str | None = None
    routes: dict[str, str] = Field(default_factory=dict)


class WorkflowRunDetail(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    run: dict[str, Any]
    template: dict[str, Any]
    preview: WorkflowTemplatePreview
    diagnosis: WorkflowRunDiagnosis
    step_execution: list[WorkflowStepExecutionRecord] = Field(default_factory=list)
    goals: list[dict[str, Any]] = Field(default_factory=list)
    schedules: list[dict[str, Any]] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    routes: dict[str, Any] = Field(default_factory=dict)


class WorkflowStepExecutionDetail(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    step: WorkflowStepExecutionRecord
    linked_goals: list[dict[str, Any]] = Field(default_factory=list)
    linked_schedules: list[dict[str, Any]] = Field(default_factory=list)
    linked_tasks: list[dict[str, Any]] = Field(default_factory=list)
    linked_decisions: list[dict[str, Any]] = Field(default_factory=list)
    linked_evidence: list[dict[str, Any]] = Field(default_factory=list)
    routes: dict[str, Any] = Field(default_factory=dict)
