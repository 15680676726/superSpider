# CoPaw External Capability Assimilation Architecture

## 0. Purpose

This spec defines how `CoPaw` should absorb external capabilities without turning the platform into a second-rate copy of every tool it can find.

The target is not "self-implement everything."

The target is:

- keep `CoPaw` as the formal autonomy carrier
- treat external projects as capability supply
- let the main brain discover, trial, compare, adopt, replace, and retire those capabilities through the existing formal object chain

This spec is architecture-level guidance. It does not replace the formal object model in `DATA_MODEL_DRAFT.md`, the runtime/kernel rules in `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`, or the current capability-governance work already landed in runtime/state.

---

## 1. Core Judgment

`CoPaw` should be a platform and carrier, not a "rewrite the ecosystem" product.

The platform must own:

- truth
- runtime orchestration
- risk governance
- evidence
- lifecycle decisions

The platform should not insist on owning every implementation detail of:

- skills
- MCP servers
- browser/desktop/document adapters
- provider/runtime helper components
- reusable open-source execution subsystems

The long-term competitive edge is therefore not "how many functions CoPaw writes itself."

It is:

- whether CoPaw can continuously absorb better external capabilities
- whether those capabilities can be governed without breaking formal runtime truth
- whether the system can improve its active capability portfolio over time without human micromanagement

---

## 2. Architecture Boundary

### 2.1 What CoPaw Must Own

The following remain first-party and cannot be outsourced:

- `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport`
- `CapabilityCandidate -> SkillTrial -> CapabilityLifecycleDecision`
- `EnvironmentMount / SessionMount / WorkContext`
- `EvidenceRecord / replay / recovery`
- `auto / guarded / confirm`
- final execution and completion judgment
- Runtime Center projections and operator-visible truth

These are not "features." They are the carrier's governing skeleton.

### 2.2 What External Donors May Supply

External donors may supply execution capability, implementation leverage, or reusable runtime modules, including:

- open-source projects or subsystems
- skills
- MCP servers
- browser / desktop / document adapters
- provider / runtime helper components

These are supply-side inputs. They are never the source of formal runtime truth.

### 2.3 Hard Rule

Three rules must remain absolute:

- `CoPaw owns truth`
- `CoPaw owns lifecycle`
- `CoPaw owns replacement power`

No donor may bypass those three.

---

## 3. Main Brain Core Competence Boundary

The main brain is not a chat persona, not a skill writer, and not a donor router.

Its core competence is:

- understanding operator intent and constraints
- compiling intent into formal objects
- deciding execution ownership and progression
- governing risk
- judging evidence quality
- governing capability lifecycle
- preserving continuity across control threads, work contexts, and environments
- taking final responsibility for result quality

The main brain may use external donors, but external donors do not replace the main brain's governing role.

Therefore:

- donor selection is a governed optimization act
- donor usage is an execution act
- donor promotion is a lifecycle act
- none of the above redefine what the main brain is

---

## 4. Unified Donor Universe

All donor types must normalize into one formal capability-evolution chain.

The source may differ, but lifecycle semantics may not.

### 4.1 Donor Categories

Recommended normalized donor categories:

- `skill`
- `mcp-bundle`
- `adapter`
- `runtime-component`
- `project-package`

### 4.2 Formal Records

Recommended formal records:

- `CapabilityDonorRecord`
  - identifies the external source, reputation, provenance, integrity, and compatibility boundary
- `CapabilityPackageRecord`
  - identifies the actual package/project/bundle/artifact that was imported or made available
- `CapabilityCandidateRecord`
  - identifies a trial-ready candidate, regardless of source
- `SkillTrialRecord`
  - identifies scoped evaluation and runtime attribution
- `CapabilityLifecycleDecisionRecord`
  - identifies promote / replace / rollback / retire decisions

### 4.3 Hard Lifecycle Rule

The following must always be false:

- install success == formal adoption
- cloned project == active capability
- file written == promoted skill
- package available == role-wide capability

