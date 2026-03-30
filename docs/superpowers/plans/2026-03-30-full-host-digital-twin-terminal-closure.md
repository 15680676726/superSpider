# Full Host Digital Twin Terminal Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining terminal-state gaps in `Full Host Digital Twin` by making `document` a first-class host-aware execution surface and by widening host continuity smoke beyond the current short-run desktop/browser path.

**Architecture:** Keep `host_twin` as the single derived host truth built from the existing environment/session facts. Do not add a second host store. Extend host-aware consumers so `workflow` and `fixed-SOP` can treat `document` execution as a canonical host requirement, then widen smoke so host switch/reentry/replay continuity is proven on the same truth.

**Tech Stack:** Python 3.11, FastAPI service layer, Pydantic models, pytest

---

## File Map

- Modify: `src/copaw/workflows/service_preview.py`
  - accept explicit `surface_kind="document"` as a host-aware requirement and map it to canonical office-document readiness
- Modify: `src/copaw/sop_kernel/service.py`
  - evaluate `document` host requirements against canonical host preflight instead of falling back to the browser branch
- Modify: `src/copaw/environments/health_service.py`
  - expose any missing document/office readiness facts required by the canonical host surface evaluation
- Modify: `tests/app/test_workflow_templates_api.py`
  - add preview/run tests for explicit document host requirements
- Modify: `tests/fixed_sops/test_service.py`
  - add service-level doctor/run tests for explicit document host requirements
- Modify: `tests/app/test_fixed_sop_kernel_api.py`
  - add API-level doctor/run tests for explicit document host requirements
- Modify: `tests/app/test_phase_next_autonomy_smoke.py`
  - widen smoke from short host switch to document-aware continuity/reentry/replay
- Modify: `TASK_STATUS.md`
  - only after verified implementation, record the terminal-state closure reality

### Task 1: Add failing tests for explicit document host-aware consumers

**Files:**
- Modify: `tests/app/test_workflow_templates_api.py`
- Modify: `tests/fixed_sops/test_service.py`
- Modify: `tests/app/test_fixed_sop_kernel_api.py`

- [x] **Step 1: Write a failing workflow preview test**

```python
def test_workflow_preview_accepts_explicit_document_surface_from_canonical_host_twin(...):
    ...
    assert payload["host_requirements"][0]["surface_kind"] == "document"
    assert payload["host_requirements"][0]["app_family"] == "office_document"
```

- [x] **Step 2: Write a failing fixed-SOP service test**

```python
def test_fixed_sop_service_uses_document_surface_host_preflight(...):
    ...
    assert detail.host_requirement["surface_kind"] == "document"
```

- [x] **Step 3: Write a failing fixed-SOP API test**

```python
def test_fixed_sop_run_api_uses_document_surface_host_preflight(...):
    ...
    assert detail_payload["host_requirement"]["surface_kind"] == "document"
```

- [x] **Step 4: Run the focused tests and verify red**

Run: `python -m pytest tests/app/test_workflow_templates_api.py tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py -k "document_surface" -q`

Expected: FAIL because workflow preview currently drops `surface_kind="document"` and fixed-SOP currently treats non-desktop surfaces as browser.

### Task 2: Implement canonical document host-surface handling

**Files:**
- Modify: `src/copaw/workflows/service_preview.py`
- Modify: `src/copaw/sop_kernel/service.py`
- Modify: `src/copaw/environments/health_service.py`

- [x] **Step 1: Implement the minimal workflow preview change**

```python
if surface_kind == "document":
    app_family = app_family or "office_document"
```

And keep the resulting host requirement in the preview payload instead of returning `None`.

- [x] **Step 2: Implement the minimal fixed-SOP preflight change**

```python
surface_key = {
    "desktop": "desktop_app",
    "document": "desktop_app",
    "browser": "browser",
}.get(surface_kind, "browser")
```

Then ensure the canonical host preflight preserves `surface_kind="document"` in the stored host requirement.

- [x] **Step 3: Add any missing host truth plumbing**

```python
"office_document": {
    ...
}
```

Only if the focused tests prove that the current host twin projection is missing document-specific readiness facts.

- [x] **Step 4: Re-run the focused tests and verify green**

Run: `python -m pytest tests/app/test_workflow_templates_api.py tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py -k "document_surface" -q`

Expected: PASS

### Task 3: Add a failing document-aware host continuity smoke

**Files:**
- Modify: `tests/app/test_phase_next_autonomy_smoke.py`

- [x] **Step 1: Write a smoke test covering document-aware host continuity**

```python
def test_phase_next_document_host_switch_smoke_keeps_document_execution_on_canonical_host_truth(...):
    ...
```

The smoke must verify:

- canonical host truth selects the runtime seat/session
- workflow and fixed-SOP both carry the same `document` host requirement
- reentry/replay continuity survives the same document-aware flow

- [x] **Step 2: Run the smoke test and verify red**

Run: `python -m pytest tests/app/test_phase_next_autonomy_smoke.py -k "document_host_switch" -q`

Expected: FAIL because the document-aware path is not yet fully wired through the current smoke and consumers.

### Task 4: Implement the minimum code to make the document smoke pass

**Files:**
- Modify: `src/copaw/workflows/service_preview.py`
- Modify: `src/copaw/sop_kernel/service.py`
- Modify: `tests/app/test_phase_next_autonomy_smoke.py`

- [x] **Step 1: Adjust only the minimum code and fixtures required**
- [x] **Step 2: Re-run the document smoke**

Run: `python -m pytest tests/app/test_phase_next_autonomy_smoke.py -k "document_host_switch" -q`

Expected: PASS

### Task 5: Final verification and status sync

**Files:**
- Modify: `TASK_STATUS.md`

- [x] **Step 1: Run the widened regression group**

Run: `python -m pytest tests/app/test_workflow_templates_api.py tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py tests/app/test_phase_next_autonomy_smoke.py -q`

Expected: PASS

- [x] **Step 2: Update `TASK_STATUS.md` only if the above command is green**

- [x] **Step 3: Re-run the full host-twin verification group**

Run: `python -m pytest tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py tests/app/test_workflow_templates_api.py tests/app/test_cron_executor.py tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py tests/app/test_phase_next_autonomy_smoke.py -q`

Expected: PASS
