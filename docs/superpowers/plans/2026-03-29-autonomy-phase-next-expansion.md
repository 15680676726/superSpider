# Autonomy Phase-Next Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the newly stabilized autonomy core into the next-phase mature runtime by deepening `Full Host Digital Twin`, broadening `single-industry` long-run scenarios, surfacing a true main-brain cockpit, adding heavier smoke coverage, and continuing targeted module decomposition without creating parallel truths.

**Architecture:** Keep every new capability on the same canonical chains that already exist: `host_twin / host_companion_session / workspace_graph` remain derived execution truth; `strategy -> lane -> backlog -> cycle -> assignment -> report -> synthesis/replan` remains the only industry runtime chain; Runtime Center and `/industry` become first-class cockpit/read surfaces over those objects instead of inventing separate UI-only state. Heavy-file splits must extract focused readers/presenters/helpers rather than moving truth into a second service layer.

**Tech Stack:** Python, FastAPI service layer, Pydantic models, React, TypeScript, Ant Design, pytest, vitest

---

## File Map

- Modify: `src/copaw/environments/health_service.py`
  - deepen canonical host truth for companion-session continuity, multi-seat coordination summaries, and app-family execution readiness
- Modify: `src/copaw/app/runtime_center/state_query.py`
  - pass richer host truth and cockpit summaries into runtime detail/read surfaces
- Modify: `src/copaw/app/runtime_center/task_review_projection.py`
  - expose richer host-companion / coordination / app-family diagnostics in task review payloads
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
  - add a main-brain cockpit overview card and richer host/governance summary meta
- Modify: `src/copaw/workflows/service_preview.py`
  - consume richer host/companion/multi-seat truth during preview preflight
- Modify: `src/copaw/workflows/service_runs.py`
  - persist richer host companion / seat coordination snapshots into run + schedule resume truth
- Modify: `src/copaw/sop_kernel/service.py`
  - deepen fixed-SOP host preflight consumption from canonical host truth
- Modify: `src/copaw/industry/service_runtime_views.py`
  - prefer live focus/report-followup/runtime cockpit objects and package richer cockpit payloads
- Modify: `src/copaw/industry/service_lifecycle.py`
  - complete long-run staffing + handoff + human-assist + report/replan continuity behaviors
- Modify: `src/copaw/kernel/governance.py`
  - keep admission/governance summaries aligned with the deeper host/industry long-run truth
- Create/Modify: `tests/environments/test_environment_registry.py`
- Create/Modify: `tests/app/runtime_center_api_parts/detail_environment.py`
- Create/Modify: `tests/app/runtime_center_api_parts/overview_governance.py`
- Create/Modify: `tests/app/test_runtime_projection_contracts.py`
- Create/Modify: `tests/app/test_workflow_templates_api.py`
- Create/Modify: `tests/fixed_sops/test_service.py`
- Create/Modify: `tests/app/test_fixed_sop_kernel_api.py`
- Create/Modify: `tests/app/industry_api_parts/runtime_updates.py`
- Create/Modify: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Create/Modify: `tests/app/industry_api_parts/retirement_chain.py`
- Create: `tests/app/test_phase_next_autonomy_smoke.py`
  - lock a heavier cross-chain smoke over host truth, industry runtime, governance, and cockpit read surfaces
- Create/Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Create/Modify: `console/src/pages/Industry/IndustryRuntimeCockpitPanel.tsx`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/runtimeEnvironmentSections.tsx`
- Modify: `console/src/pages/RuntimeCenter/runtimeIndustrySections.tsx`
- Create/Modify: `console/src/pages/RuntimeCenter/index.test.tsx`
- Create/Modify: `console/src/pages/Industry/index.test.tsx`
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `DATA_MODEL_DRAFT.md`

## Recommended Execution Order

1. Deepen canonical host truth and its workflow/fixed-SOP consumers.
2. Broaden single-industry long-run continuity around staffing/handoff/human-assist/report follow-up.
3. Surface the main-brain cockpit in Runtime Center and `/industry`, extracting focused UI sections while doing so.
4. Add heavier autonomy smoke/regression coverage across the expanded runtime chain.
5. Update architecture/status docs only after code and tests are green.

## Task 1: Full Host Digital Twin Phase-Next

**Files:**
- Modify: `src/copaw/environments/health_service.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/task_review_projection.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `src/copaw/workflows/service_preview.py`
- Modify: `src/copaw/workflows/service_runs.py`
- Modify: `src/copaw/sop_kernel/service.py`
- Test: `tests/environments/test_environment_registry.py`
- Test: `tests/app/runtime_center_api_parts/detail_environment.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`
- Test: `tests/app/test_runtime_projection_contracts.py`
- Test: `tests/app/test_workflow_templates_api.py`
- Test: `tests/fixed_sops/test_service.py`
- Test: `tests/app/test_fixed_sop_kernel_api.py`

- [ ] **Step 1: Write/extend failing tests for host companion and multi-seat truth**
- [ ] **Step 2: Run focused host/workflow/fixed-SOP suites and watch them fail**
- [ ] **Step 3: Implement the minimal canonical-host truth expansion**
- [ ] **Step 4: Re-run focused suites until green**

## Task 2: Single-Industry Long-Run Expansion

**Files:**
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/kernel/governance.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/industry_api_parts/retirement_chain.py`

- [ ] **Step 1: Write/extend failing long-run combination tests**
- [ ] **Step 2: Run focused industry suites and verify red**
- [ ] **Step 3: Implement minimal lifecycle/runtime-focus/governance changes**
- [ ] **Step 4: Re-run focused industry suites until green**

## Task 3: Main-Brain Cockpit Surface + Frontend Decomposition

**Files:**
- Create: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Create: `console/src/pages/Industry/IndustryRuntimeCockpitPanel.tsx`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/runtimeEnvironmentSections.tsx`
- Modify: `console/src/pages/RuntimeCenter/runtimeIndustrySections.tsx`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Test: `console/src/pages/RuntimeCenter/index.test.tsx`
- Test: `console/src/pages/Industry/index.test.tsx`

- [ ] **Step 1: Add failing UI/read-surface tests for cockpit summaries**
- [ ] **Step 2: Run focused vitest suites and verify red**
- [ ] **Step 3: Implement cockpit sections while extracting them out of heavy page files**
- [ ] **Step 4: Re-run focused vitest and `tsc` until green**

## Task 4: Wider Smoke And Regression Expansion

**Files:**
- Create: `tests/app/test_phase_next_autonomy_smoke.py`
- Modify: `tests/app/runtime_center_api_parts/detail_environment.py`
- Modify: `tests/app/runtime_center_api_parts/overview_governance.py`
- Modify: `tests/app/industry_api_parts/retirement_chain.py`

- [ ] **Step 1: Add failing cross-chain smoke tests**
- [ ] **Step 2: Run the new smoke file and confirm the initial red/coverage gap**
- [ ] **Step 3: Adjust only the minimum supporting code/fixtures required**
- [ ] **Step 4: Run the new smoke file plus the widened regression group**

## Task 5: Docs And Status Sync

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `DATA_MODEL_DRAFT.md`

- [ ] **Step 1: Record the upgraded host-twin, industry, cockpit, smoke, and decomposition truth**
- [ ] **Step 2: Re-run the final verification commands**
- [ ] **Step 3: Update docs to match only verified reality**
