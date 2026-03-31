# Main-Brain Chat Performance Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the main-brain chat chain materially lighter and more stable by cutting prompt/context bloat, reducing snapshot/persistence overhead, tightening chat/orchestrate boundaries, trimming frontend binding/runtime transport churn, and locking these behaviors with regressions.

**Architecture:** Keep `MainBrainChatService` as the lightweight pure-chat chain and keep orchestration in `MainBrainOrchestrator`, but add caching/thinning at the prompt/session layer so pure chat no longer rebuilds oversized context on every turn. Frontend chat should stay bound to the correct runtime thread with less churn, and the tests must lock the performance-sensitive boundaries so the chat chain cannot quietly grow heavy again.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, React, TypeScript, Vitest

---

## Scope Boundary

- This plan is only for `主脑聊天性能硬化`.
- It must not start `重模块拆分`.
- It may refine `MainBrainChatService`, `KernelTurnExecutor`, and Chat frontend runtime binding/transport, but it must not undo the already-landed cognitive closure work.

## File Map

- Modify: `src/copaw/kernel/main_brain_chat_service.py`
  - Cut repeated prompt assembly and reduce redundant context work.
- Modify: `src/copaw/kernel/turn_executor.py`
  - Keep chat/orchestrate separation cheap and deterministic.
- Modify: `tests/kernel/test_main_brain_chat_service.py`
- Modify: `tests/kernel/test_turn_executor.py`
- Modify: `src/copaw/kernel/main_brain_orchestrator.py` only if a tiny support hook is needed for the chat split
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/useRuntimeBinding.ts`
- Modify: `console/src/pages/Chat/runtimeTransport.ts`
- Modify: `console/src/pages/Chat/chatBindingRecovery.ts`
- Modify: `console/src/pages/Chat/*.test.ts*` only as needed
- Modify: `tests/app/test_runtime_conversations_api.py`
- Modify: `tests/app/test_runtime_bootstrap_split.py`
- Modify: `TASK_STATUS.md`

### Task 1: Slim Pure-Chat Prompt And Context Assembly

**Files:**
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `tests/kernel/test_main_brain_chat_service.py`

- [ ] **Step 1: Write the failing prompt-weight tests**

Add tests for:
- pure chat not rebuilding the heaviest detail/roster/cognitive sections more than needed per session
- repeated turns reusing cached prompt context when runtime truth has not materially changed
- history trimming and context shaping staying bounded

- [ ] **Step 2: Run the prompt-weight tests to verify they fail**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py -q`
Expected: FAIL because prompt/context assembly is still too eager and unbounded.

- [ ] **Step 3: Implement the minimal prompt/context slimming**

Required outcome:
- prompt assembly is cached or incrementally rebuilt
- pure chat avoids redundant heavy detail shaping
- context stays bounded without dropping the required cognitive surface

- [ ] **Step 4: Run the prompt-weight tests again**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py -q`
Expected: PASS

### Task 2: Reduce Snapshot And Persistence Overhead

**Files:**
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `tests/kernel/test_main_brain_chat_service.py`

- [ ] **Step 1: Write the failing persistence tests**

Add tests for:
- fewer unnecessary snapshot saves during normal pure-chat turns
- no duplicate save paths for the same reply lifecycle
- interrupted turns still persist enough continuity while normal turns stay lean

- [ ] **Step 2: Run the persistence tests to verify they fail**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py -q -k \"snapshot or persist or cache\"`
Expected: FAIL because session persistence still does too much work per turn.

- [ ] **Step 3: Implement the minimal snapshot/persistence slimming**

Required outcome:
- normal pure chat does not over-save
- interruption safety is preserved
- cache reuse is explicit and test-covered

- [ ] **Step 4: Run the persistence tests again**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py -q -k \"snapshot or persist or cache\"`
Expected: PASS

### Task 3: Tighten Chat/Orchestrate Routing Cost

**Files:**
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `tests/kernel/test_turn_executor.py`

- [ ] **Step 1: Write the failing routing-cost tests**

Add tests for:
- pure chat acknowledgements and minor follow-ups staying in chat when no execution is needed
- auto mode not doing unnecessary heavy routing work when the answer is obviously chat
- cached mode handling not reintroducing orchestration churn

- [ ] **Step 2: Run the routing tests to verify they fail**

Run: `python -m pytest tests/kernel/test_turn_executor.py -q`
Expected: FAIL because some chat-path routing still does more than necessary.

- [ ] **Step 3: Implement the minimal routing hardening**

Required outcome:
- chat stays cheap by default
- orchestration still triggers when it truly should
- no extra runtime work is paid for plain chat turns

- [ ] **Step 4: Run the routing tests again**

Run: `python -m pytest tests/kernel/test_turn_executor.py -q`
Expected: PASS

### Task 4: Trim Frontend Binding And Transport Churn

**Files:**
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/useRuntimeBinding.ts`
- Modify: `console/src/pages/Chat/runtimeTransport.ts`
- Modify: `console/src/pages/Chat/chatBindingRecovery.ts`
- Modify: related Chat frontend tests as needed

- [ ] **Step 1: Write the failing frontend tests**

Add tests for:
- unnecessary rebind/reset loops not firing repeatedly
- runtime transport request body staying minimal
- chat page not deriving heavyweight state redundantly on routine updates

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run: `cmd /c npm --prefix console test -- useRuntimeBinding.test.ts runtimeTransport.test.ts chatBindingRecovery.test.ts`
Expected: FAIL because current binding/transport still allows avoidable churn.

- [ ] **Step 3: Implement the minimal frontend slimming**

Required outcome:
- fewer rebind churn paths
- smaller/more stable transport assembly
- chat page remains responsive without product regressions

- [ ] **Step 4: Run the frontend tests again**

Run: `cmd /c npm --prefix console test -- useRuntimeBinding.test.ts runtimeTransport.test.ts chatBindingRecovery.test.ts`
Expected: PASS

### Task 5: Lock Perf/Interaction Regression Guards

**Files:**
- Modify: `tests/app/test_runtime_conversations_api.py`
- Modify: `tests/app/test_runtime_bootstrap_split.py`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Write the failing regression guards**

Add tests for:
- runtime conversations not regressing into oversized or duplicated main-brain chat state
- bootstrap/runtime wiring preserving the lightweight chat chain
- status board wording reflecting the hardened state once done

- [ ] **Step 2: Run the regression-guard tests to verify they fail**

Run: `python -m pytest tests/app/test_runtime_conversations_api.py tests/app/test_runtime_bootstrap_split.py -q`
Expected: FAIL if the lightweight chat chain is not yet locked tightly enough.

- [ ] **Step 3: Implement the minimal regression/documentation changes**

Required outcome:
- linked regressions lock the hardened chat chain
- status board no longer leaves the same undefined performance gap once implementation lands

- [ ] **Step 4: Run the regression-guard tests again**

Run: `python -m pytest tests/app/test_runtime_conversations_api.py tests/app/test_runtime_bootstrap_split.py -q`
Expected: PASS

## Final Verification

- [ ] **Step 1: Run the backend hardening suite**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py tests/app/test_runtime_conversations_api.py tests/app/test_runtime_bootstrap_split.py -q`
Expected: PASS

- [ ] **Step 2: Run the frontend hardening suite**

Run: `cmd /c npm --prefix console test -- MainBrainCockpitPanel.test.tsx useRuntimeBinding.test.ts runtimeTransport.test.ts chatBindingRecovery.test.ts`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/copaw/kernel/main_brain_chat_service.py src/copaw/kernel/turn_executor.py console/src/pages/Chat/index.tsx console/src/pages/Chat/useRuntimeBinding.ts console/src/pages/Chat/runtimeTransport.ts console/src/pages/Chat/chatBindingRecovery.ts tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py tests/app/test_runtime_conversations_api.py tests/app/test_runtime_bootstrap_split.py TASK_STATUS.md
git commit -m "perf: harden main-brain chat path"
```
