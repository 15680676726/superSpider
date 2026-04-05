# Runtime Closure Eight Issues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 8 confirmed runtime/Buddy/frontend/test gaps so the project no longer depends on hidden second entrances, local browser truth, fake closure narratives, or incomplete Buddy-runtime binding.

**Architecture:** Keep the current runtime-first architecture, but remove the remaining false seams. The fixes fall into six ownership groups: Buddy carrier binding, Buddy truth/projection, Buddy growth/persona/runtime refresh, Runtime Center and `/agents` IA cleanup, Industry/current-focus cleanup, and closure-test hardening with status/docs correction.

**Tech Stack:** FastAPI, Python services/state repositories, React + TypeScript + Vitest, Pytest

---

## File Ownership Map

### Group A: Buddy carrier binding and first-entry runtime binding

**Primary files**
- Modify: `console/src/pages/BuddyOnboarding/index.tsx`
- Modify: `console/src/pages/BuddyOnboarding/index.test.tsx`
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/useChatRuntimeState.ts`
- Modify: `console/src/pages/Chat/chatBindingRecovery.ts`
- Modify: `console/src/pages/Chat/runtimeTransportRequest.ts`
- Modify: `console/src/utils/runtimeChat.ts`
- Modify: `src/copaw/kernel/buddy_onboarding_service.py`
- Modify: `src/copaw/app/routers/buddy_routes.py`
- Test: `tests/app/test_buddy_cutover.py`

**Issues covered**
- Issue 1: onboarding generated `execution_carrier` is not formally bound into chat runtime

### Group B: Buddy profile source-of-truth unification

**Primary files**
- Modify: `console/src/runtime/buddyProfileBinding.ts`
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Industry/useIndustryPageState.ts`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/Chat/runtimeTransportRequest.ts`
- Modify: `src/copaw/kernel/buddy_projection_service.py`
- Modify: `src/copaw/app/routers/buddy_routes.py`
- Test: `console/src/pages/Industry/useIndustryPageState.test.tsx`
- Test: `console/src/pages/BuddyOnboarding/index.test.tsx`
- Test: `console/src/pages/Chat/runtimeTransport.test.ts`
- Test: `tests/kernel/test_buddy_projection_service.py`

**Issues covered**
- Issue 2: `buddy_profile_id` has multiple frontend truth sources

### Group C: Buddy growth, persona dedupe, and live companion refresh

**Primary files**
- Modify: `src/copaw/kernel/buddy_onboarding_service.py`
- Modify: `src/copaw/kernel/buddy_projection_service.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/BuddyPanel.tsx`
- Modify: `console/src/pages/Chat/BuddyCompanion.tsx`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/kernel/test_main_brain_runtime_context_buddy_prompt.py`
- Test: `tests/kernel/test_buddy_onboarding_service.py`
- Test: `tests/kernel/test_buddy_projection_service.py`
- Test: `console/src/pages/Chat/BuddyPanel.test.tsx`
- Test: `console/src/pages/Chat/BuddyCompanion.test.tsx`

**Issues covered**
- Issue 5: Buddy growth is driven by message ingress instead of real runtime closure
- Issue 6: Buddy surface can fabricate focus too easily
- Issue 7: Buddy persona rules are duplicated across chat and execution chains
- Issue 8: Buddy UI does not refresh with real turn-side changes

### Group D: Runtime Center and `/agents` second-entry retirement

**Primary files**
- Modify: `console/src/routes/index.tsx`
- Modify: `console/src/routes/resolveSelectedKey.test.ts`
- Modify: `console/src/pages/Chat/useRuntimeBinding.ts`
- Modify: `console/src/pages/Chat/useRuntimeBinding.test.ts`
- Modify: `console/src/pages/Agent/Workspace/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.test.tsx`
- Modify: `console/src/layouts/Sidebar.tsx`
- Modify: `console/src/layouts/Sidebar.test.tsx`

**Issues covered**
- Issue 3: `/agents` still acts as a hidden second formal entrance

### Group E: Industry runtime-first cleanup and current-focus contract cleanup

