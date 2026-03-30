# Main-Brain Cognitive Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn CoPaw's main brain from a dispatcher with rich summaries into a true cognitive center that consumes structured report synthesis, carries a shared cognitive surface across chat/orchestration/UI, and closes the loop with explicit judgment and replan state.

**Architecture:** Keep the existing canonical chain `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport`, but add a shared typed cognitive surface on top of cycle/report state instead of flattening everything into prompt prose. The implementation should strengthen synthesis semantics, persist/resolve a durable main-brain conclusion payload, project it into Runtime Center and industry views, and lock the same-thread conclusion/replan path with regression tests.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite state services, pytest

---

## Scope Boundary

- This plan is only for `主脑 cognitive closure`.
- It must not start `主脑聊天性能硬化` or `重模块拆分`.
- The plan should close the current repo-defined gap in `TASK_STATUS.md 4.2`, not attempt to finish every future V7 object (`MainBrainCarrierRecord`, etc.) in one sweep.
- The implementation target is:
  - shared structured cognitive surface
  - richer synthesis semantics
  - durable replan/judgment state
  - visible operator/runtime closure
  - same-thread regression proving the main brain reaches a unified conclusion

## File Map

- Modify: `src/copaw/industry/report_synthesis.py`
  - Make `latest_findings` canonical and widen conflict/hole/replan semantics.
- Modify: `src/copaw/industry/service_strategy.py`
  - Persist stronger synthesis/replan truth into cycle/strategy-facing payloads.
- Modify: `src/copaw/industry/service_runtime_views.py`
  - Project structured synthesis/conclusion state into runtime/industry read models.
- Create: `src/copaw/industry/main_brain_cognitive_surface.py`
  - Shared builder for `latest_reports / synthesis / needs_replan / conclusion / next_action / follow-up`.
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
  - Inject the structured cognitive surface into pure chat prompts.
- Modify: `src/copaw/kernel/main_brain_orchestrator.py`
  - Carry the cognitive surface into runtime context / orchestration metadata.
- Modify: `src/copaw/kernel/turn_executor.py`
  - Route with awareness of unresolved cognitive state where needed.
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
  - Expose the main-brain conclusion and synthesis payload in the dedicated cockpit contract.
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
  - Render the richer cognitive surface rather than only counts/summary strips.
- Test: `tests/industry/test_report_synthesis.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/kernel/test_turn_executor.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`
- Test: `tests/app/test_phase_next_autonomy_smoke.py`

### Task 1: Strengthen Report Synthesis Semantics

**Files:**
- Modify: `src/copaw/industry/report_synthesis.py`
- Test: `tests/industry/test_report_synthesis.py`

- [ ] **Step 1: Write the failing synthesis tests**

Add tests for:
- latest findings collapsing to latest-per-topic/assignment/claim
- uncertainty-driven holes
- recommendation disagreement or insufficient-evidence conflicts
- durable `replan_decision` / `replan_directives` payload generation
- replan clear-down when a successful follow-up resolves prior pressure

- [ ] **Step 2: Run the synthesis tests to verify they fail**

Run: `python -m pytest tests/industry/test_report_synthesis.py -q`
Expected: FAIL because synthesis is still narrower than the target cognitive closure semantics.

- [ ] **Step 3: Implement the minimal synthesis changes**

Required outcome:
- canonical `latest_findings`
- wider conflict/hole detection
- explicit `replan_decision` payload
- resolution/clear-down semantics

- [ ] **Step 4: Run the synthesis tests again**

Run: `python -m pytest tests/industry/test_report_synthesis.py -q`
Expected: PASS

### Task 2: Build And Persist Shared Main-Brain Cognitive Surface

**Files:**
- Create: `src/copaw/industry/main_brain_cognitive_surface.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`

- [ ] **Step 1: Write the failing runtime/read-model tests**

Add tests for:
- typed cognitive surface containing:
  - `latest_reports`
  - `synthesis`
  - `needs_replan`
  - `replan_reasons`
  - `conclusion`
  - `next_action`
  - `followup_backlog`
- strategy/runtime read surfaces preserving that payload across rollover
- resolved follow-up clearing unresolved cognitive pressure

