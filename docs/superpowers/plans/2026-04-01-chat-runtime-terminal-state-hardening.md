# Chat Runtime Terminal State Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/chat` converge on one terminal-state contract so the sent-message bubble, top runtime status rail, binding/blocking notice, and session readback all flip out of "still sending" once the reply has actually finished.

**Architecture:** Keep `POST /api/runtime-center/chat/run` as the only write ingress and do not redesign the current main-brain chat chain. Fix the regression at the frontend state boundary by introducing one pure chat runtime status reducer, wiring `runtimeTransport` to emit request-scoped lifecycle transitions instead of independent `setRuntimeWaitState` / `setRuntimeHealthNotice` mutations, and aligning `sessionApi` readback rules with the same terminal precedence. This plan intentionally excludes PowerShell/shell hardening; that is a separate subsystem and should get its own plan.

**Tech Stack:** React, TypeScript, Vitest, existing `@agentscope-ai/chat` adapter layer, current CoPaw `/runtime-center/chat/run` SSE path.

---

## Scope Guard

This plan covers only the chat runtime terminal-state bug and the frontend contracts that make it visible:

- active send/wait lifecycle in `runtimeTransport`
- terminal completion vs cleanup ordering
- binding/loading/blocked notice derivation
- top-bar runtime status presentation
- persisted transcript readback via `sessionApi`

This plan does **not** cover:

- shell / PowerShell permission hardening
- backend main-brain route redesign
- Runtime Center cockpit redesign outside `/chat`
- third-party dependency patching inside `node_modules`

## Root Cause Summary

Current `/chat` runtime state is split across too many local surfaces:

- `console/src/pages/Chat/runtimeTransport.ts`
  - mutates wait-state, health notice, dirty broadcasts, and cancel cleanup independently
- `console/src/pages/Chat/index.tsx`
  - derives top-bar state from separate `runtimeWaitState`, `runtimeHealthNotice`, and `noticeState`
- `console/src/pages/Chat/noticeState.ts`
  - only models `loading | binding | blocked | null`
- `console/src/pages/Chat/sessionApi/index.ts`
  - separately reduces persisted response-card status for transcript readback

That means the chat page currently has no single owner for:

- which request is active
- when a response is already terminal
- whether cleanup is allowed to clear or overwrite visible state
- how terminal response state should dominate older in-progress fragments

The visible symptom is exactly what the user reported: the backend reply has already completed, but the local chat surface is still showing "sending / waiting / generating" on at least one UI layer.

## File Map

### New files

- `console/src/pages/Chat/chatRuntimeStatus.ts`
  - Pure request-scoped lifecycle reducer and status precedence helpers for `/chat`.
- `console/src/pages/Chat/chatRuntimeStatus.test.ts`
  - Unit tests that lock terminal-state precedence, stale-patch rejection, and cleanup ordering.

### Existing files to modify

- `console/src/pages/Chat/runtimeTransport.ts`
  - Emit lifecycle actions into the unified reducer instead of directly mutating independent wait/notice state.
- `console/src/pages/Chat/useChatRuntimeState.ts`
  - Own the runtime status controller and pass reducer-backed callbacks into `runtimeTransport`.
- `console/src/pages/Chat/index.tsx`
  - Consume the unified runtime status surface instead of stitching together `runtimeWaitState`, `runtimeHealthNotice`, and minimal notice logic by hand.
- `console/src/pages/Chat/noticeState.ts`
  - Narrow this file to access-gate-only derivation or replace it with reducer-backed notice derivation.
- `console/src/pages/Chat/noticeState.test.ts`
  - Lock the new precedence semantics.
- `console/src/pages/Chat/ChatRuntimeSidebar.tsx`
  - Render top-bar status from one runtime status contract.
- `console/src/pages/Chat/ChatRuntimeSidebar.test.tsx`
  - Lock the new visible runtime states.
- `console/src/pages/Chat/runtimeDiagnostics.ts`
  - Keep text-formatting helpers only, or adapt it to the new reducer contract without owning state transitions.
- `console/src/pages/Chat/runtimeTransport.test.ts`
  - Add request-scoped terminal-state regression tests.
- `console/src/pages/Chat/sessionApi/index.ts`
  - Keep transcript readback aligned with terminal-state precedence.
