# Phase 4 + Phase 5 Host Event Bus and Host Twin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Formalize `Phase 4 Host Event Bus` and `Phase 5 Execution-Grade Host Twin` as real runtime behavior, read models, and workflow preflight inputs without introducing a second truth source.

**Architecture:** Extend `EnvironmentHealthService` so host events remain a runtime mechanism backed by unified state/evidence projections, then derive a new execution-grade host twin projection from `TaskRuntime + EnvironmentMount + SessionMount + Artifact/Evidence + host-event/workspace projections`. Feed the derived twin into Runtime Center/task review surfaces and workflow preview preflight so launch decisions can block on seat ownership, writable surfaces, continuity validity, trusted anchors, and legal recovery paths.

**Tech Stack:** Python, FastAPI service layer, Pydantic models, pytest

---

## File Map

- Modify: `src/copaw/app/runtime_events.py`
  - deepen runtime event bus metadata/query helpers so host events can be consumed as scheduler/recovery input rather than only replayed as generic updates
- Modify: `src/copaw/environments/health_service.py`
  - formal host-event family metadata
  - derive `host_twin` projection from existing runtime/environment/evidence facts
  - expose event-led recovery inputs, writable surface state, trusted anchors, legal recovery path, and seat/workspace owner view
- Modify: `src/copaw/app/routers/runtime_center_routes_ops.py`
  - keep formal runtime-surface key detection aligned with the new `host_twin` payload
- Modify: `src/copaw/app/runtime_center/task_review_projection.py`
  - include `host_twin` in task review execution runtime and derive continuity/risk summaries from it
- Modify: `src/copaw/app/runtime_center/state_query.py`
  - copy `host_twin` from environment detail into runtime feedback projection
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
  - ensure the bootstrapped workflow service receives environment detail access for real preflight consumers
- Modify: `src/copaw/workflows/service_preview.py`
  - add event/twin-aware launch blockers and preflight reasoning
- Modify: `tests/app/runtime_center_api_parts/shared.py`
  - keep shared fake environment payload shape aligned with the real runtime detail contract
- Test: `tests/environments/test_environment_registry.py`
  - formal host-event family/twin projection contract tests
- Test: `tests/app/runtime_center_api_parts/detail_environment.py`
  - runtime center environment/session detail host twin visibility
- Test: `tests/app/test_runtime_projection_contracts.py`
  - task review contract coverage for host twin and event-led continuity
- Test: `tests/app/test_runtime_query_services.py`
  - runtime feedback import of `host_twin`
- Test: `tests/app/test_runtime_center_api.py`
  - runtime center task review output coverage
- Test: `tests/app/test_workflow_templates_api.py`
  - workflow preview preflight blockers driven by `host_twin`
- Modify: `TASK_STATUS.md`
  - phase closeout entry after code and tests are green

## Task 1: Host Event Bus Runtime Semantics

**Files:**
- Modify: `src/copaw/app/runtime_events.py`
- Modify: `src/copaw/environments/health_service.py`
- Test: `tests/environments/test_environment_registry.py`

- [ ] **Step 1: Write failing tests for richer host-event semantics**

Add/extend tests that require:
- host events to expose event-family state usable for recovery/scheduler input
- active blocking family, active recovery family, and human takeover/return events to normalize into the same host-event mechanism
- pending recovery events to carry legal recovery path/checkpoint data

- [ ] **Step 2: Run focused environment tests to verify red**

Run: `python -m pytest tests/environments/test_environment_registry.py -q`
Expected: FAIL on missing host-event/twin fields or missing event-led semantics.

- [ ] **Step 3: Implement minimal bus + health service changes**

Implement:
- host-event classification/normalization for `active-window / modal-uac-login / download-completed / process-exit-restart / lock-unlock / network-power`
- formal handoff/return host events in the same runtime mechanism as other host disturbances
- bus helpers needed to identify active blocking/recovery signals
- environment health summaries for event-led recovery inputs without creating a second truth store
- at least one concrete runtime consumer input path (`workflow preview` or equivalent preflight gate) that uses host-event state to block or redirect mutating execution

- [ ] **Step 4: Run focused environment tests to verify green**

Run: `python -m pytest tests/environments/test_environment_registry.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/runtime_events.py src/copaw/environments/health_service.py tests/environments/test_environment_registry.py
git commit -m "feat: formalize host event bus runtime semantics"
```

## Task 2: Execution-Grade Host Twin Projection

