# CoPaw Runtime-First Architecture Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align CoPaw's runtime-first computer-control architecture work with the current hard-cut autonomy baseline so future refactors strengthen the existing main chain instead of introducing a second architecture.

**Architecture:** Keep the current official chain `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan` as the only operator write truth, then execute a runtime-first refactor in six bounded areas: bootstrap modularization, orchestrator hardening, runtime-center route/domain cleanup, state model physical split, environment-service decomposition, and provider-manager demotion. Every change must preserve public entry contracts while shrinking legacy shared layers and avoiding new top-level truth objects.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLite repositories, pytest, TypeScript, React, Vitest, Markdown architecture docs

**Companion Docs:**
- Spec: `docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md`
- Hard-cut baseline: `docs/superpowers/specs/2026-03-25-copaw-full-architecture-map-and-hard-cut-redesign.md`
- Runtime status: `TASK_STATUS.md`
- Data model contract: `DATA_MODEL_DRAFT.md`
- API transition ledger: `API_TRANSITION_MAP.md`

---

## Scope Guardrails

- Do not create a second top-level architecture vocabulary that bypasses the current hard-cut chain.
- New terms such as `ExecutionSession` or `EnvironmentHandle` may appear only as mapped aliases, never as competing truth objects.
- Preserve the public bootstrap façade and current runtime-center URLs during the first structural pass.
- First-pass refactors are structural. Avoid opportunistic behavior changes unless a test proves the old behavior is already incorrect.
- `MainBrainChatService` remains pure chat; durable execution remains orchestrator-owned.
- `EnvironmentMount / SessionMount / RuntimeFrame / DecisionRequest / Patch` remain the canonical formal objects.
- Because the user did not ask for a commit and the repo may be dirty, replace commit checkpoints with verification checkpoints plus `git diff --stat`.

## File Map

### Bootstrap modularization

- Create: `src/copaw/app/runtime_bootstrap_repositories.py`
- Create: `src/copaw/app/runtime_bootstrap_environment.py`
- Create: `src/copaw/app/runtime_bootstrap_memory.py`
- Create: `src/copaw/app/runtime_bootstrap_execution.py`
- Create: `src/copaw/app/runtime_bootstrap_domains.py`
- Create: `src/copaw/app/runtime_bootstrap_startup.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_bootstrap.py`
- Test: `tests/app/test_runtime_bootstrap.py`

### Orchestrator hardening

- Create: `src/copaw/kernel/main_brain_intent_router.py`
- Create: `src/copaw/kernel/main_brain_execution_planner.py`
- Create: `src/copaw/kernel/main_brain_environment_coordinator.py`
- Create: `src/copaw/kernel/main_brain_recovery_coordinator.py`
- Create: `src/copaw/kernel/main_brain_result_committer.py`
- Modify: `src/copaw/kernel/main_brain_orchestrator.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Test: `tests/kernel/test_main_brain_orchestrator.py`
- Test: `tests/kernel/test_turn_executor.py`

### Runtime Center route/domain cleanup

- Create: `src/copaw/app/routers/runtime_center_routes_overview.py`
- Create: `src/copaw/app/routers/runtime_center_routes_governance.py`
- Create: `src/copaw/app/routers/runtime_center_routes_tasks.py`
- Create: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Create: `src/copaw/app/routers/runtime_center_routes_knowledge.py`
- Create: `src/copaw/app/routers/runtime_center_deps.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_actor.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_ops.py`
- Modify: `src/copaw/app/routers/runtime_center_shared.py`
- Modify: `src/copaw/app/routers/runtime_center.py`
- Test: `tests/app/test_runtime_center_api.py`

### State model physical split

- Create: `src/copaw/state/models_core.py`
- Create: `src/copaw/state/models_goals_tasks.py`
- Create: `src/copaw/state/models_agents_runtime.py`
- Create: `src/copaw/state/models_governance.py`
- Create: `src/copaw/state/models_memory.py`
- Create: `src/copaw/state/models_workflows.py`
- Create: `src/copaw/state/models_prediction.py`
- Create: `src/copaw/state/models_reporting.py`
- Create: `src/copaw/state/models_industry.py`
- Modify: `src/copaw/state/models.py`
- Test: `tests/state/test_models_exports.py`

### Environment decomposition

- Create: `src/copaw/environments/session_service.py`
- Create: `src/copaw/environments/lease_service.py`
- Create: `src/copaw/environments/observation_service.py`
- Create: `src/copaw/environments/replay_service.py`
- Create: `src/copaw/environments/artifact_service.py`
- Create: `src/copaw/environments/health_service.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/__init__.py`
- Test: `tests/environments/test_environment_service_split.py`

### Provider demotion

- Create: `src/copaw/providers/provider_registry.py`
- Create: `src/copaw/providers/provider_storage.py`
- Create: `src/copaw/providers/provider_resolution_service.py`
- Create: `src/copaw/providers/provider_chat_model_factory.py`
- Create: `src/copaw/providers/provider_fallback_service.py`
- Modify: `src/copaw/providers/provider_manager.py`
- Test: `tests/providers/test_provider_manager_facade.py`

### Docs and contract sync

- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- Modify: `SPIDER_MAIN_CHAIN_MAP.md`

### Task 1: Modularize Runtime Bootstrap Without Changing Public Entry Contracts

**Files:**
- Create: `src/copaw/app/runtime_bootstrap_repositories.py`
- Create: `src/copaw/app/runtime_bootstrap_environment.py`
- Create: `src/copaw/app/runtime_bootstrap_memory.py`
- Create: `src/copaw/app/runtime_bootstrap_execution.py`
- Create: `src/copaw/app/runtime_bootstrap_domains.py`
- Create: `src/copaw/app/runtime_bootstrap_startup.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_bootstrap.py`
- Test: `tests/app/test_runtime_bootstrap.py`

- [ ] **Step 1: Write the failing bootstrap surface test**

```python
def test_build_runtime_bootstrap_still_returns_runtimebootstrap_contract():
    bootstrap = build_runtime_bootstrap(
        session_backend=fake_session_backend(),
        memory_manager=fake_memory_manager(),
        mcp_manager=fake_mcp_manager(),
    )
    assert bootstrap.turn_executor is not None
    assert bootstrap.main_brain_orchestrator is not None
    assert bootstrap.environment_service is not None
