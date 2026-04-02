# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json

from .shared import *  # noqa: F401,F403

from agentscope.message import Msg

from copaw.capabilities import CapabilityService
from copaw.app.startup_recovery import StartupRecoverySummary
from copaw.environments.models import SessionMount
from copaw.evidence import EvidenceLedger
from copaw.kernel import KernelDispatcher, KernelTaskStore, KernelTurnExecutor
from copaw.kernel.main_brain_intake import MainBrainIntakeContract
from copaw.kernel.main_brain_orchestrator import MainBrainOrchestrator
from copaw.kernel.main_brain_turn_result import MainBrainCommitState
from copaw.media import MediaService
from copaw.state import SQLiteStateStore
from copaw.state import MediaAnalysisRecord
from copaw.state.repositories import (
    SqliteDecisionRequestRepository,
    SqliteTaskRepository,
    SqliteTaskRuntimeRepository,
)
from copaw.state.repositories.base import BaseMediaAnalysisRepository


class _InMemoryMediaAnalysisRepository(BaseMediaAnalysisRepository):
    def __init__(self) -> None:
        self._records: dict[str, MediaAnalysisRecord] = {}

    def get_analysis(self, analysis_id: str) -> MediaAnalysisRecord | None:
        return self._records.get(analysis_id)

    def list_analyses(
        self,
        *,
        industry_instance_id: str | None = None,
        thread_id: str | None = None,
        work_context_id: str | None = None,
        entry_point: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[MediaAnalysisRecord]:
        records = list(self._records.values())
        filtered: list[MediaAnalysisRecord] = []
        for record in records:
            if industry_instance_id is not None and record.industry_instance_id != industry_instance_id:
                continue
            if thread_id is not None and record.thread_id != thread_id:
                continue
            if work_context_id is not None and record.work_context_id != work_context_id:
                continue
            if entry_point is not None and record.entry_point != entry_point:
                continue
            if status is not None and record.status != status:
                continue
            filtered.append(record)
        filtered.sort(
            key=lambda item: item.updated_at or item.created_at,
            reverse=True,
        )
        return filtered[:limit] if isinstance(limit, int) else filtered

    def upsert_analysis(self, analysis: MediaAnalysisRecord) -> MediaAnalysisRecord:
        self._records[analysis.analysis_id] = analysis
        return analysis

    def delete_analysis(self, analysis_id: str) -> bool:
        return self._records.pop(analysis_id, None) is not None


def _build_media_service() -> MediaService:
    return MediaService(
        repository=_InMemoryMediaAnalysisRepository(),
        evidence_ledger=EvidenceLedger(),
    )


def _wire_governed_schedule_runtime(app: FastAPI, manager: FakeCronManager, tmp_path: Path) -> None:
    state_store = SQLiteStateStore(tmp_path / "schedule-governance.sqlite3")
    task_repository = SqliteTaskRepository(state_store)
    task_runtime_repository = SqliteTaskRuntimeRepository(state_store)
    decision_request_repository = SqliteDecisionRequestRepository(state_store)
    evidence_ledger = EvidenceLedger(tmp_path / "schedule-governance.evidence.sqlite3")
    capability_service = CapabilityService(
        evidence_ledger=evidence_ledger,
    )
    capability_service.set_cron_manager(manager)
    kernel_dispatcher = KernelDispatcher(
        task_store=KernelTaskStore(
            task_repository=task_repository,
            task_runtime_repository=task_runtime_repository,
            decision_request_repository=decision_request_repository,
            evidence_ledger=evidence_ledger,
        ),
        capability_service=capability_service,
    )
    app.state.capability_service = capability_service
    app.state.kernel_dispatcher = kernel_dispatcher
    app.state.decision_request_repository = decision_request_repository
    app.state.evidence_ledger = evidence_ledger


class _CapturingRouteQueryExecutionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.synced: dict[str, object] = {}

    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield Msg(name="assistant", role="assistant", content="kernel route done"), True

    def set_session_backend(self, session_backend) -> None:
        self.synced["session_backend"] = session_backend

    def set_kernel_dispatcher(self, kernel_dispatcher) -> None:
        self.synced["kernel_dispatcher"] = kernel_dispatcher

    def resolve_request_owner_agent_id(self, *, request) -> str | None:
        return getattr(request, "agent_id", None) or None


class _CapturingRouteChatService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.synced: dict[str, object] = {}

    async def execute_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield Msg(name="assistant", role="assistant", content="chat route done"), True

    def set_session_backend(self, session_backend) -> None:
        self.synced["session_backend"] = session_backend


class _CapturingRouteEnvironmentService:
    def __init__(self, *, sessions: dict[str, SessionMount] | None = None) -> None:
        self._sessions = sessions or {}

    def get_session(self, session_mount_id: str) -> SessionMount | None:
        return self._sessions.get(session_mount_id)


class _CognitiveFakeIndustryService(FakeIndustryService):
    def get_instance_detail(self, instance_id: str):
        detail = super().get_instance_detail(instance_id)
        if detail is None:
            return None
        payload = detail.model_dump(mode="json")
        payload["current_cycle"]["synthesis"] = {
            "latest_findings": [
                {
                    "report_id": "report-1",
                    "assignment_id": "assignment-1",
                    "headline": "Delivery blocker needs supervisor review",
                    "summary": "The assigned execution slot is blocked until staffing confirms who owns the browser follow-up.",
                    "status": "recorded",
                    "needs_followup": True,
                    "updated_at": "2026-03-09T08:34:00+00:00",
                }
            ],
            "conflicts": [
                {
                    "conflict_id": "result-mismatch:report-1",
                    "kind": "result-mismatch",
                    "summary": "Reports disagree on whether the handoff is cleared.",
                    "report_ids": ["report-1", "report-2"],
                }
            ],
            "holes": [
                {
                    "hole_id": "followup-needed:report-1",
                    "kind": "followup-needed",
                    "report_id": "report-1",
                    "summary": "Supervisor review is still missing for the handoff return.",
                }
            ],
            "replan_reasons": [
                "Reports disagree on whether the handoff is cleared.",
                "Supervisor review is still missing for the handoff return.",
            ],
            "needs_replan": True,
        }
        payload["backlog"] = [
            {
                "backlog_item_id": "backlog-followup-1",
                "title": "Resolve handoff return evidence gap",
                "summary": "Main brain should reopen the report and dispatch a governed browser follow-up.",
                "status": "open",
                "metadata": {
                    "source_report_id": "report-1",
                    "source_report_ids": ["report-1"],
                    "synthesis_kind": "followup-needed",
                    "control_thread_id": "thread-1",
                    "environment_ref": "seat:browser-a",
                },
            }
        ]
        payload["agent_reports"][0]["summary"] = (
            "The assigned execution slot is blocked until staffing confirms who owns the browser follow-up."
        )
        payload["agent_reports"][0]["route"] = (
            "/api/runtime-center/industry/industry-v1-ops?report_id=report-1"
        )
        payload["agent_reports"][0]["report_consumed"] = False
        return type(
            "IndustryDetail",
            (),
            {
                "model_dump": lambda self, mode="json": payload,
            },
        )()


class _ObjectScheduleStateQueryService(FakeStateQueryService):
    async def list_schedules(self, limit: int | None = 5):
        schedules = await super().list_schedules(limit=limit)
        return [SimpleNamespace(**item) for item in schedules]


def test_runtime_center_overview_uses_state_and_evidence_services():
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.industry_service = FakeIndustryService()
    app.state.governance_service = FakeGovernanceService()
    app.state.routine_service = FakeRoutineService()
    app.state.strategy_memory_service = FakeStrategyMemoryService()

    client = TestClient(app)
    response = client.get("/runtime-center/overview")

    assert response.status_code == 200
    assert response.headers["x-copaw-runtime-surface"] == "runtime-center"
    assert response.headers["x-copaw-runtime-surface-version"] == "runtime-center-v1"

    payload = response.json()
    assert payload["surface"]["version"] == "runtime-center-v1"
    assert payload["surface"]["status"] == "state-service"
    assert "bridge" not in payload

    cards = {card["key"]: card for card in payload["cards"]}
    assert cards["tasks"]["source"] == "state_query_service"
    assert cards["tasks"]["count"] == 1
    assert cards["tasks"]["entries"][0]["title"] == "Refresh competitor brief"
    assert cards["work-contexts"]["source"] == "state_query_service"
    assert cards["work-contexts"]["count"] == 1
    assert cards["work-contexts"]["entries"][0]["title"] == "Acme Pets execution core"
    assert cards["routines"]["source"] == "routine_service"
    assert cards["routines"]["count"] == 1
    routine_actions = cards["routines"]["entries"][0].get("actions") or {}
    assert "replay" not in routine_actions
    assert "goals" not in cards
    assert "schedules" not in cards
    assert cards["industry"]["source"] == "industry_service"
    assert cards["industry"]["count"] == 1
    industry_meta = cards["industry"]["entries"][0]["meta"]
    assert industry_meta["lane_count"] == 2
    assert industry_meta["backlog_count"] == 4
    assert industry_meta["cycle_count"] == 1
    assert industry_meta["assignment_count"] == 2
    assert industry_meta["report_count"] == 1
    assert industry_meta["schedule_count"] == 2
    assert "goal_count" not in industry_meta
    assert "active_goal_count" not in industry_meta
    assert cards["agents"]["source"] == "agent_profile_service"
    assert cards["agents"]["count"] == 4
    assert cards["agents"]["entries"][0]["meta"]["current_focus_kind"] == "goal"
    assert cards["agents"]["entries"][0]["meta"]["current_focus_id"] == "goal-1"
    assert cards["agents"]["entries"][0]["meta"]["current_focus"] == "Launch runtime center"
    assert "current_goal_id" not in cards["agents"]["entries"][0]["meta"]
    assert "current_goal" not in cards["agents"]["entries"][0]["meta"]
    assert cards["capabilities"]["source"] == "capability_service"
    assert cards["capabilities"]["meta"]["total"] == 1
    assert cards["evidence"]["source"] == "evidence_query_service"
    assert cards["evidence"]["count"] == 1
    assert cards["governance"]["source"] == "governance_service"
    assert cards["governance"]["count"] == 1
    assert cards["governance"]["meta"]["host_twin_summary"]["blocked_surface_count"] == 0
    assert cards["governance"]["meta"]["host_twin_summary"]["active_app_family_count"] == 0
    assert cards["main-brain"]["source"] == "strategy_memory_service,industry_service"
    assert cards["main-brain"]["count"] == 1
    main_brain_entry = cards["main-brain"]["entries"][0]
    assert main_brain_entry["meta"]["lane_count"] == 2
    assert main_brain_entry["meta"]["assignment_count"] == 2
    assert main_brain_entry["meta"]["report_count"] == 1
    assert main_brain_entry["meta"]["decision_count"] == 2
    assert main_brain_entry["meta"]["patch_count"] == 3
    assert main_brain_entry["meta"]["evidence_count"] == 4
    assert main_brain_entry["meta"]["strategy_id"] == "strategy:industry:industry-v1-ops:copaw-agent-runner"
    assert cards["decisions"]["entries"][0]["status"] == "open"
    assert cards["decisions"]["entries"][0]["actions"]["approve"] == "/api/runtime-center/decisions/decision-1/approve"
    assert cards["patches"]["source"] == "learning_service"
    assert cards["patches"]["count"] == 1
    assert (
        cards["patches"]["entries"][0]["actions"]["apply"]
        == "/api/runtime-center/learning/patches/patch-1/apply"
    )


def test_runtime_center_main_brain_route_exposes_industry_stats():
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.industry_service = FakeIndustryService()
    app.state.governance_service = FakeGovernanceService()
    app.state.routine_service = FakeRoutineService()
    app.state.strategy_memory_service = FakeStrategyMemoryService()

    client = TestClient(app)
    response = client.get("/runtime-center/main-brain")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"]["status"] == "state-service"
    assert payload["strategy"]["strategy_id"] == "strategy:industry:industry-v1-ops:copaw-agent-runner"
    assert payload["carrier"]["industry_instance_id"] == "industry-v1-ops"
    assert payload["carrier"]["route"] == "/api/runtime-center/industry/industry-v1-ops"
    assert len(payload["lanes"]) == 2
    assert len(payload["cycles"]) == 1
    assert "backlog" in payload
    assert isinstance(payload["backlog"], list)
    assert payload["current_cycle"]["cycle_id"] == "cycle-1"
    assert len(payload["assignments"]) == 1
    assert len(payload["reports"]) == 1
    assert payload["environment"]["route"] == "/api/runtime-center/governance/status"
    assert "host_twin_summary" in payload["environment"]
    assert "handoff" in payload["environment"]
    assert "staffing" in payload["environment"]
    assert "human_assist" in payload["environment"]
    assert payload["meta"]["lane_count"] == 2
    assert payload["meta"]["assignment_count"] == 2
    assert payload["meta"]["report_count"] == 1
    assert payload["meta"]["decision_count"] == 2
    assert payload["meta"]["patch_count"] == 3
    assert payload["meta"]["evidence_count"] == 4
    assert payload["meta"]["industry_instance_id"] == "industry-v1-ops"
    assert payload["signals"]["decisions"]["count"] == 2
    assert payload["signals"]["patches"]["count"] == 3
    assert payload["signals"]["evidence"]["count"] == 4


def test_runtime_center_main_brain_route_exposes_report_cognition_surface():
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.industry_service = _CognitiveFakeIndustryService()
    app.state.governance_service = FakeGovernanceService()
    app.state.routine_service = FakeRoutineService()
    app.state.strategy_memory_service = FakeStrategyMemoryService()

    client = TestClient(app)
    response = client.get("/runtime-center/main-brain")

    assert response.status_code == 200
    payload = response.json()
    cognition = payload["report_cognition"]

    assert cognition["needs_replan"] is True
    assert cognition["replan_reasons"] == [
        "Reports disagree on whether the handoff is cleared.",
        "Supervisor review is still missing for the handoff return.",
    ]
    assert cognition["judgment"]["status"] == "attention"
    assert "decide whether to dispatch follow-up work" in cognition["judgment"]["summary"]
    assert cognition["next_action"]["kind"] == "followup-backlog"
    assert cognition["next_action"]["title"] == "Resolve handoff return evidence gap"
    assert cognition["next_action"]["route"] == (
        "/api/runtime-center/industry/industry-v1-ops?backlog_item_id=backlog-followup-1"
    )
    assert cognition["latest_findings"][0]["report_id"] == "report-1"
    assert cognition["latest_findings"][0]["route"] == (
        "/api/runtime-center/industry/industry-v1-ops?report_id=report-1"
    )
    assert cognition["conflicts"][0]["conflict_id"] == "result-mismatch:report-1"
    assert cognition["holes"][0]["hole_id"] == "followup-needed:report-1"
    assert cognition["followup_backlog"][0]["backlog_item_id"] == "backlog-followup-1"
    assert payload["backlog"][0]["backlog_item_id"] == "backlog-followup-1"
    assert cognition["unconsumed_reports"][0]["report_id"] == "report-1"
    assert cognition["needs_followup_reports"][0]["report_id"] == "report-1"
    assert payload["reports"][0]["route"] == (
        "/api/runtime-center/industry/industry-v1-ops?report_id=report-1"
    )
    assert payload["reports"][0]["report_consumed"] is False
    assert payload["signals"]["report_cognition"]["status"] == "attention"
    assert payload["signals"]["report_cognition"]["count"] == 4
    assert payload["meta"]["agent_reports"]["unconsumed_count"] == 1
    assert payload["meta"]["report_cognition"]["needs_replan"] is True


def test_runtime_center_main_brain_route_exposes_unified_operator_sections():
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.industry_service = FakeIndustryService()
    app.state.governance_service = FakeGovernanceService()
    app.state.routine_service = FakeRoutineService()
    app.state.strategy_memory_service = FakeStrategyMemoryService()
    app.state.startup_recovery_summary = StartupRecoverySummary(
        reason="Recovered expired decisions and runtime leases during startup.",
        expired_decisions=1,
        pending_decisions=2,
        active_schedules=1,
        notes=["Recovered the canonical runtime scheduler state."],
    )
    app.state.cron_manager = FakeCronManager(
        [make_job("sched-1")],
        states={
            "sched-1": CronJobState(
                last_status="success",
                last_run_at=datetime(2026, 3, 9, 8, 0, tzinfo=timezone.utc),
                next_run_at=datetime(2026, 3, 9, 9, 0, tzinfo=timezone.utc),
            ),
        },
        heartbeat_state=CronJobState(
            last_status="success",
            last_run_at=datetime(2026, 3, 9, 8, 30, tzinfo=timezone.utc),
            next_run_at=datetime(2026, 3, 9, 14, 30, tzinfo=timezone.utc),
        ),
    )

    client = TestClient(app)

    with patch(
        "copaw.app.runtime_center.overview_cards.get_heartbeat_config",
        return_value=HeartbeatConfig(enabled=True, every="6h", target="main"),
        create=True,
    ):
        response = client.get("/runtime-center/main-brain")

    assert response.status_code == 200
    payload = response.json()

    assert payload["governance"]["route"] == "/api/runtime-center/governance/status"
    assert payload["governance"]["pending_decisions"] == 0
    assert payload["governance"]["pending_patches"] == 1
    assert payload["governance"]["summary"]

    assert payload["recovery"]["available"] is True
    assert payload["recovery"]["route"] == "/api/runtime-center/recovery/latest"
    assert payload["recovery"]["pending_decisions"] == 2
    assert payload["recovery"]["summary"]

    assert payload["automation"]["route"] == "/api/runtime-center/schedules"
    assert payload["automation"]["schedule_count"] == 1
    assert payload["automation"]["active_schedule_count"] == 1
    assert payload["automation"]["heartbeat"]["route"] == "/api/runtime-center/heartbeat"
    assert payload["automation"]["heartbeat"]["status"] == "success"
    assert payload["automation"]["heartbeat"]["enabled"] is True

    control_chain_keys = [item["key"] for item in payload["meta"]["control_chain"]]
    assert "governance" in control_chain_keys
    assert "automation" in control_chain_keys
    assert "recovery" in control_chain_keys
    assert payload["signals"]["governance"]["count"] == 1
    assert payload["signals"]["automation"]["count"] == 1
    assert payload["signals"]["recovery"]["count"] == 1


def test_runtime_center_main_brain_route_handles_object_schedule_summaries():
    app = build_runtime_center_app()
    app.state.state_query_service = _ObjectScheduleStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.industry_service = FakeIndustryService()
    app.state.governance_service = FakeGovernanceService()
    app.state.routine_service = FakeRoutineService()
    app.state.strategy_memory_service = FakeStrategyMemoryService()

    client = TestClient(app)
    with patch(
        "copaw.app.runtime_center.overview_cards.get_heartbeat_config",
        return_value=HeartbeatConfig(enabled=True, every="6h", target="main"),
        create=True,
    ):
        response = client.get("/runtime-center/main-brain")

    assert response.status_code == 200
    payload = response.json()
    assert payload["automation"]["schedule_count"] == 1
    assert payload["automation"]["active_schedule_count"] == 1
    assert payload["automation"]["paused_schedule_count"] == 0


def test_runtime_center_overview_governance_uses_canonical_host_twin_summary_for_ready_runtime():
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.industry_service = FakeIndustryService()
    governance_service = FakeGovernanceService()
    governance_service.status["host_twin"] = {
        "projection_kind": "host_twin_projection",
        "is_projection": True,
        "is_truth_store": False,
        "ownership": {
            "seat_owner_agent_id": "ops-agent",
            "workspace_owner_ref": "ops-agent",
            "writer_owner_ref": "ops-agent",
        },
        "app_family_twins": {
            "browser_backoffice": {
                "active": True,
                "family_kind": "browser_backoffice",
                "surface_ref": "browser:web:main",
                "contract_status": "verified-writer",
                "family_scope_ref": "site:jd:seller-center",
            },
            "office_document": {
                "active": True,
                "family_kind": "office_document",
                "surface_ref": "window:excel:orders",
                "contract_status": "verified-writer",
                "family_scope_ref": "app:excel",
                "writer_lock_scope": "workbook:orders",
            },
        },
        "host_companion_session": {
            "session_mount_id": "session:desktop:main",
            "environment_id": "env:desktop:seat-a",
            "continuity_status": "attached",
            "continuity_source": "live-handle",
            "locality": {
                "same_host": True,
                "same_process": False,
                "startup_recovery_required": False,
            },
        },
        "blocked_surfaces": [],
        "coordination": {
            "seat_owner_ref": "ops-agent",
            "workspace_owner_ref": "ops-agent",
            "writer_owner_ref": "ops-agent",
            "candidate_seat_refs": [
                "env:desktop:seat-a",
                "env:desktop:seat-b",
            ],
            "selected_seat_ref": "env:desktop:seat-a",
            "seat_selection_policy": "sticky-active-seat",
            "contention_forecast": {
                "severity": "clear",
                "reason": "steady-state",
            },
            "recommended_scheduler_action": "proceed",
        },
        "multi_seat_coordination": {
            "seat_count": 2,
            "candidate_seat_refs": [
                "env:desktop:seat-a",
                "env:desktop:seat-b",
            ],
            "selected_seat_ref": "env:desktop:seat-a",
            "seat_selection_policy": "sticky-active-seat",
            "occupancy_state": "occupied",
            "status": "active",
            "host_companion_status": "attached",
            "active_surface_mix": ["browser", "desktop-app"],
        },
        "legal_recovery": {
            "path": "resume-environment",
            "resume_kind": "resume-environment",
            "checkpoint_ref": "checkpoint:orders",
        },
        "writable_surface_summary": "browser, desktop_app",
        "app_family_readiness": {
            "active_family_keys": [
                "browser_backoffice",
                "office_document",
            ],
            "active_family_count": 2,
            "ready_family_keys": [
                "browser_backoffice",
                "office_document",
            ],
            "ready_family_count": 2,
            "blocked_family_keys": [],
            "blocked_family_count": 0,
        },
        "trusted_anchors": [
            {
                "anchor_ref": "excel://Orders!A1",
            },
        ],
        "metadata": {
            "stale_checkpoint_state": "agent-attached",
            "stale_recommended_scheduler_action": "handoff",
            "stale_blocking_event_family": "modal-uac-login",
        },
    }
    governance_service.status["handoff"] = {
        "active": False,
        "session_ids": [],
        "owner_refs": [],
        "blocking_families": [],
    }
    governance_service.status["staffing"] = {
        "active_gap_count": 0,
        "pending_confirmation_count": 0,
        "instance_ids": [],
        "decision_request_ids": [],
    }
    governance_service.status["human_assist"] = {
        "open_count": 0,
        "blocked_count": 0,
        "need_more_evidence_count": 0,
        "task_ids": [],
        "chat_thread_ids": [],
    }
    app.state.governance_service = governance_service
    app.state.routine_service = FakeRoutineService()

    client = TestClient(app)
    response = client.get("/runtime-center/overview")

    assert response.status_code == 200
    cards = {card["key"]: card for card in response.json()["cards"]}
    governance = cards["governance"]
    assert governance["entries"][0]["status"] == "idle"
    assert governance["meta"]["host_twin_summary"]["recommended_scheduler_action"] == (
        "proceed"
    )
    assert governance["meta"]["host_twin_summary"]["active_app_family_keys"] == [
        "browser_backoffice",
        "office_document",
    ]
    assert governance["meta"]["host_twin_summary"]["host_companion_status"] == "attached"
    assert governance["meta"]["host_twin_summary"]["continuity_state"] == "ready"
    assert governance["meta"]["host_twin_summary"]["seat_count"] == 2
    assert governance["meta"]["host_twin_summary"]["ready_app_family_keys"] == [
        "browser_backoffice",
        "office_document",
    ]
    assert (
        governance["meta"]["host_twin_summary"].get("stale_recommended_scheduler_action")
        is None
    )
    assert governance["summary"] == (
        "Host twin ready on env:desktop:seat-a via sticky-active-seat; "
        "active app families: browser_backoffice, office_document."
    )
    assert cards["growth"]["source"] == "learning_service"
    assert cards["growth"]["count"] == 1
    assert "legacy-surfaces" not in cards


def test_runtime_center_overview_governance_exposes_canonical_execution_diagnostics():
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.industry_service = FakeIndustryService()
    governance_service = FakeGovernanceService()
    governance_service.status["human_assist"] = {
        "open_count": 1,
        "blocked_count": 2,
        "need_more_evidence_count": 1,
        "task_ids": ["assist-1", "assist-2"],
        "chat_thread_ids": ["thread-1"],
    }
    app.state.governance_service = governance_service
    app.state.routine_service = FakeRoutineService()

    client = TestClient(app)
    response = client.get("/runtime-center/overview")

    assert response.status_code == 200
    cards = {card["key"]: card for card in response.json()["cards"]}
    governance = cards["governance"]
    assert governance["summary"] == (
        "Human assist tasks are still blocking automatic continuation."
    )
    assert governance["meta"]["failure_source"] == "human-assist"
    assert governance["meta"]["blocked_next_step"] == (
        "Review the blocking human assist tasks and resume only after evidence is accepted."
    )
    assert governance["meta"]["remediation_summary"] == governance["summary"]
    assert governance["entries"][0]["meta"]["failure_source"] == "human-assist"
    assert governance["entries"][0]["meta"]["blocked_next_step"] == (
        "Review the blocking human assist tasks and resume only after evidence is accepted."
    )


def test_runtime_center_work_context_detail_endpoint() -> None:
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)
    response = client.get("/runtime-center/work-contexts/ctx-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["work_context"]["id"] == "ctx-1"
    assert payload["work_context"]["context_key"] == (
        "control-thread:industry-chat:industry-v1-ops:execution-core"
    )
    assert payload["stats"]["task_count"] == 3
    assert payload["tasks"][0]["work_context"]["id"] == "ctx-1"


def test_runtime_center_capability_optimizations_endpoint() -> None:
    app = build_runtime_center_app()
    app.state.prediction_service = FakePredictionService()

    client = TestClient(app)
    response = client.get("/runtime-center/governance/capability-optimizations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["actionable_count"] == 1
    assert payload["summary"]["retire_count"] == 1
    assert (
        payload["actionable"][0]["recommendation"]["recommendation"]["metadata"][
            "gap_kind"
        ]
        == "missing_capability"
    )
    assert (
        payload["history"][0]["recommendation"]["recommendation"]["metadata"][
            "optimization_stage"
        ]
        == "retire"
    )
    assert payload["routes"]["predictions"] == "/api/predictions"


def test_runtime_center_overview_returns_unavailable_cards_without_backing_state():
    app = build_runtime_center_app()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    client = TestClient(app)

    response = client.get("/runtime-center/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"]["status"] == "degraded"

    cards = {card["key"]: card for card in payload["cards"]}
    assert "goals" not in cards
    assert "schedules" not in cards
    assert cards["capabilities"]["status"] == "state-service"
    assert cards["capabilities"]["meta"]["total"] == 1
    for key, card in cards.items():
        if key in {"capabilities", "patches", "growth"}:
            continue
        if key == "industry":
            continue
        assert card["status"] == "unavailable"
        assert card["count"] == 0
        assert card["entries"] == []
    assert cards["patches"]["status"] == "state-service"
    assert cards["growth"]["status"] == "state-service"


def test_runtime_center_strategy_memory_lists_execution_core_strategy() -> None:
    app = build_runtime_center_app()
    app.state.strategy_memory_service = FakeStrategyMemoryService()

    client = TestClient(app)
    response = client.get(
        "/runtime-center/strategy-memory",
        params={"industry_instance_id": "industry-v1-ops"},
    )

    assert response.status_code == 200
    assert response.headers["x-copaw-runtime-surface"] == "runtime-center"
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["strategy_id"] == "strategy:industry:industry-v1-ops:copaw-agent-runner"
    assert payload[0]["title"] == "白泽执行中枢行业战略"
    assert payload[0]["scope_type"] == "industry"
    assert payload[0]["industry_instance_id"] == "industry-v1-ops"
    assert payload[0]["active_goal_titles"] == ["Launch runtime center"]
    assert all("亲自执行" not in item for item in payload[0]["direct_execution_policy"])
    assert any(
        "补位" in item or "改派" in item or "确认" in item
        for item in payload[0]["direct_execution_policy"]
    )


def test_runtime_center_overview_prefers_limited_list_reads() -> None:
    class StrictLimitedStateQueryService:
        def __init__(self) -> None:
            self.calls: list[int | None] = []

        async def list_tasks(self, limit: int | None = 5):
            self.calls.append(limit)
            assert limit == 5
            return [
                {
                    "id": "task-1",
                    "title": "Recent task only",
                    "kind": "task",
                    "status": "running",
                    "updated_at": "2026-03-09T08:00:00+00:00",
                },
            ]

    app = build_runtime_center_app()
    state_query = StrictLimitedStateQueryService()
    app.state.state_query_service = state_query
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()

    client = TestClient(app)
    response = client.get("/runtime-center/overview")

    assert response.status_code == 200
    assert state_query.calls == [5]


def test_runtime_center_chat_run_and_task_list_endpoints() -> None:
    app = build_runtime_center_app()
    app.state.turn_executor = FakeTurnExecutor()
    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)

    run_response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-task",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "登录京东后台并整理商品上架流程"}],
                },
            ],
            "agent_id": "copaw-agent-runner",
            "industry_instance_id": "industry-v1-ops",
            "industry_role_id": "execution-core",
            "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
        },
    )

    assert run_response.status_code == 200
    assert len(app.state.turn_executor.stream_calls) == 1
    request_payload = app.state.turn_executor.stream_calls[0]["request_payload"]
    assert getattr(request_payload, "interaction_mode", None) == "auto"

