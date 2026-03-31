# Heavy Module Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the remaining main-chain module debt by splitting the heaviest still-central files into smaller, responsibility-focused modules without changing runtime truth or behavior.

**Architecture:** This is a split wave, not a redesign. Each extraction must preserve the existing canonical state/runtime contracts and only move code into clearer landing zones. The first wave should target the highest-weight, highest-coupling files on the current main chain while keeping write ownership disjoint.

**Tech Stack:** Python, FastAPI, pytest, React, TypeScript, Vitest

---

## Scope Boundary

- This plan is only for `重模块拆分`.
- It must not start new product surfaces or policy changes.
- The target is one practical split wave on the remaining heaviest files, not a perfect final architecture for every module.

## Target Split Wave

1. `src/copaw/industry/service_lifecycle.py`
   - Extract report/synthesis/follow-up closure helpers into a dedicated closure module.
2. `src/copaw/kernel/query_execution_runtime.py`
   - Extract resident-agent lifecycle / lease / usage subflows into dedicated helpers.
3. `src/copaw/app/runtime_center/overview_cards.py`
   - Extract main-brain card and cognition payload assembly into its own module.
4. `console/src/pages/Chat/index.tsx`
   - Extract remaining page-shell presentation/state glue that still bloats the page component.
5. `console/src/pages/Industry/index.tsx` + `console/src/pages/RuntimeCenter/runtimeIndustrySections.tsx`
   - Extract remaining report/planning/cognition presentation blocks into narrower helpers.

## File Map

- Create: `src/copaw/industry/service_report_closure.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`

