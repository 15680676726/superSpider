# Native Fixed SOP Kernel and n8n Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete `n8n / Workflow Hub` from CoPaw and replace it with an internal minimal fixed SOP kernel that only handles the low-judgment automation paths we actually need.

**Architecture:** Keep computer-use execution in `Agent Body Grid` and keep the operator main chain unchanged. Replace `sop_adapters` with a native kernel for `trigger / guard / http_request / capability_call / routine_call / wait_callback / writeback`, expose only a minimal runtime automation surface, and hard-delete the old frontend/backend `n8n` product path instead of carrying compatibility forward.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLite state/evidence repositories, pytest, TypeScript/React, existing cron/runtime-center surfaces

**Companion Docs:**
- Spec: `docs/superpowers/specs/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md`
- Body runtime spec: `docs/superpowers/specs/2026-03-26-agent-body-grid-computer-runtime.md`
- Status: `TASK_STATUS.md`
- API map: `API_TRANSITION_MAP.md`

---

## Cross-Plan Order

This is the first hard-cut plan in the four-document set.

Recommended sequencing across the four documents:

1. finish this plan's architecture lock and native kernel core tasks first
2. begin body-runtime acceptance and operator refactor in parallel only after the retirement boundary is fixed
3. complete backend/frontend `n8n` retirement before claiming runtime IA is clean
4. let the Agent Body Grid plan retire remaining legacy execution bypasses only after this plan has removed the old SOP sidecar path

This plan removes ambiguity; the body-runtime plan then builds on a single automation target instead of a split target.

## Scope Guardrails

- Do not keep `n8n` as a "temporary bridge" after this cut.
- Do not create a generic workflow marketplace or arbitrary JSON import path.
- Do not move browser/desktop/document execution into the SOP kernel.
- Do not add a second run-history or evidence system.
- Do not keep the old frontend IA (`社区工作流`, `Workflow Hub`) alive under a renamed shell.
- Do not keep compatibility tables, routers, or UI forms unless they are required only for one-shot data cleanup.

## File Map

### Docs and architecture sync

- Modify: `docs/superpowers/specs/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md`
- Modify: `docs/superpowers/plans/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md`
- Modify: `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `docs/architecture/working-plans/V6_ROUTINE_MUSCLE_MEMORY_PLAN.md`
- Modify: `docs/architecture/working-plans/N8N_SOP_ADAPTER_WORKFLOW_HUB_PLAN.md`

### Backend kernel and runtime wiring

- Create: `src/copaw/sop_kernel/__init__.py`
- Create: `src/copaw/sop_kernel/models.py`
- Create: `src/copaw/sop_kernel/builtin_templates.py`
- Create: `src/copaw/sop_kernel/service.py`
- Create: `src/copaw/sop_kernel/runtime.py`
- Create: `src/copaw/app/routers/fixed_sops.py`
- Modify: `src/copaw/state/models_workflows.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/routers/__init__.py`
- Modify: `src/copaw/capabilities/system_routine_handlers.py`
- Modify: `src/copaw/capabilities/sources/system.py`
- Modify: `src/copaw/workflows/service_runs.py`
- Modify: `src/copaw/learning/acquisition_runtime.py`
- Modify: `src/copaw/industry/service_runtime_views.py`

### Backend retirement set

- Delete: `src/copaw/app/routers/sop_adapters.py`
- Delete: `src/copaw/sop_adapters/`
- Modify: `src/copaw/app/_app.py`
- Modify: `src/copaw/routines/service.py`

### Tests

- Create: `tests/fixed_sops/test_service.py`
- Create: `tests/app/test_fixed_sop_kernel_api.py`
- Modify: `tests/app/test_capability_market_api.py`
- Delete: `tests/app/test_sop_adapters_api.py`
- Delete: `tests/sop_adapters/test_catalog_client.py`
- Delete: `tests/sop_adapters/test_localization.py`

### Frontend runtime automation surface

- Create: `console/src/api/modules/fixedSops.ts`
- Create: `console/src/pages/RuntimeCenter/FixedSopPanel.tsx`
- Create: `console/src/pages/RuntimeCenter/FixedSopPanel.test.tsx`
- Modify: `console/src/api/index.ts`
- Modify: `console/src/pages/RuntimeCenter/AutomationTab.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/routes/index.tsx`
- Modify: `console/src/routes/resolveSelectedKey.test.ts`
- Modify: `console/src/layouts/Sidebar.tsx`
- Modify: `console/src/layouts/Header.tsx`
- Modify: `console/src/pages/CapabilityMarket/index.tsx`
- Modify: `console/src/pages/CapabilityMarket/useCapabilityMarketState.ts`
- Modify: `console/src/pages/CapabilityMarket/useCapabilityMarketState.test.tsx`
- Modify: `console/src/pages/CapabilityMarket/presentation.ts`
- Delete: `console/src/api/modules/sopAdapters.ts`
- Delete: `console/src/pages/WorkflowTemplates/index.tsx`
- Delete: `console/src/pages/WorkflowTemplates/localization.ts`

---

### Task 1: Lock the Hard-Cut Architecture Decision

**Files:**
- Modify: `docs/superpowers/specs/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md`
- Modify: `docs/superpowers/plans/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md`
- Modify: `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `docs/architecture/working-plans/V6_ROUTINE_MUSCLE_MEMORY_PLAN.md`
- Modify: `docs/architecture/working-plans/N8N_SOP_ADAPTER_WORKFLOW_HUB_PLAN.md`

