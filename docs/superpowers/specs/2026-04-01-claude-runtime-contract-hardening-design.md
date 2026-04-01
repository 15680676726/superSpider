# Claude-Derived Runtime Contract Hardening Design

## Goal

Harden CoPaw's lower execution contract with Claude-derived runtime ideas without replacing CoPaw's formal truth, main-brain chain, Runtime Center, or truth-first memory.

In plain terms:

- Keep CoPaw's top-level architecture.
- Fix the immature lower execution path that prevents complete tasks from finishing reliably.
- Borrow runtime discipline from Claude Code, not its full product model.

## Current Reality

This is not a ground-up rebuild.

What is already valuable and should remain intact:

- single main-brain cognitive center
- industry object chain
- Runtime Center cockpit
- truth-first memory
- host / continuity / recovery / evidence loop

What is currently weak:

- file/shell execution contract
- result normalization
- outcome / failure taxonomy
- interrupt / cancel / timeout / cleanup semantics
- evidence coupling
- request normalization at execution edges
- lower-layer execution reliability for full-task completion

What already exists and should be tightened rather than reinvented:

- `CapabilityExecutionFacade.execute_task()` already acts like a unified execution front-door
- `KernelToolBridge` already records file/shell/browser evidence against kernel tasks
- `query_execution_runtime._resolve_execution_task_context(...)` already merges execution-side runtime context
- `/runtime-center/chat/run` already behaves like a thin SSE ingress over `turn_executor.stream_request()`

## What Must Not Be Replaced

These remain CoPaw's formal core:

1. `src/copaw/state/`
2. `MainBrainOrchestrator` as the main-brain execution front
3. `Runtime Center / Industry / StrategyMemory` as formal product surfaces
4. truth-first / no-vector formal memory

Claude Code is not the new system center.

## What This Does Not Solve By Itself

Even if all Claude-derived runtime hardening items are completed, CoPaw still does not automatically become a complete short/mid/long-horizon planner.

These upgrades primarily improve:

1. execution reliability
2. planning-shell quality inside a turn or assignment
3. long-task context discipline
4. worker/runtime cleanup consistency

They do not by themselves replace the need for a stronger formal planner over CoPaw's existing upper truth chain:

- `StrategyMemory`
- `OperatingLane`
- `BacklogItem`
- `OperatingCycle`
- `Assignment`
- `AgentReport`

So the intended outcome is:

- better short-horizon decomposition
- better execution follow-through
- cleaner review/replan inputs

But not:

- a new complete long-range planning truth model
- a session-first planner
- Claude's planner becoming CoPaw's new strategic center

## Unified Ingress Boundary

`/runtime-center/chat/run` should stay.

Its role is:

- unified ingress
- transport boundary
- payload normalization boundary
- stream relay / request relay surface

Its role is not:

- a standalone chat system
- a second semantic center
- a second execution chain

The intended shape is:

`front door -> intake -> main-brain classify -> chat or execute branch -> unified runtime contract`

So:

1. the front door remains
2. the main brain still decides chat vs execute
3. `KernelTurnExecutor` still selects the runtime branch
4. the front door must not grow its own parallel logic center

## What Should Be Hardened

The lower execution contract should first be tightened along these core cuts:

1. internal execution context
2. execution outcome / failure taxonomy
3. interrupt / cancel / timeout / cleanup semantics
4. unified execution/tool front-door
5. evidence coupling
6. request normalization

Later phases can harden:

7. MCP runtime hardening
8. task interpretation / assignment execution shell
9. worker / subagent shell
10. skill / package contract

## Claude Autonomy Extraction Boundary

Claude Code has mature autonomy-related ideas that are worth extracting.

What can be borrowed later:

1. request normalization
2. single-turn intake discipline
3. task envelope design
4. worker lifecycle
5. background execution shell
6. child task / subagent result envelope
7. stage-aware failure handling
8. interrupt / cleanup discipline

What should not be copied wholesale:

1. Claude's session-first center
2. Claude's app-state/task product model
3. Claude's top-level task hierarchy as CoPaw's new control model
4. Claude as CoPaw's new planner/scheduler center

CoPaw's formal upper objects remain:

- `BacklogItem`
- `OperatingCycle`
- `Assignment`
- `Task`
- `AgentReport`

So the rule is:

- borrow execution shell ideas
- do not replace CoPaw's formal planning and execution objects

## Additional Claude-Derived Discipline Not To Miss

The first runtime-hardening design captured the main contract cuts correctly, but a real read of Claude Code shows six additional pieces of discipline that should be stated explicitly.

### 1. Context entropy control is a first-class runtime concern

Claude Code is not only strong because it has a loop.

