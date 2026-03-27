# Chat Runtime Governance And Thinking Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the chat page recover its send state after a completed reply, show only real pending approvals, and restore visible thinking blocks for main-brain chat turns.

**Architecture:** Fix the regression at the existing boundaries instead of replacing the chat container. Backend changes will tighten governance summary semantics and preserve reasoning blocks in `MainBrainChatService`; frontend changes will correct conversation status reduction so completed replies no longer keep the composer in stop mode.

**Tech Stack:** FastAPI/Python backend, React/TypeScript frontend, Vitest, pytest

---

### Task 1: Lock The Frontend Regression In Tests

**Files:**
- Modify: `console/src/pages/Chat/sessionApi/index.test.ts`
- Test: `console/src/pages/Chat/sessionApi/index.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
it("prefers completed response state over earlier in-progress chunks", async () => {
  mockedGetRuntimeConversation.mockResolvedValue(
    buildConversation("industry-chat:industry-v1-acme:execution-core", [
      { id: "user-1", role: "user", content: [{ type: "text", text: "继续" }] },
      { id: "resp-1", role: "assistant", status: "in_progress", content: [{ type: "text", text: "正在处理" }] },
      { id: "resp-1-final", role: "assistant", status: "completed", content: [{ type: "text", text: "已经完成" }] },
    ]) as Awaited<ReturnType<typeof api.getRuntimeConversation>>,
  );

  const session = await sessionApi.getSession("industry-chat:industry-v1-acme:execution-core");
  expect(session.messages[1]?.msgStatus).toBe("finished");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- console/src/pages/Chat/sessionApi/index.test.ts`
Expected: FAIL because the response card is still marked as generating/interrupted instead of finished.

- [ ] **Step 3: Write minimal implementation**

Update the response status reducer in `console/src/pages/Chat/sessionApi/index.ts` so terminal statuses win over stale `created/queued/in_progress` entries for the same grouped response.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- console/src/pages/Chat/sessionApi/index.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/Chat/sessionApi/index.ts console/src/pages/Chat/sessionApi/index.test.ts
git commit -m "fix: restore completed chat response state"
```

### Task 2: Lock Backend Governance And Thinking Regressions

**Files:**
- Modify: `tests/kernel/test_main_brain_chat_service.py`
- Modify: `tests/app/test_runtime_center_api.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/app/test_runtime_center_api.py`

- [ ] **Step 1: Write the failing tests**

```python
async def test_main_brain_chat_service_preserves_thinking_blocks_for_streaming_chunks():
    ...

def test_runtime_center_governance_status_counts_only_proposed_patches_as_pending_approvals():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/kernel/test_main_brain_chat_service.py tests/app/test_runtime_center_api.py -q`
Expected: FAIL because main-brain chat emits text-only messages and governance status still counts approved patches as pending approvals.

- [ ] **Step 3: Write minimal implementation**

Add thinking extraction/preservation inside `src/copaw/kernel/main_brain_chat_service.py` and tighten patch counting semantics in `src/copaw/kernel/governance.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/kernel/test_main_brain_chat_service.py tests/app/test_runtime_center_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/kernel/main_brain_chat_service.py src/copaw/kernel/governance.py tests/kernel/test_main_brain_chat_service.py tests/app/test_runtime_center_api.py
git commit -m "fix: restore chat thinking and approval counts"
```

### Task 3: Verify The Full Chat Fix Path

**Files:**
- Verify: `console/src/pages/Chat/sessionApi/index.ts`
- Verify: `src/copaw/kernel/main_brain_chat_service.py`
- Verify: `src/copaw/kernel/governance.py`

- [ ] **Step 1: Run targeted frontend tests**

Run: `npm test -- console/src/pages/Chat/sessionApi/index.test.ts`
Expected: PASS

- [ ] **Step 2: Run targeted backend tests**

Run: `pytest tests/kernel/test_main_brain_chat_service.py tests/app/test_runtime_center_api.py -q`
Expected: PASS

- [ ] **Step 3: Run combined regression spot-check**

Run: `npm test -- console/src/pages/Chat/sessionApi/index.test.ts && pytest tests/kernel/test_main_brain_chat_service.py tests/app/test_runtime_center_api.py -q`
Expected: PASS

- [ ] **Step 4: Review changed files for scope creep**

Confirm the diff only changes chat response status reduction, main-brain thinking preservation, and governance patch counting semantics.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-03-26-chat-runtime-governance-and-thinking-fixes.md
git commit -m "docs: add chat runtime bugfix plan"
```