- `console/src/pages/Chat/sessionApi/index.test.ts`
  - Lock transcript readback against stale generating state.

## Runtime Contract To Introduce

The new frontend contract should explicitly model:

- one active run at a time for the current chat thread
- a monotonically increasing `runId` or request token
- lifecycle phases:
  - `idle`
  - `waiting-model`
  - `streaming`
  - `completed`
  - `interrupted`
  - `error`
- non-run gate states:
  - `loading-thread`
  - `binding-thread`
  - `blocked-thread`

Rules:

- a newer `runId` always wins over older patches
- `completed / interrupted / error` are terminal for that `runId`
- cleanup may release transport resources after terminal state, but it may not demote visible status for the same or newer `runId`
- transcript readback must prefer terminal backend truth over longer local generating history
- the top bar and message bubble must be derived from the same terminal precedence, not from separate booleans

### Task 1: Lock The Actual Regression In Frontend Tests

**Files:**
- Create: `console/src/pages/Chat/chatRuntimeStatus.test.ts`
- Modify: `console/src/pages/Chat/runtimeTransport.test.ts`
- Modify: `console/src/pages/Chat/sessionApi/index.test.ts`
- Modify: `console/src/pages/Chat/noticeState.test.ts`
- Modify: `console/src/pages/Chat/ChatRuntimeSidebar.test.tsx`

- [ ] **Step 1: Write the failing reducer tests**

```ts
it("keeps completed visible when stale cleanup arrives for an older run", () => {
  const state = reduceChatRuntimeStatus(initialChatRuntimeStatus(), {
    type: "run-started",
    runId: 1,
    activeLabel: "provider/model",
    fallbackCount: 0,
  });
  const completed = reduceChatRuntimeStatus(state, {
    type: "run-terminal",
    runId: 1,
    outcome: "completed",
  });
  const staleCleanup = reduceChatRuntimeStatus(completed, {
    type: "run-cleanup",
    runId: 1,
  });
  expect(staleCleanup.phase).toBe("completed");
});

it("rejects older run patches after a newer run has started", () => {
  let state = reduceChatRuntimeStatus(initialChatRuntimeStatus(), {
    type: "run-started",
    runId: 1,
    activeLabel: "provider/model",
    fallbackCount: 0,
  });
  state = reduceChatRuntimeStatus(state, {
    type: "run-started",
    runId: 2,
    activeLabel: "provider/model",
    fallbackCount: 0,
  });
  state = reduceChatRuntimeStatus(state, {
    type: "run-terminal",
    runId: 1,
    outcome: "completed",
  });
  expect(state.runId).toBe(2);
  expect(state.phase).toBe("waiting-model");
});
```

- [ ] **Step 2: Write the failing transport tests**

```ts
it("marks the active run completed before transport cleanup executes", () => {
  ...
  expect(dispatchRuntimeStatus).toHaveBeenCalledWith(
    expect.objectContaining({ type: "run-terminal", outcome: "completed" }),
  );
  expect(dispatchRuntimeStatus).toHaveBeenCalledWith(
    expect.objectContaining({ type: "run-cleanup" }),
  );
});

it("does not let cancelSession clear a newer finished run", () => {
  ...
});
```

- [ ] **Step 3: Write the failing session readback test**

```ts
it("prefers terminal completed status over stale local generating transcript", async () => {
  ...
  expect(restored.messages[1]?.msgStatus).toBe("finished");
});
```

- [ ] **Step 4: Write the failing notice/sidebar tests**

```ts
it("shows completed runtime state instead of generic ready immediately after terminal response", () => {
  ...
});

it("derives blocked-thread only when chat ui is unavailable and no active run exists", () => {
  ...
});
```

- [ ] **Step 5: Run tests to verify they fail**

Run:

```powershell
npm --prefix console test -- chatRuntimeStatus.test.ts runtimeTransport.test.ts noticeState.test.ts ChatRuntimeSidebar.test.tsx sessionApi/index.test.ts
```

Expected: FAIL because the unified reducer does not exist yet and current transport/notice logic does not enforce terminal-before-cleanup precedence.

### Task 2: Introduce One Pure Chat Runtime Status Reducer

