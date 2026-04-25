# 2026-04-03 Autonomous Capability Evolution Loop Design

## Status Correction (`2026-04-07`)

This document remains valid for the governed `capability-evolution` slice only.

It is not the full "second-tier" end state for main-brain-controlled self-optimization.

The full second-tier target is broader:

- scheduled main-brain review cadence
- discovery / diagnosis intake
- unified optimization case truth
- baseline vs challenger trial discipline
- evidence-backed evaluator
- lifecycle decisions across skill / MCP / external source / package
- Runtime Center visibility for the whole loop

This file should therefore be read as:

- `capability package evolution design`

not as:

- `the entire autonomous self-optimization architecture`

When the two differ, the broader second-tier design takes precedence and this file remains the external-source/package/lifecycle slice inside that larger loop.

## Landed Boundary (`2026-04-07`)

What is now live in code for this slice:

- external-source / candidate / package truth stays formal and shared
- trial records and lifecycle decisions stay on the same truth chain
- evaluator verdicts now write back into lifecycle decisions instead of floating as side metadata only
- MCP challengers can now enter the same governed trial vocabulary as skill challengers

What this file should no longer imply:

- that capability evolution by itself equals the whole self-optimization loop
- that skill-only challengers are the mainline and MCP is a side path

## 1. Purpose

This document defines the complete-loop design for how CoPaw should autonomously discover, ingest, reuse, synthesize only when necessary, trial, promote, replace, and retire long-lived capability packages in the formal long-horizon autonomy architecture.

This design is intentionally broader than "auto-generate a skill". The formal target is:

- discover repeatable capability gaps
- decide the correct capability form
- prefer an external source or reusable package when one already fits
- synthesize a governed artifact only when external-source-first reuse still leaves a real gap
- trial it on the right scope
- evaluate it with runtime evidence
- promote / replace / rollback / retire it
- continuously monitor drift after activation

The resulting loop is the formal capability-evolution subsystem for long-term autonomy.

---

## 2. Design Constraints

The loop must obey repository architecture rules:

- no second truth source
- no parallel runtime main loop
- no fourth capability semantics
- no prompt-only hidden capability state
- all important mutations must stay governed and evidence-backed

The loop must also obey the external-source-first platform rule:

- CoPaw is the governance/runtime base, not a built-in skill factory
- mature external projects, MCPs, adapters, and helper runtimes are the default growth path
- local self-authored artifacts are fallback-only
- local authoring must never become the silent default just because the system can write files

The loop must stay on CoPaw's canonical chain:

- `CapabilityMount`
- `IndustryRoleBlueprint`
- `AgentRuntimeRecord`
- `EnvironmentMount`
- `SessionMount`
- `EvidenceRecord`
- `DecisionRequest`

It must not create a shadow "skill manager" that bypasses capability governance.

---

## 3. Artifact Discipline Boundary

Three external artifact-discipline patterns remain useful here:

1. `SKILL.md` as the final artifact shape for prompt-oriented reusable process knowledge.
2. Skill discovery / surfacing / loading discipline.
3. Small-step improvement of an already-existing skill artifact.

Those external artifact patterns are not the lifecycle-governance source of truth. They center on loading, injecting, discovering, and lightly improving skill files. They do not provide CoPaw's required formal loop of:

- candidate truth
- seat/session trial governance
- role promotion
- replacement budgeting
- rollback truth
- runtime-center-visible lifecycle history

CoPaw should therefore keep artifact discipline on the artifact side, while keeping lifecycle governance on its own formal truth chain.

---

## 4. Core Thesis

CoPaw should not optimize for "automatically write a skill".

CoPaw should optimize for:

`automatically evolve the correct capability package for the formal autonomy system`

The first preference order is:

1. adopt an existing external source
2. reuse an already-known healthy artifact/version
3. revise an existing governed local artifact when that is cheaper than replacement
4. author a new local artifact only when the previous three paths still fail to close the gap

In some cases the right result is:

- adoption of an existing external-source package
- reuse of an already-proven package version
- a revision of an existing skill
- an MCP bundle decision
- a role-capability recomposition
- a seat-local capability patch
- a thin local glue artifact

