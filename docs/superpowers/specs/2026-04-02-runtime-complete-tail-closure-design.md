# Runtime Complete Tail Closure Design

## Goal

Finish the remaining post-hardening runtime tails as one gated engineering program rather than a sequence of loosely related follow-ups.

This design covers exactly four workstreams and treats them as one closure contract:

1. Runtime Center read-projector split phase 2
2. MCP lifecycle hardening
3. concurrency discipline plus child-run shell unification
4. planning shell plus formal planning gap implementation

The key rule is simple:

> this program is not complete until all four workstreams reach their exit criteria, the required compatibility/duplicate paths are deleted, and the wide regression/smoke gates are green together.

## Why This Exists

The repo has already closed the first runtime-contract wave, but a real "done" state still needs four larger tails removed:

- `state_query.py` is still too large even after the first task-list extraction
- MCP reload/rebuild lifecycle is stronger but still not hardened enough around dirty state, close/swap sequencing, and scoped overlays
- writer discipline and child-run execution cleanup are still not one explicit shell/contract
- the planning shell and formal planning gap are documented, but not yet fully implemented as formal CoPaw planning machinery

The problem is not lack of activity.

The problem is that these tails are structurally bigger than "one more cleanup patch", so treating them as incidental follow-ups causes repeated premature "done" calls.

This design prevents that drift by making the remaining work explicit, gated, and verifiable.

## Non-Goals

This closure program does not:

- replace CoPaw's upper truth chain
- replace `MainBrainOrchestrator`
- replace Runtime Center with a new surface
- turn prompt-only session planning into CoPaw's planner truth
- reopen already deleted compat paths unless required for diagnosis

The governing truth remains:

`StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan`

## Execution Contract

The program runs in strict sequence.

Stage `N+1` does not start until stage `N` is complete against its exit criteria.

Each stage must finish with:

- code changes
- test additions or test tightening
- required old-path deletion for that stage
- status/doc checkpoint updates for the affected boundary while still marking the overall closure program as open
- focused verification for the stage

Checkpoint commits are allowed after individual stages if they help preserve verified progress, but they do not change the overall completion state.

Only after all four stages are complete do we run the full closure verification sweep, mark the closure program as complete in the status/docs, commit the final closure sweep, and merge.

## Stage 1: Runtime Center Read-Projector Split Phase 2

### Scope

Continue shrinking `src/copaw/app/runtime_center/state_query.py` by extracting another stable read slice, starting with work-context reads.

### Required Direction

- keep `RuntimeCenterStateQueryService` as orchestration, not a giant projector
- move stable read-only work into dedicated collaborators under `src/copaw/app/runtime_center/`
- prefer `work-context` projection before riskier host/runtime or learning aggregation moves
- do not reintroduce query-side mutation

### Exit Criteria

- `task_list_projection.py` remains the owner of task list / kernel task projection
- all `list/count/detail work_context*` projection and serialization logic lives in the dedicated collaborator
- `RuntimeCenterStateQueryService` only delegates the extracted work-context read slice and keeps shared helpers only where they are still consumed across multiple projectors
- existing task/work-context/runtime-center read contracts stay behaviorally stable at both service and API level
- runtime query tests and Runtime Center API regressions lock the extracted slice

`2026-04-02` checkpoint:

- `work_context_projection.py` is live as the stable collaborator for `list/count/detail work_context*` plus shared work-context serialization
- state-backed regressions now cover real `count_work_contexts()`, runtime-owner detail rollups, and direct `GET /runtime-center/work-contexts` plus `GET /runtime-center/work-contexts/{context_id}`
- Stage 1 is closed, but the overall four-stage closure program remains open until Stage 2 through Stage 4 also reach their exit criteria

## Stage 2: MCP Lifecycle Hardening

### Scope

Complete the missing lifecycle shell around MCP config watching and client replacement.

### Required Direction

- explicit dirty-state/reload-intent tracking per client
- clear close/swap sequencing with isolated failure handling
- no silent partial success that leaves the manager in ambiguous mixed state
- Stage 2 owns the full MCP lifecycle plus additive/scoped overlay contract
- any new lifecycle contract must explicitly extend or replace the existing `app/mcp/runtime_contract.py` path rather than creating a parallel contract that coexists indefinitely
- prepare scoped/additive overlay contracts instead of relying on a single process-global shell only

### Exit Criteria

- watcher/manager share a formal reload state contract
- close, rebuild, swap, skip, and retry outcomes are explicit and observable
- partial failure cannot silently poison the steady-state snapshot
- scoped overlay/additive mount boundary exists in code and tests, and any duplicate lifecycle contract has been deleted
- MCP tests cover dirty-state, swap sequencing, failure recovery, and overlay/scoped mount behavior

`2026-04-02` checkpoint:

- `runtime_contract.py` now owns the typed reload-state contract; no second lifecycle schema was introduced
- watcher busy-skip now marks pending reload explicitly instead of dropping dirty state on the floor
- manager diagnostics now distinguish steady, pending, connect-failed, close-failed, overlay-mounted, and overlay-removed outcomes
- scoped overlays are covered for additive mount, replace-mode isolation, clear, and failed mount preserving the previous scope shell
- Stage 2 is closed, but the overall four-stage closure program remains open until Stage 3 and Stage 4 also reach their exit criteria

## Stage 3: Concurrency Discipline Plus Child-Run Shell

### Scope

Turn "read concurrent, write serialized" and child-run cleanup into one explicit runtime contract across shared writer surfaces.

### Required Direction

- formal writer reservation/ownership contract for shared surfaces
- read-only access can proceed concurrently
- write/mutation access must serialize through one contract
- the shared writer landing zone is `src/copaw/environments/lease_service.py` unless implementation proves a better equivalent and deletes the old duplication
- delegated child runs, actor worker execution, cancellation, and terminal cleanup must use one shared shell
- Stage 3 consumes the MCP overlay/lifecycle API produced by Stage 2; it does not create a second MCP lifecycle contract

### Exit Criteria

- shared writer surfaces use an explicit acquisition/release contract
- delegated child-run execution goes through one child shell, not multiple cleanup branches
- stop/cancel/failure/finish semantics converge across supervisor, worker, and delegation paths
- tests lock shared-writer conflicts, handoff/release, cancellation, and cleanup continuity

`2026-04-02` checkpoint:

- `EnvironmentService / EnvironmentLeaseService` now expose a formal shared-writer lease surface over the existing lease store instead of leaving writer serialization to ad-hoc task scans
- `kernel/child_run_shell.py` is live as the shared writer coordination shell; `ActorWorker` and direct delegation execution both consume it instead of each growing separate writer cleanup branches
- delegation governance now blocks cross-agent writer contention by consulting the shared-writer lease, while same-owner serialized work can still proceed through the single actor/supervisor lane
- focused environment/worker/delegation suites plus the long-run `phase_next` smoke are green for this boundary
- Stage 3 is closed, but the overall four-stage closure program remains open until Stage 4 also reaches its exit criteria

## Stage 4: Planning Shell Plus Formal Planning Gap

### Scope

Execute the formal planning design without mixing it into the first three runtime-hardening stages.

Primary references:

- `docs/superpowers/specs/2026-04-01-formal-planning-capability-gap-design.md`
- `docs/superpowers/plans/2026-04-01-formal-planning-capability-gap-implementation-plan.md`

### Required Direction

- implement typed planning contracts under a dedicated planning slice
- keep planning shell as assignment-local/sidecar machinery
- do not let planning shell become planning truth
- route lifecycle/compiler usage through formal planning outputs instead of local shallow heuristics

### Exit Criteria

- Stage 4 completion requires the full deliverable set from the formal-planning implementation program, not a subset
- typed planning compiler slice is live
- assignment-local planning shell/envelope is implemented first, then cycle planning, then strategy compilation, then report-to-replan outputs, then domain/runtime-surface wiring
- strategy compilation, cycle planning, assignment planning, and report-to-replan outputs are all wired into the formal chain
- runtime/industry surfaces expose the new planning outputs where needed
- planning tests, planning-specific regressions, and phase-next smoke coverage prove the new contracts end-to-end

`2026-04-02` closure checkpoint:

- `compiler/planning` is live as the typed planning slice; no second planner-truth chain was introduced
- bootstrap, goals, industry lifecycle, predictions, and runtime surfaces all consume the same formal planning sidecars
- `force + scoped backlog` now bypasses the active-cycle gate by opening a dedicated formal-planned cycle instead of mutating the current cycle in place
- `CapabilityService` now supports injected config I/O for isolated runtime/test shells while preserving the default patchable config front-door contract
- Stage 4 is closed, and therefore the full four-stage runtime complete tail closure program is closed

## Final Completion Gate

This full-tail closure program is complete only when all of the following are true:

1. Stage 1 through Stage 4 each reach their exit criteria
2. no compatibility or duplicate path remains that contradicts the new contract for those four areas
3. targeted regressions for each stage pass
4. the repo's formal runtime gate plus wide runtime regression and smoke suites pass together
5. the full formal-planning regression suite and affected Runtime Center / Industry UI tests pass
6. `TASK_STATUS.md`, `API_TRANSITION_MAP.md`, `docs/superpowers/specs/2026-04-01-formal-planning-capability-gap-design.md`, the historical runtime-contract hardening record, and the affected plan docs are updated to remove these items as active tails for this program

If any one of those conditions is false, the program is not complete.
