# Real-System Autonomy Runtime Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the already-landed V7 main-brain skeleton into a reliable runtime where the main brain really plans and supervises, specialist agents really execute, and desktop/browser/file work is routed by capability and environment instead of stalling behind stale goal fan-out or shallow routing heuristics.

**Architecture:** Keep the existing formal chain `MainBrainChatService -> chat writeback -> Backlog -> OperatingCycle -> Assignment -> Goal -> Task -> AgentReport -> report synthesis -> next cycle`. Do not redesign the system from scratch. The repair order is: first harden runtime failures already seen in live logs, then stop eager multi-step goal materialization, then strengthen assignment-first execution and capability-aware routing, then expose supervision state so the operator can see what the main brain actually decided and what is blocked.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLite state repositories, pytest, React, TypeScript, Runtime Center

---

## Real Baseline Confirmed On 2026-03-24

- `MainBrainChatService` already exists and is the default front door for `POST /api/runtime-center/chat/run`.
- `KernelTurnExecutor` already routes `interaction_mode=auto` between pure chat and orchestration.
- `MainBrainIntakeContract` already exists in `src/copaw/kernel/main_brain_intake.py`, and `MainBrainChatService` already performs background writeback/kickoff.
- `OperatingLaneRecord`, `BacklogItemRecord`, `OperatingCycleRecord`, `AssignmentRecord`, and `AgentReportRecord` already exist in `src/copaw/state/models.py`.
- `IndustryService.run_operating_cycle()` is already wired into `system:run_operating_cycle` through `src/copaw/app/runtime_lifecycle.py`.
- `IndustryService._process_pending_agent_reports()` already writes reports back into the control thread and already calls `synthesize_reports()`.
- Two real bugs are already fixed in workspace and verified by tests, but were not yet applied to the live `8088` backend because the old process was not restarted:
  - `src/copaw/kernel/delegation_service.py`
  - `src/copaw/app/channels/console/channel.py`
- One live runtime bug is still unresolved:
  - `ContextVar ... Token ... was created in a different Context`
  - stack touches `src/copaw/agents/tools/evidence_runtime.py`, `src/copaw/agents/react_agent.py`, and `src/copaw/kernel/query_execution_runtime.py`
- The main structural blocker is still live in source:
  - `src/copaw/compiler/compiler.py:_compile_goal()` eagerly compiles one task per step
  - `src/copaw/goals/service_dispatch.py` persists those compiled tasks and background-chains them
  - this is why the runtime can look busy while real execution throughput stays low

## Scope Guardrails

- Do not create a second planner, second report store, or second orchestration kernel.
- Do not remove the V7 objects that already exist. Elevate them and make the older goal/task habits serve them.
- Do not restore direct front-end execution entrypoints such as `/chat/orchestrate` or `/tasks/{task_id}/delegate`; those are already retired and should stay retired.
- Do not hardcode app-name routing as the durable solution. Generic surface and capability routing must be the primary mechanism.
- Do not let `execution-core` become the default leaf worker again. If no seat fits, create a temporary seat or a governed proposal; do not silently fall back to direct execution.
- Keep capability/tool/MCP growth subordinate to the main-brain chain. If a change adds more surface complexity without improving `plan -> assign -> report -> synthesize -> replan`, it is out of scope.

## Already Landed And Not To Be Re-Planned

- `src/copaw/kernel/main_brain_intake.py` already exists.
- `src/copaw/industry/report_synthesis.py` already exists.
- `AgentReportRecord` already has richer cognitive fields in `src/copaw/state/models.py`.
- `OperatingCycle` / `Assignment` / `AgentReport` read surfaces already exist in runtime and industry detail APIs.

This plan only covers the still-open repair work.

## File Map

### Runtime hardening

- Modify: `src/copaw/agents/tools/evidence_runtime.py`
- Modify: `src/copaw/agents/react_agent.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Reference: `src/copaw/kernel/delegation_service.py`
- Reference: `src/copaw/app/channels/console/channel.py`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `tests/app/test_runtime_center_task_delegation_api.py`
- Test: `tests/app/test_console_channel.py`

### Goal dispatch de-staging

- Modify: `src/copaw/compiler/compiler.py`
- Modify: `src/copaw/goals/service_dispatch.py`
- Modify: `src/copaw/goals/service_core.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Test: `tests/goals/test_goal_service_dispatch.py`
- Test: `tests/app/test_runtime_center_task_delegation_api.py`

### Assignment-first execution closure

- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `src/copaw/kernel/query_execution_tools.py`
- Test: `tests/industry/test_operating_cycle.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `tests/kernel/test_turn_executor.py`

### Capability-aware routing instead of token-only routing

- Modify: `src/copaw/industry/service_context.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/industry/seat_gap_policy.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Test: `tests/industry/test_seat_gap_policy.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`

