# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403
from ..kernel.runtime_coordination import build_durable_runtime_coordination
from ..evidence import serialize_evidence_record as canonical_serialize_evidence_record


def _workflow_first_non_empty(*values: object) -> str | None:
    for value in values:
        normalized = _string(value)
        if normalized is not None:
            return normalized
    return None


def _workflow_mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _workflow_goal_task_payloads(detail: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    entries = detail.get("tasks")
    if not isinstance(entries, list):
        return payloads
    for entry in list(entries):
        if not isinstance(entry, dict):
            continue
        task_payload = _workflow_mapping(entry.get("task"))
        if not task_payload:
            continue
        runtime_payload = _workflow_mapping(entry.get("runtime"))
        if runtime_payload:
            task_payload["runtime"] = runtime_payload
        frames = entry.get("frames")
        if isinstance(frames, list) and frames:
            task_payload["frames"] = [dict(item) for item in frames if isinstance(item, dict)]
        for key in ("decision_count", "evidence_count", "latest_evidence_id"):
            if key in entry:
                task_payload[key] = entry.get(key)
        payloads.append(task_payload)
    return payloads


def _workflow_serialize_evidence(record: object) -> dict[str, Any]:
    if isinstance(record, dict):
        return dict(record)
    return canonical_serialize_evidence_record(record)


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

    def _materialize_workflow_step_goal(
        self,
        *,
        run: WorkflowRunRecord,
        template: WorkflowTemplateRecord,
        preview: WorkflowTemplatePreview,
        step: WorkflowTemplateStepPreview,
        step_payload: dict[str, Any],
        status: str,
        reason: str,
        extra_compiler_context: dict[str, Any] | None = None,
    ) -> GoalRecord:
        goal = self._goal_service.create_goal(
            title=step.title,
            summary=step.summary,
            status=status,
            priority=3,
            owner_scope=preview.owner_scope,
            industry_instance_id=preview.industry_instance_id,
            goal_class="workflow-step-goal",
        )
        if self._goal_override_repository is not None:
            compiler_context = {
                "workflow_run_id": run.run_id,
                "workflow_template_id": template.template_id,
                "workflow_step_id": step.step_id,
                "workflow_execution_mode": step.execution_mode,
                "industry_instance_id": preview.industry_instance_id,
                "materialization_path": "workflow-leaf-compatibility",
                **dict(extra_compiler_context or {}),
            }
            self._goal_override_repository.upsert_override(
                GoalOverrideRecord(
                    goal_id=goal.id,
                    plan_steps=list(step_payload.get("plan_steps") or []),
                    compiler_context=compiler_context,
                    reason=reason,
                ),
            )
        return goal

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
            }
            for step in preview.steps
        ]
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
                goal = self._materialize_workflow_step_goal(
                    run=run,
                    template=template,
                    preview=preview,
                    step=step,
                    step_payload=step_payload,
                    status="active" if payload.activate else "draft",
                    reason=f"Workflow template launch: {template.template_id}",
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
        return self._build_run_detail_from_preview(
            run=persisted,
            template=template,
            preview=preview,
            host_snapshot=dict(host_snapshot or {}),
        )

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

        for goal_id in _unique_strings(
            *list(
                _workflow_goal_ids_by_step(
                    run,
                    goal_override_repository=self._goal_override_repository,
                ).values(),
            ),
        ):
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
        stored_preview = WorkflowTemplatePreview.model_validate(run.preview_payload or {})
        preview_request = self._build_run_preview_request(
            run=run,
            preview=stored_preview,
        )
        preview = self._refresh_run_preview(
            template=template,
            preview=stored_preview,
            request=preview_request,
        )
        blocking_codes = [item.code for item in preview.launch_blockers]
        can_resume = run.status in {"planned", "running"} and not blocking_codes
        if not can_resume:
            summary = (
                "Workflow run has active launch or governance blockers."
                if blocking_codes
                else "Workflow run cannot resume"
            )
            raise ValueError(summary)
        execute_flag = (
            execute
            if execute is not None
            else str(dict(run.metadata or {}).get("launch_mode") or "").strip() == "execute"
        )
        host_snapshot = self._resolve_host_snapshot_from_request(preview_request) or dict(
            dict(run.metadata or {}).get("host_snapshot") or {},
        )
        metadata = dict(run.metadata or {})
        step_seed_items = list(dict(run.metadata or {}).get("step_execution_seed") or [])
        step_seed_by_id = {
            str(item.get("step_id")): item
            for item in step_seed_items
            if isinstance(item, dict) and str(item.get("step_id") or "").strip()
        }
        goal_ids_by_step = _workflow_goal_ids_by_step(
            run,
            goal_override_repository=self._goal_override_repository,
        )
        for step in preview.steps:
            step_payload = dict(step.payload_preview or {})
            step_seed = step_seed_by_id.get(step.step_id)
            if step.kind == "goal":
                persisted_task_ids = (
                    [
                        str(item)
                        for item in list(step_seed.get("linked_task_ids") or [])
                        if str(item).strip()
                    ]
                    if isinstance(step_seed, dict)
                    else []
                )
                persisted_decision_ids = (
                    [
                        str(item)
                        for item in list(step_seed.get("linked_decision_ids") or [])
                        if str(item).strip()
                    ]
                    if isinstance(step_seed, dict)
                    else []
                )
                persisted_evidence_ids = (
                    [
                        str(item)
                        for item in list(step_seed.get("linked_evidence_ids") or [])
                        if str(item).strip()
                    ]
                    if isinstance(step_seed, dict)
                    else []
                )
                linked_goal_ids = (
                    []
                    if persisted_task_ids or persisted_decision_ids or persisted_evidence_ids
                    else list(goal_ids_by_step.get(step.step_id, []))
                )
                if not linked_goal_ids:
                    if (
                        not persisted_task_ids
                        and not persisted_decision_ids
                        and not persisted_evidence_ids
                    ):
                        goal = self._materialize_workflow_step_goal(
                            run=run,
                            template=template,
                            preview=preview,
                            step=step,
                            step_payload=step_payload,
                            status="active",
                            reason=f"Workflow run resume: {template.template_id}",
                            extra_compiler_context={"resume_actor": actor},
                        )
                        linked_goal_ids = [goal.id]
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
                linked_schedule_ids = [
                    _workflow_step_schedule_id(
                        run,
                        step_id=step.step_id,
                        payload_preview=step_payload,
                    )
                ]
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
        return self._build_run_detail_from_preview(
            run=persisted,
            template=template,
            preview=preview,
            host_snapshot=dict(host_snapshot or {}),
        )

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
        run = self._workflow_run_repository.get_run(run_id)
        if run is None:
            raise KeyError(f"Workflow run '{run_id}' not found")
        template = self._workflow_template_repository.get_template(run.template_id)
        if template is None:
            raise KeyError(f"Workflow template '{run.template_id}' not found")
        stored_preview = WorkflowTemplatePreview.model_validate(run.preview_payload or {})
        preview = stored_preview
        preview_step = next((item for item in preview.steps if item.step_id == step_id), None)
        if preview_step is None:
            raise KeyError(f"Workflow step '{step_id}' preview missing in run '{run_id}'")
        seed = _workflow_step_seed_by_id(run).get(step_id)
        persisted_task_ids, persisted_decision_ids, persisted_evidence_ids = (
            _workflow_step_persisted_runtime_ids(seed)
        )
        goal_ids_by_step = _workflow_goal_ids_by_step(
            run,
            goal_override_repository=self._goal_override_repository,
        )
        goal_ids_from_context = list(goal_ids_by_step.get(step_id, []))
        goal_detail_by_id: dict[str, dict[str, Any]] = {}
        (
            goal_payload_by_id,
            tasks,
            decisions,
            evidence,
        ) = self._collect_workflow_goal_runtime_payloads(
            goal_ids=goal_ids_from_context,
            task_goal_ids=goal_ids_from_context,
            persisted_task_ids=persisted_task_ids,
            persisted_decision_ids=persisted_decision_ids,
            persisted_evidence_ids=persisted_evidence_ids,
        )
        for goal_id in goal_ids_from_context:
            payload = goal_payload_by_id.get(goal_id)
            if payload is None:
                continue
            goal_detail_by_id[goal_id] = {"goal": payload}
        tasks = list({str(item.get("id")): item for item in tasks if item.get("id")}.values())
        linked_tasks = [
            item
            for item in tasks
            if str(item.get("goal_id") or "") in set(goal_ids_from_context)
            or str(item.get("id") or "") in set(persisted_task_ids)
        ]
        linked_task_ids = _unique_strings(
            [
                *persisted_task_ids,
                *(
                    str(item.get("id") or "")
                    for item in linked_tasks
                    if str(item.get("id") or "").strip()
                ),
            ],
        )
        decisions = list(
            {str(item.get("id")): item for item in decisions if item.get("id")}.values(),
        )
        linked_decisions = [
            item
            for item in decisions
            if str(item.get("task_id") or "") in set(linked_task_ids)
            or str(item.get("id") or "") in set(persisted_decision_ids)
        ]
        linked_decision_ids = _unique_strings(
            [
                *persisted_decision_ids,
                *(
                    str(item.get("id") or "")
                    for item in linked_decisions
                    if str(item.get("id") or "").strip()
                ),
            ],
        )
        evidence = list(
            {str(item.get("id")): item for item in evidence if item.get("id")}.values(),
        )
        linked_evidence = [
            item
            for item in evidence
            if str(item.get("task_id") or "") in set(linked_task_ids)
            or str(item.get("id") or "") in set(persisted_evidence_ids)
        ]
        linked_evidence_ids = _unique_strings(
            [
                *persisted_evidence_ids,
                *(
                    str(item.get("id") or "")
                    for item in linked_evidence
                    if str(item.get("id") or "").strip()
                ),
            ],
        )
        linked_schedule_ids = _workflow_step_schedule_ids(
            run,
            step_kind=preview_step.kind,
            step_id=step_id,
            payload_preview=dict(preview_step.payload_preview or {}),
        )
        linked_schedules: list[dict[str, Any]] = []
        if self._schedule_repository is not None:
            for schedule_id in linked_schedule_ids:
                schedule = self._schedule_repository.get_schedule(schedule_id)
                if schedule is not None:
                    linked_schedules.append(schedule.model_dump(mode="json"))
        linked_goal_ids_for_status = (
            []
            if persisted_task_ids or persisted_decision_ids or persisted_evidence_ids
            else goal_ids_from_context
        )
        linked_goals_for_status = [
            detail.get("goal") or {}
            for goal_id, detail in goal_detail_by_id.items()
            if goal_id in linked_goal_ids_for_status
        ]
        blocker = next(
            (
                item
                for item in preview.launch_blockers
                if step_id in item.step_ids
            ),
            None,
        )
        last_event_at = self._latest_timestamp(
            [
                *(str(item.get("updated_at") or "") for item in linked_goals_for_status),
                *(str(item.get("updated_at") or "") for item in linked_schedules),
                *(str(item.get("updated_at") or "") for item in linked_tasks),
                *(str(item.get("created_at") or "") for item in linked_decisions),
                *(str(item.get("created_at") or "") for item in linked_evidence),
            ],
        )
        step = WorkflowStepExecutionRecord(
            step_id=preview_step.step_id,
            title=preview_step.title,
            kind=preview_step.kind,
            execution_mode=preview_step.execution_mode,
            status=self._infer_step_status(
                run_status=run.status,
                linked_goals=linked_goals_for_status,
                linked_schedules=linked_schedules,
                linked_tasks=linked_tasks,
                blocker=blocker,
            ),
            owner_role_id=preview_step.owner_role_id,
            owner_role_candidates=list(preview_step.owner_role_candidates or []),
            owner_agent_id=preview_step.owner_agent_id,
            linked_task_ids=linked_task_ids,
            linked_decision_ids=linked_decision_ids,
            linked_evidence_ids=linked_evidence_ids,
            blocked_reason_code=blocker.code if blocker is not None else None,
            blocked_reason_message=blocker.message if blocker is not None else None,
            summary=preview_step.summary,
            last_event_at=last_event_at,
            routes={},
        )
        self._persist_run_step_runtime_links(
            run=run,
            step_execution=[step],
        )
        linked_goal_ids = (
            []
            if persisted_decision_ids or persisted_evidence_ids
            else goal_ids_from_context
        )
        return WorkflowStepExecutionDetail(
            step=step,
            linked_goals=[
                goal_detail_by_id[goal_id].get("goal") or {}
                for goal_id in linked_goal_ids
                if goal_id in goal_detail_by_id
            ],
            linked_schedules=list(linked_schedules),
            linked_tasks=list(linked_tasks),
            linked_decisions=list(linked_decisions),
            linked_evidence=list(linked_evidence),
            routes={},
        )