It is strong because the loop actively controls context entropy through:

- tool result budget
- microcompact / autocompact
- tool-use summaries
- successful carry-forward over long turns

CoPaw should explicitly treat this as a runtime-hardening target for:

- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/memory/conversation_compaction_service.py`

This is one of the most relevant Claude-derived ideas for "full task does not reliably finish" symptoms.

### 2. Planning shell is borrowable, planning truth is not

Claude Code's plan mode, plan file, plan agent, todo list, and session task shell are useful.

What they are useful for in CoPaw:

- assignment-local planning scratch
- execution-side checklisting
- implementation/work package decomposition
- operator-visible sidecar planning

What they must not become:

- CoPaw's formal short/mid/long-horizon planning truth
- a replacement for `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport`

So the correct extraction rule is:

- borrow Claude's planning shell
- do not borrow Claude's planning truth model

### 3. Read-only concurrency vs writer serialization should be explicit

Claude Code's tool orchestration is not "parallel everywhere".

It distinguishes:

- read-only work that can run concurrently
- write/mutation work that must remain serialized

CoPaw should make this an explicit contract for future execution surfaces, especially:

- file
- browser
- desktop
- document
- multi-agent shared writers

This belongs under the execution contract, not as an incidental implementation detail.

### 4. Hook-first runtime discipline should outrank scattered branch logic

Claude Code's tool runtime is valuable because permission, evidence, stop, and failure handling are concentrated around one execution front-door using pre/post/failure hooks.

CoPaw should continue tightening toward:

- before-execution hooks
- after-execution hooks
- failure hooks

instead of duplicating runtime control logic across multiple service branches.

Primary landing zones remain:

- `src/copaw/capabilities/execution.py`
- `src/copaw/kernel/tool_bridge.py`
- `src/copaw/kernel/runtime_outcome.py`

### 5. Agent-additive MCP/runtime shell is worth borrowing

Claude Code's subagent runtime is not valuable because its top-level task model should replace CoPaw.

It is valuable because it gives child runs a cleaner shell for:

- additive MCP mounts
- inherited context with bounded scope
- startup wiring
- cleanup on finish

For CoPaw this is relevant to:

- `src/copaw/kernel/actor_worker.py`
- `src/copaw/kernel/actor_supervisor.py`
- `src/copaw/kernel/delegation_service.py`
- `src/copaw/app/mcp/manager.py`

### 6. Skill provenance and path-scoped activation should be explicit

Claude Code's skill discipline is stronger than "prompt files with metadata".

It also includes:

- source provenance
- frontmatter validation
- path-scoped activation
- duplicate suppression by canonical path identity

CoPaw should explicitly borrow this discipline for:

- `src/copaw/capabilities/skill_service.py`
- `src/copaw/capabilities/models.py`
- `src/copaw/capabilities/catalog.py`

This should remain a capability/package contract improvement, not a second truth layer.

## Merged Runtime Hardening Priority Sequence

After the full `cc/` review, the practical priority sequence for CoPaw should be stated explicitly instead of leaving it as scattered design notes.

### 1. Unified execution + tool front-door

This remains the highest-value cut.

More than any "autonomy feel", CoPaw needs one place where execution actually enters and is governed.

This front-door should concentrate:

- permission / risk gating
- execution context assembly
- outcome classification
- evidence emission
- interrupt / cancel / timeout handling
- cleanup / release handling

This absorbs and sharpens:

- unified file/shell front-door
- hook-first runtime discipline
- capability execution closure

Primary landing zones:

- `src/copaw/capabilities/execution.py`
- `src/copaw/kernel/tool_bridge.py`
- `src/copaw/kernel/runtime_outcome.py`
- `src/copaw/kernel/turn_executor.py`

### 2. Context entropy control

Claude-derived runtime value is not only that the loop exists.

It is that the loop stays clean under long-running pressure.

CoPaw should elevate:

- tool result budget
- microcompact / autocompact
- tool-use summary
- long-turn carry-forward discipline

This is more important than adding more "agentic" surface behavior while long tasks still decay under context pressure.

Primary landing zones:

- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/memory/conversation_compaction_service.py`

### 3. Concurrency discipline: read concurrent, write serialized

CoPaw should make this an explicit runtime contract, not an accidental implementation habit.

The rule should be:

- read-only work may run concurrently
- mutation work must remain serialized
- shared writer surfaces require explicit lease / lock semantics

This matters most for:

- file
- browser
- desktop
- document
- multi-agent shared writers

Primary landing zones:

- `src/copaw/environments/service.py`
- `src/copaw/environments/lease_service.py`
- `src/copaw/kernel/actor_supervisor.py`
- `src/copaw/kernel/delegation_service.py`

