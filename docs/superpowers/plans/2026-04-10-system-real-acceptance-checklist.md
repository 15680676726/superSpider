# CoPaw System Real Acceptance Checklist

> **For agentic workers:** This checklist is the post-runtime-gap acceptance plan. Use it to verify the system as a whole, in order, without inventing a second truth chain or turning the main brain into a leaf executor.

**Goal:** Verify that CoPaw now behaves like a main-brain-led execution system rather than a chat-first system with partial execution side effects.

**Architecture:** The main brain remains responsible for chat intake, understanding, planning, delegation, governance, and result synthesis. Real execution must still flow through `strategy / lane / backlog / assignment / specialist / task / report / evidence`, and every acceptance item below checks whether that formal chain is actually visible and durable.

**Tech Stack:** Python, FastAPI, pytest, console frontend, Runtime Center, Industry Workbench, Buddy flow, capability market, donor/runtime subsystem.

---

## 1. Scope and Honesty Rules

This checklist is not a marketing document.

- Passing unit tests alone does not count as full acceptance.
- Focused regression slices count as adjacency proof, not final end-to-end proof.
- Gated live smoke only counts as live proof when the exact command and environment are recorded.
- A chain only counts as accepted when the same truth is visible in:
  - backend formal object/state
  - frontend read model
  - refresh/re-entry/recovery path

This checklist should be read together with:

- [TASK_STATUS.md](/D:/word/copaw/TASK_STATUS.md)
- [2026-04-09-p0-runtime-gap-audit-ledger.md](/D:/word/copaw/docs/superpowers/specs/2026-04-09-p0-runtime-gap-audit-ledger.md)
- [2026-04-09-runtime-gap-closure-priority-plan.md](/D:/word/copaw/docs/superpowers/plans/2026-04-09-runtime-gap-closure-priority-plan.md)

---

## 2. Acceptance Definition

The system is only considered "really accepted" for a scenario when all of the following are true:

1. The operator can trigger the scenario from the real front door.
2. The main brain produces the correct formal next step.
3. A real execution seat or runtime owns the action when execution is required.
4. Evidence and report truth are durable and queryable.
5. Chat, Runtime Center, Industry, and other relevant surfaces tell the same story.
6. Refresh, reconnect, or re-entry does not silently lose the truth.

### 2.1 Mandatory Reconciliation Record

Every accepted scenario must record one explicit reconciliation bundle.

The scenario does **not** count as accepted unless the same chain can be
pointed to in all of the following:

- database/formal truth ids
  - example: `industry_instance_id`, `assignment_id`, `task_id`,
    `decision_request_id`
- API/read-model truth
  - example: chat payload, Runtime Center detail payload, Industry detail payload
- frontend-visible truth
  - the actual page state after refresh/re-entry
- evidence/report truth
  - at least one `EvidenceRecord` id or `AgentReport` id when work should have
    produced them

This is the default anti-fake-success rule for the whole checklist.

---

## 3. Current High-Level Status

As of `2026-04-10`, the runtime-gap audit set has been closed in code, but whole-system acceptance still needs to be proven at scenario level.

Current interpretation:

- The core runtime chain is no longer in the earlier "chat + record it for later" state.
- The main brain boundary is correct:
  - chat intake
  - task understanding and planning
  - delegation and orchestration
  - risk governance
  - synthesis and writeback
- Real execution is still expected to happen through:
  - `Assignment`
  - `specialist / execution seat`
  - `task / capability / environment`
  - `AgentReport / Evidence`

What remains is not another broad architecture audit.
What remains is scenario-by-scenario acceptance.

---

## 4. Acceptance Tracks

### Track A: Buddy / Domain / Carrier Entry

**Why this matters**

This proves the system can enter a real long-running operating context, not just create a profile-looking shell.

**Primary checks**

