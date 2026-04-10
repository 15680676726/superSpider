# Frontend Main Flow Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reset the frontend main path so onboarding finishes cleanly, chat behaves like chat, the right panel becomes passive, and route switches stop doing unrelated work.

**Architecture:** Keep the existing shell and page structure, but hard-cut page responsibilities. Work directly on `main` per user instruction, preserve onboarding step-1 content, and keep the likely-conflicting changes concentrated in the onboarding page flow and tests instead of spreading them across unrelated files.

**Tech Stack:** React, TypeScript, React Router, Ant Design, Vitest, Testing Library

---

## File Map

- `console/src/pages/BuddyOnboarding/index.tsx`
  Main onboarding flow. This is where step order, save-and-resume, back navigation, naming, and enter-chat behavior will be reset.
- `console/src/pages/BuddyOnboarding/index.test.tsx`
  Main regression coverage for onboarding flow.
- `console/src/pages/BuddyOnboarding/draftState.ts`
  New focused helper for local draft save/load/clear so the large onboarding page does not absorb storage logic.
- `console/src/pages/BuddyOnboarding/draftState.test.ts`
  Tests for the draft helper.
- `console/src/pages/Chat/index.tsx`
  Remove naming from chat, keep chat-first rendering, and stop non-chat gating from blocking the page.
- `console/src/pages/Chat/ChatAccessGate.tsx`
  Keep only the single allowed blocker: no profile.
- `console/src/pages/Chat/index.test.tsx`
  New chat page regression coverage for “profile exists => chat opens”.
- `console/src/layouts/RightPanel/index.tsx`
  Keep current content, but fix visibility, refresh timing, and failure isolation.
- `console/src/layouts/RightPanel/index.test.tsx`
  Regression coverage for right-panel timing and refresh.
- `console/src/routes/preload.ts`
  Remove whole-app preload behavior.
- `console/src/routes/preload.test.ts`
  Regression coverage for route preload restrictions.
- `console/src/layouts/MainLayout/index.tsx`
  Keep the shell stable and only let the middle content switch.

## Task 1: Add Onboarding Draft Persistence Helper

**Files:**
- Create: `console/src/pages/BuddyOnboarding/draftState.ts`
- Create: `console/src/pages/BuddyOnboarding/draftState.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import {
  clearBuddyOnboardingDraft,
  loadBuddyOnboardingDraft,
  saveBuddyOnboardingDraft,
} from "./draftState";

describe("draftState", () => {
  it("round-trips the onboarding draft", () => {
    saveBuddyOnboardingDraft({
      identity: { display_name: "Alex" },
      naming: { buddy_name: "Nova" },
      step: 2,
    });

    expect(loadBuddyOnboardingDraft()).toEqual({
      identity: { display_name: "Alex" },
      naming: { buddy_name: "Nova" },
      step: 2,
    });

    clearBuddyOnboardingDraft();
    expect(loadBuddyOnboardingDraft()).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix console test -- src/pages/BuddyOnboarding/draftState.test.ts`
Expected: FAIL because `draftState.ts` does not exist yet

- [ ] **Step 3: Write minimal implementation**

```ts
const STORAGE_KEY = "copaw.buddy_onboarding_draft";

export function loadBuddyOnboardingDraft() {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function saveBuddyOnboardingDraft(value: unknown) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
}

export function clearBuddyOnboardingDraft() {
  window.localStorage.removeItem(STORAGE_KEY);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix console test -- src/pages/BuddyOnboarding/draftState.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/BuddyOnboarding/draftState.ts console/src/pages/BuddyOnboarding/draftState.test.ts
git commit -m "test: add onboarding draft state helper"
```

## Task 2: Reset Onboarding To Three Steps And Finish Naming Before Chat

**Files:**
- Modify: `console/src/pages/BuddyOnboarding/index.tsx`
- Modify: `console/src/pages/BuddyOnboarding/index.test.tsx`
- Modify: `console/src/api/modules/buddy.ts`
- Use: `console/src/pages/BuddyOnboarding/draftState.ts`

- [ ] **Step 1: Write the failing test for the new flow**

