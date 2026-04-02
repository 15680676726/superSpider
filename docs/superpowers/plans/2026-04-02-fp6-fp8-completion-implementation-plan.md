# FP-6 FP-7 FP-8 Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fully deliver the remaining formal-planning backlog by landing a typed strategic uncertainty register, a typed strategy-change trigger engine, and a multi-cycle lane budget compiler on the existing `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan` truth chain.

**Architecture:** Keep strategy truth on `StrategyMemoryRecord`, compile it through the dedicated `compiler/planning` slice, and push the resulting typed uncertainty, budget, and trigger outputs through cycle materialization, report/replan, prediction overlap, goal compiler context, and runtime read models. Borrow only CC shell discipline and bounded planning artifacts; do not introduce a second planner truth source, prompt-only planner state, or duplicate shallow follow-up branches.

**Tech Stack:** Python 3.11, Pydantic, SQLite, pytest, existing CoPaw `state / compiler / industry / goals / predictions / runtime-center` services.

---

## Scope Guard

This plan completes exactly three bounded backlog items:

- `FP-6 Strategic Uncertainty Register`
- `FP-7 Strategy-Change Trigger Engine`
- `FP-8 Multi-Cycle Lane Budget Compiler`

This plan does not:

- reopen runtime-tail stages that are already closed
- replace CoPaw's planning truth chain with Claude-style session planning
- hide new work inside `metadata`-only prompt scratch when the object should be typed
- keep the old shallow "always create follow-up backlog" path once a richer trigger decision replaces it

## Ownership Map

Exactly one writer owns each file set during parallel work.

### Agent 1: Strategy Truth + Compiler Contract

**Files:**
- Modify: `src/copaw/state/models_reporting.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/repositories/sqlite_strategy.py`
- Modify: `src/copaw/compiler/planning/models.py`
- Modify: `src/copaw/compiler/planning/strategy_compiler.py`
- Test: `tests/compiler/test_planning_models.py`
- Test: `tests/compiler/test_strategy_compiler.py`
- Test: `tests/state/test_strategy_memory_service.py`

**Deliverable:**

- typed persisted strategic uncertainty register on `StrategyMemoryRecord`
- typed persisted multi-cycle lane budget entries on `StrategyMemoryRecord`
- compiled `PlanningStrategyConstraints` that carry uncertainty, lane-budget, and trigger-rule inputs without creating a second truth source

### Agent 2: Cycle Planner Budget Consumption

**Files:**
- Modify: `src/copaw/compiler/planning/cycle_planner.py`
- Test: `tests/compiler/test_cycle_planner.py`

**Deliverable:**

- cycle selection consumes typed lane-budget outputs
- planner can suppress, defer, and force-include lanes/items based on budget pressure and uncertainty review pressure
- old pure local lane-weight sort is deleted where replaced

### Agent 3: Report Replan Trigger Engine

**Files:**
- Modify: `src/copaw/compiler/planning/report_replan_engine.py`
- Test: `tests/compiler/test_report_replan_engine.py`
- Test: `tests/industry/test_report_synthesis.py`

**Deliverable:**

- `ReportReplanEngine` emits typed decision kinds:
  - `follow_up_backlog`
  - `cycle_rebalance`
  - `lane_reweight`
  - `strategy_review_required`
- repeated blocker / miss / contradiction / confidence-collapse paths are covered
- replaced shallow default branches are removed

### Agent 4: Runtime Integration + Read Surfaces

**Files:**
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `src/copaw/goals/service_compiler.py`
- Modify: `src/copaw/predictions/service_core.py`
- Modify: `src/copaw/industry/models.py`
- Test: `tests/app/test_predictions_api.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `tests/app/test_phase_next_autonomy_smoke.py`

**Deliverable:**

- strategy uncertainty, lane budgets, and trigger decisions persist in formal-planning sidecars
- goal compiler / prediction overlap / runtime read models expose the same typed outputs
- no duplicate shallow planning snapshot path remains once the typed sidecar path is available

## Task 1: Extend Strategy Truth for FP-6 and FP-8

**Files:**
- Modify: `src/copaw/state/models_reporting.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/repositories/sqlite_strategy.py`
- Modify: `src/copaw/compiler/planning/models.py`
- Test: `tests/compiler/test_planning_models.py`
- Test: `tests/state/test_strategy_memory_service.py`

- [ ] **Step 1: Write failing tests for typed uncertainty and lane-budget truth**

```python
def test_strategy_memory_record_accepts_uncertainty_register_and_lane_budgets() -> None:
    record = StrategyMemoryRecord(
        strategy_id="strategy-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Northwind strategy",
        strategic_uncertainties=[
            {
                "uncertainty_id": "uncertainty:weekend-variance",
                "statement": "Weekend variance root cause is still uncertain.",
                "scope": "lane",
                "impact_level": "high",
                "current_confidence": 0.35,
                "review_by_cycle": "next-cycle",
                "escalate_when": ["confidence-drop", "target-miss"],
            }
        ],
        lane_budgets=[
            {
                "lane_id": "lane-growth",
                "budget_window": "next-3-cycles",
                "target_share": 0.5,
                "min_share": 0.25,
                "max_share": 0.75,
            }
        ],
    )
    assert record.strategic_uncertainties[0].uncertainty_id == "uncertainty:weekend-variance"
    assert record.lane_budgets[0].lane_id == "lane-growth"
