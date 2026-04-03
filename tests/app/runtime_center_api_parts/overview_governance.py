# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import threading

from .shared import *  # noqa: F401,F403

from agentscope.message import Msg
import pytest
from pydantic import BaseModel
from pydantic_core import PydanticSerializationError

from copaw.capabilities import CapabilityService
from copaw.app.startup_recovery import StartupRecoverySummary
from copaw.environments.models import SessionMount
from copaw.evidence import EvidenceLedger
from copaw.kernel import KernelDispatcher, KernelTaskStore, KernelTurnExecutor
from copaw.kernel.main_brain_intake import MainBrainIntakeContract
from copaw.kernel.main_brain_orchestrator import MainBrainOrchestrator
from copaw.kernel.main_brain_turn_result import MainBrainCommitState
from copaw.media import MediaService
from copaw.app.runtime_center.overview_cards import _RuntimeCenterOverviewCardsSupport
from copaw.app.routers.runtime_center_shared import _encode_sse_event
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


class _BrokenModelDumpEvent:
    def model_dump_json(self) -> str:
        raise PydanticSerializationError("mock serialization failure")

    def model_dump(self, mode: str = "json") -> dict[str, object]:
        _ = mode
        return {
            "object": "message",
            "status": "completed",
            "content": [{"type": "text", "text": "safe fallback"}],
        }


class _UnserializablePayload:
    pass


class _BrokenPydanticEvent(BaseModel):
    object: str = "message"
    status: str = "completed"
    payload: object


def test_runtime_center_overview_support_inherits_entry_builder_mixin() -> None:
    base_modules = {base.__module__ for base in _RuntimeCenterOverviewCardsSupport.__bases__}
    assert "copaw.app.runtime_center.overview_entry_builders" in base_modules
    assert (
        _RuntimeCenterOverviewCardsSupport._build_task_entry.__module__
        == "copaw.app.runtime_center.overview_entry_builders"
    )
    assert (
        _RuntimeCenterOverviewCardsSupport._build_industry_entry.__module__
        == "copaw.app.runtime_center.overview_entry_builders"
    )


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
    app.state.prediction_service = FakePredictionService()
    governance_service = FakeGovernanceService()
    governance_service.status["decision_provenance"] = {
        "open_count": 3,
        "by_type": [
            {"decision_type": "tool-confirmation", "count": 2},
            {"decision_type": "staffing-confirmation", "count": 1},
        ],
        "by_risk_level": [
            {"risk_level": "confirm", "count": 2},
            {"risk_level": "guarded", "count": 1},
        ],
        "by_requester": [
            {"requested_by": "execution-core", "count": 2},
            {"requested_by": "main-brain", "count": 1},
        ],
    }
    app.state.governance_service = governance_service
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
    assert cards["capabilities"]["meta"]["total"] == 3
    assert cards["capabilities"]["meta"]["skill_count"] == 2
    assert cards["capabilities"]["meta"]["mcp_count"] == 2
    assert cards["capabilities"]["meta"]["delta"]["missing_capability_count"] == 1
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
    assert cognition["decision_kind"] == "follow_up_backlog"
    assert cognition["judgment"]["status"] == "attention"
    assert cognition["judgment"]["decision_kind"] == "follow_up_backlog"
    assert "decide whether to dispatch follow-up work" in cognition["judgment"]["summary"]
    assert cognition["next_action"]["kind"] == "followup-backlog"
    assert cognition["next_action"]["decision_kind"] == "follow_up_backlog"
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
    assert payload["signals"]["report_cognition"]["decision_kind"] == "follow_up_backlog"
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
    app.state.prediction_service = FakePredictionService()
    governance_service = FakeGovernanceService()
    governance_service.status["decision_provenance"] = {
        "open_count": 3,
        "by_type": [
            {"decision_type": "tool-confirmation", "count": 2},
            {"decision_type": "staffing-confirmation", "count": 1},
        ],
        "by_risk_level": [
            {"risk_level": "confirm", "count": 2},
            {"risk_level": "guarded", "count": 1},
        ],
        "by_requester": [
            {"requested_by": "execution-core", "count": 2},
            {"requested_by": "main-brain", "count": 1},
        ],
    }
    app.state.governance_service = governance_service
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
    assert payload["governance"]["decision_provenance"]["open_count"] == 3
    assert payload["governance"]["decision_provenance"]["by_type"][0] == {
        "decision_type": "tool-confirmation",
        "count": 2,
    }
    assert payload["governance"]["explain"]["decision_provenance"]["open_count"] == 3
    assert payload["governance"]["explain"]["remediation_summary"] == payload["governance"]["summary"]
    capability_governance = payload["governance"]["capability_governance"]
    assert capability_governance["total"] == 3
    assert capability_governance["enabled"] == 2
    assert capability_governance["skill_count"] == 2
    assert capability_governance["mcp_count"] == 2
    assert capability_governance["package_bound_skill_count"] == 1
    assert capability_governance["package_bound_mcp_count"] == 1
    assert capability_governance["delta"]["missing_capability_count"] == 1
    assert capability_governance["delta"]["trial_count"] == 1
    assert capability_governance["degraded"] is True
    assert capability_governance["degraded_components"][0]["component"] == "capability-coverage"
    assert payload["governance"]["explain"]["degraded_components"][0]["component"] == "capability-coverage"
    assert payload["governance"]["summary"]

    assert payload["recovery"]["available"] is True
    assert payload["recovery"]["route"] == "/api/runtime-center/recovery/latest"
    assert payload["recovery"]["source"] == "startup"
    assert payload["recovery"]["pending_decisions"] == 2
    assert payload["recovery"]["detail"]["decisions"]["pending_decisions"] == 2
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