**Files:**
- Create: `console/src/pages/Chat/chatRuntimeStatus.ts`
- Test: `console/src/pages/Chat/chatRuntimeStatus.test.ts`

- [ ] **Step 1: Write the minimal reducer shape**

```ts
export type ChatRuntimePhase =
  | "idle"
  | "loading-thread"
  | "binding-thread"
  | "blocked-thread"
  | "waiting-model"
  | "streaming"
  | "completed"
  | "interrupted"
  | "error";

export interface ChatRuntimeStatusState {
  runId: number;
  phase: ChatRuntimePhase;
  activeLabel: string | null;
  fallbackCount: number;
  notice: RuntimeHealthNotice | null;
}

export type ChatRuntimeStatusAction =
  | { type: "thread-loading" }
  | { type: "thread-binding" }
  | { type: "thread-blocked" }
  | { type: "run-started"; runId: number; activeLabel: string; fallbackCount: number }
  | { type: "run-streaming"; runId: number }
  | { type: "run-terminal"; runId: number; outcome: "completed" | "interrupted" | "error"; notice?: RuntimeHealthNotice | null }
  | { type: "run-cleanup"; runId: number }
  | { type: "reset-idle" };
```

- [ ] **Step 2: Implement precedence rules**

Implement `reduceChatRuntimeStatus(...)` so that:

- older `runId` actions are ignored
- `run-cleanup` never demotes `completed / interrupted / error`
- `run-streaming` clears `waiting-model`
- terminal transitions own the last visible state until a new run or thread reset starts

- [ ] **Step 3: Add pure selectors**

```ts
export function selectSidebarRuntimeState(state: ChatRuntimeStatusState): {
  waitState: RuntimeWaitState | null;
  healthNotice: RuntimeHealthNotice | null;
  completedLabel: string | null;
} {
  ...
}

export function selectAccessGateNoticeVariant(state: ChatRuntimeStatusState): ChatNoticeVariant {
  ...
}
```

- [ ] **Step 4: Run reducer tests**

Run:

```powershell
npm --prefix console test -- chatRuntimeStatus.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add console/src/pages/Chat/chatRuntimeStatus.ts console/src/pages/Chat/chatRuntimeStatus.test.ts
git commit -m "feat: add chat runtime terminal state reducer"
```

### Task 3: Rewire `runtimeTransport` And `/chat` UI To Use The Reducer

