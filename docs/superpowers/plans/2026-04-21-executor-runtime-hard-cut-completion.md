# Executor Runtime Hard-Cut Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish executor-runtime hard-cut `Task 2/3/6/7` so the remaining bridge, contract, Runtime Center, and verification gaps are closed with current evidence.

**Architecture:** Reuse the existing `ExecutorRuntimeService` and Codex adapter path, but finish the compatibility bridge on top of `ExternalCapabilityRuntimeService`, tighten executor-provider contract boundaries so donor/project install paths cannot masquerade as formal executor runtimes, and cut Runtime Center read surfaces over to executor-runtime-first while leaving actor-runtime endpoints in explicit compatibility mode only. Verification follows `UNIFIED_ACCEPTANCE_STANDARD.md`: focused regression first, then default regression, then selected `L3` smoke and `L4` soak.

**Tech Stack:** Python 3.12, FastAPI, SQLite state store, pytest, Runtime Center frontend, Codex App Server protocol shim

---

## Scope

- `Task 1`: verify still complete; do not reopen unless code or docs prove regression.
- `Task 2`: finish `models_external_runtime.py` / `external_runtime_service.py` bridge helpers.
- `Task 3`: finish executor-runtime contract cutover in:
  - `src/copaw/capabilities/external_adapter_execution.py`
  - `src/copaw/capabilities/external_runtime_execution.py`
  - `src/copaw/capabilities/project_donor_contracts.py`
- `Task 6`: finish executor-runtime-first Runtime Center read path and push actor runtime to explicit compatibility status.
- `Task 7`: produce fresh focused/default/L3/L4 evidence and update:
  - `TASK_STATUS.md`
  - `DEPRECATION_LEDGER.md`

## Guardrails

- No new parallel truth source for executor state.
- No new active path that routes arbitrary donor/project installs into formal executor-provider truth.
- Actor runtime compatibility routes may remain only if clearly no longer primary execution truth.
- Completion claims must state exact acceptance layer and remaining boundaries if any command cannot be run.

## 2026-04-21 Status Snapshot

- `Task 2`: still partial. `models_external_runtime.py` / `external_runtime_service.py` bridge helpers were not advanced in this closure slice.
- `Task 2`: additional partial closure now landed for delegation default-surface demotion:
  - execution-core baseline capability no longer exposes `system:delegate_task` by default
  - query runtime default system capability allowlist no longer auto-mounts `delegate_task` for execution-core turns
  - query prompt / capability projection / capability registry now describe `delegate_task` as a legacy compatibility path instead of a primary execution path
  - `TaskDelegationService` itself still exists and is not retired
- `Task 3`: partial overall, but actor-runtime demotion slice is now landed in the current worktree:
  - actor mutation and actor capability mutation routes were removed from `runtime_center_routes_actor.py`
  - actor payloads now advertise `read-only-compat`
  - RuntimeExecutionStrip / AgentWorkbench no longer expose actor pause/resume/cancel/retry controls
  - capability governance now uses the agent formal surface only
- `Task 6`: improved. Runtime Center / Agent Workbench actor surfaces now read as compatibility-only instead of looking canonical.
- donor/provider surface: additional partial closure now landed in the current worktree:
  - project donor contract metadata and projected package metadata now carry `compatibility/acquisition-only + formal_surface=false`
  - `/capability-market/projects/search` and `/projects/install*` responses now advertise the donor/project surface as compatibility-only instead of leaving it visually canonical
  - Runtime Center donor/package projection now carries the same compatibility marker and tolerates dict-backed service payloads
- `Task 7`: widened verification now exists for the current closure slices:
  - focused `L1 + L2` evidence still covers actor compatibility, delegation default-surface demotion, donor/provider surface demotion, and `console` build
  - `default regression` now passes through `python scripts/run_p0_runtime_terminal_gate.py`
  - selected `L3` smoke now passes for runtime front-door / Runtime Center readback
  - selected `L4` soak now passes for `3` repeated long-chain cycles across `phase_next_autonomy_smoke + runtime_canonical_flow_e2e + operator_runtime_e2e`

## 2026-04-21 Late Closure Update

- This plan is now historical and must not be treated as the latest state snapshot.
- Subsequent same-day closure landed the two previously open hard items:
  - formal assignment execution now short-circuits to executor runtime from `src/copaw/kernel/main_brain_orchestrator.py` instead of falling back to local `query_execution_service.execute_stream(...)`
  - `src/copaw/kernel/delegation_service.py` is no longer the primary assignment execution backend; it remains only as an explicit compatibility child-task path and now marks child-run metadata with `execution_source = delegation-compat`
  - formal provider inventory/intake now exists through:
    - `GET /capability-market/executor-providers/search`
    - `POST /capability-market/executor-providers/install`
  - Runtime Center state query and executor runtime repository now expose formal provider inventory read paths
