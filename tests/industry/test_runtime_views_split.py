from pathlib import Path
from types import SimpleNamespace

from copaw.compiler.planning.strategy_compiler import StrategyPlanningCompiler
from copaw.industry.models import (
    IndustryExecutionSummary,
    IndustryRoleBlueprint,
    IndustryTeamBlueprint,
)
from copaw.industry.service_runtime_views import _IndustryRuntimeViewsMixin
from copaw.state import (
    AgentReportRecord,
    AssignmentRecord,
    BacklogItemRecord,
    IndustryInstanceRecord,
    StrategyMemoryRecord,
)
from copaw.state import SQLiteStateStore
from copaw.state.skill_candidate_service import CapabilityCandidateService
from copaw.state.skill_lifecycle_decision_service import (
    SkillLifecycleDecisionService,
)
from copaw.state.skill_trial_service import SkillTrialService
from tests.shared.executor_runtime_compat import (
    AgentRuntimeRecord,
    SqliteAgentRuntimeRepository,
)


class _StrategyServiceStub:
    def __init__(self, strategy: StrategyMemoryRecord) -> None:
        self._strategy = strategy

    def get_active_strategy(
        self,
        *,
        scope_type: str,
        scope_id: str,
        owner_agent_id: str | None = None,
    ) -> StrategyMemoryRecord | None:
        if scope_type != "industry" or scope_id != self._strategy.scope_id:
            return None
        return self._strategy


class _ReportReplanEngineStub:
    def compile(self, synthesis: object | None) -> dict[str, object]:
        return {}


