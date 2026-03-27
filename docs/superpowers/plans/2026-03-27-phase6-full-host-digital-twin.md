# Phase 6 Full Host Digital Twin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deepen the execution-side `host_twin` into a mature `Phase 6 Full Host Digital Twin` by adding app-family twin packs, stronger host coordination semantics, and shared host-truth consumers for workflow planning, workflow runs, and fixed SOP execution without introducing a second truth source.

**Architecture:** Keep `Full Host Digital Twin` derived from `EnvironmentMount + SessionMount + TaskRuntime + Artifact/Evidence + host-event/workspace projections`; do not add a parallel host database, event store, or object tree. Phase 6 is execution-side only: execution agents remain the browser/desktop drivers, while the main brain and planning surfaces consume the same host truth for preflight, scheduling, supervision, and recovery decisions.

**Tech Stack:** Python, FastAPI service layer, Pydantic models, pytest

---

## Scope Note

- This is the execution-side `Phase 6 Full Host Digital Twin` plan from `docs/superpowers/specs/2026-03-27-intent-native-universal-carrier-and-symbiotic-host-runtime.md`.
- It does **not** replace the repo-wide 7-layer architecture or the masterplan's separate console/API migration `Phase 6`.
- It starts **after** the already-landed `Phase 4 Host Event Bus` and `Phase 5 Execution-Grade Host Twin`.
- Existing `host_twin`, `workspace_graph`, workflow preview blockers, and Runtime Center visibility are prerequisites, not deliverables for this phase.

## Architectural Invariants

- `Workspace Graph` remains a projection over `TaskRuntime + EnvironmentMount + SessionMount + Artifact/Evidence`; do not create a second workspace object tree.
- `Host Event Bus` remains a runtime mechanism over evidence/observation/runtime projection; do not create an event truth store.
- `Execution-Grade Host Twin` and `Full Host Digital Twin` remain derived runtime projections; do not create a second host-state database.
- Cooperative adapters remain `CapabilityMount` families; do not invent a fourth capability language.
- The main brain remains a planner/supervisor; only execution agents hold live browser/desktop ownership.

## File Map

- Modify: `src/copaw/environments/health_service.py`
  - deepen the derived `host_twin` with `app_family_twins` and `coordination` packs built only from existing host/site/app/workspace/event/evidence facts
- Modify: `src/copaw/app/runtime_center/state_query.py`
  - pass Phase 6 host-twin additions through runtime feedback
- Modify: `src/copaw/app/runtime_center/task_review_projection.py`
  - expose app-family and coordination facts in task review/read-model summaries
- Modify: `src/copaw/app/routers/runtime_center_routes_ops.py`
  - keep formal runtime-surface detection aligned with any new Phase 6 payload sections
- Modify: `src/copaw/workflows/models.py`
  - add explicit host-preflight / host-snapshot model fields for preview and run diagnosis consumers
- Modify: `src/copaw/workflows/service_preview.py`
  - infer app-family requirements and stronger coordination blockers from the canonical host twin
- Modify: `src/copaw/workflows/service_runs.py`
  - persist host preflight snapshots into workflow run metadata/diagnosis, thread host refs into schedule specs, and reuse canonical host truth on resume
- Modify: `src/copaw/app/crons/executor.py`
  - consume schedule host refs / scheduler inputs so cron execution uses canonical host truth instead of guessing from channel session ids
- Modify: `src/copaw/sop_kernel/models.py`
  - add host-aware request/doctor/run detail fields without creating fixed-SOP-local environment truth
- Modify: `src/copaw/sop_kernel/service.py`
  - inject `EnvironmentService`, consume canonical host truth in doctor/run, and record host preflight snapshots in run metadata/evidence
- Modify: `src/copaw/capabilities/system_routine_handlers.py`
  - pass through `environment_id` / `session_mount_id` for host-aware fixed SOP execution
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
  - wire `EnvironmentService` into `FixedSopService`
- Modify: `tests/app/runtime_center_api_parts/shared.py`
  - keep fake environment payload shape aligned with the real Phase 6 host twin contract
- Test: `tests/environments/test_environment_registry.py`
  - lock app-family twin and coordination projection contracts
- Test: `tests/app/runtime_center_api_parts/detail_environment.py`
  - verify environment/session detail visibility for new Phase 6 host twin sections
- Test: `tests/app/test_runtime_projection_contracts.py`
  - verify task review projection carries app-family and coordination facts