### 4. MCP lifecycle hardening

MCP should not be treated as "connected once and hope it stays fine".

The runtime contract should explicitly cover:

- connect / replace / remove
- reload on config change
- runtime diagnostics
- invalidation / refresh
- reconnect / failure handling
- cleanup on shutdown or scope end

Primary landing zones:

- `src/copaw/app/mcp/manager.py`
- `src/copaw/app/mcp/watcher.py`
- `src/copaw/capabilities/service.py`

### 5. Planning shell, not planner truth

Claude's planning shell is useful.

Claude's planning truth model is not CoPaw's replacement.

The borrowable shell should support:

- assignment-local planning scratch
- execution-side checklisting
- task decomposition / todo capture
- operator-visible sidecar planning

It must not replace:

- `StrategyMemory`
- `OperatingLane`
- `BacklogItem`
- `OperatingCycle`
- `Assignment`
- `AgentReport`

Primary landing zones:

- `src/copaw/compiler/compiler.py`
- `src/copaw/industry/service_lifecycle.py`
- `src/copaw/app/runtime_center/state_query.py`

### 6. Runtime Center projection/read-model hardening

Runtime Center should keep getting stronger as the formal visible projection layer.

But it must remain a projection and read-model surface, not a new orchestration kitchen sink.

The hardening target is:

- cleaner projection boundaries
- less ad hoc assembly inside query facades
- clearer mapping from formal truth objects to operator-visible runtime cards

Primary landing zones:

- `src/copaw/app/runtime_center/state_query.py`
- `src/copaw/app/runtime_center/task_review_projection.py`
- `src/copaw/app/runtime_center/overview_cards.py`

### 7. Risk governance should keep moving inward to the kernel

CoPaw already has the better top-level direction here than `cc`.

The remaining work is to keep risk decisions from drifting back out into scattered business branches.

The execution contract should consistently answer:

- auto vs guarded vs confirm
- whether a human confirmation boundary is required
- what evidence and decision payload must be emitted
- what cleanup or resume path follows

Primary landing zones:

- `src/copaw/kernel/governance.py`
- `src/copaw/kernel/decision_policy.py`
- `src/copaw/capabilities/execution.py`
- `src/copaw/kernel/turn_executor.py`

### 8. Skill metadata discipline

CoPaw should explicitly adopt stronger skill/package discipline instead of treating skills as loose prompt folders.

This should include:

- source provenance
- frontmatter validation
- path-scoped activation
- canonical-path duplicate suppression

Primary landing zones:

- `src/copaw/capabilities/skill_service.py`
- `src/copaw/capabilities/models.py`
- `src/copaw/capabilities/catalog.py`

### 9. Agent-specific additive MCP + cleanup shell

This is a narrower but still valuable Claude-derived borrow.

Child workers should be able to receive:

- additive MCP mounts
- bounded inherited context
- startup wiring for the child run
- guaranteed cleanup on finish / cancel / failure

This should improve worker/runtime hygiene without importing Claude's top-level task model.

Primary landing zones:

- `src/copaw/kernel/actor_worker.py`
- `src/copaw/kernel/actor_supervisor.py`
- `src/copaw/kernel/delegation_service.py`
- `src/copaw/app/mcp/manager.py`

### 10. Large-file split and orchestration hotspot cooling

This is not a cosmetic cleanup item.

It is a delivery prerequisite for the other priorities above.

The current repository already has several orchestration hotspots that are large enough to slow safe iteration and hide lifecycle leakage.

Current examples include:

- `src/copaw/environments/health_service.py`
- `src/copaw/industry/service_lifecycle.py`
- `src/copaw/capabilities/install_templates.py`
- `src/copaw/industry/service_runtime_views.py`
- `src/copaw/routines/service.py`

The goal is not performative file splitting.

The goal is to reduce orchestration concentration so front-door, entropy, concurrency, MCP, and planning-shell hardening can land without creating a new giant-file dependency cluster.

## How To Read The 10 Priorities Against `P0 / P1 / P2`

The merged 10-item priority sequence above does not replace the existing `P0 / P1 / P2` record.

It clarifies how those phases should be interpreted.

It does **not** mean that every mapped priority was fully implemented inside the historical `2026-04-01 P0 / P1 / P2 landed shape`.

The correct reading is:

- the historical landed wave closed the contract cuts explicitly recorded in the `P0 landed shape` and `P1-P2 landed shape` sections below
- the 10-item sequence is the broader Claude-derived borrowing map that should classify future execution-facing work
- some mapped priorities are therefore forward classification guidance, not retroactive completion claims

