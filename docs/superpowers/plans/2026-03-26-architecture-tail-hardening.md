# Architecture Tail Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining high-impact architecture gaps around IndustryService, Kernel query/writeback routing, frontend page-god surfaces, and learning/discovery duplication without introducing new truth sources.

**Architecture:** Harden `IndustryService` into a single injected-entry facade with targeted goal reconciliation, unify query/writeback intent heuristics behind one shared kernel policy module, move page-level orchestration out of Chat/Industry/CapabilityMarket into focused helpers, and continue shrinking learning/discovery god flows by extracting shared recommendation and lifecycle collaborators.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLite repositories, React, TypeScript, Vitest, pytest

---

### Task 1: Lock IndustryService and kernel routing seams in tests

**Files:**
- Modify: `tests/app/test_industry_service_wiring.py`
- Modify: `tests/kernel/test_query_execution_shared_split.py`
- Create: `tests/kernel/test_query_execution_intent_policy.py`

- [ ] **Step 1: Add a failing industry test that proves goal reconcile does not require scanning all instances and does not rely on lazy delegate recreation.**
- [ ] **Step 2: Add a failing kernel test that imports one shared goal/entrustment policy and asserts query-frontdoor and durable writeback use identical decisions for the same text.**
- [ ] **Step 3: Run the focused pytest batch and confirm the new assertions fail before implementation.**

### Task 2: Harden IndustryService into one explicit entry boundary

**Files:**
- Modify: `src/copaw/industry/service.py`
- Modify: `src/copaw/industry/service_context.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/view_service.py`

- [ ] **Step 1: Remove lazy internal recreation of bootstrap/team/view delegates from `IndustryService`.**
- [ ] **Step 2: Replace state-store fallback construction with explicit runtime bindings assembly at bootstrap boundaries only.**
- [ ] **Step 3: Add one targeted goal-to-instance reconciliation path so `reconcile_instance_status_for_goal()` updates only affected instances.**
- [ ] **Step 4: Re-run the focused industry pytest batch.**

### Task 3: Unify query and writeback intent heuristics

**Files:**
- Create: `src/copaw/kernel/query_execution_intent_policy.py`
- Modify: `src/copaw/kernel/query_execution_shared.py`
- Modify: `src/copaw/kernel/query_execution_writeback.py`

- [ ] **Step 1: Move goal-setting, entrustment, and hypothetical-control heuristics into a single shared policy module.**
- [ ] **Step 2: Rewire both shared query planning and durable writeback to call the same policy helpers instead of maintaining duplicated copies.**
- [ ] **Step 3: Keep public behavior stable except where the duplicated rules previously drifted.**
- [ ] **Step 4: Re-run the focused kernel pytest batch.**

### Task 4: Remove Chat DOM surgery and finish page-level boundary extraction

**Files:**
- Create: `console/src/pages/Chat/ChatComposerAdapter.tsx`
- Create: `console/src/pages/Industry/useIndustryPageState.ts`
- Create: `console/src/pages/CapabilityMarket/useCapabilityMarketState.ts`
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/useChatRuntimeState.ts`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/CapabilityMarket/index.tsx`
- Create: `console/src/pages/Chat/ChatComposerAdapter.test.tsx`

- [ ] **Step 1: Add a failing Chat test that proves the page no longer mutates third-party DOM to unlock input state.**
- [ ] **Step 2: Introduce a stable Chat composer adapter boundary so page composition owns send-state through props/state, not DOM patching.**
- [ ] **Step 3: Extract Industry and CapabilityMarket application orchestration into focused hooks so page files become composition shells.**
- [ ] **Step 4: Re-run the focused Vitest batch and `npm run build`.**

### Task 5: Thin learning/discovery tails and remove confirmed stale text corruption

**Files:**
- Create: `src/copaw/capabilities/recommendation_builders.py`
- Modify: `src/copaw/capabilities/capability_discovery.py`
- Modify: `src/copaw/learning/runtime_core.py`
- Modify: `src/copaw/learning/service.py`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Extract shared hub/curated recommendation item assembly into one builder layer used by both discovery paths.**
- [ ] **Step 2: Move remaining patch/growth/acquisition orchestration helpers out of `LearningRuntimeCore` where a focused service already exists.**
- [ ] **Step 3: Search and fix any remaining confirmed mojibake in touched source paths without broad encoding churn.**
- [ ] **Step 4: Update `TASK_STATUS.md` to reflect the landed hardening work.**

### Task 6: Verification closure

**Files:**
- Modify: `tests/app/test_industry_service_wiring.py`
- Modify: `tests/kernel/test_query_execution_intent_policy.py`
- Modify: `console/src/pages/Chat/ChatComposerAdapter.test.tsx`

- [ ] **Step 1: Run the focused backend pytest batch for industry, kernel, learning, and discovery touchpoints.**
- [ ] **Step 2: Run the focused frontend Vitest batch for Chat/Industry/CapabilityMarket.**
- [ ] **Step 3: Run `npm run build` in `console/`.**
- [ ] **Step 4: Only then report completion with concrete verification output and any residual debt that intentionally remains.**
