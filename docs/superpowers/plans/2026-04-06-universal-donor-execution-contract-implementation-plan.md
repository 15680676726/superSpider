# Universal Donor Execution Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one universal donor execution base that injects formal provider truth, enforces bounded execution, and resolves host compatibility before CoPaw claims that an external donor is formally usable.

**Architecture:** Reuse the existing donor/package/candidate/trial/lifecycle/capability spine and extend the current `adapter/runtime` seams instead of writing donor-specific fixes. The new work is split into three platform contracts: provider injection, execution envelope, and host compatibility, plus the probe/promotion/evidence read model needed to keep those contracts operator-visible and off the chat hot path.

**Tech Stack:** Python, FastAPI, SQLite state store, existing `src/copaw/capabilities`, `src/copaw/state`, `src/copaw/providers`, `src/copaw/app/runtime_center`, pytest

---

## Hard Constraints

- External expansion is a cold path. It must not sit in chat turn hot paths or pre-send chat flows.
- Main brain and normal execution turns must continue to prefer already-installed formal capabilities.
- No donor-specific `if donor == X` branches may enter the core path.
- No donor may treat host config scraping as the primary formal execution path.
- No adapter or runtime donor action may default to unbounded wait.
- `installed`, `runtime_operable`, `adapter_probe_passed`, and `primary_action_verified` must remain distinct truth states.

## File Map

### Existing files to modify

- `src/copaw/capabilities/project_donor_contracts.py`
  - Extend installed-donor metadata with provider injection requirements, execution envelope defaults, and compatibility hints.
- `src/copaw/capabilities/external_adapter_contracts.py`
  - Add typed contract models/classification helpers for provider injection mode, execution envelope, compatibility result, and probe status.
- `src/copaw/capabilities/external_adapter_execution.py`
  - Wrap adapter action execution inside the common execution envelope and provider injection path.
- `src/copaw/capabilities/external_runtime_execution.py`
  - Reuse the same bounded envelope for runtime start/stop/probe actions so runtime and adapter donors share one discipline.
- `src/copaw/capabilities/service.py`
  - Surface new execution results and evidence attribution to callers without changing the formal capability vocabulary.
- `src/copaw/app/routers/capability_market.py`
  - Wire install/probe/promotion flow to the new contracts while keeping donor expansion on cold paths only.
- `src/copaw/state/models_capability_evolution.py`
  - Add formal fields for provider resolution result, compatibility result, probe result, and verified capability stage.
- `src/copaw/state/skill_candidate_service.py`
  - Persist candidate-stage provider/compatibility/probe truth.
- `src/copaw/state/skill_trial_service.py`
  - Persist trial-stage execution-envelope and probe evidence truth.
- `src/copaw/state/skill_lifecycle_decision_service.py`
  - Persist promotion boundary decisions based on verified states rather than installation alone.
- `src/copaw/state/donor_package_service.py`
  - Store package-side declarative provider/compatibility/envelope contract snapshots.
- `src/copaw/state/donor_trust_service.py`
  - Track timeout/auth/compatibility failures as donor trust signals.
- `src/copaw/app/runtime_center/state_query.py`
  - Expose provider resolution, compatibility, timeout, and probe truth in Runtime Center read models.
- `src/copaw/kernel/query_execution_runtime.py`
  - Preserve adapter action attribution and normalized failure taxonomy in evidence.
- `src/copaw/providers/runtime_provider_facade.py`
  - Reuse the existing provider truth seam instead of letting donors guess host state themselves.

### New files to create

- `src/copaw/capabilities/donor_provider_injection.py`
  - Resolve donor-facing provider contracts from CoPaw formal provider truth and build transport-safe injection payloads.
- `src/copaw/capabilities/donor_execution_envelope.py`
  - Own timeouts, heartbeat, cancellation, kill, retry, and normalized error taxonomy for donor actions.
- `src/copaw/capabilities/donor_host_compatibility.py`
  - Evaluate donor/host compatibility and produce `compatible_native / compatible_via_bridge / blocked_*` results.
- `src/copaw/capabilities/donor_probe_service.py`
  - Run minimal probes and record `runtime_operable / adapter_probe_passed / primary_action_verified`.