- [ ] Create or restore a Buddy direction through the formal onboarding path.
- [ ] Confirm a real active domain capability exists.
- [ ] Confirm the domain owns the correct execution carrier continuity.
- [ ] Confirm `/chat`, `/industry`, and Runtime Center resolve the same active carrier.
- [ ] Confirm refresh/reopen does not reopen an obsolete or synthetic thread.

**Pass condition**

An active Buddy/domain can be created or resumed without the frontend falling back to an empty state, duplicate carrier, or wrong control thread.

**Key surfaces**

- Buddy onboarding
- Industry workbench
- Chat
- Runtime Center buddy summary

**Key backend truth**

- `BuddyDomainCapabilityRecord`
- active industry runtime / control thread continuity

---

### Track B: Main Brain Intake -> Formal Delegation

**Why this matters**

This is the line between "chat software" and "main-brain-led execution system".

**Primary checks**

- [ ] Send an operator instruction that is clearly execution-oriented.
- [ ] Confirm the main brain classifies it as executable, backlog-worthy, or confirm-required.
- [ ] If executable, confirm the same turn creates or activates formal execution truth rather than stopping at a textual acknowledgement.
- [ ] Confirm the resulting state is visible as one of:
  - recorded but pending
  - materialized
  - dispatched
  - running
  - blocked / guarded / confirm-required
- [ ] Confirm the next refresh shows the same state and not a reset to plain chat.

**Pass condition**

The main brain visibly delegates to the execution chain without becoming the executor itself.

**Key surfaces**

- chat runtime status
- Runtime Center task/detail surfaces
- Industry execution view

**Key backend truth**

- intake contract
- backlog / assignment
- dispatch / runtime state
- commit outcome

---

### Track C: Assignment -> Specialist -> Real Work

**Why this matters**

A formal assignment is only meaningful if a real execution seat takes ownership and produces real work.

**Primary checks**

- [ ] Confirm a formal `Assignment` is produced when execution should happen.
- [ ] Confirm a real specialist/execution seat becomes owner.
- [ ] Confirm the seat selects capability + environment instead of stopping at planning truth.
- [ ] Confirm task progression can be observed beyond assignment creation.
- [ ] Confirm the final result lands as `AgentReport` plus evidence.

**Pass condition**

An assignment is not just stored; it is picked up, executed, and closed by a real execution seat.

**Key surfaces**

- Runtime Center assignment/task detail
- Agent workbench
- Industry runtime cockpit

---

### Track D: Capability Install -> Real Use

**Why this matters**

This proves the system is not just a package inventory manager.

**Primary checks**

- [ ] Install a capability from the real front door:
  - skill
  - MCP
  - project/runtime donor
- [ ] Confirm install truth is durable.
- [ ] Confirm the capability is actually attached or adopted by the target execution seat when intended.
- [ ] Confirm the next execution turn can really select and use it.
- [ ] Confirm success is not merely "installed in inventory".

**Pass condition**

Capability install leads to actual execution availability on the intended seat/runtime path.

**Key surfaces**

- Capability Market
- Runtime Center capability surfaces
- seat/effective capability read model

---

### Track D2: Capability Gap -> Auto Supplement -> Temporary Seat -> Optimization Writeback

**Why this matters**

This proves the system does not collapse into "I can't do that" whenever an
execution seat lacks one surface.

**Primary checks**

- [ ] Trigger a real task where the intended specialist seat lacks a needed capability.
- [ ] Confirm the system first tries the intended professional seat instead of
      immediately bouncing to chat-only explanation.
- [ ] Confirm the system can distinguish:
  - attachable capability gap
  - non-attachable gap
  - one-off temporary work
- [ ] Confirm attachable gaps attempt formal supplement through capability
      acquisition/trial/attach.
- [ ] Confirm only unresolved or one-off work falls through to a temporary seat.
- [ ] Confirm the final outcome writes back into the optimization chain so the
      same gap does not remain pure one-off rescue work forever.

**Pass condition**

The system prefers "make the right execution seat able to do the work", uses a
temporary seat only as a fallback, and durably records the outcome for future
optimization.

