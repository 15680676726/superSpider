# CC Runtime Donor Gap Closure Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. This plan is a new follow-up program. It does not reopen the historical `2026-04-01 P0 / P1 / P2` wave.

**Goal:** Close the real remaining `cc`-derived runtime-discipline gaps that still block CoPaw from having a smaller, harder, more operator-visible execution shell, without replacing CoPaw's formal truth chain or product center.

**Architecture:** Keep `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport` as the only formal planning truth. Keep `MainBrainOrchestrator` and `KernelTurnExecutor` as the only main execution front. This plan only hardens the lower execution/runtime/diagnostic shell and graph-fed planning inputs.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite, pytest, existing CoPaw kernel/capabilities/runtime services.

---

## Boundary

This plan is for:

- first-party query-turn discipline below the existing front-door
- explicit tool orchestration and typed capability request/result envelopes
- status mapping and idempotent terminal closeout across worker/runtime/mailbox layers
- MCP/skill/runtime projection into capability/read-model/governance surfaces
- graph-fed planning follow-up that moves from `top_entities/top_opinions` toward relation-aware planner inputs
- Runtime Center diagnostic depth and operator-visible provenance

This plan is not for:

- replacing CoPaw's formal planning truth
- adding a second orchestration center
- copying `cc` session/app-state/product shell
- replacing truth-first memory with `memdir` or session notes

---

## Verified Gap Matrix

1. first-party query loop discipline is still weak
2. tool orchestration layer is still missing
3. capability request/result typing is still too soft
4. task/runtime/mailbox/agent status mapping is still too scattered
5. MCP runtime projection into capability/read-model/governance is still incomplete
6. skill metadata/package discipline is only partially hardened
7. graph-backed planning is not yet relation-driven planning
8. Runtime Center diagnostics still lack delta/provenance/drilldown depth

## Landed Slice (`2026-04-03`)

The first donor-gap hardening slice is now real code, not just audit language:

- `Workstream A` landed a minimal orchestration shell in `src/copaw/capabilities/execution.py`:
  - contiguous `parallel-read` batches now execute before `serial-write` batches
  - shell capability classification is now payload-sensitive instead of permanently forced to `write`
  - tool-bridge evidence now carries execution-contract metadata (`action_mode / read_only / concurrency_class / preflight_policy / tool_contract`)
  - tool-bridge shell evidence now preserves `blocked` instead of collapsing it to generic `failed`
- `Workstream B` landed terminal idempotence on the canonical dispatcher/lifecycle path:
  - repeated `fail_task(...)` / `cancel_task(...)` no longer append duplicate evidence or rerun terminal side effects
- `Workstream D` landed the first canonical recovery-drilldown fix:
  - `/runtime-center/recovery/latest` now prefers `app.state.latest_recovery_report`
  - Runtime Center main-brain recovery card now reads the same canonical latest-recovery source instead of being startup-only
- `Workstream C` also landed a harder package-identity rule for filesystem-backed skills:
  - skill package metadata now re-anchors filesystem `package_ref` to the resolved skill root instead of trusting escaped frontmatter paths as package identity
- `Workstream D` recovery projection is now deeper than summary-only:
  - `/runtime-center/recovery/latest` and main-brain recovery payloads now expose `source` plus structured `detail` buckets for `leases / mailbox / decisions / automation`

Focused verification already green:

- `python -m pytest tests/capabilities/test_execution_context.py::test_execution_context_carries_contract_fields tests/app/test_capabilities_execution.py::test_execute_task_batch_runs_parallel_reads_before_serial_write tests/app/test_capabilities_execution.py::test_shell_execution_writes_evidence_via_unified_contract tests/app/test_capabilities_execution.py::test_shell_execution_blocked_status_propagates_to_tool_bridge_evidence tests/app/test_capabilities_execution.py::test_shell_execution_tool_bridge_evidence_carries_execution_contract_metadata tests/kernel/test_kernel.py::TestKernelDispatcher::test_fail_task_is_idempotent_for_terminal_task tests/kernel/test_kernel.py::TestKernelDispatcher::test_cancel_task_is_idempotent_for_terminal_task tests/app/test_runtime_center_events_api.py::test_runtime_center_recovery_latest_endpoint_returns_summary tests/app/test_runtime_center_events_api.py::test_runtime_center_recovery_latest_endpoint_prefers_canonical_latest_report tests/app/runtime_center_api_parts/overview_governance.py::test_runtime_center_main_brain_route_exposes_unified_operator_sections tests/app/runtime_center_api_parts/overview_governance.py::test_runtime_center_main_brain_route_prefers_canonical_latest_recovery_report -q`
  - result: `11 passed`

