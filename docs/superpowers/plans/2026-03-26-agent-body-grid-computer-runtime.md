# Agent Body Grid Symbiotic Host Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild CoPaw's execution-side computer runtime so it becomes the `Symbiotic Host Runtime` layer inside `Intent-Native Universal Carrier`: execution agents own durable Windows seats, browser/desktop/document work all run through observe-act-verify loops or stronger native/cooperative paths, multi-agent contention is scheduled through leases, and the live system can complete real machine tasks instead of merely calling low-level tools.

**Architecture:** Keep the current hard-cut main chain unchanged at the planning/supervision layer, but upgrade the execution-side `Agent Body Grid` into `Symbiotic Host Runtime`, grounded in existing `EnvironmentMount` and `SessionMount` objects. This plan covers the current execution-side baseline only: `Windows Seat Runtime Baseline`. It does not replace the existing 7-layer target architecture, and it does not treat `Workspace Graph` or `Host Event Bus` as new truth stores. Role workflows remain the coherent "how this role works" layer, while body scheduling becomes the resource/runtime substrate underneath them. Browser and desktop must share one `Surface Host Contract`; browser adds site contracts, Windows desktop adds app/window contracts, and both should increasingly hang off the same durable seat/runtime context. Browser work must be mode-aware from the beginning: `managed-isolated`, `attach-existing-session`, and `remote-provider` are all formal runtime modes, and desktop work is explicitly Windows-first rather than a generic cross-platform click layer. Prefer native/cooperative paths before raw UI fallback.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLite state/evidence repositories, Playwright, Win32 desktop automation, pytest, TypeScript/React for operator visibility

**Companion Docs:**
- Upper framing: `docs/superpowers/specs/2026-03-27-intent-native-universal-carrier-and-symbiotic-host-runtime.md`
- Spec: `docs/superpowers/specs/2026-03-26-agent-body-grid-computer-runtime.md`
- Fixed SOP retirement: `docs/superpowers/specs/2026-03-26-native-fixed-sop-kernel-and-n8n-retirement.md`
- Existing runtime-first alignment: `docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md`
- Baseline status: `TASK_STATUS.md`
- Data model: `DATA_MODEL_DRAFT.md`

---

## Cross-Plan Order

This plan is not the first cut in isolation.

Recommended sequencing across the four documents:

1. lock the `Native Fixed SOP Kernel` hard-cut decision first
2. start the body-runtime acceptance harness and execution-loop refactor
3. align workflow launch with native fixed SOP kernel boundaries before deep scheduler work
4. retire legacy tool-first paths only after both the body runtime and fixed SOP hard cut are already real

This prevents the project from building a new execution runtime while still leaving the old automation sidecar alive as a parallel target.

## Current Scope: Phase 1 Seat Runtime Baseline

This plan does **not** attempt to land the full mature `Full Host Digital Twin`.

This plan only covers the first formal stage of `Symbiotic Host Runtime`:

- `Seat Runtime`
- `Host Companion Session`
- shared `Surface Host Contract`
- browser `Site Contract`
- Windows `Desktop App Contract`
- minimal `Workspace Graph` projection
- minimal `Host Event Bus` mechanism
- Runtime Center / Agent Workbench visibility for seat/workspace/host recovery facts

Hard boundaries:

- this is an execution-side plan, not a replacement for the repo's 7-layer architecture
- `Workspace Graph` must remain a projection over existing runtime/environment/evidence objects
- `Host Event Bus` must remain a runtime mechanism, not a second event truth store

## Scope Guardrails

- Do not move computer-operation ownership back into the main brain.
- Do not introduce a second formal state vocabulary; all new execution-body language must map to existing formal objects.
- Do not replace role workflows/routines with the body scheduler; scheduler is a lower execution substrate.
- Do not let fixed SOP handling re-expand into an external workflow hub, community JSON import path, or generic RPA DSL.
- Do not treat raw UI automation as the only or preferred execution language when a cooperative/native path exists.
- Do not claim success based on tool payloads alone; real acceptance tasks are the only completion bar.
- Do not let multiple agents mutate the same live document/account/window without a formal exclusive lease.
- Do not delete all governance; keep `auto / guarded / confirm`.

