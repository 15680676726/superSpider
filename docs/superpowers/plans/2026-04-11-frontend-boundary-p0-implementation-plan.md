# Frontend Boundary P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pull the Buddy and Chat main path back to a real display flow by moving entry truth to the backend, making `/buddy/surface` read-only, and shrinking `/chat` to a lighter reader.

**Architecture:** Keep the current page structure, but stop frontend pages from deciding Buddy truth independently. Add one canonical backend Buddy entry result, consume it from the frontend entry points, and split the chat session contract so first paint can read thread/messages without dragging unrelated runtime metadata into every open.

**Tech Stack:** FastAPI, Python, React, TypeScript, React Router, Vitest, pytest

---

## File Map

- `src/copaw/app/routers/buddy_routes.py`
  Add a formal Buddy entry read contract and remove repair side effects from `GET /buddy/surface`.
- `src/copaw/app/runtime_center/conversations.py`
  Split or slim the chat conversation metadata returned to the frontend.
- `tests/app/test_buddy_routes.py`
  Backend route coverage for Buddy entry and read-only surface behavior.
- `tests/app/test_runtime_chat_thread_binding.py`
  Runtime chat route coverage for thread binding / entry shape.
- `console/src/runtime/buddyFlow.ts`
  Convert Buddy entry resolution to consume backend truth instead of local guessing.
- `console/src/runtime/buddyChatEntry.ts`
  Use canonical Buddy entry result to open chat or route to onboarding.
- `console/src/routes/entryRedirect.tsx`
  Use the single entry result instead of rebuilding the decision locally.
- `console/src/pages/BuddyOnboarding/index.tsx`
  Stop resuming flow from raw surface guesses once backend entry result exists.
- `console/src/pages/Chat/index.tsx`
  Keep chat focused on thread bootstrap + rendering, not Buddy truth decisions.
- `console/src/pages/Chat/sessionApi/index.ts`
  Consume lighter chat session payload.
- `console/src/pages/Chat/ChatAccessGate.tsx`
  Keep only the remaining true blockers.
- `console/src/runtime/buddyFlow.test.ts`
- `console/src/runtime/buddyChatEntry.test.ts`
- `console/src/routes/entryRedirect.test.tsx`
- `console/src/pages/Chat/index.entry.test.tsx`
- `console/src/pages/Chat/sessionApi/index.test.ts`

## Task 1: Make Buddy Entry Truth Backend-Owned

**Files:**
- Modify: `src/copaw/app/routers/buddy_routes.py`
- Test: `tests/app/test_buddy_routes.py`

- [ ] **Step 1: Write the failing backend tests**

Add coverage for:
- a dedicated Buddy entry read returning one canonical mode
- `/buddy/surface` no longer calling repair / retry logic during read

- [ ] **Step 2: Run the backend tests to verify failure**

Run: `python -m pytest tests/app/test_buddy_routes.py -q`
Expected: FAIL because the new Buddy entry contract does not exist yet or surface still triggers repair logic.

- [ ] **Step 3: Implement the minimal backend entry contract**

Implement these rules:
- add a formal Buddy entry read result, for example `start-onboarding / resume-onboarding / chat-ready`
- derive it from canonical backend truth, not frontend-local branching
- keep `/buddy/surface` a pure read path
- move repair/retry behavior out of `GET /buddy/surface`

- [ ] **Step 4: Run the backend tests again**

Run: `python -m pytest tests/app/test_buddy_routes.py -q`
Expected: PASS

## Task 2: Rewire Frontend Buddy Entry To Consume One Result

**Files:**
- Modify: `console/src/runtime/buddyFlow.ts`
- Modify: `console/src/runtime/buddyChatEntry.ts`
- Modify: `console/src/routes/entryRedirect.tsx`
- Modify: `console/src/pages/BuddyOnboarding/index.tsx`
- Test: `console/src/runtime/buddyFlow.test.ts`
- Test: `console/src/runtime/buddyChatEntry.test.ts`
- Test: `console/src/routes/entryRedirect.test.tsx`

- [ ] **Step 1: Write or update the failing frontend tests**

Add coverage for:
- frontend no longer inferring Buddy truth from raw surface alone
- entry redirect consuming the backend entry mode
- chat resume path consuming the backend entry mode

- [ ] **Step 2: Run the focused frontend tests to verify failure**

