# External Executor Hard-Cut Final Closure Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the external-executor hard-cut against the `2026-04-20` design baseline so CoPaw no longer treats the local actor runtime and arbitrary external project intake as the formal execution mainline.

**Architecture:** Keep `CoPaw` as the only long-lived truth source for main-brain planning, assignment, evidence, and report closure. Move execution truth onto a formal `ExecutorRuntime` object chain and make local actor surfaces explicit read-only compatibility views while executor runtime, event writeback, and provider intake become the canonical execution path.

**Tech Stack:** Python 3.12, FastAPI, SQLite state store, pytest, Vitest, Runtime Center frontend, Codex App Server adapter

**Status Update (`2026-04-22`):** This closure plan is now complete at the formal execution mainline boundary. Fresh evidence lives in `TASK_STATUS.md` section `1.0.9`: focused regression `282 passed`, formal provider live smoke `1 passed`, repeated selected `L4` live cycles, and `python scripts/run_p0_runtime_terminal_gate.py` passed end-to-end. Compatibility leftovers remain tracked in `DEPRECATION_LEDGER.md` and are no longer part of the canonical execution path.

---

### Task 1: Formalize The Executor Truth Chain

**Files:**
- Modify: `src/copaw/state/models_executor_runtime.py`
- Modify: `src/copaw/state/executor_runtime_service.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/__init__.py`
- Test: `tests/state/test_executor_runtime_service.py`

- [ ] **Step 1: Write failing tests for thread/turn/event records**

- [ ] **Step 2: Run the focused executor state tests and verify they fail for missing formal objects or service methods**

- [ ] **Step 3: Add `ExecutorThreadBindingRecord`, `ExecutorTurnRecord`, and persisted `ExecutorEventRecord` to the executor state model**

- [ ] **Step 4: Extend `ExecutorRuntimeService` to create, update, and query the new formal objects without introducing a second truth source**

- [ ] **Step 5: Re-run executor state tests and make them pass**

- [ ] **Step 6: Commit the executor truth-chain slice**

### Task 2: Cut The Formal Assignment Write Path Over To Executor Runtime

**Files:**
- Modify: `src/copaw/kernel/runtime_coordination.py`
- Modify: `src/copaw/kernel/executor_event_ingest_service.py`
- Modify: `src/copaw/kernel/executor_event_writeback_service.py`
- Modify: `src/copaw/kernel/delegation_service.py`
- Modify: `src/copaw/app/runtime_bootstrap_execution.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Test: `tests/kernel/test_executor_event_ingest_service.py`
- Test: `tests/kernel/test_executor_event_writeback_service.py`
- Test: `tests/kernel/test_main_brain_executor_runtime_integration.py`

- [ ] **Step 1: Write failing tests that prove assignment dispatch and event writeback still depend on the local actor/delegation path**

- [ ] **Step 2: Run the targeted kernel tests and confirm the failures are on the formal cutover boundary**

- [ ] **Step 3: Route assignment start, runtime thread reuse, and normalized event writeback through the executor coordination path**

- [ ] **Step 4: Demote `delegation_service.py` from formal execution owner so it no longer acts as the primary assignment execution backend**

- [ ] **Step 5: Re-run the targeted kernel tests and make them pass**

- [ ] **Step 6: Commit the executor write-path cutover**

### Task 3: Demote Actor Runtime To Read-Only Compatibility

**Files:**
- Modify: `src/copaw/app/routers/runtime_center_routes_actor.py`
- Modify: `src/copaw/app/routers/runtime_center_payloads.py`
- Modify: `src/copaw/kernel/agent_profile_service.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `console/src/api/modules/runtimeCenter.ts`
- Modify: `console/src/hooks/useRuntimeExecutionPulse.ts`
- Modify: `console/src/components/RuntimeExecutionStrip.tsx`
- Modify: `console/src/pages/AgentWorkbench/useAgentWorkbench.ts`
- Modify: `console/src/pages/AgentWorkbench/sections/runtimePanels.tsx`
- Test: `tests/app/test_runtime_center_actor_api.py`
- Test: `console/src/components/RuntimeExecutionStrip.test.tsx`
- Test: `console/src/pages/AgentWorkbench/runtimePanels.test.tsx`
- Test: `console/src/pages/AgentWorkbench/useAgentWorkbench.test.tsx`

- [ ] **Step 1: Write failing tests for any remaining actor mutation route, route metadata, or frontend mutation hook that still looks canonical**

- [ ] **Step 2: Run the actor compatibility test slice and verify the failures are for the intended compatibility-only contract**

- [ ] **Step 3: Remove or retire canonical actor control actions and keep only explicit read-only compatibility detail/mailbox surfaces**

