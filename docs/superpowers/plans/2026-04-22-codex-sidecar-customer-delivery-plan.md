# CoPaw Codex Sidecar Customer Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current Codex external-executor integration into a customer-deliverable built-in local sidecar so CoPaw can install, launch, govern, upgrade, and recover a managed `codex CLI` runtime on customer machines without relying on manual setup.

**Execution Status (`2026-04-22`):** Implemented on `main` via commits `b2767b2`, `8c96253`, `f9d2926`, `5155d33`, `f5c8c86`; fresh acceptance evidence and remaining boundaries are recorded in `TASK_STATUS.md` `1.0.10`. The checkbox steps below remain as the original execution checklist.

**Architecture:** All five concerns below remain `P0`; the order here is dependency order, not importance order. The implementation keeps CoPaw as the single truth source for provider selection, model policy, runtime state, risk/approval, and version compatibility, while `codex CLI` runs as a managed local sidecar controlled by CoPaw instead of a user-installed loose dependency.

**Tech Stack:** Python 3.12, FastAPI, SQLite state store, pytest, Runtime Center, Codex CLI sidecar, local process management, stdio transport

---

## Guardrails

- Stay on `main`; do not create a branch or worktree.
- Do not depend on customer PATH or manual `codex` installation.
- Do not depend on manual shell auth on customer machines; sidecar credentials must come from formal CoPaw-managed config or provider injection.
- Do not leave model selection to sidecar-local defaults.
- Do not ship customer delivery on top of local websocket transport; move local sidecar control to `stdio`.
- Do not treat version drift as best-effort; compatibility gating must fail closed.
- Completion claims must follow `UNIFIED_ACCEPTANCE_STANDARD.md` with explicit `L1 / L2 / L3 / L4`.

## Dependency Order

All five are `P0`. Implementation order is:

1. Managed sidecar install truth
2. Local sidecar transport and launch cutover (`stdio`)
3. Unified model and sidecar credential governance enforced end-to-end
4. Approval / control / recovery closure
5. Version compatibility and upgrade governance
6. Full verification, docs sync, and customer-delivery closeout

## File Map

- `src/copaw/state/models_executor_runtime.py`
  - Extend formal executor state with sidecar install / compatibility / release truth.
- `src/copaw/state/executor_runtime_service.py`
  - Canonical service for sidecar install state, model policy, compatibility policy, and runtime lookup.
- `src/copaw/state/repositories/base.py`
  - Repository contracts for new sidecar state objects.
- `src/copaw/state/repositories/sqlite_executor_runtime.py`
  - SQLite persistence for sidecar install / release / compatibility records.
- `src/copaw/state/__init__.py`
  - Re-export new formal sidecar records/services so the public state surface stays in sync.
- `src/copaw/state/repositories/__init__.py`
  - Re-export new repository contracts/implementations for sidecar state.
- `src/copaw/state/store.py`
  - Schema migration surface for new sidecar tables.
- `src/copaw/adapters/executors/codex_stdio_transport.py`
  - New default local transport using managed child process + `stdio`.
- `src/copaw/adapters/executors/codex_app_server_transport.py`
  - Demote to compatibility / remote websocket-only fallback.
- `src/copaw/adapters/executors/codex_app_server_adapter.py`
  - Keep executor port semantics while supporting `stdio` transport and approval callbacks.
- `src/copaw/adapters/executors/codex_protocol.py`
  - Protocol payload builder and event normalization; extend for explicit model and approval payloads if supported.
- `src/copaw/kernel/runtime_coordination.py`
  - Enforce system model policy, compatibility checks, and sidecar selection before runtime start.
- `src/copaw/kernel/executor_runtime_port.py`
  - Expand runtime-port contract only if approval / resume control requires it.
- `src/copaw/kernel/executor_event_writeback_service.py`
  - Persist sidecar approval / failure / restart evidence when needed.
- `src/copaw/app/runtime_service_graph.py`
  - Build managed sidecar runtime port from installed sidecar truth, not PATH probing.
- `src/copaw/app/runtime_bootstrap_models.py`
  - Keep managed sidecar state/services in the formal bootstrap payload.
- `src/copaw/app/runtime_state_bindings.py`
  - Expose managed sidecar runtime services through `app.state` bindings without ad hoc lookups.
