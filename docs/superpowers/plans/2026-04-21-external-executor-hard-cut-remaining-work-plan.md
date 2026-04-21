# External Executor Hard-Cut Remaining Work Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining seven hard-cut gaps so `ExecutorRuntime` becomes the only formal execution mainline and all leftover local actor, delegation, donor/project, and local-tool surfaces are either explicit compatibility paths or retired.

**Architecture:** First fix the formal contract mismatch around model governance so subsequent cutovers do not build on a broken binding. Then move `ExecutorRuntime` truth off the legacy external-runtime bridge, demote actor/delegation/bootstrap remnants out of the formal startup and assignment path, retire donor/project execution shells, and finally prove the new provider intake with fresh live verification and doc sync.

**Tech Stack:** Python 3.12, FastAPI, SQLite state store, pytest, Vitest, Runtime Center frontend, Codex App Server adapter

---

## Guardrails

- Stay on `main`; do not create a worktree or feature branch unless the human explicitly approves it.
- Do not inspect generated output directories or bundled assets.
- Preserve UTF-8 file encoding.
- Do not create a second executor truth source.
- Any remaining compatibility code must state its deletion condition in docs.
- No completion claim without fresh verification evidence.

## File Map

- `src/copaw/state/models_executor_runtime.py`
  - Formal executor data model: provider, binding, policy, runtime, thread, turn, event.
- `src/copaw/state/executor_runtime_service.py`
  - Canonical service for executor runtime/provider/policy/thread/turn/event truth.
- `src/copaw/state/external_runtime_service.py`
  - Legacy external-runtime bridge that must stop acting as canonical executor truth.
- `src/copaw/state/repositories/base.py`
  - Abstract executor repository contract.
- `src/copaw/state/repositories/sqlite_executor_runtime.py`
  - SQLite executor-runtime persistence implementation.
- `src/copaw/state/store.py`
  - SQLite schema/migration surface for executor tables.
- `src/copaw/kernel/runtime_coordination.py`
  - Role/provider/model selection and assignment-to-runtime coordination.
- `src/copaw/kernel/main_brain_orchestrator.py`
  - Formal assignment front-door that must short-circuit to executor runtime.
- `src/copaw/kernel/delegation_service.py`
  - Local child-task compatibility backend; no longer allowed to look canonical.
- `src/copaw/kernel/query_execution_runtime.py`
  - Query-time tool front-door that still exposes local execution tooling.
- `src/copaw/capabilities/sources/system.py`
  - System capability registry and compatibility aliases.
- `src/copaw/app/runtime_bootstrap_execution.py`
  - Execution bootstrap seam; currently still wires actor runtime services.
- `src/copaw/app/runtime_bootstrap_domains.py`
  - Domain bootstrap graph; currently still constructs delegation/actor services.
- `src/copaw/app/runtime_bootstrap_models.py`
  - Runtime bootstrap state model that still advertises actor/delegation services.
- `src/copaw/app/runtime_service_graph.py`
  - App assembly path that still injects actor runtime classes.
- `src/copaw/app/routers/capability_market.py`
  - Formal executor provider intake plus legacy donor/project compatibility routes.
- `src/copaw/app/runtime_center/state_query.py`
  - Runtime Center read model for executor providers and donor compatibility projections.
- `src/copaw/capabilities/project_donor_contracts.py`
  - Donor/project compatibility metadata.
- `TASK_STATUS.md`
  - Canonical status and acceptance evidence log.
- `DEPRECATION_LEDGER.md`
  - Canonical deletion/compatibility ledger.

## Task Order

1. Fix the model-governance contract mismatch first.
2. Move executor truth off the legacy external-runtime bridge.
3. Remove actor runtime from the formal startup graph.
4. Continue retiring `delegation_service.py` to a non-formal compatibility edge.
5. Retire donor/project execution shells from active execution vocabulary.
6. Cut the formal execution front-door away from local browser/file/shell tooling.
7. Run fresh verification, sync docs, commit on `main`, push `origin/main`, and confirm a clean worktree.

### Task 1: Fix Model Governance And `ExecutionPolicy` Contract Wiring

**Files:**
- Modify: `src/copaw/kernel/runtime_coordination.py`
- Modify: `src/copaw/app/routers/capability_market.py`
- Modify: `src/copaw/state/models_executor_runtime.py`
- Test: `tests/kernel/test_main_brain_executor_runtime_integration.py`
- Test: `tests/app/test_capability_market_api.py`
- Test: `tests/state/test_executor_runtime_service.py`

