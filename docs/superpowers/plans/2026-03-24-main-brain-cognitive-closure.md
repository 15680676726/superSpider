# Main Brain Cognitive Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen COPAW's existing main-brain chain so the system no longer stops at delegation and status return, but can receive richer structured reports, synthesize them, surface conflicts and follow-ups, and keep the main-brain chat/runtime split clean.

**Architecture:** Reuse the existing `Backlog -> OperatingCycle -> Assignment -> AgentReport -> reconcile` chain instead of creating a second planning truth source. Enrich the report contract first, add an explicit synthesis module on top of the existing cycle/report path, then tighten the chat/intake/runtime boundary so the main brain remains the communication and decision center while execution stays in the governed runtime.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLite state repositories, pytest, React, TypeScript, Runtime Center

**Companion Docs:**
- Audit baseline: `docs/archive/root-legacy/REVIEW_C3PO_FULL_AUDIT.md`
- Acceptance gate: `docs/archive/root-legacy/REVIEW_C3PO_ACCEPTANCE_CHECKLIST.md`

---

## Scope Guardrails

- Keep `execution-core` as the only main-brain control role. Do not reintroduce parallel `manager` or second-brain semantics.
- Reuse `MainBrainChatService`, `OperatingCycleService`, `AssignmentService`, and `AgentReportService`. Do not create a parallel planner, report store, or orchestration kernel.
- Treat `tool / MCP / skill / browser / desktop` as capability surfaces only. Do not let them absorb main-brain synthesis responsibility.
- Keep all new truth in existing `state` objects or explicit extensions of those objects.
- Prefer extracting focused helper modules over growing `service_lifecycle.py` and `query_execution_runtime.py` even further.
- Treat `docs/archive/root-legacy/REVIEW_C3PO_ACCEPTANCE_CHECKLIST.md` as the release gate. A task is not complete if it only improves wording, routing heuristics, or status summaries without moving the acceptance items.

## Exit Gates

- `S1`: Main brain becomes a clearer single cognitive center instead of leaving synthesis split across chat/runtime/executor.
- `S2`: Delegation and synthesis both have explicit engineering surfaces.
- `S3`: New work primarily strengthens `plan / report / synthesis / replan`, not capability/platform sprawl.
- `A2`: `AgentReportRecord` becomes a formal cognitive return contract instead of only a lifecycle summary.
- `A3`: chat/runtime split keeps clear boundaries without preserving dual-brain behavior.

## Existing Baseline To Reuse

- `OperatingLaneRecord`, `BacklogItemRecord`, `OperatingCycleRecord`, `AssignmentRecord`, and `AgentReportRecord` already exist in `src/copaw/state/models.py`.
- `AgentReportService.record_task_terminal_report()` already turns terminal tasks into structured report records.
- `IndustryService.run_operating_cycle()` already materializes cycles, assignments, and reconciles them.
- `IndustryService._process_pending_agent_reports()` already writes agent reports back to the execution-core control thread.
- `MainBrainChatService` already exists as the pure-chat front and already runs background intake for control-thread turns.
- `KernelTurnExecutor` already routes `interaction_mode=auto` between chat and orchestration.

## File Map

### Report contract and persistence

- Modify: `src/copaw/state/models.py`
  - Extend `AgentReportRecord` with stronger cognitive fields instead of keeping only `headline / summary / result`.
- Modify: `src/copaw/state/store.py`
  - Persist any new report columns in SQLite.
- Modify: `src/copaw/state/repositories/sqlite_industry.py`
  - Read and write the richer report schema.
- Modify: `src/copaw/state/main_brain_service.py`
  - Materialize and retain richer task-terminal reports.

### Report synthesis and replan

- Create: `src/copaw/industry/report_synthesis.py`
  - Centralize report comparison, conflict detection, hole detection, and follow-up generation.
- Modify: `src/copaw/industry/service_lifecycle.py`
  - Call the synthesis module during report processing and cycle reconciliation.
- Modify: `src/copaw/industry/service_strategy.py`
  - Expose synthesis results in `IndustryInstanceDetail` and staffing/runtime read surfaces.

### Main-brain chat/runtime boundary

- Create: `src/copaw/kernel/main_brain_intake.py`
  - Hold the structured main-brain intake decision/materialization contract shared by chat and runtime.
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
  - Use the shared intake contract and keep the chat front focused on communication.
- Modify: `src/copaw/kernel/turn_executor.py`
  - Keep `auto` routing thin and explicit.
- Modify: `src/copaw/kernel/query_execution_runtime.py`
  - Consume the shared intake/writeback contract instead of duplicating decision semantics.