**Primary files**
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/Industry/useIndustryPageState.ts`
- Modify: `console/src/pages/Industry/IndustryRuntimeCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/actorPulse.ts`
- Modify: `console/src/pages/RuntimeCenter/text.ts`
- Modify: `console/src/pages/Chat/chatRuntimePresentation.ts`
- Modify: `console/src/pages/Chat/pagePresentation.tsx`
- Test: `console/src/pages/Industry/index.test.tsx`
- Test: `console/src/pages/RuntimeCenter/index.test.tsx`

**Issues covered**
- Issue 4: Industry page still mixes runtime cockpit and legacy draft editor
- Issue 5b: frontend focus still falls back to `goal_*` semantics instead of `current_focus_*`

### Group F: Closure-test hardening and status correction

**Primary files**
- Modify: `tests/app/test_runtime_canonical_flow_e2e.py`
- Modify: `tests/app/test_phase_next_autonomy_smoke.py`
- Modify: `tests/app/test_operator_runtime_e2e.py`
- Modify: `tests/app/test_mcp_runtime_contract.py`
- Modify: `tests/app/test_cron_executor.py`
- Modify: `tests/app/test_runtime_lifecycle.py`
- Modify: `tests/providers/test_live_provider_smoke.py`
- Modify: `tests/routines/test_live_routine_smoke.py`
- Modify: `tests/test_p0_runtime_terminal_gate.py`
- Modify: `TASK_STATUS.md`

**Issues covered**
- Issue 6: fake closure claims around canonical e2e / phase-next / automation
- Issue 7b: MCP / scheduler / live-smoke truth gaps

---

### Task 1: Formal Buddy carrier-to-chat binding

**Files:**
- Modify: `console/src/pages/BuddyOnboarding/index.tsx`
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/useChatRuntimeState.ts`
- Modify: `console/src/pages/Chat/chatBindingRecovery.ts`
- Modify: `console/src/utils/runtimeChat.ts`
- Modify: `src/copaw/kernel/buddy_onboarding_service.py`
- Modify: `src/copaw/app/routers/buddy_routes.py`
- Test: `tests/app/test_buddy_cutover.py`
- Test: `console/src/pages/BuddyOnboarding/index.test.tsx`

- [ ] Write failing tests that prove Buddy onboarding must open the generated execution carrier/control thread, not just `/chat?buddy_session=...&buddy_profile=...`.
- [ ] Run the targeted tests and confirm the failure is about missing carrier/thread binding.
- [ ] Implement a formal carrier binding handoff from onboarding confirm response to chat entry.
- [ ] Ensure the produced chat route/thread metadata carries the real control thread / industry instance / execution-core role.
- [ ] Re-run targeted backend and frontend tests for the cutover path.

### Task 2: Unify Buddy profile truth

**Files:**
- Modify: `console/src/runtime/buddyProfileBinding.ts`
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Industry/useIndustryPageState.ts`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `src/copaw/kernel/buddy_projection_service.py`
- Test: `console/src/pages/Industry/useIndustryPageState.test.tsx`
- Test: `console/src/pages/Chat/runtimeTransport.test.ts`
- Test: `tests/kernel/test_buddy_projection_service.py`

- [ ] Write failing tests for the mismatched Buddy read/write source cases.
- [ ] Run the tests and capture the failing profile-resolution behavior.
- [ ] Remove `localStorage` as runtime truth; keep it, if needed, as a soft cache only.
- [ ] Make Buddy surface loading, Industry protected-carrier logic, and runtime payload building all consume the same canonical profile source.
- [ ] Re-run targeted tests for Chat, Industry, and projection behavior.

### Task 3: Fix Buddy growth, focus truth, persona dedupe, and live refresh

**Files:**
- Modify: `src/copaw/kernel/buddy_onboarding_service.py`
- Modify: `src/copaw/kernel/buddy_projection_service.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/BuddyPanel.tsx`
- Modify: `console/src/pages/Chat/BuddyCompanion.tsx`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/kernel/test_main_brain_runtime_context_buddy_prompt.py`
- Test: `tests/kernel/test_buddy_onboarding_service.py`
- Test: `tests/kernel/test_buddy_projection_service.py`

- [ ] Write failing tests for: growth-before-execution, duplicated persona rules, and stale Buddy UI after chat turns.
- [ ] Run tests and verify the failures are real behavior gaps.
- [ ] Move Buddy growth/accounting to formal runtime outcomes or accepted interaction checkpoints rather than raw ingress only.
- [ ] Stop fabricating strong “current task / why now / next action” summaries when no canonical runtime focus exists; degrade honestly.
- [ ] Extract a shared Buddy persona builder so chat and execution chains consume one contract.
- [ ] Trigger Buddy surface refresh/invalidation on relevant chat-side completion events.
- [ ] Re-run targeted backend and frontend Buddy tests.