- [ ] **Step 1: Write a failing integration test that proves `model_policy_id` is ignored when `execution_policy_id` differs**

```python
binding = RoleExecutorBindingRecord(
    role_id="backend-engineer",
    executor_provider_id="codex-app-server",
    selection_mode="role-routed",
    execution_policy_id="open-default",
    model_policy_id="codex-default",
)
policy = ModelInvocationPolicyRecord(
    policy_id="codex-default",
    ownership_mode="runtime_owned",
    default_model_ref="gpt-5-codex",
)
assert runtime_context["executor_runtime"]["model_policy_id"] == "codex-default"
assert runtime_context["executor_runtime"]["model_ref"] == "gpt-5-codex"
```

- [ ] **Step 2: Write a failing API test that proves provider install stores model policy and execution policy separately**

Run target: `python -m pytest tests/app/test_capability_market_api.py -q -k "executor_provider_install"`
Expected: FAIL because `runtime_coordination.py` still reads `binding.execution_policy_id` as the model-policy lookup key.

- [ ] **Step 3: Update `runtime_coordination.py` so model selection resolves from `binding.model_policy_id` first**

- [ ] **Step 4: Keep `execution_policy_id` for execution-policy semantics only**

Implementation notes:
- If `execution_policy_id` is present, resolve it through `resolve_execution_policy(...)`, not `resolve_model_invocation_policy(...)`.
- If `model_policy_id` is absent, fall back to the coordinator default model policy id.
- Preserve `single-runtime` and `role-routed` selection behavior.

- [ ] **Step 5: Re-run the focused contract tests**

Run: `python -m pytest tests/kernel/test_main_brain_executor_runtime_integration.py tests/app/test_capability_market_api.py tests/state/test_executor_runtime_service.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

Run:

```bash
git add src/copaw/kernel/runtime_coordination.py src/copaw/app/routers/capability_market.py src/copaw/state/models_executor_runtime.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/app/test_capability_market_api.py tests/state/test_executor_runtime_service.py
git commit -m "fix: wire executor model policy selection correctly"
```

### Task 2: Move `ExecutorRuntime` Truth Off The Legacy External-Runtime Bridge

**Files:**
- Modify: `src/copaw/state/executor_runtime_service.py`
- Modify: `src/copaw/state/external_runtime_service.py`
- Modify: `src/copaw/state/repositories/base.py`
- Modify: `src/copaw/state/repositories/sqlite_executor_runtime.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/__init__.py`
- Test: `tests/state/test_executor_runtime_service.py`
- Test: `tests/state/test_external_runtime_service.py`
- Test: `tests/app/test_runtime_center_executor_runtime_projection.py`

- [ ] **Step 1: Write a failing test that proves canonical executor runtime create/query still requires `ExternalCapabilityRuntimeService`**

```python
service = ExecutorRuntimeService(repository=repository, external_runtime_service=None)
runtime = service.create_or_reuse_assignment_runtime(...)
assert runtime.runtime_id
assert service.list_executor_runtimes(assignment_id="assignment-1")
```

- [ ] **Step 2: Run the focused state tests and confirm failure lands on the canonical-truth dependency**

Run: `python -m pytest tests/state/test_executor_runtime_service.py tests/state/test_external_runtime_service.py tests/app/test_runtime_center_executor_runtime_projection.py -q`
Expected: FAIL because canonical executor-runtime operations still depend on the legacy external-runtime service.

- [ ] **Step 3: Add canonical runtime-instance persistence to the executor repository path**

Implementation notes:
- `ExecutorRuntimeService` should persist and query `ExecutorRuntimeInstanceRecord` directly through the executor repository.
- `ExternalCapabilityRuntimeService` may remain as a read-only compatibility bridge, but not as the canonical write owner.

- [ ] **Step 4: Keep any legacy bridge explicitly one-way and compatibility-scoped**

Implementation notes:
- Legacy fallback is allowed only for compatibility read/projection.
- New runtime/thread/turn/event writes must stay in executor-runtime tables only.

- [ ] **Step 5: Re-run the focused state/projection tests**

Run: `python -m pytest tests/state/test_executor_runtime_service.py tests/state/test_external_runtime_service.py tests/app/test_runtime_center_executor_runtime_projection.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/state/executor_runtime_service.py src/copaw/state/external_runtime_service.py src/copaw/state/repositories/base.py src/copaw/state/repositories/sqlite_executor_runtime.py src/copaw/state/store.py src/copaw/state/models.py src/copaw/state/__init__.py tests/state/test_executor_runtime_service.py tests/state/test_external_runtime_service.py tests/app/test_runtime_center_executor_runtime_projection.py
git commit -m "refactor: make executor runtime state canonical"
```

### Task 3: Remove Actor Runtime From The Formal Startup Graph

**Files:**
- Modify: `src/copaw/app/runtime_bootstrap_execution.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Test: `tests/app/test_runtime_bootstrap_helpers.py`
- Test: `tests/app/test_runtime_bootstrap_split.py`
- Test: `tests/app/test_runtime_execution_provider_wiring.py`
- Test: `tests/app/test_runtime_center_actor_api.py`

