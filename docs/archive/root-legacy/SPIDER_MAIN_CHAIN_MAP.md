# Spider Main Chain Map

Status: current as of `2026-03-25` after the hard-cut autonomy rebuild.

This file is a concise runtime map for the chain that is actually live now.
It replaces the old goal-dispatch description that no longer matches the code.

The authoritative companions are:

- [TASK_STATUS.md](/D:/word/copaw/TASK_STATUS.md)
- [docs/superpowers/specs/2026-03-25-copaw-full-architecture-map-and-hard-cut-redesign.md](/D:/word/copaw/docs/superpowers/specs/2026-03-25-copaw-full-architecture-map-and-hard-cut-redesign.md)

---

## 1. Current Formal Chain

The current formal main chain is:

`bootstrap or operator turn`
-> `KernelTurnExecutor`
-> `MainBrainChatService` or `MainBrainOrchestrator`
-> `StrategyMemoryRecord`
-> `OperatingLaneRecord`
-> `BacklogItemRecord`
-> `OperatingCycleRecord`
-> `AssignmentRecord`
-> `TaskRecord`
-> `KernelDispatcher / ActorMailbox / ActorWorker`
-> `EvidenceRecord`
-> `AgentReportRecord`
-> `report synthesis / replan / strategy sync`

Key rule:

- `GoalRecord / ScheduleRecord` may still exist as leaf compatibility objects
- they are no longer the main-brain planning truth
- the formal operating-cycle path does not materialize backlog into new goals first

---

## 2. Visible Runtime Projection

`GET /api/runtime-center/industry/{instance_id}` now exposes the same runtime chain through:

- `execution`
- `main_chain`

The shared supervision chain shown in `/industry`, `Runtime Center`, and `AgentWorkbench` is:

`writeback`
-> `backlog`
-> `cycle`
-> `assignment`
-> `report`
-> `replan`

The runtime model still keeps leaf execution nodes such as:

- `routine`
- `child-task`
- `evidence`

Those nodes are derived from the same state and evidence objects, not from log parsing.

---

## 3. Single Sources Of Truth

Read the current system like this:

- team carrier and lifecycle: `IndustryInstanceRecord`
- long-horizon direction: `StrategyMemoryRecord`
- lane ownership and routing: `OperatingLaneRecord`
- queued work and writeback landing zone: `BacklogItemRecord`
- current operating loop: `OperatingCycleRecord`
- execution envelope: `AssignmentRecord`
- concrete leaf execution: `TaskRecord` plus `TaskRuntimeRecord`
- delegated child execution: `TaskRecord.parent_task_id`
- evidence and replay trail: `EvidenceRecord`
- structured worker return: `AgentReportRecord`

These are not primary truth anymore:

- prompt text that says what the team is "doing"
- a single operator chat message
- frontend-local reconstructed chain wording
- old `goal/task/schedule` planning views

---

## 4. Chat vs Orchestrate

Current split:

- `MainBrainChatService`: pure chat, state explanation, conversation memory
- `MainBrainOrchestrator`: formal execution/orchestration ingress

Important status:

- `MainBrainChatService` no longer performs background `writeback/kickoff`
- durable operator execution turns go through `MainBrainOrchestrator`

---

## 5. Bootstrap Contract

There are now two important bootstrap contracts:

### Default bootstrap contract

`IndustryBootstrapRequest.auto_activate` currently defaults to `true`.

That means public bootstrap enters the live contract unless the caller explicitly turns it off:

- goals are activated
- schedules are enabled
- runtime can enter `learning` or `coordinating` directly
- a second chat kickoff is not required to "start"

### Explicit conservative contract

If bootstrap passes `auto_activate = false`, the industry instance stays in the conservative waiting state:

- `autonomy_status = waiting-confirm`
- goals remain paused
- schedules remain disabled
- chat kickoff is still required

This is why the retirement regression now asserts live `learning` semantics for the default bootstrap contract, and only expects `waiting-confirm` when bootstrap explicitly opts into the conservative mode.

---

## 6. Operating-Cycle Contract

The repaired operating-cycle path is:

`BacklogItemRecord`
-> `AssignmentRecord`
-> assignment-backed `TaskRecord`
-> terminal task reconciliation
-> `AgentReportRecord`
-> synthesis / replan / strategy sync

Important repairs now in place:

- no eager goal fan-out from chat writeback
- no formal `goal -> task` bridge inside `run_operating_cycle()`
- report reconciliation prefers `assignment_id`
- when no live task exists, `main_chain.routine` can re-anchor to the latest report-linked assignment/task metadata so completed SOP runs remain visible

---

## 7. Child Tasks And Closure

Child tasks are still real kernel tasks.

The parent/child closure rule remains:

- parent tasks do not close before live child tasks close
- terminal child state flows back through the kernel
- industry/runtime views read the same task store and runtime store

What changed is where the parent task sits in the larger brain chain:

- it is now a leaf under `Assignment`
- it is not the top-level planning object anymore

---

## 8. Current Risks

The main remaining risks are architectural tail, not fake delegation:

- residual `GoalRecord` compatibility still exists in leaf services
- industry and frontend runtime surfaces are still heavy modules
- larger aggregate regression coverage still needs to expand
- memory/media closure is not fully finished

---

## 9. Practical Reading Order

If you need the live chain quickly, read in this order:

1. [TASK_STATUS.md](/D:/word/copaw/TASK_STATUS.md)
2. [docs/superpowers/specs/2026-03-25-copaw-full-architecture-map-and-hard-cut-redesign.md](/D:/word/copaw/docs/superpowers/specs/2026-03-25-copaw-full-architecture-map-and-hard-cut-redesign.md)
3. [src/copaw/industry/service_lifecycle.py](/D:/word/copaw/src/copaw/industry/service_lifecycle.py)
4. [src/copaw/industry/service_runtime_views.py](/D:/word/copaw/src/copaw/industry/service_runtime_views.py)
5. [src/copaw/kernel/turn_executor.py](/D:/word/copaw/src/copaw/kernel/turn_executor.py)
