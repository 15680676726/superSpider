from pathlib import Path
from types import SimpleNamespace

from copaw.compiler.planning.strategy_compiler import StrategyPlanningCompiler
from copaw.industry.models import (
    IndustryExecutionSummary,
    IndustryRoleBlueprint,
    IndustryTeamBlueprint,
)
from copaw.industry.service_runtime_views import _IndustryRuntimeViewsMixin
from copaw.state import AgentRuntimeRecord, IndustryInstanceRecord, StrategyMemoryRecord
from copaw.state import SQLiteStateStore
from copaw.state.repositories import SqliteAgentRuntimeRepository


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


class _CapabilityGovernanceRuntimeViewsHarness(_RuntimeViewsHarness):
    def __init__(self, strategy: StrategyMemoryRecord, runtime_repository) -> None:
        super().__init__(strategy)
        self._agent_runtime_repository = runtime_repository
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