def test_runtime_center_chat_run_ignores_legacy_kernel_task_flags() -> None:
    app = build_runtime_center_app()
    turn_executor = FakeTurnExecutor()
    app.state.turn_executor = turn_executor

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        params={
            "kernel_task_id": "query:session:console:ops-user:industry-chat:industry-v1-ops:execution-core",
            "skip_kernel_admission": "true",
        },
        json={
            "id": "req-task-follow-up",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "继续执行并给我结果"}],
                },
            ],
            "session_kind": "industry-control-thread",
            "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
        },
    )

    assert response.status_code == 200
    assert len(turn_executor.stream_calls) == 1
    assert turn_executor.stream_calls[0]["kernel_task_id"] is None
    assert turn_executor.stream_calls[0]["skip_kernel_admission"] is False
    assert (
        getattr(turn_executor.stream_calls[0]["request_payload"], "interaction_mode", None)
        == "auto"
    )
    assert '"kernel_task_id": null' in response.text
    assert '"skip_kernel_admission": false' in response.text


def test_runtime_center_chat_run_preserves_explicit_environment_continuity_context() -> None:
    app = build_runtime_center_app()
    query_execution_service = _CapturingRouteQueryExecutionService()
    chat_service = _CapturingRouteChatService()
    session_backend = object()
    persisted_session = SessionMount(
        id="session:console:desktop-session-1",
        environment_id="env:desktop:session-1",
        channel="console",
        session_id="desktop-session-1",
        lease_status="leased",
        lease_owner="ops-agent",
        lease_token="lease-persisted",
        live_handle_ref="live:desktop:session-1",
    )

    async def _resolve_intake_contract(**_kwargs):
        return MainBrainIntakeContract(
            message_text="Continue the assigned desktop workflow.",
            decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
            intent_kind="execute-task",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=True,
        )

    app.state.turn_executor = KernelTurnExecutor(
        session_backend=session_backend,
        environment_service=_CapturingRouteEnvironmentService(
            sessions={persisted_session.id: persisted_session},
        ),
        query_execution_service=query_execution_service,
        main_brain_chat_service=chat_service,
        main_brain_orchestrator=MainBrainOrchestrator(
            query_execution_service=query_execution_service,
            session_backend=session_backend,
            intake_contract_resolver=_resolve_intake_contract,
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-env-continuity",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "interaction_mode": "orchestrate",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "继续这个桌面会话并完成当前任务"}],
                },
            ],
                "session_kind": "industry-control-thread",
                "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
                "industry_instance_id": "industry-v1-ops",
                "environment_ref": "desktop:session-1",
                "environment_session_id": persisted_session.id,
                "continuity_token": "continuity:desktop-session-1",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(query_execution_service.calls) == 1
    assert chat_service.calls == []
    request = query_execution_service.calls[0]["request"]
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["environment_ref"] == "desktop:session-1"
    assert runtime_context["environment_session_id"] == persisted_session.id
    assert runtime_context["environment_continuity_token"] == "continuity:desktop-session-1"
    assert runtime_context["environment_continuity_source"] == "session-lease"
    assert runtime_context["environment_resume_ready"] is True
    assert runtime_context["recovery_mode"] == "resume-environment"
    assert runtime_context["recovery_reason"] == "session-lease"
    assert runtime_context["recovery_continuity_token"] == "continuity:desktop-session-1"
    assert '"resolved_interaction_mode":"orchestrate"' in response.text


