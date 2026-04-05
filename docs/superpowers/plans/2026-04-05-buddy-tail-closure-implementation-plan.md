# Buddy Tail Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the last 5 Buddy-first product-logic gaps so Buddy, chat, and Industry behave as one coherent companion runtime.

**Architecture:** Apply a medium hard-cut closure pass instead of a broad rewrite. Protect the active Buddy carrier, switch Buddy's front-stage task source to human-first semantics, make strong-support growth come from formal runtime signals, add a short confirmation completion state, and reframe Industry as a current carrier editor instead of a second onboarding surface.

**Tech Stack:** FastAPI, Python, Pydantic, React, TypeScript, Ant Design, pytest, Vitest

---

## File Structure

### Backend files to modify

- `src/copaw/kernel/buddy_projection_service.py`
  - reorder Buddy task resolution to prefer human-assist / human-owned next step before carrier assignment/backlog fallback
- `src/copaw/kernel/buddy_runtime_focus.py`
  - downgrade carrier assignment/backlog focus to fallback-only human-facing input
- `src/copaw/kernel/buddy_onboarding_service.py`
  - formalize strong-support detection in interaction recording
- `src/copaw/app/routers/runtime_center_routes_core.py`
  - pass stronger interaction context into Buddy interaction recording

### Frontend files to modify

- `console/src/pages/BuddyOnboarding/index.tsx`
  - add a short post-confirm completion state before entering chat naming
- `console/src/pages/BuddyOnboarding/index.test.tsx`
  - lock the new completion step and navigation behavior
- `console/src/pages/Industry/index.tsx`
  - block deletion for the active Buddy carrier and replace remaining second-onboarding language
- `console/src/pages/Industry/useIndustryPageState.ts`
  - expose active-carrier deletion guard and keep carrier selection logic stable
- `console/src/pages/Industry/index.test.tsx`
  - cover protected current-carrier deletion and updated copy
- `console/src/pages/Industry/useIndustryPageState.test.tsx`
  - cover current-carrier protection logic

### Backend tests to modify/add

- `tests/kernel/test_buddy_projection_service.py`
- `tests/app/test_buddy_runtime_bootstrap.py`
- `tests/kernel/test_buddy_onboarding_service.py`

### Frontend tests to modify/add

- `console/src/pages/BuddyOnboarding/index.test.tsx`
- `console/src/pages/Industry/index.test.tsx`
- `console/src/pages/Industry/useIndustryPageState.test.tsx`

---

### Task 1: Protect The Active Buddy Carrier From Deletion

**Files:**
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/Industry/useIndustryPageState.ts`
- Test: `console/src/pages/Industry/index.test.tsx`
- Test: `console/src/pages/Industry/useIndustryPageState.test.tsx`

- [ ] **Step 1: Write the failing UI test for protected current carrier**

```tsx
it("does not show delete affordance for the current buddy carrier", () => {
  // render Industry page with selected instance_id === `buddy:${profileId}`
  // expect delete action to be hidden or disabled
});
```

- [ ] **Step 2: Run the targeted frontend tests to verify failure**

Run: `npm --prefix console run test -- src/pages/Industry/index.test.tsx src/pages/Industry/useIndustryPageState.test.tsx`
Expected: FAIL because current carrier is still deletable

- [ ] **Step 3: Add current-carrier protection logic in page state**

Implement a helper that detects:

- current bound Buddy profile id
- active carrier id `buddy:${profile_id}`
- whether a listed instance is the protected current carrier

- [ ] **Step 4: Update Industry UI**

Change the current carrier list so the protected Buddy carrier:

- cannot be deleted
- shows clear current-carrier language

- [ ] **Step 5: Re-run targeted frontend tests**

Run: `npm --prefix console run test -- src/pages/Industry/index.test.tsx src/pages/Industry/useIndustryPageState.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add console/src/pages/Industry/index.tsx console/src/pages/Industry/useIndustryPageState.ts console/src/pages/Industry/index.test.tsx console/src/pages/Industry/useIndustryPageState.test.tsx
git commit -m "fix: protect current buddy carrier from deletion"
```

### Task 2: Make Buddy's Default Current Task Human-First

**Files:**
- Modify: `src/copaw/kernel/buddy_projection_service.py`
- Modify: `src/copaw/kernel/buddy_runtime_focus.py`
- Test: `tests/kernel/test_buddy_projection_service.py`
- Test: `tests/app/test_buddy_runtime_bootstrap.py`

- [ ] **Step 1: Write the failing backend test for human-first current task**

```python
def test_buddy_projection_prefers_human_assist_task_over_carrier_assignment(tmp_path):
    # create both a human-assist task and a carrier assignment
    # assert Buddy presentation.current_task_summary uses the human task
