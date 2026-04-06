# Frontend Runtime And Chat Audit Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit and repair frontend garbled text, stale logic, backend contract mismatches, and chat page bugs across the current runtime-first product surface.

**Architecture:** Treat this as one frontend audit with four independent evidence domains: text/encoding, route/page logic, frontend-backend contract alignment, and chat/Buddy interaction flow. Fix root causes only after each domain produces concrete evidence.

**Tech Stack:** React, TypeScript, Vite frontend under `console/`, FastAPI backend surface under `src/copaw/app/routers/`, runtime-first state/query contracts.

---

### Task 1: Establish Audit Map

**Files:**
- Read: `console/src/`
- Read: `console/src/pages/`
- Read: `console/src/api/`
- Read: `console/src/routes/`
- Read: `console/src/layouts/`

- [ ] Enumerate main frontend entry pages and their current data sources.
- [ ] Mark suspected legacy surfaces and duplicate flows.
- [ ] Mark pages with obvious garbled Chinese or mixed stale copy.

### Task 2: Audit Garbled Text And Copy Chain

**Files:**
- Read: `console/src/**/*.ts`
- Read: `console/src/**/*.tsx`
- Read: `FRONTEND_UPGRADE_PLAN.md`
- Read: `RUNTIME_CENTER_UI_SPEC.md`
- Read: `AGENT_VISIBLE_MODEL.md`

- [ ] Find visible frontend Chinese garbling and determine whether root cause is source file encoding, copied stale text, or bad literal fallback.
- [ ] Separate document-only garbling from user-facing UI garbling.
- [ ] Produce exact file-level evidence before any rewrite.

### Task 3: Audit Runtime/Industry/Identity Page Logic

**Files:**
- Read: `console/src/pages/RuntimeCenter/`
- Read: `console/src/pages/Industry/`
- Read: `console/src/pages/Identity*`
- Read: `console/src/pages/*Onboarding*`
- Read: `console/src/layouts/Sidebar.tsx`

- [ ] Find duplicate identity creation and stale navigation paths.
- [ ] Check whether Runtime Center and Industry pages still use removed or legacy assumptions.
- [ ] Identify backend mismatch points by tracing each page's actual API calls.

### Task 4: Audit Chat/Buddy Page

**Files:**
- Read: `console/src/pages/Chat/`
- Read: `console/src/api/modules/`
- Read: `src/copaw/app/routers/runtime_center_routes*`
- Read: `src/copaw/kernel/main_brain_*`

- [ ] Trace chat request path, response render path, Buddy panel state path, and onboarding/name creation path.
- [ ] Find reproducible chat bugs, stale local cache truth, and contract drift from backend.
- [ ] Confirm whether the page still contains old entry paths or broken persona/Buddy state merges.

### Task 5: Repair Highest-Risk Root Causes

**Files:**
- Modify only after Tasks 1-4 produce evidence.

- [ ] Fix one root cause at a time, starting with user-visible breakage.
- [ ] Keep one truth source per page flow.
- [ ] Remove stale branching instead of adding another compatibility path.

### Task 6: Verify

**Files:**
- Test: frontend and targeted integration commands

- [ ] Run targeted frontend tests if present.
- [ ] Run build/typecheck on touched frontend scope.
- [ ] Re-verify affected backend contracts when frontend changed request or response assumptions.
