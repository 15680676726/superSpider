# Execution Graph Projection Complete Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining execution-graph gap so canonical `backlog / cycle / assignment / report / work_context / runtime_outcome` truth is durably projected into the formal memory graph from canonical write paths instead of scattered business entry points.

**Architecture:** Move execution graph projection ownership to canonical `state` services plus shared `memory` builders. Business-layer `industry/bootstrap/onboarding` flows should keep writing canonical state only; graph projection must happen automatically when canonical state mutates. Raw report graph writeback should no longer be owned by report synthesis.

**Tech Stack:** Python, Pydantic, SQLite-backed state repositories, truth-first memory graph, pytest.

---

## Scope Summary

- Canonical objects already exist and are the formal execution truth:
  - `BacklogItemRecord`
  - `OperatingCycleRecord`
  - `AssignmentRecord`
  - `AgentReportRecord`
  - `WorkContextRecord`
- The current formal gap is not the runtime chain itself.
- The real gap is that canonical execution truth is only partially projected into the memory graph:
  - `report -> evidence` exists
  - `runtime_outcome -> failure/recovery` exists
  - `backlog / cycle / assignment / work_context` graph nodes are missing or incomplete
  - `assignment -> report`, `assignment -> cycle`, `backlog -> assignment`, `backlog -> cycle`, `work_context` anchor edges are missing
- Complete closure requires moving graph projection to canonical write services.

## Required Formal Graph Contract

### Node Types

- `backlog`
- `cycle`
- `assignment`
- `report`
- `work_context`
- `runtime_outcome`

### Required Relations

- `backlog belongs_to cycle`
- `backlog produces assignment`
- `assignment belongs_to cycle`
- `assignment belongs_to work_context`
- `assignment produces report`
- `report belongs_to work_context`
- `runtime_outcome belongs_to work_context`

### Status Expectations

- Backlog node status tracks canonical backlog status:
  - `open`
  - `selected`
  - `materialized`
  - `completed`
- Cycle node status tracks canonical cycle status:
  - `planned`
  - `active`
  - `review`
  - `completed`
- Assignment node status tracks canonical assignment status:
  - `planned`
  - `queued`
  - `running`
  - `waiting-report`
  - `completed`
  - `failed`
- Report node status tracks canonical report status:
  - `recorded`
  - `processed`
- Work-context node status tracks canonical work-context status:
  - `active`
  - `paused`
  - `completed`
  - `archived`

### Invalidation Requirements

- Projection must invalidate stale relations when canonical links move.
- At minimum:
  - old `backlog -> cycle`
  - old `backlog -> assignment`
  - old `assignment -> cycle`
  - old `assignment -> work_context`
  - old `assignment -> report`
  - old `report -> work_context`
  - old `runtime_outcome -> work_context`

## File Ownership

### Memory / Graph Layer

**Modify:**
- `src/copaw/memory/knowledge_graph_models.py`
- `src/copaw/memory/knowledge_writeback_service.py`
- `src/copaw/memory/knowledge_graph_service.py`

**Responsibility:**
- add missing execution node types
- add shared projection builders
- provide stable relation ids and invalidation helpers
- expose graph projection API for canonical state services

### Canonical State Layer

**Modify:**
- `src/copaw/state/main_brain_service.py`
- `src/copaw/state/work_context_service.py`

**Responsibility:**
- make canonical state mutators own projection timing
- remove dependence on business-layer manual graph writeback
- project canonical execution truth from services that already own the write paths

### Runtime Wiring Layer

**Modify:**
- `src/copaw/industry/service_context.py`
- `src/copaw/app/runtime_bootstrap_domains.py`
- `src/copaw/app/runtime_service_graph.py`

**Responsibility:**
- inject the graph projection dependency into canonical services
- keep one shared graph projection path in runtime assembly

### Industry / Synthesis Boundary

**Modify:**
- `src/copaw/industry/report_synthesis.py`
- `src/copaw/industry/service_report_closure.py`

**Responsibility:**
- remove raw report graph ownership from report synthesis
- keep synthesis focused on summary/replan/follow-up decisions
- preserve knowledge writeback summary compatibility only where still needed

