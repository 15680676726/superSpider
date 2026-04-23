# External Executor Multi-Agent Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make external executor runtime the only formal execution backend for multi-agent work, then physically retire the local actor/delegation runtime.

**Architecture:** First extend the formal `ExecutorRuntime` seam so it can carry the multi-agent semantics that still live in the local actor stack: child-run dispatch, continuity, checkpoint/resume, and recovery. Then cut production writers off the actor mailbox/supervisor path, including the industry-owned runtime truth that still persists `AgentRuntimeRecord` and `AgentThreadBindingRecord`. After that, migrate formal read surfaces and bootstrap exports away from actor runtime truth, and only then delete actor kernel/state files plus the remaining state/repository/env glue that still imports those records.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite repositories, pytest

---

## Scope-Checked File Map

**External executor formal contract and truth**
- Modify: `src/copaw/kernel/executor_runtime_port.py`
- Modify: `src/copaw/kernel/runtime_coordination.py`
- Modify: `src/copaw/state/models_executor_runtime.py`
- Modify: `src/copaw/state/executor_runtime_service.py`
- Modify: `src/copaw/adapters/executors/codex_app_server_adapter.py`
- Test: `tests/state/test_executor_runtime_service.py`
- Test: `tests/adapters/test_codex_app_server_adapter.py`
- Test: `tests/kernel/test_main_brain_executor_runtime_integration.py`
- Test: `tests/app/test_external_executor_live_smoke.py`

**Production writers still using local actor/delegation**
- Modify: `src/copaw/kernel/delegation_service.py`
- Modify: `src/copaw/app/startup_recovery.py`
- Modify: `src/copaw/app/_app.py`
- Modify: `src/copaw/app/runtime_lifecycle.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_context.py`
- Modify: `src/copaw/industry/service_team_runtime.py`
- Modify: `src/copaw/industry/service_cleanup.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Test: `tests/app/test_runtime_center_task_delegation_api.py`
- Test: `tests/app/test_startup_recovery.py`
- Test: `tests/app/test_runtime_lifecycle.py`
- Test: `tests/app/test_industry_service_wiring.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `tests/kernel/test_assignment_envelope.py`

**Actor runtime truth and read surfaces**
- Modify: `src/copaw/app/runtime_state_bindings.py`
- Modify: `src/copaw/app/routers/runtime_center_dependencies.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `src/copaw/app/routers/runtime_center_actor_capabilities.py`
- Modify: `src/copaw/kernel/agent_profile_service.py`
- Modify: `src/copaw/app/runtime_center/conversations.py`
- Modify: `src/copaw/kernel/query_execution_context_runtime.py`
- Modify: `src/copaw/kernel/query_execution_usage_runtime.py`
- Modify: `src/copaw/kernel/query_execution_resident_runtime.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `src/copaw/state/__init__.py`
- Modify: `src/copaw/state/repositories/__init__.py`
- Test: `tests/app/test_runtime_center_actor_api.py`
- Test: `tests/app/test_runtime_chat_thread_binding.py`
- Test: `tests/app/test_runtime_conversations_api.py`
- Test: `tests/kernel/test_query_usage_accounting.py`
- Test: `tests/industry/test_runtime_views_split.py`

**Actor runtime state/kernel physical retirement**
- Delete: `src/copaw/kernel/actor_mailbox.py`
- Delete: `src/copaw/kernel/actor_worker.py`
- Delete: `src/copaw/kernel/actor_supervisor.py`
- Delete: `src/copaw/state/models_agents_runtime.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_repositories.py`
- Modify: `src/copaw/app/runtime_center/recovery_projection.py`
- Modify: `src/copaw/state/repositories/sqlite_governance_agents.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/repositories/base.py`
- Modify: `src/copaw/state/repositories/sqlite_shared.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/lease_service.py`
- Modify: `src/copaw/kernel/__init__.py`
- Modify: `src/copaw/app/runtime_bootstrap_execution.py`
- Test: `tests/kernel/test_actor_mailbox.py`
- Test: `tests/kernel/test_actor_worker.py`
- Test: `tests/kernel/test_actor_supervisor.py`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `tests/kernel/query_execution_environment_parts/lifecycle.py`
- Test: `tests/app/test_startup_recovery.py`
- Test: `tests/state/test_models_module_exports.py`
- Test: `tests/state/test_sqlite_repositories.py`