def test_runtime_center_chat_run_attaches_environment_without_claiming_resume_on_session_only() -> None:
    app = build_runtime_center_app()
    query_execution_service = _CapturingRouteQueryExecutionService()
    chat_service = _CapturingRouteChatService()
    session_backend = object()

    async def _resolve_intake_contract(**_kwargs):
        return MainBrainIntakeContract(
            message_text="Continue the assigned desktop workflow.",
            decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
            intent_kind="execute-task",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=True,
        )

    app.state.turn_executor = KernelTurnExecutor(
        session_backend=session_backend,
        query_execution_service=query_execution_service,
        main_brain_chat_service=chat_service,
        main_brain_orchestrator=MainBrainOrchestrator(
            query_execution_service=query_execution_service,
            session_backend=session_backend,
            intake_contract_resolver=_resolve_intake_contract,
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-env-attach-only",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "interaction_mode": "orchestrate",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "继续这个桌面会话并完成当前任务"}],
                },
            ],
                "session_kind": "industry-control-thread",
                "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
                "industry_instance_id": "industry-v1-ops",
                "environment_ref": "desktop:session-1",
                "environment_session_id": "session:console:desktop-session-1",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(query_execution_service.calls) == 1
    assert chat_service.calls == []
    request = query_execution_service.calls[0]["request"]
    runtime_context = getattr(request, "_copaw_main_brain_runtime_context")
    assert runtime_context["environment_ref"] == "desktop:session-1"
    assert runtime_context["environment_session_id"] == "session:console:desktop-session-1"
    assert runtime_context["environment_continuity_source"] == "environment-session"
    assert runtime_context["environment_resume_ready"] is False
    assert runtime_context["recovery_mode"] == "attach-environment"
    assert runtime_context["recovery_reason"] == "environment-session-without-continuity-proof"
    assert '"resolved_interaction_mode":"orchestrate"' in response.text