### Tests

**Modify or create:**
- `tests/memory/test_knowledge_writeback_service.py`
- `tests/memory/test_knowledge_graph_service.py`
- `tests/state/test_execution_graph_projection_services.py`
- `tests/industry/test_report_synthesis.py`
- `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- `tests/app/industry_api_parts/runtime_updates.py`
- `tests/app/test_startup_recovery.py`
- `tests/app/test_runtime_center_memory_api.py`
- `tests/kernel/test_execution_knowledge_writeback.py`
- `tests/app/test_buddy_onboarding_activation.py`
- `tests/kernel/test_buddy_onboarding_service.py`

### Docs

**Modify:**
- `DATA_MODEL_DRAFT.md`
- `TASK_STATUS.md`

---

### Task 1: Document The Complete Closure Contract

**Files:**
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `TASK_STATUS.md`
- Create: `docs/superpowers/plans/2026-04-14-execution-graph-projection-complete-closure.md`

- [ ] **Step 1: Write the implementation plan document**

Add the full execution-graph closure plan, including canonical ownership, required node types, required relation directions, invalidation rules, and test matrix.

- [ ] **Step 2: Update `DATA_MODEL_DRAFT.md`**

Add the execution graph projection contract:
- canonical write ownership
- node ids
- edge directions
- `work_context` graph node
- raw report projection ownership moving to canonical report write path

- [ ] **Step 3: Update `TASK_STATUS.md`**

Record:
- why the earlier understanding was incomplete
- what the real gap is
- what this closure changes
- what verification commands must pass

### Task 2: Add Shared Execution Projection Builders

**Files:**
- Modify: `src/copaw/memory/knowledge_graph_models.py`
- Modify: `src/copaw/memory/knowledge_writeback_service.py`
- Modify: `src/copaw/memory/knowledge_graph_service.py`
- Test: `tests/memory/test_knowledge_writeback_service.py`
- Test: `tests/memory/test_knowledge_graph_service.py`

- [ ] **Step 1: Add missing `work_context` node type**

Update `knowledge_graph_models.py` so `work_context` is a first-class execution node kind.

- [ ] **Step 2: Add execution projection builders**

Extend `KnowledgeWritebackService` with shared builders for:
- backlog nodes and links
- cycle nodes and links
- assignment nodes and links
- work-context nodes
- report anchor links
- runtime outcome work-context anchors

- [ ] **Step 3: Add stale relation invalidation helpers**

Support invalidating prior relation ids when canonical link targets change.

- [ ] **Step 4: Expose projection methods through `KnowledgeGraphService`**

Add thin wrapper methods so canonical services can request execution projection without touching writeback internals directly.

- [ ] **Step 5: Add focused tests**

Add tests covering:
- node type support
- relation generation
- invalidation generation
- work-context anchor projection

### Task 3: Move Projection Ownership To Canonical State Services

**Files:**
- Modify: `src/copaw/state/main_brain_service.py`
- Modify: `src/copaw/state/work_context_service.py`
- Test: `tests/state/test_execution_graph_projection_services.py`

- [ ] **Step 1: Inject optional graph projection dependency**

Add optional constructor dependency to:
- `BacklogService`
- `OperatingCycleService`
- `AssignmentService`
- `AgentReportService`
- `WorkContextService`

Dependency must default to `None` so unrelated construction sites keep working.

- [ ] **Step 2: Project backlog mutations**

Backlog canonical writes must project:
- seed/bootstrap backlog
- generated backlog
- schedule backlog
- selected backlog
- materialized backlog
- completed backlog

- [ ] **Step 3: Project cycle mutations**

Cycle canonical writes must project:
- cycle start
- cycle link updates
- cycle reconcile status

- [ ] **Step 4: Project assignment mutations**

Assignment canonical writes must project:
- ensured assignments
- reconciled assignments
- evidence attachment where relevant metadata changes node summary/status

- [ ] **Step 5: Project reports from canonical report write path**

`AgentReportService.record_task_terminal_report(...)` must own raw report graph projection.

- [ ] **Step 6: Project work-context writes**

`WorkContextService.ensure_context(...)` must upsert the formal work-context graph node.

- [ ] **Step 7: Add service-level tests**

Add state tests proving canonical service mutation produces graph projection automatically.

### Task 4: Remove Raw Report Graph Ownership From Synthesis

**Files:**
- Modify: `src/copaw/industry/report_synthesis.py`
- Modify: `src/copaw/industry/service_report_closure.py`
- Test: `tests/industry/test_report_synthesis.py`

- [ ] **Step 1: Separate raw report projection from synthesis**

Report synthesis must stop being the owner of raw report graph writeback.

- [ ] **Step 2: Preserve synthesis summary contract where needed**

If public/read surfaces still rely on `knowledge_writeback` summary fields, keep only the summary contract that belongs to synthesis itself.

- [ ] **Step 3: Update tests**

Tests must prove:
- synthesis still drives replan/follow-up output
- raw report graph projection no longer depends on synthesis entry

### Task 5: Wire Runtime Assembly To The Canonical Projection Path

**Files:**
- Modify: `src/copaw/industry/service_context.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Test: `tests/app/test_runtime_bootstrap_split.py`
- Test: `tests/app/test_runtime_bootstrap_helpers.py`

