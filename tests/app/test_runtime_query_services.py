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
from copaw.app.runtime_center.task_list_projection import RuntimeCenterTaskListProjector
from copaw.app.runtime_center.work_context_projection import (
    RuntimeCenterWorkContextProjector,
)
from copaw.evidence import EvidenceLedger, EvidenceRecord
from copaw.kernel.models import KernelTask
from copaw.kernel.persistence import KernelTaskStore
from copaw.state import (
    DecisionRequestRecord,
    HumanAssistTaskRecord,
    SQLiteStateStore,
    TaskRecord,
    TaskRuntimeRecord,
    WorkContextRecord,
)
from copaw.state.human_assist_task_service import HumanAssistTaskService
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteHumanAssistTaskRepository,
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


def _make_human_assist_task(*, task_id: str = "task-1") -> HumanAssistTaskRecord:
    timestamp = datetime(2026, 3, 28, 9, 0, tzinfo=timezone.utc)
    return HumanAssistTaskRecord(
        id=f"human-assist:{task_id}",
        industry_instance_id="industry-1",
        assignment_id="assignment-1",
        task_id=task_id,
        chat_thread_id="industry-chat:industry-1:execution-core",
        title="Upload receipt proof",
        summary="Host proof is required before the task can resume.",
        task_type="evidence-submit",
        reason_code="blocked-by-proof",
        reason_summary="The runtime cannot verify the payment receipt alone.",
        required_action="Upload the receipt in chat and say the task is finished.",
        submission_mode="chat-message",
        acceptance_mode="evidence_verified",
        acceptance_spec={
            "version": "v1",
            "hard_anchors": ["receipt"],
            "result_anchors": ["uploaded"],
            "negative_anchors": ["missing"],
            "failure_hint": "Provide receipt proof before acceptance.",
        },
        reward_preview={"sync_points": 2, "familiarity_exp": 1},
        resume_checkpoint_ref="checkpoint:receipt-upload",
        status="created",
        created_at=timestamp,
        updated_at=timestamp,
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
                    "browser_mode": "attach-existing-session",
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
                    "ownership": {
                        "seat_owner_agent_id": "ops-agent",
                        "handoff_owner_ref": "human-operator:alice",
                        "workspace_scope": "project:copaw",
                    },
                    "surface_mutability": {
                        "desktop_app": {
                            "surface_ref": "window:excel:main",
                            "mutability": "blocked",
                            "safe_to_mutate": False,
                            "blocker_family": "modal-uac-login",
                        },
                    },
                    "blocked_surfaces": [
                        {
                            "surface_kind": "desktop_app",
                            "surface_ref": "window:excel:main",
                            "reason": "captcha-required",
                            "event_family": "modal-uac-login",
                        },
                    ],
                    "trusted_anchors": [
                        {
                            "surface_ref": "window:excel:main",
                            "anchor_ref": "excel://Orders!A1",
                            "label": "Orders workbook row 1",
                        },
                    ],
                    "legal_recovery": {
                        "path": "handoff",
                        "checkpoint_ref": "checkpoint:captcha:orders",
                        "resume_kind": "resume-environment",
                        "verification_channel": "runtime-center-self-check",
                        "return_condition": "captcha-cleared",
                    },
                    "active_blocker_families": [
                        "modal-uac-login",
                        "writer-lock",
                    ],
                    "app_family_twins": {
                        "office_document": {
                            "active": True,
                            "family_kind": "office_document",
                            "surface_ref": "window:excel:main",
                            "contract_status": "verified-writer",
                            "family_scope_ref": "app:excel",
                            "writer_lock_scope": "workbook:orders",
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
                    },
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
        task_review["review"]["execution_runtime"]["host_twin"]["ownership"]["handoff_owner_ref"]
        == "human-operator:alice"
    )
    assert (
        task_review["review"]["execution_runtime"]["host_twin"]["legal_recovery"]["resume_kind"]
        == "resume-environment"
    )
    assert (
        task_review["review"]["execution_runtime"]["host_twin"]["app_family_twins"][
            "office_document"
        ]["writer_lock_scope"]
        == "workbook:orders"
    )
    assert (
        task_review["review"]["execution_runtime"]["host_twin"]["coordination"][
            "recommended_scheduler_action"
        ]
        == "handoff"
    )
    assert (
        task_review["review"]["execution_runtime"]["host_twin_summary"][
            "active_app_family_count"
        ]
        == 1
    )
    assert (
        task_review["review"]["execution_runtime"]["host_twin_summary"][
            "recommended_scheduler_action"
        ]
        == "handoff"
    )
    assert (
        task_review["review"]["execution_runtime"]["host_twin_summary"][
            "continuity_state"
        ]
        == "blocked"
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
        task_review["review"]["continuity"]["handoff"]["return_condition"]
        == "captcha-cleared"
    )
    assert (
        task_review["review"]["continuity"]["verification"]["channel"]
        == "runtime-center-self-check"
    )
    assert (
        task_review["review"]["continuity"]["verification"]["latest_anchor"]
        == "excel://Orders!A1"
    )
    assert any(
        "Coordination: handoff" in line
        for line in task_review["review"]["summary_lines"]
    )
    assert any(
        "Host twin families:" in line
        for line in task_review["review"]["summary_lines"]
    )
    assert any(
        "sticky-active-seat" in line
        for line in task_review["review"]["summary_lines"]
    )
    assert any(
        "Follow host coordination action: handoff" in action
        for action in task_review["review"]["next_actions"]
    )
    assert any(
        "Orders workbook" in action
        for action in task_review["review"]["next_actions"]
    )
    assert any(
        "Host coordination contention is blocked" in risk
        for risk in task_review["review"]["risks"]
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


def test_runtime_query_services_prefer_canonical_top_level_host_twin_summary(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    schedule_repository = SqliteScheduleRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")

    timestamp = datetime(2026, 3, 29, 13, 0, tzinfo=timezone.utc)
    task_repository.upsert_task(
        TaskRecord(
            id="task-host-summary-canonical-1",
            title="Canonical host summary check",
            summary="Ensure canonical top-level host summary wins over stale nested metadata.",
            task_type="system:dispatch_query",
            status="running",
            owner_agent_id="ops-agent",
            acceptance_criteria='{"kind":"kernel-task-meta-v1"}',
            created_at=timestamp,
            updated_at=timestamp,
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-host-summary-canonical-1",
            runtime_status="active",
            current_phase="executing",
            risk_level="guarded",
            active_environment_id="session:console:canonical-host-summary",
            last_result_summary="Canonical host summary indicates reentry is clean.",
            last_owner_agent_id="ops-agent",
            updated_at=timestamp,
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
            if session_mount_id != "session:console:canonical-host-summary":
                return None
            return {
                "id": session_mount_id,
                "host_companion_session": {
                    "session_mount_id": session_mount_id,
                    "environment_id": "env:canonical-host-summary",
                    "continuity_status": "attached",
                    "continuity_source": "live-handle",
                },
                "host_twin_summary": {
                    "recommended_scheduler_action": "proceed",
                    "blocked_surface_count": 0,
                    "legal_recovery_mode": "resume-environment",
                    "contention_severity": "clear",
                    "contention_reason": "clean-reentry",
                    "continuity_state": "ready",
                    "seat_owner_ref": "ops-agent",
                    "active_app_family_keys": ["office_document"],
                },
                "host_twin": {
                    "continuity": {
                        "status": "attached",
                        "valid": True,
                    },
                    "legal_recovery": {
                        "path": "handoff",
                        "resume_kind": "resume-runtime",
                    },
                    "blocked_surfaces": [
                        {
                            "surface_kind": "desktop_app",
                            "surface_ref": "window:excel:orders",
                            "reason": "stale-captcha",
                            "event_family": "modal-uac-login",
                        },
                    ],
                    "coordination": {
                        "recommended_scheduler_action": "handoff",
                        "contention_forecast": {
                            "severity": "blocked",
                            "reason": "stale-captcha",
                        },
                    },
                    "host_twin_summary": {
                        "recommended_scheduler_action": "handoff",
                        "blocked_surface_count": 1,
                        "legal_recovery_mode": "handoff",
                        "contention_severity": "blocked",
                        "contention_reason": "stale-captcha",
                    },
                },
                "host_contract": {
                    "handoff_state": "handoff-required",
                    "handoff_reason": "stale-handoff",
                    "blocked_reason": "stale-host-blocker",
                },
                "recovery": {
                    "status": "pending",
                    "mode": "attach-environment",
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
        decision_request_repository=decision_request_repository,
        evidence_ledger=evidence_ledger,
        environment_service=StubEnvironmentService(),
    )

    review = state_query.get_task_review("task-host-summary-canonical-1")
    assert review is not None
    review_payload = review["review"]
    assert (
        review_payload["execution_runtime"]["host_twin_summary"]["recommended_scheduler_action"]
        == "proceed"
    )
    assert review_payload["execution_runtime"]["host_twin_summary"]["blocked_surface_count"] == 0
    assert (
        review_payload["execution_runtime"]["host_twin_summary"]["continuity_state"]
        == "ready"
    )
    assert review_payload["continuity"]["handoff"]["state"] is None
    assert not any("Handoff:" in line for line in review_payload["summary_lines"])


def test_runtime_query_services_list_kernel_tasks_from_state_with_phase_filter(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    schedule_repository = SqliteScheduleRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)

    kernel_task_store = KernelTaskStore(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
    )

    kernel_task_store.upsert(
        KernelTask(
            id="ktask-executing",
            trace_id="trace:ktask-executing",
            title="Sync storefront inventory",
            capability_ref="browser_use",
            environment_ref="env:browser:jd",
            owner_agent_id="ops-agent",
            actor_owner_id="actor:ops-agent",
            phase="executing",
            risk_level="guarded",
            task_segment={"kind": "inventory-sync"},
            resume_point={"checkpoint": "inventory:page-3"},
            payload={"step": "sync-inventory", "attempt": 2},
            created_at=datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc),
        ),
    )
    kernel_task_store.upsert(
        KernelTask(
            id="ktask-waiting-confirm",
            trace_id="trace:ktask-waiting-confirm",
            title="Approve payout release",
            capability_ref="tool:confirm_transfer",
            environment_ref="env:finance:payments",
            owner_agent_id="finance-agent",
            phase="waiting-confirm",
            risk_level="confirm",
            payload={"decision_type": "query-tool-confirmation"},
            created_at=datetime(2026, 4, 1, 7, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 1, 8, 30, tzinfo=timezone.utc),
        ),
    )
    task_repository.upsert_task(
        TaskRecord(
            id="non-kernel-task",
            title="Non-kernel task",
            summary="Should not leak into the kernel list.",
            task_type="text",
            status="running",
            owner_agent_id="ops-agent",
            created_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        ),
    )

    state_query = RuntimeCenterStateQueryService(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        schedule_repository=schedule_repository,
        decision_request_repository=decision_request_repository,
    )

    tasks = state_query.list_kernel_tasks()

    assert [task["id"] for task in tasks] == [
        "ktask-executing",
        "ktask-waiting-confirm",
    ]
    assert tasks[0] == {
        "id": "ktask-executing",
        "trace_id": "trace:ktask-executing",
        "goal_id": None,
        "parent_task_id": None,
        "work_context_id": None,
        "title": "Sync storefront inventory",
        "capability_ref": "browser_use",
        "environment_ref": "env:browser:jd",
        "owner_agent_id": "ops-agent",
        "actor_owner_id": "actor:ops-agent",
        "phase": "executing",
        "risk_level": "guarded",
        "task_segment": {"kind": "inventory-sync"},
        "resume_point": {"checkpoint": "inventory:page-3"},
        "payload": {"step": "sync-inventory", "attempt": 2},
        "created_at": "2026-04-01T08:00:00Z",
        "updated_at": "2026-04-01T09:00:00Z",
    }
    assert tasks[1]["phase"] == "waiting-confirm"
    assert tasks[1]["environment_ref"] == "env:finance:payments"
    assert tasks[1]["payload"] == {"decision_type": "query-tool-confirmation"}

    waiting_confirm = state_query.list_kernel_tasks(phase="waiting-confirm")
    assert [task["id"] for task in waiting_confirm] == ["ktask-waiting-confirm"]


def test_runtime_task_list_projector_projects_stable_task_list_fields(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    work_context_repository = SqliteWorkContextRepository(state_store)

    task_timestamp = datetime(2026, 4, 2, 9, 0, tzinfo=timezone.utc)
    runtime_timestamp = datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc)
    work_context_repository.upsert_context(
        WorkContextRecord(
            id="ctx-projector",
            title="Projector context",
            summary="Stable task list projection context.",
            context_type="control-thread",
            status="active",
            context_key="control-thread:projector",
            owner_scope="projector-scope",
        ),
    )
    task_repository.upsert_task(
        TaskRecord(
            id="task-projector-parent",
            title="Project stable list payload",
            summary="Task summary from task record.",
            task_type="system:dispatch_query",
            status="running",
            owner_agent_id="task-owner",
            work_context_id="ctx-projector",
            acceptance_criteria=json.dumps(
                {
                    "kind": "kernel-task-meta-v1",
                    "trace_id": "trace:projector-parent",
                },
            ),
            created_at=task_timestamp,
            updated_at=task_timestamp,
        ),
    )
    task_repository.upsert_task(
        TaskRecord(
            id="task-projector-child",
            title="Projector child",
            summary="Child task",
            task_type="system:dispatch_query",
            status="completed",
            owner_agent_id="child-owner",
            parent_task_id="task-projector-parent",
            created_at=task_timestamp,
            updated_at=task_timestamp,
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-projector-parent",
            runtime_status="active",
            current_phase="executing",
            risk_level="guarded",
            last_result_summary="Runtime summary wins.",
            last_owner_agent_id="runtime-owner",
            updated_at=runtime_timestamp,
        ),
    )

    projector = RuntimeCenterTaskListProjector(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        work_context_loader=lambda work_context_id: (
            None
            if not work_context_id
            else {
                "id": "ctx-projector",
                "title": "Projector context",
                "context_type": "control-thread",
                "status": "active",
                "context_key": "control-thread:projector",
            }
        ),
        task_route_builder=lambda task_id: f"/tasks/{task_id}",
        activation_summary_builder=lambda *, task, runtime, kernel_metadata: {
            "scope_id": getattr(task, "id"),
            "activated_count": 1,
            "trace_id": (kernel_metadata or {}).get("trace_id"),
            "owner_agent_id": getattr(runtime, "last_owner_agent_id", None),
        },
    )

    tasks = projector.list_tasks(limit=10)

    assert len(tasks) == 2
    assert tasks[0] == {
        "id": "task-projector-parent",
        "trace_id": "trace:projector-parent",
        "title": "Project stable list payload",
        "kind": "system:dispatch_query",
        "status": "active",
        "owner_agent_id": "runtime-owner",
        "summary": "Runtime summary wins.",
        "current_progress_summary": "Runtime summary wins.",
        "updated_at": runtime_timestamp,
        "parent_task_id": None,
        "work_context_id": "ctx-projector",
        "context_key": "control-thread:projector",
        "work_context": {
            "id": "ctx-projector",
            "title": "Projector context",
            "context_type": "control-thread",
            "status": "active",
            "context_key": "control-thread:projector",
        },
        "child_task_count": 1,
        "route": "/tasks/task-projector-parent",
        "activation": {
            "scope_id": "task-projector-parent",
            "activated_count": 1,
            "trace_id": "trace:projector-parent",
            "owner_agent_id": "runtime-owner",
        },
    }
    assert tasks[1]["id"] == "task-projector-child"
    assert tasks[1]["child_task_count"] == 0


def test_runtime_work_context_projector_uses_runtime_owner_for_detail_rollups(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    work_context_repository = SqliteWorkContextRepository(state_store)

    timestamp = datetime(2026, 4, 2, 11, 0, tzinfo=timezone.utc)
    work_context_repository.upsert_context(
        WorkContextRecord(
            id="ctx-runtime-owner",
            title="Runtime owner context",
            summary="Ensure work-context detail follows runtime ownership.",
            context_type="control-thread",
            status="active",
            context_key="control-thread:runtime-owner",
            owner_scope="runtime-owner-scope",
            primary_thread_id="thread:runtime-owner",
        ),
    )
    task_repository.upsert_task(
        TaskRecord(
            id="task-runtime-owner",
            title="Follow runtime owner",
            summary="Task owner should not lag behind runtime owner.",
            task_type="system:dispatch_query",
            status="running",
            owner_agent_id="task-owner",
            work_context_id="ctx-runtime-owner",
            created_at=timestamp,
            updated_at=timestamp,
        ),
    )
    task_runtime_repository.upsert_runtime(
        TaskRuntimeRecord(
            task_id="task-runtime-owner",
            runtime_status="active",
            current_phase="executing",
            risk_level="guarded",
            last_result_summary="Runtime owner has taken over the task.",
            last_owner_agent_id="runtime-owner",
            updated_at=timestamp,
        ),
    )

    requested_agent_ids: list[set[str]] = []
    projector = RuntimeCenterWorkContextProjector(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        work_context_repository=work_context_repository,
        related_agents_loader=lambda agent_ids: (
            requested_agent_ids.append(set(agent_ids)) or [
                {
                    "agent_id": "runtime-owner",
                    "name": "Runtime Owner",
                    "status": "active",
                },
            ]
        ),
    )

    detail = projector.get_work_context_detail("ctx-runtime-owner")

    assert detail is not None
    assert requested_agent_ids == [{"runtime-owner"}]
    assert detail["agents"] == [
        {
            "agent_id": "runtime-owner",
            "name": "Runtime Owner",
            "status": "active",
        },
    ]
    assert detail["tasks"][0]["owner_agent_id"] == "runtime-owner"
    assert detail["tasks"][0]["owner_agent_name"] == "Runtime Owner"
    assert detail["stats"]["owner_agent_count"] == 1


def test_runtime_work_context_projector_counts_real_contexts(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    work_context_repository = SqliteWorkContextRepository(state_store)

    work_context_repository.upsert_context(
        WorkContextRecord(
            id="ctx-count-1",
            title="Count context one",
            summary="First context",
            context_type="control-thread",
            status="active",
            context_key="control-thread:count-1",
            owner_scope="count-scope",
        ),
    )
    work_context_repository.upsert_context(
        WorkContextRecord(
            id="ctx-count-2",
            title="Count context two",
            summary="Second context",
            context_type="control-thread",
            status="active",
            context_key="control-thread:count-2",
            owner_scope="count-scope",
        ),
    )

    projector = RuntimeCenterWorkContextProjector(
        task_repository=task_repository,
        task_runtime_repository=task_runtime_repository,
        work_context_repository=work_context_repository,
        related_agents_loader=lambda agent_ids: [],
    )

    assert projector.count_work_contexts() == 2
    contexts = projector.list_work_contexts(limit=10)
    assert {item["id"] for item in contexts} == {"ctx-count-1", "ctx-count-2"}


def test_runtime_query_service_counts_work_contexts_from_projector_backed_state(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    work_context_repository = SqliteWorkContextRepository(state_store)
    work_context_repository.upsert_context(
        WorkContextRecord(
            id="ctx-state-query-1",
            title="State query one",
            summary="First context for state query count.",
            context_type="control-thread",
            status="active",
            context_key="control-thread:state-query-1",
            owner_scope="state-query-scope",
        ),
    )
    work_context_repository.upsert_context(
        WorkContextRecord(
            id="ctx-state-query-2",
            title="State query two",
            summary="Second context for state query count.",
            context_type="control-thread",
            status="active",
            context_key="control-thread:state-query-2",
            owner_scope="state-query-scope",
        ),
    )

    state_query = RuntimeCenterStateQueryService(
        task_repository=SqliteTaskRepository(state_store),
        task_runtime_repository=SqliteTaskRuntimeRepository(state_store),
        schedule_repository=SqliteScheduleRepository(state_store),
        decision_request_repository=SqliteDecisionRequestRepository(state_store),
        work_context_repository=work_context_repository,
    )

    assert state_query.count_work_contexts() == 2


def test_runtime_query_services_expose_human_assist_task_surfaces(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    human_assist_repository = SqliteHumanAssistTaskRepository(state_store)
    human_assist_service = HumanAssistTaskService(
        repository=human_assist_repository,
        evidence_ledger=evidence_ledger,
    )
    issued = human_assist_service.issue_task(_make_human_assist_task())

    state_query = RuntimeCenterStateQueryService(
        task_repository=SqliteTaskRepository(state_store),
        task_runtime_repository=SqliteTaskRuntimeRepository(state_store),
        schedule_repository=SqliteScheduleRepository(state_store),
        decision_request_repository=SqliteDecisionRequestRepository(state_store),
        evidence_ledger=evidence_ledger,
        human_assist_task_service=human_assist_service,
    )

    current = state_query.get_current_human_assist_task(
        chat_thread_id="industry-chat:industry-1:execution-core",
    )
    assert current is not None
    assert current["id"] == issued.id
    assert current["status"] == "issued"
    assert current["route"] == f"/api/runtime-center/human-assist-tasks/{issued.id}"
    assert (
        current["tasks_route"]
        == "/api/runtime-center/human-assist-tasks?chat_thread_id=industry-chat%3Aindustry-1%3Aexecution-core"
    )

    items = state_query.list_human_assist_tasks(
        chat_thread_id="industry-chat:industry-1:execution-core",
        limit=10,
    )
    assert len(items) == 1
    assert items[0]["id"] == issued.id
    assert items[0]["acceptance_mode"] == "evidence_verified"

    detail = state_query.get_human_assist_task_detail(issued.id)
    assert detail is not None
    assert detail["task"]["id"] == issued.id
    assert detail["task"]["acceptance_spec"]["hard_anchors"] == ["receipt"]
    assert detail["task"]["reward_preview"]["sync_points"] == 2
    assert detail["routes"]["self"] == f"/api/runtime-center/human-assist-tasks/{issued.id}"


def test_runtime_query_services_hide_resume_queued_human_assist_from_current_but_keep_detail(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    evidence_ledger = EvidenceLedger(database_path=tmp_path / "evidence.sqlite3")
    human_assist_repository = SqliteHumanAssistTaskRepository(state_store)
    human_assist_service = HumanAssistTaskService(
        repository=human_assist_repository,
        evidence_ledger=evidence_ledger,
    )
    issued = human_assist_service.issue_task(_make_human_assist_task())
    human_assist_service.mark_resume_queued(issued.id)

    state_query = RuntimeCenterStateQueryService(
        task_repository=SqliteTaskRepository(state_store),
        task_runtime_repository=SqliteTaskRuntimeRepository(state_store),
        schedule_repository=SqliteScheduleRepository(state_store),
        decision_request_repository=SqliteDecisionRequestRepository(state_store),
        evidence_ledger=evidence_ledger,
        human_assist_task_service=human_assist_service,
    )

    current = state_query.get_current_human_assist_task(
        chat_thread_id="industry-chat:industry-1:execution-core",
    )
    assert current is None

    items = state_query.list_human_assist_tasks(
        chat_thread_id="industry-chat:industry-1:execution-core",
        limit=10,
    )
    assert len(items) == 1
    assert items[0]["status"] == "resume_queued"

    detail = state_query.get_human_assist_task_detail(issued.id)
    assert detail is not None
    assert detail["task"]["status"] == "resume_queued"
    assert detail["task"]["current_route"].endswith(
        "chat_thread_id=industry-chat%3Aindustry-1%3Aexecution-core",
    )
    assert detail["routes"]["list"].endswith(
        "chat_thread_id=industry-chat%3Aindustry-1%3Aexecution-core",
    )
    assert detail["routes"]["current"].endswith(
        "chat_thread_id=industry-chat%3Aindustry-1%3Aexecution-core",
    )
