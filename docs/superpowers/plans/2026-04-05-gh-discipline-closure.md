# G/H Discipline Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close Package G/H by formalizing skill metadata and scoped activation read models, then turning portfolio governance into executable actions while cooling the capability governance hotspot.

**Architecture:** Keep one capability truth path. Skill activation stays compatibility-backed by `active_skills`, but formal runtime reads move to canonical metadata summaries bound to package identity and activation scope. Portfolio governance grows from summary-only counters into structured action payloads, and the Runtime Center capability governance projection is extracted from `overview_cards.py` so future hardening does not pile back into the hotspot.

**Tech Stack:** Python, pytest, FastAPI runtime-center read models, CoPaw capability/state services

---

### Task 1: Lock G with failing tests

**Files:**
- Modify: `tests/test_skill_service.py`
- Modify: `tests/app/test_capability_skill_service.py`

- [ ] **Step 1: Write failing tests for scoped activation metadata and duplicate suppression**

Add tests that require:
- skill metadata summary includes canonical package binding plus scoped activation fields
- path-scoped activation is surfaced when `target_scope` / `target_role_id` / `target_seat_ref` exists
- duplicate skill specs collapse to one canonical record instead of leaking parallel duplicates

- [ ] **Step 2: Run focused tests to verify they fail**

Run: `PYTHONPATH=src C:\Python312\python.exe -m pytest tests/test_skill_service.py tests/app/test_capability_skill_service.py -q`
Expected: FAIL on new assertions around metadata summary / duplicate suppression

### Task 2: Implement G in canonical skill/catalog seams

**Files:**
- Modify: `src/copaw/capabilities/skill_service.py`
- Modify: `src/copaw/capabilities/catalog.py`
- Modify: `src/copaw/capabilities/service.py` if needed for surfaced read APIs only

- [ ] **Step 1: Add canonical skill metadata summary helpers**

Implement focused helpers that normalize:
- package provenance
- activation scope (`target_scope`, `target_role_id`, `target_seat_ref`)
- canonical scope key
- `path_scoped_activation`
- package-bound metadata summary payloads

- [ ] **Step 2: Make catalog skill specs consume the canonical metadata summary**

Update skill spec payload building to:
- reuse the canonical summary
- mark working-dir activation separately from scoped activation truth
- suppress duplicate records by canonical package identity / canonical root path

- [ ] **Step 3: Re-run G tests**

Run: `PYTHONPATH=src C:\Python312\python.exe -m pytest tests/test_skill_service.py tests/app/test_capability_skill_service.py -q`
Expected: PASS

### Task 3: Lock H with failing tests

**Files:**
- Modify: `tests/predictions/test_skill_candidate_service.py`
- Modify: `tests/app/runtime_center_api_parts/overview_governance.py`

- [ ] **Step 1: Write failing tests for executable governance actions and projection passthrough**

Add tests that require:
- portfolio summaries expose structured governance actions with scope/budget/route metadata
- replacement / retirement / density compaction actions become machine-readable payloads
- Runtime Center capability governance projection returns the structured actions

- [ ] **Step 2: Run H tests to verify they fail**

Run: `PYTHONPATH=src C:\Python312\python.exe -m pytest tests/predictions/test_skill_candidate_service.py tests/app/runtime_center_api_parts/overview_governance.py -q`
Expected: FAIL on missing governance action contract

### Task 4: Implement H and cool the hotspot

**Files:**
- Modify: `src/copaw/state/capability_portfolio_service.py`
- Add: `src/copaw/app/runtime_center/overview_capability_governance.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`

- [ ] **Step 1: Add structured governance action builders in portfolio service**

Introduce a canonical action payload that includes:
- `action`
- `priority`
- scope identifiers
- donor/candidate references
- reason/summary
- route or review surface hint

Keep legacy `planning_actions` as a compatibility projection derived from the structured actions.

- [ ] **Step 2: Extract capability governance projection from `overview_cards.py`**

Move the capability governance assembly into a dedicated helper module and keep `overview_cards.py` as an orchestrator.

- [ ] **Step 3: Re-run H tests**

Run: `PYTHONPATH=src C:\Python312\python.exe -m pytest tests/predictions/test_skill_candidate_service.py tests/app/runtime_center_api_parts/overview_governance.py -q`
Expected: PASS

### Task 5: Full focused verification and status sync

**Files:**
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Run combined verification**

Run: `PYTHONPATH=src C:\Python312\python.exe -m pytest tests/test_skill_service.py tests/app/test_capability_skill_service.py tests/predictions/test_skill_candidate_service.py tests/app/runtime_center_api_parts/overview_governance.py -q`
Expected: PASS

- [ ] **Step 2: Update task status with verified G/H closure note**

Record the precise scope landed and the exact verification command/result.