### Task 4: Retire `/agents` as a second entrance

**Files:**
- Modify: `console/src/routes/index.tsx`
- Modify: `console/src/pages/Chat/useRuntimeBinding.ts`
- Modify: `console/src/pages/Agent/Workspace/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/layouts/Sidebar.tsx`
- Test: `console/src/routes/resolveSelectedKey.test.ts`
- Test: `console/src/pages/Chat/useRuntimeBinding.test.ts`
- Test: `console/src/pages/RuntimeCenter/index.test.tsx`
- Test: `console/src/layouts/Sidebar.test.tsx`

- [ ] Write failing tests that prove `/agents` is still acting like a second formal home.
- [ ] Run the tests to verify current behavior.
- [ ] Change navigation so Runtime Center remains the owning surface and `/agents` becomes a detail-only view or direct record route, per current architecture.
- [ ] Remove leftover redirects and path builders that still treat `/agents` as the workbench home.
- [ ] Re-run targeted route/sidebar/runtime-center tests.

### Task 5: Clean up Industry page and current-focus contract

**Files:**
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/Industry/useIndustryPageState.ts`
- Modify: `console/src/pages/Industry/IndustryRuntimeCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/actorPulse.ts`
- Modify: `console/src/pages/RuntimeCenter/text.ts`
- Modify: `console/src/pages/Chat/chatRuntimePresentation.ts`
- Modify: `console/src/pages/Chat/pagePresentation.tsx`
- Test: `console/src/pages/Industry/index.test.tsx`
- Test: `console/src/pages/RuntimeCenter/index.test.tsx`

- [ ] Write failing tests for legacy `goal_*` fallback exposure and Industry draft/runtime dual-mind behavior.
- [ ] Run the tests and confirm the failures line up with the audited gaps.
- [ ] Reduce or isolate the old draft/preview/bootstrap editor so Industry reads as a runtime-first surface.
- [ ] Make focus presentation consume `current_focus_*` as canonical truth and remove legacy `goal_title / goal_id` fallback where the new contract exists.
- [ ] Re-run targeted Industry and Runtime Center tests.

### Task 6: Harden closure tests and correct status claims

**Files:**
- Modify: `tests/app/test_runtime_canonical_flow_e2e.py`
- Modify: `tests/app/test_phase_next_autonomy_smoke.py`
- Modify: `tests/app/test_operator_runtime_e2e.py`
- Modify: `tests/app/test_mcp_runtime_contract.py`
- Modify: `tests/app/test_cron_executor.py`
- Modify: `tests/app/test_runtime_lifecycle.py`
- Modify: `tests/test_p0_runtime_terminal_gate.py`
- Modify: `TASK_STATUS.md`

- [ ] Write or strengthen tests so canonical flow no longer relies on a fake mid-chain query service to claim full closure.
- [ ] Do the same for phase-next long-run smoke, MCP contract, and cron/automation launch-contract coverage.
- [ ] Run each targeted test suite and ensure failures demonstrate the current fake-closure gaps before fixing.
- [ ] Update the tests to either use stronger production wiring or narrow the claims to what is actually being proven.
- [ ] Correct `TASK_STATUS.md` so claims match the strengthened evidence.
- [ ] Re-run all targeted Python suites used as proof.

### Task 7: Verify gated live smoke boundaries honestly

**Files:**
- Modify: `tests/providers/test_live_provider_smoke.py`
- Modify: `tests/routines/test_live_routine_smoke.py`
- Modify: `TASK_STATUS.md`

- [ ] Review the live smoke gates and ensure documentation clearly separates “checked-in test exists”, “gated live smoke exists”, and “default CI proof exists”.
- [ ] Add or tighten assertions/documentation so skipped live tests cannot be mistaken for default regression coverage.
- [ ] Re-run the relevant collect/skip test commands and record the exact outcome.

### Task 8: Final verification matrix

**Files:**
- Reuse only files already touched above

- [ ] Run the full targeted backend verification matrix for Buddy, runtime canonical flow, phase-next, lifecycle/cron, and MCP.
- [ ] Run the full targeted frontend verification matrix for Buddy, routes, Runtime Center, Industry, and Sidebar.
- [ ] Run `npm --prefix console run build`.
- [ ] Confirm no open issue still depends on hidden fake services, hidden second entrances, or browser-local truth.

