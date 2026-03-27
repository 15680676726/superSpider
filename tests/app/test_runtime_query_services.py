# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from copaw.app.crons.models import (
    CronJobSpec,
    DispatchSpec,
    DispatchTarget,
    ScheduleSpec,
)
from copaw.app.crons.repo import StateBackedJobRepository
from copaw.app.runtime_center import (
    RuntimeCenterEvidenceQueryService,
    RuntimeCenterStateQueryService,
)
from copaw.evidence import EvidenceLedger, EvidenceRecord
from copaw.state import (
    DecisionRequestRecord,
    SQLiteStateStore,
    TaskRecord,
    TaskRuntimeRecord,
    WorkContextRecord,
)
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteScheduleRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
    SqliteWorkContextRepository,
)


def _make_job(job_id: str) -> CronJobSpec:
    return CronJobSpec(
        id=job_id,
        name=f"Job {job_id}",
        enabled=True,
        schedule=ScheduleSpec(cron="0 9 * * 1", timezone="UTC"),
        task_type="text",
        text="Ship weekly summary",
        dispatch=DispatchSpec(
            target=DispatchTarget(user_id="founder", session_id=f"cron:{job_id}"),
        ),
    )


def test_runtime_query_services_read_state_backed_surfaces(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    schedule_repository = SqliteScheduleRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    work_context_repository = SqliteWorkContextRepository(state_store)
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")

    async def seed() -> None:
        job_repo = StateBackedJobRepository(
            schedule_repository=schedule_repository,
        )
        timestamp = datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc)
        work_context_repository.upsert_context(
            WorkContextRecord(
                id="ctx-industry-control",
                title="Acme Pets execution core",
                summary="Primary continuous work boundary for the execution core control thread.",
                context_type="industry-control-thread",
                status="active",
                context_key="control-thread:industry-chat:industry-1:execution-core",
                owner_scope="industry-1-scope",
                owner_agent_id="copaw-agent-runner",
                industry_instance_id="industry-1",
                primary_thread_id="industry-chat:industry-1:execution-core",
            ),
        )
        task_repository.upsert_task(
            TaskRecord(
                id="query:session:console:founder:console:chat-1",
                title="Founder sync",
                summary="Interactive runtime thread for founder console chat.",
                task_type="interactive-query",
                status="completed",
                owner_agent_id="copaw-agent-runner",
                work_context_id="ctx-industry-control",
                created_at=timestamp,
                updated_at=timestamp,
            ),
        )
        task_repository.upsert_task(
            TaskRecord(
                id="query:session:console:founder:ops-followup-1",
                title="Follow the merchandising thread",
                summary="Continue the task thread without mixing unrelated memory.",
                task_type="system:dispatch_query",
                status="running",
                owner_agent_id="ops-agent",
                work_context_id="ctx-industry-control",
                acceptance_criteria=json.dumps(
                    {
                        "kind": "kernel-task-meta-v1",
                        "trace_id": "trace:task-thread-1",
                        "payload": {
                            "request": {
                                "channel": "console",
                                "user_id": "founder",
                                "session_id": "industry-chat:industry-1:execution-core",
                                "agent_id": "ops-agent",
                                "industry_instance_id": "industry-1",
                                "industry_label": "Industry Team",
                                "owner_scope": "industry-1-scope",
                                "task_title": "Merchandising task thread",
                                "control_thread_id": "industry-chat:industry-1:execution-core",
                            },
                            "meta": {
                                "task_title": "Merchandising task thread",
                                "control_thread_id": "industry-chat:industry-1:execution-core",
                            },
                        },
                    },
                ),
                created_at=timestamp,
                updated_at=timestamp,
            ),
        )
        task_repository.upsert_task(
            TaskRecord(
                id="query:session:console:founder:industry-chat:industry-1:execution-core",
                title="What is the execution core doing?",
                summary="Plain control-thread status follow-up.",
                task_type="system:dispatch_query",
                status="completed",
                owner_agent_id="copaw-agent-runner",
                work_context_id="ctx-industry-control",
                acceptance_criteria=json.dumps(
                    {
                        "kind": "kernel-task-meta-v1",
                        "trace_id": "trace:control-query-1",
                        "payload": {
                            "request": {
                                "channel": "console",
                                "user_id": "founder",
                                "session_id": "industry-chat:industry-1:execution-core",
                                "agent_id": "copaw-agent-runner",
                                "industry_instance_id": "industry-1",
                                "industry_label": "Industry Team",
                                "industry_role_id": "execution-core",
                                "session_kind": "industry-agent-chat",
                                "control_thread_id": "industry-chat:industry-1:execution-core",
                            },
                        },
                    },
                ),
                created_at=timestamp,
                updated_at=timestamp,
            ),
        )
        task_repository.upsert_task(
            TaskRecord(
                id="task-child-1",
                title="Collect evidence",
                summary="Gather the latest screenshots.",
                task_type="system:dispatch_query",
                status="completed",
                owner_agent_id="research-agent",
                parent_task_id="query:session:console:founder:ops-followup-1",
                work_context_id="ctx-industry-control",
                created_at=timestamp,
                updated_at=timestamp,
            ),
        )
        task_runtime_repository.upsert_runtime(
            TaskRuntimeRecord(
                task_id="query:session:console:founder:console:chat-1",
                runtime_status="terminated",
                current_phase="completed",
                risk_level="auto",
                active_environment_id="session:console:console:chat-1",
                last_result_summary="Summarized backlog.",
                last_owner_agent_id="copaw-agent-runner",
                updated_at=timestamp,
            ),
        )
        task_runtime_repository.upsert_runtime(
            TaskRuntimeRecord(
                task_id="query:session:console:founder:ops-followup-1",
                runtime_status="active",
                current_phase="executing",
                risk_level="guarded",
                active_environment_id="session:console:industry-chat:industry-1:execution-core",
                last_result_summary="Drafted the current task-thread action summary.",
                last_owner_agent_id="ops-agent",
                updated_at=timestamp,
            ),
        )
        task_runtime_repository.upsert_runtime(
            TaskRuntimeRecord(
                task_id="query:session:console:founder:industry-chat:industry-1:execution-core",
                runtime_status="terminated",
                current_phase="completed",
                risk_level="auto",
                active_environment_id="session:console:industry-chat:industry-1:execution-core",
                last_result_summary="The execution core is handling reports and backlog.",
                last_owner_agent_id="copaw-agent-runner",
                updated_at=timestamp,
            ),
        )
        task_runtime_repository.upsert_runtime(
            TaskRuntimeRecord(
                task_id="task-child-1",
                runtime_status="terminated",
                current_phase="completed",
                risk_level="auto",
                last_result_summary="Stored the latest screenshots.",
                last_owner_agent_id="research-agent",
                updated_at=timestamp,
            ),
        )
        await job_repo.upsert_job(_make_job("job-1"))

    asyncio.run(seed())

    decision = decision_request_repository.upsert_decision_request(
        DecisionRequestRecord(
            task_id="query:session:console:founder:console:chat-1",
            decision_type="guarded-browser-action",
            risk_level="guarded",
            summary="Approve guarded browser action",
            requested_by="ops-agent",
        ),
    )
    evidence = evidence_ledger.append(
        EvidenceRecord(
            task_id="query:session:console:founder:console:chat-1",
            actor_ref="ops-agent",
            capability_ref="system:dispatch_query",
            risk_level="auto",
            action_summary="query completed",
            result_summary="Summarized backlog.",
        ),
    )
    task_thread_decision = decision_request_repository.upsert_decision_request(
        DecisionRequestRecord(
            task_id="query:session:console:founder:ops-followup-1",
            decision_type="guarded-browser-action",
            risk_level="guarded",
            summary="Approve task-thread external action",
            requested_by="ops-agent",
        ),
    )
    task_thread_evidence = evidence_ledger.append(
        EvidenceRecord(
            task_id="query:session:console:founder:ops-followup-1",
            actor_ref="ops-agent",
            capability_ref="system:dispatch_query",
            risk_level="guarded",
            action_summary="task thread progressed",
            result_summary="Stored the current task-thread checkpoint.",
        ),
    )
    task_thread_failed_a = evidence_ledger.append(
        EvidenceRecord(
            task_id="query:session:console:founder:ops-followup-1",
            actor_ref="ops-agent",
            capability_ref="browser_use",
            risk_level="guarded",
            action_summary="Retry storefront login",
            result_summary="Login failed because the OTP expired.",
        ),
    )
    task_thread_failed_b = evidence_ledger.append(
        EvidenceRecord(
            task_id="query:session:console:founder:ops-followup-1",
            actor_ref="ops-agent",
            capability_ref="browser_use",
            risk_level="guarded",
            action_summary="Retry storefront login",
            result_summary="Login failed again because the OTP expired.",
        ),
    )

    class StubEnvironmentService:
        def get_session_detail(
            self,
            session_mount_id: str,
            *,
            limit: int = 20,
        ) -> dict[str, object] | None:
            _ = limit
            if session_mount_id != "session:console:industry-chat:industry-1:execution-core":
                return None
            return {
                "id": session_mount_id,
                "recovery": {
                    "status": "pending",
                    "resume_kind": "resume-environment",
                    "mode": "resume-environment",
                },
                "cooperative_adapter_availability": {
                    "status": "available",
                    "adapters": ["desktop", "browser"],
                },
                "host_contract": {
                    "host_mode": "symbiotic",
                    "current_gap_or_blocker": "uac-prompt",
                    "handoff_state": "handoff-required",
                    "handoff_reason": "uac-prompt",
                    "verification_channel": "runtime-center-self-check",
                },
                "host_event_summary": {
                    "last_event": "uac_prompt",
                    "latest_event": {
                        "event_name": "uac_prompt",
                        "topic": "system",
                        "action": "recovery",
                        "payload": {
                            "prompt_kind": "uac",
                            "window_title": "User Account Control",
                        },
                    },
                    "counts_by_topic": {
                        "system": 2,
                        "browser": 1,
                    },
                    "pending_recovery_events": [
                        {
                            "event_name": "uac_prompt",
                            "checkpoint": {
                                "resume_kind": "resume-environment",
                            },
                        },
                    ],
                },
                "seat_runtime": {
                    "seat_ref": "env:desktop:industry-core",
                },
                "workspace_graph": {
                    "workspace_id": "workspace:industry-core",
                    "projection_kind": "workspace_graph_projection",
                    "download_status": {
                        "bucket_refs": ["download-bucket:industry-core"],
                        "active_bucket_ref": "download-bucket:industry-core",
                        "download_policy": "download-bucket:industry-core",
                        "download_verification": True,
                    },
                    "surface_contracts": {
                        "browser_active_site": "jd:seller-center",
                        "browser_site_contract_status": "verified-writer",
                        "desktop_app_identity": "excel",
                        "desktop_app_contract_status": "handoff-required",
                    },
                    "locks": [
                        {
                            "resource_ref": "excel:writer-lock",
                            "writer_lock": {
                                "status": "held",
                                "owner_agent_id": "ops-agent",
                            },
                        },
                    ],
                    "surfaces": {
                        "browser": {
                            "active_tab": {
                                "tab_id": "tab-7",
                                "site": "jd:seller-center",
                            },
                        },
                        "desktop": {
                            "active_window": {
                                "app_identity": "excel",
                                "window_scope": "window:excel:main",
                            },
                        },
                    },
                    "latest_host_event_summary": {
                        "event_name": "uac_prompt",
                        "severity": "guarded",
                    },
                },
                "browser_site_contract": {
                    "browser_mode": "tab-attached",
                    "active_site": "jd:seller-center",
                    "authenticated_continuation": True,
                    "download_verification": True,
                    "save_reopen_verification": True,
                    "download_bucket_refs": ["download-bucket:industry-core"],
                },
                "desktop_app_contract": {
                    "app_identity": "excel",
                    "window_scope": "window:excel:main",
                    "current_gap_or_blocker": "uac-prompt",
                    "blocker_event_family": "modal-uac-login",
                    "recovery_mode": "resume-environment",
                },
                "host_twin": {
                    "seat_owner": {
                        "owner_ref": "human-operator:alice",
                        "label": "Alice",
                    },
                    "writable_surfaces": [
                        {
                            "surface_ref": "window:excel:main",
                            "label": "Orders workbook",
                        },
                    ],
                    "legal_recovery_path": {
                        "mode": "resume-environment",
                        "summary": "resume-environment via Orders workbook checkpoint",
                    },
                    "trusted_anchors": [
                        {
                            "anchor_ref": "excel://Orders!A1",
                            "label": "Orders workbook row 1",
                        },
                    ],
                    "active_blocker_families": [
                        "modal-uac-login",
                        "writer-lock",
                    ],
                },
            }

        def get_environment_detail(
            self,
            env_id: str,
            *,
            limit: int = 20,
        ) -> dict[str, object] | None:
            _ = env_id, limit
            return None

    state_query = RuntimeCenterStateQueryService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        schedule_repository=schedule_repository,
        work_context_repository=work_context_repository,
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
        environment_service=StubEnvironmentService(),
    )
    evidence_query = RuntimeCenterEvidenceQueryService(
        evidence_ledger=evidence_ledger,
    )

    tasks = state_query.list_tasks(limit=10)
    assert tasks[0]["id"] == "query:session:console:founder:console:chat-1"
    assert tasks[0]["trace_id"] == "trace:query:session:console:founder:console:chat-1"
    assert tasks[0]["summary"] == "Summarized backlog."
    assert tasks[0]["route"] == "/api/runtime-center/tasks/query:session:console:founder:console:chat-1"
    assert tasks[0]["context_key"] == "control-thread:industry-chat:industry-1:execution-core"
    assert tasks[0]["work_context"]["id"] == "ctx-industry-control"
    assert tasks[0]["work_context"]["context_key"] == "control-thread:industry-chat:industry-1:execution-core"

    task_detail = state_query.get_task_detail("query:session:console:founder:console:chat-1")
    assert task_detail is not None
    assert task_detail["trace_id"] == "trace:query:session:console:founder:console:chat-1"
    assert task_detail["task"]["id"] == "query:session:console:founder:console:chat-1"
    assert task_detail["decisions"][0]["id"] == decision.id
    assert task_detail["decisions"][0]["trace_id"] == "trace:query:session:console:founder:console:chat-1"
    assert task_detail["evidence"][0]["id"] == evidence.id
    assert task_detail["evidence"][0]["trace_id"] == "trace:query:session:console:founder:console:chat-1"
    assert task_detail["stats"]["decision_count"] == 1
    assert task_detail["stats"]["evidence_count"] == 1
    assert task_detail["work_context"]["id"] == "ctx-industry-control"

    task_review = state_query.get_task_review(
        "query:session:console:founder:ops-followup-1",
    )
    assert task_review is not None
    assert task_review["review"]["review_route"] == "/api/runtime-center/tasks/query:session:console:founder:ops-followup-1/review"
    assert task_review["review"]["evidence_count"] == 3
    assert task_review["review"]["pending_decision_count"] == 1
    assert task_review["review"]["current_stage"] == "Follow the merchandising thread [executing]"
    assert any("Retry storefront login" in item for item in task_review["review"]["recent_failures"])
    assert any("task thread progressed" in item for item in task_review["review"]["effective_actions"])
    assert any("failed 2 times" in item for item in task_review["review"]["avoid_repeats"])
    assert (
        task_review["review"]["execution_runtime"]["workspace"]["workspace_id"]
        == "workspace:industry-core"
    )
    assert (
        task_review["review"]["execution_runtime"]["workspace"]["projection_kind"]
        == "workspace_graph_projection"
    )
    assert (
        task_review["review"]["execution_runtime"]["workspace"]["locks"][0]["resource_ref"]
        == "excel:writer-lock"
    )
    assert (
        task_review["review"]["execution_runtime"]["workspace"]["locks"][0]["writer_lock"]["owner_agent_id"]
        == "ops-agent"
    )
    assert (
        task_review["review"]["execution_runtime"]["workspace"]["locks"][0]["writer_lock"]["status"]
        == "held"
    )
    assert (
        task_review["review"]["execution_runtime"]["workspace"]["surfaces"]["browser"]["active_tab"]["tab_id"]
        == "tab-7"
    )
    assert (
        task_review["review"]["execution_runtime"]["workspace"]["surfaces"]["desktop"]["active_window"]["window_scope"]
        == "window:excel:main"
    )
    assert (
        task_review["review"]["execution_runtime"]["workspace"]["latest_host_event_summary"]["severity"]
        == "guarded"
    )
    assert (
        task_review["review"]["execution_runtime"]["workspace"]["latest_host_event_summary"]["event_name"]
        == "uac_prompt"
    )
    assert (
        task_review["review"]["execution_runtime"]["workspace"]["download_status"]["active_bucket_ref"]
        == "download-bucket:industry-core"
    )
    assert (
        task_review["review"]["execution_runtime"]["workspace"]["surface_contracts"]["desktop_app_identity"]
        == "excel"
    )
    assert (
        task_review["review"]["execution_runtime"]["workspace"]["surface_contracts"]["browser_site_contract_status"]
        == "verified-writer"
    )
    assert (
        task_review["review"]["execution_runtime"]["workspace"]["surface_contracts"]["desktop_app_contract_status"]
        == "handoff-required"
    )
    assert (
        task_review["review"]["execution_runtime"]["cooperative_adapter_availability"]["status"]
        == "available"
    )
    assert (
        task_review["review"]["execution_runtime"]["host"]["current_gap_or_blocker"]
        == "uac-prompt"
    )
    assert (
        task_review["review"]["execution_runtime"]["recovery"]["mode"]
        == "resume-environment"
    )
    assert (
        task_review["review"]["execution_runtime"]["host_event_summary"]["latest_event"]["event_name"]
        == "uac_prompt"
    )
    assert (
        task_review["review"]["execution_runtime"]["host_event_summary"]["latest_event"]["payload"]["window_title"]
        == "User Account Control"
    )
    assert (
        task_review["review"]["execution_runtime"]["host_event_summary"]["counts_by_topic"]["system"]
        == 2
    )
    assert (
        task_review["review"]["execution_runtime"]["host_event_summary"]["pending_recovery_events"][0]["checkpoint"]["resume_kind"]
        == "resume-environment"
    )
    assert (
        task_review["review"]["execution_runtime"]["seat_runtime"]["seat_ref"]
        == "env:desktop:industry-core"
    )
    assert (
        task_review["review"]["execution_runtime"]["browser_site_contract"]["active_site"]
        == "jd:seller-center"
    )
    assert (
        task_review["review"]["execution_runtime"]["browser_site_contract"]["authenticated_continuation"]
        is True
    )
    assert (
        task_review["review"]["execution_runtime"]["browser_site_contract"]["download_verification"]
        is True
    )
    assert (
        task_review["review"]["execution_runtime"]["desktop_app_contract"]["app_identity"]
        == "excel"
    )
    assert (
        task_review["review"]["execution_runtime"]["desktop_app_contract"]["current_gap_or_blocker"]
        == "uac-prompt"
    )
    assert (
        task_review["review"]["execution_runtime"]["host_twin"]["seat_owner"]["owner_ref"]
        == "human-operator:alice"
    )
    assert (
        task_review["review"]["execution_runtime"]["host_twin"]["legal_recovery_path"]["mode"]
        == "resume-environment"
    )
    assert (
        task_review["review"]["continuity"]["handoff"]["state"]
        == "handoff-required"
    )
    assert (
        task_review["review"]["continuity"]["handoff"]["owner_ref"]
        == "human-operator:alice"
    )
    assert (
        task_review["review"]["continuity"]["verification"]["latest_anchor"]
        == "excel://Orders!A1"
    )
    assert any(
        "Orders workbook" in action
        for action in task_review["review"]["next_actions"]
    )
    assert any(
        "modal-uac-login" in risk
        for risk in task_review["review"]["risks"]
    )
    assert task_thread_decision.id

    work_contexts = state_query.list_work_contexts(limit=10)
    assert len(work_contexts) == 1
    assert work_contexts[0]["id"] == "ctx-industry-control"
    assert work_contexts[0]["task_count"] == 4
    assert work_contexts[0]["active_task_count"] == 1

    work_context_detail = state_query.get_work_context_detail("ctx-industry-control")
    assert work_context_detail is not None
    assert work_context_detail["work_context"]["context_key"] == (
        "control-thread:industry-chat:industry-1:execution-core"
    )
    assert work_context_detail["stats"]["task_count"] == 4
    assert work_context_detail["stats"]["active_task_count"] == 1
    assert work_context_detail["tasks"][0]["context_key"] == (
        "control-thread:industry-chat:industry-1:execution-core"
    )
    assert work_context_detail["tasks"][0]["work_context"]["id"] == "ctx-industry-control"
    assert "industry-chat:industry-1:execution-core" in work_context_detail["threads"]

    schedules = state_query.list_schedules(limit=10)
    assert len(schedules) == 1
    schedule = schedules[0]
    assert schedule["id"] == "job-1"
    assert schedule["title"] == "Job job-1"
    assert schedule["status"] == "scheduled"
    assert schedule["owner"] == "founder"
    assert schedule["cron"] == "0 9 * * 1"
    assert schedule["enabled"] is True
    assert schedule["task_type"] == "text"
    assert schedule["last_run_at"] is None
    assert schedule["next_run_at"] is None
    assert schedule["last_error"] is None
    assert schedule["route"] == "/api/runtime-center/schedules/job-1"
    assert schedule["actions"] == {
        "run": "/api/runtime-center/schedules/job-1/run",
        "delete": "/api/runtime-center/schedules/job-1",
        "pause": "/api/runtime-center/schedules/job-1/pause",
    }

    decisions = state_query.list_decision_requests(limit=10)
    founder_decision = next(item for item in decisions if item["id"] == decision.id)
    assert founder_decision["trace_id"] == "trace:query:session:console:founder:console:chat-1"
    assert founder_decision["task_route"] == "/api/runtime-center/tasks/query:session:console:founder:console:chat-1"
    assert founder_decision["actions"]["approve"].endswith(f"/{decision.id}/approve")

    assert evidence_query.count_records() == 4
    recent = evidence_query.list_recent_records(limit=10)
    assert {item.id for item in recent} == {
        evidence.id,
        task_thread_evidence.id,
        task_thread_failed_a.id,
        task_thread_failed_b.id,
    }
