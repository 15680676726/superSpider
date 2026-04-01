# Claude Runtime Contract Hardening P1-P2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Claude-derived runtime contract hardening by first deleting leftover `P0` compatibility/duplicate logic, then hardening MCP runtime, task/worker execution shells, diagnostics, and capability metadata/package binding without creating a second execution center.

**Architecture:** This plan keeps CoPaw's upper truth and main-brain chain intact. `P1/P2` work only tightens lower execution contracts and deletes compatibility paths once the new contract is live. Conditional extractions such as `task_state_machine.py` or `turn_loop.py` are explicitly out-of-scope unless implementation proves they remove real duplication.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite, pytest, existing CoPaw kernel/capabilities/runtime services.

---

## Scope Guard

This plan covers only:

- `src/copaw/app/mcp/manager.py`
- `src/copaw/app/runtime_service_graph.py`
- `src/copaw/app/runtime_lifecycle.py`
- `src/copaw/app/runtime_bootstrap_execution.py`
- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/kernel/query_execution_resident_runtime.py`
- `src/copaw/kernel/query_execution_usage_runtime.py`
- `src/copaw/kernel/actor_worker.py`
- `src/copaw/kernel/actor_supervisor.py`
- `src/copaw/kernel/delegation_service.py`
- `src/copaw/kernel/lifecycle.py`
- `src/copaw/kernel/turn_executor.py`
- `src/copaw/app/runtime_host.py`
- `src/copaw/app/runtime_center/overview_governance.py`
- `src/copaw/kernel/query_execution_tools.py`
- `src/copaw/capabilities/models.py`
- `src/copaw/capabilities/skill_service.py`
- `src/copaw/capabilities/catalog.py`
- `src/copaw/capabilities/service.py`
- `src/copaw/capabilities/mcp_registry.py`
- related tests and status/docs updates

This plan does **not** cover:

- `MainBrainOrchestrator` redesign
- `/runtime-center/chat/run` redesign
- Runtime Center UI redesign
- truth-first memory redesign
- mandatory `task_state_machine.py`
- mandatory `turn_loop.py`

## File Map

### New files

- `src/copaw/app/mcp/runtime_contract.py`
  - Typed MCP runtime client/outcome/diagnostic contract.
- `tests/app/test_mcp_runtime_contract.py`
  - MCP runtime hardening contract tests.
- `tests/kernel/test_execution_diagnostics.py`
  - Diagnostics projection tests.

### Existing files to modify

- `src/copaw/kernel/query_execution_runtime.py`
  - Delete `P0` leftover compatibility setters/aliases and adopt hardened lifecycle/diagnostic contracts.
- `src/copaw/kernel/query_execution_resident_runtime.py`
  - Harden assignment/runtime shell behavior and shared terminal semantics.
- `src/copaw/kernel/query_execution_usage_runtime.py`
  - Remove legacy provider fallback drift and align usage reporting with execution run context.
- `src/copaw/app/mcp/manager.py`
  - Adopt typed MCP runtime contract and richer diagnostics.
- `src/copaw/app/runtime_service_graph.py`
  - Wire new MCP runtime contract and delete stale bootstrap duplication.
- `src/copaw/app/runtime_lifecycle.py`
  - Align watcher reload/hot-swap with new runtime contract.
- `src/copaw/app/runtime_bootstrap_execution.py`
  - Share one runtime admission/execution launch contract across runtime entrypoints.
- `src/copaw/kernel/actor_worker.py`
  - Adopt hardened worker lifecycle and terminal taxonomy.
- `src/copaw/kernel/actor_supervisor.py`
  - Surface worker lifecycle state and cleanup results.
- `src/copaw/kernel/delegation_service.py`
  - Adopt hardened child-run/result envelope and delete duplicate cleanup logic.
- `src/copaw/kernel/lifecycle.py`
  - Only extract helpers if they remove real duplication without changing vocabulary.
- `src/copaw/capabilities/models.py`
  - Formalize skill/package metadata on `CapabilityMount`.
- `src/copaw/capabilities/skill_service.py`
  - Bind skills/packages to formal metadata, not loose legacy assumptions.
- `src/copaw/capabilities/mcp_registry.py`
  - Reuse formal package binding fields instead of bespoke package refs.
- `TASK_STATUS.md`
  - Mark `P1/P2` closure and explicit deletion of old paths.
- `API_TRANSITION_MAP.md`
  - Record new runtime contract surfaces and retired compatibility paths.
- `docs/superpowers/specs/2026-04-01-claude-runtime-contract-hardening-design.md`
  - Update landed shape once green.

## Task 1: Retire Safe Lower-Layer `P0` Compatibility Paths

**Files:**
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/kernel/query_execution_usage_runtime.py`
- Test: `tests/kernel/test_turn_executor.py`
- Test: `tests/kernel/test_query_usage_accounting.py`
- Test: `tests/test_memory_compaction_hook.py`