- Modify: `src/copaw/kernel/query_execution_prompt.py`
  - Rebalance control-core instructions toward synthesis responsibility before delegation.

### Frontend read surfaces

- Modify: `console/src/api/modules/industry.ts`
  - Add typings for richer agent reports and synthesis summary.
- Modify: `console/src/pages/Industry/index.tsx`
  - Show unresolved report conflicts, follow-ups, and latest main-brain synthesis.
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.tsx`
  - Surface the same synthesis summary in runtime detail views.
- Modify: `console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx`
  - Show richer latest report payload and whether follow-up is still needed.

### Tests and docs

- Modify: `tests/state/test_sqlite_repositories.py`
  - Cover richer `AgentReportRecord` persistence.
- Create: `tests/industry/test_report_synthesis.py`
  - Unit coverage for conflict detection and replan suggestions.
- Modify: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
  - Integration coverage for report creation, synthesis, and control-thread writeback.
- Modify: `tests/kernel/test_main_brain_chat_service.py`
  - Verify prompt context and background intake use the cleaned main-brain intake path.
- Modify: `tests/kernel/test_turn_executor.py`
  - Verify `auto` routing still behaves correctly after intake extraction.
- Modify: `TASK_STATUS.md`
  - Register the closure pass after implementation lands.

### Task 1: Enrich the Formal Agent Report Contract

**Files:**
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/repositories/sqlite_industry.py`
- Modify: `src/copaw/state/main_brain_service.py`
- Test: `tests/state/test_sqlite_repositories.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`

- [ ] **Step 1: Write failing persistence tests for richer report fields**

Add tests that assert `AgentReportRecord` persists and reloads:
- `findings`
- `uncertainties`
- `recommendation`
- `needs_followup`
- `followup_reason`

- [ ] **Step 2: Run the targeted tests to confirm they fail**

Run: `python -m pytest tests/state/test_sqlite_repositories.py tests/app/industry_api_parts/bootstrap_lifecycle.py -q -k "agent_report or report_processing"`
Expected: FAIL because the new report fields are not stored or exposed yet.

- [ ] **Step 3: Extend the report model and SQLite mapping**

Implement the minimal schema changes so `AgentReportRecord` becomes a real cognitive return object instead of only a status summary.

- [ ] **Step 4: Update task-terminal report materialization**

Teach `AgentReportService.record_task_terminal_report()` to fill safe defaults for the new fields from existing runtime/evidence/decision context without inventing content.

- [ ] **Step 5: Re-run the targeted tests**

Run: `python -m pytest tests/state/test_sqlite_repositories.py tests/app/industry_api_parts/bootstrap_lifecycle.py -q -k "agent_report or report_processing"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/copaw/state/models.py src/copaw/state/store.py src/copaw/state/repositories/sqlite_industry.py src/copaw/state/main_brain_service.py tests/state/test_sqlite_repositories.py tests/app/industry_api_parts/bootstrap_lifecycle.py
git commit -m "feat: enrich agent report contract"
```

### Task 2: Add an Explicit Report Synthesis Module

**Files:**
- Create: `src/copaw/industry/report_synthesis.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Test: `tests/industry/test_report_synthesis.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`

- [ ] **Step 1: Write failing unit tests for report synthesis**

Add tests for:
- two reports that agree and should close cleanly
- two reports that conflict and should emit a conflict entry
- a failed report that should create a follow-up backlog/replan signal
- a report with `needs_followup=True` that should remain visible in the main-brain surface

- [ ] **Step 2: Run the synthesis tests to confirm they fail**

Run: `python -m pytest tests/industry/test_report_synthesis.py -q`
Expected: FAIL because `report_synthesis.py` does not exist yet.

- [ ] **Step 3: Implement a focused synthesis module**

Create a small module that takes latest reports and returns a normalized synthesis payload:
- `latest_findings`
- `conflicts`
- `holes`
- `recommended_actions`
- `needs_replan`

- [ ] **Step 4: Wire synthesis into report processing and cycle reconciliation**

Call the synthesis module from `IndustryService._process_pending_agent_reports()` and `run_operating_cycle()` so unresolved conflicts or explicit follow-ups become formal backlog or cycle feedback instead of only free-text summaries.

- [ ] **Step 5: Expose synthesis in `IndustryInstanceDetail`**

Update the runtime read model so `Industry` / `Runtime Center` can show the current main-brain synthesis state.

- [ ] **Step 6: Re-run the synthesis and integration tests**

Run: `python -m pytest tests/industry/test_report_synthesis.py tests/app/industry_api_parts/bootstrap_lifecycle.py -q -k "report or cycle"`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/copaw/industry/report_synthesis.py src/copaw/industry/service_lifecycle.py src/copaw/industry/service_strategy.py tests/industry/test_report_synthesis.py tests/app/industry_api_parts/bootstrap_lifecycle.py
git commit -m "feat: add main brain report synthesis"
```

