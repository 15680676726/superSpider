# Runtime Complete Tail Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining runtime tail work as one gated four-stage closure program, with no "done" claim until Runtime Center projector split, MCP lifecycle hardening, concurrency/child-run shell unification, and planning-shell/formal-planning implementation all complete together.

**Architecture:** Execute the work in strict sequence with hard stage exit criteria. Stage 1 continues Runtime Center read-collaborator extraction. Stage 2 hardens MCP reload lifecycle and scoped overlays. Stage 3 unifies shared-writer discipline and child execution cleanup. Stage 4 implements the documented formal planning slice without replacing CoPaw's truth chain.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite, pytest, Vitest, existing CoPaw `runtime_center / mcp / kernel / environments / compiler / industry / state` services.

---

## Scope Guard

This plan intentionally treats the following as one closure program:

- Runtime Center read-projector split phase 2
- MCP lifecycle hardening
- concurrency discipline and child-run shell unification
- planning shell and formal planning gap implementation

This plan does **not** allow stopping after any one of those stages and calling the overall program complete.

Stage checkpoint commits are allowed, but:

- `TASK_STATUS.md` and `API_TRANSITION_MAP.md` must continue to mark the overall closure program as open until the final closure gate passes
- only the final closure sweep may mark the program complete and merge it back to `main`

## File Structure

### New files expected during this program

- `src/copaw/app/runtime_center/work_context_projection.py`
  - Dedicated work-context read collaborator.
- `src/copaw/app/mcp/lifecycle_contract.py`
  - Typed MCP reload/dirty/swap state contracts, only if extending `runtime_contract.py` directly proves insufficient and the duplicate boundary is deleted before Stage 2 closes.
- `src/copaw/kernel/child_run_shell.py`
  - Shared child-run lifecycle/cleanup shell if extraction proves worthwhile.
- `src/copaw/compiler/planning/*`
  - Formal planning compiler package as already described in the planning-gap plan.

### Core existing files expected to change

