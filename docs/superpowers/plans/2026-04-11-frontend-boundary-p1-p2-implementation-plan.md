# Frontend Boundary P1 P2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining frontend boundary cleanup from the audit by removing page-owned bootstrap work from Runtime Center, Industry, RightPanel, Knowledge, Predictions, and Settings.

**Architecture:** Keep the current route and page structure, but stop first paint from waiting on unnecessary work. Centralize Buddy summary reads, stage heavy page loads, and narrow each page to its own visible data instead of letting it open extra flows on mount.

**Tech Stack:** React, TypeScript, React Router, Ant Design, Vitest, Testing Library

---

## File Map

- `console/src/runtime/buddySummaryStore.ts`
  New shared read cache/store for Buddy summary so global UI does not independently re-fetch the same truth.
- `console/src/runtime/buddySummaryStore.test.ts`
  Regression coverage for cache, subscription, and refresh behavior.
- `console/src/layouts/RightPanel/index.tsx`
  Consume shared Buddy summary, stop owning its own truth.
- `console/src/layouts/RightPanel/index.test.tsx`
  Verify RightPanel reads shared summary, refresh timing, and failure isolation.
- `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
  Change Runtime Center first paint to cards-first, main-brain-second.
- `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
  Verify staged loading and separate main-brain follow-up load.
- `console/src/pages/RuntimeCenter/index.tsx`
  Keep page rendering stable while main-brain loads separately.
- `console/src/pages/RuntimeCenter/index.test.tsx`
  Verify page stays usable while main-brain is still loading.
- `console/src/pages/Industry/useIndustryPageState.ts`
  Split Industry first paint into active list first, retired/detail later.
- `console/src/pages/Industry/useIndustryPageState.test.tsx`
  Verify first paint no longer waits on retired/detail chain.
- `console/src/pages/Industry/index.tsx`
  Keep list-first UI stable with partial data.
- `console/src/pages/Industry/index.test.tsx`
  Verify industry first paint remains usable before detail hydration.
- `console/src/pages/Knowledge/index.tsx`
  Separate first paint from memory workspace/detail work.
- `console/src/pages/Knowledge/index.test.tsx`
  Verify page loads the primary list before background workspace work.
- `console/src/pages/Predictions/index.tsx`
  Keep list-first load and isolate later detail/action work.
- `console/src/pages/Predictions/index.test.ts`
  Verify list-first load path.
- `console/src/pages/Settings/System/index.tsx`
  Replace hard first-paint `Promise.all` with staged loading.
- `console/src/pages/Settings/System/index.test.tsx`
  Verify visible system surface renders without waiting on every section.
- `console/src/pages/Settings/Environments/index.tsx`
  Replace hard first-paint dual request with staged loading.
- `console/src/pages/Settings/Environments/index.test.tsx`
  New regression coverage for staged environment settings loading.

## Task 1: Add Shared Buddy Summary Store And Rewire RightPanel

**Files:**
- Create: `console/src/runtime/buddySummaryStore.ts`
- Create: `console/src/runtime/buddySummaryStore.test.ts`
- Modify: `console/src/layouts/RightPanel/index.tsx`
- Modify: `console/src/layouts/RightPanel/index.test.tsx`
- Modify if needed: `console/src/runtime/buddyChatEntry.ts`
- Modify if needed: `console/src/routes/entryRedirect.tsx`
- Modify if needed: `console/src/pages/BuddyOnboarding/index.tsx`

- [ ] **Step 1: Write the failing tests**

Cover these cases:
- store caches Buddy summary per profile id
- multiple consumers do not trigger duplicate reads for the same profile
- RightPanel consumes the store instead of directly owning `getBuddySurface` timing
- RightPanel still refreshes on the existing 5-minute cadence and failure does not break the page

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `npm --prefix console test -- src/runtime/buddySummaryStore.test.ts src/layouts/RightPanel/index.test.tsx`
Expected: FAIL because the shared store does not exist yet and RightPanel still reads directly.

- [ ] **Step 3: Implement the minimal shared Buddy summary path**

Implement these rules:
- create a small app-level Buddy summary store/cache with subscription support
- the store owns deduped fetch and refresh timing
- RightPanel subscribes to store state and no longer independently decides truth
- existing Buddy entry/chat/onboarding paths may seed the store when they already hold fresh Buddy data

- [ ] **Step 4: Run the focused tests again**

Run: `npm --prefix console test -- src/runtime/buddySummaryStore.test.ts src/layouts/RightPanel/index.test.tsx`
Expected: PASS

## Task 2: Make Runtime Center Cards-First And Main-Brain-Second

**Files:**
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Modify: `console/src/pages/RuntimeCenter/index.test.tsx`

- [ ] **Step 1: Write the failing tests**

Cover these cases:
- first paint requests `cards` only
- main-brain loads in a follow-up request
- cards stay visible while main-brain is still loading
- event-driven refresh continues to request only the needed sections

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `npm --prefix console test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/index.test.tsx`
Expected: FAIL because Runtime Center still defaults to `cards + main_brain` on first paint.