Every donor must pass through the same lifecycle chain before formal adoption.

---

## 5. Unified Capability Assimilation Chain

All external capability assimilation must follow:

`discover -> evaluate -> candidate -> scoped trial -> evidence -> lifecycle decision -> promote/replace/rollback/retire`

### 5.1 Discover

Discovery only identifies possible leverage. It must not mutate formal runtime capability state.

### 5.2 Evaluate

Evaluation scores a donor for fit, safety, environment compatibility, role relevance, and likely leverage.

### 5.3 Candidate

`CapabilityCandidateRecord` is the first point where a donor becomes formal system state.

Before candidate state, a donor is only an external possibility.

### 5.4 Scoped Trial

Trial is the default proving mechanism.

Trial must prefer:

- seat-scoped
- session-scoped
- agent-scoped

Trial must avoid immediate role-wide adoption unless a stronger governance tier explicitly allows it.

### 5.5 Evidence

Evidence must come from actual execution effect, not only from:

- package install logs
- import success
- static metadata
- prompt claims

### 5.6 Lifecycle Decision

Formal lifecycle decisions are:

- `continue_trial`
- `promote_to_role`
- `keep_seat_local`
- `replace_existing`
- `rollback`
- `retire`

These decisions are formal state transitions, not implicit side effects.

---

## 6. Discovery Model

External discovery must not be implemented as continuous platform crawling.

Constant GitHub/registry polling would create:

- uncontrolled cost
- noise inflation
- low-signal candidate floods
- donor pollution
- portfolio entropy

Recommended discovery model is:

- `gap-driven`
- `performance-driven`
- `bounded periodic review`
- `opportunity-driven`

### 6.1 Gap-Driven Discovery

Trigger when the system encounters a real capability hole:

- repeated failure on the same task family
- no suitable donor in the current portfolio
- role/environment mismatch
- persistent inability to execute a required class of work

### 6.2 Performance-Driven Discovery

Trigger when an existing donor underperforms:

- too many failures
- too much latency
- too much operational friction
- poor evidence quality
- high recovery/handoff rate

### 6.3 Bounded Periodic Review

Allow low-frequency, budget-bounded review of:

- already adopted donors
- allowlisted ecosystems
- already trusted registries
- version updates for high-importance donors

This is a health review, not full-market crawling.

### 6.4 Opportunity-Driven Discovery

This exists for the real-world case where a newly appearing project is useful before any explicit gap has been logged.

Typical triggers:

- trusted ecosystem release feeds
- trusted author/org updates
- explicit donor watchlists
- high-value market signals from already relevant ecosystems

This should behave as a low-frequency radar, not as broad continuous scraping.

### 6.5 Discovery Budget Discipline

Discovery must always be bounded by:

- source whitelist / watchlist
- time budget
- candidate budget
- evaluation budget
- adoption budget

Discovery is useful only if it improves execution leverage more than it increases portfolio entropy.

---

## 7. Discovery Source Topology And Regional Resilience

Discovery must not assume a globally reachable source topology.

For many deployments, including mainland-China environments, GitHub may be:

- unavailable
- unstable
- too slow
- policy-blocked

That must not break the carrier.

### 7.1 Active Source Chain

CoPaw should not treat GitHub as the mandatory singular source.

Instead it should maintain a source priority chain such as:

- `primary`
- `mirror`
- `fallback`

Examples:

- `github -> domestic mirror -> cached snapshot`
- `trusted registry -> internal mirror -> last-known-good snapshot`

### 7.2 Single Active Source Per Discovery Action

To avoid noisy duplicate intake, each concrete discovery or refresh action should use exactly one active source.

This means:

- the system may keep multiple configured sources
- but each specific discovery run activates only one source from the chain
- if that source fails, the run may retry against the next source
- the successful source must be recorded in provenance

The target is:

- resilient source topology
- single-source execution per discovery action
- cleaner provenance and simpler deduplication