### Operator-visible supervision and rollout

- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `console/src/api/modules/industry.ts`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.tsx`
- Modify: `console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `console/src/runtime/staffingGapPresentation.test.ts`

### Documentation and release gate

- Modify: `TASK_STATUS.md`
- Modify: `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`
- Reference: `docs/superpowers/plans/2026-03-24-main-brain-cognitive-closure.md`
- Reference: `docs/superpowers/plans/2026-03-23-single-industry-autonomy-closure.md`

### Task 0: Land The Existing Verified Hotfixes And Fix Context Leakage

**Files:**
- Modify: `src/copaw/agents/tools/evidence_runtime.py`
- Modify: `src/copaw/agents/react_agent.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Reference: `src/copaw/kernel/delegation_service.py`
- Reference: `src/copaw/app/channels/console/channel.py`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `tests/app/test_runtime_center_task_delegation_api.py`
- Test: `tests/app/test_console_channel.py`

- [ ] **Step 1: Add a failing regression for cross-context tool/evidence binding**

Add a kernel test that executes the runtime path which binds:
- `bind_tool_preflight()`
- `bind_shell_evidence_sink()`
- `bind_file_evidence_sink()`
- `bind_browser_evidence_sink()`

and reproduces the live error:
- `Token was created in a different Context`

- [ ] **Step 2: Run the targeted regression tests**

Run: `python -m pytest tests/kernel/test_query_execution_runtime.py tests/app/test_runtime_center_task_delegation_api.py tests/app/test_console_channel.py -q`
Expected: FAIL on the new context regression, while the delegation and console regressions continue to pass.

- [ ] **Step 3: Replace reset-across-context assumptions with execution-scope propagation**

Implementation rules:
- keep `ContextVar` lookup behavior for same-task execution
- do not reset tokens from a different task/context
- if the runtime spawns or resumes work across task boundaries, pass the bound sinks/preflight resolver as explicit call-scoped state instead of assuming the original token can be reset later
- keep evidence capture best-effort and non-fatal

- [ ] **Step 4: Re-run the targeted tests**

Run: `python -m pytest tests/kernel/test_query_execution_runtime.py tests/app/test_runtime_center_task_delegation_api.py tests/app/test_console_channel.py -q`
Expected: PASS

- [ ] **Step 5: Restart the live backend so the already-fixed delegation and console patches actually take effect**

Verification after restart:
- `GET /api/system/info` returns `200`
- `GET /api/runtime-center/industry` returns `200`
- live log no longer emits the GBK `UnicodeEncodeError`
- live log no longer emits the `Token was created in a different Context` stack during the exercised scenario

- [ ] **Step 6: Commit**

```bash
git add src/copaw/agents/tools/evidence_runtime.py src/copaw/agents/react_agent.py src/copaw/kernel/query_execution_runtime.py tests/kernel/test_query_execution_runtime.py
git commit -m "fix: harden runtime context propagation"
```

### Task 1: Stop Eager Goal Fan-Out From Pretending Work Is Active

**Files:**
- Modify: `src/copaw/compiler/compiler.py`
- Modify: `src/copaw/goals/service_dispatch.py`
- Modify: `src/copaw/goals/service_core.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Test: `tests/goals/test_goal_service_dispatch.py`
- Test: `tests/app/test_runtime_center_task_delegation_api.py`

- [ ] **Step 1: Add failing tests for stepwise goal execution**

Add tests that assert:
- a goal with `steps=[...]` compiles only the current executable step
- unfinished future steps are not persisted as cold sibling tasks
- completing step `N` can trigger step `N+1` without pre-materializing the whole chain
- delegation preview and environment conflict logic only see real inflight work

- [ ] **Step 2: Run the goal-dispatch tests**

Run: `python -m pytest tests/goals/test_goal_service_dispatch.py tests/app/test_runtime_center_task_delegation_api.py -q`
Expected: FAIL because `_compile_goal()` still emits one compiled task per step.

- [ ] **Step 3: Change goal compilation from eager multi-step materialization to single-step staging**

Implementation rules:
- when a goal already has a plan, compile only the current step into a kernel task
- persist the remaining steps in goal/runtime/work-context metadata instead of creating sibling tasks immediately
- after a step completes, compute and dispatch the next step from canonical goal state
- remove any background-chain logic that treats cold future steps as an active execution chain

- [ ] **Step 4: Update cycle auto-dispatch to reuse the new single-step behavior**

Ensure:
- `IndustryService._dispatch_operating_cycle_materialized_goals()` still works
- `kickoff_execution_from_chat()` still works
- neither path recreates the eager step fan-out problem

- [ ] **Step 5: Re-run the dispatch tests**