def test_runtime_center_chat_run_chat_only_turn_skips_orchestrator_runtime_context() -> None:
    app = build_runtime_center_app()
    query_execution_service = _CapturingRouteQueryExecutionService()
    chat_service = _CapturingRouteChatService()
    app.state.turn_executor = KernelTurnExecutor(
        session_backend=object(),
        query_execution_service=query_execution_service,
        main_brain_chat_service=chat_service,
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-chat-only",
            "session_id": "sess-chat-only",
            "user_id": "ops-user",
            "channel": "console",
            "interaction_mode": "auto",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "如果继续执行会发生什么？"}],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert len(chat_service.calls) == 1
    assert query_execution_service.calls == []
    request = chat_service.calls[0]["request"]
    assert getattr(request, "_copaw_resolved_interaction_mode") == "chat"
    assert not hasattr(request, "_copaw_main_brain_runtime_context")
    assert '"resolved_interaction_mode":"chat"' in response.text

class _CommitAwareTurnExecutor:
    def __init__(
        self,
        *,
        runtime_context: dict[str, object] | None = None,
        commit_state: MainBrainCommitState | None = None,
        timing_profile: dict[str, object] | None = None,
    ) -> None:
        self.runtime_context = dict(runtime_context or {})
        self.commit_state = commit_state
        self.timing_profile = dict(timing_profile or {})

    async def stream_request(
        self,
        request_payload,
        *,
        kernel_task_id: str | None = None,
        skip_kernel_admission: bool = False,
    ):
        if self.runtime_context:
            setattr(request_payload, "_copaw_main_brain_runtime_context", self.runtime_context)
        if self.commit_state is not None:
            setattr(request_payload, "_copaw_main_brain_commit_state", self.commit_state)
        if self.timing_profile:
            setattr(request_payload, "_copaw_main_brain_timing", self.timing_profile)
        yield {
            "object": "response",
            "status": "completed",
            "sequence_number": 0,
        }