- `src/copaw/app/startup_environment_preflight.py`
  - Fail fast on missing / incompatible sidecar install.
- `src/copaw/app/_app.py`
  - Ensure managed stdio sidecar lifecycle closes cleanly on app shutdown and restart paths.
- `src/copaw/app/daemon_commands.py`
  - Add sidecar status / install / upgrade / rollback operator commands.
- `src/copaw/app/routers/capability_market.py`
  - Keep provider install flow but bind provider to system-managed model/sidecar policies.
- `src/copaw/capabilities/donor_provider_injection.py`
  - Reuse the formal provider injection contract for sidecar auth env/arg/config shaping instead of manual shell state.
- `TASK_STATUS.md`
  - Record exact acceptance evidence and remaining follow-up boundaries.
- `DATA_MODEL_DRAFT.md`
  - Document new sidecar state objects if they become formal core objects.
- `docs/superpowers/specs/2026-04-20-copaw-codex-app-server-hard-cut-design.md`
  - Update formal sidecar boundary and local transport boundary.

### Test Map

- `tests/state/test_executor_runtime_service.py`
- `tests/state/test_executor_sidecar_state.py`
- `tests/adapters/test_codex_app_server_adapter.py`
- `tests/adapters/test_codex_stdio_transport.py`
- `tests/kernel/test_main_brain_executor_runtime_integration.py`
- `tests/kernel/test_executor_event_writeback_service.py`
- `tests/capabilities/test_donor_provider_injection.py`
- `tests/app/test_runtime_execution_provider_wiring.py`
- `tests/app/test_runtime_bootstrap_helpers.py`
- `tests/app/test_runtime_bootstrap_split.py`
- `tests/app/test_startup_environment_preflight.py`
- `tests/app/test_capability_market_api.py`
- `tests/app/test_external_executor_live_smoke.py`
- `tests/app/test_daemon_commands.py`

---

### Task 1: Formalize Managed Sidecar Install Truth

**Files:**
- Modify: `src/copaw/state/models_executor_runtime.py`
- Modify: `src/copaw/state/executor_runtime_service.py`
- Modify: `src/copaw/state/repositories/base.py`
- Modify: `src/copaw/state/repositories/sqlite_executor_runtime.py`
- Modify: `src/copaw/state/__init__.py`
- Modify: `src/copaw/state/repositories/__init__.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_state_bindings.py`
- Test: `tests/state/test_executor_runtime_service.py`
- Create: `tests/state/test_executor_sidecar_state.py`
- Modify: `tests/app/test_runtime_bootstrap_helpers.py`
- Modify: `tests/app/test_runtime_bootstrap_split.py`

- [ ] **Step 1: Write failing tests for managed sidecar install truth**

Target assertions:
- CoPaw can persist one active local sidecar install record.
- Runtime bootstrap does not need PATH lookup when a managed install exists.
- Compatibility policy can gate install status.
- Bootstrap/state bindings expose managed sidecar truth through formal runtime surfaces.

- [ ] **Step 2: Run the new state tests and verify they fail**

Run: `python -m pytest tests/state/test_executor_sidecar_state.py tests/state/test_executor_runtime_service.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py -q -k "sidecar or compatibility_policy or executor_runtime"`
Expected: FAIL on missing sidecar records / service methods / bootstrap bindings.

- [ ] **Step 3: Add formal sidecar state objects**

Add records for:
- managed install
- compatibility policy
- release manifest / current channel

- [ ] **Step 4: Extend executor runtime service and repositories**

Required capabilities:
- upsert / get active sidecar install
- resolve compatibility policy
- mark install healthy / degraded / incompatible
- re-export formal sidecar state through `src/copaw/state/__init__.py` and `src/copaw/state/repositories/__init__.py`
- keep bootstrap models/state bindings aligned with the new sidecar truth surface

- [ ] **Step 5: Re-run state tests and make them pass**

Run: `python -m pytest tests/state/test_executor_sidecar_state.py tests/state/test_executor_runtime_service.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py -q`
Expected: PASS

- [ ] **Step 6: Commit the sidecar truth slice**

Commit: `git commit -m "feat: add managed codex sidecar runtime state"`