```

- [ ] **Step 2: Run the focused tests and verify they fail for the missing typed fields**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_planning_models.py tests/state/test_strategy_memory_service.py -q
```

Expected:

- FAIL because the new typed fields and persistence path do not exist yet

- [ ] **Step 3: Add typed state models and persistence columns**

Implementation notes:

- add dedicated typed models for uncertainty register entries and lane-budget entries on `StrategyMemoryRecord`
- persist them as first-class JSON columns on `strategy_memories`
- keep `metadata` for residual context only; do not hide formal truth there

- [ ] **Step 4: Extend planning models to carry the new compiler inputs**

Implementation notes:

- add typed planning-side representations for uncertainty register, lane budget, and trigger evaluation hints
- keep these inside `PlanningStrategyConstraints`, not as a second top-level planner truth object

- [ ] **Step 5: Re-run the focused tests and verify they pass**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_planning_models.py tests/state/test_strategy_memory_service.py -q
```

Expected:

- PASS with typed strategy truth surviving model validation and SQLite persistence

## Task 2: Compile FP-6 and FP-8 Through the Strategy Compiler

**Files:**
- Modify: `src/copaw/compiler/planning/strategy_compiler.py`
- Test: `tests/compiler/test_strategy_compiler.py`

- [ ] **Step 1: Write failing compiler tests for uncertainties, budgets, and trigger hints**

```python
def test_strategy_compiler_emits_uncertainties_lane_budgets_and_trigger_hints() -> None:
    compiler = StrategyPlanningCompiler()
    strategy = StrategyMemoryRecord(
        strategy_id="strategy-1",
        scope_type="industry",
        scope_id="industry-1",
        title="Northwind strategy",
        strategic_uncertainties=[...],
        lane_budgets=[...],
        review_rules=["repeat-failure-needs-review"],
    )
    constraints = compiler.compile(strategy)
    assert constraints.strategic_uncertainties[0].uncertainty_id == "uncertainty:weekend-variance"
    assert constraints.lane_budgets[0].lane_id == "lane-growth"
    assert "repeat-failure-needs-review" in constraints.strategy_trigger_rules
```

- [ ] **Step 2: Run the strategy compiler tests and verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_strategy_compiler.py -q
```

Expected:

- FAIL on missing compiled fields

- [ ] **Step 3: Implement strategy compilation**

Implementation notes:

- preserve current field behavior
- compile typed uncertainty and lane-budget outputs
- derive stable trigger-rule hints from existing review rules plus typed uncertainty escalation settings
- keep compiler pure; no repository writes

- [ ] **Step 4: Re-run the strategy compiler tests and verify they pass**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_strategy_compiler.py -q
```

Expected:

- PASS with explicit compiled outputs

## Task 3: Make the Cycle Planner Consume Lane Budgets

**Files:**
- Modify: `src/copaw/compiler/planning/cycle_planner.py`
- Test: `tests/compiler/test_cycle_planner.py`

- [ ] **Step 1: Write failing tests for suppress / defer / force-include lane behavior**

```python
def test_cycle_planner_defer_and_force_include_follow_budget_constraints() -> None:
    constraints = PlanningStrategyConstraints(
        lane_budgets=[
            {
                "lane_id": "lane-growth",
                "budget_window": "next-3-cycles",
                "target_share": 0.2,
                "min_share": 0.0,
                "max_share": 0.25,
                "defer_reason": "budget-capped",
            },
            {
                "lane_id": "lane-ops",
                "budget_window": "next-3-cycles",
                "target_share": 0.5,
                "min_share": 0.4,
                "max_share": 0.75,
                "force_include_reason": "customer-issue-lane-underfunded",
            },
        ],
    )
```

- [ ] **Step 2: Run the cycle planner tests and verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_cycle_planner.py -q
```

Expected:

- FAIL on missing budget-aware planner behavior

- [ ] **Step 3: Implement multi-cycle lane-budget consumption**

Implementation notes:

- use typed lane budgets as a hard constraint during candidate selection
- preserve follow-up pressure and paused-lane semantics where still valid
- emit selected/deferred lane rationale in decision metadata
- remove replaced pure lane-weight-only ranking branches