```tsx
it("keeps step 1 content, uses naming as step 3, and only enters chat after explicit confirmation", async () => {
  render(<BuddyOnboardingPage />);

  expect(await screen.findByTestId("buddy-identity-form")).toBeInTheDocument();

  fireEvent.change(screen.getByTestId("buddy-identity-display-name"), {
    target: { value: "Alex" },
  });

  fireEvent.click(screen.getByTestId("buddy-step-next"));
  fireEvent.click(screen.getByTestId("buddy-step-back"));

  expect(screen.getByDisplayValue("Alex")).toBeInTheDocument();

  fireEvent.change(screen.getByTestId("buddy-name-input"), {
    target: { value: "Nova" },
  });
  fireEvent.click(screen.getByTestId("buddy-start-chat"));

  expect(apiMock.nameBuddy).toHaveBeenCalledWith({
    session_id: "session-1",
    buddy_name: "Nova",
  });
  expect(runtimeChatMock.openRuntimeChat).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix console test -- src/pages/BuddyOnboarding/index.test.tsx`
Expected: FAIL because step 3 naming and explicit start-chat behavior do not exist yet

- [ ] **Step 3: Write minimal implementation**

```tsx
const stepItems = [
  { title: "身份建档" },
  { title: "方向确认" },
  { title: "伙伴命名" },
];

const [draft, setDraft] = useState(loadBuddyOnboardingDraft());
const [buddyNameDraft, setBuddyNameDraft] = useState(
  draft?.naming?.buddy_name ?? "",
);

async function handleStartChat() {
  setSubmitting(true);
  await api.nameBuddy({
    session_id: confirmPayload.session.session_id,
    buddy_name: buddyNameDraft.trim(),
  });
  clearBuddyOnboardingDraft();
  await openRuntimeChat(binding, navigate);
}
```

- [ ] **Step 4: Keep step-1 content unchanged and narrow the conflict surface**

Implement these rules inside `index.tsx`:

- keep the current identity form fields and copy
- keep the current direction-confirm content as the middle step
- replace “enter chat and name buddy there” with “name buddy here, then explicit `开始聊天`”
- save after each meaningful change through `draftState.ts`
- allow going back from step 2 to step 1 and from step 3 to step 2
- keep the user on onboarding while waiting for final creation / chat binding

- [ ] **Step 5: Run test to verify it passes**

Run: `npm --prefix console test -- src/pages/BuddyOnboarding/index.test.tsx src/pages/BuddyOnboarding/draftState.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add console/src/pages/BuddyOnboarding/index.tsx console/src/pages/BuddyOnboarding/index.test.tsx console/src/api/modules/buddy.ts console/src/pages/BuddyOnboarding/draftState.ts console/src/pages/BuddyOnboarding/draftState.test.ts
git commit -m "feat: finish buddy naming inside onboarding"
```

## Task 3: Slim Chat To Chat-Only Front Door