- The latest truthful state lives in:
  - `TASK_STATUS.md` section `1.0.7`
  - `DEPRECATION_LEDGER.md` entries `3.1.4` and `3.1.5`

## Fresh Verification

- `python -m pytest tests/kernel/test_agent_profile_service.py tests/kernel/query_execution_environment_parts/lifecycle.py tests/kernel/query_execution_environment_parts/dispatch.py tests/kernel/test_assignment_envelope.py tests/app/test_capabilities_execution.py tests/app/test_runtime_center_task_delegation_api.py -q`
  - `130 passed in 88.04s`
  - Acceptance: `L1 + L2`

- `PYTHONPATH=src python -m pytest tests/app/test_runtime_center_actor_api.py -q`
  - `8 passed in 37.69s`
  - Acceptance: `L1 + L2`
- `PYTHONPATH=src python -m pytest tests/app/test_runtime_center_actor_api.py tests/app/test_runtime_center_external_runtime_api.py tests/app/test_runtime_center_executor_runtime_projection.py tests/app/test_runtime_center_executor_runtime_bootstrap.py -q`
  - `17 passed in 56.78s`
  - Acceptance: `L1 + L2`
- `npm --prefix console test -- src/components/RuntimeExecutionStrip.test.tsx src/components/RuntimeExecutionLauncher.test.tsx src/pages/AgentWorkbench/runtimePanels.test.tsx src/pages/AgentWorkbench/useAgentWorkbench.test.tsx src/pages/AgentWorkbench/index.test.tsx`
  - `13 passed`
  - Acceptance: `L1 + L2`
- `npm --prefix console run build`
  - passed
  - Acceptance: `L1 + L2`
- `PYTHONPATH=src python -m pytest tests/capabilities/test_project_donor_contracts.py tests/app/test_capability_market_api.py tests/app/test_runtime_center_events_api.py tests/app/test_runtime_center_external_runtime_api.py -q`
  - `96 passed in 77.54s`
  - Acceptance: `L1 + L2`
- `python -m pytest tests/app/test_industry_draft_generator.py -q -k "missing_chat_model_as_upstream_unavailable"`
  - `1 passed, 5 deselected in 4.21s`
  - Acceptance: `L1 + L2`
- `python -m pytest tests/app/industry_api_parts/runtime_updates.py -q -k "test_industry_preview_returns_service_unavailable_when_chat_model_missing or test_governance_blocks_dispatch_when_pending_staffing_proposal_is_not_top_active_gap or test_report_followup_backlog_wins_next_cycle_over_unrelated_open_backlog_when_handoff_and_staffing_are_live"`
  - `3 passed, 45 deselected in 28.56s`
  - Acceptance: `L1 + L2`
- `python scripts/run_p0_runtime_terminal_gate.py`
  - backend mainline regression: `361 passed in 238.94s`
  - long-run / retirement regression: `84 passed in 387.04s`
  - console targeted regression: `21 passed`
  - console build: passed
  - Acceptance: `L2`
- `PYTHONPATH=src python -m pytest tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q`
  - `16 passed in 94.23s`
  - Acceptance: `L3`
- `PYTHONPATH=src python -m pytest tests/app/test_phase_next_autonomy_smoke.py -q -k "runtime_center or runtime_center_overview or canonical_flow or operator or chat_run or long_run_smoke"`
  - `4 passed, 7 deselected in 36.45s`
  - Acceptance: `L3`
- `PYTHONPATH=src python -m pytest tests/app/test_phase_next_autonomy_smoke.py tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_operator_runtime_e2e.py -q`
  - repeated `3` times: `27 passed in 178.60s`, `27 passed in 176.46s`, `27 passed in 177.24s`
  - Acceptance: `selected L4`

## Remaining Boundaries

- `delegation_service.py` is no longer the formal assignment execution backend, but it still exists as an explicit compatibility capability/backend and has not been physically deleted.
- `delegate_task` is no longer a default execution-core surface, but it still exists as an explicit compatibility capability.
- formal `ExecutorProvider` intake is now landed, but donor/project compatibility surfaces and donor taxonomy retirement are still not physically deleted.
- selected `default regression`, `L3`, and `L4` evidence now exist for the `2026-04-21` closure slices, but this still does not prove full external-executor hard-cut completion.
- `live external-provider smoke` and full-repo soak remain unrun.
- This plan must not be cited as proof that the entire external-executor hard-cut is fully complete; use the newer status/deprecation docs for the latest boundary statement.
