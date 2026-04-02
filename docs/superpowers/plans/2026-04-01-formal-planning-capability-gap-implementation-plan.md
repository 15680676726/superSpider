# Formal Planning Capability Gap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build CoPaw's remaining formal short/mid/long-horizon planning stack on top of the existing `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan` truth chain, while keeping Claude-derived planning shell ideas strictly sidecar.

**Architecture:** Add a dedicated formal planning compiler slice under `src/copaw/compiler/planning/` instead of continuing to grow planner logic inside `industry/service_lifecycle.py` or `state/main_brain_service.py`. State services remain the truth-owning read/write layer; the new planning slice compiles strategy, backlog, reports, and runtime facts into typed planning decisions that existing lifecycle/services apply. Claude-derived planning shell artifacts are allowed only as assignment-local sidecars and must never become formal planning truth.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite, pytest, existing CoPaw `state / compiler / industry / predictions / runtime-center` services.

## Status Update (`2026-04-02`)

This plan is now landed for the intended `Task 1 -> Task 7` scope.

Delivered shape:

- `src/copaw/compiler/planning/` now exists as the dedicated formal planning compiler slice
- strategy, cycle, assignment, and report-to-replan planning contracts are typed and tested
- `IndustryService` lifecycle now persists `formal_planning` sidecars on cycle/assignment materialization
- prediction cycle review now receives formal planning overlap context from the real operating-cycle path
- runtime/bootstrap/runtime-view wiring now exposes planner outputs through `main_brain_planning`

Focused verification:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_planning_models.py tests/compiler/test_strategy_compiler.py tests/compiler/test_cycle_planner.py tests/compiler/test_assignment_planner.py tests/compiler/test_report_replan_engine.py tests/app/test_goals_api.py tests/app/test_predictions_api.py tests/app/test_phase_next_autonomy_smoke.py tests/industry/test_report_synthesis.py tests/industry/test_runtime_views_split.py tests/app/test_runtime_bootstrap_split.py -q
```

Result:

- `77 passed`

This closeout does not claim that all future long-horizon planning work is finished.
Remaining next-wave work still includes richer cycle kinds, deeper lane investment policy, and explicit strategic uncertainty / strategy-shift triggers.

---

## Scope Guard

This plan covers only:

- formal planner construction on top of the existing CoPaw truth chain
- assignment-local planner
- cycle planner
- strategy compiler
- report-to-replan engine
- Runtime Center / industry planning visibility for those outputs

This plan does **not** cover:

- replacing CoPaw's formal planning truth with Claude-style session planning
- redesigning `/runtime-center/chat/run`
- replacing `MainBrainOrchestrator`
- redoing truth-first memory
- reopening already-closed Claude runtime contract hardening work

## File Structure

### New files

- `src/copaw/compiler/planning/__init__.py`
  - Export the formal planning compiler pieces.
- `src/copaw/compiler/planning/models.py`
  - Typed planner contracts for strategy constraints, cycle proposals, assignment plans, and replan outcomes.
- `src/copaw/compiler/planning/strategy_compiler.py`
  - Compile `StrategyMemoryRecord` into formal planning constraints.
- `src/copaw/compiler/planning/cycle_planner.py`
  - Compile strategy + backlog + reports into cycle launch decisions.
- `src/copaw/compiler/planning/assignment_planner.py`
  - Build assignment-local plan envelopes, checkpoints, acceptance criteria, and bounded sidecar planning scratch.
- `src/copaw/compiler/planning/report_replan_engine.py`
  - Turn report synthesis and repeated failure patterns into structured follow-up/replan outputs.
- `tests/compiler/test_planning_models.py`
  - Unit tests for typed planning contracts.
- `tests/compiler/test_strategy_compiler.py`
  - Unit tests for strategic constraint compilation.
- `tests/compiler/test_cycle_planner.py`
  - Unit tests for cycle launch/materialization behavior.
- `tests/compiler/test_assignment_planner.py`
  - Unit tests for assignment-local planning envelopes.
- `tests/compiler/test_report_replan_engine.py`
  - Unit tests for report-to-replan decisions.

### Existing files to modify

- `src/copaw/app/runtime_bootstrap_domains.py`
  - Instantiate and wire the new formal planner services.
- `src/copaw/compiler/__init__.py`
  - Re-export planning compiler pieces if needed by domain services/tests.
- `src/copaw/goals/service_compiler.py`
  - Consume assignment planner outputs when compiling goal/assignment work.
- `src/copaw/industry/service_context.py`
  - Carry planner runtime bindings into `IndustryService`.
- `src/copaw/industry/service_lifecycle.py`
  - Replace shallow cycle materialization and report follow-up logic with planner outputs.
- `src/copaw/industry/service_runtime_views.py`
  - Surface formal planner outputs in industry/runtime read models.
- `src/copaw/industry/service_strategy.py`
  - Route strategic fields into the formal strategy compiler instead of thin field propagation only.
- `src/copaw/predictions/service_core.py`
  - Reuse formal cycle review/replan inputs where prediction review overlaps planning review.
- `src/copaw/state/main_brain_service.py`
  - Keep state services as truth-owning helpers while delegating planning decisions to the new compiler layer.
- `tests/app/test_goals_api.py`
  - Lock assignment-local planning compiler context and sidecar boundaries.
- `tests/app/test_predictions_api.py`
  - Lock cycle review/replan integration.
- `tests/app/test_phase_next_autonomy_smoke.py`
  - Lock end-to-end planning chain assumptions.
- `tests/app/test_runtime_bootstrap_split.py`
  - Verify planner services are wired into domain bootstrap.
- `tests/industry/test_report_synthesis.py`
  - Verify report synthesis feeds replan engine outputs.
- `tests/industry/test_runtime_views_split.py`
  - Verify planning outputs appear on runtime read surfaces.
- `TASK_STATUS.md`
  - Record the new formal planning spec/plan once green.

## Task 1: Create the Formal Planning Compiler Slice

**Files:**
- Create: `src/copaw/compiler/planning/__init__.py`
- Create: `src/copaw/compiler/planning/models.py`
- Modify: `src/copaw/compiler/__init__.py`
- Test: `tests/compiler/test_planning_models.py`
- Test: `tests/app/test_runtime_bootstrap_split.py`

- [ ] **Step 1: Write the failing planning model tests**

```python
from copaw.compiler.planning.models import (
    PlanningStrategyConstraints,
    CyclePlanningDecision,
    AssignmentPlanEnvelope,
    ReportReplanDecision,
)