- [ ] **Step 1: Create one shared runtime graph projection dependency**

Use the existing shared knowledge-graph services already assembled in runtime bootstrap.

- [ ] **Step 2: Pass the dependency into canonical state services**

Backlog/cycle/assignment/report/work-context services must receive the same shared graph projector.

- [ ] **Step 3: Keep runtime bindings single-path**

Do not create a second graph write path in `industry` runtime bindings.

- [ ] **Step 4: Update wiring tests**

Prove the assembled app binds one graph projection dependency all the way through canonical services.

### Task 6: Verify Business Entrypoints Close Automatically

**Files:**
- Modify: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Modify: `tests/app/industry_api_parts/runtime_updates.py`
- Modify: `tests/app/test_startup_recovery.py`
- Modify: `tests/app/test_runtime_center_memory_api.py`
- Modify: `tests/app/test_buddy_onboarding_activation.py`
- Modify: `tests/kernel/test_buddy_onboarding_service.py`
- Modify: `tests/kernel/test_execution_knowledge_writeback.py`

- [ ] **Step 1: Add bootstrap execution-graph assertions**

Verify bootstrap-created backlog/cycle/assignment graph nodes and relations exist.

- [ ] **Step 2: Add runtime update assertions**

Verify chat writeback, cycle rollover, report follow-up backlog, and report closure all keep the execution graph consistent.

- [ ] **Step 3: Add restart recovery assertions**

Verify relation views survive restart/reload with correct canonical links.

- [ ] **Step 4: Add onboarding assertions**

Verify buddy onboarding execution scaffold enters the same graph projection path.

- [ ] **Step 5: Add runtime outcome work-context assertions**

Verify work-context anchored runtime outcomes become formal graph truth.

### Task 7: Final Verification

**Files:**
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Run focused memory/state tests**

Run:
`python -m pytest tests/memory/test_knowledge_writeback_service.py tests/memory/test_knowledge_graph_service.py tests/state/test_execution_graph_projection_services.py -q`

- [ ] **Step 2: Run focused industry/runtime tests**

Run:
`python -m pytest tests/industry/test_report_synthesis.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py tests/app/test_startup_recovery.py tests/app/test_runtime_center_memory_api.py -q`

- [ ] **Step 3: Run onboarding/runtime outcome tests**

Run:
`python -m pytest tests/app/test_buddy_onboarding_activation.py tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_execution_knowledge_writeback.py -q`

- [ ] **Step 4: Update docs with landed status**

Write the final landed closure summary into `TASK_STATUS.md` and the formal object/graph contract into `DATA_MODEL_DRAFT.md`.

- [ ] **Step 5: Commit in reviewable batches**

Recommended commit split:
- commit 1: memory graph contract + builders
- commit 2: canonical state service projection ownership
- commit 3: synthesis/wiring cleanup + tests + docs
