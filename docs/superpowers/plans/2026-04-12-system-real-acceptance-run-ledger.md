# System Real Acceptance Run Ledger

> **For agentic workers:** This ledger records actual acceptance runs against the system real acceptance checklist. A track is not signed off until the evidence bundle is present and the checklist is explicitly updated.

**Goal:** Preserve a factual record of acceptance attempts, including failures, so the project stops relying on chat memory or vague "we already tested that" claims.

**Architecture:** Each entry records one real acceptance run or one grouped automated acceptance sweep. A failed run stays in the ledger and blocks sign-off until a later run resolves it.

**Tech Stack:** pytest, console vitest, Runtime Center, Chat, Industry, Buddy flow, capability market, governance/read surfaces.

---

## Summary Index

| Run ID | Track | Scenario | Date | Commit | Result | Evidence Bundle Ready | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `accept-001` | `A` | Buddy/domain/carrier automated regression sweep | `2026-04-12` | `main (dirty worktree)` | `failed` | `yes` | Same-domain transition/restore path failed |
| `accept-002` | `D` | Capability install/use automated regression sweep | `2026-04-12` | `main (dirty worktree)` | `failed` | `yes` | Blocked shell classification regressed to `waiting-confirm` |
| `accept-003` | `H` | Frontend truth consistency targeted regression sweep | `2026-04-12` | `main (dirty worktree)` | `passed` | `partial` | Code-side consistency checks passed; still not final live sign-off |
| `accept-004` | `Gate-partial` | Frontend slice from P0 runtime terminal gate | `2026-04-12` | `main (dirty worktree)` | `passed` | `partial` | Runtime Center / Predictions / Knowledge targeted frontend slice passed |
| `accept-005` | `A` | Buddy/domain/carrier automated regression re-run after blocker fix | `2026-04-12` | `main (dirty worktree after 247f329)` | `passed` | `yes` | Same-domain preview and archived restore blocker cleared |
| `accept-006` | `D` | Capability install/use automated regression re-run after blocker fix | `2026-04-12` | `main (dirty worktree after 247f329)` | `passed` | `yes` | Blocked shell classification restored to `blocked` |
| `accept-007` | `B` | Main-brain intake to formal delegation automated regression sweep | `2026-04-12` | `main (dirty worktree after 247f329)` | `passed` | `yes` | Main brain keeps delegating into formal execution truth |
| `accept-008` | `C` | Assignment to specialist real work automated regression sweep | `2026-04-12` | `main (dirty worktree after 247f329)` | `passed` | `yes` | Assignment execution, ownership, and closeout chain passed |
| `accept-009` | `F/G` | Evidence-writeback and human-assist resume automated regression sweep | `2026-04-12` | `main (dirty worktree after 247f329)` | `passed` | `yes` | Evidence/report/writeback and handoff/resume truth passed |
| `accept-010` | `K` | Temporal grounding automated regression sweep | `2026-04-12` | `main (dirty worktree after 247f329)` | `passed` | `partial` | Grounded time/tool path passed; still not a live front-door sign-off |
| `accept-011` | `D2/J` | Capability gap, workflow, cron, optimization automated regression sweep | `2026-04-12` | `main (dirty worktree after 247f329)` | `passed` | `yes` | Gap handling, workflow continuity, cron, and optimization loop passed |
| `accept-012` | `E/L` | Environment continuity and fail-closed automated regression sweep | `2026-04-12` | `main (dirty worktree after 247f329)` | `passed` | `yes` | Continuity and explicit fail-closed paths passed |
| `accept-013` | `I` | Long-run autonomy smoke automated regression sweep | `2026-04-12` | `main (dirty worktree after 247f329)` | `passed` | `yes` | Phase-next long-run smoke stayed on one formal chain |
| `accept-014` | `D/J-live-partial` | Live remote skill optimization loop | `2026-04-12` | `main (dirty worktree after 247f329)` | `passed` | `yes` | Real live optimization smoke passed through planning writeback |
| `accept-015` | `B/C/F-live-partial` | Live browser action through chat front door | `2026-04-12` | `main (dirty worktree after 247f329)` | `passed` | `yes` | Real browser execution through chat front door produced task and evidence |