### Task 3: Clean Up the Main-Brain Chat and Runtime Intake Boundary

**Files:**
- Create: `src/copaw/kernel/main_brain_intake.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/kernel/test_turn_executor.py`

- [ ] **Step 1: Write failing tests for shared intake behavior**

Add tests that assert:
- control-thread `auto` turns still answer through `MainBrainChatService`
- background intake uses one structured decision/materialization path
- runtime writeback/kickoff no longer duplicates the same decision logic in multiple places

- [ ] **Step 2: Run the kernel tests to confirm they fail**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py -q`
Expected: FAIL after adding the new expectations because the shared intake module does not exist yet.

- [ ] **Step 3: Extract a shared main-brain intake contract**

Implement `main_brain_intake.py` so chat front and runtime reuse the same decision-to-writeback/kickoff materialization logic.

- [ ] **Step 4: Simplify `turn_executor` and runtime integration**

Keep `turn_executor` responsible for routing and keep runtime responsible for execution, while the shared intake module owns the structured handoff semantics.

- [ ] **Step 5: Re-run the kernel tests**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/copaw/kernel/main_brain_intake.py src/copaw/kernel/main_brain_chat_service.py src/copaw/kernel/turn_executor.py src/copaw/kernel/query_execution_runtime.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py
git commit -m "refactor: unify main brain intake flow"
```

### Task 4: Rebalance Control-Core Prompts Toward Synthesis Ownership

**Files:**
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `src/copaw/industry/prompting.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Test: `tests/kernel/query_execution_environment_parts/lifecycle.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`

- [ ] **Step 1: Add failing prompt assertions**

Add assertions that the control core prompt explicitly mentions:
- compare reports
- detect conflicts and holes
- surface staffing/routing gaps
- own final operator-facing synthesis before delegating more work

- [ ] **Step 2: Run the prompt-focused tests**

Run: `python -m pytest tests/kernel/query_execution_environment_parts/lifecycle.py tests/kernel/test_main_brain_chat_service.py -q`
Expected: FAIL because those instructions are not yet explicit enough.

- [ ] **Step 3: Update control-core prompt language**

Keep delegation available, but make synthesis and final decision ownership first-class responsibilities in prompt contracts and runtime detail surfaces.

- [ ] **Step 4: Re-run the prompt-focused tests**

Run: `python -m pytest tests/kernel/query_execution_environment_parts/lifecycle.py tests/kernel/test_main_brain_chat_service.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/copaw/kernel/query_execution_prompt.py src/copaw/industry/prompting.py src/copaw/industry/service_strategy.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/kernel/test_main_brain_chat_service.py
git commit -m "feat: emphasize main brain synthesis ownership"
```

### Task 5: Frontend Visibility and Final Verification

**Files:**
- Modify: `console/src/api/modules/industry.ts`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.tsx`
- Modify: `console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Add frontend typings for richer reports and synthesis**

Update the industry/runtime API layer so the frontend can read the new report and synthesis payloads without fallback `any` handling.

- [ ] **Step 2: Surface main-brain synthesis state in the operator views**

Render:
- latest main-brain synthesis summary
- unresolved report conflicts
- follow-up needed / replan needed markers

- [ ] **Step 3: Run frontend build verification**

Run: `cmd.exe /c npm --prefix console run build`
Expected: build succeeds.

- [ ] **Step 4: Run the final backend verification bundle**

Run: `python -m pytest tests/state/test_sqlite_repositories.py tests/industry/test_report_synthesis.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py tests/kernel/query_execution_environment_parts/lifecycle.py -q`
Expected: all targeted regression tests pass.

- [ ] **Step 5: Update task status**

Record the closure pass in `TASK_STATUS.md`, explicitly stating that the repository now has:
- richer `AgentReportRecord`
- explicit report synthesis
- cleaner main-brain intake boundary
- operator-visible synthesis surfaces

- [ ] **Step 6: Commit**

```bash
git add console/src/api/modules/industry.ts console/src/pages/Industry/index.tsx console/src/pages/RuntimeCenter/viewHelpers.tsx console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx TASK_STATUS.md
git commit -m "feat: surface main brain synthesis state"
```
