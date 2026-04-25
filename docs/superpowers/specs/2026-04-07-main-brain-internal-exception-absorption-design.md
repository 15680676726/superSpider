# 2026-04-07 Main-Brain Internal Exception Absorption Design

## 0. Purpose

This spec defines how CoPaw should absorb multi-agent runtime failures inside the main brain boundary.

The target is not:

- expose more multi-agent details to ordinary users
- add a second incident system
- add a heavy orchestration state machine next to the current runtime truth

The target is:

- keep the front stage as a single main-brain experience
- let the system detect internal stuck / blocked / degraded execution states
- let the system try recovery and replan automatically
- only ask the human for help when the main brain has exhausted safe autonomous recovery

---

## 1. Problem Statement

CoPaw already has partial internal runtime governance.

Today the system can already:

- prevent same-actor parallel execution with actor lease
- prevent shared writer conflicts with child-run writer lease
- heartbeat active execution
- classify runtime outcomes into `completed / waiting-confirm / cancelled / failed / timeout / blocked`
- recover orphaned mailbox items on startup
- convert repeated blocker pressure into formal replan signals
- keep `HumanAssistTask` as a formal host-side object

But these pieces have not yet been closed into one complete main-brain absorption loop.

The current gap is not "nothing exists."

The current gap is:

- detection exists, but not enough cross-agent stuck reasoning
- recovery exists, but not yet as one formal escalation ladder
- user-facing runtime language exists, but not yet as a strict main-brain translation boundary

That means the system is currently better than a raw multi-agent shell, but still weaker than the desired product rule:

> internal execution problems belong to the main brain first, not to the ordinary user.

---

## 2. Core Judgment

The right next step is not to show more multi-agent detail.

The right next step is to close a strict internal-exception absorption chain:

- detect
- absorb
- recover
- replan or reassign
- escalate to human only when necessary

This must reuse current runtime truth instead of creating a parallel incident product.

The official system-level interpretation should therefore be:

- multi-agent execution remains internal
- the main brain remains the only front-door persona
- runtime failures are first-class only inside canonical runtime/state/evidence objects
- human-visible output should be a main-brain conclusion, not raw scheduler detail

---

## 3. Hard Boundaries

This design must obey the repository rules:

- no second truth source
- no parallel main brain
- no new planner truth
- no user-facing multi-agent diagnostics as the default product surface
- no "install a monitoring system beside the runtime" shortcut

The formal truth must continue to live in existing objects:

- `AgentRuntimeRecord`
- actor mailbox item / checkpoint truth
- actor and writer lease state
- kernel task phase and decision request state
- `HumanAssistTaskRecord`
- report synthesis replan directives
- `EvidenceRecord`

If a new mechanism cannot be expressed as a derived layer over these objects, it is probably the wrong cut.

---

## 4. What Already Exists

The following current pieces are valid foundations and should be reused rather than replaced.

### 4.1 Runtime Detection Foundations

- `actor_supervisor.py`
  - runtime snapshot
  - `blocked_runtime_count`
  - `recent_failure_count`
- `actor_worker.py`
  - actor lease
  - heartbeat-wrapped task execution
- `runtime_outcome.py`
  - stable runtime outcome vocabulary

### 4.2 Conflict and Recovery Foundations

- `child_run_shell.py`
  - shared writer lease conflict boundary
- `actor_mailbox.py`
  - retry
  - orphan recovery
  - waiting-confirm recovery to blocked state
- startup recovery chain
  - stale runtime hydration and mailbox cleanup

### 4.3 Escalation Foundations

- `HumanAssistTaskService`
  - `mark_resume_queued(...)`
  - `mark_handoff_blocked(...)`
- decision request / waiting-confirm chain

### 4.4 Formal Replan Foundations

- `report_replan_engine.py`
  - `lane_reweight`
  - `cycle_rebalance`
- routine/runtime paths that already emit blocker and drift pressure

These foundations are enough to justify a closure pass.
They are not enough to claim the full loop is already finished.

---

## 5. The Three Missing Closures

Three closures are still missing.

### 5.1 Cross-Agent Stuck Watchdog

Today the system mainly knows about local failure and stale execution.

It still lacks a formal derived watcher for patterns such as:

- the same writer scope repeatedly blocking multiple actors
- one agent repeatedly waiting on confirm while downstream work keeps accumulating
- mailbox items that keep rotating through retry without net progress
- actor runtimes that heartbeat but do not produce useful state transitions

This should not become a new persistent incident graph.

It should become a derived watchdog pass over existing truth:

- mailbox status age
- runtime heartbeat age
- repeated lease conflict summaries
- waiting-confirm age
- retry count and retry cadence
- repeated blocker evidence across the same owner / seat / writer scope / assignment scope

