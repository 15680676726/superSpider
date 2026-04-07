# Buddy Stage Tail Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the remaining Buddy stage work by making domain capability scores grow from real execution evidence and by requiring explicit human confirmation for domain inheritance decisions in Buddy onboarding.

**Architecture:** Keep `BuddyDomainCapabilityRecord` as the single truth for the current domain's capability stage. Add one backend service that derives `strategy / execution / evidence / stability / capability_score` from canonical planning/runtime signals for the active Buddy domain, and reuse the existing preview/confirm contract while moving the frontend from auto-accepting the recommendation to a real user choice modal.

**Tech Stack:** Python, FastAPI, SQLite, Pydantic, React, TypeScript, Ant Design, pytest, Vitest

---

## File Structure

- `src/copaw/kernel/buddy_domain_capability.py`
  Responsibility: pure capability-stage helpers plus score aggregation math and stage-band mapping.
- `src/copaw/kernel/buddy_domain_capability_growth.py`
  Responsibility: derive active-domain capability metrics from canonical planning/runtime truth and persist updates.
- `src/copaw/kernel/buddy_onboarding_service.py`
  Responsibility: trigger capability growth refresh after domain confirmation and expose preview data needed by the UI.
- `src/copaw/kernel/buddy_projection_service.py`
  Responsibility: surface refreshed capability truth without reintroducing relationship-driven stage logic.
- `src/copaw/app/runtime_service_graph.py`
  Responsibility: wire the new growth service into the canonical Buddy service graph.
- `tests/kernel/test_buddy_domain_capability.py`
  Responsibility: pure score-band and score-aggregation coverage.
- `tests/kernel/test_buddy_onboarding_service.py`
  Responsibility: domain confirmation behavior and capability refresh coverage.
- `tests/kernel/test_buddy_projection_capability.py`
  Responsibility: stage projection coverage after score recomputation.
- `tests/app/test_buddy_cutover.py`
  Responsibility: end-to-end Buddy surface/runtime summary alignment after capability refresh.
- `console/src/pages/BuddyOnboarding/index.tsx`
  Responsibility: explicit transition-choice UI instead of auto-confirming the preview recommendation.
- `console/src/pages/BuddyOnboarding/index.test.tsx`
  Responsibility: UI coverage for keep/restore/new domain choices and confirm payloads.
- `console/src/api/modules/buddy.ts`
  Responsibility: frontend types for preview payload and confirm request.
- `console/src/pages/Chat/BuddyPanel.tsx`
  Responsibility: render refreshed capability metrics without assuming static zeros.
- `TASK_STATUS.md`
  Responsibility: record completion of the tail items and fresh verification evidence.

---

### Task 1: Lock Capability Growth Rules With Tests

**Files:**
- Modify: `tests/kernel/test_buddy_domain_capability.py`
- Modify: `tests/kernel/test_buddy_onboarding_service.py`

- [ ] **Step 1: Write failing tests for score derivation**

Add tests that prove:

```python
def test_derive_capability_scores_caps_each_component_and_stage_band() -> None: ...
def test_confirm_primary_direction_refreshes_active_domain_capability_from_planning_truth(tmp_path) -> None: ...
```

- [ ] **Step 2: Run the focused backend tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_domain_capability.py tests/kernel/test_buddy_onboarding_service.py -q`
Expected: FAIL because score derivation and refresh hooks do not exist yet.

- [ ] **Step 3: Implement the minimal growth helpers**

Add pure functions that:
- clamp `strategy/execution/evidence/stability`
- sum them into `capability_score`
- derive `evolution_stage`
- serialize a stable summary for projection

- [ ] **Step 4: Run the focused backend tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_domain_capability.py tests/kernel/test_buddy_onboarding_service.py -q`
Expected: PASS

---

### Task 2: Recompute Active-Domain Capability From Canonical Runtime Truth

**Files:**
- Create: `src/copaw/kernel/buddy_domain_capability_growth.py`
- Modify: `src/copaw/kernel/buddy_onboarding_service.py`
- Modify: `src/copaw/kernel/buddy_projection_service.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `tests/kernel/test_buddy_projection_capability.py`
- Modify: `tests/app/test_buddy_cutover.py`

- [ ] **Step 1: Write failing integration tests for refreshed capability payloads**

Cover:
- active domain refresh uses canonical planning/runtime facts
- Buddy surface exposes non-zero capability metrics when evidence exists
- Runtime Center buddy summary matches the refreshed record

- [ ] **Step 2: Run the targeted backend suites to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_projection_capability.py tests/app/test_buddy_cutover.py -q`
Expected: FAIL because capability refresh is not computed from planning/runtime truth yet.

- [ ] **Step 3: Implement the growth service and hook it into Buddy flows**

Service responsibilities:
- read canonical planning/runtime signals for the Buddy execution carrier
- derive `strategy / execution / evidence / stability`
- update the active `BuddyDomainCapabilityRecord`
- refresh during direction confirmation and before Buddy surface projection if needed

- [ ] **Step 4: Run the targeted backend suites to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_projection_capability.py tests/app/test_buddy_cutover.py -q`
Expected: PASS

---

### Task 3: Require Explicit Human Choice In Buddy Onboarding

**Files:**
- Modify: `console/src/pages/BuddyOnboarding/index.tsx`
- Modify: `console/src/pages/BuddyOnboarding/index.test.tsx`
- Modify: `console/src/api/modules/buddy.ts`

- [ ] **Step 1: Write failing UI tests**

Add tests that prove:
- preview opens a choice UI before confirmation
- the user can choose `keep-active`
- the user can choose a specific archived domain to restore
- the user can choose `start-new`

- [ ] **Step 2: Run the focused frontend suite to verify it fails**

Run: `npm --prefix console test -- src/pages/BuddyOnboarding/index.test.tsx src/api/modules/buddy.test.ts`
Expected: FAIL because the page still auto-submits the recommended action.

- [ ] **Step 3: Implement the explicit confirmation UI**

Minimal UI requirements:
- keep current recommendation explanation visible
- render the three action choices with human-readable copy
- require a user click before submitting `confirmBuddyDirection(...)`
- only send `target_domain_id` when the chosen action is `restore-archived`

- [ ] **Step 4: Run the focused frontend suite to verify it passes**

Run: `npm --prefix console test -- src/pages/BuddyOnboarding/index.test.tsx src/api/modules/buddy.test.ts`
Expected: PASS

---

### Task 4: Regression Verification And Status Sync

**Files:**
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Run the full Buddy backend regression set**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_domain_capability.py tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_service.py tests/kernel/test_buddy_projection_capability.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py -q`
Expected: PASS

- [ ] **Step 2: Run the full Buddy frontend regression set**

Run: `npm --prefix console test -- src/api/modules/buddy.test.ts src/pages/BuddyOnboarding/index.test.tsx src/pages/Chat/buddyEvolution.test.ts src/pages/Chat/buddyPresentation.test.ts src/pages/Chat/BuddyPanel.test.tsx src/pages/Chat/BuddyCompanion.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/runtime/buddyFlow.test.ts`
Expected: PASS

- [ ] **Step 3: Run the console build**

Run: `npm --prefix console run build`
Expected: PASS

- [ ] **Step 4: Update status documentation with fresh verification evidence**

Record:
- capability growth is now execution/evidence-driven
- onboarding domain switch requires explicit human choice
- exact backend/frontend/build verification commands and outcomes