### Task 2: Cut Local Sidecar Transport To Managed `stdio`

**Files:**
- Create: `src/copaw/adapters/executors/codex_stdio_transport.py`
- Modify: `src/copaw/adapters/executors/codex_app_server_adapter.py`
- Modify: `src/copaw/adapters/executors/codex_protocol.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_state_bindings.py`
- Modify: `src/copaw/app/startup_environment_preflight.py`
- Modify: `src/copaw/app/_app.py`
- Test: `tests/adapters/test_codex_stdio_transport.py`
- Modify: `tests/adapters/test_codex_app_server_adapter.py`
- Modify: `tests/app/test_runtime_execution_provider_wiring.py`
- Modify: `tests/app/test_runtime_bootstrap_helpers.py`
- Modify: `tests/app/test_runtime_bootstrap_split.py`
- Modify: `tests/app/test_startup_environment_preflight.py`

- [ ] **Step 1: Write failing tests for local `stdio` sidecar launch**

Target assertions:
- default local provider uses managed install path, not PATH probing
- local transport uses child process `stdin/stdout`
- websocket transport is no longer the default local sidecar path
- app shutdown closes the managed stdio child deterministically

- [ ] **Step 2: Run transport/preflight tests and verify they fail**

Run: `python -m pytest tests/adapters/test_codex_stdio_transport.py tests/app/test_runtime_execution_provider_wiring.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_startup_environment_preflight.py -q`
Expected: FAIL on missing stdio transport / old local websocket assumptions.

- [ ] **Step 3: Implement managed stdio transport**

Required behavior:
- launch bundled `codex CLI` via absolute path
- perform initialize handshake over stdio
- route responses, notifications, and shutdown cleanly
- keep lifecycle shutdown compatible with app-level `close()` behavior

- [ ] **Step 4: Cut runtime bootstrap to stdio-first**

Required behavior:
- local customer delivery path = managed install + stdio
- websocket path stays only as explicit compatibility / remote override
- bootstrap/state bindings continue exposing the active executor runtime port without PATH-based fallback

- [ ] **Step 5: Re-run the transport/preflight tests and make them pass**

Run: `python -m pytest tests/adapters/test_codex_stdio_transport.py tests/adapters/test_codex_app_server_adapter.py tests/app/test_runtime_execution_provider_wiring.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_startup_environment_preflight.py -q`
Expected: PASS

- [ ] **Step 6: Commit the stdio launch slice**

Commit: `git commit -m "refactor: switch local codex sidecar to stdio transport"`

### Task 3: Enforce System-Managed Model and Sidecar Credential Governance

**Files:**
- Modify: `src/copaw/state/models_executor_runtime.py`
- Modify: `src/copaw/state/executor_runtime_service.py`
- Modify: `src/copaw/app/routers/capability_market.py`
- Modify: `src/copaw/capabilities/donor_provider_injection.py`
- Modify: `src/copaw/kernel/runtime_coordination.py`
- Modify: `src/copaw/adapters/executors/codex_protocol.py`
- Modify: `tests/capabilities/test_donor_provider_injection.py`
- Modify: `tests/app/test_capability_market_api.py`
- Modify: `tests/kernel/test_main_brain_executor_runtime_integration.py`
- Modify: `tests/state/test_executor_runtime_service.py`

- [ ] **Step 1: Write failing tests proving model policy does not yet hard-control the sidecar**

Target assertions:
- provider install persists `model_policy_id`
- assignment start resolves a single system-owned model ref
- protocol / launch payload cannot silently fall back to sidecar defaults
- sidecar credential sourcing comes from formal provider/system-managed config, not operator shell state

- [ ] **Step 2: Run the model-governance tests and verify they fail**

Run: `python -m pytest tests/capabilities/test_donor_provider_injection.py tests/app/test_capability_market_api.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/state/test_executor_runtime_service.py -q -k "model_policy or default_model_ref or provider_auth"`
Expected: FAIL on missing hard enforcement and missing managed sidecar credential path.

- [ ] **Step 3: Expand formal model policy contract**

Minimum policy fields:
- default model ref
- role override support
- mismatch handling
- ownership mode = `copaw_managed` or `hybrid` where needed
- sidecar auth source and injection mode for bundled customer delivery