- [ ] **Step 1: Write failing tests for deleted lower-layer compatibility paths**
- [ ] **Step 2: Run the targeted tests to verify drift/failure**
- [ ] **Step 3: Remove `set_memory_manager` aliasing from `query_execution_runtime.py` where the canonical object is already `ConversationCompactionService`**
- [ ] **Step 4: Replace legacy provider fallback drift in `query_execution_usage_runtime.py` with injected/provider-resolved behavior**
- [ ] **Step 5: Run targeted tests and fix callers**
- [ ] **Step 6: Commit**

## Task 2: Harden MCP Runtime Contract

**Files:**
- Create: `src/copaw/app/mcp/runtime_contract.py`
- Modify: `src/copaw/app/mcp/manager.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_lifecycle.py`
- Modify: `src/copaw/app/runtime_bootstrap_execution.py`
- Test: `tests/app/test_mcp_runtime_contract.py`
- Test: `tests/test_mcp_resilience.py`
- Test: `tests/app/test_runtime_bootstrap_helpers.py`

- [ ] **Step 1: Write failing MCP contract tests covering client status, connect timeout, auth/session/cache/error policy, replace/remove diagnostics, and closeout**
- [ ] **Step 2: Run MCP tests to verify the new contract is missing**
- [ ] **Step 3: Add typed MCP runtime client/result/diagnostic models**
- [ ] **Step 4: Refactor `MCPClientManager` and bootstrap/lifecycle callers to use the typed contract**
- [ ] **Step 5: Delete duplicate raw-dict rebuild/diagnostic handling once the typed contract is live**
- [ ] **Step 6: Run MCP/bootstrap regression tests**
- [ ] **Step 7: Commit**

## Task 3: Harden Task Interpretation and Assignment/Worker Lifecycle

**Files:**
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/kernel/query_execution_resident_runtime.py`
- Modify: `src/copaw/kernel/actor_worker.py`
- Modify: `src/copaw/kernel/actor_supervisor.py`
- Modify: `src/copaw/kernel/delegation_service.py`
- Modify: `src/copaw/kernel/lifecycle.py`
- Test: `tests/kernel/test_actor_worker.py`
- Test: `tests/app/test_runtime_center_task_delegation_api.py`
- Test: `tests/kernel/test_query_execution_runtime.py`

- [ ] **Step 1: Write failing tests for task interpretation, delegated child-run envelope, and assignment execution cleanup**
- [ ] **Step 2: Run worker/delegation/runtime tests to verify the shell is not shared yet**
- [ ] **Step 3: Tighten task interpretation and assignment execution envelopes in-place without changing `KernelTask.phase` vocabulary**
- [ ] **Step 4: Only extract a shared helper if in-place refactor proves real duplication**
- [ ] **Step 5: Delete duplicate terminal/cleanup/result-envelope logic from individual callers**
- [ ] **Step 6: Run worker/runtime/delegation regression tests**
- [ ] **Step 7: Commit**

## Task 4: Add Richer Execution Diagnostics

**Files:**
- Modify: `src/copaw/kernel/runtime_outcome.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `src/copaw/app/runtime_center/overview_governance.py`
- Test: `tests/kernel/test_execution_diagnostics.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`
- Test: `tests/app/test_operator_runtime_e2e.py`

- [ ] **Step 1: Write failing diagnostics tests for normalized failure source, blocked-next-step hints, and operator-visible remediation summaries**
- [ ] **Step 2: Run diagnostics tests to verify gaps**
- [ ] **Step 3: Harden diagnostics shaping in-place and extract a helper only if it clearly deletes duplication**
- [ ] **Step 4: Delete duplicate summary shaping once the shared path is live**
- [ ] **Step 5: Run diagnostics/operator regressions**
- [ ] **Step 6: Commit**

