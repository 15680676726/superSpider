# Universal Surface Execution Foundation Design

Date: `2026-04-17`
Status: `draft`
Owner: `Codex`

## 1. Problem

CoPaw already has real browser, desktop, and document execution capabilities, but the current product chain still has a structural gap:

- browser / desktop / document actions are available at the tool and environment layer
- some vertical services can already drive real surfaces
- but there is not yet one formal, profession-agnostic execution foundation that every profession agent can reuse

The current risk is not "the system cannot operate real surfaces". The current risk is:

- one profession can accumulate one private page flow
- another profession can accumulate another private desktop flow
- a third profession can accumulate another document flow
- over time, CoPaw grows parallel execution logics instead of one reusable formal layer

This design closes that gap.

## 2. Goal

Build one formal, profession-agnostic dynamic surface execution foundation for:

- browser
- desktop application
- document

The foundation must let profession agents reuse the same formal execution chain while keeping the planning boundary clean:

- profession agents decide what step should be done
- the foundation observes the current surface, resolves the target, executes one step, verifies the outcome, and writes evidence

This is not a second main brain and not a second profession layer.

## 3. Non-Goals

This round does not:

- replace the main-brain planning chain
- make the foundation decide the business strategy or next profession step
- create a second environment runtime system
- create a second evidence system
- create one hardcoded automation flow per profession
- make Baidu research the universal runtime model

This round also does not require migrating every existing profession immediately.

Phase 1 only needs:

- the formal foundation
- three real profession demonstrations:
  - researcher
  - listing operator
  - writer

These three are only demonstration adapters, not the final profession list.

## 4. Hard Boundaries

### 4.1 Planning Boundary

The foundation does not decide the next business step.

The foundation is only responsible for:

1. observing the current page/window/document
2. locating the intended target
3. executing one action
4. verifying whether the action succeeded
5. writing evidence and returning the latest state

The profession agent is responsible for:

- deciding what should happen next
- deciding what content should be entered
- deciding whether to retry, reroute, or stop

### 4.2 Truth Boundary

This design must not introduce a parallel truth source.

The canonical runtime truth remains in the existing formal chain:

- `EnvironmentMount`
- `SessionMount`
- `TaskRuntime`
- `RuntimeFrame`
- `EvidenceRecord`

If a new structure cannot map back to these objects, it should not be introduced.

### 4.3 Reuse-First Boundary

This design must not rebuild a second browser/desktop/document runtime.

The following existing layers are mandatory reuse targets:

- `src/copaw/environments/models.py`
  - `EnvironmentMount`
  - `SessionMount`
- `src/copaw/environments/lease_service.py`
- `src/copaw/environments/surface_control_service.py`
- `src/copaw/agents/tools/browser_control.py`
- `src/copaw/evidence/models.py`
  - `EvidenceRecord`
- `src/copaw/evidence/ledger.py`
- `src/copaw/routines/service.py`

New code is only allowed to fill the orchestration gap above these layers.

## 5. Current Repo Truth

The current repo already contains most of the low-level foundations needed for this design:

### 5.1 Environment Truth

`src/copaw/environments/models.py` already defines:

- `EnvironmentMount`
- `SessionMount`
- observation/cache related derived records

This means the foundation does not need to invent a second surface session model.

### 5.2 Execution Routing

`src/copaw/environments/surface_control_service.py` already exposes formal cross-surface execution routes:

- `execute_browser_action(...)`
- `execute_document_action(...)`
- `execute_windows_app_action(...)`

This means the foundation does not need to rebuild browser/document/desktop dispatch.

### 5.3 Browser Capabilities

`src/copaw/agents/tools/browser_control.py` already supports real browser primitives including:

- `snapshot`
- `click`
- `type`
- `fill_form`
- `press_key`
- `evaluate`

This means browser dynamic operation is already possible at the lower layer.

### 5.4 Evidence

`src/copaw/evidence/models.py` and `src/copaw/evidence/ledger.py` already provide the formal evidence path.