- [ ] **Step 1: Write a failing bootstrap test that proves actor runtime services are still part of the default formal startup graph**

```python
bootstrap = build_kernel_runtime(...)
assert bootstrap.actor_mailbox_service is None
assert bootstrap.actor_worker is None
assert bootstrap.actor_supervisor is None
```

- [ ] **Step 2: Run the focused bootstrap tests and confirm the failure is on actor runtime still being eagerly wired**

Run: `python -m pytest tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_execution_provider_wiring.py tests/app/test_runtime_center_actor_api.py -q`
Expected: FAIL because the bootstrap graph still constructs actor runtime services by default.

- [ ] **Step 3: Move actor services behind explicit compatibility-only wiring**

Implementation notes:
- The formal execution path should bootstrap executor-runtime services first.
- Actor services may remain optional only for compatibility routes/tests.

- [ ] **Step 4: Keep Runtime Center actor APIs read-only compatibility**

Implementation notes:
- Do not reintroduce actor mutation routes.
- Do not let actor bootstrap state look canonical in app state or shared payloads.

- [ ] **Step 5: Re-run the focused bootstrap/actor tests**

Run: `python -m pytest tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_execution_provider_wiring.py tests/app/test_runtime_center_actor_api.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/app/runtime_bootstrap_execution.py src/copaw/app/runtime_bootstrap_domains.py src/copaw/app/runtime_bootstrap_models.py src/copaw/app/runtime_service_graph.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_execution_provider_wiring.py tests/app/test_runtime_center_actor_api.py
git commit -m "refactor: demote actor runtime from bootstrap mainline"
```

### Task 4: Continue Retiring `delegation_service.py` To Compatibility-Only

**Files:**
- Modify: `src/copaw/kernel/delegation_service.py`
- Modify: `src/copaw/kernel/main_brain_orchestrator.py`
- Modify: `src/copaw/capabilities/sources/system.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Test: `tests/kernel/test_assignment_envelope.py`
- Test: `tests/kernel/test_task_execution_projection.py`
- Test: `tests/app/test_runtime_center_task_delegation_api.py`

- [ ] **Step 1: Write a failing test that proves a default formal assignment can still fall into delegation compatibility surfaces**

```python
assert runtime_projection["execution_source"] != "delegation-compat"
assert runtime_projection["formal_surface"] is True
```

- [ ] **Step 2: Run the focused delegation tests and confirm the failure is on canonical/compatibility leakage**

Run: `python -m pytest tests/kernel/test_assignment_envelope.py tests/kernel/test_task_execution_projection.py tests/app/test_runtime_center_task_delegation_api.py -q`
Expected: FAIL on delegation metadata or exposed routes still looking canonical.

- [ ] **Step 3: Restrict `TaskDelegationService` to explicit child-task compatibility use only**

Implementation notes:
- Preserve `execution_source = delegation-compat`.
- Remove it from any remaining default bootstrap or capability exposure that still suggests a formal backend.

- [ ] **Step 4: Keep assignment continuity fields without letting compatibility runs masquerade as formal assignment ownership**

Implementation notes:
- `assignment_id` may continue flowing for continuity/audit.
- Compatibility runs must never mark themselves as the formal assignment backend.

- [ ] **Step 5: Re-run the focused delegation tests**

Run: `python -m pytest tests/kernel/test_assignment_envelope.py tests/kernel/test_task_execution_projection.py tests/app/test_runtime_center_task_delegation_api.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/kernel/delegation_service.py src/copaw/kernel/main_brain_orchestrator.py src/copaw/capabilities/sources/system.py src/copaw/app/runtime_bootstrap_models.py tests/kernel/test_assignment_envelope.py tests/kernel/test_task_execution_projection.py tests/app/test_runtime_center_task_delegation_api.py
git commit -m "refactor: isolate delegation service as compatibility path"
```

### Task 5: Retire Donor/Project Execution Shells From Active Execution Vocabulary

**Files:**
- Modify: `src/copaw/app/routers/capability_market.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/capabilities/project_donor_contracts.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Test: `tests/capabilities/test_project_donor_contracts.py`
- Test: `tests/app/test_capability_market_api.py`
- Test: `tests/app/test_runtime_center_external_runtime_api.py`

