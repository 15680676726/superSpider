# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403


class _WorkflowServicePreviewMixin:
    _HOST_TWIN_SURFACE_BY_CAPABILITY = {
        "mcp:desktop_windows": "desktop",
        "tool:browser_use": "browser",
    }
    _HOST_TWIN_VALID_CONTINUITY_STATUSES = {
        "attached",
        "restorable",
        "same-host-other-process",
    }
    _HOST_TWIN_HANDOFF_ONLY_STATES = {
        "requested",
        "active",
        "manual-only-terminal",
    }
    _HOST_TWIN_BLOCKING_RESPONSES = {"recover", "handoff", "retry"}

    def get_run_detail(self, run_id: str) -> WorkflowRunDetail:
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
        host_snapshot = self._resolve_host_snapshot_from_request(preview_request) or dict(
            dict(run.metadata or {}).get("host_snapshot") or {},
        )
        goals: list[dict[str, Any]] = []
        tasks: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []
        goal_detail_by_id: dict[str, dict[str, Any]] = {}
        for goal_id in run.goal_ids:
            detail = self._goal_service.get_goal_detail(goal_id)
            if detail is None:
                continue
            goal_detail_by_id[goal_id] = detail
            goals.append(detail.get("goal") or {})
            tasks.extend(list(detail.get("tasks") or []))
            decisions.extend(list(detail.get("decisions") or []))
            evidence.extend(list(detail.get("evidence") or []))
        schedules: list[dict[str, Any]] = []
        schedule_by_id: dict[str, dict[str, Any]] = {}
        if self._schedule_repository is not None:
            for schedule_id in run.schedule_ids:
                schedule = self._schedule_repository.get_schedule(schedule_id)
                if schedule is not None:
                    payload = schedule.model_dump(mode="json")
                    schedules.append(payload)
                    schedule_by_id[schedule_id] = payload
        tasks = list({str(item.get("id")): item for item in tasks if item.get("id")}.values())
        decisions = list(
            {str(item.get("id")): item for item in decisions if item.get("id")}.values(),
        )
        evidence = list(
            {str(item.get("id")): item for item in evidence if item.get("id")}.values(),
        )
        step_execution = self._build_step_execution_records(
            run=run,
            preview=preview,
            goal_detail_by_id=goal_detail_by_id,
            schedule_by_id=schedule_by_id,
            tasks=tasks,
            decisions=decisions,
            evidence=evidence,
        )
        diagnosis = self._build_run_diagnosis(
            run=run,
            preview=preview,
            goals=goals,
            schedules=schedules,
            tasks=tasks,
            decisions=decisions,
            evidence=evidence,
            host_snapshot=host_snapshot,
        )
        return WorkflowRunDetail(
            run=run.model_dump(mode="json"),
            template=template.model_dump(mode="json"),
            preview=preview,
            diagnosis=diagnosis,
            step_execution=step_execution,
            goals=goals,
            schedules=schedules,
            tasks=tasks,
            decisions=decisions,
            evidence=evidence,
            routes={
                "template": f"/api/workflow-templates/{template.template_id}",
                "run": f"/api/workflow-runs/{run.run_id}",
                "cancel": f"/api/workflow-runs/{run.run_id}/cancel",
                "goals": [
                    f"/api/runtime-center/goals/{goal_id}"
                    for goal_id in run.goal_ids
                ],
                "schedules": [
                    f"/api/runtime-center/schedules/{schedule_id}"
                    for schedule_id in run.schedule_ids
                ],
            },
        )

    def _build_step_execution_records(
        self,
        *,
        run: WorkflowRunRecord,
        preview: WorkflowTemplatePreview,
        goal_detail_by_id: dict[str, dict[str, Any]],
        schedule_by_id: dict[str, dict[str, Any]],
        tasks: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> list[WorkflowStepExecutionRecord]:
        step_seed_items = list(dict(run.metadata or {}).get("step_execution_seed") or [])
        step_seed_by_id = {
            str(item.get("step_id")): item
            for item in step_seed_items
            if isinstance(item, dict) and str(item.get("step_id") or "").strip()
        }
        step_records: list[WorkflowStepExecutionRecord] = []
        for step in preview.steps:
            seed = step_seed_by_id.get(step.step_id) or {}
            linked_goal_ids = [
                str(item)
                for item in list(seed.get("linked_goal_ids") or [])
                if str(item).strip()
            ]
            linked_schedule_ids = [
                str(item)
                for item in list(seed.get("linked_schedule_ids") or [])
                if str(item).strip()
            ]
            linked_tasks = [
                item
                for item in tasks
                if str(item.get("goal_id") or "") in linked_goal_ids
            ]
            linked_decisions = [
                item
                for item in decisions
                if str(item.get("task_id") or "") in {
                    str(task.get("id") or "") for task in linked_tasks
                }
            ]
            linked_evidence = [
                item
                for item in evidence
                if str(item.get("task_id") or "") in {
                    str(task.get("id") or "") for task in linked_tasks
                }
            ]
            linked_goals = [
                detail.get("goal") or {}
                for goal_id, detail in goal_detail_by_id.items()
                if goal_id in linked_goal_ids
            ]
            linked_schedules = [
                schedule_by_id[schedule_id]
                for schedule_id in linked_schedule_ids
                if schedule_id in schedule_by_id
            ]
            blocker = next(
                (
                    item
                    for item in preview.launch_blockers
                    if step.step_id in item.step_ids
                ),
                None,
            )
            status = self._infer_step_status(
                run_status=run.status,
                linked_goals=linked_goals,
                linked_schedules=linked_schedules,
                linked_tasks=linked_tasks,
                blocker=blocker,
            )
            last_event_at = self._latest_timestamp(
                [
                    *(str(item.get("updated_at") or "") for item in linked_goals),
                    *(str(item.get("updated_at") or "") for item in linked_schedules),
                    *(str(item.get("updated_at") or "") for item in linked_tasks),
                    *(str(item.get("created_at") or "") for item in linked_decisions),
                    *(str(item.get("created_at") or "") for item in linked_evidence),
                ],
            )
            step_records.append(
                WorkflowStepExecutionRecord(
                    step_id=step.step_id,
                    title=step.title,
                    kind=step.kind,
                    execution_mode=step.execution_mode,
                    status=status,
                    owner_role_id=step.owner_role_id,
                    owner_role_candidates=list(step.owner_role_candidates or []),
                    owner_agent_id=step.owner_agent_id,
                    linked_goal_ids=linked_goal_ids,
                    linked_schedule_ids=linked_schedule_ids,
                    linked_task_ids=[
                        str(item.get("id") or "")
                        for item in linked_tasks
                        if str(item.get("id") or "").strip()
                    ],
                    linked_decision_ids=[
                        str(item.get("id") or "")
                        for item in linked_decisions
                        if str(item.get("id") or "").strip()
                    ],
                    linked_evidence_ids=[
                        str(item.get("id") or "")
                        for item in linked_evidence
                        if str(item.get("id") or "").strip()
                    ],
                    blocked_reason_code=blocker.code if blocker is not None else None,
                    blocked_reason_message=blocker.message if blocker is not None else None,
                    summary=step.summary,
                    last_event_at=last_event_at,
                    routes={
                        "template": f"/api/workflow-templates/{run.template_id}",
                        "run": f"/api/workflow-runs/{run.run_id}",
                        "detail": f"/api/workflow-runs/{run.run_id}/steps/{step.step_id}",
                    },
                ),
            )
        return step_records

    def _infer_step_status(
        self,
        *,
        run_status: str,
        linked_goals: list[dict[str, Any]],
        linked_schedules: list[dict[str, Any]],
        linked_tasks: list[dict[str, Any]],
        blocker: WorkflowTemplateLaunchBlocker | None,
    ) -> str:
        if blocker is not None:
            return "blocked"
        if run_status == "cancelled":
            return "cancelled"
        if linked_goals:
            goal_statuses = {str(item.get("status") or "") for item in linked_goals}
            if goal_statuses and goal_statuses <= {"completed", "archived"}:
                return "completed"
            if "active" in goal_statuses:
                return "running"
            if "draft" in goal_statuses:
                return "planned"
        if linked_schedules:
            schedule_statuses = {str(item.get("status") or "") for item in linked_schedules}
            if "paused" in schedule_statuses:
                return "paused"
            if "scheduled" in schedule_statuses:
                return "scheduled"
        if linked_tasks:
            task_statuses = {str(item.get("status") or "") for item in linked_tasks}
            if "completed" in task_statuses and len(task_statuses) == 1:
                return "completed"
            if task_statuses & {"running", "in_progress"}:
                return "running"
        return "planned"

    def _build_run_diagnosis(
        self,
        *,
        run: WorkflowRunRecord,
        preview: WorkflowTemplatePreview,
        goals: list[dict[str, Any]],
        schedules: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        host_snapshot: dict[str, Any],
    ) -> WorkflowRunDiagnosis:
        blocking_codes = [item.code for item in preview.launch_blockers]
        goal_statuses = self._count_statuses(goals)
        schedule_statuses = self._count_statuses(schedules)
        open_decision_count = sum(
            1
            for item in decisions
            if str(item.get("status") or "").strip().lower() in {"open", "reviewing"}
        )
        completed_task_count = sum(
            1
            for item in tasks
            if str(item.get("status") or "").strip().lower() == "completed"
        )
        diagnosis_status = run.status
        if blocking_codes:
            diagnosis_status = "blocked"
        elif open_decision_count > 0:
            diagnosis_status = "awaiting-approval"
        summary = (
            "Workflow run has active launch or governance blockers."
            if blocking_codes
            else "Workflow run is waiting on approval."
            if open_decision_count > 0
            else "Workflow run is active and resumable."
            if run.status in {"planned", "running"}
            else "Workflow run is in a terminal state."
        )
        return WorkflowRunDiagnosis(
            status=diagnosis_status,
            summary=summary,
            can_resume=run.status in {"planned", "running"} and not blocking_codes,
            blocking_codes=blocking_codes,
            missing_capability_ids=list(preview.missing_capability_ids or []),
            assignment_gap_capability_ids=list(preview.assignment_gap_capability_ids or []),
            open_decision_count=open_decision_count,
            task_count=len(tasks),
            completed_task_count=completed_task_count,
            evidence_count=len(evidence),
            goal_statuses=goal_statuses,
            schedule_statuses=schedule_statuses,
            host_snapshot=dict(host_snapshot or {}),
            routes={
                "run": f"/api/workflow-runs/{run.run_id}",
                "template": f"/api/workflow-templates/{run.template_id}",
                "decisions": "/api/runtime-center/decisions",
            },
        )

    def _count_statuses(self, items: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            status = str(item.get("status") or "").strip() or "unknown"
            counts[status] = counts.get(status, 0) + 1
        return counts

    def _latest_timestamp(self, values: list[str]) -> str | None:
        normalized = [value.strip() for value in values if value and value.strip()]
        if not normalized:
            return None
        return max(normalized)

    def _first_string(self, *values: object) -> str | None:
        for value in values:
            normalized = _string(value)
            if normalized is not None:
                return normalized
        return None

    def _mapping(self, value: object) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    def _resolve_environment_service(self) -> object | None:
        service = getattr(self, "_environment_service", None)
        if service is not None:
            return service
        agent_profile_service = getattr(self, "_agent_profile_service", None)
        return getattr(agent_profile_service, "_environment_service", None)

    def _resolve_host_twin_detail(
        self,
        payload: WorkflowPreviewRequest,
    ) -> dict[str, Any] | None:
        service = self._resolve_environment_service()
        if service is None:
            return None
        session_mount_id = _string(payload.session_mount_id)
        if session_mount_id:
            getter = getattr(service, "get_session_detail", None)
            if callable(getter):
                detail = getter(session_mount_id, limit=20)
                if isinstance(detail, dict):
                    return dict(detail)
        environment_id = _string(payload.environment_id)
        if environment_id:
            getter = getattr(service, "get_environment_detail", None)
            if callable(getter):
                detail = getter(environment_id, limit=20)
                if isinstance(detail, dict):
                    return dict(detail)
        return None

    def _extract_host_snapshot(
        self,
        detail: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(detail, dict):
            return {}
        host_twin = self._mapping(detail.get("host_twin"))
        return dict(host_twin) if host_twin else {}

    def _resolve_host_snapshot_from_request(
        self,
        payload: WorkflowPreviewRequest | None,
    ) -> dict[str, Any]:
        if payload is None:
            return {}
        return self._extract_host_snapshot(self._resolve_host_twin_detail(payload))

    def _build_run_preview_request(
        self,
        *,
        run: WorkflowRunRecord,
        preview: WorkflowTemplatePreview,
    ) -> WorkflowPreviewRequest:
        metadata = dict(run.metadata or {})
        return WorkflowPreviewRequest(
            owner_scope=preview.owner_scope or run.owner_scope,
            industry_instance_id=preview.industry_instance_id or run.industry_instance_id,
            owner_agent_id=run.owner_agent_id,
            environment_id=_string(metadata.get("environment_id")),
            session_mount_id=_string(metadata.get("session_mount_id")),
            preset_id=_string(metadata.get("preset_id")),
            parameters=dict(run.parameter_payload or preview.parameters or {}),
        )

    def _refresh_run_preview(
        self,
        *,
        template: WorkflowTemplateRecord,
        preview: WorkflowTemplatePreview,
        request: WorkflowPreviewRequest,
    ) -> WorkflowTemplatePreview:
        try:
            return self._build_preview(template, request)
        except Exception:
            return preview

    def _infer_host_twin_surface_kind(
        self,
        required_capability_ids: list[str],
    ) -> str | None:
        for capability_id in required_capability_ids:
            surface_kind = self._HOST_TWIN_SURFACE_BY_CAPABILITY.get(capability_id)
            if surface_kind is not None:
                return surface_kind
        return None

    def _build_step_host_twin_requirement(
        self,
        *,
        raw_step: dict[str, Any],
        step: WorkflowTemplateStepPreview,
    ) -> dict[str, Any] | None:
        if step.execution_mode != "leaf":
            return None
        preflight = self._mapping(raw_step.get("environment_preflight"))
        surface_kind = self._first_string(
            preflight.get("surface_kind"),
            self._infer_host_twin_surface_kind(step.required_capability_ids),
        )
        if surface_kind not in {"browser", "desktop"}:
            return None
        explicit_mutating = preflight.get("mutating")
        mutating = (
            bool(explicit_mutating)
            if isinstance(explicit_mutating, bool)
            else surface_kind == "desktop"
        )
        app_family = self._first_string(preflight.get("app_family"))
        if app_family is None:
            if surface_kind == "browser":
                app_family = "browser_backoffice"
            elif mutating:
                app_family = "office_document"
            else:
                app_family = "desktop_specialized"
        return {
            "surface_kind": surface_kind,
            "mutating": mutating,
            "step_id": step.step_id,
            "title": step.title,
            "agent_id": step.owner_agent_id,
            "capability_ids": list(step.required_capability_ids or []),
            "app_family": app_family,
        }

    def _host_requirement_for_step(
        self,
        preview: WorkflowTemplatePreview,
        step_id: str,
    ) -> dict[str, Any]:
        requirements = [dict(item) for item in list(preview.host_requirements or [])]
        if not requirements:
            return {}
        for requirement in requirements:
            if _string(requirement.get("step_id")) == step_id:
                return requirement
        return requirements[0]

    def _surface_active_projection(
        self,
        *,
        surface_kind: str,
        workspace_surfaces: dict[str, Any],
    ) -> dict[str, Any]:
        surface = self._mapping(workspace_surfaces.get(surface_kind))
        if surface_kind == "desktop":
            return self._mapping(surface.get("active_window"))
        if surface_kind == "browser":
            return self._mapping(surface.get("active_tab"))
        return {}

    def _step_requirement_capability_ids(
        self,
        requirements: list[dict[str, Any]],
    ) -> list[str]:
        capability_ids: list[str] = []
        seen: set[str] = set()
        for requirement in requirements:
            for capability_id in list(requirement.get("capability_ids") or []):
                normalized = _string(capability_id)
                if normalized is None or normalized in seen:
                    continue
                seen.add(normalized)
                capability_ids.append(normalized)
        return capability_ids

    def _step_requirement_agent_id(
        self,
        requirements: list[dict[str, Any]],
    ) -> str | None:
        agent_ids = {
            normalized
            for normalized in (
                _string(requirement.get("agent_id"))
                for requirement in requirements
            )
            if normalized is not None
        }
        if len(agent_ids) == 1:
            return next(iter(agent_ids))
        return None

    def _build_host_twin_launch_blockers(
        self,
        *,
        payload: WorkflowPreviewRequest,
        requirements: list[dict[str, Any]],
    ) -> list[WorkflowTemplateLaunchBlocker]:
        if not requirements:
            return []
        detail = self._resolve_host_twin_detail(payload)
        if detail is None:
            return []
        host_twin = self._mapping(detail.get("host_twin"))
        host_twin_continuity = self._mapping(host_twin.get("continuity"))
        host_twin_legal_recovery = self._mapping(host_twin.get("legal_recovery"))
        host_twin_scheduler = self._mapping(host_twin.get("scheduler_inputs"))
        host_twin_execution_ready = self._mapping(host_twin.get("execution_mutation_ready"))
        host_twin_coordination = self._mapping(host_twin.get("coordination"))
        host_twin_blocked_surfaces = [
            self._mapping(item)
            for item in list(host_twin.get("blocked_surfaces") or [])
            if isinstance(item, dict)
        ]
        host_companion = self._mapping(detail.get("host_companion_session"))
        host_contract = self._mapping(detail.get("host_contract"))
        recovery = self._mapping(detail.get("recovery"))
        host_event_summary = self._mapping(detail.get("host_event_summary"))
        workspace_graph = self._mapping(detail.get("workspace_graph"))
        workspace_surfaces = self._mapping(workspace_graph.get("surfaces"))
        host_blocker = self._mapping(workspace_surfaces.get("host_blocker"))
        active_alert_families = _unique_strings(
            host_twin.get("active_blocker_families"),
            host_event_summary.get("active_alert_families"),
        )
        continuity_status = self._first_string(
            host_twin_continuity.get("status"),
            host_companion.get("continuity_status"),
            recovery.get("status"),
        )
        recovery_status = self._first_string(recovery.get("status"))
        handoff_state = self._first_string(host_contract.get("handoff_state"))
        blockers: list[WorkflowTemplateLaunchBlocker] = []
        requirements_by_surface: dict[str, list[dict[str, Any]]] = {}
        for requirement in requirements:
            surface_kind = self._first_string(requirement.get("surface_kind"))
            if surface_kind is None:
                continue
            requirements_by_surface.setdefault(surface_kind, []).append(requirement)

        for surface_kind, surface_requirements in requirements_by_surface.items():
            all_step_ids = [
                str(requirement.get("step_id"))
                for requirement in surface_requirements
                if _string(requirement.get("step_id")) is not None
            ]
            mutating_step_ids = [
                str(requirement.get("step_id"))
                for requirement in surface_requirements
                if requirement.get("mutating") is True
                and _string(requirement.get("step_id")) is not None
            ]
            active_surface = self._surface_active_projection(
                surface_kind=surface_kind,
                workspace_surfaces=workspace_surfaces,
            )
            blocked_surface = next(
                (
                    item
                    for item in host_twin_blocked_surfaces
                    if self._first_string(item.get("surface_kind")) in {
                        surface_kind,
                        "desktop_app" if surface_kind == "desktop" else surface_kind,
                    }
                ),
                {},
            )
            current_gap = self._first_string(
                self._mapping(host_twin_coordination.get("contention_forecast")).get("reason"),
                blocked_surface.get("reason"),
                active_surface.get("current_gap_or_blocker"),
                host_contract.get("current_gap_or_blocker"),
                host_companion.get("current_gap_or_blocker"),
                recovery.get("note"),
            )
            capability_ids = self._step_requirement_capability_ids(surface_requirements)
            agent_id = self._step_requirement_agent_id(surface_requirements)

            if continuity_status not in self._HOST_TWIN_VALID_CONTINUITY_STATUSES:
                blockers.append(
                    WorkflowTemplateLaunchBlocker(
                        code="host-twin-continuity-invalid",
                        message=(
                            f"{surface_kind.capitalize()} host continuity is "
                            f"'{continuity_status or 'unknown'}'. "
                            f"{current_gap or 'Attach or recover a valid host twin before launch.'}"
                        ),
                        agent_id=agent_id,
                        capability_ids=capability_ids,
                        step_ids=all_step_ids,
                    ),
                )

            if mutating_step_ids:
                access_mode = self._first_string(host_contract.get("access_mode"))
                execution_key = "desktop_app" if surface_kind == "desktop" else "browser"
                writable_surface_available = host_twin_execution_ready.get(execution_key)
                if not isinstance(writable_surface_available, bool):
                    active_ref = self._first_string(
                        active_surface.get("window_ref"),
                        active_surface.get("tab_id"),
                    )
                    writer_lock_scope = self._first_string(
                        active_surface.get("writer_lock_scope"),
                    )
                    writable_surface_available = (
                        access_mode == "writer" and active_ref is not None
                    )
                    if surface_kind == "desktop":
                        writable_surface_available = (
                            writable_surface_available and writer_lock_scope is not None
                        )
                if not writable_surface_available:
                    blockers.append(
                        WorkflowTemplateLaunchBlocker(
                            code="host-twin-writable-surface-unavailable",
                            message=(
                                f"{surface_kind.capitalize()} host twin is not currently writable "
                                f"(access_mode={access_mode or 'unknown'}). "
                                f"{current_gap or 'No writable surface is currently available.'}"
                            ),
                            agent_id=agent_id,
                            capability_ids=capability_ids,
                            step_ids=mutating_step_ids,
                        ),
                    )

                legal_recovery_path = self._first_string(
                    host_twin_legal_recovery.get("path"),
                    host_twin_legal_recovery.get("resume_kind"),
                )
                requires_human_return = bool(
                    host_twin_continuity.get("requires_human_return"),
                )
                if (
                    handoff_state in self._HOST_TWIN_HANDOFF_ONLY_STATES
                    or requires_human_return
                    or legal_recovery_path == "handoff"
                    or (
                        recovery_status == "same-host-other-process"
                        and not bool(recovery.get("recoverable"))
                    )
                ):
                    blockers.append(
                        WorkflowTemplateLaunchBlocker(
                            code="host-twin-recovery-handoff-only",
                            message=(
                                f"{surface_kind.capitalize()} host twin is currently in "
                                f"handoff/recovery state '{handoff_state or recovery_status or 'unknown'}'. "
                                f"{self._first_string(host_contract.get('handoff_reason'), recovery.get('note')) or 'Resolve the legal recovery path before launch.'}"
                            ),
                            agent_id=agent_id,
                            capability_ids=capability_ids,
                            step_ids=mutating_step_ids,
                        ),
                    )

                blocking_families = set(active_alert_families)
                host_blocker_family = self._first_string(host_blocker.get("event_family"))
                host_blocker_response = self._first_string(
                    host_blocker.get("recommended_runtime_response"),
                )
                scheduler_blocker_family = self._first_string(
                    host_twin_scheduler.get("active_blocker_family"),
                )
                if scheduler_blocker_family is not None:
                    blocking_families.add(scheduler_blocker_family)
                if (
                    host_blocker_family is not None
                    and host_blocker_response in self._HOST_TWIN_BLOCKING_RESPONSES
                ):
                    blocking_families.add(host_blocker_family)
                if blocking_families:
                    blockers.append(
                        WorkflowTemplateLaunchBlocker(
                            code="host-twin-active-host-blockers",
                            message=(
                                f"Active host blocker families make {surface_kind} mutating work unsafe: "
                                f"{', '.join(sorted(blocking_families))}. "
                                f"{current_gap or 'Stabilize the host before launch.'}"
                            ),
                            agent_id=agent_id,
                            capability_ids=capability_ids,
                            step_ids=mutating_step_ids,
                        ),
                    )
                contention_forecast = self._mapping(
                    host_twin_coordination.get("contention_forecast"),
                )
                contention_severity = self._first_string(
                    contention_forecast.get("severity"),
                )
                recommended_scheduler_action = self._first_string(
                    host_twin_coordination.get("recommended_scheduler_action"),
                    host_twin_scheduler.get("recommended_scheduler_action"),
                )
                if contention_severity == "blocked" or (
                    recommended_scheduler_action in self._HOST_TWIN_BLOCKING_RESPONSES
                ):
                    blockers.append(
                        WorkflowTemplateLaunchBlocker(
                            code="host-twin-contention-forecast-blocked",
                            message=(
                                f"{surface_kind.capitalize()} host coordination forecasts a blocked writer path: "
                                f"{self._first_string(contention_forecast.get('reason'), current_gap) or 'handoff required.'}"
                            ),
                            agent_id=agent_id,
                            capability_ids=capability_ids,
                            step_ids=mutating_step_ids,
                        )
                    )
        return blockers

    def _build_preview(
        self,
        template: WorkflowTemplateRecord,
        payload: WorkflowPreviewRequest,
    ) -> WorkflowTemplatePreview:
        preset = self._resolve_preset(
            template_id=template.template_id,
            preset_id=payload.preset_id,
        )
        merged_parameters = self._merge_parameters(
            preset=preset,
            parameters=payload.parameters,
        )
        industry_context = self._resolve_industry_context(payload.industry_instance_id)
        context: dict[str, Any] = {
            **merged_parameters,
            **industry_context,
        }
        owner_scope = (
            _string(payload.owner_scope)
            or (preset.owner_scope if preset is not None else None)
            or _string(industry_context.get("owner_scope"))
            or f"workflow:{template.template_id}"
        )
        dependency_map: dict[str, WorkflowTemplateDependencyStatus] = {}
        budget_by_agent: dict[str, int] = {}
        required_capabilities_by_agent: dict[str, set[str]] = {}
        owner_role_by_agent: dict[str, str | None] = {}
        steps: list[WorkflowTemplateStepPreview] = []
        host_twin_requirements: list[dict[str, Any]] = []
        materialized_goals: list[dict[str, Any]] = []
        materialized_schedules: list[dict[str, Any]] = []
        installed_client_keys = self._list_installed_mcp_client_keys()

        for raw_step in template.step_specs:
            if not isinstance(raw_step, dict):
                continue
            requested_owner_role_id = (
                _string(raw_step.get("owner_role_id")) or template.owner_role_id
            )
            owner_role_candidates = self._build_owner_role_candidates(
                requested_owner_role_id=requested_owner_role_id,
                raw_candidates=raw_step.get("owner_role_candidates"),
            )
            resolved_owner_role_id, resolved_owner_agent_id = self._resolve_owner_binding(
                raw_step=raw_step,
                template=template,
                industry_context=industry_context,
                fallback_owner_agent_id=payload.owner_agent_id,
            )
            owner_role_id = resolved_owner_role_id or requested_owner_role_id
            owner_agent_id = _string(raw_step.get("owner_agent_id")) or resolved_owner_agent_id
            required_capability_ids = _unique_strings(raw_step.get("required_capability_ids"))
            missing_capability_ids = [
                capability_id
                for capability_id in required_capability_ids
                if not self._has_capability(capability_id)
            ]
            if owner_agent_id:
                budget_by_agent[owner_agent_id] = (
                    budget_by_agent.get(owner_agent_id, 0) + len(required_capability_ids)
                )
                required_capabilities_by_agent.setdefault(owner_agent_id, set()).update(
                    required_capability_ids,
                )
                owner_role_by_agent.setdefault(owner_agent_id, owner_role_id)
            for capability_id in required_capability_ids:
                mount = self._get_capability_mount(capability_id)
                status = dependency_map.setdefault(
                    capability_id,
                    WorkflowTemplateDependencyStatus(
                        capability_id=capability_id,
                        installed=mount is not None,
                        enabled=mount.enabled if mount is not None else None,
                        available=bool(mount.enabled) if mount is not None else False,
                        install_templates=self._resolve_install_templates_for_capability(
                            template=template,
                            capability_id=capability_id,
                            installed_client_keys=installed_client_keys,
                        ),
                    ),
                )
                if raw_step.get("id") and str(raw_step["id"]) not in status.required_by_steps:
                    status.required_by_steps.append(str(raw_step["id"]))
                if owner_agent_id and owner_agent_id not in status.target_agent_ids:
                    status.target_agent_ids.append(owner_agent_id)

            title = _render_text(raw_step.get("title"), context) or template.title
            summary = _render_text(raw_step.get("summary"), context) or template.summary
            kind = "schedule" if _string(raw_step.get("kind")) == "schedule" else "goal"
            execution_mode = (
                "control"
                if _string(raw_step.get("execution_mode")) == "control"
                else "leaf"
            )
            step_payload = self._build_step_payload(
                raw_step=raw_step,
                context=context,
                owner_agent_id=owner_agent_id,
            )
            preview_step = WorkflowTemplateStepPreview(
                step_id=str(raw_step.get("id") or title),
                title=title,
                summary=summary,
                kind=kind,
                execution_mode=execution_mode,
                owner_role_id=owner_role_id,
                owner_role_candidates=owner_role_candidates,
                owner_agent_id=owner_agent_id,
                required_capability_ids=required_capability_ids,
                missing_capability_ids=missing_capability_ids,
                budget_cost=len(required_capability_ids),
                payload_preview=step_payload,
            )
            steps.append(preview_step)
            host_twin_requirement = self._build_step_host_twin_requirement(
                raw_step=raw_step,
                step=preview_step,
            )
            if host_twin_requirement is not None:
                host_twin_requirements.append(host_twin_requirement)
            if kind == "goal":
                materialized_goals.append(
                    {
                        "title": title,
                        "summary": summary,
                        "owner_agent_id": owner_agent_id,
                        "owner_role_id": owner_role_id,
                        "execution_mode": execution_mode,
                    },
                )
            else:
                materialized_schedules.append(
                    {
                        "id": step_payload.get("id"),
                        "title": title,
                        "cron": step_payload.get("cron"),
                        "timezone": step_payload.get("timezone"),
                        "owner_agent_id": owner_agent_id,
                        "owner_role_id": owner_role_id,
                    },
                )

        assignment_gap_capability_ids: set[str] = set()
        launch_blockers: list[WorkflowTemplateLaunchBlocker] = []
        budget_status_by_agent: list[WorkflowTemplateAgentBudgetStatus] = []
        effective_capabilities_by_agent: dict[str, set[str]] = {}
        assigned_capabilities_by_agent: dict[str, set[str]] = {}

        for agent_id, required_capabilities in required_capabilities_by_agent.items():
            capability_surface = self._get_agent_capability_surface(agent_id)
            profile = self._get_agent_profile(agent_id)
            effective_capabilities = set(
                _unique_strings(
                    list(capability_surface.get("effective_capabilities") or [])
                    if isinstance(capability_surface, dict)
                    else [],
                    list(getattr(profile, "capabilities", []) or []),
                ),
            )
            effective_capabilities_by_agent[agent_id] = effective_capabilities
            baseline_capabilities = _unique_strings(
                list(capability_surface.get("baseline_capabilities") or [])
                if isinstance(capability_surface, dict)
                else [],
            )
            assigned_capabilities_by_agent[agent_id] = set(
                _unique_strings(
                    list(effective_capabilities),
                    baseline_capabilities,
                ),
            )
            planned_capability_ids = _unique_strings(
                list(effective_capabilities),
                sorted(required_capabilities),
            )
            current_extra_count = len(
                [
                    capability_id
                    for capability_id in effective_capabilities
                    if capability_id not in baseline_capabilities
                ],
            )
            planned_extra_count = len(
                [
                    capability_id
                    for capability_id in planned_capability_ids
                    if capability_id not in baseline_capabilities
                ],
            )
            agent_class = _string(getattr(profile, "agent_class", None))
            extra_limit = (
                self._BUSINESS_AGENT_EXTRA_CAPABILITY_LIMIT
                if agent_class == "business"
                else None
            )
            over_limit_by = (
                max(planned_extra_count - extra_limit, 0)
                if isinstance(extra_limit, int)
                else 0
            )
            blocking = over_limit_by > 0
            budget_status_by_agent.append(
                WorkflowTemplateAgentBudgetStatus(
                    agent_id=agent_id,
                    role_id=owner_role_by_agent.get(agent_id),
                    agent_class=agent_class,
                    agent_present=profile is not None,
                    baseline_capability_ids=baseline_capabilities,
                    effective_capability_ids=sorted(effective_capabilities),
                    required_capability_ids=sorted(required_capabilities),
                    planned_capability_ids=planned_capability_ids,
                    current_extra_count=current_extra_count,
                    planned_extra_count=planned_extra_count,
                    extra_limit=extra_limit,
                    over_limit_by=over_limit_by,
                    within_limit=not blocking,
                    blocking=blocking,
                ),
            )
            if profile is None:
                launch_blockers.append(
                    WorkflowTemplateLaunchBlocker(
                        code="target-agent-unavailable",
                        message=f"Target agent '{agent_id}' is not currently available.",
                        agent_id=agent_id,
                        capability_ids=sorted(required_capabilities),
                        step_ids=[
                            step.step_id
                            for step in steps
                            if step.owner_agent_id == agent_id
                        ],
                    ),
                )
            if blocking:
                launch_blockers.append(
                    WorkflowTemplateLaunchBlocker(
                        code="capability-budget-exceeded",
                        message=(
                            f"Agent '{agent_id}' would exceed the non-baseline capability "
                            f"budget ({planned_extra_count}/{extra_limit})."
                        ),
                        agent_id=agent_id,
                        capability_ids=sorted(required_capabilities),
                        step_ids=[
                            step.step_id
                            for step in steps
                            if step.owner_agent_id == agent_id
                        ],
                    ),
                )

        for step in steps:
            if not step.owner_agent_id:
                continue
            assigned_capabilities = assigned_capabilities_by_agent.get(step.owner_agent_id, set())
            step.assignment_gap_capability_ids = sorted(
                capability_id
                for capability_id in step.required_capability_ids
                if capability_id not in step.missing_capability_ids
                and capability_id not in assigned_capabilities
            )
            assignment_gap_capability_ids.update(step.assignment_gap_capability_ids)

        for dependency in dependency_map.values():
            if dependency.available:
                continue
            if dependency.installed:
                launch_blockers.append(
                    WorkflowTemplateLaunchBlocker(
                        code="disabled-capability",
                        message=(
                            f"Capability '{dependency.capability_id}' is installed but currently "
                            "disabled."
                        ),
                        capability_ids=[dependency.capability_id],
                        step_ids=list(dependency.required_by_steps),
                    ),
                )
                continue
            launch_blockers.append(
                WorkflowTemplateLaunchBlocker(
                    code="missing-capability-install",
                    message=f"Capability '{dependency.capability_id}' is required but not installed.",
                    capability_ids=[dependency.capability_id],
                    step_ids=list(dependency.required_by_steps),
                ),
            )

        for agent_id, required_capabilities in required_capabilities_by_agent.items():
            assigned_capabilities = assigned_capabilities_by_agent.get(agent_id, set())
            missing_assignments = sorted(
                capability_id
                for capability_id in required_capabilities
                if capability_id not in assigned_capabilities and self._has_capability(capability_id)
            )
            if not missing_assignments:
                continue
            launch_blockers.append(
                WorkflowTemplateLaunchBlocker(
                    code="assignment-gap",
                    message=(
                        f"Agent '{agent_id}' does not currently have the required assigned "
                        f"capabilities: {', '.join(missing_assignments)}."
                    ),
                    agent_id=agent_id,
                    capability_ids=missing_assignments,
                    step_ids=[
                        step.step_id
                        for step in steps
                        if step.owner_agent_id == agent_id
                        and set(step.assignment_gap_capability_ids) & set(missing_assignments)
                    ],
                ),
            )

        launch_blockers.extend(
            self._build_host_twin_launch_blockers(
                payload=payload,
                requirements=host_twin_requirements,
            ),
        )

        return WorkflowTemplatePreview(
            template_id=template.template_id,
            title=template.title,
            summary=template.summary,
            owner_scope=owner_scope,
            industry_instance_id=_string(payload.industry_instance_id),
            strategy_memory=(
                dict(industry_context.get("strategy_memory"))
                if isinstance(industry_context.get("strategy_memory"), dict)
                else None
            ),
            parameters=merged_parameters,
            steps=steps,
            dependencies=list(dependency_map.values()),
            missing_capability_ids=sorted(
                {
                    capability_id
                    for step in steps
                    for capability_id in step.missing_capability_ids
                }
            ),
            assignment_gap_capability_ids=sorted(assignment_gap_capability_ids),
            capability_budget_by_agent=budget_by_agent,
            budget_status_by_agent=budget_status_by_agent,
            host_requirements=host_twin_requirements,
            launch_blockers=launch_blockers,
            can_launch=not launch_blockers,
            materialized_objects={
                "goals": materialized_goals,
                "schedules": materialized_schedules,
            },
        )

    def _build_step_payload(
        self,
        *,
        raw_step: dict[str, Any],
        context: dict[str, Any],
        owner_agent_id: str | None,
    ) -> dict[str, Any]:
        payload = {
            "id": _render_text(raw_step.get("id"), context) or str(raw_step.get("id") or ""),
            "cron": _render_text(raw_step.get("cron"), context),
            "timezone": _render_text(raw_step.get("timezone"), context) or "UTC",
            "request_input": _render_text(raw_step.get("request_input"), context),
            "dispatch_channel": _render_text(raw_step.get("dispatch_channel"), context) or "console",
            "dispatch_user_id": _render_text(raw_step.get("dispatch_user_id"), context) or "workflow",
            "dispatch_session_id": _render_text(raw_step.get("dispatch_session_id"), context),
            "dispatch_mode": _render_text(raw_step.get("dispatch_mode"), context) or "final",
            "owner_agent_id": owner_agent_id,
            "plan_steps": [
                _render_text(step, context)
                for step in list(raw_step.get("plan_steps") or [])
                if _render_text(step, context)
            ],
        }
        if not payload["dispatch_session_id"]:
            payload["dispatch_session_id"] = payload["id"] or owner_agent_id or "workflow"
        return payload
