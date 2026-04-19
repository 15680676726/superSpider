# -*- coding: utf-8 -*-
"""Kernel persistence backed by the unified state/evidence layer.

This store intentionally avoids creating a second kernel-only SQLite truth
source. Kernel task state is persisted into the Phase 1 state repositories,
while evidence and confirmation requests flow through the shared ledgers.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..evidence import ArtifactRecord, EvidenceLedger, EvidenceRecord, ReplayPointer
from ..state import (
    DecisionRequestRecord,
    RuntimeFrameRecord,
    TaskRecord,
    TaskRuntimeRecord,
    WorkContextService,
)
from ..state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteRuntimeFrameRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)
from .decision_policy import decision_requested_by
from .models import KernelTask, TaskPhase

_KERNEL_META_MARKER = "kernel-task-meta-v1"
_TERMINAL_PHASES = frozenset({"completed", "failed", "cancelled"})


class KernelTaskStore:
    """Persist kernel tasks into the unified state/evidence layer."""

    def __init__(
        self,
        *,
        task_repository: SqliteTaskRepository,
        task_runtime_repository: SqliteTaskRuntimeRepository,
        runtime_frame_repository: SqliteRuntimeFrameRepository | None = None,
        decision_request_repository: SqliteDecisionRequestRepository | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        runtime_event_bus: Any | None = None,
        work_context_service: WorkContextService | None = None,
    ) -> None:
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._runtime_frame_repository = runtime_frame_repository
        self._decision_request_repository = decision_request_repository
        self._evidence_ledger = evidence_ledger
        self._runtime_event_bus = runtime_event_bus
        self._work_context_service = work_context_service

    def upsert(
        self,
        task: KernelTask,
        *,
        last_result_summary: str | None = None,
        last_error_summary: str | None = None,
        last_evidence_id: str | None = None,
    ) -> None:
        existing_task = self._task_repository.get_task(task.id)
        existing_runtime = self._task_runtime_repository.get_runtime(task.id)
        task = self._resolve_task_work_context(task, existing=existing_task)

        task_record = self._build_task_record(task, existing=existing_task)
        runtime_record = self._build_runtime_record(
            task,
            existing=existing_runtime,
            last_result_summary=last_result_summary,
            last_error_summary=last_error_summary,
            last_evidence_id=last_evidence_id,
        )

        self._task_repository.upsert_task(task_record)
        self._task_runtime_repository.upsert_runtime(runtime_record)
        self._append_frame_if_needed(
            task,
            existing_runtime=existing_runtime,
            runtime_record=runtime_record,
        )
        self._publish_runtime_event(
            topic="task",
            action=(
                "accepted"
                if existing_task is None
                else task.phase
                if existing_runtime is None or existing_runtime.current_phase != task.phase
                else "updated"
            ),
            payload={
                "task_id": task.id,
                "trace_id": task.trace_id,
                "goal_id": task.goal_id,
                "title": task.title,
                "phase": task.phase,
                "risk_level": task.risk_level,
                "capability_ref": task.capability_ref,
                "environment_ref": task.environment_ref,
                "owner_agent_id": task.owner_agent_id,
                "work_context_id": task.work_context_id,
                "last_evidence_id": last_evidence_id,
            },
        )

    def get(self, task_id: str) -> KernelTask | None:
        task_record = self._task_repository.get_task(task_id)
        if task_record is None:
            return None

        runtime_record = self._task_runtime_repository.get_runtime(task_id)
        return self._task_from_records(task_record, runtime_record)

    def get_runtime_record(self, task_id: str) -> TaskRuntimeRecord | None:
        return self._task_runtime_repository.get_runtime(task_id)

    def list_tasks(
        self,
        *,
        phase: str | None = None,
        owner_agent_id: str | None = None,
        limit: int = 200,
    ) -> list[KernelTask]:
        task_records = self._task_repository.list_tasks(
            owner_agent_id=owner_agent_id,
            status=_task_status_for_phase(phase) if phase is not None else None,
            acceptance_criteria_like=_KERNEL_META_MARKER,
        )
        if not task_records:
            return []

        runtime_records = self._task_runtime_repository.list_runtimes(
            task_ids=[record.id for record in task_records],
        )
        runtime_map = {
            runtime.task_id: runtime
            for runtime in runtime_records
        }

        tasks: list[KernelTask] = []
        for task_record in task_records:
            task = self._task_from_records(
                task_record,
                runtime_map.get(task_record.id),
            )
            if task is None:
                continue
            if phase is not None and task.phase != phase:
                continue
            tasks.append(task)
        tasks.sort(key=lambda item: item.updated_at, reverse=True)
        return tasks[:limit]

    def list_child_tasks(
        self,
        *,
        parent_task_id: str,
        limit: int = 200,
    ) -> list[KernelTask]:
        task_records = self._task_repository.list_tasks(parent_task_id=parent_task_id)
        if not task_records:
            return []
        runtime_records = self._task_runtime_repository.list_runtimes(
            task_ids=[record.id for record in task_records],
        )
        runtime_map = {
            runtime.task_id: runtime
            for runtime in runtime_records
        }
        tasks = [
            task
            for task in (
                self._task_from_records(task_record, runtime_map.get(task_record.id))
                for task_record in task_records
            )
            if task is not None
        ]
        tasks.sort(key=lambda item: item.updated_at, reverse=True)
        return tasks[:limit]

    def list_decision_requests(
        self,
        *,
        task_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[DecisionRequestRecord]:
        if self._decision_request_repository is None:
            return []
        return self._decision_request_repository.list_decision_requests(
            task_id=task_id,
            status=status,
            limit=limit,
        )

    def get_decision_request(self, decision_id: str) -> DecisionRequestRecord | None:
        if self._decision_request_repository is None:
            return None
        return self._decision_request_repository.get_decision_request(decision_id)

    def ensure_decision_request(
        self,
        task: KernelTask,
        *,
        expires_at: datetime | None = None,
        requested_by: str | None = None,
    ) -> DecisionRequestRecord | None:
        if self._decision_request_repository is None:
            return None
        candidates = self._decision_request_repository.list_decision_requests(
            task_id=task.id,
        )
        pending = [
            decision
            for decision in candidates
            if decision.status in {"open", "reviewing"}
        ]
        if pending:
            return pending[0]

        task_payload = task.payload if isinstance(task.payload, dict) else {}
        decision_type = _non_empty_str(task_payload.get("decision_type")) or "kernel-confirmation"
        summary = _non_empty_str(task_payload.get("decision_summary"))
        decision = DecisionRequestRecord(
            task_id=task.id,
            decision_type=decision_type,
            risk_level=task.risk_level,
            summary=summary or f"Approve kernel task '{task.title}' before execution.",
            requested_by=requested_by or decision_requested_by(task),
            expires_at=expires_at,
        )
        self._decision_request_repository.upsert_decision_request(decision)
        self._publish_runtime_event(
            topic="decision",
            action="open",
            payload={
                "decision_id": decision.id,
                "task_id": decision.task_id,
                "trace_id": task.trace_id,
                "status": decision.status,
                "risk_level": decision.risk_level,
                "summary": decision.summary,
            },
        )
        return decision

    def resolve_open_decisions(
        self,
        *,
        task_id: str,
        status: str,
        resolution: str,
    ) -> list[DecisionRequestRecord]:
        if self._decision_request_repository is None:
            return []
        task = self.get(task_id)
        resolved: list[DecisionRequestRecord] = []
        for decision in self._decision_request_repository.list_decision_requests(
            task_id=task_id,
        ):
            if decision.status not in {"open", "reviewing"}:
                continue
            updated = decision.model_copy(
                update={
                    "status": status,
                    "resolution": resolution,
                    "resolved_at": datetime.now(timezone.utc),
                },
            )
            persisted = self._decision_request_repository.upsert_decision_request(updated)
            self._publish_runtime_event(
                topic="decision",
                action=status,
                payload={
                    "decision_id": persisted.id,
                    "task_id": persisted.task_id,
                    "trace_id": task.trace_id if task is not None else None,
                    "status": persisted.status,
                    "resolution": persisted.resolution,
                },
            )
            resolved.append(persisted)
        return resolved

    def resolve_decision_request(
        self,
        decision_id: str,
        *,
        status: str,
        resolution: str,
    ) -> DecisionRequestRecord | None:
        if self._decision_request_repository is None:
            return None
        decision = self._decision_request_repository.get_decision_request(decision_id)
        if decision is None:
            return None
        task = self.get(decision.task_id)
        updated = decision.model_copy(
            update={
                "status": status,
                "resolution": resolution,
                "resolved_at": datetime.now(timezone.utc),
            },
        )
        persisted = self._decision_request_repository.upsert_decision_request(updated)
        self._publish_runtime_event(
            topic="decision",
            action=status,
            payload={
                "decision_id": persisted.id,
                "task_id": persisted.task_id,
                "trace_id": task.trace_id if task is not None else None,
                "status": persisted.status,
                "resolution": persisted.resolution,
            },
        )
        return persisted

    def mark_decision_reviewing(
        self,
        decision_id: str,
    ) -> DecisionRequestRecord | None:
        if self._decision_request_repository is None:
            return None
        decision = self._decision_request_repository.get_decision_request(decision_id)
        if decision is None:
            return None
        if decision.status != "open":
            return decision
        task = self.get(decision.task_id)
        updated = decision.model_copy(update={"status": "reviewing"})
        persisted = self._decision_request_repository.upsert_decision_request(updated)
        self._publish_runtime_event(
            topic="decision",
            action="reviewing",
            payload={
                "decision_id": persisted.id,
                "task_id": persisted.task_id,
                "trace_id": task.trace_id if task is not None else None,
                "status": persisted.status,
            },
        )
        return persisted

    def expire_decision_request(
        self,
        decision_id: str,
        *,
        resolution: str,
    ) -> DecisionRequestRecord | None:
        if self._decision_request_repository is None:
            return None
        decision = self._decision_request_repository.get_decision_request(decision_id)
        if decision is None:
            return None
        if decision.status in {"approved", "rejected", "expired"}:
            return decision
        task = self.get(decision.task_id)
        updated = decision.model_copy(
            update={
                "status": "expired",
                "resolution": resolution,
                "resolved_at": datetime.now(timezone.utc),
            },
        )
        persisted = self._decision_request_repository.upsert_decision_request(updated)
        self._publish_runtime_event(
            topic="decision",
            action="expired",
            payload={
                "decision_id": persisted.id,
                "task_id": persisted.task_id,
                "trace_id": task.trace_id if task is not None else None,
                "status": persisted.status,
                "resolution": persisted.resolution,
            },
        )
        return persisted

    def append_evidence(
        self,
        task: KernelTask,
        *,
        kind: str | None = None,
        action_summary: str,
        result_summary: str,
        status: str = "recorded",
        metadata: dict[str, Any] | None = None,
        actor_ref: str | None = None,
        capability_ref: str | None = None,
        environment_ref: str | None = None,
        artifacts: tuple[ArtifactRecord, ...] | None = None,
        replay_pointers: tuple[ReplayPointer, ...] | None = None,
    ) -> EvidenceRecord | None:
        if self._evidence_ledger is None:
            return None
        merged_metadata = {
            **(metadata or {}),
            "trace_id": task.trace_id,
            "trace_task_id": task.id,
            "trace_owner_agent_id": task.owner_agent_id,
            "work_context_id": task.work_context_id,
        }
        record = self._evidence_ledger.append(
            EvidenceRecord(
                task_id=task.id,
                actor_ref=actor_ref or "kernel:dispatcher",
                environment_ref=environment_ref or task.environment_ref,
                capability_ref=capability_ref or task.capability_ref,
                risk_level=task.risk_level,
                kind=kind or "generic",
                action_summary=action_summary,
                result_summary=result_summary,
                status=status,
                metadata=merged_metadata,
                artifacts=artifacts or (),
                replay_pointers=replay_pointers or (),
            ),
        )
        self._publish_runtime_event(
            topic="evidence",
            action="recorded",
            payload={
                "evidence_id": record.id,
                "task_id": task.id,
                "trace_id": task.trace_id,
                "work_context_id": task.work_context_id,
                "capability_ref": capability_ref or task.capability_ref,
                "environment_ref": environment_ref or task.environment_ref,
                "status": status,
            },
        )
        return record

    def _resolve_task_work_context(
        self,
        task: KernelTask,
        *,
        existing: TaskRecord | None,
    ) -> KernelTask:
        descriptor = _task_work_context_descriptor(task)
        explicit_context_id = _non_empty_str(
            task.work_context_id,
            descriptor.get("work_context_id"),
        )
        if explicit_context_id is not None:
            ensured = self._ensure_work_context(
                task,
                existing=existing,
                context_id=explicit_context_id,
                descriptor=descriptor,
            )
            if ensured is None or ensured == task.work_context_id:
                return task
            return task.model_copy(update={"work_context_id": ensured})

        explicit_context_key = _non_empty_str(descriptor.get("context_key"))
        if explicit_context_key is not None:
            ensured = self._ensure_work_context(
                task,
                existing=existing,
                context_key=explicit_context_key,
                descriptor=descriptor,
            )
            if ensured is None or ensured == task.work_context_id:
                return task
            return task.model_copy(update={"work_context_id": ensured})

        existing_work_context_id = (
            _non_empty_str(existing.work_context_id) if existing is not None else None
        )
        if existing_work_context_id is not None:
            if existing_work_context_id == task.work_context_id:
                return task
            return task.model_copy(update={"work_context_id": existing_work_context_id})

        parent_work_context_id = None
        if task.parent_task_id:
            parent_task = self._task_repository.get_task(task.parent_task_id)
            parent_work_context_id = (
                _non_empty_str(parent_task.work_context_id)
                if parent_task is not None
                else None
            )
        if parent_work_context_id is not None:
            return task.model_copy(update={"work_context_id": parent_work_context_id})
        return task

    def _ensure_work_context(
        self,
        task: KernelTask,
        *,
        existing: TaskRecord | None,
        descriptor: dict[str, Any],
        context_id: str | None = None,
        context_key: str | None = None,
    ) -> str | None:
        service = self._work_context_service
        resolved_context_id = _non_empty_str(context_id)
        if service is None:
            return resolved_context_id
        runtime_context = _task_runtime_context(task)
        stored = service.ensure_context(
            context_id=resolved_context_id,
            context_key=_non_empty_str(context_key),
            title=(
                _non_empty_str(descriptor.get("title"), task.title)
                or "Work Context"
            ),
            summary=_non_empty_str(
                descriptor.get("summary"),
                _task_summary(task),
            )
            or "",
            context_type=_non_empty_str(descriptor.get("context_type")) or "generic",
            owner_scope=_non_empty_str(
                descriptor.get("owner_scope"),
                runtime_context.get("owner_scope"),
            ),
            owner_agent_id=task.owner_agent_id,
            industry_instance_id=_non_empty_str(
                descriptor.get("industry_instance_id"),
                runtime_context.get("industry_instance_id"),
                existing.industry_instance_id if existing is not None else None,
            ),
            primary_thread_id=_non_empty_str(descriptor.get("primary_thread_id")),
            source_kind=_non_empty_str(descriptor.get("source_kind")),
            source_ref=_non_empty_str(descriptor.get("source_ref"), task.id),
            parent_work_context_id=_non_empty_str(descriptor.get("parent_work_context_id")),
            metadata={
                **_task_work_context_metadata(task),
                **dict(descriptor.get("metadata") or {}),
            },
        )
        return stored.id

    def _build_task_record(
        self,
        task: KernelTask,
        *,
        existing: TaskRecord | None,
    ) -> TaskRecord:
        now = task.updated_at
        encoded_meta = _encode_kernel_metadata(
            task,
            existing_acceptance_criteria=(
                existing.acceptance_criteria if existing is not None else None
            ),
        )
        seed_source = _task_seed_source(task)
        constraints_summary = _task_constraints_summary(task)
        runtime_context = _task_runtime_context(task)
        if existing is None:
            return TaskRecord(
                id=task.id,
                goal_id=task.goal_id,
                parent_task_id=task.parent_task_id,
                work_context_id=task.work_context_id,
                title=task.title,
                summary=_task_summary(task),
                task_type=task.capability_ref or "kernel-task",
                status=_task_status_for_phase(task.phase),
                owner_agent_id=task.owner_agent_id,
                seed_source=seed_source,
                constraints_summary=constraints_summary,
                acceptance_criteria=encoded_meta,
                current_risk_level=task.risk_level,
                industry_instance_id=_non_empty_str(runtime_context.get("industry_instance_id")),
                assignment_id=_non_empty_str(runtime_context.get("assignment_id")),
                lane_id=_non_empty_str(runtime_context.get("lane_id")),
                cycle_id=_non_empty_str(runtime_context.get("cycle_id")),
                report_back_mode=_non_empty_str(runtime_context.get("report_back_mode")) or "summary",
                created_at=task.created_at,
                updated_at=now,
            )

        return existing.model_copy(
            update={
                "goal_id": task.goal_id or existing.goal_id,
                "parent_task_id": task.parent_task_id or existing.parent_task_id,
                "work_context_id": task.work_context_id or existing.work_context_id,
                "title": task.title or existing.title,
                "summary": _task_summary(task),
                "task_type": existing.task_type or task.capability_ref or "kernel-task",
                "status": _task_status_for_phase(task.phase),
                "owner_agent_id": task.owner_agent_id or existing.owner_agent_id,
                "seed_source": seed_source or existing.seed_source,
                "constraints_summary": constraints_summary,
                "acceptance_criteria": encoded_meta,
                "current_risk_level": task.risk_level,
                "industry_instance_id": (
                    _non_empty_str(runtime_context.get("industry_instance_id"))
                    or existing.industry_instance_id
                ),
                "assignment_id": (
                    _non_empty_str(runtime_context.get("assignment_id"))
                    or existing.assignment_id
                ),
                "lane_id": _non_empty_str(runtime_context.get("lane_id")) or existing.lane_id,
                "cycle_id": _non_empty_str(runtime_context.get("cycle_id")) or existing.cycle_id,
                "report_back_mode": (
                    _non_empty_str(runtime_context.get("report_back_mode"))
                    or existing.report_back_mode
                ),
                "updated_at": now,
            },
        )

    def _build_runtime_record(
        self,
        task: KernelTask,
        *,
        existing: TaskRuntimeRecord | None,
        last_result_summary: str | None,
        last_error_summary: str | None,
        last_evidence_id: str | None,
    ) -> TaskRuntimeRecord:
        if existing is None:
            return TaskRuntimeRecord(
                task_id=task.id,
                runtime_status=_runtime_status_for_phase(task.phase),
                current_phase=task.phase,
                risk_level=task.risk_level,
                active_environment_id=task.environment_ref,
                last_result_summary=last_result_summary,
                last_error_summary=last_error_summary,
                last_owner_agent_id=task.owner_agent_id,
                last_evidence_id=last_evidence_id,
                updated_at=task.updated_at,
            )

        return existing.model_copy(
            update={
                "runtime_status": _runtime_status_for_phase(task.phase),
                "current_phase": task.phase,
                "risk_level": task.risk_level,
                "active_environment_id": task.environment_ref or existing.active_environment_id,
                "last_result_summary": (
                    last_result_summary
                    if last_result_summary is not None
                    else existing.last_result_summary
                ),
                "last_error_summary": (
                    last_error_summary
                    if last_error_summary is not None
                    else existing.last_error_summary
                ),
                "last_owner_agent_id": task.owner_agent_id,
                "last_evidence_id": (
                    last_evidence_id
                    if last_evidence_id is not None
                    else existing.last_evidence_id
                ),
                "updated_at": task.updated_at,
            },
        )

    def _append_frame_if_needed(
        self,
        task: KernelTask,
        *,
        existing_runtime: TaskRuntimeRecord | None,
        runtime_record: TaskRuntimeRecord,
    ) -> None:
        if self._runtime_frame_repository is None:
            return
        if existing_runtime is not None:
            same_phase = existing_runtime.current_phase == runtime_record.current_phase
            same_result = existing_runtime.last_result_summary == runtime_record.last_result_summary
            same_error = existing_runtime.last_error_summary == runtime_record.last_error_summary
            same_evidence = existing_runtime.last_evidence_id == runtime_record.last_evidence_id
            if same_phase and same_result and same_error and same_evidence:
                return

        self._runtime_frame_repository.append_frame(
            RuntimeFrameRecord(
                task_id=task.id,
                goal_summary="Kernel dispatcher",
                owner_agent_id=task.owner_agent_id,
                current_phase=task.phase,
                current_risk_level=task.risk_level,
                environment_summary=task.environment_ref or "kernel-task",
                evidence_summary=(
                    runtime_record.last_result_summary
                    or runtime_record.last_error_summary
                    or "Kernel state transition recorded."
                ),
                capabilities_summary=task.capability_ref,
            ),
        )

    def _publish_runtime_event(
        self,
        *,
        topic: str,
        action: str,
        payload: dict[str, Any],
    ) -> None:
        if self._runtime_event_bus is None:
            return
        self._runtime_event_bus.publish(
            topic=topic,
            action=action,
            payload=payload,
        )

    def _task_from_records(
        self,
        task_record: TaskRecord,
        runtime_record: TaskRuntimeRecord | None,
    ) -> KernelTask | None:
        meta = decode_kernel_task_metadata(task_record.acceptance_criteria)
        if meta is None:
            return None

        phase = _normalize_phase(
            runtime_record.current_phase if runtime_record is not None else None,
            fallback=_phase_from_task_status(task_record.status),
        )
        environment_ref = (
            runtime_record.active_environment_id
            if runtime_record is not None and runtime_record.active_environment_id
            else str(meta.get("environment_ref") or "") or None
        )
        payload = meta.get("payload")
        payload = dict(payload) if isinstance(payload, dict) else {}
        capability_ref = str(meta.get("capability_ref") or "") or None

        goal_id = task_record.goal_id
        if goal_id is None:
            meta_goal = meta.get("goal_id")
            if isinstance(meta_goal, str) and meta_goal:
                goal_id = meta_goal

        return KernelTask(
            id=task_record.id,
            trace_id=_decode_trace_id(
                task_record.id,
                meta=meta,
                payload=payload,
            ),
            goal_id=goal_id,
            parent_task_id=task_record.parent_task_id,
            work_context_id=_non_empty_str(
                task_record.work_context_id,
                meta.get("work_context_id"),
            ),
            title=task_record.title,
            capability_ref=capability_ref,
            environment_ref=environment_ref,
            owner_agent_id=task_record.owner_agent_id or "copaw-agent-runner",
            actor_owner_id=(
                str(meta.get("actor_owner_id"))
                if isinstance(meta.get("actor_owner_id"), str)
                else None
            ),
            phase=phase,
            risk_level=(
                runtime_record.risk_level
                if runtime_record is not None
                else task_record.current_risk_level
            ),
            task_segment=_task_payload_mapping(
                meta.get("task_segment"),
                payload.get("task_segment"),
            ),
            resume_point=_task_payload_mapping(
                meta.get("resume_point"),
                payload.get("resume_point"),
            ),
            payload=payload,
            created_at=task_record.created_at,
            updated_at=(
                runtime_record.updated_at
                if runtime_record is not None
                else (task_record.updated_at or task_record.created_at)
            ),
        )


def _encode_kernel_metadata(
    task: KernelTask,
    *,
    existing_acceptance_criteria: str | None,
) -> str:
    existing_meta = decode_kernel_task_metadata(existing_acceptance_criteria)
    legacy_acceptance_criteria: str | None = None
    if existing_meta is not None:
        legacy_value = existing_meta.get("legacy_acceptance_criteria")
        if isinstance(legacy_value, str) and legacy_value:
            legacy_acceptance_criteria = legacy_value
    elif existing_acceptance_criteria:
        legacy_acceptance_criteria = existing_acceptance_criteria

    payload: dict[str, Any] = {
        "kind": _KERNEL_META_MARKER,
        "trace_id": task.trace_id,
        "capability_ref": task.capability_ref,
        "environment_ref": task.environment_ref,
        "goal_id": task.goal_id,
        "parent_task_id": task.parent_task_id,
        "work_context_id": task.work_context_id,
        "actor_owner_id": task.actor_owner_id,
        "task_segment": task.task_segment,
        "resume_point": task.resume_point,
        "payload": task.payload,
    }
    if legacy_acceptance_criteria:
        payload["legacy_acceptance_criteria"] = legacy_acceptance_criteria
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def encode_kernel_task_metadata(
    task: KernelTask,
    *,
    existing_acceptance_criteria: str | None = None,
) -> str:
    """Serialize a kernel task into the unified acceptance_criteria payload."""

    return _encode_kernel_metadata(
        task,
        existing_acceptance_criteria=existing_acceptance_criteria,
    )


def decode_kernel_task_metadata(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("kind") != _KERNEL_META_MARKER:
        return None
    return payload


def _decode_trace_id(
    task_id: str,
    *,
    meta: dict[str, Any],
    payload: dict[str, Any],
) -> str:
    for value in (meta.get("trace_id"), payload.get("trace_id")):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"trace:{task_id}"


def _task_summary(task: KernelTask) -> str:
    preview = _task_preview(task)
    if preview:
        return preview
    capability_ref = task.capability_ref or "kernel-task"
    if task.environment_ref:
        return f"Kernel-managed task for {capability_ref} on {task.environment_ref}."
    return f"Kernel-managed task for {capability_ref}."


def _non_empty_str(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None


def _task_seed_source(task: KernelTask) -> str:
    meta = _task_meta(task)
    source_kind = str(meta.get("source_kind") or "kernel")
    unit_kind = str(meta.get("unit_kind") or "task")
    unit_id = str(meta.get("unit_id") or task.id)
    return f"{source_kind}:{unit_kind}:{unit_id}"


def _task_constraints_summary(task: KernelTask) -> str | None:
    meta = _task_meta(task)
    compiler = _task_payload_mapping(task.payload.get("compiler"))
    request = _task_payload_mapping(task.payload.get("request"))
    task_segment = _task_payload_mapping(meta.get("task_segment"), task.task_segment)
    resume_point = _task_payload_mapping(meta.get("resume_point"), task.resume_point)
    segment_index = task_segment.get("index")
    segment_total = task_segment.get("total")
    segment_summary: str | None = None
    if isinstance(segment_index, int) and isinstance(segment_total, int):
        segment_summary = f"{segment_index + 1}/{segment_total}"
    elif (
        isinstance(segment_index, str)
        and segment_index.isdigit()
        and isinstance(segment_total, str)
        and segment_total.isdigit()
    ):
        segment_summary = f"{int(segment_index) + 1}/{int(segment_total)}"
    parts = [
        f"unit_kind={meta.get('unit_kind')}" if meta.get("unit_kind") else None,
        f"goal_id={meta.get('goal_id')}" if meta.get("goal_id") else None,
        (
            f"parent_task_id={task.parent_task_id}"
            if task.parent_task_id
            else None
        ),
        (
            f"actor_owner_id={meta.get('actor_owner_id')}"
            if meta.get("actor_owner_id")
            else None
        ),
        (
            f"segment={task_segment.get('segment_kind')}@{segment_summary}"
            if task_segment.get("segment_kind") and segment_summary
            else (
                f"segment={task_segment.get('segment_kind')}"
                if task_segment.get("segment_kind")
                else None
            )
        ),
        (
            f"resume_phase={resume_point.get('phase')}"
            if resume_point.get("phase")
            else None
        ),
        (
            f"plan_step={compiler.get('step_text')}"
            if compiler.get("step_text")
            else None
        ),
        (
            f"channel={request.get('channel')}"
            if request.get("channel")
            else None
        ),
    ]
    values = [str(part) for part in parts if part]
    return "; ".join(values) if values else None


def _task_preview(task: KernelTask) -> str | None:
    compiler = _task_payload_mapping(task.payload.get("compiler"))
    if isinstance(compiler.get("prompt_text"), str) and compiler["prompt_text"].strip():
        return compiler["prompt_text"].strip()[:280]

    request = _task_payload_mapping(task.payload.get("request"))
    inputs = request.get("input")
    if isinstance(inputs, list):
        for item in inputs:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "text":
                    continue
                text = str(part.get("text") or "").strip()
                if text:
                    return text[:280]
    return None


def _task_meta(task: KernelTask) -> dict[str, Any]:
    payload_meta = _task_payload_mapping(task.payload.get("meta"))
    compiler = _task_payload_mapping(task.payload.get("compiler"))
    return {
        **payload_meta,
        **compiler,
    }


def _task_runtime_context(task: KernelTask) -> dict[str, Any]:
    request_context = _task_payload_mapping(
        task.payload.get("request_context"),
        _task_payload_mapping(task.payload.get("task_seed")).get("request_context"),
        _task_payload_mapping(task.payload.get("meta")).get("request_context"),
        _task_meta(task).get("request_context"),
    )
    context: dict[str, Any] = dict(request_context)
    for key in (
        "industry_instance_id",
        "assignment_id",
        "lane_id",
        "cycle_id",
        "report_back_mode",
        "task_mode",
    ):
        value = task.payload.get(key)
        if value is None:
            value = _task_meta(task).get(key)
        if value is None:
            continue
        context[key] = value
    return context


def _task_payload_mapping(*values: object) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return dict(value)
    return {}


def _task_work_context_descriptor(task: KernelTask) -> dict[str, Any]:
    payload = _task_payload_mapping(task.payload)
    request = _task_payload_mapping(payload.get("request"))
    meta = _task_meta(task)
    runtime_context = _task_runtime_context(task)
    request_context = _task_payload_mapping(runtime_context.get("request_context"))

    def pick(*keys: str) -> str | None:
        for source in (payload, request, meta, runtime_context, request_context):
            for key in keys:
                value = _non_empty_str(source.get(key))
                if value is not None:
                    return value
        return None

    control_thread_id = pick("control_thread_id")
    request_session_id = pick("session_id")
    session_kind = pick("session_kind")
    context_key = pick("work_context_key", "context_key")
    source_kind = pick("work_context_source_kind", "context_source_kind")
    source_ref = pick("work_context_source_ref", "context_source_ref")
    primary_thread_id = pick("primary_thread_id")
    if primary_thread_id is None:
        primary_thread_id = _non_empty_str(
            control_thread_id,
            request_session_id,
        )
    context_type = pick("work_context_type", "context_type")
    if context_type is None:
        if control_thread_id is not None:
            context_type = "chat-thread"
        elif task.parent_task_id:
            context_type = "delegation"
        else:
            context_type = "task"
    return {
        "work_context_id": pick("work_context_id", "context_id"),
        "context_key": context_key,
        "title": pick("work_context_title", "context_title", "task_title") or task.title,
        "summary": pick("work_context_summary", "context_summary") or _task_summary(task),
        "context_type": context_type,
        "owner_scope": pick("owner_scope"),
        "industry_instance_id": pick("industry_instance_id"),
        "primary_thread_id": primary_thread_id,
        "source_kind": source_kind,
        "source_ref": source_ref or task.id,
        "parent_work_context_id": pick("parent_work_context_id"),
        "metadata": {
            "control_thread_id": control_thread_id,
            "session_id": request_session_id,
            "session_kind": session_kind,
        },
    }


def _task_work_context_metadata(task: KernelTask) -> dict[str, Any]:
    runtime_context = _task_runtime_context(task)
    return {
        "task_id": task.id,
        "goal_id": task.goal_id,
        "parent_task_id": task.parent_task_id,
        "capability_ref": task.capability_ref,
        "environment_ref": task.environment_ref,
        "owner_agent_id": task.owner_agent_id,
        "industry_instance_id": _non_empty_str(runtime_context.get("industry_instance_id")),
        "assignment_id": _non_empty_str(runtime_context.get("assignment_id")),
        "lane_id": _non_empty_str(runtime_context.get("lane_id")),
        "cycle_id": _non_empty_str(runtime_context.get("cycle_id")),
    }


def _task_status_for_phase(phase: TaskPhase) -> str:
    mapping = {
        "pending": "queued",
        "risk-check": "queued",
        "executing": "running",
        "waiting-confirm": "needs-confirm",
        "completed": "completed",
        "failed": "failed",
        "cancelled": "cancelled",
    }
    return mapping.get(phase, "queued")


def _runtime_status_for_phase(phase: TaskPhase) -> str:
    mapping = {
        "pending": "cold",
        "risk-check": "hydrating",
        "executing": "active",
        "waiting-confirm": "waiting-confirm",
        "completed": "terminated",
        "failed": "terminated",
        "cancelled": "terminated",
    }
    return mapping.get(phase, "cold")


def _phase_from_task_status(status: str | None) -> TaskPhase:
    mapping: dict[str, TaskPhase] = {
        "created": "pending",
        "queued": "risk-check",
        "running": "executing",
        "waiting": "waiting-confirm",
        "blocked": "waiting-confirm",
        "needs-confirm": "waiting-confirm",
        "completed": "completed",
        "failed": "failed",
        "cancelled": "cancelled",
    }
    return mapping.get(str(status or ""), "pending")


def _normalize_phase(value: str | None, *, fallback: TaskPhase) -> TaskPhase:
    allowed = {
        "pending",
        "risk-check",
        "executing",
        "waiting-confirm",
        "completed",
        "failed",
        "cancelled",
    }
    if value in allowed:
        return value  # type: ignore[return-value]
    return fallback