class _RuntimeViewsHarness(_IndustryRuntimeViewsMixin):
    def __init__(self, strategy: StrategyMemoryRecord) -> None:
        self._strategy = strategy
        self._strategy_compiler = StrategyPlanningCompiler()
        self._strategy_memory_service = _StrategyServiceStub(strategy)
        self._report_replan_engine = _ReportReplanEngineStub()

    def _rank_materializable_backlog_items(
        self,
        backlog_items: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        return list(backlog_items)

    def _backlog_item_is_report_followup(
        self,
        item: dict[str, object] | None,
    ) -> bool:
        _ = item
        return False

    def _planner_sidecar_payload(self, value: object | None) -> dict[str, object]:
        if hasattr(value, "model_dump"):
            return dict(value.model_dump(mode="python"))
        if isinstance(value, dict):
            return dict(value)
        return {}

    def _compile_strategy_constraints(
        self,
        *,
        record: IndustryInstanceRecord,
    ) -> object:
        return self._strategy_compiler.compile(self._strategy)

    def _resolve_latest_planning_cycle_entry(
        self,
        *,
        current_cycle: dict[str, object] | None,
        cycles: list[dict[str, object]],
    ) -> dict[str, object] | None:
        return current_cycle or (cycles[0] if cycles else None)

    def _resolve_current_assignment_for_planning(
        self,
        *,
        current_cycle: dict[str, object] | None,
        assignments: list[dict[str, object]],
        selected_assignment_id: str | None = None,
        selected_backlog_item_id: str | None = None,
    ) -> dict[str, object] | None:
        return assignments[0] if assignments else None

    def _resolve_replan_cycle_entry(
        self,
        *,
        current_cycle: dict[str, object] | None,
        current_cycle_entry: dict[str, object] | None,
        cycles: list[dict[str, object]],
    ) -> dict[str, object] | None:
        return current_cycle or current_cycle_entry or (cycles[0] if cycles else None)

    def _resolve_cycle_synthesis_payload(
        self,
        cycle_entry: dict[str, object] | None,
    ) -> dict[str, object]:
        return {}

    def _report_replan_surface_payload(
        self,
        *,
        planning_sidecar: dict[str, object],
        replan_synthesis: dict[str, object] | None,
    ) -> dict[str, object]:
        return {}

    def _evidence_summary(self, evidence: dict[str, object] | None) -> str | None:
        if not isinstance(evidence, dict):
            return None
        summary = str(evidence.get("summary") or "").strip()
        return summary or None

    def _matches_execution_marker(
        self,
        detail_text: str | None,
        markers: tuple[str, ...],
    ) -> bool:
        if not detail_text:
            return False
        lowered = detail_text.lower()
        return any(marker.lower() in lowered for marker in markers)

    def _list_schedule_ids_for_instance(self, instance_id: str) -> list[str]:
        _ = instance_id
        return []


class _CapabilityGovernanceRuntimeViewsHarness(_RuntimeViewsHarness):
    def __init__(self, strategy: StrategyMemoryRecord, runtime_repository) -> None:
        super().__init__(strategy)
        self._executor_runtime_service = runtime_repository.service
        self._goal_service = SimpleNamespace(get_goal=lambda goal_id: None)
        self._goal_override_repository = SimpleNamespace(
            get_override=lambda goal_id: None,
        )
        self._evidence_ledger = None
        self._learning_service = None
        self._media_service = None
        self._agent_profile_service = None

    def _materialize_team_blueprint(
        self,
        record: IndustryInstanceRecord,
    ) -> IndustryTeamBlueprint:
        return IndustryTeamBlueprint(
            team_id=record.instance_id,
            label=f"{record.label} Team",
            summary="Governed runtime team.",
            agents=[
                IndustryRoleBlueprint(
                    role_id="support-seat",
                    agent_id="agent-seat",
                    name="Support Seat",
                    role_name="Support Specialist",
                    role_summary="Handles governed support follow-up.",
                    mission="Close support follow-up with the correct seat pack.",
                    goal_kind="support",
                    agent_class="business",
                    employment_mode="temporary",
                    activation_mode="on-demand",
                    allowed_capabilities=["tool:read_file"],
                ),
            ],
        )

    def _derive_instance_status(self, record: IndustryInstanceRecord) -> str:
        _ = record
        return "active"

    def _materialize_execution_core_identity(
        self,
        record: IndustryInstanceRecord,
        *,
        profile,
        team,
    ):
        _ = (record, profile, team)
        return None

    def _load_strategy_memory(
        self,
        record: IndustryInstanceRecord,
        *,
        profile,
        team,
        execution_core_identity,
    ):
        _ = (record, profile, team, execution_core_identity)
        return None

    def _list_operating_lanes(self, instance_id: str, status=None):
        _ = (instance_id, status)
        return []

    def _current_operating_cycle_record(self, instance_id: str):
        _ = instance_id
        return None

    def _list_operating_cycles(self, instance_id: str, status=None, limit=None):
        _ = (instance_id, status, limit)
        return []

    def _list_assignment_records(self, instance_id: str):
        _ = instance_id
        return []

    def _list_agent_report_records(self, instance_id: str, limit=None):
        _ = (instance_id, limit)
        return []

    def _list_backlog_items(self, instance_id: str, limit=None):
        _ = (instance_id, limit)
        return []

    def _resolve_report_synthesis_payload(
        self,
        *,
        cycle_record,
        agent_report_records,
    ) -> dict[str, object]:
        _ = (cycle_record, agent_report_records)
        return {}

    def _rank_materializable_backlog_items(
        self,
        backlog_items: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        return list(backlog_items)

    def _list_instance_schedules(self, instance_id: str, schedule_ids):
        _ = (instance_id, schedule_ids)
        return []

    def _resolve_instance_goal_ids(
        self,
        record: IndustryInstanceRecord,
        team=None,
    ) -> list[str]:
        _ = (record, team)
        return []

    def _list_instance_agents(self, agent_ids: set[str]) -> list[dict[str, object]]:
        assert agent_ids == {"agent-seat"}
        return [
            {
                "agent_id": "agent-seat",
                "name": "Support Seat",
                "role_name": "Support Specialist",
                "role_summary": "Handles governed support follow-up.",
                "status": "waiting",
                "employment_mode": "temporary",
                "activation_mode": "on-demand",
                "capabilities": [
                    "tool:read_file",
                    "skill:crm-seat-playbook",
                    "mcp:campaign-dashboard",
                    "mcp:browser-temp",
                ],
                "updated_at": "2026-04-03T00:00:00+00:00",
            },
        ]

    def _list_instance_proposals(self, *, goal_ids, task_ids, agent_ids):
        _ = (goal_ids, task_ids, agent_ids)
        return []

    def _list_instance_acquisition_proposals(self, instance_id: str):
        _ = instance_id
        return []

    def _list_instance_install_binding_plans(self, instance_id: str):
        _ = instance_id
        return []

    def _list_instance_onboarding_runs(self, instance_id: str):
        _ = instance_id
        return []

    def _build_reports(self, **kwargs):
        _ = kwargs
        return {}

    def _build_instance_staffing(self, **kwargs):
        _ = kwargs
        return {}

    def _build_instance_execution_summary(self, **kwargs) -> IndustryExecutionSummary:
        _ = kwargs
        return IndustryExecutionSummary(status="idle")

    def _build_instance_main_chain(self, **kwargs):
        _ = kwargs
        return None


class _FocusSelectionDetailRuntimeViewsHarness(_CapabilityGovernanceRuntimeViewsHarness):
    def __init__(
        self,
        strategy: StrategyMemoryRecord,
        runtime_repository,
        *,
        assignments: list[AssignmentRecord],
        backlog_items: list[BacklogItemRecord],
        execution: IndustryExecutionSummary,
    ) -> None:
        super().__init__(strategy, runtime_repository)
        self._assignment_records = assignments
        self._backlog_records = backlog_items
        self._execution = execution

    def _list_assignment_records(self, instance_id: str):
        _ = instance_id
        return list(self._assignment_records)

    def _list_backlog_items(self, instance_id: str, limit=None):
        _ = (instance_id, limit)
        return list(self._backlog_records)

    def _build_instance_execution_summary(self, **kwargs) -> IndustryExecutionSummary:
        _ = kwargs
        return self._execution


class _AgentReportRouteRuntimeViewsHarness(_FocusSelectionDetailRuntimeViewsHarness):
    def __init__(
        self,
        strategy: StrategyMemoryRecord,
        runtime_repository,
        *,
        assignments: list[AssignmentRecord],
        backlog_items: list[BacklogItemRecord],
        reports: list[AgentReportRecord],
        execution: IndustryExecutionSummary,
    ) -> None:
        super().__init__(
            strategy,
            runtime_repository,
            assignments=assignments,
            backlog_items=backlog_items,
            execution=execution,
        )
        self._reports = reports

    def _list_agent_report_records(self, instance_id: str, limit=None):
        _ = (instance_id, limit)
        return list(self._reports)


def test_runtime_views_mixin_owns_instance_detail_builder() -> None:
    runtime_views = Path("src/copaw/industry/service_runtime_views.py").read_text(
        encoding="utf-8",
    )
    models = Path("src/copaw/industry/models.py").read_text(
        encoding="utf-8",
    )
    service_strategy = Path("src/copaw/industry/service_strategy.py").read_text(
        encoding="utf-8",
    )

    assert "class _IndustryRuntimeViewsMixin:" in runtime_views
    assert "def _build_instance_detail(" in runtime_views
    assert "def _build_main_brain_planning_surface(" in runtime_views
    assert "class IndustryMainBrainPlanningSurface" in models
    assert "def _build_instance_detail(" in service_strategy
    assert "_IndustryRuntimeViewsMixin._build_instance_detail(" in service_strategy


def test_capability_governance_projection_exposes_current_capability_trial(tmp_path) -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
        north_star="Keep governed follow-up visible.",
    )
    state_store = SQLiteStateStore(tmp_path / "runtime-views.db")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-seat",
            actor_key="runtime:agent-seat",
            actor_fingerprint="fp-agent-seat",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="running",
            metadata={
                "capability_layers": {
                    "role_prototype_capability_ids": ["tool:read_file"],
                    "seat_instance_capability_ids": ["mcp:browser_runtime"],
                    "cycle_delta_capability_ids": [],
                    "session_overlay_capability_ids": [],
                    "effective_capability_ids": [
                        "tool:read_file",
                        "mcp:browser_runtime",
                    ],
                },
                "current_capability_trial": {
                    "candidate_id": "cand-browser-runtime",
                    "skill_trial_id": "trial-browser-runtime-seat-primary",
                    "selected_scope": "seat",
                    "selected_seat_ref": "seat-primary",
                    "replacement_target_ids": ["mcp:legacy_browser"],
                },
            },
        ),
    )
    harness = _CapabilityGovernanceRuntimeViewsHarness(strategy, runtime_repository)

    payload = harness._enrich_agent_capability_governance_payload(  # pylint: disable=protected-access
        {
            "agent_id": "agent-seat",
            "status": "running",
            "employment_mode": "temporary",
            "activation_mode": "on-demand",
        },
    )

    trial = payload["capability_governance"]["current_capability_trial"]
    assert trial["candidate_id"] == "cand-browser-runtime"
    assert trial["skill_trial_id"] == "trial-browser-runtime-seat-primary"
    assert trial["selected_scope"] == "seat"
    assert trial["selected_seat_ref"] == "seat-primary"
    assert trial["replacement_target_ids"] == ["mcp:legacy_browser"]