def _parse_sse_events(raw_text: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for chunk in raw_text.strip().split("\n\n"):
        if not chunk:
            continue
        lines = [line for line in chunk.splitlines() if line.strip()]
        for line in lines:
            if not line.startswith("data:"):
                continue
            payload_text = line[len("data:"):].strip()
            if not payload_text:
                continue
            events.append(json.loads(payload_text))
    return events


class _SnapshotSessionBackend:
    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, str], dict[str, object]] = {}

    def load_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        allow_not_exist: bool = False,
    ) -> dict[str, object]:
        _ = allow_not_exist
        return dict(self.snapshots.get((session_id, user_id), {}))

    def save_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        payload: dict[str, object],
        source_ref: str,
    ) -> None:
        _ = source_ref
        self.snapshots[(session_id, user_id)] = dict(payload)


class _BatchGovernanceResult:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = dict(payload)

    def model_dump(self, mode: str = "json") -> dict[str, object]:
        _ = mode
        return dict(self._payload)


class _SnapshotAwareGovernanceService:
    def __init__(self, *, result_payload: dict[str, object]) -> None:
        self.calls: list[dict[str, object]] = []
        self._result_payload = dict(result_payload)

    async def batch_decisions(self, **kwargs):
        self.calls.append(dict(kwargs))
        return _BatchGovernanceResult(self._result_payload)


def test_runtime_center_chat_run_streams_reply_then_sidecar_commit_events() -> None:
    app = build_runtime_center_app()
    control_thread_id = "industry-chat:industry-v1-ops:commit-lane"
    runtime_context = {
        "kernel_task_id": "ktask-sidecar",
        "execution_intent": "execute-task",
        "environment_ref": "desktop:session-1",
        "writeback_requested": True,
        "should_kickoff": False,
        "intake_contract": SimpleNamespace(
            intent_kind="execute-task",
            writeback_requested=True,
            should_kickoff=False,
            decision=SimpleNamespace(intention="execute-task", id="decision-1"),
        ),
    }
    app.state.turn_executor = _CommitAwareTurnExecutor(
        runtime_context=runtime_context,
        commit_state=MainBrainCommitState(
            status="confirm_required",
            action_type="writeback_operating_truth",
            reason="confirm_required",
            summary="Approve the backlog writeback before commit.",
            control_thread_id=control_thread_id,
            session_id="session-sidecar",
            payload={"decision_id": "decision-1"},
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-sidecar",
            "session_id": "session-sidecar",
            "user_id": "ops-user",
            "channel": "console",
            "thread_id": control_thread_id,
            "control_thread_id": control_thread_id,
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {"type": "text", "text": "测试主脑流式回复后续 sidecar"}
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    sidecar_events = [
        event
        for event in _parse_sse_events(response.text)
        if event.get("object") == "runtime.sidecar"
    ]
    assert [event["event"] for event in sidecar_events] == [
        "turn_reply_done",
        "commit_started",
        "confirm_required",
    ]
    assert sidecar_events[0]["payload"]["control_thread_id"] == control_thread_id
    assert sidecar_events[2]["payload"]["summary"] == (
        "Approve the backlog writeback before commit."
    )
    assert sidecar_events[2]["payload"]["decision_id"] == "decision-1"


def test_runtime_center_chat_run_turn_reply_done_includes_main_brain_timing_profile() -> None:
    app = build_runtime_center_app()
    control_thread_id = "industry-chat:industry-v1-ops:timing"
    app.state.turn_executor = _CommitAwareTurnExecutor(
        timing_profile={
            "pre_model_ms": 18.2,
            "first_output_ms": 146.4,
            "prompt_context_cache_hit": True,
            "lexical_recall_mode": "skip_short_followup",
        }
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-timing",
            "session_id": "session-timing",
            "user_id": "ops-user",
            "channel": "console",
            "thread_id": control_thread_id,
            "control_thread_id": control_thread_id,
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "show timing"}],
                },
            ],
        },
    )

    assert response.status_code == 200
    sidecar_events = [
        event
        for event in _parse_sse_events(response.text)
        if event.get("object") == "runtime.sidecar"
    ]
    assert sidecar_events[0]["event"] == "turn_reply_done"
    assert sidecar_events[0]["payload"]["timing"] == {
        "pre_model_ms": 18.2,
        "first_output_ms": 146.4,
        "prompt_context_cache_hit": True,
        "lexical_recall_mode": "skip_short_followup",
    }