### Tests to create or extend

- `tests/capabilities/test_donor_provider_injection.py`
- `tests/capabilities/test_donor_execution_envelope.py`
- `tests/capabilities/test_donor_host_compatibility.py`
- `tests/capabilities/test_donor_probe_service.py`
- `tests/capabilities/test_external_adapter_execution.py`
- `tests/capabilities/test_external_runtime_execution.py`
- `tests/capabilities/test_project_donor_contracts.py`
- `tests/app/test_capability_market_api.py`
- `tests/app/test_runtime_center_donor_api.py`
- `tests/kernel/test_query_execution_runtime.py`
- `tests/state/test_skill_candidate_service.py`
- `tests/state/test_skill_trial_service.py`
- `tests/state/test_skill_lifecycle_decision_service.py`

---

### Task 1: Add formal donor execution contract fields

**Files:**
- Modify: `src/copaw/capabilities/external_adapter_contracts.py`
- Modify: `src/copaw/state/models_capability_evolution.py`
- Modify: `src/copaw/capabilities/project_donor_contracts.py`
- Test: `tests/capabilities/test_project_donor_contracts.py`
- Test: `tests/state/test_skill_candidate_service.py`

- [ ] **Step 1: Write the failing tests**

Add tests that require:
- donor package metadata to expose `provider_injection_mode`
- donor package metadata to expose `execution_envelope`
- donor package metadata to expose `host_compatibility_requirements`
- candidate/trial/lifecycle records to carry `verified_stage`, `provider_resolution_status`, and `compatibility_status`

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/capabilities/test_project_donor_contracts.py tests/state/test_skill_candidate_service.py -q`
Expected: FAIL because formal donor execution contract fields do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement:
- typed contract helpers in `external_adapter_contracts.py`
- new model fields in `models_capability_evolution.py`
- package-side contract projection in `project_donor_contracts.py`

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/capabilities/test_project_donor_contracts.py tests/state/test_skill_candidate_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/capabilities/external_adapter_contracts.py src/copaw/state/models_capability_evolution.py src/copaw/capabilities/project_donor_contracts.py tests/capabilities/test_project_donor_contracts.py tests/state/test_skill_candidate_service.py
git commit -m "feat: add formal donor execution contract fields"
```

### Task 2: Implement donor provider injection contract

**Files:**
- Create: `src/copaw/capabilities/donor_provider_injection.py`
- Modify: `src/copaw/providers/runtime_provider_facade.py`
- Modify: `src/copaw/capabilities/external_adapter_execution.py`
- Test: `tests/capabilities/test_donor_provider_injection.py`
- Test: `tests/capabilities/test_external_adapter_execution.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- provider truth resolves from CoPaw provider facade, not donor-local guessing
- injection payload can be emitted as env/args/config-wrapper modes
- secrets are masked from operator-visible payloads
- missing provider contract returns typed `provider_resolution_error`

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/capabilities/test_donor_provider_injection.py tests/capabilities/test_external_adapter_execution.py -q`
Expected: FAIL because no universal provider injection path exists yet.

- [ ] **Step 3: Write the minimal implementation**