def test_capability_governance_projection_exposes_formal_governance_result(
    tmp_path,
) -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
        north_star="Keep governed capability packs coherent.",
    )
    state_store = SQLiteStateStore(tmp_path / "runtime-views-governance-result.db")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    candidate_service = CapabilityCandidateService(state_store=state_store)
    trial_service = SkillTrialService(state_store=state_store)
    decision_service = SkillLifecycleDecisionService(state_store=state_store)
    baseline = candidate_service.normalize_candidate_source(
        candidate_kind="mcp-bundle",
        target_scope="seat",
        target_role_id="support-seat",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_catalog",
        candidate_source_ref="registry://legacy-browser",
        candidate_source_version="2026.04.06",
        ingestion_mode="baseline-import",
        proposed_skill_name="legacy-browser",
        summary="Protected legacy browser baseline.",
        status="active",
        lifecycle_stage="baseline",
        protection_flags=[
            "protected_from_auto_replace",
            "protected_from_auto_retire",
            "required_by_role_blueprint",
        ],
        canonical_package_id="pkg:browser-runtime",
        equivalence_class="browser-runtime",
        capability_overlap_score=0.91,
        metadata={"mount_id": "mcp:legacy_browser"},
    )
    candidate = candidate_service.normalize_candidate_source(
        candidate_kind="mcp-bundle",
        target_scope="seat",
        target_role_id="support-seat",
        target_seat_ref="seat-primary",
        candidate_source_kind="external_remote",
        candidate_source_ref="https://example.com/browser-runtime-next.zip",
        candidate_source_version="2026.04.06",
        candidate_source_lineage="donor:browser-runtime",
        ingestion_mode="prediction-recommendation",
        proposed_skill_name="browser-runtime-next",
        summary="Next governed browser runtime.",
        status="trial",
        lifecycle_stage="trial",
        canonical_package_id="pkg:browser-runtime",
        equivalence_class="browser-runtime",
        capability_overlap_score=0.93,
        metadata={"mount_id": "mcp:browser_runtime_next"},
    )
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-seat",
            actor_key="runtime:agent-seat",
            actor_fingerprint="fp-agent-seat",
            actor_class="industry-dynamic",
            desired_state="active",
            runtime_status="running",
            industry_role_id="support-seat",
            metadata={
                "selected_seat_ref": "seat-primary",
                "capability_layers": {
                    "role_prototype_capability_ids": [
                        "skill:role-a",
                        "skill:role-b",
                        "skill:role-c",
                        "skill:role-d",
                        "skill:role-e",
                    ],
                    "seat_instance_capability_ids": [
                        "skill:seat-a",
                        "skill:seat-b",
                        "skill:seat-c",
                        "skill:seat-d",
                    ],
                    "cycle_delta_capability_ids": [
                        "mcp:campaign-dashboard",
                        "mcp:legacy_browser",
                    ],
                    "session_overlay_capability_ids": [
                        "mcp:browser_runtime_next",
                    ],
                    "effective_capability_ids": [
                        "skill:role-a",
                        "skill:role-b",
                        "skill:role-c",
                        "skill:role-d",
                        "skill:role-e",
                        "skill:seat-a",
                        "skill:seat-b",
                        "skill:seat-c",
                        "skill:seat-d",
                        "mcp:campaign-dashboard",
                        "mcp:legacy_browser",
                        "mcp:browser_runtime_next",
                    ],
                },
                "current_capability_trial": {
                    "candidate_id": candidate.candidate_id,
                    "skill_trial_id": "trial-browser-runtime-seat-primary",
                    "selected_scope": "session",
                    "selected_seat_ref": "seat-primary",
                    "capability_ids": ["mcp:browser_runtime_next"],
                    "replacement_target_ids": ["mcp:legacy_browser"],
                },
            },
        ),
    )
    trial_service.create_or_update_trial(
        candidate_id=candidate.candidate_id,
        canonical_package_id=candidate.canonical_package_id,
        equivalence_class=candidate.equivalence_class,
        capability_overlap_score=candidate.capability_overlap_score,
        scope_type="seat",
        scope_ref="seat-primary",
        verdict="passed",
        summary="Seat trial passed.",
        success_count=1,
        metadata={"selected_scope": "session"},
    )
    decision_service.create_decision(
        candidate_id=candidate.candidate_id,
        canonical_package_id=candidate.canonical_package_id,
        equivalence_class=candidate.equivalence_class,
        capability_overlap_score=candidate.capability_overlap_score,
        decision_kind="replace_existing",
        from_stage="trial",
        to_stage="active",
        reason="Promote the next browser runtime.",
        replacement_target_ids=["mcp:legacy_browser"],
    )
    harness = _CapabilityGovernanceRuntimeViewsHarness(strategy, runtime_repository)
    harness._prediction_service = SimpleNamespace(
        _capability_candidate_service=candidate_service,
        _skill_trial_service=trial_service,
        _skill_lifecycle_decision_service=decision_service,
        _capability_portfolio_service=None,
    )

    payload = harness._enrich_agent_capability_governance_payload(  # pylint: disable=protected-access
        {
            "agent_id": "agent-seat",
            "status": "running",
            "employment_mode": "temporary",
            "activation_mode": "on-demand",
        },
    )

    governance_result = payload["capability_governance"]["governance_result"]
    assert governance_result["status"] == "guarded"
    assert governance_result["budgets"]["role_skill"]["over_budget"] is True
    assert governance_result["budgets"]["seat_skill"]["over_budget"] is True
    assert governance_result["budgets"]["mcp"]["over_budget"] is True
    assert governance_result["overlap"]["over_budget"] is True
    assert governance_result["replacement_pressure"]["blocked_replacement_target_ids"] == [
        "mcp:legacy_browser",
    ]
    assert governance_result["protection"]["protected_baseline_capability_ids"] == [
        "mcp:legacy_browser",
    ]
    assert governance_result["install_discipline"]["preferred_action"] == (
        "mount_existing_candidate"
    )
    assert any(
        item["action"] == "compact_mcp_budget"
        for item in governance_result["actions"]
    )
    assert any(
        item["action"] == "review_protected_replacement"
        for item in governance_result["actions"]
    )