**Acceptance and docs**
- Modify: `TASK_STATUS.md`
- Modify: `DEPRECATION_LEDGER.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`

---

### Task 1: Add Missing Multi-Agent Semantics To External Executor

**Files:**
- Modify: `src/copaw/kernel/executor_runtime_port.py`
- Modify: `src/copaw/kernel/runtime_coordination.py`
- Modify: `src/copaw/state/models_executor_runtime.py`
- Modify: `src/copaw/state/executor_runtime_service.py`
- Modify: `src/copaw/adapters/executors/codex_app_server_adapter.py`
- Test: `tests/state/test_executor_runtime_service.py`
- Test: `tests/adapters/test_codex_app_server_adapter.py`
- Test: `tests/kernel/test_main_brain_executor_runtime_integration.py`
- Test: `tests/app/test_external_executor_live_smoke.py`

- [ ] **Step 1: Write failing tests for the missing contract**

Add tests that prove external executor truth can represent:
- a parent assignment spawning a child execution unit
- continuity metadata needed for resume/writeback
- restart/recovery metadata for a live runtime

Use or extend:
- `tests/state/test_executor_runtime_service.py`
- `tests/adapters/test_codex_app_server_adapter.py`
- `tests/kernel/test_main_brain_executor_runtime_integration.py`
- `tests/app/test_external_executor_live_smoke.py`

- [ ] **Step 2: Run the focused tests to confirm RED**

Run:
```powershell
python -m pytest tests/state/test_executor_runtime_service.py tests/adapters/test_codex_app_server_adapter.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/app/test_external_executor_live_smoke.py -q
```

Expected: failures showing missing child-run / continuity / recovery contract.

- [ ] **Step 3: Implement the minimal formal contract**

Add only the missing formal fields and port methods needed for cutover:
- child execution identity or parent-child linkage
- resume/checkpoint continuity metadata
- restart/recovery metadata exposed through executor runtime truth

Do this in:
- `src/copaw/kernel/executor_runtime_port.py`
- `src/copaw/state/models_executor_runtime.py`
- `src/copaw/state/executor_runtime_service.py`
- `src/copaw/kernel/runtime_coordination.py`

- [ ] **Step 4: Keep Codex adapter on the same contract**

Update:
- `src/copaw/adapters/executors/codex_app_server_adapter.py`

So the first formal adapter speaks the same child-run / continuity / recovery contract instead of silently dropping those fields.

- [ ] **Step 5: Re-run the focused tests to confirm GREEN**

Run:
```powershell
python -m pytest tests/state/test_executor_runtime_service.py tests/adapters/test_codex_app_server_adapter.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/app/test_external_executor_live_smoke.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```powershell
git add src/copaw/kernel/executor_runtime_port.py src/copaw/kernel/runtime_coordination.py src/copaw/state/models_executor_runtime.py src/copaw/state/executor_runtime_service.py src/copaw/adapters/executors/codex_app_server_adapter.py tests/state/test_executor_runtime_service.py tests/adapters/test_codex_app_server_adapter.py tests/kernel/test_main_brain_executor_runtime_integration.py tests/app/test_external_executor_live_smoke.py
git commit -m "feat: extend executor runtime for multi-agent continuity"
```

### Task 2: Cut Production Writers Off Actor Mailbox And Supervisor

**Files:**
- Modify: `src/copaw/kernel/delegation_service.py`
- Modify: `src/copaw/app/startup_recovery.py`
- Modify: `src/copaw/app/_app.py`
- Modify: `src/copaw/app/runtime_lifecycle.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_context.py`
- Modify: `src/copaw/industry/service_team_runtime.py`
- Modify: `src/copaw/industry/service_cleanup.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Test: `tests/app/test_runtime_center_task_delegation_api.py`
- Test: `tests/app/test_startup_recovery.py`
- Test: `tests/app/test_runtime_lifecycle.py`
- Test: `tests/app/test_industry_service_wiring.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/industry_api_parts/runtime_updates.py`
- Test: `tests/kernel/test_assignment_envelope.py`