### `P0` foundation phase

`P0` should be read primarily as the foundation cut for:

- priority `1` unified execution + tool front-door
- the execution-side portion of priority `7` risk governance moving inward to the kernel

Concretely, this means:

- execution context standardization
- normalized outcome / failure taxonomy
- interrupt / cancel / timeout / cleanup consistency
- evidence coupling
- request normalization

This phase is about making one lower execution contract reliable before widening the shell.

### `P1` runtime-shell phase

`P1` should be read primarily as the shell-hardening cut for:

- priority `4` MCP lifecycle hardening
- priority `3` concurrency discipline
- the assignment-local shell portion of priority `5` planning shell
- the projection-facing portion of priority `6` Runtime Center hardening
- the lifecycle portion of priority `9` agent-specific additive MCP + cleanup

This phase is about stabilizing runtime shells around the already-hardened front-door instead of inventing another execution center.

### `P2` long-task-discipline phase

`P2` should be read primarily as the long-task and package-contract cut for:

- priority `2` context entropy control
- priority `8` skill metadata discipline
- the provenance / additive cleanup remainder of priority `9`

Priority `10` large-file split and orchestration hotspot cooling is not a truth-bearing phase by itself.

It should be treated as enabling work that attaches to whichever phase it unblocks.

### Practical rule

If a future execution-facing task cannot be cleanly explained as `P0`, `P1`, or `P2` under this mapping, it probably does not belong under Claude-derived runtime contract hardening.

## Construction-Fit Notes

To avoid ambiguous implementation ownership, future work should apply the sequence above with these additional construction rules:

### 1. Historical closure vs future borrowing must stay separate

Do not treat the merged 10-item sequence as proof that every item is already green.

When checking completion, use:

- `P0 landed shape`
- `P1-P2 landed shape`
- `TASK_STATUS.md`

When classifying a new execution-facing hardening task, use:

- the merged 10-item sequence
- the `P0 / P1 / P2` mapping above

### 2. Planning-shell and Runtime Center projection items usually need separate follow-up plans

The historical `2026-04-01` runtime-contract implementation plans did not own the full file surface for:

- `src/copaw/compiler/compiler.py`
- `src/copaw/industry/service_lifecycle.py`
- `src/copaw/app/runtime_center/state_query.py`
- `src/copaw/app/runtime_center/task_review_projection.py`
- `src/copaw/app/runtime_center/overview_cards.py`

So future work under priority `5` or priority `6` should normally be recorded as separate follow-up plans instead of being silently folded into the already-closed historical `P1/P2` record.

### 3. Context-entropy work should be treated as explicit long-task verification work

For priority `2`, "implemented" should not mean only that a service or helper exists.

The acceptance bar should explicitly cover:

- long-turn budget behavior
- compaction boundary behavior
- carry-forward cleanliness across multiple turns
- operator-visible degradation/summary behavior

If those verification slices are not present, the item should be treated as partially framed rather than fully closed.

### 4. Large-file splitting is enabling work, not decorative cleanup

Priority `10` should only be logged when it materially reduces delivery risk for another priority.

Good examples:

- splitting a hotspot so front-door hooks can land cleanly
- splitting projection assembly so Runtime Center read-model work can be isolated
- splitting lifecycle orchestration so MCP or worker cleanup semantics can be tested in smaller units

Bad examples:

- file shuffling without contract reduction
- presentation-only renames counted as hardening progress

## Current Repo Construction Matrix

This matrix is a current repo classification snapshot against the 10 priorities above.

It is not:

- a retroactive claim that the historical `2026-04-01 P0 / P1 / P2` landed wave fully closed every row below
- a reason to reopen already-closed historical work without a new follow-up scope

Reading guide:

- `present` means the primary landing zone already exists and materially carries the intended contract
- `partial` means the landing zone exists but still has policy leakage, lifecycle gaps, or missing verification
- `follow-up` in the phase column means the work should be tracked as new scope instead of being silently counted against the already-closed historical wave

