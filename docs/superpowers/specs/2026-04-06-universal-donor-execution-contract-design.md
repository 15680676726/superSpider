# Universal Donor Execution Contract Design

## Status

- Date: `2026-04-06`
- Scope: design only
- Goal: turn donor runtime fragility into one common platform contract, not per-project repair

## 1. Goal

`CoPaw` already has the first half of donor assimilation:

- discover
- materialize
- classify
- compile formal capability objects

What is still missing is the second half:

- donor receives a formal provider contract
- donor executes inside a bounded fail-fast envelope
- donor/host mismatches are normalized or blocked by one common compatibility contract

The target is not "fix OpenSpace."

The target is:

- any donor with `MCP / API / SDK / CLI-runtime` intake
- must pass through the same provider/execution/compatibility contracts
- before CoPaw can honestly claim that the donor is formally usable

## 2. Why This Spec Exists

The current donor-first base proved that CoPaw can:

- find real open-source donors
- install them
- classify their protocol surfaces
- compile formal `project-package / runtime-component / adapter`
- execute at least some compiled actions

But real live probing exposed a harder truth:

- install success does not imply callable business execution
- a donor may still depend on hidden host assumptions
- a donor may hang instead of failing fast
- a donor may guess provider configuration incorrectly

Those are not one-project bugs.

They are the missing universal execution contracts of the external expansion base.

OpenSpace is only the motivating sample that exposed the platform gap.

## 3. Core Judgment

`One path, many donors` here means:

- donor-specific transports may differ
- donor-specific packaging may differ
- donor-specific startup commands may differ
- but the execution contracts must not differ

The universal donor execution base therefore needs exactly three common contracts:

1. `Donor Provider Injection Contract`
2. `Donor Execution Envelope Contract`
3. `Donor Host Compatibility Contract`

These contracts sit after materialization and before formal promotion.

## 4. Architecture Boundary

This design must stay on the existing formal spine:

- `CapabilitySourceProfileRecord`
- `DonorPackageRecord`
- `CapabilityCandidateRecord`
- `SkillTrialRecord`
- `CapabilityLifecycleDecisionRecord`
- `CapabilityMount`
- `EvidenceRecord`

This design must not create:

- a donor-local provider manager
- a donor-local lifecycle ledger
- a second runtime truth chain
- project-specific special-case branches in the core execution path

In the repository's architecture questions:

1. This belongs primarily to `capabilities / state / kernel / evidence`.
2. It attaches to the existing donor/package/candidate/trial/lifecycle/capability truth chain.
3. It must not bypass governed execution.
4. It must not introduce a fourth capability vocabulary.
5. It must emit provider resolution, probe, timeout, compatibility, and action evidence.
6. It replaces the current "installed donor may still secretly rely on host guesses" limitation.

## 5. Contract 1: Donor Provider Injection

### 5.1 Problem

Today a donor may do one of the following:

- read raw process env vars
- guess provider model names
- read host config files directly
- silently fall back to defaults

That makes donor execution nondeterministic and host-dependent.

### 5.2 Rule

CoPaw must resolve provider truth first, then inject it into the donor.

The donor must not treat "guess host config by itself" as the primary execution path.

### 5.3 Formal Meaning

Provider truth remains owned by CoPaw's formal provider/runtime layer.

The donor only receives a resolved execution contract, for example:

- resolved provider kind
- resolved model
- auth mode
- injected credentials or credential references
- api base
- extra headers
- timeout policy
- retry policy
- provenance of the resolved provider choice

This is an execution contract, not a second truth store.

### 5.4 Injection Modes

Allowed injection modes:

- environment injection
- argument injection
- config-file patch injection
- startup wrapper injection

Every donor runtime must declare which one it consumes.

### 5.5 Hard Rules

- donor direct host-config scraping may exist only as a last-resort compatibility bridge
- it must never remain the primary formal path
- provider resolution must be observable in evidence
- raw secrets must not be copied into operator-visible evidence payloads

## 6. Contract 2: Donor Execution Envelope

### 6.1 Problem

A donor action may currently:

- block for too long
- never emit a heartbeat
- return no explicit failure
- force the caller to wait indefinitely

That turns real failures into "looks hung" experiences.

### 6.2 Rule

Every donor action must execute inside one common governed envelope.

The envelope owns bounded time, cancellation, liveness, and failure reporting.

### 6.3 Required Envelope Fields

At minimum:

- `startup_timeout_sec`
- `action_timeout_sec`
- `idle_timeout_sec`
- `heartbeat_interval_sec`
- `cancel_grace_sec`
- `kill_grace_sec`
- `max_retries`
- `retry_backoff_policy`
- `output_size_limit`
- `probe_kind`
- `probe_timeout_sec`

### 6.4 Required Runtime Outcomes

Every donor action must end in one of these formal outcomes:

- `succeeded`
- `failed`
- `timeout`
- `cancelled`
- `degraded`
- `blocked`