- [ ] **Step 1: Write failing tests proving actor mailbox is still on the write path**

Add or tighten tests that fail if:
- `TaskDelegationService` still enqueues mailbox items
- startup recovery still needs actor mailbox for formal execution recovery
- industry lifecycle still enqueues mailbox work for formal execution
- industry runtime bootstrap/update paths still persist formal `AgentRuntimeRecord` / `AgentThreadBindingRecord`
- app startup/restart still re-injects actor runtime truth into `run_startup_recovery(...)`

- [ ] **Step 2: Run the focused writer-path tests to confirm RED**

Run:
```powershell
python -m pytest tests/app/test_runtime_center_task_delegation_api.py tests/app/test_startup_recovery.py tests/app/test_runtime_lifecycle.py tests/app/test_industry_service_wiring.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py tests/kernel/test_assignment_envelope.py -q
```

Expected: failures tied to actor mailbox / supervisor dependency.

- [ ] **Step 3: Move `delegation_service.py` from compatibility backend to deletable stub**

Change `src/copaw/kernel/delegation_service.py` so formal child-task execution no longer:
- enqueues actor mailbox items
- calls `run_agent_once(...)`
- depends on actor-owned checkpoints

If a compatibility shell must remain temporarily, it must fail closed for formal paths and route only through executor runtime truth.

- [ ] **Step 4: Remove actor mailbox writes from startup and industry lifecycle**

Change:
- `src/copaw/app/startup_recovery.py`
- `src/copaw/industry/service_lifecycle.py`
- `src/copaw/industry/service_context.py`
- `src/copaw/industry/service_team_runtime.py`
- `src/copaw/industry/service_cleanup.py`

So recovery, industry bootstrap, runtime updates, and retirement paths no longer write or recover formal execution through actor mailbox/runtime state.

- [ ] **Step 5: Remove leftover delegation wiring from query/bootstrap**