- Create: `src/copaw/kernel/query_execution_resident_runtime.py`
- Create: `src/copaw/kernel/query_execution_usage_runtime.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `tests/app/test_runtime_bootstrap_split.py`

- Create: `src/copaw/app/runtime_center/overview_main_brain.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`

- Create: `console/src/pages/Chat/pagePresentation.tsx`
- Modify: `console/src/pages/Chat/index.tsx`
- Test: `console/src/pages/Chat/*.test.ts*` as needed

- Create: `console/src/pages/Industry/runtimePresentation.tsx`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/runtimeIndustrySections.tsx`
- Test: Industry / RuntimeCenter frontend tests as needed

### Task 1: Split Industry Report Closure Helpers Out Of `service_lifecycle.py`

**Files:**
- Create: `src/copaw/industry/service_report_closure.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`

- [ ] **Step 1: Write/extend failing regression tests if needed**
- [ ] **Step 2: Run the scoped industry closure tests**

Run: `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py -q`
Expected: PASS before and after extraction; behavior must not drift.

- [ ] **Step 3: Extract the report closure seam**

Target responsibilities to move:
- report synthesis + backlog creation helpers
- report follow-up metadata merging/carry
- cycle synthesis persistence
- control-thread report writeback helpers

- [ ] **Step 4: Re-run the scoped industry closure tests**

Run: `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py -q`
Expected: PASS

### Task 2: Split Resident Runtime And Usage Flows Out Of `query_execution_runtime.py`

**Files:**
- Create: `src/copaw/kernel/query_execution_resident_runtime.py`
- Create: `src/copaw/kernel/query_execution_usage_runtime.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `tests/app/test_runtime_bootstrap_split.py`

- [ ] **Step 1: Write/extend failing regression tests if needed**
- [ ] **Step 2: Run the scoped runtime tests**

Run: `python -m pytest tests/kernel/test_query_execution_runtime.py tests/app/test_runtime_bootstrap_split.py -q`
Expected: PASS before and after extraction.

- [ ] **Step 3: Extract runtime seams**

Target responsibilities to move:
- resident agent cache/signature/reuse helpers
- lease acquisition/release/heartbeat helpers
- usage/evidence aggregation helpers

- [ ] **Step 4: Re-run the scoped runtime tests**

Run: `python -m pytest tests/kernel/test_query_execution_runtime.py tests/app/test_runtime_bootstrap_split.py -q`
Expected: PASS

### Task 3: Split Main-Brain Card Assembly Out Of `overview_cards.py`

**Files:**
- Create: `src/copaw/app/runtime_center/overview_main_brain.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`

- [ ] **Step 1: Write/extend failing regression tests if needed**
- [ ] **Step 2: Run the scoped Runtime Center tests**

Run: `python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q`
Expected: PASS before and after extraction.

- [ ] **Step 3: Extract the main-brain/cognition card seam**

Target responsibilities to move:
- dedicated main-brain entry meta builder
- main-brain payload normalization
- report cognition payload assembly

- [ ] **Step 4: Re-run the scoped Runtime Center tests**

Run: `python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q`
Expected: PASS

### Task 4: Split Remaining Chat Page Shell Responsibilities

**Files:**
- Create: `console/src/pages/Chat/pagePresentation.tsx`
- Modify: `console/src/pages/Chat/index.tsx`
- Test: relevant Chat frontend tests

- [ ] **Step 1: Write/extend failing frontend tests if needed**
- [ ] **Step 2: Run the scoped Chat frontend tests**

Run: `cmd /c npm --prefix console test -- useRuntimeBinding.test.ts runtimeTransport.test.ts chatBindingRecovery.test.ts`
Expected: PASS before and after extraction.

- [ ] **Step 3: Extract page-shell presentation/helpers**

Target responsibilities to move:
- runtime header/status presentation
- media panel / lightweight page shell composition helpers
- page-level pure presentation pieces that do not need to stay in `index.tsx`

- [ ] **Step 4: Re-run the scoped Chat frontend tests**

Run: `cmd /c npm --prefix console test -- useRuntimeBinding.test.ts runtimeTransport.test.ts chatBindingRecovery.test.ts`
Expected: PASS

### Task 5: Split Remaining Industry/RuntimeCenter Presentation Blocks

**Files:**
- Create: `console/src/pages/Industry/runtimePresentation.tsx`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/runtimeIndustrySections.tsx`
- Test: relevant Industry / RuntimeCenter frontend tests

- [ ] **Step 1: Write/extend failing frontend tests if needed**
- [ ] **Step 2: Run the scoped frontend tests**

Run: `cmd /c npm --prefix console test -- MainBrainCockpitPanel.test.tsx`
Expected: PASS before and after extraction.

- [ ] **Step 3: Extract presentation seams**

Target responsibilities to move:
- report/planning/cognition sub-block renderers
- industry page presentation helpers that do not belong in the page shell

- [ ] **Step 4: Re-run the scoped frontend tests**

Run: `cmd /c npm --prefix console test -- MainBrainCockpitPanel.test.tsx`
Expected: PASS

## Final Verification

- [ ] **Step 1: Run the backend split suite**

Run: `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py tests/kernel/test_query_execution_runtime.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_bootstrap_split.py -q`
Expected: PASS

- [ ] **Step 2: Run the frontend split suite**

Run: `cmd /c npm --prefix console test -- MainBrainCockpitPanel.test.tsx useRuntimeBinding.test.ts runtimeTransport.test.ts chatBindingRecovery.test.ts`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/copaw/industry/service_report_closure.py src/copaw/industry/service_lifecycle.py src/copaw/kernel/query_execution_resident_runtime.py src/copaw/kernel/query_execution_usage_runtime.py src/copaw/kernel/query_execution_runtime.py src/copaw/app/runtime_center/overview_main_brain.py src/copaw/app/runtime_center/overview_cards.py console/src/pages/Chat/pagePresentation.tsx console/src/pages/Chat/index.tsx console/src/pages/Industry/runtimePresentation.tsx console/src/pages/Industry/index.tsx console/src/pages/RuntimeCenter/runtimeIndustrySections.tsx
git commit -m "refactor: split remaining heavy runtime modules"
```
