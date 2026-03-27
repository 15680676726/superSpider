# Capability / Governance / UI Tail Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining capability-compat and presentation tails so the runtime-first hard-cut no longer ships legacy `/skills` and `/mcp` aliases, duplicated router mutation dispatch, duplicated decision/patch action builders, or split frontend risk/status color semantics.

**Architecture:** Delete the legacy alias routers instead of preserving them behind headers, move router-side governed writes onto one shared mutation dispatcher, move decision/patch action link assembly onto shared runtime helpers, and centralize frontend runtime tag color semantics behind one shared presentation module consumed by runtime/chat/agent workbench surfaces.

**Tech Stack:** Python 3, FastAPI, Pydantic, pytest, TypeScript, React, Vitest

---

### Task 1: Retire legacy `/skills` and `/mcp` router aliases

**Files:**
- Modify: `tests/app/test_phase2_read_surface_unification.py`
- Modify: `tests/app/test_capabilities_write_api.py`
- Modify: `src/copaw/app/routers/__init__.py`
- Delete: `src/copaw/app/routers/legacy_capability_aliases.py`
- Delete: `src/copaw/app/routers/skills.py`
- Delete: `src/copaw/app/routers/mcp.py`

- [ ] **Step 1: Rewrite the route-surface tests to assert legacy routers are absent instead of hidden**
- [ ] **Step 2: Run the focused tests and confirm the old legacy routes still exist and therefore fail**
- [ ] **Step 3: Remove legacy router mounting and delete the three legacy alias files**
- [ ] **Step 4: Update or remove legacy write-route tests so canonical capability-market routes remain the only supported surface**
- [ ] **Step 5: Re-run the focused route tests**

### Task 2: Unify router governed mutation dispatch

**Files:**
- Create: `src/copaw/app/routers/governed_mutations.py`
- Modify: `tests/app/test_capabilities_write_api.py`
- Modify: `src/copaw/app/routers/config.py`
- Modify: `src/copaw/app/routers/capabilities.py`
- Modify: `src/copaw/app/routers/capability_market.py`
- Modify: `src/copaw/app/routers/runtime_center_shared.py`
- Modify: `src/copaw/app/routers/agent.py`

- [ ] **Step 1: Add a failing backend test covering the shared mutation helper contract**
- [ ] **Step 2: Run that test and verify it fails because the helper does not exist**
- [ ] **Step 3: Implement one shared governed mutation helper for capability lookup, risk resolution, `KernelTask` assembly, submit, and execute**
- [ ] **Step 4: Replace the duplicated `_mutation_risk()` and `_dispatch_*mutation()` blocks in the router modules with the shared helper**
- [ ] **Step 5: Re-run the backend mutation tests**

### Task 3: Unify runtime decision and patch action builders

**Files:**
- Create: `src/copaw/app/runtime_center/action_links.py`
- Modify: `tests/app/test_runtime_center_api.py`
- Modify: `src/copaw/kernel/query_execution_shared.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/routers/runtime_center_shared.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`

- [ ] **Step 1: Add a failing test that asserts decision and patch action payloads stay aligned across runtime-center surfaces**
- [ ] **Step 2: Run that test and confirm the current duplicated builders fail the shared-contract expectation**
- [ ] **Step 3: Add one shared runtime action-link module for decision and patch actions**
- [ ] **Step 4: Replace the duplicated action builder implementations in kernel/runtime query/router/overview code**
- [ ] **Step 5: Re-run the focused runtime-center tests**

### Task 4: Unify frontend runtime risk/status tag colors

**Files:**
- Create: `console/src/runtime/tagSemantics.ts`
- Create: `console/src/runtime/tagSemantics.test.ts`
- Modify: `console/src/pages/Chat/chatPageHelpers.tsx`
- Modify: `console/src/pages/AgentWorkbench/executionSeatPresentation.ts`
- Modify: `console/src/components/RuntimeCapabilitySurfaceCard.tsx`
- Modify: `console/src/runtime/executionPresentation.ts`
- Modify: additional runtime/chat/agent-workbench consumers that currently inline `statusColor()` / `riskColor()`

- [ ] **Step 1: Add a failing Vitest that captures the canonical runtime risk/status color mapping**
- [ ] **Step 2: Run the Vitest and verify it fails because the shared semantics module does not exist**
- [ ] **Step 3: Implement one shared runtime tag semantics module**
- [ ] **Step 4: Replace duplicated `statusColor()` and `riskColor()` implementations across the runtime/chat/agent workbench/capability surfaces with the shared module**
- [ ] **Step 5: Re-run the focused frontend tests**

### Task 5: Close the loop

**Files:**
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Run the full focused backend regression batch for capability-market/runtime-center/capability write surfaces**
- [ ] **Step 2: Run the focused frontend Vitest batch for runtime presentation consumers**
- [ ] **Step 3: Update `TASK_STATUS.md` with the actual tail-closure state**
- [ ] **Step 4: Only then report the closure with concrete verification output**