**Files:**
- Modify: `src/copaw/environments/health_service.py`
- Test: `tests/environments/test_environment_registry.py`
- Test: `tests/app/runtime_center_api_parts/detail_environment.py`

- [ ] **Step 1: Write failing tests for host twin projection**

Add/extend tests that require `host_twin` to answer:
- seat owner and active ownership source
- writable/read-only/blocked surfaces
- continuity validity
- trusted evidence anchors
- legal recovery path
- event-driven blocker state and contention forecast inputs

- [ ] **Step 2: Run focused projection tests to verify red**

Run: `python -m pytest tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py -q`
Expected: FAIL on missing `host_twin` payload or missing derived fields.

- [ ] **Step 3: Implement minimal host twin derivation**

Implement a derived `host_twin` projection in `EnvironmentHealthService` using only:
- `EnvironmentMount / SessionMount`
- existing lease/lock/session facts
- workspace graph
- host event summary/events
- latest evidence/verification anchors

- [ ] **Step 4: Run focused projection tests to verify green**

Run: `python -m pytest tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/environments/health_service.py tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py
git commit -m "feat: add execution-grade host twin projection"
```

## Task 3: Runtime Center and Task Review Host Twin Visibility

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/task_review_projection.py`
- Test: `tests/app/test_runtime_projection_contracts.py`
- Test: `tests/app/test_runtime_query_services.py`
- Test: `tests/app/test_runtime_center_api.py`

- [ ] **Step 1: Write failing tests for runtime/read-model consumption**

Add/extend tests that require:
- environment feedback import to carry `host_twin`
- task review payload to expose `execution_runtime.host_twin`
- continuity/risk/next-action summaries to use host twin writable surface and legal recovery path data

- [ ] **Step 2: Run focused runtime-center tests to verify red**

Run: `python -m pytest tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py -q`
Expected: FAIL on missing `host_twin` sections or unchanged review/preflight text.

- [ ] **Step 3: Implement minimal runtime-center wiring**

Implement:
- `host_twin` pass-through in runtime feedback import
- task review projection support for `host_twin`
- summary/next-action/risk lines that prefer twin facts over weaker fallback heuristics

- [ ] **Step 4: Run focused runtime-center tests to verify green**

Run: `python -m pytest tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/runtime_center/state_query.py src/copaw/app/runtime_center/task_review_projection.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py
git commit -m "feat: surface host twin in runtime center task review"
```

## Task 4: Workflow Preview / Preflight Host Twin Blockers

**Files:**
- Modify: `src/copaw/workflows/service_preview.py`
- Test: `tests/app/test_workflow_templates_api.py`

- [ ] **Step 1: Write failing tests for host-twin-driven launch blockers**

Add/extend tests that require workflow preview to block launch when:
- seat continuity is invalid
- target surfaces are not writable
- legal recovery path is `handoff` or unresolved
- active host blocker families make mutating work unsafe

- [ ] **Step 2: Run focused workflow preview tests to verify red**

Run: `python -m pytest tests/app/test_workflow_templates_api.py -q`
Expected: FAIL on missing launch blockers or missing blocker metadata.

- [ ] **Step 3: Implement minimal host-twin-aware preflight**

Implement launch blocker derivation from existing environment detail / host twin facts, keeping workflow preview as a consumer instead of a second truth source.

- [ ] **Step 4: Run focused workflow preview tests to verify green**

Run: `python -m pytest tests/app/test_workflow_templates_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/workflows/service_preview.py tests/app/test_workflow_templates_api.py
git commit -m "feat: use host twin for workflow preview preflight"
```

## Task 5: Integration Verification and Status Sync

**Files:**
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Run focused Phase 4/5 acceptance suite**

Run:
`python -m pytest tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py tests/app/test_workflow_templates_api.py -q`

Expected: PASS

- [ ] **Step 2: Run wider regression covering host/runtime/routine seams**

Run:
`python -m pytest tests/agents/test_browser_tool_evidence.py tests/routines/test_routine_service.py tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py tests/app/test_capability_market_phase2_api.py tests/app/test_workflow_templates_api.py -q`

Expected: PASS

- [ ] **Step 3: Update status board**

Record:
- `Phase 4 Host Event Bus` closeout
- `Phase 5 Execution-Grade Host Twin` closeout
- exact acceptance command/results
- real runtime consumer coverage, not only read-model coverage
- next boundary into mature host-twin / broader phase work

- [ ] **Step 4: Commit**

```bash
git add TASK_STATUS.md
git commit -m "docs: close phase 4 and phase 5 status"
```