- [ ] **Step 1: Add a failing documentation expectation check**

```python
def test_n8n_is_retired_from_target_architecture() -> None:
    text = Path("TASK_STATUS.md").read_text(encoding="utf-8")
    assert "n8n / Workflow Hub" in text and "已从目标架构退役" in text
```

- [ ] **Step 2: Run the targeted docs check**

Run: `python -m pytest tests -q -k "n8n_is_retired_from_target_architecture"`
Expected: FAIL until the docs are aligned.

- [ ] **Step 3: Update all architecture docs and status**

Rules:
- every core doc must say `n8n` is retired, not "still kept as a narrow bridge"
- the replacement name must be `Native Fixed SOP Kernel`
- the body-runtime boundary must stay intact
- the Agent Body Grid documents must read as downstream execution docs, not a competing automation plan

- [ ] **Step 4: Re-run the targeted docs check**

Run: `python -m pytest tests -q -k "n8n_is_retired_from_target_architecture"`
Expected: PASS.

- [ ] **Step 5: Save a checkpoint**

Run: `git diff --stat`
Expected: only docs/status/plan files changed.

### Task 2: Write the Failing Backend Contract Tests First

**Files:**
- Create: `tests/fixed_sops/test_service.py`
- Create: `tests/app/test_fixed_sop_kernel_api.py`
- Delete: `tests/app/test_sop_adapters_api.py`

- [ ] **Step 1: Write the native kernel node-contract tests**

```python
def test_fixed_sop_service_rejects_unknown_node_kind() -> None:
    ...

def test_fixed_sop_service_allows_only_minimal_node_set() -> None:
    ...
```

- [ ] **Step 2: Write the API contract tests**

```python
def test_list_fixed_sop_templates(client) -> None:
    response = client.get("/api/fixed-sops/templates")
    assert response.status_code == 200

def test_old_sop_adapters_route_is_gone(client) -> None:
    response = client.get("/api/sop-adapters/templates")
    assert response.status_code in {404, 410}
```

- [ ] **Step 3: Run the backend contract tests**

Run: `python -m pytest tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py -q`
Expected: FAIL because the new service/router does not exist yet.

- [ ] **Step 4: Delete or rewrite the old API tests**

Rules:
- no test should continue asserting `sop-adapters` as a target surface
- route retirement must be explicit, not silently orphaned

- [ ] **Step 5: Save the failing evidence**

Run: `python -m pytest tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py -q > fixed_sop_kernel_failures.txt`
Expected: failure log captured.

### Task 3: Introduce the Native Fixed SOP Kernel Data Model and Runtime

**Files:**
- Create: `src/copaw/sop_kernel/__init__.py`
- Create: `src/copaw/sop_kernel/models.py`
- Create: `src/copaw/sop_kernel/builtin_templates.py`
- Create: `src/copaw/sop_kernel/service.py`
- Create: `src/copaw/sop_kernel/runtime.py`
- Modify: `src/copaw/state/models_workflows.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_service_graph.py`

