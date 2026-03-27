# -*- coding: utf-8 -*-
"""Focused tests for the Runtime Center operator surface API."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.crons.api import router as cron_router
from copaw.app.crons.models import (
    CronJobSpec,
    CronJobState,
    DispatchSpec,
    DispatchTarget,
    ScheduleSpec,
)
from copaw.app.routers.routines import router as routines_router
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.capabilities import CapabilityService
from copaw.config.config import HeartbeatConfig
from copaw.environments.models import (
    ArtifactEntry,
    EnvironmentMount,
    EnvironmentSummary,
    ObservationRecord,
    ReplayEntry,
    SessionMount,
)
from copaw.evidence import EvidenceLedger
from copaw.kernel import KernelResult
from copaw.kernel import KernelDispatcher
from copaw.routines import (
    RoutineCreateFromEvidenceRequest,
    RoutineCreateRequest,
    RoutineDetail,
    RoutineDiagnosis,
    RoutineReplayRequest,
    RoutineReplayResponse,
    RoutineRunDetail,
    RoutineService,
)
from copaw.state import DecisionRequestRecord, ExecutionRoutineRecord, RoutineRunRecord

class FakeCronManager:
    def __init__(
        self,
        jobs: list[CronJobSpec],
        states: dict[str, CronJobState] | None = None,
        heartbeat_state: CronJobState | None = None,
    ) -> None:
        self._jobs = list(jobs)
        self._states = states or {}
        self._heartbeat_state = heartbeat_state or CronJobState()
        self.heartbeat_rescheduled = False

    async def list_jobs(self) -> list[CronJobSpec]:
        return self._jobs

    async def get_job(self, job_id: str) -> CronJobSpec | None:
        for job in self._jobs:
            if job.id == job_id:
                return job
        return None

    def get_state(self, job_id: str) -> CronJobState:
        return self._states.get(job_id, CronJobState())

    def get_heartbeat_state(self) -> CronJobState:
        return self._heartbeat_state

    async def reschedule_heartbeat(self) -> None:
        self.heartbeat_rescheduled = True
        self._heartbeat_state = self._heartbeat_state.model_copy(
            update={
                "next_run_at": datetime(2026, 3, 10, 8, 30, tzinfo=timezone.utc),
            },
        )

    async def run_heartbeat(self, *, ignore_active_hours: bool = True) -> dict[str, object]:
        _ = ignore_active_hours
        self._heartbeat_state = self._heartbeat_state.model_copy(
            update={
                "last_status": "success",
                "last_run_at": datetime(2026, 3, 9, 9, 0, tzinfo=timezone.utc),
                "next_run_at": datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc),
                "last_error": None,
            },
        )
        return {
            "status": "success",
            "task_id": "ktask:heartbeat",
            "query_path": "D:/word/copaw/HEARTBEAT.md",
        }

    async def create_or_replace_job(self, spec: CronJobSpec) -> None:
        for index, job in enumerate(self._jobs):
            if job.id == spec.id:
                self._jobs[index] = spec
                break
        else:
            self._jobs.append(spec)
        self._states.setdefault(spec.id, CronJobState())

    async def delete_job(self, job_id: str) -> bool:
        original = len(self._jobs)
        self._jobs = [job for job in self._jobs if job.id != job_id]
        self._states.pop(job_id, None)
        return len(self._jobs) != original

    async def pause_job(self, job_id: str) -> None:
        job = await self.get_job(job_id)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")
        await self.create_or_replace_job(job.model_copy(update={"enabled": False}))

    async def resume_job(self, job_id: str) -> None:
        job = await self.get_job(job_id)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")
        await self.create_or_replace_job(job.model_copy(update={"enabled": True}))

    async def run_job(self, job_id: str) -> None:
        job = await self.get_job(job_id)
        if job is None:
            raise KeyError(f"Job not found: {job_id}")
        self._states[job.id] = self.get_state(job.id).model_copy(
            update={"last_status": "running"},
        )


class FakeScheduleStateQueryService:
    def __init__(self, manager: FakeCronManager) -> None:
        self._manager = manager

    async def list_schedules(self, limit: int | None = 5):
        jobs = await self._manager.list_jobs()
        selected = jobs if limit is None else jobs[:limit]
        return [self._serialize_schedule_summary(job) for job in selected]

    async def get_schedule_detail(self, schedule_id: str):
        job = await self._manager.get_job(schedule_id)
        if job is None:
            return None
        route = f"/api/runtime-center/schedules/{job.id}"
        status = self._status_for(job)
        actions = {"run": f"{route}/run", "delete": route}
        if status == "paused" or job.enabled is False:
            actions["resume"] = f"{route}/resume"
        else:
            actions["pause"] = f"{route}/pause"
        state = self._manager.get_state(job.id)
        return {
            "schedule": {
                "id": job.id,
                "title": job.name,
                "status": status,
                "enabled": job.enabled,
                "cron": job.schedule.cron,
                "timezone": job.schedule.timezone,
                "task_type": job.task_type,
                "target_channel": job.dispatch.channel,
                "target_user_id": job.dispatch.target.user_id,
                "target_session_id": job.dispatch.target.session_id,
                "last_run_at": state.last_run_at.isoformat() if state.last_run_at else None,
                "next_run_at": state.next_run_at.isoformat() if state.next_run_at else None,
                "last_error": state.last_error,
            },
            "spec": job.model_dump(mode="json"),
            "runtime": {
                "status": status,
                "enabled": job.enabled,
                "last_run_at": state.last_run_at.isoformat() if state.last_run_at else None,
                "next_run_at": state.next_run_at.isoformat() if state.next_run_at else None,
                "last_error": state.last_error,
            },
            "route": route,
            "actions": actions,
        }

    def _serialize_schedule_summary(self, job: CronJobSpec) -> dict[str, object]:
        state = self._manager.get_state(job.id)
        route = f"/api/runtime-center/schedules/{job.id}"
        status = self._status_for(job)
        actions = {"run": f"{route}/run", "delete": route}
        if status == "paused" or job.enabled is False:
            actions["resume"] = f"{route}/resume"
        else:
            actions["pause"] = f"{route}/pause"
        return {
            "id": job.id,
            "title": job.name,
            "status": status,
            "owner": job.dispatch.target.user_id,
            "cron": job.schedule.cron,
            "enabled": job.enabled,
            "task_type": job.task_type,
            "updated_at": "2026-03-09T07:50:00+00:00",
            "last_run_at": state.last_run_at.isoformat() if state.last_run_at else None,
            "next_run_at": state.next_run_at.isoformat() if state.next_run_at else None,
            "last_error": state.last_error,
            "route": route,
            "actions": actions,
        }

    def _status_for(self, job: CronJobSpec) -> str:
        if job.enabled is False:
            return "paused"
        state = self._manager.get_state(job.id)
        if state.last_status == "running":
            return "running"
        return "scheduled"


class FakeStateQueryService:
    async def list_tasks(self, limit: int | None = 5):
        assert limit in {None, 5, 20}
        return [
            {
                "id": "task-1",
                "title": "Refresh competitor brief",
                "kind": "task",
                "status": "running",
                "owner_role": "ops-agent",
                "current_progress_summary": "Collecting current market notes",
                "updated_at": "2026-03-09T08:00:00+00:00",
                "work_context_id": "ctx-1",
                "context_key": "control-thread:industry-chat:industry-v1-ops:execution-core",
                "work_context": {
                    "id": "ctx-1",
                    "title": "Acme Pets execution core",
                    "context_key": "control-thread:industry-chat:industry-v1-ops:execution-core",
                },
            },
        ]

    async def list_work_contexts(self, limit: int | None = 5):
        assert limit in {None, 5, 20}
        return [
            {
                "id": "ctx-1",
                "title": "Acme Pets execution core",
                "kind": "work-context",
                "status": "active",
                "owner_scope": "pets-ops",
                "summary": "Formal control-thread work boundary for Acme Pets.",
                "updated_at": "2026-03-09T08:00:00+00:00",
                "route": "/api/runtime-center/work-contexts/ctx-1",
                "context_type": "industry-control-thread",
                "context_key": "control-thread:industry-chat:industry-v1-ops:execution-core",
                "task_count": 3,
                "active_task_count": 1,
            },
        ]

    async def count_work_contexts(self):
        return 1

    async def list_schedules(self, limit: int | None = 5):
        assert limit in {None, 5, 20}
        return [
            {
                "id": "sched-1",
                "name": "Morning heartbeat",
                "status": "scheduled",
                "owner": "system",
                "cron": "0 9 * * 1",
                "updated_at": "2026-03-09T07:50:00+00:00",
            },
        ]

    async def list_decision_requests(self, limit: int | None = 5):
        assert limit in {None, 5, 20}
        return [
            {
                "id": "decision-1",
                "summary": "Approve guarded browser action",
                "status": "open",
                "risk_level": "guarded",
                "requested_by": "ops-agent",
                "created_at": "2026-03-09T07:55:00+00:00",
                "route": "/api/runtime-center/decisions/decision-1",
                "actions": {
                    "approve": "/api/runtime-center/decisions/decision-1/approve",
                    "reject": "/api/runtime-center/decisions/decision-1/reject",
                },
            },
        ]

    async def list_goals(self, limit: int | None = 5):
        assert limit in {None, 5, 20}
        return [
            {
                "id": "goal-1",
                "title": "Launch runtime center",
                "summary": "Make goals visible across runtime center and agent workbench.",
                "status": "active",
                "priority": 3,
                "owner_scope": "ops",
                "updated_at": "2026-03-09T07:40:00+00:00",
                "route": "/api/runtime-center/goals/goal-1",
            },
        ]

    async def get_task_detail(self, task_id: str):
        if task_id != "task-1":
            return None
        return {
            "task": {
                "id": "task-1",
                "goal_id": "goal-1",
                "title": "Refresh competitor brief",
                "summary": "Collect the latest competitor notes.",
                "task_type": "task",
                "status": "running",
                "owner_agent_id": "ops-agent",
            },
            "runtime": {
                "runtime_status": "active",
                "current_phase": "executing",
                "risk_level": "guarded",
                "active_environment_id": "session:web:main",
            },
            "child_tasks": [
                {
                    "id": "task-child-1",
                    "title": "Collect screenshots",
                    "status": "completed",
                    "owner_agent_id": "research-agent",
                    "owner_agent_name": "Research Agent",
                    "summary": "Stored the latest screenshots.",
                    "route": "/api/runtime-center/tasks/task-child-1",
                },
            ],
            "goal": {"id": "goal-1", "title": "Launch runtime center"},
            "frames": [],
            "decisions": [],
            "evidence": [{"id": "evidence-1"}],
            "agents": [{"agent_id": "ops-agent", "name": "Ops Agent"}],
            "work_context": {
                "id": "ctx-1",
                "title": "Acme Pets execution core",
                "context_key": "control-thread:industry-chat:industry-v1-ops:execution-core",
            },
            "kernel": {"capability_ref": "system:dispatch_query"},
            "patches": [{"id": "patch-1"}],
            "growth": [{"id": "growth-1"}],
            "review": {
                "headline": "Task is still progressing with formal writeback.",
                "objective": "Collect the latest competitor notes.",
                "status": "running",
                "phase": "executing",
                "pending_decision_count": 0,
                "evidence_count": 1,
                "child_task_count": 1,
                "child_terminal_count": 1,
                "child_completion_rate": 100.0,
                "summary_lines": ["目标：Collect the latest competitor notes."],
                "next_actions": ["Continue execution and write evidence."],
                "risks": ["No extra governance blocker detected."],
                "task_route": "/api/runtime-center/tasks/task-1",
                "review_route": "/api/runtime-center/tasks/task-1/review",
            },
            "stats": {"evidence_count": 1},
            "route": "/api/runtime-center/tasks/task-1",
        }

    async def get_task_review(self, task_id: str):
        if task_id != "task-1":
            return None
        return {
            "task": {
                "id": "task-1",
                "title": "Refresh competitor brief",
            },
            "runtime": {
                "runtime_status": "active",
                "current_phase": "executing",
            },
            "review": {
                "headline": "Task is still progressing with formal writeback.",
                "objective": "Collect the latest competitor notes.",
                "status": "running",
                "phase": "executing",
                "pending_decision_count": 0,
                "evidence_count": 1,
                "child_task_count": 1,
                "child_terminal_count": 1,
                "child_completion_rate": 100.0,
                "summary_lines": ["目标：Collect the latest competitor notes."],
                "next_actions": ["Continue execution and write evidence."],
                "risks": ["No extra governance blocker detected."],
                "task_route": "/api/runtime-center/tasks/task-1",
                "review_route": "/api/runtime-center/tasks/task-1/review",
            },
            "route": "/api/runtime-center/tasks/task-1/review",
        }

    async def get_work_context_detail(self, context_id: str):
        if context_id != "ctx-1":
            return None
        return {
            "work_context": {
                "id": "ctx-1",
                "title": "Acme Pets execution core",
                "summary": "Formal control-thread work boundary for Acme Pets.",
                "context_type": "industry-control-thread",
                "status": "active",
                "context_key": "control-thread:industry-chat:industry-v1-ops:execution-core",
                "owner_scope": "pets-ops",
                "primary_thread_id": "industry-chat:industry-v1-ops:execution-core",
            },
            "parent_work_context": None,
            "child_contexts": [],
            "tasks": [
                {
                    "id": "task-1",
                    "title": "Refresh competitor brief",
                    "status": "running",
                    "owner_agent_id": "ops-agent",
                    "work_context_id": "ctx-1",
                    "work_context": {
                        "id": "ctx-1",
                        "title": "Acme Pets execution core",
                        "context_key": "control-thread:industry-chat:industry-v1-ops:execution-core",
                    },
                    "summary": "Collect the latest competitor notes.",
                    "updated_at": "2026-03-09T08:00:00+00:00",
                    "route": "/api/runtime-center/tasks/task-1",
                },
            ],
            "agents": [{"agent_id": "ops-agent", "name": "Ops Agent"}],
            "threads": ["industry-chat:industry-v1-ops:execution-core"],
            "stats": {
                "task_count": 3,
                "active_task_count": 1,
                "terminal_task_count": 2,
                "owner_agent_count": 1,
                "child_context_count": 0,
            },
            "route": "/api/runtime-center/work-contexts/ctx-1",
        }

    async def get_goal_detail(self, goal_id: str):
        if goal_id != "goal-1":
            return None
        return {
            "goal": {
                "id": "goal-1",
                "title": "Launch runtime center",
                "summary": "Make goals visible across runtime center and agent workbench.",
                "status": "active",
            },
            "tasks": [{"task": {"id": "task-1"}}],
            "patches": [{"id": "patch-1"}],
            "growth": [{"id": "growth-1"}],
        }

    async def get_decision_request(self, decision_id: str):
        if decision_id != "decision-1":
            return None
        return {
            "id": "decision-1",
            "summary": "Approve guarded browser action",
            "status": "open",
            "risk_level": "guarded",
            "requested_by": "ops-agent",
            "created_at": "2026-03-09T07:55:00+00:00",
            "route": "/api/runtime-center/decisions/decision-1",
            "actions": {
                "approve": "/api/runtime-center/decisions/decision-1/approve",
                "reject": "/api/runtime-center/decisions/decision-1/reject",
            },
        }

    async def legacy_list_chat_tasks_removed(
        self,
        *,
        control_thread_id: str,
        limit: int | None = 10,
    ):
        assert control_thread_id == "industry-chat:industry-v1-ops:execution-core"
        assert limit == 10
        return [
            {
                "id": "removed-query-task",
                "title": "执行流程：登录京东后台并整理商品上架流程",
                "status": "running",
                "summary": "正在整理最新上架步骤。",
                "owner_agent_id": "copaw-agent-runner",
                "updated_at": "2026-03-16T09:00:00+00:00",
                "thread_id": "removed-thread:req-task",
                "session_id": "removed-session:req-task",
                "session_kind": "removed",
                "control_thread_id": control_thread_id,
                "task_route": "/api/runtime-center/tasks/removed-query-task",
                "industry_instance_id": "industry-v1-ops",
                "industry_label": "白泽行业团队",
                "owner_scope": "jd-ops",
                "work_context_id": "ctx-1",
                "context_key": "control-thread:industry-chat:industry-v1-ops:execution-core",
                "work_context": {
                    "id": "ctx-1",
                    "title": "Acme Pets execution core",
                    "context_key": "control-thread:industry-chat:industry-v1-ops:execution-core",
                },
            },
        ]


class FakeEvidenceQueryService:
    async def list_recent_records(self, limit: int = 5):
        assert limit == 5
        return [
            {
                "id": "evidence-1",
                "action_summary": "Opened dashboard snapshot",
                "result_summary": "Snapshot stored for later replay",
                "actor": "ops-agent",
                "risk_level": "auto",
                "created_at": "2026-03-09T08:01:00+00:00",
            },
        ]

    async def count_records(self) -> int:
        return 1

    def get_record(self, evidence_id: str):
        if evidence_id != "evidence-1":
            return None
        return type(
            "EvidenceRecord",
            (),
            {
                "id": "evidence-1",
                "task_id": "task-1",
                "actor_ref": "ops-agent",
                "environment_ref": "session:web:main",
                "capability_ref": "system:dispatch_query",
                "risk_level": "guarded",
                "action_summary": "Opened dashboard snapshot",
                "result_summary": "Snapshot stored for later replay",
                "created_at": datetime(2026, 3, 9, 8, 1, tzinfo=timezone.utc),
                "status": "recorded",
                "metadata": {},
                "artifacts": (),
                "replay_pointers": (),
            },
        )()

    def serialize_record(self, record):
        return {
            "id": record.id,
            "task_id": record.task_id,
            "action_summary": record.action_summary,
            "result_summary": record.result_summary,
            "capability_ref": record.capability_ref,
            "environment_ref": record.environment_ref,
            "created_at": record.created_at.isoformat(),
        }


class FakeRoutineService(RoutineService):
    def __init__(self) -> None:
        verified_at = datetime(2026, 3, 16, 9, 30, tzinfo=timezone.utc)
        completed_at = datetime(2026, 3, 16, 9, 35, tzinfo=timezone.utc)
        self.routine = ExecutionRoutineRecord(
            id="routine-1",
            routine_key="jd-login-capture",
            name="京东登录例行",
            summary="固定回放京东后台登录与截图动作。",
            status="active",
            owner_agent_id="ops-agent",
            owner_scope="jd-ops",
            engine_kind="browser",
            trigger_kind="manual",
            last_verified_at=verified_at,
            success_rate=0.9,
            created_at=verified_at,
            updated_at=verified_at,
        )
        self.run = RoutineRunRecord(
            id="routine-run-1",
            routine_id=self.routine.id,
            source_type="manual",
            status="completed",
            owner_agent_id="ops-agent",
            owner_scope="jd-ops",
            session_id="browser-session-1",
            lease_ref="session:browser-local:browser-session-1",
            deterministic_result="replay-complete",
            output_summary="例行回放完成",
            evidence_ids=["evidence-1"],
            started_at=verified_at,
            completed_at=completed_at,
            created_at=verified_at,
            updated_at=completed_at,
        )
        self.diagnosis = RoutineDiagnosis(
            routine_id=self.routine.id,
            last_run_id=self.run.id,
            status="active",
            drift_status="stable",
            selector_health="healthy",
            session_health="healthy",
            lock_health="healthy",
            evidence_health="healthy",
            fallback_summary={"counts": {}, "last_fallback": None},
            recommended_actions=[],
            last_verified_at=verified_at.isoformat(),
        )
        self.replay_requests: list[RoutineReplayRequest | None] = []

    def get_runtime_center_overview(self, *, limit: int = 5) -> dict[str, object]:
        _ = limit
        return {
            "total": 1,
            "active": 1,
            "degraded": 0,
            "recent_success_rate": 0.9,
            "last_verified_at": self.routine.last_verified_at.isoformat(),
            "last_failure_class": None,
            "last_fallback": None,
            "resource_conflicts": 0,
            "entries": [
                {
                    "id": self.routine.id,
                    "title": self.routine.name,
                    "kind": "routine",
                    "status": self.routine.status,
                    "summary": self.routine.summary,
                    "updated_at": self.routine.updated_at.isoformat(),
                    "route": f"/api/routines/{self.routine.id}",
                    "actions": {
                        "replay": f"/api/routines/{self.routine.id}/replay",
                        "diagnosis": f"/api/routines/{self.routine.id}/diagnosis",
                    },
                    "meta": {
                        "engine_kind": self.routine.engine_kind,
                        "trigger_kind": self.routine.trigger_kind,
                        "success_rate": self.routine.success_rate,
                        "last_verified_at": self.routine.last_verified_at.isoformat(),
                    },
                },
            ],
        }

    def list_routines(self, **kwargs):
        _ = kwargs
        return [self.routine]

    def get_routine_detail(self, routine_id: str) -> RoutineDetail:
        if routine_id != self.routine.id:
            raise KeyError(f"Routine '{routine_id}' not found")
        return RoutineDetail(
            routine=self.routine,
            last_run=self.run,
            recent_runs=[self.run],
            recent_evidence=[
                {
                    "id": "evidence-1",
                    "result_summary": "例行截图已写回",
                    "created_at": self.run.completed_at.isoformat(),
                },
            ],
            diagnosis=self.diagnosis,
            routes={
                "detail": f"/api/routines/{self.routine.id}",
                "diagnosis": f"/api/routines/{self.routine.id}/diagnosis",
                "replay": f"/api/routines/{self.routine.id}/replay",
                "runs": f"/api/routines/runs?routine_id={self.routine.id}",
            },
        )

    def get_diagnosis(self, routine_id: str) -> RoutineDiagnosis:
        if routine_id != self.routine.id:
            raise KeyError(f"Routine '{routine_id}' not found")
        return self.diagnosis

    async def replay_routine(
        self,
        routine_id: str,
        payload: RoutineReplayRequest | None = None,
    ) -> RoutineReplayResponse:
        if routine_id != self.routine.id:
            raise KeyError(f"Routine '{routine_id}' not found")
        self.replay_requests.append(payload)
        replayed_run = self.run.model_copy(
            update={
                "updated_at": datetime(2026, 3, 16, 10, 0, tzinfo=timezone.utc),
            },
        )
        self.run = replayed_run
        return RoutineReplayResponse(
            run=replayed_run,
            diagnosis=self.diagnosis,
            routes={
                "run": f"/api/routines/runs/{replayed_run.id}",
                "routine": f"/api/routines/{self.routine.id}",
                "diagnosis": f"/api/routines/{self.routine.id}/diagnosis",
            },
        )

    def list_runs(self, **kwargs):
        _ = kwargs
        return [self.run]

    def get_run_detail(self, run_id: str) -> RoutineRunDetail:
        if run_id != self.run.id:
            raise KeyError(f"Routine run '{run_id}' not found")
        return RoutineRunDetail(
            run=self.run,
            routine=self.routine,
            evidence=[
                {
                    "id": "evidence-1",
                    "result_summary": "例行截图已写回",
                    "created_at": self.run.completed_at.isoformat(),
                },
            ],
            routes={
                "detail": f"/api/routines/runs/{self.run.id}",
                "routine": f"/api/routines/{self.routine.id}",
                "diagnosis": f"/api/routines/{self.routine.id}/diagnosis",
            },
        )

    def create_routine(self, payload: RoutineCreateRequest) -> ExecutionRoutineRecord:
        self.routine = self.routine.model_copy(
            update={
                "routine_key": payload.routine_key,
                "name": payload.name,
                "summary": payload.summary,
                "updated_at": datetime(2026, 3, 16, 10, 5, tzinfo=timezone.utc),
            },
        )
        return self.routine

    def create_routine_from_evidence(
        self,
        payload: RoutineCreateFromEvidenceRequest,
    ) -> ExecutionRoutineRecord:
        self.routine = self.routine.model_copy(
            update={
                "source_evidence_ids": list(payload.evidence_ids),
                "updated_at": datetime(2026, 3, 16, 10, 10, tzinfo=timezone.utc),
            },
        )
        return self.routine


class FakeCapabilityService:
    def get_capability(self, capability_id: str):
        if capability_id == "system:update_heartbeat_config":
            return SimpleNamespace(risk_level="guarded")
        return None

    def list_capabilities(self, *args, **kwargs):
        return [
            {
                "id": "tool:execute_shell_command",
                "name": "execute_shell_command",
                "summary": "Run shell commands.",
                "kind": "local-tool",
                "risk_level": "guarded",
                "environment_requirements": ["workspace"],
                "role_access_policy": ["all"],
                "evidence_contract": ["shell-command"],
                "replay_support": True,
                "enabled": True,
            },
        ]

    def summarize(self):
        return {
            "total": 1,
            "enabled": 1,
            "by_kind": {"local-tool": 1},
        }


class FakeLearningService:
    def __init__(
        self,
        *,
        patch_status: str = "approved",
        risk_level: str = "guarded",
    ) -> None:
        self._patch_status = patch_status
        self._risk_level = risk_level

    def _patch_payload(self) -> dict[str, object]:
        return {
            "id": "patch-1",
            "kind": "capability_patch",
            "goal_id": "goal-1",
            "task_id": "task-1",
            "agent_id": "ops-agent",
            "title": "Enable richer shell evidence",
            "description": "Persist shell command metadata into the evidence ledger.",
            "source_evidence_id": "evidence-1",
            "evidence_refs": ["evidence-1"],
            "risk_level": self._risk_level,
            "status": self._patch_status,
            "created_at": "2026-03-09T08:10:00+00:00",
            "proposal_id": None,
        }

    def list_patches(
        self,
        *,
        status: str | None = None,
        goal_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
    ):
        patch = self._patch_payload()
        if status is not None and patch["status"] != status:
            return []
        return [patch]

    def get_patch(self, patch_id: str):
        if patch_id != "patch-1":
            raise KeyError(f"Patch '{patch_id}' not found")
        payload = self._patch_payload()
        return type(
            "Patch",
            (),
            {
                "id": "patch-1",
                "goal_id": "goal-1",
                "task_id": "task-1",
                "agent_id": "ops-agent",
                "source_evidence_id": "evidence-1",
                "evidence_refs": ["evidence-1"],
                "model_dump": lambda self, mode="json": dict(payload),
            },
        )()

    def approve_patch(self, patch_id: str, *, approved_by: str = "system"):
        _ = approved_by
        self.get_patch(patch_id)
        self._patch_status = "approved"
        return self.get_patch(patch_id)

    def reject_patch(self, patch_id: str, *, rejected_by: str = "system"):
        _ = rejected_by
        self.get_patch(patch_id)
        self._patch_status = "rejected"
        return self.get_patch(patch_id)

    def apply_patch(self, patch_id: str, *, applied_by: str = "system"):
        _ = applied_by
        self.get_patch(patch_id)
        if self._patch_status == "proposed" and self._risk_level == "confirm":
            raise ValueError(
                f"Patch {patch_id} has risk_level=confirm and must be approved before applying.",
            )
        self._patch_status = "applied"
        return self.get_patch(patch_id)

    def rollback_patch(self, patch_id: str, *, rolled_back_by: str = "system"):
        _ = rolled_back_by
        self.get_patch(patch_id)
        self._patch_status = "rolled_back"
        return self.get_patch(patch_id)

    def list_growth(
        self,
        *,
        agent_id: str | None = None,
        goal_id: str | None = None,
        task_id: str | None = None,
        source_patch_id: str | None = None,
        limit: int = 50,
    ):
        assert limit in {5, 50, 200}
        return [
            {
                "id": "growth-1",
                "agent_id": "ops-agent",
                "goal_id": "goal-1",
                "task_id": "task-1",
                "change_type": "patch_applied",
                "description": "Applied capability patch for shell evidence.",
                "source_patch_id": "patch-1",
                "source_evidence_id": "evidence-1",
                "risk_level": "guarded",
                "result": "applied",
                "created_at": "2026-03-09T08:20:00+00:00",
            },
        ]

    def get_growth_event(self, event_id: str):
        if event_id != "growth-1":
            raise KeyError(f"Growth event '{event_id}' not found")
        return type(
            "GrowthEvent",
            (),
            {
                "source_patch_id": "patch-1",
                "source_evidence_id": "evidence-1",
                "agent_id": "ops-agent",
                "goal_id": "goal-1",
                "task_id": "task-1",
                "model_dump": lambda self, mode="json": {
                    "id": "growth-1",
                    "agent_id": "ops-agent",
                    "goal_id": "goal-1",
                    "task_id": "task-1",
                    "change_type": "patch_applied",
                    "description": "Applied capability patch for shell evidence.",
                    "source_patch_id": "patch-1",
                    "source_evidence_id": "evidence-1",
                    "risk_level": "guarded",
                    "result": "applied",
                },
            },
        )()


class FakeAgentProfileService:
    def list_agents(
        self,
        limit: int | None = 5,
        view: str = "all",
        industry_instance_id: str | None = None,
    ):
        assert limit in {None, 5}
        agents = [
            {
                "agent_id": "ops-agent",
                "name": "Ops Agent",
                "status": "running",
                "role_name": "operator",
                "role_summary": "Owns runtime coordination.",
                "risk_level": "guarded",
                "current_goal_id": "goal-1",
                "current_goal": "Launch runtime center",
                "current_task_id": "task-1",
                "environment_summary": "session:web:main",
                "today_output_summary": "Reviewed runtime center open tasks.",
                "latest_evidence_summary": "Dashboard snapshot stored.",
                "industry_instance_id": "industry-v1-ops",
                "updated_at": "2026-03-09T08:30:00+00:00",
                "capabilities": ["system:dispatch_query", "tool:execute_shell_command"],
            },
            {
                "agent_id": "copaw-agent-runner",
                "name": "白泽平台兜底",
                "status": "waiting",
                "role_name": "平台兜底执行",
                "role_summary": "平台级历史兼容兜底身份，仅在底层运行链需要时承接执行。",
                "risk_level": "guarded",
                "current_goal_id": None,
                "current_goal": "维持底层执行兼容兜底，不再作为业务团队执行脑暴露。",
                "current_task_id": None,
                "environment_summary": "workspace + browser + session",
                "today_output_summary": "",
                "latest_evidence_summary": "",
                "updated_at": "2026-03-09T08:00:00+00:00",
                "capabilities": ["system:dispatch_query"],
            },
            {
                "agent_id": "copaw-scheduler",
                "name": "白泽调度中枢",
                "status": "running",
                "role_name": "定时调度",
                "role_summary": "负责自动调度与运行节奏。",
                "risk_level": "guarded",
                "current_goal_id": None,
                "current_goal": "维持自动调度运行稳定。",
                "current_task_id": None,
                "environment_summary": "schedule runtime",
                "today_output_summary": "",
                "latest_evidence_summary": "",
                "updated_at": "2026-03-09T08:10:00+00:00",
                "capabilities": ["system:dispatch_query"],
            },
            {
                "agent_id": "copaw-governance",
                "name": "白泽治理中枢",
                "status": "idle",
                "role_name": "风险治理",
                "role_summary": "负责审批、治理与补丁收口。",
                "risk_level": "confirm",
                "current_goal_id": None,
                "current_goal": "",
                "current_task_id": None,
                "environment_summary": "governance runtime",
                "today_output_summary": "",
                "latest_evidence_summary": "",
                "updated_at": "2026-03-09T08:05:00+00:00",
                "capabilities": ["system:dispatch_query"],
            },
        ]
        if view == "business":
            agents = [
                agent
                for agent in agents
                if agent["agent_id"] not in {"copaw-agent-runner", "copaw-scheduler", "copaw-governance"}
            ]
        if view == "system":
            agents = [
                agent
                for agent in agents
                if agent["agent_id"] in {"copaw-scheduler", "copaw-governance"}
            ]
        if industry_instance_id is not None:
            agents = [
                agent
                for agent in agents
                if agent.get("industry_instance_id") == industry_instance_id
            ]
        return agents

    def get_agent(self, agent_id: str):
        for agent in self.list_agents(view="all"):
            if agent["agent_id"] == agent_id:
                return agent
        return None

    def get_agent_detail(self, agent_id: str):
        agent = self.get_agent(agent_id)
        if agent is None:
            return None
        workspace_environment = {
            "id": "env:workspace:workspace:main",
            "kind": "workspace",
            "display_name": "workspace:main",
            "ref": "workspace:main",
            "status": "active",
            "route": "/api/runtime-center/environments/env:workspace:workspace:main",
            "stats": {
                "observation_count": 1,
                "replay_count": 1,
                "artifact_count": 1,
            },
            "observations": [{"id": "obs-1", "action_summary": "Saved profile.md"}],
            "replays": [{"replay_id": "replay-1", "replay_type": "shell"}],
            "artifacts": [{"artifact_id": "artifact-1", "artifact_kind": "file"}],
        }
        return {
            "agent": agent,
            "goals": [{"id": "goal-1", "title": "Launch runtime center"}],
            "tasks": [{"task": {"id": "task-1"}, "route": "/api/runtime-center/tasks/task-1"}],
            "decisions": [{"id": "decision-1"}],
            "evidence": [{"id": "evidence-1"}],
            "patches": [{"id": "patch-1"}],
            "growth": [{"id": "growth-1"}],
            "environments": [workspace_environment],
            "workspace": {
                "current_environment_id": workspace_environment["id"],
                "current_environment_ref": workspace_environment["ref"],
                "current_environment": workspace_environment,
                "files_supported": True,
            },
            "stats": {"task_count": 1, "environment_count": 1},
        }


class FakeIndustryService:
    def list_instances(self, limit: int | None = 5):
        assert limit in {None, 5, 20}
        return [
            {
                "instance_id": "industry-v1-ops",
                "label": "Ops Industry Team",
                "summary": "Formal team object for operations.",
                "status": "active",
                "owner_scope": "ops",
                "updated_at": "2026-03-09T08:35:00+00:00",
                "stats": {
                    "agent_count": 3,
                    "lane_count": 2,
                    "backlog_count": 4,
                    "cycle_count": 1,
                    "assignment_count": 2,
                    "report_count": 1,
                    "schedule_count": 2,
                },
                "routes": {
                    "runtime_detail": "/api/runtime-center/industry/industry-v1-ops",
                },
            },
        ]

    def get_instance_detail(self, instance_id: str):
        if instance_id != "industry-v1-ops":
            return None
        return type(
            "IndustryDetail",
            (),
            {
                "model_dump": lambda self, mode="json": {
                    "instance_id": "industry-v1-ops",
                    "label": "Ops Industry Team",
                    "summary": "Formal team object for operations.",
                    "status": "active",
                    "owner_scope": "ops",
                    "stats": {
                        "agent_count": 3,
                        "lane_count": 2,
                        "backlog_count": 4,
                        "cycle_count": 1,
                        "assignment_count": 2,
                        "report_count": 1,
                        "schedule_count": 2,
                    },
                }
            },
        )()


class FakeStrategyMemoryService:
    def list_strategies(
        self,
        *,
        scope_type: str | None = None,
        scope_id: str | None = None,
        owner_agent_id: str | None = None,
        industry_instance_id: str | None = None,
        status: str | None = None,
        limit: int | None = 20,
    ):
        assert scope_type in {None, "industry", "global"}
        assert status in {"active", "archived", "retired", None}
        assert limit in {20, 50, None}
        records = [
            {
                "strategy_id": "strategy:industry:industry-v1-ops:copaw-agent-runner",
                "scope_type": "industry",
                "scope_id": "industry-v1-ops",
                "owner_agent_id": "copaw-agent-runner",
                "owner_scope": "ops",
                "industry_instance_id": "industry-v1-ops",
                "title": "白泽执行中枢行业战略",
                "summary": "统一经营目标、证据要求与委派边界。",
                "mission": "对齐团队经营方向并持续推进执行。",
                "north_star": "把行业目标拆成可验证的执行闭环。",
                "priority_order": ["增长", "风险", "效率"],
                "thinking_axes": ["行业趋势", "渠道经营", "执行瓶颈"],
                "delegation_policy": ["优先交给专业执行位", "需要跨席位协同时统一调度"],
                "direct_execution_policy": [
                    "主脑不直接使用浏览器、桌面、文件编辑等叶子执行能力。",
                    "没有合适执行位时，先补位、改派或请求确认，不让主脑兜底变成执行员。",
                ],
                "execution_constraints": ["高风险动作走治理确认"],
                "evidence_requirements": ["关键动作必须留证据", "日报周报必须可追溯"],
                "active_goal_ids": ["goal-1"],
                "active_goal_titles": ["Launch runtime center"],
                "teammate_contracts": [{"role_id": "ops-agent", "role_name": "运营执行位"}],
                "status": "active",
                "metadata": {},
                "created_at": "2026-03-09T08:00:00+00:00",
                "updated_at": "2026-03-09T08:30:00+00:00",
            },
        ]
        filtered = records
        if scope_type is not None:
            filtered = [item for item in filtered if item["scope_type"] == scope_type]
        if scope_id is not None:
            filtered = [item for item in filtered if item["scope_id"] == scope_id]
        if owner_agent_id is not None:
            filtered = [
                item for item in filtered if item["owner_agent_id"] == owner_agent_id
            ]
        if industry_instance_id is not None:
            filtered = [
                item
                for item in filtered
                if item["industry_instance_id"] == industry_instance_id
            ]
        if status is not None:
            filtered = [item for item in filtered if item["status"] == status]
        return filtered if limit is None else filtered[:limit]


class FakeGovernanceService:
    def __init__(self) -> None:
        self.status = {
            "control_id": "runtime",
            "emergency_stop_active": False,
            "emergency_reason": None,
            "emergency_actor": None,
            "paused_schedule_ids": [],
            "channel_shutdown_applied": False,
            "blocked_capability_refs": [],
            "pending_decisions": 0,
            "proposed_patches": 1,
            "pending_patches": 1,
            "metadata": {},
            "updated_at": "2026-03-09T08:35:00+00:00",
        }
    def get_status(self):
        return self

    def model_dump(self, mode: str = "json"):
        _ = mode
        return dict(self.status)


class FakeRuntimeSurfaceProjection:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = dict(payload)

    def model_dump(self, mode: str = "json") -> dict[str, object]:
        _ = mode
        return dict(self._payload)


class FakeEnvironmentService:
    def __init__(self) -> None:
        now = datetime(2026, 3, 9, 9, 0, tzinfo=timezone.utc)
        host_events = [
            {
                "event_id": 1,
                "event_name": "window-focus-changed",
                "topic": "window",
                "action": "focus-changed",
                "event_family": "active-window",
                "recommended_runtime_response": "re-observe",
                "severity": "medium",
                "created_at": now.isoformat(),
                "payload": {"window_ref": "window:excel:main"},
                "mechanism_backed": True,
                "is_truth_store": False,
                "note": (
                    "Host events are runtime-mechanism signals for observe/recover loops, "
                    "not truth-store records."
                ),
            },
            {
                "event_id": 2,
                "event_name": "captcha-prompt-required",
                "topic": "desktop",
                "action": "captcha-required",
                "event_family": "modal-uac-login",
                "recommended_runtime_response": "handoff",
                "severity": "high",
                "created_at": "2026-03-09T09:01:00+00:00",
                "payload": {"prompt_kind": "captcha"},
                "mechanism_backed": True,
                "is_truth_store": False,
                "note": (
                    "Host events are runtime-mechanism signals for observe/recover loops, "
                    "not truth-store records."
                ),
            },
            {
                "event_id": 3,
                "event_name": "download-finished",
                "topic": "download",
                "action": "download-completed",
                "event_family": "download-completed",
                "recommended_runtime_response": "re-observe",
                "severity": "low",
                "created_at": "2026-03-09T09:02:00+00:00",
                "payload": {"download_ref": "download-bucket:workspace:copaw:main"},
                "mechanism_backed": True,
                "is_truth_store": False,
                "note": (
                    "Host events are runtime-mechanism signals for observe/recover loops, "
                    "not truth-store records."
                ),
            },
            {
                "event_id": 4,
                "event_name": "excel-restarted",
                "topic": "process",
                "action": "process-restarted",
                "event_family": "process-exit-restart",
                "recommended_runtime_response": "recover",
                "severity": "high",
                "created_at": "2026-03-09T09:03:00+00:00",
                "payload": {"process_ref": "process:4242"},
                "mechanism_backed": True,
                "is_truth_store": False,
                "note": (
                    "Host events are runtime-mechanism signals for observe/recover loops, "
                    "not truth-store records."
                ),
            },
            {
                "event_id": 5,
                "event_name": "desktop-unlocked",
                "topic": "host",
                "action": "desktop-unlocked",
                "event_family": "lock-unlock",
                "recommended_runtime_response": "recover",
                "severity": "high",
                "created_at": "2026-03-09T09:04:00+00:00",
                "payload": {"locked": False},
                "mechanism_backed": True,
                "is_truth_store": False,
                "note": (
                    "Host events are runtime-mechanism signals for observe/recover loops, "
                    "not truth-store records."
                ),
            },
            {
                "event_id": 6,
                "event_name": "network-restored",
                "topic": "network",
                "action": "connectivity-changed",
                "event_family": "network-power",
                "recommended_runtime_response": "retry",
                "severity": "medium",
                "created_at": "2026-03-09T09:05:00+00:00",
                "payload": {"network_state": "online"},
                "mechanism_backed": True,
                "is_truth_store": False,
                "note": (
                    "Host events are runtime-mechanism signals for observe/recover loops, "
                    "not truth-store records."
                ),
            },
        ]
        latest_download_event = {
            "event_id": 3,
            "event_name": "download-finished",
            "topic": "download",
            "action": "download-completed",
            "severity": "low",
            "recommended_runtime_response": "re-observe",
            "created_at": "2026-03-09T09:02:00+00:00",
        }
        latest_host_event = {
            "event_id": 6,
            "event_name": "network-restored",
            "topic": "network",
            "action": "connectivity-changed",
            "event_family": "network-power",
            "severity": "medium",
            "recommended_runtime_response": "retry",
            "created_at": "2026-03-09T09:05:00+00:00",
        }
        self._host_contract = {
            "projection_kind": "host_contract_projection",
            "is_projection": True,
            "surface_kind": "session",
            "environment_id": "env:session:session:web:main",
            "session_mount_id": "session:web:main",
            "host_mode": "local-managed",
            "lease_class": "seat-runtime",
            "access_mode": "desktop-app",
            "session_scope": "desktop-user-session",
            "account_scope_ref": "windows:user:alice",
            "handoff_state": "agent-attached",
            "handoff_reason": "captcha-required",
            "handoff_owner_ref": "human-operator:alice",
            "resume_kind": "host-companion-session",
            "verification_channel": "runtime-center-self-check",
        }
        self._seat_runtime = {
            "projection_kind": "seat_runtime_projection",
            "is_projection": True,
            "seat_ref": "env:session:session:web:main",
            "environment_ref": "session:web:main",
            "workspace_scope": "project:copaw",
            "session_scope": "desktop-user-session",
            "host_mode": "local-managed",
            "lease_status": "leased",
            "lease_owner": "ops-agent",
            "host_id": "host:primary",
            "process_id": 4242,
            "session_count": 1,
            "active_session_mount_id": "session:web:main",
            "host_companion_status": "restorable",
            "active_surface_mix": ["browser", "desktop-app"],
            "status": "active",
            "occupancy_state": "occupied",
            "candidate_seat_refs": ["env:session:session:web:main"],
            "selected_seat_ref": "env:session:session:web:main",
            "seat_selection_policy": "sticky-active-seat",
            "expected_release_at": None,
            "live_handle_ref": "live:env:session:session:web:main:1234",
        }
        self._workspace_graph = {
            "projection_kind": "workspace_graph_projection",
            "is_projection": True,
            "workspace_id": "workspace:copaw:main",
            "seat_ref": "env:session:session:web:main",
            "session_mount_id": "session:web:main",
            "browser_context_refs": ["browser:web:main"],
            "app_window_refs": ["window:excel:main"],
            "file_doc_refs": ["doc:workspace:copaw"],
            "clipboard_refs": ["clipboard:workspace:main"],
            "download_bucket_refs": ["download-bucket:workspace:copaw:main"],
            "lock_refs": ["excel:writer-lock"],
            "active_surface_refs": [
                "browser:web:main",
                "window:excel:main",
                "doc:workspace:copaw",
                "clipboard:workspace:main",
                "download-bucket:workspace:copaw:main",
            ],
            "workspace_components": {
                "browser_context_count": 1,
                "app_window_count": 1,
                "file_doc_count": 1,
                "clipboard_count": 1,
                "download_bucket_count": 1,
                "lock_count": 1,
            },
            "artifact_refs": ["artifact-1"],
            "replay_refs": ["replay-1"],
            "observation_refs": ["ev-1"],
            "active_lock_summary": "excel:writer-lock",
            "pending_handoff_summary": "agent-attached",
            "owner_agent_id": "ops-agent",
            "account_scope_ref": "windows:user:alice",
            "workspace_scope": "project:copaw",
            "handoff_owner_ref": "human-operator:alice",
            "ownership": {
                "owner_agent_id": "ops-agent",
                "handoff_owner_ref": "human-operator:alice",
                "account_scope_ref": "windows:user:alice",
                "workspace_scope": "project:copaw",
                "session_scope": "desktop-user-session",
                "lease_class": "seat-runtime",
                "access_mode": "desktop-app",
            },
            "ownership_summary": "human-operator:alice",
            "collision_facts": {
                "account_scope_ref": "windows:user:alice",
                "writer_lock_scope": "workbook:weekly-report",
                "active_lock_summary": "excel:writer-lock",
                "handoff_state": "agent-attached",
                "handoff_reason": "captcha-required",
                "handoff_owner_ref": "human-operator:alice",
                "current_gap_or_blocker": None,
                "blocking_event_family": "modal-uac-login",
                "shared_surface_owner": "ops-agent",
                "requires_human_return": True,
            },
            "collision_summary": "excel:writer-lock",
            "download_status": {
                "bucket_refs": ["download-bucket:workspace:copaw:main"],
                "active_bucket_ref": "download-bucket:workspace:copaw:main",
                "download_policy": "workspace-bucket",
                "download_verification": True,
                "latest_download_event": dict(latest_download_event),
            },
            "surface_contracts": {
                "browser_active_site": "jd:seller-center",
                "browser_site_contract_status": "verified-writer",
                "desktop_app_identity": "excel",
                "desktop_app_contract_status": "verified-writer",
            },
            "locks": [
                {
                    "resource_ref": "excel:writer-lock",
                    "summary": "excel:writer-lock",
                    "surface_ref": "window:excel:main",
                    "account_scope_ref": "windows:user:alice",
                    "writer_lock": {
                        "status": "held",
                        "scope": "workbook:weekly-report",
                        "owner_agent_id": "ops-agent",
                        "lease_class": "seat-runtime",
                        "access_mode": "desktop-app",
                        "handoff_state": "agent-attached",
                        "handoff_owner_ref": "human-operator:alice",
                    },
                },
            ],
            "surfaces": {
                "browser": {
                    "context_refs": ["browser:web:main"],
                    "active_tab": {
                        "tab_id": "page:jd:seller-center:home",
                        "site": "jd:seller-center",
                        "tab_scope": "single-tab",
                        "login_state": "authenticated",
                        "account_scope_ref": "windows:user:alice",
                        "handoff_state": "agent-attached",
                        "resume_kind": "host-companion-session",
                        "verification_channel": "runtime-center-self-check",
                        "current_gap_or_blocker": None,
                    },
                    "site_contract_status": "verified-writer",
                    "download_policy": "workspace-bucket",
                },
                "desktop": {
                    "window_refs": ["window:excel:main"],
                    "active_window": {
                        "window_ref": "window:excel:main",
                        "window_scope": "window:excel:main",
                        "app_identity": "excel",
                        "window_anchor_summary": "Excel > Weekly Report.xlsx > Sheet1!A1",
                        "writer_lock_scope": "workbook:weekly-report",
                        "account_scope_ref": "windows:user:alice",
                        "handoff_state": "agent-attached",
                        "resume_kind": "host-companion-session",
                        "verification_channel": "runtime-center-self-check",
                        "current_gap_or_blocker": None,
                    },
                    "app_contract_status": "verified-writer",
                    "adapter_refs": ["app-adapter:excel", "app-adapter:file-explorer"],
                },
                "file_docs": {
                    "refs": ["doc:workspace:copaw"],
                    "active_doc_ref": "doc:workspace:copaw",
                    "workspace_scope": "project:copaw",
                },
                "clipboard": {
                    "refs": ["clipboard:workspace:main"],
                    "active_clipboard_ref": "clipboard:workspace:main",
                    "workspace_scope": "project:copaw",
                },
                "downloads": {
                    "bucket_refs": ["download-bucket:workspace:copaw:main"],
                    "active_bucket": {
                        "bucket_ref": "download-bucket:workspace:copaw:main",
                        "download_policy": "workspace-bucket",
                        "download_verification": True,
                        "latest_event_family": "download-completed",
                    },
                },
                "host_blocker": {
                    "event_family": "modal-uac-login",
                    "event_name": "captcha-required",
                    "recommended_runtime_response": "handoff",
                },
            },
            "handoff_checkpoint": {
                "state": "agent-attached",
                "reason": "captcha-required",
                "owner_ref": "human-operator:alice",
                "resume_kind": "host-companion-session",
                "verification_channel": "runtime-center-self-check",
                "checkpoint_ref": "checkpoint:captcha:jd-seller",
                "return_condition": "captcha-cleared",
                "summary": "agent-attached",
            },
            "latest_host_event_summary": dict(latest_host_event),
            "projection_note": (
                "Workspace graph is a derived runtime projection over mounts, "
                "artifacts, replays, observations, live-handle descriptors, and "
                "workspace/runtime handoff facts."
            ),
        }
        self._host_twin = {
            "projection_kind": "host_twin_projection",
            "is_projection": True,
            "is_truth_store": False,
            "seat_ref": "env:session:session:web:main",
            "environment_id": "env:session:session:web:main",
            "session_mount_id": "session:web:main",
            "ownership": {
                "seat_owner_agent_id": "ops-agent",
                "handoff_owner_ref": "human-operator:alice",
                "account_scope_ref": "windows:user:alice",
                "workspace_scope": "project:copaw",
                "ownership_source": "workspace_graph.ownership",
                "active_owner_kind": "agent-with-human-handoff",
            },
            "surface_mutability": {
                "browser": {
                    "surface_ref": "browser:web:main",
                    "mutability": "blocked",
                    "safe_to_mutate": False,
                    "blocker_family": "modal-uac-login",
                },
                "desktop_app": {
                    "surface_ref": "window:excel:main",
                    "mutability": "blocked",
                    "safe_to_mutate": False,
                    "blocker_family": "modal-uac-login",
                },
                "file_docs": {
                    "surface_ref": "doc:workspace:copaw",
                    "mutability": "blocked",
                    "safe_to_mutate": False,
                    "blocker_family": "modal-uac-login",
                },
            },
            "blocked_surfaces": [
                {
                    "surface_kind": "browser",
                    "surface_ref": "browser:web:main",
                    "reason": "captcha-required",
                    "event_family": "modal-uac-login",
                },
                {
                    "surface_kind": "desktop_app",
                    "surface_ref": "window:excel:main",
                    "reason": "captcha-required",
                    "event_family": "modal-uac-login",
                },
                {
                    "surface_kind": "file_docs",
                    "surface_ref": "doc:workspace:copaw",
                    "reason": "captcha-required",
                    "event_family": "modal-uac-login",
                },
            ],
            "continuity": {
                "status": "guarded",
                "valid": True,
                "continuity_source": "registered-restorer",
                "resume_kind": "host-companion-session",
                "requires_human_return": True,
            },
            "trusted_anchors": [
                {
                    "anchor_kind": "browser-dom",
                    "surface_ref": "browser:web:main",
                    "anchor_ref": "#shop-header",
                    "source": "browser_site_contract.last_verified_dom_anchor",
                },
                {
                    "anchor_kind": "desktop-window",
                    "surface_ref": "window:excel:main",
                    "anchor_ref": "Excel > Weekly Report.xlsx > Sheet1!A1",
                    "source": "desktop_app_contract.window_anchor_summary",
                },
                {
                    "anchor_kind": "checkpoint",
                    "surface_ref": "checkpoint:captcha:jd-seller",
                    "anchor_ref": "checkpoint:captcha:jd-seller",
                    "source": "workspace_graph.handoff_checkpoint",
                },
            ],
            "legal_recovery": {
                "path": "handoff",
                "checkpoint_ref": "checkpoint:captcha:jd-seller",
                "resume_kind": "host-companion-session",
                "verification_channel": "runtime-center-self-check",
                "return_condition": "captcha-cleared",
            },
            "active_blocker_families": ["modal-uac-login"],
            "latest_blocking_event": {
                "event_family": "modal-uac-login",
                "event_name": "captcha-required",
                "recommended_runtime_response": "handoff",
                "surface_refs": [
                    "browser:web:main",
                    "window:excel:main",
                    "doc:workspace:copaw",
                ],
            },
            "execution_mutation_ready": {
                "browser": False,
                "desktop_app": False,
                "file_docs": False,
            },
            "app_family_twins": {
                "browser_backoffice": {
                    "active": True,
                    "family_kind": "browser_backoffice",
                    "surface_ref": "browser:web:main",
                    "contract_status": "verified-writer",
                    "family_scope_ref": "site:jd:seller-center",
                },
                "messaging_workspace": {
                    "active": False,
                    "family_kind": "messaging_workspace",
                    "surface_ref": None,
                    "contract_status": "inactive",
                    "family_scope_ref": None,
                },
                "office_document": {
                    "active": True,
                    "family_kind": "office_document",
                    "surface_ref": "window:excel:main",
                    "contract_status": "verified-writer",
                    "family_scope_ref": "app:excel",
                    "writer_lock_scope": "workbook:weekly-report",
                },
                "desktop_specialized": {
                    "active": False,
                    "family_kind": "desktop_specialized",
                    "surface_ref": None,
                    "contract_status": "inactive",
                    "family_scope_ref": None,
                },
            },
            "coordination": {
                "seat_owner_ref": "ops-agent",
                "workspace_owner_ref": "ops-agent",
                "writer_owner_ref": "ops-agent",
                "candidate_seat_refs": ["env:session:session:web:main"],
                "selected_seat_ref": "env:session:session:web:main",
                "seat_selection_policy": "sticky-active-seat",
                "contention_forecast": {
                    "severity": "blocked",
                    "reason": "captcha-required",
                },
                "legal_owner_transition": {
                    "allowed": False,
                    "reason": "human handoff is still active",
                },
                "recommended_scheduler_action": "handoff",
                "expected_release_at": None,
            },
            "projection_note": (
                "Execution-grade host twin is a derived runtime projection over "
                "seat/workspace/contracts/events/evidence anchors, not a second "
                "truth source."
            ),
        }
        self._recovery = {
            "status": "restorable",
            "recoverable": True,
            "resume_kind": "resume-environment",
            "mode": "resume-environment",
            "same_host": True,
            "same_process": True,
            "startup_recovery_required": False,
            "note": "Seat runtime can rebind via host companion session.",
        }
        self._host_companion_session = {
            "projection_kind": "host_companion_session_projection",
            "is_projection": True,
            "session_mount_id": "session:web:main",
            "environment_id": "env:session:session:web:main",
            "channel": "web",
            "session_id": "main",
            "user_id": "alice",
            "continuity_status": "restorable",
            "continuity_source": "registered-restorer",
            "lease_status": "leased",
            "lease_owner": "ops-agent",
            "lease_runtime": {
                "host_id": "host:primary",
                "process_id": 4242,
                "seen_at": now.isoformat(),
                "expires_at": now.isoformat(),
            },
            "locality": {
                "same_host": True,
                "same_process": True,
                "startup_recovery_required": False,
            },
            "live_handle": {
                "ref": "live:env:session:session:web:main:1234",
            },
            "handoff_state": "agent-attached",
            "resume_kind": "host-companion-session",
            "verification_channel": "runtime-center-self-check",
            "current_gap_or_blocker": None,
        }
        self._browser_site_contract = {
            "projection_kind": "browser_site_contract_projection",
            "is_projection": True,
            "environment_id": "env:session:session:web:main",
            "session_mount_id": "session:web:main",
            "browser_mode": "tab-attached",
            "login_state": "authenticated",
            "tab_scope": "single-tab",
            "profile_ref": "profile:copaw:main",
            "attach_transport_ref": "transport:cdp:local",
            "provider_kind": "local-managed-browser",
            "provider_session_ref": "browser-session:web:main",
            "download_policy": "workspace-bucket",
            "storage_scope": "profile+workspace",
            "account_scope_ref": "windows:user:alice",
            "site_contract_ref": "site-contract:jd:seller-center:writer",
            "site_contract_status": "verified-writer",
            "site_risk_contract_ref": "site-risk:jd:seller-center",
            "handoff_state": "agent-attached",
            "resume_kind": "host-companion-session",
            "manual_resume_required": False,
            "active_site": "jd:seller-center",
            "active_tab_ref": "page:jd:seller-center:home",
            "last_verified_url": "https://seller.jd.com/home",
            "last_verified_dom_anchor": "#shop-header",
            "navigation": True,
            "dom_interaction": True,
            "multi_tab": False,
            "uploads": True,
            "downloads": True,
            "download_verification": True,
            "pdf_export": True,
            "storage_access": True,
            "locale_timezone_override": False,
            "download_bucket_refs": ["download-bucket:workspace:copaw:main"],
            "continuity_source": "registered-restorer",
            "current_gap_or_blocker": None,
        }
        self._desktop_app_contract = {
            "projection_kind": "desktop_app_contract_projection",
            "is_projection": True,
            "environment_id": "env:session:session:web:main",
            "session_mount_id": "session:web:main",
            "app_identity": "excel",
            "window_scope": "window:excel:main",
            "active_window_ref": "window:excel:main",
            "active_process_ref": "process:4242",
            "app_contract_ref": "app-contract:excel:writer",
            "app_contract_status": "verified-writer",
            "control_channel": "accessibility-tree",
            "writer_lock_scope": "workbook:weekly-report",
            "window_anchor_summary": "Excel > Weekly Report.xlsx > Sheet1!A1",
            "account_scope_ref": "windows:user:alice",
            "handoff_state": "agent-attached",
            "resume_kind": "host-companion-session",
            "manual_resume_required": False,
            "continuity_source": "registered-restorer",
            "current_gap_or_blocker": None,
        }
        self._cooperative_adapter_availability = {
            "projection_kind": "cooperative_adapter_availability_projection",
            "is_projection": True,
            "environment_id": "env:session:session:web:main",
            "session_mount_id": "session:web:main",
            "preferred_execution_path": "cooperative-native-first",
            "fallback_mode": "ui-fallback-last",
            "browser_companion": {
                "available": True,
                "status": "attached",
                "transport_ref": "transport:cdp:local",
                "provider_session_ref": "browser-session:web:main",
            },
            "document_bridge": {
                "available": True,
                "status": "ready",
                "bridge_ref": "document-bridge:office",
                "supported_families": ["spreadsheets", "documents"],
            },
            "watchers": {
                "filesystem": {
                    "available": True,
                    "status": "ready",
                },
                "downloads": {
                    "available": True,
                    "status": "healthy",
                    "download_policy": "workspace-bucket",
                },
                "notifications": {
                    "available": False,
                    "status": "disabled",
                },
            },
            "windows_app_adapters": {
                "available": True,
                "adapter_refs": ["app-adapter:excel", "app-adapter:file-explorer"],
                "app_identity": "excel",
                "control_channel": "accessibility-tree",
            },
            "available_families": [
                "browser-companion",
                "document-bridge",
                "filesystem-watcher",
                "download-watcher",
                "windows-app-adapters",
            ],
            "unavailable_families": ["notification-watcher"],
            "host_mode": "local-managed",
            "current_gap_or_blocker": None,
            "projection_note": (
                "Cooperative adapter availability is a runtime visibility projection "
                "over mounts, live handles, and surface contracts; it is not a new "
                "truth store."
            ),
        }
        self._host_event_summary = {
            "runtime_mechanism": "runtime_event_bus",
            "is_truth_store": False,
            "available": True,
            "environment_id": "env:session:session:web:main",
            "session_mount_id": "session:web:main",
            "total_relevant_events": 6,
            "returned_events": 6,
            "limit": 20,
            "supported_families": [
                "active-window",
                "modal-uac-login",
                "download-completed",
                "process-exit-restart",
                "lock-unlock",
                "network-power",
            ],
            "family_counts": {
                "active-window": 1,
                "modal-uac-login": 1,
                "download-completed": 1,
                "process-exit-restart": 1,
                "lock-unlock": 1,
                "network-power": 1,
            },
            "latest_event_by_family": {
                "active-window": {
                    "event_id": 1,
                    "event_name": "window-focus-changed",
                    "topic": "window",
                    "action": "focus-changed",
                    "created_at": now.isoformat(),
                    "severity": "medium",
                    "recommended_runtime_response": "re-observe",
                },
                "modal-uac-login": {
                    "event_id": 2,
                    "event_name": "captcha-prompt-required",
                    "topic": "desktop",
                    "action": "captcha-required",
                    "created_at": "2026-03-09T09:01:00+00:00",
                    "severity": "high",
                    "recommended_runtime_response": "handoff",
                },
                "download-completed": {
                    "event_id": 3,
                    "event_name": "download-finished",
                    "topic": "download",
                    "action": "download-completed",
                    "created_at": "2026-03-09T09:02:00+00:00",
                    "severity": "low",
                    "recommended_runtime_response": "re-observe",
                },
                "process-exit-restart": {
                    "event_id": 4,
                    "event_name": "excel-restarted",
                    "topic": "process",
                    "action": "process-restarted",
                    "created_at": "2026-03-09T09:03:00+00:00",
                    "severity": "high",
                    "recommended_runtime_response": "recover",
                },
                "lock-unlock": {
                    "event_id": 5,
                    "event_name": "desktop-unlocked",
                    "topic": "host",
                    "action": "desktop-unlocked",
                    "created_at": "2026-03-09T09:04:00+00:00",
                    "severity": "high",
                    "recommended_runtime_response": "recover",
                },
                "network-power": {
                    "event_id": 6,
                    "event_name": "network-restored",
                    "topic": "network",
                    "action": "connectivity-changed",
                    "created_at": "2026-03-09T09:05:00+00:00",
                    "severity": "medium",
                    "recommended_runtime_response": "retry",
                },
            },
            "active_alert_families": [
                "modal-uac-login",
                "process-exit-restart",
                "lock-unlock",
                "network-power",
            ],
            "latest_event": dict(latest_host_event),
        }
        self._host_events = host_events
        self._mount = EnvironmentMount(
            id="env:session:session:web:main",
            kind="session",
            display_name="session:web:main",
            ref="session:web:main",
            status="active",
            last_active_at=now,
            evidence_count=2,
            metadata={"channel": "web", "session_id": "main"},
        )
        self._session = SessionMount(
            id="session:web:main",
            environment_id=self._mount.id,
            channel="web",
            session_id="main",
            user_id="alice",
            status="active",
            created_at=now,
            last_active_at=now,
            metadata={"chat_id": "chat-1"},
            lease_status="leased",
            lease_owner="ops-agent",
            lease_token="lease-1",
            live_handle_ref="live:env:session:session:web:main:1234",
        )
        self._observation = ObservationRecord(
            evidence_id="ev-1",
            environment_ref="session:web:main",
            capability_ref="tool:execute_shell_command",
            action_summary="Ran ls",
            result_summary="Listed files",
            risk_level="auto",
            created_at=now,
        )
        self._replay = ReplayEntry(
            evidence_id="ev-1",
            replay_id="replay-1",
            replay_type="shell",
            storage_uri="file:///tmp/replay-1.txt",
            summary="Shell command output",
            created_at=now,
        )
        self._artifact = ArtifactEntry(
            evidence_id="ev-1",
            artifact_id="artifact-1",
            artifact_type="file",
            storage_uri="file:///tmp/artifact-1.txt",
            summary="Output file",
            created_at=now,
        )

    def _environment_projection(self) -> dict[str, object]:
        payload = self._mount.model_dump(mode="json")
        payload.update(
            {
                "recovery": dict(self._recovery),
                "host_contract": dict(self._host_contract),
                "seat_runtime": dict(self._seat_runtime),
                "host_companion_session": dict(self._host_companion_session),
                "browser_site_contract": dict(self._browser_site_contract),
                "desktop_app_contract": dict(self._desktop_app_contract),
                "cooperative_adapter_availability": dict(self._cooperative_adapter_availability),
                "workspace_graph": dict(self._workspace_graph),
                "host_twin": dict(self._host_twin),
                "host_event_summary": dict(self._host_event_summary),
                "host_events": [dict(item) for item in self._host_events],
            },
        )
        return payload

    def _session_projection(self) -> dict[str, object]:
        payload = self._session.model_dump(mode="json")
        payload.update(
            {
                "recovery": dict(self._recovery),
                "host_contract": dict(self._host_contract),
                "seat_runtime": dict(self._seat_runtime),
                "host_companion_session": dict(self._host_companion_session),
                "browser_site_contract": dict(self._browser_site_contract),
                "desktop_app_contract": dict(self._desktop_app_contract),
                "cooperative_adapter_availability": dict(self._cooperative_adapter_availability),
                "workspace_graph": dict(self._workspace_graph),
                "host_twin": dict(self._host_twin),
                "host_event_summary": dict(self._host_event_summary),
                "host_events": [dict(item) for item in self._host_events],
            },
        )
        return payload

    def list_environments(self, *, kind: str | None = None, limit: int | None = None):
        if kind and kind != self._mount.kind:
            return []
        mounts = [self._mount]
        if limit is not None and limit >= 0:
            return mounts[:limit]
        return mounts

    def summarize(self) -> EnvironmentSummary:
        return EnvironmentSummary(total=1, active=1, by_kind={"session": 1})

    def get_environment(self, env_id: str):
        return self._mount if env_id == self._mount.id else None

    def list_sessions(self, **_kwargs):
        return [self._session]

    def get_session(self, session_mount_id: str):
        return self._session if session_mount_id == self._session.id else None

    def force_release_session_lease(self, session_mount_id: str, *, reason: str = "forced release"):
        if session_mount_id != self._session.id:
            return None
        self._session = self._session.model_copy(
            update={
                "lease_status": "released",
                "lease_token": None,
                "live_handle_ref": None,
                "metadata": {
                    **self._session.metadata,
                    "lease_release_reason": reason,
                },
            },
        )
        return self._session

    def get_environment_detail(self, env_id: str):
        if env_id != self._mount.id:
            return None
        payload = self._environment_projection()
        payload.update(
            {
                "sessions": [self._session_projection()],
                "observations": [self._observation.model_dump(mode="json")],
                "replays": [self._replay.model_dump(mode="json")],
                "artifacts": [self._artifact.model_dump(mode="json")],
                "stats": {
                    "session_count": 1,
                    "observation_count": 1,
                    "replay_count": 1,
                    "artifact_count": 1,
                },
            },
        )
        return FakeRuntimeSurfaceProjection(payload)

    def get_session_detail(self, session_mount_id: str):
        if session_mount_id != self._session.id:
            return None
        payload = self._session_projection()
        payload.update(
            {
                "environment": self._environment_projection(),
                "observations": [self._observation.model_dump(mode="json")],
                "replays": [self._replay.model_dump(mode="json")],
                "artifacts": [self._artifact.model_dump(mode="json")],
                "stats": {
                    "observation_count": 1,
                    "replay_count": 1,
                    "artifact_count": 1,
                },
            },
        )
        return FakeRuntimeSurfaceProjection(payload)

    def list_observations(self, *, environment_ref: str | None, limit: int = 20):
        if environment_ref != self._observation.environment_ref:
            return []
        return [self._observation]

    def get_observation(self, observation_id: str):
        if observation_id != self._observation.evidence_id:
            return None
        return self._observation

    def list_replays(self, *, environment_ref: str | None, limit: int = 20):
        if environment_ref != self._observation.environment_ref:
            return []
        return [self._replay]

    def get_replay(self, replay_id: str):
        if replay_id != self._replay.replay_id:
            return None
        return self._replay

    async def execute_replay(self, replay_id: str, *, actor: str = "runtime-center"):
        if replay_id != self._replay.replay_id:
            raise KeyError(f"Replay '{replay_id}' not found")
        return {
            "replay": self._replay.model_dump(mode="json"),
            "result": {
                "task_id": "task-replay-1",
                "phase": "completed",
                "success": True,
                "summary": f"Executed replay as {actor}",
            },
        }

    def list_artifacts(self, *, environment_ref: str | None, limit: int = 20):
        if environment_ref != self._observation.environment_ref:
            return []
        return [self._artifact]

    def get_artifact(self, artifact_id: str):
        if artifact_id != self._artifact.artifact_id:
            return None
        return self._artifact


class FakeMutationDispatcher:
    def __init__(self, heartbeat_state: dict[str, HeartbeatConfig] | None = None) -> None:
        self._heartbeat_state = heartbeat_state or {}
        self._tasks: dict[str, object] = {}

    def submit(self, task) -> KernelResult:
        self._tasks[task.id] = task
        return KernelResult(
            task_id=task.id,
            success=True,
            phase="executing",
            summary="Admitted",
        )

    async def execute_task(self, task_id: str) -> KernelResult:
        task = self._tasks[task_id]
        payload = getattr(task, "payload", {}) or {}
        heartbeat_payload = payload.get("heartbeat")
        if heartbeat_payload is not None:
            self._heartbeat_state["config"] = HeartbeatConfig.model_validate(heartbeat_payload)
        return KernelResult(
            task_id=task_id,
            success=True,
            phase="completed",
            summary="Completed",
        )


class FakeDecisionDispatcher:
    async def approve_decision(
        self,
        decision_id: str,
        *,
        resolution: str | None = None,
        execute: bool | None = None,
    ) -> KernelResult:
        if decision_id == "missing":
            raise KeyError("Decision request 'missing' not found")
        if decision_id == "closed":
            raise ValueError(
                "Decision request 'closed' is in status 'approved', expected 'open' or 'reviewing'",
            )
        return KernelResult(
            task_id="task-1",
            success=True,
            phase="completed",
            summary=resolution or "Approved",
            decision_request_id=decision_id,
        )

    def reject_decision(
        self,
        decision_id: str,
        *,
        resolution: str | None = None,
    ) -> KernelResult:
        if decision_id == "missing":
            raise KeyError("Decision request 'missing' not found")
        if decision_id == "closed":
            raise ValueError(
                "Decision request 'closed' is in status 'approved', expected 'open' or 'reviewing'",
            )
        return KernelResult(
            task_id="task-1",
            success=False,
            phase="cancelled",
            summary=resolution or "Rejected",
            decision_request_id=decision_id,
        )


class FakeApproveDecisionRequestRepository:
    def __init__(self, *, decision_type: str) -> None:
        self._decision_type = decision_type

    def get_decision_request(self, decision_id: str):
        if decision_id != "decision-1":
            return None
        return DecisionRequestRecord(
            id=decision_id,
            task_id="task-1",
            decision_type=self._decision_type,
            risk_level="confirm",
            summary="Resume guarded browser workflow",
            status="approved",
            requested_by="ops-agent",
        )


class FakeQueryExecutionService:
    def __init__(self) -> None:
        self.resume_calls: list[str] = []

    async def resume_query_tool_confirmation(self, *, decision_request_id: str) -> dict[str, object]:
        self.resume_calls.append(decision_request_id)
        return {
            "resumed": True,
            "decision_request_id": decision_request_id,
        }


class FakeTaskRepository:
    def get_task(self, task_id: str):
        if task_id != "task-1":
            return None
        return type(
            "TaskRecord",
            (),
            {
                "model_dump": lambda self, mode="json": {
                    "id": "task-1",
                    "goal_id": "goal-1",
                    "title": "Refresh competitor brief",
                    "summary": "Collect the latest competitor notes.",
                    "task_type": "task",
                    "status": "running",
                    "owner_agent_id": "ops-agent",
                }
            },
        )()


class FakeGoalService:
    def get_goal(self, goal_id: str):
        if goal_id != "goal-1":
            return None
        return type(
            "GoalRecord",
            (),
            {
                "model_dump": lambda self, mode="json": {
                    "id": "goal-1",
                    "title": "Launch runtime center",
                    "summary": "Make goals visible across runtime center and agent workbench.",
                    "status": "active",
                }
            },
        )()


class FakePredictionService:
    def get_runtime_capability_optimization_overview(
        self,
        *,
        industry_instance_id: str | None = None,
        owner_scope: str | None = None,
        limit: int = 12,
        history_limit: int = 8,
        window_days: int = 14,
    ) -> dict[str, object]:
        assert industry_instance_id is None
        assert owner_scope is None
        assert limit == 12
        assert history_limit == 8
        assert window_days == 14
        return {
            "generated_at": "2026-03-16T12:00:00+00:00",
            "summary": {
                "total_items": 2,
                "actionable_count": 1,
                "history_count": 1,
                "case_count": 2,
                "missing_capability_count": 1,
                "underperforming_capability_count": 0,
                "trial_count": 1,
                "rollout_count": 0,
                "retire_count": 1,
                "waiting_confirm_count": 0,
                "manual_only_count": 0,
                "executed_count": 1,
            },
            "actionable": [
                {
                    "case": {
                        "case_id": "case-gap-1",
                        "title": "Capability gap case",
                        "status": "open",
                        "case_kind": "cycle",
                        "updated_at": "2026-03-16T11:00:00+00:00",
                    },
                    "recommendation": {
                        "recommendation": {
                            "recommendation_id": "rec-gap-1",
                            "case_id": "case-gap-1",
                            "recommendation_type": "capability_recommendation",
                            "title": "Trial remote skill",
                            "summary": "Run a governed remote-skill trial.",
                            "priority": 91,
                            "confidence": 0.93,
                            "risk_level": "confirm",
                            "action_kind": "system:trial_remote_skill_assignment",
                            "executable": True,
                            "auto_eligible": False,
                            "auto_executed": False,
                            "status": "proposed",
                            "target_agent_id": "industry-solution-lead-demo",
                            "target_capability_ids": ["skill:nextgen_outreach"],
                            "action_payload": {},
                            "metadata": {
                                "gap_kind": "missing_capability",
                                "optimization_stage": "trial",
                                "requested_capability_ids": [
                                    "skill:nextgen_outreach",
                                ],
                            },
                            "created_at": "2026-03-16T10:58:00+00:00",
                            "updated_at": "2026-03-16T11:00:00+00:00",
                        },
                        "decision": None,
                        "routes": {
                            "case": "/api/predictions/case-gap-1",
                            "execute": (
                                "/api/predictions/case-gap-1/recommendations/"
                                "rec-gap-1/execute"
                            ),
                        },
                    },
                    "status_bucket": "actionable",
                    "routes": {
                        "case": "/api/predictions/case-gap-1",
                        "execute": (
                            "/api/predictions/case-gap-1/recommendations/"
                            "rec-gap-1/execute"
                        ),
                    },
                },
            ],
            "history": [
                {
                    "case": {
                        "case_id": "case-gap-2",
                        "title": "Capability retirement case",
                        "status": "closed",
                        "case_kind": "cycle",
                        "updated_at": "2026-03-16T09:00:00+00:00",
                    },
                    "recommendation": {
                        "recommendation": {
                            "recommendation_id": "rec-gap-2",
                            "case_id": "case-gap-2",
                            "recommendation_type": "capability_recommendation",
                            "title": "Retire legacy skill",
                            "summary": "Disable the old capability after trial success.",
                            "priority": 78,
                            "confidence": 0.88,
                            "risk_level": "guarded",
                            "action_kind": "system:set_capability_enabled",
                            "executable": True,
                            "auto_eligible": False,
                            "auto_executed": False,
                            "status": "executed",
                            "target_agent_id": "industry-solution-lead-demo",
                            "target_capability_ids": [
                                "skill:legacy_outreach",
                                "skill:nextgen_outreach",
                            ],
                            "action_payload": {},
                            "metadata": {
                                "gap_kind": "capability_retirement",
                                "optimization_stage": "retire",
                                "old_capability_id": "skill:legacy_outreach",
                                "new_capability_id": "skill:nextgen_outreach",
                            },
                            "created_at": "2026-03-16T08:40:00+00:00",
                            "updated_at": "2026-03-16T09:00:00+00:00",
                        },
                        "decision": None,
                        "routes": {
                            "case": "/api/predictions/case-gap-2",
                        },
                    },
                    "status_bucket": "history",
                    "routes": {
                        "case": "/api/predictions/case-gap-2",
                    },
                },
            ],
            "routes": {
                "predictions": "/api/predictions",
            },
        }


class FakeDecisionRequestRepository:
    def list_decision_requests(self, *, task_id: str | None = None, status: str | None = None):
        if task_id == "patch-1":
            return [
                type(
                    "DecisionRequestRecord",
                    (),
                    {
                        "model_dump": lambda self, mode="json": {
                            "id": "decision-patch-1",
                            "task_id": "patch-1",
                            "status": "approved",
                        }
                    },
                )()
            ]
        return []


class FakeTurnExecutor:
    def __init__(self) -> None:
        self.stream_calls: list[dict[str, object]] = []

    def legacy_prepare_chat_turn_removed(self, request_payload):
        raise AssertionError("prepare_chat_turn is removed")
        return {
            "mode": "task",
            "request_id": getattr(request_payload, "id", None) or "req-task",
            "thread_id": "removed-thread:req-task",
            "thread_name": "执行流程：登录京东后台并整理商品上架流程",
            "thread_user_id": "ops-user",
            "thread_channel": "console",
            "thread_meta": {
                "session_kind": "removed",
                "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
                "task_id": "removed-query-task",
                "task_title": "执行流程：登录京东后台并整理商品上架流程",
                "runtime_session_id": "removed-session:req-task",
            },
            "session_id": "removed-session:req-task",
            "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
            "task_id": "removed-query-task",
            "task_title": "执行流程：登录京东后台并整理商品上架流程",
            "task_route": "/api/runtime-center/tasks/removed-query-task",
            "skip_kernel_admission": True,
            "request_updates": {
                "session_id": "removed-session:req-task",
                "session_kind": "removed",
                "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
                "task_id": "removed-query-task",
                "task_title": "执行流程：登录京东后台并整理商品上架流程",
            },
        }

    async def stream_request(
        self,
        request_payload,
        *,
        kernel_task_id: str | None = None,
        skip_kernel_admission: bool = False,
    ):
        self.stream_calls.append(
            {
                "request_payload": request_payload,
                "kernel_task_id": kernel_task_id,
                "skip_kernel_admission": skip_kernel_admission,
            },
        )
        yield {
            "object": "response",
            "status": "completed",
            "kernel_task_id": kernel_task_id,
            "skip_kernel_admission": skip_kernel_admission,
        }


def build_runtime_center_app() -> FastAPI:
    app = FastAPI()
    app.include_router(runtime_center_router)
    return app


def build_routines_app() -> FastAPI:
    app = FastAPI()
    app.include_router(routines_router)
    evidence_ledger = EvidenceLedger()
    capability_service = CapabilityService(evidence_ledger=evidence_ledger)
    app.state.evidence_ledger = evidence_ledger
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = KernelDispatcher(capability_service=capability_service)
    return app


def make_job(job_id: str, *, enabled: bool = True) -> CronJobSpec:
    return CronJobSpec(
        id=job_id,
        name=f"Job {job_id}",
        enabled=enabled,
        schedule=ScheduleSpec(cron="0 9 * * 1", timezone="UTC"),
        task_type="text",
        text="Ship weekly summary",
        dispatch=DispatchSpec(
            target=DispatchTarget(user_id="alice", session_id=f"cron:{job_id}"),
        ),
    )


__all__ = [name for name in globals() if not name.startswith("__")]


