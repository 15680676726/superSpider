# Main-Brain Governed Optimization Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current review/prediction/candidate/trial/lifecycle pieces into one complete second-tier optimization loop without creating a parallel truth source or apply path.

**Architecture:** Reuse the existing main-brain cadence, prediction discovery, donor/package/candidate truth, skill trial/lifecycle truth, MCP runtime contract, and Runtime Center governance surfaces. The work is to unify semantics and contracts so they behave like one loop instead of several adjacent subsystems.

**Tech Stack:** Python, Pydantic, existing CoPaw `predictions / capabilities / app.mcp / state / industry / runtime_center`, pytest.

---

## Scope Guardrail

This plan follows the three-batch delivery boundary from the design.

### Batch 1: Required In This Loop

This implementation plan is primarily for:

- main-brain review cadence
- prediction discovery intake
- reporting/performance metrics
- skill / donor / candidate / trial / lifecycle truth
- MCP runtime as trialable governed capability supply
- Runtime Center optimization read-model

### Batch 2: Pull In Immediately After Batch 1 Closure

These should be connected next once the Batch 1 loop is stable:

- workflow preview / assignment-gap pressure
- donor trust / capability portfolio pressure
- knowledge-graph activation context
- strategy / planning constraints

### Batch 3: Explicitly Out Of Scope

Do not expand this plan into:

- generic chat-history optimization
- loose human-preference tuning
- pure frontend settings optimization
- autonomous mainline source-code mutation

If a task starts drifting into Batch 3, it is out of scope for this implementation plan.

---

### Task 1: Reframe Prediction Into Discovery Intake

**Files:**
- Modify: `src/copaw/predictions/service.py`
- Modify: `src/copaw/predictions/service_core.py`
- Modify: `src/copaw/predictions/service_refresh.py`
- Modify: `src/copaw/app/routers/predictions.py`
- Test: `tests/app/test_predictions_api.py`

- [ ] Add failing tests for "prediction" records carrying optimization/discovery semantics without creating a parallel object model.
- [ ] Verify the tests fail before changing implementation.
- [ ] Add explicit discovery/optimization metadata fields and projection helpers on the current prediction case/recommendation flow.
- [ ] Keep existing API compatibility where needed, but make the internal read-model clearly discovery-first.
- [ ] Ensure recommendation-to-main-brain handoff preserves optimization-case identity.
- [ ] Run focused prediction API tests.
- [ ] Commit only the files for this task.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/app/test_predictions_api.py -q
```

---

### Task 2: Add Unified Optimization Case Projection

**Files:**
- Add: `src/copaw/predictions/optimization_case_projection.py`
- Modify: `src/copaw/predictions/service_core.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`

- [ ] Add failing tests for a single optimization-case projection that includes issue, baseline, challenger, scope, evidence, and next decision.
- [ ] Verify the tests fail first.
- [ ] Build a projection helper over current case/recommendation/candidate/trial/lifecycle truth.
- [ ] Expose the projection through Runtime Center without inventing a new truth record.
- [ ] Ensure the projection works for both active and historical cases.
- [ ] Run focused Runtime Center governance tests.
- [ ] Commit only the files for this task.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q
```

---

### Task 3: Unify Trial Contract Across Skill And MCP

**Files:**
- Modify: `src/copaw/capabilities/skill_evolution_service.py`
- Modify: `src/copaw/app/mcp/runtime_contract.py`
- Modify: `src/copaw/industry/service_capability_governance.py`
- Modify: `src/copaw/predictions/service_recommendations.py`
- Test: `tests/predictions/test_skill_candidate_service.py`
- Test: `tests/app/test_mcp_runtime_contract.py`

- [ ] Add failing tests for MCP challengers entering the same trial vocabulary as skill challengers.
- [ ] Verify the tests fail first.
- [ ] Define shared trial metadata: baseline ref, challenger ref, scope, target capability family, rollback criteria.
- [ ] Lock the default apply scope to the acting unit:
  - main-brain local scope
  - professional-agent local scope
  - seat/session/agent-local runtime scope
  - no role-wide or system-wide replacement as the first move
- [ ] Extend recommendation/candidate materialization so MCP-backed challengers can attach to the same trial contract.
- [ ] Harden the missing-MCP path so real work can drive:
  - missing capability detection
  - candidate matching
  - governed enable/install
  - scoped trial
  - lifecycle decision handoff
- [ ] Encode the MCP governance boundary explicitly:
  - auto-enable only for already-known disabled local clients with narrow scope
  - guarded install/enable for install-template or builtin-runtime challengers with clear rollback
  - stronger governed approval for brand-new external installs, destructive replacement, or role-wide rollout
- [ ] Preserve existing skill behavior while making MCP symmetric at the contract layer.
- [ ] Run focused skill-candidate and MCP runtime tests.
- [ ] Commit only the files for this task.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/predictions/test_skill_candidate_service.py tests/app/test_mcp_runtime_contract.py -q
```

---

### Task 4: Add Explicit Evaluator Verdict Layer

**Files:**
- Add: `src/copaw/predictions/optimization_evaluator.py`
- Modify: `src/copaw/predictions/service_refresh.py`
- Modify: `src/copaw/state/skill_lifecycle_decision_service.py`
- Test: `tests/predictions/test_skill_trial_service.py`

- [ ] Add failing tests for baseline-vs-challenger verdict generation from trial evidence.
- [ ] Verify the tests fail first.
- [ ] Implement a small evaluator that scores trial evidence into stable verdicts.
- [ ] Map verdicts onto existing lifecycle decisions instead of creating a new apply path.
- [ ] Ensure evaluator output is evidence-backed and deterministic.
- [ ] Run focused trial/lifecycle tests.
- [ ] Commit only the files for this task.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/predictions/test_skill_trial_service.py -q
```

