# Runtime-First Computer-Control Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the runtime-first “computer control” refactor with CoPaw’s existing hard-cut autonomy baseline so the system gets a stronger orchestrator, cleaner runtime boundaries, a decomposed environment domain, and a demoted provider layer without creating a second architecture language.

**Architecture:** Treat `Control / Execution / Environment / Knowledge` as operating views over the existing formal architecture instead of a new parallel model. Execute in this order: keep docs/status aligned, split the current composition root, thicken `MainBrainOrchestrator`, clean Runtime Center shared boundaries, physically split state models, decompose `EnvironmentService`, and demote `ProviderManager` behind smaller services and facades.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLite repositories, pytest, TypeScript/React for Runtime Center verification

**Companion Docs:**
- Spec: `docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md`
- Existing hard-cut spec: `docs/superpowers/specs/2026-03-25-copaw-full-architecture-map-and-hard-cut-redesign.md`
- Baseline status: `TASK_STATUS.md`
- Data model: `DATA_MODEL_DRAFT.md`
- API ledger: `API_TRANSITION_MAP.md`

---

## Scope Guardrails

- Do not introduce a second main chain. Operator writes must remain on `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan`.
- Do not introduce new first-class truth objects such as `ComputerControlRuntime` or `ExecutionSession` unless they are explicitly mapped to existing formal objects.
- Preserve current external HTTP contracts unless the hard-cut docs already retired them.
- Prefer behavior-preserving structural splits first, then semantic tightening.
- Every phase must leave docs and tests updated; do not let runtime-first docs drift from live code again.

## File Map

### Docs and architecture contract

- Create: `docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md`
- Create: `docs/superpowers/plans/2026-03-25-copaw-runtime-first-computer-control-alignment.md`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`

### Runtime bootstrap split

- Create: `src/copaw/app/runtime_bootstrap_repositories.py`
- Create: `src/copaw/app/runtime_bootstrap_observability.py`
- Create: `src/copaw/app/runtime_bootstrap_query.py`
- Create: `src/copaw/app/runtime_bootstrap_execution.py`
- Create: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_bootstrap.py`

### Main-brain orchestration

- Create: `src/copaw/kernel/main_brain_execution_planner.py`
- Create: `src/copaw/kernel/main_brain_environment_coordinator.py`
- Create: `src/copaw/kernel/main_brain_recovery_coordinator.py`
- Create: `src/copaw/kernel/main_brain_result_committer.py`
- Modify: `src/copaw/kernel/main_brain_orchestrator.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `src/copaw/kernel/query_execution.py`

### Runtime Center domain cleanup

- Create: `src/copaw/app/routers/runtime_center_routes_overview.py`
- Create: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Create: `src/copaw/app/routers/runtime_center_routes_knowledge.py`
- Create: `src/copaw/app/routers/runtime_center_routes_reports.py`
- Create: `src/copaw/app/routers/runtime_center_routes_industry.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `src/copaw/app/routers/runtime_center_shared.py`
- Modify: `src/copaw/app/routers/runtime_center.py`

### State model split

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
- Modify: `src/copaw/state/__init__.py`

### Environment service decomposition

- Create: `src/copaw/environments/session_service.py`
- Create: `src/copaw/environments/lease_service.py`
- Create: `src/copaw/environments/replay_service.py`
- Create: `src/copaw/environments/artifact_service.py`
- Create: `src/copaw/environments/health_service.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/__init__.py`

### Provider demotion

- Create: `src/copaw/providers/provider_registry.py`
- Create: `src/copaw/providers/provider_storage.py`
- Create: `src/copaw/providers/provider_resolution_service.py`
- Create: `src/copaw/providers/provider_chat_model_factory.py`
- Create: `src/copaw/providers/provider_fallback_service.py`
- Modify: `src/copaw/providers/provider_manager.py`
- Modify: call sites that should stop using `ProviderManager.get_instance()` directly

### Tests

- Create: `tests/app/test_runtime_bootstrap_split.py`
- Create: `tests/kernel/test_main_brain_orchestrator_roles.py`
- Create: `tests/app/test_runtime_center_router_split.py`
- Create: `tests/state/test_models_module_exports.py`
- Create: `tests/environments/test_environment_service_split.py`
- Create: `tests/providers/test_provider_manager_facade.py`
- Modify: existing runtime, state, environment, and provider tests touched by these refactors

### Task 1: Lock the Documentation Contract

**Files:**
- Create: `docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md`
- Create: `docs/superpowers/plans/2026-03-25-copaw-runtime-first-computer-control-alignment.md`
- Modify: `TASK_STATUS.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`