- [ ] **Step 2: Run the runtime/read-model tests to verify they fail**

Run: `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py -q`
Expected: FAIL because the read model does not yet expose a first-class cognitive surface.

- [ ] **Step 3: Implement the minimal cognitive-surface builder and projections**

Required outcome:
- one shared builder for cognitive state
- runtime and strategy surfaces consume that builder
- no ad hoc duplicated summary shaping

- [ ] **Step 4: Run the runtime/read-model tests again**

Run: `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py -q`
Expected: PASS

### Task 3: Main-Brain Chat And Orchestrator Consumption

**Files:**
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/main_brain_orchestrator.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/kernel/test_turn_executor.py`

- [ ] **Step 1: Write the failing chat/orchestrator tests**

Add tests for:
- pure chat consuming structured synthesis/replan state, not just shallow report prose
- orchestrator/runtime context carrying the same cognitive surface
- routing/behavior changing when unresolved conflicts or `needs_replan` is present

- [ ] **Step 2: Run the chat/orchestrator tests to verify they fail**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py -q`
Expected: FAIL because the main brain still lacks a shared typed cognitive surface in these paths.

- [ ] **Step 3: Implement the minimal consumer changes**

Required outcome:
- chat and orchestrator read the same cognitive surface
- the main brain can reason about unresolved report state programmatically
- no prompt-only fake closure remains

- [ ] **Step 4: Run the chat/orchestrator tests again**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py -q`
Expected: PASS

### Task 4: Runtime Center Cockpit And Operator Visibility

**Files:**
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`

- [ ] **Step 1: Write the failing cockpit tests**

Add tests for:
- `/runtime-center/main-brain` exposing:
  - `latest_findings`
  - `conflicts`
  - `holes`
  - `judgment`
  - `next_action`
  - `needs_replan`
  - `replan_reasons`
- operator-facing surface rendering rich report cognition, not only counts

- [ ] **Step 2: Run the cockpit tests to verify they fail**

Run: `python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q`
Expected: FAIL because the dedicated main-brain contract is still too thin.

- [ ] **Step 3: Implement the minimal cockpit changes**

Required outcome:
- dedicated main-brain API carries the cognitive surface
- Runtime Center cockpit renders the cognitive closure loop explicitly

- [ ] **Step 4: Run the cockpit tests again**

Run: `python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q`
Expected: PASS

### Task 5: Same-Thread End-To-End Cognitive Closure Regression

**Files:**
- Modify: `tests/app/test_phase_next_autonomy_smoke.py`

- [ ] **Step 1: Write the failing end-to-end cognitive-closure smoke**

Add one same-thread story that proves:
- operator request
- two or more report returns / conflict or hole detection
- main-brain unified conclusion
- visible replan/judgment on the same control thread
- follow-up resolution can clear or update that conclusion

- [ ] **Step 2: Run the new smoke to verify it fails**

Run: `python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q -k cognitive`
Expected: FAIL because the full same-thread cognitive closure is not yet locked.

- [ ] **Step 3: Implement the minimal glue needed for the smoke**

Required outcome:
- same-thread conclusion is no longer implicit
- regression proves the system acts as a cognitive center, not a dispatcher with rich summaries

- [ ] **Step 4: Run the smoke again**

Run: `python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q -k cognitive`
Expected: PASS

## Final Verification

- [ ] **Step 1: Run the focused closure suite**

Run: `python -m pytest tests/industry/test_report_synthesis.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_phase_next_autonomy_smoke.py -q`
Expected: PASS

- [ ] **Step 2: Run the wider linked regressions**

Run: `python -m pytest tests/kernel/test_memory_recall_integration.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_conversations_api.py tests/app/test_runtime_center_api.py -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/copaw/industry/report_synthesis.py src/copaw/industry/service_strategy.py src/copaw/industry/service_runtime_views.py src/copaw/industry/main_brain_cognitive_surface.py src/copaw/kernel/main_brain_chat_service.py src/copaw/kernel/main_brain_orchestrator.py src/copaw/kernel/turn_executor.py src/copaw/app/runtime_center/overview_cards.py console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx tests/industry/test_report_synthesis.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_phase_next_autonomy_smoke.py
git commit -m "feat: close main-brain cognitive loop"
```
