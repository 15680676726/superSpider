# CoPaw Formal Planning Capability Gap Design

## Goal

Define the remaining gap between:

- CoPaw's current formal planning chain
- Claude Code's borrowable planning/runtime discipline
- the complete short/mid/long-horizon planner CoPaw still needs

This document exists to answer one precise question:

> after borrowing Claude Code's execution shell and planning shell ideas, what formal planning capability still needs to be built inside CoPaw itself?

It does not replace:

- `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
- `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`
- `docs/superpowers/specs/2026-04-01-claude-runtime-contract-hardening-design.md`

It narrows the planning question to:

- what CoPaw already has
- what Claude Code can really donate
- what Claude Code cannot donate
- what must be built as CoPaw's own formal planner

---

## 1. Core Judgment

CoPaw already has the correct formal planning truth chain.

That chain is:

`StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> synthesis/replan`

This is closer to CoPaw's target than Claude Code's session/task/todo/plan-file mental model.

But CoPaw still does not yet have a complete formal planner.

The current situation is:

- the formal planning objects exist
- strategy-aware context injection exists
- cycle/review/replan has partial machinery
- but the planner is still too rule-driven, too local, and too shallow in horizon handling

So the real upgrade target is:

- keep CoPaw's formal planning truth
- borrow Claude Code's planning shell and execution discipline
- build the remaining formal short/mid/long-horizon planner inside CoPaw

---

## 2. What CoPaw Already Has

### 2.1 Formal strategic truth already exists

`StrategyMemoryRecord` already holds:

- `mission`
- `north_star`
- `priority_order`
- `lane_weights`
- `planning_policy`
- `current_focuses`
- `paused_lane_ids`
- `review_rules`

See:

- `src/copaw/state/models_reporting.py`
- `src/copaw/state/strategy_memory_service.py`

This means CoPaw is not missing a strategic truth object.

It is missing a stronger compiler from that truth into formal planning behavior.

### 2.2 Formal planning objects already exist

The current state layer already includes:

- `OperatingLaneRecord`
- `BacklogItemRecord`
- `OperatingCycleRecord`
- `AssignmentRecord`
- `AgentReportRecord`

See:

- `src/copaw/state/models_goals_tasks.py`
- `V7_MAIN_BRAIN_AUTONOMY_PLAN.md`

So CoPaw does not need Claude Code's task/todo/session model as a new planning truth.

### 2.3 Strategy and memory already enter lower planning/compile paths

Current code already injects:

- strategy context
- knowledge and memory context
- activation-derived memory items and refs

into goal compilation and prompt assembly.

See:

- `src/copaw/goals/service_compiler.py`
- `tests/app/test_goals_api.py`

This means CoPaw is not planning blind.

It already has a strategy-aware and memory-aware planning base.

### 2.4 Cycle review and report synthesis already exist

Current code already has:

- cycle review case creation
- report synthesis
- follow-up backlog materialization
- prediction cycle deduplication

See:

- `src/copaw/industry/service_lifecycle.py`
- `src/copaw/predictions/service_core.py`
- `tests/app/test_predictions_api.py`

This means CoPaw already has the beginning of a review-driven planner.

---

## 3. What Is Still Too Weak In Current CoPaw Planning

### 3.1 Cycle start is still mostly rule-driven

Current cycle start logic is still close to:

- if backlog exists, start
- if due time arrived and there are pending reports, start

See:

- `src/copaw/state/main_brain_service.py`

This is enough for a live chain.

It is not enough for a mature planner that understands:

- competing horizons
- lane budgets
- strategic timing
- uncertainty-driven review
- multi-cycle sequencing

### 3.2 Cycle materialization is still shallow

Current cycle materialization still does things like:

- rank open backlog
- pick top few backlog items
- start a fixed `daily` cycle

See:

- `src/copaw/industry/service_lifecycle.py`

This is useful, but it is not yet a real horizon planner.

It is still close to:

- local prioritization
- short-window selection
- thin cycle typing

### 3.3 Strategy fields exist, but they are not yet a strong planning compiler

Fields such as:

- `planning_policy`
- `review_rules`
- `lane_weights`
- `paused_lane_ids`

already exist in strategy memory and persistence.

But the current system still relies more on:

- local sorting
- per-surface writeback
- report follow-up
- cycle review sidecars

than on a strong formal strategy compiler that turns strategic truth into:

- lane investment policy
- cycle selection policy
- review cadence policy
- horizon-aware planning constraints

### 3.4 Assignment planning is still stronger as execution shell than as formal planner

CoPaw already has assignment objects.

But the system still lacks a strong assignment-local planning shell that formally handles:

- internal decomposition
- checkpoints
- success criteria
- retry policy
- dependency ordering
- bounded scratch planning

This is exactly where Claude Code's planning shell is useful.

---

## 4. What Claude Code Can Really Donate

Claude Code should be treated here as a donor of planning shell discipline, not planning truth.

### 4.1 Directly borrowable

These ideas can be borrowed almost directly in adapted form:

1. plan-mode discipline
   - read-only planning pass before mutation when needed
2. plan artifact discipline
   - a sidecar planning artifact that can be revised incrementally
3. todo/checklist discipline
   - bounded task checklist inside one run or assignment
4. single-turn planning closure
   - think -> inspect -> update plan -> continue or exit
5. context entropy control
   - compaction, summaries, bounded carry-forward
6. worker/subagent run shell
   - startup, additive tooling, finish-time cleanup

### 4.2 Borrowable only after adaptation

These are useful, but only after remapping into CoPaw's formal model:

1. `plan file`
   - should become assignment-local planning scratch or operator-visible sidecar artifact
   - must not become formal planning truth
2. `todo/session task list`
   - should become assignment checklist or execution-local planner scratch
   - must not replace backlog/cycle/assignment
3. `plan agent`
   - should become a planning assistant under main-brain or assignment scope
   - must not become the strategic center
4. `query summaries`
   - should become assignment/cycle review aides
   - not the formal report object itself

### 4.3 Not borrowable as system center

These should not be adopted as CoPaw's primary planning model:

1. session-first planning truth
2. todo/task/app-state as formal planner center
3. plan file as canonical strategic memory
4. Claude's top-level planner replacing `StrategyMemory/Lane/Backlog/Cycle`

---

## 5. Formal Planning Gaps By Horizon

## 5.1 Short-horizon planner gaps

Short horizon means:

- this cycle
- this assignment
- this execution window

Still missing or too weak:

1. assignment-local planning shell
   - explicit step decomposition
   - bounded checklist
   - stop conditions
   - acceptance criteria
   - retry/escalation criteria
2. dependency-aware sequencing
   - not just "top items first"
   - but "what must happen before what"
3. capacity-aware assignment shaping
   - who can take what now
   - with what environment/body/session availability
4. checkpointed execution planning
   - what can be verified mid-run
   - what requires human checkpoint
   - what should write back before continuing
5. local plan revision after evidence
   - when new evidence changes the current assignment path

Claude Code helps strongly here through:

- planning shell
- todo shell
- context control
- execution closure discipline

But CoPaw must still formalize these around:

- `Assignment`
- `Task`
- `AgentReport`
- `WorkContext`

## 5.2 Mid-horizon planner gaps

Mid horizon means:

- multiple cycles
- daily/weekly/event rhythm
- lane balancing over time

Still missing or too weak:

1. richer cycle typing
   - not only thin `daily`
   - but formal daily/weekly/event review and launch contracts
2. lane budget allocator
   - how much attention/capacity each lane gets this round
3. carry-over policy
   - what rolls from one cycle into the next
   - what expires
   - what gets downgraded or escalated
4. review cadence policy
   - strategy-driven review timing
   - uncertainty-triggered review
   - not only due-time or backlog existence
5. report-to-replan compiler
   - structured interpretation of repeated failures, blocked work, partial progress, and contradictions

Claude Code helps only indirectly here.

Its main contribution is:

- making assignment and turn-level planning cleaner
- making review inputs less noisy

But the formal mid-horizon planner must be built in CoPaw around:

- `OperatingLane`
- `BacklogItem`
- `OperatingCycle`
- `Assignment`
- `AgentReport`

## 5.3 Long-horizon planner gaps

Long horizon means:

- strategic mission
- months-scale direction
- lane weighting and structural priority
- continued adaptation over long operation

Still missing or too weak:

1. strategy compiler
   - compile `mission / north_star / priority_order / lane_weights / planning_policy / review_rules`
     into formal planning constraints
2. lane investment model
   - sustained attention allocation across lanes
   - not only backlog sort order
3. strategic assumption and uncertainty register
   - what the brain believes
   - what is unverified
   - what needs deliberate review
4. long-range replanning triggers
   - when repeated report evidence should change strategy, not just create follow-up backlog
5. horizon coupling
   - how long-term mission constrains mid-cycle lane allocation and short-horizon assignment decomposition

Claude Code does not provide this planner.

This must be built natively in CoPaw.

---

## 6. Final Classification

### 6.1 Claude Code can directly help with

- assignment-local planning shell
- checklist/todo discipline
- turn/worker execution closure
- context entropy control
- review input cleanup
- subagent run shell

### 6.2 Claude Code can help only after adaptation

- sidecar planning artifact
- plan assistant
- review summary shell
- bounded assignment planner workspace

### 6.3 Claude Code cannot replace

- strategy compiler
- lane allocator
- cycle materializer
- report-to-replan compiler
- horizon coupling model
- formal planning truth chain

These are CoPaw-native planner responsibilities.

---

## 7. Recommended Build Order

To finish the complete planning capability gap cleanly, the order should be:

Important naming note:

- `Phase P-1` here is a planning-program phase label used only inside this planning-gap build order.
- It is not the same thing as the historical `2026-04-01 P0 / P1 / P2` landed wave recorded in `2026-04-01-claude-runtime-contract-hardening-design.md`.
- The historical `P0 / P1 / P2` record tracks Claude-derived runtime-contract hardening closure.
- The `P-1 -> P-5` sequence below tracks the staged completion order for CoPaw's remaining formal planning capability.

### Phase P-1: Finish Claude-derived runtime/planning shell hardening

Use Claude Code ideas for:

- execution front-door
- planning shell
- todo/checklist shell
- context entropy control
- worker/MCP/skill discipline

This improves short-horizon execution maturity.

### Phase P-2: Add assignment-local formal planner

Build inside CoPaw:

- assignment plan envelope
- checkpoints
- acceptance criteria
- retry/escalation policy
- bounded planning scratch linked to formal assignment truth

### Phase P-3: Add cycle planner

Build inside CoPaw:

- richer cycle kinds
- cycle selection policy
- lane budget allocation
- carry-over rules
- review cadence compiler

### Phase P-4: Add strategy compiler

Build inside CoPaw:

- compile strategic truth into lane and cycle constraints
- formalize uncertainty/review rules
- produce strategic reweighting triggers

### Phase P-5: Add report-to-replan engine

Build inside CoPaw:

- repeated-failure interpretation
- contradiction interpretation
- opportunity uplift logic
- strategy-change vs follow-up-backlog decision logic

---

## 8. Success Standard

This planning gap is considered closed only when:

1. short-horizon assignment planning is explicit, bounded, and checkpointed
2. cycle generation is no longer just "backlog exists -> pick top items -> daily cycle"
3. strategy fields such as `lane_weights`, `planning_policy`, and `review_rules` are compiled into real planning behavior
4. report synthesis can trigger more than local follow-up; it can formally reshape cycle and strategy decisions
5. Claude-derived planning shell remains sidecar and does not become a second strategic truth source

---

## 9. Landed Shape (`2026-04-02`)

The `2026-04-01` formal planning implementation wave has now landed as a real compiler/runtime slice:

- `StrategyPlanningCompiler`
- `CyclePlanningCompiler`
- `AssignmentPlanningCompiler`
- `ReportReplanEngine`

They are now wired through the real CoPaw chain:

- strategy memory compiles into typed planning constraints
- operating-cycle materialization persists `formal_planning` sidecars on `OperatingCycle` and `Assignment`
- prediction cycle review now reuses formal planning overlap context instead of creating a planning-blind review shell
- goal compilation carries assignment-local planning envelopes as sidecar compiler context
- Runtime Center / industry detail now expose `main_brain_planning` as a read model, not a second truth source

This means the current gap closure should be read as:

- short-horizon planning is now explicit and typed
- mid-horizon cycle/replan shaping is no longer only thin local rule glue
- Claude-derived planning shell remains bounded sidecar discipline

What is now explicitly closed by the `2026-04-02` implementation round:

- `FP-6 Strategic Uncertainty Register`
  - now lands as typed `StrategicUncertaintyRecord` truth on strategy memory
  - compiles through `StrategyPlanningCompiler`
  - stays visible in goal compile context, prediction planning overlap, and runtime `main_brain_planning`
- `FP-7 Strategy-Change Trigger Engine`
  - now lands as typed `ReportReplanDecision.decision_kind`
  - emits governed `follow_up_backlog / cycle_rebalance / lane_reweight / strategy_review_required`
  - stays visible in prediction snapshots, runtime cognition, runtime replan nodes, and prompt/runtime context
- `FP-8 Multi-Cycle Lane Budget Compiler`
  - now lands as typed `LaneBudgetRecord` truth on strategy memory
  - compiles through `StrategyPlanningCompiler`
  - is consumed by `CyclePlanningCompiler` before local lane-weight tie-breaking

This design line no longer carries an open FP-6/7/8 tail.

If future work wants richer horizon logic beyond this closure, it must start a new dated spec instead of silently reopening this gap document with vague “follow-up” language.

Those items are not an open-ended "keep optimizing planning" bucket.

They are the remaining bounded post-closure backlog for formal planning, and this
document should be read as closed once these items are either delivered or
explicitly deferred into a new dated design doc.

## 10. Explicit Post-Closure Backlog

The remaining work is only the following three items.

If a future request does not map to one of these items, it must not be smuggled
in under "planning follow-up". It needs a new spec.

### 10.1 FP-6: Strategic Uncertainty Register

Problem to solve:

- the current chain can compile strategy into cycle and assignment planning
- but it still lacks a typed place to record what is uncertain, what evidence can
  invalidate the current strategy, and when uncertainty should force review

Deliverable:

- add a typed `strategic_uncertainties` sidecar under the formal planning chain
- the register must stay attached to existing planner truth, not create a second
  planning truth source

Minimum object shape:

- `uncertainty_id`
- `statement`
- `scope`
  - `strategy`
  - `lane`
  - `cycle`
- `impact_level`
  - `low`
  - `medium`
  - `high`
- `current_confidence`
- `evidence_for_refs`
- `evidence_against_refs`
- `review_by_cycle`
- `escalate_when`
  - repeated blocker
  - confidence drop
  - target miss

Why this exists:

- faster: avoids running the same local follow-up loop for a strategic unknown
- more accurate: forces the system to distinguish "task failure" from
  "strategy may be wrong"
- more stable: review timing becomes explicit instead of depending on whichever
  report happened to arrive last

Exit criteria:

1. a typed uncertainty register exists in the formal planning path
2. cycle planning can consume uncertainty state as an input constraint
3. report/replan logic can update uncertainty confidence and review timing
4. Runtime Center or industry detail can expose the register read-model
5. regression tests prove uncertainty state survives `strategy -> cycle ->
   assignment -> report -> replan`

CC donor map:

- borrow:
  - plan shell discipline from `cc/src/commands/plan/plan.tsx`
  - plan file persistence / resume / fork handling from `cc/src/utils/plans.ts`
  - lightweight todo/checklist shell from `cc/src/utils/todo/types.ts`
- do not borrow:
  - planner truth
  - uncertainty object model
  - strategy review decision logic

Reason:

- Claude Code can donate assignment-local planning scratch and durable plan-file
  behavior
- Claude Code does not have CoPaw's formal truth chain
  `StrategyMemory -> Lane -> Backlog -> Cycle -> Assignment -> Report`
- therefore the uncertainty register must remain a CoPaw-native formal-planning
  sidecar, not a transplanted plan/todo file

Implementation rule:

- use the CC donor only for operator-visible shell and planner scratch behavior
- persist uncertainty truth on CoPaw planning objects and runtime read-models
- if a future implementation stores uncertainty only in plan files, todo state,
  or transient prompt scratch, that implementation does not satisfy FP-6

### 10.2 FP-7: Strategy-Change Trigger Engine

Problem to solve:

- today the system is still biased toward creating local follow-up backlog
- it still needs a formal way to decide when repeated evidence should reshape
  strategy, not just generate another assignment

Deliverable:

- add typed strategy-change trigger evaluation to the report-to-replan path
- the engine must emit one of a small fixed decision set rather than vague prose

Required decision set:

- `follow_up_backlog`
- `cycle_rebalance`
- `lane_reweight`
- `strategy_review_required`

Required trigger families:

- repeated blocker across cycles
- repeated assignment miss against the same lane objective
- confidence collapse on a tracked uncertainty
- repeated contradiction from synthesis / activation / report evidence

Why this exists:

- faster: prevents wasting cycles on assignments that should have been stopped at
  strategy level
- more accurate: strategy changes are driven by explicit evidence patterns
- more closed-loop: the system can prove why it generated backlog versus why it
  escalated to strategy review

Exit criteria:

1. `ReportReplanEngine` emits typed strategy-change decisions
2. the emitted decision is persisted in formal planning sidecars
3. backlog creation is no longer the only default output path
4. regression tests prove repeated evidence can produce each decision kind
5. old shallow "always follow-up backlog" branches are deleted where replaced

CC donor map:

- borrow:
  - review/planning shell discipline from `cc/src/commands/plan/plan.tsx`
  - read-only explore-before-decide behavior from `cc/src/tools/AgentTool/built-in/planAgent.ts`
  - bounded review artifact habits from the plan/todo shell
- do not borrow:
  - trigger taxonomy
  - strategy escalation decisions
  - backlog vs cycle vs strategy review routing truth

Reason:

- Claude Code has a strong planning/review shell but not a formal
  `report -> replan -> strategy review` engine
- CoPaw still has to own the decision set
  `follow_up_backlog / cycle_rebalance / lane_reweight / strategy_review_required`
- the trigger engine must therefore be implemented inside
  `ReportReplanEngine` and formal-planning sidecars, not by copying a generic
  planning-agent workflow

Implementation rule:

- CC can inform how review work is staged and explained
- CC must not become the source of decision categories or escalation truth
- if a future implementation cannot show typed trigger inputs, typed decision
  outputs, and persisted rationale on CoPaw objects, it does not satisfy FP-7

### 10.3 FP-8: Multi-Cycle Lane Budget Compiler

Problem to solve:

- current formal planning is good enough for one cycle and one assignment chain
- it still does not strongly encode how lanes should be funded or throttled over
  multiple cycles

Deliverable:

- compile `lane_weights`, review policy, and current pressure into a typed
  multi-cycle lane budget output
- the output must constrain cycle materialization, not just annotate it

Minimum output shape:

- `lane_id`
- `budget_window`
- `target_share`
- `min_share`
- `max_share`
- `review_pressure`
- `defer_reason`
- `force_include_reason`

Why this exists:

- faster: stops low-value lanes from stealing assignment slots every cycle
- more accurate: lane selection becomes a compiled result instead of local sort
- more predictable: cycle generation can be explained against visible budgets

Exit criteria:

1. strategy compilation emits typed lane budget outputs
2. cycle planning consumes those outputs during candidate selection
3. industry/runtime read surfaces expose lane budget state
4. regression tests prove lane budget can suppress, defer, and force-include
   backlog items across more than one cycle

CC donor map:

- borrow:
  - context entropy control from `cc/src/services/compact/autoCompact.ts`
  - microcompact / tool-result-budget discipline from
    `cc/src/services/compact/microCompact.ts` and
    `cc/src/utils/toolResultStorage.ts`
  - additive agent-MCP shell from `cc/src/tools/AgentTool/runAgent.ts` only
    where multi-cycle planning needs bounded worker context
- do not borrow:
  - lane model
  - budget model
  - cycle compiler
  - multi-cycle allocation policy

Reason:

- Claude Code does not have `lane_weights`, `planning_policy`,
  `review_rules`, or a multi-cycle budget compiler
- the useful donor value is operational discipline: keep planning context
  bounded, keep subagent/tool shells additive, and avoid context rot over long
  runs
- the actual lane budget output must remain a CoPaw-native strategy compiler
  product

Implementation rule:

- use CC patterns to keep the compiler readable, resumable, and bounded
- keep all budget math and lane-allocation truth in CoPaw planning objects
- if a future implementation only annotates cycles with lane hints but does not
  constrain materialization with typed budget outputs, it does not satisfy FP-8

## 10.4 Donor Boundary Summary

For `FP-6 -> FP-8`, Claude Code is a donor of shell and discipline, not of
planner truth.

Allowed borrow classes:

- plan file lifecycle
- assignment-local planning scratch
- todo/checklist shell
- read-only planning/review staging
- context entropy control
- additive agent-specific MCP shell

Forbidden borrow classes:

- strategic truth objects
- lane/cycle/assignment/report planner truth
- strategy-change decision taxonomy
- lane budget compiler outputs

Hard rule:

- if a future implementation copies CC artifacts without anchoring the result to
  CoPaw's formal planning objects, that implementation is out of architecture
  and should be rejected

## 11. Closure Rule For This Design

This design must not be treated as an evergreen "planning keeps improving"
document.

For this document, formal planning is considered closed when:

1. the landed `P-1 -> P-5` chain remains green
2. `FP-6 -> FP-8` are either delivered with tests or explicitly moved into a new
   dated follow-up spec
3. no active status note keeps using vague language such as "planning can still
   get better" without naming object, trigger, output, and exit criteria

Anything outside those boundaries is a new project, not a hidden tail on this
one.

---

## 12. One-Sentence Summary

Claude Code can help CoPaw plan better inside a run, an assignment, and a review loop.

It cannot replace the formal short/mid/long-horizon planner that CoPaw still needs to build on top of its own `StrategyMemory -> Lane -> Backlog -> Cycle -> Assignment -> Report` truth chain.
