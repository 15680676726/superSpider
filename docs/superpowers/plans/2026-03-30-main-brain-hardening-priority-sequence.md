# Main-Brain Hardening Priority Sequence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock CoPaw's main-brain architecture in the correct order: truth chain first, mode split second, continuity contract third, projection discipline fourth, long-run smoke last.

**Architecture:** Treat this as a hardening sequence, not a feature roadmap. Each phase exists to reduce one class of architectural regression before the next phase adds wider coverage. New capability work should stay behind these guardrails instead of racing ahead of them.

**Tech Stack:** Python, FastAPI, SQLite state services, pytest, TypeScript, Vitest

---

## Scope Boundary

- This plan is the execution order for `P0 -> P4`.
- It does not replace focused implementation plans such as:
  - `docs/superpowers/plans/2026-03-30-main-brain-cognitive-closure-implementation-plan.md`
  - `docs/superpowers/plans/2026-03-30-canonical-host-continuity-plan.md`
- The purpose here is to define the repo-wide hardening order and the gates between phases.
- If a new task does not clearly map to one of `P0-P4`, it should not start yet.

## File Map

- Modify: `TASK_STATUS.md`
  - Add the canonical `P0-P4` execution order.
- Modify: `tests/state/test_main_brain_hard_cut.py`
  - Lock root/frontdoor hard-cut regressions and write-chain boundary behavior.
- Modify: `tests/app/test_goals_api.py`
  - Keep leaf detail surfaces read-only.
- Modify: `tests/kernel/test_turn_executor.py`
  - Lock `chat` vs `orchestrate` routing behavior.
- Modify: `tests/kernel/test_main_brain_chat_service.py`
  - Lock pure-chat light-chain constraints and prompt/tool boundaries.
- Modify: `tests/app/runtime_center_api_parts/overview_governance.py`
  - Lock cockpit/operator projections without reintroducing write-side mutation.
- Modify: `tests/app/test_phase_next_autonomy_smoke.py`
  - Lock long-run multi-cycle continuity and unified runtime chain.
- Reference: `docs/superpowers/plans/2026-03-30-main-brain-cognitive-closure-implementation-plan.md`
- Reference: `docs/superpowers/plans/2026-03-30-canonical-host-continuity-plan.md`

### Task 1: P0 Truth-Chain And Write-Boundary Guardrails

**Files:**
- Modify: `tests/state/test_main_brain_hard_cut.py`
- Modify: `tests/app/test_goals_api.py`
- Modify: `src/copaw/app/_app.py` only if a hard-cut regression is still exposed

- [ ] **Step 1: Write the failing boundary tests**

Add tests for:
- root `/goals` frontdoor staying detail-only in the assembled app
- retired write frontdoors staying `404`
- goal detail and other read surfaces staying side-effect free
- chat writeback keeping new work in backlog until the operating-cycle chain materializes it

- [ ] **Step 2: Run the focused P0 tests**

Run: `python -m pytest tests/state/test_main_brain_hard_cut.py tests/app/test_goals_api.py -q`
Expected: FAIL if any retired write path or read-side mutation has regressed.

- [ ] **Step 3: Implement the minimal hard-cut fixes**

Required outcome:
- one canonical planning/write chain
- no retired write frontdoor revival
- read surfaces do not mutate truth

- [ ] **Step 4: Re-run the focused P0 tests**

Run: `python -m pytest tests/state/test_main_brain_hard_cut.py tests/app/test_goals_api.py -q`
Expected: PASS

### Task 2: P1 Chat-Mode Vs Orchestrate-Mode Isolation

**Files:**
- Modify: `tests/kernel/test_turn_executor.py`
- Modify: `tests/kernel/test_main_brain_chat_service.py`
- Modify: `src/copaw/kernel/turn_executor.py` only if routing isolation regresses
- Modify: `src/copaw/kernel/main_brain_chat_service.py` only if pure-chat light-chain constraints regress

- [ ] **Step 1: Write the failing mode-isolation tests**

Add tests for:
- `interaction_mode=auto` defaulting to pure chat unless execution intent is explicit
- pure chat not exposing execution-only system tools
- pure chat not inheriting execution-runtime side effects by default
- orchestration still entering the formal kernel/governance/evidence chain

- [ ] **Step 2: Run the focused P1 tests**