- [ ] **Step 4: Enforce the resolved model at runtime start**

Required behavior:
- runtime coordination must resolve one canonical model
- transport / protocol layer must inject or pin that model
- runtime metadata must record the effective model for post-run verification
- sidecar launch/config path must resolve credentials from formal CoPaw-managed config or provider injection

- [ ] **Step 5: Add mismatch detection**

Required behavior:
- if sidecar reports a different model, CoPaw records evidence and fails closed or degrades according to policy
- if sidecar launch lacks required credentials, CoPaw records formal failure instead of depending on ambient shell env

- [ ] **Step 6: Re-run model-governance tests and make them pass**

Run: `python -m pytest tests/capabilities/test_donor_provider_injection.py tests/app/test_capability_market_api.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/state/test_executor_runtime_service.py -q`
Expected: PASS

- [ ] **Step 7: Commit the model-governance slice**

Commit: `git commit -m "feat: enforce codex sidecar model governance"`

### Task 4: Close Approval, Control, and Recovery Loop

**Files:**
- Modify: `src/copaw/kernel/executor_runtime_port.py`
- Modify: `src/copaw/adapters/executors/codex_stdio_transport.py`
- Modify: `src/copaw/adapters/executors/codex_app_server_adapter.py`
- Modify: `src/copaw/kernel/runtime_coordination.py`
- Modify: `src/copaw/kernel/executor_event_writeback_service.py`
- Modify: `src/copaw/app/_app.py`
- Modify: `src/copaw/app/daemon_commands.py`
- Test: `tests/adapters/test_codex_stdio_transport.py`
- Modify: `tests/kernel/test_main_brain_executor_runtime_integration.py`
- Modify: `tests/kernel/test_executor_event_writeback_service.py`
- Create: `tests/app/test_daemon_commands.py`

- [ ] **Step 1: Write failing tests for approval and recovery behavior**

Target assertions:
- sidecar approval requests are surfaced into CoPaw
- CoPaw can approve / reject / interrupt
- crash / restart transitions are persisted and visible

- [ ] **Step 2: Run the approval/recovery tests and verify they fail**

Run: `python -m pytest tests/adapters/test_codex_stdio_transport.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/kernel/test_executor_event_writeback_service.py tests/app/test_daemon_commands.py -q -k "approval or recovery or restart"`
Expected: FAIL on missing request/response loop.

- [ ] **Step 3: Add server-request handling to the transport**

Required behavior:
- accept sidecar-initiated approval requests
- route them into CoPaw risk/decision flow
- send structured response back to sidecar

- [ ] **Step 4: Wire approval into existing CoPaw risk model**

Required behavior:
- `auto / guarded / confirm` stays the only approval model
- approvals become formal runtime truth and evidence, not console-only logs

- [ ] **Step 5: Add recovery and operator controls**

Minimum operator controls:
- sidecar status
- restart
- interrupt active turn

- [ ] **Step 6: Re-run approval/recovery tests and make them pass**

Run: `python -m pytest tests/adapters/test_codex_stdio_transport.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/kernel/test_executor_event_writeback_service.py tests/app/test_daemon_commands.py -q`
Expected: PASS

- [ ] **Step 7: Commit the approval/recovery slice**

Commit: `git commit -m "feat: add codex sidecar approval and recovery control"`

### Task 5: Add Version Compatibility and Upgrade Governance

**Files:**
- Modify: `src/copaw/state/models_executor_runtime.py`
- Modify: `src/copaw/state/executor_runtime_service.py`
- Create: `src/copaw/app/sidecar_release_service.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/startup_environment_preflight.py`
- Modify: `src/copaw/app/daemon_commands.py`
- Create: `tests/app/test_sidecar_release_service.py`
- Modify: `tests/app/test_startup_environment_preflight.py`
- Modify: `tests/app/test_daemon_commands.py`

- [ ] **Step 1: Write failing tests for compatibility gating and upgrade flow**

Target assertions:
- CoPaw rejects unsupported sidecar versions
- sidecar release manifest can stage upgrade / rollback
- startup preflight blocks incompatible customer installs

- [ ] **Step 2: Run version-governance tests and verify they fail**