def test_main_brain_planning_surface_exposes_uncertainty_register_from_durable_strategy_truth() -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
        north_star="Keep governed follow-up visible.",
        review_rules=["repeat-failure-needs-review"],
        strategic_uncertainties=[
            {
                "uncertainty_id": "uncertainty-governed-followup",
                "statement": "Governed follow-up demand may outpace the lane mix.",
                "scope": "strategy",
                "impact_level": "high",
                "current_confidence": 0.42,
                "review_by_cycle": "cycle-weekly-1",
                "escalate_when": ["confidence drop", "target miss"],
            }
        ],
        lane_budgets=[
            {
                "lane_id": "lane-growth",
                "budget_window": "next-2-cycles",
                "target_share": 0.5,
                "min_share": 0.35,
                "max_share": 0.65,
                "review_pressure": "high",
                "force_include_reason": "Keep governed follow-up visible.",
            }
        ],
    )
    runtime_views = _RuntimeViewsHarness(strategy)
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind Robotics",
        owner_scope="industry:northwind",
    )
    current_cycle = {
        "cycle_id": "cycle-daily-1",
        "cycle_kind": "daily",
        "formal_planning": {
            "strategy_constraints": {
                "north_star": strategy.north_star,
                "review_rules": list(strategy.review_rules),
                "strategic_uncertainties": strategy.model_dump(mode="python")[
                    "strategic_uncertainties"
                ],
                "lane_budgets": strategy.model_dump(mode="python")["lane_budgets"],
            },
        },
    }

    surface = runtime_views._build_main_brain_planning_surface(
        record=record,
        current_cycle=current_cycle,
        cycles=[current_cycle],
        assignments=[],
    ).model_dump(mode="json")

    strategy_constraints = surface["strategy_constraints"]
    assert strategy_constraints["strategic_uncertainties"] == current_cycle["formal_planning"][
        "strategy_constraints"
    ]["strategic_uncertainties"]
    assert strategy_constraints["lane_budgets"] == current_cycle["formal_planning"][
        "strategy_constraints"
    ]["lane_budgets"]

    replan = surface["replan"]
    assert [rule["rule_id"] for rule in replan["strategy_trigger_rules"]] == [
        "review-rule:0",
        "uncertainty:uncertainty-governed-followup:confidence-drop",
        "uncertainty:uncertainty-governed-followup:target-miss",
    ]
    assert replan["uncertainty_register"]["durable_source"] == "strategy-memory"
    assert replan["uncertainty_register"]["summary"] == {
        "uncertainty_count": 1,
        "lane_budget_count": 1,
        "trigger_rule_count": 3,
        "review_cycle_ids": ["cycle-weekly-1"],
        "trigger_families": [
            "confidence_collapse",
            "review_rule",
            "target_miss",
        ],
    }
    assert replan["uncertainty_register"]["items"] == [
        {
            "uncertainty_id": "uncertainty-governed-followup",
            "statement": "Governed follow-up demand may outpace the lane mix.",
            "scope": "strategy",
            "impact_level": "high",
            "current_confidence": 0.42,
            "review_by_cycle": "cycle-weekly-1",
            "escalate_when": ["confidence drop", "target miss"],
            "trigger_rule_ids": [
                "uncertainty:uncertainty-governed-followup:confidence-drop",
                "uncertainty:uncertainty-governed-followup:target-miss",
            ],
            "trigger_families": [
                "confidence_collapse",
                "target_miss",
            ],
        }
    ]