---

### Task 5: Build Full Runtime Center Optimization Surface

**Files:**
- Modify: `src/copaw/app/runtime_center/overview_capability_governance.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`

- [ ] Add failing tests for a unified Runtime Center optimization surface.
- [ ] Verify the tests fail first.
- [ ] Show discovery queue, active cases, running trials, promotion/rollback/retirement pressure, donor provenance, and MCP health in one read-model.
- [ ] Expose the minimum operator-visible fields per optimization case:
  - issue source
  - discovery case id
  - baseline
  - challenger
  - trial scope
  - owner
  - evaluator verdict
  - lifecycle decision
  - donor trust impact
  - planning impact
  - rollback/recovery route
- [ ] Remove duplicate or misleading labels that imply separate prediction/optimization systems.
- [ ] Run focused Runtime Center tests.
- [ ] Commit only the files for this task.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/app/runtime_center_api_parts/overview_governance.py -q
```

---

### Task 6: End-to-End Review-To-Lifecycle Closure

**Files:**
- Modify: `tests/app/test_predictions_api.py`
- Add: `tests/app/test_main_brain_optimization_loop_e2e.py`

- [ ] Add a failing end-to-end test covering: review cadence -> discovery case -> main-brain handoff -> challenger trial -> evaluator verdict -> lifecycle decision -> Runtime Center readback.
- [ ] Verify the new e2e test fails first.
- [ ] Fill any missing glue in the existing chain until the loop passes end to end.
- [ ] Ensure review results also write back into the next main-brain planning turn through donor trust / portfolio pressure / future discovery pressure.
- [ ] Ensure the e2e path proves the intended boundary:
  - apply locally first
  - write truth back globally
  - only broaden rollout through explicit lifecycle decision
- [ ] Make the writeback targets explicit and testable:
  - main-brain planning constraints
  - donor trust truth
  - capability portfolio pressure
  - future discovery/review pressure
  - strategy or operating-lane reopen signals
- [ ] Re-run focused loop tests plus the new e2e test.
- [ ] Commit only the files for this task.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/app/test_predictions_api.py tests/app/test_main_brain_optimization_loop_e2e.py -q
```

---

### Task 7: Document Real Completion Boundary

**Files:**
- Modify: `docs/superpowers/specs/2026-04-03-autonomous-capability-evolution-loop-design.md`
- Modify: `docs/superpowers/specs/2026-04-07-main-brain-governed-optimization-loop-design.md`
- Modify: `docs/superpowers/plans/2026-04-07-main-brain-governed-optimization-loop-implementation-plan.md`

- [ ] After implementation, update the docs with the honest landed boundary.
- [ ] List what is complete, what is intentionally deferred, and what old wording is now superseded.
- [ ] Commit the documentation closure.

---

## Completion Note (`2026-04-07`)

This plan is now implemented for the intended Batch 1 loop boundary.

Landed in code:

- discovery-first prediction intake
- unified optimization case projection
- shared MCP / skill trial contract vocabulary
- evaluator verdict -> lifecycle decision writeback
- Runtime Center optimization actionable/history surface
- end-to-end loop verification from discovery to Runtime Center readback
- real `desktop-windows` MCP template acceptance through manager connect + safe tool call
- optimization review results written back into the next formal planning turn through planning constraints / donor trust / portfolio pressure / future discovery pressure

Focused verification used for closure:

```powershell
python -m pytest tests/predictions/test_skill_candidate_service.py tests/predictions/test_skill_trial_service.py tests/app/test_mcp_runtime_contract.py tests/app/test_skill_runtime_smoke.py tests/app/test_predictions_api.py tests/app/test_main_brain_optimization_loop_e2e.py tests/app/runtime_center_api_parts/overview_governance.py -q
```

Result:

- `147 passed`

Additional closure verification:

```powershell
python -m pytest tests/app/test_mcp_runtime_contract.py tests/app/test_predictions_api.py tests/app/test_main_brain_optimization_loop_e2e.py tests/app/test_main_brain_optimization_planning_writeback.py tests/app/runtime_center_api_parts/overview_governance.py -q
```

Result:

- `122 passed`

Live external acceptance added after closure:

```powershell
$env:PYTHONPATH='src'
$env:COPAW_RUN_LIVE_OPTIMIZATION_SMOKE='1'
python -m pytest tests/app/test_mcp_runtime_contract.py tests/app/test_predictions_api.py tests/app/test_skill_runtime_smoke.py tests/app/test_main_brain_optimization_loop_e2e.py tests/app/test_main_brain_optimization_planning_writeback.py tests/app/test_live_optimization_smoke.py tests/app/runtime_center_api_parts/overview_governance.py -q
```

Result:

- `125 passed`
- includes real `desktop-windows` MCP acceptance
- includes real remote SkillHub search/install/trial -> review -> retirement -> next planning writeback

Deferred on purpose:

- Batch 2 quality enhancers
- Batch 3 excluded surfaces
