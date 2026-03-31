# Media Memory Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining chat media -> analysis -> writeback -> memory -> operator surface chain without leaving thread/work-context continuity gaps.

**Architecture:** Keep `MediaAnalysisRecord` as the formal persisted analysis object and keep truth-first memory as the only recall path. Close the remaining gaps by exposing `work_context_id` through the media list contract, fixing main-brain recall precedence, restoring trace routes from memory hits back to media analyses, and adding a formal Runtime Center media section instead of generic record rendering.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite repositories, React, TypeScript, Vitest, pytest

---

### Task 1: Expose Work-Context Media Continuity

**Files:**
- Modify: `src/copaw/media/service.py`
- Modify: `src/copaw/app/routers/media.py`
- Modify: `console/src/api/modules/media.ts`
- Modify: `console/src/pages/Chat/useChatMedia.ts`
- Test: `console/src/pages/Chat/useChatMedia.test.tsx`

- [ ] Add `work_context_id` passthrough to the media list service and router contract.
- [ ] Extend the console media API contract to send and receive `work_context_id`.
- [ ] Update chat media loading to prefer `work_context_id` continuity when available, while keeping `thread_id` filtering for the current thread.
- [ ] Add frontend tests proving resumed threads can reload analyses by shared `work_context_id`.

### Task 2: Fix Main-Brain Recall Precedence

**Files:**
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`

- [ ] Make main-brain recall prefer `work_context` scope over `industry` scope when both are present.
- [ ] Add regression coverage so truth-first recall keeps the narrower scope in chat follow-up turns.

### Task 3: Close Media Trace Routes in Truth-First Memory

**Files:**
- Modify: `src/copaw/memory/derived_index_service.py`
- Test: `tests/state/test_truth_first_memory_recall.py`

- [ ] Teach memory source-route resolution to map retained `media-analysis:*` refs back to `/api/media/analyses/{analysis_id}`.
- [ ] Normalize doubled media-analysis prefixes during route derivation instead of changing persisted source-ref contracts in this task.
- [ ] Add a state-level regression test proving media-backed recall hits resolve to the original media analysis route.

### Task 4: Add Formal Runtime Center Media Section

**Files:**
- Modify: `console/src/pages/RuntimeCenter/runtimeIndustrySections.tsx`
- Modify: `console/src/pages/RuntimeCenter/runtimeDetailDrawer.tsx`
- Test: `console/src/pages/RuntimeCenter/runtimeDetailDrawer.test.tsx`

- [ ] Add a dedicated media analyses section for industry/runtime details.
- [ ] Surface analysis status, media type, work-context continuity, and writeback status instead of generic object cards.
- [ ] Add UI regression coverage for the new Runtime Center media section.

### Task 5: Sync Status and Run Focused Verification

**Files:**
- Modify: `TASK_STATUS.md`
- Test: `tests/app/test_runtime_chat_media.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`
- Test: `tests/state/test_truth_first_memory_recall.py`
- Test: `console/src/pages/Chat/useChatMedia.test.tsx`
- Test: `console/src/pages/RuntimeCenter/runtimeDetailDrawer.test.tsx`

- [ ] Update `TASK_STATUS.md` so this item moves from “还没完全收干净” to explicit closed wording.
- [ ] Run the focused backend and frontend suites that prove media-memory closure, continuity, and operator visibility.
- [ ] Commit and push once the targeted suites pass.