- Test: `tests/app/test_runtime_query_services.py`
  - verify runtime feedback imports the Phase 6 host-twin fields
- Test: `tests/app/test_runtime_center_api.py`
  - verify Runtime Center task-review/runtime surfaces expose the new host-twin fields
- Test: `tests/app/test_workflow_templates_api.py`
  - verify preview, launch, run detail, and resume use shared host truth for app-family and coordination checks
- Test: `tests/app/test_cron_executor.py`
  - verify cron execution reuses stored host refs / scheduler inputs instead of inventing a fallback environment guess
- Test: `tests/fixed_sops/test_service.py`
  - verify doctor/run consume canonical host truth and reject unsafe mutating execution
- Test: `tests/app/test_fixed_sop_kernel_api.py`
  - verify fixed-SOP API surfaces the new host-aware doctor/run behavior
- Test: `tests/app/test_capabilities_execution.py`
  - verify system fixed-SOP capability passes environment/session bindings through
- Test: `tests/app/test_runtime_bootstrap_split.py`
  - verify runtime bootstrap wires `EnvironmentService` into `FixedSopService`
- Modify: `TASK_STATUS.md`
  - add the new Phase 6 execution plan reference and next execution order after code is green

## Recommended Execution Order

1. Derive Phase 6 host truth (`app_family_twins` + `coordination`) in `EnvironmentHealthService`.
2. Make Runtime Center/task review consume the new truth.
3. Make workflow preview/run/resume consume the same truth.
4. Make fixed SOP doctor/run consume the same truth.
5. Run focused acceptance, then wider regression, then update status.

## Task 1: Derived App-Family Twin Packs And Coordination Core

**Files:**
- Modify: `src/copaw/environments/health_service.py`
- Test: `tests/environments/test_environment_registry.py`
- Test: `tests/app/runtime_center_api_parts/detail_environment.py`

- [ ] **Step 1: Write the failing tests**

Add/extend tests that require `host_twin` to expose two new Phase 6 projection sections:

```python
app_family_twins = detail["host_twin"]["app_family_twins"]
coordination = detail["host_twin"]["coordination"]

assert app_family_twins["browser_backoffice"]["contract_status"] == "verified-writer"
assert app_family_twins["office_document"]["writer_lock_scope"] == "workbook:weekly-report"
assert coordination["writer_owner_ref"] == "agent:solution-lead"
assert coordination["contention_forecast"]["severity"] == "blocked"
```

Required derived packs:
- `app_family_twins.browser_backoffice`
- `app_family_twins.messaging_workspace`
- `app_family_twins.office_document`
- `app_family_twins.desktop_specialized`

Required coordination facts:
- `seat_owner_ref`
- `candidate_seat_refs`
- `selected_seat_ref`
- `seat_selection_policy`
- `workspace_owner_ref`
- `writer_owner_ref`
- `contention_forecast`
- `legal_owner_transition`
- `recommended_scheduler_action`
- `expected_release_at`

- [ ] **Step 2: Run focused projection tests to verify red**

Run:
`python -m pytest tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py -q`

Expected: FAIL on missing `app_family_twins` / `coordination` sections or missing derived fields.

- [ ] **Step 3: Implement minimal Phase 6 host-twin derivation**

Implement in `EnvironmentHealthService`:
- `app_family_twins` derived only from existing `host_contract`, `browser_site_contract`, `desktop_app_contract`, `workspace_graph`, `host_event_summary`, and trusted anchors
- `coordination` derived only from existing ownership, lock, handoff, and blocker facts
- `seat_runtime` extended into scheduler-grade projection fields (`status`, `occupancy_state`, `candidate_seat_refs`, `selected_seat_ref`, `expected_release_at`) without creating a new seat truth store
- family classification rules based on canonical site/app/runtime descriptors rather than template-local guesses
- no new repository, no new persistent host object, no second truth source

Example target payload shape:

```python
host_twin["coordination"] = {
    "seat_owner_ref": "...",
    "workspace_owner_ref": "...",
    "writer_owner_ref": "...",
    "contention_forecast": {"severity": "blocked", "reason": "..."},
    "legal_owner_transition": {"allowed": False, "reason": "..."},
    "recommended_scheduler_action": "handoff",
}
```

- [ ] **Step 4: Run focused projection tests to verify green**

Run:
`python -m pytest tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/environments/health_service.py tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py
git commit -m "feat: deepen host twin with app-family and coordination projections"
```