The design therefore centers on capability evolution, not skill generation alone.

---

## 5. Unified Candidate Sources

CoPaw already has two real-world ways to obtain a capability artifact:

1. external source / open-source project / MCP / adapter / remote auto-install path
2. local self-authored / main-brain-requested / writer-authored fallback path

These must not become two promotion systems.

The formal rule is:

- external-source intake is the default candidate source
- local self-authored synthesis is fallback-only candidate supply
- both must normalize into the same `CapabilityCandidateRecord`
- both must pass the same overlap detection, budget governance, scoped trial, lineage, promotion, replacement, and rollback flow

This means:

- an externally fetched skill must not become role-active only because install succeeded
- a locally generated skill must not become role-active only because a file was written
- both paths must be visible in Runtime Center as the same lifecycle object model
- the existence of local writing ability does not justify bypassing external-source search or external-source reuse

The difference between the two paths is source provenance, not lifecycle semantics.

### 5.1 Candidate Source Metadata

`CapabilityCandidateRecord` should explicitly record where the candidate came from.

Minimum source fields:

- `candidate_source_kind`
- `candidate_source_ref`
- `candidate_source_version`
- `candidate_source_lineage`
- `ingestion_mode`

Typical values for `candidate_source_kind`:

- `external_catalog`
- `external_remote`
- `local_authored`
- `local_revision`
- `seat_overlay_promoted`

This preserves auditability without allowing source-specific governance shortcuts.

---

## 6. Formal Candidate Type Boundary

The loop is formally about capability evolution, not only skill evolution.

The top-level candidate truth should therefore be:

- `CapabilityCandidateRecord`

Skill-specific and MCP-specific candidates are typed specializations of that truth, not separate lifecycle systems.

Recommended subtype split:

- `SkillCandidateRecord`
- `McpBundleCandidateRecord`
- `CapabilityPatchCandidateRecord`

Required rule:

- shared governance fields live on `CapabilityCandidateRecord`
- subtype-specific fields live on the typed candidate payload
- MCP candidates must not be forced into a skill-only schema
- if implementation ships the skill slice first, it must still leave the top-level object model open for MCP-native candidates

This prevents a fake "unified loop" that is actually skill-only.

---

## 7. Formal Roles

The loop has five formal roles:

### 5.1 Main Brain

Owns:

- worthiness decision
- candidate form decision
- trial scope decision
- lifecycle decision

Does not own:

- artifact authoring
- runtime trial execution details

### 5.2 Artifact Adapter / Writer

Owns:

- external-source artifact normalization and packaging
- thin local glue artifact synthesis when external-source-first paths still leave a gap
- companion `SKILL.md` / `scripts/` / `references/` only when they are actually needed
- verification contract authoring

Does not own lifecycle promotion.

### 5.3 Trial Executor

Owns:

- real execution on seat/session scope
- runtime evidence generation
- trial outcome data

Does not own promotion.

### 5.4 Capability Governor

Owns:

- apply promote / replace / rollback / retire
- enforce capability budgets
- recompute role / seat / session capability layers

### 5.5 Runtime Observer / Learning

Owns:

- ongoing gap detection
- trial evaluation aggregation
- active drift detection
- replacement pressure detection

---

## 8. Complete Loop

The complete loop has ten stages.

### 6.1 Detect

The system continuously watches for:

- repeated failure clusters
- repeated success patterns
- repeated human takeover
- repeated session overlay reuse
- role-pack overload
- capability contention
- environment drift
- newly available external capability sources

### 6.2 Classify

Main brain classifies the pressure into one of:

- `missing_capability`
- `poor_existing_skill`
- `temporary_overlay_becoming_permanent`
- `role_pack_overloaded`
- `mcp_orchestration_gap`

### 6.3 Decide Form

Main brain decides the candidate form:

- `new_skill_candidate`
- `skill_revision_candidate`
- `capability_patch_candidate`
- `mcp_bundle_candidate`
- `role_pack_recomposition_candidate`

This is a major architectural difference from a skill-only system.

### 6.4 Resolve Donor Or Reuse Path

Before any new local artifact is authored, the system must explicitly try:

- governed external-source adoption
- healthy-version reuse
- existing local artifact revision

Only if those paths still fail should the loop proceed to local artifact drafting.

### 6.5 Draft Fallback Artifact

If the chosen form still needs a new or revised local artifact after external-source-first resolution, the main brain dispatches an `artifact-writer` owner to synthesize:

- `SKILL.md`
- `scripts/`
- `references/`
- allowed-tools contract
- required mounts
- verification plan

### 6.6 Attach Trial

The default trial sequence is:

- first `session overlay`
- then `seat instance`
- only later `role prototype`

New capability artifacts must not default directly to role-wide activation.

### 6.7 Run Trial

Trial execution must happen in real runtime conditions:

- real task chain
- real work context
- real environment mounts
- real writeback / evidence path
- real seat contention and runtime governance

### 6.8 Evaluate

Observer / learning aggregates:

- completion rate
- failure rate
- operator intervention rate
- handoff rate
- latency summary
- evidence quality
- environment friction
- comparison with previous capability path

### 6.9 Decide Lifecycle

Main brain decides:

- `continue_trial`
- `promote_to_role`
- `keep_seat_local`
- `replace_existing`
- `rollback`
- `retire`

### 6.10 Recompose Capability Layers

Capability governor applies the decision onto the formal layers:

- role prototype capability pack
- seat instance capability pack
- cycle delta pack
- session overlay

### 6.11 Monitor Drift

After activation, the system keeps monitoring:

- regression
- overlap pressure
- capability drift
- environment dependency drift
- candidate replacement pressure

Active capability packages remain inside the loop. Activation is not terminal.

---

## 9. Formal Objects

### 9.1 `CapabilityCandidateRecord`

Formal truth for a capability-evolution candidate.

Minimum fields:

- `candidate_id`
- `candidate_kind`
- `industry_instance_id`
- `target_role_id`
- `target_seat_ref`
- `target_scope`
- `status`
- `candidate_form`
- `candidate_source_kind`
- `candidate_source_ref`
- `candidate_source_version`
- `candidate_source_lineage`
- `ingestion_mode`
- `proposed_skill_name`
- `source_gap_kind`
- `summary`
- `replacement_target_ids`
- `required_capability_ids`
- `required_mcp_ids`
- `success_criteria`
- `rollback_criteria`
- `source_task_ids`
- `evidence_refs`
- `created_at`
- `updated_at`

Shared governance fields above apply to every candidate kind.

Typed candidate payload examples:

- skill artifact payload
- MCP bundle/install payload
- seat-local capability patch payload

### 9.2 `SkillCandidateRecord`

Skill-specific view over `CapabilityCandidateRecord`.

Extra fields may include:

- `proposed_skill_name`
- `skill_artifact_kind`
- `references_plan`
- `scripts_plan`

### 9.3 `McpBundleCandidateRecord`

MCP-specific view over `CapabilityCandidateRecord`.

Extra fields may include:

- `mcp_bundle_name`
- `mcp_server_ids`
- `transport_kind`
- `session_mount_requirements`
- `auth_contract`

### 9.4 `SkillDraftArtifactRecord`

Formal mapping from candidate truth to synthesized artifact.

Minimum fields:

- `draft_id`
- `candidate_id`
- `skill_name`
- `skill_path`
- `content_hash`
- `allowed_tools`
- `required_mounts`
- `verification_plan`
- `author_agent_id`
- `created_at`

### 9.5 `SkillTrialRecord`

Formal truth for a trial on a specific scope.

Minimum fields:

- `trial_id`
- `candidate_id`
- `scope_type`
- `scope_ref`
- `started_at`
- `ended_at`
- `task_ids`
- `evidence_refs`
- `success_count`
- `failure_count`
- `handoff_count`
- `operator_intervention_count`
- `verdict`
- `summary`

### 9.6 `SkillLifecycleDecisionRecord`

Formal truth for governance decisions.

Minimum fields:

- `decision_id`
- `candidate_id`
- `decision_kind`
- `from_stage`
- `to_stage`
- `reason`
- `evidence_refs`
- `applied_by`
- `applied_at`

### 9.7 Version And Lineage Fields