def test_assignment_plan_envelope_keeps_formal_truth_ids() -> None:
    envelope = AssignmentPlanEnvelope(
        assignment_id="assignment-1",
        backlog_item_id="backlog-1",
        lane_id="lane-growth",
        cycle_id="cycle-daily-1",
        checkpoints=[{"kind": "verify", "label": "check result"}],
        acceptance_criteria=["result verified"],
        sidecar_plan={"checklist": ["step 1", "step 2"]},
    )
    assert envelope.assignment_id == "assignment-1"
    assert envelope.sidecar_plan["checklist"] == ["step 1", "step 2"]
```

- [ ] **Step 2: Run tests to verify the compiler slice does not exist yet**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_planning_models.py tests/app/test_runtime_bootstrap_split.py -q
```

Expected:

- FAIL with import errors for `copaw.compiler.planning`

- [ ] **Step 3: Add the new planning package and typed contracts**

```python
from pydantic import BaseModel, Field


class PlanningStrategyConstraints(BaseModel):
    mission: str = ""
    north_star: str = ""
    priority_order: list[str] = Field(default_factory=list)
    lane_weights: dict[str, float] = Field(default_factory=dict)
    planning_policy: list[str] = Field(default_factory=list)
    review_rules: list[str] = Field(default_factory=list)
    paused_lane_ids: list[str] = Field(default_factory=list)


class AssignmentPlanEnvelope(BaseModel):
    assignment_id: str
    backlog_item_id: str | None = None
    lane_id: str | None = None
    cycle_id: str | None = None
    checkpoints: list[dict[str, object]] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    sidecar_plan: dict[str, object] = Field(default_factory=dict)
```

- [ ] **Step 4: Expose the new planning package through `copaw.compiler`**

```python
from .planning import (
    AssignmentPlanEnvelope,
    CyclePlanningDecision,
    PlanningStrategyConstraints,
    ReportReplanDecision,
)
```