## Task 2: Runtime Center And Task Review Phase 6 Visibility

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/task_review_projection.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_ops.py`
- Modify: `tests/app/runtime_center_api_parts/shared.py`
- Test: `tests/app/test_runtime_projection_contracts.py`
- Test: `tests/app/test_runtime_query_services.py`
- Test: `tests/app/test_runtime_center_api.py`

- [ ] **Step 1: Write the failing tests**

Add/extend tests that require:
- runtime feedback to carry `host_twin.app_family_twins` and `host_twin.coordination`
- task review payload to expose those fields under `execution_runtime.host_twin`
- review summary / next-action / risk lines to prefer Phase 6 coordination facts over weaker fallbacks

```python
payload = build_task_review_payload(...)
host_twin = payload["execution_runtime"]["host_twin"]

assert "coordination" in host_twin
assert host_twin["coordination"]["recommended_scheduler_action"] == "handoff"
assert "office_document" in host_twin["app_family_twins"]
```

- [ ] **Step 2: Run focused runtime-center tests to verify red**

Run:
`python -m pytest tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py -q`

Expected: FAIL on missing Phase 6 payload sections or unchanged review summaries.

- [ ] **Step 3: Implement minimal Runtime Center wiring**

Implement:
- pass-through for new `host_twin` fields in runtime feedback
- Phase 6 task-review helpers for app-family readiness and coordination/risk summaries
- shared fake payload updates so tests consume the same contract shape as the real service

- [ ] **Step 4: Run focused runtime-center tests to verify green**

Run:
`python -m pytest tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/runtime_center/state_query.py src/copaw/app/runtime_center/task_review_projection.py src/copaw/app/routers/runtime_center_routes_ops.py tests/app/runtime_center_api_parts/shared.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py
git commit -m "feat: surface phase 6 host twin facts in runtime center"
```

## Task 3: Workflow Preview, Run Lifecycle, And Scheduling Host-Truth Consumers

**Files:**
- Modify: `src/copaw/workflows/models.py`
- Modify: `src/copaw/workflows/service_preview.py`
- Modify: `src/copaw/workflows/service_runs.py`
- Modify: `src/copaw/app/crons/executor.py`
- Test: `tests/app/test_workflow_templates_api.py`
- Test: `tests/app/test_cron_executor.py`

- [ ] **Step 1: Write the failing tests**

Add/extend tests that require:
- preview to declare explicit `host_requirements` / app-family requirements for mutating steps
- preview blockers to use Phase 6 `coordination` and `app_family_twins`
- launched workflow runs to retain a host preflight snapshot in run diagnosis/detail
- resume to re-check canonical host truth rather than trusting stale run metadata alone
- materialized schedule steps to retain `environment_id` / `session_mount_id` / host requirement metadata
- cron execution to prefer those stored refs and scheduler inputs over `session:{channel}:{session_id}` fallback guessing

Example assertions:

```python
assert payload["host_requirements"][0]["app_family"] == "office_document"
assert any(item["code"] == "host-twin-contention-forecast-blocked" for item in payload["launch_blockers"])
assert detail_payload["diagnosis"]["host_snapshot"]["coordination"]["recommended_scheduler_action"] == "handoff"
assert cron_kernel_task.environment_ref == "env:session:session:web:main"
```

- [ ] **Step 2: Run focused workflow tests to verify red**

Run:
`python -m pytest tests/app/test_workflow_templates_api.py tests/app/test_cron_executor.py -q`

Expected: FAIL on missing host requirement fields, missing blockers, missing run-diagnosis host snapshot, or cron still using fallback environment refs.

- [ ] **Step 3: Implement minimal workflow consumers**

Implement:
- explicit host requirement inference from step `environment_preflight` + required capabilities
- app-family and coordination blockers from the canonical host twin only
- workflow run metadata/diagnosis host snapshot built from canonical environment detail
- resume logic that re-resolves current environment/session detail before mutating execution continues
- schedule spec `meta` fields that carry host refs and host requirement descriptors forward from workflow materialization
- cron executor logic that consumes those stored refs and canonical scheduler inputs before dispatch

- [ ] **Step 4: Run focused workflow tests to verify green**

Run:
`python -m pytest tests/app/test_workflow_templates_api.py tests/app/test_cron_executor.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/workflows/models.py src/copaw/workflows/service_preview.py src/copaw/workflows/service_runs.py src/copaw/app/crons/executor.py tests/app/test_workflow_templates_api.py tests/app/test_cron_executor.py
git commit -m "feat: consume phase 6 host truth in workflow planning runs and scheduling"
```

## Task 4: Fixed SOP Doctor And Run Host-Truth Consumers

**Files:**
- Modify: `src/copaw/sop_kernel/models.py`
- Modify: `src/copaw/sop_kernel/service.py`
- Modify: `src/copaw/capabilities/system_routine_handlers.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Test: `tests/fixed_sops/test_service.py`
- Test: `tests/app/test_fixed_sop_kernel_api.py`
- Test: `tests/app/test_capabilities_execution.py`
- Test: `tests/app/test_runtime_bootstrap_split.py`