def test_runtime_center_main_brain_route_prefers_canonical_latest_recovery_report():
    app = build_runtime_center_app()
    app.state.state_query_service = FakeStateQueryService()
    app.state.evidence_query_service = FakeEvidenceQueryService()
    app.state.capability_service = FakeCapabilityService()
    app.state.learning_service = FakeLearningService()
    app.state.agent_profile_service = FakeAgentProfileService()
    app.state.industry_service = FakeIndustryService()
    app.state.prediction_service = FakePredictionService()
    governance_service = FakeGovernanceService()
    governance_service.status["decision_provenance"] = {
        "open_count": 3,
        "by_type": [
            {"decision_type": "tool-confirmation", "count": 2},
            {"decision_type": "staffing-confirmation", "count": 1},
        ],
        "by_risk_level": [
            {"risk_level": "confirm", "count": 2},
            {"risk_level": "guarded", "count": 1},
        ],
        "by_requester": [
            {"requested_by": "execution-core", "count": 2},
            {"requested_by": "main-brain", "count": 1},
        ],
    }
    app.state.governance_service = governance_service
    app.state.routine_service = FakeRoutineService()
    app.state.strategy_memory_service = FakeStrategyMemoryService()
    app.state.startup_recovery_summary = StartupRecoverySummary(
        reason="startup",
        pending_decisions=2,
        active_schedules=1,
    )
    app.state.latest_recovery_report = {
        "reason": "runtime-recovery",
        "pending_decisions": 1,
        "active_schedules": 4,
        "notes": ["Recovered post-start runtime drift."],
    }
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
    assert payload["recovery"]["reason"] == "runtime-recovery"
    assert payload["recovery"]["source"] == "latest"
    assert payload["recovery"]["pending_decisions"] == 1
    assert payload["recovery"]["active_schedules"] == 4
    assert payload["recovery"]["detail"]["decisions"]["pending_decisions"] == 1
    assert payload["recovery"]["detail"]["automation"]["active_schedules"] == 4


def test_runtime_center_overview_capabilities_card_exposes_skill_mcp_governance_projection():
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
    app.state.prediction_service = FakePredictionService()

    client = TestClient(app)
    response = client.get("/runtime-center/overview")

    assert response.status_code == 200
    payload = response.json()
    cards = {
        card["key"]: card
        for card in payload["cards"]
    }
    capabilities = cards["capabilities"]
    assert capabilities["meta"]["skill_count"] == 2
    assert capabilities["meta"]["mcp_count"] == 2
    assert capabilities["meta"]["package_bound_skill_count"] == 1
    assert capabilities["meta"]["package_bound_mcp_count"] == 1
    assert capabilities["meta"]["delta"]["missing_capability_count"] == 1
    assert capabilities["meta"]["degraded"] is True