```

- [ ] **Step 2: Run the targeted test to verify the current refactor seam**

Run: `python -m pytest tests/app/test_runtime_bootstrap.py -q`
Expected: PASS or FAIL with a clear bootstrap contract gap before refactor starts.

- [ ] **Step 3: Move each in-file helper into its own bootstrap module**

Rules:
- `runtime_service_graph.py` keeps `build_runtime_bootstrap(...)`
- New modules own repository, environment, memory, execution, domain, and startup assembly
- Imports stay one-directional

- [ ] **Step 4: Re-run the targeted bootstrap test**

Run: `python -m pytest tests/app/test_runtime_bootstrap.py -q`
Expected: PASS with unchanged public bootstrap behavior.

- [ ] **Step 5: Record the structural diff checkpoint**

Run: `git diff --stat`
Expected: bootstrap files changed, no unrelated runtime behavior files included.

### Task 2: Make `MainBrainOrchestrator` a Real Coordination Core

**Files:**
- Create: `src/copaw/kernel/main_brain_intent_router.py`
- Create: `src/copaw/kernel/main_brain_execution_planner.py`
- Create: `src/copaw/kernel/main_brain_environment_coordinator.py`
- Create: `src/copaw/kernel/main_brain_recovery_coordinator.py`
- Create: `src/copaw/kernel/main_brain_result_committer.py`
- Modify: `src/copaw/kernel/main_brain_orchestrator.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Test: `tests/kernel/test_main_brain_orchestrator.py`
- Test: `tests/kernel/test_turn_executor.py`

- [ ] **Step 1: Write the failing orchestrator responsibility tests**

```python
async def test_orchestrator_classifies_and_selects_execution_mode():
    result = await orchestrator.plan_turn(msgs=[user_msg("帮我整理桌面文件并继续跟进")], request=req)
    assert result.intent_kind == "orchestrated-task"
    assert result.execution_mode == "orchestrate"


async def test_orchestrator_commits_result_metadata_before_stream_completion():
    result = await orchestrator.prepare_turn(msgs=[user_msg("继续推进电商团队本周工作")], request=req)
    assert result.runtime_context.assignment_owner is not None
```

- [ ] **Step 2: Run the targeted kernel tests**

Run: `python -m pytest tests/kernel/test_main_brain_orchestrator.py tests/kernel/test_turn_executor.py -q`
Expected: FAIL because the orchestrator is still a forwarding façade.

- [ ] **Step 3: Add internal coordinators and keep `execute_stream(...)` as façade**

Rules:
- `MainBrainOrchestrator` remains the public entry
- Internal components own intent routing, planning, environment coordination, recovery, and result commit
- `KernelTurnExecutor` still decides `chat` vs `orchestrate`, but orchestration details move under orchestrator

- [ ] **Step 4: Re-run the targeted kernel tests**

Run: `python -m pytest tests/kernel/test_main_brain_orchestrator.py tests/kernel/test_turn_executor.py -q`
Expected: PASS.

- [ ] **Step 5: Smoke-check current orchestration regressions**

Run: `python -m pytest tests/state/test_main_brain_hard_cut.py -q`
Expected: PASS, proving the new orchestrator still honors the current hard-cut chain.