---

## Run ID: accept-001

**Track:** `A`  
**Scenario:** Buddy/domain/carrier automated regression sweep  
**Date:** `2026-04-12`  
**Commit:** `main (dirty worktree)`  
**Operator:** Codex automated acceptance run  
**Environment:** local repo test environment

### A. Preconditions

- Buddy onboarding / projection / routes tests available
- runtime chat binding and conversation tests available

### B. Trigger Path

- Real front door: automated regression
- User/operator action: run Buddy and chat-binding related regression suites
- Expected formal chain: identity -> contract -> direction confirm -> active domain capability -> correct carrier continuity -> same chat/runtime truth

### C. Formal Truth IDs

- `industry_instance_id`: covered by test assertions
- `control_thread_id`: covered by test assertions
- `assignment_id`: `N/A`
- `task_id`: `N/A`
- `decision_request_id`: `N/A`
- `evidence_id`: `N/A`
- `agent_report_id`: `N/A`

### D. API / Read-Model Proof

- Command:
  - `python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_service.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py tests/app/test_runtime_chat_thread_binding.py tests/app/test_runtime_conversations_api.py -q`

### E. Frontend-Visible Proof

- Not a live frontend run
- This entry records automated acceptance only

### F. Refresh / Re-entry Proof

- Covered indirectly by route/projection/binding tests
- Not yet a final live refresh/re-entry sign-off

### G. Result

- Final result: `failed`
- Root cause category:
  - read model and write model mismatch

### H. Failure Detail

- Failure 1:
  - [test_buddy_onboarding_service.py](/D:/word/copaw/tests/kernel/test_buddy_onboarding_service.py)
  - `test_confirm_primary_direction_start_new_and_restore_archived_domain_carrier`
  - observed: archived match list empty, restore path cannot continue
- Failure 2:
  - [test_buddy_routes.py](/D:/word/copaw/tests/app/test_buddy_routes.py)
  - `test_direction_transition_preview_suggests_keep_active_for_same_domain`
  - observed: returned `start-new-domain` instead of expected `same-domain`

### I. Notes

- Track A cannot be signed off while same-domain preview and archived restore are failing in automated regression.

---

## Run ID: accept-002

**Track:** `D`  
**Scenario:** Capability install/use automated regression sweep  
**Date:** `2026-04-12`  
**Commit:** `main (dirty worktree)`  
**Operator:** Codex automated acceptance run  
**Environment:** local repo test environment

### A. Preconditions

- capability market and donor tests available
- capability execution front-door tests available

### B. Trigger Path

- Real front door: automated regression
- User/operator action: run donor/install/use and capability execution suites
- Expected formal chain: install -> durable truth -> usable capability -> real execution outcome -> correct failure classification

### C. Formal Truth IDs

- `industry_instance_id`: `N/A`
- `control_thread_id`: `N/A`
- `assignment_id`: `N/A`
- `task_id`: covered by failing task payload
- `decision_request_id`: `N/A`
- `evidence_id`: covered by execution tests
- `agent_report_id`: `N/A`

### D. API / Read-Model Proof

- Command:
  - `python -m pytest tests/app/test_capability_market_api.py tests/app/test_runtime_center_donor_api.py tests/capabilities/test_project_donor_contracts.py tests/app/test_capabilities_execution.py tests/agents/test_react_agent_tool_compat.py tests/kernel/test_query_execution_runtime.py -q`

### E. Frontend-Visible Proof

- Not a live frontend run
- This entry records automated acceptance only

### F. Refresh / Re-entry Proof

- Install durability covered by test matrix
- Not yet a final live refresh/re-entry sign-off

### G. Result

- Final result: `failed`
- Root cause category:
  - failure was not surfaced and the chain did not fail closed

### H. Failure Detail

- Failure:
  - [test_capabilities_execution.py](/D:/word/copaw/tests/app/test_capabilities_execution.py)
  - `test_execution_failure_contract_classifies_blocked_shell_separately`
  - observed:
    - expected `error_kind == "blocked"`
    - actual `error_kind == "waiting-confirm"`

