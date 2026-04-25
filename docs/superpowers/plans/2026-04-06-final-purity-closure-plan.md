# Final Purity Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hard-cut the remaining non-pure seams so runtime truth, workflow linkage, reporting/prediction semantics, and product wording all align with the formal main-brain chain.

**Architecture:** Execute the cleanup from write path inward. First remove live industry reliance on legacy `goal/schedule` bridges, then downgrade workflow `linked_goal_ids/linked_schedule_ids` from active semantics, then remove reporting/prediction reliance on goal-id sets as primary analysis truth, and finally align docs/frontend wording to the canonical vocabulary. Each wave owns a disjoint primary write set and ends with focused regression.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite repositories, pytest, React/Vitest, Markdown docs

**Status:** Completed on `2026-04-06` and extended on `2026-04-07`.
- Industry runtime status/strategy truth now prefers live assignment/backlog/cycle state over legacy goal titles or blocked bootstrap goals.
- Industry bootstrap `auto_dispatch` now materializes governed assignment tasks instead of invoking legacy goal dispatch during activation.
- Workflow read-side no longer collapses to legacy `linked_goal_ids` for step drill-down; persisted task linkage can sustain step detail/status even after goal-link removal.
- Workflow resume now preserves canonical runtime context: deterministic schedule identity is derived without rehydrating persisted legacy schedule links, and legacy goal links are only recreated when no task context exists.
- Reporting/prediction scope now prioritizes canonical `industry_instance_id / task_ids / strategy focus` truth over top-level `goal_ids` collections.
- Product/docs wording updated so the default narrative no longer describes the runtime as `goal-first`.

---

### Task 1: Industry Legacy Bridge Hard Cut

**Files:**
- Modify: `src/copaw/industry/service_activation.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/industry/service_cleanup.py`
- Modify: `src/copaw/state/main_brain_service.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `tests/app/industry_api_parts/retirement_chain.py`
- Test: `tests/app/test_industry_service_wiring.py`

- [x] **Step 1: Write the failing tests**

Add or tighten tests asserting:
- instance status/detail no longer require `_resolve_instance_goal_ids(record)` to derive live operation truth
- strategy sync no longer derives priority/current truth from legacy goal titles
- delete/archive flows keep cleanup coverage without instance-level legacy goal/schedule bridge assumptions

- [x] **Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py tests/app/industry_api_parts/retirement_chain.py tests/app/test_industry_service_wiring.py -q
```

- [x] **Step 3: Write the minimal implementation**

Remove live-status, kickoff, strategy, and cleanup dependence on legacy instance goal/schedule bridge reads where assignment/backlog/cycle/report truth already exists.

- [x] **Step 4: Run tests to verify they pass**

Run the same focused matrix and confirm green.

- [x] **Step 5: Commit**

```bash
git add src/copaw/industry/service_activation.py src/copaw/industry/service_lifecycle.py src/copaw/industry/service_strategy.py src/copaw/industry/service_cleanup.py src/copaw/state/main_brain_service.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py tests/app/industry_api_parts/retirement_chain.py tests/app/test_industry_service_wiring.py
git commit -m "runtime: cut industry legacy bridge"
```

### Task 2: Workflow Historical Link Demotion

**Files:**
- Modify: `src/copaw/workflows/models.py`
- Modify: `src/copaw/workflows/service_runs.py`
- Modify: `src/copaw/workflows/service_preview.py`
- Modify: `src/copaw/workflows/service_context.py`
- Test: `tests/app/test_workflow_templates_api.py`

- [x] **Step 1: Write the failing tests**

Add tests asserting workflow preview/run/resume still show drill-down context without treating `linked_goal_ids/linked_schedule_ids` as active main-chain truth.

- [x] **Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/app/test_workflow_templates_api.py -q
```

- [x] **Step 3: Write the minimal implementation**

Replace active reliance on linked goal/schedule ids with canonical owner/industry/work-context and runtime-derived linkage, keeping historical references only where needed for audit drill-down.

- [x] **Step 4: Run tests to verify they pass**

Run the same focused workflow matrix and confirm green.

- [x] **Step 5: Commit**

```bash
git add src/copaw/workflows/models.py src/copaw/workflows/service_runs.py src/copaw/workflows/service_preview.py src/copaw/workflows/service_context.py tests/app/test_workflow_templates_api.py
git commit -m "runtime: demote workflow historical goal schedule links"
```

### Task 3: Reporting And Prediction Goal-Semantics Cleanup

**Files:**
- Modify: `src/copaw/state/reporting_service.py`
- Modify: `src/copaw/predictions/service_context.py`
- Modify: `src/copaw/predictions/service_core.py`
- Modify: `src/copaw/predictions/service_recommendations.py`
- Test: `tests/app/test_predictions_api.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`

- [x] **Step 1: Write the failing tests**

Add tests asserting report/prediction scope uses canonical industry/owner/lane/cycle/assignment/report truth first, not top-level `goal_ids` collections as primary anchors.

- [x] **Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/app/test_predictions_api.py tests/app/runtime_center_api_parts/overview_governance.py -q
```

- [x] **Step 3: Write the minimal implementation**

Move prediction/report scope building to canonical runtime truth and keep legacy goal references only as secondary derived evidence where still required.

- [x] **Step 4: Run tests to verify they pass**

Run the same focused reporting/prediction matrix and confirm green.

- [x] **Step 5: Commit**

```bash
git add src/copaw/state/reporting_service.py src/copaw/predictions/service_context.py src/copaw/predictions/service_core.py src/copaw/predictions/service_recommendations.py tests/app/test_predictions_api.py tests/app/runtime_center_api_parts/overview_governance.py
git commit -m "runtime: remove reporting prediction goal truth residue"
```

### Task 4: Documentation And Product Vocabulary Alignment

**Files:**
- Modify: `README.md`
- Modify: `TASK_STATUS.md`
- Modify: `docs/archive/root-legacy/46问题文档.md`
- Modify: `docs/superpowers/plans/2026-04-06-closure-remediation-plan.md`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Modify: any directly impacted frontend copy/tests discovered during implementation

- [x] **Step 1: Write the failing tests**

Add or tighten copy/contract tests where product wording still reinforces retired goal-first mental models on runtime surfaces.

- [x] **Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_runtime_canonical_flow_e2e.py -q
cmd /c npm --prefix console run test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts
```

- [x] **Step 3: Write the minimal implementation**

Update docs and frontend wording so the default narrative matches the canonical main-brain chain and current truth of the codebase.

- [x] **Step 4: Run tests to verify they pass**

Run the same doc/product focused matrix plus any touched frontend tests.

- [x] **Step 5: Commit**

```bash
git add README.md TASK_STATUS.md docs/archive/root-legacy/46问题文档.md docs/superpowers/plans/2026-04-06-closure-remediation-plan.md console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts
git commit -m "docs: align runtime vocabulary with canonical main brain chain"
```