**Key surfaces**

- Chat
- Runtime Center capability/state surfaces
- Capability Market
- optimization / prediction / lifecycle read surfaces

---

### Track E: Environment Continuity

**Why this matters**

Long-running work cannot depend on re-explaining the world every turn.

**Primary checks**

- [ ] Start with a real environment-bearing task.
- [ ] Confirm the system holds a formal environment/session reference.
- [ ] Confirm a later turn can resume from the same environment continuity.
- [ ] Confirm environment truth is not faked by a bare symbolic ref.
- [ ] Confirm recovery/re-entry still resolves the live or correctly degraded state.

**Pass condition**

Browser/desktop/document/runtime continuity is durable enough to support multi-turn execution rather than prompt-only reconstruction.

**Key surfaces**

- Runtime Center environment detail
- chat runtime sidebar
- startup recovery / runtime re-entry surfaces

---

### Track F: Evidence / Report / Writeback

**Why this matters**

Without durable evidence and reports, the system cannot prove work happened or learn from it.

**Primary checks**

- [ ] Confirm external work produces formal `EvidenceRecord` truth.
- [ ] Confirm completed execution produces `AgentReport`.
- [ ] Confirm the result is visible in the operating chain, not just in logs.
- [ ] Confirm important transitions have durable acceptance/closure proof where required.
- [ ] Confirm the next planning/synthesis path can consume the result.

**Pass condition**

Real work leaves durable evidence and feeds the formal report/writeback chain.

**Key surfaces**

- Runtime Center reports/details
- Industry summaries
- evidence-linked task or report views

---

### Track G: Human Assist / Host Handoff / Resume

**Why this matters**

This is where a supposedly autonomous system most easily collapses into "the task disappeared".

**Primary checks**

- [ ] Create a real human-assist task through the formal producer path.
- [ ] Confirm the task appears in chat and runtime surfaces.
- [ ] Submit evidence or completion from the real front door.
- [ ] Confirm `accepted / need_more_evidence / resume_queued / resumed` are all visible and not silently swallowed.
- [ ] Confirm resume returns work to the real execution chain.

**Pass condition**

Human assist behaves like a governed interruption in the same runtime chain, not like a detached side quest.

---

### Track H: Frontend Truth Consistency

**Why this matters**

A system can have correct backend truth and still feel broken if each surface tells a different story.

**Primary checks**

- [ ] Compare the same live scenario across:
  - Chat
  - Runtime Center
  - Industry
  - Agent workbench where relevant
- [ ] Confirm status words are consistent.
- [ ] Confirm empty states only appear when the formal truth is actually empty.
- [ ] Confirm deferred/pending/running/blocked states are not turned into misleading "active" or "nothing here".

**Pass condition**

Different surfaces expose the same truth in different views, not different truths.

---

### Track I: Long-Run Autonomy

**Why this matters**

This proves the system can keep going after the first visible success.

**Primary checks**

- [ ] Start a real multi-step operating thread.
- [ ] Confirm the main brain can continue planning and dispatching over time.
- [ ] Confirm specialist work, evidence, and reports continue to accumulate.
- [ ] Confirm schedules/automation are not merely configured but visibly progressing.
- [ ] Confirm the system still reads as a running operation after delay/re-entry, not as a static chat transcript.

**Pass condition**

The system continues to operate as a governed autonomous runtime instead of collapsing back into single-turn chat behavior.

---

### Track J: Workflow / Cron / Self-Optimization Loop

**Why this matters**

This proves the system is not only interactive, but can also improve and push
its formal operating chain forward through scheduled and workflow-driven paths.

**Primary checks**

- [ ] Trigger a real workflow or cron-driven execution path.
- [ ] Confirm the path reaches the same formal chain:
  - strategy / lane / backlog / assignment / specialist / report / evidence
- [ ] Confirm main-brain optimization or recommendation output can feed the next
      formal cycle instead of staying in analysis text only.