Run: `python -m pytest tests/app/test_sidecar_release_service.py tests/app/test_startup_environment_preflight.py tests/app/test_daemon_commands.py -q -k "sidecar and (version or upgrade or rollback or compatibility)"`
Expected: FAIL on missing compatibility policy and release service.

- [ ] **Step 3: Add formal compatibility policy**

Minimum policy:
- supported codex version range
- supported protocol feature set
- required CoPaw version range
- fail-closed mode when incompatible

- [ ] **Step 4: Implement staged upgrade / rollback service**

Required behavior:
- download or stage release artifact
- verify checksum
- switch current version atomically
- rollback on health-check failure

- [ ] **Step 5: Add operator-visible sidecar version commands**

Minimum commands:
- status
- current version
- available upgrade
- upgrade
- rollback

- [ ] **Step 6: Re-run version-governance tests and make them pass**

Run: `python -m pytest tests/app/test_sidecar_release_service.py tests/app/test_startup_environment_preflight.py tests/app/test_daemon_commands.py -q`
Expected: PASS

- [ ] **Step 7: Commit the version-governance slice**

Commit: `git commit -m "feat: add codex sidecar upgrade governance"`

### Task 6: Run Fresh Verification and Sync Docs

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `docs/superpowers/specs/2026-04-20-copaw-codex-app-server-hard-cut-design.md`
- Modify: touched code/test files only if final fixes are required

- [ ] **Step 1: Run fresh focused regression for sidecar state, transport, model governance, approval flow, and upgrade governance**

Run:

```bash
python -m pytest tests/state/test_executor_runtime_service.py tests/state/test_executor_sidecar_state.py tests/adapters/test_codex_app_server_adapter.py tests/adapters/test_codex_stdio_transport.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/kernel/test_executor_event_writeback_service.py tests/capabilities/test_donor_provider_injection.py tests/app/test_runtime_execution_provider_wiring.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_startup_environment_preflight.py tests/app/test_capability_market_api.py tests/app/test_daemon_commands.py tests/app/test_sidecar_release_service.py -q
```

Expected: PASS

- [ ] **Step 2: Run widened default regression**

Run: `python scripts/run_p0_runtime_terminal_gate.py`
Expected: PASS

- [ ] **Step 3: Run fresh live smoke on managed local sidecar**

Run:

```bash
COPAW_RUN_EXTERNAL_EXECUTOR_LIVE_SMOKE=1 python -m pytest tests/app/test_external_executor_live_smoke.py -q -k live_external_executor_provider_intake_and_runtime_writeback
```

Expected: PASS on bundled sidecar install path, not PATH-only fallback.

- [ ] **Step 4: Run selected repeated live cycles**

Run the same live smoke command at least `3` times.
Expected: stable PASS across repeated cycles.

- [ ] **Step 5: Update docs with exact commands, outputs, acceptance levels, and remaining boundaries**

Required doc outcomes:
- `TASK_STATUS.md` records `L1 / L2 / L3 / L4` separately
- design doc records `managed local codex CLI sidecar + stdio` as the customer-delivery boundary
- `DATA_MODEL_DRAFT.md` records new sidecar truth objects if added
- bootstrap/lifecycle/auth/exports are explicitly recorded as part of the managed sidecar boundary

- [ ] **Step 6: Commit docs and verification updates**

Commit: `git commit -m "docs: record codex sidecar customer delivery acceptance"`

### Task 7: Mainline Delivery Closeout

**Files:**
- Modify: touched files only if last-mile fixes are required

- [ ] **Step 1: Ensure the worktree is clean except for intentional changes**

- [ ] **Step 2: Re-run final verification after any last fix**

- [ ] **Step 3: Commit all remaining changes on `main`**

- [ ] **Step 4: Push `main` to `origin/main`**

- [ ] **Step 5: Confirm `git status -sb` is clean and `origin/main...main` is `0 0`**

---

## Delivery Rule

This plan only counts as finished when all five `P0` concerns are covered by formal code, fresh verification, and mainline delivery:

1. Managed sidecar installation
2. Local `stdio` transport
3. System-owned model and sidecar credential governance
4. Approval/control/recovery closure
5. Version compatibility and upgrade governance

If any one of these remains partial, the result is still an internal demo baseline, not a customer-deliverable Codex sidecar release.
