# Autonomous Capability Evolution Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full governed capability-evolution loop for long-term autonomy so CoPaw can discover capability gaps, adopt mature external capability donors first, synthesize local fallback artifacts only when necessary, trial them on the correct scope, evaluate them with evidence, and promote / replace / rollback / retire them without introducing a second truth source.

**Architecture:** Reuse the canonical `CapabilityMount / role prototype / seat instance / cycle delta / session overlay / governed mutation / evidence` chain. Do not build a parallel skill lifecycle manager. CoPaw remains the governance/runtime base; mature external projects, MCPs, adapters, and helper runtimes are the default growth path, while local authored artifacts remain fallback-only.

**Tech Stack:** Python, Pydantic, existing CoPaw `state / capabilities / industry / kernel / predictions / runtime_center`, pytest.

---

## Phase 1: Candidate Truth And Discovery

**Outcome:** capability-evolution candidates become formal state, not transient recommendation text.

**Files:**
- Add: `src/copaw/state/skill_candidate_service.py`
- Modify: `src/copaw/predictions/service_context.py`
- Modify: `src/copaw/predictions/service_recommendations.py`
- Modify: `src/copaw/app/_app.py`
- Test: `tests/predictions/test_skill_candidate_service.py`
- Test: `tests/app/test_capability_market_api.py`

- [ ] Define top-level `CapabilityCandidateRecord` and repository/service contract.
- [ ] Keep `SkillCandidateRecord` as the skill-specific subtype instead of the only candidate truth.
- [ ] Leave room for `McpBundleCandidateRecord` so MCP-native candidates do not get forced into a skill-only schema.
- [ ] Add candidate-source normalization so both:
  - external donor / remote auto-install / MCP / adapter ingest
  - local self-authored / generated fallback artifacts
  enter the same `CapabilityCandidateRecord` truth before any activation work.
- [ ] Persist source provenance on every candidate:
  - `candidate_source_kind`
  - `candidate_source_ref`
  - `candidate_source_version`
  - `candidate_source_lineage`
  - `ingestion_mode`
- [ ] Add discovery rules for:
  - repeated failure clusters
  - repeated success patterns
  - repeated overlay reuse
  - repeated human takeover
- [ ] Ensure predictions can emit governed candidate proposals without directly installing anything.
- [ ] Add duplicate/overlap detection between external candidates and local candidates so equivalent artifacts do not create parallel trial tracks.
- [ ] Import already-active installed/enabled skill/MCP artifacts as baseline lifecycle records instead of re-installing them as if they were brand new candidates.
- [ ] Enforce donor-first selection discipline so candidate creation prefers:
  - existing mature donor
  - healthy artifact reuse
  - governed local revision
  - only then new local artifact authoring
- [ ] Project candidate truth into Runtime Center read models.
- [ ] Verify candidate creation never writes role capability state directly.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/predictions/test_skill_candidate_service.py tests/app/test_capability_market_api.py -q
```

---

## Phase 2: Donor Adoption, Reuse, And Fallback Artifact Materialization

**Outcome:** a candidate can first resolve to donor adoption or healthy-version reuse, and only then produce a governed fallback artifact package when donor-first paths still leave a real gap.

**Files:**
- Modify: `src/copaw/capabilities/skill_service.py`
- Add: `src/copaw/capabilities/skill_evolution_service.py`
- Modify: `src/copaw/capabilities/remote_skill_contract.py`
- Test: `tests/app/test_capability_skill_service.py`
- Test: `tests/test_skill_service.py`

- [ ] Define governed package materialization contract for:
  - external donor package/adapters
  - MCP/runtime bundle metadata
  - `SKILL.md`
  - optional `scripts/`
  - optional `references/`
  - lifecycle metadata
  - verification contract
- [ ] Ensure externally sourced artifacts and locally authored fallback artifacts both materialize behind the same draft/artifact contract instead of separate lifecycle codepaths.
- [ ] Keep subtype-specific materialization boundaries explicit:
  - skill candidates materialize skill artifacts
  - MCP candidates materialize MCP/runtime bundle metadata
- [ ] Require donor adoption or healthy-version reuse to be evaluated before new local artifact authoring starts.
- [ ] Persist `candidate_id`, lifecycle stage, and lineage metadata into the artifact path and capability projection.
- [ ] Keep artifact materialization separate from lifecycle promotion.
- [ ] Ensure missing local artifact targets fail safely and do not corrupt lifecycle truth.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/app/test_capability_skill_service.py tests/test_skill_service.py -q
```

---

## Phase 3: Scoped Trial Mount

**Outcome:** candidate artifacts can be trialed on `session` / `seat` scope without immediate role-wide promotion.

**Files:**
- Modify: `src/copaw/industry/models.py`
- Modify: `src/copaw/industry/service_team_runtime.py`
- Modify: `src/copaw/app/mcp/manager.py`
- Modify: `src/copaw/kernel/child_run_shell.py`
- Test: `tests/app/test_industry_service_wiring.py`
- Test: `tests/app/test_mcp_runtime_contract.py`
- Test: `tests/test_mcp_resilience.py`