```

- [ ] **Step 2: Run the targeted backend tests to verify failure**

Run: `python -m pytest tests/kernel/test_buddy_projection_service.py tests/app/test_buddy_runtime_bootstrap.py -q`
Expected: FAIL because assignment/backlog currently wins

- [ ] **Step 3: Change Buddy projection priority**

Update Buddy projection so the human-facing task source order becomes:

1. active human-assist task
2. explicit human checkpoint if available
3. carrier fallback from assignment/backlog

- [ ] **Step 4: Narrow carrier focus helper**

Update `buddy_runtime_focus.py` so it becomes fallback-only support context instead of the default human-facing task source.

- [ ] **Step 5: Re-run the targeted backend tests**

Run: `python -m pytest tests/kernel/test_buddy_projection_service.py tests/app/test_buddy_runtime_bootstrap.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/kernel/buddy_projection_service.py src/copaw/kernel/buddy_runtime_focus.py tests/kernel/test_buddy_projection_service.py tests/app/test_buddy_runtime_bootstrap.py
git commit -m "fix: prefer human task in buddy current-step projection"
```

### Task 3: Make Strong Support A Real Runtime Signal

**Files:**
- Modify: `src/copaw/kernel/buddy_onboarding_service.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Test: `tests/kernel/test_buddy_onboarding_service.py`

- [ ] **Step 1: Write the failing backend test for strong-support growth**

```python
def test_record_chat_interaction_increments_strong_pull_for_stuck_or_avoidance_messages(tmp_path):
    # submit profile, confirm direction
    # record message like "我卡住了，我现在不想做"
    # assert strong_pull_count increments
```

- [ ] **Step 2: Run the targeted backend test to verify failure**

Run: `python -m pytest tests/kernel/test_buddy_onboarding_service.py -k strong_pull -q`
Expected: FAIL because only `interaction_mode == "strong-pull"` increments today

- [ ] **Step 3: Implement formal strong-support detection**

Make strong support trigger from at least:

- explicit stuck/avoidance/refusal phrases
- any future explicit pull-back interaction mode

Keep the implementation small and rule-based for this closure pass.

- [ ] **Step 4: Ensure the runtime chat front-door passes through the needed signal cleanly**

Only extend the current recording seam enough to preserve a formal runtime signal. Do not add a parallel side chain.

- [ ] **Step 5: Re-run the targeted backend tests**

Run: `python -m pytest tests/kernel/test_buddy_onboarding_service.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/kernel/buddy_onboarding_service.py src/copaw/app/routers/runtime_center_routes_core.py tests/kernel/test_buddy_onboarding_service.py
git commit -m "fix: ground strong support growth in formal chat signals"
```

### Task 4: Add A Visible Completion Step After Direction Confirmation

**Files:**
- Modify: `console/src/pages/BuddyOnboarding/index.tsx`
- Test: `console/src/pages/BuddyOnboarding/index.test.tsx`

- [ ] **Step 1: Write the failing frontend test for confirmation completion**

```tsx
it("shows carrier generation completion before routing into chat naming", async () => {
  // confirm direction
  // expect generated carrier summary to appear
  // then continue into chat
});
```

- [ ] **Step 2: Run the targeted onboarding tests to verify failure**

Run: `npm --prefix console run test -- src/pages/BuddyOnboarding/index.test.tsx`
Expected: FAIL because the page navigates immediately today