## File Map

### Docs and status

- Modify: `docs/superpowers/specs/2026-03-27-intent-native-universal-carrier-and-symbiotic-host-runtime.md`
- Modify: `docs/superpowers/specs/2026-03-26-agent-body-grid-computer-runtime.md`
- Modify: `docs/superpowers/plans/2026-03-26-agent-body-grid-computer-runtime.md`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `V6_ROUTINE_MUSCLE_MEMORY_PLAN.md`

### Workflow and SOP alignment

- Modify: `src/copaw/workflows/models.py`
- Modify: `src/copaw/workflows/service_preview.py`
- Modify: `src/copaw/workflows/service_runs.py`
- Create: `src/copaw/sop_kernel/models.py`
- Create: `src/copaw/sop_kernel/service.py`
- Create: `src/copaw/app/routers/fixed_sops.py`
- Delete: `src/copaw/app/routers/sop_adapters.py`

### Acceptance harness

- Create: `tests/runtime_bodies/test_seat_runtime_baseline.py`
- Create: `tests/runtime_bodies/test_browser_real_form_flow.py`
- Create: `tests/runtime_bodies/test_browser_site_contracts.py`
- Create: `tests/runtime_bodies/test_surface_host_contracts.py`
- Create: `tests/runtime_bodies/test_document_real_save_flow.py`
- Create: `tests/runtime_bodies/test_desktop_real_app_flow.py`
- Create: `tests/runtime_bodies/test_desktop_app_contracts.py`
- Create: `tests/runtime_bodies/test_workspace_graph.py`
- Create: `tests/runtime_bodies/test_host_event_bus.py`
- Create: `tests/runtime_bodies/test_body_scheduler_contention.py`
- Create: `tests/runtime_bodies/test_body_recovery_resume.py`
- Create: `tests/runtime_bodies/conftest.py`

### Body runtime and scheduling

- Create: `src/copaw/computer_runtime/body_models.py`
- Create: `src/copaw/computer_runtime/body_scheduler.py`
- Create: `src/copaw/computer_runtime/body_runtime.py`
- Create: `src/copaw/computer_runtime/body_checkpoint_service.py`
- Create: `src/copaw/computer_runtime/seat_runtime.py`
- Create: `src/copaw/computer_runtime/host_companion.py`
- Create: `src/copaw/computer_runtime/workspace_graph.py`
- Create: `src/copaw/computer_runtime/host_event_bus.py`
- Create: `src/copaw/computer_runtime/surface_host_contracts.py`
- Create: `src/copaw/computer_runtime/__init__.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/lease_service.py`
- Modify: `src/copaw/environments/health_service.py`

### Browser operator refactor

- Create: `src/copaw/computer_runtime/browser_operator.py`
- Create: `src/copaw/computer_runtime/browser_verifier.py`
- Create: `src/copaw/computer_runtime/browser_site_contracts.py`
- Modify: `src/copaw/agents/tools/browser_control.py`
- Modify: `src/copaw/agents/tools/browser_control_shared.py`
- Modify: `src/copaw/capabilities/browser_runtime.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/kernel/tool_bridge.py`

### Desktop/document operator refactor

- Create: `src/copaw/computer_runtime/desktop_operator.py`
- Create: `src/copaw/computer_runtime/document_operator.py`
- Create: `src/copaw/computer_runtime/desktop_verifier.py`
- Create: `src/copaw/computer_runtime/desktop_app_contracts.py`
- Modify: `src/copaw/adapters/desktop/windows_host.py`
- Modify: `src/copaw/adapters/desktop/windows_mcp_server.py`
- Modify: `src/copaw/routines/service.py`
- Modify: `src/copaw/kernel/query_execution_team.py`
- Modify: `src/copaw/kernel/tool_bridge.py`