### I. Notes

- Track D cannot be signed off while blocked shell execution is misclassified, because capability failure semantics are part of "install -> real use" honesty.

---

## Run ID: accept-003

**Track:** `H`  
**Scenario:** Frontend truth consistency targeted regression sweep  
**Date:** `2026-04-12`  
**Commit:** `main (dirty worktree)`  
**Operator:** Codex automated acceptance run  
**Environment:** local repo test environment

### A. Preconditions

- Chat / Runtime Center / Industry / RightPanel / entry redirect tests available

### B. Trigger Path

- Real front door: automated regression
- User/operator action: run shared frontend truth/binding related suites
- Expected formal chain: same runtime truth across Chat, Runtime Center, Industry, and shared companion summary

### C. Formal Truth IDs

- scenario-level formal ids covered inside mocked regression fixtures

### D. API / Read-Model Proof

- Command:
  - `npm --prefix console test -- src/routes/entryRedirect.test.tsx src/layouts/RightPanel/index.test.tsx src/pages/Industry/useIndustryPageState.test.tsx src/pages/RuntimeCenter/useRuntimeCenter.test.ts`
- Result:
  - `4 passed files`
  - `37 passed tests`
- Additional command:
  - `npm --prefix console test -- src/pages/AgentWorkbench/useAgentWorkbench.test.tsx`
- Result:
  - `1 passed file`
  - `2 passed tests`

### E. Frontend-Visible Proof

- Automated only
- No live screenshots recorded yet

### F. Refresh / Re-entry Proof

- Covered by test cases in the targeted suites
- Not yet a final live operator sign-off

### G. Result

- Final result: `passed`
- Root cause category if later rejected:
  - `N/A`

### H. Notes

- This is a code-side pass, not final track sign-off.
- Track H still requires a live reconciliation bundle across real surfaces before final acceptance.

---

## Run ID: accept-004

**Track:** `Gate-partial`  
**Scenario:** Frontend slice from P0 runtime terminal gate  
**Date:** `2026-04-12`  
**Commit:** `main (dirty worktree)`  
**Operator:** Codex automated acceptance run  
**Environment:** local repo test environment

### A. Preconditions

- console test runner available

### B. Trigger Path

- Real front door: targeted frontend gate slice
- User/operator action: run the current frontend slice from the P0 runtime terminal gate

### C. Formal Truth IDs

- `N/A`

### D. API / Read-Model Proof

- Command:
  - `npm --prefix console run test -- src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/components/RuntimeExecutionStrip.test.tsx src/pages/Predictions/index.test.ts src/pages/Knowledge/index.test.tsx`
- Result:
  - `4 passed files`
  - `18 passed tests`

### E. Frontend-Visible Proof

- Automated only

### F. Refresh / Re-entry Proof

- Not a dedicated live sign-off entry

### G. Result

- Final result: `passed`
- Root cause category if later rejected:
  - `N/A`

### H. Notes

- The full backend gate batches timed out in this run window, so this entry only records the frontend slice that completed successfully.

---

## Run ID: accept-005

**Track:** `A`  
**Scenario:** Buddy/domain/carrier automated regression re-run after blocker fix  
**Date:** `2026-04-12 10:20:53 +08:00`  
**Commit:** `main (dirty worktree after 247f329)`  
**Operator:** Codex automated acceptance run  
**Environment:** local repo test environment

### A. Preconditions

- Buddy onboarding / projection / routes tests available
- runtime chat binding and conversation tests available

### B. Trigger Path

- Real front door: automated regression re-run after Track A repair
- User/operator action: rerun Buddy and chat-binding related regression suites
- Expected formal chain: identity -> contract -> direction confirm -> same-domain preview or archived restore -> correct carrier continuity

### C. Formal Truth IDs

- `industry_instance_id`: covered by test assertions
- `control_thread_id`: covered by test assertions
- `assignment_id`: `N/A`
- `task_id`: `N/A`
- `decision_request_id`: `N/A`
- `evidence_id`: `N/A`
- `agent_report_id`: `N/A`