- [ ] **Step 1: Write the failing documentation consistency test**

```python
def test_runtime_first_spec_does_not_define_a_second_main_chain() -> None:
    text = Path("docs/superpowers/specs/2026-03-25-copaw-runtime-first-computer-control-alignment.md").read_text(encoding="utf-8")
    assert "StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan" in text
    assert "不能替代现有 7 层" in text
```

- [ ] **Step 2: Run the targeted doc check**

Run: `python -m pytest tests/app/test_runtime_bootstrap_split.py -q -k documentation`
Expected: FAIL until the alignment doc and references exist.

- [ ] **Step 3: Write the alignment spec and plan, then sync status/docs**

Rules:
- The runtime-first spec must explicitly state it is a supplement, not a replacement.
- `TASK_STATUS.md` must mention the supplemental runtime-first spec only if it becomes part of the active read chain.
- `DATA_MODEL_DRAFT.md` and `API_TRANSITION_MAP.md` must keep the existing formal object vocabulary.

- [ ] **Step 4: Re-run the doc check**

Run: `python -m pytest tests/app/test_runtime_bootstrap_split.py -q -k documentation`
Expected: PASS.

- [ ] **Step 5: Save a checkpoint**

Run: `git diff --stat`
Expected: only doc files and referenced ledgers changed.

### Task 2: Split the Runtime Bootstrap Without Changing Behavior

**Files:**
- Create: `src/copaw/app/runtime_bootstrap_repositories.py`
- Create: `src/copaw/app/runtime_bootstrap_observability.py`
- Create: `src/copaw/app/runtime_bootstrap_query.py`
- Create: `src/copaw/app/runtime_bootstrap_execution.py`
- Create: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_bootstrap.py`
- Test: `tests/app/test_runtime_bootstrap_split.py`

- [x] **Step 1: Write the failing bootstrap parity tests**

```python
def test_build_runtime_bootstrap_still_returns_runtime_bootstrap(monkeypatch) -> None:
    bootstrap = build_runtime_bootstrap(...)
    assert bootstrap.turn_executor is not None
    assert bootstrap.main_brain_orchestrator is not None
```

- [x] **Step 2: Run the bootstrap tests to confirm current failure**

Run: `python -m pytest tests/app/test_runtime_bootstrap_split.py -q`
Expected: FAIL once imports are pointed at not-yet-created bootstrap modules.

- [x] **Step 3: Extract helper sections into focused modules**

Rules:
- `build_runtime_bootstrap(...)` remains the public entry.
- Move repository wiring, observability wiring, query services, execution stack, and domain services into separate files.
- Do not change service behavior in this task.

- [x] **Step 4: Re-run bootstrap and smoke tests**

Run: `python -m pytest tests/app/test_runtime_bootstrap_split.py tests/app/industry_api_parts/runtime_updates.py -q`
Expected: PASS.

- [x] **Step 5: Verify imports stay stable**

Run: `python - <<'PY'\nfrom copaw.app.runtime_bootstrap import build_runtime_bootstrap\nprint(callable(build_runtime_bootstrap))\nPY`
Expected: prints `True`.

### Task 3: Make `MainBrainOrchestrator` a Real Coordinator

**Files:**
- Create: `src/copaw/kernel/main_brain_execution_planner.py`
- Create: `src/copaw/kernel/main_brain_environment_coordinator.py`
- Create: `src/copaw/kernel/main_brain_recovery_coordinator.py`
- Create: `src/copaw/kernel/main_brain_result_committer.py`
- Modify: `src/copaw/kernel/main_brain_orchestrator.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `src/copaw/kernel/query_execution.py`
- Test: `tests/kernel/test_main_brain_orchestrator_roles.py`
- Test: `tests/kernel/test_turn_executor.py`

- [x] **Step 1: Write the failing orchestrator-responsibility tests**

```python
async def test_orchestrator_classifies_and_plans_before_query_execution() -> None:
    result = await orchestrator.ingest_operator_turn(...)
    assert result.intent_kind == "orchestrate"
    assert result.execution_mode in {"direct-answer", "delegated", "environment-bound"}


async def test_turn_executor_uses_orchestrator_for_non_chat_turns() -> None:
    ...
```

- [x] **Step 2: Run the targeted orchestrator tests**

Run: `python -m pytest tests/kernel/test_main_brain_orchestrator_roles.py tests/kernel/test_turn_executor.py -q`
Expected: FAIL because the orchestrator is still a forwarding shell.

- [x] **Step 3: Introduce planner/coordinator/committer helpers**

