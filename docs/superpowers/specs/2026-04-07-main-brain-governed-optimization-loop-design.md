# 2026-04-07 Main-Brain Governed Optimization Loop Design

## 1. Purpose

This document defines the full "second-tier" end state for CoPaw's self-optimization loop.

The goal is not "let the system randomly evolve itself."

The goal is:

- let the main brain periodically review real operating facts
- discover optimization opportunities
- formalize them into governed cases
- run scoped baseline-vs-challenger trials
- evaluate them with evidence
- promote / rollback / retire the better option
- keep the whole loop visible in Runtime Center

This design intentionally reuses the current truth chain instead of creating a second optimization system.

---

## 2. Core Judgment

CoPaw should not add a parallel "evolution engine" next to the main brain.

CoPaw should turn the existing pieces into one governed optimization loop:

- main-brain morning/evening review cadence
- prediction-style discovery and recommendation intake
- external-source / package / candidate / trial / lifecycle truth
- MCP runtime diagnostics
- Runtime Center governance read-model

In plain terms:

- `review cadence` is the trigger
- `prediction/discovery` is the problem-finding layer
- `candidate/trial` is the experiment layer
- `lifecycle` is the governed mutation layer
- `Runtime Center` is the operator-visible surface

The system must not split these into separate products with separate state words.

The official system-level name should therefore be:

- `Main-Brain Governed Optimization Loop`

The following names are allowed only as sub-slices inside that loop:

- `prediction` = discovery intake
- `candidate/trial/lifecycle` = experiment and mutation chain
- `MCP runtime` = external capability runtime slice

They must not keep competing as top-level system names.

---

## 3. Hard Boundaries

The full loop must obey the repository rules:

- no second truth source
- no parallel main brain
- no fourth capability semantics
- no external-source install == formal adoption
- no prompt-only hidden optimization state

The loop must remain under CoPaw's canonical chain:

- `StrategyMemory`
- `OperatingLane / BacklogItem / OperatingCycle / Assignment / AgentReport`
- `CapabilityDonorRecord / CapabilityPackageRecord / CapabilityCandidateRecord`
- `SkillTrialRecord`
- `CapabilityLifecycleDecisionRecord`
- `EvidenceRecord`
- `DecisionRequest`

Nothing in this design may bypass governance, evidence, or the main brain's final authority.

---

## 4. What Counts As "Second Tier"

The correct second-tier scope is wider than capability evolution, but narrower than "auto-rewrite the whole system."

It contains six formal segments.

### 4.1 Cadence Trigger

The loop begins from durable review cadence:

- morning review
- evening review
- cycle review
- anomaly review
- explicit operator-requested review

These are not chat niceties. They are optimization triggers.

### 4.2 Discovery Intake

The loop then discovers pressures from:

- repeated task failure
- runtime degradation
- underperforming active capability
- missing capability
- operator feedback
- repeated human intervention
- recovery friction
- source/package drift
- MCP runtime instability

The current "prediction" layer should be treated as this discovery intake layer.

### 4.3 Optimization Case

Every real optimization opportunity should become a formal optimization case.

The system should not rely on loose recommendations alone.

The optimization case must answer:

- what is wrong or improvable
- where it was observed
- what evidence supports it
- which capability family it touches
- what baseline is currently active
- what challenger is proposed
- what scope is safe for trial
- what success and rollback criteria apply

Recommended implementation rule:

- reuse current `PredictionCaseRecord` as the current discovery-case truth
- evolve its semantics into "optimization case" instead of creating a parallel record

### 4.4 Trial Runtime

The system must run real scoped trials, not just materialize packages.

Required trial discipline:

- baseline vs challenger must be explicit
- trial scope must be explicit
- trial owner must be explicit
- evidence attribution must be explicit
- trial must be seat/session/agent scoped by default
- role-wide promotion is never the first move

This trial runtime must cover:

- skill candidates
- MCP candidates
- external-source-backed packages
- local fallback artifacts

### 4.5 Evaluator

The system needs one formal evaluator layer that decides whether the challenger actually won.

It must use:

- success rate
- failure rate
- latency
- operator intervention rate
- handoff/recovery pressure
- evidence quality
- drift after activation

The evaluator must produce a stable verdict such as:

- continue_trial
- keep_baseline
- promote
- rollback
- retire

### 4.6 Lifecycle Apply

Only after evaluation should the system perform governed mutation:

- promote_to_role
- keep_seat_local
- replace_existing
- rollback
- retire

This must continue to reuse the existing lifecycle chain instead of creating a new optimizer-owned apply path.

---

## 5. What Stays Reused

This design is intentionally not a rewrite.

The following current pieces are the right building blocks:

