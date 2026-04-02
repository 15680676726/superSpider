# Main Brain Shell Surface Visibility Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the single-window `intent_shell` surface readable to operators by replacing raw debug-style trigger text with stable, human-friendly display text.

**Architecture:** Keep the backend payload unchanged and derive display-friendly shell metadata in the existing chat-side sidecar state. Reuse the current shell card and sidebar instead of adding a new panel or state source.

**Tech Stack:** React, TypeScript, Vitest, existing chat runtime sidecar state

---

### Task 1: Derive Human-Friendly Shell Display Metadata

**Files:**
- Modify: `console/src/pages/Chat/runtimeSidecarEvents.ts`
- Test: `console/src/pages/Chat/runtimeSidecarEvents.test.ts`

- [ ] **Step 1: Tighten the existing sidecar intent-shell test**

Update the current `intent_shell` reducer coverage so it asserts derived display text for:

- trigger source label
- matched-text label
- confidence percent label

- [ ] **Step 2: Run the focused reducer test to verify failure**

Run:

```powershell
cmd /c npm --prefix D:\word\copaw\.worktrees\main-brain-single-loop-chat\console test -- runtimeSidecarEvents.test.ts
```

Expected: the updated assertions fail because the reducer does not yet expose display-friendly shell metadata.

- [ ] **Step 3: Implement minimal derived display fields**

Update `runtimeSidecarEvents.ts` to derive stable display text from the existing payload without changing backend contracts.

- [ ] **Step 4: Re-run the focused reducer test**

Run:

```powershell
cmd /c npm --prefix D:\word\copaw\.worktrees\main-brain-single-loop-chat\console test -- runtimeSidecarEvents.test.ts
```

Expected: the focused reducer test passes.

### Task 2: Replace Raw Debug Strings In Shell UI

**Files:**
- Modify: `console/src/pages/Chat/ChatIntentShellCard.tsx`
- Modify: `console/src/pages/Chat/ChatRuntimeSidebar.tsx`
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/runtimeSidecarEvents.ts`
- Test: `console/src/pages/Chat/ChatIntentShellCard.test.tsx`
- Test: `console/src/pages/Chat/ChatRuntimeSidebar.test.tsx`
- Test: `console/src/pages/Chat/runtimeSidecarEvents.test.ts`

- [ ] **Step 1: Tighten the existing shell card and sidebar tests**

Update current tests so they assert:

- shell card shows readable source / match / confidence text
- the page-level shell hint formatter uses readable shell summary instead of raw `trigger=...`
- the sidebar derives shell label / hint from `runtimeIntentShell` instead of accepting raw debug strings from the page
- raw `trigger=` / `match=` / `confidence=` fragments are absent from the shell UI path

- [ ] **Step 2: Run the focused frontend tests to verify failure**

Run:

```powershell
cmd /c npm --prefix D:\word\copaw\.worktrees\main-brain-single-loop-chat\console test -- ChatIntentShellCard.test.tsx runtimeSidecarEvents.test.ts
```

Expected: one or more assertions fail because the current UI still renders raw debug-style strings.

- [ ] **Step 3: Implement minimal UI hardening**

Update the existing shell card and sidebar to use the derived display metadata and keep the single-window shell surface compact.

- [ ] **Step 4: Re-run focused UI tests**

Run:

```powershell
cmd /c npm --prefix D:\word\copaw\.worktrees\main-brain-single-loop-chat\console test -- ChatIntentShellCard.test.tsx runtimeSidecarEvents.test.ts
```

Expected: focused UI tests pass.

- [ ] **Step 5: Run cross-file frontend regression**

Run:

```powershell
cmd /c npm --prefix D:\word\copaw\.worktrees\main-brain-single-loop-chat\console test -- runtimeSidecarEvents.test.ts ChatIntentShellCard.test.tsx ChatRuntimeSidebar.test.tsx
```

Expected: all shell-surface frontend tests pass.

- [ ] **Step 6: Commit**

```bash
git add console/src/pages/Chat/runtimeSidecarEvents.ts console/src/pages/Chat/ChatIntentShellCard.tsx console/src/pages/Chat/ChatRuntimeSidebar.tsx console/src/pages/Chat/index.tsx console/src/pages/Chat/runtimeSidecarEvents.test.ts console/src/pages/Chat/ChatIntentShellCard.test.tsx console/src/pages/Chat/ChatRuntimeSidebar.test.tsx docs/superpowers/plans/2026-04-02-main-brain-shell-surface-visibility-hardening-implementation.md
git commit -m "feat: harden main-brain shell surface visibility"
```
