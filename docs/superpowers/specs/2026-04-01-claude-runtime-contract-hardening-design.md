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

The lower execution contract should be tightened in this order:

1. internal execution context
2. execution outcome / failure taxonomy
3. interrupt / cancel / timeout / cleanup semantics
4. unified file/shell front-door
5. evidence coupling
6. request normalization

Later phases can harden:

6. MCP runtime
7. task interpretation / assignment execution shell
8. worker / subagent shell
9. skill / package contract

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

1. MCP runtime hardening
2. task interpretation hardening
3. assignment execution / worker lifecycle hardening
4. richer execution diagnostics
5. conditional extraction of `task_state_machine.py` if it removes real duplication
6. conditional extraction of `turn_loop.py` if it removes real orchestration duplication

## P2 Scope

After `P1`:

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

## Immediate Next Step

Write and execute a narrow `P0` plan in this order:

1. `execution_context.py`
2. outcome / failure taxonomy hardening
3. interrupt / cancel / timeout / cleanup hardening
4. file/shell front-door hardening
5. evidence/result contract hardening
6. request normalization hardening