def test_execution_summary_without_live_runtime_focus_does_not_fallback_to_goal_title() -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _RuntimeViewsHarness(strategy)
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind Robotics",
        owner_scope="industry:northwind",
        autonomy_status="active",
    )

    summary = runtime_views._build_instance_execution_summary(
        record=record,
        goals=[
            {
                "goal_id": "goal-legacy-focus",
                "title": "Legacy goal title",
                "status": "active",
                "owner_agent_id": "copaw-agent-runner",
                "role_id": "execution-core",
                "updated_at": "2026-04-03T00:00:00Z",
            }
        ],
        agents=[
            {
                "agent_id": "copaw-agent-runner",
                "role_name": "Execution Core",
                "risk_level": "guarded",
            }
        ],
        tasks=[],
        evidence=[],
    )

    assert summary.status == "idle"
    assert summary.current_focus_id is None
    assert summary.current_focus is None
    assert summary.current_owner_agent_id is None
    assert summary.current_owner is None
    assert summary.next_step == "当前没有可继续的执行链。"


def test_execution_summary_does_not_invent_focus_from_live_task_title() -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _RuntimeViewsHarness(strategy)
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind Robotics",
        owner_scope="industry:northwind",
        autonomy_status="active",
    )

    summary = runtime_views._build_instance_execution_summary(
        record=record,
        goals=[
            {
                "goal_id": "goal-legacy-focus",
                "title": "Legacy goal title",
                "status": "active",
                "owner_agent_id": "ops-agent",
                "updated_at": "2026-04-03T00:00:00Z",
            }
        ],
        agents=[
            {
                "agent_id": "ops-agent",
                "role_name": "Operator",
                "risk_level": "guarded",
            }
        ],
        tasks=[
            {
                "task": {
                    "id": "task-live-focus",
                    "title": "Verify storefront copy",
                    "summary": "Verify storefront copy before publish",
                    "status": "running",
                    "owner_agent_id": "ops-agent",
                    "goal_id": "goal-legacy-focus",
                    "acceptance_criteria": '{"kind":"kernel-task-meta-v1","payload":{}}',
                    "updated_at": "2999-04-03T00:01:00Z",
                },
                "runtime": {
                    "runtime_status": "running",
                    "current_phase": "executing",
                    "updated_at": "2999-04-03T00:02:00Z",
                },
                "route": "/api/runtime-center/kernel/tasks/task-live-focus",
                "evidence_count": 0,
            }
        ],
        evidence=[],
    )

    assert summary.status == "executing"
    assert summary.current_focus_id is None
    assert summary.current_focus is None
    assert summary.current_task_id == "task-live-focus"


def test_execution_summary_ignores_malformed_waiting_confirm_task_after_recovery() -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _RuntimeViewsHarness(strategy)
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind Robotics",
        owner_scope="industry:northwind",
        autonomy_status="active",
    )

    summary = runtime_views._build_instance_execution_summary(
        record=record,
        goals=[],
        agents=[
            {
                "agent_id": "ops-agent",
                "role_name": "Operator",
                "risk_level": "guarded",
            }
        ],
        tasks=[
            {
                "task": {
                    "id": "task-stale-waiting-confirm",
                    "title": "Malformed recovery checkpoint",
                    "summary": "Older malformed recovery checkpoint is still hanging around.",
                    "status": "running",
                    "owner_agent_id": "ops-agent",
                    "acceptance_criteria": (
                        '{"kind":"kernel-task-meta-v1","payload":'
                        '{"control_thread_id":"industry-chat:-core",'
                        '"session_id":"industry-chat:-core",'
                        '"thread_id":"industry-chat:-core"}}'
                    ),
                    "updated_at": "2026-04-03T00:01:00Z",
                },
                "runtime": {
                    "runtime_status": "waiting-confirm",
                    "current_phase": "waiting-confirm",
                    "active_environment_id": (
                        "session:console:delegate:query:session:console:"
                        "copaw-agent-runner:industry-chat:-core:"
                        "req-clean-s2-writeback:industry-researcher-northwind-robotics"
                    ),
                    "last_result_summary": "Waiting for operator confirm on malformed recovery thread.",
                    "updated_at": "2026-04-03T00:02:00Z",
                },
                "route": "/api/runtime-center/kernel/tasks/task-stale-waiting-confirm",
                "evidence_count": 0,
            },
            {
                "task": {
                    "id": "task-recovered-child",
                    "title": "Recovered child task",
                    "summary": "Recovered child task failed after confirm.",
                    "status": "failed",
                    "owner_agent_id": "ops-agent",
                    "acceptance_criteria": (
                        '{"kind":"kernel-task-meta-v1","payload":'
                        '{"control_thread_id":"industry-chat:industry-1:execution-core",'
                        '"session_id":"industry-chat:industry-1:execution-core",'
                        '"thread_id":"industry-chat:industry-1:execution-core"}}'
                    ),
                    "updated_at": "2999-04-03T00:05:00Z",
                },
                "runtime": {
                    "runtime_status": "failed",
                    "current_phase": "failed",
                    "active_environment_id": (
                        "session:console:industry-chat:"
                        "industry-1:execution-core"
                    ),
                    "last_error_summary": "Recovered child task failed after confirm.",
                    "updated_at": "2999-04-03T00:06:00Z",
                },
                "route": "/api/runtime-center/kernel/tasks/task-recovered-child",
                "evidence_count": 0,
            },
        ],
        evidence=[],
    )

    assert summary.status == "failed"
    assert summary.current_task_id == "task-recovered-child"
    assert summary.current_owner_agent_id == "ops-agent"
    assert summary.current_focus_id is None
    assert summary.current_focus is None