Change:
- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/app/runtime_bootstrap_domains.py`
- `src/copaw/app/runtime_service_graph.py`
- `src/copaw/app/_app.py`
- `src/copaw/app/runtime_lifecycle.py`

So formal runtime composition no longer threads delegation/actor execution as a hidden fallback.

- [ ] **Step 6: Re-run the focused tests to confirm GREEN**

Run:
```powershell
python -m pytest tests/app/test_runtime_center_task_delegation_api.py tests/app/test_startup_recovery.py tests/app/test_runtime_lifecycle.py tests/app/test_industry_service_wiring.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py tests/kernel/test_assignment_envelope.py -q
```

Expected: PASS

- [ ] **Step 7: Commit**

```powershell
git add src/copaw/kernel/delegation_service.py src/copaw/app/startup_recovery.py src/copaw/app/_app.py src/copaw/app/runtime_lifecycle.py src/copaw/industry/service_lifecycle.py src/copaw/industry/service_context.py src/copaw/industry/service_team_runtime.py src/copaw/industry/service_cleanup.py src/copaw/kernel/query_execution_runtime.py src/copaw/app/runtime_bootstrap_domains.py src/copaw/app/runtime_service_graph.py tests/app/test_runtime_center_task_delegation_api.py tests/app/test_startup_recovery.py tests/app/test_runtime_lifecycle.py tests/app/test_industry_service_wiring.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py tests/kernel/test_assignment_envelope.py
git commit -m "feat: cut formal execution off actor mailbox path"
```

### Task 3: Remove Actor Runtime Truth From Formal Read Surfaces

**Files:**
- Modify: `src/copaw/app/runtime_state_bindings.py`
- Modify: `src/copaw/app/routers/runtime_center_dependencies.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `src/copaw/app/routers/runtime_center_actor_capabilities.py`
- Modify: `src/copaw/kernel/agent_profile_service.py`
- Modify: `src/copaw/app/runtime_center/conversations.py`
- Modify: `src/copaw/kernel/query_execution_context_runtime.py`
- Modify: `src/copaw/kernel/query_execution_usage_runtime.py`
- Modify: `src/copaw/kernel/query_execution_resident_runtime.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `src/copaw/state/__init__.py`
- Modify: `src/copaw/state/repositories/__init__.py`
- Test: `tests/app/test_runtime_center_actor_api.py`
- Test: `tests/app/test_runtime_chat_thread_binding.py`
- Test: `tests/app/test_runtime_conversations_api.py`
- Test: `tests/kernel/test_query_usage_accounting.py`
- Test: `tests/industry/test_runtime_views_split.py`

- [ ] **Step 1: Write failing tests for stale actor read surfaces**

Add tests that fail if formal read surfaces still require:
- `agent_runtime_repository`
- `agent_mailbox_repository`
- `agent_checkpoint_repository`
- `agent_thread_binding_repository`

for executor-backed execution truth.

- [ ] **Step 2: Run the focused read-surface tests to confirm RED**

Run:
```powershell
python -m pytest tests/app/test_runtime_center_actor_api.py tests/app/test_runtime_chat_thread_binding.py tests/app/test_runtime_conversations_api.py tests/kernel/test_query_usage_accounting.py tests/industry/test_runtime_views_split.py -q
```

Expected: failures proving actor repositories are still formal dependencies.

- [ ] **Step 3: Replace formal readers with executor-runtime truth**

Update:
- `src/copaw/kernel/agent_profile_service.py`
- `src/copaw/app/runtime_center/conversations.py`
- `src/copaw/app/routers/runtime_center_routes_core.py`
- `src/copaw/app/routers/runtime_center_actor_capabilities.py`
- `src/copaw/kernel/query_execution_context_runtime.py`
- `src/copaw/kernel/query_execution_usage_runtime.py`
- `src/copaw/kernel/query_execution_resident_runtime.py`
- `src/copaw/industry/service_runtime_views.py`

So they read executor thread/runtime truth instead of actor runtime truth for formal execution.

- [ ] **Step 4: Shrink app state and dependency exports**

Update:
- `src/copaw/app/runtime_state_bindings.py`
- `src/copaw/app/routers/runtime_center_dependencies.py`
- `src/copaw/state/__init__.py`
- `src/copaw/state/repositories/__init__.py`

So actor repositories stop being exported as formal runtime state and dependency surface.

- [ ] **Step 5: Re-run the focused tests to confirm GREEN**

Run:
```powershell
python -m pytest tests/app/test_runtime_center_actor_api.py tests/app/test_runtime_chat_thread_binding.py tests/app/test_runtime_conversations_api.py tests/kernel/test_query_usage_accounting.py tests/industry/test_runtime_views_split.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```powershell
git add src/copaw/app/runtime_state_bindings.py src/copaw/app/routers/runtime_center_dependencies.py src/copaw/app/routers/runtime_center_routes_core.py src/copaw/app/routers/runtime_center_actor_capabilities.py src/copaw/kernel/agent_profile_service.py src/copaw/app/runtime_center/conversations.py src/copaw/kernel/query_execution_context_runtime.py src/copaw/kernel/query_execution_usage_runtime.py src/copaw/kernel/query_execution_resident_runtime.py src/copaw/industry/service_runtime_views.py src/copaw/state/__init__.py src/copaw/state/repositories/__init__.py tests/app/test_runtime_center_actor_api.py tests/app/test_runtime_chat_thread_binding.py tests/app/test_runtime_conversations_api.py tests/kernel/test_query_usage_accounting.py tests/industry/test_runtime_views_split.py
git commit -m "feat: move formal read surfaces off actor runtime truth"
```