### Recovery integration

- Modify: `src/copaw/kernel/main_brain_environment_coordinator.py`
- Modify: `src/copaw/kernel/main_brain_recovery_coordinator.py`
- Modify: `src/copaw/kernel/main_brain_result_committer.py`
- Modify: `src/copaw/app/startup_recovery.py`
- Modify: `src/copaw/app/runtime_health_service.py`

### Runtime center visibility

- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `src/copaw/app/runtime_center/task_review_projection.py`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/AgentWorkbench/sections/runtimePanels.tsx`

---

### Task 1: Lock the Agent Body Grid Contract and Cross-Doc Alignment

**Files:**
- Modify: `docs/superpowers/specs/2026-03-26-agent-body-grid-computer-runtime.md`
- Modify: `docs/superpowers/plans/2026-03-26-agent-body-grid-computer-runtime.md`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`

- [ ] **Step 1: Add a failing documentation expectation test**

```python
def test_agent_body_grid_spec_declares_execution_agents_own_bodies() -> None:
    text = Path("docs/superpowers/specs/2026-03-26-agent-body-grid-computer-runtime.md").read_text(encoding="utf-8")
    assert "execution agents, not the main brain, own computer-operation bodies" in text
    assert "Symbiotic Host Runtime" in text
    assert "Surface Host Contract" in text
    assert "lease_class" in text and "access_mode" in text
    assert "managed-isolated" in text and "attach-existing-session" in text
    assert "Windows-first" in text
    assert "observe" in text and "verify" in text
```

- [ ] **Step 2: Run the targeted documentation check**

Run: `python -m pytest tests/runtime_bodies -q -k spec`
Expected: FAIL until the new spec references exist.

- [ ] **Step 3: Align the spec, plan, and model/status contract**

Rules:
- `TASK_STATUS.md` must mention this spec only as an execution-side supplement, not as a new main chain.
- `DATA_MODEL_DRAFT.md` must map `AgentBody / BodySession / BodyLease` back to existing formal objects.
- browser spec must distinguish `managed-isolated / attach-existing-session / remote-provider` and define explicit mode-scoped capability gaps
- browser data-model mapping must land on `SessionMount`/existing recovery vocabulary instead of introducing browser-only truth objects
- browser site contract and human handoff must stay execution-side and must not be rewritten as
  main-brain direct browser control
- shared `Surface Host Contract` fields must stay consistent across browser and desktop instead of
  splitting into two separate readiness/handoff vocabularies
- the upper target framing is now `Intent-Native Universal Carrier`, while this plan remains the
  execution-side `Symbiotic Host Runtime` plan; do not flatten them into the same layer
- this plan currently covers `Windows Seat Runtime Baseline`, not a one-shot `Full Host Digital Twin`
- `Workspace Graph` must remain a projection instead of a new runtime state tree
- `Host Event Bus` must remain a runtime mechanism instead of a separate event truth store
- shared host truth must explicitly cover
  `host_mode / lease_class / access_mode / session_scope / handoff_state / resume_kind /
  verification_channel / capability_summary / current_gap_or_blocker`
- live writer surfaces without explicit `lease_class / access_mode` must be treated as malformed
  runtime state rather than silently downgraded in logs
- desktop/app work is Windows-first in this repo; do not pivot the plan toward macOS companion
  assumptions
- Windows desktop writer flows must resolve `Desktop App Contract` metadata for known apps instead of
  staying a generic click/type surface
- this plan must remain downstream of the native fixed SOP hard cut instead of competing with it

- [ ] **Step 4: Re-run the targeted documentation check**

Run: `python -m pytest tests/runtime_bodies -q -k spec`
Expected: PASS.

- [ ] **Step 5: Save a checkpoint**

Run: `git diff --stat`
Expected: only docs/status/model draft changed.

### Task 2: Build the Real Acceptance Harness First