| Priority | Current landing zones | Current repo reading | Phase reading | Current gap / best next move |
|---|---|---|---|---|
| `1. Unified execution + tool front-door` | `src/copaw/capabilities/execution.py`, `src/copaw/kernel/tool_bridge.py`, `src/copaw/kernel/runtime_outcome.py`, `src/copaw/kernel/turn_executor.py` | `present` | historical `P0` landed; future tightening is `follow-up` | The unified lower execution front-door is real, but some execution/evidence policy is still hard-coded by capability id and can leak on indirect skill-shell paths. Next move: move execution/evidence ownership into mount-declared policy and keep `KernelToolBridge` as the single sink closure for indirect shell/file/browser actions. |
| `2. Context entropy control` | `src/copaw/kernel/query_execution_runtime.py`, `src/copaw/memory/conversation_compaction_service.py`, downstream Runtime Center degradation surfaces | `partial` | `P2` partial | Compaction exists and sidecar-memory degradation is explicit, but the repo still lacks a clear tool-result budget, microcompact/autocompact policy, carry-forward acceptance contract, and explicit operator-visible verification. Next move: treat this as telemetry/acceptance work at the query-runtime boundary, not as a new truth source. |
| `3. Concurrency discipline: read concurrent, write serialized` | `src/copaw/environments/service.py`, `src/copaw/environments/lease_service.py`, `src/copaw/kernel/actor_supervisor.py`, `src/copaw/kernel/delegation_service.py` | `partial` | `P1` partial | Lease primitives, agent locks, and conflict previews exist, but writer serialization is still partly advisory and preview-driven rather than one explicit reservation contract. Next move: add serialized/CAS-style writer acquisition and make delegated child runs reserve shared writer surfaces before execution. |
| `4. MCP lifecycle hardening` | `src/copaw/app/mcp/manager.py`, `src/copaw/app/mcp/watcher.py`, execution-side MCP dispatch in `src/copaw/capabilities/execution.py` | `partial` | `P1` partial | Typed runtime/rebuild records and watcher reloads already exist, but reload reconciliation and close/swap sequencing still leave lifecycle leak risk, especially on partial failure. Next move: track per-client dirty state, separate close outcome from in-lock swap, and prepare for scoped overlays instead of one process-global shell only. |
| `5. Planning shell, not planner truth` | `src/copaw/compiler/compiler.py`, `src/copaw/industry/service_lifecycle.py`, `src/copaw/kernel/query_execution_runtime.py`, `docs/superpowers/specs/2026-04-01-formal-planning-capability-gap-design.md` | `partial` | historical `P1` shell partial; native planning follow-up beyond that | Strategy/memory-aware step shells, continuity metadata, and review seeds exist, but they are still mostly raw `steps` / dict payloads rather than a typed assignment-plan envelope with checkpoints, acceptance criteria, retry policy, and bounded sidecar planning artifacts. Next move: move the remaining planner contract into the dedicated planning compiler slice instead of deepening `service_lifecycle.py`. |
| `6. Runtime Center projection/read-model hardening` | `src/copaw/app/runtime_center/state_query.py`, `src/copaw/app/runtime_center/task_list_projection.py`, `src/copaw/app/runtime_center/task_review_projection.py`, `src/copaw/app/runtime_center/overview_cards.py` | `partial` | `P1` follow-up | Runtime Center has now pulled the clearest boundary violations back behind formal surfaces: decision list/detail reads stay pure, the official review write front-door is only `/runtime-center/governed/decisions/{id}/review`, `/runtime-center/kernel/tasks` reads the persisted `KernelTaskStore` projection instead of live dispatcher lifecycle, and the first stable task-list slice has been extracted into `task_list_projection.py`. Remaining follow-up is still real: the projection path is heuristic-heavy in places, `state_query.py` remains a hotspot, and per-card/read-slice contracts need further narrowing. |
| `7. Risk governance moving inward to the kernel` | `src/copaw/capabilities/execution.py`, `src/copaw/kernel/runtime_outcome.py`, `src/copaw/kernel/turn_executor.py`, adjacent delegation/runtime paths | `present` | execution-side historical `P0` landed; further inward moves are `follow-up` | CoPaw already has the right direction: risk, outcome, confirmation, and remediation are increasingly answered by the front-door/runtime contract instead of scattered leaf branches. Next move: keep pushing remaining branch-local policy into mount-declared/front-door governance and avoid query/projection surfaces making governance-side mutations. |
| `8. Skill metadata discipline` | `src/copaw/capabilities/skill_service.py`, `src/copaw/capabilities/catalog.py`, skill execution path in `src/copaw/capabilities/execution.py` | `partial` | `P2` partial | Package provenance is now formal enough to carry `package_ref / package_kind / package_version`, but metadata discipline is still permissive: no strong evidence yet of strict frontmatter validation, path-scoped activation, or canonical-path duplicate suppression. Next move: add validated source identity and expose normalized metadata summaries instead of raw filesystem-first payloads. |
| `9. Agent-specific additive MCP + cleanup shell` | `src/copaw/kernel/actor_worker.py`, `src/copaw/kernel/actor_supervisor.py`, `src/copaw/kernel/delegation_service.py`, `src/copaw/app/mcp/manager.py`, `src/copaw/kernel/runtime_outcome.py` | `partial` | historical `P1` lifecycle partial with `P2` remainder | Worker heartbeat and centralized cleanup already exist, but the child-run shell is still split and additive MCP mounts are not yet formalized; some delegated paths can still bypass the richer worker shell. Next move: require one child execution shell and give that shell scoped additive MCP/session setup plus guaranteed finish/cancel/failure cleanup. |
| `10. Large-file split and orchestration hotspot cooling` | `src/copaw/industry/service_lifecycle.py`, `src/copaw/kernel/turn_executor.py`, `src/copaw/app/runtime_center/state_query.py`, `src/copaw/app/runtime_center/task_review_projection.py`, `src/copaw/app/runtime_center/overview_cards.py`, `src/copaw/environments/lease_service.py`, `src/copaw/capabilities/execution.py`, `src/copaw/environments/service.py`, `src/copaw/kernel/delegation_service.py` | `partial` | enabling `follow-up` only | The repo already has several real hotspot files where future hardening work will otherwise pile up into new orchestration clusters. Next move: split only where the split reduces contract concentration for priorities `1`-`9`; do not count cosmetic file moves as hardening progress. |

