# Closure Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the highest-confidence truth gaps confirmed in `46问题文档.md` without adding new parallel truth sources.

**Architecture:** Fix the closure gaps from the write path inward: first harden `HumanAssistTask` verification semantics, then remove active legacy `goal/schedule` writebacks from industry runtime, then eliminate read-side truth fabrication and governance bypasses, and finally align API/frontend/doc surfaces to the corrected contracts. Each task owns a disjoint write set.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite state repositories, Vitest, pytest

---

### Task 1: Harden HumanAssist Verification Semantics

**Files:**
- Modify: `src/copaw/state/human_assist_task_service.py`
- Modify: `src/copaw/state/models_core.py`
- Modify: `src/copaw/state/models_goals_tasks.py`
- Test: `tests/state/test_human_assist_task_service.py`
- Test: `tests/app/test_runtime_human_assist_tasks_api.py`

- [ ] Add failing tests for `evidence_verified` and `state_change_verified` so plain text cannot pass without the required evidence/state contract.
- [ ] Add a failing test that `verification_evidence_refs` persists accepted verification evidence.
- [ ] Implement acceptance-mode branching in `HumanAssistTaskService.verify_task(...)`.
- [ ] Implement persistence of `verification_evidence_refs` and mode-specific verification payload.
- [ ] Decide and encode evidence-ledger failure semantics explicitly; do not silently downgrade without state evidence.
- [ ] Run focused tests for state and API human-assist coverage.

### Task 2: Remove Legacy Goal Dispatch From Industry Bootstrap/Kickoff

**Files:**
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_activation.py`
- Modify: `src/copaw/state/models_industry.py`
- Modify: `src/copaw/state/models_reporting.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/test_phase_next_autonomy_smoke.py`

- [ ] Add failing tests that bootstrap/kickoff do not require `goal/schedule` dispatch to activate an instance.
- [ ] Add failing tests that no new `goal_ids/schedule_ids` truth is written during bootstrap/kickoff.
- [ ] Refactor public activation flags so `auto_activate` no longer implies legacy goal dispatch.
- [ ] Route kickoff/auto-resume through backlog/cycle/assignment-native execution.
- [ ] Remove or neutralize persistent `goal_ids/schedule_ids` / `active_goal_ids` write paths that act as live truth.
- [ ] Run focused industry bootstrap/lifecycle smoke tests.

### Task 3: Remove Goal-Based Runtime Focus Writeback And Read-Side Fabrication

**Files:**
- Modify: `src/copaw/industry/service_team_runtime.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/industry/test_runtime_views_split.py`

- [ ] Add failing tests that runtime focus is not written as `goal` when assignment/task truth exists.
- [ ] Add failing tests that read models do not fabricate `current_focus_*` from selected assignment/backlog when execution truth is empty.
- [ ] Remove `goal_id/goal_title -> current_focus_kind="goal"` runtime sync behavior.
- [ ] Remove read-side fallback that invents `execution.current_focus_*`.
- [ ] Run focused runtime-view and industry runtime tests.

### Task 4: Unify DecisionRequest / Acquisition Governance Paths

**Files:**
- Modify: `src/copaw/kernel/persistence.py`
- Modify: `src/copaw/learning/runtime_core.py`
- Modify: `src/copaw/learning/acquisition_runtime.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_actor.py`
- Test: `tests/app/test_learning_api.py`
- Test: `tests/app/test_runtime_center_api.py`

- [ ] Add failing tests that acquisition approval/reject flows use the canonical decision path rather than learning-specific special cases.
- [ ] Refactor learning/acquisition producers to stop constructing free-form `DecisionRequestRecord` bypasses where the kernel seam should own them.
- [ ] Remove Runtime Center actor-route special handling that bypasses canonical review flow for acquisition approvals.
- [ ] Run focused decision/governance API tests.

### Task 5: Remove API/Frontend Focus Truth Patching And Local Runtime Truth Derivation

**Files:**
- Modify: `src/copaw/app/routers/runtime_center_routes_industry.py`
- Modify: `src/copaw/industry/view_service.py`
- Modify: `console/src/api/modules/industry.ts`
- Modify: `console/src/pages/Industry/industryPagePresentation.ts`
- Modify: `console/src/pages/AgentWorkbench/useAgentWorkbench.ts`
- Modify: `console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx`
- Modify: `console/src/pages/AgentWorkbench/sections/runtimePanels.tsx`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`
- Test: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Test: `console/src/pages/Chat/sessionApi/index.test.ts`

- [ ] Add failing tests that `/runtime-center/industry/{id}` does not inject nonexistent `focus_selection`.
- [ ] Move any supported focus-selection truth into canonical view building or reject unsupported focus inputs.
- [ ] Remove frontend local derivations that select current focus/environment/owner when canonical payload already defines them.
- [ ] Keep frontend as a consumer of canonical projections, not a second truth producer.
- [ ] Run focused backend and frontend tests plus console build.

### Task 6: Reconcile Docs And Verification Claims

**Files:**
- Modify: `46问题文档.md`
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`

- [ ] Update docs so “已验证/已闭环” statements distinguish live e2e, focused harness contract, and code-baseline completion.
- [ ] Remove stale canonical-vocabulary conflicts where current truth and target-state terms are mixed.
- [ ] Document deletion criteria for any remaining compatibility seams left after Tasks 1-5.
- [ ] Re-run the verification matrix referenced by the updated claims and record actual results.

### Final Verification

**Files:**
- Test: `tests/state/test_human_assist_task_service.py`
- Test: `tests/app/test_runtime_human_assist_tasks_api.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/industry/test_runtime_views_split.py`
- Test: `tests/app/test_phase_next_autonomy_smoke.py`
- Test: `tests/app/test_operator_runtime_e2e.py`
- Test: `tests/app/test_runtime_canonical_flow_e2e.py`
- Test: `tests/app/test_runtime_center_api.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`
- Test: `tests/app/test_learning_api.py`
- Test: `console/src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`
- Test: `console/src/pages/Settings/System/index.test.tsx`

- [ ] Run all focused backend tests touched by Tasks 1-5.
- [ ] Run focused frontend tests touched by Task 5.
- [ ] Run `npm --prefix console run build`.
- [ ] Update `46问题文档.md` with final resolved/unresolved status.