- [ ] **Step 4: Re-run the cycle planner tests and verify they pass**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_cycle_planner.py -q
```

Expected:

- PASS with defer/suppress/force-include behavior visible on the decision surface

## Task 4: Deliver the FP-7 Strategy-Change Trigger Engine

**Files:**
- Modify: `src/copaw/compiler/planning/report_replan_engine.py`
- Test: `tests/compiler/test_report_replan_engine.py`
- Test: `tests/industry/test_report_synthesis.py`

- [ ] **Step 1: Write failing tests for each required decision kind**

```python
def test_report_replan_engine_emits_lane_reweight_on_repeated_lane_miss() -> None:
    decision = ReportReplanEngine().compile({...})
    assert decision.decision_kind == "lane_reweight"
```

- [ ] **Step 2: Run the report/replan tests and verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_report_replan_engine.py tests/industry/test_report_synthesis.py -q
```

Expected:

- FAIL because the current engine only emits `clear` or `needs-replan`

- [ ] **Step 3: Implement the trigger engine**

Implementation notes:

- keep `status` for backward-compatible read surfaces where still needed
- add typed `decision_kind`, trigger-family evidence, uncertainty-confidence updates, and rationale
- support:
  - repeated blocker across cycles
  - repeated assignment miss against the same lane objective
  - confidence collapse on tracked uncertainty
  - repeated contradiction across synthesis / activation / evidence
- delete replaced "always follow-up backlog" shallow defaults

- [ ] **Step 4: Re-run the report/replan tests and verify they pass**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_report_replan_engine.py tests/industry/test_report_synthesis.py -q
```

Expected:

- PASS with each decision kind emitted by an explicit evidence pattern

## Task 5: Wire FP-6 FP-7 FP-8 Into Lifecycle, Predictions, Goals, and Runtime Views

**Files:**
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `src/copaw/goals/service_compiler.py`
- Modify: `src/copaw/predictions/service_core.py`
- Modify: `src/copaw/industry/models.py`
- Test: `tests/app/test_predictions_api.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `tests/app/test_phase_next_autonomy_smoke.py`

- [ ] **Step 1: Write failing integration tests**

Required assertions:

- runtime planning surface exposes `strategic_uncertainties`
- runtime planning surface exposes typed `lane_budgets`
- runtime/prediction/detail surfaces expose `decision_kind`
- prediction overlap summary keeps the same typed trigger output
- phase-next smoke proves uncertainty survives `strategy -> cycle -> assignment -> report -> replan`

- [ ] **Step 2: Run the focused integration tests and verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/app/test_predictions_api.py tests/app/industry_api_parts/runtime_updates.py tests/app/test_phase_next_autonomy_smoke.py -q
```

Expected:

- FAIL because the typed outputs are not yet wired through

- [ ] **Step 3: Implement lifecycle and read-surface wiring**

Implementation notes:

- `IndustryService` must persist the new planning sidecars on cycle/assignment materialization
- report synthesis decoration must preserve typed trigger decisions
- prediction planning snapshot must expose the same typed replan output, not a lossy summary only
- goal compiler context should surface uncertainty/budget inputs when they affect assignment planning
- runtime read surfaces should show typed uncertainty/budget/trigger state without creating a second read model path

- [ ] **Step 4: Delete replaced shallow or duplicate branches**

Deletion targets:

- old fallback branches that assume replan means only `follow-up backlog`
- duplicate summary-only paths that discard typed decision fields once the typed sidecar exists

- [ ] **Step 5: Re-run the focused integration tests and verify they pass**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/app/test_predictions_api.py tests/app/industry_api_parts/runtime_updates.py tests/app/test_phase_next_autonomy_smoke.py -q
```

Expected:

- PASS with one consistent typed planning surface across lifecycle, prediction, and runtime detail

## Task 6: Docs and Status Closeout

**Files:**
- Modify: `docs/superpowers/specs/2026-04-01-formal-planning-capability-gap-design.md`
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`

- [ ] **Step 1: Update the design/status docs only after code is green**
- [ ] **Step 2: Remove language that leaves `FP-6 -> FP-8` as active tails**
- [ ] **Step 3: Record the delivered typed objects, trigger decisions, and budget compiler outputs**

## Verification Matrix

Run in order, stopping on failure:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_planning_models.py tests/compiler/test_strategy_compiler.py tests/compiler/test_cycle_planner.py tests/compiler/test_report_replan_engine.py tests/state/test_strategy_memory_service.py -q
python -m pytest tests/industry/test_report_synthesis.py tests/app/test_predictions_api.py tests/app/industry_api_parts/runtime_updates.py tests/app/test_phase_next_autonomy_smoke.py -q
python -m pytest tests/app/test_goals_api.py tests/industry/test_runtime_views_split.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_canonical_flow_e2e.py -q
git diff --check
```

Expected final state:

- all focused formal-planning and integration suites green
- no duplicate shallow planning branch left for `FP-6 -> FP-8`
- docs updated to mark the bounded backlog delivered