- morning/evening review triggers
- prediction discovery and recommendation generation
- prediction-to-main-brain handoff
- external-source / package / candidate truth
- skill trial records
- lifecycle decision records
- MCP runtime contract and diagnostics
- Runtime Center capability-governance projection

The change is not "throw these away."

The change is:

- stop treating them as separate mini-systems
- make them read and behave like one optimization loop

---

## 6. What Must Change

The current system is close, but not yet the full second tier.

Four real gaps remain.

### 6.1 Prediction Must Downgrade Into Discovery

`prediction` is currently doing part of the right work, but the name is too narrow.

Its correct role is:

- discovery intake
- recommendation drafting
- review-case creation

It should not continue to imply "a separate center that owns optimization by itself."

### 6.2 Trial Must Be Unified Across Skill And MCP

Skill evolution is currently the most mature slice.

MCP already has runtime truth and diagnostics, but it is not yet fully symmetric with skill trial/lifecycle semantics.

The second tier requires:

- one trial discipline across skill and MCP
- one evaluator contract across skill and MCP
- one lifecycle decision vocabulary across skill and MCP

It also requires one complete missing-capability closure path for MCP:

- detect the missing MCP capability during real work
- match an existing client, install-template, builtin runtime, or governed external candidate
- enable or install it through governance
- run it in scoped trial
- then let lifecycle decide whether it stays local, promotes, rolls back, or retires

Current reality is only partial:

- existing MCP clients can already be discovered and enabled
- missing MCP capabilities can already produce recommendations and candidate paths
- but the full autonomous "detect -> match -> install/enable -> trial -> lifecycle" path is not yet as hard or as smooth as skill

Closing that asymmetry is a first-batch requirement, not a later polish item.

### 6.3 Evaluator Must Become Explicit

Today the loop has recommendations and lifecycle pressure, but not yet a first-class unified evaluator contract.

The second tier requires an explicit layer for:

- baseline/challenger comparison
- trial score aggregation
- formal verdict generation

### 6.4 Runtime Center Must Show The Whole Loop

Runtime Center can already show parts of this.

But the final surface must show:

- what issue was discovered
- what candidate was proposed
- what trial is running
- what baseline is being challenged
- what evidence was collected
- what decision was made
- what is currently degraded

Without this, the loop is real but still hard to operate.

### 6.5 Review Results Must Flow Back Into Main Brain Truth

Today reviews can trigger discovery and recommendations, and the main brain can receive the handoff.

That is not enough for the full second tier.

The loop must also feed long-horizon consequences back into main-brain truth, including:

- which capability families should be preferred less in future planning
- which source profiles lost trust
- which trial patterns became validated local heuristics
- which replacement or retirement pressures should become recurring planning constraints
- which review findings should reopen strategy or operating-lane decisions

In plain terms:

- the system must not merely "run a trial"
- it must learn what that trial means for future planning and future capability choices

The writeback targets should be explicit, not left as vague "learning happened somewhere."

At minimum, review-to-lifecycle closure must be able to write back into:

- main-brain planning constraints for future assignment and capability choice
- provenance trust truth for future provenance-weighted decisions
- capability portfolio pressure so repeated weak families stay visible
- future discovery and review pressure so unresolved patterns re-enter review cadence
- strategy or operating-lane reopen signals when the finding is large enough to change direction

Without this, the system experiments, but does not truly accumulate governed operating judgment.

---

## 7. Formal Loop

The full second-tier loop should be:

1. review cadence triggers analysis
2. discovery layer detects an optimization pressure
3. the system opens or refreshes an optimization case
4. the main brain decides whether the case is worth acting on
5. external-source/package/candidate resolution proposes the challenger
6. scoped trial mounts challenger against the current baseline
7. runtime evidence is collected
8. evaluator scores baseline vs challenger
9. lifecycle decision is created
10. governed apply promotes / rolls back / retires
11. review results write back into main-brain truth, provenance trust, and future planning pressure
12. Runtime Center projects the whole loop
13. later reviews measure post-activation drift and reopen the case if needed

This is the real second-tier end state.

---

## 8. Skill, MCP, And Donor Boundary

All three must participate, but not at the same layer.

### 8.1 Skill

Skill is usually the most direct challenger artifact.

It already has:

- candidate
- trial
- lifecycle

Skill should remain the most mature artifact slice.

### 8.2 MCP

MCP is primarily:

- runtime capability supply
- live environment access
- protocol-bound external leverage

MCP must not remain "runtime diagnostics only."

It should be allowed to enter the same optimization loop through:

- candidate resolution
- scoped trial
- evaluator
- lifecycle decision

MCP governance boundary must also be explicit.

The safe default is:

- auto-enable only for already-known local MCP clients that are currently disabled, already compatible, and whose trial scope stays seat-local or agent-local
- guarded enable/install for install-template or builtin-runtime challengers when the scope is still narrow and rollback is clear
- stronger governed approval for brand-new external installs, destructive replacement of an active runtime, or any role-wide rollout