## Task 5: Harden Worker/Subagent Shell

**Files:**
- Modify: `src/copaw/kernel/actor_worker.py`
- Modify: `src/copaw/kernel/actor_supervisor.py`
- Modify: `src/copaw/kernel/delegation_service.py`
- Modify: `src/copaw/kernel/query_execution_tools.py`
- Test: `tests/kernel/test_actor_worker.py`
- Test: `tests/app/test_runtime_center_task_delegation_api.py`

- [ ] **Step 1: Write failing tests for long-lived worker/subagent run ownership, interruption, and terminal cleanup**
- [ ] **Step 2: Run worker/subagent tests to verify shell hardening is incomplete**
- [ ] **Step 3: Tighten worker/subagent run ownership and interruption semantics on top of the `P1` lifecycle contract**
- [ ] **Step 4: Delete residual per-caller worker cleanup branches**
- [ ] **Step 5: Run worker/subagent regressions**
- [ ] **Step 6: Commit**

## Task 6: Formalize Skill Metadata and Package Binding

**Files:**
- Modify: `src/copaw/capabilities/models.py`
- Modify: `src/copaw/capabilities/skill_service.py`
- Modify: `src/copaw/capabilities/catalog.py`
- Modify: `src/copaw/capabilities/service.py`
- Modify: `src/copaw/capabilities/mcp_registry.py`
- Test: `tests/app/test_capability_catalog.py`
- Test: `tests/app/test_capability_skill_service.py`
- Test: `tests/app/test_capability_market_api.py`
- Test: `tests/app/test_capabilities_execution.py`

- [ ] **Step 1: Write failing tests for formal `package_ref/package_kind/package_version` metadata on skill and remote-MCP mounts**
- [ ] **Step 2: Run capability tests to verify metadata is still informal**
- [ ] **Step 3: Extend `CapabilityMount` and skill/package producers to emit formal metadata**
- [ ] **Step 4: Add one formal package-binding write/read path in capability services instead of leaving binding as ad hoc fields only**
- [ ] **Step 5: Refactor catalog/execution/registry consumers to use the formal fields**
- [ ] **Step 6: Delete bespoke package-ref shaping once the formal fields are live**
- [ ] **Step 7: Run capability/market regressions**
- [ ] **Step 8: Commit**

## Task 7: Sidecar Memory Boundary and Stronger Autonomy Degradation

**Files:**
- Modify: `src/copaw/kernel/runtime_outcome.py`
- Modify: `src/copaw/kernel/turn_executor.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/app/runtime_center/overview_governance.py`
- Modify: `src/copaw/app/runtime_bootstrap_execution.py`
- Test: `tests/app/test_phase_next_autonomy_smoke.py`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `tests/app/test_operator_runtime_e2e.py`

- [ ] **Step 1: Write failing tests for normalized degraded execution decisions, sidecar-memory boundary handling, and stronger operator-visible degradation strategies**
- [ ] **Step 2: Run autonomy/runtime tests to verify the strategy is still fragmented**
- [ ] **Step 3: Implement shared degradation/remediation selection and sidecar-memory boundary handling on top of the hardened outcome contract**
- [ ] **Step 4: Delete residual ad hoc degraded-summary branches**
- [ ] **Step 5: Run autonomy/operator regressions**
- [ ] **Step 6: Commit**

## Task 8: Conditional Extraction Audit

**Files:**
- Modify: `docs/superpowers/specs/2026-04-01-claude-runtime-contract-hardening-design.md`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Audit whether `task_state_machine.py` extraction removes real duplication**
- [ ] **Step 2: Audit whether `turn_loop.py` extraction removes real orchestration duplication**
- [ ] **Step 3: If neither clears the bar, record explicit non-extraction rationale and delete-noise rationale in docs**
- [ ] **Step 4: If one clears the bar, add a narrow follow-up task and retire duplicated code in the same commit**
- [ ] **Step 5: Commit**

## Task 9: Docs, Status, and Full Regression

**Files:**
- Modify: `docs/superpowers/specs/2026-04-01-claude-runtime-contract-hardening-design.md`
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`

- [ ] **Step 1: Update landed shape and delete-old notes once all code is green**
- [ ] **Step 2: Run focused full regression for `P1/P2` scope**
- [ ] **Step 3: Run build/contract checks if frontend surfaces changed indirectly**
- [ ] **Step 4: Commit**
