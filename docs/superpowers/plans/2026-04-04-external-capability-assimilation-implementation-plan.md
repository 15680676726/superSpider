# External Capability Assimilation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend CoPaw's existing governed capability lifecycle into a donor-first external capability assimilation system that can discover, normalize, trial, compare, adopt, replace, and retire external capability sources without creating a second truth chain.

**Architecture:** Reuse the current `CapabilityCandidate / SkillTrial / CapabilityLifecycleDecision / Runtime Center / evidence` base as the formal lifecycle spine. Add source-chain discovery, donor/package truth, deduplication, autonomous scout policy, and portfolio governance around that spine instead of building a parallel capability manager.

**Tech Stack:** Python, FastAPI, SQLite state store, existing `src/copaw/state`, `src/copaw/predictions`, `src/copaw/capabilities`, `src/copaw/app/runtime_center`, pytest

## Reality Correction (`2026-04-05`)

This plan's code-structure wave has landed, and the previously listed live external donor gaps have now been closed with real discovery/install/use verification.

Current verified runtime reality:

- donor/package/source/trial/lifecycle truth is in the mainline codebase
- Runtime Center donor/package/trust/scout read surfaces exist
- runtime bootstrap discovery executor is wired to real external providers instead of an empty placeholder
- opportunity radar now carries bounded default feeds instead of `feeds={}`
- generic open-source / GitHub donor search is on the runtime discovery path
- SkillHub / curated results suppress dead bundles before default search results are returned
- source-chain now records `empty` distinctly, advances to the next source, and only records last-known-good snapshot success when a source actually yields results

Fresh live-verified surfaces now include:

- SkillHub search -> install
- curated catalog search -> install with suppressed dead-bundle warnings
- official MCP registry search -> detail -> install -> live connection
- browser-local template install -> start -> attach -> stop
- desktop-windows template install -> live connection
- GitHub donor discovery through the runtime discovery executor
- scout gap/opportunity runs importing real donor candidates
- snapshot fallback after forced primary-source failure
- offline-private cache-backed discovery path

Therefore this plan must be read as:

- the formal donor-first spine exists
- the live discovery/installability gaps previously listed here have been closed
- completion claims for this plan are now backed by real discovery/install/use evidence, not only code/read-model/tests

## Execution Coupling Rule

This plan must not be implemented as:

- "finish all discipline work first, then build donor expansion"
- or "ship donor expansion first, then clean it up later"

The correct rule is:

- donor-first external expansion and the blocking `P0` discipline cuts move together

Concretely, the following are coupled and should be treated as one implementation wave:

- donor/package/source truth
- discovery source chain
- multi-source deduplication and donor normalization
- query runtime entropy contract for donor/trial-heavy turns

Reason:

- without the external spine, the platform does not actually grow
- without the `P0` discipline cuts, growth immediately creates duplicate candidates, provenance drift, and long-turn entropy

Therefore:

- `Package A` from `2026-04-04-next-round-discipline-closure-spec.md` is a hard companion to the first donor expansion wave
- `Package B` and `Package C` are not optional "later hardening"; they are part of the minimal safe donor-first spine
- later packages such as shared writer contract, child-run shell, MCP lifecycle hardening, and hotspot cooling may continue as follow-up waves, but the first donor expansion wave must already include `A + B + C`

---

## File Map

### Existing files to extend

- `src/copaw/state/models_capability_evolution.py`
  - Extend candidate/trial/lifecycle truth with donor/package/source-chain normalization fields.
- `src/copaw/state/store.py`
  - Add formal donor/package/source-profile/watchlist/trust-memory tables.
- `src/copaw/state/skill_candidate_service.py`
  - Evolve into normalized candidate service rather than only remote-skill oriented candidate intake.
- `src/copaw/state/skill_trial_service.py`
  - Extend scoped trial truth to keep donor/package attribution.
- `src/copaw/state/skill_lifecycle_decision_service.py`
  - Extend lifecycle truth with donor replacement and retirement metadata.
- `src/copaw/app/runtime_service_graph.py`
  - Wire new donor/source/discovery services into app bootstrap.
- `src/copaw/app/runtime_center/state_query.py`
  - Add donor/source/discovery/portfolio read surfaces.