def test_execution_summary_failed_delegate_wrapper_does_not_misclassify_structured_error_as_waiting_verification() -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _RuntimeViewsHarness(strategy)
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind Robotics",
        owner_scope="industry:northwind",
        autonomy_status="active",
    )

    structured_delegate_failure = (
        "{'parent_task': {'id': 'ctask:stale-parent', "
        "'summary': 'Verify the result and supporting evidence.'}, "
        "'dispatch_result': {'phase': 'cancelled', "
        "'summary': \"Parent task 'ctask:stale-parent' is already failed; "
        "rejecting child admission fail-closed.\"}}"
    )

    summary = runtime_views._build_instance_execution_summary(
        record=record,
        goals=[],
        agents=[
            {
                "agent_id": "ops-agent",
                "role_name": "Operator",
                "risk_level": "guarded",
            }
        ],
        tasks=[
            {
                "task": {
                    "id": "task-delegate-wrapper-failed",
                    "title": "Delegate missing file check",
                    "summary": "Delegated child tasks finished with 0 completed, 1 failed, 0 cancelled.",
                    "status": "failed",
                    "owner_agent_id": "ops-agent",
                    "acceptance_criteria": (
                        '{"kind":"kernel-task-meta-v1","payload":'
                        '{"control_thread_id":"industry-chat:industry-1:execution-core",'
                        '"session_id":"industry-chat:industry-1:execution-core",'
                        '"thread_id":"industry-chat:industry-1:execution-core"}}'
                    ),
                    "updated_at": "2999-04-03T00:07:00Z",
                },
                "runtime": {
                    "runtime_status": "failed",
                    "current_phase": "failed",
                    "active_environment_id": (
                        "session:console:industry-chat:"
                        "industry-1:execution-core"
                    ),
                    "last_error_summary": structured_delegate_failure,
                    "updated_at": "2999-04-03T00:08:00Z",
                },
                "route": "/api/runtime-center/kernel/tasks/task-delegate-wrapper-failed",
                "evidence_count": 0,
            },
        ],
        evidence=[],
    )

    assert summary.status == "failed"
    assert summary.current_task_id == "task-delegate-wrapper-failed"


def test_execution_summary_coordinating_without_live_focus_does_not_fallback_to_goal_title() -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _RuntimeViewsHarness(strategy)
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind Robotics",
        owner_scope="industry:northwind",
        autonomy_status="coordinating",
    )

    summary = runtime_views._build_instance_execution_summary(
        record=record,
        goals=[
            {
                "goal_id": "goal-legacy-focus",
                "title": "Legacy goal title",
                "status": "active",
                "owner_agent_id": "ops-agent",
                "updated_at": "2026-04-03T00:00:00Z",
            }
        ],
        agents=[
            {
                "agent_id": "ops-agent",
                "role_name": "Operator",
                "risk_level": "guarded",
            }
        ],
        tasks=[],
        evidence=[],
    )

    assert summary.status == "coordinating"
    assert summary.current_focus_id is None
    assert summary.current_focus is None
    assert summary.next_step == "主脑正在协调执行位与 backlog，命中条件后会自动继续执行。"


def test_runtime_views_instance_detail_projects_multi_seat_capability_governance(
    tmp_path,
) -> None:
    state_store = SQLiteStateStore(tmp_path / "runtime-views-capability-governance.db")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    runtime_repository.upsert_runtime(
        AgentRuntimeRecord(
            agent_id="agent-seat",
            actor_key="industry-1:support-seat",
            actor_fingerprint="seat-fingerprint",
            actor_class="industry-dynamic",
            desired_state="paused",
            runtime_status="blocked",
            employment_mode="temporary",
            activation_mode="on-demand",
            persistent=False,
            industry_instance_id="industry-1",
            industry_role_id="support-seat",
            metadata={
                "capability_layers": {
                    "schema_version": "industry-seat-capability-layers-v1",
                    "role_prototype_capability_ids": ["tool:read_file"],
                    "seat_instance_capability_ids": ["skill:crm-seat-playbook"],
                    "cycle_delta_capability_ids": ["mcp:campaign-dashboard"],
                    "session_overlay_capability_ids": ["mcp:browser-temp"],
                    "effective_capability_ids": [
                        "tool:read_file",
                        "skill:crm-seat-playbook",
                        "mcp:campaign-dashboard",
                        "mcp:browser-temp",
                    ],
                },
                "current_session_overlay": {
                    "overlay_scope": "session",
                    "overlay_mode": "additive",
                    "session_id": "session-seat-1",
                    "capability_ids": ["mcp:browser-temp"],
                    "status": "active",
                },
                "seat_runtime_status": "blocked",
            },
        ),
    )
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _CapabilityGovernanceRuntimeViewsHarness(
        strategy,
        runtime_repository,
    )
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind Robotics",
        summary="Governed industry runtime.",
        owner_scope="industry:northwind",
        profile_payload={"industry": "robotics", "company_name": "Northwind Robotics"},
        agent_ids=["agent-seat"],
        lifecycle_status="running",
        autonomy_status="coordinating",
    )

    detail = runtime_views._build_instance_detail(record).model_dump(mode="json")

    agent = detail["agents"][0]
    governance = agent["capability_governance"]
    assert governance["is_projection"] is True
    assert governance["is_truth_store"] is False
    assert governance["source"] == "agent_runtime.metadata.capability_layers"
    assert governance["layers"]["role_prototype_capability_ids"] == ["tool:read_file"]
    assert governance["layers"]["seat_instance_capability_ids"] == [
        "skill:crm-seat-playbook",
    ]
    assert governance["layers"]["cycle_delta_capability_ids"] == [
        "mcp:campaign-dashboard",
    ]
    assert governance["layers"]["session_overlay_capability_ids"] == [
        "mcp:browser-temp",
    ]
    assert governance["current_session_overlay"] == {
        "overlay_scope": "session",
        "overlay_mode": "additive",
        "session_id": "session-seat-1",
        "capability_ids": ["mcp:browser-temp"],
        "status": "active",
    }
    assert governance["lifecycle"] == {
        "employment_mode": "temporary",
        "activation_mode": "on-demand",
        "desired_state": "paused",
        "runtime_status": "blocked",
        "status": "waiting",
    }