- [ ] Extend scope attach semantics so candidate artifacts can mount to:
  - session overlay
  - seat instance pack
- [ ] Enforce the same scoped-trial rule for both external and local candidates; neither path may activate role-wide directly from install/materialization success.
- [ ] Add seat/session trial lease discipline so one seat's trial mutations cannot leak into another seat's runtime surface.
- [ ] Allow shared artifact/version reuse across seats only when the environment contract matches; keep trial truth and evidence attribution separate per seat/session.
- [ ] Ensure healthy matching artifacts are reused instead of reinstalled for every new task.
- [ ] Ensure the mount path respects existing capability layers and MCP overlay inheritance.
- [ ] Add explicit trial metadata to seat/session runtime truth.
- [ ] Enforce fail-closed behavior for malformed scope truth.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/app/test_industry_service_wiring.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py -q
```

---

## Phase 4: Runtime Trial Attribution

**Outcome:** runtime execution and evidence can be attributed back to candidate trial truth.

**Files:**
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/kernel/query_execution_prompt.py`
- Modify: `src/copaw/agents/react_agent.py`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `tests/agents/test_react_agent_tool_compat.py`

- [ ] Emit canonical runtime metadata:
  - `skill_candidate_id`
  - `skill_trial_id`
  - `skill_lifecycle_stage`
  - `selected_scope`
  - `replacement_target_ids`
- [ ] Ensure effective capability resolution still uses the canonical layered capability resolver.
- [ ] Preserve current fast-loop chat/runtime performance constraints.
- [ ] Verify evidence sinks keep correct attribution metadata.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/kernel/test_query_execution_runtime.py tests/agents/test_react_agent_tool_compat.py -q
```

---

## Phase 5: Trial Truth And Evaluation

**Outcome:** trials are formal objects with verdicts, not ad-hoc interpretation of logs.

**Files:**
- Add: `src/copaw/state/skill_trial_service.py`
- Modify: `src/copaw/predictions/service_context.py`
- Modify: `src/copaw/predictions/service_recommendations.py`
- Test: `tests/predictions/test_skill_trial_service.py`
- Test: `tests/capabilities/test_remote_skill_presentation.py`

- [ ] Define `SkillTrialRecord`.
- [ ] Aggregate multi-seat trials at the candidate level without collapsing seat-local evidence or handoff/failure attribution.
- [ ] Aggregate:
  - completion rate
  - failure rate
  - operator intervention rate
  - handoff rate
  - latency summary
- [ ] Feed verdict-ready trial summaries back into prediction / learning.
- [ ] Distinguish trial success from mere time-in-use.
- [ ] Verify donor adoption/reuse paths and local fallback artifacts feed the same trial verdict model.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/predictions/test_skill_trial_service.py tests/capabilities/test_remote_skill_presentation.py -q
```

---

## Phase 6: Lifecycle Decision And Governed Apply

**Outcome:** promote / replace / rollback / retire become formal governed actions.

**Files:**
- Add: `src/copaw/state/skill_lifecycle_decision_service.py`
- Modify: `src/copaw/kernel/governed_mutation_dispatch.py`
- Modify: `src/copaw/industry/service_activation.py`
- Modify: `src/copaw/capabilities/system_team_handlers.py`
- Test: `tests/app/test_governed_mutations.py`
- Test: `tests/app/industry_api_parts/bootstrap_lifecycle.py`
- Test: `tests/app/test_industry_api.py`

- [ ] Define `SkillLifecycleDecisionRecord`.
- [ ] Support decisions:
  - `continue_trial`
  - `promote_to_role`
  - `keep_seat_local`
  - `replace_existing`
  - `rollback`
  - `retire`
- [ ] Route all lifecycle applies through governed mutations.
- [ ] Explicitly block direct role activation from either:
  - external install success
  - local file authoring success
- [ ] Add protected-artifact handling:
  - `pinned_by_operator`
  - `required_by_role_blueprint`
  - `protected_from_auto_retire`
  - `protected_from_auto_replace`
- [ ] Support protected replacement flow where the system can propose `replace_requested`, but only explicit confirm/protection-lift can apply the final replace.
- [ ] Ensure replacement and rollback restore correct prior capability truth.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/app/test_governed_mutations.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_industry_api.py -q
```

---

## Phase 7: Capability Recomposition And Budget Governance

**Outcome:** role/seat packs stay coherent instead of accreting unbounded skills.

**Files:**
- Add: `src/copaw/industry/service_capability_governance.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `src/copaw/industry/service_team_runtime.py`
- Test: `tests/industry/test_runtime_views_split.py`
- Test: `tests/app/test_industry_service_wiring.py`