- [ ] **Step 1: Write a failing test that proves donor/project compatibility surfaces still appear alongside formal executor intake without explicit segregation**

```python
assert payload["formal_surface"] is False
assert payload["compatibility_mode"] == "compatibility/acquisition-only"
assert "executor_provider_search" in payload["routes"]
```

- [ ] **Step 2: Run the donor/provider tests and confirm the failure is on mixed formal/acquisition vocabulary**

Run: `python -m pytest tests/capabilities/test_project_donor_contracts.py tests/app/test_capability_market_api.py tests/app/test_runtime_center_external_runtime_api.py -q`
Expected: FAIL because an active read/write path still exposes donor/project shells too close to canonical executor-provider surfaces.

- [ ] **Step 3: Separate formal executor-provider intake from donor/project acquisition surfaces**

Implementation notes:
- Formal execution vocabulary must stay `ExecutorProvider / control_surface_kind / default_protocol_kind`.
- Donor/project routes must remain explicitly acquisition-only and never the default execution product shell.

- [ ] **Step 4: Remove donor/project execution wording from Runtime Center active runtime projections**

Implementation notes:
- Runtime Center should show donor/project records only as compatibility/acquisition inventory, not as active executor-runtime truth.

- [ ] **Step 5: Re-run the focused donor/provider tests**

Run: `python -m pytest tests/capabilities/test_project_donor_contracts.py tests/app/test_capability_market_api.py tests/app/test_runtime_center_external_runtime_api.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/app/routers/capability_market.py src/copaw/app/runtime_center/state_query.py src/copaw/capabilities/project_donor_contracts.py src/copaw/app/runtime_bootstrap_models.py tests/capabilities/test_project_donor_contracts.py tests/app/test_capability_market_api.py tests/app/test_runtime_center_external_runtime_api.py
git commit -m "refactor: quarantine donor project surfaces from executor runtime"
```

### Task 6: Cut The Formal Execution Front-Door Away From Local Browser/File/Shell Tooling