### Hotspot Shortlist

The highest-value current cooling candidates are:

1. `src/copaw/industry/service_lifecycle.py`
   - planning-shell, cycle materialization, review, and dispatch are still too concentrated here
   - this is the easiest place for Claude-derived shell logic to accidentally drift toward a second planner truth
2. `src/copaw/kernel/turn_executor.py`
   - ingress, interaction-mode heuristics, streaming, failure handling, and usage writeback are still concentrated in one orchestration file
   - future cooling should only happen if it deletes real duplicated logic instead of introducing a donor-style parallel loop
3. `src/copaw/app/runtime_center/state_query.py`
   - the worst query-side mutation leak is now closed, and the first task-list/kernel-task slice has already moved into `task_list_projection.py`, but read-model assembly and heuristic-heavy task/decision projection are still too concentrated here
   - this remains the clearest Runtime Center hotspot for future split work, even after the projection/write boundary was tightened and the first projector extraction landed
4. `src/copaw/environments/lease_service.py`
   - the real writer-discipline logic lives here, but acquisition and release semantics are still too optimistic/multi-step for long-lived shared writers
   - this is the key landing zone if CoPaw wants `browser / desktop / file / document / multi-agent` writer discipline to stay clean

### Repo-Level Judgment

Across the current repo, the strongest already-landed Claude-derived borrowing is still:

- unified execution/tool front-door
- lower outcome/evidence coupling
- basic runtime-shell cleanup discipline

The most important remaining borrowing work is:

- make entropy control explicit and verifiable
- keep planning shell as shell by moving the remaining planner contract into typed planning slices
- convert concurrency/MCP/child-run discipline from partially advisory shells into explicit scoped runtime contracts
- keep Runtime Center projection-only while hotspot cooling happens

If a future task claims Claude-derived runtime hardening progress but does not clearly improve one row in the matrix above, it probably belongs to:

- a different planning-program task
- a general refactor that should not be counted as hardening progress
- or a new parallel truth source that should be rejected

## Core Design Decisions

### 1. `CapabilityExecutionContext` is internal only

`CapabilityExecutionContext` is allowed in `P0`, but only as an internal standard context inside the execution layer.

Primary landing point:

- `src/copaw/capabilities/execution.py`

New file:

- `src/copaw/capabilities/execution_context.py`

It may carry:

- task identity
- goal/work-context references
- capability identity
- owner / risk / environment binding
- timeout / cancellation hints
- evidence binding
- read-vs-write execution hints

It must not become:

- a new runtime truth source
- a new environment truth source
- a new owner/risk center

It should be treated as a typed/clean internal wrapper around context that is currently assembled ad hoc across:

- `CapabilityExecutionFacade.execute_task()`
- `query_execution_runtime._resolve_execution_task_context(...)`
- file/shell tool invocation payload shaping

### 1a. Unified execution outcome / failure taxonomy is a first-class `P0` target

CoPaw already has partial pieces of this across:

- `CapabilityExecutionFacade`
- `KernelToolBridge`
- `runtime_outcome.py`
- `ActorWorker`
- `TaskLifecycleManager`
- `TaskDelegationService`

The `P0` goal is not to invent a new top-level object model.

The goal is to make the lower-layer execution contract consistently answer:

1. did execution succeed, fail, cancel, block, or wait for confirmation
2. what summary should downstream layers display
3. what error class / failure family is this
4. what evidence should be emitted
5. what cleanup action should follow

This is one of the highest-value `P0` cuts.

### 2. `task_state_machine.py` is conditional, not mandatory `P0`