Remaining real boundary after this landed slice:

- query-side capability delegation is now landed for built-in `tool:*`, and the wrapped builtin path now has end-to-end boundary coverage across delegate-builder -> toolkit wrapper -> capability execution submission, including preflight ordering and delegate-fallback behavior
- skill metadata/package discipline is now re-anchored for filesystem-backed skills, but skill/MCP/runtime projection into the main capability/read-model/governance surfaces is still not fully landed
- relation propagation, governance explain, recovery source/detail drilldown, visible execution-phase projection, capability governance projection, and capability-gap degraded drilldown are landed for this donor slice

## Audit Refinement (`2026-04-03`)

Deep `cc -> CoPaw` audit across execution, task shell, MCP/skill/bridge, memory/planning, and Runtime Center diagnostics now narrows the remaining real gaps more precisely:

- `Workstream A` is no longer blocked on the direct capability path.
  - The direct capability execution shell now has payload-sensitive shell classification, `parallel-read -> serial-write` batching, and tool-bridge metadata parity.
  - The remaining execution gap is no longer raw tool mounting; it is the absence of full end-to-end boundary tests around the delegated `query/chat` tool front-door under the existing `ToolExecutionContract` / orchestration contract.
- `Workstream B` is now partially landed, not open-ended.
  - Shared status normalization now exists as `src/copaw/kernel/task_execution_projection.py`, with coverage in `tests/kernel/test_task_execution_projection.py` and `tests/kernel/test_actor_mailbox.py`.
  - The remaining gap is adapter cleanup and terminal closeout discipline at the runtime/query boundary, not inventing a new status vocabulary.
- `Workstream C` has shifted.
  - MCP typed lifecycle/runtime projection and bridge lifecycle ops are no longer the main donor gap.
  - Filesystem-backed skill package identity is now stricter: `package_ref` is re-anchored to the resolved skill root during read/write binding.
  - The remaining donor value is getting that hardened skill/MCP/runtime metadata fully projected into the main capability/read-model/governance surfaces, plus selected MCP transport/auth/cache/reconnect hardening.
  - `cc` bridge/session-first runtime must still not be transplanted as a second truth shell.
- `Workstream D` remains materially open.
  - Canonical `governance provenance explain` and recovery `source/detail` drilldown are now real code.
  - The remaining Runtime Center gap is full `delta diagnostics` plus deeper `degraded component drilldown`, not summary-only recovery/governance payload shaping.
- `Workstream E` is now materially landed for the donor gap tracked here.
  - Relation-aware cycle ranking is real code and green.
  - Relation propagation now reaches `strategy_constraints -> report_synthesis -> report_closure/follow-up continuity`; broader planner/read-surface evolution, if reopened later, should be treated as a separate follow-up rather than this donor slice staying open-ended.

Latest landed fixes in this refinement:

- blocked shell evidence no longer writes a replay pointer for policy-denied commands
- dispatcher no longer appends a duplicate `kernel.failed` evidence record when tool-bridge already emitted canonical failure/blocked evidence
- cycle planner now consumes relation focus/evidence as a real tie-breaker and projects typed `affected_relation_ids / affected_relation_kinds`
- activation strategy resolution now uses the current `resolve_strategy_payload(...)` contract instead of the stale `fallback_payload` call shape
- query/chat wrapped built-in tools now apply the same typed `ToolExecutionContract` validation used by the direct capability front-door
- query/chat tool-bridge evidence sinks now enrich shell/file/browser events with the same `tool_contract / action_mode / read_only / concurrency_class / preflight_policy` metadata family used by `CapabilityExecutionFacade`
- governance status now exposes structured `decision_provenance` explain payloads, and Runtime Center main-brain governance surface now carries that explain summary instead of showing only a flat pending count
- query/chat built-in `tool:*` functions can now delegate through a bound capability front-door instead of always calling raw local tools directly
- activation relation outputs now flow into `PlanningStrategyConstraints.graph_focus_relations / graph_relation_evidence`, report synthesis activation payloads, and materialized follow-up assignment metadata
- Runtime Center task list projection now uses the shared visible execution-phase resolver instead of leaking raw runtime-only statuses like `active`
- filesystem-backed skill package bindings now canonicalize/re-anchor `package_ref` to the resolved skill root on bind/read, preventing escaped frontmatter paths from becoming package identity
- recovery latest/main-brain payloads now carry `source` plus structured `detail` drilldown for `leases / mailbox / decisions / automation`, rather than only summary-level recovery counters
- query/chat wrapped builtin tools now have boundary coverage for delegate-builder -> wrapper -> capability execution, and delegate failures now fall back to the builtin tool path instead of tearing down the query turn
- Runtime Center main-brain governance now projects capability governance into the primary operator read surface, including `skill / MCP / package-bound` counts plus `delta` and `degraded_components` drilldown sourced from existing capability/prediction truth