**Files:**
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/ChatAccessGate.tsx`
- Create: `console/src/pages/Chat/index.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
it("opens the chat shell when a profile exists and does not ask for buddy naming", async () => {
  render(<ChatPage />);

  expect(await screen.findByTestId("chat-page-shell")).toBeInTheDocument();
  expect(screen.queryByText(/给伙伴起名/)).toBeNull();
  expect(screen.queryByRole("dialog")).toBeNull();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix console test -- src/pages/Chat/index.test.tsx src/pages/Chat/ChatAccessGate.test.tsx`
Expected: FAIL because chat still contains naming and extra gate behavior

- [ ] **Step 3: Write minimal implementation**

```tsx
const shouldBlockForIdentity = !buddyProfileId;

if (shouldBlockForIdentity) {
  return <ChatAccessGate onOpenIdentityCenter={openIdentityCenter} ... />;
}

return (
  <div data-testid="chat-page-shell">
    <MessageList />
    <Composer />
  </div>
);
```

- [ ] **Step 4: Remove non-chat blockers from the first paint**

Implement these rules in `index.tsx`:

- remove buddy naming UI from chat
- render message area and composer before nonessential side work
- keep only the single blocker: no profile
- move progress display to above the latest reply
- keep one `查看详情` entry and no extra recommendation or onboarding carry-over cards

- [ ] **Step 5: Run test to verify it passes**

Run: `npm --prefix console test -- src/pages/Chat/index.test.tsx src/pages/Chat/ChatAccessGate.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add console/src/pages/Chat/index.tsx console/src/pages/Chat/ChatAccessGate.tsx console/src/pages/Chat/index.test.tsx
git commit -m "feat: slim chat to chat-only front door"
```

## Task 4: Make The Right Panel Passive And Timed

**Files:**
- Modify: `console/src/layouts/RightPanel/index.tsx`
- Modify: `console/src/layouts/RightPanel/index.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
it("refreshes panel data every 5 minutes without blocking the main page", async () => {
  vi.useFakeTimers();
  render(
    <MemoryRouter initialEntries={["/chat"]}>
      <RightPanel />
    </MemoryRouter>,
  );

  await waitFor(() => {
    expect(apiMock.getBuddySurface).toHaveBeenCalledTimes(1);
  });

  vi.advanceTimersByTime(300000);

  await waitFor(() => {
    expect(apiMock.getBuddySurface).toHaveBeenCalledTimes(2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix console test -- src/layouts/RightPanel/index.test.tsx`
Expected: FAIL because the panel does not do 5-minute refresh yet

- [ ] **Step 3: Write minimal implementation**

```tsx
useEffect(() => {
  if (!shouldShowPanel) return;

  void loadSurface();
  const timer = window.setInterval(() => {
    void loadSurface();
  }, 300000);

  return () => window.clearInterval(timer);
}, [shouldShowPanel, loadSurface]);
```

- [ ] **Step 4: Keep failure isolation**

Implement these rules in `index.tsx`:

- no profile => return empty state without loading
- has profile => show panel and load in the background
- if `getBuddySurface` fails, keep the panel isolated and do not throw into the main layout
- keep the avatar animation timer separate from the data refresh timer

- [ ] **Step 5: Run test to verify it passes**

Run: `npm --prefix console test -- src/layouts/RightPanel/index.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add console/src/layouts/RightPanel/index.tsx console/src/layouts/RightPanel/index.test.tsx
git commit -m "feat: make right panel passive and timed"
```

## Task 5: Remove Whole-App Route Preload

**Files:**
- Modify: `console/src/routes/preload.ts`
- Modify: `console/src/routes/preload.test.ts`
- Modify: `console/src/layouts/MainLayout/index.tsx`

- [ ] **Step 1: Write the failing test**

```ts
it("does not resolve unrelated route preload targets during normal route switching", () => {
  const routes: PreloadableRouteConfig[] = [
    { path: "/chat", preload: vi.fn() },
    { path: "/runtime-center", preload: vi.fn() },
  ];

  expect(resolveRoutePreloadPaths(routes, "/chat")).toEqual([]);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix console test -- src/routes/preload.test.ts`
Expected: FAIL because the current helper still returns unrelated pages

- [ ] **Step 3: Write minimal implementation**

```ts
export function resolveRoutePreloadPaths() {
  return [];
}
```

- [ ] **Step 4: Update layout usage**

Implement these rules:

- remove the “every route change triggers preload scheduling” behavior from `MainLayout`
- keep route switching focused on rendering the current page
- keep fallback behavior local to the route content area instead of blanking the whole shell

- [ ] **Step 5: Run test to verify it passes**

Run: `npm --prefix console test -- src/routes/preload.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add console/src/routes/preload.ts console/src/routes/preload.test.ts console/src/layouts/MainLayout/index.tsx
git commit -m "fix: stop whole-app route preload"
```

## Task 6: Final Frontend Regression Sweep

**Files:**
- Verify: `console/src/pages/BuddyOnboarding/index.test.tsx`
- Verify: `console/src/pages/BuddyOnboarding/draftState.test.ts`
- Verify: `console/src/pages/Chat/index.test.tsx`
- Verify: `console/src/pages/Chat/ChatAccessGate.test.tsx`
- Verify: `console/src/layouts/RightPanel/index.test.tsx`
- Verify: `console/src/routes/preload.test.ts`

- [ ] **Step 1: Run the focused test suite**

Run:

```bash
npm --prefix console test -- src/pages/BuddyOnboarding/index.test.tsx src/pages/BuddyOnboarding/draftState.test.ts src/pages/Chat/index.test.tsx src/pages/Chat/ChatAccessGate.test.tsx src/layouts/RightPanel/index.test.tsx src/routes/preload.test.ts
```

Expected: PASS

- [ ] **Step 2: Run a quick production build check**

Run:

```bash
npm --prefix console build
```

Expected: build completes successfully

- [ ] **Step 3: Commit**

```bash
git add console
git commit -m "test: verify frontend main flow reset"
```