def test_live_focus_payload_does_not_invent_focus_from_assignment_or_backlog() -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _RuntimeViewsHarness(strategy)
    execution = IndustryExecutionSummary(
        status="executing",
        current_focus_id=None,
        current_focus=None,
        current_owner_agent_id="ops-agent",
        current_owner="Operator",
        current_risk="guarded",
        evidence_count=0,
    )

    payload = runtime_views._resolve_live_focus_payload(
        execution=execution,
        assignments=[
            {
                "assignment_id": "assignment-1",
                "task_id": "task-1",
                "backlog_item_id": "backlog-1",
                "title": "Assignment title",
                "summary": "Assignment summary",
                "status": "active",
            }
        ],
        backlog=[
            {
                "backlog_item_id": "backlog-1",
                "title": "Backlog title",
                "summary": "Backlog summary",
                "status": "open",
            }
        ],
        tasks=[
            {
                "task": {
                    "id": "task-1",
                    "assignment_id": "assignment-1",
                    "title": "Task title",
                    "summary": "Task summary",
                    "status": "running",
                    "updated_at": "2999-04-03T00:01:00Z",
                },
                "runtime": {
                    "runtime_status": "running",
                    "current_phase": "executing",
                    "updated_at": "2999-04-03T00:02:00Z",
                },
            }
        ],
    )

    assert payload["current_assignment_id"] == "assignment-1"
    assert payload["current_backlog_id"] == "backlog-1"
    assert payload["current_focus_id"] is None
    assert payload["current_focus_title"] is None


def test_runtime_views_live_focus_prefers_latest_operator_writeback_chain_when_no_live_task() -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _RuntimeViewsHarness(strategy)

    payload = runtime_views._resolve_live_focus_payload(
        execution=IndustryExecutionSummary(status="idle"),
        assignments=[
            {
                "assignment_id": "assignment-schedule",
                "backlog_item_id": "backlog-schedule",
                "status": "queued",
                "metadata": {},
            },
            {
                "assignment_id": "assignment-operator",
                "backlog_item_id": "backlog-operator",
                "status": "completed",
                "metadata": {
                    "fixed_sop_binding_id": "binding-1",
                    "fixed_sop_binding_name": "Solution Lane Fixed SOP",
                },
            },
        ],
        backlog=[
            {
                "backlog_item_id": "backlog-schedule",
                "status": "materialized",
                "source_kind": "schedule",
                "source_ref": "schedule:daily-review",
                "updated_at": "2026-04-03T00:00:00Z",
                "created_at": "2026-04-03T00:00:00Z",
                "metadata": {},
            },
            {
                "backlog_item_id": "backlog-operator",
                "assignment_id": "assignment-operator",
                "status": "completed",
                "source_kind": "operator",
                "source_ref": "test:sop-binding-backlog",
                "updated_at": "2026-04-03T00:10:00Z",
                "created_at": "2026-04-03T00:05:00Z",
                "metadata": {
                    "fixed_sop_binding_id": "binding-1",
                    "fixed_sop_binding_name": "Solution Lane Fixed SOP",
                },
            },
        ],
        tasks=[],
    )

    assert payload["current_assignment_id"] == "assignment-operator"
    assert payload["current_backlog_id"] == "backlog-operator"


def test_instance_main_chain_uses_chinese_default_read_copy() -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _RuntimeViewsHarness(strategy)
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind Robotics",
        owner_scope="industry:northwind",
        autonomy_status="active",
    )

    payload = runtime_views._build_instance_main_chain(
        record=record,
        lanes=[],
        backlog=[],
        current_cycle=None,
        cycles=[],
        assignments=[],
        agent_reports=[],
        goals=[],
        agents=[],
        tasks=[],
        evidence=[],
        execution=None,
        strategy_memory=None,
    ).model_dump(mode="json")

    nodes = {node["node_id"]: node for node in payload["nodes"]}
    assert nodes["carrier"]["summary"] == "当前共有 0 条泳道、0 个打开的 backlog、0 个 assignment、0 条汇报。"
    assert nodes["writeback"]["summary"] == "还没有记录正式聊天回写。"
    assert nodes["strategy"]["summary"] == "还没有挂接激活中的战略记忆。"
    assert nodes["lane"]["summary"] == "当前还没有选中的执行泳道。"
    assert nodes["backlog"]["summary"] == "当前还没有选中的 backlog 事项。"
    assert nodes["cycle"]["summary"] == "当前还没有选中的执行周期。"
    assert nodes["assignment"]["summary"] == "当前还没有选中的正式 assignment。"
    assert nodes["routine"]["summary"] == "当前任务还没有挂接正式 SOP 或例行执行。"
    assert nodes["child-task"]["summary"] == "当前还没有挂接委派出来的子任务。"
    assert nodes["evidence"]["summary"] == "还没有写入正式证据。"
    assert nodes["report"]["summary"] == "还没有结构化执行汇报回流。"
    assert nodes["replan"]["summary"] == "当前没有明确的重排请求。"
    assert nodes["instance-reconcile"]["summary"] == "团队当前状态为 draft。"


