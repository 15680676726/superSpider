# Python Donor Runtime Contract Design

## Goal

Turn supported GitHub/Python open-source donors into formally installable and operable `project-package / adapter / runtime-component` capabilities that can be started, probed, stopped, observed, and governed inside CoPaw without creating a second truth chain.

## Why This Exists

The current donor-first external project path solved only the first half of the problem:

- discover
- install
- resolve entrypoint
- execute a shell command

That is enough to prove materialization, but it is not enough to prove that an open-source project has become a real runtime capability inside CoPaw.

Right now a Python donor such as `OpenSpace` can land as an installed capability and pass `--help`, but it still behaves like a governed shell wrapper rather than a formal runtime component with:

- runtime state
- readiness truth
- process lifecycle
- stop/restart semantics
- Runtime Center visibility

This design closes that gap for supported Python donors.

## Scope

This design covers only:

- GitHub-hosted Python donors
- repositories installable through the current governed `pip`-based isolated-venv contract
- two runtime shapes:
  - short-lived CLI/tool donors
  - long-running service donors

This design does not cover:

- arbitrary non-Python donors
- arbitrary build systems
- arbitrary repositories with undocumented startup flows
- project-specific deep business adapters as a prerequisite for first-class runtime support

## Architecture Boundary

This design must stay inside CoPaw's existing formal architecture.

It is not allowed to create:

- a second capability manager
- a parallel runtime state store
- a donor-only environment system

The formal mapping is:

- capability/package identity remains on the existing donor/package/source/candidate/trial/lifecycle spine
- runtime lifecycle truth is added as a scoped runtime-instance record attached to existing `CapabilityMount / WorkContext / EnvironmentMount / SessionMount / EvidenceRecord` semantics
- Runtime Center consumes projections of that same truth

In terms of the repository's architecture questions:

1. This belongs primarily to `capabilities / state / environment / evidence`.
2. The single truth source remains the formal capability + runtime/evidence state chain.
3. It must not bypass the unified capability execution/governance path.
4. It must not introduce a fourth capability vocabulary.
5. It must emit start/ready/run/stop/restart evidence.
6. It is intended to replace the current "external Python project = shell command only" limitation.

## Supported Donor Contract

### Supported Python CLI/Tool Donors

A donor is supported as a CLI/tool donor when all of the following are true:

- it can be installed through the current isolated-venv `pip` contract
- it exposes a stable `console_script` or `python -m package` entrypoint
- it is intended to run as a short-lived command rather than a resident service
- its execution output can be captured through the existing evidence sink

### Supported Python Service Donors

A donor is supported as a service donor when all of the following are true:

- it can be installed through the current isolated-venv `pip` contract
- it exposes a stable `console_script` or `python -m package` entrypoint
- it has at least one machine-verifiable readiness signal:
  - HTTP health/readiness endpoint
  - port binding probe
  - stdout ready marker
- it accepts a standard stop path:
  - governed process terminate/kill
  - or an explicit project stop command

### Explicit Non-Supported Cases

The following are outside the first supported contract:

- projects that require manual document reading just to discover their startup path
- projects with no stable entrypoint
- projects with no usable readiness signal
- projects whose startup requires a bespoke handwritten adapter before first execution
- projects that require multi-service orchestration not expressible inside the current bounded runtime contract

## Formal Runtime Shapes

Supported Python donors are classified into exactly two runtime shapes:

- `cli`
- `service`

Classification is not a new user-facing capability type. It is runtime contract metadata attached to the existing capability landing:

- `project-package`
- `adapter`
- `runtime-component`

Examples:

- `project:black` -> `project-package + cli`
- `adapter:pywinauto` -> `adapter + cli`
- `runtime:openspace` -> `runtime-component + service`

## Formal Runtime Truth

### Contract Truth vs Runtime Truth

This design must keep a hard split between:

- declarative runtime contract truth
- live runtime instance truth

Declarative runtime contract truth answers:

- what kind of donor runtime this installed capability claims to be
- which actions it supports
- which environment/evidence contract it requires
- which ready probe and stop strategy it prefers

Live runtime instance truth answers:

- which scoped runtime instance is active right now
- who owns it
- which process/port/session it is attached to
- whether it is ready/degraded/stopped/failed

The runtime instance record must not become the place where package identity or startup contract truth silently drifts.

### Contract Truth

For supported Python donors, formal runtime contract data is canonically owned by the installed external capability package truth.

That package-side runtime contract is the single declarative owner for:

- `runtime_kind`
- `supported_actions`
- `scope_policy`
- `ready_probe_kind`
- `ready_probe_config`
- `stop_strategy`
- `startup_entry_ref`
- `environment_requirements`
- `evidence_contract`

Everything else is projection only:

- `CapabilityMount` carries a read-only projection of that canonical package-side runtime contract for capability-graph consumption
- install/search responses carry a response projection of that same contract
- runtime-instance records may copy immutable audit snapshots such as `runtime_kind`, but they do not become the owner of declarative contract truth

The `CapabilityMount` for an external donor must surface this contract so that the capability graph itself knows whether the donor is `cli` or `service`, what it can do, and what evidence/environment contract it carries.

### New Scoped Runtime Record

Add a formal runtime record for installed external Python donors:

- `ExternalCapabilityRuntimeInstanceRecord`

This record represents the current scoped runtime truth of an installed donor capability instance. It is not a replacement for package truth. It is the missing runtime half of the donor model.

The core cardinality is:

- `1 installed capability -> N scoped runtime instances`

This is required so donor runtimes can stay on CoPaw's seat/session/work-context truth chain instead of degenerating into a single global daemon record.

Canonical v1 scope kinds are:

- `session`
- `work_context`
- `seat`

Uniqueness rule for active instances:

- maximum one active service runtime instance per `capability_id + scope_kind + canonical scope ref`

Canonical scope refs are:

- `session` -> `session_mount_id`
- `work_context` -> `work_context_id`
- `seat` -> `environment_ref`

CLI runs are allowed to create multiple historical execution instances, but each individual run still gets its own explicit scoped runtime-instance record.

### Required Fields

The runtime instance record should minimally carry:

- `runtime_id`
- `capability_id`
- `runtime_kind`
- `scope_kind`
- `work_context_id`
- `owner_agent_id`
- `environment_ref`
- `session_mount_id`
- `status`
- `command`
- `cwd`
- `process_id`
- `port`
- `health_url`
- `lease_owner_ref`
- `continuity_policy`
- `retention_policy`
- `last_started_at`
- `last_ready_at`
- `last_stopped_at`
- `last_exit_code`
- `last_error`
- `latest_start_evidence_id`
- `latest_healthcheck_evidence_id`
- `latest_stop_evidence_id`
- `latest_recovery_evidence_id`
- `artifact_refs`
- `replay_pointer`
- `metadata`

### Status Values

The first formal runtime-instance status family should be:

- `starting`
- `restarting`
- `ready`
- `degraded`
- `completed`
- `stopped`
- `failed`
- `orphaned`

This state must be persisted, queryable, and projected into Runtime Center. It must not be inferred ad hoc from a one-shot shell result.

Installed-but-never-started is contract truth, not runtime-instance truth. Runtime-instance records begin only when a scoped `run/start` action is admitted.

## Runtime Lifecycle Contract

### Install-Time Outcome

`/capability-market/projects/install` remains the install/materialization front-door.

After install, the system must:

1. resolve package entrypoint metadata
2. predict the donor runtime contract as `cli` or `service`
3. materialize the installed capability config
4. project the runtime contract onto the installed capability mount
5. return the runtime contract summary in the install response

Install must not silently perform a real service start just to prove runtime validity.

If active validation is needed, it must happen as an explicit scoped trial/runtime-validation action with evidence.

### CLI Lifecycle

CLI donors support:

- `describe`
- `run`
- `healthcheck`

CLI donors do not create a long-lived resident process. They still create explicit scoped execution-instance records on each admitted `run`.

CLI execution transitions:

- `starting -> completed`
- `starting -> failed`
- `completed -> archived history only`

### Service Lifecycle

Service donors support:

- `describe`
- `start`
- `healthcheck`
- `stop`
- `restart`

Service donors create scoped runtime instances rather than a single global process record.

State transitions:

- `starting -> ready`
- `starting -> failed`
- `ready -> degraded`
- `ready -> stopped`
- `stopped -> starting`
- `failed -> starting`
- `ready -> restarting`
- `degraded -> restarting`
- `restarting -> ready`
- `restarting -> failed`
- `ready|degraded -> orphaned` when runtime reconciliation loses truthful ownership

Ownership and continuity rules:

- each service runtime instance must be attached to a formal scope
- session-scoped instances stop on session end by default
- broader-scope retained instances must declare an explicit retention policy
- runtime bootstrap must reconcile persisted instances after restart and detect orphaned processes rather than assuming readiness
- restart/recovery must emit explicit evidence rather than mutating status silently

Canonical v1 retention policies:

- `until-session-end`
- `until-work-context-close`
- `retained-seat-runtime`

Legal orphan-resolution actions:

- `reclaim` when environment/session lineage still matches and bounded probes succeed
- `stop`
- `archive`
- `start_new`

These actions must map back onto the existing `EnvironmentMount / SessionMount` recovery chain rather than creating donor-local recovery semantics.

The first version does not need a complex supervisor. It does need truthful lifecycle state and governed actions.

## Detection and Contract Resolution

### Install-Time Detection Order

The runtime contract resolver should work in this order:

1. inspect package metadata:
   - distribution name
   - package version
   - console scripts
   - entry module
2. inspect lightweight help output:
   - service-shaped flags such as `--host`, `--port`, `serve`, `server`, `api`, `daemon`, `worker`
3. inspect configured donor hints when present

This detection phase is predictive only. It must not collapse install into runtime execution.

Active validation belongs to a later explicit scoped action:

- CLI runtime validation via `run`
- service runtime validation via `start + ready probe`

### Ready Probe Kinds

The first supported ready probe kinds are:

- `http`
- `port`
- `stdout`
- `none` for CLI

### Thin Hint Layer

The system may keep a thin optional hint layer for hard-to-detect but still supported donors.

Hints may specify only bounded runtime contract details such as:

- preferred runtime kind
- default startup args
- default port
- health path
- stdout ready marker
- stop strategy

Hints must not become a per-project handwritten execution adapter framework. The default path remains generic contract resolution first.

## Execution Model

### Install Is Not Runtime

The current model collapses installation and execution into the same shell abstraction. That is the core defect being corrected.

After this design lands:

- install truth lives in external package config + donor/package/source truth
- runtime contract truth lives on the installed capability/package projection
- runtime truth lives in `ExternalCapabilityRuntimeInstanceRecord`
- execution actions mutate runtime truth and emit evidence

### Capability Execution

The capability execution layer must stop treating every external donor as "pick one shell command and run it".

Instead:

- `cli` actions call the bounded run path
- `service` actions call lifecycle verbs
- raw arbitrary `command` execution must no longer be the primary runtime contract for supported donors
- capability execution resolves supported actions from the capability's formal runtime contract, not from a donor-only side record

The capability execution layer may retain an escape hatch only for unsupported/manual donors. Once a donor is classified as supported under this contract, its formal execution path is exclusive to typed lifecycle verbs and must not silently fall back to generic governed shell execution.

## API Surface

### Install/Search Front-Door

Keep:

- `POST /capability-market/projects/search`
- `POST /capability-market/projects/install`

Extend install/search payloads to expose runtime contract summaries:

- `runtime_kind`
- `supported_actions`
- `ready_probe_kind`
- `predicted_default_port`
- `predicted_health_path`
- `scope_policy`

Search/install must expose predicted/default contract fields only. Live instance facts such as bound `port` and effective `health_url` belong only to runtime-instance truth after a scoped action has actually started the donor.

### Runtime Action Front-Door

Add formal runtime actions for installed external donors.

Recommended operator-facing endpoints:

- `GET /runtime-center/capabilities/external-runtimes`
- `GET /runtime-center/capabilities/external-runtimes/{runtime_id}`
- `GET /runtime-center/capabilities/{capability_id}/runtime-contract`
- `POST /runtime-center/capabilities/{capability_id}/runtime/run`
- `POST /runtime-center/capabilities/{capability_id}/runtime/start`
- `POST /runtime-center/capabilities/external-runtimes/{runtime_id}/healthcheck`
- `POST /runtime-center/capabilities/external-runtimes/{runtime_id}/stop`
- `POST /runtime-center/capabilities/external-runtimes/{runtime_id}/restart`

This split keeps:

- discovery/install under capability market
- runtime operations under Runtime Center/operator surfaces

These routes must not become a second imperative execution front-door.

They must route through a governed runtime-operation service facade that carries:

- `capability_id`
- `runtime_id` for existing-instance verbs
- `work_context_id`
- `environment_ref`
- `session_mount_id`
- `scope_kind`
- `owner_agent_id`
- requested action
- action payload
- actor identity

Admission rules:

- `start` and `run` must first resolve the effective scoped capability mount/allowlist for the supplied seat/session/work-context before execution
- `stop/restart/healthcheck` operate on a resolved `runtime_id`, not an ambiguous capability-global process
- `start` on a scope that already has an active instance for the same `capability_id + scope_kind + canonical scope ref` must reuse or explicitly reject duplicate creation rather than silently spawning a second active runtime