Latest focused verification:

- `python -m pytest tests/app/test_capabilities_execution.py -k "read_only_shell or blocked_status_propagates or tool_bridge_evidence_carries or blocked_shell_execution_preserves or execute_task_batch" -q`
  - result: `4 passed`
- `python -m pytest tests/compiler/test_cycle_planner.py tests/compiler/test_report_replan_engine.py -k "relation" -q`
  - result: `2 passed`
- `python -m pytest tests/kernel/test_kernel.py -k "idempotent or execution_core_task_records_growth_and_experience" -q`
  - result: `3 passed`
- `python -m pytest tests/kernel/test_task_execution_projection.py tests/kernel/test_actor_mailbox.py -q`
  - result: `5 passed`
- `python -m pytest tests/app/test_runtime_center_events_api.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_mcp_runtime_contract.py tests/app/test_capability_catalog.py tests/app/test_capability_skill_service.py tests/memory/test_activation_service.py tests/compiler/test_cycle_planner.py tests/compiler/test_report_replan_engine.py tests/app/test_capabilities_execution.py tests/kernel/test_tool_bridge.py tests/capabilities/test_execution_context.py -q`
  - result: `166 passed`
- `python -m pytest tests/kernel/test_query_execution_runtime.py tests/kernel/test_governance.py -k "wrapped_builtin_tool_applies_unified_tool_contract_validation or evidence_sinks_attach_tool_contract_metadata or decision_provenance" -q`
  - result: `3 passed`
- `python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -k "unified_operator_sections or canonical_latest_recovery_report" -q`
  - result: `2 passed`
- `python -m pytest tests/agents/test_react_agent_tool_compat.py tests/kernel/test_query_execution_runtime.py -k "frontdoor or unified_tool_contract_validation or evidence_sinks_attach_tool_contract_metadata" -q`
  - result: `4 passed`
- `python -m pytest tests/app/industry_api_parts/bootstrap_lifecycle.py -k "graph_focus_into_formal_planning_sidecar or activation_followup" -q`
  - result: `3 passed`
- `python -m pytest tests/industry/test_report_synthesis.py tests/compiler/test_report_replan_engine.py -k "relation" -q`
  - result: `2 passed`
- `python -m pytest tests/kernel/test_task_execution_projection.py tests/app/test_runtime_query_services.py -k "projector or visible_execution_phase" -q`
  - result: `6 passed`
- `python -m pytest tests/agents/test_react_agent_tool_compat.py tests/kernel/test_query_execution_runtime.py -k "frontdoor or preflight or fallback or end_to_end or entropy_budget" -q`
  - result: `6 passed`
- `python -m pytest tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_center_events_api.py tests/app/test_runtime_query_services.py -q`
  - result: `75 passed`
- `python -m pytest tests/app/test_capability_skill_service.py tests/app/test_capabilities_execution.py tests/kernel/test_tool_bridge.py tests/capabilities/test_execution_context.py tests/industry/test_report_synthesis.py -k "relation_activation or relation or tool_bridge or execution_context or capability_skill_service or capabilities_execution" -q`
  - result: `54 passed`
- `python -m pytest tests/app/test_runtime_center_events_api.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_mcp_runtime_contract.py tests/app/test_capability_catalog.py tests/app/test_capability_skill_service.py tests/memory/test_activation_service.py tests/compiler/test_cycle_planner.py tests/compiler/test_report_replan_engine.py tests/app/test_capabilities_execution.py tests/kernel/test_tool_bridge.py tests/capabilities/test_execution_context.py tests/kernel/test_query_execution_runtime.py tests/kernel/test_governance.py -q`
  - result: `187 passed`

---

## Workstream A: Query-Turn Contract + Tool Orchestration