**Files:**
- Create: `tests/runtime_bodies/test_browser_real_form_flow.py`
- Create: `tests/runtime_bodies/test_browser_site_contracts.py`
- Create: `tests/runtime_bodies/test_surface_host_contracts.py`
- Create: `tests/runtime_bodies/test_document_real_save_flow.py`
- Create: `tests/runtime_bodies/test_desktop_real_app_flow.py`
- Create: `tests/runtime_bodies/test_desktop_app_contracts.py`
- Create: `tests/runtime_bodies/test_body_scheduler_contention.py`
- Create: `tests/runtime_bodies/test_body_recovery_resume.py`
- Create: `tests/runtime_bodies/conftest.py`

- [ ] **Step 1: Write the failing browser real-flow tests for managed and attached sessions**

```python
def test_browser_form_flow_reads_fills_submits_and_verifies(...) -> None:
    result = run_browser_acceptance_flow(...)
    assert result.status == "completed"
    assert result.verified is True

def test_browser_existing_session_flow_continues_authenticated_backend_work(...) -> None:
    result = run_browser_acceptance_flow(mode="attach-existing-session", ...)
    assert result.status == "completed"
    assert result.resume_kind in {"attach-environment", "resume-environment"}

def test_browser_known_backend_requires_site_contract_or_governed_handoff(...) -> None:
    result = run_browser_acceptance_flow(mode="attach-existing-session", ...)
    assert result.status in {"blocked", "handoff-required", "completed"}
```

- [ ] **Step 2: Add failing shared host/site/app contract tests**

```python
def test_surface_host_contract_projects_explicit_lease_class_and_access_mode(...) -> None:
    ...

def test_browser_site_contract_blocks_known_writer_flow_without_contract(...) -> None:
    ...

def test_windows_desktop_app_contract_blocks_known_writer_flow_without_contract(...) -> None:
    ...
```

- [ ] **Step 3: Write the failing document save/reopen test**

```python
def test_document_flow_writes_saves_reopens_and_verifies(...) -> None:
    result = run_document_acceptance_flow(...)
    assert result.saved_text == "expected text"
```

- [ ] **Step 4: Write the failing desktop app state-change test**

```python
def test_desktop_flow_changes_real_app_state(...) -> None:
    result = run_desktop_acceptance_flow(...)
    assert result.verified is True
```

- [ ] **Step 5: Run the acceptance suite to capture the current failures**

Run: `python -m pytest tests/runtime_bodies/test_browser_real_form_flow.py tests/runtime_bodies/test_browser_site_contracts.py tests/runtime_bodies/test_surface_host_contracts.py tests/runtime_bodies/test_document_real_save_flow.py tests/runtime_bodies/test_desktop_real_app_flow.py tests/runtime_bodies/test_desktop_app_contracts.py -q`
Expected: FAIL with current browser submit/attach-session/document save/desktop verification gaps.

- [ ] **Step 6: Save the failing evidence**

Run: `python -m pytest tests/runtime_bodies/test_browser_real_form_flow.py tests/runtime_bodies/test_browser_site_contracts.py tests/runtime_bodies/test_surface_host_contracts.py tests/runtime_bodies/test_document_real_save_flow.py tests/runtime_bodies/test_desktop_real_app_flow.py tests/runtime_bodies/test_desktop_app_contracts.py -q > runtime_body_failures.txt`
Expected: failure log captured for root-cause work.

### Task 3: Align Workflow and Native Fixed SOP Kernel Contracts Before Body Scheduling

**Files:**
- Modify: `src/copaw/workflows/models.py`
- Modify: `src/copaw/workflows/service_preview.py`
- Modify: `src/copaw/workflows/service_runs.py`
- Create: `src/copaw/sop_kernel/models.py`
- Create: `src/copaw/sop_kernel/service.py`
- Create: `src/copaw/app/routers/fixed_sops.py`
- Delete: `src/copaw/app/routers/sop_adapters.py`