- [ ] Confirm the next workflow/cron turn actually consumes the updated truth.
- [ ] Confirm read models show progression, not just configured automation.

**Pass condition**

Workflow, cron, and optimization form one durable operating loop rather than
three disconnected subsystems.

**Key surfaces**

- Runtime Center automation
- workflow preview / run detail
- Industry execution view
- optimization / recommendation read surfaces

---

### Track K: Temporal Grounding

**Why this matters**

If the system gets `today / tomorrow / Monday / Beijing time` wrong, it will
mis-plan real work even when the rest of the chain is technically healthy.

**Primary checks**

- [ ] Ask time-sensitive questions in the real front door:
  - current date
  - current weekday
  - current Beijing time
  - relative day references such as `today / tomorrow / next Monday`
- [ ] Confirm the answer matches current grounded runtime time, not model guesswork.
- [ ] Confirm refresh/re-entry does not switch to a different implicit date.
- [ ] Confirm scheduled and workflow-facing summaries use the same grounded time basis.

**Pass condition**

Time-sensitive reasoning is grounded to real runtime time instead of free-form
model guessing.

---

### Track L: Failure Injection / Fail-Closed Behavior

**Why this matters**

A chain that only works when everything is healthy can still hide dangerous
fake-success paths.

**Primary checks**

- [ ] Inject a model timeout.
- [ ] Inject a tool/runtime failure.
- [ ] Inject a missing capability attachment.
- [ ] Inject a handoff/resume interruption.
- [ ] Inject an environment continuity break.
- [ ] Confirm the system:
  - surfaces the failure explicitly
  - stops the affected path cleanly
  - does not silently continue with fabricated success
  - leaves durable failure truth for replay and recovery

**Pass condition**

The system fails closed, leaves visible truth, and does not disguise broken
execution as successful progress.

---

## 5. Execution Order

Run acceptance in this order:

1. Track A: Buddy / Domain / Carrier Entry
2. Track B: Main Brain Intake -> Formal Delegation
3. Track C: Assignment -> Specialist -> Real Work
4. Track F: Evidence / Report / Writeback
5. Track H: Frontend Truth Consistency
6. Track G: Human Assist / Host Handoff / Resume
7. Track D: Capability Install -> Real Use
8. Track D2: Capability Gap -> Auto Supplement -> Temporary Seat -> Optimization Writeback
9. Track E: Environment Continuity
10. Track K: Temporal Grounding
11. Track J: Workflow / Cron / Self-Optimization Loop
12. Track L: Failure Injection / Fail-Closed Behavior
13. Track I: Long-Run Autonomy

Reasoning:

- First prove the operating identity and carrier are real.
- Then prove the main brain delegates correctly.
- Then prove real work, evidence, and surfaces stay aligned.
- Then prove capability growth, environment continuity, grounded time, and
  failure behavior.
- Finally prove the longer workflow/automation loop and long-run autonomy.

---

## 6. What Counts as "System Basically Complete"

The system can reasonably be described as "basically complete" when:

- Tracks A through L pass on real or gated-real acceptance, with exact commands,
  reconciliation bundles, and scenarios recorded.
- Track I has at least one honest long-run acceptance case showing continued
  autonomous progression.
- No core surface regresses back to:
  - chat-only acknowledgement
  - false empty state
  - false active state
  - invisible deferred/resume state
  - fake capability availability
  - fake time grounding
  - fake success after hard failure

The system should still not be described as "final forever".
It should instead be described as:

> The core runtime and orchestration system is closed enough for real use, and the remaining work is on stronger live acceptance, expansion, and long-run maturity.

---

## 7. Immediate Next Step

The next execution phase should not be another broad audit.

It should be:

- selecting one real scenario per track
- running the acceptance in order
- recording exact commands, outcomes, reconciliation bundles, and any new breakpoints
- only opening a new issue when a scenario fails on the formal chain

That is the shortest path from "code looks complete" to "system is truly accepted".