- [ ] **Step 5: Run tests to verify the contracts import and bootstrap stays stable**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_planning_models.py tests/app/test_runtime_bootstrap_split.py -q
```

Expected:

- PASS for model import tests
- bootstrap split tests still pass or fail only on missing planner wiring assertions added later

- [ ] **Step 6: Commit**

```powershell
git add src/copaw/compiler/__init__.py src/copaw/compiler/planning tests/compiler/test_planning_models.py tests/app/test_runtime_bootstrap_split.py
git commit -m "feat: add formal planning compiler contracts"
```

## Task 2: Build the Strategy Compiler

**Files:**
- Create: `src/copaw/compiler/planning/strategy_compiler.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/state/main_brain_service.py`
- Test: `tests/compiler/test_strategy_compiler.py`
- Test: `tests/state/test_strategy_memory_contract.py`

- [ ] **Step 1: Write failing strategy compiler tests**

```python
from copaw.compiler.planning.strategy_compiler import StrategyPlanningCompiler
from copaw.state import StrategyMemoryRecord


def test_strategy_compiler_emits_lane_and_review_constraints() -> None:
    compiler = StrategyPlanningCompiler()
    strategy = StrategyMemoryRecord(
        id="strategy-1",
        scope_type="industry",
        scope_id="industry-1",
        north_star="Grow retained revenue",
        priority_order=["retain", "grow", "expand"],
        lane_weights={"lane-retention": 0.7, "lane-growth": 0.3},
        planning_policy=["prefer-followup-before-net-new"],
        review_rules=["repeat-failure-needs-review"],
        paused_lane_ids=["lane-experimental"],
    )
    constraints = compiler.compile(strategy)
    assert constraints.lane_weights["lane-retention"] == 0.7
    assert "repeat-failure-needs-review" in constraints.review_rules
```

- [ ] **Step 2: Run tests to verify no strategy compiler exists yet**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_strategy_compiler.py tests/state/test_strategy_memory_contract.py -q
```

Expected:

- FAIL on missing compiler/import or missing compiled constraint behavior

- [ ] **Step 3: Implement the strategy compiler as a pure compiler layer**

```python
class StrategyPlanningCompiler:
    def compile(self, strategy: StrategyMemoryRecord | None) -> PlanningStrategyConstraints:
        if strategy is None:
            return PlanningStrategyConstraints()
        return PlanningStrategyConstraints(
            mission=strategy.mission,
            north_star=strategy.north_star,
            priority_order=list(strategy.priority_order or []),
            lane_weights={str(k): float(v) for k, v in (strategy.lane_weights or {}).items()},
            planning_policy=list(strategy.planning_policy or []),
            review_rules=list(strategy.review_rules or []),
            paused_lane_ids=list(strategy.paused_lane_ids or []),
        )
```

- [ ] **Step 4: Route strategic field consumption through compiled constraints instead of thin field threading**

```python
constraints = strategy_compiler.compile(active_strategy)
if lane.id in constraints.paused_lane_ids:
    continue
priority_bias = constraints.lane_weights.get(lane.id, 0.0)
```

- [ ] **Step 5: Run strategy tests**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_strategy_compiler.py tests/state/test_strategy_memory_contract.py -q
```

Expected:

- PASS

- [ ] **Step 6: Commit**

```powershell
git add src/copaw/compiler/planning/strategy_compiler.py src/copaw/industry/service_strategy.py src/copaw/state/main_brain_service.py tests/compiler/test_strategy_compiler.py tests/state/test_strategy_memory_contract.py
git commit -m "feat: add formal strategy planning compiler"
```

## Task 3: Build the Cycle Planner

**Files:**
- Create: `src/copaw/compiler/planning/cycle_planner.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/state/main_brain_service.py`
- Modify: `src/copaw/predictions/service_core.py`
- Test: `tests/compiler/test_cycle_planner.py`
- Test: `tests/app/test_predictions_api.py`
- Test: `tests/app/test_phase_next_autonomy_smoke.py`

- [ ] **Step 1: Write failing cycle planner tests**

```python
from copaw.compiler.planning.cycle_planner import CyclePlanner


def test_cycle_planner_does_not_only_pick_top_three_daily_items() -> None:
    planner = CyclePlanner()
    decision = planner.plan_cycle(
        cycle_kind="weekly",
        open_backlog=[
            {"id": "b1", "lane_id": "lane-retention", "priority": 5},
            {"id": "b2", "lane_id": "lane-growth", "priority": 4},
        ],
        pending_reports=[{"id": "r1", "result": "failed"}],
        strategy_constraints={"lane_weights": {"lane-retention": 0.8}},
    )
    assert decision.cycle_kind == "weekly"
    assert decision.selected_backlog_ids
```

- [ ] **Step 2: Run tests to verify current cycle planning is still shallow**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_cycle_planner.py tests/app/test_predictions_api.py tests/app/test_phase_next_autonomy_smoke.py -q
```

Expected:

- FAIL on missing `CyclePlanner`
- or FAIL because lifecycle still hard-codes shallow cycle behavior

- [ ] **Step 3: Implement a typed cycle planning decision**

```python
class CyclePlanner:
    def plan_cycle(self, *, strategy_constraints, open_backlog, pending_reports, cycle_kind_hint=None):
        resolved_cycle_kind = cycle_kind_hint or "daily"
        selected = self._select_backlog(open_backlog, strategy_constraints)
        return CyclePlanningDecision(
            should_start=bool(selected or pending_reports),
            cycle_kind=resolved_cycle_kind,
            selected_backlog_ids=[item["id"] for item in selected],
            review_reasons=self._build_review_reasons(pending_reports, strategy_constraints),
        )
```

- [ ] **Step 4: Replace the shallow launch/materialization path in `service_lifecycle.py` with planner output**

```python
decision = self._cycle_planner.plan_cycle(
    strategy_constraints=strategy_constraints,
    open_backlog=open_backlog_payload,
    pending_reports=pending_reports_payload,
    cycle_kind_hint=self._resolve_cycle_kind_hint(record, strategy_constraints),
)
if decision.should_start:
    new_cycle = self._operating_cycle_service.start_cycle(
        cycle_kind=decision.cycle_kind,
        backlog_item_ids=decision.selected_backlog_ids,
        ...
    )
```

- [ ] **Step 5: Thread cycle review inputs so prediction review consumes the same planning facts**

```python
case_detail = create_cycle_case(
    ...,
    lane_summaries=decision.lane_summaries,
    assignment_summaries=decision.assignment_inputs,
    meeting_window=decision.review_window,
)
```

- [ ] **Step 6: Run cycle/planning regressions**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_cycle_planner.py tests/app/test_predictions_api.py tests/app/test_phase_next_autonomy_smoke.py -q
```

Expected:

- PASS

- [ ] **Step 7: Commit**

```powershell
git add src/copaw/compiler/planning/cycle_planner.py src/copaw/industry/service_lifecycle.py src/copaw/state/main_brain_service.py src/copaw/predictions/service_core.py tests/compiler/test_cycle_planner.py tests/app/test_predictions_api.py tests/app/test_phase_next_autonomy_smoke.py
git commit -m "feat: add formal cycle planner"
```

## Task 4: Build the Assignment Planner

**Files:**
- Create: `src/copaw/compiler/planning/assignment_planner.py`
- Modify: `src/copaw/goals/service_compiler.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Test: `tests/compiler/test_assignment_planner.py`
- Test: `tests/kernel/test_assignment_envelope.py`
- Test: `tests/app/test_goals_api.py`

- [ ] **Step 1: Write failing assignment planner tests**

```python
from copaw.compiler.planning.assignment_planner import AssignmentPlanner


def test_assignment_planner_produces_checkpoints_and_acceptance_criteria() -> None:
    planner = AssignmentPlanner()
    envelope = planner.plan_assignment(
        assignment={"id": "assignment-1", "lane_id": "lane-growth"},
        backlog_item={"id": "backlog-1", "title": "Fix landing page"},
        strategy_constraints={"planning_policy": ["verify-before-close"]},
    )
    assert envelope.checkpoints
    assert "verify-before-close" in envelope.sidecar_plan["planning_policy"]
```

- [ ] **Step 2: Run tests to verify assignment-local planner is missing**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_assignment_planner.py tests/kernel/test_assignment_envelope.py tests/app/test_goals_api.py -q
```

Expected:

- FAIL on missing assignment planner or missing checkpoint/acceptance fields

- [ ] **Step 3: Implement assignment-local planning envelopes**

```python
class AssignmentPlanner:
    def plan_assignment(self, *, assignment, backlog_item, strategy_constraints):
        return AssignmentPlanEnvelope(
            assignment_id=str(assignment["id"]),
            backlog_item_id=str(backlog_item["id"]),
            lane_id=str(assignment.get("lane_id") or ""),
            checkpoints=self._build_checkpoints(backlog_item, strategy_constraints),
            acceptance_criteria=self._build_acceptance_criteria(backlog_item, strategy_constraints),
            sidecar_plan={
                "checklist": self._build_checklist(backlog_item),
                "planning_policy": list(strategy_constraints.get("planning_policy", [])),
            },
        )
