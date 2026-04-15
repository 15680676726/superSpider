# -*- coding: utf-8 -*-
from __future__ import annotations

from .service_shared import *  # noqa: F401,F403
from ..app.runtime_center.task_review_projection import (
    build_host_twin_summary,
    host_twin_summary_ready,
)
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


class _WorkflowServicePreviewMixin:
    _HOST_TWIN_SURFACE_BY_CAPABILITY = {
        "mcp:desktop_windows": "desktop",
        "tool:browser_use": "browser",
        "system:document_bridge_runtime": "document",
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

    def _canonical_host_summary_ready(self, host_twin_summary: dict[str, Any]) -> bool:
        return host_twin_summary_ready(host_twin_summary)

    def _canonical_host_summary_overrides_live_blockers(
        self,
        host_twin_summary: dict[str, Any],
        *,
        active_alert_families: object | None = None,
        host_blocker: dict[str, Any] | None = None,
        host_twin_scheduler: dict[str, Any] | None = None,
    ) -> bool:
        if not self._canonical_host_summary_ready(host_twin_summary):
            return False
        recommended_scheduler_action = self._first_string(
            host_twin_summary.get("recommended_scheduler_action"),
        )
        if recommended_scheduler_action in {"proceed", "ready", "clear"}:
            return True
        blocking_families = set(
            _unique_strings(
                active_alert_families,
                host_twin_summary.get("active_blocker_families"),
                host_twin_summary.get("active_blocker_family"),
                host_twin_scheduler.get("active_blocker_family")
                if isinstance(host_twin_scheduler, dict)
                else None,
            ),
        )
        host_blocker_family = self._first_string(
            host_blocker.get("event_family") if isinstance(host_blocker, dict) else None,
        )
        host_blocker_response = self._first_string(
            host_blocker.get("recommended_runtime_response")
            if isinstance(host_blocker, dict)
            else None,
        )
        if (
            host_blocker_family is not None
            and host_blocker_response in self._HOST_TWIN_BLOCKING_RESPONSES
        ):
            blocking_families.add(host_blocker_family)
        if blocking_families:
            return False
        return recommended_scheduler_action in {"continue", "proceed", "ready", "clear"}

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
        return self._build_run_detail_from_preview(
            run=run,
            template=template,
            preview=preview,
            host_snapshot=host_snapshot,
        )

    def _build_run_detail_from_preview(
        self,
        *,
        run: WorkflowRunRecord,
        template: WorkflowTemplateRecord,
        preview: WorkflowTemplatePreview,
        host_snapshot: dict[str, Any],
    ) -> WorkflowRunDetail:
        goals: list[dict[str, Any]] = []
        tasks: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []
        goal_detail_by_id: dict[str, dict[str, Any]] = {}
        step_seed_items = _workflow_step_execution_seed(run)
        step_seed_by_id = {
            str(seed.get("step_id") or ""): seed
            for seed in step_seed_items
            if str(seed.get("step_id") or "").strip()
        }
        goal_ids_by_step = _workflow_goal_ids_by_step(
            run,
            goal_override_repository=self._goal_override_repository,
        )
        visible_goal_ids: set[str] = set()
        for step in preview.steps:
            if step.kind != "goal":
                continue
            seed = step_seed_by_id.get(step.step_id, {})
            persisted_task_ids = [
                str(item)
                for item in list(seed.get("linked_task_ids") or [])
                if str(item).strip()
            ]
            persisted_decision_ids = [
                str(item)
                for item in list(seed.get("linked_decision_ids") or [])
                if str(item).strip()
            ]
            persisted_evidence_ids = [
                str(item)
                for item in list(seed.get("linked_evidence_ids") or [])
                if str(item).strip()
            ]
            if persisted_task_ids or persisted_decision_ids or persisted_evidence_ids:
                continue
            visible_goal_ids.update(goal_ids_by_step.get(step.step_id, []))
        runtime_goal_ids = _unique_strings(*goal_ids_by_step.values())
        goal_ids = sorted(_unique_strings(visible_goal_ids, runtime_goal_ids))
        persisted_task_ids = _unique_strings(
            *[
                [
                    str(item)
                    for item in list(seed.get("linked_task_ids") or [])
                    if str(item).strip()
                ]
                for seed in step_seed_items
            ],
        )
        persisted_decision_ids = _unique_strings(
            *[
                [
                    str(item)
                    for item in list(seed.get("linked_decision_ids") or [])
                    if str(item).strip()
                ]
                for seed in step_seed_items
            ],
        )
        persisted_evidence_ids = _unique_strings(
            *[
                [
                    str(item)
                    for item in list(seed.get("linked_evidence_ids") or [])
                    if str(item).strip()
                ]
                for seed in step_seed_items
            ],
        )
        (
            goal_payload_by_id,
            tasks,
            decisions,
            evidence,
        ) = self._collect_workflow_goal_runtime_payloads(
            goal_ids=goal_ids,
            task_goal_ids=runtime_goal_ids,
            persisted_task_ids=persisted_task_ids,
            persisted_decision_ids=persisted_decision_ids,
            persisted_evidence_ids=persisted_evidence_ids,
        )
        for goal_id in goal_ids:
            payload = goal_payload_by_id.get(goal_id)
            if payload is None:
                continue
            goal_detail_by_id[goal_id] = {"goal": payload}
            goals.append(payload)
        schedules: list[dict[str, Any]] = []
        schedule_by_id: dict[str, dict[str, Any]] = {}
        schedule_ids = _workflow_schedule_ids_for_preview(run, preview)
        if self._schedule_repository is not None:
            for schedule_id in schedule_ids:
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
            goal_ids_by_step=goal_ids_by_step,
            goal_detail_by_id=goal_detail_by_id,
            schedule_by_id=schedule_by_id,
            tasks=tasks,
            decisions=decisions,
            evidence=evidence,
        )
        run = self._persist_run_step_runtime_links(
            run=run,
            step_execution=step_execution,
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
        run_payload = run.model_dump(mode="json")
        host_requirements = [dict(item) for item in list(preview.host_requirements or [])]
        if host_requirements:
            run_payload["host_requirements"] = host_requirements
            run_payload["host_requirement"] = dict(host_requirements[0])
        return WorkflowRunDetail(
            run=run_payload,
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
                "goals": [
                    f"/api/goals/{goal_id}/detail"
                    for goal_id in goal_ids
                ],
                "schedules": [
                    f"/api/runtime-center/schedules/{schedule_id}"
                    for schedule_id in schedule_ids
                ],
            },
        )

    def _collect_workflow_goal_runtime_payloads(
        self,
        *,
        goal_ids: list[str],
        task_goal_ids: list[str],
        persisted_task_ids: list[str],
        persisted_decision_ids: list[str],
        persisted_evidence_ids: list[str],
    ) -> tuple[
        dict[str, dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        goal_payload_by_id: dict[str, dict[str, Any]] = {}
        for goal_id in goal_ids:
            goal = self._goal_service.get_goal(goal_id)
            if goal is None:
                continue
            goal_payload_by_id[goal_id] = goal.model_dump(mode="json")

        task_records_by_id: dict[str, Any] = {}
        if self._task_repository is not None:
            if task_goal_ids:
                for task in self._task_repository.list_tasks(goal_ids=task_goal_ids):
                    task_records_by_id[task.id] = task
            if persisted_task_ids:
                for task in self._task_repository.list_tasks(task_ids=persisted_task_ids):
                    task_records_by_id[task.id] = task

        return self._build_workflow_task_runtime_payloads(
            list(task_records_by_id.values()),
            persisted_decision_ids=persisted_decision_ids,
            persisted_evidence_ids=persisted_evidence_ids,
            goal_payload_by_id=goal_payload_by_id,
        )

    def _build_workflow_task_runtime_payloads(
        self,
        tasks: list[Any],
        *,
        persisted_decision_ids: list[str],
        persisted_evidence_ids: list[str],
        goal_payload_by_id: dict[str, dict[str, Any]],
    ) -> tuple[
        dict[str, dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        task_runtime_repository = getattr(self._goal_service, "_task_runtime_repository", None)
        runtime_frame_repository = getattr(self._goal_service, "_runtime_frame_repository", None)
        task_ids = [task.id for task in tasks if getattr(task, "id", None) is not None]
        runtime_map = (
            {
                runtime.task_id: runtime
                for runtime in task_runtime_repository.list_runtimes(task_ids=task_ids)
            }
            if task_runtime_repository is not None and task_ids
            else {}
        )
        task_decisions: dict[str, list[object]] = {}
        if self._decision_request_repository is not None and task_ids:
            for decision in self._decision_request_repository.list_decision_requests(
                task_ids=task_ids,
                limit=None,
            ):
                task_decisions.setdefault(decision.task_id, []).append(decision)
        evidence_by_task: dict[str, list[object]] = {}
        if self._evidence_ledger is not None:
            for task_id in task_ids:
                evidence_by_task[task_id] = list(self._evidence_ledger.list_by_task(task_id))

        task_payloads: list[dict[str, Any]] = []
        decision_map: dict[str, dict[str, Any]] = {}
        evidence_map: dict[str, dict[str, Any]] = {}
        for task in sorted(tasks, key=lambda item: item.updated_at, reverse=True):
            runtime = runtime_map.get(task.id)
            frames = (
                runtime_frame_repository.list_frames(task.id, limit=3)
                if runtime_frame_repository is not None
                else []
            )
            decisions = task_decisions.get(task.id, [])
            evidence = evidence_by_task.get(task.id, [])
            task_payload = task.model_dump(mode="json")
            runtime_payload = (
                runtime.model_dump(mode="json")
                if runtime is not None
                else None
            )
            if runtime_payload:
                task_payload["runtime"] = runtime_payload
            if frames:
                task_payload["frames"] = [frame.model_dump(mode="json") for frame in frames]
            task_payload["decision_count"] = len(decisions)
            task_payload["evidence_count"] = len(evidence)
            task_payload["latest_evidence_id"] = (
                evidence[-1].id
                if evidence and evidence[-1].id is not None
                else runtime.last_evidence_id
                if runtime is not None
                else None
            )
            task_payloads.append(task_payload)
            for decision in decisions:
                decision_map[decision.id] = decision.model_dump(mode="json")
            for record in evidence:
                if record.id is None:
                    continue
                evidence_map[record.id] = _workflow_serialize_evidence(record)

        if self._decision_request_repository is not None:
            for decision_id in persisted_decision_ids:
                decision = self._decision_request_repository.get_decision_request(decision_id)
                if decision is not None:
                    decision_map[decision.id] = decision.model_dump(mode="json")
        if self._evidence_ledger is not None:
            for evidence_id in persisted_evidence_ids:
                record = self._evidence_ledger.get_record(evidence_id)
                if record is not None and record.id is not None:
                    evidence_map[record.id] = _workflow_serialize_evidence(record)

        decisions = sorted(
            decision_map.values(),
            key=lambda item: item.get("created_at") or "",
            reverse=True,
        )
        evidence = sorted(
            evidence_map.values(),
            key=lambda item: item.get("created_at") or "",
            reverse=True,
        )
        return goal_payload_by_id, task_payloads, decisions, evidence

    def _persist_run_step_runtime_links(
        self,
        *,
        run: WorkflowRunRecord,
        step_execution: list[WorkflowStepExecutionRecord],
    ) -> WorkflowRunRecord:
        step_execution_by_id = {
            str(item.step_id or ""): item
            for item in list(step_execution or [])
            if str(item.step_id or "").strip()
        }
        metadata = dict(run.metadata or {})
        step_seed_items = [
            dict(item)
            for item in list(metadata.get("step_execution_seed") or [])
            if isinstance(item, dict)
        ]
        changed = False
        updated_step_seed: list[dict[str, Any]] = []
        for seed in step_seed_items:
            copied = dict(seed)
            step_id = str(copied.get("step_id") or "").strip()
            record = step_execution_by_id.get(step_id)
            if record is None:
                updated_step_seed.append(copied)
                continue
            linked_task_ids = [str(item).strip() for item in list(record.linked_task_ids or []) if str(item).strip()]
            linked_decision_ids = [
                str(item).strip()
                for item in list(record.linked_decision_ids or [])
                if str(item).strip()
            ]
            linked_evidence_ids = [
                str(item).strip()
                for item in list(record.linked_evidence_ids or [])
                if str(item).strip()
            ]
            if linked_task_ids and list(copied.get("linked_task_ids") or []) != linked_task_ids:
                copied["linked_task_ids"] = linked_task_ids
                changed = True
            if linked_decision_ids and list(copied.get("linked_decision_ids") or []) != linked_decision_ids:
                copied["linked_decision_ids"] = linked_decision_ids
                changed = True
            if linked_evidence_ids and list(copied.get("linked_evidence_ids") or []) != linked_evidence_ids:
                copied["linked_evidence_ids"] = linked_evidence_ids
                changed = True
            updated_step_seed.append(copied)
        if not changed:
            return run
        persisted = run.model_copy(
            update={
                "metadata": {
                    **metadata,
                    "step_execution_seed": updated_step_seed,
                },
                "updated_at": _utc_now(),
            },
        )
        self._workflow_run_repository.upsert_run(persisted)
        return persisted

    def _build_step_execution_records(
        self,
        *,
        run: WorkflowRunRecord,
        preview: WorkflowTemplatePreview,
        goal_ids_by_step: dict[str, list[str]],
        goal_detail_by_id: dict[str, dict[str, Any]],
        schedule_by_id: dict[str, dict[str, Any]],
        tasks: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> list[WorkflowStepExecutionRecord]:
        step_seed_by_id = _workflow_step_seed_by_id(run)
        step_records: list[WorkflowStepExecutionRecord] = []
        for step in preview.steps:
            seed = step_seed_by_id.get(step.step_id) or {}
            (
                persisted_task_ids,
                persisted_decision_ids,
                persisted_evidence_ids,
            ) = _workflow_step_persisted_runtime_ids(seed)
            runtime_goal_ids = list(goal_ids_by_step.get(step.step_id, []))
            linked_goal_ids = (
                []
                if persisted_task_ids or persisted_decision_ids or persisted_evidence_ids
                else runtime_goal_ids
            )
            linked_schedule_ids = _workflow_step_schedule_ids(
                run,
                step_kind=step.kind,
                step_id=step.step_id,
                payload_preview=dict(step.payload_preview or {}),
            )
            linked_tasks = [
                item
                for item in tasks
                if str(item.get("goal_id") or "") in runtime_goal_ids
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
                    linked_task_ids=linked_task_ids,
                    linked_decision_ids=linked_decision_ids,
                    linked_evidence_ids=linked_evidence_ids,
                    blocked_reason_code=blocker.code if blocker is not None else None,
                    blocked_reason_message=blocker.message if blocker is not None else None,
                    summary=step.summary,
                    last_event_at=last_event_at,
                    routes={},
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
        if linked_tasks:
            task_statuses = {str(item.get("status") or "") for item in linked_tasks}
            if "completed" in task_statuses and len(task_statuses) == 1:
                return "completed"
            if task_statuses & {"running", "in_progress"}:
                return "running"
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
        host_companion_session = self._mapping(detail.get("host_companion_session"))
        snapshot = dict(host_twin) if host_twin else {}
        if host_companion_session:
            snapshot["host_companion_session"] = dict(host_companion_session)
        embedded_summary = self._mapping(host_twin.get("host_twin_summary"))
        top_level_summary = self._mapping(detail.get("host_twin_summary"))
        derived_summary = build_host_twin_summary(
            host_twin,
            host_companion_session=host_companion_session,
        )
        summary = {
            **dict(embedded_summary or {}),
            **dict(derived_summary or {}),
            **dict(top_level_summary or {}),
        }
        if summary:
            snapshot["host_twin_summary"] = summary
        return snapshot

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
        host_snapshot = self._mapping(metadata.get("host_snapshot"))
        canonical_environment_ref, canonical_environment_id, canonical_session_mount_id = (
            _resolve_canonical_host_identity(
                host_snapshot,
                metadata=metadata,
            )
        )
        return WorkflowPreviewRequest(
            owner_scope=preview.owner_scope or run.owner_scope,
            industry_instance_id=preview.industry_instance_id or run.industry_instance_id,
            owner_agent_id=run.owner_agent_id,
            environment_id=canonical_environment_id or canonical_environment_ref,
            session_mount_id=canonical_session_mount_id,
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
        if surface_kind not in {"browser", "desktop", "document"}:
            return None
        explicit_mutating = preflight.get("mutating")
        mutating = (
            bool(explicit_mutating)
            if isinstance(explicit_mutating, bool)
            else surface_kind in {"desktop", "document"}
        )
        app_family = self._first_string(preflight.get("app_family"))
        if app_family is None:
            if surface_kind == "browser":
                app_family = "browser_backoffice"
            elif surface_kind == "document" or mutating:
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
        surface_lookup = "desktop" if surface_kind == "document" else surface_kind
        surface = self._mapping(workspace_surfaces.get(surface_lookup))
        if surface_kind in {"desktop", "document"}:
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
        embedded_host_twin_summary = self._mapping(host_twin.get("host_twin_summary"))
        top_level_host_twin_summary = self._mapping(detail.get("host_twin_summary"))
        derived_host_twin_summary = build_host_twin_summary(
            host_twin,
            host_companion_session=self._mapping(detail.get("host_companion_session")),
        )
        host_twin_summary = {
            **dict(embedded_host_twin_summary or {}),
            **dict(derived_host_twin_summary or {}),
            **dict(top_level_host_twin_summary or {}),
        }
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
        recovery_status = self._first_string(recovery.get("status"))
        handoff_state = self._first_string(host_contract.get("handoff_state"))
        canonical_host_ready = self._canonical_host_summary_ready(host_twin_summary)
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
                        "desktop_app"
                        if surface_kind in {"desktop", "document"}
                        else surface_kind,
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

            if not canonical_host_ready:
                blockers.append(
                    WorkflowTemplateLaunchBlocker(
                        code="host-twin-continuity-invalid",
                        message=(
                            f"{surface_kind.capitalize()} host canonical summary indicates the writer path is not ready. "
                            f"{current_gap or 'Confirm canonical host readiness before launch.'}"
                        ),
                        agent_id=agent_id,
                        capability_ids=capability_ids,
                        step_ids=all_step_ids,
                    ),
                )

            if mutating_step_ids:
                access_mode = self._first_string(host_contract.get("access_mode"))
                execution_key = (
                    "desktop_app"
                    if surface_kind in {"desktop", "document"}
                    else "browser"
                )
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
                    if surface_kind in {"desktop", "document"}:
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
                    host_twin_summary.get("legal_recovery_mode"),
                    host_twin_legal_recovery.get("path"),
                    host_twin_legal_recovery.get("resume_kind"),
                )
                requires_human_return = bool(
                    host_twin_continuity.get("requires_human_return"),
                )
                recommended_scheduler_action = self._first_string(
                    host_twin_summary.get("recommended_scheduler_action"),
                    host_twin_coordination.get("recommended_scheduler_action"),
                    host_twin_scheduler.get("recommended_scheduler_action"),
                )
                canonical_host_ready = self._canonical_host_summary_ready(host_twin_summary)
                if canonical_host_ready:
                    writable_surface_available = True
                if (
                    not canonical_host_ready
                    and (
                        handoff_state in self._HOST_TWIN_HANDOFF_ONLY_STATES
                        or requires_human_return
                        or legal_recovery_path == "handoff"
                        or (
                            recovery_status == "same-host-other-process"
                            and not bool(recovery.get("recoverable"))
                        )
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

                blocking_families: set[str] = set()
                if not self._canonical_host_summary_overrides_live_blockers(
                    host_twin_summary,
                    active_alert_families=active_alert_families,
                    host_blocker=host_blocker,
                    host_twin_scheduler=host_twin_scheduler,
                ):
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
                    host_twin_summary.get("contention_severity"),
                    contention_forecast.get("severity"),
                )
                if (not canonical_host_ready) and (
                    contention_severity == "blocked"
                    or recommended_scheduler_action in self._HOST_TWIN_BLOCKING_RESPONSES
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
        capability_mounts_by_id: dict[str, Any | None] = {}
        installed_client_cache: dict[str, set[str]] = {}
        install_template_candidates_by_runtime: dict[bool, list[Any]] = {}
        install_templates_by_id: dict[str, Any | None] = {}
        installed_client_keys = self._list_installed_mcp_client_keys(
            cached_values=installed_client_cache,
        )

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
                if not self._has_capability(
                    capability_id,
                    capability_mounts_by_id=capability_mounts_by_id,
                )
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
                status = dependency_map.get(capability_id)
                if status is None:
                    mount = self._get_capability_mount(
                        capability_id,
                        capability_mounts_by_id=capability_mounts_by_id,
                    )
                    status = WorkflowTemplateDependencyStatus(
                        capability_id=capability_id,
                        installed=mount is not None,
                        enabled=mount.enabled if mount is not None else None,
                        available=bool(mount.enabled) if mount is not None else False,
                        install_templates=self._resolve_install_templates_for_capability(
                            template=template,
                            capability_id=capability_id,
                            installed_client_keys=installed_client_keys,
                            install_template_candidates_by_runtime=(
                                install_template_candidates_by_runtime
                            ),
                            install_templates_by_id=install_templates_by_id,
                            capability_mounts_by_id=capability_mounts_by_id,
                        ),
                    )
                    dependency_map[capability_id] = status
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
        agent_capability_surfaces_by_id: dict[str, dict[str, Any] | None] = {}

        self._prefetch_agent_capability_surfaces(
            sorted(required_capabilities_by_agent),
            agent_capability_surfaces_by_id=agent_capability_surfaces_by_id,
            capability_mounts_by_id=capability_mounts_by_id,
        )

        for agent_id, required_capabilities in required_capabilities_by_agent.items():
            capability_surface = self._get_agent_capability_surface(
                agent_id,
                agent_capability_surfaces_by_id=agent_capability_surfaces_by_id,
                capability_mounts_by_id=capability_mounts_by_id,
            )
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
                if capability_id not in assigned_capabilities
                and self._has_capability(
                    capability_id,
                    capability_mounts_by_id=capability_mounts_by_id,
                )
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