### 5.2 Recovery Ladder

Recovery today exists in pieces.

It should become one explicit ladder:

1. local cleanup
   - release stale lease
   - recover orphaned mailbox item
   - requeue safe runnable work
2. bounded retry
   - retry with cooldown and budget
   - stop infinite spin
3. structural recovery
   - trigger reassignment
   - trigger lane reweight
   - trigger cycle rebalance
4. human escalation
   - only after autonomous recovery paths are exhausted

This ladder must be deterministic enough that the main brain can explain what happened.

### 5.3 Main-Brain Translation Boundary

The system still lacks a strict rule that converts internal runtime failure into a main-brain explanation.

The human should not see raw internal categories as the primary product surface:

- `leased`
- `retry-wait`
- `writer conflict`
- low-level actor/runtime drift

The user should instead receive a single main-brain conclusion:

- what is blocked
- what the system already tried
- whether the system has recovered
- whether human action is still required
- the exact next human action if one is required

This translation must be generated from canonical runtime/evidence truth, not from prompt-only wording.

---

## 6. Target Behavior

### 6.1 Default Product Behavior

The ordinary user sees the main brain, not the multi-agent backend.

When internal execution trouble happens:

- the main brain first tries to absorb it internally
- the user is not immediately asked to reason about scheduler state
- only unresolved boundary cases become a human request

### 6.2 Watchdog Behavior

The system should periodically derive stuck pressure from current truth and classify it into stable families such as:

- `stale-lease`
- `retry-loop`
- `waiting-confirm-orphan`
- `writer-contention`
- `progressless-runtime`
- `repeated-blocker-same-scope`

These families should stay derived and low-entropy.

They do not need a second giant ontology.

### 6.3 Recovery Behavior

The absorber should apply the lowest safe recovery step first.

Examples:

- orphaned running mailbox item -> recover and requeue
- stale writer lock -> release or expire and retry once
- repeated local failure on same seat -> stop local retry and request reassignment or replan
- waiting-confirm that already has an unresolved human boundary -> keep blocked, do not spin

### 6.4 Human Escalation Behavior

If human help is required, the main brain should surface one governed action, not internal complexity.

Good output shape:

- problem summary
- what was already attempted automatically
- why automation stopped
- one human action with acceptance criteria

This should usually map to existing `HumanAssistTask` truth.

---

## 7. Implementation Shape

The implementation should stay narrow and reuse current modules.

### 7.1 Watchdog Layer

Add a derived watchdog service that reads:

- actor runtime state
- mailbox state
- lease conflict evidence
- waiting-confirm age
- retry metadata

Recommended responsibility:

- compute a bounded list of active absorption cases
- classify the case family
- recommend the next recovery rung

This should be a service layer, not a new persistence subsystem.

### 7.2 Absorber Layer

Add an absorber service that consumes watchdog cases and executes the recovery ladder:

- cleanup
- retry
- requeue
- reassign or replan recommendation
- human escalation

It must write outcomes back through current runtime/state/evidence services.

### 7.3 Main-Brain Summary Layer

Add a summary builder that turns active absorption state into:

- main-brain-readable status
- operator-readable diagnostics
- human-visible next step only when needed

The front-door chat and runtime-center top cards should read this summary instead of inventing ad hoc wording.

---

## 8. Non-Goals

This spec does not:

- redesign the entire Runtime Center
- expose raw multi-agent topology to ordinary users
- introduce a second incident database
- replace the current mailbox/runtime model
- create a deep deadlock engine with full graph theory semantics
- make all human confirmations disappear

The goal is disciplined absorption, not fantasy autonomy.

---

## 9. Why This Is The Right Cut

This design matches the repository architecture and the desired product direction.

It is the right cut because it:

- keeps one main brain at the front
- keeps multi-agent complexity internal
- reuses current runtime truth instead of multiplying systems
- follows a low-entropy, single-path style closer to the desired single-loop discipline
- improves product usability without weakening governance boundaries

Most importantly:

- it fixes the product responsibility boundary
- normal users should not need to understand multi-agent internals
- the main brain should carry that burden by default

---

## 10. Acceptance Criteria

This work is complete when:

1. the system can derive stable stuck/blocked classes from current runtime truth without adding a second incident truth source
2. autonomous recovery follows a bounded, observable recovery ladder instead of scattered ad hoc retries
3. repeated internal failures can escalate into reassignment or replan rather than only local retry
4. human escalation is emitted as a main-brain conclusion with a concrete action, not raw scheduler details
5. the default product surface continues to present a single main-brain experience rather than exposing multi-agent internals