def test_runtime_center_main_brain_route_exposes_automation_loop_and_supervisor_health():
    class _FakeLoopTask:
        def __init__(
            self,
            *,
            name: str,
            done: bool = False,
            cancelled: bool = False,
        ) -> None:
            self._name = name
            self._done = done
            self._cancelled = cancelled

        def get_name(self) -> str:
            return self._name

        def done(self) -> bool:
            return self._done

        def cancelled(self) -> bool:
            return self._cancelled

    class _FakeRuntimeRepository:
        def list_runtimes(self, limit=None):
            assert limit is None
            return [
                SimpleNamespace(
                    agent_id="agent-1",
                    runtime_status="blocked",
                    metadata={
                        "supervisor_last_failure_at": "2026-04-02T10:00:00+00:00",
                        "supervisor_last_failure_type": "RuntimeError",
                    },
                ),
                SimpleNamespace(
                    agent_id="agent-2",
                    runtime_status="queued",
                    metadata={},
                ),
            ]

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
        reason="Recovered leases after restart.",
        expired_decisions=0,
        pending_decisions=1,
        active_schedules=2,
        notes=["Recovered canonical scheduler ownership after restart."],
    )
    app.state.cron_manager = FakeCronManager([make_job("sched-1")])
    app.state.automation_tasks = [
        _FakeLoopTask(name="copaw-automation-host-recovery", done=False),
        _FakeLoopTask(name="copaw-automation-operating-cycle", done=True),
    ]
    app.state.actor_supervisor = SimpleNamespace(
        _loop_task=_FakeLoopTask(name="copaw-actor-supervisor", done=False),
        _poll_interval_seconds=1.25,
        _agent_tasks={
            "agent-1": _FakeLoopTask(name="copaw-actor:agent-1", done=False),
            "agent-2": _FakeLoopTask(name="copaw-actor:agent-2", done=True),
        },
        _runtime_repository=_FakeRuntimeRepository(),
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

    assert payload["automation"]["loop_count"] == 2
    assert payload["automation"]["active_loop_count"] == 1
    assert payload["automation"]["loops"][0]["name"] == "copaw-automation-host-recovery"
    assert payload["automation"]["loops"][0]["status"] == "running"
    assert payload["automation"]["loops"][1]["status"] == "completed"
    assert payload["automation"]["supervisor"]["status"] == "degraded"
    assert payload["automation"]["supervisor"]["running"] is True
    assert payload["automation"]["supervisor"]["poll_interval_seconds"] == 1.25
    assert payload["automation"]["supervisor"]["active_agent_run_count"] == 1
    assert payload["automation"]["supervisor"]["blocked_runtime_count"] == 1
    assert payload["automation"]["supervisor"]["recent_failure_count"] == 1
    assert payload["automation"]["supervisor"]["last_failure_type"] == "RuntimeError"


def test_runtime_center_main_brain_route_exposes_automation_loop_snapshots():
    class _FakeLoopTask:
        def __init__(
            self,
            *,
            name: str,
            done: bool = False,
            cancelled: bool = False,
        ) -> None:
            self._name = name
            self._done = done
            self._cancelled = cancelled

        def get_name(self) -> str:
            return self._name

        def done(self) -> bool:
            return self._done

        def cancelled(self) -> bool:
            return self._cancelled

    class _FakeAutomationTasks(list):
        def loop_snapshots(self) -> dict[str, dict[str, object]]:
            return {
                "host-recovery": {
                    "task_name": "host-recovery",
                    "capability_ref": "system:run_host_recovery",
                    "owner_agent_id": "copaw-main-brain",
                    "interval_seconds": 300,
                    "automation_task_id": (
                        "copaw-main-brain:host-recovery:system:run_host_recovery"
                    ),
                    "coordinator_contract": "automation-coordinator/v1",
                    "loop_phase": "blocked",
                    "health_status": "idle",
                    "last_gate_reason": "no-actionable-host-events",
                    "last_result_phase": None,
                    "last_error_summary": None,
                    "submit_count": 0,
                    "consecutive_failures": 0,
                },
                "operating-cycle": {
                    "task_name": "operating-cycle",
                    "capability_ref": "system:run_operating_cycle",
                    "owner_agent_id": "copaw-main-brain",
                    "interval_seconds": 180,
                    "automation_task_id": (
                        "copaw-main-brain:operating-cycle:system:run_operating_cycle"
                    ),
                    "coordinator_contract": "automation-coordinator/v1",
                    "loop_phase": "failed",
                    "health_status": "degraded",
                    "last_gate_reason": "active-industry",
                    "last_result_phase": "failed",
                    "last_error_summary": "planner timeout",
                    "submit_count": 3,
                    "consecutive_failures": 2,
                },
            }

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
    app.state.cron_manager = FakeCronManager([make_job("sched-1")])
    app.state.automation_tasks = _FakeAutomationTasks(
        [
            _FakeLoopTask(name="copaw-automation-host-recovery", done=False),
            _FakeLoopTask(name="copaw-automation-operating-cycle", done=False),
        ],
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
    host_recovery = payload["automation"]["loops"][0]
    operating_cycle = payload["automation"]["loops"][1]

    assert host_recovery["automation_task_id"] == (
        "copaw-main-brain:host-recovery:system:run_host_recovery"
    )
    assert host_recovery["coordinator_contract"] == "automation-coordinator/v1"
    assert host_recovery["loop_phase"] == "blocked"
    assert host_recovery["health_status"] == "idle"
    assert host_recovery["last_gate_reason"] == "no-actionable-host-events"

    assert operating_cycle["loop_phase"] == "failed"
    assert operating_cycle["health_status"] == "degraded"
    assert operating_cycle["last_result_phase"] == "failed"
    assert operating_cycle["last_error_summary"] == "planner timeout"
    assert operating_cycle["submit_count"] == 3
    assert operating_cycle["consecutive_failures"] == 2


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
    assert cards["capabilities"]["meta"]["total"] == 3
    assert cards["capabilities"]["meta"]["skill_count"] == 2
    assert cards["capabilities"]["meta"]["mcp_count"] == 2
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


def test_runtime_center_governance_status_includes_capability_governance_projection() -> None:
    app = build_runtime_center_app()
    app.state.governance_service = FakeGovernanceService()
    app.state.capability_service = FakeCapabilityService()
    app.state.prediction_service = FakePredictionService()

    client = TestClient(app)
    response = client.get("/runtime-center/governance/status")

    assert response.status_code == 200
    payload = response.json()
    capability_governance = payload["capability_governance"]
    assert capability_governance["total"] == 3
    assert capability_governance["enabled"] == 2
    assert capability_governance["skill_count"] == 2
    assert capability_governance["mcp_count"] == 2
    assert capability_governance["package_bound_skill_count"] == 1
    assert capability_governance["package_bound_mcp_count"] == 1
    assert capability_governance["delta"]["missing_capability_count"] == 1
    assert capability_governance["delta"]["trial_count"] == 1
    assert capability_governance["degraded"] is True
    assert capability_governance["degraded_components"][0]["component"] == "capability-coverage"


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


def test_runtime_center_chat_run_e2e_routes_builtin_tool_calls_through_capability_frontdoor(
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    import copaw.kernel.query_execution as query_execution_module
    from copaw.agents.react_agent import _wrap_tool_function_for_toolkit
    from copaw.agents.tools import get_current_time
    from copaw.capabilities import CapabilityMount
    from copaw.kernel import KernelQueryExecutionService

    app = build_runtime_center_app()

    class _FrontdoorSessionBackend:
        async def load_session_state(self, *, session_id: str, user_id: str, agent) -> None:
            _ = (session_id, user_id, agent)

        async def save_session_state(self, *, session_id: str, user_id: str, agent) -> None:
            _ = (session_id, user_id, agent)

    class _FrontdoorAgentProfileService:
        def get_agent(self, agent_id: str):
            if agent_id != "ops-agent":
                return None
            return SimpleNamespace(
                agent_id="ops-agent",
                actor_key="industry:ops:execution-core",
                actor_fingerprint="fp-ops-v1",
                name="Ops Agent",
                role_name="Operations lead",
                role_summary="Owns runtime closeout.",
                mission="Turn the industry brief into an executable operating loop.",
                environment_constraints=[],
                evidence_expectations=[],
                current_focus_kind="goal",
                current_focus_id="goal-1",
                current_focus="Launch runtime center",
                current_task_id="task-1",
                industry_instance_id="industry-v1-ops",
                industry_role_id="execution-core",
            )

    class _FrontdoorCapabilityService:
        def __init__(self) -> None:
            self.tasks = []

        def list_accessible_capabilities(
            self,
            *,
            agent_id: str | None,
            enabled_only: bool = False,
        ):
            _ = enabled_only
            assert agent_id == "ops-agent"
            return [
                CapabilityMount(
                    id="tool:get_current_time",
                    name="get_current_time",
                    summary="Return the current time.",
                    kind="local-tool",
                    source_kind="tool",
                    risk_level="auto",
                    environment_requirements=[],
                    evidence_contract=["call-record"],
                    role_access_policy=["all"],
                    enabled=True,
                ),
            ]

        async def execute_task(self, task):
            self.tasks.append(task)
            return {
                "success": True,
                "summary": "delegated-http-frontdoor",
            }

    class _FrontdoorDispatcher:
        def __init__(self) -> None:
            self.submitted = []
            self.lifecycle = SimpleNamespace(
                get_task=lambda task_id: next(
                    (task for task in self.submitted if task.id == task_id),
                    None,
                ),
            )

        def submit(self, task):
            self.submitted.append(task)
            return SimpleNamespace(
                task_id=task.id,
                phase="executing",
                summary="admitted",
                error=None,
                decision_request_id=None,
            )

        def complete_task(self, task_id, **kwargs) -> None:
            _ = (task_id, kwargs)

        def fail_task(self, task_id, **kwargs) -> None:
            _ = (task_id, kwargs)

    class _FrontdoorAgent:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.tool_response = None

        async def register_mcp_clients(self) -> None:
            return None

        def set_console_output_enabled(self, *, enabled: bool) -> None:
            _ = enabled

        def rebuild_sys_prompt(self) -> None:
            return None

        async def interrupt(self) -> None:
            return None

        def __call__(self, msgs):
            _ = msgs
            wrapped = _wrap_tool_function_for_toolkit(get_current_time)

            async def _run():
                self.tool_response = await wrapped()
                return "fake-agent-task"

            return _run()

    async def _stream_and_wait_for_agent_tool(*, agents, coroutine_task):
        await coroutine_task
        agent = agents[0]
        text = str(agent.tool_response.content[0]["text"])
        yield Msg(name="assistant", role="assistant", content=text), True

    monkeypatch.setattr(query_execution_module, "CoPawAgent", _FrontdoorAgent)
    monkeypatch.setattr(
        query_execution_module,
        "stream_printing_messages",
        _stream_and_wait_for_agent_tool,
    )
    monkeypatch.setattr(
        query_execution_module,
        "load_config",
        lambda: SimpleNamespace(
            agents=SimpleNamespace(
                running=SimpleNamespace(max_iters=1, max_input_length=512),
            ),
        ),
    )

    capability_service = _FrontdoorCapabilityService()
    kernel_dispatcher = _FrontdoorDispatcher()
    session_backend = _FrontdoorSessionBackend()
    query_execution_service = KernelQueryExecutionService(
        session_backend=session_backend,
        capability_service=capability_service,
        agent_profile_service=_FrontdoorAgentProfileService(),
    )
    chat_service = _CapturingRouteChatService()

    async def _resolve_intake_contract(**_kwargs):
        return MainBrainIntakeContract(
            message_text="what time is it",
            decision=SimpleNamespace(intent_kind="execute-task", kickoff_allowed=True),
            intent_kind="execute-task",
            writeback_requested=False,
            writeback_plan=None,
            should_kickoff=True,
        )

    app.state.turn_executor = KernelTurnExecutor(
        session_backend=session_backend,
        kernel_dispatcher=kernel_dispatcher,
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
            "id": "req-http-frontdoor",
            "session_id": "industry-chat:industry-v1-ops:execution-core",
            "user_id": "ops-user",
            "agent_id": "ops-agent",
            "channel": "console",
            "interaction_mode": "orchestrate",
            "session_kind": "industry-agent-chat",
            "industry_instance_id": "industry-v1-ops",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "what time is it"}],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"execution_mode": "delegated"' in response.text
    assert chat_service.calls == []
    assert len(capability_service.tasks) == 1
    submitted = capability_service.tasks[0]
    assert submitted.capability_ref == "tool:get_current_time"
    assert submitted.owner_agent_id == "ops-agent"
    assert submitted.id.startswith(
        "query:session:console:ops-user:industry-chat:industry-v1-ops:execution-core:",
    )
    assert submitted.payload == {}


class _CommitAwareTurnExecutor:
    def __init__(
        self,
        *,
        runtime_context: dict[str, object] | None = None,
        commit_state: MainBrainCommitState | None = None,
        intent_shell_payload: dict[str, object] | None = None,
        timing_profile: dict[str, object] | None = None,
    ) -> None:
        self.runtime_context = dict(runtime_context or {})
        self.commit_state = commit_state
        self.intent_shell_payload = dict(intent_shell_payload or {})
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
        if self.intent_shell_payload:
            setattr(request_payload, "_copaw_main_brain_intent_shell", self.intent_shell_payload)
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


def test_encode_sse_event_falls_back_when_model_dump_json_raises() -> None:
    payload = _encode_sse_event(_BrokenModelDumpEvent())
    assert payload.startswith("data: ")
    assert "safe fallback" in payload


def test_encode_sse_event_keeps_json_object_shape_for_pydantic_events() -> None:
    payload = _encode_sse_event(_BrokenPydanticEvent(payload=_UnserializablePayload()))
    decoded = json.loads(payload.removeprefix("data: ").strip())
    assert isinstance(decoded, dict)
    assert decoded["object"] == "message"
    assert decoded["status"] == "completed"
    assert isinstance(decoded["payload"], str)


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


def test_runtime_center_chat_run_turn_reply_done_includes_intent_shell_payload() -> None:
    app = build_runtime_center_app()
    control_thread_id = "industry-chat:industry-v1-ops:intent-shell"
    app.state.turn_executor = _CommitAwareTurnExecutor(
        intent_shell_payload={
            "mode_hint": "plan",
            "trigger_source": "keyword",
            "matched_text": "计划",
            "confidence": 0.95,
        }
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-intent-shell",
            "session_id": "session-intent-shell",
            "user_id": "ops-user",
            "channel": "console",
            "thread_id": control_thread_id,
            "control_thread_id": control_thread_id,
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "先做个计划，再动手。"}],
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
    assert sidecar_events[0]["payload"]["intent_shell"] == {
        "mode_hint": "plan",
        "label": "PLAN",
        "summary": "Use a compact planning shell for this reply.",
        "hint": (
            "Goal, constraints, affected scope/files, checklist, acceptance criteria, "
            "verification steps."
        ),
        "trigger_source": "keyword",
        "matched_text": "计划",
        "confidence": 0.95,
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


def test_runtime_center_chat_run_emits_accepted_and_commit_sidecars_from_runtime_durability_metadata() -> None:
    app = build_runtime_center_app()
    control_thread_id = "industry-chat:industry-v1-ops:thread-durable"
    app.state.turn_executor = _CommitAwareTurnExecutor(
        runtime_context={
            "kernel_task_id": "ktask-durable",
            "execution_intent": "execute-task",
            "execution_mode": "environment-bound",
            "environment_ref": "desktop:session-1",
            "writeback_requested": True,
            "should_kickoff": True,
            "accepted_persistence": {
                "status": "accepted",
                "source": "query_execution_runtime",
                "boundary": "execution_runtime_intake",
                "control_thread_id": control_thread_id,
                "session_id": "session-durable",
            },
            "commit_outcome": {
                "status": "commit_failed",
                "action_type": "writeback_and_kickoff",
                "reason": "durable_kickoff_failed",
                "message": "kickoff pipeline did not confirm durable persistence",
                "control_thread_id": control_thread_id,
                "session_id": "session-durable",
            },
        },
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-durable",
            "session_id": "session-durable",
            "user_id": "ops-user",
            "channel": "console",
            "thread_id": control_thread_id,
            "control_thread_id": control_thread_id,
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "Continue the same durable control thread."}],
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
        "accepted",
        "turn_reply_done",
        "commit_started",
        "commit_failed",
    ]
    assert sidecar_events[0]["payload"]["status"] == "accepted"
    assert sidecar_events[2]["payload"]["reason"] == "durable_kickoff_failed"
    assert sidecar_events[3]["payload"]["message"] == "kickoff pipeline did not confirm durable persistence"