Not "maybe still running forever."

### 6.5 Error Taxonomy

Errors should at minimum normalize into:

- `auth_error`
- `provider_resolution_error`
- `config_error`
- `compatibility_error`
- `startup_error`
- `probe_error`
- `network_error`
- `protocol_error`
- `runtime_error`
- `timeout_error`
- `cancellation_error`

### 6.6 Hard Rules

- external donor actions must not default to unbounded wait
- long-running actions still need bounded heartbeat and cancellability
- timeout policy must be explicit and visible in evidence
- timeout failure must not be mistaken for success or silent incompletion

## 7. Contract 3: Donor Host Compatibility

### 7.1 Problem

A donor may assume host facts that CoPaw never formally declared, such as:

- config file field names
- provider naming conventions
- env var names
- path layout
- cwd semantics
- runtime binaries
- OS support
- browser/desktop availability

Without a compatibility contract, every donor turns into bespoke glue logic.

### 7.2 Rule

Every donor must be checked against one common host compatibility contract before promotion.

### 7.3 Compatibility Inputs

The contract should cover at least:

- supported OS / architecture
- required runtimes (`python`, `node`, `java`, etc.)
- package manager assumptions
- required provider contract kind
- required surfaces (`shell`, `browser`, `desktop`, `document`, `network`)
- required env keys
- config location expectations
- workspace / cwd expectations
- startup/health/stop expectations

### 7.4 Compatibility Outcomes

Formal outcomes should be:

- `compatible_native`
- `compatible_via_bridge`
- `blocked_missing_dependency`
- `blocked_missing_provider_contract`
- `blocked_unsupported_host`
- `blocked_contract_violation`

### 7.5 Generic Bridge Discipline

Bridges are allowed only when they are generic and reusable, for example:

- provider field alias normalization
- env alias normalization
- config path normalization
- cwd/path normalization
- transport wrapper normalization

Bridges are not allowed to become:

- `if donor == X`
- `if repo == Y`
- `if package == Z`

inside the main execution path.

## 8. Promotion Boundary

This spec makes the adoption boundary explicit.

### 8.1 Honest Capability States

The platform should distinguish these truths:

- `installed`
  - materialized but not yet operationally proven
- `runtime_operable`
  - can start/probe/stop inside the formal runtime envelope
- `adapter_probe_passed`
  - can execute at least one formal business action through CoPaw
- `primary_action_verified`
  - the donor's main business action has passed real verification

### 8.2 Hard Rule

Only `adapter_probe_passed` and above may be described as "formally usable business capability."

`installed` and `runtime_operable` must not be overstated.

## 9. Updated Assimilation Pipeline

The universal donor pipeline should become:

`discover -> normalize -> classify -> materialize -> resolve provider contract -> resolve compatibility -> run minimal probe -> compile/promote`

### 9.1 Minimal Probe Rules

Probe rules depend on landing type:

- `project-package`
  - install proof and bounded runnable proof may be enough
- `runtime-component`
  - startup + readiness + stop proof required
- `adapter`
  - at least one minimal business action must succeed

### 9.2 Primary Action Verification

For donors whose main value is one dominant action, such as delegation/execution engines, the platform should additionally track whether the main action itself has been verified.

That is a stronger truth than "some auxiliary action worked."

## 10. What OpenSpace Exposed

OpenSpace revealed three universal gaps:

- provider truth was not formally injected
- execution waited too long without bounded fail-fast semantics
- donor/host compatibility relied on host-guessing instead of one normalized contract

This spec does not treat those as OpenSpace-only bugs.

It treats them as platform gaps that any serious donor can expose.

## 11. Non-Goals

This spec does not promise:

- that every open-source repository will auto-work
- that donor metadata is no longer needed
- that all languages/build systems are already covered
- that donors may bypass CoPaw governance if they provide their own runtime logic

This spec also does not allow:

- exposing raw donor protocol surfaces directly to the main brain
- treating donor-local config discovery as formal truth
- writing project-specific special cases into the core donor execution path

## 12. Acceptance Criteria

This design is considered implemented only when all of the following are true:

1. A donor with a valid provider dependency receives provider truth from CoPaw through a formal injection contract.
2. A donor missing valid provider truth fails fast with typed error output instead of appearing hung.
3. A donor with host/runtime incompatibility is normalized or blocked through one formal compatibility result.
4. Adapter donor actions no longer wait indefinitely by default.
5. Runtime Center / evidence surfaces can show:
   - provider resolution result
   - compatibility result
   - envelope timeout/cancel/failure result
   - probe result
6. The same machinery works without OpenSpace-specific branches in the core path.

## 13. Recommended Next Step

The next step is not implementation directly in random files.

The next step is:

- write one implementation plan that splits the work into:
  - provider injection
  - execution envelope
  - compatibility contract
  - probe/promotion truth
  - evidence/read-model updates

Only after that should code changes begin.