- [ ] **Step 1: Add failing workflow-preview tests for body/resource awareness**

```python
def test_workflow_preview_blocks_when_required_writer_body_is_unavailable(...) -> None:
    ...

def test_workflow_preview_allows_parallel_read_only_research_bodies(...) -> None:
    ...
```

- [ ] **Step 2: Extend workflow step contracts**

Rules:
- workflow steps must be able to declare required body kind, execution surface, and lease class
- preview/launch must validate body/session/resource availability in addition to capability availability
- role workflow remains the coherent execution shell; it must not be replaced by routine definitions

- [ ] **Step 3: Land the native fixed SOP kernel boundary**

Rules:
- retire `n8n` / external workflow-hub surfaces completely
- native fixed SOP kernel supports only webhook/schedule/API-first low-judgment flows
- any real browser/desktop/document mutation must callback into CoPaw body runtime or routine replay
- workflow truth, evidence truth, and recovery truth must stay in CoPaw
- no community template market or external JSON import survives the hard cut

- [ ] **Step 4: Re-run targeted workflow/SOP alignment tests**

Run: `python -m pytest tests/workflows tests/app -q -k "workflow or sop"`
Expected: PASS for body-aware workflow launch and native fixed SOP kernel boundaries.

### Task 4: Introduce Body Runtime, Body Leases, and Scheduling

**Files:**
- Create: `src/copaw/computer_runtime/body_models.py`
- Create: `src/copaw/computer_runtime/body_scheduler.py`
- Create: `src/copaw/computer_runtime/body_runtime.py`
- Create: `src/copaw/computer_runtime/body_checkpoint_service.py`
- Create: `src/copaw/computer_runtime/surface_host_contracts.py`
- Create: `src/copaw/computer_runtime/__init__.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/lease_service.py`
- Modify: `src/copaw/environments/health_service.py`
- Test: `tests/runtime_bodies/test_surface_host_contracts.py`
- Test: `tests/runtime_bodies/test_body_scheduler_contention.py`

- [ ] **Step 1: Write failing contention and exclusive-lease tests**

```python
def test_only_one_writer_body_can_hold_a_document_write_lease(...) -> None:
    ...

def test_multiple_research_bodies_can_hold_parallel_read_leases(...) -> None:
    ...

def test_surface_host_contract_requires_explicit_lease_class_and_access_mode(...) -> None:
    ...
```

- [ ] **Step 2: Run the scheduler tests to verify failure**

Run: `python -m pytest tests/runtime_bodies/test_body_scheduler_contention.py tests/runtime_bodies/test_surface_host_contracts.py -q`
Expected: FAIL because no formal body scheduler exists yet.

- [ ] **Step 3: Add body models and scheduler mapped to EnvironmentMount/SessionMount**

Rules:
- no new top-level truth source
- body and lease state must map to environment/session/resource-slot data
- exclusive write resources and parallel read resources must be explicitly classified
- shared surface host metadata must be normalized in one place instead of reimplemented in browser
  and desktop code separately
- `host_mode` must remain the shared cross-surface host truth; browser/app-specific contracts may
  refine it but may not replace it
- `lease_class` and `access_mode` must be persisted/queryable and visible to scheduler/health/UI

- [ ] **Step 4: Re-run contention tests**

Run: `python -m pytest tests/runtime_bodies/test_body_scheduler_contention.py tests/runtime_bodies/test_surface_host_contracts.py -q`
Expected: PASS.

- [ ] **Step 5: Commit the body scheduler slice**

```bash
git add src/copaw/computer_runtime src/copaw/environments tests/runtime_bodies/test_body_scheduler_contention.py tests/runtime_bodies/test_surface_host_contracts.py
git commit -m "feat: add agent body scheduler and lease model"
```

### Task 5: Rebuild the Browser Operator Around Observe-Act-Verify

