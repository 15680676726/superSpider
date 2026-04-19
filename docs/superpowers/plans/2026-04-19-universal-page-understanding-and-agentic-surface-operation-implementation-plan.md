# Universal Page Understanding And Agentic Surface Operation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade CoPaw from provider-shaped browser interaction to a shared surface foundation that supports generic page understanding seams and profession-agent step-by-step operation.

**Architecture:** Keep the existing environment/runtime/evidence spine. Strengthen the shared browser substrate first: snapshot-derived candidates, thin page profiles, live observe/reobserve, more generic slot resolution, then cut Baidu over to that shared layer. Only after the shared foundation is stable should profession-agent step loops expand outward.

**Tech Stack:** Python, pytest, existing browser runner, SurfaceControlService, browser_use, research session runtime, Pydantic models.

---

## File Structure Map

- Create: `src/copaw/environments/surface_execution/browser/profiles.py`
- Modify: `src/copaw/environments/surface_execution/browser/contracts.py`
- Modify: `src/copaw/environments/surface_execution/browser/observer.py`
- Modify: `src/copaw/environments/surface_execution/browser/resolver.py`
- Modify: `src/copaw/environments/surface_execution/browser/service.py`
- Modify: `src/copaw/environments/surface_execution/browser/__init__.py`
- Modify: `src/copaw/research/baidu_page_research_service.py`
- Modify: `tests/environments/test_browser_surface_execution.py`
- Modify: `tests/research/test_baidu_page_research_service.py`
- Modify: `TASK_STATUS.md`

### Task 1: Lock The Generic Browser Substrate Gaps Into Tests

**Files:**
- Modify: `tests/environments/test_browser_surface_execution.py`
- Test: `tests/environments/test_browser_surface_execution.py`

- [ ] **Step 1: Write the failing test for snapshot-derived input candidates**

Add a test proving observer can produce a usable primary input candidate from snapshot text even when `dom_probe.inputs` is empty.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py -k "snapshot_derived_input" -q`
Expected: FAIL because observer currently only trusts explicit `dom_probe.inputs`.

- [ ] **Step 3: Write the failing test for generic slot resolution**

Add a test proving resolver can resolve a profile-declared slot such as `submit_button`, not just `primary_input` or `reasoning_toggle`.

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py -k "submit_button_slot" -q`
Expected: FAIL because resolver is still slot-limited.

- [ ] **Step 5: Commit**

```bash
git add tests/environments/test_browser_surface_execution.py
git commit -m "test: lock browser substrate generic slot gaps"
```

### Task 2: Add Thin Page Profile Contract And Live Observation Helper

**Files:**
- Create: `src/copaw/environments/surface_execution/browser/profiles.py`
- Modify: `src/copaw/environments/surface_execution/browser/contracts.py`
- Modify: `src/copaw/environments/surface_execution/browser/__init__.py`
- Modify: `tests/environments/test_browser_surface_execution.py`
- Test: `tests/environments/test_browser_surface_execution.py`

- [ ] **Step 1: Write the failing test for live page profile observation**

Add a test that proves a thin page profile can:

- trigger snapshot
- run one local probe
- return a normalized `BrowserObservation`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py -k "page_profile_observation" -q`
Expected: FAIL because page profile contract/helper do not exist yet.

- [ ] **Step 3: Implement minimal profile contract and live observation helper**

Create:

- `BrowserPageProfile`
- optional `BrowserProbeSpec`
- a helper such as `observe_live_browser_page(...)`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py -k "page_profile_observation" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/environments/surface_execution/browser/profiles.py src/copaw/environments/surface_execution/browser/contracts.py src/copaw/environments/surface_execution/browser/__init__.py tests/environments/test_browser_surface_execution.py
git commit -m "feat: add browser page profile observation seam"
```

### Task 3: Generalize Observer And Resolver

**Files:**
- Modify: `src/copaw/environments/surface_execution/browser/observer.py`
- Modify: `src/copaw/environments/surface_execution/browser/resolver.py`
- Modify: `src/copaw/environments/surface_execution/browser/contracts.py`
- Modify: `tests/environments/test_browser_surface_execution.py`
- Test: `tests/environments/test_browser_surface_execution.py`

