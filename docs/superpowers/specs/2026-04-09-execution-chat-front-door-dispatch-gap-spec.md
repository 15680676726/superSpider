# CoPaw Execution-Chat Front-Door Dispatch Gap Spec

## 0. Purpose

This spec records one confirmed runtime-chain problem as of `2026-04-09`.

It is not a new architecture proposal.

It is a truthful issue record for a specific execution gap that currently makes
parts of CoPaw feel like:

- "the main brain accepted the instruction"

instead of:

- "the main brain assigned work and the system started execution"

This spec exists so later fixes and audits do not dilute the problem into vague
phrases like "chat is not strong enough" or "autonomy is not smooth enough."

The concrete issue is narrower and more important:

- for a class of execution-core chat instructions, the current front door can
  persist formal backlog truth first
- but does not materialize and dispatch executable assignment truth in the same
  turn

That gap is enough to make the product feel closer to governed chat plus
recording than true execution-first delegation.

### 0.1 Validation Note (`2026-04-10`)

This spec now serves as an audit record of a gap that has been closed.

What changed after the original audit:

- execution-chat writeback now attempts same-turn cycle materialization when the
  target seat is already resolvable
- query-runtime commit/readback now prefers materialized assignment truth over a
  generic deferred summary
- the remaining "pending staffing / routing" path is now treated as a separate
  governed state, not as evidence that an execution-ready instruction was left
  waiting for the later automation sweep

So this document should now be read as:

- `archived audit record`
- not `current open front-door blocker`

---

## 1. Confirmed Judgment

The confirmed judgment is:

- the current long-term autonomy architecture is not itself the problem
- the current execution-chat front door is the problem
- specifically, "accepted instruction" and "started execution" can still be
  separated across two different runtime moments

In plain terms, the current chain can become:

- main brain accepted the operator instruction
- system wrote formal backlog / strategy / schedule truth
- system marked dispatch as deferred
- actual assignment materialization and dispatch happened later in the operating
  cycle chain

This is not the correct product behavior for instructions that are already
concrete enough to be treated as immediate execution work.

---

## 2. Confirmed Trace

The following trace is already confirmed in the current repo.

### 2.1 Chat writeback persists backlog truth

`IndustryService.apply_execution_chat_writeback(...)` in
[src/copaw/industry/service_lifecycle.py](/D:/word/copaw/src/copaw/industry/service_lifecycle.py)
records chat-originated execution intent through
`BacklogService.record_chat_writeback(...)`.

The writeback result explicitly returns:

- `created_backlog_ids`
- `dispatch_deferred`
- `delegated = False`

This means the function already admits that successful writeback does not always
mean immediate dispatch.

### 2.2 Kickoff only dispatches already-existing pending assignments

`IndustryService.kickoff_execution_from_chat(...)` in
[src/copaw/industry/service_lifecycle.py](/D:/word/copaw/src/copaw/industry/service_lifecycle.py)
does not create fresh assignments out of the newly written backlog item.

It starts from `_list_pending_kickoff_assignments(record)`.

If there are no pending kickoff assignments, it returns `None` or a blocked
result.

So this path is:

- dispatch existing pending assignment truth

not:

- materialize new assignment truth from the just-written chat backlog

### 2.3 Assignment materialization happens later in operating-cycle flow

Backlog-to-assignment materialization is handled by:

- `_materialize_backlog_into_cycle(...)`
- `run_operating_cycle(...)`

in
[src/copaw/industry/service_lifecycle.py](/D:/word/copaw/src/copaw/industry/service_lifecycle.py).

That chain:

- selects materializable open backlog
- starts or resumes an operating cycle
- creates assignments through `ensure_assignments(...)`
- marks backlog items `materialized`
- optionally dispatches materialized assignments

### 2.4 Operating-cycle dispatch is automation-driven by default

The operating-cycle chain is wired into the runtime automation loop in
[src/copaw/app/runtime_lifecycle.py](/D:/word/copaw/src/copaw/app/runtime_lifecycle.py).

The default operating-cycle interval is currently:

- `COPAW_OPERATING_CYCLE_INTERVAL_SECONDS`
- default value `180`

This means a newly accepted execution-core chat instruction can become:

- formally recorded now
- actually materialized and dispatched on the next automation sweep

### 2.5 Operating-cycle does auto-dispatch once it gets there

This spec is not claiming the later chain never dispatches.