- [ ] **Step 3: Add a short completion state**

Show:

- confirmed direction
- generated carrier label or fallback message
- generated scaffold status
- CTA to enter chat and name Buddy

- [ ] **Step 4: Keep navigation single-path and lightweight**

Do not introduce a second onboarding center or a dashboard detour. This step should only close the loop visibly, then continue to chat.

- [ ] **Step 5: Re-run the targeted onboarding tests**

Run: `npm --prefix console run test -- src/pages/BuddyOnboarding/index.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add console/src/pages/BuddyOnboarding/index.tsx console/src/pages/BuddyOnboarding/index.test.tsx
git commit -m "fix: add visible buddy direction confirmation closure"
```

### Task 5: Reframe Industry As Current Carrier Adjustment

**Files:**
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/Industry/useIndustryPageState.ts`
- Test: `console/src/pages/Industry/index.test.tsx`

- [ ] **Step 1: Write the failing UI test for carrier-adjustment copy**

```tsx
it("presents Industry as carrier adjustment rather than first-time bootstrap", () => {
  // expect current-carrier language
  // expect old create-again language to be absent from the active path
});
```

- [ ] **Step 2: Run the targeted Industry tests to verify failure**

Run: `npm --prefix console run test -- src/pages/Industry/index.test.tsx`
Expected: FAIL because legacy bootstrap semantics still remain

- [ ] **Step 3: Narrow the active edit flow**

For the active Buddy carrier adjustment path:

- remove or hide legacy bootstrap-only copy
- keep only current-carrier adjustment inputs
- rename actions so they read as adjustment, not genesis

- [ ] **Step 4: Keep backend usage minimal**

Reuse the existing preview/update machinery where possible, but stop exposing it with first-time bootstrap wording in the active Buddy flow.

- [ ] **Step 5: Re-run the targeted Industry tests**

Run: `npm --prefix console run test -- src/pages/Industry/index.test.tsx src/pages/Industry/useIndustryPageState.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add console/src/pages/Industry/index.tsx console/src/pages/Industry/useIndustryPageState.ts console/src/pages/Industry/index.test.tsx console/src/pages/Industry/useIndustryPageState.test.tsx
git commit -m "fix: reframe industry as current carrier adjustment"
```

### Task 6: End-To-End Verification And Status Sync

**Files:**
- Modify: `TASK_STATUS.md`
- Test: targeted backend and frontend suites

- [ ] **Step 1: Run backend verification**

Run:

```bash
python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_service.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py tests/app/test_buddy_runtime_bootstrap.py -q
```

Expected: PASS

- [ ] **Step 2: Run frontend verification**

Run:

```bash
npm --prefix console run test -- src/pages/BuddyOnboarding/index.test.tsx src/pages/Industry/index.test.tsx src/pages/Industry/useIndustryPageState.test.tsx src/pages/Chat/ChatAccessGate.test.tsx src/runtime/buddyFlow.test.ts src/pages/Chat/BuddyPanel.test.tsx src/pages/Chat/BuddyCompanion.test.tsx src/pages/Chat/buddyPresentation.test.ts src/pages/Chat/buddyEvolution.test.ts src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
```

Expected: PASS

- [ ] **Step 3: Run frontend build**

Run:

```bash
npm --prefix console run build
```

Expected: build succeeds

- [ ] **Step 4: Update task status**

Record the closure of:

- active carrier deletion protection
- human-first Buddy task semantics
- formal strong-support growth signal
- visible post-confirm completion state
- Industry carrier-adjustment semantic hard cut

- [ ] **Step 5: Commit**

```bash
git add TASK_STATUS.md
git commit -m "docs: sync buddy tail closure status"
```

---

## Notes For Execution

- Do not re-open a second onboarding path.
- Do not let Industry regain first-entry ownership.
- Do not reintroduce a second truth source for Buddy state.
- Keep the closure pass focused on product logic, not visual over-expansion.
- Respect the current user rule: no multi-agent execution in this repo session.