def test_runtime_center_chat_run_emits_durable_sidecars_from_nested_query_runtime_state() -> None:
    app = build_runtime_center_app()
    control_thread_id = "industry-chat:industry-v1-ops:thread-nested-durable"
    app.state.turn_executor = _CommitAwareTurnExecutor(
        runtime_context={
            "kernel_task_id": "ktask-nested-durable",
            "execution_intent": "execute-task",
            "execution_mode": "environment-bound",
            "environment_ref": "desktop:session-1",
            "writeback_requested": True,
            "should_kickoff": True,
            "query_runtime_state": {
                "accepted_persistence": {
                    "status": "accepted",
                    "source": "query_execution_runtime",
                    "boundary": "execution_runtime_intake",
                    "control_thread_id": control_thread_id,
                    "session_id": "session-nested-durable",
                },
                "commit_outcome": {
                    "status": "committed",
                    "action_type": "writeback_and_kickoff",
                    "summary": "Durably persisted requested main-brain intake writeback and kickoff.",
                    "record_id": "backlog-durable-1",
                    "control_thread_id": control_thread_id,
                    "session_id": "session-nested-durable",
                },
            },
        },
    )

    client = TestClient(app)
    response = client.post(
        "/runtime-center/chat/run",
        json={
            "id": "req-nested-durable",
            "session_id": "session-nested-durable",
            "user_id": "ops-user",
            "channel": "console",
            "thread_id": control_thread_id,
            "control_thread_id": control_thread_id,
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "Continue from the durable runtime state."}],
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
        "accepted",
        "turn_reply_done",
        "commit_started",
        "committed",
    ]
    assert sidecar_events[0]["payload"]["boundary"] == "execution_runtime_intake"
    assert sidecar_events[3]["payload"]["record_id"] == "backlog-durable-1"


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


