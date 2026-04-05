# MCP-First Donor Adapter Assimilation Design

## Status

- Date: `2026-04-06`
- Scope: design only
- Goal: define the common external-donor intake contract for `MCP -> API/SDK -> runtime`, without adding project-specific special cases

## 1. Goal

`CoPaw` should absorb external open-source projects through one common external expansion base:

- native `MCP` first
- `API/SDK` second
- `CLI/runtime` last
- all three must converge into CoPaw-owned formal capability objects

The target is not:

- writing per-project custom adapters
- exposing raw external protocols directly to the main brain
- treating "installed" or "can start" as equivalent to "formally usable business capability"

The target is:

- external protocols stay external
- CoPaw compiles them into formal `adapter / runtime / project` capability truth
- the main brain and execution agents consume only CoPaw formal capabilities

## 2. Core Judgment

The correct platform rule is:

- `MCP-first but not MCP-only`

Meaning:

- if a donor already exposes a stable native `MCP`, CoPaw should prefer that path
- if a donor has no usable `MCP` but does expose a stable `HTTP API`, `OpenAPI`, or callable `SDK`, CoPaw should use that instead
- if a donor has neither `MCP` nor usable `API/SDK`, it may still land as `project-package` or `runtime-component`, but it must not be presented as a formal business adapter

This keeps CoPaw aligned with current ecosystem reality:

- `MCP` is increasingly standardized and often simpler when present
- `API/SDK` remains more common than `MCP` across the wider open-source ecosystem

## 3. Architecture Answers

This design must satisfy the repository's six architecture questions.

### 3.1 Which layer does it belong to?

Primarily:

- `capabilities/`
- `state/`
- `kernel/`
- `evidence/`

Secondarily:

- `app/runtime_center`
- `predictions/governance`

### 3.2 What single source of truth does it connect to?

It must stay on the existing formal spine:

- `CapabilitySourceProfileRecord`
- `DonorPackageRecord`
- `CapabilityCandidateRecord`
- `SkillTrialRecord`
- `CapabilityLifecycleDecisionRecord`
- `CapabilityMount`
- `EvidenceRecord`

No donor-local capability manager, no donor-local runtime truth, and no second adoption ledger may be introduced.

### 3.3 Does it bypass the unified kernel?

No.

All formal donor actions must still go through CoPaw governed write paths:

- candidate creation
- materialization
- scoped trial
- lifecycle decision
- promotion / replace / rollback / retire

### 3.4 Does it add a new capability vocabulary?

No.

External protocols may differ, but internal formal capability language remains:

- `project-package`
- `runtime-component`
- `adapter`

`MCP`, `HTTP API`, `SDK`, and `CLI` are transport or intake facts, not new first-class internal product vocabularies.

### 3.5 What evidence does it produce?

At minimum:

- discovery provenance
- protocol classification
- install/materialization evidence
- adapter compilation evidence
- scoped trial evidence
- lifecycle decision evidence
- runtime execution attribution

### 3.6 What old limitation does it replace?

It replaces these wrong assumptions:

- install success == usable capability
- runtime start success == business capability closure
- raw shell execution == formal donor integration
- per-project custom special cases == external expansion strategy

## 4. Formal Object Model

This design intentionally reuses the current donor-first base instead of inventing a parallel system.

### 4.1 `CapabilitySourceProfileRecord`

Owns source truth such as:

- source kind
- active source chain identity
- mirror/fallback provenance
- region/source profile

It answers: where did this donor come from?

### 4.2 `DonorPackageRecord`

Owns normalized donor identity such as:

- canonical package/project id
- owner/repo or package coordinates
- normalized aliases
- package lineage

It answers: what external project is this?

### 4.3 `CapabilityCandidateRecord`

Owns trial-ready intake truth such as:

- canonical donor/package linkage
- detected protocol surface
- candidate summary
- source lineage
- overlap/equivalence metadata

It answers: is this donor worth trying?

### 4.4 `SkillTrialRecord`

Despite the historical name, this remains the common scoped trial record.

It answers:

- where is this donor being tried
- by which seat/session/work-context
- with what evidence
- under which attribution

### 4.5 `CapabilityLifecycleDecisionRecord`

Owns governed decisions:

- `continue_trial`
- `keep_seat_local`
- `promote_to_role`
- `replace_existing`
- `rollback`
- `retire`

### 4.6 `CapabilityMount`

This remains the only formal capability object exposed to the main brain and execution agents.

Main rule:

- external intake facts are not consumed directly by the main brain
- only compiled CoPaw capability mounts are consumed

## 5. Common Assimilation Pipeline

All external donors must use the same common pipeline:

`discover -> normalize -> protocol classify -> candidate -> materialize -> compile adapter -> scoped trial -> evidence -> lifecycle decision`

### 5.1 Discover

Discovery only identifies external possibilities.

Discovery must not:

- mutate formal active capability truth
- auto-promote anything
- skip source provenance

### 5.2 Normalize

Normalization merges raw source hits into one donor identity.

This stage must handle:

- canonical package identity
- source aliases
- mirror lineage
- duplicate source hits

Hard rule:

- dedup must happen before candidate expansion

### 5.3 Protocol Classify

Protocol classification determines the donor's best formal intake path.

Allowed outcomes:

- `native_mcp`
- `api`
- `sdk`
- `cli_runtime`

This stage records intake facts only.

It does not yet decide whether the donor is formally adoptable as a business adapter.

### 5.4 Candidate

Candidate is the first formal persisted system state for an external donor opportunity.

Before candidate state, the donor is just an outside possibility.

### 5.5 Materialize

Materialization prepares a bounded runnable or callable donor surface:

- download or fetch package
- create isolated environment if needed
- persist donor/package/runtime contract truth

Install success alone never means formal capability success.

### 5.6 Compile Adapter

This is the key platform step.

CoPaw must compile external intake into internal capability form:

- native `MCP` -> CoPaw `adapter`
- `HTTP/OpenAPI` -> CoPaw `adapter`
- callable `Python/Node SDK` -> CoPaw `adapter`
- `CLI/runtime` only -> `project-package` or `runtime-component`, not business adapter

### 5.7 Scoped Trial

Trial is the default proving mechanism.

Default scopes:

- `session`
- `seat`
- `work_context`

Role-wide adoption is not the default.

### 5.8 Evidence

Evidence must come from real effect:

- callable invocation outcome
- typed output
- runtime behavior
- recovery/rollback behavior

Not enough:

- README claims
- install logs
- "process started"

### 5.9 Lifecycle Decision

Only after trial evidence may CoPaw decide:

- continue trial
- keep local
- promote
- replace
- rollback
- retire

## 6. Protocol Priority Rule

The donor intake priority must be fixed and generic.

### 6.1 Native `MCP` First

If a donor exposes a stable, maintained native `MCP` surface, CoPaw should prefer that path.

Reasons:

- lower adapter authoring cost
- typed tool schema already exists
- host/tooling ecosystem support is improving

### 6.2 `API/SDK` Second

If there is no stable native `MCP`, but there is a stable `HTTP API`, `OpenAPI`, or callable `SDK`, CoPaw should use that path.

Reasons:

- wider ecosystem coverage
- fewer false negatives than requiring `MCP`

### 6.3 `CLI/runtime` Last

If neither `MCP` nor `API/SDK` exists, the donor may still be useful, but only as:

- `project-package`
- `runtime-component`

It must not be marketed internally as a formal business adapter unless a typed callable surface is later compiled.

## 7. Internal Compilation Rule

The internal compilation rule is the most important boundary:

- transport may stay external
- capability truth must stay internal

Concretely:

- main brain never calls raw `MCP` method names
- main brain never calls raw external HTTP endpoints
- main brain never imports raw donor SDK modules
- main brain never builds donor shell commands directly

Instead, the main brain and execution agents only see CoPaw formal capabilities such as:

- `adapter:*`
- `runtime:*`
- `project:*`

## 8. Auto-Generation Boundary

The external expansion base may automatically generate common intake scaffolding, but only within strict limits.

### 8.1 Safe To Auto-Generate

Allowed common automation:

- source normalization
- protocol classification
- package/runtime contract extraction
- isolated materialization setup
- adapter skeleton generation
- typed action schema skeletons
- default evidence attribution wiring
- scoped trial creation

### 8.2 Must Not Be Auto-Generated As Adoption Truth

The following may not be auto-promoted into formal capability success:

- install success
- process start success
- arbitrary raw shell command success
- README-derived guesses
- undocumented hidden endpoints

## 9. Hard Blocking Rules

The system must explicitly block these cases from formal adapter adoption:

- no formal callable surface, only README/manual instructions
- UI-only usage path when the current strategy is non-UI integration
- only `CLI/runtime`, but presented as if it were a business adapter
- arbitrary shell/env/cwd freedom required for normal usage
- no stable typed input/output surface
- no scoped trial evidence
- direct main-brain exposure to external raw protocol surfaces
- project-specific special-case logic in the common donor base

## 10. No Project-Specific Special Cases

This design must stay generic.

`OpenSpace` may be used only as a verification sample.

Hard rule:

- no `OpenSpace`-only config fields
- no `OpenSpace`-only router branches
- no `OpenSpace`-only prompt branches
- no `if donor == X` expansion policy in the common base

At most, the system may support generic donor hints contracts, but those hints must be:

- protocol-generic
- schema-bounded
- reusable across many donors

## 11. Promotion Standard

A donor may become a formal business adapter only when all of the following are true:

- stable callable intake surface exists: `MCP` or `API/SDK`
- it compiles into a CoPaw `adapter`
- it has typed input/output contracts
- it passes scoped trial with real evidence
- rollback or failure handling is defined
- it does not bypass governance
- it does not create a second truth chain

If these conditions are not met, the donor may still be useful, but it must remain lower in the formal hierarchy.

## 12. Risk And Governance

Default governance posture:

- candidate creation: fast
- scoped trial: fast but bounded
- role-wide promotion: governed
- replacement/retirement: governed

This is intentionally not "strict everywhere."

The system should be permissive at trial time and strict at promotion time.

## 13. Runtime Center Visibility

Runtime Center must be able to show this donor chain without inventing a second UI truth:

- normalized donor identity
- detected intake protocol
- compiled capability landing
- scoped trial state
- lifecycle decision state
- replacement/rollback history
- evidence attribution

The operator must be able to distinguish:

- discovered donor
- candidate donor
- trialed donor
- promoted donor
- retired donor

## 14. Rollout Direction

The correct rollout order is:

1. keep current donor-first spine
2. add generic protocol classification
3. add generic adapter compilation rules
4. keep `MCP-first but not MCP-only`
5. block project-specific special cases
6. prove the base with real sample donors from different protocol shapes

The proof samples must validate the common base, not become permanent product exceptions.

## 15. Final Standard

This design is successful only if:

- CoPaw can absorb external projects through one common public base
- native `MCP` is preferred when available
- `API/SDK` remains available when `MCP` is absent
- the main brain never consumes raw external protocol surfaces
- every successful donor still lands as CoPaw formal capability truth
- no single donor receives custom architecture privilege

The final discipline is:

- `MCP` is a preferred intake path
- not the platform's internal truth model