def test_runtime_center_chat_run_keeps_commit_events_in_same_control_thread() -> None:
    app = build_runtime_center_app()
    control_thread_id = "industry-chat:industry-v1-ops:thread-same"
    task_thread_id = "task-chat:query:session:console:ops-user:req-thread"
    runtime_context = {
        "kernel_task_id": "ktask-thread",
        "execution_intent": "execute-task",
        "environment_ref": "desktop:session-1",
        "writeback_requested": True,
        "should_kickoff": True,
        "intake_contract": SimpleNamespace(
            intent_kind="execute-task",
            writeback_requested=True,
            should_kickoff=True,
        ),
    }
    executor = _CommitAwareTurnExecutor(
        runtime_context=runtime_context,
        commit_state=MainBrainCommitState(
            status="committed",
            action_type="create_backlog_item",
            summary="Committed the backlog item.",
            control_thread_id=control_thread_id,
            session_id="session-thread",
            payload={"record_id": "backlog-1"},
        ),
    )
    app.state.turn_executor = executor

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-thread",
            "session_id": "session-thread",
            "user_id": "ops-user",
            "channel": "console",
            "thread_id": task_thread_id,
            "control_thread_id": control_thread_id,
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "保持线程一致"}],
                },
            ],
        },
    )

    assert response.status_code == 200
    sidecar_events = [
        event
        for event in _parse_sse_events(response.text)
        if event.get("object") == "runtime.sidecar"
    ]
    assert [event["event"] for event in sidecar_events] == [
        "turn_reply_done",
        "commit_started",
        "committed",
    ]
    assert sidecar_events[2]["payload"]["record_id"] == "backlog-1"
    for event in sidecar_events:
        assert event["payload"].get("control_thread_id") == control_thread_id
        assert event["payload"].get("thread_id") == control_thread_id


def test_runtime_center_chat_run_does_not_fabricate_terminal_sidecar_for_noop_deferred() -> None:
    app = build_runtime_center_app()
    control_thread_id = "industry-chat:industry-v1-ops:thread-noop"
    app.state.turn_executor = _CommitAwareTurnExecutor(
        runtime_context={
            "kernel_task_id": "ktask-noop",
            "execution_intent": "chat",
        },
        commit_state=MainBrainCommitState(
            status="commit_deferred",
            action_type="none",
            reason="no_commit_action",
            summary="No commit action was required.",
            control_thread_id=control_thread_id,
            session_id="session-noop",
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-noop",
            "session_id": "session-noop",
            "user_id": "ops-user",
            "channel": "console",
            "thread_id": control_thread_id,
            "control_thread_id": control_thread_id,
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "只是聊天，不需要提交"}],
                },
            ],
        },
    )

    assert response.status_code == 200
    sidecar_events = [
        event
        for event in _parse_sse_events(response.text)
        if event.get("object") == "runtime.sidecar"
    ]
    assert [event["event"] for event in sidecar_events] == ["turn_reply_done"]
    assert sidecar_events[0]["payload"]["control_thread_id"] == control_thread_id


def test_runtime_center_governance_approve_persists_main_brain_commit_resolution() -> None:
    app = build_runtime_center_app()
    control_thread_id = "industry-chat:industry-v1-ops:execution-core"
    session_backend = _SnapshotSessionBackend()
    session_backend.save_session_snapshot(
        session_id=control_thread_id,
        user_id="execution-core-agent",
        payload={
            "main_brain": {
                "phase2_commit": {
                    "status": "confirm_required",
                    "action_type": "writeback_operating_truth",
                    "control_thread_id": control_thread_id,
                    "session_id": control_thread_id,
                    "summary": "Approve the writeback before commit.",
                    "payload": {"decision_id": "decision-1"},
                }
            }
        },
        source_ref="test:/phase2-commit",
    )
    app.state.session_backend = session_backend
    app.state.governance_service = _SnapshotAwareGovernanceService(
        result_payload={
            "action": "decision:approve",
            "requested": 1,
            "succeeded": 1,
            "failed": 0,
            "actor": "ops-user",
            "results": [
                {
                    "decision_request_id": "decision-1",
                    "summary": "Approved and executed",
                    "output": {"record_id": "backlog-1"},
                }
            ],
            "errors": [],
            "evidence_id": "evidence-1",
        },
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/governance/decisions/approve",
        json={
            "decision_ids": ["decision-1"],
            "actor": "ops-user",
            "execute": True,
            "control_thread_id": control_thread_id,
            "session_id": control_thread_id,
            "agent_id": "execution-core-agent",
        },
    )

    assert response.status_code == 200
    snapshot = session_backend.load_session_snapshot(
        session_id=control_thread_id,
        user_id="execution-core-agent",
        allow_not_exist=True,
    )
    phase2 = snapshot["main_brain"]["phase2_commit"]
    assert phase2["status"] == "committed"
    assert phase2["record_id"] == "backlog-1"
    assert phase2["payload"]["decision_id"] == "decision-1"


def test_runtime_center_governance_reject_persists_main_brain_commit_resolution() -> None:
    app = build_runtime_center_app()
    control_thread_id = "industry-chat:industry-v1-ops:execution-core"
    session_backend = _SnapshotSessionBackend()
    session_backend.save_session_snapshot(
        session_id=control_thread_id,
        user_id="execution-core-agent",
        payload={
            "main_brain": {
                "phase2_commit": {
                    "status": "confirm_required",
                    "action_type": "writeback_operating_truth",
                    "control_thread_id": control_thread_id,
                    "session_id": control_thread_id,
                    "summary": "Approve the writeback before commit.",
                    "payload": {"decision_id": "decision-1"},
                }
            }
        },
        source_ref="test:/phase2-commit",
    )
    app.state.session_backend = session_backend
    app.state.governance_service = _SnapshotAwareGovernanceService(
        result_payload={
            "action": "decision:reject",
            "requested": 1,
            "succeeded": 1,
            "failed": 0,
            "actor": "ops-user",
            "results": [
                {
                    "decision_request_id": "decision-1",
                    "summary": "Rejected by operator",
                }
            ],
            "errors": [],
            "evidence_id": "evidence-2",
        },
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/governance/decisions/reject",
        json={
            "decision_ids": ["decision-1"],
            "actor": "ops-user",
            "control_thread_id": control_thread_id,
            "session_id": control_thread_id,
            "agent_id": "execution-core-agent",
        },
    )

    assert response.status_code == 200
    snapshot = session_backend.load_session_snapshot(
        session_id=control_thread_id,
        user_id="execution-core-agent",
        allow_not_exist=True,
    )
    phase2 = snapshot["main_brain"]["phase2_commit"]
    assert phase2["status"] == "commit_failed"
    assert phase2["reason"] == "governance_denied"
    assert phase2["message"] == "Rejected by operator"


