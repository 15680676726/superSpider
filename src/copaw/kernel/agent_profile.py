# -*- coding: utf-8 -*-
"""Agent profile model - defines how each agent is visible in the system.

Based on AGENT_VISIBLE_MODEL.md §3 and §10 (minimum viable version).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from ..industry.identity import EXECUTION_CORE_AGENT_ID, EXECUTION_CORE_NAME


AgentStatus = Literal["idle", "running", "waiting", "blocked", "needs-confirm", "degraded"]


class AgentProfile(BaseModel):
    """An agent's visible identity and current state."""

    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Display name")
    role_name: str = Field(default="", description="Role classification")
    role_summary: str = Field(default="", description="One-line role description")
    agent_class: Literal["system", "business"] = Field(default="system")
    employment_mode: Literal["career", "temporary"] = Field(default="career")
    activation_mode: Literal["persistent", "on-demand"] = Field(
        default="persistent",
    )
    suspendable: bool = Field(default=False)
    reports_to: str | None = Field(default=None)
    mission: str = Field(default="", description="Role mission")
    actor_key: str | None = Field(default=None)
    actor_fingerprint: str | None = Field(default=None)
    desired_state: str | None = Field(default=None)
    runtime_status: str | None = Field(default=None)
    resident: bool = Field(default=False)
    status: AgentStatus = Field(default="idle")
    risk_level: str = Field(default="auto")
    current_focus_kind: str | None = Field(default=None)
    current_focus_id: str | None = Field(default=None)
    current_focus: str = Field(default="", description="Current live execution focus")
    current_task_id: str | None = Field(default=None)
    current_mailbox_id: str | None = Field(default=None)
    queue_depth: int = Field(default=0, ge=0)
    industry_instance_id: str | None = Field(default=None)
    industry_role_id: str | None = Field(default=None)
    environment_summary: str = Field(default="", description="Current environment state")
    current_environment_id: str | None = Field(default=None)
    last_checkpoint_id: str | None = Field(default=None)
    thread_id: str | None = Field(default=None)
    today_output_summary: str = Field(default="", description="Today's cumulative output")
    latest_evidence_summary: str = Field(default="", description="Most recent evidence")
    environment_constraints: list[str] = Field(default_factory=list)
    evidence_expectations: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list, description="Accessible capability IDs")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

class AgentDailyReport(BaseModel):
    """Agent daily report based on AGENT_VISIBLE_MODEL.md §4."""

    agent_id: str
    date: str
    goal: str = ""
    completed: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_plan: list[str] = Field(default_factory=list)


# ── Default agent profiles (the system's built-in agents) ──────────

DEFAULT_AGENTS: list[AgentProfile] = [
    AgentProfile(
        agent_id=EXECUTION_CORE_AGENT_ID,
        name=EXECUTION_CORE_NAME,
        role_name="团队执行中枢",
        role_summary="系统唯一执行大脑，负责承接团队目标、统一调度执行与分派协作。",
        agent_class="business",
        status="running",
        current_focus_kind="goal",
        current_focus="承接业务团队目标并统一调度执行，不再生成团队级主管副本。",
        environment_summary="workspace + browser + session",
    ),
    AgentProfile(
        agent_id="copaw-scheduler",
        name="Spider Mesh 调度中枢",
        role_name="定时调度",
        role_summary="管理定时任务的生命周期和触发",
        status="idle",
        current_focus_kind="goal",
        current_focus="让 schedule 只保留 ingress/adapter 角色，停止依赖 runner 执行 turn",
    ),
    AgentProfile(
        agent_id="copaw-governance",
        name="Spider Mesh 治理中枢",
        role_name="风险治理",
        role_summary="审查高风险操作，管理 confirm 审批流",
        status="idle",
        current_focus_kind="goal",
        current_focus="补齐 Decision 前端动作，并继续收口 patch/expiry 治理策略",
    ),
]