**Files:**
- Create: `src/copaw/computer_runtime/browser_operator.py`
- Create: `src/copaw/computer_runtime/browser_verifier.py`
- Create: `src/copaw/computer_runtime/browser_site_contracts.py`
- Modify: `src/copaw/agents/tools/browser_control.py`
- Modify: `src/copaw/agents/tools/browser_control_shared.py`
- Modify: `src/copaw/capabilities/browser_runtime.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/kernel/tool_bridge.py`
- Test: `tests/runtime_bodies/test_browser_real_form_flow.py`
- Test: `tests/runtime_bodies/test_browser_site_contracts.py`

- [ ] **Step 1: Reduce the failing browser test to the exact submit/verify gap**

Run: `python -m pytest tests/runtime_bodies/test_browser_real_form_flow.py tests/runtime_bodies/test_browser_site_contracts.py -q -vv`
Expected: FAIL on the real form flow.

- [ ] **Step 2: Add a browser operator contract test for post-action verification**

```python
def test_browser_operator_requires_surface_verification_after_submit(...) -> None:
    ...

def test_browser_attach_mode_reports_capability_gap_for_unsupported_operation(...) -> None:
    ...

def test_browser_writer_action_requires_site_contract_for_known_backend(...) -> None:
    ...

def test_browser_resumes_with_reobserve_after_human_handoff(...) -> None:
    ...
```

- [ ] **Step 3: Implement BrowserOperator and BrowserVerifier**

Rules:
- DOM-first, vision-fallback
- browser runtime must explicitly distinguish `managed-isolated / attach-existing-session / remote-provider`
- known-site authenticated writer flows must resolve site contract before acting
- browser surfaces must project shared `Surface Host Contract` fields before browser-only fields
- each action returns observed-before, action, observed-after, verification result
- browser session resume must remain compatible with existing runtime/profile storage
- attach-existing-session is first-class for authenticated continuation, but unsupported downloads/PDF/context overrides must stay explicit
- browser evidence must record verified outcome, not only raw action payload
- human handoff for login/CAPTCHA/MFA/recovery must emit checkpoint + evidence + return semantics
- mode-scoped capability/readiness state must be queryable by Runtime Center and recovery flows

- [ ] **Step 4: Re-run the browser real-flow tests**

Run: `python -m pytest tests/runtime_bodies/test_browser_real_form_flow.py tests/runtime_bodies/test_browser_site_contracts.py tests/agents/test_browser_tool_evidence.py -q`
Expected: PASS.

- [ ] **Step 5: Commit the browser operator slice**

```bash
git add src/copaw/computer_runtime src/copaw/agents/tools src/copaw/capabilities src/copaw/kernel tests/runtime_bodies/test_browser_real_form_flow.py tests/runtime_bodies/test_browser_site_contracts.py tests/agents/test_browser_tool_evidence.py
git commit -m "feat: add verified browser operator loop"
```

### Task 6: Rebuild Desktop and Document Operators Around Verified State Change

**Files:**
- Create: `src/copaw/computer_runtime/desktop_operator.py`
- Create: `src/copaw/computer_runtime/document_operator.py`
- Create: `src/copaw/computer_runtime/desktop_verifier.py`
- Create: `src/copaw/computer_runtime/desktop_app_contracts.py`
- Modify: `src/copaw/adapters/desktop/windows_host.py`
- Modify: `src/copaw/adapters/desktop/windows_mcp_server.py`
- Modify: `src/copaw/routines/service.py`
- Modify: `src/copaw/kernel/query_execution_team.py`
- Modify: `src/copaw/kernel/tool_bridge.py`
- Test: `tests/runtime_bodies/test_document_real_save_flow.py`
- Test: `tests/runtime_bodies/test_desktop_real_app_flow.py`
- Test: `tests/runtime_bodies/test_desktop_app_contracts.py`

- [ ] **Step 1: Run the real document and desktop tests to capture the current false-success behavior**