**Files:**
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/capabilities/sources/system.py`
- Test: `tests/kernel/query_execution_environment_parts/dispatch.py`
- Test: `tests/app/test_capabilities_execution.py`
- Test: `tests/app/test_mcp_runtime_contract.py`

- [ ] **Step 1: Write a failing test that proves formal execution-core turns still auto-mount local browser/file/shell/document tooling as canonical front-door capability**

```python
allowed = runtime_env["allowed_tool_capability_ids"]
assert "tool:execute_shell_command" not in allowed
assert "tool:browser_use" not in allowed
```

- [ ] **Step 2: Run the focused query-execution tests and verify the failure is on local-tool default exposure**

Run: `python -m pytest tests/kernel/query_execution_environment_parts/dispatch.py tests/app/test_capabilities_execution.py tests/app/test_mcp_runtime_contract.py -q`
Expected: FAIL because execution-core still auto-exposes local execution tools as a default formal path.

- [ ] **Step 3: Gate local execution tools behind explicit compatibility or non-formal paths**

Implementation notes:
- Formal assignment/execution-core turns should prefer executor-runtime dispatch.
- Keep direct local tools only where the request is explicitly local, compatibility-only, or non-assignment utility.

- [ ] **Step 4: Preserve evidence sinks and auditability without reintroducing a second canonical execution chain**

Implementation notes:
- Evidence may still flow from local tools.
- The capability registry and prompts must not describe those tools as the formal executor path.

- [ ] **Step 5: Re-run the focused query-execution tests**

Run: `python -m pytest tests/kernel/query_execution_environment_parts/dispatch.py tests/app/test_capabilities_execution.py tests/app/test_mcp_runtime_contract.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/kernel/query_execution_runtime.py src/copaw/capabilities/sources/system.py tests/kernel/query_execution_environment_parts/dispatch.py tests/app/test_capabilities_execution.py tests/app/test_mcp_runtime_contract.py
git commit -m "refactor: make formal execution front-door executor-first"
```

### Task 7: Run Fresh Verification, Sync Docs, And Finish The Mainline Workflow

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `DEPRECATION_LEDGER.md`
- Modify: `docs/superpowers/specs/2026-04-20-copaw-codex-app-server-hard-cut-design.md`
- Modify: touched files only if verification finds regressions

- [ ] **Step 1: Run fresh focused regression for all touched hard-cut slices**

Run:

```bash
python -m pytest tests/state/test_executor_runtime_service.py tests/state/test_external_runtime_service.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/kernel/test_assignment_envelope.py tests/kernel/test_task_execution_projection.py tests/kernel/query_execution_environment_parts/dispatch.py tests/app/test_capability_market_api.py tests/app/test_runtime_center_external_runtime_api.py tests/app/test_runtime_center_task_delegation_api.py tests/app/test_runtime_center_actor_api.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_execution_provider_wiring.py tests/app/test_capabilities_execution.py tests/app/test_mcp_runtime_contract.py tests/capabilities/test_project_donor_contracts.py -q
```

Expected: PASS

- [ ] **Step 2: Run the widened default regression gate**

Run: `python scripts/run_p0_runtime_terminal_gate.py`
Expected: PASS

- [ ] **Step 3: Run selected `L3` live smoke, including formal provider intake and Runtime Center readback**

Run:

```bash
PYTHONPATH=src python -m pytest tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q
PYTHONPATH=src python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q -k "runtime_center or runtime_center_overview or canonical_flow or operator or chat_run or long_run_smoke"
```

Expected: PASS

- [ ] **Step 4: Add or run a formal executor-provider intake smoke**

Implementation notes:
- Cover `/capability-market/executor-providers/search`
- Cover `/capability-market/executor-providers/install`
- Cover provider selection/readback through executor-runtime projection or Runtime Center

- [ ] **Step 5: Run selected `L4` soak**

Run:

```bash
PYTHONPATH=src python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q
```

Expected: PASS for repeated runs with stable results

- [ ] **Step 6: Update status and deprecation docs with exact commands, outputs, acceptance levels, and remaining boundaries**

Implementation notes:
- `TASK_STATUS.md` must distinguish `L1 / L2 / L3 / L4`
- `DEPRECATION_LEDGER.md` must state what moved to compatibility, what is ready-to-delete, and what still is not
- Update the `2026-04-20` design doc only where current architecture boundaries changed materially

- [ ] **Step 7: Commit, push `main`, and confirm the worktree is clean**

Run:

```bash
git add TASK_STATUS.md DEPRECATION_LEDGER.md docs/superpowers/specs/2026-04-20-copaw-codex-app-server-hard-cut-design.md
git add src/copaw/state/models_executor_runtime.py src/copaw/state/executor_runtime_service.py src/copaw/state/external_runtime_service.py src/copaw/state/repositories/base.py src/copaw/state/repositories/sqlite_executor_runtime.py src/copaw/state/store.py src/copaw/kernel/runtime_coordination.py src/copaw/kernel/main_brain_orchestrator.py src/copaw/kernel/delegation_service.py src/copaw/kernel/query_execution_runtime.py src/copaw/capabilities/sources/system.py src/copaw/app/runtime_bootstrap_execution.py src/copaw/app/runtime_bootstrap_domains.py src/copaw/app/runtime_bootstrap_models.py src/copaw/app/runtime_service_graph.py src/copaw/app/routers/capability_market.py src/copaw/app/runtime_center/state_query.py src/copaw/capabilities/project_donor_contracts.py
git add tests/state/test_executor_runtime_service.py tests/state/test_external_runtime_service.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/kernel/test_assignment_envelope.py tests/kernel/test_task_execution_projection.py tests/kernel/query_execution_environment_parts/dispatch.py tests/app/test_capability_market_api.py tests/app/test_runtime_center_external_runtime_api.py tests/app/test_runtime_center_task_delegation_api.py tests/app/test_runtime_center_actor_api.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_execution_provider_wiring.py tests/app/test_capabilities_execution.py tests/app/test_mcp_runtime_contract.py tests/capabilities/test_project_donor_contracts.py
git commit -m "refactor: finish external executor hard-cut remaining gaps"
git push origin main
git status --short
```

Expected: push succeeds and `git status --short` prints nothing.

## Done Criteria

- `model_policy_id` and `execution_policy_id` are no longer conflated.
- `ExecutorRuntime` canonical truth does not rely on `ExternalCapabilityRuntimeService`.
- Actor runtime is no longer part of the default formal startup graph.
- `delegation_service.py` remains only as explicit compatibility backend, not a formal execution owner.
- Donor/project execution shells no longer share active execution vocabulary with formal executor-provider intake.
- Formal execution-core turns no longer default to local browser/file/shell/document tooling.
- Fresh `L1 + L2 + default regression + L3 + selected L4` evidence exists, including provider-intake-specific smoke.
- `TASK_STATUS.md` and `DEPRECATION_LEDGER.md` match the real code state.