- `src/copaw/app/routers/runtime_center_routes_core.py`
  - Add runtime-center routes for donor candidates, discovery state, source-chain state, and portfolio views.
- `src/copaw/predictions/service_recommendations.py`
  - Allow recommendations to target donor assimilation actions, not only current remote skill recommendations.
- `src/copaw/predictions/service_context.py`
  - Feed donor-performance and repeated-gap signals into discovery inputs.
- `src/copaw/kernel/query_execution_runtime.py`
  - Preserve donor/package/candidate/trial attribution in runtime evidence.

### New files to create

- `src/copaw/state/donor_source_service.py`
  - Own source profiles, active source-chain resolution, health state, and last-known-good snapshots.
- `src/copaw/state/donor_package_service.py`
  - Own normalized donor/package truth.
- `src/copaw/state/donor_trust_service.py`
  - Own trust/reputation memory and retirement/underperformance counters.
- `src/copaw/discovery/source_chain.py`
  - Resolve `primary -> mirror -> fallback` execution for one discovery action.
- `src/copaw/discovery/opportunity_radar.py`
  - Define bounded trending/weekly/release radar inputs.
- `src/copaw/discovery/deduplication.py`
  - Implement source-level, package-level, lineage-level, overlap-level normalization.
- `src/copaw/discovery/scout_service.py`
  - Main autonomous scout entrypoint for gap/performance/periodic/opportunity discovery.
- `src/copaw/discovery/models.py`
  - Typed models for discovery request, source profile, scout budget, normalized donor hit, overlap cluster.
- `src/copaw/governance/capability_portfolio_service.py`
  - Enforce role/seat/environment donor portfolio limits and compaction.

### Tests to create or extend

- `tests/state/test_donor_source_service.py`
- `tests/state/test_donor_package_service.py`
- `tests/state/test_donor_trust_service.py`
- `tests/discovery/test_source_chain.py`
- `tests/discovery/test_opportunity_radar.py`
- `tests/discovery/test_deduplication.py`
- `tests/discovery/test_scout_service.py`
- `tests/app/test_runtime_center_donor_api.py`
- `tests/predictions/test_donor_recommendations.py`
- `tests/kernel/test_query_execution_runtime.py`

---

### Task 1: Extend formal donor/package/source truth

**Files:**
- Modify: `src/copaw/state/models_capability_evolution.py`
- Modify: `src/copaw/state/store.py`
- Test: `tests/state/test_donor_package_service.py`

- [ ] **Step 1: Write the failing state-model tests**

Add tests for:
- donor/package/source profile records can be persisted and reloaded
- candidate truth can carry `canonical_package_id`, `candidate_source_lineage`, `equivalence_class`
- lifecycle records can carry replacement and retirement metadata

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/state/test_donor_package_service.py -q`
Expected: FAIL because donor/package/source truth does not exist yet.

- [ ] **Step 3: Add the minimal state models and schema**

Implement:
- donor source profile record
- donor package record
- donor trust/reputation record
- extra candidate normalization fields
- schema/table/index additions in `store.py`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/state/test_donor_package_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/state/models_capability_evolution.py src/copaw/state/store.py tests/state/test_donor_package_service.py
git commit -m "feat: add donor package and source truth"
```

### Task 2: Implement source-chain and regional profile resolution

**Files:**
- Create: `src/copaw/state/donor_source_service.py`
- Create: `src/copaw/discovery/source_chain.py`
- Test: `tests/state/test_donor_source_service.py`
- Test: `tests/discovery/test_source_chain.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- `global/china-mainland/hybrid/offline-private` source profiles
- one discovery action uses exactly one active source
- failure retries next source in chain
- source failure degrades discovery only
- last-known-good snapshot fallback

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/state/test_donor_source_service.py tests/discovery/test_source_chain.py -q`
Expected: FAIL because source-chain services do not exist yet.

- [ ] **Step 3: Implement minimal source-chain services**