- [ ] **Step 1: Write the failing tests**

Add/extend tests that require:
- `FixedSopRunRequest` to accept `environment_id` / `session_mount_id`
- `run_doctor()` to use canonical environment detail and return `blocked` when mutating execution has no legal writable path
- `run_binding()` to refuse unsafe mutating execution instead of silently running through a broken host state
- the system fixed-SOP capability facade to pass environment/session refs through
- runtime bootstrap to inject `EnvironmentService` into `FixedSopService`

Example assertions:

```python
doctor = service.run_doctor("binding-1")
assert doctor.status == "blocked"
assert doctor.host_preflight["coordination"]["recommended_scheduler_action"] == "handoff"

with pytest.raises(ValueError, match="host preflight"):
    await service.run_binding("binding-1", FixedSopRunRequest(session_mount_id="session-1"))
```

- [ ] **Step 2: Run focused fixed-SOP tests to verify red**

Run:
`python -m pytest tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py tests/app/test_capabilities_execution.py tests/app/test_runtime_bootstrap_split.py -q`

Expected: FAIL on missing request fields, missing doctor output, or unsafe run behavior still succeeding.

- [ ] **Step 3: Implement minimal fixed-SOP consumers**

Implement:
- `EnvironmentService` injection into `FixedSopService`
- shared host preflight evaluation based on canonical `host_twin`
- doctor/run metadata that records host snapshot and blocker/recovery facts without creating fixed-SOP-local truth
- system routine handler pass-through for `environment_id` / `session_mount_id`

- [ ] **Step 4: Run focused fixed-SOP tests to verify green**

Run:
`python -m pytest tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py tests/app/test_capabilities_execution.py tests/app/test_runtime_bootstrap_split.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/sop_kernel/models.py src/copaw/sop_kernel/service.py src/copaw/capabilities/system_routine_handlers.py src/copaw/app/runtime_bootstrap_domains.py tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py tests/app/test_capabilities_execution.py tests/app/test_runtime_bootstrap_split.py
git commit -m "feat: use phase 6 host truth in fixed sop execution"
```

## Task 5: Phase 6 Focused Acceptance, Wider Regression, And Status Sync

**Files:**
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Run focused Phase 6 acceptance**

Run:
`python -m pytest tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py tests/app/test_workflow_templates_api.py tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py tests/app/test_capabilities_execution.py tests/app/test_runtime_bootstrap_split.py -q`

Expected: PASS

- [ ] **Step 2: Run the wider host/runtime regression**

Run:
`python -m pytest tests/agents/test_browser_tool_evidence.py tests/routines/test_routine_service.py tests/environments/test_environment_registry.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/test_runtime_projection_contracts.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_api.py tests/app/test_capability_market_phase2_api.py tests/app/test_workflow_templates_api.py tests/app/test_cron_executor.py tests/fixed_sops/test_service.py tests/app/test_fixed_sop_kernel_api.py tests/app/test_capabilities_execution.py tests/app/test_runtime_bootstrap_split.py -q`

Expected: PASS

- [ ] **Step 3: Update the status board**

Record:
- Phase 6 plan execution results
- exact acceptance commands/results
- landed app-family twin coverage
- landed workflow/fixed-SOP host-truth consumers
- remaining mature-state gaps, if any, into later execution-side work

- [ ] **Step 4: Commit**

```bash
git add TASK_STATUS.md
git commit -m "docs: sync phase 6 host twin status"
```

## Exit Criteria

Phase 6 is only considered real when all of the following are true:

- `host_twin` exposes derived app-family packs and explicit coordination facts without a second truth source
- Runtime Center and task review consume those facts directly
- workflow preview, launch, run diagnosis, and resume consume shared host truth rather than rebuilding environment guesses
- fixed SOP doctor/run consume shared host truth rather than running blind
- acceptance proves concurrent host work is blocked, handed off, or resumed through explicit coordination semantics instead of silent corruption