def test_runtime_center_chat_run_collects_requested_actions_and_enriches_media_inputs(
    tmp_path,
) -> None:
    app = build_runtime_center_app()
    turn_executor = FakeTurnExecutor()
    app.state.turn_executor = turn_executor
    media_service = _build_media_service()
    app.state.media_service = media_service

    attachment_path = tmp_path / "brief.md"
    attachment_path.write_text(
        "# 京东上架材料\n需要先登录后台，再核对库存、价格和物流模板。",
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-media-task",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "根据这份材料整理执行步骤"}],
                },
            ],
            "thread_id": "industry-chat:industry-v1-ops:execution-core",
            "industry_instance_id": "industry-v1-ops",
            "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
            "requested_actions": ["inspect_host", "writeback_backlog"],
            "media_inputs": [
                {
                    "source_kind": "upload",
                    "filename": attachment_path.name,
                    "storage_uri": str(attachment_path),
                    "entry_point": "chat",
                    "purpose": "chat-answer",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert len(turn_executor.stream_calls) == 1
    request_payload = turn_executor.stream_calls[0]["request_payload"]
    request_data = request_payload.model_dump(mode="python")
    assert request_data["media_inputs"] == []
    assert len(request_data["media_analysis_ids"]) == 1
    assert request_data["requested_actions"] == [
        "inspect_host",
        "writeback_backlog",
    ]
    assert getattr(request_payload, "interaction_mode", None) == "auto"

    analyses = media_service.list_analyses(
        thread_id="industry-chat:industry-v1-ops:execution-core",
        entry_point="chat",
        status="completed",
        limit=10,
    )
    assert len(analyses) == 1
    assert analyses[0].thread_id == "industry-chat:industry-v1-ops:execution-core"
    assert analyses[0].status == "completed"


def test_runtime_center_chat_run_enriches_request_from_media_inputs(tmp_path) -> None:
    app = build_runtime_center_app()
    turn_executor = FakeTurnExecutor()
    media_service = _build_media_service()
    app.state.turn_executor = turn_executor
    app.state.media_service = media_service

    attachment_path = tmp_path / "task-brief.md"
    attachment_path.write_text(
        "# 执行说明\n先整理上架流程，再输出待确认风险点。",
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-media-run",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "thread_id": "industry-chat:industry-v1-ops:execution-core",
            "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
            "session_kind": "industry-control-thread",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "继续执行，并结合附件输出结果"}],
                },
            ],
            "media_inputs": [
                {
                    "source_kind": "upload",
                    "filename": attachment_path.name,
                    "storage_uri": str(attachment_path),
                    "entry_point": "chat",
                    "purpose": "chat-answer",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert len(turn_executor.stream_calls) == 1

    request_payload = turn_executor.stream_calls[0]["request_payload"]
    request_data = request_payload.model_dump(mode="python")
    assert request_data["media_inputs"] == []
    assert len(request_data["media_analysis_ids"]) == 1
    assert getattr(request_payload, "interaction_mode", None) == "auto"

    message_blocks = request_data["input"][-1]["content"]
    text_blocks = [
        block["text"]
        for block in message_blocks
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    assert any("Attached analyzed materials are available below." in block for block in text_blocks)


def test_runtime_center_chat_orchestrate_route_is_retired() -> None:
    app = build_runtime_center_app()
    turn_executor = FakeTurnExecutor()
    app.state.turn_executor = turn_executor

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/orchestrate",
        json={
            "id": "req-orchestrate",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "开始执行并给我结果"}],
                },
            ],
            "control_thread_id": "industry-chat:industry-v1-ops:execution-core",
        },
    )

    assert response.status_code == 404
    assert len(turn_executor.stream_calls) == 0


def test_runtime_center_goal_dispatch_route_is_removed() -> None:
    app = build_runtime_center_app()
    client = TestClient(app)

    response = client.post(
        "/runtime-center/goals/goal-1/dispatch",
        json={"execute": True, "activate": True, "owner_agent_id": "ops-agent"},
    )

    assert response.status_code == 404