### D. API / Read-Model Proof

- Command:
  - `python -m pytest tests/kernel/test_buddy_onboarding_service.py tests/kernel/test_buddy_projection_service.py tests/app/test_buddy_routes.py tests/app/test_buddy_cutover.py tests/app/test_runtime_chat_thread_binding.py tests/app/test_runtime_conversations_api.py -q`
- Result:
  - `62 passed`

### E. Frontend-Visible Proof

- Not a live frontend run
- This entry records automated acceptance only

### F. Refresh / Re-entry Proof

- Covered indirectly by route/projection/binding tests
- Not yet a final live refresh/re-entry sign-off

### G. Result

- Final result: `passed`

### H. Notes

- Track A automated blocker is cleared.
- This does not replace the later live acceptance run.

---

## Run ID: accept-006

**Track:** `D`  
**Scenario:** Capability install/use automated regression re-run after blocker fix  
**Date:** `2026-04-12 10:20:53 +08:00`  
**Commit:** `main (dirty worktree after 247f329)`  
**Operator:** Codex automated acceptance run  
**Environment:** local repo test environment

### A. Preconditions

- capability market and donor tests available
- capability execution front-door tests available

### B. Trigger Path

- Real front door: automated regression re-run after Track D repair
- User/operator action: rerun donor/install/use and capability execution suites
- Expected formal chain: install -> durable truth -> usable capability -> real execution outcome -> honest blocked/failed classification

### C. Formal Truth IDs

- `industry_instance_id`: `N/A`
- `control_thread_id`: `N/A`
- `assignment_id`: `N/A`
- `task_id`: covered by execution tests
- `decision_request_id`: `N/A`
- `evidence_id`: covered by execution tests
- `agent_report_id`: `N/A`

### D. API / Read-Model Proof

- Commands:
  - `python -m pytest tests/app/test_capability_market_api.py tests/app/test_runtime_center_donor_api.py -q`
  - `python -m pytest tests/capabilities/test_project_donor_contracts.py tests/app/test_capabilities_execution.py -q`
  - `python -m pytest tests/agents/test_react_agent_tool_compat.py tests/kernel/test_query_execution_runtime.py -q`
- Result:
  - `52 passed`
  - `65 passed`
  - `36 passed`

### E. Frontend-Visible Proof

- Not a live frontend run
- This entry records automated acceptance only

### F. Refresh / Re-entry Proof

- Install durability and execution honesty covered by the grouped suites
- Not yet a final live refresh/re-entry sign-off

### G. Result

- Final result: `passed`

### H. Notes

- Track D automated blocker is cleared.
- The previous grouped command timed out; the split re-run completed cleanly.

---

## Run ID: accept-007

**Track:** `B`  
**Scenario:** Main-brain intake to formal delegation automated regression sweep  
**Date:** `2026-04-12`  
**Commit:** `main (dirty worktree after 247f329)`  
**Operator:** Codex automated acceptance run  
**Environment:** local repo test environment

### D. API / Read-Model Proof

- Command:
  - `python -m pytest tests/kernel/test_main_brain_orchestrator.py tests/kernel/test_turn_executor.py tests/kernel/test_kernel.py tests/app/test_runtime_center_task_delegation_api.py -q`
- Result:
  - `107 passed`

### G. Result

- Final result: `passed`

### H. Notes

- This run covers operator intake, formal delegation, and runtime delegation read surfaces.
- Still counts as automated evidence, not final live sign-off.

---

## Run ID: accept-008

**Track:** `C`  
**Scenario:** Assignment to specialist real work automated regression sweep  
**Date:** `2026-04-12`  
**Commit:** `main (dirty worktree after 247f329)`  
**Operator:** Codex automated acceptance run  
**Environment:** local repo test environment

### D. API / Read-Model Proof

- Command:
  - `python -m pytest tests/kernel/test_actor_worker.py tests/kernel/test_assignment_envelope.py tests/kernel/test_chat_writeback.py -q`
- Result:
  - `24 passed`

### G. Result

- Final result: `passed`

### H. Notes