def test_live_focus_payload_keeps_focus_selection_without_overriding_runtime_focus_truth() -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _RuntimeViewsHarness(strategy)

    payload = runtime_views._resolve_live_focus_payload(
        execution=IndustryExecutionSummary(status="idle"),
        assignments=[
            {
                "assignment_id": "assignment-1",
                "backlog_item_id": "backlog-1",
                "title": "Assignment title",
                "summary": "Assignment summary",
                "status": "active",
            }
        ],
        backlog=[
            {
                "backlog_item_id": "backlog-1",
                "title": "Backlog title",
                "summary": "Backlog summary",
                "status": "open",
                "source_kind": "operator",
                "source_ref": "chat-writeback:test",
                "updated_at": "2026-04-03T00:10:00Z",
                "created_at": "2026-04-03T00:05:00Z",
            }
        ],
        tasks=[],
        selected_assignment_id="assignment-1",
    )

    assert payload["current_assignment_id"] == "assignment-1"
    assert payload["current_backlog_id"] == "backlog-1"
    assert payload["current_focus_id"] is None
    assert payload["current_focus_title"] is None


def test_task_entry_continuity_refs_tolerates_missing_kernel_metadata() -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _RuntimeViewsHarness(strategy)

    refs = runtime_views._task_entry_continuity_refs(
        {
            "task": {
                "id": "task-1",
                "acceptance_criteria": None,
            },
            "runtime": {},
        }
    )

    assert refs == []


def test_extract_execution_task_trigger_tolerates_missing_kernel_metadata() -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _RuntimeViewsHarness(strategy)

    trigger = runtime_views._extract_execution_task_trigger(
        {
            "task": {
                "id": "task-1",
                "acceptance_criteria": None,
            },
        }
    )

    assert trigger == {
        "source": None,
        "actor": None,
        "reason": None,
    }


def test_instance_detail_keeps_selected_assignment_without_fabricating_execution_focus(
    tmp_path: Path,
) -> None:
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    state_store = SQLiteStateStore(tmp_path / "runtime-views-focus.db")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    runtime_views = _FocusSelectionDetailRuntimeViewsHarness(
        strategy,
        runtime_repository,
        assignments=[
            AssignmentRecord(
                id="assignment-1",
                industry_instance_id="industry-1",
                backlog_item_id="backlog-1",
                owner_agent_id="agent-seat",
                owner_role_id="support-seat",
                title="Assignment title",
                summary="Assignment summary",
                status="queued",
            )
        ],
        backlog_items=[
            BacklogItemRecord(
                id="backlog-1",
                industry_instance_id="industry-1",
                assignment_id="assignment-1",
                title="Backlog title",
                summary="Backlog summary",
                status="open",
                source_kind="operator",
                source_ref="chat-writeback:test",
            )
        ],
        execution=IndustryExecutionSummary(
            status="executing",
            current_focus_id=None,
            current_focus=None,
            current_owner_agent_id="agent-seat",
            current_owner="Support Specialist",
            current_risk="guarded",
            evidence_count=0,
        ),
    )
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind Robotics",
        summary="Governed industry runtime.",
        owner_scope="industry:northwind",
        profile_payload={"industry": "robotics", "company_name": "Northwind Robotics"},
        agent_ids=["agent-seat"],
        lifecycle_status="running",
        autonomy_status="active",
    )

    detail = runtime_views._build_instance_detail(
        record,
        assignment_id="assignment-1",
    ).model_dump(mode="json")

    assert detail["focus_selection"]["selection_kind"] == "assignment"
    assert detail["focus_selection"]["assignment_id"] == "assignment-1"
    assert detail["execution"]["current_focus_id"] is None
    assert detail["execution"]["current_focus"] is None


def test_industry_runtime_routes_point_to_runtime_center_surface(tmp_path: Path) -> None:
    runtime_views = Path("src/copaw/industry/service_runtime_views.py").read_text(
        encoding="utf-8",
    )
    service_strategy = Path("src/copaw/industry/service_strategy.py").read_text(
        encoding="utf-8",
    )

    assert '"runtime_center": "/api/runtime-center/surface"' in runtime_views
    assert '"runtime_center": "/api/runtime-center/surface"' in service_strategy


def test_instance_detail_prefers_assignment_route_for_report_without_task(tmp_path) -> None:
    state_store = SQLiteStateStore(tmp_path / "runtime-views-report-route.db")
    runtime_repository = SqliteAgentRuntimeRepository(state_store)
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-industry-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Planning truth",
    )
    runtime_views = _AgentReportRouteRuntimeViewsHarness(
        strategy,
        runtime_repository,
        assignments=[
            AssignmentRecord(
                id="assignment-1",
                industry_instance_id="industry-1",
                goal_id="goal-legacy-focus",
                title="Assignment title",
                summary="Assignment summary",
                status="queued",
            ),
        ],
        backlog_items=[],
        reports=[
            AgentReportRecord(
                id="report-1",
                industry_instance_id="industry-1",
                assignment_id="assignment-1",
                goal_id="goal-legacy-focus",
                headline="Report headline",
                summary="Report summary",
                result="completed",
            ),
        ],
        execution=IndustryExecutionSummary(status="idle"),
    )
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Northwind Robotics",
        summary="Governed industry runtime.",
        owner_scope="industry:northwind",
        profile_payload={"industry": "robotics", "company_name": "Northwind Robotics"},
        agent_ids=["agent-seat"],
        lifecycle_status="running",
        autonomy_status="active",
    )

    detail = runtime_views._build_instance_detail(record).model_dump(mode="json")

    assert detail["agent_reports"][0]["route"] == (
        "/api/runtime-center/industry/industry-1?assignment_id=assignment-1"
    )