Run: `npm --prefix console test -- src/runtime/buddyFlow.test.ts src/runtime/buddyChatEntry.test.ts src/routes/entryRedirect.test.tsx`
Expected: FAIL because frontend still reconstructs the decision locally.

- [ ] **Step 3: Implement the minimal frontend rewiring**

Implement these rules:
- `buddyFlow.ts` becomes a thin mapper over backend entry payload
- `entryRedirect.tsx` consumes one canonical entry result
- `buddyChatEntry.ts` consumes one canonical entry result
- `BuddyOnboarding/index.tsx` stops using raw surface to choose between onboarding and chat when entry truth is available

- [ ] **Step 4: Run the focused frontend tests again**

Run: `npm --prefix console test -- src/runtime/buddyFlow.test.ts src/runtime/buddyChatEntry.test.ts src/routes/entryRedirect.test.tsx`
Expected: PASS

## Task 3: Shrink Chat To A Lighter Reader

**Files:**
- Modify: `src/copaw/app/runtime_center/conversations.py`
- Modify: `console/src/pages/Chat/sessionApi/index.ts`
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/ChatAccessGate.tsx`
- Test: `tests/app/test_runtime_chat_thread_binding.py`
- Test: `console/src/pages/Chat/index.entry.test.tsx`
- Test: `console/src/pages/Chat/sessionApi/index.test.ts`

- [ ] **Step 1: Write or update the failing tests**

Add coverage for:
- chat first paint can open from a canonical thread/session result
- non-message metadata is no longer required for first paint
- chat error gate only blocks on true entry failure, not every temporary recovery miss

- [ ] **Step 2: Run the tests to verify failure**

Run: `python -m pytest tests/app/test_runtime_chat_thread_binding.py -q`
Run: `npm --prefix console test -- src/pages/Chat/index.entry.test.tsx src/pages/Chat/sessionApi/index.test.ts`
Expected: FAIL because chat still depends on the heavier contract or still over-blocks.

- [ ] **Step 3: Implement the minimal chat contract shrink**

Implement these rules:
- backend conversation read keeps messages/thread truth first
- extra metadata becomes optional or separately attachable
- `sessionApi/index.ts` accepts the lighter payload
- `Chat/index.tsx` keeps thread bootstrap and rendering, but stops acting like the Buddy truth owner
- `ChatAccessGate.tsx` only blocks on real entry failure

- [ ] **Step 4: Run the focused tests again**

Run: `python -m pytest tests/app/test_runtime_chat_thread_binding.py -q`
Run: `npm --prefix console test -- src/pages/Chat/index.entry.test.tsx src/pages/Chat/sessionApi/index.test.ts`
Expected: PASS

## Task 4: Verify The P0 Main Path

**Files:**
- No new source files
- Reuse all touched test files

- [ ] **Step 1: Run consolidated backend verification**

Run: `python -m pytest tests/app/test_buddy_routes.py tests/app/test_runtime_chat_thread_binding.py -q`
Expected: PASS

- [ ] **Step 2: Run consolidated frontend verification**

Run: `npm --prefix console test -- src/runtime/buddyFlow.test.ts src/runtime/buddyChatEntry.test.ts src/routes/entryRedirect.test.tsx src/pages/Chat/index.entry.test.tsx src/pages/Chat/sessionApi/index.test.ts`
Expected: PASS

- [ ] **Step 3: Run production build**

Run: `npm --prefix console run build`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/copaw/app/routers/buddy_routes.py src/copaw/app/runtime_center/conversations.py tests/app/test_buddy_routes.py tests/app/test_runtime_chat_thread_binding.py console/src/runtime/buddyFlow.ts console/src/runtime/buddyChatEntry.ts console/src/routes/entryRedirect.tsx console/src/pages/BuddyOnboarding/index.tsx console/src/pages/Chat/index.tsx console/src/pages/Chat/ChatAccessGate.tsx console/src/pages/Chat/sessionApi/index.ts console/src/runtime/buddyFlow.test.ts console/src/runtime/buddyChatEntry.test.ts console/src/routes/entryRedirect.test.tsx console/src/pages/Chat/index.entry.test.tsx console/src/pages/Chat/sessionApi/index.test.ts
git commit -m "feat: harden buddy entry and slim chat front door"
```
