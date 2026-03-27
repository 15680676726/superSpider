# Learning and Runtime Center Hard-Cut Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hard-cut the remaining heavy learning/runtime-center services into facades plus focused collaborators while retiring legacy overview cards and keeping the live API stable.

**Architecture:** Keep `LearningService` and `RuntimeCenterQueryService` as public facades, but move domain behavior into internal services/builders with explicit shared bindings. Retire overview `goals`/`schedules` from the operator surface and thin app-layer wiring so runtime-first boundaries become real in code, not just in prompts or docs.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLite repositories, pytest

**Companion Docs:**
- Spec: `docs/superpowers/specs/2026-03-26-learning-runtime-center-hard-cut-closure.md`
- Status: `TASK_STATUS.md`
- Master plan: `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`

---

## File Map

- Create: `src/copaw/learning/runtime_bindings.py`
- Create: `src/copaw/learning/proposal_service.py`
- Create: `src/copaw/learning/patch_service.py`
- Create: `src/copaw/learning/growth_service.py`
- Create: `src/copaw/learning/acquisition_service.py`
- Modify: `src/copaw/learning/service.py`
- Create: `src/copaw/app/runtime_center/overview_cards.py`
- Create: `src/copaw/app/runtime_center/overview_helpers.py`
- Modify: `src/copaw/app/runtime_center/service.py`
- Modify: `src/copaw/app/routers/learning.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `tests/app/test_learning_api.py`
- Modify: `tests/app/runtime_center_api_parts/overview_governance.py`
- Modify: `tests/app/test_runtime_center_api.py`
- Modify: `TASK_STATUS.md`

### Task 1: Lock the overview retirement in tests

**Files:**
- Modify: `tests/app/runtime_center_api_parts/overview_governance.py`
- Modify: `tests/app/test_runtime_center_api.py`

- [ ] **Step 1: Write failing assertions that `/runtime-center/overview` no longer includes `goals` and `schedules` cards**
- [ ] **Step 2: Run the focused runtime-center tests and confirm the old behavior still fails the new assertions**
- [ ] **Step 3: Update Runtime Center overview implementation to satisfy the new contract**
- [ ] **Step 4: Re-run the focused runtime-center tests until green**

### Task 2: Split Runtime Center overview into a real facade

**Files:**
- Create: `src/copaw/app/runtime_center/overview_cards.py`
- Create: `src/copaw/app/runtime_center/overview_helpers.py`
- Modify: `src/copaw/app/runtime_center/service.py`

- [ ] **Step 1: Move card construction/mapping helpers into dedicated overview collaborators**
- [ ] **Step 2: Keep `RuntimeCenterQueryService.get_overview()` as the public entry point and delegate to the new collaborators**
- [ ] **Step 3: Preserve current cards and summaries except for retired `goals`/`schedules`**
- [ ] **Step 4: Re-run runtime-center tests**

### Task 3: Split LearningService into facade plus domain services

**Files:**
- Create: `src/copaw/learning/runtime_bindings.py`
- Create: `src/copaw/learning/proposal_service.py`
- Create: `src/copaw/learning/patch_service.py`
- Create: `src/copaw/learning/growth_service.py`
- Create: `src/copaw/learning/acquisition_service.py`
- Modify: `src/copaw/learning/service.py`
- Modify: `tests/app/test_learning_api.py`

- [ ] **Step 1: Add tests that prove learning API behavior still works through the facade after the split**
- [ ] **Step 2: Introduce explicit learning runtime bindings/shared context**
- [ ] **Step 3: Move proposal, patch, growth, and acquisition logic into dedicated internal services**
- [ ] **Step 4: Keep the public `LearningService` API stable by delegating to the internal services**
- [ ] **Step 5: Re-run focused learning tests**

### Task 4: Thin learning router and bootstrap wiring

**Files:**
- Modify: `src/copaw/app/routers/learning.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`

- [ ] **Step 1: Reduce repeated router learning-service lookups to a stable facade helper pattern**
- [ ] **Step 2: Replace setter sprawl with a single learning bindings/configuration handoff where practical**
- [ ] **Step 3: Run focused API/bootstrap regressions**

### Task 5: Close the hard-cut loop

**Files:**
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Run the full focused regression set for learning/runtime-center/industry touchpoints**
- [ ] **Step 2: Update `TASK_STATUS.md` with the actual landed state**
- [ ] **Step 3: Run one broader regression batch covering touched subsystems**
- [ ] **Step 4: Only then report completion with concrete verification output**
