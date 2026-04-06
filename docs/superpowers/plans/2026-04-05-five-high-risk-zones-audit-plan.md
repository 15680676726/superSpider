# Five High-Risk Zones Audit Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit the 5 highest-risk remaining areas after the runtime-closure pass and convert them into concrete pass/fail findings instead of vague concern.

**Architecture:** This is a truth-boundary and regression-risk audit, not a feature build. The work should stay focused on canonical-source integrity, live-surface semantics, encoding safety, proof-strength honesty, and the new knowledge-graph line.

**Tech Stack:** React + TypeScript, FastAPI + Python, Pytest, Vitest, repo docs

---

### Task 1: Audit Buddy profile source truth on Chat entry

**Files:**
- Inspect: `console/src/pages/Chat/index.tsx`
- Inspect: `console/src/runtime/buddyProfileBinding.ts`
- Inspect: `console/src/pages/Chat/runtimeTransportRequest.ts`
- Inspect: `console/src/pages/Industry/useIndustryPageState.ts`
- Test: `console/src/pages/Chat/runtimeTransport.test.ts`

- [ ] Verify whether Chat still treats `buddy_profile` query params or browser storage as runtime truth.
- [ ] Record the exact remaining fallback order.
- [ ] Decide whether the current behavior is acceptable compatibility read or a real truth leak.
- [ ] If it is a leak, define the exact cut line for removal and the regression tests that must exist.

### Task 2: Audit Buddy projection honesty and persona fragility

**Files:**
- Inspect: `src/copaw/kernel/buddy_projection_service.py`
- Inspect: `src/copaw/kernel/buddy_onboarding_service.py`
- Inspect: `src/copaw/kernel/main_brain_chat_service.py`
- Inspect: `src/copaw/kernel/query_execution_prompt.py`
- Test: `tests/kernel/test_buddy_projection_service.py`
- Test: `tests/kernel/test_buddy_onboarding_service.py`

- [ ] Verify there is no remaining path that fabricates current task / why now / single next action when canonical runtime focus is absent.
- [ ] Verify chat interaction no longer advances growth counters in places that should be runtime-outcome driven.
- [ ] Record any remaining duplicated persona formatting or garbled default copy.
- [ ] Mark which remaining issues are real bugs vs. fragility hotspots.

### Task 3: Audit Industry page complexity and Chinese text integrity

**Files:**
- Inspect: `console/src/pages/Industry/index.tsx`
- Inspect: `console/src/pages/Industry/index.test.tsx`
- Inspect: `console/src/pages/RuntimeCenter/actorPulse.ts`
- Inspect: `console/src/pages/Industry/useIndustryPageState.ts`

- [ ] Verify runtime cockpit remains the owning surface and legacy draft editing is truly secondary.
- [ ] Search for remaining garbled Chinese or encoding-fragile strings in the live product chain.
- [ ] Separate harmless historical text from user-facing runtime-path risk.
- [ ] Record which files still need dedicated encoding cleanup later.

### Task 4: Audit current_focus contract vs. legacy goal semantics

**Files:**
- Inspect: `console/src/pages/RuntimeCenter/actorPulse.ts`
- Inspect: `console/src/pages/RuntimeCenter/index.tsx`
- Inspect: `console/src/pages/Chat/pagePresentation.tsx`
- Inspect: `console/src/pages/AgentWorkbench/*`
- Inspect: `src/copaw/goals/*`
- Inspect: `src/copaw/compiler/*`

- [ ] Verify frontend live-surfaces now read `current_focus_*` as the canonical operator-facing focus contract.
- [ ] Identify where `goal_id / goal_title` still remain valid domain objects instead of legacy leakage.
- [ ] Record the exact boundary where compat read is still allowed.
- [ ] Flag the places most likely to regress focus semantics back into old goal-first UI behavior.

### Task 5: Audit proof strength and the new knowledge-graph line

**Files:**
- Inspect: `TASK_STATUS.md`
- Inspect: `tests/providers/test_live_provider_smoke.py`
- Inspect: `tests/routines/test_live_routine_smoke.py`
- Inspect: `tests/test_p0_runtime_terminal_gate.py`
- Inspect: `src/copaw/memory/knowledge_graph_models.py`
- Inspect: `tests/memory/test_knowledge_graph_models.py`

- [ ] Verify default regression, focused slice, collect-only, and opt-in live smoke are still clearly separated.
- [ ] Confirm no documentation drift has reintroduced fake-closure language.
- [ ] Audit whether the new knowledge-graph line is merely landed or actually integrated into current runtime truth flows.
- [ ] Record whether knowledge-graph work is an active regression risk or just a next-wave feature line.

---

## Output Format

Each task should end with:

- `Current status: green / yellow / red`
- `Why`
- `Real risk if left as-is`
- `Recommended next action`