Run: `python -m pytest tests/runtime_bodies/test_document_real_save_flow.py tests/runtime_bodies/test_desktop_real_app_flow.py tests/runtime_bodies/test_desktop_app_contracts.py -q -vv`
Expected: FAIL on save/reopen and/or state verification.

- [ ] **Step 2: Add contract tests for verified state change**

```python
def test_document_operator_does_not_report_success_without_saved_content(...) -> None:
    ...

def test_desktop_operator_does_not_report_success_without_observed_app_change(...) -> None:
    ...

def test_windows_desktop_surface_projects_shared_host_contract_before_app_fields(...) -> None:
    ...

def test_windows_desktop_writer_action_requires_app_contract_for_known_app(...) -> None:
    ...

def test_windows_desktop_resume_after_handoff_reobserves_active_window(...) -> None:
    ...
```

- [ ] **Step 3: Implement DesktopOperator, DocumentOperator, and DesktopVerifier**

Rules:
- desktop surfaces must project shared `Surface Host Contract` fields before app-specific details
- current repo contract is Windows-first: foreground window/process/control identity is baseline
- actions must verify target state again after acting
- document save is only successful if reopened content matches expectation
- desktop action success must not be based on Win32 API return alone
- known Windows app writer flows must resolve `app contract` before mutating app state
- desktop handoff/login/UAC/modal rescue must emit checkpoint + evidence + return semantics
- add desktop evidence sink support to the kernel bridge

- [ ] **Step 4: Re-run desktop/document tests**

Run: `python -m pytest tests/runtime_bodies/test_document_real_save_flow.py tests/runtime_bodies/test_desktop_real_app_flow.py tests/runtime_bodies/test_desktop_app_contracts.py tests/adapters/test_windows_host.py -q`
Expected: PASS.

- [ ] **Step 5: Commit the desktop/document slice**

```bash
git add src/copaw/computer_runtime src/copaw/adapters/desktop src/copaw/routines src/copaw/kernel tests/runtime_bodies/test_document_real_save_flow.py tests/runtime_bodies/test_desktop_real_app_flow.py tests/runtime_bodies/test_desktop_app_contracts.py tests/adapters/test_windows_host.py
git commit -m "feat: add verified desktop and document operators"
```

### Task 7: Unify Body Recovery Into the Main Execution Chain

**Files:**
- Modify: `src/copaw/kernel/main_brain_environment_coordinator.py`
- Modify: `src/copaw/kernel/main_brain_recovery_coordinator.py`
- Modify: `src/copaw/kernel/main_brain_result_committer.py`
- Modify: `src/copaw/app/startup_recovery.py`
- Modify: `src/copaw/app/runtime_health_service.py`
- Modify: `src/copaw/environments/health_service.py`
- Test: `tests/runtime_bodies/test_body_recovery_resume.py`

- [ ] **Step 1: Write the failing body-recovery test**

```python
def test_body_recovery_resumes_from_last_verified_checkpoint(...) -> None:
    result = recover_body_session(...)
    assert result.resume_kind == "checkpoint-resume"
    assert result.can_continue is True
```

- [ ] **Step 2: Run the recovery test to verify failure**

Run: `python -m pytest tests/runtime_bodies/test_body_recovery_resume.py tests/app/test_startup_recovery.py -q`
Expected: FAIL because recovery still stops at metadata-level coordination.

- [ ] **Step 3: Extend coordinators and startup recovery with body semantics**

Rules:
- recovery must be visible as environment/session/body state, not just request attrs
- runtime health must expose body-runtime readiness and recovery health
- recovery must preserve browser mode, attach/provider references, and explicit `resume / rebind / attach / fresh` outcome
- recovery must preserve site-contract and handoff state, and resume must force a fresh re-observe
  after human intervention
- no second orchestration chain may be introduced

- [ ] **Step 4: Re-run the recovery tests**