@pytest.mark.parametrize("action", ["run", "pause", "resume"])
def test_runtime_center_schedule_control_returns_404_for_missing_schedule(action: str) -> None:
    app = build_runtime_center_app()
    app.state.cron_manager = FakeCronManager([])

    client = TestClient(app)
    response = client.post(f"/runtime-center/schedules/missing/{action}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Schedule 'missing' not found"


@pytest.mark.parametrize(
    ("action", "enabled"),
    [("run", True), ("pause", True), ("resume", False)],
)
def test_runtime_center_schedule_control_returns_400_on_dispatch_failure(
    action: str,
    enabled: bool,
) -> None:
    app = build_runtime_center_app()
    app.state.cron_manager = FakeCronManager([make_job("sched-1", enabled=enabled)])
    app.state.capability_service = FakeCapabilityService()

    class _ErrorDispatcher:
        def __init__(self) -> None:
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
            return KernelResult(
                task_id=task_id,
                success=False,
                phase="failed",
                summary="Failed",
                error=f"schedule {action} failed",
            )

    app.state.kernel_dispatcher = _ErrorDispatcher()

    client = TestClient(app)
    response = client.post(f"/runtime-center/schedules/sched-1/{action}")

    assert response.status_code == 400
    assert response.json()["detail"] == f"schedule {action} failed"


@pytest.mark.parametrize(
    ("action", "enabled", "result_field", "expected_reason"),
    [
        ("pause", False, "paused", "Schedule 'sched-1' is already paused"),
        ("resume", True, "resumed", "Schedule 'sched-1' is already active"),
    ],
)
def test_runtime_center_schedule_control_returns_typed_noop_when_already_at_target_state(
    action: str,
    enabled: bool,
    result_field: str,
    expected_reason: str,
    tmp_path,
) -> None:
    app = build_runtime_center_app()
    manager = FakeCronManager([make_job("sched-1", enabled=enabled)])
    app.state.cron_manager = manager
    app.state.state_query_service = FakeScheduleStateQueryService(manager)
    _wire_governed_schedule_runtime(app, manager, tmp_path)

    client = TestClient(app)
    response = client.post(f"/runtime-center/schedules/sched-1/{action}")

    assert response.status_code == 200
    payload = response.json()
    assert payload[result_field] is False
    assert payload["noop"] is True
    assert payload["reason"] == expected_reason
    assert payload["schedule"]["schedule"]["enabled"] is enabled


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

    update_retry_response = client.put("/runtime-center/schedules/sched-2", json=update_payload)
    assert update_retry_response.status_code == 200
    update_retry_result = update_retry_response.json()
    assert update_retry_result["updated"] is False
    assert update_retry_result["result"]["phase"] == "waiting-confirm"
    assert update_retry_result["result"]["decision_request_id"] == update_decision_id

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


def test_runtime_center_heartbeat_update_returns_400_and_does_not_reschedule_on_dispatch_failure() -> None:
    app = build_runtime_center_app()
    manager = FakeCronManager([])
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

    class _ErrorDispatcher:
        def __init__(self) -> None:
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
            return KernelResult(
                task_id=task_id,
                success=False,
                phase="failed",
                summary="Failed",
                error="heartbeat update failed",
            )

    app.state.kernel_dispatcher = _ErrorDispatcher()

    def _get_heartbeat_config() -> HeartbeatConfig:
        return heartbeat_state["config"]

    client = TestClient(app)

    with patch(
        "copaw.app.routers.runtime_center.get_heartbeat_config",
        side_effect=_get_heartbeat_config,
    ):
        response = client.put(
            "/runtime-center/heartbeat",
            json={
                "enabled": True,
                "every": "4h",
                "target": "last",
                "activeHours": {"start": "09:00", "end": "18:00"},
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "heartbeat update failed"
    assert manager.heartbeat_rescheduled is False


def test_runtime_center_heartbeat_run_returns_started_false_on_failed_result() -> None:
    app = build_runtime_center_app()

    class _FailingHeartbeatManager(FakeCronManager):
        async def run_heartbeat(self, *, ignore_active_hours: bool = True) -> dict[str, object]:
            _ = ignore_active_hours
            self._heartbeat_state = self._heartbeat_state.model_copy(
                update={
                    "last_status": "error",
                    "last_run_at": datetime(2026, 3, 9, 9, 0, tzinfo=timezone.utc),
                    "next_run_at": datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc),
                    "last_error": "manual failure",
                },
            )
            return {
                "status": "failed",
                "task_id": "ktask:heartbeat",
                "error": "manual failure",
            }

    manager = _FailingHeartbeatManager([])
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
        response = client.post("/runtime-center/heartbeat/run")

    assert response.status_code == 200
    assert response.json()["started"] is False
    assert response.json()["result"]["status"] == "failed"
    assert response.json()["heartbeat"]["runtime"]["status"] == "error"
    assert response.json()["heartbeat"]["runtime"]["last_error"] == "manual failure"


def test_runtime_center_heartbeat_run_rejects_duplicate_inflight_submission() -> None:
    app = build_runtime_center_app()
    manager = FakeCronManager(
        [],
        heartbeat_state=CronJobState(
            last_status="success",
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
    app.state.runtime_center_operator_frontdoor_guard = {
        "lock": threading.Lock(),
        "inflight": {"heartbeat:run"},
    }

    def _get_heartbeat_config() -> HeartbeatConfig:
        return heartbeat_state["config"]

    client = TestClient(app)

    with patch(
        "copaw.app.routers.runtime_center.get_heartbeat_config",
        side_effect=_get_heartbeat_config,
    ):
        response = client.post("/runtime-center/heartbeat/run")

    assert response.status_code == 409
    assert response.json()["detail"] == "Heartbeat run is already in progress"


@pytest.mark.parametrize(
    ("action", "enabled", "guard_key", "expected_detail"),
    [
        ("run", True, "schedule:sched-1:run", "Schedule 'sched-1' run is already in progress"),
        ("pause", True, "schedule:sched-1:pause", "Schedule 'sched-1' pause is already in progress"),
        ("resume", False, "schedule:sched-1:resume", "Schedule 'sched-1' resume is already in progress"),
    ],
)
def test_runtime_center_schedule_control_rejects_duplicate_inflight_submission(
    action: str,
    enabled: bool,
    guard_key: str,
    expected_detail: str,
    tmp_path,
) -> None:
    app = build_runtime_center_app()
    manager = FakeCronManager([make_job("sched-1", enabled=enabled)])
    app.state.cron_manager = manager
    app.state.state_query_service = FakeScheduleStateQueryService(manager)
    app.state.runtime_center_operator_frontdoor_guard = {
        "lock": threading.Lock(),
        "inflight": {guard_key},
    }
    _wire_governed_schedule_runtime(app, manager, tmp_path)

    client = TestClient(app)
    response = client.post(f"/runtime-center/schedules/sched-1/{action}")

    assert response.status_code == 409
    assert response.json()["detail"] == expected_detail


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