### Task 4: Delete Actor Runtime State And Kernel

**Files:**
- Delete: `src/copaw/kernel/actor_mailbox.py`
- Delete: `src/copaw/kernel/actor_worker.py`
- Delete: `src/copaw/kernel/actor_supervisor.py`
- Delete: `src/copaw/state/models_agents_runtime.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_repositories.py`
- Modify: `src/copaw/app/runtime_center/recovery_projection.py`
- Modify: `src/copaw/state/repositories/sqlite_governance_agents.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/repositories/base.py`
- Modify: `src/copaw/state/repositories/sqlite_shared.py`
- Modify: `src/copaw/environments/service.py`
- Modify: `src/copaw/environments/lease_service.py`
- Modify: `src/copaw/kernel/__init__.py`
- Modify: `src/copaw/app/runtime_bootstrap_execution.py`
- Test: `tests/kernel/test_actor_mailbox.py`
- Test: `tests/kernel/test_actor_worker.py`
- Test: `tests/kernel/test_actor_supervisor.py`
- Test: `tests/state/test_models_module_exports.py`
- Test: `tests/state/test_sqlite_repositories.py`

- [ ] **Step 1: Write deletion-guard tests**

Add tests that prove:
- bootstrap no longer builds actor runtime objects even as compatibility
- kernel exports no longer expose actor runtime symbols
- actor runtime model import path is gone from formal state
- repository/export shims no longer import actor runtime records
- environment lease APIs no longer depend on `AgentLeaseRecord`
- interactive query runtime no longer acquires or heartbeats actor leases

- [ ] **Step 2: Run the actor retirement tests to confirm RED**

Run:
```powershell
python -m pytest tests/kernel/test_actor_mailbox.py tests/kernel/test_actor_worker.py tests/kernel/test_actor_supervisor.py tests/kernel/test_query_execution_runtime.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/app/test_startup_recovery.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/state/test_models_module_exports.py tests/state/test_sqlite_repositories.py -q
```

Expected: failures because actor files and exports still exist.

- [ ] **Step 3: Remove actor runtime construction and exports**

Change:
- `src/copaw/app/runtime_bootstrap_models.py`
- `src/copaw/app/runtime_bootstrap_repositories.py`
- `src/copaw/app/runtime_bootstrap_execution.py`
- `src/copaw/app/runtime_center/recovery_projection.py`
- `src/copaw/state/models.py`
- `src/copaw/state/repositories/base.py`
- `src/copaw/state/repositories/sqlite_shared.py`
- `src/copaw/state/repositories/__init__.py`
- `src/copaw/environments/service.py`
- `src/copaw/environments/lease_service.py`
- `src/copaw/kernel/query_execution_resident_runtime.py`
- `src/copaw/kernel/__init__.py`
- `src/copaw/state/repositories/sqlite_governance_agents.py`

Then delete:
- `src/copaw/kernel/actor_mailbox.py`
- `src/copaw/kernel/actor_worker.py`
- `src/copaw/kernel/actor_supervisor.py`
- `src/copaw/state/models_agents_runtime.py`

- [ ] **Step 4: Retire or rewrite actor-only tests**

Delete or replace:
- `tests/kernel/test_actor_mailbox.py`
- `tests/kernel/test_actor_worker.py`
- `tests/kernel/test_actor_supervisor.py`
- `tests/state/test_models_module_exports.py`
- actor-only portions of `tests/state/test_sqlite_repositories.py`

Do not keep stale “compatibility green” tests for code that no longer exists.

- [ ] **Step 5: Run the retirement-focused suite to confirm GREEN**