This is the main correction to the earlier design.

CoPaw already has:

- kernel phase vocabulary in `KernelTask.phase`
- lifecycle logic in `TaskLifecycleManager`
- phase-to-task/runtime projection in `kernel/persistence.py`

Therefore:

- do not force `task_state_machine.py` into `P0`
- only extract it if implementation proves phase logic is duplicated enough to justify it

If extracted later, it may only:

1. wrap existing `KernelTask.phase` transitions
2. reuse existing phase/status mappings

It must not:

1. invent a second vocabulary
2. redefine live status semantics
3. bypass lifecycle/persistence contracts

### 3. `turn_loop.py` is also conditional, not a `P0` entry requirement

This is the second major correction.

CoPaw already has:

- `MainBrainOrchestrator`
- `KernelTurnExecutor`
- `QueryExecutionRuntime`

So a separate `turn_loop.py` should not be added in `P0` just because Claude has a strong single-turn loop concept.

If extracted later, it should be a refactoring result:

- thin orchestration helper
- no new semantic center
- no replacement of the existing main chain

It must not become:

- a second orchestration center
- a second explanation layer for the same path

### 4. Claude files are semantic references, not transplant targets

The reference map below is for extracting contracts, not doing file ownership migration.

Correct use:

- extract boundaries
- extract lifecycle discipline
- extract failure handling
- extract context shapes

Incorrect use:

- file-by-file transplant
- building a second session/task/app-state center inside CoPaw

## Reference Extraction Map

### Tool execution contract

References:

- `claude-code-source-code-main/src/Tool.ts`
- `claude-code-source-code-main/src/services/tools/toolOrchestration.ts`
- `claude-code-source-code-main/src/services/tools/toolExecution.ts`

Landing:

- `src/copaw/capabilities/execution.py`
- `src/copaw/capabilities/execution_context.py`
- `src/copaw/kernel/tool_bridge.py`

Extract:

- execution context
- read/write orchestration discipline
- normalized result envelope
- tool/evidence coupling

### Query loop

References:

- `claude-code-source-code-main/src/QueryEngine.ts`
- `claude-code-source-code-main/src/query.ts`

Landing:

- `src/copaw/kernel/turn_executor.py`
- later, only if justified: `src/copaw/kernel/turn_loop.py`

Extract:

- single-turn closure
- stage ordering
- stage-aware failure surface

### Task / subagent runtime shell

References:

- `claude-code-source-code-main/src/Task.ts`
- `claude-code-source-code-main/src/tools/AgentTool/`

Landing:

- `src/copaw/kernel/actor_worker.py`
- `src/copaw/kernel/actor_supervisor.py`
- `src/copaw/kernel/delegation_service.py`

Extract:

- worker lifecycle
- cancel/stop semantics
- background execution shell

Not in `P0`.

### MCP runtime

Reference:

- `claude-code-source-code-main/src/services/mcp/client.ts`

Landing:

- `src/copaw/app/mcp/manager.py`

Extract:

- lifecycle hardening
- auth/session/cache/error policy

Not in `P0`.

### Skill/package contract

References:

- `claude-code-source-code-main/src/skills/loadSkillsDir.ts`
- `claude-code-source-code-main/src/plugins/builtinPlugins.ts`

Landing:

- `src/copaw/capabilities/skill_service.py`
- `src/copaw/capabilities/models.py`
- later package-binding services

Not in `P0`.

## P0 Scope

`P0` is intentionally narrow. It covers only:

This corresponds primarily to priority `1` plus the lower execution portion of priority `7` in the merged sequence above.

1. introduce `CapabilityExecutionContext` as a typed internal execution-layer context over existing lower-layer fields
2. standardize execution outcome / failure taxonomy around the already-existing lower runtime pieces
3. standardize interrupt / cancel / timeout / cleanup semantics where they currently differ across execution paths
4. standardize file/shell front-door behavior around the already-existing `CapabilityExecutionFacade` contract
5. tighten evidence coupling where the file/shell path still differs between direct evidence append and tool-bridge-mediated evidence
6. tighten request normalization by reusing and clarifying the existing `_resolve_execution_task_context(...)` path
7. make all of this work without breaking the current live route

`P0` explicitly does not include:

- `MainBrainOrchestrator` redesign
- `/runtime-center/chat/run` redesign
- Runtime Center read-surface redesign
- mandatory `task_state_machine.py`
- mandatory `turn_loop.py`
- MCP runtime hardening
- worker/subagent shell hardening

## P1 Scope

After `P0` is green:

This corresponds primarily to priorities `3 / 4 / 5 / 6`, plus the lifecycle portion of priority `9`.