- This run covers assignment ownership, execution envelope inheritance, and downstream execution truth.
- Still counts as automated evidence, not final live sign-off.

---

## Run ID: accept-009

**Track:** `F/G`  
**Scenario:** Evidence-writeback and human-assist resume automated regression sweep  
**Date:** `2026-04-12`  
**Commit:** `main (dirty worktree after 247f329)`  
**Operator:** Codex automated acceptance run  
**Environment:** local repo test environment

### D. API / Read-Model Proof

- Command:
  - `python -m pytest tests/app/test_runtime_query_services.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_lifecycle.py -q`
- Result:
  - `51 passed`

### G. Result

- Final result: `passed`

### H. Notes

- This run covers evidence/report surfaces plus human-assist, handoff, resume, and continuity read models.
- Still counts as automated evidence, not final live sign-off.

---

## Run ID: accept-010

**Track:** `K`  
**Scenario:** Temporal grounding automated regression sweep  
**Date:** `2026-04-12`  
**Commit:** `main (dirty worktree after 247f329)`  
**Operator:** Codex automated acceptance run  
**Environment:** local repo test environment

### D. API / Read-Model Proof

- Command:
  - `python -m pytest tests/agents/test_react_agent_tool_compat.py tests/kernel/test_main_brain_runtime_context_buddy_prompt.py tests/app/test_cron_manager.py tests/kernel/test_query_execution_runtime.py -k "get_current_time or frontdoor or query_turn or today or tomorrow or weekday or monday or preflight or fallback" -q`
- Result:
  - `8 passed`
  - `35 deselected`

### G. Result

- Final result: `passed`

### H. Notes

- The grounded time/tool path is green in automated coverage.
- This still needs real front-door live questioning before final track sign-off.

---

## Run ID: accept-011

**Track:** `D2/J`  
**Scenario:** Capability gap, workflow, cron, optimization automated regression sweep  
**Date:** `2026-04-12`  
**Commit:** `main (dirty worktree after 247f329)`  
**Operator:** Codex automated acceptance run  
**Environment:** local repo test environment

### D. API / Read-Model Proof

- Commands:
  - `python -m pytest tests/app/test_main_brain_optimization_loop_e2e.py::test_main_brain_governed_optimization_loop_e2e -q`
  - `python -m pytest tests/app/test_cron_manager.py -q`
  - `python -m pytest tests/app/test_workflow_templates_api.py::test_workflow_resume_refreshes_schedule_host_meta_from_live_host_twin -q`
  - `python -m pytest tests/app/test_workflow_templates_api.py::test_workflow_resume_prefers_canonical_selected_seat_from_live_host_twin_summary -q`
  - `python -m pytest tests/app/test_workflow_templates_api.py::test_workflow_run_cancel_archives_goals_and_pauses_schedules -q`
  - `python -m pytest tests/app/test_workflow_templates_api.py::test_workflow_preview_reports_assignment_gap_and_internal_launch_stays_blocked -q`
  - `python -m pytest tests/app/test_workflow_templates_api.py::test_install_template_assigns_capability_and_unlocks_workflow_launch -q`
- Result:
  - `1 passed`
  - `5 passed`
  - `1 passed`
  - `1 passed`
  - `1 passed`
  - `1 passed`
  - `1 passed`

### G. Result

- Final result: `passed`

### H. Notes

- This run covers assignment-gap handling, capability supplement/unlock, workflow continuity, cron, and optimization writeback loop.
- Still counts as automated evidence, not final live sign-off.

---

## Run ID: accept-012

**Track:** `E/L`  
**Scenario:** Environment continuity and fail-closed automated regression sweep  
**Date:** `2026-04-12`  
**Commit:** `main (dirty worktree after 247f329)`  
**Operator:** Codex automated acceptance run  
**Environment:** local repo test environment

### D. API / Read-Model Proof