### 7.3 Regional Source Profiles

CoPaw should support source profiles such as:

- `global`
- `china-mainland`
- `hybrid`
- `offline/private`

Normal users should not have to manually assemble complex source graphs.

The platform should ship region-appropriate defaults, and the main brain should be able to health-check and switch active sources automatically.

### 7.4 Degrade Discovery, Never Runtime

Source outage or source misconfiguration must only degrade:

- discovery
- refresh
- update checking

It must never break:

- main-brain operation
- existing donor execution
- current runtime tasks
- already adopted capabilities

Hard rule:

- `source failure != runtime failure`

### 7.5 Last-Known-Good Snapshot

The platform should retain last-known-good snapshots for:

- donor catalogs
- source metadata
- trust memory
- allowlists/watchlists

This lets discovery degrade gracefully when external sources are not reachable.

---

## 8. Autonomous Scout And Opportunity Radar

CoPaw should be able to scout for better external capabilities by itself.

The right model is not "human manually finds everything."

The right model is:

- the system scouts like a human engineer
- but within bounded source chains, curated surfaces, and governed trial discipline

### 8.1 Opportunity Radar

Not all useful donors are discovered through explicit failure or missing capability.

Some donors are worth evaluating because they newly appear and obviously expand future leverage.

So opportunity-driven discovery should explicitly include curated radar surfaces such as:

- trending boards
- weekly top charts
- recent release lists
- newly published project rankings
- trusted org / trusted author release feeds
- trusted ecosystem watchboards

### 8.2 Radar Boundaries

Opportunity radar must remain bounded.

Recommended constraints:

- allowlisted ecosystems only
- top-N intake only
- low-frequency polling
- source budget
- candidate budget

This preserves serendipity without turning the platform into a full-time crawler.

### 8.3 Autonomous Scout Behavior

The main brain should be able to autonomously decide:

- whether it is worth scouting now
- which discovery mode to use
- which source chain to activate
- which radar surfaces to inspect
- which candidate set should enter evaluation

But this autonomy must still obey:

- budget
- allowlists/watchlists
- deduplication
- trial discipline
- promotion governance

In short:

- CoPaw should scout like a human engineer
- but not roam like an unbounded internet crawler

---

## 9. Multi-Source Deduplication And Donor Normalization

Multiple sources improve resilience, but they also create duplication noise.

Without formal deduplication, the same donor would appear as many fake choices, which would:

- inflate candidate count
- split evidence
- split trust memory
- confuse portfolio decisions
- make the system noisier instead of smarter

So multi-source discovery must normalize before candidate expansion.

### 9.1 Dedup Layers

Recommended dedup layers:

1. `source-level dedup`
   - remove duplicates inside the active source result set
2. `package identity dedup`
   - merge artifacts with the same canonical package identity
3. `donor lineage dedup`
   - merge different source aliases pointing at the same donor family
4. `candidate overlap detection`
   - detect functionally overlapping donors even when package identity differs
5. `portfolio compaction`
   - keep the best compact active combination instead of retaining all discovered equivalents

### 9.2 Recommended Normalization Fields

Recommended fields include:

- `canonical_package_id`
- `source_aliases`
- `candidate_source_lineage`
- `equivalence_class`
- `capability_overlap_score`
- `replacement_relation`

### 9.3 Hard Rules

Three rules should remain explicit:

- `multi-source discovery must merge before candidate expansion`
- `same donor from multiple sources should strengthen confidence, not multiply candidates`
- `portfolio count is based on normalized donors, not raw source hits`

---

## 10. Donor Admission Policy

Discovery does not equal admission.

Admission does not equal trial.

Trial does not equal promotion.

Recommended donor admission classes:

### 10.1 `allowlisted`

Properties:

- trusted source
- known structure
- acceptable license and provenance
- already compatible with existing runtime patterns

Allowed behavior:

- automatic discovery
- automatic candidate creation
- automatic scoped trial

### 10.2 `review-required`

Properties:

- source is plausible
- impact radius is larger
- structure or compatibility is less stable

Allowed behavior:

- automatic discovery
- automatic candidate creation
- trial allowed only after stronger system governance or explicit boundary confirmation

### 10.3 `manual-intake-only`

Properties:

- touches core runtime layers
- licensing or boundary concerns are non-trivial
- too powerful for routine automatic intake

Allowed behavior:

- no autonomous admission
- human-initiated intake only

### 10.4 `forbidden`

Properties:

- bypasses evidence or governance
- mutates formal truth without explicit contracts
- provenance/integrity cannot be trusted

Allowed behavior:

- never enters formal candidate flow

---

## 11. Donor-First Growth Priority

CoPaw should not treat self-authored skills or self-authored capabilities as the default way to grow.

The default growth rule should be:

1. reuse an existing donor
2. compose existing donors
3. compare multiple donors
4. adopt the best-performing donor
5. only then allow local fallback authoring

This is the platform-first interpretation of long-term evolution.

The system grows primarily by improving its governed capability portfolio, not by rewriting every missing component itself.

---

## 12. Governance Tiers

The correct governance model is not "strict everywhere."

The correct model is:

- `candidate default-open`
- `trial default-fast`
- `promotion strictly governed`
- `core mutation most strict`

### 12.1 Tier A: Fast Trial

Typical donors:

- most skills
- small low-risk read-mostly MCP servers
- narrow-scope adapters

Behavior:

- autonomous candidate creation
- autonomous scoped trial
- automatic rollback on poor evidence

### 12.2 Tier B: Scoped Guarded Trial

Typical donors:

- writer MCPs
- browser/desktop/document adapters
- higher-friction execution helpers

Behavior:

- autonomous candidate creation
- autonomous trial allowed, but only within explicit scope and environment contracts
- promotion requires stronger evidence

### 12.3 Tier C: Governed Promotion

Typical actions:

- role baseline promotion
- replacing existing formal capability packages
- multi-seat expansion

Behavior:

- candidate and trial may remain autonomous
- promotion/replacement must pass formal lifecycle governance

### 12.4 Tier D: Core Mutation

Typical donors:

- provider helpers close to runtime routing
- runtime components close to kernel/governance/persistence contracts
- anything that can distort formal truth, lifecycle, or evidence

Behavior:

- strongest governance
- no "fast adoption" path

---

## 13. Human Participation Policy

Default policy must be:

- `human-out-of-the-loop by default`
- `human-at-the-boundary only`

Most users do not understand skill ecosystems, MCP internals, provider contracts, or donor quality signals.

Therefore routine trial-and-error should be handled by the system itself.

### 13.1 What Should Be Autonomous

By default the system should autonomously handle:

- donor discovery
- donor evaluation
- candidate creation
- scoped trial
- trial evidence collection
- donor comparison
- automatic rollback
- portfolio refresh

### 13.2 What Should Still Reach Human Boundary

Human involvement should be reserved for:

- irreversible external actions
- money/account/legal/privacy high-risk boundaries
- mutations near kernel/truth/governance core
- cases where multiple high-impact donor choices remain unresolved with insufficient evidence

The platform should not routinely require the human to choose technical building blocks.

---

## 14. Local Authoring Downgrade

`local_authored` must remain possible, but must no longer be treated as the default growth route.

The old intuition of "system discovers gap -> main brain writes new skill" should be downgraded.

Recommended priority order:

1. reuse an existing donor
2. compose existing donors
3. compare multiple donors through scoped trial
4. adopt the best-performing donor
5. only if the ecosystem cannot cover the gap, allow `local_authored`

So `local_authored` should become:

- `fallback-only`
- `gap-closure-only`
- `private-constraint-only`
- `temporary-bridge-only`

It must also obey the same lifecycle rules:

- local file write does not imply formal adoption
- local authored artifacts must still become candidates
- local authored artifacts must still pass trial/evidence/lifecycle governance

This keeps self-authoring as a recovery tool, not as the platform's default way of growing.

---

## 15. Donor Portfolio Discipline

Long-term autonomy is not only about adding donors.

It is also about:

- portfolio shape
- donor replacement
- donor forgetting
- donor retirement

### 15.1 Portfolio Limits

Every role, seat, and environment should have bounded donor density.

Too many active donors produce:

- cognitive entropy
- routing ambiguity
- lower trial quality
- worse execution predictability

So the platform should maintain bounded active donor counts per:

- role baseline
- seat runtime
- environment/session scope
- donor category

### 15.2 Trust Memory

CoPaw should accumulate donor trust memory over time:

- reliable sources
- unstable sources
- high-value authors/orgs
- donors with frequent rollback history
- donors with repeated mismatch by role or environment

This is not a separate truth system. It is governance memory that improves future donor selection.

### 15.3 Retirement And Forgetting

CoPaw must know how to remove donors, not only add them.

Retirement signals include:

- better replacement exists
- donor quality degrades
- maintenance stops
- compatibility cost grows
- no longer matches current strategic portfolio

This is required for sustained autonomy. Otherwise the system only accumulates baggage.

---

## 16. Donor Combination As A Managed Asset

The platform should not optimize only single donors.

It should optimize donor combinations:

- best role capability mix
- best environment capability mix
- best task-family execution stack
- best fallback chain per execution surface

This means the target is not:

- "find the best skill"

The target is:

- "maintain the best governed capability portfolio for each scope"

That portfolio must stay subordinate to formal runtime truth, not the other way around.

---

## 17. Anti-Capture Rules

No donor, no matter how good, may capture the platform.

Three anti-capture rules should remain explicit:

1. a donor may be integrated into CoPaw
2. CoPaw must not be redefined around a donor's native internal model
3. if a donor conflicts with CoPaw's formal truth/lifecycle/evidence chain, the donor must adapt or remain external

This rule protects the carrier from turning into a pile of loosely glued third-party subsystems.

---

## 18. Formal Runtime Contract

This architecture should land as a formal CoPaw contract, not as loose operator guidance.

Minimum formal runtime expectations:

### 18.1 State Truth

State should be able to represent:

- donor provenance
- package provenance
- candidate state
- scoped trial state
- lifecycle decisions
- replacement relationships
- trust/reputation memory
- retirement status

### 18.2 Query / Read Surfaces

Runtime Center and governance read surfaces should be able to show:

- active donors by scope
- candidate donors
- trial outcomes
- adoption and rollback history
- degraded donor components
- donor portfolio deltas
- source provenance and current trust posture

### 18.3 Execution Attribution

Runtime/evidence should be able to attribute execution to:

- donor id
- package id
- candidate id
- trial id
- lifecycle stage
- selected scope

### 18.4 Write Chain

Formal write surfaces should remain explicit:

- discover candidate
- start scoped trial
- apply lifecycle decision
- retire donor
- rebuild capability portfolio

No hidden adoption path should exist outside that chain.

---

## 19. Implementation Direction

The next implementation direction should be:

1. keep the current governed capability lifecycle chain as the formal base
2. extend it from remote-skill emphasis to full donor assimilation
3. add donor/source/package truth
4. add discovery budgeting and watchlist policy
5. add portfolio limits and trust/retirement rules
6. keep local authoring only as exception path

This avoids building a second capability manager while still enabling long-term donor-driven evolution.

---

## 20. Final Standard

CoPaw should be judged successful here only if:

- it can continuously improve by adopting better external capabilities
- it does so without surrendering truth, lifecycle, or replacement power
- most trial-and-error happens autonomously
- human involvement stays at real boundary cases
- the active donor portfolio stays compact, auditable, and strategically aligned

That is the standard for long-term autonomy under a platform-first architecture.
