# Chat And Workbench Runtime Slimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `Chat` back to a true chat surface while finishing the remaining `AgentWorkbench` runtime-panel decomposition and syncing status docs to real code state.

**Architecture:** Extract chat-only attachment orchestration into a focused hook, move the remaining non-chat runtime chrome into a minimal component that only keeps approval entry and a compact status rail, and move the remaining `AgentWorkbench` actor runtime panel into its own section module so `pageSections.tsx` stays as a compatibility/export surface.

**Tech Stack:** TypeScript, React, Ant Design, Vitest, Vite

---

### Task 1: Pin the remaining frontend decomposition seams

**Files:**
- Create: `console/src/pages/Chat/useChatMedia.test.tsx`
- Create: `console/src/pages/Chat/ChatRuntimeSidebar.test.tsx`
- Create: `console/src/pages/AgentWorkbench/runtimePanels.test.tsx`

- [ ] **Step 1: Write the failing `useChatMedia` test for loading completed thread analyses and syncing selected ids**
- [ ] **Step 2: Run `npx vitest run src/pages/Chat/useChatMedia.test.tsx` and confirm it fails because the module does not exist**
- [ ] **Step 3: Write the failing `ChatRuntimeSidebar` render test for minimal governance + status-only chrome**
- [ ] **Step 4: Run `npx vitest run src/pages/Chat/ChatRuntimeSidebar.test.tsx` and confirm it fails because the component does not exist**
- [ ] **Step 5: Write the failing `runtimePanels` smoke/render test for the extracted actor runtime panel**
- [ ] **Step 6: Run `npx vitest run src/pages/AgentWorkbench/runtimePanels.test.tsx` and confirm it fails because the section module does not exist**

### Task 2: Slim `Chat` into chat-first composition

**Files:**
- Create: `console/src/pages/Chat/useChatMedia.ts`
- Create: `console/src/pages/Chat/ChatRuntimeSidebar.tsx`
- Modify: `console/src/pages/Chat/index.tsx`
- Modify: `console/src/pages/Chat/useRuntimeBinding.test.ts`

- [ ] **Step 1: Implement `useChatMedia.ts` to own media draft state, thread analysis sync, and mutable refs consumed by the runtime fetch path**
- [ ] **Step 2: Implement `ChatRuntimeSidebar.tsx` as the minimal non-chat chrome: compact binding label, approval entry, and status rail only**
- [ ] **Step 3: Remove capability drawer, capability surface card, detailed runtime sidebar, and actor detail loading from `Chat/index.tsx`**
- [ ] **Step 4: Keep only message flow, input, compact status rail, approval entry, blocking notices, and attachment controls in `Chat/index.tsx`**
- [ ] **Step 5: Re-run focused Chat tests**

### Task 3: Finish `AgentWorkbench` runtime panel extraction

**Files:**
- Create: `console/src/pages/AgentWorkbench/sections/runtimePanels.tsx`
- Modify: `console/src/pages/AgentWorkbench/pageSections.tsx`
- Modify: `console/src/pages/AgentWorkbench/index.tsx`
- Modify: `console/src/pages/AgentWorkbench/pageSections.test.ts`

- [ ] **Step 1: Move `ActorRuntimePanel` out of `pageSections.tsx` into `sections/runtimePanels.tsx`**
- [ ] **Step 2: Re-export the runtime panel through `pageSections.tsx` so current consumers stay stable**
- [ ] **Step 3: Re-run focused AgentWorkbench tests**

### Task 4: Sync status docs and verify end-to-end

**Files:**
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Update `TASK_STATUS.md` so Chat/runtime decomposition status matches the actual codebase**
- [ ] **Step 2: Run the focused frontend Vitest batch for Chat and AgentWorkbench decomposition**
- [ ] **Step 3: Run `npm run build` in `console/`**
- [ ] **Step 4: Only then report completion with concrete verification output**
