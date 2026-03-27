# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403


class _WorkflowServiceRunMixin:
    def __init__(
        self,
        *,
        workflow_template_repository: SqliteWorkflowTemplateRepository,
        workflow_run_repository: SqliteWorkflowRunRepository,
        workflow_preset_repository: SqliteWorkflowPresetRepository | None = None,
        goal_service: GoalService,
        goal_override_repository: SqliteGoalOverrideRepository | None = None,
        schedule_repository: SqliteScheduleRepository | None = None,
        industry_instance_repository: SqliteIndustryInstanceRepository | None = None,
        strategy_memory_service: object | None = None,
        task_repository: SqliteTaskRepository | None = None,
        decision_request_repository: SqliteDecisionRequestRepository | None = None,
        agent_profile_override_repository: SqliteAgentProfileOverrideRepository | None = None,
        agent_profile_service: object | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        capability_service: object | None = None,
        environment_service: object | None = None,
        schedule_writer: object | None = None,
        cron_manager: object | None = None,
    ) -> None:
        self._workflow_template_repository = workflow_template_repository
        self._workflow_run_repository = workflow_run_repository
        self._workflow_preset_repository = workflow_preset_repository
        self._goal_service = goal_service
        self._goal_override_repository = goal_override_repository
        self._schedule_repository = schedule_repository
        self._industry_instance_repository = industry_instance_repository
        self._strategy_memory_service = strategy_memory_service
        self._task_repository = task_repository
        self._decision_request_repository = decision_request_repository
        self._agent_profile_override_repository = agent_profile_override_repository
        self._agent_profile_service = agent_profile_service
        self._evidence_ledger = evidence_ledger
        self._capability_service = capability_service
        self._environment_service = environment_service
        self._schedule_writer = schedule_writer
        self._cron_manager = cron_manager
        self._seed_builtin_templates()

    def set_schedule_runtime(
        self,
        *,
        schedule_writer: object | None = None,
        cron_manager: object | None = None,
    ) -> None:
        self._schedule_writer = schedule_writer
        self._cron_manager = cron_manager

    def list_templates(
        self,
        *,
        category: str | None = None,
        status: str | None = "active",
    ) -> list[WorkflowTemplateRecord]:
        return self._workflow_template_repository.list_templates(
            category=category,
            status=status,
        )

    def get_template(self, template_id: str) -> WorkflowTemplateRecord | None:
        return self._workflow_template_repository.get_template(template_id)

    def list_presets(
        self,
        template_id: str,
        *,
        industry_instance_id: str | None = None,
        owner_scope: str | None = None,
    ) -> list[WorkflowPresetRecord]:
        if self._workflow_preset_repository is None:
            return []
        return self._workflow_preset_repository.list_presets(
            template_id=template_id,
            industry_scope=_string(industry_instance_id),
            owner_scope=_string(owner_scope),
        )

    def create_preset(
        self,
        template_id: str,
        *,
        name: str,
        summary: str = "",
        owner_scope: str | None = None,
        industry_scope: str | None = None,
        created_by: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> WorkflowPresetRecord:
        if self._workflow_preset_repository is None:
            raise RuntimeError("Workflow preset repository is not available")
        template = self._workflow_template_repository.get_template(template_id)
        if template is None:
            raise KeyError(f"Workflow template '{template_id}' not found")
        preset = WorkflowPresetRecord(
            template_id=template_id,
            name=name,
            summary=summary,
            owner_scope=_string(owner_scope),
            industry_scope=_string(industry_scope),
            parameter_overrides=dict(parameters or {}),
            created_by=_string(created_by),
        )
        return self._workflow_preset_repository.upsert_preset(preset)

    def list_runs(
        self,
        *,
        template_id: str | None = None,
        status: str | None = None,
        industry_instance_id: str | None = None,
    ) -> list[WorkflowRunRecord]:
        return self._workflow_run_repository.list_runs(
            template_id=template_id,
            status=status,
            industry_instance_id=industry_instance_id,
        )

    def get_run(self, run_id: str) -> WorkflowRunRecord | None:
        return self._workflow_run_repository.get_run(run_id)

    def has_capability(self, capability_id: str) -> bool:
        return self._has_capability(capability_id)

    def preview_template(
        self,
        template_id: str,
        payload: WorkflowPreviewRequest,
    ) -> WorkflowTemplatePreview:
        template = self._workflow_template_repository.get_template(template_id)
        if template is None:
            raise KeyError(f"Workflow template '{template_id}' not found")
        return self._build_preview(template, payload)

    async def launch_template(
        self,
        template_id: str,
        payload: WorkflowLaunchRequest,
    ) -> WorkflowRunDetail:
        template = self._workflow_template_repository.get_template(template_id)
        if template is None:
            raise KeyError(f"Workflow template '{template_id}' not found")
        preview = self._build_preview(
            template,
            WorkflowPreviewRequest(
                owner_scope=payload.owner_scope,
                industry_instance_id=payload.industry_instance_id,
                owner_agent_id=payload.owner_agent_id,
                environment_id=payload.environment_id,
                session_mount_id=payload.session_mount_id,
                preset_id=payload.preset_id,
                parameters=dict(payload.parameters or {}),
            ),
        )
        if not preview.can_launch:
            raise ValueError(self._summarize_launch_blockers(preview.launch_blockers))
        step_execution_seed = [
            {
                "step_id": step.step_id,
                "title": step.title,
                "summary": step.summary,
                "kind": step.kind,
                "execution_mode": step.execution_mode,
                "owner_role_id": step.owner_role_id,
                "owner_role_candidates": list(step.owner_role_candidates or []),
                "owner_agent_id": step.owner_agent_id,
                "linked_goal_ids": [],
                "linked_schedule_ids": [],
            }
            for step in preview.steps
        ]
        step_seed_by_id = {
            str(item.get("step_id")): item
            for item in step_execution_seed
            if str(item.get("step_id") or "").strip()
        }
        run = WorkflowRunRecord(
            template_id=template.template_id,
            title=preview.title,
            summary=preview.summary,
            status="running" if payload.execute else "planned",
            owner_scope=preview.owner_scope,
            owner_agent_id=_string(payload.owner_agent_id),
            industry_instance_id=preview.industry_instance_id,
            parameter_payload=dict(payload.parameters or {}),
            preview_payload=preview.model_dump(mode="json"),
            metadata={
                "launch_mode": "execute" if payload.execute else "plan-only",
                "preset_id": _string(payload.preset_id),
                "step_execution_seed": step_execution_seed,
            },
        )
        run = self._workflow_run_repository.upsert_run(run)
        goal_ids: list[str] = []
        schedule_ids: list[str] = []

        for step in preview.steps:
            step_payload = dict(step.payload_preview or {})
            if step.kind == "goal":
                goal = self._goal_service.create_goal(
                    title=step.title,
                    summary=step.summary,
                    status="active" if payload.activate else "draft",
                    priority=3,
                    owner_scope=preview.owner_scope,
                )
                goal_ids.append(goal.id)
                step_seed = step_seed_by_id.get(step.step_id)
                if isinstance(step_seed, dict):
                    linked_goal_ids = list(step_seed.get("linked_goal_ids") or [])
                    linked_goal_ids.append(goal.id)
                    step_seed["linked_goal_ids"] = linked_goal_ids
                if self._goal_override_repository is not None:
                    self._goal_override_repository.upsert_override(
                        GoalOverrideRecord(
                            goal_id=goal.id,
                            plan_steps=list(step_payload.get("plan_steps") or []),
                            compiler_context={
                                "workflow_run_id": run.run_id,
                                "workflow_template_id": template.template_id,
                                "workflow_step_id": step.step_id,
                                "workflow_execution_mode": step.execution_mode,
                                "industry_instance_id": preview.industry_instance_id,
                            },
                            reason=f"Workflow template launch: {template.template_id}",
                        ),
                    )
                if payload.activate:
                    await self._goal_service.dispatch_goal(
                        goal.id,
                        context={
                            "channel": "workflow-template",
                            "workflow_run_id": run.run_id,
                            "workflow_template_id": template.template_id,
                            "workflow_step_id": step.step_id,
                            "execution_mode": step.execution_mode,
                        },
                        owner_agent_id=step.owner_agent_id,
                        execute=payload.execute,
                        execute_background=payload.execute,
                        activate=payload.activate,
                    )
            elif step.kind == "schedule":
                schedule_id = str(step_payload.get("id") or f"{run.run_id}:{step.step_id}")
                schedule_ids.append(schedule_id)
                step_seed = step_seed_by_id.get(step.step_id)
                if isinstance(step_seed, dict):
                    linked_schedule_ids = list(step_seed.get("linked_schedule_ids") or [])
                    linked_schedule_ids.append(schedule_id)
                    step_seed["linked_schedule_ids"] = linked_schedule_ids
                await self._persist_schedule_spec(
                    {
                        "id": schedule_id,
                        "name": step.title,
                        "enabled": True,
                        "schedule": {
                            "type": "cron",
                            "cron": str(step_payload.get("cron") or "0 9 * * *"),
                            "timezone": str(step_payload.get("timezone") or "UTC"),
                        },
                        "task_type": "agent",
                        "request": {
                            "input": str(step_payload.get("request_input") or step.summary),
                            "meta": {
                                "workflow_run_id": run.run_id,
                                "workflow_template_id": template.template_id,
                                "workflow_step_id": step.step_id,
                            },
                        },
                        "dispatch": {
                            "type": "channel",
                            "channel": str(step_payload.get("dispatch_channel") or "console"),
                            "target": {
                                "user_id": str(step_payload.get("dispatch_user_id") or "workflow"),
                                "session_id": str(step_payload.get("dispatch_session_id") or run.run_id),
                            },
                            "mode": str(step_payload.get("dispatch_mode") or "final"),
                            "meta": {
                                "summary": step.summary,
                                "owner_agent_id": step.owner_agent_id,
                                "workflow_run_id": run.run_id,
                                "workflow_template_id": template.template_id,
                            },
                        },
                        "runtime": {
                            "max_concurrency": 1,
                            "timeout_seconds": 120,
                            "misfire_grace_seconds": 60,
                        },
                        "meta": {
                            "workflow_run_id": run.run_id,
                            "workflow_template_id": template.template_id,
                            "workflow_step_id": step.step_id,
                        },
                    }
                )
                if self._schedule_repository is not None:
                    stored = self._schedule_repository.get_schedule(schedule_id)
                    if stored is None:
                        self._schedule_repository.upsert_schedule(
                            ScheduleRecord(
                                id=schedule_id,
                                title=step.title,
                                cron=str(step_payload.get("cron") or "0 9 * * *"),
                                timezone=str(step_payload.get("timezone") or "UTC"),
                                status="scheduled",
                                enabled=True,
                                target_channel=str(step_payload.get("dispatch_channel") or "console"),
                                source_ref=f"workflow-template:{template.template_id}",
                                spec_payload={
                                    "meta": {
                                        "workflow_run_id": run.run_id,
                                        "workflow_template_id": template.template_id,
                                    }
                                },
                            ),
                        )

        persisted = run.model_copy(
            update={
                "goal_ids": goal_ids,
                "schedule_ids": schedule_ids,
                "metadata": {
                    **dict(run.metadata or {}),
                    "step_execution_seed": step_execution_seed,
                },
                "updated_at": _utc_now(),
            },
        )
        self._workflow_run_repository.upsert_run(persisted)
        return self.get_run_detail(persisted.run_id)

    async def cancel_run(
        self,
        run_id: str,
        *,
        actor: str = "copaw-operator",
        reason: str | None = None,
    ) -> WorkflowRunDetail:
        run = self._workflow_run_repository.get_run(run_id)
        if run is None:
            raise KeyError(f"Workflow run '{run_id}' not found")
        if run.status == "cancelled":
            return self.get_run_detail(run_id)

        for goal_id in run.goal_ids:
            goal = self._goal_service.get_goal(goal_id)
            if goal is None:
                continue
            if goal.status in {"completed", "archived"}:
                continue
            self._goal_service.update_goal(goal_id, status="archived")

        for schedule_id in run.schedule_ids:
            await self._pause_schedule(schedule_id)

        cancelled = run.model_copy(
            update={
                "status": "cancelled",
                "metadata": {
                    **dict(run.metadata or {}),
                    "cancelled_by": actor,
                    "cancel_reason": _string(reason),
                    "cancelled_at": _utc_now().isoformat(),
                },
                "updated_at": _utc_now(),
            },
        )
        self._workflow_run_repository.upsert_run(cancelled)
        return self.get_run_detail(run_id)

    async def resume_run(
        self,
        run_id: str,
        *,
        actor: str = "copaw-operator",
        execute: bool | None = None,
    ) -> WorkflowRunDetail:
        run = self._workflow_run_repository.get_run(run_id)
        if run is None:
            raise KeyError(f"Workflow run '{run_id}' not found")
        template = self._workflow_template_repository.get_template(run.template_id)
        if template is None:
            raise KeyError(f"Workflow template '{run.template_id}' not found")
        detail = self.get_run_detail(run_id)
        if not detail.diagnosis.can_resume:
            raise ValueError(detail.diagnosis.summary or "Workflow run cannot resume")
        execute_flag = (
            execute
            if execute is not None
            else str(dict(run.metadata or {}).get("launch_mode") or "").strip() == "execute"
        )
        step_seed_items = list(dict(run.metadata or {}).get("step_execution_seed") or [])
        step_seed_by_id = {
            str(item.get("step_id")): item
            for item in step_seed_items
            if isinstance(item, dict) and str(item.get("step_id") or "").strip()
        }
        goal_ids = list(run.goal_ids or [])
        schedule_ids = list(run.schedule_ids or [])
        for step in detail.preview.steps:
            step_payload = dict(step.payload_preview or {})
            step_seed = step_seed_by_id.get(step.step_id)
            if step.kind == "goal":
                linked_goal_ids = (
                    list(step_seed.get("linked_goal_ids") or [])
                    if isinstance(step_seed, dict)
                    else []
                )
                if not linked_goal_ids:
                    goal = self._goal_service.create_goal(
                        title=step.title,
                        summary=step.summary,
                        status="active",
                        priority=3,
                        owner_scope=detail.preview.owner_scope,
                    )
                    goal_ids.append(goal.id)
                    linked_goal_ids = [goal.id]
                    if isinstance(step_seed, dict):
                        step_seed["linked_goal_ids"] = linked_goal_ids
                    if self._goal_override_repository is not None:
                        self._goal_override_repository.upsert_override(
                            GoalOverrideRecord(
                                goal_id=goal.id,
                                plan_steps=list(step_payload.get("plan_steps") or []),
                                compiler_context={
                                    "workflow_run_id": run.run_id,
                                    "workflow_template_id": template.template_id,
                                    "workflow_step_id": step.step_id,
                                    "workflow_execution_mode": step.execution_mode,
                                    "industry_instance_id": detail.preview.industry_instance_id,
                                    "resume_actor": actor,
                                },
                                reason=f"Workflow run resume: {template.template_id}",
                            ),
                        )
                for goal_id in linked_goal_ids:
                    goal = self._goal_service.get_goal(goal_id)
                    if goal is None or goal.status in {"completed", "archived"}:
                        continue
                    await self._goal_service.dispatch_goal(
                        goal_id,
                        context={
                            "channel": "workflow-template",
                            "workflow_run_id": run.run_id,
                            "workflow_template_id": template.template_id,
                            "workflow_step_id": step.step_id,
                            "execution_mode": step.execution_mode,
                            "resume_actor": actor,
                        },
                        owner_agent_id=step.owner_agent_id,
                        execute=bool(execute_flag),
                        execute_background=bool(execute_flag),
                        activate=True,
                    )
            elif step.kind == "schedule":
                linked_schedule_ids = (
                    list(step_seed.get("linked_schedule_ids") or [])
                    if isinstance(step_seed, dict)
                    else []
                )
                if not linked_schedule_ids:
                    schedule_id = str(step_payload.get("id") or f"{run.run_id}:{step.step_id}")
                    if schedule_id not in schedule_ids:
                        schedule_ids.append(schedule_id)
                    if isinstance(step_seed, dict):
                        step_seed["linked_schedule_ids"] = [schedule_id]
                    await self._persist_schedule_spec(
                        {
                            "id": schedule_id,
                            "name": step.title,
                            "enabled": True,
                            "schedule": {
                                "type": "cron",
                                "cron": str(step_payload.get("cron") or "0 9 * * *"),
                                "timezone": str(step_payload.get("timezone") or "UTC"),
                            },
                            "task_type": "agent",
                            "request": {
                                "input": str(step_payload.get("request_input") or step.summary),
                                "meta": {
                                    "workflow_run_id": run.run_id,
                                    "workflow_template_id": template.template_id,
                                    "workflow_step_id": step.step_id,
                                },
                            },
                            "dispatch": {
                                "type": "channel",
                                "channel": str(step_payload.get("dispatch_channel") or "console"),
                                "target": {
                                    "user_id": str(step_payload.get("dispatch_user_id") or "workflow"),
                                    "session_id": str(step_payload.get("dispatch_session_id") or run.run_id),
                                },
                                "mode": str(step_payload.get("dispatch_mode") or "final"),
                                "meta": {
                                    "summary": step.summary,
                                    "owner_agent_id": step.owner_agent_id,
                                    "workflow_run_id": run.run_id,
                                    "workflow_template_id": template.template_id,
                                    "resume_actor": actor,
                                },
                            },
                            "runtime": {
                                "max_concurrency": 1,
                                "timeout_seconds": 120,
                                "misfire_grace_seconds": 60,
                            },
                            "meta": {
                                "workflow_run_id": run.run_id,
                                "workflow_template_id": template.template_id,
                                "workflow_step_id": step.step_id,
                            },
                        }
                    )
                    if self._schedule_repository is not None:
                        stored = self._schedule_repository.get_schedule(schedule_id)
                        if stored is None:
                            self._schedule_repository.upsert_schedule(
                                ScheduleRecord(
                                    id=schedule_id,
                                    title=step.title,
                                    cron=str(step_payload.get("cron") or "0 9 * * *"),
                                    timezone=str(step_payload.get("timezone") or "UTC"),
                                    status="scheduled",
                                    enabled=True,
                                    target_channel=str(
                                        step_payload.get("dispatch_channel") or "console"
                                    ),
                                    source_ref=f"workflow-template:{template.template_id}",
                                    spec_payload={
                                        "meta": {
                                            "workflow_run_id": run.run_id,
                                            "workflow_template_id": template.template_id,
                                        }
                                    },
                                )
                            )
                else:
                    for schedule_id in linked_schedule_ids:
                        await self._resume_schedule(schedule_id)

        persisted = run.model_copy(
            update={
                "goal_ids": goal_ids,
                "schedule_ids": schedule_ids,
                "status": "running" if execute_flag else run.status,
                "metadata": {
                    **dict(run.metadata or {}),
                    "step_execution_seed": step_seed_items,
                    "last_resumed_by": actor,
                    "last_resumed_at": _utc_now().isoformat(),
                    "resume_count": int(dict(run.metadata or {}).get("resume_count") or 0) + 1,
                },
                "updated_at": _utc_now(),
            },
        )
        self._workflow_run_repository.upsert_run(persisted)
        return self.get_run_detail(run_id)

    def get_run_step_detail(
        self,
        run_id: str,
        step_id: str,
    ) -> WorkflowStepExecutionDetail:
        detail = self.get_run_detail(run_id)
        step = next(
            (item for item in detail.step_execution if item.step_id == step_id),
            None,
        )
        if step is None:
            raise KeyError(f"Workflow step '{step_id}' not found in run '{run_id}'")
        return WorkflowStepExecutionDetail(
            step=step,
            linked_goals=[
                item
                for item in detail.goals
                if str(item.get("id") or "") in set(step.linked_goal_ids)
            ],
            linked_schedules=[
                item
                for item in detail.schedules
                if str(item.get("id") or "") in set(step.linked_schedule_ids)
            ],
            linked_tasks=[
                item
                for item in detail.tasks
                if str(item.get("id") or "") in set(step.linked_task_ids)
            ],
            linked_decisions=[
                item
                for item in detail.decisions
                if str(item.get("id") or "") in set(step.linked_decision_ids)
            ],
            linked_evidence=[
                item
                for item in detail.evidence
                if str(item.get("id") or "") in set(step.linked_evidence_ids)
            ],
            routes={
                "run": f"/api/workflow-runs/{run_id}",
                "step": f"/api/workflow-runs/{run_id}/steps/{step_id}",
            },
        )