Non-auto actions must use the existing governed-write flow and return typed admission states such as:

- `accepted`
- `waiting-confirm`
- `completed`
- `failed`

When confirmation is required, the response must include the formal `decision_request_id` rather than bypassing governance.

### Runtime Action Risk Model

Initial policy:

- `healthcheck` -> `auto`
- `run` -> `guarded`
- `start` -> `guarded`
- `restart` -> `guarded`
- `stop` -> `auto` when same-scope owner and no broader retention policy, otherwise `guarded`

This policy may tighten for high-risk external surfaces, but the contract must be explicit.

### Typed Runtime Action Payloads

Supported runtime actions must use typed bounded payloads, not a generic raw shell bag.

Allowed v1 payload shapes:

- `run`
  - `args: list[str]`
  - `timeout_sec`
  - `input_artifact_ref`
- `start`
  - `arg_profile`
  - `port_override`
  - `health_path_override`
  - `retention_policy`
- `healthcheck`
  - `timeout_sec`
  - `probe_mode`
- `restart`
  - `reason`
- `stop`
  - `reason`

Forbidden as formal runtime action payloads:

- raw shell command strings
- arbitrary environment variable dictionaries
- arbitrary cwd mutation outside the donor's governed workspace root
- free-form stop/start command replacement

If a donor needs that level of freedom, it is outside the supported contract and must not be presented as a formal runtime capability.

## Runtime Center Visibility

Runtime Center must show external donor runtime truth as first-class operator data.

Minimum read-model fields:

- capability identity
- landing kind: `project-package / adapter / runtime-component`
- runtime kind: `cli / service`
- scope kind/key
- work context / session linkage
- owner/lease identity
- continuity policy
- retention policy
- runtime status
- capability enabled state from contract projection
- process id
- port
- health URL
- ready probe kind
- command/cwd summary
- last started
- last ready
- last stopped
- last error
- latest evidence link
- latest `decision_request_id` when pending confirmation exists
- orphan reason / recovery options when status is `orphaned`
- supported actions

Runtime Center must also be able to distinguish:

- installed-but-never-validated contract
- scoped active runtime instance
- reconciled-orphaned runtime that needs operator review

This is required so installed donors stop being invisible shells and become explicit runtime assets.

## Evidence Contract

Every formal runtime action must emit evidence:

- install
- classify
- start
- ready
- healthcheck
- run
- stop
- restart
- failure/timeout

Evidence metadata must preserve:

- `capability_id`
- `runtime_id`
- `runtime_kind`
- `scope_kind`
- `scope_key`
- `work_context_id`
- `environment_ref`
- `session_mount_id`
- `action`
- `process_id`
- `port`
- `health_url`
- `ready_probe_kind`
- `source_url`
- `package_ref`
- actor identity
- `decision_request_id` when governance applies

When runtime validation is executed as part of donor adoption/trial flow, the evidence may be linked to the existing donor candidate/trial chain. It must not invent a second trial system.

## Verification Standard

This work is complete only when all three layers are true.

### 1. Unit/Integration

Must cover:

- CLI contract resolution
- service contract resolution
- scoped runtime instance creation
- lifecycle status transitions
- ready probe success/failure
- stop/restart behavior
- bootstrap reconciliation / orphan detection
- Runtime Center read-model projection
- governed admission and `decision_request_id` flow

### 2. Repository Regression

Must preserve:

- capability market
- capability catalog
- capability execution
- donor/source/package truth
- evidence sinks
- Runtime Center capability read surfaces

### 3. Live Smoke

At least two real Python donors must be validated:

- one CLI/tool donor
- one service donor

The live smoke bar is:

- discover
- install
- classify
- run or start
- ready or successful one-shot execution
- stop for service donors

For service donors, live smoke must also prove:

- scoped runtime instance creation
- Runtime Center visibility of that instance
- truthful post-stop state

`--help` alone is not sufficient evidence for service closure.

## Rollout Recommendation

Implement in this order:

1. runtime contract projection onto installed capabilities
2. scoped runtime instance record + persistence
3. governed lifecycle executor for `start / healthcheck / stop / restart / run`
4. runtime bootstrap reconciliation/orphan detection
5. Runtime Center read-model and endpoints
6. live smoke against one CLI and one service donor

## Non-Goals

This design does not claim:

- all languages are automatically supported
- all Python repos are automatically supported
- all supported donors need zero hints
- OpenSpace-specific business integration is required for phase 1

The goal is narrower and stricter:

Supported Python donors must stop being decorative shell wrappers and become formally operable runtime capabilities.