**Files:**
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/kernel/query_execution.py`
- Modify: `src/copaw/capabilities/execution.py`
- Modify: `src/copaw/capabilities/models.py`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `tests/app/test_capabilities_execution.py`

- [ ] Step 1: add failing tests for explicit turn-step state, typed capability result envelopes, and read-vs-write orchestration behavior
- [ ] Step 2: add a first-party internal turn-step contract under the existing query runtime instead of introducing a second top-level loop
- [ ] Step 3: add explicit tool orchestration batches with read-parallel / write-serialized behavior
- [ ] Step 4: replace signature-filter-only execution shaping with typed request/result envelopes while preserving current public capability ids
- [ ] Step 5: run focused query/capability regressions

## Workstream B: Status Mapping + Idempotent Terminal Closeout

**Files:**
- Modify: `src/copaw/kernel/runtime_outcome.py`
- Modify: `src/copaw/kernel/actor_worker.py`
- Modify: `src/copaw/kernel/actor_supervisor.py`
- Modify: `src/copaw/kernel/delegation_service.py`
- Modify: `src/copaw/state/main_brain_service.py`
- Test: `tests/kernel/test_actor_worker.py`
- Test: `tests/kernel/test_actor_supervisor.py`
- Test: `tests/app/test_runtime_center_task_delegation_api.py`

- [ ] Step 1: add failing tests for explicit status mapping, terminal idempotence, and delegated child-run closeout reuse
- [ ] Step 2: add one canonical status-mapping surface without inventing a second status vocabulary
- [ ] Step 3: make terminal closeout idempotent across worker/supervisor/delegation/report writeback paths
- [ ] Step 4: run worker/delegation/runtime regressions

## Workstream C: MCP / Skill / Bridge Projection Hardening

**Files:**
- Modify: `src/copaw/app/mcp/manager.py`
- Modify: `src/copaw/capabilities/catalog.py`
- Modify: `src/copaw/capabilities/service.py`
- Modify: `src/copaw/capabilities/skill_service.py`
- Modify: `src/copaw/capabilities/mcp_registry.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Test: `tests/app/test_mcp_runtime_contract.py`
- Test: `tests/app/test_capability_catalog.py`
- Test: `tests/app/test_capability_skill_service.py`
- Test: `tests/app/test_capability_market_api.py`

- [ ] Step 1: add failing tests for MCP runtime projection, capability inventory metadata summaries, and stricter skill provenance/path-scope handling
- [ ] Step 2: project typed MCP runtime state into capability/read-model surfaces
- [ ] Step 3: finish projecting hardened skill/package identity beyond filesystem re-anchor, including validated source identity and residual duplicate/path-scope discipline
- [ ] Step 4: run MCP/capability regressions

## Workstream D: Runtime Center Diagnostics / Provenance / Recovery Drilldown

**Files:**
- Modify: `src/copaw/kernel/runtime_outcome.py`
- Modify: `src/copaw/kernel/governance.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_overview.py`
- Test: `tests/kernel/test_execution_diagnostics.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`
- Test: `tests/app/test_operator_runtime_e2e.py`

- [ ] Step 1: add failing tests for delta diagnostics, degraded rollups, and residual recovery/governance drilldown edge cases
- [ ] Step 2: expand canonical diagnostic shaping without letting Runtime Center mutate truth
- [ ] Step 3: finish operator-visible delta/drilldown surfaces from existing startup/runtime/environment facts
- [ ] Step 4: run Runtime Center/operator regressions

## Workstream E: Graph-Planning Mainline Follow-Up

**Files:**
- Modify: `src/copaw/memory/activation_service.py`
- Modify: `src/copaw/compiler/planning/models.py`
- Modify: `src/copaw/compiler/planning/cycle_planner.py`
- Modify: `src/copaw/compiler/planning/report_replan_engine.py`
- Modify: `src/copaw/industry/service_lifecycle.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Test: `tests/memory/test_activation_service.py`
- Test: `tests/compiler/test_cycle_planner.py`
- Test: `tests/compiler/test_report_replan_engine.py`
- Test: `tests/app/test_predictions_api.py`
- Test: `tests/industry/test_runtime_views_split.py`

- [ ] Step 1: if this slice is reopened, add failing tests only for new planner/read-surface consumers beyond the current relation-propagation chain
- [ ] Step 2: keep activation strategy reads on `resolve_strategy_payload(...)`
- [ ] Step 3: extend relation-edge summaries into additional planner/read surfaces only when needed, without creating graph persistence or a second truth source
- [ ] Step 4: run graph/planning regressions when that follow-up is reopened

## Workstream F: Docs / Status / Focused Regression

**Files:**
- Modify: `docs/superpowers/specs/2026-04-01-claude-runtime-contract-hardening-design.md`
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`

- [ ] Step 1: update landed-vs-follow-up wording once code is green
- [ ] Step 2: run focused full regression covering all workstreams
- [ ] Step 3: record remaining boundary explicitly instead of silently leaving vague “later optimization” language