**Files:**
- Modify: `console/src/pages/Chat/runtimeTransport.ts`
- Modify: `console/src/pages/Chat/useChatRuntimeState.ts`
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/noticeState.ts`
- Modify: `console/src/pages/Chat/ChatRuntimeSidebar.tsx`
- Modify: `console/src/pages/Chat/runtimeDiagnostics.ts`
- Test: `console/src/pages/Chat/runtimeTransport.test.ts`
- Test: `console/src/pages/Chat/noticeState.test.ts`
- Test: `console/src/pages/Chat/ChatRuntimeSidebar.test.tsx`

- [ ] **Step 1: Replace direct wait/health setters with reducer actions**

Thread one `dispatchRuntimeStatus(action)` callback through `createRuntimeTransport(...)` and remove the independent state ownership from:

- `beginRuntimeWait(...)`
- `parseRuntimeResponseChunk(...)`
- request error handling
- `cancelSession(...)`

- [ ] **Step 2: Introduce request-scoped run IDs**

Use a monotonic counter per transport instance:

```ts
let nextRunId = 1;
const activeRunBySession = new Map<string, number>();
```

Each outgoing request should:

- allocate a fresh `runId`
- dispatch `run-started`
- dispatch `run-streaming` on first real response chunk
- dispatch `run-terminal` on terminal response or error
- dispatch `run-cleanup` only after transport resources are released

- [ ] **Step 3: Re-derive sidebar and access-gate state from the reducer**

`index.tsx` should stop hand-assembling:

- `runtimeWaitState`
- `runtimeHealthNotice`
- `chatNoticeVariant`

from separate local sources, and instead consume the reducer selectors.

- [ ] **Step 4: Make the sidebar show a real terminal state**

`ChatRuntimeSidebar.tsx` should distinguish:

- waiting for model
- actively streaming
- terminal completed
- interrupted terminal
- error terminal

instead of collapsing every non-wait / non-error state back to the generic ready badge immediately.

- [ ] **Step 5: Run the targeted UI tests**

Run:

```powershell
npm --prefix console test -- runtimeTransport.test.ts noticeState.test.ts ChatRuntimeSidebar.test.tsx
```

Expected: PASS

- [ ] **Step 6: Commit**

```powershell
git add console/src/pages/Chat/runtimeTransport.ts console/src/pages/Chat/useChatRuntimeState.ts console/src/pages/Chat/index.tsx console/src/pages/Chat/noticeState.ts console/src/pages/Chat/ChatRuntimeSidebar.tsx console/src/pages/Chat/runtimeDiagnostics.ts console/src/pages/Chat/runtimeTransport.test.ts console/src/pages/Chat/noticeState.test.ts console/src/pages/Chat/ChatRuntimeSidebar.test.tsx
git commit -m "fix: unify chat runtime terminal state"
```

### Task 4: Align `sessionApi` Transcript Readback With The Same Terminal Precedence

**Files:**
- Modify: `console/src/pages/Chat/sessionApi/index.ts`
- Modify: `console/src/pages/Chat/sessionApi/index.test.ts`

- [ ] **Step 1: Tighten response-status reduction**

Keep `resolveResponseStatus(...)` and merge rules aligned with terminal precedence:

- terminal statuses beat older in-progress chunks
- fetched backend terminal transcript beats longer local generating transcript when user/assistant shape still matches one completed turn
- `completed_at` is only omitted for genuinely generating bubbles

- [ ] **Step 2: Tighten fetched-vs-existing merge semantics**

Re-check `shouldPreferFetchedMessages(...)` against the new reducer assumptions so that:

- terminal backend truth can replace stale local generating state
- active local in-flight state still wins when backend is genuinely behind

- [ ] **Step 3: Run session API regression tests**

Run:

```powershell
npm --prefix console test -- sessionApi/index.test.ts
```

Expected: PASS

- [ ] **Step 4: Commit**

```powershell
git add console/src/pages/Chat/sessionApi/index.ts console/src/pages/Chat/sessionApi/index.test.ts
git commit -m "fix: align chat transcript terminal precedence"
```

### Task 5: Run The Focused Chat Runtime Regression Gate

**Files:**
- Verify: `console/src/pages/Chat/chatRuntimeStatus.ts`
- Verify: `console/src/pages/Chat/runtimeTransport.ts`
- Verify: `console/src/pages/Chat/index.tsx`
- Verify: `console/src/pages/Chat/sessionApi/index.ts`

- [ ] **Step 1: Run the targeted frontend regression set**

Run:

```powershell
npm --prefix console test -- chatRuntimeStatus.test.ts runtimeTransport.test.ts noticeState.test.ts ChatRuntimeSidebar.test.tsx sessionApi/index.test.ts ChatComposerAdapter.test.tsx
```

Expected: PASS

- [ ] **Step 2: Run the chat-page-adjacent smoke tests already in repo**

Run:

```powershell
npm --prefix console test -- useRuntimeBinding.test.ts chatBindingRecovery.test.ts chatRuntimePresentation.test.ts
```

Expected: PASS

- [ ] **Step 3: Run a production build**

Run:

```powershell
npm --prefix console run build
```

Expected: PASS

- [ ] **Step 4: Manual verification**

Verify in `/chat`:

- send one plain chat turn
- confirm the assistant finishes
- confirm the message bubble leaves generating state
- confirm the top status rail leaves waiting state
- confirm a follow-up send starts a new run cleanly
- confirm refresh / remount still shows the finished transcript

- [ ] **Step 5: Commit**

```powershell
git add docs/superpowers/plans/2026-04-01-chat-runtime-terminal-state-hardening.md
git commit -m "docs: add chat runtime terminal state hardening plan"
```

## Follow-Up Plan Needed Separately

After this chat-runtime plan is green, write a separate implementation plan for the other validated `cc` borrowing gap:

- PowerShell / shell safety hardening

Candidate scope for that second plan:

- `src/copaw/agents/tools/shell.py`
- lower execution contract / permission semantics
- git-path / read-only / destructive-command hardening
- evidence-compatible shell result contract
