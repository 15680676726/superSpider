# Donor-First Capability Evolution Priority Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the next capability-evolution wave in donor-first order so CoPaw grows by adopting, reusing, trialing, and governing external capability packages before falling back to local authored artifacts.

**Architecture:** Keep all work on the canonical `CapabilityCandidateRecord -> SkillTrialRecord -> SkillLifecycleDecisionRecord -> governed mutation -> Runtime Center` chain. Do not build a local-authoring-first side system. Mature external donors, MCP bundles, adapters, and already-healthy artifact versions are the primary supply; local authored artifacts are fallback-only and must still pass through the same lifecycle.

**Tech Stack:** Python, FastAPI, SQLite state store, existing CoPaw `state / discovery / capabilities / industry / predictions / kernel / runtime_center`, pytest.

## Reality Correction (`2026-04-05`)

This priority plan is still valid, but it must now be read with a stricter runtime boundary:

- Task 1-4 landing in code/read-model/tests does not by itself prove live donor-first closure
- donor-first evolution is only "closed" when external discovery, external installability, and downstream use are all live-verified

The live gaps that still block a truthful completion claim are:

- autonomous scout still lacks a real default discovery executor
- opportunity radar still lacks real default feeds
- generic GitHub/open-source donor search is not yet on the runtime path
- SkillHub/curated search still needs dead-bundle suppression before results can be trusted by default

So this plan should be executed as:

- keep the donor-first lifecycle/resolver/read-model work already landed
- finish the live external supply-chain gaps
- only then report full donor-first capability evolution closure

---

## Priority Rule

This plan supersedes any lingering reading of the `2026-04-03` capability-evolution docs that sounds like "write a new skill first."

The practical priority order is:

1. normalize and import donor-first candidates
2. prefer donor adoption and healthy-version reuse
3. support MCP-native and non-skill package forms on the same lifecycle
4. trial and govern the chosen package on the correct scope
5. only then synthesize a bounded local artifact if the gap still remains

---

## File Map

### Existing files to extend

- `src/copaw/state/models_capability_evolution.py`
  - Keep the top-level candidate/trial/lifecycle truth open for donor/MCP/runtime bundle forms instead of only skill-shaped assumptions.
- `src/copaw/state/skill_candidate_service.py`
  - Make donor-first candidate normalization and baseline import the default entry behavior.
- `src/copaw/state/skill_trial_service.py`
  - Aggregate verdict-ready trial truth across donor-first and fallback-local candidates.
- `src/copaw/state/skill_lifecycle_decision_service.py`
  - Keep protected replace / rollback / retire on the same governed lifecycle.
- `src/copaw/predictions/service_context.py`
  - Feed repeated failure, human takeover, overlay reuse, and active drift into candidate creation.
- `src/copaw/predictions/service_recommendations.py`
  - Emit donor-first proposals and reuse-first lifecycle actions instead of local-authoring-first proposals.
- `src/copaw/capabilities/skill_service.py`
  - Materialize fallback local artifacts safely and only after donor-first resolution says they are needed.
- `src/copaw/industry/service_activation.py`
  - Apply lifecycle decisions without donor shortcuts or local-authored shortcuts.
- `src/copaw/industry/service_team_runtime.py`
  - Preserve seat/session trial continuity and reuse healthy versions instead of reinstalling.
- `src/copaw/kernel/query_execution_runtime.py`
  - Keep runtime attribution on candidate/trial/scope truth.
- `src/copaw/app/routers/capability_market.py`
  - Surface donor-first package decisions and baseline-import state.
- `src/copaw/app/runtime_center/state_query.py`
  - Expose candidate source, baseline import state, trial status, and lifecycle history.
- `src/copaw/app/runtime_center/overview_cards.py`
  - Show donor-first governance/read-model summaries without implying that local authored is the primary path.

### New files to create

- `src/copaw/capabilities/skill_evolution_service.py`
  - Resolve `adopt existing donor / reuse healthy version / revise existing artifact / author fallback local artifact`.
- `src/copaw/learning/skill_gap_detector.py`
  - Turn active drift and repeated execution pressure into formal candidate pressure instead of ad-hoc local fixes.

### Tests to extend

