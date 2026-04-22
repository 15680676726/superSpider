# Local Executor Physical Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Physically retire CoPaw's remaining local execution brain so the formal execution path is external-executor-only, and explicitly separate deletable local-runtime remnants from still-unreplaced product surfaces.

**Architecture:** The retirement work splits into two different categories that must not be mixed. `actor + delegation` already have formal external-executor replacements and should be physically deleted from bootstrap, state bindings, capabilities, Runtime Center, and tests. `browser / desktop / document-file-shell` local execution still backs live product/API surfaces and therefore requires replacement product surfaces before physical deletion; until then, they remain explicit blockers rather than “quietly frozen” debt.

**Tech Stack:** Python 3.12, FastAPI, SQLite state store, pytest, Runtime Center, external executor runtime, Codex CLI sidecar

---

## Guardrails

- Stay on `main`; do not create branches or worktrees.
- Do not claim “local executor fully deleted” until `actor + delegation + local tool product surfaces` are all either physically removed or replaced by formal external-executor surfaces.
- Do not treat `frozen` / `read-only-compat` as completion.
- Do not delete browser/desktop/document runtime code while live product/API surfaces still depend on it.
- Completion claims must follow `UNIFIED_ACCEPTANCE_STANDARD.md` with explicit `L1 / L2 / L3 / L4`.

## Scope Split

### Delete Now

- `src/copaw/kernel/delegation_service.py`
- `src/copaw/kernel/actor_mailbox.py`
- `src/copaw/kernel/actor_worker.py`
- `src/copaw/kernel/actor_supervisor.py`
- actor/delegation exports, bootstrap fields, app state bindings, capability mounts, Runtime Center actor routes, and focused tests

### Blockers Before Delete

- `src/copaw/agents/tools/browser_control.py`
- `src/copaw/capabilities/browser_runtime.py`
- `src/copaw/agents/tools/desktop_actuation.py`
- `src/copaw/agents/tools/document_surface.py`
- `tool:execute_shell_command / tool:read_file / tool:write_file / tool:document_surface`
- browser-local Capability Market routes and other live local-runtime product/API surfaces

These remain follow-up work because the current external executor seam exposes `assignment/thread/turn/event`, not browser/desktop/document product surfaces.

## File Map

### Actor / Delegation Retirement