Implement:
- `resolve_donor_provider_contract(...)`
- `build_donor_injection_payload(...)`
- runtime-provider facade adapter for donor use
- external adapter execution path that injects provider truth before invoking donor actions

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/capabilities/test_donor_provider_injection.py tests/capabilities/test_external_adapter_execution.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/capabilities/donor_provider_injection.py src/copaw/providers/runtime_provider_facade.py src/copaw/capabilities/external_adapter_execution.py tests/capabilities/test_donor_provider_injection.py tests/capabilities/test_external_adapter_execution.py
git commit -m "feat: add donor provider injection contract"
```

### Task 3: Implement universal donor execution envelope

**Files:**
- Create: `src/copaw/capabilities/donor_execution_envelope.py`
- Modify: `src/copaw/capabilities/external_adapter_execution.py`
- Modify: `src/copaw/capabilities/external_runtime_execution.py`
- Test: `tests/capabilities/test_donor_execution_envelope.py`
- Test: `tests/capabilities/test_external_adapter_execution.py`
- Test: `tests/capabilities/test_external_runtime_execution.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- adapter actions fail with typed `timeout_error` after bounded timeout
- long-running actions emit heartbeat snapshots
- cancellation and kill paths are explicit
- runtime start/probe/stop also use the shared envelope rather than one-off waits

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/capabilities/test_donor_execution_envelope.py tests/capabilities/test_external_adapter_execution.py tests/capabilities/test_external_runtime_execution.py -q`
Expected: FAIL because donor actions still bypass a shared execution envelope.

- [ ] **Step 3: Write the minimal implementation**

Implement:
- envelope helper for `startup_timeout / action_timeout / idle_timeout`
- heartbeat callbacks
- normalized cancellation/kill handling
- normalized error taxonomy mapping
- integration into adapter and runtime execution paths

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/capabilities/test_donor_execution_envelope.py tests/capabilities/test_external_adapter_execution.py tests/capabilities/test_external_runtime_execution.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/capabilities/donor_execution_envelope.py src/copaw/capabilities/external_adapter_execution.py src/copaw/capabilities/external_runtime_execution.py tests/capabilities/test_donor_execution_envelope.py tests/capabilities/test_external_adapter_execution.py tests/capabilities/test_external_runtime_execution.py
git commit -m "feat: add donor execution envelope"
```

### Task 4: Implement donor host compatibility contract

**Files:**
- Create: `src/copaw/capabilities/donor_host_compatibility.py`
- Modify: `src/copaw/capabilities/project_donor_contracts.py`
- Modify: `src/copaw/state/donor_package_service.py`
- Modify: `src/copaw/state/donor_trust_service.py`
- Test: `tests/capabilities/test_donor_host_compatibility.py`
- Test: `tests/capabilities/test_project_donor_contracts.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- donor compatibility can return `compatible_native`
- generic alias bridge can return `compatible_via_bridge`
- missing runtime/provider requirements return typed `blocked_*`
- donor trust updates record compatibility failures without project-specific flags

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/capabilities/test_donor_host_compatibility.py tests/capabilities/test_project_donor_contracts.py -q`
Expected: FAIL because no universal compatibility contract exists yet.

- [ ] **Step 3: Write the minimal implementation**

Implement:
- compatibility evaluator
- generic bridge discipline for env/config/provider aliases
- package-side compatibility snapshots
- trust-service updates for compatibility outcomes

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/capabilities/test_donor_host_compatibility.py tests/capabilities/test_project_donor_contracts.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/capabilities/donor_host_compatibility.py src/copaw/capabilities/project_donor_contracts.py src/copaw/state/donor_package_service.py src/copaw/state/donor_trust_service.py tests/capabilities/test_donor_host_compatibility.py tests/capabilities/test_project_donor_contracts.py
git commit -m "feat: add donor host compatibility contract"
```

### Task 5: Add minimal probe and verified-stage promotion boundary

**Files:**
- Create: `src/copaw/capabilities/donor_probe_service.py`
- Modify: `src/copaw/app/routers/capability_market.py`
- Modify: `src/copaw/state/skill_trial_service.py`
- Modify: `src/copaw/state/skill_lifecycle_decision_service.py`
- Test: `tests/capabilities/test_donor_probe_service.py`
- Test: `tests/app/test_capability_market_api.py`
- Test: `tests/state/test_skill_trial_service.py`
- Test: `tests/state/test_skill_lifecycle_decision_service.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- runtime donor can become `runtime_operable` after start/probe/stop proof
- adapter donor can become `adapter_probe_passed` only after a minimal business action succeeds
- dominant-action donors can be marked `primary_action_verified`
- install alone never promotes beyond `installed`

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/capabilities/test_donor_probe_service.py tests/app/test_capability_market_api.py tests/state/test_skill_trial_service.py tests/state/test_skill_lifecycle_decision_service.py -q`
Expected: FAIL because probe-driven verified stages do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Implement:
- minimal probe service
- probe-triggered verified-stage persistence
- promotion boundary changes in lifecycle decisions
- capability-market install/probe flow updates

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/capabilities/test_donor_probe_service.py tests/app/test_capability_market_api.py tests/state/test_skill_trial_service.py tests/state/test_skill_lifecycle_decision_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/capabilities/donor_probe_service.py src/copaw/app/routers/capability_market.py src/copaw/state/skill_trial_service.py src/copaw/state/skill_lifecycle_decision_service.py tests/capabilities/test_donor_probe_service.py tests/app/test_capability_market_api.py tests/state/test_skill_trial_service.py tests/state/test_skill_lifecycle_decision_service.py
git commit -m "feat: add donor probe and verified stage boundary"
```

