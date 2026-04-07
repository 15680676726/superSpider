# Industry Bootstrap Hard-Cut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove bootstrap's legacy `goals / schedules` public contract and stop bootstrap from depending on materialized legacy goal/schedule objects as its primary write-path truth.

**Architecture:** Keep industry bootstrap rooted in canonical `draft -> goal specs -> backlog -> cycle -> assignments` truth. Preserve `GoalRecord` and `ScheduleRecord` only as downstream compatibility/runtime artifacts where still required, but stop treating them as bootstrap's primary response objects or bootstrap seed truth.

**Tech Stack:** FastAPI, Pydantic models, Python service layer, pytest integration suites, SQLite repositories.

---

### Task 1: Hard-Cut Bootstrap Response Contract

**Files:**
- Modify: `src/copaw/industry/models.py`
- Modify: `src/copaw/industry/service_activation.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`

- [ ] **Step 1: Write the failing tests**

Add/adjust tests so `/industry/v1/bootstrap` no longer exposes legacy `goals / schedules` response keys and instead returns canonical `draft`, `backlog`, `cycle`, `assignments`, and lightweight schedule/runtime summary fields.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -k "bootstrap_response_hard_cut or persists_draft_truth" -q`
Expected: FAIL because bootstrap still returns legacy `goals / schedules`.

- [ ] **Step 3: Write minimal implementation**

Refactor `IndustryBootstrapResponse` away from `IndustryBootstrapGoalResult` / `IndustryBootstrapScheduleResult` as first-class response fields. Build the bootstrap response from canonical `draft`, persisted backlog items, cycle, assignments, and route summaries.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -k "bootstrap_response_hard_cut or persists_draft_truth" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/copaw/industry/models.py src/copaw/industry/service_activation.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py
git commit -m "runtime: hard-cut bootstrap response contract"
```

### Task 2: Remove Bootstrap Write-Path Dependence on Materialized Goals

**Files:**
- Modify: `src/copaw/industry/service_activation.py`
- Modify: `src/copaw/state/main_brain_service.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/goals/service_core.py` (only if compatibility creation still needs reshaping)
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/industry_api_parts/retirement_chain.py`

- [ ] **Step 1: Write the failing tests**

Add/adjust tests proving bootstrap can fully materialize backlog/cycle/assignment truth and delete/retire correctly without depending on bootstrap response goal ids or pre-materialized goal truth as the bootstrap seed anchor.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/retirement_chain.py -k "bootstrap_hard_cut or delete_retired_instance or runtime_detail_and_goal_detail" -q`
Expected: FAIL because tests still depend on legacy bootstrap goal/schedule response shape and write ordering.

- [ ] **Step 3: Write minimal implementation**

Shift bootstrap internals so canonical goal specs drive backlog/cycle/assignment creation. Keep `GoalRecord` / `GoalOverrideRecord` only as compatibility/detail artifacts after canonical truth is already established, and stop bootstrap response/delete assertions from depending on them as the primary public anchor.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/retirement_chain.py -k "bootstrap_hard_cut or delete_retired_instance or runtime_detail_and_goal_detail" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/copaw/industry/service_activation.py src/copaw/state/main_brain_service.py src/copaw/industry/service_strategy.py src/copaw/goals/service_core.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/retirement_chain.py
git commit -m "runtime: cut bootstrap legacy write path"
```

### Task 3: Sweep Public Consumers and Runtime Assertions

**Files:**
- Modify: `tests/app/industry_api_parts/runtime_updates.py`
- Modify: `tests/app/industry_api_parts/retirement_chain.py`
- Modify: `tests/app/test_runtime_canonical_flow_e2e.py`
- Modify: `tests/app/test_phase_next_autonomy_smoke.py`

- [ ] **Step 1: Write the failing tests**

Adjust the public-consumer suites so bootstrap assertions consume canonical response fields and runtime detail truth instead of `payload["goals"]` / `payload["schedules"]`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/app/industry_api_parts/runtime_updates.py tests/app/industry_api_parts/retirement_chain.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_phase_next_autonomy_smoke.py -k "bootstrap or industry" -q`
Expected: FAIL anywhere the old bootstrap response is still assumed.

- [ ] **Step 3: Write minimal implementation**

Move affected assertions to `draft_payload`, assignment/backlog truth, runtime detail, or instance summary stats as appropriate.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/app/industry_api_parts/runtime_updates.py tests/app/industry_api_parts/retirement_chain.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_phase_next_autonomy_smoke.py -k "bootstrap or industry" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/app/industry_api_parts/runtime_updates.py tests/app/industry_api_parts/retirement_chain.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_phase_next_autonomy_smoke.py
git commit -m "test: move bootstrap assertions to canonical runtime truth"
```

### Task 4: Documentation and Focused Verification

**Files:**
- Modify: `46问题文档.md`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`

- [ ] **Step 1: Update documentation**

Document that bootstrap no longer uses legacy `goals / schedules` as a first-class public contract and that canonical bootstrap truth now lives in `draft_payload + backlog/cycle/assignments`.

- [ ] **Step 2: Run focused verification**

Run:

```bash
python -m pytest tests/state/test_state_store_migration.py::test_sqlite_state_store_initialize_upgrades_legacy_tables_before_schema_indexes tests/state/test_sqlite_repositories.py::test_sqlite_override_repositories_crud_round_trip tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py tests/app/industry_api_parts/retirement_chain.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_phase_next_autonomy_smoke.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add 46问题文档.md TASK_STATUS.md DATA_MODEL_DRAFT.md
git commit -m "docs: record bootstrap hard-cut closure"
```
