# Buddy Industry Direction Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure Buddy-generated execution carriers store a formal direction-first `IndustryProfile` instead of a human current-state snapshot, and align the affected UI mindshare with that boundary.

**Architecture:** Keep `HumanProfile` as the human-current-state truth and `GrowthTarget` as the chosen direction truth. Convert Buddy onboarding carrier generation to write a minimal valid `IndustryProfile` into `IndustryInstanceRecord.profile_payload`, then protect the behavior with backend tests and a small front-end mindshare fix where the wrong coupling is exposed.

**Tech Stack:** Python, FastAPI, Pydantic, React, TypeScript, pytest, Vitest

---

## File Structure

- `src/copaw/kernel/buddy_onboarding_service.py`
  - build the formal Buddy carrier `IndustryProfile`
- `tests/kernel/test_buddy_onboarding_service.py`
  - lock the new Buddy carrier truth contract
- `console/src/pages/Industry/pageHelpers.tsx`
  - inspect and tighten current carrier preview payload mapping or related field copy
- `console/src/pages/Industry/useIndustryPageState.ts`
  - inspect current carrier preview flow if Buddy-specific mental model leaks here
- `console/src/pages/Industry/*.test.tsx`
  - add or update the smallest test that protects the corrected mental model

---

### Task 1: Lock The Backend Truth Contract

**Files:**
- Modify: `tests/kernel/test_buddy_onboarding_service.py`
- Test: `tests/kernel/test_buddy_onboarding_service.py`

- [ ] **Step 1: Write the failing Buddy carrier truth test**

```python
def test_confirm_primary_direction_writes_direction_first_industry_profile(tmp_path) -> None:
    ...
    profile = IndustryProfile.model_validate(instance.profile_payload)
    assert profile.industry == result.growth_target.primary_direction
    assert result.growth_target.final_goal in profile.goals
    assert "profession" not in instance.profile_payload
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_onboarding_service.py::test_confirm_primary_direction_writes_direction_first_industry_profile -q`
Expected: FAIL because the current Buddy scaffold writes a human snapshot into `profile_payload`

---

### Task 2: Implement Formal IndustryProfile Writing

**Files:**
- Modify: `src/copaw/kernel/buddy_onboarding_service.py`
- Test: `tests/kernel/test_buddy_onboarding_service.py`

- [ ] **Step 1: Add a minimal helper that builds a formal IndustryProfile**

```python
def _build_buddy_industry_profile(*, profile: HumanProfile, growth_target: GrowthTarget) -> IndustryProfile:
    ...
```

- [ ] **Step 2: Replace the current `profile_payload` write inside `_ensure_growth_scaffold(...)`**

Write:
- `industry` from `growth_target.primary_direction`
- `goals` including `growth_target.final_goal`
- `constraints` from execution constraints only
- `notes` as a short Buddy bootstrap summary

- [ ] **Step 3: Keep `execution_core_identity_payload` aligned with the same formal direction**

- [ ] **Step 4: Run the targeted backend test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_onboarding_service.py::test_confirm_primary_direction_writes_direction_first_industry_profile -q`
Expected: PASS

---

### Task 3: Run Focused Backend Regression

**Files:**
- Test: `tests/kernel/test_buddy_onboarding_service.py`
- Test: `tests/app/test_buddy_cutover.py`

- [ ] **Step 1: Run the Buddy onboarding suite**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_onboarding_service.py -q`
Expected: PASS

- [ ] **Step 2: Run the Buddy cutover/API regression that touches the carrier path**

Run: `PYTHONPATH=src python -m pytest tests/app/test_buddy_cutover.py -q`
Expected: PASS

---

### Task 4: Tighten Frontend Mindshare

**Files:**
- Modify: `console/src/pages/Industry/pageHelpers.tsx`
- Modify: `console/src/pages/Industry/useIndustryPageState.ts`
- Modify: one relevant frontend test file under `console/src/pages/Industry/`

- [ ] **Step 1: Write or update one focused frontend test**

Protect one concrete rule:
- Buddy/current carrier flow must not imply that current profession/current industry is the formal execution direction

- [ ] **Step 2: Adjust the smallest front-end surface needed**

Options:
- field label / placeholder / helper copy
- preview payload mapping only if the wrong value source is confirmed in code

- [ ] **Step 3: Run the targeted frontend test**

Run: `npm --prefix console run test -- src/pages/Industry/<target-test-file>`
Expected: PASS

---

### Task 5: Final Verification

**Files:**
- Test: `tests/kernel/test_buddy_onboarding_service.py`
- Test: `tests/app/test_buddy_cutover.py`
- Test: relevant `console/src/pages/Industry/*` test file

- [ ] **Step 1: Run the complete focused verification set**

Run: `PYTHONPATH=src python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/app/test_buddy_cutover.py -q`
Expected: PASS

- [ ] **Step 2: Run the targeted frontend verification**

Run: `npm --prefix console run test -- src/pages/Industry/<target-test-file>`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-04-07-buddy-industry-direction-truth-design.md docs/superpowers/plans/2026-04-07-buddy-industry-direction-truth-implementation-plan.md src/copaw/kernel/buddy_onboarding_service.py tests/kernel/test_buddy_onboarding_service.py console/src/pages/Industry/pageHelpers.tsx console/src/pages/Industry/useIndustryPageState.ts
git commit -m "fix: align buddy carrier industry truth with confirmed direction"
```