- [ ] **Step 1: Implement snapshot-derived candidate extraction**

Move the generic primary-input scoring logic out of `BaiduPageResearchService` and into shared observer logic.

- [ ] **Step 2: Implement slot candidate support**

Allow candidates to declare generic `target_slots` and let resolver resolve them before falling back to the hardcoded legacy slots.

- [ ] **Step 3: Run focused regression**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/copaw/environments/surface_execution/browser/contracts.py src/copaw/environments/surface_execution/browser/observer.py src/copaw/environments/surface_execution/browser/resolver.py tests/environments/test_browser_surface_execution.py
git commit -m "feat: generalize browser observation and slot resolution"
```

### Task 4: Add Real Reobserve To Shared Browser Service

**Files:**
- Modify: `src/copaw/environments/surface_execution/browser/service.py`
- Modify: `tests/environments/test_browser_surface_execution.py`
- Test: `tests/environments/test_browser_surface_execution.py`

- [ ] **Step 1: Write the failing test for after-observation refresh**

Add a test proving `after_observation` is rebuilt from a fresh snapshot/probe after action execution.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py -k "after_observation_refresh" -q`
Expected: FAIL because service currently reuses `before_observation`.

- [ ] **Step 3: Implement live reobserve**

Update service to support a live observation path through page profile/helper and return true `after_observation`.

- [ ] **Step 4: Run focused regression**

Run: `python -m pytest tests/environments/test_browser_surface_execution.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/environments/surface_execution/browser/service.py tests/environments/test_browser_surface_execution.py
git commit -m "feat: add browser substrate reobserve support"
```

### Task 5: Cut Baidu Input And Toggle Flow Over To Thin Page Profile

**Files:**
- Modify: `src/copaw/research/baidu_page_research_service.py`
- Modify: `tests/research/test_baidu_page_research_service.py`
- Test: `tests/research/test_baidu_page_research_service.py`

- [ ] **Step 1: Keep Baidu as research orchestration owner only**

Refactor `_build_baidu_surface_context(...)` into thin profile usage:

- no provider-local generic input resolver
- no provider-local generic page observation owner

- [ ] **Step 2: Remove `_select_chat_input_ref(...)` from the live main path**

Shared observer should now derive the base input candidate.

- [ ] **Step 3: Route deep-think toggle lookup through shared profile observation**

Keep only a thin local group profile for Baidu, not a provider-private page scan owner.

- [ ] **Step 4: Run focused regression**

Run: `python -m pytest tests/research/test_baidu_page_research_service.py -k "split_action_and_readback or deep_think_state_scopes" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/research/baidu_page_research_service.py tests/research/test_baidu_page_research_service.py
git commit -m "refactor: cut baidu browser flow over to thin page profile"
```

### Task 6: Record Status And Run Verification

**Files:**
- Modify: `TASK_STATUS.md`
- Test: `tests/environments/test_browser_surface_execution.py`
- Test: `tests/research/test_baidu_page_research_service.py`

- [ ] **Step 1: Run focused regression**

Run:

```bash
python -m pytest tests/environments/test_browser_surface_execution.py tests/research/test_baidu_page_research_service.py -q
```

Expected: PASS

- [ ] **Step 2: Update `TASK_STATUS.md`**

Record:

- what landed
- what remains unfinished
- L1/L2/L3/L4 truthfully

- [ ] **Step 3: Commit**

```bash
git add TASK_STATUS.md
git commit -m "docs: record browser substrate generic cutover progress"
```

### Task 7: Next-Round Follow-Up

**Files:**
- Future follow-up only

- [x] **Step 1: Add profession-agent step loop owner**
- [x] **Step 2: Add browser substrate evidence materialization**
- [x] **Step 3: Mirror the same contract into document/desktop**
- [ ] **Step 4: Run L3/L4 long-chain acceptance**
  - `L3` 已补到 logged-in / waiting-login live smoke
  - `L4` long soak 仍未完成