- [ ] **Step 4: Point frontend control affordances and capability governance to the executor-first or agent formal surfaces**

- [ ] **Step 5: Re-run backend and frontend actor compatibility tests and make them pass**

- [ ] **Step 6: Commit the actor demotion slice**

### Task 4: Supersede Project Donor Intake As A Formal Execution Surface

**Files:**
- Modify: `src/copaw/app/routers/capability_market.py`
- Modify: `src/copaw/capabilities/project_donor_contracts.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Test: `tests/capabilities/test_project_donor_contracts.py`
- Test: `tests/app/test_runtime_center_external_runtime_api.py`
- Test: `tests/app/test_capability_market_api.py`

- [ ] **Step 1: Write failing tests that prove arbitrary external-project compatibility install/search still presents itself as a canonical executor surface**

- [ ] **Step 2: Run the provider/compatibility cutover tests and verify the failures are on the intended compatibility boundary**

- [ ] **Step 3: Mark `/capability-market/projects/install*` and related taxonomy as compatibility/acquisition-only, and prevent them from being interpreted as formal executor-provider truth**

- [ ] **Step 4: Keep `ExecutorProvider / control_surface_kind / protocol_surface_kind` as the only formal execution-layer vocabulary in active read/write paths**

- [ ] **Step 5: Re-run provider/compatibility tests and make them pass**

- [ ] **Step 6: Commit the provider/compatibility supersede slice**

### Task 5: Update Status And Deprecation Contracts

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `DEPRECATION_LEDGER.md`
- Modify: `docs/superpowers/plans/2026-04-21-executor-runtime-hard-cut-completion.md`

- [ ] **Step 1: Re-read the hard-cut design, this closure plan, and the real code state**

- [ ] **Step 2: Update `TASK_STATUS.md` so Task 2/3/6/7 reflect the actual post-cutover state and exact remaining boundaries**

- [ ] **Step 3: Update `DEPRECATION_LEDGER.md` so actor runtime, delegation, and external-project intake entries reflect their new compatibility or retirement status**

- [ ] **Step 4: Update the older completion plan so it no longer overstates or misstates the final closure scope**

- [ ] **Step 5: Commit the docs and ledger sync**

### Task 6: Run Fresh Verification Across L1/L2/L3/L4

**Files:**
- Test: `tests/state/test_external_runtime_service.py`
- Test: `tests/state/test_executor_runtime_service.py`
- Test: `tests/kernel/test_executor_event_ingest_service.py`
- Test: `tests/kernel/test_executor_event_writeback_service.py`
- Test: `tests/kernel/test_main_brain_executor_runtime_integration.py`
- Test: `tests/app/test_runtime_center_executor_runtime_projection.py`
- Test: `tests/app/test_runtime_center_executor_runtime_bootstrap.py`
- Test: `tests/app/test_runtime_center_actor_api.py`
- Test: `tests/app/test_runtime_center_external_runtime_api.py`
- Test: `tests/app/test_capability_market_api.py`
- Test: `tests/app/test_runtime_canonical_flow_e2e.py`
- Test: `tests/app/test_operator_runtime_e2e.py`
- Test: `tests/app/test_phase_next_autonomy_smoke.py`
- Test: `console/src/components/RuntimeExecutionStrip.test.tsx`
- Test: `console/src/pages/AgentWorkbench/runtimePanels.test.tsx`
- Test: `console/src/pages/AgentWorkbench/useAgentWorkbench.test.tsx`

- [ ] **Step 1: Run fresh focused regression for executor state, kernel writeback, Runtime Center, actor compatibility, provider/compatibility boundaries, and touched frontend slices**

- [ ] **Step 2: Run default regression for the canonical runtime gate that covers the widened hard-cut surface**

- [ ] **Step 3: Run selected `L3` smoke covering real runtime front-door and Runtime Center readback after the cutover**

- [ ] **Step 4: Run selected `L4` soak covering repeated executor-runtime cycles or equivalent long-chain stability checks**

- [ ] **Step 5: Record exact commands, outputs, and acceptance level in `TASK_STATUS.md`**

- [ ] **Step 6: Commit verification updates**

### Task 7: Finish The Mainline Workflow

**Files:**
- Modify: touched files only if follow-up fixes are required from verification

- [ ] **Step 1: Ensure the worktree is clean except for intentional hard-cut changes**

- [ ] **Step 2: Re-run the final verification commands after any last fixes**

- [ ] **Step 3: Commit all remaining changes on `main`**

- [ ] **Step 4: Push `main` to `origin/main`**

- [ ] **Step 5: Confirm the worktree is clean**
