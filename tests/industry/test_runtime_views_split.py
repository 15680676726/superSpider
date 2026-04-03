# -*- coding: utf-8 -*-
from pathlib import Path

from copaw.compiler.planning.strategy_compiler import StrategyPlanningCompiler
from copaw.industry.service_runtime_views import _IndustryRuntimeViewsMixin
from copaw.state import IndustryInstanceRecord, StrategyMemoryRecord


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
    assert "目标" not in (summary.next_step or "")
