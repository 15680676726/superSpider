# Seat Gap Closure Implementation Plan

> **Document status (`2026-03-25`):** This plan is now a historical sub-plan. Its core rules remain valid, but top-level authority has moved to:
> - `docs/superpowers/specs/2026-03-25-copaw-full-architecture-map-and-hard-cut-redesign.md`
> - `docs/superpowers/plans/2026-03-25-copaw-hard-cut-autonomy-rebuild.md`
>
> Read this file only as the seat-gap/staffing closure slice. Do not use it as the current top-level execution plan when it conflicts with the hard-cut documents.

## Status Alignment

- Still valid:
  - main brain never executes leaf work directly
  - low-risk local gaps may auto-create temporary seats
  - high-risk or long-term gaps must become governed seat proposals
  - staffing state must be visible in backend read models, prompts, and frontend surfaces
- Superseded by the hard-cut rebuild:
  - seat-gap is no longer a standalone top-level rollout; it is part of the single autonomy main chain
  - `MainBrainChatService` is no longer the intended durable runtime mutation entry
  - old file/path targets such as `src/copaw/app/runtime_center/conversations.py` should not override the current hard-cut wiring
  - any implementation step that preserves old `goal/task/schedule` planning truth loses priority to the hard-cut chain

---

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the industry chat writeback staffing-gap loop so the main brain never executes leaf work directly, can auto-create temporary seats for low-risk local work, can raise governed seat proposals for high-risk or long-term gaps, and exposes the staffing state in runtime surfaces.

**Architecture:** Route unmatched execution-core chat writeback through `seat_gap_policy`, materialize seat lifecycle changes through `system:update_industry_team`, persist seat-resolution metadata on backlog items, and surface the resulting staffing state through detail read models and runtime prompts/UI. Keep the main brain on planning/supervision only; all leaf execution stays on specialist seats.

**Tech Stack:** Python, FastAPI services, SRK kernel dispatcher, Pydantic models, pytest, TypeScript, React, Vitest

---

### Task 1: Seat-Gap Backend Closure

**Files:**
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/capabilities/system_team_handlers.py`
- Test: `tests/industry/test_seat_gap_policy.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`

- [ ] **Step 1: Keep failing tests as the red baseline**

Run: `python -m pytest tests/industry/test_seat_gap_policy.py tests/app/industry_api_parts/runtime_updates.py -q -k "seat_gap or temporary_seat_for_low_risk_local_gap or governed_seat_proposal_for_high_risk_gap or unmatched_work_in_backlog_when_no_specialist_matches"`
Expected: the low-risk and governed gap tests fail against the old writeback chain.

- [ ] **Step 2: Wire `seat_gap_policy` into `apply_execution_chat_writeback`**

Implement seat-resolution branching for:
- existing specialist reuse
- temporary seat auto-creation through `system:update_industry_team`
- temporary/career seat governed proposals with decision requests
- generic routing-pending backlog retention

- [ ] **Step 3: Suppress default long-term role goals for governed seat-gap updates**

Add a payload-controlled escape hatch so `system:update_industry_team` can add a seat without also synthesizing an unrelated default role goal.

- [ ] **Step 4: Re-run the targeted backend tests**

Run: `python -m pytest tests/industry/test_seat_gap_policy.py tests/app/industry_api_parts/runtime_updates.py -q`
Expected: all targeted seat-gap tests pass.

### Task 2: Staffing Read Model + Prompt Wiring

**Files:**
- Modify: `src/copaw/industry/models.py`
- Modify: `src/copaw/industry/service_strategy.py`
- Modify: `src/copaw/kernel/main_brain_chat_service.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `src/copaw/app/runtime_center/conversations.py`
- Test: `tests/kernel/test_main_brain_chat_service.py`

- [ ] **Step 1: Add `staffing` to `IndustryInstanceDetail`**

Expose active gap, pending proposals, temporary seats, and researcher status from the canonical instance detail model.

- [ ] **Step 2: Build the staffing read model from backlog/team/decisions**

Derive staffing state from seat-resolution backlog metadata, decision requests, current temporary seats, and researcher visibility.

- [ ] **Step 3: Inject staffing context into main-brain and runtime prompts**

Teach the main brain and execution surfaces to mention active staffing gaps and temporary seats instead of falling back to “can’t do it”.

- [ ] **Step 4: Re-run the prompt/runtime tests**

Run: `python -m pytest tests/kernel/test_main_brain_chat_service.py -q`
Expected: prompt/runtime coverage stays green with the new staffing context.

### Task 3: Frontend Staffing Visibility

**Files:**
- Modify: `console/src/api/modules/industry.ts`
- Create: `console/src/runtime/staffingGapPresentation.ts`
- Create: `console/src/runtime/staffingGapPresentation.test.ts`
- Modify: `console/src/pages/Industry/index.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/AgentWorkbench/V7ExecutionSeatPanel.tsx`

- [ ] **Step 1: Add frontend typings and presentation helpers for staffing**

Model the backend staffing payload and centralize text presentation for active gaps, proposals, and temporary seats.

- [ ] **Step 2: Surface staffing state on the key runtime pages**

Show the current staffing gap/proposal/temporary-seat state on `/industry`, `Runtime Center`, and `AgentWorkbench`.

- [ ] **Step 3: Run frontend tests and build**

Run: `npm --prefix console exec vitest run src/runtime/staffingGapPresentation.test.ts`
Expected: staffing presentation tests pass.

Run: `npm --prefix console run build`
Expected: frontend build succeeds.

### Task 4: Final Verification + Status Doc

**Files:**
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Update task status for the seat-gap closure**

Record that post-V7 main-brain seat-gap closure is wired through governed seat lifecycle and runtime staffing visibility.

- [ ] **Step 2: Run the full verification bundle**

Run: `python -m pytest tests/industry/test_seat_gap_policy.py tests/app/industry_api_parts/runtime_updates.py tests/kernel/test_main_brain_chat_service.py -q`
Expected: backend verification passes.

Run: `npm --prefix console exec vitest run src/runtime/staffingGapPresentation.test.ts`
Expected: frontend unit coverage passes.

Run: `npm --prefix console run build`
Expected: frontend production build passes.
