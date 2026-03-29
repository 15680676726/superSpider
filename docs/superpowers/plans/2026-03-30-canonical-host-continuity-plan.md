# Host Continuity Canonicalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task in the current session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert workflow preview, fixed-SOP, and cron execution to rely on the canonical `host_twin_summary` readiness semantics (`ready`/`guarded`/`blocked`) instead of the legacy continuity status enum while keeping everyone synchronized.

**Architecture:** Derive a shared helper inside `task_review_projection.py` that classifies the existing summary data as a single `continuity_state` and expose it alongside `build_host_twin_summary`. Update each consumer to reuse that helper via the summary payload produced by the environment service so they all measure the same canonical host truth.

**Tech Stack:** Python 3.11, Pytest, Pydantic models, SQL state persistence, HTTP API tests.

---

### Task 1: Enrich the canonical host summary with `continuity_state`

**Files:**
- Modify: `src/copaw/app/runtime_center/task_review_projection.py`

- [ ] **Step 1: Add a test fixture (maybe in this file or an existing test module) to fail when `build_host_twin_summary` lacks continuity_state.**
  
  ```python
  def test_build_host_twin_summary_includes_continuity_state():
      summary = build_host_twin_summary(fake_host_twin)
      assert summary["continuity_state"] in {"ready", "guarded", "blocked"}
  ```

- [ ] **Step 2: Run targeted tests to see the new assertion fail.**

  Run: `python -m pytest tests/app/test_runtime_projection_contracts.py -k continuity_state -q`
  Expected: FAIL (since helper/field not yet implemented).

- [ ] **Step 3: Implement `derive_host_continuity_state` helper and set `continuity_state` inside `build_host_twin_summary`.**

  ```python
  def derive_host_continuity_state(summary: dict[str, Any]) -> str:
      ...
  ```

  and update `build_host_twin_summary` to validate input, compute the state (using blocked surface counts, recommended_scheduler_action, legal recovery path, contention severity), and store it under `"continuity_state"`.

- [ ] **Step 4: Run the same pytest module to confirm the new test passes.**

  Run: `python -m pytest tests/app/test_runtime_projection_contracts.py -k continuity_state -q`
  Expected: PASS

- [ ] **Step 5: Commit**

  ```bash
  git add src/copaw/app/runtime_center/task_review_projection.py tests/app/test_runtime_projection_contracts.py
  git commit -m "feat: add host continuity state helper"
  ```

### Task 2: Make workflow preview rely on the shared continuity state

**Files:**
- Modify: `src/copaw/workflows/service_preview.py`
- Modify: `tests/app/test_workflow_templates_api.py`

- [ ] **Step 1: Update the workflow preview tests to assert new `continuity_state` values rather than old continuity_status enumerations.**

  Update fixtures to expect `"continuity_state": "ready"` when summary recommends proceed, etc., and fail when old continuity_status is missing.

- [ ] **Step 2: Run the workflow template tests to confirm they fail under the old logic.**

  Run: `python -m pytest tests/app/test_workflow_templates_api.py::test_workflow_preview_prefers_canonical_host_twin_summary_over_stale_handoff_metadata -q`
  Expected: FAIL because the code still checks `host_twin.continuity.status`.

- [ ] **Step 3: Refactor `_build_host_twin_launch_blockers` and `_canonical_host_summary_ready` to use `host_twin_summary["continuity_state"]` (and the shared helper logic) instead of `host_twin.continuity.status` / `_HOST_TWIN_VALID_CONTINUITY_STATUSES`.**

  Remove `_HOST_TWIN_VALID_CONTINUITY_STATUSES`, `_HOST_TWIN_HANDOFF_ONLY_STATES` if they become redundant. Ensure launch blockers refer to the canonical readiness string and rely on `recommended_scheduler_action`, `legal_recovery_mode`, and `blocked_surface_count` from the summary.

- [ ] **Step 4: Run the same targeted pytest selection to confirm it passes.**

  Run: `python -m pytest tests/app/test_workflow_templates_api.py::test_workflow_preview_prefers_canonical_host_twin_summary_over_stale_handoff_metadata -q`
  Expected: PASS

- [ ] **Step 5: Commit changes**

  ```bash
  git add src/copaw/workflows/service_preview.py tests/app/test_workflow_templates_api.py
  git commit -m "fix: align workflow preview with continuity_state"
  ```

### Task 3: Align FixedSopService to the canonical host truth

**Files:**
- Modify: `src/copaw/sop_kernel/service.py`
- Modify: `tests/fixed_sops/test_service.py`
- Modify: `tests/app/test_fixed_sop_kernel_api.py`

- [ ] **Step 1: Adjust tests to assert `host_preflight["host_twin_summary"]["continuity_state"]` and rely on the helper for every scenario (ready vs blocked).**

  Add a failing assertion or scenario expecting the states to change when the recommended scheduler action switches from handoff to continue.

- [ ] **Step 2: Run the targeted fixed SOP tests to confirm failure.**

  Run:
  `python -m pytest tests/fixed_sops/test_service.py::test_fixed_sop_service_blocks_mutating_run_when_host_preflight_requires_handoff -q`
  Expected: FAIL since code still trusts `continuity` dict.

- [ ] **Step 3: Update `_resolve_host_preflight` to rely on the enriched summary (reusing `derive_host_continuity_state` if necessary) and update `_evaluate_host_preflight` to interpret `continuity_state` instead of the legacy continuity dict.**

  Also ensure metadata saved to runs/evidence contains the updated summary.

- [ ] **Step 4: Re-run the same fixed SOP + kernel API tests (including relevant regression combinations) to confirm they pass.**

  Run:
  `python -m pytest tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py -q`
  Expected: PASS

- [ ] **Step 5: Commit**

  ```bash
  git add src/copaw/sop_kernel/service.py tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py
  git commit -m "fix: align fixed SOP host preflight with continuity_state"
  ```

### Task 4: Update cron executor metadata to carry canonical host summary

**Files:**
- Modify: `src/copaw/app/crons/executor.py`
- Modify: `tests/app/test_cron_executor.py`

- [ ] **Step 1: Extend cron executor tests to assert the new `host_snapshot["host_twin_summary"]["continuity_state"]` passes through the meta payload.**

  Expect that when a `host_snapshot` exists in `job.meta`, the `continuity_state` is retained and simplified.

- [ ] **Step 2: Run the cron executor tests to capture the failure.**

  Run: `python -m pytest tests/app/test_cron_executor.py -q`
  Expected: FAIL because metadata still depends on `continuity_status`.

- [ ] **Step 3: Update `_host_meta` to seed `host_snapshot` (with canonical summary) and ensure `host_requirement` or future gating logic can read `"continuity_state"` if needed.**

- [ ] **Step 4: Re-run the cron executor tests to confirm success.**

  Run: `python -m pytest tests/app/test_cron_executor.py -q`
  Expected: PASS

- [ ] **Step 5: Commit**

  ```bash
  git add src/copaw/app/crons/executor.py tests/app/test_cron_executor.py
  git commit -m "fix: propagate canonical host summary in cron meta"
  ```

### Task 5: Final regression sweep

**Files:**
- Mention all changed files as part of regression testing

- [ ] **Step 1: Run the combined regression suite covering all touched areas.**

  Run: `python -m pytest tests/app/test_workflow_templates_api.py tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py tests/app/test_cron_executor.py -q`
  Expected: PASS

- [ ] **Step 2: Run linters / formatting if required (not specified).**

- [ ] **Step 3: Commit combined regression evidence / update changelog doc if needed.**