### Task 3: Finish Runtime Center Domain Split and Delete Shared-Layer Debt

**Files:**
- Create: `src/copaw/app/routers/runtime_center_routes_overview.py`
- Create: `src/copaw/app/routers/runtime_center_routes_governance.py`
- Create: `src/copaw/app/routers/runtime_center_routes_tasks.py`
- Create: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Create: `src/copaw/app/routers/runtime_center_routes_knowledge.py`
- Create: `src/copaw/app/routers/runtime_center_deps.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_actor.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_ops.py`
- Modify: `src/copaw/app/routers/runtime_center_shared.py`
- Modify: `src/copaw/app/routers/runtime_center.py`
- Test: `tests/app/test_runtime_center_api.py`

- [ ] **Step 1: Write the failing API structure tests**

```python
def test_runtime_center_core_no_longer_exports_memory_routes():
    from copaw.app.routers import runtime_center_routes_core as core
    assert not hasattr(core, "recall_memory")


def test_runtime_center_shared_no_longer_contains_delegate_request_shape():
    from copaw.app.routers import runtime_center_shared as shared
    assert not hasattr(shared, "TaskDelegationRequest")
```

- [ ] **Step 2: Run the targeted router tests**

Run: `python -m pytest tests/app/test_runtime_center_api.py -q -k runtime_center`
Expected: FAIL because shared/core still own those responsibilities.

- [ ] **Step 3: Move handlers by domain and collapse shared to common deps/utilities only**

Rules:
- Keep existing `/api/runtime-center/...` URLs
- `runtime_center_shared.py` may keep router + minimal helpers only
- Delete stale retired DTOs from shared
- Replace `import *` with explicit imports

- [ ] **Step 4: Re-run the targeted router tests**

Run: `python -m pytest tests/app/test_runtime_center_api.py -q -k runtime_center`
Expected: PASS.

- [ ] **Step 5: Run a runtime-center regression slice**

Run: `python -m pytest tests/app/industry_api_parts/runtime_updates.py -q`
Expected: PASS.

### Task 4: Physically Split `state/models.py` While Preserving the Contract

**Files:**
- Create: `src/copaw/state/models_core.py`
- Create: `src/copaw/state/models_goals_tasks.py`
- Create: `src/copaw/state/models_agents_runtime.py`
- Create: `src/copaw/state/models_governance.py`
- Create: `src/copaw/state/models_memory.py`
- Create: `src/copaw/state/models_workflows.py`
- Create: `src/copaw/state/models_prediction.py`
- Create: `src/copaw/state/models_reporting.py`
- Create: `src/copaw/state/models_industry.py`
- Modify: `src/copaw/state/models.py`
- Test: `tests/state/test_models_exports.py`

- [ ] **Step 1: Write the failing export-compat test**

```python
def test_state_models_reexport_existing_runtime_records():
    from copaw.state.models import AssignmentRecord, AgentReportRecord, StrategyMemoryRecord
    assert AssignmentRecord.__name__ == "AssignmentRecord"
    assert AgentReportRecord.__name__ == "AgentReportRecord"
    assert StrategyMemoryRecord.__name__ == "StrategyMemoryRecord"
```

- [ ] **Step 2: Run the targeted state export test**

Run: `python -m pytest tests/state/test_models_exports.py -q`
Expected: FAIL because the new split modules do not exist yet.

- [ ] **Step 3: Move models into layered files and re-export from `models.py`**

Rules:
- No field renames in this phase
- No schema cleanup in this phase
- Keep import paths stable for current callers

- [ ] **Step 4: Re-run the targeted state export test**

Run: `python -m pytest tests/state/test_models_exports.py -q`
Expected: PASS.

- [ ] **Step 5: Run a hard-cut contract regression**

Run: `python -m pytest tests/state/test_main_brain_hard_cut.py tests/app/industry_api_parts/bootstrap_lifecycle.py -q`
Expected: PASS.

### Task 5: Decompose `EnvironmentService` Into Focused Subservices

**Files:**
- Create: `src/copaw/environments/session_service.py`
- Create: `src/copaw/environments/lease_service.py`
- Create: `src/copaw/environments/observation_service.py`
- Create: `src/copaw/environments/replay_service.py`
- Create: `src/copaw/environments/artifact_service.py`
- Create: `src/copaw/environments/health_service.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/__init__.py`
- Test: `tests/environments/test_environment_service_split.py`

- [ ] **Step 1: Write the failing service-decomposition test**

```python
def test_environment_service_delegates_to_session_and_lease_subservices():
    env = EnvironmentService(registry=fake_registry())
    assert env.session_service is not None
    assert env.lease_service is not None
```