Run:
```powershell
python -m pytest tests/app/test_startup_recovery.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_execution_provider_wiring.py tests/app/test_runtime_workflow_patch_bootstrap_wiring.py tests/kernel/test_query_execution_runtime.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/state/test_models_module_exports.py tests/state/test_sqlite_repositories.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```powershell
git add src/copaw/app/runtime_bootstrap_models.py src/copaw/app/runtime_bootstrap_repositories.py src/copaw/app/runtime_bootstrap_execution.py src/copaw/app/runtime_center/recovery_projection.py src/copaw/state/models.py src/copaw/state/repositories/base.py src/copaw/state/repositories/sqlite_shared.py src/copaw/state/repositories/__init__.py src/copaw/state/repositories/sqlite_governance_agents.py src/copaw/kernel/query_execution_resident_runtime.py src/copaw/kernel/__init__.py src/copaw/environments/service.py src/copaw/environments/lease_service.py tests/app/test_startup_recovery.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_execution_provider_wiring.py tests/app/test_runtime_workflow_patch_bootstrap_wiring.py tests/kernel/test_query_execution_runtime.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/state/test_models_module_exports.py tests/state/test_sqlite_repositories.py
git rm src/copaw/kernel/actor_mailbox.py src/copaw/kernel/actor_worker.py src/copaw/kernel/actor_supervisor.py src/copaw/state/models_agents_runtime.py tests/kernel/test_actor_mailbox.py tests/kernel/test_actor_worker.py tests/kernel/test_actor_supervisor.py
git commit -m "feat: retire local actor runtime kernel"
```

### Task 5: Run End-To-End Acceptance And Sync Docs

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `DEPRECATION_LEDGER.md`
- Modify: `DATA_MODEL_DRAFT.md`
- Modify: `API_TRANSITION_MAP.md`

- [ ] **Step 1: Re-run focused executor + retirement regression**

Run:
```powershell
python -m pytest tests/kernel/test_main_brain_executor_runtime_integration.py tests/app/test_external_executor_live_smoke.py tests/app/test_runtime_center_task_delegation_api.py tests/app/test_startup_recovery.py tests/app/test_runtime_lifecycle.py tests/app/test_industry_service_wiring.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/industry_api_parts/runtime_updates.py tests/app/test_runtime_center_actor_api.py tests/app/test_runtime_chat_thread_binding.py tests/app/test_runtime_conversations_api.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_execution_provider_wiring.py tests/app/test_runtime_workflow_patch_bootstrap_wiring.py tests/industry/test_runtime_views_split.py tests/kernel/test_query_execution_runtime.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/kernel/test_query_usage_accounting.py tests/state/test_models_module_exports.py tests/state/test_sqlite_repositories.py -q
```

Expected: PASS

- [ ] **Step 2: Run full default gate**

Run:
```powershell
python scripts/run_p0_runtime_terminal_gate.py
```

Expected:
- backend mainline PASS
- long-run / deletion PASS
- frontend targeted regression PASS
- frontend build PASS

- [ ] **Step 3: Update architecture/status docs honestly**

Update:
- `TASK_STATUS.md`
- `DEPRECATION_LEDGER.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`

Record explicitly:
- external executor now owns formal multi-agent execution semantics
- local actor/delegation runtime is deleted
- any still-blocked browser/desktop/document replacement scope is outside this cutover

- [ ] **Step 4: Run final doc/worktree checks**

Run:
```powershell
git diff --check
git status -sb
```

Expected:
- no diff format errors
- only intended files changed

- [ ] **Step 5: Commit and push**

```powershell
git add TASK_STATUS.md DEPRECATION_LEDGER.md DATA_MODEL_DRAFT.md API_TRANSITION_MAP.md
git commit -m "feat: complete external executor multi-agent cutover"
git push origin main
```

- [ ] **Step 6: Final completion gate**

Run:
```powershell
git status -sb
git rev-list --left-right --count origin/main...main
```

Expected:
- clean worktree
- `0 0`