`handle_run_operating_cycle(...)` in
[src/copaw/capabilities/system_team_handlers.py](/D:/word/copaw/src/copaw/capabilities/system_team_handlers.py)
passes `auto_dispatch_materialized_goals=True` by default.

So the current gap is not:

- "backlog is never executed"

The current gap is:

- "execution start can be delayed into the later operating-cycle chain instead
  of happening in the same front-door turn"

---

## 3. Product Impact

This gap produces four concrete product-level problems.

### 3.1 Main-brain acceptance is easy to misread as execution start

The operator can give a concrete instruction and receive a response that looks
accepted and durable.

But the actual system state may only be:

- backlog recorded
- strategy updated
- dispatch deferred

This makes the product feel like it accepted intent without starting work.

### 3.2 The system feels like chat plus recording

When execution does not start in the same turn, the user experiences:

- the main brain understood the instruction
- but the system did not immediately move into owned execution

That is the core reason the product can feel like governed chat instead of a
main-brain-led autonomous executor.

### 3.3 Frontend surfaces can overstate progress

Chat, Runtime Center, and Industry can all truthfully show that a formal change
happened.

But if the surface does not clearly separate:

- recorded
- materialized
- dispatched
- running

the user sees a softer version of the same problem:

- the system appears to have started, while it has only persisted intent

### 3.4 Long-term autonomy gets blamed for a front-door flaw

If this issue is described vaguely, it sounds like:

- "autonomy is too slow"
- "the cycle model is wrong"
- "the system became round-based"

That diagnosis is too broad.

The more accurate diagnosis is:

- long-term autonomy is valid
- but the front door still routes too many execution-ready instructions into the
  slower backlog/cycle path

---

## 4. What This Spec Does Not Claim

To avoid overcorrection, this spec explicitly does not claim the following.

### 4.1 Not every instruction should bypass backlog

Some operator instructions should still become:

- backlog
- schedule
- strategic review input
- governed waiting state

This spec only targets instructions that are already concrete enough to be
owned as immediate execution work.

### 4.2 This is not a rejection of cycle-based autonomy

Operating cycles remain the correct place for:

- backlog prioritization
- report follow-up materialization
- schedule-triggered work
- long-run cadence and re-entry

The issue is not that cycles exist.

The issue is that the front door still sends too much immediately actionable
work into the later cycle path.

### 4.3 This spec is not yet a fix design

This document records the issue and its boundaries.

It does not yet define the final implementation contract for:

- same-turn assignment materialization
- same-turn dispatch gating
- immediate-vs-backlog routing criteria

Those should be handled in a follow-up implementation plan.

---

## 5. Required Closure Direction

The intended closure direction should be:

1. execution-ready operator instructions should materialize assignment truth in
   the same turn
2. same-turn assignment truth should be dispatched in the same turn when risk
   and environment rules allow
3. backlog/cycle should remain the durable long-run planning plane, not the
   default sink for already-executable instructions
4. frontend surfaces must explicitly distinguish:
   - recorded
   - materialized
   - dispatched
   - running
   - blocked / waiting-confirm

The target product feeling should become:

- "I told the main brain to do something concrete"
- "the main brain immediately assigned it"
- "the execution seat started or clearly showed why it is blocked"

not:

- "the main brain wrote it down and the rest may happen later"

---

## 6. Follow-Up Audit Questions

This confirmed issue creates five follow-up audit questions that should be
tracked separately.

1. Which operator instructions should be classified as immediate execution
   instead of backlog-first?
2. Where is the safest same-turn materialization boundary:
   - query runtime
   - main-brain commit phase
   - industry lifecycle layer
3. Which current frontend states conflate accepted truth with started work?
4. Does the current evidence chain explicitly record:
   - formal object creation
   - assignment materialization
   - dispatch start
5. Which read models still hide this gap by collapsing missing wiring into empty
   arrays or neutral states?

---

## 7. Current Status

As of `2026-04-09`, this issue should be treated as:

- `confirmed`
- `product-critical`
- `not yet fixed`

As of `2026-04-10`, that judgment still stands.

The narrower accurate statement is:

- front-door routing and continuity have been tightened in several adjacent
  places
- but same-turn `writeback -> assignment materialization -> dispatch start`
  is still not a fully closed contract

Any claim that the execution-chat front door is already fully closed should
still be considered inaccurate until this same-turn dispatch gap is explicitly
removed or made intentionally visible.