Run: `python -m pytest tests/goals/test_goal_service_dispatch.py tests/app/test_runtime_center_task_delegation_api.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/compiler/compiler.py src/copaw/goals/service_dispatch.py src/copaw/goals/service_core.py src/copaw/industry/service_lifecycle.py tests/goals/test_goal_service_dispatch.py tests/app/test_runtime_center_task_delegation_api.py
git commit -m "fix: stage goal steps instead of fan-out compiling"
```

### Task 2: Make Assignments The Real Execution Envelope

**Files:**
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `src/copaw/kernel/query_execution_tools.py`
- Test: `tests/industry/test_operating_cycle.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `tests/kernel/test_turn_executor.py`

- [ ] **Step 1: Add failing integration tests for assignment-first execution**

Add tests that assert:
- operator input first becomes backlog and cycle work, not immediate free-floating leaf execution
- every auto-dispatched goal from a cycle carries `assignment_id`, `lane_id`, and `report_back_mode`
- when no specialist seat is available, the system stays in staffing/routing flow instead of silently letting the main brain act as the worker
- task completion writes back to the matching assignment/report chain

- [ ] **Step 2: Run the integration tests**

Run: `python -m pytest tests/industry/test_operating_cycle.py tests/app/industry_api_parts/runtime_updates.py tests/kernel/test_turn_executor.py -q`
Expected: FAIL on the new assignment-first expectations.

- [ ] **Step 3: Tighten lifecycle transitions around assignments**

Implementation rules:
- `AssignmentRecord` is the main-brain work packet the operator should reason about
- goal dispatch remains an execution vehicle, not the planning truth
- backlog materialization must always resolve an assignment owner or a staffing gap outcome before execution begins
- `execution-core` may supervise and synthesize, but it must not become the default assignee for arbitrary leaf work

- [ ] **Step 4: Strengthen prompts and tools around supervisory-only control-core behavior**

Ensure:
- control-core runtime remains `delegate / dispatch / verify / synthesize` oriented
- specialist runtime remains `execute / report / escalate` oriented
- prompts do not let a blocked tool response masquerade as final task handling

- [ ] **Step 5: Re-run the integration tests**

Run: `python -m pytest tests/industry/test_operating_cycle.py tests/app/industry_api_parts/runtime_updates.py tests/kernel/test_turn_executor.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/industry/service_lifecycle.py src/copaw/industry/service_strategy.py src/copaw/kernel/query_execution_prompt.py src/copaw/kernel/query_execution_tools.py tests/industry/test_operating_cycle.py tests/app/industry_api_parts/runtime_updates.py tests/kernel/test_turn_executor.py
git commit -m "refactor: make assignments the real execution envelope"
```

### Task 3: Replace Token-Only Surface Routing With Capability-Aware Routing

**Files:**
- Modify: `src/copaw/industry/service_context.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/industry/seat_gap_policy.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Test: `tests/industry/test_seat_gap_policy.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`

- [ ] **Step 1: Add failing routing tests that avoid app-name hardcoding**

Add tests for messages like:
- `帮我整理桌面上的文件`
- `打开文末天机把这批资料归档`
- `登录某电商后台改一下标题`

Expected routing behavior:
- desktop/file requests resolve by surface and mounted capability, not by a hardcoded app list
- unknown desktop apps still resolve as `desktop` work if the mounted environment can drive them
- browser/business-backend work resolves as `browser` if the seat and capability envelope support it

- [ ] **Step 2: Run the routing tests**

Run: `python -m pytest tests/industry/test_seat_gap_policy.py tests/kernel/test_main_brain_chat_service.py -q`
Expected: FAIL because current routing still depends heavily on token matches in `service_strategy.py`.

- [ ] **Step 3: Introduce layered surface resolution**

Resolution order:
1. explicit structured intent from `MainBrainIntakeContract` / approved writeback targets
2. role capability projection and accessible mounted capabilities
3. environment constraints and evidence expectations
4. text-token heuristics only as fallback

Implementation rules:
- keep surfaces generic: `file`, `desktop`, `browser`
- do not add durable hardcoded app-name catalogs as the primary router
- preserve text-token fallback for weak prompts, but stop treating it as the canonical truth

- [ ] **Step 4: Feed the resolved routing result into staffing summaries and main-brain chat context**

The operator-visible state should explain:
- requested surfaces
- matched seat or missing seat
- whether this is a capability gap, staffing gap, or approval gate

- [ ] **Step 5: Re-run the routing tests**

Run: `python -m pytest tests/industry/test_seat_gap_policy.py tests/kernel/test_main_brain_chat_service.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/industry/service_context.py src/copaw/industry/service_strategy.py src/copaw/industry/seat_gap_policy.py src/copaw/kernel/main_brain_chat_service.py tests/industry/test_seat_gap_policy.py tests/kernel/test_main_brain_chat_service.py
git commit -m "refactor: route work by capability-aware surfaces"
```

