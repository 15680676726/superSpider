# Final Residual Purity Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining industry bridge, reporting/prediction goal residue, workflow historical-link dependency, and stale documentation wording from the live product surface.

**Architecture:** Keep the assignment/backlog/cycle/task/evidence chain as the only live runtime truth. Retain legacy `goal/schedule` objects only as leaf execution artifacts where unavoidable, and stop using them as scope anchors, lifecycle truth, or public workflow semantics.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, Markdown docs

---

### Task 1: Industry Residual Bridge

**Files:**
- Modify: `src/copaw/industry/service_activation.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_cleanup.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `tests/app/industry_api_parts/retirement_chain.py`

- [ ] Write failing tests proving industry status/cleanup no longer need `goal_ids` as their primary scope anchor.
- [ ] Run the targeted industry tests to verify the failure is real.
- [ ] Implement the minimal industry-side scope and cleanup changes.
- [ ] Re-run the targeted industry tests until green.

### Task 2: Reporting And Prediction Goal Residue

**Files:**
- Modify: `src/copaw/state/reporting_service.py`
- Modify: `src/copaw/predictions/service_context.py`
- Test: `tests/app/test_predictions_api.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`

- [ ] Write failing tests proving reporting and prediction stay task-first without goal-derived fallback when task truth exists.
- [ ] Run the targeted tests to verify the failure is real.
- [ ] Implement the minimal reporting/prediction cleanup.
- [ ] Re-run the targeted tests until green.

### Task 3: Workflow Historical Links

**Files:**
- Modify: `src/copaw/workflows/service_runs.py`
- Modify: `src/copaw/workflows/service_preview.py`
- Modify: `src/copaw/workflows/models.py`
- Test: `tests/app/test_workflow_templates_api.py`

- [ ] Write failing tests proving workflow resume/detail no longer require internal goal/schedule link fallback when task/decision/evidence/runtime context exists.
- [ ] Run the targeted workflow tests to verify the failure is real.
- [ ] Implement the minimal workflow cleanup.
- [ ] Re-run the targeted workflow tests until green.

### Task 4: Docs And Verification

**Files:**
- Modify: `46问题文档.md`
- Modify: `TASK_STATUS.md`

- [ ] Update the docs so only the current residuals remain documented.
- [ ] Run the focused verification matrix for industry, reporting/prediction, and workflow.
- [ ] Commit and push the final closure bundle.

## Status Update (`2026-04-07`)

- Completed:
  - reporting / prediction task-first closure
  - workflow internal step-record removal of `linked_goal_ids / linked_schedule_ids`
  - cycle reconcile / prediction case removal of `goal_statuses` sidecar
- Remaining:
  - industry bootstrap still materializes bootstrap goal/schedule before canonical backlog/cycle takes over
  - workflow `step_execution_seed` still accepts legacy goal/schedule ids as compatibility input for older runs
  - `runtime_service_graph.py` / `runtime_bootstrap_models.py` wiring remains heavy and manually assembled