- `tests/predictions/test_skill_candidate_service.py`
- `tests/predictions/test_skill_trial_service.py`
- `tests/app/test_capability_market_api.py`
- `tests/app/test_capability_skill_service.py`
- `tests/test_skill_service.py`
- `tests/app/test_industry_api.py`
- `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- `tests/app/test_mcp_runtime_contract.py`
- `tests/test_mcp_resilience.py`
- `tests/kernel/test_query_execution_runtime.py`
- `tests/industry/test_runtime_views_split.py`

---

### Task 1: Baseline Import And Donor-First Candidate Truth

**Files:**
- Modify: `src/copaw/state/models_capability_evolution.py`
- Modify: `src/copaw/state/skill_candidate_service.py`
- Modify: `src/copaw/predictions/service_context.py`
- Modify: `src/copaw/predictions/service_recommendations.py`
- Modify: `src/copaw/app/routers/capability_market.py`
- Test: `tests/predictions/test_skill_candidate_service.py`
- Test: `tests/app/test_capability_market_api.py`

- [ ] **Step 1: Write or extend failing tests**

Cover:
- active installed/enabled donor artifacts import into lifecycle truth as baseline instead of pretending they are brand new installs
- repeated failure / human takeover / overlay reuse creates a formal candidate
- donor-first selection ranks `external donor -> healthy reuse -> local fallback`
- candidate creation does not mutate role capability state directly

- [ ] **Step 2: Run tests to verify the gap**

Run:
`PYTHONPATH=src python -m pytest tests/predictions/test_skill_candidate_service.py tests/app/test_capability_market_api.py -q`

Expected:
- FAIL on baseline import and donor-first preference assertions

- [ ] **Step 3: Implement minimal donor-first candidate truth**

Implement:
- candidate-source normalization for donor, MCP, adapter, runtime-helper, and local-fallback paths
- baseline-import path for already-active artifacts
- donor-first candidate ranking metadata
- no-direct-activation guard at candidate creation

- [ ] **Step 4: Run tests to verify they pass**

Run:
`PYTHONPATH=src python -m pytest tests/predictions/test_skill_candidate_service.py tests/app/test_capability_market_api.py -q`

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/state/models_capability_evolution.py src/copaw/state/skill_candidate_service.py src/copaw/predictions/service_context.py src/copaw/predictions/service_recommendations.py src/copaw/app/routers/capability_market.py tests/predictions/test_skill_candidate_service.py tests/app/test_capability_market_api.py
git commit -m "feat: make capability candidates donor first"
```

### Task 2: MCP-Native Candidate Forms And Reuse-First Resolver

**Files:**
- Add: `src/copaw/capabilities/skill_evolution_service.py`
- Modify: `src/copaw/capabilities/skill_service.py`
- Modify: `src/copaw/state/donor_package_service.py`
- Modify: `src/copaw/industry/service_team_runtime.py`
- Test: `tests/app/test_capability_skill_service.py`
- Test: `tests/test_skill_service.py`
- Test: `tests/app/test_mcp_runtime_contract.py`
- Test: `tests/test_mcp_resilience.py`

- [ ] **Step 1: Write or extend failing tests**

Cover:
- MCP/runtime bundle candidates do not get forced through skill-only assumptions
- healthy artifact versions are reused when scope and environment contract still match
- donor adoption/reuse is attempted before local fallback authoring
- missing local artifact targets fail safely without corrupting lifecycle truth

- [ ] **Step 2: Run tests to verify the gap**

Run:
`PYTHONPATH=src python -m pytest tests/app/test_capability_skill_service.py tests/test_skill_service.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py -q`

Expected:
- FAIL on MCP-native and reuse-first assertions

- [ ] **Step 3: Implement the resolver and fallback materialization path**

Implement:
- `skill_evolution_service` as the single resolver for `adopt / reuse / revise / author fallback`
- explicit MCP-native package branch
- healthy-version reuse check before reinstall
- bounded fallback local artifact materialization only after donor-first resolution

- [ ] **Step 4: Run tests to verify they pass**

Run:
`PYTHONPATH=src python -m pytest tests/app/test_capability_skill_service.py tests/test_skill_service.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py -q`

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/capabilities/skill_evolution_service.py src/copaw/capabilities/skill_service.py src/copaw/state/donor_package_service.py src/copaw/industry/service_team_runtime.py tests/app/test_capability_skill_service.py tests/test_skill_service.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py
git commit -m "feat: resolve donor reuse before local fallback artifacts"
```

### Task 3: Trial Verdict Truth And Protected Lifecycle Apply

**Files:**
- Modify: `src/copaw/state/skill_trial_service.py`
- Modify: `src/copaw/state/skill_lifecycle_decision_service.py`
- Modify: `src/copaw/industry/service_activation.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Test: `tests/predictions/test_skill_trial_service.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/kernel/test_query_execution_runtime.py`

- [ ] **Step 1: Write or extend failing tests**

Cover:
- donor-first and local-fallback candidates both feed the same trial verdict model
- multi-seat trial evidence aggregates to candidate verdicts without collapsing seat-local evidence
- protected artifacts can receive replacement proposals but cannot be silently auto-replaced
- runtime attribution remains attached to candidate/trial/scope truth through trial and follow-up lifecycle decisions