This means the foundation should write into the existing evidence chain, not invent a parallel action log system.

### 5.5 Routine / Replay Assets

`src/copaw/routines/service.py` already provides a formal place for replay/diagnosis style assets.

This should be reused where appropriate for inspection, replay, and operator-visible traces.

## 6. Formal Architecture

The new foundation should sit above existing environment and action primitives and below profession-specific execution logic.

### 6.1 Layer Position

Recommended placement:

`src/copaw/environments/surface_execution/`

This keeps the foundation in the execution/environment layer, not in profession-specific services.

### 6.2 Internal Modules

The foundation should be split into these focused modules:

- `service.py`
  - one-step orchestration owner
- `observer.py`
  - reads current surface state
- `resolver.py`
  - maps a profession hint to a concrete target
- `executor.py`
  - runs the action through existing surface control paths
- `verifier.py`
  - checks whether the intended result actually happened
- `evidence.py`
  - writes before/after/action/verification evidence
- `adapters/browser.py`
- `adapters/desktop.py`
- `adapters/document.py`

The profession layer should only call the foundation owner, not directly call browser/desktop/document action tools.

## 7. Formal Typed Contracts

Phase 1 should introduce typed contracts, but should avoid new dedicated persistence tables unless they are proven necessary.

### 7.1 `SurfaceExecutionStep`

Represents one profession-requested execution step.

Required fields:

- `surface_kind`
  - `browser | desktop | document`
- `intent_kind`
  - for example:
  - `observe`
  - `click`
  - `input`
  - `select`
  - `upload`
  - `read`
  - `save`
  - `submit`
- `target_hint`
  - natural-language target description from the profession agent
- `input_payload`
  - typed content to enter/select/upload
- `success_assertion`
  - what must become true after the action
- `failure_policy`
  - what the foundation may do locally when the step fails

This object is not a full profession plan. It only represents one step.

### 7.2 `SurfaceObservation`

Represents what the foundation sees on the current surface.

Required content:

- current surface identity
  - page/window/document identity
- current actionable targets
- current readable content summary
- blockers/risk cues
- enough metadata for target resolution and verification

This object is not long-term memory.

### 7.3 `SurfaceActionResult`

Represents the outcome of one executed step.

Required fields:

- `status`
  - `succeeded | blocked | failed`
- `failure_class`
  - if not successful
- `verification_passed`
- `resolved_target`
- `latest_observation`
- `evidence_ids`
- `recovery_hint`

This object is not a profession summary. It is one-step execution output.

## 8. Execution Flow

The canonical one-step flow is:

1. profession agent produces a `SurfaceExecutionStep`
2. kernel binds it to the formal `EnvironmentMount / SessionMount`
3. `SurfaceObserver` reads the current surface
4. `TargetResolver` resolves the actual target from `target_hint + observation`
5. `SurfaceExecutor` runs the requested action through existing surface control
6. `ResultVerifier` checks whether the intended success condition is now true
7. `SurfaceEvidenceWriter` records before/after/action/verification evidence
8. `SurfaceActionResult` is returned to the profession agent

The profession agent then decides the next step.

## 9. Failure Classes and Recovery Boundary

Phase 1 should formalize these failure classes:

- `target-not-found`
- `blocked-by-ui`
- `action-failed`
- `verification-failed`
- `environment-lost`
- `human-required`

The foundation may only perform bounded local recovery:

- `retry-once`
- `refresh-observation`
- `reacquire-target`
- `return-blocked`

The foundation must not:

- change the business goal
- invent a new profession strategy
- switch sites/products/documents on its own

## 10. Evidence Contract

Every step must leave formal evidence, at minimum:

- `before-observation`
- `action-evidence`
- `after-observation`
- `verification-result`

These should reuse the existing `EvidenceRecord` chain.

Expected evidence sources include:

- surface snapshots
- structured target resolution output
- action payload summaries
- verification summaries
- failure/blocker summaries

This rule applies equally to:

- browser
- desktop application
- document

## 11. Persistence Strategy

Phase 1 should prefer typed contracts plus reuse of current formal persistence, instead of introducing a second execution database model.

Recommended persistence mapping:

- `SurfaceExecutionStep`
  - formal typed input contract
- `TaskRuntime`
  - current execution state / step state
- `RuntimeFrame`
  - before/after observation payloads and recovery points
- `EvidenceRecord`
  - action and verification evidence
- `EnvironmentMount / SessionMount`
  - continuity and live handle truth

Phase 1 should avoid introducing a new dedicated step-history repository unless the existing formal chain proves insufficient.

## 12. Acceptance Standard

The acceptance standard must cover browser, desktop application, and document equally.

### 12.1 Browser

- can dynamically read the current page structure
- can locate input/button/select/upload/result areas without a hardcoded fixed flow
- can execute browser actions through the formal chain
- can verify whether the result actually took effect
- can classify login/captcha/popup/permission blockers correctly
- can re-enter the same formal session continuity after refresh/reopen
- leaves formal evidence at each step

### 12.2 Desktop Application

- can dynamically identify the current window/app identity and major actionable regions
- can locate inputs/buttons/menus/lists/dialogs without hardcoded screen coordinates
- can execute click/input/shortcut/select/save/export style actions
- can detect focus loss, modal blockers, permission dialogs, and wrong-window risk
- can verify that the action actually happened in the intended application
- can classify interruption/window-loss/handle-loss correctly
- leaves formal evidence at each step

### 12.3 Document

- can dynamically read the current document state
- can locate title/body/section/selection/table/editable region
- can execute insert/replace/append/delete/save/export style actions
- can verify that content was actually written and persisted
- can classify readonly/locked/save-failed/format-conflict blockers correctly
- can confirm persistence after close/reopen when the surface supports it
- leaves formal evidence at each step

### 12.4 Cross-Surface Shared Acceptance

- browser, desktop, and document all go through the same formal `observe -> resolve -> execute -> verify -> evidence` chain
- profession agents provide step intent, not low-level action scripts
- `researcher + listing operator + writer` all demonstrate the shared foundation on real targets
- failures are classified
- blockers are returned
- continuity is recoverable
- evidence is operator-visible
- results can write back to the formal execution chain instead of stopping in ad-hoc strings

### 12.5 Additional Governance Acceptance

- high-risk external effects must still respect `auto / guarded / confirm`
- the foundation must verify target identity before mutating the surface
- one live surface must not be mutated concurrently by multiple execution chains without formal leasing rules
- cross-surface steps must preserve the same `work_context / control_thread / evidence chain`
- refresh/reopen/reentry must not cause duplicate submit/publish/save/upload actions

## 13. Phase 1 Profession Demonstrations

Phase 1 should demonstrate the shared foundation through three real profession adapters:

- `researcher`
  - real web research flow
- `listing operator`
  - real product/listing form flow
- `writer`
  - real editor/document writing flow

These are only demonstration adapters. They must not become the fixed profession boundary of the foundation.

## 14. Cutover and Retirement Rules

Phase 1 must start retiring the following bad patterns:

- profession services directly calling low-level browser tools
- profession-specific private page flow logic as the long-term main path
- treating `BaiduPageResearchService` as the universal surface execution model
- hardcoded URL/selector/step chains as the formal execution strategy
- execution results that stop in ad-hoc strings instead of the formal evidence chain

The correct final direction is:

- vertical services may keep scenario adapters
- but surface observation, target resolution, action execution, verification, and evidence must converge into one shared foundation

## 15. Implementation Principle

This round must be implemented as:

- reuse-first
- foundation-first
- profession-demo-second

Not as:

- profession-first duplicated automation
- second runtime system
- second evidence system
- second environment truth system

## 16. Summary

The correct target is not "build three profession automations".

The correct target is:

build one formal universal surface execution foundation, reuse the current environment/evidence/execution spine, and prove it through three real profession demonstrations.