- `src/copaw/app/runtime_center/state_query.py`
- `src/copaw/app/runtime_center/task_list_projection.py`
- `src/copaw/app/mcp/watcher.py`
- `src/copaw/app/mcp/manager.py`
- `src/copaw/app/mcp/runtime_contract.py`
- `src/copaw/environments/service.py`
- `src/copaw/environments/lease_service.py`
- `src/copaw/environments/host_event_recovery_service.py`
- `src/copaw/kernel/actor_worker.py`
- `src/copaw/kernel/actor_supervisor.py`
- `src/copaw/kernel/delegation_service.py`
- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/compiler/planning/*`
- `src/copaw/industry/service_lifecycle.py`
- `src/copaw/goals/service_compiler.py`
- `src/copaw/state/main_brain_service.py`
- runtime/industry/planning related tests
- `TASK_STATUS.md`
- `API_TRANSITION_MAP.md`

## Stage 1: Runtime Center Read-Projector Split Phase 2

**Files:**
- Create: `src/copaw/app/runtime_center/work_context_projection.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `tests/app/test_runtime_query_services.py`
- Modify: `tests/app/test_runtime_center_api.py`
- Modify: affected `tests/app/runtime_center_api_parts/*` work-context/runtime-center regressions as needed
- Modify: `docs/superpowers/specs/2026-04-02-runtime-complete-tail-closure-design.md`
- Modify: `TASK_STATUS.md`

- [x] **Step 1: Write/extend failing tests for extracted work-context reads**

Cover:

- `list_work_contexts`
- `count_work_contexts`
- `get_work_context_detail`
- task/task-detail payloads that still depend on shared work-context serialization

- [x] **Step 2: Run the focused runtime-query tests and confirm the extraction gap**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/app/test_runtime_query_services.py -k "work_context or projector" -q
```

- [x] **Step 3: Add `work_context_projection.py` and move all `list/count/detail work_context*` projection and serialization logic into it**

- [x] **Step 4: Refactor `RuntimeCenterStateQueryService` to delegate that slice**

- [x] **Step 5: Re-run focused runtime-query tests**

- [x] **Step 6: Re-run Runtime Center API-level regressions for the extracted work-context surface**

- [x] **Step 7: Update status/design checkpoint notes for Stage 1 while keeping the overall closure program open**

- [ ] **Step 8: Create an optional Stage 1 checkpoint commit**

## Stage 2: MCP Lifecycle Hardening

**Files:**
- Create or Modify: `src/copaw/app/mcp/lifecycle_contract.py`
- Modify: `src/copaw/app/mcp/watcher.py`
- Modify: `src/copaw/app/mcp/manager.py`
- Modify: `src/copaw/app/mcp/runtime_contract.py`
- Modify: `src/copaw/app/runtime_bootstrap_execution.py`
- Modify: `src/copaw/app/runtime_bootstrap_query.py`
- Modify: `tests/test_mcp_resilience.py`
- Modify: `tests/app/test_mcp_runtime_contract.py`
- Modify: `tests/app/test_runtime_bootstrap_helpers.py`
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`

- [x] **Step 1: Write/extend failing MCP lifecycle tests**

Cover:

- dirty-state tracking
- in-flight reload skipping semantics
- close/swap sequencing on success
- swap failure / close failure behavior
- scoped/additive overlay boundary

- [x] **Step 2: Run focused MCP tests to prove the lifecycle contract is incomplete**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_mcp_resilience.py tests/app/test_mcp_runtime_contract.py tests/app/test_runtime_bootstrap_helpers.py -q
```

- [x] **Step 3: Add the typed lifecycle contract and wire watcher/manager around it**

- [x] **Step 4: Resolve the ownership boundary with `runtime_contract.py`**

Allowed outcomes:

- extend `runtime_contract.py` and skip `lifecycle_contract.py`
- add `lifecycle_contract.py` but delete any duplicate lifecycle model/path from `runtime_contract.py`

- [x] **Step 5: Implement overlay/scoped mount boundary without reopening raw-dict lifecycle drift**

- [x] **Step 6: Re-run focused MCP/bootstrap tests**

- [x] **Step 7: Update status/docs checkpoint notes for Stage 2 while keeping the overall closure program open**

- [ ] **Step 8: Create an optional Stage 2 checkpoint commit**

## Stage 3: Concurrency Discipline Plus Child-Run Shell

**Files:**
- Create: `src/copaw/kernel/child_run_shell.py` (only if the extraction deletes real duplication)
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/lease_service.py`
- Modify: `src/copaw/environments/host_event_recovery_service.py`
- Modify: `src/copaw/kernel/actor_worker.py`
- Modify: `src/copaw/kernel/actor_supervisor.py`
- Modify: `src/copaw/kernel/delegation_service.py`
- Modify: `tests/environments/test_environment_registry.py`
- Modify: `tests/environments/test_host_event_recovery_service.py`
- Modify: `tests/kernel/test_actor_worker.py`
- Modify: `tests/kernel/test_actor_supervisor.py`
- Modify: `tests/kernel/test_query_execution_shared_split.py` if shared writer acquisition changes query-time coordination semantics
- Modify: `tests/app/test_runtime_center_task_delegation_api.py`
- Modify: `tests/app/test_phase_next_autonomy_smoke.py`
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`

- [x] **Step 1: Write/extend failing tests for shared writer reservation and unified child cleanup**

Cover:

- read-parallel / write-serialized expectations
- delegated child writer conflicts
- release/handoff continuity
- supervisor stop / cancel / failure cleanup

- [x] **Step 2: Run focused environment/worker/delegation tests**

- [x] **Step 3: Implement the explicit shared-writer contract**

- [x] **Step 4: Unify child-run cleanup shell across worker/supervisor/delegation**

- [x] **Step 5: Re-run focused tests plus one long-run smoke**

- [x] **Step 6: Update status/docs checkpoint notes for Stage 3 while keeping the overall closure program open**

- [ ] **Step 7: Create an optional Stage 3 checkpoint commit**

## Stage 4: Planning Shell Plus Formal Planning Gap

**Files:**
- Create/Modify: `src/copaw/compiler/planning/__init__.py`
- Create/Modify: `src/copaw/compiler/planning/models.py`
- Create/Modify: `src/copaw/compiler/planning/assignment_planner.py`
- Create/Modify: `src/copaw/compiler/planning/cycle_planner.py`
- Create/Modify: `src/copaw/compiler/planning/strategy_compiler.py`
- Create/Modify: `src/copaw/compiler/planning/report_replan_engine.py`
- Modify: `src/copaw/compiler/__init__.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/goals/service_compiler.py`
- Modify: `src/copaw/industry/service_context.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/predictions/service_core.py`
- Modify: `src/copaw/state/main_brain_service.py`
- Modify: `tests/compiler/test_planning_models.py`
- Modify: `tests/compiler/test_assignment_planner.py`
- Modify: `tests/compiler/test_cycle_planner.py`
- Modify: `tests/compiler/test_strategy_compiler.py`
- Modify: `tests/compiler/test_report_replan_engine.py`
- Modify: `tests/app/test_goals_api.py`
- Modify: `tests/app/test_predictions_api.py`
- Modify: `tests/app/test_runtime_bootstrap_split.py`
- Modify: `tests/state/test_strategy_memory_contract.py`
- Modify: `tests/kernel/test_assignment_envelope.py`
- Modify: `tests/industry/test_report_synthesis.py`
- Modify: `tests/industry/test_runtime_views_split.py`
- Modify: `tests/app/test_phase_next_autonomy_smoke.py`
- Modify: `docs/superpowers/specs/2026-04-01-formal-planning-capability-gap-design.md`
- Modify: `docs/superpowers/plans/2026-04-01-formal-planning-capability-gap-implementation-plan.md`
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `docs/superpowers/specs/2026-04-02-runtime-complete-tail-closure-design.md`

- [x] **Step 1: Reconcile the planning-gap implementation plan with current mainline code**

Stage 4 completion requires the full deliverable set from the formal-planning program, not a subset.

- [x] **Step 2: Build the planning compiler package contracts and typed models**

- [x] **Step 3: Implement assignment-local planning shell/envelope first**

- [x] **Step 4: Implement cycle planning second**

- [x] **Step 5: Implement strategy compilation third**

- [x] **Step 6: Implement report-to-replan outputs fourth**

- [x] **Step 7: Wire bootstrap, lifecycle, runtime views, predictions, and state services to the new planning outputs**

- [x] **Step 8: Run the full formal-planning test suite plus the phase-next smoke suite**

- [x] **Step 9: Update planning/status/docs checkpoint notes for Stage 4 while keeping the overall closure program open**

- [ ] **Step 10: Create an optional Stage 4 checkpoint commit**

## Final Closure Gate

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: any touched design/plan doc that still describes these four areas as active tails

- [ ] **Step 1: Run the full closure verification sweep**

Run:

```powershell
$env:PYTHONPATH='src'
python scripts/run_p0_runtime_terminal_gate.py
```

Expected:

- PASS as the repo's formal runtime gate

- [ ] **Step 2: Run the full closure verification sweep**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_mcp_resilience.py tests/app/test_mcp_runtime_contract.py tests/app/test_capability_skill_service.py tests/app/test_capability_catalog.py tests/environments/test_environment_registry.py tests/environments/test_host_event_recovery_service.py tests/kernel/test_runtime_events.py tests/app/test_runtime_query_services.py tests/app/test_capabilities_execution.py tests/app/test_operator_runtime_e2e.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_action_links.py tests/kernel/test_query_execution_shared_split.py tests/kernel/query_execution_environment_parts/confirmations.py tests/kernel/test_agent_profile_service.py tests/app/test_runtime_center_actor_api.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_phase_next_autonomy_smoke.py -q
```

- [ ] **Step 3: Run the full formal-planning regression suite**

Run:

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/compiler/test_planning_models.py tests/compiler/test_assignment_planner.py tests/compiler/test_cycle_planner.py tests/compiler/test_strategy_compiler.py tests/compiler/test_report_replan_engine.py tests/app/test_goals_api.py tests/app/test_predictions_api.py tests/app/test_runtime_bootstrap_split.py tests/state/test_strategy_memory_contract.py tests/kernel/test_assignment_envelope.py tests/industry/test_report_synthesis.py tests/industry/test_runtime_views_split.py tests/app/test_phase_next_autonomy_smoke.py -q
```

- [ ] **Step 4: Run the frontend workbench/runtime/planning tests touched by the program**

Run:

```powershell
npm exec vitest run ./src/pages/AgentWorkbench/useAgentWorkbench.test.tsx --root .
```

Workdir:

```text
D:\word\copaw\console
```

- [ ] **Step 5: Run the Runtime Center / Industry planning UI regressions**

Run:

```powershell
npm exec vitest run ./src/pages/RuntimeCenter/runtimeDetailDrawer.test.tsx ./src/pages/RuntimeCenter/viewHelpers.test.tsx ./src/pages/Industry/runtimePresentation.test.tsx --root .
```

- [ ] **Step 6: Run `git diff --check`**

- [ ] **Step 7: Update status/docs so these four items are no longer active tails for this program**

Required docs:

- `TASK_STATUS.md`
- `API_TRANSITION_MAP.md`
- `docs/superpowers/specs/2026-04-01-formal-planning-capability-gap-design.md`
- the historical runtime-contract hardening record for this program
- `docs/superpowers/plans/2026-04-01-formal-planning-capability-gap-implementation-plan.md`
- `docs/superpowers/specs/2026-04-02-runtime-complete-tail-closure-design.md`
- `docs/superpowers/plans/2026-04-02-runtime-complete-tail-closure-implementation-plan.md`

- [ ] **Step 8: Commit the final closure sweep**

- [ ] **Step 9: Merge back to `main`**
