# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403
from ..kernel.runtime_coordination import build_durable_runtime_coordination


def _workflow_first_non_empty(*values: object) -> str | None:
    for value in values:
        normalized = _string(value)
        if normalized is not None:
            return normalized
    return None


def _workflow_mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _resolve_canonical_host_identity(
    host_payload: dict[str, Any] | None,
    *,
    metadata: dict[str, Any] | None = None,
    fallback_environment_ref: str | None = None,
    fallback_environment_id: str | None = None,
    fallback_session_mount_id: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    host_payload = _workflow_mapping(host_payload)
    metadata = _workflow_mapping(metadata)
    scheduler_inputs = _workflow_mapping(host_payload.get("scheduler_inputs"))
    host_twin_summary = _workflow_mapping(host_payload.get("host_twin_summary"))
    coordination = _workflow_mapping(host_payload.get("coordination"))
    canonical_environment_ref = _workflow_first_non_empty(
        scheduler_inputs.get("environment_ref"),
        scheduler_inputs.get("environment_id"),
        host_twin_summary.get("selected_seat_ref"),
        coordination.get("selected_seat_ref"),
        host_payload.get("environment_ref"),
        host_payload.get("environment_id"),
        metadata.get("environment_ref"),
        metadata.get("environment_id"),
        fallback_environment_ref,
        fallback_environment_id,
    )
    canonical_environment_id = _workflow_first_non_empty(
        scheduler_inputs.get("environment_id"),
        scheduler_inputs.get("environment_ref"),
        host_twin_summary.get("selected_seat_ref"),
        coordination.get("selected_seat_ref"),
        host_payload.get("environment_id"),
        host_payload.get("environment_ref"),
        metadata.get("environment_id"),
        metadata.get("environment_ref"),
        fallback_environment_id,
        fallback_environment_ref,
        canonical_environment_ref,
    )
    canonical_session_mount_id = _workflow_first_non_empty(
        scheduler_inputs.get("session_mount_id"),
        host_twin_summary.get("selected_session_mount_id"),
        coordination.get("selected_session_mount_id"),
        host_payload.get("session_mount_id"),
        metadata.get("session_mount_id"),
        fallback_session_mount_id,
    )
    return (
        canonical_environment_ref,
        canonical_environment_id,
        canonical_session_mount_id,
    )


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
        preview_request = WorkflowPreviewRequest(
            owner_scope=payload.owner_scope,
            industry_instance_id=payload.industry_instance_id,
            owner_agent_id=payload.owner_agent_id,
            environment_id=payload.environment_id,
            session_mount_id=payload.session_mount_id,
            preset_id=payload.preset_id,
            parameters=dict(payload.parameters or {}),
        )
        preview = self._build_preview(template, preview_request)
        host_snapshot = self._resolve_host_snapshot_from_request(preview_request)
        (
            resolved_environment_ref,
            resolved_environment_id,
            resolved_session_mount_id,
        ) = self._resolve_host_identity_from_snapshot(
            host_snapshot=host_snapshot,
            fallback_environment_id=_string(payload.environment_id),
            fallback_session_mount_id=_string(payload.session_mount_id),
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
                "environment_ref": resolved_environment_ref,
                "environment_id": resolved_environment_id,
                "session_mount_id": resolved_session_mount_id,
                "host_snapshot": dict(host_snapshot or {}),
                "step_execution_seed": step_execution_seed,
                **build_durable_runtime_coordination(
                    entrypoint="workflow-run",
                    coordinator_id=None,
                ),
            },
        )
        run = self._workflow_run_repository.upsert_run(run)
        run = run.model_copy(
            update={
                "metadata": {
                    **dict(run.metadata or {}),
                    **build_durable_runtime_coordination(
                        entrypoint="workflow-run",
                        coordinator_id=run.run_id,
                    ),
                }
            }
        )
        self._workflow_run_repository.upsert_run(run)
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
                    dispatch_context = {
                        "channel": "workflow-template",
                        "workflow_run_id": run.run_id,
                        "workflow_template_id": template.template_id,
                        "workflow_step_id": step.step_id,
                        "execution_mode": step.execution_mode,
                    }
                    if payload.execute:
                        await self._goal_service.dispatch_goal_background(
                            goal.id,
                            context=dispatch_context,
                            owner_agent_id=step.owner_agent_id,
                            activate=payload.activate,
                        )
                    else:
                        await self._goal_service.compile_goal_dispatch(
                            goal.id,
                            context=dispatch_context,
                            owner_agent_id=step.owner_agent_id,
                            activate=payload.activate,
                        )
            elif step.kind == "schedule":
                schedule_id = _workflow_step_schedule_id(
                    run,
                    step_id=step.step_id,
                    payload_preview=step_payload,
                )
                schedule_meta = self._build_schedule_host_meta(
                    run=run,
                    template=template,
                    preview=preview,
                    step=step,
                    host_snapshot=host_snapshot,
                )
                schedule_spec = self._build_schedule_spec(
                    run=run,
                    template=template,
                    step=step,
                    step_payload=step_payload,
                    schedule_id=schedule_id,
                    schedule_meta=schedule_meta,
                )
                await self._persist_schedule_spec(schedule_spec)
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
                                spec_payload=schedule_spec,
                            ),
                        )

        persisted = run.model_copy(
            update={
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

        for goal_id in _workflow_linked_resource_ids(run, key="linked_goal_ids"):
            goal = self._goal_service.get_goal(goal_id)
            if goal is None:
                continue
            if goal.status in {"completed", "archived"}:
                continue
            self._goal_service.update_goal(goal_id, status="archived")

        preview = WorkflowTemplatePreview.model_validate(run.preview_payload or {})
        for schedule_id in _workflow_schedule_ids_for_preview(run, preview):
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
        host_snapshot = dict(detail.diagnosis.host_snapshot or {})
        metadata = dict(run.metadata or {})
        step_seed_items = list(dict(run.metadata or {}).get("step_execution_seed") or [])
        step_seed_by_id = {
            str(item.get("step_id")): item
            for item in step_seed_items
            if isinstance(item, dict) and str(item.get("step_id") or "").strip()
        }
        for step in detail.preview.steps:
            step_payload = dict(step.payload_preview or {})
            step_seed = step_seed_by_id.get(step.step_id)
            if step.kind == "goal":
                linked_goal_ids = (
                    list(step_seed.get("linked_goal_ids") or [])
                    if isinstance(step_seed, dict)
                    else []
                )
                persisted_task_ids = (
                    [
                        str(item)
                        for item in list(step_seed.get("linked_task_ids") or [])
                        if str(item).strip()
                    ]
                    if isinstance(step_seed, dict)
                    else []
                )
                if not linked_goal_ids:
                    if not persisted_task_ids:
                        goal = self._goal_service.create_goal(
                            title=step.title,
                            summary=step.summary,
                            status="active",
                            priority=3,
                            owner_scope=detail.preview.owner_scope,
                        )
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
                    dispatch_context = {
                        "channel": "workflow-template",
                        "workflow_run_id": run.run_id,
                        "workflow_template_id": template.template_id,
                        "workflow_step_id": step.step_id,
                        "execution_mode": step.execution_mode,
                        "resume_actor": actor,
                    }
                    if bool(execute_flag):
                        await self._goal_service.dispatch_goal_background(
                            goal_id,
                            context=dispatch_context,
                            owner_agent_id=step.owner_agent_id,
                            activate=True,
                        )
                    else:
                        await self._goal_service.compile_goal_dispatch(
                            goal_id,
                            context=dispatch_context,
                            owner_agent_id=step.owner_agent_id,
                            activate=True,
                        )
            elif step.kind == "schedule":
                linked_schedule_ids = _unique_strings(
                    (
                        [
                            str(item)
                            for item in list(step_seed.get("linked_schedule_ids") or [])
                            if str(item).strip()
                        ]
                        if isinstance(step_seed, dict)
                        else []
                    ),
                    [
                        _workflow_step_schedule_id(
                            run,
                            step_id=step.step_id,
                            payload_preview=step_payload,
                        )
                    ],
                )
                if linked_schedule_ids:
                    missing_schedule_ids = [
                        schedule_id
                        for schedule_id in linked_schedule_ids
                        if self._schedule_repository is None
                        or self._schedule_repository.get_schedule(schedule_id) is None
                    ]
                else:
                    missing_schedule_ids = []
                if missing_schedule_ids:
                    schedule_id = missing_schedule_ids[0]
                    schedule_meta = self._build_schedule_host_meta(
                        run=run,
                        template=template,
                        preview=detail.preview,
                        step=step,
                        host_snapshot=host_snapshot,
                    )
                    schedule_spec = self._build_schedule_spec(
                        run=run,
                        template=template,
                        step=step,
                        step_payload=step_payload,
                        schedule_id=schedule_id,
                        schedule_meta=schedule_meta,
                        dispatch_meta_extra={"resume_actor": actor},
                    )
                    await self._persist_schedule_spec(schedule_spec)
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
                                    spec_payload=dict(schedule_spec),
                                )
                            )
                else:
                    for schedule_id in linked_schedule_ids:
                        schedule_meta = self._build_schedule_host_meta(
                            run=run,
                            template=template,
                            preview=detail.preview,
                            step=step,
                            host_snapshot=host_snapshot,
                        )
                        schedule_spec = self._build_schedule_spec(
                            run=run,
                            template=template,
                            step=step,
                            step_payload=step_payload,
                            schedule_id=schedule_id,
                            schedule_meta=schedule_meta,
                            dispatch_meta_extra={"resume_actor": actor},
                        )
                        await self._persist_schedule_spec(schedule_spec)
                        if self._schedule_repository is not None:
                            stored = self._schedule_repository.get_schedule(schedule_id)
                            if stored is not None:
                                self._schedule_repository.upsert_schedule(
                                    stored.model_copy(
                                        update={
                                            "title": step.title,
                                            "cron": str(
                                                step_payload.get("cron") or stored.cron
                                            ),
                                            "timezone": str(
                                                step_payload.get("timezone") or stored.timezone
                                            ),
                                            "status": "scheduled",
                                            "enabled": True,
                                            "target_channel": str(
                                                step_payload.get("dispatch_channel")
                                                or stored.target_channel
                                            ),
                                            "source_ref": (
                                                stored.source_ref
                                                or f"workflow-template:{template.template_id}"
                                            ),
                                            "spec_payload": {
                                                **dict(stored.spec_payload or {}),
                                                **dict(schedule_spec),
                                                "meta": dict(schedule_meta),
                                            },
                                            "updated_at": _utc_now(),
                                        }
                                    )
                                )
                        await self._resume_schedule(schedule_id)

        (
            resolved_environment_ref,
            resolved_environment_id,
            resolved_session_mount_id,
        ) = self._resolve_host_identity_from_snapshot(
            host_snapshot=host_snapshot,
            metadata=metadata,
        )
        persisted = run.model_copy(
            update={
                "status": "running" if execute_flag else run.status,
                "metadata": {
                    **metadata,
                    "step_execution_seed": step_seed_items,
                    "last_resumed_by": actor,
                    "last_resumed_at": _utc_now().isoformat(),
                    "resume_count": int(dict(run.metadata or {}).get("resume_count") or 0) + 1,
                    "host_snapshot": host_snapshot,
                    "environment_ref": resolved_environment_ref,
                    "environment_id": resolved_environment_id,
                    "session_mount_id": resolved_session_mount_id,
                    **build_durable_runtime_coordination(
                        entrypoint="workflow-run",
                        coordinator_id=run.run_id,
                    ),
                },
                "updated_at": _utc_now(),
            },
        )
        self._workflow_run_repository.upsert_run(persisted)
        return self.get_run_detail(run_id)

    def _resolve_host_identity_from_snapshot(
        self,
        *,
        host_snapshot: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        fallback_environment_id: str | None = None,
        fallback_session_mount_id: str | None = None,
    ) -> tuple[str | None, str | None, str | None]:
        return _resolve_canonical_host_identity(
            host_snapshot,
            metadata=dict(metadata or {}),
            fallback_environment_ref=fallback_environment_id,
            fallback_environment_id=fallback_environment_id,
            fallback_session_mount_id=fallback_session_mount_id,
        )

    def _build_schedule_spec(
        self,
        *,
        run: WorkflowRunRecord,
        template: WorkflowTemplateRecord,
        step: WorkflowTemplateStepPreview,
        step_payload: dict[str, Any],
        schedule_id: str,
        schedule_meta: dict[str, Any],
        dispatch_meta_extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dispatch_meta = {
            "summary": step.summary,
            "owner_agent_id": step.owner_agent_id,
            "workflow_run_id": run.run_id,
            "workflow_template_id": template.template_id,
            **dict(dispatch_meta_extra or {}),
            **dict(schedule_meta),
        }
        environment_ref = _string(schedule_meta.get("environment_ref")) or _string(
            schedule_meta.get("environment_id"),
        )
        control_thread_id = run.run_id
        return {
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
                "control_thread_id": control_thread_id,
                "entry_source": "workflow-run",
                "main_brain_runtime": {
                    "environment": {
                        "ref": environment_ref,
                        "session_id": control_thread_id,
                        "continuity_source": "workflow-run",
                        "resume_ready": True,
                    },
                },
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
                "meta": dispatch_meta,
            },
            "runtime": {
                "max_concurrency": 1,
                "timeout_seconds": 120,
                "misfire_grace_seconds": 60,
            },
            "meta": dict(schedule_meta),
        }

    def _build_schedule_host_meta(
        self,
        *,
        run: WorkflowRunRecord,
        template: WorkflowTemplateRecord,
        preview: WorkflowTemplatePreview,
        step: WorkflowTemplateStepPreview,
        host_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        metadata = dict(run.metadata or {})
        environment_ref, environment_id, session_mount_id = (
            self._resolve_host_identity_from_snapshot(
                host_snapshot=host_snapshot,
                metadata=metadata,
            )
        )
        schedule_meta = {
            "workflow_run_id": run.run_id,
            "workflow_template_id": template.template_id,
            "workflow_step_id": step.step_id,
            **build_durable_runtime_coordination(
                entrypoint="workflow-run",
                coordinator_id=run.run_id,
            ),
        }
        if environment_ref is not None:
            schedule_meta["environment_ref"] = environment_ref
        if environment_id is not None:
            schedule_meta["environment_id"] = environment_id
        if session_mount_id is not None:
            schedule_meta["session_mount_id"] = session_mount_id
        host_requirement = self._host_requirement_for_step(preview, step.step_id)
        if host_requirement:
            schedule_meta["host_requirement"] = host_requirement
        if host_snapshot:
            schedule_meta["host_snapshot"] = dict(host_snapshot)
        return schedule_meta

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
            routes={},
        )