- Command:
  - `python -m pytest tests/environments/test_cooperative_browser_attach_runtime.py::test_browser_channel_resolver_fails_closed_when_attach_is_required_but_not_available tests/app/test_startup_recovery.py::test_startup_recovery_surface_detection_fails_closed_when_layers_are_malformed tests/kernel/test_main_brain_chat_service.py::test_main_brain_chat_service_fails_closed_for_empty_model_response tests/environments/test_environment_registry.py::test_environment_detail_keeps_host_events_as_formal_runtime_mechanism_for_handoff_and_return tests/environments/test_environment_registry.py::test_host_twin_recovery_handoff_long_run_prefers_current_host_truth_over_stale_blocker_history tests/environments/test_environment_registry.py::test_detached_session_without_explicit_handoff_does_not_require_human_return -q`
- Result:
  - `6 passed`

### G. Result

- Final result: `passed`

### H. Notes

- This run covers explicit fail-closed behavior and environment continuity/handoff continuity truth.
- Still counts as automated evidence, not final live sign-off.

---

## Run ID: accept-013

**Track:** `I`  
**Scenario:** Long-run autonomy smoke automated regression sweep  
**Date:** `2026-04-12`  
**Commit:** `main (dirty worktree after 247f329)`  
**Operator:** Codex automated acceptance run  
**Environment:** local repo test environment

### D. API / Read-Model Proof

- Commands:
  - `python -m pytest tests/app/test_phase_next_autonomy_smoke.py::test_phase_next_industry_long_run_smoke_keeps_followup_focus_and_replan_truth_contract -q`
  - `python -m pytest tests/app/test_phase_next_autonomy_smoke.py::test_phase_next_industry_long_run_smoke_keeps_handoff_human_assist_and_replan_on_one_control_thread_contract -q`
  - `python -m pytest tests/app/test_phase_next_autonomy_smoke.py::test_phase_next_long_run_harness_smoke_covers_runtime_chain_and_multi_surface_continuity_contract -q`
- Result:
  - `1 passed`
  - `1 passed`
  - `1 passed`

### G. Result

- Final result: `passed`

### H. Notes

- This run covers multi-step long-run continuity, replan, handoff, and multi-surface runtime-chain truth.
- Still counts as automated evidence, not final live sign-off.

---

## Run ID: accept-014

**Track:** `D/J-live-partial`  
**Scenario:** Live remote skill optimization loop  
**Date:** `2026-04-12`  
**Commit:** `main (dirty worktree after 247f329)`  
**Operator:** Codex live smoke run  
**Environment:** current local machine with `COPAW_RUN_LIVE_OPTIMIZATION_SMOKE=1`

### D. API / Read-Model Proof

- Command:
  - `python -m pytest tests/app/test_live_optimization_smoke.py::test_live_remote_skill_optimization_loop_closes_into_planning_writeback -q`
- Result:
  - `1 passed`

### E. Frontend-Visible Proof

- Live smoke path exercised a real live optimization front door
- No separate manual screenshot bundle recorded in this ledger entry

### G. Result

- Final result: `passed`

### H. Notes

- This is real live evidence for the remote skill optimization loop and planning writeback.
- It materially strengthens Track D / J, but does not by itself complete the full supported-scope sign-off matrix.

---

## Run ID: accept-015

**Track:** `B/C/F-live-partial`  
**Scenario:** Live browser action through chat front door  
**Date:** `2026-04-12`  
**Commit:** `main (dirty worktree after 247f329)`  
**Operator:** Codex live smoke run  
**Environment:** current local machine with `COPAW_RUN_LIVE_AGENT_ACTION_SMOKE=1`

### D. API / Read-Model Proof

- Command:
  - `python -m pytest tests/app/test_live_agent_action_smoke.py::test_live_solution_lead_browser_action_runs_through_runtime_center_chat_front_door -q`
- Result:
  - `1 passed`

### E. Frontend-Visible Proof

- Live chat front door path exercised
- Browser screenshot artifact was actually created
- Browser evidence truth was asserted by the live smoke

### G. Result

- Final result: `passed`

### H. Notes

- This is real live evidence that chat front door -> professional seat -> browser capability -> task/evidence chain can complete honestly.
- It materially strengthens Track B / C / F, but does not by itself replace the full multi-surface live reconciliation required for final sign-off.