Run: `python -m pytest tests/runtime_bodies/test_body_recovery_resume.py tests/app/test_startup_recovery.py tests/app/test_system_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit the recovery slice**

```bash
git add src/copaw/kernel src/copaw/app src/copaw/environments tests/runtime_bodies/test_body_recovery_resume.py tests/app/test_startup_recovery.py tests/app/test_system_api.py
git commit -m "feat: unify agent body recovery into runtime chain"
```

### Task 8: Make the Operator Surfaces Show Body Ownership and Contention

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `src/copaw/app/runtime_center/task_review_projection.py`
- Modify: `console/src/pages/RuntimeCenter/index.tsx`
- Modify: `console/src/pages/AgentWorkbench/sections/runtimePanels.tsx`

- [ ] **Step 1: Write failing query/UI tests for body visibility**

```python
def test_runtime_center_exposes_body_owner_and_lease_state(...) -> None:
    ...
```

- [ ] **Step 2: Run the state query tests**

Run: `python -m pytest tests/app/test_operator_runtime_e2e.py -q`
Expected: FAIL until body ownership and corrected task review semantics are surfaced.

- [ ] **Step 3: Add body owner/lease/contention/recovery visibility**

Rules:
- overview should show which execution body is holding a live resource
- overview/detail should show browser mode, attach state, and explicit capability gaps instead of one opaque browser-ready label
- overview/detail should also surface site-contract state and handoff state for browser bodies
- browser surfaces should explicitly project at least `browser_mode / login_state / tab_scope / active_site / site_contract_status / handoff_state / resume_kind / last_verified_anchor / capability_summary / current_gap_or_blocker`
- all live surfaces should first project shared host fields:
  `surface_kind / host_mode / lease_class / access_mode / session_scope / account_scope_ref / continuity_source / handoff_state / resume_kind / verification_channel / capability_summary / current_gap_or_blocker`
- Windows desktop surfaces should also explicitly project at least `app_identity / window_scope / active_window_ref / active_process_ref / app_contract_status / control_channel / writer_lock_scope / window_anchor_summary`
- rejected decisions must remain visible as rejected, not generic runtime-error
- retired operator summary cards must not come back

- [ ] **Step 4: Re-run operator/runtime tests**

Run: `python -m pytest tests/app/test_operator_runtime_e2e.py tests/app/test_capability_market_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit the visibility slice**

```bash
git add src/copaw/app console/src/pages/RuntimeCenter console/src/pages/AgentWorkbench tests/app/test_operator_runtime_e2e.py tests/app/test_capability_market_api.py
git commit -m "feat: expose agent body ownership in operator surfaces"
```

### Task 9: Retire Legacy Tool-First Paths Only After the New Body Runtime Is Green

**Files:**
- Modify: legacy entry points discovered during implementation
- Modify: docs/status ledgers
- Test: full runtime body suite plus touched regressions

- [ ] **Step 1: Identify legacy browser/desktop/document entry paths still bypassing the body runtime**

Run: `rg -n "browser_use\\(|desktop_actuation|type_text|press_keys|focus_window|click\\(" src/copaw`
Expected: inventory of remaining direct tool-first paths.

- [ ] **Step 2: Add regression tests for any path still bypassing the verified loop**

Rules:
- every surviving direct execution path must prove it goes through observe/act/verify or be deleted

- [ ] **Step 3: Remove or redirect the bypasses**

Rules:
- prefer deletion over long-lived compatibility shims
- any compatibility bridge must declare a removal condition in comments/docs

- [ ] **Step 4: Run the full verification suite**

Run: `python -m pytest tests/runtime_bodies tests/agents/test_browser_tool_evidence.py tests/adapters/test_windows_host.py tests/app/test_startup_recovery.py tests/app/test_system_api.py tests/app/test_operator_runtime_e2e.py tests/app/test_capability_market_api.py -q`
Expected: PASS.

- [ ] **Step 5: Final cleanup commit**

```bash
git add src/copaw tests TASK_STATUS.md DATA_MODEL_DRAFT.md
git commit -m "feat: cut over to agent body grid computer runtime"
```