Implement:
- source profile selection
- active-source resolution
- retry to mirror/fallback
- success provenance capture
- snapshot fallback API

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/state/test_donor_source_service.py tests/discovery/test_source_chain.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/state/donor_source_service.py src/copaw/discovery/source_chain.py tests/state/test_donor_source_service.py tests/discovery/test_source_chain.py
git commit -m "feat: add donor source-chain resolution"
```

### Task 3: Implement multi-source deduplication and donor normalization

**Files:**
- Create: `src/copaw/discovery/deduplication.py`
- Modify: `src/copaw/state/skill_candidate_service.py`
- Test: `tests/discovery/test_deduplication.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- same donor from different sources merges before candidate expansion
- duplicate package hits strengthen confidence instead of multiplying candidates
- overlap detection groups equivalent donors
- normalized portfolio counts use deduped donors rather than raw source hits

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/discovery/test_deduplication.py -q`
Expected: FAIL because deduplication logic is missing.

- [ ] **Step 3: Implement minimal normalization logic**

Implement:
- source-level dedup
- package identity merge
- donor lineage merge
- overlap scoring and equivalence clustering
- candidate import path updated to consume normalized hits

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/discovery/test_deduplication.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/discovery/deduplication.py src/copaw/state/skill_candidate_service.py tests/discovery/test_deduplication.py
git commit -m "feat: normalize donor discovery across sources"
```

### Task 4: Implement bounded opportunity radar and autonomous scout

**Files:**
- Create: `src/copaw/discovery/models.py`
- Create: `src/copaw/discovery/opportunity_radar.py`
- Create: `src/copaw/discovery/scout_service.py`
- Test: `tests/discovery/test_opportunity_radar.py`
- Test: `tests/discovery/test_scout_service.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- gap-driven discovery
- performance-driven discovery
- bounded periodic review
- opportunity radar with top-N/trusted-ecosystem discipline
- autonomous scout chooses one discovery mode and one active source chain per run
- scout budget prevents uncontrolled expansion

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/discovery/test_opportunity_radar.py tests/discovery/test_scout_service.py -q`
Expected: FAIL because scout/radar services do not exist yet.

- [ ] **Step 3: Implement minimal scout stack**

Implement:
- typed discovery request and budget models
- radar surface abstraction
- scout decision entrypoint
- gap/performance/periodic/opportunity mode routing
- top-N bounded candidate output

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/discovery/test_opportunity_radar.py tests/discovery/test_scout_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/discovery/models.py src/copaw/discovery/opportunity_radar.py src/copaw/discovery/scout_service.py tests/discovery/test_opportunity_radar.py tests/discovery/test_scout_service.py
git commit -m "feat: add bounded donor scout and radar"
```

### Task 5: Add donor trust memory and retirement signals

**Files:**
- Create: `src/copaw/state/donor_trust_service.py`
- Modify: `src/copaw/state/skill_lifecycle_decision_service.py`
- Test: `tests/state/test_donor_trust_service.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- trust memory accumulates successful and failed donor outcomes
- repeated rollback lowers trust posture
- stale/retired donors can be marked for replacement
- trust memory stays tied to donor truth rather than raw source hits

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/state/test_donor_trust_service.py -q`
Expected: FAIL because donor trust service does not exist yet.

- [ ] **Step 3: Implement minimal trust and retirement logic**

Implement:
- donor trust counters and posture summary
- underperforming/repeated rollback memory
- retirement flagging
- replacement candidate linkage

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/state/test_donor_trust_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/state/donor_trust_service.py src/copaw/state/skill_lifecycle_decision_service.py tests/state/test_donor_trust_service.py
git commit -m "feat: add donor trust and retirement memory"
```

### Task 6: Enforce donor portfolio limits and compaction

**Files:**
- Create: `src/copaw/governance/capability_portfolio_service.py`
- Modify: `src/copaw/predictions/service_recommendations.py`
- Test: `tests/predictions/test_donor_recommendations.py`

- [ ] **Step 1: Write the failing tests**

Cover:
- portfolio limit by role/seat/environment
- candidate recommendation prefers replacement/compaction over unbounded expansion
- portfolio count uses normalized donor identities
- donor-first priority chooses reuse/compose before local authoring

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/predictions/test_donor_recommendations.py -q`
Expected: FAIL because portfolio governance is missing.

- [ ] **Step 3: Implement minimal portfolio governance**

Implement:
- portfolio limit resolution
- donor compaction scoring
- replacement-first recommendation behavior
- local-authoring-as-last-resort recommendation rule

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/predictions/test_donor_recommendations.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/governance/capability_portfolio_service.py src/copaw/predictions/service_recommendations.py tests/predictions/test_donor_recommendations.py
git commit -m "feat: govern donor portfolios and compaction"
```