### Task 4: Make Supervision Visible Instead Of Implicit

**Files:**
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `console/src/api/modules/industry.ts`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.tsx`
- Modify: `console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `console/src/runtime/staffingGapPresentation.test.ts`

- [ ] **Step 1: Add failing read-model/UI tests for supervision state**

Add assertions that the runtime read surface can explicitly show:
- latest writeback result
- current backlog item selected into cycle
- assignment owner and status
- blocked reason when no seat/capability is ready
- latest agent report and synthesis outcome

- [ ] **Step 2: Run the backend/frontend focused tests**

Run: `python -m pytest tests/app/industry_api_parts/runtime_updates.py -q`
Run: `npm --prefix console exec vitest run src/runtime/staffingGapPresentation.test.ts`
Expected: FAIL on the new visibility expectations.

- [ ] **Step 3: Persist and expose supervision checkpoints**

Write or expose formal state transitions for:
- `writeback-recorded`
- `waiting-seat`
- `assignment-created`
- `execution-started`
- `report-received`
- `replan-requested`

- [ ] **Step 4: Render the same supervision chain in Runtime Center, Industry, and Agent Workbench**

The operator should be able to answer:
- Did the main brain understand the ask?
- Did it create backlog/cycle/assignment?
- Which agent is supposed to act?
- Is the blocker capability, staffing, confirmation, or execution failure?
- Has the main brain consumed the resulting report?

- [ ] **Step 5: Re-run the backend/frontend tests**

Run: `python -m pytest tests/app/industry_api_parts/runtime_updates.py -q`
Run: `npm --prefix console exec vitest run src/runtime/staffingGapPresentation.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/industry/service_lifecycle.py src/copaw/industry/service_runtime_views.py console/src/api/modules/industry.ts console/src/pages/Industry/index.tsx console/src/pages/RuntimeCenter/viewHelpers.tsx console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx tests/app/industry_api_parts/runtime_updates.py console/src/runtime/staffingGapPresentation.test.ts
git commit -m "feat: expose main brain supervision state"
```

### Task 5: Verification, Live Smoke, And Documentation Sync

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`
- Reference: `docs/superpowers/plans/2026-03-24-main-brain-cognitive-closure.md`
- Reference: `docs/superpowers/plans/2026-03-23-single-industry-autonomy-closure.md`

- [ ] **Step 1: Run the complete targeted backend suite**

Run:
`python -m pytest tests/kernel/test_query_execution_runtime.py tests/goals/test_goal_service_dispatch.py tests/industry/test_operating_cycle.py tests/industry/test_seat_gap_policy.py tests/app/test_runtime_center_task_delegation_api.py tests/app/test_console_channel.py tests/app/industry_api_parts/runtime_updates.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py -q`

Expected:
- all targeted runtime/autonomy tests pass
- no regression in delegation preview, console output, or main-brain routing

- [ ] **Step 2: Run the frontend visibility smoke**

Run:
`npm --prefix console exec vitest run src/runtime/staffingGapPresentation.test.ts`

Expected:
- PASS

- [ ] **Step 3: Restart the real backend and re-check live endpoints**

Smoke:
- `GET /api/system/info`
- `GET /api/runtime-center/industry`
- one real industry control-thread turn that should create backlog/cycle/assignment

Expected:
- no stale overload message caused by cold compiled siblings
- no GBK console crash
- no cross-context token reset error
- the new supervision/read-model states appear in API responses

- [ ] **Step 4: Update status docs with the new post-repair baseline**

Document:
- eager goal fan-out retired
- assignment-first execution envelope strengthened
- capability-aware surface routing enabled
- remaining open work, if any

- [ ] **Step 5: Commit**

```bash
git add TASK_STATUS.md V7_MAIN_BRAIN_AUTONOMY_PLAN.md
git commit -m "docs: record runtime autonomy repair baseline"
```

## Execution Order

1. Task 0: runtime hardening and live restart
2. Task 1: goal fan-out de-staging
3. Task 2: assignment-first execution closure
4. Task 3: capability-aware routing
5. Task 4: supervision visibility
6. Task 5: verification and doc sync

## Why This Order

- Task 0 removes live runtime noise that can invalidate every later observation.
- Task 1 fixes the biggest structural source of fake activity and delegation blockage.
- Task 2 makes the main brain/specialist split real at the execution envelope.
- Task 3 fixes the user's most important scalability objection: no durable app-name hardcoding.
- Task 4 makes the repaired chain visible so the operator can tell whether the main brain is truly supervising.
- Task 5 prevents declaring success while the real `8088` backend is still running old code or stale behavior.