Rules:
- `MainBrainOrchestrator.execute_stream()` remains externally compatible.
- Classification, planning, environment selection, recovery checks, and result commit happen inside the orchestrator chain before/after query execution.
- `KernelQueryExecutionService` remains an execution engine, not the place where orchestration policy accumulates.

- [x] **Step 4: Re-run targeted kernel tests**

Run: `python -m pytest tests/kernel/test_main_brain_orchestrator_roles.py tests/kernel/test_turn_executor.py tests/state/test_main_brain_hard_cut.py -q`
Expected: PASS.

- [x] **Step 5: Review the change surface**

Run: `git diff --stat`
Expected: orchestrator-related files only.

### Task 4: Clean Runtime Center Domain Boundaries

**Files:**
- Create: `src/copaw/app/routers/runtime_center_routes_overview.py`
- Create: `src/copaw/app/routers/runtime_center_routes_memory.py`
- Create: `src/copaw/app/routers/runtime_center_routes_knowledge.py`
- Create: `src/copaw/app/routers/runtime_center_routes_reports.py`
- Create: `src/copaw/app/routers/runtime_center_routes_industry.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `src/copaw/app/routers/runtime_center_shared.py`
- Modify: `src/copaw/app/routers/runtime_center.py`
- Test: `tests/app/test_runtime_center_router_split.py`

- [x] **Step 1: Write failing router-boundary tests**

```python
def test_runtime_center_memory_routes_live_in_memory_module() -> None:
    import copaw.app.routers.runtime_center_routes_memory as module
    assert hasattr(module, "recall_memory")