Every active or historical capability artifact in this loop must also support:

- `version`
- `lineage_root_id`
- `supersedes`
- `superseded_by`
- `rollback_target`

Without this, long-term replacement and rollback are not governable.

---

## 10. Lifecycle State Machine

The lifecycle states are:

- `candidate`
- `drafting`
- `trial`
- `active`
- `blocked`
- `retired`

Allowed transitions:

- `candidate -> drafting`
- `drafting -> trial`
- `trial -> active`
- `trial -> blocked`
- `trial -> retired`
- `active -> blocked`
- `blocked -> active`
- `active -> retired`

Promotion to role-wide activation only happens through an explicit lifecycle decision, not because a file exists.

---

## 11. Capability Layer Semantics

This design explicitly reuses the existing multi-layer capability model:

- global capability base
- role prototype capability pack
- seat instance capability pack
- cycle delta pack
- session overlay

Required rules:

- new artifacts default to `session` or `seat`
- role-wide promotion requires trial evidence
- replacement must explicitly identify previous targets
- rollback restores the previous effective layer composition

No trial scope may bypass these layers.

---

## 12. Concurrent Trial Discipline

The system must support multiple seats trialing the same candidate without creating trial pollution.

Required rules:

- one candidate version may be trialed by multiple seats at the same time
- each seat/session trial gets its own `SkillTrialRecord`
- candidate-level evaluation aggregates many seat/session trials instead of pretending there was only one run
- artifact payload/cache may be reused across seats when the version and environment contract match
- runtime evidence, handoff, and failure attribution must remain seat-local
- seat-local writer locks and environment isolation must prevent one seat's trial mutations from leaking into another seat

This separates artifact reuse from trial truth.

---

## 13. Budget Governance

Long-term autonomy cannot allow unlimited additive capability growth.

Each governed layer needs explicit budgets:

- role skill budget
- seat skill budget
- MCP budget
- overlap budget

Budget enforcement must support:

- overlap detection
- low-value replacement pressure
- priority-based retirement
- safer candidate rejection when a new artifact adds complexity without net value

Time-in-use is not a sufficient promotion criterion. Fit, quality, stability, and friction matter more.

---

## 14. Baseline Import And Existing Active Artifacts

CoPaw already has active installed/enabled skills and MCP surfaces before this new loop.

Those artifacts must not stay outside the lifecycle truth.

Required migration rule:

- existing active artifacts are imported as `baseline active artifacts`
- baseline import records source, version, lineage root, and current scope
- baseline import may also record pin/protection status
- baseline import does not re-trigger installation or trial by default
- later replacement candidates can target these baseline artifacts through normal lifecycle decisions

This prevents the new loop from governing only future artifacts while legacy-active artifacts remain invisible.

---

## 15. Environment Governance

Every candidate artifact must declare its environment contract.

Minimum declarations:

- required MCP clients
- required tool contracts
- required environment mounts
- auth dependency
- risk level
- evidence contract

A capability artifact that cannot answer "what environment does this require?" is not mature enough for role promotion.

---

## 16. Install And Reuse Discipline

Installation is not a per-task reflex.

Required rules:

- installation happens at artifact/version/scope level, not once per task
- if a seat/session already has a healthy matching artifact version, the runtime reuses it
- reinstall only happens when:
  - candidate version changes
  - environment contract changes
  - health verification fails
  - corruption/recovery requires rebuild
  - operator explicitly requests reset/reinstall

The fast loop should prefer:

- reuse installed artifact
- mount existing artifact
- attach session overlay

and only then:

- install or rebuild

This keeps long-horizon autonomy from degenerating into repeated install churn.

---

## 17. Operator Pins And Protected Capabilities

Autonomy must not silently override hard human constraints.

The lifecycle must support protected capability states such as:

- `pinned_by_operator`
- `required_by_role_blueprint`
- `protected_from_auto_retire`
- `protected_from_auto_replace`

Protected artifacts may still be:

- observed
- compared
- trialed against

But they must not be automatically retired or replaced unless the protection state is explicitly lifted or a governed confirm-path authorizes the change.

Protected replacement should therefore follow this sequence:

1. produce a normal replacement candidate
2. complete seat/session trial and evidence aggregation
3. emit `replace_requested` or equivalent protected-replacement decision
4. require either:
   - operator confirmation
   - or a governed role-blueprint/protection-state mutation
5. only then apply the atomic replace with lineage and rollback preserved

This keeps protected artifacts replaceable, but never silently replaceable.

---

## 18. Service Contracts

Recommended contracts:

### 18.1 Discovery

`PredictionService.propose_capability_candidate(...) -> CapabilityCandidateRecord`

### 18.2 Candidate Normalization

`CapabilitySkillService.normalize_candidate_source(...) -> CapabilityCandidateRecord`

This normalization step must be used for both external and local sources before any draft / trial / activation work starts.

### 18.3 Baseline Import

`CapabilitySkillService.import_active_baseline_artifacts(...)`

This import step should register already-active skills/MCP surfaces into the lifecycle ledger without reinstalling them.

### 18.4 Draft Dispatch

`IndustryService.dispatch_skill_candidate_drafting(candidate_id, owner_agent_id="skill-writer")`

### 18.5 Artifact Materialization

`CapabilitySkillService.materialize_candidate_skill(...)`

### 18.6 Scoped Trial Attach

`IndustryTeamRuntimeService.attach_candidate_to_scope(...)`

### 18.7 Runtime Attribution

`QueryExecutionRuntime` must emit:

- `skill_candidate_id`
- `skill_trial_id`
- `skill_lifecycle_stage`
- `replacement_target_ids`
- `selected_scope`

into runtime metadata and evidence.

### 18.8 Lifecycle Apply

`IndustryService.apply_skill_lifecycle_decision(...)`

with allowed decisions:

- `continue_trial`
- `promote_to_role`
- `keep_seat_local`
- `replace_existing`
- `rollback`
- `retire`

All lifecycle applies must use governed mutations, not side-channel writes.

---

## 19. Runtime Center Visibility

The loop is not complete unless the UI can show it.

Required read-model visibility:

- candidate list and status
- per-seat / per-session trials
- lifecycle decision history
- promoted / replaced / rolled-back artifacts
- current role/seat capability composition
- active drift / replacement pressure

The minimum operator-visible questions that must be answerable are:

- Which role/seat is trialing which candidate?
- Why was it promoted or rolled back?
- What did it replace?
- What evidence justified the decision?
- Is the role pack becoming overloaded?

---

## 20. What Must Not Happen

The following are architectural failures:

- directly writing a new skill file and treating that as completion
- allowing the main brain to become the default artifact author
- treating local self-authored artifacts as the default growth path
- skipping external-source adoption/reuse evaluation because local synthesis is available
- promoting directly to role prototype with no seat/session trial
- silently mutating active role skills from ad-hoc user corrections
- letting session overlay state become a hidden second lifecycle truth
- letting external auto-install promote directly outside `CapabilityCandidateRecord`
- letting local authored/generated skills promote through a separate local-only path
- treating source provenance as a reason to skip overlap detection or budget checks
- forcing MCP candidates into skill-only candidate truth
- re-installing the same healthy artifact for every new task
- automatically replacing operator-pinned or role-required artifacts without governed protection removal

---

## 21. Recommended Implementation Strategy

Implementation should proceed in four macro phases:

1. candidate truth and discovery
2. external-source adoption / reuse / fallback artifact materialization
3. scoped trialing and lifecycle decision
4. continuous drift detection and active artifact improvement

The system should first ship a full governed loop for external-source-first candidates, then extend the same lifecycle model to local revisions and broader capability recomposition. Local new-artifact authoring is not the first milestone; it is the bounded fallback path inside the same governed loop.

---

## 22. Final Recommendation

The recommended strategy for CoPaw is:

`Main-brain-governed complete capability evolution loop`

That means:

- main brain decides
- external-source/reuse path is evaluated first
- writer only fills the remaining bounded gap
- executor trials them
- governor applies lifecycle mutations
- observer keeps the loop alive after activation

This preserves CoPaw's formal autonomy boundaries while still retaining useful artifact-discipline patterns without importing an external product center.