```

- [ ] **Step 4: Thread assignment planner output into goal/assignment compilation without changing formal truth**

```python
compiler_context["assignment_plan"] = envelope.model_dump(mode="json")
compiler_context["sidecar_plan"] = envelope.sidecar_plan
payload["assignment_plan"] = envelope.model_dump(mode="json")
```

- [ ] **Step 5: Keep the sidecar boundary explicit**

```python
payload["assignment_plan_truth_source"] = "AssignmentRecord"
payload["assignment_plan_sidecar"] = envelope.sidecar_plan
```

- [ ] **Step 6: Run assignment planning regressions**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_assignment_planner.py tests/kernel/test_assignment_envelope.py tests/app/test_goals_api.py -q
```

Expected:

- PASS

- [ ] **Step 7: Commit**

```powershell
git add src/copaw/compiler/planning/assignment_planner.py src/copaw/goals/service_compiler.py src/copaw/industry/service_lifecycle.py tests/compiler/test_assignment_planner.py tests/kernel/test_assignment_envelope.py tests/app/test_goals_api.py
git commit -m "feat: add assignment-local planner"
```

## Task 5: Build the Report-to-Replan Engine

**Files:**
- Create: `src/copaw/compiler/planning/report_replan_engine.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Test: `tests/compiler/test_report_replan_engine.py`
- Test: `tests/industry/test_report_synthesis.py`
- Test: `tests/industry/test_runtime_views_split.py`

- [ ] **Step 1: Write failing replan engine tests**

```python
from copaw.compiler.planning.report_replan_engine import ReportReplanEngine


def test_replan_engine_escalates_repeated_failures_beyond_local_followup() -> None:
    engine = ReportReplanEngine()
    decision = engine.evaluate(
        reports=[
            {"id": "r1", "result": "failed", "lane_id": "lane-growth"},
            {"id": "r2", "result": "failed", "lane_id": "lane-growth"},
        ],
        strategy_constraints={"review_rules": ["repeat-failure-needs-review"]},
    )
    assert decision.requires_review is True
    assert decision.replan_kind in {"lane-reweight", "cycle-review", "strategy-review"}
```

- [ ] **Step 2: Run tests to verify report closure is still mostly local follow-up**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_report_replan_engine.py tests/industry/test_report_synthesis.py tests/industry/test_runtime_views_split.py -q
```

Expected:

- FAIL because no replan engine exists and runtime views expose no structured replan output

- [ ] **Step 3: Implement the report-to-replan engine**

```python
class ReportReplanEngine:
    def evaluate(self, *, reports, strategy_constraints):
        repeated_failures = self._group_repeated_failures(reports)
        if repeated_failures:
            return ReportReplanDecision(
                requires_review=True,
                replan_kind="cycle-review",
                followup_backlog_items=self._build_followups(repeated_failures),
                strategy_deltas=self._build_strategy_deltas(repeated_failures, strategy_constraints),
            )
        return ReportReplanDecision(requires_review=False)
```

- [ ] **Step 4: Replace ad hoc follow-up-only logic with replan decisions**

```python
decision = self._report_replan_engine.evaluate(
    reports=report_payloads,
    strategy_constraints=strategy_constraints,
)
for item in decision.followup_backlog_items:
    self._backlog_service.record_chat_writeback(...)
cycle = self._apply_replan_decision_to_cycle(cycle, decision)
```

- [ ] **Step 5: Surface the structured replan output in runtime views**

```python
detail["main_brain_planning"]["replan"] = decision.model_dump(mode="json")
detail["main_brain_planning"]["review_required"] = decision.requires_review
```

- [ ] **Step 6: Run replan/runtime view regressions**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_report_replan_engine.py tests/industry/test_report_synthesis.py tests/industry/test_runtime_views_split.py -q
```

Expected:

- PASS

- [ ] **Step 7: Commit**

```powershell
git add src/copaw/compiler/planning/report_replan_engine.py src/copaw/industry/service_lifecycle.py src/copaw/industry/service_runtime_views.py tests/compiler/test_report_replan_engine.py tests/industry/test_report_synthesis.py tests/industry/test_runtime_views_split.py
git commit -m "feat: add report to replan engine"
```

## Task 6: Wire Planner Services and End-to-End Planning Views

**Files:**
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/industry/service_context.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Test: `tests/app/test_runtime_bootstrap_split.py`
- Test: `tests/app/test_phase_next_autonomy_smoke.py`

- [ ] **Step 1: Write failing wiring/view tests**

```python
def test_runtime_domain_services_expose_formal_planner_components() -> None:
    services = build_runtime_domain_services(...)
    assert services.industry_service is not None
    assert getattr(services.industry_service, "_strategy_planning_compiler", None) is not None
    assert getattr(services.industry_service, "_cycle_planner", None) is not None