### Task 7: Wire donor assimilation into runtime bootstrap and read surfaces

**Files:**
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Test: `tests/app/test_runtime_center_donor_api.py`

- [ ] **Step 1: Write the failing API/query tests**

Cover:
- runtime-center donor candidate list
- source profile/active chain state
- portfolio state by scope
- degraded donor component visibility
- trust/retirement summary visibility

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/app/test_runtime_center_donor_api.py -q`
Expected: FAIL because routes/query methods do not exist yet.

- [ ] **Step 3: Implement minimal runtime-center read surfaces**

Implement:
- bootstrap wiring for donor source/package/trust/portfolio services
- state query methods
- runtime-center routes
- projection payloads for operators

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/app/test_runtime_center_donor_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/app/runtime_service_graph.py src/copaw/app/runtime_center/state_query.py src/copaw/app/routers/runtime_center_routes_core.py tests/app/test_runtime_center_donor_api.py
git commit -m "feat: expose donor assimilation runtime surfaces"
```

### Task 8: Preserve donor attribution in runtime and evidence

**Files:**
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Test: `tests/kernel/test_query_execution_runtime.py`

- [ ] **Step 1: Write the failing runtime attribution tests**

Cover:
- runtime evidence carries donor/package/candidate/trial attribution
- selected scope and lifecycle stage survive runtime execution
- same normalized donor lineage aggregates evidence consistently

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/kernel/test_query_execution_runtime.py -q -k \"donor or candidate or trial or attribution\"`
Expected: FAIL because attribution is incomplete.

- [ ] **Step 3: Implement minimal runtime attribution propagation**

Implement:
- donor/package/candidate/trial metadata propagation
- lineage/equivalence attribution fields
- runtime/evidence sink compatibility for donor truth

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/kernel/test_query_execution_runtime.py -q -k \"donor or candidate or trial or attribution\"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/kernel/query_execution_runtime.py tests/kernel/test_query_execution_runtime.py
git commit -m "feat: preserve donor attribution in runtime evidence"
```

### Task 9: Verify integrated donor-first chain

**Files:**
- Test: `tests/state/test_donor_source_service.py`
- Test: `tests/state/test_donor_package_service.py`
- Test: `tests/state/test_donor_trust_service.py`
- Test: `tests/discovery/test_source_chain.py`
- Test: `tests/discovery/test_opportunity_radar.py`
- Test: `tests/discovery/test_deduplication.py`
- Test: `tests/discovery/test_scout_service.py`
- Test: `tests/predictions/test_donor_recommendations.py`
- Test: `tests/app/test_runtime_center_donor_api.py`
- Test: `tests/kernel/test_query_execution_runtime.py`

- [ ] **Step 1: Run the focused integrated verification**

Run:

```bash
python -m pytest tests/state/test_donor_source_service.py tests/state/test_donor_package_service.py tests/state/test_donor_trust_service.py tests/discovery/test_source_chain.py tests/discovery/test_opportunity_radar.py tests/discovery/test_deduplication.py tests/discovery/test_scout_service.py tests/predictions/test_donor_recommendations.py tests/app/test_runtime_center_donor_api.py tests/kernel/test_query_execution_runtime.py -q
```

Expected: PASS

- [ ] **Step 2: Run adjacent capability-governance regression**

Run:

```bash
python -m pytest tests/predictions/test_skill_candidate_service.py tests/predictions/test_skill_trial_service.py tests/app/test_capability_market_api.py tests/app/test_predictions_api.py tests/app/test_capability_skill_service.py tests/app/test_runtime_center_events_api.py -q
```

Expected: PASS

- [ ] **Step 3: Commit final integration**

```bash
git add .
git commit -m "feat: add donor-first capability assimilation architecture"
```

---

## Notes For Execution

- Reuse the already-landed governed capability lifecycle chain; do not invent a parallel donor manager.
- Keep `local_authored` valid but explicitly last-resort in recommendations and lifecycle policy.
- Preserve the existing rule that source failure degrades discovery, not runtime.
- Treat "single active source" as a per-discovery-run rule, not a system-wide removal of source redundancy.
- Avoid overbuilding full internet crawling; the scout is bounded, allowlisted, and budgeted.