def test_runtime_center_task_review_endpoint() -> None:
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)
    response = client.get("/runtime-center/tasks/task-1/review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["review"]["headline"] == "Task is still progressing with formal writeback."
    assert payload["review"]["review_route"] == "/api/runtime-center/tasks/task-1/review"


def test_cron_exposes_runtime_center_surface_headers():
    app = FastAPI()
    app.include_router(cron_router)
    app.state.cron_manager = FakeCronManager([])

    client = TestClient(app)

    cron_response = client.get("/cron/jobs")
    assert cron_response.status_code == 200
    assert cron_response.headers["x-copaw-runtime-surface"] == "cron"
    assert cron_response.headers["x-copaw-runtime-overview"] == "/api/runtime-center/overview"


def test_runtime_center_schedule_control_endpoints(tmp_path) -> None:
    app = build_runtime_center_app()
    manager = FakeCronManager([make_job("sched-1")])
    app.state.cron_manager = manager
    app.state.state_query_service = FakeScheduleStateQueryService(manager)
    _wire_governed_schedule_runtime(app, manager, tmp_path)

    client = TestClient(app)

    list_response = client.get("/runtime-center/schedules")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == "sched-1"
    assert list_response.json()[0]["actions"]["delete"] == "/api/runtime-center/schedules/sched-1"

    detail_response = client.get("/runtime-center/schedules/sched-1")
    assert detail_response.status_code == 200
    assert detail_response.json()["actions"]["pause"] == "/api/runtime-center/schedules/sched-1/pause"

    pause_response = client.post("/runtime-center/schedules/sched-1/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["paused"] is True
    assert pause_response.json()["schedule"]["schedule"]["enabled"] is False
    assert "resume" in pause_response.json()["schedule"]["actions"]

    resume_response = client.post("/runtime-center/schedules/sched-1/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["resumed"] is True
    assert resume_response.json()["schedule"]["schedule"]["enabled"] is True
    assert "pause" in resume_response.json()["schedule"]["actions"]

    run_response = client.post("/runtime-center/schedules/sched-1/run")
    assert run_response.status_code == 200
    assert run_response.json()["started"] is True
    assert run_response.json()["schedule"]["runtime"]["status"] == "running"


def test_runtime_center_schedule_write_endpoints_enter_governed_confirm_flow(
    tmp_path,
) -> None:
    app = build_runtime_center_app()
    manager = FakeCronManager([make_job("sched-1")])
    app.state.cron_manager = manager
    app.state.state_query_service = FakeScheduleStateQueryService(manager)
    _wire_governed_schedule_runtime(app, manager, tmp_path)

    client = TestClient(app)

    create_payload = make_job("sched-2").model_dump(mode="json")
    create_response = client.post("/runtime-center/schedules", json=create_payload)
    assert create_response.status_code == 200
    create_result = create_response.json()
    assert create_result["created"] is False
    assert create_result["result"]["phase"] == "waiting-confirm"
    create_decision_id = create_result["result"]["decision_request_id"]
    assert create_decision_id
    assert asyncio.run(manager.get_job("sched-2")) is None

    create_approval = client.post(
        f"/runtime-center/decisions/{create_decision_id}/approve",
        json={"resolution": "Approve schedule creation.", "execute": True},
    )
    assert create_approval.status_code == 200
    assert create_approval.json()["phase"] == "completed"
    assert create_approval.json()["decision_request_id"] == create_decision_id

    created_detail = client.get("/runtime-center/schedules/sched-2")
    assert created_detail.status_code == 200
    assert created_detail.json()["schedule"]["id"] == "sched-2"

    duplicate_response = client.post("/runtime-center/schedules", json=create_payload)
    assert duplicate_response.status_code == 409

    update_payload = make_job("sched-2", enabled=False).model_dump(mode="json")
    update_payload["name"] = "Updated schedule"
    update_response = client.put("/runtime-center/schedules/sched-2", json=update_payload)
    assert update_response.status_code == 200
    update_result = update_response.json()
    assert update_result["updated"] is False
    assert update_result["result"]["phase"] == "waiting-confirm"
    update_decision_id = update_result["result"]["decision_request_id"]
    assert update_decision_id

    update_approval = client.post(
        f"/runtime-center/decisions/{update_decision_id}/approve",
        json={"resolution": "Approve schedule update.", "execute": True},
    )
    assert update_approval.status_code == 200
    assert update_approval.json()["phase"] == "completed"
    assert update_approval.json()["decision_request_id"] == update_decision_id

    updated_detail = client.get("/runtime-center/schedules/sched-2")
    assert updated_detail.status_code == 200
    assert updated_detail.json()["schedule"]["title"] == "Updated schedule"
    assert updated_detail.json()["schedule"]["enabled"] is False

    mismatch_payload = make_job("sched-3").model_dump(mode="json")
    mismatch_response = client.put("/runtime-center/schedules/sched-2", json=mismatch_payload)
    assert mismatch_response.status_code == 400

    delete_response = client.delete("/runtime-center/schedules/sched-2")
    assert delete_response.status_code == 200
    delete_result = delete_response.json()
    assert delete_result["deleted"] is False
    assert delete_result["result"]["phase"] == "waiting-confirm"
    delete_decision_id = delete_result["result"]["decision_request_id"]
    assert delete_decision_id

    delete_rejection = client.post(
        f"/runtime-center/decisions/{delete_decision_id}/reject",
        json={"resolution": "Keep this schedule active."},
    )
    assert delete_rejection.status_code == 200
    assert delete_rejection.json()["phase"] == "cancelled"
    assert delete_rejection.json()["decision_request_id"] == delete_decision_id

    rejected_delete_detail = client.get("/runtime-center/schedules/sched-2")
    assert rejected_delete_detail.status_code == 200

    delete_retry = client.delete("/runtime-center/schedules/sched-2")
    assert delete_retry.status_code == 200
    delete_retry_result = delete_retry.json()
    assert delete_retry_result["deleted"] is False
    assert delete_retry_result["result"]["phase"] == "waiting-confirm"
    delete_retry_decision_id = delete_retry_result["result"]["decision_request_id"]
    assert delete_retry_decision_id

    delete_approval = client.post(
        f"/runtime-center/decisions/{delete_retry_decision_id}/approve",
        json={"resolution": "Delete the schedule.", "execute": True},
    )
    assert delete_approval.status_code == 200
    assert delete_approval.json()["phase"] == "completed"
    assert delete_approval.json()["decision_request_id"] == delete_retry_decision_id

    missing_response = client.get("/runtime-center/schedules/sched-2")
    assert missing_response.status_code == 404


def test_cron_job_write_frontdoor_uses_governed_mutation(tmp_path) -> None:
    app = FastAPI()
    app.include_router(cron_router)
    app.include_router(runtime_center_router)
    manager = FakeCronManager([])
    app.state.cron_manager = manager
    _wire_governed_schedule_runtime(app, manager, tmp_path)

    client = TestClient(app)

    create_response = client.post("/cron/jobs", json=make_job("ignored").model_dump(mode="json"))
    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["created"] is False
    assert payload["result"]["phase"] == "waiting-confirm"
    decision_id = payload["result"]["decision_request_id"]
    created_job = payload["job"]
    created_job_id = created_job["id"]
    assert decision_id
    assert created_job_id
    assert asyncio.run(manager.get_job(created_job_id)) is None

    approval = client.post(
        f"/runtime-center/decisions/{decision_id}/approve",
        json={"resolution": "Approve cron frontdoor schedule.", "execute": True},
    )
    assert approval.status_code == 200
    assert approval.json()["phase"] == "completed"

    detail_response = client.get(f"/cron/jobs/{created_job_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["spec"]["id"] == created_job_id


def test_runtime_center_heartbeat_endpoints() -> None:
    app = build_runtime_center_app()
    manager = FakeCronManager(
        [],
        heartbeat_state=CronJobState(
            last_status="success",
            last_run_at=datetime(2026, 3, 9, 8, 0, tzinfo=timezone.utc),
            next_run_at=datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc),
        ),
    )
    heartbeat_state = {
        "config": HeartbeatConfig(
            enabled=True,
            every="6h",
            target="main",
            activeHours={"start": "08:00", "end": "22:00"},
        ),
    }
    app.state.cron_manager = manager
    app.state.capability_service = FakeCapabilityService()
    app.state.kernel_dispatcher = FakeMutationDispatcher(heartbeat_state)

    def _get_heartbeat_config() -> HeartbeatConfig:
        return heartbeat_state["config"]

    client = TestClient(app)

    with patch(
        "copaw.app.routers.runtime_center.get_heartbeat_config",
        side_effect=_get_heartbeat_config,
    ):
        get_response = client.get("/runtime-center/heartbeat")
        assert get_response.status_code == 200
        assert get_response.json()["runtime"]["query_path"] == "system:run_operating_cycle"
        assert get_response.json()["actions"]["run"] == "/api/runtime-center/heartbeat/run"

        update_response = client.put(
            "/runtime-center/heartbeat",
            json={
                "enabled": True,
                "every": "4h",
                "target": "last",
                "activeHours": {"start": "09:00", "end": "18:00"},
            },
        )
        assert update_response.status_code == 200
        assert update_response.json()["updated"] is True
        assert update_response.json()["heartbeat"]["heartbeat"]["every"] == "4h"
        assert update_response.json()["heartbeat"]["heartbeat"]["target"] == "last"
        assert manager.heartbeat_rescheduled is True

        run_response = client.post("/runtime-center/heartbeat/run")
        assert run_response.status_code == 200
        assert run_response.json()["started"] is True
        assert run_response.json()["result"]["status"] == "success"
        assert run_response.json()["heartbeat"]["runtime"]["status"] == "success"


def test_runtime_center_decision_list_and_detail_endpoints() -> None:
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()

    client = TestClient(app)

    list_response = client.get("/runtime-center/decisions")
    assert list_response.status_code == 200
    decisions = list_response.json()
    assert decisions[0]["id"] == "decision-1"
    assert decisions[0]["route"] == "/api/runtime-center/decisions/decision-1"

    detail_response = client.get("/runtime-center/decisions/decision-1")
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "open"

    missing_response = client.get("/runtime-center/decisions/missing")
    assert missing_response.status_code == 404


def test_runtime_center_agents_endpoint_supports_business_and_system_views() -> None:
    app = build_runtime_center_app()
    app.state.agent_profile_service = FakeAgentProfileService()

    client = TestClient(app)

    all_response = client.get("/runtime-center/agents")
    assert all_response.status_code == 200
    assert {item["agent_id"] for item in all_response.json()} == {
        "ops-agent",
        "copaw-agent-runner",
        "copaw-scheduler",
        "copaw-governance",
    }

    business_response = client.get("/runtime-center/agents", params={"view": "business"})
    assert business_response.status_code == 200
    assert [item["agent_id"] for item in business_response.json()] == ["ops-agent"]

    system_response = client.get("/runtime-center/agents", params={"view": "system"})
    assert system_response.status_code == 200
    assert [item["agent_id"] for item in system_response.json()] == [
        "copaw-scheduler",
        "copaw-governance",
    ]

    scoped_response = client.get(
        "/runtime-center/agents",
        params={
            "view": "business",
            "industry_instance_id": "industry-v1-ops",
        },
    )
    assert scoped_response.status_code == 200
    assert [item["agent_id"] for item in scoped_response.json()] == ["ops-agent"]


def test_runtime_center_decision_approve_and_reject_endpoints() -> None:
    app = build_runtime_center_app()
    app.state.kernel_dispatcher = FakeDecisionDispatcher()

    client = TestClient(app)

    approve_response = client.post(
        "/runtime-center/decisions/decision-1/approve",
        json={"resolution": "Approved from API", "execute": True},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["decision_request_id"] == "decision-1"
    assert approve_response.json()["phase"] == "completed"

    reject_response = client.post(
        "/runtime-center/decisions/decision-1/reject",
        json={"resolution": "Rejected from API"},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["decision_request_id"] == "decision-1"
    assert reject_response.json()["phase"] == "cancelled"


def test_runtime_center_decision_approve_schedules_query_tool_resume() -> None:
    app = build_runtime_center_app()
    app.state.kernel_dispatcher = FakeDecisionDispatcher()
    app.state.decision_request_repository = FakeApproveDecisionRequestRepository(
        decision_type="query-tool-confirmation",
    )
    app.state.query_execution_service = FakeQueryExecutionService()

    scheduled: dict[str, object] = {}

    def _fake_create_task(coro, *args, **kwargs):
        scheduled["called"] = True
        scheduled["args"] = args
        scheduled["kwargs"] = kwargs
        scheduled["coroutine_name"] = getattr(getattr(coro, "cr_code", None), "co_name", None)
        coro.close()
        return SimpleNamespace()

    client = TestClient(app)

    with patch("copaw.app.routers.runtime_center.asyncio.create_task", side_effect=_fake_create_task):
        response = client.post("/runtime-center/decisions/decision-1/approve")

    assert response.status_code == 200
    assert response.json()["resume_scheduled"] is True
    assert response.json()["resume_kind"] == "query-tool-confirmation"
    assert scheduled["called"] is True
    assert scheduled["coroutine_name"] == "_resume_query_tool_confirmation_in_background"


def test_runtime_center_decision_approve_does_not_schedule_resume_for_normal_decisions() -> None:
    app = build_runtime_center_app()
    app.state.kernel_dispatcher = FakeDecisionDispatcher()
    app.state.decision_request_repository = FakeApproveDecisionRequestRepository(
        decision_type="capability-update",
    )
    app.state.query_execution_service = FakeQueryExecutionService()

    client = TestClient(app)

    with patch("copaw.app.routers.runtime_center.asyncio.create_task") as create_task:
        response = client.post("/runtime-center/decisions/decision-1/approve")

    assert response.status_code == 200
    assert "resume_scheduled" not in response.json()
    create_task.assert_not_called()


def test_runtime_center_decision_action_conflicts_map_to_http_errors() -> None:
    app = build_runtime_center_app()
    app.state.kernel_dispatcher = FakeDecisionDispatcher()

    client = TestClient(app)

    approve_response = client.post("/runtime-center/decisions/closed/approve")
    assert approve_response.status_code == 409

    reject_response = client.post("/runtime-center/decisions/closed/reject")
    assert reject_response.status_code == 409