1. MCP runtime hardening
2. task interpretation hardening
3. assignment execution / worker lifecycle hardening
4. richer execution diagnostics
5. conditional extraction of `task_state_machine.py` if it removes real duplication
6. conditional extraction of `turn_loop.py` if it removes real orchestration duplication

## P2 Scope

After `P1`:

This corresponds primarily to priorities `2 / 8 / 9`, with priority `10` treated as enabling split work rather than a standalone truth phase.

1. worker/subagent shell hardening
2. skill metadata formalization
3. package binding
4. sidecar memory
5. stronger autonomy execution/degradation strategies

## Risks

Main risks:

1. inventing a second execution vocabulary
2. cutting into main-brain/front-door too early
3. turning reference extraction into donor transplant
4. treating an alive main chain like a rebuild target
5. importing Claude's execution shell as CoPaw's upper scheduling model
6. adding abstraction shells before they remove real complexity

## Success Standard

`P0` succeeds when:

1. file/shell execution goes through one hardened front-door
2. evidence is coupled to that front-door
3. the existing execution outcome / failure taxonomy is clearer and more uniform
4. interrupt / cancel / timeout / cleanup semantics are more consistent across execution paths
5. the existing execution-context normalization path is clearer and more uniform
6. the current live route still works
7. complete-task execution becomes materially more reliable without changing upper truth layers

## 2026-04-01 P0 Landed Shape

The implemented `P0` landed in the following concrete shape:

1. `CapabilityExecutionContext` is now wired into `CapabilityExecutionFacade`; it is no longer only a design placeholder.
2. capability execution now returns one normalized result contract across early-return, exception, and tool-response paths.
3. lower execution failure taxonomy is explicit through `error_kind`, with `completed / failed / cancelled / timeout` now distinguished at the capability contract level.
4. mailbox/delegation cleanup now reuses one shared `cleanup disposition` helper keyed off existing kernel phases, without introducing a second state machine.
5. file/shell/browser tool-bridge evidence now records concrete outcome status instead of collapsing everything into a generic success record.
6. `_resolve_execution_task_context(...)` remains the canonical query-runtime merge point for `main_brain_runtime / work_context / environment` continuity.
7. `/runtime-center/chat/run` stays as the same SSE ingress; this work did not introduce a second front door or a donor-style `turn_loop`.

## 2026-04-01 P1-P2 Landed Shape

The follow-up `P1/P2` work landed in the following concrete shape:

1. MCP runtime now has a typed runtime/rebuild contract; `MCPClientManager` no longer hand-shapes multiple raw diagnostic dict variants for init/reload/remove flows.
2. task interpretation now hardens around one canonical request view: system dispatch prefers `dispatch_request`, delegated child-run payloads carry `dispatch_request + request + request_context`, and lineage stays in `meta`, so dispatcher/persistence/read surfaces all consume one normalized request family.
3. delegated `execute=True` no longer performs per-caller mailbox terminal cleanup inside `TaskDelegationService`; ownership now centers on `ActorSupervisor -> ActorWorker`.
4. worker interruption, submit-time terminal handling, and result-time terminal handling now close through one mailbox finalization path without introducing a new lifecycle vocabulary.
5. richer execution diagnostics now normalize `failure_source / blocked_next_step / remediation_summary` for blocked admissions and operator-visible governance surfaces.
6. capability mounts now carry formal `package_ref / package_kind / package_version`; skill frontmatter and MCP registry provenance both bind into the same read model instead of bespoke shaping.
7. skill package binding now has a real write/read path: hub install writes package metadata back into `SKILL.md`, and the capability catalog reads it back through the formal binding contract.
8. sidecar-memory and degraded-runtime handling are now explicit degradation contracts rather than hidden fallback behavior; the runtime-side `sidecar_memory` contract now derives from the same `conversation_compaction_service` boundary that query execution uses, so query execution checkpoints/runtime metadata and Runtime Center overview can surface one consistent degradation path without treating it as a truth-source failure.

## 2026-04-01 Conditional Extraction Audit

The conditional extraction audit was completed and both candidate extractions were rejected for this wave:

1. `task_state_machine.py` was not extracted because the remaining task-phase logic now shares contract helpers without enough duplicated transition code to justify a second state-machine shell.
2. `turn_loop.py` was not extracted because `KernelTurnExecutor + MainBrainOrchestrator + QueryExecutionRuntime` still form one coherent existing chain; adding a donor-style turn loop here would create a second orchestration explanation layer without deleting enough real complexity.
3. The practical rule remains: only extract either file in a future wave if the extraction deletes real duplication in the same commit and does not introduce a second execution center.