In plain terms:

- "existing but off" can be comparatively cheap
- "newly install and trial in a narrow lane" can be guarded
- "replace broadly or introduce a new external dependency" must be treated as a bigger governance decision

### 8.3 Donor / Package

Donor/package truth is the provenance and supply layer.

It answers:

- where the challenger came from
- whether it is trusted
- which package lineage is active
- whether replacement or retirement pressure exists

It is not the optimization loop by itself, but it is required input to the loop.

### 8.4 Scope Of Apply

Skill and MCP optimization should default to the acting unit, not the whole system.

That acting unit can be:

- the main brain itself
- a specific professional agent
- a specific seat/session/agent-local runtime scope

The default rule is:

- trial locally
- judge globally
- promote deliberately

In plain terms:

- the execution target is usually a single acting unit
- the governance, evidence, trust update, and learning writeback belong to system truth
- system-wide replacement is never the first move

So the correct boundary is not:

- "single agent optimization only"

and not:

- "system-wide rollout by default"

The correct boundary is:

- local apply scope first
- global truth and governance always
- broader rollout only after explicit lifecycle decision

---

## 9. What Must Not Be Built

To avoid another architecture split, the second tier must not create:

- a separate optimizer brain
- a separate optimization database
- a separate apply path
- a skill-only optimizer that excludes MCP
- an MCP-only manager that bypasses lifecycle
- a Runtime Center page that invents a new state vocabulary

The system should evolve by tightening the current chain, not by adding another one.

---

## 10. End-State Read Model

The Runtime Center end state should expose a single optimization surface with at least:

- discovery queue
- active optimization cases
- running trials
- promoted challengers
- rollback pressure
- retirement pressure
- degraded capability families
- source/package provenance
- MCP runtime health inside the same story

The minimum operator-visible fields for each case should include:

- issue source
- discovery case id
- baseline
- challenger
- trial scope
- owner
- evaluator verdict
- lifecycle decision
- provenance trust impact
- planning impact
- rollback or recovery route

This is the point where the loop becomes actually operable, not just architecturally correct.

---

## 11. One-Sentence Summary

The correct full second tier is:

`main-brain-controlled review cadence + discovery intake + unified optimization case + scoped baseline/challenger trial + explicit evaluator + governed lifecycle apply + Runtime Center full-loop visibility`

and not merely:

`capability evolution in isolation`.

---

## 12. Delivery Scope

To avoid endless drift, the second-tier loop should be delivered in three explicit batches.

### 12.1 Batch 1: Must Enter The Loop

These pieces are required for the loop to exist at all:

- main-brain morning / evening / cycle review cadence
- prediction discovery intake
- reporting / performance metrics
- skill / external-source / candidate / trial / lifecycle chain
- MCP runtime as a governed challenger source
- Runtime Center full-loop visibility

In plain terms, Batch 1 is:

- trigger
- discover
- measure
- trial
- decide
- show

Without Batch 1, the system still has pieces, but not a real self-optimization loop.

### 12.2 Batch 2: Strong Enhancers

These pieces should enter once Batch 1 is stable because they materially improve optimization quality:

- workflow preview and assignment-gap detection
- provenance trust and capability portfolio pressure
- knowledge-graph activation and relation traversal
- strategy / planning constraints as optimization boundaries

These are not optional forever.

They are the first serious quality upgrades after the base loop is alive.

### 12.3 Batch 3: Explicitly Deferred

These should not be forced into the optimization loop now:

- generic chat history
- loose human-preference fragments
- pure frontend configuration toggles
- direct self-modification of mainline source code

They are too soft, too noisy, or too risky relative to the current maturity target.

The correct rule is:

- Batch 1 makes the system able to optimize
- Batch 2 makes it optimize better
- Batch 3 stays outside until the platform is much more mature

---

## 13. Landed Boundary (`2026-04-07`)

This second-tier loop is now live at the current repository boundary with these pieces wired end to end:

- prediction records act as the formal discovery intake
- optimization cases project from the existing truth chain instead of a parallel object
- skill and MCP challengers can both enter a scoped trial contract
- evaluator verdicts write back into lifecycle decisions
- Runtime Center shows actionable/history optimization cases with projection details
- review -> discovery -> main-brain handoff -> trial -> lifecycle -> Runtime Center readback has a passing e2e path

What is intentionally still outside this landed boundary:

- generic chat-history optimization
- pure frontend configuration tuning
- self-modifying source-code optimization
- broader strategy-quality enhancers that are useful but not required for the loop to exist

What old wording is now superseded:

- the older `autonomous capability evolution` document is the capability-evolution slice, not the whole loop
- `latest decision` in the optimization read-model must mean the current recommendation/case decision, not just the latest candidate-global decision