- [ ] **Step 2: Run tests to verify the gap**

Run:
`PYTHONPATH=src python -m pytest tests/predictions/test_skill_trial_service.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/kernel/test_query_execution_runtime.py -q`

Expected:
- FAIL on verdict aggregation or protected replace assertions

- [ ] **Step 3: Implement minimal governed trial/lifecycle hardening**

Implement:
- verdict-ready trial aggregation
- protected replace / rollback / retire handling
- donor-first lifecycle decisions with no direct install shortcut
- preserved runtime attribution metadata on evidence sinks

- [ ] **Step 4: Run tests to verify they pass**

Run:
`PYTHONPATH=src python -m pytest tests/predictions/test_skill_trial_service.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/kernel/test_query_execution_runtime.py -q`

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/state/skill_trial_service.py src/copaw/state/skill_lifecycle_decision_service.py src/copaw/industry/service_activation.py src/copaw/kernel/query_execution_runtime.py tests/predictions/test_skill_trial_service.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/kernel/test_query_execution_runtime.py
git commit -m "feat: govern donor first trial verdicts and lifecycle apply"
```

### Task 4: Runtime Center Visibility And Drift Re-Entry

**Files:**
- Add: `src/copaw/learning/skill_gap_detector.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `src/copaw/predictions/service_context.py`
- Test: `tests/industry/test_runtime_views_split.py`
- Test: `tests/app/test_industry_api.py`
- Test: `tests/app/test_capability_market_api.py`

- [ ] **Step 1: Write or extend failing tests**

Cover:
- Runtime Center shows whether a candidate came from donor ingest, baseline import, reuse, or fallback local authoring
- active artifact degradation re-enters the loop as a formal candidate/replacement/retirement pressure
- read models show lifecycle history, replacement lineage, and active composition without inventing a second truth source

- [ ] **Step 2: Run tests to verify the gap**

Run:
`PYTHONPATH=src python -m pytest tests/industry/test_runtime_views_split.py tests/app/test_industry_api.py tests/app/test_capability_market_api.py -q`

Expected:
- FAIL on missing drift/read-model assertions

- [ ] **Step 3: Implement minimal drift/read-model closure**

Implement:
- `skill_gap_detector` for active drift and replacement pressure
- Runtime Center projections for source provenance, baseline import, trial status, lifecycle history, and replacement lineage
- no-local-authoring-first language or behavior in operator-visible summaries

- [ ] **Step 4: Run tests to verify they pass**

Run:
`PYTHONPATH=src python -m pytest tests/industry/test_runtime_views_split.py tests/app/test_industry_api.py tests/app/test_capability_market_api.py -q`

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add src/copaw/learning/skill_gap_detector.py src/copaw/app/runtime_center/state_query.py src/copaw/app/runtime_center/overview_cards.py src/copaw/industry/service_runtime_views.py src/copaw/predictions/service_context.py tests/industry/test_runtime_views_split.py tests/app/test_industry_api.py tests/app/test_capability_market_api.py
git commit -m "feat: expose donor first capability evolution and drift"
```

---

## Global Acceptance Criteria

- [ ] Mature external donor adoption is always evaluated before local fallback authoring.
- [ ] Healthy artifact/version reuse is preferred before reinstall or rewrite.
- [ ] MCP-native candidates and skill candidates share the same top-level lifecycle truth.
- [ ] Already-active artifacts can be baseline-imported into the lifecycle ledger.
- [ ] New artifacts default to session/seat trial, not direct role promotion.
- [ ] Trial verdicts aggregate multi-seat evidence without erasing seat/session attribution.
- [ ] Protected artifacts cannot be silently auto-replaced.
- [ ] Runtime/evidence attribution stays attached to candidate/trial/scope truth.
- [ ] Runtime Center can show provenance, baseline import state, trial status, lifecycle history, replacement lineage, and active composition.
- [ ] Active degradation can re-enter the governed loop as revision / replacement / retirement pressure.

---

## Final Verification

Run at the end:

```powershell
PYTHONPATH=src python -m pytest tests/predictions/test_skill_candidate_service.py tests/predictions/test_skill_trial_service.py tests/app/test_capability_market_api.py tests/app/test_capability_skill_service.py tests/test_skill_service.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_industry_api.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py tests/kernel/test_query_execution_runtime.py tests/industry/test_runtime_views_split.py -q
```

And adjacent regressions:

```powershell
PYTHONPATH=src python -m pytest tests/app/test_predictions_api.py tests/app/test_runtime_center_events_api.py tests/app/test_capabilities_execution.py tests/app/test_runtime_bootstrap_helpers.py -q
```
