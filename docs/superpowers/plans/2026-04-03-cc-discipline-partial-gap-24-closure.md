# CC Discipline Partial Gap 2/4 Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining verified partial gaps for repo-wide writer discipline adoption and query-runtime-native entropy contract projection without introducing a second runtime truth source.

**Architecture:** Keep `EnvironmentMount / SessionMount / EvidenceRecord` as the only execution/runtime truth chain. For gap `2`, harden the existing shared writer lease into the unified write front door for direct capability execution instead of creating a second write lock system. For gap `4`, formalize a typed runtime entropy contract from existing compaction/degradation facts and project it into checkpoints and Runtime Center without letting read models infer new truth.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite, pytest, existing CoPaw kernel/capabilities/environment/runtime services.

---

## Ownership

- Issue `2` owner:
  - `src/copaw/capabilities/execution.py`
  - `src/copaw/capabilities/execution_support.py`
  - `src/copaw/capabilities/service.py`
  - `src/copaw/capabilities/sources/tools.py`
  - `src/copaw/environments/surface_control_service.py`
  - `tests/app/test_capabilities_execution.py`
  - `tests/environments/test_cooperative_document_bridge.py`
  - `tests/environments/test_cooperative_browser_companion.py`
  - `tests/environments/test_cooperative_windows_apps.py`
- Issue `4` owner:
  - `src/copaw/kernel/query_execution_runtime.py`
  - `src/copaw/app/runtime_bootstrap_execution.py`
  - `src/copaw/app/runtime_center/overview_cards.py`
  - `tests/kernel/test_query_execution_runtime.py`
  - `tests/app/test_runtime_bootstrap_split.py`
  - `tests/app/test_operator_runtime_e2e.py`
- Shared/doc integration owner:
  - `docs/superpowers/plans/2026-04-03-cc-discipline-partial-gap-24-closure.md`
  - `TASK_STATUS.md`

## Scoped Status (`2026-04-03`, integrated closure)

- This worktree closes both verified partial gaps:
  - issue `2`: direct capability execution and live browser/document/windows surface actions now share the same writer-lease front-door discipline
  - issue `4`: query runtime now emits a canonical typed `runtime_entropy` contract, while `query_runtime_entropy` remains the compatibility projection of that same truth
- Runtime Center governance now treats `query_runtime_entropy` as the typed source of truth and only falls back to legacy `runtime_contract.sidecar_memory` when the typed contract is unavailable.
- `TASK_STATUS.md` is updated in this integration pass so repo-level status wording matches the code.

## Task 1: Repo-Wide Writer Gateway Adoption for Direct Capability Execution

**Files:**
- Modify: `src/copaw/capabilities/models.py`
- Modify: `src/copaw/capabilities/execution.py`
- Modify: `src/copaw/capabilities/service.py`
- Test: `tests/app/test_capabilities_execution.py`

- [x] **Step 1: Write the failing tests**

Add focused tests proving:
- direct write capabilities acquire and release a shared writer lease when mount policy declares a writer contract
- conflicting writer scope blocks execution before the tool runs
- read-only capabilities do not acquire writer leases

- [x] **Step 2: Run the targeted test command and verify RED**

Run: `set PYTHONPATH=src; python -m pytest tests/app/test_capabilities_execution.py -k "writer_lease or writer_scope or writer_contract" -q`

Expected: fail because direct capability execution does not yet use the shared writer lease front door.

- [x] **Step 3: Add typed writer contract support to capability execution**

Implement a mount-declared writer contract that:
- stays inside `execution_policy`
- uses existing `EnvironmentService.acquire/heartbeat/release_shared_writer_lease(...)`
- wraps direct capability execution with the same lease lifecycle discipline already used by child runs
- does not invent a second lock vocabulary

- [x] **Step 4: Re-run targeted tests and widen to capability regressions**

Run:
- `set PYTHONPATH=src; python -m pytest tests/app/test_capabilities_execution.py -q`

Observed:
- direct capability writer lease subset: `4 passed`
- full capability execution file: included in focused aggregate, green

## Task 2: Query-Runtime-Native Typed Entropy Contract + Projection

**Files:**
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `tests/app/test_operator_runtime_e2e.py`

- [x] **Step 1: Write the failing tests**

Add focused tests proving:
- query execution context now emits a typed runtime entropy contract even when the compaction sidecar is healthy
- sidecar-missing degradation is projected through the same typed entropy contract instead of staying as an unstructured partial hint
- Runtime Center governance meta surfaces the typed entropy contract

- [x] **Step 2: Run the targeted test command and verify RED**

Run: `set PYTHONPATH=src; python -m pytest tests/kernel/test_query_execution_runtime.py tests/app/test_operator_runtime_e2e.py -k "entropy or sidecar_memory_boundary" -q`

Expected: fail because runtime entropy is not yet a formal typed contract/projected payload.

- [x] **Step 3: Implement the typed entropy contract**

Add a canonical `runtime_entropy` payload derived from:
- current running config budgets
- compaction sidecar presence/health
- degradation/remediation facts already produced by query runtime

Wire it into:
- execution context / checkpoint metadata
- Runtime Center governance overview projection

Do not:
- create a second memory truth
- let overview/read models synthesize entropy truth on their own

- [x] **Step 4: Re-run targeted tests and widen to runtime/read-model regressions**

Run:
- `set PYTHONPATH=src; python -m pytest tests/kernel/test_query_execution_runtime.py tests/app/test_operator_runtime_e2e.py -q`

Observed:
- kernel/runtime entropy subset: `2 passed`
- runtime bootstrap entropy subset: `1 passed`
- operator runtime entropy projection subset: `1 passed`

## Task 3: Docs + Focused Aggregate Verification

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `docs/superpowers/plans/2026-04-03-cc-discipline-partial-gap-24-closure.md`

- [x] **Step 1: Update runtime status wording**

Record that:
- shared writer lease is now adopted by the direct capability execution front door
- query runtime now exposes a typed entropy contract instead of only partial degradation hints
- remaining boundaries, if any, are explicitly listed

Scoped status:
- [x] Recorded the integrated issue `2 / 4` closure boundary in this plan file.
- [x] Recorded that Runtime Center must mirror canonical `query_runtime_entropy` rather than synthesizing a projection-local shape.
- [x] Updated repo-level `TASK_STATUS.md` wording in the integration pass.

- [x] **Step 2: Run focused aggregate verification**

Run:
- `set PYTHONPATH=src; python -m pytest tests/app/test_capabilities_execution.py tests/kernel/test_query_execution_runtime.py tests/app/test_operator_runtime_e2e.py -q`

Observed: broader touched execution/runtime aggregate passed in widened regression below.

- [x] **Step 3: Run broader regression for touched execution/runtime surfaces**

Run:
- `set PYTHONPATH=src; python -m pytest tests/kernel/test_actor_worker.py tests/app/test_runtime_center_task_delegation_api.py tests/app/test_capabilities_execution.py tests/kernel/test_query_execution_runtime.py tests/app/test_operator_runtime_e2e.py -q`

Observed:
- `set PYTHONPATH=src; python -m pytest tests/app/test_capabilities_execution.py tests/environments/test_cooperative_document_bridge.py tests/environments/test_cooperative_browser_companion.py tests/environments/test_cooperative_windows_apps.py tests/kernel/test_query_execution_runtime.py tests/app/test_runtime_bootstrap_split.py tests/app/test_operator_runtime_e2e.py -q`
- Result: `107 passed`