- [ ] Add budget enforcement for:
  - role skill budget
  - seat skill budget
  - MCP budget
  - overlap pressure
- [ ] Ensure budget/overlap evaluation runs on normalized candidates, not source-specific paths.
- [ ] Exclude baseline-imported protected artifacts from silent auto-retire/auto-replace unless protection state changes through the governed path.
- [ ] Add install/rebuild discipline so recomposition prefers reuse/mount before reinstall.
- [ ] Add replacement pressure evaluation.
- [ ] Recompute role/seat/cycle/session capability composition after lifecycle applies.
- [ ] Prefer reuse/mount/replace over fresh reinstall whenever a healthy governed package already exists.
- [ ] Ensure no layer becomes a hidden second truth source.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/industry/test_runtime_views_split.py tests/app/test_industry_service_wiring.py -q
```

---

## Phase 8: Runtime Center Visibility

**Outcome:** operators can see the loop end-to-end.

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Test: `tests/app/test_capability_market_api.py`
- Test: `tests/industry/test_runtime_views_split.py`

- [ ] Project candidate status into Runtime Center.
- [ ] Project candidate source provenance and source normalization result into Runtime Center so operators can see whether a candidate came from external donor ingest or local authoring without implying different governance.
- [ ] Project baseline-imported active artifacts and their protection state so operators can tell which active capabilities are inherited baseline versus newly trialed candidates.
- [ ] Project per-seat / per-session trial state.
- [ ] Project lifecycle decision history.
- [ ] Project replacement / rollback lineage and active pack composition.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/app/test_capability_market_api.py tests/industry/test_runtime_views_split.py -q
```

---

## Phase 9: Active Drift Detection And Improvement Loop

**Outcome:** activation is not terminal; active capability packages stay inside the evolution loop.

**Files:**
- Add: `src/copaw/learning/skill_gap_detector.py`
- Modify: `src/copaw/predictions/service_context.py`
- Modify: `src/copaw/capabilities/skill_evolution_service.py`
- Test: `tests/predictions/test_skill_candidate_service.py`
- Test: `tests/app/test_industry_api.py`

- [ ] Detect active artifact degradation.
- [ ] Distinguish:
  - small-step revision candidate
  - replacement candidate
  - retirement pressure
- [ ] Reuse `cc`-style improvement ideas only for governed revisions of existing active artifacts.
- [ ] Keep local self-authored revision as a bounded fallback path, not the default answer to every degradation signal.
- [ ] Do not allow silent mutation of active role-wide skills without a lifecycle pass.

**Verification:**
```powershell
PYTHONPATH=src python -m pytest tests/predictions/test_skill_candidate_service.py tests/app/test_industry_api.py -q
```

---

## Global Acceptance Criteria

- [ ] A repeated failure/success pattern can create a formal candidate.
- [ ] External auto-installed artifacts and local self-authored/generated fallback artifacts normalize into the same candidate lifecycle.
- [ ] The top-level lifecycle truth can represent both skill candidates and MCP-native candidates without forcing MCP into a skill-only schema.
- [ ] Existing active installed/enabled artifacts can be imported into the lifecycle ledger without forced reinstall.
- [ ] Donor adoption and healthy-version reuse are evaluated before new local artifact authoring.
- [ ] A candidate can synthesize a governed fallback artifact package when donor-first paths do not close the gap.
- [ ] A new artifact defaults to seat/session trial, not direct role promotion.
- [ ] The same healthy artifact version is reused across tasks when scope and environment contract still match.
- [ ] Multi-seat trial evidence stays isolated per seat/session while still aggregating to candidate-level verdicts.
- [ ] Runtime and evidence can be attributed to a trial.
- [ ] Main brain can promote / replace / rollback / retire via governed mutations.
- [ ] Protected artifacts can be trialed against and proposed for replacement, but cannot be silently auto-replaced.
- [ ] Capability layer recomposition stays on the canonical role/seat/session chain.
- [ ] Runtime Center can show candidate/trial/decision history.
- [ ] Active artifacts can re-enter the loop through drift detection.

---

## Final Verification

Run at the end:

```powershell
PYTHONPATH=src python -m pytest tests/app/test_industry_service_wiring.py tests/industry/test_runtime_views_split.py tests/kernel/test_query_execution_runtime.py tests/agents/test_react_agent_tool_compat.py tests/app/test_capability_market_api.py tests/app/industry_api_parts/bootstrap_lifecycle.py tests/app/test_industry_api.py tests/app/test_mcp_runtime_contract.py tests/test_mcp_resilience.py tests/capabilities/test_remote_skill_presentation.py tests/app/test_capability_skill_service.py tests/test_skill_service.py tests/app/test_governed_mutations.py -q
```

And adjacent regressions:

```powershell
PYTHONPATH=src python -m pytest tests/app/test_capabilities_execution.py tests/agents/test_skills_hub.py tests/app/test_capabilities_api.py tests/app/test_capability_catalog.py -q
```