- [ ] **Step 1: Define the minimal records and node models**

```python
class FixedSopNodeKind(str, Enum):
    TRIGGER = "trigger"
    GUARD = "guard"
    HTTP_REQUEST = "http_request"
    CAPABILITY_CALL = "capability_call"
    ROUTINE_CALL = "routine_call"
    WAIT_CALLBACK = "wait_callback"
    WRITEBACK = "writeback"
```

- [ ] **Step 2: Run the service tests to verify failure narrows to missing behavior**

Run: `python -m pytest tests/fixed_sops/test_service.py -q -vv`
Expected: FAIL on missing records/service methods.

- [ ] **Step 3: Implement builtin template loading and run orchestration**

Rules:
- v1 templates are curated/builtin, not user-authored marketplace imports
- keep all truth in CoPaw state/evidence
- `routine_call` is the only path for UI work

- [ ] **Step 4: Re-run the service tests**

Run: `python -m pytest tests/fixed_sops/test_service.py -q`
Expected: PASS.

- [ ] **Step 5: Save a checkpoint**

```bash
git add src/copaw/sop_kernel src/copaw/state src/copaw/app/runtime_bootstrap_* tests/fixed_sops/test_service.py
git commit -m "feat: add native fixed sop kernel core"
```

### Task 4: Rewire Workflow, Capability, Learning, and Industry Integrations

**Files:**
- Create: `src/copaw/app/routers/fixed_sops.py`
- Modify: `src/copaw/app/routers/__init__.py`
- Modify: `src/copaw/capabilities/system_routine_handlers.py`
- Modify: `src/copaw/capabilities/sources/system.py`
- Modify: `src/copaw/workflows/service_runs.py`
- Modify: `src/copaw/learning/acquisition_runtime.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Test: `tests/app/test_fixed_sop_kernel_api.py`

- [ ] **Step 1: Add failing integration tests for kernel-governed fixed SOP execution**

```python
def test_fixed_sop_run_routes_ui_work_through_routine_call(...) -> None:
    ...

def test_industry_learning_reads_fixed_sop_bindings_not_n8n_bindings(...) -> None:
    ...
```

- [ ] **Step 2: Wire the new router and system capability entry**

Rules:
- preferred system action name is `system:run_fixed_sop`
- remove `n8n` tags and adapter-specific capability semantics
- keep run/evidence/report truth on existing chains

- [ ] **Step 3: Update workflow and industry consumers**

Rules:
- workflow launch may reference fixed SOP bindings
- industry/learning surfaces must stop mentioning `n8n`, `doctor`, or callback bridges

- [ ] **Step 4: Re-run the integration tests**

Run: `python -m pytest tests/app/test_fixed_sop_kernel_api.py tests/app/test_industry_api.py tests/app/test_learning_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit the integration slice**

```bash
git add src/copaw/app src/copaw/capabilities src/copaw/workflows src/copaw/learning src/copaw/industry tests/app/test_fixed_sop_kernel_api.py
git commit -m "feat: wire fixed sop kernel into workflow and runtime integrations"
```

### Task 5: Delete the Old Backend n8n Surface Completely

**Files:**
- Delete: `src/copaw/app/routers/sop_adapters.py`
- Delete: `src/copaw/sop_adapters/`
- Modify: `src/copaw/app/_app.py`
- Modify: `src/copaw/routines/service.py`
- Delete: `tests/sop_adapters/test_catalog_client.py`
- Delete: `tests/sop_adapters/test_localization.py`

- [ ] **Step 1: Remove catalog sync, callback, and adapter imports**

Rules:
- no `ensure_n8n_template_catalog_sync_job(...)`
- no `N8nSopRemoteClient`
- no callback ingress for `n8n`

- [ ] **Step 2: Remove the retired router from app composition**

Run: `python -m pytest tests/app/test_fixed_sop_kernel_api.py -q -k fixed_sops`
Expected: still PASS after router cleanup.

- [ ] **Step 3: Delete the retired package and tests**

Rules:
- do not leave a compatibility shell directory
- do not leave "retired n8n" strings in runtime code paths

- [ ] **Step 4: Run the backend regression slice**