- `src/copaw/kernel/__init__.py`
- `src/copaw/kernel/delegation_service.py`
- `src/copaw/kernel/actor_mailbox.py`
- `src/copaw/kernel/actor_worker.py`
- `src/copaw/kernel/actor_supervisor.py`
- `src/copaw/capabilities/service.py`
- `src/copaw/capabilities/system_handlers.py`
- `src/copaw/capabilities/system_team_handlers.py`
- `src/copaw/capabilities/system_actor_handlers.py`
- `src/copaw/capabilities/sources/system.py`
- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/kernel/query_execution_tools.py`
- `src/copaw/kernel/query_execution_prompt.py`
- `src/copaw/app/runtime_bootstrap_execution.py`
- `src/copaw/app/runtime_bootstrap_domains.py`
- `src/copaw/app/runtime_bootstrap_models.py`
- `src/copaw/app/runtime_state_bindings.py`
- `src/copaw/app/runtime_service_graph.py`
- `src/copaw/app/_app.py`
- `src/copaw/app/startup_recovery.py`
- `src/copaw/app/routers/runtime_center.py`
- `src/copaw/app/routers/runtime_center_routes_actor.py`
- `src/copaw/app/routers/runtime_center_dependencies.py`
- `src/copaw/app/routers/runtime_center_payloads.py`
- `src/copaw/app/runtime_center/models.py`
- `src/copaw/app/runtime_center/overview_cards.py`
- `src/copaw/app/runtime_center/overview_main_brain.py`
- `src/copaw/kernel/main_brain_chat_service.py`

### Docs / Status

- `TASK_STATUS.md`
- `DEPRECATION_LEDGER.md`
- `DATA_MODEL_DRAFT.md`
- `API_TRANSITION_MAP.md`

## Test Map

- `tests/app/test_capabilities_execution.py`
- `tests/app/test_runtime_bootstrap_helpers.py`
- `tests/app/test_runtime_bootstrap_split.py`
- `tests/app/test_runtime_execution_provider_wiring.py`
- `tests/app/test_runtime_center_actor_api.py`
- `tests/app/test_runtime_center_task_delegation_api.py`
- `tests/kernel/test_assignment_envelope.py`
- `tests/kernel/test_actor_worker.py`
- `tests/kernel/test_actor_supervisor.py`
- `tests/kernel/test_main_brain_chat_service.py`
- `tests/kernel/test_query_execution_runtime.py`
- `tests/kernel/query_execution_environment_parts/dispatch.py`

## Tasks

### Task 1: Delete Delegation Compatibility From The Formal Runtime

- [x] Write failing tests that prove bootstrap, capability execution, and query tools no longer expose `system:delegate_task` or a `delegation_service`.
- [ ] Remove `TaskDelegationService` from kernel exports, capability handlers, bootstrap/domain builders, app state bindings, and query tool surfaces.
- [ ] Delete `src/copaw/kernel/delegation_service.py` and retire direct delegation-focused tests.
- [ ] Re-run the focused delegation/bootstrap regression and make it pass.
- Progress `2026-04-22`:
  - `capabilities/sources/system.py` 已停止注册 `system:delegate_task`
  - `query_execution_tools.py` 已物理删除 `delegate_task` tool builder
  - `query_execution_prompt.py` / `query_execution_runtime.py` 不再把 `system:delegate_task` 视为 formal query front-door 条件
  - `delegation_service.py` compatibility result 已停止输出已删除的 actor mailbox route
  - `delegation_service.py` 文件、kernel export 与 compatibility-focused tests 仍在，因此当前仍是 `partial`

  - `capabilities/service.py` no longer exposes a formal `set_delegation_service(...)` setter
  - `system_handlers.py` / `system_team_handlers.py` no longer keep a formal `system:delegate_task` dispatch branch
  - `capabilities/execution.py` no longer carries a `system:delegate_task`-only environment inheritance special case
  - `delegation_service.py` file and compatibility-focused tests still exist, so the task remains `partial`

### Task 2: Delete Actor Runtime Compatibility From Bootstrap And Runtime Center

- [x] Write failing tests that prove bootstrap/app state no longer expose actor services and Runtime Center no longer serves `/runtime-center/actors*`.
- [ ] Remove actor services from execution bootstrap, app lifecycle, Runtime Center read models, and main-brain actor-supervisor snapshots.
- [ ] Delete `actor_mailbox.py`, `actor_worker.py`, `actor_supervisor.py`, actor capability mounts, actor handlers, actor routes, and actor-focused tests.
- [ ] Re-run the focused actor/runtime-center regression and make it pass.
- Progress `2026-04-22`:
  - `runtime_center_routes_actor.py` / `runtime_center_shared_actor.py` 已物理删除
  - formal `kernel task / decision / agent capability` 路由已拆到 `runtime_center_routes_governance.py` / `runtime_center_routes_agents.py`
  - actor runtime payload 与 capability surface 已停止返回 `/api/runtime-center/actors/*` dead routes
  - `install_templates.py`、`runtime_center_payloads.py`、`system_actor_handlers.py` 也已停止输出 `/api/runtime-center/actors/*` dead links
  - `actor_mailbox.py` / `actor_worker.py` / `actor_supervisor.py` 与 overview/startup compatibility wiring 仍在，因此当前仍是 `partial`

  - `runtime_bootstrap_models.py` / `runtime_service_graph.py` no longer expose `actor_mailbox_service / actor_worker / actor_supervisor` on the formal bootstrap object
  - `_app.py` / `runtime_lifecycle.py` no longer thread actor mailbox or actor-supervisor lifecycle through the default app startup/restart path
  - `runtime_center_routes_agents.py` / `runtime_center_routes_governance.py` now carry the formal Runtime Center `agents + learning governance` routes needed by the default gate
  - `runtime_center/models.py` / `overview_cards.py` no longer fall back to `actor_worker / actor_supervisor.runtime_contract` for main-brain governance sidecar memory
  - `overview_main_brain.py` no longer reads `actor_supervisor_snapshot / actor_supervisor.snapshot()` to expose `exception_absorption` in the Runtime Center main-brain card
  - `capabilities/service.py` / `system_handlers.py` no longer keep a formal actor capability setter/dispatch surface; `system_actor_handlers.py` is physically deleted and prediction recommendations no longer emit `system:pause_actor`
  - `runtime_center/models.py` / `overview_cards.py` no longer expose `main_brain.automation.supervisor`; Runtime Center automation now reads only schedules, automation loops, and heartbeat
  - `main_brain_chat_service.py` no longer reads actor-supervisor exception-absorption snapshots into pure-chat prompt context
  - `query_execution_runtime.py` / `query_execution_context_runtime.py` now read and write formal execution checkpoints via `agent_checkpoint_repository`; `KernelQueryExecutionService` no longer exposes `set_actor_mailbox_service(...)`
  - `runtime_center_dependencies.py` no longer exposes `_get_actor_mailbox_service(...)` or `_get_actor_supervisor(...)` dead compatibility getters
  - `runtime_center_payloads.py` no longer exposes `_actor_mailbox_payload(...)` dead compatibility helper
  - `runtime_center_actor_capabilities.py` / `runtime_center_routes_agents.py` no longer keep the dead `require_actor` branch on the formal agent capability assignment surface
  - `runtime_bootstrap_domains.py` no longer accepts an `actor_supervisor` parameter, and `runtime_service_graph.py` no longer threads that value through default bootstrap
  - `_app.py` / `runtime_lifecycle.py` no longer pass `actor_mailbox_service=None` or `exception_absorption_service=None` into `run_startup_recovery(...)` on the default startup/restart path
  - `actor_mailbox.py` / `actor_worker.py` / `actor_supervisor.py` files still exist, so the task remains `partial`

### Task 3: Re-state The Remaining Local-Tool Blockers Honestly

- [ ] Update docs/status so browser/desktop/document-file-shell local paths are explicitly recorded as still-blocked product-surface replacements, not “done later maybe”.
- [ ] Record the exact missing replacement surfaces required before physical deletion.

### Task 4: Verify And Close

- [x] Run focused regression for delegation/actor retirement.
- [x] Run default regression if the focused slice is green.
- [x] Update docs with exact `L1 / L2 / L3 / L4` evidence and remaining blocker boundaries.
- [ ] Commit and push to `origin/main`.
- Focused regression `2026-04-22`:
  - `python -m pytest tests/app/test_capabilities_execution.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_center_actor_api.py tests/kernel/query_execution_environment_parts/dispatch.py tests/kernel/test_agent_profile_service.py tests/kernel/test_query_execution_runtime.py -q`
  - `178 passed in 101.15s`
- Focused regression `2026-04-22` gate-repair slice:
  - `python -m pytest tests/app/test_runtime_center_api.py tests/app/test_learning_api.py tests/app/test_operator_runtime_e2e.py tests/app/test_runtime_center_actor_api.py tests/app/runtime_center_api_parts/detail_environment.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_bootstrap_helpers.py tests/app/test_runtime_bootstrap_split.py tests/app/test_runtime_lifecycle.py -q`
  - `346 passed in 180.25s`
- Default regression `2026-04-22`:
  - `python scripts/run_p0_runtime_terminal_gate.py`
  - backend mainline `361 passed in 266.07s`
  - long-run / deletion regression `84 passed in 427.67s`
  - `cmd /c npm --prefix console run test -- src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx src/components/RuntimeExecutionStrip.test.tsx src/pages/Predictions/index.test.ts src/pages/Knowledge/index.test.tsx`
  - frontend targeted regression passed, `21 passed`
  - `cmd /c npm --prefix console run build`
  - frontend build passed
