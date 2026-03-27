# Runtime Surface Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the stage-2 structural cleanup by decomposing the remaining runtime projection and large UI surface files so CoPaw no longer keeps core runtime read logic and operator surfaces trapped inside a few giant mixed-responsibility modules.

**Architecture:** Extract backend runtime projection helpers into shared, typed modules, split `query_execution_shared.py` by responsibility instead of continuing to pile more orchestration helpers into one file, and break the Chat and AgentWorkbench surfaces into focused hooks/components that consume shared presentation helpers instead of carrying page-local runtime assembly logic.

**Tech Stack:** Python 3, FastAPI, Pydantic, pytest, TypeScript, React, Vitest

---

### Task 1: Pin the runtime projection contract with tests

**Files:**
- Create: `tests/app/test_runtime_projection_contracts.py`
- Modify: `tests/app/test_runtime_center_api.py`

- [ ] **Step 1: Add a failing backend test for shared runtime routes and task-review projection helpers**
- [ ] **Step 2: Run the focused pytest command and verify the new expectations fail before implementation**
- [ ] **Step 3: Extend the existing runtime-center API test coverage to confirm the refactor preserves the current read surface**

### Task 2: Split backend runtime projection helpers out of `state_query.py`

**Files:**
- Create: `src/copaw/utils/runtime_routes.py`
- Create: `src/copaw/app/runtime_center/task_review_projection.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `src/copaw/kernel/query_execution_shared.py`

- [ ] **Step 1: Introduce one shared runtime route helper module for task/goal/agent/decision/schedule/work-context routes**
- [ ] **Step 2: Introduce one shared task-review projection module for trace IDs, evidence serialization, review payload assembly, and chat-thread extraction**
- [ ] **Step 3: Rewire runtime-center state query, runtime overview, and query-execution call sites to the new helpers without changing the API contract**
- [ ] **Step 4: Re-run the focused runtime projection/backend API tests**

### Task 3: Split `query_execution_shared.py` by responsibility

**Files:**
- Create: `src/copaw/kernel/query_execution_writeback.py`
- Create: `src/copaw/kernel/query_execution_confirmation.py`
- Modify: `src/copaw/kernel/query_execution_shared.py`
- Test: `tests/kernel/test_query_execution_shared_split.py`

- [ ] **Step 1: Add a failing kernel-level test that imports the extracted writeback and confirmation helpers through the public shared flow**
- [ ] **Step 2: Run the focused pytest command and confirm the extraction seam does not exist yet**
- [ ] **Step 3: Move chat-writeback planning helpers and risky confirmation helpers into dedicated modules**
- [ ] **Step 4: Keep `query_execution_shared.py` as orchestration glue only, with imports into the extracted helper families**
- [ ] **Step 5: Re-run the kernel/query tests**

### Task 4: Split AgentWorkbench runtime surface

**Files:**
- Create: `console/src/pages/AgentWorkbench/sections/taskPanels.tsx`
- Create: `console/src/pages/AgentWorkbench/sections/runtimePanels.tsx`
- Create: `console/src/pages/AgentWorkbench/sections/detailPanels.tsx`
- Modify: `console/src/pages/AgentWorkbench/pageSections.tsx`
- Modify: `console/src/pages/AgentWorkbench/index.tsx`
- Test: `console/src/pages/AgentWorkbench/pageSections.test.tsx`

- [ ] **Step 1: Add a failing frontend test that renders the extracted workbench sections through the canonical page entry**
- [ ] **Step 2: Run the focused Vitest command and verify the sections are not yet decomposed**
- [ ] **Step 3: Move task/runtime/detail section components out of `pageSections.tsx` while preserving exports used by the page**
- [ ] **Step 4: Keep `pageSections.tsx` as the compatibility/export surface instead of the implementation dump**
- [ ] **Step 5: Re-run the focused AgentWorkbench test**

### Task 5: Split Chat runtime surface

**Files:**
- Create: `console/src/pages/Chat/useRuntimeBinding.ts`
- Create: `console/src/pages/Chat/useChatMedia.ts`
- Create: `console/src/pages/Chat/ChatRuntimeSidebar.tsx`
- Modify: `console/src/pages/Chat/index.tsx`
- Test: `console/src/pages/Chat/useRuntimeBinding.test.ts`

- [ ] **Step 1: Add a failing frontend test for the extracted runtime-binding helper**
- [ ] **Step 2: Run the focused Vitest command and verify the helper does not exist yet**
- [ ] **Step 3: Move runtime binding/bootstrap logic and media draft orchestration into focused hooks, and move sidebar rendering into a component**
- [ ] **Step 4: Keep `Chat/index.tsx` as page composition and wiring, not the place where every runtime concern lives**
- [ ] **Step 5: Re-run the focused Chat test**

### Task 6: Close the loop

**Files:**
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Run the focused backend regression batch for runtime-center/query-execution surfaces**
- [ ] **Step 2: Run the focused frontend Vitest batch for AgentWorkbench/Chat/runtime presentation surfaces**
- [ ] **Step 3: Update `TASK_STATUS.md` with the actual decomposition state and remaining high-order debt**
- [ ] **Step 4: Only then report completion with concrete verification output**