Run: `python -m pytest tests/app tests/industry tests/routines tests/kernel -q -k "fixed_sop or workflow or runtime_center or learning"`
Expected: PASS.

- [ ] **Step 5: Commit the hard delete**

```bash
git add src/copaw/app src/copaw/routines tests
git commit -m "refactor: delete n8n sop adapter backend"
```

### Task 6: Collapse the Frontend into a Minimal Runtime Automation Surface

**Files:**
- Create: `console/src/api/modules/fixedSops.ts`
- Create: `console/src/pages/RuntimeCenter/FixedSopPanel.tsx`
- Create: `console/src/pages/RuntimeCenter/FixedSopPanel.test.tsx`
- Modify: `console/src/api/index.ts`
- Modify: `console/src/pages/RuntimeCenter/AutomationTab.tsx`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/routes/index.tsx`
- Modify: `console/src/routes/resolveSelectedKey.test.ts`
- Modify: `console/src/layouts/Sidebar.tsx`
- Modify: `console/src/layouts/Header.tsx`
- Modify: `console/src/pages/CapabilityMarket/index.tsx`
- Modify: `console/src/pages/CapabilityMarket/useCapabilityMarketState.ts`
- Modify: `console/src/pages/CapabilityMarket/useCapabilityMarketState.test.tsx`
- Modify: `console/src/pages/CapabilityMarket/presentation.ts`
- Delete: `console/src/api/modules/sopAdapters.ts`
- Delete: `console/src/pages/WorkflowTemplates/index.tsx`
- Delete: `console/src/pages/WorkflowTemplates/localization.ts`

- [ ] **Step 1: Add failing UI tests for the new IA**

```tsx
it("does not expose workflow-hub navigation", () => {
  expect(resolveSelectedKey("/capability-market?tab=workflows")).not.toBe("workflow-hub");
});

it("renders fixed SOP automation in Runtime Center", async () => {
  render(<AutomationTab />);
  expect(await screen.findByText("Fixed SOP")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the targeted frontend tests**

Run: `npm test -- --runInBand console/src/routes/resolveSelectedKey.test.ts console/src/pages/RuntimeCenter/FixedSopPanel.test.tsx console/src/pages/CapabilityMarket/useCapabilityMarketState.test.tsx`
Expected: FAIL until the IA and API changes land.

- [ ] **Step 3: Introduce `fixedSops` API module and Runtime Center panel**

Rules:
- Runtime Center Automation is the canonical UI
- Capability Market must stop presenting community workflow / `n8n` concepts
- no new "workflow hub" page is allowed

- [ ] **Step 4: Delete old navigation and workflow-hub pages**

Rules:
- remove sidebar/header labels
- remove routes and redirect shells
- remove `n8n webhook` forms and community-template sync affordances

- [ ] **Step 5: Re-run the targeted frontend tests**

Run: `npm test -- --runInBand console/src/routes/resolveSelectedKey.test.ts console/src/pages/RuntimeCenter/FixedSopPanel.test.tsx console/src/pages/CapabilityMarket/useCapabilityMarketState.test.tsx`
Expected: PASS.

### Task 7: Hard-Cut Cleanup, Reset, and Full Verification

**Files:**
- Modify: `scripts/reset_autonomy_runtime.py`
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `console/src/pages/RuntimeCenter/AutomationTab.tsx`

- [ ] **Step 1: Extend runtime reset to clear retired SOP-adapter data**

```python
def purge_retired_sop_adapter_state(...) -> None:
    ...
```

- [ ] **Step 2: Run the reset and targeted regression**

Run: `python scripts/reset_autonomy_runtime.py`
Expected: retired SOP-adapter state removed without manual DB edits.

- [ ] **Step 3: Run backend verification**

Run: `python -m pytest tests/app tests/industry tests/kernel tests/routines tests/fixed_sops -q`
Expected: PASS.

- [ ] **Step 4: Run frontend verification**

Run: `cd console && npm run build`
Expected: PASS with no `workflow-hub`, `sopAdapters`, or `n8n` UI compile references.

- [ ] **Step 5: Run a repo-wide retirement grep**

Run: `rg -n "n8n|workflow-hub|sop-adapters|社区工作流（n8n）" src console/src tests`
Expected: no live runtime/product references remain outside historical docs and explicit retirement ledgers.