```

- [ ] **Step 2: Run tests to verify planner services are not wired yet**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/app/test_runtime_bootstrap_split.py tests/app/test_phase_next_autonomy_smoke.py -q
```

Expected:

- FAIL on missing planner bindings or missing planning view fields

- [ ] **Step 3: Instantiate the planner services in domain bootstrap**

```python
strategy_planning_compiler = StrategyPlanningCompiler()
cycle_planner = CyclePlanner()
assignment_planner = AssignmentPlanner()
report_replan_engine = ReportReplanEngine()
```

- [ ] **Step 4: Pass them through `IndustryService` runtime bindings**

```python
industry_runtime_bindings = build_industry_service_runtime_bindings(
    ...,
    strategy_planning_compiler=strategy_planning_compiler,
    cycle_planner=cycle_planner,
    assignment_planner=assignment_planner,
    report_replan_engine=report_replan_engine,
)
```

- [ ] **Step 5: Expose planner outputs in runtime views and smoke surfaces**

```python
main_brain_planning = {
    "strategy_constraints": ...,
    "cycle_decision": ...,
    "assignment_plan": ...,
    "replan": ...,
}
detail["main_brain_planning"] = main_brain_planning
```

- [ ] **Step 6: Run end-to-end planning regressions**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/app/test_runtime_bootstrap_split.py tests/app/test_phase_next_autonomy_smoke.py -q
```

Expected:

- PASS

- [ ] **Step 7: Commit**

```powershell
git add src/copaw/app/runtime_bootstrap_domains.py src/copaw/industry/service_context.py src/copaw/industry/service_runtime_views.py tests/app/test_runtime_bootstrap_split.py tests/app/test_phase_next_autonomy_smoke.py
git commit -m "feat: wire formal planner services"
```

## Task 7: Docs, Status, and Full Regression

**Files:**
- Modify: `docs/superpowers/specs/2026-04-01-formal-planning-capability-gap-design.md`
- Modify: `TASK_STATUS.md`
- Test: `tests/compiler/test_planning_models.py`
- Test: `tests/compiler/test_strategy_compiler.py`
- Test: `tests/compiler/test_cycle_planner.py`
- Test: `tests/compiler/test_assignment_planner.py`
- Test: `tests/compiler/test_report_replan_engine.py`
- Test: `tests/app/test_goals_api.py`
- Test: `tests/app/test_predictions_api.py`
- Test: `tests/app/test_phase_next_autonomy_smoke.py`
- Test: `tests/industry/test_report_synthesis.py`
- Test: `tests/industry/test_runtime_views_split.py`

- [ ] **Step 1: Update the planning gap spec with landed shape**

```markdown
- assignment-local formal planner landed
- cycle planner no longer only picks shallow daily slices
- strategy compiler now compiles lane/review constraints
- report-to-replan engine now emits structured review/replan outputs
```

- [ ] **Step 2: Update `TASK_STATUS.md` with the new planning closure/next phase**

```markdown
- formal planner work now reads as:
  `strategy compiler -> cycle planner -> assignment planner -> report-to-replan`
```

- [ ] **Step 3: Run the full focused regression suite**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_planning_models.py tests/compiler/test_strategy_compiler.py tests/compiler/test_cycle_planner.py tests/compiler/test_assignment_planner.py tests/compiler/test_report_replan_engine.py tests/app/test_goals_api.py tests/app/test_predictions_api.py tests/app/test_phase_next_autonomy_smoke.py tests/industry/test_report_synthesis.py tests/industry/test_runtime_views_split.py tests/app/test_runtime_bootstrap_split.py -q
```

Expected:

- PASS

- [ ] **Step 4: Commit**

```powershell
git add docs/superpowers/specs/2026-04-01-formal-planning-capability-gap-design.md docs/superpowers/plans/2026-04-01-formal-planning-capability-gap-implementation-plan.md TASK_STATUS.md
git commit -m "docs: add formal planning capability gap plan"
```

## Execution Choice

Once this plan is accepted, execute it in this order:

1. `Task 1-2`
   - establish planning contracts and strategy compiler first
2. `Task 3-4`
   - add cycle and assignment planners
3. `Task 5-6`
   - add report-to-replan and runtime visibility
4. `Task 7`
   - doc closure and regression

Do not reorder this into "UI first" or "prediction first".

The formal planner should land from truth/compiler inward to lifecycle/view outward.