Run: `python -m pytest tests/kernel/test_turn_executor.py tests/kernel/test_main_brain_chat_service.py -q`
Expected: FAIL if chat/orchestrate boundaries have drifted.

- [ ] **Step 3: Implement the minimal routing and pure-chat fixes**

Required outcome:
- mode switch stays centralized in `KernelTurnExecutor`
- `MainBrainChatService` remains the lightweight chain
- execution-only capability exposure remains orchestrate-only

- [ ] **Step 4: Re-run the focused P1 tests**

Run: `python -m pytest tests/kernel/test_turn_executor.py tests/kernel/test_main_brain_chat_service.py -q`
Expected: PASS

### Task 3: P2 Canonical Continuity Contract

**Files:**
- Reference/Modify: `docs/superpowers/plans/2026-03-30-canonical-host-continuity-plan.md`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/task_review_projection.py`
- Modify: `src/copaw/app/runtime_chat_media.py`
- Modify: continuity-related regression tests in `tests/app/test_phase_next_autonomy_smoke.py`

- [ ] **Step 1: Write the failing continuity tests**

Add tests for:
- `work_context_id / environment_ref / control_thread_id / recovery checkpoint` surviving handoff and resume
- missing continuity anchors causing `blocked/fresh/human-assist`, not guessed resume
- `host_twin_summary` staying a canonical derived summary across consumers

- [ ] **Step 2: Run the focused P2 tests**

Run: `python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q -k "continuity or handoff or host"`
Expected: FAIL if continuity semantics are inconsistent across consumers.

- [ ] **Step 3: Implement the minimal continuity-contract fixes**

Required outcome:
- one canonical continuity contract
- no module-local resume dialects
- shared host summary across runtime/workflow/cron consumers

- [ ] **Step 4: Re-run the focused P2 tests**

Run: `python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q -k "continuity or handoff or host"`
Expected: PASS

### Task 4: P3 Projection Discipline

**Files:**
- Modify: `src/copaw/industry/report_synthesis.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `console/src/runtime/controlChainPresentation.ts`
- Modify: projection/cockpit tests

- [ ] **Step 1: Write the failing projection-discipline tests**

Add tests for:
- derived synthesis and cockpit projections staying read-only
- presenters not reordering truth semantics independently of the canonical chain
- projection payloads never becoming implicit write triggers

- [ ] **Step 2: Run the focused P3 tests**

Run: `python -m pytest tests/industry/test_report_synthesis.py tests/app/runtime_center_api_parts/overview_governance.py -q`
Expected: FAIL if projection logic has started to leak into truth mutation.

- [ ] **Step 3: Implement the minimal projection fixes**

Required outcome:
- projections remain derived read models
- cockpit and presenter layers consume canonical truth instead of recreating it

- [ ] **Step 4: Re-run the focused P3 tests**

Run: `python -m pytest tests/industry/test_report_synthesis.py tests/app/runtime_center_api_parts/overview_governance.py -q`
Expected: PASS

### Task 5: P4 Long-Run Smoke As Maturity Gate

**Files:**
- Modify: `tests/app/test_phase_next_autonomy_smoke.py`

- [ ] **Step 1: Write the failing long-run maturity smoke**

Add one gate suite that proves:
- multi-cycle planning/execution/report/replan stays on one canonical chain
- handoff/human-assist/resume stays on one control thread
- host switch and replay continuity remain attached to the same runtime truth

- [ ] **Step 2: Run the focused P4 smoke**

Run: `python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q`
Expected: FAIL until the full maturity gate is covered end to end.

- [ ] **Step 3: Implement the minimal glue needed for the smoke**

Required outcome:
- long-run smoke becomes a formal maturity gate, not an optional confidence run

- [ ] **Step 4: Re-run the focused P4 smoke**

Run: `python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q`
Expected: PASS

## Execution Order

1. Finish `P0` before starting `P1`.
2. Finish `P1` before widening continuity work in `P2`.
3. Do not treat `P3` as a UI polish task; it is a truth-discipline task.
4. Treat `P4` as the acceptance gate for the whole sequence.

## Immediate Start

- Start now with `P0`.
- First slice:
  - extend `tests/state/test_main_brain_hard_cut.py`
  - prove the assembled app keeps root `/goals` frontdoor detail-only
  - re-run the focused hard-cut suite before touching `P1`