- [ ] **Step 2: Run the targeted environment test**

Run: `python -m pytest tests/environments/test_environment_service_split.py -q`
Expected: FAIL because the split subservices do not exist yet.

- [ ] **Step 3: Extract focused subservices and keep `EnvironmentService` as façade**

Rules:
- `EnvironmentService` remains public entry
- session, lease, observation, replay, artifact, and health logic move behind dedicated collaborators
- Preserve existing public methods in the first pass

- [ ] **Step 4: Re-run the targeted environment test**

Run: `python -m pytest tests/environments/test_environment_service_split.py -q`
Expected: PASS.

- [ ] **Step 5: Run runtime health regressions**

Run: `python -m pytest tests/app/test_runtime_health_service.py -q`
Expected: PASS.

### Task 6: Demote `ProviderManager` to a Compatibility Façade

**Files:**
- Create: `src/copaw/providers/provider_registry.py`
- Create: `src/copaw/providers/provider_storage.py`
- Create: `src/copaw/providers/provider_resolution_service.py`
- Create: `src/copaw/providers/provider_chat_model_factory.py`
- Create: `src/copaw/providers/provider_fallback_service.py`
- Modify: `src/copaw/providers/provider_manager.py`
- Test: `tests/providers/test_provider_manager_facade.py`

- [ ] **Step 1: Write the failing provider façade test**

```python
def test_provider_manager_facade_delegates_resolution_and_factory():
    manager = ProviderManager()
    assert manager._resolution_service is not None
    assert manager._chat_model_factory is not None
```

- [ ] **Step 2: Run the targeted provider test**

Run: `python -m pytest tests/providers/test_provider_manager_facade.py -q`
Expected: FAIL because the manager still owns everything directly.

- [ ] **Step 3: Extract registry/storage/resolution/factory/fallback collaborators**

Rules:
- Keep `ProviderManager.get_instance()` and `ProviderManager.get_active_chat_model()` for compat
- New logic lives in extracted collaborators
- No UI/schema change in this phase

- [ ] **Step 4: Re-run the targeted provider test**

Run: `python -m pytest tests/providers/test_provider_manager_facade.py -q`
Expected: PASS.

- [ ] **Step 5: Run current provider/system regressions**

Run: `python -m pytest tests/app/test_system_api.py tests/agents/test_memory_manager_config.py -q`
Expected: PASS.

### Task 7: Sync the Formal Docs and Verification Ledger

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- Modify: `SPIDER_MAIN_CHAIN_MAP.md`

- [ ] **Step 1: Update docs to reference the runtime-first supplement as a secondary lens**

Rules:
- hard-cut chain remains primary
- runtime-first becomes a supplemental perspective
- no new truth objects added to the official data model

- [ ] **Step 2: Verify document cross-references**

Run: `rg -n "runtime-first|ComputerControlRuntime|ExecutionSession|EnvironmentHandle" TASK_STATUS.md DATA_MODEL_DRAFT.md API_TRANSITION_MAP.md COPAW_CARRIER_UPGRADE_MASTERPLAN.md docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md`
Expected: every occurrence either maps to existing formal objects or is explicitly marked as a supplemental alias.

- [ ] **Step 3: Run the focused live regressions**

Run: `python -m pytest tests/app/industry_api_parts/retirement_chain.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py tests/state/test_main_brain_hard_cut.py -q`
Expected: PASS.

- [ ] **Step 4: Run the frontend control-chain regression**

Run: `npx vitest run src/runtime/controlChainPresentation.test.ts`
Expected: PASS.

- [ ] **Step 5: Capture the final verification checkpoint**

Run: `git diff --stat`
Expected: only the planned architecture, runtime, and docs files changed.

---

## Verification Bundle

Before calling this alignment work complete, run this exact bundle:

```bash
python -m pytest tests/app/test_runtime_bootstrap.py -q
python -m pytest tests/kernel/test_main_brain_orchestrator.py tests/kernel/test_turn_executor.py -q
python -m pytest tests/app/test_runtime_center_api.py -q -k runtime_center
python -m pytest tests/state/test_models_exports.py tests/state/test_main_brain_hard_cut.py -q
python -m pytest tests/environments/test_environment_service_split.py tests/app/test_runtime_health_service.py -q
python -m pytest tests/providers/test_provider_manager_facade.py tests/app/test_system_api.py tests/agents/test_memory_manager_config.py -q
python -m pytest tests/app/industry_api_parts/retirement_chain.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py -q
npx vitest run src/runtime/controlChainPresentation.test.ts
git diff --stat
```

Expected:

- backend regression slices stay green
- frontend control-chain presenter stays green
- no new runtime truth path bypasses the existing hard-cut chain
- docs consistently describe runtime-first as a supplemental lens, not a second architecture