- [ ] **Step 3: Implement the minimal staged Runtime Center load**

Implement these rules:
- first paint requests only `cards`
- a follow-up effect requests `main_brain`
- page UI remains usable while `main_brain` is pending
- keep section-aware event refresh behavior intact

- [ ] **Step 4: Run the focused tests again**

Run: `npm --prefix console test -- src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/index.test.tsx`
Expected: PASS

## Task 3: Split Industry First Paint Into List-First Loading

**Files:**
- Modify: `console/src/pages/Industry/useIndustryPageState.ts`
- Modify: `console/src/pages/Industry/useIndustryPageState.test.tsx`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/Industry/index.test.tsx`

- [ ] **Step 1: Write the failing tests**

Cover these cases:
- active list renders without waiting on retired list
- first paint does not wait on detail hydration for current carrier
- retired/detail work can finish later without blocking page usability

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `npm --prefix console test -- src/pages/Industry/useIndustryPageState.test.tsx src/pages/Industry/index.test.tsx`
Expected: FAIL because Industry still waits on combined first-paint work.

- [ ] **Step 3: Implement the minimal staged Industry load**

Implement these rules:
- first paint loads active instances first
- retired instances load in follow-up work
- detail stays on-demand
- current carrier should not force a full detail fetch before the page becomes usable

- [ ] **Step 4: Run the focused tests again**

Run: `npm --prefix console test -- src/pages/Industry/useIndustryPageState.test.tsx src/pages/Industry/index.test.tsx`
Expected: PASS

## Task 4: Reduce Secondary Page First-Paint Work

**Files:**
- Modify: `console/src/pages/Knowledge/index.tsx`
- Modify: `console/src/pages/Knowledge/index.test.tsx`
- Modify: `console/src/pages/Predictions/index.tsx`
- Modify: `console/src/pages/Predictions/index.test.ts`
- Modify: `console/src/pages/Settings/System/index.tsx`
- Modify: `console/src/pages/Settings/System/index.test.tsx`
- Modify: `console/src/pages/Settings/Environments/index.tsx`
- Create or Modify: `console/src/pages/Settings/Environments/index.test.tsx`

- [ ] **Step 1: Write the failing tests**

Cover these cases:
- Knowledge first paint loads the main page before memory workspace/detail
- Predictions first paint stays list-first
- Settings/System no longer hard-waits on every section
- Settings/Environments no longer hard-waits on both initial requests

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `npm --prefix console test -- src/pages/Knowledge/index.test.tsx src/pages/Predictions/index.test.ts src/pages/Settings/System/index.test.tsx src/pages/Settings/Environments/index.test.tsx`
Expected: FAIL because these pages still bind first paint to extra work.

- [ ] **Step 3: Implement the minimal secondary-page staged loading**

Implement these rules:
- Knowledge: page-first, workspace/detail later
- Predictions: list-first, detail/action later
- Settings/System: visible primary section first, remaining requests later
- Settings/Environments: provider list or active surface first, secondary context later

- [ ] **Step 4: Run the focused tests again**

Run: `npm --prefix console test -- src/pages/Knowledge/index.test.tsx src/pages/Predictions/index.test.ts src/pages/Settings/System/index.test.tsx src/pages/Settings/Environments/index.test.tsx`
Expected: PASS

## Task 5: Verify The Remaining P1 P2 Scope

**Files:**
- Reuse all touched frontend files

- [ ] **Step 1: Run the consolidated remaining frontend verification**

Run: `npm --prefix console test -- src/runtime/buddySummaryStore.test.ts src/layouts/RightPanel/index.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts src/pages/RuntimeCenter/index.test.tsx src/pages/Industry/useIndustryPageState.test.tsx src/pages/Industry/index.test.tsx src/pages/Knowledge/index.test.tsx src/pages/Predictions/index.test.ts src/pages/Settings/System/index.test.tsx src/pages/Settings/Environments/index.test.tsx`
Expected: PASS

- [ ] **Step 2: Run production build**

Run: `npm --prefix console run build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add console/src/runtime/buddySummaryStore.ts console/src/runtime/buddySummaryStore.test.ts console/src/layouts/RightPanel/index.tsx console/src/layouts/RightPanel/index.test.tsx console/src/pages/RuntimeCenter/useRuntimeCenter.ts console/src/pages/RuntimeCenter/index.tsx console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts console/src/pages/RuntimeCenter/index.test.tsx console/src/pages/Industry/useIndustryPageState.ts console/src/pages/Industry/useIndustryPageState.test.tsx console/src/pages/Industry/index.tsx console/src/pages/Industry/index.test.tsx console/src/pages/Knowledge/index.tsx console/src/pages/Knowledge/index.test.tsx console/src/pages/Predictions/index.tsx console/src/pages/Predictions/index.test.ts console/src/pages/Settings/System/index.tsx console/src/pages/Settings/System/index.test.tsx console/src/pages/Settings/Environments/index.tsx console/src/pages/Settings/Environments/index.test.tsx
git commit -m "feat: finish frontend staged loading and shared buddy summary"
```
