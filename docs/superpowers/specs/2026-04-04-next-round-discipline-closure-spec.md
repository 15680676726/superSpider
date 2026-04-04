# CoPaw Next-Round Discipline Closure Spec

## 0. Purpose

This spec defines the next round of runtime/capability discipline work that is most worth doing after:

- single-loop main-brain chat closure
- governed capability lifecycle landing
- donor-first external capability assimilation design
- the current Claude-derived runtime hardening wave

This is not a new architecture.

It is a closure spec for the most important remaining discipline gaps so CoPaw keeps moving toward:

- low entropy
- single-path execution and discovery
- default autonomy
- donor-first growth
- compact governed portfolios

This spec is intentionally focused on discipline, not on adding more product surfaces.

---

## 1. Scope Judgment

The next round should not reopen already-closed top-level directions such as:

- main-brain chat front-door simplification
- single-loop chat/orchestrate split
- formal planning truth
- old `goal/task/schedule` product mindsets
- building a parallel donor manager

The next round should instead close the remaining discipline gaps that still threaten long-term autonomy quality.

If these gaps are not closed, CoPaw can still "work," but it will become:

- noisier
- more brittle
- harder to scale across donors and long tasks
- more prone to portfolio sprawl
- less trustworthy under long-running pressure

---

## 2. The Closure Target

The target state is:

- query/runtime stays clean under long turns
- discovery remains autonomous without turning into crawler entropy
- external donor intake remains resilient across regions and mirrors
- duplicate donor hits collapse into one governed truth
- shared writer work obeys one explicit contract
- child runs use one cleanup shell
- MCP/runtime overlays obey lifecycle discipline
- skill/package metadata becomes trustworthy enough for donor-first growth
- portfolios stay compact and replaceable instead of only expanding

These are the highest-value remaining discipline cuts.

---

## 3. Current Repo Gap Snapshot

This round exists because the current repo already has the architectural direction, but some discipline contracts are still only partial.

The most important current gap signals are:

- query runtime already has compaction and memory machinery, but not yet one explicit entropy contract for donor/trial-heavy long turns
- donor-first discovery direction is defined, but source-chain discipline is not yet fully formalized as one-active-source runtime behavior
- donor/package/source profile truth is starting to land, but multi-source normalization still needs to become the rule before candidate fan-out
- shared writer behavior exists in parts of browser/desktop/file flows, but not yet as one repo-wide read-concurrent/write-serialized contract
- worker/supervisor/delegation flows already do cleanup, but child-run startup and teardown semantics are still too distributed
- MCP governance has moved forward, but lifecycle meaning is still too easy to blur with simple install/connect state
- skill/package growth direction has changed to donor-first, but metadata discipline still needs to become strict enough to resist duplication and provenance drift
- portfolio governance exists conceptually, but density limits, replacement-first pressure, and hotspot cooling are not yet strong enough to prevent renewed entropy

This means the problem is no longer "what architecture do we want."

The problem is "which discipline contracts still need to be made explicit so the chosen architecture stays stable under long-term use."

---

## 4. What To Borrow From `cc`

The point is not to copy `cc` as a product.

The point is to continue borrowing the specific disciplines that matter most:

- low entropy
- one active path per action
- read concurrency / write serialization
- additive child-run shell
- strict metadata/provenance discipline
- compact portfolios instead of unbounded accumulation

What must still remain CoPaw-owned:

- formal truth chain
- lifecycle governance
- runtime evidence chain
- replacement power
- main-brain strategic control

So the rule remains:

- borrow runtime discipline from `cc`
- keep CoPaw's own truth and lifecycle center

---

## 5. The Eight Closure Packages

The next round should be tracked as eight closure packages.

They are ordered by architectural leverage rather than by implementation convenience.

### 5.1 Package A: Query Runtime Entropy Contract

This is the highest-priority remaining discipline gap.

The problem is not merely "prompt too long."

The real issue is that long-running turns still lack a sufficiently explicit contract for:

- tool-result budget
- microcompact / autocompact triggers
- carry-forward acceptance
- operator-visible entropy state
- bounded metadata carry-forward from donor discovery/trial flows

The goal is:

- keep the runtime clean under pressure
- avoid turning discovery/trial metadata into uncontrolled prompt growth
- make entropy visible as a formal runtime concern rather than hidden prompt drift

Hard rules:

- donor metadata must not flood long-turn context
- compaction must remain a runtime/evidence discipline, not a second memory truth source
- entropy degradation must be operator-visible

Primary landing zones:

- `src/copaw/kernel/query_execution_runtime.py`
- `src/copaw/memory/conversation_compaction_service.py`

### 5.2 Package B: Discovery Source Chain

This is the first donor-first runtime discipline cut.

The platform must support:

- `primary -> mirror -> fallback`
- region-aware source profiles
- graceful degradation
- last-known-good snapshot fallback

But every concrete discovery action should still use:

- one active source

The goal is:

- source resilience
- clean provenance
- simpler deduplication
- no discovery-induced runtime fragility

Hard rules:

- `source failure != runtime failure`
- one discovery action == one active source
- source misconfiguration may degrade discovery only

This matters especially for:

- mainland-China deployment
- hybrid onshore/offshore setups
- offline/private donor operation

### 5.3 Package C: Multi-Source Deduplication And Donor Normalization

Without this package, multi-source resilience will turn into candidate noise.

The system must normalize across:

- source-level duplication
- package identity duplication
- donor lineage duplication
- capability overlap
- portfolio compaction

The goal is:

- one donor family should not appear as many fake choices
- multiple source confirmations should strengthen confidence rather than multiply candidates
- portfolio counts should track normalized donors, not raw search hits

Recommended normalized identity signals:

- canonical package id
- source aliases
- candidate source lineage
- equivalence class
- overlap score
- replacement relation

### 5.4 Package D: Read Concurrent, Write Serialized

This is the core execution discipline for shared surfaces.

The current repo already has partial lease and preview discipline, but the next round should tighten it into one explicit contract:

- reads may run concurrently
- writes must serialize
- shared writer surfaces must require explicit reservation/lease
- donor-triggered writer work must obey the same contract as first-party work

This matters most for:

- file writes
- browser writes
- desktop writes
- document writes
- multi-agent shared surfaces

The goal is not a prettier locking story.

The goal is to make shared mutation predictable and verifiable.

### 5.5 Package E: Unified Child-Run Shell

The current worker/supervisor/delegation stack already has meaningful cleanup discipline, but it still needs to converge further into one shared child-run shell.

That shell should own:

- bounded inherited context
- additive scoped mounts
- startup wiring
- heartbeat
- finish/cancel/failure cleanup
- writer lease acquire/release discipline

This matters for:

- delegated execution
- donor scouting
- donor trial comparison
- scoped runtime experiments

The point is to prevent every new worker-style path from inventing its own cleanup semantics.

### 5.6 Package F: MCP Lifecycle Discipline

MCP must keep moving from "connected means usable" toward full lifecycle governance.

The next round should explicitly tighten:

- connect / replace / remove
- dirty state
- reload sequencing
- partial failure handling
- scoped overlays
- cleanup on shutdown or scope end

Under donor-first architecture, MCP is not special.

It is another donor class and must obey:

- candidate
- trial
- lifecycle decision
- rollback/retire

What must be removed over time is the hidden intuition that "installed and connected" means "formally adopted."

### 5.7 Package G: Skill / Package Metadata Discipline

This package is the capability-side counterpart of donor normalization.

The next round should formalize:

- source provenance
- frontmatter validation
- canonical path identity
- duplicate suppression
- path-scoped activation
- package-bound metadata summaries

This is especially important because CoPaw is now explicitly donor-first.

If metadata discipline stays weak, donor-first architecture will collapse into:

- prompt folders
- duplicated skills
- weak provenance
- messy package identity

This package also supports the new rule that:

- `local_authored` remains valid
- but it is fallback-only, not default growth mode

### 5.8 Package H: Portfolio Governance And Hotspot Cooling

This package closes the strategic discipline loop.

Part one is portfolio governance:

- per-role donor density limits
- per-seat donor density limits
- per-environment donor density limits
- trust memory
- replacement-first logic
- retirement / forgetting
- compact governed capability combinations

Part two is hotspot cooling:

- split orchestration hotspots only where that reduces contract concentration
- do not count cosmetic file moves as progress
- keep future donor/runtime discipline from collapsing back into giant files

The point is not code style.

The point is to keep future hardening work from reintroducing entropy through oversized orchestration hubs.

---

## 6. Suggested Landing Zones

This round should land in the current system rather than introduce a parallel subsystem.

Recommended landing zones:

- Package A should primarily land in `kernel/` and runtime compaction seams, not in a new memory truth
- Package B and Package C should primarily land in `state/`, discovery services, and query/runtime adapters that resolve active source selection
- Package D should land in shared writer primitives and environment/body mutation seams, not as ad hoc guards inside individual tools
- Package E should land in worker/supervisor/delegation runtime seams, not as another isolated child runtime implementation
- Package F should land in capability lifecycle/state services, governed mutations, and scope attach/remove flows
- Package G should land in capability metadata/state services plus installer/discovery adapters
- Package H should land in portfolio summary, governance, prediction, and replacement/retire decision seams

The important rule is:

- add missing discipline contracts to the current architecture
- do not invent a second architecture to hold them

---

## 7. Recommended Priority Sequence

The next round should not be treated as one flat backlog.

Recommended ordering:

### 7.1 Priority P0

- Package A: Query Runtime Entropy Contract
- Package B: Discovery Source Chain
- Package C: Multi-Source Deduplication And Donor Normalization

These three define whether donor-first autonomy stays clean enough to scale.

They must not be treated as an isolated cleanup phase.

Implementation rule:

- `P0` should be built together with the first donor-first external expansion wave
- not fully before it
- and not deferred until after it

In other words:

- the safe minimal donor expansion spine is `external assimilation chain + A/B/C`
- not `external assimilation chain` alone
- and not `A/B/C` as a detached internal-only hardening project

### 7.2 Priority P1

- Package D: Read Concurrent, Write Serialized
- Package E: Unified Child-Run Shell
- Package F: MCP Lifecycle Discipline
- Package G: Skill / Package Metadata Discipline

These four define whether execution and donor growth remain governable.

### 7.3 Priority P2

- Package H: Portfolio Governance And Hotspot Cooling

This package should close the loop after the lower contracts are strong enough.

---

## 8. Acceptance Standard

This next round should only be considered properly closed if it produces the following outcomes:

1. discovery source failure can no longer break runtime behavior
2. each discovery action has one active source with clear provenance
3. donor duplication is normalized before candidate expansion
4. long-turn entropy is visible, bounded, and contractually handled
5. shared writer work obeys one clear reservation contract
6. child-run cleanup no longer splits across multiple hidden shells
7. MCP donors no longer enjoy install/connect == adoption shortcuts
8. skill/package identity is provenance-safe and duplicate-resistant
9. donor portfolios stay compact and replaceable instead of only growing

If these outcomes are not met, the round should be treated as partial.

---

## 9. Explicit Non-Goals

This round should not be expanded into:

- another chat-front-door redesign
- a replacement planner truth model
- a second capability manager
- a giant UX redesign
- broad speculative crawler infrastructure
- renewed "main brain writes everything itself" product logic

These are distractions relative to the discipline gaps above.

---

## 10. Final Rule

The core standard for this round is:

- keep CoPaw low-entropy
- keep actions single-path
- keep autonomy default-on
- keep donor growth governed
- keep the platform compact enough to keep evolving

That is the closure target for the next round.