```

- [x] **Step 2: Run the targeted router tests**

Run: `python -m pytest tests/app/test_runtime_center_router_split.py -q`
Expected: FAIL until the domain modules exist.

- [x] **Step 3: Move routes by domain and shrink shared surface**

Rules:
- Keep existing `/api/runtime-center/*` URLs.
- Remove retired delegate request schema and any dead compatibility helper from `runtime_center_shared.py`.
- Replace star-import sprawl with explicit imports where practical.

- [x] **Step 4: Re-run router and API regression tests**

Run: `python -m pytest tests/app/test_runtime_center_router_split.py tests/app/test_runtime_center_api.py -q`
Expected: PASS.

- [x] **Step 5: Smoke the router import surface**

Run: `python - <<'PY'\nfrom copaw.app.routers.runtime_center import _runtime_center_routes_core\nprint('ok')\nPY`
Expected: prints `ok`.

### Task 5: Physically Split the State Models

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
- Modify: `src/copaw/state/__init__.py`
- Test: `tests/state/test_models_module_exports.py`

- [x] **Step 1: Write the failing module export tests**

```python
def test_assignment_record_reexports_from_state_models() -> None:
    from copaw.state.models import AssignmentRecord
    assert AssignmentRecord.__name__ == "AssignmentRecord"
```

- [x] **Step 2: Run the targeted state export tests**

Run: `python -m pytest tests/state/test_models_module_exports.py -q`
Expected: FAIL until the split modules and re-exports exist.

- [x] **Step 3: Move record classes without renaming them**

Rules:
- Preserve class names and fields.
- Preserve import compatibility from `copaw.state.models`.
- Separate canonical, runtime-carrier, override, derived, and reporting groups by module.

- [x] **Step 4: Re-run state and repository regressions**

Run: `python -m pytest tests/state/test_models_module_exports.py tests/state/test_main_brain_hard_cut.py tests/app/industry_api_parts/bootstrap_lifecycle.py -q`
Expected: PASS.

- [x] **Step 5: Check for stale imports**

Run: `rg -n "from copaw\\.state\\.models import" src tests`
Expected: output is acceptable because compatibility re-exports remain.

### Task 6: Decompose `EnvironmentService` Behind a Stable Facade

**Files:**
- Create: `src/copaw/environments/session_service.py`
- Create: `src/copaw/environments/lease_service.py`
- Create: `src/copaw/environments/replay_service.py`
- Create: `src/copaw/environments/artifact_service.py`
- Create: `src/copaw/environments/health_service.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/__init__.py`
- Test: `tests/environments/test_environment_service_split.py`

- [x] **Step 1: Write the failing environment split tests**

```python
def test_environment_service_uses_internal_session_service() -> None:
    service = EnvironmentService(...)
    assert hasattr(service, "_session_service")
```

- [x] **Step 2: Run the targeted environment tests**

Run: `python -m pytest tests/environments/test_environment_service_split.py -q`
Expected: FAIL until the internal services exist.

- [x] **Step 3: Extract internal environment coordinators**

Rules:
- Keep `EnvironmentService` as the outward-facing facade.
- Move session, lease, replay, artifact, and health concerns into focused collaborators.
- Preserve existing environment API behavior.

- [x] **Step 4: Re-run environment and runtime health tests**

Run: `python -m pytest tests/environments/test_environment_service_split.py tests/environments/test_environment_registry.py tests/app/test_system_api.py tests/app/test_startup_recovery.py -q`
Expected: PASS.

- [x] **Step 5: Inspect the facade size**

Run: `(Get-Content src/copaw/environments/service.py -Encoding utf8 | Measure-Object -Line).Lines`
Expected: materially smaller than the pre-split baseline (`1435 -> 408` lines in the completed refactor).

### Task 7: Demote `ProviderManager` to a Compatibility Facade

**Files:**
- Create: `src/copaw/providers/provider_registry.py`
- Create: `src/copaw/providers/provider_storage.py`
- Create: `src/copaw/providers/provider_resolution_service.py`
- Create: `src/copaw/providers/provider_chat_model_factory.py`
- Create: `src/copaw/providers/provider_fallback_service.py`
- Modify: `src/copaw/providers/provider_manager.py`
- Modify: call sites that should stop using `ProviderManager.get_instance()` directly
- Test: `tests/providers/test_provider_manager_facade.py`

- [x] **Step 1: Write the failing provider facade tests**

```python
def test_provider_manager_delegates_resolution_to_resolution_service() -> None:
    manager = ProviderManager()
    assert hasattr(manager, "_resolution_service")
```

- [x] **Step 2: Run the targeted provider tests**

Run: `python -m pytest tests/providers/test_provider_manager_facade.py -q`
Expected: FAIL until the split services exist.

- [x] **Step 3: Extract provider sub-services and rewire manager**

Rules:
- `ProviderManager` remains import-compatible.
- Storage, registry, resolution, fallback, and chat-model construction move into dedicated collaborators.
- Stop direct singleton access in runtime/core code where dependency injection is practical.

- [x] **Step 4: Re-run provider and memory/config regressions**

Run: `python -m pytest tests/providers/test_provider_manager_facade.py tests/providers/test_provider_manager.py tests/providers/test_llm_routing_provider_manager.py tests/providers/test_runtime_fallback_chat_model.py tests/agents/test_memory_manager_config.py tests/app/test_system_api.py tests/app/test_models_api.py tests/app/test_runtime_bootstrap_split.py -q`
Expected: PASS (`50 passed`).

- [x] **Step 5: Audit remaining singleton usage**

Run: `rg -n "ProviderManager\\.get_instance\\(" src`
Expected: remaining hits are limited to `app/runtime_service_graph.py`, router/CLI boundaries, `agents/memory/memory_manager.py`, and the compat static inside `providers/provider_manager.py`.

### Task 8: Full Regression and Contract Verification

**Files:**
- Modify: any touched tests/docs needed for final consistency

- [x] **Step 1: Run targeted backend/runtime regression suites**

Run: `python -m pytest tests/app/industry_api_parts/runtime_updates.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/state/test_main_brain_hard_cut.py tests/kernel/test_turn_executor.py tests/app/test_runtime_center_api.py tests/app/test_system_api.py -q`
Expected: PASS.

- [x] **Step 2: Run environment/provider-specific suites**

Run: `python -m pytest tests/environments/test_environment_service_split.py tests/providers/test_provider_manager_facade.py tests/app/test_system_api.py -q`
Expected: PASS (`16 passed`). Runtime health / self-check contract currently lives in `tests/app/test_system_api.py`.

- [x] **Step 3: Run frontend runtime-center verification if UI files changed**

Run: `npm --prefix console exec vitest run src/runtime/controlChainPresentation.test.ts`
Expected: PASS (`1 passed`, `2 tests`).

- [x] **Step 4: Verify no stale delegate/shared-contract residue remains**

Run: `rg -n "TaskDelegationRequest|/tasks/\\{task_id\\}/delegate|runtime_center_shared import \\*" src/copaw/app/routers`
Expected: no dead delegate schema; the remaining `runtime_center_shared import *` in `runtime_center.py` is the deliberate aggregation surface and is now explicitly documented in code.

- [x] **Step 5: Final diff review**

Run: `git diff --stat` and `git status --short`
Expected: `git diff --stat` may be empty in this repository because the current workspace baseline is still untracked; use `git status --short` to confirm the touched surface stays within the runtime-first alignment scope.

---

## Review Loop Note

This plan normally requires a separate plan-review subagent, but this session is not authorized to spawn new agents unless the user explicitly asks for delegation. If delegation is later approved, run a plan-review pass before implementation.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-03-25-copaw-runtime-first-computer-control-alignment.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

If you want, I can continue with Inline Execution against this plan in the current session.