### Task 6: Expose provider/compatibility/envelope/probe truth in Runtime Center and evidence

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/capabilities/service.py`
- Test: `tests/app/test_runtime_center_donor_api.py`
- Test: `tests/kernel/test_query_execution_runtime.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- Runtime Center donor read model shows provider resolution result
- Runtime Center donor read model shows compatibility result
- Runtime Center donor read model shows timeout/cancel/probe outcomes
- evidence attribution includes normalized error taxonomy and selected donor action

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/app/test_runtime_center_donor_api.py tests/kernel/test_query_execution_runtime.py -q`
Expected: FAIL because these read fields are not projected yet.

- [ ] **Step 3: Write the minimal implementation**

Implement:
- Runtime Center projection updates
- evidence/output attribution updates
- capability service result propagation updates

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/app/test_runtime_center_donor_api.py tests/kernel/test_query_execution_runtime.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/runtime_center/state_query.py src/copaw/kernel/query_execution_runtime.py src/copaw/capabilities/service.py tests/app/test_runtime_center_donor_api.py tests/kernel/test_query_execution_runtime.py
git commit -m "feat: expose donor execution contract truth"
```

### Task 7: Run adjacency regression and verify hot-path isolation

**Files:**
- Modify: `docs/superpowers/specs/2026-04-06-universal-donor-execution-contract-design.md`
- Modify: `TASK_STATUS.md`
- Test: no new file; verification commands only

- [ ] **Step 1: Run focused regression for the new contract**

Run:

```bash
PYTHONPATH=src python -m pytest tests/capabilities/test_donor_provider_injection.py tests/capabilities/test_donor_execution_envelope.py tests/capabilities/test_donor_host_compatibility.py tests/capabilities/test_donor_probe_service.py tests/capabilities/test_external_adapter_execution.py tests/capabilities/test_external_runtime_execution.py tests/capabilities/test_project_donor_contracts.py tests/app/test_capability_market_api.py tests/app/test_runtime_center_donor_api.py tests/kernel/test_query_execution_runtime.py tests/state/test_skill_candidate_service.py tests/state/test_skill_trial_service.py tests/state/test_skill_lifecycle_decision_service.py -q
```

Expected: PASS

- [ ] **Step 2: Run adjacency regression around hot paths**

Run:

```bash
PYTHONPATH=src python -m pytest tests/kernel/test_query_execution_runtime.py tests/app/test_capabilities_execution.py tests/app/test_runtime_center_events_api.py tests/app/test_runtime_center_donor_api.py -q
```

Expected: PASS and no new chat/runtime preflight dependency on donor discovery or donor install paths.

- [ ] **Step 3: Update docs to reflect only verified reality**

Update:
- `docs/superpowers/specs/2026-04-06-universal-donor-execution-contract-design.md`
- `TASK_STATUS.md`

Record:
- what is truly live-verified
- what still remains bounded by donor contract assumptions
- that donor expansion remains a cold path, not a chat hot path

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-04-06-universal-donor-execution-contract-design.md TASK_STATUS.md
git commit -m "docs: record verified donor execution contract state"
```

## Suggested Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6
7. Task 7

## Notes For Execution

- Do not start by live-fixing OpenSpace directly.
- First land the universal contracts, then re-run OpenSpace as one acceptance sample.
- Keep all donor discovery, install, probe, and compatibility work off the main brain chat hot path.
- If a donor needs a bridge, the bridge must be generic enough to plausibly help other donors.
- If a donor still requires project-specific logic after Tasks 1-6, stop and document the remaining incompatibility instead of hiding it in the core path.
